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

### Active

**Rename**

- [ ] Rename `collective.googleauthenticator` → `imio.googleauthenticator` everywhere,
      including the on-disk file structure (`src/collective/` → `src/imio/`), the egg name, the
      i18n domain, the GenericSetup profile and marker file, the registry interface path, the
      PAS plugin id and title, the `++resource++` prefixes, and `.coveragerc`

**Correctness**

- [ ] Fix `Interface ... IGoogleAuthenticatorSettings defines a field ska_secret_key, for which
      there is no record` on new Plone site creation
- [ ] `bin/code-analysis` exits 0 (~40 pre-existing findings; the buildout installs a
      pre-commit hook that fails every commit until this is clean)
- [ ] Fix open redirect: `next_url` accepted unvalidated at `token.py:112-113`
- [ ] Fix `UnboundLocalError` on `redirect_url` at `user_setup.py:96`
- [ ] Use a constant-time comparison for the reset token at `reset_bar_code.py:104`
- [ ] Separate the components of the derived `ska` key at `helpers.py:259` (currently bare
      concatenation, collidable)

**Secret handling**

- [ ] Encrypt TOTP seeds at rest with a key held outside the ZODB, read via `os.getenv()` and
      injected by Puppet through `port.cfg` → buildout `environment-vars`
- [ ] Generate the enrollment QR code locally instead of sending the seed to
      `chart.googleapis.com`

**Second-factor integrity**

- [ ] Close the `credentials_basic_auth` bypass for in-site users
- [ ] Reject a TOTP code already consumed within its time window (replay)
- [ ] Lock an account after N consecutive failed second-factor attempts
- [ ] Single-use recovery codes issued at enrollment, stored hashed, for self-service recovery

**Coexistence with imio.dms.mail**

- [ ] Delete the `login_form.cpt` and `popupforms.js` skin/resource overrides; perform the
      challenge and redirect from the PAS plugin only

**Quality**

- [ ] Test coverage above 90%, enforced in CI
- [ ] Move the browser tests onto the already-defined-but-unused `FUNCTIONAL_TESTING` layer so
      they stop breaking Plone test isolation

### Out of Scope

- **Python 3 migration** — Keycloak supersedes this package before the migration would pay off.
  This also parks every concern whose only real fix is Python 3: the `ska` 1.7.5 pin (already at
  its last py2.7-compatible release), `py2-ipaddress`, the self-hosted py2 CI runner.
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
- **`onetimepass` → `pyotp` swap** — `onetimepass==0.2.2` is old but working, and the swap has no
  security payoff on its own once seeds are encrypted.
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

**QR generation is also already solved.** `imio.helpers.barcode.generate_barcode()` shells out to
`zint`, which Puppet already deploys (`modules/plone/manifests/packages/imiohelpers.pp:4`,
v2.6.0). QR Code is zint barcode type **58**. This adds a dependency on `imio.helpers` but no new
system package.

**Coverage machinery exists but is switched off.** `base.cfg:82-92` defines a `[test-coverage]`
part running `coverage report -m --fail-under=90`; `base.cfg:19-20` show `coverage` and
`test-coverage` commented out of the parts list. The threshold is already the one we want. CI
(`.github/workflows/package-test.yml`) calls `IMIO/gha-workflows` `package-test-legacy.yml@v1`
with a bare `test_command: 'bin/test -t !robot'` and no coverage step.

**Not deployed yet.** No enrolled users anywhere, so the rename and the move to encrypted seeds
need no upgrade steps, no in-place re-encryption, and no memberdata migration.

**Detailed prior analysis** lives in `.planning/codebase/` — `CONCERNS.md` in particular
enumerates the bugs, security gaps, and test-coverage holes referenced above.

## Constraints

- **Tech stack**: Python 2.7.18 and Plone 4.3 stay — the entire point of the package is serving
  projects that have not migrated
- **Dependencies**: `cryptography == 3.3.2` — the last release supporting Python 2.7, and already
  pinned and building in `server.dmsmail/versions-base.cfg:219`
- **Dependencies**: `zint` 2.6.0 via `imio.helpers` — already Puppet-deployed, so local QR
  generation costs no new system package
- **Compatibility**: must coexist with `imio.dms.mail` — no wholesale skin or resource-registry
  overrides
- **Security**: the seed encryption key never lives in the ZODB
- **Security**: replay and lockout state must be consistent across all ZEO clients — a
  per-instance RAM cache would let an attacker multiply attempts by rotating clients, so this
  state goes in memberdata properties alongside the seed
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
| Replay and lockout state in memberdata properties | Only option consistent across ZEO clients without a single-object write hotspot | — Pending |
| Drop skin overrides, challenge from the PAS plugin only | The overrides exist solely to defeat the AJAX login overlay, and they collide with `imio.dms.mail`'s `jsregistry.xml` | — Pending |
| Zope root admins accepted as out of reach | An in-site PAS plugin never runs for the root `acl_users`; MFA is scoped to users and site admins inside the Plone site | — Pending |
| Local QR via `imio.helpers` + `zint` type 58 | Encrypting the seed at rest is pointless while it is also sent to `chart.googleapis.com`; the helper and the `zint` binary already exist | — Pending |
| Recovery codes instead of WebAuthn/SMS | Covers the lost-device case at a fraction of the cost, for a package with a 2-year life | — Pending |
| No upgrade steps for the rename | Not deployed yet — no enrolled users to migrate | — Pending |

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
*Last updated: 2026-07-28 after initialization*
