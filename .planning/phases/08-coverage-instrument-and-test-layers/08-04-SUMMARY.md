---
phase: 08-coverage-instrument-and-test-layers
plan: 04
subsystem: testing
tags: [coverage, z3c.form, ska, unit-tests, ci-gate]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Corrected .coveragerc, coverage 5.5, bin/test-coverage with set -e, and per-module Missing line baselines"
  - phase: 08-03
    provides: "Every test class on IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING; post-migration coverage baseline 84%"
provides:
  - "TOTAL branch coverage above 90% (90.03% precise) against the corrected instrument"
  - "Real, asserting tests for the per-user disable view, the bulk disable view, the control-panel save handler's five branches, and 8 of reset_bar_code.py's 9 previously-missing branches"
  - ".github/workflows/package-test.yml runs bin/test-coverage, so the 90% threshold gates every push"
  - "A documented, worked-around process-wide shared-mutable-state hazard in ResetBarCodeForm's qr_code field description"
affects: [08-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "z3c.form direct-call testing: build a real ska Signature with Signature.generate_signature, wire it onto self.request (form dict + QUERY_STRING), matching what request_bar_code_reset.py mints for a real reset email -- the only way to reach a form's genuinely-signed-request success branches without a live Browser round-trip"
    - "Reset process-wide mutable schema-field state (IResetBarCodeForm['qr_code'].description) in setUp(), captured once at import time, so test order cannot make an assertion pass or fail vacuously"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py
  modified:
    - src/imio/googleauthenticator/tests/test_controlpanel.py
    - src/imio/googleauthenticator/tests/test_reset_bar_code.py
    - .github/workflows/package-test.yml

key-decisions:
  - "Task 3 could not clear 90% TOTAL by extending test_reset_bar_code.py alone (that module maxed out at 99%, landing TOTAL at 89.73%) -- extended test_controlpanel.py as well, outside Task 3's originally declared <files> list, to close controlpanel.py's remaining two branches and reach 90.03%"
  - "Discovered mid-Task-3 that the existing test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken's part-3 assertion (control-panel Save) passes for the wrong reason: its handleSave call returns early on a RequiredMissing extraction error (max_failed_attempts/lockout_duration never filled), and Products.statusmessages only clears its cookie on a non-redirect response, so the assertion reads a leftover 'error' message from an earlier call in the same test method rather than a fresh handleSave outcome. Not fixed -- out of this plan's scope and the existing test still passes -- but documented here and in the new test's docstring so the next reader does not trust it as evidence of that branch"
  - "IResetBarCodeForm's qr_code field description is process-wide mutable class-level state (zope.schema.Field is a singleton per Interface, not per-request) -- updateFields()'s non-success branches never reset it after a prior success, so a QR-code HTML leak from one test's success case corrupted a later test's assertion regardless of alphabetical run order. Worked around by resetting to the captured default in setUp(); production code left untouched per this plan's own prohibition"

requirements-completed: [QUAL-04]

coverage:
  - id: D1
    description: "Per-user 2FA-disable view: anonymous guard (401 + no mutation), full property clear, status message + redirect -- each proven non-vacuous"
    requirement: "QUAL-04"
    verification:
      - kind: unit
        ref: "tests/test_disable_two_factor_authentication.py -- bin/test -t test_disable_two_factor_authentication: 3 tests, 0 failures"
        status: pass
    human_judgment: false
  - id: D2
    description: "Bulk disable view and two untested control-panel save-handler branches (globally-disabled, neither-true-nor-false) -- each proven non-vacuous"
    requirement: "QUAL-04"
    verification:
      - kind: unit
        ref: "tests/test_controlpanel.py -- bin/test -t test_controlpanel: 4 new tests, 0 failures (this task's slice)"
        status: pass
    human_judgment: false
  - id: D3
    description: "reset_bar_code.py's 8 previously-missing branches closed (extraction errors, unknown user, non-site-local user, both updateFields QR-embed branches, handleSubmit success path, bare except arm); one branch (200->215, barcode_field falsy) named undrivable"
    requirement: "QUAL-04"
    verification:
      - kind: unit
        ref: "tests/test_reset_bar_code.py -- bin/test -t test_reset_bar_code: 10 tests, 0 failures"
        status: pass
    human_judgment: false
  - id: D4
    description: "Two further control-panel branches closed to clear TOTAL 90% (handleSave globally-enabled-True success and exception arm, handleCancel)"
    requirement: "QUAL-04"
    verification:
      - kind: unit
        ref: "tests/test_controlpanel.py -- bin/test -t test_controlpanel: 7 tests total, 0 failures"
        status: pass
    human_judgment: false
  - id: D5
    description: "TOTAL branch coverage above 90% (90.03% precise); bin/test-coverage -t '!robot' exits 0; CI workflow's test_command runs bin/test-coverage"
    requirement: "QUAL-04"
    verification:
      - kind: other
        ref: "bin/test-coverage -t '!robot' -- exit 0, TOTAL 1048 stmts/72 missed, 286 branches/53 partial, 90% (90.03% at --precision=2); grep test_command .github/workflows/package-test.yml shows bin/test-coverage"
        status: pass
    human_judgment: false

duration: ~2h
completed: 2026-08-05
status: complete
---

# Phase 08 Plan 04: Coverage Gap Closure and CI Gate Summary

**Closed the branch-coverage gap from 87% to 90.03% by writing real, asserting tests for the four weakest modules named in the plan, discovering and working around a process-wide shared-mutable-state test hazard along the way, then pointed CI's `test_command` at `bin/test-coverage` so the 90% threshold gates every push.**

## Performance

- **Duration:** ~2h
- **Started:** 2026-08-05 (session start)
- **Completed:** 2026-08-05
- **Tasks:** 3 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- **Task 1** — `browser/disable_two_factor_authentication.py`'s single `disable()` method (40% coverage, zero tests before this plan) now has three tests: the anonymous 401 guard asserted on *effect* (the member property is unchanged, not just the status code), the full three-property clear, and the status-message-type + redirect-target assertion. Module coverage 40% → 100%.
- **Task 2** — the bulk disable view (`@@google-authenticator-disable-for-all-users`, 56% coverage, zero tests) now asserts both the `'info'` message and that a previously-enabled user is actually disabled. The control-panel save handler's two previously-untested branches (`globally_enabled is False`, and neither True nor False) are each covered, asserting that changes are applied and no user is enabled or disabled as a side effect. Module coverage: `disable_two_factor_authentication_for_all_users.py` 56% → 100%; `controlpanel.py` 68% → 86% (this task's slice).
- **Task 3** — `reset_bar_code.py` (76% coverage) got 8 new tests closing extraction-error, unknown-username, non-site-local-user, both `updateFields` QR-embed branches (success and stale-token), the full `handleSubmit` success path, and the bare `except Exception` arm. Module coverage 76% → 99%, with one branch (`200->215`, `barcode_field` always truthy in this schema) named as undrivable rather than chased with a pragma. Closing this module alone still left TOTAL at 89.73%, so `test_controlpanel.py` got two further methods (the `globally_enabled is True` success and exception-arm branches, plus `handleCancel`) to clear 90%. TOTAL branch coverage: 87% → 90% (90.03% precise, confirmed with `--precision=2`). `.github/workflows/package-test.yml`'s `test_command` now runs `bin/test-coverage -t !robot` instead of the plain `bin/test`.
- Every one of the 14 new test methods across this plan (3 + 4 + 7) has a recorded non-vacuity control: the production branch was temporarily broken, the test confirmed red, then the source was restored and `git diff` confirmed byte-identical before moving on.
- A genuine, previously-undetected shared-mutable-state hazard was found in `ResetBarCodeForm`: `IResetBarCodeForm['qr_code']` is a `zope.schema.Field` singleton bound to the *Interface class*, not per-request, and `updateFields()`'s success branch mutates its `.description` in place with no reset on the non-success branches. Two new tests running in the same process would silently leak a prior success's QR-code HTML into a later test's failure-path assertion, regardless of alphabetical run order. Worked around entirely in test code (captured the schema default once at import time, reset it in `setUp()`); production code is untouched, per this plan's own prohibition against changing behaviour while writing tests for it.

