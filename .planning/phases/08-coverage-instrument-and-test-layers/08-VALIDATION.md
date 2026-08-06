---
phase: 8
slug: coverage-instrument-and-test-layers
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-05
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `08-RESEARCH.md` §Validation Architecture. Every command below was run live
> on 2026-08-05 in this working tree unless marked otherwise.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testing.testrunner` via `bin/test` (Plone/Zope2 standard — not pytest, not unittest2 discovery) |
| **Config file** | none dedicated — driven by `[test]` / `[testenv]` in `base.cfg` plus the layer registrations in `src/imio/googleauthenticator/testing.py` |
| **Quick run command** | `bin/test -t test_<name>` (single test or module, matched by name substring) |
| **Full suite command** | `bin/test -t '!robot'` |
| **Coverage-gated command** | `bin/test-coverage -t !robot` — generated script; **does not exist until QUAL-03 enables the `[coverage]` / `[test-coverage]` buildout parts** |
| **Estimated runtime** | ~58 seconds for 111 tests (measured 2026-08-05) |

---

## Sampling Rate

- **After every task commit:** `bin/test -t '!robot'` — 111 tests, ~58s
- **After every plan wave:** `bin/test-coverage -t !robot` once QUAL-03 has landed. Before that,
  `bin/coverage run --rcfile=.coveragerc bin/test -t '!robot' && bin/coverage report --rcfile=.coveragerc -m`.
  **Pass `--rcfile` explicitly** — the installed coverage 4.2 silently ignores `COVERAGE_RCFILE`
  and returns the old broken figure while appearing to have used the new config (CONTEXT.md D-02).
- **Before `/gsd-verify-work`:** `bin/test-coverage -t !robot` exits 0 **and** `bin/code-analysis` exits 0
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Task IDs are assigned by the planner; this table is seeded per requirement and the plan/wave/task
columns are filled in during planning and execution.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 1 | QUAL-01 | — | N/A — instrument correctness, no security surface | config + report-shape check | `bin/coverage report --rcfile=.coveragerc -m` — output must carry `Branch` and `BrPart` columns | ✅ `bin/coverage` exists | ⬜ pending |
| TBD | TBD | 1 | QUAL-02 | — | A failing test must fail the build; today it does not | red-build proof (non-vacuity mutation check) | Add one deliberately-failing test → `bin/test-coverage` → expect non-zero exit → remove the test → `git diff` empty | ❌ no permanent file — a documented, then-reverted mutation | ⬜ pending |
| TBD | TBD | 1 | QUAL-03 | — | N/A | build verification | `bin/buildout -c test-4.3.cfg`; then `bin/coverage --version` reports `5.5` and `bin/createcoverage` is gone | ❌ no test file — buildout-level | ⬜ pending |
| TBD | TBD | ≥2 | QUAL-04 | — | N/A | coverage threshold via `--fail-under=90` in the `[test-coverage]` template | `bin/test-coverage -t !robot` (exit 0) | New tests extend existing `tests/test_*.py`; targets per CONTEXT.md D-11 | ⬜ pending |
| TBD | TBD | ≥2 | QUAL-05 | — | Test isolation — a leaked commit must not let a later test pass on stale state | integration / functional, all 14 existing test files | `bin/test -t '!robot'` must stay green through the layer migration, absorbing D-08 fallout | ✅ 14 existing files, edited in place | ⬜ pending |
| TBD | TBD | last | QUAL-06 | — | N/A | lint gate | `bin/code-analysis` (exit code 0) | ✅ tool exists; 500 findings across 15 codes measured 2026-08-05 | ⬜ pending |
| TBD | TBD | ≥2 | QUAL-07 | — | Installedness asserted through what this package controls, so a correct change cannot fail the test | unit / integration | `bin/test -t test_generic` | ✅ `src/imio/googleauthenticator/tests/test_generic.py` (existing, edited) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. `zope.testing.testrunner`, the 14 existing
test files, and the `plone.app.testing` layers are all in place. What this phase repairs is the
**instrument** — `.coveragerc`, the buildout parts, the CI command, the test layer — not the test
framework plumbing. The only genuinely new test *content* is CONTEXT.md D-11's coverage-gap tests,
which extend existing test files and classes rather than needing new fixtures.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A failing test produces a red `bin/test-coverage` build | QUAL-02 | The proof requires deliberately breaking the suite, which cannot live in the suite. ROADMAP success criterion 1 and CONTEXT.md `<specifics>` both require a real red build rather than an inspection, because the current failure mode is invisible: `bin/test` exits non-zero, the next line runs anyway, `coverage report --fail-under=90` exits 0, and the script exits 0 with nothing in the output saying a test failed. | Add one assertion guaranteed to fail to an existing test method. Run `bin/test-coverage -t '!robot'`. Record the non-zero exit code and the output. Remove the assertion. Confirm `git diff` is empty so the tree is byte-identical. |
| CI actually runs the coverage-gated command | QUAL-04 | The gate lives in `.github/workflows/package-test.yml`'s single `test_command` string, handed to a reusable workflow this repo does not own. Only a real CI run proves the wiring. | After the `test_command` change lands, push and confirm the GitHub Actions run invokes `bin/test-coverage` and that the job fails if coverage drops below 90. Research settled that the shared workflow builds every buildout part, so `bin/test-coverage` will exist — this verification confirms it in practice. |
| The pre-commit hook stops requiring `--no-verify` | QUAL-06 | The hook is installed by buildout into `.git/hooks`; its effect is observable only by attempting a real commit. | After the style sweep lands, make a trivial commit **without** `--no-verify` and confirm it succeeds. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
