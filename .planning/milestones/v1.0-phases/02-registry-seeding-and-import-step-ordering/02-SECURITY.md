---
phase: 02
slug: registry-seeding-and-import-step-ordering
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: 2026-07-29
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: both `02-01-PLAN.md` and `02-02-PLAN.md` carry a `<threat_model>` block
authored at plan time, so this run **verified existing mitigations** rather than building a
retroactive STRIDE register. ASVS level 1, blocking threshold `high`; per the secure-phase
short-circuit rule (`threats_open: 0` + `register_authored_at_plan_time: true` +
`asvs_level == 1`), L1 grep-depth verification is sufficient and no deeper auditor pass was
required.

---

## Trust Boundaries

Merged from both plans' `<threat_model>` blocks.

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| GenericSetup profile import → `plone.registry` | An import step whose ordering relative to `plone.app.registry` is undeclared reads records that do not exist yet. | Registry records (`ska_secret_key`, `globally_enabled`, `ip_addresses_whitelist`) |
| unauthenticated HTTP → `@@google-authenticator-token` / `@@reset-bar-code` → `validate_user_data` → `get_ska_secret_key` | An unauthenticated request reaches the key derivation. The lazy-mint branch this boundary was written for **no longer exists** (CR-02); the function is now a pure read. | Signed-URL signature, site-wide secret |
| PAS `authenticateCredentials` → `sign_user_data` → `get_ska_secret_key` | A request path that ends in `transaction.abort()` on `Unauthorized` (`pas_plugin.py:160`). No ZODB write remains on this path. | Site-wide secret, per-user seed |
| signed URL query string → `ska.validate_signed_request_data` | Attacker-supplied `auth_user` + signature validated against a key derived from three components; a component-boundary collision would let a signature minted in one context validate in another. | Signature, `auth_user` |
| memberdata `two_factor_authentication_secret` → the derivation | A per-user value of attacker-influenced *length* (via enrolment) is joined with a site-wide secret. | Per-user TOTP seed |
| `HTTP_User-Agent` → `get_browser_hash` → the derivation | An absent or unhashable `User-Agent` on an unauthenticated login path reaches a `len()` call. | Device-binding hash |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-02-01 | Elevation of Privilege | `helpers.get_app_settings()` — `forInterface` `KeyError` on a missing record | high | mitigate | `helpers.py` `get_app_settings()` is a bare `registry.forInterface(IGoogleAuthenticatorSettings)` — no `check=False`, no `omit=`, no wrapping try/except, so the `KeyError` propagates. Verified by grep: `check=False\|omit=` over `helpers.py` returns no match. With Phase 1's `_dont_swallow_my_exceptions = True` this renders a 500 rather than falling through to password-only login. | closed |
| T-02-02 | Repudiation | `GenericSetup.tool.getSortedImportSteps` — undeclared step order over a Python 2 `set` | medium | mitigate | `configure.zcml:50` declares `<depends name="plone.app.registry"/>`. Two assertions back it: `test_import_step_declares_registry_dependency` (`test_setuphandlers.py:44`, the real control — asserts the pre-sort `getImportStepMetadata(...)['dependencies']`) and `test_import_step_ordering` (`:71`, the outcome check, honestly self-limiting per its docstring). | closed |
| T-02-03 | Tampering | `plone.app.registry` `<records interface=...>` re-import replacing `ska_secret_key` with `u''` | medium | mitigate | `test_reapply_profile_does_not_reset_ska_secret_key` (`test_setuphandlers.py:128`) sets a distinctive literal, re-applies the profile, asserts equality against that same literal. | closed |
| T-02-04 | Denial of Service | lazy mint reachable from an unauthenticated request | low | accept | **Moot — attack surface deleted.** CR-02 removed the mint branch entirely; `get_ska_secret_key` is a pure read that raises `ValueError` on an empty key (fail-closed). Seeding moved to `setuphandlers._setup_secret_key()` at install time. No unauthenticated write path remains. | closed |
| T-02-05 | Tampering | mint write discarded by `transaction.abort()` on the PAS plugin path | low | accept | **Moot — same removal.** There is no longer any ZODB write in `get_ska_secret_key`, so nothing on the `authenticateCredentials` path can be lost to `transaction.abort()`. Confirmed: no assignment to `settings.ska_secret_key` anywhere in `helpers.py`. | closed |
| T-02-06 | Information Disclosure | the `ska_secret_key` reaching a log line or exception message | low | accept | No mint branch, no logging of the key, and the fail-closed `ValueError` text names only the remedy (`'ska_secret_key is not set; (re)install imio.googleauthenticator'`), not the value. Verified by grep for `logger.*ska_secret_key` / `print.*ska_secret_key` across `helpers.py`, `browser/` and `browser/forms/` — no match. See Accepted Risks R-02-01 for the pre-existing control-panel exposure. | closed |
| T-02-07 | Spoofing | `helpers.get_ska_secret_key` — unframed concatenation of `(user_secret, browser_hash, ska_secret_key)` | high | mitigate | Length-prefixed netstring join: `u''.join(u'{0}:{1}'.format(len(part), part) for part in (user_secret, browser_hash, ska_secret_key))`. A component-boundary shift changes the derived key. `test_get_ska_secret_key` asserts a fixture that provably collides under bare concatenation derives to the exact string `u'2:ab0:2:cd'`, plus `assertNotEqual` against the colliding fixture — so the mitigation cannot regress into a cosmetic reformat. | closed |
| T-02-08 | Denial of Service | `get_browser_hash` returning `None` under `len()` on the login path | medium | mitigate | `helpers.py` `except` branch returns `''`; `test_get_browser_hash` asserts both `assertEqual('', result)` and `assertIsNotNone(result)` (`test_helpers.py:195`). The guard is what stops a future edit reintroducing a fall-off-the-end `None`, which on this path would be an unauthenticated `TypeError`. | closed |
| T-02-09 | Denial of Service | a non-ASCII `str` component reaching a `u'...'` format → `UnicodeDecodeError` on the login path | low | accept | Accepted — see R-02-02. Every component is ASCII by construction (base32 seed, hex sha1 or `u''`, `unicode(uuid4())`). | closed |
| T-02-10 | Tampering | reopening the derivation after deployment | medium | accept | Accepted — see R-02-03. Recorded as the plan's one prohibition and as Task 1's `costly` reversibility rating. | closed |
| T-02-SC | Tampering | npm/pip/cargo installs (supply chain) | low | accept | No package-manager install added by either plan. Verified: `git diff master...HEAD --stat -- setup.py test-4.3.cfg requirements-4.3.txt` is empty, so there is no `[ASSUMED]`/`[SUS]` package to gate and no legitimacy checkpoint is required. Declared identically in both plans (duplicate ID, recorded once). | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `high` count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

