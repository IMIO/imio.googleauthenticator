---
phase: 10
slug: global-enforcement-and-enrollment
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-06
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `bin/test`, `unittest2.TestCase` plus this repo's `BaseTest` mixin (`tests/base.py`) |
| **Config file** | none dedicated — driven by the `test-4.3.cfg` / `base.cfg` buildout parts; coverage scoped by `.coveragerc` (`source = src/imio/googleauthenticator`, `branch = True`) |
| **Quick run command** | `bin/test -t test_setuphandlers` / `-t test_disable_two_factor_authentication` / `-t test_settings_helper` / `-t test_pas_plugin` / `-t test_user_setup` |
| **Full suite command** | `bin/test -t '!robot'` |
| **Coverage-gated run** | `bin/test-coverage -t '!robot'` — branch coverage must stay above 90% |
| **Estimated runtime** | ~35–60 seconds full suite; Plone 4.3 layer setup dominates |

---

## Sampling Rate

- **After every task commit:** the single most relevant module, `bin/test -t test_<module>`
- **After every plan wave:** `bin/test -t '!robot'`
- **Before `/gsd-verify-work`:** `bin/test-coverage -t '!robot'` green above 90%, and
  `bin/code-analysis` exit 0
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

> Task IDs are assigned when the PLAN.md files are written. Seeded from the research's
> Phase Requirements → Test Map.

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T2 | 10-01 | 1 | MFA-15 | Install sets the enable flag for every pre-existing account and creates no seed (D-02) | integration | `bin/test -t test_setuphandlers -t test_user_setup` | ✅ `_enroll_existing_users` (`setuphandlers.py`); proven end-to-end by 10-01's tracer test, matrixed by 10-02's `test_install_enrolls_every_pre_existing_account_without_a_seed` | ✅ green |
| 02-T2 | 10-02 | 2 | MFA-15 (D-04) | Install never partially enrols without reporting it | integration | `bin/test -t test_setuphandlers` | ✅ `test_install_enrollment_reports_a_failure_instead_of_partially_enrolling` | ✅ green |
| 02-T1 | 10-02 | 2 | MFA-15 (D-13) | Installing twice changes nothing the first install did | integration | `bin/test -t test_setuphandlers` | ✅ `test_install_enrollment_is_idempotent_across_two_profile_applications` | ✅ green |
| 03-T1/T2 | 10-03 | 2 | MFA-16 | Self-disable is refused while the global setting is on; flag, seed and reset token all unchanged afterwards | integration | `bin/test -t test_disable_two_factor_authentication` | ✅ `disable_two_factor_authentication.py`'s D-08 guard + 3 new test methods | ✅ green |
| 03-T1/T2 | 10-03 | 2 | MFA-16 (D-18) | The all-users disable view is refused the same way | integration | `bin/test -t test_disable_two_factor_authentication` | ✅ `disable_two_factor_authentication_for_all_users.py`'s D-18 guard + `TestDisableTwoFactorAuthenticationForAllUsers` (new class, 2 methods) | ✅ green |
| 04-T1/T3 | 10-04 | 2 | MFA-17, MFA-18 | Enable link offered whenever the user is not enrolled, whatever the global setting says; disable link only when enrolled and the setting is off | unit | `bin/test -t test_settings_helper` | ✅ **W0 closed** — `tests/test_settings_helper.py` created from scratch, 100% statement coverage on `browser/settings_helper.py` | ✅ green |
| 04-T2/T3 | 10-04 | 2 | MFA-18 (D-15) | "Regenerate recovery codes" stays visible for an enrolled user while the global setting is on | unit | `bin/test -t test_settings_helper -t test_generic` | ✅ `show_regenerate_recovery_codes_link` + `test_regenerate_link_survives_global_enforcement` + `test_every_settings_combination_leaves_enrollment_reachable` (the criterion-5 matrix, resolved via `listActionInfos`) | ✅ green |
| 01-T2 | 10-01 | 1 | MFA-19 | A user with the flag set who has not completed enrollment is routed to the enrollment page, not the code-entry page | integration | `bin/test -t test_pas_plugin` | ✅ `REQUEST_KEY_ENROLLMENT_NEEDED` routing seam; hardened in 10-05 (positive-presence + generalised-absence guard assertions) | ✅ green |
| 01-T3 | 10-01 | 1 | MFA-19 (D-16) | The enrollment page is reachable and shows the QR code for a user arriving with a cleared session cookie and a valid signed `auth_user` parameter | integration | `bin/test -t test_user_setup` | ✅ **W0 closed** — `SetupForm._resolve_signed_user`/`action()`; 10-05 adds the tampered-signature negative case | ✅ green |
| 05-T3 | 10-05 | 2 | D-17 property | The new member-data property recording completed enrollment survives a set/get round trip | unit | `bin/test -t test_adapter` | ✅ `test_enrollment_completion_property_round_trips_as_a_bool` (`INTERNAL_MEMBERDATA_PROPERTIES`, renamed from `LOCKOUT_STATE_PROPERTIES`) | ✅ green |
| 05-T1 | 10-05 | 2 | Standing constraint | No MFA state is written from the PAS plugin | source guard | `bin/test -t test_no_second_factor_state_written_from_the_plugin` | ✅ extended (not worked around): positive-presence assertion for `has_completed_enrollment(`, generalised absence assertion for `setMemberProperties` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Three genuine gaps, all identified by research against the real test tree:

