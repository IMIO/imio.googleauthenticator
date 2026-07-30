---
status: complete
phase: 03-encrypted-seeds-and-local-qr
source: [03-VERIFICATION.md]
started: 2026-07-30T15:10:00Z
updated: 2026-07-30T16:40:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Enrol with a real TOTP authenticator app and log in end to end

expected: QR renders and is scannable as displayed (a `data:` URI — no outbound request in the browser network panel); the `otpauth://` label reads `<username>@<domain>`; the app's 6-digit code is accepted at enrollment; after logout and a fresh username/password login the app's current code is accepted at `@@google-authenticator-token` and the user reaches the site authenticated.
result: pass
reported: "I saved my MFA for user cadam, logged out, logged in, it prompted to enter OTP, I did and it worked"

evidence: |
  Verified end to end across three runs, the third of which closed it. Took three runs
  because the first used a Zope-root account (G-03-1) and the second hit a first-login
  lockout with no enrolment path (see Observations).

  CONFIRMED:
  - QR rendered and was scannable at displayed size, from a `data:` URI with no
    outbound request — local `qrcode` rendering, phase 3's SEC-05 deliverable.
  - The authenticator app's 6-digit code was accepted at
    `@@setup-two-factor-authentication`, proving the Fernet encrypt → decrypt round
    trip holds on a seed a real phone parsed, not just a computed one.
  - A fresh username/password login as member `cadam` was intercepted and redirected
    to `@@google-authenticator-token?valid_until=...&auth_user=cadam&extra=&signature=...`
    — a correctly signed URL.
  - That app's current code was accepted at the token form and the session reached the
    site as the authenticated user.

  - The `otpauth://` label renders as `<username>@<domain>`. Initially recorded as
    inferred rather than observed (the payload had not been read back); the reporter
    subsequently confirmed the label directly, so no part of this test now rests on
    inference.

  Enrolment route used: `@@google-authenticator-disable-for-all-users` to clear the
  flag (secrets are preserved), log in as `cadam` unchallenged, enrol via
  `@@setup-two-factor-authentication`, then re-login. The bar-code reset path — the
  intended recovery route — was not available at that point, because it was broken
  (G-03-3). It was exercised and confirmed working after that fix landed.

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
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Outcome

