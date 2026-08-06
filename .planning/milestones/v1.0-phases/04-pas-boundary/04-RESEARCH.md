# Phase 4: PAS Boundary - Research

**Researched:** 2026-07-31
**Domain:** Zope 2 `ZPublisher`/`Products.PluggableAuthService` request lifecycle; PAS plugin ordering and challenge protocol
**Confidence:** HIGH (every mechanical claim below was traced in the exact eggs this buildout resolves, not from memory)

No `CONTEXT.md` exists for this phase (the user elected to skip `/gsd-discuss-phase`). This research
is therefore the primary evidence base for the phase's one open decision (basic-auth deactivation).
There is no `## User Constraints` section to reproduce as a result — the constraints that exist are
ROADMAP.md's phase notes and REQUIREMENTS.md's MFA-01..04/COEX-08/DOC-01/DOC-02, both read in full
before this research and treated as fixed inputs below.

## Summary

Every mechanism this phase depends on was read from the *installed* eggs this buildout actually
resolves — `Products.PluggableAuthService==1.11.3`, `Products.PluginRegistry==1.4.1`,
`Zope2==2.13.30` — not from general PAS knowledge, because the phase's own success criteria are
literally "read the loop and confirm X." All eight research-priority questions came back with a
concrete file:line answer; none required a web search. There are no new third-party packages in
this phase, so there is no Package Legitimacy Audit to run — the phase is pure standard-library/eggs
plumbing on top of the four modules already at the center of the codebase
(`pas_plugin.py`, `setuphandlers.py`, `helpers.py`, `browser/forms/token.py`).

The chain that makes the veto work is: `PluggableAuthService._extractUserIds` calls every
`IAuthenticationPlugin.authenticateCredentials(credentials)` **in plugin order**, in a loop that
passes the **same dict object** to each call and never breaks on success — so wiping `credentials`
in place inside our plugin genuinely blinds every authenticator listed *after* ours in that same
call, and does nothing for ones listed before it. That is why plugin order is not a nicety here, it
*is* the security control (`PluggableAuthService.py:648-667`), and why `movePluginsTop` (which
exists, with exactly the signature the roadmap assumes, in `Products.PluginRegistry==1.4.1`) has to
replace the current `movePluginsDown(iface, listPlugins(iface)[:-1])` idiom in `setuphandlers.py`.

The redirect-body-leak bug (MFA-02) has a precise root cause: `HTTPResponse.redirect(url, lock=1)`
is two lines — `setStatus(302, lock=1)` and `setHeader('Location', url)` — and locking the status
only blocks a *later* `setStatus()` call from changing the numeric code; it does nothing to the
response body (`ZPublisher/HTTPResponse.py:606-611`, `:204-239`). Because `authenticateCredentials`
runs during traversal/authorization, *before* `mapply()` renders the requested view and calls
`response.setBody(result)` (`ZPublisher/Publish.py:127-141`), any redirect issued from
`authenticateCredentials` gets its Location header and locked 302 status, and then the originally
requested page's HTML is rendered into the body anyway right afterward — exactly the leak the
roadmap describes, and exactly what the current `pas_plugin.py:169` line does today. Fixing it means
never rendering the original view at all (challenge path) or overwriting the body after it renders
(`IPubBeforeCommit` path) — `response.redirect()` alone, on its own, fixes neither.

`IPubBeforeCommit` fires *after* `mapply()`/`setBody()` and *before* `transactions_manager.commit()`
and before the body is ever flushed to the client (`Publish.py:134-146`, confirmed again by
`publish_module_standard`'s `outputBody()` call happening only after `publish()` returns,
`Publish.py:264-267`) — so a subscriber there genuinely can still overwrite status, headers and
body; `plone.transformchain`, already in this buildout's egg cache, does precisely this in
production (`plone/transformchain/zpublisher.py:81-96`) and is the concrete pattern to copy.
`IChallengePlugin.challenge()`, by contrast, is reached only after an `Unauthorized` exception has
propagated all the way out of `publish()`, and `publish()`'s own exception handling runs
`transactions_manager.abort()` in a `finally:` block *before* re-raising
(`Publish.py:187-198`/`:213-222`) — so by the time `response.exception()` calls PAS's
`_unauthorized()` → `challenge()` (`HTTPResponse.py:789-800`, `PluggableAuthService.py:1140-1192`),
the transaction for that request is already gone. Any write inside `challenge()` is discarded, full
stop; this is not a timing race, it is a hard ordering guarantee in the publisher.

The `credentials_basic_auth` deactivation decision: three sibling iMio repos were searched
(`imio.dms.mail`, `server.dmsmail`, `industrialisation`) and turned up no live dependency on HTTP
Basic Auth *against this Plone site's own `acl_users`*. `server.dmsmail`'s only `webdav-address`
setting is commented out in every buildout config found, no XML-RPC client targeting the site was
found, and the one script that does use HTTP Basic Auth with `requests`
(`scripts/run-copy-missing-blobs.py`) authenticates *outward* to a different, remote "source" site,
not into this one. The one script that does Basic-Auth into *this* Zope process
(`pack_zeo.sh`, from `industrialisation`) targets `/Control_Panel/Database/.../manage_pack` — the
Zope-root `Control_Panel`, which sits above any Plone site's `acl_users` and is exactly the
DOC-01 "architecturally out of reach" boundary, so it is unaffected by this site's PAS
configuration either way. This is real but not literally exhaustive evidence (three repos, not
every iMio repo); see Assumptions Log A1.

