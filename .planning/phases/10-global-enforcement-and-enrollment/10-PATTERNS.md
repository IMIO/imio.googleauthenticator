# Phase 10: Global Enforcement and Enrollment - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 13 (9 modified, 1 new source view/logic, 4 test files extended, 1 new test file)
**Analogs found:** 12 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `setuphandlers.py` (new install-enrollment step) | migration/install-handler | batch/CRUD | `setuphandlers.py:_add_plugin` (same file) | exact — same file, same idempotency shape |
| `helpers.py` (new flag-only enrollment helper) | utility | batch/CRUD | `helpers.enable_two_factor_authentication_for_users` | exact — same module, narrower sibling |
| `browser/disable_two_factor_authentication.py` (add refusal) | controller/view | request-response | `browser/controlpanel.py` `handleSave`'s `ValueError` refusal shape, and `SetupForm.handleSubmit`'s anonymous 401 guard | role-match |
| `browser/disable_two_factor_authentication_for_all_users.py` (add refusal) | controller/view | request-response | `disable_two_factor_authentication.py` after D-08 is applied to it | exact (sibling, same refusal) |
| `browser/settings_helper.py` (invert two conditions) | utility/view-helper | request-response | itself (in-place edit); precedent for inverted boolean composition is its own docstrings | exact |
| `profiles/default/actions.xml` (new condition for regenerate) | config | request-response | existing `regenerate_recovery_codes` / `disable_two_factor_authentication` action entries, same file | exact |
| `pas_plugin.py` (route to enrollment vs token page) | controller/PAS-plugin | request-response | `pas_plugin.py:authenticateCredentials` / `send_2fa_redirect` (same file, same seam) | exact |
| `browser/forms/user_setup.py` (anonymous/signed-URL reachability) | controller/component (z3c.form) | request-response | `browser/forms/token.py` `TokenForm.handleSubmit` | exact — this is the analog named explicitly by CONTEXT.md/RESEARCH.md |
| `profiles/default/memberdata_properties.xml` (new property) | config | CRUD | existing lockout/replay counter entries, same file | exact |
| `tests/test_settings_helper.py` (new) | test | request-response | `tests/test_adapter.py` (BaseTest/layer shape) + `tests/test_controlpanel.py` (globally_enabled toggling) | role-match, composed from two analogs |
| `tests/test_setuphandlers.py` (extend) | test | batch | `tests/test_setuphandlers.py` (existing `get_app_settings()` tests, same file) | exact |
| `tests/test_disable_two_factor_authentication.py` (extend) | test | request-response | same file's existing 3 methods | exact |
| `tests/test_pas_plugin.py` / `tests/test_user_setup.py` / `tests/test_adapter.py` (extend) | test | request-response / CRUD | same files' existing methods; `tests/test_adapter.py`'s `LOCKOUT_STATE_PROPERTIES` round-trip tests for the D-06(b) property | exact |

## Pattern Assignments

### `src/imio/googleauthenticator/setuphandlers.py` — install-time enrollment (D-01/D-02/D-04/D-13)

**Analog:** same file, `_add_plugin` (lines 47-78) and `setupVarious` (lines 81-97).

**Idempotency pattern to copy** (`setuphandlers.py:58-61`):
```python
installed = pas.objectIds()
if pluginid not in installed:
    plugin = GoogleAuthenticatorPlugin(pluginid, title=PAS_TITLE)
    pas._setObject(pluginid, plugin)
```
Mirror this shape for the per-user guard: check `has_enabled_two_factor_authentication(user)` before writing, exactly the "check current state before writing" idiom RESEARCH.md calls out.

**Marker-file gate to reuse, not duplicate** (`setuphandlers.py:81-97`):
```python
def setupVarious(context):
    if context.readDataFile('imio.googleauthenticator.marker.txt') is None:
        return
    portal = context.getSite()
    _setup_secret_key()
    pas = portal.acl_users
    _add_plugin(pas)
```
Add the new enrollment call inside this same gated block (after `_add_plugin(pas)` or before it — order does not matter, both are idempotent), not in a separately-gated function. D-13 leaves "call it inline vs. via a helper" at your discretion, but it must run inside this existing `if` body.

