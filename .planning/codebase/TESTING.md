# Testing Patterns

**Analysis Date:** 2026-07-28

## Test Framework

**Runner:**
- Buildout-based: `bin/test` command (configured via `.travis.yml`)
- Underlying framework: unittest2 (Python 2.7 compatible)
- Config: `setup.py` with `extras_require = {'test': ['plone.app.testing', 'plone.app.robotframework']}`

**Assertion Library:**
- unittest2 assertions (assertEqual, assertTrue, assertFalse, assertIn, etc.)
- No external assertion library (plain unittest)

**Test Dependencies:**
- `plone.app.testing` - Plone integration testing layer
- `plone.app.robotframework` - Robot Framework integration
- `unittest2` - Python 2.7-compatible unittest
- `robotsuite` - Robot test suite runner

**Run Commands:**
```bash
bin/test                           # Run all unit/integration tests
bin/test -t robot_test             # Run specific Robot Framework tests
bin/createcoverage --output-dir=htmlcov -t "--layer=!Robot"  # Coverage (excludes Robot tests)
bin/code-analysis                  # Run flake8 linting
```

## Test File Organization

**Location:**
- `src/collective/googleauthenticator/tests/` directory
- Co-located with source package, not in separate test directory

**Naming:**
- Pattern: `test_*.py` for unit/integration tests
- Example: `test_helpers.py`, `test_generic.py`, `test_pas_plugin.py`, `test_security.py`, `test_robot.py`
- Robot tests: `robot_test.txt` (Robot Framework format, not Python)

**Structure:**
```
src/collective/googleauthenticator/
├── tests/
│   ├── __init__.py
│   ├── base.py              # BaseTest mixin with shared test utilities
│   ├── test_generic.py      # Integration tests for product installation
│   ├── test_helpers.py      # Unit tests for helper functions
│   ├── test_pas_plugin.py   # Tests for PAS plugin
│   ├── test_security.py     # Security-related tests
│   ├── test_robot.py        # Robot Framework test suite runner
│   └── robot_test.txt       # Robot Framework acceptance tests
```

## Test Structure

**Suite Organization:**

Test classes inherit from `unittest.TestCase` and mix in `BaseTest` for shared utilities.

```python
class TestIPWhitelisting(unittest.TestCase, BaseTest):
    """Test class for IP whitelisting functionality."""
    
    layer = COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
    
    def test_get_ip_ranges_always_returns_networks_and_accepts_single_ip(self):
        """Test that get_ip_ranges normalizes IP addresses."""
        ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
        self.assertEqual(
            [IPv4Network('127.0.0.1'), IPv4Network('192.168.0.0/16')],
            ranges)
```

**Pattern - Three-layer test architecture:**

1. **Unit tests** - Test individual helper functions with direct calls:
   ```python
   # From test_helpers.py
   def test_get_ip_ranges_always_returns_networks_and_accepts_single_ip(self):
       ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
       self.assertEqual([IPv4Network('127.0.0.1'), ...], ranges)
   ```

2. **Integration tests** - Test with Plone layer setup/teardown:
   ```python
   # From test_generic.py
   def setUp(self):
       self.app = self.layer['app']
       self.portal = self.layer['portal']
       self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
       self.portal_url = api.portal.get().absolute_url()
       self._install()  # Install product
   
   def test_product_is_installed(self):
       """Validate that product GS profile has been run."""
       pid = 'collective.googleauthenticator'
       installed = [p['id'] for p in self.qi_tool.listInstalledProducts()]
       self.assertTrue(pid in installed)
   ```

3. **Functional/Browser tests** - Test UI interactions:
   ```python
   # From test_generic.py
   def test_control_panel_view(self):
       browser = self._get_browser()
       self._login_browser(browser, SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
       browser.open('{0}/@@google-authenticator-settings'.format(self.portal_url))
       self.assertEqual(browser.headers.get('status'), '200 Ok')
   ```

**Patterns:**

- **Setup pattern** - `setUp()` method initializes layer fixtures and calls `_install()` from BaseTest:
  ```python
  def setUp(self):
      self.app = self.layer['app']
      self.portal = self.layer['portal']
      self._install()  # From BaseTest mixin
  ```

