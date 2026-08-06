---
phase: 4
slug: pas-boundary
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-31
audited: 2026-07-31
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

Seeded by `plan-phase` from `04-RESEARCH.md` `## Validation Architecture`. Rows are keyed by
requirement, not task id — plans do not exist yet at seed time, and phase 3 showed a
task-keyed table duplicates every row when one task satisfies several requirements. The
plan-checker and `/gsd-validate-phase` fill in Plan/Wave/Threat-Ref columns once plans exist.

Phase 3's equivalent file was left as an unfilled `{REQ-XX}` stub and had to be reconstructed
by a later audit; this one is seeded with real commands so that does not repeat.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `plone.app.testing` (Plone 4.3 / Python 2.7) — **not** pytest. `unittest2` in test modules |
| **Config file** | `base.cfg` `[test]` part; pins in `test-4.3.cfg`. No `pytest.ini`/`pyproject.toml` exists and none should be added |
| **Quick run command** | `bin/test -t test_pas_plugin -t test_setuphandlers -t test_subscribers -t test_challenge` — `test_challenge` added at audit time; the seeded command omitted it and therefore missed 7 of this phase's tests |
| **Full suite command** | `make test` (= `bin/test -t '!robot'`) |
| **Measured runtime (2026-07-31, post-execution)** | Full suite 67 tests, 32.3 s wall clock. Quick run 30 tests, 24.4 s wall clock. Layer setup dominates so heavily that the quick run saves only ~8 s — the two-tier sampling rate below buys much less than it did at seed time, when the full suite was 48 tests in ~11 s |
| **Environment** | `base.cfg` `[testenv]` supplies a throwaway `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`; `[test]`'s `environment = testenv` bakes it into the generated `bin/test` |
| **Excluded** | `test_robot.py` — needs a real browser, excluded everywhere via `-t !robot` |
| **Isolation caveat** | `plone.testing` is intentionally unpinned (Plone 4.3 supplies 4.1.3). Browser tests here drive a testbrowser inside an `IntegrationTesting` layer, which commits; pinning 5.0.0 introduces the `TestIsolationBroken` guard and every browser test trips it. Do not add a testing approach that depends on that guard |

---

## Sampling Rate

- **After every task commit:** `bin/test -t test_pas_plugin -t test_setuphandlers -t test_subscribers -t test_challenge`
- **After every plan wave:** `make test`
- **Before `/gsd-verify-work`:** full suite must be green
- **Measured feedback latency:** 24.4 s quick run, 32.3 s full suite (both measured 2026-07-31 after execution, replacing the ~11 s seed-time estimate)

---

## Per-Task Verification Map

All rows verified by running each command individually on 2026-07-31, after the phase was
executed. Every command returned 1 test, 0 failures, 0 errors.