**Primary recommendation:** Fix the ordering with `movePluginsTop` (structural, required regardless
of the basic-auth decision), keep `authenticateCredentials` write-free of `RESPONSE`, split the
actual redirect into an `IChallengePlugin.challenge()` (Unauthorized path, no writes, no `protocol`
attribute set) and an `IPubBeforeCommit` subscriber (login-POST path, explicit `setBody('')` after
`redirect()`/before returning), and **additionally** deactivate `credentials_basic_auth` site-wide as
defense in depth, since the ordering fix alone is correct but silently reversible by any future
plugin reorder, while deactivation removes the vulnerable code path structurally.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Password verification delegation | API/Backend (PAS plugin) | — | `authenticateCredentials` already delegates to other `IAuthenticationPlugin`s; this phase does not change that delegation, only what happens after it |
| Credentials-dict veto | API/Backend (PAS plugin) | — | In-process mutation of a shared dict inside the single Zope publish cycle; no ZODB, no cookie, no cross-request state |
| 2FA-pending signal | API/Backend (`request` attribute) | — | `request['_2fa_pending']` is per-request, set in `authenticateCredentials`, read by the challenge plugin and the pub-event subscriber later in the *same* request — never persisted |
| Unauthorized-path redirect | API/Backend (`IChallengePlugin`) | — | Reached only from `HTTPResponse.exception()`, after `transaction.abort()`; must be write-free by construction, not by discipline |
| Login-POST-200 redirect | API/Backend (`IPubBeforeCommit` subscriber) | — | Reached from the success path of `ZPublisher.Publish.publish`, before commit; the only hook that can intervene on a request that never raises |
| Plugin ordering | API/Backend (GenericSetup install handler) | — | `Products.PluginRegistry.movePluginsTop`, invoked once at install time from `setuphandlers.py`; not a per-request concern |
| Basic-auth extractor policy | API/Backend (PAS plugin registry) | — | Site-wide toggle on `acl_users.plugins`, decided once, not per-request |
| Documentation of the Zope-root/basic-auth boundary | Docs (README.rst) | — | No code tier; DOC-01/DOC-02 are prose requirements |

## Standard Stack

No new third-party dependency is introduced by this phase. Every API used already ships inside
eggs this buildout resolves:

### Core (already in the resolved environment — no install step)

| Component | Resolved version (this buildout) | Purpose | Evidence |
|-----------|-----------------------------------|---------|----------|
| `Products.PluggableAuthService` | 1.11.3 | `_extractUserIds`, `IAuthenticationPlugin`, `IChallengePlugin`, `_unauthorized`/`challenge` | `[VERIFIED: /srv/src/imio.googleauthenticator/parts/omelette/Products/PluggableAuthService -> /srv/cache/eggs/Products.PluggableAuthService-1.11.3-py2.7-linux-x86_64.egg]` |
| `Products.PluginRegistry` | 1.4.1 | `movePluginsTop`/`movePluginsUp`/`movePluginsDown`/`activatePlugin`/`listPlugins` | `[VERIFIED: /srv/src/imio.googleauthenticator/parts/omelette/Products/PluginRegistry -> /srv/cache/eggs/Products.PluginRegistry-1.4.1-py2.7-linux-x86_64.egg]` |
| `Zope2` (`ZPublisher`) | 2.13.30 | `IPubBeforeCommit`/`IPubEvent` interfaces, `Publish.publish`, `HTTPResponse.exception`/`redirect` | `[VERIFIED: /home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg]` |
| `zope.event`/`zope.component` | (transitive, already installed) | `notify(PubBeforeCommit(...))`, `@adapter(IPubBeforeCommit)` subscriber registration | `[VERIFIED: Publish.py:28,30-31]` |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| `IPubBeforeCommit` subscriber for the login-POST redirect | `IPubSuccess`/`IPubAfterTraversal` | `IPubSuccess` fires *after* `transactions_manager.commit()` (`Publish.py:146-149`) — any body mutation there is too late to affect what was already committed/about to be sent, and the phase notes' own framing ("never raises... returns 200") matches the pre-commit hook, not post-commit. `IPubAfterTraversal` fires before `mapply()` even runs (`Publish.py:129`), i.e. before the login_form view has produced anything to overwrite — using it would mean re-implementing the view dispatch, not intercepting its output. `IPubBeforeCommit` is the only one of the three that sees the rendered body and can still change it before anything is sent or committed. |
| Deactivating `credentials_basic_auth` | Leaving it active and relying solely on `movePluginsTop` ordering | Ordering-only is correct today but order-*dependent*: a future add-on install, a ZMI plugin-list edit, or a GenericSetup re-run that reorders `IAuthenticationPlugin` silently reopens the basic-auth bypass with no error and no log line — the same "silent" failure mode ROADMAP.md calls out as this project's dominant risk category. Deactivation removes the code path outright, independent of order, at the cost of site-wide Basic Auth for every user (2FA or not). |

**Installation:** None — no new packages.

## Package Legitimacy Audit

Not applicable. This phase adds zero new third-party packages; it modifies internal usage of
already-approved, already-pinned eggs (`Products.PluggableAuthService`, `Products.PluginRegistry`,
`Zope2`). **Packages removed due to `[SLOP]` verdict:** none. **Packages flagged as suspicious
`[SUS]`:** none.

## Architecture Patterns

### System Architecture Diagram — two independent redirect triggers, one shared signal

