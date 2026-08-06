"""
User setup.
"""

from imio.googleauthenticator.helpers import drop_login_failed_msg
from imio.googleauthenticator.helpers import generate_recovery_codes
from imio.googleauthenticator.helpers import get_token_description
from imio.googleauthenticator.helpers import is_account_locked
from imio.googleauthenticator.helpers import is_site_local_user
from imio.googleauthenticator.helpers import mark_enrollment_completed
from imio.googleauthenticator.helpers import register_failed_second_factor
from imio.googleauthenticator.helpers import reset_failed_second_factor
from imio.googleauthenticator.helpers import validate_token
from imio.googleauthenticator.helpers import validate_user_data
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

    def action(self):
        """Query-string-preserving form action (D-16, copied from
        token.py:57-61). Without it z3c.form posts back to the bare URL
        and the signed ``auth_user``/``signature`` pair carried on this
        page's own URL is dropped on submit -- a redirected, not-yet-
        enrolled user's token submission would then arrive unidentifiable,
        and the failure would look like a working page that 401s the
        moment "Verify" is pressed.
        """
        return "{0}?{1}".format(
            self.request.getURL(),
            self.request.get('QUERY_STRING', '')
        )

    def _resolve_signed_user(self):
        """
        Resolves who this request is for, and whether that resolution came
        from a valid ``ska`` signature rather than a live session.

        Built from ``token.py:107-122`` (D-16) -- the one existing
        mechanism in this codebase for authenticating a request with no
        session -- rather than a second, unreviewed one:

        - ``auth_user`` empty: this is an ordinary visit with no signed
          enrollment redirect in play. Resolve the current user, unless
          there is none at all (a plain anonymous visitor who never
          attempted a signature). This is the branch every pre-existing
          authenticated test in this module takes, unchanged.
        - ``auth_user`` present but unresolvable (``api.user.get`` returns
          ``None``): refused. An ``auth_user`` naming an account that does
          not exist gets no QR and no token evaluation.
        - ``auth_user`` present and resolvable, but
          ``validate_user_data``'s signature check fails: refused. T-10-01:
          the signing key includes the resolved user's own seed, so a
          signature minted for one account cannot validate for another.

        The last two refusals collapse to the same return value on
        purpose -- this method's caller cannot distinguish "wrong
        account" from "bad signature" from the return value alone, only
        from whether ``auth_user`` was present at all.

        :return tuple: ``(user, signed)`` -- ``user`` is a
            ``Products.PlonePAS.tools.memberdata`` instance or ``None``;
            ``signed`` is ``True`` only when ``user`` was resolved through
            a validated ``ska`` signature.
        """
        username = self.request.get('auth_user', '')

        if not username:
            if bool(api.user.is_anonymous()) is True:
                return None, False
            return api.user.get_current(), False

        user = api.user.get(username=username)
        if user is None:
            return None, False

        validation_result = validate_user_data(
            request=self.request, user=user)
        if not validation_result.result:
            return None, False

        return user, True

    @button.buttonAndHandler(_('Verify'))
    def handleSubmit(self, action):
        user, signed = self._resolve_signed_user()
        if user is None:
            if self.request.get('auth_user', ''):
                # D-16: a signed attempt was made (auth_user was present)
                # but did not resolve to a real account or did not
                # validate -- tell the caller their data is invalid,
                # mirroring token.py:118-122. D-12: must not state or
                # imply anything about which account, if any, exists.
                IStatusMessage(self.request).addStatusMessage(
                    _(u"Invalid data. The enrollment link is invalid or "
                      u"has expired."),
                    'error')
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
        if not is_site_local_user(user):
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

        # CR-01/MFA-08/MFA-11: the third of this package's three
        # validate_token callers to share the lockout counter -- see
        # reset_bar_code.py::handleSubmit for the same is_account_locked /
        # register_failed_second_factor / reset_failed_second_factor
        # pattern. DELIBERATE DEVIATION from reset_bar_code.py's locked
        # arm: there, the locked arm adds its message and returns
        # immediately, which is equivalent to falling through because that
        # handler's failure tail is message-only. Here the wrong-code arm
        # also binds redirect_url and redirects to this same setup form, so
        # an early return in the locked arm would leave the locked response
        # at 200-with-no-Location while a wrong code gets a 302 --
        # reinstating exactly the message-plus-response oracle 05-05
        # closed on the reset form. The locked arm must therefore reach the
        # shared "if reason is not None:" tail below and produce the same
        # message and the same redirect target as a wrong code. This arm
        # and the wrong-code arm below must be changed together, or the
        # lock becomes readable from the response alone (MFA-08).
        reason = None
        if is_account_locked(user):
            reason = _("Invalid token or token expired.")
        elif validate_token(token, user=user):
            # The second factor succeeded, so the counter/lock reset
            # happens here -- before the try: block -- rather than inside
            # it (P5-14): a PropertyValueError from a mis-declared property
            # must surface as a 500, not be caught by the except Exception
            # below and reported as an unexpected error.
            reset_failed_second_factor(user)
            try:
                # Set the ``enable_two_factor_authentication`` to True
                user.setMemberProperties(mapping={'enable_two_factor_authentication': True})

                # D-17: the only writer of this property anywhere in the
                # package. Must run on every success path -- not only the
                # signed one -- or a self-enroller whose enrollment-
                # completion flag stayed False would be routed straight
                # back to this page at their next login, forever.
                mark_enrollment_completed(user)

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

                if signed:
                    # D-16: this request arrived with no session --
                    # send_2fa_redirect cleared __ac before redirecting
                    # here. The call below establishes one now that the
                    # token has been verified, the same call
                    # token.py:152-153 makes. Do not add a redirect after
                    # it: RECOV-03 depends on this response staying a 200
                    # so the codes render. username must stay unicode,
                    # not str()-coerced (WR-03: UnicodeEncodeError on any
                    # non-ASCII character).
                    username = self.request.get('auth_user', '')
                    self.context.acl_users.session._setupSession(
                        username, self.context.REQUEST.RESPONSE)

                redirect_url = None
            except Exception:
                logger.exception("Two-step verification setup failed")
                reason = _("An unexpected error occurred.")
        else:
            register_failed_second_factor(user)
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

        D-16: restructured so ``super().updateFields(...)`` runs on
        *every* path. Before this phase it sat inside the
        ``is_anonymous() is False`` guard below, so an anonymous request
        got no field update at all -- half of why this page was unusable
        for a user the login path had just redirected here with a signed,
        sessionless request (the other half was the barcode gating itself,
        also fixed below).
        """
        user, signed = self._resolve_signed_user()

        if signed:
            # D-16: authenticateCredentials wiped the shared credentials
            # dict before redirecting here (to stop a later PAS plugin
            # logging the user in before the token is checked), which
            # queues a spurious "Login failed" status message -- drop it,
            # the same way token.py's updateFields does, or it renders
            # above the QR code on a request that never actually failed
            # to log in.
            #
            # Deliberate deviation from token.py: do NOT also clear the
            # __ac cookie here. send_2fa_redirect already cleared it
            # before this request was ever issued, and this same code
            # path also runs for ordinary authenticated self-service
            # enrollment -- clearing it unconditionally here would log
            # that user out mid-enrollment.
            drop_login_failed_msg(self.request)

        if user is not None:
            # Adding a proper description (with bar code image)
            barcode_field = self.fields.get('qr_code')
            if barcode_field:
                if is_site_local_user(user):
                    barcode_field.field.description = _(get_token_description(user))
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
