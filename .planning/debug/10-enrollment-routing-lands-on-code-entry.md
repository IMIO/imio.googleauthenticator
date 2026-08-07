---
status: diagnosed
trigger: "For new users, the OTP is asked but they can reset it. (MFA-19 enrollment-routing
  failure, reported on server.dmsmail site \"PARAF-503\", 2026-08-07)"
created: 2026-08-07T00:00:00Z
updated: 2026-08-07T00:00:00Z
---

## Current Focus

hypothesis: the leading D-07 hypothesis (mint-then-abort asymmetry on the challenge() path)
  does NOT explain this symptom for new/creation-time-enrolled users -- REFUTED with evidence
  below, on both possible redirect mechanisms.
test: n/a -- investigation complete, diagnose-only mode.
expecting: n/a
next_action: none from this agent -- root cause for THIS symptom not found; see
  "What I could not confirm" below for the concrete next steps to hand to the operator/a
  follow-up investigation.

## Symptoms

expected: an account created after `imio.googleauthenticator` was installed, while
  `globally_enabled` is on, must be shown the enrollment page (QR code + secret) BEFORE being
  asked for a login code, since it has never completed second-factor setup (MFA-19).
actual: reported by the operator -- new users are asked for a one-time code at login (i.e. land
  on `@@google-authenticator-token`) without ever seeing an enrollment page; their only way in
  is the bar-code-reset-by-email flow.
errors: none reported -- a clean redirect to the wrong page, not a crash.
reproduction: NOT reproduced. Three independent end-to-end attempts, all using the real
  `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` layer and either a real testbrowser login-form
  POST or a real HTTP Basic Auth request that genuinely triggers `Unauthorized`, land the
  never-enrolled account on `@@setup-two-factor-authentication` every time -- see Evidence.
started: reported by the operator on 2026-08-07, on the "PARAF-503" `server.dmsmail` site,
  created via `imio.dms.mail:examples`, addon installed afterwards with `globally_enabled`
  already on (its shipped default).

## Eliminated

- hypothesis: D-07 asymmetry as literally described in `pas_plugin.py`'s comment -- signing the
    enrollment target mints a secret via `get_or_create_secret()`, and on the `challenge()`
    path the transaction is aborted, discarding that mint, so the signature the enrollment page
    receives does not validate, and the user falls back to a normal login-form retry.
  evidence: for a NEW user this mechanism cannot fire, because `userdataschema.
    userCreatedHandler` (adapter.py-style `@adapter(IBasicUser, IPrincipalCreatedEvent)`,
    userdataschema.py:113-139) already calls `get_or_create_secret(user)` and persists the
    secret in a normal, already-committed transaction AT ACCOUNT CREATION time -- long before
    any login attempt. By the time `sign_user_data()` (helpers.py:888-917) runs during a later
    login, its own `get_or_create_secret(user)` call (line 909) finds the secret already on the
    user's memberdata and performs a pure read, no write -- there is nothing left for a
    `transaction.abort()` on the challenge() path to discard. Confirmed by direct property
    inspection in a written-and-run experiment: `two_factor_authentication_secret` was already
    non-empty immediately after `api.user.create()` with `globally_enabled=True`, before any
    login request was made.
  timestamp: 2026-08-07

- hypothesis: `has_completed_enrollment()` (helpers.py:1062-1097) returns a truthy value for a
    brand-new, never-enrolled account because GenericSetup's boolean-property XML parsing
    (`memberdata_properties.xml:11`, `<property type="boolean">False</property>`) leaves the
    Python-level default as the string `'False'` (truthy in Python) instead of the bool `False`.
  evidence: directly inspected the live property on a freshly created account in the real
    functional-testing layer: `two_factor_authentication_enrolled=False (type <type 'bool'>)`,
    and `has_completed_enrollment(created_user)` returned `False`. Not a string, not a
    mis-cast value. `enrollment_needed = not has_completed_enrollment(user)` therefore
    correctly evaluates to `True` for this account.
  timestamp: 2026-08-07

