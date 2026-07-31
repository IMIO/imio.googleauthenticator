"""
This helper module contains functions used throughout c.googleauthenticator.
"""
from hashlib import sha1
from hmac import compare_digest
from urllib import unquote, quote
from urlparse import urlparse
import base64
import io
import logging
import os
import time

from zope.component import getUtility
from zope.globalrequest import getRequest
from zope.i18n import translate
from zope.i18nmessageid import MessageFactory

from Products.statusmessages.interfaces import IStatusMessage

from onetimepass import valid_totp

from plone import api
from plone.registry.interfaces import IRegistry

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from ska import sign_url, validate_signed_request_data
import ipaddress
import qrcode

from imio.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings

_ = MessageFactory('imio.googleauthenticator')

logger = logging.getLogger("imio.googleauthenticator")

# Environment variable name carrying the Fernet key that encrypts every
# user's TOTP seed. Locked via this phase's Task 1 checkpoint:decision.
ENV_VAR_NAME = 'IMIO_GOOGLEAUTHENTICATOR_SEED_KEY'
# Literal envelope prefix on every ciphertext this module stores. '$' cannot
# appear in URL-safe base64 (A-Za-z0-9-_=), so the split is unambiguous.
CIPHERTEXT_VERSION_PREFIX = 'v1$'


def get_encryption_key():
    """
    Reads the Fernet key from the environment on every call, deliberately --
    unlike ``imio.helpers/__init__.py``'s module-scope
    ``SSO_APPS_CLIENT_SECRET = os.environ.get(...)`` read at import time. A
    module-scope read here would run before ``bin/test``'s environment is
    necessarily populated, and could never be overridden per-test.

    :return string: The raw value of ``ENV_VAR_NAME``, or ``None`` if unset.
    """
    return os.environ.get(ENV_VAR_NAME)


def _get_fernet():
    """
    Builds a ``Fernet`` instance from :func:`get_encryption_key`, failing
    closed. Never caught locally to return ``None`` or a cached/default
    instance -- a caller that swallows this turns a loud refusal into a
    silent plaintext or password-only downgrade.

    :return cryptography.fernet.Fernet:
    """
    key = get_encryption_key()
    if not key:
        raise ValueError(
            '{0} is not set; seed encryption is unavailable'.format(ENV_VAR_NAME))

    if isinstance(key, unicode):
        key = key.encode('ascii')

    try:
        return Fernet(key)
    except (ValueError, TypeError):
        # A right-shaped-but-wrong-length base64 key raises ValueError; a
        # key that is not valid base64 at all raises TypeError from
        # binascii on py2. Catch both so the operator sees a readable
        # message naming the variable, not a bare TypeError traceback.
        raise ValueError(
            '{0} is set but is not a valid Fernet key'.format(ENV_VAR_NAME))


def encrypt_seed(plaintext_seed):
    """
    Encrypts a plaintext TOTP seed for storage.

    :param string plaintext_seed:
    :return unicode: ``v1$<fernet-token>``.
    """
    fernet = _get_fernet()
    if isinstance(plaintext_seed, unicode):
        plaintext_seed = plaintext_seed.encode('ascii')
    token = fernet.encrypt(plaintext_seed)
    return u'{0}{1}'.format(CIPHERTEXT_VERSION_PREFIX, token.decode('ascii'))


def decrypt_seed(ciphertext):
    """
    Decrypts a ``v1$<fernet-token>`` ciphertext back to the plaintext seed.

    :param string ciphertext:
    :return string: The plaintext seed.
    """
    if not ciphertext or not ciphertext.startswith(CIPHERTEXT_VERSION_PREFIX):
        raise ValueError('Unknown or missing ciphertext version prefix')

    token = ciphertext[len(CIPHERTEXT_VERSION_PREFIX):]
    if isinstance(token, unicode):
        token = token.encode('ascii')

    fernet = _get_fernet()
    try:
        return fernet.decrypt(token)
    except InvalidToken:
        raise ValueError('Ciphertext failed to decrypt')