- [x] **`src/imio/googleauthenticator/tests/test_settings_helper.py` does not exist.** Closed by
      **plan 10-04**: the file was created from scratch (`TestSettingsHelper`, 6 methods), reaching
      100% statement coverage on `browser/settings_helper.py` (was 0%). Covers the enable and
      disable link conditions (D-10, D-11) and the "Regenerate recovery codes" collateral check
      (D-15), including the MFA-18/criterion-5 four-case matrix resolved via `listActionInfos`.
- [x] **No existing test raises an exception from inside `setuphandlers.setupVarious`.** Closed by
      **plan 10-02**: `test_install_enrollment_reports_a_failure_instead_of_partially_enrolling`
      injects a real `ValueError` via a `_FakeApiWithOneFailingUser` collaborator and proves it
      propagates unswallowed through `applyProfile`, settling RESEARCH.md's open assumption A1 —
      "let it raise" satisfies D-04 as originally designed; no rewrite of `_enroll_existing_users`
      was needed.
- [x] **No existing test exercises the enrollment form with an anonymous request carrying a valid
      signed `auth_user` parameter.** Closed by **plans 10-01 and 10-05**: `SetupForm.
      _resolve_signed_user()`/`action()` (plan 10-01) serve exactly this request shape, proven by
      the tracer's install→login→QR→code test and the empty/unresolvable `auth_user` probe; plan
      10-05 adds the resolvable-but-tampered-signature variant
      (`test_enrollment_page_refuses_an_invalid_signature`).

**Project convention, inherited from phases 1 through 9:** every new test gets a non-vacuity check
— prove it goes red against the unmodified source, then restore the source byte-identical, and
record the real failure output.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Outcome |
|----------|-------------|------------|-------------------|---------|
| Installing the add-on onto a real populated site enrols the existing accounts and none of them is locked out at next login | MFA-15 + MFA-19 together | The failure this phase exists to prevent is a site-wide lockout on first install onto a populated site. A test can prove the flag is set and the routing is correct, but only a real install onto a site with real accounts exercises the whole path in one piece — which is how the original problem was found (recorded 2026-08-05 on a two-egg environment). | 1. Start from a site with several existing accounts and the add-on not installed. 2. Export `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`. 3. Install the add-on with `globally_enabled` on. 4. Log in as one of the pre-existing accounts. 5. Confirm you are shown the enrollment page with a QR code — not a code-entry prompt. 6. Complete enrollment and confirm login succeeds. | **BLOCKED** — same precedent as Phase 9's TOTP-client check. This execution environment has no operator and no `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` exported to `bin/instance` (`base.cfg:54` sets it for the `[testenv]` buildout part only, confirmed absent from this shell's environment). Stopped before step 1 — there is no running, populated Plone 4.3 site and no browser to drive in this session. Recorded as blocked, not passed. |
| The four settings combinations all leave a reachable enrollment path | MFA-18, success criterion 5 | Criterion 5 is a statement about combinations. Automated tests cover each condition, but confirming no combination strands a user is a judgement across the matrix. | Cross the global setting on/off with the user enrolled/not enrolled. In all four cases confirm the user can reach enrollment. | **BLOCKED** — the automatable half is green (`test_every_settings_combination_leaves_enrollment_reachable`, plan 10-04: all four cells resolve to a rendered portal action pointing at `@@setup-two-factor-authentication`). The judgement half — a real user, in a real browser, actually completing enrollment from each of the four states, not merely being offered a link — needs the same running site and human as the row above and was not attempted for the same reason. Same precedent as Phase 9. |

---

## Validation Sign-Off

- [x] All tasks have an automated verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without an automated verify
- [x] Wave 0 covers all three missing-coverage items above
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** every automated row is green (`bin/test -t '!robot'` — 165 tests, 0 failures, 0
errors; `bin/test-coverage -t '!robot'` — 92% branch coverage; `bin/code-analysis` — exit 0). Both
Manual-Only Verification rows are recorded as **blocked**, not passed — no operator and no
`IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` available to `bin/instance` in this execution environment, the
same gap Phase 9 hit and recorded rather than inferred around. `status: validated` reflects every
row being accounted for (green or honestly blocked), not that every row was verified end to end.
