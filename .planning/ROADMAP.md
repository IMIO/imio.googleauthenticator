# Roadmap: imio.googleauthenticator

## Overview

Eight phases take a forked, undeployed Plone 4.3 PAS plugin from "plaintext seeds and skin
overrides that collide with `imio.dms.mail`" to "a second factor that actually holds." The order is
not negotiable and is not arbitrary: the rename touches every file so it goes first (carrying the
one-line `_dont_swallow_my_exceptions` guard that converts every later phase's mistakes from silent
2FA bypasses into 500s); the registry seeding fix precedes encryption because the key is read on a
code path the seeding bug destabilises; encryption comes early because its one non-code dependency
— a Puppet `concat::fragment` in the separate `industrialisation` repo — has the longest lead time
in the milestone; the PAS boundary precedes the memberdata counters because it establishes which
code paths commit; the lockout counter precedes recovery codes because recovery codes must share
it; the override deletion follows the PAS boundary so the overlay is only ever exercised against
the final redirect mechanism; and coverage is last because it is instrumentation for work that must
already exist.

Every dominant risk in this project is a **silent** one — a swallowed exception, an aborted
transaction, a popped memberdata property, an orphan `.pyc`, a coverage gate measuring nothing.
That is why so many success criteria below are phrased as "a test asserts X": for MFA-03, REG-03
and RENAME-12 the requirement text itself names the test as the security control, because the
failure mode has no error page and no log line.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Rename and Fail-Closed** - `imio.googleauthenticator` everywhere, and a plugin exception becomes a 500 instead of a password-only login (completed 2026-07-29)
- [x] **Phase 2: Registry Seeding and Import-Step Ordering** - New Plone sites install cleanly, and the ordering that makes them clean is asserted rather than accidental (completed 2026-07-29)
- [x] **Phase 3: Encrypted Seeds and Local QR** - Seeds are Fernet-encrypted at rest, never sent to Google, and never fall back to plaintext (completed 2026-07-30)
- [x] **Phase 4: PAS Boundary** - The second factor cannot be bypassed by any credentials extractor, and the refusal leaks nothing (completed 2026-07-31)
- [x] **Phase 5: Drift, Replay and Lockout** - A replayed code fails, brute force stops at N attempts, and the counters actually persist (completed 2026-08-03)
- [x] **Phase 6: Recovery Codes** - A user who loses their phone gets back in without an admin, on a throttled path (completed 2026-08-04)
- [ ] **Phase 7: Coexistence with imio.dms.mail** - Both packages install in either order with no vendored JavaScript, no skin layer, and no open redirect
- [ ] **Phase 8: Coverage Instrument and Test Layers** - The build fails when tests fail, the coverage number means something, and `bin/code-analysis` exits 0

## Phase Details

### Phase 1: Rename and Fail-Closed

**Goal**: The package is `imio.googleauthenticator` everywhere — on disk, in the egg, in the i18n domain, in the GenericSetup profile and its marker file — and any exception inside the PAS plugin becomes a 500 rather than a silent fallthrough to password-only authentication.
**Depends on**: Nothing (first phase)
**Requirements**: RENAME-01, RENAME-02, RENAME-03, RENAME-04, RENAME-05, RENAME-06, RENAME-07, RENAME-08, RENAME-09, RENAME-10, RENAME-11, RENAME-12, DOC-04
**Success Criteria** (what must be TRUE):

  1. From a fresh clone, `bin/instance` starts and a new Plone site installs the add-on with the PAS plugin present — and `collective.googleauthenticator` is importable from nowhere, all 27 orphan `.pyc` files and the stale `.egg-info` having been purged.
  2. A test asserts `google_auth` is registered for `IAuthenticationPlugin`. This one test catches both a half-done rename and a `Broken`-object ZODB, whose shared failure mode is 2FA silently not running with no error page.
  3. `python setup.py sdist` produces an archive containing `profiles/`, `locales/` and the templates — the only way to prove `MANIFEST.in`'s eight hardcoded paths were all updated, since a develop-egg reads `src/` directly and hides the breakage until release.
  4. The Dutch translation still renders in the UI: `locales/*.pot` and `locales/nl/**` were `git mv`-ed to the new domain filenames and stale `.mo` files deleted. The i18n domain comes from the filenames, not from `i18n_domain`, so renaming `MessageFactory` alone silently deletes the translation.
  5. `_dont_swallow_my_exceptions = True` is set on the plugin class, and a test asserts a deliberately raised plugin exception yields a 500 rather than authenticating on password alone via `source_users`.

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Move the package, regenerate the buildout, rename every dotted reference and GenericSetup identity; suite green again plus the namespace, plugin-registration and resource assertions

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — i18n domain filenames, a Dutch-renders assertion, the three defective msgids, and new French and English catalogues

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — MANIFEST.in rewrite verified by a real sdist, distribution metadata, CHANGES.rst with DOC-04, build tooling, docs and the developer purge target

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — PAS `meta_type`/title rename in an isolated commit, then `_dont_swallow_my_exceptions` with its fail-closed test

**Phase notes:**

