from plone import api
from plone.app.users.browser.personalpreferences import UserDataPanel
from plone.app.users.userdataschema import IUserDataSchema
from plone.app.users.userdataschema import IUserDataSchemaProvider
from Products.PluggableAuthService.interfaces.authservice import IBasicUser
from Products.PluggableAuthService.interfaces.events import IPrincipalCreatedEvent
from zope.component import adapter
from zope.i18nmessageid import MessageFactory
from zope.interface import implements
from zope.schema import Bool
from zope.schema import TextLine

import logging


logger = logging.getLogger("imio.googleauthenticator")

_ = MessageFactory('imio.googleauthenticator')


class CustomizedUserDataPanel(UserDataPanel):
    """
    Customise the user form shown in personal-preferences.
    """
    def __init__(self, context, request):
        super(CustomizedUserDataPanel, self).__init__(context, request)

        # Removing certain fields from form.
        #
        # This omit() only covers the view it is registered for,
        # ``personal-information``. It is NOT a general protection: plone.app.users'
        # ``@@user-information``, the form an administrator uses to edit another
        # user's profile, is not overridden here and renders whatever the schema
        # declares. Anything that must never reach a profile form therefore has to
        # be kept off ``IEnhancedUserDataSchema`` altogether, not merely omitted
        # here -- which is why the replay and lockout counters are memberdata
        # properties with no schema field. See tests/test_adapter.py.
        self.form_fields = self.form_fields.omit(
            'enable_two_factor_authentication',
            'two_factor_authentication_secret',
            'bar_code_reset_token',
            )


class UserDataSchemaProvider(object):
    implements(IUserDataSchemaProvider)

    def getSchema(self):
        """
        """
        return IEnhancedUserDataSchema


class IEnhancedUserDataSchema(IUserDataSchema):
    """
    Extended user profile.

    :property bool enable_two_factor_authentication: Indicates, whether the two-step verification is
                                                     enabled for the user.
    :property string two_factor_authentication_secret: Secret key of the user (unique per user). Automatically
                                                       generated.
    :property string bar_code_reset_token: Token to reset users' bar-code. Automatically generated.

    The replay and lockout counters -- ``two_factor_authentication_failed_attempts``,
    ``two_factor_authentication_locked_until`` and
    ``two_factor_authentication_last_interval`` -- are deliberately NOT declared here.
    They are internal state, written only by ``helpers.py`` via
    ``setMemberProperties`` and read only via ``getProperty``; what makes them
    persist is their ``profiles/default/memberdata_properties.xml`` entry, which a
    schema field neither provides nor replaces. Declaring them here would render
    them on every profile form that this package does not override -- crashing
    ``@@user-information`` with ``AttributeError``, since ``adapter.py`` supplies no
    accessor for them -- and would make a user's own lockout deadline
    form-writable. See ``tests/test_adapter.py``.
    """
    enable_two_factor_authentication = Bool(
        title=_('Enable two-step verification.'),
        description=_("""Enable/disable the two-step verification. Click <a href=\"@@setup-two-factor-authentication\"> """
                      """here</a> to set it up or <a href=\"@@disable-two-factor-authentication\">here</a> to """
                      """disable it."""
            ),
        required=False
        )

    two_factor_authentication_secret = TextLine(
        title=_('Secret key'),
        description=_('Automatically generated'),
        required=False,
    )

    bar_code_reset_token = TextLine(
        title=_('Token to reset the bar code'),
        description=_('Automatically generated'),
        required=False,
    )


@adapter(IBasicUser, IPrincipalCreatedEvent)
def userCreatedHandler(principal, event):
    """
    Fired upon creation of each user. If app setting ``globally_enabled`` is set to True,
    two-step verification would be automatically enabled for the registered users (in that
    case they would have to go through the bar-code recovery procedure.

    The ``principal`` value is seems to be a user object, although it does not have
    the ``setMemberProperties`` method defined (that's why we obtain the user
    using `plone.api`, 'cause that one has it).
    """
    from imio.googleauthenticator.helpers import get_or_create_secret
    from imio.googleauthenticator.helpers import is_two_factor_authentication_globally_enabled
    try:
        globally_enabled = is_two_factor_authentication_globally_enabled()
    except KeyError:
        # This subscriber is registered instance-wide in configure.zcml, with
        # no site or layer constraint, so it also fires for user creation in
        # Plone sites that never installed this add-on's profile -- notably
        # while imio.dms.mail's own profile creates its users, where the
        # escaping KeyError aborted addPloneSite outright and no site was
        # created at all. Such a site has no IGoogleAuthenticatorSettings
        # records and there is nothing to enable in it (COEX-10).
        #
        # Deliberately NOT pushed down into helpers.get_app_settings(): every
        # other caller of that function is reached only from an installed
        # site, where a missing record is a real fault. Defaulting there would
        # make is_two_factor_authentication_globally_enabled() answer False
        # and silently stop enforcing two-factor authentication.
        logger.debug(
            'imio.googleauthenticator is not installed in this site; '
            'skipping two-factor enrolment for %s', principal.getId())
        return

    user = api.user.get(username=principal.getId())
    if globally_enabled:
        get_or_create_secret(user)
        user.setMemberProperties(mapping={'enable_two_factor_authentication': True})

    logger.debug(user.getProperty('enable_two_factor_authentication'))
    logger.debug(user.getProperty('two_factor_authentication_secret'))
