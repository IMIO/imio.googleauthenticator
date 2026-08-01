---
phase: 5
slug: drift-replay-and-lockout
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

Seeded by `plan-phase` from `05-RESEARCH.md` `## Validation Architecture`. Rows are keyed by
requirement, not task id — plans do not exist yet at seed time, and phase 3 showed a task-keyed
table duplicates every row when one task satisfies several requirements. The plan-checker and
`/gsd-validate-phase` fill in the Plan, Wave and Threat Ref columns once plans exist.

Following phase 4's practice, every `Automated Command` below names a **real, intended test
function name** rather than a `{REQ-XX}` placeholder. Phase 3's equivalent file was left as an
unfilled stub and had to be reconstructed by a later audit.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `plone.app.testing` (Plone 4.3 / Python 2.7) — **not** pytest. `unittest2` in test modules |
| **Config file** | `base.cfg` `[test]` part; pins in `test-4.3.cfg`. No `pytest.ini`/`pyproject.toml` exists and none should be added |
| **Quick run command** | `bin/test -t test_helpers -t test_token -t test_reset_bar_code -t test_generic` |
| **Full suite command** | `make test` (= `bin/test -t '!robot'`) |
| **Baseline at seed time** | 66 non-robot tests across 10 modules. Phase 4 measured the full suite at 32.3 s wall clock; layer setup dominates, so expect this phase's additions to cost far less than proportionally |
| **Environment** | `base.cfg` `[testenv]` supplies a throwaway `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`; `[test]`'s `environment = testenv` bakes it into the generated `bin/test`. Any test that reads or writes an encrypted seed needs it |
| **Excluded** | `test_robot.py` — needs a real browser, excluded everywhere via `-t !robot` |
| **Isolation caveat** | `plone.testing` is intentionally unpinned (Plone 4.3 supplies 4.1.3). Browser tests here drive a testbrowser inside an `IntegrationTesting` layer, which commits; pinning 5.0.0 introduces the `TestIsolationBroken` guard and every browser test trips it. Do not add a testing approach that depends on that guard |
| **Time control** | MFA-09 needs a lock to expire. Prefer setting `..._locked_until` directly to a past epoch over sleeping or monkeypatching `time.time()` — the stored value is a plain `int` epoch, so a past value is the whole fixture |

---

## Sampling Rate

- **After every task commit:** `bin/test -t test_helpers -t test_token -t test_reset_bar_code -t test_generic`
- **After every plan wave:** `make test`
- **Before `/gsd-verify-work`:** full suite must be green
- **Feedback latency target:** under 30 s. Phase 4 measured 32.3 s for the full suite and
  recorded the miss rather than ticking it; the same honesty applies here

---

## Per-Requirement Verification Map