- **Do NOT rename `PAS_ID`** (`google_auth`). It is already namespace-neutral, and renaming it creates a second plugin on any existing ZODB. Rename `PAS_TITLE` and `meta_type` only, and put `meta_type` in its own commit so `registerMultiPlugin`'s duplicate-meta_type `RuntimeError` stays interpretable as "stale artefact" rather than "rename bug".
- `git clean -xdf src/` belongs in the first rename commit; `git mv` moves only tracked files and every `.pyc` is git-ignored.
- `PYTHONDONTWRITEBYTECODE=1` in the test/instance environment, plus `cleanup.sh` updated.
- **Namespace early-warning:** research adjudicated that adding `imio.helpers` to `install_requires` here is the only thing that forces `imio.googleauthenticator` and `imio.helpers` into one process, surfacing an `imio` namespace-package declaration mistake before deployment. PROJECT.md's QR decision was reversed to `qrcode == 6.1`, so `imio.helpers` is no longer pulled in for QR. The substitute the research names explicitly is required instead: an explicit two-package import check (`bin/python -c "import imio.helpers, imio.googleauthenticator"`) in the suite or CI.
- `upgrades/` is deleted (RENAME-09) — it only ever applied to sites installed at ≤0.3.0, of which there are none.
- `bin/code-analysis` is NOT clean until Phase 8, so the buildout's pre-commit hook fails in this and every intervening phase. Accepted cost of cleaning ~40 findings after the code stops moving rather than in files Phases 3–7 rewrite; commits here pass the hook only with `--no-verify`.

### Phase 2: Registry Seeding and Import-Step Ordering

**Goal**: Creating a new Plone site with the add-on selected completes without the `ska_secret_key ... no record` error, and the import-step ordering that makes it complete is asserted in the suite rather than left to CPython 2.7 string-hash order.
**Depends on**: Phase 1
**Requirements**: REG-01, REG-02, REG-03, REG-04, REG-05, BUG-04
**Success Criteria** (what must be TRUE):

  1. Creating a new Plone site with the add-on selected completes with no `IGoogleAuthenticatorSettings defines a field ska_secret_key, for which there is no record` in `var/log/instance.log`.
  2. A test asserts the import step **declares** `plone.app.registry` as a dependency (via `getImportStepMetadata()['dependencies']`), and a second test asserts `getSortedImportSteps()` places this package's step after it. **The declaration assertion is the control, not the rename and not the sorted order** — verified in phase-2 verification: with the `<depends>` line deleted, the sorted-order assertion still passes by CPython 2.7 string-hash accident (index 51 vs 36 of 52), so order alone proves nothing and would flip the first time any other add-on adds or removes an import step.
  3. `grep -r runImportStepFromProfile src/` returns nothing, and `ska_secret_key` is minted without a nested profile import — seeded once at install time by `setuphandlers._setup_secret_key()`, with `get_ska_secret_key()` a pure read. *(Revised after code review CR-02: the original criterion said "minted by a lazy accessor on first use". A mint inside the accessor writes registry state from `authenticateCredentials()`, a path that ends in `transaction.abort()` on `Unauthorized`, discarding the key after a URL signed with it was already redirected to. See `02-REVIEW.md` CR-02 and `02-01-SUMMARY.md`.)*
  4. A test applies the default profile **twice** and asserts `ska_secret_key` is unchanged, so signed URLs in flight are not invalidated by a reinstall. (A retained value that no longer validates is silently replaced by the default `u''`, with only an INFO log line.)
  5. A test asserts the derived `ska` key separates its components: two different component tuples that share the same bare concatenation produce different keys.

**Plans**: 2/2 plans executed

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Declared `<depends name="plone.app.registry"/>`, the nested profile re-entry deleted, `ska_secret_key` minted lazily in `get_ska_secret_key`, and one test asserting ordering, records, mint and profile-re-apply preservation

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Length-prefixed `ska` key derivation with the collision it prevents asserted, plus the `get_browser_hash` empty-string regression guard and the changelog

**Phase notes:**

- The fix is `<depends name="plone.app.registry"/>` on the import step plus deleting the nested `runImportStepFromProfile`. **Never** silence the error with `forInterface(check=False)`.
- Must precede Phase 3: the encryption key is read on a code path this bug destabilises, and a `KeyError` from `get_app_settings()` is one of PAS's swallowable exceptions — i.e. a bypass.
- Which of the four nested-`runImportStepFromProfile` mechanisms fires on the site-creation path is a carried-forward MEDIUM. Settle it with one command (`getSortedImportSteps()` + `grep "Cannot find registry" var/log/instance.log`) rather than guessing; the recommended fix does not depend on the answer.

### Phase 3: Encrypted Seeds and Local QR

