---
status: deferred
phase: 10-global-enforcement-and-enrollment
source: [10-06-SUMMARY.md, 10-VALIDATION.md]
started: 2026-08-06T18:05:00Z
updated: 2026-08-06T18:05:00Z
deferred_by: operator
deferred_on: 2026-08-06
---

## Current Test

number: 1
name: Install onto a site that already has accounts
expected: |
  A user whose account existed before the add-on was installed is shown the enrollment page
  with a QR code at their next login, and can complete enrollment — not asked for a code from
  an application they never set up.
awaiting: operator, on a running instance

## Why these are deferred

Both checks need a running Plone 4.3 instance with `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` set and a
person at a browser. Neither is available in the environment this phase was built in. The operator
chose on 2026-08-06 to defer both and stop the autonomous run rather than validate now.

**Phase 10's automated evidence is complete and green** — 165 tests with 0 failures, 92% branch
coverage against a 90% floor, and `bin/code-analysis` exit 0, all independently re-run rather than
taken from the executing agents' reports. What is missing is only what a test cannot do.

## Tests

### 1. Install onto a site that already has accounts

requirements: MFA-15, MFA-19 (together)

expected: A pre-existing account is walked through enrollment at next login, not locked out.

why_human: This is the exact failure the phase exists to prevent, and it was originally found by
running a real two-egg environment on 2026-08-05, not by a test. Installing onto a populated site
used to leave every existing account with no second factor; a careless fix instead locks them all
out by asking for codes from an application they never set up. Only a real install exercises the
whole path in one piece.

steps:
  1. Start from a site that has several accounts and where this add-on is NOT yet installed.
     This differs from the Phase 9 check, which ran against a site with the add-on already there.
  2. `export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY=<a Fernet key>` then `bin/instance fg`.
  3. Install the add-on with "Globally enabled" on.
  4. Log in as one of the accounts that existed before the install.
  5. Confirm you are shown the enrollment page with a QR code and the copyable setup key,
     NOT a code-entry prompt.
  6. Complete enrollment and confirm the login finishes.

fails_if: you are asked for a code before ever seeing a QR code, or you cannot get in at all.

result: [deferred — not run]

### 2. No settings combination strands a user

requirements: MFA-18 (success criterion 5)

expected: All four combinations leave a reachable route to the enrollment page.

why_human: The automatable half is green — `test_every_settings_combination_leaves_enrollment_reachable`
covers it. The remaining half is a judgement across the matrix on a real site, confirming the route
is not just present in the action list but actually usable.

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

result: [deferred — not run]

## Summary

total: 2
passed: 0
issues: 0
pending: 0
skipped: 0
blocked: 0
deferred: 2

## Gaps

None found. Both items are unrun, not failed.

## Resume

`/gsd-verify-work 10`
