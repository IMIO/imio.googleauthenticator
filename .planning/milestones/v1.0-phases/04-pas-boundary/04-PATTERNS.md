# Phase 4: PAS Boundary - Pattern Map

**Mapped:** 2026-07-31
**Files analyzed:** 7 (all modified/extended in-place — no brand-new modules needed)
**Analogs found:** 7 / 7

The key finding: this phase has no "no analog found" gap. `subscribers.py` and
`tests/test_subscribers.py` already exist (added in phase 3 for `IProcessStarting`); the
`IPubBeforeCommit` handler is a second function added to the *same* module, registered with a
second `<subscriber>` element in the *same* `configure.zcml`. There is no need for a new
`subscribers.zcml` as RESEARCH.md's "Recommended Project Structure" sketch speculated.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/imio/googleauthenticator/pas_plugin.py` (add `challenge()`, trim `authenticateCredentials`) | controller (PAS plugin) | request-response | itself, `authenticateCredentials` (same file, lines 77-176) | exact — same class, same file, this is an edit not a new pattern |
| `src/imio/googleauthenticator/setuphandlers.py` (`_add_plugin`: `movePluginsDown` → `movePluginsTop`) | config / install handler | event-driven (GenericSetup import step) | itself, `_add_plugin` (same file, lines 33-51) | exact — one-line API swap in place |
| `src/imio/googleauthenticator/subscribers.py` (add `redirect_pending_2fa`) | event-driven handler | event-driven (ZPublisher pub-event) | `on_process_starting` in the same file (lines 13-31) | exact — same module, same "one function per event" shape |
| `src/imio/googleauthenticator/configure.zcml` (add one `<subscriber>` element) | config (ZCML) | event-driven | the existing `IProcessStarting` `<subscriber>` block (lines 69-73) | exact |
| `src/imio/googleauthenticator/tests/test_pas_plugin.py` (add veto tests) | test | request-response (unit-style PAS call) | `test_login_is_refused_when_seed_key_is_broken` (lines 138-193) | exact |
| `src/imio/googleauthenticator/tests/test_setuphandlers.py` (add ordering test) | test | CRUD-ish (registry read) | `test_import_step_ordering` (lines 80-95) | exact |
| `src/imio/googleauthenticator/tests/test_challenge.py` (new) | test | request-response (`Browser`, redirect-following) | `tests/test_subscribers.py` (whole file, direct-call style) + `tests/base.py` `_login_browser`/`_get_browser` | role-match — no existing test drives a real `Unauthorized`/redirect body assertion yet, but the two building blocks (direct-call unit test shape, `Browser` helpers) both exist |
| `README.rst` (DOC-01/DOC-02 sections) | docs | n/a | existing deployment-key section + `tests/test_generic.py::test_readme_documents_the_deployment_key_and_its_failure_mode` | exact |

## Pattern Assignments

### `src/imio/googleauthenticator/pas_plugin.py`

**Analog:** itself — `authenticateCredentials` (lines 77-176), `classImplements` (line 179)

**Interface declaration pattern** (line 23, 179):
```python
from Products.PluggableAuthService.utils import classImplements
...
classImplements(GoogleAuthenticatorPlugin, IAuthenticationPlugin)
```
For the new `IChallengePlugin`, add the import and extend the same call:
```python
from Products.PluggableAuthService.interfaces.plugins import IChallengePlugin
...
classImplements(GoogleAuthenticatorPlugin, IAuthenticationPlugin, IChallengePlugin)
```
Do **not** add `protocol = 'http'` as a class attribute — RESEARCH.md's anti-pattern section
(citing `HTTPBasicAuthHelper.protocol = "http"`) is explicit that leaving it unset is what keeps
this challenger isolated from the Basic Auth challenger group.

