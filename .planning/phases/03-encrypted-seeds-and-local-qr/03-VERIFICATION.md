---
phase: 03-encrypted-seeds-and-local-qr
verified: 2026-07-30T15:00:00Z
status: human_needed
score: 20/21 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "ROADMAP Phase 3 success criterion 4 — enrol with a real TOTP authenticator app (Google Authenticator, FreeOTP, or similar) and log in end to end, against a seed that is 160 bits of os.urandom."
    expected: "QR renders and is scannable at the size the form displays it (data: URI, no outbound network request visible in the browser's network panel); the otpauth:// label reads as <username>@<domain>; the 6-digit code the app shows is accepted at enrollment; the same app's current code, after logout and a fresh username/password login, is accepted at @@google-authenticator-token and reaches the site as the authenticated user."
    why_human: "Requires a physical/virtual TOTP authenticator app scanning a real QR code rendered by a running bin/instance and a live login round trip — not executable by an automated agent. Deliberately deferred to end-of-phase per workflow.human_verify_mode=end-of-phase (03-03-PLAN.md Task 2's <verify><human-check>); 03-03-SUMMARY.md confirms it was not performed during execution. helpers.get_totp's round trip in 03-01's test_seed_encryption_round_trip proves the seed survives Fernet encryption and that onetimepass accepts a computed token — it does not prove what a phone parses, displays, or accepts as a fresh code."
---

# Phase 3: Encrypted Seeds and Local QR Verification Report

**Phase Goal:** A TOTP seed is unreadable from the ZODB, never transmitted to an external
service, and never silently downgraded to plaintext — and adding `cryptography` cannot
break every login on the site through `ipaddress` module shadowing.

**Verified:** 2026-07-30T15:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

