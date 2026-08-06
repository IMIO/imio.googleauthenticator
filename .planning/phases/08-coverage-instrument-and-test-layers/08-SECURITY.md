---
phase: 08
slug: coverage-instrument-and-test-layers
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-06
---

# Phase 08 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: authored at plan time. All five plan files
(`08-01-PLAN.md` through `08-05-PLAN.md`) carried a `<threat_model>` block, so this
audit verified that each declared mitigation is present rather than building a
register retroactively from the implementation.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| developer or CI → build scripts | An exit code is the only signal a reviewer or a merge gate reads. A script that cannot report failure is a boundary that lies. | pass/fail verdict |
| buildout → shared eggs cache (`/srv/cache/eggs`) | A version pin change resolves a third-party artifact into the build. | third-party package contents |
| test layer → code under test | A layer that leaks committed state across tests can make a broken authorization guard look enforced. | ZODB state between tests |
| test assertion → install correctness | `test_product_is_installed` is the only assertion between a broken GenericSetup profile and a release with no PAS plugin registered. | install verdict |
| anonymous HTTP request → per-user 2FA-disable endpoint | An unauthenticated caller reaching this view could turn off a second factor. | authentication state |
| manager HTTP request → bulk enable/disable views and control-panel save handler | One request changes the 2FA state of every account in the site. | site-wide authentication state |
| coverage number → merge decision | The 90% threshold is a merge gate. A number produced by suppressed measurement reports safety it did not check. | coverage percentage |
| contributor commit → pre-commit hook | The hook is the last automated check before code enters history. A hook everyone bypasses has nothing behind it. | source changes |
| linter finding → the fix | Fixing versus suppressing decides whether the next contributor sees a problem or inherits it invisibly. | code quality signal |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-08-01 | Repudiation | `[test-coverage]` template in `base.cfg` | high | mitigate | `set -e` present in the template. A deliberately failing test was shown to make `bin/test-coverage` exit 1 and print no coverage total at all — reproduced independently twice, by the plan 08-01 executor and again by the phase verifier. | closed |
| T-08-02 | Tampering | `.coveragerc` measurement scope | medium | mitigate | `[run] source = src/imio/googleauthenticator`, `omit = */tests/*`, `branch = True`. Confirmed by report shape, not by percentage: the live report has `Branch`/`BrPart` columns and contains no `/tests/` rows. | closed |
| T-08-03 | Information disclosure | `htmlcov/` written by `coverage html` | low | accept | Build output in the working tree, rendering this repository's own public source. Now listed in `.gitignore` so it cannot be committed. | closed |
| T-08-SC | Tampering | `coverage` pin 4.2 → 5.5 in `test-4.3.cfg` | high | mitigate | `coverage = 5.5` pinned at `test-4.3.cfg:68`. Legitimacy verdict approved in `08-RESEARCH.md`: released 2021-02-28 from `github.com/nedbat/coveragepy`, `requires_python >=2.7,<4`, prebuilt cp27 wheels so no build-time network calls. | closed |
| T-08-04 | Elevation of privilege | test-layer isolation, install helper committing inside the layer | high | mitigate | `setUpPloneSite` in `src/imio/googleauthenticator/testing.py` performs the install. `BaseTest._install()` deleted along with all 16 call sites; zero remain. | closed |
| T-08-05 | Tampering | rewritten `test_product_is_installed` assertions | high | mitigate | Each assertion carries a non-vacuity control — broken one at a time, confirmed red, restored — recorded in `08-02-SUMMARY.md`. | closed |
| T-08-06 | Tampering | a production defect revealed by the install-mechanism change | high | mitigate | No test was skipped, deleted, weakened or inverted. Verified: zero `@unittest.skip`, `@skip`, or `expectedFailure` decorators anywhere in the test tree. | closed |
| T-08-07 | Information disclosure | `setUpPloneSite` → `setuphandlers.setupVarious` generating the URL-signing secret | low | accept | The generated `ska_secret_key` lives in the throwaway `DemoStorage` and is never printed. The phase changed when the profile runs, not what it stores or logs. | closed |
| T-08-08 | Elevation of privilege | integration-layer teardown leaving committed writes behind | high | mitigate | All 16 layer attributes moved to the functional layer; the integration layer definition deleted. Verified: no `INTEGRATION_TESTING` or `IntegrationTesting` reference anywhere in `src/`. | closed |
| T-08-09 | Tampering | the fix chosen for each revealed failure | high | mitigate | The isolation change revealed zero failures, so no repair choice arose. Gate confirmed: zero skip or expected-failure decorators in the test tree. | closed |
| T-08-10 | Repudiation | the record of what the isolation change revealed | medium | mitigate | The mechanical layer change was committed on its own (`4c6be92`) before any repair, so the revealed-failure list (empty) is recorded as evidence. | closed |
| T-08-11 | Denial of service | suite runtime under a per-test `DemoStorage` | low | accept | The per-test stack is what buys the isolation. Suite runs in 37.6 seconds; nothing was tuned for speed at the expense of isolation. | closed |
| T-08-12 | Elevation of privilege | anonymous guard in `browser/disable_two_factor_authentication.py` | high | mitigate | `test_anonymous_request_is_refused_and_mutates_nothing` asserts the guard's effect (member property unchanged) **and** the 401 status, and opens with an explicit precondition assertion so the unchanged-after check cannot pass vacuously. | closed |
| T-08-13 | Tampering | bulk 2FA-disable view and control-panel save handler | high | mitigate | `test_controlpanel.py` now holds 7 test methods covering the bulk disable path and the two previously untested save-handler branches, asserting the effect on a real user. | closed |
| T-08-14 | Repudiation | the 90% coverage number itself | high | mitigate | Gates check the inputs, not the output: zero coverage-exclusion pragmas anywhere in `src/` or `.coveragerc`; `--fail-under=90` intact at `base.cfg:92`; `.coveragerc` unchanged since plan 08-01. | closed |
| T-08-15 | Tampering | scope creep into deferred behaviour changes | medium | mitigate | The bulk-disable call in the save handler is still commented out at `browser/controlpanel.py:152`. No behaviour changed while tests were written next to it. | closed |
| T-08-16 | Denial of service | a wrong `test_command` breaking CI for every push | medium | accept | One-line change, reverted by one edit, and the failure would be loud and immediate. Ordered strictly after the 90% threshold was met. | closed |
| T-08-17 | Tampering | the lint gate's own config in `base.cfg` `[code-analysis]` | high | mitigate | `flake8-ignore`, `directory`, `flake8-extensions` and `pre-commit-hook` are byte-identical to their pre-phase values. The gate was cleared by fixing findings, not by narrowing what is checked. No per-file suppression added. | closed |
| T-08-18 | Tampering | deleting an import the linter calls unused but which carries a registration side effect | medium | mitigate | Each of the 9 deletions re-confirmed against the live tabulation rather than the stale pre-phase audit. Suite green (128 tests) and coverage gate green on the same commit. | closed |
| T-08-19 | Tampering | a whitespace fix landing inside a string literal | medium | accept | Mitigation partially violated, then accepted — see Accepted Risks Log entry R-08-01. | closed |
| T-08-20 | Repudiation | documentation that contradicts the tree | low | mitigate | `CLAUDE.md` and `.planning/codebase/TESTING.md` corrected in the same phase that made the old text wrong, including replacing the stale finding counts. | closed |
| T-08-21 | Elevation of privilege | the pre-commit hook running repository-controlled config on a developer machine | low | accept | Pre-existing and unchanged. `pre-commit-hook = True` predates this phase; the phase made the hook succeed rather than changing what it runs. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-08-01 | T-08-19 | Plan 08-05 trimmed trailing whitespace from three `>>> ` lines inside the `:example:` docstring block of `src/imio/googleauthenticator/adapter.py`. A docstring is a quoted string, so the mitigation's literal wording ("no change inside a quoted string") was crossed. The hazard that wording guards against — a whitespace change inside a translated message or a template string silently altering behaviour — cannot occur here: no doctests are collected anywhere. `grep` for `doctest`, `DocTestSuite` and `DocFileSuite` across `src/`, `base.cfg`, `test-4.3.cfg` and `setup.py` returns no matches, so those lines are never executed. Reverting them would reintroduce three `W291` findings and make `bin/code-analysis` exit non-zero, defeating the phase's stated goal (QUAL-06). | Chris | 2026-08-06 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-06 | 22 | 22 | 0 | /gsd-secure-phase 8 (orchestrator, ASVS L1) |

Audit method: register authored at plan time, ASVS level 1, blocking threshold `high`.
Classification was evidence-based at grep and command depth. Mitigations for T-08-01
(red build) and T-08-02/T-08-14 (coverage instrument) were additionally confirmed by
live command runs recorded in `08-VERIFICATION.md`, which scored 14 of 14 observable
truths verified. Per the ASVS L1 short-circuit rule, no separate auditor subagent was
spawned; the one non-clean threat (T-08-19) was resolved by explicit user acceptance.

---

## Out of Scope — Tracked Elsewhere

One security-relevant defect exists in code this phase touched but did not introduce:
`src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:112-113` catches
`SMTPRecipientsRefused` and re-raises the same exception type, which the only enclosing
handler (`except ValueError`) cannot catch. A rejected recipient address therefore
produces an unhandled error instead of the in-page failure message. It predates this
phase — `git log -S` places its first appearance in the phase 1 rename commit — and
plan 08-05 touched those lines only to delete an unused `as e` binding. It is a
robustness and error-disclosure concern, not one of this phase's declared threats.
Recorded as finding CR-01 in `08-REVIEW.md`.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-06
