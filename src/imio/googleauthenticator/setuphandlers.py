from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import has_enabled_two_factor_authentication
from imio.googleauthenticator.helpers import is_two_factor_authentication_globally_enabled
from imio.googleauthenticator.pas_plugin import GoogleAuthenticatorPlugin
from plone import api
from uuid import uuid4
from zope.i18nmessageid import MessageFactory


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
    plugin = pas[pluginid]  # get plugin acquisition wrapped!
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


def _enroll_existing_users():
    """
    MFA-15/D-01/D-02: enrol every pre-existing account when
    ``globally_enabled`` is on, at install time -- flag only, no seed.
    Mirrors ``_add_plugin``'s own "check current state before writing"
    shape for idempotency (D-13): re-applying the profile enrols only
    whoever is not enrolled yet, so a second application changes nothing
    the first one already did.

    Deliberately does NOT call ``get_or_create_secret`` (D-02): the seed
    is minted when the enrollment redirect is signed, and shown as a QR
    in that same request chain -- not here. Minting here would give
    every account a seed nobody has seen, and would make installation
    fail outright on any site where ``IMIO_GOOGLEAUTHENTICATOR_SEED_KEY``
    is unset.

    Deliberately does NOT wrap the loop body in a bare ``except
    Exception`` that logs and continues -- the shape
    ``enable_two_factor_authentication_for_users`` uses at
    ``helpers.py``. D-04 forbids that here: at install it would mean some
    accounts enrolled and some not, with nothing visible to the operator.
    A per-user failure is left to propagate out of the import step
    instead, so a broken install is a visible failure, not a silent
    partial one.

    Deliberately does NOT reuse ``enable_two_factor_authentication_for_
    users``: that function calls ``get_or_create_secret`` before its own
    flag check, and swallows every per-user exception except
    ``ValueError`` -- both of which this function must not do.
    """
    if not is_two_factor_authentication_globally_enabled():
        return
    for user in api.user.get_users():
        if not has_enabled_two_factor_authentication(user):
            user.setMemberProperties(
                mapping={'enable_two_factor_authentication': True})


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

    _enroll_existing_users()


def _remove_plugin(pas, pluginid=PAS_ID):
    """
    Remove the imio.googleauthenticator PAS plugin from acl_users, and
    deactivate it from every plugin type it was registered in.

    The guard below is what makes applying the uninstall profile twice a
    no-op instead of an AttributeError from _delObject on a missing id --
    the same "already there / already gone" idempotency _add_plugin's own
    installed-check gives the install path.

    pas._delObject(pluginid) is the whole removal. PluggableAuthService's
    _delOb (PluggableAuthService.py:454-465) calls
    plugins.removePluginById(id), which (Products/PluginRegistry/
    PluginRegistry.py:320-327) deactivates the plugin from every plugin
    type it is configured in -- IAuthenticationPlugin, IChallengePlugin,
    and any other interface it provides -- before the object itself is
    deleted. Do not add a separate deactivatePlugin loop here: it would be
    redundant with what _delOb already does, and would run against an
    object that then gets deleted anyway.
    """
    if pluginid not in pas.objectIds():
        return
    pas._delObject(pluginid)


def uninstallVarious(context):
    """
    @param context: Products.GenericSetup.context.DirectoryImportContext instance

    Widens the uninstall profile to actually reverse installation
    (COEX-06 / v1.0-MILESTONE-AUDIT.md Gap 2): a GenericSetup profile can
    remove a configlet, a browser layer, a local utility and a registry
    record declaratively, but it cannot remove a PAS plugin object -- that
    needs a handler, same as install needed one for _add_plugin. Leaving
    the plugin behind means it keeps intercepting every login after the
    add-on is believed uninstalled, and it unpickles as
    OFS.Uninstalled.Broken inside acl_users if the egg is later removed
    from the Python environment.

    This handler does NOT touch memberdata. The eight
    memberdata_properties.xml declarations and any enrolled user's stored
    seed are a deliberate exclusion from this uninstall profile -- see the
    scope_boundary note in this quick task's PLAN.md and
    test_uninstall_keeps_enrolled_user_data: removing them would destroy
    every enrolled user's encrypted seed and recovery-code hashes with no
    recovery path, and an uninstall is often temporary.
    """
    # Mirrors setupVarious's own gate: presence of a data file that exists
    # only in profiles/uninstall/, not its content. Without this gate the
    # handler is a registered import step that fires on every profile
    # import in the whole Zope process (applyProfile's
    # runAllImportStepsFromProfile runs every registered step, not only
    # the ones the target profile "owns") and would delete google_auth
    # from any site that installs anything at all -- the same
    # instance-wide-subscriber class of defect as COEX-10.
    if context.readDataFile('imio.googleauthenticator.uninstall.txt') is None:
        # Not our uninstall profile
        return

    portal = context.getSite()
    pas = portal.acl_users
    _remove_plugin(pas)
