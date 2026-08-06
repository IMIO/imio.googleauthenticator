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
from imio.googleauthenticator.browser import disable_two_factor_authentication_for_all_users
from imio.googleauthenticator.browser.disable_two_factor_authentication import DisableTwoFactorAuthentication
from imio.googleauthenticator.browser.disable_two_factor_authentication_for_all_users import \
    DisableTwoFactorAuthenticationForAllUsers
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.testing import z2
from Products.statusmessages.interfaces import IStatusMessage

import unittest2 as unittest


class _FakeApiWithNoUsers(object):
    """Stand-in for ``disable_two_factor_authentication_for_all_users``'s
    own ``from plone import api`` name, used only by
    ``test_disable_for_all_users_on_an_empty_user_list``. The view's only
    use of this name, once past the ``globally_enabled`` guard, is
    ``api.user.get_users()`` -- this always returns an empty list,
    simulating a site with no accounts at all.

    Injected through a real collaborator, following
    ``tests/test_user_setup.py:21-39``'s ``_RaisesOnFirstCall`` precedent
    and ``tests/test_setuphandlers.py``'s ``_FakeApiWithOneFailingUser``
    precedent, rather than a mock framework.
    """

    class _UserNamespace(object):
        def get_users(self):
            return []

    def __init__(self):
        self.user = self._UserNamespace()


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

    def test_disable_is_refused_while_globally_enabled_and_mutates_nothing(self):
        """D-08/MFA-16: with globally_enabled on, disable() refuses and
        leaves the flag, the seed and the reset token all unchanged --
        this is the actual security control (D-09), asserted by calling
        the view directly rather than through a rendered link.

        Message *types* are asserted, never rendered text (QUAL-04's
        established convention), except for the one substantive check
        D-12 leaves open: the rendered text must not name another
        account's login name.
        """
        other_username = 'other-account-for-message-check'
        api.user.create(
            email='{0}@example.com'.format(other_username),
            username=other_username, password='Secret0123!')

        user = self._enable_2fa_for_current_user()
        flag_before = user.getProperty('enable_two_factor_authentication')
        secret_before = user.getProperty('two_factor_authentication_secret')
        token_before = user.getProperty('bar_code_reset_token')
        self.assertTrue(
            flag_before and secret_before and token_before,
            'Non-vacuity control: all three must be set before the call, '
            'or the unchanged-after assertion below would pass on an '
            'account that never had a second factor.')

        settings = get_app_settings()
        saved_globally_enabled = settings.globally_enabled
        settings.globally_enabled = True
        try:
            IStatusMessage(self.request).show()  # drain prior messages
            view = DisableTwoFactorAuthentication(self.portal, self.request)
            view.disable()
        finally:
            settings.globally_enabled = saved_globally_enabled

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            flag_before,
            refetched_user.getProperty('enable_two_factor_authentication'),
            'D-08: the refusal must not touch the flag.')
        self.assertEqual(
            secret_before,
            refetched_user.getProperty('two_factor_authentication_secret'),
            'D-08: the refusal must not touch the stored seed.')
        self.assertEqual(
            token_before,
            refetched_user.getProperty('bar_code_reset_token'),
            'D-08: the refusal must not touch the reset token.')

        messages = IStatusMessage(self.request).show()
        types = [m.type for m in messages]
        self.assertIn('error', types)
        self.assertNotIn('info', types)
        for message in messages:
            self.assertNotIn(
                other_username, unicode(message.message),
                'D-12: the refusal must not state or imply anything '
                'about any other account.')

    def test_disable_still_works_while_globally_disabled(self):
        """D-08's conditionality: the refusal is conditional, not a
        deletion of the feature. This is the non-vacuity partner of the
        method above -- without it, a guard that refused unconditionally
        would pass the refusal test above and silently delete the
        feature this view exists to provide.
        """
        self._enable_2fa_for_current_user()

        settings = get_app_settings()
        saved_globally_enabled = settings.globally_enabled
        settings.globally_enabled = False
        try:
            IStatusMessage(self.request).show()  # drain prior messages
            view = DisableTwoFactorAuthentication(self.portal, self.request)
            view.disable()
        finally:
            settings.globally_enabled = saved_globally_enabled

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertFalse(
            refetched_user.getProperty('enable_two_factor_authentication'))
        self.assertEqual(
            '',
            refetched_user.getProperty('two_factor_authentication_secret'))
        self.assertEqual(
            '', refetched_user.getProperty('bar_code_reset_token'))

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('info', types)
        self.assertNotIn('error', types)

        location = self.request.response.getHeader('location')
        self.assertTrue(
            location and location.endswith('/@@personal-information'),
            'the redirect must land on @@personal-information, got '
            '{0!r}'.format(location))

    def test_disable_is_refused_for_an_unenrolled_user_too(self):
        """MFA-16 adjacency probe: the refusal must not depend on the
        caller's own enrollment state -- an unenrolled user calling this
        URL while globally_enabled is on is refused, not silently treated
        as a no-op. A guard placed after a
        has_enabled_two_factor_authentication read would answer
        differently for the two cases for no reason; this test would
        catch that.
        """
        user = api.user.get_current()
        user.setMemberProperties(mapping={
            'enable_two_factor_authentication': False,
            'two_factor_authentication_secret': '',
            'bar_code_reset_token': '',
            })

        settings = get_app_settings()
        saved_globally_enabled = settings.globally_enabled
        settings.globally_enabled = True
        try:
            IStatusMessage(self.request).show()  # drain prior messages
            view = DisableTwoFactorAuthentication(self.portal, self.request)
            view.disable()
        finally:
            settings.globally_enabled = saved_globally_enabled

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('error', types)

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertFalse(
            refetched_user.getProperty('enable_two_factor_authentication'),
            'the flag must still be False -- it was never True to begin '
            'with, so this is not asserting the absence of a change '
            'that could not have happened; combined with the "error" '
            'assertion above it proves the refusal branch, not a '
            'no-op, is what ran.')


