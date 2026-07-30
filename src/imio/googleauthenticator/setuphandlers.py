from uuid import uuid4

from zope.i18nmessageid import MessageFactory

from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.pas_plugin import GoogleAuthenticatorPlugin

_ = MessageFactory('imio.googleauthenticator')

PAS_TITLE = 'Google Authenticator plugin (imio.googleauthenticator)'
PAS_ID = 'google_auth'

def _setup_secret_key():
    """
    Seed ska_secret_key at install time, if it is not already set.

    Post-review revision (CR-02): this seeding was deleted by this phase's
    original plan (D-04) in favour of a lazy mint inside
    get_ska_secret_key(), which turned out to write registry state from a
    request path (PAS authenticateCredentials -> sign_user_data) that ends
    in transaction.abort() on Unauthorized, discarding the mint after a
    signed URL using it was already redirected to. Restoring seeding here
    fixes that. D-04's actual intent is kept intact: no nested profile
    import-step re-entry -- the <depends name="plone.app.registry"/>
    declaration added by REG-02 already guarantees the registry records
    exist by the time setupVarious runs, so a direct get_app_settings()
    call is enough.
    """
    settings = get_app_settings()
    if not settings.ska_secret_key:
        settings.ska_secret_key = unicode(uuid4())

def _add_plugin(pas, pluginid=PAS_ID):
    """
    Install and activate imio.googleauthenticator PAS plugin
    """
    installed = pas.objectIds()
    if pluginid in installed:
        return PAS_TITLE + " already installed."
    plugin = GoogleAuthenticatorPlugin(pluginid, title=PAS_TITLE)
    pas._setObject(pluginid, plugin)
    plugin = pas[plugin.getId()] # get plugin acquisition wrapped!
    for info in pas.plugins.listPluginTypeInfo():
        interface = info['interface']
        if not interface.providedBy(plugin):
            continue
        pas.plugins.activatePlugin(interface, plugin.getId())
        pas.plugins.movePluginsDown(
            interface,
            [x[0] for x in pas.plugins.listPlugins(interface)[:-1]],
        )

def setupVarious(context):
    """
    @param context: Products.GenericSetup.context.DirectoryImportContext instance
    """

    # We check from our GenericSetup context whether we are running
    # add-on installation for your product or any other proudct
    if context.readDataFile('imio.googleauthenticator.marker.txt') is None:
        # Not your add-on
        return

    portal = context.getSite()

    _setup_secret_key()

    pas = portal.acl_users
    _add_plugin(pas)


