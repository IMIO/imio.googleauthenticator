---
phase: 3
slug: encrypted-seeds-and-local-qr
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-30
validated: 2026-07-30
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

This file was still the unfilled `plan-phase` stub when this audit ran — every row was
placeholder text (`REQ-{XX}`, `{pytest 7.x}`, `T-3-01`) and `status: draft`. It has been
reconstructed from the three PLAN/SUMMARY pairs and cross-referenced against the real
suite, so the audit was effectively State B despite a file being present.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `plone.app.testing` (Plone 4.3 / Python 2.7) — **not** pytest |
| **Config file** | `base.cfg` `[test]` part; pins in `test-4.3.cfg`. No `pytest.ini`/`pyproject.toml` exists and none should be added |
| **Quick run command** | `bin/test -t '<pattern>'` |
| **Full suite command** | `make test` (= `bin/test -t '!robot'`) |
| **Estimated runtime** | ~11 s full suite (48 tests); ~6 s layer setup dominates |
| **Environment** | `base.cfg` `[testenv]` supplies a throwaway `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`; `[test]`'s `environment = testenv` bakes it into the generated `bin/test`. This is also how CI inherits it — CI runs only `bin/buildout` then `bin/test -t !robot` |
| **Excluded** | `test_robot.py` — needs a real browser, excluded everywhere via `-t !robot` |

---

## Sampling Rate

- **After every task commit:** `bin/test -t '<the task's own pattern>'`
- **After every plan wave:** `make test`
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** ~11 s — fast enough that no task in this phase needed a
  narrower sampling loop

---

## Per-Task Verification Map

Keyed by requirement rather than by task id: this phase's three plans carry 9 tasks, but
two are checkpoints (`checkpoint:decision`, `checkpoint:human-verify`) with no code, and
the remaining tasks each satisfy several requirements at once, so a task-keyed table would
duplicate every row.

| Req | Plan | Wave | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|-----|------|------|------------|-----------------|-----------|-------------------|--------|
| SEC-01 | 01 | 1 | T-03-01 | Seed Fernet-encrypted at rest; plaintext never a substring of the stored value | integration | `bin/test -t seed_encryption_round_trip` | ✅ green |
| SEC-02 | 01 | 1 | T-03-02 / T-03-06 | Key read per-call from the environment, never in ZODB, a log, or an exception message | integration | `bin/test -t 'seed_encryption_fails_closed' -t 'encryption_key_is_read_per_call'` | ✅ green |
| SEC-03 | 01 | 1 | T-03-02 / T-03-21 | Enrolment, login, bulk enable and user creation all fail closed on a broken key — never plaintext, never password-only | integration | `bin/test -t 'fails_closed' -t 'login_is_refused_when_seed_key_is_broken' -t 'bulk_enable_reports_failure'` | ✅ green |
| SEC-04 | 01 | 1 | T-03-07 | `v1$` envelope on every ciphertext; unknown/missing prefix refuses rather than attempting a decrypt | integration | `bin/test -t seed_encryption_round_trip -t seed_encryption_fails_closed` | ✅ green |
| SEC-05 | 01 | 1 | T-03-03 / T-03-04 | QR is a local `data:` URI decoding to a real PNG; no external host, no subprocess | integration | `bin/test -t seed_encryption_round_trip` | ✅ green |
| SEC-06 | 01 | 1 | T-03-08 | 160-bit `os.urandom` seed, exactly 32 base32 chars, no padding | integration | `bin/test -t seed_encryption_round_trip` | ✅ green |
| SEC-07 | 02 | 2 | T-03-11 / T-03-21b | The key is present where it must be **and absent where its presence would be the vulnerability** | integration | `bin/test -t seed_key_is_present_in_the_test_environment -t instance_section_declares_no_seed_key` | ✅ green **(gap filled by this audit)** |
| SEC-08 | 02 | 2 | T-03-12 / T-03-13 / T-03-15 | Missing key logs CRITICAL exactly once at process start, naming the variable, never raising from import or ZCML | unit | `bin/test -t on_process_starting` | ✅ green |
| DOC-03 | 02 | 2 | T-03-10 / T-03-14 | README records the out-of-repo Puppet dependency and the ZEO stale-key failure mode | unit | `bin/test -t readme_documents_the_deployment_key` | ✅ green **(gap filled by this audit)** |
| BUG-02 | 03 | 3 | T-03-19 / T-03-20 | `redirect_url` bound on all three reachable paths through `SetupForm.handleSubmit` | integration | `bin/test -t test_handleSubmit` | ✅ green |
| BUG-03 | 03 | 3 | T-03-16 / T-03-17 / T-03-18 | Constant-time reset-token compare, both operands coerced, falsy refuses | unit | `bin/test -t validate_bar_code_reset_token` | ✅ green |
| BUG-05 | 01 | 1 | T-03-05 | `ipaddress == 1.0.23` with `unicode` coercion at all three call sites; hop order unchanged | integration | `bin/test -t TestIPWhitelisting` (7 tests) | ✅ green |

### Post-UAT additions (not phase-3 requirements)

Threats found by human UAT after execution, each closed with a regression test in this
phase's suite. Listed because they are part of the phase's coverage even though no
requirement id predicted them.

