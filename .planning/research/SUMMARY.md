# Project Research Summary

**Project:** imio.googleauthenticator
**Domain:** TOTP second-factor hardening + package rename in a frozen Plone 4.3 / Zope 2.13 / Python 2.7.18 PAS add-on
**Researched:** 2026-07-28
**Confidence:** HIGH (all four researchers worked from primary source — installed eggs, executed code, PyPI release metadata — not recall)

## Executive Summary

This is a brownfield security hardening of a forked, undeployed Plone 4.3 PAS authentication plugin, plus a `collective.*` → `imio.*` rename. Experts build this kind of second factor as a **decision/redirect/grant split**: the `IAuthenticationPlugin` only *decides* and vetoes (by wiping the shared credentials dict — the only veto PAS 1.11.3 offers, verified against all 22 plugin interfaces); the redirect happens in `IChallengePlugin` (Unauthorized paths) and an `IPubBeforeCommit` subscriber (the login-form POST path, which returns HTTP 200 and never raises `Unauthorized`); and **all** second-factor state writes happen in the token form view, because that is the only path in the request lifecycle that actually commits. Every parameter for the hardening itself is fixed by RFC 6238 §5.2 (replay MUST NOT, one step of drift), RFC 4226 §7.3 (throttle as low as usable), NIST SP 800-63B §5.1.2.2/§5.2.2 and OWASP ASVS V2 — and needs almost no new dependency: four of six capabilities are stdlib (`hashlib.pbkdf2_hmac`, `hmac.compare_digest`, `os.urandom`, `int(time.time())//30`).

The recommended approach: **rename first** (with a one-line fail-closed fix riding along), then fix the PAS boundary, then the memberdata state, then the override deletion, with encryption + local QR running as an independent parallel workstream. Only `cryptography==3.3.2` (+ `ipaddress`, `cffi`) and `coverage==5.5` are genuinely new; `qrcode==6.1` is optional and contested (below). `onetimepass` stays: `get_hotp(secret, intervals_no=i)` already exposes the counter-level primitive, so the `pyotp` swap remains correctly out of scope.

The dominant risks are all **silent** ones, and they cluster. PAS swallows five exception types from plugins and falls through to `source_users`, so any bug in the plugin is a total, unlogged 2FA bypass. `transaction.abort()` on the `Unauthorized` path silently discards any counter written in the plugin, so a lockout implemented there is a security control that does not work and looks like it does. Undeclared memberdata properties are silently popped, so a forgotten `memberdata_properties.xml` entry means the counter never persists with nothing in the log. Stale `.pyc` files and a stale egg-link keep the old namespace importable, so a half-done rename passes CI and breaks on a fresh clone. And the coverage instrumentation itself is unsound before it is ever used. Mitigation is cheap in every case and is folded into the phase order below.

## Convergent Findings (highest-confidence signal in the set)

Where two independent researchers reached the same conclusion, treat it as settled:

| Finding | Found by | Confidence |
|---|---|---|
| `onetimepass.valid_totp()` returns a bare bool and has **zero** clock-drift tolerance — replay detection is impossible on top of it | STACK (source read + executed), FEATURES (source read) | **HIGH** |
| `get_hotp(secret, intervals_no=i)` over `now-1 .. now+1` is the route to both drift tolerance and replay detection; returns the matched window number | STACK (executed `matched_window`, real values), FEATURES | **HIGH** |
| The coverage setup is broken *before* it is used — `.coveragerc` has `[report] include` but no `[run] source` and no `omit = */tests/*`; `bin/test-coverage` (`base.cfg:82-92`) has no `set -e` | STACK, PITFALLS (P13, P14) | **HIGH** |
| Plugin ordering (`google_auth` first among `IAuthenticationPlugin`) is load-bearing and undocumented; the credentials-dict wipe is the real veto, `return None` vetoes nothing | ARCHITECTURE (§1, §3 Vector 1), PITFALLS (P11.4), FEATURES (local fact 7) | **HIGH** |
| Encrypting the seed is worthless while the seed still goes to `chart.googleapis.com` — QR must land with or before encryption | FEATURES, PITFALLS (integration gotchas), PROJECT.md | **HIGH** |
| Replay/lockout state must be per-user memberdata, never a shared object or RAM cache | ARCHITECTURE (§5, OOBTree bucket analysis), FEATURES (anti-feature), PITFALLS (performance) | **HIGH** |

## Conflicts, Adjudicated

These are resolved, not averaged. Each names the cost of the road not taken.

### 1. QR generation: `imio.helpers`/zint vs `qrcode==6.1` — **RECOMMEND `imio.helpers` + zint 58, accept the argv leak**

- **The finding:** `imio.helpers.barcode.generate_barcode` passes the payload as `--data=otpauth://totp/...?secret=<SEED>`, so the plaintext seed is visible in `ps` and `/proc/<pid>/cmdline` to any local user on the Zope host for the subprocess lifetime. STACK tested `--input=/dev/stdin` as a workaround; zint rejects it (`Error 79`). Only argv or a temp file are available. `qrcode==6.1` renders in-process — no subprocess, no argv, no temp file — and STACK verified it under this exact interpreter (848-byte PNG; `SvgPathImage` also works with no Pillow).
- **The counterweight:** PITFALLS found that adding `imio.helpers` to `install_requires` **in the rename phase** is the only thing that forces `imio.googleauthenticator` and `imio.helpers` into the same process, which is the only way the `imio` namespace-package declaration mistake (`declare_namespace` vs `pkgutil` vs empty, plus `namespace_packages=['imio']`) surfaces before deployment. Choosing `qrcode` removes that early-warning detector.
- **Adjudication:** keep PROJECT.md's decision (`imio.helpers` + zint type 58) and record the argv leak as an **accepted, documented risk** — the threat model is a local user on the Zope host, who on a Plone 4 box has other paths to the ZODB anyway, and this is still a categorical improvement over posting the seed to Google. **But** the namespace-detector benefit is only real if `imio.helpers` lands in the rename phase, not the QR phase. If the roadmap declines to add `imio.helpers` early, switch to `qrcode==6.1` and add an explicit two-package import test (`bin/python -c "import imio.helpers, imio.googleauthenticator"`) instead.
- **Cost of the alternative:** `qrcode==6.1` is one small pure-Python pinned egg and closes the leak, at the price of losing the namespace early-warning and diverging from PROJECT.md.

