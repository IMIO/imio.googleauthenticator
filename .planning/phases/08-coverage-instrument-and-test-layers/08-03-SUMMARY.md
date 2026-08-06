---
phase: 08-coverage-instrument-and-test-layers
plan: 03
subsystem: testing
tags: [plone.testing, plone.app.testing, PAS, test-isolation, DemoStorage]

# Dependency graph
requires:
  - phase: 08-02
    provides: "ImiogoogleauthenticatorLayer.setUpPloneSite install hook and a ZSERVER-free IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING layer to migrate every test class onto"
provides:
  - "Every test class in src/imio/googleauthenticator/tests/ (12 files, 16 class attributes) runs on IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING"
  - "IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING and the IntegrationTesting import deleted from testing.py -- the leaking layer cannot be silently reintroduced"
  - "Per-test DemoStorage isolation confirmed to reveal zero pre-existing failures -- the suite was already correct, not merely appearing so"
  - "Post-layer-change branch-coverage baseline for plan 08-04: TOTAL 1048/131/286/61, 84%"
affects: [08-04, 08-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mechanical layer-attribute rename kept in its own commit, separate from any fix commit, so either is independently revertible (plan's own Task 1/Task 2 split)"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/testing.py
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/tests/test_adapter.py
    - src/imio/googleauthenticator/tests/test_challenge.py
    - src/imio/googleauthenticator/tests/test_controlpanel.py
    - src/imio/googleauthenticator/tests/test_generic.py
    - src/imio/googleauthenticator/tests/test_helpers.py
    - src/imio/googleauthenticator/tests/test_pas_plugin.py
    - src/imio/googleauthenticator/tests/test_request_bar_code_reset.py
    - src/imio/googleauthenticator/tests/test_reset_bar_code.py
    - src/imio/googleauthenticator/tests/test_security.py
    - src/imio/googleauthenticator/tests/test_setuphandlers.py
    - src/imio/googleauthenticator/tests/test_token.py
    - src/imio/googleauthenticator/tests/test_user_setup.py

key-decisions:
  - "Task 1's own automated verify (`! grep -rq 'IntegrationTesting' src/imio/googleauthenticator/ --include='*.py'`) would have failed on a stale comment in helpers.py:1103 naming 'the IntegrationTesting test browser' -- reworded to 'the functional-testing test browser' in the same commit as the mechanical rename, since it is a direct consequence of this task's own deletion (same class of fix as 08-02's three stale-comment rewordings), not a new task."
  - "Task 1 produced zero failures on the first run (111 tests, 0 failures, 0 errors), re-run twice for stability -- so Task 2 made no code or test changes. This is the plan's own explicitly anticipated valid outcome ('If Task 1 produced no failures at all, make no changes and record that outcome explicitly... it means the leak was masking nothing'), not a shortcut around the fix step."
  - "No commit was made for Task 2, matching 08-01's precedent for a no-op verification task -- there is nothing to commit when no file changed."

requirements-completed: []
requirements-partial:
  - id: QUAL-05
    note: "Second half complete: every test class now runs on IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING and the integration layer is retired. Marking REQUIREMENTS.md complete via requirements mark-complete in this plan's state-update step."

coverage:
  - id: D1
    description: "All 12 test files' layer attributes (16 total) moved from IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING to IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING; the integration layer definition and its IntegrationTesting import deleted from testing.py"
    requirement: "QUAL-05"
    verification:
      - kind: other
        ref: "grep -rq IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING / IntegrationTesting src/imio/googleauthenticator/ --include='*.py' -- both find nothing; grep -rl 'layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING' -- exactly 12 files, 16 attributes total"
        status: pass
    human_judgment: false
  - id: D2
    description: "bin/test -t '!robot' green on the new per-test-DemoStorage layer with zero failures revealed by the isolation change"
    requirement: "QUAL-05"
    verification:
      - kind: other
        ref: "bin/test -t '!robot' run twice for stability -- both runs: Total: 111 tests, 0 failures, 0 errors"
        status: pass
    human_judgment: false
  - id: D3
    description: "Post-layer-change branch-coverage TOTAL recorded for plan 08-04"
    requirement: "QUAL-05"
    verification:
      - kind: other
        ref: "bin/coverage run --rcfile=.coveragerc bin/test -t '!robot' then bin/coverage report --rcfile=.coveragerc -m -- TOTAL 1048 stmts, 131 missed, 286 branches, 61 partial, 84%"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-08-05
status: complete
---

# Phase 08 Plan 03: Test-Layer Migration to FunctionalTesting Summary

**Moved every test class (12 files, 16 attributes) from the leaking `IntegrationTesting` layer to the ZSERVER-free `FunctionalTesting` layer, deleted the integration layer definition entirely, and confirmed the per-test `DemoStorage` isolation revealed zero pre-existing test failures -- the suite was 111/0/0 both before and after, proving the prior leak was masking nothing.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-05T12:00:00Z (approx)
- **Completed:** 2026-08-05T12:22:10Z
- **Tasks:** 2 completed (Task 2 produces no commit -- no failures to fix)
- **Files modified:** 14 (`testing.py`, `helpers.py`, 12 test files)

## Accomplishments

- All 16 `layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` class attributes across 12 test files renamed to `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`, along with the matching import line in each file (`test_generic.py` and 10 others use a two-line backslash-continued import; `test_controlpanel.py` uses a single-line import -- both forms handled by the same string substitution since the identifier itself, not the line layout, changed).
- `testing.py`: deleted the `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING = IntegrationTesting(...)` module-level definition and the now-unused `from plone.app.testing import IntegrationTesting` line. `FunctionalTesting`, `PLONE_FIXTURE`, `PloneSandboxLayer`, `applyProfile`, the robot fixture import, and `z2` all kept. `ZSERVER_FIXTURE` still appears exactly once outside comments (the robot layer's own `bases`).
- 14-versus-12 file reconciliation: `test_robot.py` uses `IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING` (excluded from every run via the `!robot` tag) and `test_subscribers.py` declares no layer at all (its handler touches no Zope state). Neither was touched.
- Full suite run on the new layer, twice for stability: `bin/test -t '!robot'` -- **111 tests, 0 failures, 0 errors** both times. The isolation change (per-test `stackDemoStorage` at `testSetUp`, closed at `testTearDown`, discarding every committed write) revealed **no** failures -- the six-plus test files that commit inside test bodies (`test_challenge`, `test_token`, `test_reset_bar_code`, `test_helpers`, `test_pas_plugin`, `test_setuphandlers`) were not, in fact, relying on cross-test leaked state to pass.
- Post-layer-change coverage baseline measured for plan 08-04: `bin/coverage run --rcfile=.coveragerc bin/test -t '!robot'` then `bin/coverage report --rcfile=.coveragerc -m` -- **TOTAL 1048 stmts, 131 missed, 286 branches, 61 partial, 84%**. One `BrPart` point higher than plan 08-01's pre-layer-change baseline (1048/131/286/**60**, 84%) -- the same statement/branch counts, one additional partially-covered branch, consistent with the install mechanism now running once per layer instead of per test class touching slightly different branch paths in `setuphandlers`/profile application. TOTAL percentage unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: Move every test class to the functional layer and retire the integration layer** - `4c6be92` (feat, `--no-verify` -- see Deviations)
2. **Task 2: Fix every failure the isolation change revealed** - no commit (Task 1 revealed zero failures; nothing to fix, nothing to commit -- matches 08-01 Task 2's precedent for a no-op verification task)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `src/imio/googleauthenticator/testing.py` - `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` definition and `IntegrationTesting` import deleted
- `src/imio/googleauthenticator/helpers.py` - one stale comment reworded (see Deviations)
- `src/imio/googleauthenticator/tests/test_adapter.py` - 3 occurrences (1 import, 2 layer attributes) renamed
- `src/imio/googleauthenticator/tests/test_challenge.py` - 2 occurrences (1 import, 1 layer attribute) renamed
- `src/imio/googleauthenticator/tests/test_controlpanel.py` - 2 occurrences (1 import, 1 layer attribute) renamed
- `src/imio/googleauthenticator/tests/test_generic.py` - 2 occurrences (1 import, 1 layer attribute) renamed
- `src/imio/googleauthenticator/tests/test_helpers.py` - 5 occurrences (1 import, 4 layer attributes across 4 classes) renamed
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` - 2 occurrences renamed
- `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py` - 2 occurrences renamed
- `src/imio/googleauthenticator/tests/test_reset_bar_code.py` - 2 occurrences renamed
- `src/imio/googleauthenticator/tests/test_security.py` - 2 occurrences renamed
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - 2 occurrences renamed
- `src/imio/googleauthenticator/tests/test_token.py` - 2 occurrences renamed
- `src/imio/googleauthenticator/tests/test_user_setup.py` - 2 occurrences renamed

## Decisions Made

- **Task 1's failure list is empty.** Per the plan's own instruction, this is stated explicitly rather than left as an absence: the first run on the new layer (`bin/test -t '!robot'`) reported 111 tests, 0 failures, 0 errors, and a second run confirmed the same result. No test id, assertion, or traceback to record. This means Task 2's classification-and-fix work has nothing to act on.
- **helpers.py comment fix folded into Task 1's commit, not treated as a Task 2 fix.** `helpers.py:1103`'s comment named `IntegrationTesting` explaining a `REMOTE_ADDR`-missing edge case. Task 1's own automated `<verify>` requires no `IntegrationTesting` string survive anywhere under `src/imio/googleauthenticator/` -- this comment would have failed that gate. Reworded to "the functional-testing test browser" (same referent, updated name), landed in the same commit as the mechanical rename since it is a direct, mechanical consequence of deleting the identifier this task deletes, not a revealed defect.
- **Coverage TOTAL's BrPart moved 60 -> 61** (same Stmts/Miss/Branch, same 84%) between plan 08-01's baseline and this plan's post-layer-change measurement. Recorded as observed, not investigated further -- plan 08-04 is the consumer of this figure and works from per-module `Missing` line detail, not the single-point BrPart delta.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, direct consequence of this task's own deletion] Reworded a stale `IntegrationTesting` comment in `helpers.py`**
- **Found during:** Task 1 (running the plan's own verify grep before committing)
- **Issue:** `helpers.py:1103` had a comment reading "No REMOTE_ADDR (seen with the IntegrationTesting test browser, and ...)". The plan's own Task 1 acceptance criterion and automated verify require `grep -rq 'IntegrationTesting' src/imio/googleauthenticator/ --include='*.py'` to find nothing anywhere under `src/`, and this comment is a substring match that would have failed that gate even though `helpers.py` is not in the plan's `<files>` list.
- **Fix:** Reworded to "seen with the functional-testing test browser" -- same referent (a test browser producing no `REMOTE_ADDR`), no logic change, no identifier left dangling.
- **Files modified:** `src/imio/googleauthenticator/helpers.py`
- **Committed in:** `4c6be92` (Task 1 commit)

**2. [CLAUDE.md-documented, expected] Task 1 commit required `--no-verify`**
- **Found during:** Task 1 commit
- **Issue:** The buildout-installed pre-commit hook runs `bin/code-analysis`, which fails on pre-existing isort/flake8 findings unrelated to this plan's files, documented in CLAUDE.md and this plan's own `<verification>` "Commit note": "commits in this plan need `git commit --no-verify` -- the pre-commit hook stays red until plan 08-05".
- **Fix:** Committed with `--no-verify`, exactly as anticipated.
- **Files modified:** none beyond those already staged
- **Committed in:** `4c6be92`

---

**Total deviations:** 2 (1 direct Rule-3-style cleanup forced by this task's own gate, 1 expected/pre-authorized `--no-verify`)
**Impact on plan:** None on scope. Neither deviation touched code outside what the mechanical rename itself required.

## Issues Encountered

None -- the isolation change revealed no pre-existing defects. Every test file that commits inside a test body (the six-plus named in the plan's objective) turned out to already be correct without relying on cross-test leaked state.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QUAL-05 is now fully closed: `setUpPloneSite` applies the profile once per layer (08-02), and every test class runs on the ZSERVER-free, per-test-isolated `FunctionalTesting` layer with the leaking `IntegrationTesting` layer deleted outright (08-03).
- Plan 08-04 has its consumable post-layer-change coverage baseline: TOTAL 1048/131/286/61, 84%, with the per-module `Missing` line detail unchanged in shape from plan 08-01's figures (re-run above, same command).
- No blockers for plan 08-04 (branch-coverage work) or plan 08-05 (the `bin/code-analysis` cleanup, which still needs `--no-verify` until it lands).

---
*Phase: 08-coverage-instrument-and-test-layers*
*Completed: 2026-08-05*

## Self-Check: PASSED
- FOUND: .planning/phases/08-coverage-instrument-and-test-layers/08-03-SUMMARY.md
- FOUND: 4c6be92 (Task 1 commit)
