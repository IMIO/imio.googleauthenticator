---
phase: 04-pas-boundary
verified: 2026-07-31T00:00:00Z
status: passed
score: 5/5 must-haves verified (roadmap success criteria)
behavior_unverified: 0
overrides_applied: 0
human_verification:

  - test: "Confirm with iMio operations owners that no cron job, script, WebDAV mount, FTP client or XML-RPC integration authenticates against this Plone site's own acl_users over HTTP Basic Auth."
    expected: "No live external consumer of credentials_basic_auth against this site is found, or any found consumer is migrated to the service-account + ip_addresses_whitelist alternative before deployment."
    why_human: "04-02's own checkpoint decision (kept credentials_basic_auth active) rests on a three-repository grep search explicitly documented as non-exhaustive (04-RESEARCH.md Assumptions Log A1). No test in this repository can prove the absence of an external consumer -- this is exactly the residual risk 04-VALIDATION.md's 'Manual-Only Verifications' table records as 'NOT DONE', and README.rst's own DOC-02 section tells the operator to check this before deploying. It is also the concrete form of 04-02's `verification: backstop` truth ('no assertion in this repository can prove that a future third-party add-on has not displaced the plugin on a live site')."
---

# Phase 04: PAS Boundary Verification Report

**Phase Goal:** A user with 2FA enabled cannot obtain a session without the second factor via any
credentials extractor, the refusal leaks no protected content, and the challenge fires on both the
`Unauthorized` path and the HTTP-200 login POST.

**Verified:** 2026-07-31
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All five ROADMAP.md success criteria were checked against the actual codebase (not the summaries),
with the load-bearing tests re-run individually and two of the "proven load-bearing by mutation"
claims independently reproduced by editing `pas_plugin.py`, confirming the targeted tests go red,
then restoring the file to a byte-identical state and re-running the full suite green.

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One veto test per credentials extractor (form POST, `Authorization: Basic`), each asserting no session is granted | VERIFIED | `test_form_post_veto` and `test_basic_auth_veto` in `tests/test_pas_plugin.py` pass individually; each carries a non-vacuity control (same credentials DO authenticate with 2FA disabled). Independently reproduced the "proven load-bearing by mutation" claim: commenting out the credentials-wipe loop in `authenticateCredentials` made `test_form_post_veto`, `test_basic_auth_veto`, and `test_both_extractors_at_once_grant_no_session` all fail with the exact assertion messages the tests specify; restored, full suite green (67/67). |
| 2 | A test asserts the refusal serves no response body | VERIFIED | `test_no_body_leak_on_2fa_redirect` asserts `response.body == ''`, `content-length == '0'`, the seeded `SECRET-PAGE-MARKER` absent, and that the emptiness survives a later `setBody()` call (the lock). `test_no_body_leak_over_http` reproduces the same over a real HTTP round trip. Both pass. The MFA-02 root-cause fix (`response.body = ''` + `setHeader` + `setBody('', lock=1)`, since plain `setBody('')` is a no-op) is present at `pas_plugin.py:124-136` exactly as claimed. |
| 3 | Test asserts this package's plugin is first among `IAuthenticationPlugin`, ordered by `movePluginsTop` not an incidental `movePluginsDown` | VERIFIED | `setuphandlers.py:77` calls `pas.plugins.movePluginsTop(interface, [plugin.getId()])`; `grep -c movePluginsDown` returns 0 in that file. `test_plugin_is_first_authenticator` and `test_reapply_profile_keeps_plugin_first_and_unique` (displace-then-reinstall-then-recover) both pass. |
| 4 | Challenge fires on both paths, each with its own test: `IChallengePlugin` for `Unauthorized`, `IPubBeforeCommit` subscriber for the login-form POST | VERIFIED | `GoogleAuthenticatorPlugin.challenge()` (`pas_plugin.py:275-304`) is the `IChallengePlugin` half; `subscribers.redirect_pending_2fa` (`subscribers.py:40-74`), registered in `configure.zcml:76-79` for `ZPublisher.interfaces.IPubBeforeCommit`, is the login-POST half. Both share `send_2fa_redirect`. `test_challenge_fires_on_unauthorized` (real HTTP, Basic Auth, non-vacuity control proving the URL is genuinely protected) and `test_pub_before_commit_fires_on_login_post` (real HTTP, login-form POST, ZCML wiring parsed with `xml.dom.minidom`) both pass independently. |
| 5 | An exception inside `authenticateCredentials` wipes credentials and refuses rather than falling through to `source_users`; DOC-01 and DOC-02 written | VERIFIED | `test_exception_path_still_wipes_credentials` passes. Independently reproduced the second mutation claim: moved the credentials-wipe loop from ahead of the delegation loop to just after the `_mark_2fa_pending` call site, confirmed the test failed exactly as the summary describes (`{} != {'login': 'test-user', 'password': 'secret'}`), then restored the file (byte-identical, confirmed by diff) and re-ran the full suite green. DOC-01 and DOC-02 are both present in `README.rst` with the exact required facts (`Control_Panel`, `inituser`, "emergency user", `credentials_basic_auth`, `WebDAV`, `XML-RPC`, `ip_addresses_whitelist`, `enable_two_factor_authentication`), backed by `test_readme_documents_zope_root_limitation` and `test_readme_documents_basic_auth_consequence`, both passing. |

