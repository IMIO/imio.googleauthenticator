import unittest2 as unittest

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

from imio.googleauthenticator.helpers import extract_ip_address_from_request
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_browser_hash
from imio.googleauthenticator.helpers import get_ip_addresses_whitelist
from imio.googleauthenticator.helpers import get_ip_ranges
from imio.googleauthenticator.helpers import get_ska_secret_key
from ipaddress import IPv4Network
from ipaddress import IPv4Address


class TestIPWhitelisting(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def test_get_ip_ranges_always_returns_networks_and_accepts_single_ip(self):
        ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
        self.assertEqual(
            [IPv4Network('127.0.0.1'), IPv4Network('192.168.0.0/16')],
            ranges)

    def test_get_ip_ranges_can_be_used_for_containment_testing(self):
        ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
        self.assertTrue(any(IPv4Address('127.0.0.1') in r for r in ranges))
        self.assertTrue(any(IPv4Address('192.168.1.1') in r for r in ranges))
        self.assertFalse(any(IPv4Address('10.0.0.0') in r for r in ranges))

    def test_get_ip_ranges_skips_invalid_entries_instead_of_raising(self):
        """CR-03 regression: a trailing blank line in the admin whitelist
        setting (or any other malformed single entry) must not crash every
        login site-wide.
        """
        ranges = get_ip_ranges(['127.0.0.1', '', 'not-an-ip', '192.168.0.0/16'])
        self.assertEqual(
            [IPv4Network('127.0.0.1'), IPv4Network('192.168.0.0/16')],
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