**What must be deleted from `authenticateCredentials`** (lines 155-169):
```python
request = self.REQUEST
response = request['RESPONSE']
response.setCookie('__ac', '', path='/')

signed_url = sign_user_data(request=request, user=user,
                            url='@@google-authenticator-token')

came_from_adapter = ICameFrom(request)
came_from = came_from_adapter.getCameFrom()
if came_from:
    signed_url = '{0}&next_url={1}'.format(signed_url, came_from)

response.redirect(signed_url, lock=1)

return None
```
Replace with a decide-only body: set `request['_2fa_pending'] = True` (and whatever the
challenge/subscriber need to rebuild the signed URL — user id, came_from — either recomputed
there or stashed on the request) and `return None`. Keep the `for key in credentials.keys():
del credentials[key]` veto (lines 148-149) exactly as-is; RESEARCH.md's Pitfall 1 confirms this
in-place mutation is the actual security control, unrelated to the redirect being removed.

**Error handling / veto pattern to preserve unchanged** (lines 91-149): the whitelist check,
`api.user.get()` None-guard (CR-01 regression, lines 99-104), the inner `IAuthenticationPlugin`
delegation loop with `reraise(authplugin)` (lines 121-137), and `_dont_swallow_my_exceptions =
True` (line 71) are all untouched by this phase — do not "clean up" them while making the
redirect edit.

**New `challenge()` method** — no local analog exists (this is the one genuinely new method in
the file), so copy directly from RESEARCH.md's traced contract (`PluggableAuthService.py:1152-1192`
verified there) and follow this file's own `logger.debug` idiom (line 106, 110):
```python
def challenge(self, request, response):
    if not request.get('_2fa_pending'):
        return False
    signed_url = sign_user_data(...)
    response.redirect(signed_url)
    return True
```
Per Pitfall 3, this method must perform zero writes beyond `response.redirect` — no
`setMemberProperties`, no registry write.

---

### `src/imio/googleauthenticator/setuphandlers.py`

**Analog:** itself, `_add_plugin` (lines 33-51)

**Current idiom to replace** (lines 48-51):
```python
pas.plugins.activatePlugin(interface, plugin.getId())
pas.plugins.movePluginsDown(
    interface,
    [x[0] for x in pas.plugins.listPlugins(interface)[:-1]],
)
```
**Replacement** (per RESEARCH.md Q6, `PluginRegistry.py:166-177` signature confirmed):
```python
pas.plugins.activatePlugin(interface, plugin.getId())
pas.plugins.movePluginsTop(interface, [plugin.getId()])
```
Keep the surrounding `for info in pas.plugins.listPluginTypeInfo():` loop structure (lines 43-47)
and the existing `installed = pas.objectIds()` idempotency guard (lines 37-39) unchanged — this
is a one-call swap inside an existing loop, not a restructure.