**Goal**: A TOTP seed is unreadable from the ZODB, never transmitted to an external service, and never silently downgraded to plaintext — and adding `cryptography` cannot break every login on the site through `ipaddress` module shadowing.
**Depends on**: Phase 2
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-07, SEC-08, BUG-02, BUG-03, BUG-05, DOC-03
**Success Criteria** (what must be TRUE):

  1. A newly enrolled user's seed memberdata property reads as `v1$<fernet-token>`. No plaintext base32 seed appears in the ZODB, in a log line, or in an exception message — and the key appears in none of those either, nor in the registry (QuickInstaller snapshots `portal_setup` before *and* after every install).
  2. Two tests assert login is **refused** with the key unset and refused again with the key set to garbage, at both enrollment and validation — never downgraded to plaintext and never to password-only. Fail-closed is the one mistake that silently undoes the entire phase.
  3. The enrollment QR renders in-process via `qrcode == 6.1`: no request reaches `chart.googleapis.com`, and no subprocess argv carries the seed (the reason `imio.helpers` + zint was rejected — `--data=otpauth://...secret=<SEED>` is readable in `ps` by any local user).
  4. A user enrolls with a real authenticator app and logs in end to end, against a seed that is 160 bits of `os.urandom` (RFC 4226 §4 R6 requires ≥128; `b32encode(str(uuid4()))` gave ~122).
  5. `py2-ipaddress` is gone and `ipaddress == 1.0.23` pinned, with `unicode` coercion at **all three** `ipaddress.*()` call sites in `helpers.py`; a login from a whitelisted CIDR still succeeds. Both distributions install a top-level `ipaddress` module, so without this the site works on a dev box and every login fails on a Puppet-built one, decided by egg ordering. *(Corrected during planning: this criterion previously said two call sites at `helpers.py:459` and `:496`. Those line numbers are stale, and there are three calls — `ip_address(proxies[0])` inside the private-hop strip loop is the third. Missing it is not cosmetic: `AddressValueError` subclasses `ValueError`, so the existing `except ValueError: break` would fire on the first iteration on every request, silently disabling private-hop stripping and making the whitelist trust an attacker-supplied hop.)*

**Plans**: 3/3 plans executed

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — The ROADMAP's own same-commit group: the `cryptography`/`qrcode`/`ipaddress`/`Pillow` pin swap, the `v1$` Fernet envelope with a per-call key read, a 160-bit `os.urandom` seed via stdlib base32, in-process QR rendering, `unicode` coercion at all three `ipaddress` call sites, `[testenv]`'s throwaway key so Wave 1 ends green, and fail-closed asserted at all four live `get_or_create_secret` surfaces — enrollment, login, bulk enable (unswallowed, with both callers reporting failure instead of "Changes saved.") and account creation (SEC-01/02/03/04/05/06, BUG-05)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-02-PLAN.md — The `IProcessStarting` CRITICAL log for a missing key, the SEC-07 four-places accounting settled with this repo owning exactly one site and no `[instance]` placeholder, and `README.rst` documenting all three consequences of a missing key, the ZEO-client-skew failure mode and the out-of-repo Puppet dependency (SEC-07, SEC-08, DOC-03)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-03-PLAN.md — One constant-time reset-token comparison used at both call sites, a regression test locking the `user_setup.py` redirect invariant with no production change, the real-authenticator-app end-to-end human check for success criterion 4, and the changelog (BUG-03, BUG-02)

**Phase notes:**

- **Same commit, non-negotiable:** Fernet + fail-closed + local QR + the `ipaddress` swap (SEC-01/03/05 + BUG-05). Fail-closed silently undoes encryption; a QR posted to Google makes encryption worthless; `cryptography` forces the `ipaddress` swap.
- **Placed here, third, deliberately.** `parallelization: false`, so this runs as an ordinary sequential phase rather than the "parallel workstream" the research describes. It is still early because its one out-of-repo dependency has the longest lead time in the milestone: the encryption-key `concat::fragment` lives in the separate **`industrialisation` repo** and is not one of this roadmap's commits. Code lands and is tested here (tests set the env var themselves); the feature is not *deployable* until that Puppet change ships. **Do not let this fall through.**
- **The key goes in four places, not one** (SEC-07): `[instance]`, `[testenv]` (obviously-fake value), the CI workflow, and the Puppet fragment. It is per-ZEO-client, not per-database — one client with a stale fragment yields non-deterministic `InvalidToken` depending on which client the load balancer picked, with no ZODB-side evidence. DOC-03 documents exactly this failure mode.
- Key access is a per-call plain function doing `os.environ.get()` (SEC-08: log CRITICAL at `IProcessStarting` when absent; never `raise` from module import or ZCML, which is invisible and unpatchable under `bin/test`). This deliberately diverges from `imio.helpers/__init__.py:44-55`'s module-scope pattern — note the divergence so it does not read as an oversight.
- **Two py2 bytes traps that pass a unit test and fail a live site:** `Fernet()` and `decrypt()` reject `unicode` with `TypeError` while Plone coerces memberdata freely between `str`/`unicode` — `.encode('ascii')` before `decrypt`, `.decode('ascii')` before storing. And a malformed base64 key raises `TypeError`, not `ValueError`, so key validation must catch both.
- BUG-03 rides here for the same reason: `hmac.compare_digest` raises `TypeError` across `str`/`unicode`, and the stored and submitted reset tokens differ in type, so the `reset_bar_code.py:104` fix cannot be a naive swap — encode both sides first.
- BUG-02 (`UnboundLocalError` on `redirect_url` at `user_setup.py:96`) rides here because enrollment is being rewritten in this phase anyway.

### Phase 4: PAS Boundary

