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

# MFA-03 decision record (2026-07-31): `credentials_basic_auth` is deliberately
# left ACTIVE. Deactivating it was considered as defence in depth (ROADMAP.md
# Open Decision) but rejected: it would mutate a plugin this package does not
# own, site-wide, with no uninstall counterpart, on evidence limited to three
# grepped repositories (imio.dms.mail, server.dmsmail, industrialisation) that
# is explicitly not exhaustive. The Basic Auth credentials path is still
# vetoed -- tests/test_pas_plugin.py::test_basic_auth_veto (plan 04-03)
# asserts that directly -- so nothing is left unprotected; what is accepted
# is that the veto's reach still depends on plugin *ordering*, not on this
# extractor being absent. This is the load-bearing consequence:
# test_plugin_is_first_authenticator (below) is therefore the ONLY thing
# standing between a future plugin reorder and a Basic Auth bypass, and it
# must never be weakened or deleted.
def _add_plugin(pas, pluginid=PAS_ID):
    """
    Install and activate imio.googleauthenticator PAS plugin, and (re-)assert
    that it is first among every plugin type it provides.

    MFA-03: only object creation is guarded by the "already installed" check
    below. Activation and ordering are re-asserted on *every* profile
    application, not only on first install -- otherwise reinstalling the
    profile would be no recovery at all for a plugin some other add-on has
    since displaced from position 0.
    """
    installed = pas.objectIds()
    if pluginid not in installed:
        plugin = GoogleAuthenticatorPlugin(pluginid, title=PAS_TITLE)
        pas._setObject(pluginid, plugin)
    plugin = pas[pluginid] # get plugin acquisition wrapped!
    for info in pas.plugins.listPluginTypeInfo():
        interface = info['interface']
        if not interface.providedBy(plugin):
            continue
        if plugin.getId() not in pas.plugins.listPluginIds(interface):
            pas.plugins.activatePlugin(interface, plugin.getId())
        # MFA-03: this plugin must be first among IAuthenticationPlugin.
        # authenticateCredentials() vetoes a login by wiping the shared
        # credentials dict in place, but PAS's _extractUserIds loop
        # (PluggableAuthService.py:648-667) hands that same dict object to
        # every authenticator in listing order with no break on success --
        # the wipe only blinds authenticators listed *after* this one. States
        # the intent directly rather than relying on our plugin happening to
        # be the most recently activated entry, which was the previous
        # (accidental) mechanism for reaching index 0.
        pas.plugins.movePluginsTop(interface, [plugin.getId()])

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