- **Teardown pattern** - Handled automatically by Plone testing layer; no explicit tearDown() needed in most tests

- **Assertion pattern** - Standard unittest assertions:
  ```python
  self.assertEqual(expected, actual)
  self.assertTrue(condition)
  self.assertFalse(condition)
  self.assertIn(item, container)
  ```

## Mocking

**Framework:** No explicit mocking library (unittest mock not used in Python 2.7 code)

**Approach:** Uses Plone test fixtures instead of mocks

**Patterns:**

- **Fixture-based testing** - Plone provides fixtures via testing layer:
  ```python
  from plone.app.testing import SITE_OWNER_NAME, SITE_OWNER_PASSWORD, TEST_USER_NAME, TEST_USER_PASSWORD
  
  browser._login_browser(browser, SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
  ```

- **Browser object** - Simulates HTTP client without actual HTTP:
  ```python
  from plone.testing.z2 import Browser
  
  browser = Browser(self.app)
  browser.open('{0}/login_form'.format(self.portal.absolute_url()))
  browser.getControl(name='__ac_name').value = SITE_OWNER_NAME
  browser.getControl(name='submit').click()
  ```

- **No third-party mocks** - Tests use actual Plone objects with test layer isolation

**What to Mock:**
- Not typically mocked; integration tests use real Plone instances within layer isolation
- If mocking needed, would use `unittest.mock` (Python 3.3+) but codebase targets Python 2.7

**What NOT to Mock:**
- Plone portal object
- User management (use real test users from fixtures)
- Form handling (use Browser object for real interaction)
- Database/persistence (handled by layer sandbox)

## Fixtures and Factories

**Test Data:**

Fixtures provided by `plone.app.testing` and custom `BaseTest` mixin:

```python
# From base.py - BaseTest mixin
class BaseTest(object):
    def _install(self):
        """Install the package using browser-based quick installer."""
        browser = Browser(self.app)
        browser.open('{0}/login_form'.format(self.portal.absolute_url()))
        browser.getControl(name='__ac_name').value = SITE_OWNER_NAME
        browser.getControl(name='__ac_password').value = SITE_OWNER_PASSWORD
        browser.getControl(name='submit').click()
        # ... install via UI

    def _get_browser(self):
        """Get a new Browser instance for testing."""
        browser = Browser(self.app)
        browser.handleErrors = False
        return browser

    def _login_browser(self, browser, user, passwd):
        """Log in via browser form."""
        browser.open(self.portal_url + '/login_form')
        browser.getControl(name='__ac_name').value = user
        browser.getControl(name='__ac_password').value = passwd
        browser.getControl(name='submit').click()
```

**Test Constants:**
```python
# Provided by plone.app.testing
SITE_OWNER_NAME = 'admin'
SITE_OWNER_PASSWORD = 'admin'
TEST_USER_NAME = 'test_user_1_'
TEST_USER_PASSWORD = 'secret'
```

**Location:**
- `tests/base.py` - Shared BaseTest mixin for all test classes
- `testing.py` - Testing layer fixtures and configuration (separate file)

## Coverage

**Requirements:** No enforced target; coverage tracking enabled

**Configuration:**
- `.coveragerc` includes `src/collective/googleauthenticator/*`
- Coverage report generated excluding Robot tests:
  ```bash
  bin/createcoverage --output-dir=htmlcov -t "--layer=!Robot"
  ```

**View Coverage:**
```bash
bin/createcoverage --output-dir=htmlcov -t "--layer=!Robot"
# Generated report: htmlcov/index.html
```

## Test Types

**Unit Tests:**
- Location: `test_helpers.py`
- Scope: Test individual helper functions in isolation
- Approach: Direct function calls with known inputs
- Example:
  ```python
  class TestIPWhitelisting(unittest.TestCase, BaseTest):
      layer = COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
      
      def test_get_ip_ranges_always_returns_networks_and_accepts_single_ip(self):
          ranges = get_ip_ranges(['127.0.0.1', '192.168.0.0/16'])
          self.assertEqual([IPv4Network('127.0.0.1'), ...], ranges)
  ```

