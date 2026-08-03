# imio.googleauthenticator

## What This Is

A Plone 4.3 / Python 2.7 PAS plugin providing TOTP two-factor authentication (Google
Authenticator app) for users and site admins **inside** a Plone site. Forked from
[collective.googleauthenticator](https://github.com/collective/collective.googleauthenticator)
and being renamed, hardened, and made deployable alongside `imio.dms.mail`.

Deliberately temporary. It exists because iMio's main projects are still on Plone 4 and need
MFA now. When those projects reach Plone 6 (~1–2 years), this package is dropped and MFA moves
to Keycloak.

## Core Value

A second factor that actually holds for in-site users, and that can be deployed alongside
`imio.dms.mail` without colliding with it.

## Requirements

### Validated

<!-- Inferred from the existing codebase (.planning/codebase/ARCHITECTURE.md, STACK.md).
     These work today and must keep working. -->

- ✓ TOTP second factor via a PAS `IAuthenticationPlugin` that intercepts login and redirects
  to a token form — existing
- ✓ Per-user enrollment: secret generation, QR barcode display, `enable_two_factor_authentication`
  memberdata property — existing
- ✓ Signed hand-off between login and token form via `ska` (secret derived from user secret +
  browser hash + site key) — existing
- ✓ Bar-code reset by email request, with a signed, time-limited reset link — existing
- ✓ Registry-backed control panel: site secret, `globally_enabled`, IP whitelist — existing
- ✓ Bulk enable of 2FA for all users from the control panel — existing
- ✓ IP whitelist that skips the second factor for configured CIDR ranges — existing

**Rename** — *Validated in Phase 1: Rename and Fail-Closed (2026-07-29)*

- ✓ Renamed `collective.googleauthenticator` → `imio.googleauthenticator` everywhere:
      on-disk structure (`src/collective/` → `src/imio/`), egg name, i18n domain **and the
      `locales/` filenames**, the GenericSetup profile **and its marker file**, the registry
      interface path, the PAS plugin *title* and `meta_type`, the `++resource++` prefixes,
      `MANIFEST.in`, `.coveragerc`, `base.cfg`, `cleanup.sh`, and `testing.py`'s
      `installProduct` string — RENAME-01…10
- ✓ Stale artefacts purged: the 27 git-ignored `.pyc` files and the
      `collective.googleauthenticator.egg-info` directory. Verified: 0 old-namespace `.pyc`,
      one develop-egg, one egg-info — RENAME-08
- ✓ `upgrades/` deleted along with its ZCML include — RENAME-09
- ✓ `_dont_swallow_my_exceptions = True` on the plugin class, so a plugin exception is a 500
      rather than a silent fallthrough to `source_users` password-only auth. Asserted by
      `test_plugin_exception_is_not_swallowed` plus a counterfactual — RENAME-11, RENAME-12.
      The three crash paths this flag exposed on ordinary input (unknown username, malformed
      `X-Forwarded-For`, blank line in the IP whitelist) were found by code review and fixed
      with regression tests, so the plugin is fail-closed rather than fail-crashed

**Registry seeding** — *Validated in Phase 2: Registry Seeding and Import-Step Ordering (2026-07-29)*

- ✓ `Interface ... IGoogleAuthenticatorSettings defines a field ska_secret_key, for which there
      is no record` is fixed on new Plone site creation. `<depends name="plone.app.registry"/>`
      declared at `configure.zcml:50`, and the nested `runImportStepFromProfile` re-entry is gone
      from `src/`. Confirmed against a real site-creation log (UAT 2026-07-29): zero `no record`
      lines — REG-01, REG-02, REG-04
- ✓ The ordering is asserted rather than accidental, and the assertion is a *genuine* control:
      `test_import_step_declares_registry_dependency` asserts the pre-sort
      `getImportStepMetadata(...)['dependencies']` and was reproduced failing when the `<depends>`
      line is deleted. The older `test_import_step_ordering` is kept as the outcome check with a
      docstring that admits it proves nothing alone — REG-03
- ✓ `ska_secret_key` is seeded once at install time by `setuphandlers._setup_secret_key()`;
      `get_ska_secret_key()` is a pure read that raises `ValueError` on an empty key (fail-closed,
      no plaintext-equivalent fallback, no lazy mint on a `transaction.abort()` path). Re-applying
      the profile leaves an existing key unchanged — REG-04, REG-05
- ✓ Derived `ska` key components are separated by a length-prefixed netstring join, so two
      component tuples that collide under bare concatenation now derive to different keys.
      Asserted with an exact-string check on a provably-colliding fixture — BUG-04

**Secret handling** — *Validated in Phase 3: Encrypted Seeds and Local QR (2026-07-30)*

- ✓ TOTP seeds are Fernet-encrypted at rest; the key is read per-call from the process
      environment and never reaches the ZODB, a memberdata property, a log line or an
      exception message — SEC-01, SEC-02
- ✓ Enrollment and validation both fail closed when the key is missing or invalid: login is
      refused, never downgraded to plaintext or to password-only — SEC-03
- ✓ Ciphertext carries a `v1$` version prefix — SEC-04
- ✓ The enrollment QR code is rendered in-process by `qrcode == 6.1`; the seed reaches no
      external service and appears in no subprocess argv — SEC-05
- ✓ New seeds are 160 bits of `os.urandom`, satisfying RFC 4226 §4 R6's 128-bit minimum — SEC-06
- ✓ The required environment variable is documented in all four places it must exist
      (`[instance]`, `[testenv]`, the CI workflow, and the out-of-repo Puppet fragment), and a
      missing key logs CRITICAL at process start rather than raising from import or ZCML —
      SEC-07, SEC-08, DOC-03
- ✓ `redirect_url` is bound on every code path through `user_setup.py`; the bar-code reset
      token comparison is constant-time with both operands encoded first — BUG-02, BUG-03
- ✓ `py2-ipaddress` replaced by `ipaddress == 1.0.23` with `unicode` coercion at both call
      sites, so adding `cryptography` cannot break every login through module shadowing — BUG-05

**Second-factor integrity** — *Validated in Phase 4: PAS Boundary (2026-07-31)*

- ✓ The `credentials_basic_auth` bypass is closed for in-site users. The deny mechanism is
      wiping the shared credentials dict, not `return None` — PAS accumulates every
      authenticator's result and returns the first success. One veto test per extractor
      (form POST and `Authorization: Basic`), each with a disabled-2FA control, each proven
      load-bearing by removing the wipe and watching it fail — MFA-01, MFA-04
- ✓ The refusal no longer relies on `response.redirect(lock=1)`, which sets a status and header
      but neither clears the body nor stops publishing. `send_2fa_redirect` sets
      `response.body = ''` plus `content-length: 0` and locks the body — `setBody('')` alone is
      a no-op — MFA-02
- ✓ Plugin ordering is explicit (`movePluginsTop`) and re-asserted on every profile
      application, so re-applying the profile is a real recovery if a third-party add-on
      displaces the plugin. `test_plugin_is_first_authenticator` is the security control — MFA-03
- ✓ The challenge fires on both paths: `IChallengePlugin.challenge` for requests ending in
      `Unauthorized`, and an `IPubBeforeCommit` subscriber for the login-form POST, which
      returns HTTP 200 and never raises. Each has its own test — COEX-08
- ✓ The Zope-root boundary and the HTTP Basic Auth consequence are documented in `README.rst`,
      each pinned by an identifier-based test so a routine rewrite cannot silently drop them —
      DOC-01, DOC-02

**Drift, replay and lockout** — *Validated in Phase 5: Drift, Replay and Lockout (2026-08-03)*

- ✓ A code from the immediately preceding time step is accepted and a code already consumed is
      refused on reuse, in one commit. The accepted interval is stored in
      `two_factor_authentication_last_interval` and any newly matched interval `<=` it is
      rejected; the candidate tuple is exactly `(current, current - 1)`, so there is no
      forward-looking window to double the guessing surface. The replay rejection is logged with
      no operand at all — no username, user id, token, secret or interval number. Confirmed
      against a real mobile authenticator app, which no in-process test can do, because the
      in-process test generates its code with the same library and clock as the code under test —
      MFA-05, MFA-06, MFA-07
- ✓ Five consecutive failures lock the account for the configured duration, the lock is evaluated
      before the token is ever evaluated, and it expires on its own with no admin action. A
      successful second factor clears the counter. Both anonymously reachable endpoints are
      metered, not just the login form: `@@reset-bar-code` takes its target account from an
      attacker-supplied query parameter and would otherwise be an unmetered guessing oracle —
      MFA-08, MFA-09, MFA-11
- ✓ The attempt ceiling and lock duration are editable in the control panel, defaulting to 5 and
      900 seconds, and the edited values survive a page reload in a live instance — MFA-10
- ✓ No second-factor state is written from the PAS plugin or a challenge plugin. Every write
      originates in `browser/forms/token.py` or `browser/forms/reset_bar_code.py`, both of which
      return 200 or 302 and therefore commit. This matters because `ZPublisher` aborts the
      transaction on any request ending in an exception and `Unauthorized` is such an exception,
      so a counter written in the plugin would be a lockout that silently never locks. Confirmed
      across four ZEO clients sharing one database: the counter is cumulative, not per-instance —
      MFA-12
- ✓ Every new memberdata property has a `memberdata_properties.xml` entry and a set/get
      round-trip test, because `MutablePropertySheet.setProperties` silently pops an undeclared
      key with no error. The three counters are deliberately memberdata only and are **not**
      declared on `IEnhancedUserDataSchema`: as schema fields they crashed the administrator's
      view of another user's profile and were form-writable — MFA-13

### Active

**Correctness**

- [ ] `bin/code-analysis` exits 0. The corrected baseline is **318 pre-existing findings**, not
      the ~40 previously recorded here — measured in plan 01-03 (RESEARCH C-6). 184 of the 318
      (58%) are `isort` findings, and the rename actively perturbs first-party import ordering,
      so QUAL-06 must be planned against 318. The buildout installs a pre-commit hook that fails
      every commit until this is clean (`--no-verify` in the meantime)
- [ ] Fix open redirect: `next_url` accepted unvalidated at `token.py:112-113`

**Second-factor integrity**

- [ ] Single-use recovery codes issued at enrollment, stored hashed with a per-user salt, for
      self-service recovery. They share the lockout counter, or they are the unthrottled path.
      Phase 6 therefore adds new writers of the counter Phase 5 introduced, so its plan must
      extend the source-level guard in `tests/test_pas_plugin.py` to any new module that touches
      that state — the guard cannot cover files that do not yet exist

**Coexistence with imio.dms.mail**

- [ ] Give `TokenForm` `id = 'login_form'` so Plone's existing overlay finds it, then delete the
      `login_form.cpt` override and the vendored `popupforms.js` copy, its `jsregistry.xml`
      entries, and the `remove="True"` line that permanently unregisters a resource we do not own
- [ ] Keep `control_panel_extra.html` and `request_bar_code_reset_email.pt` — they are reached
      by `restrictedTraverse`, not overrides. Convert both to `ViewPageTemplateFile` in the same
      commit that removes the skin layer
- [ ] Ship a real `profiles/uninstall/` so uninstalling does not leave the site without
      `popupforms.js`

**Quality**

- [ ] Fix the coverage instrumentation before writing any new test: `.coveragerc` needs
      `[run] source`, `omit = */tests/*` and `branch = True`, and the `bin/test-coverage`
      template needs `set -e` — without it, failing tests plus ≥90% coverage is a green build
- [ ] Test coverage above 90%, enforced in CI, measured against the corrected instrument
- [ ] Move the browser tests onto a ZSERVER-free `FunctionalTesting` layer so they stop breaking
      Plone test isolation

### Out of Scope

- **Python 3 migration** — Keycloak supersedes this package before the migration would pay off.
  This also parks every concern whose only real fix is Python 3: the `ska` 1.7.5 pin (already at
  its last py2.7-compatible release) and the self-hosted py2 CI runner. **`py2-ipaddress` is not
  one of them** — see the Active requirement above; research showed it is fixable now and must be.
- **Plone 5 / Plone 6 support** — same reason. This package dies with Plone 4.
- **Zope root admins** (`bin/instance` inituser, emergency user) — they live in the root
  `acl_users`, which an in-site PAS plugin never sees. Architecturally unreachable from this
  package at any effort level. MFA here is scoped to users and site admins inside the Plone site.
  Accepted limitation, to be documented.
- **WebAuthn / U2F / SMS fallback** — recovery codes cover the lost-device case at a fraction of
  the cost.
- **Async bulk operations** (task queue for enable/disable across all users) — iMio sites are
  nowhere near the ~10k user mark where the current loop times out.
- **Performance caching** (IP-range precompilation, user-property and registry-lookup caching) —
  no observed problem at current scale.
- **`onetimepass` → `pyotp` swap** — confirmed unnecessary: `get_hotp(secret, intervals_no=i)` is
  already public and exposes the window counter that replay detection needs.
- **Email notification on lockout or recovery-code use** — conventional (ASVS 2.2.3) and cheap,
  but it is a new feature on a mail path with zero test coverage. Revisit if operations asks.
- **`MultiFernet` key rotation** — a `ponytail:` comment marking the upgrade path is enough for a
  package with two years left.
- **Completing or removing the unused `hashed` parameter** on `get_secret` /
  `get_or_create_secret` — cosmetic.

## Context

**Why this fork exists.** iMio needs MFA on Plone 4 projects now. Upstream
`collective.googleauthenticator` is unmaintained and targets Plone 4 only, which happens to suit
us — but it ships two problems we cannot deploy with: plaintext TOTP seeds in user properties,
and wholesale skin overrides that collide with `imio.dms.mail`.

**The collision is real, not theoretical.** `imio.dms.mail/profiles/default/jsregistry.xml:102`
re-registers `popupforms.js` (`insert-after="form_tabbing.js"`), while this package's
`jsregistry.xml` removes `popupforms.js` and registers its own copy. Whichever profile is applied
last wins. `imio.dms.mail` also ships its own skins directory.

**What the overrides are actually for.** The only functional change in the 197-line
`popupforms.js` copy is commenting out the login-overlay binding (line 60) — the AJAX overlay
cannot follow the 2FA redirect. The 310-line `login_form.cpt` is a stock Plone 4.3 copy carried
along for the ride. Both exist to defeat the overlay, and both can go if the PAS plugin drives
the challenge itself.

**Secret injection is a solved problem here.** The established iMio pattern is Puppet writing a
`concat::fragment` into `port.cfg`, buildout exposing it via `environment-vars` in `[instance]`,
and Python reading `os.getenv()`. `SSO_APPS_CLIENT_SECRET` follows exactly this path today:
`industrialisation/modules/plone/manifests/buildout.pp:188` →
`server.dmsmail/base.cfg:102` → `imio/helpers/__init__.py:46`. We reuse it rather than invent
anything.

**QR generation — reversed after research.** The first plan was to reuse
`imio.helpers.barcode.generate_barcode()` with `zint` type 58, which Puppet already deploys
(`modules/plone/manifests/packages/imiohelpers.pp:4`, v2.6.0). Research found it passes the
payload as `--data=otpauth://...secret=<SEED>`, so the plaintext seed is readable in `ps` and
`/proc/<pid>/cmdline` by any local user on the Zope host. `--input=/dev/stdin` was tested; zint
rejects it (Error 79), leaving only argv or a temp file. Since the entire point of the change is
to stop leaking the seed, we use `qrcode == 6.1` instead — one pinned pure-Python egg, rendering
in-process, verified producing a real PNG and a Pillow-free SVG under this interpreter.

**Coverage machinery exists but is switched off.** `base.cfg:82-92` defines a `[test-coverage]`
part running `coverage report -m --fail-under=90`; `base.cfg:19-20` show `coverage` and
`test-coverage` commented out of the parts list. The threshold is already the one we want. CI
(`.github/workflows/package-test.yml`) calls `IMIO/gha-workflows` `package-test-legacy.yml@v1`
with a bare `test_command: 'bin/test -t !robot'` and no coverage step.

**Not deployed yet — but that is about users, not databases.** No enrolled users anywhere, so the
rename and the move to encrypted seeds need no upgrade steps, no in-place re-encryption, and no
memberdata migration. Any *existing local* `Data.fs` is a different matter: the PAS plugin, the
`IUserDataSchemaProvider` utility, the browser-layer interface and the registry record prefixes
all pickle the old module path, so after the rename the plugin unpickles as
`OFS.Uninstalled.Broken`, stops providing `IAuthenticationPlugin`, and 2FA silently stops running
with no error page. Existing dev databases are discarded, not migrated, and a permanent test
asserts the plugin is registered for `IAuthenticationPlugin`.

**Detailed prior analysis** lives in `.planning/codebase/` — `CONCERNS.md` in particular
enumerates the bugs, security gaps, and test-coverage holes referenced above.

## Constraints

- **Tech stack**: Python 2.7.18 and Plone 4.3 stay — the entire point of the package is serving
  projects that have not migrated
- **Dependencies**: `cryptography == 3.3.2` — the last release supporting Python 2.7, and already
  pinned and building in `server.dmsmail/versions-base.cfg:219`
- **Dependencies**: `qrcode == 6.1` — last release supporting Python 2.7; pure Python, renders
  in-process, so no system package and no seed in argv
- **Dependencies**: `coverage == 5.5` — last release supporting Python 2.7; `--fail-under` confirmed
- **Dependencies**: nothing may require PEP 517 — `requirements-4.3.txt` pins `setuptools 44.1.1`,
  which rules out any release needing `setuptools>=61`
- **Compatibility**: must coexist with `imio.dms.mail` — no wholesale skin or resource-registry
  overrides, and nothing that mutates a resource we do not own
- **Security**: the seed encryption key never lives in the ZODB — nor in a memberdata property, a
  log line, or an exception message. QuickInstaller snapshots `portal_setup` before and after
  every install
- **Security**: replay and lockout state goes in memberdata properties alongside the seed, so it
  is consistent across ZEO clients (a per-instance RAM cache would let an attacker multiply
  attempts by rotating clients). The hazard to design against is **not** ConflictError — storage
  is an `OOBTree` keyed by user id, so writes merge and retry correctly. It is
  `transaction.abort()`: any request ending in an exception discards its writes, and `Unauthorized`
  is re-raised, so a counter written in the PAS plugin is a lockout that silently never locks.
  Hence: all state writes in the token form view
- **Security**: undeclared memberdata properties are silently *popped* by
  `MutablePropertySheet.setProperties` with no error, so every new property needs a
  `memberdata_properties.xml` entry and a set/get round-trip test
- **Quality**: test coverage above 90%, enforced in CI, using the existing `[test-coverage]` part
- **Lifespan**: retired for Keycloak in ~1–2 years — this caps how much any fix is worth, and is
  the reason the Python 3 and Plone 6 migrations are out of scope
- **Deployment dependency**: the encryption-key `concat::fragment` is a change in the separate
  `industrialisation` repo, outside this roadmap's commits. Tracked here so it does not silently
  fall through.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stay on Python 2.7 / Plone 4.3 | Package is a bridge for unmigrated projects; Keycloak replaces it before a py3 port would pay off | — Pending |
| Fernet via `cryptography==3.3.2` for seed encryption | Last py2.7-compatible release, already proven in the iMio stack — no new dependency risk | — Pending |
| Key injected as an env var via Puppet `port.cfg` → `environment-vars` | Reuses the exact mechanism `SSO_APPS_CLIENT_SECRET` already uses; keeps the key out of the ZODB | — Pending |
| Replay and lockout state in memberdata properties, written only in the token form view | Consistent across ZEO clients; the view is the only path in the request lifecycle that actually commits | — Pending |
| Drop the two overrides via `id = 'login_form'` on `TokenForm` | The overrides exist solely to defeat the AJAX login overlay, and they collide with `imio.dms.mail`'s `jsregistry.xml`. One class attribute makes Plone's own overlay find the token form, replacing 507 vendored lines | — Pending |
| Challenge split across `IChallengePlugin` + an `IPubBeforeCommit` subscriber | Plone 4.3's login POST returns HTTP 200 and never raises `Unauthorized`, so `challenge()` alone never fires on the normal login path | ✓ Shipped Phase 4 |
| Zope root admins accepted as out of reach | An in-site PAS plugin never runs for the root `acl_users`; MFA is scoped to users and site admins inside the Plone site | ✓ Shipped Phase 4 — documented in `README.rst`, pinned by `test_readme_documents_zope_root_limitation` |
| Local QR via `qrcode == 6.1`, not `imio.helpers` + zint | Reversed after research: zint takes the seed in argv, readable via `ps` by any local user, which defeats the purpose of encrypting it. One pure-Python egg avoids the subprocess entirely | — Pending |
| Lockout N and duration as control-panel settings | Tunable on a live site without a release, following `imio.dms.mail`'s `RegistryEditForm` pattern | — Pending |
| Recovery codes instead of WebAuthn/SMS | Covers the lost-device case at a fraction of the cost, for a package with a 2-year life | — Pending |
| Recovery codes hashed with one salt per user, not per code | A per-code salt forces N hash runs per attempt (~1.1s for 10 codes) on a login-adjacent endpoint — a DoS lever. Per-user still defeats cross-user rainbow tables, which is all a salt does here | — Pending |
| No upgrade steps for the rename; existing dev ZODBs discarded | No enrolled users to migrate, and pickled module paths make in-place migration far more work than recreating a dev database | — Pending |
| Don't rename `PAS_ID` (`google_auth`) | Already namespace-neutral; renaming it would create a second plugin on any existing ZODB | — Pending |
| Seed `ska_secret_key` at install time in `setuphandlers._setup_secret_key()`, **not** lazily on first read | Reverses the 02-01 plan's D-04/D-05 lazy-mint design (CR-02). A mint inside `get_ska_secret_key()` is reachable from `authenticateCredentials()`, a path that ends in `transaction.abort()` on `Unauthorized` — it would discard the key *after* a signed URL using it was already handed to the browser. `get_ska_secret_key()` is now a pure read that raises `ValueError` on an empty key | ✓ Shipped Phase 2 |
| Derive the `ska` key with a length-prefixed netstring join, not bare concatenation | Bare concatenation of `(user_secret, browser_hash, ska_secret_key)` is collidable: a component-boundary shift yields the same key, so a signature minted in one context validates in another. Asserted with an exact-string check on a fixture that provably collides under the old scheme, so it cannot regress into a cosmetic reformat | ✓ Shipped Phase 2 |
| Assert the `<depends>` *declaration*, not just the resulting sorted order | The first ordering test was tautological — it stayed green with `<depends name="plone.app.registry"/>` deleted, purely by CPython 2.7 string-hash coincidence. `test_import_step_declares_registry_dependency` asserts the pre-sort `getImportStepMetadata(...)['dependencies']` instead, and was reproduced failing on deletion. The outcome test is kept, with a docstring admitting it proves nothing alone | ✓ Shipped Phase 2 |
| Keep Plone's `credentials_basic_auth` extractor active rather than deactivating it site-wide | Operator decision at a blocking checkpoint, 2026-07-31. Deactivating it would break WebDAV, FTP and XML-RPC password login for every user whether or not they use 2FA, on the strength of a search across only three iMio repositories that the research recorded as non-exhaustive. It also mutates a plugin this package does not own, which the project constraints forbid. The Basic Auth path is vetoed instead, proven by `test_basic_auth_veto`. Accepted cost: correctness stays order-dependent, enforced by CI rather than at request time. Operator confirmed on 2026-07-31 that no external consumer depends on it | ✓ Shipped Phase 4 |
| `authenticateCredentials` decides only; the redirect moved to an `IPubBeforeCommit` subscriber | The PAS method runs inside a request that may be aborted, and the login-form POST never raises, so a redirect issued there could not both cover the HTTP-200 path and survive. The plugin now sets a pending flag in `request.other` and the subscriber issues the redirect. Keeps the plugin write-free, which Phase 5's lockout state depends on | ✓ Shipped Phase 4 |
| Clear the refusal body with `response.body = ''` plus a lock, not `setBody('')` | `setBody('')` is a no-op in `ZPublisher.HTTPResponse`, so the protected page was still readable out of the 302 by any client that did not follow redirects. The lock (`setBody('', lock=1)`) also stops a later subscriber such as `plone.transformchain` from refilling it | ✓ Shipped Phase 4 |
| Set plugin order with `movePluginsTop`, re-asserted on every profile application | The previous `movePluginsDown(iface, listPlugins(iface)[:-1])` reached position 0 only while this plugin happened to be the most recently activated entry — an accident, not a statement. Re-asserting on every profile application also makes re-applying the profile a real recovery when a third-party add-on displaces the plugin | ✓ Shipped Phase 4 |
| Meter `@@reset-bar-code` with the same counter and lock as the login form | Operator decision at plan time, 2026-07-31 (P5-12). Registered `permission="zope2.View"`, it takes its target account from an attacker-supplied `auth_user` parameter and called `validate_token` before checking the reset signature. Left unmetered it was an anonymous TOTP guessing oracle, which would have made the phase goal untrue while appearing met. `user_setup.py` stays deliberately excluded: it validates the enrolling user's own in-progress secret, so a counter there would let a user lock themselves out mid-enrolment | ✓ Shipped Phase 5 |
| Accept that an anonymous party can lock a named account | Operator decision P5-13. Bounded to the configured duration by self-expiry. Both alternatives are worse: leaving the reset path unmetered restores the guessing oracle, and admin-unlock-only lockout is ruled out in `REQUIREMENTS.md` as a denial-of-service primitive | ✓ Shipped Phase 5 — logged as accepted risk R-05-A |
| Close only the lock-state oracle at `@@reset-bar-code`, not username existence | Operator decision P5-17, 2026-08-01. The user-not-found and non-site-local branches keep their distinct messages. Username existence is a pre-existing disclosure this Plone site already makes through standard member lookups, it is not the state of a security control, and collapsing those messages would also remove the assurance a legitimate administrator needs that a Zope-root account cannot be gated by this plugin. Fixing it later is strictly additive to the same two branches | ✓ Shipped Phase 5 — logged as accepted risk R-05-B |
| Keep the replay and lockout counters off `IEnhancedUserDataSchema` | Found in real-deployment testing, 2026-08-03. As schema fields they crashed `plone.app.users`' `@@user-information`, the form an administrator uses to edit another user's profile, because `adapter.py` supplies no accessor for them and `zope.formlib` does a plain `getattr` per rendered field. The `omit()` call that hid them covers `personal-information` only. What makes them persist is their `memberdata_properties.xml` entry, which a schema field neither provides nor replaces, so removing them costs nothing and also removes the write path by which a user could have zeroed their own lock deadline | ✓ Shipped Phase 5 |
| Pin every `jsregistry.xml` registration to an explicit position | Found in real-deployment testing, 2026-08-03. `BaseRegistry.storeResource` appends, so an unpositioned entry's load order depends on when the profile's import step runs. Installing onto an existing site works; on a fresh site this package's two scripts landed above jQuery, and because cooking merges adjacent resources into one bundle, the `$ is not defined` thrown at the top of `main.js` aborted the bundle before jQuery loaded — every jQuery-dependent script on the site died. Phase 7 supersedes this by deleting both registrations outright | ✓ Shipped Phase 5 (stop-gap; Phase 7 owns the removal) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-03 — Phase 5 complete (drift, replay and lockout). Phase 5's requirements
(MFA-05 to MFA-13) moved to Validated, and the four Active "Second-factor integrity" bullets they
satisfied were removed, leaving only recovery codes, which is Phase 6. Five Phase 5 decisions
logged: two operator decisions taken at plan time (meter `@@reset-bar-code`, accept that an
anonymous party can lock a named account), one taken during the phase (close only the lock-state
oracle, not username existence), and two forced by defects that only real-deployment testing
found — keeping the counters off the user-profile schema, and pinning every `jsregistry.xml`
registration to an explicit position. The recovery-codes bullet now carries the note that Phase 6
adds new writers of Phase 5's counter and must extend the source-level guard that keeps those
writes off aborted request paths.*

*Last updated: 2026-07-31 — Phase 4 complete (PAS boundary). Phase 4's requirements (MFA-01..04, COEX-08, DOC-01, DOC-02) moved to Validated and four Phase 4 decisions logged, including the operator decision to keep `credentials_basic_auth` active. Phase 3's requirements (SEC-01..08, BUG-02, BUG-03, BUG-05, DOC-03) were also moved to Validated — they had been left in Active because this document was last evolved after Phase 2.*
