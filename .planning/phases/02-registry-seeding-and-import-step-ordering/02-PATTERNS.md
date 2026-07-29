# Phase 2: Registry Seeding and Import-Step Ordering - Pattern Map

**Mapped:** 2026-07-29
**Files analyzed:** 3 modified source files + 1 modified test file (or new test module)
**Analogs found:** 4 / 4 — this phase edits existing files in place; every "analog" is the file's
own current content, since there is no comparable sibling elsewhere in the tree for a
GenericSetup import-step/registry-seeding fix.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/imio/googleauthenticator/setuphandlers.py` | config/install handler | event-driven (GS install) | itself, `_setup_secret_key`/`setupVarious` (deleted/shrunk) | exact |
| `src/imio/googleauthenticator/configure.zcml` | config (ZCML) | n/a | itself, the `<genericsetup:importStep>` block | exact |
| `src/imio/googleauthenticator/helpers.py` | utility | request-response (signing) | itself, `get_ska_secret_key` / `get_browser_hash` | exact |
| `src/imio/googleauthenticator/tests/test_generic.py` (or new `test_setuphandlers.py`) | test | request-response / CRUD (registry) | `test_generic.py::test_product_is_installed` + `tests/base.py` | exact |

## Pattern Assignments

### `src/imio/googleauthenticator/setuphandlers.py` (config/install handler, event-driven)

**Analog:** itself, current lines 1-63 (read in full above).

**Current state to delete (D-04):**
```python
from uuid import uuid4
...
def _setup_secret_key(portal):
    """
    Generate secret key
    """
    portal.portal_setup.runImportStepFromProfile(
        'profile-imio.googleauthenticator:default',
        'plone.app.registry'
        )

    settings = get_app_settings()
    if not settings.ska_secret_key:
        settings.ska_secret_key = unicode(uuid4())
```
and its one call site inside `setupVarious`:
```python
    portal = context.getSite()

    _setup_secret_key(portal)

    pas = portal.acl_users
    _add_plugin(pas)
```

**Target shape** — `setupVarious` keeps only the marker guard and `_add_plugin`:
```python
def setupVarious(context):
    """
    @param context: Products.GenericSetup.context.DirectoryImportContext instance
    """

    # We check from our GenericSetup context whether we are running
    # add-on installation for your product or any other proudct
    if context.readDataFile('imio.googleauthenticator.marker.txt') is None:
        # Not your add-on
        return

    portal = context.getSite()

    pas = portal.acl_users
    _add_plugin(pas)
```
Drop the now-unused `from uuid import uuid4` and `from imio.googleauthenticator.helpers import
get_app_settings` imports at the top of the file (both become dead once `_setup_secret_key` is
gone) — `.isort.cfg` `force_single_line`/`force_alphabetical_sort` conventions apply to whatever
import block remains; `_add_plugin` still needs its existing
`from imio.googleauthenticator.pas_plugin import GoogleAuthenticatorPlugin` and
`from zope.i18nmessageid import MessageFactory` lines untouched.

**Error handling:** none added or removed here — `setupVarious` has never wrapped
`_add_plugin`/registry access in try/except, and D-07 explicitly wants `KeyError` to propagate
uncaught later in `get_ska_secret_key`/`get_app_settings`, not here.

---

### `src/imio/googleauthenticator/configure.zcml` (ZCML config, n/a data flow)

**Analog:** itself, lines 44-49, the existing dependency-free `importStep`:
```xml
    <genericsetup:importStep
        name="imio.googleauthenticator"
        title="imio.googleauthenticator install steps"
        description=""
        handler="imio.googleauthenticator.setuphandlers.setupVarious"
        />
```

**Target shape (D-10)** — add a `<depends>` child element:
```xml
    <genericsetup:importStep
        name="imio.googleauthenticator"
        title="imio.googleauthenticator install steps"
        description=""
        handler="imio.googleauthenticator.setuphandlers.setupVarious"
        >
        <depends name="plone.app.registry"/>
    </genericsetup:importStep>
