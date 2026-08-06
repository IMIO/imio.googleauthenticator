# Phase 8: Coverage Instrument and Test Layers - Pattern Map

**Mapped:** 2026-08-05
**Files analyzed:** ~20 (config edits, one test-infra class, one deleted helper + 21 call sites, 14 test files' `setUp`, ~4 new test targets, 1 style-sweep sample)
**Analogs found:** all — this phase edits existing files; every "analog" is precedent inside the same file family, not a cross-codebase match.

## File Classification

Almost nothing here is a new file. Classification is by **edit type**, not new-file role, per the
phase's own framing.

| Changed File | Edit Type | Data Flow | Closest Precedent | Match Quality |
|---|---|---|---|---|
| `.coveragerc` | config | batch (coverage measurement) | none needed — see Code Examples in RESEARCH.md | n/a |
| `base.cfg` / `test-4.3.cfg` | config | batch (buildout parts/pins) | existing commented `[coverage]`/`[test-coverage]` sections already in `base.cfg` | exact |
| `.github/workflows/package-test.yml` | config | request-response (CI) | existing single `test_command` line | exact |
| `src/imio/googleauthenticator/testing.py` | test-infra (add method) | event-driven (layer setup hook) | `PloneSandboxLayer.setUpPloneSite` in `plone.app.testing` (installed egg) | role-match (framework hook, not in-repo) |
| `src/imio/googleauthenticator/tests/base.py` (`_install` deletion) | test-infra (delete) | file/browser I/O | `_get_browser()` / `_login_browser()` in the same file (survive) | exact (same file, same class) |
| 12 files' `_install()` call sites (21 total) | test (edit `setUp`) | CRUD (fixture setup) | `tests/test_generic.py:43-48` `setUp` | exact |
| `tests/test_generic.py::test_product_is_installed` | test (rewrite) | request-response (assertion) | `tests/test_setuphandlers.py:212`-area PAS-plugin-registration assertion (already in repo) | exact |
| New coverage tests for `browser/disable_two_factor_authentication.py` | test (new method) | request-response | `tests/test_controlpanel.py::test_render_appends_the_extra_links` (view instantiated directly, `update()`/method called, assertions on effect) | role-match |
| New coverage tests for `browser/disable_two_factor_authentication_for_all_users.py` | test (new method) | request-response | `tests/test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken` (drives `@@google-authenticator-enable-for-all-users` view's `.index()` directly, asserts `IStatusMessage` types) | exact — same view family, same call shape |
| New coverage tests for `browser/controlpanel.py:125-158` (save handler) | test (new method) | request-response | `tests/test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken` part 3 (drives `GoogleAuthenticatorSettingsEditForm`, `extractData`/`handleSave` shape) | exact |
| New coverage tests for `browser/forms/reset_bar_code.py` | test (new method) | request-response | `tests/test_reset_bar_code.py` (existing file already covers this form; extend, don't duplicate) | exact |
| `browser/controlpanel.py` `E251` fixes | style | n/a | `browser/forms/reset_bar_code.py` lines 35-45 (`TextLine(title=_(...), ...)`, no spaces around `=`) — already-correct sibling in the same `browser/forms/` family | exact (target shape) |
| `browser/forms/request_bar_code_reset.py` `E251` fixes | style | n/a | same as above | exact |
| isort sweep (26 `.py` files) | style | n/a | `helpers.py`, `pas_plugin.py`, `subscribers.py`, `adapter.py`, `testing.py` — already isort-clean, confirmed live with `bin/isort -df` | exact |
| `CLAUDE.md` / `.planning/codebase/TESTING.md` | docs | n/a | n/a | n/a |

## Pattern Assignments

### `src/imio/googleauthenticator/testing.py` — add `setUpPloneSite`, drop ZSERVER_FIXTURE (QUAL-05, D-10, D-15)

**Current shape (full file, 45 lines, already read in full):**
```python
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import applyProfile
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.testing import z2

from zope.configuration import xmlconfig


class ImiogoogleauthenticatorLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load ZCML
        import imio.googleauthenticator
        xmlconfig.file(
            'configure.zcml',
            imio.googleauthenticator,
            context=configurationContext
        )

        # Install products that use an old-style initialize() function
        z2.installProduct(app, 'imio.googleauthenticator')

#    def tearDownZope(self, app):
#        # Uninstall products installed above
#        z2.uninstallProduct(app, 'imio.googleauthenticator')


IMIO_GOOGLEAUTHENTICATOR_FIXTURE = ImiogoogleauthenticatorLayer()
IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,),
    name="ImiogoogleauthenticatorLayer:Integration"
)
IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE, z2.ZSERVER_FIXTURE),
    name="ImiogoogleauthenticatorLayer:Functional"
)
IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE, REMOTE_LIBRARY_BUNDLE_FIXTURE, z2.ZSERVER_FIXTURE),
    name="ImiogoogleauthenticatorLayer:Robot"
)
```

**New method to add**, following the exact shape RESEARCH.md's Pattern 1 verified against the
installed `plone.app.testing` egg (`applyProfile` is already imported at line 2, unused today —
one of the 13 `F401` findings this phase fixes by using it):
```python
    def setUpPloneSite(self, portal):
        applyProfile(portal, 'imio.googleauthenticator:default')
```
Place it directly after `setUpZope`, same indentation, same class — mirrors how `setUpZope`
already sits as the one lifecycle method on this class.

**Edit to `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`** — drop `z2.ZSERVER_FIXTURE` from `bases`
(D-10 edits in place, does not add a third layer):
```python
IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,),
    name="ImiogoogleauthenticatorLayer:Functional"
)
```
`IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING` keeps its own `z2.ZSERVER_FIXTURE` — untouched.

All 14 test files' `layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` class attribute changes
to `layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` — mechanical, one line per file, same
import line changes from `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` to
`IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`. `IntegrationTesting` becomes unused in this package
after the sweep (verify no remaining reference before D-06's isort pass, since an unused import of
the old name would itself be a new `F401`).

---

### `tests/base.py` — delete `_install()`, keep `_get_browser()`/`_login_browser()` (D-15)

**Full current file (30 lines, already read):**
```python
from plone.testing.z2 import Browser
from plone.app.testing import SITE_OWNER_NAME, SITE_OWNER_PASSWORD

class BaseTest(object):

    def _install(self):
        browser = Browser(self.app)
        # Login as site owner
        browser.open('{0}/login_form'.format(self.portal.absolute_url()))
        browser.getControl(name='__ac_name').value = SITE_OWNER_NAME
        browser.getControl(name='__ac_password').value = SITE_OWNER_PASSWORD
        browser.getControl(name='submit').click()
        # We must uninstall and install the package, it seems generic setup profile
        # is not applied coorectly by plone.app.testing in this testing layer.
        browser.open('{0}/prefs_install_products_form'.format(self.portal.absolute_url()))
        form = browser.getForm(index=1)
        self.assertEqual(
            form.action, '{0}/portal_quickinstaller/installProducts'.format(self.portal.absolute_url()),
            u'Install form not found')
        products_list = form.getControl(name='products:list')
        if "imio.googleauthenticator" in products_list.options:
            products_list.value = (u"imio.googleauthenticator",)
            form.getControl(label='Activate').click()
        browser.open(self.portal.absolute_url() + '/logout')

    def _get_browser(self):
        browser = Browser(self.app)
        browser.handleErrors = False
        return browser

    def _login_browser(self, browser, user, passwd):
        browser.open(self.portal_url + '/login_form')
        browser.getControl(name='__ac_name').value = user
        browser.getControl(name='__ac_password').value = passwd
        browser.getControl(name='submit').click()
```

**Post-edit shape:** delete the entire `_install` method (lines 6-28), keep `_get_browser` and
`_login_browser` verbatim. The module-level comment admitting "generic setup profile is not
applied correctly by plone.app.testing in this testing layer" goes with it — `setUpPloneSite` is
exactly the fix for that admitted bug.

**All 21 call sites** follow the same `setUp()` shape seen in `test_generic.py:43-48`:
```python
    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')   # DELETE (D-16)
        self.portal_url = api.portal.get().absolute_url()
        self._install()                                                      # DELETE (D-15)
```
becomes:
```python
    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = api.portal.get().absolute_url()
```
The 12 files carrying one or both of `self.qi_tool = getToolByName(...)` / `self._install()`
(confirmed by grep, 21 total `_install()` sites): `test_adapter.py`, `test_challenge.py`,
`test_controlpanel.py`, `test_generic.py`, `test_helpers.py`, `test_pas_plugin.py`,
`test_request_bar_code_reset.py`, `test_reset_bar_code.py`, `test_security.py`,
`test_setuphandlers.py`, `test_token.py`, `test_user_setup.py`. Some files call `_install()` more
than once (setUp plus a re-install inside an individual test method, e.g. after an uninstall
profile run) — grep each file individually rather than assuming exactly one occurrence per file.

---

### `tests/test_generic.py::test_product_is_installed` → QUAL-07 rewrite

**Current (lines 39-57, full class header + method, already read):**
```python
class TestGeneric(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self.portal_url = api.portal.get().absolute_url()
        self._install()

    def test_product_is_installed(self):
        """ Validate that our products GS profile has been run and the product
            installed
        """
        pid = 'imio.googleauthenticator'
        installed = [p['id'] for p in self.qi_tool.listInstalledProducts()]
        self.assertTrue(pid in installed,
            u'package appears not to have been installed')
```

**Replacement — the three assertions RESEARCH.md's Pattern 4 specifies**, following this file's own
docstring convention (reference the requirement ID, explain what a regression would look like) seen
throughout the same file (e.g. `test_control_panel_has_lockout_fields`, `test_manifest_ships_...`):
```python
    def test_product_is_installed(self):
        """QUAL-07: applyProfile() never touches portal_quickinstaller (verified
        against the installed plone.app.testing source), so installedness is
        asserted through what the package's own install path actually
        guarantees instead: PAS plugin registration, the
        IGoogleAuthenticatorSettings registry records, and the browser layer.
        """
        ids = [x[0] for x in self.pas.plugins.listPlugins(IAuthenticationPlugin)]
        self.assertIn('google_auth', ids)

        registry = getUtility(IRegistry)
        registry.forInterface(IGoogleAuthenticatorSettings)  # raises KeyError if any record missing

        self.assertIn(IGoogleAuthenticatorLayer, registered_layers())
```
Needs `self.pas = getToolByName(self.portal, 'acl_users')` (or equivalent) in `setUp` if not
already present — check `test_setuphandlers.py`'s existing PAS-registration assertion (around line
212, already in repo, cited in RESEARCH.md Pattern 4) for the exact `self.pas` construction this
file should copy, since `test_generic.py` today has no `self.pas` attribute.

New imports needed at the top of `test_generic.py`, following this file's existing style of
one-symbol-per-line-ish imports already partially present (isort sweep will reformat regardless):
```python
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from plone.registry.interfaces import IRegistry
from plone.browserlayer.utils import registered_layers
from imio.googleauthenticator.interfaces import IGoogleAuthenticatorLayer
from zope.component import getUtility
```
`IGoogleAuthenticatorSettings` is already imported (line 14).

Also delete the commented-out `test_disable_view` block at lines 78-82 of the same file — dead
code the D-11 tests below make redundant.

---

### D-11 coverage tests — `disable_two_factor_authentication.py` (40% → target higher)

**Target source** (`browser/disable_two_factor_authentication.py`, full file, 41 lines, already
read): a `BrowserView` with one method, `disable()`, three branches — anonymous 401 guard, the
member-property mutation, the status message + redirect.

**Analog to copy call shape from** — `tests/test_controlpanel.py::test_render_appends_the_extra_links`
(instantiates the view class directly against `self.portal`/`self.request`, calls the method under
test, asserts on side effects):
```python
# Source: tests/test_controlpanel.py:43-49 (existing, this repo)
def test_render_appends_the_extra_links(self):
    setRoles(self.portal, TEST_USER_ID, ['Manager'])
    form = GoogleAuthenticatorSettingsEditForm(self.portal, self.request)
    form.update()
    ...
```
New test file/class should follow the same instantiate-directly pattern:
```python
view = DisableTwoFactorAuthentication(self.portal, self.request)
view.disable()
```
For the anonymous-401 branch, `api.user.is_anonymous()` needs to return `True` — check how
`test_helpers.py` or `test_pas_plugin.py` fakes anonymous state elsewhere in the suite before
inventing a new mechanism (grep `is_anonymous` across `tests/`).

For the status-message assertion, copy the `IStatusMessage(self.request).show()` /
`m.type` idiom already used in `test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken`
(lines 493-500, already read above):
```python
IStatusMessage(self.request).show()  # drain prior messages
...
types = [m.type for m in IStatusMessage(self.request).show()]
self.assertIn('info', types)
```

---

### D-11 coverage tests — `disable_two_factor_authentication_for_all_users.py` (56% → target higher)

**Target source** (full file, 33 lines, already read): `index()` calls
`api.user.get_users()` then `disable_two_factor_authentication_for_users(users)`, sets a status
message, redirects.

**Exact analog already in repo** — `test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken`
part 2 drives the sibling `@@google-authenticator-enable-for-all-users` view the identical way:
```python
# Source: tests/test_helpers.py:492-500 (existing, this repo)
view = self.portal.restrictedTraverse('@@google-authenticator-enable-for-all-users')
view.request = self.request
view.index()
types = [m.type for m in IStatusMessage(self.request).show()]
self.assertIn('error', types)
self.assertNotIn('info', types)
```
The new test for `@@google-authenticator-disable-for-all-users` copies this shape verbatim,
swapping the traversal name and asserting the happy path (`'info'` in types, since
`disable_two_factor_authentication_for_users` has no encryption-key failure mode the enable path
has — confirm by reading `helpers.py`'s `disable_two_factor_authentication_for_users` before
assuming no error branch exists).

---

### D-11 coverage tests — `browser/controlpanel.py` lines 125-158 (save handler, 68% → target higher)

**Target source** (already read in full above, lines 112-158): `handleSave` branches on
`globally_enabled is True` / `is False` / neither, with a `try/except ValueError` around the
enable-for-all-users call.

**Exact analog already in repo** — same test method, part 3 (lines 502+ in `test_helpers.py`,
partially read):
```python
form = GoogleAuthenticatorSettingsEditForm(
    self.portal, self.request)
# ... exercises extractData/handleSave via form.groups[0].widgets
```
Read the rest of that method (lines 508-540ish) before writing new tests — it already exercises
the `globally_enabled is True` branch with the encryption-key failure. D-11's new tests should add
coverage for the **currently-untested** branches: `globally_enabled is False` (the
`#disable_two_factor_authentication_for_users(users)` commented-out line at 152 — note this is
dead code today; a `False` test only exercises the `logger.debug('Disabled')` line, not an actual
disable, unless this dead line is what MFA-14/07-UAT.md flags — do not un-comment it, that is a
behaviour change, out of scope per CONTEXT.md), and the `globally_enabled is None`
(neither-branch) path that skips both blocks and goes straight to `applyChanges`.

---

### D-11 coverage tests — `browser/forms/reset_bar_code.py` (76% → target higher)

**Existing test file already covers this form**: `tests/test_reset_bar_code.py`. D-11 extends this
file's existing test class with new methods for uncovered branches — read the file's current
content and existing test method list before adding, so new tests target what's actually missing
(`updateFields`'s `user_data_validation_result.result` False branch, the bar-code-token mismatch
branch, and/or the bare `except Exception` arm at line 166-168) rather than duplicating existing
coverage. Follow this repo's "one test method per requirement, grouped by concern" convention (D-11
cross-reference, WR-03 precedent) — one new method per uncovered branch, not one giant test.

---

### Style sweep — `E251` target shape (D-05, D-18)

**Non-conforming** (`browser/controlpanel.py:29-35`, already read):
```python
ska_secret_key = TextLine(
    title = _("Secret Key"),
    description = _("Enter your secret key for the site here. ..."),
    required = False,
    default = u'',
    )
```

**Conforming sibling in the same `browser/forms/` family** (`browser/forms/reset_bar_code.py:35-39`,
already read — no spaces around `=` in keyword args):
```python
qr_code = TextLine(
    title=_(u'1. Scan this QR code with the Google Authenticator app'),
    description=u'This description is replaced with the QR code.',
    required=False
)
```
The fix for all 100 `E251` findings (54 in `controlpanel.py`, 28 in
`browser/forms/request_bar_code_reset.py`, 12 in `userdataschema.py`, 4 in `__init__.py`, 2 in
`browser/disable_two_factor_authentication.py`) is exactly this: remove the space on both sides of
`=` inside call arguments. `reset_bar_code.py` is the in-repo reference for the target shape —
already conforms, no `E251` findings there.

**isort-clean import block to copy the target shape from** (`helpers.py` top, confirmed clean via
`bin/isort -df`) — one import per line, alphabetically sorted within each `from X import Y` group,
per `.isort.cfg`'s `force_single_line` + `force_alphabetical_sort`. Use `bin/isort -rc -y src/` per
RESEARCH.md Pitfall 3 rather than hand-editing 26 files — this file's current state is the proof the
mechanical tool produces the right shape, no hand-verification of every file needed beyond the
finding-count-by-code check (D-18).

## Shared Patterns

### Fixture setup after the layer change
**Source:** `src/imio/googleauthenticator/testing.py` (new `setUpPloneSite`)
**Apply to:** all 14 test files' `setUp()` — removes `self.qi_tool = ...` and `self._install()`,
nothing else changes in `setUp()`.

### Status-message assertion idiom
**Source:** `tests/test_helpers.py:493-500` (`IStatusMessage(self.request).show()` drain +
`[m.type for m in ...]`)
**Apply to:** all new D-11 tests against `disable_two_factor_authentication.py`,
`disable_two_factor_authentication_for_all_users.py`, and `controlpanel.py`'s save handler — every
one of these views reports outcomes via `IStatusMessage`, never a return value.

### Direct view/form instantiation over `restrictedTraverse` where both exist in-repo
**Source:** `tests/test_controlpanel.py:48` (`GoogleAuthenticatorSettingsEditForm(self.portal, self.request)`)
vs. `tests/test_helpers.py:494` (`self.portal.restrictedTraverse('@@...')`)
**Apply to:** either is acceptable per existing precedent — `test_helpers.py` traverses for the
`@@google-authenticator-enable-for-all-users` view (no constructor args beyond context/request
needed at call time because `.index()` is called directly after), `test_controlpanel.py`
instantiates the form class directly. For the two `disable_*` views (plain `BrowserView`
subclasses with a two-arg `__init__(context, request)`), either style works; prefer
`restrictedTraverse` for the `@@google-authenticator-disable-for-all-users` view specifically since
it is the direct sibling of the already-tested enable view and keeping the same call shape makes
the two tests easy to diff against each other.

### Non-vacuity / mutation-check discipline
**Source:** every phase 1-7 plan (per CONTEXT.md "Established Patterns"); this phase's own
`test_no_restrictedTraverse_left_in_browser_code` in `test_generic.py:423-472` is a concrete
in-repo example of the "assert the search itself isn't vacuous" idiom.
**Apply to:** QUAL-02's `set -e` proof (a real red build then reverted) and every D-11 new test
(prove it fails before the fix, or — since these are coverage-only additions with no source
change — prove the assertion is not vacuously true, e.g. by temporarily breaking the branch under
test and confirming red, then restoring).

## No Analog Found

None — every changed file has an in-repo precedent for its edit type. The one genuinely
"new" piece of logic (`setUpPloneSite`) is a framework hook with its exact reference implementation
verified directly against the installed `plone.app.testing` egg source (RESEARCH.md Pattern 1),
not against another in-repo file, since this repo has never had this method before.

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/` (all `browser/`, `tests/`, root modules),
`.coveragerc`, `base.cfg`, `test-4.3.cfg`, `.github/workflows/package-test.yml`
**Files scanned:** `testing.py`, `tests/base.py`, `tests/test_generic.py`,
`tests/test_controlpanel.py`, `tests/test_helpers.py` (targeted section),
`browser/controlpanel.py`, `browser/disable_two_factor_authentication.py`,
`browser/disable_two_factor_authentication_for_all_users.py`,
`browser/forms/reset_bar_code.py`, `browser/forms/request_bar_code_reset.py`, plus a live
`bin/isort -df` sweep across all non-test `.py` files to find clean-import exemplars
**Pattern extraction date:** 2026-08-05
