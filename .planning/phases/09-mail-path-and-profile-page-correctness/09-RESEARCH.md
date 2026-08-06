# Phase 9: Mail Path and Profile-Page Correctness - Research

**Researched:** 2026-08-06
**Domain:** Plone 4.3 / Python 2.7 PAS-plugin bugfix and usability phase — no new stack, no new
dependency. Four independent, single-file corrections against shipped v1.0 code.
**Confidence:** HIGH — every factual claim below was checked against the live source tree, the
buildout's installed eggs, or a `python2.7 -c` interpreter probe. This phase needed no external
web research; all four fixes are local-codebase questions, and CONTEXT.md's 17 decisions already
settle every design choice. This document's job is verification, not exploration.

## Summary

CONTEXT.md's decisions (D-01..D-17) all hold up against the actual source — no factual claim in
CONTEXT.md was contradicted by this research. The one gap CONTEXT.md does not close is *how* the
z3c.form field-description slot renders markup, which decides whether D-08's approach (append the
base32 secret to the HTML string `get_token_description()` already returns) actually produces
copyable text rather than escaped `&lt;code&gt;` tags on the page. This research traced that
slot into the installed `plone.app.z3cform-0.7.8` egg and confirms it renders `structure`
(raw HTML, unescaped) — D-08 works exactly as designed, and needs no template change, no new
field, and no escaping logic.

The other three fixes are equally mechanical once traced: BUG-07 needs one `except` clause
widened from a single re-raise to a tuple that also catches `socket.error` (verified in this
session: a Python 2.7 `smtplib.SMTPRecipientsRefused` is an `SMTPException`, but a refused
*connection* raises `socket.error`, which is not); BUG-08 is a two-line deletion inside a
docstring-sentence in `userdataschema.py`, already proven to be the *only* rendering path by the
`omit()` call three lines above it; UX-01 is a one-line `href` swap plus a one-word text change in
a template that already has a working `navigationRootUrl` idiom to copy three lines away, in
`actions.xml`.

**Primary recommendation:** Implement all four as small, independent, single-file diffs, in any
order. Each ships its own test. No shared risk between them — they touch disjoint files
(`request_bar_code_reset.py`, `userdataschema.py`, `recovery_codes.pt`, `helpers.py` +
`user_setup.py`'s consumption of it) and none depends on the others landing first.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Retarget the existing link on the recovery-codes page. `recovery_codes.pt:24` currently
reads `href="string:${context/absolute_url}/@@personal-information"` with text "Continue to your
profile". That link becomes the home-page link. Nothing else in the enrollment flow changes.
Rejected: an acknowledge-button-then-redirect (new form handler for a criterion a link already
satisfies); a second link beside the existing one (two links do not decide where the user *ends
up*).

**D-02:** "Home page" resolves through `globals_view/navigationRootUrl`, the same expression
`profiles/default/actions.xml` already uses on all three of this package's action URLs (lines
11, 24, 45). Rejected: the bare `context/absolute_url` already in the template (wrong once
reached from a folder URL); the true portal root (wrong inside a subsite).

**D-03:** The refusal redirect at `user_setup.py:91-93` (T-03-23, non-site-local account) stays
put. Not touched by this phase.

**D-04:** The link text becomes "Continue to the home page." Retires msgid "Continue to your
profile", adds a new one — a Phase 13 (I18N-02) input.

**Hard constraint on D-01..D-04:** The success path in `user_setup.py::handleSubmit` leaves
`redirect_url = None` deliberately (`user_setup.py:162-176`). `plone.z3cform` 0.8.1's
`FormWrapper.update()` blanks the wrapped form only on a 302/303 response. UX-01 must be reached
from the recovery-codes page, not by restoring a redirect in `handleSubmit`.

**D-05:** UX-02 stays in Phase 9 (settles REQUIREMENTS.md open question 4). The QR already
encodes the same secret with no gate at all; the text adds no new secret to the page.

**D-06:** Always visible beside the QR, no reveal control, no JavaScript, no
`jsregistry.xml` change. Rejected: `<details>` disclosure; a JS reveal button.

**D-07:** Show the base32 secret only, not the `otpauth://` URI. It is exactly what
`helpers.get_or_create_secret()` already returns — no new formatting code. Rejected: the full URI
(long, some clients reject it); showing both (two representations for a case neither alone
fails).

**D-08:** Produced by extending `helpers.get_token_description()` (`helpers.py:330-348`), whose
return value `SetupForm.updateFields` already assigns to the `qr_code` field's description. Keeps
the change inside the site-local branch of `user_setup.py:196-210` (actual verified lines:
196-212), so a Zope-root account still gets the T-03-23 refusal and mints no seed. Rejected: a
second read-only field on `ISetupForm` (needs its own `get_or_create_secret()` call and its own
non-site-local guard); rendering from a page template (`SetupForm` has none today).

**D-09:** Catch every SMTP-level and network-level send failure, not only
`SMTPRecipientsRefused`. Verified in this session's Python 2.7:
`SMTPRecipientsRefused → SMTPException → Exception`, and a refused connection raises
`socket.error`, which is not an `SMTPException`. Reversible — one `except` clause in one method.

**D-10:** Delete the inner `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)`
re-raise entirely. The send failure reaches the method's shared `if reason is not None:` tail.

**D-11:** Reuse the existing message `_("An unexpected error occurred.")` — the same one the
`except ValueError` arm sets. Adds no msgid (nothing for Phase 13 to inherit); avoids widening the
username-enumeration oracle (T-03-26) with a distinct "could not email that address" message.
Log the real cause with `logger.exception`.

