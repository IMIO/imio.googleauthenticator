---
status: testing
phase: 10-global-enforcement-and-enrollment
source: [10-06-SUMMARY.md, 10-VALIDATION.md, 10-REVIEW-FIX.md]
started: 2026-08-06T18:05:00Z
updated: 2026-08-07T09:00:00Z
resumed_on: 2026-08-07
---

## Current Test

number: 1
name: Install onto a site that already has accounts
expected: |
  A user whose account existed before the add-on was installed is shown the enrollment page
  with a QR code at their next login, and can complete enrollment — not asked for a code from
  an application they never set up.
awaiting: user response

## Setup needed for all three tests

```
export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY='jbC8PM1bwM3dFXKfT1hDd_wDHNa6OtstXhWKJLy7li0='
bin/instance fg
```

That key is a throwaway generated with this project's own `cryptography` library. Fine for a
local check, not for anything real.

Test 1 needs a site with several accounts where this add-on is **not yet installed**. Tests 2
and 3 work on a site with it already installed.

## Tests

### 1. Install onto a site that already has accounts

requirements: MFA-15, MFA-19 (together)

expected: A pre-existing account is walked through enrollment at next login, not locked out.

why_human: This is the exact failure the phase exists to prevent, and it was originally found by
running a real two-egg environment on 2026-08-05, not by a test. Installing onto a populated site
used to leave every existing account without a second factor; a careless fix instead locks them all
out by asking for codes from an application they never set up. Only a real install exercises the
whole path in one piece.

steps:
  1. Start from a site that has several accounts and where this add-on is NOT yet installed.
  2. Install the add-on with "Globally enabled" on.
  3. Log in as one of the accounts that existed before the install.
  4. Confirm you are shown the enrollment page with a QR code and the copyable setup key,
     NOT a code-entry prompt.
  5. Complete enrollment and confirm the login finishes.

fails_if: you are asked for a code before ever seeing a QR code, or you cannot get in at all.

result: issue
reported: "No. For existing users, nothing is asked and they can log in without setting MFA. For new users, the OTP is asked but they can reset it"
severity: blocker
reported_on: 2026-08-07

analysis_so_far: |
  Two separate failures in one report.

  (a) Accounts that existed before the install are not asked for a second factor at all. This is
      requirement MFA-15 not working. Since accounts created after the install ARE asked for a
      code, the login check itself works — so the enable flag is not being set on pre-existing
      accounts at install time.

  (b) Accounts created after the install are asked for a code without first being shown the
      enrollment page. This is requirement MFA-19 not working. Their only way in is the
      bar-code reset flow.

  The automated tests pass for both. That means the tests do not reproduce the real install
  conditions — the most likely reason is that the test applies the profile to a site where the
  add-on is ALREADY installed (the shared test layer applies it first), so the member-data
  properties are already declared and the flag write succeeds. On a genuine first install the
  ordering of profile steps may differ.

### 2. No settings combination strands a user

requirements: MFA-18 (success criterion 5)

expected: All four combinations leave a reachable route to the enrollment page.

why_human: The automatable half is green — a test named
`test_every_settings_combination_leaves_enrollment_reachable` covers it. The remaining half is a
judgement on a real site, confirming the route is not just present in the action list but actually
usable.

the four cases:

| Global setting | User completed enrollment? | Expected route |
|---|---|---|
| On | No | Routed to enrollment automatically at login |
| On | Yes | "Regenerate recovery codes" in the user menu |
| Off | No | "Enable two-step verification" in the user menu |
| Off | Yes | "Regenerate recovery codes" in the user menu |

note: the second row is the one to check hardest. "Regenerate recovery codes" shared its
visibility rule with the disable link, so making the disable link hide under global enforcement
would have hidden regeneration too, leaving that cell with no route at all. Decision D-15 gave the
regenerate action its own condition specifically to prevent that.

result: [pending]

### 3. Turning the second factor off and on again does not lock the user out (optional)

requirements: none directly — this confirms a defect found by the code review after the phase was
built (finding CR-01)

expected: After disabling and re-enabling, the user is shown the enrollment page again, not asked
for a code from a secret they never saw.

why_optional: This is already covered by an automated regression test,
`test_disable_then_reenable_does_not_lock_the_user_out_of_login`. It is offered here only because
you will have a running instance anyway, and because it was found late rather than during planning.
Skipping it is reasonable.

steps:
  1. As an enrolled user with the site-wide setting off, use "Disable two-step verification".
  2. Turn the site-wide setting back on (or re-enable that account some other way).
  3. Log in as that user.
  4. Confirm you are shown the enrollment page with a QR code, not a code-entry prompt.

fails_if: you are asked for a code you have no way to produce.

result: [pending]

## Summary

total: 3
passed: 0
issues: 1
pending: 2
skipped: 0
blocked: 0

## Gaps

- gap_id: G-10-1a
  truth: "An account that existed before this add-on was installed is asked for a second factor at its next login when the site-wide setting is on"
  status: failed
  reason: "User reported: For existing users, nothing is asked and they can log in without setting MFA"
  severity: blocker
  test: 1
  requirement: MFA-15
  root_cause: "The login plugin raises KeyError before it checks anything. authenticateCredentials calls is_whitelisted_client() first, which reaches get_app_settings(), which calls plone.registry forInterface() and raises because the site has no record for the max_failed_attempts settings field. Proven from /srv/src/server.dmsmail/var/log/instance1.log line 1207155, timestamp 260807 152305. The record is missing because max_failed_attempts was added to the settings interface on 2026-07-31 (commit bb528fe) while the GenericSetup profile version has never changed from 1000 and no upgrade step exists, so a site installed before that date never gains the record. This is a fail-open failure: the second factor is skipped rather than the login refused."
  debug_session: ".planning/debug/10-settings-record-missing-breaks-login-plugin.md"
  artifacts:
    - path: "src/imio/googleauthenticator/profiles/default/metadata.xml"
      issue: "Profile version is 1000 and has never been bumped, so no registry or member-data change reaches an already-installed site"
    - path: "src/imio/googleauthenticator/helpers.py"
      issue: "get_app_settings raises on an incomplete registry; the login plugin then fails open"
    - path: "src/imio/googleauthenticator/configure.zcml"
      issue: "Install step declares no dependency on memberdata-properties (separate confirmed defect, see 10-install-enrollment-not-applied.md)"
  missing:
    - "Bump the GenericSetup profile version in profiles/default/metadata.xml"
    - "Create an upgrades package with an upgrade step that re-imports the registry and memberdata-properties steps"
    - "Decide deliberately what the login plugin does when the settings registry is incomplete, so it cannot fail open"
    - "Add <depends name=\"memberdata-properties\"/> to the install step, plus a test asserting the dependency is declared"

- gap_id: G-10-1b
  truth: "A user enrolled by the site-wide setting rather than by their own action is shown the enrollment page (QR code and secret) before being asked for a code"
  status: not_reproduced
  reason: "User reported: For new users, the OTP is asked but they can reset it. A dedicated investigation could NOT reproduce this: it created an account and drove a real login through both redirect paths, and both times the user correctly reached the enrollment page with a valid signed link. On a site where the login plugin raises on every request (gap G-10-1a) nobody would be asked for a code at all, so this observation cannot have come from the same site state. Needs its own reproduction before any fix is attempted."
  severity: unknown
  test: 1
  requirement: MFA-19
  debug_session: ".planning/debug/10-enrollment-routing-lands-on-code-entry.md"
  artifacts: []
  missing:
    - "A reproduction on a site whose settings registry is complete, so the login plugin actually runs"
