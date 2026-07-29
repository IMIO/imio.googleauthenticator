# Requirements: imio.googleauthenticator

**Defined:** 2026-07-28
**Core Value:** A second factor that actually holds for in-site users, and that can be deployed alongside `imio.dms.mail` without colliding with it.

Parameters below are not invented — they trace to RFC 6238, RFC 4226, NIST SP 800-63B and OWASP
ASVS V2, and to APIs executed against this repo's own Python 2.7.18 interpreter. See
`.planning/research/SUMMARY.md`.

## v1 Requirements

### Rename (RENAME)

- [x] **RENAME-01**: Package is `imio.googleauthenticator` on disk (`src/imio/googleauthenticator/`), in `setup.py`, and in the egg name, with `namespace_packages=['imio']` and a `declare_namespace` boilerplate `src/imio/__init__.py`
- [x] **RENAME-02**: All dotted references updated — `configure.zcml`, `overrides.zcml`, the registry interface path, `MessageFactory`, logger names, and the `IUserDataSchemaProvider` registration
- [x] **RENAME-03**: Dutch translation survives the rename — `locales/*.pot` and `locales/nl/**` are `git mv`-ed to the new domain filenames and stale `.mo` files deleted, because the i18n domain is taken from the filenames rather than from `i18n_domain`
- [x] **RENAME-04**: GenericSetup profile marker file is renamed alongside the string it is compared to, so `setupVarious` does not silently return and skip PAS plugin installation
- [x] **RENAME-05**: `++resource++` prefixes in `jsregistry.xml` and `cssregistry.xml` match the new package name
- [ ] **RENAME-06**: `MANIFEST.in`'s eight hardcoded `src/collective/...` paths updated, verified by building an sdist and confirming it contains `profiles/`, `locales/` and templates
- [x] **RENAME-07**: Build and tooling config updated — `.coveragerc`, `base.cfg` (`package-name`, `[code-analysis] directory`), `cleanup.sh`, and `testing.py`'s `installProduct` string and layer constants
- [x] **RENAME-08**: Stale artefacts purged — all 27 git-ignored `.pyc` files under the old namespace and the `collective.googleauthenticator.egg-info` directory, so the old namespace is no longer importable from an orphan `.pyc`
- [x] **RENAME-09**: `upgrades/` is deleted, having only ever applied to sites installed at ≤0.3.0
- [ ] **RENAME-10**: PAS plugin `meta_type` and `PAS_TITLE` renamed; `PAS_ID` (`google_auth`) deliberately unchanged
- [ ] **RENAME-11**: `_dont_swallow_my_exceptions = True` on the plugin class, so a plugin exception becomes a 500 rather than a silent fallthrough to password-only authentication
- [x] **RENAME-12**: A test asserts the plugin is registered for `IAuthenticationPlugin`, catching both a broken rename and a `Broken`-object ZODB

### Site creation and registry (REG)

- [ ] **REG-01**: Creating a new Plone site with the add-on selected completes without the `ska_secret_key ... no record` error
- [ ] **REG-02**: The `<depends name="plone.app.registry"/>` declaration makes the import-step ordering explicit rather than dependent on Python 2 `set` iteration order
- [ ] **REG-03**: A test asserts `getSortedImportSteps()` places this package's step after `plone.app.registry` — the ordering assertion, not the rename, is the control
- [ ] **REG-04**: The nested `runImportStepFromProfile` call is gone; `ska_secret_key` is minted by a lazy accessor on first use
- [ ] **REG-05**: Re-applying the default profile leaves an existing `ska_secret_key` unchanged, so signed URLs in flight are not invalidated

### Secret handling (SEC)

