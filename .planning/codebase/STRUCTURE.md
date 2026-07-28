# Codebase Structure

**Analysis Date:** 2026-07-28

## Directory Layout

```
/srv/src/imio.googleauthenticator/
├── src/                           # Package source code
│   └── collective/
│       └── googleauthenticator/   # Main package
│           ├── browser/           # View layer (forms, templates, static assets)
│           │   ├── forms/         # z3c.form form classes
│           │   ├── static/        # CSS, JS, images
│           │   └── *.py           # View classes
│           ├── tests/             # Test suite
│           ├── profiles/          # Generic Setup configuration
│           │   ├── default/       # Installation profile
│           │   └── uninstall/     # Uninstall profile
│           ├── upgrades/          # Database upgrade scripts
│           ├── locales/           # i18n translations
│           ├── skins/             # Old-style Plone skins (fallback)
│           ├── www/               # Page template files (.pt)
│           ├── *.py               # Core modules
│           └── __init__.py        # Package initialization
├── docs/                          # Sphinx documentation
├── examples/simple/               # Example Plone instance (own, unrelated buildout)
├── .github/workflows/             # CI — package-test.yml (delegates to IMIO/gha-workflows)
├── Makefile                       # Task entry point (setup / buildout / test / vcn)
├── test-4.3.cfg                   # Buildout entry point: Plone 4.3 pins + extra eggs
├── base.cfg                       # Shared buildout parts (instance, test, code-analysis, ...)
├── checkouts.cfg                  # mr.developer remotes + [sources]
├── requirements-4.3.txt           # pip bootstrap for the virtualenv
├── .isort.cfg                     # Import sorting rules
├── .coveragerc                    # Coverage scope
├── setup.py                       # Package definition
└── CLAUDE.md                      # Claude Code guidance
```

