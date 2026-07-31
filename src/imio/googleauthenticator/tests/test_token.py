"""
Tests for ``browser/forms/token.py::TokenForm.handleSubmit``'s lockout gate
(MFA-08 through MFA-13). Decision P5-06: named ``test_token.py`` rather than
``test_token_form.py`` (05-VALIDATION.md's original naming), matching the
skill's R5 file-to-module rule and the sibling forms' own precedent
(``test_user_setup.py``, ``test_request_bar_code_reset.py``). Cites
``tests/test_challenge.py``'s/``tests/test_setuphandlers.py``'s ``WR-03``
precedent: one test method per *requirement* rather than one per production
method, so a failure in one requirement's assertions does not hide whether
the others still pass (decision P5-07).
"""
import base64
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
from plone.testing.z2 import Browser

from imio.googleauthenticator import helpers
from imio.googleauthenticator.helpers import get_or_create_secret
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class TestTokenFormLockout(unittest.TestCase, BaseTest):
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
        # Extended from test_challenge.py's TestPubBeforeCommitRedirect.
        # tearDown: a lock or counter set by one test method must not leak
        # into the next method sharing this layer, on top of the existing
        # 2FA-flag/secret reset that test already needed.
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
        """Shared enrollment boilerplate, lifted verbatim from
        test_challenge.py's TestPubBeforeCommitRedirect._enable_2fa (itself
        lifted from test_pas_plugin.py:157-165): log the test user in, flip
        the memberdata flag, and force a fresh secret under this test's own
        setUp key. Explicit commit: a subsequent ``Browser.open()`` call
        starts a fresh ZPublisher transaction (``transactions_manager.
        begin()``, ``ZPublisher/Publish.py:124-125``), which discards any
        uncommitted change from this test method's own still-open
        transaction -- without the commit, the memberdata write is
        invisible to the plugin's own ``api.user.get()`` lookup on the
        next request.
        """
        login(self.portal, TEST_USER_NAME)
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(user, overwrite=True)
        transaction.commit()
        return user

    def _wrong_code(self, correct_code):
        """A six-digit code guaranteed to differ from ``correct_code`` --
        used instead of a single hardcoded literal so a test that also
        needs the real correct code never accidentally reuses it as its
        'wrong' fixture.
        """
        return u'000000' if correct_code != u'000000' else u'111111'

    def _submit_token(self, browser, token):
        """Submits ``token`` through a real Browser POST. ``browser`` must
        already be sitting on the signed ``@@google-authenticator-token``
        URL -- the state ``_login_browser`` leaves it in, per Phase 4's
        ``IPubBeforeCommit`` subscriber (test_challenge.py's
        ``test_pub_before_commit_fires_on_login_post``). ``TokenForm.
        action()`` posts back to that same URL, so the browser stays there
        across repeated wrong submissions.
        """
        browser.getControl(name='form.widgets.token').value = token
        browser.getControl('Verify').click()

    def test_lockout_after_five_failures(self):
        """MFA-08: five consecutive wrong codes lock the account for the
        configured duration. MFA-13 boundary: the 4th consecutive failure
        sets no lock; the 5th does. MFA-13/P5-05: the lock write zeroes the
        counter in the same call. Re-reads the property through a fresh
        ``api.user.get(username=...)`` so the assertions see committed
        state rather than this test's own in-memory object.
        """
        self._enable_2fa()

        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self.assertIn('@@google-authenticator-token', browser.url)

        for _attempt in range(4):
            self._submit_token(browser, u'000000')

        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_locked_until'),
            'non-vacuity control: the 4th consecutive failure must not '
            'lock the account, or the 5th-failure assertion below proves '
            'nothing')

        self._submit_token(browser, u'000000')

        user = api.user.get(username=TEST_USER_NAME)
        locked_until = user.getProperty(
            'two_factor_authentication_locked_until')
        self.assertGreater(
            locked_until, int(time.time()),
            'MFA-08: the 5th consecutive failure must set a future lock '
            'epoch')
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'MFA-13/P5-05: the lock write must zero the failure counter '
            'in the same call')

    def test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code(self):
        """MFA-08 oracle: while locked, a correct code and an incorrect
        code produce indistinguishable outcomes -- the lock is evaluated
        before validate_user_data/validate_token are ever consulted, so
        the response cannot be used to confirm a guess.

        Deviation from 05-VALIDATION.md's "byte-identical" wording, stated
        explicitly: whole-body byte identity is not asserted, because
        z3c.form re-renders the submitted value into its own ``token``
        input, so the two bodies differ by exactly that echo and nothing
        else. The assertion set below -- neither submission redirects
        (i.e. neither logs in), both show the identical generic message,
        and the lock epoch is unchanged by either -- is the strongest
        claim that is actually true. To prove the lock really is evaluated
        *before* the token (not merely coincidentally refusing both), the
        correct code is refused while locked and then accepted immediately
        once the lock is cleared.
        """
        user = self._enable_2fa()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        wrong_code = self._wrong_code(correct_code)

        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self.assertIn('@@google-authenticator-token', browser.url)

        for _attempt in range(5):
            self._submit_token(browser, wrong_code)

        user = api.user.get(username=TEST_USER_NAME)
        locked_until = user.getProperty(
            'two_factor_authentication_locked_until')
        self.assertGreater(
            locked_until, int(time.time()),
            'precondition: the account must be locked')

        # Correct code, while locked: refused exactly like a wrong code --
        # no redirect (no login granted).
        self._submit_token(browser, correct_code)
        self.assertIn(
            '@@google-authenticator-token', browser.url,
            'MFA-08: a correct code must not log a locked account in')
        self.assertIn(
            'Invalid token or token expired.', browser.contents)
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            locked_until,
            user.getProperty('two_factor_authentication_locked_until'),
            'a refused submission while locked must not change the lock '
            'epoch')

        # Wrong code, while locked: the same outcome.
        self._submit_token(browser, wrong_code)
        self.assertIn('@@google-authenticator-token', browser.url)
        self.assertIn(
            'Invalid token or token expired.', browser.contents)
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            locked_until,
            user.getProperty('two_factor_authentication_locked_until'))

        # Prove the lock really gates the correct code rather than luck:
        # clear it directly and submit the identical correct code again.
        user.setMemberProperties(
            mapping={'two_factor_authentication_locked_until': 0})
        transaction.commit()
        self._submit_token(browser, correct_code)
        self.assertNotIn(
            '@@google-authenticator-token', browser.url,
            'the same correct code must succeed once the lock is cleared')

    def test_lockout_expires_without_admin_action(self):
        """MFA-09: the lock releases with no administrator action once the
        stored epoch passes -- the stored value is a plain int epoch, so a
        past value is the entire fixture. Nothing sleeps and no clock is
        monkeypatched. Asserts the boundary in both directions directly
        against the helper: equal to now is NOT locked; one second ahead
        IS locked.
        """
        user = self._enable_2fa()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        wrong_code = self._wrong_code(correct_code)

        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        for _attempt in range(5):
            self._submit_token(browser, wrong_code)

        user = api.user.get(username=TEST_USER_NAME)
        self.assertGreater(
            user.getProperty('two_factor_authentication_locked_until'),
            int(time.time()), 'precondition: the account must be locked')

        user.setMemberProperties(mapping={
            'two_factor_authentication_locked_until': int(time.time())})
        self.assertFalse(
            helpers.is_account_locked(user),
            'MFA-13 adjacency: equal to now must NOT be locked')

        user.setMemberProperties(mapping={
            'two_factor_authentication_locked_until': int(time.time()) + 1})
        self.assertTrue(
            helpers.is_account_locked(user),
            'MFA-13 adjacency: one second ahead of now must be locked')

        user.setMemberProperties(mapping={
            'two_factor_authentication_locked_until': int(time.time()) - 1})
        transaction.commit()

        self._submit_token(browser, correct_code)
        self.assertNotIn(
            '@@google-authenticator-token', browser.url,
            'MFA-09: a lock whose epoch has passed must release with no '
            'administrator action')

    def test_successful_second_factor_resets_failed_attempts(self):
        """MFA-11: a successful second factor sets the failure counter and
        the lock epoch back to 0 in the same write. Also proves the reset
        really cleared the run, rather than the assertion reading a stale
        object: a fresh wrong code submitted afterwards reads back 1, not
        5.
        """
        user = self._enable_2fa()
        secret = helpers.get_secret(user)
        correct_code = get_totp(secret, as_string=True)
        wrong_code = self._wrong_code(correct_code)

        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)

        for _attempt in range(4):
            self._submit_token(browser, wrong_code)

        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            4,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'precondition: four consecutive failures must be recorded')

        self._submit_token(browser, correct_code)
        self.assertNotIn(
            '@@google-authenticator-token', browser.url,
            'MFA-11 precondition: the correct code must actually log in')

        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'MFA-11: a successful second factor must reset the counter')
        self.assertEqual(
            0,
            user.getProperty('two_factor_authentication_locked_until'),
            'MFA-11: a successful second factor must reset the lock')

        # A fresh session, since the first is now logged in: one more
        # wrong code must read back 1, not 5.
        second_browser = self._get_browser()
        self._login_browser(
            second_browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self._submit_token(second_browser, wrong_code)

        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            1,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'MFA-11: the reset must actually clear the run, not just the '
            'assertion above reading a stale object')

    def test_failed_attempt_counter_survives_unauthorized_request(self):
        """MFA-12: the failure counter is still readable after a request
        sequence that begins with an Unauthorized-ending hit, proving the
        write happened on a committing path and not one that
        ``transaction.abort()`` discarded. Per 05-VALIDATION.md's
        resolution of Open Question 2 -- a direct ``handleSubmit()`` call
        never reaches ``transactions_manager.commit()`` and cannot prove
        this. First request follows test_challenge.py's
        ``test_challenge_fires_on_unauthorized`` idiom (Basic Auth against
        a protected resource, redirects not auto-followed); second request
        is a bad-token POST to the signed URL taken from the first
        response's ``Location`` header.
        """
        self._enable_2fa()
        protected_url = self.portal_url + '/@@personal-information'

        # Non-vacuity control, lifted from test_challenge.py: prove the
        # URL really is protected before trusting the assertions below.
        anon_browser = Browser(self.app)
        anon_browser.open(protected_url)
        self.assertIn('require_login', anon_browser.url)

        credentials = base64.b64encode(
            '%s:%s' % (TEST_USER_NAME, TEST_USER_PASSWORD))
        browser = Browser(self.app)
        browser.addHeader('Authorization', 'Basic %s' % credentials)
        browser.mech_browser.set_handle_redirect(False)
        browser.raiseHttpErrors = False
        browser.open(protected_url)

        self.assertEqual(
            '302 Moved Temporarily', browser.headers.get('Status'))
        location = browser.headers.get('Location')
        self.assertIn('@@google-authenticator-token', location)

        # Second request: a bad-token POST to the signed URL above.
        # ``Location`` is relative to the portal root here (the redirect
        # is built from ``self.context.absolute_url()``), so it must be
        # resolved against ``self.portal_url`` before a fresh Browser --
        # which is "not viewing any document" yet -- can open it.
        second_browser = self._get_browser()
        second_browser.open('{0}/{1}'.format(self.portal_url, location))
        self._submit_token(second_browser, u'000000')

        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            1,
            user.getProperty('two_factor_authentication_failed_attempts'),
            'MFA-12: the counter must be readable after a request '
            'sequence that began in Unauthorized')