**Goal**: A user with 2FA enabled cannot obtain a session without the second factor via any credentials extractor, the refusal leaks no protected content, and the challenge fires on both the `Unauthorized` path and the HTTP-200 login POST.
**Depends on**: Phase 1 (which sets the plugin id and `meta_type` the ordering assertion keys on). Sequenced after Phase 3.
**Requirements**: MFA-01, MFA-02, MFA-03, MFA-04, COEX-08, DOC-01, DOC-02
**Success Criteria** (what must be TRUE):

  1. One veto test per credentials extractor — an `__ac_name`/`__ac_password` form POST and an `Authorization: Basic` request — each asserting a 2FA-enabled user is granted **no session**. PAS 1.11.3 accumulates every authenticator's result and returns the first success, so `return None` vetoes nothing; wiping the shared credentials dict is the only veto the 22 plugin interfaces offer.
  2. A test asserts the refusal serves no response body: the protected resource does not render inside the 302. `response.redirect(lock=1)` sets a status and a header but neither clears the body nor stops publishing, so today a request without `-L` reads the page out of the redirect.
  3. A test asserts this package's plugin is **first** among `IAuthenticationPlugin`, with ordering set explicitly by `movePluginsTop` rather than by `movePluginsDown(iface, listPlugins(iface)[:-1])` incidentally bubbling it to position 0. The entire second factor rests on this ordering, so the test is the security control.
  4. The challenge fires on both paths, each with its own test: `IChallengePlugin` for requests ending in `Unauthorized`, and an `IPubBeforeCommit` subscriber for the login-form POST, which returns HTTP 200 and never raises. One hook does not cover both.
  5. An exception inside `authenticateCredentials` wipes the credentials dict and refuses the login rather than falling through to `source_users`; and DOC-01 (Zope-root admins architecturally out of reach) and DOC-02 (the basic-auth consequence, naming the service-account alternative for scripts, WebDAV, FTP and XML-RPC) are written.

**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — Tracer: decide-only `authenticateCredentials`, the shared `send_2fa_redirect`, the `IPubBeforeCommit` subscriber and its ZCML, and the body-emptiness control against a real `HTTPResponse` (MFA-02, COEX-08 login-POST half)
- [x] 04-02-PLAN.md — `movePluginsTop` re-asserted on every profile application, the ordering and no-`protocol` assertions, and the blocking `credentials_basic_auth` decision checkpoint (MFA-03)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-03-PLAN.md — `IChallengePlugin.challenge` for the `Unauthorized` path, one veto assertion per extractor with non-vacuity controls, and the exception-path wipe (MFA-01, MFA-04, COEX-08 challenge half)
- [x] 04-04-PLAN.md — `README.rst` DOC-01/DOC-02 with fact-presence tests, the reconciled ZMI ordering section, and the changelog (DOC-01, DOC-02)

**Phase notes:**

- **Planning found three mechanical errors in `04-RESEARCH.md`**, each verified against the installed egg and recorded in 04-01-PLAN.md's `<research_corrections>`: `response.setBody('')` is a no-op (`HTTPResponse.py:459` returns before assigning `self.body`); the challenge-path redirect needs `lock=1` because `HTTPResponse.exception` runs `setStatus(Unauthorized)` immediately after calling the challenge (`:799-803`); and `request.get('_2fa_pending')` falls through to form data and cookies (`HTTPRequest.py:1250-1255`), making the research's recommended read attacker-settable. Read from `request.other` only.
- **Open Decision to settle here, not assume:** whether to deactivate the `credentials_basic_auth` extractor outright. It is the only genuinely order-independent fix, at the cost of site-wide WebDAV/FTP/XML-RPC password auth. **Check `imio.dms.mail` and `server.dmsmail` for basic-auth dependence FIRST**, then choose and record the choice.
- **Open Decision to settle here:** none other; the `ajax_load` question belongs to Phase 7.
- The design is decision/redirect/grant split: `authenticateCredentials` **decides only** — whitelist check, 2FA check, first-factor verification, wipe the dict, set `request['_2fa_pending']`, return `None`. It never touches `RESPONSE` and **never writes to the ZODB**. Move the credentials wipe to the top of the 2FA branch so it also runs on the exception path.
- `IChallengePlugin.challenge` must be **write-free** — it is reached from `HTTPResponse.exception()`, which runs *after* `transaction.abort()`, so any write there is discarded 100% of the time. **Do not set `protocol = 'http'`**, or WebDAV/FTP/XML-RPC clients get an HTML redirect; set no `protocol` at all.
- Worth a one-line comment: PAS's `_extractUserIds` calls `ZCacheable_get`. Plone 4.3 puts no cache manager on `acl_users` by default, but a cached 2FA bypass is catastrophic if one is ever added.

### Phase 5: Drift, Replay and Lockout

**Goal**: A code from the previous time step still works, a code already used never works again, and brute-forcing the second factor stops after N attempts — with counters that survive the request they are written in.
**Depends on**: Phase 4 (which establishes which code paths commit)
**Requirements**: MFA-05, MFA-06, MFA-07, MFA-08, MFA-09, MFA-10, MFA-11, MFA-12, MFA-13
**Success Criteria** (what must be TRUE):

  1. A test asserts a code from the immediately preceding time step is accepted (RFC 6238 §6), and another asserts a code already consumed is rejected on reuse (RFC 6238 §5.2 MUST NOT). **Both land in one commit** — they are the same six lines on `get_hotp(secret, intervals_no=i)`, and splitting them produces drift-accepted-but-replay-undetected, which is strictly worse than today.
  2. A test asserts the replay rejection is logged, and that the log line carries no plaintext username (ASVS 2.8.4/2.8.5).
  3. A test asserts 5 consecutive failures lock the account for 900 seconds; that the lock is evaluated **before** the token, so a locked account answers identically for a valid and an invalid code and is not an oracle; and that the lock expires on its own with no admin action.
  4. A test asserts a successful second factor resets the failure counter, and that only exactly-6-digit input is treated as a candidate token. This requires a **new** gate in `helpers.py`, checked before `onetimepass` is ever called: the permissive `_is_possible_token` that accepts `"1"` and `"123"` is a private function inside the pinned `onetimepass==0.2.2` egg, so it cannot be patched (corrected during Phase 5 research — the earlier wording implied it lived in this package). N and the duration are editable in the control panel, defaulting to 5 and 900.
  5. Every new memberdata property has a `memberdata_properties.xml` entry and a `setMemberProperties()` → `getProperty()` round-trip test; and a test asserts the failure counter still increments after a request that ends in `Unauthorized`, proving the write lives in the token form view and not on an aborted path.

