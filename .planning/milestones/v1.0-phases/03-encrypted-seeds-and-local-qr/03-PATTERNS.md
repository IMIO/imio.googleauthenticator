# Phase 3: Encrypted Seeds and Local QR - Pattern Map

**Mapped:** 2026-07-30
**Files analyzed:** 8 modified source files + 1 new module + 1 modified ZCML + 2 config files +
2 pin files + 1 modified test file (or new test module)
**Analogs found:** 9 / 9 — this phase mostly rewrites existing functions in place; the two
genuinely new artifacts (`subscribers.py`, the `<subscriber>` ZCML entry) have in-repo analogs one
element away in the same file.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/imio/googleauthenticator/helpers.py` (encrypt/decrypt/key funcs) | utility | transform (crypto) | itself, `get_ska_secret_key`/`get_browser_hash` (per-call, fail-soft-vs-fail-closed shape) | role-match |
| `src/imio/googleauthenticator/helpers.py` (`generate_secret`/`get_secret`/`get_or_create_secret`) | utility | CRUD (memberdata property) | itself, current implementation | exact |
| `src/imio/googleauthenticator/helpers.py` (`get_barcode_image`) | utility | transform (render) | itself, current implementation | exact |
| `src/imio/googleauthenticator/helpers.py` (`extract_ip_address_from_request`/`get_ip_ranges`) | utility | transform | itself, current implementation | exact |
| `src/imio/googleauthenticator/subscribers.py` (NEW) | event subscriber | event-driven | `userdataschema.userCreatedHandler` (existing `<subscriber>` in this package) | role-match |
| `src/imio/googleauthenticator/configure.zcml` | config (ZCML) | n/a | itself, the existing `<subscriber>` block (lines 63-67) | exact |
| `src/imio/googleauthenticator/browser/forms/user_setup.py` | controller (z3c.form) | request-response | itself, current `handleSubmit`/`updateFields` | exact |
| `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` | controller (z3c.form) | request-response | itself, current `handleSubmit` (line 104) | exact |
| `src/imio/googleauthenticator/tests/test_helpers.py` | test | request-response/CRUD | `test_helpers.py::TestIPWhitelisting` + Phase 2's monkeypatch-`get_app_settings` shape | exact |
| `src/imio/googleauthenticator/tests/test_subscribers.py` (NEW) | test | event-driven | Phase 2's `test_setuphandlers`-style direct-call unit test | role-match |
| `setup.py` | config | n/a | itself, `install_requires` list | exact |
| `base.cfg` / `test-4.3.cfg` | config | n/a | itself, `[instance] environment-vars` / `[versions]` | exact |

## Pattern Assignments

### `src/imio/googleauthenticator/helpers.py` — new key/Fernet functions (utility, transform)

**Analog:** itself, current imports (lines 1-30) and `get_browser_hash`/`get_ska_secret_key`
(per-call `getRequest()`/`get_app_settings()` pattern, no module-scope caching):
```python
from hashlib import sha1
from urllib import urlencode, unquote, quote
from urlparse import urlparse
from uuid import uuid4
import logging

from zope.component import getUtility
from zope.globalrequest import getRequest
...
from onetimepass import valid_totp

from plone import api
from plone.registry.interfaces import IRegistry

from ska import sign_url, validate_signed_request_data
import ipaddress
import rebus
```
Follow the exact same single-import-per-line, stdlib-then-zope-then-plone-then-package grouping
(`.isort.cfg` `force_single_line`/`force_alphabetical_sort`) for the new block:
```python
import base64
import os

from cryptography.fernet import Fernet, InvalidToken
```
`rebus` import is deleted (its one call site, `generate_secret`, moves to `base64.b32encode`);
`ipaddress` import stays (still used by the whitelist functions, just with the swapped
distribution installed under the same module name).

**Fail-closed shape to copy** — `_get_fernet`/`encrypt_seed`/`decrypt_seed` must never wrap their
own raise in a local `try/except` that swallows it, mirroring how `get_ska_secret_key` never
catches a missing `get_app_settings()` registry record (Phase 2 D-07: `KeyError` propagates
uncaught). Contrast with `get_browser_hash`'s **fail-soft** `except Exception: return ''` — do not
copy that shape here; SEC-03 requires the opposite. Concrete functions to add (from RESEARCH.md
Code Examples, already reviewed against this repo's actual current line numbers — see below):
```python
ENV_VAR_NAME = 'IMIO_GA_SEED_KEY'
CIPHERTEXT_VERSION_PREFIX = 'v1$'