**Integration Tests:**
- Location: `test_generic.py`, `test_pas_plugin.py`, `test_security.py`
- Scope: Test with Plone environment, product installation, database
- Approach: Use `COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` layer
- Setup: Install product, get portal/quickinstaller tools
- Example:
  ```python
  class TestGeneric(unittest.TestCase, BaseTest):
      layer = COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
      
      def setUp(self):
          self.app = self.layer['app']
          self.portal = self.layer['portal']
          self._install()
      
      def test_product_is_installed(self):
          installed = [p['id'] for p in self.qi_tool.listInstalledProducts()]
          self.assertTrue('collective.googleauthenticator' in installed)
  ```

**Functional/Browser Tests:**
- Location: `test_generic.py` (methods with `_view` suffix)
- Scope: Test HTTP endpoints and form interactions
- Approach: Use Browser object to simulate user interactions
- Layer: `COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` (no Z2 server)
- Example:
  ```python
  def test_control_panel_view(self):
      browser = self._get_browser()
      self._login_browser(browser, SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
      browser.open('{0}/@@google-authenticator-settings'.format(self.portal_url))
      self.assertEqual(browser.headers.get('status'), '200 Ok')
  ```

**Robot Framework Tests:**
- Location: `robot_test.txt` (Robot Framework syntax)
- Framework: Selenium-based, requires browser automation
- Layer: `COLLECTIVE_GOOGLEAUTHENTICATOR_ROBOT_TESTING` (with Z2ZSERVER_FIXTURE)
- Scope: End-to-end acceptance testing
- Example:
  ```robot
  *** Settings ***
  Resource  plone/app/robotframework/selenium.robot
  Library  Remote  ${PLONE_URL}/RobotRemote
  Test Setup  Open test browser
  Test Teardown  Close all browsers
  
  *** Test Cases ***
  Plone is installed
      Go to  ${PLONE_URL}
      Page should contain  Powered by Plone
  ```
- Excluded from standard test run: `bin/test` excludes layer=!Robot

## Testing Layers

**Three testing contexts provided:**

1. **COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING**
   - Base: `COLLECTIVE_GOOGLEAUTHENTICATOR_FIXTURE`
   - Scope: Plone instance with package installed, no HTTP server
   - Use for: Unit and integration tests
   - Files: `test_helpers.py`, `test_generic.py`, `test_pas_plugin.py`

2. **COLLECTIVE_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING**
   - Base: Above + `z2.ZSERVER_FIXTURE`
   - Scope: Full HTTP server with Plone
   - Use for: Browser tests that need HTTP
   - No examples in current test suite

3. **COLLECTIVE_GOOGLEAUTHENTICATOR_ROBOT_TESTING**
   - Base: Above + `REMOTE_LIBRARY_BUNDLE_FIXTURE`
   - Scope: Selenium automation, full browser simulation
   - Use for: Robot Framework acceptance tests
   - Files: `test_robot.py` (runner), `robot_test.txt` (tests)

## Common Patterns

**Async Testing:**
- Not applicable (Plone/Python 2.7 is synchronous)

**Error Testing:**
```python
# Test validation failures
def test_validate_token_failure(self):
    """Test that invalid token is rejected."""
    # Direct function testing
    result = validate_token('000000', user=test_user)
    self.assertFalse(result)
```

**Browser Interaction Pattern:**
```python
# Test form submission
def test_token_view(self):
    browser = self._get_browser()
    self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
    browser.open('{0}/@@google-authenticator-token'.format(self.portal_url))
    self.assertEqual(browser.headers.get('status'), '200 Ok')
```

**Skipped/Incomplete Tests:**
- Some tests commented out: `test_disable_view` in `test_generic.py`
- Incomplete test: `test_` in `test_security.py` (empty body)

## Best Practices Observed

1. **Descriptive test names** - Methods clearly state what is tested: `test_get_ip_ranges_always_returns_networks_and_accepts_single_ip`

2. **Shared utilities via BaseTest** - Common operations (_install, _get_browser, _login_browser) in base class

3. **Layer-based test isolation** - Each test class declares its layer, ensuring proper setup/teardown

4. **Separation of concerns** - Helper tests, plugin tests, and security tests in separate files

5. **Browser error handling disabled** - `browser.handleErrors = False` in test browser for debugging

---

*Testing analysis: 2026-07-28*
