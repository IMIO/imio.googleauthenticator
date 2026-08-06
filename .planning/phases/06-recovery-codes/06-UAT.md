---
status: complete
phase: 06-recovery-codes
source: [06-VERIFICATION.md]
started: 2026-08-04T08:05:22Z
updated: 2026-08-04T08:12:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Lockout wiring on the enrollment / regeneration form

expected: A recorded decision — fix or explicitly accept.
result: pass
decision: accepted as deferred risk
decided_by: Chris
decided_at: 2026-08-04

**Decision.** The operator reviewed the facts below and accepted the current state as
deferred risk. No lockout wiring will be added to `browser/forms/user_setup.py` in
Phase 6. Phase 6 closes with this state recorded.

**Rationale carried forward.** The exposure is bounded by the fact that the same form
already renders the account's own TOTP secret (as a QR code) to any authenticated,
site-local user who loads it, so repeated code guessing gains an attacker nothing they
could not read directly off the page. Closing the gap remains worthwhile for consistency
between the three second-factor checks and is a candidate for a later phase.

**What the code does today.** `browser/forms/user_setup.py:94` validates the submitted
TOTP code with a bare `validate_token(token)` call. It does not call `is_account_locked`
before the check, does not call `register_failed_second_factor` when the check fails, and
does not call `reset_failed_second_factor` when it succeeds. The two other places in this
package that check a second factor both do all three: `browser/forms/token.py` (the login
gate, lines 108/113/120/140) and `browser/forms/reset_bar_code.py` (the seed-reset gate,
lines 123/132/145/170).

**Why it matters for this phase.** `profiles/default/actions.xml` adds a
`regenerate_recovery_codes` portal action pointing at `@@setup-two-factor-authentication`,
and its own inline comment names that form's TOTP check as the gate protecting
regeneration. So the one unthrottled second-factor check in the package is now the check
standing in front of minting a fresh, durable set of ten recovery codes.

**Correction to how the code review and verifier described the risk.** Both reports frame
this as an unlimited six-digit brute-force window. That framing is overstated. The same
form's `updateFields` (user_setup.py:169) renders the account's own QR code — which encodes
the TOTP secret — to any authenticated, site-local user who loads the page. Anyone in a
position to guess the code repeatedly can instead read the secret directly off the rendered
form. The gap is a real inconsistency between the three second-factor gates and is worth
closing for defense in depth and for consistency, but it is not the brute-force hole the
two reports describe.

**Scope note.** This predates Phase 6 — phase 05-03 added the lockout wiring to
`reset_bar_code.py` and did not extend it to `user_setup.py`. No ROADMAP success criterion
and no plan `must_haves.truth` for Phase 6 requires this endpoint to be rate-limited, so
nothing in the phase mechanically fails because of it.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
