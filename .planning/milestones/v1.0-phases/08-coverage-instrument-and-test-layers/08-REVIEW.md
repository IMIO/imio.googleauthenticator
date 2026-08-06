---
phase: 08-coverage-instrument-and-test-layers
reviewed: 2026-08-05T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - .github/workflows/package-test.yml
  - src/imio/googleauthenticator/__init__.py
  - src/imio/googleauthenticator/browser/controlpanel.py
  - src/imio/googleauthenticator/browser/disable_two_factor_authentication.py
  - src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/testing.py
  - src/imio/googleauthenticator/tests/base.py
  - src/imio/googleauthenticator/tests/test_adapter.py
  - src/imio/googleauthenticator/tests/test_challenge.py
  - src/imio/googleauthenticator/tests/test_controlpanel.py
  - src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py
  - src/imio/googleauthenticator/tests/test_generic.py
  - src/imio/googleauthenticator/tests/test_helpers.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/tests/test_request_bar_code_reset.py
  - src/imio/googleauthenticator/tests/test_reset_bar_code.py
  - src/imio/googleauthenticator/tests/test_security.py
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
  - src/imio/googleauthenticator/tests/test_token.py
  - src/imio/googleauthenticator/tests/test_user_setup.py
  - src/imio/googleauthenticator/userdataschema.py
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-08-05T00:00:00Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

This phase's diff (`.github/workflows/package-test.yml`, `__init__.py`, `browser/controlpanel.py`,
`browser/disable_two_factor_authentication.py`, `browser/forms/request_bar_code_reset.py`,
`helpers.py`, `testing.py`, `tests/base.py`, `userdataschema.py`, plus the full test-layer
suite) is dominated by isort/formatting cleanup, a CI switch from `bin/test` to
`bin/test-coverage`, a testing-layer simplification (dropping the unused
`IntegrationTesting`/`ZSERVER_FIXTURE` bases), and a very large, carefully-documented test
suite covering TOTP drift/replay, lockout, recovery codes and coexistence concerns. The
bulk of the test code is thorough and self-auditing (non-vacuity controls throughout).

The production-code changes are smaller but contain one genuine functional bug (a
mis-shaped exception handler in the bar-code-reset-request form that turns a routine
SMTP-rejection into an unhandled 500 instead of the graceful failure path every sibling
branch uses), plus several exception-handling and dead-code quality issues in `helpers.py`
and `browser/controlpanel.py` that weaken the "never silently swallow a security-relevant
failure" discipline this codebase otherwise holds itself to.

## Critical Issues

### CR-01: `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)` never actually reaches this form's error-handling path — a rejected recipient 500s instead of failing gracefully

**File:** `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:112-113`
**Issue:**

```python
except SMTPRecipientsRefused:
    raise SMTPRecipientsRefused('Recipient address rejected by server')
```

This is the only exception handler in `handleSubmit` that does not feed into the
function's `reason = ...` / `IStatusMessage(..., 'error')` graceful-failure convention.
The re-raised `SMTPRecipientsRefused` is **not** a `ValueError`, so it is not caught by
the enclosing `except ValueError:` a few lines below (`request_bar_code_reset.py:130`) —
it propagates straight out of `handleSubmit` as an unhandled exception. Every other
failure in this method (invalid username, non-site-local user, a broken encryption key,
any other exception during signing/mailing) ends with a translated status message on a
page the anonymous caller can still read; this one alone produces a bare 500 error page.

This is a realistic, unprivileged, user-triggerable path: a mistyped or bounced email
address on the user's own account is exactly the kind of input this whole method exists
to handle gracefully, and it is currently the one branch with zero test coverage
(`tests/test_request_bar_code_reset.py` never exercises `SMTPRecipientsRefused`).

The `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)` construct as written
achieves nothing except discarding the original exception's `recipients` payload before
re-raising an equivalent, still-uncaught exception — it reads as a `ValueError` that was
never actually converted.

