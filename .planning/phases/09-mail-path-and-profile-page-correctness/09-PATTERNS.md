# Phase 9: Mail Path and Profile-Page Correctness - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 4 modified source files + 3 test files (additions to existing suites)
**Analogs found:** 7 / 7 — every analog is in-file (the surrounding code in the same
method/module) or in-suite (an existing test in the same test file). No new file is created in
this phase, so there is no cross-module "closest match" search to do — the closest analog to
each edit is almost always the code immediately around it.

## File Classification

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|----------------|------|-----------|-----------------|---------------|
| `browser/forms/request_bar_code_reset.py` (BUG-07) | controller (z3c.form button handler) | request-response | the method's own `except ValueError:` arm + shared `if reason is not None:` tail, same file lines 130-140 | exact (in-file) |
| `userdataschema.py` (BUG-08) | model (zope.schema field on a schema interface) | CRUD (static field, no runtime flow) | the sibling `two_factor_authentication_secret` / `bar_code_reset_token` field declarations in the same schema, lines 85-99 | exact (in-file) |
| `browser/forms/recovery_codes.pt` (UX-01) | component (Page Template) | request-response (rendered once, no round-trip) | `profiles/default/actions.xml` lines 11/24/45 (`globals_view/navigationRootUrl` idiom) | role-match (XML action property vs. TAL attribute, identical `${...}` interpolation) |
| `helpers.py::get_token_description()` (UX-02) | utility (string builder called from a view) | transform | `get_or_create_secret()` two functions above it, same file lines 305-327 | exact (in-file, same module, adjacent function it already calls) |
| `tests/test_request_bar_code_reset.py` (BUG-07 test) | test | request-response | `_submit_reset_request` + `test_successful_request_keeps_the_caller_on_the_form`, same file lines 30-121 | exact (in-file harness reuse) |
| `tests/test_user_setup.py` (UX-01 + UX-02 tests) | test | request-response | `test_recovery_codes_are_issued_once_at_enrollment`, same file lines 373-413 | exact (in-file harness reuse) |
| `tests/test_adapter.py` or new `tests/test_userdataschema.py` (BUG-08 test) | test | CRUD (schema introspection, no request) | `test_adapter.py` lines 40-48 (`getFieldNames(IEnhancedUserDataSchema)` pattern) | role-match |

## Pattern Assignments

### `browser/forms/request_bar_code_reset.py` (controller, request-response) — BUG-07

**Analog:** the same method, `handleSubmit`, lines 51-141 — this is an in-file fix, not a
cross-file port. Current exact source (verified this session, unchanged from RESEARCH.md):

**Imports** (lines 1-24, what to add to):
```python
from imio.googleauthenticator.helpers import get_ska_secret_key
from plone import api
from plone.directives import form
from plone.z3cform.layout import wrap_form
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from ska import RequestHelper
from ska import Signature
from smtplib import SMTPRecipientsRefused
from z3c.form import button
from z3c.form import field
from zope.i18nmessageid import MessageFactory
from zope.schema import TextLine

import logging
```
Add `from smtplib import SMTPException` and `import socket` alongside the existing
`from smtplib import SMTPRecipientsRefused` line; the narrow import can be dropped once the
tuple catch replaces it (nothing else in the file references `SMTPRecipientsRefused`).

**Bug site, exact current lines 87-113** (this is the code to change; the fix inlines directly
here, not copied from elsewhere):
```python
                # Now we need to send an email to user with URL in and a small explanations.
                try:
                    host = getToolByName(self, 'MailHost')

                    mail_text = self.mail_text_template(
                        member=user,
                        bar_code_reset_url=signed_url,
                        charset='utf-8'
                        )
                    mail_text = mail_text.format(bar_code_reset_url=signed_url)

                    # ``charset`` is not optional in practice: ... (comment, keep as-is)
                    host.send(
                        mail_text,
                        immediate=True,
                        charset='utf-8',
                        msg_type='text/html'
                        )
                except SMTPRecipientsRefused:
                    raise SMTPRecipientsRefused('Recipient address rejected by server')
```

**Shared failure-reporting tail to route into instead (lines 136-140), copy the shape of the
existing `except ValueError:` arm (lines 130-132) as the template for the new `except`:**
```python
            except ValueError:
                logger.exception("Bar-code reset request failed for %r", username)
                reason = _("An unexpected error occurred.")
        else:
            reason = _("Invalid username.")

        if reason is not None:
            IStatusMessage(self.request).addStatusMessage(
                _("Request for bar-code reset is failed! {0}".format(reason)),
                'error'
                )
```

