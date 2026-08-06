from cryptography.fernet import Fernet
from imio.googleauthenticator import helpers
from imio.googleauthenticator.browser.controlpanel import GoogleAuthenticatorSettingsEditForm
from imio.googleauthenticator.helpers import decrypt_seed
from imio.googleauthenticator.helpers import enable_two_factor_authentication_for_users
from imio.googleauthenticator.helpers import encrypt_seed
from imio.googleauthenticator.helpers import extract_ip_address_from_request
from imio.googleauthenticator.helpers import generate_secret
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_barcode_image
from imio.googleauthenticator.helpers import get_browser_hash
from imio.googleauthenticator.helpers import get_ip_addresses_whitelist
from imio.googleauthenticator.helpers import get_ip_ranges
from imio.googleauthenticator.helpers import get_or_create_secret
from imio.googleauthenticator.helpers import get_secret
from imio.googleauthenticator.helpers import get_ska_secret_key
from imio.googleauthenticator.helpers import get_token_description
from imio.googleauthenticator.helpers import validate_bar_code_reset_token
from imio.googleauthenticator.helpers import validate_token
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from onetimepass import get_hotp
from onetimepass import get_totp
from plone import api
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from Products.PlonePAS.sheet import PropertyValueError
from Products.statusmessages.interfaces import IStatusMessage

import base64
import logging
import os
import time
import unittest2 as unittest


