---
phase: 04-pas-boundary
reviewed: 2026-07-31T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - src/imio/googleauthenticator/configure.zcml
  - src/imio/googleauthenticator/pas_plugin.py
  - src/imio/googleauthenticator/setuphandlers.py
  - src/imio/googleauthenticator/subscribers.py
  - src/imio/googleauthenticator/tests/test_challenge.py
  - src/imio/googleauthenticator/tests/test_generic.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-31
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 04 splits `GoogleAuthenticatorPlugin.authenticateCredentials` into a decide-only
method plus two redirect entry points (`subscribers.redirect_pending_2fa` on
`IPubBeforeCommit` for the login-POST path, `GoogleAuthenticatorPlugin.challenge` on the
`Unauthorized` path), both funnelled through the shared `pas_plugin.send_2fa_redirect`
builder. `setuphandlers.py` now re-asserts plugin ordering (`movePluginsTop`) on every
profile (re-)apply rather than only at first install.

I read all eight files in full, traced the call chain from `authenticateCredentials`
through `_mark_2fa_pending` / `send_2fa_redirect` into `helpers.sign_user_data` /
`get_or_create_secret` / `_get_fernet`, read the actual PAS (`PluggableAuthService.py`)
and ZPublisher (`Publish.py`, `HTTPResponse.py`) source this plugin hooks into to verify
the docstrings' claims about transaction/commit ordering, and ran the full phase test
suite (`test_challenge.py`, `test_pas_plugin.py`, `test_setuphandlers.py`,
`test_generic.py` — 40 tests, all green). I also wrote and ran two throwaway integration
tests (not committed) to empirically probe an edge case the existing suite does not
cover; see WR-01 below.

The credential-wipe-before-delegation veto, the `IChallengePlugin` write-freedom
argument, the body-lock reasoning in `send_2fa_redirect`, the forgery-immunity of
reading `request.other` instead of `request.get(...)`, and the `movePluginsTop`
re-assertion all check out against the actual PAS/ZPublisher source and pass their
mutation-tested assertions. No authentication bypass was found. Two warnings and one
info-level finding below.

## Warnings

### WR-01: SEC-03's synchronous seed-decrypt check has a gap for a 2FA-enabled user who has never enrolled a secret

**File:** `src/imio/googleauthenticator/pas_plugin.py:253-260`, `src/imio/googleauthenticator/subscribers.py:58-65`

**Issue:** `authenticateCredentials`'s SEC-03 comment claims calling `get_secret(user)`
"force[s] the seed-decrypt check synchronously... so a broken encryption key still
raises out of `_extractUserIds` -- exactly as it did before this plan's restructure."
This is true only when the user already has a stored (non-empty)
`two_factor_authentication_secret` property: `helpers.get_secret()` returns `None`
silently for an empty property without ever calling `decrypt_seed`/`_get_fernet` (see
`helpers.py:226-233`). For a user with `enable_two_factor_authentication=True` but no
secret yet (e.g. an admin flips the flag on an existing account without walking it
through the enrollment wizard), `authenticateCredentials` does **not** raise even when
`IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` is unset or malformed -- it stashes the pending flag
and returns `None` as if everything were fine.

The failure is deferred to `subscribers.redirect_pending_2fa` (`IPubBeforeCommit`) or
`pas_plugin.challenge` (`Unauthorized`), whose call to `send_2fa_redirect` ->
`sign_user_data` -> `get_or_create_secret` -> `generate_secret` -> `encrypt_seed` ->
`_get_fernet` raises there instead. I proved this empirically: with the env var unset
and a 2FA-enabled user whose secret property is `''`, `self.pas._extractUserIds(...)`
completes without raising, and `pas_plugin.send_2fa_redirect(request, request.response)`
is what actually raises `ValueError`. Over a real HTTP round trip
(`zope.testbrowser` POST to `login_form`), this `ValueError` propagates out of
`notify(PubBeforeCommit(request))` inside `ZPublisher/Publish.py:143`, after `mapply()`
has already run and set the response body (a "Login failed" page) at line 141 -- so the
request ends in Zope's generic exception-view handling (`ZPublisherExceptionHook`)
rather than the clean, controlled refusal SEC-03 was written to guarantee.

This is **not** a new authentication bypass (no session is ever granted either way, and
the pre-phase-04 code called `sign_user_data` synchronously inside
`authenticateCredentials` too, so the exception was always reachable from this state --
only the call site moved), and it still fails closed. But it does mean the phase's own
stated invariant ("a broken encryption key still raises... exactly as it did before")
does not hold for this specific, real (not purely theoretical) memberdata state, and the
resulting failure mode is a generic/uncontrolled error response instead of a normal
"Login failed" outcome.

**Fix:** Validate the encryption key itself synchronously in `authenticateCredentials`,
independent of whether the user already has a stored secret, without writing anything
(preserve the "no ZODB write in the PAS plugin" invariant this phase and CLAUDE.md both
require). E.g. expose a tiny read-only helper and call it unconditionally alongside the
existing `get_secret(user)` call:

```python
# helpers.py
def check_encryption_key_is_usable():
    """Read-only Fernet-key health check; raises ValueError if the key is
    missing or malformed. Never call anything that writes memberdata."""
    _get_fernet()

# pas_plugin.py, in the two_factor_authentication_enabled branch:
get_secret(user)
helpers.check_encryption_key_is_usable()
_mark_2fa_pending(self.REQUEST, user)
```

Add a regression test alongside `test_login_is_refused_when_seed_key_is_broken` for the
"enabled, never enrolled" state (see WR-02).

### WR-02: No test covers "2FA enabled + no secret yet + broken encryption key"

**File:** `src/imio/googleauthenticator/tests/test_pas_plugin.py`

**Issue:** `test_login_is_refused_when_seed_key_is_broken` only exercises a user who
already has a secret (`get_or_create_secret(user, overwrite=True)` is called in its
setup before the key is broken). It cannot, and does not, catch the WR-01 gap: a
2FA-enabled user whose `two_factor_authentication_secret` property is still empty.
Given this package's stated >90% coverage bar and the "every write path needs a
round-trip test" discipline CLAUDE.md calls for elsewhere in this codebase, this
security-relevant state combination should have an explicit test either way (asserting
today's actual behaviour, or asserting the WR-01 fix once applied).

**Fix:** Add a test mirroring `test_login_is_refused_when_seed_key_is_broken` but
without the `get_or_create_secret(user, overwrite=True)` call, asserting that
`self.pas._extractUserIds(...)` raises `ValueError` synchronously (post-WR-01-fix) or,
if WR-01 is deliberately deferred, asserting the current documented behaviour (that the
failure surfaces from `send_2fa_redirect` instead) so a future refactor cannot silently
change it in either direction without a red test.

## Info

### IN-01: Dead branch at the end of `authenticateCredentials`

**File:** `src/imio/googleauthenticator/pas_plugin.py:270-273`

**Issue:** Pre-existing code, unchanged by this phase's diff, but present in the
reviewed file:

```python
if credentials.get('extractor') != self.getId():
    return None

return None
```

Both branches return `None` unconditionally, so the `if` is inert -- this always
returns `None` regardless of `credentials['extractor']`. It reads as a leftover from an
earlier version of the plugin that could authenticate on its own extractor match; today
it only adds confusion about whether some case is actually being distinguished here.

**Fix:** Collapse to a single `return None` (or remove the trailing dead branch
entirely), since `two_factor_authentication_enabled` being falsy already fully
determines the outcome of this code path.

---

_Reviewed: 2026-07-31_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