class TestDisableTwoFactorAuthenticationForAllUsers(unittest.TestCase, BaseTest):
    """D-18/MFA-16: the site-wide un-enroll view
    (`browser/disable_two_factor_authentication_for_all_users.py`) gets
    the same `globally_enabled` refusal as the single-user view above.
    This is an operator-approved widening of MFA-16 beyond its literal
    wording (which speaks only of a user's own second factor) -- the
    operator was offered the alternatives of leaving it as a Future
    Requirement, or deleting the view outright, and chose to gate it on
    2026-08-06 (see 10-CONTEXT.md D-18). Recorded here so a later reader
    auditing this phase against the requirement text does not read this
    class as unplanned work.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()

    def test_disable_for_all_users_is_refused_while_globally_enabled(self):
        """D-18/MFA-16: with globally_enabled on, calling index() changes
        no account's flag and reports an error.
        """
        usernames = (
            'all-users-disable-refused-1',
            'all-users-disable-refused-2',
            )
        for username in usernames:
            api.user.create(
                email='{0}@example.com'.format(username),
                username=username, password='Secret0123!')
            user = api.user.get(username=username)
            user.setMemberProperties(
                mapping={'enable_two_factor_authentication': True})

        settings = get_app_settings()
        saved_globally_enabled = settings.globally_enabled
        settings.globally_enabled = True
        try:
            IStatusMessage(self.request).show()  # drain prior messages
            view = DisableTwoFactorAuthenticationForAllUsers(
                self.portal, self.request)
            view.index()
        finally:
            settings.globally_enabled = saved_globally_enabled

        for username in usernames:
            refetched_user = api.user.get(username=username)
            self.assertTrue(
                refetched_user.getProperty('enable_two_factor_authentication'),
                'D-18: the refusal must not touch any account\'s flag '
                '-- {0!r} must still be enrolled.'.format(username))

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('error', types)
        self.assertNotIn('info', types)

    def test_disable_for_all_users_on_an_empty_user_list(self):
        """MFA-16 empty probe: a zero-user site is refused while the
        setting is on, and completes without raising while it is off --
        the same class of defect as T-03-21's zero-user bulk 'Changes
        saved.', where an empty set silently produces a false success
        claim.
        """
        settings = get_app_settings()
        saved_globally_enabled = settings.globally_enabled
        real_api = disable_two_factor_authentication_for_all_users.api
        disable_two_factor_authentication_for_all_users.api = (
            _FakeApiWithNoUsers())
        try:
            settings.globally_enabled = True
            IStatusMessage(self.request).show()  # drain prior messages
            view = DisableTwoFactorAuthenticationForAllUsers(
                self.portal, self.request)
            view.index()
            types = [m.type for m in IStatusMessage(self.request).show()]
            self.assertIn(
                'error', types,
                'a zero-user site must still be refused while the '
                'setting is on.')

            settings.globally_enabled = False
            IStatusMessage(self.request).show()  # drain prior messages
            try:
                view.index()
            except Exception as e:
                self.fail(
                    'a zero-user site must not raise once the setting '
                    'is off, got {0!r}'.format(e))
            types = [m.type for m in IStatusMessage(self.request).show()]
            self.assertIn(
                'info', types,
                'a zero-user site with the setting off must still '
                'report success (over zero accounts) rather than '
                'silently doing nothing.')
        finally:
            disable_two_factor_authentication_for_all_users.api = real_api
            settings.globally_enabled = saved_globally_enabled