**Plans**: 5/5 plans executed

Plans:
**Wave 1**

- [x] 05-01-PLAN.md — Memberdata counter substrate, control-panel policy fields, and the lockout wired end to end on the token form (MFA-08..13)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-02-PLAN.md — Drift acceptance, replay rejection and the exact-six-digit gate in `helpers.validate_token`, one commit (MFA-05, MFA-06, MFA-07)
- [x] 05-03-PLAN.md — The same counter and lock on `@@reset-bar-code`, closing the anonymous guessing oracle (MFA-08 reset path, MFA-11, MFA-12)

**Wave 3** *(gap closure, blocked on Wave 2 completion)*

- [x] 05-04-PLAN.md — Move the lockout gate in `token.py` to run after signature validation so an unsigned caller can no longer read account lock state, plus the anonymous no-signature test (MFA-08)

**Wave 4** *(gap closure, additive — all prior plans already executed)*

- [x] 05-05-PLAN.md — Make the locked-account and wrong-code failures at `@@reset-bar-code` emit the same assembled status message, plus the anonymous equality test the 05-03 substring criterion could not catch (MFA-08)

**UI hint**: no

**Phase notes:**

- **MFA-12 is the invariant this phase is built around:** no second-factor state write in the PAS plugin or a challenge plugin, ever. `ZPublisher/Publish.py`'s `finally: transactions_manager.abort()` discards every write on any request ending in an exception, and `Unauthorized` *is* such an exception (`zpublisher_exception_hook` renders the view then re-raises). A lockout counter written in the plugin is a security control that does not work and looks like it does. The token form POST returns 200/302 → `PubBeforeCommit` → `commit()`, and a failed second factor is by definition submitted to the token form.
- **MFA-13 exists because the failure is silent:** `MutablePropertySheet.setProperties` **pops** keys not declared in the sheet, with no error. A forgotten `memberdata_properties.xml` entry means the counter never persists and nothing appears in the log.
- **Open Decision to settle here:** `memberdata_properties.xml` types for the new counters. Smoke-test the GenericSetup import (`float` and `lines` behaviour for these fields was never executed — carried-forward MEDIUM) and prefer an `int` epoch over `float`/`date` to avoid `DateTime` round-tripping.
- The ConflictError worry is a non-issue and PROJECT.md's stated reason for memberdata was wrong: storage is an `OOBTree` keyed by user id, so cross-user writes merge and `retry_max_count = 3` handles same-user parallel brute force correctly (the retry re-reads the fresh counter). The decision stands; the hazard to design against is `transaction.abort()`.
- Control panel follows `imio.dms.mail`'s `RegistryEditForm` + `layout.wrap_form(..., ControlPanelFormWrapper)` pattern.
- N=5 / 900 s ≈ 1042 days expected time-to-hit for a 6-digit code; NIST SP 800-63B §5.2.2's 100 attempts is a ceiling, not a target.
- **Lockout scope decided at plan time (2026-07-31):** the counter and lock cover **both** `browser/forms/token.py` **and** `browser/forms/reset_bar_code.py`, not the token form alone. `reset-bar-code` is registered `permission="zope2.View"`, takes its target account from an attacker-supplied `auth_user` query parameter, and calls `validate_token` at `reset_bar_code.py:109` — *before* it checks the signed `bar_code_reset_token` at line 120, with a distinct error message for each failure. Left unmetered it is an anonymous TOTP guessing oracle, which would make this phase's goal untrue while appearing met. Both are browser form views that return 200/302 and commit, so covering both keeps the MFA-12 invariant intact. `user_setup.py` is deliberately **excluded**: it validates against the enrolling user's own in-progress secret, so a counter there would let a user lock themselves out mid-setup.

### Phase 6: Recovery Codes

**Goal**: A user who loses their authenticator device recovers access themselves, once per code, and that path is throttled exactly like the TOTP path.
**Depends on**: Phase 5 (the shared lockout counter, and the single dispatch point in the token form)
**Requirements**: RECOV-01, RECOV-02, RECOV-03, RECOV-04, RECOV-05, RECOV-06, RECOV-07
**Success Criteria** (what must be TRUE):

  1. Enrollment issues 10 single-use codes of 80 bits each (`os.urandom(10)` → 16 base32 characters), displayed exactly once and never redisplayed; a test asserts the plaintext codes appear nowhere in the ZODB, only a per-user-salted hash.
  2. A test asserts a recovery code is accepted in place of a TOTP token, is consumed on use, and is rejected on a second use.
  3. A test asserts a failed recovery-code attempt increments the **same** counter as a failed TOTP attempt. Without this, recovery codes are the unthrottled brute-force path and Phase 5's lockout is decorative.
  4. The user can regenerate the whole set, and a test asserts every previously issued code stops working.
  5. The user is warned when 3 or fewer codes remain.

**Plans**: 3/3 plans executed

Plans:
**Wave 1**