**Not present** (removed in the buildout migration): `buildout.cfg`, `bootstrap.py`,
`setup.cfg`, `.travis.yml`. Root config now follows the multi-file
[IMIO/scripts-buildout](https://github.com/IMIO/scripts-buildout) layout, one file per
Plone version — and only 4.3 exists here.

## Directory Purposes

**`src/collective/googleauthenticator/`:**
- Purpose: Main package containing all add-on logic
- Contains: Core modules (10 .py files), sub-packages for browser, tests, etc.
- Key files: `__init__.py`, `pas_plugin.py`, `helpers.py`, `adapter.py`

**`src/collective/googleauthenticator/browser/`:**
- Purpose: User-facing view components and form handlers
- Contains: z3c.form classes, Zope view classes, form templates
- Key files: `controlpanel.py`, `settings_helper.py`, form classes in `forms/`

**`src/collective/googleauthenticator/browser/forms/`:**
- Purpose: z3c.form implementations for 2FA workflows
- Contains: Token validation form, user setup form, reset forms
- Key files: `token.py`, `user_setup.py`, `request_bar_code_reset.py`, `reset_bar_code.py`

**`src/collective/googleauthenticator/tests/`:**
- Purpose: Test suite for the add-on
- Contains: Unit and integration tests, test fixtures, base test classes
- Key files: `base.py` (shared test utilities), `test_*.py` modules

**`src/collective/googleauthenticator/profiles/`:**
- Purpose: Generic Setup installation and configuration profiles
- Contains: XML configuration files defining site setup, control panel, adapters, browser layer
- Key files: `default/metadata.xml`, `default/registry.xml`, `default/browserlayer.xml`, `default/componentregistry.xml`

**`src/collective/googleauthenticator/profiles/default/`:**
- Purpose: Standard installation profile applied when add-on installed
- Contains: Registry settings, control panel registration, skins, CSS/JS registration
- Key files: `registry.xml` (settings schema), `controlpanel.xml` (control panel entry), `componentregistry.xml` (adapters/utilities)

**`src/collective/googleauthenticator/upgrades/`:**
- Purpose: Database upgrade handlers for version migrations
- Contains: Upgrade step profiles and Python handlers for product version bumps
- Key files: `to0301.py` (upgrade to v0.3.0)

**`src/collective/googleauthenticator/locales/`:**
- Purpose: Internationalization (i18n) message translations
- Contains: `.po` files with translated strings for different languages
- Key files: `collective.googleauthenticator.po` (message template)

**`src/collective/googleauthenticator/skins/`:**
- Purpose: Legacy Plone skin layer (fallback when templates not found elsewhere)
- Contains: Old-style .pt template files
- Key files: Skin directory `googleauthenticator_custom/`

**`src/collective/googleauthenticator/www/`:**
- Purpose: Zope Page Template files for forms and views
- Contains: `.pt` files for rendering PAS plugin add form and templates
- Key files: `add_google_authenticator_form.pt` (PAS plugin installation form)

**`docs/`:**
- Purpose: Sphinx documentation source
- Contains: `.rst` files and `conf.py` for building HTML documentation
- Key files: `conf.py`

**`examples/simple/`:**
- Purpose: Example Plone buildout configuration for testing locally
- Contains: Buildout config files and bootstrap script
- Key files: `buildout-plone4.cfg`, `buildout-base.cfg`, `buildout-dvl.cfg`,
  `buildout-sources.cfg`, `versions.cfg`, `bootstrap.py`
- Independent of the root buildout — untouched by the scripts-buildout migration, and still
  uses the old `bootstrap.py` flow

## Key File Locations

**Entry Points:**
- `src/collective/googleauthenticator/__init__.py`: Zope product initialization (PAS plugin registration)
- `src/collective/googleauthenticator/pas_plugin.py`: Main PAS authentication plugin intercepting login
- `src/collective/googleauthenticator/browser/forms/token.py`: Token validation form (user-facing 2FA screen)

**Configuration:**
- `src/collective/googleauthenticator/browser/controlpanel.py`: Settings interface and control panel form
- `src/collective/googleauthenticator/profiles/default/registry.xml`: Global settings schema
- `src/collective/googleauthenticator/setuphandlers.py`: Installation handler (secret key generation)

**Core Logic:**
- `src/collective/googleauthenticator/helpers.py`: 27+ helper functions (token validation, secret management, signing)
- `src/collective/googleauthenticator/adapter.py`: Adapters (EnhancedUserDataPanelAdapter, CameFromAdapter, ICameFrom interface)
- `src/collective/googleauthenticator/userdataschema.py`: User profile schema extensions (2FA fields)

**Testing:**
- `src/collective/googleauthenticator/tests/base.py`: Shared test utilities and base classes
- `src/collective/googleauthenticator/tests/test_generic.py`: Integration tests (installation, views)
- `src/collective/googleauthenticator/tests/test_helpers.py`: Unit tests for helper functions
- `src/collective/googleauthenticator/tests/test_pas_plugin.py`: PAS plugin tests
- `src/collective/googleauthenticator/tests/test_security.py`: Security-related tests

## Naming Conventions

**Files:**
- `*.py`: Python modules (lowercase, underscores for multi-word names)
- `*.pt`: Zope Page Templates (mixedCase names common in Plone)
- `*.xml`: Generic Setup configuration (lowercase descriptive names)
- `test_*.py`: Test modules (prefixed with `test_`)

**Directories:**
- Package namespace: `collective.googleauthenticator` (lowercase with dot notation)
- Sub-packages: `browser`, `tests`, `profiles`, `upgrades` (lowercase, descriptive, plural for collections)
- Profile directories: `default`, `uninstall` (standard GS names)

**Functions (in helpers.py):**
- `get_*()`: Retrieve data (e.g., `get_app_settings()`, `get_secret()`, `get_user()`)
- `validate_*()`: Verify/validate data (e.g., `validate_token()`, `validate_user_data()`)
- `is_*()`: Boolean predicates (e.g., `is_whitelisted_client()`, `is_two_factor_authentication_globally_enabled()`)
- `enable_*()` / `disable_*()`: State changes (e.g., `enable_two_factor_authentication_for_users()`)
- `extract_*()`: Parse/extract from requests (e.g., `extract_request_data()`, `extract_ip_address_from_request()`)

**Classes:**
- `I*`: Zope interface definitions (e.g., `IEnhancedUserDataSchema`, `IGoogleAuthenticatorLayer`, `ICameFrom`)
- `*Form`: z3c.form classes (e.g., `TokenForm`, `GoogleAuthenticatorSettingsEditForm`)
- `*Plugin`: PAS plugin classes (e.g., `GoogleAuthenticatorPlugin`)
- `*Adapter`: Adapter classes (e.g., `EnhancedUserDataPanelAdapter`, `CameFromAdapter`)
- `*Handler`: Event handlers (e.g., `userCreatedHandler()`)

**Properties (on user objects):**
- `enable_two_factor_authentication`: Boolean flag (True = 2FA enabled)
- `two_factor_authentication_secret`: Base32-encoded secret key for TOTP
- `bar_code_reset_token`: Token for resetting/recovering 2FA (emergency access)

## Where to Add New Code

**New Authentication/Authorization Feature:**
- Primary code: `src/collective/googleauthenticator/pas_plugin.py` (extend `authenticateCredentials()` or add new method)
- Helpers: Add functions to `src/collective/googleauthenticator/helpers.py`
- Tests: Add test class to `src/collective/googleauthenticator/tests/test_pas_plugin.py`

**New User-Facing Form/View:**
- Implementation: Create new form class in `src/collective/googleauthenticator/browser/forms/` (inherit from `plone.directives.form.SchemaForm`)
- Template: Add `.pt` file to `src/collective/googleauthenticator/www/` if needed for custom rendering
- Registration: Register view in Generic Setup profile at `src/collective/googleauthenticator/profiles/default/configure.zcml` (or via decorator)
- Tests: Add integration test to `src/collective/googleauthenticator/tests/test_generic.py`

**New Global Settings:**
- Schema: Add field to `IGoogleAuthenticatorSettings` interface in `src/collective/googleauthenticator/browser/controlpanel.py`
- Registration: Auto-registered via `plone.directives.form` decorators (no manual XML needed)
- Access: Use `helpers.get_app_settings()` to retrieve settings in your code
- Tests: Add test to verify new setting in `src/collective/googleauthenticator/tests/test_generic.py`

**New User Profile Property:**
- Schema: Add field to `IEnhancedUserDataSchema` in `src/collective/googleauthenticator/userdataschema.py`
- Access: Read via `user.getProperty('field_name')`, write via `user.setMemberProperties(mapping={...})`
- Adapter: If property should be editable in user preferences panel, add getter/setter to `EnhancedUserDataPanelAdapter`
- Tests: Add unit test to `src/collective/googleauthenticator/tests/test_helpers.py`

**New Helper Function:**
- Location: `src/collective/googleauthenticator/helpers.py`
- Pattern: Follow existing conventions (`get_*`, `validate_*`, `is_*`, `extract_*` prefixes)
- Import in calling code: `from collective.googleauthenticator.helpers import function_name`
- Tests: Add test to `src/collective/googleauthenticator/tests/test_helpers.py`

**Utilities/Shared Code:**
- Location: `src/collective/googleauthenticator/helpers.py` (not in separate util modules)
- Reason: Small codebase; centralized helpers keep dependencies clear and reduce fragmentation

## Special Directories

**`src/collective/googleauthenticator/profiles/default/`:**
- Purpose: Generic Setup installation profile
- Generated: No (hand-authored XML configuration)
- Committed: Yes (committed to version control)
- Files applied on install: All XML files in this directory (registry, actions, controlpanel, etc.)

**`src/collective/googleauthenticator/browser/static/`:**
- Purpose: Static assets (CSS, JavaScript, images) served by web server
- Generated: No (hand-authored)
- Committed: Yes
- Accessible via: `++resource++collective.googleauthenticator/` URL prefix in templates

**`src/collective/googleauthenticator/locales/`:**
- Purpose: i18n message translations
- Generated: `.po` files generated from source code by i18ndude, `.mo` files compiled by buildout
- Committed: `.po` files committed, `.mo` compiled at build time
- Workflow: Extract messages from source code → translate → compile to `.mo` for runtime

**`src/collective/googleauthenticator/upgrades/`:**
- Purpose: Handle schema/data migrations between product versions
- Generated: No
- Committed: Yes
- Usage: One subdirectory per version (e.g., `upgrades/profiles/0301/`) with handlers

---

*Structure analysis: 2026-07-28*
