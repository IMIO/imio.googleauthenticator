---
phase: 05-drift-replay-and-lockout
reviewed: 2026-08-01T00:00:00Z
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
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-08-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Judged against the phase's four guarantees -- no replay, one step of backward-only clock
drift, a persisted lockout counter, and lock-state-indistinguishable failure messages --
by tracing `validate_token`/`_find_accepted_interval` (drift + replay), `is_account_locked`/
`register_failed_second_factor`/`reset_failed_second_factor` (lockout), and both
`browser/forms/token.py` and `browser/forms/reset_bar_code.py` `handleSubmit` call sites
by hand, then cross-checking each conclusion against the existing test suite.

**A prior round of this review (visible in this file's previous revision) flagged a
message-prefix mismatch between `reset_bar_code.py`'s locked-account branch
("Resetting of the bar-code failed! ...") and its wrong-code branch ("Setup failed!
..."). That defect is gone in the current code**: both branches now render through the
identical `"Setup failed! {0}".format(reason)` wrapper (`reset_bar_code.py:122-129` and
`:169-174`), confirmed via `git log` against commit `be31592` ("close the reset-bar-code
lock-state oracle (MFA-08)"), and it is now covered by
`test_reset_bar_code.py::test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account`'s
three-way message-equality assertion. Per this review's instructions, that resolved finding
is not carried forward.

Independently verified as correct, not merely plausible:

- `_find_accepted_interval` only ever tests `(current, current - 1)`, never
  `current + 1` -- drift tolerance cannot become a second guessing window.
- The replay gate (`matched <= last_accepted_interval`) is strict; equality (a replayed
  code) is refused, confirmed against `test_helpers.py::TestDriftAndReplay`.
- `register_failed_second_factor`'s "counter and lock land together, or neither does"
  claim holds at the `Products.PlonePAS.sheet.MutablePropertySheet.setProperties` level:
  every key in the mapping is validated in a first pass before `self._properties.update(...)`
  runs, so a `PropertyValueError` on one key cannot leave the pair half-written.
- `is_account_locked`'s `>` (not `>=`) boundary matches the adjacency tests exactly.
- `token.py`'s and `reset_bar_code.py`'s own locked-vs-wrong-code messages are now
  byte-identical within each endpoint, and the lock check runs strictly before
  `validate_token` in both.

Two warnings and one info item remain, detailed below.

## Warnings

### WR-01: `@@reset-bar-code` lets an unauthenticated caller consume the shared lockout counter, with nothing scoping the attempt budget to an IP or session

**File:** `src/imio/googleauthenticator/browser/forms/reset_bar_code.py:72-171`
**Issue:** `ResetBarCodeForm.handleSubmit` never calls `validate_user_data` (contrast
`token.py:90-97`, which does before consulting `is_account_locked`/`validate_token`). The
only gates before `validate_token`/`register_failed_second_factor` are `api.user.get(username=
username)` resolving and `is_site_local_user`/`is_account_locked`. An anonymous POST to
`@@reset-bar-code?auth_user=<any-enrolled-username>` with five wrong six-digit
`form.widgets.token` submissions requires no password, no `ska` signature and no
`auth_timestamp` -- nothing beyond the username itself -- and locks that account's second
factor for `lockout_duration` (default 900s).

`tests/test_reset_bar_code.py::test_reset_bar_code_lockout_after_five_failures` proves this
is deliberate and *bounded* for a single account (its own docstring names it "the defect
being metered", bounded by `lockout_duration`, decisions T-05-08/P5-13). What neither that
test nor the design bounds is the aggregate case: nothing here rate-limits by IP or session,
so a single anonymous actor can iterate a list of known/guessed usernames and drive every
one of them through the same five-submission sequence, locking the entire enrolled user
base's second factor at once and re-triggering it every `lockout_duration` seconds
indefinitely. This is asymmetric with `token.py`'s login path, where reaching
`is_account_locked` first requires a valid `ska`-signed URL -- i.e. the attacker must already
possess that specific user's password -- so the login path cannot be used to mass-lock
accounts the attacker has not already compromised. `reset_bar_code.py` is the one path that
can, by design, at zero authentication cost.

**Fix:** A signature requirement can't be added here without breaking the already-tested
MFA-11 guarantee that a *correct* code at this endpoint clears the counter/lock even with no
signature supplied (`test_reset_bar_code_lockout_after_five_failures` step 2 depends on
exactly that). The narrower fix is a rate limit in front of the per-account counter that
doesn't touch that guarantee -- e.g. an IP- or session-scoped throttle on `@@reset-bar-code`
POSTs, independent of which `auth_user` is named:

```python
# reset_bar_code.py, ResetBarCodeForm.handleSubmit, before validate_token is ever reached
if not within_ip_rate_limit(self.request):
    reason = _("Too many attempts, please try again later.")
    IStatusMessage(self.request).addStatusMessage(
        _("Setup failed! {0}".format(reason)), 'error')
    return
```
(The rate-limit state itself needs the same memberdata-vs-RAM-cache consideration CLAUDE.md
already documents for the per-user counter -- a per-instance cache would let an attacker
multiply attempts by rotating ZEO clients.) At minimum, document this as an accepted
operator-facing risk in README.rst if no throttle is added.

### WR-02: The three new lockout/replay counters are writable, non-`readonly` schema fields, with the personal-preferences form's `omit()` as the only barrier

**File:** `src/imio/googleauthenticator/userdataschema.py:86-102`
**Issue:** `two_factor_authentication_failed_attempts`, `two_factor_authentication_locked_until`
and `two_factor_authentication_last_interval` are declared as plain `Int(required=False)`
with no `readonly=True`. The only thing stopping a user from self-editing their own
lockout/replay state today is `CustomizedUserDataPanel.__init__`'s
`form_fields.omit(...)` (`userdataschema.py:30-37`), which is applied per-view.
`UserDataSchemaProvider.getSchema()` hands the same `IEnhancedUserDataSchema` to every
consumer of `plone.app.users`' schema machinery, and any future or alternate consumer that
renders this schema without independently re-applying the same `omit()` call (an admin
user-management view, a REST/JSON adapter, an XML-RPC exposure of member properties) would
let an authenticated user write `two_factor_authentication_locked_until = 0` to self-unlock,
or `two_factor_authentication_last_interval = 0` to re-open a replay window on their own
account, directly through the ordinary z3c.form/plone.autoform edit machinery, no exploit
required -- just an omitted `omit()`.

**Fix:** Add `readonly=True` to the three new fields (and, opportunistically, to
`two_factor_authentication_secret`/`bar_code_reset_token`, which have the same exposure)
so the `omit()` calls become defense-in-depth rather than the sole barrier:
```python
two_factor_authentication_locked_until = Int(
    title=_('Second-factor locked until'),
    description=_('Automatically generated'),
    required=False,
    readonly=True,
)
```

## Info

### IN-01: Dead fetch in `GoogleAuthenticatorSettingsEditForm.handleSave`'s disable branch

**File:** `src/imio/googleauthenticator/browser/controlpanel.py:148-152`
**Issue:**
```python
elif globally_enabled is False:
    # Disable for all users
    users = api.user.get_users()
    #disable_two_factor_authentication_for_users(users)
    logger.debug('Disabled')
```
`users` is fetched (a full `api.user.get_users()` call) and never used -- the only consumer
is the commented-out line directly below. Pre-existing (not introduced by this phase's own
`max_failed_attempts`/`lockout_duration` additions to the same file), and intentional in
effect (the field's own description already documents that unchecking `globally_enabled`
leaves existing users untouched), but it's dead code worth cleaning up opportunistically
since this phase already touched the file.

**Fix:**
```python
elif globally_enabled is False:
    logger.debug('Disabled')
```

---

_Reviewed: 2026-08-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
