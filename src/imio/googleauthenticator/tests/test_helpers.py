import base64
import os
import unittest2 as unittest

from cryptography.fernet import Fernet
from onetimepass import get_totp

from Products.statusmessages.interfaces import IStatusMessage

from plone import api
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME

from imio.googleauthenticator import helpers
from imio.googleauthenticator.browser.controlpanel import GoogleAuthenticatorSettingsEditForm
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

from imio.googleauthenticator.helpers import decrypt_seed
from imio.googleauthenticator.helpers import encrypt_seed
from imio.googleauthenticator.helpers import enable_two_factor_authentication_for_users
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
from imio.googleauthenticator.helpers import validate_bar_code_reset_token
from imio.googleauthenticator.helpers import validate_token
from ipaddress import IPv4Network
from ipaddress import IPv4Address


class TestIPWhitelisting(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

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

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self._install()
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

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self._install()
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
        self.assertTrue(
            validate_token(get_totp(seed), user=user), 'SEC-01 end-to-end')

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
        # (memberdata commits inside BaseTest._install()'s testbrowser calls
        # survive across test methods in this layer -- see TestSkaSecretKey
        # .setUp's docstring for the same hazard's re-login half).
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
