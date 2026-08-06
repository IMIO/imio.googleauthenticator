from imio.googleauthenticator.helpers import disable_two_factor_authentication_for_users
from imio.googleauthenticator.helpers import is_two_factor_authentication_globally_enabled
from plone import api
from Products.Five import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from zope.i18nmessageid import MessageFactory


_ = MessageFactory('imio.googleauthenticator')


class DisableTwoFactorAuthenticationForAllUsers(BrowserView):
    """
    Disable the two-step verification for all users.
    """
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def index(self):
        """
        Disble the two-step verification for the user and redirect back to the `@@google-authenticator-settings`.
        """
        # D-18/MFA-16: operator decision, 2026-08-06. This is a deliberate
        # widening of MFA-16 beyond its literal wording (which speaks only
        # of a user's own second factor) -- an operator-approved one: a
        # refusal that stops one user turning their own second factor off
        # while leaving a one-click "disable for everyone" reachable makes
        # the enforcement incoherent. The documented operator recovery
        # path is unchanged and intact: turn `globally_enabled` off in the
        # control panel, then use this view -- an administrator is never
        # trapped by their own enforcement setting.
        if is_two_factor_authentication_globally_enabled():
            IStatusMessage(self.request).addStatusMessage(
                _("Two-step verification cannot be disabled for all users "
                  "while it is globally enforced. Turn off global "
                  "enforcement in the control panel first."),
                'error'
                )
            redirect_url = "{0}/@@google-authenticator-settings".format(self.context.absolute_url())
            self.request.response.redirect(redirect_url)
            return None

        users = api.user.get_users()
        disable_two_factor_authentication_for_users(users)

        IStatusMessage(self.request).addStatusMessage(
            _("You have successfully disabled the two-step verification for all users."),
            'info'
            )
        redirect_url = "{0}/@@google-authenticator-settings".format(self.context.absolute_url())
        self.request.response.redirect(redirect_url)
