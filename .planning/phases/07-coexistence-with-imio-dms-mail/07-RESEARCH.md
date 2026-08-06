# Phase 7: Coexistence with imio.dms.mail - Research

**Researched:** 2026-08-04
**Domain:** Plone 4.3 login overlay (jQuery Tools + `popupforms.js`), GenericSetup resource-registry (`portal_javascripts`/`portal_css`/`portal_skins`) lifecycle, z3c.form/`plone.z3cform` rendering internals, open-redirect remediation
**Confidence:** HIGH — nearly every claim below is verified either against this repo's own source or against the exact egg versions installed in this buildout (`Products.CMFPlone-4.3.20`, `z3c.form-3.2.11`, `plone.z3cform-0.8.1`, `ska-1.7.5`), not against training-data recollection of "typical" Plone behaviour.

**No `CONTEXT.md` exists for this phase** (consistent with Phases 3-6). `ROADMAP.md`'s Phase 7 section and `REQUIREMENTS.md`'s COEX/BUG entries are therefore the locked decisions; this research does not present alternatives to them, only how to implement them correctly given what the installed code and eggs actually do (several of which differ from what the roadmap assumed — see `<research_corrections>` inline below).

## Summary

This phase deletes ~350 lines of vendored Plone core code (`login_form.cpt`, `popupforms.js`, the `skins/` filesystem-directory override, and the `jsregistry.xml` `remove="True"` mutation) and replaces the login-overlay dependency with one small, targeted change to `TokenForm`. The vendored copies are not neutral dead weight: the vendored `popupforms.js`'s login-overlay binding is **already commented out** ("Temporary disabled, as doesn't work with Google Authenticator app"), and the `remove="True"` line in this package's own `jsregistry.xml` **actively collides**, right now, with a real dependency — `imio.dms.mail`'s own `profiles/default/jsregistry.xml` (found on this machine at `/srv/src/imio.dms.mail/imio/dms/mail/profiles/default/jsregistry.xml:87`) carries `<javascript id="popupforms.js" insert-after="form_tabbing.js" />`, i.e. it expects Plone's own `popupforms.js` resource to still exist so it can reposition it. `imio.googleauthenticator`'s `remove="True"` permanently deletes that resource object from `portal_javascripts`, and once deleted, `imio.dms.mail`'s bare reposition entry has nothing to reposition — this breaks **every** `prepOverlay` widget in `imio.dms.mail` (delete/rename dialogs, `imio.pm.wsclient` popups, faceted-nav widgets, etc.), regardless of which package's GenericSetup profile happens to import last. This is not hypothetical: `server.dmsmail`'s `dev.cfg` already lists `imio.googleauthenticator` as an "evaluation only" (MOD-1076) egg alongside the real `imio.dms.mail`, and this package's own `tests/test_setuphandlers.py` already documents "observed on a real `server.dmsmail` deployment, 2026-08-03" for a related jQuery-load-order bug. Coexistence is being tested for real, soon.

The second load-bearing finding changes how COEX-01 must be implemented. The roadmap states "`id = 'login_form'` on `TokenForm` as the only mechanism," implying a one-line Python class-attribute change is sufficient. It is not: `z3c.form.form.Form.id` is a `@property` used internally by z3c.form, but **neither `plone.z3cform` 0.8.1's `wrappedform.pt`/`form.pt` templates nor the shared `macros.pt` `titlelessform` macro they both delegate to ever render that property onto the `<form>` HTML tag** (verified by reading the installed egg source directly — see `<research_corrections>` below). Setting `id = 'login_form'` as a class attribute changes a Python-level property; it does not by itself put `id="login_form"` in the response body Plone's stock, untouched `popupforms.js` searches for (`formselector: 'form#login_form'`). `TokenForm` needs to actually emit that attribute, and the smallest correct fix is a `render()` override that post-processes the rendered HTML — not a template fork, which would just re-introduce the vendoring this phase exists to remove.

Third, `ska==1.7.5`'s signature only ever covers `auth_user` + `valid_until` (+ an opt-in `extra` dict this package never populates) — read directly from `ska/utils.py`'s `RequestHelper.validate_request_data` and `ska/base.py`'s `Signature.get_base`. Any other query-string key, including the overlay's injected `ajax_load`, is invisible to the signature and cannot break it. The roadmap's open decision is settled: **`ska` tolerates `ajax_load` unconditionally**, with certainty, not "should ignore it."

Fourth, BUG-01 (open redirect) and BUG-06 (`+`-escaping FIXME) are two ends of the same undefended pipe: `pas_plugin.py::send_2fa_redirect` appends `&next_url={came_from}` with **no quoting at all**, and `browser/forms/token.py::handleSubmit` reads it back and calls `self.request.response.redirect(redirect_url)` with **no on-site check at all**. Both fixes are one-line, using code that already exists in this module (`helpers.extract_next_url_from_referer`'s already-built-but-never-used `quote_url` parameter, and CMFCore's stock `portal_url.isURLInPortal`) — no new dependency, no hand-rolled URL parser.

