---
phase: 05-drift-replay-and-lockout
reviewed: 2026-07-31T16:14:56Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/userdataschema.py
  - src/imio/googleauthenticator/browser/controlpanel.py
  - src/imio/googleauthenticator/browser/forms/token.py
  - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
  - src/imio/googleauthenticator/profiles/default/memberdata_properties.xml
  - src/imio/googleauthenticator/tests/test_token.py
  - src/imio/googleauthenticator/tests/test_reset_bar_code.py
  - src/imio/googleauthenticator/tests/test_helpers.py
  - src/imio/googleauthenticator/tests/test_generic.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
findings:
  critical: 1
  warning: 2
  info: 1
  total: 4
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-31T16:14:56Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Reviewed the drift-tolerance, replay-refusal and lockout logic added in this phase
(`helpers.py`'s `_is_six_digit_token`, `_find_accepted_interval`, `validate_token`,
`is_account_locked`, `register_failed_second_factor`, `reset_failed_second_factor`; the
lock gates wired into `browser/forms/token.py` and `browser/forms/reset_bar_code.py`; the
new memberdata declarations in `userdataschema.py` and `memberdata_properties.xml`).

The core TOTP drift/replay state machine is sound: drift acceptance is
strictly backward-looking (`current`, `current - 1`, never `current + 1`), replay is
refused via a monotonically-increasing stored interval including across the drift
window, the six-ASCII-digit gate runs before any seed decrypt, and the failure
counter/lock epoch are written together in a single `setMemberProperties` call so they
can't land inconsistently. All of that is exercised by real assertions in
`test_helpers.py::TestDriftAndReplay` and is correct as traced.

However, the lock-gate wiring into `browser/forms/token.py` reintroduces exactly the kind
of oracle this phase's own design principle (`browser/forms/reset_bar_code.py`'s "same
message as a wrong code" pattern) was meant to prevent, just one level up: it lets an
unauthenticated party learn whether an arbitrary username is currently locked out, without
ever needing a valid `ska` signature or password. See CR-01 below. A second finding
(WR-01) flags that `@@reset-bar-code`'s `handleSubmit` consumes attempts against the
*same* lockout counter as the real login form with no signature check at all gating entry
into `validate_token` -- a tested and explicitly-accepted tradeoff (T-05-08/P5-13), but
still a real, cheaply-repeatable, zero-authentication denial-of-service primitive against
any known username's ability to log in, worth a second look.

## Critical Issues

### CR-01: `is_account_locked` gate in `token.py` leaks lock status to an unauthenticated caller

**File:** `src/imio/googleauthenticator/browser/forms/token.py:85-106`
**Issue:**

```python
if username:
    user = api.user.get(username=username)

    if user is not None and is_account_locked(user):
        # Locked accounts get the exact same message as a wrong
        # code, so the response cannot be used as an oracle ...
        msg = _("Invalid token or token expired.")
        IStatusMessage(self.request).addStatusMessage(msg, 'error')
        return

    # Validating the signed request data. If invalid (likely tampered
    # with or expired), generate an appropriate error message.
    user_data_validation_result = validate_user_data(
        request=self.request, user=user)

    if not user_data_validation_result.result:
        IStatusMessage(self.request).addStatusMessage(
            _("Invalid data. Details: {0}".format(' '.join(
                user_data_validation_result.reason))), 'error')
        return
```

The comment claims "Locked accounts get the exact same message as a wrong code, so the
response cannot be used as an oracle" -- and that is true for the *wrong-code-vs-locked*
comparison the existing test (`test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code`)
exercises. But that test always drives a browser that already holds a genuinely
`ska`-signed URL (obtained through a real password login), so `validate_user_data`
always succeeds in that test and the comparison never reaches the branch below it.

Before this phase, an anonymous request to `@@google-authenticator-token?auth_user=<any
existing username>` with no valid signature at all always fell through to
`validate_user_data`, which fails for lack of a legitimate signature and produces
`"Invalid data. Details: ..."` -- identical regardless of whether the named account
exists, is 2FA-enabled, or has any failed attempts recorded. This phase's `is_account_locked`
check runs *before* that signature check, so it now short-circuits to a *different*,
distinguishable message (`"Invalid token or token expired."`) whenever the named account
happens to be locked. The result: with nothing but a known or guessed username -- no
password, no `ska` signature, no valid TOTP code -- an attacker can send

```
GET/POST /@@google-authenticator-token?auth_user=victim
```

repeatedly and learn, purely from which of the two message strings comes back, whether
`victim`'s second factor is *currently locked out* (i.e. whether somebody, possibly the
attacker themself via a separate password-guessing or 2FA-guessing run, has recently
driven that account past `max_failed_attempts`). This is precisely the "locked account
must not be usable as an oracle" property this phase set out to guarantee, violated for
a strictly weaker attacker than the one the existing test covers (this one never even
needs a valid signature).

**Fix:** Move the lock check to after the signature validation, so nothing about lock
status is revealed until the caller has already proven possession of a legitimately
signed URL (which itself requires having supplied the correct password):

```python
if username:
    user = api.user.get(username=username)

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
```