# ******************************************


def get_app_settings():
    """
    Gets the Google Authenticator settings.
    """
    registry = getUtility(IRegistry)
    settings = registry.forInterface(IGoogleAuthenticatorSettings)
    return settings


def get_user(username):
    """
    Get user by username given and return member object.
    """
    return api.user.get(username=username)


def get_username(user=None):
    """
    Gets the username of the user.

    :param user: If given, used to extract the user. Otherwise,
    ``plone.api.user.get_current`` is used.

    :return string:
    """
    if user is None:
        user = api.user.get_current()
    if user:
        return user.getUserName()


def get_base_url(request=None):
    """
    Gets domain name (with HTTP).

    :param ZPublisher.HTTPRequest request:
    :return string:
    """
    if request is None:
        request = getRequest()

    parsed_uri = urlparse(request.base)
    return "{0}://{1}/".format(parsed_uri.scheme, parsed_uri.netloc)


def get_domain_name(request=None):
    """
    Gets domain name (without HTTP).

    :param ZPublisher.HTTPRequest request:
    :return string:
    """
    if request is None:
        request = getRequest()

    parsed_uri = urlparse(request.base)
    return parsed_uri.netloc


def generate_secret(user):
    """
    Generates secret for the user. 160 bits of ``os.urandom``, stdlib
    base32-encoded -- the previous third-party encoder ASCII-decodes its
    input before encoding and rejects raw entropy.

    :param Products.PlonePAS.tools.memberdata user:
    """
    secret = base64.b32encode(os.urandom(20))
    # logger.debug(secret)
    ciphertext = encrypt_seed(secret)
    user.setMemberProperties(
        mapping={'two_factor_authentication_secret': ciphertext})
    return secret


def get_barcode_image(username, domain, secret):
    """
    Get barcode image as an in-process ``data:`` URI. Rendered locally with
    a pure-Python QR encoder -- no outbound request and nothing shelled
    out, so the seed never crosses the process boundary.

    :param string username:
    :param string domain:
    :param string secret:
    :return string:
    """
    data = "otpauth://totp/{0}@{1}?secret={2}".format(username, domain, secret)
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    encoded = base64.b64encode(buf.getvalue())
    return 'data:image/png;base64,{0}'.format(encoded)


def get_secret(user=None, hashed=False):
    """
    Gets users' secret code. If ``hashed`` is set to True, returned hashed.

    :param Products.PlonePAS.tools.memberdata user:
    :param bool hashed: If set to True, hashed version is returned.
    :return string:
    """
    # TODO: Return hashed version if ``hashed`` is set to True.
    if user is None:
        user = api.user.get_current()
    if user:
        secret = user.getProperty('two_factor_authentication_secret')

        # If string returned, then it's likely a set string
        if isinstance(secret, basestring) and secret:
            return decrypt_seed(secret)


def is_site_local_user(user=None):
    """
    Tells whether the user is defined in the Plone site's own PAS, rather
    than in the Zope root user folder.

    This plugin is registered in the site's ``acl_users``, so it only sees
    logins that the site's PAS authenticates. An account defined in the root
    user folder -- typically the ``inituser`` ``admin`` -- is authenticated
    above the site, and this plugin's ``authenticateCredentials`` cannot gate
    it: its password pre-check delegates to the *site's* other
    ``IAuthenticationPlugin``s, none of which can resolve a root account, so
    it declines to veto and the root user folder logs the user in on the
    password alone.

    Enrolment therefore has to refuse such an account rather than report
    success for a second factor that will never be demanded (T-03-23).

    Note that ``plone.api.user.get`` is NOT a usable test here: it returns a
    ``MemberData`` for a root account too (wrapped ``for /acl_users``), and
    ``portal_memberdata`` will happily store properties against it. Only the
    site PAS lookup distinguishes the two.

    :param Products.PlonePAS.tools.memberdata user:
    :return bool:
    """
    if user is None:
        user = api.user.get_current()

    if user is None:
        return False

    user_id = user.getId()
    if not user_id:
        # Anonymous.
        return False

    portal = api.portal.get()
    return portal.acl_users.getUserById(user_id) is not None


