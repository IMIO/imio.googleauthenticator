"""
The idea of this PAS plugin is quite simple. It should check the user profile
for the user being logged in and if user has enabled two-step verification for
his account (``enable_two_factor_authentication`` is set to True), then
redirect him further to a another page, where he would enter his Google
Authenticator token, after successful validation of which the user would be
definitely logged in.

If user has not enabled the two-step verification for his account
(``enable_two_factor_authentication`` is set to False), then do nothing so
that Plone continues logging in the user normal way.
"""
import logging

from Globals import InitializeClass
from AccessControl.SecurityInfo import ClassSecurityInfo

from plone import api

from Products.PluggableAuthService.PluggableAuthService import reraise
from Products.PluggableAuthService.PluggableAuthService import _SWALLOWABLE_PLUGIN_EXCEPTIONS
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from Products.PageTemplates.PageTemplateFile import PageTemplateFile

from imio.googleauthenticator.adapter import ICameFrom
from imio.googleauthenticator.helpers import get_secret
from imio.googleauthenticator.helpers import is_whitelisted_client
from imio.googleauthenticator.helpers import sign_user_data


logger = logging.getLogger("imio.googleauthenticator")

# Shared request.other keys between authenticateCredentials() (writer, via
# _mark_2fa_pending) and subscribers.redirect_pending_2fa (reader). Both
# sides import the constants rather than repeating the literals, so a typo
# is an ImportError rather than a silent bypass (MFA-02/COEX-08).
REQUEST_KEY_PENDING = '_2fa_pending'
REQUEST_KEY_USER_ID = '_2fa_user_id'

manage_addGoogleAuthenticatorPluginForm = PageTemplateFile(
    './www/add_google_authenticator_form',
    globals(),
    __name__='manage_addGoogleAuthenticatorPluginForm'
)


def addGoogleAuthenticatorPlugin(self, id, title='', REQUEST=None):
    """
    Add a Google Authenticator PAS Plugin to Plone PAS
    """
    o = GoogleAuthenticatorPlugin(id, title)
    self._setObject(o.getId(), o)

    if REQUEST is not None:
        msg = 'Google+Authentiactor+PAS+Plugin+added.'
        REQUEST['RESPONSE'].redirect(
            '{0}/manage_main?manage_tabs_message={1}'.format(
                self.absolute_url(), msg))


def _mark_2fa_pending(request, user):
    """
    Stashes the pending-2FA signal on ``request.other`` (``request.set`` is
    ``BaseRequest.__setitem__``, ZPublisher/BaseRequest.py:233-241), the one
    channel form data and cookies cannot reach. This is the only thing
    ``authenticateCredentials`` does once it has decided a login needs a
    second factor -- the actual redirect happens later, in
    ``subscribers.redirect_pending_2fa``, driven by ``IPubBeforeCommit``.

    :param ZPublisher.HTTPRequest request:
    :param Products.PlonePAS.tools.memberdata user:
    """
    request.set(REQUEST_KEY_PENDING, True)
    request.set(REQUEST_KEY_USER_ID, user.getUserId())


def send_2fa_redirect(request, response):
    """
    Builds and applies the 2FA challenge redirect: signs a
    ``@@google-authenticator-token`` URL for the user stashed by
    ``_mark_2fa_pending``, points the response at it, and empties the
    response body so nothing rendered ahead of us on this request leaks to
    the client. Shared by this plan's ``IPubBeforeCommit`` subscriber and
    plan 04-03's challenge plugin, so the cookie clear, the ``ICameFrom``
    ``next_url`` append, the status lock and the body clear+lock cannot
    drift between the two call sites.

    :param ZPublisher.HTTPRequest request:
    :param ZPublisher.HTTPResponse.HTTPResponse response:
    :return bool: True if the redirect was applied, False if the stashed
        user id was missing or did not resolve (no response mutation in
        that case).
    """
    user_id = request.other.get(REQUEST_KEY_USER_ID)
    if not user_id:
        return False

    user = api.user.get(userid=user_id)
    if user is None:
        return False

    response.setCookie('__ac', '', path='/')

    signed_url = sign_user_data(
        request=request, user=user, url='@@google-authenticator-token')

    came_from_adapter = ICameFrom(request)
    # Appending possible `came_from`, but give it another name.
    came_from = came_from_adapter.getCameFrom()
    if came_from:
        signed_url = '{0}&next_url={1}'.format(signed_url, came_from)

    # The status lock below is for HTTPResponse.exception
    # (HTTPResponse.py:799-803): it calls self._unauthorized() -- hence
    # PAS's challenge() -- and then unconditionally runs
    # setStatus(Unauthorized) one line later. Without locking the status
    # here, an unlocked 302 set on this line would be overwritten by that
    # 401 on the challenge-plugin path plan 04-03 adds.
    response.redirect(signed_url, lock=1)

    # response.setBody('') alone is a no-op: HTTPResponse.py:453-460
    # returns before ever assigning self.body when the argument is falsy.
    # The plain attribute assignment is what actually clears what the
    # publisher writes to the client (HTTPResponse.__str__, :947-966).
    response.body = ''
    response.setHeader('content-length', '0')
    # Locking the body below sets _locked_body, which setBody checks first
    # (HTTPResponse.py:454-455). plone.transformchain 1.2.2 is registered
    # for the same IPubBeforeCommit event in this buildout and calls
    # setBody(...) unconditionally; subscriber order for one interface is
    # undefined, so without locking it here the emptiness would hold only
    # by luck.
    response.setBody('', lock=1)

    return True


