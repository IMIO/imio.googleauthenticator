---
phase: 09-mail-path-and-profile-page-correctness
reviewed: 2026-08-06T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - CHANGES.rst
  - src/imio/googleauthenticator/browser/forms/recovery_codes.pt
  - src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/tests/test_adapter.py
  - src/imio/googleauthenticator/tests/test_request_bar_code_reset.py
  - src/imio/googleauthenticator/tests/test_user_setup.py
  - src/imio/googleauthenticator/userdataschema.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-08-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This phase's actual diff is small and well-scoped: (1) `request_bar_code_reset.py` deletes
the `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)` re-raise, widens the
catch to `(SMTPException, socket.error)`, and moves the success status message inside the
inner `try:`; (2) `helpers.get_token_description()` now also renders the base32 secret as
selectable `<code>` text next to the QR image; (3) `recovery_codes.pt` retargets its one link
from `@@personal-information` to `context/@@plone/navigationRootUrl`; (4) `userdataschema.py`
drops two links from a field description. Each change was traced against its own tests and
against the git diff of the previous commit (not just the file's current state), to separate
what this phase touched from what it left alone.

I traced the `get_token_description()` change specifically for the XSS risk the review brief
flagged: the returned HTML is rendered with `tal:content="structure description"` (unescaped),
and both interpolated values — the `data:image/png;base64,...` QR URL and the plaintext
`secret` — are embedded via bare `.format()` with no escaping. On inspection, this is **not
currently exploitable**: `get_barcode_image()`'s output alphabet is base64 (`A-Za-z0-9+/=`,
no `"`/`<`/`>`), and `secret` is always base32 (`A-Z2-7`, no padding at this bit length) —
neither alphabet contains an HTML metacharacter, and `username`/`domain` never reach the
visible markup directly (they are only baked into the QR pixel data, not the text). I still
flag the missing defensive escaping below (WR-02): the safety here rests entirely on an
unenforced invariant about two upstream functions' output alphabets, not on anything in this
function itself.

The `request_bar_code_reset.py` control-flow fix for BUG-07 is correct for the two failure
modes it targets (`SMTPException`/`socket.error`) and for the double-message hazard the phase
brief called out: the success message living inside the inner `try:` means a caught failure
can never also report success, and vice versa — confirmed against both new tests. But the
same code block still contains a `str.format()` call (`mail_text.format(bar_code_reset_url=...)`,
pre-existing, unchanged by this diff) that is not covered by either the widened inner `except`
or the outer `except ValueError:` for every failure shape it can produce — see WR-01.

No hardcoded secrets, injection, or empty-catch anti-patterns found. Tests are non-vacuous and
assert on user-visible behaviour (status messages, `Location` header, rendered markup) rather
than internals.

## Warnings

### WR-01: Mail-template `.format()` re-substitution can still 500 past the widened catch

**File:** `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:97` (catch at lines 138-140)

**Issue:** `request_bar_code_reset_email.pt` renders the mail body with TAL, but deliberately
leaves one placeholder as **literal text** — `<a href="{bar_code_reset_url}">` — and
`handleSubmit` performs a second, plain Python substitution afterward:

```python
mail_text = self.mail_text_template(member=user, bar_code_reset_url=signed_url, charset='utf-8')
mail_text = mail_text.format(bar_code_reset_url=signed_url)   # line 97
```

Everything else in that template reaches the rendered string via TAL (`tal:replace="python:here.email_from_name"`,
`member/getUserName`, `member.getProperty('email')`), i.e. admin- or user-controlled text lands
in the string handed to `.format()` *before* `.format()` runs. If any of those values contains
a literal `{` or `}` (an admin's `email_from_name`, or a username, depending on the site's
registration policy — Plone does not universally forbid these characters), `str.format()`
raises:
- `ValueError` for a lone `{` — this **is** caught, by the outer `except ValueError:` (line 141),
  so that specific shape degrades gracefully.
