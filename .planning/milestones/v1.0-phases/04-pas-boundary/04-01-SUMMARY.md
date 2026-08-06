---
phase: 04-pas-boundary
plan: 01
subsystem: auth
tags: [pas, zpublisher, ipubbeforecommit, ska, plone4, python2]

# Dependency graph
requires:
  - phase: 03-encrypted-seeds-and-local-qr
    provides: encrypted seed storage (get_or_create_secret/decrypt_seed) that send_2fa_redirect's sign_user_data call now reaches from a new call site
provides:
  - "decide-only GoogleAuthenticatorPlugin.authenticateCredentials -- no RESPONSE access, no redirect"
  - "REQUEST_KEY_PENDING / REQUEST_KEY_USER_ID module constants shared between pas_plugin.py and subscribers.py"
  - "_mark_2fa_pending(request, user) -- writes the pending signal to request.other"
  - "send_2fa_redirect(request, response) -- the one shared redirect builder (cookie clear, ska sign, came_from append, status lock, body clear+lock)"
  - "subscribers.redirect_pending_2fa -- IPubBeforeCommit handler driving the login-POST redirect"
  - "tests/test_challenge.py -- TestPubBeforeCommitRedirect, the direct-call and real-HTTP MFA-02/COEX-08 proofs"
affects: [04-02, 04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IPubBeforeCommit subscriber as the login-POST challenge hook (the login-form POST returns HTTP 200 and never raises Unauthorized, so a IChallengePlugin alone never fires here)"
    - "response.body = '' + setHeader('content-length', '0') + setBody('', lock=1) to actually clear and lock a response body -- setBody('') alone is a no-op"
    - "request.other (never request.get) as the trusted, form-data-immune channel for an internal cross-hook signal"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_challenge.py
  modified:
    - src/imio/googleauthenticator/pas_plugin.py
    - src/imio/googleauthenticator/subscribers.py
    - src/imio/googleauthenticator/configure.zcml

key-decisions:
  - "SEC-03 preserved via a synchronous get_secret(user) call (pure read, no ZODB write) inside authenticateCredentials's 2FA branch, so a broken encryption key still raises out of _extractUserIds on the same request -- the plan's own acceptance criteria required test_login_is_refused_when_seed_key_is_broken to keep passing unmodified, which a fully decide-only branch (as the plan's <action> text literally describes) cannot satisfy"
  - "Task 2's over-HTTP body assertion submits the encoded POST through Browser.open() rather than Browser.getControl(...).click(): _clickSubmit() re-raises any mechanize.HTTPError unconditionally and never consults raiseHttpErrors, so the plan's suggested two-switch idiom only works against a directly-POSTed request, not a clicked form control"
  - "TestPubBeforeCommitRedirect's tearDown resets TEST_USER_NAME's enable_two_factor_authentication flag AND two_factor_authentication_secret property, committed: testbrowser-driven memberdata writes in this layer survive across test methods (documented precedent in test_pas_plugin.py), and leaving either behind broke test_generic.py's TEST_USER_NAME-driven views for two sibling test files"

patterns-established:
  - "Pattern: crypto/redirect logic that must run once, shared by two call sites (login-POST subscriber now, challenge plugin in 04-03 next), lives in one module-level function (send_2fa_redirect) in pas_plugin.py rather than being duplicated or moved into helpers.py (which would create a circular import via adapter.ICameFrom)"

requirements-completed: [MFA-02, COEX-08]

coverage:
  - id: D1
    description: "authenticateCredentials no longer touches RESPONSE or performs the redirect; it only decides and stashes a pending signal"
    requirement: "MFA-02"
    verification:
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_login_is_refused_when_seed_key_is_broken (regression, unmodified)"
        status: pass
      - kind: unit
        ref: "static grep: awk-scoped RESPONSE/response. count over authenticateCredentials body == 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "The refusal's response body is exactly empty ('', content-length '0') and stays empty under a later setBody call from a sibling IPubBeforeCommit subscriber (e.g. plone.transformchain)"
    requirement: "MFA-02"
    verification:
      - kind: unit
        ref: "tests/test_challenge.py#test_no_body_leak_on_2fa_redirect"
        status: pass
      - kind: integration
        ref: "tests/test_challenge.py#test_no_body_leak_over_http"
        status: pass
    human_judgment: false
  - id: D3
    description: "A 2FA-enabled user's login-form POST lands on the signed @@google-authenticator-token URL, driven by the IPubBeforeCommit subscriber (not by any RESPONSE call inside authenticateCredentials) -- Open Question 1 settled as 302-to-token-form"
    requirement: "COEX-08"
    verification:
      - kind: integration
        ref: "tests/test_challenge.py#test_pub_before_commit_fires_on_login_post"
        status: pass
    human_judgment: false
  - id: D4
    description: "The pending signal cannot be forged via a query string (?_2fa_pending=1&_2fa_user_id=<victim>) because the handler reads request.other only, never request.get"
    requirement: "MFA-02"
    verification:
      - kind: unit
        ref: "tests/test_challenge.py#test_request_flag_cannot_be_forged_from_the_query_string"
        status: pass
    human_judgment: false

duration: 70min
completed: 2026-07-31
status: complete
---

# Phase 04 Plan 01: PAS-boundary redirect relocation Summary

**Moved the 2FA redirect out of `authenticateCredentials` into a new `IPubBeforeCommit` subscriber, fixing the MFA-02 body-leak bug (`setBody('')` is a no-op; the fix is a plain `response.body = ''` assignment plus a body lock) and settling COEX-08's login-POST half.**

## Performance

- **Duration:** ~70 min
- **Started:** 2026-07-31T07:57:00Z (approx, per STATE.md)
- **Completed:** 2026-07-31T09:07:00Z (approx)
- **Tasks:** 2 (1 tracer + 1 optional/time-boxed)
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments

- `authenticateCredentials` is now decide-only: it wipes credentials, delegates to the other `IAuthenticationPlugin`s, and (on success) calls `_mark_2fa_pending(self.REQUEST, user)` -- no `RESPONSE` access, no redirect, anywhere in the method body.
- `send_2fa_redirect(request, response)` is the one shared redirect builder (cookie clear, `ska` sign, `came_from` append, status lock, body clear+lock), used by this plan's subscriber and reusable by plan 04-03's challenge plugin.
- `subscribers.redirect_pending_2fa`, an `IPubBeforeCommit` handler, drives the actual redirect on the login-form POST path -- the only hook that can still intervene once `mapply()` has already rendered the requested page into the response body and before the transaction commits.
- The MFA-02 body-leak bug is fixed at its root: `response.setBody('')` returns before ever assigning `self.body` (`HTTPResponse.py:453-460`) when the argument is falsy, so the fix assigns `response.body = ''` directly, resets `content-length`, then locks the body with `setBody('', lock=1)` so a later `IPubBeforeCommit` subscriber (`plone.transformchain`, registered for the same event in this buildout) cannot refill it.
- The pending signal travels only through `request.other` (`_mark_2fa_pending`/`redirect_pending_2fa`), never `request.get(...)`, which would otherwise fall through to form data and turn `?_2fa_pending=1&_2fa_user_id=<victim>` into a validly signed token URL for an arbitrary account.
- Task 2's optional over-HTTP assertion survived: `tests/test_challenge.py::test_no_body_leak_over_http` proves the same emptiness across a real `zope.testbrowser`/`mechanize` round trip, not just a direct-call `HTTPResponse`.

## Task Commits

1. **Task 1: One extractor vetoed end to end -- decide-only plugin, IPubBeforeCommit redirect, empty body** - `a9838e2` (feat)
2. **Task 2: Optional -- assert the empty body over real HTTP, time-boxed** - `b5468aa` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `src/imio/googleauthenticator/pas_plugin.py` - Added `REQUEST_KEY_PENDING`/`REQUEST_KEY_USER_ID` constants, `_mark_2fa_pending`, `send_2fa_redirect`; restructured `authenticateCredentials`'s 2FA branch to decide-only plus a synchronous `get_secret(user)` fail-closed check
- `src/imio/googleauthenticator/subscribers.py` - Added `redirect_pending_2fa`, an `@adapter(IPubBeforeCommit)` handler; extended the module docstring to cover both handlers
- `src/imio/googleauthenticator/configure.zcml` - Registered the new `IPubBeforeCommit` subscriber
- `src/imio/googleauthenticator/tests/test_challenge.py` - New: `TestPubBeforeCommitRedirect` with four test methods (body-leak direct-call, login-POST end-to-end, query-string-forgery guard, over-HTTP body-leak)

## Decisions Made

- **SEC-03 preserved via a synchronous pure-read crypto check.** The plan's `<action>` text describes `authenticateCredentials`'s 2FA branch ending with just `_mark_2fa_pending(...)` and `return None` -- fully decide-only, no crypto. But the plan's own acceptance criteria require `tests/test_pas_plugin.py::test_login_is_refused_when_seed_key_is_broken` (a pre-existing Phase 3 test, not in this plan's `files_modified`) to keep passing **unmodified**, and that test asserts a broken encryption key raises `ValueError` out of a raw `self.pas._extractUserIds(...)` call -- which never reaches `IPubBeforeCommit` and so never reaches the deferred `send_2fa_redirect`. Reconciled by adding one line, `get_secret(user)`, right before `_mark_2fa_pending`: it is a pure read (never `get_or_create_secret`, which can generate-and-write for a never-enrolled user), so it does not violate the "no ZODB write" prohibition in the common case, but it does force the same `decrypt_seed` raise synchronously that the old code produced via `sign_user_data`. Documented in `pas_plugin.py`'s inline comment.
- **Task 2's over-HTTP idiom submits via `Browser.open()` with encoded POST data, not `Browser.getControl(...).click()`.** The plan's suggested `set_handle_redirect(False)` + `raiseHttpErrors = False` combination only works against `Browser.open()`; `_clickSubmit()` (`zope/testbrowser/browser.py:407-424`) re-raises any `mechanize.HTTPError` unconditionally and never consults `raiseHttpErrors` at all, so the originally-planned clicked-control idiom raised `HTTPError: HTTP Error 302: Moved Temporarily` regardless of the two switches. Submitting the same `__ac_name`/`__ac_password`/`submit` fields as a `urllib.urlencode`d POST body through `Browser.open()` instead routes through the code path that actually honours `raiseHttpErrors`, and the test passes.
- **Test-pollution cleanup added to `TestPubBeforeCommitRedirect.tearDown`.** `_enable_2fa()` needs an explicit `transaction.commit()` so a subsequent `Browser.open()` (which calls `transactions_manager.begin()`, implicitly discarding this test method's own uncommitted memberdata write) can see the 2FA flag. That same commit-and-survive behaviour meant the flag and the encrypted secret (bound to this test module's own, later-discarded, seed-key env var) leaked into `test_generic.py::test_user_setup_view` and `test_token_view`, which log in as the same `TEST_USER_NAME` without resetting either -- surfacing as `ValueError: Ciphertext failed to decrypt`. Fixed by resetting both properties, committed, in `tearDown`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restored the SEC-03 synchronous fail-closed guarantee via `get_secret(user)`**
- **Found during:** Task 1, running the full `bin/test -t '!robot'` acceptance gate
- **Issue:** A fully decide-only `authenticateCredentials`, exactly as the plan's `<action>` text describes, made `test_login_is_refused_when_seed_key_is_broken` fail (`AssertionError: ValueError not raised`) -- the crypto validation that test depends on had moved entirely into the deferred `send_2fa_redirect`, unreachable from a raw `_extractUserIds()` call
- **Fix:** Added a synchronous `get_secret(user)` call (pure read, no write) in the 2FA branch, forcing the same `decrypt_seed` raise on this same request
- **Files modified:** `src/imio/googleauthenticator/pas_plugin.py`
- **Verification:** `bin/test -t test_login_is_refused_when_seed_key_is_broken` passes; full suite green
- **Committed in:** `a9838e2` (Task 1 commit)