| Threat | Secure Behavior | Automated Command | Status |
|--------|-----------------|-------------------|--------|
| T-03-23 | Enrolment refuses an account absent from the site's `acl_users` — no flag, no seed, no QR | `bin/test -t 'not_defined_in_this_site' -t 'is_site_local_user'` | ✅ green |
| T-03-24 | `validate_token` refuses a secret-less user instead of raising `TypeError` as a 500; a decryption failure still propagates | `bin/test -t validate_token_refuses_a_user_with_no_stored_seed` | ✅ green |
| T-03-25 | Reset email survives a non-ASCII sender name / subject | `bin/test -t reset_email_survives_a_non_ascii_sender_name` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No framework install, no new
config, no fixture module was needed — `plone.app.testing` layers and `BaseTest` were
already in place, and `[testenv]` already supplied the one environment variable this
phase introduced.

---

## Gaps Found And Filled By This Audit

Two requirements were verified **once at execution time by a grep acceptance criterion**
and had no assertion surviving into CI. Both are now tested. Each new test was confirmed
to fail against a deliberately violated invariant before being kept — a test that passes
whether or not the invariant holds would have left the gap open while appearing to close
it.

| Gap | Requirement | Why it mattered | Test added | Failure proven by |
|-----|-------------|-----------------|------------|-------------------|
| `[instance]` must declare no key | SEC-07 / T-03-21b (**high**) | Held only by plan 03-02's prohibition P6 and a one-time grep. The threat is the *tempting* edit — a valid placeholder added so the buildout parses — which would encrypt production seeds under a repo-readable value **and** suppress the missing-key CRITICAL log, converting a loud failure into a silent one | `test_subscribers.py::test_instance_section_declares_no_seed_key` | Injecting that exact placeholder into `[instance]`; the test failed, naming the value |
| Deployment docs | DOC-03 / T-03-10, T-03-14 | The only phase-3 requirement with no automated verification. The risk is not deletion but a routine README rewrite quietly dropping the operator-facing paragraphs, leaving the requirement still marked Complete | `test_generic.py::test_readme_documents_the_deployment_key_and_its_failure_mode` | Redacting `concat::fragment`; the test failed |

The `[instance]` test carries a **non-vacuity control asserted first** — `[testenv]` is
known to declare the key, so if the section reader silently returned nothing the real
assertion would pass for the wrong reason. Both tests assert on load-bearing facts rather
than prose, so rewording stays free while removing information does not.

---

## Requirement-Text Divergence (not a gap)

**SEC-07 as written is stale, and the implementation is the safer of the two.** The
requirement says the variable is *"present in all four places it must exist —
`[instance]`, `[testenv]`, the CI workflow, and (out of repo) the Puppet fragment"*. As
built, two of those four are deliberately empty:

- **`[instance]`** — deliberately empty. Plan 03-02's T-03-21b (`high`) concluded a
  placeholder there is worse than an absence, and `README.rst` documents the reasoning.
  The requirement text and the threat model contradict each other; the threat model won.
  This audit added the test that keeps it that way.
- **CI workflow** — empty and *redundant*, not missing. CI runs `bin/buildout` then
  `bin/test`, and `[test]`'s `environment = testenv` bakes the key into the generated
  runner (verified present in `bin/test`). Adding it to `package-test.yml` would create a
  second source of truth for a value that already has one.

Recorded here rather than silently ticked: SEC-07 is marked Complete in `REQUIREMENTS.md`
while two of its four named locations are empty by design. The requirement wording should
be corrected when `REQUIREMENTS.md` is next revised — the behaviour is right, the sentence
describing it is not.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reset email is actually **delivered** by a real SMTP server | DOC-03 adjacency / T-03-25 | The regression test patches `MailBase._send`, so it proves the message survives encoding and reaches MailHost — not that it leaves the host. No SMTP fixture exists and adding one is out of scope for a package retired in ~1–2 years | Request a bar-code reset for an enrolled member and confirm the email arrives. **Performed 2026-07-30 — email received** (`03-SECURITY.md` Residual Risks) |
| Zope reaches "Ready to handle requests" with the key unset | SEC-08 | `test_on_process_starting` calls the handler directly; it cannot prove the real startup sequence completes rather than aborting | `unset IMIO_GOOGLEAUTHENTICATOR_SEED_KEY && bin/instance fg`; expect one CRITICAL line naming the variable and a successful start. **Performed during phase execution** (03-02-SUMMARY.md) |
| The Puppet `concat::fragment` ships the key | SEC-07 | Lives in the separate `industrialisation` repository — outside this repo's commits entirely | Confirm `modules/plone/manifests/buildout.pp` carries the fragment before deploying. **NOT DONE — the feature is not deployable until it ships** |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — none were needed
- [x] No watch-mode flags
- [x] Feedback latency ~11 s
- [x] `nyquist_compliant: true` set in frontmatter — every phase-3 requirement now has
      automated verification, the two audit-found gaps filled and each proven to fail
      against a violated invariant
- [x] Manual-only entries are genuinely manual (SMTP delivery, real process startup,
      out-of-repo Puppet), each with its performed/not-done state recorded

**Approval:** approved 2026-07-30

---

## Validation Audit 2026-07-30

| Metric | Count |
|--------|-------|
| Requirements audited | 12 |
| Covered on entry | 10 |
| Gaps found | 2 (1 PARTIAL — SEC-07; 1 MISSING — DOC-03) |
| Resolved | 2 |
| Escalated | 0 |
| Manual-only | 3 (2 performed, 1 blocked out of repo) |
| Suite | 48 tests, 0 failures, 0 errors (46 → 48) |