- [x] 06-01-PLAN.md — Tracer: the recovery-code substrate end to end — two memberdata properties, the hash/generate/validate-and-consume helpers, the promoted `validate_second_factor` dispatcher at the token form's one call site, and a real browser login with a recovery code (RECOV-02, RECOV-04). Opens with a `checkpoint:decision` on the two one-way choices: the PBKDF2 iteration count and the storage shape.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 06-02-PLAN.md — Issue the codes at enrollment, render them exactly once in the same response (no redirect, no stored plaintext), and add a `regenerate_recovery_codes` portal action reusing the existing availability view (RECOV-01, RECOV-03, RECOV-06)
- [x] 06-03-PLAN.md — The shared lockout counter proven at the real form, the "3 or fewer remain" warning on the success path only, and the MFA-12 source guard extended to this phase's new writers (RECOV-05, RECOV-07)

**Phase notes:**

- **Open Decision to settle here:** PBKDF2 iteration count. Any value in 20k–200k is defensible and it is not load-bearing — the codes are 80-bit random values with no dictionary to walk, so iterations are insurance. Timings behind the 100k suggestion were measured on one machine and scale linearly on a slower host (carried-forward MEDIUM).
- **One salt per user, not per code** (PROJECT.md decision). A per-code salt forces N PBKDF2 runs per attempt (10 × 0.113 s ≈ 1.1 s) on a login-adjacent endpoint — a DoS lever. A per-user salt still defeats cross-user rainbow tables, which is all a salt does here.
- Out of scope and staying out: redisplaying codes, emailing codes, emailing on recovery-code use (v2 NOTF-02).

### Phase 7: Coexistence with imio.dms.mail

**Goal**: This package and `imio.dms.mail` install alongside each other in either order and both keep working, with no vendored JavaScript, no skin layer, no resource we do not own being mutated, and no open redirect.
**Depends on**: Phase 4 (so the overlay is only ever exercised against the final redirect mechanism)
**Requirements**: COEX-01, COEX-02, COEX-03, COEX-04, COEX-05, COEX-06, COEX-07, COEX-09, BUG-01, BUG-06
**Success Criteria** (what must be TRUE):

  1. Clicking the header **"Log in" link** — not POSTing to `login_form` — reaches the token form inside Plone's stock overlay and completes the login, with `id = 'login_form'` on `TokenForm` as the only mechanism. A direct-POST testbrowser test passes while the real UI is dead, so the link is the test. 507 vendored lines (`login_form.cpt` 310 + `popupforms.js` 197), `skins.xml`, `registerDirectory` and `skins/` are all gone.
  2. Installing this package and `imio.dms.mail` in **both orders** leaves both working and `popupforms.js` registered exactly once. The `remove="True"` line that permanently unregisters Plone's own resource is deleted — it is a global mutation with no uninstall counterpart, and it is why the collision flips on install order.
  3. Uninstalling the package restores everything the install profile changed, via a real `profiles/uninstall/` with `jsregistry.xml` and `cssregistry.xml` — so uninstalling no longer leaves the whole site without `popupforms.js`.
  4. A test asserts an off-site `next_url` is refused and an on-site one honoured, with query-string values URL-encoded on the way in. **Same commit as the `login_form.cpt` deletion**: the stale copy deleted Plone 4.3.20's `came_from` hidden input, which is the only reason `CameFromAdapter` exists, so removing the copy restores the field and changes what `ICameFrom` sees.
  5. `control_panel_extra.html` and `request_bar_code_reset_email.pt` still render, converted to `ViewPageTemplateFile`, with no `restrictedTraverse` into a skin left in the package.

**Plans**: 2/4 plans executed

Plans:
**Wave 1**

- [x] 07-01-PLAN.md — Tracer: restore Plone's own login overlay (delete the vendored script and the `remove="True"` mutation), make `TokenForm` render the `id` the overlay binds on, prove login through the header link; then delete the `login_form.cpt` override with the `next_url` allowlist guard and the query-string encoding in the same commit (COEX-01, COEX-02, COEX-03, COEX-09, BUG-01, BUG-06)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 07-02-PLAN.md — Convert both live skin templates to `ViewPageTemplateFile` class attributes and delete the skin directory, `skins.xml`, `registerDirectory` and the packaging include in one commit, plus the absence assertions (COEX-04, COEX-05)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 07-03-PLAN.md — A real `profiles/uninstall/` scoped to this package's own two resources, the two-order collision proof, the resource-ownership invariant test, and the README/docs/CHANGES corrections (COEX-06, COEX-07, COEX-03)

**Wave 4** *(blocked on Wave 3 completion, non-autonomous)*

- [ ] 07-04-PLAN.md — The two verifications `bin/test` cannot reach: a real two-egg install in both orders on the `server.dmsmail` MOD-1076 environment, and a real browser click through the stock overlay (COEX-07, COEX-09 manual halves)

**UI hint**: yes

**Phase notes:**

