from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
import os
import unittest2 as unittest
from cryptography.fernet import Fernet
from plone.testing.z2 import Browser
from plone import api
from plone.app.testing import login
from plone.app.testing import quickInstallProduct
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from zope.globalrequest import setRequest
from imio.googleauthenticator import helpers
from imio.googleauthenticator import pas_plugin
from imio.googleauthenticator.helpers import get_or_create_secret
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

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()

    def tearDown(self):
        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key

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

        authenticateCredentials()'s first statement (is_whitelisted_client())
        calls zope.globalrequest.getRequest() with no argument, so this test
        needs a request bound the same way a real HTTP request would --
        plain zope.globalrequest.setRequest(), not a Browser/publish
        roundtrip, keeps this a narrow unit test of the plugin method itself.
        """
        plugin = self.pas[PAS_ID]
        request = self.layer['request']
        setRequest(request)
        try:
            result = plugin.authenticateCredentials(
                {'login': 'no-such-user', 'password': 'whatever'})
        finally:
            setRequest(None)
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

    def test_login_is_refused_when_seed_key_is_broken(self):
        """SEC-03 validation half: a 2FA-enabled user's login must raise out
        of _extractUserIds rather than falling through to a password-only
        session when the seed key is unset or malformed.

        authenticateCredentials()'s first statement is the whitelist check,
        called with no argument, which reaches
        zope.globalrequest.getRequest(), so the request must be bound with
        setRequest() -- exactly what test_unmatched_username_does_not_crash's
        docstring documents -- or every assertion below dies on
        AttributeError inside that check before it ever reaches the crypto
        path, rather than the refusal it claims to assert. A non-vacuity control
        runs first with the good key from setUp still in place, so a pass on
        the two assertions below cannot be explained by an unrelated crash.
        _extractUserIds returning user ids here would be a session granted
        on password alone -- exactly what
        test_plugin_exception_is_swallowed_without_the_flag demonstrates
        happens when _dont_swallow_my_exceptions is absent.
        """
        login(self.portal, TEST_USER_NAME)
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        # overwrite=True: force a fresh secret encrypted under this test's
        # own setUp key, rather than trusting a property that may already be
        # set -- memberdata commits inside BaseTest._install()'s testbrowser
        # calls survive across test methods in this layer.
        get_or_create_secret(user, overwrite=True)

        request = self.layer['request']
        request.form['__ac_name'] = TEST_USER_NAME
        request.form['__ac_password'] = TEST_USER_PASSWORD
        setRequest(request)
        try:
            # Non-vacuity control: with the good key, this completes
            # without raising.
            self.pas._extractUserIds(request, self.pas.plugins)

            original = helpers.get_encryption_key
            helpers.get_encryption_key = lambda: None
            try:
                self.assertRaises(
                    ValueError,
                    self.pas._extractUserIds, request, self.pas.plugins)
            finally:
                helpers.get_encryption_key = original

            helpers.get_encryption_key = lambda: 'not-a-valid-fernet-key'
            try:
                self.assertRaises(
                    ValueError,
                    self.pas._extractUserIds, request, self.pas.plugins)
            finally:
                helpers.get_encryption_key = original
        finally:
            setRequest(None)
