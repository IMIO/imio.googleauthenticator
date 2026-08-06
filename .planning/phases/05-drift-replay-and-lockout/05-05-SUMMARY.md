---
phase: 05-drift-replay-and-lockout
plan: 05
subsystem: auth
tags: [plone, pas-plugin, totp, lockout, oracle, z3c.form]

# Dependency graph
requires:
  - phase: 05-03
    provides: browser/forms/reset_bar_code.py::handleSubmit metered with is_account_locked/register_failed_second_factor/reset_failed_second_factor
  - phase: 05-04
    provides: the sibling fix and test pattern at token.py, and the false-comment/oracle-property mirroring convention this plan follows
provides:
  - "browser/forms/reset_bar_code.py's locked branch now wraps its reason in the same \"Setup failed! {0}\" template the wrong-code branch already uses, closing the message-level lock-state oracle at @@reset-bar-code (MFA-08)"
  - "tests/test_reset_bar_code.py::test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account -- proves two-way message-list equality between a locked account and the same/a different unlocked, enrolled account for an anonymous, unsigned caller"
  - "05-VALIDATION.md's new MFA-08 (not an oracle, reset path) row, naming plan 05-05 and threat T-05-23"
affects: [08-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One message template swapped for another already-existing template in the same file and catalogue -- no new i18n msgid, no orphaned one"
    - "Two-way message-list equality (locked vs. unlocked, same account; then vs. a second distinct unlocked account) rather than three-way, since the user-not-found/is_site_local_user branches are explicitly out of scope (P5-17) at this endpoint"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
    - src/imio/googleauthenticator/tests/test_reset_bar_code.py
    - .planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md

key-decisions:
  - "P5-17/P5-18/P5-19/P5-20 followed exactly as the plan specified (see plan frontmatter Decisions table). No deviations from the plan's decision table."

requirements-completed: [MFA-08]

coverage:
  - id: D1
    description: "An anonymous, unsigned caller at @@reset-bar-code who supplies only auth_user cannot distinguish a locked account from the same account unlocked, nor from a different unlocked, enrolled account -- asserted on the ordered list of rendered status messages, not a substring"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "tests/test_reset_bar_code.py#test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account"
        status: pass
    human_judgment: false
  - id: D2
    description: "The lock gate still runs strictly before validate_token (line-order verified), and register_failed_second_factor/reset_failed_second_factor/try/except call sites are untouched"
    requirement: "MFA-08"
    verification:
      - kind: other
        ref: "grep -n 'is_account_locked(\\|validate_token(' src/imio/googleauthenticator/browser/forms/reset_bar_code.py (locked-check precedes validate_token); git diff shows zero changed lines with register_failed_second_factor/reset_failed_second_factor/try:/except"
        status: pass
    human_judgment: false
  - id: D3
    description: "The comment above the gate is honest: it names the coupling to the shared reason-is-not-None tail, cites MFA-08, and states the two-way (not three-way) scope"
    verification:
      - kind: other
        ref: "git diff src/imio/googleauthenticator/browser/forms/reset_bar_code.py -- comment replaced, contains 'validate_token' and 'MFA-08'"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-01
status: complete
---

# Phase 5 Plan 5: Reset-Bar-Code Lock-State Oracle Gap Closure Summary

**Swapped the locked branch's message wrapper at `@@reset-bar-code` from `"Resetting of the bar-code failed! {0}"` to the already-existing `"Setup failed! {0}"` the wrong-code path uses, closing the message-level oracle 05-03's T-05-03 claim had wrongly assumed was already closed -- proven by a new test asserting two-way equality of the full ordered list of rendered status messages.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-01 (continuing Phase 05 execution)
- **Completed:** 2026-08-01
- **Tasks:** 1 (RED test / GREEN fix, per the plan's `tdd="true"` / `type="tracer"` task)
- **Files modified:** 3

## Accomplishments

- Added `test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account` to `TestResetBarCodeLockout` in `tests/test_reset_bar_code.py`. It locks `TEST_USER_NAME` directly, submits one wrong code anonymously (no `signature`, no `auth_timestamp`) and captures the ordered list of rendered `portalMessage error` texts; unlocks the same account and repeats; creates a second distinct enrolled account (`reset-unlocked-enrolled-user`, guarded creation for a warm layer) and repeats a third time. Asserts, in order: same-account locked-vs-unlocked equality (primary), unlocked-vs-other-unlocked equality (control, isolates lock state from anything account-specific), then locked-vs-other-unlocked equality (the literal `05-VERIFICATION.md missing[1]` contract).
- **Confirmed RED against unmodified source** before touching production code: assertion 1 failed with
  ```
  AssertionError: Lists differ: ['Invalid signature!', 'Resett... != ['Invalid signature!', 'Setup ...
  First differing element 1:
  Resetting of the bar-code failed! Invalid token or token expired.
  Setup failed! Invalid token or token expired.
  ```
  This is the non-vacuity evidence `05-VALIDATION.md` requires: the two sides differ only by their leading message template, exactly as predicted.
- Fixed `reset_bar_code.py::handleSubmit`'s locked branch: the `IStatusMessage` wrapper changed from `_("Resetting of the bar-code failed! {0}".format(reason))` to `_("Setup failed! {0}".format(reason))`. Both msgids already exist in `locales/imio.googleauthenticator.pot` and all three `.po` catalogues; no i18n file touched.
- Replaced the false five-line comment above the gate (it previously asserted the response "cannot be used as an oracle," which was false -- the branches shared the embedded `reason` but not the top-level wrapper) with one naming the coupling to the shared `reason is not None` tail, citing MFA-08, confirming the gate still runs before `validate_token`, and stating the honest two-way scope (P5-17's carve-out for `user not found`/`is_site_local_user` remains explicit).
- Added the `MFA-08 (not an oracle, reset path)` row to `05-VALIDATION.md`'s Per-Requirement Verification Map, naming this test, Plan `05-05`, Wave `1`, Threat Ref `T-05-23` -- a new row rather than overloading the existing `MFA-08 (reset path)` row, which is the lockout-threshold predicate with a different test.
- `bin/test -t '!robot'`: 84 tests, 0 failures, 0 errors, run twice in a row.

## Task Commits

Each step of the single TDD task was committed atomically:

1. **RED: add failing test** - `21d5572` (test)
2. **GREEN: close the oracle** - `be31592` (feat)
3. **Record the validation row** - `deaf3d0` (docs)

_TDD task: test → feat → docs (docs substituting for a refactor commit, since the plan's own Step 4 required a `05-VALIDATION.md` row rather than code cleanup)._

## Files Created/Modified

- `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` - Locked-branch message wrapper swapped to `"Setup failed! {0}"`; comment above the gate rewritten to state the true, narrower guarantee
- `src/imio/googleauthenticator/tests/test_reset_bar_code.py` - New test method proving two-way message-list equality (locked/unlocked, same and different accounts)
- `.planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md` - New `MFA-08 (not an oracle, reset path)` row

## Decisions Made

- P5-17, P5-18, P5-19 and P5-20 followed exactly as the plan specified (see `key-decisions` above and the plan's own Decisions table). No deviations from the plan's decision table.

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria satisfied on the first implementation, no Rule 1/2/3 fixes needed.

## Non-Vacuity / RED Evidence

Recorded verbatim above under Accomplishments: the new test was run against unmodified source before the fix and failed on the same-account locked-vs-unlocked assertion, with the reported difference being exactly the leading message template (`"Resetting of the bar-code failed!"` vs. `"Setup failed!"`). File restored to the fixed state immediately after (this is the tracer's real, intended final state -- no revert-and-restore dance was needed since the RED observation used the actual planned test against actual unmodified source, per the plan's stated preference over 05-04's revert/restore idiom).

## Acceptance Criteria Verification

- `bin/test -t test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account` passes.
- `bin/test -t test_reset_bar_code` -- 2 tests, 0 failures.
- `bin/test -t '!robot'` -- 84 tests, 0 failures, 0 errors, twice in a row.
- `grep -c 'def test_' tests/test_reset_bar_code.py` -> 2; `git diff` added one `def test_`, modified no existing method body.
- New method's URLs contain neither `signature` nor `auth_timestamp`; its `Browser` objects were never passed to `_login_browser`.
- Line order: `is_account_locked(` (line 123) precedes `validate_token(` (line 132).
- Comment-immune source counts: `grep -v '^\s*#' ... | grep -c 'Setup failed'` -> 2 (locked branch + shared tail); same pipeline counting `Resetting of the bar-code failed` -> 3 (user-not-found, non-site-local, invalid-reset-token).
- `git diff` on `reset_bar_code.py` shows the comment replaced (not relocated), containing `validate_token` and `MFA-08`.
- `git diff` shows zero changed lines containing `register_failed_second_factor`, `reset_failed_second_factor`, `try:` or `except`.
- `git diff --name-only` across the three commits lists exactly `src/imio/googleauthenticator/browser/forms/reset_bar_code.py`, `src/imio/googleauthenticator/tests/test_reset_bar_code.py`, `.planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md` -- no other file, and nothing under `locales/`.
- `test_reset_bar_code_lockout_after_five_failures` passes unmodified.
- `05-VALIDATION.md` carries the `MFA-08 (not an oracle, reset path)` row naming this test, `Plan` = `05-05`.

## Issues Encountered

None. The commit hook's `bin/code-analysis` failure is the documented pre-existing 318-finding debt (CLAUDE.md); all three commits used `--no-verify` per this repository's stated exception, and no other failure occurred.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MFA-08's "not an oracle" half is now closed at both call sites this phase covers: `token.py` (plan 05-04) and `reset_bar_code.py` (this plan). The two out-of-scope enumeration branches at `reset_bar_code.py` (`user not found`, `is_site_local_user`) remain a recorded, operator-accepted finding (P5-17) -- carried forward per the plan's own "Known, unaddressed" table, not silently dropped.
- `bin/test -t '!robot'` is green at 84 tests (up from 83 at this plan's start), run twice in a row.
- No blockers introduced by this plan. The pre-existing Phase 5 blockers/concerns in `STATE.md` (external encryption-key fragment, code-analysis debt through Phase 8) are unaffected.

---
*Phase: 05-drift-replay-and-lockout*
*Completed: 2026-08-01*

## Self-Check: PASSED

All 3 modified files confirmed present on disk; all 3 task commit hashes
(`21d5572`, `be31592`, `deaf3d0`) confirmed in `git log`.