**Score:** 5/5 ROADMAP success criteria verified with reproduced behavioral evidence, not just presence.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/pas_plugin.py` | decide-only `authenticateCredentials`, `send_2fa_redirect`, `_mark_2fa_pending`, `challenge()`, `REQUEST_KEY_*` | VERIFIED | All present; `authenticateCredentials` has zero `RESPONSE`/`response.` references in its body; module constants and functions confirmed by direct read and by `bin/python -c "from ... import ..."`-style checks embedded in the plan (equivalent grep performed). |
| `src/imio/googleauthenticator/subscribers.py` | `redirect_pending_2fa` `IPubBeforeCommit` handler | VERIFIED | Present, reads `request.other` only (no `request.get`), calls `send_2fa_redirect`. |
| `src/imio/googleauthenticator/configure.zcml` | `IPubBeforeCommit` subscriber registration | VERIFIED | Present at lines 75-79, well-formed (parsed by `test_pub_before_commit_fires_on_login_post` via `xml.dom.minidom`, asserting exactly one matching `<subscriber>`). |
| `src/imio/googleauthenticator/setuphandlers.py` | `movePluginsTop`, split idempotency guard, dated basic-auth decision comment | VERIFIED | `_add_plugin` restructured exactly as described; the dated 2026-07-31 decision comment (kept `credentials_basic_auth` active) is present above `_add_plugin`. |
| `src/imio/googleauthenticator/tests/test_challenge.py` | body-leak, login-POST, forgery-guard, challenge tests | VERIFIED | All 7 methods present and pass individually (`test_no_body_leak_on_2fa_redirect`, `test_pub_before_commit_fires_on_login_post`, `test_request_flag_cannot_be_forged_from_the_query_string`, `test_no_body_leak_over_http`, `test_challenge_declines_without_the_flag`, `test_challenge_writes_nothing`, `test_challenge_fires_on_unauthorized`). |
| `src/imio/googleauthenticator/tests/test_pas_plugin.py` | five veto/exception tests | VERIFIED | `test_form_post_veto`, `test_basic_auth_veto`, `test_both_extractors_at_once_grant_no_session`, `test_empty_credentials_do_not_raise`, `test_exception_path_still_wipes_credentials` all present and pass; each absence-assertion carries a non-vacuity control. |
| `src/imio/googleauthenticator/tests/test_setuphandlers.py` | three ordering tests | VERIFIED | `test_plugin_is_first_authenticator`, `test_reapply_profile_keeps_plugin_first_and_unique`, `test_plugin_declares_no_challenge_protocol` all present and pass. |
| `README.rst` | DOC-01/DOC-02 sections, reconciled "ZMI -> acl_users" | VERIFIED | Both new sections present with required facts; "ZMI -> acl_users" reads as verification + `movePluginsTop`-based recovery, not a manual instruction. |
| `CHANGES.rst` | 1.0.0 (unreleased) entries for the phase | VERIFIED | Present; entries match what actually shipped (body-leak fix, two-hook redirect split, `movePluginsTop` re-assertion, credentials-wipe reordering, the basic-auth decision, the new README sections). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pas_plugin.py` (`_mark_2fa_pending`) | `subscribers.py` (`redirect_pending_2fa`) | `request.other[REQUEST_KEY_PENDING]` / `REQUEST_KEY_USER_ID`, shared constants | WIRED | Confirmed by reading both files; constants imported, not repeated as literals. |
| `configure.zcml` | `subscribers.redirect_pending_2fa` | `<subscriber for="ZPublisher.interfaces.IPubBeforeCommit" handler=".subscribers.redirect_pending_2fa"/>` | WIRED | Present and parses; asserted by a passing test that fails if the registration is ever deleted. |
| `subscribers.py` | `pas_plugin.send_2fa_redirect` | direct import, single shared redirect builder | WIRED | Confirmed by reading `subscribers.py` imports and the `challenge()`/`redirect_pending_2fa` bodies — both call the same function, no duplicated redirect logic. |
| `setuphandlers.py` | `acl_users.plugins` (PluginRegistry) | `movePluginsTop(interface, [plugin.getId()])`, run unconditionally inside the `listPluginTypeInfo()` loop, covering `IChallengePlugin` once `classImplements` declares it (Open Question 3) | WIRED | Confirmed: `test_challenge_fires_on_unauthorized` lands on the token form rather than `credentials_cookie_auth`'s `require_login`, empirically proving the existing generic ordering loop already covers the new interface with zero new code, as the summary claims. |

