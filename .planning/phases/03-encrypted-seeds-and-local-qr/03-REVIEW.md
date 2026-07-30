---
phase: 03-encrypted-seeds-and-local-qr
reviewed: 2026-07-30T10:27:32Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/subscribers.py
  - src/imio/googleauthenticator/configure.zcml
  - src/imio/googleauthenticator/browser/controlpanel.py
  - src/imio/googleauthenticator/browser/enable_two_factor_authentication_for_all_users.py
  - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
  - src/imio/googleauthenticator/tests/test_helpers.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/tests/test_subscribers.py
  - src/imio/googleauthenticator/tests/test_user_setup.py
  - setup.py
  - base.cfg
  - test-4.3.cfg
  - README.rst
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-07-30T10:27:32Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

This phase's core security property — Fernet-encrypted seeds at rest, fail-closed on a
missing/malformed key, no plaintext fallback — was traced end-to-end and holds up. I
verified, by reading the actual installed `cryptography==3.3.2`/`ipaddress==1.0.23` eggs
and running the relevant snippets under Python 2.7.18 (not just reading the source), that:

- `_get_fernet()` cannot return `None` or a cached instance, and every realistic malformed-
  key shape (missing, non-base64, wrong-length, non-ASCII) ends up raising `ValueError`
  before any plaintext write, confirmed against `cryptography`'s actual `Fernet.__init__`
  (`base64.urlsafe_b64decode` raises `TypeError` for bad base64 on py2, `ValueError` for
  wrong length — matches the code's own comment).
- Every caller of `get_secret`/`get_or_create_secret`/`encrypt_seed`/`decrypt_seed` in the
  reviewed files (`generate_secret`, `get_token_description`, `sign_user_data`,
  `enable_two_factor_authentication_for_users`, `userCreatedHandler`) propagates a crypto
  `ValueError` rather than swallowing it; the only two call sites that catch broadly
  (`reset_bar_code.py`'s `except Exception` and `enable_two_factor_authentication_for_users`'s
  `except Exception as e: logger.debug(...)`) do not wrap any crypto call, and the latter
  re-raises `ValueError` explicitly before the broad clause.
- All three `ipaddress.*()` call sites are coerced through `_to_unicode_ip()`, and
  `AddressValueError`'s parent (`ValueError`, confirmed `UnicodeDecodeError` also subclasses
  `ValueError` on py2) is what the surrounding `except ValueError` blocks actually catch, so
  a non-ASCII/malformed hop still fails closed rather than silently disabling the
  private-hop strip.
- `validate_bar_code_reset_token` refuses on any falsy operand before ever calling
  `hmac.compare_digest`, so an absent/empty stored or submitted token can never authorize a
  reset.
- `subscribers.on_process_starting` never raises and never interpolates the key value,
  only `ENV_VAR_NAME`.
- `base.cfg` carries the key exactly once, in `[testenv]` only; `[instance]` correctly has
  no entry.

What I found instead were quality/robustness gaps around the edges of that core property:
a control-panel save path that persists a state change even when it reports failure, a
bulk-enable loop that can't distinguish "the key itself is broken" from "one user's row is
corrupt" and aborts everyone's enrollment on the latter, a new hard runtime dependency
(Pillow, required by `qrcode.make()`'s default `PilImage` factory — confirmed against the
installed `qrcode==6.1` egg) that never got its version pinned in `test-4.3.cfg`, and two
residual commented-out `logger.debug(secret)` lines that are a standing invitation to leak
the plaintext seed if ever re-enabled during debugging.

No test-file issues were flagged: the new `test_helpers.py`/`test_subscribers.py`/
`test_pas_plugin.py`/`test_user_setup.py` coverage of the fail-closed paths is thorough and
each assertion I spot-checked (README-encryption-flow doc drift, per-call key re-read,
foreign-key `InvalidToken` -> `ValueError`) matches the actual runtime behavior rather than
just re-asserting the implementation.

## Warnings

