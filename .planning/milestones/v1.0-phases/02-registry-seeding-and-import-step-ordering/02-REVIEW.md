---
phase: 02-registry-seeding-and-import-step-ordering
reviewed: 2026-07-29T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - src/imio/googleauthenticator/configure.zcml
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/setuphandlers.py
  - src/imio/googleauthenticator/tests/test_helpers.py
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the import-step-ordering fix (`configure.zcml`), the removal of install-time
`ska_secret_key` seeding (`setuphandlers.py`), and the lazy-mint + netstring-style key
derivation in `helpers.get_ska_secret_key()`, plus the two new/expanded test files. The
`<depends name="plone.app.registry"/>` fix and the netstring-style separation of the three
key components are both sound: the length-prefixed join is a textbook unambiguous
encoding and does close the collision the old bare concatenation had (confirmed correct by
tracing the decode invariant, not just trusting the test).

However, moving the `ska_secret_key`-minting write out of the install step and into a bare
getter introduces two real regressions that the test suite does not catch, because every
new test drives `get_ska_secret_key()` directly with a hand-set, always-non-empty,
always-string `two_factor_authentication_secret` — never through the one call path
(`pas_plugin.authenticateCredentials` → `sign_user_data`) that the phase's own removed code
used to protect, and never with the falsy/`None` secret value the sibling `get_secret()`
function is defensively written to expect.

## Critical Issues

### CR-01: `get_ska_secret_key()` raises an unhandled `TypeError` if the user's secret property is falsy/`None`, where the old code silently tolerated it

**File:** `src/imio/googleauthenticator/helpers.py:255-265`
**Issue:**
The old derivation was `"{0}{1}{2}".format(user_secret, browser_hash, ska_secret_key)` —
`str.format()` coerces `None` to the literal string `"None"`, so a missing/undeclared
`two_factor_authentication_secret` property never crashed this function (it just silently
produced a wrong-but-well-formed key). The new derivation:

```python
return u''.join(
    u'{0}:{1}'.format(len(part), part)
    for part in (user_secret, browser_hash, ska_secret_key)
)
```

calls `len(part)` directly. If `user_secret` (`user.getProperty('two_factor_authentication_secret')`,
line 255, called with **no default argument**) is `None`, this raises
`TypeError: object of type 'NoneType' has no len()`, unhandled, inside a getter with no
`try`/`except`.

This is not hypothetical: `.claude/CLAUDE.md` explicitly documents that "undeclared
memberdata properties are silently popped by `MutablePropertySheet.setProperties` with no
error" as a live hazard in this exact codebase — `getProperty(id)` with no default returns
`None` when a property isn't declared for a user's (possibly stale/cached) property sheet.
The sibling function `get_secret()` (lines 126-142, unchanged) already anticipates exactly
this by guarding `isinstance(secret, basestring) and secret` before use — `get_ska_secret_key()`
has no equivalent guard.

Worse, the two callers are not equally protected: `sign_user_data()` (line 299) calls
`get_or_create_secret(user)` immediately before calling `get_ska_secret_key()`, which
guarantees the property is a set string. But `validate_user_data()` in the token form
(`browser/forms/token.py:87-88`) calls `get_ska_secret_key()` (via `validate_user_data`)
**without** that guarantee — so a user whose secret property is missing/dropped between the
initial redirect and following the signed link gets an unhandled 500 instead of the old
(silently-wrong-but-non-crashing) behavior.

Since `pas_plugin.GoogleAuthenticatorPlugin._dont_swallow_my_exceptions = True`
(`pas_plugin.py:71`), an exception raised inside this plugin's own code is not swallowed
by PAS's `_SWALLOWABLE_PLUGIN_EXCEPTIONS` handling either — it propagates.

**Fix:**
```python
user_secret = user.getProperty('two_factor_authentication_secret') or ''
```
placed right after line 255, mirroring the defensive pattern already used in `get_secret()`.
Add a regression test calling `get_ska_secret_key()` with a user whose
`two_factor_authentication_secret` property is unset/`None` (e.g. a freshly created member
that never went through `get_or_create_secret`).

### CR-02: Lazy-minting `ska_secret_key` inside a getter writes registry state from `authenticateCredentials`, not "the token form view" — violating the project's own documented `transaction.abort()` invariant

**File:** `src/imio/googleauthenticator/helpers.py:250-253` (write), called from
`src/imio/googleauthenticator/pas_plugin.py:160` (via `sign_user_data`, not the token form)

**Issue:**
`.claude/CLAUDE.md` states the architecture rule for exactly this class of hazard:

> "The hazard to design against is not `ConflictError`... It is `transaction.abort()`: any
> request ending in an exception discards its writes, and `Unauthorized` is re-raised, so a
> counter written in the PAS plugin is a lockout that silently never locks. Hence: all state
> writes in the token form view"

Before this phase, `ska_secret_key` was guaranteed non-empty by `_setup_secret_key()`,
which ran once, at install time, inside the GenericSetup import transaction (an
admin-triggered request that reliably commits). This phase deleted that seeding entirely
(confirmed via `git diff`: `setuphandlers.py` lost both the `uuid4`/`get_app_settings`
imports and the whole `_setup_secret_key` function) and replaced it with a lazy mint inside
`get_ska_secret_key()`:

```python
ska_secret_key = settings.ska_secret_key
if not ska_secret_key:
    ska_secret_key = unicode(uuid4())
    settings.ska_secret_key = ska_secret_key      # <-- persistent write
```

This getter is called from `sign_user_data()`, which runs directly inside
`GoogleAuthenticatorPlugin.authenticateCredentials()` (`pas_plugin.py:160`) — i.e. exactly
the "written in the PAS plugin" location the CLAUDE.md passage calls out, not the token
form view.