- [ ] **SEC-01**: TOTP seeds are Fernet-encrypted at rest; no plaintext seed is ever written to a memberdata property
- [ ] **SEC-02**: The encryption key is read per-call from the process environment, never stored in the ZODB, a memberdata property, a log line, or an exception message
- [ ] **SEC-03**: Enrollment and validation both fail closed when the key is missing or invalid — login is refused, never downgraded to plaintext or to password-only
- [ ] **SEC-04**: Ciphertext carries a `v1$` version prefix
- [ ] **SEC-05**: The enrollment QR code is rendered in-process by `qrcode == 6.1`; the seed is transmitted to no external service and appears in no subprocess argv
- [ ] **SEC-06**: New seeds are 160 bits of `os.urandom`, satisfying RFC 4226 §4 R6's 128-bit minimum
- [ ] **SEC-07**: The required environment variable is documented and present in all four places it must exist — `[instance]`, `[testenv]`, the CI workflow, and (out of repo) the Puppet fragment
- [ ] **SEC-08**: A missing key logs CRITICAL at process start rather than raising from module import or ZCML

### Second-factor integrity (MFA)

- [ ] **MFA-01**: A user with 2FA enabled cannot authenticate via `Authorization: Basic` without the second factor
- [ ] **MFA-02**: Refusal does not leak the protected resource — no response body is served alongside the redirect
- [ ] **MFA-03**: Plugin ordering is set explicitly with `movePluginsTop`, and a test asserts this package's plugin is first among `IAuthenticationPlugin`
- [ ] **MFA-04**: One veto test per credentials extractor — form POST and HTTP Basic — each asserting no session is granted
- [ ] **MFA-05**: A TOTP code from the immediately preceding time step is accepted (one step of drift, RFC 6238 §6)
- [ ] **MFA-06**: A TOTP code already consumed is rejected on reuse (RFC 6238 §5.2 MUST NOT), and the rejection is logged without the username in plaintext
- [ ] **MFA-07**: Only exactly-6-digit input is treated as a candidate token
- [ ] **MFA-08**: After N consecutive failed second-factor attempts the account is locked for the configured duration, and the lock is checked before the token is evaluated so a locked account is not an oracle
- [ ] **MFA-09**: The lock expires on its own; no admin action is required
- [ ] **MFA-10**: N and the lock duration are editable in the control panel, defaulting to 5 and 900 seconds
- [ ] **MFA-11**: A successful second factor resets the failure counter
- [ ] **MFA-12**: No second-factor state is written from the PAS plugin or a challenge plugin; all writes happen in the token form view, which is the only path that commits
- [ ] **MFA-13**: Every new memberdata property has a `memberdata_properties.xml` entry and a set/get round-trip test, since undeclared properties are silently discarded

### Recovery codes (RECOV)

- [ ] **RECOV-01**: Enrollment issues 10 single-use recovery codes of 80 bits each (16 base32 characters from `os.urandom(10)`)
- [ ] **RECOV-02**: Codes are stored hashed with one salt per user; the plaintext codes are never stored
- [ ] **RECOV-03**: Codes are displayed exactly once, at enrollment, and never redisplayed
- [ ] **RECOV-04**: A recovery code is accepted in place of a TOTP token, and is consumed on use
- [ ] **RECOV-05**: Recovery-code attempts increment the same failure counter as TOTP attempts, so they are not an unthrottled path
- [ ] **RECOV-06**: The user can regenerate the whole set, invalidating all previous codes
- [ ] **RECOV-07**: The user is warned when 3 or fewer codes remain

### Coexistence with imio.dms.mail (COEX)

- [ ] **COEX-01**: `TokenForm` carries `id = 'login_form'` so Plone's stock overlay finds it with no vendored JavaScript
- [ ] **COEX-02**: The `login_form.cpt` override and its `.metadata` are deleted
- [ ] **COEX-03**: The vendored `popupforms.js` copy, its `jsregistry.xml` entries, and the `remove="True"` line that permanently unregisters Plone's own resource are all deleted
- [ ] **COEX-04**: `control_panel_extra.html` and `request_bar_code_reset_email.pt` still work, converted to `ViewPageTemplateFile` — they are reached by `restrictedTraverse` and are not overrides
- [ ] **COEX-05**: The skin layer, `skins.xml`, `registerDirectory` and the `skins/` directory are gone
- [ ] **COEX-06**: A real `profiles/uninstall/` restores anything the install profile changed
- [ ] **COEX-07**: Installing this package alongside `imio.dms.mail` leaves both working regardless of install order, verified with both orders
- [ ] **COEX-08**: The challenge fires on both paths — `IChallengePlugin` for requests ending in `Unauthorized`, and an `IPubBeforeCommit` subscriber for the login-form POST, which returns HTTP 200
- [ ] **COEX-09**: Login through the header "Log in" link (not a direct POST) reaches the token form and completes