### WR-01: Control-panel Save persists `globally_enabled=True` even when bulk enrollment fails

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:109-140`
**Issue:** `handleSave()` sets `enrollment_failed = True` and shows an error status message
("...Set the `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` environment variable and try again.") when
`enable_two_factor_authentication_for_users()` raises `ValueError`, and correctly skips the
"Changes saved." message in that case (line 138). But `changes = self.applyChanges(data)`
at line 137 runs unconditionally, regardless of `enrollment_failed` — so the submitted
`globally_enabled=True` value is still written to the registry. The error message implies
nothing took effect ("try again"), but the registry now reads `globally_enabled=True` with
zero users actually enrolled, which (per this phase's own README addition) also means every
subsequent `plone.api.user.create()` call will start raising until the key is fixed. An
admin re-reading the control panel after seeing the error would see the checkbox still
checked and could reasonably (and incorrectly) conclude their attempt to enable it had no
effect at all.
**Fix:**
```python
if globally_enabled is True:
    users = api.user.get_users()
    try:
        enable_two_factor_authentication_for_users(users)
        logger.debug('Enabled')
    except ValueError:
        enrollment_failed = True
        IStatusMessage(self.request).addStatusMessage(
            _(u"Two-step verification could not be enabled for any user: seed "
              u"encryption is unavailable. Set the IMIO_GOOGLEAUTHENTICATOR_SEED_KEY "
              u"environment variable and try again. The 'Globally enabled' setting "
              u"has NOT been saved."),
            "error")
        # Do not persist globally_enabled in this failure branch.
        data.pop('globally_enabled', None)

changes = self.applyChanges(data)
```
(or equivalently, message the admin explicitly that the toggle *was* saved despite the
enrollment failure — either is fine, but the current combination of silent-persist +
"try again" wording is the actual defect).

### WR-02: One corrupt/foreign ciphertext aborts bulk-enable for every other user

**File:** `src/imio/googleauthenticator/helpers.py:564-584`
**Issue:** `enable_two_factor_authentication_for_users()` re-raises `ValueError` (comment:
"A key failure is not per-user, it is total"), but `decrypt_seed()`/`encrypt_seed()` raise
the exact same `ValueError` for two structurally different situations: (a) the
`IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` env var itself is missing/malformed (genuinely total,
correctly re-raised), and (b) a *single* user's stored ciphertext fails to decrypt under an
otherwise-good key (`InvalidToken` inside `decrypt_seed`, e.g. a row left over from a key
rotation without re-encryption, or manual DB tampering — a per-user data problem). Because
`get_or_create_secret()` is called once per user inside the loop and the loop iterates in
whatever order `api.user.get_users()` returns, a single bad row for user #3 out of 5000
aborts the whole call with a `ValueError`, leaving users #4-5000 completely unprocessed even
though their secrets and the key are both fine. The caller (control panel / bulk-enable
view) then reports total failure for what may be a single corrupt record.
**Fix:** Check `get_encryption_key()` once, up front, outside the loop (a real systemic
failure); inside the loop, catch a decrypt-specific failure per user and log+skip instead
of aborting everyone:
```python
def enable_two_factor_authentication_for_users(users=None):
    if get_encryption_key() is None:
        raise ValueError('seed encryption key is not set')
    if not users:
        users = api.user.get_users()
    for user in users:
        try:
            get_or_create_secret(user)
            if not has_enabled_two_factor_authentication(user):
                user.setMemberProperties(
                    mapping={'enable_two_factor_authentication': True})
        except ValueError as e:
            # Per-user decrypt failure (corrupt/foreign ciphertext): log and
            # continue with the remaining users instead of aborting the batch.
            logger.error("Could not enable 2FA for %r: %s", user.getUserName(), e)
        except Exception as e:
            logger.debug(str(e))