def get_or_create_secret(user, overwrite=False):
    """
    Gets or creates token secret for the user given. Checks first if user
    given has a ``secret`` generated.
    If not, generate it for him and save it in his profile
    (``two_factor_authentication_secret``).

    :param Products.PlonePAS.tools.memberdata user: If provided, used.
        Otherwise ``plone.api.user.get_current`` is used to obtain the user.
    :return string:
    """
    # TODO: Return hashed version if ``hashed`` is set to True.
    if user is None:
        user = api.user.get_current()

    if overwrite:
        return generate_secret(user)

    secret = user.getProperty('two_factor_authentication_secret')
    if isinstance(secret, basestring) and secret:
        return decrypt_seed(secret)
    else:
        return generate_secret(user)


def get_token_description(user=None, overwrite_secret=False):
    """
    Gets description with bar code image.

    :param Products.PlonePAS.tools.memberdata user:
    :return string:
    """
    request = getRequest()

    if user is None:
        user = api.user.get_current()

    return '<div><img src="{url}" alt="QR Code" /></div>'.format(
        url=get_barcode_image(
            get_username(user),
            get_domain_name(request),
            get_or_create_secret(user, overwrite=overwrite_secret)
        ),
    )


def validate_token(token, user=None):
    """
    Validates the given token.

    :param string token:
    :return bool:
    """
    if user is None:
        user = api.user.get_current()

    secret = get_secret(user)

    # logger.debug('secret: {0}'.format(secret))

    if not secret:
        # No stored seed means no token can be valid, so refuse rather than
        # hand a falsy secret to onetimepass: it base32-decodes whatever it
        # is given and raises TypeError('Incorrect secret'), which is an
        # unhandled 500 on a form whose job is to reject bad input. Note
        # that get_secret returns None *implicitly* for a user with no
        # secret, which is how this reaches onetimepass at all.
        #
        # Guarded here rather than in the three callers (token.py,
        # reset_bar_code.py, user_setup.py) because all three route through
        # this function, and each can resolve a secret-less user: the token
        # and reset forms pass user=None when no signed `auth_user`
        # parameter is present, and their updateFields has already blanked
        # the __ac cookie, so that submit arrives anonymous.
        #
        # Deliberately narrow: a *decryption* failure inside get_secret
        # raises ValueError and must keep propagating, since swallowing it
        # would downgrade a broken-key refusal into a wrong-token message.
        return False

    validation_result = valid_totp(token=token, secret=secret)

    return validation_result


def is_account_locked(user):
    """
    Tells whether the user's second factor is currently locked out, per
    ``two_factor_authentication_locked_until``. Equality means NOT locked --
    the lock releases at the exact epoch it names.

    ``getProperty(...)`` returns ``''`` rather than ``0`` for a Zope-root
    account (no property sheet), which would raise ``TypeError`` against
    ``int(time.time())`` without the ``or 0`` coercion.

    :param Products.PlonePAS.tools.memberdata user:
    :return bool:
    """
    locked_until = int(
        user.getProperty('two_factor_authentication_locked_until') or 0)
    return locked_until > int(time.time())


