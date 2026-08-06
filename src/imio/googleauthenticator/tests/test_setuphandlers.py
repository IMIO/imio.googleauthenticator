from imio.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_ska_secret_key
from imio.googleauthenticator.interfaces import IGoogleAuthenticatorLayer
from imio.googleauthenticator.setuphandlers import PAS_ID
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import applyProfile
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.users.userdataschema import IUserDataSchemaProvider
from plone.browserlayer.utils import registered_layers
from plone.registry import Record
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from xml.dom import minidom
from zope.component import getUtility

import imio.googleauthenticator
import os.path
import unittest2 as unittest


JSREGISTRY_XML = os.path.join(
    os.path.dirname(imio.googleauthenticator.__file__),
    'profiles', 'default', 'jsregistry.xml')

CSSREGISTRY_XML = os.path.join(
    os.path.dirname(imio.googleauthenticator.__file__),
    'profiles', 'default', 'cssregistry.xml')

UNINSTALL_JSREGISTRY_XML = os.path.join(
    os.path.dirname(imio.googleauthenticator.__file__),
    'profiles', 'uninstall', 'jsregistry.xml')

UNINSTALL_CSSREGISTRY_XML = os.path.join(
    os.path.dirname(imio.googleauthenticator.__file__),
    'profiles', 'uninstall', 'cssregistry.xml')

# Any one of these on a <javascript> node pins its position explicitly, instead
# of leaving it to BaseRegistry.storeResource's plain append.
POSITION_ATTRIBUTES = (
    'insert-before', 'position-before',
    'insert-after', 'position-after',
    'insert-top', 'position-top',
    'insert-bottom', 'position-bottom',
    )