```

### WR-03: `Pillow` added as a hard runtime dependency but never pinned in `test-4.3.cfg`

**File:** `setup.py:65`, `base.cfg:27,77`, `test-4.3.cfg`
**Issue:** This phase's `get_barcode_image()` calls `qrcode.make(data)` with no explicit
`image_factory`, which (confirmed against the actual installed `qrcode==6.1` egg,
`qrcode/main.py`) defaults to `from qrcode.image.pil import PilImage`, i.e. Pillow is
required at runtime, not merely optional. `Pillow` was correctly added to
`install_requires` in `setup.py` and to `[buildout] eggs +=` / `[robot] eggs =` in
`base.cfg`, but — unlike every other dependency this phase touched
(`cryptography`, `cffi`, `ipaddress`, `qrcode`, all pinned under the phase's own
"Pins for the encryption/QR/whitelist dependency swap" block) — it has no entry in
`test-4.3.cfg`'s `[versions]`. Per this project's documented convention ("All pins live in
`test-4.3.cfg` `[versions]`... buildout appends resolved pins to that file itself"), this is
a real gap: an unpinned resolution risks pulling a Pillow release that dropped Python 2.7
support (Pillow >= 7.0; the last py2-compatible release is 6.2.2).
**Fix:** Run `make buildout` and commit the Pillow version it appends to `test-4.3.cfg`
(pin to `6.2.2` or the newest 2.7-compatible release).

## Info

### IN-01: `_get_fernet()`'s ASCII-encode step can raise outside its own friendly-error branch

**File:** `src/imio/googleauthenticator/helpers.py:72-83`
**Issue:** `if isinstance(key, unicode): key = key.encode('ascii')` (lines 72-74) runs
before the `try: return Fernet(key) except (ValueError, TypeError):` block (lines 75-83), so
a key value containing non-ASCII characters raises a raw `UnicodeEncodeError` instead of the
intended `"{ENV_VAR_NAME} is set but is not a valid Fernet key"` message. This is not a
fail-closed violation — `UnicodeEncodeError` subclasses `ValueError` (confirmed on Python
2.7.18), so it still surfaces as a `ValueError` and still never returns `None`/a cached
instance — but the operator gets a confusing traceback naming a stray character position
rather than the documented, readable message.
**Fix:** Move the encode inside the try, or add `UnicodeEncodeError` to the except tuple:
```python
try:
    if isinstance(key, unicode):
        key = key.encode('ascii')
    return Fernet(key)
except (ValueError, TypeError):
    raise ValueError(
        '{0} is set but is not a valid Fernet key'.format(ENV_VAR_NAME))
```

### IN-02: Residual commented-out `logger.debug(secret)` lines risk leaking the plaintext seed

**File:** `src/imio/googleauthenticator/helpers.py:191` (`generate_secret`) and `:294`
(`validate_token`)
**Issue:** Both lines are pre-existing (untouched by this phase's diff) but sit directly
inside the two functions this phase's "no seed leakage" requirement is about. `# logger.debug(secret)`
in `generate_secret` and `# logger.debug('secret: {0}'.format(secret))` in `validate_token`
are inert today, but leaving them commented rather than removed is exactly the kind of
"someone re-enables it while debugging a login issue in production" hazard this phase is
explicitly designed to close.
**Fix:** Delete both lines outright rather than leaving them commented.

### IN-03: Dead code in the control panel's "disable for all users" branch

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:131-135`
**Issue:**
```python
elif globally_enabled is False:
    # Disable for all users
    users = api.user.get_users()
    #disable_two_factor_authentication_for_users(users)
    logger.debug('Disabled')
```
`api.user.get_users()` fetches every user and then the result is never used, since the only
consumer of it is commented out. This matches the schema's documented intent
(`IGoogleAuthenticatorSettings.globally_enabled`'s description explicitly says "unchecking
the checkbox does not disable the two-step verification for all users"), so it is not a
functional bug, but the two-line block reads like an accidentally-reverted feature to a
future maintainer and does a needless full user-listing query for nothing.
**Fix:** Remove the unused `users = api.user.get_users()` call and the commented-out line;
keep only `logger.debug('Disabled')` (or drop the branch's body entirely and rely on the
schema description).

---

_Reviewed: 2026-07-30T10:27:32Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
