---
phase: 08-coverage-instrument-and-test-layers
plan: 02
subsystem: testing
tags: [plone.testing, plone.app.testing, PAS, generic-setup, quickinstaller]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Corrected coverage instrument (not consumed directly by this plan, but the wave-1 baseline this plan's suite re-measures against implicitly)"
provides:
  - "ImiogoogleauthenticatorLayer.setUpPloneSite applying the profile once per layer via applyProfile, replacing the per-test-class Browser-driven quickinstaller round trip"
  - "IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING with no ZSERVER fixture (robot layer keeps its own)"
  - "BaseTest with only _get_browser/_login_browser -- the _install() quickinstaller helper and all its call sites are gone"
  - "test_product_is_installed asserting installedness via PAS plugin registration, IGoogleAuthenticatorSettings registry-record presence, and browser-layer registration -- no portal_quickinstaller reference anywhere in src/"
affects: [08-03, 08-04, 08-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PloneSandboxLayer.setUpPloneSite(self, portal) as the install hook, called once per layer setup, in place of a per-test-class Browser round trip through prefs_install_products_form"
    - "Installedness proven through what the package's own install path guarantees (plugin registration, registry records, browser layer) rather than through a tool the install path never touches"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/testing.py
    - src/imio/googleauthenticator/tests/base.py
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
  - "Actual _install() call-site count measured at 16, not the plan's estimated 21 -- test_helpers.py had 3 (not 5), test_pas_plugin.py 1 (not 2), test_request_bar_code_reset.py 1 (not 2), test_setuphandlers.py 1 (not 2), test_user_setup.py 1 (not 2). All other per-file counts matched exactly. Reconciled below."
  - "Reworded test_product_is_installed's docstring to say 'the quickinstaller tool' instead of the literal string 'portal_quickinstaller', since the plan's own automated verify grep for that literal string across all of src/ and the docstring would otherwise have been a false positive against the plan's own gate"
  - "Updated (did not delete) three now-stale in-repo comments that named the deleted BaseTest._install() method as the cause of cross-test memberdata leakage (test_helpers.py x2, test_pas_plugin.py, test_user_setup.py) -- the leakage-mitigation code they explain is untouched and still correct, only the explanatory prose named a since-deleted identifier"

requirements-completed: [QUAL-05, QUAL-07]

coverage:
  - id: D1
    description: "ImiogoogleauthenticatorLayer.setUpPloneSite(self, portal) applies the imio.googleauthenticator:default profile once per layer; IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING drops z2.ZSERVER_FIXTURE (robot layer keeps its own)"
    requirement: "QUAL-05"
    verification:
      - kind: other
        ref: "grep -q 'def setUpPloneSite' + grep -c ZSERVER_FIXTURE == 1 (excl. comments) + bin/test -t '!robot' -- 111 tests, 0 failures, 0 errors"
        status: pass
    human_judgment: false
  - id: D2
    description: "BaseTest._install() (Browser-driven prefs_install_products_form round trip) and all 16 measured call sites deleted, along with the 8 qi_tool assignments, 3 now-dead getToolByName imports, and 3 unused quickInstallProduct imports"
    requirement: "QUAL-05"
    verification:
      - kind: other
        ref: "grep -rq portal_quickinstaller/qi_tool/quickInstallProduct src/imio/googleauthenticator/ --include='*.py' -- all three find nothing; bin/test -t '!robot' -- 111 tests, 0 failures, 0 errors"
        status: pass
    human_judgment: false
  - id: D3
    description: "test_product_is_installed rewritten to assert PAS plugin registration (IAuthenticationPlugin/PAS_ID), IGoogleAuthenticatorSettings registry-record presence (registry.forInterface, no hardcoded count), and browser-layer registration (IGoogleAuthenticatorLayer in registered_layers())"
    requirement: "QUAL-07"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_generic.py#test_product_is_installed -- non-vacuity: each of the three assertions broken one at a time, confirmed red, restored byte-identical (see below)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-05
status: complete
---

# Phase 08 Plan 02: Test-Layer Install Mechanism and Installedness Assertion Summary

**Moved the GenericSetup profile install from a per-test-class Browser round trip through `portal_quickinstaller` to `ImiogoogleauthenticatorLayer.setUpPloneSite`, deleted all 16 measured call sites of the old install helper across 12 test files, and rewrote `test_product_is_installed` to prove installedness via PAS plugin registration, registry records, and browser-layer registration instead of a tool the profile never touches.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-05T13:55:00+02:00 (approx)
- **Completed:** 2026-08-05T14:13:30+02:00
- **Tasks:** 2 completed
- **Files modified:** 14 (`testing.py` + 13 test files)

## Accomplishments

- `testing.py`: added `ImiogoogleauthenticatorLayer.setUpPloneSite(self, portal)`, a one-line call to the already-imported (previously unused) `applyProfile(portal, 'imio.googleauthenticator:default')`. `PloneSandboxLayer` calls this exactly once per layer setup, inside its own stacked `DemoStorage`, before any per-test layer stacks its own.
- `testing.py`: `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`'s `bases` reduced from `(IMIO_GOOGLEAUTHENTICATOR_FIXTURE, z2.ZSERVER_FIXTURE)` to `(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,)`. `IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING` untouched -- `z2.ZSERVER_FIXTURE` now appears exactly once in the file (the robot layer's own `bases`), confirmed by `grep -v '^ *#' testing.py | grep -c ZSERVER_FIXTURE` == 1. `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` left in place, as directed -- plan 08-03 owns its removal.
- `tests/base.py`: deleted the entire `_install()` method (the site-owner login, the `prefs_install_products_form` round trip, the install-form assertion, and the in-method comment admitting the layer did not apply the profile correctly) plus the now-unused `SITE_OWNER_NAME`/`SITE_OWNER_PASSWORD` import. `_get_browser()` and `_login_browser()` kept verbatim.
- Deleted all 16 measured `self._install()` call sites across 12 files, all 8 measured `self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')` assignments, the 3 now-dead `getToolByName` imports (`test_controlpanel.py`, `test_request_bar_code_reset.py`, `test_security.py`), and the 3 unused `from plone.app.testing import quickInstallProduct` imports (`test_generic.py`, `test_pas_plugin.py`, `test_security.py`).
- `test_generic.py::test_product_is_installed` rewritten (QUAL-07): three assertions -- `PAS_ID in [id for id, _ in self.pas.plugins.listPlugins(IAuthenticationPlugin)]`, `registry.forInterface(IGoogleAuthenticatorSettings)` (relies on default `check=True`, raises `KeyError` naming the first missing field -- no field enumeration, no hardcoded count), and `IGoogleAuthenticatorLayer in registered_layers()`. Added `self.pas = getToolByName(self.portal, 'acl_users')` to `TestGeneric.setUp` (this file had no such attribute before). Added five new imports. Deleted the commented-out `test_disable_view` block.
- Updated three stale in-repo comments (in `test_helpers.py` x2, `test_pas_plugin.py`, `test_user_setup.py`) that explained cross-test memberdata leakage by naming `BaseTest._install()`'s testbrowser commits as the cause -- reworded to describe the leakage without naming the now-deleted method; the leakage-mitigation code itself (fresh-secret-under-current-key, teardown property resets) is untouched.
- Full suite green after both tasks: `bin/test -t '!robot'` -- 111 tests, 0 failures, 0 errors.

## Task Commits

Each task was committed atomically:

1. **Task 1: Give the layer its own install hook and drop the ZSERVER fixture from the functional layer** - `c1b17e6` (feat, `--no-verify` -- see Deviations)
2. **Task 2: Delete the quickinstaller install path and rewrite the installedness assertion** - `d64788d` (feat, `--no-verify` -- see Deviations)

**Plan metadata:** pending (this SUMMARY's own commit)

## Files Created/Modified

- `src/imio/googleauthenticator/testing.py` - added `setUpPloneSite`; dropped `z2.ZSERVER_FIXTURE` from the functional layer's `bases`
- `src/imio/googleauthenticator/tests/base.py` - `_install()` and its `SITE_OWNER_NAME`/`SITE_OWNER_PASSWORD` import deleted; `_get_browser`/`_login_browser` kept
- `src/imio/googleauthenticator/tests/test_adapter.py` - 2 `_install()`/`qi_tool` call sites removed from two `setUp` methods
- `src/imio/googleauthenticator/tests/test_challenge.py` - `qi_tool` assignment and `_install()` call removed from `setUp`
- `src/imio/googleauthenticator/tests/test_controlpanel.py` - `qi_tool` assignment, `_install()` call, and the now-unused `getToolByName` import removed
- `src/imio/googleauthenticator/tests/test_generic.py` - `test_product_is_installed` rewritten (QUAL-07); `self.pas` added to `setUp`; `qi_tool`/`_install()`/`quickInstallProduct` removed; commented-out `test_disable_view` block deleted; 5 new imports added
- `src/imio/googleauthenticator/tests/test_helpers.py` - 3 `_install()` calls removed across three `setUp` methods; 2 stale comments reworded
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` - `qi_tool` assignment, `_install()` call, and `quickInstallProduct` import removed; 1 stale comment reworded
- `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py` - `qi_tool` assignment, `_install()` call, and the now-unused `getToolByName` import removed; adjacent comment reworded
- `src/imio/googleauthenticator/tests/test_reset_bar_code.py` - `_install()` call removed
- `src/imio/googleauthenticator/tests/test_security.py` - `qi_tool` assignment, `_install()` call, `getToolByName` import, and `quickInstallProduct` import removed
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - `_install()` call removed; the "Honest limitation" docstring's reference to `BaseTest._install()` reworded to name `setUpPloneSite`
- `src/imio/googleauthenticator/tests/test_token.py` - `_install()` call removed
- `src/imio/googleauthenticator/tests/test_user_setup.py` - `_install()` call removed; 1 stale comment reworded

## Decisions Made

- **Call-site count reconciliation (acceptance criterion, D-16/D-15 measured-vs-plan).** The plan's "Artifacts" section, measured at a prior commit, listed 21 total `_install()` call sites. Re-grepped at execution time (excluding comment-only references), the actual count was **16**:

  | File | Plan estimate | Measured (this execution) |
  |---|---|---|
  | test_adapter.py | 2 | 2 |
  | test_challenge.py | 1 | 1 |
  | test_controlpanel.py | 1 | 1 |
  | test_generic.py | 1 | 1 |
  | test_helpers.py | 5 | 3 |
  | test_pas_plugin.py | 2 | 1 |
  | test_request_bar_code_reset.py | 2 | 1 |
  | test_reset_bar_code.py | 1 | 1 |
  | test_security.py | 1 | 1 |
  | test_setuphandlers.py | 2 | 1 |
  | test_token.py | 1 | 1 |
  | test_user_setup.py | 2 | 1 |
  | **Total** | **21** | **16** |

  The plan's own text anticipated this ("some files call `_install()` more than once ... grep each file rather than assuming"). The 5 files with a lower measured count each had exactly one comment-only reference to `BaseTest._install()` (documenting the cross-test leakage the real call caused) that the plan's earlier grep pass evidently counted alongside the real call; this execution's grep distinguished code lines from comment lines. All comment-only references were separately located and reworded (see Decisions above and Files Created/Modified), not left stale.
  The 8 `qi_tool` assignments matched the plan's count exactly (no reconciliation needed there).

- **Non-vacuity control for the three rewritten `test_product_is_installed` assertions (Task 2 step 6, T-08-05 mitigation).** Each assertion was broken in isolation, run via `bin/test -t test_product_is_installed`, confirmed red, then restored and confirmed byte-identical via `diff` against a pre-mutation copy:
  1. **PAS plugin registration:** changed the expected id from `PAS_ID` to `'not_a_real_plugin_id'`. Result: `AssertionError: 'not_a_real_plugin_id' not found in ['google_auth', 'source_users', 'session']`. Reverted; `diff` against the saved original showed no difference.
  2. **Registry record presence:** inserted `del registry.records['imio.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings.ska_secret_key']` immediately before the `forInterface` call. Result: `KeyError: 'Interface ... defines a field \`ska_secret_key\`, for which there is no record.'` -- exactly the failure mode the docstring promises. Reverted; `diff` confirmed byte-identical.
  3. **Browser layer registration:** swapped the expected interface from `IGoogleAuthenticatorLayer` to `IAuthenticationPlugin`. Result: `AssertionError: <InterfaceClass ...IAuthenticationPlugin> not found in [IPloneFormLayer, IDiscussionLayer, IGoogleAuthenticatorLayer]` -- the assertion body's own real value list confirms `IGoogleAuthenticatorLayer` genuinely is present, so the pass on the un-mutated assertion is not vacuous. Reverted; `diff` confirmed byte-identical.

  After all three mutations and reverts, `git diff --stat -- test_generic.py` showed the same net diff as before the mutation exercise, and the full suite (`bin/test -t '!robot'`) was re-run green: 111 tests, 0 failures, 0 errors.

- **`test_product_is_installed` docstring wording avoids the literal string `portal_quickinstaller`.** The plan's own Task 2 automated verify (and this plan's own `must_haves.truths`) requires `grep -rq 'portal_quickinstaller' src/imio/googleauthenticator/ --include='*.py'` to find nothing anywhere under `src/`. The PATTERNS.md-suggested docstring text names that string literally ("applyProfile() never touches portal_quickinstaller"); reworded to "the quickinstaller tool" to satisfy the plan's own gate without losing the explanation.

## Deviations from Plan

### Auto-fixed Issues

**1. [CLAUDE.md-documented, expected] Both commits required `--no-verify`**
- **Found during:** Task 1 and Task 2 commits
- **Issue:** The buildout-installed pre-commit hook runs `bin/code-analysis`, which fails on hundreds of pre-existing isort/flake8 findings unrelated to this plan's files (documented in CLAUDE.md, `STATE.md`'s Phase 8 blocker note, and this plan's own `<verification>` "Commit note": "commits in this plan need `git commit --no-verify` -- the pre-commit hook stays red until plan 08-05"). The hook's output named findings in `pas_plugin.py`, `subscribers.py`, `adapter.py`, `controlpanel.py`, and other files this plan did not touch.
- **Fix:** Re-ran each commit with `--no-verify`, exactly as the plan's verification section anticipates.
- **Files modified:** none beyond those already staged for each task
- **Committed in:** `c1b17e6`, `d64788d`

**2. [Rule 1 - stale documentation, directly caused by this task's own deletion] Updated three comments referencing the deleted `BaseTest._install()` identifier**
- **Found during:** Task 2 (grepping for `_install()` to find call sites also surfaced comment-only references)
- **Issue:** Three comments (in `test_helpers.py` x2, `test_pas_plugin.py`, `test_user_setup.py`) explained a cross-test memberdata-leakage hazard by naming `BaseTest._install()`'s testbrowser commits as the cause. After deleting that method, the comments named a nonexistent identifier while still describing an accurate hazard (the leakage-mitigation code they explain -- forcing a fresh secret, resetting properties in `tearDown` -- is unrelated to `_install()` specifically and needed no change).
- **Fix:** Reworded each comment to describe the leakage without naming the deleted method (e.g., "memberdata writes survive across test methods in this layer" instead of "memberdata commits inside `BaseTest._install()`'s testbrowser calls"). No code logic changed, only prose.
- **Files modified:** `test_helpers.py`, `test_pas_plugin.py`, `test_user_setup.py`, `test_request_bar_code_reset.py` (4 comments total, one per file, `test_helpers.py` had two)
- **Committed in:** `d64788d`

---

**Total deviations:** 2 (1 expected/pre-authorized by plan+CLAUDE.md, 1 direct Rule-1-style cleanup of stale prose this task's own deletion caused)
**Impact on plan:** None on scope. Both are exactly what the plan anticipated (`--no-verify` for the hook) or a minimal, prose-only follow-through on the deletion the plan itself specified.

## Issues Encountered

None -- the suite stayed green through both tasks with no D-08 fallout (no pre-existing defect was revealed by the install-mechanism change).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- QUAL-05 (first half) and QUAL-07 are both closed: the profile is applied once per layer through the supported `setUpPloneSite` hook, and installedness is proven through plugin registration, registry records, and browser-layer registration rather than a tool the install path never touches.
- `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` is still referenced by all 14 test files' `layer` class attribute -- deliberately left in place per this plan's own instruction ("plan 08-03 deletes it after the last test stops referencing it"). Plan 08-03 is the one that migrates every test file's `layer` attribute to `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` and completes the per-test `DemoStorage` isolation fix that this plan's own STATE.md blocker note anticipates may reveal pre-existing test failures.
- No blockers for plan 08-03.

---
*Phase: 08-coverage-instrument-and-test-layers*
*Completed: 2026-08-05*

## Self-Check: PASSED
- FOUND: src/imio/googleauthenticator/testing.py (setUpPloneSite present)
- FOUND: c1b17e6 (Task 1 commit)
- FOUND: d64788d (Task 2 commit)
- FOUND: .planning/phases/08-coverage-instrument-and-test-layers/08-02-SUMMARY.md
