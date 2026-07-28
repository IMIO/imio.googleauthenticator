# Technology Stack

**Analysis Date:** 2026-07-28

## Languages

**Primary:**
- Python 2.7 - Only supported/tested version. `setup.py` classifiers still advertise 2.6,
  but the buildout targets 2.7 exclusively (`requirements-4.3.txt`, `Makefile` pyenv pin)

**Secondary:**
- ZCML - Zope configuration language used throughout
- JavaScript - Minimal client-side logic in `src/collective/googleauthenticator/browser/static/`
- HTML/TAL - Plone page templates for views

## Runtime

**Environment:**
- Zope application server
- Python 2.7+ (deprecated, legacy support)

**Package Manager:**
- setuptools - Primary package manager
- Buildout - Dependency and configuration management, multi-file layout from
  [IMIO/scripts-buildout](https://github.com/IMIO/scripts-buildout):
  `test-4.3.cfg` (entry point buildout actually runs) → `base.cfg` (shared parts) →
  `checkouts.cfg` (mr.developer sources)
- pyenv + virtualenv - Environment provisioning, driven by `Makefile` (hard prerequisite:
  pyenv 2.7 with `virtualenv` installed inside it)
- Lockfile: version pins live in `test-4.3.cfg` `[versions]`; buildout appends resolved
  pins to that same file (`update-versions-file = test-4.3.cfg`)

## Frameworks

**Core:**
- Plone 4.3.x - CMS/portal framework
- Zope 2 - Application server and framework foundation
- Zope Component Architecture (ZCA) - Component framework for plugin registration
- Products.PluggableAuthService (PAS) - Authentication and authorization plugin system

**Forms & UI:**
- plone.directives.form (>=1.1) - Form framework via ZCML
- plone.app.registry - Control panel and registry for settings
- plone.autoform - Automatic form generation
- z3c.form - Advanced form framework
- Products.PageTemplates - Template engine for views

**Testing:**
- plone.app.testing - Plone testing infrastructure
- plone.app.robotframework - Robot Framework integration for browser automation
- plone.testing - Core Zope testing utilities

**Build/Dev:**
- plone.recipe.codeanalysis - Code quality analysis (flake8 + flake8-isort), `[code-analysis]`
  in `base.cfg`. Also installs a git pre-commit hook (`pre-commit-hook = True`)
- collective.recipe.omelette - Egg inspection tool
- plone.versioncheck - Reports outdated pins (`make vcr` / `make vcn`)
- createcoverage - Coverage runs (`.coveragerc` scopes to `src/collective/googleauthenticator/*`)
- Sphinx - Documentation generation, but **not** a buildout part: `builddocs.sh` invokes a
  system-wide `sphinx-build`

## Key Dependencies

**Critical:**
- plone.api (>=1.1.0) - Plone API for user/content management (`src/collective/googleauthenticator/helpers.py`, `src/collective/googleauthenticator/pas_plugin.py`)
- onetimepass (==0.2.2) - TOTP token generation and validation (`src/collective/googleauthenticator/helpers.py:205` via `valid_totp()`)
- ska (>=1.1, **pinned to 1.7.5**) - Cryptographic URL signing for secure data passage (`src/collective/googleauthenticator/helpers.py:22`, `pas_plugin.py:144`). 1.7.5 is the last Python 2.7 release; later versions need `setuptools>=61` (PEP 517) and cannot build on 2.7
- rebus (>=0.1) - Base32 encoding for secrets (`src/collective/googleauthenticator/helpers.py:100`)

**Infrastructure:**
- py2-ipaddress (>2.0.1) - IPv4/IPv6 address handling for IP whitelisting (`src/collective/googleauthenticator/helpers.py:459`)
- Products.PluggableAuthService - Plone authentication plugin architecture (`src/collective/googleauthenticator/__init__.py`)
- Products.CMFCore - Content management framework permissions
- Products.statusmessages - Status message system for user feedback
- zope.component - Component registry and utilities
- zope.i18n - Internationalization framework
- zope.i18nmessageid - Message factory for i18n
- zope.schema - Schema definition system
- zope.interface - Interface definitions and component contracts

## Configuration

**Environment:**
- Buildout entry point: `test-4.3.cfg` (extends `buildout.plonetest/test-4.3.x.cfg` + `base.cfg`)
- Active Plone version recorded in `.plone-version` (written by `make setup`, read by later
  `make` calls so `plone=` is only needed once)
- Application settings registry via plone.app.registry interface `IGoogleAuthenticatorSettings` (`src/collective/googleauthenticator/browser/controlpanel.py:24`)
- Settings stored in Plone's ZODB registry, not environment variables

**Build:**
- `setup.py` - Package definition and dependencies
- `Makefile` - Task entry point (`make setup plone=4.3`, `make buildout`, `make test`, `make vcn`)
- `test-4.3.cfg` - Plone 4.3 pins + extra eggs; the config buildout runs
- `base.cfg` - Shared parts (instance, test, omelette, code-analysis, robot, createcoverage)
- `checkouts.cfg` - mr.developer remotes and `[sources]` (currently no auto-checkouts)
- `requirements-4.3.txt` - pip bootstrap (pip 20.3.4, setuptools 44.1.1, zc.buildout 3.1.1, wheel 0.37.1)
- `.isort.cfg` - Import sorting (`force_alphabetical_sort`, `force_single_line`, `line_length = 120`)
- Examples in `examples/simple/` with buildout configs for different Plone versions

**Removed in the buildout migration (do not expect them):** `buildout.cfg`, `bootstrap.py`
(zc.buildout now comes from `requirements-4.3.txt` inside a virtualenv), `setup.cfg`
(superseded by `.isort.cfg`), `.travis.yml`.

## Configuration Settings

**Application Settings (stored in Plone registry):**
- `ska_secret_key` - Site-wide secret for URL signing (TextLine, required)
- `globally_enabled` - Force two-factor authentication for all users (Bool, default=True)
- `ip_addresses_whitelist` - CIDR/IP ranges to skip 2FA (Text, newline-separated)

## Platform Requirements

**Development:**
- Python 2.7 (EOL - legacy codebase), provisioned via pyenv; `Makefile` aborts if `pyenv`
  is absent, and errors if `virtualenv` is not installed inside the 2.7 pyenv
- setuptools for building
- Buildout for environment setup
- Plone 4.2.6 or higher (buildout targets 4.3; no Plone 5/6 config exists — the migration
  deliberately kept 4.3 only)
- Google Authenticator mobile app (iOS, Android, Blackberry, Windows Phone)

**Production:**
- Zope application server
- ZODB object database (included with Zope)
- Email server (implicit dependency for password reset emails)
- Python 2.7 runtime environment (legacy - no modern support)

---

*Stack analysis: 2026-07-28*