### 2. Where the failure counter is written — **the token form view, not the PAS plugin. FEATURES' phase 2 shape needs amending.**

- ARCHITECTURE (§5, `ZPublisher/Publish.py` `finally: transactions_manager.abort()`) established that **any** request ending in an exception loses every ZODB write, and `Unauthorized` *is* such an exception (`zpublisher_exception_hook` renders the view then explicitly re-raises it). A write inside `IChallengePlugin.challenge()` is discarded **100%** of the time, because `challenge()` is reached from `HTTPResponse.exception()`, which runs *after* the abort.
- FEATURES' MVP groups "F6 + F1a–F1d + F2a–F2c" as one phase without stating *where* the writes live, and its data-flow language ("increment on any failed second-factor submission") is compatible with putting the increment in `authenticateCredentials`. **Reconciled:** the grouping is right, the location must be pinned. The token form POST returns 200/302 → `PubBeforeCommit` → `commit()`, and a failed second factor is by definition submitted to the token form, so this lines up cleanly. Write the invariant into the phase: *no ZODB write in the PAS plugin or the challenge plugin, ever.*
- Also fold in ARCHITECTURE's silent-drop finding: `MutablePropertySheet.setProperties` **pops** keys not declared in the sheet, with no error. `memberdata_properties.xml` entries are mandatory, and the smallest test that catches a missing one is a `setMemberProperties()` → `user.getProperty()` round-trip per new property.

### 3. Does the rename fix the registry error? — **NO. Unmissable.**

PITFALLS P6 traced the root cause of `IGoogleAuthenticatorSettings defines a field ska_secret_key, for which there is no record` to `SetupTool.getSortedImportSteps()` (`tool.py:269-276`) building a **Python 2 `set`** of step ids and `_computeTopologicalSort` (`utils.py:856-905`) inserting dependency-free steps in whatever order the set yields — i.e. **CPython 2.7 string-hash order**.

**Renaming the import step id from `collective.googleauthenticator` to `imio.googleauthenticator` changes its hash and can silently flip the ordering. If the error disappears after the rename, that is NOT evidence the bug is fixed.** It will return the first time any other add-on adds or removes an import step — i.e. the first time this is deployed next to `imio.dms.mail`. The fix is `<depends name="plone.app.registry"/>` on the import step, plus deleting the nested `runImportStepFromProfile` (preferably by moving the `ska_secret_key` seeding to a lazy accessor), plus a test asserting `getSortedImportSteps().index('imio.googleauthenticator') > index('plone.app.registry')`. The assertion is the control; the `<depends>` is just how you satisfy it.

### 4. Is `IChallengePlugin` the right hook? — ARCHITECTURE wins over PITFALLS P11.6

PITFALLS P11.6 concluded "`IChallengePlugin` is the wrong hook, stay in `authenticateCredentials`". ARCHITECTURE traced the full publish path against `PluggableAuthService-1.11.3`, `Zope2-2.13.30`, `Products.PlonePAS-5.1.1` and `CMFPlone-4.3.20`'s `login_form.cpt.metadata` / `logged_in.cpy` and reached a more precise answer: `IChallengePlugin` is **correct for every path that ends in `Unauthorized`** (deep links, basic auth, expired session) *and* is the mechanism that suppresses `credentials_basic_auth`'s 401 via the protocol-group lock (`PAS.py:1183-1185`) — but it is **never reached** on the login-form POST, which returns HTTP 200. That path needs an `IPubBeforeCommit` subscriber (~6 lines). Both researchers agree the *redirect must not stay in* `authenticateCredentials`; ARCHITECTURE has the line numbers for where it goes instead. **Take ARCHITECTURE's two-hook design.**

## Corrections to PROJECT.md (amend it before roadmapping)

1. **`py2-ipaddress` is NOT a Python-3-only problem.** PROJECT.md files it under "parks every concern whose only real fix is Python 3". Wrong. `cryptography==3.3.2` requires the `ipaddress` backport, and **both distributions install a top-level module named `ipaddress`** (confirmed on disk). Whichever egg is first on `sys.path` wins, and their APIs diverge on exactly the call this package makes: `ipaddress-1.0.23` raises `AddressValueError` for a `str` argument, and `helpers.py:459` does `ip_address(request.get('REMOTE_ADDR'))` with a Zope `str`, uncaught. **Consequence: total login failure, decided by egg ordering — works on a dev box, fails on a Puppet-built one.** Fix is a straight swap (drop `py2-ipaddress`, add `ipaddress==1.0.23`, `.decode('ascii')` at `helpers.py:459` and `helpers.py:496`), and it is **not separable from the encryption phase** — adding `cryptography` forces it. Net: one fewer dependency.
2. **The memberdata risk is not a ConflictError write hotspot.** PROJECT.md records it that way. Verified reality: storage is an `OOBTree` keyed by user id, so cross-user writes merge via bucket conflict resolution, same-user writes conflict but `retry_max_count = 3` handles the parallel-brute-force case correctly (the retry re-reads the fresh counter). **The real hazard is `transaction.abort()`** — see conflict 2. PROJECT.md's *decision* (memberdata, not RAM) is still right; its *stated reason* is wrong, and the wrong reason points the roadmap at the wrong mitigation.
3. **`IChallengePlugin` alone is not sufficient.** PROJECT.md's "perform the challenge and redirect from the PAS plugin only" assumes one hook covers it. Plone 4.3's login POST (`login_form` → `logged_in.cpy` → `login_failed.cpt`) returns **HTTP 200** and never raises `Unauthorized`, so `challenge()` is never called on the normal login path. Two mechanisms are required: `IChallengePlugin` + an `IPubBeforeCommit` subscriber.

