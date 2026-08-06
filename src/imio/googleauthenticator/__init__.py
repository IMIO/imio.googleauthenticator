# -*- extra stuff goes here -*-

from imio.googleauthenticator.pas_plugin import addGoogleAuthenticatorPlugin
from imio.googleauthenticator.pas_plugin import GoogleAuthenticatorPlugin
from imio.googleauthenticator.pas_plugin import manage_addGoogleAuthenticatorPluginForm
from Products.PluggableAuthService.PluggableAuthService import registerMultiPlugin
from zope.i18nmessageid import MessageFactory


_ = MessageFactory('imio.googleauthenticator')


def initialize(context):
    """
    Initializer called when used as a Zope 2 product.
    """
    registerMultiPlugin(GoogleAuthenticatorPlugin.meta_type)  # Add to PAS menu
    context.registerClass(
        GoogleAuthenticatorPlugin,
        constructors=(manage_addGoogleAuthenticatorPluginForm, addGoogleAuthenticatorPlugin),
        visibility=None
        )
