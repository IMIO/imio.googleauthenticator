# Phase 7: Coexistence with imio.dms.mail - Pattern Map

**Mapped:** 2026-08-04
**Files analyzed:** 15 (deletions, conversions, one-line fixes, uninstall profile, 6 test files)
**Analogs found:** 12 / 15 (3 are pure deletions with no in-repo analog — the "pattern" is stock Plone behaviour, listed under No Analog Found)

This phase is mostly subtraction. Where a conventional PATTERNS.md would point at
another file to imitate, most entries here point instead at (a) the stock Plone
4.3.20 asset being restored by deletion, and (b) every in-repo reference that must
be removed in the same commit so nothing dangles.

## File Classification

| New/Modified/Deleted File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `skins/googleauthenticator_custom/login_form.cpt` (+`.metadata`) | template (deleted) | request-response | Stock `Products.CMFPlone-4.3.20.../skins/plone_login/login_form.cpt` | restoration, no in-repo analog |
| `skins/googleauthenticator_custom/static/popupforms.js` | static asset (deleted) | event-driven (client) | Stock `Products.CMFPlone-4.3.20.../skins/plone_ecmascript/popupforms.js` | restoration, no in-repo analog |
| `profiles/default/skins.xml` | config (deleted) | CRUD (GenericSetup import) | n/a — deleted outright | deletion |
| `configure.zcml` (`cmf:registerDirectory`) | config (modified) | CRUD | n/a — one line removed | deletion |
| `profiles/default/jsregistry.xml` (`popupforms.js` entries + `remove="True"`) | config (modified) | CRUD | n/a — two lines removed | deletion |
| `browser/controlpanel.py` (`GoogleAuthenticatorSettingsEditForm.render`) | controller/form | request-response | Same file, same method (self-analog — convert in place) | exact |
| `browser/templates/control_panel_extra.pt` | template (new) | request-response | `browser/forms/templates/request_bar_code_reset_email.pt` (already a `.pt`, once created) — or, for the `ViewPageTemplateFile` wiring, RESEARCH.md's own quoted example | role-match |
| `browser/forms/request_bar_code_reset.py` (`RequestBarCodeResetForm.handleSubmit`) | controller/form | event-driven (mail send) | Same file, same method (self-analog) | exact |
| `browser/forms/templates/request_bar_code_reset_email.pt` | template (relocated) | event-driven | `skins/googleauthenticator_custom/request_bar_code_reset_email.pt` (content unchanged, only moved) | exact |
| `browser/forms/token.py` (`TokenForm.render`, new method) | controller/form | request-response | No `render()` override precedent in this package — see below | no analog, first-of-kind |
| `browser/forms/token.py` (`handleSubmit`, BUG-01 fix) | controller/form | request-response | Stock `login_form.cpt`'s `isURLInPortal(next)` idiom (not an in-repo analog) | pattern from stock template |
| `adapter.py` (`CameFromAdapter.getCameFrom`, BUG-06 fix) | service/adapter | transform | Same file, same method (self-analog: `extract_next_url_from_referer`'s own `quote_url` kwarg) | exact |
| `profiles/uninstall/jsregistry.xml` (new) | config | CRUD | `profiles/default/jsregistry.xml` (mirror, `remove="True"` only) | exact |
| `profiles/uninstall/cssregistry.xml` (new) | config | CRUD | `profiles/default/cssregistry.xml` (mirror, `remove="True"` only) | exact |
| `profiles/uninstall/skins.xml` (deleted) | config | CRUD | `profiles/default/skins.xml` (its own install-time counterpart, also deleted) | exact |
| `tests/test_token.py` (COEX-01, COEX-09, BUG-01 tests) | test | request-response | Existing tests in same file (see below) | exact |
| `tests/test_setuphandlers.py` (COEX-02/03/05/06 tests) | test | CRUD/config | `test_every_javascript_registration_pins_its_position` (minidom pattern) | exact |
| `tests/test_pas_plugin.py` (COEX-04 source-grep test) | test | transform | `test_no_second_factor_state_written_from_the_plugin`-style source-grep (lines 379-393) | exact |
| `tests/test_adapter.py` (new `TestCameFromAdapter` class, BUG-06) | test | transform | `TestEnhancedUserDataPanelAdapter` (class shape) | role-match |
| `tests/test_request_bar_code_reset.py` (COEX-04 email-path extension) | test | event-driven | Existing `setUp`/`_submit_reset_request` in same file | exact |

## Pattern Assignments

### Deletions — restoring stock Plone behaviour

**`skins/` directory, `profiles/default/skins.xml`, `configure.zcml`'s `cmf:registerDirectory`**

There is no in-repo file to copy a pattern *from* — the correct end state is
"as if this package never shipped a skin layer." Point the executor at:

- Stock asset being restored: `/home/cadam/buildout-cache/eggs/Products.CMFPlone-4.3.20-py2.7.egg/Products/CMFPlone/skins/plone_login/login_form.cpt` (unmodified, once the override is gone Zope's acquisition/skin lookup falls through to this).
- Stock asset being restored: `/home/cadam/buildout-cache/eggs/Products.CMFPlone-4.3.20-py2.7.egg/Products/CMFPlone/skins/plone_ecmascript/popupforms.js`.

**Every in-repo reference that must be removed/edited in the same commit so nothing dangles:**

1. `src/imio/googleauthenticator/skins/googleauthenticator_custom/` — delete the whole directory (`login_form.cpt`, `login_form.cpt.metadata`, `popupforms.js` under `static/` if present, `control_panel_extra.html`, `request_bar_code_reset_email.pt` — **the last two are live templates, not overrides; they must be converted, not just deleted, see next section**).
2. `src/imio/googleauthenticator/profiles/default/skins.xml` — delete outright (current content, for reference):
   ```xml
   <?xml version="1.0"?>
   <object name="portal_skins">
    <object name="googleauthenticator_custom"
       meta_type="Filesystem Directory View"
       directory="imio.googleauthenticator:skins/googleauthenticator_custom"/>
    <skin-path name="*">
     <layer name="googleauthenticator_custom"
        insert-after="custom"/>
    </skin-path>
   </object>
   ```
3. `src/imio/googleauthenticator/configure.zcml` — delete this one line:
   ```xml
   <cmf:registerDirectory name="skins" directory="skins" recursive="True" />
   ```
4. `src/imio/googleauthenticator/profiles/default/jsregistry.xml` — delete both:
   ```xml
   <javascript id="popupforms.js" remove="True" enabled="False" />
   ...
   <javascript cacheable="True" compression="none" cookable="True"
               enabled="True" expression="" insert-bottom="True"
               id="++resource++imio.googleauthenticator/plone_ecmascript/popupforms.js" inline="False"/>
   ```
   Leave the `main.js` `<javascript ...>` entry and its long explanatory comment untouched — `test_every_javascript_registration_pins_its_position` and `test_registered_javascript_loads_after_jquery` (Pitfall 4 in RESEARCH.md) both explicitly `continue` past `remove="True"` nodes and only assert about `main.js`'s own position, so they need no edit.
5. `MANIFEST.in` — delete the stale `recursive-include src/imio/googleauthenticator/skins *` line (RESEARCH.md Runtime State Inventory).
6. `profiles/uninstall/skins.xml` — delete (current content, for reference):
   ```xml
   <?xml version="1.0"?>
   <object name="portal_skins">
       <object name="googleauthenticator_custom"
           meta_type="Filesystem Directory View"
           remove="True"/>
       <skin-path name="*">
       <layer name="googleauthenticator_custom"
           remove="True"/>
       </skin-path>
   </object>
   ```
   There is nothing left for an uninstall step to un-register once `profiles/default/skins.xml` is gone.

---

### `browser/controlpanel.py` — `restrictedTraverse` → `ViewPageTemplateFile`

**Analog:** the file's own current `render()` method (self-conversion — the shape to replace, verbatim, is quoted here so the diff is obvious):

**Current (lines 99-109):**
```python
def render(self, *args, **kwargs):
    res = super(GoogleAuthenticatorSettingsEditForm, self).render(*args, **kwargs)
    additional_template = self.context.restrictedTraverse('control_panel_extra')
    additional = additional_template(
        enable_url = '{0}/{1}'.format(self.context.absolute_url(), '@@google-authenticator-enable-for-all-users'),
        enable_text = _("Enable two-step verification for all users"),
        disable_url = '{0}/{1}'.format(self.context.absolute_url(), '@@google-authenticator-disable-for-all-users'),
        disable_text = _("Disable two-step verification for all users"),
        charset = 'utf-8',
        )
    return res + additional
```

**Target shape (per RESEARCH.md's verified `ViewPageTemplateFile` example, Products.Five namespace contract `here == context`):**
```python
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

class GoogleAuthenticatorSettingsEditForm(AutoExtensibleForm, form.EditForm):
    additional_template = ViewPageTemplateFile('templates/control_panel_extra.pt')
    ...
    def render(self, *args, **kwargs):
        res = super(GoogleAuthenticatorSettingsEditForm, self).render(*args, **kwargs)
        additional = self.additional_template(
            enable_url='{0}/{1}'.format(self.context.absolute_url(), '@@google-authenticator-enable-for-all-users'),
            enable_text=_("Enable two-step verification for all users"),
            disable_url='{0}/{1}'.format(self.context.absolute_url(), '@@google-authenticator-disable-for-all-users'),
            disable_text=_("Disable two-step verification for all users"),
            charset='utf-8',
        )
        return res + additional
```
Only the lookup mechanism changes; the template body (`skins/googleauthenticator_custom/control_panel_extra.html`, 274 bytes) moves unedited to `browser/templates/control_panel_extra.pt` (standardize on `.pt` per RESEARCH.md Open Question 2).

**Imports pattern (existing, lines 1-17 of `controlpanel.py`)** — keep isort's `force_single_line`/`force_alphabetical_sort` ordering; the new import (`Products.Five.browser.pagetemplatefile.ViewPageTemplateFile`) sorts alphabetically among the existing `Products.statusmessages...` line.

---

### `browser/forms/request_bar_code_reset.py` — same conversion, second call site

**Analog:** the file's own current call site (self-conversion):

**Current (line 90):**
```python
mail_text_template = self.context.restrictedTraverse('request_bar_code_reset_email')
mail_text = mail_text_template(
    member = user,
    bar_code_reset_url = signed_url,
    charset = 'utf-8'
    )
mail_text = mail_text.format(bar_code_reset_url=signed_url)
```

**Target shape:**
```python
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

class RequestBarCodeResetForm(form.SchemaForm):
    mail_text_template = ViewPageTemplateFile('templates/request_bar_code_reset_email.pt')
    ...
    def handleSubmit(self, action):
        ...
        mail_text = self.mail_text_template(
            member=user, bar_code_reset_url=signed_url, charset='utf-8')
        mail_text = mail_text.format(bar_code_reset_url=signed_url)
```
Template body (`skins/googleauthenticator_custom/request_bar_code_reset_email.pt`, 910 bytes) moves unedited to `browser/forms/templates/request_bar_code_reset_email.pt`.

**Test-side note (COEX-04 trap, RESEARCH.md Correction 4):** `tests/test_request_bar_code_reset.py::setUp` (lines 24-38) currently does:
```python
self._install()
# The email body is a skin template, so it is only traversable once
# the portal's skin is bound to this request.
self.portal.setupCurrentSkin(self.layer['request'])
```
After the conversion, `setupCurrentSkin(...)` is dead code (harmless to leave per RESEARCH.md, cheap to remove) — `ViewPageTemplateFile` needs no skin binding. This test is the safety net that turns red if `skins/` is deleted before this file is converted; land both changes in the same commit.

---

### `browser/forms/token.py` — `TokenForm.render()` override (COEX-01)

**No existing `render()` override precedent anywhere in `browser/forms/`** — grepped `forms/token.py`, `forms/request_bar_code_reset.py`, `forms/user_setup.py`, `forms/reset_bar_code.py`: none override `render()`. This is first-of-kind for the package. Point the executor at the base method being overridden instead:

- `z3c.form.form.BaseForm.render()` (installed: `z3c.form==3.2.11`, `z3c/form/form.py`) — "a pure string-returning method; no update/widget-processing logic runs inside `render()` itself" (RESEARCH.md Correction 1, verified).
- The exact stock selector this must satisfy: `Products.CMFPlone-4.3.20.../skins/plone_ecmascript/popupforms.js:76-98`, `formselector: 'form#login_form'`.

**Target shape (verified-safe per RESEARCH.md):**
```python
def render(self):
    html = super(TokenForm, self).render()
    # plone.z3cform 0.8.1's titlelessform macro never emits an id
    # attribute on <form>; Plone's own (untouched) popupforms.js
    # binds its ajax overlay via formselector: 'form#login_form',
    # which must match THIS form -- the second, ajax-loaded fragment
    # -- not just the stock login form Plone already renders correctly.
    return html.replace('<form ', '<form id="login_form" ', 1)
```
Place this method alongside the existing `action()`/`handleSubmit()`/`updateFields()` methods on `TokenForm` (lines 46-176 of the current file).

**Existing method-placement convention to imitate (imports/structure, lines 1-31):**
```python
from zope.i18nmessageid import MessageFactory
from zope.schema import TextLine

from z3c.form import button, field

from plone import api
from plone.directives import form
from plone.z3cform.layout import wrap_form
```
No new imports are needed for the `render()` override itself.

---

### `browser/forms/token.py` — BUG-01 fix (`handleSubmit`, current lines 136-137)

**Current:**
```python
request_data = extract_request_data(self.request)
context_url = self.context.absolute_url()
redirect_url = request_data.get('next_url', context_url)
self.request.response.redirect(redirect_url)
```

**Analog:** stock Plone's own `login_form.cpt` idiom (not in this repo — quoted from RESEARCH.md, which read it from the installed egg): `test(next is not None and isURLInPortal(next), next, None)`.

**Target shape:**
```python
from Products.CMFCore.utils import getToolByName
...
redirect_url = request_data.get('next_url', context_url)
portal_url_tool = getToolByName(self.context, 'portal_url')
if not portal_url_tool.isURLInPortal(redirect_url):
    redirect_url = context_url
self.request.response.redirect(redirect_url)
```
`getToolByName` is already imported this way elsewhere in the package (e.g. `browser/forms/request_bar_code_reset.py:16`, `from Products.CMFCore.utils import getToolByName`) — reuse that exact import line for `isort` consistency.

---

### `adapter.py` — BUG-06 fix (`CameFromAdapter.getCameFrom`)

**Analog:** the same function's own already-built, already-unused kwarg — no new code needed, only passing an existing parameter:

**Current (lines 107-113):**
```python
def getCameFrom(self):
    """
    Extracts the ``came_from`` value from the referrer (uses global request).

    :return string:
    """
    return extract_next_url_from_referer(self.request)
```

**Target:**
```python
def getCameFrom(self):
    """
    Extracts the ``came_from`` value from the referrer (uses global request).

    :return string:
    """
    return extract_next_url_from_referer(self.request, quote_url=True)
```

`extract_next_url_from_referer`'s `quote_url` parameter already exists at `helpers.py:914-934`:
```python
def extract_next_url_from_referer(request, quote_url=False):
    ...
    url = request_data.get('came_from', '')

    if quote_url:
        return quote(url)

    return url
```
No change needed in `helpers.py` itself — the FIXME this closes is attached to a function that already has the fix built in and unused (RESEARCH.md).

---

### `profiles/uninstall/jsregistry.xml` / `cssregistry.xml` (new, COEX-06)

**Analog:** `profiles/default/jsregistry.xml` / `profiles/default/cssregistry.xml` — mirror the install-time entries with `remove="True"`, for `main.js`/`main.css` ONLY (not `popupforms.js`, which after COEX-03 this package no longer registers at all).

**Install-time entry being mirrored (`profiles/default/jsregistry.xml`, current):**
```xml
<javascript cacheable="True" compression="none" cookable="True"
            enabled="True" expression="" insert-bottom="True"
            id="++resource++imio.googleauthenticator/main.js" inline="False"/>
```
**New `profiles/uninstall/jsregistry.xml`:**
```xml
<?xml version="1.0"?>
<object name="portal_javascripts">
    <javascript id="++resource++imio.googleauthenticator/main.js" remove="True"/>
</object>
```

**Install-time entry being mirrored (`profiles/default/cssregistry.xml`, current):**
```xml
<stylesheet title=""
            id="++resource++imio.googleauthenticator/main.css"
            media="screen" rel="stylesheet" rendering="import"
            cacheable="True" compression="safe" cookable="True"
            enabled="1" expression=""/>
```
**New `profiles/uninstall/cssregistry.xml`:**
```xml
<?xml version="1.0"?>
<object name="portal_css">
    <stylesheet id="++resource++imio.googleauthenticator/main.css" remove="True"/>
</object>
```

**Registration to leave untouched (`configure.zcml`, already present — no edit needed):**
```xml
<genericsetup:registerProfile
    name="uninstall"
    title="Google Authenticator Plone Action Uninstall"
    directory="profiles/uninstall"
    description="Uninstall Postlogin Action"
    provides="Products.GenericSetup.interfaces.EXTENSION"
    />
```

---

## Test Assignments (Validation Architecture § 10 test methods)

All 10 named test methods, file + analog:

| Test method | File | Analog to quote |
|---|---|---|
| `test_token_form_carries_login_form_id` (COEX-01) | `tests/test_token.py` | Existing browser-content assertion pattern in same file (grep for `browser.contents` usage in `test_token.py`; if none exists, use `plone.testing.z2.Browser` setup identical to `tests/test_request_bar_code_reset.py`'s testbrowser calls in `BaseTest._install()`) |
| `test_login_form_override_is_deleted` (COEX-02) | `tests/test_setuphandlers.py` | Filesystem-fact pattern — `os.path.exists(os.path.join(package_dir, 'skins', 'googleauthenticator_custom', 'login_form.cpt'))` is False; same `os.path.dirname(imio.googleauthenticator.__file__)` idiom as `test_pas_plugin.py:379` |
| `test_popupforms_js_is_not_vendored` (COEX-03) | `tests/test_setuphandlers.py` | `minidom.parse(JSREGISTRY_XML)` pattern, lines 310-311, plus a filesystem-fact check that `skins/.../popupforms.js` (or `browser/static/popupforms.js`) no longer exists |
| `test_control_panel_view` / `test_reset_email_survives_a_non_ascii_sender_name` (COEX-04, existing, extend not rewrite) | `tests/test_generic.py` / `tests/test_request_bar_code_reset.py` | Already exist and already exercise both templates — no new test class, just confirm they stay green post-conversion |
| `test_no_restrictedTraverse_left_in_browser_code` (COEX-04, new) | `tests/test_pas_plugin.py`-style source-grep, but belongs in `tests/test_generic.py` or a new small test since it spans `browser/` not `pas_plugin.py` | Source-grep pattern at `test_pas_plugin.py:379-393`/411-414 (`open(...)`, `.read()`, `assertNotIn`) |
| `test_skin_layer_is_removed` (COEX-05) | `tests/test_setuphandlers.py` | Same filesystem-fact + ZCML source-grep pattern as COEX-02/03 (grep `configure.zcml` source for absence of `registerDirectory`) |
| `test_uninstall_restores_resource_registries` (COEX-06) | `tests/test_setuphandlers.py` | `applyProfile`/reapply pattern at `test_reapply_profile_keeps_plugin_first_and_unique` (lines 197-227) — same `applyProfile(self.portal, 'imio.googleauthenticator:default')` idiom, extended with `applyProfile(self.portal, 'imio.googleauthenticator:uninstall')` and assertions on `portal_javascripts`/`portal_css` resource ids via `getToolByName` |
| `test_popupforms_js_survives_either_install_order` (COEX-07, synthetic) | `tests/test_setuphandlers.py` (new) | Construct the exact colliding `<javascript id="popupforms.js" insert-after="form_tabbing.js" />` fragment (quoted verbatim in RESEARCH.md from `/srv/src/imio.dms.mail/imio/dms/mail/profiles/default/jsregistry.xml:87`) and apply via `portal_javascripts` before/after this package's own profile import — same `getToolByName(self.portal, 'portal_javascripts')` tool access as `test_registered_javascript_loads_after_jquery` (line 345) |
| `test_login_link_reaches_token_form` (COEX-09, markup/redirect chain only — JS overlay itself is `checkpoint:human-verify`) | `tests/test_token.py` | `plone.testing.z2.Browser`, `Browser.getLink(...).click()` — same testbrowser idiom used throughout `tests/test_request_bar_code_reset.py`/`tests/test_reset_bar_code.py` |
| `test_next_url_is_validated_against_the_portal` (BUG-01) | `tests/test_token.py` | Existing `handleSubmit`-driving tests in same file (form instantiated directly, `extractData`/button handler invoked) |
| `test_get_came_from_quotes_the_value` (BUG-06) | `tests/test_adapter.py`, **new `TestCameFromAdapter` class** | `TestEnhancedUserDataPanelAdapter` (lines 30-38 for `setUp`/layer wiring) is the class-shape analog — no `TestCameFromAdapter` class exists yet, only `TestEnhancedUserDataPanelAdapter` |

## Shared Patterns

### `getToolByName` for CMF tool access
**Source:** `browser/forms/request_bar_code_reset.py:16` (`from Products.CMFCore.utils import getToolByName`), also `tests/test_setuphandlers.py`/`test_pas_plugin.py` throughout.
**Apply to:** `token.py`'s BUG-01 fix (`portal_url` tool), any new test needing `portal_javascripts`/`portal_css`.

### Source-grep test pattern (proving something is *absent* from a file)
**Source:** `tests/test_pas_plugin.py:379-393` (open/read every relevant module) + `:411-414` (`assertNotIn` loop with a descriptive failure message naming the requirement ID).
**Apply to:** COEX-02/03/04/05's filesystem/ZCML/source-absence tests.

### `minidom` XML-assertion pattern
**Source:** `tests/test_setuphandlers.py:3` (`from xml.dom import minidom`), `:310-330` (`document.getElementsByTagName('javascript')`, loop with a `POSITION_ATTRIBUTES`/`remove` skip, `assertEqual([], unpinned, ...)`).
**Apply to:** COEX-03's `test_popupforms_js_is_not_vendored`, COEX-07's synthetic collision test.

### `applyProfile` install/reapply pattern
**Source:** `tests/test_setuphandlers.py:213-227` (`test_reapply_profile_keeps_plugin_first_and_unique`).
**Apply to:** COEX-06's uninstall-then-reinstall test.

### `Products.Five.browser.pagetemplatefile.ViewPageTemplateFile`
**Source:** RESEARCH.md's verified example, cross-checked against `Zope2-2.13.30-py2.7-linux-x86_64.egg/Products/Five/browser/pagetemplatefile.py` (namespace: `here == context`, `request`, no template-body edits needed).
**Apply to:** `controlpanel.py`, `request_bar_code_reset.py`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `skins/googleauthenticator_custom/login_form.cpt` (+`.metadata`) | template | request-response | Pure deletion; the "pattern" is the stock Plone asset it shadows, not an in-repo file |
| `skins/googleauthenticator_custom/static/popupforms.js` (or wherever the vendored copy lives) | static asset | event-driven (client) | Same — pure deletion, stock asset takes over |
| `browser/forms/token.py`'s `render()` override | controller/form | request-response | First `render()` override precedent in this package's `browser/forms/`; analog is the z3c.form base method itself (`z3c.form.form.BaseForm.render()`), not an in-repo file |

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/` (`browser/`, `browser/forms/`, `adapter.py`, `helpers.py`, `profiles/`, `configure.zcml`, `browser/configure.zcml`, `tests/`); `/home/cadam/buildout-cache/eggs/Products.CMFPlone-4.3.20-py2.7.egg/` for stock assets; `/srv/src/imio.dms.mail/` for the collision fixture source.
**Files scanned:** ~20 (all files named in RESEARCH.md's file inventory plus the 6 test files named in Validation Architecture)
**Pattern extraction date:** 2026-08-04