Add a test that drives this endpoint with a locked account and *no* `signature`/`auth_timestamp`
query parameters at all, and asserts the response is the generic `"Invalid data. Details:
..."` message (or at minimum is indistinguishable from the same request against a
non-existent or unlocked username), not `"Invalid token or token expired."`.

## Warnings

### WR-01: `@@reset-bar-code` consumes the shared lockout counter with no signature check at all before guessing

**File:** `src/imio/googleauthenticator/browser/forms/reset_bar_code.py:72-164`
**Issue:** `ResetBarCodeForm.handleSubmit` is registered `permission="zope2.View"` (see
`browser/configure.zcml:40-45`), i.e. anonymously reachable, and never calls
`validate_user_data`/checks the `ska` signature before running `validate_token(token,
user=user)` -- the signature (`signature_token`/`bar_code_reset_token` comparison) is
only consulted *after* a correct TOTP guess, inside the `if valid_token:` branch. So an
anonymous party who knows (or guesses/enumerates) nothing but a valid, site-local,
2FA-enrolled username can submit five wrong six-digit guesses at
`@@reset-bar-code?auth_user=<victim>` with no signature at all, and `register_failed_second_factor`
(`helpers.py:471-502`) will lock the account via the property this phase now shares with
the real login form (`is_account_locked`, checked in both `token.py:88` and
`reset_bar_code.py:116`). The result is a free, unauthenticated, indefinitely-repeatable
way to deny a known user's real login for `lockout_duration` seconds at a time, forever
(wait it out, repeat).

This is explicitly tested and was a conscious tradeoff of this phase
(`test_reset_bar_code.py::test_reset_bar_code_lockout_after_five_failures`, T-05-08/P5-13
in the docstrings), and it is an *improvement* over the pre-phase state (previously this
same endpoint allowed unlimited, unthrottled TOTP guessing with no lockout of any kind).
Flagging it anyway because sharing the counter with the login path turns a
self-contained guessing surface into an availability lever against the account's
*primary* login path, and there is no gate anywhere on this endpoint that ties an
attempt to actually having received the emailed reset link.

**Fix:** Consider requiring `validate_user_data` (the `ska` signature check already
performed in `updateFields` for rendering) to pass before `handleSubmit` even calls
`validate_token`/counts the attempt -- mirroring the gate `token.py` uses for the login
path -- or track reset-form failures under a separate, shorter-lived counter that does
not also lock the login form. At minimum, document this as a known/accepted risk in
README.rst alongside the other operator-facing caveats (`DOC-01`/`DOC-02`/`DOC-03`
precedent already established in this package), so it isn't rediscovered as a surprise.

### WR-02: New security-critical counters are writable schema fields with no `readonly` flag

**File:** `src/imio/googleauthenticator/userdataschema.py:86-102`
**Issue:** `two_factor_authentication_failed_attempts`, `two_factor_authentication_locked_until`
and `two_factor_authentication_last_interval` are declared as ordinary
`Int(required=False)` fields on `IEnhancedUserDataSchema`, with no `readonly=True`. The
only thing preventing an end user from editing their own lockout/replay state through a
member-data edit form is `CustomizedUserDataPanel.__init__`'s `form_fields.omit(...)`
call (`userdataschema.py:26-37`), which is per-view. `IUserDataSchemaProvider.getSchema()`
returns this same schema to every consumer of `plone.app.users`' schema machinery
(personal preferences, and potentially an admin user-management edit form or any future
view built against the schema directly); any of those that doesn't apply the same
`omit()` would let a user reset their own `two_factor_authentication_locked_until` to `0`
(self-unlock) or their own `two_factor_authentication_last_interval` to `0` (re-enabling
acceptance of a previously-used/replayed code) by editing their profile.

This mirrors the pre-existing gap already accepted for `two_factor_authentication_secret`/
`bar_code_reset_token` (same pattern, same lack of `readonly`), so it isn't a new
deviation from this package's conventions, but the blast radius for the three new fields
is more direct: writing to them changes live security-control state (lockout, replay)
rather than a value that's separately verified against a stored token.

**Fix:** Add `readonly=True` to the three new fields (and, opportunistically,
`two_factor_authentication_secret`/`bar_code_reset_token`, as a follow-up) so the
omission in `CustomizedUserDataPanel` is defense-in-depth rather than the sole barrier.

## Info

### IN-01: Dead code around `disable_two_factor_authentication_for_users` in `handleSave` (pre-existing, not part of this phase's diff)

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:116-121, 148-152`
**Issue:** Not introduced by this phase (the diff here only adds the `max_failed_attempts`/
`lockout_duration` fields), but present in the file under review: the `elif
globally_enabled is False:` branch fetches `users = api.user.get_users()` and then never
uses it -- the actual call is commented out (`#disable_two_factor_authentication_for_users(users)`).
`disable_two_factor_authentication_for_users` is imported inside `handleSave` for a call
that never happens. Noting for completeness since it's in a file this phase's task list
asked to be reviewed in full.
**Fix:** Either wire the call back in (if disabling globally was meant to work) or drop
the dead fetch/import and the stale comment; the control panel's own field description
already documents that unchecking `globally_enabled` intentionally does not disable 2FA
for existing users, so the current behaviour may be correct -- only the leftover
dead code needs cleaning up.

---

_Reviewed: 2026-07-31T16:14:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
