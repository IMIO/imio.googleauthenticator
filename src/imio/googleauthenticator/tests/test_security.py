import unittest2 as unittest
from plone.testing.z2 import Browser
from plone.app.testing import SITE_OWNER_NAME, SITE_OWNER_PASSWORD, TEST_USER_NAME, TEST_USER_PASSWORD
from plone import api

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class TestGeneric(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = api.portal.get().absolute_url()

    def test_(self):
        """
        """
        