- `KeyError` for a well-formed-but-unknown field like `{oo}` (e.g. `email_from_name = "iMio {Team}"`)
  — this is **not** caught by the inner `except (SMTPException, socket.error):` (line 138) nor
  by the outer `except ValueError:` (line 141), and escapes as an unhandled exception all the
  way to a bare Zope error page for an anonymous caller — exactly the failure mode BUG-07 set
  out to close, just reached through a different value than the ones this phase's tests cover.

This line is unchanged by this phase's diff (confirmed against the pre-phase revision), so it
is not a regression this phase introduced, but it sits inside the very block this phase edited
to fix "no unhandled exception on a mail failure," and the fix does not fully deliver on that
for this code path.

**Fix:** Either broaden the inner catch to close the same gap the outer one already covers for
`ValueError`:

```python
except (SMTPException, socket.error, KeyError, IndexError):
    logger.exception("Bar-code reset request failed to send for %r", username)
    reason = _("An unexpected error occurred.")
```

or better, stop re-running `.format()` on already-TAL-rendered content — pass
`bar_code_reset_url` into the template only (it already receives it as a macro argument) and
delete the literal-`{bar_code_reset_url}`/`.format()` step entirely, which removes the hazard
at its source rather than widening a catch tuple around it.

### WR-02: `get_token_description()` relies on an unenforced character-set invariant, not escaping

**File:** `src/imio/googleauthenticator/helpers.py:352-360`

**Issue:**

```python
secret = get_or_create_secret(user, overwrite=overwrite_secret)
return (
    '<div><img src="{url}" alt="QR Code" /></div>'
    '<p>{label} <code>{secret}</code></p>'
).format(
    url=get_barcode_image(get_username(user), get_domain_name(request), secret),
    label=_(u'Setup key:'),
    secret=secret,
)
```

This string is later assigned as a `zope.schema` field `description` and rendered with
`tal:content="structure description"` (unescaped) by z3c.form. Today this is safe only because
of two facts that are true by accident of the current implementation, not by anything this
function enforces: `get_barcode_image()`'s return value is base64 (`A-Za-z0-9+/=`), and
`secret` is base32 (`A-Z2-7`) with no padding at 160 bits — neither alphabet contains `"`,
`<`, `>`, or `&`. If a future change ever stores/returns a `secret` value through a different
path (e.g. an imported legacy seed, a different encoding, or a secret round-tripped through
`decrypt_seed()` from ciphertext that was never produced by `generate_secret()`), nothing here
would catch a `<`/`"`/`&` making it into this unescaped HTML. There is no validation on the
shape of `secret` in this function, unlike e.g. `_is_six_digit_token`/`_is_recovery_code_shape`
elsewhere in this same module, which do gate their inputs before use.

**Fix:** Escape defensively at the point of interpolation, independent of the upstream
invariant:

```python
from xml.sax.saxutils import escape
...
secret=escape(secret),
```

(or add an assertion that `secret` matches the expected base32 alphabet before formatting, so
a violation fails loudly instead of silently becoming injectable).

## Info

### IN-01: `RequestBarCodeResetForm.updateFields` is a no-op override

**File:** `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:153-156`

**Issue:**

```python
def updateFields(self, *args, **kwargs):
    """
    """
    return super(RequestBarCodeResetForm, self).updateFields(*args, **kwargs)
```

This override does nothing but call the base-class implementation with the same arguments —
behaviourally identical to not overriding `updateFields` at all. It carries an empty docstring
and no comment explaining why it exists (unlike, say, `SetupForm.updateFields` in the same
package, which overrides for a real reason).

**Fix:** Delete the method; the base `form.SchemaForm.updateFields` is inherited automatically.
If it is a placeholder for planned future behaviour, say so in the docstring so it reads as
deliberate rather than leftover.

---

_Reviewed: 2026-08-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
