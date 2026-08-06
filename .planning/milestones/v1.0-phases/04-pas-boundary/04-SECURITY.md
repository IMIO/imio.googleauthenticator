---
phase: 04
slug: pas-boundary
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-07-31
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: authored at plan time. All four plan files
(`04-01-PLAN.md` … `04-04-PLAN.md`) carry a `<threat_model>` block, so the audit
verified that each declared mitigation exists rather than building a register
retroactively. Full test suite green at audit time: `bin/test -t '!robot'` →
67 tests, 0 failures, 0 errors.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Anonymous HTTP request → PAS credential extraction | Any client can submit `__ac_name`/`__ac_password` form fields or an `Authorization: Basic` header to `acl_users` | Username and password |
| PAS authenticator chain → this plugin's veto | The plugin empties the shared credentials dict so later authenticators cannot grant a session; this only works while the plugin is first among `IAuthenticationPlugin` | Credentials dict (mutated in place) |
| Internal 2FA-pending signal (`request.other`) | Marks a request that passed the first factor and still owes a second one. Written only by `_mark_2fa_pending` after successful password delegation | Boolean flag plus user id |
| Refusal response body | The 302 redirect to the token form must carry no content from the protected resource | Rendered page content (must be empty) |
| Zope root (`/Control_Panel`, root `acl_users`) | Above any Plone site's `acl_users`; PAS's emergency user always wins. This plugin cannot reach it | Root administrator credentials |
| HTTP Basic Auth / WebDAV / FTP / XML-RPC clients | `credentials_basic_auth` remains active by recorded decision; those requests are vetoed, not blocked at extraction | Username and password |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-04-01 | Information Disclosure | `pas_plugin.send_2fa_redirect` | high | mitigate | `response.body = ''` plus `setHeader('content-length', '0')` at `pas_plugin.py:128-129` — not `setBody('')`, which is a no-op. Asserted by `test_no_body_leak_on_2fa_redirect` (`test_challenge.py:114`) against a real `HTTPResponse` with a seeded marker | closed |
| T-04-02 | Elevation of Privilege | `subscribers.redirect_pending_2fa` | high | mitigate | The pending signal is read from `request.other` only (`pas_plugin.py:97`, `:302`, `subscribers.py:71`). No `request.get(...)` or `request[...]` read of it exists in either module. Asserted by `test_challenge.py:190` | closed |
| T-04-03 | Tampering | `pas_plugin.send_2fa_redirect` | high | mitigate | `response.setBody('', lock=1)` at `pas_plugin.py:136` sets `_locked_body`, which `setBody` checks first, so a later subscriber cannot refill. Refill assertion inside `test_challenge.py:114` | closed |
| T-04-04 | Elevation of Privilege | `acl_users` cache manager | medium | accept | No cache manager exists on Plone 4.3's default `acl_users`. Accepted as dormant; the required warning comment sits at the credentials wipe (`pas_plugin.py:212-219`) so anyone attaching a cache manager later meets it in the code that depends on it. Logged as risk R-04-A below | closed |
| T-04-05 | Tampering | `subscribers.redirect_pending_2fa` | medium | mitigate | The handler body is three statements with no state write; `grep setMemberProperties\|setProperties` over `subscribers.py` and `pas_plugin.py` returns zero. Rationale recorded in the docstring at `subscribers.py:58-65`. See residual R-04-C | closed |
| T-04-06 | Denial of Service | `subscribers.redirect_pending_2fa` | medium | mitigate | The pending-flag guard is the handler's first statement (`subscribers.py:71-72`), so every unflagged request returns immediately; `send_2fa_redirect` returns `False` without touching the response when the stashed user id is missing or unresolvable (`pas_plugin.py:97-103`). The 67-test suite runs green with the subscriber live on every request. See residual R-04-D | closed |
| T-04-10 | Elevation of Privilege | `setuphandlers._add_plugin` | high | mitigate | `pas.plugins.movePluginsTop(interface, [plugin.getId()])` at `setuphandlers.py:77`, placed outside the object-creation guard so it re-runs on every profile application. Asserted by `test_plugin_is_first_authenticator` (`test_setuphandlers.py:156`) and `test_reapply_profile_keeps_plugin_first_and_unique` (`:181`), the latter deliberately displacing the plugin first as a non-vacuity control | closed |
| T-04-11 | Elevation of Privilege | `setuphandlers._add_plugin` | high | mitigate | `grep -c movePluginsDown setuphandlers.py` returns 0. Ordering is stated, not reached incidentally | closed |
| T-04-12 | Denial of Service | `setuphandlers._add_plugin` | high | mitigate | The `listPluginIds` membership guard at `setuphandlers.py:66-67` precedes the ordering call at `:77`, so `activatePlugin` is never called for an already-active plugin and `movePluginsTop` is never called for an inactive id. `test_setuphandlers.py:181` applies the profile twice and asserts exactly one entry with no exception | closed |
| T-04-13 | Denial of Service | `credentials_basic_auth` | high | mitigate | The extractor was NOT deactivated. The decision to keep it active is recorded in-repo at `setuphandlers.py:33-45`, dated 2026-07-31, stating the evidence and its non-exhaustiveness. Operator (Chris) confirmed on 2026-07-31 that no external consumer depends on it — `04-UAT.md` test 1 `result: pass`, `04-VALIDATION.md` Manual-Only row marked DONE. Pre-deploy instruction retained at `README.rst:314-317` | closed |
| T-04-14 | Tampering | `credentials_basic_auth` | medium | mitigate | Hazard did not materialise: no code anywhere in `src/` mutates `credentials_basic_auth`. The only occurrences are the decision comment and test docstrings. No `profiles/uninstall/` counterpart obligation was triggered | closed |
| T-04-15 | Elevation of Privilege | `GoogleAuthenticatorPlugin` class | medium | mitigate | The class declares no `protocol` attribute; the only `protocol` text in `pas_plugin.py` is docstring prose at `:289-290` describing `HTTPBasicAuthHelper`. `test_plugin_declares_no_challenge_protocol` (`test_setuphandlers.py:221`) asserts `not hasattr(plugin, 'protocol')` | closed |
| T-04-20 | Elevation of Privilege | `pas_plugin.authenticateCredentials` | high | mitigate | One veto assertion per extractor: form POST (`test_pas_plugin.py:196`), `Authorization: Basic` through the real `_extractUserIds` path (`:239`), and both at once (`:285`). Each runs a disabled-2FA non-vacuity control first. All three confirmed load-bearing by removing the credentials wipe and observing them fail | closed |
| T-04-21 | Elevation of Privilege | `pas_plugin.authenticateCredentials` | high | mitigate | Copy-then-wipe are the branch's first two statements (`pas_plugin.py:220-222`); first-factor delegation at `:237-238` uses the copy. `test_exception_path_still_wipes_credentials` (`test_pas_plugin.py:347`) confirmed load-bearing by relocating the wipe below the delegation loop and observing it fail | closed |
| T-04-22 | Information Disclosure | `pas_plugin.challenge` | high | mitigate | `challenge()` returns `send_2fa_redirect(...)` on the pending flag (`pas_plugin.py:302-304`), routing through the same body-clearing and locking path. Ordering is covered because `setuphandlers.py:62-77` loops every plugin-type interface the plugin provides, `IChallengePlugin` included. `test_challenge_fires_on_unauthorized` (`test_challenge.py:308`) asserts 302 to `@@google-authenticator-token` (not `login_form`) and an empty body, with an anonymous-request control proving the URL is genuinely protected | closed |
| T-04-23 | Elevation of Privilege | `pas_plugin.challenge` | high | mitigate | `pas_plugin.py:302` reads `request.other` only. `test_challenge_declines_without_the_flag` (`test_challenge.py:263`) includes the `request.form` forgery case at `:282-285` | closed |
| T-04-24 | Tampering | `pas_plugin.challenge` | medium | mitigate | The `challenge()` body is two statements. `test_challenge_writes_nothing` (`test_challenge.py:287`) asserts a memberdata property is unchanged across the call. See residual R-04-C | closed |
| T-04-25 | Denial of Service | `pas_plugin.authenticateCredentials` | low | mitigate | `login = credentials.get('login')` at `pas_plugin.py:186`. `test_pas_plugin.py:323` covers `{}`, `''` and `None` | closed |
| T-04-30 | Elevation of Privilege | `README.rst` (DOC-01) | high | mitigate | `README.rst:262-285` states the Zope-root boundary, its mechanism, PAS's emergency-user carve-out that no plugin can close, and the deployment action that follows. `test_generic.py:265` asserts the identifiers `Control_Panel`, `acl_users`, `inituser` and `emergency user`; proven load-bearing by deleting the section and observing the test fail | closed |
| T-04-31 | Repudiation | `README.rst` (DOC-01, DOC-02) | high | mitigate | Both documentation requirements carry automated identifier-based tests rather than a one-time manual check: `test_generic.py:265` (DOC-01) and `:297` (DOC-02). Both confirmed load-bearing by delete-the-section runs, with the file restored byte-identical | closed |
| T-04-32 | Denial of Service | `README.rst` (DOC-02) | medium | mitigate | `README.rst:308-313` names an alternative that already exists in code: a service account with `enable_two_factor_authentication` false plus a CIDR entry in `ip_addresses_whitelist`. Verified against the implementation — the whitelist check really is the first statement of `authenticateCredentials` (`pas_plugin.py:183-184`). Identifiers pinned by `test_generic.py:315-320` | closed |
| T-04-33 | Tampering | `README.rst` ZMI section | medium | mitigate | `README.rst:196-218` rewritten as a verification step plus the profile re-application recovery, retaining the ordered example and the "critical!" emphasis and adding the reason (the credentials wipe only blinds authenticators listed after this plugin). See residual R-04-E | closed |
| T-04-34 | Repudiation | `README.rst` (DOC-02) | low | mitigate | `README.rst:293-306` states the single branch that was taken ("kept **active**", dated); the other branch appears only as an explicitly counterfactual clause. `test_generic.py:327-333` asserts `index 0`, so the test goes red if the decision is reversed without a README update | closed |
| T-04-SC | Tampering | dependency declarations | low | accept | This phase installed nothing. `git diff --stat` over the phase range for `setup.py`, `test-4.3.cfg`, `base.cfg`, `requirements-4.3.txt` and `checkouts.cfg` is empty. Logged as risk R-04-B below | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-04-A | T-04-04 | A `ZCacheManager` attached to `acl_users` could serve a cached `_extractUserIds` result and skip the credentials veto. Plone 4.3's default `acl_users` has no cache manager, so `ZCacheable_getCache()` returns `None` and the authenticator loop always runs. Accepted as dormant, with a warning comment sited at the credentials wipe (`pas_plugin.py:212-219`) for anyone who attaches one later | Plan 04-01 threat model | 2026-07-31 |
| R-04-B | T-04-SC | Supply-chain risk from package installation. This phase installed nothing and touched no dependency declaration; `Products.PluggableAuthService` 1.11.3 and `Products.PluginRegistry` 1.4.1 were already resolved and pinned | Plan threat models 04-01 through 04-04 | 2026-07-31 |
| R-04-C | T-04-05, T-04-24 | `send_2fa_redirect` reaches `sign_user_data` → `get_or_create_secret` (`helpers.py:294-298`), which writes a memberdata seed for a 2FA-enabled user who has none yet. This is a seed mint, not second-factor control state, and its discard is fail-closed in both directions: after `transaction.abort()` on the challenge path the stored property is empty again, so `validate_user_data` recomputes a different signing key and rejects; on the committing subscriber path the seed persists but the user's app does not hold it, so the token still fails. It is not attacker-reachable — the pending flag is written only after successful first-factor delegation, into `request.other`, which form data and cookies cannot write. It does nonetheless literally breach plan 04-01's prohibition against ZODB writes from `send_2fa_redirect`, and no test pins the behaviour in either direction: `test_challenge_writes_nothing` uses a user who already has a seed, so it never exercises the writing branch. **Phase 5 (MFA-12) must not attach lockout or replay state to this call chain** — the write-free guarantee it inherits covers the `challenge()` and subscriber bodies, not everything reachable from them | Security audit, accepted as non-blocking | 2026-07-31 |
| R-04-D | T-04-06 | For a user with 2FA enabled but no stored seed, a broken or missing `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` raises inside `send_2fa_redirect` rather than synchronously in `authenticateCredentials`, producing an uncontrolled error page instead of a clean refusal. It is not the site-wide 500 the threat describes: the pending-flag guard returns for every request that has not already passed a password check by a 2FA-enabled user, so the blast radius is one login attempt, and no session is granted. Availability defect inside an already fail-closed posture. Tracked as findings WR-01 and WR-02 in `04-REVIEW.md`; the fix is an unconditional `check_encryption_key_is_usable()` call plus a test for the never-enrolled state | Security audit, accepted as non-blocking | 2026-07-31 |
| R-04-E | T-04-33 | `README.rst:254-255` still carries the legacy sentence "It's important that Google Authenticator comes as first in the ZMI -> acl_users -> Authentication." in the Notes section, stale framing left behind by the rewrite forty lines above it and pinned by no test. It is not an instruction to hand-order the plugin list, so it does not reopen T-04-33. One-line cleanup | Security audit, informational | 2026-07-31 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-31 | 24 | 24 | 0 | gsd-security-auditor (ASVS level 1, block_on high) |

Audit scope note: the four SUMMARY files contain no `## Threat Flags` section, so
their silence was not treated as an enumeration of new attack surface. The auditor
derived that surface from the phase diff instead and found exactly two new
externally reachable entry points — the `IPubBeforeCommit` subscriber
(`configure.zcml:76-78`) and `IChallengePlugin.challenge` (`pas_plugin.py:275`) —
both already covered by the register (T-04-02, T-04-03, T-04-05, T-04-06 and
T-04-22, T-04-23, T-04-24). No dependency, ZCML file or module beyond those.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-31