- hypothesis: the login-form POST for a brand-new user actually goes through the aborting
    `challenge()` path in practice (not the committing `IPubBeforeCommit` subscriber the
    package's own comments say normal login-form POSTs use), and that is what exposes D-07.
  evidence: tested BOTH mechanisms directly and independently, not just the one the package's
    own comments say is normal:
    (1) `_login_browser` (the same helper `TestEnrollmentRedirect` uses) against `/login_form`
    -> lands on `@@setup-two-factor-authentication` with a valid QR-bearing signature.
    (2) a real HTTP Basic Auth request against a protected page (`@@personal-information`),
    which genuinely triggers `Unauthorized` -> `challenge()` on an aborted transaction (the
    exact mechanism `test_challenge_writes_nothing`'s docstring documents and
    `test_challenge_fires_on_unauthorized` exercises for an already-enrolled user) -> ALSO
    lands on `@@setup-two-factor-authentication` with a valid signature, for a never-enrolled,
    creation-time-enrolled account. Both mechanisms produce the correct redirect. D-07 is a
    real, correctly-documented residual defect, but its trigger condition (a secret that still
    needs minting at sign time) is not met by any account `userCreatedHandler` has touched.
  timestamp: 2026-08-07

- hypothesis: this is actually the same defect as the sibling debug session
    `.planning/debug/10-install-enrollment-not-applied.md` (a GenericSetup step-ordering race
    between `imio.googleauthenticator`'s install step and the `memberdata-properties` step,
    which can make `_enroll_existing_users()`'s property write silently no-op in a
    large buildout like `server.dmsmail`) -- i.e. the operator's two reports might be the same
    root cause described from two angles.
  evidence: read that session file in full. Its own mechanism is bounded to code that runs
    DURING the one-time install transaction (`_enroll_existing_users`, install-time bulk
    enrollment of PRE-EXISTING accounts). By the time any later, real HTTP request occurs --
    including a brand-new account's creation via `userCreatedHandler`, which is what "new
    users" in this report means -- the install transaction has long since finished and
    `portal_memberdata`'s properties are declared either way, regardless of which order the
    two one-time steps ran in. That session's own note reaches the same conclusion: "accounts
    created AFTER install ... are enrolled correctly." The two reports are two different,
    independently-confirmed defects (or, for THIS one, no defect I could find at all), not one.
  timestamp: 2026-08-07

## Evidence

- timestamp: 2026-08-07
  checked: `src/imio/googleauthenticator/pas_plugin.py` (full file), specifically
    `authenticateCredentials` (lines 201-356), `_mark_2fa_pending` (68-88), `send_2fa_redirect`
    (91-170), and `challenge` (358-387).
  found: the routing decision is computed exactly once, at line 246:
    `enrollment_needed = not has_completed_enrollment(user)`, independent of which redirect
    mechanism (`IPubBeforeCommit` subscriber vs. `IChallengePlugin.challenge`) ends up applying
    it. Both mechanisms call the same shared `send_2fa_redirect` (line 91), which reads the
    stashed boolean from `request.other` (line 137) and signs `@@setup-two-factor-authentication`
    or `@@google-authenticator-token` accordingly. `_mark_2fa_pending`'s only production call
    site passes the real `enrollment_needed` value (line 349); the function's `False` default
    is used only by direct test callers, never by the routing decision.
  implication: the routing decision itself has one code path, and it is a pure function of
    `has_completed_enrollment(user)` -- nothing in `authenticateCredentials`, `_mark_2fa_pending`,
    or `send_2fa_redirect` treats a brand-new account differently from an install-time bulk
    -enrolled one at the routing-decision level.

- timestamp: 2026-08-07
  checked: `src/imio/googleauthenticator/userdataschema.py`, `userCreatedHandler`
    (lines 102-142), against `src/imio/googleauthenticator/setuphandlers.py`,
    `_enroll_existing_users` (84-120).
  found: the two enrollment mechanisms leave DIFFERENT states on the account.
    `_enroll_existing_users` (install-time, pre-existing accounts, MFA-15) sets ONLY
    `enable_two_factor_authentication=True`; it deliberately does not mint a secret (D-02).
    `userCreatedHandler` (runtime, brand-new accounts) sets `enable_two_factor_authentication
    =True` AND calls `get_or_create_secret(user)`, minting and persisting a secret immediately.
    NEITHER writer ever touches `two_factor_authentication_enrolled` -- confirmed the only
    writer of that property anywhere in the package is `mark_enrollment_completed`
    (helpers.py:1100-1110), called only from `browser/forms/user_setup.py`'s `handleSubmit` on
    a successfully verified first code (line 212).
  implication: whichever mechanism enrolled the account, `has_completed_enrollment` reads the
    same, untouched-until-first-success property. There is no code path by which either
    enrollment mechanism could leave `two_factor_authentication_enrolled=True` on an account
    that has not actually completed setup.

- timestamp: 2026-08-07
  checked: `Products.GenericSetup-1.8.11` `PropertyManagerHelpers._initProperties`
    (utils.py:716-773) -- how `<property type="boolean">False</property>` in
    `memberdata_properties.xml` is actually parsed -- and then confirmed empirically rather
    than trusting the source read alone (see next entry).
  found: boolean property text is passed through `_convertToBoolean` (line 768), not stored
    verbatim as a string.
  implication: no XML-boolean-parsing defect exists in this GenericSetup version for this
    file's declarations.

- timestamp: 2026-08-07
  checked: wrote and ran a new experiment inside `bin/test`'s real
    `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` layer (not committed -- deleted after use,
    per the diagnose-only instruction): `settings.globally_enabled = True` +
    `transaction.commit()` BEFORE `api.user.create(...)`, mirroring "globally enabled already
    on at install time, new user created afterwards" exactly, then a real testbrowser
    `_login_browser` POST to `/login_form` (the same helper `TestEnrollmentRedirect` and
    `TestPubBeforeCommitRedirect` use).
  found:
    ```
    enable_two_factor_authentication=True
    two_factor_authentication_secret=True (non-empty)
    two_factor_authentication_enrolled=False (type <type 'bool'>)
    has_completed_enrollment=False
    landed on URL: http://nohost/plone/@@setup-two-factor-authentication?valid_until=...&auth_user=...&signature=...
    ```
  implication: the exact scenario in the trigger reproduces correctly in this repository's own
    code and test harness -- the user is routed to the enrollment page with a validly-signed
    URL, not the code-entry page.

- timestamp: 2026-08-07
  checked: wrote and ran a second experiment, same account setup, but using a real HTTP Basic
    Auth request against a protected page (`@@personal-information`) to genuinely trigger
    `Unauthorized` -> `IChallengePlugin.challenge` on an aborted transaction -- the specific
    mechanism the D-07 comment blames, and the one `test_challenge_writes_nothing` and
    `test_challenge_fires_on_unauthorized` already prove aborts writes for other scenarios.
  found: `302 Moved Temporarily`, `Location` header containing
    `@@setup-two-factor-authentication?valid_until=...&auth_user=...&signature=...` -- a valid
    signature, not a refusal.
  implication: D-07's mint-then-abort asymmetry does not manifest for this account even when
    forced through the literal aborted-transaction path the comment describes, because (per
    the userCreatedHandler evidence above) there is no mint left to lose -- the secret was
    already committed at account-creation time, in a separate, earlier transaction.

- timestamp: 2026-08-07
  checked: `src/imio/googleauthenticator/tests/test_user_setup.py`, class
    `TestEnrollmentRedirect` (lines 638-955), specifically
    `test_install_enrolled_user_is_walked_through_enrollment_at_login` (693-764) and
    `test_abandoned_enrollment_is_routed_to_the_enrollment_page_again` (800-826).
  found: the first test's own setup comment explicitly avoids exercising
    `userCreatedHandler`'s creation-time enrollment path end-to-end (it creates the account
    with `globally_enabled=False`, THEN flips it on and re-applies the profile, specifically
    "so that `userdataschema.userCreatedHandler` does not itself enrol it at creation time...
    that would test creation-time enrolment (already existing behaviour) rather than
    install-time enrolment"). This confirms the task's own observation that no test exercises
    a real browser login end-to-end for a `userCreatedHandler`-enrolled account. However, the
    SECOND test (`test_abandoned_enrollment_is_routed_to_the_enrollment_page_again`) does cover
    the resulting STATE that path leaves (secret already minted via
    `get_or_create_secret(user, overwrite=True)`, `enrolled=False`) via a real browser login,
    and passes -- it is state-equivalent to what `userCreatedHandler` leaves, just constructed
    with a different helper call instead of going through the event handler itself.
  implication: the task's premise -- "the tests do not reproduce whatever is different in the
    real flow" -- is correct in the narrow sense that no test drives `userCreatedHandler`
    itself through a browser login. But the state that handler leaves behind IS covered by an
    existing, passing test, and my own new experiment closes the remaining, literal gap by
    driving `userCreatedHandler` itself. Both pass. The routing/signing code is not where the
    real-world divergence lives.

- timestamp: 2026-08-07
  checked: `.planning/debug/10-install-enrollment-not-applied.md` (a parallel, already-
    diagnosed session on the same operator report, different symptom: "For existing users,
    nothing is asked and they can log in without setting MFA").
  found: that session's confirmed root cause is a GenericSetup import-step-ordering race
    between `imio.googleauthenticator`'s install step and the globally-registered
    `memberdata-properties` step, which can make `_enroll_existing_users()`'s property write
    silently no-op in a large, multi-add-on buildout. Its own analysis states this is bounded
    to the one-time install transaction and explicitly does not affect accounts created
    afterwards via `userCreatedHandler`.
  implication: this is a genuinely separate, mirror-image defect (existing accounts under-
    enrolled vs. new accounts allegedly mis-routed) with a different, already-confirmed
    mechanism. It does not explain the "new users" symptom this session was asked to
    investigate, and my findings do not overlap with or duplicate that session's evidence.

- timestamp: 2026-08-07
  checked: `imio.dms.mail/imio/dms/mail/examples.py` (`add_test_users_and_groups`,
    lines 570-611) and the underlying `Products.CMFCore.RegistrationTool.addMember` ->
    `Products.PlonePAS.tools.membership.MembershipTool.addMember` ->
    `PluggableAuthService._doAddUser` chain (PluggableAuthService.py:985-1026).
  found: `_doAddUser` calls `notify(PrincipalCreated(user))` (line 1025) unconditionally after
    creating the account, for both `imio.dms.mail`'s own example-user creation and any
    standard Plone "add user" admin panel (which routes through the same
    `portal_registration.addMember`/`portal_membership.addMember` machinery) -- i.e. the same
    event `plone.api.user.create()` fires in my experiment. No evidence found of an
    alternative, real-world user-creation mechanism in the packages available in this
    environment that would bypass `IPrincipalCreatedEvent` for genuinely new, locally-created
    accounts.
  implication: whatever mechanism a real administrator used to create the reported "new
    users" on PARAF-503, if it is a standard Plone/PAS local-account creation path, it fires
    the same event my experiment fires, with the same observed (correct) result.

## Resolution

root_cause: "NOT CONFIRMED for this symptom. The leading hypothesis handed to this
  investigation -- D-07's documented mint-then-abort asymmetry between the committing
  `IPubBeforeCommit` login-POST path and the aborting `IChallengePlugin.challenge()` path --
  is REFUTED for a new/creation-time-enrolled user by direct, repeated, end-to-end evidence on
  BOTH redirect mechanisms: `userdataschema.userCreatedHandler` mints and persists that
  account's secret at account-creation time, in an already-committed transaction, so
  `sign_user_data()`'s later `get_or_create_secret()` call at login is a pure read with
  nothing for an aborted transaction to discard. `has_completed_enrollment()` was also
  confirmed, by direct property inspection, to correctly return a real Python `False` (not a
  truthy string) for such an account, so `enrollment_needed` correctly computes `True`. Three
  independent end-to-end reproductions of the operator's exact scenario (globally_enabled
  already on, new user created afterwards, real browser login-form POST; the same scenario via
  a genuinely aborting HTTP-Basic-Auth-triggered `Unauthorized`/`challenge()` request; and the
  pre-existing `test_abandoned_enrollment_is_routed_to_the_enrollment_page_again` covering the
  same resulting account state) all land the account on `@@setup-two-factor-authentication`
  with a valid signature, never on `@@google-authenticator-token`. I could not find, in this
  package's code or in the sibling packages available in this environment
  (`imio.dms.mail`, `server.dmsmail`), a mechanism that reproduces the reported symptom.
  This is an honest inconclusive result, not a disguised guess -- see 'What I could not
  confirm' below for what would be needed to close it."
fix: "Not applicable -- no confirmed root cause to fix. Do not apply the D-07 fix (making the
  challenge() path also mint-and-persist safely) as a blind fix for THIS report: it addresses
  a real but different-triggering-condition defect (an account with no pre-existing secret
  hitting the aborted path), which the evidence above shows is not what new/creation-time
  -enrolled accounts encounter."
