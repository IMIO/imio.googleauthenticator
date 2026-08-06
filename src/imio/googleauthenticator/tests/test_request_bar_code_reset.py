"""
Tests for the bar-code reset request form.
"""

from imio.googleauthenticator.browser.forms.request_bar_code_reset import RequestBarCodeResetForm
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import TEST_USER_NAME
from Products.MailHost.MailHost import MailBase
from Products.statusmessages.interfaces import IStatusMessage
from smtplib import SMTPRecipientsRefused

import socket
import unittest2 as unittest


class TestRequestBarCodeReset(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = api.portal.get().absolute_url()
        # Memberdata writes survive across test methods in this layer, so a
        # leftover token from a sibling test would make the control below
        # pass vacuously.
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

    def _submit_reset_request_with_failing_send(self, username, exception):
        """Raising sibling of ``_submit_reset_request``.

        Identical to that harness except that the patched ``_send`` raises
        ``exception`` instead of appending the message to a captured list --
        this drives the mail-failure path through the real form handler
        rather than the success path.
        """
        def _raise(inner_self, mfrom, mto, messageText, immediate=False):
            raise exception

        original_send = MailBase._send
        MailBase._send = _raise
        try:
            request = self.layer['request']
            request.form['form.widgets.username'] = username
            request.form['form.buttons.submit'] = u'Submit'
            form = RequestBarCodeResetForm(self.portal, request)
            form.update()
        finally:
            MailBase._send = original_send

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

    def test_successful_request_keeps_the_caller_on_the_form(self):
        """A successful reset request must not redirect to the site root.

        The caller arrives here from the token form, by which point the PAS
        plugin has cleared their ``__ac`` cookie -- they are anonymous. A
        redirect to the portal root therefore sends an anonymous visitor to the
        login form on any site whose root is not anonymously viewable, which
        reads as "the reset bounced me back to login" and hides the
        confirmation. Not redirecting -- exactly what the ``reason is not
        None`` failure branch already does -- re-renders this form, which is
        registered ``permission="zope2.View"`` and so is readable while
        anonymous, with the confirmation message on it.

        Asserted on the response's ``Location`` header rather than on the
        absence of the two source lines, so the test tracks the user-visible
        outcome and would still catch a redirect reintroduced by another route.
        """
        self.portal.manage_changeProperties(
            email_from_name='iMio', email_from_address='noreply@imio.be')
        user = api.user.get(username=TEST_USER_NAME)
        user.setMemberProperties(mapping={'email': 'cadam@imio.be'})
        request = self.layer['request']
        IStatusMessage(request).show()  # drain prior messages

        self._submit_reset_request(TEST_USER_NAME)

        self.assertIsNone(
            request.response.getHeader('Location'),
            'The handler redirected the caller away from the form; an '
            'anonymous caller lands on the login form instead of reading the '
            'confirmation.')
        messages = [m.message for m in IStatusMessage(request).show()]
        self.assertEqual(
            [u'An email with instructions on resetting your bar-code is sent '
             u'successfully.'],
            messages,
            'The caller was not told, on a page they can actually see, that '
            'the reset email was sent.')

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

    def test_a_refused_recipient_reports_in_page_not_an_error_page(self):
        """BUG-07: a mail server that refuses the recipient must report
        through this form's shared failure path, not escape as an unhandled
        exception into a framework error page.

        Asserted on the full drained message list, not with ``assertIn``,
        because a fix that widens the ``except`` without also moving the
        success message inside the inner ``try:`` would fire both messages
        on the same request (RESEARCH.md Pitfall 1) and ``assertIn`` alone
        would not catch that.
        """
        self.portal.manage_changeProperties(
            email_from_name='iMio', email_from_address='noreply@imio.be')
        user = api.user.get(username=TEST_USER_NAME)
        user.setMemberProperties(mapping={'email': 'cadam@imio.be'})
        request = self.layer['request']
        IStatusMessage(request).show()  # drain prior messages

        self._submit_reset_request_with_failing_send(
            TEST_USER_NAME,
            SMTPRecipientsRefused(
                {'cadam@imio.be': (550, 'Recipient address rejected')}))

        self.assertIsNone(
            request.response.getHeader('Location'),
            'The handler redirected the caller away from the form; an '
            'anonymous caller lands on the login form instead of reading '
            'the error message.')
        messages = [m.message for m in IStatusMessage(request).show()]
        self.assertEqual(
            [u'Request for bar-code reset is failed! An unexpected error '
             u'occurred.'],
            messages,
            'The caller was not told about the send failure on a page they '
            'can actually see, or was also told the send succeeded.')
        self.assertTrue(
            api.user.get(username=TEST_USER_NAME).getProperty(
                'bar_code_reset_token'),
            'bar_code_reset_token was rolled back on a send failure -- '
            'D-12 says it should not be.')

    def test_a_stray_curly_brace_in_the_mail_body_reports_in_page_not_a_500(self):
        """WR-01: ``mail_text.format(bar_code_reset_url=signed_url)`` re-runs
        ``.format()`` on text TAL has already rendered. A well-formed-but-
        unknown field in admin-controlled ``email_from_name`` -- e.g.
        ``iMio {Team}`` -- makes that call raise ``KeyError``, which (unlike
        a lone ``{``, already caught by the outer ``except ValueError:``) is
        not an ``SMTPException``/``socket.error`` and, without this fix,
        escapes as an unhandled exception to an anonymous caller.

        Uses the plain (non-raising) harness, not the failing-send one: the
        ``.format()`` call runs before ``host.send()`` is ever reached, so
        the exception this test exercises does not depend on the send step
        at all.
        """
        self.portal.manage_changeProperties(
            email_from_name=u'iMio {Team}', email_from_address='noreply@imio.be')
        user = api.user.get(username=TEST_USER_NAME)
        user.setMemberProperties(mapping={'email': 'cadam@imio.be'})
        request = self.layer['request']
        IStatusMessage(request).show()  # drain prior messages

        sent = self._submit_reset_request(TEST_USER_NAME)

        self.assertEqual(
            0, len(sent),
            'The mail was handed to MailHost despite the KeyError raised '
            'while formatting its body.')
        self.assertIsNone(
            request.response.getHeader('Location'),
            'The handler redirected the caller away from the form; an '
            'anonymous caller lands on the login form instead of reading '
            'the error message.')
        messages = [m.message for m in IStatusMessage(request).show()]
        self.assertEqual(
            [u'Request for bar-code reset is failed! An unexpected error '
             u'occurred.'],
            messages,
            'The caller was not told about the formatting failure on a '
            'page they can actually see, or the exception escaped '
            'unhandled.')

    def test_an_unreachable_mail_server_reports_the_same_failure(self):
        """BUG-07 (D-09): a refused connection is not an SMTP-protocol
        failure -- it raises ``socket.error``, which is not an
        ``SMTPException`` at all -- so it is not reachable through the
        first name in the catch tuple. Without this scenario the
        ``socket.error`` arm would be untested and could be silently
        narrowed later.
        """
        self.portal.manage_changeProperties(
            email_from_name='iMio', email_from_address='noreply@imio.be')
        user = api.user.get(username=TEST_USER_NAME)
        user.setMemberProperties(mapping={'email': 'cadam@imio.be'})
        request = self.layer['request']
        IStatusMessage(request).show()  # drain prior messages

        self._submit_reset_request_with_failing_send(
            TEST_USER_NAME, socket.error(111, 'Connection refused'))

        self.assertIsNone(
            request.response.getHeader('Location'),
            'The handler redirected the caller away from the form; an '
            'anonymous caller lands on the login form instead of reading '
            'the error message.')
        messages = [m.message for m in IStatusMessage(request).show()]
        self.assertEqual(
            [u'Request for bar-code reset is failed! An unexpected error '
             u'occurred.'],
            messages,
            'The caller was not told about the send failure on a page they '
            'can actually see, or was also told the send succeeded.')