Two smaller amendments worth making at the same time: the QR decision should carry the argv-leak note as an accepted risk (conflict 1), and the rename requirement should name the `imio.helpers` `install_requires` addition explicitly.

## Cheapest High-Value Items (do not let the roadmap bury these)

| Change | Payoff | Where |
|---|---|---|
| `_dont_swallow_my_exceptions = True` on the plugin class | **One line.** PAS's `_SWALLOWABLE_PLUGIN_EXCEPTIONS = (NameError, AttributeError, KeyError, TypeError, ValueError)` currently means any such exception logs at `debug` and `continue`s to `source_users`, which authenticates on password alone — a **silent total 2FA bypass**, with no forensic trail. Converts every later phase's mistakes from silent bypasses into 500s. Land it in the **rename phase**, as its own commit. | PITFALLS P4 |
| `id = 'login_form'` on `TokenForm` | **One class attribute.** Makes `popupforms.js`'s existing `formselector: 'form#login_form'` find the token form and render it *inside* the overlay — removing the need for both vendored override files (310-line `login_form.cpt` + 197-line `popupforms.js`) and the `imio.dms.mail` collision, with zero JS and zero skin overrides. | ARCHITECTURE §4 |
| `movePluginsTop(interface, [plugin.getId()])` + one assertion | Replaces the undocumented `movePluginsDown(interface, listPlugins(interface)[:-1])` incantation that the entire second-factor guarantee silently rests on. The test is the security control. | ARCHITECTURE §3 |
| `<depends name="plone.app.registry"/>` | Two lines; the actual fix for the registry error (conflict 3). | PITFALLS P6 |
| `set -e` in the `bin/test-coverage` template | One line; without it, failing tests + ≥90% coverage is a **green build**. | PITFALLS P14 |

## Broken-Before-Use Instrumentation (blocks a stated project requirement)

">90% coverage enforced in CI" is an Active requirement, and **both** STACK and PITFALLS independently found the instrument unsound:

- `.coveragerc` has only `[report] include = src/collective/googleauthenticator/*`. `include` under `[report]` filters what is *reported*; it does not add un-executed files to the denominator. So never-imported modules (`upgrades/to0301.py`, `browser/forms/request_bar_code_reset.py`, `browser/disable_two_factor_authentication*.py`) are absent from the report and their absence **raises** the percentage. Test modules are also in the denominator, so a package can clear `--fail-under=90` on the strength of its own tests. Needs `[run] source = src/imio/googleauthenticator`, `omit = */tests/*`, and `branch = True` (Plone add-ons execute every import/def/class line at ZCML time, so statement coverage over-reports by a large unpredictable margin).
- `bin/test-coverage` (`base.cfg:82-92`) has no `set -e` and no `exit`; its status is that of `coverage report` alone.

**Expect the number to drop sharply when this is fixed. That drop is the truth, not a regression.** Set the gate against the corrected number. Fix both **in the first commit of the coverage phase, before any new tests are written**, and prove the exit status with a deliberate test failure. Also `coverage==5.5` uses a SQLite data file, so delete any stale 4.x `.coverage` once, and drop the redundant `createcoverage` part and pin.

## Key Findings

### Recommended Stack

Four of six capabilities are pure stdlib on Python 2.7.18. Only two genuinely new runtime dependencies are needed. Every version below is the **last release publishing a `cp27` or `py2.py3` file** — verified against PyPI release metadata with upload dates, and executed against this repo's own `bin/python`. Nothing may require PEP 517: `requirements-4.3.txt` pins `setuptools 44.1.1`.

**Core technologies:**
- `cryptography == 3.3.2` — Fernet seed encryption; last `cp27` wheel (2021-02-07), 3.4 moved to py3.6+ *and* added a Rust build requirement. Already pinned in `server.dmsmail`. Raw `Fernet.generate_key()` output is used directly — **no KDF needed**.
- `ipaddress == 1.0.23` — forced by `cryptography`; **replaces** `py2-ipaddress` (see correction 1).
- `coverage == 5.5` — the 90% gate; `--fail-under` and `--precision` both confirmed present.
- stdlib: `hashlib.pbkdf2_hmac` (2.7.8+), `hmac.compare_digest` (2.7.7+), `os.urandom` + `base64.b32encode`, `int(time.time()) // 30`.
- `imio.helpers` + `zint` type 58 for QR (per PROJECT.md, argv leak accepted) — or `qrcode == 6.1` (see conflict 1).

**Two py2 bytes traps that pass a unit test and fail a live site:** `Fernet()` and `decrypt()` reject `unicode` (`TypeError`), and Plone coerces memberdata freely between `str`/`unicode` — so `.encode('ascii')` before `decrypt`, `.decode('ascii')` before storing. And `hmac.compare_digest` raises `TypeError` across `str`/`unicode`, which means the existing `reset_bar_code.py:104` fix cannot be a naive swap — encode both sides first. Also: on py2 a malformed base64 key raises `TypeError`, not `ValueError`, so key validation must catch both.

### Expected Features

Every parameter traces to a primary standard; vendor defaults (Keycloak especially, since it is the successor system) are sanity anchors. This is a real bug class, not theoretical — TOTP-valid-after-use shipped in Craft CMS (SBA-ADV-20240617-01), its two-factor plugin (SBA-ADV-20240202-02) and Vikunja (GHSA-p747-qc5p-773r).

