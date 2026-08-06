# Phase 1: Rename and Fail-Closed - Pattern Map

**Mapped:** 2026-07-28
**Files analyzed:** 4 genuinely-new/rewritten artefacts + 5 new test methods (moved files: see note)
**Analogs found:** 9 / 9

## Scope note on the moved files

~50 tracked files are renamed by `git mv src/collective src/imio` plus a dotted-name edit. They need
no pattern map: each moved file **is** its own analog, and `01-RESEARCH.md` §"Rename Surface
Inventory" (§A–§F) already enumerates every site at file:line precision. **Planner: reference
RESEARCH.md for those; do not re-derive.** This document covers only the artefacts where the
executor must copy a convention from somewhere else.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/imio/__init__.py` | config (namespace pkg) | n/a | `/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py` (byte-copy); in-repo `src/collective/__init__.py` | exact |
| `src/imio/googleauthenticator/testing.py` | test fixture / layer | n/a | itself (`src/collective/googleauthenticator/testing.py`) — rename class + 4 constants + 1 string | exact |
| `tests/test_pas_plugin.py` (+2 methods) | test | request-response (PAS auth path) | `test_pas_plugin.py:13-30` `TestPas` | exact |
| `tests/test_generic.py` (+3 methods) | test | request-response (browser) | `test_generic.py:33-38` `test_control_panel_view` | exact |
| `MANIFEST.in` | config (packaging) | file-I/O | none in repo — verified replacement in RESEARCH.md:944-957 | supplied verbatim |
| `Makefile` purge target (D-20) | build tooling | file-I/O | `Makefile:57-82` existing `.PHONY` + `## help` targets | role-match |
| `locales/fr/…po`, `locales/en/…po` | i18n data | file-I/O | `locales/nl/LC_MESSAGES/*.po` (generated, not hand-written — use `rebuild_i18n.sh`) | exact |

## Project skills

`.claude/skills/` does **not exist** in this repo. No skill-imposed test-placement rules apply; the
conventions below are the repo's own.

---

## Pattern Assignments

### `src/imio/__init__.py` (new file, namespace declaration)

**Analog:** `/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py` — 2 lines, byte-copy:

```python
# -*- coding: utf-8 -*-
__import__('pkg_resources').declare_namespace(__name__)
```

**In-repo comparison:** `src/collective/__init__.py` is the same `declare_namespace` line but
**without the coding cookie**. Copy the `imio.helpers` version *including* the cookie so the two
`imio.*` eggs on a shared `sys.path` are byte-identical (RESEARCH Pitfall 3: mixed declaration
styles inside one namespace make whichever `imio/__init__.py` is found first win, silently hiding
the other subpackage).

**Note:** `git mv src/collective src/imio` moves the old `src/collective/__init__.py` into place as
`src/imio/__init__.py`. It must then be *replaced* with the two lines above, not left as-is.

---

### `src/imio/googleauthenticator/testing.py` (test layer — rename, blocks all other tests)

**Analog:** itself. Current definitions verbatim (`testing.py:12-45`), so the executor renames all
six sites consistently:

```python
class CollectivegoogleauthenticatorLayer(PloneSandboxLayer):          # -> ImiogoogleauthenticatorLayer

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load ZCML
        import collective.googleauthenticator                          # -> imio.googleauthenticator
        xmlconfig.file(
            'configure.zcml',
            collective.googleauthenticator,                            # -> imio.googleauthenticator
            context=configurationContext
        )

        # Install products that use an old-style initialize() function
        z2.installProduct(app, 'collective.googleauthenticator')       # -> 'imio.googleauthenticator'

#    def tearDownZope(self, app):
#        z2.uninstallProduct(app, 'collective.googleauthenticator')    # commented; rename anyway


COLLECTIVE_GOOGLEAUTHENTICATOR_FIXTURE = CollectivegoogleauthenticatorLayer()
COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING = IntegrationTesting(
    bases=(COLLECTIVE_GOOGLEAUTHENTICATOR_FIXTURE,),
    name="CollectivegoogleauthenticatorLayer:Integration"
)
COLLECTIVE_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(COLLECTIVE_GOOGLEAUTHENTICATOR_FIXTURE, z2.ZSERVER_FIXTURE),
    name="CollectivegoogleauthenticatorLayer:Functional"
)
COLLECTIVE_GOOGLEAUTHENTICATOR_ROBOT_TESTING = FunctionalTesting(
    bases=(COLLECTIVE_GOOGLEAUTHENTICATOR_FIXTURE, REMOTE_LIBRARY_BUNDLE_FIXTURE, z2.ZSERVER_FIXTURE),
    name="CollectivegoogleauthenticatorLayer:Robot"
)
```

