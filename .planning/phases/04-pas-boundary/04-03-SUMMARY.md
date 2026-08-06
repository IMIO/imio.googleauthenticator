---
phase: 04-pas-boundary
plan: 03
subsystem: auth
tags: [pas, ichallengeplugin, unauthorized, pluggableauthservice, plone4, python2]

# Dependency graph
requires:
  - phase: 04-01
    provides: "send_2fa_redirect, _mark_2fa_pending, REQUEST_KEY_PENDING/REQUEST_KEY_USER_ID -- reused as-is, not reimplemented, by this plan's challenge()"
  - phase: 04-02
    provides: "movePluginsTop re-asserted unconditionally over every interface the plugin provides (the mechanism that, with no new code, also covers IChallengePlugin once this plan declares it); the recorded decision to keep credentials_basic_auth active, with the explicit instruction that test_basic_auth_veto must assert through _extractUserIds"
provides:
  - "GoogleAuthenticatorPlugin.challenge(request, response) -- IChallengePlugin's Unauthorized-path counterpart to 04-01's IPubBeforeCommit subscriber, sharing send_2fa_redirect so the two redirect entry points cannot drift"
  - "classImplements(GoogleAuthenticatorPlugin, IAuthenticationPlugin, IChallengePlugin)"
  - "tests/test_challenge.py::test_challenge_declines_without_the_flag, test_challenge_writes_nothing, test_challenge_fires_on_unauthorized"
  - "tests/test_pas_plugin.py::test_form_post_veto, test_basic_auth_veto, test_both_extractors_at_once_grant_no_session, test_empty_credentials_do_not_raise, test_exception_path_still_wipes_credentials"
  - "empirical answer to Open Question 3: no new ordering code needed -- 04-02's existing movePluginsTop loop already covers IChallengePlugin once classImplements declares it"