Concrete failure sequence: on the very first 2FA login after a fresh install (the case this
phase's own tests exercise for REG-04), any request that reaches this plugin's
`authenticateCredentials` while requesting a resource that needs more than Anonymous
permission (e.g. a 2FA-enabled user directly opening any member-only page — not an edge
case, this is exactly the situation that triggers 2FA in the first place) ends, after our
plugin empties `credentials` and returns `None`, in `Unauthorized` being raised for that
resource. Zope aborts the transaction on an unhandled exception, discarding the
just-written `ska_secret_key`. But `sign_user_data()` already computed and queued the
redirect (`response.redirect(signed_url, lock=1)`, `pas_plugin.py:169`) using the
in-memory (never-persisted) key value. When the user follows that link, the token form's
`validate_user_data()` calls `get_ska_secret_key()` again, finds the registry key **still
empty** (the mint was rolled back), and mints a **different** random key — so the
signature computed against the URL's key can never validate. The 2FA-enabled user is stuck
in a redirect loop / permanently invalid-signature error until some other request happens to
commit a mint, with no way for the user to recover on their own.

This is a regression relative to the pre-phase behavior (seed always committed at install,
independent of any login request's fate), introduced specifically by moving the write out
of a reliably-committing context into a bare getter reachable from the PAS plugin.

**Fix:** Do not perform registry writes from `get_ska_secret_key()`. Options, in order of
how little they cost given this package's stated 1-2 year lifespan:
- Re-add install-time seeding (without reintroducing the old nested
  `runImportStepFromProfile` re-entry bug this phase fixed — just call
  `get_app_settings()` + set the field directly in `setupVarious`, after the
  `<depends name="plone.app.registry"/>` guarantees registry records already exist).
- Or: keep the lazy mint, but perform the persisting write only from the token form view
  (mirroring how replay/lockout counters are already scoped there), passing the freshly
  minted value down to `sign_user_data()` instead of letting the getter mutate registry
  state as a side effect.

## Warnings

### WR-01: `get_ska_secret_key()` is a mutating "getter" with an undocumented side effect

**File:** `src/imio/googleauthenticator/helpers.py:228-265`
**Issue:** Per this codebase's own naming convention (`.claude/CLAUDE.md`: "Getter
functions prefix with `get_`"), a `get_` function is expected to be a pure accessor. This
one silently writes to `plone.registry` on first call (see CR-02) and the docstring
(lines 229-241) documents none of that — it still only describes the three input sources,
not the minting behavior or the new netstring-style output format.
**Fix:** Document the side effect explicitly in the docstring, or split into an explicit
`ensure_ska_secret_key()` write step called from a known-safe context (see CR-02 fix) plus
a genuinely pure `get_ska_secret_key()` read.

### WR-02: No test exercises `get_ska_secret_key()` with a falsy/`None` secret component

**File:** `src/imio/googleauthenticator/tests/test_helpers.py:126-160`
**Issue:** `test_get_ska_secret_key` only ever sets `two_factor_authentication_secret` to
non-empty string literals (`'ab'`, `'a'`). The most likely real-world failure mode for the
new `len(part)`-based derivation — a falsy/`None` component — has zero coverage, which is
exactly how CR-01 shipped uncaught despite the sibling `get_secret()` function's explicit
handling of the same scenario.
**Fix:** Add a case that leaves `two_factor_authentication_secret` unset (or explicitly
`None`) and asserts `get_ska_secret_key()` returns a well-formed key instead of raising.

### WR-03: `test_setupVarious` bundles five independent assertion groups into one method

**File:** `src/imio/googleauthenticator/tests/test_setuphandlers.py:36-105`
**Issue:** Ordering (REG-03), records-exist, no-install-seeding (REG-04), lazy-mint
(REG-04), and re-apply-guard (REG-05) are distinct requirements sharing one `test_`
method. Since `unittest` stops at the first failed assertion, a regression in an earlier
group (e.g. import-step ordering silently reverted) hides whether the later groups (lazy
mint, re-apply guard) still pass or fail. The docstring documents this as a deliberate
convention choice (R5), but it does reduce failure-localization precision for exactly the
kind of regression this phase is most at risk of (see CR-01/CR-02).
**Fix:** Not blocking given the documented convention, but consider splitting at least the
lazy-mint and re-apply-guard groups (the two REG-04/REG-05 behaviors most likely to
silently regress together) into their own test methods.

## Info

### IN-01: `get_ska_secret_key()` docstring not updated for the netstring-style format change

**File:** `src/imio/googleauthenticator/helpers.py:228-241`
**Issue:** The docstring still describes only the three composite inputs; it doesn't
mention the `length:value` separation scheme or that a missing key is now minted on first
read. A future maintainer changing the format without reading the implementation could
reintroduce a collision.
**Fix:** Add a line noting the length-prefixed (netstring-style) separation and why it's
required (prevents the BUG-04 collision the tests pin).

### IN-02: Implicit Python 2 `str`/`unicode` coercion in the netstring join is unguarded

**File:** `src/imio/googleauthenticator/helpers.py:262-265`
**Issue:** `u'{0}:{1}'.format(len(part), part)` implicitly decodes a `str` `part` using the
ASCII codec in Python 2. Today this is safe only because every current producer of these
values is ASCII-only (`rebus.b32encode`, `sha1().hexdigest()`, `unicode(uuid4())`). If any
producer ever changes to allow non-ASCII bytes in a `str` (not `unicode`) value, this raises
`UnicodeDecodeError` inside the same unguarded getter as CR-01.
**Fix:** Low priority given current constraints; worth revisiting alongside the CR-01 fix
since both need the same kind of input-normalization guard.

---

_Reviewed: 2026-07-29T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