**Rename map (4 constants + 1 class + 3 `name=` strings):**

| Old | New |
|-----|-----|
| `CollectivegoogleauthenticatorLayer` | `ImiogoogleauthenticatorLayer` |
| `COLLECTIVE_GOOGLEAUTHENTICATOR_FIXTURE` | `IMIO_GOOGLEAUTHENTICATOR_FIXTURE` |
| `COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` | `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` |
| `COLLECTIVE_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` | `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` |
| `COLLECTIVE_GOOGLEAUTHENTICATOR_ROBOT_TESTING` | `IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING` |
| `name="Collectivegoogleauthenticator…:{Integration,Functional,Robot}"` | `name="Imiogoogleauthenticator…:…"` |

**Consumers to update in the same commit** (else `ImportError` at collection):
`tests/test_generic.py:8-9`, `tests/test_pas_plugin.py:8-9`, `tests/test_security.py:8-9`,
`tests/test_helpers.py:3-4`, `tests/test_robot.py`.

---

### `tests/test_pas_plugin.py` — 2 new methods

**Analog:** the existing `TestPas` class in the same file (`test_pas_plugin.py:1-30`). This is the
only test class that already reaches `acl_users`, which both new tests need:

```python
from Products.CMFCore.utils import getToolByName
import unittest2 as unittest
from plone import api
from collective.googleauthenticator.setuphandlers import PAS_ID
from collective.googleauthenticator.testing import \
    COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from collective.googleauthenticator.tests.base import BaseTest


class TestPas(unittest.TestCase, BaseTest):

    layer = COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self.pas = getToolByName(self.portal, 'acl_users')
        self.portal_url = api.portal.get().absolute_url()
        self._install()

    def test_plugin_is_installed(self):
        installed = self.pas.objectIds()
        self.assertIn(PAS_ID, installed)
```

**Conventions this analog fixes (copy all of them):**
- `unittest2 as unittest`, class inherits `(unittest.TestCase, BaseTest)` — the mixin, second base.
- `layer = <FIXTURE>_INTEGRATION_TESTING` as a class attribute. **Every** test in this package uses
  the *integration* layer, including the ones driving a `z2.Browser`. Do not add a functional layer
  (that isolation debt is Phase 8 / QUAL-05).
- `setUp` boilerplate: `self.app`/`self.portal` off `self.layer[...]`, tools via
  `getToolByName`, `self.portal_url` via `api.portal.get().absolute_url()`, then `self._install()`
  — the `_install()` call is **required**: `base.py:16-17` documents that `applyProfile` does not
  apply the GS profile correctly in this layer, so the add-on is installed through the
  QuickInstaller *via a testbrowser*.
- `self._install()` hardcodes the product id at `base.py:25-26`
  (`"collective.googleauthenticator" in products_list.options`) — **rename that string** or every
  test silently runs against an uninstalled add-on.

**New test bodies:** use RESEARCH.md:998-1049 verbatim (`test_plugin_is_registered_for_authentication`,
`test_plugin_exception_is_not_swallowed`). Two points the analog does not show:
- `self.layer['request']` is the request handle (`base.py` never uses it; the layer provides it).
- Patch `pas_plugin.is_whitelisted_client`, **not** `helpers.is_whitelisted_client` —
  `pas_plugin.py` uses `from ...helpers import is_whitelisted_client`, so the helpers-module
  attribute is not consulted. Restore in a `finally`.

