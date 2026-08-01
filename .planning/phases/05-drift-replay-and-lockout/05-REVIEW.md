---
phase: 05-drift-replay-and-lockout
reviewed: 2026-08-01T13:10:12Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/imio/googleauthenticator/browser/controlpanel.py
  - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
  - src/imio/googleauthenticator/browser/forms/token.py
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/profiles/default/memberdata_properties.xml
  - src/imio/googleauthenticator/tests/test_generic.py
  - src/imio/googleauthenticator/tests/test_helpers.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/tests/test_reset_bar_code.py
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
  - src/imio/googleauthenticator/tests/test_token.py
  - src/imio/googleauthenticator/userdataschema.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 05: Code Review Report (re-review)

**Reviewed:** 2026-08-01T13:10:12Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

This is a re-review following plan 05-04 (commits `ff28800`, `eee1d29`, `6a3a8ef`), whose
stated purpose was to close the prior review's CR-01 (`is_account_locked` gate in
`token.py` leaking lock status to an unauthenticated caller). A `git diff 972ae68..HEAD --
src/imio/googleauthenticator/` confirms the *only* production/test files touched since the
prior review are `browser/forms/token.py` and `tests/test_token.py`; every other file in
scope is byte-identical to what the prior review already examined.

**CR-01 is genuinely closed, on the merits, not just by commit message.** The lock check
in `token.py:handleSubmit` was moved to run strictly after `validate_user_data` succeeds,
so an unsigned caller (no password, no `ska` signature, no `auth_timestamp`) now always
gets the same generic "Invalid data. Details: ..." message regardless of whether the named
account is locked, unlocked-and-enrolled, or does not exist at all -- traced the control
flow by hand and it holds. The new test
(`test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account`) proves this
with a genuine three-way equality plus a negative assertion that the lock-branch message
string is never reachable unsigned, which is real, non-tautological coverage (not just
"the code runs without raising").

**However, the identical class of bug the 05-04 plan set out to close is still present,
unfixed, in `reset_bar_code.py` -- and is reachable by a strictly weaker attacker than the
original CR-01 required**, since that endpoint (unlike `token.py`) performs no signature
check at all before consulting `is_account_locked`. See CR-01 below (fresh numbering for
this report; the prior CR-01 is resolved and not carried forward). This was present before
05-04 (introduced in 05-03, commit `b4139b1`) and was not caught by the prior review's
WR-01, which discussed the shared-counter DoS angle but not this specific
message-distinguishability defect.

WR-01 (shared lockout counter between `@@reset-bar-code` and the login form) and WR-02
(new security-critical counters as writable, non-`readonly` schema fields) are unchanged
in the current code and are independently confirmed as real, live warnings -- not because
the prior review's classification was inherited, but because tracing the current code
shows neither has been mitigated. IN-01 (dead `disable_two_factor_authentication_for_users`
fetch in `controlpanel.py`) is likewise unchanged and still a harmless but real piece of
dead code.

## Critical Issues

### CR-01: `@@reset-bar-code` still lets an unauthenticated caller learn account lock status, via a message-prefix mismatch, with *no signature check at all*

**File:** `src/imio/googleauthenticator/browser/forms/reset_bar_code.py:111-122` and `:162-167`
**Issue:**

The locked-account branch:

```python
if is_account_locked(user):
    reason = _("Invalid token or token expired.")
    IStatusMessage(self.request).addStatusMessage(
        _("Resetting of the bar-code failed! {0}".format(reason)),
        'error'
        )
    return
```

renders **"Resetting of the bar-code failed! Invalid token or token expired."**

The ordinary wrong-code (not locked) branch, reached when `valid_token` is `False`:

```python
else:
    register_failed_second_factor(user)
    reason = _("Invalid token or token expired.")

if reason is not None:
    IStatusMessage(self.request).addStatusMessage(_("Setup failed! {0}".format(reason)), 'error')
```

renders **"Setup failed! Invalid token or token expired."**

The comment directly above the locked-branch claims: "Locked accounts get the exact same
message as a wrong code, so the response cannot be used as an oracle" -- but the two
branches use *different* top-level message templates (`"Resetting of the bar-code
failed! {0}"` vs `"Setup failed! {0}"`), even though the embedded `reason` text happens to
be identical in both cases. The two rendered strings are not equal, and nothing in
`test_reset_bar_code.py` (grepped for both literal templates: zero matches) ever asserts
they are, so this was never caught.

Critically, `handleSubmit` on this endpoint performs **no signature/`ska` validation of
any kind** before reaching either branch (it only checks `user found` -> `is_site_local_user`
-> `is_account_locked` -> `validate_token`; the bar-code-reset-token/signature comparison
only happens *after* a correct TOTP guess, deep inside the `if valid_token:` branch). So an
attacker needs nothing but a known or guessed site-local, 2FA-enrolled username -- no
password, no signature, no `auth_timestamp`, nothing -- to submit a wrong six-digit code at

```
POST /@@reset-bar-code?auth_user=victim   (form.widgets.token=000000)
```