**Must have (table stakes):**
- Counter-returning `validate_token()` on `get_hotp` — the keystone; ~6 lines. Also tighten input to exactly 6 digits (`_is_possible_token` currently accepts `"1"` and `"123"`).
- Drift tolerance `{T, T−1}` **and** replay rejection (`matched_counter > last_used_totp_counter`) — **same six lines, same commit.** Splitting them yields a state where drift is accepted but replay is not detected: strictly worse than today. RFC 6238 §5.2 MUST NOT; ASVS 2.8.4/2.8.5 (log the replay, no username in plaintext).
- Failed-attempt counter + **15-minute auto-expiring lock at N=5**, checked *before* the token is evaluated (else a locked account is still an oracle). Recovery-code attempts share the same counter. N=5/900 s ≈ 1042 days expected time-to-hit; NIST §5.2.2's 100 is a ceiling, not a target.
- **10 single-use recovery codes**, 80 bits each (`os.urandom(10)` → 16 base32 chars), salted and hashed, shown exactly once at enrollment, regenerable as a whole set, with a remaining-count warning at ≤3. Note STACK and FEATURES differ on salt strategy: FEATURES proposes per-code salt + SHA-256, STACK argues **one salt per user** because per-code salts force N PBKDF2 runs per attempt (10 × 0.113 s = 1.1 s) — a DoS lever on a login-adjacent endpoint. **Take STACK's per-user salt**; a per-user salt still defeats cross-user rainbow tables, which is the only thing salts do here. Codes are 40–80-bit random values, not passwords, so iteration count is insurance, not load-bearing.
- Fernet-encrypted seed with **fail-closed** on a missing/invalid key, same commit — never a "TOTP or plaintext" fallback. Plus local QR in the same phase.
- Deny (do not challenge) on the `credentials_basic_auth` extractor for enrolled users — **wipe the credentials dict**, do not redirect (a 302 to HTML is meaningless to a non-browser client). Document the consequence: scripts/WebDAV/API consumers use a non-2FA service account or the existing IP whitelist.

**Should have (competitive):**
- Email on lockout and on recovery-code use (ASVS 2.2.3) — one MailHost call each, reusing the bar-code-reset path. **Never per failed attempt** (mail-flood amplification DoS).
- Bump the seed to 160 bits (`b32encode(os.urandom(20))`) — current `b32encode(str(uuid4()))` is ~122 bits in a needlessly long 58-char secret, marginally under RFC 4226 §4 R6's 128-bit MUST. One line, and free because enrollment is being rewritten anyway.
- Version the ciphertext now (`v1$<token>`) — three bytes today, impossible to retrofit once the old key is gone.

**Defer / never:**
- "Remember this device", admin-unlock-only lockout (a DoS primitive: 5 requests permanently locks any known username), re-displaying recovery codes, emailing recovery codes, deriving the key from the user's password, progressive backoff, CAPTCHA, 8-digit OTP, adaptive/geo MFA, `MultiFernet` rotation (leave a `ponytail:` comment), any attempt to make HTTP Basic Auth work with a second factor, and distinguishing "wrong password" from "wrong token" in responses.
- Everything already in PROJECT.md Out of Scope stays out: Python 3, Plone 5/6, WebAuthn/U2F/SMS, Zope-root/emergency admins (ARCHITECTURE §3 confirms `_tryEmergencyUserAuthentication` runs twice and bypasses every plugin by construction — that is the citation for the documented limitation), the `pyotp` swap, async bulk ops, performance caching.

### Architecture Approach

PAS 1.11.3 has **no order-independent authentication veto** — verified against all 22 interfaces. Extraction is the outer loop (each extractor gets its own dict), authentication *accumulates* (`result.extend(user_ids)` at `:675`) and `validate()` returns the first authorized user (`:262`), so `return None` vetoes nothing. The defence is therefore layered: enforce the ordering with a test, fail closed on exceptions, and make the token form view the **only** thing that grants a session.

**Major components:**
1. `IAuthenticationPlugin.authenticateCredentials` — **decision only.** Whitelist check, 2FA check, first-factor verification, wipe the credentials dict (the veto), set `request['_2fa_pending'] = signed_url`, return `None`. Wrapped in `except Exception:` → wipe + log + return `None`. **Never** touches `RESPONSE`, **never** writes to the ZODB.
2. `IChallengePlugin.challenge` — the redirect on the `Unauthorized` path, and the mechanism that suppresses `credentials_basic_auth`'s 401 (browser requests have no `'Browser'` key in `DEFAULT_PROTO_MAPPING`, so `valid_protocols` is empty, ours fires first and locks the protocol group). **Must be write-free** — the transaction is already aborted. **Do not set `protocol = 'http'`**, or WebDAV/FTP/XML-RPC clients get an HTML redirect; set no `protocol` at all and `getattr(challenger, 'protocol', id)` yields the plugin id.
3. `IPubBeforeCommit` subscriber (~6 lines) — the redirect on the login-form POST path, which returns HTTP 200. Fires after the render, before commit, so writes survive.
4. `@@google-authenticator-token` view — signature + TOTP validation, **all** memberdata state writes, and `session._setupSession()`: the only grant point. Carries `id = 'login_form'`.
5. Env key access — a per-call plain function doing `os.environ.get()`, raising a useful error. **Not** at module import (invisible and unpatchable under `bin/test`), **not** a `zope.component` utility (one implementation). Deliberately diverges from `imio.helpers/__init__.py:44-55`'s module-scope pattern; note the divergence so it does not read as an oversight.

### Critical Pitfalls