```
Note the closing-tag change (self-closing `/>` becomes `>...</genericsetup:importStep>`) — this is
the one line-shape gotcha an executor doing a text-only diff can miss. No other element in this
file uses `<depends>`, so there is no second in-repo example to cross-check against; the shape is
`plone.app.registry`'s own step declaration
(`/srv/cache/eggs/plone.app.registry-1.7.9-py2.7.egg/plone/app/registry/exportimport/configure.zcml:10-18`,
cited in CONTEXT.md canonical refs) which uses the identical `<depends name="...">` child-element
form for its own three dependencies (`componentregistry`, `toolset`, `typeinfo`).

---

### `src/imio/googleauthenticator/helpers.py` (utility, request-response)

**Analog:** itself, current `get_ska_secret_key` (lines 228-259) and `get_browser_hash`
(lines 210-225).

**`get_browser_hash` — already matches D-09.** Current code already does:
```python
def get_browser_hash(request=None):
    ...
    try:
        return sha1(request.get('HTTP_USER_AGENT')).hexdigest()
    except Exception as e:
        logger.debug(str(e))
        return ''
```
This already returns `''` from the `except` branch, not `None` — CONTEXT.md's D-09 describes it as
falling through to `None`, but that no longer matches the installed tree (likely fixed incidentally
in Phase 1's fail-closed work). **No change needed here**; the planner/executor should verify this
during implementation and treat D-09 as already satisfied rather than re-doing it, but should still
add/keep a regression test asserting `get_browser_hash` returns `''` (not `None`) on a missing/bad
`HTTP_USER_AGENT`, since `test_helpers.py` today has no test for this function at all.

**`get_ska_secret_key` — needs both D-05 (lazy mint) and D-08 (netstring join).** Current:
```python
def get_ska_secret_key(request=None, user=None, use_browser_hash=True):
    """
    Gets the `secret_key` to be used in `ska` package.
    ...
    """
    if request is None:
        request = getRequest()

    if user is None:
        user = api.user.get_current()

    settings = get_app_settings()

    ska_secret_key = settings.ska_secret_key

    user_secret = user.getProperty('two_factor_authentication_secret')

    if use_browser_hash:
        browser_hash = get_browser_hash(request=request)
    else:
        browser_hash = ''

    return "{0}{1}{2}".format(user_secret, browser_hash, ska_secret_key)
```

**Target shape** — single `if not ska_secret_key:` mint branch (D-05, randomness unchanged from the
deleted `_setup_secret_key`: `unicode(uuid4())`), plus a length-prefixed join replacing the bare
`.format()` concatenation (D-08). This requires `from uuid import uuid4` to move from
`setuphandlers.py` into `helpers.py` (it's already imported there at line 7 — reuse it, do not
re-import):
```python
    settings = get_app_settings()

    ska_secret_key = settings.ska_secret_key
    if not ska_secret_key:
        ska_secret_key = unicode(uuid4())
        settings.ska_secret_key = ska_secret_key

    user_secret = user.getProperty('two_factor_authentication_secret')

    if use_browser_hash:
        browser_hash = get_browser_hash(request=request)
    else:
        browser_hash = ''

    return u''.join(
        u'{0}:{1}'.format(len(part), part)
        for part in (user_secret, browser_hash, ska_secret_key)
    )