and learn, purely from which message template comes back, whether `victim`'s account is
*currently locked out*. This is a strictly weaker-attacker version of the same "not an
oracle" property this phase's own design principle (and the just-closed CR-01) requires,
reachable through a sibling endpoint that 05-04 did not touch.

**Fix:** Make the locked-branch message textually identical to the wrong-code branch's
final rendering, e.g. by routing both through the same `"Setup failed! {0}"` wrapper
instead of two separate `addStatusMessage` call sites with different templates:

```python
if is_account_locked(user):
    reason = _("Invalid token or token expired.")
    IStatusMessage(self.request).addStatusMessage(
        _("Setup failed! {0}".format(reason)), 'error')
    return
```

Add a test mirroring
`test_token.py::test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account`
for this endpoint: submit a wrong code against a locked account and against an
unlocked-but-enrolled account through a browser carrying only `auth_user` (no `signature`),
and assert the two rendered status messages are byte-identical.

## Warnings

### WR-01: `@@reset-bar-code` consumes the shared lockout counter with no signature check at all before guessing (confirmed still present)

**File:** `src/imio/googleauthenticator/browser/forms/reset_bar_code.py:72-164`
**Issue:** Unchanged since the prior review. `ResetBarCodeForm.handleSubmit` is reachable
anonymously and never validates the `ska` signature before calling `validate_token`/
`register_failed_second_factor` -- the signature is only checked after a *correct* TOTP
guess. An anonymous party who knows a valid, site-local, 2FA-enrolled username can submit
five wrong guesses at `@@reset-bar-code?auth_user=<victim>` with no signature at all and
lock the account via the counter shared with the real login form
(`is_account_locked`/`register_failed_second_factor` in `helpers.py`), denying that user's
login for `lockout_duration` seconds, repeatably, forever.

Independently re-confirmed as a real, live, zero-authentication DoS primitive against a
known username's login availability. It is tested and was a documented, conscious tradeoff
(`test_reset_bar_code_lockout_after_five_failures`, decisions T-05-08/P5-13) and represents
an improvement over the pre-phase state (previously unthrottled, unlimited TOTP guessing at
this endpoint). Given the package's ~1-2 year retirement horizon, staying at WARNING (not
blocking) is proportionate, but note it now compounds with CR-01 above: the same
unauthenticated caller who can lock the account through this endpoint can also *detect*
that they succeeded, through the very message-prefix bug CR-01 describes.

**Fix:** Unchanged from prior review. Consider gating `handleSubmit`'s counter-consuming
path behind `validate_user_data` (mirroring `token.py`'s gate), or track reset-form
failures under a separate, shorter-lived counter that does not also lock the primary login
path. At minimum, document as an accepted operator-facing risk in README.rst.

### WR-02: New security-critical counters are writable schema fields with no `readonly` flag (confirmed still present)

**File:** `src/imio/googleauthenticator/userdataschema.py:86-102`
**Issue:** Unchanged since the prior review. `two_factor_authentication_failed_attempts`,
`two_factor_authentication_locked_until` and `two_factor_authentication_last_interval` are
plain `Int(required=False)` fields with no `readonly=True`. The only thing preventing an
end user from self-editing their own lockout/replay state is
`CustomizedUserDataPanel.__init__`'s `form_fields.omit(...)` (`userdataschema.py:30-37`),
which is per-view -- `IUserDataSchemaProvider.getSchema()` hands this same schema to every
consumer of `plone.app.users`' schema machinery, and any future/alternate consumer that
doesn't apply the same `omit()` would let a user self-unlock
(`two_factor_authentication_locked_until = 0`) or re-enable a replayed code
(`two_factor_authentication_last_interval = 0`) by editing their own profile.

Independently re-confirmed: `omit()` is the sole barrier today, and it is call-site
specific rather than schema-level, so it is one missed `omit()` call away (e.g. a future
admin user-management view built directly against `IEnhancedUserDataSchema`) from becoming
a live self-service bypass of the lockout/replay controls this phase built.

**Fix:** Unchanged from prior review -- add `readonly=True` to the three new fields (and,
opportunistically, to `two_factor_authentication_secret`/`bar_code_reset_token`) so the
`omit()` is defense-in-depth rather than the only barrier.

## Info

### IN-01: Dead code around `disable_two_factor_authentication_for_users` in `handleSave` (pre-existing, confirmed still present)

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:148-152`
**Issue:** Unchanged since the prior review, and unchanged since well before this phase.
The `elif globally_enabled is False:` branch fetches `users = api.user.get_users()` and
never uses it -- the call is commented out
(`#disable_two_factor_authentication_for_users(users)`), and
`disable_two_factor_authentication_for_users` is imported (line 117) for a call that never
happens.
**Fix:** Either wire the call back in, or drop the dead fetch/import and stale comment; the
field's own description already documents that unchecking `globally_enabled` intentionally
leaves existing users untouched, so only the leftover dead code needs cleaning up.

---

_Reviewed: 2026-08-01T13:10:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