1. **PAS swallows plugin exceptions → silent total 2FA bypass** — `_dont_swallow_my_exceptions = True`, in the rename phase. Recovery if shipped is HIGH cost with **no forensic trail** (the swallowed exception logs at `debug`): you must assume every login since the deploy was single-factor.
2. **`transaction.abort()` discards counters written in the plugin** — all second-factor state writes go in the token form view. A lockout written in the plugin never locks out.
3. **The rename does not fix the registry error** — it changes a hash and may flip an unspecified ordering. `<depends>` + an ordering assertion, not a rename.
4. **Stale `.pyc` + stale `.egg-info`/egg-link keep `collective.googleauthenticator` importable** — reproduced locally: py2.7 imports an orphan `.pyc` with no `.py` beside it. `git mv` moves only tracked files; all 27 `.pyc` files and the egg-info are git-ignored and stay. Both namespaces can load at once → duplicate ZCML. `git clean -xdf src/` in the first rename commit, delete both artefacts, update `cleanup.sh`, `PYTHONDONTWRITEBYTECODE=1`. Loud secondary detector: `registerMultiPlugin` raises `RuntimeError` on a duplicate meta_type, so Zope refuses to start — read that traceback as "stale artefact", not "rename bug".
5. **Existing ZODBs silently downgrade to password-only** — "not deployed" is true of *users*, false of *databases*. Any local `Data.fs` unpickles the plugin as `OFS.Uninstalled.Broken`, it stops providing `IAuthenticationPlugin`, and **2FA stops running with no error page.** Declare DBs discarded, not migrated; say so in CHANGES.txt; add a permanent test asserting `google_auth` is registered for `IAuthenticationPlugin`.
6. **Undeclared memberdata properties are silently popped** — `memberdata_properties.xml` entries are mandatory; a `setMemberProperties()` → `getProperty()` round-trip test per property is the smallest thing that catches it.
7. **Two rename traps that pass CI:** the i18n domain comes from the **filenames** under `locales/`, not `i18n_domain`, so renaming `MessageFactory` without `git mv`-ing the `.pot`/`.po` (and deleting the `.mo`) silently deletes the Dutch translation. And `setupVarious` guards on `context.readDataFile('<name>.marker.txt')` and **returns silently** on a mismatch — rename the marker *file*, not just the string, or the PAS plugin is never added.
8. **Deleting `skins/` deletes two live templates** — `control_panel_extra.html` (`controlpanel.py:84`) and `request_bar_code_reset_email.pt` (`request_bar_code_reset.py:90`) are reached by `restrictedTraverse` and are **not** overrides. Convert both to `ViewPageTemplateFile` in the same commit; delete only `login_form.cpt` + `.metadata`. The email path has zero test coverage, so CI will not notice.
9. **`remove="True"` on `popupforms.js` is a permanent, global mutation** with no uninstall counterpart — uninstalling the add-on leaves stock Plone without `popupforms.js` site-wide, and the `imio.dms.mail` collision flips on install order. Stop touching resources you do not own; ship a real `profiles/uninstall/`.
10. **`MANIFEST.in`'s eight hardcoded `src/collective/...` paths** — with no `setuptools_git`, stale paths produce an sdist with no `profiles/`, no `locales/`, no `skins/`. Invisible in dev (develop-egg reads `src/` directly), **fatal on release.**

## Implications for Roadmap

One reconciled build order. FEATURES proposed four feature phases, ARCHITECTURE proposed Rename → PAS boundary → memberdata with overrides after and encryption in parallel, PITFALLS required rename-first, registry-before-encryption and coverage-infrastructure-before-tests. All three are satisfiable simultaneously.

```
 P1 Rename ──▶ P2 Registry ──▶ P3 PAS boundary ──▶ P4 memberdata state ──▶ P5 recovery codes
   (+P4 one-liner)                    │
                                      └──▶ P6 delete overrides (+ next_url fix)
 PW Encryption + local QR + ipaddress swap   (parallel workstream, start at P1)
 P7 Coverage + test layers   (last; its two infra fixes come first inside it)
```

### Phase 1: Rename + fail-closed
**Rationale:** touches every file, so it must precede everything to avoid rebasing every later diff. P3's ZODB-Broken risk is only cheap while nothing is deployed. It also changes the PAS plugin id and `meta_type`, which is exactly what the PAS-boundary phase's ordering assertion keys on.
**Delivers:** `imio.*` everywhere — on disk, egg name, i18n domain **and `locales/` filenames**, GenericSetup profile **and marker file**, registry interface path, `++resource++` prefixes, `MANIFEST.in` (8 paths), `.coveragerc`, `base.cfg` `package-name` + `[code-analysis] directory`, `cleanup.sh`, `testing.py`'s `z2.installProduct` string, layer constants. Plus: `git clean -xdf src/`, both stale artefacts deleted, `PYTHONDONTWRITEBYTECODE=1`, `namespace_packages=['imio']` + `declare_namespace`, `imio.helpers` in `install_requires`, and `upgrades/` deleted (it only mattered for sites installed at ≤0.3.0, of which there are none).
**Same commit, separately:** `_dont_swallow_my_exceptions = True`.
**Avoids:** P1, P2, P3, P4, P5, the marker-file trap, the `MANIFEST.in` trap.
**Do NOT:** rename `PAS_ID` (`google_auth` is already namespace-neutral; renaming it creates a second plugin on any existing ZODB). Rename `PAS_TITLE` only, and `meta_type` in its own commit so the `RuntimeError` signal stays interpretable.

### Phase 2: Registry fix
**Rationale:** must precede encryption — the key is read on a code path the registry seeding bug destabilises, and `get_app_settings()` raising `KeyError` is one of the swallowable exceptions that becomes a bypass.
**Delivers:** `<depends name="plone.app.registry"/>`; `_setup_secret_key` deleted in favour of a lazy `get_ska_secret_key()` accessor that mints on first use; `runImportStepFromProfile` gone (`grep` returns nothing); an ordering assertion in the suite; a test that applies the profile **twice** and asserts `ska_secret_key` is unchanged (catches `<records>` hole 3, where a retained value that no longer validates is silently replaced by the default — resetting the site secret to `u''` and invalidating every in-flight signed URL, with only an INFO log line).
**Avoids:** P6, P7, P8. Never use `forInterface(check=False)` to silence it.