affects: [04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A second IChallengePlugin.challenge() entry point sharing the same send_2fa_redirect builder as the IPubBeforeCommit subscriber, rather than duplicating the redirect/body-clear/status-lock logic for the Unauthorized path"
    - "Veto assertions run through the real _extractUserIds path (not a direct authenticateCredentials call) whenever the extractor under test is still active, so the test exercises the actual PAS entry point rather than bypassing it"
    - "Every absence assertion (a veto test proving 'nothing authenticated') carries a disabled-2FA non-vacuity control run first in the same method, and mutation checks (temporarily commenting out or relocating the production code) are run once during development and recorded here rather than left as an unverified claim"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/pas_plugin.py
    - src/imio/googleauthenticator/tests/test_challenge.py
    - src/imio/googleauthenticator/tests/test_pas_plugin.py

key-decisions:
  - "Open Question 3 resolved empirically as 'not needed' (no new movePluginsTop call for IChallengePlugin): 04-02's _add_plugin loop already iterates every interface listPluginTypeInfo() lists and calls movePluginsTop unconditionally for each one providedBy the plugin. Since classImplements now declares IChallengePlugin, that existing loop body picks it up with zero new code. Verified two ways: (1) tests/test_challenge.py::test_challenge_fires_on_unauthorized lands on the token form rather than credentials_cookie_auth's require_login/login_form; (2) a one-off self.pas.plugins.listPlugins(IChallengePlugin) inspection during development showed google_auth first, ahead of credentials_cookie_auth and credentials_basic_auth, immediately after the standard test fixture's self._install() reinstall."
  - "test_challenge_fires_on_unauthorized targets /@@personal-information (permission cmf.SetOwnProperties, requires login) rather than a made-up protected view, matching the precedent already used in tests/test_user_setup.py. The anonymous non-vacuity control lands on PAS's credentials_cookie_auth require_login screen, not literally 'login_form' -- the initial docstring assumption was wrong and corrected against the real observed URL."
  - "The test does not follow the redirect to the token form and render it. A real HTTP Basic Auth client resends the same Authorization header on every request in the realm, including the redirect target itself -- confirmed empirically while writing this test: opening the signed token-form URL with the same header re-triggers authenticateCredentials's veto and the IPubBeforeCommit subscriber on THAT request too, producing an infinite 302 loop (mechanize's own redirect-loop detector fired). This is an accepted, by-design consequence of 04-02's decision to keep credentials_basic_auth active (T-04-20): Basic Auth is a dead end for a 2FA-enabled user, not a path meant to ever complete. The test disables auto-redirect-following and asserts only the single hop challenge() itself produces (302 status, Location containing @@google-authenticator-token and auth_user=, empty body)."
  - "test_exception_path_still_wipes_credentials injects via rebinding pas_plugin._mark_2fa_pending to a raising stub (the module-level seam 04-01 introduced), per the plan's explicit instruction. The second mutation check (below) demonstrates this specific injection point is sufficient to catch a reordering where the wipe moves to after this call site, not merely a reordering to somewhere between delegation and get_secret -- documented precisely so the mutation check is not misread as covering every possible relocation."
  - "test_basic_auth_veto asserts through _extractUserIds (not a direct authenticateCredentials call), per 04-02-SUMMARY.md's explicit guidance -- credentials_basic_auth remains active, so this exercises the real PAS entry point rather than bypassing it."

patterns-established:
  - "Pattern: an IChallengePlugin added late to a plugin that already implements IAuthenticationPlugin does not need its own ordering-assertion code if the install-time ordering loop already iterates over every interface the plugin implements generically (04-02's design). Confirm this with a real end-to-end test before adding an ordering call some verifier might otherwise ask for on faith."

requirements-completed: [MFA-01, MFA-04, COEX-08]

coverage:
  - id: D1
    description: "GoogleAuthenticatorPlugin.challenge() fires for the Unauthorized/challenge path exactly when this request's authenticateCredentials marked it pending, redirecting to @@google-authenticator-token via the same send_2fa_redirect builder the login-POST subscriber uses -- not served the resource, and not sent to Plone's own login_form/require_login"
    requirement: "COEX-08"
    verification:
      - kind: unit
        ref: "tests/test_challenge.py#test_challenge_fires_on_unauthorized"
        status: pass
      - kind: unit
        ref: "tests/test_challenge.py#test_challenge_declines_without_the_flag"
        status: pass
    human_judgment: false
  - id: D2
    description: "challenge() performs zero writes -- a memberdata property is unchanged across a call that fires the redirect, mirroring test_get_ska_secret_key_does_not_mutate_registry's before/after shape"
    requirement: "COEX-08"
    verification:
      - kind: unit
        ref: "tests/test_challenge.py#test_challenge_writes_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "The plugin declares no protocol attribute and implements IChallengePlugin, keeping it out of HTTPBasicAuthHelper's protocol group while still being reachable by PAS's challenge loop"
    requirement: "COEX-08"
    verification:
      - kind: unit
        ref: "bin/python -c IChallengePlugin.implementedBy(...) and not hasattr(P, 'protocol') (acceptance criteria, both run and passing)"
        status: pass
    human_judgment: false
  - id: D4
    description: "MFA-01: a 2FA-enabled user presenting Authorization: Basic is granted no session via the real _extractUserIds path, with a disabled-2FA non-vacuity control proving the same header does authenticate otherwise; proven load-bearing by a mutation check that comments out the credentials-wipe loop"
    requirement: "MFA-01"
    verification:
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_basic_auth_veto"
        status: pass
    human_judgment: false
  - id: D5
    description: "MFA-04: a 2FA-enabled user POSTing form credentials is granted no session (test_form_post_veto); both extractors presenting credentials at once independently grant nothing (test_both_extractors_at_once_grant_no_session); an empty/blank/None credentials dict returns None and raises nothing (test_empty_credentials_do_not_raise) -- all three with disabled-2FA non-vacuity controls where applicable, and the first two proven load-bearing by the same wipe-removal mutation check"
    requirement: "MFA-04"
    verification:
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_form_post_veto"
        status: pass
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_both_extractors_at_once_grant_no_session"
        status: pass
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_empty_credentials_do_not_raise"
        status: pass
    human_judgment: false
  - id: D6
    description: "ROADMAP success criterion 5: an exception raised after the 2FA branch has begun (injected via pas_plugin._mark_2fa_pending) leaves the shared credentials dict empty, so the refusal holds even in the counterfactual world where PAS swallows the exception and falls through to source_users; proven load-bearing by a second mutation check that relocates the wipe to after this call site"
    requirement: null
    verification:
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_exception_path_still_wipes_credentials"
        status: pass
    human_judgment: false

# Metrics
duration: 90min
completed: 2026-07-31
status: complete
---

# Phase 04 Plan 03: PAS Boundary -- Unauthorized Challenge + Per-Extractor Veto Summary

**Added `IChallengePlugin.challenge()` (COEX-08's Unauthorized half, sharing 04-01's `send_2fa_redirect`) and one veto assertion per credentials extractor (MFA-01, MFA-04) plus the exception-path guarantee, each proven load-bearing by a recorded mutation check rather than a green run alone.**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-07-31 (session start)
- **Completed:** 2026-07-31
- **Tasks:** 2
- **Files modified:** 3 (1 production, 2 test)

## Accomplishments

- `GoogleAuthenticatorPlugin` now also implements `IChallengePlugin`: `challenge(request, response)` returns `True` and calls the existing `send_2fa_redirect` exactly when `request.other[REQUEST_KEY_PENDING]` is set by this same request's `authenticateCredentials`, `False` otherwise. The method is two statements, reuses 04-01's shared redirect builder verbatim, and is proven write-free by `test_challenge_writes_nothing` (a memberdata property is read before and after the call and compared).
- Open Question 3 (does challenger ordering need an explicit fix?) is answered empirically as **not needed**: 04-02's `_add_plugin` already calls `movePluginsTop` unconditionally for every interface `listPluginTypeInfo()` lists that `providedBy(plugin)` is true for. Since this plan's `classImplements` addition makes `IChallengePlugin` one of those interfaces, the existing loop puts `google_auth` first among `IChallengePlugin` with zero new code -- confirmed both by `test_challenge_fires_on_unauthorized` landing on the token form (not `credentials_cookie_auth`'s `require_login`) and by a one-off `listPlugins(IChallengePlugin)` inspection during development: `[('google_auth', ...), ('credentials_cookie_auth', ...), ('credentials_basic_auth', ...)]`.
- Five new veto assertions in `tests/test_pas_plugin.py`, one per credentials-extractor path plus the exception-path guarantee, each with a disabled-2FA non-vacuity control where the assertion is an absence, and each (where applicable) proven load-bearing by a recorded, reverted mutation check rather than trusted on a green run alone.
- Discovered and documented (not fixed, since it is by design): HTTP Basic Auth is a genuine dead end for a 2FA-enabled user with this architecture -- a real client resends the same `Authorization` header on every request in the realm, including the redirect target, which re-triggers the veto and loops forever. This is an accepted consequence of 04-02's "keep `credentials_basic_auth` active" decision (T-04-20), not a new bug; `test_challenge_fires_on_unauthorized` deliberately does not follow the redirect for this reason, and the finding is recorded in this summary's key-decisions so it is not silently relied upon or silently "fixed" by a future phase without re-reading this note.

## Task Commits

Each task was committed atomically:

1. **Task 1: IChallengePlugin.challenge -- the Unauthorized path, write-free, status-locked** - `2ab4998` (feat)
2. **Task 2: One veto assertion per extractor, plus the exception path** - `5161203` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `src/imio/googleauthenticator/pas_plugin.py` -- Added `IChallengePlugin` import, extended `classImplements` to declare it, added `challenge(self, request, response)`; updated the `_dont_swallow_my_exceptions` comment now that Phase 4's boundary rework (04-01's decide-only split plus this plan's `challenge()`) is complete.
- `src/imio/googleauthenticator/tests/test_challenge.py` -- Added `test_challenge_declines_without_the_flag`, `test_challenge_writes_nothing`, `test_challenge_fires_on_unauthorized` to `TestPubBeforeCommitRedirect`; added `base64`, `Browser`, `PAS_ID` imports.
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` -- Added `test_form_post_veto`, `test_basic_auth_veto`, `test_both_extractors_at_once_grant_no_session`, `test_empty_credentials_do_not_raise`, `test_exception_path_still_wipes_credentials` to `TestPas`; added module-level `import base64`.

## Decisions Made

- **Open Question 3: no new ordering code.** See key-decisions above -- 04-02's existing generic `movePluginsTop` loop already covers `IChallengePlugin` once `classImplements` declares it, verified two ways rather than assumed.
- **`test_basic_auth_veto` asserts through `_extractUserIds`**, per 04-02-SUMMARY.md's explicit instruction (the extractor stays active under the "keep" decision), not through a direct `authenticateCredentials` call that would bypass the real entry point and prove nothing about it.
- **`test_challenge_fires_on_unauthorized` targets `/@@personal-information`** (permission `cmf.SetOwnProperties`), the same protected view `tests/test_user_setup.py` already relies on for its own redirect assertions -- reusing an already-validated "genuinely requires login" fixture rather than inventing a new one.
- **The anonymous non-vacuity control asserts `require_login` in the URL, not `login_form`.** The read_first notes named `login_path = 'login_form'` as the eventual destination, but the actually-observed intermediate landing page for an anonymous `Unauthorized` in this fixture is `credentials_cookie_auth/require_login`. The docstring and assertion were corrected against the real observed behaviour rather than left matching the plan's untested assumption.
- **The redirect is not followed to the token form in the main test.** See "Discovered" above -- following it with the same Basic Auth header present produces an infinite redirect loop by design, not by bug. The test asserts the single hop (`302`, `Location` containing `@@google-authenticator-token` and `auth_user=`, empty body) instead.
- **`test_exception_path_still_wipes_credentials`'s injection point is `pas_plugin._mark_2fa_pending`**, per the plan's explicit instruction. Documented precisely in the test's docstring and here that the corresponding mutation check (moving the wipe "below the delegation loop") was performed by relocating the wipe to directly after the `_mark_2fa_pending` call site specifically -- the minimal relocation that this particular injection point can actually detect -- not to an arbitrary point between the delegation loop and `get_secret`, which this test's injection point would not catch. This is recorded so the mutation check is not later mis-cited as proving a broader claim than it does.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in test docstring's assumption] `require_login`, not `login_form`, is the anonymous landing page**
- **Found during:** Task 1, writing `test_challenge_fires_on_unauthorized`
- **Issue:** The plan's read_first notes state `ExtendedCookieAuthHelper`'s `login_path = 'login_form'`, and the first draft of the non-vacuity control asserted `'login_form' in anon_browser.url`. The actual observed URL after an anonymous `Unauthorized` on `/@@personal-information` is `.../acl_users/credentials_cookie_auth/require_login?came_from=...` -- `require_login` is itself a distinct, un-redirected landing page in this fixture, not a mid-flight hop to `login_form`.
- **Fix:** Assertion corrected to check for `require_login` (and that `Personal Information` is absent from the anonymous response), matching the real observed behaviour.
- **Files modified:** `src/imio/googleauthenticator/tests/test_challenge.py`
- **Verification:** `bin/test -t test_challenge_fires_on_unauthorized` passes
- **Committed in:** `2ab4998` (Task 1 commit)

**2. [Rule 1 - Bug in test design] Following the redirect with a persistent Basic Auth header loops forever**
- **Found during:** Task 1, writing `test_challenge_fires_on_unauthorized`
- **Issue:** The first draft of the test opened the protected URL with a Basic Auth header and let `zope.testbrowser` auto-follow the resulting redirect, expecting to land cleanly on the rendered token form. Instead, `mechanize` raised `HTTPError: HTTP Error 302: ... would lead to an infinite loop` -- confirmed (with `handleErrors=False`, ruling out a swallowed Python exception) that the *second* hop is also a clean, application-level 302 back to the same signed URL: the token-form request itself still carries the same `Authorization` header, so `authenticateCredentials` sets the pending flag again on that request too, and 04-01's `IPubBeforeCommit` subscriber (which fires on *every* request with the flag set, not only login-form POSTs) redirects again.
- **Fix:** Disabled auto-redirect-following (`browser.mech_browser.set_handle_redirect(False)`) and asserted only the single hop: status `302`, `Location` containing `@@google-authenticator-token` and `auth_user=`, and an empty body. Documented as an accepted, by-design consequence of keeping `credentials_basic_auth` active (04-02, T-04-20), not a bug to fix in this plan.
- **Files modified:** `src/imio/googleauthenticator/tests/test_challenge.py`
- **Verification:** `bin/test -t test_challenge_fires_on_unauthorized` passes; full suite green
- **Committed in:** `2ab4998` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both test-correctness fixes against real observed behaviour; no production-code bug found or fixed by either).
**Impact on plan:** Both necessary for a genuinely green, honest `test_challenge_fires_on_unauthorized`. No scope creep -- production code (`pas_plugin.py`) matches the plan's `<action>` text exactly (challenge() is 2 statements, well under the "at most four" acceptance ceiling), and both fixes are confined to the test file the plan already names.

## Issues Encountered

- The HTTP-Basic-Auth-resent-on-every-request infinite-loop discovery (deviation 2 above) took the bulk of Task 1's debugging time. Root-caused with a sequence of increasingly targeted debug prints: first confirming the loop was a clean `302` (not a Python exception) even with `handleErrors=False`, then confirming the response body was empty (matching `send_2fa_redirect`'s own signature), which pointed at the `IPubBeforeCommit` subscriber firing unconditionally on the second request rather than at `challenge()` misbehaving.
- Both required mutation checks (T-04-20's wipe-removal, and the second wipe-relocation check for the exception path) were performed manually during development by temporarily editing `pas_plugin.py`, confirming the targeted tests went red, then reverting -- confirmed via `git diff` that the file returned to byte-identical state before the Task 2 commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `challenge()` and the five veto tests give plan 04-04 (documentation) a complete, evidenced account of both redirect entry points (login-POST subscriber from 04-01, `IChallengePlugin.challenge()` from this plan) and the full credentials-extractor veto surface (form POST, Basic Auth, both at once, empty, and the exception exit).
- The HTTP-Basic-Auth-infinite-loop finding should be mentioned in 04-04's documentation update if it covers `credentials_basic_auth`'s "keep active" decision, so a future reader is not surprised by it in production logs.
- No blockers carried forward from this plan.

---
*Phase: 04-pas-boundary*
*Completed: 2026-07-31*

## Self-Check: PASSED

- FOUND: src/imio/googleauthenticator/pas_plugin.py
- FOUND: src/imio/googleauthenticator/tests/test_challenge.py
- FOUND: src/imio/googleauthenticator/tests/test_pas_plugin.py
- FOUND commit: 2ab4998 (Task 1)
- FOUND commit: 5161203 (Task 2)
- Full suite: 65 tests, 0 failures, 0 errors (`bin/test -t '!robot'`)