### Behavioral Spot-Checks / Mutation Reproductions

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase test suite | `bin/test -t '!robot'` | 67 tests, 0 failures, 0 errors | PASS |
| 16 named phase tests run individually | `bin/test -t <name>` x16 | 16 tests, 0 failures, 0 errors | PASS |
| Mutation 1: comment out credentials-wipe loop | edit `pas_plugin.py`, `bin/test -t test_form_post_veto -t test_basic_auth_veto -t test_both_extractors_at_once_grant_no_session` | all 3 fail with the exact non-vacuity assertion messages named in the tests' own docstrings | PASS (confirms load-bearing, not vacuous) |
| Mutation 2: move wipe to after `_mark_2fa_pending` | edit `pas_plugin.py`, `bin/test -t test_exception_path_still_wipes_credentials` | fails: `{} != {'login': 'test-user', 'password': 'secret'}` | PASS (confirms the reordering is load-bearing) |
| File restored after both mutations | `diff` against pre-edit backup | byte-identical | PASS |
| Full suite after restore | `bin/test -t '!robot'` | 67 tests, 0 failures, 0 errors | PASS |
| Debt-marker scan | `grep -nE "TBD|FIXME|XXX"` across all 10 phase-modified files | no matches | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| MFA-01 | 04-03 | 2FA-enabled user via `Authorization: Basic` grants no session | SATISFIED | `test_basic_auth_veto`, mutation-verified |
| MFA-02 | 04-01 | Refusal leaks no response body | SATISFIED | `test_no_body_leak_on_2fa_redirect`, `test_no_body_leak_over_http` |
| MFA-03 | 04-02 | Plugin explicitly first via `movePluginsTop`, re-asserted on reinstall | SATISFIED | `test_plugin_is_first_authenticator`, `test_reapply_profile_keeps_plugin_first_and_unique` |
| MFA-04 | 04-03 | One veto per extractor, including combined-extractor and empty-dict cases | SATISFIED | `test_form_post_veto`, `test_both_extractors_at_once_grant_no_session`, `test_empty_credentials_do_not_raise` |
| COEX-08 | 04-01, 04-03 | Challenge fires on both `Unauthorized` and login-POST paths | SATISFIED | `test_challenge_fires_on_unauthorized`, `test_pub_before_commit_fires_on_login_post` |
| DOC-01 | 04-04 | Zope-root boundary documented, CI-enforced | SATISFIED | `test_readme_documents_zope_root_limitation`; README section present with required facts |
| DOC-02 | 04-04 | Basic-auth consequence + service-account alternative documented, CI-enforced | SATISFIED | `test_readme_documents_basic_auth_consequence`; README section present with required facts |

