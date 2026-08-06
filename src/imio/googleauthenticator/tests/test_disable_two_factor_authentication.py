"""
Tests for ``browser/disable_two_factor_authentication.py`` (T-08-12, QUAL-04).

Before this module, ``DisableTwoFactorAuthentication.disable()`` had zero
tests despite being the only guard standing between an unauthenticated
request and turning off a user's second factor (40% coverage, plan
08-01's baseline). Follows the WR-03 convention this suite uses throughout
(one test method per behaviour, grouped by concern, docstring naming the
requirement and the regression it guards) rather than the
plone-write-tests skill's one-assertion-per-tested-method rule, per this
plan's own explicit instruction.
"""
from imio.googleauthenticator.browser.disable_two_factor_authentication import DisableTwoFactorAuthentication
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.testing import z2
from Products.statusmessages.interfaces import IStatusMessage

import unittest2 as unittest


class TestDisableTwoFactorAuthentication(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()

    def _enable_2fa_for_current_user(self):
        user = api.user.get_current()
        user.setMemberProperties(mapping={
            'enable_two_factor_authentication': True,
            'two_factor_authentication_secret': 'placeholder-secret',
            'bar_code_reset_token': 'placeholder-token',
        })
        return user

    def test_anonymous_request_is_refused_and_mutates_nothing(self):
        """T-08-12: the anonymous guard is the only thing standing between
        an unauthenticated request and a 2FA-disable endpoint, so this
        asserts the guard's *effect* (the member property is unchanged),
        not only its 401 status -- a status code alone would still pass if
        the guard returned 401 after mutating the property.
        """
        user = self._enable_2fa_for_current_user()
        flag_before = user.getProperty('enable_two_factor_authentication')
        self.assertTrue(
            flag_before, 'precondition: the flag must start set, or the '
            'unchanged-after assertion below is vacuous')

        z2.logout()
        try:
            view = DisableTwoFactorAuthentication(self.portal, self.request)
            result = view.disable()
        finally:
            z2.logout()
            login(self.portal, TEST_USER_NAME)

        self.assertIsNone(
            result, 'the anonymous branch must return without reaching '
            'the member-property write below it')
        self.assertEqual(401, self.request.response.getStatus())

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            flag_before,
            refetched_user.getProperty('enable_two_factor_authentication'),
            'T-08-12: the anonymous guard must not mutate the member '
            'property it refuses to touch.')

    def test_authenticated_call_clears_all_three_properties(self):
        """QUAL-04: the memberdata write is a single mapping -- asserting
        all three properties matters because a partial write would leave a
        disabled account still holding its seed.
        """
        self._enable_2fa_for_current_user()

        view = DisableTwoFactorAuthentication(self.portal, self.request)
        view.disable()

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertFalse(
            refetched_user.getProperty('enable_two_factor_authentication'))
        self.assertEqual(
            '',
            refetched_user.getProperty('two_factor_authentication_secret'))
        self.assertEqual(
            '', refetched_user.getProperty('bar_code_reset_token'))

    def test_successful_call_reports_info_and_redirects_to_personal_information(self):
        """QUAL-04: message *types* are asserted, never rendered text --
        the strings are zope.i18nmessageid Messages and comparing rendered
        text couples the assertion to translation state, the convention
        test_helpers.py's bulk-enable test already documents.
        """
        self._enable_2fa_for_current_user()

        IStatusMessage(self.request).show()  # drain prior messages
        view = DisableTwoFactorAuthentication(self.portal, self.request)
        view.disable()

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('info', types)

        location = self.request.response.getHeader('location')
        self.assertTrue(
            location and location.endswith('/@@personal-information'),
            'the redirect must land on @@personal-information, got '
            '{0!r}'.format(location))