**Concrete fix shape** (D-09/D-10/D-11; move the success message inside the inner `try:` per
Pitfall 1 in RESEARCH.md so it cannot fire alongside the new error path):
```python
                try:
                    host = getToolByName(self, 'MailHost')
                    mail_text = self.mail_text_template(
                        member=user, bar_code_reset_url=signed_url, charset='utf-8')
                    mail_text = mail_text.format(bar_code_reset_url=signed_url)
                    host.send(mail_text, immediate=True, charset='utf-8', msg_type='text/html')
                    IStatusMessage(self.request).addStatusMessage(
                        _("An email with instructions on resetting your bar-code is sent successfully."),
                        'info')
                except (SMTPException, socket.error):
                    logger.exception("Bar-code reset request failed to send for %r", username)
                    reason = _("An unexpected error occurred.")
```
Note the pre-existing success-message call currently sits *after* this inner try/except, still
inside the outer `try:` (lines 126-129) — moving it inside the inner `try:` is part of the fix,
not an unrelated refactor.

**Error handling pattern to copy:** `logger.exception(...)` + set `reason` to the shared
`_("An unexpected error occurred.")` message, exactly as the existing `except ValueError:` arm
does two lines below (lines 130-132) — do not invent a new message string (D-11).

---

### `userdataschema.py` (model, CRUD) — BUG-08

**Analog:** the sibling schema fields in the same interface, same file lines 85-99 — this is a
deletion inside an existing field, not a port from elsewhere.

**Current field (lines 76-83, to be edited):**
```python
    enable_two_factor_authentication = Bool(
        title=_('Enable two-step verification.'),
        description=_("""Enable/disable the two-step verification. Click <a href=\"@@setup-two-factor-authentication\"> """
                      """here</a> to set it up or <a href=\"@@disable-two-factor-authentication\">here</a> to """
                      """disable it."""
            ),
        required=False
        )
```

**Sibling field style to match for the replacement (lines 85-90, e.g. how a short plain
description is written elsewhere in this same schema):**
```python
    two_factor_authentication_secret = TextLine(
        title=_('Secret key'),
        description=_('Automatically generated'),
        required=False,
    )
```

**Fix shape (D-14/D-15):**
```python
    enable_two_factor_authentication = Bool(
        title=_('Enable two-step verification.'),
        description=_('Enable/disable the two-step verification.'),
        required=False
        )
```

**Evidence for why this is safe to delete outright (`CustomizedUserDataPanel.__init__`, lines
21-42 — the `omit()` call proper is lines 38-42):**
```python
    def __init__(self, context, request):
        super(CustomizedUserDataPanel, self).__init__(context, request)

        # Removing certain fields from form.
        #
        # This omit() only covers the view it is registered for,
        # ``personal-information``. It is NOT a general protection: ...
        self.form_fields = self.form_fields.omit(
            'enable_two_factor_authentication',
            'two_factor_authentication_secret',
            'bar_code_reset_token',
            )
```

---

### `browser/forms/recovery_codes.pt` (component, request-response) — UX-01

**Analog:** `profiles/default/actions.xml` lines 11/24/45 — the package's existing
`globals_view/navigationRootUrl` idiom, already used three times, just in a CMF action
`url_expr` property rather than a page-template `tal:attributes`. Same `${...}` TAL
interpolation mechanics in both places.

**Analog excerpt (`actions.xml:10-11`):**
```xml
   <property
      name="url_expr">string:${globals_view/navigationRootUrl}/@@setup-two-factor-authentication</property>
```

**Current template link to change (lines 23-26):**
```html
  <p>
    <a tal:attributes="href string:${context/absolute_url}/@@personal-information"
       i18n:translate="">Continue to your profile</a>
  </p>
```

**Fix shape (D-01/D-02/D-04):**
```html
  <p>
    <a tal:attributes="href string:${globals_view/navigationRootUrl}"
       i18n:translate="">Continue to the home page</a>
  </p>
```
No `@@personal-information` suffix — D-01 sends the user to the home page itself, not to a
page under it.

---

### `helpers.py::get_token_description()` (utility, transform) — UX-02

**Analog:** `get_or_create_secret()`, the function immediately above it in the same module
(lines 305-327) — already called by `get_token_description` for the QR, so no new call is
needed, only reuse of the value already fetched.

**Current function (lines 330-348, to be extended):**
```python
def get_token_description(user=None, overwrite_secret=False):
    """
    Gets description with bar code image.

    :param Products.PlonePAS.tools.memberdata user:
    :return string:
    """
    request = getRequest()

    if user is None:
        user = api.user.get_current()

    return '<div><img src="{url}" alt="QR Code" /></div>'.format(
        url=get_barcode_image(
            get_username(user),
            get_domain_name(request),
            get_or_create_secret(user, overwrite=overwrite_secret)
        ),
    )
```

