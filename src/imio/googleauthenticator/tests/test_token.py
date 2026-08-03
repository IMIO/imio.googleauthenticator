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
import re
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
                'two_factor_authentication_recovery_codes_salt': '',
                'two_factor_authentication_recovery_codes_hashes': (),
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

    def test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account(self):
        """Covers 05-VERIFICATION.md gap ``missing[1]`` / 05-REVIEW.md
        CR-01, and asserts the requirement-level half of MFA-08 that
        ``test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code``
        cannot reach, because that test always holds a genuinely signed URL
        obtained through a real password login. Here the caller supplies
        nothing but a username -- no password, no ``ska`` signature, no
        ``auth_timestamp``, no code.
        """
        self._enable_2fa()
        locked_user = api.user.get(username=TEST_USER_NAME)
        locked_user.setMemberProperties(mapping={
            'two_factor_authentication_locked_until':
                int(time.time()) + 900})
        transaction.commit()

        locked_user = api.user.get(username=TEST_USER_NAME)
        self.assertTrue(
            helpers.is_account_locked(locked_user),
            'precondition: the account must actually be locked, or the '
            'rest of this test is vacuous')

        # Non-vacuity control: an enrolled account that is NOT locked.
        # Two-way equality (locked vs. nonexistent) could be satisfied by
        # an unrelated coincidence; three-way equality is what "not an
        # oracle" actually means.
        unlocked_username = 'unlocked-enrolled-user'
        unlocked_user = api.user.create(
            email='unlocked-enrolled-user@example.com',
            username=unlocked_username,
            password='Secret0123!')
        unlocked_user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(unlocked_user, overwrite=True)
        transaction.commit()

        unknown_username = 'no-such-account-at-all'
        self.assertIsNone(
            api.user.get(username=unknown_username),
            'precondition: this username must not exist')

        # ``globalstatusmessage.pt`` renders each message as
        # ``<dl class="portalMessage {type}"><dt>{Type}</dt><dd>{text}
        # </dd></dl>`` -- extracting the ``<dd>`` text is what keeps this
        # assertion from being defeated by the CSRF token and portal date
        # that differ elsewhere on the page for reasons unrelated to the
        # oracle this test is about.
        message_re = re.compile(
            r'<dl class="portalMessage error">\s*<dt>.*?</dt>\s*'
            r'<dd>(.*?)</dd>\s*</dl>', re.DOTALL)

        def _unsigned_message(username):
            # A fresh, never-``_login_browser``-ed Browser: the URL
            # carries only ``auth_user``, no ``signature`` and no
            # ``auth_timestamp``.
            browser = self._get_browser()
            browser.open(
                '{0}/@@google-authenticator-token?auth_user={1}'.format(
                    self.portal_url, username))
            self._submit_token(browser, u'000000')
            match = message_re.search(browser.contents)
            self.assertIsNotNone(
                match,
                'no status message rendered for {0!r}'.format(username))
            return match.group(1).strip()

        locked_message = _unsigned_message(TEST_USER_NAME)
        unlocked_message = _unsigned_message(unlocked_username)
        unknown_message = _unsigned_message(unknown_username)

        self.assertEqual(
            locked_message, unknown_message,
            'MFA-08: an unsigned request must not distinguish a locked '
            'account from one that does not exist')
        self.assertEqual(
            locked_message, unlocked_message,
            'MFA-08: an unsigned request must not distinguish a locked '
            'account from an unlocked, enrolled one')
        self.assertNotIn(
            'Invalid token or token expired.', locked_message,
            'the lock-branch message must never be reachable by an '
            'unsigned caller')

    def test_recovery_code_is_accepted_in_place_of_a_token_and_consumed(self):
        """RECOV-01/RECOV-02/RECOV-04 tracer: a recovery code authenticates
        exactly as a TOTP code does, through a real Browser POST, and is
        consumed on use so a replay is refused. Covers all seven
        06-01-PLAN.md ``<behavior>`` rows in one method per the project
        skill's R5 one-method-per-function rule.
        """
        user = self._enable_2fa()
        secret = helpers.get_secret(user)
        codes = helpers.generate_recovery_codes(user)
        transaction.commit()

        self.assertEqual(10, len(codes), 'precondition: ten codes minted')

        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self.assertIn('@@google-authenticator-token', browser.url)

        # Rows 1/2: the first code logs the user in and leaves nine hashes.
        self._submit_token(browser, codes[0])
        self.assertNotIn(
            '@@google-authenticator-token', browser.url,
            'RECOV-04: an unused recovery code must log the user in')
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            9,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'RECOV-04: consuming one code must remove exactly one hash')

        # Row 3: replaying the same code is refused, count unchanged.
        second_browser = self._get_browser()
        self._login_browser(
            second_browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self._submit_token(second_browser, codes[0])
        self.assertIn(
            '@@google-authenticator-token', second_browser.url,
            'RECOV-04: a consumed recovery code must be refused on replay')
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            9,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'a refused replay must not change the stored count')

        # Row 4: a still-unused code from the same set is accepted.
        self._submit_token(second_browser, codes[1])
        self.assertNotIn(
            '@@google-authenticator-token', second_browser.url,
            'a still-unused code from the same set must be accepted')
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            8,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')))

        # Row 5: a valid six-digit TOTP code still logs the user in.
        third_browser = self._get_browser()
        self._login_browser(
            third_browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        totp_code = get_totp(secret, as_string=True)
        self._submit_token(third_browser, totp_code)
        self.assertNotIn(
            '@@google-authenticator-token', third_browser.url,
            'a valid six-digit TOTP code must still log the user in')
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            8,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'a TOTP login must not touch the recovery-code hash list')

        # Row 6: shape refusals, before pbkdf2_hmac is ever reached.
        for bad in (u'', u'A', u'A' * 17, codes[2][:-1] + u'0'):
            refusal_browser = self._get_browser()
            self._login_browser(
                refusal_browser, TEST_USER_NAME, TEST_USER_PASSWORD)
            self._submit_token(refusal_browser, bad)
            self.assertIn(
                '@@google-authenticator-token', refusal_browser.url,
                'malformed input {0!r} must be refused'.format(bad))
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            8,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'malformed submissions must never consume a stored hash')

        # Row 7: a code drawn from a different user's set is refused.
        other_username = 'other-recovery-code-user'
        other_user = api.user.create(
            email='other-recovery-code-user@example.com',
            username=other_username,
            password='Secret0123!')
        other_user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(other_user, overwrite=True)
        other_codes = helpers.generate_recovery_codes(other_user)
        transaction.commit()

        cross_browser = self._get_browser()
        self._login_browser(
            cross_browser, TEST_USER_NAME, TEST_USER_PASSWORD)
        self._submit_token(cross_browser, other_codes[0])
        self.assertIn(
            '@@google-authenticator-token', cross_browser.url,
            "RECOV-04: a code from a different user's set must be refused")
        user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            8,
            len(user.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            "a cross-user code must never consume this user's hash list")

        other = api.user.get(username=other_username)
        self.assertEqual(
            10,
            len(other.getProperty(
                'two_factor_authentication_recovery_codes_hashes')),
            'a refused cross-user attempt must not touch the other '
            "user's hash list either")