```
                     ┌─────────────────────────────────────────────┐
                     │        authenticateCredentials()             │
   request arrives──▶│  (whitelist? 2FA enabled? password OK       │
   (POST form OR      │   via delegation to other auth plugins?)     │
   Authorization:      │  -- decides only, never touches RESPONSE --  │
   Basic header)       │  wipe credentials dict in place              │
                     │  set request['_2fa_pending'] = True          │
                     │  return None                                 │
                     └───────────────┬───────────────────────────────┘
                                     │
                     ┌───────────────┴────────────────┐
                     │  what happens next depends on   │
                     │  whether the requested resource  │
                     │  needs authorization             │
                     └───────┬───────────────────┬──────┘
                             │                   │
              resource needs auth,        resource is login_form
              wiped creds => anonymous     itself (publicly viewable):
              can't view it => Unauthorized  mapply() runs normally,
              raised during traversal        renders "login failed"-ish
                             │                200 body
                             ▼                   │
              publish()'s except: block           ▼
              -> transaction.abort() (Publish.py:187-198)   notify(PubBeforeCommit)
              -> re-raise -> publish_module_standard         (Publish.py:143, BEFORE
              -> response.exception()                        commit, BEFORE flush)
              -> self._unauthorized() (PAS)                        │
              -> pas.challenge(req, resp)                          ▼
              -> for each IChallengePlugin:                 subscriber checks
                   challenger.challenge(req, resp)           request['_2fa_pending']
                     │                                               │
                     ▼                                               ▼
        our IChallengePlugin.challenge():             response.redirect(signed_url)
        if request['_2fa_pending']:                    response.setBody('')  <- REQUIRED,
          response.redirect(signed_url)                 redirect() alone does NOT clear
          return True   (no ZODB write --                the body mapply() already set
           transaction already aborted)                         │
                                                                 ▼
                                                     client gets 302, empty body,
                                                     Location: @@google-authenticator-token
```

### Recommended Project Structure

No new files/folders. Changes land in the existing four modules:

```
src/imio/googleauthenticator/
├── pas_plugin.py          # authenticateCredentials trimmed to decide-only;
│                           # NEW: challenge() method (IChallengePlugin)
├── setuphandlers.py        # _add_plugin(): movePluginsTop replaces movePluginsDown;
│                           # optionally deactivate credentials_basic_auth
├── subscribers.py           # NEW (or reuse tests/test_subscribers.py's existing
│                           # module if one already exists outside tests/) --
│                           # IPubBeforeCommit handler + its subscriber ZCML
├── helpers.py               # unchanged by this phase, referenced for sign_user_data
└── configure.zcml           # <subscriber handler=".subscribers.xxx" /> added
```

### Pattern 1: Decide/redirect/grant split

**What:** `authenticateCredentials` only decides (whitelist, 2FA flag, password delegation, wipe,
set a request-scoped flag) and returns `None`. It never calls `response.redirect`/`setCookie` and
never writes to the ZODB. The actual HTTP-level redirect happens later, in one of two independent
hooks, driven by the flag it set.
**When to use:** Any PAS plugin that needs a multi-step (first factor, then second factor) flow
inside a protocol (PAS `authenticateCredentials`) that offers no "pause and redirect" primitive of
its own.
**Example (challenge plugin, write-free):**
```python
# Source: Products.PluggableAuthService.PluggableAuthService.PluggableAuthService.challenge
# (PluggableAuthService.py:1152-1192) -- confirms the calling contract:
# challenge(request, response) -> bool, called once per IChallengePlugin in listing order,
# only for challengers whose (possibly-defaulted-to-plugin-id) `protocol` matches the winning one.
from Products.PluggableAuthService.interfaces.plugins import IChallengePlugin

class GoogleAuthenticatorPlugin(BasePlugin):
    # Deliberately NOT set: protocol = 'http'. Leaving `protocol` undeclared means
    # PAS's getattr(challenger, 'protocol', challenger_id) falls back to this
    # plugin's own id ('google_auth') -- a protocol string no other challenger
    # shares, so this challenge() only ever competes with itself, and non-browser
    # request types (WebDAV/FTP/XML-RPC, restricted to 'http' by PAS's
    # IChallengeProtocolChooser/IRequestTypeSniffer machinery) skip it entirely
    # (PluggableAuthService.py:1180: "if valid_protocols and challenger_protocol
    # not in valid_protocols: continue").
    def challenge(self, request, response):
        if not request.get('_2fa_pending'):
            return False  # decline; let other challengers (cookie/basic) fire
        signed_url = sign_user_data(request=request, user=..., url='@@google-authenticator-token')
        response.redirect(signed_url)
        return True
```
**Example (IPubBeforeCommit subscriber, real production pattern already in this buildout):**
```python
# Source: plone.transformchain 1.2.2, plone/transformchain/zpublisher.py:81-96
# (already resolved in this buildout's egg cache) -- proves setBody() at this
# event genuinely takes effect, since this is the mechanism Plone's own resource
# registries/diazo theming rely on in production.
from zope.component import adapter
from ZPublisher.interfaces import IPubBeforeCommit

@adapter(IPubBeforeCommit)
def redirect_pending_2fa(event):
    request = event.request
    if not request.get('_2fa_pending'):
        return
    response = request.response
    signed_url = sign_user_data(request=request, user=..., url='@@google-authenticator-token')
    response.redirect(signed_url)
    # REQUIRED: mapply() already ran and called response.setBody(result) with the
    # rendered login_form (Publish.py:134-141), *before* this event fires
    # (Publish.py:143). redirect() alone only sets status+Location
    # (HTTPResponse.py:606-611) -- it does not touch the body. Omitting this line
    # reproduces MFA-02 exactly.
    response.setBody('')
```
ZCML registration (same shape as `plone.transformchain/configure.zcml`):
```xml
<subscriber handler=".subscribers.redirect_pending_2fa" />
```

### Anti-Patterns to Avoid

- **Redirecting from inside `authenticateCredentials`:** `response.redirect(url, lock=1)`
  (`pas_plugin.py:169` today) only locks the *status code*, not the body — `mapply()` still runs
  and still calls `response.setBody(result)` with the full protected page for any resource whose
  authorization doesn't itself raise `Unauthorized`. This is the literal MFA-02 bug.
