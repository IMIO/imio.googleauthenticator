"""
User setup.
"""

from imio.googleauthenticator.helpers import generate_recovery_codes
from imio.googleauthenticator.helpers import get_token_description
from imio.googleauthenticator.helpers import is_site_local_user
from imio.googleauthenticator.helpers import validate_token
from plone import api
from plone.directives import form
from plone.z3cform.layout import wrap_form
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from z3c.form import button
from z3c.form import field
from zope.i18nmessageid import MessageFactory
from zope.schema import TextLine

import logging


logger = logging.getLogger('imio.googleauthenticator')

_ = MessageFactory('imio.googleauthenticator')


class ISetupForm(form.Schema):
    """
    Interface for the Google Authenticator setup form.
    """

    # The qr_code field isn't used as a input field, instead it is used to show the QR code
    qr_code = TextLine(
        title=_(u'1. Scan this QR code with the Google Authenticator app'),
        description=u'This description is replaced with the QR code.',
        required=False
    )
    token = TextLine(
        title=_(u'2. Enter the verification code to activate two-step verification'),
        description=_(u'The Google Authenticator app generates a verification code, '
                      u'enter the code below'),
        required=True
    )


class SetupForm(form.SchemaForm):
    """
    Form for the Google Authenticator setup.
    """
    fields = field.Fields(ISetupForm)
    ignoreContext = True
    schema = ISetupForm
    label = _("Setup two-step verification")
    description = _(u"To setup two-step verification you need to install the Google"
                    u"Authenticator app on your phone. This app is available for "
                    u"Android, iOS and BlackBerry devices.")
    # Not underscore-prefixed: Zope TAL path traversal refuses names
    # beginning with an underscore, so ``view/_recovery_codes`` would be
    # unreachable from recovery_codes.pt. Holds plaintext for the lifetime
    # of one request only -- never assigned to anything persistent.
    issued_recovery_codes = None
    recovery_codes_template = ViewPageTemplateFile('recovery_codes.pt')

    @button.buttonAndHandler(_('Verify'))
    def handleSubmit(self, action):
        if bool(api.user.is_anonymous()) is True:
            self.request.response.setStatus(401, _('Forbidden for anonymous'), True)
            return False

        data, errors = self.extractData()
        if errors:
            return False

        # T-03-23: refuse an account this plugin cannot gate. Enrolling a
        # Zope-root account and reporting success would claim a second factor
        # that is never demanded at login -- a false report of a security
        # control's state, the same class as T-03-21's zero-user bulk
        # "Changes saved.". Checked before the token is validated, so no
        # enrolment state is written on this path at all.
        if not is_site_local_user():
            IStatusMessage(self.request).addStatusMessage(
                _(u"Two-step verification cannot be enabled for this account: "
                  u"it is not defined in this Plone site, so its logins are "
                  u"authenticated above the site and cannot be intercepted. "
                  u"Use an account created inside the site."),
                'error'
                )
            self.request.response.redirect(
                "{0}/@@personal-information".format(
                    self.context.absolute_url()))
            return False

        token = data.get('token', '')

        valid_token = validate_token(token)

        # self.context.plone_log(valid_token)
        # self.context.plone_log(token)

        reason = None
        if valid_token:
            try:
                # Set the ``enable_two_factor_authentication`` to True
                user = api.user.get_current()
                user.setMemberProperties(mapping={'enable_two_factor_authentication': True})

                IStatusMessage(self.request).addStatusMessage(
                    _("Two-step verification is successfully enabled for your account."),
                    'info'
                    )
                # RECOV-03: mint the recovery codes only after the success
                # message above has been queued, so the historical
                # exception-branch scenario (a failure inside this try:)
                # mints no codes at all -- a set generated but never shown
                # is a set the user never received while their stored
                # hashes were already replaced. redirect_url is set to
                # None *after* this call: if generate_recovery_codes raises,
                # redirect_url stays unbound here and the "if reason is not
                # None:" fallback below binds it, preserving BUG-02's
                # "bound on every reachable path" property unchanged.
                self.issued_recovery_codes = generate_recovery_codes(user)
                redirect_url = None
            except Exception:
                logger.exception("Two-step verification setup failed")
                reason = _("An unexpected error occurred.")
        else:
            reason = _("Invalid token or token expired.")

        if reason is not None:
            IStatusMessage(self.request).addStatusMessage(_("Setup failed! {0}".format(reason)), 'error')
            redirect_url = "{0}/@@setup-two-factor-authentication".format(self.context.absolute_url())

        # TODO: Is there a nicer way of resolving the "@@setup-two-factor-authentication" URL?

        # RECOV-03: redirect_url is None only on the success path above,
        # deliberately -- skipping the redirect on that one path is the
        # entire mechanism the one-time code display depends on.
        # plone.z3cform 0.8.1's FormWrapper.update() (site-packages/
        # plone/z3cform/layout.py, lines 39-60 of the pinned egg) blanks
        # the wrapped form's contents and returns early only when
        # self.request.response.getStatus() is 302 or 303; leaving the
        # response at its default 200 here is sufficient for render() to
        # run normally in this same response. Do not "tidy" this back into
        # an unconditional redirect.
        if redirect_url is not None:
            self.request.response.redirect(redirect_url)

    def render(self):
        """RECOV-03: the one-time display. If handleSubmit just minted a
        fresh set of recovery codes, render those instead of the ordinary
        setup form -- this is the only response in which they exist in
        plaintext anywhere. Any other render() call (a fresh form, a
        second GET) has issued_recovery_codes at its class default of
        None, so the ordinary form renders and nothing is redisplayed.
        """
        if self.issued_recovery_codes:
            return self.recovery_codes_template()
        return super(SetupForm, self).render()

    def updateFields(self, *args, **kwargs):
        """
        Bar code image is applied here.
        """
        if bool(api.user.is_anonymous()) is False:

            # Adding a proper description (with bar code image)
            barcode_field = self.fields.get('qr_code')
            if barcode_field:
                if is_site_local_user():
                    barcode_field.field.description = _(get_token_description())
                else:
                    # T-03-23: show no QR for an account this plugin cannot
                    # gate. Beyond the misleading offer, get_token_description
                    # mints and stores a seed as a side effect, so rendering
                    # it here would leave enrolment state behind for an
                    # account that can never use it.
                    barcode_field.field.description = _(
                        u"This account is not defined in this Plone site, so "
                        u"its logins are authenticated above the site and "
                        u"cannot be intercepted. Two-step verification is "
                        u"unavailable for it.")

            return super(SetupForm, self).updateFields(*args, **kwargs)


# View for the ``SetupForm``.
SetupFormView = wrap_form(SetupForm)