- **Planned 2026-08-04. Three corrections to this section, established by reading the installed egg source — the plans implement the corrected version, not the text below:**
  1. Success criterion 1's "`id = 'login_form'` on `TokenForm` as the only mechanism" is not achievable as written. `z3c.form 3.2.11`'s `Form.id` is a Python property, and `plone.z3cform 0.8.1`'s `titlelessform` macro — used by both the wrapped and the standalone render paths — emits no `id` attribute on the `<form>` tag at all. The class attribute produces no markup. A `render()` override that post-processes the emitted HTML is required; forking the macro would re-vendor what this phase removes. The *rendered* attribute is the only mechanism.
  2. Success criterion 4's causal claim is imprecise: the restored stock `came_from` hidden input lands in `request.form`, whereas `CameFromAdapter.getCameFrom()` reads `HTTP_REFERER`'s **query string**. Restoring the input does not by itself change what `ICameFrom` sees. The same-commit grouping still holds — it is the commit where the whole redirect surface changes — but nothing depends on the restored input feeding the adapter.
  3. The COEX-04 note below says the email path has zero test coverage. It has three tests that drive `handleSubmit` end to end and assert on the rendered mail body, so a missed conversion there **is** caught by CI. The half with genuinely zero coverage is the **control panel**, which no test renders — corrected in `07-VALIDATION.md`, and closed by a new `tests/test_controlpanel.py`. Also: `controlpanel.py:84` is actually line 101, and the skin directory holds **four** files, not five (the vendored script lives under `browser/static/plone_ecmascript/`).
- **Open Decision settled at plan time, no browser test needed to settle it:** `ska 1.7.5` hashes only `auth_user` + `valid_until` (plus an `extra` dict this codebase never populates) — read directly from `ska/utils.py`'s `validate_request_data` and `ska/base.py`'s `Signature.get_base`. Any other query-string key, `ajax_load` included, is never read and never enters the hash. `ska` cannot fail on `ajax_load`. The browser test in 07-04 remains valuable for proving the overlay injects it correctly and the chain survives in practice, but the "silent signature failure" fear is unfounded.
- **Open Decision to settle here (original text, superseded by the note above):** whether `ska` tolerates the `ajax_load` parameter the overlay injects. `pb.add_ajax_load` prepends a hidden `ajax_load=<timestamp>` input and `pb.ajax_click` appends it to the GET. It *should* be ignored (`validate_signed_request_data` reads named keys), but a signature failure here is **silent from the user's side**. One browser test settles it.
- Also confirm in the same browser test that `common_content_filter` reaches the wrapped z3c.form — `plone.z3cform.layout`'s `wrap_form` renders inside `#content` and `el.find()` is a descendant search, so it should be reachable.
- COEX-04 is the trap: `control_panel_extra.html` (`controlpanel.py:84`) and `request_bar_code_reset_email.pt` (`request_bar_code_reset.py:90`) are reached by `restrictedTraverse` and are **not** overrides. Deleting `skins/` deletes two live templates; convert both in the same commit. The email path has zero test coverage, so CI will not notice.
- The vendored copies are stale and actively harmful, which is extra reason to delete rather than maintain: `popupforms.js` reverts `msieversion()` to `jQuery.browser.msie` (removed in jQuery 1.9) and drops `dl.portalMessage.warning` from `common_content_filter`, swallowing warning messages in every Plone overlay site-wide.
- **UI hint** is set because this is the one phase with real frontend surface (login overlay, resource registries, templates). Phases 5 and 6 touch z3c.forms and a control panel but carry no visual design latitude. Leaving them unannotated does **not** mean "no UI" to the tooling: the UI gate word-matches the phase section against a token list that includes `form`, `view` and `layout`, so `token form view`, `layout.wrap_form` and `RegistryEditForm` make it block for a missing UI-SPEC. Phase 5 therefore carries an explicit `**UI hint**: no`; Phase 6 still needs one added before it is planned.

### Phase 8: Coverage Instrument and Test Layers

**Goal**: The build fails when tests fail, the coverage figure reflects package code actually exercised, branch coverage clears 90% against that corrected figure, and `bin/code-analysis` exits 0 so the pre-commit hook stops training contributors to use `--no-verify`.
**Depends on**: Phase 7
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06, QUAL-07
**Success Criteria** (what must be TRUE):

  1. **First commit of the phase, before any new test is written:** `.coveragerc` declares `[run] source`, `omit = */tests/*` and `branch = True`, and the `bin/test-coverage` template has `set -e`. The `set -e` fix is proven with a deliberately failing test showing a red build, not by inspection — today a failing test plus ≥90% coverage is a **green build**.
  2. Branch coverage is above 90% against the corrected instrument, enforced in CI. **The number is expected to drop sharply when the instrument is fixed, and the drop is the truth rather than a regression** — `[report] include` never added un-executed modules to the denominator, test modules were inside it, and statement coverage over-reports badly because Plone executes every import/def/class line at ZCML time. Re-baseline against the corrected report; do not tune `.coveragerc` until 90% appears.
  3. Browser tests run on a ZSERVER-free `FunctionalTesting(bases=(FIXTURE,))` layer, and the in-layer quickinstaller commit in `tests/base.py:_install()` is replaced by `applyProfile` in `setUpPloneSite`, so the suite stops leaking state across tests.
  4. Installedness is asserted through things this package controls — plugin registered for `IAuthenticationPlugin`, registry records present, browser layer active — not through `portal_quickinstaller`. `applyProfile` does not call `installProduct`, so `test_product_is_installed` can fail on an otherwise-correct change.
  5. `bin/code-analysis` exits 0 (~40 pre-existing findings), the `[coverage]` and `[test-coverage]` buildout parts are enabled with `coverage == 5.5` pinned, and the redundant `createcoverage` part and pin are dropped.

**Plans**: TBD

**Phase notes:**

