# Architecture Research

**Domain:** Plone 4.3 / Zope 2.13 PAS second-factor authentication plugin (brownfield)
**Researched:** 2026-07-28
**Confidence:** HIGH

> **Source basis.** Every claim below is read from the *exact* egg versions this
> buildout resolves (`bin/instance` interpreter path): `Zope2-2.13.30`,
> `Products.PluggableAuthService-1.11.3`, `Products.PluginRegistry-1.4.1`,
> `Products.PlonePAS-5.1.1`, `Products.CMFPlone-4.3.20`, `plone.session-3.5.6`,
> `plone.app.jquerytools-1.9.5`. File:line references are to those installed
> sources, not to training data or upstream docs. The `classify-confidence` seam
> returns `LOW` for a `local-source` provider only because it has no mapping for
> reading primary source; primary source is the highest tier available here.
>
> The existing package architecture is **not** re-derived — see
> `.planning/codebase/ARCHITECTURE.md`.

---

## Executive answer

| Question | Answer |
|---|---|
| Is `IChallengePlugin` the right place for the redirect? | **Yes for every path that ends in `Unauthorized`** (deep links, basic auth, expired session). **No for the login-form POST** — Plone 4.3's `login_form` → `logged_in` → `login_failed` chain returns HTTP 200 and never raises `Unauthorized`, so `challenge()` is never called. That path needs a response side effect; the correct place for it is an `IPubBeforeCommit` subscriber, not `authenticateCredentials`. |
| `ICredentialsResetPlugin` / `IExtractionPlugin`? | Neither. `resetCredentials` is only called from `PAS.resetCredentials()` (logout). `IExtractionPlugin` cannot veto — extraction is the **outer** loop and each extractor gets its own credentials dict. |
| Does plugin order let `credentials_basic_auth` bypass the second factor? | **Yes, and order is the whole ballgame.** The current veto works only because `google_auth` happens to be first among `IAuthenticationPlugin`, an undocumented artefact of one line in `setuphandlers._add_plugin`. Details and three concrete vectors in §3. |
| Can the AJAX overlay be made to fall back without copying `popupforms.js`? | **A non-200 does not work and no response header is read.** But you do not need a fallback: give the token form `id="login_form"` and the existing `formselector` renders it *inside* the overlay. Zero JS, zero skin overrides. §4. |
| memberdata writes on every failed attempt — ZEO implications? | Storage is an `OOBTree` keyed by user id, so cross-user writes resolve; same-user writes conflict and ZPublisher retries up to 3×. **The real hazard is not conflicts, it is `transaction.abort()`**: any request ending in an exception (including `Unauthorized`) loses the write. §5. |
| Where to read the env-var key? | **Per-call `os.environ.get()` inside a plain function.** Not module import time (invisible to `bin/test`, unpatchable), not a `zope.component` utility (one implementation, no swap requirement). §6. |

---

## 1. PAS call order in Plone 4.3, verified

Zope publishes a request, `BaseRequest.traverse()` calls `PAS.validate()`, and PAS
runs exactly this sequence.

```
ZPublisher.Publish.publish()                        Publish.py
  transactions_manager.begin()
  request.traverse()  ──▶  PAS.validate()            PluggableAuthService.py:240
    │
    ├─ INotCompetentPlugin                                              :551
    │     any plugin returns True  ──▶  this user folder gives up entirely
    │
    ├─ _extractUserIds(request, plugins)                                :577
    │     extractors    = listPlugins(IExtractionPlugin)                :586
    │     authenticators = listPlugins(IAuthenticationPlugin)           :595
    │
    │     FOR EACH extractor:                    ◀── OUTER loop        :602
    │       credentials = extractor.extractCredentials(request)         :605
    │       credentials['extractor'] = extractor_id                     :616
    │       _tryEmergencyUserAuthentication(credentials)                :630
    │           ──▶ if it matches, RETURN IMMEDIATELY, no plugin runs
    │       FOR EACH authenticator:              ◀── INNER loop        :648
    │         uid_and_info = auth.authenticateCredentials(credentials)  :651
    │         if user_id is not None: user_ids.append(...)              :666
    │       result.extend(user_ids)              ◀── ACCUMULATES       :675
    │
    │     _tryEmergencyUserAuthentication(DumbHTTPExtractor()...)       :678
    │         # "Emergency user via HTTP basic auth always wins"
    │
    ├─ FOR EACH (user_id, login) in result:                             :251
    │     user = _findUser(...)          IPropertiesPlugin, IGroupsPlugin,
    │                                    IRolesPlugin (add-only)   :780-805
    │     if _authorizeUser(user, ...): RETURN user   ◀── FIRST WINS   :262
    │
    └─ anonymous fallback                                              :278

  mapply(object, ...)          ── the view renders
  notify(PubBeforeCommit)                                     Publish.py
  transactions_manager.commit()

  ══ on ANY exception ══
  err_hook = zpublisher_exception_hook              Zope2/App/startup.py
      ConflictError  ──▶ raise ZPublisher.Retry     (retry_max_count = 3)
      Unauthorized   ──▶ render view, then RE-RAISE
  finally: notify(PubBeforeAbort); transactions_manager.abort()   ◀── ABORT
  ──▶ publish_module_standard: request.response.exception()
        HTTPResponse.exception():  if issubclass(t, Unauthorized):
                                       self._unauthorized()
                                   ...then setStatus(401)
              │
              └─ PAS installed resp._unauthorized in the
                 __before_publishing_traverse__ hook           PAS.py:1058-1067
                   ──▶ PAS._unauthorized()                              :1140
                   ──▶ PAS.challenge(request, response)                 :1152
                         IChallengeProtocolChooser.chooseProtocols      :1159
                         FOR EACH IChallengePlugin (in registry order)  :1177
                           protocol = getattr(challenger,'protocol',id) :1178
                           skip if valid_protocols and protocol not in it
                           if protocol is None or protocol == this one:
                               if challenger.challenge(req, resp):
                                   protocol = this one    ◀── LOCKS the group
```

**Five consequences that decide the design:**