**Primary recommendation:** Delete the vendored skin/JS/CSS-mutation trio in one commit (COEX-02/03/05 + BUG-01 per the roadmap's own same-commit grouping), fix `TokenForm`'s rendered `id` with a `render()` override (not a template fork), fix the two redirect bugs with the two one-line changes above, convert both `restrictedTraverse` skin templates to `ViewPageTemplateFile`, and write the `profiles/uninstall/` counterpart for the package's *own* two resources (`main.js`, `main.css`) — not for `popupforms.js`, which after COEX-03 this package no longer touches at all.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COEX-01 | `TokenForm` carries `id = 'login_form'` so Plone's stock overlay finds it with no vendored JavaScript | `<research_corrections>` #1 — the property alone does not reach the HTML; a `render()` override is required. Exact stock selector documented from `Products.CMFPlone-4.3.20`'s `popupforms.js`. |
| COEX-02 | The `login_form.cpt` override and its `.metadata` are deleted | File inventory below; exact line counts corrected (roadmap said 310, actual is 310 — confirmed exact) |
| COEX-03 | Vendored `popupforms.js`, its `jsregistry.xml` entries, and `remove="True"` are deleted | Confirmed real collision partner: `imio.dms.mail`'s own `jsregistry.xml`. See Summary. |
| COEX-04 | `control_panel_extra.html`/`request_bar_code_reset_email.pt` still work, converted to `ViewPageTemplateFile` | Exact call sites verified (line numbers corrected below); `ViewPageTemplateFile` namespace requirements documented from `Products.Five` source. |
| COEX-05 | Skin layer, `skins.xml`, `registerDirectory`, `skins/` gone | Exact `cmf:registerDirectory` line found in `configure.zcml`; `MANIFEST.in`/`setup.py` cross-references identified. |
| COEX-06 | Real `profiles/uninstall/` restores install-time changes | Current `profiles/uninstall/` inventory (only `skins.xml`, no `jsregistry.xml`/`cssregistry.xml`) — the actual gap is documented. |
| COEX-07 | Installs in both orders alongside `imio.dms.mail` | Concrete evidence of the real collision (not hypothetical); honest split between an automatable synthetic-collision test and a non-automatable real two-egg install (`server.dmsmail` MOD-1076 environment). |
| COEX-09 | Header "Log in" link (not direct POST) reaches token form and completes | Explains *why* `TokenForm` needs `id="login_form"` (it's the second, ajax-loaded fragment the overlay must also bind, not the first) and why a `testbrowser`-only proof is necessarily incomplete (no JS engine). |
| BUG-01 | `next_url` validated against portal URL; off-site refused | Exact current code read (`token.py`, not the stale `:112-113` the requirement text cites — current lines are 136-137); `portal_url.isURLInPortal` is the stock, un-hand-rolled fix. |
| BUG-06 | Query-string values URL-encoded on the way in | Root cause traced to `adapter.CameFromAdapter.getCameFrom()` calling `helpers.extract_next_url_from_referer(request)` with the existing `quote_url` parameter left at its default `False`. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Login-overlay binding (jQuery Tools `prepOverlay`) | Browser / Client | — | Pure client-side DOM/AJAX behaviour, entirely inside Plone's own stock `popupforms.js`; this package must stop shipping a client-side asset at all. |
| `TokenForm` HTML output (`id="login_form"`) | Frontend Server (SSR) | Browser / Client | Server renders the exact markup the client-side overlay selector requires; the two tiers must agree on one literal string (`form#login_form`) with no negotiation. |
| Signed-URL construction/validation (`ska`, `next_url`) | API / Backend | — | Pure server-side security logic (signature scope, redirect allowlist); no client involvement. |
| GenericSetup resource registries (`portal_javascripts`, `portal_css`, `portal_skins`) | Database / Storage (ZODB-backed registry tools) | Frontend Server (SSR, since it decides page `<script>`/`<link>` order) | These are ZODB-persisted registries mutated by an install/uninstall profile; the mutation is a storage-tier concern even though its effect is felt at render time. |
| Two skin templates (`control_panel_extra`, `request_bar_code_reset_email`) | Frontend Server (SSR) | — | Server-rendered fragments with no client logic; converting the lookup mechanism (`restrictedTraverse` → `ViewPageTemplateFile`) is purely a backend wiring change. |
| Two-package install-order interaction | Database / Storage (registry state) | CDN / Static (script load order is what actually breaks) | The observable symptom is a broken client asset, but the root cause and the fix are both entirely in ZODB-persisted registry state set by GenericSetup import steps. |

## Standard Stack

No new third-party package is introduced by this phase. It is a deletion-and-refactor phase: removing vendored code and adding a handful of stdlib (`urllib.quote`) and already-installed-egg (`Products.Five.browser.pagetemplatefile.ViewPageTemplateFile`, `Products.CMFCore` `portal_url` tool) calls, all already present in this buildout's dependency graph.

### Core
No additions. Everything used below is already an install-time dependency of this package or of Plone 4.3 itself (`Products.Five`, `Products.CMFCore`, `z3c.form`, `plone.z3cform`, `ska==1.7.5`).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `render()` string-post-process for `id="login_form"` | A custom `ViewPageTemplateFile` re-implementing `titlelessform`'s widget-rendering macro | Rejected: re-copies ~90 lines of Plone's own macro logic, which is exactly the vendoring this phase exists to remove. The string-replace is a 2-line diff on code this package already owns. |
| `helpers.extract_next_url_from_referer(request, quote_url=True)` at the one existing call site (`adapter.CameFromAdapter.getCameFrom`) | Quote at the `pas_plugin.py::send_2fa_redirect` call site instead | Either works; the adapter call site is smaller (the `quote_url` kwarg already exists and is unused) and fixes the FIXME at the exact function the FIXME comment is attached to. |
| `portal_url.isURLInPortal(url)` for BUG-01 | Hand-rolled `urlparse` host-matching | Rejected per project convention (`CLAUDE.md`: "no wholesale skin or resource-registry overrides… nothing custom where a stock tool exists") and because Plone's own stock `login_form.cpt` already uses exactly this idiom (`isURLInPortal(came_from)`, `isURLInPortal(next)` — see Code Examples). |

## Package Legitimacy Audit

Not applicable — this phase installs no new packages (`setup.py install_requires` is unmodified). It deletes vendored assets and adds calls to already-installed, already-vetted eggs (`Products.Five`, `Products.CMFCore`, stdlib `urllib`). No `gsd-tools query package-legitimacy check` run was needed.

## Architecture Patterns

### System Architecture Diagram — the corrected login flow

```
Browser click "Log in" link (#portal-personaltools a[href$="/login"])
        |
        v
Plone stock popupforms.js: prepOverlay({subtype:'ajax', formselector:'form#login_form', ...})
        |  (AJAX GET the link's href)
        v
Plone STOCK login_form.cpt (unmodified once COEX-02 deletes our override)
        |  renders <form id="login_form" method="post"> with came_from/next/ajax_load hidden inputs
        v
common_content_filter extracts #content fragment --> injected into jQuery Tools overlay
        |
        v
User submits credentials INSIDE the overlay (still AJAX, still same form#login_form)
        |  POST __ac_name / __ac_password / ajax_load=<timestamp> / came_from=...
        v
GoogleAuthenticatorPlugin.authenticateCredentials()  [decide-only, Phase 4 boundary]
   - wipes credentials dict, delegates password check to other IAuthenticationPlugins
   - on success: _mark_2fa_pending(request, user)   [request.other, not request.get]
        |
        v
subscribers.redirect_pending_2fa  (IPubBeforeCommit, fires because login POST returns HTTP 200)
        |
        v
pas_plugin.send_2fa_redirect(request, response)
   - sign_user_data() --> ska.sign_url(auth_user=..., secret_key=..., url='@@google-authenticator-token')
     (signature covers ONLY auth_user + valid_until -- ajax_load/next_url/came_from are OUTSIDE it)
   - appends "&next_url={came_from}"   <-- BUG-06: currently unquoted
   - response.redirect(signed_url, lock=1); response.body = ''  (empties body, Phase 4 MFA-02 fix)
        |
        v
Browser's AJAX call transparently follows the 302 (XHR does this automatically)
        |
        v
TokenForm rendered at @@google-authenticator-token
   - MUST also carry id="login_form" (COEX-01) so the SAME overlay's formselector
     can find and AJAX-bind THIS second, ajax-loaded fragment too -- this is the
     part the roadmap's phrasing under-states: the id is not for the *first*
     form (that's Plone's own, already correct), it's for the *second* one.
        |
        v
User submits token INSIDE the (still open) overlay
        |
        v
TokenForm.handleSubmit(): validate_user_data() [ska check, ajax_load/next_url IGNORED, not validated]
   -> validate_second_factor(token)
   -> on success: redirect_url = request_data.get('next_url', context_url)
      BUG-01: currently redirects with NO on-site check --> add portal_url.isURLInPortal() guard
        |
        v
Full navigation to the final destination (last redirect is same-origin by construction
once BUG-01's guard is in place, so the overlay's ajax "noform"/"redirect" handling
for this final hop is a full top-level navigation, matching Plone's own stock pattern
for a completed login)
```

### Recommended Project Structure (files touched, no new top-level dirs)
```
src/imio/googleauthenticator/
├── browser/
│   ├── configure.zcml            # (unchanged registrations; skins ZCML removed elsewhere)
│   ├── controlpanel.py           # restrictedTraverse -> ViewPageTemplateFile
│   ├── templates/                # NEW -- .pt files that replace the two skin templates
│   │   └── control_panel_extra.pt
│   └── forms/
│       ├── token.py              # id="login_form" render() override; BUG-01 guard
│       ├── request_bar_code_reset.py   # restrictedTraverse -> ViewPageTemplateFile
│       └── templates/            # NEW
│           └── request_bar_code_reset_email.pt
├── adapter.py                     # BUG-06: quote_url=True at the one call site
├── configure.zcml                 # cmf:registerDirectory line DELETED (COEX-05)
├── profiles/
│   ├── default/
│   │   ├── jsregistry.xml         # popupforms.js entries + remove="True" DELETED (COEX-03)
│   │   ├── cssregistry.xml        # unchanged (main.css only)
│   │   └── skins.xml              # DELETED (COEX-05)
│   └── uninstall/
│       ├── skins.xml              # DELETED (nothing left to un-register)
│       ├── jsregistry.xml         # NEW -- remove="True" for main.js ONLY
│       └── cssregistry.xml        # NEW -- remove="True" for main.css ONLY
└── skins/                          # ENTIRE DIRECTORY DELETED (COEX-02/03/05)
```

<research_corrections>

### Correction 1 (HIGH confidence, source-verified): `id = 'login_form'` alone does not render into HTML

`z3c.form.form.Form` (installed: `z3c.form==3.2.11`) defines:
```python
# Source: z3c.form-3.2.11-py2.7-linux-x86_64.egg/z3c/form/form.py:216-218
@property
def id(self):
    return self.name.replace('.', '-')
```
This is a Python-level property, read by z3c.form internals (e.g. widget id prefixing), but the actual `<form>` tag markup comes from `plone.z3cform` (installed: `0.8.1`), whose `templates/macros.pt` `titlelessform` macro — used by **both** the wrapped-form path (`wrappedform.pt`, what `wrap_form()`/`FormWrapper` uses) and the standalone path (`form.pt`) — renders:
```xml
<!-- Source: plone.z3cform-0.8.1-py2.7.egg/plone/z3cform/templates/macros.pt:30-31 -->
<form action="." method="post"
      tal:attributes="action view/action; enctype view/enctype">
```
No `id` attribute, anywhere in the render chain, in any of `layout.pt`, `wrappedform.pt`, `form.pt`, or `macros.pt`. Setting `id = 'login_form'` as a class attribute on `TokenForm` (shadowing the parent's property, which does work at the Python level) changes nothing about the emitted HTML.

**Recommended fix** (verified safe — `GrokkedForm.render()` → `z3c.form.form.BaseForm.render()` is a pure string-returning method; no update/widget-processing logic runs inside `render()` itself):
```python
# Source: browser/forms/token.py, new method on TokenForm
def render(self):
    html = super(TokenForm, self).render()
    # plone.z3cform 0.8.1's titlelessform macro never emits an id
    # attribute on <form>; Plone's own (untouched) popupforms.js
    # binds its ajax overlay via formselector: 'form#login_form',
    # which must match THIS form -- the second, ajax-loaded fragment
    # -- not just the stock login form Plone already renders correctly.
    return html.replace('<form ', '<form id="login_form" ', 1)
```
This is why COEX-09 names the *header link* as the real test: a direct POST to `@google-authenticator-token` never asks the overlay's `formselector` to find anything, so a testbrowser test that skips the link can pass while the real jQuery-driven flow is dead.

### Correction 2 (HIGH confidence, source-verified): the `imio.dms.mail` collision is real, not hypothetical

`imio.dms.mail`'s own `jsregistry.xml` (checked out on this machine at `/srv/src/imio.dms.mail/imio/dms/mail/profiles/default/jsregistry.xml`) contains:
```xml
<javascript id="popupforms.js" insert-after="form_tabbing.js" />
```
This bare entry (no `directory`/`enabled`/`remove` attributes) only **repositions** an existing `portal_javascripts` resource named `popupforms.js` — it does not create one. `imio.googleauthenticator`'s own `profiles/default/jsregistry.xml` currently contains:
```xml
<javascript id="popupforms.js" remove="True" enabled="False" />
```
`remove="True"` deletes the resource object outright. Whichever profile's import step runs relative to the other, the net result converges on "no `popupforms.js` resource exists," because a delete cannot be undone by a bare reposition entry with nothing to reposition. This breaks every `jQuery.tools` `prepOverlay` call across the *entire* `imio.dms.mail` site (delete/rename dialogs, `imio.pm.wsclient` popups, `eea.faceted-navigation` widgets, the users/groups add forms — all present in that jsregistry.xml), not just this package's own login form.

Confirmed as a live concern, not a paper risk: `server.dmsmail/dev.cfg` already lists `imio.googleauthenticator` under `# MOD-1076: evaluation only`, with a throwaway `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` already provisioned — i.e. this exact package is already staged for a real side-by-side deployment with the real `imio.dms.mail`, not a synthetic future scenario.

### Correction 3 (HIGH confidence): stale line numbers in `REQUIREMENTS.md`/`ROADMAP.md`

- `BUG-01` cites `token.py:112-113`; the current redirect code (after Phases 3-6 rewrote enrollment/lockout logic ahead of it) is at `token.py:136-137` (`redirect_url = request_data.get('next_url', context_url)` / `self.request.response.redirect(redirect_url)`).
- The phase notes cite `control_panel_extra.html (controlpanel.py:84)`; the actual `restrictedTraverse` call is at `controlpanel.py:101`. `request_bar_code_reset_email.pt (request_bar_code_reset.py:90)` is, however, exactly accurate — verified.

### Correction 4 (MEDIUM confidence, contradicts a specific roadmap claim): the email path is *not* zero-coverage

The phase notes say "The email path has zero test coverage, so CI will not notice [deleting `skins/`]." This is not accurate as of the current test suite: `tests/test_request_bar_code_reset.py::test_reset_email_survives_a_non_ascii_sender_name` and two sibling tests already drive `RequestBarCodeResetForm.handleSubmit()` end-to-end, which calls `self.context.restrictedTraverse('request_bar_code_reset_email')` and asserts on the rendered mail body's content. `setUp()` even explicitly calls `self.portal.setupCurrentSkin(self.layer['request'])` with the comment "The email body is a skin template, so it is only traversable once the portal's skin is bound to this request" — proving this exact team already knows the coupling exists. Deleting `skins/` without converting the template in the same commit **will** turn this pre-existing test red (an `AttributeError`/`NotFound` out of `restrictedTraverse`), which is a safety net, not a silent gap — but it is real evidence the conversion must land in the same commit as the deletion, exactly as COEX-04's phase note already (correctly) insists. One side-effect the planner should note: after conversion, `self.portal.setupCurrentSkin(...)` in that test's `setUp()` becomes dead code (a `ViewPageTemplateFile` needs no skin binding) — harmless to leave, cheap to remove.

</research_corrections>

### Pattern: `ViewPageTemplateFile` replacement for a `restrictedTraverse`'d skin template

**What:** Both `control_panel_extra.html` and `request_bar_code_reset_email.pt` are reached via `self.context.restrictedTraverse('<name>')`, which only works while `skins/` is registered as a `portal_skins` layer. `ViewPageTemplateFile` (from `Products.Five.browser.pagetemplatefile`, already installed as part of `Zope2`) is the standard Zope 2 replacement: a class attribute descriptor, bound to the instance at attribute-access time.

**When to use:** Any time a view/form needs to render an auxiliary fragment that used to live in `skins/` and was looked up by name.

**Verified namespace contract** (from the installed `Products.Five.browser.pagetemplatefile.ViewPageTemplateFile.pt_getContext`): the template gets `request = instance.request`, `context = instance.context`, and **`here = instance.context`** (not the view) — both templates use `here.email_from_name`/`here.portal_url` idioms that map directly onto `context`, so no template-body edits are needed, only the Python-side lookup mechanism.

**Example — `browser/controlpanel.py`:**
```python
# Source: verified against Zope2-2.13.30-py2.7-linux-x86_64.egg/Products/Five/browser/pagetemplatefile.py
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

class GoogleAuthenticatorSettingsEditForm(AutoExtensibleForm, form.EditForm):
    additional_template = ViewPageTemplateFile('templates/control_panel_extra.pt')

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

**Example — `browser/forms/request_bar_code_reset.py`:**
```python
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile

class RequestBarCodeResetForm(form.SchemaForm):
    mail_text_template = ViewPageTemplateFile('templates/request_bar_code_reset_email.pt')

    @button.buttonAndHandler(_('Submit'))
    def handleSubmit(self, action):
        ...
        mail_text = self.mail_text_template(
            member=user, bar_code_reset_url=signed_url, charset='utf-8')
        mail_text = mail_text.format(bar_code_reset_url=signed_url)
```
The template files themselves need no content edit — only their filesystem home (`skins/googleauthenticator_custom/*.html`/`.pt` → `browser/templates/*.pt` and `browser/forms/templates/*.pt`) and the two Python call sites above.

### Pattern: one-line BUG-01/BUG-06 fixes using stock, already-installed tools

**BUG-06** (`adapter.py`, the actual root cause of the FIXME in `helpers.py`):
```python
# Source: adapter.py, CameFromAdapter.getCameFrom -- the ONE call site
def getCameFrom(self):
    return extract_next_url_from_referer(self.request, quote_url=True)
```
`extract_next_url_from_referer`'s `quote_url` parameter has existed since before this phase and has never been passed as `True` anywhere in the codebase — the FIXME comment in `helpers.py` is attached to a function that already has the fix built in and unused.

**BUG-01** (`browser/forms/token.py::handleSubmit`, current lines 136-137):
```python
# Source: browser/forms/token.py -- pattern matches Plone's own stock
# login_form.cpt: "next python:test(next is not None and isURLInPortal(next), next, None)"
from Products.CMFCore.utils import getToolByName
...
redirect_url = request_data.get('next_url', context_url)
portal_url_tool = getToolByName(self.context, 'portal_url')
if not portal_url_tool.isURLInPortal(redirect_url):
    redirect_url = context_url
self.request.response.redirect(redirect_url)
```
Both fixes are one function call each; neither introduces a new dependency, and both reuse an idiom Plone's own stock `login_form.cpt` already uses for the identical problem (`isURLInPortal`).

### Anti-Patterns to Avoid
- **Re-vendoring the login overlay to "fix it properly":** the vendored copy already exists precisely because someone once tried to make the overlay "work properly" with 2FA and gave up (the login-overlay binding in the vendored `popupforms.js` is commented out with "Temporary disabled, as doesn't work with Google Authenticator app"). The correct fix is deletion + a two-line `TokenForm` change, not a better vendored copy.
- **Trusting the roadmap's stated line numbers over the source.** Two of the four cited line references in this phase's requirement text are stale (see Correction 3). Always re-derive from the current file.
- **Assuming a `testbrowser`/`mechanize` test proves the overlay works.** It cannot execute JavaScript; see Validation Architecture below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Validating a redirect target stays on-site | A custom `urlparse`-based host/scheme comparison | `getToolByName(context, 'portal_url').isURLInPortal(url)` | Stock CMFCore tool, already used by Plone's own `login_form.cpt` for the identical `came_from`/`next` problem; handles relative URLs, virtual hosting (`VirtualHostMonster`), and scheme edge cases this package would otherwise have to rediscover. |
| Preserving special characters through a query string round-trip | A custom encode/decode pair | `urllib.quote`/`urllib.unquote` (stdlib, already imported in `helpers.py`) | `extract_request_data_from_query_string` already `unquote()`s on read; pairing it with `quote()` on write (via the already-present, already-unused `quote_url` parameter) closes the loop with zero new code. |
| Rendering a Zope 2 view fragment outside the normal ZCML `browser:page` registration | A new skin-directory registration, or a hand-rolled template loader | `Products.Five.browser.pagetemplatefile.ViewPageTemplateFile` as a class attribute | The stock, standard Zope 2 replacement for exactly this "auxiliary fragment a view renders itself" use case; verified namespace (`here`/`context`/`request`) needs zero template-body changes. |

**Key insight:** Every "don't hand-roll" item in this phase is "use the tool Plone's own stock template/code already uses for the identical problem" — this is a coexistence phase precisely because the vendored copies drifted away from doing that.

## Runtime State Inventory

This phase deletes GenericSetup-managed ZODB registry state (`portal_skins`, `portal_javascripts`, `portal_css`), which is exactly the class of change this inventory exists to catch.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. This package has never shipped to a persisted production site (`imio.googleauthenticator` is pre-1.0, per `setup.py`'s `version = '1.0.0.dev0'`); no ZODB carries this package's `googleauthenticator_custom` skin layer or the `remove="True"`-mutated `popupforms.js` registry state outside test/dev sandboxes. | None for this phase's own commits. |
| Live service config | `server.dmsmail`'s dev buildout (`/srv/src/server.dmsmail/dev.cfg`) already lists `imio.googleauthenticator` under `# MOD-1076: evaluation only` with a throwaway `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`. Any Zope instance already built from that buildout carries the *current* (pre-this-phase) `jsregistry.xml`/`skins.xml` state in its ZODB `portal_javascripts`/`portal_skins` tools. | Not a code-edit item, but worth surfacing to whoever operates that environment: reinstalling/upgrading the package there after this phase ships is required to actually clear the stale `remove="True"` mutation — a fresh `bin/instance` from an old Data.fs will not self-heal. Flag as an operational note, not a task in this phase's commits. |
| OS-registered state | None. No Task Scheduler, pm2, systemd, or launchd artifacts are touched by this phase. | None. |
| Secrets/env vars | None touched. `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` (Phase 3) is unaffected by this phase's changes. | None. |
| Build artifacts | `MANIFEST.in`'s `recursive-include src/imio/googleauthenticator/skins *` line becomes a no-op glob once `skins/` is deleted (harmless if left, but should be deleted in the same commit as COEX-05 for cleanliness — a stale include line does not break the sdist, `check-manifest`'s CI step may flag it as pointing at nothing). `setup.py`'s `include_package_data = True` needs no change. | Delete the one stale `MANIFEST.in` line in the same commit as `skins/`'s deletion. |

## Common Pitfalls

### Pitfall 1: Setting `TokenForm.id` and believing COEX-01 is done
**What goes wrong:** The class attribute is set, existing tests (which never assert on rendered HTML content, only HTTP status) stay green, and the login overlay silently never binds to the token form.
**Why it happens:** `z3c.form`'s `id` property is real and does something (internal widget-id namespacing) — it is easy to assume it reaches the template because it "sounds" like exactly what's needed.
**How to avoid:** Assert on the literal rendered HTML string `id="login_form"` at `@@google-authenticator-token`, not just HTTP 200.
**Warning signs:** A "passing" COEX-01 test that never inspects `browser.contents`.

### Pitfall 2: Treating the `imio.dms.mail` collision as "will be caught in integration testing later"
**What goes wrong:** `imio.dms.mail` is not a dependency of this package's own buildout, so nothing in `bin/test` will ever exercise the real collision, and it ships broken to the first site that installs both.
**Why it happens:** The two packages' `jsregistry.xml` entries look unrelated at a glance (one repositions, one removes) and are in different repositories.
**How to avoid:** Write the synthetic-collision test described in Validation Architecture below, using the *actual* colliding XML fragment quoted in `<research_corrections>` Correction 2, and add a `checkpoint:human-verify` against the real `server.dmsmail` MOD-1076 environment before calling COEX-07 done.
**Warning signs:** COEX-07 marked complete with no test that ever constructs `imio.dms.mail`'s specific `<javascript id="popupforms.js" insert-after="form_tabbing.js" />` entry.

### Pitfall 3: Deleting `skins/` before converting both `restrictedTraverse` targets
**What goes wrong:** `control_panel_extra` and `request_bar_code_reset_email` immediately 500 (or, for the email path, raise inside a `try/except ValueError` that swallows it into a generic "unexpected error" status message — see `request_bar_code_reset.py`'s `except ValueError: logger.exception(...); reason = _("An unexpected error occurred.")`), and — per Correction 4 — the *email* failure is masked by that broad `except ValueError`, so a human reading the status message sees "unexpected error," not "template missing."
**Why it happens:** `skins/` looks like a single deletable unit; the two live (non-override) templates hiding inside it are easy to miss.
**How to avoid:** Same commit, as the roadmap's phase notes already insist — convert both call sites and delete `skins/` together.
**Warning signs:** A commit whose diff touches `skins/` but not `controlpanel.py`/`request_bar_code_reset.py`.

### Pitfall 4: The `jsregistry.xml` position-pinning tests (`test_every_javascript_registration_pins_its_position`, `test_registered_javascript_loads_after_jquery`) do NOT need to change
**What goes wrong:** A planner assumes both existing tests in `tests/test_setuphandlers.py` need rewriting because COEX-03 touches `jsregistry.xml`.
**Why it happens:** Both tests parse the same file COEX-03 edits.
**How to avoid:** Read them first — both loops explicitly `continue` past any node with `remove="True"` and only assert about `main.js`'s own position relative to jQuery, which COEX-03 does not touch. They remain valid, unmodified, after the `popupforms.js` entries and `remove="True"` line are deleted.
**Warning signs:** Unnecessary edits to these two tests in the COEX-03 commit's diff.

### Pitfall 5: Assuming a `testbrowser` (`plone.testing.z2.Browser`) test proves the overlay works end to end
**What goes wrong:** `zope.testbrowser`/`mechanize` (what every existing test in this suite uses) has no JavaScript engine. A test that "clicks the Log in link" via `browser.getLink(...).click()` only ever exercises the plain HTTP navigation Plone would perform *without* JS — it can prove the underlying markup/redirect chain is correct, but cannot prove the jQuery Tools overlay actually binds `formselector: 'form#login_form'` and completes the AJAX round trip in a real browser.
**Why it happens:** It is the only test tool this suite has ever used (`test_robot.py`, which could exercise real JS via Selenium, is excluded everywhere per `CLAUDE.md`), so it is tempting to over-claim what it proves.
**How to avoid:** State explicitly, in the requirement-to-test map, that COEX-09's JS-level proof is a `checkpoint:human-verify`, not an automated test — see Validation Architecture.
**Warning signs:** A verification report claiming COEX-09 is "fully automated."

## Code Examples

### Exact stock overlay binding selector (proves what COEX-01 must satisfy)
```javascript
// Source: Products.CMFPlone-4.3.20-py2.7.egg/Products/CMFPlone/skins/plone_ecmascript/popupforms.js:76-98
// (untouched Plone stock file -- NOT the vendored copy this phase deletes)
$('#portal-personaltools a[href$="/login"], #portal-personaltools a[href$="/login_form"], '
+ '.discussion a[href$="/login"], .discussion a[href$="/login_form"]').prepOverlay(
    {
        subtype: 'ajax',
        filter: common_content_filter,
        formselector: 'form#login_form',   // <-- the literal selector both forms must satisfy
        cssclass: 'overlay-login',
        noform: function () { /* ... reload/redirect fallback ... */ },
        redirect: function () { /* ... */ }
    }
);
```

### `ska` 1.7.5's signature scope (settles the `ajax_load` open decision with certainty)
```python
# Source: ska-1.7.5-py2.7.egg/ska/utils.py, RequestHelper.validate_request_data (lines 154-204)
def validate_request_data(self, data, secret_key):
    signature = data.get(self.signature_param, '')
    auth_user = data.get(self.auth_user_param, '')
    valid_until = data.get(self.valid_until_param, '')
    extra = extract_signed_data(
        data=data, extra=data.get(self.extra_param, '').split(','))
    # `extra` is only ever populated from an explicit `extra_param` value
    # this codebase never sets (sign_user_data() calls sign_url() with no
    # `extra=` kwarg at all) -- so `extra` is always {} here in practice.
    return self.signature_cls.validate_signature(
        signature=signature, auth_user=auth_user, secret_key=secret_key,
        valid_until=valid_until, return_object=True, extra=extra)

