---
phase: 01-rename-and-fail-closed
reviewed: 2026-07-29T09:30:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - docs/conf.py
  - docs/index.rst
  - src/imio/__init__.py
  - src/imio/googleauthenticator/browser/controlpanel.py
  - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
  - src/imio/googleauthenticator/browser/forms/token.py
  - src/imio/googleauthenticator/browser/forms/user_setup.py
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/locales/en/LC_MESSAGES/imio.googleauthenticator.po
  - src/imio/googleauthenticator/locales/fr/LC_MESSAGES/imio.googleauthenticator.po
  - src/imio/googleauthenticator/locales/imio.googleauthenticator.pot
  - src/imio/googleauthenticator/locales/nl/LC_MESSAGES/imio.googleauthenticator.po
  - src/imio/googleauthenticator/pas_plugin.py
  - src/imio/googleauthenticator/profiles/default/imio.googleauthenticator.marker.txt
  - src/imio/googleauthenticator/profiles/default/metadata.xml
  - src/imio/googleauthenticator/rebuild_i18n.sh
  - src/imio/googleauthenticator/setuphandlers.py
  - src/imio/googleauthenticator/testing.py
  - src/imio/googleauthenticator/tests/test_generic.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/www/add_google_authenticator_form.zpt
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-29T09:30:00Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

The rename (`collective.googleauthenticator` -> `imio.googleauthenticator`) is clean and
consistent in the files reviewed: i18n domain, GenericSetup profile id, resource ids
(`++resource++imio.googleauthenticator/*`), browser layer, `meta_type`, the namespace
declaration in `src/imio/__init__.py`, and the `PAS_TITLE`/`PAS_ID` constants all agree with
the new package path. Grepping the reviewed tree for `collective.` in source (Python/ZCML/
XML/PT/PO) turns up nothing. The three msgid corrections (D-18) are consistently reflected
across `.pot` and all three `.po` catalogues.

The real problem is the other half of this phase: `_dont_swallow_my_exceptions = True` on
`GoogleAuthenticatorPlugin` (commit `60f377f`) makes *every* unhandled exception raised
anywhere inside `authenticateCredentials` propagate as an uncaught HTTP 500 instead of being
silently swallowed by PAS's `reraise()` and falling through to the next plugin. The commit
correctly found and fixed two call sites its own new test happened to exercise (empty
`REMOTE_ADDR`, `getProperty('username')`), but tracing the rest of the exception-class
(`NameError, AttributeError, KeyError, TypeError, ValueError` — PAS's
`_SWALLOWABLE_PLUGIN_EXCEPTIONS`) through the same method's call graph turns up three more
unguarded paths, none of which are covered by the new test
(`test_plugin_exception_is_not_swallowed` only injects via `is_whitelisted_client` itself, not
via its callees, and not via `api.user.get`). Two of the three are trivially triggerable in
normal operation (an unmatched username; a trailing blank line in the whitelist textarea), and
one is remotely triggerable by an unauthenticated client via a request header. Each turns
login into a hard, site-wide crash rather than a graceful "authentication failed" — the
opposite of the fail-closed intent documented in the code's own `RENAME-11` comment ("keeps the
whitelist fail-closed instead of fail-crashed").

I checked one candidate finding from an earlier pass of this review (a `KeyError` on
`credentials['login']` in `pas_plugin.py:94`) against the actual `Products.PluggableAuthService`
1.11.3 source used by this buildout: `_extractUserIds` unconditionally executes
`credentials['login'] = self.applyTransform(credentials.get('login'))` before calling any
`IAuthenticationPlugin.authenticateCredentials`, so the `login` key is always present (possibly
`None`) by the time this plugin's code runs — that finding does not reproduce and has been
dropped rather than carried forward.

## Critical Issues

### CR-01: Unmatched username crashes every failed login attempt

**File:** `src/imio/googleauthenticator/pas_plugin.py:99-101`
**Issue:** `api.user.get(username=login)` returns `None` whenever `login` does not match an
existing account (mistyped username, a bot probing usernames, or simply a user who
fat-fingers their login before their password — confirmed via `plone.api.user.get()`'s
`get_member_by_login_name(..., raise_exceptions=False)`). The very next line calls
`user.getUserName()` unconditionally:
```python
user = api.user.get(username=login)
logger.debug("Found user: {0}".format(user.getUserName()))
```
`None.getUserName()` raises `AttributeError`, one of PAS's `_SWALLOWABLE_PLUGIN_EXCEPTIONS`.
Before this phase that exception was silently absorbed by `reraise()`/`_extractUserIds`, so a
bad username simply fell through to the next auth plugin. Now that
`_dont_swallow_my_exceptions = True` is set on this plugin, the same `AttributeError`
propagates unhandled: every login attempt with an unknown username 500s instead of showing
"Login failed". This is the single most common failed-login case, and it is not exercised by
any test — every test in `test_pas_plugin.py` that reaches `authenticateCredentials` uses
`TEST_USER_NAME`, a valid account.
**Fix:**
```python
user = api.user.get(username=login)
if user is None:
    return None

logger.debug("Found user: {0}".format(user.getUserName()))
```

