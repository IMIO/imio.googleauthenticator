"""
Tests for ``subscribers.redirect_pending_2fa`` and ``pas_plugin.send_2fa_
redirect`` (MFA-02, COEX-08 login-POST half). No production test file maps
1:1 here -- ``subscribers.py`` already has ``test_subscribers.py`` for its
sibling ``on_process_starting`` handler, and this module instead covers the
new cross-file contract between ``pas_plugin.py`` and ``subscribers.py`` --
a role-match rather than a strict R5 file-name match (04-PATTERNS.md).
"""
import os
import unittest2 as unittest
import urllib
import xml.dom.minidom

import transaction
from cryptography.fernet import Fernet
from ZPublisher.HTTPResponse import HTTPResponse
from zope.globalrequest import setRequest

from Products.CMFCore.utils import getToolByName

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD

import imio.googleauthenticator
from imio.googleauthenticator import helpers
from imio.googleauthenticator import pas_plugin
from imio.googleauthenticator import subscribers
from imio.googleauthenticator.helpers import get_or_create_secret
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class _EventStub(object):
    """Minimal event stub exposing only ``.request`` -- same spirit as
    test_subscribers.py's ``_StubLogger``: the smallest substitute for the
    real ``ZPublisher.pubevents.PubBeforeCommit`` object, since
    ``redirect_pending_2fa`` only ever reads ``.request`` off it.
    """

    def __init__(self, request):
        self.request = request