## Task Commits

1. **Task 1: Test the per-user 2FA-disable view — the weakest module in the package** - `df830be` (feat, `--no-verify` — see Deviations)
2. **Task 2: Test the bulk disable view and the control-panel save handler's untested branches** - `6f84f1e` (feat, `--no-verify` — see Deviations)
3. **Task 3: Clear 90% and make CI enforce it** - `6fdafab` (feat, `--no-verify` — see Deviations)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py` (created) — 3 tests for the per-user disable view
- `src/imio/googleauthenticator/tests/test_controlpanel.py` (modified) — 7 new test methods total across Tasks 2 and 3 (bulk disable view, four `handleSave` branches, `handleCancel`), plus a shared `_fill_required_save_widgets` helper and one new import (`helpers`)
- `src/imio/googleauthenticator/tests/test_reset_bar_code.py` (modified) — 8 new test methods, a shared `_sign_reset_request` helper for building real `ska` signatures, a module-level `_raise_value_error` stand-in, the `IResetBarCodeForm['qr_code']` process-wide-state reset in `setUp`/`tearDown`, and five new imports
- `.github/workflows/package-test.yml` (modified) — `test_command` value changed from `'bin/test -t !robot'` to `'bin/test-coverage -t !robot'`; nothing else in the file changed

## Coverage Progression

| Point | TOTAL | disable_2fa.py | disable_all.py | controlpanel.py | reset_bar_code.py |
|---|---|---|---|---|---|
| Plan 08-01 baseline (pre-04) | 84% | 40% | 56% | 68% | 76% |
| After Task 1 | 85% | 100% | 56% | 68% | 76% |
| After Task 2 | 87% | 100% | 100% | 86% | 76% |
| After Task 3 (reset_bar_code.py alone) | 89.73% | 100% | 100% | 86% | 99% |
| After Task 3 (+ controlpanel.py) | 90.03% | 100% | 100% | 100% | 99% |

Measured with `bin/coverage run --rcfile=.coveragerc bin/test -t '!robot'` then `bin/coverage report --rcfile=.coveragerc -m` (and `--precision=2` for the exact decimal). `bin/test-coverage -t '!robot'` exits 0 at the final point.

## Decisions Made

- **Task 3's declared `<files>` list (`test_reset_bar_code.py` + the workflow file) was insufficient to satisfy the plan's own `above 90%` truth criterion.** `reset_bar_code.py` reached 99% (its remaining branch is undrivable — see below), but TOTAL landed at 89.73%. `test_controlpanel.py` (already touched in Task 2) was extended with two more methods to close `controlpanel.py`'s last two branches, reaching 90.03%. Documented here as a deviation rather than silently reached, since the plan's `<files>` list did not name this file for Task 3.
- **`200->215` in `reset_bar_code.py` (the `if barcode_field:` false branch) is named undrivable, not chased.** `barcode_field = self.fields.get('qr_code')` and `qr_code` is declared unconditionally on `IResetBarCodeForm`, so this attribute is always truthy for any real instantiation of `ResetBarCodeForm`. No pragma applied; the branch is simply left in the `Missing` column.
- **The existing `test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken`'s part-3 assertion was found to pass for the wrong reason.** Its `handleSave` call never fills `max_failed_attempts`/`lockout_duration`, so `extractData()` reports `RequiredMissing` for both and `handleSave` returns before line 128 — the `'error'` assertion that follows is reading a leftover message from part 2's `view.index()` call in the *same* test method, because `Products.statusmessages.StatusMessage.show()` only clears its cookie when the response status is not a redirect, and part 2 ends in a 302. Not fixed (it is a pre-existing test outside this plan's file list, and it still passes) but recorded here and in `test_handleSave_globally_enabled_true_reports_error_when_seed_key_is_broken`'s docstring so a future reader does not mistake it for real coverage of that branch — which is exactly why `controlpanel.py:134-143` still showed as `Missing` before this plan's own, correctly-filled version of the same scenario.
- **`IResetBarCodeForm['qr_code'].description` reset added to `TestResetBarCodeLockout.setUp()`.** Discovered via a genuine cross-test failure (not hypothetical): two new test methods running in the same process, in alphabetical order, failed because a prior successful `updateFields()` call had mutated the schema field's description in place and nothing ever reset it. The fix lives entirely in test code — the default description string is captured once at module import time and reassigned in `setUp()` before every test — production code (`browser/forms/reset_bar_code.py`) is unchanged.

## Deviations from Plan

### Auto-fixed Issues

**1. [CLAUDE.md-documented, expected] All three task commits required `--no-verify`**
- **Found during:** every task's commit
- **Issue:** the buildout-installed pre-commit hook runs `bin/code-analysis`, which fails on pre-existing findings unrelated to this plan's files (documented in CLAUDE.md and this plan's own `<verification>` "Commit note": pre-commit stays red until plan 08-05).
- **Fix:** committed with `--no-verify`, exactly as anticipated.
- **Files modified:** none beyond those already staged
- **Committed in:** `df830be`, `6f84f1e`, `6fdafab`

**2. [Rule 3 — blocking, scope adjustment] Extended `test_controlpanel.py` in Task 3, outside its declared `<files>` list**
- **Found during:** Task 3, after closing `reset_bar_code.py` to 99% left TOTAL at 89.73%
- **Issue:** Task 3's `<files>` list named only `test_reset_bar_code.py` and the CI workflow file, but `reset_bar_code.py` alone could not supply enough uncovered surface to clear the plan's own 90% truth criterion — it was already at 99% with only one (undrivable) branch left.
- **Fix:** added two test methods to `test_controlpanel.py` (a file this same plan already touches in Task 2) covering `controlpanel.py`'s last two missing branches, reaching TOTAL 90.03%. No new files or unrelated modules touched.
- **Files modified:** `src/imio/googleauthenticator/tests/test_controlpanel.py`
- **Committed in:** `6fdafab`

**3. [Rule 1/Rule 3 — test-infrastructure, no production change] Reset `IResetBarCodeForm['qr_code'].description` in `setUp()`**
- **Found during:** Task 3, running the new `updateFields` tests together
- **Issue:** `zope.schema.Field.description` is mutable state on the Interface's field object, shared by every `ResetBarCodeForm` instance in the process. A successful `updateFields()` call in one test leaked its rendered QR-code HTML into the field's description for every later test in the same run, regardless of alphabetical order, since the non-success branches never reset it.
- **Fix:** captured the schema's default description string once at module import time (`_QR_CODE_DEFAULT_DESCRIPTION`) and reassigned it in `setUp()` before every test. No production code changed — confirmed via `git diff` on `browser/forms/reset_bar_code.py`.
- **Files modified:** `src/imio/googleauthenticator/tests/test_reset_bar_code.py`
- **Committed in:** `6fdafab`

---

**Total deviations:** 3 (1 expected/pre-authorized `--no-verify`, 1 scope adjustment to satisfy the plan's own truth criterion, 1 test-infrastructure fix for a discovered shared-mutable-state hazard — none touched production code behaviour)
**Impact on plan:** None on the plan's goal. All three landed within the same plan's file family and none altered the behaviour of any module under test.

## Issues Encountered

- `z3c.form`'s `SingleCheckBoxWidget`/`BoolSingleCheckboxDataConverter` requires the widget's `-empty-marker` sibling key (not the widget's own name) to distinguish "checkbox unchecked" from "field entirely absent from the request" — the load-bearing distinction between this plan's `globally-disabled` and `neither` test scenarios. Confirmed empirically before writing the real tests.
- `validate_user_data`'s `extract_request_data(request)` reads `request.get('QUERY_STRING')` directly (not `request.form`), so exercising `reset_bar_code.py`'s signed-request branches required setting both `self.request.environ['QUERY_STRING']` and the individual `self.request.form[...]` keys, matching what a real `ZPublisher` request assembles from a GET query string.
- A real browser POST always submits every rendered `<input>`, including the `qr_code` text field that nothing ever fills in — an *absent* key (as a hand-built `TestRequest` would otherwise have) makes `z3c.form.field.Fields.extract()` fall back to the field's own `missing_value` rather than the empty-string `FieldDataConverter` conversion a real submission produces, raising a spurious `WrongType`. Fixed by explicitly setting the widget's key to `u''` in the two new success-path tests.

## User Setup Required

None — no external service configuration required. The `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` environment variable used by tests needing a working encryption key is already supplied by `base.cfg`'s `[instance]` `environment-vars`.

## Next Phase Readiness

- QUAL-04 is closed: TOTAL branch coverage is 90.03% against the corrected instrument, `bin/test-coverage -t '!robot'` exits 0, and CI's `test_command` now runs that same command, so the threshold gates every push once this commit is pushed.
- **Carried to `/gsd-verify-work` per this plan's own `<verification>` note:** confirm the real GitHub Actions run actually invokes `bin/test-coverage` and fails the job if coverage regresses below 90 — this cannot be proven from the working tree alone.
- Plan 08-05 (the `bin/code-analysis` cleanup against the ~500-finding baseline) can now proceed on a coverage-gated, functionally-migrated suite (128 tests, 0 failures, 0 errors) with no blockers from this plan.

---
*Phase: 08-coverage-instrument-and-test-layers*
*Completed: 2026-08-05*

## Self-Check: PASSED
- FOUND: src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py
- FOUND: src/imio/googleauthenticator/tests/test_controlpanel.py
- FOUND: src/imio/googleauthenticator/tests/test_reset_bar_code.py
- FOUND: .github/workflows/package-test.yml
- FOUND: df830be (Task 1 commit)
- FOUND: 6f84f1e (Task 2 commit)
- FOUND: 6fdafab (Task 3 commit)
