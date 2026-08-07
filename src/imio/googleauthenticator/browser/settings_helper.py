from imio.googleauthenticator.helpers import has_completed_enrollment
from imio.googleauthenticator.helpers import has_enabled_two_factor_authentication
from imio.googleauthenticator.helpers import is_two_factor_authentication_globally_enabled
from plone import api
from Products.Five import BrowserView
from zope.i18nmessageid import MessageFactory


_ = MessageFactory('imio.googleauthenticator')


class SettingsHelper(BrowserView):
    """
    Helper view for accessing some conditions from portal actions (actions.xml).
    """
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def is_two_factor_authentication_globally_enabled(self):
        """
        Disable the two-step verification for the user and redirect back to the `@@personal-information`.
        """
        return is_two_factor_authentication_globally_enabled()

    def show_enable_two_factor_authentication_link(self):
        """
        Indicates whether the enable two factor authentication link should be shown.

        The following condition shall be met for True to be returned:

        - User hasn't completed second-factor enrollment yet.

        :return bool:
        """
        if api.user.is_anonymous():
            return False  # don't show action to anonymous users

        user = api.user.get_current()
        # D-10/MFA-17/MFA-18: keyed on the enrollment-completion property,
        # not on has_enabled_two_factor_authentication (the shape
        # RESEARCH.md's "Recommended shape" section suggested). Under D-01,
        # install sets the enable flag for every pre-existing account, so
        # keying this link on that flag would hide it from exactly the
        # install-enrolled population MFA-19 exists to walk through
        # enrollment. The global setting is not consulted at all: whether
        # enrollment is offered depends only on whether the user has
        # completed it.
        return not has_completed_enrollment(user)

    def show_disable_two_factor_authentication_link(self):
        """
        Indicates whether the disable two factor authentication link should be shown.

        The following conditions shall be met for True to be returned:

        - User has enabled the two factor authentication for his account.
        - User has completed second-factor enrollment.
        - In app settings, the globally enable two factor authentication is set to False.

        :return bool:
        """
        if api.user.is_anonymous():
            return False  # don't show action to anonymous users

        user = api.user.get_current()
        # D-11/MFA-16: hiding this link is cosmetic, not the control -- the
        # actual refusal lives in
        # browser/disable_two_factor_authentication.py (plan 10-03), because
        # a hidden link is still a working bookmarked URL (D-09, the mirror
        # of the case Phase 9 settled as BUG-08).
        #
        # WR-02: has_completed_enrollment(user) added so an install-time
        # bulk-enrolled account (enable=True, enrolled=False) does not show
        # this link at the same time as "Enable two-step verification" once
        # globally_enabled is off -- two contradictory actions for the same
        # unfinished setup. Does not strand anyone: such an account still
        # sees the "Enable" link (show_enable_two_factor_authentication_link
        # is keyed only on enrollment, not this flag), and this link
        # reappears once enrollment completes.
        return (
            has_enabled_two_factor_authentication(user) and
            has_completed_enrollment(user) and
            not is_two_factor_authentication_globally_enabled()
        )

    def show_regenerate_recovery_codes_link(self):
        """
        Indicates whether the "Regenerate recovery codes" link should be shown.

        The following condition shall be met for True to be returned:

        - User has completed second-factor enrollment.

        :return bool:
        """
        if api.user.is_anonymous():
            return False  # don't show action to anonymous users

        user = api.user.get_current()
        # D-15: profiles/default/actions.xml used to reuse
        # show_disable_two_factor_authentication_link's condition for this
        # action. D-11 changed that condition to require the global setting
        # to be off, which would have hidden "Regenerate recovery codes"
        # from every user under global enforcement -- exactly the
        # population that needs it. This method gives the action its own
        # condition, with no global-setting term. Keyed on completed
        # enrollment rather than the enable flag: a user who has never seen
        # a QR code has no recovery codes to regenerate.
        return has_completed_enrollment(user)