**Error propagation, do NOT copy the swallowing arm:**
```python
# helpers.py:1031-1052, enable_two_factor_authentication_for_users
except ValueError:
    raise
except Exception as e:
    logger.debug(str(e))   # <-- D-04 forbids this shape at install time
```
D-04 requires letting any per-user exception propagate unswallowed (or an explicit try/except that raises after enrolling everyone it can and reporting — but the simplest compliant shape is just not wrapping the loop body in a swallowing except at all, per RESEARCH.md's Assumption A1).

---

### `src/imio/googleauthenticator/helpers.py` — new flag-only enrollment helper (D-02)

**Analog:** `enable_two_factor_authentication_for_users` (`helpers.py:1031-1046`), narrowed.

```python
def enable_two_factor_authentication_for_users(users=None):
    if not users:
        users = api.user.get_users()
    for user in users:
        try:
            get_or_create_secret(user)                      # <-- DO NOT call this
            if not has_enabled_two_factor_authentication(user):
                user.setMemberProperties(
                    mapping={'enable_two_factor_authentication': True})
        except ValueError:
            raise
        except Exception as e:
            logger.debug(str(e))                            # <-- DO NOT copy this arm
```
The new helper keeps the loop shape and the `has_enabled_two_factor_authentication` guard, drops the `get_or_create_secret` call (no seed at install — D-02) and drops the swallowing `except Exception` arm (D-04). No `ValueError` handling is needed either, since nothing in the narrowed body can raise it — a plain `setMemberProperties` call raises nothing comparable.

---

### `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py` — self-disable refusal (D-08)

**Analog (anonymous-guard shape):** `browser/forms/user_setup.py:69-71` (`SetupForm.handleSubmit`'s anonymous 401 guard) and this file's own existing anonymous guard.

**Current file in full** (40 lines) — the refusal is a second guard of the identical shape, right after the existing one:
```python
def disable(self):
    if bool(api.user.is_anonymous()) is True:
        self.request.response.setStatus(401, _('Forbidden for anonymous'), True)
        return None

    # D-08: NEW — refuse while globally_enabled is on
    if is_two_factor_authentication_globally_enabled():
        IStatusMessage(self.request).addStatusMessage(
            _('...'),  # D-12: wording at implementer's discretion
            'error')
        redirect_url = "{0}/@@personal-information".format(self.context.absolute_url())
        self.request.response.redirect(redirect_url)
        return None

    user = api.user.get_current()
    user.setMemberProperties(mapping={...})
    ...
```
Import `is_two_factor_authentication_globally_enabled` from `helpers` the same way `settings_helper.py:2` already does.

**Status-message error-reporting pattern to copy** (`browser/controlpanel.py:143-148`):
```python
IStatusMessage(self.request).addStatusMessage(
    _(u"Two-step verification could not be enabled for any user: ..."),
    "error")
```

---

### `src/imio/googleauthenticator/browser/disable_two_factor_authentication_for_all_users.py` — same refusal (D-18)

**Analog:** the sibling file above, post-D-08 edit. Same guard, same import, same early-return-with-redirect shape; this view has no anonymous guard today (`index()`, lines 19-31) so this is the *only* guard added, not a second one.

---

### `src/imio/googleauthenticator/browser/settings_helper.py` — invert two conditions (D-10/D-11) + `regenerate` (D-15)

**Analog:** itself — RESEARCH.md's "Recommended shape" section gives the exact target code:

```python
# D-10 (MFA-17/MFA-18)
def show_enable_two_factor_authentication_link(self):
    if api.user.is_anonymous():
        return False
    user = api.user.get_current()
    return not has_enabled_two_factor_authentication(user)

# D-11 (MFA-16 mirror)
def show_disable_two_factor_authentication_link(self):
    if api.user.is_anonymous():
        return False
    user = api.user.get_current()
    return (
        has_enabled_two_factor_authentication(user) and
        not is_two_factor_authentication_globally_enabled()
    )
```
Current (wrong) code to replace, `settings_helper.py:36-63` — both methods today require `is_two_factor_authentication_globally_enabled()` to be **True**, which this phase inverts/removes per D-10 and changes to a `not` per D-11.

**D-15 addition — new method, same class, same shape:**
```python
def show_regenerate_recovery_codes_link(self):
    if api.user.is_anonymous():
        return False
    user = api.user.get_current()
    return has_enabled_two_factor_authentication(user)
```

---

### `src/imio/googleauthenticator/profiles/default/actions.xml` — D-15

**Analog:** the existing `regenerate_recovery_codes` action entry (lines ~41-52) and its neighboring comment (lines 33-39) explaining the old reuse — both need editing in place, not copying from elsewhere. Point `available_expr` at the new `@@show-regenerate-recovery-codes-link` (or equivalent) view method instead of reusing `@@show-disable-two-factor-authentication-link`, and update the adjacent comment so it no longer claims the old reuse rationale.

---

### `src/imio/googleauthenticator/pas_plugin.py` — routing decision (D-05/D-06(b)/D-07)

**Analog:** same file — `authenticateCredentials` (lines 166-268) and `send_2fa_redirect` (lines 77-135), the existing "decide, don't act" seam.

**Current flag read to extend** (`pas_plugin.py:197-200`):
```python
two_factor_authentication_enabled = user.getProperty(
    'enable_two_factor_authentication')
```
Add a second, sibling read of the new D-06(b) memberdata property (e.g. `two_factor_authentication_enrolled`) right after this, still inside the same read-only region, still before `_mark_2fa_pending` (line 263). D-03 says do NOT gate on `is_two_factor_authentication_globally_enabled()` here — keep reading only user-level flags.

**Redirect-target selection to extend** (`pas_plugin.py:104-105`, inside `send_2fa_redirect`):
```python
signed_url = sign_user_data(
    request=request, user=user, url='@@google-authenticator-token')
```
The `url=` argument is the one thing that must vary — swap in the enrollment target's view name when the stashed pending-signal (carried via `_mark_2fa_pending`'s payload, extended to also carry the routing choice) says "not yet enrolled." Follow the existing `REQUEST_KEY_USER_ID` pattern in `_mark_2fa_pending` (lines 61-74) for stashing the extra bit — same `request.set(...)` mechanism, same `request.other` channel, no ZODB write.

**D-07 note:** `get_secret(user)` at `pas_plugin.py:257` is the existing synchronous fail-closed check for *enrolled* users with a broken seed. There is no equivalent pure-read check possible for a never-enrolled user (no seed exists yet to check) — RESEARCH.md flags this as an accepted pre-existing 500 risk, not something this phase is required to close. Do not invent a new key-presence check here unless the plan explicitly scopes it in.

---

### `src/imio/googleauthenticator/browser/forms/user_setup.py` — anonymous/signed-URL reachability (D-16) — **the single most important excerpt**

**Analog:** `browser/forms/token.py:107-153`, `TokenForm.handleSubmit`, copied near-verbatim.

**Full mechanism to mirror** (`token.py:107-153`):
```python
user = None
username = self.request.get('auth_user', '')

if username:
    user = api.user.get(username=username)

    # Validating the signed request data. If invalid (likely tampered
    # with or expired), generate an appropriate error message.
    user_data_validation_result = validate_user_data(
        request=self.request, user=user)

    if not user_data_validation_result.result:
        IStatusMessage(self.request).addStatusMessage(
            _("Invalid data. Details: {0}".format(' '.join(
                user_data_validation_result.reason))), 'error')
        return

    if user is not None and is_account_locked(user):
        msg = _("Invalid token or token expired.")
        IStatusMessage(self.request).addStatusMessage(msg, 'error')
        return

valid_token = validate_second_factor(token, user=user)   # -> validate_token(...) here

if valid_token:
    if user is not None:
        reset_failed_second_factor(user)

    # _setupSession accepts unicode directly on this stack; do not str() it
    self.context.acl_users.session._setupSession(
        username, self.context.REQUEST.RESPONSE)
    ...
else:
    if user is not None:
        register_failed_second_factor(user)
    msg = _("Invalid token or token expired.")
    IStatusMessage(self.request).addStatusMessage(msg, 'error')
```

**Where this plugs into `SetupForm.handleSubmit` (`user_setup.py:67-71` today):**
```python
@button.buttonAndHandler(_('Verify'))
def handleSubmit(self, action):
    if bool(api.user.is_anonymous()) is True:            # <-- this hard 401 must become
        self.request.response.setStatus(401, ...)         #     conditional on there being
        return False                                       #     no valid signed auth_user
```
Replace the unconditional `is_anonymous()` refusal with: read `auth_user`, `validate_user_data` it (same as `token.py`) — only if that check fails (or is absent AND the user is genuinely anonymous with no signed param) does the 401 stand. On success, resolve `user` from `auth_user` instead of `api.user.get_current()`, and after a first successful token verification, call `_setupSession` (exactly like `token.py:152-153`) before showing recovery codes, and write the new D-06(b) "enrolled" property.

**`updateFields`'s anonymous QR-hiding gate to also relax** (`user_setup.py:189-212`, the `is_anonymous() is False` guard around barcode rendering, per RESEARCH.md lines 189-212) — the same signed-`auth_user` check must gate this the same way it gates `handleSubmit`, so the QR code renders for a validly-signed-but-sessionless request.

**Do not hand-roll a second signing scheme** — reuse `validate_user_data`/`sign_user_data` exactly as imported in `token.py:5-11`; add the same imports to `user_setup.py`.

---

### `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` — D-06(b) new property

**Analog:** the existing lockout/replay counter entries, same file, one-line pattern:
```xml
<!-- existing precedent -->
<property name="two_factor_authentication_failed_attempts" type="int">0</property>
```
New entry, same shape:
```xml
<property name="two_factor_authentication_enrolled" type="boolean">False</property>
```
**Do NOT** add a corresponding field to `IEnhancedUserDataSchema` (`userdataschema.py`) or an accessor to `adapter.py` — the docstring precedent at `userdataschema.py:64-74` explains exactly why (internal state, would crash `@@user-information`, would become form-writable).

---

## Shared Patterns

### Global-setting read
**Source:** `helpers.is_two_factor_authentication_globally_enabled()`, already imported in `settings_helper.py:2` and usable identically in `disable_two_factor_authentication.py` / `disable_two_factor_authentication_for_all_users.py`.
```python
from imio.googleauthenticator.helpers import is_two_factor_authentication_globally_enabled
```

### Status-message refusal shape
**Source:** `browser/controlpanel.py:143-148` (error message) and `browser/disable_two_factor_authentication.py:35-38` (info message + redirect). Apply to both disable views for D-08/D-18's refusal, and reuse for D-12's new msgid.

### Anonymous / signed-request identity resolution
**Source:** `browser/forms/token.py:107-122, 152-153` — the ONE mechanism in this codebase for identifying a user from a request with no session. Apply to `user_setup.py` per D-16. Never invent a second signing/session-establishment scheme (see Don't Hand-Roll in RESEARCH.md).

### Internal-state memberdata property, no schema/adapter exposure
**Source:** `profiles/default/memberdata_properties.xml`'s existing 5 counter/hash entries, and `userdataschema.py:64-74`'s docstring explaining why they carry no schema field. Apply verbatim to the new D-06(b) property.

### Test: toggling `globally_enabled` directly
**Source:** `tests/test_setuphandlers.py:137-141` and `tests/test_helpers.py:158/172/180` — direct registry manipulation:
```python
from imio.googleauthenticator.helpers import get_app_settings
settings = get_app_settings()
settings.globally_enabled = True   # or False
```
This is the lightweight pattern for `test_settings_helper.py` and `test_pas_plugin.py`/`test_setuphandlers.py` extensions — simpler than driving the control-panel form's widgets (which `test_controlpanel.py` uses only because it's testing the form itself).

### Test: bulk-enrollment-over-several-users shape
**Source:** `tests/test_controlpanel.py:216-247` (`test_handleSave_globally_enabled_true_enrolls_users_successfully`) — set a precondition flag on `api.user.get_current()`/`api.user.get_users()`, run the handler, refetch via `api.user.get(username=...)`, assert the *effect* not just a status message. Apply this shape to `test_setuphandlers.py`'s new install-enrollment tests, creating additional users with `api.user.create(...)` (see `test_controlpanel.py`'s imports of `TEST_USER_ID`/`TEST_USER_NAME` for the one-user case; for multiple users, `helpers.py`'s own `enable_two_factor_authentication_for_users` tests in `test_helpers.py` iterate `api.user.get_users()` — grep that file for a multi-user creation helper if the plan needs more than the fixture's one default user).

