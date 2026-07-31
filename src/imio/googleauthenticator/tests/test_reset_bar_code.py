"""
Tests for ``browser/forms/reset_bar_code.py``'s lockout gate (MFA-08 reset
path, MFA-11). This module is the reset-form counterpart to the existing
``test_request_bar_code_reset.py``, which covers the *request* form (the one
that emails a reset link) rather than this one (the one that actually
consumes a token and a signature to reset the bar code).

Follows the ``WR-03``/decision P5-07 precedent recorded in
``tests/test_challenge.py``/``tests/test_token.py``: one test method per
requirement rather than one per production method, so a failure in one
requirement's assertions does not hide whether the others still pass. This
module has a single requirement -- the reset path shares the token form's
lockout counter with no bypass -- so it is proven as a single ordered
sequence of assertions in one method rather than split artificially.
"""
import os
import time
import unittest2 as unittest

import transaction
from cryptography.fernet import Fernet
from onetimepass import get_totp

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD

from imio.googleauthenticator import helpers
from imio.googleauthenticator.helpers import get_or_create_secret
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class TestResetBarCodeLockout(unittest.TestCase, BaseTest):
    """See this module's docstring for the WR-03/P5-07 precedent this class
    follows.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = api.portal.get().absolute_url()
        self._install()

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()

    def tearDown(self):
        # A lock or counter set by one test method must not leak into a
        # later class sharing this layer (same discipline as
        # test_token.py::TestTokenFormLockout.tearDown).
        user = api.user.get(username=TEST_USER_NAME)
        if user is not None:
            user.setMemberProperties(mapping={
                'enable_two_factor_authentication': False,
                'two_factor_authentication_secret': '',
                'two_factor_authentication_failed_attempts': 0,
                'two_factor_authentication_locked_until': 0,
                'two_factor_authentication_last_interval': 0,
            })
            transaction.commit()

        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key

    def _enable_2fa(self):
        """Shared enrollment boilerplate, the same shape as
        test_token.py::TestTokenFormLockout._enable_2fa.
        """
        login(self.portal, TEST_USER_NAME)
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(user, overwrite=True)
        transaction.commit()
        return user

    def _wrong_code(self, correct_code):
        return u'000000' if correct_code != u'000000' else u'111111'

    def _submit(self, browser, token):
        """Submits ``token`` through a real Browser POST. ``browser`` must
        already be sitting on a form carrying a ``form.widgets.token``
        control and a ``Verify`` button -- true of both the reset form and
        the login token form, since both are the same z3c.form shape.
        """
        browser.getControl(name='form.widgets.token').value = token
        browser.getControl('Verify').click()

    def test_reset_bar_code_lockout_after_five_failures(self):
        """MFA-08 (reset path): five anonymous wrong codes at
        ``@@reset-bar-code`` lock the account, and that lock has no
        bypass -- it also refuses a correct code at the login token form
        (one shared counter, one shared lock). MFA-11: a correct code
        clears the counter and the lock even when the bar-code-reset
        signature then fails. T-05-08/P5-13: the lock this anonymous path
        can cause is bounded by ``lockout_duration`` and clears itself.
        """
        user = self._enable_2fa()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        wrong_code = self._wrong_code(correct_code)

        reset_url = '{0}/@@reset-bar-code?auth_user={1}'.format(
            self.portal_url, TEST_USER_NAME)

        # Step 1: non-vacuity control for the whole plan's rationale. An
        # anonymous GET naming the enrolled test user must render the form,
        # not Unauthorized and not a login redirect -- with no signature
        # supplied at all, reaching the token check is precisely the
        # defect being metered. If this ever stops being true, the oracle
        # is closed by permissions and the rest of this test measures
        # nothing.
        browser = self._get_browser()
        browser.open(reset_url)
        self.assertIn('reset-bar-code', browser.url)
        self.assertNotIn('login_form', browser.url)
        # Proves the form really rendered its Verify button rather than an
        # error page that happens to still say "reset-bar-code" in the URL.
        browser.getControl('Verify')

        # Step 3: five wrong six-digit codes, anonymous, no signature.
        for _attempt in range(4):
            self._submit(browser, wrong_code)

        # Step 4 (4th submission control): the account must not be locked
        # yet, or the 5th-submission assertion below proves nothing.
        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            0,
            refetched_user.getProperty(
                'two_factor_authentication_locked_until'),
            'non-vacuity control: the 4th consecutive failure must not '
            'lock the account')

        self._submit(browser, wrong_code)

        # Step 4: the 5th consecutive failure locks the account.
        refetched_user = api.user.get(username=TEST_USER_NAME)
        locked_until = refetched_user.getProperty(
            'two_factor_authentication_locked_until')
        self.assertGreater(
            locked_until, int(time.time()),
            'MFA-08: the 5th consecutive wrong code at @@reset-bar-code '
            'must lock the account')

        # Step 5: the bypass assertion, and the point of the whole plan.
        # With the lock set through the reset form, a *correct* code is
        # refused at the login token form too -- one counter, one lock,
        # no second budget of attempts.
        login_browser = self._get_browser()
        self._login_browser(
            login_browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self.assertIn(
            '@@google-authenticator-token', login_browser.url,
            'precondition: the login must reach the token form')
        self._submit(login_browser, correct_code)
        self.assertIn(
            '@@google-authenticator-token', login_browser.url,
            'MFA-08: a correct code must not log in while the lock set '
            'through @@reset-bar-code holds -- there must be no separate '
            'attempt budget on the login path')
        self.assertIn(
            'Invalid token or token expired.', login_browser.contents)

        # Step 6: the bound on the accepted DoS (T-05-08). The stored
        # epoch is never further ahead than lockout_duration seconds.
        lockout_duration = int(helpers.get_app_settings().lockout_duration)
        self.assertLessEqual(
            locked_until, int(time.time()) + lockout_duration,
            'T-05-08: the lock an anonymous party can cause must be '
            'bounded by the configured lockout_duration')

        # Restoring service needs no administrator action: writing the
        # stored epoch to the past is the whole fixture (same discipline
        # as test_token.py::test_lockout_expires_without_admin_action).
        refetched_user.setMemberProperties(mapping={
            'two_factor_authentication_locked_until': int(time.time()) - 1})
        transaction.commit()
        self.assertFalse(
            helpers.is_account_locked(refetched_user),
            'T-05-08/P5-13: a past epoch must clear the lock with no '
            'administrator action')

        # Step 2/MFA-11: a correct code at @@reset-bar-code clears the
        # counter and the lock, even though no valid signature is supplied
        # here, so the bar-code-reset-token comparison that follows fails
        # -- the second factor still succeeded, which is what the counter
        # measures (decision P5-14).
        second_browser = self._get_browser()
        second_browser.open(reset_url)
        self._submit(second_browser, correct_code)
        self.assertIn(
            'Invalid bar-code reset token', second_browser.contents,
            'precondition: no signature was supplied, so the reset '
            'itself must still fail')

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            0,
            refetched_user.getProperty(
                'two_factor_authentication_failed_attempts'),
            'MFA-11: a correct code must clear the failure counter even '
            'when the bar-code-reset signature check then fails')
        self.assertEqual(
            0,
            refetched_user.getProperty(
                'two_factor_authentication_locked_until'),
            'MFA-11: a correct code must clear the lock even when the '
            'bar-code-reset signature check then fails')
