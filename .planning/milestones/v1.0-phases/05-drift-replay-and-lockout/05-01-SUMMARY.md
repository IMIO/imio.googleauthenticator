---
phase: 05-drift-replay-and-lockout
plan: 01
subsystem: auth
tags: [plone, pas-plugin, totp, lockout, memberdata, z3c.form, zope.schema]

# Dependency graph
requires:
  - phase: 04-pas-boundary
    provides: write-free PAS plugin/challenge boundary (MFA-12's standing R-04-C constraint), the token form's existing handleSubmit shape
provides:
  - Three int memberdata properties (two_factor_authentication_failed_attempts, two_factor_authentication_locked_until, two_factor_authentication_last_interval) declared in userdataschema.py and memberdata_properties.xml
  - max_failed_attempts (default 5) / lockout_duration (default 900) control-panel settings on IGoogleAuthenticatorSettings
  - helpers.is_account_locked / register_failed_second_factor / reset_failed_second_factor
  - Lock gate wired into browser/forms/token.py::TokenForm.handleSubmit, evaluated before validate_user_data/validate_token
  - tests/test_token.py (new) with TestTokenFormLockout covering MFA-08/09/11/12
affects: [05-02-drift-and-replay, 05-03-reset-bar-code-lockout, 08-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lockout state lives in three int memberdata properties written only from browser/forms/token.py, never pas_plugin.py/subscribers.py (MFA-12), enforced by a source-grep regression test"
    - "Counter increment and lock epoch always travel in a single setMemberProperties() call so both land or neither does"
    - "Locked accounts get the exact same generic message as a wrong code, so the response cannot be used as an oracle"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_token.py
  modified:
    - src/imio/googleauthenticator/userdataschema.py
    - src/imio/googleauthenticator/profiles/default/memberdata_properties.xml
    - src/imio/googleauthenticator/browser/controlpanel.py
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/browser/forms/token.py
    - src/imio/googleauthenticator/tests/test_helpers.py
    - src/imio/googleauthenticator/tests/test_setuphandlers.py
    - src/imio/googleauthenticator/tests/test_generic.py
    - src/imio/googleauthenticator/tests/test_pas_plugin.py
    - .planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md

key-decisions:
  - "Decision P5-06 followed as planned: new test module named tests/test_token.py, not test_token_form.py, matching the skill's R5 file-to-module rule and this package's own precedent (test_user_setup.py, test_request_bar_code_reset.py)"
  - "Decision P5-05 followed as planned: setting the lock also zeroes the attempt counter in the same write, so a cleared lock starts the user with a fresh N attempts"

patterns-established:
  - "Pattern: two_factor_authentication_last_interval is declared and round-trip-tested in this plan but not yet read/written by any helper -- plan 05-02 is the first consumer"
  - "Pattern: non-vacuity mutation checks for security-relevant tests are performed by hand (mutate, run, confirm red, restore byte-identical, re-run green) and recorded in the plan summary rather than left as an unexercised claim"

requirements-completed: [MFA-08, MFA-09, MFA-10, MFA-11, MFA-12, MFA-13]

coverage:
  - id: D1
    description: "Five consecutive wrong codes at @@google-authenticator-token lock the account for the configured duration; the fourth does not"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "tests/test_token.py#test_lockout_after_five_failures"
        status: pass
    human_judgment: false
  - id: D2
    description: "A locked account is not an oracle: a correct code and an incorrect code are refused identically, and the correct code succeeds once the lock is cleared"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "tests/test_token.py#test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code"
        status: pass
    human_judgment: false
  - id: D3
    description: "The lock releases itself at the epoch it names, with no administrator action, and the is_account_locked boundary holds in both directions"
    requirement: "MFA-09"
    verification:
      - kind: integration
        ref: "tests/test_token.py#test_lockout_expires_without_admin_action"
        status: pass
    human_judgment: false
  - id: D4
    description: "max_failed_attempts and lockout_duration are editable control-panel settings with defaults 5 and 900, readable through get_app_settings() after install"
    requirement: "MFA-10"
    verification:
      - kind: integration
        ref: "tests/test_generic.py#test_control_panel_has_lockout_fields"
        status: pass
    human_judgment: true
    rationale: "Automated test covers schema presence/defaults/registry readback only; actual form rendering and persistence through the real Plone control panel needs a running instance (test_robot.py is excluded everywhere) -- listed as a manual-only verification in 05-VALIDATION.md"
  - id: D5
    description: "A successful second factor clears both the counter and the lock, and a fresh wrong code afterwards reads back 1, not 5"
    requirement: "MFA-11"
    verification:
      - kind: integration
        ref: "tests/test_token.py#test_successful_second_factor_resets_failed_attempts"
        status: pass
    human_judgment: false
  - id: D6
    description: "No second-factor state is written from the PAS plugin or the challenge plugin, and the failure counter survives a request sequence that begins in Unauthorized"
    requirement: "MFA-12"
    verification:
      - kind: integration
        ref: "tests/test_token.py#test_failed_attempt_counter_survives_unauthorized_request"
        status: pass
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_no_second_factor_state_written_from_the_plugin"
        status: pass
      - kind: integration
        ref: "bin/test -t test_challenge -t test_pas_plugin"
        status: pass
    human_judgment: false
  - id: D7
    description: "The three new memberdata properties are declared in the Python schema and the profile XML, round-trip as Python ints, and are confirmed by the profile import that ships"
    requirement: "MFA-13"
    verification:
      - kind: integration
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_new_memberdata_properties_round_trip"
        status: pass
      - kind: integration
        ref: "tests/test_setuphandlers.py#test_memberdata_properties_import_declares_expected_types"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-07-31
status: complete
---

# Phase 5 Plan 1: Lockout Substrate and Gate Summary

**Three int memberdata properties, two control-panel settings, and a pre-token lock gate wired into TokenForm.handleSubmit, with all five writes proven to happen only from a committing view (not the PAS plugin) via a source-grep regression test.**

## Performance

- **Duration:** 16 min (17:15 -> 17:31, commit timestamps)
- **Started:** 2026-07-31T17:15:00+02:00
- **Completed:** 2026-07-31T17:31:03+02:00
- **Tasks:** 3
- **Files modified:** 10 (1 created)

## Accomplishments
- `two_factor_authentication_failed_attempts`, `two_factor_authentication_locked_until` and `two_factor_authentication_last_interval` declared as `Int` fields on `IEnhancedUserDataSchema` (and omitted from the personal-preferences panel), plus matching `type="int"` entries in `memberdata_properties.xml` -- proven by both a direct round-trip test and a profile-import test against `portal_memberdata`'s own property-map API.
- `max_failed_attempts` (default 5, min 1) and `lockout_duration` (default 900, min 1) added to `IGoogleAuthenticatorSettings` with zero new form class and zero `registry.xml` edit.
- `helpers.is_account_locked` / `register_failed_second_factor` / `reset_failed_second_factor` added with no `except` anywhere, every value `int()`-coerced before the write, and the counter+lock always written in a single `setMemberProperties()` call.
- The lock is evaluated in `TokenForm.handleSubmit` before `validate_user_data`/`validate_token` are ever consulted, reusing the existing `"Invalid token or token expired."` message verbatim -- a locked account cannot be used as an oracle to confirm a guessed code.
- `tests/test_token.py` (new): five test methods proving the lock threshold (4th fails to lock, 5th locks), the oracle-safety property, the self-expiring epoch (boundary asserted in both directions against `is_account_locked`), the success-resets-the-counter behaviour, and counter survival across a real two-request `Browser` sequence that begins in `Unauthorized`.
- `tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin`: source-greps `pas_plugin.py`/`subscribers.py` for all three property names and all three helper function names, with positive controls proving the search itself works.

## Task Commits

Each task was committed atomically:

1. **Task 1: Five wrong codes lock the account -- one path, wired through every layer** - `bb528fe` (feat)
2. **Task 2: Prove the declarations actually took effect -- round trip, profile import, control-panel fields** - `4993047` (test)
3. **Task 3: The lock is not an oracle, expires by itself, resets on success, and survives Unauthorized** - `bd8a195` (test)

_No TDD tasks in this plan; each task was a single commit._

## Files Created/Modified
- `src/imio/googleauthenticator/userdataschema.py` - Three new `Int` fields + omit-list entries + docstring
- `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` - Three new `type="int"` property entries
- `src/imio/googleauthenticator/browser/controlpanel.py` - `max_failed_attempts` / `lockout_duration` fields + fieldset
- `src/imio/googleauthenticator/helpers.py` - `is_account_locked`, `register_failed_second_factor`, `reset_failed_second_factor`
- `src/imio/googleauthenticator/browser/forms/token.py` - Lock gate wired into `handleSubmit`
- `src/imio/googleauthenticator/tests/test_token.py` - New; `TestTokenFormLockout`, 5 test methods
- `src/imio/googleauthenticator/tests/test_helpers.py` - New `TestDriftAndReplay` class + round-trip test
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - Profile-import type-declaration test
- `src/imio/googleauthenticator/tests/test_generic.py` - Control-panel lockout-field test
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` - MFA-12 plugin-boundary source-grep test
- `.planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md` - Rows filled (Plan/Wave/Threat Ref/Status), `test_token_form.py` references replaced with `test_token.py`

## Decisions Made
- P5-05 and P5-06 followed exactly as the plan specified (see `key-decisions` in frontmatter above).
- Placed the three new `helpers.py` functions immediately after `validate_token` (not specified precisely by the plan) since they are thematically adjacent and both consulted from the same call site in `token.py`.

## Deviations from Plan

### Auto-fixed Issues

None - all three tasks executed within the plan's design. No Rule 1/2/3 auto-fixes were needed; the plan's own read-first excerpts and pattern map were accurate against the current source.

### Clarifications (not deviations, but worth recording)

**1. Non-vacuity mutation for the MFA-08 oracle test used a different mechanic than the literal plan wording.**
- **Found during:** Task 3, non-vacuity check for `test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code`.
- **Issue:** The plan's acceptance criterion says "moving the lock check in `token.py` to *after* the `validate_token` call turns [the test] red." A literal move -- relocating the `is_account_locked` check to just after `valid_token = validate_token(...)` but still *before* the `if valid_token:` dispatch -- is behaviourally identical to the original (still intercepts before either branch runs), so it does **not** turn the test red.
- **Resolution:** The actual mutation applied removed the up-front gate and left `is_account_locked` called (but its result discarded) only inside the `else` (wrong-code) branch, so a *correct* code while locked was no longer refused. This reproduces the real vulnerability class the test protects against (the lock stops gating login once the check is no longer strictly prior to the success/failure dispatch) and turned the test red as required (`AssertionError: '@@google-authenticator-token' not found in 'http://nohost/plone'`). Restored byte-identical afterwards.
- **Files affected:** `src/imio/googleauthenticator/browser/forms/token.py` (mutated and restored, not part of the final commit).
- **Verification:** `bin/test -t test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code` went red under the mutation, green after restore; full suite re-run green (76 tests).

---

**Total deviations:** 0 auto-fixed. 1 clarification recorded above (methodology note on how a non-vacuity check was satisfied, not a change in scope or behaviour).
**Impact on plan:** None on delivered scope. The clarification only concerns how the required non-vacuity proof was constructed.

## Issues Encountered
- `Location` header from `PluggableAuthService.challenge()`'s `response.redirect(signed_url, lock=1)` is relative to the portal root, not absolute -- `test_failed_attempt_counter_survives_unauthorized_request`'s second request had to resolve it against `self.portal_url` before a fresh `Browser` (which has no current document) could `.open()` it. Test-only fix, no production code touched.
- `plone.supermodel`'s `fieldset(...)` tagged-value key is `plone.supermodel.fieldsets` (via `FIELDSETS_KEY`), not `plone.autoform.fieldsets` as initially assumed while writing `test_control_panel_has_lockout_fields`; confirmed by reading `/srv/cache/eggs/plone.supermodel-1.2.7-py2.7-linux-x86_64.egg/plone/supermodel/directives.py` (the egg this buildout's own `bin/test` actually resolves, distinct from a same-named egg elsewhere on the machine) before writing the assertion.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 05-02 (drift/replay) can build directly on `two_factor_authentication_last_interval`, which is declared and round-trip-proven here but has no reader/writer yet.
- Plan 05-03 (reset-bar-code lockout) reuses `is_account_locked`/`register_failed_second_factor`/`reset_failed_second_factor` from `helpers.py` unchanged; `browser/forms/reset_bar_code.py` is untouched by this plan.
- `bin/test -t '!robot'` is green at 76 tests (up from the 66 recorded at phase seed time), with Phase 4's `test_challenge`/`test_pas_plugin` baseline (19 tests) still passing unmodified.
- No blockers.

---
*Phase: 05-drift-replay-and-lockout*
*Completed: 2026-07-31*

## Self-Check: PASSED

All 12 created/modified files confirmed present on disk; all 3 task commit
hashes (`bb528fe`, `4993047`, `bd8a195`) confirmed in `git log`.
