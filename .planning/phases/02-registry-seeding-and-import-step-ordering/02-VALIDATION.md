---
phase: 2
slug: registry-seeding-and-import-step-ordering
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-30
validated: 2026-07-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

Reconstructed post-execution (State B — no VALIDATION.md was ever seeded for this phase)
from `02-01-PLAN.md`, `02-02-PLAN.md` and their SUMMARYs, cross-referenced against the
live suite.

**This phase needed no new tests.** It is the only one of the three built phases whose
plans converted every invariant into a behavioural assertion rather than leaving a shell
grep as the sole proof — the pattern that produced two gaps in phase 1 and two in phase 3.
The audit's only change was a requirement-id correction in two docstrings; see below.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `plone.app.testing` (Plone 4.3 / Python 2.7); test classes are `unittest2.TestCase` + the local `BaseTest` mixin |
| **Config file** | `base.cfg` `[test]` part; pins in `test-4.3.cfg`. No `pytest.ini`/`pyproject.toml` exists and none should be added |
| **Quick run command** | `bin/test -t setuphandlers` (6 tests, ~1.6 s) |
| **Full suite command** | `make test` (= `bin/test -t '!robot'`) |
| **Estimated runtime** | ~11 s full suite (50 tests); layer setup dominates |
| **Layer** | `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` |
| **Excluded** | `test_robot.py` — needs a real browser, excluded everywhere via `-t !robot` |

---

## Sampling Rate

- **After every task commit:** `bin/test -t setuphandlers` (plan 02-01) or
  `bin/test -t test_get_ska_secret_key` (plan 02-02)
- **After every plan wave:** `make test`
- **Before `/gsd-verify-work`:** full suite green
- **Max feedback latency:** ~11 s full suite, ~1.6 s for this phase's own module
- **Not a gate:** `bin/code-analysis` — 318 pre-existing findings, exit 1 until Phase 8
  (QUAL-06). Commits use `git commit --no-verify`.

---

## Per-Task Verification Map

Keyed by requirement. Two plans, 4 tasks, 6 requirements.

| Req | Plan | Wave | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|-----|------|------|------------|-----------------|-----------|-------------------|--------|
| REG-01 | 02-01 | 1 | — | Registry records exist once the profile is applied, so `get_app_settings()` cannot raise a swallowable `KeyError` inside `setupVarious` | integration | `bin/test -t test_registry_records_exist_after_install` | ✅ green |
| REG-02 | 02-01 | 1 | T-02-04 | The `<depends name="plone.app.registry"/>` dependency is *recorded on the import step*, not merely implied by a lucky sort order | integration | `bin/test -t test_import_step_declares_registry_dependency` | ✅ green |
| REG-03 | 02-01 | 1 | — | GenericSetup's topological sort actually honours that declaration | integration | `bin/test -t test_import_step_ordering` | ✅ green |
| REG-04 | 02-01 | 1 | T-02-04, T-02-05 | `ska_secret_key` is seeded at install time, and `get_ska_secret_key()` is a pure read that never writes registry state from a request path | integration | `bin/test -t test_install_seeds_ska_secret_key -t test_get_ska_secret_key_does_not_mutate_registry` | ✅ green |
| REG-05 | 02-01 | 1 | T-02-10 | Re-applying the default profile leaves an existing key untouched, so signed URLs in flight stay valid | integration | `bin/test -t test_reapply_profile_does_not_reset_ska_secret_key` | ✅ green |
| BUG-04 | 02-02 | 2 | T-02-09 | The derived `ska` key length-prefixes its three components, so two different component tuples sharing a concatenation derive to different keys | integration | `bin/test -t test_get_ska_secret_key` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Why no gaps here.** The plans' acceptance criteria did include shell greps
(`grep -c 'depends name="plone.app.registry"'`, `grep -r runImportStepFromProfile src/`,
`grep -c "u''.join"`), but unlike phases 1 and 3 every one of them has a behavioural test
asserting its *effect*:

- the `<depends>` grep → `test_import_step_declares_registry_dependency` reads the recorded
  step metadata, which is strictly stronger than grepping the ZCML text;
- the `u''.join` / `'{0}{1}{2}'` greps → `test_get_ska_secret_key` pins the exact derived
  shape (`u'2:ab0:2:cd'`), which a bare concatenation cannot produce;