**D-12:** The already-written `bar_code_reset_token` (`request_bar_code_reset.py:85`) is not
rolled back on a send failure. A stored token grants nothing without the `ska` signature that
went into the undelivered email; rolling it back is machinery for no gain.

**D-13:** The test reuses the existing harness: `tests/test_request_bar_code_reset.py` already
patches `Products.MailHost.MailHost.MailBase._send`. The new test makes that patch raise, and
asserts the error status message appears and no exception escapes. Needs the project's standard
non-vacuity check: prove it goes red against the unfixed source, then restore byte-identical.

**D-14:** Delete both links from the field description outright; do not make it conditional. The
deciding fact, verified in the source: `CustomizedUserDataPanel.__init__`
(`userdataschema.py:38-42` — note: verified line range is 38-42, not 21-42; see Verification
Findings) omits `enable_two_factor_authentication` from `@@personal-information`. The **only**
form that renders this description is `@@user-information`. Rejected: a conditional description
(a `zope.schema` field description is a static class attribute evaluated at import time; varying
it per request needs a custom widget or form override). Reversible — one string literal.

**D-15:** The replacement description is the first sentence already there: "Enable/disable the
two-step verification." The "Click here … or here …" sentence goes.

**D-16:** Do not hand-edit the `.po`/`.pot` catalogues in this phase. The old msgid is orphaned
after D-15 — verified present at `imio.googleauthenticator.pot:75` and
`fr/LC_MESSAGES/imio.googleauthenticator.po:76-77` (with a real French translation on line 77).
The field description on `@@user-information` will read in English for a French user until
Phase 13 rebuilds the catalogue. Accepted consequence, not a defect to patch here.

**D-17:** The test asserts absence, not wording: neither `@@setup-two-factor-authentication` nor
`@@disable-two-factor-authentication` appears in the rendered description.

### Claude's Discretion