def get_encryption_key():
    return os.environ.get(ENV_VAR_NAME)


def _get_fernet():
    key = get_encryption_key()
    if not key:
        raise ValueError(
            '{0} is not set; refusing to encrypt/decrypt a TOTP seed'.format(ENV_VAR_NAME))
    if isinstance(key, unicode):
        key = key.encode('ascii')
    try:
        return Fernet(key)
    except (ValueError, TypeError) as e:
        raise ValueError('{0} is malformed: {1}'.format(ENV_VAR_NAME, e))
```
Docstrings: match this module's existing `:param Type name:` / `:return type:` reStructuredText
convention (see `get_domain_name`, lines 80-91, for the shortest example of the house style).

---

### `src/imio/googleauthenticator/helpers.py` — `generate_secret`/`get_secret`/`get_or_create_secret` (utility, CRUD)

**Analog:** itself, current lines 94-104 (`generate_secret`), 126-143 (`get_secret`), 145-167
(`get_or_create_secret`):
```python
def generate_secret(user):
    """
    Generates secret for the user.

    :param Products.PlonePAS.tools.memberdata user:
    """
    secret = rebus.b32encode(str(uuid4()))
    # logger.debug(secret)
    user.setMemberProperties(
        mapping={'two_factor_authentication_secret': secret})
    return secret
```
```python
def get_secret(user=None, hashed=False):
    # TODO: Return hashed version if ``hashed`` is set to True.
    if user is None:
        user = api.user.get_current()
    if user:
        secret = user.getProperty('two_factor_authentication_secret')
        # If string returned, then it's likely a set string
        if isinstance(secret, basestring) and secret:
            return secret
```
```python
def get_or_create_secret(user, overwrite=False):
    if user is None:
        user = api.user.get_current()
    if overwrite:
        return generate_secret(user)
    secret = user.getProperty('two_factor_authentication_secret')
    if isinstance(secret, basestring) and secret:
        return secret
    else:
        return generate_secret(user)
```
**Target shape** — same three functions, same public signatures and same `isinstance(...,
basestring)` guard shape, but `generate_secret` seeds with `base64.b32encode(os.urandom(20))` and
stores `encrypt_seed(plaintext_seed)`; `get_secret` and `get_or_create_secret`'s
`user.getProperty(...)` branch call `decrypt_seed(ciphertext)` before returning. Keep the
`# TODO: Return hashed version...` comment and existing dead-code shape untouched — this phase
does not touch the `hashed` parameter. Preserve the commented-out `# logger.debug(secret)` /
never-log-the-secret discipline already present at line 101 — do not add a new debug log for the
plaintext seed or ciphertext anywhere in these three functions (SEC-01/V6.4.1).

---

### `src/imio/googleauthenticator/helpers.py` — `get_barcode_image` (utility, transform/render)

**Analog:** itself, current lines 107-123:
```python
def get_barcode_image(username, domain, secret):
    """
    Get barcode image URL.

    :param string username:
    :param string domain:
    :param string secret:
    :return string:
    """
    params = urlencode({
        'chs': '200x200',
        'chld': 'M|0',
        'cht': 'qr',
        'chl': "otpauth://totp/{0}@{1}?secret={2}".format(
            username, domain, secret)})
    url = "https://chart.googleapis.com/chart?{0}".format(params)
    return url
```
**Target shape** — same signature, same docstring shape, replace the Google Charts URL build with
in-process `qrcode` rendering into a `data:` URI (RESEARCH.md Code Examples has the exact body:
`qrcode.make(otpauth_uri)` → `io.BytesIO()` → `base64.b64encode`). `get_token_description` (lines
170-188) needs **no change** — it already just wraps whatever `get_barcode_image` returns in an
`<img src="{url}">`, so a `data:` URI drops in unchanged. `urlencode` import (line 5) becomes
unused once this function no longer builds a query string — drop it from the `urllib` import if
nothing else in the module still needs it (grep before removing: `quote`/`unquote` are used
elsewhere in this file's `ska` URL-signing helpers, so only drop `urlencode` specifically, keep
`unquote, quote`).

---

### `src/imio/googleauthenticator/helpers.py` — `extract_ip_address_from_request` / `get_ip_ranges` (utility, transform)