# Source: ska-1.7.5-py2.7.egg/ska/base.py, Signature.get_base (lines 181-201)
@classmethod
def get_base(cls, auth_user, timestamp, extra=None):
    _base = [str(timestamp), auth_user]
    if extra:
        _base.append(sorted_urlencode(extra))
    return ("_".join(_base)).encode()
```
Any key in `data` other than `signature`/`auth_user`/`valid_until`/(an unused) `extra` — including `ajax_load`, `next_url`, `ajax_include_head`, `target` — is never read by `validate_request_data` and never enters the hash `get_base` computes. **`ska` cannot fail on `ajax_load`,** full stop; this needs no browser test to "settle," only this source read (a browser test is still valuable to prove the *overlay* injects it correctly and the whole chain survives in practice, but the roadmap's "silent signature failure" fear is unfounded).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Vendored, stale copy of `popupforms.js`/`login_form.cpt` fighting the 2FA flow (login-overlay binding actively commented out in the vendored copy) | `TokenForm.id`-carrying render + deletion, relying entirely on Plone's own untouched stock assets | This phase | Restores the login overlay Plone 4.3.20 ships, removes ~350 lines this package had to keep in sync with upstream Plone forever, and removes the `imio.dms.mail` collision (Correction 2). |
| `restrictedTraverse('<skin-name>')` for auxiliary template fragments | `ViewPageTemplateFile` class attribute | This phase | Standard Zope 2/Five idiom; removes the last two reasons `skins/`/`registerDirectory` need to exist at all. |
| Unquoted, unvalidated `next_url`/`came_from` round-trip | `quote_url=True` on write, `portal_url.isURLInPortal()` on read | This phase | Closes an open redirect (BUG-01) and a query-string corruption bug (BUG-06) with two one-line changes reusing code already in the module. |

**Deprecated/outdated:** The entire `skins/` mechanism for this package. Zope 2's old-style skin-directory overrides (`cmf:registerDirectory` + `skins.xml`) predate `browser:page`/`ViewPageTemplateFile` and have no place in a package that otherwise already uses z3c.form/`plone.directives.form` throughout.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | OWASP ASVS 4.0's redirect-validation control is conventionally cited as within the "Validation, Sanitization and Encoding" (V5) chapter; ASVS 5.0 renumbers this to §3.7.2 ("Web Frontend Security"). Neither exact clause number was cross-checked against the specific ASVS edition this project's `REQUIREMENTS.md` otherwise cites (it references ASVS "V2" elsewhere without a version). | Security Domain | Low — cosmetic citation only; the control itself (allowlist-validate redirect destinations) is undisputed and independently verified against Plone's own stock template using the identical idiom. |

**If this table were otherwise empty:** every other claim in this document is either read directly from this repository's own source files or from the exact installed egg source in this buildout (`z3c.form==3.2.11`, `plone.z3cform==0.8.1`, `ska==1.7.5`, `Products.CMFPlone==4.3.20`, `Zope2==2.13.30`), all confirmed present via `find`/`grep`/`Read` in this session — not from training-data recollection.

## Open Questions

1. **Should the `profiles/uninstall/skins.xml` file be deleted outright, or repurposed?**
   - What we know: after COEX-05, the default profile no longer registers a `googleauthenticator_custom` skin layer, so there is nothing left for an uninstall step to un-register.
   - What's unclear: whether QuickInstaller's uninstall-profile lookup tolerates an empty/missing `profiles/uninstall/` directory gracefully, versus needing at least one file present (it already has `configure.zcml`'s `genericsetup:registerProfile name="uninstall"` registered regardless of directory contents, so an empty directory is almost certainly fine, but this wasn't executed in this session).
   - Recommendation: delete `skins.xml` from `profiles/uninstall/`, add the new `jsregistry.xml`/`cssregistry.xml` (for `main.js`/`main.css`), and let a Wave-0-style smoke test (`applyProfile(portal, 'imio.googleauthenticator:uninstall')`) confirm the profile still imports cleanly with only two files.

2. **Exact template filename/extension convention for the two new `.pt` files.**
   - What we know: `control_panel_extra.html` currently uses `.html`; `request_bar_code_reset_email.pt` already uses `.pt`. `ViewPageTemplateFile` does not care about the extension for TAL parsing.
   - What's unclear: whether to standardize both on `.pt` (this package's only other template-shaped file convention) or preserve the historical `.html` for the control-panel fragment.
   - Recommendation: standardize both on `.pt` under `browser/templates/` and `browser/forms/templates/` respectively — purely cosmetic, zero behavioural risk either way.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `bin/test` / `plone.testing.z2.Browser` | All new/changed tests | ✓ | zope.testbrowser 3.11.1 (via `plone.testing`) | — |
| `Products.CMFPlone` (stock `popupforms.js`/`login_form.cpt`) | COEX-01/02/03/09 | ✓ | 4.3.20 | — |
| `ska` | BUG-01/06 verification, `ajax_load` question | ✓ | 1.7.5 (pinned, load-bearing per `CLAUDE.md`) | — |
| `imio.dms.mail` (real package, for a genuine two-egg install) | COEX-07's full proof | ✓ present on this machine at `/srv/src/imio.dms.mail` and checked out inside `/srv/src/server.dmsmail`, but NOT a dependency of this package's own buildout | — | Synthetic-collision test using the real XML fragment (see Validation Architecture) + `checkpoint:human-verify` against `server.dmsmail`'s existing MOD-1076 evaluation environment, rather than pulling `imio.dms.mail`'s ~40-egg dependency tree into this package's own `test-4.3.cfg`. |
| Real browser with JS (for COEX-09's overlay-binding proof) | COEX-09 | Not available in `bin/test` (no Selenium/Robot in this suite; `test_robot.py` excluded everywhere per `CLAUDE.md`) | — | `checkpoint:human-verify`: a human clicks the real header "Log in" link in a real browser against a running `bin/instance`. |

**Missing dependencies with no fallback:** None — everything above has either a real tool or an explicit, honest human-verify fallback.

**Missing dependencies with fallback:** `imio.dms.mail` (real two-egg install) and a JS-capable browser, both covered above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` 4.4.4 via `bin/test`, `unittest2`-style test classes, `plone.app.testing` layers (already in use throughout this package's suite) |
| Config file | none dedicated — driven by `base.cfg`'s `[test]` buildout part |
| Quick run command | `bin/test -t <test_method_or_pattern>` |
| Full suite command | `bin/test -t '!robot'` (per `CLAUDE.md`; `test_robot.py` needs a real browser and is excluded everywhere) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COEX-01 | `TokenForm`'s rendered `<form>` carries `id="login_form"` | integration (Browser, content assertion) | `bin/test -t test_token_form_carries_login_form_id` | ❌ Wave 0 (extend `tests/test_token.py` or `tests/test_generic.py`) |
| COEX-02 | `login_form.cpt`/`.metadata` no longer exist on disk | unit (filesystem fact) | `bin/test -t test_login_form_override_is_deleted` | ❌ Wave 0 |
| COEX-03 | `popupforms.js` vendored copy, its `jsregistry.xml` entries, and `remove="True"` are all gone | unit (filesystem + `minidom` XML assertion, precedent: `tests/test_setuphandlers.py`) | `bin/test -t test_popupforms_js_is_not_vendored` | ❌ Wave 0 |
| COEX-04 | `control_panel_extra`/`request_bar_code_reset_email` still render; no `restrictedTraverse` remains | integration (existing `test_control_panel_view`, `test_reset_email_survives_a_non_ascii_sender_name` extended) + unit (source-grep, precedent: `test_no_second_factor_state_written_from_the_plugin`'s style) | `bin/test -t test_control_panel_view`, `bin/test -t test_reset_email_survives_a_non_ascii_sender_name`, new `bin/test -t test_no_restrictedTraverse_left_in_browser_code` | ✅ (first two) / ❌ Wave 0 (source-grep test) |
| COEX-05 | Skin layer, `skins.xml`, `registerDirectory`, `skins/` gone | unit (filesystem + ZCML source-grep) | `bin/test -t test_skin_layer_is_removed` | ❌ Wave 0 |
| COEX-06 | `profiles/uninstall/` restores install-time registry changes | integration (`applyProfile` install then uninstall, assert `portal_javascripts`/`portal_css` resource sets, precedent: `test_reapply_profile_keeps_plugin_first_and_unique`) | `bin/test -t test_uninstall_restores_resource_registries` | ❌ Wave 0 |
| COEX-07 | Both install orders leave both packages working, `popupforms.js` registered exactly once | integration (synthetic collision, using `imio.dms.mail`'s actual XML fragment) **+ non-automatable real two-egg install** | `bin/test -t test_popupforms_js_survives_either_install_order` (synthetic) | ❌ Wave 0 (synthetic) / **N/A — `checkpoint:human-verify` against `server.dmsmail` MOD-1076 environment for the real two-egg proof** |
| COEX-09 | Header "Log in" link reaches token form and completes | integration (`Browser.getLink().click()` proves the markup/redirect chain) **+ non-automatable JS-overlay proof** | `bin/test -t test_login_link_reaches_token_form` | ❌ Wave 0 (markup/redirect chain) / **N/A — `checkpoint:human-verify`, real browser, real click, since `bin/test` has no JS engine** |
| BUG-01 | Off-site `next_url` refused; on-site honoured | integration (`tests/test_token.py`) | `bin/test -t test_next_url_is_validated_against_the_portal` | ❌ Wave 0 |
| BUG-06 | Query-string values survive quoting round-trip | unit (`tests/test_adapter.py`, new `TestCameFromAdapter` class) | `bin/test -t test_get_came_from_quotes_the_value` | ❌ Wave 0 (no `TestCameFromAdapter` class exists yet — only `TestEnhancedUserDataPanelAdapter`) |

### Sampling Rate
- **Per task commit:** the specific new/changed test method(s) for that task, e.g. `bin/test -t test_next_url_is_validated_against_the_portal`
- **Per wave merge:** `bin/test -t '!robot'`
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus both `checkpoint:human-verify` items above (COEX-07's real two-egg install, COEX-09's real-browser click) recorded as UAT, not silently skipped.

### Wave 0 Gaps
- [ ] `tests/test_adapter.py` — needs a new `TestCameFromAdapter` class (none exists; only `TestEnhancedUserDataPanelAdapter` is present) to cover BUG-06.
- [ ] Source-grep test for "no `restrictedTraverse` remains in `browser/`" (COEX-04) — no shared fixture beyond what `tests/test_pas_plugin.py`'s existing MFA-12 source-grep test already demonstrates as a pattern in this codebase.
- [ ] A synthetic `imio.dms.mail`-collision fixture for COEX-07 — constructs the exact `<javascript id="popupforms.js" insert-after="form_tabbing.js" />` entry (quoted verbatim from `/srv/src/imio.dms.mail/imio/dms/mail/profiles/default/jsregistry.xml:87`) and applies it via `portal_javascripts` before/after this package's own profile import.
- Framework install: none — `zope.testrunner`/`plone.app.testing`/`plone.testing.z2.Browser` are already fully wired.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Marginal | The login-overlay mechanics themselves carry no new authentication logic (already settled in Phases 4-5); this phase only changes *how* the existing, already-verified 2FA challenge is delivered to the browser. |
| V3 Session Management | No | No session-token handling changes in this phase. |
| V4 Access Control | No | No permission/role changes. |
| V5 Input Validation | Yes | `portal_url.isURLInPortal()` allowlist check on `next_url` (BUG-01); `quote()`/`unquote()` round-trip integrity on query-string values (BUG-06). `[CITED: OWASP ASVS — unvalidated-redirect control, historically V5 in ASVS 4.0 / renumbered §3.7.2 in ASVS 5.0 — exact clause number not cross-checked against a specific edition this session, see Assumptions Log A1]` |
| V6 Cryptography | No (unchanged) | `ska` signature scope was read for correctness (Code Examples), not modified. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Open redirect via `next_url`/`came_from` (BUG-01) | Tampering / Spoofing (phishing pivot after a legitimate login) | Allowlist validate the destination against `portal_url.isURLInPortal()` before calling `response.redirect()`; refuse (fall back to a known-good same-site URL) rather than warn-and-continue. |
| Query-string corruption enabling parameter-boundary confusion (BUG-06) | Tampering | Quote reserved characters (`&`, `=`, `+`, space) on write, `unquote()` on read — already half-implemented in this codebase; this phase completes the pairing. |
| Global GenericSetup mutation with no uninstall counterpart (`jsregistry.xml`'s `remove="True"`) | Denial of Service (site-wide, not attacker-triggered but operator-triggered by install order) | Never ship a `remove="True"`/global-registry mutation without a matching `profiles/uninstall/` counterpart (COEX-06); prefer additive/repositioning registry entries over deletions of resources this package does not own. |

## Sources

### Primary (HIGH confidence — read directly from this repo or the exact installed egg in this buildout)
- `/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/` — full read of `pas_plugin.py`, `subscribers.py`, `helpers.py`, `adapter.py`, `configure.zcml`, `browser/configure.zcml`, `browser/controlpanel.py`, `browser/forms/token.py`, `browser/forms/request_bar_code_reset.py`, `skins/googleauthenticator_custom/*`, `profiles/default/{skins,jsregistry,cssregistry}.xml`, `profiles/uninstall/skins.xml`, `tests/test_setuphandlers.py`, `tests/test_generic.py`, `tests/test_request_bar_code_reset.py`, `tests/test_token.py`, `tests/test_adapter.py`, `MANIFEST.in`, `setup.py`
- `/home/cadam/buildout-cache/eggs/Products.CMFPlone-4.3.20-py2.7.egg/Products/CMFPlone/skins/{plone_ecmascript/popupforms.js, plone_login/login_form.cpt}` — stock Plone assets, exact overlay selector and `came_from`/`ajax_load`/`next` hidden-input handling
- `/home/cadam/buildout-cache/eggs/z3c.form-3.2.11-py2.7-linux-x86_64.egg/z3c/form/form.py` — `Form.id`/`BaseForm.render()`
- `/home/cadam/buildout-cache/eggs/plone.z3cform-0.8.1-py2.7.egg/plone/z3cform/{templates.py,layout.py,templates/{macros,form,wrappedform}.pt,configure.zcml,templates.zcml}` — full render-chain trace proving no `id` attribute is ever emitted
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/Products/Five/browser/pagetemplatefile.py` — `ViewPageTemplateFile` namespace contract (`here`, `context`, `request`)
- `/srv/cache/eggs/ska-1.7.5-py2.7.egg/ska/{utils.py,base.py,shortcuts.py}` — signature scope, settling the `ajax_load` open decision
- `/srv/src/imio.dms.mail/imio/dms/mail/profiles/default/jsregistry.xml` — the actual colliding entry
- `/srv/src/server.dmsmail/{dev.cfg,versions-dev.cfg,sources-dev.cfg}` — confirms `imio.googleauthenticator` is already staged (MOD-1076) alongside the real `imio.dms.mail`
- `.planning/phases/04-pas-boundary/04-0{1,2,3,4}-SUMMARY.md` — final redirect mechanism (`send_2fa_redirect`, `IPubBeforeCommit` subscriber, `IChallengePlugin.challenge`) this phase's overlay work is verified against, per the roadmap's Phase 4 dependency

### Secondary (MEDIUM confidence)
- [Unvalidated Redirects and Forwards — OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html) — general control description
- [Open Redirect — OWASP Foundation](https://owasp.org/www-community/attacks/open_redirect) — threat pattern description

### Tertiary (LOW confidence)
- ASVS exact clause number for the redirect-validation control (V5 in 4.0, §3.7.2 in 5.0) — not cross-checked against the specific edition this project otherwise cites; see Assumptions Log A1.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A (no new packages) — HIGH by construction
- Architecture (overlay binding, template render chain, `ska` signature scope): HIGH — verified against installed egg source, not training-data recollection
- Two-package collision (COEX-07): HIGH — verified against the real, checked-out `imio.dms.mail` source on this machine
- Pitfalls / test-map: HIGH for automatable items, explicitly flagged MEDIUM/non-automatable for the two JS/two-egg items that genuinely cannot be proven inside `bin/test`
- Security ASVS clause numbering: LOW (see Assumptions Log A1) — does not affect the correctness of the recommended control, only its citation

**Research date:** 2026-08-04
**Valid until:** Stable for the life of this phase (Plone 4.3.20/z3c.form 3.2.11/plone.z3cform 0.8.1/ska 1.7.5 are all pinned, frozen dependencies per `CLAUDE.md`; no expectation of drift). Re-verify only if any of those pins change.