def register_failed_second_factor(user):
    """
    Records one failed second-factor submission for ``user``. If the new
    count reaches ``max_failed_attempts``, locks the account for
    ``lockout_duration`` seconds and resets the counter to 0 in the same
    write -- so both the counter and the lock land together, or neither
    does.

    No ``try``/``except`` here: a ``PropertyValueError`` from a
    mis-declared property must reach the developer as a 500, not be
    downgraded into a lockout that silently never locks.

    :param Products.PlonePAS.tools.memberdata user:
    """
    failed_attempts = int(
        user.getProperty('two_factor_authentication_failed_attempts') or 0)
    failed_attempts += 1

    settings = get_app_settings()
    max_failed_attempts = int(settings.max_failed_attempts)
    lockout_duration = int(settings.lockout_duration)

    if failed_attempts >= max_failed_attempts:
        user.setMemberProperties(mapping={
            'two_factor_authentication_failed_attempts': 0,
            'two_factor_authentication_locked_until':
                int(time.time()) + lockout_duration,
        })
    else:
        user.setMemberProperties(mapping={
            'two_factor_authentication_failed_attempts': failed_attempts,
        })


def reset_failed_second_factor(user):
    """
    Clears the failed-attempts counter and any active lock for ``user`` in
    a single write, following a successful second factor.

    :param Products.PlonePAS.tools.memberdata user:
    """
    user.setMemberProperties(mapping={
        'two_factor_authentication_failed_attempts': 0,
        'two_factor_authentication_locked_until': 0,
    })


def get_browser_hash(request=None):
    """
    Gets browser hash. Adds an extra security layer, since browser version is
    unlikely to be changed.

    :param ZPublisher.HTTPRequest request:
    :return string:
    """
    if request is None:
        request = getRequest()

    try:
        return sha1(request.get('HTTP_USER_AGENT')).hexdigest()
    except Exception as e:
        logger.debug(str(e))
        return ''


def get_ska_secret_key(request=None, user=None, use_browser_hash=True):
    """
    Gets the `secret_key` to be used in `ska` package. A pure read -- this
    function does NOT mint or persist `ska_secret_key` (CR-02): seeding
    happens once, reliably, at install time
    (`setuphandlers._setup_secret_key`), because a write performed here would
    be reachable from `sign_user_data()` inside
    `GoogleAuthenticatorPlugin.authenticateCredentials()`, a request path
    that ends in `transaction.abort()` on `Unauthorized` and would discard
    the mint after a signed URL using it had already been handed to the
    browser.

    - Value of the ``two_factor_authentication_secret`` (from users' profile).
    - Browser info (hash of)
    - The SECRET set for the `ska` (use `plone.app.registry`).

    :param ZPublisher.HTTPRequest request:
    :param Products.PlonePAS.tools.memberdata user:
    :param bool use_browser_hash: If set to True, browser hash is used.
        Otherwise - not. Defaults to True.
    :return string:
    """
    if request is None:
        request = getRequest()

    if user is None:
        user = api.user.get_current()

    settings = get_app_settings()

    ska_secret_key = settings.ska_secret_key
    if not ska_secret_key:
        # Fail closed (CR-02): install-time seeding should already guarantee
        # a non-empty key. An empty value here means installation was
        # skipped or the registry record was cleared out-of-band -- signing
        # with an empty/weak key would silently degrade the 2FA guarantee,
        # so raise instead of minting one. Not caught anywhere: RENAME-11's
        # _dont_swallow_my_exceptions = True turns this into a 500 on the
        # PAS plugin path rather than a swallowed exception falling through
        # to password-only login.
        raise ValueError(
            'ska_secret_key is not set; (re)install imio.googleauthenticator')

    # CR-01: getProperty() with no default returns None for an
    # undeclared/stale-cached property sheet (documented hazard, see
    # CLAUDE.md); len(None) would raise TypeError. Coerce to '' like the
    # sibling get_secret()/get_browser_hash() already do.
    user_secret = user.getProperty('two_factor_authentication_secret') or ''

    if use_browser_hash:
        browser_hash = get_browser_hash(request=request)
    else:
        browser_hash = ''

    return u''.join(
        u'{0}:{1}'.format(len(part), part)
        for part in (user_secret, browser_hash, ska_secret_key)
    )