class TestIPWhitelisting(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def test_get_ip_ranges_always_returns_networks_and_accepts_single_ip(self):
        ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
        self.assertEqual(
            [IPv4Network(u'127.0.0.1'), IPv4Network(u'192.168.0.0/16')],
            ranges)

    def test_get_ip_ranges_can_be_used_for_containment_testing(self):
        ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
        self.assertTrue(any(IPv4Address(u'127.0.0.1') in r for r in ranges))
        self.assertTrue(any(IPv4Address(u'192.168.1.1') in r for r in ranges))
        self.assertFalse(any(IPv4Address(u'10.0.0.0') in r for r in ranges))

    def test_get_ip_ranges_skips_invalid_entries_instead_of_raising(self):
        """CR-03 regression: a trailing blank line in the admin whitelist
        setting (or any other malformed single entry) must not crash every
        login site-wide.
        """
        ranges = get_ip_ranges(['127.0.0.1', '', 'not-an-ip', '192.168.0.0/16'])
        self.assertEqual(
            [IPv4Network(u'127.0.0.1'), IPv4Network(u'192.168.0.0/16')],
            ranges)

    def test_get_ip_addresses_whitelist_drops_blank_lines(self):
        """CR-03 regression: a trailing newline in the control panel's
        ip_addresses_whitelist Text field (the ordinary result of hitting
        Enter after the last address) must not produce an empty '' entry
        that later blows up ipaddress.ip_network('').
        """
        from imio.googleauthenticator import helpers

        class FakeSettings(object):
            ip_addresses_whitelist = '127.0.0.1\n192.168.0.0/16\n'

        original = helpers.get_app_settings
        helpers.get_app_settings = lambda: FakeSettings()
        try:
            self.assertEqual(
                ['127.0.0.1', '192.168.0.0/16'],
                get_ip_addresses_whitelist(request=object()))
        finally:
            helpers.get_app_settings = original

    def test_extract_ip_address_from_request_ignores_malformed_ip(self):
        """CR-02 regression: a malformed/attacker-controlled X-Forwarded-For
        value must not raise ValueError from inside is_whitelisted_client(),
        the first statement of authenticateCredentials.
        """
        request = {'REMOTE_ADDR': '127.0.0.1',
                   'HTTP_X_FORWARDED_FOR': 'not-an-ip'}
        self.assertIsNone(extract_ip_address_from_request(request=request))

    def test_extract_ip_address_does_not_treat_public_172_216_as_private(self):
        """WR-01 regression: the old '172.'/'192.' string-prefix match swept
        up all of 172.0.0.0/8 and 192.0.0.0/8 (only 172.16.0.0/12 and
        192.168.0.0/16 are actually RFC1918 private), so a client whose real
        address happened to start with one of these prefixes -- e.g.
        Google's public 172.217.0.0/16 -- got silently skipped in favour of
        the next, attacker-controlled hop in the chain.
        """
        request = {'REMOTE_ADDR': '10.0.0.1',
                   'HTTP_X_FORWARDED_FOR': '172.217.0.1, 172.16.0.1'}
        self.assertEqual(
            IPv4Address(u'172.217.0.1'),
            extract_ip_address_from_request(request=request))

    def test_extract_ip_address_still_strips_real_private_hops(self):
        """Companion to the above: genuinely private hops (172.16.0.0/12)
        are still stripped so the first public hop in the chain is used.
        """
        request = {'REMOTE_ADDR': '10.0.0.1',
                   'HTTP_X_FORWARDED_FOR': '172.16.0.1, 8.8.8.8'}
        self.assertEqual(
            IPv4Address(u'8.8.8.8'),
            extract_ip_address_from_request(request=request))


class TestSkaSecretKey(unittest.TestCase, BaseTest):
    """Concern-named class, like TestIPWhitelisting above: this file already
    groups by concern rather than by module (R7), so the ska key derivation
    and its browser-hash guard live in one class named for what they protect
    rather than a second class named for test_helpers.py itself.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        # PLONE_FIXTURE logs the test user in (and caches its property
        # sheets) before this class's own setUp installs the add-on's
        # memberdata_properties.xml. Re-login so the cached user is rebuilt
        # against the now-current portal_memberdata schema; otherwise
        # setMemberProperties silently drops 'two_factor_authentication_secret'
        # per MutablePropertySheet.setProperties (CLAUDE.md's documented
        # "undeclared properties are popped" hazard -- here the property IS
        # declared, but the cached sheet predates the declaration).
        login(self.portal, TEST_USER_NAME)

    def test_get_ska_secret_key(self):
        """BUG-04: the derivation must separate its three components instead
        of bare-concatenating them, so two component tuples sharing the same
        concatenation derive to different keys.
        """
        user = api.user.get_current()

        # EXACT SHAPE: pins ordering (user secret first), the empty
        # component (browser hash), the delimiter and the length semantics,
        # all in one assertion.
        user.setMemberProperties(
            mapping={'two_factor_authentication_secret': 'ab'})
        get_app_settings().ska_secret_key = u'cd'
        result = get_ska_secret_key(
            request=self.request, user=user, use_browser_hash=False)
        self.assertEqual(u'2:ab0:2:cd', result)
        self.assertIsInstance(result, unicode)

        # THE COLLISION IT PREVENTS: the fixture above really does collide
        # under the old bare-concatenation scheme. Without this line the
        # fixture below looks arbitrary and a future editor could
        # "simplify" it into one that no longer collides.
        self.assertEqual(u'ab' + u'' + u'cd', u'a' + u'' + u'bcd')

        user.setMemberProperties(
            mapping={'two_factor_authentication_secret': 'a'})
        get_app_settings().ska_secret_key = u'bcd'
        second_result = get_ska_secret_key(
            request=self.request, user=user, use_browser_hash=False)
        self.assertNotEqual(result, second_result)

        # MINT UNTOUCHED: a non-empty ska_secret_key already in place is not
        # re-minted by the derivation -- the registry value read back after
        # both derive calls above is still the one explicitly set here.
        self.assertEqual(u'bcd', get_app_settings().ska_secret_key)

    def test_get_ska_secret_key_handles_missing_secret_property(self):
        """CR-01/WR-02 regression: a user whose
        two_factor_authentication_secret property is unset/None (e.g. a
        freshly created member that never went through
        get_or_create_secret, or a cached property sheet that predates the
        memberdata_properties.xml declaration -- see this class's setUp
        docstring for why that can happen) must not crash
        get_ska_secret_key() with 'TypeError: object of type NoneType has
        no len()'. The old bare "{0}{1}{2}".format(...) concatenation
        coerced None to the literal string "None" and never crashed; the
        netstring-style len()-based derivation (BUG-04) must keep that same
        crash-safety by coercing a falsy/None component to '' first, like
        the sibling get_secret() already does.
        """
        class FakeUser(object):
            def getProperty(self, name, default=None):
                return None

        result = get_ska_secret_key(
            request=self.request, user=FakeUser(), use_browser_hash=False)
        self.assertIsInstance(result, unicode)

    def test_get_browser_hash(self):
        """Regression guard, not a fix for a live bug: get_browser_hash's
        `except` branch already returns '' today (not None). It stopped
        being merely cosmetic the moment Task 1's length-prefixed derivation
        landed -- that derivation takes len() of this return value, and
        len(None) raises TypeError on a login path. Nobody should go looking
        for a currently-firing bug here; this pins the guard against a
        future edit reintroducing a fall-off-the-end None.
        """
        result = get_browser_hash(request={})
        self.assertEqual('', result)
        self.assertIsNotNone(result)

        happy_result = get_browser_hash(
            request={'HTTP_USER_AGENT': 'Mozilla/5.0'})
        self.assertEqual(40, len(happy_result))


class TestSeedEncryption(unittest.TestCase, BaseTest):
    """Concern-named class, like TestIPWhitelisting and TestSkaSecretKey
    above: this file groups by concern rather than by module (R7). This
    class covers the seed's whole storage lifecycle -- generation, Fernet
    encryption, storage, decryption and validation through a real
    onetimepass TOTP round trip -- rather than one helper function.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        # See TestSkaSecretKey.setUp's docstring: PLONE_FIXTURE caches the
        # test user's property sheets before this add-on's
        # memberdata_properties.xml is applied, so a re-login is mandatory
        # or setMemberProperties silently drops
        # two_factor_authentication_secret.
        login(self.portal, TEST_USER_NAME)

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()

    def tearDown(self):
        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key

    def test_seed_encryption_round_trip(self):
        """SEC-01/SEC-04/SEC-05/SEC-06 tracer: a single linear walk of the
        enrollment-then-validation path, real memberdata storage, a real
        onetimepass TOTP round trip and a real in-process QR render.
        """
        user = api.user.get_current()

        seed = generate_secret(user)

        # SEC-06 boundary: 160 bits, above RFC 4226 Section 4 R6's 128-bit floor.
        self.assertEqual(20, len(base64.b32decode(seed)), 'SEC-06 boundary')
        # SEC-06 precision: 20 bytes is an exact multiple of base32's 5-byte
        # block, so the encoded seed is exactly 32 characters, no padding.
        self.assertEqual(32, len(seed), 'SEC-06 precision')
        self.assertNotIn('=', seed, 'SEC-06 precision')

        stored = user.getProperty('two_factor_authentication_secret')
        self.assertTrue(stored.startswith(u'v1$'), 'SEC-04')

        # SEC-01: the plaintext seed is not a substring of the ciphertext.
        self.assertNotIn(seed, stored, 'SEC-01')

        # Round trip through real memberdata storage.
        self.assertEqual(seed, get_secret(user))

        # SEC-01 end-to-end, and the assertion that catches Pitfall A: a
        # real onetimepass token computed from the plaintext seed validates
        # through get_secret -> decrypt_seed.
        # as_string=True: get_totp's library default returns a bare,
        # non-zero-padded int, so roughly one attempt in ten produces
        # fewer than six characters and would fail validate_token's new
        # exact-six-ASCII-digit gate intermittently. Do not "simplify"
        # this back to the bare call.
        self.assertTrue(
            validate_token(get_totp(seed, as_string=True), user=user),
            'SEC-01 end-to-end')

        # SEC-05: the QR is a locally rendered data: URI, no external host,
        # and the payload decodes to a real PNG.
        img = get_barcode_image('bob', 'example.com', seed)
        self.assertTrue(img.startswith('data:image/png;base64,'), 'SEC-05')
        self.assertNotIn('googleapis', img, 'SEC-05')
        payload = base64.b64decode(img.split(',', 1)[1])
        self.assertTrue(payload.startswith(b'\x89PNG'), 'SEC-05')

        # The read branch decrypts, it does not re-roll: two calls return
        # the same plaintext seed and the stored ciphertext is unchanged.
        first = get_or_create_secret(user)
        second = get_or_create_secret(user)
        self.assertEqual(seed, first)
        self.assertEqual(first, second)
        self.assertEqual(
            stored, user.getProperty('two_factor_authentication_secret'))

    def test_get_token_description_escapes_html_metacharacters_in_secret(self):
        """WR-02: ``get_token_description``'s return value is assigned as a
        z3c.form field description and rendered with
        ``tal:content="structure description"`` (unescaped). Today the
        interpolated ``secret`` is safe only because
        ``generate_secret()``'s base32 alphabet happens to contain no HTML
        metacharacter -- nothing in ``get_token_description`` itself
        enforces that. Patches ``get_or_create_secret`` to return a value
        that violates the invariant, standing in for a future code path
        (an imported legacy seed, a different encoding) that could produce
        one for real.
        """
        user = api.user.get_current()

        original = helpers.get_or_create_secret
        helpers.get_or_create_secret = (
            lambda user, overwrite=False: '<script>alert(1)</script>')
        try:
            description = get_token_description(user=user)
        finally:
            helpers.get_or_create_secret = original

        self.assertNotIn(
            '<script>alert(1)</script>', description,
            'The malicious secret reached the returned HTML unescaped.')
        self.assertIn(
            '&lt;script&gt;alert(1)&lt;/script&gt;', description,
            'The secret was not escaped at the point of interpolation.')

    def test_seed_encryption_fails_closed(self):
        """SEC-03 enrollment half: encrypt_seed/generate_secret refuse with
        the key unset, with the key garbage (not valid base64 at all -- the
        TypeError-from-binascii branch), and with the key valid base64 but
        the wrong length (the ValueError branch) -- never falling back to a
        plaintext store or the input unchanged. Also pins that the
        exception text names ENV_VAR_NAME and never the key's own value,
        and that an unknown ciphertext envelope version refuses rather than
        attempting a decrypt.
        """
        user = api.user.get_current()
        pre_call_property = user.getProperty('two_factor_authentication_secret')

        bad_keys = (
            lambda: None,
            lambda: 'not-a-valid-fernet-key',
            lambda: base64.urlsafe_b64encode('short'),
        )
        for bad_key in bad_keys:
            original = helpers.get_encryption_key
            helpers.get_encryption_key = bad_key
            try:
                self.assertRaises(ValueError, encrypt_seed, 'ABCDEFGH')
                self.assertRaises(ValueError, generate_secret, user)
                # No plaintext leaked on the failure path.
                self.assertEqual(
                    pre_call_property,
                    user.getProperty('two_factor_authentication_secret'))
            finally:
                helpers.get_encryption_key = original

        # The key value never appears in the exception message -- only the
        # variable name does.
        distinctive_key = 'this-is-a-distinctive-bogus-key-value'
        original = helpers.get_encryption_key
        helpers.get_encryption_key = lambda: distinctive_key
        try:
            try:
                encrypt_seed('ABCDEFGH')
                self.fail('expected ValueError')
            except ValueError as exc:
                self.assertIn('IMIO_GOOGLEAUTHENTICATOR_SEED_KEY', str(exc))
                self.assertNotIn(distinctive_key, str(exc))
        finally:
            helpers.get_encryption_key = original

        # Version prefix: an unknown/missing envelope version refuses
        # rather than attempting a decrypt, with the valid key from setUp
        # still in place.
        self.assertRaises(ValueError, decrypt_seed, u'no-prefix-here')
        self.assertRaises(ValueError, decrypt_seed, u'v2$whatever')

    def test_validate_token_refuses_a_user_with_no_stored_seed(self):
        """G-03-2 regression: a secret-less user must get a refusal, not a
        500.

        ``get_secret`` returns ``None`` *implicitly* for a user whose
        ``two_factor_authentication_secret`` is empty, and ``onetimepass``
        base32-decodes whatever it is handed, so before the guard this raised
        ``TypeError('Incorrect secret')`` straight out of the token form.
        Reported from a real instance: submitting any code at
        ``@@google-authenticator-token`` after arriving without a signed
        ``auth_user`` parameter 500'd regardless of whether the code was
        correct.

        The second half pins the guard's narrowness, which is the part a
        careless refactor breaks: an *undecryptable* stored seed must still
        raise, because answering "wrong token" to a broken-key condition
        would turn a fail-closed refusal into a silent security downgrade.
        """
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'two_factor_authentication_secret': ''})

        # Precondition -- the implicit None that reaches onetimepass.
        self.assertIsNone(get_secret(user))

        self.assertFalse(
            validate_token('123456', user=user),
            'A user with no stored seed must be refused, not crashed on.')

        # Narrowness: a stored seed that cannot be decrypted still raises.
        generate_secret(user)
        original = helpers.get_encryption_key
        helpers.get_encryption_key = lambda: Fernet.generate_key()
        try:
            self.assertRaises(
                ValueError, validate_token, '123456', user=user)
        finally:
            helpers.get_encryption_key = original

    def test_is_site_local_user_distinguishes_a_root_account(self):
        """T-03-23: the discriminator behind the enrolment refusal.

        SITE_OWNER_NAME is the fixture's Zope-root user, the analog of the
        buildout ``inituser`` admin. The asymmetry this pins is the whole
        reason the bug existed: ``plone.api.user.get`` resolves a root account
        to a MemberData and ``portal_memberdata`` stores properties against
        it, so every obvious check reports the account as perfectly ordinary.
        Only the site PAS lookup tells them apart.
        """
        member = api.user.get(username=TEST_USER_NAME)
        root = api.user.get(username=SITE_OWNER_NAME)

        # Both look like real users through plone.api -- that is the trap.
        self.assertIsNotNone(member)
        self.assertIsNotNone(root)

        self.assertTrue(helpers.is_site_local_user(member))
        self.assertFalse(helpers.is_site_local_user(root))

        # The bulk-enrolment path cannot reach a root account at all, which is
        # why the guard is only wired into the two self-service forms. If this
        # ever starts including root accounts, helpers.py's bulk enable needs
        # the same guard.
        self.assertNotIn(
            SITE_OWNER_NAME, [u.getId() for u in api.user.get_users()])

    def test_encryption_key_is_read_per_call(self):
        """SEC-02's behavioural proof: every fail-closed assertion above
        injects by rebinding the module's key reader, which exercises the
        callers but never proves the reader itself reads os.environ fresh --
        a module-scope ``_KEY = os.environ.get(ENV_VAR_NAME)`` would satisfy
        the source-grep criterion too. This method must NOT rebind that
        reader; rewriting it to do so would delete the only assertion in
        this phase that distinguishes a per-call read from a frozen one.
        """
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()
        ciphertext = encrypt_seed('ABCDEFGH')

        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()
        self.assertRaises(ValueError, decrypt_seed, ciphertext)

    def test_ciphertext_is_a_safe_ska_key_component(self):
        """Closes 02-SECURITY.md R-02-02 by assertion rather than carrying
        the ASCII-by-construction assumption forward a third time:
        get_ska_secret_key() must survive a real v1$<fernet-token>
        ciphertext as the ``user_secret`` netstring component.
        """
        user = api.user.get_current()
        # overwrite=True: force a fresh secret encrypted under this test's
        # own key, rather than trusting a property that may already be set
        # by an earlier test method in this layer -- see TestSkaSecretKey
        # .setUp's docstring for the same hazard's re-login half.
        get_or_create_secret(user, overwrite=True)
        ciphertext = user.getProperty('two_factor_authentication_secret')

        result = get_ska_secret_key(
            request=self.request, user=user, use_browser_hash=False)

        self.assertIsInstance(result, unicode)
        self.assertIn(ciphertext, result)
        self.assertTrue(result.startswith(u'{0}:'.format(len(ciphertext))))

    def test_bulk_enable_reports_failure_when_seed_key_is_broken(self):
        """T-03-21: before this task, a control-panel Save or the
        @@google-authenticator-enable-for-all-users view with a missing or
        malformed key showed a success message while enrolling zero users --
        the same silent-security-control-removal shape as Phase 1's
        _dont_swallow_my_exceptions gap and Phase 2's CR-02 transaction-abort
        bug, landing on what is plausibly an operator's first action before
        the Puppet fragment ships. Message TYPES are asserted, not message
        text: the strings are zope.i18nmessageid Messages and comparing
        rendered text couples the assertion to translation state.
        """
        user = api.user.get_current()
        # google-authenticator-enable-for-all-users and the control panel
        # both require cmf.ManagePortal.
        setRoles(self.portal, TEST_USER_ID, ['Manager'])

        original = helpers.get_encryption_key
        helpers.get_encryption_key = lambda: None
        try:
            # 1. The mechanism: the loop no longer absorbs the key failure.
            self.assertRaises(
                ValueError,
                enable_two_factor_authentication_for_users, [user])

            # 2. The @@google-authenticator-enable-for-all-users view.
            IStatusMessage(self.request).show()  # drain prior messages
            view = self.portal.restrictedTraverse(
                '@@google-authenticator-enable-for-all-users')
            view.request = self.request
            view.index()
            types = [m.type for m in IStatusMessage(self.request).show()]
            self.assertIn('error', types)
            self.assertNotIn('info', types)

            # 3. The control panel Save. IGoogleAuthenticatorSettings'
            # fieldset(None, ...) puts all three fields into a single
            # unnamed group rather than form.fields directly, so the
            # widget -- and its request key -- lives in
            # form.groups[0].widgets, not form.widgets.
            IStatusMessage(self.request).show()  # drain prior messages
            form = GoogleAuthenticatorSettingsEditForm(
                self.portal, self.request)
            form.update()
            widget_name = form.groups[0].widgets['globally_enabled'].name
            self.request.form[widget_name] = u'selected'
            data, errors = form.extractData()
            if errors:
                # Same one-line fallback as 03-03 Task 2 uses for its
                # widget key: report the actual widget name rather than
                # guessing further.
                print(form.groups[0].widgets['globally_enabled'].name)
            handleSave = GoogleAuthenticatorSettingsEditForm.handleSave.func
            handleSave(form, None)
            types = [m.type for m in IStatusMessage(self.request).show()]
            self.assertIn('error', types)
            self.assertNotIn('info', types)
        finally:
            helpers.get_encryption_key = original

    def test_user_creation_fails_closed_when_seed_key_is_broken(self):
        """T-03-22: userdataschema.userCreatedHandler runs
        get_or_create_secret on every new-user IPrincipalCreatedEvent
        because globally_enabled defaults True, so a missing/malformed key
        does not only refuse logins -- it stops account creation entirely.
        Correct fail-closed, different blast radius: plan 03-02's DOC-03
        records it in README.rst so an operator learns it from the docs
        rather than from a broken registration form.
        """
        setRoles(self.portal, TEST_USER_ID, ['Manager'])

        # Control, run first: with the good key from setUp, account
        # creation succeeds and the new user gets a real ciphertext.
        control_user = api.user.create(
            email='seed-fail-closed-control@example.com',
            username='seed-fail-closed-control-user',
            password='Secret0123!')
        self.assertTrue(
            control_user.getProperty(
                'two_factor_authentication_secret').startswith(u'v1$'))

        original = helpers.get_encryption_key
        helpers.get_encryption_key = lambda: None
        try:
            broken_username = 'seed-fail-closed-broken-user'
            self.assertRaises(
                ValueError, api.user.create,
                email='seed-fail-closed-broken@example.com',
                username=broken_username,
                password='Secret0123!')
            # Observed, not assumed (the plan's own philosophy for its two
            # Open Questions, applied here): a real HTTP request rolls this
            # back via transaction.abort() when the subscriber's raise
            # escapes, but this synchronous test call crosses no such
            # boundary, so the MemberData object created before the
            # subscriber's get_or_create_secret call is still visible here.
            # What the raise DOES guarantee even in-process: it happens
            # before setMemberProperties(enable_two_factor_authentication=
            # True), so a half-made account is never left enrolled, and
            # generate_secret's own raise (inside get_or_create_secret)
            # happens before its setMemberProperties too, so no secret is
            # stored either.
            broken_user = api.user.get(username=broken_username)
            if broken_user is not None:
                self.assertFalse(broken_user.getProperty(
                    'enable_two_factor_authentication', False))
                self.assertFalse(broken_user.getProperty(
                    'two_factor_authentication_secret', ''))
        finally:
            helpers.get_encryption_key = original


