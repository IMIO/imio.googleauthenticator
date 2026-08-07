from imio.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings
from imio.googleauthenticator.browser.forms.token import TokenForm
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.interfaces import IGoogleAuthenticatorLayer
from imio.googleauthenticator.setuphandlers import PAS_ID
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.browserlayer.utils import registered_layers
from plone.registry.interfaces import IRegistry
from plone.supermodel.interfaces import FIELDSETS_KEY
from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from zope.component import getUtility
from zope.i18n import translate
from zope.schema import Bool
from zope.schema import Int

import imio.googleauthenticator
import os
import unittest2 as unittest


def _read_readme():
    """Read README.rst's full text, resolved relative to the installed package --
    the same path construction
    test_readme_documents_the_deployment_key_and_its_failure_mode already uses (that
    test is left untouched; this helper only backs the two new DOC-01/DOC-02 tests
    below, to avoid repeating the path construction a third time).
    """
    readme = os.path.join(
        os.path.dirname(imio.googleauthenticator.__file__),
        os.pardir, os.pardir, os.pardir, 'README.rst')
    assert os.path.exists(readme), (
        'README.rst not found at {0} -- if the repository layout moved, '
        'fix this path rather than deleting the test'.format(readme))
    with open(readme) as handle:
        return handle.read()


