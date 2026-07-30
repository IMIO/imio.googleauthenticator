---
phase: 03
slug: encrypted-seeds-and-local-qr
status: secured
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: 2026-07-30
---

# Phase 03 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Verification depth: **ASVS level 1** (grep/AST-depth mitigation verification), blocking
threshold **high**. The plan-time register was authored across all three PLAN files
(`register_authored_at_plan_time: true`), so this audit **verified existing mitigations**
rather than constructing a register retroactively.

Four threats absent from the plan-time register were added during this audit — they were
found by human UAT (`03-UAT.md`), not by the plan's threat modelling. They are marked
**(UAT)** below. Recording them here rather than only in the UAT file is deliberate: a
register that omits what testing actually found would overstate this phase's coverage.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| ZODB / backup / `Data.fs` copy → any reader | The `two_factor_authentication_secret` memberdata property is stored in the database; a filesystem backup, ZEO connection or the ZMI exposes it | TOTP seed (shared secret) |
| `helpers.get_barcode_image` → outbound HTTP | Previously a GET to `chart.googleapis.com` carrying the plaintext seed in the query string, visible to every proxy and access log in between. Removed by this phase | TOTP seed |
| process environment → `helpers.get_encryption_key` | The Fernet key enters only via `os.environ`, injected at start by buildout/Puppet, and must not cross back into the ZODB, a log or an exception message | seed encryption key |
| Puppet-managed host config → Zope process environment | The production key crosses from a `concat::fragment` in the separate `industrialisation` repo. This repository declares the variable and never holds the value | seed encryption key |
| ZEO client N's environment → the shared ZODB | The key is per-process, the seeds are shared; divergence between clients is invisible from the database side | seed encryption key |
| repository / git history → any reader | A key literal committed to `base.cfg` or `README.rst` is permanently in the history of a repository more people can read than can read production | seed encryption key |
| unauthenticated HTTP → PAS `authenticateCredentials` → `decrypt_seed` | An unauthenticated login attempt reaches the crypto path; what happens when it raises decides whether the second factor exists at all | credentials, TOTP seed |
| unauthenticated HTTP `?signature=…` → `ResetBarCodeForm` → stored `bar_code_reset_token` | An unauthenticated request supplies a candidate compared against a stored secret, at two comparison sites per request | bar-code reset token |
| operator → control panel Save / `@@…-enable-for-all-users` → bulk enrolment | The operator's report of whether the second factor was actually turned on. A success message with zero enrolments is a false report of a security control's state | 2FA enablement state |
| anonymous or admin registration → `IPrincipalCreatedEvent` → `encrypt_seed` | Account creation transits the crypto path on every new user, because `globally_enabled` defaults `True` | TOTP seed |
| **Zope root `acl_users` → login, bypassing the site's PAS** | **(UAT)** An account defined in the root user folder is authenticated above the site, so this plugin — registered in the site's `acl_users` — cannot gate it | credentials, 2FA enablement state |
| `sys.path` egg ordering → `import ipaddress` | Two distributions install a top-level module of the same name; which wins is decided by the build host, not the code | client IP / whitelist decision |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-03-01 | Information Disclosure | plaintext base32 seed in memberdata | critical | mitigate | `encrypt_seed` stores only `v1$<fernet-token>`; verified `generate_secret` encrypts before store, `test_seed_encryption_round_trip` asserts `v1$` prefix and `assertNotIn(seed, stored)` | closed |
| T-03-02 | Elevation of Privilege | crypto layer silently downgrading to plaintext / password-only | critical | mitigate | `_get_fernet` raises on both branches (unset key, invalid key); no local `except` returns a fallback. `test_login_is_refused_when_seed_key_is_broken` asserts `_extractUserIds` raises rather than returning user ids | closed |
| T-03-03 | Information Disclosure | seed in a GET query string to an external host | high | mitigate | In-process `qrcode` render to a `data:` URI; 0 `googleapis` references in `src/` outside a test assertion | closed |
| T-03-04 | Information Disclosure | seed readable in `ps` / `/proc/<pid>/cmdline` | high | mitigate | Pure-Python `qrcode == 6.1`; 0 `subprocess`/`os.system`/`os.popen`/`commands.` in `helpers.py` | closed |
| T-03-05 | Tampering | `ipaddress` module shadowing decided by egg ordering | high | mitigate | `py2-ipaddress` removed from `setup.py` (0 refs), `ipaddress = 1.0.23` pinned in `test-4.3.cfg`; all 3 real `ipaddress.*()` call sites wrapped in `_to_unicode_ip` | closed |
| T-03-06 | Information Disclosure | key value reaching an exception message, traceback or log line | high | mitigate | `_get_fernet`'s two messages interpolate `ENV_VAR_NAME` only; asserted a distinctive bogus key is absent from `str(exc)` while the variable name is present | closed |
| T-03-21 | Repudiation | bulk enable reporting "Changes saved." with zero users enrolled | high | mitigate | `ValueError` re-raised above the per-user broad handler; **both** entry points (`controlpanel.handleSave`, `@@…-enable-for-all-users`) add an `'error'` message and suppress the success message — verified in both files | closed |
| T-03-10 | Denial of Service | one ZEO client with a stale/missing key — intermittent failures with no ZODB-side evidence | high | mitigate | Boot-time CRITICAL line gives that client a first-person symptom; foreign-key ciphertext raises `ValueError` rather than yielding a different seed | closed |
| T-03-11 | Information Disclosure | a real production Fernet key committed to git | high | mitigate | Exactly 1 `SEED_KEY` reference in `base.cfg`, in `[testenv]`, commented as a throwaway; `README.rst` states the deployment buildout owns the production copy | closed |
| T-03-21b | Tampering | a syntactically valid placeholder key in `[instance]` — production encrypts under a value every repo reader has, and the CRITICAL log never fires | high | mitigate | `[instance]` carries `environment-vars` with only `PYTHONBREAKPOINT` and **no key entry** — the loud state. Verified across all `*.cfg` | closed |
| T-03-SC | Tampering | `cryptography`, `ipaddress`, `qrcode`, `cffi`, `Pillow` legitimacy | high | mitigate | Blocking `checkpoint:human-verify` gate placed before the `install_requires` edit; recorded as performed in `03-01-SUMMARY.md` | closed |
| **T-03-23 (UAT)** | **Repudiation / Elevation of Privilege** | **`@@setup-two-factor-authentication` enrolled a Zope-root account and reported "successfully enabled" for a login this plugin can never gate** | **high** | **mitigate** | **`helpers.is_site_local_user` refuses enrolment at both self-service claim sites (`user_setup.py`, `reset_bar_code.py`), before any flag write or seed mint; the QR is not rendered either. Verified failing without the guard** | **closed** |
| T-03-07 | Spoofing | substituted/hand-edited ciphertext accepted as a valid seed | medium | mitigate | Fernet is authenticated (HMAC-SHA256); `InvalidToken` re-raised as `ValueError` and never caught; envelope-prefix check refuses `v2$`/prefixless input | closed |
| T-03-08 | Information Disclosure | ~122-bit `uuid4` seed below RFC 4226 §4 R6's 128-bit floor | medium | mitigate | `base64.b32encode(os.urandom(20))` = 160 bits, asserted as `len(b32decode(seed)) == 20` | closed |
| T-03-09 | Denial of Service | enrolment crashing because the previous base32 encoder ASCII-decodes raw entropy | medium | mitigate | stdlib `base64`, plus a round trip through the real `generate_secret` and real `onetimepass.get_totp` | closed |
| T-03-12 | Denial of Service | key absent at process start — every enrolment and login fails with no prior warning | medium | mitigate | `IProcessStarting` subscriber logs CRITICAL once, naming the variable and the consequence | closed |
| T-03-13 | Denial of Service | a raise from the startup subscriber taking down `bin/instance debug` and `bin/test` too | medium | mitigate | AST walk of `subscribers.py`: **0** `Raise`/`TryExcept`/`TryFinally` nodes (the lone grep hit is the docstring — the self-invalidating case the plan predicted) | closed |
| T-03-14 | Repudiation | the out-of-repo Puppet dependency silently dropped | medium | mitigate | `README.rst` states it as shipped documentation; `concat::fragment`, `industrialisation` and "not deployable" all present | closed |
| T-03-16 | Information Disclosure | timing oracle on `bar_code_reset_token`, reachable pre-auth at two sites | medium | mitigate | One shared `validate_bar_code_reset_token` using `hmac.compare_digest`; 3 references in `reset_bar_code.py` (import + both call sites) | closed |
| T-03-17 | Denial of Service | `compare_digest` raising `TypeError` on py2 `unicode` on every reset attempt | medium | mitigate | Both operands coerced to py2 `str` before compare, asserted across all four `str`/`unicode` combinations plus a non-ASCII operand | closed |
| T-03-18 | Spoofing | an empty stored token matching an empty submitted signature | medium | mitigate | Either operand falsy returns False before any comparison; asserted for all three empty combinations plus `None` | closed |
| T-03-22 | Denial of Service | a missing key stopping all account creation, not only logins | medium | **accept** | Correct fail-closed behaviour — see Accepted Risks R-03-01 | closed |
| **T-03-24 (UAT)** | **Denial of Service** | **`validate_token` passed `get_secret`'s implicit `None` to `onetimepass`, raising `TypeError('Incorrect secret')` as an unhandled 500 on the token and reset forms** | **medium** | **mitigate** | **Falsy-secret guard in `validate_token`, the one function all three callers route through; narrow by design so a decryption `ValueError` still propagates. Verified failing without the guard** | **closed** |
| **T-03-25 (UAT)** | **Denial of Service** | **the bar-code reset email ASCII-encoded a unicode body, so the only documented recovery path for a locked-out user was dead** | **medium** | **mitigate** | **`charset='utf-8'` passed to `MailHost.send`. Verified failing without it (0 messages delivered). Delivery against a real SMTP server remains unproven — see Residual Risks** | **closed** |
| T-03-15 | Information Disclosure | the CRITICAL message reworded to interpolate the key value | low | mitigate | Fixed text naming only the variable; fires only on the falsy-key branch, so there is nothing to interpolate. Exactly 1 `logger.critical` | closed |
| T-03-19 | Denial of Service | unbound `redirect_url` on `SetupForm.handleSubmit`'s exception path | low | mitigate | All three branches driven by one committed test, exception branch injected through a real collaborator | closed |
| T-03-20 | Repudiation | BUG-02 recorded as fixed with no fix and no test | low | mitigate | `git diff --name-only` criterion asserts `user_setup.py` absent from the commit; the test docstring records the trace | closed |
| T-03-SC (03-02) | Tampering | package installs | low | accept | Plan adds no package; `zope.processlifetime` already transitively available | closed |
| T-03-SC (03-03) | Tampering | package installs | low | accept | Plan adds no package; `hmac` is stdlib | closed |
| **T-03-26 (UAT)** | **Information Disclosure** | **username-enumeration oracle: `request_bar_code_reset.py:116` answers "Invalid username." for an unknown user and success for a known one, on an unauthenticated endpoint** | **low** | **accept** | **See Accepted Risks R-03-02** | **open — below `high` threshold (non-blocking)** |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `block_on: high` count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-03-01 | T-03-22 | A missing key stops all account creation, not only logins. Accepted because the behaviour *is* the desired one — enrolling a user with no recoverable second factor is worse. Not silently accepted: asserted by test (`assertRaises` plus a good-key control and an `assertIsNone` proving no half-made account) and documented in `README.rst`'s failure-mode list so an operator learns it from the docs rather than a broken registration form | plan 03-01 (author) | 2026-07-29 |
| R-03-02 | T-03-26 | The reset form distinguishes known from unknown usernames on an unauthenticated endpoint. Pre-existing, `low`, and below the `high` blocking threshold. A password-reset-shaped flow would normally answer identically either way; changing it is a deliberate UX/security trade-off rather than a defect fix, and is out of phase-03 scope. Recorded so it does not resurface as a discovery | Chris (UAT) | 2026-07-30 |
| R-03-03 | T-03-23 (residual) | A Zope-root login is **not** gated by this plugin and cannot be, since the plugin is registered in the site's `acl_users`. Accepted as a scope boundary: the project's Core Value scopes to *in-site users*, and gating root logins would require installing the plugin in the root `acl_users` — a roadmap-level change. What was **not** accepted is the false assurance, which is now mitigated (T-03-23): the forms refuse such an account instead of reporting success | Chris (UAT) | 2026-07-30 |

