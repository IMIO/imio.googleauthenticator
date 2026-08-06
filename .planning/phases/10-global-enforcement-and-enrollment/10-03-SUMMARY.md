---
phase: 10-global-enforcement-and-enrollment
plan: 03
subsystem: auth
tags: [pas-plugin, plone, browserview, statusmessages]

requires:
  - phase: 10-global-enforcement-and-enrollment
    provides: "plan 10-01's install-time enrollment and plan 10-02's proof that _enroll_existing_users satisfies D-01/D-02/D-04 -- this plan's guard only reads the same globally_enabled registry setting those plans already exercise"
provides:
  - "browser/disable_two_factor_authentication.py refuses (error message, redirect to @@personal-information) when globally_enabled is on, leaving the flag/seed/reset-token untouched (D-08/D-09/MFA-16)"
  - "browser/disable_two_factor_authentication_for_all_users.py gets the same refusal on its bulk un-enroll path (D-18, an operator-approved widening beyond MFA-16's literal wording)"
  - "two new translatable msgids (D-12): neither names another account"
  - "TestDisableTwoFactorAuthenticationForAllUsers, the first test class for the bulk un-enroll view"
affects: [10-04, 10-05, 10-06]

tech-stack:
  added: []
  patterns:
    - "Real-collaborator stand-in for an empty api.user.get_users() result (_FakeApiWithNoUsers), following test_setuphandlers.py's _FakeApiWithOneFailingUser and test_user_setup.py's _RaisesOnFirstCall precedent -- monkeypatch the target module's own `api` name, restore in a finally:"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/disable_two_factor_authentication.py
    - src/imio/googleauthenticator/browser/disable_two_factor_authentication_for_all_users.py
    - src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py

key-decisions:
  - "The all-users-refused test creates two real accounts via api.user.create rather than reusing the fixture user only, matching test_controlpanel.py's established multi-user shape -- a guard that only checked the current user would pass a single-account test."
  - "The empty-user-list probe's off-branch does not assert zero mutation for real accounts. helpers.disable_two_factor_authentication_for_users(users) has its own pre-existing `if not users: users = api.user.get_users()` fallback, which re-fetches the real user list when passed an empty one -- an empty list and 'no argument' are indistinguishable to that function. This plan's guard is orthogonal to that behaviour and does not touch it; the plan's own acceptance bar (\"returns without raising ... queues info\") is satisfied either way. Recorded here so a later reader does not mistake the off-branch assertion for a zero-mutation proof."

patterns-established: []

requirements-completed: [MFA-16]

duration: ~25min
completed: 2026-08-06
status: complete
---

# Phase 10 Plan 03: Global-Enforcement Refusal on Both Disable Views Summary

**Both `browser/disable_two_factor_authentication.py` and `browser/disable_two_factor_authentication_for_all_users.py` now refuse (server-side, before any member-data read or write) when `globally_enabled` is on, proven by five new tests that call the views directly and assert the flag/seed/reset-token are unchanged and the error message names no other account.**

## Performance

- **Duration:** ~25min
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments

- `disable_two_factor_authentication.py`'s `disable()` gains a second guard, immediately after
  the existing anonymous guard and before any read of the caller's own member data: with
  `globally_enabled` on it queues an `error` `IStatusMessage`, redirects to
  `@@personal-information`, and returns without writing. With it off, the view behaves exactly
  as before (D-08's conditionality is preserved, not a deletion of the feature).
- `disable_two_factor_authentication_for_all_users.py`'s `index()` gets the identical guard as
  its first statement, before `api.user.get_users()` — D-18, an operator-approved widening of
  MFA-16 beyond its literal "a user's own second factor" wording, recorded in-source with the
  2026-08-06 decision and the documented recovery path (turn `globally_enabled` off, then use
  this view).
- Both refusal messages are new `MessageFactory('imio.googleauthenticator')` msgids (D-12); the
  self-disable message speaks only of "this site" and "your own" account, the bulk message
  speaks only of "all users" as a class — neither names an individual account.
- `TestDisableTwoFactorAuthentication` gains three methods: refusal-plus-no-mutation while on,
  continued normal operation while off, and refusal for a caller who was never enrolled (the
  guard runs before any per-user enrollment check, so it does not treat an unenrolled caller as
  a no-op).
- New `TestDisableTwoFactorAuthenticationForAllUsers` class, with two methods: the bulk refusal
  (two real accounts, both still enrolled afterwards) and a zero-user-site probe (refused while
  on, completes without raising while off) via a real-collaborator stand-in
  (`_FakeApiWithNoUsers`) for `api.user.get_users()`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Both disable views refuse while global enforcement is on** - `bba586d` (feat)
2. **Task 2: Cover the refusal, its conditionality, and the bulk path** - `33cb604` (test)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py` — new
  `is_two_factor_authentication_globally_enabled` guard in `disable()`, with an in-source comment
  recording why hiding the menu link (D-09) is not the control, citing Phase 9's BUG-08 mirror.
- `src/imio/googleauthenticator/browser/disable_two_factor_authentication_for_all_users.py` —
  the same guard as the first statement of `index()`, with an in-source comment recording D-18's
  operator decision, date, reasoning, and the intact recovery path.
- `src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py` — three new
  methods on `TestDisableTwoFactorAuthentication`, a new `TestDisableTwoFactorAuthenticationForAllUsers`
  class with two methods, and the module-level `_FakeApiWithNoUsers` test collaborator.

## Decisions Made

- Guard ordering in `disable()`: after the anonymous check (so the existing
  `test_anonymous_request_is_refused_and_mutates_nothing` keeps getting its 401), before any
  read of the caller's own member data (so an unenrolled caller is refused, not silently
  no-op'd) — matching the plan's explicit ordering requirement.
- The bulk view's guard is the *only* guard added — it had no anonymous check before this plan
  and still does not; D-18 does not introduce one, since the view is already restricted to
  `cmf.ManagePortal` at the ZCML permission level.
- See `key-decisions` above (frontmatter) for the two decisions worth surfacing at a glance:
  the multi-account test shape, and the empty-user-list off-branch's actual scope.

## Deviations from Plan

None — plan executed exactly as written. One isort-only fix was needed and is not counted as a
deviation (mechanical import-line-wrapping, no behavioural change):

- After adding the new imports to `test_disable_two_factor_authentication.py`, `bin/code-analysis`
  flagged two `I001` "import in the wrong position" findings on the multi-line
  `disable_two_factor_authentication_for_all_users` import. `bin/isort -y` rewrote it to the
  single-line-with-backslash-continuation form this repo's `.isort.cfg` expects; re-ran the full
  suite and `bin/code-analysis` afterward, both green. No production or test logic changed.

## Issues Encountered

None beyond the isort fix noted above.

## Non-vacuity checks (mandatory, project convention since Phase 1)

All five new methods were run against unmodified source first (passing baseline, see Verification
Evidence), then each was falsified against a real source mutation in the scratchpad-backed
files, then the source was restored byte-identical (`git diff --stat` confirmed empty after every
restoration, both files) before the next check began.

**1 & 3. `test_disable_is_refused_while_globally_enabled_and_mutates_nothing` and
`test_disable_is_refused_for_an_unenrolled_user_too`** — deleted the entire D-08 guard block from
`disable_two_factor_authentication.py`'s `disable()`. Real failure output:

```
AssertionError: True != False : D-08: the refusal must not touch the flag.
```
```
AssertionError: 'error' not found in [u'info']
```

Restored byte-identical; `git diff --stat` confirmed empty.

**2. `test_disable_still_works_while_globally_disabled`** — made the guard's condition
unconditional (`if True:` instead of `if is_two_factor_authentication_globally_enabled():`). Real
failure output (this test's own assertion, plus a pre-existing test that also went red — evidence
the mutation was total, not partial):

```
AssertionError: True is not False
```
```
AssertionError: 'info' not found in [u'error']
```

Restored byte-identical; `git diff --stat` confirmed empty.

**4. `test_disable_for_all_users_is_refused_while_globally_enabled`** — deleted the entire D-18
guard block from `disable_two_factor_authentication_for_all_users.py`'s `index()`. Real failure
output:

```
AssertionError: False is not True : D-18: the refusal must not touch any account's flag -- 'all-users-disable-refused-1' must still be enrolled.
```

Restored byte-identical; `git diff --stat` confirmed empty.

**5. `test_disable_for_all_users_on_an_empty_user_list`** — same deletion (the guard removed for
check 4 falsifies this test too, exercised in the same run). Real failure output:

```
AssertionError: 'error' not found in [u'info'] : a zero-user site must still be refused while the setting is on.
```

Restored byte-identical; `git diff --stat` confirmed empty for both modified source files after
all five checks.

## User Setup Required

None — no external service configuration required.

## Verification Evidence

- `bin/test -t test_disable_two_factor_authentication -t test_controlpanel` (Task 1, before new
  tests existed) → **10 tests, 0 failures, 0 errors**.
- `bin/test -t test_disable_two_factor_authentication` (Task 2, with all 8 methods) →
  **8 tests, 0 failures, 0 errors** (3 pre-existing + 5 new).
- `bin/test -t '!robot'` → **155 tests, 0 failures, 0 errors** (150 baseline + 5 new), reproduced
  after every source restoration.
- `bin/code-analysis` → exits 0 (Flake8 OK), checked after each task commit and after the isort
  fix.
- Acceptance-criteria greps, all confirmed:
  - `grep -c 'is_two_factor_authentication_globally_enabled' disable_two_factor_authentication.py` → `2`
  - `grep -c 'is_two_factor_authentication_globally_enabled' disable_two_factor_authentication_for_all_users.py` → `2`
  - `grep -c 'class TestDisableTwoFactorAuthenticationForAllUsers' test_disable_two_factor_authentication.py` → `1`
  - `grep -cE '^    def test_disable' test_disable_two_factor_authentication.py` → `5`
  - `grep -cE '^    def test_' test_disable_two_factor_authentication.py` → `8`

## Known Stubs

None.

## Threat Flags

None beyond what the plan's own `<threat_model>` already names and mitigates. T-10-11 (the
single-user view) and T-10-12 (the bulk view) are both mitigated exactly as designed: the refusal
is server-side, before any read/write, asserted by calling the views directly rather than through
rendered markup. T-10-13 (information disclosure in the refusal message) is mitigated by the
message-text assertion in `test_disable_is_refused_while_globally_enabled_and_mutates_nothing`.
T-10-14 (the refusal trapping the operator) is an accepted residual per the plan's own
disposition, and the recovery path is documented in-source on the bulk view. T-10-15 (the
commented-out bulk-disable block in `controlpanel.py:152`) remains untouched, as scoped.

## Next Phase Readiness

- MFA-16 is now fully proven by test on both the single-user and bulk-disable paths. Plans 10-04
  through 10-06 can treat both refusals as settled, not provisional.
- The `settings_helper.py` link-visibility inversions (D-10/D-11, MFA-17/MFA-18) and the
  `regenerate_recovery_codes` action-condition fix (D-15) are still open for a later plan in this
  phase — this plan touched neither file.

## Self-Check: PASSED

Confirmed present on disk: `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py`,
`src/imio/googleauthenticator/browser/disable_two_factor_authentication_for_all_users.py`,
`src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py`, and this
SUMMARY.md. Confirmed present in `git log --oneline --all`: `bba586d`, `33cb604`.

---
*Phase: 10-global-enforcement-and-enrollment*
*Completed: 2026-08-06*