The new class may live beside `TestPas` (its own `TestFailClosed`, per RESEARCH) or as two methods
on `TestPas`; the `setUp` is identical either way.

---

### `tests/test_generic.py` — 3 new methods

**Analog:** `TestGeneric` in the same file. Two distinct patterns to copy.

**(a) Browser-driven view assertion** (`test_generic.py:33-38`) — the shape for
`test_control_panel_is_translated_nl`:

```python
    def test_control_panel_view(self):
        browser = self._get_browser()
        self._login_browser(browser, SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
        browser.open('{0}/@@google-authenticator-settings'.format(self.portal_url))

        self.assertEqual(browser.headers.get('status'), '200 Ok', 'HTTP response was not 200 Ok')
```

Helpers from `tests/base.py:30-38`:

```python
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

For the Dutch assertion, append `?set_language=nl` to the same URL and assert on
`browser.contents`. **Concrete target string** (from
`locales/nl/LC_MESSAGES/collective.googleauthenticator.po`, msgid at `browser/controlpanel.py:28`):

| msgid | Dutch msgstr |
|-------|--------------|
| `Google Authenticator settings` | `Google Authenticator instellingen` |

Prefer this msgid: it is the control-panel form label, its Dutch differs from its English (so the
assertion actually discriminates), and it is **not** one of the three msgids D-18 rewrites, so
D-19's fuzzy sweep will not invalidate the test.

**(b) Tool-inspection assertion** (`test_generic.py:24-31`) — the shape for
`test_resources_are_registered`, using `self.qi_tool` set up in `setUp`:

```python
    def test_product_is_installed(self):
        pid = 'collective.googleauthenticator'
        installed = [p['id'] for p in self.qi_tool.listInstalledProducts()]
        self.assertTrue(pid in installed,
            u'package appears not to have been installed')
```

Same shape, `portal_javascripts` / `portal_css` via `getToolByName` +
`getResourceIds()`. The two ids to assert, read from the profiles today, are
`++resource++collective.googleauthenticator/main.js`
(`profiles/default/jsregistry.xml:23`) and `++resource++collective.googleauthenticator/main.css`
(`profiles/default/cssregistry.xml:7`) — both become `++resource++imio.googleauthenticator/…`.

**Three files must agree or the assertion fails** (RENAME-05's hidden half):
- `browser/configure.zcml:10` — `<browser:resourceDirectory name="collective.googleauthenticator" …>`
  is what *defines* the `++resource++` prefix.
- `profiles/default/jsregistry.xml:23,27` — note there is a **second** js id,
  `++resource++collective.googleauthenticator/plone_ecmascript/popupforms.js`.
- `profiles/default/cssregistry.xml:7`.
- Adjacent, same trap: `profiles/default/skins.xml:4` —
  `directory="collective.googleauthenticator:skins/googleauthenticator_custom"`, consumed by
  `cmf:registerDirectory`; the skin layer name `googleauthenticator_custom` stays.

**(c) `test_imio_is_a_pkg_resources_namespace`** — no in-repo analog (no test in this package
inspects `pkg_resources`). Use RESEARCH.md:924-936 verbatim. It attaches to `TestGeneric` and needs
none of the `setUp` state, but keeping it on the existing class avoids a second layer setup.

---

### `MANIFEST.in`

No analog needed — RESEARCH.md:944-957 contains a replacement **measured** with
`distutils.filelist.FileList` (+5 files / −1). Use it as given. Current file for the diff:

```
include CHANGES.txt
include CONTRIBUTORS.txt           <- file does not exist, drop
include README.rst
include TODOS.rst
recursive-include src *.zcml, *.pot, ...  <- commas are literal; every pattern here is dead but *.sh
recursive-include src/collective/googleauthenticator/locales/nl *   <- 9 stale paths follow
...
```

---

### `Makefile` purge target (D-20)

**Analog:** the existing targets at `Makefile:57-82`. Convention: `.PHONY:` declaration +
`target: deps  ## help text` so it appears in `make help`. Body is the three removals from
RESEARCH: `.pyc` under the old namespace, `src/collective.googleauthenticator.egg-info`,
`var/filestorage/Data.fs` + `var/blobstorage`. Note `git clean -xdf src/` covers the first two for
*this* checkout (Commit 1); the target exists for other developers and for the residual risk D-21
accepts.

