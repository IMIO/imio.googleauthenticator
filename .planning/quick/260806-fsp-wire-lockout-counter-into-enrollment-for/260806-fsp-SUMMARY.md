---
phase: quick-260806-fsp
plan: 01
subsystem: auth
tags: [totp, lockout, pas-plugin, plone, python2]

requires:
  - phase: 05-lockout-and-drift
    provides: is_account_locked/register_failed_second_factor/reset_failed_second_factor shared counter, already wired into token.py and reset_bar_code.py
provides:
  - SetupForm.handleSubmit (browser/forms/user_setup.py) now checks the lock before validate_token, registers a failed attempt on a wrong code, and clears the counter on success -- the third and last of the three validate_token callers to share the counter
affects: [06-recovery-codes, 08-security-review]

tech-stack:
  added: []
  patterns:
    - "Lock-gate-before-validate three-arm dispatch (is_account_locked / validate_token / else), reused verbatim from reset_bar_code.py/token.py"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/forms/user_setup.py
    - src/imio/googleauthenticator/tests/test_user_setup.py
    - CHANGES.rst

key-decisions:
  - "Locked arm reaches the shared \"if reason is not None:\" tail (same message, same redirect target as a wrong code) instead of an early return, deliberately deviating from reset_bar_code.py's early-return shape -- see Deviations section below."
  - "user = api.user.get_current() hoisted above the three-arm dispatch and passed explicitly to validate_token(token, user=user), rather than relying on validate_token's internal fallback, so the lock check, the validation call and both counter calls share one user object."

requirements-completed: [MFA-08, MFA-11, MFA-12]

coverage:
  - id: D1
    description: "Locked account with a correct code is refused; no enrolment, no fresh recovery-code set"
    requirement: "MFA-08"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_user_setup.py::TestSetupForm::test_handleSubmit_refuses_a_locked_account_even_with_a_correct_code"
        status: pass
    human_judgment: false
  - id: D2
    description: "One wrong code at the setup form increments the shared failed-attempts counter"
    requirement: "MFA-08"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_user_setup.py::TestSetupForm::test_handleSubmit_wrong_code_increments_the_failed_attempts_counter"
        status: pass
    human_judgment: false
  - id: D3
    description: "A correct code at the setup form clears the shared failed-attempts counter"
    requirement: "MFA-11"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_user_setup.py::TestSetupForm::test_handleSubmit_correct_code_clears_the_failed_attempts_counter"
        status: pass
    human_judgment: false
  - id: D4
    description: "Reaching max_failed_attempts consecutive wrong codes at the setup form locks the account, bounded by lockout_duration"
    requirement: "MFA-08"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_user_setup.py::TestSetupForm::test_handleSubmit_reaching_max_failed_attempts_locks_the_account"
        status: pass
    human_judgment: false
  - id: D5
    description: "All second-factor state writes on this path happen inside the committing form view (MFA-12), never in pas_plugin.py or a subscriber"
    requirement: "MFA-12"
    verification:
      - kind: other
        ref: "grep -n is_account_locked / register_failed_second_factor / reset_failed_second_factor confined to browser/forms/user_setup.py; existing test_no_second_factor_state_written_from_the_plugin (test_pas_plugin.py) unaffected and still green"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-06
status: complete
---

# Phase quick-260806-fsp: Wire lockout counter into enrollment form Summary

**`SetupForm.handleSubmit` now checks `is_account_locked` before `validate_token`, calls `register_failed_second_factor`/`reset_failed_second_factor` around it, and reaches the same failure tail as a wrong code when locked -- closing 06-REVIEW.md CR-01 (CRITICAL), the last of three `validate_token` callers with no lockout wiring.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3/3 completed
- **Files modified:** 3 (`user_setup.py`, `test_user_setup.py`, `CHANGES.rst`)

## Accomplishments

