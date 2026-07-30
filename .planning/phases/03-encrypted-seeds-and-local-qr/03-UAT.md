---
status: testing
phase: 03-encrypted-seeds-and-local-qr
source: [03-VERIFICATION.md]
started: 2026-07-30T15:10:00Z
updated: 2026-07-30T16:05:00Z
---

## Current Test

[testing complete — 1 test, 1 issue]

## Tests

### 1. Enrol with a real TOTP authenticator app and log in end to end

expected: QR renders and is scannable as displayed (a `data:` URI — no outbound request in the browser network panel); the `otpauth://` label reads `<username>@<domain>`; the app's 6-digit code is accepted at enrollment; after logout and a fresh username/password login the app's current code is accepted at `@@google-authenticator-token` and the user reaches the site authenticated.
result: issue
reported: "I managed to enable my MFA. I entered my OTP as a confirmation. However, if I logout and login again, it doesn't ask for my OTP and log in without MFA. If I manually navigate to the view @@google-authenticator-token and enter my OTP, it yields an error 500 no matter if my OTP is correct or not. TypeError: Incorrect secret at imio.googleauthenticator.helpers line 296 validate_token -> onetimepass line 100 get_hotp"
severity: blocker

partial_pass: |
  The enrollment half of this test PASSED — QR rendered, was scannable, and the app's
  6-digit code was accepted at `@@setup-two-factor-authentication`. That exercises the
  phase-3 deliverables directly: local `qrcode` rendering (no outbound request) and the
  Fernet encrypt → decrypt round trip on a real seed a real phone parsed.
  The login half FAILED.

why_human: Requires a physical or virtual TOTP authenticator app scanning a real QR code
rendered by a running `bin/instance`, plus a live login round trip — not executable by an
automated agent. Deliberately deferred to end-of-phase per
`workflow.human_verify_mode=end-of-phase` (03-03-PLAN.md Task 2's `<verify><human-check>`);
03-03-SUMMARY.md confirms it was not performed during execution.
`test_seed_encryption_round_trip` proves the seed survives Fernet encryption and that
`onetimepass` accepts a computed token — it does not prove what a phone parses, displays,
or accepts as a fresh code.

setup: This phase's feature is not deployable until the `industrialisation` repo's Puppet
`concat::fragment` ships the key (out of repo, tracked). To run this test locally, generate
a key and export it before starting Zope:

    export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY="$(bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())")"
    bin/instance fg

covers: ROADMAP Phase 3 success criterion 4, SEC-06 (160-bit `os.urandom` seed — the
entropy half is machine-verified; the real-app acceptance half is not)

## Summary

total: 1
passed: 0
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- gap_id: G-03-1
  truth: "After logout and a fresh username/password login, a 2FA-enabled user is redirected to @@google-authenticator-token instead of being logged in on the password alone"
  status: failed
  reason: "User reported: if I logout and login again, it doesn't ask for my OTP and log in without MFA"
  severity: blocker
  test: 1
  root_cause: |
    CONFIRMED AND REPRODUCED. The reporter enrolled and logged in as the Zope root
    `admin` (buildout `inituser`), which lives in the ROOT acl_users, not the Plone
    site's. Probed with plone.app.testing's SITE_OWNER_NAME, the exact analog:

      root acl_users .getUserById('admin')  -> <PropertiedUser 'admin'>
      site acl_users .getUserById('admin')  -> None
      api.user.get(username='admin')        -> MemberData ... used for /acl_users
      enable_two_factor_authentication      -> True   (genuinely persisted)
      plugin.authenticateCredentials(creds) -> None, credentials NOT emptied,
                                               no Location header == NO veto
      site auth plugin source_users         -> None
      site auth plugin session              -> None

    The flag is not the problem and neither is the user lookup — both resolve fine.
    The bail-out is pas_plugin.py:139-141: the plugin validates the password by
    delegating to the *Plone site's* other IAuthenticationPlugins, and for a
    root-acl_users account every one of them returns None. `authorized is None`
    therefore returns early, BEFORE the credential wipe and the signed redirect.
    Control then reaches the root acl_users, which does hold that user, and it
    authenticates the password — a session on one factor.

    NOT A PHASE-3 REGRESSION. This is a pre-existing structural boundary (present
    upstream): a plugin installed in the site's PAS cannot gate a Zope-root login.
    The project's Core Value scopes to "in-site users", so protecting the root
    admin is arguably out of scope. The IN-SCOPE defect is the false assurance —
    `@@setup-two-factor-authentication` enrols such an account, writes the flag,
    and reports "Two-step verification is successfully enabled for your account"
    for a login it can never gate. That is precisely the silent
    security-control-removal pattern this project's constraints exist to prevent.
  artifacts:
    - path: "src/imio/googleauthenticator/pas_plugin.py"
      issue: "line 139-141 returns early for any account no site auth plugin can validate, silently declining to veto instead of failing closed"
    - path: "src/imio/googleauthenticator/browser/forms/user_setup.py"
      issue: "enrols an account outside the site's acl_users and reports success — false assurance"
  missing:
    - "Refuse enrolment (or warn unmistakably) when the account is not in the site's own acl_users — portal.acl_users.getUserById(id) is None is the exact test"
    - "Re-run this UAT's login half with a real Plone member account: phase 3 success criterion 4 is still UNVERIFIED end to end, since the reporter's run never reached the token form"
    - "No automated test asserts the positive interception path — test_login_is_refused_when_seed_key_is_broken asserts only the refusal, and its non-vacuity control (line 174) discards the return value. Add a test asserting credentials are emptied and a signed Location is set."
    - "Decide explicitly whether a Zope-root login is in scope; if it is, the plugin must also be installed in the root acl_users, which is a roadmap-level change, not a gap fix"

- gap_id: G-03-2
  truth: "Submitting a token at @@google-authenticator-token returns a form error, never an HTTP 500"
  status: failed
  reason: "User reported: it yields an error 500 no matter if my OTP is correct or not — TypeError: Incorrect secret"
  severity: major
  test: 1
  root_cause: "CONFIRMED AND REPRODUCED under test. helpers.validate_token (helpers.py:296) passes get_secret()'s return value straight into onetimepass.valid_totp. get_secret returns None whenever the resolved user has no stored seed -- its `if isinstance(secret, basestring) and secret:` guard falls through with an implicit None return (helpers.py:229-233). onetimepass.get_hotp then base32-decodes None and raises TypeError('Incorrect secret'), which is an unhandled 500. Reached whenever the token form resolves no secret-bearing user: TokenForm.handleSubmit only looks up a user when the signed `auth_user` parameter is present (token.py:80-83), so a manual visit passes user=None and get_secret falls back to api.user.get_current(); TokenForm.updateFields has already blanked the __ac cookie (token.py:137), so that POST is anonymous and getProperty returns the memberdata default ''. Probe: get_secret -> None, validate_token -> TypeError: Incorrect secret."
  artifacts:
    - path: "src/imio/googleauthenticator/helpers.py"
      issue: "validate_token (line ~296) does not guard a falsy secret before calling valid_totp"
  missing:
    - "Guard in validate_token — the single shared function both callers (token form, setup form) route through: no secret means the token cannot be valid, so return False rather than letting onetimepass raise. Fixing it there also covers the setup form's unenrolled-user path."
    - "Regression test: validate_token returns False (does not raise) for a user with no stored seed"