### CR-02: Malformed/attacker-controlled `X-Forwarded-For` crashes every authenticated request

**File:** `src/imio/googleauthenticator/helpers.py:433-469` (`extract_ip_address_from_request`)
**Issue:** The fix added in `60f377f` only guards the *empty*-IP case:
```python
if not ip:
    return None

return ipaddress.ip_address(ip)
```
`ip` can come straight from the client-supplied `HTTP_X_FORWARDED_FOR` header (`ip =
proxies[0]`, a few lines above, after only stripping known-private prefixes — see WR-01). Any
non-empty but unparseable value (`X-Forwarded-For: not-an-ip`, a legacy `ip:port` entry some
proxies emit, or a value deliberately crafted to survive the private-prefix strip) passes the
`if not ip` guard and reaches `ipaddress.ip_address(ip)`, raising `ValueError`. This function is
called from `is_whitelisted_client()`, the very first statement of
`authenticateCredentials`. With `_dont_swallow_my_exceptions = True`, this `ValueError` is no
longer swallowed — it crashes the request. Any request that reaches this plugin (a login-form
POST, or any request carrying a still-valid `__ac` cookie) can be forced to 500 simply by
sending a bogus `X-Forwarded-For` value: an unauthenticated, client-controlled denial of
service against the login path, and the exact bug class this same commit already fixed once
(for "IP missing") but not for "IP malformed".
**Fix:**
```python
if not ip:
    return None
try:
    return ipaddress.ip_address(ip)
except ValueError:
    logger.debug("Unparseable client IP %r", ip)
    return None
```

### CR-03: A trailing blank line in the admin whitelist setting crashes login site-wide

**File:** `src/imio/googleauthenticator/helpers.py:472-523` (`get_ip_addresses_whitelist`, `get_ip_ranges`, `is_whitelisted_client`)
**Issue:** `get_ip_addresses_whitelist` splits the control panel's `ip_addresses_whitelist`
`Text` field on `\n` and strips each line, but never drops empty lines:
```python
ip_addresses_whitelist = ip_addresses_whitelist.split('\n')
ip_addresses_whitelist = [ip_address.strip() for ip_address in ip_addresses_whitelist]
```
A value that ends with a newline — the ordinary result of editing a multi-line textarea and
hitting Enter after the last address — produces a trailing `''` entry. `get_ip_ranges` then
calls `ipaddress.ip_network('')` for it:
```python
def get_ip_ranges(list_of_networks):
    return [ipaddress.ip_network(net) for net in list_of_networks]
```
which raises `ValueError`, uncaught, from inside `is_whitelisted_client()` — again the first
call in `authenticateCredentials`. Same mechanism as CR-01/CR-02: previously swallowed by PAS
(silently falling through to `source_users`, a latent 2FA-bypass path in its own right), now
an unhandled exception that 500s **every** login attempt for **every** user the moment an
admin saves a whitelist that ends in a blank line — a plausible, easy-to-hit misconfiguration,
not an edge case.
**Fix:**
```python
ip_addresses_whitelist = [
    ip.strip() for ip in ip_addresses_whitelist.split('\n') if ip.strip()
]
```
and/or make `get_ip_ranges` defensive against any one bad entry:
```python
def get_ip_ranges(list_of_networks):
    ranges = []
    for net in list_of_networks:
        try:
            ranges.append(ipaddress.ip_network(net))
        except ValueError:
            logger.debug("Skipping invalid whitelist entry %r", net)
    return ranges
```

## Warnings

### WR-01: `PRIVATE_IPS_PREFIX` treats all of `172.0.0.0/8` and `192.0.0.0/8` as private

**File:** `src/imio/googleauthenticator/helpers.py:444`
**Issue:** `PRIVATE_IPS_PREFIX = ('10.', '172.', '192.', )` is used to strip "private" hops
from the front of an `X-Forwarded-For` chain before picking "the" client IP. String-prefix
matching means `'172.'` strips all of `172.0.0.0/8` (only `172.16.0.0/12` is actually RFC1918
private — e.g. Google's public `172.217.0.0/16` gets treated as private), and `'192.'` strips
all of `192.0.0.0/8` (only `192.168.0.0/16` is private — e.g. `192.0.2.0/24` TEST-NET is
public). A client whose real address happens to start with one of these prefixes gets
silently skipped, and the *next*, fully attacker-controlled entry in the chain is used
instead — undermining the IP-whitelist feature's trust model.
**Fix:** Use `ipaddress.ip_address(candidate).is_private` per hop, or narrow the prefixes to
the real private CIDR blocks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).

### WR-02: Mutable default arguments (`users=[]`)