Two areas the operator chose not to discuss (BUG-07's exact exception handling shape, D-09..D-13;
and BUG-08's exact fix mechanics, D-14..D-17) — both already decided above and not reopened by
this research.

### Deferred Ideas (OUT OF SCOPE)

- Refusing a mismatched `userid` at `@@setup-two-factor-authentication` and
  `@@disable-two-factor-authentication` themselves. Already a Future Requirement in
  REQUIREMENTS.md. Residual risk, unchanged by this phase: a bookmarked or hand-typed
  `@@disable-two-factor-authentication` URL still silently disables the clicker's own second
  factor and reports success.
- Sweeping the orphaned msgids left by D-15. Phase 13 owns catalogue rebuilds.
- `profiles/default/site_properties.xml` — recorded dead in Phase 1, still dead, still tied to no
  requirement.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BUG-07 | Rejected recipient produces the same in-page failure message every other failure path uses | Verified exact `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)` at lines 112-113; confirmed exception hierarchy live; confirmed the shared `if reason is not None:` tail at lines 136-140; confirmed existing mail-failure test harness at lines 30-56 |
| BUG-08 | Admin viewing another user's profile is offered no set-up/disable link that acts on the admin's own account | Verified `CustomizedUserDataPanel.__init__`'s `omit()` call (lines 38-42) does not cover `@@user-information`; verified the two links live only in the field description (lines 76-83); traced the orphaned-msgid consequence in all three catalogues |
| UX-01 | User ends on the site home page after enrollment, not their profile | Verified `recovery_codes.pt:23-26` link markup; verified `user_setup.py`'s no-redirect success path (lines 162-176) and its `redirect_url = None` binding (line 150); verified `navigationRootUrl` precedent in `actions.xml:11,24,45` |
| UX-02 | Enrollment page shows the TOTP secret as selectable text beside the QR | Verified `get_token_description()` (lines 330-348) already holds the base32 secret via `get_or_create_secret()`; verified (new this session) that the z3c.form field-description slot renders `structure` (raw HTML), so appended markup is not escaped |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Mail-send failure reporting (BUG-07) | Backend / Browser view (`RequestBarCodeResetForm.handleSubmit`) | — | Failure handling is entirely inside one z3c.form button handler; no other tier is involved — MailHost is a local Zope tool, not an external service boundary this package owns |
| Profile field description content (BUG-08) | Backend / Zope schema (`zope.schema` field on `IEnhancedUserDataSchema`) | Browser template (rendering) | The vulnerable surface is a static schema attribute rendered by `plone.app.users`' own `@@user-information` view, which this package does not control — the fix must live in the data the schema exposes, not in a view this package cannot safely override without duplicating `plone.app.users` machinery |
| Post-enrollment redirect target (UX-01) | Browser template (`recovery_codes.pt`) | — | Purely a link `href` and its label; no server-side routing logic changes |
| Secret display (UX-02) | Backend helper (`helpers.get_token_description`) | Browser form (`SetupForm.updateFields` consumption) | The secret is already computed and cached server-side (`get_or_create_secret`); the fix is what that helper returns, not a new client-side reveal or a new schema field |

## Verification Findings (source-of-truth check against CONTEXT.md)

All line-number and behavioral claims in CONTEXT.md were checked directly against
`src/imio/googleauthenticator/`. Result: **every substantive claim holds.** Two claims needed a
small correction (both are off-by-a-few-lines citation slips, not factual errors), and one gap
in CONTEXT.md (the z3c.form escaping question, open by omission) is now closed. Details:

### 1. `request_bar_code_reset.py` — full mail-send arm (confirmed exactly as described)

```python
# lines 106-113 (exact, current source)
                    host.send(
                        mail_text,
                        immediate=True,
                        charset='utf-8',
                        msg_type='text/html'
                        )
                except SMTPRecipientsRefused:
                    raise SMTPRecipientsRefused('Recipient address rejected by server')
```
- Exception class import: `from smtplib import SMTPRecipientsRefused` at line 13.
- The outer `except ValueError:` arm is lines 130-132; it sets
  `reason = _("An unexpected error occurred.")` and calls `logger.exception(...)`.
- The shared tail is lines 136-140:
  ```python
  if reason is not None:
      IStatusMessage(self.request).addStatusMessage(
          _("Request for bar-code reset is failed! {0}".format(reason)),
          'error'
          )
  ```
- The `bar_code_reset_token` write CONTEXT.md cites at line 85 is exactly there:
  `user.setMemberProperties(mapping={'bar_code_reset_token': str(signature)})`.
- Structurally: the outer `try:` (opens line 63) wraps signature generation, the mail send, and
  the success status message. The inner `try/except SMTPRecipientsRefused` (lines 88-113) is
  nested inside it. Because `SMTPRecipientsRefused` is not a `ValueError`, the re-raise at line
  113 propagates straight past the outer `except ValueError:` and out of `handleSubmit` entirely
  — confirmed unhandled, confirmed produces a bare error page (z3c.form's button handler has no
  enclosing try of its own here).
- **CONTEXT.md's citation was exact:** "lines 112-113" is precisely the `except`/`raise` pair.

**Fix shape implied (D-09/D-10):** replace lines 112-113 with a tuple catch that also covers
`socket.error`, dropping the re-raise so execution falls through to the outer `try`'s implicit
success path being skipped and the exception being swallowed into a `reason`-setting arm. Because
Python 2.7's `except (SMTPException, socket.error):` needs both names imported, add
`from smtplib import SMTPException` and `import socket` (or `from socket import error as
SocketError` if the project prefers no bare `socket` import — no existing convention favors
either in this file; `pas_plugin.py` and `helpers.py` were not checked for a project-wide
preference and none is asserted in CONTEXT.md). Recommend:

```python
from smtplib import SMTPException
import socket
...
                except (SMTPException, socket.error):
                    logger.exception("Bar-code reset request failed to send for %r", username)
                    reason = _("An unexpected error occurred.")
```

This still needs the *outer* `except ValueError:` arm preserved (it catches `ValueError` from
signature generation, a separate failure mode upstream of the mail send) — the new
`except (SMTPException, socket.error):` must sit at the same nesting level as the current
`except SMTPRecipientsRefused:` (inside the inner `try:`, around the `host.send(...)` call only),
**not** replace the outer `except ValueError:`. Setting `reason` inside the inner except means the
success-path `IStatusMessage` call at lines 126-129 (which is *after* the inner try/except in the
same outer try block) must not execute after a send failure — confirm by reading the current
control flow again: lines 126-129's `IStatusMessage(...)` call is **outside** the inner
`try/except` (it follows it, still inside the outer `try:`). Setting `reason` inside the inner
`except` and then falling through would still execute the success message afterward unless the
inner except also returns/re-raises or the code is restructured so the success message is
skipped. **This is a real control-flow subtlety the planner must resolve** — either:
(a) move the success-message call inside the inner `try:` block (immediately after `host.send`,
before the `except`), so a send failure short-circuits past it naturally, or
(b) have the new `except` clause set `reason` and then explicitly return/skip to the shared tail
(e.g. via an early `return` after adding the status message, since `reason is not None` handling
is idempotent whether or not the success message also ran — but that would show the user *both*
messages, which is wrong).
Option (a) is the minimal-diff fix and matches the existing shape of the `except ValueError:` arm,
which also relies on the try block's remaining statements simply not running once an exception is
raised. **Flag this for the planner as an implementation-order detail inside D-09/D-10, not a new
decision** — CONTEXT.md's decisions describe *what* to catch and *what message* to show, not this
statement-ordering nuance, which only becomes visible when actually rewriting the lines.

### 2. `userdataschema.py` — field description and `CustomizedUserDataPanel`

Confirmed field description exactly as CONTEXT.md states, lines 76-83:
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

`CustomizedUserDataPanel.__init__` — **verified, with a small line-range correction.** CONTEXT.md
cites "`userdataschema.py:21-42`" for the class as a whole (accurate — the class starts at line
21) but the `omit()` call itself is lines 38-42, not "21-42" as the fix-site citation in
`<canonical_refs>` implies for the omit specifically:
```python
class CustomizedUserDataPanel(UserDataPanel):          # line 21
    def __init__(self, context, request):              # line 25
        super(CustomizedUserDataPanel, self).__init__(context, request)   # line 26
        # [comment, lines 28-37]
        self.form_fields = self.form_fields.omit(       # line 38
            'enable_two_factor_authentication',         # line 39
            'two_factor_authentication_secret',          # line 40
            'bar_code_reset_token',                      # line 41
            )                                            # line 42
```
This is a citation-range nuance only (the class body is 21-42; the `omit()` call proper is
38-42) — it does not change D-14's conclusion, which this research confirms: the comment at
lines 28-37 explicitly states this `omit()` "only covers the view it is registered for,
`personal-information`" and that `@@user-information` "is not overridden here and renders
whatever the schema declares." **CONTEXT.md's claim holds exactly.**

### 3. `recovery_codes.pt` — link markup (confirmed exactly)

```html
  <p>
    <a tal:attributes="href string:${context/absolute_url}/@@personal-information"
       i18n:translate="">Continue to your profile</a>
  </p>
```
Lines 23-26 exactly as CONTEXT.md's canonical_refs cites. The `i18n:translate=""` attribute with
no explicit value means the msgid is auto-derived from the tag's text content ("Continue to your
profile") by i18ndude at extraction time — **but this string is not currently present in any
catalogue** (see Additional Finding below). D-04's rewrite to
`href="string:${globals_view/navigationRootUrl}/@@personal-information".../"Continue to the home
page"` follows the `actions.xml` idiom exactly (see finding 7 below) — no `context/absolute_url`
form of `navigationRootUrl` exists to copy; the three existing uses are all in the CMF-action TAL
expression form `${globals_view/navigationRootUrl}`, which is directly reusable inside a page
template's `tal:attributes` the same way `context/absolute_url` is used today.

### 4. `user_setup.py` — `updateFields` and the no-redirect comment (confirmed, with one line-range correction)

`updateFields` is lines 189-212 (CONTEXT.md's canonical_refs says "189-212" — exact). The
no-redirect comment block is lines 164-176 in the currently-read source, not "162-176" as cited —
line 162 is a `# TODO:` comment about a different concern (resolving the setup URL), and the
RECOV-03 comment block proper starts at line 164 (`# RECOV-03: redirect_url is None only on the
success path above,`). This is a one-line citation slip, not a factual problem — the content
CONTEXT.md describes is exactly there:
```python
        # RECOV-03: redirect_url is None only on the success path above,
        # deliberately -- skipping the redirect on that one path is the
        # entire mechanism the one-time code display depends on.
        # plone.z3cform 0.8.1's FormWrapper.update() (site-packages/
        # plone/z3cform/layout.py, lines 39-60 of the pinned egg) blanks
        # the wrapped form's contents and returns early only when
        # self.request.response.getStatus() is 302 or 303; leaving the
        # response at its default 200 here is sufficient for render() to
        # run normally in this same response. Do not "tidy" this back into
        # an unconditional redirect.
        if redirect_url is not None:
            self.request.response.redirect(redirect_url)
```
This confirms the constraint on D-01..D-04 precisely: `recovery_codes.pt` (not a redirect target)
is the only place UX-01 can act, because `redirect_url` stays `None` on the success path
(line 150: `redirect_url = None`, immediately after `self.issued_recovery_codes =
generate_recovery_codes(user)` at line 149).

The site-local/non-site-local branch D-08 must stay inside is confirmed at lines 193-212:
```python
    def updateFields(self, *args, **kwargs):
        if bool(api.user.is_anonymous()) is False:
            barcode_field = self.fields.get('qr_code')
            if barcode_field:
                if is_site_local_user():
                    barcode_field.field.description = _(get_token_description())
                else:
                    barcode_field.field.description = _(
                        u"This account is not defined in this Plone site, ...")
            return super(SetupForm, self).updateFields(*args, **kwargs)
```
**Implementation note not in CONTEXT.md:** this whole method body is nested inside
`if bool(api.user.is_anonymous()) is False:`, with no `else:` — for an anonymous caller,
`updateFields` returns `None` implicitly and never calls `super().updateFields(...)`. This is
existing behavior, unrelated to any of the four requirements, and not something this phase should
touch — flagged only so the planner does not mistake it for scope creep or a defect to fix while
in this file for D-08.

### 5. `helpers.py` — `get_token_description()` (confirmed, plus the escaping question resolved)

Exact current source, lines 330-348:
```python
def get_token_description(user=None, overwrite_secret=False):
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
`get_or_create_secret(user, overwrite=overwrite_secret)` (called at `helpers.py:305-327`) returns
the **plaintext base32 secret** — either freshly generated (`generate_secret`, which does
`base64.b32encode(os.urandom(20))`, encrypts it for storage, but returns the plaintext) or
decrypted from storage (`decrypt_seed(secret)`). This is exactly the string D-07 wants displayed:
no re-derivation needed, D-08's claim that "the secret is in hand" is literally true — the same
call already produces both the value baked into the QR's `otpauth://` URI (via
`get_barcode_image`, `helpers.py:227-243`) and the value D-08 proposes to print beside it.

`get_barcode_image(username, domain, secret)` builds
`"otpauth://totp/{username}@{domain}?secret={secret}".format(...)`, renders it with the pure-Python
`qrcode` library (`qrcode.make(data)`), and returns a `data:image/png;base64,...` URI — confirming
D-06's premise that the QR already fully encodes the secret with **zero network egress** (no
Google Charts API call, contrary to the stale docstring/comment in some older code paths — this
package's `get_barcode_image` is local-render only, verified by reading its body).

**z3c.form field-description escaping — resolved this session (was an open question, not just
unverified in CONTEXT.md):** the description text a `zope.schema` field carries is rendered by
the `widget-wrapper` macro in the installed `plone.app.z3cform-0.7.8` egg,
`plone/app/z3cform/templates/widget.pt:23-29`:
```html
<span class="formHelp"
    tal:define="description widget/field/description"
    i18n:translate=""
    tal:content="structure description"
    tal:condition="python:description and not hidden"
    >field description
</span>
```
`tal:content="structure description"` renders the description as **raw HTML, unescaped** — this
is the same mechanism that already makes the QR's `<img>` tag render as an image rather than as
literal angle-bracket text today. **This confirms D-08's approach works exactly as designed**:
appending a plain HTML fragment (e.g. `<p>Secret: <code>{secret}</code></p>`) to the string
`get_token_description()` returns will render as a real `<code>` element with selectable text,
with no template change and no new escaping logic. Base32 output uses only `[A-Z2-7=]`, which
needs no HTML-escaping in practice, but wrapping it in a tag (`<code>` or `<span>`) rather than
concatenating bare text keeps it visually distinct from the surrounding sentence and gives a
password-manager "select all in this element" affordance a bare text node does not.

This resolves the CONTEXT.md-adjacent open item cleanly: **UX-02's plan needs no re-authentication
gate to *render correctly*** (D-05 already settled that it needs no gate to be *in scope*); this
research only confirms the rendering mechanics D-08 assumed but did not itself verify.

### 6. `tests/test_request_bar_code_reset.py` — mail-failure harness (confirmed, lines corrected slightly)

CONTEXT.md cites "lines 31-37" for the `MailBase._send` patch and its explanatory comment. The
verified structure: `_submit_reset_request` is defined at line 30; its docstring (the "why we
patch `_send`" explanation) is lines 31-39; the actual monkeypatch is lines 40-54:
```python
    def _submit_reset_request(self, username):
        """... (docstring, lines 31-39) ..."""
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
A **raising variant** for BUG-07's new test replaces `_capture`'s body with a `raise
SMTPRecipientsRefused(...)` (or `socket.error(...)`, to exercise the wider catch D-09 adds) instead
of appending to `sent`, still restoring `original_send` in the `finally:`. The existing three test
methods in this file (`test_reset_email_survives_a_non_ascii_sender_name`,
`test_successful_request_keeps_the_caller_on_the_form`,
`test_reset_request_stores_a_reset_token`) are the pattern to follow: drive the real form through
`_submit_reset_request` (or a sibling helper built the same way), then assert on
`IStatusMessage(request).show()` for the error message and on the *absence* of the previous
"sent successfully" info message — mirroring
`test_successful_request_keeps_the_caller_on_the_form`'s assertion style at lines 115-121.

**Non-vacuity requirement (D-13):** the new test must first be run against the unfixed source
(lines 112-113 still doing the narrow re-raise) to confirm it goes red — either because the
`SMTPRecipientsRefused` re-raise still escapes uncaught (test errors, not fails, unless the test
wraps the call in its own `assertRaises` first to prove the *current* broken behavior, then is
rewritten to assert the *fixed* behavior) or, for the `socket.error` variant, because no `except`
clause catches it at all today. Byte-identical restore afterward, per project convention
(Phase 08 and earlier's practice, referenced in `08-CONTEXT.md`).

### 7. `profiles/default/actions.xml` — `navigationRootUrl` idiom (confirmed exactly)

Lines 11, 24, 45 all use the identical expression form:
```xml
<property name="url_expr">string:${globals_view/navigationRootUrl}/@@setup-two-factor-authentication</property>
...
<property name="url_expr">string:${globals_view/navigationRootUrl}/@@disable-two-factor-authentication</property>
...
<property name="url_expr">string:${globals_view/navigationRootUrl}/@@setup-two-factor-authentication</property>
```
This is a **TAL/CMF `string:` expression inside an XML property**, not a page-template TAL
attribute — but `globals_view/navigationRootUrl` is a plain view-method traversal
(`portal_view/@@plone/navigationRootUrl` under the hood, exposed via the `globals_view` browser
view alias CMF/Plone registers), and the identical syntax works unchanged inside a page template's
`tal:attributes="href string:${globals_view/navigationRootUrl}/@@personal-information"` — the
same `${...}` interpolation mechanics `recovery_codes.pt:24` already uses for
`${context/absolute_url}`. No adaptation needed; D-02's plan is a drop-in replacement of one
sub-expression.

### 8. Python 2.7 exception hierarchy (confirmed live, this session)

Verified directly against the project's own `pyenv`-provisioned `python2.7`
(`/home/cadam/.pyenv/shims/python2.7`, the interpreter this buildout's virtualenv is built from):
```
>>> smtplib.SMTPRecipientsRefused.__mro__
(SMTPRecipientsRefused, SMTPException, Exception, BaseException, object)
>>> socket.error.__mro__
(error, IOError, EnvironmentError, StandardError, Exception, BaseException, object)
```
and, live-reproduced by attempting a connection to a closed port:
```
>>> socket.create_connection(('127.0.0.1', 1), timeout=1)
socket.error  (confirmed the exact type raised on connection refusal)
```
**The concrete `except` clause D-09 needs:** `except (smtplib.SMTPException, socket.error):` —
`SMTPException` (not the narrower `SMTPRecipientsRefused`) so any SMTP-protocol-level failure is
covered, matching D-09's "every SMTP-level and network-level send failure" wording, and
`socket.error` for the no-server-reachable case, which is not an `SMTPException` at all.

### 9. Test running and coverage-gate mechanics (confirmed)

- `bin/test -t <pattern>` runs the suite; `make test opt='-t "helpers"'` is the Makefile wrapper.
- The CI/local coverage gate is `bin/test-coverage`, generated by buildout's `[test-coverage]`
  part (`base.cfg:84-96`): `bin/coverage run bin/test $*`, then
  `bin/coverage report -m --fail-under=90`, exiting 1 if branch coverage (per `.coveragerc`:
  `branch = True`, `source = src/imio/googleauthenticator`, `omit = */tests/*`) drops below 90%.
- BUG-07's two currently-uncovered lines (112-113) are exactly the lines this phase deletes/
  rewrites, so the new test both proves the fix and closes the coverage gap in the same commit.

## Additional Finding Not in CONTEXT.md

**The `recovery_codes.pt` link's msgid ("Continue to your profile") is not present in any
catalogue at all** — checked `imio.googleauthenticator.pot` and all three `LC_MESSAGES/*.po`
files; no match for "recovery" anywhere and no match for "Continue to your profile". This means
D-04's rewording produces **no orphaned, previously-translated msgid** the way D-15/D-16's
`userdataschema.py` edit does — there was never a French translation of this string to begin
with (the catalogues predate `recovery_codes.pt`, which Phase 6 added). Practical effect: UX-01's
text change carries strictly less i18n risk than BUG-08's, and Phase 13's I18N-02 catalogue
rebuild will pick up the new "Continue to the home page" string as a first-time addition, not a
replacement. This does not change any decision — it is a reassurance for the planner that D-04
has no D-16-shaped consequence to record.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Catching mail-send failures | A custom mail-exception wrapper class | Python 2.7 stdlib `smtplib.SMTPException` + `socket.error` in one `except` tuple | Both are already the exact types raised by the code path in use (`Products.MailHost.MailHost.MailBase._send` → `smtplib`); no third-party exception-normalization library exists or is needed for two stdlib types |
| Copyable secret display | A JS "copy to clipboard" button, a `<details>` reveal, a second schema field | Plain HTML text (e.g. `<code>`) appended to the existing `get_token_description()` string | The field-description slot already renders raw HTML (`structure`); D-06 already rejected the reveal-control alternatives for good reason — nothing here needs building |
| Conditional per-viewer field description (BUG-08) | A custom widget or form override that varies `enable_two_factor_authentication`'s description by "is this my own profile" | Delete the two links from the static description | `zope.schema` field descriptions are class-level, evaluated once at import time — building per-request logic for this is real machinery for a link that has no correct audience on `@@user-information` anyway (D-14) |

**Key insight:** all four fixes are subtraction or narrow-widening of existing code, not new
capability. The temptation to over-build (a mail-failure taxonomy, a secret-reveal widget, a
per-viewer schema) was already identified and rejected in CONTEXT.md's decision log; this
research found no reason to reopen any of it.

## Common Pitfalls

### Pitfall 1: Setting `reason` inside the widened `except` clause without checking what runs after it
**What goes wrong:** `request_bar_code_reset.py`'s success-message call
(`IStatusMessage(...).addStatusMessage(_("...sent successfully."), 'info')`, lines 126-129) sits
in the **same outer `try:` block**, after the inner `try/except` around `host.send(...)`. A naive
fix that just widens the inner `except` tuple and sets `reason = _(...)` without also preventing
the success-message call from running afterward will report *both* an error and a success on the
same request.
**Why it happens:** the inner `try/except` and the success-message call look independent but
share one outer `try:` scope; nothing currently returns or short-circuits between them because
today's re-raise makes it moot (execution never reaches the success message on failure).
**How to avoid:** move the success-message call inside the inner `try:`, immediately after
`host.send(...)`, so a raised exception skips it naturally — the same shape the `except
ValueError:` arm already relies on for the rest of the method's statements.
**Warning signs:** a test asserting the error message appears would still pass even with this bug
present, unless it *also* asserts the info message does *not* appear (mirroring
`test_successful_request_keeps_the_caller_on_the_form`'s existing assertion style).

### Pitfall 2: Citing `userdataschema.py:21-42` as "the omit() call" when writing the diff
**What goes wrong:** CONTEXT.md's canonical_refs bundles the whole `CustomizedUserDataPanel`
class body under one line range for the `omit()` evidence. The `omit()` call itself is lines
38-42; lines 21-37 are the class declaration, `__init__` signature, `super()` call, and a
seven-line comment. Not a functional risk, but a planner writing an Edit against the wrong
line-anchored context could target the wrong span.
**Why it happens:** citation ranges in planning docs describe "the relevant code," not
statement-exact boundaries.
**How to avoid:** re-read the file before editing (already project convention per
CLAUDE.md's canonical_refs instruction) rather than trusting a cited range to be exact.
**Warning signs:** none at runtime — this is a documentation-precision note only.

### Pitfall 3: Assuming `updateFields`'s anonymous-user branch is in scope for D-08
**What goes wrong:** `SetupForm.updateFields` has no `else:` for
`api.user.is_anonymous() is True` — it implicitly returns `None` without calling
`super().updateFields(...)`. A planner reading this while implementing D-08 might read it as a
bug needing a fix alongside the secret-display change.
**Why it happens:** it looks incomplete next to the explicit non-site-local branch a few lines
below it.
**How to avoid:** this is pre-existing behavior unrelated to BUG-07/08/UX-01/02; leave it alone.
Anonymous users cannot reach `SetupForm.handleSubmit` either (line 69-71 returns 401), so this
path's practical effect is limited to whatever GET rendering happens before that check — out of
this phase's four success criteria entirely.
**Warning signs:** a diff to this phase that touches the `if bool(api.user.is_anonymous())...`
line itself is scope creep — flag it in review.

## Code Examples

### BUG-07 — widened mail-failure catch (illustrative shape, not a literal diff)
```python
# Source: src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py, verified this session
from smtplib import SMTPException
import socket
...
                try:
                    host = getToolByName(self, 'MailHost')
                    mail_text = self.mail_text_template(
                        member=user, bar_code_reset_url=signed_url, charset='utf-8')
                    mail_text = mail_text.format(bar_code_reset_url=signed_url)
                    host.send(mail_text, immediate=True, charset='utf-8', msg_type='text/html')
                    # Success message moved inside this try: so a send
                    # failure below skips it naturally (Pitfall 1).
                    IStatusMessage(self.request).addStatusMessage(
                        _("An email with instructions on resetting your bar-code is sent successfully."),
                        'info')
                except (SMTPException, socket.error):
                    logger.exception("Bar-code reset request failed to send for %r", username)
                    reason = _("An unexpected error occurred.")
```

### UX-02 — extending `get_token_description()` (illustrative shape)
```python
# Source: src/imio/googleauthenticator/helpers.py, verified this session
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
Renders as raw HTML per the confirmed `structure description` macro
(`plone/app/z3cform/templates/widget.pt:26`, `plone.app.z3cform` 0.7.8) — the `<code>` text is
selectable in any browser without further markup.

### UX-01 — `recovery_codes.pt` link (illustrative shape)
```html
<!-- Source: src/imio/googleauthenticator/browser/forms/recovery_codes.pt, verified this session -->
<p>
  <a tal:attributes="href string:${globals_view/navigationRootUrl}"
     i18n:translate="">Continue to the home page</a>
</p>
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | No project-wide convention favors `import socket` vs. `from socket import error as SocketError` in exception imports | Verification Findings §1 | Cosmetic only — either form works; a reviewer preference, not a correctness risk |
| A2 | `Products.MailHost.MailHost.MailBase._send`'s `_makeMailer().send(...)` call is where a `socket.error` would actually originate for a connection-refused scenario | Verification Findings §8 | If wrong, D-09's `socket.error` arm would be dead code for THIS call path specifically (though still correct stdlib behavior generally) — low risk: even if the exact raise site differs, catching `socket.error` broadly at the outer boundary is still safe and matches D-09's stated intent ("every ... network-level send failure") |

**Both entries are low-risk implementation-detail assumptions, not design assumptions** — D-09's
substantive claim (SMTPRecipientsRefused is an SMTPException; socket.error is not) was verified
live against the interpreter, not assumed.

## Open Questions

None remaining that block planning. CONTEXT.md's own open questions (4 and 5) are already
resolved by D-05 and D-14 respectively. The one implementation nuance this research surfaced
(Pitfall 1's statement-ordering requirement for BUG-07) is documented above as an implementation
detail for the plan to specify, not an open design question.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` via `bin/test` (Products.PloneTestCase / `plone.app.testing` layers), `unittest2` test classes |
| Config file | none — layers and fixtures are Python (`testing.py`, `tests/base.py`); coverage config is `.coveragerc` |
| Quick run command | `bin/test -t test_request_bar_code_reset` / `bin/test -t test_user_setup` / `bin/test -t test_adapter` |
| Full suite command | `bin/test -t '!robot'` (excludes `test_robot.py`, which needs a real browser) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BUG-07 | A rejected/unreachable mail server produces the same in-page error message every other failure path shows, no error page | integration | `bin/test -t test_request_bar_code_reset` (new test method) | ✅ existing file, new method |
| BUG-08 | `@@user-information` field description contains neither link | unit (schema-level) | `bin/test -t test_adapter` or a new `test_userdataschema` module | ❌ Wave 0 — no existing test touches the field description text; cheapest form is a plain assertion on `IEnhancedUserDataSchema['enable_two_factor_authentication'].description`, no Zope traversal needed |
| UX-01 | Recovery-codes page link points at the home page, text reads "Continue to the home page" | integration (template render) | `bin/test -t test_user_setup` (extend `test_recovery_codes_are_issued_once_at_enrollment` or add a sibling) | ✅ existing file; existing test already calls `form.render()` and inspects `markup` — the same pattern covers the new link assertion |
| UX-02 | Base32 secret appears in the rendered `qr_code` field description, matches `get_or_create_secret()` for that user | unit/integration | `bin/test -t test_user_setup` (new method) or `bin/test -t test_helpers` for `get_token_description()` directly | ❌ Wave 0 — `get_token_description()` has no dedicated test today; cheapest form asserts the returned string contains `get_or_create_secret(user)`'s value |

### Sampling Rate
- **Per task commit:** `bin/test -t test_request_bar_code_reset` / `-t test_user_setup` /
  `-t test_adapter` (or the new module), scoped to the file just changed.
- **Per wave merge:** `bin/test -t '!robot'` (full suite, excluding robot).
- **Phase gate:** `bin/test-coverage -t '!robot'` green at `--fail-under=90` before
  `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] BUG-08's field-description test — either add to `tests/test_adapter.py` (which already
  imports `IEnhancedUserDataSchema`) or create `tests/test_userdataschema.py`. No new fixture or
  framework install needed; a plain `zope.schema` field-attribute assertion needs no Zope
  request/traversal at all, and is the lazier option.
- [ ] UX-02's secret-in-description test — extend `tests/test_user_setup.py`, which already
  builds a real `SetupForm` and calls `.update()`/`.render()`; assert
  `helpers.get_or_create_secret(user)` (called with `overwrite=False`, matching what
  `get_token_description` does by default) appears in `form.fields.get('qr_code').field.description`
  after `updateFields()` runs.
- [ ] BUG-07's raising-mail test — extend `tests/test_request_bar_code_reset.py`'s
  `_submit_reset_request` pattern with a raising variant of the `MailBase._send` monkeypatch.

*(No framework install needed — `zope.testrunner`, `unittest2`, and all three target test files
already exist and already exercise the exact forms/functions this phase modifies.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Not touched — no login-path code changes in this phase |
| V3 Session Management | no | Not touched |
| V4 Access Control | yes | BUG-08 is an access-control-adjacent defect: it is not a permission-check bug (the `@@disable-two-factor-authentication` view still checks the standard Plone `View` permission, unchanged), but a **UI affordance that leads an authorized viewer to unintentionally act on the wrong principal's account state** (a confused-deputy shape, not a broken-access-control shape). The fix (delete the links from the only form that offers them out of context) is a control-removal, not a new permission check — consistent with D-14's rejection of a per-viewer conditional, which *would* have been the V4-shaped fix (checking "is this my own profile?") and was explicitly rejected as needing "real machinery" |
| V5 Input Validation | no | No new input surface — BUG-07 changes only what is caught around an existing `host.send()` call; no new field, no new form |
| V6 Cryptography | no | Not touched — `ska` signing and `get_or_create_secret()` are unchanged by this phase; UX-02 *displays* an existing secret, it does not touch how it is generated, stored, or encrypted |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Confused-deputy link on an admin-facing form (BUG-08) — a link on a page rendered for principal A actually acts on principal B (the viewing admin), because the underlying view has no notion of "which account was this link generated for" | Elevation of Privilege / Repudiation (admin unknowingly disables their own MFA and is told it succeeded, weakening their own account without their intent) | Standard mitigation is either (a) remove the affordance from the context where it is ambiguous (this phase's approach, D-14) or (b) have the target view validate the acting principal against an explicit `userid` parameter, refusing on mismatch (the Future Requirement CONTEXT.md defers) |
| Verbose/distinguishing error messages on an unauthenticated form (`RequestBarCodeResetForm`) creating a username-enumeration oracle | Information Disclosure | Already mitigated pre-phase and preserved by D-11: the generic `_("An unexpected error occurred.")` message is reused rather than a distinct "recipient rejected" message, which would tell an anonymous submitter whether a given username has a deliverable email address — T-03-26 in prior phase security review, explicitly not widened by this fix |
| Unhandled exception producing a framework error page instead of an application-controlled response (BUG-07 as currently shipped) | Denial of Service (soft) / Information Disclosure (a default Zope error page can leak traceback detail depending on site debug settings) | Standard mitigation: catch all expected failure modes at the boundary and render the application's own error UI — exactly what D-09/D-10/D-11 do |

## Sources

### Primary (HIGH confidence — verified this session against local source/eggs/interpreter)
- `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py` (full file read)
- `src/imio/googleauthenticator/userdataschema.py` (full file read)
- `src/imio/googleauthenticator/browser/forms/recovery_codes.pt` (full file read)
- `src/imio/googleauthenticator/browser/forms/user_setup.py` (full file read)
- `src/imio/googleauthenticator/helpers.py` lines 150-370 (`get_app_settings` through
  `_is_six_digit_token`, including `get_token_description`, `get_or_create_secret`,
  `get_barcode_image`, `generate_secret`)
- `src/imio/googleauthenticator/profiles/default/actions.xml` (full file read)
- `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py` (full file read)
- `src/imio/googleauthenticator/tests/test_user_setup.py` (full file read)
- `src/imio/googleauthenticator/tests/test_adapter.py` lines 1-80
- `src/imio/googleauthenticator/adapter.py` lines 1-60
- `src/imio/googleauthenticator/locales/imio.googleauthenticator.pot` (grepped for both
  contested msgids)
- `src/imio/googleauthenticator/locales/fr/LC_MESSAGES/imio.googleauthenticator.po` (grepped)
- `/home/cadam/buildout-cache/eggs/plone.app.z3cform-0.7.8-py2.7.egg/plone/app/z3cform/templates/widget.pt`
  (installed egg, the exact pinned version this buildout resolves) — resolves the field-
  description escaping question
- `/home/cadam/buildout-cache/eggs/Products.MailHost-2.13.2-py2.7-linux-x86_64.egg/Products/MailHost/MailHost.py`
  lines 280-348 (`_send` implementation, confirming the `immediate=True` path calls
  `_makeMailer().send(...)`, ultimately stdlib `smtplib`)
- `python2.7` interpreter probe (this session): `smtplib.SMTPRecipientsRefused.__mro__`,
  `socket.error.__mro__`, and a live `socket.create_connection` to a closed port reproducing
  `socket.error`
- `base.cfg` lines 84-96 (`[test-coverage]` recipe) and `.coveragerc` (coverage gate mechanics)
- `.planning/config.json` (`workflow.nyquist_validation: true`, `workflow.security_enforcement:
  true`, `workflow.security_asvs_level: 1` — both optional RESEARCH.md sections included per
  these flags)

### Secondary (MEDIUM confidence)
- None — this phase required no web search; every claim traced to a file this session read
  directly.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new stack or dependency introduced by this phase; all four fixes use
  existing stdlib (`smtplib`, `socket`) or existing project code
- Architecture: HIGH — traced every file this phase touches end to end, including the
  installed-egg templates that render the two surfaces (field description, recovery-codes page)
- Pitfalls: HIGH — Pitfall 1 (statement ordering in the widened `except`) was discovered by
  tracing the actual control flow, not inferred; Pitfalls 2 and 3 are documentation-precision and
  scope-boundary notes respectively, both directly observed in the source

**Research date:** 2026-08-06
**Valid until:** No expiry driver — this is a fixed-point-in-time snapshot of an unchanging
Python 2.7/Plone 4.3 codebase with no external dependency updates possible (all pins are frozen
per CLAUDE.md's version-pinning rules). Re-verify only if the four target files change before
this phase is planned/executed.
