import base64
import os
import unittest2 as unittest

from cryptography.fernet import Fernet
from onetimepass import get_totp

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME

from imio.googleauthenticator import helpers
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

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