```
(Exact netstring formatting — `len(part):part` per component, concatenated with no separator — is
D-08's own description; the executor should pick concrete syntax matching this module's existing
generator/comprehension style, e.g. `get_ip_ranges`'s list-comprehension-with-try style at lines
517-531 for comparison, though a plain generator expression as above is idiomatic enough and
matches `get_app_settings`'s and neighboring functions' terseness.)

**Import ordering note:** `uuid4` is already imported at the top of `helpers.py` (line 7,
`from uuid import uuid4`) — used today by `generate_secret`. No new import line needed for the mint
branch.

**Four call sites affected by the D-08 derivation change** (none need edits themselves — they all
call `get_ska_secret_key`/`sign_user_data`/`validate_user_data` and are correct as long as both
sides of every signed URL use the same derivation):
- `pas_plugin.py:160` — `sign_user_data(request=request, user=user, url=...)`
- `browser/forms/token.py:87` — `validate_user_data(request=..., user=..., use_browser_hash=...)`
- `browser/forms/reset_bar_code.py:150` — `validate_user_data(request=self.request, user=...)`
- `browser/forms/request_bar_code_reset.py:66` — `get_ska_secret_key(request=self.request, user=user)`
All four are call sites, not definition sites — verify each still reads the same way after the
edit; no diff is expected in these four files.

---

### `src/imio/googleauthenticator/tests/test_generic.py` or new `test_setuphandlers.py` (test)

**Analog:** `test_generic.py::test_product_is_installed` (lines 27-34) — same layer, same
`qi_tool`/`setUp` shape:
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
        pid = 'imio.googleauthenticator'
        installed = [p['id'] for p in self.qi_tool.listInstalledProducts()]
        self.assertTrue(pid in installed,
            u'package appears not to have been installed')
```
`self._install()` (from `tests/base.py:6-28`) drives a real testbrowser through
`prefs_install_products_form` — this is how the profile actually gets applied in this layer
(`base.py:16-17` docstring: "generic setup profile is not applied correctly by plone.app.testing in
this testing layer"). **New D-03 tests can reuse this exact `setUp`/`_install()` pattern**; no new
fixture machinery is needed.

**D-03 half 1 — ordering assertion.** No existing test calls `getSortedImportSteps()`; this is new
ground, but `self.portal.portal_setup` is accessed the same way other tests reach tools
(`getToolByName(self.portal, ...)` idiom used throughout `test_generic.py` and `test_helpers.py`):
```python
    def test_import_step_runs_after_plone_app_registry(self):
        portal_setup = getToolByName(self.portal, 'portal_setup')
        steps = portal_setup.getSortedImportSteps()
        self.assertGreater(
            steps.index('imio.googleauthenticator'),
            steps.index('plone.app.registry'))
```

**D-03 half 2 — outcome assertion**, chained onto the same test or a sibling, using
`get_app_settings()` per CONTEXT.md's D-07 (propagating `KeyError` if a record is missing):
```python
    def test_registry_records_exist_after_install(self):
        from imio.googleauthenticator.helpers import get_app_settings
        settings = get_app_settings()  # raises KeyError if any record is missing
        self.assertIsNotNone(settings.ska_secret_key)
```
Import placement: module-level, alongside the file's other `from imio.googleauthenticator...`
imports (single-import-per-line, per `.isort.cfg` `force_single_line` — see `test_helpers.py:7-11`
for the convention already followed in this package's test modules), not a function-local import
as shown inline above for brevity.

**D-13 — double-apply value-preservation regression test.** No existing test calls `applyProfile`
directly (`_install()` goes through the QuickInstaller browser form instead), so this is the one
genuinely new pattern in this phase. Use `self.portal.portal_setup.applyProfile(...)` directly
(bypassing `_install()`'s browser dance, since the product is already installed by `setUp`) with a
**known** seeded value, not an assertion of mere non-emptiness:
```python
    def test_ska_secret_key_survives_reapply(self):
        from imio.googleauthenticator.helpers import get_app_settings
        settings = get_app_settings()
        settings.ska_secret_key = u'known-test-value'
        self.portal.portal_setup.applyProfile('imio.googleauthenticator:default')
        self.assertEqual(u'known-test-value', get_app_settings().ska_secret_key)
```
`IntegrationTesting` aborts its transaction per test (Phase 1 PATTERNS.md, confirmed again here),
so this does not leak `known-test-value` into sibling tests.

**BUG-04 component-separation test** — belongs in `test_helpers.py` (role/data-flow match:
request-response, secret derivation), next to the existing `TestIPWhitelisting` class or as a new
`TestSkaSecretKey` class using the same layer:
```python
    def test_ska_key_components_do_not_collide(self):
        """BUG-04 regression: '{0}{1}{2}'.format(a, b, c) let (user_secret='ab', browser_hash='',
        ska='cd') collide with (user_secret='a', browser_hash='', ska='bcd'). The netstring-style
        join must keep them distinct."""
        from imio.googleauthenticator.helpers import get_ska_secret_key
        ... # construct two fake users/settings with colliding concatenations,
            # assert get_ska_secret_key returns different strings for each
```
No existing test in this package fakes `get_app_settings`/user objects for `get_ska_secret_key`
directly; the closest structural analog for "monkeypatch `helpers.get_app_settings`, restore in
`finally`" is `test_helpers.py:46-58`
(`test_get_ip_addresses_whitelist_drops_blank_lines`), which patches `helpers.get_app_settings`
with a `FakeSettings` class and restores the original in a `finally` block — copy that shape for
whatever fake settings/user objects the collision test needs.

---

## Shared Patterns

### Monkeypatching `helpers.get_app_settings` for a fake registry value
**Source:** `test_helpers.py:46-58`
**Apply to:** the BUG-04 collision test and D-13's known-value test if `get_app_settings` needs
faking rather than driving the real registry through `IRegistry`.
```python
from imio.googleauthenticator import helpers

class FakeSettings(object):
    ip_addresses_whitelist = '127.0.0.1\n192.168.0.0/16\n'

original = helpers.get_app_settings
helpers.get_app_settings = lambda: FakeSettings()
try:
    ...
finally:
    helpers.get_app_settings = original
```

### Test module import block (single-import-per-line)
**Source:** `test_helpers.py:1-11`
**Apply to:** any new test file/class in this phase
```python
import unittest2 as unittest

from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest

from imio.googleauthenticator.helpers import extract_ip_address_from_request
from imio.googleauthenticator.helpers import get_ip_addresses_whitelist
from imio.googleauthenticator.helpers import get_ip_ranges
```
Note `test_generic.py`'s own import block (multi-name `from plone.app.testing import A, B, C, D`)
violates this and is **pre-existing debt, not a pattern to copy** — new imports in either file
should use the single-name-per-line form shown above; do not propagate the multi-name style further.

### `getToolByName` for tool access
**Source:** used throughout `test_generic.py` and this phase's new tests (`portal_quickinstaller`,
`portal_setup`, `acl_users` in Phase 1's `test_pas_plugin.py`)
**Apply to:** `portal_setup` access for `getSortedImportSteps()` and `applyProfile()`.

### `_dont_swallow_my_exceptions = True` (Phase 1, unrelated file but load-bearing here)
**Source:** PAS plugin class attribute set in Phase 1
**Apply to:** why D-07's propagating `KeyError` from `get_app_settings()` surfaces as a 500 instead
of silently falling through — no code in this phase touches this attribute, but D-03/D-07's tests
rely on it having already landed.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `<depends name="plone.app.registry"/>` ZCML shape | config | n/a | No second `<depends>` usage exists in this package's own `configure.zcml`; shape sourced from the installed `plone.app.registry` egg's own `configure.zcml` (cited in CONTEXT.md canonical refs), not from an in-repo analog |
| Netstring-style join in `get_ska_secret_key` | utility | request-response | No existing helper in this codebase does length-prefixed joining; D-08's rationale (delimiter-collision safety ahead of Phase 3's Fernet-token `user_secret`) is itself the design source, not a copied pattern |
| `applyProfile()` double-apply test | test | CRUD (registry) | No existing test calls `applyProfile` directly (`_install()` goes through the QuickInstaller browser form); D-13's test is genuinely new machinery, built from `portal_setup` tool access already used elsewhere |

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/setuphandlers.py`,
`src/imio/googleauthenticator/configure.zcml`, `src/imio/googleauthenticator/helpers.py`,
`src/imio/googleauthenticator/tests/{test_generic.py,test_helpers.py,base.py}`,
`src/imio/googleauthenticator/browser/forms/{token.py,reset_bar_code.py,request_bar_code_reset.py}`,
`src/imio/googleauthenticator/pas_plugin.py` (grep only, call sites), installed
`plone.app.registry` egg's `configure.zcml` (external reference cited by CONTEXT.md)
**Files read:** 7 (+1 grep-only for call-site confirmation)
**Pattern extraction date:** 2026-07-29