1. **Extraction is the outer loop.** Each extractor produces its *own* dict. Wiping
   one dict is invisible to the others. There is no "consume the request's
   credentials" primitive.
2. **Authentication accumulates, it does not short-circuit.** `result.extend(user_ids)`
   at `:675` collects successes from *every* authenticator, and `validate()` returns
   the *first* one that authorizes (`:262`). An `IAuthenticationPlugin` returning
   `None` therefore vetoes **nothing**.
3. **`challenge()` runs after `transaction.abort()`.** It is reached from
   `HTTPResponse.exception()`, which `publish_module_standard` calls *after*
   `publish()`'s `finally` already aborted. **A challenge plugin must be write-free.**
4. **The first challenger to return `True` sets `protocol` and every challenger with
   a different protocol is skipped** (`:1183-1185`). This is the mechanism that
   suppresses `credentials_basic_auth`'s 401.
5. **Exceptions in a plugin are fail-open.**
   `_SWALLOWABLE_PLUGIN_EXCEPTIONS = (NameError, AttributeError, KeyError, TypeError, ValueError)`
   (`PluggableAuthService.py`, module level). A `KeyError` from
   `credentials['login']` or an `AttributeError` from `None.getProperty(...)`
   silently removes the 2FA plugin from the chain for that credential set.

### Which interface may legitimately redirect

| Interface | Called from | May write the response? | Verdict for this package |
|---|---|---|---|
| `IExtractionPlugin` | `_extractUserIds` outer loop `:605` | No contract for it | **No.** Cannot veto; other extractors still run. |
| `IAuthenticationPlugin` | inner loop `:651` | Contract is `credentials -> (userid, login) \| None`. Nothing else. | **Decision only.** This is the only place that can prevent other authenticators from seeing a credential set (by mutating the dict) — so the veto lives here, but the redirect does not. |
| `IChallengePlugin` | `PAS.challenge()` `:1184` | **Yes, explicitly.** Interface docstring, `interfaces/plugins.py:112-129`: *"Cause the response object to redirect to another URL (a login form page, for instance)"* and *"Returns True if it fired"*. | **The redirect belongs here** — for every path reached via `Unauthorized`. Must be write-free (see consequence 3). |
| `ICredentialsResetPlugin` | `PAS.resetCredentials()`, logout only | Yes (`HTTPBasicAuthHelper.resetCredentials` calls `response.unauthorized()`) | **No.** Wrong lifecycle event. |
| `INotCompetentPlugin` | `validate()` `:551` | No | **No.** Disables the entire user folder for the request, for all users. |
| `IRolesPlugin` | `_findUser` `:792-803` | No | **Cannot veto** — `if roles: user._addRoles(roles)`. Add-only. There is no role-stripping hook. |
| `IUserFactoryPlugin` | `_createUser` `:749` | No | Could substitute a crippled user object, but first non-`None` wins → still order-dependent, and hijacking `PloneUser` is far worse than the status quo. |

**There is no order-independent authentication veto in PAS 1.11.3.** All 22 interfaces
in `interfaces/plugins.py` were checked. This is a property of the framework, not a
gap in the package.

### The login-form POST does not raise `Unauthorized` — verified

`Products/CMFPlone/skins/plone_login/login_form.cpt.metadata`:

```ini
[validators]
validators=login_form_validate
[actions]
action.success=traverse_to:string:logged_in
action.failure_page=traverse_to:string:login_failed
```

`logged_in.cpy` → `if membership_tool.isAnonymousUser(): ... return state.set(status='failure')`
→ `logged_in.cpy.metadata: action.failure=traverse_to:string:login_failed` →
`login_failed.cpt` renders with **status 200**. No exception, no
`response.exception()`, no `_unauthorized()`, **no `challenge()`**.

That is the single fact that forces a second mechanism. It is also why the upstream
author put `response.redirect(..., lock=1)` in `authenticateCredentials` — it was not
laziness, it was the only reachable hook they found.

---

## 2. Recommended component boundaries

```
┌──────────────────────────────────────────────────────────────────────────┐
│  acl_users  (in-site PAS)                                                │
│                                                                          │
│  IExtractionPlugin        credentials_cookie_auth  credentials_basic_auth │
│  (unchanged, ours is NOT one)      session                                │
│                                    │                                     │
│                       ┌────────────┴─────────────┐                       │
│  IAuthenticationPlugin │  google_auth  (MUST be first)                    │
│                        │  ── DECIDE ONLY ──                              │
│                        │  • is_whitelisted_client()? → return None        │
│                        │  • 2FA off for this login?  → return None        │
│                        │  • verify 1st factor via the other authenticators│
│                        │  • WIPE the credentials dict  (the veto)         │
│                        │  • request['_2fa_pending'] = signed_url          │
│                        │  • return None                                   │
│                        │  • except Exception: wipe + log + return None    │
│                        │    ◀── FAIL CLOSED                              │
│                        │  NO response mutation. NO ZODB write.            │
│                        └───────────┬──────────────┘                      │
│                            session    source_users   (see empty dict)    │
│                                                                          │
│  IChallengePlugin      │  google_auth  (first, DISTINCT protocol)         │
│                        │  ── REDIRECT (Unauthorized path) ──             │
│                        │  if request.get('_2fa_pending'):                 │
│                        │      response.redirect(url, lock=1); return True │
│                        │  else: return False                              │
│                        │  NO ZODB write — the txn is already aborted      │
│                        └──────────────────────────────────────────────────│
│                           credentials_cookie_auth  credentials_basic_auth │
│                           ── both SKIPPED once ours fires (protocol lock) │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  IPubBeforeCommit subscriber   (~6 lines, ZPublisher.pubevents)           │
│  ── REDIRECT (login-form POST path, where no Unauthorized is raised) ──   │
│  url = request.get('_2fa_pending')                                        │
│  if url and response.status < 300: response.redirect(url)                 │
│  Fires AFTER the render, BEFORE commit → writes in this request survive.   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│  @@google-authenticator-token  (z3c.form, browser layer)                 │
│  ── THE ONLY THING THAT GRANTS A SESSION ──                              │
│  • validate ska signature + TOTP                                          │
│  • ALL memberdata state writes live here (replay window, attempt counter, │
│    recovery-code consumption) — this path returns 200/302 and COMMITS      │
│  • session._setupSession(userid, response)                                │
│  • <form id="login_form">  ◀── makes the AJAX overlay work, §4            │
└──────────────────────────────────────────────────────────────────────────┘
```

