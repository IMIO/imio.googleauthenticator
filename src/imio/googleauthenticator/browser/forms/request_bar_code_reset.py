"""
Request the bar code reset.
"""
from imio.googleauthenticator.helpers import get_ska_secret_key
from plone import api
from plone.directives import form
from plone.z3cform.layout import wrap_form
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from ska import RequestHelper
from ska import Signature
from smtplib import SMTPException
from z3c.form import button
from z3c.form import field
from zope.i18nmessageid import MessageFactory
from zope.schema import TextLine

import logging
import socket


logger = logging.getLogger('imio.googleauthenticator')

_ = MessageFactory('imio.googleauthenticator')


class IRequestBarCodeResetForm(form.Schema):
    """
    Interface for the request to reset the Google Authenticator bar code form.
    """
    username = TextLine(
        title=_(u'Username'),
        description=_(u'Enter your username for verification. The link code to reset the '
                      u'bar code would be sent to your email.'),
        required=True
    )


class RequestBarCodeResetForm(form.SchemaForm):
    """
    Form for request to reset to the Google Authenticator bar code form.
    """
    fields = field.Fields(IRequestBarCodeResetForm)
    ignoreContext = True
    schema = IRequestBarCodeResetForm
    label = _("Request to reset the Google Authenticator bar code")
    description = _(u"Enter your username for verification. The link code to reset the "
                    u"bar code would be sent to your email.")
    mail_text_template = ViewPageTemplateFile('templates/request_bar_code_reset_email.pt')

    @button.buttonAndHandler(_('Submit'))
    def handleSubmit(self, action):
        data, errors = self.extractData()
        if errors:
            return False

        username = data.get('username', '')

        user = api.user.get(username=username)

        reason = None
        if user:
            try:
                # Here we need to generate a token which is valid for let's say, 2 hours
                # using which it should be possible to reset the bar-code. The `signature`
                # generated should be saved in the user profile `bar_code_reset_token`.
                ska_secret_key = get_ska_secret_key(request=self.request, user=user)
                signature = Signature.generate_signature(
                    auth_user=username,
                    secret_key=ska_secret_key,
                    lifetime=7200  # 2 hours
                    )
                request_helper = RequestHelper(
                    signature_param='signature',
                    auth_user_param='auth_user',
                    valid_until_param='valid_until'
                    )

                signed_url = request_helper.signature_to_url(
                    signature=signature,
                    endpoint_url='{0}/{1}'.format(self.context.absolute_url(), '@@reset-bar-code')
                )

                # Save the `signature` value to the `bar_code_reset_token`.
                user.setMemberProperties(mapping={'bar_code_reset_token': str(signature)})

                # Now we need to send an email to user with URL in and a small explanations.
                try:
                    host = getToolByName(self, 'MailHost')

                    mail_text = self.mail_text_template(
                        member=user,
                        bar_code_reset_url=signed_url,
                        charset='utf-8'
                        )
                    mail_text = mail_text.format(bar_code_reset_url=signed_url)

                    # ``charset`` is not optional in practice: MailHost's
                    # _mungeHeaders ASCII-encodes a unicode body when it is
                    # given none (_try_encode falls back to a bare
                    # ``text.encode()``), so a single accented character
                    # anywhere in the rendered message aborts the send. The
                    # ``charset`` passed to the template above is a different
                    # argument entirely -- it only sets the Content-Type the
                    # message declares, and never reaches MailHost.
                    host.send(
                        mail_text,
                        immediate=True,
                        charset='utf-8',
                        msg_type='text/html'
                        )

                    # This success message lives inside this inner ``try:``
                    # deliberately -- it and the ``host.send(...)`` call
                    # above share the same outer ``try:``, so a send failure
                    # below must skip this call too or the caller would be
                    # told the send both failed and succeeded on the same
                    # request.
                    #
                    # Deliberately no redirect: the caller reaches this form
                    # from the token form, by which point the PAS plugin has
                    # cleared their ``__ac`` cookie, so they are anonymous.
                    # Redirecting to the portal root sent an anonymous
                    # visitor straight to the login form on any site whose
                    # root is not anonymously viewable -- the confirmation
                    # below was never read, and the bounce looked like the
                    # reset had failed. Returning without a redirect
                    # re-renders this form, which is registered
                    # ``permission="zope2.View"`` and so stays readable while
                    # anonymous, carrying the message. This matches what the
                    # ``reason is not None`` tail below already does on
                    # failure.
                    IStatusMessage(self.request).addStatusMessage(
                        _("An email with instructions on resetting your bar-code is sent successfully."),
                        'info'
                        )
                except (SMTPException, socket.error, KeyError, IndexError):
                    # KeyError/IndexError (WR-01): `mail_text.format(...)` above
                    # re-substitutes into a string that TAL has already rendered,
                    # so admin-/user-controlled text (``email_from_name``, a
                    # username, a member email) can carry a literal `{...}` that
                    # `str.format()` reads as a field reference. A malformed field
                    # (lone `{`) raises `ValueError`, already caught by the outer
                    # `except ValueError:` below -- but a well-formed, unknown one
                    # (`{oo}`, or a stray positional `{}`) raises `KeyError` or
                    # `IndexError`, which is not an `SMTPException`/`socket.error`
                    # and would otherwise escape to a bare error page for an
                    # anonymous caller. Keep these here rather than widening the
                    # outer `except ValueError:` -- they belong to the
                    # `.format()` call, not to the `host.send()` failure modes
                    # that clause exists for.
                    logger.exception("Bar-code reset request failed to send for %r", username)
                    reason = _("An unexpected error occurred.")
            except ValueError:
                logger.exception("Bar-code reset request failed for %r", username)
                reason = _("An unexpected error occurred.")
        else:
            reason = _("Invalid username.")

        if reason is not None:
            IStatusMessage(self.request).addStatusMessage(
                _("Request for bar-code reset is failed! {0}".format(reason)),
                'error'
                )

    def updateFields(self, *args, **kwargs):
        """
        """
        return super(RequestBarCodeResetForm, self).updateFields(*args, **kwargs)


# View for the ``RequestBarCodeResetForm``.
RequestBarCodeResetFormView = wrap_form(RequestBarCodeResetForm)
