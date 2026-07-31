# Phase 5: Drift, Replay and Lockout - Pattern Map

**Mapped:** 2026-07-31
**Files analyzed:** 13 (11 modified, 2 created)
**Analogs found:** 13 / 13

**Correction vs. the seeded file list:** `profiles/default/metadata.xml` currently reads
`<version>1000</version>`, not the zero-padded `0301` CLAUDE.md describes, and no
`upgrades/` directory exists in this checkout (`find . -iname '*upgrade*'` is empty). There
is therefore no `upgrades/to0301.py` or `genericsetup:upgradeStep` registration to copy from.
If the plan wants a formal upgrade step, it has no existing analog in this repo and must be
built from `plone.app.genericsetup`'s standard `<genericsetup:upgradeStep ... handler="...">`
shape (documented, but not present here to excerpt) — flagged in "No Analog Found" below.
`registry.xml` needs **zero changes** (confirmed: the existing blanket `<records
interface="..."/>` has no child `<value>` nodes, so `plone.app.registry`'s importer seeds any
new schema field with its Python-level default — RESEARCH.md's claim holds).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `helpers.py::validate_token` (rewrite) | service/utility | request-response (pure check) | `helpers.py::validate_bar_code_reset_token` (constant-time compare, no-log discipline) + `helpers.py::get_or_create_secret`/`get_secret` (property read/decrypt pattern) | exact (same file, same module conventions) |
| `browser/forms/token.py::handleSubmit` | controller (z3c.form button handler) | request-response, state write | itself (existing `handleSubmit`) — extend in place | exact |
| `browser/forms/reset_bar_code.py::handleSubmit` | controller (z3c.form button handler) | request-response, state write | `browser/forms/token.py::handleSubmit` (sibling lockout wrapper, once written) | exact (near-identical shape already) |
| `browser/controlpanel.py::IGoogleAuthenticatorSettings` (2 new `Int` fields) | config/model (registry schema) | CRUD (registry record) | itself — `ska_secret_key`/`globally_enabled`/`ip_addresses_whitelist` fields on the same interface | exact |
| `userdataschema.py::IEnhancedUserDataSchema` (3 new fields) | model (memberdata schema) | CRUD (property declaration) | itself — `two_factor_authentication_secret`/`bar_code_reset_token` fields, plus `CustomizedUserDataPanel.__init__`'s `form_fields.omit(...)` | exact |
| `profiles/default/memberdata_properties.xml` (3 new `type="int"` entries) | config (GenericSetup XML) | batch (import-time seed) | itself — existing 3 `<property>` lines | exact |
| `profiles/default/registry.xml` | config | batch | itself — confirmed no change needed | n/a (no diff expected) |
| `tests/test_helpers.py` (extend) | test | CRUD/transform | `TestSeedEncryption` (setUp/tearDown env-key pattern) + `TestSkaSecretKey` (concern-named class convention) | exact |
| `tests/test_generic.py` (extend) | test | CRUD (field presence) | existing `IGoogleAuthenticatorSettings['ska_secret_key']` field lookups (`test_generic.py:106`) | exact |
| `tests/test_setuphandlers.py` (extend) | test | batch (GenericSetup import) | existing install/import assertion style in the same file (not excerpted here — same file, extend in place) | role-match |
| `tests/test_token_form.py` (new) | test | request-response, event-driven (real HTTP sequence) | `tests/test_challenge.py::TestPubBeforeCommitRedirect` (`_enable_2fa`, `_get_browser`/`_login_browser` from `tests/base.py::BaseTest`, `test_challenge_fires_on_unauthorized`, `test_pub_before_commit_fires_on_login_post`) | exact |
| `tests/test_reset_bar_code.py` (new) | test | request-response | same `test_challenge.py` two-request idiom, applied to `@@reset-bar-code` instead of the token form; `tests/test_request_bar_code_reset.py` for the sibling *request* form's setUp shape | role-match |
| Upgrade step (metadata.xml bump + upgrade handler) | migration | batch | **none in this repo** — see "No Analog Found" | — |

## Pattern Assignments

### `helpers.py::validate_token` (service, pure check + gated state read)

**Analog:** `helpers.py::validate_bar_code_reset_token` (lines 566-611) for the "no logging of
secret material, fail-closed on falsy/malformed input" discipline, and the existing
`validate_token` itself (lines 322-358) as the function being rewritten in place.

**Current implementation to replace** (`helpers.py:322-358`):
```python
def validate_token(token, user=None):
    if user is None:
        user = api.user.get_current()
    secret = get_secret(user)
    if not secret:
        return False
    validation_result = valid_totp(token=token, secret=secret)
    return validation_result
```

**Imports already present at module top** (`helpers.py:1-33`) — add `time` and `get_hotp` to
this existing block, do not create a new import section:
```python
from hashlib import sha1
from hmac import compare_digest
...
from onetimepass import valid_totp
...
logger = logging.getLogger("imio.googleauthenticator")
```

**Property-read pattern to copy** (`helpers.py::get_secret`, lines 217-233) — same
`user.getProperty(name)` + falsy-coerce idiom the new `last_interval` read should follow:
```python
def get_secret(user=None, hashed=False):
    if user is None:
        user = api.user.get_current()
    if user:
        secret = user.getProperty('two_factor_authentication_secret')
        if isinstance(secret, basestring) and secret:
            return decrypt_seed(secret)
```

**Property-write pattern to copy** (`helpers.py::generate_secret`, lines 182-195) — the
`setMemberProperties(mapping={...})` call shape, single dict, single call:
```python
def generate_secret(user):
    secret = base64.b32encode(os.urandom(20))
    ciphertext = encrypt_seed(secret)
    user.setMemberProperties(
        mapping={'two_factor_authentication_secret': ciphertext})
    return secret
```
Apply `int(...)` before any epoch/interval value reaches `setMemberProperties` — Pitfall 3 in
RESEARCH.md is a hard rule, not a suggestion: `MutablePropertySheet`'s `'int'` type inspector
is `isinstance(x, int)` and rejects a `float` or `long` loudly (`PropertyValueError`), it does
not coerce.

**No-log-of-secret-material pattern to copy** (`helpers.py::validate_bar_code_reset_token`,
docstring lines 566-599): the existing convention for a security-relevant rejection is to
*omit* the identifying value entirely, not hash or truncate it. MFA-06's replay-log-with-no-
plaintext-username requirement should follow the same convention — a bare
`logger.info('TOTP replay rejected')` with no `username`/`user.getId()` argument at all,
mirroring how `validate_bar_code_reset_token` never logs either operand:
```python
# Source: helpers.py:592-594 docstring, the exact discipline to replicate:
# "Do not log either operand at any level: the stored value is a secret
# that grants a bar-code reset."
```

**Existing logger conventions** (`helpers.py:35`, and call sites at lines 375/644/661/732/777):
```python
logger = logging.getLogger("imio.googleauthenticator")
...
logger.debug(str(e))
logger.debug("Unparseable client IP %r", ip)
```
Use `logger.info(...)` (not `.debug`) for the replay rejection since it is security-relevant,
matching this module's existing `logger.debug` for benign/expected paths vs. reserving a
higher level for anything worth an operator's attention — there is no existing `.info()` call
in `helpers.py` to copy verbatim, so this is a new but consistent usage.

**Format gate — no existing analog, net-new per RESEARCH.md Pattern 2** (write directly in
`helpers.py`, before any `onetimepass` call):
```python
def _is_six_digit_token(token):
    token = token if isinstance(token, basestring) else str(token)
    return token.isdigit() and len(token) == 6
```

**Drift+replay loop — no existing analog, net-new per RESEARCH.md Pattern 1** (pure function,
same file):
```python
from onetimepass import get_hotp
import time

def _find_accepted_interval(token, secret, last_accepted_interval):
    current_interval = int(time.time()) // 30
    for interval in (current_interval, current_interval - 1):
        if get_hotp(secret, intervals_no=interval) == int(token):
            if interval <= last_accepted_interval:
                return None
            return interval
    return None
```

---

### `browser/forms/token.py::handleSubmit` (controller, lockout wrapper)

**Analog:** itself — extend the existing `handleSubmit` (`browser/forms/token.py:61-120`) in
place, following the file's own existing shape rather than introducing a new class or method.

**Existing imports block to extend** (`token.py:1-21`):
```python
from imio.googleauthenticator.helpers import drop_login_failed_msg
from imio.googleauthenticator.helpers import extract_request_data
from imio.googleauthenticator.helpers import validate_token
from imio.googleauthenticator.helpers import validate_user_data
```
Add `get_app_settings` (for `max_failed_attempts`/`lockout_duration`) and `time` alongside
these — same style, one import per helper name, no wildcard.

**Existing handler shape to wrap** (`token.py:61-120`):
```python
@button.buttonAndHandler(_('Verify'))
def handleSubmit(self, action):
    data, errors = self.extractData()
    if errors:
        return False

    token = data.get('token', '')

    user = None
    username = self.request.get('auth_user', '')

    if username:
        user = api.user.get(username=username)
        user_data_validation_result = validate_user_data(
            request=self.request, user=user)
        if not user_data_validation_result.result:
            IStatusMessage(self.request).addStatusMessage(
                _("Invalid data. Details: {0}".format(' '.join(
                    user_data_validation_result.reason))), 'error')
            return

    valid_token = validate_token(token, user=user)

    if valid_token:
        self.context.acl_users.session._setupSession(
            username, self.context.REQUEST.RESPONSE)
        msg = PMF("Welcome! You are now logged in.")
        IStatusMessage(self.request).addStatusMessage(msg, 'info')
        request_data = extract_request_data(self.request)
        context_url = self.context.absolute_url()
        redirect_url = request_data.get('next_url', context_url)
        self.request.response.redirect(redirect_url)
    else:
        msg = _("Invalid token or token expired.")
        IStatusMessage(self.request).addStatusMessage(msg, 'error')
```
Insert the lock-check gate immediately after `user = api.user.get(username=username)` and
*before* `validate_user_data`/`validate_token` are called (RESEARCH.md's Architecture
Diagram, Gate 1) — same generic `"Invalid token or token expired."` message string already
defined at line 119, reused verbatim so a locked account is indistinguishable from a wrong
code. On the success branch, zero the counter with the same
`user.setMemberProperties(mapping={...})` call shape shown above. On the failure branch,
increment the counter and set `locked_until` with the same call shape, still inside this one
method, never in `pas_plugin.py`/`subscribers.py` (MFA-12 invariant).

**Error-handling convention:** this file has no broad `except Exception` today in
`handleSubmit` — do not add one around the new lockout write (RESEARCH.md Pitfall 3 warns this
would mask a real `PropertyValueError`, the exact failure mode `browser/forms/reset_bar_code.py`
demonstrates should be avoided for security-relevant writes).

---

### `browser/forms/reset_bar_code.py::handleSubmit` (controller, same lockout wrapper)

**Analog:** `browser/forms/token.py::handleSubmit`, once it has the lockout wrapper — this is
a second, near-identical application of the same gate, not a new pattern.

**Existing handler to wrap** (`reset_bar_code.py:69-143`):
```python
@button.buttonAndHandler(_('Verify'))
def handleSubmit(self, action):
    data, errors = self.extractData()
    if errors:
        return False

    token = data.get('token', '')
    signature_token = self.request.get('signature', '')
    username = self.request.get('auth_user', '')
    user = api.user.get(username=username)

    if not user:
        ...
        return

    if not is_site_local_user(user):
        ...
        return

    valid_token = validate_token(token, user=user)

    reason = None
    if valid_token:
        try:
            bar_code_reset_token = user.getProperty('bar_code_reset_token')
            if not validate_bar_code_reset_token(bar_code_reset_token, signature_token):
                reason = _("Invalid bar-code reset token.")
                ...
                return
            user.setMemberProperties(mapping={'enable_two_factor_authentication': True,})
            ...
        except Exception:
            logger.exception("Bar-code reset failed for %r", username)
            reason = _("An unexpected error occurred.")
    else:
        reason = _("Invalid token or token expired.")
```
Note this file already has a broad `except Exception: logger.exception(...)` block, but it
wraps only the *post-token* reset-application logic (bar-code-reset-token comparison +
`enable_two_factor_authentication` write), not the token validation itself. The new lock
check and counter write must go **before** `validate_token(token, user=user)` is called (line
109) — same placement rule as `token.py` — and the counter/lock write itself should sit
outside that existing `try/except Exception` block for the same reason given above (Pitfall
3): a masked `PropertyValueError` here would silently disable the very brute-force protection
`reset_bar_code.py` needs most, since MFA-08's scope decision (ROADMAP.md Phase 5 notes)
explicitly names this file as an anonymous TOTP-guessing oracle otherwise.

---

### `browser/controlpanel.py::IGoogleAuthenticatorSettings` (config, 2 new `Int` fields)

**Analog:** itself — the existing three fields on the same interface.

**Full existing interface to extend** (`controlpanel.py:24-55`):
```python
from zope.schema import TextLine, Bool, Text
...
class IGoogleAuthenticatorSettings(Interface):
    ska_secret_key = TextLine(
        title = _("Secret Key"),
        ...
        required = False,
        default = u'',
        )
    globally_enabled = Bool(
        title = _("Globally enabled"),
        ...
        default = True,
        )
    ip_addresses_whitelist = Text(
        title = _("White-listed IP addresses"),
        ...
        default = u'',
        )

    fieldset(
        None,
        label=None,
        fields=['ska_secret_key', 'globally_enabled', 'ip_addresses_whitelist',]
        )
```
Add `from zope.schema import Int` to the existing `from zope.schema import TextLine, Bool,
Text` line (line 7), add `max_failed_attempts`/`lockout_duration` as two more field
assignments in the same style, and append their names to the existing `fields=[...]` list in
the `fieldset(...)` call. **No new form class** — `GoogleAuthenticatorSettingsEditForm`
(`controlpanel.py:57-146`) already renders/saves any field the schema declares via
`AutoExtensibleForm` + `getContent()`/`applyChanges(data)`, confirmed by RESEARCH.md's
"Alternatives Considered" table.

---

### `userdataschema.py::IEnhancedUserDataSchema` (model, 3 new fields)

**Analog:** itself — `two_factor_authentication_secret`/`bar_code_reset_token`, the existing
two-field precedent for adding an automatically-generated, hidden-from-the-user-panel
property.

**Full existing pattern to copy** (`userdataschema.py:20-73`):
```python
class CustomizedUserDataPanel(UserDataPanel):
    def __init__(self, context, request):
        super(CustomizedUserDataPanel, self).__init__(context, request)
        self.form_fields = self.form_fields.omit(
            'enable_two_factor_authentication',
            'two_factor_authentication_secret',
            'bar_code_reset_token',
            )

class IEnhancedUserDataSchema(IUserDataSchema):
    two_factor_authentication_secret = TextLine(
        title = _('Secret key'),
        description = _('Automatically generated'),
        required = False,
    )
    bar_code_reset_token = TextLine(
        title = _('Token to reset the bar code'),
        description = _('Automatically generated'),
        required = False,
    )
```
Add `from zope.schema import Int` (alongside the existing `from zope.schema import Bool,
TextLine` at line 6), declare the three new fields
(`two_factor_authentication_failed_attempts`, `two_factor_authentication_locked_until`,
`two_factor_authentication_last_interval`) as `Int(title=..., required=False)` in the same
style, and add all three names to `CustomizedUserDataPanel.__init__`'s `form_fields.omit(...)`
call — they are internal counters, not user-editable fields, exactly like the two existing
omitted properties.

---

### `profiles/default/memberdata_properties.xml` (config, 3 new `type="int"` entries)

**Analog:** itself, verbatim shape — the file is 6 lines today:
```xml
<?xml version="1.0"?>
<object name="portal_memberdata" meta_type="Plone Memberdata Tool">
  <property name="enable_two_factor_authentication" type="boolean">False</property>
  <property name="two_factor_authentication_secret" type="string"></property>
  <property name="bar_code_reset_token" type="string"></property>
</object>
```
Add three more `<property name="..." type="int">0</property>` lines before `</object>`, one
per new counter, matching this exact indentation/self-closing style. `type="int"` is
mandatory per RESEARCH.md's confirmed `PropertySchema.addType('int', lambda x: x is None or
isinstance(x, int))` — a `float`/`long` value raises `PropertyValueError` on write, and
`type="date"`/`type="float"` are explicitly ruled out (DateTime round-tripping / float
rejection). Default `0`, matching the existing boolean/string defaults' pattern of a safe
falsy value.

---

### `tests/test_helpers.py` (test, extend existing concern-named classes)

**Analog:** `TestSeedEncryption` (`tests/test_helpers.py:223-253`) for the
`setUp`/`tearDown` env-key idiom every TOTP-touching test needs, and `TestSkaSecretKey`
(lines 122-146) for the "one concern-named class per phase's new behaviour" convention this
file already follows (its own docstring says so explicitly).

**setUp/tearDown pattern to copy** (`tests/test_helpers.py:230-253`):
```python
class TestSeedEncryption(unittest.TestCase, BaseTest):
    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self._install()
        login(self.portal, TEST_USER_NAME)

        self._previous_key = os.environ.get(helpers.ENV_VAR_NAME)
        os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()

    def tearDown(self):
        if self._previous_key is None:
            os.environ.pop(helpers.ENV_VAR_NAME, None)
        else:
            os.environ[helpers.ENV_VAR_NAME] = self._previous_key