**2. [Rule 3 - Blocking] Test-pollution across `TestPubBeforeCommitRedirect` and `TestGeneric`**
- **Found during:** Task 1, running `bin/test -t '!robot'`
- **Issue:** `TestGeneric::test_user_setup_view` and `test_token_view` started failing with `ValueError: Ciphertext failed to decrypt` after `TestPubBeforeCommitRedirect`'s browser-driven tests ran first in the same layer -- a committed, un-reset 2FA flag and ciphertext bound to a since-discarded env key
- **Fix:** `TestPubBeforeCommitRedirect.tearDown` now resets `enable_two_factor_authentication` and `two_factor_authentication_secret` for `TEST_USER_NAME`, committed
- **Files modified:** `src/imio/googleauthenticator/tests/test_challenge.py`
- **Verification:** `bin/test -t '!robot'` -- 53/53 (then 54/54 after Task 2), 0 failures
- **Committed in:** `a9838e2` (Task 1 commit)

**3. [Rule 1 - Bug] `Browser.getControl(...).click()` does not honour `raiseHttpErrors`**
- **Found during:** Task 2
- **Issue:** The plan's suggested idiom (`set_handle_redirect(False)` + `raiseHttpErrors = False`) raised `mechanize.HTTPError: HTTP Error 302: Moved Temporarily` when submitting via a clicked form control, because `_clickSubmit()` never checks `raiseHttpErrors`
- **Fix:** Submit the encoded POST directly via `Browser.open(url, data)`, which does respect the switch
- **Files modified:** `src/imio/googleauthenticator/tests/test_challenge.py`
- **Verification:** `bin/test -t test_no_body_leak_over_http` passes
- **Committed in:** `b5468aa` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 bug/SEC-03 regression, 1 test-pollution blocker, 1 test-mechanism bug)
**Impact on plan:** All three necessary for a genuinely green `bin/test -t '!robot'` and a working Task 2 assertion. No scope creep -- no files touched beyond the four declared in Task 1's `files_modified`, and Task 2 touched only `tests/test_challenge.py` as its own acceptance criterion requires.

