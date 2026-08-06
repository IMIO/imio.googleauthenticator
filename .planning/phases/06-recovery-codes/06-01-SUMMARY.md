---
phase: 06-recovery-codes
plan: 01
subsystem: auth
tags: [pbkdf2, totp, memberdata, plone-pas, python2]

# Dependency graph
requires:
  - phase: 05-drift-replay-and-lockout
    provides: validate_token, is_account_locked, register_failed_second_factor, reset_failed_second_factor -- the lockout substrate this phase's recovery-code path reuses with no new counter
provides:
  - Two new memberdata properties (two_factor_authentication_recovery_codes_salt, _hashes) storing one PBKDF2-HMAC-SHA256 salt and a tuple of hex hashes per user, never the plaintext
  - helpers.generate_recovery_codes / validate_recovery_code / validate_second_factor -- mint, validate-and-consume, and the promoted dispatcher
  - The single second-factor dispatch point in browser/forms/token.py now accepts a TOTP code or a recovery code through one call
affects: [06-02-enrollment-display, 06-03-lockout-sharing-and-low-count-warning, 08-code-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Promoted dispatcher over add-alongside branch: validate_second_factor is the sole caller-facing API; validate_token stays byte-identical as the demoted TOTP variant handler (this plan's assumption_delta_decision)."
    - "Consume-by-index, never by equality filter: validate_recovery_code removes the matched entry via stored[:i] + stored[i+1:] so a birthday-collision duplicate hash cannot burn two codes on one use."
    - "One salt per user (a `string` property), never per code (would need a `lines` property) -- keeps one submitted code at exactly one pbkdf2_hmac call regardless of stored hash count."

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/profiles/default/memberdata_properties.xml
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/browser/forms/token.py
    - src/imio/googleauthenticator/tests/test_token.py
    - src/imio/googleauthenticator/tests/test_helpers.py
    - src/imio/googleauthenticator/tests/test_adapter.py

key-decisions:
  - "Task 1 checkpoint:decision (resolved by the orchestrator before this executor was spawned): option-a -- RECOVERY_CODE_PBKDF2_ITERATIONS = 100000, salt as a 32-character hex string, hashes as a `lines` tuple of 64-character hex strings. One-way: rehashing requires the unrecoverable plaintext codes, so this could only ever be changed by forcing every enrolled user to regenerate, invalidating every printed code in circulation."
  - "validate_second_factor (not RESEARCH.md's proposed validate_token_or_recovery_code) is the promoted dispatcher name, per this plan's assumption_delta_decision: the primary noun is 'second factor', not 'token', so the generalized name is free to choose before any caller exists."
  - "Neither new property is declared on IEnhancedUserDataSchema -- memberdata-only, matching the Phase 5 lockout-counter decision, and proven by extending the existing LOCKOUT_STATE_PROPERTIES guard rather than writing a parallel test."

patterns-established:
  - "Pattern: A future second-factor kind is added by a new _is_<kind>_shape/validate_<kind> pair plus one more branch in validate_second_factor -- never a new if/elif inside validate_token or a second call site in token.py."

requirements-completed: [RECOV-02, RECOV-04]

coverage:
  - id: D1
    description: "A 16-character base32 recovery code authenticates at @@google-authenticator-token through a real Browser POST exactly as a TOTP code does, is consumed on use, and a replay is refused."
    requirement: "RECOV-04"
    verification:
      - kind: integration
        ref: "tests/test_token.py#TestTokenFormLockout.test_recovery_code_is_accepted_in_place_of_a_token_and_consumed"
        status: pass
    human_judgment: false
  - id: D2
    description: "One salt per user, ten hashes, plaintext codes absent from both stored property values; every RECOV-01 shape/empty-state refusal edge returns False rather than raising."
    requirement: "RECOV-02"
    verification:
      - kind: integration
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_recovery_code_storage_and_validation_edges"
        status: pass
    human_judgment: false
  - id: D3
    description: "Neither new property reaches @@user-information or becomes form-writable -- extended the existing memberdata-only guard rather than adding a parallel test, and the guard was reproduced red before being trusted."
    verification:
      - kind: integration
        ref: "tests/test_adapter.py#TestEnhancedUserDataPanelAdapter.test_lockout_state_is_memberdata_only_and_never_a_form_field"
        status: pass
    human_judgment: false

duration: ~45min
completed: 2026-08-03
status: complete
---

# Phase 6 Plan 1: Recovery-Code Substrate Summary

**A 16-character base32 recovery code, PBKDF2-HMAC-SHA256-hashed under one per-user salt, authenticates through the existing token form exactly like a TOTP code, is consumed on use, and never touches the plaintext after generation.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3 (Task 1 resolved by decision before this executor ran; Tasks 2-3 implemented)
- **Files modified:** 6

## Accomplishments
- Two new memberdata properties (`two_factor_authentication_recovery_codes_salt`, `_hashes`) declared, memberdata-only, round-trip-proven with their declared types.
- `helpers.py` gained `generate_recovery_codes`, `validate_recovery_code`, `validate_second_factor` and three private primitives (`_normalize_recovery_code_input`, `_is_recovery_code_shape`, `_hash_recovery_code`), plus six `RECOVERY_CODE_*` constants including `RECOVERY_CODE_PBKDF2_ITERATIONS = 100000`.
- `browser/forms/token.py`'s single second-factor dispatch point now calls `validate_second_factor` instead of `validate_token` directly -- a one-line right-hand-side swap; `validate_token` itself is byte-identical.
- End-to-end Browser test proves accept, consume (10 -> 9 hashes), replay-refused, a second code still works (9 -> 8), TOTP still works unchanged, four shape refusals, and a cross-user code refused.
- Storage-contract test proves the MFA-13 round trip for both new properties (including the empty-tuple case), plaintext absence from both stored values, one-salt/ten-hash counts, every RECOV-01 refusal edge (empty, one-char, 17-char, forbidden-digit, no-salt user, empty-hashes user), `unicode`/`str` equivalence, non-ASCII refusal, and validating the last entry in the stored tuple.
- `test_adapter.py`'s `LOCKOUT_STATE_PROPERTIES` guard extended to cover both new properties, so the existing schema-absence test protects them without a parallel test.

## Task Commits

1. **Task 1: Settle the two one-way decisions** -- resolved by the orchestrator before this executor was spawned (option-a: 100,000 iterations, hex-string salt, `lines`-tuple hashes). No commit of its own; recorded in STATE.md.
2. **Task 2: End-to-end "log in with a recovery code"** -- `429a873` (feat)
3. **Task 3: Pin the storage contract** -- `f6d74e5` (test)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` - two new `<property>` entries, `string` and `lines`
- `src/imio/googleauthenticator/helpers.py` - `pbkdf2_hmac`/`binascii` imports, six `RECOVERY_CODE_*` constants, six new functions
- `src/imio/googleauthenticator/browser/forms/token.py` - import and dispatch-line swap to `validate_second_factor`
- `src/imio/googleauthenticator/tests/test_token.py` - one end-to-end method, `tearDown` extended
- `src/imio/googleauthenticator/tests/test_helpers.py` - one storage/validation-edges method on `TestDriftAndReplay`
- `src/imio/googleauthenticator/tests/test_adapter.py` - `LOCKOUT_STATE_PROPERTIES` extended with the two new property names

## Decisions Made
- Task 1's checkpoint:decision: **option-a** -- `RECOVERY_CODE_PBKDF2_ITERATIONS = 100000`; salt stored as a 32-character hex string; hashes stored as a `lines` tuple of 64-character hex strings. Measured at 0.117s on this buildout's Python 2.7.18 interpreter this session. One-way: rehashing later requires the plaintext codes, which are deliberately unrecoverable, so the only migration path is forcing every enrolled user to regenerate, invalidating every printed code in circulation. Recorded in STATE.md.
- `validate_second_factor` (not RESEARCH.md's `validate_token_or_recovery_code`) is the promoted dispatcher name -- see the plan's `assumption_delta_decision`: the primary noun is "second factor", and the promote costs nothing since the dispatcher did not exist yet.

## Deviations from Plan

None - plan executed exactly as written. Both non-vacuity mutation checks Task 3 required were run and reproduced red before the source was restored byte-identical:

- Removing the `two_factor_authentication_recovery_codes_salt` `<property>` line from `memberdata_properties.xml` made `bin/test -t test_helpers` fail with `ValueError: The property two_factor_authentication_recovery_codes_salt does not exist` (1 error). Restored; `git diff --stat` on the file is empty.
- Adding `two_factor_authentication_recovery_codes_salt` as a `TextLine` field on `IEnhancedUserDataSchema` made `bin/test -t test_adapter` fail 2 of 3 tests (`test_every_field_this_package_adds_is_readable_from_the_adapter` and `test_lockout_state_is_memberdata_only_and_never_a_form_field`). Restored; `git diff --stat` on `userdataschema.py` is empty.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `helpers.validate_second_factor` is now the sole second-factor validator `token.py` calls, ready for plan 06-03 to wire `RECOV-05`'s shared-lockout-counter proof (no new call site needed) and the low-recovery-code-count warning.
- `generate_recovery_codes(user)` returns the plaintext list and is ready for plan 06-02 to wire enrollment display (`SetupForm.issued_recovery_codes`, `recovery_codes.pt`, the `regenerate_recovery_codes` action) -- nothing in this plan renders the codes anywhere.
- `RECOVERY_CODE_PBKDF2_ITERATIONS` is the single source for the iteration count; no call site inlines the literal.
- `bin/test -t '!robot'` is green at 92 tests (up from 84 pre-phase), with every Phase 5 `TestDriftAndReplay` method unmodified.

---
*Phase: 06-recovery-codes*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 6 modified/created source files and this SUMMARY.md exist on disk; both task commits (`429a873`, `f6d74e5`) confirmed present in `git log`.
