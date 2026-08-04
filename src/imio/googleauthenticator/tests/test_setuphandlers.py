import os.path
import unittest2 as unittest
from xml.dom import minidom

from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin

from plone import api
from plone.app.testing import applyProfile

import imio.googleauthenticator
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_ska_secret_key
from imio.googleauthenticator.setuphandlers import PAS_ID
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

JSREGISTRY_XML = os.path.join(
    os.path.dirname(imio.googleauthenticator.__file__),
    'profiles', 'default', 'jsregistry.xml')

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

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self.pas = getToolByName(self.portal, 'acl_users')
        self._install()

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

        Honest limitation: ``BaseTest._install()`` installs onto an already-built
        site, where Plone's registrations are present and an append lands after
        them -- so this passes even with the ``insert-bottom`` directives
        removed. It is the outcome check, not the regression check;
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