### Test: memberdata round-trip for a new internal property
**Source:** `tests/test_adapter.py:83-124` — `test_lockout_state_is_memberdata_only_and_never_a_form_field` (schema-absence guard) and `test_lockout_state_still_persists_as_memberdata` (`memberdata.hasProperty(name)` check). Extend the `LOCKOUT_STATE_PROPERTIES` tuple (`test_adapter.py:22-28`) to include the new D-06(b) property name and both existing tests cover it automatically — no new test method needed, just add the name to the tuple. Add a third, separate set/get test if the plan wants explicit `setMemberProperties`/`getProperty` round-trip coverage beyond the `hasProperty` check.

### Test: layer/BaseTest shape for a brand-new test file
**Source:** `tests/test_adapter.py:1-37` (imports, class declaration, `layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`, `setUp` pulling `self.app`/`self.portal` off `self.layer`) — this is the minimal shape `test_settings_helper.py` should copy for its class skeleton:
```python
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
import unittest2 as unittest

class TestSettingsHelper(unittest.TestCase, BaseTest):
    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
```

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `tests/test_settings_helper.py` (as a whole file) | test | request-response | No prior test file for this module exists at all (confirmed by RESEARCH.md); composed above from `test_adapter.py`'s skeleton + `test_setuphandlers.py`/`test_helpers.py`'s `get_app_settings()` toggling — not a single analog but a documented composition. |

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/` (all `.py` under `browser/`, root package, `tests/`) and `profiles/default/`.
**Files scanned:** ~20 source files, 6 test files, read in full or targeted excerpts.
**Pattern extraction date:** 2026-08-06
