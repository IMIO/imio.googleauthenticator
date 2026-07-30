import os
import unittest2 as unittest

from cryptography.fernet import Fernet

from zope.globalrequest import setRequest

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME

from imio.googleauthenticator import helpers
from imio.googleauthenticator.browser.forms import user_setup
from imio.googleauthenticator.browser.forms.user_setup import SetupForm
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


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
       try: at "redirect_url = ...@@personal-information", reason stays
       None, so the "if reason is not None:" fallback is skipped.
    2. valid_token True, an exception raised inside the try: (here, from
       the first IStatusMessage(self.request) call): reason is set to
       "An unexpected error occurred." without reaching the redirect_url
       assignment inside the try; the "if reason is not None:" block then
       binds redirect_url to "...@@setup-two-factor-authentication".
    3. valid_token False: reason is set directly, same fallback binds
       redirect_url to the same "...@@setup-two-factor-authentication"
       target as scenario 2.
    redirect_url is bound on all three reachable paths -- there is no
    fourth branch that skips both assignments.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self._install()
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
        # #2: BaseTest._install() commits inside a real testbrowser, so a
        # ciphertext written by an earlier test method under a different
        # key survives into this one. updateFields() -> get_token_
        # description() -> get_or_create_secret(overwrite=False) would try
        # to decrypt that stale ciphertext under this test's fresh key and
        # raise. Force a fresh secret under the current key up front.
        helpers.get_or_create_secret(api.user.get_current(), overwrite=True)

    def tearDown(self):
        setRequest(None)
        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key

    def _clear_location(self):
        if 'location' in self.request.response.headers:
            del self.request.response.headers['location']

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
        form = SetupForm(self.portal, self.request)
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

    def test_handleSubmit(self):
        user = api.user.get_current()
        real_validate_token = user_setup.validate_token
        real_is_status_message = user_setup.IStatusMessage

        # Scenario 1: valid_token True, nothing raises.
        user_setup.validate_token = lambda *args, **kwargs: True
        try:
            form = self._build_form('123456')
            result = SetupForm.handleSubmit.func(form, None)
        finally:
            user_setup.validate_token = real_validate_token
        self.assertIsNot(result, False)
        location = self.request.response.getHeader('location')
        self.assertIsNotNone(location)
        self.assertTrue(location.endswith('/@@personal-information'))
        self.assertTrue(
            user.getProperty('enable_two_factor_authentication', False))
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
        self._clear_location()

        # Scenario 4: empty token, real validate_token. This is the BUG-02
        # empty row: extractData() reports the required-field error and the
        # handler returns False before any redirect is attempted -- the
        # short circuit is the specified behaviour, not an oversight.
        form = self._build_form('')
        result = SetupForm.handleSubmit.func(form, None)
        self.assertFalse(result)
        self.assertIsNone(self.request.response.getHeader('location'))