**Fix:**
```python
except SMTPRecipientsRefused:
    logger.exception("Bar-code reset email refused for %r", username)
    reason = _("An unexpected error occurred.")
```
(or extend the outer `except ValueError:` to also catch `SMTPRecipientsRefused`, but
raising a plain, caught exception is the smaller diff and matches the existing
`except ValueError:` sibling immediately below it.)

## Warnings

### WR-01: Bulk enable/disable silently swallow non-`ValueError` per-user failures at debug level

**File:** `src/imio/googleauthenticator/helpers.py:1009-1046`
**Issue:** `enable_two_factor_authentication_for_users` re-raises `ValueError` (correctly,
per its own comment, since a broken encryption key is a total failure) but any *other*
exception for an individual user — `PropertyValueError`, `AttributeError` on a malformed
member, etc. — is caught by the trailing `except Exception as e: logger.debug(str(e))`
and silently skipped. `disable_two_factor_authentication_for_users` has the identical
pattern with no `ValueError` carve-out at all. Both are invoked from
`browser/controlpanel.py`'s "enable/disable for all users" control-panel action, which
then reports a blanket `"Changes saved."` / `"info"` status message with no indication
that some users were skipped. This is the same class of "silent security-control
partial-failure" this codebase's `CLAUDE.md` and inline comments elsewhere (CR-02,
T-03-21) explicitly call out as the failure mode to avoid — here it survives for every
failure mode *except* a broken encryption key.
**Fix:** Collect the per-user exceptions and either re-raise/aggregate them, or log at
`logger.warning`/`logger.error` and surface a count of skipped users in the control
panel's status message, rather than a bare `logger.debug`.

### WR-02: `elif globally_enabled is False:` branch fetches `users` and never uses it

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:149-153`
**Issue:**
```python
elif globally_enabled is False:
    # Disable for all users
    users = api.user.get_users()
    # disable_two_factor_authentication_for_users(users)
    logger.debug('Disabled')
```
`users = api.user.get_users()` fetches every user in the site and is then discarded —
the only call that would use it is commented out. This is dead code left over from the
deferred MFA-14-adjacent decision; as written it does nothing but iterate the whole user
catalogue on every "Save" with `globally_enabled` unchecked.
**Fix:** Delete the unused `users = api.user.get_users()` line (or move it inside the
commented-out call it exists to support), so the branch reads as the intentional no-op it
is documented to be.

### WR-03: Error status message is composed before translation, so it can never be localized

**File:** `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:136-140`
**Issue:**
```python
if reason is not None:
    IStatusMessage(self.request).addStatusMessage(
        _("Request for bar-code reset is failed! {0}".format(reason)),
        'error'
        )
