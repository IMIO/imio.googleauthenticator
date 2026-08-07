---
phase: 10-global-enforcement-and-enrollment
reviewed: 2026-08-07T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - CHANGES.rst
  - src/imio/googleauthenticator/browser/configure.zcml
  - src/imio/googleauthenticator/browser/disable_two_factor_authentication.py
  - src/imio/googleauthenticator/browser/disable_two_factor_authentication_for_all_users.py
  - src/imio/googleauthenticator/browser/forms/user_setup.py
  - src/imio/googleauthenticator/browser/settings_helper.py
  - src/imio/googleauthenticator/helpers.py
  - src/imio/googleauthenticator/pas_plugin.py
  - src/imio/googleauthenticator/profiles/default/actions.xml
  - src/imio/googleauthenticator/profiles/default/memberdata_properties.xml
  - src/imio/googleauthenticator/setuphandlers.py
  - src/imio/googleauthenticator/testing.py
  - src/imio/googleauthenticator/tests/test_adapter.py
  - src/imio/googleauthenticator/tests/test_challenge.py
  - src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py
  - src/imio/googleauthenticator/tests/test_generic.py
  - src/imio/googleauthenticator/tests/test_helpers.py
  - src/imio/googleauthenticator/tests/test_pas_plugin.py
  - src/imio/googleauthenticator/tests/test_reset_bar_code.py
  - src/imio/googleauthenticator/tests/test_settings_helper.py
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
  - src/imio/googleauthenticator/tests/test_token.py
  - src/imio/googleauthenticator/tests/test_user_setup.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-08-07T00:00:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

This phase wires a new `two_factor_authentication_enrolled` property into the login-routing
decision (`pas_plugin.py`), the enrollment form's sessionless authentication path
(`user_setup.py`), and the two menu-link predicates (`settings_helper.py`). The sessionless
signature verification in `user_setup._resolve_signed_user` was traced end to end and fails
closed on every branch (absent/empty `auth_user`, unresolvable `auth_user`, and a tampered
signature all refuse cleanly, confirmed against `test_enrollment_page_refuses_an_invalid_signature`
and its sibling tests). `pas_plugin.authenticateCredentials`'s new routing decision is a pure
read with no member-data write, and `_2fa_enrollment_needed` is carried through `request.other`
only, immune to query-string forgery — consistent with the equivalent, already-tested guarantee
for the pre-existing pending-2FA flag.

The one genuine defect found is a write-side gap this phase's own new semantics expose: neither
of the two "disable 2FA" code paths (the single-user view and the bulk-for-all-users helper)
resets `two_factor_authentication_enrolled` back to `False`. Because this phase makes that flag
the sole input to the login-routing decision, a user who disables their second factor and is
later re-enabled — individually, in bulk, or simply by re-applying the install profile — is
routed straight to the code-entry page for a secret they have never seen (freshly minted or
absent), which they can never satisfy: a self-inflicted, unrecoverable login lockout. See CR-01.

Two related state-consistency and UI-matrix warnings, and two minor quality items, are recorded
below.

## Critical Issues

### CR-01: Disabling 2FA leaves `two_factor_authentication_enrolled` stale, causing an unrecoverable login lockout on re-enable

**File:** `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py:47-54`
**File:** `src/imio/googleauthenticator/helpers.py:1136-1150` (`disable_two_factor_authentication_for_users`)

**Issue:** Both places that turn a user's second factor off clear `enable_two_factor_authentication`
(and, for the single-user view, `two_factor_authentication_secret` and `bar_code_reset_token`)
but never touch `two_factor_authentication_enrolled`. This phase's `pas_plugin.authenticateCredentials`
now uses exactly that stale property, through `has_completed_enrollment`, to decide whether a
2FA-enabled user is routed to the enrollment page (with a QR code) or the code-entry page (which
renders no QR at all).

Concrete reachable sequence, no bulk-enable view or admin action required beyond a normal
reinstall/reapply:

1. A user completes enrollment: `enable=True`, `secret=<X>`, `enrolled=True`.
2. `globally_enabled` is off; the user (or an admin) calls
   `@@disable-two-factor-authentication` (allowed while the setting is off — this is the
   documented, intended path). Result: `enable=False`, `secret=''`, `bar_code_reset_token=''`,
   but **`enrolled` is still `True`**.
3. `globally_enabled` is turned back on and the `imio.googleauthenticator:default` profile is
   re-applied (a normal, supported, already-tested operation — see
   `test_reapply_profile_keeps_plugin_first_and_unique`). `setuphandlers._enroll_existing_users`
   sees `enable_two_factor_authentication` is `False` and sets it back to `True` — by design
   (D-02) it mints **no** seed.
