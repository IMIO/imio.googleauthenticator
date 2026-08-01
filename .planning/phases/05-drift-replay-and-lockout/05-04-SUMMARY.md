---
phase: 05-drift-replay-and-lockout
plan: 04
subsystem: auth
tags: [totp, lockout, oracle, plone-pas, ska]

# Dependency graph
requires:
  - phase: 05-drift-replay-and-lockout
    provides: "05-01's is_account_locked/register_failed_second_factor/reset_failed_second_factor helpers and the lock gate first wired into token.py::handleSubmit"
provides:
  - "token.py::TokenForm.handleSubmit reordered so is_account_locked is checked only after validate_user_data succeeds, closing the CR-01 unauthenticated account-state oracle"
  - "test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account: three-way equality proof (locked / unlocked-enrolled / nonexistent) for an unsigned anonymous caller"
  - "05-VALIDATION.md MFA-08 not-an-oracle row filled in"
affects: [phase-06, phase-08-qual]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Guard-clause ordering as the security boundary: a lock/state-disclosure gate must sit strictly after the signature/authentication check that proves the caller earned the right to see it, and strictly before the operation (validate_token) the lock exists to protect"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/forms/token.py
    - src/imio/googleauthenticator/tests/test_token.py
    - .planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md

key-decisions:
  - "Moved the is_account_locked gate to sit between the validate_user_data success check and the validate_token call -- the middle position is the only one that satisfies both halves of MFA-08 simultaneously (checked before the token, and not an oracle to an unsigned caller)."
  - "Non-vacuity for the new test proven by mutation: reverting the reorder locally (checking out HEAD~1's token.py) turned the new test red while the other 6 test_token.py methods stayed green; token.py restored byte-identical afterwards (confirmed via empty git diff/git status)."

patterns-established:
  - "Status-message extraction for cross-account response-equality assertions: regex against the rendered <dl class=\"portalMessage error\"><dt>...</dt><dd>{text}</dd></dl> markup (Products.statusmessages via plone.app.layout 3.5.2's globalstatusmessage.pt), rather than whole-page byte comparison, which would be defeated by the CSRF token and portal date that differ per request for reasons unrelated to the property under test."

requirements-completed: [MFA-08]

coverage:
  - id: D1
    description: "The is_account_locked lock gate in token.py::TokenForm.handleSubmit now runs after validate_user_data succeeds and before validate_token, so an unsigned/unauthenticated caller supplying only a username cannot learn lock state"
    requirement: "MFA-08"
    verification:
      - kind: integration
        ref: "src/imio/googleauthenticator/tests/test_token.py#test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account"
        status: pass
      - kind: integration
        ref: "src/imio/googleauthenticator/tests/test_token.py#test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code (unmodified regression)"
        status: pass
    human_judgment: false
  - id: D2
    description: "On a live instance, an unauthenticated request with no signature/auth_timestamp against a locked, unlocked, and nonexistent account all return the identical message -- the in-process test asserts this through zope.testbrowser, which cannot rule out a difference introduced by the real ZPublisher error/status path or a front-end proxy (05-VERIFICATION.md Human Verification item 3)"
    verification: []
    human_judgment: true
    rationale: "No running instance or front-end proxy exists in this execution environment; this is 05-VERIFICATION.md's own designated backstop item, explicitly deferred to end-of-phase human verification per the phase's Manual-Only Verifications table."

duration: 20min
completed: 2026-08-01
status: complete
---

# Phase 5 Plan 04: Close the CR-01 lockout-oracle gap Summary