def is_two_factor_authentication_globally_enabled():
    """
    Checks if the two factor authentication is globally enabled.

    :return bool:
    """
    settings = get_app_settings()
    return settings.globally_enabled


def sign_user_data(request=None, user=None, url='@@google-authenticator-token'):
    """
    Signs the user data with `ska` package. The secret key is `secret_key` to
    be used with `ska` is a combination of:

    - Value of the ``two_factor_authentication_secret`` (from users' profile).
    - Browser info (hash of)
    - The SECRET set for the `ska` (use `plone.app.registry`).

    :param ZPublisher.HTTPRequest request:
    :param Products.PlonePAS.tools.memberdata user:
    :param string url:
    :return string:
    """
    if request is None:
        request = getRequest()

    if user is None:
        user = api.user.get_current()

    # Make sure the secret key always exists
    get_or_create_secret(user)

    secret_key = get_ska_secret_key(request=request, user=user)
    signed_url = sign_url(
        auth_user=user.getUserId(),
        secret_key=secret_key,
        url=url
    )
    return signed_url


def extract_request_data_from_query_string(request_qs):
    """
    Plone seems to strip/escape some special chars (such as '+') from values
    and those chars are quite important for us. This method extracts the vars
    from request QUERY_STRING given and returns them unescaped.

    :FIXME: As stated above, for some reason Plone escapes from special chars
    from the values. If you know what the reason is and if it has some effects
    on security, please make the changes necessary.

    :param string request_qs:
    :return dict:
    """
    request_data = {}

    if not request_qs:
        return request_data

    for part in request_qs.split('&'):
        try:
            key, value = part.split('=', 1)
            request_data.update({key: unquote(value)})
        except ValueError:
            pass

    return request_data


def extract_request_data(request):
    """
    Plone seems to strip/escape some special chars (such as '+') from values
    and those chars are quite important for us. This method extracts the vars
    from request QUERY_STRING given and returns them unescaped.

    :FIXME: As stated above, for some reason Plone escapes from special chars
    from the values. If you know what the reason is and if it has some effects
    on security, please make the changes necessary.

    :param request ZPublisher.HTTPRequest:
    :return dict:
    """
    request_qs = request.get('QUERY_STRING')
    return extract_request_data_from_query_string(request_qs)


def extract_next_url_from_referer(request, quote_url=False):
    """
    Since we override the default Plone functionality (take out the `came_from`
    from the login form for a very strong reason), we want to make sure that
    for users, the "came from" functionality stays intact.
    That why, we check the referer for the `came_from` attributes and if
    present, redirect to that after successful two-factor authentication token
    validation.

    :param request ZPublisher.HTTPRequest:
    :return string: Extracted `came_from` URL.
    """
    referer = request.get('HTTP_REFERER')
    request_qs = urlparse(referer).query
    request_data = extract_request_data_from_query_string(request_qs)
    url = request_data.get('came_from', '')

    if quote_url:
        return quote(url)

    return url


def validate_user_data(request, user, use_browser_hash=True):
    """
    Validates the user data.

    :param ZPublisher.HTTPRequest request:
    :param Products.PlonePAS.tools.memberdata user:
    :return ska.SignatureValidationResult:
    """
    secret_key = get_ska_secret_key(
        request=request, user=user, use_browser_hash=use_browser_hash)
    validation_result = validate_signed_request_data(
        data=extract_request_data(request),
        secret_key=secret_key
    )
    return validation_result