4. The account is now `enable=True`, `secret=''`, `enrolled=True` (stale).
5. At the next login, `pas_plugin.authenticateCredentials` computes
   `enrollment_needed = not has_completed_enrollment(user)` = `not True` = `False`. The user is
   routed to `@@google-authenticator-token` (the code-entry page), never to
   `@@setup-two-factor-authentication`. `get_secret(user)` returns `None` (empty stored secret,
   no seed to decrypt), so no TOTP code can ever validate — every submission is "Invalid token",
   and repeated attempts trip the shared lockout counter (`register_failed_second_factor`)
   instead of ever succeeding.

The same lockout is reached even more directly through the pre-existing, unmodified
`@@google-authenticator-enable-for-all-users` view: `enable_two_factor_authentication_for_users`
calls `get_or_create_secret(user)` unconditionally, silently minting a *fresh* secret for the
disabled-then-bulk-re-enabled user with no QR ever shown to them (that view has no user-facing
display step at all), while `enrolled` is still `True` from their earlier enrollment — the same
"routed to code-entry, secret never seen" lockout, reachable in a single admin click.

This is a genuine authentication-availability defect newly exposed by this phase: before
`two_factor_authentication_enrolled` existed, `enable_two_factor_authentication_for_users` and
`_enroll_existing_users` re-minting/re-flagging a disabled account was harmless (the routing
decision had no enrollment concept to get out of sync). Now it deterministically locks the user
out of their own account through the normal login path, with no self-service recovery (the
"Regenerate recovery codes" action that could otherwise get them a QR again requires being
logged in — which is exactly what this bug prevents).

**Fix:** Reset `two_factor_authentication_enrolled` to `False` wherever
`enable_two_factor_authentication` is cleared, so a re-enabled account is routed back through
enrollment instead of the code-entry page:

```python
# browser/disable_two_factor_authentication.py
user.setMemberProperties(
    mapping={
        'enable_two_factor_authentication': False,
        'two_factor_authentication_secret': '',
        'bar_code_reset_token': '',
        'two_factor_authentication_enrolled': False,
        }
    )
```

```python
# helpers.py: disable_two_factor_authentication_for_users
if has_enabled_two_factor_authentication(user):
    user.setMemberProperties(mapping={
        'enable_two_factor_authentication': False,
        'two_factor_authentication_enrolled': False,
    })
```

## Warnings

### WR-01: `disable_two_factor_authentication_for_users` (bulk disable-for-all) leaves the stored seed and reset token behind, unlike the single-user disable view

**File:** `src/imio/googleauthenticator/helpers.py:1136-1150`

**Issue:** `DisableTwoFactorAuthentication.disable()` (single account) clears three properties:
the enable flag, `two_factor_authentication_secret`, and `bar_code_reset_token`. The bulk
equivalent this phase's newly-gated `@@google-authenticator-disable-for-all-users` view calls,
`disable_two_factor_authentication_for_users`, clears only the enable flag — the commented-out
`# get_or_create_secret(user)` line even shows the secret was consciously left alone. Combined
with CR-01, every account touched by a bulk disable keeps its old seed live in storage
indefinitely; if that account is ever re-enabled without a fresh QR step (which, per CR-01, is
exactly what happens today), the stale seed silently becomes valid again with no user awareness
of what secret is now "current."

**Fix:** Bring the bulk path in line with the single-user path — clear the same set of
properties (and, per WR-01/CR-01 together, the enrollment-completion flag too):

```python
if has_enabled_two_factor_authentication(user):
    user.setMemberProperties(mapping={
        'enable_two_factor_authentication': False,
        'two_factor_authentication_secret': '',
        'bar_code_reset_token': '',
        'two_factor_authentication_enrolled': False,
    })
```

### WR-02: `settings_helper.py`'s "Enable" and "Disable" link conditions can both be true at once, for an untested state

**File:** `src/imio/googleauthenticator/browser/settings_helper.py:26-74`
**File:** `src/imio/googleauthenticator/tests/test_settings_helper.py:121-146` (`test_disable_link_is_offered_only_when_enrolled_and_globally_disabled`)

