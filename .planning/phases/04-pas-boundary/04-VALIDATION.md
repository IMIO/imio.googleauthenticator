---
phase: 4
slug: pas-boundary
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-31
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
| **Quick run command** | `bin/test -t test_pas_plugin -t test_setuphandlers -t test_subscribers` |
| **Full suite command** | `make test` (= `bin/test -t '!robot'`) |
| **Estimated runtime** | ~11 s full suite as of phase 3 (48 tests); ~6 s layer setup dominates |
| **Environment** | `base.cfg` `[testenv]` supplies a throwaway `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`; `[test]`'s `environment = testenv` bakes it into the generated `bin/test` |
| **Excluded** | `test_robot.py` — needs a real browser, excluded everywhere via `-t !robot` |
| **Isolation caveat** | `plone.testing` is intentionally unpinned (Plone 4.3 supplies 4.1.3). Browser tests here drive a testbrowser inside an `IntegrationTesting` layer, which commits; pinning 5.0.0 introduces the `TestIsolationBroken` guard and every browser test trips it. Do not add a testing approach that depends on that guard |

---

## Sampling Rate

- **After every task commit:** `bin/test -t test_pas_plugin -t test_setuphandlers -t test_subscribers`
- **After every plan wave:** `make test`
- **Before `/gsd-verify-work`:** full suite must be green
- **Max feedback latency:** ~11 s

---

## Per-Task Verification Map

| Req | Plan | Wave | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|-----|------|------|------------|-----------------|-----------|-------------------|--------|
| MFA-01 | TBD | TBD | TBD | A 2FA-enabled user cannot authenticate via `Authorization: Basic` — no session granted | integration (unit-style, via `_extractUserIds`) | `bin/test -t test_basic_auth_veto` | ⬜ pending |
| MFA-02 | TBD | TBD | TBD | The refusal serves no response body — the protected resource does not render inside the 302 | integration (`Browser`, redirect-following disabled) | `bin/test -t test_no_body_leak_on_2fa_redirect` | ⬜ pending |
| MFA-03 | TBD | TBD | TBD | This package's plugin is **first** among `IAuthenticationPlugin`, ordered explicitly by `movePluginsTop` | integration | `bin/test -t test_plugin_is_first_authenticator` | ⬜ pending |
| MFA-04 | TBD | TBD | TBD | One veto per credentials extractor — `__ac_name`/`__ac_password` form POST **and** `Authorization: Basic`, each granting no session | integration (unit-style, via `_extractUserIds`) | `bin/test -t test_form_post_veto -t test_basic_auth_veto` | ⬜ pending |
| COEX-08 | TBD | TBD | TBD | Challenge fires on **both** paths: `IChallengePlugin` for `Unauthorized`, `IPubBeforeCommit` subscriber for the HTTP-200 login POST. One test each — one hook does not cover both | integration | `bin/test -t test_challenge_fires_on_unauthorized -t test_pub_before_commit_fires_on_login_post` | ⬜ pending |
| — | TBD | TBD | TBD | An exception inside `authenticateCredentials` wipes the credentials dict and refuses, rather than falling through to `source_users` | integration | `bin/test -t test_exception_path_still_wipes_credentials` | ⬜ pending |
| DOC-01 | TBD | TBD | — | Zope-root admins architecturally out of reach, documented | see note below | `bin/test -t test_readme_documents_zope_root_limitation` | ⬜ pending |
| DOC-02 | TBD | TBD | — | Basic-auth consequence documented, naming the service-account alternative for scripts, WebDAV, FTP and XML-RPC | see note below | `bin/test -t test_readme_documents_basic_auth_consequence` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

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

All four are **new test surface** — no framework install, no new config, no fixture module.
`plone.app.testing` layers and `BaseTest` are already in place.

- [ ] `tests/test_pas_plugin.py` — add `test_basic_auth_veto`, `test_form_post_veto`, and the
      exception-path test (MFA-01, MFA-04, and success criterion 5), using the `_extractUserIds`
      unit idiom recorded in `04-RESEARCH.md`
- [ ] `tests/test_setuphandlers.py` — add `test_plugin_is_first_authenticator` (MFA-03)
- [ ] New `tests/test_challenge.py` (or extend `tests/test_subscribers.py` if that module
      already targets `IPubBeforeCommit`-style subscribers) — COEX-08's two independent paths
      plus MFA-02's body-emptiness assertion
- [ ] **Blocked on Open Question 2** — whether `plone.testing.z2.Browser` auto-follows redirects
      at this buildout's pinned version. The MFA-02 body-emptiness test cannot be written
      correctly until this is settled; the research flags it as needing a Wave 0 spike

---

## Open Questions Carried From Research

These are seeded here so they cannot be lost between research and validation sign-off.

| # | Question | Blocks | Resolution route |
|---|----------|--------|------------------|
| 1 | Must the login-POST path's final client-visible status be literally 200, or is 302-to-token-form acceptable? | COEX-08 test shape | Settle via the success-criterion test itself |
| 2 | Does `plone.testing.z2.Browser` auto-follow redirects at this pinned version? | MFA-02 test | Wave 0 spike before writing the body-emptiness test |
| 3 | Is explicit `IChallengePlugin` ordering needed in addition to `IAuthenticationPlugin` ordering? | MFA-03 scope | Research traced it as likely unnecessary (protocol-group isolation via unset `protocol`); confirm or discharge during planning |

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real WebDAV / FTP / XML-RPC client is unaffected (or, if `credentials_basic_auth` is deactivated, is affected exactly as documented) | DOC-02 / the basic-auth decision | The research found no live basic-auth dependence in `imio.dms.mail`, `server.dmsmail` or `industrialisation`, but the search was **not exhaustive across every iMio repo**. No test can prove absence of an external consumer | Before deploying, confirm with the iMio ops owners that no cron job, script, or integration authenticates against this site's `acl_users` over Basic auth. **NOT DONE** |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 s
- [ ] Open Questions 1–3 each resolved or explicitly carried with a rationale
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