class TestDriftAndReplay(unittest.TestCase, BaseTest):
    """Concern-named class, like TestIPWhitelisting/TestSkaSecretKey/
    TestSeedEncryption above: this file groups by concern rather than by
    module (R7, WR-03 precedent -- see tests/test_setuphandlers.py's class
    docstring). Plan 05-01 adds the property round-trip method below; plan
    05-02 adds this class's remaining drift/replay methods.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        # See TestSkaSecretKey.setUp's docstring: PLONE_FIXTURE caches the
        # test user's property sheets before this add-on's
        # memberdata_properties.xml is applied, so a re-login is mandatory
        # or setMemberProperties silently drops the new properties.
        login(self.portal, TEST_USER_NAME)

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()

    def tearDown(self):
        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key
        # This layer's cross-test leakage (see the note in setUp) means a
        # recovery-code salt/hash set minted by one test method could
        # otherwise survive into the next one in this class.
        api.user.get_current().setMemberProperties(mapping={
            'two_factor_authentication_recovery_codes_salt': '',
            'two_factor_authentication_recovery_codes_hashes': (),
        })

    def test_new_memberdata_properties_round_trip(self):
        """MFA-13: each of the three new memberdata properties survives a
        setMemberProperties() -> getProperty() round trip as a Python int.
        An undeclared property is silently skipped by setMemberProperties
        with no exception and no log line, so reading back the declared
        default 0 instead of the written value is exactly the failure this
        test exists to catch.
        """
        user = api.user.get_current()

        user.setMemberProperties(mapping={
            'two_factor_authentication_failed_attempts': 3,
            'two_factor_authentication_locked_until': 1234567890,
            'two_factor_authentication_last_interval': 42,
        })

        failed_attempts = user.getProperty(
            'two_factor_authentication_failed_attempts')
        locked_until = user.getProperty(
            'two_factor_authentication_locked_until')
        last_interval = user.getProperty(
            'two_factor_authentication_last_interval')

        self.assertEqual(3, failed_attempts)
        self.assertIsInstance(failed_attempts, int)
        self.assertEqual(1234567890, locked_until)
        self.assertIsInstance(locked_until, int)
        self.assertEqual(42, last_interval)
        self.assertIsInstance(last_interval, int)

        # MFA-13 precision edge: a float value is refused, not silently
        # coerced -- this is why production code always int()-coerces
        # before the write.
        self.assertRaises(
            PropertyValueError,
            user.setMemberProperties,
            mapping={'two_factor_authentication_locked_until': time.time()})

        # Idempotent-reset edge: writing 0 to an already-0 counter is
        # accepted and reads back 0.
        user.setMemberProperties(
            mapping={'two_factor_authentication_failed_attempts': 0})
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_failed_attempts'))
        user.setMemberProperties(
            mapping={'two_factor_authentication_failed_attempts': 0})
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_failed_attempts'))

    def test_validate_token_accepts_previous_interval(self):
        """MFA-05: a code generated for the interval exactly one step back
        (current - 1) is accepted, and the stored interval then reads back
        current - 1.
        """
        user = api.user.get_current()
        seed = helpers.generate_secret(user)
        user.setMemberProperties(
            mapping={'two_factor_authentication_last_interval': 0})

        current = int(time.time()) // helpers.TOTP_INTERVAL_SECONDS
        previous_code = get_hotp(
            seed, intervals_no=current - 1, as_string=True)

        self.assertTrue(validate_token(previous_code, user=user))
        self.assertEqual(
            current - 1,
            user.getProperty('two_factor_authentication_last_interval'))

    def test_validate_token_rejects_future_interval(self):
        """MFA-05 boundary: a code generated for the interval one step
        forward (current + 1) is refused -- the window widens backward
        only (T-05-13). Non-vacuity control in the same method: the code
        for `current` from the same seed IS accepted, so the refusal
        cannot be an artifact of a broken fixture.
        """
        user = api.user.get_current()
        seed = helpers.generate_secret(user)
        user.setMemberProperties(
            mapping={'two_factor_authentication_last_interval': 0})

        current = int(time.time()) // helpers.TOTP_INTERVAL_SECONDS
        future_code = get_hotp(
            seed, intervals_no=current + 1, as_string=True)

        self.assertFalse(validate_token(future_code, user=user))
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_last_interval'))

        # Non-vacuity control: the current interval's own code from the
        # same seed and fixture IS accepted.
        current_code = get_hotp(seed, intervals_no=current, as_string=True)
        self.assertTrue(validate_token(current_code, user=user))

    def test_validate_token_rejects_replayed_interval(self):
        """MFA-06: a code already accepted is refused on a second
        submission, because the accepted interval number is stored and any
        newly matched interval less than or equal to it is a replay.
        Adjacency asserted explicitly: an interval exactly equal to the
        stored last-accepted interval is refused, and the next interval up
        is accepted.
        """
        user = api.user.get_current()
        seed = helpers.generate_secret(user)
        user.setMemberProperties(
            mapping={'two_factor_authentication_last_interval': 0})

        current = int(time.time()) // helpers.TOTP_INTERVAL_SECONDS
        code = get_hotp(seed, intervals_no=current, as_string=True)

        self.assertTrue(validate_token(code, user=user), 'first submission')
        self.assertFalse(
            validate_token(code, user=user), 'replayed submission')

        # Adjacency, asserted explicitly.
        user.setMemberProperties(
            mapping={'two_factor_authentication_last_interval': current})
        self.assertFalse(
            validate_token(code, user=user),
            'equal to the stored interval is refused')

        user.setMemberProperties(mapping={
            'two_factor_authentication_last_interval': current - 1})
        self.assertTrue(
            validate_token(code, user=user),
            'the next interval up is accepted')

    def test_validate_token_rejects_non_six_digit_input(self):
        """MFA-07: only exactly-six-ASCII-digit input is a candidate token.
        Every other shape is refused before onetimepass is ever called,
        including a unicode character that satisfies isdigit() but is not
        an ASCII digit -- refused rather than reaching int(), which would
        raise ValueError and turn an anonymously reachable form into a 500.
        """
        user = api.user.get_current()
        helpers.generate_secret(user)
        user.setMemberProperties(
            mapping={'two_factor_authentication_last_interval': 0})

        self.assertFalse(validate_token('12345', user=user), 'length 5')
        self.assertFalse(validate_token('1234567', user=user), 'length 7')
        self.assertFalse(validate_token('', user=user), 'empty')
        self.assertFalse(validate_token('12a456', user=user), 'non-digit')
        self.assertFalse(validate_token(' 12345', user=user), 'leading space')
        self.assertFalse(validate_token('+12345', user=user), 'leading sign')
        # A unicode superscript-two satisfies isdigit() in Python 2 but is
        # not an ASCII digit; must be refused without raising.
        self.assertFalse(
            validate_token(u'\xb2' * 6, user=user), 'non-ASCII digit')

    def test_replay_rejection_log_has_no_username(self):
        """MFA-06/T-05-04: the replay rejection is logged, and the log
        record carries no username, no user id, no token and no plaintext
        seed -- asserted on both the formatted message and the lazy ``%s``
        arguments, since a lazily-formatted argument would keep a name out
        of the format string but still put it in the log output.

        Non-vacuity control: the first (accepted) submission must log
        nothing at all, otherwise a test that captures nothing would pass
        for the wrong reason.
        """
        user = api.user.get_current()
        seed = helpers.generate_secret(user)
        user.setMemberProperties(
            mapping={'two_factor_authentication_last_interval': 0})

        current = int(time.time()) // helpers.TOTP_INTERVAL_SECONDS
        code = get_hotp(seed, intervals_no=current, as_string=True)

        records = []

        class _ListHandler(logging.Handler):
            def emit(self, record):
                records.append(record)

        # The module logger is process-global; a leaked handler or level
        # change would follow every later test in the run, so both are
        # restored in a finally block.
        target_logger = logging.getLogger('imio.googleauthenticator')
        handler = _ListHandler()
        previous_level = target_logger.level
        target_logger.setLevel(logging.INFO)
        target_logger.addHandler(handler)
        try:
            self.assertTrue(validate_token(code, user=user))
            self.assertEqual(
                0, len(records), 'accepted submission must log nothing')

            self.assertFalse(validate_token(code, user=user))
        finally:
            target_logger.removeHandler(handler)
            target_logger.setLevel(previous_level)

        self.assertEqual(1, len(records))
        record = records[0]
        self.assertGreaterEqual(record.levelno, logging.INFO)

        message = record.getMessage()
        for forbidden in (TEST_USER_NAME, TEST_USER_ID, code, seed):
            self.assertNotIn(forbidden, message)
            self.assertNotIn(forbidden, record.args or ())

    def test_recovery_code_storage_and_validation_edges(self):
        """RECOV-01/RECOV-02: the deliberate, one-commit-later companion to
        06-01's Task 2 end-to-end Browser test. That test already proved
        persistence across a real request boundary; this method is the
        explicit MFA-13 artifact the project convention requires --
        round-trip-with-declared-types for both new properties, the
        plaintext-absence guarantee, the one-salt/ten-hashes counts, every
        RECOV-01 refusal edge, the unicode/str equivalence, and validating
        from any position in the stored tuple.
        """
        user = api.user.get_current()

        # MFA-13 round trip: declared types survive setMemberProperties ->
        # getProperty for both new properties.
        salt = '0' * 32
        hashes = tuple('a' * 64 for _i in range(3))
        user.setMemberProperties(mapping={
            'two_factor_authentication_recovery_codes_salt': salt,
            'two_factor_authentication_recovery_codes_hashes': hashes,
        })
        stored_salt = user.getProperty(
            'two_factor_authentication_recovery_codes_salt')
        stored_hashes = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')
        self.assertEqual(salt, stored_salt, 'MFA-13')
        self.assertIsInstance(stored_salt, str)
        self.assertEqual(tuple(hashes), tuple(stored_hashes), 'MFA-13')

        # Empty-tuple round trip: reads back as an empty sequence, not ''.
        user.setMemberProperties(mapping={
            'two_factor_authentication_recovery_codes_hashes': (),
        })
        empty_hashes = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')
        self.assertEqual(0, len(empty_hashes), 'MFA-13')
        self.assertNotEqual('', empty_hashes, 'MFA-13')

        # Plaintext absence, counts and shape, after a real generation.
        codes = helpers.generate_recovery_codes(user)
        stored_salt = user.getProperty(
            'two_factor_authentication_recovery_codes_salt')
        stored_hashes = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')

        self.assertEqual(1, len(set([stored_salt])), 'RECOV-02: one salt')
        self.assertEqual(32, len(stored_salt), 'RECOV-02')
        self.assertEqual(10, len(codes), 'RECOV-02: ten codes')
        self.assertEqual(10, len(stored_hashes), 'RECOV-02: ten hashes')
        for code in codes:
            self.assertEqual(16, len(code), 'RECOV-02')
            self.assertNotIn('=', code, 'RECOV-02')
            self.assertNotIn(code, stored_salt, 'RECOV-02')
        for stored_hash in stored_hashes:
            self.assertEqual(64, len(stored_hash), 'RECOV-02')
            for code in codes:
                self.assertNotIn(code, stored_hash, 'RECOV-02')

        # Refusal scenarios -- shape gate, then the empty-salt/empty-hashes
        # gate, all returning False rather than raising.
        self.assertFalse(
            helpers.validate_recovery_code('', user=user), 'RECOV-01')
        self.assertFalse(
            helpers.validate_recovery_code('A', user=user), 'RECOV-01')
        self.assertFalse(
            helpers.validate_recovery_code('A' * 17, user=user), 'RECOV-01')
        self.assertFalse(
            helpers.validate_recovery_code(codes[0][:-1] + '0', user=user),
            'RECOV-01')

        no_salt_user = api.user.create(
            email='no-salt-recovery-user@example.com',
            username='no-salt-recovery-user',
            password='Secret0123!')
        self.assertFalse(
            helpers.validate_recovery_code(codes[0], user=no_salt_user),
            'RECOV-01: no stored salt must refuse, not raise')

        empty_hashes_user = api.user.create(
            email='empty-hashes-recovery-user@example.com',
            username='empty-hashes-recovery-user',
            password='Secret0123!')
        empty_hashes_user.setMemberProperties(mapping={
            'two_factor_authentication_recovery_codes_salt': '0' * 32,
            'two_factor_authentication_recovery_codes_hashes': (),
        })
        self.assertFalse(
            helpers.validate_recovery_code(codes[0], user=empty_hashes_user),
            'RECOV-01: an empty stored hash tuple must refuse, not raise')

        # unicode vs. str equivalence; non-ASCII refusal.
        unicode_code = unicode(codes[0])
        self.assertTrue(
            helpers.validate_recovery_code(unicode_code, user=user),
            'a unicode submission of the real code must validate '
            'identically to the same value as str')
        self.assertFalse(
            helpers.validate_recovery_code(u'\xe9' * 16, user=user),
            'a non-ASCII unicode submission must refuse, not raise')

        remaining = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')
        self.assertEqual(
            9, len(remaining),
            'precondition: exactly one code consumed above')

        # Validates from any position in the stored tuple, including last.
        last_code = codes[-1]
        self.assertTrue(
            helpers.validate_recovery_code(last_code, user=user),
            'a code must validate regardless of its position in the '
            'stored tuple, including the last')
        remaining = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')
        self.assertEqual(8, len(remaining))

    def test_recovery_code_regeneration_invalidates_the_previous_set(self):
        """RECOV-06: regeneration overwrites the salt and the hash list in
        one write (generate_recovery_codes's own setMemberProperties call),
        so every code from a previous set is refused afterwards, even a
        value drawn again by coincidence, and a fresh set of ten replaces
        it regardless of how many hashes were stored before.
        """
        user = api.user.get_current()

        first_codes = helpers.generate_recovery_codes(user)
        first_salt = user.getProperty(
            'two_factor_authentication_recovery_codes_salt')
        self.assertEqual(10, len(first_codes), 'RECOV-06')

        second_codes = helpers.generate_recovery_codes(user)
        second_hashes = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')
        second_salt = user.getProperty(
            'two_factor_authentication_recovery_codes_salt')
        self.assertNotEqual(
            first_salt, second_salt,
            'RECOV-06: regeneration must mint a fresh salt, not reuse the '
            'previous one.')
        self.assertEqual(10, len(second_codes), 'RECOV-06')
        self.assertEqual(10, len(second_hashes), 'RECOV-06')

        for code in first_codes:
            self.assertFalse(
                helpers.validate_recovery_code(code, user=user),
                'RECOV-06: every code from the first set must be refused '
                'after regeneration.')
        for code in second_codes:
            self.assertTrue(
                helpers.validate_recovery_code(code, user=user),
                'RECOV-06: every code from the second set must validate '
                'once, on first use.')

        remaining = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')
        self.assertEqual(
            0, len(remaining),
            'RECOV-06: precondition -- all ten of the second set were just '
            'consumed above.')

        # Regenerating from zero, one, and ten stored hashes each yields
        # exactly ten stored hashes.
        helpers.generate_recovery_codes(user)
        self.assertEqual(
            10,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'RECOV-06: regenerating from zero stored hashes must yield ten.')

        user.setMemberProperties(mapping={
            'two_factor_authentication_recovery_codes_hashes':
                (user.getProperty(
                    'two_factor_authentication_recovery_codes_hashes')[0],),
        })
        self.assertEqual(
            1, len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'precondition: exactly one hash stored')
        helpers.generate_recovery_codes(user)
        self.assertEqual(
            10,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'RECOV-06: regenerating from one stored hash must yield ten.')

        helpers.generate_recovery_codes(user)
        self.assertEqual(
            10,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'RECOV-06: regenerating from ten stored hashes must yield ten.')


class TestBarCodeResetToken(unittest.TestCase):
    """BUG-03: validate_bar_code_reset_token is a pure comparison function
    with no Zope state, so -- unlike every other class in this
    concern-named file (R7) -- this class carries no layer. The two
    production call sites in reset_bar_code.py (handleSubmit and
    updateFields) are covered by this plan's acceptance-criteria greps
    rather than by an integration test: the bar-code reset flow has zero
    test coverage today, and building it is COEX-04's business in Phase 7,
    not this plan's.
    """

    def test_validate_bar_code_reset_token(self):
        # All four str/unicode combinations of a matching pair. Each of
        # these would raise TypeError under a naive hmac.compare_digest
        # swap, so each is a separate assertion, not a loop over one
        # representative.
        self.assertTrue(validate_bar_code_reset_token('abc123', 'abc123'))
        self.assertTrue(validate_bar_code_reset_token('abc123', u'abc123'))
        self.assertTrue(validate_bar_code_reset_token(u'abc123', 'abc123'))
        self.assertTrue(validate_bar_code_reset_token(u'abc123', u'abc123'))

        # A genuine mismatch, same type and same length -- a length-differing
        # pair would pass even a broken implementation.
        self.assertFalse(validate_bar_code_reset_token('abc123', 'xyz789'))

        # A mismatch where the two operands differ in length returns False
        # without raising -- compare_digest accepts unequal lengths and
        # leaks only the length, which is acceptable here and must not be
        # "improved" into a raise.
        self.assertFalse(validate_bar_code_reset_token('abc123', 'ab'))

        # The empty cases all return False. An absent or empty stored token
        # means no reset was ever requested, so it must never match --
        # including an empty submitted value. This is the behaviour change
        # from the previous ==/!= equality tests, which returned True for
        # two empty strings.
        self.assertFalse(validate_bar_code_reset_token('', 'abc123'))
        self.assertFalse(validate_bar_code_reset_token('abc123', ''))
        self.assertFalse(validate_bar_code_reset_token('', ''))
        self.assertFalse(validate_bar_code_reset_token(None, 'abc123'))

        # A non-ASCII unicode operand returns False rather than raising
        # UnicodeEncodeError -- the stored token is always ASCII hex-ish
        # ska output, so a non-ASCII submitted value can only be an
        # attacker probing.
        self.assertFalse(
            validate_bar_code_reset_token('abc123', u'\xe9\xe9\xe9\xe9\xe9\xe9'))