class TestSetupHandlers(unittest.TestCase, BaseTest):
    """Integration-layer assertions for setupVarious and the import-step
    ordering it depends on.

    WR-03: one test method per requirement rather than one method bundling
    all assertion groups, so a failure in an earlier group (e.g. import-step
    ordering silently reverted) does not hide whether the later groups
    (seeding, re-apply guard) still pass or fail.

    Post-review revision (CR-02): install-time seeding of ska_secret_key was
    restored after code review found the lazy-mint-inside-a-getter design
    (this phase's original D-04/D-05) writes registry state from
    authenticateCredentials() -> sign_user_data(), a request path that ends
    in transaction.abort() on Unauthorized and silently discards the mint --
    see 02-01-SUMMARY.md "Post-review revision" for the full account. The
    tests below assert the current (post-revision) behaviour: install seeds
    a non-empty key, and get_ska_secret_key() is a pure read that must not
    mutate the registry.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self.pas = getToolByName(self.portal, 'acl_users')

    def test_import_step_declares_registry_dependency(self):
        """REG-02: the <depends name="plone.app.registry"/> declaration is
        recorded on our import step.

        This -- not the sorted order below -- is the control. Asserting only
        the post-sort position of getSortedImportSteps() is a tautology in
        the current fixture: with the <depends> line deleted,
        'imio.googleauthenticator' still lands after 'plone.app.registry'
        (index 51 vs 36 of 52) purely by CPython 2.7 string-hash order, so
        that assertion passes either way and would not catch the deletion.
        Verified empirically during phase-2 verification. Asserting the
        recorded dependency instead fails the moment the declaration goes.

        Requirement id corrected from REG-03 to REG-02 during the phase-2
        Nyquist audit: REG-02 is the declaration, REG-03 is the sorted-order
        outcome below. Both docstrings previously read REG-03, leaving REG-02
        with no test claiming it by id. Note that REG-03's own wording calls
        the ordering assertion "the control" -- the paragraph above is the
        evidence that it is not, so REG-02's declaration check is what
        actually holds the requirement REG-03 was trying to express. See
        02-VALIDATION.md "Requirement-Text Divergence".
        """
        portal_setup = getToolByName(self.portal, 'portal_setup')
        metadata = portal_setup.getImportStepMetadata(
            'imio.googleauthenticator')
        self.assertIsNotNone(
            metadata,
            'REG-02: imio.googleauthenticator import step must be registered')
        self.assertIn(
            'plone.app.registry',
            metadata['dependencies'],
            'REG-02: the import step must declare <depends '
            'name="plone.app.registry"/> -- without it the registry records '
            'may not exist when setupVarious runs, and the resulting '
            'get_app_settings() KeyError is a swallowable PAS exception')

    def test_import_step_ordering(self):
        """REG-03: imio.googleauthenticator's import step sorts after
        plone.app.registry.

        Kept as the outcome check that the declared dependency above is
        actually honoured by GenericSetup's topological sort. On its own it
        proves nothing (see
        test_import_step_declares_registry_dependency) -- the two together
        assert both the declaration and its effect.
        """
        portal_setup = getToolByName(self.portal, 'portal_setup')
        steps = portal_setup.getSortedImportSteps()
        self.assertGreater(
            steps.index('imio.googleauthenticator'),
            steps.index('plone.app.registry'),
            'REG-03: imio.googleauthenticator must sort after plone.app.registry')

    def test_registry_records_exist_after_install(self):
        """REG-01/REG-02 outcome: after the default profile is applied, all
        three IGoogleAuthenticatorSettings records exist and
        get_app_settings() returns without raising.
        """
        settings = get_app_settings()
        self.assertIsNotNone(
            settings.globally_enabled,
            'REG-01/REG-02: globally_enabled record must exist after install')
        self.assertIsNotNone(
            settings.ip_addresses_whitelist,
            'REG-01/REG-02: ip_addresses_whitelist record must exist after install')

    def test_install_seeds_ska_secret_key(self):
        """REG-04, post-CR-02 revision: setupVarious seeds ska_secret_key at
        install time (setuphandlers._setup_secret_key), so it is non-empty
        immediately after install -- no PAS-plugin-path mint is required
        for even the very first login.
        """
        self.assertTrue(
            get_app_settings().ska_secret_key,
            'REG-04: install must seed a non-empty ska_secret_key')

    def test_get_ska_secret_key_does_not_mutate_registry(self):
        """CR-02 regression guard: get_ska_secret_key() must be a pure read
        and must NOT write settings.ska_secret_key as a side effect. That
        write, when it happened from sign_user_data() inside
        authenticateCredentials(), was silently discarded by
        transaction.abort() on the Unauthorized login path -- a test that
        only checks the happy path (a getter returning a well-formed key)
        does not catch a reintroduced mint; this asserts the registry value
        is unchanged across the call.
        """
        before = get_app_settings().ska_secret_key
        get_ska_secret_key(
            request=self.request, user=api.user.get_current(), use_browser_hash=False)
        self.assertEqual(
            before, get_app_settings().ska_secret_key,
            'CR-02: get_ska_secret_key() must not mutate ska_secret_key')

    def test_reapply_profile_does_not_reset_ska_secret_key(self):
        """REG-05 regression guard, not a live bug fix: ska_secret_key is
        TextLine(required=False, default=u''), so an existing non-empty
        unicode value revalidates cleanly on profile re-import today, and
        the "bare <records interface=...> replaces the value with the field
        default on re-import" hole does not fire. It would fire the day
        someone adds required=True or a constraint to that field, which is
        what this test guards against.
        """
        known_value = u'known-test-value-for-reg-05'
        get_app_settings().ska_secret_key = known_value
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        self.assertEqual(
            known_value, get_app_settings().ska_secret_key,
            'REG-05: re-applying the default profile must not reset ska_secret_key')

    def test_plugin_is_first_authenticator(self):
        """MFA-03: this IS the security control, not a nice-to-have ordering
        check.

        authenticateCredentials() vetoes a login by wiping the shared
        credentials dict in place -- PAS's _extractUserIds loop hands that
        same dict object to every IAuthenticationPlugin in listing order,
        with no break on success. If this plugin is not first, an
        authenticator listed before it (e.g. source_users, password-only)
        authenticates the user before the wipe ever reaches it, and the
        second factor silently never runs: no error page, no log line.

        Nothing at request time re-asserts this position. A later add-on
        calling movePluginsTop for its own plugin displaces this one to
        index 1 with no warning. The documented recovery is re-applying the
        'imio.googleauthenticator:default' profile, which re-runs
        setuphandlers._add_plugin and its movePluginsTop call -- see
        test_reapply_profile_keeps_plugin_first_and_unique below.
        """
        self.assertEqual(
            PAS_ID,
            self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0],
            'MFA-03: imio.googleauthenticator must be first among '
            'IAuthenticationPlugin, or the second factor silently never runs')

    def test_reapply_profile_keeps_plugin_first_and_unique(self):
        """MFA-03 (adjacency + empty probe rows): re-applying the profile is
        idempotent, and is a real recovery for a displaced plugin.

        First: applying the profile a second time must not raise (activatePlugin
        raises KeyError: 'Duplicate plugin id' for an already-active plugin,
        which is why _add_plugin's activation guard checks listPluginIds
        first) and must leave exactly one PAS_ID entry, still at index 0.

        Second, the case that actually exercises the restructure: displace
        the plugin deliberately, confirm it really moved (a non-vacuity
        control -- otherwise the recovery assertion below could pass for the
        wrong reason), then re-apply the profile and confirm movePluginsTop
        put it back at index 0. Without this pair the guard-split in Task 1
        has no test.
        """
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        ids = self.pas.plugins.listPluginIds(IAuthenticationPlugin)
        self.assertEqual(
            1, ids.count(PAS_ID),
            'MFA-03: re-applying the profile must not duplicate the plugin entry')
        self.assertEqual(
            PAS_ID,
            self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0],
            'MFA-03: re-applying the profile must leave the plugin first')

        self.pas.plugins.movePluginsDown(IAuthenticationPlugin, [PAS_ID])
        self.assertNotEqual(
            PAS_ID,
            self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0],
            'non-vacuity control: the deliberate displacement must actually move '
            'the plugin, or the recovery assertion below proves nothing')

        applyProfile(self.portal, 'imio.googleauthenticator:default')
        self.assertEqual(
            PAS_ID,
            self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0],
            'MFA-03: re-applying the profile must restore the plugin to first '
            'position after a deliberate displacement')

    def test_memberdata_properties_import_declares_expected_types(self):
        """MFA-13 (import half): the GenericSetup import of
        memberdata_properties.xml -- as it actually ships -- registers the
        three new properties on portal_memberdata with type 'int'. A
        round-trip test alone (test_helpers.py's
        test_new_memberdata_properties_round_trip) can pass against a
        fixture whose property sheet is not the one the profile installs;
        this asserts the import itself, via portal_memberdata's own
        property-map API rather than a file read or XML parse.

        The two pre-existing properties are asserted alongside the three
        new ones as a non-vacuity control: if the whole import silently did
        not run, those would fail too, and the new-property failure would
        be ambiguous.
        """
        portal_memberdata = getToolByName(self.portal, 'portal_memberdata')

        expected = (
            ('enable_two_factor_authentication', 'boolean'),
            ('two_factor_authentication_secret', 'string'),
            ('two_factor_authentication_failed_attempts', 'int'),
            ('two_factor_authentication_locked_until', 'int'),
            ('two_factor_authentication_last_interval', 'int'),
        )
        for name, expected_type in expected:
            self.assertIn(
                name, portal_memberdata.propertyIds(),
                'MFA-13: {0!r} must be registered on portal_memberdata by '
                'the profile import'.format(name))
            self.assertEqual(
                expected_type, portal_memberdata.getPropertyType(name),
                'MFA-13: {0!r} must be declared type {1!r} on '
                'portal_memberdata'.format(name, expected_type))

    def test_plugin_declares_no_challenge_protocol(self):
        """Open Question 3: the plugin declares no `protocol` class attribute.

        PAS resolves a challenger's protocol group with
        getattr(challenger, 'protocol', challenger_id)
        (PluggableAuthService.py:1173), so an unset attribute keeps this
        challenger in a protocol group of its own. HTTPBasicAuthHelper is the
        plugin that DOES declare protocol = "http", and PAS's
        IChallengeProtocolChooser/IRequestTypeSniffer machinery routes
        WebDAV/FTP/XML-RPC request types to that group -- if this plugin ever
        joined it (e.g. a future "belt and suspenders" `protocol = 'http'`
        edit), those clients would receive an HTML redirect instead of a
        clean 401. This test exists to fail on exactly that edit.
        """
        self.assertFalse(
            hasattr(self.pas[PAS_ID], 'protocol'),
            'Open Question 3: the plugin must not declare a protocol attribute')

    def test_every_javascript_registration_pins_its_position(self):
        """Each ``<javascript>`` this profile registers must state where it goes.

        ``BaseRegistry.storeResource`` appends, so with no position directive the
        final order depends on when this profile's import step happens to run.
        Installing onto an existing site appends after Plone's own registrations
        and works, which is the only path the test below can exercise. On a fresh
        site, where GenericSetup may run this step before Plone registers jQuery,
        both of this package's scripts landed at positions 0 and 1 with
        ``++resource++plone.app.jquery.js`` at 2 -- observed on a real
        ``server.dmsmail`` deployment, 2026-08-03. Because cooking merges adjacent
        compatible resources into a single bundle, the ``$ is not defined`` thrown
        at the top of ``main.js`` aborted that bundle before jQuery defined
        itself, so every jQuery-dependent script on the site failed and every
        Plone overlay form rendered as a full page.

        This asserts the XML directly rather than the resulting order, because
        the defect is the reliance on append order, and that is visible in the
        file on any install path. Nodes carrying ``remove="True"`` are skipped:
        they unregister and have no position.
        """
        document = minidom.parse(JSREGISTRY_XML)
        nodes = document.getElementsByTagName('javascript')

        self.assertTrue(
            nodes,
            'Non-vacuity control: no <javascript> nodes were parsed from '
            '{0}, so the loop below would assert nothing.'.format(
                JSREGISTRY_XML))

        unpinned = []
        for node in nodes:
            if (node.getAttribute('remove') or '').lower() == 'true':
                continue
            if not any(node.getAttribute(name) for name in POSITION_ATTRIBUTES):
                unpinned.append(node.getAttribute('id'))

        self.assertEqual(
            [], unpinned,
            'These jsregistry.xml entries pin no position, so their load order '
            'depends on when the profile is imported: {0}'.format(unpinned))

    def test_registered_javascript_loads_after_jquery(self):
        """This package's script must sit after jQuery and jQuery Tools.

        ``main.js`` calls ``$(document).ready(...)`` at top level, so it
        needs those two to have run first.

        Honest limitation: the layer's ``setUpPloneSite`` applies our profile
        onto an already-built site, where Plone's registrations are present
        and an append lands after them -- so this passes even with the
        ``insert-bottom`` directives removed. It is the outcome check, not
        the regression check;
        ``test_every_javascript_registration_pins_its_position`` above is the one
        that fails when the directives go away.
        """
        registry = getToolByName(self.portal, 'portal_javascripts')
        resource_ids = [r.getId() for r in registry.getResources()]

        for dependency in ('++resource++plone.app.jquery.js',
                           '++resource++plone.app.jquerytools.js'):
            self.assertIn(
                dependency, resource_ids,
                'Non-vacuity control: {0!r} is not registered at all, so the '
                'ordering assertions below are meaningless.'.format(dependency))

        last_dependency = max(
            resource_ids.index('++resource++plone.app.jquery.js'),
            resource_ids.index('++resource++plone.app.jquerytools.js'))

        ours = ('++resource++imio.googleauthenticator/main.js',)
        for resource_id in ours:
            self.assertIn(
                resource_id, resource_ids,
                '{0!r} was not registered by the profile import'.format(
                    resource_id))
            self.assertGreater(
                resource_ids.index(resource_id), last_dependency,
                '{0!r} loads at position {1}, before jQuery/jQuery Tools '
                'finish at {2} -- it will throw and, if cooked into the same '
                'bundle, take jQuery down with it'.format(
                    resource_id, resource_ids.index(resource_id),
                    last_dependency))

    def test_popupforms_js_is_not_vendored(self):
        """COEX-03: this package must carry no copy of Plone's own
        ``popupforms.js``, and must not unregister Plone's copy from
        ``portal_javascripts``.

        ``imio.dms.mail``'s own ``profiles/default/jsregistry.xml`` carries
        a bare ``insert-after`` reposition entry for the same stock
        resource id (``popupforms.js``). A reposition entry moves an
        existing resource and cannot create one -- so as long as this
        package's own profile still unregistered that id
        (``remove="True"``), any site installing both packages would end
        up with ``imio.dms.mail``'s reposition finding nothing to
        reposition, and every ``prepOverlay``-driven widget it ships would
        break. This asserts all three levels: the vendored file is gone
        from disk, the profile XML mentions no such id and unregisters
        nothing at all, and the live registry still carries Plone's own
        resource after this package installs.
        """
        popupforms_path = os.path.join(
            os.path.dirname(imio.googleauthenticator.__file__),
            'browser', 'static', 'plone_ecmascript', 'popupforms.js')
        self.assertFalse(
            os.path.exists(popupforms_path),
            'COEX-03: the vendored popupforms.js copy must not exist on '
            'disk: {0}'.format(popupforms_path))

        document = minidom.parse(JSREGISTRY_XML)
        nodes = document.getElementsByTagName('javascript')
        for node in nodes:
            node_id = node.getAttribute('id')
            self.assertNotIn(
                'popupforms', node_id,
                'COEX-03: this profile must not mention the stock '
                'popupforms.js resource id at all: {0!r}'.format(node_id))
            self.assertEqual(
                '', node.getAttribute('remove'),
                'COEX-03: this profile must only register resources, '
                'never unregister one it does not own -- node {0!r} '
                'carries a remove attribute'.format(node_id))

        registry = getToolByName(self.portal, 'portal_javascripts')
        resource_ids = [r.getId() for r in registry.getResources()]
        self.assertTrue(
            resource_ids,
            'Non-vacuity control: portal_javascripts has no resources at '
            'all, so the assertion below would be vacuous.')
        self.assertIn(
            'popupforms.js', resource_ids,
            "COEX-03: Plone's own popupforms.js resource must still be "
            'registered after this package installs -- this is the '
            "assertion that actually proves the imio.dms.mail collision "
            'is closed, not merely that our file changed')

    def test_login_form_override_is_deleted(self):
        """COEX-02: the vendored ``login_form.cpt`` override and its
        ``.metadata`` file must not exist on disk.

        Non-vacuity control, same idiom
        ``test_no_second_factor_state_written_from_the_plugin`` uses: a
        file that should still exist under the package directory
        (``profiles/default/jsregistry.xml``, not scheduled for deletion
        in this phase) really does exist, so a wrong ``package_dir`` --
        which would make every absence assertion below pass vacuously --
        is caught.
        """
        package_dir = os.path.dirname(imio.googleauthenticator.__file__)

        control_path = os.path.join(
            package_dir, 'profiles', 'default', 'jsregistry.xml')
        self.assertTrue(
            os.path.exists(control_path),
            'Non-vacuity control: {0} must exist, or package_dir is wrong '
            'and the absence assertions below would pass vacuously'.format(
                control_path))

        override_path = os.path.join(
            package_dir, 'skins', 'googleauthenticator_custom',
            'login_form.cpt')
        self.assertFalse(
            os.path.exists(override_path),
            'COEX-02: the vendored login_form.cpt override must not '
            'exist: {0}'.format(override_path))
        self.assertFalse(
            os.path.exists(override_path + '.metadata'),
            'COEX-02: the vendored login_form.cpt.metadata must not '
            'exist: {0}.metadata'.format(override_path))

    def test_skin_layer_is_removed(self):
        """COEX-05: the skin mechanism this package used to register two
        auxiliary templates through -- now reached instead through
        ``ViewPageTemplateFile`` class attributes (plan 07-02) -- must be
        completely gone: the directory, its GenericSetup registration file,
        its ZCML filesystem-directory registration, and the live outcome
        (no ``googleauthenticator_custom`` skin layer created on install).

        Four assertions, per WR-03. (a)-(c) catch the source-level
        regression; (d) is the one that would catch a stale registration
        surviving in a real site.
        """
        package_dir = os.path.dirname(imio.googleauthenticator.__file__)

        # (a) the skin directory does not exist on disk.
        skins_dir = os.path.join(package_dir, 'skins')
        self.assertFalse(
            os.path.exists(skins_dir),
            'COEX-05: the skins/ directory must not exist: '
            '{0}'.format(skins_dir))

        # (b) profiles/default/skins.xml does not exist.
        skins_xml = os.path.join(
            package_dir, 'profiles', 'default', 'skins.xml')
        self.assertFalse(
            os.path.exists(skins_xml),
            'COEX-05: profiles/default/skins.xml must not exist: '
            '{0}'.format(skins_xml))

        # (c) configure.zcml carries no filesystem-directory registration
        # element, with a positive control in the same read so a wrong
        # path cannot pass vacuously.
        configure_zcml = os.path.join(package_dir, 'configure.zcml')
        with open(configure_zcml) as handle:
            zcml_source = handle.read()
        self.assertNotIn(
            'registerDirectory', zcml_source,
            'COEX-05: configure.zcml must not register a filesystem skin '
            'directory: {0}'.format(configure_zcml))
        self.assertIn(
            'genericsetup:registerProfile', zcml_source,
            'Non-vacuity control: genericsetup:registerProfile must still '
            'be present in configure.zcml, or the read above found the '
            'wrong file and the assertion above would pass vacuously.')

        # (d) the live outcome: no googleauthenticator_custom skin layer is
        # created by the profile, and Plone's own 'custom' layer, the
        # non-vacuity control, is untouched.
        portal_skins = getToolByName(self.portal, 'portal_skins')
        skin_ids = portal_skins.objectIds()
        self.assertIn(
            'custom', skin_ids,
            "Non-vacuity control: Plone's own 'custom' skin layer must "
            'still exist in portal_skins, or the tool lookup above is '
            'wrong and the assertion below would pass vacuously.')
        self.assertNotIn(
            'googleauthenticator_custom', skin_ids,
            'COEX-05: no googleauthenticator_custom object must be '
            'created in portal_skins after this profile installs.')

    def test_uninstall_restores_resource_registries(self):
        """COEX-06: ``profiles/uninstall/`` unregisters exactly this
        package's own ``main.js`` and ``main.css`` and nothing else,
        idempotently and reversibly, and leaves Plone's own
        ``popupforms.js`` overlay resource registered throughout.

        Five assertion groups, per WR-03 -- (c) is the one that actually
        matters: uninstalling this add-on must not leave the whole site
        without Plone's overlay script, the same class of breakage
        COEX-03 removed from the install side.
        """
        js_registry = getToolByName(self.portal, 'portal_javascripts')
        css_registry = getToolByName(self.portal, 'portal_css')
        js_id = '++resource++imio.googleauthenticator/main.js'
        css_id = '++resource++imio.googleauthenticator/main.css'

        # (a) precondition/non-vacuity: both of this package's own
        # resources are registered before the uninstall, or the removal
        # assertions below prove nothing.
        js_ids = [r.getId() for r in js_registry.getResources()]
        css_ids = [r.getId() for r in css_registry.getResources()]
        self.assertIn(
            js_id, js_ids,
            'Non-vacuity control: {0!r} must be registered before the '
            'uninstall, or its absence below proves nothing'.format(js_id))
        self.assertIn(
            css_id, css_ids,
            'Non-vacuity control: {0!r} must be registered before the '
            'uninstall, or its absence below proves nothing'.format(css_id))

        # (b) applying the uninstall profile removes both of this
        # package's own resources.
        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')
        js_ids = [r.getId() for r in js_registry.getResources()]
        css_ids = [r.getId() for r in css_registry.getResources()]
        self.assertNotIn(
            js_id, js_ids,
            'COEX-06: {0!r} must be unregistered by the uninstall '
            'profile'.format(js_id))
        self.assertNotIn(
            css_id, css_ids,
            'COEX-06: {0!r} must be unregistered by the uninstall '
            'profile'.format(css_id))

        # (c) the coexistence half -- the assertion that actually
        # matters: Plone's own overlay resource is still registered
        # after the uninstall.
        self.assertIn(
            'popupforms.js', js_ids,
            "COEX-06: Plone's own popupforms.js must still be registered "
            'in portal_javascripts after this package uninstalls')

        # (d) idempotency: applying the uninstall profile a second time
        # must not raise, and must leave the same resource-id sets.
        # BaseRegistry.unregisterResource filters the resource tuple by
        # id, so a missing id is a no-op rather than a KeyError.
        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')
        js_ids_after_second_uninstall = [
            r.getId() for r in js_registry.getResources()]
        css_ids_after_second_uninstall = [
            r.getId() for r in css_registry.getResources()]
        self.assertEqual(
            js_ids, js_ids_after_second_uninstall,
            'COEX-06: applying the uninstall profile a second time must '
            'not change portal_javascripts')
        self.assertEqual(
            css_ids, css_ids_after_second_uninstall,
            'COEX-06: applying the uninstall profile a second time must '
            'not change portal_css')

        # (e) reversibility: re-applying the default profile
        # re-registers both of this package's own resources -- an
        # uninstall followed by a reinstall is a working site, not a
        # half-registered one. This also restores the installed state
        # this layer's other tests expect.
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        js_ids = [r.getId() for r in js_registry.getResources()]
        css_ids = [r.getId() for r in css_registry.getResources()]
        self.assertIn(
            js_id, js_ids,
            'COEX-06: re-applying the default profile must re-register '
            '{0!r}'.format(js_id))
        self.assertIn(
            css_id, css_ids,
            'COEX-06: re-applying the default profile must re-register '
            '{0!r}'.format(css_id))

    def test_uninstall_removes_pas_plugin(self):
        """T-gfr-06 (COEX-06 widening, quick task 260806-gfr): applying
        ``imio.googleauthenticator:uninstall`` removes the ``google_auth``
        PAS plugin from ``acl_users`` and deactivates it from every plugin
        type it was registered in -- the defect this quick task exists to
        close. Today the plugin survives an uninstall and keeps
        intercepting every login, then unpickles as
        ``OFS.Uninstalled.Broken`` once the egg is removed.

        Five assertion groups, per WR-03.
        """
        # (a) non-vacuity: the plugin is present before the uninstall, or
        # its absence below proves nothing.
        self.assertIn(
            PAS_ID, self.pas.objectIds(),
            'Non-vacuity control: {0!r} must be registered in acl_users '
            'before the uninstall, or its absence below proves '
            'nothing'.format(PAS_ID))

        # (b) applying the uninstall profile removes the plugin object and
        # deactivates it from every plugin type -- pas._delObject(PAS_ID)
        # routes to PluggableAuthService._delOb, which calls
        # plugins.removePluginById(id) before the object goes.
        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')
        self.assertNotIn(
            PAS_ID, self.pas.objectIds(),
            'T-gfr-06: the uninstall profile must remove {0!r} from '
            'acl_users'.format(PAS_ID))
        self.assertNotIn(
            PAS_ID, self.pas.plugins.listPluginIds(IAuthenticationPlugin),
            'T-gfr-06: {0!r} must be deactivated from every plugin type it '
            'was registered in'.format(PAS_ID))

        # (c) idempotency: applying the uninstall profile a second time
        # must not raise -- the objectIds() guard in _remove_plugin is what
        # makes this a no-op instead of an AttributeError on a missing
        # object -- and must leave the plugin still absent.
        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')
        self.assertNotIn(
            PAS_ID, self.pas.objectIds(),
            'T-gfr-06: applying the uninstall profile twice must not '
            'resurrect {0!r}'.format(PAS_ID))

        # (d) reversibility: re-applying the default profile puts the
        # plugin back, first among IAuthenticationPlugin (MFA-03) -- an
        # uninstall followed by a reinstall is a working site, not a
        # half-registered one. This also restores the installed state this
        # layer's other tests expect.
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        self.assertIn(
            PAS_ID, self.pas.objectIds(),
            'T-gfr-06: re-applying the default profile must restore '
            '{0!r}'.format(PAS_ID))
        self.assertEqual(
            PAS_ID,
            self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0],
            'T-gfr-06: re-applying the default profile must restore '
            '{0!r} to first position'.format(PAS_ID))

        # (e) T-gfr-01, setupVarious/uninstallVarious mutual isolation:
        # both handlers run on every profile import in the process
        # (applyProfile's runAllImportStepsFromProfile runs every
        # registered import step, not only the ones the target profile
        # "owns"), and each gates on a data file that exists only in its
        # own profile directory. If uninstallVarious's gate were satisfied
        # by the default profile's directory, step (d) above would have
        # undone _add_plugin's work in the same call instead of restoring
        # the plugin. Symmetrically, if setupVarious's gate were satisfied
        # by the uninstall profile's directory, step (b) above would have
        # recreated the plugin instead of removing it. Both directions are
        # already exercised by the sequence above; (d) and (b) are the
        # assertions that would go red if either gate were wrong.

    def _local_userdataschema_utility_registrations(self):
        """Local-only ``IUserDataSchemaProvider`` utility registrations on
        this site's site manager.

        Deliberately not ``getUtility()``/``queryUtility()``:
        ``plone.app.users`` registers its own global default
        ``IUserDataSchemaProvider`` utility, so either lookup falls back to
        it and would report "present" even after our local registration in
        ``componentregistry.xml`` is gone -- the silent-no-op trap this
        quick task's PLAN.md names explicitly. Filtering
        ``registeredUtilities()`` by ``provided`` iterates local
        registrations only.
        """
        return [
            registration
            for registration in self.portal.getSiteManager().registeredUtilities()
            if registration.provided is IUserDataSchemaProvider
            ]

    def test_uninstall_reverses_the_profile_registrations(self):
        """COEX-06 widening (quick task 260806-gfr, Task 2): applying
        ``imio.googleauthenticator:uninstall`` removes the five artifacts
        ``profiles/default/`` registers -- the local
        ``IUserDataSchemaProvider`` utility, the three
        ``portal_actions/user`` entries, the browser layer, the
        ``google_authenticator_settings`` configlet and the
        ``IGoogleAuthenticatorSettings`` registry records -- idempotently
        and reversibly.

        Five groups, per WR-03, each present-before (non-vacuity) /
        absent-after / still-absent-after-a-second-apply (idempotency) /
        present-again-after-reinstall (reversibility).

        Note: ``IGoogleAuthenticatorSettings`` now declares five fields
        (``max_failed_attempts`` and ``lockout_duration`` were added in
        Phase 5, after this plan's own truths table was written naming
        "three" records) -- this asserts every field the interface
        actually declares, read live via ``.names()``, not a stale
        hardcoded count.
        """
        portal_actions = getToolByName(self.portal, 'portal_actions')
        portal_controlpanel = getToolByName(self.portal, 'portal_controlpanel')
        registry = getUtility(IRegistry)
        action_ids = (
            'enable_two_factor_authentication',
            'disable_two_factor_authentication',
            'regenerate_recovery_codes',
            )
        record_names = [
            '{0}.{1}'.format(IGoogleAuthenticatorSettings.__identifier__, name)
            for name in IGoogleAuthenticatorSettings.names()
            ]

        def _configlet_ids():
            return [action.id for action in portal_controlpanel.listActions()]

        def _user_action_ids():
            return portal_actions.user.objectIds()

        # (a) non-vacuity: all five artifacts are present before the
        # uninstall, or their absence below proves nothing.
        self.assertTrue(
            self._local_userdataschema_utility_registrations(),
            'Non-vacuity control: the local IUserDataSchemaProvider '
            'utility must be registered before the uninstall.')
        for action_id in action_ids:
            self.assertIn(
                action_id, _user_action_ids(),
                'Non-vacuity control: {0!r} must exist under '
                'portal_actions/user before the uninstall.'.format(action_id))
        self.assertIn(
            IGoogleAuthenticatorLayer, registered_layers(),
            'Non-vacuity control: the browser layer must be registered '
            'before the uninstall.')
        self.assertIn(
            'google_authenticator_settings', _configlet_ids(),
            'Non-vacuity control: the configlet must be registered '
            'before the uninstall.')
        for record_name in record_names:
            self.assertIn(
                record_name, registry.records,
                'Non-vacuity control: {0!r} must exist before the '
                'uninstall.'.format(record_name))

        # (b) applying the uninstall profile removes all five.
        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')
        self.assertFalse(
            self._local_userdataschema_utility_registrations(),
            'COEX-06: the local IUserDataSchemaProvider utility must be '
            'unregistered by the uninstall profile.')
        for action_id in action_ids:
            self.assertNotIn(
                action_id, _user_action_ids(),
                'COEX-06: {0!r} must be removed from portal_actions/user '
                'by the uninstall profile.'.format(action_id))
        self.assertNotIn(
            IGoogleAuthenticatorLayer, registered_layers(),
            'COEX-06: the browser layer must be unregistered by the '
            'uninstall profile.')
        self.assertNotIn(
            'google_authenticator_settings', _configlet_ids(),
            'COEX-06: the configlet must be unregistered by the '
            'uninstall profile.')
        for record_name in record_names:
            self.assertNotIn(
                record_name, registry.records,
                'COEX-06: {0!r} must be removed by the uninstall '
                'profile.'.format(record_name))

        # (c) idempotency: applying the uninstall profile a second time
        # must not raise, and must leave the same absence.
        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')
        self.assertFalse(
            self._local_userdataschema_utility_registrations(),
            'COEX-06: applying the uninstall profile twice must not '
            'resurrect the local utility.')
        for action_id in action_ids:
            self.assertNotIn(
                action_id, _user_action_ids(),
                'COEX-06: applying the uninstall profile twice must not '
                'resurrect {0!r}.'.format(action_id))
        self.assertNotIn(
            IGoogleAuthenticatorLayer, registered_layers(),
            'COEX-06: applying the uninstall profile twice must not '
            'resurrect the browser layer.')
        self.assertNotIn(
            'google_authenticator_settings', _configlet_ids(),
            'COEX-06: applying the uninstall profile twice must not '
            'resurrect the configlet.')
        for record_name in record_names:
            self.assertNotIn(
                record_name, registry.records,
                'COEX-06: applying the uninstall profile twice must not '
                'resurrect {0!r}.'.format(record_name))

        # (d) reversibility: re-applying the default profile restores all
        # five -- an uninstall followed by a reinstall is a working site,
        # not a half-registered one. This also restores the installed
        # state this layer's other tests expect.
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        self.assertTrue(
            self._local_userdataschema_utility_registrations(),
            'COEX-06: re-applying the default profile must restore the '
            'local IUserDataSchemaProvider utility.')
        for action_id in action_ids:
            self.assertIn(
                action_id, _user_action_ids(),
                'COEX-06: re-applying the default profile must restore '
                '{0!r}.'.format(action_id))
        self.assertIn(
            IGoogleAuthenticatorLayer, registered_layers(),
            'COEX-06: re-applying the default profile must restore the '
            'browser layer.')
        self.assertIn(
            'google_authenticator_settings', _configlet_ids(),
            'COEX-06: re-applying the default profile must restore the '
            'configlet.')
        for record_name in record_names:
            self.assertIn(
                record_name, registry.records,
                'COEX-06: re-applying the default profile must restore '
                '{0!r}.'.format(record_name))

    def test_uninstall_keeps_enrolled_user_data(self):
        """T-gfr-04 (deliberate exclusion, pinned): the uninstall profile
        must NOT touch ``portal_memberdata``'s property declarations or an
        enrolled user's stored seed. ``memberdata_properties.xml`` stays
        out of ``profiles/uninstall/`` on purpose -- removing those eight
        declarations would destroy every enrolled user's encrypted seed
        and recovery-code hashes with no recovery path, and an uninstall
        is often temporary. A future edit that starts deleting user data
        must turn this test red.
        """
        portal_memberdata = getToolByName(self.portal, 'portal_memberdata')
        expected_properties = (
            'enable_two_factor_authentication',
            'two_factor_authentication_secret',
            'bar_code_reset_token',
            'two_factor_authentication_failed_attempts',
            'two_factor_authentication_locked_until',
            'two_factor_authentication_last_interval',
            'two_factor_authentication_recovery_codes_salt',
            'two_factor_authentication_recovery_codes_hashes',
            )

        # Non-vacuity: all eight are declared before the uninstall, or
        # their survival below proves nothing.
        for name in expected_properties:
            self.assertIn(
                name, portal_memberdata.propertyIds(),
                'Non-vacuity control: {0!r} must be declared on '
                'portal_memberdata before the uninstall.'.format(name))

        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        user = api.user.get(username=TEST_USER_ID)
        known_seed = u'v1$known-test-seed-for-260806-gfr'
        user.setMemberProperties(mapping={
            'enable_two_factor_authentication': True,
            'two_factor_authentication_secret': known_seed,
            })
        # .claude/CLAUDE.md: undeclared memberdata properties are
        # silently popped with no error by MutablePropertySheet.
        # setProperties -- assert the read-back rather than trusting the
        # write.
        self.assertEqual(
            known_seed,
            user.getProperty('two_factor_authentication_secret'),
            'Non-vacuity control: the seed written above must actually '
            'be readable before the uninstall, or its survival below '
            'proves nothing.')

        applyProfile(self.portal, 'imio.googleauthenticator:uninstall')

        for name in expected_properties:
            self.assertIn(
                name, portal_memberdata.propertyIds(),
                'T-gfr-04: {0!r} must survive the uninstall untouched -- '
                'removing it would destroy enrolled users\' data.'.format(
                    name))
        self.assertEqual(
            known_seed,
            user.getProperty('two_factor_authentication_secret'),
            'T-gfr-04: an enrolled user\'s stored seed must survive the '
            'uninstall byte-identical.')

        applyProfile(self.portal, 'imio.googleauthenticator:default')

    def _replay_dms_mail_reposition(self, registry):
        """Replay ``imio.dms.mail``'s own reposition entry for the stock
        ``popupforms.js`` resource -- ``imio/dms/mail/profiles/default/
        jsregistry.xml``, around line 102: ``<javascript id="popupforms.js"
        insert-after="form_tabbing.js" />``.

        A bare reposition entry carries no other attribute, so
        ``Products.ResourceRegistries.exportimport.resourceregistry.
        _initResources`` routes it straight to ``moveResourceAfter`` --
        the same tool method called here -- with no registration call at
        all, which is the whole mechanism of the collision this phase
        closes: it can move an existing resource, never create one.
        """
        registry.moveResourceAfter('popupforms.js', 'form_tabbing.js')

    def test_popupforms_js_survives_either_install_order(self):
        """COEX-07 (automated half), COEX-03: ``imio.dms.mail``'s real
        bare reposition entry for the stock ``popupforms.js`` resource
        must not duplicate or delete that resource, whether it is
        replayed before or after this package's own profile, and under a
        repeated import of either.

        This is a *synthetic* collision test: it replays the reposition
        directly against ``portal_javascripts`` rather than installing
        the ``imio.dms.mail`` egg. The real two-egg proof is plan
        07-04's human-verify item -- a verification report claiming
        COEX-07 is fully automated by this test alone is wrong.
        """
        registry = getToolByName(self.portal, 'portal_javascripts')
        resource_ids = [r.getId() for r in registry.getResources()]

        # (a) non-vacuity controls: both ids the reposition needs are
        # registered by stock Plone in this fixture, or neither ordering
        # assertion below means anything.
        self.assertIn(
            'popupforms.js', resource_ids,
            'Non-vacuity control: stock popupforms.js must be registered '
            'by Plone in this fixture, or the ordering assertions below '
            'are meaningless.')
        self.assertIn(
            'form_tabbing.js', resource_ids,
            'Non-vacuity control: stock form_tabbing.js must be '
            'registered by Plone in this fixture, or the reposition '
            'below has nothing to reposition after.')

        # (b) order A: this package's profile applies, then the
        # reposition.
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        self._replay_dms_mail_reposition(registry)
        resource_ids = [r.getId() for r in registry.getResources()]
        self.assertEqual(
            1, resource_ids.count('popupforms.js'),
            'COEX-07: popupforms.js must appear exactly once after '
            'imio.googleauthenticator:default then the imio.dms.mail '
            'reposition -- never 0 (this package deleted it) and never '
            '2 (a duplicate registration)')

        # (c) order B: the reposition applies first, then this
        # package's profile.
        self._replay_dms_mail_reposition(registry)
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        resource_ids = [r.getId() for r in registry.getResources()]
        self.assertEqual(
            1, resource_ids.count('popupforms.js'),
            'COEX-07: popupforms.js must appear exactly once after the '
            'imio.dms.mail reposition then '
            'imio.googleauthenticator:default -- never 0 and never 2')

        # (e) the idempotency edge the probe raised: a second import of
        # the default profile must not duplicate either resource --
        # _initResources routes a duplicate registration to the update
        # method rather than a second entry.
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        resource_ids = [r.getId() for r in registry.getResources()]
        self.assertEqual(
            1, resource_ids.count('popupforms.js'),
            'COEX-07: a second default-profile import must not '
            "duplicate Plone's own popupforms.js")
        self.assertEqual(
            1, resource_ids.count(
                '++resource++imio.googleauthenticator/main.js'),
            'COEX-07: a second default-profile import must not '
            "duplicate this package's own main.js")

    def test_profile_only_registers_resources_it_owns(self):
        """Ownership invariant, promoted from plan 07-01's
        assumption-delta decision: this package registers, repositions
        and unregisters only resource ids under its own
        ``++resource++imio.googleauthenticator/`` prefix, across all
        four resource-registry profile files.

        Exists to go red the day a future phase reintroduces a bare
        Plone resource id in any of ``profiles/default/jsregistry.xml``,
        ``profiles/default/cssregistry.xml``,
        ``profiles/uninstall/jsregistry.xml`` or
        ``profiles/uninstall/cssregistry.xml``, whether to add, move or
        remove it.
        """
        prefix = '++resource++imio.googleauthenticator/'
        files = (
            JSREGISTRY_XML, CSSREGISTRY_XML,
            UNINSTALL_JSREGISTRY_XML, UNINSTALL_CSSREGISTRY_XML,
            )
        all_nodes = []
        for path in files:
            document = minidom.parse(path)
            all_nodes.extend(document.getElementsByTagName('javascript'))
            all_nodes.extend(document.getElementsByTagName('stylesheet'))

        self.assertGreaterEqual(
            len(all_nodes), 4,
            'Non-vacuity control: fewer than 4 nodes were parsed across '
            'the four resource-registry profile files, so a wrong path '
            'or a failed parse could pass with an empty loop.')

        offenders = [
            node.getAttribute('id') for node in all_nodes
            if not node.getAttribute('id').startswith(prefix)
            ]
        self.assertEqual(
            [], offenders,
            'These resource-registry ids do not start with {0!r}: {1}. '
            'This package must register, reposition and unregister only '
            'resources it owns.'.format(prefix, offenders))

    def test_user_creation_survives_absent_settings_records(self):
        """COEX-10: userdataschema.userCreatedHandler is registered
        instance-wide in configure.zcml, with no site or layer constraint, so
        it fires for user creation in every Plone site in the process --
        including sites that never installed this add-on's profile. Reading
        IGoogleAuthenticatorSettings there raised KeyError, and because
        PluggableAuthService notifies the event from inside _doAddUser, that
        raise escaped through addMember and aborted addPloneSite: creating a
        site from imio.dms.mail's examples profile failed outright and no site
        was created (observed 2026-08-05).

        Exercises the real path rather than calling the handler directly --
        api.user.create reaches _doAddUser -> notify() -> the subscriber,
        which is what actually broke.
        """
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        registry = getUtility(IRegistry)
        record_name = '{0}.globally_enabled'.format(
            IGoogleAuthenticatorSettings.__identifier__)

        # Non-vacuity control: the record must exist to begin with, or
        # removing it below proves nothing about the guard.
        self.assertIn(
            record_name, registry.records,
            'Non-vacuity control: the record this test removes must exist '
            'after install, otherwise removing it cannot exercise the guard.')

        # Copy the field and value out before deleting. A Record cannot restore
        # itself: Record.field looks the field up from registry._fields, which
        # the delete below removes, so re-assigning the saved Record raises.
        saved_field = registry.records[record_name].field
        saved_value = registry.records[record_name].value
        del registry.records[record_name]
        try:
            user = api.user.create(
                email='no-settings-records@example.com',
                username='no-settings-records-user',
                password='Secret0123!')
        finally:
            registry.records[record_name] = Record(saved_field, saved_value)

        self.assertFalse(
            user.getProperty('enable_two_factor_authentication', False),
            'COEX-10: a site with no settings records must not enrol the '
            'user -- and must not raise while declining to.')
        self.assertFalse(
            user.getProperty('two_factor_authentication_secret', ''),
            'COEX-10: no seed may be minted in a site that has no settings.')
