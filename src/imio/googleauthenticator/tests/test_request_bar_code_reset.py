"""
Tests for the bar-code reset request form.
"""

import unittest2 as unittest

from Products.CMFCore.utils import getToolByName
from Products.MailHost.MailHost import MailBase
from plone import api
from plone.app.testing import TEST_USER_NAME

from imio.googleauthenticator.browser.forms.request_bar_code_reset import \
    RequestBarCodeResetForm
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class TestRequestBarCodeReset(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self.portal_url = api.portal.get().absolute_url()
        self._install()
        # The email body is a skin template, so it is only traversable once
        # the portal's skin is bound to this request.
        self.portal.setupCurrentSkin(self.layer['request'])
        # Memberdata writes commit inside BaseTest._install()'s testbrowser
        # calls and survive across test methods in this layer, so a leftover
        # token from a sibling test would make the control below pass
        # vacuously.
        api.user.get(username=TEST_USER_NAME).setMemberProperties(
            mapping={'bar_code_reset_token': ''})

    def _submit_reset_request(self, username):
        """Drive the real form handler and return the messages MailHost was
        asked to deliver.

        ``MailBase._send`` is patched rather than the whole MailHost, so
        ``send()`` still runs the real ``_mungeHeaders``/``_try_encode`` --
        which is where the encoding decision under test is actually made.
        Swapping in a mock MailHost that reimplements ``send`` would let a
        broken charset argument pass unnoticed.
        """
        sent = []

        def _capture(inner_self, mfrom, mto, messageText, immediate=False):
            sent.append(messageText)

        original_send = MailBase._send
        MailBase._send = _capture
        try:
            request = self.layer['request']
            request.form['form.widgets.username'] = username
            request.form['form.buttons.submit'] = u'Submit'
            form = RequestBarCodeResetForm(self.portal, request)
            form.update()
        finally:
            MailBase._send = original_send

        return sent

    def test_reset_email_survives_a_non_ascii_sender_name(self):
        """A reset request must not die on an accented character.

        ``MailHost.send`` ASCII-encodes a unicode body when it is handed no
        ``charset`` (``_try_encode``'s bare ``text.encode()`` fallback), so
        any non-ASCII byte anywhere in the rendered message aborts the send.
        The site's ``email_from_name`` is the shortest way to inject one; in
        the field it also arrives via the translated Subject line, which
        reads "Demande de reinitialisation ..." under the fr catalogue.

        Asserted through the form, not by inspecting the send() call, so the
        test tracks the user-visible outcome rather than the fix's shape.
        """
        self.portal.manage_changeProperties(
            email_from_name=u'iMio F\xe9d\xe9ration',
            email_from_address='noreply@imio.be')
        user = api.user.get(username=TEST_USER_NAME)
        user.setMemberProperties(mapping={'email': 'cadam@imio.be'})

        sent = self._submit_reset_request(TEST_USER_NAME)

        self.assertEqual(
            1, len(sent),
            'The reset email was never handed to MailHost for delivery.')
        self.assertIn('noreply@imio.be', sent[0])

    def test_reset_request_stores_a_reset_token(self):
        """Non-vacuity control for the test above: proves the handler ran its
        success path to completion rather than bailing early for an unrelated
        reason, which would make an empty ``sent`` list ambiguous.
        """
        self.portal.manage_changeProperties(
            email_from_name='iMio', email_from_address='noreply@imio.be')
        user = api.user.get(username=TEST_USER_NAME)
        user.setMemberProperties(mapping={'email': 'cadam@imio.be'})

        self._submit_reset_request(TEST_USER_NAME)

        self.assertTrue(
            api.user.get(username=TEST_USER_NAME).getProperty(
                'bar_code_reset_token'),
            'bar_code_reset_token was not written, so the handler did not '
            'reach the send step at all.')
