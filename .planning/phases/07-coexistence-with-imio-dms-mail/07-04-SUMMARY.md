---
status: complete
plan: 07-04
phase: 07-coexistence-with-imio-dms-mail
date: 2026-08-05
requirements: [COEX-07, COEX-09]
---

# Plan 07-04 Summary — Manual-only verifications recorded

## What this plan produced

`07-UAT.md` — the record of the two verifications `bin/test` genuinely cannot perform,
carrying the operator's actual results rather than letting the automated halves stand in
for them.

No code changes. This plan's `files_modified` was empty by design.

## Results

| Test | Requirement | Result |
|------|-------------|--------|
| Real two-egg install in both orders alongside `imio.dms.mail` | COEX-07 | passed |
| Real browser overlay check on the login path | COEX-09 | passed |

Both were performed by the operator on the `server.dmsmail` MOD-1076 buildout, with a
**fresh Plone site created for each install order**, so no artifacts from before this
phase were present.

- **Order A** (`imio.dms.mail` first, then this package): exactly one overlay-script
  registration, `imio.dms.mail` overlay widgets open, 2FA login completes.
- **Order B** (this package first, then `imio.dms.mail`): same three results.
- **Browser check**: the 2FA form renders in the same stock overlay as the login form,
  warning status messages work, and the browser JS console is empty.

## Two things found that were not part of this plan

### 1. A blocker that had to be cleared before the test could run

Creating a site from the `imio.dms.mail:examples` profile aborted with `KeyError` on the
absent `ska_secret_key` record. Cause: `userdataschema.userCreatedHandler` is registered
instance-wide in `configure.zcml` (lines 60-64) with no site or layer constraint, so it
fired while `imio.dms.mail`'s profile created its users in a site that had not installed
this package's profile, and reading the settings raised.

Fixed outside this plan, in quick task `260805-f5m` (commit `184f053`), tracked as
requirement COEX-10, with a regression test proven non-vacuous. The operator applied the
same guard inside the `server.dmsmail` buildout first, to unblock this verification; the
repository fix landed afterwards.

### 2. An open gap, recorded rather than passed over

In Order A, two-factor authentication was **not** forced on an existing Plone Member
account despite the "Globally enabled" setting being on. In Order B it was.

COEX-07's stated criteria are met in both orders, so test 1 is recorded as passed. The
enrolment difference is carried as a named gap in `07-UAT.md` with its own new
requirement, **MFA-14**, currently unassigned to a phase. The operator decided this does
not block Phase 7.

Mechanism, confirmed by reading the code: the global setting is consulted only by the
user-creation subscriber and by `browser/settings_helper.py`; the login gate
(`helpers.py:1021`, `helpers.py:1044`) checks only the per-user memberdata flag; and
existing users are enrolled only on a control-panel form save
(`browser/controlpanel.py:125-132`), never by `setuphandlers.setupVarious`. Installing
into a running `imio.dms.mail` site — the real deployment direction — therefore leaves
existing accounts without a second factor.

## Test suite state

111 tests, 0 failures, 0 errors, exit code 0. Verified directly by the orchestrator, not
taken from an agent's claim. The count rose from 110 because quick task `260805-f5m`
added one regression test.

## Deviation from the plan's execution model

The plan was executed with the operator answering both checkpoints directly, and the
resulting artifacts were written inline rather than by a continuation executor agent. The
operator was in manual command-approval mode, where subagent dispatch produces a long
stream of prompts to approve without visible reasoning. Inline execution is the same
pattern GSD's `--interactive` execution mode uses.

## Self-Check: PASSED