class GoogleAuthenticatorPlugin(BasePlugin):
    """
    Google Authenticator PAS Plugin
    """
    meta_type = 'iMio Google Authenticator PAS'
    security = ClassSecurityInfo()

    # RENAME-11. PAS's _SWALLOWABLE_PLUGIN_EXCEPTIONS (NameError, AttributeError,
    # KeyError, TypeError, ValueError) otherwise make any bug here a silent
    # fallthrough to source_users -- i.e. authentication on password alone, logged
    # only at DEBUG. reraise() (PluggableAuthService.py:88-93) reads this attribute
    # off the plugin instance it is handed, so it is scoped to us: later plugins
    # still get their post-credentials-wipe KeyError swallowed (below), which the
    # veto this plugin performs depends on. The plugin's own inner delegation loop
    # (which calls reraise() on the *other* plugins) is deliberately left alone --
    # Phase 4 owns that boundary rework.
    _dont_swallow_my_exceptions = True

    def __init__(self, id, title=None):
        self._setId(id)
        self.title = title

    def authenticateCredentials(self, credentials):
        """
        Place to actually validate the user credentials specified and return a
        tuple (login, login) on success or (None, None) on failure.

        If we find one and two-step verification is not enabled for the
        account, we consider the authentication passed and log the user in. If
        two-step verification has been enabled for the account, the first step
        of authentication is considered to be passed and we go to the next
        page (having the user and pass remembered), where we check for the
        token generated by the token generator (Google Authenticator). If the
        token is valid too, we log the user in.
        """

        if is_whitelisted_client():
            return None

        login = credentials.get('login')

        if not login:
            return None

        user = api.user.get(username=login)
        if user is None:
            # Unmatched username (mistyped, or a bot probing usernames).
            # Fall through so the next auth plugin / PAS can report a normal
            # login failure instead of crashing on user.getUserName() below.
            return None

        logger.debug("Found user: {0}".format(user.getUserName()))

        two_factor_authentication_enabled = user.getProperty(
            'enable_two_factor_authentication')
        logger.debug("Two-step verification enabled: {0}".format(
            two_factor_authentication_enabled))

        if two_factor_authentication_enabled:
            # Consume the credentials before delegating, so every exit from
            # this branch -- normal, early-return, and exception -- leaves
            # the shared dict empty. This prevents later IAuthenticationPlugins
            # from authenticating the user before we verified the token. It
            # does produce a "Login failed" status message though, that we
            # need to remove in the token validation view. The wipe cannot
            # literally precede the copy below: the delegated plugins still
            # need the password to verify it. Also note PAS wraps the
            # authenticator loop in ZCacheable_get/ZCacheable_set
            # (PluggableAuthService.py:641-673); Plone 4.3 associates no
            # cache manager with acl_users so ZCacheable_getCache() returns
            # None and this loop always runs (OFS/Cache.py:150-168), but a
            # cache manager added later would serve a previously cached
            # *successful* result and skip this veto entirely.
            delegated_credentials = dict(credentials)
            for key in credentials.keys():
                del credentials[key]

            # First see, if the password is correct.
            # We do this by allowing all IAuthenticationPlugin plugins to
            # authenticate the credentials, and pick the first one that is
            # successful.
            pas_plugins = self._getPAS().plugins
            auth_plugins = pas_plugins.listPlugins(IAuthenticationPlugin)
            authorized = None
            for plugid, authplugin in auth_plugins:
                if plugid == self.getId():
                    # Avoid infinite recursion
                    continue

                try:
                    authorized = authplugin.authenticateCredentials(
                        delegated_credentials)
                except _SWALLOWABLE_PLUGIN_EXCEPTIONS:
                    reraise(authplugin)
                    msg = 'AuthenticationPlugin {0} error'.format(plugid)
                    logger.info(msg, exc_info=True)
                    continue

                if authorized is not None:
                    # An auth plugin successfully authenticated the user
                    break

            if authorized is None:
                # No auth plugin was able to authenticate the user
                return None

            # SEC-03: force the seed-decrypt check synchronously, on this
            # same request, so a broken encryption key still raises out of
            # _extractUserIds -- exactly as it did before this plan's
            # restructure. get_secret() is a pure read (never
            # get_or_create_secret), so this cannot itself write the ZODB;
            # it only surfaces a decrypt failure that would otherwise wait,
            # silently, until send_2fa_redirect runs on IPubBeforeCommit.
            get_secret(user)

            # Decide-only: stash the pending signal for
            # subscribers.redirect_pending_2fa to act on later, on
            # IPubBeforeCommit. No RESPONSE access and no ZODB write here --
            # see send_2fa_redirect for the actual redirect/body-clear.
            _mark_2fa_pending(self.REQUEST, user)

            return None

        if credentials.get('extractor') != self.getId():
            return None

        return None


classImplements(GoogleAuthenticatorPlugin, IAuthenticationPlugin)
InitializeClass(GoogleAuthenticatorPlugin)