### Known bug fixes (BUG)

- [ ] **BUG-01**: `next_url` is validated against the portal URL before redirect; an off-site value is refused (`token.py:112-113`)
- [ ] **BUG-02**: `redirect_url` is always bound on every code path through `user_setup.py`
- [ ] **BUG-03**: The bar-code reset token comparison is constant-time, with both operands encoded first to avoid `TypeError` across `str`/`unicode`
- [ ] **BUG-04**: The derived `ska` key separates its components rather than concatenating them bare
- [ ] **BUG-05**: `py2-ipaddress` is replaced by `ipaddress == 1.0.23`, with `unicode` coercion at the two call sites, so adding `cryptography` cannot break every login through module shadowing
- [ ] **BUG-06**: Query-string values are URL-encoded on the way in, resolving the `+`-escaping FIXME

### Quality (QUAL)

- [ ] **QUAL-01**: `.coveragerc` declares `[run] source`, `omit = */tests/*` and `branch = True`, so the figure reflects package code actually exercised
- [ ] **QUAL-02**: `bin/test-coverage` fails the build when tests fail — proven with a deliberately failing test, not by inspection
- [ ] **QUAL-03**: The `[coverage]` and `[test-coverage]` buildout parts are enabled, `coverage == 5.5` pinned, and the redundant `createcoverage` removed
- [ ] **QUAL-04**: Branch coverage is above 90% against the corrected instrument, enforced in CI
- [ ] **QUAL-05**: Browser tests run on a ZSERVER-free `FunctionalTesting` layer, with the in-layer quickinstaller workaround replaced by `applyProfile` in `setUpPloneSite`
- [ ] **QUAL-06**: `bin/code-analysis` exits 0, so the buildout's pre-commit hook stops training contributors to use `--no-verify`
- [ ] **QUAL-07**: Installedness is asserted through things the package controls (plugin registered, registry records present, browser layer active) rather than through `portal_quickinstaller`

### Documentation (DOC)

- [ ] **DOC-01**: The Zope-root limitation is documented — MFA covers users and site admins inside the Plone site; root `acl_users` admins are architecturally out of reach for an in-site PAS plugin
- [ ] **DOC-02**: The basic-auth consequence is documented, naming the supported alternative for scripts and API consumers
- [ ] **DOC-03**: The required encryption-key environment variable is documented for deployment, including the failure mode when a single ZEO client has a stale value
- [ ] **DOC-04**: `CHANGES.txt` records the rename and that existing databases are discarded rather than migrated

## v2 Requirements

Acknowledged, not in this roadmap.

### Notifications

- **NOTF-01**: Email the user on account lockout (ASVS 2.2.3)
- **NOTF-02**: Email the user when a recovery code is used
- **NOTF-03**: Never email per failed attempt — mail-flood amplification

### Key management

- **KEY-01**: `MultiFernet` key rotation without re-enrollment. A `ponytail:` comment marks the upgrade path

## Out of Scope