def validate_bar_code_reset_token(stored_token, submitted_token):
    """
    Compares a bar-code reset token against a submitted value in constant
    time, through ``hmac.compare_digest``, refusing to match on any falsy
    operand.

    The stored token is written as a py2 ``str``
    (``request_bar_code_reset.py``'s ``user.setMemberProperties(mapping=
    {'bar_code_reset_token': str(signature)})``) while the value read off
    the request is typically ``unicode``. A naive ``compare_digest(a, b)``
    raises ``TypeError: 'unicode' does not have the buffer interface`` when
    ``a`` and ``b`` are different types on Python 2, so both operands are
    coerced to ``str`` bytes first.

    An absent or empty stored token means no reset was ever requested, so it
    must never match anything -- including an empty submitted value. This is
    a deliberate behaviour change from the previous ``==``/``!=`` equality
    tests, which returned ``True`` for two empty strings.

    A non-ASCII ``unicode`` operand is caught and turned into ``False``
    rather than allowed to escape as ``UnicodeEncodeError`` -- the one place
    in this module where catching an exception on attacker-controlled,
    pre-authentication input is the fail-closed behaviour rather than a
    violation of it: the stored token is always ASCII hex-ish ``ska``
    output, so a non-ASCII submitted value can only be an attacker probing,
    and it must be a clean refusal, not a crash.

    Do not log either operand at any level: the stored value is a secret
    that grants a bar-code reset.

    :param stored_token: The ``bar_code_reset_token`` memberdata property.
    :param submitted_token: The ``signature`` value read from the request.
    :return bool:
    """
    if not stored_token or not submitted_token:
        return False

    try:
        if isinstance(stored_token, unicode):
            stored_token = stored_token.encode('ascii')
        if isinstance(submitted_token, unicode):
            submitted_token = submitted_token.encode('ascii')
    except UnicodeEncodeError:
        return False

    return compare_digest(stored_token, submitted_token)


def has_enabled_two_factor_authentication(user):
    """
    Checks if user has enabled the two-step verification.

    :param Products.PlonePAS.tools.memberdata user:
    :return bool:
    """
    return user.getProperty('enable_two_factor_authentication', False)


def enable_two_factor_authentication_for_users(users=None):
    """
    Enable two-factor authentication for the list of users given.
    """
    if not users:
        users = api.user.get_users()

    for user in users:
        try:
            get_or_create_secret(user)
            if not has_enabled_two_factor_authentication(user):
                user.setMemberProperties(
                    mapping={'enable_two_factor_authentication': True})
        except ValueError:
            # A key failure is not per-user, it is total: skipping every
            # user and returning normally would report a success that did
            # not happen. Let it escape so the callers can turn it into an
            # operator-visible failure instead of a silently absorbed one.
            raise
        except Exception as e:
            logger.debug(str(e))


def disable_two_factor_authentication_for_users(users=None):
    """
    Disable two-factor authentication for the list of users given.
    """
    if not users:
        users = api.user.get_users()

    for user in users:
        try:
            # get_or_create_secret(user)
            if has_enabled_two_factor_authentication(user):
                user.setMemberProperties(
                    mapping={'enable_two_factor_authentication': False})
        except Exception as e:
            logger.debug(str(e))


def _to_unicode_ip(value):
    """
    Coerces a py2 ``str`` to ``unicode`` before it reaches an
    ``ipaddress.ip_address``/``ip_network`` call. ``ipaddress == 1.0.23`` is
    the CPython backport and requires ``unicode``; the distribution
    previously installed under the same module name accepted ``str``.

    :param value:
    :return: ``value.decode('ascii')`` if this helper is given a ``str``,
        ``value`` unchanged otherwise.
    """
    if isinstance(value, str):
        return value.decode('ascii')
    return value