**File:** `src/imio/googleauthenticator/helpers.py:399`, `src/imio/googleauthenticator/helpers.py:416`
**Issue:** `enable_two_factor_authentication_for_users(users=[])` and
`disable_two_factor_authentication_for_users(users=[])` use a mutable default argument.
Neither function mutates the default list in place today (both only read it via `if not
users:`), so it is not currently exploited, but it is the classic Python footgun the moment
either function grows an `.append()`/`.remove()`, and it costs nothing to avoid now.
**Fix:** `def enable_two_factor_authentication_for_users(users=None): if not users: users = api.user.get_users()`

### WR-03: `str(username)` can raise `UnicodeEncodeError` for non-ASCII usernames

**File:** `src/imio/googleauthenticator/browser/forms/token.py:103-104`
**Issue:**
```python
self.context.acl_users.session._setupSession(
    str(username), self.context.REQUEST.RESPONSE)
```
`username` is `self.request.get('auth_user', '')`, which Zope typically hands back as
`unicode`. `str(unicode_value)` implicitly encodes as ASCII in Python 2 and raises
`UnicodeEncodeError` (a `ValueError` subclass) for any non-ASCII character — a real risk in a
Belgian/French-locale deployment where usernames or logins may contain accented characters.
This crashes the final, successful step of 2FA login, i.e. after the user has already entered
a correct token, turning what should be a successful login into a 500.
**Fix:** `username.encode('utf-8') if isinstance(username, unicode) else username`, or drop
the `str()` call — `_setupSession` accepts unicode on this stack.

### WR-04: Raw exception text surfaced to end users via status messages

**File:** `src/imio/googleauthenticator/browser/forms/reset_bar_code.py:120-121`, `src/imio/googleauthenticator/browser/forms/user_setup.py:85-86`
**Issue:** Both forms catch every exception on the success path and echo `str(e)` straight
back to the browser:
```python
except Exception as e:
    reason = _(str(e))
...
IStatusMessage(self.request).addStatusMessage(_("Setup failed! {0}".format(reason)), 'error')
```
`.claude/CLAUDE.md`'s security constraints state the seed/secret material "never lives ... in
a log line, or an exception message" — this pattern is an easy invariant to violate the next
time this try block is touched (any exception constructed with a secret-bearing argument would
render straight to the browser). Independent of secrets, echoing raw Python exception text to
end users is also a general information-disclosure smell.
**Fix:** Log `str(e)` server-side at `debug`/`exception` level and show a generic user-facing
message instead of the raw exception text.

### WR-05: TOTP secret sent to a third-party HTTP endpoint to render the QR code

**File:** `src/imio/googleauthenticator/helpers.py:107-123` (`get_barcode_image`)
**Issue:** The TOTP secret is embedded in plaintext inside an `otpauth://` URL and shipped as
a query parameter over HTTPS to `chart.googleapis.com` to render the QR code server-side,
meaning the raw 2FA seed leaves this server and transits a third party on every setup/reset.
Pre-existing behaviour carried over unchanged by the rename, but it sits in a reviewed file
and is directly at odds with `.claude/CLAUDE.md`'s stated secret-handling bar ("the seed
encryption key never lives in the ZODB — nor in a memberdata property, a log line, or an
exception message") and this project's own documented intent to depend on `qrcode==6.1`
specifically because it is "pure Python, renders in-process, so no system package and no seed
in argv." Flagging since the dependency is already available but not used here.
**Fix:** Render the QR code in-process with the `qrcode` package instead of delegating to the
Google Charts API.

## Info

### IN-01: Stale Sphinx doc version

**File:** `docs/conf.py:58,60`
**Issue:** `version = '0.2.5'` / `release = '0.2.5'`, unchanged by this phase, while
`setup.py` carries `1.0.0.dev0` after this same rename work. Pre-existing drift (no diff
touches these lines), noted for completeness.
**Fix:** Bump `version`/`release` in `docs/conf.py` alongside the next version tag.

### IN-02: Dead code / unused import for the "disable for all users" path

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:99-101,114-118`
**Issue:** `disable_two_factor_authentication_for_users` is imported and `users =
api.user.get_users()` is computed in the `elif globally_enabled is False:` branch, but the
actual call is commented out (`#disable_two_factor_authentication_for_users(users)`). This
matches the field's own description ("unchecking the checkbox does not disable... for all
users"), so the behaviour itself looks intentional, but the dead call, the unused import, and
the now-pointless `api.user.get_users()` fetch should be removed so a future reader isn't left
wondering whether this is a bug or a deliberate no-op.
**Fix:** Remove the commented-out call, the unused `disable_two_factor_authentication_for_users`
import, and the unused `users = api.user.get_users()` in that branch.

### IN-03: `hashed` parameter accepted but silently ignored

**File:** `src/imio/googleauthenticator/helpers.py:126-142` (`get_secret`)
**Issue:** `get_secret(user=None, hashed=False)` documents and accepts a `hashed` flag
(`# TODO: Return hashed version if hashed is set to True.`) that is never implemented —
any caller passing `hashed=True` silently gets the plaintext secret back.
**Fix:** Either implement the hashed-return path or drop the dead `hashed` parameter so
callers cannot be misled into believing it does something.

---

_Reviewed: 2026-07-29T09:30:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