```

**Required same-commit regression fix** (`tests/test_helpers.py:283-284`, the exact call
Pitfall 2 in RESEARCH.md names):
```python
self.assertTrue(
    validate_token(get_totp(seed), user=user), 'SEC-01 end-to-end')
```
Change to `get_totp(seed, as_string=True)` — confirmed the current call passes a bare,
non-zero-padded `int` that the new exact-6-digit gate will intermittently reject.

**New tests** (drift-accepted, future-rejected, replay-rejected, format-rejected, no-username
log, property round-trip) should each be their own `def test_...` method inside a new or
existing concern-named class (e.g. `TestDriftReplayLockout`), following this file's own stated
convention of grouping by concern rather than by production module.

---

### `tests/test_generic.py` (test, extend control-panel field-presence pattern)

**Analog:** the existing `ska_secret_key` field lookup (`tests/test_generic.py:106-107`):
```python
title = IGoogleAuthenticatorSettings['ska_secret_key'].title
self.assertEqual(translate(title, target_language='nl'), u'Geheime Sleutel')
```
For MFA-10, the equivalent new assertion is schema-level field presence and default, not
translation — e.g. `IGoogleAuthenticatorSettings['max_failed_attempts'].default == 5` and
`IGoogleAuthenticatorSettings['lockout_duration'].default == 900`, using the same
`IGoogleAuthenticatorSettings[...]` subscript idiom already imported at the top of this file
(`from imio.googleauthenticator.browser.controlpanel import IGoogleAuthenticatorSettings`).

---

### `tests/test_token_form.py` (new, real two-request `Browser` sequence)

**Analog:** `tests/test_challenge.py::TestPubBeforeCommitRedirect` — this is the file's own
recommended model (RESEARCH.md names it explicitly), and `tests/base.py::BaseTest` for the
shared browser helpers.

**Shared fixture helpers to reuse, not reimplement** (`tests/base.py:29-37`):
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

**Enrollment fixture to copy** (`tests/test_challenge.py::_enable_2fa`, lines 94-112):
```python
def _enable_2fa(self):
    login(self.portal, TEST_USER_NAME)
    user = api.user.get_current()
    user.setMemberProperties(
        mapping={'enable_two_factor_authentication': True})
    get_or_create_secret(user, overwrite=True)
    transaction.commit()
    return user