Phase 3's own success criterion 4 is **verified end to end**: a real authenticator app
enrolled against a locally-rendered QR, and its code logged a real Plone member in
through the token form. Both phase-3 deliverables under test — local `qrcode` rendering
with no outbound request (SEC-05) and the Fernet seed round trip (SEC-06's storage half)
— hold against real hardware.

The single test passes, so `issues: 0` is accurate as a UAT tally. But three defects
were found along the way and are recorded in `## Gaps` below. **None is a phase-3
regression** — all three are pre-existing, and none is a phase-3 deliverable:

| Gap | What | Disposition | Status |
|-----|------|-------------|--------|
| G-03-1 | 2FA silently bypassed for Zope-root accounts | Scope accepted; false assurance fixed (T-03-23) | resolved `01a8c04` |
| G-03-2 | Unguarded null seed → HTTP 500 at the token form | Guard in the shared `validate_token` | resolved `3d97681` |
| G-03-3 | Bar-code reset email dies on non-ASCII | `charset='utf-8'` to `MailHost.send` | resolved `d8cda87` |

**All three gaps were closed after this table was written** — G-03-2 and G-03-3 by direct
fix, G-03-1 during `/gsd-secure-phase 03`, where it surfaced as blocking threat T-03-23 and
was dispositioned scope-accept plus false-assurance-mitigate. See each gap's `resolution`
below and `03-SECURITY.md`. The recovery path (G-03-3) was re-run in the browser afterwards
and the email arrived, so the locked-out-user route this phase depends on is observed
working, not merely unit-tested.

## Gaps

- gap_id: G-03-1
  truth: "After logout and a fresh username/password login, a 2FA-enabled user is redirected to @@google-authenticator-token instead of being logged in on the password alone"
  status: resolved
  reason: "User reported: if I logout and login again, it doesn't ask for my OTP and log in without MFA. Root-caused to a Zope-root account; a later run with a real Plone member was intercepted correctly, so this is not a login-path defect."
  severity: major
  resolved_by: "helpers.is_site_local_user + refusal guards at both self-service claim sites"
  resolved_at: 2026-07-30
  resolution: |
    Disposed during /gsd-secure-phase 03, where it surfaced as blocking threat T-03-23
    (high). The scope half is ACCEPTED (SECURITY.md R-03-03): a Zope-root login is not
    gated by this plugin and cannot be, since the plugin lives in the site's acl_users;
    the project targets in-site users, and gating root logins would mean installing the
    plugin in the root acl_users — roadmap-level, not a phase-03 fix.
    The false-assurance half is MITIGATED: user_setup.py and reset_bar_code.py now refuse
    an account absent from the site's acl_users, before any flag write or seed mint, and
    no QR is rendered for it.
    Guard scope determined empirically, not assumed: api.user.get_users() returns only
    site members, so the bulk-enrolment path cannot reach a root account and needs no
    guard; the test asserts that, so the day it changes, this decision fails loudly.
    Verified failing without the guard, with the assertions ordered so the security
    property (no flag written) is what breaks first rather than the return value.
    Suite green at 46 tests, 0 failures, 0 errors.
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
  status: resolved
  resolved_by: "falsy-secret guard in helpers.validate_token"
  resolved_at: 2026-07-30
  resolution: |
    Fixed directly rather than via a gap-closure plan, at the reporter's request.
    Guarded in validate_token rather than in its three callers (token.py:96,
    reset_bar_code.py:94, user_setup.py:68) — all route through it, and
    reset_bar_code.py had the same unreported exposure.
    Verified failing first by stashing only the guard: the test errors with the
    reported `TypeError: Incorrect secret`, and passes with it.
    The test also pins the guard's narrowness — an undecryptable stored seed must
    still raise ValueError, since answering "wrong token" to a broken-key condition
    would turn a fail-closed refusal into a silent downgrade.
    Suite green at 44 tests, 0 failures, 0 errors.
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

- gap_id: G-03-3
  truth: "Requesting a bar-code reset sends the reset email and confirms success"
  status: resolved
  resolved_by: "charset='utf-8' passed to host.send in request_bar_code_reset.py"
  resolved_at: 2026-07-30
  resolution: |
    Fixed directly rather than via a gap-closure plan, at the reporter's request.
    Test written first and confirmed to FAIL on the unfixed code (0 messages handed
    to MailHost, the UnicodeEncodeError having been swallowed by `except ValueError`),
    with a non-vacuity control asserting the handler reached the send step at all —
    that control initially passed vacuously on leftover memberdata from its sibling
    test, which is why setUp now clears `bar_code_reset_token`.
    Suite green at 43 tests, 0 failures, 0 errors.
    CONFIRMED IN THE BROWSER (2026-07-30, after the fix): the reporter ran the reset flow
    and received the email. Delivery is therefore proven end to end, not merely past the
    encoding step where the original traceback died. The automated test still stops at
    MailHost by design — it patches MailBase._send — so delivery is covered by this
    observation rather than by CI.
  reason: "User reported: 'Request for bar-code reset is failed! An unexpected error occurred.' — UnicodeEncodeError: 'ascii' codec can't encode character u'\\xe9' in position 83"
  severity: major
  test: 1
  root_cause: |
    CONFIRMED by traceback plus reading Products.MailHost 2.13.2 source.
    `request_bar_code_reset.py:98-102` calls `host.send(mail_text, immediate=True,
    msg_type='text/html')` and passes NO `charset`. MailHost.send's signature is
    `send(messageText, mto, mfrom, subject, encode, immediate, charset, msg_type)`,
    and `_mungeHeaders` (MailHost.py:400-402) does:

        if isinstance(messageText, unicode):
            messageText = _try_encode(messageText, charset)

    with `_try_encode` (MailHost.py:506-512) falling back to bare `text.encode()`
    — i.e. ASCII — when charset is None. The rendered template is unicode and
    contains a non-ASCII character, so it dies on the first accented byte.

    The `charset='utf-8'` on line 94 is a red herring: it is an argument to the
    page template, not to MailHost. The template uses it only to set its own
    `Content-Type` header (and a RESPONSE header), so the message correctly
    DECLARES utf-8 while MailHost is still told nothing and encodes as ASCII.

    The é does not come from the template — `request_bar_code_reset_email.pt` is
    pure ASCII. It comes from a value interpolated into it at render time: the
    site's `email_from_name`, and/or the `i18n:translate`d Subject line resolving
    through the French catalogue. Position 83 falls in that header region.

    Not a 500: UnicodeEncodeError subclasses ValueError, so line 112's
    `except ValueError` catches it and degrades to the reported status message.
    Only one MailHost.send call site exists in the package, so the fix is not
    repeated elsewhere (verified by grep).
  artifacts:
    - path: "src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py"
      issue: "line 98-102: host.send() omits charset, so a unicode body is ASCII-encoded"
  missing:
    - "Pass charset='utf-8' to host.send — one line, matching the Content-Type the template already declares"
    - "Regression test: a reset request succeeds when email_from_name (or the translated subject) contains a non-ASCII character. A test asserting only ASCII content would pass against the broken code."
    - "Resolve the declared-type contradiction while in there: the template's own header says text/plain, the call says msg_type='text/html', and the body contains an <a href> anchor. _mungeHeaders honours the template's existing Content-Type, so msg_type is currently inert — the anchor is delivered as plain text."

## Observations (not gaps)

Raised by the reporter or found while diagnosing; none blocks this phase, none has
been actioned. Recorded so they are not silently lost.

- **Reset form re-asks for the username.** Reporter: "weird because I just tried to
  login so Plone should already have my username, but it's not breaking." Correct —
  the signed token URL already carries `auth_user`, so the field could be prefilled.
  Cosmetic, but see the next item before treating it as purely cosmetic.
- **Username-enumeration oracle on the reset form.** `request_bar_code_reset.py:116`
  answers "Invalid username." for an unknown user and success for a known one, on an
  unauthenticated endpoint. Standard practice for a password-reset-shaped flow is an
  identical response either way. Minor, pre-existing, and a deliberate-decision call
  rather than a bug — but it is a security-relevant one in a 2FA package.
- **A user enrolled by `globally_enabled` is never shown a QR.** The reporter's member
  had 2FA on with a generated secret but no way to obtain an OTP, so first login was a
  lockout whose only exit is the (broken) reset path. This is the onboarding gap that
  turned G-03-3 from an inconvenience into a dead end. Pre-existing and roadmap-level,
  not a phase-3 regression.