| Req | Plan | Wave | Threat Ref | Secure Behavior | Test Type | Automated Command | Test File | Status |
|-----|------|------|------------|-----------------|-----------|-------------------|-----------|--------|
| MFA-05 | 05-02 | 2 | T-05-13 | A code generated for the immediately preceding 30 s interval is accepted; a code for the **next** interval is not — the window widens backward only | integration (real secret, real `get_hotp`) | `bin/test -t test_validate_token_accepts_previous_interval -t test_validate_token_rejects_future_interval` | `tests/test_helpers.py` (new) | ✅ green |
| MFA-06 | 05-02 | 2 | T-05-02 | A code already accepted is refused on second use, because the accepted interval number is recorded and compared | integration | `bin/test -t test_validate_token_rejects_replayed_interval` | `tests/test_helpers.py` (new) | ✅ green |
| MFA-06 (log) | 05-02 | 2 | T-05-04 | The replay rejection is logged, and the log line contains no plaintext username | integration (log capture) | `bin/test -t test_replay_rejection_log_has_no_username` | `tests/test_helpers.py` (new) | ✅ green |
| MFA-07 | 05-02 | 2 | T-05-14 | Only input that is exactly 6 digits reaches TOTP comparison. `"1"`, `"123"`, `"1234567"`, `""`, `"12a456"` and a leading-`+`/whitespace form are all refused before `onetimepass` is called | unit | `bin/test -t test_validate_token_rejects_non_six_digit_input` | `tests/test_helpers.py` (new) | ✅ green |
| MFA-07 (regression) | 05-02 | 2 | — | The existing seed round-trip test still passes under the new format gate — it currently calls `validate_token(get_totp(seed), ...)`, and `get_totp` returns a bare non-zero-padded int, so it must move to `get_totp(seed, as_string=True)` **in the same commit** as the gate | regression | `bin/test -t test_seed_encryption_round_trip` | `tests/test_helpers.py:existing` | ✅ green |
| MFA-08 | 05-01 | 1 | T-05-01 | 5 consecutive failed second-factor submissions lock the account for 900 s | integration (real `Browser` POST sequence) | `bin/test -t test_lockout_after_five_failures` | `tests/test_token.py` (new; decision P5-06 -- named to match the skill's R5 file-to-module rule) | ✅ green |
| MFA-08 (oracle) | 05-01 | 1 | T-05-03 | While locked, a **correct** code and an **incorrect** code produce indistinguishable user-visible outcomes (no redirect either way, same generic message, unchanged lock epoch) — deviation from "byte-identical" wording, since z3c.form echoes the submitted token back into its own input | integration | `bin/test -t test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code` | `tests/test_token.py` (new) | ✅ green |
| MFA-08 (not an oracle, unsigned caller) | 05-04 | 3 | T-05-18 | An unauthenticated request carrying only `auth_user` — no `signature`, no `auth_timestamp`, no password — gets the identical response whether the named account is locked, unlocked-but-enrolled, or does not exist. Closes CR-01: the lock gate previously ran *before* `validate_user_data`, so a locked account alone answered with a distinguishable message to a caller who never proved possession of a valid signature | integration (three-way `Browser` equality, non-vacuity mutation check recorded in 05-04-SUMMARY.md) | `bin/test -t test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account` | `tests/test_token.py` (new) | ✅ green |
| MFA-08 (reset path) | 05-03 | 2 | T-05-16 | The same lock and counter apply to `@@reset-bar-code`, which is anonymously reachable and validates the token before the reset signature. Without this the lockout has a documented bypass — see the scope decision in ROADMAP.md Phase 5 notes | integration (real `Browser` POST sequence) | `bin/test -t test_reset_bar_code_lockout_after_five_failures` | `tests/test_reset_bar_code.py` (new) | ✅ green |
| MFA-09 | 05-01 | 1 | T-05-09 | The lock releases with no admin action once the stored epoch passes | integration | `bin/test -t test_lockout_expires_without_admin_action` | `tests/test_token.py` (new) | ✅ green |
| MFA-10 | 05-01 | 1 | — | Attempt limit and lock duration are editable control-panel fields, defaulting to 5 and 900 | integration (field presence + default value) | `bin/test -t test_control_panel_has_lockout_fields` | `tests/test_generic.py:existing pattern` | ✅ green |
| MFA-11 | 05-01, 05-03 | 1, 2 | — / T-05-16 | A successful second factor sets the failure counter back to zero, so a user who mistypes then succeeds is not one attempt from a lock. 05-03 additionally proves this at `@@reset-bar-code`: the counter and lock clear even when the bar-code-reset signature check then fails | integration | `bin/test -t test_successful_second_factor_resets_failed_attempts -t test_reset_bar_code_lockout_after_five_failures` | `tests/test_token.py`, `tests/test_reset_bar_code.py` (new) | ✅ green |
| MFA-12 | 05-01 | 1 | T-05-07 | No second-factor state is written from the PAS plugin or the challenge plugin. Phase 4's tests must still pass **unmodified** | regression | `bin/test -t test_challenge -t test_pas_plugin` | `tests/test_challenge.py:existing`, `tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin` (new) | ✅ green |
| MFA-12 (survives) | 05-01 | 1 | T-05-07 | The failure counter is still readable after a request sequence that begins with an `Unauthorized`-ending hit, proving the write happened on a committing path and not one that aborted | integration (two-request `Browser` sequence, per resolved Open Question 2) | `bin/test -t test_failed_attempt_counter_survives_unauthorized_request` | `tests/test_token.py` (new) | ✅ green |
| MFA-13 | 05-01 | 1 | T-05-05 | Each new memberdata property is declared in `memberdata_properties.xml` and survives a `setMemberProperties()` → `getProperty()` round trip. An undeclared property is silently discarded, so this test is the only thing that would catch a missing entry | integration | `bin/test -t test_new_memberdata_properties_round_trip` | `tests/test_helpers.py` (new) | ✅ green |
| MFA-13 (import) | 05-01 | 1 | T-05-05 | The GenericSetup import of the new `memberdata_properties.xml` entries actually executes and produces the declared types — the roadmap flagged this as never having been exercised | integration | `bin/test -t test_memberdata_properties_import_declares_expected_types` | `tests/test_setuphandlers.py` (new) | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Non-vacuity is required, not optional.** Phase 4 established the practice: every test above
must additionally be shown to go **red** when the behaviour it guards is removed or reverted,
and the file restored byte-identical afterwards. Record each check in the plan summary. A
lockout test that passes whether or not the lock exists is the exact failure mode MFA-12 and
MFA-13 exist to prevent.

---

## Wave 0 Requirements

No framework install, no new config, no new fixture module — `plone.app.testing` layers and
`tests/base.py` are already in place. Everything below is new **test surface**.

- [ ] `tests/test_helpers.py` — add the drift-accepted, future-interval-rejected,
      replay-rejected, exact-6-digit-format, replay-log-no-username, and property round-trip
      tests. **In the same commit as the format gate**, change the existing
      `test_seed_encryption_round_trip` call from `get_totp(seed)` to
      `get_totp(seed, as_string=True)`, or it starts failing. Partial: the property round-trip
      test (`test_new_memberdata_properties_round_trip`, new `TestDriftAndReplay` class) landed
      in plan 05-01; the drift/replay/format-gate methods remain for plan 05-02
- [x] New `tests/test_token.py` (decision P5-06 -- not `test_token_form.py`) — no test module
      previously exercised `browser/forms/token.py::TokenForm.handleSubmit` at all. Covers
      MFA-08, MFA-09, MFA-11 and the MFA-12 counter-survival sequence. Landed in plan 05-01
- [x] New `tests/test_reset_bar_code.py` — `tests/test_request_bar_code_reset.py` covers the
      *request* form, not the reset form. Needed for the MFA-08 reset-path row. Landed in
      plan 05-03
- [x] `tests/test_generic.py` — extend the existing control-panel field-presence pattern
      (the `IGoogleAuthenticatorSettings['ska_secret_key']`-style lookups already there) to the
      two new integer fields. Landed in plan 05-01
- [x] `tests/test_setuphandlers.py` — add the GenericSetup import assertion for the new
      `memberdata_properties.xml` entries

---

## Open Questions Carried From Research

Seeded here so they cannot be lost between research and validation sign-off. **Both are
resolved before planning starts.**

| # | Question | Blocked | Answer (2026-07-31) |
|---|----------|---------|---------------------|
| 1 | Does the lockout apply only to `browser/forms/token.py`, or to the other `validate_token` call sites too? | MFA-08 scope, and which test modules Wave 0 needs | **Resolved by operator decision: `token.py` **and** `reset_bar_code.py`; `user_setup.py` excluded.** Research recommended token-form-only on the literal requirement wording, but `reset-bar-code` is registered `permission="zope2.View"`, takes its target account from an attacker-supplied `auth_user` query parameter, and calls `validate_token` at `reset_bar_code.py:109` — before the signed `bar_code_reset_token` check at line 120, with a different error message for each failure. Unmetered, it is an anonymous TOTP guessing oracle, which would leave this phase's goal untrue while appearing met. Both are browser form views returning 200/302 that commit, so covering both keeps MFA-12 intact. `user_setup.py` is excluded because it validates the enrolling user's own in-progress secret, so a counter there would let a user lock themselves out mid-setup. Recorded in ROADMAP.md Phase 5 notes |
| 2 | What exactly does "the counter still increments after a request that ends in `Unauthorized`" mean as a test, given the token-form POST does not itself raise `Unauthorized`? | MFA-12 test shape | **Resolved: a real two-request `Browser` sequence**, following phase 4's own idiom (`test_challenge_fires_on_unauthorized`, `test_pub_before_commit_fires_on_login_post`). The first request is the anonymous hit on a 2FA-protected resource that ends in `Unauthorized` and triggers the challenge redirect; the second is the bad-token POST to the token form. A unit-level call against `handleSubmit` never exercises `transactions_manager.commit()`, so it cannot prove the write survived — which is the entire point of MFA-12 |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The two new control-panel fields render and save through the real Plone control panel in a running instance | MFA-10 | The automated test asserts schema field presence and defaults, which is the part that can regress silently. Actual form rendering and persistence through a browser needs a running instance; `test_robot.py` is excluded everywhere | `bin/instance fg`, visit `@@google-authenticator-settings`, change the attempt limit to 3 and the duration to 60, save, reload, and confirm both values persisted |
| A real Google Authenticator app code is accepted at the boundary of the drift window | MFA-05 | Proves the server's interval arithmetic agrees with a real phone's clock, which no in-process test can establish — both sides would use the same `time.time()` | During UAT, wait until a code is about to roll over, then submit the just-expired code. It must be accepted. Submit the one before that; it must be refused |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] Every row shown non-vacuous — goes red when its behaviour is reverted, file restored after
- [ ] No watch-mode flags — `zope.testrunner` has no watch mode; `bin/test` is one-shot
- [ ] Feedback latency measured and recorded (not estimated)
- [ ] Open Questions 1 and 2 remain resolved as recorded above, or the deviation is documented
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