class TestPubBeforeCommitRedirect(unittest.TestCase, BaseTest):
    """WR-03 (see tests/test_setuphandlers.py's class docstring for the
    precedent): one test method per *requirement* rather than one per
    production function, so a failure in one requirement's assertions does
    not hide whether the others still pass.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self.pas = getToolByName(self.portal, 'acl_users')
        self.portal_url = api.portal.get().absolute_url()
        self._install()

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()

    def tearDown(self):
        # _enable_2fa() commits TEST_USER_NAME's 2FA flag and secret so a
        # subsequent Browser.open() (which starts a fresh ZPublisher
        # transaction, see _enable_2fa's docstring) can see them -- and
        # that commit survives into other test methods sharing this layer
        # (documented in test_pas_plugin.py's setUp). Undo both here,
        # committed: the flag, so TestGeneric's TEST_USER_NAME-driven views
        # are not gated behind 2FA, and the secret, whose ciphertext is
        # bound to this test's now-discarded env key below and would
        # otherwise fail every later test's decrypt_seed() with 'Ciphertext
        # failed to decrypt'.
        user = api.user.get(username=TEST_USER_NAME)
        if user is not None:
            user.setMemberProperties(mapping={
                'enable_two_factor_authentication': False,
                'two_factor_authentication_secret': '',
            })
            transaction.commit()

        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key

    def _enable_2fa(self):
        """Shared enrollment boilerplate, lifted from
        test_pas_plugin.py:157-165: log the test user in, flip the
        memberdata flag, and force a fresh secret under this test's own
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

    def test_no_body_leak_on_2fa_redirect(self):
        """MFA-02: the refusal's response body must be exactly empty and
        stay empty under a later ``setBody`` call, proved against a real
        ``ZPublisher.HTTPResponse.HTTPResponse`` -- the exact class the
        publisher uses, not a stub.
        """
        response = HTTPResponse()
        response.setBody('<html><body>SECRET-PAGE-MARKER</body></html>')
        # Non-vacuity control: if the seeding above silently failed, every
        # assertion below would pass for the wrong reason.
        self.assertIn('SECRET-PAGE-MARKER', response.body)

        request = self.layer['request']
        setRequest(request)
        try:
            user = self._enable_2fa()
            pas_plugin._mark_2fa_pending(request, user)
            request.response = response

            subscribers.redirect_pending_2fa(_EventStub(request))
        finally:
            setRequest(None)

        self.assertEqual('', response.body)
        self.assertNotIn('SECRET-PAGE-MARKER', response.body)
        self.assertEqual('0', response.getHeader('content-length'))
        self.assertEqual(302, response.status)
        self.assertIn(
            '@@google-authenticator-token', response.getHeader('Location'))

        # The lock holds: a later IPubBeforeCommit subscriber (e.g.
        # plone.transformchain) calling setBody(...) must not refill it.
        response.setBody('<html>REFILL</html>')
        self.assertEqual('', response.body)

        # Regression control for the research's mistake: a freshly built
        # HTTPResponse seeded with a body and then given setBody('') STILL
        # has that body -- recorded as an executable fact, not a comment,
        # for why production code assigns response.body directly instead.
        fresh_response = HTTPResponse()
        fresh_response.setBody('<html>original-page</html>')
        fresh_response.setBody('')
        self.assertEqual('<html>original-page</html>', fresh_response.body)

    def test_pub_before_commit_fires_on_login_post(self):
        """COEX-08 (login-POST half) and Open Question 1's settlement as
        302-to-token-form: a 2FA-enabled user's login-form POST must not
        complete a normal login. It must land on the signed
        ``@@google-authenticator-token`` URL, driven by the
        ``IPubBeforeCommit`` subscriber -- not by any ``RESPONSE`` call
        inside ``authenticateCredentials``.
        """
        self._enable_2fa()

        browser = self._get_browser()
        self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)

        self.assertIn('@@google-authenticator-token', browser.url)
        self.assertIn('auth_user=', browser.url)
        self.assertIn('signature=', browser.url)

        # Wiring: parsed with xml.dom.minidom rather than substring-matched,
        # so this also proves configure.zcml is still well-formed after
        # edit (d), and fails the suite if the registration is ever deleted.
        package_dir = os.path.dirname(imio.googleauthenticator.__file__)
        dom = xml.dom.minidom.parse(
            os.path.join(package_dir, 'configure.zcml'))
        matches = [
            element for element in dom.getElementsByTagName('subscriber')
            if element.getAttribute('for') ==
            'ZPublisher.interfaces.IPubBeforeCommit'
            and element.getAttribute('handler') ==
            '.subscribers.redirect_pending_2fa'
        ]
        self.assertEqual(1, len(matches))

    def test_request_flag_cannot_be_forged_from_the_query_string(self):
        """T-04-04: ``request.get(...)`` falls through to form data (and
        then cookies), so reading the pending signal that way would turn
        an anonymous ``?_2fa_pending=1&_2fa_user_id=<victim>`` query string
        into a validly signed token URL for an arbitrary account. Proves
        the hazard is real (``request.get`` does find the forged values),
        then proves the handler is immune to it (it reads ``request.other``
        only, which the forged query string never reaches).
        """
        request = self.layer['request']
        request.form['_2fa_pending'] = '1'
        request.form['_2fa_user_id'] = TEST_USER_NAME

        # request.other must still be clean before the handler runs --
        # asserted first, because HTTPRequest.get()'s own fallthrough
        # promotes form data into `other` as a caching side effect, and
        # calling it here (before the handler) would contaminate the very
        # channel this test proves is safe.
        self.assertIsNone(
            request.other.get(pas_plugin.REQUEST_KEY_PENDING))
        self.assertIsNone(
            request.other.get(pas_plugin.REQUEST_KEY_USER_ID))

        response = HTTPResponse()
        request.response = response

        subscribers.redirect_pending_2fa(_EventStub(request))

        self.assertEqual(200, response.status)
        self.assertIsNone(response.getHeader('Location'))
        self.assertEqual('', response.body)

        # Now prove the hazard would be real if the handler used
        # request.get(...) instead of request.other.get(...) -- run last,
        # since request.get()'s fallthrough mutates `other` as a side
        # effect and must not influence the assertions above.
        self.assertEqual('1', request.get('_2fa_pending'))
        self.assertEqual(TEST_USER_NAME, request.get('_2fa_user_id'))

    def test_no_body_leak_over_http(self):
        """MFA-02, belt-and-braces: the same emptiness Task 1's
        ``test_no_body_leak_on_2fa_redirect`` already proves against a
        direct-call ``HTTPResponse``, reproduced over a real HTTP round
        trip through ``zope.testbrowser`` 3.11.1 / ``mechanize`` 0.2.5.

        ``set_handle_redirect(False)`` and ``raiseHttpErrors = False`` are
        both needed, but only against ``Browser.open()`` --
        ``Browser.getControl(...).click()`` calls ``_clickSubmit()``
        (``zope/testbrowser/browser.py:407-424``), which re-raises any
        ``mechanize.HTTPError`` unconditionally and never consults
        ``raiseHttpErrors`` at all. Submitting the encoded POST directly
        through ``Browser.open()`` instead of via a clicked control routes
        through the code path that actually honours the switch
        (``zope/testbrowser/browser.py:233-259``).
        """
        self._enable_2fa()

        browser = self._get_browser()
        browser.mech_browser.set_handle_redirect(False)
        browser.raiseHttpErrors = False

        data = urllib.urlencode({
            '__ac_name': TEST_USER_NAME,
            '__ac_password': TEST_USER_PASSWORD,
            'submit': 'Log in',
        })
        browser.open(self.portal_url + '/login_form', data)

        self.assertTrue(browser.headers['Status'].startswith('302'))
        self.assertIn(
            '@@google-authenticator-token', browser.headers['Location'])
        self.assertEqual('', browser.contents)