| Req | Plan | Wave | Threat Ref | Secure Behavior | Test Type | Automated Command | Test File | Status |
|-----|------|------|------------|-----------------|-----------|-------------------|-----------|--------|
| MFA-01 | 04-03 | 2 | T-04-20 | A 2FA-enabled user cannot authenticate via `Authorization: Basic` — no session granted | integration (unit-style, via `_extractUserIds`) | `bin/test -t test_basic_auth_veto` | `tests/test_pas_plugin.py:239` | ✅ green |
| MFA-02 | 04-01 | 1 | T-04-01, T-04-03 | The refusal serves no response body — the protected resource does not render inside the 302 | integration (direct `HTTPResponse`, plus a real HTTP round trip with redirect-following disabled) | `bin/test -t test_no_body_leak_on_2fa_redirect` | `tests/test_challenge.py:114` (and `test_no_body_leak_over_http` at `:229`) | ✅ green |
| MFA-03 | 04-02 | 1 | T-04-10, T-04-11, T-04-12 | This package's plugin is **first** among `IAuthenticationPlugin`, ordered explicitly by `movePluginsTop` | integration | `bin/test -t test_plugin_is_first_authenticator` | `tests/test_setuphandlers.py:156` (and `test_reapply_profile_keeps_plugin_first_and_unique` at `:181`) | ✅ green |
| MFA-04 | 04-03 | 2 | T-04-20 | One veto per credentials extractor — `__ac_name`/`__ac_password` form POST **and** `Authorization: Basic`, each granting no session | integration (unit-style, via `_extractUserIds`) | `bin/test -t test_form_post_veto -t test_basic_auth_veto` | `tests/test_pas_plugin.py:196`, `:239` (and `test_both_extractors_at_once_grant_no_session` at `:285`) | ✅ green |
| COEX-08 | 04-01 (subscriber half), 04-03 (challenge half) | 1 and 2 | T-04-06, T-04-22 | Challenge fires on **both** paths: `IChallengePlugin` for `Unauthorized`, `IPubBeforeCommit` subscriber for the login POST. One test each — one hook does not cover both | integration | `bin/test -t test_challenge_fires_on_unauthorized -t test_pub_before_commit_fires_on_login_post` | `tests/test_challenge.py:308`, `:158` | ✅ green |
| — | 04-03 | 2 | T-04-21 | An exception inside `authenticateCredentials` wipes the credentials dict and refuses, rather than falling through to `source_users` | integration | `bin/test -t test_exception_path_still_wipes_credentials` | `tests/test_pas_plugin.py:347` | ✅ green |
| DOC-01 | 04-04 | 2 | T-04-30 | Zope-root admins architecturally out of reach, documented | fact-presence assertion on identifiers, not prose (see note below) | `bin/test -t test_readme_documents_zope_root_limitation` | `tests/test_generic.py:265` | ✅ green |
| DOC-02 | 04-04 | 2 | T-04-32, T-04-34 | Basic-auth consequence documented, naming the service-account alternative for scripts, WebDAV, FTP and XML-RPC | fact-presence assertion on identifiers, not prose (see note below) | `bin/test -t test_readme_documents_basic_auth_consequence` | `tests/test_generic.py:297` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Non-vacuity.** Every row above was additionally shown to be load-bearing rather than
merely passing. The credentials-wipe tests were re-run with the wipe loop removed and with
the wipe relocated below the delegation loop; the plugin-ordering test was re-run with the
re-assert guard reverted; the two documentation tests were re-run with their README sections
deleted. All went red as expected and all files were restored byte-identical. These checks
are recorded in the plan summaries (`04-01-SUMMARY.md`, `04-02-SUMMARY.md`,
`04-03-SUMMARY.md`, `04-04-SUMMARY.md`) and were independently reproduced by the phase
verifier for the two credentials-wipe cases (`04-VERIFICATION.md`).

**On DOC-01 / DOC-02.** The research classified both as manual-only. Phase 3's audit rejected
that classification for its own DOC-03 and added a test, because the risk is not deletion but
a routine README rewrite quietly dropping the operator-facing paragraphs while the requirement
stays marked Complete. The same reasoning applies here, so both are seeded as automated with a
prose-independent assertion (assert on load-bearing facts, not wording). If the planner
concludes otherwise it must say so explicitly rather than silently demoting them to manual —
`test_readme_documents_the_deployment_key_and_its_failure_mode` is the existing precedent to
copy.

---

## Wave 0 Requirements

All four were **new test surface** — no framework install, no new config, no fixture module.
`plone.app.testing` layers and `BaseTest` were already in place. All four are complete.

- [x] `tests/test_pas_plugin.py` — `test_basic_auth_veto`, `test_form_post_veto` and
      `test_exception_path_still_wipes_credentials` added (MFA-01, MFA-04, and success
      criterion 5), using the `_extractUserIds` unit idiom recorded in `04-RESEARCH.md`.
      `test_both_extractors_at_once_grant_no_session` and `test_empty_credentials_do_not_raise`
      were added beyond the seeded list
- [x] `tests/test_setuphandlers.py` — `test_plugin_is_first_authenticator` added (MFA-03),
      plus `test_reapply_profile_keeps_plugin_first_and_unique` and
      `test_plugin_declares_no_challenge_protocol`
- [x] New `tests/test_challenge.py` created rather than extending `tests/test_subscribers.py` —
      COEX-08's two independent paths plus MFA-02's body-emptiness assertion, in both a
      direct-`HTTPResponse` and a real-HTTP form
- [x] **Open Question 2 discharged** (see the table below), so the MFA-02 body-emptiness test
      was written against a settled answer rather than a guess. No separate spike was needed —
      the answer was established while writing the test itself

---

## Open Questions Carried From Research

These were seeded here so they could not be lost between research and validation sign-off.
**All three are now resolved.**

