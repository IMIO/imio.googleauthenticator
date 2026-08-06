---
phase: 10-global-enforcement-and-enrollment
plan: 04
subsystem: auth
tags: [pas-plugin, plone, actions.xml, portal-actions, memberdata]

requires:
  - phase: 10-global-enforcement-and-enrollment
    provides: "two_factor_authentication_enrolled property + has_completed_enrollment accessor (plan 10-01)"
provides:
  - "browser/settings_helper.py's three link conditions corrected to match their own docstrings (D-10, D-11) and a new fourth method for the regenerate action (D-15)"
  - "profiles/default/actions.xml's regenerate_recovery_codes action decoupled from the disable link's condition, with its own SettingsHelper-backed available_expr"
  - "tests/test_settings_helper.py -- Wave 0 gap 1 closed, zero-to-100%-statement coverage on browser/settings_helper.py"
affects: [10-05, 10-06]

tech-stack:
  added: []
  patterns:
    - "Deliberate deviation from a research recommendation recorded as an in-source comment on the exact line a future reader would 'simplify' back (D-10's has_completed_enrollment vs has_enabled_two_factor_authentication)"
    - "portal_actions.listActionInfos(object=self.portal) used to resolve which actions actually render, not just which booleans are True -- catches a correct predicate wired to the wrong available_expr"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_settings_helper.py
  modified:
    - src/imio/googleauthenticator/browser/settings_helper.py
    - src/imio/googleauthenticator/browser/configure.zcml
    - src/imio/googleauthenticator/profiles/default/actions.xml
    - src/imio/googleauthenticator/tests/test_generic.py

key-decisions:
  - "Followed the plan's deliberate override of RESEARCH.md's recommended shape: show_enable_two_factor_authentication_link is keyed on has_completed_enrollment, not has_enabled_two_factor_authentication -- the latter would hide the enable link from every install-enrolled account under D-01."
  - "test_generic.py's pre-existing test_regenerate_recovery_codes_action_is_registered asserted the old (soon-to-be-wrong) available_expr; updated in the same commit as the actions.xml change rather than left to break, since it directly encodes the D-15 regression this plan closes."
  - "Fixture writes go through api.user.get_current(), not a separately fetched api.user.get(username=...) object -- the two are different MemberData wrappers within one request; a write through the latter was invisible through the former until a transaction boundary this test layer never crosses. Found via the disable-link non-vacuity debugging, not stated in the plan."
  - "Folded coverage of SettingsHelper's pre-existing (untouched by this plan) is_two_factor_authentication_globally_enabled passthrough method into the existing MFA-18 test rather than adding a 7th test method, to hit the plan's 100%-statement-coverage acceptance criterion for the file without violating its 6-methods count."

patterns-established:
  - "A test matrix that resolves actual rendered portal actions (listActionInfos), not just the booleans feeding available_expr, is the only way to catch a correct predicate wired to the wrong view."

requirements-completed: [MFA-17, MFA-18]

duration: ~1h
completed: 2026-08-06
status: complete
---

# Phase 10 Plan 04: Enable/Disable/Regenerate Link Conditions Summary

**Corrected two inverted `settings_helper.py` conditions to match their own docstrings (D-10, D-11), added a fourth `show_regenerate_recovery_codes_link` method so "Regenerate recovery codes" survives global enforcement (D-15), and closed Wave 0's first test gap with a new `tests/test_settings_helper.py` covering the MFA-18 four-case matrix as a matrix.**

## Performance

