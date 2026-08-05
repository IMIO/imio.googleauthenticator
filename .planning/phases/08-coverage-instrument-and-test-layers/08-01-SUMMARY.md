---
phase: 08-coverage-instrument-and-test-layers
plan: 01
subsystem: testing
tags: [coverage, buildout, coveragepy, ci-gate]

# Dependency graph
requires: []
provides:
  - "Corrected .coveragerc [run] scope (source/omit/branch), no [report] include"
  - "coverage == 5.5 pinned and buildout-installed; createcoverage part/pin/script removed"
  - "bin/test-coverage regenerated with set -e ahead of coverage html/report"
  - "Coverage-5.5 branch-coverage baseline recorded for plan 08-04"
affects: [08-02, 08-03, 08-04, 08-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Red-build proof by output contrast (TOTAL row present/absent), not exit code alone -- both a coverage-threshold failure and a set -e abort exit non-zero for different reasons"

key-files:
  created: []
  modified:
    - .coveragerc
    - base.cfg
    - test-4.3.cfg

key-decisions:
  - "Re-measured baseline under coverage 5.5 landed on the exact same TOTAL as the 4.2 reference (1048/131/286/60, 84%), not a shifted figure -- reported as-is per D-12, no .coveragerc adjustment made either way"
  - "Task 2's mutation and revert produced no commit; verified byte-identical via git diff on the touched test file specifically, since .planning/STATE.md carries a pre-existing unrelated orchestrator-init diff that predates this plan"

requirements-completed: [QUAL-01, QUAL-02, QUAL-03]

coverage:
  - id: D1
    description: ".coveragerc scoped to package code only, branch coverage on, no test modules in the denominator"
    requirement: "QUAL-01"
    verification:
      - kind: other
        ref: "bin/coverage report --rcfile=.coveragerc -m | head -1 -- contains Branch and BrPart columns; no /tests/ rows in the body"
        status: pass
    human_judgment: false
  - id: D2
    description: "set -e in the [test-coverage] template makes a failing test abort the script before coverage html/report run, proven by a real red build against a recorded control"
    requirement: "QUAL-02"
    verification:
      - kind: other
        ref: "bin/test-coverage -t '!robot' -- mutated run: exit 1, test failure, no TOTAL row, no fail-under message; control run: exit 2, TOTAL row + fail-under message"
        status: pass
    human_judgment: false
  - id: D3
    description: "coverage 5.5 pinned and installed via buildout; createcoverage part, pin and generated script all removed"
    requirement: "QUAL-03"
    verification:
      - kind: other
        ref: "bin/coverage --version reports 5.5; bin/test-coverage exists and is executable; bin/createcoverage does not exist; grep -rq createcoverage base.cfg test-4.3.cfg finds nothing"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-05
status: complete
---

# Phase 08 Plan 01: Coverage Instrument Repair Summary

**Corrected `.coveragerc` scope plus a `set -e` gate that actually fails, proven by a real red build, with the coverage-5.5 baseline re-measured at TOTAL 84% (1048 stmts / 131 missed, 286 branches / 60 partial) — unchanged from the pre-pin 4.2 reference.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-05T11:52:00Z
- **Completed:** 2026-08-05T11:59:54Z
- **Tasks:** 2 completed (Task 2 produces no commit by design)
- **Files modified:** 3 (`.coveragerc`, `base.cfg`, `test-4.3.cfg`)

## Accomplishments

- `.coveragerc` rewritten to a single `[run]` section (`source`, `omit`, `branch`), dropping the `[report] include` key that had been admitting the 14 test modules into the coverage denominator.
- `base.cfg`: `[coverage]`/`[test-coverage]` parts enabled in `parts +=`, `createcoverage` line deleted outright; `set -e` inserted as the first line of the `[test-coverage]` inline template, immediately after the shebang.
- `test-4.3.cfg`: `coverage = 5.5` pinned (replacing the commented 4.5.1 placeholder), `createcoverage = 1.5` pin deleted.
- `bin/buildout -c test-4.3.cfg` run with no network access needed — the `coverage-5.5-py2.7-linux-x86_64.egg` was already in `/srv/cache/eggs`. Regenerated `bin/coverage` from the `[coverage]` part, generated `bin/test-coverage`, removed `bin/createcoverage`. Buildout appended no new pins to `test-4.3.cfg` beyond the ones this plan made by hand.
- Re-measured baseline under coverage 5.5 recorded below (Task 1, step 7).
- Task 2: proved the `set -e` gate can actually fail with a real deliberately-failing test, contrasted against a recorded unmutated control, then reverted the mutation byte-identical.

## Task Commits

1. **Task 1: End-to-end coverage instrument — corrected scope, branch measurement, and a gate that can fail** - `352a612` (feat, `--no-verify` — see Deviations)
2. **Task 2: Prove the gate can actually fail — a real red build, then reverted byte-identical** - no commit (plan requires the mutation be introduced and removed within this task, tree ends byte-identical)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `.coveragerc` - `[run]` section: `source = src/imio/googleauthenticator`, `omit = */tests/*`, `branch = True`; `[report] include` key removed
- `base.cfg` - `coverage`/`test-coverage` uncommented into `parts +=`, `createcoverage` line deleted; `set -e` added to the `[test-coverage]` inline template
- `test-4.3.cfg` - `coverage = 5.5` pin added (replacing the commented placeholder), `createcoverage = 1.5` pin deleted
- `bin/coverage`, `bin/test-coverage` (buildout-generated, gitignored) - regenerated/created
- `bin/createcoverage` (buildout-generated, gitignored) - removed by buildout on uninstall of the old part

## Coverage-5.5 Baseline (D-12, for plan 08-04)

Measured with `bin/coverage run --rcfile=.coveragerc bin/test -t '!robot'` (111 tests, 0 failures, 0 errors) then `bin/coverage report --rcfile=.coveragerc -m`:

```
TOTAL: 1048 stmts, 131 missed, 286 branches, 60 partial, 84%
```

Identical to the pre-pin coverage-4.2 reference (1048/131/286/60, 84%) — the corrected instrument reproduces the known-good figure exactly rather than shifting it, confirming the `.coveragerc` rewrite changed scope correctness, not the underlying measured set.

Per-module `Missing` line lists for the four modules plan 08-04 consumes:

- `browser/disable_two_factor_authentication.py` — 18 stmts, 10 missed, 2 branches, 0 partial, 40%. Missing: `15-16, 22-40`
- `browser/disable_two_factor_authentication_for_all_users.py` — 16 stmts, 7 missed, 0 branches, 0 partial, 56%. Missing: `17-18, 24-32`
- `browser/controlpanel.py` — 72 stmts, 19 missed, 8 branches, 1 partial, 68%. Missing: `125-158, 162-163`
- `browser/forms/reset_bar_code.py` — 83 stmts, 16 missed, 22 branches, 9 partial, 76%. Missing: `76, 90-95, 103-109, 158-168, 173->exit, 192->215, 200->215, 202, 210`

## Task 2: Red-Build Proof

**Control run** (`bin/test-coverage -t '!robot'`, unmutated source): exit code `2`. Output tail:
```
TOTAL   1048    131    286     60    84%
Coverage failure: total of 84 is less than fail-under=90
```
Reaches `coverage html` and `coverage report`; a TOTAL row and the `--fail-under` threshold message are present.

**Mutated run** (`self.assertEqual(1, 2, 'deliberate mutation for 08-01 Task 2 red-build proof')` added inside `test_control_panel_view`, `bin/test-coverage -t '!robot'` re-run): exit code `1`. Output tail:
```
Failure in test test_control_panel_view (imio.googleauthenticator.tests.test_generic.TestGeneric)
...
AssertionError: 1 != 2 : deliberate mutation for 08-01 Task 2 red-build proof
...
Total: 111 tests, 1 failures, 0 errors in 58.026 seconds.
```
Contains the test failure; contains **no** TOTAL row and no `fail-under` message (confirmed with `grep -c` returning 0 for both strings). `set -e` aborted the script at the `bin/coverage run bin/test` line before `coverage html`/`coverage report` ever executed.

This is the contrast the plan requires: both runs exit non-zero, for different reasons — the discriminator is the output shape, not the exit code, and it is exactly the shape that distinguishes the fixed behaviour from the pre-fix bug (a failing test previously produced a clean exit 0).

The mutation was then removed. `git diff -- src/imio/googleauthenticator/tests/test_generic.py` is empty — the tree is byte-identical for that file. `bin/test -t '!robot'` was re-run afterward: 111 tests, 0 failures, 0 errors.

## Decisions Made

- Baseline landed on the identical TOTAL to the 4.2 reference rather than shifting by a point or two; recorded as measured, per D-12's instruction not to adjust `.coveragerc` to move the number either way.
- Task 2's byte-identical check was verified specifically against `src/imio/googleauthenticator/tests/test_generic.py` (the only file this task touched) rather than a blanket `git diff --quiet`, because `.planning/STATE.md` carries an unrelated pre-existing diff from the orchestrator's phase-init step that predates and is outside this plan's scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [CLAUDE.md-documented, expected] Task 1 commit required `--no-verify`**
- **Found during:** Task 1 commit
- **Issue:** The buildout-installed pre-commit hook runs `bin/code-analysis`, which fails on ~500 pre-existing isort/flake8 findings unrelated to this plan's three config files (documented in CLAUDE.md and this plan's own `<verification>` "Commit note"). The hook rejected the commit citing findings in `pas_plugin.py`, `subscribers.py`, `adapter.py`, `controlpanel.py`, etc. — none of which this plan touched.
- **Fix:** Re-ran the commit with `--no-verify`, exactly as the plan's verification section and this project's `<sequential_execution>` instructions anticipate for this specific, already-documented pre-existing-findings case.
- **Files modified:** none beyond the three already staged
- **Committed in:** `352a612`

---

**Total deviations:** 1 (expected, pre-authorized by plan/CLAUDE.md — not a Rule 1-4 auto-fix, no scope creep)
**Impact on plan:** None. All four config edits landed in the single planned commit as required.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The `coverage-5.5-py2.7-linux-x86_64.egg` was already present in the shared `/srv/cache/eggs` cache, so no network fetch was needed.

## Next Phase Readiness

- The coverage instrument is now trustworthy: `bin/test-coverage`'s exit code means something, and `.coveragerc` measures only package code with branch coverage on.
- Plan 08-04 has its consumable baseline: the four per-module `Missing` line lists above, plus the TOTAL figures.
- No blockers for plan 08-02/08-03 (test-layer migration work), which can now build on a coverage signal that will not silently pass a red suite.

---
*Phase: 08-coverage-instrument-and-test-layers*
*Completed: 2026-08-05*

## Self-Check: PASSED
- FOUND: .planning/phases/08-coverage-instrument-and-test-layers/08-01-SUMMARY.md
- FOUND: 352a612 (Task 1 commit)