def extract_ip_address_from_request(request=None):
    """
    Extracts client's IP address from request. This is not the safest solution,
    since client may change headers.

    :param ZPublisher.HTTPRequest request:
    :return string:
    """
    if not request:
        request = getRequest()

    ip = request.get('REMOTE_ADDR')
    x_forwarded_for = request.get('HTTP_X_FORWARDED_FOR')

    if x_forwarded_for:
        proxies = [proxy.strip() for proxy in x_forwarded_for.split(',')]

        # Remove the private/reserved hops from the beginning. Uses
        # ipaddress' own notion of "private" rather than a string-prefix
        # match (WR-01: '172.' / '192.' as prefixes wrongly swept up public
        # ranges like 172.217.0.0/16 and 192.0.2.0/24). A hop that doesn't
        # even parse as an IP stops the strip -- it's left in place for the
        # ip_address() call below (CR-02) to reject.
        while proxies:
            try:
                if not ipaddress.ip_address(_to_unicode_ip(proxies[0])).is_private:
                    break
            except ValueError:
                break
            proxies.pop(0)

        # Take the first ip which is not a private one (of a proxy)
        if len(proxies) > 0:
            ip = proxies[0]

    if not ip:
        # No REMOTE_ADDR (seen with the IntegrationTesting test browser, and
        # possibly with a misconfigured front end): there is no client IP to
        # check against the whitelist. `ipaddress.ip_address('')` raises
        # ValueError, which -- now that RENAME-11 stops that being swallowed --
        # would 500 on every single request. Returning None here, and treating
        # it as "not whitelisted" in is_whitelisted_client, keeps the whitelist
        # fail-closed instead of fail-crashed.
        return None

    try:
        return ipaddress.ip_address(_to_unicode_ip(ip))
    except ValueError:
        # Malformed/attacker-controlled IP (bogus X-Forwarded-For value, a
        # legacy "ip:port" entry some proxies emit, ...). Same fail-closed
        # reasoning as the empty-IP case above: treat as "no client IP to
        # check" rather than letting the client 500 the login path.
        logger.debug("Unparseable client IP %r", ip)
        return None


def get_ip_addresses_whitelist(request=None):
    """
    Gets IP addresses white list.

    :param ZPublisher.HTTPRequest request:
    :return list:
    """
    if not request:
        request = getRequest()

    settings = get_app_settings()

    ip_addresses_whitelist = settings.ip_addresses_whitelist

    if ip_addresses_whitelist:
        try:
            ip_addresses_whitelist = [
                ip_address.strip()
                for ip_address in ip_addresses_whitelist.split('\n')
                if ip_address.strip()
            ]
        except Exception as e:
            logger.debug(str(e))
            ip_addresses_whitelist = []

    return ip_addresses_whitelist or []


def get_ip_ranges(list_of_networks):
    """
    Returns a list of IPv4Network or IPv6Network objects from a list of
    single IP addresses ('127.0.0.1') or IP network specs ('127.0.0.0/8').

    :param list list_of_networks:
    :return list: A list of IPv4Network or IPv6Network objects.
    """
    ranges = []
    for net in list_of_networks:
        try:
            ranges.append(ipaddress.ip_network(_to_unicode_ip(net)))
        except ValueError:
            logger.debug("Skipping invalid whitelist entry %r", net)
    return ranges


def is_whitelisted_client(request=None):
    """
    Checks if client's IP address is whitelisted.

    :param ZPublisher.HTTPRequest request:
    :return bool:
    """
    ip_addresses_whitelist = get_ip_addresses_whitelist(request=request)
    whitelisted_ranges = get_ip_ranges(ip_addresses_whitelist)

    ip_address = extract_ip_address_from_request(request=request)
    if ip_address is None:
        return False

    return any(ip_address in ip_range for ip_range in whitelisted_ranges)


def drop_login_failed_msg(request):
    """
    Drop an eventual "Login failed..." status message from the request,
    but keep all other messages by re-adding them.

    Because what ends up in the request is the message translated in the
    user's language, we have to first translate the "Login failed" message
    using the same request(i.e. language), and then filter out the status
    message based on that.

    :param ZPublisher.HTTPRequest request:
    """
    login_failed = ("Login failed. Both login name and password are case "
                    "sensitive, check that caps lock is not enabled.")
    login_failed_translated = translate(
        login_failed, domain='plone', context=request)
    status_messages = IStatusMessage(request)

    msgs = status_messages.show()
    for msg in msgs:
        if msg.message == login_failed_translated:
            # Drop the "Login failed" message
            continue
        status_messages.add(msg.message, msg.type)