**Boundary rules, stated as invariants:**

| Component | Owns | Must never |
|---|---|---|
| `IAuthenticationPlugin.authenticateCredentials` | the *decision*; the credentials veto; setting the request flag | touch `RESPONSE`; write to the ZODB; let an exception escape |
| `IChallengePlugin.challenge` | the redirect on the `Unauthorized` path; suppressing the basic-auth 401 by winning the protocol group | write to the ZODB (transaction already aborted); claim `protocol = 'http'` (would answer WebDAV/FTP/XML-RPC clients with HTML) |
| `IPubBeforeCommit` subscriber | the redirect on the login-form POST path | do anything but read one request key and set a Location |
| token form view | TOTP + signature validation; **all** second-factor state writes; session creation | be reachable without a valid `ska` signature |

Do **not** create an interface, adapter or utility for any of this beyond what PAS
already demands. There is one implementation of each responsibility.

### Why the request flag rather than a redirect in place

- `authenticateCredentials` regains its contract: pure function of `credentials`.
- `challenge()` becomes the single place that decides *how* to challenge, so the
  protocol-group rule (`:1183`) can do the work of suppressing the 401 — which is
  the actual fix for the basic-auth hole, not a cosmetic refactor.
- `request` is per-thread by construction, so no `zserver-threads 2` hazard. Do
  **not** use a module global.

---

## 3. The `credentials_basic_auth` bypass: three verified vectors

### Vector 1 — the veto is order-dependent, and nothing enforces the order

`setuphandlers._add_plugin` currently does:

```python
pas.plugins.activatePlugin(interface, plugin.getId())
pas.plugins.movePluginsDown(
    interface,
    [x[0] for x in pas.plugins.listPlugins(interface)[:-1]],
)
```

`PluginRegistry.activatePlugin` appends to the **end**;
`movePluginsDown(iface, all_but_last)` walks indexes in reverse and swaps each one
down, which bubbles the *last* entry to position 0. Traced on `[a, b, c, google_auth]`:
`[a,b,g,c]` → `[a,g,b,c]` → `[g,a,b,c]`. So the plugin does end up first — **by
side effect of an incantation with no comment explaining that the security property
depends on it.**

Because `_extractUserIds` accumulates (`:675`) and `validate()` returns the first
authorized user (`:262`), if anything ever puts `source_users` above `google_auth` —
another add-on's `plugins.xml`, a ZMI drag, re-running PlonePAS's own setup handlers —
then for the basic-auth credential set:

1. `source_users.authenticateCredentials(creds)` succeeds → `(user_id, login)` lands
   in `user_ids`.
2. `google_auth` runs *after*, wipes an already-consumed dict, sets a `Location`.
3. `validate()` returns the fully-privileged user. **The request executes with one
   factor.**

**Fix:** replace the incantation with the self-documenting call that already exists in
`PluginRegistry 1.4.1` —

```python
pas.plugins.movePluginsTop(interface, [plugin.getId()])
```

— and add a test that fails if
`listPluginIds(IAuthenticationPlugin)[0] != PAS_ID`. That test is the actual security
control; the ordering call is just how you satisfy it.

### Vector 2 — `redirect(lock=1)` is not a refusal

`ZPublisher/HTTPResponse.py`:

```python
def redirect(self, location, status=302, lock=0):
    self.setStatus(status, lock=lock)
    self.setHeader('Location', location)
    return str(location)
```

It sets a status and a header. **It does not clear the body and does not stop
publishing.** So whenever Vector 1 fires, the requested resource still renders and its
HTML is returned inside a 302 — readable by any client that does not follow redirects
(`curl` without `-L`), and any side effect of a POST has already committed.

This matters far more for basic auth than for cookies: a basic-auth client
re-presents the first factor on **every** request, so `response.setCookie('__ac', '')`
accomplishes nothing, and there is no "consume once" semantics to lean on.

`lock=1` does buy one thing worth keeping: `setStatus` becomes a no-op afterwards
(`_locked_status`), so `HTTPBasicAuthHelper.challenge`'s `setStatus(401)` and
`HTTPResponse.exception`'s `setStatus(401)` cannot clobber the 302.

### Vector 3 — swallowed exceptions are fail-open

`credentials['login']` raises `KeyError` for credential sets without a login (the
`plone.session` cookie set is `{cookie, source, extractor}`). `api.user.get()` returns
`None` for an unknown login, and `None.getProperty(...)` raises `AttributeError`. Both
are in `_SWALLOWABLE_PLUGIN_EXCEPTIONS`, so PAS logs at DEBUG and **continues to the
next authenticator with an intact credentials dict** (`:659-664`).

**Fix:** wipe first, decide second, and wrap the whole body:

```python
def authenticateCredentials(self, credentials):
    try:
        ...  # decide; wipe on the 2FA path
    except Exception:
        logger.exception("2FA plugin failed; refusing credentials")
        credentials.clear()          # fail CLOSED
    return None
```

### Making the second factor authoritative regardless of extractor

There is no order-independent veto (§1). The defence is therefore layered:

1. **Enforce the ordering, with a test.** Vector 1. Cheapest and highest value.
2. **Fail closed.** Vector 3. Three lines.
3. **Move the grant to the session layer.** Nothing may create an `__ac` session
   except the token form view. The plugin never returns a user id for a 2FA-enabled
   account, from *any* extractor, because each extractor's dict passes through the
   first authenticator. That is the design invariant to write down and test —
   one test per extractor (`__ac_name`/`__ac_password` POST, `Authorization: Basic`).