---

### `locales/fr/…` and `locales/en/…` (new)

**Do not hand-author the PO headers.** Analog and tool in one: `rebuild_i18n.sh` already implements
`i18ndude rebuild-pot` + per-language `sync`. Update its `I18NDOMAIN` (D-15) and run it; hand-written
`Plural-Forms`/charset headers are the failure mode, and a PO syntax error costs the whole language
with a single `logger.warn` (RESEARCH Pitfall 1, consequence 2).

---

## Shared Patterns

### Test module import block
**Source:** `tests/test_generic.py:1-10` (identical in `test_security.py:1-10`)
**Apply to:** every test file touched
```python
from Products.CMFCore.utils import getToolByName
import unittest2 as unittest
from plone.testing.z2 import Browser
from plone.app.testing import quickInstallProduct
from plone.app.testing import SITE_OWNER_NAME, SITE_OWNER_PASSWORD, TEST_USER_NAME, TEST_USER_PASSWORD
from plone import api

from collective.googleauthenticator.testing import \
    COLLECTIVE_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from collective.googleauthenticator.tests.base import BaseTest
```
Multi-name `from … import a, b, c` and the unused `Browser`/`quickInstallProduct` imports violate
`.isort.cfg` (`force_single_line`) and flake8 F401 — they are part of the 318 pre-existing findings.
**Preserve the existing style; do not tidy.** Lint is Phase 8 (QUAL-06), and `bin/code-analysis` is
explicitly not a gate here (commits use `--no-verify`).

### Dotted-name rename inside test files
**Apply to:** all five test modules + `base.py`
Three classes of occurrence, all in test files: (1) `from collective.googleauthenticator…` imports,
(2) the `COLLECTIVE_GOOGLEAUTHENTICATOR_*` layer constants, (3) **literal product-id strings** —
`base.py:25-26` and `test_generic.py:28`. Class (3) is the one a mechanical import-rewrite misses.

### Logger naming
**Source:** `logging.getLogger("collective.googleauthenticator")` / `getLogger(__file__)`
**Apply to:** every module that declares one — the dotted-name form moves with the rename.

### `MessageFactory` / i18n domain
**Source:** `i18n_domain="collective.googleauthenticator"` (`browser/configure.zcml:5`) and
`MessageFactory('collective.googleauthenticator')` in 11 modules.
**Apply to:** all of them — but the domain that actually takes effect is the `locales/**` **filename**
(RESEARCH Pitfall 1). Renaming the factory without `git mv`-ing the `.pot`/`.po` is a silent
total translation loss, which is exactly what `test_control_panel_is_translated_nl` catches.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `test_imio_is_a_pkg_resources_namespace` | test | n/a | No existing test inspects `pkg_resources`; use RESEARCH.md:924-936 |
| `MANIFEST.in` replacement | config | file-I/O | Nothing in-repo to copy; RESEARCH.md:944-957 is measured and verified |
| `CHANGES.rst` format | docs | n/a | External authority: `/srv/src/server.dmsmail/src/imio.dms.mail/CHANGES.rst` (excerpt at RESEARCH.md:1079-1093) |
| `locales/fr`, `locales/en` | i18n | file-I/O | Generate with `rebuild_i18n.sh`; no hand-authored analog |

## Metadata

**Analog search scope:** `src/collective/googleauthenticator/` (all), `src/collective/__init__.py`,
`tests/**`, `profiles/default/**`, `MANIFEST.in`, `Makefile`,
`/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py`
**Files read:** 14
**Pattern extraction date:** 2026-07-28
