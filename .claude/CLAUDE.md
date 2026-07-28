<!-- GSD:project-start source:PROJECT.md -->

## Project

**imio.googleauthenticator**

A Plone 4.3 / Python 2.7 PAS plugin providing TOTP two-factor authentication (Google
Authenticator app) for users and site admins **inside** a Plone site. Forked from
[collective.googleauthenticator](https://github.com/collective/collective.googleauthenticator)
and being renamed, hardened, and made deployable alongside `imio.dms.mail`.

Deliberately temporary. It exists because iMio's main projects are still on Plone 4 and need
MFA now. When those projects reach Plone 6 (~1–2 years), this package is dropped and MFA moves
to Keycloak.

**Core Value:** A second factor that actually holds for in-site users, and that can be deployed alongside
`imio.dms.mail` without colliding with it.

### Constraints

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
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 2.7 - Only supported/tested version. `setup.py` classifiers still advertise 2.6,
- ZCML - Zope configuration language used throughout
- JavaScript - Minimal client-side logic in `src/collective/googleauthenticator/browser/static/`
- HTML/TAL - Plone page templates for views

## Runtime

- Zope application server
- Python 2.7+ (deprecated, legacy support)
- setuptools - Primary package manager
- Buildout - Dependency and configuration management, multi-file layout from
- pyenv + virtualenv - Environment provisioning, driven by `Makefile` (hard prerequisite:
- Lockfile: version pins live in `test-4.3.cfg` `[versions]`; buildout appends resolved

## Frameworks

- Plone 4.3.x - CMS/portal framework
- Zope 2 - Application server and framework foundation
- Zope Component Architecture (ZCA) - Component framework for plugin registration
- Products.PluggableAuthService (PAS) - Authentication and authorization plugin system
- plone.directives.form (>=1.1) - Form framework via ZCML
- plone.app.registry - Control panel and registry for settings
- plone.autoform - Automatic form generation
- z3c.form - Advanced form framework
- Products.PageTemplates - Template engine for views
- plone.app.testing - Plone testing infrastructure
- plone.app.robotframework - Robot Framework integration for browser automation
- plone.testing - Core Zope testing utilities
- plone.recipe.codeanalysis - Code quality analysis (flake8 + flake8-isort), `[code-analysis]`
- collective.recipe.omelette - Egg inspection tool
- plone.versioncheck - Reports outdated pins (`make vcr` / `make vcn`)
- createcoverage - Coverage runs (`.coveragerc` scopes to `src/collective/googleauthenticator/*`)
- Sphinx - Documentation generation, but **not** a buildout part: `builddocs.sh` invokes a

## Key Dependencies

- plone.api (>=1.1.0) - Plone API for user/content management (`src/collective/googleauthenticator/helpers.py`, `src/collective/googleauthenticator/pas_plugin.py`)
- onetimepass (==0.2.2) - TOTP token generation and validation (`src/collective/googleauthenticator/helpers.py:205` via `valid_totp()`)
- ska (>=1.1, **pinned to 1.7.5**) - Cryptographic URL signing for secure data passage (`src/collective/googleauthenticator/helpers.py:22`, `pas_plugin.py:144`). 1.7.5 is the last Python 2.7 release; later versions need `setuptools>=61` (PEP 517) and cannot build on 2.7
- rebus (>=0.1) - Base32 encoding for secrets (`src/collective/googleauthenticator/helpers.py:100`)
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

- Buildout entry point: `test-4.3.cfg` (extends `buildout.plonetest/test-4.3.x.cfg` + `base.cfg`)
- Active Plone version recorded in `.plone-version` (written by `make setup`, read by later
- Application settings registry via plone.app.registry interface `IGoogleAuthenticatorSettings` (`src/collective/googleauthenticator/browser/controlpanel.py:24`)
- Settings stored in Plone's ZODB registry, not environment variables
- `setup.py` - Package definition and dependencies
- `Makefile` - Task entry point (`make setup plone=4.3`, `make buildout`, `make test`, `make vcn`)
- `test-4.3.cfg` - Plone 4.3 pins + extra eggs; the config buildout runs
- `base.cfg` - Shared parts (instance, test, omelette, code-analysis, robot, createcoverage)
- `checkouts.cfg` - mr.developer remotes and `[sources]` (currently no auto-checkouts)
- `requirements-4.3.txt` - pip bootstrap (pip 20.3.4, setuptools 44.1.1, zc.buildout 3.1.1, wheel 0.37.1)
- `.isort.cfg` - Import sorting (`force_alphabetical_sort`, `force_single_line`, `line_length = 120`)
- Examples in `examples/simple/` with buildout configs for different Plone versions

## Configuration Settings

- `ska_secret_key` - Site-wide secret for URL signing (TextLine, required)
- `globally_enabled` - Force two-factor authentication for all users (Bool, default=True)
- `ip_addresses_whitelist` - CIDR/IP ranges to skip 2FA (Text, newline-separated)

## Platform Requirements

- Python 2.7 (EOL - legacy codebase), provisioned via pyenv; `Makefile` aborts if `pyenv`
- setuptools for building
- Buildout for environment setup
- Plone 4.2.6 or higher (buildout targets 4.3; no Plone 5/6 config exists — the migration
- Google Authenticator mobile app (iOS, Android, Blackberry, Windows Phone)
- Zope application server
- ZODB object database (included with Zope)
- Email server (implicit dependency for password reset emails)
- Python 2.7 runtime environment (legacy - no modern support)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Lowercase with underscores: `helpers.py`, `pas_plugin.py`, `adapter.py`
- Test files follow pattern: `test_*.py` (e.g., `test_helpers.py`, `test_generic.py`)
- Browser forms in subdirectories: `browser/forms/token.py`, `browser/forms/user_setup.py`
- Snake case: `get_app_settings()`, `validate_token()`, `extract_ip_address_from_request()`
- Verb-noun pattern: `get_*`, `set_*`, `validate_*`, `extract_*`, `is_*`
- Getter functions prefix with `get_`: `get_user()`, `get_username()`, `get_secret()`
- Boolean functions prefix with `is_` or `has_`: `is_two_factor_authentication_globally_enabled()`, `has_enabled_two_factor_authentication()`
- Snake case: `user_secret`, `browser_hash`, `validation_result`
- Module-level: lowercase with underscores
- Constants: UPPERCASE with underscores: `PRIVATE_IPS_PREFIX`, `DEBUG`, `PAS_ID`
- Temporary locals: short descriptive names (e.g., `user`, `request`, `data`)
- Interface classes: Prefix with `I`, PascalCase: `ITokenForm`, `IGoogleAuthenticatorLayer`, `ICameFrom`
- Implementation classes: PascalCase: `GoogleAuthenticatorPlugin`, `TokenForm`, `EnhancedUserDataPanelAdapter`
- Schema classes: suffix with `Schema`: `ITokenForm`, `IEnhancedUserDataSchema`

## Code Style

- isort for import sorting (configured in `.isort.cfg`; `setup.cfg` no longer exists)
- Line length: 120 characters (per `.isort.cfg`) — tightened from the old 200
- Indentation: 4 spaces (Python standard)
- No enforced formatter beyond isort
- flake8 for code analysis, plus the `flake8-isort` extension
- Run via: `bin/code-analysis` (plone.recipe.codeanalysis)
- Configuration in `base.cfg` `[code-analysis]`: `return-status-codes = True`,
- `flake8-ignore = E123,E124,E501,E126,E127,E128,W391,C901,W503,W504`
- **Currently failing** on ~40 pre-existing findings in `src/` (mostly `I001`/`I003`/`I004`

## Import Organization

- None detected. Imports use absolute paths from `src/` root via package structure.
- isort settings (from `.isort.cfg`):

## Error Handling

- Try/except blocks for defensive programming:
- Exception logging for debugging:
- Status messages for user feedback via `IStatusMessage`:
- Silent failures with logging when handling optional features (e.g., IP whitelisting parsing)

## Logging

- Pattern: `logger = logging.getLogger(__file__)` or `logger = logging.getLogger("collective.googleauthenticator")`
- Per-module loggers with package/module name
- Example from `adapter.py`:
- Example from `helpers.py`:
- `logger.debug()` used for troubleshooting and optional diagnostics
- `logger.info()` used sparingly; not observed in provided code
- Sensitive information (secrets) logged at debug level with comments: `# logger.debug(secret)`
- Entry points for plugin methods: `logger.debug("Found user: {0}".format(...))`
- Error conditions and exceptions: `logger.debug(str(e))`
- Feature toggling: `logger.debug("Two-step verification enabled: {0}".format(...))`

## Comments

- Module-level docstrings explaining purpose (e.g., `pas_plugin.py` module docstring explains the plugin's logic)
- Function docstrings with `:param`, `:return` documentation
- Complex algorithms (e.g., IP whitelist parsing with proxy handling)
- FIXME/TODO for known issues:
- Disabled code kept as reference:
- Not applicable (Python package, no TypeScript)
- Docstrings follow reStructuredText format for Sphinx documentation
- Parameter documentation uses `:param Type name: description` format
- Return documentation uses `:return type: description` format

## Function Design

- Keyword arguments with defaults for optional dependencies (request=None, user=None, overwrite=False)
- Pattern: Check if None, then assign from global getter:
- Parameter order: required positional args, then keyword args
- Functions return None implicitly when no explicit return (e.g., setters)
- Explicit None returns in some setters: `return # Read only` pattern
- Boolean returns for validation functions: `return True/False`
- Object/list returns for getters: `return [objects]`
- Logging via module-level logger
- Setting member properties via `user.setMemberProperties(mapping={...})`
- Status message manipulation via `IStatusMessage`

## Module Design

- Explicit imports in `__init__.py` for public API:
- Helper functions exposed directly from `helpers.py` (not re-exported in `__init__.py`)
- Browser/form classes grouped in `browser/` and `browser/forms/` subdirectories
- `__init__.py` files import and re-export primary plugin classes
- `__init__.py` includes initialization function for Zope product registration:
- Namespace packages via `namespace_packages = ['collective', ]` in `setup.py`
- `src/collective/googleauthenticator/` main package
- `src/collective/googleauthenticator/browser/` for browser views/forms
- `src/collective/googleauthenticator/tests/` for test modules
- `src/collective/googleauthenticator/upgrades/` for upgrade steps

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| GoogleAuthenticatorPlugin | PAS authentication plugin - intercepts login, validates user credentials, redirects to 2FA token screen if enabled | `src/collective/googleauthenticator/pas_plugin.py` |
| EnhancedUserDataPanelAdapter | Exposes 2FA properties (enable_two_factor_authentication, two_factor_authentication_secret, bar_code_reset_token) to user profile UI | `src/collective/googleauthenticator/adapter.py` |
| CameFromAdapter | Extracts post-login redirect URL from HTTP referer since Plone form field removed | `src/collective/googleauthenticator/adapter.py` |
| IEnhancedUserDataSchema | Schema definition extending Plone's user properties with 2FA fields | `src/collective/googleauthenticator/userdataschema.py` |
| Token validation form | z3c.form for collecting and validating one-time password token | `src/collective/googleauthenticator/browser/forms/token.py` |
| User setup form | Generates QR code, presents secret/recovery codes for new 2FA setup | `src/collective/googleauthenticator/browser/forms/user_setup.py` |
| Control panel | Settings form for global 2FA configuration (secret key, IP whitelist, global enable) | `src/collective/googleauthenticator/browser/controlpanel.py` |
| Helper functions | Token generation/validation (TOTP), secret management, URL signing, IP validation | `src/collective/googleauthenticator/helpers.py` |

## Pattern Overview

- Extends Plone's user authentication pipeline via PAS plugin interface
- Intercepts credentials during login, validates password, then redirects to 2FA form
- Uses `ska` library for cryptographic signing of URLs to protect redirect flow
- Uses `onetimepass` for TOTP token validation (Google Authenticator compatible)
- Stores 2FA settings in user profile properties (enable flag + secret key)
- Optional IP whitelist to bypass 2FA for trusted networks

## Layers

- Purpose: Intercept Plone login flow and inject 2FA verification step
- Location: `src/collective/googleauthenticator/pas_plugin.py`
- Contains: `GoogleAuthenticatorPlugin(BasePlugin)` implementing `IAuthenticationPlugin`
- Depends on: `plone.api`, `ska`, `adapter.CameFromAdapter`, `helpers` module
- Used by: Plone's PluggableAuthService during login
- Purpose: Render user-facing forms for token entry, 2FA setup, and settings
- Location: `src/collective/googleauthenticator/browser/`
- Contains: z3c.form classes, view handlers, control panel registration
- Depends on: `plone.directives.form`, `z3c.form`, `helpers` module
- Used by: HTTP requests to `@@google-authenticator-token`, `@@setup-two-factor-authentication`, etc.
- Purpose: Core business logic for TOTP validation, secret generation, URL signing, IP checking
- Location: `src/collective/googleauthenticator/helpers.py`
- Contains: 27+ helper functions for token validation, secret management, whitelisting
- Depends on: `onetimepass`, `ska`, `plone.api`, `plone.registry`
- Used by: PAS plugin, forms, views, user creation handlers
- Purpose: Define and manage 2FA-related user profile fields
- Location: `src/collective/googleauthenticator/userdataschema.py`
- Contains: `IEnhancedUserDataSchema` interface, `UserDataSchemaProvider` adapter, user creation event handler
- Depends on: `plone.app.users`, `Products.PluggableAuthService`
- Used by: Plone's user management system during user creation and profile updates
- Purpose: Generic Setup (GS) profile and installation handlers
- Location: `src/collective/googleauthenticator/setuphandlers.py`, `src/collective/googleauthenticator/profiles/`
- Contains: PAS plugin registration, secret key generation on install
- Depends on: `Products.PluggableAuthService`, `plone.registry`
- Used by: Plone installation process

## Data Flow

### Primary Login Flow (with 2FA enabled)

### Alternative Flows

- Form renders QR code via `helpers.get_token_description()` (Google Charts API)
- Secret generated via `helpers.generate_secret()`
- User scans code with Google Authenticator app
- User enters test token to confirm before saving
- No server-side session state during 2FA flow
- Uses cryptographic URL signing (`ska` library) instead: URL contains `auth_user` and signature
- Secret key for signing combines user's 2FA secret + browser hash + global site secret
- Browser hash provides device-binding (different browser = different signature)

## Key Abstractions

- Purpose: Generate time-based one-time passwords compatible with Google Authenticator
- Examples: `helpers.validate_token()`, `helpers.get_secret()`, `helpers.generate_secret()`
- Pattern: Delegates to `onetimepass.valid_totp()` for RFC 4226/4328 compliance
- Purpose: Protect redirect flow from URL tampering during 2FA verification step
- Examples: `helpers.sign_user_data()`, `helpers.validate_user_data()`, `helpers.get_ska_secret_key()`
- Pattern: Uses `ska` library with composite secret (user secret + browser hash + global secret)
- Purpose: Allow trusted networks to bypass 2FA
- Examples: `helpers.is_whitelisted_client()`, `helpers.extract_ip_address_from_request()`, `helpers.get_ip_ranges()`
- Pattern: Supports CIDR notation for IP ranges, handles proxy headers (`X-Forwarded-For`)
- Purpose: Tie signed URLs to a specific browser to prevent session hijacking
- Examples: `helpers.get_browser_hash()`
- Pattern: SHA1 hash of `User-Agent` header included in `ska` signing key

## Entry Points

- Location: `src/collective/googleauthenticator/pas_plugin.py:66`
- Triggers: Every user login attempt (via `authenticateCredentials()` method)
- Responsibilities: Intercept credentials, validate password, redirect to 2FA form if needed
- Location: `src/collective/googleauthenticator/__init__.py:13-22`
- Triggers: When Plone loads the product
- Responsibilities: Register PAS plugin class with `registerMultiPlugin()`
- Location: `src/collective/googleauthenticator/profiles/default/`
- Triggers: When add-on is installed via Plone control panel
- Responsibilities: Register control panel, browser layer, CSS/JS, register adapter factories
- Location: `src/collective/googleauthenticator/userdataschema.py:76-96`
- Triggers: `IPrincipalCreatedEvent` when new user created
- Responsibilities: If globally_enabled setting true, generate secret and enable 2FA for new users

## Architectural Constraints

- **Threading:** Single-threaded Zope2 WSGI application. No explicit threading used. Global request accessed via `getRequest()`.
- **Global state:** 
- **Circular imports:** None detected. Adapter callbacks create loose coupling between `pas_plugin` and `adapter`.
- **Authentication ordering:** Plugin position in PAS plugin list matters. Typically ordered last so standard auth plugins run first, this plugin only validates 2FA on successful password auth.
- **User property mutation:** User 2FA properties set via `user.setMemberProperties()` (Plone MemberData mutation API). No direct database writes.

## Anti-Patterns

### Credentials Dictionary Mutation (Design Compromise)

### Bearer Token in Query String (Security Shortcut)

### Browser Hash Fingerprinting (Weak Binding)

## Error Handling

- Token validation returns boolean; form checks and shows error to user
- User data signing/verification uses `ska` library's `SignatureValidationResult` object
- PAS plugin catches plugin exceptions, logs, and continues with next plugin (per `Products.PluggableAuthService` protocol)
- IP validation swallows address parsing exceptions, treats as not-whitelisted
- User property lookups return empty string if property missing, no exceptions

## Cross-Cutting Concerns

- TOTP validation via `onetimepass.valid_totp()` (RFC 4226/4328 compliant)
- URL signing validation via `ska.validate_signed_request_data()` (time-window tolerance included)
- IP range validation via `ipaddress` stdlib (handles CIDR notation, IPv4/IPv6)

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
