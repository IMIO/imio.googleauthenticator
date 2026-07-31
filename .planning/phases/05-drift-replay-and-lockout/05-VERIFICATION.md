---
phase: 05-drift-replay-and-lockout
verified: 2026-07-31T16:19:57Z
status: gaps_found
score: 15/16 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "A locked account is not an oracle (MFA-08 / ROADMAP Phase 5 Success Criterion 3, REQUIREMENTS.md: \"the lock is checked before the token is evaluated so a locked account is not an oracle\")"
    status: failed
    reason: >
      The shipped code makes a locked account distinguishable from an unlocked/nonexistent
      one to an unauthenticated caller who supplies nothing but a guessed or known username
      -- no password, no valid ska signature, no correct TOTP code required. This is
      05-REVIEW.md's CR-01 finding (rated critical), confirmed still present at HEAD
      (972ae68, the commit that only adds the review report -- no fix commit exists after
      it) by direct inspection of browser/forms/token.py:85-106. Before this phase, every
      request to @@google-authenticator-token without a valid signature fell through
      uniformly to the "Invalid data. Details: ..." message regardless of account state.
      This phase's is_account_locked gate runs BEFORE validate_user_data, so a locked
      account now answers "Invalid token or token expired." even with no signature at all,
      while every other account (unlocked, nonexistent, not 2FA-enabled) still answers
      "Invalid data. Details: ...". An attacker can poll
      GET/POST /@@google-authenticator-token?auth_user=<victim> repeatedly and learn,
      purely from which message string comes back, whether victim's second factor is
      currently locked out -- exactly the oracle property MFA-08 was written to rule out,
      for a strictly weaker attacker than the one the shipped test covers.

      The existing test (test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code)
      does not catch this: it always drives a browser that already holds a genuinely
      ska-signed URL obtained through a real password login, so validate_user_data always
      succeeds in that test and the vulnerable code path (no valid signature at all) is
      never exercised. The narrower truth the test proves -- correct vs. incorrect code
      indistinguishable once a legitimate signed session already reached the token form --
      is true and does hold. The broader requirement text ("a locked account is not an
      oracle") is false for the no-signature case.
    artifacts:
      - path: "src/imio/googleauthenticator/browser/forms/token.py"
        issue: "is_account_locked(user) check (lines 88-95) runs before validate_user_data (lines 99-106), so lock status leaks to a caller with no valid signature at all"
    missing:
      - "Move the is_account_locked check in token.py::TokenForm.handleSubmit to after the validate_user_data check succeeds (05-REVIEW.md CR-01 already contains the concrete fix, matching the ordering reset_bar_code.py already uses relative to its own account guards)."
      - "A new or extended test that drives @@google-authenticator-token anonymously, with a locked account and no signature/auth_timestamp query parameters at all, and asserts the response is the generic \"Invalid data. Details: ...\" message (or is otherwise indistinguishable from the same request against a non-existent or unlocked username) -- not \"Invalid token or token expired.\""
---

# Phase 5: Drift, Replay and Lockout Verification Report

**Phase Goal:** A code from the previous time step still works, a code already used never
works again, and brute-forcing the second factor stops after N attempts — with counters
that survive the request they are written in.
**Verified:** 2026-07-31T16:19:57Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A code for the immediately preceding interval (`current - 1`) is accepted (MFA-05) | VERIFIED | `helpers._find_accepted_interval` tries `(current_interval, current_interval - 1)`; `tests/test_helpers.py#TestDriftAndReplay.test_validate_token_accepts_previous_interval` passes |
| 2 | A code for `current + 1` is refused — window widens backward only | VERIFIED | Same function never tries `+1`; `test_validate_token_rejects_future_interval` passes with a same-seed non-vacuity control |
| 3 | A code already accepted is refused on replay, adjacency pair asserted (MFA-06) | VERIFIED | `validate_token`'s `matched <= last_accepted_interval` check; `test_validate_token_rejects_replayed_interval` passes |
| 4 | Replay rejection is logged with no username/id/token/secret in message or `record.args` (MFA-06) | VERIFIED | `logger.info('TOTP replay rejected')` carries no operand; `test_replay_rejection_log_has_no_username` passes, asserting both `getMessage()` and `record.args`, plus a no-record-on-accept control |
| 5 | Only exactly-6-ASCII-digit input is a candidate token, refused before `onetimepass`/decrypt (MFA-07) | VERIFIED | `_is_six_digit_token` checked first in `validate_token`, before `get_secret`; `test_validate_token_rejects_non_six_digit_input` covers the full matrix incl. the non-ASCII-digit edge |
| 6 | 5 consecutive wrong codes lock the account; the 4th does not (MFA-08) | VERIFIED | `register_failed_second_factor`'s `>= max_failed_attempts` branch; `test_lockout_after_five_failures` passes |
| 7 | **A locked account is not an oracle** (MFA-08 / ROADMAP SC3) | **FAILED (partial)** | The tested claim (correct vs. incorrect code identical once a legitimately signed session already reached the form) holds. The broader, requirement-level claim is false: `is_account_locked` runs before `validate_user_data` in `token.py`, so an unauthenticated caller with only a guessed/known username and **no valid signature at all** can distinguish a locked account from every other account by response message alone. This is 05-REVIEW.md's CR-01, rated critical, confirmed still unfixed at HEAD. See `gaps` above. |
| 8 | The lock releases itself at the epoch it names, no admin action (MFA-09) | VERIFIED | `is_account_locked`'s `locked_until > int(time.time())`; `test_lockout_expires_without_admin_action` asserts the boundary in both directions, no sleep/monkeypatch |
| 9 | `max_failed_attempts` / `lockout_duration` editable, defaults 5 / 900 (MFA-10) | VERIFIED (schema); real control-panel render/persistence is human-verification-only | `IGoogleAuthenticatorSettings` fields present with correct defaults/min; `test_control_panel_has_lockout_fields` passes. Real-instance form rendering explicitly deferred as a backstop truth in 05-01-PLAN.md and 05-01-SUMMARY.md (human_judgment: true) |
| 10 | A successful second factor resets both the counter and the lock (MFA-11) | VERIFIED | `reset_failed_second_factor`; `test_successful_second_factor_resets_failed_attempts` passes, including the "next wrong code reads 1, not 5" non-staleness check |
| 11 | No second-factor state is written from `pas_plugin.py`/`subscribers.py` (MFA-12) | VERIFIED | `grep` over both files for the three property names and three helper function names returns nothing; `test_no_second_factor_state_written_from_the_plugin` source-greps this with positive controls |
| 12 | The failure counter survives a request sequence that begins in `Unauthorized` (MFA-12) | VERIFIED | `test_failed_attempt_counter_survives_unauthorized_request` drives two real `Browser` requests (first genuinely ends in `Unauthorized`) and reads the counter back through a fresh `api.user.get` |
| 13 | Every new memberdata property is declared, round-trips as a Python int, and is confirmed by the profile import (MFA-13) | VERIFIED | `userdataschema.py` + `memberdata_properties.xml` (`type="int"` x3); `test_new_memberdata_properties_round_trip` and `test_memberdata_properties_import_declares_expected_types` both pass, the latter reading `portal_memberdata`'s own property-map API |
| 14 | `@@reset-bar-code` is metered by the same counter/lock, with no bypass at the login form (MFA-08 reset-path scope decision, MFA-11) | VERIFIED | `reset_bar_code.py::handleSubmit` gates on `is_account_locked` after the account guards and before `validate_token`; `test_reset_bar_code_lockout_after_five_failures` proves the lock set through the reset form also refuses a correct code at the login form |
| 15 | Lock/counter writes sit outside `reset_bar_code.py`'s broad `except Exception`; `user_setup.py` untouched | VERIFIED | Grep + line-order acceptance criteria in 05-03-PLAN.md; `git diff -- browser/forms/user_setup.py` is empty |
| 16 | `CHANGES.rst` records the phase's behaviour changes and the profile-import requirement | VERIFIED | `CHANGES.rst` names `max_failed_attempts`, `lockout_duration`, and the `imio.googleauthenticator:default` re-import requirement |

**Score:** 15/16 truths verified (1 failed on its full requirement-level claim; the narrower tested claim within it holds)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/userdataschema.py` | 3 new `Int` fields + omit-list entries | VERIFIED | Confirmed by direct read: fields declared, all 3 names in `form_fields.omit(...)` |
| `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` | 3 `type="int"` entries | VERIFIED | Confirmed present, `type="int"`, default `0` |
| `src/imio/googleauthenticator/browser/controlpanel.py` | `max_failed_attempts`/`lockout_duration` fields + fieldset | VERIFIED | Confirmed: `Int`, `default=5`/`900`, `min=1`, both in `fieldset(...)` list |
| `src/imio/googleauthenticator/helpers.py` | `is_account_locked`, `register_failed_second_factor`, `reset_failed_second_factor`, `TOTP_INTERVAL_SECONDS`, `_is_six_digit_token`, `_find_accepted_interval`, rewritten `validate_token` | VERIFIED | All present, no `except` in the three lockout functions, single `setMemberProperties` call per branch |
| `src/imio/googleauthenticator/browser/forms/token.py` | Lock gate wired into `handleSubmit` | VERIFIED, but the wiring introduces the CR-01 oracle (see gap) | Gate present before `validate_user_data`/`validate_token`; ordering is exactly what creates the leak |
| `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` | Lock gate + counter register/reset | VERIFIED | Gate after account guards, before `validate_token`; reset call outside the `try`/`except` block |
| `src/imio/googleauthenticator/tests/test_token.py` (new) | `TestTokenFormLockout`, 5 methods | VERIFIED | File exists, 5 `def test_` methods matching the plan's named tests |
| `src/imio/googleauthenticator/tests/test_reset_bar_code.py` (new) | `TestResetBarCodeLockout`, 1 method | VERIFIED | File exists, single ordered-assertion method as documented |
| `CHANGES.rst` | Phase 5 entries | VERIFIED | 5 entries under `1.0.0 (unreleased)` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `userdataschema.IEnhancedUserDataSchema` | `memberdata_properties.xml` | Same 3 property names declared in both | WIRED | Both files list identical names; profile-import test confirms the types actually land |
| `browser/forms/token.py::handleSubmit` | `helpers.register_failed_second_factor`/`reset_failed_second_factor` | Sole caller in this plan | WIRED | Confirmed by source-grep test (`test_no_second_factor_state_written_from_the_plugin`)'s positive control |
| `helpers.is_account_locked` | `browser/forms/token.py` / `reset_bar_code.py` | Called before `validate_token` in both views | WIRED (but see CR-01: in `token.py` it is also placed before `validate_user_data`, which is the defect) |
| `helpers.get_app_settings().max_failed_attempts`/`.lockout_duration` | `plone.registry` | Read at check time in `register_failed_second_factor` | WIRED | `test_control_panel_has_lockout_fields` proves the registry seeding path with no `registry.xml` edit |
| `helpers.validate_token` | 3 form views (`token.py`, `reset_bar_code.py`, `user_setup.py`) | Sole write path for `two_factor_authentication_last_interval` | WIRED | Confirmed unchanged call signature; grep shows no other caller |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| MFA-05 | 05-02 | Previous-interval accepted, future refused | SATISFIED | `test_validate_token_accepts_previous_interval`, `test_validate_token_rejects_future_interval` |
| MFA-06 | 05-02 | Replay refused, logged without username | SATISFIED | `test_validate_token_rejects_replayed_interval`, `test_replay_rejection_log_has_no_username` |
| MFA-07 | 05-02 | Exactly-6-digit gate | SATISFIED | `test_validate_token_rejects_non_six_digit_input` |
| MFA-08 | 05-01, 05-03 | N-failure lockout, lock before token, not an oracle | **PARTIALLY SATISFIED** | Lockout mechanics (threshold, reset-path parity, no-bypass) are proven. The "not an oracle" clause is violated for an unauthenticated, no-signature caller (CR-01, unfixed) |
| MFA-09 | 05-01 | Self-expiring lock | SATISFIED | `test_lockout_expires_without_admin_action` |
| MFA-10 | 05-01 | Editable N/duration, defaults 5/900 | SATISFIED (schema); form persistence is human-verification-only | `test_control_panel_has_lockout_fields`; real-instance check deferred |
| MFA-11 | 05-01, 05-03 | Success resets counter | SATISFIED | `test_successful_second_factor_resets_failed_attempts`, reset-path test |
| MFA-12 | 05-01 | No state written from PAS plugin/challenge path | SATISFIED | `test_no_second_factor_state_written_from_the_plugin`, `test_failed_attempt_counter_survives_unauthorized_request`, `bin/test -t test_challenge -t test_pas_plugin` green |
| MFA-13 | 05-01 | Property declaration + round-trip + import proof | SATISFIED | `test_new_memberdata_properties_round_trip`, `test_memberdata_properties_import_declares_expected_types` |

No orphaned requirements: all of MFA-05..13 are claimed by a plan's `requirements:` frontmatter and appear in REQUIREMENTS.md mapped to Phase 5.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/imio/googleauthenticator/browser/forms/token.py` | 88-95 | Lock check ordered before signature validation | 🛑 Blocker | CR-01: creates a distinguishable-response oracle for an unauthenticated, unsigned request; see gap above |
| `src/imio/googleauthenticator/userdataschema.py` | 86-102 | New security-relevant `Int` fields declared without `readonly=True` | ⚠️ Warning | WR-02 in 05-REVIEW.md: the only barrier preventing a user from self-editing their own lockout/replay state through some future non-`CustomizedUserDataPanel` consumer of the schema is the per-view `omit()` call. Mirrors a pre-existing accepted pattern on `two_factor_authentication_secret`/`bar_code_reset_token`, so not a new deviation, but the blast radius is more direct here (live security-control state). Not a phase-blocking gap; recommend a follow-up. |
| `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` | 72-164 | `@@reset-bar-code` shares the lockout counter with the login form and requires no signature before consuming an attempt | ℹ️ Info | WR-01 in 05-REVIEW.md: an explicit, tested, and documented tradeoff (decision P5-13, T-05-08), bounded by `lockout_duration` and asserted in `test_reset_bar_code_lockout_after_five_failures`. Not a gap. |
| `src/imio/googleauthenticator/browser/controlpanel.py` | 116-121, 148-152 | Dead `disable_two_factor_authentication_for_users` import/fetch, pre-existing | ℹ️ Info | IN-01 in 05-REVIEW.md, not introduced by this phase's diff, noted for completeness only |

No `TBD`/`FIXME`/`XXX` markers found in any file this phase modified.

### Human Verification Required

### 1. Control-panel field render and persistence (MFA-10)

**Test:** Run `bin/instance fg`, visit `@@google-authenticator-settings`, set the attempt
limit to 3 and the duration to 60, save, reload.
**Expected:** Both values persist across the reload.
**Why human:** The automated test (`test_control_panel_has_lockout_fields`) covers schema
presence, defaults, and registry readback — the part that regresses silently — but real
form rendering and persistence through the running Plone control panel needs a live
instance; `test_robot.py` is excluded everywhere.

### 2. Real-device drift-boundary acceptance (MFA-05)

**Test:** With `bin/instance fg` running and a real Google Authenticator app enrolled,
wait until a code is about to roll over, submit the just-expired code, then submit the
code before that one.
**Expected:** The just-expired code is accepted; the one before it is refused.
**Why human:** No in-process test can establish this — both sides of an in-process
assertion read the same `time.time()`. Explicitly named as a backstop truth in
05-02-PLAN.md and deferred in 05-02-SUMMARY.md.

### 3. CR-01 fix verification, once applied (MFA-08)

**Test:** After reordering the `is_account_locked` check in `token.py` to run after
`validate_user_data`, send an unauthenticated request with no `signature`/
`auth_timestamp` to `@@google-authenticator-token?auth_user=<locked-account>` and to
`@@google-authenticator-token?auth_user=<unlocked-or-nonexistent-account>`.
**Expected:** Both return the identical `"Invalid data. Details: ..."` message.
**Why human/deferred:** Not yet fixed in the codebase; listed here so the fix can be
verified against the exact attacker model CR-01 describes once it lands.

### Gaps Summary

One must-have — "a locked account is not an oracle" (MFA-08, and ROADMAP Phase 5 Success
Criterion 3) — is only partially true. The phase's own test proves the narrower claim
(a correct and an incorrect code are indistinguishable once a legitimately `ska`-signed
session has already reached the token form), and that part is solid and well-tested. But
the phase's own code review (05-REVIEW.md, CR-01, rated critical) found — and this
verification independently confirmed by reading `browser/forms/token.py:85-106` at
HEAD — that the lock gate was placed *before* signature validation, which means an
unauthenticated party who knows or guesses nothing but a username can now learn whether
that account is currently locked out, with no password and no valid signature. That is a
live, unremediated violation of the general "not an oracle" property MFA-08's own
requirement text asserts, introduced by this phase's own change (pre-phase behaviour
returned a uniform message here regardless of account state). No commit exists after the
review (972ae68, docs-only) that addresses CR-01.

This is a security-relevant, requirement-level gap, not a cosmetic or documentation
issue — closing it is a small, well-scoped fix (05-REVIEW.md already contains the
concrete before/after code and the missing test), but it must land before this phase is
considered to fully satisfy MFA-08.

Two additional review findings (WR-01, WR-02) are explicitly not treated as gaps: WR-01
is a deliberate, tested, and documented tradeoff (decision P5-13); WR-02 mirrors a
pre-existing accepted pattern in this package and is lower severity, recorded above as a
warning-level follow-up recommendation rather than a phase blocker.

All other truths for MFA-05, 06, 07, 09, 10 (schema half), 11, 12 and 13 are solidly
verified against the actual code and a green `bin/test -t '!robot'` (82 tests, confirmed
by the orchestrator prior to this verification), with real behavioral tests (not merely
presence/wiring) proving drift acceptance, replay rejection, lockout threshold behaviour,
self-expiry, counter reset, and survival across an `Unauthorized`-ending request
sequence.

---

_Verified: 2026-07-31T16:19:57Z_
_Verifier: Claude (gsd-verifier)_