4. **Belt and braces, genuinely order-independent:** deactivate
   `credentials_basic_auth` for `IExtractionPlugin` when 2FA is globally enabled.
   If no extractor turns an `Authorization` header into first-factor credentials, no
   authenticator order can matter. `PlonePAS/setuphandlers.py:226-239` shows Plone
   adds and activates it unconditionally, and `deactivate_basic_reset` /
   `deactivate_cookie_challenge` show selective deactivation is an intended knob.
   **Cost:** WebDAV / FTP / XML-RPC clients lose password auth. For a site with
   mandatory MFA that is the correct outcome, and it is already what the protocol
   chooser implies (below). Confirm with `imio.dms.mail` before doing it.

### What the `ChallengeProtocolChooser` does to our challenger

`PlonePAS/config.py:5-10`:

```python
DEFAULT_CHALLENGE_PROTOCOL = ['http']
DEFAULT_PROTO_MAPPING = {'WebDAV': ..., 'FTP': ..., 'XML-RPC': ...}
```

There is **no `'Browser'` key**, so `chooseProtocols()` returns `None` for browser
requests → `valid_protocols` stays empty → every challenger is eligible → **ours,
being first, fires and locks the group, and both `credentials_basic_auth` (protocol
`'http'`) and `credentials_cookie_auth` (no `protocol` attribute → its own id) are
skipped.** Exactly the behaviour needed.

For WebDAV / FTP / XML-RPC, `valid_protocols == ['http']`, so a challenger with a
distinct protocol is **skipped** and basic auth 401s. That is correct — never send an
HTML redirect to a WebDAV client — and it is safe, because the user is not
authenticated either way. Two notes:

- `RequestTypeSniffer.webdavSniffer` returns `True` for **any method not in
  `('GET','POST')`**, so `HEAD`, `PUT`, `PROPFIND`, `DELETE` are all classified WebDAV.
  Redirect-based challenge only ever happens for GET/POST. Fine.
- **Do not set `protocol = 'http'` on our challenger.** Simplest: do not set
  `protocol` at all; `getattr(challenger, 'protocol', challenger_id)` then yields the
  plugin id, which is distinct by construction.

### Out of scope, now with line numbers

`_extractUserIds` calls `_tryEmergencyUserAuthentication` **twice** — once per
extractor before any plugin runs (`:630`) and once unconditionally at the end against
a synthetic `DumbHTTPExtractor()`, commented *"Emergency user via HTTP basic auth
always wins"* (`:677-682`). Both bypass every plugin by construction. This confirms
PROJECT.md's decision to treat Zope-root/emergency admins as architecturally
unreachable, and gives the citation for the documented limitation.

---

## 4. The AJAX login overlay

### What it actually does on a redirect — verified

`plone.app.jquerytools-1.9.5/browser/overlayhelpers.js`, `pb.prep_ajax_form`:

```js
var formtarget = pbo.formselector;      // 'form#login_form'
options.success = function (responseText, statusText, xhr, form) {
    ...
    myform = el.find(formtarget);
    if (success && myform.length) {
        ajax_parent.empty().append(el);   // re-render the form IN the overlay
        myform.ajaxForm(options);         // rebind with the same options
    } else {
        if (success) {
            if (typeof noform === "function") { noform = noform(el, pbo); }
        } else {
            noform = statusText;          // e.g. 'error'
        }
        switch (noform) {
        case 'reload': api.close(); location.replace(location.href); break;
        case 'redirect': ... location.replace(target); break;
        default: ajax_parent.empty().append(el);   // show it in the overlay
        }
    }
};
options.error = options.success;
```

And `popupforms.js:76-98` binds the login link with
`formselector: 'form#login_form'` and

```js
noform: function () {
    if (location.href.search(/pwreset_finish$/) >= 0) { return 'redirect'; }
    else { return 'reload'; }
}
```

**Trace of the current failure:** the XHR POSTs the login form. The browser follows
the 302 transparently, so jQuery receives the **token form's HTML** with status 200.
`el.find('form#login_form')` finds nothing → `noform()` → `'reload'` →
`location.replace(location.href)`. The user is bounced back to the page they were on,
still anonymous, and never sees the token form. That is the bug, exactly.

### The three suggested escapes, tested against the source

| Approach | Verdict |
|---|---|
| Reach the overlay's own `'redirect'` branch | **Impossible without editing `popupforms.js`.** The `noform` callback hard-codes `'reload'` for every URL not ending `pwreset_finish`. |
| Return a non-200 | **Does not work, and is worse than doing nothing.** `options.error = options.success`, and on failure `noform = statusText` (`'error'`), which hits `default:` → `ajax_parent.empty().append(el)` → the error body is rendered *inside the overlay*. No full page load. |
| A response header | **No such hook exists.** `overlayhelpers.js` 1.9.5 never reads a response header; `xhr` is only forwarded to the `formOverlayStart` trigger. |

### The fix: `id="login_form"` on the token form

You do not need a fallback — you need the overlay to *succeed*.

```python
class TokenForm(form.SchemaForm):
    id = 'login_form'          # matches popupforms.js formselector
```

Then: login POST → 302 → XHR follows → token form HTML contains
`form#login_form` → `myform.length` is truthy → **the token form renders inside the
overlay**, `ploneTabInit` runs, first input is focused, and `myform.ajaxForm(options)`
rebinds submission. The user types the TOTP code in the overlay. On submit, the token
form's action is the signed URL; a valid code sets the session and redirects to the
destination, whose HTML has no `form#login_form` → `noform()` → `'reload'` →
`location.replace(location.href)` → the page reloads **with the session cookie set**.

That last hop is *identical to stock Plone login* (login POST → `logged_in` → no form →
reload), so behaviour matches user expectation. An invalid code re-renders the token
form with its error message and the overlay simply stays open — better UX than today.

**Cost:** one class attribute. **Deleted:** the 310-line `login_form.cpt`, the 197-line
`popupforms.js` copy, `skins/googleauthenticator_custom/`, `skins.xml`, the
`popupforms.js` remove+register pair in `jsregistry.xml`, and with them the
`imio.dms.mail` collision.

**Two things to verify during implementation** (both cheap, both flagged rather than
assumed):