- **Setting `protocol = 'http'` on the challenge plugin:** `HTTPBasicAuthHelper.protocol = "http"`
  (`plugins/HTTPBasicAuthHelper.py:64`). Per the `IChallengePlugin` interface docstring, "plugins
  operating under the same protocol will all be given an attempt to fire" — sharing `'http'` means
  our challenge and Basic Auth's 401 challenge both run for the same request, and PAS's
  `IChallengeProtocolChooser`/`IRequestTypeSniffer` machinery routes WebDAV/FTP/XML-RPC requests to
  exactly the `'http'` protocol group, so they would receive our HTML redirect instead of (or mixed
  with) a clean 401.
- **Raising `zExceptions.Redirect` from an event subscriber to force a redirect:** `Redirect` is
  handled specially only inside `publish()`'s own exception machinery
  (`Zope2/App/startup.py:190-191`, `HTTPResponse.py:811-817`), which also runs
  `transactions_manager.abort()` — the opposite of "returns HTTP 200 and never raises" the phase
  requires for the login-POST path.
- **Trusting `movePluginsDown(iface, listPlugins(iface)[:-1])` to mean "first":** it achieves the
  same *end state* today only because the plugin being ordered was the most-recently-appended (hence
  last) entry — an implementation accident of `activatePlugin`'s append-only behavior
  (`Products/PluginRegistry/PluginRegistry.py:150-151`), not an assertion of intent. `movePluginsTop`
  says what it means.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Moving a plugin to position 0 in a `PluginRegistry` list | A custom `list.index`/`list.insert` dance in `setuphandlers.py` | `pas.plugins.movePluginsTop(interface, [plugin_id])` | Already exists, already handles multi-id reordering correctly, already the documented API (`Products/PluginRegistry/PluginRegistry.py:166-177`) |
| Intercepting a response after the view rendered but before it is sent | A custom `WSGI`/ZServer middleware, or monkeypatching `HTTPResponse` | `zope.component.adapter(IPubBeforeCommit)` subscriber | `ZPublisher` already notifies this event at exactly the right point in every request (`Publish.py:143`); `plone.transformchain` proves the pattern works in production in this exact buildout |
| Detecting "did an Unauthorized-triggering request happen" to redirect cleanly | Wrapping every view/`__call__` in a try/except | `IChallengePlugin.challenge()` | This is the protocol PAS designed for exactly this; it is reached automatically for every `Unauthorized`, with no need to guess which view raised it |

**Key insight:** Nothing in this phase needs new abstraction. It needs precise use of three PAS/
ZPublisher extension points that already exist for exactly this purpose, and removing one line
(`response.redirect(...)` inside `authenticateCredentials`) that pre-empts all three.

## Common Pitfalls

### Pitfall 1: Assuming `return None` vetoes a later plugin's success
**What goes wrong:** A developer reads `authenticateCredentials` returning `None` as "authentication
failed, stop here," and assumes that is enough to block 2FA-enabled users.
**Why it happens:** `None` does mean "this plugin didn't authenticate," but PAS's outer loop
(`_extractUserIds`, `PluggableAuthService.py:648-667`) calls **every** `IAuthenticationPlugin` for
the same extracted credentials and accumulates every non-`None` result into `user_ids`/`result`; it
never stops at the first success either. A `None` from our plugin changes nothing about what
`source_users` (or any other authenticator) independently returns for the *same, unmodified*
credentials dict.
**How to avoid:** The only observable effect our plugin can have on later authenticators in the
*same* `for authenticator_id, auth in authenticators:` loop iteration is mutating the shared
`credentials` dict object in place — which is exactly what the code already does
(`pas_plugin.py:148-149`) and exactly why ordering (this plugin listed *before* `source_users`)
is required for the mutation to reach it.
**Warning signs:** A veto test that passes only because the test's plugin list happens to already
be ordered correctly, with no explicit ordering assertion — this is precisely what MFA-03 exists to
catch.

### Pitfall 2: Believing a lock on status locks the body
**What goes wrong:** `response.redirect(url, lock=1)` reads as "make this redirect final," and a
reviewer assumes the response is now closed to further changes.
**Why it happens:** `lock` really does prevent a *later* `setStatus()` call from overwriting the
302 (`HTTPResponse.py:211-214`) — that part of the mental model is correct. What's missing is that
`setBody()` has no such lock at all, and nothing in the redirect call path ever calls it.
**How to avoid:** Either don't let `mapply()` run against the original view at all (challenge-path
early exit) or explicitly `setBody('')` after the redirect (pub-event path).
**Warning signs:** A manual `curl` (no `-L`) against a 2FA-gated URL returning a 302 with a
non-empty body containing recognizable page content.

### Pitfall 3: Writing state inside the challenge plugin because "it feels like the right place"
**What goes wrong:** A lockout counter, a "challenge issued" flag, or any `setMemberProperties` call
placed inside `challenge()` because that's where the redirect logic naturally lives.
**Why it happens:** `challenge()` has a `response` argument and looks like a normal view-ish
callable.
**How to avoid:** Remember the calling context: `challenge()` runs only after
`transactions_manager.abort()` has already executed for this request (`Publish.py:194`/`:218`,
confirmed by the fact that `err_hook`'s `finally:` block runs the abort *before* re-raising, which
is what eventually reaches `response.exception()` → `challenge()`). Any write here is thrown away
100% of the time, silently — no exception, no log line, just a lockout that never locks. This is
explicitly why MFA-12 (Phase 5) requires all second-factor state writes to live in the token form
view, and this phase's `challenge()`/subscriber must stay write-free from day one so Phase 5 doesn't
have to retrofit it.