- **Duration:** ~1h
- **Tasks:** 3 completed
- **Files modified:** 4 (3 named in the plan's frontmatter, plus `tests/test_generic.py` -- see Deviations)

## Accomplishments

- `show_enable_two_factor_authentication_link` now returns `not has_completed_enrollment(user)`
  with no global-setting term at all (D-10/MFA-17/MFA-18) -- the deliberate deviation from
  RESEARCH.md's recommended `not has_enabled_two_factor_authentication` shape, recorded in-source
  as a comment explaining why that shape would hide enrollment from every install-enrolled
  account under D-01.
- `show_disable_two_factor_authentication_link` now returns
  `has_enabled_two_factor_authentication(user) and not is_two_factor_authentication_globally_enabled()`
  (D-11/MFA-16) -- the mirror inversion, with an in-source comment that this condition is
  cosmetic, not the control (plan 10-03's refusal is).
- New `show_regenerate_recovery_codes_link` (D-15), registered in `configure.zcml` as
  `show-regenerate-recovery-codes-link`, keyed on `has_completed_enrollment` with no
  global-setting term.
- `profiles/default/actions.xml`'s `regenerate_recovery_codes` action now points its
  `available_expr` at the new view instead of reusing the disable link's condition; the comment
  block above it rewritten to describe the current code rather than the reuse it no longer does.
- `src/imio/googleauthenticator/tests/test_settings_helper.py` created from scratch: 6 test
  methods, 100% statement coverage on `browser/settings_helper.py` (was 0%), including the
  MFA-18 success-criterion-5 matrix resolved via `portal_actions.listActionInfos()` rather than
  the three booleans alone.

## Task Commits

Each task was committed atomically:

1. **Task 1: Correct both link conditions and add the regenerate condition** - `a148811` (fix)
2. **Task 2: Give the regenerate action its own condition, and fix the comment that explained the old reuse** - `5466ec4` (fix)
3. **Task 3: Create tests/test_settings_helper.py from scratch, carrying the four-case matrix** - `81c04a8` (test)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `src/imio/googleauthenticator/browser/settings_helper.py` - two corrected conditions, one new
  method, in-source comments recording D-09/D-10/D-11/D-15 reasoning
- `src/imio/googleauthenticator/browser/configure.zcml` - new `show-regenerate-recovery-codes-link`
  registration
- `src/imio/googleauthenticator/profiles/default/actions.xml` - `regenerate_recovery_codes`'s
  `available_expr` repointed, comment block rewritten
- `src/imio/googleauthenticator/tests/test_generic.py` - `test_regenerate_recovery_codes_action_is_registered`
  updated to assert the new condition (deviation, see below)
- `src/imio/googleauthenticator/tests/test_settings_helper.py` - new, `TestSettingsHelper`, 6
  methods

## Decisions Made

See `key-decisions` in frontmatter. In particular: fixture writes in the new test module go
through `api.user.get_current()` rather than a separately fetched `api.user.get(username=...)`
object, because the two are different `MemberData` wrappers within the same request and a write
through the latter was not visible through the former -- discovered while debugging the first
non-vacuity run of the disable-link test (see Issues Encountered).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_generic.py`'s pre-existing action-registration test asserted the condition this plan removes**
- **Found during:** Task 2, first `bin/test -t test_generic -t test_setuphandlers` run after
  rewiring `actions.xml`.
- **Issue:** `test_regenerate_recovery_codes_action_is_registered` asserted
  `'show-disable-two-factor-authentication-link' in action.available_expr` -- exactly the
  reuse D-15 requires undoing. Left as-is it would fail the moment `actions.xml` changed, for the
  correct reason but as an unplanned break, not a signal of a new defect.
- **Fix:** Updated the assertion to check for `show-regenerate-recovery-codes-link` instead, with
  a docstring paragraph recording why (D-15, this plan).
- **Files modified:** `src/imio/googleauthenticator/tests/test_generic.py`
- **Verification:** `bin/test -t test_generic -t test_setuphandlers` green (43/43).
- **Committed in:** `5466ec4`

**2. [Rule 1 - Bug] XML comments cannot contain `--`**
- **Found during:** Task 2, first attempt at the rewritten `actions.xml` comment block.
- **Issue:** The rewritten comment used `--` as a prose separator (an em-dash convention used
  elsewhere in this codebase's Python comments); inside an XML comment this produced
  `ExpatError: not well-formed (invalid token)` at layer setup, since `--` is forbidden anywhere
  inside `<!-- -->` except its closing delimiter.
- **Fix:** Replaced both occurrences with plain punctuation (colon, comma).
- **Files modified:** `src/imio/googleauthenticator/profiles/default/actions.xml`
- **Verification:** `bin/test -t test_generic -t test_setuphandlers` green.
- **Committed in:** `5466ec4`

**3. [Rule 1 - Bug] New test module's fixture helper wrote through the wrong MemberData wrapper**
- **Found during:** Task 3, first run of `test_disable_link_is_offered_only_when_enrolled_and_globally_disabled`.
- **Issue:** `_set_state` originally wrote properties via `api.user.get(username=TEST_USER_NAME)`,
  then `_conditions()` read them via `SettingsHelper`'s internal `api.user.get_current()` call.
  These are two distinct `MemberData` object instances within the same request; a property write
  through one was not visible through a read via the other until a transaction boundary this test
  layer's fixture never crosses between setup and assertion. Confirmed by debug prints: the same
  property read `True` via the fetched object and `False` via `get_current()`.
- **Fix:** `_set_state` now writes through `api.user.get_current()`, matching the object
  `SettingsHelper` itself reads from.
- **Files modified:** `src/imio/googleauthenticator/tests/test_settings_helper.py`
- **Verification:** all 6 methods green afterward; see Non-vacuity section below.
- **Committed in:** `81c04a8`

**4. [Rule 2 - Missing coverage] `SettingsHelper`'s pre-existing `is_two_factor_authentication_globally_enabled` passthrough had zero coverage**
- **Found during:** Task 3, first `bin/test-coverage` run: `browser/settings_helper.py` at 97%,
  missing line 24 (that one pre-existing method, untouched by this plan, registered separately
  as the `is-two-factor-authentication-globally-enabled` view).
- **Issue:** The plan's own acceptance criteria demand 100% statement coverage on the file. This
  method predates the plan and isn't named in its artifact list, but it lives in the same file
  and the criterion is file-scoped.
- **Fix:** Folded two assertions calling it directly into the existing
  `test_enable_link_is_offered_whatever_the_global_setting_says` method (which already toggles
  `globally_enabled` on and off), rather than adding a 7th test method that would break the
  plan's `grep -cE '    def test_' ... returns 6` acceptance check.
- **Files modified:** `src/imio/googleauthenticator/tests/test_settings_helper.py`
- **Verification:** `bin/test-coverage -t '!robot'` -- `browser/settings_helper.py` at 100%.
- **Committed in:** `81c04a8`

---

**Total deviations:** 4 auto-fixed (2 Rule 1 bugs surfaced by the plan's own required change, 1
Rule 1 bug in the new test's own fixture, 1 Rule 2 coverage completion).
**Impact on plan:** None widen scope beyond what the plan's own acceptance criteria already
required (`bin/test -t test_generic` green, 100% statement coverage on the touched file). No
production behaviour changed beyond what tasks 1-2 specify.

## Issues Encountered

- The `MemberData`-wrapper hazard (deviation #3) took the most investigation: property writes
  and reads that "should" be on the same user object silently diverged within one request. Debug
  prints comparing `api.user.get(username=...)` against `api.user.get_current()` side by side
  were what isolated it; the SUMMARY for plan 10-01 documents an adjacent but distinct hazard
  (process-wide mutable schema state), not this one.

## User Setup Required

None - no external service configuration required.

## Non-vacuity checks (mandatory, project convention since Phase 1)

All six test methods were proven to go red against a mutated version of the production code they
guard, then the mutated files were restored byte-identical (`git diff --stat` confirmed clean
after each restore).

**1. `test_enable_link_is_offered_to_a_user_who_has_not_completed_enrollment` /
`test_enable_link_is_offered_whatever_the_global_setting_says`** -- reverted
`show_enable_two_factor_authentication_link` to the pre-task-1 shape
(`is_two_factor_authentication_globally_enabled() and not has_enabled_two_factor_authentication(user)`).
Real failure output:
```
AssertionError: False is not True : D-10: the enable link must be offered to an install-enrolled user who has not completed enrollment.
...
AssertionError: False is not True : MFA-18: offered with the setting off.
```

**2. `test_disable_link_is_offered_only_when_enrolled_and_globally_disabled`** -- reverted
`show_disable_two_factor_authentication_link` to the pre-task-1 shape (removed the `not`). Real
failure output:
```
AssertionError: False is not True : globally_enabled off, flag set: must be offered.
```

**3. `test_regenerate_link_survives_global_enforcement`** -- mutated
`show_regenerate_recovery_codes_link` to the regression shape D-15 exists to prevent
(`has_enabled_two_factor_authentication(user) and not is_two_factor_authentication_globally_enabled()`,
the disable link's own condition). Real failure output:
```
AssertionError: False is not True : D-15: "Regenerate recovery codes" must survive global enforcement.
```

**4. `test_every_settings_combination_leaves_enrollment_reachable`** -- two separate mutations,
each restored before the next:
- Reverted `show_enable_two_factor_authentication_link` to the pre-task-1 shape (same as check 1).
  Real failure output:
  ```
  AssertionError: False is not True : MFA-18 criterion 5: globally_enabled=True, enrolled=False must offer at least one route to enrollment.
  ```
- With `settings_helper.py` untouched, reverted only `actions.xml`'s `regenerate_recovery_codes`
  `available_expr` back to `portal/@@show-disable-two-factor-authentication-link` (the D-15
  regression). Real failure output:
  ```
  AssertionError: [] is not True : globally_enabled=True, enrolled=True: no visible "user" action resolves to @@setup-two-factor-authentication -- a correct predicate pointed at the wrong view would still fail here (D-15).
  ```
  Note on scope: the loop's `assertTrue` raises on the first failing combination it hits, so this
  run stopped at the `(globally_enabled=True, enrolled=True)` cell rather than separately proving
  both enrollment-completed cells in one run. Working through the algebra by hand: with
  `enabled=True` fixed (as the loop does), the `(globally_enabled=False, enrolled=True)` cell's
  reused `available_expr` happens to evaluate `True` anyway under this specific mutation (the
  disable link's own D-11-corrected condition is coincidentally also `True` there), so it would
  *not* independently fail this particular mutation -- the test still correctly catches the
  regression via the other cell, which is what matters for non-vacuity, but this is recorded
  honestly rather than claimed as "both cells proven independently."

**5. `test_all_three_conditions_are_false_for_anonymous`** -- removed the anonymous guard from
`show_enable_two_factor_authentication_link`. Real failure output:
```
AssertionError: True is not False : anonymous: enable link must be False.
```

All five mutations restored byte-identical afterward; `git diff --stat` confirmed clean after
every restore (verified inline during execution, not merely asserted here).

## Next Phase Readiness

- All three `settings_helper.py` conditions now match their own docstrings, and the regenerate
  action has a stable, independent condition. Plans 10-05/10-06 can build on
  `show_regenerate_recovery_codes_link` without re-deriving it.
- **Open per the plan's own flagged assumptions (EDGE-MFA-17-unclassified,
  EDGE-MFA-18-unclassified), not a gap this plan introduces:** if a later reviewer determines
  MFA-17's "from their own profile" or MFA-18's "reachable" was meant to include the
  `@@personal-information` schema-field surface (Phase 9/BUG-08 emptied its description) or an
  anonymous/non-site-local-account path, this phase's `settings_helper`/`actions.xml` work does
  not cover those surfaces and would need revisiting.

## Known Stubs

None.

## Threat Flags

None beyond what the plan's own `<threat_model>` already names and mitigates (T-10-16 through
T-10-19 addressed as planned; T-10-SC not applicable, no package installs in this plan).

## Verification Evidence

- `bin/test -t test_settings_helper -t test_generic -t test_setuphandlers` -> **49 tests, 0
  failures, 0 errors**.
- `bin/test -t '!robot'` -> **161 tests, 0 failures, 0 errors** (up from the 155-test baseline).
- `bin/test-coverage -t '!robot'` -> **91% branch coverage** overall (above the 90% bar);
  `browser/settings_helper.py` at **100% statement coverage** (was 0% before this plan; missed
  line 24 closed by deviation #4).
- `bin/code-analysis` -> exits 0 (Flake8 OK), confirmed after every task commit.
- Acceptance-criteria greps, all confirmed:
  - `grep -cE '^\s+def show_(enable|disable|regenerate)' settings_helper.py` -> `3`
  - `grep -c 'has_completed_enrollment' settings_helper.py` -> `3`
  - `grep -c 'show-regenerate-recovery-codes-link' configure.zcml` -> `1`
  - `grep -c 'name="available_expr">portal/@@show-regenerate-recovery-codes-link' actions.xml` -> `1`
  - `grep -c 'name="available_expr">portal/@@show-disable-two-factor-authentication-link' actions.xml` -> `1`
  - `grep -c 'name="available_expr"' actions.xml` -> `3`
  - `grep -cE '    def test_' tests/test_settings_helper.py` -> `6`

## Self-Check: PASSED

All 5 modified/created source files and this SUMMARY.md confirmed present on disk via direct
filesystem check; all three task commit hashes (`a148811`, `5466ec4`, `81c04a8`) confirmed
present in `git log --oneline --all`.

---
*Phase: 10-global-enforcement-and-enrollment*
*Completed: 2026-08-06*
