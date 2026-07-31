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
import os
import time
import unittest2 as unittest

import transaction
from cryptography.fernet import Fernet

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD

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
