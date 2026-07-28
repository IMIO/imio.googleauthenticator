from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
import unittest2 as unittest
from plone.testing.z2 import Browser
from plone import api
from plone.app.testing import quickInstallProduct
from imio.googleauthenticator.setuphandlers import PAS_ID

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


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