```

**Two-request idiom to copy** (`tests/test_challenge.py::test_challenge_fires_on_unauthorized`,
lines 308-351, and `test_pub_before_commit_fires_on_login_post`, lines 158-188): the required
shape for MFA-12's counter-survival test is a `Browser` hitting a protected resource
un-authenticated (or logging in via the login form) to trigger the real
`Unauthorized`→challenge→redirect sequence, *then* a second request (a bad-token POST to the
token form) whose write must be independently re-readable afterward — proving the write
happened on a normally-committing path, not one `transaction.abort()` discarded. Do not
substitute a direct unit-level call to `TokenForm.handleSubmit` for this; RESEARCH.md/
VALIDATION.md are explicit that a unit call never exercises `transactions_manager.commit()`
and cannot prove the survival property.

**`tearDown` reset pattern to copy** (`tests/test_challenge.py:70-92`) — undo the enrollment
flag/secret and commit, so later test classes sharing the layer are not left gated behind 2FA:
```python
def tearDown(self):
    user = api.user.get(username=TEST_USER_NAME)
    if user is not None:
        user.setMemberProperties(mapping={
            'enable_two_factor_authentication': False,
            'two_factor_authentication_secret': '',
        })
        transaction.commit()
    if self._previous_key is None:
        os.environ.pop(helpers.ENV_VAR_NAME, None)
    else:
        os.environ[helpers.ENV_VAR_NAME] = self._previous_key