- **Budget for revealed failures, do not treat them as regressions.** `plone.testing 4.1.3` has no isolation guard, so today's in-layer quickinstaller commit leaks state into every later test in the layer and **some tests currently pass because of that leak**. Fixing the layer will surface them. Those are real, pre-existing bugs being revealed, not caused by this phase.
- `coverage == 5.5` uses a SQLite data file — delete any stale 4.x `.coverage` once.
- **QUAL-04's 90% gate is a firm project requirement**, measured on branch coverage against the corrected instrument. The post-fix baseline is genuinely unknown and cannot be estimated before `[run] source` lands, so do not commit to an intermediate number.
- Last phase because coverage is instrumentation for work that must already exist; infrastructure-first within itself because otherwise the phase measures itself with a broken instrument.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Rename and Fail-Closed | 4/4 | Complete    | 2026-07-29 |
| 2. Registry Seeding and Import-Step Ordering | 2/2 | Complete    | 2026-07-29 |
| 3. Encrypted Seeds and Local QR | 3/3 | Complete    | 2026-07-30 |
| 4. PAS Boundary | 4/4 | Complete    | 2026-07-31 |
| 5. Drift, Replay and Lockout | 5/5 | Complete    | 2026-08-03 |
| 6. Recovery Codes | 3/3 | Complete    | 2026-08-04 |
| 7. Coexistence with imio.dms.mail | 2/4 | In Progress|  |
| 8. Coverage Instrument and Test Layers | 0/TBD | Not started | - |

## Same-Commit Requirements

These five groups must not be split across phases **or across plans within a phase**. Each was
identified because the split state is worse than either endpoint.

| Must ship together | Phase | Why |
|---|---|---|
| Drift `{T, T−1}` + replay rejection (MFA-05 + MFA-06) | 5 | Same six lines. Split yields drift-accepted-but-replay-undetected — strictly worse than today. |
| Fernet + fail-closed + local QR + `ipaddress` swap (SEC-01/03/05 + BUG-05) | 3 | Fail-closed is the one mistake that silently undoes encryption; a QR posted to Google makes encryption worthless; `cryptography` forces the `ipaddress` swap. |
| Override deletion + `next_url` open-redirect fix + query-string encoding (COEX-02 + BUG-01 + BUG-06) | 7 | This is the commit where the whole redirect surface changes. *(Planned as 07-01 Task 2. The original rationale — "deleting `login_form.cpt` restores Plone's `came_from` field and changes what `ICameFrom` sees" — is imprecise: the restored hidden input lands in `request.form`, while the adapter reads `HTTP_REFERER`'s query string. The grouping stands on the surface-change reason; nothing depends on the restored input.)* |
| Both live-template conversions + skin-directory deletion (COEX-04 + COEX-05) | 7 | The directory holds two live templates that are not overrides. Deleting it first takes both fragments down, and the control-panel one fails inside a broad `except ValueError` that nothing in `bin/test` would notice. Planned as 07-02 Task 1. |
| `.coveragerc` fix + `set -e` (QUAL-01 + QUAL-02) | 8 | Both must precede any new test, or the gate measures nothing and green means nothing. |

## Open Decisions

Each is deliberately unresolved and must appear as an explicit task in its phase, settled with
evidence rather than assumed.

| Decision | Phase | How |
|---|---|---|
| Deactivate the `credentials_basic_auth` extractor outright? | 4 | **Check `imio.dms.mail` and `server.dmsmail` for basic-auth dependence FIRST**, then choose. Cost of yes: site-wide WebDAV/FTP/XML-RPC password auth. |
| `memberdata_properties.xml` types for the new counters | 5 | Smoke-test the GenericSetup import; prefer an `int` epoch over `float`/`date`. |
| PBKDF2 iteration count for recovery codes | 6 | Any value in 20k–200k is defensible; not load-bearing for 80-bit random codes. |
| Does `ska` tolerate the overlay's injected `ajax_load` parameter? | 7 | One browser test — a signature failure here is silent from the user's side. |

## External Dependency (not one of this roadmap's commits)

The encryption-key `concat::fragment` lives in the separate **`industrialisation` repo**
(`modules/plone/manifests/buildout.pp`, following the `SSO_APPS_CLIENT_SECRET` path:
`buildout.pp:188` → `server.dmsmail/base.cfg:102` → `os.getenv()`). Phase 3's code lands and is
tested without it — tests set the env var themselves — but the feature is **not deployable** until
that Puppet change ships. It is placed at Phase 3 precisely to give it lead time. Surfaced here so
it is not silently dropped.

## Granularity Note

Config sets `granularity: standard`. Eight phases sits at the top of the standard band. The
structure was derived from the reconciled build order that three independent researchers converged
on, and it is not compressed further because the compression candidates all destroy a verification
boundary that exists for a reason:

- **Merging Phase 1 into Phase 2** would let "the `ska_secret_key` error disappeared" read as
  evidence the bug is fixed. It is not — the rename changes the import-step id's hash and can flip
  an unspecified ordering. Separate phases keep the ordering assertion as its own gate.

- **Merging Phase 4 into Phase 5** would blur exactly the boundary Phase 4 exists to establish:
  which code paths commit. Phase 5's counters are correct only because Phase 4 already answered
  that.

- **Merging Phase 6 into Phase 5** would produce a 16-requirement phase whose two halves have
  distinct user-observable outcomes.

The research's "parallel workstream" (encryption) is folded in as ordinary sequential Phase 3
because `parallelization: false`.