---

## Residual Risks

Not threats with open dispositions, but known gaps in the *evidence* behind two closures.
Recorded so a later reader does not mistake a passing test for a proven end-to-end path.

| Ref | Gap | Why it remains |
|-----|-----|----------------|
| T-03-25 | The regression test patches `MailBase._send`, so it proves the message survives encoding and is handed to MailHost — **not** that it is delivered. The originally reported traceback died during encoding, before any SMTP conversation, so whether this instance can deliver mail at all is untested | Needs a browser run against a real SMTP server; no such fixture exists and none is planned for this phase |
| criterion 4 | The `otpauth://` label rendering literally as `<username>@<domain>` was not read back from the QR payload during UAT; it is inferred from the authenticator app accepting the code and emitting codes that validated | Weak evidence for that one sub-assertion only; every other part of criterion 4 was directly observed |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-30 | 29 | 28 | 1 (low, non-blocking) | Claude (orchestrator, ASVS L1 verification) |

Register origin: `register_authored_at_plan_time: true` — 25 threats from the three PLAN
`<threat_model>` blocks, verified rather than rediscovered. 4 further threats (T-03-23 →
T-03-26) were added from human UAT findings during this audit; 3 of the 4 are now closed by
mitigation, 1 is accepted at `low`.

One threat changed the code during this audit: **T-03-23** was presented as a blocking
`high` and dispositioned "fix now" rather than "accept", so `is_site_local_user` and its two
call-site guards were written, tested and committed as part of this run.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed — the single open threat (T-03-26, `low`) is below the
      `high` blocking threshold and carries an accepted-risk entry
- [x] Suite green at 46 tests, 0 failures, 0 errors
- [x] Evidence gaps recorded under Residual Risks rather than left implicit