- the `runImportStepFromProfile` absence grep → the *hazard* it guards (registry state
  written from a request path that `transaction.abort()`s) is asserted directly by
  `test_get_ska_secret_key_does_not_mutate_registry`.

That last one is the reason no test was added for it: a grep-for-absence would pin a code
shape, while the behaviour it exists to protect is already pinned. Adding one would be
coverage theatre.

---

## Wave 0 Requirements

Existing infrastructure covered all phase requirements. `test_setuphandlers.py` was created
by this phase's own plan 02-01 as part of the work, not as a Wave 0 prerequisite; no
framework install, config or fixture module was needed.

---

## Requirement-Text Divergence (not a gap)

**REG-03's premise is wrong, and phase 2 proved it empirically rather than complying with
it.** REG-03 reads: *"A test asserts `getSortedImportSteps()` places this package's step
after `plone.app.registry` — **the ordering assertion, not the rename, is the control**."*

Phase 2 found the ordering assertion is a **tautology in this fixture**: with the
`<depends>` line deleted, `imio.googleauthenticator` still sorts after `plone.app.registry`
(index 51 vs 36 of 52) purely by CPython 2.7 string-hash order. The assertion passes either
way and would not catch the deletion. So the phase added
`test_import_step_declares_registry_dependency`, which reads the recorded step metadata and
fails the moment the declaration goes — and kept the ordering test as the outcome check.

That was the right call. But it means REG-03's sentence describes a control that does not
control anything; the real control is REG-02's declaration. Recorded here rather than
silently ticked: **REG-03's wording should be corrected when `REQUIREMENTS.md` is next
revised**, to say the recorded-dependency assertion is the control and the sorted order is
its observable effect. The behaviour is right; the sentence is not.

This is the second such divergence in the milestone — SEC-07 in phase 3 is the other, and
in both cases the implementation is the safer of the two readings.

---

## Corrections Made By This Audit

| What | Why |
|------|-----|
| `test_import_step_declares_registry_dependency`: docstring and both assertion messages relabelled **REG-03 → REG-02** | Both it and `test_import_step_ordering` labelled themselves REG-03, so REG-02 had no test claiming it by id and REG-03 had two. Coverage was real throughout; only the labels were wrong — but a future audit reading ids would have scored REG-02 as uncovered and REG-03 as doubly covered. Suite re-run green after the change (6 tests). |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Creating a new Plone site with the add-on selected logs no `ska_secret_key ... no record` error | REG-01 | Declared `verification: backstop` at plan time (D-01/D-02). No second-site fixture exists, by design, and no `var/log/instance.log` from a real site creation is available to an automated verifier | `bin/instance fg` → add a Plone site with the add-on ticked → `grep -e "no record" -e "defines a field ska_secret_key" var/log/instance.log`. **Performed 2026-07-29 (02-UAT test 1) — clean.** Note the corrected grep: 02-UAT recorded that the original `-e "Cannot find registry"` pattern is over-broad and matches stock Plone site-creation noise in every build |

The mechanised substitutes for this backstop all pass: the RECORDS assertion
(`test_registry_records_exist_after_install`), the DECLARATION assertion
(`test_import_step_declares_registry_dependency`, proven to fail when the `<depends>` line
is deleted) and the ORDERING assertion (`test_import_step_ordering`).

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — 4 tasks, every
      one carrying a `bin/test` invocation
- [x] Wave 0 covers all MISSING references — none were needed
- [x] No watch-mode flags — `bin/test` has no watch mode
- [x] Feedback latency ~11 s full suite, ~1.6 s for this phase's module
- [x] `nyquist_compliant: true` set in frontmatter — all 6 requirements have behavioural
      automated verification, and every shell-grep criterion in the plans has a test
      asserting its effect
- [x] The one manual-only entry is genuinely manual (a real site-creation log) and was
      performed
- [x] Requirement-text divergence (REG-03) recorded rather than ticked

**Approval:** approved 2026-07-30

---

## Validation Audit 2026-07-30

| Metric | Count |
|--------|-------|
| Requirements audited | 6 |
| Covered on entry | 6 |
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only | 1 (performed) |
| Corrections made | 1 (requirement-id relabel in 2 docstrings + 2 assertion messages) |
| Suite | 50 tests, 0 failures, 0 errors (unchanged — no tests added) |