| # | Question | Blocked | Answer (2026-07-31) |
|---|----------|---------|---------------------|
| 1 | Must the login-POST path's final client-visible status be literally 200, or is 302-to-token-form acceptable? | COEX-08 test shape | **302-to-token-form is the accepted shape.** The subscriber runs after the response body is already set and before the transaction commits, so it converts the HTTP-200 login POST into a redirect. `test_pub_before_commit_fires_on_login_post` (`tests/test_challenge.py:158`) asserts the browser lands on a signed `@@google-authenticator-token` URL carrying `auth_user=` and `signature=`, and parses `configure.zcml` with `xml.dom.minidom` to prove the subscriber registration is present and the file is well-formed |
| 2 | Does `plone.testing.z2.Browser` auto-follow redirects at this pinned version? | MFA-02 test | **Yes, it follows redirects by default** (`zope.testbrowser` 3.11.1 / `mechanize` 0.2.5). Disabling it needs both `mech_browser.set_handle_redirect(False)` and `raiseHttpErrors = False`, and those switches are only honoured on the `Browser.open()` path — `Browser.getControl(...).click()` routes through `_clickSubmit()`, which re-raises `mechanize.HTTPError` unconditionally and never consults `raiseHttpErrors`. `test_no_body_leak_over_http` (`tests/test_challenge.py:229`) therefore submits URL-encoded POST data through `Browser.open()` directly. The finding is recorded in that test's docstring so it is not rediscovered |
| 3 | Is explicit `IChallengePlugin` ordering needed in addition to `IAuthenticationPlugin` ordering? | MFA-03 scope | **Not needed.** Resolved empirically during plan 04-03: the ordering loop added in plan 04-02 (`setuphandlers.py:62-77`) iterates every plugin-type interface the plugin declares, so once `classImplements` added `IChallengePlugin`, that interface was covered with no extra call. The related invariant — that the class declares no `protocol` attribute, which would move it into `HTTPBasicAuthHelper`'s protocol group and hand WebDAV, FTP and XML-RPC clients an HTML redirect instead of a 401 — is pinned by `test_plugin_declares_no_challenge_protocol` (`tests/test_setuphandlers.py:221`) |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real WebDAV / FTP / XML-RPC client is unaffected (or, if `credentials_basic_auth` is deactivated, is affected exactly as documented) | DOC-02 / the basic-auth decision | The research found no live basic-auth dependence in `imio.dms.mail`, `server.dmsmail` or `industrialisation`, but the search was **not exhaustive across every iMio repo**. No test can prove absence of an external consumer | Before deploying, confirm with the iMio ops owners that no cron job, script, or integration authenticates against this site's `acl_users` over Basic auth. **DONE** — confirmed by the operator (Chris) on 2026-07-31 during UAT for this phase; recorded as test 1 `result: pass` in `04-UAT.md` |

---

## Validation Audit 2026-07-31

| Metric | Count |
|--------|-------|
| Requirements audited | 8 (7 requirement IDs plus the exception-path behaviour, which carries no ID) |
| Covered | 8 |
| Partial | 0 |
| Missing | 0 |
| Gaps escalated to manual-only | 0 |
| Manual-only entries | 1 (pre-existing, now confirmed done) |

Method: each `Automated Command` in the map above was run individually against the executed
codebase. All returned 1 test, 0 failures, 0 errors. No test needed to be written, so the
gap-filling subagent was not run. The full suite stands at 67 tests, 0 failures.

Three things were corrected rather than merely ticked:

1. The quick-run command omitted `test_challenge`, the module holding 7 of this phase's tests.
   It now includes it.
2. The runtime figures were seed-time estimates from phase 3 (~11 s, 48 tests). Measured
   values replace them: 32.3 s full suite, 24.4 s quick run.
3. Every row said `⬜ pending` with `TBD` in the Plan, Wave and Threat Ref columns. Those are
   now filled from the executed plans and the threat register in `04-SECURITY.md`.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — all four Wave 0 items complete, zero MISSING
- [x] No watch-mode flags — `zope.testrunner` has no watch mode; `bin/test` is one-shot
- [ ] Feedback latency < 30 s — **not met for the full suite.** Measured 32.3 s wall clock
      (67 tests), over the 30 s target. The quick run is 24.4 s and does meet it. Layer setup
      dominates both, so the gap will widen as tests are added. Recorded rather than ticked;
      it is a target miss, not a coverage gap, and does not affect `nyquist_compliant`
- [x] Open Questions 1–3 each resolved or explicitly carried with a rationale — all three
      resolved with evidence, recorded in the table above
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** validated 2026-07-31 — every phase requirement has automated verification that
runs green, and each test was additionally shown to fail when the behaviour it guards is
removed.
