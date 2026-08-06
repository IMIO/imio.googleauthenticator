from cryptography.fernet import Fernet
from imio.googleauthenticator import helpers
from imio.googleauthenticator.browser.forms import user_setup
from imio.googleauthenticator.browser.forms.user_setup import SetupForm
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from onetimepass import get_totp
from plone import api
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import TEST_USER_NAME
from plone.testing import z2
from Products.statusmessages.interfaces import IStatusMessage
from zope.globalrequest import setRequest

import os
import time
import unittest2 as unittest


class _RaisesOnFirstCall(object):
    """Stand-in for ``user_setup.IStatusMessage``, used only for the
    exception-branch scenario below. It raises on its first invocation
    (simulating a failure of the ``IStatusMessage(self.request)`` call
    inside ``handleSubmit``'s ``try:``) and delegates to the real adapter
    factory on every call after that -- the ``if reason is not None:``
    block calls it again, and that second call must succeed or the test
    cannot observe the redirect.
    """

    def __init__(self, real):
        self._real = real
        self._calls = 0

    def __call__(self, request):
        self._calls += 1
        if self._calls == 1:
            raise ValueError('deliberate: injected via a real collaborator')
        return self._real(request)


class TestSetupForm(unittest.TestCase, BaseTest):
    """BUG-02: this class does not fix anything in user_setup.py -- research
    traced all three reachable branches of SetupForm.handleSubmit and found
    redirect_url bound on every one of them, so the UnboundLocalError the
    requirement describes does not reproduce on the current source. This is
    a regression guard, not the verification of a fix. The trace, one
    branch per scenario below:

    1. valid_token True, no exception: redirect_url is bound inside the
       try: to None, immediately after generate_recovery_codes mints the
       ten codes (RECOV-03: this is a deliberate behaviour change from the
       "redirect_url = ...@@personal-information" this scenario used to
       assert -- the success response now renders the codes in place of
       redirecting). reason stays None, so the "if reason is not None:"
       fallback is skipped and no redirect happens.
    2. valid_token True, an exception raised inside the try: (here, from
       the first IStatusMessage(self.request) call): reason is set to
       "An unexpected error occurred." without reaching either the
       generate_recovery_codes call or the redirect_url assignment inside
       the try; the "if reason is not None:" block then binds redirect_url
       to "...@@setup-two-factor-authentication".
    3. valid_token False: reason is set directly, same fallback binds
       redirect_url to the same "...@@setup-two-factor-authentication"
       target as scenario 2.
    4. valid_token True, generate_recovery_codes itself raises: the same
       fallback as scenarios 2 and 3 -- generate_recovery_codes runs inside
       the same try:, so its failure hits the existing
       "except Exception: logger.exception(...)" branch and redirect_url is
       bound by the same "if reason is not None:" block. No new failure
       branch, no new message string.
    redirect_url is bound on all four reachable paths -- there is no fifth
    branch that skips every assignment.

    CR-01/MFA-08/MFA-11: this class also covers the lockout-counter wiring
    added to ``handleSubmit`` -- the enrolment/regeneration form is the
    third of the three ``validate_token`` callers in this package to share
    the ``is_account_locked``/``register_failed_second_factor``/
    ``reset_failed_second_factor`` counter that ``token.py`` and
    ``reset_bar_code.py`` already used. The BUG-02 framing above this
    docstring paragraph describes only the original regression guard; it no
    longer describes the whole class.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        # See TestSkaSecretKey.setUp's docstring in test_helpers.py:
        # PLONE_FIXTURE caches the test user's property sheets before this
        # add-on's memberdata_properties.xml is applied, so a re-login is
        # mandatory or setMemberProperties silently drops
        # enable_two_factor_authentication / the secret property.
        login(self.portal, TEST_USER_NAME)
        # updateFields() -> get_token_description() -> get_domain_name()
        # falls back to zope.globalrequest.getRequest() when called with no
        # request argument; register self.request as the current one, same
        # pattern test_pas_plugin.py uses.
        setRequest(self.request)

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()
        # Cross-test leakage hazard documented in 03-01-SUMMARY.md Deviation
        # #2: this layer does not isolate memberdata writes per test method,
        # so a ciphertext written by an earlier test method under a
        # different key survives into this one. updateFields() -> get_token_
        # description() -> get_or_create_secret(overwrite=False) would try
        # to decrypt that stale ciphertext under this test's fresh key and
        # raise. Force a fresh secret under the current key up front.
        helpers.get_or_create_secret(api.user.get_current(), overwrite=True)
        # Same MemberData-cache leakage hazard, applied to the lockout/
        # replay/enrolment/recovery-code properties: a lock, a counter, a
        # last-accepted-interval or a stored recovery-code set left behind
        # by an earlier test method (in this class or an earlier one
        # sharing the layer) would make the assertions below vacuous, or
        # would make a genuinely-correct code read as a replay (MFA-06).
        api.user.get_current().setMemberProperties(mapping={
            'enable_two_factor_authentication': False,
            'two_factor_authentication_failed_attempts': 0,
            'two_factor_authentication_locked_until': 0,
            'two_factor_authentication_last_interval': 0,
            'two_factor_authentication_recovery_codes_salt': '',
            'two_factor_authentication_recovery_codes_hashes': (),
        })

    def tearDown(self):
        setRequest(None)
        # Mirrors test_reset_bar_code.py's tearDown: a lock or counter set
        # by one test method here must not leak into a later class sharing
        # this layer.
        user = api.user.get(username=TEST_USER_NAME)
        if user is not None:
            user.setMemberProperties(mapping={
                'enable_two_factor_authentication': False,
                'two_factor_authentication_failed_attempts': 0,
                'two_factor_authentication_locked_until': 0,
                'two_factor_authentication_last_interval': 0,
                'two_factor_authentication_recovery_codes_salt': '',
                'two_factor_authentication_recovery_codes_hashes': (),
            })
        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key

    def _clear_location(self):
        if 'location' in self.request.response.headers:
            del self.request.response.headers['location']

    def _wrong_code(self, correct_code):
        """Mirrors test_reset_bar_code.py::_wrong_code."""
        return u'000000' if correct_code != u'000000' else u'111111'

    def _build_form(self, token_value):
        """Builds and updates a fresh SetupForm with ``token_value`` (which
        may be '' to leave the field empty) submitted under z3c.form's
        default prefix-composed widget name.
        """
        self.request.form = {}
        # ZPublisher's HTTPRequest.get() caches whatever it resolves into
        # self.request.other, so a later scenario overwriting
        # self.request.form alone would still read back an earlier
        # scenario's stale token value. Both this test file's own
        # mechanics, not a production bug.
        self.request.other.clear()
        # HTTPRequest.__init__ normally seeds other['RESPONSE'] alongside
        # self.response (ZPublisher/HTTPRequest.py); clearing ``other``
        # above drops that alias. A real request always has it, so restore
        # it here rather than in every caller -- render() on the unwrapped
        # form (used by test_recovery_codes_are_issued_once_at_enrollment)
        # needs request.RESPONSE to resolve the Plone default page
        # template macros.
        self.request.other['RESPONSE'] = self.request.response
        # HTTPRequest.__init__ also seeds other['URL'] alongside RESPONSE;
        # z3c.form.form.Form.action calls request.getURL() unconditionally,
        # and Plone's default standalone form page template (rendered by
        # the unwrapped SetupForm's own render(), used below and by
        # test_recovery_codes_are_issued_once_at_enrollment) reads that
        # property. A real request always has both; restore them here
        # rather than in every caller of this helper.
        self.request.other['URL'] = self.portal_url
        form = SetupForm(self.portal, self.request)
        # FormWrapper.__init__ (plone.z3cform.layout) sets this on the
        # wrapped form instance in production.
        form.__name__ = 'setup-two-factor-authentication'
        form.update()
        widget_name = form.widgets['token'].name
        if widget_name != 'form.widgets.token':
            # One-line fallback per this plan's flagged assumption: report
            # the actual widget name rather than guessing further.
            print(widget_name)
        if token_value:
            # The TextLine widget's converter requires unicode input (a
            # str value fails extraction with WrongType, not with the
            # required-field error scenario 4 exercises).
            if isinstance(token_value, str):
                token_value = token_value.decode('ascii')
            self.request.form[widget_name] = token_value
            form = SetupForm(self.portal, self.request)
            form.update()
        return form

    def test_handleSubmit_refuses_an_account_not_defined_in_this_site(self):
        """T-03-23: enrolment must refuse a Zope-root account rather than
        report success for a second factor its login will never be asked for.

        ``validate_token`` is stubbed to True so the refusal cannot be
        explained by a rejected code: the point is that even a *correct* code
        does not enrol such an account. The two assertions that matter are
        negative -- no flag written and no seed minted -- because the original
        defect wrote both and then said "successfully enabled".
        """
        real_validate_token = user_setup.validate_token
        z2.login(self.app['acl_users'], SITE_OWNER_NAME)
        try:
            root = api.user.get_current()
            self.assertFalse(
                helpers.is_site_local_user(root), 'precondition')
            flag_before = root.getProperty('enable_two_factor_authentication')

            user_setup.validate_token = lambda *args, **kwargs: True
            try:
                form = self._build_form('123456')
                result = SetupForm.handleSubmit.func(form, None)
            finally:
                user_setup.validate_token = real_validate_token

            # State assertions first, deliberately: these are the security
            # properties, so they should be what fails if the guard regresses.
            # Asserting the return value first would short-circuit them.
            current = api.user.get_current()
            self.assertFalse(
                flag_before, 'precondition: flag must start unset, or the '
                'next assertion is vacuous')
            self.assertEqual(
                flag_before,
                current.getProperty('enable_two_factor_authentication'),
                'The 2FA flag must not be written for an account whose login '
                'cannot be intercepted.')
            # updateFields must not have minted a seed either: rendering the
            # QR calls get_or_create_secret as a side effect.
            self.assertFalse(
                current.getProperty('two_factor_authentication_secret'),
                'No seed should be stored for an unprotectable account.')

            messages = IStatusMessage(self.request).show()
            self.assertTrue(messages, 'The refusal must be reported.')
            self.assertEqual(
                ['error'], list({m.type for m in messages}),
                'The refusal must be an error, never an info/success.')

            self.assertIs(result, False)
        finally:
            z2.logout()
            login(self.portal, TEST_USER_NAME)

    def test_handleSubmit(self):
        user = api.user.get_current()
        real_validate_token = user_setup.validate_token
        real_is_status_message = user_setup.IStatusMessage

        # Scenario 1: valid_token True, nothing raises. RECOV-03 deliberate
        # behaviour change: this used to assert a redirect to
        # /@@personal-information; it now asserts no redirect at all (the
        # response renders the ten codes instead), plus the codes
        # themselves.
        user_setup.validate_token = lambda *args, **kwargs: True
        try:
            form = self._build_form('123456')
            result = SetupForm.handleSubmit.func(form, None)
        finally:
            user_setup.validate_token = real_validate_token
        self.assertIsNot(result, False)
        location = self.request.response.getHeader('location')
        self.assertIsNone(
            location,
            'RECOV-03: the success response must not redirect -- it '
            'renders the codes in the same response instead. (Was: '
            'asserted to end with /@@personal-information.)')
        self.assertTrue(
            user.getProperty('enable_two_factor_authentication', False))
        self.assertIsInstance(form.issued_recovery_codes, list)
        self.assertEqual(10, len(form.issued_recovery_codes))
        for code in form.issued_recovery_codes:
            self.assertEqual(16, len(code))
        self._clear_location()

        # Scenario 2: valid_token True, the first IStatusMessage call
        # inside the try: raises. This is the historically reported
        # failure shape and the core of the regression guard: the handler
        # must complete without raising UnboundLocalError or NameError, and
        # still redirect to the failure target.
        user_setup.validate_token = lambda *args, **kwargs: True
        user_setup.IStatusMessage = _RaisesOnFirstCall(real_is_status_message)
        try:
            form = self._build_form('123456')
            try:
                SetupForm.handleSubmit.func(form, None)
            except (UnboundLocalError, NameError):
                self.fail(
                    'handleSubmit raised UnboundLocalError/NameError on '
                    'the exception branch -- redirect_url was not bound')
        finally:
            user_setup.validate_token = real_validate_token
            user_setup.IStatusMessage = real_is_status_message
        location = self.request.response.getHeader('location')
        self.assertIsNotNone(location)
        self.assertTrue(
            location.endswith('/@@setup-two-factor-authentication'))
        self.assertIsNone(
            form.issued_recovery_codes,
            'No codes must be minted when the try: raises before reaching '
            'generate_recovery_codes.')
        self._clear_location()

        # Scenario 3: valid_token False.
        user_setup.validate_token = lambda *args, **kwargs: False
        try:
            form = self._build_form('000000')
            SetupForm.handleSubmit.func(form, None)
        finally:
            user_setup.validate_token = real_validate_token
        location = self.request.response.getHeader('location')
        self.assertIsNotNone(location)
        self.assertTrue(
            location.endswith('/@@setup-two-factor-authentication'))
        self.assertIsNone(
            form.issued_recovery_codes,
            'No codes must be minted when the token itself is rejected.')
        self._clear_location()

        # Scenario 4: empty token, real validate_token. This is the BUG-02
        # empty row: extractData() reports the required-field error and the
        # handler returns False before any redirect is attempted -- the
        # short circuit is the specified behaviour, not an oversight.
        form = self._build_form('')
        result = SetupForm.handleSubmit.func(form, None)
        self.assertFalse(result)
        self.assertIsNone(self.request.response.getHeader('location'))

        # Scenario 5: valid_token True, generate_recovery_codes itself
        # raises. Same module-attribute-rebinding technique already used
        # above for validate_token/IStatusMessage. Must land in the
        # existing except Exception: path -- no UnboundLocalError/
        # NameError, and the same failure redirect as scenarios 2 and 3.
        def _raise_instead(user):
            raise ValueError('deliberate: generate_recovery_codes failure')

        real_generate_recovery_codes = user_setup.generate_recovery_codes
        user_setup.validate_token = lambda *args, **kwargs: True
        user_setup.generate_recovery_codes = _raise_instead
        try:
            form = self._build_form('123456')
            try:
                SetupForm.handleSubmit.func(form, None)
            except (UnboundLocalError, NameError):
                self.fail(
                    'handleSubmit raised UnboundLocalError/NameError when '
                    'generate_recovery_codes itself raised -- redirect_url '
                    'was not bound')
        finally:
            user_setup.validate_token = real_validate_token
            user_setup.generate_recovery_codes = real_generate_recovery_codes
        location = self.request.response.getHeader('location')
        self.assertIsNotNone(location)
        self.assertTrue(
            location.endswith('/@@setup-two-factor-authentication'))
        self._clear_location()

    def test_recovery_codes_are_issued_once_at_enrollment(self):
        """RECOV-03: the render() half, which test_handleSubmit cannot
        reach because it calls the handler function directly rather than
        going through the wrapped view's update/render cycle. Proves both
        halves of "shown exactly once": the codes appear in the response
        that mints them, and a fresh form instance's render() shows none of
        them -- meaningful only against a *new* instance, since
        issued_recovery_codes lives on the instance, not anywhere shared.
        """
        real_validate_token = user_setup.validate_token
        user_setup.validate_token = lambda *args, **kwargs: True
        try:
            form = self._build_form('123456')
            SetupForm.handleSubmit.func(form, None)
        finally:
            user_setup.validate_token = real_validate_token
        self._clear_location()

        codes = form.issued_recovery_codes
        self.assertIsInstance(codes, list)
        self.assertEqual(10, len(codes))

        markup = form.render()
        for code in codes:
            self.assertIn(
                code, markup,
                'RECOV-03: every issued code must appear in the response '
                'that minted it.')
        self.assertIn(
            'shown only this one time', markup,
            'RECOV-03: the one-time warning must be present, so a future '
            'template edit cannot silently drop the one thing that tells '
            'the user to write the codes down.')

        fresh_form = self._build_form('')
        fresh_markup = fresh_form.render()
        for code in codes:
            self.assertNotIn(
                code, fresh_markup,
                'RECOV-03: a fresh form instance must never redisplay a '
                'previously issued code.')

    def test_recovery_codes_page_links_to_the_home_page(self):
        """UX-01: the recovery-codes page's only link goes to the site
        home page, not to the user's own profile. The expected ``href`` is
        obtained through the ``@@plone`` view's ``navigationRootUrl`` --
        the same value production resolves -- rather than a hard-coded
        ``self.portal_url``: a hard-coded path would pass vacuously on a
        portal that happens to be its own navigation root and would not
        prove the template's own expression actually resolves.
        """
        real_validate_token = user_setup.validate_token
        user_setup.validate_token = lambda *args, **kwargs: True
        try:
            form = self._build_form('123456')
            SetupForm.handleSubmit.func(form, None)
        finally:
            user_setup.validate_token = real_validate_token
        self._clear_location()

        codes = form.issued_recovery_codes
        markup = form.render()

        self.assertIn(
            'Continue to the home page', markup,
            'UX-01: the retargeted link text must be present.')
        self.assertNotIn(
            'Continue to your profile', markup,
            'UX-01: the old link text must be gone.')

        navigation_root_url = self.portal.restrictedTraverse(
            '@@plone').navigationRootUrl()
        self.assertIn(
            'href="{0}"'.format(navigation_root_url), markup,
            'The anchor must resolve to the navigation root URL returned '
            'by the @@plone view, not a hard-coded path.')
        self.assertNotIn(
            '@@personal-information', markup,
            'The retargeted link must not carry a @@personal-information '
            'suffix -- the destination is the home page itself, not a '
            'page under it.')

        # RECOV-03 guard: a future change that reintroduces a redirect on
        # the success path would blank the wrapped form and remove the
        # codes from this same markup.
        for code in codes:
            self.assertIn(
                code, markup,
                'RECOV-03 guard: the ten recovery codes must still render '
                'in the same response as the retargeted link.')

    def test_setup_form_shows_the_secret_as_selectable_text(self):
        """UX-02: the enrollment page's qr_code field description carries
        the base32 secret as selectable text beside the QR image -- the
        exact value ``get_or_create_secret`` already returns for this user,
        not a re-derivation. This is a GET-render concern reached through
        ``updateFields``, so no ``handleSubmit`` call and no token are
        needed.
        """
        form = self._build_form('')
        description = form.fields.get('qr_code').field.description

        # Read the stored seed *after* the form has been built, so the
        # comparison is against the seed updateFields() actually rendered,
        # not a competing value minted by this assertion itself.
        secret = helpers.get_or_create_secret(
            api.user.get_current(), overwrite=False)

        self.assertIn(
            secret, description,
            'The base32 secret must appear as text beside the QR code.')
        self.assertIn(
            '<img', description,
            'The QR image must still be present -- the text is added '
            'beside it, not in place of it.')
        self.assertIn(
            '<code', description,
            'The secret must be wrapped in a <code> element, so a browser '
            'gives it a select-all-in-element affordance.')

    def test_handleSubmit_refuses_a_locked_account_even_with_a_correct_code(self):
        """CR-01/T-fsp-01: the lock gate must run strictly before
        ``validate_token``, so a locked account cannot enrol -- and cannot
        mint a fresh recovery-code set -- with a currently-correct TOTP
        code. Uses a real code, not a stubbed ``validate_token``, so the
        test measures the actual gate rather than the stub.
        """
        user = api.user.get_current()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        user.setMemberProperties(mapping={
            'two_factor_authentication_locked_until': int(time.time()) + 900,
        })
        self.assertTrue(
            helpers.is_account_locked(user),
            'precondition: the account must actually be locked, or the '
            'refusal below proves nothing')
        hashes_before = user.getProperty(
            'two_factor_authentication_recovery_codes_hashes')

        form = self._build_form(correct_code)
        SetupForm.handleSubmit.func(form, None)

        current = api.user.get(username=TEST_USER_NAME)
        self.assertFalse(
            current.getProperty('enable_two_factor_authentication'),
            'A locked account must not be enrolled, even by a correct code.')
        self.assertEqual(
            hashes_before,
            current.getProperty('two_factor_authentication_recovery_codes_hashes'),
            'A locked account must not have a fresh recovery-code set '
            'minted for it.')
        self.assertIsNone(
            form.issued_recovery_codes,
            'A locked account must not be shown any recovery codes.')

    def test_handleSubmit_wrong_code_increments_the_failed_attempts_counter(self):
        """One wrong code at this form must count into the shared
        lockout counter, the same one ``token.py`` and ``reset_bar_code.py``
        already share.
        """
        user = api.user.get_current()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        wrong_code = self._wrong_code(correct_code)
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'precondition')

        form = self._build_form(wrong_code)
        SetupForm.handleSubmit.func(form, None)

        current = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            1,
            current.getProperty('two_factor_authentication_failed_attempts'),
            'One wrong code must increment the shared failed-attempts '
            'counter.')

    def test_handleSubmit_correct_code_clears_the_failed_attempts_counter(self):
        """MFA-11: a correct code at this form must clear the shared
        counter -- proven with a non-vacuity control that the submit
        itself actually succeeded, so this cannot pass by the code being
        rejected.
        """
        user = api.user.get_current()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        user.setMemberProperties(mapping={
            'two_factor_authentication_failed_attempts': 3,
        })
        self.assertEqual(
            3,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'precondition')

        form = self._build_form(correct_code)
        SetupForm.handleSubmit.func(form, None)

        current = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            0,
            current.getProperty('two_factor_authentication_failed_attempts'),
            'A correct code must clear the shared failed-attempts counter.')
        self.assertTrue(
            current.getProperty('enable_two_factor_authentication'),
            'non-vacuity control: enrolment must actually have succeeded, '
            'or the counter-clear assertion above is meaningless.')

    def test_handleSubmit_reaching_max_failed_attempts_locks_the_account(self):
        """Reaching ``max_failed_attempts`` consecutive wrong codes at this
        form must lock the account, bounded by ``lockout_duration`` -- the
        same guarantee ``token.py``/``reset_bar_code.py`` already give.
        """
        user = api.user.get_current()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        wrong_code = self._wrong_code(correct_code)
        max_failed_attempts = int(
            helpers.get_app_settings().max_failed_attempts)

        for _attempt in range(max_failed_attempts - 1):
            form = self._build_form(wrong_code)
            SetupForm.handleSubmit.func(form, None)
            self._clear_location()

        current = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            0,
            current.getProperty('two_factor_authentication_locked_until'),
            'non-vacuity control: max_failed_attempts - 1 consecutive '
            'failures must not lock the account yet')

        form = self._build_form(wrong_code)
        SetupForm.handleSubmit.func(form, None)

        current = api.user.get(username=TEST_USER_NAME)
        self.assertTrue(
            helpers.is_account_locked(current),
            'Reaching max_failed_attempts must lock the account.')
        lockout_duration = int(helpers.get_app_settings().lockout_duration)
        self.assertLessEqual(
            current.getProperty('two_factor_authentication_locked_until'),
            int(time.time()) + lockout_duration,
            'The lock must be bounded by the configured lockout_duration.')