- `pb.add_ajax_load(myform)` prepends a hidden `ajax_load=<timestamp>` input, and
  `pb.ajax_click` appends `ajax_load=` to the GET. Confirm `ska`'s
  `validate_signed_request_data` ignores unsigned extra query parameters — it should,
  since it reads named keys (`signature`, `auth_user`, `valid_until`, `extra`), but a
  test is warranted because a signature failure here is silent from the user's side.
- `common_content_filter` is `'#content>*:not(div.configlet),dl.portalMessage.error,dl.portalMessage.warning,dl.portalMessage.info'`.
  `plone.z3cform.layout`'s `wrap_form` renders inside `#content`, and `el.find()` is a
  descendant search, so the form is reachable — confirm in a browser test.

**Fallback if that misbehaves** (do not build it pre-emptively): `overlayhelpers.js`
exposes `$.plonepopups.remove_overlay(jqObject)` as a public API. Three lines in the
package's *already registered* `browser/static/main.js`, ordered after
`popupforms.js`, unbind the login overlay without copying any file:

```js
jQuery(function ($) {
    $.plonepopups.remove_overlay($('#portal-personaltools a[href$="/login"], ' +
        '#portal-personaltools a[href$="/login_form"]'));
});
```

That still kills the overlay for everyone, including non-2FA users — which is why
`id="login_form"` is the better answer.

### Bonus finding: the vendored copies are stale and actively harmful

`diff` against `Products.CMFPlone-4.3.20`:

- `login_form.cpt` drops the `<input type="hidden" name="came_from">` field, reverts
  `nav_root` → `portal_url` (breaks `mail_password_form` under a navigation root), and
  drops the `plone`/`nav_root` definitions.
- `popupforms.js` reverts `msieversion()` back to `jQuery.browser.msie`, **removed in
  jQuery 1.9**, so the IE guard silently throws or no-ops; and drops
  `dl.portalMessage.warning` from `common_content_filter`, so warning messages are
  swallowed in every Plone overlay site-wide.

The missing `came_from` field explains why `adapter.CameFromAdapter` exists at all
(its docstring says the Plone form field was removed — it was removed *by this
override*). Deleting `login_form.cpt` restores the field and changes what `ICameFrom`
sees. **That is the real entanglement in the override deletion**, and it ties directly
into the `next_url` open-redirect fix at `token.py:112-113`.

---

## 5. memberdata property writes under ZEO

### Where the bytes actually land

`user.setMemberProperties({...})` → `PloneUser.setProperties`
(`PlonePAS/plugins/ufactory.py`) → for each ordered sheet, collect keys where
`sheet.hasProperty(key)` → `MutablePropertySheet.setProperties(user, update)`
(`PlonePAS/sheet.py`) → `ZODBMutablePropertyProvider.setPropertiesForUser`
(`PlonePAS/plugins/property.py`):

```python
self._storage = OOBTree()      # __init__
...
userid = user.getId()
userprops = self._storage.get(userid)
properties.update({'isGroup': isGroup})
if userprops is not None:
    userprops.update(properties)
    self._storage[userid] = self._storage[userid]   # mark the bucket dirty
else:
    self._storage.insert(user.getId(), properties)
```

**The persistent unit is the `OOBTree` bucket, not the user record.** The value is a
plain `dict`, re-pickled into the bucket on every write. An `OOBTree` bucket holds up
to ~30 keys, so ~30 users share one persistent object.

### ConflictError behaviour

| Scenario | Outcome |
|---|---|
| Two **different** users fail 2FA concurrently on two ZEO clients | Same bucket, **different keys** → BTree bucket conflict resolution merges them. No `ConflictError`. |
| The **same** user fails 2FA concurrently (parallel brute force) | Same key, both sides changed → `BTreesConflictError`. |
| A `ConflictError` reaches the publisher | `zpublisher_exception_hook` raises `ZPublisher.Retry`; `HTTPRequest.retry_max_count = 3`, `supports_retry()` sleeps `random.uniform(0, 2**retry_count)` and `retry()` does `self.stdin.seek(0)` so the POST body is replayed. **Up to 3 automatic retries, then the user sees the error.** |

So conflicts are **not** the interesting risk at iMio's scale: the write is per-user,
off the read path, and the retry machinery handles the parallel-brute-force case (which
is precisely the case where a lost increment would matter, and the retry re-reads the
fresh counter, so read-modify-write is correct under retry).

**Conventional Plone mitigations, in the order they matter here:**

1. **Never put the counter in a single shared object.** A site-wide
   `{userid: attempts}` `PersistentMapping` or an annotation on the portal is one
   persistent object for the whole site — a genuine write hotspot and a guaranteed
   conflict under any concurrency. Per-user memberdata avoids it for free. This is
   already the PROJECT.md decision; the OOBTree finding confirms it is the right one.
2. **Keep the write off the success path.** Write only on failure and on code
   consumption, never on a plain page view.
3. **Never `transaction.commit()` or `savepoint()` inside the plugin.** Let the
   publisher commit. An explicit commit defeats the retry machinery and, worse, can
   half-commit a request that later aborts.
4. **Keep non-idempotent side effects out of the retried region.** A retry replays the
   *whole* request up to 4 times. An "account locked" notification email sent
   alongside the increment would go out up to 4 times. Send it from the same code
   path but guard it on the post-write state, or accept it.

### The actual hazard: `transaction.abort()`, not `ConflictError`

`ZPublisher/Publish.py`, `publish()`, exception path:

```python
finally:
    try:
        try:
            notify(PubBeforeAbort(request, exc_info, retry))
        finally:
            if transactions_manager:
                transactions_manager.abort()      # ◀── unconditional
```

**Any** request ending in an exception loses every ZODB write — and `Unauthorized` is
such an exception (`zpublisher_exception_hook` renders the view then explicitly
re-raises it: *"Re-raise Unauthorized to make sure it is handled correctly"*).

Consequences, and they are decisive:

- A failed-attempt increment written inside `authenticateCredentials` on a request
  that ends in `Unauthorized` **is silently discarded**. Lockout would never trigger
  on exactly the paths an attacker uses.
