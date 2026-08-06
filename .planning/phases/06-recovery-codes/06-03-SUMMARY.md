---
phase: 06-recovery-codes
plan: 03
subsystem: auth
tags: [pbkdf2, totp, lockout, memberdata, plone-pas, python2, i18n]

# Dependency graph
requires:
  - phase: 06-recovery-codes (plans 01-02)
    provides: validate_recovery_code, validate_second_factor, generate_recovery_codes -- the substrate and dispatcher this plan asserts the lockout-sharing structure of and adds the low-count warning to
provides:
  - "RECOVERY_CODE_LOW_WATERMARK constant and a warning-level status message queued inside validate_recovery_code's accept branch only, naming the remaining code count once it reaches three or fewer"
  - "Three new test methods proving RECOV-05 (shared lockout counter), RECOV-07 (low-count warning, both adjacency sides), and the one-call-site-per-outcome invariant in token.py"
  - "The MFA-12 source guard (test_no_second_factor_state_written_from_the_plugin) extended to cover both new recovery-code memberdata properties and all three new helper functions, with positive controls restructured into per-file (name, source, label) triples"
affects: [07-documentation, 08-code-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Warning queued inside the accept branch, after the write and before return True -- unreachable from a failed or anonymous attempt by construction, not by a conditional a later edit could invert."
    - "zope.i18nmessageid MessageFactory called with mapping= (not str.format inside _()) for a count that needs no plural machinery: 'Recovery codes remaining: ${remaining}.' stays extractable by i18ndude and substitutes at render time via Products.CMFPlone's global_statusmessage.pt tal:content + i18n:translate dynamic-message-id mechanism."
    - "Positive controls as (name, source, label) triples pinned per-file, replacing two loops that assumed every property lives in helpers.py and every function in token.py -- a control asserted against the wrong file would pass vacuously and hide a broken search."

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/tests/test_token.py
    - src/imio/googleauthenticator/tests/test_pas_plugin.py

key-decisions:
  - "No new decisions this plan -- it asserts structure plans 06-01/06-02 already built (RECOV-05 is a right-hand-side-assignment fact, not new plumbing) and adds one self-contained warning inside an existing accept branch."

patterns-established:
  - "A future warning/notice tied to a security-control state follows the same shape: queue it strictly inside the branch that has already decided the security outcome, after the state write, guarded on getRequest() returning None so an absent collaborator degrades to silence rather than to a refusal."

requirements-completed: [RECOV-05, RECOV-07]

coverage:
  - id: D1
    description: "A failed recovery-code attempt increments two_factor_authentication_failed_attempts through the same register_failed_second_factor call a failed TOTP attempt uses; a mixed five-failure run (wrong recovery codes and wrong TOTP codes) locks the account; a successful recovery code resets both the counter and the lock through reset_failed_second_factor."
    requirement: "RECOV-05"
    verification:
      - kind: integration
        ref: "tests/test_token.py#TestTokenFormLockout.test_recovery_code_failure_shares_the_totp_lockout_counter"
        status: pass
    human_judgment: false
  - id: D2
    description: "A consumption leaving three or fewer codes queues one warning-level status message naming the remaining count; four or more queues none; a failed or anonymous submission never renders the warning."
    requirement: "RECOV-07"
    verification:
      - kind: integration
        ref: "tests/test_token.py#TestTokenFormLockout.test_low_recovery_code_count_warning"
        status: pass
    human_judgment: false
  - id: D3
    description: "browser/forms/token.py has exactly one validate_second_factor(, one register_failed_second_factor( and one reset_failed_second_factor( call; user_setup.py and reset_bar_code.py both still demand validate_token( and neither accepts the dispatcher -- the generalized-intent invariant from plan 06-01's assumption_delta_decision."
    verification:
      - kind: integration
        ref: "tests/test_token.py#TestTokenFormLockout.test_second_factor_dispatch_has_exactly_one_call_site_per_outcome"
        status: pass
    human_judgment: false
  - id: D4
    description: "The MFA-12 source guard (pas_plugin.py/subscribers.py must never mention second-factor state) extended to the two new recovery-code properties and all three new helper functions, with positive controls pinned per-file so none can pass vacuously."
    verification:
      - kind: integration
        ref: "tests/test_pas_plugin.py#TestPas.test_no_second_factor_state_written_from_the_plugin"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-04
status: complete
---

# Phase 6 Plan 3: Lockout Sharing and Low-Count Warning Summary

**Recovery-code failures and successes now assert (not merely happen) to route through Phase 5's exact lockout counter, a `<=3`-remaining warning fires only on the already-authenticated accept path, and the MFA-12 source guard now covers all five of this phase's new writers.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- `RECOVERY_CODE_LOW_WATERMARK = 3` added to `helpers.py`'s `RECOVERY_CODE_*` constant block; the comparison is `<=`, so three warns and four does not.
- `validate_recovery_code`'s accept branch queues one `'warning'`-level `IStatusMessage`, built with the module's `_` `MessageFactory` and a `mapping={'remaining': ...}` keyword (not `str.format` inside `_()`), naming the remaining count -- queued after the consume write and before `return True`, so it is unreachable from a failed or anonymous attempt by construction. A missing `getRequest()` degrades to silence, not a refusal.
- `test_recovery_code_failure_shares_the_totp_lockout_counter`: a wrong recovery code, three wrong TOTP codes, and one more wrong recovery code (five failures of two kinds) locks the account; a non-vacuity control proves four of them do not; a genuine code afterward resets both the counter and the lock through `reset_failed_second_factor`.
- `test_low_recovery_code_count_warning`: consuming codes down through five, four, three remaining proves the adjacency boundary (three warns, four does not); a failed submission at four remaining and an anonymous unsigned submission both render no warning text; the stored hash count (not the interpolated markup) is what the "three remaining" assertion hinges on.
- `test_second_factor_dispatch_has_exactly_one_call_site_per_outcome`: counted source assertions pin exactly one `validate_second_factor(`, one `register_failed_second_factor(` and one `reset_failed_second_factor(` call in `token.py`; `user_setup.py`/`reset_bar_code.py` still contain `validate_token(` (non-vacuity control) and neither contains the dispatcher call. Reproduced red by injecting a second `validate_second_factor(` call into `token.py`, confirmed the count assertion failed naming `1 != 2`, then restored `token.py` byte-identical (`git diff --stat` empty).
- `test_no_second_factor_state_written_from_the_plugin` (MFA-12) extended in place: absence tuples gained `two_factor_authentication_recovery_codes_salt`, `two_factor_authentication_recovery_codes_hashes`, `generate_recovery_codes`, `validate_recovery_code`, `validate_second_factor`; the two former "assume every property is in helpers.py / every function is in token.py" loops were replaced by one loop over `(name, source, label)` triples, each pinned to the file the name legitimately lives in.

## Task Commits

1. **Task 1: Warn on three or fewer remaining, on the success path only** -- `6f5c6c0` (feat)
2. **Task 2: Assert the shared counter, the warning, and the single dispatch point** -- `623fa04` (test)
3. **Task 3: Extend the MFA-12 guard to this phase's new writers, and make it fail first** -- `00091e7` (test)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `src/imio/googleauthenticator/helpers.py` - `RECOVERY_CODE_LOW_WATERMARK` constant; the warning queued inside `validate_recovery_code`'s accept branch
- `src/imio/googleauthenticator/tests/test_token.py` - `import imio.googleauthenticator` added at module level; three new methods on `TestTokenFormLockout`
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` - `test_no_second_factor_state_written_from_the_plugin` extended in place: one more `open()` read (`user_setup.py`), two absence tuples extended, positive controls restructured into `(name, source, label)` triples

## Decisions Made

None new. This plan asserts structure plans 06-01 (the single dispatch point, the untouched `reset_failed_second_factor`/`register_failed_second_factor` call sites) and 06-02 (enrollment/regeneration UI) already built, and adds one self-contained, already-scoped warning.

## Deviations from Plan

None -- plan executed exactly as written. Both mandatory non-vacuity demonstrations were performed and both mutations restored byte-identical, confirmed by an empty `git diff --stat`:

- **Task 2's source-count guard:** inserted a second `validate_second_factor(token, user=user)` call into `token.py`'s `handleSubmit`. `bin/test -t test_second_factor_dispatch_has_exactly_one_call_site_per_outcome` failed with `AssertionError: 1 != 2`, naming the exact assertion. Restored; `git diff --stat` on `token.py` empty.
- **Task 3's MFA-12 guard, module 1:** inserted a `# mutation-check: validate_second_factor` comment line into `pas_plugin.py`. `bin/test -t test_pas_plugin` failed, the assertion message quoting the full `pas_plugin.py` source and naming `'validate_second_factor' unexpectedly found in ...`. Restored; `git diff --stat` on `pas_plugin.py` empty.
- **Task 3's MFA-12 guard, module 2:** inserted a `# mutation-check: two_factor_authentication_recovery_codes_salt` comment line into `subscribers.py`. Same failure shape, naming that symbol in `subscribers.py`. Restored; `git diff --stat` on `subscribers.py` empty.
- **Task 3's restructured positive-control loop:** additionally verified the *wrong-file* failure mode the restructure exists to catch -- temporarily pointed `generate_recovery_codes`'s positive control at `token_source` instead of `user_setup_source`. The test failed with `'generate_recovery_codes' not found in <token.py source>`, confirming the loop checks the pairing, not merely "found somewhere." Restored the correct pairing; `bin/test -t test_pas_plugin` green afterward.

`--no-verify` used on all three task commits, per this plan's explicit `<action>` instruction and the project's documented pre-existing 318-finding `bin/code-analysis` debt (CLAUDE.md, scheduled for Phase 8/QUAL-06). No new finding was introduced by this plan's own edits beyond that pre-existing baseline.

## Issues Encountered

None.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- All five of `06-VALIDATION.md`'s verification steps pass: `bin/test -t test_helpers` (27 tests), `bin/test -t test_token` (11 tests), `bin/test -t test_pas_plugin` (12 tests), and `bin/test -t '!robot'` (98 tests total, up from 95 at the end of 06-02) all green.
- `git diff --stat` at plan close shows no change to `pas_plugin.py`, `subscribers.py`, `browser/forms/token.py`, `browser/forms/user_setup.py`, or `browser/forms/reset_bar_code.py` -- this plan asserted their structure, it did not change any of them.
- Phase 6's three plans (substrate, enrollment/regeneration UI, lockout-sharing-and-warning) are all complete. RECOV-01 through RECOV-07 are now all implemented and asserted; Phase 6's ROADMAP success criteria (recovery codes exist, are single-use, share the lockout counter, warn on low count) are met.
- Phase 7 (documentation) and Phase 8 (code quality, including the 318-finding `bin/code-analysis` baseline and the MFA-12-adjacent guard this plan extended) can proceed with no outstanding Phase 6 gaps.

---
*Phase: 06-recovery-codes*
*Completed: 2026-08-04*

## Self-Check: PASSED

All 3 modified source files exist on disk and contain the expected new symbols
(`RECOVERY_CODE_LOW_WATERMARK` in `helpers.py`; the three new test methods in
`test_token.py`; the extended tuples and restructured positive-control loop in
`test_pas_plugin.py`). All three task commits (`6f5c6c0`, `623fa04`, `00091e7`)
confirmed present in `git log --oneline`.