**Issue:** `show_enable_two_factor_authentication_link` is `not has_completed_enrollment(user)`,
independent of the enable flag or the global setting. `show_disable_two_factor_authentication_link`
is `has_enabled_two_factor_authentication(user) and not is_two_factor_authentication_globally_enabled()`,
independent of enrollment completion. For an install-time bulk-enrolled account
(`enable=True`, `enrolled=False`) once `globally_enabled` has been turned back off before that
account's first login, both conditions evaluate `True` simultaneously: the user's menu offers
"Enable two-step verification" and "Disable two-step verification" at the same time for the same
unfinished feature.

The requirement's own test method name — "offered only when enrolled and globally disabled" —
describes a stronger condition than the code implements (`enrolled` is not part of the
`show_disable` predicate at all), and the four combinations it actually exercises always keep
`enrolled` equal to the enable flag, so this specific state (`enabled=True, enrolled=False,
globally_enabled=False`) is never probed by `test_disable_link_is_offered_only_when_enrolled_and_globally_disabled`
or by `test_every_settings_combination_leaves_enrollment_reachable` (which always sets
`enabled=True` and only checks that *some* route to enrollment exists, not that the two links
don't contradict each other).

This does not strand anyone — the enrollment route is still offered — but it is a genuine,
reachable, and currently untested UI inconsistency: two contradictory actions shown together to
a user who has not yet scanned a QR code.

**Fix:** Either fold enrollment completion into `show_disable_two_factor_authentication_link`
(`has_enabled_two_factor_authentication(user) and has_completed_enrollment(user) and not
is_two_factor_authentication_globally_enabled()`), or add the missing test-matrix cell
(`enabled=True, enrolled=False, globally_enabled=False`) to
`test_disable_link_is_offered_only_when_enrolled_and_globally_disabled` asserting the intended
behaviour explicitly, so a reviewer can tell whether the overlap is accepted or a defect.

### WR-03: `testing.py`'s layer-wide override of `globally_enabled` means most tests run against a non-default configuration

**File:** `src/imio/googleauthenticator/testing.py:30-48`

**Issue:** `ImiogoogleauthenticatorLayer.setUpPloneSite` now forces `globally_enabled = False` and
clears `TEST_USER_NAME`'s enable flag immediately after the default profile is applied. This is a
documented, deliberate test-isolation choice (comment explains why), and the `True` (production
default) path is exercised explicitly by several tests
(`test_setuphandlers.py::test_install_enrolls_every_pre_existing_account_without_a_seed`,
`test_pas_plugin.py`, `test_user_setup.py::TestEnrollmentRedirect`), so the default configuration
is not uncovered. Flagged here only because the review brief called this file out specifically:
worth confirming during future maintenance that any *new* test added to this suite which forgets
to explicitly set `globally_enabled` is silently exercising the off-by-default fixture state, not
the schema's real `default=True` — a maintenance trap rather than a present defect.

**Fix:** No code change required. Consider a comment or a small assertion in one canonical test
(e.g. in `test_generic.py::test_product_is_installed`) that pins the schema-level default to
`True`, independent of the layer's own runtime override, so a future edit to the schema default
cannot silently drift without a test noticing.

## Info

### IN-01: Dead branch in `pas_plugin.authenticateCredentials`

**File:** `src/imio/googleauthenticator/pas_plugin.py:353-356`

**Issue:** 
```python
if credentials.get('extractor') != self.getId():
    return None
return None
```
Both branches return `None` unconditionally; the `if` decides nothing. Pre-existing (not
introduced by this phase's diff), but it sits in a file this phase substantially edited and is
worth a cleanup pass since it reads as if it should have differing behaviour.

**Fix:** Collapse to a single `return None`, or restore whatever differing behaviour the
conditional was originally meant to express.

### IN-02: `DisableTwoFactorAuthentication.disable()` reports success for a no-op

**File:** `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py:47-61`

**Issue:** Once past the anonymous and `globally_enabled` guards, `disable()` unconditionally
writes the three properties and unconditionally shows "You have successfully disabled the
two-step verification for your account," even when the caller never had 2FA enabled in the first
place (flag already `False`, secret already empty). This is the same class of "false success for
an empty/no-op operation" this codebase treats as a defect elsewhere (see `T-03-21`'s zero-user
bulk "Changes saved." and `T-03-23`'s account-this-plugin-cannot-gate refusal). Pre-existing
behaviour, not modified by this phase's new `globally_enabled` guard (which only adds an earlier
`return None`), so not scored as a blocker here, but worth folding into a future pass over this
same "false success" defect class.

**Fix:** Optional — gate the success message on `has_enabled_two_factor_authentication(user)`
being true before the write, and skip both the write and the message otherwise (or show a
neutral "nothing to disable" message).

---

_Reviewed: 2026-08-07T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