class TestGeneric(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = api.portal.get().absolute_url()
        self.pas = getToolByName(self.portal, 'acl_users')

    def test_product_is_installed(self):
        """QUAL-07: applyProfile() never touches the quickinstaller tool
        (verified against the installed plone.app.testing source), so
        installedness is asserted through what the package's own install
        path actually guarantees instead: PAS plugin registration, the
        IGoogleAuthenticatorSettings registry records, and the browser
        layer. A regression here means the layer's setUpPloneSite silently
        ran its PloneSandboxLayer no-op base instead of applying our
        profile.
        """
        ids = [x[0] for x in self.pas.plugins.listPlugins(IAuthenticationPlugin)]
        self.assertIn(PAS_ID, ids)

        registry = getUtility(IRegistry)
        registry.forInterface(IGoogleAuthenticatorSettings)  # raises KeyError if any record missing

        self.assertIn(IGoogleAuthenticatorLayer, registered_layers())

    def test_globally_enabled_schema_default_is_true(self):
        """WR-03: testing.py's layer forces globally_enabled = False right
        after applyProfile() (deliberate test-isolation, documented there),
        so nearly every test in this suite runs against that override, not
        the schema's own default. This pins the schema-level default
        directly against the IGoogleAuthenticatorSettings field, so a
        future edit to that default cannot drift silently -- asserted
        against the field's declared default, not a live registry read
        (which would only ever observe the layer's override).
        """
        field = IGoogleAuthenticatorSettings['globally_enabled']
        self.assertIsInstance(field, Bool)
        self.assertTrue(
            field.default,
            'WR-03: IGoogleAuthenticatorSettings.globally_enabled must '
            'default to True -- this is the production default, distinct '
            'from the test layer\'s own runtime override.')

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

    def test_control_panel_has_lockout_fields(self):
        """MFA-10: max_failed_attempts and lockout_duration exist on
        IGoogleAuthenticatorSettings with defaults 5 and 900, are both
        zope.schema.Int with min=1, and are listed in the interface's
        fieldset so the existing auto-extensible form renders them --
        following the same IGoogleAuthenticatorSettings[...] subscript
        idiom this file already uses for ska_secret_key above. The values
        are also asserted readable through get_app_settings() after
        install, proving plone.app.registry seeded the two new records
        from the blanket <records interface=.../> line with no
        registry.xml edit (decision P5-03).
        """
        max_field = IGoogleAuthenticatorSettings['max_failed_attempts']
        duration_field = IGoogleAuthenticatorSettings['lockout_duration']

        self.assertIsInstance(max_field, Int)
        self.assertEqual(5, max_field.default)
        self.assertEqual(1, max_field.min)

        self.assertIsInstance(duration_field, Int)
        self.assertEqual(900, duration_field.default)
        self.assertEqual(1, duration_field.min)

        fieldsets = IGoogleAuthenticatorSettings.queryTaggedValue(
            FIELDSETS_KEY)
        all_fields = [
            name for fieldset in fieldsets for name in fieldset.fields]
        self.assertIn('max_failed_attempts', all_fields)
        self.assertIn('lockout_duration', all_fields)

        settings = get_app_settings()
        self.assertEqual(5, settings.max_failed_attempts)
        self.assertEqual(900, settings.lockout_duration)

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

    def test_readme_documents_zope_root_limitation(self):
        """DOC-01: what this catches is not deletion of the README but a rewrite
        that drops the operator-facing scope statement while DOC-01 stays marked
        Complete -- phase 3's DOC-03 test above is the precedent and the reasoning
        is identical.

        Asserts on load-bearing *identifiers*, never on prose, so rewording stays
        free and removing the information does not:

        - ``Control_Panel`` / ``acl_users`` / ``inituser`` -- the boundary and
          where a Zope-root account actually lives;
        - a mention of the "emergency user" carve-out (matched
          case-insensitively, since a sentence-initial capital should not break
          the assertion) -- PAS's own bypass that sits above this plugin's
          machinery entirely and that no plugin, ordering or extractor change
          can close.
        """
        text = _read_readme()

        for fact in ('Control_Panel', 'acl_users', 'inituser'):
            self.assertIn(
                fact, text,
                'DOC-01: README.rst must still record {0!r} -- an operator '
                'needs to know a Zope-root account is architecturally out of '
                "this plugin's reach.".format(fact))

        self.assertIn(
            'emergency user', text.lower(),
            'DOC-01: README.rst must still name PAS\'s own emergency-user '
            'carve-out -- it sits above the plugin machinery entirely and no '
            'plugin ordering can close it.')

    def test_readme_documents_basic_auth_consequence(self):
        """DOC-02: written against the branch MFA-03's checkpoint actually took
        (2026-07-31, see 04-02-SUMMARY.md): ``credentials_basic_auth`` is kept
        ACTIVE, not deactivated. A later reversal of that decision without a
        README update should turn this test red rather than leave a stale
        README quietly wrong.

        Asserts on load-bearing *identifiers*, never on prose:

        - ``credentials_basic_auth`` -- the settled decision itself;
        - ``WebDAV`` / ``XML-RPC`` -- the protocols affected alongside Basic
          Auth, none of which has anywhere to enter a six-digit code;
        - ``ip_addresses_whitelist`` / ``enable_two_factor_authentication`` --
          the two already-shipped mechanisms behind the supported
          service-account alternative.
        """
        text = _read_readme()

        for fact in ('credentials_basic_auth', 'WebDAV', 'XML-RPC',
                     'ip_addresses_whitelist',
                     'enable_two_factor_authentication'):
            self.assertIn(
                fact, text,
                'DOC-02: README.rst must still record {0!r}.'.format(fact))

        # Branch-specific: credentials_basic_auth was KEPT active (not
        # deactivated), so the README must name what protects that path
        # under the "keep" branch -- the plugin's index-0 ordering -- rather
        # than a "no longer authenticates" statement, which only applies to
        # the unselected "deactivate" branch.
        self.assertIn(
            'index 0', text,
            'DOC-02: the "keep credentials_basic_auth active" branch was '
            'taken, so README.rst must name the plugin\'s index-0 ordering '
            'as what protects that path. If this decision is ever reversed '
            'to "deactivate", this assertion (and the README paragraph it '
            'checks) must be updated together.')

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
        """This single assertion is what makes the three files that must agree --
        the resourceDirectory name in browser/configure.zcml, the two
        jsregistry.xml ids, and the cssregistry.xml id -- verifiable, because
        a mismatch is otherwise a 404 on the asset and nothing else."""
        portal_javascripts = getToolByName(self.portal, 'portal_javascripts')
        portal_css = getToolByName(self.portal, 'portal_css')
        js_ids = portal_javascripts.getResourceIds()
        css_ids = portal_css.getResourceIds()
        self.assertIn('++resource++imio.googleauthenticator/main.js', js_ids)
        self.assertIn('++resource++imio.googleauthenticator/main.css', css_ids)

    def test_regenerate_recovery_codes_action_is_registered(self):
        """RECOV-06: the regeneration path is a rendered portal action, not
        a URL a user has to type. The available_expr is asserted
        explicitly, not just the action's existence -- the wrong
        availability expression would render a "Regenerate recovery codes"
        link to a user who has never enrolled, a misleading offer of a
        security control's state, the same class of defect T-03-23 and
        T-03-21 already documented in this package.

        D-15 (phase 10 plan 04): available_expr used to reuse
        show-disable-two-factor-authentication-link, deliberately. That
        reuse was undone because D-11 changed the disable condition to
        require the global setting to be off, which would have hidden this
        action from exactly the users under global enforcement -- so this
        now asserts the action's own show-regenerate-recovery-codes-link
        condition instead.
        """
        portal_actions = getToolByName(self.portal, 'portal_actions')
        user_category = portal_actions.user
        self.assertIn(
            'regenerate_recovery_codes', user_category.objectIds(),
            'RECOV-06: the regenerate_recovery_codes action must be '
            'registered in the "user" action category.')
        action = user_category['regenerate_recovery_codes']
        self.assertIn(
            '@@setup-two-factor-authentication',
            action.url_expr,
            'RECOV-06: regeneration must reuse the setup form -- there is '
            'no dedicated regeneration view.')
        self.assertIn(
            'show-regenerate-recovery-codes-link',
            action.available_expr,
            'D-15: regeneration must use its own availability view, not '
            'the disable link\'s condition.')

    def test_no_restrictedTraverse_left_in_browser_code(self):
        """COEX-04: no view under ``browser/`` may reach a template through
        a skin-name ``restrictedTraverse`` lookup any more -- both auxiliary
        fragments that used to be looked up that way
        (``control_panel_extra``, ``request_bar_code_reset_email``) are now
        reached through a ``ViewPageTemplateFile`` class attribute, and the
        skin layer they were looked up against no longer exists.

        Walks ``browser/`` with ``os.walk`` rather than a hand-written file
        list, so a future view added with a skin-name traversal is caught
        too. Non-vacuity control: the collected file list must be non-empty
        and contain at least ``controlpanel.py`` and
        ``forms/request_bar_code_reset.py``, so a wrong root directory fails
        here rather than passing with an empty loop.
        """
        browser_dir = os.path.join(
            os.path.dirname(imio.googleauthenticator.__file__), 'browser')

        py_files = []
        for dirpath, _dirnames, filenames in os.walk(browser_dir):
            for filename in filenames:
                if filename.endswith('.py'):
                    py_files.append(os.path.join(dirpath, filename))

        self.assertTrue(
            py_files,
            'Non-vacuity control: no .py files found under {0} -- the '
            'walk root is wrong and every assertion below would pass '
            'vacuously.'.format(browser_dir))
        relative_paths = [
            os.path.relpath(path, browser_dir) for path in py_files]
        self.assertIn(
            'controlpanel.py', relative_paths,
            'Non-vacuity control: controlpanel.py must be found by the '
            'walk.')
        self.assertIn(
            os.path.join('forms', 'request_bar_code_reset.py'),
            relative_paths,
            'Non-vacuity control: forms/request_bar_code_reset.py must be '
            'found by the walk.')

        for path in py_files:
            with open(path) as handle:
                source = handle.read()
            self.assertNotIn(
                'restrictedTraverse', source,
                'COEX-04: {0} must not perform a skin-name traversal -- '
                'reach the template through a ViewPageTemplateFile class '
                'attribute instead.'.format(path))