If the basic-auth deactivation is implemented in this phase (per RESEARCH.md's "Primary
recommendation"), add it as a new, separate statement in `setupVarious` (lines 53-69) — do not
fold it into `_add_plugin`, which is specifically about *our* plugin's install/activation, not
about other plugins' extractor status. `_setup_secret_key()` (lines 13-31) is the existing
model for "one focused helper function called once from `setupVarious`" — mirror that shape for
a `_deactivate_basic_auth(pas)` helper if the roadmap's open decision resolves to "do it."

---

### `src/imio/googleauthenticator/subscribers.py`

**Analog:** itself, `on_process_starting` (lines 13-31)

**Imports pattern** (lines 1-10):
```python
import logging

from imio.googleauthenticator.helpers import get_encryption_key

logger = logging.getLogger("imio.googleauthenticator")
```
Add `from ZPublisher.interfaces import IPubBeforeCommit` and `from zope.component import
adapter` alongside — same flat, no-package-prefix-aliasing import style already used here.

**Core event-handler shape to copy** (lines 13-30 — docstring + guard + log, no exception):
```python
def on_process_starting(event):
    """..."""
    if not get_encryption_key():
        logger.critical(...)
```
New handler, same shape, doc-commented per this module's own convention (explaining *why*
write-free, matching the existing docstring's density):
```python
@adapter(IPubBeforeCommit)
def redirect_pending_2fa(event):
    """..."""
    request = event.request
    if not request.get('_2fa_pending'):
        return
    response = request.response
    signed_url = sign_user_data(...)
    response.redirect(signed_url)
    response.setBody('')  # required -- see RESEARCH.md Pitfall 2
```
This module currently imports only from `helpers`; add `from imio.googleauthenticator.helpers
import sign_user_data` next to the existing `get_encryption_key` import, following the same
one-symbol-per-line style (compare `pas_plugin.py` lines 27-29, which imports the same
`sign_user_data` the same way).

---

### `src/imio/googleauthenticator/configure.zcml`

**Analog:** the existing `IProcessStarting` subscriber block (lines 69-73)

**Pattern to copy verbatim (structure), new `for`/`handler`:**
```xml
<!-- -*- Loud at boot when the seed-encryption key is missing (SEC-08) -*- -->
<subscriber
   for="zope.processlifetime.IProcessStarting"
   handler=".subscribers.on_process_starting"
   />
```
New entry, same indentation/comment style, appended after it:
```xml
<!-- -*- Redirect a pending 2FA challenge before the response commits (MFA-02/COEX-08) -*- -->
<subscriber
   for="ZPublisher.interfaces.IPubBeforeCommit"
   handler=".subscribers.redirect_pending_2fa"
   />
```
No new ZCML file — everything else already registered in this file (`<genericsetup:importStep>`,
the `IPrincipalCreatedEvent` subscriber at lines 63-67) lives here too; a `subscribers.zcml` split
would be an unrequested restructure.

---

### `src/imio/googleauthenticator/tests/test_pas_plugin.py`

**Analog:** `test_login_is_refused_when_seed_key_is_broken` (lines 138-193), and the `setRequest`
idiom shared with `test_unmatched_username_does_not_crash` (lines 86-109)

**Unit-style PAS-loop idiom to copy for MFA-01/MFA-04** (lines 167-174 — form-POST extractor):
```python
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
For the Basic-Auth extractor veto (MFA-01), RESEARCH.md's Q8 continuation gives the exact
request-construction line to substitute for the two `request.form[...]` lines above:
```python
import base64
request._auth = 'Basic ' + base64.b64encode('%s:%s' % (TEST_USER_NAME, TEST_USER_PASSWORD))
```
Reuse this file's existing `setUp`/`tearDown` fixture (lines 31-46, seed-key env var) and the
2FA-enablement boilerplate from `test_login_is_refused_when_seed_key_is_broken` (lines 157-165 —
`login()`, `setMemberProperties`, `get_or_create_secret(user, overwrite=True)`) rather than
re-deriving it.

---

### `src/imio/googleauthenticator/tests/test_setuphandlers.py`

**Analog:** `test_import_step_ordering` (lines 80-95)

**Ordering-assertion shape to copy for MFA-03**, using RESEARCH.md's exact assertion:
```python
def test_plugin_is_first_authenticator(self):
    """MFA-03: google_auth must be first among IAuthenticationPlugin so its
    in-place credentials wipe is observed by every later plugin in the same
    _extractUserIds loop iteration (see pas_plugin.py's veto)."""
    self.assertEqual(
        self.pas.plugins.listPlugins(IAuthenticationPlugin)[0][0], PAS_ID)
```
Needs `from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin` added
to this file's imports (not currently imported here — it is imported in `test_pas_plugin.py`,
line 2); follow that file's import line verbatim. Use the same `self.pas` (from `setUp`,
`getToolByName(self.portal, 'acl_users')` — mirror `test_pas_plugin.py` line 35, since
`test_setuphandlers.py`'s current `setUp` does not define `self.pas` yet) — add that one line to
`setUp` alongside `self.portal`/`self.request`.

---

### `src/imio/googleauthenticator/tests/test_challenge.py` (new)

**Analog:** `tests/test_subscribers.py` (direct-call event-handler test shape, whole file) +
`tests/base.py` `_get_browser`/`_login_browser` (lines 30-38) for the HTTP-level half

No file in this repo currently drives a real `Unauthorized`/redirect-body assertion, so this is
the one genuinely new test module. Structure it in two halves, each copying a different existing
idiom rather than inventing a third:

1. **Challenge-plugin unit half** (COEX-08's `Unauthorized` path) — copy the direct-call idiom
   from `test_subscribers.py` (lines 27-79): instantiate/fetch the plugin, call `.challenge(request,
   response)` directly with `request['_2fa_pending']` set/unset, assert the boolean return and
   that `response.redirect` was invoked (a stub response object, same spirit as `_StubLogger`,
   lines 17-24).
2. **Body-emptiness + login-POST half** (MFA-02, COEX-08's pub-event path) — copy
   `tests/base.py`'s `_get_browser`/`_login_browser` (lines 30-38) and `test_pas_plugin.py`'s
   `setUp`/`_install()` fixture (lines 31-46). RESEARCH.md's Open Question 2/Assumption A3 flags
   that `plone.testing.z2.Browser`'s redirect-following default is unverified in this buildout —
   spike that first (per RESEARCH.md's own recommendation) before asserting on `browser.contents`;
   `browser.mech_browser.set_handle_redirect(False)` or inspecting `browser.headers`/status prior
   to any `.open()` follow-through is the likely shape, but confirm against the installed
   `mechanize` version before writing the assertion.

Reuse `test_pas_plugin.py`'s seed-key env var setUp/tearDown (lines 39-46) since any test that
reaches `sign_user_data` needs a valid encryption key present.

---

### `README.rst`

**Analog:** the existing deployment-key section and its precedent test,
`tests/test_generic.py::test_readme_documents_the_deployment_key_and_its_failure_mode`

Read that test's assertion shape (grep-based existence check, not prose-matching) and add two
sibling assertions in the same test file for DOC-01 (Zope-root/Control_Panel boundary is out of
2FA's reach) and DOC-02 (Basic-Auth deactivation consequence + service-account alternative) —
same "assert a heading/keyword exists, not exact wording" pattern.

## Shared Patterns

### PAS plugin interface declaration
**Source:** `src/imio/googleauthenticator/pas_plugin.py:23,179`
**Apply to:** `pas_plugin.py` only (single call site) — add `IChallengePlugin` to the existing
`classImplements(...)` call rather than a second call.

### Event-handler module shape (one function per event, direct-call testable)
**Source:** `src/imio/googleauthenticator/subscribers.py:13-31` (`on_process_starting`)
**Apply to:** the new `redirect_pending_2fa` function in the same module, and its test in
`test_subscribers.py` or `test_challenge.py`.

### ZCML `<subscriber>` registration block, with a one-line comment naming the requirement id
**Source:** `src/imio/googleauthenticator/configure.zcml:69-73`
**Apply to:** the new `IPubBeforeCommit` registration in the same file.

### `setRequest(request)` / `finally: setRequest(None)` for unit-style PAS calls
**Source:** `src/imio/googleauthenticator/tests/test_pas_plugin.py:102-109, 170-193`
**Apply to:** all new veto tests in `test_pas_plugin.py`, and the challenge-plugin unit half of
`test_challenge.py`.

### Seed-key env var fixture (`os.environ[helpers.ENV_VAR_NAME]`)
**Source:** `src/imio/googleauthenticator/tests/test_pas_plugin.py:39-46`
**Apply to:** any new test that reaches `sign_user_data`/`get_or_create_secret` — `test_challenge.py`
in particular.

## No Analog Found

None. Every file in this phase's expected set is either an edit to an existing file, or (for
`test_challenge.py`) a new file assembled from two already-established test idioms in this same
package (see Pattern Assignments above for the exact composition).

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/` (all `.py`/`.zcml` — 27 files listed via
`find`); no search outside this package was needed, since RESEARCH.md already identified every
mechanism as internal-to-this-repo or in already-installed eggs (`plone.transformchain`, not a
local analog but already cited in RESEARCH.md's own code examples).
**Files scanned:** `pas_plugin.py`, `setuphandlers.py`, `subscribers.py`, `configure.zcml`,
`tests/test_pas_plugin.py`, `tests/test_setuphandlers.py`, `tests/test_subscribers.py`,
`tests/base.py`.
**Pattern extraction date:** 2026-07-31