verification: "not applicable -- no fix proposed."
files_changed: []
---

## What I could not confirm (recommended next steps for whoever picks this back up)

The routing decision, the signing mechanism, and both possible redirect paths for a genuinely
new, never-enrolled, `globally_enabled`-created account all behave correctly in this
repository's own code, exercised through its real functional-testing layer with a real
browser. I was unable to reproduce the operator's reported symptom by any mechanism available
to me. To make further progress, the following would need clarifying from the real "PARAF-503"
environment, since they are outside what this repository's code and test harness can show:

1. **Exact user-creation mechanism.** Confirm which UI/action actually created these "new
   users" on PARAF-503 -- `imio.dms.mail`'s own agent-management view, Plone's standard
   `@@usergroup-userprefs` add-user panel, or something SSO/Keycloak-backed. If any local
   accounts were instead provisioned through an external identity source that does not fire
   `Products.PluggableAuthService.interfaces.events.IPrincipalCreatedEvent`, `enable_two_
   factor_authentication` and the secret would never get set by `userCreatedHandler` at all --
   a different failure mode than the one reported ("OTP is asked" implies the enable flag IS
   set), but worth ruling out explicitly with the operator.

2. **The literal URL the user lands on.** Get the actual browser URL/server access log entry
   for one affected login, not just the rendered page's appearance. `@@setup-two-factor
   -authentication` (the enrollment form) and `@@google-authenticator-token` (the code-entry
   form) both ultimately render a "enter a code" field; if a signature happened to fail to
   validate for some environment-specific reason (e.g. a reverse proxy normalizing the
   `User-Agent` header differently between the login POST and the redirected GET, which feeds
   `get_browser_hash()`), the ENROLLMENT page would still render, just without its QR code
   (`user_setup.py`'s `updateFields`, lines 314-330, skips the QR/description update entirely
   when `_resolve_signed_user()` fails to validate) -- which could plausibly be mis-described
   as "asked for a code" even though the URL says `@@setup-two-factor-authentication`, not
   `@@google-authenticator-token`. Confirming the actual URL distinguishes this from a genuine
   mis-route.

3. **Whether this is in fact the same report as the sibling session.** Given
   `.planning/debug/10-install-enrollment-not-applied.md`'s confirmed root cause (existing
   accounts silently left unenrolled by a GenericSetup step-ordering race), it is worth
   double-checking with the operator whether the accounts they tested and called "new" were
   in fact the pre-existing `imio.dms.mail:examples` accounts (`scanner`, `encodeur`, `dirg`,
   `chef`, `agent`, `agent1`, `lecteur`) rather than genuinely-new, post-install accounts --
   a mix-up here would not be surprising given both reports came from the same UAT session on
   the same site, and would mean this symptom has no separate root cause to find at all.