All code-level, machine-checkable truths were independently re-derived from the actual
source and re-run (not taken from SUMMARY.md prose). The only outstanding item is the one
ROADMAP success criterion the phase itself flags as requiring a human with a physical
authenticator app.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SEC-01: stored secret is `v1$<fernet-token>`, no plaintext seed appears in the ZODB/log/exception, key appears in none of those or the registry | ✓ VERIFIED | `helpers.py:86-118` (`encrypt_seed`/`decrypt_seed`); independently ran `bin/test -t test_seed_encryption_round_trip` → 1 test, 0 failures. `get_encryption_key()`/`_get_fernet()` never interpolate the key value into any message (`helpers.py:45-83`). |
| 2 | SEC-02: key read fresh from `os.environ` every call, never module-scope; `str`/`unicode` coerced to bytes; no-leak error message | ✓ VERIFIED | `helpers.py:45-55` reads `os.environ.get(ENV_VAR_NAME)` inside the function body (no module-level cache); `.encode('ascii')` coercion at lines 72-73, 94-95, 111-112; error messages at lines 70/83 name only `ENV_VAR_NAME`. Independently ran `bin/test -t test_encryption_key_is_read_per_call` → 1 test, 0 failures. |
| 3 | SEC-03: enrollment, validation, bulk-enable (both callers), and user creation all fail closed (refuse) with key unset or garbage — never downgraded to plaintext or password-only | ✓ VERIFIED | `helpers.py:564-584` (`enable_two_factor_authentication_for_users` re-raises `ValueError` explicitly rather than swallowing); `controlpanel.py:113-130` and `enable_two_factor_authentication_for_all_users.py:25-41` both catch `ValueError` and show an `'error'` status message, never an unconditional success. Independently ran `bin/test -t test_login_is_refused_when_seed_key_is_broken` → 1 test, 0 failures. Full suite (below) also covers bulk-enable and user-creation fail-closed tests. |
| 4 | SEC-04: every ciphertext starts with `v1$`; `decrypt_seed` raises `ValueError` on missing/unknown prefix | ✓ VERIFIED | `helpers.py:100-108` — explicit `startswith(CIPHERTEXT_VERSION_PREFIX)` check before any decrypt attempt. |
| 5 | SEC-05: QR renders in-process, `data:image/png;base64,` URI, no `chart.googleapis.com`, no subprocess | ✓ VERIFIED | `helpers.py:198-214` (`get_barcode_image`) — `qrcode.make()` + `io.BytesIO()` + `base64.b64encode`, no network/subprocess calls. `grep -rc "googleapis\|subprocess\|os.system\|os.popen\|commands\." src/imio/googleauthenticator/helpers.py` → 0 for all. |
| 6 | SEC-06: seeds are 160 bits `os.urandom`, 32-char unpadded base32 | ✓ VERIFIED | `helpers.py:182-195` (`generate_secret`) — `base64.b32encode(os.urandom(20))`; 20 bytes = 160 bits, exact multiple of base32's 5-byte block. |
| 7 | SEC-07: repo owns exactly one of the four declaration sites (`[testenv]`); CI inherits transitively; `[instance]` carries no entry (not even a placeholder) | ✓ VERIFIED | `grep -c "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" base.cfg` → exactly `1`. Direct inspection of `base.cfg` `[instance]` (lines ~39-45) confirms no key entry; `[testenv]` (line 55) carries the throwaway key. `README.rst` documents `[instance]`/Puppet ownership by the deployment. |
| 8 | SEC-08: missing key logs CRITICAL once at boot; never raises from import/ZCML/handler | ✓ VERIFIED | `subscribers.py` (30 lines) — `if not get_encryption_key(): logger.critical(...)`, no `raise`/`try`/`except` anywhere in the module (matches 03-02-SUMMARY's AST-walk evidence of 0 `Raise`/`TryExcept`/`TryFinally` nodes). Registered in `configure.zcml` for `zope.processlifetime.IProcessStarting`; file still parses as well-formed XML (confirmed by direct read). |
| 9 | BUG-05: `py2-ipaddress` replaced by `ipaddress==1.0.23`; unicode coercion at **all three** call sites (not the two originally assumed) | ✓ VERIFIED | `grep -c "py2-ipaddress" setup.py test-4.3.cfg` → 0/0; `setup.py`/`test-4.3.cfg` carry `ipaddress==1.0.23`/`ipaddress = 1.0.23`. Read `helpers.py:604-718` directly: `_to_unicode_ip()` helper (line 604), and all three call sites (`ip_address(_to_unicode_ip(proxies[0]))` line 645, `ip_address(_to_unicode_ip(ip))` line 666, `ip_network(_to_unicode_ip(net))` line 715) coerce before the call. |
| 10 | BUG-02: `redirect_url` bound on all three reachable branches of `SetupForm.handleSubmit`; empty token short-circuits before any redirect; closed by regression test with **no production code change** | ✓ VERIFIED | `git log --oneline HEAD~20..HEAD -- .../user_setup.py` → no commits in this phase touch the file; `git diff` against pre-phase HEAD is empty (confirmed by history). `tests/test_user_setup.py` (200 lines) exists with `test_handleSubmit` driving all four scenarios. |
| 11 | BUG-03: bar-code reset token comparison is constant-time via one shared helper at **both** call sites; refuses empty/absent tokens; no `TypeError` across `str`/`unicode` | ✓ VERIFIED | `helpers.py` — `validate_bar_code_reset_token` (falsy-refuse, `.encode('ascii')` coercion inside `try`/`except UnicodeEncodeError`, `compare_digest`). `reset_bar_code.py` — both `handleSubmit` (line ~104) and `updateFields` (line ~154) call the helper; `grep -rn -E "bar_code_reset_token *(==|!=)" src/` (excluding tests) → no matches. |
| 12 | DOC-03: `README.rst` documents the variable, generation, all three failure consequences (enrollment/login/account creation), per-ZEO-client scope, `InvalidToken`-with-no-ZODB-evidence, `[instance]` ownership, and the open `industrialisation` Puppet dependency | ✓ VERIFIED | Direct read of `README.rst` confirms `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`, `InvalidToken`, `concat::fragment`, `industrialisation`, `server.dmsmail`, `export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`, and "not deployable" all present. |
| 13 | `IMIO_GA_SEED_KEY` (stale plan literal) does not appear in any shipped artifact | ✓ VERIFIED | `git grep -n IMIO_GA_SEED_KEY -- src base.cfg README.rst CHANGES.rst setup.py test-4.3.cfg` → confirmed no matches by direct inspection of each named file; the locked name `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` is used consistently throughout. |
| 14 | ROADMAP SC1: newly enrolled seed reads as `v1$<fernet-token>`, no plaintext substring anywhere | ✓ VERIFIED | Same evidence as truth #1; `assertNotIn(seed, stored)` assertion present and passing in `test_seed_encryption_round_trip`. |
| 15 | ROADMAP SC2: two tests assert login refused with key unset and with key garbage, at enrollment and validation | ✓ VERIFIED | `test_seed_encryption_fails_closed` (helpers-level) and `test_login_is_refused_when_seed_key_is_broken` (PAS-level) both exist and independently re-run green. |
| 16 | ROADMAP SC3: QR renders in-process, no request to `chart.googleapis.com`, no subprocess argv | ✓ VERIFIED | Same evidence as truth #5. |
| 17 | ROADMAP SC4: real authenticator app enrolls and logs in end to end | ⚠️ Not machine-verifiable — see Human Verification | Deliberately deferred per `workflow.human_verify_mode=end-of-phase`; not a gap. |
| 18 | ROADMAP SC5: `py2-ipaddress` gone, `ipaddress==1.0.23` pinned, unicode coercion at all three call sites | ✓ VERIFIED | Same evidence as truth #9. |
| 19 | Full test suite green, whole phase | ✓ VERIFIED | Independently ran `bin/test -t '!robot'` → **41 tests, 0 failures, 0 errors** (matches orchestrator's independent claim; re-confirmed by this verifier, not merely trusted). |
| 20 | Requirements coverage: all 12 phase requirement IDs (SEC-01..08, BUG-02, BUG-03, BUG-05, DOC-03) accounted for, none orphaned | ✓ VERIFIED | `REQUIREMENTS.md` marks all 12 `Complete` under Phase 3; plan frontmatter requirements across 03-01 (7) + 03-02 (3) + 03-03 (2) = 12, matching exactly. |
| 21 | No debt-marker or anti-pattern blockers introduced by this phase | ✓ VERIFIED (with 2 pre-existing findings noted, not new) | See Anti-Patterns section below. |

**Score:** 20/21 truths verified (1 explicitly and correctly deferred to human verification, not a gap)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/helpers.py` | Per-call key read, fail-closed Fernet wrapper, `v1$` envelope, 160-bit seed, in-process QR, unicode-coerced `ipaddress` calls, non-swallowing bulk-enable loop, constant-time reset-token comparison | ✓ VERIFIED | All present, read directly, all wired. |
| `setup.py` | `install_requires` with cryptography/ipaddress/qrcode/Pillow, without the two removed distributions | ✓ VERIFIED | `cryptography==3.3.2`, `ipaddress==1.0.23`, `qrcode==6.1`, `Pillow` present; `py2-ipaddress`/`rebus` absent (grep count 0). |
| `test-4.3.cfg` | `[versions]` pins for cryptography/cffi/ipaddress/qrcode | ✓ VERIFIED | All four pinned. **Pillow is not pinned here** — see Anti-Patterns/Quality note (WR-03, carried from code review). |
| `base.cfg` | `[testenv] IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`, `[instance]` untouched | ✓ VERIFIED | Confirmed by direct read; count exactly 1 in the whole file. |
| `browser/controlpanel.py` | Save handler reports failure instead of "Changes saved." on bulk-enrollment failure | ✓ VERIFIED (wired) — see WARNING below | `except ValueError` present, error status shown, "Changes saved." suppressed on that path. However `applyChanges(data)` still runs unconditionally, persisting `globally_enabled=True` to the registry even when enrollment failed — see WARNING. |
| `browser/enable_two_factor_authentication_for_all_users.py` | Same failure-reporting shape | ✓ VERIFIED | `except ValueError` present, error status shown. |
| `src/imio/googleauthenticator/subscribers.py` | `on_process_starting` — SEC-08 CRITICAL log | ✓ VERIFIED | 30 lines (≤ 40 required), no raise/try/except. |
| `src/imio/googleauthenticator/configure.zcml` | `IProcessStarting` subscriber registration | ✓ VERIFIED | Present, file parses. |
| `tests/test_helpers.py` | `TestSeedEncryption`, `TestBarCodeResetToken`, etc. | ✓ VERIFIED | All 17 test methods present, independently re-run subset green. |
| `tests/test_pas_plugin.py` | `test_login_is_refused_when_seed_key_is_broken` | ✓ VERIFIED | 193 lines (≥ 160 required); independently re-run green. |
| `tests/test_subscribers.py` | `TestOnProcessStarting` | ✓ VERIFIED | 108 lines (≥ 90 required). |
| `tests/test_user_setup.py` | `TestSetupForm.test_handleSubmit` | ✓ VERIFIED | 200 lines (≥ 90 required); `user_setup.py` untouched. |
| `README.rst` | Seed-key documentation subsection | ✓ VERIFIED | Confirmed present and complete. |
| `CHANGES.rst` | Phase 3 changelog entries | ✓ VERIFIED | Confirmed present (`IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`, re-enrol language, `[chris-adam]` entries). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `helpers.py` | `os.environ` | `get_encryption_key()` reads `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` fresh every call | ✓ WIRED | Confirmed no module-scope cache; read happens inside the function body. |
| `helpers.py` | memberdata `two_factor_authentication_secret` | `generate_secret` stores `encrypt_seed(plaintext)` | ✓ WIRED | Confirmed at `helpers.py:190-194`. |
| `pas_plugin.py` | `helpers.decrypt_seed` | `authenticateCredentials → sign_user_data → get_or_create_secret → decrypt_seed`; `_dont_swallow_my_exceptions=True` | ✓ WIRED | Confirmed `sign_user_data` import and call at `pas_plugin.py:160`, flag at line 71. |
| `configure.zcml` | `subscribers.py` | `<subscriber for="zope.processlifetime.IProcessStarting" handler=".subscribers.on_process_starting"/>` | ✓ WIRED | Confirmed present in file. |
| `base.cfg [testenv]` | `bin/test`'s process environment | `[test] environment = testenv` | ✓ WIRED | Confirmed section present; independently re-ran full suite which depends on this wiring and passed. |
| `reset_bar_code.py` | `helpers.validate_bar_code_reset_token` | both `handleSubmit` and `updateFields` call sites | ✓ WIRED | Confirmed both call sites route through the helper. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Seed encryption round trip (SEC-01/04/05/06) | `bin/test -t test_seed_encryption_round_trip` | 1 test, 0 failures, 0 errors | ✓ PASS |
| Login refused with broken key (SEC-03 validation) | `bin/test -t test_login_is_refused_when_seed_key_is_broken` | 1 test, 0 failures, 0 errors | ✓ PASS |
| Per-call key read, not module-scope (SEC-02) | `bin/test -t test_encryption_key_is_read_per_call` | 1 test, 0 failures, 0 errors | ✓ PASS |
| Whole phase suite | `bin/test -t '!robot'` | **41 tests, 0 failures, 0 errors** | ✓ PASS |
| No outbound QR call / no subprocess in `helpers.py` | `grep -c "chart.googleapis.com"`, `grep -cE "subprocess\|os\.system\|os\.popen\|commands\."` | both 0 | ✓ PASS |
| `[instance]` carries no seed-key entry | `grep -c "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" base.cfg` | exactly 1 | ✓ PASS |
| `user_setup.py` untouched by BUG-02 closure | `git log HEAD~20..HEAD -- .../user_setup.py` | no phase-3 commits touch the file | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention exists in this repository and no plan/summary references a probe script; this phase's verification is a Plone/`bin/test`-based buildout project, not a probe-driven migration/tooling phase. Skipped — no applicable probes.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|--------------|--------|----------|
| SEC-01 | 03-01 | Seeds Fernet-encrypted at rest, no plaintext ever written | ✓ SATISFIED | `encrypt_seed`/`generate_secret`, test round trip |
| SEC-02 | 03-01 | Key read per-call, never in ZODB/log/exception | ✓ SATISFIED | `get_encryption_key`, `test_encryption_key_is_read_per_call` |
| SEC-03 | 03-01 | Enrollment/validation fail closed, never downgraded | ✓ SATISFIED | fail-closed wrappers + 4 dedicated tests |
| SEC-04 | 03-01 | `v1$` version prefix | ✓ SATISFIED | `decrypt_seed` prefix check |
| SEC-05 | 03-01 | In-process QR, no external service, no subprocess argv | ✓ SATISFIED | `get_barcode_image`, no-googleapis/no-subprocess greps |
| SEC-06 | 03-01 | 160-bit `os.urandom` seeds | ✓ SATISFIED | `generate_secret` |
| SEC-07 | 03-02 | Env var present/documented in all 4 places; repo owns 1 | ✓ SATISFIED | `base.cfg` count, README, test_seed_key_is_present |
| SEC-08 | 03-02 | Missing key logs CRITICAL, never raises | ✓ SATISFIED | `subscribers.py`, AST-walk test |
| BUG-02 | 03-03 | `redirect_url` always bound | ✓ SATISFIED (non-reproduction confirmed + regression test) | `test_user_setup.py`, empty diff on `user_setup.py` |
| BUG-03 | 03-03 | Constant-time reset-token comparison | ✓ SATISFIED | `validate_bar_code_reset_token`, both call sites |
| BUG-05 | 03-01 | `ipaddress==1.0.23`, unicode coercion (3 call sites) | ✓ SATISFIED | `_to_unicode_ip`, all 3 sites confirmed |
| DOC-03 | 03-02 | Seed-key deployment documentation | ✓ SATISFIED | `README.rst` section |

No orphaned requirements: all 12 IDs REQUIREMENTS.md maps to Phase 3 appear in a plan's `requirements` frontmatter (03-01: 7, 03-02: 3, 03-03: 2 = 12).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `browser/controlpanel.py` | 137 | `applyChanges(data)` runs unconditionally, persisting `globally_enabled=True` to the registry even when the bulk-enrollment `except ValueError` branch fires and reports failure | ⚠️ WARNING (carried from 03-REVIEW.md WR-01) | Not a fail-closed *crypto* violation and not a false-success status message (the must-have text is satisfied literally), but an admin who sees the error and later re-checks the control panel finds the checkbox already "on" — a partial-persistence edge the review correctly flagged as worth a follow-up fix. |
| `helpers.py` | 564-584 | `enable_two_factor_authentication_for_users` re-raises *any* `ValueError` from `get_or_create_secret`, whether from a systemically broken key or a single corrupt/foreign ciphertext on one user's row, aborting the whole batch | ⚠️ WARNING (carried from 03-REVIEW.md WR-02) | Does not violate the stated must-have (which only requires the `ValueError` to escape rather than be swallowed), but means one bad row can abort enrollment for every other user in a large bulk-enable run. |
| `test-4.3.cfg` | — | `Pillow` (a hard runtime dependency of the new QR path, per `qrcode.make()`'s default `PilImage` factory) has no `[versions]` pin, unlike every sibling dependency (`cryptography`/`cffi`/`ipaddress`/`qrcode`) this phase added | ⚠️ WARNING (carried from 03-REVIEW.md WR-03) | Violates the project's own documented convention ("All pins live in test-4.3.cfg [versions]"). Does not currently break anything (build/tests green), but risks a future `make buildout` resolving a Pillow ≥ 7.0 release that drops Python 2.7 support. |
| `helpers.py` | 191, 294 | Commented-out `# logger.debug(secret)` / `# logger.debug('secret: ...')` lines, pre-existing, inside the two functions this phase's "no seed leakage" requirement is about | ℹ️ INFO (carried from 03-REVIEW.md IN-02) | Inert today; a standing invitation to leak the plaintext seed if re-enabled during future debugging. |
| `helpers.py` | 225, 247, 427, 455 | Pre-existing `# TODO: Return hashed version...` / `:FIXME:` markers, dated to the original 2015 upstream commit, in a file this phase modifies | ℹ️ INFO | Predates this phase by over a decade; the plan's own `<action>` explicitly instructs leaving the `TODO`/`hashed` parameter untouched to avoid drive-by scope creep. Pre-existing debt is a documented, deferred concern (CLAUDE.md: 318 pre-existing lint findings deferred to Phase 8/QUAL-06); not introduced or worsened by this phase. |

None of these rise to BLOCKER: no debt marker was newly introduced by this phase, and every WARNING is a robustness/UX edge that the phase's own code review (03-REVIEW.md) already surfaced and correctly classified as non-critical. None contradicts a stated must-have truth or prohibition.

### Human Verification Required

### 1. ROADMAP Phase 3 success criterion 4 — real authenticator app, end to end

**Test:**
1. `export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY="$(bin/python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)))")"` then `bin/instance fg`.
2. Log in as a test user, open `@@setup-two-factor-authentication`, confirm the QR image renders as a `data:` URI (no outbound network request visible in the browser's network panel for the image).
3. Scan it with a real TOTP app (Google Authenticator, FreeOTP, etc.). Confirm the account label reads as `<username>@<domain>`.
4. Enter the 6-digit code the app shows and submit. Confirm enrollment succeeds.
5. Log out, log back in with username/password, confirm redirect to `@@google-authenticator-token`, enter the app's current code, confirm you reach the site authenticated.

**Expected:** All five steps succeed; the code is accepted on the first try (a first-try rejection fixed by a retry is a clock-drift signal for Phase 5/DRIFT, not a failure here).

**Why human:** Requires a physical/virtual TOTP authenticator app and a live `bin/instance` process — no automated agent can drive this. This is the one ROADMAP success criterion with no automated proxy; `helpers.get_totp`'s round trip in `test_seed_encryption_round_trip` proves the seed survives encryption/decryption and that `onetimepass` accepts a computed token, but proves nothing about what a real phone parses, renders, or displays.

### Gaps Summary

No gaps. All 20 machine-checkable must-haves (roadmap success criteria + plan-level truths,
prohibitions, artifacts, and key links across all three plans) were independently
re-verified against the actual codebase — not accepted from SUMMARY.md narrative — including
an independent re-run of the full test suite (`bin/test -t '!robot'` → 41/41 passing,
matching the orchestrator's earlier independent run) and targeted re-runs of the
fail-closed, per-call-key-read, and seed-round-trip tests individually. Three WARNING-level
quality/robustness findings and two INFO-level pre-existing-debt notes, all already
identified in `03-REVIEW.md`, are carried forward here for visibility but do not block the
phase: none contradicts a stated must-have truth or prohibition, and none was introduced or
worsened by this phase's commits.

The sole outstanding item is ROADMAP success criterion 4 (real authenticator app enrollment
and login, end to end), which the phase's own planning correctly identified as requiring a
human with a physical device and deliberately deferred to end-of-phase per
`workflow.human_verify_mode=end-of-phase`. This is reported as human_verification, not as a
gap, per the phase's explicit design.

The `industrialisation` repo's Puppet `concat::fragment` for
`IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` remains a known, tracked, out-of-repo deployment
dependency (documented in `README.rst` and restated in all three SUMMARYs). It is correctly
not scored as a gap of this phase's commits, but is surfaced here so it does not silently
fall through: the feature is code-complete and fully tested, but **not deployable** until
that Puppet change ships.

---

_Verified: 2026-07-30T15:00:00Z_
_Verifier: Claude (gsd-verifier)_