### Pitfall 4: Assuming a `plone.testing.z2.Browser` test proves the veto held
**What goes wrong:** A `Browser` POST to `login_form` with a 2FA user's credentials "looks" like the
strongest possible test, so the PAS-level plugin-order assertion (MFA-03) gets skipped as redundant.
**Why it happens:** An end-to-end browser test does exercise the real HTTP path, which is valuable,
but `zope.testbrowser`-family browsers may auto-follow redirects by default, silently hiding whether
the pre-redirect body was non-empty (MFA-02) unless redirect-following is explicitly disabled for
that one assertion.
**How to avoid:** Use the existing unit-level idiom (`self.pas._extractUserIds(request,
self.pas.plugins)` with `setRequest(request)` bound, as in
`tests/test_pas_plugin.py:138-193`) for the "no session granted" assertions per extractor (MFA-04),
which exercises PAS's real loop without going through full HTTP publish, and reserve the
`Browser`-based test specifically for the body-emptiness and redirect-target assertions where a real
`HTTPResponse` is unavoidable.
**Warning signs:** A `Browser`-based veto test that passes today for the wrong reason (e.g. the
2FA-enabled user's password was simply wrong in the test fixture, or the browser followed the
redirect to a page that also happens to render "please log in").

## Code Examples

### Confirmed authenticator-accumulation loop (Q1)
```python
# Source: Products.PluggableAuthService.PluggableAuthService, installed egg
# Products.PluggableAuthService-1.11.3-py2.7-linux-x86_64.egg,
# PluggableAuthService.py:648-667 (inside _extractUserIds)
user_ids = []
for authenticator_id, auth in authenticators:
    try:
        uid_and_info = auth.authenticateCredentials(credentials)
        if uid_and_info is None:
            continue
        user_id, info = uid_and_info
    except _SWALLOWABLE_PLUGIN_EXCEPTIONS:
        reraise(auth)
        msg = 'AuthenticationPlugin %s error' % (authenticator_id, )
        logger.debug(msg, exc_info=True)
        continue
    if user_id is not None:
        user_ids.append((user_id, info))
```
Confirms: (a) `credentials` is the same dict object passed to every authenticator in this loop —
in-place mutation by an earlier plugin is observed by a later one; (b) there is no `break` on
success — every authenticator gets called and every non-`None` result is appended; (c) `return None`
from one plugin has zero effect on any other plugin's independent result.

### Confirmed `ZCacheable_get` gating (Q2)
```python
# Source: Zope2 2.13.30, OFS/Cache.py:150-168
def ZCacheable_get(self, view_name='', keywords=None, mtime_func=None, default=None):
    c = self.ZCacheable_getCache()
    if c is not None and self.__enabled:
        ...
    return default
```
`ZCacheable_getCache()` returns `None` unless a `ZCacheManager` object has been added *and*
associated via `ZCacheable_setManagerId` (`OFS/Cache.py:104-135`). Plone 4.3's default `acl_users`
carries no such association, so `_extractUserIds`'s `user_ids = self.ZCacheable_get(...)` call
(`PluggableAuthService.py:641-644`) always returns the `default=None`, and the full authenticator
loop always executes on every request. For a bypass to be cacheable at all, an operator would first
have to add a `ZCacheManager`, associate it with `acl_users`, and have a prior *successful*
authentication already cached under the same login+password+extractor keywords (`ZCacheable_set` is
only called `if user_ids:`, i.e. only on a non-empty/successful result,
`PluggableAuthService.py:669-673`) — at which point enabling 2FA for that user *after* the cache
entry was written would go unenforced until the cache manager's own timeout. This is a real,
if currently dormant, hazard worth the one-line comment the roadmap already calls for.

### Confirmed `IChallengePlugin` reachability, post-abort (Q3)
```python
# Source: Zope2 2.13.30, ZPublisher/Publish.py:143-222 (abridged)
result = mapply(object, request.args, request, call_object, 1, ...)
if result is not response:
    response.setBody(result)
notify(PubBeforeCommit(request))          # <- our IPubBeforeCommit subscriber runs HERE
if transactions_manager:
    transactions_manager.commit()
...
except:                                    # <- Unauthorized lands here
    exc_info = sys.exc_info()
    ...
    if not debug and err_hook is not None:
        try:
            return err_hook(...)           # Zope2.App.startup: re-raises Unauthorized after
                                            # rendering it (startup.py:233-238, :277-282)
        finally:
            try:
                notify(PubBeforeAbort(request, exc_info, retry))
            finally:
                if transactions_manager:
                    transactions_manager.abort()   # <- ALREADY RUN before the exception
                                                     #    finishes propagating
```
The re-raised `Unauthorized` propagates out of `publish()` into `publish_module_standard`'s own
`except:` block, which calls `request.response.exception()`
(`Publish.py:257-261`), which does `if issubclass(t, Unauthorized): self._unauthorized()`
(`HTTPResponse.py:799-800`). PAS's `__before_publishing_traverse__` hook has already monkeypatched
`response._unauthorized = self._unauthorized` (`PluggableAuthService.py:1058-1067`) for this
request, so this calls `PluggableAuthService._unauthorized` (`:1140-1150`) → `self.challenge(req,
resp)` (`:1152-1192`), which iterates `IChallengePlugin`s. All of this — abort, then challenge — is
strictly sequential in that order; there is no interleaving.

### Confirmed protocol-group semantics (Q3, continued)
```python
# Source: PluggableAuthService.py:1172-1192
for challenger_id, challenger in challengers:
    challenger_protocol = getattr(challenger, 'protocol', challenger_id)
    if valid_protocols and challenger_protocol not in valid_protocols:
        continue
    if protocol is None or protocol == challenger_protocol:
        if challenger.challenge(request, response):
            protocol = challenger_protocol
```
`BasePlugin` (our superclass) declares no `protocol` attribute, so `getattr(self, 'protocol',
challenger_id)` falls back to `challenger_id` — this plugin's own id (`google_auth`), a string no
other registered challenger shares. `HTTPBasicAuthHelper.protocol = "http"`
(`plugins/HTTPBasicAuthHelper.py:64`) is the one plugin that *does* declare a shared protocol; not
setting `protocol` on our plugin keeps us out of that group entirely, and PAS's
`ChallengeProtocolChooser`/`IRequestTypeSniffer` machinery is what restricts WebDAV/FTP/XML-RPC
request types to the `'http'` protocol group in the first place
(`plugins/ChallengeProtocolChooser.py:103-118`).

