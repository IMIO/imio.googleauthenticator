from Products.CMFCore.utils import getToolByName
import unittest2 as unittest
from plone.testing.z2 import Browser
from plone.app.testing import quickInstallProduct
from plone.app.testing import SITE_OWNER_NAME, SITE_OWNER_PASSWORD, TEST_USER_NAME, TEST_USER_PASSWORD
from plone import api
from zope.i18n import translate

from imio.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class TestGeneric(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self.portal_url = api.portal.get().absolute_url()
        self._install()

    def test_product_is_installed(self):
        """ Validate that our products GS profile has been run and the product
            installed
        """
        pid = 'imio.googleauthenticator'
        installed = [p['id'] for p in self.qi_tool.listInstalledProducts()]
        self.assertTrue(pid in installed,
            u'package appears not to have been installed')

    def test_control_panel_view(self):
        browser = self._get_browser()
        self._login_browser(browser, SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
        browser.open('{0}/@@google-authenticator-settings'.format(self.portal_url))

        self.assertEqual(browser.headers.get('status'), '200 Ok', 'HTTP response was not 200 Ok')

    def test_user_setup_view(self):
        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        browser.open('{0}/@@setup-two-factor-authentication'.format(self.portal_url))
        self.assertEqual(browser.headers.get('status'), '200 Ok', 'HTTP response was not 200 Ok')

    def test_token_view(self):
        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        browser.open('{0}/@@google-authenticator-token'.format(self.portal_url))
        self.assertEqual(browser.headers.get('status'), '200 Ok', 'HTTP response was not 200 Ok')

    # def test_disable_view(self):
    #     browser = Browser(self.app)
    #     browser.open('{0}/@@disable-two-factor-authentication'.format(self.portal_url))
    #
    #     self.assertEqual(browser.headers.get('status'), '200 Ok', 'HTTP response was not 200 Ok')
    #

    def test_control_panel_is_translated_nl(self):
        """Domain-level proof that the i18n domain rename holds: translating
        the control-panel schema label with target language ``nl`` must
        resolve through the catalogue now registered under the renamed
        ``locales/`` filenames, not silently fall back to the English msgid.
        Uses ``translate()`` directly rather than a browser-level render of
        the settings view with a language query parameter, because that
        alternative additionally depends on Dutch being among
        ``portal_languages``'s supported languages in the test site, which
        this phase does not configure.

        Deviation from the plan text: the plan names the expected value
        ``Google Authenticator instellingen`` (msgid ``Google Authenticator
        settings``), but that msgid has no corresponding ``_(...)`` call
        anywhere in current source -- it is a stale catalogue entry left
        over from an earlier upstream revision (confirmed by grep). Task 2's
        ``i18ndude rebuild-pot`` step extracts msgids from live source only,
        so keeping that msgid would make this assertion pass after task 1
        and then silently break after task 2's regeneration drops it. The
        ``ska_secret_key`` field's title (``Secret Key`` -> ``Geheime
        Sleutel``) is used instead: it is live in source, its Dutch differs
        from its English so the assertion discriminates, and it is not one
        of the three msgids task 2 rewrites.
        """
        title = IGoogleAuthenticatorSettings['ska_secret_key'].title
        self.assertEqual(translate(title, target_language='nl'), u'Geheime Sleutel')

    def test_imio_is_a_pkg_resources_namespace(self):
        """Catches: empty src/imio/__init__.py, a pkgutil-style declaration, and a
        missing namespace_packages=['imio'] in setup.py. No new dependency needed --
        this proves this package's own namespace declaration, not agreement with a
        second imio.* egg in the same process (that residual gap is accepted, see
        RESEARCH Adjudication A-1)."""
        import pkg_resources
        import imio.googleauthenticator  # noqa
        self.assertIn('imio', pkg_resources._namespace_packages)
        dist = pkg_resources.get_distribution('imio.googleauthenticator')
        self.assertEqual(
            dist.get_metadata('namespace_packages.txt').split(), ['imio'])

    def test_resources_are_registered(self):
        """This single assertion is what makes the four files that must agree --
        the resourceDirectory name in browser/configure.zcml, the two
        jsregistry.xml ids, the cssregistry.xml id, and the skins.xml
        directory-view prefix -- verifiable, because a mismatch is otherwise a
        404 on the asset and nothing else."""
        portal_javascripts = getToolByName(self.portal, 'portal_javascripts')
        portal_css = getToolByName(self.portal, 'portal_css')
        js_ids = portal_javascripts.getResourceIds()
        css_ids = portal_css.getResourceIds()
        self.assertIn('++resource++imio.googleauthenticator/main.js', js_ids)
        self.assertIn('++resource++imio.googleauthenticator/main.css', css_ids)