- A write inside `IChallengePlugin.challenge()` is discarded 100% of the time —
  `challenge()` is reached from `HTTPResponse.exception()`, which runs *after* the
  abort.
- The token form POST returns 200/302 with no exception → `PubBeforeCommit` →
  `commit()`. **This is the only reliable place to write second-factor state.**

**Therefore: all replay-window, attempt-counter and recovery-code writes belong in the
token form view, not in the PAS plugin.** This is not a style preference; a counter
written in the plugin is a lockout that does not lock out. It happens to line up
neatly: a *failed second factor* is submitted to the token form by definition.

### Silent-drop pitfall: `memberdata_properties.xml` is mandatory

`MutablePropertySheet.setProperties` **pops** keys not already in the sheet:

```python
for key, value in tuple(prop_update.items()):
    if key not in prop_keys:
        prop_update.pop(key)
        continue
    self.validateProperty(key, value)
```

An undeclared property is **silently discarded with no error**. Forget to add the new
properties to `profiles/default/memberdata_properties.xml` (which today declares only
`enable_two_factor_authentication` and `two_factor_authentication_secret`) and the
lockout counter simply never persists, with nothing in the log.

Type must be one PAS supports (`string`, `text`, `boolean`, `int`, `long`, `float`,
`lines`, `date`), enforced by `validateValue`. All the new state fits:

| State | Type | Note |
|---|---|---|
| last consumed TOTP interval (replay) | `int` | store the interval counter, compare `>` |
| consecutive failed attempts | `int` | |
| locked-until | `int` (epoch) or `date` | `int` avoids `DateTime` round-tripping |
| hashed recovery codes | `lines` | a tuple of hashed strings — no JSON blob needed |

Note `setPropertiesForUser` injects `'isGroup'` into the dict *after* the
`allowed_prop_keys` check, so `isGroup` appears in storage without being declared.
Harmless, but do not model anything on it.

Add a test that reads each new property back through `user.getProperty()` after a
`setMemberProperties()` — that is the check that catches a missing profile entry, and
it is the smallest thing that fails if the wiring breaks.

---

## 6. Reading the encryption key from the environment

### Where the env var actually becomes visible

`plone.recipe.zope2instance`'s `environment-vars` lands in `zope.conf` as an
`<environment>` block (confirmed in this checkout's
`parts/instance/etc/zope.conf:11-14`). `Zope2/Startup/handlers.py:127-129` applies it:

```python
# Set environment variables
for k, v in config.environment.items():
    os.environ[k] = v
```

and `Zope2/Startup/run.py` calls `_setconfig()` (which runs `handleConfig`) **before**
`starter.prepare()`, which is what imports products and loads ZCML. So under
`bin/instance` a module-import-time `os.getenv()` *would* see the value.

**It still must not be done at import time:**

- `bin/test` (`zope.testrunner`) never calls `_setconfig` and never reads
  `zope.conf`. A module-level `KEY = os.getenv(...)` is permanently `None` under
  tests, and a module global cannot be patched without `reload()`.
- The same applies to `bin/code-analysis`, `bin/instance debug` invoked oddly, and any
  script that imports the package without Zope's startup path.
- An import-time `raise` on a missing key makes the whole instance fail to start with
  a traceback from deep inside `import_products`, and makes the test runner unusable.
  Fail at *use* time, where you can produce a useful message and where only the 2FA
  feature breaks.

### Recommendation: per-call, plain function

```python
# helpers.py
def get_encryption_key():
    key = os.environ.get('GOOGLEAUTHENTICATOR_KEY')
    if not key:
        raise ValueError(
            'GOOGLEAUTHENTICATOR_KEY is not set; '
            'check environment-vars in the instance section of buildout')
    return key
```

- **Thread-safe.** `zserver-threads 2` in this project's `zope.conf`, so >1 worker
  thread is real. `os.environ` is a plain `dict` in CPython 2.7 and a read is a single
  bytecode under the GIL. No lock needed. Do not cache into a module global — that is
  the only way to introduce a race here.
- **Cheap.** A dict lookup plus `Fernet(key)` construction, which only splits the
  32-byte key into signing and encryption halves. Per-call is fine.
  **If a KDF is ever introduced** (PBKDF2 etc.), that becomes ~100 ms and must be
  memoised — cache keyed on the raw key string, never on nothing.
- **Testable.** `mock.patch.dict(os.environ, {'GOOGLEAUTHENTICATOR_KEY': ...})` — no
  `reload`, no layer surgery, works on the existing `INTEGRATION_TESTING` layer.
- **Matches the house pattern, deliberately diverging on one point.**
  `imio.helpers/__init__.py:44-55` reads `SSO_APPS_*` at module scope. That is fine for
  values that are optional and only used at request time; it is wrong for a key whose
  absence must produce a clear error and whose presence must be overridable in tests.
  Note the divergence in the plan so it does not read as an oversight.
- **No `zope.component` utility.** One implementation, no swap requirement, and
  `provideUtility` in tests buys nothing that `patch.dict` does not. An interface with
  a single implementation is exactly the abstraction to skip.

---

## 7. Data flow: a login that needs a second factor

