---
phase: 05-drift-replay-and-lockout
plan: 03
subsystem: auth
tags: [plone, pas-plugin, totp, lockout, memberdata, z3c.form, oracle]

# Dependency graph
requires:
  - phase: 05-01
    provides: helpers.is_account_locked / register_failed_second_factor / reset_failed_second_factor, and the three memberdata properties they read/write
  - phase: 05-02
    provides: rewritten helpers.validate_token (drift, replay, format gate) that reset_bar_code.py calls unchanged
provides:
  - "browser/forms/reset_bar_code.py::handleSubmit metered with the same lock gate and counter as token.py -- closing the anonymous TOTP guessing oracle at @@reset-bar-code (permission=\"zope2.View\", attacker-named account, token checked before the reset signature)"
  - "tests/test_reset_bar_code.py (new) proving the reset path locks after five failures, the lock has no bypass at the login token form, and the lock is bounded/self-clearing"
  - "CHANGES.rst 1.0.0 (unreleased) entries for the whole of phase 5: drift/replay acceptance, the format gate, the shared lockout on both form views, the two new control-panel settings, and the profile-import upgrade note"
affects: [08-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A second, near-identical application of the token-form lockout gate on browser/forms/reset_bar_code.py, sharing the same helpers and memberdata properties -- one counter, one lock, no per-view budget"
    - "The success-branch counter/lock reset is placed before the try/except Exception block that wraps the bar-code-reset-token comparison, so a PropertyValueError from a mis-declared property surfaces rather than being reported as 'An unexpected error occurred.'"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_reset_bar_code.py
  modified:
    - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
    - CHANGES.rst
    - .planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md

key-decisions:
  - "P5-12/P5-13/P5-14 followed exactly as the plan specified: lockout scope covers token.py and reset_bar_code.py (user_setup.py excluded), the anonymous-triggerable lock is an accepted trade-off bounded by lockout_duration, and the success-branch counter reset is placed before the try block, not inside it."

patterns-established:
  - "Pattern: when a second call site needs the same security gate as an already-gated sibling, mirror the sibling's exact placement rule (after the account guards, before validate_token) rather than re-deriving it."

requirements-completed: [MFA-08, MFA-11, MFA-12]

coverage:
  - id: D1
    description: "Five anonymous wrong codes submitted at @@reset-bar-code (no valid signature, target account named via the auth_user query parameter) lock the account for the configured duration; the fourth submission does not"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "tests/test_reset_bar_code.py#test_reset_bar_code_lockout_after_five_failures"
        status: pass
    human_judgment: false
  - id: D2
    description: "The lock set through @@reset-bar-code has no bypass: it also refuses a correct code at the login token form (@@google-authenticator-token), because both views share one counter and one lock property"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "tests/test_reset_bar_code.py#test_reset_bar_code_lockout_after_five_failures"
        status: pass
    human_judgment: false
  - id: D3
    description: "A correct code at @@reset-bar-code clears the counter and the lock, even though the bar-code-reset signature check then fails for lack of a valid signature -- the second factor succeeded, which is what the counter measures"
    requirement: "MFA-11"
    verification:
      - kind: integration
        ref: "tests/test_reset_bar_code.py#test_reset_bar_code_lockout_after_five_failures"
        status: pass
    human_judgment: false
  - id: D4
    description: "The lock an anonymous party can trigger against a named account is bounded to lockout_duration seconds and clears itself with no administrator action"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "tests/test_reset_bar_code.py#test_reset_bar_code_lockout_after_five_failures"
        status: pass
    human_judgment: false
  - id: D5
    description: "The counter and lock writes in reset_bar_code.py sit outside the file's existing broad except Exception block, and browser/forms/user_setup.py is left completely untouched"
    requirement: "MFA-12"
    verification:
      - kind: integration
        ref: "tests/test_reset_bar_code.py#test_reset_bar_code_lockout_after_five_failures"
        status: pass
      - kind: other
        ref: "git diff -- src/imio/googleauthenticator/browser/forms/user_setup.py (empty)"
        status: pass
    human_judgment: false
  - id: D6
    description: "CHANGES.rst records phase 5's behaviour changes and states plainly that the imio.googleauthenticator:default profile must be (re-)imported for the two new registry records and three new memberdata properties to exist, with no GenericSetup upgrade step shipped"
    verification:
      - kind: other
        ref: "grep -c 'imio.googleauthenticator:default' CHANGES.rst (>=1), grep -c 'lockout_duration'/'max_failed_attempts' CHANGES.rst (>=1 each)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-31
status: complete
---

# Phase 5 Plan 3: Reset-Bar-Code Lockout and Changelog Summary

**`browser/forms/reset_bar_code.py::handleSubmit` metered with the exact same lock gate, counter and reset calls as `token.py`, closing the anonymous TOTP guessing oracle at `@@reset-bar-code` -- proven by a new `tests/test_reset_bar_code.py` whose central assertion is that the lock has no separate budget at the login form, plus the phase-wide `CHANGES.rst` entry.**

## Performance

- **Duration:** ~12 min (17:48 -> 18:00, commit timestamps)
- **Started:** 2026-07-31T17:48:19+02:00 (previous plan's completion commit)
- **Completed:** 2026-07-31T18:00:01+02:00
- **Tasks:** 3
- **Files modified:** 4 (1 created)

## Accomplishments

- `reset_bar_code.py::handleSubmit` now checks `is_account_locked(user)` after the `if not user:` and `if not is_site_local_user(user):` guards and before `validate_token` is ever called, reusing the file's existing `"Invalid token or token expired."` message verbatim so a locked account is indistinguishable from a wrong code -- no new i18n string.
- On the success branch, `reset_failed_second_factor(user)` is called as the first statement inside `if valid_token:`, **before** the `try:` that wraps the bar-code-reset-token comparison (decision P5-14) -- so the reset survives even when the reset signature then fails, and a `PropertyValueError` from a mis-declared property would surface rather than be swallowed by the file's pre-existing `except Exception` block.
- On the wrong-code branch, `register_failed_second_factor(user)` is called before the generic error message is set, outside any `try` block.
- `tests/test_reset_bar_code.py` (new): a single `test_reset_bar_code_lockout_after_five_failures` proving, in order: the view really is anonymously reachable and renders (non-vacuity control for the whole plan's rationale), five wrong codes lock the account (with a four-submission non-lock control), the lock refuses a **correct** code at the login token form too (the bypass assertion -- one shared counter, no separate budget), the stored epoch is bounded by `lockout_duration`, a past epoch restores service with no administrator action, and a correct code at `@@reset-bar-code` itself clears the counter and lock even when the reset signature then fails (MFA-11).
- `CHANGES.rst`: five new entries under `1.0.0 (unreleased)` covering drift/replay acceptance, the exact-six-digit format gate, the shared lockout on both form views, the two new control-panel settings, and the profile-import upgrade note (`registry.forInterface` and `getProperty` both raise loudly on an unimported profile, so a lockout that never locks is not a possible failure mode).
- `05-VALIDATION.md`: filled the MFA-08 (reset path) and MFA-11 rows for this plan, and -- as a deviation documented below -- filled the MFA-05/06/07 rows that plan 05-02 had left as `TBD`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Meter the bar-code reset form with the same counter and lock** - `b4139b1` (feat)
2. **Task 2: Prove the reset path is metered and the lock has no bypass** - `bd8e44f` (test)
3. **Task 3: Record the phase in CHANGES.rst, including the profile-import requirement** - `e7ed383` (docs)

**Plan metadata (deviation fix, see below):** `a691c4a` (docs)

_No TDD tasks in this plan; each task was a single commit._

## Files Created/Modified

- `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` - Lock gate + counter register/reset calls wired into `handleSubmit`
- `src/imio/googleauthenticator/tests/test_reset_bar_code.py` - New; `TestResetBarCodeLockout`, one method
- `CHANGES.rst` - Five new `1.0.0 (unreleased)` entries covering all of phase 5
- `.planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md` - MFA-08 (reset path) and MFA-11 rows filled (this plan); MFA-05/06/07 rows filled (deviation, see below)

## Decisions Made

- P5-12, P5-13 and P5-14 followed exactly as the plan specified (see `key-decisions` in frontmatter above). No deviations from the plan's decision table.
- The Task 2 test is a single method covering all of the plan's required assertions in one ordered sequence, rather than split across several `test_*` methods, since the plan itself frames this file's one requirement (the reset path shares the token form's lock with no bypass) as a single ordered proof rather than several independent behaviours -- consistent with `tests/test_helpers.py`'s "one method per requirement" convention, since this module has exactly one requirement.

## Deviations from Plan

### Auto-fixed Issues

None - all three tasks executed within the plan's design. No Rule 1/2/3 bug-fixes were needed; the plan's own `read_first` excerpts and pattern map were accurate against the current source.

### Clarifications (not deviations in scope, but worth recording)

**1. [Rule 2 - Missing Critical] Filled the MFA-05/06/07 rows in `05-VALIDATION.md` that plan 05-02 left as `TBD`, and fixed a stale `test_token_form` reference.**
- **Found during:** Task 2/3, while satisfying this plan's own `<verification>` requirement that "`05-VALIDATION.md` has every row's `Plan` column filled and no row still naming `tests/test_token_form.py`".
- **Issue:** Plan 05-02 (drift and replay) landed its tests and passed its own acceptance criteria, but did not update its own rows in `05-VALIDATION.md` -- the MFA-05, MFA-06, MFA-06 (log), MFA-07 and MFA-07 (regression) rows were still `TBD`/`⬜ pending`. Separately, the "After every task commit" sampling command still named the pre-rename `test_token_form` module (renamed to `test_token.py` in plan 05-01, decision P5-06).
- **Fix:** Filled `Plan=05-02`, `Wave=2` (matching 05-02-PLAN.md's own frontmatter), and the `Threat Ref` column from 05-02-PLAN.md's own STRIDE register (T-05-13 for the drift-acceptance/future-rejection pair, T-05-02 for replay rejection, T-05-04 for the no-username log, T-05-14 for the format gate), `Status=✅ green` per 05-02-SUMMARY.md's recorded coverage (D1/D2/D4/D6, all `pass`). Corrected the sampling command to `test_token`.
- **Files affected:** `.planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md`.
- **Verification:** No test impact (documentation only). `bin/test -t '!robot'` re-run green (82 tests) after the change, since it touches only `.planning/`.
- **Committed in:** `a691c4a` (separate docs commit, since it corrects a gap in a prior plan rather than this plan's own task list).

---

**Total deviations:** 0 auto-fixed bugs. 1 documentation-completeness fix recorded above (Rule 2: this plan's own `<verification>` block required every row filled, and the gap was left by a prior plan).
**Impact on plan:** None on this plan's delivered scope. The fix only concerns a documentation gap in a sibling plan's own aftermath.

## Non-Vacuity Mutation Check

Required by Task 2's acceptance criteria, performed by hand: removed the `register_failed_second_factor(user)` call from the wrong-code branch of `reset_bar_code.py::handleSubmit`. Re-ran `test_reset_bar_code_lockout_after_five_failures`: **red**, `AssertionError: 0 not greater than <epoch> : MFA-08: the 5th consecutive wrong code at @@reset-bar-code must lock the account` -- the fifth wrong submission no longer locked the account because the counter was never incremented. Restored the file; `diff` against the pre-mutation copy confirmed byte-identical. Full suite re-run green (82 tests, twice in a row).

## Issues Encountered

None. The pattern map's excerpts of `reset_bar_code.py::handleSubmit` and `token.py::handleSubmit` matched the current source exactly, and driving the reset form anonymously through `zope.testbrowser` worked on the first attempt -- the plan's named fallback (the direct `request.form` / `ResetBarCodeForm(...).update()` idiom from `test_request_bar_code_reset.py`) was not needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 (drift, replay and lockout) is now complete: all three plans (05-01 substrate/token-form gate, 05-02 drift/replay/format-gate, 05-03 reset-bar-code gate + changelog) landed, `bin/test -t '!robot'` is green at 82 tests (up from 66 at phase seed time), run twice in a row.
- `05-VALIDATION.md` now has every automated row's `Plan`/`Wave`/`Threat Ref`/`Status` column filled and no stale `test_token_form` reference; two manual-only verifications remain deferred to the phase's end-of-phase human verification pass per `config.json`'s `human_verify_mode: end-of-phase` (the control-panel field persistence check, and the real-device drift-boundary check recorded by plan 05-02).
- `browser/forms/user_setup.py` remains completely untouched across all three plans in this phase, confirmed by an empty `git diff` at each plan's own acceptance check.
- No blockers.

---
*Phase: 05-drift-replay-and-lockout*
*Completed: 2026-07-31*

## Self-Check: PASSED

All 5 created/modified files confirmed present on disk; all 4 task commit
hashes (`b4139b1`, `bd8e44f`, `e7ed383`, `a691c4a`) confirmed in `git log`.