## Issues Encountered

- Extensive debugging was needed to find why the login-POST redirect wasn't firing in the first full-suite run: `zope.component.subscribers(event, None)` always returns an empty list for handler-style (as opposed to typed subscription-adapter) registrations **by design** (`zope/interface/adapter.py:585-597` -- for `provided=None` it calls each subscriber but discards the return value), which is easy to misread as "the subscriber isn't registered." The actual root cause was unrelated: `Browser.open()` starts a fresh ZPublisher transaction, silently discarding the test method's own uncommitted `enable_two_factor_authentication` write from the same test. Resolved by adding `transaction.commit()` in `_enable_2fa()`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `REQUEST_KEY_PENDING`, `REQUEST_KEY_USER_ID`, and `send_2fa_redirect` are the shared contract plan 04-03's challenge plugin (`IChallengePlugin`, for the `Unauthorized`-raising paths) will import and reuse -- no drift risk between the two redirect call sites.
- `authenticateCredentials` is now write-free from `RESPONSE`'s perspective and write-minimal from ZODB's (only the pre-existing, now-explicit `get_secret`/`get_or_create_secret` paths), which is the exact precondition Phase 5's MFA-12 (lockout state) depends on.
- No blockers for 04-02, 04-03, or 04-04.

---
*Phase: 04-pas-boundary*
*Completed: 2026-07-31*

## Self-Check: PASSED

All four files verified present (`pas_plugin.py`, `subscribers.py`, `configure.zcml`, `tests/test_challenge.py`); both commits (`a9838e2`, `b5468aa`) verified present in `git log`.