```
`reason` is already a translatable `zope.i18nmessageid.Message` (e.g. `_("Invalid
username.")`, `_("An unexpected error occurred.")`). `.format(reason)` renders it to its
default (English) text *before* the outer `_(...)` call ever runs, so the resulting msgid
is a dynamically-built string (`"Request for bar-code reset is failed! Invalid
username."`) that will never appear in any `.po` catalogue. The message is therefore
always shown in English regardless of the visitor's locale, and `i18ndude rebuild-pot`
cannot extract it as two independently translatable pieces.
**Fix:** Use a message with a mapping instead:
```python
IStatusMessage(self.request).addStatusMessage(
    _(u"bar_code_reset_request_failed",
      default=u"Request for bar-code reset failed: ${reason}",
      mapping={'reason': reason}),
    'error')
```

### WR-04: `userCreatedHandler` unconditionally debug-logs the encrypted secret ciphertext on every user creation

**File:** `src/imio/googleauthenticator/userdataschema.py:137-138`
**Issue:**
```python
logger.debug(user.getProperty('enable_two_factor_authentication'))
logger.debug(user.getProperty('two_factor_authentication_secret'))
```
These two lines run unconditionally at the end of `userCreatedHandler`, for every new
user, regardless of whether `globally_enabled` was true. The second line writes the
user's encrypted TOTP seed ciphertext to the application log at debug level. This is
inconsistent with the deliberate discipline the rest of the codebase applies to this
exact property — `helpers.generate_secret` keeps its own `# logger.debug(secret)` line
commented out specifically to avoid ever writing seed material to a log, and
`validate_token`/`validate_recovery_code` go out of their way to log nothing that could
identify a user or a secret. Even though this value is Fernet-ciphertext rather than the
raw seed, it is still per-user secret material that should not be routinely written to
logs (a future key rotation or key leak turns every historical log line into a plaintext
seed).
**Fix:** Delete both lines, or gate them behind an explicit, still-secret-free debug
statement (e.g. `logger.debug('enrolled=%s', bool(...))`) with no property value logged.

### WR-05: `get_secret`/`get_or_create_secret` carry a stale, unimplemented `hashed` concept

**File:** `src/imio/googleauthenticator/helpers.py:246, 254, 316`
**Issue:** `get_secret(user=None, hashed=False)` declares and documents a `hashed`
parameter ("If set to True, hashed version is returned") that the function body never
reads or acts on (`# TODO: Return hashed version if hashed is set to True.`, followed by
code that always returns the plaintext seed). `get_or_create_secret` carries the
identical stale `# TODO` comment even though its signature (`user, overwrite=False`) has
no `hashed` parameter at all — the comment was evidently copy-pasted and never adapted.
No caller anywhere in the codebase passes `hashed=True` (confirmed by grep), so this is
dead, misleading API surface on a security-relevant function.
**Fix:** Remove the `hashed` parameter and both stale TODO comments, or implement the
feature if it is genuinely still wanted.

## Info

### IN-01: `tests/test_security.py` is an empty placeholder with no assertions

**File:** `src/imio/googleauthenticator/tests/test_security.py:17-19`
**Issue:**
```python
def test_(self):
    """
    """
```
This is the entire body of the only test in the file. `test_security.py` registers a
test class and a test method that asserts nothing at all — it inflates the collected
test count with a security-sounding filename while providing zero coverage. Given how
rigorously the rest of this phase's test suite documents intent and non-vacuity controls,
this file reads as leftover scaffolding rather than a deliberate placeholder.
**Fix:** Either delete `test_security.py`, or replace its content with a real assertion
(or an explicit `self.skipTest(...)` naming what it is waiting to become).

### IN-02: No-op `updateFields`/`updateWidgets` overrides that only call `super()`

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:89-93`, `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:142-145`
**Issue:** `GoogleAuthenticatorSettingsEditForm.updateFields`/`updateWidgets` and
`RequestBarCodeResetForm.updateFields` each consist of a single `return
super(...).updateFields(*args, **kwargs)` (or the arg-less equivalent) with no added
behaviour. These are dead overrides that add indirection with no functional purpose.
**Fix:** Delete the overrides and let the base-class methods be inherited directly.

### IN-03: Redundant double-coercion of an already-boolean value

**File:** `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py:22`
**Issue:** `if bool(api.user.is_anonymous()) is True:` — `plone.api.user.is_anonymous()`
already returns a `bool`; wrapping it in `bool(...)` and then comparing `is True` is
redundant.
**Fix:** `if api.user.is_anonymous():`.

### IN-04: `bin/test-coverage` CI switch has no fallback if the coverage part is ever removed from `base.cfg`

**File:** `.github/workflows/package-test.yml:14`
**Issue:** The workflow now hard-depends on `bin/test-coverage` (a `collective.recipe.template`-generated script), whereas the previous `bin/test` target is always produced by `zc.recipe.testrunner`. This is a reasonable, deliberate change (matches `.claude/CLAUDE.md`'s coverage-enforcement goal) but it means a future buildout edit that drops the `[test-coverage]` part from `base.cfg` silently breaks CI with a "no such file" error rather than a clear coverage-related failure. Not a defect in the reviewed diff, just a coupling worth naming since nothing in this file set documents the dependency.
**Fix:** No action required; noting for awareness only — consider a comment in `base.cfg` (out of this review's file scope) cross-referencing this workflow file.

---

_Reviewed: 2026-08-05T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
