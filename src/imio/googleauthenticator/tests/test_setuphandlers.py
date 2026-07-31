import unittest2 as unittest

from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin

from plone import api
from plone.app.testing import applyProfile

from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_ska_secret_key
from imio.googleauthenticator.setuphandlers import PAS_ID
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


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