```
Browser POST /login_form   __ac_name=alice  __ac_password=secret  ajax_load=…
    │
    ▼  ZPublisher.publish() → transactions_manager.begin() → request.traverse()
PAS.validate()
    │
    ├── extractor credentials_cookie_auth → {login:'alice', password:'secret', …}
    │       ├── google_auth.authenticateCredentials        ◀── FIRST, the veto
    │       │     is_whitelisted_client()? no
    │       │     alice.enable_two_factor_authentication == True
    │       │     verify 1st factor: source_users.authenticateCredentials → ok
    │       │     credentials.clear()               ◀── the veto
    │       │     request['_2fa_pending'] = sign_user_data(...)
    │       │     return None                        (no RESPONSE, no ZODB write)
    │       ├── session.authenticateCredentials({})         → None
    │       └── source_users.authenticateCredentials({})     → None
    │
    ├── extractor credentials_basic_auth → {} (no Authorization header this time)
    └── extractor session               → {} (no __ac cookie)
    │
    └── result == []  →  no user  →  anonymous
    ▼
CMFFormController: login_form → validate → logged_in.cpy
    isAnonymousUser() → True → expireCookie('__ac') → status='failure'
    → login_failed.cpt renders, HTTP 200            ◀── NO Unauthorized here
    ▼
notify(PubBeforeCommit)
    our subscriber: url = request.get('_2fa_pending') → set 302 + Location
    ▼
transactions_manager.commit()                       ◀── writes in this request live
    ▼
302 → XHR follows → GET @@google-authenticator-token?auth_user=alice&signature=…
    ▼
TokenForm renders  <form id="login_form">           ◀── overlay finds it
    drop_login_failed_msg(request)                     (the "Login failed" from
                                                        logged_in.cpy)
    ▼  overlay renders the token form in place; user types 123456; XHR POST
TokenForm.handleSubmit
    validate_user_data(request, user)      ska signature + browser hash
    check replay:  interval > last_consumed_interval  else reject
    validate_token(token, user)             onetimepass.valid_totp
    ├── invalid → attempts += 1; if attempts >= N: locked_until = now + T
    │             setMemberProperties(...)   ◀── COMMITS (200 response)
    │             re-render with error; overlay stays open
    └── valid   → last_consumed_interval = interval
                  attempts = 0
                  setMemberProperties(...)   ◀── COMMITS
                  session._setupSession(userid, RESPONSE)   ◀── ONLY grant point
                  redirect(validated next_url)
    ▼  no form#login_form in the response → noform() → 'reload'
location.replace(location.href)  → page reloads with __ac set. Logged in.
```

### The `Unauthorized` variant (deep link, expired session, basic auth)

```
GET /plone/private-page      [Authorization: Basic YWxpY2U6c2VjcmV0]
    ▼
PAS.validate()
    extractor credentials_basic_auth → {login:'alice', password:'secret', …}
        google_auth (first): 2FA on → verify 1st factor → credentials.clear()
                             request['_2fa_pending'] = signed_url → None
        session, source_users: see {} → None
    result == [] → anonymous → not authorized → raise Unauthorized
    ▼
publish(): err_hook renders, RE-RAISES Unauthorized
           finally: transactions_manager.abort()    ◀── any write here is LOST
    ▼
publish_module_standard → response.exception()
    issubclass(t, Unauthorized) → self._unauthorized()   (PAS-patched)
    ▼
PAS._unauthorized() → PAS.challenge(req, resp)
    chooser: browser request → no 'Browser' key → valid_protocols == []
    challengers in order:
      google_auth       → sees _2fa_pending → redirect(url, lock=1) → True
                          protocol := 'google_auth'
      credentials_cookie_auth (protocol 'credentials_cookie_auth') → SKIPPED
      credentials_basic_auth  (protocol 'http')                    → SKIPPED
                                                    ◀── the 401 is suppressed
    ▼
back in exception(): setStatus(401) → no-op, status is locked at 302
    ▼
302 → token form. Same tail as above.
```

For a `PROPFIND`/`PUT`/`HEAD` request the sniffer classifies it WebDAV,
`valid_protocols == ['http']`, our challenger is skipped, and
`credentials_basic_auth` returns a clean 401. Correct: no HTML redirect to a
non-browser client, and no authentication granted.

---

## 8. Build order and entanglements

```
 Rename  ──▶  B: PAS boundary  ──▶  C: memberdata state
 (first)      (the keystone)   │
                               └──▶  D: delete the overrides
 A: env key + seed encryption + local QR   (independent, start in parallel)
```

| # | Change | Depends on | Why / entanglement |
|---|---|---|---|
| **Rename** | `collective.*` → `imio.*` | — | Touches every file, so doing it first avoids rebasing every later diff. **Entangled with B**: it changes the PAS plugin id and `meta_type`, which is exactly what B's ordering assertion keys on. Do it before B, not after. |
| **A** | env-var key, Fernet seed encryption, local QR via `zint` | — | Fully independent of the PAS work. **Start it early anyway**: the key's `concat::fragment` is a change in the separate `industrialisation` repo, so it has the longest lead time of anything in the milestone. §6. |
| **B** | request flag + `IChallengePlugin` + `IPubBeforeCommit` subscriber + `movePluginsTop` + fail-closed `try/except` + the `credentials_basic_auth` extractor decision | Rename | **The keystone.** Closes the basic-auth bypass (§3) and establishes *where writes can and cannot happen* (§5), which C needs. Ships with the ordering assertion test and one veto test per extractor. |
| **C** | replay window, attempt counter + lockout, hashed recovery codes | **B** | B answers "which code paths commit". Writing these into the PAS plugin before B lands produces a lockout counter that is silently aborted on the `Unauthorized` path — a security control that does not work and looks like it does. Also needs `memberdata_properties.xml` entries or the writes vanish silently (§5). |
| **D** | delete `skins/`, `skins.xml`, the `popupforms.js` copy and its `jsregistry.xml` entries; add `id = 'login_form'` to `TokenForm` | Loosely **B** | Mechanically independent of B — `id="login_form"` works with the redirect wherever it lives. **The real entanglement is `came_from`**: the stale `login_form.cpt` copy *deleted* Plone 4.3.20's `came_from` hidden input, which is why `CameFromAdapter` exists. Deleting the copy restores the field and changes what `ICameFrom` sees, so D must land together with the `next_url` open-redirect fix at `token.py:112-113`. Sequence D after B so the overlay is only exercised against the final redirect mechanism. |

**Not entangled, do not let them be sequenced together:** A ↔ B/C/D share no code.
A can run in a parallel workstream.

**Phases likely to need their own research:** none of the above. Every mechanism is
pinned to a file:line in an installed egg. The two open verification items are
implementation-time browser tests, not research: `ska` tolerance of the injected
`ajax_load` parameter, and `common_content_filter` reaching the wrapped z3c.form
(§4).

---

## 9. Anti-patterns to retire, and one to keep

### Retire: response side effects inside `authenticateCredentials`