**Fix shape (D-07/D-08), capturing the secret once and reusing it for both the QR and the new
text (mirrors how `get_or_create_secret(user, overwrite=overwrite_secret)` was already the
single call site — do not call it twice):**
```python
def get_token_description(user=None, overwrite_secret=False):
    request = getRequest()
    if user is None:
        user = api.user.get_current()

    secret = get_or_create_secret(user, overwrite=overwrite_secret)
    return (
        '<div><img src="{url}" alt="QR Code" /></div>'
        '<p>{label} <code>{secret}</code></p>'
    ).format(
        url=get_barcode_image(get_username(user), get_domain_name(request), secret),
        label=_(u"Setup key:"),
        secret=secret,
    )
```
Renders unescaped because the z3c.form field-description slot uses `tal:content="structure
description"` (`plone.app.z3cform-0.7.8`'s `widget.pt:23-29`, verified in RESEARCH.md) — the
same mechanism that already renders the `<img>` tag as an image, not literal text. No template
change, no new field (D-08's rejected alternatives).

Note `helpers.py` has no `_ = MessageFactory(...)` import visible in the excerpt above — check
the top of `helpers.py` for its existing message-factory alias before adding the `_(u"Setup
key:")` call; use whatever name the file already binds (the project convention throughout this
package is `_ = MessageFactory('imio.googleauthenticator')`, per every other file read this
session).

---

### `tests/test_request_bar_code_reset.py` — BUG-07 test

**Analog:** `_submit_reset_request` (lines 30-56) and
`test_successful_request_keeps_the_caller_on_the_form` (lines 84-121), same file.

**Harness to copy verbatim, then make the inner function raise instead of capture:**
```python
    def _submit_reset_request(self, username):
        """Drive the real form handler and return the messages MailHost was
        asked to deliver.
        ...
        """
        sent = []

        def _capture(inner_self, mfrom, mto, messageText, immediate=False):
            sent.append(messageText)

        original_send = MailBase._send
        MailBase._send = _capture
        try:
            request = self.layer['request']
            request.form['form.widgets.username'] = username
            request.form['form.buttons.submit'] = u'Submit'
            form = RequestBarCodeResetForm(self.portal, request)
            form.update()
        finally:
            MailBase._send = original_send

        return sent
```
**Raising variant (new helper or a sibling with a `raise` in place of `sent.append(...)`):**
```python
        def _raise(inner_self, mfrom, mto, messageText, immediate=False):
            raise SMTPRecipientsRefused('Recipient address rejected by server')
```
(also exercise `socket.error(...)` in a second scenario per D-09's "every SMTP-level and
network-level" wording — same substitution, different exception raised).

**Assertion pattern to copy (`test_successful_request_keeps_the_caller_on_the_form`, lines
100-121):**
```python
        request = self.layer['request']
        IStatusMessage(request).show()  # drain prior messages

        self._submit_reset_request(TEST_USER_NAME)  # or the raising variant

        self.assertIsNone(
            request.response.getHeader('Location'),
            '...')
        messages = [m.message for m in IStatusMessage(request).show()]
        self.assertEqual(
            [u'Request for bar-code reset is failed! An unexpected error occurred.'],
            messages,
            'The caller was not told about the send failure on a page they can see.')
```
Must additionally assert `messages` does NOT contain the success string (Pitfall 1 guard, per
RESEARCH.md) — mirror by asserting the list has exactly one entry and that entry is the error
message, as the pattern above already does via `assertEqual` on the full list rather than
`assertIn`.

**Non-vacuity requirement (D-13):** run this test against the byte-identical unfixed source
first (confirm it goes red — either an uncaught `SMTPRecipientsRefused`/`socket.error`
escaping `form.update()`, or the wrong message), then restore and apply the real fix.

---

### `tests/test_user_setup.py` — UX-01 and UX-02 tests

**Analog:** `test_recovery_codes_are_issued_once_at_enrollment` (lines 373-413), same file —
the existing form-render-and-inspect-markup pattern.

**Pattern to copy (build via `_build_form`, drive `handleSubmit`, call `form.render()`, assert
on markup substrings):**
```python
    def test_recovery_codes_are_issued_once_at_enrollment(self):
        real_validate_token = user_setup.validate_token
        user_setup.validate_token = lambda *args, **kwargs: True
        try:
            form = self._build_form('123456')
            SetupForm.handleSubmit.func(form, None)
        finally:
            user_setup.validate_token = real_validate_token
        self._clear_location()

        codes = form.issued_recovery_codes
        ...
        markup = form.render()
        for code in codes:
            self.assertIn(code, markup, '...')
        self.assertIn('shown only this one time', markup, '...')
```

**UX-01 test (extend or add sibling, same shape):** after the same `form.render()` call, assert
the new link text and target appear:
```python
        markup = form.render()
        # existing recovery-code assertions...
        # UX-01:
        self.assertNotIn('Continue to your profile', markup)
        self.assertIn('Continue to the home page', markup)
```
Rendering `recovery_codes.pt` needs `form.render()` on the already-built `SetupForm`, same call
already used in the analog — no new fixture.

**UX-02 test (new method, no `handleSubmit` needed — this is a GET-render concern via
`updateFields`, matching the comment already in the file at lines 98-110 about
`updateFields() -> get_token_description() -> get_domain_name()`):**
```python
    def test_setup_form_shows_the_secret_as_text(self):
        form = self._build_form('')
        form.update()  # runs updateFields(), which calls get_token_description()
        secret = helpers.get_or_create_secret(api.user.get_current(), overwrite=False)
        description = form.fields.get('qr_code').field.description
        self.assertIn(secret, description)
```
`helpers.get_or_create_secret` and `api` are already imported in this test module per the
`updateFields() -> get_token_description() -> get_or_create_secret` comment trail cited above —
confirm the exact import names in the file before writing (`helpers` module alias, `api` from
`plone`).

---

### `tests/test_adapter.py` (or new `tests/test_userdataschema.py`) — BUG-08 test

**Analog:** the existing `getFieldNames(IEnhancedUserDataSchema)` pattern, `test_adapter.py`
lines 40-48 — no Zope request/traversal needed, this is a plain schema-attribute assertion
(cheapest form per RESEARCH.md's Wave 0 note).

**Pattern to copy (structure, not literal names — re-read `test_adapter.py:1-50` before
writing to match its actual imports and class):**
```python
from imio.googleauthenticator.userdataschema import IEnhancedUserDataSchema
...
    def test_enable_two_factor_authentication_description_has_no_wrong_account_links(self):
        """BUG-08: the field description renders only on @@user-information
        (CustomizedUserDataPanel.omit() does not cover it), and neither link
        there acts on the viewed user -- both act on api.user.get_current().
        """
        description = IEnhancedUserDataSchema[
            'enable_two_factor_authentication'].description
        self.assertNotIn('@@setup-two-factor-authentication', description)
        self.assertNotIn('@@disable-two-factor-authentication', description)
```
D-17: assert absence of both view names, not the replacement wording.

## Shared Patterns

### Failure-message reuse (BUG-07)
**Source:** `request_bar_code_reset.py`'s existing `except ValueError:` arm (lines 130-132) and
the shared `if reason is not None:` tail (lines 136-140).
**Apply to:** the new `except (SMTPException, socket.error):` arm — same `reason = _(...)`
assignment, same `logger.exception(...)` call, no new message string, no new reporting path.

### `globals_view/navigationRootUrl` for "home page" URLs
**Source:** `profiles/default/actions.xml` lines 11, 24, 45.
**Apply to:** `recovery_codes.pt`'s link (UX-01). This is now the package's only precedent for
"home page" and should be treated as the idiom to reuse anywhere else "home" needs resolving in
this milestone.

### Non-vacuity test convention
**Source:** established every prior phase (per `08-CONTEXT.md`), restated in D-13.
**Apply to:** both new BUG-07 and BUG-08 tests — prove red against unmodified source, then
restore byte-identical before applying the real fix.

### `MailBase._send` monkeypatch harness
**Source:** `tests/test_request_bar_code_reset.py:30-56`, with its own comment explaining why
`_send` (not the whole `MailHost`) is patched.
**Apply to:** the new BUG-07 raising-variant test — reuse the same patch/restore shape, just
swap the inner function's body.

## No Analog Found

None. All seven edit/test sites have an exact or role-matched analog in the same file or same
test module — expected for a phase described in CONTEXT.md as "four independent corrections,"
none of which introduces a new pattern shape.

## Metadata

**Analog search scope:** the four target source files and their existing test files only — no
broader codebase search was needed or useful, since CONTEXT.md and RESEARCH.md already pin exact
line numbers for every fix site and its immediate surrounding pattern.
**Files scanned:** `request_bar_code_reset.py`, `userdataschema.py`, `recovery_codes.pt`,
`helpers.py` (lines 300-355), `actions.xml`, `test_request_bar_code_reset.py`,
`test_user_setup.py` (lines 1-450), `test_adapter.py` (lines 1-110), `user_setup.py`
(grep only, redirect_url/updateFields sites).
**Pattern extraction date:** 2026-08-06