### Phase 3: PAS boundary — the keystone
**Rationale:** closes the basic-auth bypass, which gates the value of every other defence (they are all on the challenge path), and establishes *where writes can and cannot happen*, which the next phase needs.
**Delivers:** the request-flag design — decision in `authenticateCredentials`, redirect in `IChallengePlugin` + `IPubBeforeCommit`; `movePluginsTop` + the ordering assertion; fail-closed `try/except`; credentials wipe moved to the top of the 2FA branch so it also runs on the exception path; the `credentials_basic_auth` extractor-deactivation decision (belt-and-braces, genuinely order-independent, **confirm with `imio.dms.mail` first**); documented basic-auth consequence. One veto test per extractor (`__ac_name`/`__ac_password` POST, `Authorization: Basic`).
**Avoids:** P11 (including trap 5, PAS's `_extractUserIds` `ZCacheable_get` — no cache manager on `acl_users` by default in Plone 4.3, but a cached 2FA bypass is catastrophic if one is ever added; worth a one-line comment), and the `redirect(lock=1)`-is-not-a-refusal problem (it sets a status and a header; it does not clear the body or stop publishing, so the resource still renders inside the 302).

### Phase 4: memberdata state — drift + replay + lockout
**Rationale:** depends on P3, which answers "which code paths commit". Writing these before P3 lands produces a lockout counter silently aborted on exactly the paths an attacker uses.
**Delivers, in ONE phase and with drift+replay in ONE commit:** the counter-returning validator on `get_hotp`, `{T, T−1}` drift, replay rejection with a logged detection, the failed-attempt counter and 15-min lock at N=5 checked *before* token evaluation, all four `memberdata_properties.xml` entries, and a `setMemberProperties()`/`getProperty()` round-trip test per property. All writes in the token form view.
**Avoids:** the conflict-2 write-location trap, the silent-property-drop trap, and the drift-without-replay intermediate state.

### Phase 5: Recovery codes
**Rationale:** requires the shared lockout counter from P4 (else recovery codes are the unthrottled brute-force path) and P4's single dispatch point in the token form.
**Delivers:** 10 × 80-bit base32 codes, per-user salt + hash, single-use consumption, shown once at enrollment, whole-set regeneration, remaining-count warning at ≤3.

### Phase 6: Delete the overrides
**Rationale:** mechanically independent of P3, but sequence it after so the overlay is only ever exercised against the final redirect mechanism.
**Delivers:** `id = 'login_form'` on `TokenForm`; `login_form.cpt` + `.metadata` deleted; `control_panel_extra.html` and `request_bar_code_reset_email.pt` converted to `ViewPageTemplateFile` (`restrictedTraverse` grep clean); the `popupforms.js` copy, its `jsregistry.xml` entries and the `remove="True"` line deleted; `skins.xml`, `profiles/uninstall/skins.xml`, the `<cmf:registerDirectory>`, `skins/`, the `MANIFEST.in` line; a real `profiles/uninstall/` with `jsregistry.xml` + `cssregistry.xml`.
**MUST ship in the SAME commit as the `next_url` open-redirect fix** (`token.py:112-113`): the stale `login_form.cpt` copy *deleted* Plone 4.3.20's `came_from` hidden input, which is the only reason `CameFromAdapter` exists (its docstring blames Plone; the override is the culprit). Deleting the copy restores the field and changes what `ICameFrom` sees. Fix both ends: `urlencode` on the way in (also fixes the `+` FIXME at `helpers.py:310`), portal-prefix validation on the way out.
**Also:** the vendored copies are stale and actively harmful — `popupforms.js` reverts `msieversion()` to `jQuery.browser.msie` (**removed in jQuery 1.9**) and drops `dl.portalMessage.warning` from `common_content_filter`, swallowing warning messages in every Plone overlay site-wide.
**Verify by clicking the header "Log in" link, not by POSTing to `login_form`** — a direct-POST testbrowser test passes while the real UI is dead.

### Parallel Workstream: Encryption + local QR + `ipaddress` swap
**Rationale:** shares no code with P1–P6 and has the **longest lead time** in the milestone — the key's `concat::fragment` lives in the separate `industrialisation` repo. Start it at P1. Code can land and be tested first (tests set the env var themselves); the feature is not *deployable* until the Puppet change ships.
**Delivers:** Fernet seed encryption with a `v1$` version prefix; fail-closed on missing/invalid key at **enrollment and validation**; a per-call `get_encryption_key()`; local QR (the seed stops going to `chart.googleapis.com` — same phase, non-negotiable); the 160-bit seed bump; and the **`py2-ipaddress` → `ipaddress==1.0.23` swap with `unicode` coercion at `helpers.py:459` and `:496`** (correction 1 — not separable).
**Four places for the key, not one:** `[instance]`, `[testenv]` (with an obviously-fake value), the CI workflow, and the Puppet fragment. Per-ZEO-client, not per-database — one client with a stale fragment produces `InvalidToken` non-deterministically depending on which client the load balancer picked, with no ZODB-side evidence. Log CRITICAL at `IProcessStarting` when absent; never `raise` from module import or ZCML. Never put the key in the registry, a memberdata property, a log line or an exception message — QuickInstaller takes a `portal_setup` snapshot before *and* after every install. Tests: key unset → login **refused**; key garbage → login **refused**.

### Phase 7: Coverage + test layers + code-analysis
**Rationale:** last, and its **two infrastructure fixes are its first commit** — otherwise the phase measures itself with a broken instrument.
**Delivers:** `.coveragerc` `[run] source` + `omit` + `branch = True`; `set -e` in the `test-coverage` template (proven with a deliberate failure); `[coverage]`/`[test-coverage]` enabled and `createcoverage` dropped; `coverage = 5.5` pinned; browser tests on a **ZSERVER-free** `FunctionalTesting(bases=(FIXTURE,))` — the currently-defined `FUNCTIONAL_TESTING` drags in `z2.ZSERVER_FIXTURE`, which binds a real TCP port that in-process `z2.Browser` does not need; `bin/code-analysis` to 0 (~40 findings) so the pre-commit hook stops training people to use `--no-verify`.
**Budget for revealed failures:** `plone.testing 4.1.3` has **no** isolation guard, so `tests/base.py:_install()`'s quickinstaller commit currently leaks state into every later test in the layer — some tests pass *because* of that leak. Those failures are real bugs being revealed, not caused. Also: `applyProfile` does not call `installProduct`, so `test_product_is_installed` may fail on an otherwise-correct change — assert installedness by things you control (plugin registered for `IAuthenticationPlugin`, registry records exist, browser layer active), which is also what catches the Broken-ZODB pitfall.
**Re-baseline the gate against the corrected number. Do not tune `.coveragerc` until 90% appears.**

### Same-Commit Requirements (do not let the roadmap split these)

| Must ship together | Why |
|---|---|
| Drift `{T, T−1}` **+** replay rejection | Same six lines. Splitting yields drift-accepted-but-replay-undetected: **strictly worse than today.** |
| Override deletion **+** `next_url` open-redirect fix | Deleting `login_form.cpt` restores Plone's `came_from` field and changes what `ICameFrom` sees. |
| Fernet encryption **+** fail-closed **+** local QR **+** `ipaddress` swap | Fail-closed is the one mistake that silently undoes encryption; QR-to-Google makes encryption worthless; `cryptography` forces the `ipaddress` swap. |
| `.coveragerc` fix **+** `set -e` | Both must precede any new test, or the gate measures nothing and green means nothing. |
| `imio.helpers` in `install_requires` **+** the rename | It is the only thing that surfaces the `imio` namespace-package mistake before deployment. |

### Phase Ordering Rationale

- **Rename first** because P3 (Broken ZODB objects) is LOW recovery cost now and HIGH after deployment, and because the rename touches every file.
- **`_dont_swallow_my_exceptions` in the rename phase, not the encryption phase.** It is the guard that converts every later phase's mistakes from silent bypasses into 500s. One line, earliest possible commit.
- **Registry before encryption** because the encryption key is read on a code path the registry seeding bug destabilises, and a `KeyError` from `get_app_settings()` is swallowable.
- **PAS boundary before memberdata state** because it defines which code paths commit.
- **Lockout before recovery codes** because recovery codes must share the counter.
- **Encryption in parallel** because it shares no code and has the longest external lead time.
- **Coverage last, infra-first-within-itself**, because it is instrumentation for work that must already exist.

### Research Flags

**Needs research during planning: none.** ARCHITECTURE states this explicitly — every mechanism is pinned to a file:line in an installed egg, and STACK verified every version claim by execution or PyPI metadata. All four researchers worked from primary source.

Standard patterns / skip `--research-phase`:
- **P1 Rename** — mechanical; PITFALLS supplies a complete "looks done but isn't" checklist.
- **P2 Registry** — root cause traced to `tool.py:269-276` / `utils.py:856-905`; fix is a `<depends>` and a lazy accessor.
- **P3 PAS boundary** — full publish path traced with line numbers.
- **P4/P5 state + recovery codes** — parameters fixed by RFC/NIST/ASVS, APIs executed.
- **PW Encryption** — Fernet API surface executed, every exception type confirmed.
- **P6 Overrides** — `overlayhelpers.js` and `popupforms.js` read; all three alternative escapes tested against source and rejected.
- **P7 Coverage** — both defects quoted verbatim from `base.cfg` and `.coveragerc`.

What remains are **implementation-time verification items**, not research (below).

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | **HIGH** | Every version from PyPI `cp27`/`py2.py3` release metadata with upload dates; every API executed in this repo's own `bin/python` against `/srv/cache/eggs`; quoted output is real. Two claims self-labelled MEDIUM (below). |
| Features | **MEDIUM–HIGH** | Standards quoted verbatim from the publishers and cross-corroborated (MEDIUM per the researcher's own label); vendor defaults corroborated across ≥2 sources; local codebase facts read directly (HIGH). The parameter *choices* (N=5, 900 s, 10 codes) are calibrated judgements, defensible but not derived. |
| Architecture | **HIGH** | Read from the exact eggs `bin/instance` resolves — `PluggableAuthService-1.11.3`, `Zope2-2.13.30`, `PlonePAS-5.1.1`, `CMFPlone-4.3.20`, `plone.session-3.5.6`, `plone.app.jquerytools-1.9.5` — with line numbers, plus `diff` of both vendored overrides against upstream. |
| Pitfalls | **HIGH** | Read from the pinned eggs or reproduced on this machine (the orphan-`.pyc` import was actually run). Three items self-labelled MEDIUM (below). |

**Overall confidence:** HIGH

### Carried-Forward MEDIUM Caveats (not laundered into certainty)

- **PBKDF2 at 100 000 iterations** — MEDIUM. Timings measured on *this* machine; a slower production host scales linearly. Any value in 20k–200k is defensible. Not load-bearing: the codes are 40–80-bit random values with no dictionary to walk.
- **Suggested memberdata property types** — MEDIUM. They follow Plone 4.3 conventions and the existing file, but no GenericSetup import was executed to confirm `float` and `lines` behave for these fields. **Smoke-test in P4.** (ARCHITECTURE independently suggests `int` epoch over `float` or `date` for locked-until, to avoid `DateTime` round-tripping — prefer `int`.)
- **The site-creation-vs-add-on-install asymmetry in the registry bug** — MEDIUM. The `set`-hash explanation is HIGH; *which* of the four nested-`runImportStepFromProfile` mechanisms fires on this specific path is MEDIUM. Settle it with one command (`getSortedImportSteps()` + `grep "Cannot find registry" var/log/instance.log`) rather than guessing. The recommended fix does not depend on the answer.
- **`plone.app.jquery` overlay behaviour** — MEDIUM in PITFALLS, upgraded to HIGH by ARCHITECTURE's line-by-line read of `overlayhelpers.js` 1.9.5's success/noform/redirect switch. Still needs one browser test (below).

### Gaps to Address

- **`ska` tolerance of the injected `ajax_load` parameter.** `pb.add_ajax_load` prepends a hidden `ajax_load=<timestamp>` input and `pb.ajax_click` appends it to the GET. It *should* be ignored (`validate_signed_request_data` reads named keys), but a signature failure here is **silent from the user's side**. → One test in P6.
- **`common_content_filter` reaching the wrapped z3c.form.** `plone.z3cform.layout`'s `wrap_form` renders inside `#content` and `el.find()` is a descendant search, so it should be reachable. → Confirm in a browser test in P6, via the header "Log in" link.
- **Whether `credentials_basic_auth` can be deactivated for `IExtractionPlugin`.** The genuinely order-independent fix, at the cost of WebDAV/FTP/XML-RPC password auth. → **Confirm with `imio.dms.mail` before doing it** (P3).
- **QR route final call.** Conflict 1 above; the roadmap must decide, and whichever way it goes, record the accepted cost rather than leaving it undiscovered.
- **The Puppet `concat::fragment`** in the `industrialisation` repo — outside this roadmap's commits. Already in PROJECT.md Constraints; it is the one dependency a roadmap silently drops.
- **`memberdata_properties.xml` `float`/`lines` behaviour** — see the MEDIUM caveat above.
- **Post-fix coverage baseline is unknown.** Cannot be estimated before `[run] source` lands; do not commit to a number until the corrected report exists.

## Sources

### Primary (HIGH confidence)
- **Executed in this repo's interpreter** `/srv/src/imio.googleauthenticator/bin/python` (2.7.18) against `/srv/cache/eggs/`: `cryptography 3.3.2` (full Fernet round-trip, all four exception types), `coverage 5.5`, `onetimepass 0.2.2` (working `matched_window`), `py2_ipaddress 3.4.2` vs `ipaddress 1.0.23` in both `sys.path` orderings, `qrcode 6.1` (real PNG + SVG), `Pillow 6.2.2`, stdlib `hashlib`/`hmac`/`os.urandom`/`sqlite3`; and the orphan-`.pyc` import.
- **Source read from the exact pinned eggs:** `Products.PluggableAuthService-1.11.3` (`validate` :240, `_extractUserIds` :577/:602/:648/:675, `_findUser` :760, `challenge` :1152, `_unauthorized` :1140, all 22 interfaces in `interfaces/plugins.py`), `Products.PluginRegistry-1.4.1`, `Zope2-2.13.30` (`ZPublisher/Publish.py`, `HTTPResponse.py`, `HTTPRequest.py`, `Zope2/App/startup.py`, `Startup/handlers.py:127-129`), `Products.PlonePAS-5.1.1` (`setuphandlers.py:195-244`, `config.py:5-10`, `plugins/property.py`, `sheet.py`), `Products.CMFPlone-4.3.20` (`skins/plone_login/*`, `popupforms.js:76-98`), `plone.session-3.5.6`, `plone.app.jquerytools-1.9.5` (`overlayhelpers.js`), `Products.GenericSetup-1.8.11` (`tool.py`, `utils.py`, `zcml.py`, `registry.py`), `plone.registry-1.0.5`, `plone.app.registry-1.2.5`, `Products.CMFQuickInstallerTool-3.0.16`, `plone.testing-4.1.3`/`5.0.0`, `plone.app.testing-4.2.7`, `createcoverage-1.5`, `imio.helpers-1.3.15` (`barcode.py`, `__init__.py:44-55`).
- **PyPI JSON release metadata** — `cryptography`, `coverage`, `qrcode`, `cffi`, `enum34`, `ipaddress`, `createcoverage`, filtered on `cp27`/`py2.py3` files with upload dates.
- **`zint 2.13.0`** on this host — `zint -t` confirms type 58 QRCODE; `--input=/dev/stdin` rejected with Error 79.
- **This checkout** — `setup.py`, `base.cfg`, `test-4.3.cfg`, `.coveragerc`, `MANIFEST.in`, `.gitignore`, `cleanup.sh`, `parts/instance/etc/zope.conf`, all `profiles/**`, `skins/**`, `browser/static/**`, `pas_plugin.py`, `helpers.py`, `setuphandlers.py`, `browser/forms/token.py`, `.planning/PROJECT.md`, `.planning/codebase/{ARCHITECTURE,STACK,CONCERNS,TESTING}.md`.
- **`buildout.plonetest/qa.cfg`** — fetched to confirm it sets no `coverage` pin.
- RFC 6238 §5.2/§6, RFC 4226 §4 R6/§7.3/§7.4, NIST SP 800-63B §5.1.2.2/§5.2.2, OWASP ASVS 4.0 V2, OWASP WSTG 4.11 — quoted verbatim from the publishers.
- [PAS eats exceptions — Plone 4.3 docs](https://4.docs.plone.org/old-reference-manuals/pluggable_authentication_service/pas-eats-exceptions.html) — corroborates `_dont_swallow_my_exceptions`.

### Secondary (MEDIUM confidence)
- Real vulnerabilities in this exact bug class: Vikunja GHSA-p747-qc5p-773r (CVSS 5.7), SBA-ADV-20240617-01 (Craft CMS), SBA-ADV-20240202-02 (Craft two-factor plugin).
- Vendor defaults, each corroborated across ≥2 sources: Keycloak (`lookAheadWindow` 1, `failureFactor` 30, `maxFailureWaitSeconds` 900, 12 recovery codes), django-otp (`tolerance` 1, `THROTTLE_FACTOR` 1), GitHub (16×10), Google (10×8), GitLab (10×16).
- Legacy/basic-auth MFA bypass class (BAV2ROPC / M365) — Red Canary, Kroll.
- [GenericSetup — Plone 4.3 docs](https://4.docs.plone.org/develop/addons/components/genericsetup.html) — `pre_handler`/`post_handler` from 1.8.2+, `forInterface(check=False)`/`omit`.

### Tertiary (LOW confidence)
- None relied upon. Nothing in the roadmap implications above rests on a single unverified source.

### Detail
- [STACK.md](STACK.md) · [FEATURES.md](FEATURES.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [PITFALLS.md](PITFALLS.md)

---
*Research completed: 2026-07-28*
*Ready for roadmap: yes — with three PROJECT.md corrections to apply first*
