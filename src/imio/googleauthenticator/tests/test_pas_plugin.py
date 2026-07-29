from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
import unittest2 as unittest
from plone.testing.z2 import Browser
from plone import api
from plone.app.testing import quickInstallProduct
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from imio.googleauthenticator import pas_plugin
from imio.googleauthenticator.setuphandlers import PAS_ID

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


def _boom(*args, **kwargs):
    raise ValueError('deliberate: injected via a real collaborator')


class TestPas(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self.pas = getToolByName(self.portal, 'acl_users')
        self.portal_url = api.portal.get().absolute_url()
        self._install()

    def test_plugin_is_installed(self):
        """ Validate that our products GS profile has been run and the product
            installed
        """
        installed = self.pas.objectIds()
        self.assertIn(PAS_ID, installed)

    def test_plugin_is_registered_for_authentication(self):
        """objectIds() (test_plugin_is_installed, above) cannot catch this: a
        Broken object still appears there. PluginRegistry.listPlugins filters
        on _satisfies() and logs the miss at debug level, so a Broken plugin --
        or a marker-file mismatch that never added it -- is invisible without
        this assertion. This is the acceptance test for the marker-file
        invariant (RENAME-04) as well as for RENAME-12."""
        registered = [pid for pid, _p
                      in self.pas.plugins.listPlugins(IAuthenticationPlugin)]
        self.assertIn(PAS_ID, registered)

    def test_plugin_exception_is_not_swallowed(self):
        """Inject a ValueError through a real collaborator -- is_whitelisted_client,
        the first statement of authenticateCredentials -- rather than monkeypatching
        authenticateCredentials itself, so the code under test is PAS's own
        except _SWALLOWABLE_PLUGIN_EXCEPTIONS: reraise(auth); continue block in
        _extractUserIds. Fail closed: the exception must escape (-> HTTP 500), NOT
        be swallowed into a fallthrough that authenticates via source_users.
        """
        original = pas_plugin.is_whitelisted_client
        pas_plugin.is_whitelisted_client = _boom
        try:
            request = self.layer['request']
            request.form['__ac_name'] = TEST_USER_NAME
            request.form['__ac_password'] = TEST_USER_PASSWORD
            self.assertRaises(
                ValueError,
                self.pas._extractUserIds, request, self.pas.plugins)
        finally:
            pas_plugin.is_whitelisted_client = original

    def test_unmatched_username_does_not_crash(self):
        """CR-01 regression: api.user.get() returns None for a login that
        does not match any account (mistyped username, a bot probing
        usernames). Before the fix, the very next line called
        user.getUserName() unconditionally, raising AttributeError -- one of
        PAS's _SWALLOWABLE_PLUGIN_EXCEPTIONS -- which _dont_swallow_my_exceptions
        (RENAME-11) then lets propagate as an uncaught HTTP 500 instead of a
        normal 'Login failed'.
        """
        plugin = self.pas[PAS_ID]
        result = plugin.authenticateCredentials(
            {'login': 'no-such-user', 'password': 'whatever'})
        self.assertIsNone(result)

    def test_plugin_exception_is_swallowed_without_the_flag(self):
        """Counterfactual documenting exactly what the flag above buys: with
        _dont_swallow_my_exceptions removed, the same injected ValueError is
        swallowed and _extractUserIds falls through to source_users instead of
        raising.
        """
        original = pas_plugin.is_whitelisted_client
        pas_plugin.is_whitelisted_client = _boom
        had_flag = hasattr(
            pas_plugin.GoogleAuthenticatorPlugin, '_dont_swallow_my_exceptions')
        flag_value = getattr(
            pas_plugin.GoogleAuthenticatorPlugin,
            '_dont_swallow_my_exceptions', None)
        if had_flag:
            del pas_plugin.GoogleAuthenticatorPlugin._dont_swallow_my_exceptions
        try:
            request = self.layer['request']
            request.form['__ac_name'] = TEST_USER_NAME
            request.form['__ac_password'] = TEST_USER_PASSWORD
            user_ids = self.pas._extractUserIds(request, self.pas.plugins)
            self.assertTrue(user_ids)
        finally:
            pas_plugin.is_whitelisted_client = original
            if had_flag:
                pas_plugin.GoogleAuthenticatorPlugin._dont_swallow_my_exceptions = \
                    flag_value
