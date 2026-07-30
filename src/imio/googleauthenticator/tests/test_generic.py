from Products.CMFCore.utils import getToolByName
import unittest2 as unittest
from plone.testing.z2 import Browser
from plone.app.testing import quickInstallProduct
from plone.app.testing import SITE_OWNER_NAME, SITE_OWNER_PASSWORD, TEST_USER_NAME, TEST_USER_PASSWORD
from plone import api
from zope.i18n import translate

from imio.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings
from imio.googleauthenticator.browser.forms.token import TokenForm
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

    def test_corrected_msgid_renders_in_english(self):
        """D-18's acceptance test and the resolution of RESEARCH Open Question
        1: does Plone resolve a translation through the ``en`` catalogue, or
        short-circuit to the msgid when the target language matches the
        source language? This assertion is deliberately indifferent to which
        path fires -- the corrected text is both the msgid (step 1's source
        fix) and the ``en`` catalogue's msgstr (step 3's duplication by
        design), so the assertion holds either way, and it fails only if the
        source fix was missed or reverted.
        """
        result = translate(TokenForm.description, target_language='en')
        self.assertIn(
            'entering the verification code generated by', result)

    def _repo_root(self):
        import os
        import imio.googleauthenticator
        return os.path.abspath(os.path.join(
            os.path.dirname(imio.googleauthenticator.__file__),
            os.pardir, os.pardir, os.pardir))

    def test_manifest_ships_the_profile_and_catalogues(self):
        """RENAME-06: guards what actually lands in the sdist.

        A GenericSetup profile or a locale catalogue missing from the sdist
        produces a package that installs and then misbehaves -- no registry
        records, or an untranslated UI -- with nothing failing at build time.
        Phase 1 verified the real sdist contents once by hand (01-UAT test 2);
        nothing has re-checked it since, and `bin/check-manifest` is not wired
        into `bin/code-analysis`.

        Asserts MANIFEST.in's directives rather than building an sdist: the
        regression this catches is an edit dropping an include, and a
        `setup.py sdist` subprocess would cost seconds per run to reach the
        same verdict. The two `global-exclude` lines matter as much as the
        includes -- shipping `.pyc` or compiled `.mo` files was the specific
        defect phase 1 cleaned up.
        """
        import os
        with open(os.path.join(self._repo_root(), 'MANIFEST.in')) as handle:
            manifest = handle.read()

        self.assertTrue(manifest.strip(), 'MANIFEST.in is empty')

        required = (
            'recursive-include src/imio/googleauthenticator/locales *',
            'recursive-include src/imio/googleauthenticator/profiles *',
            'recursive-include src/imio/googleauthenticator/skins *',
            'recursive-include src/imio/googleauthenticator/browser/static *',
            'recursive-include src/imio/googleauthenticator/www *',
            'global-exclude *.pyc',
            'global-exclude *.mo',
        )
        for directive in required:
            self.assertIn(
                directive, manifest,
                'RENAME-06: MANIFEST.in must keep {0!r}, or the sdist ships '
                'an incomplete or polluted package.'.format(directive))

    def test_long_description_does_not_fall_into_setup_pys_bare_except(self):
        """DOC-04's automatable half, which 01-VALIDATION.md left manual-only.

        `setup.py` builds `long_description` by reading README.rst and
        CHANGES.rst, each wrapped in a **bare `except:` that substitutes an
        empty string** (setup.py:8-15). So a rename, a move or an encoding
        error in either file does not fail the build -- it silently ships
        package metadata missing that half, and the only symptom is a short
        description on the index page.

        Runs the real `setup.py --long-description` rather than re-reading the
        two files, because the failure being guarded is precisely that setup.py
        stopped incorporating one of them. Asserts a marker from each file, so
        losing either half fails; a length-only check would pass on README
        alone.
        """
        import os
        import subprocess
        import sys

        root = self._repo_root()
        proc = subprocess.Popen(
            [sys.executable, 'setup.py', '--long-description'],
            cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()

        self.assertEqual(
            0, proc.returncode,
            'setup.py --long-description failed: {0}'.format(stderr))

        # From README.rst -- the fork attribution CLAUDE.md requires be kept.
        self.assertIn(
            'Forked from', stdout,
            'DOC-04: README.rst content is missing from long_description, so '
            'setup.py fell into its bare except (or stopped reading it).')
        # From CHANGES.rst -- the current unreleased heading.
        self.assertIn(
            '1.0.0 (unreleased)', stdout,
            'DOC-04: CHANGES.rst content is missing from long_description, so '
            'setup.py fell into its bare except (or stopped reading it).')

        self.assertGreater(
            len(stdout), 5000,
            'DOC-04: long_description is implausibly short at {0} chars'
            .format(len(stdout)))

    def test_readme_documents_the_deployment_key_and_its_failure_mode(self):
        """DOC-03: the deployment documentation is a shipped artefact, so it
        needs a regression guard like any other.

        Until now DOC-03 was the phase's only requirement with no automated
        verification -- it was grep-checked once during execution, which does
        not survive into CI. The risk is not that someone deletes README.rst;
        it is a routine rewrite quietly dropping the two paragraphs an
        operator needs, leaving a phase still marked Complete.

        Deliberately asserts on the load-bearing *facts*, not on prose, so
        rewording is free and removing information is not:

        - the out-of-repo Puppet dependency (T-03-14), which is the reason
          this feature is not deployable from this repository alone;
        - the ZEO-skew failure mode (T-03-10), which has no database-side
          evidence and is therefore undiagnosable from the docs' absence.
        """
        import os
        import imio.googleauthenticator
        readme = os.path.join(
            os.path.dirname(imio.googleauthenticator.__file__),
            os.pardir, os.pardir, os.pardir, 'README.rst')
        self.assertTrue(
            os.path.exists(readme),
            'README.rst not found at {0} -- if the repository layout moved, '
            'fix this path rather than deleting the test'.format(readme))

        with open(readme) as handle:
            text = handle.read()

        # The out-of-repo dependency (T-03-14).
        for fact in ('IMIO_GOOGLEAUTHENTICATOR_SEED_KEY',
                     'concat::fragment',
                     'industrialisation',
                     'not deployable'):
            self.assertIn(
                fact, text,
                'DOC-03: README.rst must still record {0!r} -- the Puppet '
                'dependency is outside this repository and nothing else '
                'tracks it.'.format(fact))

        # The ZEO-skew failure mode (T-03-10): intermittent, per-client, with
        # nothing in the database to inspect.
        for fact in ('ZEO client', 'InvalidToken'):
            self.assertIn(
                fact, text,
                'DOC-03: README.rst must still describe the stale-key ZEO '
                'failure mode ({0!r}) -- it produces no database-side '
                'evidence, so the docs are the only diagnosis.'.format(fact))

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