| Feature | Reason |
|---------|--------|
| Python 3 migration | Keycloak replaces this package before it would pay off |
| Plone 5 / Plone 6 support | Same; this package dies with Plone 4 |
| Zope root / emergency admins | An in-site PAS plugin never runs for the root `acl_users`; `_tryEmergencyUserAuthentication` bypasses every plugin by construction |
| WebAuthn / U2F / SMS fallback | Recovery codes cover the lost-device case far more cheaply |
| `onetimepass` → `pyotp` | Unnecessary: `get_hotp(secret, intervals_no=i)` already exposes the window counter replay detection needs |
| Async bulk enable/disable | iMio sites are far from the ~10k users where the current loop times out |
| Performance caching (IP ranges, user properties, registry) | No observed problem at current scale |
| Lifting the `ska` 1.7.5 pin | Already the last release supporting Python 2.7 |
| "Remember this device" | Weakens the second factor for a convenience nobody asked for |
| Admin-unlock-only lockout | A DoS primitive — 5 requests would permanently lock any known username |
| Redisplaying or emailing recovery codes | Defeats the point of showing them once |
| Progressive backoff, CAPTCHA, 8-digit OTP, adaptive/geo MFA | Gold-plating for a package with a 2-year life |
| Distinguishing "wrong password" from "wrong token" in responses | Username and enrollment-state oracle |
| Making HTTP Basic Auth work *with* a second factor | Not possible in a single round trip; the answer is a service account |
| Completing the unused `hashed` parameter on `get_secret` | Cosmetic |

## Open Decisions

Deliberately deferred to the phase that can settle them with evidence, rather than guessed now.

| Decision | Settled in | How |
|----------|-----------|-----|
| Whether to deactivate the `credentials_basic_auth` extractor outright — the only order-independent fix, at the cost of site-wide WebDAV/FTP/XML-RPC password auth | MFA phase | Check `imio.dms.mail` and `server.dmsmail` for basic-auth dependence, then choose |
| Whether `ska` tolerates the `ajax_load` parameter the overlay injects | COEX phase | One browser test; a signature failure here would be silent from the user's side |
| PBKDF2 iteration count for recovery codes | RECOV phase | Any value in 20k–200k is defensible; not load-bearing for 80-bit random codes |
| `memberdata_properties.xml` types for the new counters | MFA phase | Smoke-test the GenericSetup import; prefer an `int` epoch over `float`/`date` |

## Traceability

Populated during roadmap creation. Ordered by category so cross-checking against the requirement
lists above is mechanical. Phase names are in `.planning/ROADMAP.md`.

| Requirement | Phase | Status |
|-------------|-------|--------|
| RENAME-01 | Phase 1 | Complete |
| RENAME-02 | Phase 1 | Complete |
| RENAME-03 | Phase 1 | Complete |
| RENAME-04 | Phase 1 | Complete |
| RENAME-05 | Phase 1 | Complete |
| RENAME-06 | Phase 1 | Pending |
| RENAME-07 | Phase 1 | Complete |
| RENAME-08 | Phase 1 | Complete |
| RENAME-09 | Phase 1 | Complete |
| RENAME-10 | Phase 1 | Pending |
| RENAME-11 | Phase 1 | Pending |
| RENAME-12 | Phase 1 | Complete |
| REG-01 | Phase 2 | Pending |
| REG-02 | Phase 2 | Pending |
| REG-03 | Phase 2 | Pending |
| REG-04 | Phase 2 | Pending |
| REG-05 | Phase 2 | Pending |
| SEC-01 | Phase 3 | Pending |
| SEC-02 | Phase 3 | Pending |
| SEC-03 | Phase 3 | Pending |
| SEC-04 | Phase 3 | Pending |
| SEC-05 | Phase 3 | Pending |
| SEC-06 | Phase 3 | Pending |
| SEC-07 | Phase 3 | Pending |
| SEC-08 | Phase 3 | Pending |
| MFA-01 | Phase 4 | Pending |
| MFA-02 | Phase 4 | Pending |
| MFA-03 | Phase 4 | Pending |
| MFA-04 | Phase 4 | Pending |
| MFA-05 | Phase 5 | Pending |
| MFA-06 | Phase 5 | Pending |
| MFA-07 | Phase 5 | Pending |
| MFA-08 | Phase 5 | Pending |
| MFA-09 | Phase 5 | Pending |
| MFA-10 | Phase 5 | Pending |
| MFA-11 | Phase 5 | Pending |
| MFA-12 | Phase 5 | Pending |
| MFA-13 | Phase 5 | Pending |
| RECOV-01 | Phase 6 | Pending |
| RECOV-02 | Phase 6 | Pending |
| RECOV-03 | Phase 6 | Pending |
| RECOV-04 | Phase 6 | Pending |
| RECOV-05 | Phase 6 | Pending |
| RECOV-06 | Phase 6 | Pending |
| RECOV-07 | Phase 6 | Pending |
| COEX-01 | Phase 7 | Pending |
| COEX-02 | Phase 7 | Pending |
| COEX-03 | Phase 7 | Pending |
| COEX-04 | Phase 7 | Pending |
| COEX-05 | Phase 7 | Pending |
| COEX-06 | Phase 7 | Pending |
| COEX-07 | Phase 7 | Pending |
| COEX-08 | Phase 4 | Pending |
| COEX-09 | Phase 7 | Pending |
| BUG-01 | Phase 7 | Pending |
| BUG-02 | Phase 3 | Pending |
| BUG-03 | Phase 3 | Pending |
| BUG-04 | Phase 2 | Pending |
| BUG-05 | Phase 3 | Pending |
| BUG-06 | Phase 7 | Pending |
| QUAL-01 | Phase 8 | Pending |
| QUAL-02 | Phase 8 | Pending |
| QUAL-03 | Phase 8 | Pending |
| QUAL-04 | Phase 8 | Pending |
| QUAL-05 | Phase 8 | Pending |
| QUAL-06 | Phase 8 | Pending |
| QUAL-07 | Phase 8 | Pending |
| DOC-01 | Phase 4 | Pending |
| DOC-02 | Phase 4 | Pending |
| DOC-03 | Phase 3 | Pending |
| DOC-04 | Phase 1 | Pending |

