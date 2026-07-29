import unittest2 as unittest

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

from imio.googleauthenticator.helpers import extract_ip_address_from_request
from imio.googleauthenticator.helpers import get_ip_addresses_whitelist
from imio.googleauthenticator.helpers import get_ip_ranges
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