```
Extend this reset to also zero the three new counters, or a lock/counter set by one test
method will leak into the next.

---

### `tests/test_reset_bar_code.py` (new, same two-request idiom applied to `@@reset-bar-code`)

**Analog:** the same `test_challenge.py` idiom above, retargeted at
`@@reset-bar-code?auth_user=...&signature=...` instead of the login-triggered token form.
`tests/test_request_bar_code_reset.py` (not read in full here — same directory, sibling
*request* form) is the closer file-name match for setUp shape if it establishes a
`bar_code_reset_token`/signature fixture; reuse whatever helper it has for minting a valid
reset signature rather than re-deriving `ska`'s signing key by hand, since `reset_bar_code.py`'s
own `handleSubmit`/`updateFields` already show the exact `validate_bar_code_reset_token`/
`validate_user_data` call shape a test fixture must satisfy to reach the token-validation gate
at all.

---

## Shared Patterns

### Property read/write (memberdata)
**Source:** `helpers.py::get_secret` (lines 217-233), `helpers.py::generate_secret` (lines
182-195), `browser/forms/reset_bar_code.py:128` (`user.setMemberProperties(mapping={...})`)
**Apply to:** every new counter/lock/interval read or write, in `helpers.py`,
`browser/forms/token.py`, and `browser/forms/reset_bar_code.py`
```python
value = user.getProperty('some_property')  # falsy default if undeclared/unset
user.setMemberProperties(mapping={'some_property': int(computed_value)})
```

### No-log-of-security-material discipline
**Source:** `helpers.py::validate_bar_code_reset_token` docstring (lines 592-594)
**Apply to:** MFA-06's replay-rejection log line — omit the username/user id entirely, do not
hash or truncate it as a middle ground
```python
logger.info("TOTP replay rejected")  # no username, no secret, no interval-plus-user tuple
```

### Generic, oracle-safe error message
**Source:** `browser/forms/token.py:119` (`_("Invalid token or token expired.")`)
**Apply to:** the locked-account response in both `token.py` and `reset_bar_code.py` — reuse
this exact existing message string so a locked account is byte-identical to a wrong-code
response, satisfying MFA-08's indistinguishability requirement with zero new i18n string.

### Control-panel field addition, zero new form class
**Source:** `browser/controlpanel.py:24-55` (`IGoogleAuthenticatorSettings`),
`browser/controlpanel.py:57-146` (`GoogleAuthenticatorSettingsEditForm`)
**Apply to:** `max_failed_attempts`/`lockout_duration` — add fields to the interface and its
`fieldset(...)` field list only; the existing `AutoExtensibleForm`-based edit form needs no
change.

### Concern-named test classes, one method per requirement
**Source:** `tests/test_helpers.py`'s own docstrings on `TestSkaSecretKey`/`TestSeedEncryption`
("this file already groups by concern rather than by module"); `tests/test_challenge.py`'s
`TestPubBeforeCommitRedirect` docstring ("one test method per requirement... a failure in one
requirement's assertions does not hide whether the others still pass")
**Apply to:** all new test classes in `test_helpers.py` and the two new test files — name
classes for the behaviour under test (e.g. `TestDriftReplayLockout`,
`TestTokenFormLockout`), not for the production module.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `upgrades/to0301.py` + `upgrades/configure.zcml` `genericsetup:upgradeStep` registration | migration | batch | Directory does not exist in this checkout (`find . -iname '*upgrade*'` empty); `profiles/default/metadata.xml` is `1000`, not `0301`. CLAUDE.md's description of this shape appears to describe a state this repo has not yet reached. If the plan needs a formal upgrade step for the new registry records/memberdata properties, it must be built from `plone.app.genericsetup`'s standard `<genericsetup:upgradeStep source="..." destination="..." handler="..." title="...">` shape registered in `configure.zcml`'s existing `<configure ...>` block (which already has `<genericsetup:importStep>` and `<genericsetup:registerProfile>` entries at lines ~27-42 to place it alongside), plus a Python module with a single `def upgrade(setup_tool):` function — no in-repo file to excerpt from. |

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/` (`helpers.py`, `browser/`,
`browser/forms/`, `userdataschema.py`, `profiles/default/`, `tests/`)
**Files scanned:** `helpers.py` (821 lines, targeted reads), `browser/forms/token.py` (158,
full), `browser/forms/reset_bar_code.py` (188, full), `browser/controlpanel.py` (152, full),
`userdataschema.py` (96, full), `profiles/default/memberdata_properties.xml` (6, full),
`profiles/default/registry.xml` (3, full), `profiles/default/metadata.xml` (6, full),
`tests/test_helpers.py` (615, targeted reads), `tests/test_generic.py` (359, targeted reads),
`tests/test_challenge.py` (351, targeted reads), `tests/base.py` (37, full)
**Pattern extraction date:** 2026-07-31