- Closed 06-REVIEW.md CR-01 (CRITICAL) / v1.0-MILESTONE-AUDIT.md Gap 1: `@@setup-two-factor-authentication` (enrollment, and its reuse as the "Regenerate recovery codes" action) is now metered by the same shared lockout counter `token.py` and `reset_bar_code.py` already use, so an attacker with a session that skipped the second factor (hijacked cookie, or `ip_addresses_whitelist`) can no longer brute-force six-digit TOTP guesses without limit to mint a fresh recovery-code set.
- Added four tests to the existing `TestSetupForm` class (not a second class), proven RED against the unmodified source first, then proven load-bearing by mutation in Task 3.
- Kept the RECOV-03 one-time recovery-code display mechanism (the `redirect_url = None` / `if reason is not None:` fallback) byte-identical -- only the dispatch feeding into it changed.

## Task 1: RED evidence (proven against unmodified `user_setup.py`)

`bin/test -t '!robot' -m test_user_setup` against the source *before* Task 2's fix: 7 tests ran, 4 failed (the three pre-existing methods stayed green), 0 errors. The four actual failure lines:

```
AssertionError: True is not False : A locked account must not be enrolled, even by a correct code.
  (test_handleSubmit_refuses_a_locked_account_even_with_a_correct_code)

AssertionError: 1 != 0 : One wrong code must increment the shared failed-attempts counter.
  (test_handleSubmit_wrong_code_increments_the_failed_attempts_counter)

AssertionError: 0 != 3 : A correct code must clear the shared failed-attempts counter.
  (test_handleSubmit_correct_code_clears_the_failed_attempts_counter)

AssertionError: False is not True : Reaching max_failed_attempts must lock the account.
  (test_handleSubmit_reaching_max_failed_attempts_locks_the_account)
```

None of the four passed before the fix -- each measures the gate it names, not a vacuous assertion.

## Task 2: the fix

`user = api.user.get_current()` hoisted above the dispatch (after the `is_site_local_user()` guard, so a Zope-root account still returns before `is_account_locked` sees a user with no property sheet) and passed explicitly to `validate_token(token, user=user)`. The single `if valid_token:` became a three-arm `if is_account_locked(user): ... elif validate_token(...): ... else: ...` chain:

- **Locked arm:** sets `reason` to the same `"Invalid token or token expired."` text a wrong code uses, and falls through to the shared tail (see Deviation below) -- no `validate_token` call, no counter write.
- **Success arm:** `reset_failed_second_factor(user)` runs before the existing `try:` block (P5-14 -- a `PropertyValueError` from a mis-declared property must surface as a 500, not be swallowed), then the existing try/except/RECOV-03 body runs byte-identical.
- **Wrong-code arm:** `register_failed_second_factor(user)` then the same `reason` text.

Re-run of `bin/test -t '!robot' -m test_user_setup` after the fix: 7 tests, 0 failures, 0 errors. Full suite `bin/test -t '!robot'`: **132 tests, 0 failures, 0 errors** (baseline 128 -- the four new tests, no regressions).

## Task 3: mutation-proof table

Each mutation was applied to the now-green source, tests re-run, then the source was restored and `git diff --stat src/imio/googleauthenticator/browser/forms/user_setup.py` confirmed empty before moving to the next mutation.

| # | Mutation | Methods that went red | Restored clean |
|---|----------|------------------------|-----------------|
| 1 | Removed the `is_account_locked` arm (`if is_account_locked(user):` -> `if False:`) | `test_handleSubmit_refuses_a_locked_account_even_with_a_correct_code` (1 of 7) | Yes |
| 2 | Removed the `register_failed_second_factor(user)` call in the wrong-code arm | `test_handleSubmit_wrong_code_increments_the_failed_attempts_counter`, `test_handleSubmit_reaching_max_failed_attempts_locks_the_account` (2 of 7) | Yes |
| 3 | Removed the `reset_failed_second_factor(user)` call in the success arm | `test_handleSubmit_correct_code_clears_the_failed_attempts_counter` (1 of 7) | Yes |