**Analog:** itself, current lines 459-513 (`extract_ip_address_from_request`) and 543-557
(`get_ip_ranges`) — note actual current line numbers differ slightly from RESEARCH.md's cited
`:459`/`:496` (the file has grown since that citation was written; `get_ip_ranges` is now at 543,
not 496), but the two call sites RESEARCH.md means are unambiguous — the two `ipaddress.ip_address(
...)` / `ipaddress.ip_network(...)` calls:
```python
    try:
        return ipaddress.ip_address(ip)
    except ValueError:
        ...
```
```python
    for net in list_of_networks:
        try:
            ranges.append(ipaddress.ip_network(net))
        except ValueError:
            logger.debug("Skipping invalid whitelist entry %r", net)
```
**Target shape** — same `try/except ValueError` fail-closed shape (unchanged, already correct
per Phase 1's WR-01/CR-02 hardening), only the argument changes to force `unicode` first, per
BUG-05:
```python
        return ipaddress.ip_address(ip.decode('ascii') if isinstance(ip, str) else ip)
...
            ranges.append(ipaddress.ip_network(net.decode('ascii') if isinstance(net, str) else net))
```
This is a one-line edit at each of the two `ipaddress.*(...)` call expressions — do not restructure
the surrounding `try/except`/logging, which is Phase-1-hardened and must survive unchanged.

---

### `src/imio/googleauthenticator/subscribers.py` (NEW — event subscriber, event-driven)

**Analog:** `src/imio/googleauthenticator/userdataschema.py`'s `userCreatedHandler` — the only
existing subscriber function in this package (module-level `logger`, plain function taking one
`event` argument, no class):
```python
# userdataschema.py — shape to copy (module-level logger, plain function signature)
logger = logging.getLogger("imio.googleauthenticator")

def userCreatedHandler(user, event):
    ...
```
**Target shape** (from RESEARCH.md Code Examples, verified against an installed egg's
`IProcessStarting` subscriber in this exact stack — `Products.PloneMeeting`):
```python
"""
Process-start subscriber: warns loudly if the seed encryption key is absent.
"""
import logging

from imio.googleauthenticator.helpers import get_encryption_key

logger = logging.getLogger("imio.googleauthenticator")


def on_process_starting(event):
    """
    Logs CRITICAL if the encryption key is absent at Zope startup (SEC-08).

    :param zope.processlifetime.IProcessStarting event:
    """
    if not get_encryption_key():
        logger.critical(
            "IMIO_GA_SEED_KEY is not set. Two-factor authentication seed "
            "encryption/decryption will fail closed on every enrollment and "
            "login attempt until this is fixed.")
```
Match this package's `logging.getLogger("imio.googleauthenticator")` string-literal convention
(not `__name__` or `__file__`) — every other module in this package (`helpers.py`,
`browser/forms/user_setup.py`, `browser/forms/reset_bar_code.py`) uses this exact literal.

---

### `src/imio/googleauthenticator/configure.zcml` (config, n/a)

**Analog:** itself, the existing `<subscriber>` element (lines 63-67):
```xml
    <!-- -*- Event fired on user creation -*- -->
    <subscriber
       for="Products.PluggableAuthService.interfaces.authservice.IBasicUser
            Products.PluggableAuthService.interfaces.events.IPrincipalCreatedEvent"
       handler=".userdataschema.userCreatedHandler"
       />
```
**Target shape** — add a second `<subscriber>` block, same file, same indentation style, right
before the closing `</configure>`:
```xml
    <!-- -*- Log CRITICAL at process start if the seed encryption key is absent -*- -->
    <subscriber
       for="zope.processlifetime.IProcessStarting"
       handler=".subscribers.on_process_starting"
       />
```
No new `<include package="zope.processlifetime"/>` line is needed — `IProcessStarting` is a plain
interface import inside `subscribers.py`, not a ZCML directive from that package.

---

### `src/imio/googleauthenticator/browser/forms/user_setup.py` (controller, request-response)

**Analog:** itself, current `handleSubmit` (lines 56-97) and `updateFields` (lines 99-110), read
in full above. **BUG-02 does not reproduce** on this exact current source — `redirect_url` is
bound on every reachable path (`valid_token` True+success sets it in the `try`; `valid_token`
True+exception or `valid_token` False both fall into the `if reason is not None:` block, which
also sets it). **Do not "fix" this** — add a regression test instead (see test section below).

**New failure mode this phase introduces:** `get_token_description()` inside `updateFields` (line
108) now calls through to `get_or_create_secret` → `generate_secret`/`decrypt_seed`, either of
which can raise `ValueError` on a missing/garbage key — currently `updateFields` has no
try/except around this call at all, so it propagates as a plain 500 (matches Phase 1's "plain
500, no custom error view" deferred decision, now exercised here per Open Question 2). Inside
`handleSubmit`, the existing bare `except Exception:` at line 85 **will** catch a `ValueError`
raised by a future `get_or_create_secret`/`generate_secret` call if one is ever added there (none
is added by this phase's `helpers.py` rewrite — `handleSubmit` only calls `validate_token`, not
`get_or_create_secret` — so this is a latent note, not an active bug to fix this phase).

---

### `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` (controller, request-response) — BUG-03

**Analog:** itself, current lines 100-110 (exact code BUG-03 targets):
```python
                bar_code_reset_token = user.getProperty('bar_code_reset_token')
                if bar_code_reset_token != signature_token:
                    reason = _("Invalid bar-code reset token.")
                    IStatusMessage(self.request).addStatusMessage(
                        _("Resetting of the bar-code failed! {0}".format(reason)),
                        'error'
                        )
                    return
```
**Target shape** — encode both sides to `str` before a constant-time compare (RESEARCH.md
Common Pitfalls Pitfall C, exact code):
```python
from hmac import compare_digest
...
                bar_code_reset_token = user.getProperty('bar_code_reset_token') or ''
                if isinstance(bar_code_reset_token, unicode):
                    bar_code_reset_token = bar_code_reset_token.encode('ascii')
                signature_token_bytes = (
                    signature_token.encode('ascii')
                    if isinstance(signature_token, unicode) else signature_token)
                if not compare_digest(bar_code_reset_token, signature_token_bytes):
                    reason = _("Invalid bar-code reset token.")
                    IStatusMessage(self.request).addStatusMessage(
                        _("Resetting of the bar-code failed! {0}".format(reason)),
                        'error'
                        )
                    return
```
Add `from hmac import compare_digest` to the existing import block (line 4 area), matching this
file's existing stdlib-then-zope-then-z3c-then-plone-then-package grouping (compare against the
current block at lines 4-17).

---

### `src/imio/googleauthenticator/tests/test_helpers.py` (test, request-response/CRUD)

**Analog:** existing `TestIPWhitelisting` class + Phase 2's monkeypatch-`get_app_settings` shape
(`02-PATTERNS.md`'s "Shared Patterns" section, copied verbatim below) + import block:
```python
import unittest2 as unittest

from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

from imio.googleauthenticator.helpers import extract_ip_address_from_request
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_browser_hash
from imio.googleauthenticator.helpers import get_ip_addresses_whitelist
from imio.googleauthenticator.helpers import get_ip_ranges
```
New tests add single-name imports the same way: `from imio.googleauthenticator.helpers import
encrypt_seed`, `decrypt_seed`, `generate_secret`, `get_secret`, `get_or_create_secret`,
`get_barcode_image`, `get_encryption_key`.

**Fail-closed monkeypatch shape** (Phase 2 `02-PATTERNS.md` Shared Patterns, apply to
`get_encryption_key` instead of `get_app_settings`):
```python
from imio.googleauthenticator import helpers

original = helpers.get_encryption_key
helpers.get_encryption_key = lambda: None   # or lambda: 'not-a-valid-fernet-key'
try:
    with self.assertRaises(ValueError):
        helpers.decrypt_seed(u'v1$whatever')
finally:
    helpers.get_encryption_key = original
```
This is RESEARCH.md's own "Fail-closed test shape" section verbatim — cited here because it
already matches this file's own established monkeypatch-and-restore convention exactly (same
`test_helpers.py:46-58` shape Phase 2 cited for `get_app_settings`).

**Seed-entropy/round-trip test** (closes Pitfall A — the class of bug a mock-based test would
hide): call the real `generate_secret()`/`decrypt_seed()`, not a mocked one, and assert
`len(base64.b32decode(seed)) == 20` plus a real `onetimepass.get_hotp()` round-trip, with
`IMIO_GA_SEED_KEY` set to a real `Fernet.generate_key()` value for the test (per DOC-03: tests set
the env var themselves).

**QR data-URI test:** assert `get_barcode_image(...)` return value `.startswith('data:image/png;
base64,')` and does **not** contain `'googleapis.com'` — same assertion-on-real-output style as
`TestIPWhitelisting`'s existing tests (no mocking of `qrcode` itself).

---

### `src/imio/googleauthenticator/tests/test_subscribers.py` (NEW — test, event-driven)

**Analog:** Phase 2's plain-function-call unit-test style (`02-PATTERNS.md`'s
`test_registry_records_exist_after_install`-style direct call, no full Zope boot needed) —
`on_process_starting` takes a stub event nobody inspects:
```python
import unittest2 as unittest

from imio.googleauthenticator import subscribers


class TestOnProcessStarting(unittest.TestCase):

    def test_logs_critical_when_key_absent(self):
        original = subscribers.get_encryption_key
        subscribers.get_encryption_key = lambda: None
        try:
            with self.assertRaises(Exception):
                pass  # placeholder -- assert on logger.critical call instead of an exception,
                      # e.g. via assertLogs / a stub logger, matching this repo's logging test
                      # conventions if any exist, else a simple monkeypatched logger.critical
        finally:
            subscribers.get_encryption_key = original
```
No existing test in this package asserts on a `logger.critical(...)` call — this is genuinely new
test machinery (see "No Analog Found" below); a plain `unittest2.TestCase`, no
`IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` layer needed since `on_process_starting` takes no
Zope-state-dependent argument.

