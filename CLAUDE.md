# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Naming: repo vs. package

The git repository is `imio.googleauthenticator`, but the distribution and Python
package are **`collective.googleauthenticator`** (`src/collective/googleauthenticator/`).
Use the `collective.*` name in `setup.py`, buildout config, i18n domains, GenericSetup
profile ids, and test selectors. The repo name appears nowhere in the code.

This is a fork of the upstream `collective/collective.googleauthenticator`; README and
`setup.py` metadata still point at the upstream project.

## Stack

Plone 4.3 / Python 2.7 only. There is no Python 3 or Plone 5/6 branch — the buildout was
deliberately reduced to the 4.3 target. `pyenv` with 2.7 (and `virtualenv` installed
inside it) is a hard prerequisite; the Makefile aborts without it.

## Commands

Buildout uses the multi-file layout from [IMIO/scripts-buildout](https://github.com/IMIO/scripts-buildout):
`Makefile` + `base.cfg` (shared parts) + `checkouts.cfg` (mr.developer sources) +
`test-4.3.cfg` (Plone pins, the file buildout actually runs) + `requirements-4.3.txt`.

```bash
make setup plone=4.3   # first time, or after `make cleanall`: virtualenv + pip bootstrap
make buildout          # bin/buildout -c test-4.3.cfg
make test              # bin/test -t '!robot'
make test opt='-t "helpers"'   # single test / pattern
bin/test -t test_product_is_installed
bin/code-analysis      # flake8 + isort; currently FAILS on pre-existing style debt
bin/instance fg        # run Plone
make vcn               # report newer available eggs -> checkversion-n-4.3.html
```

`make setup` records the version in `.plone-version`; later `make` calls read it, so the
`plone=` argument is only needed for `setup`. Never edit `bin/*` — buildout regenerates it.

Buildout installs a **git pre-commit hook** that runs `bin/code-analysis`. Since the
existing `src/` has ~40 unfixed isort/flake8 findings, commits need `--no-verify` until
that debt is cleaned up. CI does not run code-analysis, so this does not turn the build red.

`test_robot.py` needs a real browser and is excluded everywhere (`make test` and the CI
`test_command` both pass `-t !robot`).

## Version pinning rules

All pins live in `test-4.3.cfg` `[versions]`; `base.cfg` has none. Buildout appends
resolved pins to that file itself (`update-versions-file = test-4.3.cfg`), so expect it to
grow after a `make buildout` that pulls something new — commit those additions.

Two pins are load-bearing and documented in-file; do not "upgrade" them:

- **`ska = 1.7.5`** — last release supporting Python 2.7. `>=1.1` resolves to 1.11.x, which
  needs `setuptools>=61` (PEP 517) and cannot build on 2.7.
- **`plone.testing` intentionally unpinned** (Plone 4.3 supplies 4.1.3). Pinning 5.0.0, as
  the upstream scripts-buildout `test-4.3.cfg` does, introduces the `TestIsolationBroken`
  guard, and every browser test in this package trips it — they drive a testbrowser inside
  an `IntegrationTesting` layer, which commits.

## Architecture

A PAS (PluggableAuthService) authentication plugin that wedges a TOTP step into Plone's
login. Understanding it means reading `pas_plugin.py` + `helpers.py` + `browser/forms/token.py`
together, since the flow is split across all three.

**Login interception** (`pas_plugin.py:authenticateCredentials`) is the entry point on every
login attempt:

1. Bail out (`return None`, standard Plone login proceeds) if the client IP is whitelisted or
   the user's `enable_two_factor_authentication` property is false.
2. Otherwise validate the password by delegating to *every other* `IAuthenticationPlugin` in
   the PAS chain, skipping itself to avoid recursion.
3. **Empty the `credentials` dict in place** so later plugins cannot log the user in before
   the token is checked. This mutation is deliberate — PAS offers no "consume credentials"
   protocol — and it produces a spurious "Login failed" status message that
   `helpers.drop_login_failed_msg()` removes downstream.
4. Clear the `__ac` cookie and redirect to a `ska`-signed `@@google-authenticator-token` URL.

**No session state exists during the 2FA step.** State travels in the signed URL. The `ska`
signing key (`helpers.get_ska_secret_key`) is a composite of the user's stored secret, the
global `ska_secret_key` registry record, and a SHA1 of the `User-Agent`
(`helpers.get_browser_hash`) for weak device binding. If you touch any of those three
inputs, previously-issued token URLs stop validating.

`helpers.py` holds essentially all the logic (~26 functions: TOTP via `onetimepass`, secret
generation, URL signing, CIDR whitelist matching, `X-Forwarded-For` handling). Views and the
PAS plugin are thin wrappers over it — put new behaviour there and unit-test it in
`tests/test_helpers.py`.

**Settings** live in two places: global config in `plone.registry` under
`IGoogleAuthenticatorSettings` (`browser/controlpanel.py` — `ska_secret_key`,
`globally_enabled`, `ip_addresses_whitelist`), and per-user state in memberdata properties
(`enable_two_factor_authentication`, `two_factor_authentication_secret`,
`bar_code_reset_token`) declared via `userdataschema.py` and surfaced by
`adapter.EnhancedUserDataPanelAdapter`.

**Install** (`setuphandlers.setupVarious`, gated on the
`collective.googleauthenticator.marker.txt` data file) generates the `ska_secret_key` if
empty and registers the PAS plugin as `google_auth`, then reorders the plugin list — plugin
ordering matters, because this plugin must see credentials only after the password-checking
plugins have run.

## Conventions

`snake_case` functions with `get_`/`set_`/`validate_`/`is_`/`has_` prefixes; `I`-prefixed
interfaces; reStructuredText docstrings with `:param Type name:` / `:return type:`.
isort settings are in `.isort.cfg` (`force_single_line`, `force_alphabetical_sort`,
`line_length = 120`) — there is no `setup.cfg`.

The GenericSetup profile version is a zero-padded string (`0301`, in
`profiles/default/metadata.xml`), matching the package version `0.3.0`. Adding an upgrade
step means bumping that, plus a `genericsetup:upgradeStep` in `upgrades/configure.zcml` —
see `upgrades/to0301.py` for the shape.

## Further reading

`.planning/codebase/` holds a generated deep-dive (ARCHITECTURE, TESTING, CONVENTIONS,
CONCERNS, STACK, STRUCTURE, INTEGRATIONS). Useful for detail, but it predates the buildout
migration and still refers to `buildout.cfg`, `setup.cfg`, and `.travis.yml`, none of which
exist any more.