### Confirmed `movePluginsTop` (Q6)
```python
# Source: Products.PluginRegistry 1.4.1, PluginRegistry.py:166-177
def movePluginsTop(self, plugin_type, ids_to_move):
    ids = list(self._getPlugins(plugin_type))
    indexes = list(map(ids.index, ids_to_move))
    indexes.sort()
    for i1 in indexes:
        ids.insert(0, ids.pop(i1))
    self._plugins[plugin_type] = tuple(ids)
```
Signature: `movePluginsTop(plugin_type, ids_to_move)` where `ids_to_move` is a list of plugin ids
(not tuples). Confirmed resolved by this buildout (`parts/omelette/Products/PluginRegistry ->
Products.PluginRegistry-1.4.1-py2.7-linux-x86_64.egg`). The correct `setuphandlers.py` idiom:
```python
pas.plugins.movePluginsTop(interface, [plugin.getId()])
```
in place of the current:
```python
# setuphandlers.py:47-51 (today)
pas.plugins.movePluginsDown(
    interface,
    [x[0] for x in pas.plugins.listPlugins(interface)[:-1]],
)
```
The exact assertion for "first among `IAuthenticationPlugin`":
```python
self.assertEqual(
    self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0], PAS_ID)
```

### Testing idiom already established in this package (Q8)
```python
# Source: src/imio/googleauthenticator/tests/test_pas_plugin.py:157-193
# (test_login_is_refused_when_seed_key_is_broken) -- the pattern to reuse for
# MFA-01/MFA-04's veto tests: bind a request, populate credentials on it
# directly, call PAS's own _extractUserIds, assert on the return value.
request = self.layer['request']
request.form['__ac_name'] = TEST_USER_NAME
request.form['__ac_password'] = TEST_USER_PASSWORD
setRequest(request)
try:
    user_ids = self.pas._extractUserIds(request, self.pas.plugins)
    self.assertFalse(user_ids, 'MFA-04: no session for a 2FA-enabled user')
finally:
    setRequest(None)
```
For the `Authorization: Basic` extractor specifically, `credentials_basic_auth`'s
`extractCredentials` reads `request._authUserPW()`, which decodes `request._auth`
(`ZPublisher/HTTPRequest.py:1518-1527`, populated from `environ['HTTP_AUTHORIZATION']` at request
construction, `:328`). A unit test can set `request._auth = 'Basic ' + base64.b64encode('%s:%s' %
(user, password))` directly on the layer's request object before calling `_extractUserIds`, mirroring
the form-POST idiom above without a full HTTP round trip.

For the body-emptiness assertion (MFA-02) and the real redirect target (COEX-08), a
`plone.testing.z2.Browser`-based test is unavoidable (`tests/base.py:_login_browser`,
`BaseTest._install`, both already `Browser(self.app)`-based) — but redirect-following must be
verified/disabled for the specific request that checks the pre-redirect body, since the standard
`browser.open()` idiom already used in this package does not itself prove anything about redirect
behavior either way. Flagged as Open Question 2 below.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `movePluginsDown(iface, listPlugins(iface)[:-1])` to bubble the just-added plugin to index 0 | `movePluginsTop(iface, [plugin_id])` | This phase | Same end state today (both land the plugin at index 0), but `movePluginsTop` states intent directly and does not depend on the plugin being the most-recently-appended entry — a future re-install order or a second `activatePlugin` call between ours and the "top" call would silently break the old idiom's assumption |
| `response.redirect(signed_url, lock=1)` inside `authenticateCredentials` | Decide-only `authenticateCredentials`; redirect issued from `IChallengePlugin.challenge()` or an `IPubBeforeCommit` subscriber | This phase | Closes the MFA-02 body leak and is the prerequisite for MFA-12 (Phase 5) — a PAS plugin that never writes anything after this phase is a PAS plugin Phase 5 does not have to retrofit |