---

### `setup.py` (config, n/a)

**Analog:** itself, current `install_requires` (lines 55-64):
```python
    install_requires = [
        'setuptools',
        # -*- Extra requirements: -*-
        'plone.api>=1.1.0',
        'plone.directives.form>=1.1',
        'onetimepass==0.2.2',
        'ska>=1.1',
        'rebus>=0.1',
        'py2-ipaddress>2.0.1',
    ],
```
**Target shape** — remove `rebus>=0.1` and `py2-ipaddress>2.0.1`, add the three new pins:
```python
    install_requires = [
        'setuptools',
        # -*- Extra requirements: -*-
        'plone.api>=1.1.0',
        'plone.directives.form>=1.1',
        'onetimepass==0.2.2',
        'ska>=1.1',
        'cryptography==3.3.2',
        'ipaddress==1.0.23',
        'qrcode==6.1',
    ],
```

---

### `base.cfg` / `test-4.3.cfg` (config, n/a) — SEC-07/DOC-03

**Analog:** `base.cfg`, current `[instance]`/`[test]`/`[testenv]` (lines 39-52):
```ini
[instance]
environment-vars +=
    PYTHONBREAKPOINT pdbp.set_trace
eggs +=
    ${buildout:eggs}
zcml +=

[test]
environment = testenv
initialization +=
    os.environ['PYTHONBREAKPOINT'] = 'pdbp.set_trace'

[testenv]
zope_i18n_compile_mo_files = true
```
**Target shape** — add `IMIO_GA_SEED_KEY` to both `[instance] environment-vars` (real value
supplied out-of-repo by Puppet's `concat::fragment`, per the roadmap's phase notes — this repo's
`base.cfg` only needs the variable *declared*, matching how `PYTHONBREAKPOINT` is declared without
its value being a repo secret) and `[testenv]` with an obviously-fake value for `bin/test`:
```ini
[instance]
environment-vars +=
    PYTHONBREAKPOINT pdbp.set_trace
    IMIO_GA_SEED_KEY ${:_buildout_section_name_}  # [ASSUMED] real value injected by Puppet; see DOC-03
...
[testenv]
zope_i18n_compile_mo_files = true
IMIO_GA_SEED_KEY = obviously-fake-test-key-not-a-real-fernet-key
```
Note per Pitfall E: **do not** edit `.github/workflows/package-test.yml` — CI inherits the key
transitively through `[testenv]` already (verified in RESEARCH.md by reading the reusable
workflow's source directly). The exact `[instance]` value/syntax for a real Fernet key in
`environment-vars` needs a `checkpoint:human-verify` per RESEARCH.md's package-legitimacy note —
flag this in the plan rather than guessing the buildout `environment-vars` value substitution
syntax without testing it against a real `bin/buildout` run.

**`test-4.3.cfg`** `[versions]` — same file Phase 2 touched for other pins; add:
```ini
cryptography = 3.3.2
cffi = 1.15.1
ipaddress = 1.0.23
qrcode = 6.1
```
and remove the existing `py2-ipaddress = 3.4.2` (line 106) and `rebus = 0.2` (line 108) lines.
Buildout's own `update-versions-file = test-4.3.cfg` mechanism (documented in CLAUDE.md) will
re-append resolved versions after the first `bin/buildout` run — commit whatever it appends.

## Shared Patterns

### Per-call env var read, never module scope
**Source:** this phase's own design (RESEARCH.md Pattern 1), explicitly inverted from
`imio.helpers/__init__.py:44-55`'s `SSO_APPS_CLIENT_SECRET` module-scope pattern (not in this
repo — a sibling `server.dmsmail` package, cited for contrast only).
**Apply to:** `get_encryption_key()` in `helpers.py`; every call site (`_get_fernet`,
`subscribers.on_process_starting`) must call `get_encryption_key()` fresh, never cache its result
in a module-level constant.