**Coverage:**

- v1 requirements: 71 total
- Mapped to phases: 71
- Unmapped: 0 (every v1 requirement maps to exactly one phase)

**Count correction:** this section previously read "61 total". That was a miscount. The actual total
is 71: RENAME 12 + REG 5 + SEC 8 + MFA 13 + RECOV 7 + COEX 9 + BUG 6 + QUAL 7 + DOC 4 = 71. No
requirement was added, removed or reworded during roadmapping.

**Per-phase distribution:**

| Phase | Requirements | Count |
|-------|--------------|-------|
| 1 - Rename and Fail-Closed | RENAME-01..12, DOC-04 | 13 |
| 2 - Registry Seeding and Import-Step Ordering | REG-01..05, BUG-04 | 6 |
| 3 - Encrypted Seeds and Local QR | SEC-01..08, BUG-02, BUG-03, BUG-05, DOC-03 | 12 |
| 4 - PAS Boundary | MFA-01..04, COEX-08, DOC-01, DOC-02 | 7 |
| 5 - Drift, Replay and Lockout | MFA-05..13 | 9 |
| 6 - Recovery Codes | RECOV-01..07 | 7 |
| 7 - Coexistence with imio.dms.mail | COEX-01..07, COEX-09, BUG-01, BUG-06 | 10 |
| 8 - Coverage Instrument and Test Layers | QUAL-01..07 | 7 |

**Two cross-category placements worth noting:**

- **COEX-08** (the challenge fires on both the `IChallengePlugin` path and the `IPubBeforeCommit`
  login-POST path) sits in **Phase 4**, not the coexistence phase. It is the two-hook redirect
  design, which the research delivers in the PAS-boundary phase; Phase 7's overlay work is verified
  *against* it rather than building it.

- **MFA-12** (no second-factor state written from the PAS plugin or a challenge plugin) sits in
  **Phase 5**, not Phase 4. Phase 4 establishes the token form as the sole grant point, but the
  invariant only becomes assertable once Phase 5 introduces state to write.

**Where the four Open Decisions land:** Phase 4 (`credentials_basic_auth` deactivation), Phase 5
(`memberdata_properties.xml` counter types), Phase 6 (PBKDF2 iterations), Phase 7 (`ska` vs
`ajax_load`). Each is an explicit task in its phase, not an assumption.

---
*Requirements defined: 2026-07-28*
*Last updated: 2026-07-28 after roadmap creation (traceability populated, coverage count corrected 61 -> 71)*