**Reordered the `is_account_locked` gate in `token.py::TokenForm.handleSubmit` to run after the `ska` signature check succeeds instead of before it, closing the last open MFA-08 gap (CR-01): an unauthenticated caller supplying only a username can no longer distinguish a locked account from an unlocked or nonexistent one.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-01T12:52Z (approx, per STATE.md's init timestamp)
- **Completed:** 2026-08-01T13:01Z
- **Tasks:** 2
- **Files modified:** 3 (`token.py`, `test_token.py`, `05-VALIDATION.md`)

## Accomplishments

- `token.py::TokenForm.handleSubmit`: the `is_account_locked` gate moved from *before* `validate_user_data` to *between* `validate_user_data`'s success check and `validate_token` — the only position that satisfies both halves of MFA-08 at once (locked accounts never reach TOTP arithmetic; unsigned callers learn nothing about lock state).
- New test `test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account` in `TestTokenFormLockout`: proves three-way message equality (locked / unlocked-enrolled / nonexistent) for a fully anonymous caller with no `signature`, no `auth_timestamp`, and no password.
- `05-VALIDATION.md`'s MFA-08 not-an-oracle row filled in, naming the new test and Plan `05-04`/Wave `3`.
- Full suite green at 83 tests (up from 82), twice in a row.

## Task Commits

Each task was committed atomically:

1. **Task 1: Reorder the lock gate behind the signature check** - `ff28800` (fix)
2. **Task 2: Prove the unsigned response is identical for a locked and an unknown account** - `eee1d29` (test)

**Plan metadata:** (this commit, appended after SUMMARY.md creation)

## Files Created/Modified

- `src/imio/googleauthenticator/browser/forms/token.py` - `is_account_locked` gate moved between the `validate_user_data` success branch and `validate_token`; comment rewritten to name both identifiers and cite MFA-08
- `src/imio/googleauthenticator/tests/test_token.py` - added `import re` and one new test method (6th `def test_` in the file); no existing method body touched
- `.planning/phases/05-drift-replay-and-lockout/05-VALIDATION.md` - MFA-08 not-an-oracle row added, naming the new test

## Decisions Made

- **Gate position:** the middle position (after signature success, before token check) is the only one that satisfies both MFA-08 clauses simultaneously. Reversible per the plan's own rating: a `git revert` restores the previous (broken) ordering exactly, and the new test is what would go red if that ever happened.
- **Third fixture account for non-vacuity:** rather than relying on two-way equality (locked vs. nonexistent, which could coincidentally match), the test also creates a real enrolled-but-unlocked account (`api.user.create`) and asserts three-way equality across all three states. This is what "not an oracle" actually means per the plan's Task 2 step 7.
- **Message extraction approach:** rather than comparing whole rendered pages (which differ by CSRF token and portal date), the test extracts just the `<dd>` text inside `<dl class="portalMessage error">` via a small regex, matching the markup the installed `plone.app.layout` 3.5.2 (py2.7) egg's `globalstatusmessage.pt` actually renders in this environment (verified by dumping `browser.contents` during development, since `tal:replace` on the `<span class="content">` element in some Plone versions replaces the tag itself rather than just its content — the actual markup here uses `<dl>`/`<dt>`/`<dd>`, not `<span>`).

## Deviations from Plan

None - plan executed exactly as written. The one implementation detail not fully specified by the plan (exact HTML markup to extract the status message from) was resolved empirically by inspecting real rendered output, per the plan's own instruction to "extract the message the way the sibling tests in this file already do" combined with "prefer... over hardcoding a string" — no rule violation, no scope change.

## Non-Vacuity Mutation Check (recorded per plan's acceptance criteria)

1. Copied the good (Task-1-reordered) `token.py` aside.
2. Checked out `HEAD~1`'s `token.py` (the pre-reorder version) over the working file.
3. Ran `bin/test -t test_token`: **7 tests, 1 failure** — `test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account` failed with `AssertionError: 'Invalid token or token expired.' != 'Invalid data. Details: Invalid signature!'`; all 6 other `TestTokenFormLockout` methods (including the untouched `test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code`) passed.
4. Restored the good `token.py` from the saved copy; `git diff --stat` and `git status --short` on the file were both empty, confirming byte-identical restoration.
5. Re-ran `bin/test -t '!robot'`: 83 tests, 0 failures, twice in a row.

## Issues Encountered

- The plan's suggested `<span class="content">` extraction target (mirrored from a different `plone.app.layout` release's `globalstatusmessage.pt`, where `tal:replace` swaps the whole span tag for the message text) does not match what this buildout's pinned `plone.app.layout` 3.5.2 (py2.7) egg actually renders. Resolved by dumping real `browser.contents` to a scratch file during development and adjusting the regex to the actual `<dl class="portalMessage error"><dt>...</dt><dd>{text}</dd></dl>` markup. No production code involved; test-only.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- MFA-08 moves from PARTIALLY SATISFIED to SATISFIED on re-verification, with only the live-instance backstop (05-VERIFICATION.md Human Verification item 3 — the ZPublisher/proxy-level check that no in-process test can rule out) still outstanding.
- Phase 5 has no further open gaps from `05-REVIEW.md`'s CR-01; the remaining WR-01/WR-02/IN-01 items are recorded as deferred, non-blocking follow-ups (see `05-01-PLAN.md`'s Deferred table) and were not in this plan's scope.
- No blockers for Phase 6 or the Phase 8 code-quality pass.

---
*Phase: 05-drift-replay-and-lockout*
*Completed: 2026-08-01*

## Self-Check: PASSED

All claimed files and commit hashes verified present on disk / in git history.