Every mutation reproduced red on exactly the methods it should, and no others -- none of the four tests stayed green under removal of its own guard, so none needed fixing.

**Remaining gates:**
- `bin/test-coverage -t '!robot'` exits 0 -- **TOTAL 90%** (1076 statements, 72 missed, 288 branches, 53 partial). Unchanged from the pre-change baseline percentage (statement/branch counts shifted slightly since the fix touched `user_setup.py`'s branch structure, but the TOTAL percentage held at 90%, matching the recorded baseline).
- `bin/code-analysis` exits 0 -- all three commits landed without `--no-verify`.
- `grep -n is_account_locked` / `validate_token(token` in `user_setup.py`: `is_account_locked` at line 122, `validate_token(token, ...)` at line 124 -- the lock check runs strictly above the validation call.

## Deviations from Plan

### Auto-fixed Issues

None -- plan executed exactly as written, including the one deliberate deviation the plan itself calls out and asks to be recorded:

**Deliberate deviation from `reset_bar_code.py`'s locked-arm shape (per plan Task 2, not a Rule 1-4 deviation):**
`reset_bar_code.py`'s locked arm adds its message and `return`s immediately -- equivalent to falling through, because that handler's failure tail is message-only (no redirect binding on that path). `user_setup.py`'s wrong-code arm, by contrast, also binds `redirect_url` and redirects to the setup form on any failure. An early `return` in the locked arm here would therefore leave the locked response at 200-with-no-`Location` while a wrong code gets a 302 -- reinstating exactly the message-plus-response oracle that 05-05 closed on the reset form (MFA-08's no-oracle requirement). So the locked arm in `user_setup.py` falls through to the shared `if reason is not None:` tail, producing the same message and the same redirect target as a wrong code. A comment at the locked arm cross-references `reset_bar_code.py`'s equivalent comment and states both arms must be changed together.

## Auth Gates

None encountered.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources introduced.

## Threat Flags

None -- all three STRIDE threats in the plan's threat register (T-fsp-01 critical, T-fsp-02 medium, T-fsp-03 low/accepted) were the plan's own pre-identified threats, fully mitigated by Task 2's fix (T-fsp-01, T-fsp-02) or already accepted (T-fsp-03, same bounded self-clearing DoS already accepted for the reset path under T-05-08/P5-13). No new, previously-unmodeled surface was introduced.

## Verification Checklist

- [x] `bin/test -t '!robot'`: 132 tests, 0 failures, 0 errors (baseline 128)
- [x] `bin/test-coverage -t '!robot'` exits 0, TOTAL 90% (at or above baseline)
- [x] `bin/code-analysis` exits 0; all three commits landed without `--no-verify`
- [x] All four new tests recorded RED against the unfixed source in Task 1, and each recorded RED again under removal of its own guard in Task 3, with byte-identical restoration
- [x] `is_account_locked` call confirmed above the `validate_token` call in `user_setup.py`

## Commits

- `3e54afe` test(260806-fsp): add four lockout tests for SetupForm.handleSubmit
- `5f719f9` fix(260806-fsp): wire the lockout counter into SetupForm.handleSubmit
- `8acfd42` docs(260806-fsp): record the lockout-counter fix in CHANGES.rst

## Self-Check

- FOUND: src/imio/googleauthenticator/browser/forms/user_setup.py (is_account_locked/register_failed_second_factor/reset_failed_second_factor wired in)
- FOUND: src/imio/googleauthenticator/tests/test_user_setup.py (four new test methods)
- FOUND: CHANGES.rst (new bullet under 1.0.0 (unreleased), ending [chris-adam])
- FOUND: commit 3e54afe
- FOUND: commit 5f719f9
- FOUND: commit 8acfd42

## Self-Check: PASSED
