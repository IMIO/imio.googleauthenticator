---
phase: 10
slug: global-enforcement-and-enrollment
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| TBD | TBD | TBD | MFA-15 | Install sets the enable flag for every pre-existing account and creates no seed (D-02) | integration | `bin/test -t test_setuphandlers` | ✅ extend `tests/test_setuphandlers.py` — 22 existing methods, none cover per-user enrollment | ⬜ pending |
| TBD | TBD | TBD | MFA-15 (D-04) | Install never partially enrols without reporting it | integration | `bin/test -t test_setuphandlers` | ✅ same file, new negative test | ⬜ pending |
| TBD | TBD | TBD | MFA-15 (D-13) | Installing twice changes nothing the first install did | integration | `bin/test -t test_setuphandlers` | ✅ same file | ⬜ pending |
| TBD | TBD | TBD | MFA-16 | Self-disable is refused while the global setting is on; flag, seed and reset token all unchanged afterwards | integration | `bin/test -t test_disable_two_factor_authentication` | ✅ extend — 3 existing methods, no global-setting gate exists in source yet | ⬜ pending |
| TBD | TBD | TBD | MFA-16 (D-18) | The all-users disable view is refused the same way | integration | `bin/test -t test_disable_two_factor_authentication_for_all_users` or the module above | ❌ W0 — verify whether a test module exists for the all-users view | ⬜ pending |
| TBD | TBD | TBD | MFA-17, MFA-18 | Enable link offered whenever the user is not enrolled, whatever the global setting says; disable link only when enrolled and the setting is off | unit | `bin/test -t test_settings_helper` | ❌ **W0 — `tests/test_settings_helper.py` does not exist**; zero coverage of this module today | ⬜ pending |
| TBD | TBD | TBD | MFA-18 (D-15) | "Regenerate recovery codes" stays visible for an enrolled user while the global setting is on | unit | `bin/test -t test_settings_helper` | ❌ W0 — same new file | ⬜ pending |
| TBD | TBD | TBD | MFA-19 | A user with the flag set who has not completed enrollment is routed to the enrollment page, not the code-entry page | integration | `bin/test -t test_pas_plugin` | ✅ file exists, needs substantial new coverage | ⬜ pending |
| TBD | TBD | TBD | MFA-19 (D-16) | The enrollment page is reachable and shows the QR code for a user arriving with a cleared session cookie and a valid signed `auth_user` parameter | integration | `bin/test -t test_user_setup` | ❌ W0 — `test_user_setup.py` is entirely authenticated-session-based today | ⬜ pending |
| TBD | TBD | TBD | D-17 property | The new member-data property recording completed enrollment survives a set/get round trip | unit | `bin/test -t test_adapter` | ✅ `tests/test_adapter.py` already documents this convention for the lockout and replay counters | ⬜ pending |
| TBD | TBD | TBD | Standing constraint | No MFA state is written from the PAS plugin | source guard | `bin/test -t test_no_second_factor_state_written_from_the_plugin` | ✅ exists — must be **extended, not worked around** | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Three genuine gaps, all identified by research against the real test tree:

- [ ] **`src/imio/googleauthenticator/tests/test_settings_helper.py` does not exist.** There is
      zero coverage of `browser/settings_helper.py` today. This file must be created, not extended.
      It covers the enable and disable link conditions (D-10, D-11) and the
      "Regenerate recovery codes" collateral check (D-15).
- [ ] **No existing test raises an exception from inside `setuphandlers.setupVarious`.** Needed
      before trusting that "let the exception propagate" actually satisfies D-04's requirement to
      report a partial enrollment plainly. Research flagged this as an unverified assumption.
- [ ] **No existing test exercises the enrollment form with an anonymous request carrying a valid
      signed `auth_user` parameter.** `tests/test_user_setup.py` is entirely authenticated-session
      based. This is the mode MFA-19 needs (D-16), so it is new ground.

**Project convention, inherited from phases 1 through 9:** every new test gets a non-vacuity check
— prove it goes red against the unmodified source, then restore the source byte-identical, and
record the real failure output.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Installing the add-on onto a real populated site enrols the existing accounts and none of them is locked out at next login | MFA-15 + MFA-19 together | The failure this phase exists to prevent is a site-wide lockout on first install onto a populated site. A test can prove the flag is set and the routing is correct, but only a real install onto a site with real accounts exercises the whole path in one piece — which is how the original problem was found (recorded 2026-08-05 on a two-egg environment). | 1. Start from a site with several existing accounts and the add-on not installed. 2. Export `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`. 3. Install the add-on with `globally_enabled` on. 4. Log in as one of the pre-existing accounts. 5. Confirm you are shown the enrollment page with a QR code — not a code-entry prompt. 6. Complete enrollment and confirm login succeeds. |
| The four settings combinations all leave a reachable enrollment path | MFA-18, success criterion 5 | Criterion 5 is a statement about combinations. Automated tests cover each condition, but confirming no combination strands a user is a judgement across the matrix. | Cross the global setting on/off with the user enrolled/not enrolled. In all four cases confirm the user can reach enrollment. |

---

## Validation Sign-Off

- [ ] All tasks have an automated verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without an automated verify
- [ ] Wave 0 covers all three missing-coverage items above
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