**Blocking tally:** 2 `high` threats (T-02-01, T-02-07), both `mitigate`, both verified closed →
`threats_open: 0`.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-02-01 | T-02-06 | `browser/controlpanel.py` renders `ska_secret_key` into a form field. **Pre-existing**, untouched by this phase, and already a recorded Phase 3 Deferred Idea (canon secret-hygiene, breadcrumbed to `/gsd-secure-phase`). Not minted as a prohibition here. | Chris (plan D-06) | 2026-07-29 |
| R-02-02 | T-02-09 | Every derivation component is ASCII by construction: a base32 seed, a hex sha1 or `u''`, and a `unicode(uuid4())`. Phase 3's planned `v1$<fernet token>` is base64, also ASCII. Coercion deliberately not added — untested defensive code on a login path guarding a state no code path can produce. **Re-check when Phase 3 changes `user_secret`.** | Chris (02-02-PLAN) | 2026-07-29 |
| R-02-03 | T-02-10 | Reopening the `ska` derivation after deployment invalidates every signed URL in flight and every outstanding bar-code-reset link. Accepted now because nothing is deployed and no user is enrolled; a later change requires an explicit migration. Recorded as the plan's one prohibition. | Chris (02-02-PLAN) | 2026-07-29 |
| R-02-04 | T-02-04, T-02-05 | Both were accepted at plan time against the lazy-mint design. CR-02 subsequently **deleted** that branch, so the accepted risk is moot rather than live — recorded here only so the two IDs do not resurface as unexplained closures in a future audit. | Chris (CR-02) | 2026-07-29 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-29 | 11 | 11 | 0 | Claude (`/gsd-secure-phase 02`, L1 short-circuit — no auditor spawn) |

**Evidence run in this audit (not taken on trust from VERIFICATION.md):**

- `bin/test -t '!robot'` after a `.pyc` purge → `Ran 30 tests with 0 failures and 0 errors`
- `grep -n "check=False\|omit=" src/imio/googleauthenticator/helpers.py` → no match (T-02-01)
- `get_ska_secret_key` body read directly; netstring join present, no write branch, fail-closed `ValueError` (T-02-07, T-02-04/05)
- `grep -n "logger.*ska_secret_key\|print.*ska_secret_key"` over `helpers.py`, `browser/`, `browser/forms/` → no match (T-02-06)
- `configure.zcml:50` `<depends name="plone.app.registry"/>` present; both backing tests present at `test_setuphandlers.py:44` and `:71` (T-02-02)
- `git diff master...HEAD --stat` over `setup.py`, `test-4.3.cfg`, `requirements-4.3.txt` → empty (T-02-SC)
- `git diff master...HEAD --stat` over the four `ska`-derivation consumers (`pas_plugin.py`, `browser/forms/token.py`, `reset_bar_code.py`, `request_bar_code_reset.py`) → empty

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-29