**Deprecated/outdated:** None — no library API in this phase is versioned/deprecated; this is a
correction of this codebase's own usage of a still-current API.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No live HTTP Basic Auth / WebDAV / FTP / XML-RPC dependency exists against this Plone site's own `acl_users` anywhere in the iMio ecosystem | Summary, "Alternatives Considered" | Search covered `imio.dms.mail`, `server.dmsmail`, and `industrialisation` (the three repos ROADMAP.md names plus the Puppet repo CLAUDE.md names) but not every iMio repo on this machine (e.g. `imio.pm.wsclient`, other product buildouts). If some other deployed script or integration does rely on Basic Auth into a `server.dmsmail`-family site, deactivating `credentials_basic_auth` site-wide would break it silently until someone reports failed automation. **This is exactly why the phase notes require the decision to be settled with evidence, not assumed** — treat this finding as strong-but-not-exhaustive and gate the actual deactivation behind a `checkpoint:human-verify` naming the repos searched. |
| A2 | The phase's "returns HTTP 200" framing for the login-POST path describes `login_form`'s baseline (pre-fix) behavior on invalid credentials, not a hard requirement that our own redirect must itself be status 200 rather than 302 | Architecture Patterns, Open Questions | If a plan or test enforces literal 200 on the *final* response instead of 302-to-token-form, the implementation could end up serving the token form's HTML directly at 200 instead of redirecting — a materially different (and untested-here) UX/security shape. Needs one concrete behavioral test to settle, as the phase's own success criterion #4 already mandates. |
| A3 | `plone.testing.z2.Browser`'s underlying `zope.testbrowser`/`mechanize` stack in this buildout's pinned version does or does not auto-follow HTTP redirects by default | Common Pitfalls (#4), Code Examples | If it auto-follows, a naive `browser.open()` assertion for MFA-02's "body is empty on the 302" would need explicit redirect-disabling (e.g. driving `mechanize` directly, or asserting via `browser.headers`/response object before any follow) rather than the plain `open()`/`contents` idiom already used elsewhere in this suite. Not yet spiked against the installed `plone.testing` version. |

## Open Questions

1. **Does the `IPubBeforeCommit` subscriber's final client-visible status need to be literally 200,
   or is 302-to-token-form acceptable?**
   - What we know: `IPubBeforeCommit` fires after the login_form view has already rendered a 200
     body; nothing stops the subscriber from also changing the status via `response.redirect()`.
   - What's unclear: whether "returns HTTP 200" in the phase description is a hard client-visible
     requirement or a description of the pre-fix baseline that justifies needing this hook at all.
   - Recommendation: write the success-criterion test first (per this project's TDD convention) and
     let its assertion settle the question; do not guess in the plan.

2. **Does `plone.testing.z2.Browser` in this buildout's pinned version auto-follow redirects?**
   - What we know: the package already uses `Browser(self.app)` extensively
     (`tests/base.py`), but no existing test in this suite currently inspects a pre-redirect body.
   - What's unclear: the exact redirect-following default for the installed version.
   - Recommendation: spike this in Wave 0 with a one-line assertion against a known-redirecting URL
     before writing the MFA-02 test for real, to avoid discovering it mid-test-writing.

3. **Should the plugin also be explicitly ordered first among `IChallengePlugin` (not just
   `IAuthenticationPlugin`), given the protocol-group semantics traced above?**
   - What we know: leaving `protocol` unset isolates our challenge from every other challenger's
     protocol group by construction (own-plugin-id fallback), so in practice ordering among
     challengers should not matter — our `challenge()` only ever returns `True` when we ourselves
     set `_2fa_pending` this same request, so it never competes with another challenger's *own*
     trigger condition.
   - What's unclear: whether there is some edge case (e.g. `IChallengeProtocolChooser`'s mapping
     configured non-default at some iMio site) where this isolation breaks.
   - Recommendation: no explicit `IChallengePlugin` ordering requirement in this phase's
     REQUIREMENTS.md, and none is needed given the above — but the planner should not add ordering
     for `IChallengePlugin` as a "belt and suspenders" task without a test proving it changes
     behavior, since an untested ordering call is dead weight.

## Environment Availability

Skipped — this phase has no external dependency beyond the eggs already resolved and verified above
(`Products.PluggableAuthService`, `Products.PluginRegistry`, `Zope2`), all present in this buildout's
`parts/omelette` symlink tree.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` via `bin/test` (plone.recipe.zope2instance `[test]` part; `unittest2` in test modules) |
| Config file | `test-4.3.cfg` (buildout-generated `bin/test`); no separate pytest/nose config |
| Quick run command | `bin/test -t test_pas_plugin -t test_setuphandlers` (module-scoped, fast) |
| Full suite command | `bin/test -t '!robot'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MFA-01 | 2FA user cannot authenticate via `Authorization: Basic` | integration (unit-style, `_extractUserIds`) | `bin/test -t test_basic_auth_veto` | ❌ Wave 0 — new test method in `tests/test_pas_plugin.py` |
| MFA-02 | No response body served alongside the refusal redirect | integration (`Browser`, redirect-following disabled) | `bin/test -t test_no_body_leak_on_2fa_redirect` | ❌ Wave 0 — new test, likely `tests/test_pas_plugin.py` or a new `tests/test_challenge.py` |
| MFA-03 | Plugin is first among `IAuthenticationPlugin`, via `movePluginsTop` | integration | `bin/test -t test_plugin_is_first_authenticator` | ❌ Wave 0 — new test in `tests/test_setuphandlers.py` |
| MFA-04 | One veto test per credentials extractor (form POST, Basic) | integration (unit-style, `_extractUserIds`) | `bin/test -t test_form_post_veto -t test_basic_auth_veto` | ❌ Wave 0 — extends `tests/test_pas_plugin.py` |
| COEX-08 | Challenge fires on both `Unauthorized` and login-POST-200 paths, each with its own test | integration | `bin/test -t test_challenge_fires_on_unauthorized -t test_pub_before_commit_fires_on_login_post` | ❌ Wave 0 — new tests, likely a new `tests/test_challenge.py` and extending `tests/test_subscribers.py` |
| DOC-01 | Zope-root limitation documented | manual-only (docs, not code) | n/a — reviewed by `grep`/read of README.rst | N/A (docs, `helpers.py:is_site_local_user`'s existing docstring already states this; README.rst needs the equivalent) |
| DOC-02 | Basic-auth consequence + service-account alternative documented | manual-only (docs) | n/a | N/A (docs) |

### Sampling Rate
- **Per task commit:** `bin/test -t test_pas_plugin -t test_setuphandlers -t test_subscribers`
- **Per wave merge:** `bin/test -t '!robot'`
- **Phase gate:** Full suite green (`bin/test -t '!robot'`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pas_plugin.py` — add `test_basic_auth_veto` and (if not already present)
  `test_form_post_veto`, covering MFA-01/MFA-04, using the `_extractUserIds` unit idiom above.
- [ ] `tests/test_setuphandlers.py` — add `test_plugin_is_first_authenticator`, covering MFA-03.
- [ ] New `tests/test_challenge.py` (or extend `tests/test_subscribers.py` if that module already
  targets `IPubBeforeCommit`-style subscribers) — covers COEX-08's two independent paths and MFA-02's
  body-emptiness assertion; requires settling Open Question 2 (redirect-following) first.
- [ ] Framework install: none — `bin/test` already exists and is the established test runner for
  this package.

## Security Domain

### Applicable ASVS Categories (Level 1, per `.planning/config.json` `security_asvs_level: 1`)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | This *is* the authentication boundary: PAS `IAuthenticationPlugin` ordering + credential wipe is the second-factor enforcement mechanism (ASVS 2.1/2.2-adjacent: verifier requires possession factor before granting session) |
| V3 Session Management | yes (adjacent) | `__ac` cookie is cleared, never set, until the token form's own `_setupSession` call (`browser/forms/token.py:107-108`); this phase must not introduce any path that sets `__ac` before the second factor is verified |
| V4 Access Control | no (this phase) | Access control decisions (role/permission checks) are unaffected; this phase only concerns *authentication*, not authorization once authenticated |
| V5 Input Validation | n/a (this phase) | No new user-supplied input parsing is introduced; `_2fa_pending` is a server-set flag, not user input |
| V6 Cryptography | no (this phase) | Unchanged from Phase 3; `sign_user_data`/`ska` reused as-is, not modified here |
| V7 Error Handling and Logging | yes | MFA-04's veto and the exception-path refusal (success criterion 5) both concern what happens on failure — must not leak (MFA-02) and must fail closed (refuse rather than fall through to `source_users`) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Second-factor bypass via authenticator ordering (a later `IAuthenticationPlugin` grants a session before ours vetoes it) | Elevation of Privilege | `movePluginsTop` at install time + an explicit ordering test (MFA-03), not implicit append-order behavior |
| Second-factor bypass via an extractor our plugin doesn't veto (Basic Auth, any future `IExtractionPlugin`) | Elevation of Privilege | One veto test per extractor (MFA-04); deactivate `credentials_basic_auth` as defense-in-depth pending the human-verify checkpoint |
| Protected-content disclosure via a 302 body (information disclosure despite a "refusal") | Information Disclosure | Explicit `setBody('')` in the pub-event subscriber; challenge-path avoids the problem structurally by intercepting before the original view ever renders |
| Silent lockout-that-never-locks from a write on an aborted transaction | Tampering (of the security control itself) | Write-free `challenge()`/subscriber in this phase; all second-factor state writes deferred to the token form view (Phase 5, MFA-12) |
| A cached authentication result (via `ZCacheable_get`/`ZCacheable_set`) bypassing 2FA if a cache manager is ever added to `acl_users` | Elevation of Privilege | No cache manager exists today (verified); one-line comment at the `_extractUserIds` call site documenting the hazard for any future site administrator, per the roadmap's own instruction |

## Sources

### Primary (HIGH confidence — read directly from the eggs this buildout resolves)
- `/srv/src/imio.googleauthenticator/parts/omelette/Products/PluggableAuthService` →
  `Products.PluggableAuthService-1.11.3-py2.7-linux-x86_64.egg/Products/PluggableAuthService/PluggableAuthService.py`
  — `_extractUserIds`, `challenge`, `_unauthorized`, `__call__` (before-traverse hook), `validate`
- `/srv/cache/eggs/Products.PluginRegistry-1.4.1-py2.7-linux-x86_64.egg/Products/PluginRegistry/PluginRegistry.py`
  — `movePluginsTop`/`movePluginsUp`/`movePluginsDown`/`activatePlugin`/`listPlugins`
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/ZPublisher/Publish.py` —
  `publish`, event-notification ordering relative to `mapply`/`commit`/`abort`
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/ZPublisher/HTTPResponse.py` —
  `redirect`, `setStatus`, `exception`, `_unauthorized`
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/ZPublisher/interfaces.py` —
  `IPubBeforeCommit`/`IPubSuccess`/`IPubAfterTraversal` definitions
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/Zope2/App/startup.py` —
  `zpublisher_exception_hook`'s explicit `Unauthorized`/`Redirect` re-raise behavior
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/OFS/Cache.py` —
  `ZCacheable_get`/`ZCacheable_getCache`
- `.../Products/PluggableAuthService/plugins/HTTPBasicAuthHelper.py`,
  `.../plugins/CookieAuthHelper.py`, `.../plugins/ChallengeProtocolChooser.py` — extractor/challenge
  plugin behavior and `protocol` attribute semantics
- `/home/cadam/buildout-cache/eggs/plone.transformchain-1.2.2-py2.7.egg/plone/transformchain/zpublisher.py`
  and its `configure.zcml` — production `IPubBeforeCommit` subscriber pattern, already in this
  buildout
- This repo's own `src/imio/googleauthenticator/pas_plugin.py`, `setuphandlers.py`, `helpers.py`,
  `browser/forms/token.py`, `tests/test_pas_plugin.py`, `tests/test_setuphandlers.py`, `tests/base.py`
- `/srv/src/imio.dms.mail`, `/srv/src/server.dmsmail`, `/srv/src/industrialisation` — grepped for
  basic-auth/WebDAV/FTP/XML-RPC dependence (Assumptions Log A1)

### Secondary (MEDIUM confidence)
- None — every claim above was traceable to an installed source file; no web search was required
  or performed for this phase's technical questions.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all APIs traced to the exact installed egg versions.
- Architecture: HIGH — the decide/redirect/grant split and its two hooks are derived directly from
  `Publish.py`'s literal control flow, not inferred.
- Pitfalls: HIGH for the mechanical ones (accumulation loop, body-vs-status lock, abort timing);
  MEDIUM for the basic-auth deactivation recommendation (evidence-based but not exhaustively
  searched — see A1) and the testbrowser redirect-following behavior (not yet spiked — see A3).

**Research date:** 2026-07-31
**Valid until:** Effectively indefinite for the mechanical PAS/ZPublisher findings (pinned egg
versions, `test-4.3.cfg` does not move without a deliberate pin bump); ~30 days for the basic-auth
ecosystem-dependence finding (A1), since sibling repos change independently of this one.
