# Coding Conventions

**Analysis Date:** 2026-07-28

## Naming Patterns

**Files:**
- Lowercase with underscores: `helpers.py`, `pas_plugin.py`, `adapter.py`
- Test files follow pattern: `test_*.py` (e.g., `test_helpers.py`, `test_generic.py`)
- Browser forms in subdirectories: `browser/forms/token.py`, `browser/forms/user_setup.py`

**Functions:**
- Snake case: `get_app_settings()`, `validate_token()`, `extract_ip_address_from_request()`
- Verb-noun pattern: `get_*`, `set_*`, `validate_*`, `extract_*`, `is_*`
- Getter functions prefix with `get_`: `get_user()`, `get_username()`, `get_secret()`
- Boolean functions prefix with `is_` or `has_`: `is_two_factor_authentication_globally_enabled()`, `has_enabled_two_factor_authentication()`

**Variables:**
- Snake case: `user_secret`, `browser_hash`, `validation_result`
- Module-level: lowercase with underscores
- Constants: UPPERCASE with underscores: `PRIVATE_IPS_PREFIX`, `DEBUG`, `PAS_ID`
- Temporary locals: short descriptive names (e.g., `user`, `request`, `data`)

**Types:**
- Interface classes: Prefix with `I`, PascalCase: `ITokenForm`, `IGoogleAuthenticatorLayer`, `ICameFrom`
- Implementation classes: PascalCase: `GoogleAuthenticatorPlugin`, `TokenForm`, `EnhancedUserDataPanelAdapter`
- Schema classes: suffix with `Schema`: `ITokenForm`, `IEnhancedUserDataSchema`

## Code Style

**Formatting:**
- isort for import sorting (configured in `.isort.cfg`; `setup.cfg` no longer exists)
- Line length: 120 characters (per `.isort.cfg`) — tightened from the old 200
- Indentation: 4 spaces (Python standard)
- No enforced formatter beyond isort

**Linting:**
- flake8 for code analysis, plus the `flake8-isort` extension
- Run via: `bin/code-analysis` (plone.recipe.codeanalysis)
- Configuration in `base.cfg` `[code-analysis]`: `return-status-codes = True`,
  `pre-commit-hook = True`, `directory = src/collective/googleauthenticator`
- `flake8-ignore = E123,E124,E501,E126,E127,E128,W391,C901,W503,W504`
- **Currently failing** on ~40 pre-existing findings in `src/` (mostly `I001`/`I003`/`I004`
  isort ordering, plus `F401` unused imports and `W292`/`W293` whitespace, concentrated in
  `src/collective/googleauthenticator/tests/`). Because `pre-commit-hook` is enabled,
  commits need `--no-verify` until that debt is cleared. CI does not run code-analysis.

## Import Organization

**Order:**
1. Python standard library imports (logging, uuid, hashlib, etc.)
2. External framework/package imports (zope, plone, Products)
3. Third-party package imports (onetimepass, ska, rebus, ipaddress)
4. Internal package imports (collective.googleauthenticator)

**Example from `helpers.py`:**
```python
# Standard library
import logging
from hashlib import sha1
from urllib import urlencode, unquote, quote
from urlparse import urlparse
from uuid import uuid4

# Zope/external
from zope.component import getUtility
from zope.globalrequest import getRequest
from zope.i18n import translate
from zope.i18nmessageid import MessageFactory

# Third-party
from onetimepass import valid_totp
from ska import sign_url, validate_signed_request_data

# Internal
from collective.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings
```

**Path Aliases:**
- None detected. Imports use absolute paths from `src/` root via package structure.
- isort settings (from `.isort.cfg`):
  - `force_alphabetical_sort = True`
  - `force_single_line = True`
  - `line_length = 120`
  - `lines_after_imports = 2`
  - (`not_skip = __init__.py` was dropped along with `setup.cfg`)

## Error Handling

**Patterns:**
- Try/except blocks for defensive programming:
  ```python
  try:
      key, value = part.split('=', 1)
      request_data.update({key: unquote(value)})
  except ValueError:
      pass
  ```
- Exception logging for debugging:
  ```python
  except Exception as e:
      logger.debug(str(e))
  ```
- Status messages for user feedback via `IStatusMessage`:
  ```python
  IStatusMessage(self.request).addStatusMessage(
      _("Invalid data. Details: {0}".format(reason)), 'error')
  ```