### Fail-closed via propagation, not a caught fallback
**Source:** Phase 2's `get_app_settings()` `KeyError` propagation (D-07), reused as the
precedent for this phase's `ValueError` propagation from `_get_fernet`/`encrypt_seed`/
`decrypt_seed`.
**Apply to:** every new crypto function in `helpers.py`; never add a local `except ValueError`
around these that returns `None`/plaintext/a default — this is the one mistake that silently
undoes SEC-01 through SEC-03 (RESEARCH.md's own framing, repeated here because it's the single
most important invariant in this phase).

### `str`/`unicode` bytes discipline at every crypto/comparison boundary
**Source:** `helpers.py`'s existing `.decode('ascii')`/`isinstance(x, str)` coercions in
`extract_ip_address_from_request` (new, this phase) and the pattern this phase newly establishes
in `encrypt_seed`/`decrypt_seed`/BUG-03's `compare_digest` fix.
**Apply to:** `_get_fernet` (key), `encrypt_seed`/`decrypt_seed` (seed/ciphertext),
`reset_bar_code.py`'s BUG-03 fix (reset token) — `Fernet()`/`.encrypt()`/`.decrypt()` and
`hmac.compare_digest` all raise `TypeError` on a `str`/`unicode` mismatch on Python 2; encode to
`str`/`bytes` explicitly before calling any of them, never rely on Plone's free `str`/`unicode`
coercion of memberdata properties.

