---
phase: 08-coverage-instrument-and-test-layers
verified: 2026-08-05T13:51:09Z
status: human_needed
score: 14/14 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Push the phase-8 commits (branch `phase-5`, 21 unpushed commits, HEAD `d46604e`) and observe the real GitHub Actions run of `Package Test Workflow`."
    expected: "The job invokes `bin/test-coverage -t !robot` (per `.github/workflows/package-test.yml:14`, confirmed statically) and reports success at 90% branch coverage; a subsequent PR that drops coverage below 90% or breaks a test produces a failing/red job."
    why_human: "All 21 phase-8 commits are local-only (`git log origin/phase-5..HEAD` shows the full commit range unpushed; `gh run list` shows no run newer than the pre-phase-8 07-03 commit). The `test_command` wiring and the local `bin/test-coverage` exit code are verified directly in this report, but no real CI execution of the new coverage-gated command has happened yet, so 'enforced in CI' (ROADMAP success criterion 2 / QUAL-04) is proven by static wiring only, not by an observed CI run."
---

# Phase 8: Coverage Instrument and Test Layers Verification Report

**Phase Goal:** The build fails when tests fail, the coverage figure reflects package code actually exercised, branch coverage clears 90% against that corrected figure, and `bin/code-analysis` exits 0 so the pre-commit hook stops training contributors to use `--no-verify`.
**Verified:** 2026-08-05T13:51:09Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `.coveragerc` scopes measurement to `src/imio/googleauthenticator`, omits `*/tests/*`, and turns on branch coverage | ✓ VERIFIED | Read `.coveragerc`: `[run] source = src/imio/googleauthenticator`, `omit = */tests/*`, `branch = True`. Confirmed no `/tests/` rows in `bin/coverage report` output (ran live, see #4). |
| 2 | A failing test makes `bin/test-coverage` exit non-zero **before** the TOTAL/coverage-report line prints — the `set -e` fix is a real behavior, not an inspection claim | ✓ VERIFIED | Behaviorally reproduced: mutated `tests/test_security.py::test_` to `self.assertTrue(False)`, ran `bin/test-coverage -t '!robot'` live → exit 1, `Ran 124 tests with 1 failures`, zero `TOTAL` lines in output. Reverted byte-identical (`git status --short` clean afterward). |
| 3 | `coverage == 5.5` is pinned and installed; `[coverage]`/`[test-coverage]` buildout parts are enabled; `createcoverage` is fully removed | ✓ VERIFIED | `test-4.3.cfg:68` → `coverage = 5.5`; `base.cfg:13-19` `parts +=` includes `coverage`, `test-coverage`; `grep -rn createcoverage *.cfg` → no matches; `bin/createcoverage` absent from `bin/`; `bin/test-coverage` present and executable. |
| 4 | Branch coverage against the corrected instrument clears 90% | ✓ VERIFIED | Ran `bin/test-coverage -t '!robot'` live: `TOTAL 1070 stmts, 72 missed, 286 branches, 53 partial, 90%`, exit 0 — matches orchestrator's independent measurement exactly. |
| 5 | Browser/functional tests run on a ZSERVER-free `FunctionalTesting` layer; no `IntegrationTesting`/`INTEGRATION_TESTING` reference survives | ✓ VERIFIED | `src/imio/googleauthenticator/testing.py`: `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING = FunctionalTesting(bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,), ...)` — no ZSERVER fixture; `IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING` keeps its own. `grep -rn "INTEGRATION_TESTING\|IntegrationTesting" src/` → no matches. All 16 non-robot test files declare `layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`; `test_subscribers.py` is deliberately layer-free (event-handler unit tests, no Zope state). |
| 6 | The in-layer `portal_quickinstaller` browser-driven install commit is replaced by `applyProfile` in the layer's `setUpPloneSite` | ✓ VERIFIED | `testing.py:26-27`: `def setUpPloneSite(self, portal): applyProfile(portal, 'imio.googleauthenticator:default')`. `grep -rln "quickinstaller\|portal_quickinstaller" src/` → only a docstring in `test_generic.py` explaining why it's *not* used; no functional call sites remain. |
| 7 | `test_product_is_installed` asserts installedness through plugin registration, registry records, and browser-layer presence — never through the quickinstaller tool | ✓ VERIFIED | Read `test_generic.py:54-70`: asserts `PAS_ID in ids` (PAS plugin list), `registry.forInterface(IGoogleAuthenticatorSettings)` (raises `KeyError` if any record missing), `IGoogleAuthenticatorLayer in registered_layers()`. No quickinstaller call. |
| 8 | Every test class in the package runs on the functional layer (no split-layer regression risk) and per-test isolation actually discards in-body `transaction.commit()` calls | ✓ VERIFIED | 16 non-robot test files inspected — all set `layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`. 20 in-body `transaction.commit()` calls remain across the suite by design (safe under `FunctionalTesting`'s per-test `DemoStorage`, per 08-03-PLAN's design rationale) and the full-suite run (0 failures/0 errors, 124+4 tests) confirms no cross-test leakage regression. |
| 9 | `bin/test -t '!robot'` / `bin/test-coverage -t '!robot'` report 0 failures, 0 errors, at least 111 tests | ✓ VERIFIED | Live run: `Total: 128 tests, 0 failures, 0 errors` (124 on the functional layer + 4 on `UnitTests` for `test_subscribers.py`). Matches orchestrator's independently-measured figure. |
| 10 | Branch-coverage gap closed with real, assertive tests for the weakest modules (anonymous-disable guard, bulk-disable view, control-panel save-handler branches) — not by suppressing measurement | ✓ VERIFIED | `test_disable_two_factor_authentication.py::test_anonymous_request_is_refused_and_mutates_nothing` asserts both the 401 status *and* that no member property was mutated (non-vacuity control). `test_controlpanel.py` has 7 test methods including `test_bulk_disable_view_...`, `test_handleSave_globally_disabled_...`, `test_handleSave_neither_true_nor_false_...`. `grep -rn "pragma: no cover" src/` → no matches. `.coveragerc` and `--fail-under=90` unchanged from plan 08-01. |
| 11 | CI's `test_command` is statically wired to the coverage-gated script | ✓ VERIFIED (static only — see human verification) | `.github/workflows/package-test.yml:14`: `test_command: 'bin/test-coverage -t !robot'`. No real CI run has yet exercised this string — see Human Verification. |
| 12 | `bin/code-analysis` exits 0, and the git pre-commit hook (which calls it) therefore passes without `--no-verify` | ✓ VERIFIED | Ran `bin/code-analysis` live → `Flake8............... [OK] in 1.802s`, exit 0. `.git/hooks/pre-commit` content: `bin/code-analysis --return-status-codes`. `base.cfg`'s `[code-analysis]` `flake8-ignore`/`directory` values unchanged from pre-plan (`E123,E124,E501,E126,E127,E128,W391,C901,W503,W504`; `directory = .../src/imio/googleauthenticator`) — gate cleared by fixing findings, not by narrowing what's checked. |
| 13 | The stale finding-count figures (ROADMAP's "~40", old CLAUDE.md's "318") are corrected to the real, re-measured number | ✓ VERIFIED | `CLAUDE.md:41-48` now states 318 (measured in 01-03) grew to 500 (re-measured 2026-08-05 after Phase 7) before plan 08-05 cleared all of them, and explains why (`bin/isort -rc -y src/` sweep + hand fixes). Matches known_open_item #1. |
| 14 | `.planning/codebase/TESTING.md` no longer contradicts the tree (coverage figures, layer names, package name, test count) | ✓ VERIFIED | `TESTING.md` header states "2026-08-05 (Phase 8 plan 08-05, D-19) — package renamed to `imio.googleauthenticator`..."; body references `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`, `bin/test-coverage`, 90% branch coverage, `128 tests, 0 failures, 0 errors`, `.coveragerc`'s corrected `[run]` section. |

**Score:** 14/14 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.coveragerc` | `[run]` with `source`, `omit`, `branch` | ✓ VERIFIED | Exact match, 4 lines, no `[report] include` legacy key. |
| `base.cfg` | `coverage`/`test-coverage` in `parts +=`; `set -e` in `[test-coverage]` template; `createcoverage` gone | ✓ VERIFIED | Confirmed at lines 13-19, 80-94. |
| `test-4.3.cfg` | `coverage = 5.5` pin | ✓ VERIFIED | Line 68. |
| `bin/test-coverage` | buildout-generated, executable | ✓ VERIFIED | Present, mode `755`, content matches template. |
| `src/imio/googleauthenticator/testing.py` | `setUpPloneSite`, ZSERVER-free functional layer | ✓ VERIFIED | Lines 10-42. |
| `src/imio/googleauthenticator/tests/test_generic.py` | rewritten `test_product_is_installed` | ✓ VERIFIED | Lines 54-70. |
| `src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py` | new module, anonymous-guard test | ✓ VERIFIED | Present, 3 test methods. |
| `src/imio/googleauthenticator/tests/test_controlpanel.py` | new bulk-disable and save-handler-branch tests | ✓ VERIFIED | 7 test methods total. |
| `.github/workflows/package-test.yml` | `test_command` → coverage-gated script | ✓ VERIFIED | Line 14. |
| `CLAUDE.md` | corrected lint-debt paragraph | ✓ VERIFIED | Lines 32, 40-48. |
| `.planning/codebase/TESTING.md` | corrected coverage/layer/name/count sections | ✓ VERIFIED | Header + body, spot-checked. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `[test-coverage]` template | `.coveragerc` `[run]` | `bin/coverage run bin/test` reads `.coveragerc` implicitly by cwd/rcfile convention | ✓ WIRED | Live run produced the exact corrected-scope report (no test-module rows, Branch/BrPart columns present). |
| `setUpPloneSite` | `applyProfile(portal, 'imio.googleauthenticator:default')` | Direct call in `testing.py` | ✓ WIRED | Confirmed by source read; confirmed indirectly by `test_product_is_installed` passing (registry records + PAS registration only exist if the profile applied). |
| `test_command` string in `package-test.yml` | `bin/test-coverage` | Reusable workflow `IMIO/gha-workflows/package-test-legacy.yml@v1` | ⚠️ WIRED (statically) — unexercised by a real push | See Human Verification. |
| `.git/hooks/pre-commit` | `bin/code-analysis --return-status-codes` | Buildout-generated hook | ✓ WIRED | Hook content confirmed; `bin/code-analysis` confirmed exit 0 live. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green under corrected instrument | `bin/test-coverage -t '!robot'` | `Total: 128 tests, 0 failures, 0 errors`; `TOTAL 1070/72/286/53 90%`; exit 0 | ✓ PASS |
| Red build on a real failing test | mutate `test_security.py::test_` → `assertTrue(False)`, run `bin/test-coverage -t '!robot'` | exit 1, `1 failures`, zero `TOTAL` lines printed; mutation reverted, tree clean | ✓ PASS |
| Lint gate | `bin/code-analysis` | `Flake8............... [OK]`, exit 0 | ✓ PASS |
| Pre-existing debt markers not phase-introduced | `git blame` on the 6 `TODO`/`FIXME` lines still present in phase-8-touched files (`helpers.py`, `token.py`, `user_setup.py`) | All blame to 2014/2015 fork-era commits, untouched by phase 8's line content | ✓ PASS (confirms these are out-of-scope debt, not new markers this phase introduced) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| QUAL-01 | 08-01 | `.coveragerc` scopes measurement correctly | ✓ SATISFIED | Truth #1 |
| QUAL-02 | 08-01 | `bin/test-coverage` fails build on test failure, proven not inspected | ✓ SATISFIED | Truth #2, behavioral spot-check |
| QUAL-03 | 08-01 | `[coverage]`/`[test-coverage]` parts enabled, `coverage==5.5`, `createcoverage` removed | ✓ SATISFIED | Truth #3 |
| QUAL-04 | 08-04 | Branch coverage >90%, enforced in CI | ✓ SATISFIED locally / ? NEEDS HUMAN for CI enforcement | Truth #4 (local), Truth #11 (CI wiring static-only) |
| QUAL-05 | 08-02, 08-03 | ZSERVER-free functional layer replaces quickinstaller-driven integration layer | ✓ SATISFIED | Truths #5, #6, #8 |
| QUAL-06 | 08-05 | `bin/code-analysis` exits 0 | ✓ SATISFIED | Truth #12, behavioral spot-check |
| QUAL-07 | 08-02 | Installedness asserted via package-controlled facts, not quickinstaller | ✓ SATISFIED | Truth #7 |

All 7 requirement IDs declared in the phase (QUAL-01..07) are accounted for across the 5 plans' frontmatter and REQUIREMENTS.md marks all 7 "Complete." No orphaned requirements found for Phase 8.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py` | 112-113 | `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)` — re-raised exception is not a `ValueError`, escapes the enclosing `except ValueError:`, produces a bare 500 instead of the graceful-failure path every sibling branch uses | ℹ️ Info (pre-existing, out of phase-8 scope) | Confirmed pre-existing via `git blame` — not introduced or touched by any phase-8 commit's line content. Already documented as CR-01 in the committed `08-REVIEW.md`. QUAL-01..07 do not call for fixing production bugs incidentally found during coverage work, and plan 08-04's explicit prohibition ("MUST NOT change the behaviour of the code under test while writing tests for it") argues against touching it inside this phase. Judged **consistent with phase scope** to leave open, tracked in the review for future work — not a phase-8 blocker. |
| `src/imio/googleauthenticator/helpers.py` | 254, 316, 873, 901 | Stale `TODO`/`FIXME` markers (`hashed` parameter never implemented; Plone escaping caveat) | ℹ️ Info (pre-existing, 2014-2015 fork-era) | `git blame` confirms none were touched by phase-8 commits. Not a phase-8 debt-marker gate violation — the gate targets markers introduced by the phase under verification. |
| `src/imio/googleauthenticator/tests/test_security.py` | 17-19 | Empty placeholder test (`test_` with a docstring-only body, asserts nothing) | ℹ️ Info (pre-existing, documented as IN-01 in `08-REVIEW.md`) | Inflates test count by 1 with zero assertions. Not introduced by phase 8; already flagged in the committed review for follow-up. |

No 🛑 blockers found in phase-8-authored or phase-8-modified code.

### Human Verification Required

### 1. Real CI enforcement of the coverage-gated command

**Test:** Push the phase-8 commits (currently local-only on branch `phase-5`, 21 commits ahead of `origin/phase-5`) and observe the resulting GitHub Actions run of `Package Test Workflow`.
**Expected:** The job runs `bin/test-coverage -t !robot`, exits 0 at ~90% branch coverage, and a subsequent regression (failing test or coverage drop) turns the job red.
**Why human:** `gh run list` shows no CI run newer than the pre-phase-8 `07-03` commit — the new `test_command` string has never actually executed in the real runner. All static wiring (workflow YAML, script content, local dry-run) is verified in this report; only the live CI execution is outside what this verifier can reach from the working tree, consistent with known_open_item #2 in the verification brief.

### Gaps Summary

No gaps found. All 14 merged must-have truths (ROADMAP's 5 phase-level success criteria plus the more granular per-plan must_haves from the 5 PLAN.md frontmatters) are verified against the actual codebase, most with live command execution rather than static inspection alone — including a real, reverted red-build reproduction of the `set -e` mechanism (QUAL-02's specific "proven, not inspected" requirement). The one open item is a CI-execution confirmation that cannot be obtained without pushing commits, which is explicitly expected to land as human verification rather than a gap per the verification brief. Two pre-existing, out-of-scope issues (the `SMTPRecipientsRefused` bug and stale `helpers.py` TODOs) were confirmed via `git blame` to predate this phase and are already tracked in the committed `08-REVIEW.md` — leaving them alone is judged consistent with this phase's QUAL-01..07 scope.

---

_Verified: 2026-08-05T13:51:09Z_
_Verifier: Claude (gsd-verifier)_