- Silent failures with logging when handling optional features (e.g., IP whitelisting parsing)

## Logging

**Framework:** Standard Python `logging` module

**Logger Creation:**
- Pattern: `logger = logging.getLogger(__file__)` or `logger = logging.getLogger("collective.googleauthenticator")`
- Per-module loggers with package/module name
- Example from `adapter.py`:
  ```python
  logger = logging.getLogger(__file__)
  ```
- Example from `helpers.py`:
  ```python
  logger = logging.getLogger("collective.googleauthenticator")
  ```

**Logging Levels:**
- `logger.debug()` used for troubleshooting and optional diagnostics
- `logger.info()` used sparingly; not observed in provided code
- Sensitive information (secrets) logged at debug level with comments: `# logger.debug(secret)`

**When to Log:**
- Entry points for plugin methods: `logger.debug("Found user: {0}".format(...))`
- Error conditions and exceptions: `logger.debug(str(e))`
- Feature toggling: `logger.debug("Two-step verification enabled: {0}".format(...))`

## Comments

**When to Comment:**
- Module-level docstrings explaining purpose (e.g., `pas_plugin.py` module docstring explains the plugin's logic)
- Function docstrings with `:param`, `:return` documentation
- Complex algorithms (e.g., IP whitelist parsing with proxy handling)
- FIXME/TODO for known issues:
  ```python
  # TODO: Return hashed version if ``hashed`` is set to True.
  ```
- Disabled code kept as reference:
  ```python
  #return self.context.setMemberProperties({'enable_two_factor_authentication': value})
  ```

**JSDoc/TSDoc:**
- Not applicable (Python package, no TypeScript)
- Docstrings follow reStructuredText format for Sphinx documentation
- Parameter documentation uses `:param Type name: description` format
- Return documentation uses `:return type: description` format

**Example:**
```python
def get_or_create_secret(user, overwrite=False):
    """
    Gets or creates token secret for the user given. Checks first if user
    given has a ``secret`` generated.
    If not, generate it for him and save it in his profile
    (``two_factor_authentication_secret``).

    :param Products.PlonePAS.tools.memberdata user: If provided, used.
        Otherwise ``plone.api.user.get_current`` is used to obtain the user.
    :return string:
    """
```

## Function Design

**Size:** Functions are typically 5-30 lines; helper functions often shorter (1-5 lines)

**Parameters:**
- Keyword arguments with defaults for optional dependencies (request=None, user=None, overwrite=False)
- Pattern: Check if None, then assign from global getter:
  ```python
  def get_secret(user=None, hashed=False):
      if user is None:
          user = api.user.get_current()
      if user:
          secret = user.getProperty('two_factor_authentication_secret')
  ```
- Parameter order: required positional args, then keyword args

**Return Values:**
- Functions return None implicitly when no explicit return (e.g., setters)
- Explicit None returns in some setters: `return # Read only` pattern
- Boolean returns for validation functions: `return True/False`
- Object/list returns for getters: `return [objects]`

**Side Effects:**
- Logging via module-level logger
- Setting member properties via `user.setMemberProperties(mapping={...})`
- Status message manipulation via `IStatusMessage`

## Module Design

**Exports:**
- Explicit imports in `__init__.py` for public API:
  ```python
  from collective.googleauthenticator.pas_plugin import (
      GoogleAuthenticatorPlugin, addGoogleAuthenticatorPlugin, manage_addGoogleAuthenticatorPluginForm
  )
  ```
- Helper functions exposed directly from `helpers.py` (not re-exported in `__init__.py`)
- Browser/form classes grouped in `browser/` and `browser/forms/` subdirectories

**Barrel Files:**
- `__init__.py` files import and re-export primary plugin classes
- `__init__.py` includes initialization function for Zope product registration:
  ```python
  def initialize(context):
      """Initializer called when used as a Zope 2 product."""
      registerMultiPlugin(GoogleAuthenticatorPlugin.meta_type)
      context.registerClass(GoogleAuthenticatorPlugin, ...)
  ```
- Namespace packages via `namespace_packages = ['collective', ]` in `setup.py`

**Package Structure:**
- `src/collective/googleauthenticator/` main package
- `src/collective/googleauthenticator/browser/` for browser views/forms
- `src/collective/googleauthenticator/tests/` for test modules
- `src/collective/googleauthenticator/upgrades/` for upgrade steps

---

*Convention analysis: 2026-07-28*