### Single-import-per-line, `.isort.cfg`-compliant import blocks
**Source:** every existing module in this package (`helpers.py`, `test_helpers.py`,
`reset_bar_code.py`).
**Apply to:** `subscribers.py`'s new imports, `helpers.py`'s new `cryptography`/`base64`/`os`
imports, `reset_bar_code.py`'s new `from hmac import compare_digest`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `subscribers.py`'s `on_process_starting` test asserting a `logger.critical(...)` call | test | event-driven | No existing test in this package asserts on a logger call; closest is `test_helpers.py`'s monkeypatch-and-restore shape, reused for the collaborator (`get_encryption_key`) but not for asserting the log itself — pick `assertLogs` (unittest2 may lack it on py2; verify) or a simple stub `logger.critical` swap |
| `IMIO_GA_SEED_KEY` buildout `environment-vars` real-value injection syntax | config | n/a | No existing `environment-vars` entry in this repo carries a "value supplied elsewhere" placeholder (`PYTHONBREAKPOINT` is fully inline); the Puppet-side mechanism is out of this repo per ROADMAP's "External Dependency" note — do not guess the substitution syntax, verify against a real `bin/buildout` run first |
| Fernet key generation one-liner for `[testenv]`'s fake value | config | n/a | Not a code file; RESEARCH.md's `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"` one-liner is the source, no in-repo analog needed |

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/helpers.py`,
`src/imio/googleauthenticator/subscribers.py` (does not yet exist — checked for absence),
`src/imio/googleauthenticator/configure.zcml`,
`src/imio/googleauthenticator/userdataschema.py` (subscriber shape reference),
`src/imio/googleauthenticator/browser/forms/{user_setup.py,reset_bar_code.py}`,
`src/imio/googleauthenticator/tests/test_helpers.py`, `setup.py`, `base.cfg`, `test-4.3.cfg`,
plus `.planning/phases/02-registry-seeding-and-import-step-ordering/02-PATTERNS.md` for the
monkeypatch/test-shape precedent.
**Files read:** 11
**Pattern extraction date:** 2026-07-30