**What:** `pas_plugin.py:139-153` mutates `RESPONSE` (clears `__ac`, issues a
`redirect(..., lock=1)`) from a method contracted to return
`(userid, login) | None`.
**Why it's wrong:** it is not merely impure — it is a *refusal that does not refuse*
(§3 Vector 2), and it is unreachable-by-design on the only path where PAS provides a
redirect hook. It also puts the redirect where a ZODB write would be aborted (§5).
**Instead:** decide in `authenticateCredentials`, redirect in
`IChallengePlugin.challenge` for the `Unauthorized` path and in an
`IPubBeforeCommit` subscriber for the login-form POST path.

### Retire: an undocumented ordering incantation as a security control

**What:** `movePluginsDown(interface, listPlugins(interface)[:-1])`.
**Why it's wrong:** the entire second-factor guarantee rests on the resulting
position, and nothing states that, tests it, or restores it.
**Instead:** `movePluginsTop(interface, [plugin.getId()])` plus a test asserting
`listPluginIds(IAuthenticationPlugin)[0] == PAS_ID`. The test is the control.

### Retire: full-file skin and resource overrides

**What:** a 310-line `login_form.cpt` and a 197-line `popupforms.js`, both to
suppress one `prepOverlay` call.
**Why it's wrong:** last-profile-wins collision with `imio.dms.mail`, and both copies
have silently frozen Plone at a pre-4.3.20 state, reverting fixes (§4).
**Instead:** `id = 'login_form'` on `TokenForm`.

### Retire: fail-open exception handling in the plugin

**What:** relying on PAS to swallow `KeyError`/`AttributeError`.
**Why it's wrong:** an exception in the 2FA plugin removes the 2FA plugin, which is
the definition of fail-open.
**Instead:** `except Exception: credentials.clear(); log; return None`.

### Keep: mutating the credentials dict

**What:** `for key in credentials.keys(): del credentials[key]`.
`.planning/codebase/ARCHITECTURE.md` flags it as a design compromise. It is, but it is
**the only veto PAS 1.11.3 offers** (§1) — verified against all 22 plugin interfaces.
Keep it, move it to the top of the 2FA branch so it also runs on the exception path,
and replace the apologetic comment with a citation:
`PluggableAuthService.py:648-675` accumulates every authenticator's result, so
returning `None` vetoes nothing.

---

## 10. Scaling

Not the axis that matters for this package — iMio sites are a few thousand users and
the milestone is capped by a 1–2 year lifespan. The only load-relevant findings:

| Concern | Reality |
|---|---|
| memberdata write per failed attempt | Per-user `OOBTree` bucket; cross-user writes merge; same-user writes retry 3×. Fine at any scale iMio will see. §5 |
| Extra request work in the plugin | One `request.get()` in the `IPubBeforeCommit` subscriber, on every request. Negligible. |
| `Fernet(key)` per call | Key split only, no KDF. Negligible — **unless** a KDF is introduced, in which case memoise. §6 |
| Bulk enable across all users | Already out of scope in PROJECT.md; nothing here changes that. |

---

## Sources

All primary source, read from the eggs `bin/instance` resolves:

- `Products.PluggableAuthService-1.11.3` — `PluggableAuthService.py` (`validate` :240,
  `_extractUserIds` :577, `_findUser` :760, `_authorizeUser` :866,
  `__before_publishing_traverse__` :1058, `_unauthorized` :1140, `challenge` :1152),
  `interfaces/plugins.py` (all 22 interfaces; `IChallengePlugin` :99-129),
  `plugins/HTTPBasicAuthHelper.py`, `plugins/CookieAuthHelper.py`,
  `plugins/ChallengeProtocolChooser.py`, `plugins/RequestTypeSniffer.py`
- `Products.PluginRegistry-1.4.1` — `PluginRegistry.py` (`activatePlugin`,
  `movePluginsTop`, `movePluginsUp`, `movePluginsDown`, `listPlugins`)
- `Zope2-2.13.30` — `ZPublisher/Publish.py` (`publish`, abort/retry),
  `ZPublisher/HTTPResponse.py` (`redirect`, `setStatus`, `exception`, `_unauthorized`),
  `ZPublisher/HTTPRequest.py` (`retry_max_count`, `supports_retry`, `retry`),
  `Zope2/App/startup.py` (`ZPublisherExceptionHook`),
  `Zope2/Startup/run.py` + `Zope2/Startup/handlers.py:127-129` (`<environment>`)
- `Products.PlonePAS-5.1.1` — `setuphandlers.py:195-244` (default `acl_users`),
  `setuphandlers.py:350-385` (`challenge_chooser_setup`), `config.py:5-10`
  (`DEFAULT_PROTO_MAPPING`), `plugins/property.py`
  (`ZODBMutablePropertyProvider`, `OOBTree` storage, `setPropertiesForUser`),
  `plugins/ufactory.py` (`PloneUser.setProperties`), `sheet.py`
  (`MutablePropertySheet.setProperties` silent pop), `plugins/cookie_handler.py`
- `Products.CMFPlone-4.3.20` — `skins/plone_login/login_form.cpt` + `.metadata`,
  `logged_in.cpy` + `.metadata`, `login_next.cpy`,
  `skins/plone_ecmascript/popupforms.js:76-98`
- `plone.session-3.5.6` — `plugins/session.py` (`extractCredentials`,
  `authenticateCredentials`, `_setupSession`)
- `plone.app.jquerytools-1.9.5` — `browser/overlayhelpers.js`
  (`prep_ajax_form` success/noform/redirect switch, `remove_overlay`, `add_ajax_load`)
- This checkout — `parts/instance/etc/zope.conf` (`zserver-threads 2`,
  `<environment>`), `src/collective/googleauthenticator/pas_plugin.py`,
  `setuphandlers.py`, `browser/forms/token.py`,
  `profiles/default/memberdata_properties.xml`, `profiles/default/jsregistry.xml`,
  and `diff` of both vendored overrides against CMFPlone 4.3.20
- `imio.helpers-1.3.15` — `imio/helpers/__init__.py:44-55` (existing env-var pattern)

---
*Architecture research for: Plone 4.3 PAS second-factor plugin*
*Researched: 2026-07-28*
