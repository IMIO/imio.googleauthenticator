from imio.googleauthenticator.helpers import is_two_factor_authentication_globally_enabled
from plone import api
from Products.Five import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from zope.i18nmessageid import MessageFactory


_ = MessageFactory('imio.googleauthenticator')


class DisableTwoFactorAuthentication(BrowserView):
    """
    Disabling the two-step verification.
    """
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def disable(self):
        """
        Disable the two-step verification for the user and redirect back to the `@@personal-information`.
        """
        if bool(api.user.is_anonymous()) is True:
            self.request.response.setStatus(401, _('Forbidden for anonymous'), True)
            return None

        # D-08/D-09/MFA-16: this is the actual security control, not the
        # hidden menu link. Phase 9 (BUG-08) established that a link that
        # acts on the wrong account cannot be fixed by hiding it, because a
        # bookmarked or hand-typed URL still works -- same reasoning here:
        # hiding this view's menu link is cosmetic, refusing here is the
        # control. Must run after the anonymous guard above (an anonymous
        # caller must keep getting 401) and before any read of the
        # caller's own member data (an unenrolled user must be refused
        # too, not silently treated as a no-op).
        if is_two_factor_authentication_globally_enabled():
            IStatusMessage(self.request).addStatusMessage(
                _("This site requires a second factor for every account. "
                  "Ask your site administrator to turn off global "
                  "enforcement before you disable your own."),
                'error'
                )
            redirect_url = "{0}/@@personal-information".format(self.context.absolute_url())
            self.request.response.redirect(redirect_url)
            return None

        user = api.user.get_current()
        user.setMemberProperties(
            mapping={
                'enable_two_factor_authentication': False,
                'two_factor_authentication_secret': '',
                'bar_code_reset_token': '',
                # CR-01: routing (pas_plugin.authenticateCredentials) uses
                # this flag alone to decide enrollment vs. code-entry.
                # Leaving it True here means a later re-enable (single,
                # bulk, or profile-reapply) sends the account straight to
                # the code-entry page for a secret it never saw.
                'two_factor_authentication_enrolled': False,
                }
            )

        IStatusMessage(self.request).addStatusMessage(
            _("You have successfully disabled the two-step verification for your account."),
            'info'
            )
        redirect_url = "{0}/@@personal-information".format(self.context.absolute_url())
        self.request.response.redirect(redirect_url)
