from cryptography.fernet import Fernet
from imio.googleauthenticator import helpers
from imio.googleauthenticator import pas_plugin
from imio.googleauthenticator.helpers import get_or_create_secret
from imio.googleauthenticator.setuphandlers import PAS_ID
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from zope.globalrequest import setRequest

import base64
import imio.googleauthenticator
import os
import unittest2 as unittest


def _boom(*args, **kwargs):
    raise ValueError('deliberate: injected via a real collaborator')


class TestPas(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.pas = getToolByName(self.portal, 'acl_users')
        self.portal_url = api.portal.get().absolute_url()

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
        # own setUp key, rather than trusting a property that may already
        # be set by an earlier test method in this layer.
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

    def test_form_post_veto(self):
        """T-04-20 / MFA-04: a 2FA-enabled user's login-form POST
        credentials must not authenticate via _extractUserIds -- 'return
        None' from authenticateCredentials vetoes nothing on its own, PAS
        accumulates every authenticator's result and returns the first
        success (PluggableAuthService.py:648-667); the wipe of the shared
        dict is the only veto the interface offers.

        Non-vacuity control, run FIRST with 2FA still disabled: the
        identical credentials DO authenticate. Without this control a pass
        below could be explained by a wrong password in the fixture rather
        than by the veto -- the easiest mistake to make with any assertion
        of absence.

        Proven load-bearing by mutation (04-03-SUMMARY.md): commenting out
        the credentials-wipe loop in authenticateCredentials makes this
        test go red.
        """
        request = self.layer['request']
        request.form['__ac_name'] = TEST_USER_NAME
        request.form['__ac_password'] = TEST_USER_PASSWORD
        setRequest(request)
        try:
            user_ids = self.pas._extractUserIds(request, self.pas.plugins)
            self.assertTrue(
                user_ids,
                'non-vacuity control: the same credentials must authenticate '
                'while 2FA is still disabled, or the veto below proves nothing')

            login(self.portal, TEST_USER_NAME)
            user = api.user.get_current()
            user.setMemberProperties(
                mapping={'enable_two_factor_authentication': True})
            get_or_create_secret(user, overwrite=True)

            user_ids = self.pas._extractUserIds(request, self.pas.plugins)
            self.assertFalse(
                user_ids,
                'MFA-04: a 2FA-enabled user must not authenticate on a '
                'login-form POST alone')
        finally:
            setRequest(None)

    def test_basic_auth_veto(self):
        """T-04-20 / MFA-01: a 2FA-enabled user presenting Authorization:
        Basic must not authenticate via _extractUserIds either.

        Call level per 04-02-SUMMARY.md's explicit guidance: 04-02's
        checkpoint kept credentials_basic_auth ACTIVE, so this asserts
        through the normal _extractUserIds path -- the extractor still
        produces a credentials dict for every request, and this plugin's
        in-place wipe (first among IAuthenticationPlugin, per
        test_plugin_is_first_authenticator) must blind it. A direct
        authenticateCredentials call bypassing extraction would only apply
        under the (unselected) deactivate branch.

        Non-vacuity control, run FIRST with 2FA still disabled: the
        identical header DOES authenticate.

        Proven load-bearing by mutation (04-03-SUMMARY.md): commenting out
        the credentials-wipe loop in authenticateCredentials makes this
        test go red.
        """
        request = self.layer['request']
        request._auth = 'Basic ' + base64.b64encode(
            '%s:%s' % (TEST_USER_NAME, TEST_USER_PASSWORD))
        setRequest(request)
        try:
            user_ids = self.pas._extractUserIds(request, self.pas.plugins)
            self.assertTrue(
                user_ids,
                'non-vacuity control: the same Basic Auth header must '
                'authenticate while 2FA is still disabled, or the veto '
                'below proves nothing')

            login(self.portal, TEST_USER_NAME)
            user = api.user.get_current()
            user.setMemberProperties(
                mapping={'enable_two_factor_authentication': True})
            get_or_create_secret(user, overwrite=True)

            user_ids = self.pas._extractUserIds(request, self.pas.plugins)
            self.assertFalse(
                user_ids,
                'MFA-01: a 2FA-enabled user must not authenticate via '
                'Authorization: Basic alone')
        finally:
            setRequest(None)

    def test_both_extractors_at_once_grant_no_session(self):
        """MFA-04 (adjacency probe row): a single request carrying BOTH
        form credentials and an Authorization: Basic header for the same
        2FA-enabled user. PAS's _extractUserIds loop runs the whole
        authenticator loop once per IExtractionPlugin against that
        extractor's own credentials dict, with no break on success
        (PluggableAuthService.py:620-675) -- the two paths separate rather
        than merge or collide, so the veto has to hold in both passes
        independently. There is no assertion pinning extractor order, and
        none should be added -- the invariant this test demonstrates is
        that order does not matter, because each extractor gets its own
        full pass.

        Proven load-bearing by mutation (04-03-SUMMARY.md): commenting out
        the credentials-wipe loop in authenticateCredentials makes this
        test go red.
        """
        login(self.portal, TEST_USER_NAME)
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(user, overwrite=True)

        request = self.layer['request']
        request.form['__ac_name'] = TEST_USER_NAME
        request.form['__ac_password'] = TEST_USER_PASSWORD
        request._auth = 'Basic ' + base64.b64encode(
            '%s:%s' % (TEST_USER_NAME, TEST_USER_PASSWORD))
        setRequest(request)
        try:
            user_ids = self.pas._extractUserIds(request, self.pas.plugins)
            self.assertFalse(
                user_ids,
                'MFA-04: neither extractor pass may grant a session when '
                'both carry credentials for the same 2FA-enabled user')
        finally:
            setRequest(None)

    def test_empty_credentials_do_not_raise(self):
        """MFA-04 (empty probe row): authenticateCredentials({}) returns
        None and raises nothing. credentials.get('login') is falsy, so the
        branch exits before any user lookup.

        Unreachable through PAS itself, which assigns credentials['login']
        at PluggableAuthService.py:638 before ever calling an
        authenticator -- but reachable by a direct call, and with
        _dont_swallow_my_exceptions = True (RENAME-11) a KeyError here
        would be an HTTP 500 rather than a declined login. Also covers the
        empty-string and None-login variants in the same method (WR-03:
        this is still one requirement, not three).
        """
        plugin = self.pas[PAS_ID]
        request = self.layer['request']
        setRequest(request)
        try:
            self.assertIsNone(plugin.authenticateCredentials({}))
            self.assertIsNone(
                plugin.authenticateCredentials({'login': '', 'password': ''}))
            self.assertIsNone(plugin.authenticateCredentials({'login': None}))
        finally:
            setRequest(None)

    def test_no_second_factor_state_written_from_the_plugin(self):
        """MFA-12, and the standing R-04-C constraint from 04-SECURITY.md:
        pas_plugin.py and subscribers.py must write no second-factor state
        at all -- the write must live in a view that commits, never in a
        path the publisher's transaction.abort() discards. Read at source
        level rather than by behavioural probing, so this pins the
        invariant regardless of which request path a future edit might
        reach it from.

        Extended in plan 06-03 (this plan spans plans 05-01 and 06-01) to
        cover Phase 6's two new writers of this same guard: the recovery
        code salt/hash properties (written by ``generate_recovery_codes``
        at enrollment/regeneration, and mutated on consume by
        ``validate_recovery_code``) and the promoted dispatcher
        ``validate_second_factor``, which supersedes ``06-RESEARCH.md``'s
        proposed name ``validate_token_or_recovery_code`` (plan 06-01's
        ``assumption_delta_decision`` -- a future reader should grep for
        the promoted name).

        Positive controls prove the search itself is not broken: each
        name in ``property_names``/``helper_function_names`` has at least
        one positive-control pairing below, asserted against the specific
        file it legitimately lives in -- pinned per-file rather than
        "anywhere", because a positive control asserted against the wrong
        file would pass vacuously and hide a broken search, which is the
        one failure mode this whole test exists to rule out.
        ``two_factor_authentication_last_interval`` is plan 05-02's
        property (drift/replay) -- it is checked for absence from
        pas_plugin.py/subscribers.py here too, but has no positive control
        since nothing in helpers.py references it yet.

        Extended again (gap fix following plan 10-01) to cover the
        enrollment-completion property ``two_factor_authentication_enrolled``
        and its sole writer ``mark_enrollment_completed`` (both from
        helpers.py). ``has_completed_enrollment``, the paired *read*
        helper, is deliberately NOT added to ``helper_function_names``:
        it legitimately appears in pas_plugin.py (the login path reads
        enrollment status to decide where to route the user), so adding
        it would make this test fail against a correct design. Only the
        write side belongs in the guard.
        """
        package_dir = os.path.dirname(imio.googleauthenticator.__file__)

        with open(os.path.join(package_dir, 'pas_plugin.py')) as handle:
            pas_plugin_source = handle.read()
        with open(os.path.join(package_dir, 'subscribers.py')) as handle:
            subscribers_source = handle.read()
        with open(os.path.join(package_dir, 'helpers.py')) as handle:
            helpers_source = handle.read()
        with open(os.path.join(
                package_dir, 'browser', 'forms', 'token.py')) as handle:
            token_source = handle.read()
        with open(os.path.join(
                package_dir, 'browser', 'forms',
                'user_setup.py')) as handle:
            user_setup_source = handle.read()

        property_names = (
            'two_factor_authentication_failed_attempts',
            'two_factor_authentication_locked_until',
            'two_factor_authentication_last_interval',
            'two_factor_authentication_recovery_codes_salt',
            'two_factor_authentication_recovery_codes_hashes',
            'two_factor_authentication_enrolled',
        )
        helper_function_names = (
            'is_account_locked',
            'register_failed_second_factor',
            'reset_failed_second_factor',
            'generate_recovery_codes',
            'validate_recovery_code',
            'validate_second_factor',
            # has_completed_enrollment (the paired read helper) is
            # deliberately excluded here -- see this method's docstring.
            'mark_enrollment_completed',
        )

        for name in property_names + helper_function_names:
            self.assertNotIn(
                name, pas_plugin_source,
                'MFA-12: {0!r} must not appear in pas_plugin.py -- the '
                'write must live in a view that commits'.format(name))
            self.assertNotIn(
                name, subscribers_source,
                'MFA-12: {0!r} must not appear in subscribers.py -- '
                'reached from a request the publisher aborts'.format(name))

        # Positive controls, restructured (06-03) into (name, source,
        # label) triples: every existing pair from 05-01 preserved
        # verbatim, plus the two new properties against helpers.py,
        # validate_second_factor against token.py, generate_recovery_codes
        # against user_setup.py (where enrollment/regeneration call it),
        # and validate_recovery_code against helpers.py (referenced only
        # there). A property or function whose positive control pointed
        # at the wrong file would pass even if the absence loop above
        # were checking nothing at all.
        positive_controls = (
            ('two_factor_authentication_failed_attempts',
                helpers_source, 'helpers.py'),
            ('two_factor_authentication_locked_until',
                helpers_source, 'helpers.py'),
            ('two_factor_authentication_recovery_codes_salt',
                helpers_source, 'helpers.py'),
            ('two_factor_authentication_recovery_codes_hashes',
                helpers_source, 'helpers.py'),
            ('is_account_locked', token_source, 'token.py'),
            ('register_failed_second_factor', token_source, 'token.py'),
            ('reset_failed_second_factor', token_source, 'token.py'),
            ('validate_second_factor', token_source, 'token.py'),
            ('generate_recovery_codes', user_setup_source, 'user_setup.py'),
            ('validate_recovery_code', helpers_source, 'helpers.py'),
            ('two_factor_authentication_enrolled',
                helpers_source, 'helpers.py'),
            ('mark_enrollment_completed',
                user_setup_source, 'user_setup.py'),
        )
        for name, source, label in positive_controls:
            self.assertIn(
                name, source,
                'non-vacuity control: {0!r} must be present in '
                '{1}'.format(name, label))

    def test_exception_path_still_wipes_credentials(self):
        """ROADMAP success criterion 5: an exception raised after the 2FA
        branch has begun must leave the shared credentials dict empty, so
        the refusal holds even in the counterfactual world
        test_plugin_exception_is_swallowed_without_the_flag documents,
        where PAS swallows the exception and continues to source_users
        with whatever is left in the dict.

        Injected via pas_plugin._mark_2fa_pending -- the module-level seam
        plan 04-01 introduced, rebound the same way this file already
        rebinds pas_plugin.is_whitelisted_client -- rather than by
        monkeypatching authenticateCredentials itself.

        Proven load-bearing by a second mutation (04-03-SUMMARY.md): moving
        the wipe below this call site (rather than to its current position,
        ahead of first-factor delegation) makes this test go red, which is
        the only proof that the wipe-before-delegation reordering is
        load-bearing rather than cosmetic.
        """
        login(self.portal, TEST_USER_NAME)
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(user, overwrite=True)

        request = self.layer['request']
        setRequest(request)
        original = pas_plugin._mark_2fa_pending
        pas_plugin._mark_2fa_pending = _boom
        try:
            plugin = self.pas[PAS_ID]
            credentials = {
                'login': TEST_USER_NAME, 'password': TEST_USER_PASSWORD}
            self.assertRaises(
                ValueError, plugin.authenticateCredentials, credentials)
            self.assertEqual(
                {}, credentials,
                'the credentials dict must still be empty on the exception '
                'exit, or a later authenticator sees the original login/'
                'password intact')
        finally:
            pas_plugin._mark_2fa_pending = original
            setRequest(None)