No orphaned requirements: `REQUIREMENTS.md` maps exactly these 7 IDs to Phase 4, matching the union of `requirements:` frontmatter across all four plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `pas_plugin.py` | 270-273 | Dead `if credentials.get('extractor') != self.getId(): return None` followed by unconditional `return None` (pre-existing, per 04-REVIEW.md IN-01) | Info | No functional impact; cosmetic dead code, not introduced by this phase. |
| `pas_plugin.py` | 253-260 / `subscribers.py` | SEC-03's synchronous seed-decrypt check (`get_secret(user)`) does not cover a 2FA-enabled user who has never enrolled a secret + a broken encryption key — that combination's failure is deferred to `send_2fa_redirect` and surfaces as a generic, uncontrolled Zope exception page rather than SEC-03's intended clean refusal (04-REVIEW.md WR-01, WR-02) | Warning | Still fail-closed (no session is ever granted either way), and the same gap existed pre-phase-04 in a different call location — not a new bypass. Untested state combination, though. Not one of this phase's five ROADMAP success criteria per the human-provided context, so it does not block this phase, but it is unresolved technical debt worth tracking as a fast-follow. |

### Human Verification Required

1. **Confirm with iMio operations owners that no external consumer depends on HTTP Basic Auth against this Plone site's `acl_users`.**
   - **Test:** Ask the ops/deployment owners whether any cron job, script, WebDAV mount, FTP client, or XML-RPC integration authenticates against this site over `Authorization: Basic`.
   - **Expected:** No such consumer exists, or any found consumer is migrated to the service-account + `ip_addresses_whitelist` alternative documented in README.rst before this package is deployed with 2FA enabled for real users.
   - **Why human:** This is explicitly a `verification: backstop` truth in 04-02's plan frontmatter ("no assertion in this repository can prove that a future third-party add-on has not displaced the plugin on a live site" / the basic-auth non-exhaustiveness gap) and is listed as "NOT DONE" in `04-VALIDATION.md`'s own Manual-Only Verifications table. README.rst's DOC-02 section itself instructs the operator to do this before deploying. No code-level check can close this gap; it requires a human with visibility into iMio's other repositories and running systems.

### Gaps Summary

None of the five ROADMAP.md success criteria are unmet. All five were checked against the actual
code (not the SUMMARY.md narratives), with the relevant tests re-run individually and two of the
plans' "proven load-bearing by mutation" claims independently reproduced by editing the production
file, confirming the targeted assertions fail, then restoring it. The full suite is green (67/67)
both before and after those reproductions, and the working tree was left byte-identical to its
pre-verification state (confirmed via `diff` and `git status`).

The one item keeping this phase out of a clean `passed` is not a code gap: it is the operational,
human-only confirmation (no external Basic Auth consumer) that both `04-02-SUMMARY.md` and
`04-VALIDATION.md` already flag as outstanding and that this package's own README now tells the
deploying operator to perform. The WR-01/WR-02 code-review warning (a real, but narrow and already
fail-closed, gap in SEC-03's seed-decrypt check for a never-enrolled 2FA-enabled account) is noted
per the human-supplied context as not one of this phase's five success criteria, and is reported
here as a WARNING for tracking rather than a BLOCKER.

---

_Verified: 2026-07-31_
_Verifier: Claude (gsd-verifier)_
