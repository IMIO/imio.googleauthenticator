---
phase: 05-drift-replay-and-lockout
plan: 02
subsystem: auth
tags: [totp, onetimepass, rfc6238, replay, drift, memberdata]

# Dependency graph
requires:
  - phase: 05-01
    provides: two_factor_authentication_last_interval memberdata property (declared in userdataschema.py and memberdata_properties.xml, round-trip-proven, unread/unwritten until this plan)
provides:
  - "helpers.validate_token accepts one step of RFC 6238 backward clock drift and refuses a code whose interval has already been accepted (replay)"
  - "helpers._is_six_digit_token / helpers._find_accepted_interval as new pure helpers, TOTP_INTERVAL_SECONDS module constant"
  - "The replay rejection is logged at INFO with no operand at all"
affects: [05-03-reset-bar-code-lockout, 08-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Format gate (_is_six_digit_token) runs before the seed is fetched or decrypted, so garbage input never reaches onetimepass or the decrypt path"
    - "Drift tolerance is a pure function (_find_accepted_interval) with no ZODB access and no logging; validate_token alone owns the replay comparison, the log line and the write"
    - "Security-relevant rejections are logged with the event name only, no operand -- same discipline as validate_bar_code_reset_token's existing docstring convention"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/tests/test_helpers.py

key-decisions:
  - "P5-08/P5-09/P5-10/P5-11 followed exactly as planned (see 05-02-PLAN.md's Decisions table): _find_accepted_interval takes two args and stays pure; the last-accepted-interval write lives inside validate_token, not a caller; the format gate tests ASCII digit membership rather than isdigit(); the replay log line carries no operand at all."

patterns-established:
  - "Pattern: any future TOTP-adjacent helper that needs the current interval should call TOTP_INTERVAL_SECONDS rather than hardcoding 30, so RFC 6238's time step lives in exactly one place."

requirements-completed: [MFA-05, MFA-06, MFA-07]

coverage:
  - id: D1
    description: "A code generated for the interval exactly one step back (current - 1) is accepted, and the stored interval then reads back current - 1"
    requirement: "MFA-05"
    verification:
      - kind: unit
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_validate_token_accepts_previous_interval"
        status: pass
    human_judgment: false
  - id: D2
    description: "A code generated for the interval one step forward (current + 1) is refused -- the window widens backward only -- with a non-vacuity control proving the fixture is live"
    requirement: "MFA-05"
    verification:
      - kind: unit
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_validate_token_rejects_future_interval"
        status: pass
    human_judgment: false
  - id: D3
    description: "A code at the drift-window boundary produced by a real Google Authenticator app on a real phone is accepted, proving the server's interval arithmetic agrees with an independent clock"
    requirement: "MFA-05"
    verification: []
    human_judgment: true
    rationale: "Named explicitly in the plan's must_haves as a backstop-verification truth and in Task 2's <verify> as a <human-check>: no in-process test can establish this, because both sides of an in-process assertion read the same time.time(). Requires bin/instance fg running plus a real enrolled Google Authenticator app on a physical device, neither of which exists in this execution environment. Deferred to the phase's end-of-phase human verification pass (config.json human_verify_mode: end-of-phase)."
  - id: D4
    description: "A code already accepted is refused on a second submission; an interval exactly equal to the stored last-accepted interval is refused and the next interval up is accepted"
    requirement: "MFA-06"
    verification:
      - kind: unit
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_validate_token_rejects_replayed_interval"
        status: pass
    human_judgment: false
  - id: D5
    description: "The replay rejection is logged, and the log record's message and lazy-format arguments carry no username, no user id, no token and no secret"
    requirement: "MFA-06"
    verification:
      - kind: unit
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_replay_rejection_log_has_no_username"
        status: pass
    human_judgment: false
  - id: D6
    description: "Only exactly-six-ASCII-digit input is a candidate token; every other shape (wrong length, non-digit, leading whitespace/sign, a unicode digit that is not ASCII) is refused before onetimepass is called and without raising, and the format gate runs before the seed is fetched or decrypted"
    requirement: "MFA-07"
    verification:
      - kind: unit
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_validate_token_rejects_non_six_digit_input"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-31
status: complete
---

# Phase 5 Plan 2: Drift and Replay Summary

**`helpers.validate_token` rewritten so drift tolerance (accept current or current-1), replay rejection (refuse a re-used interval, logged with no operand) and an exact-six-ASCII-digit format gate ship together in one commit, with the pre-existing seed round-trip test fixed in the same commit.**

## Performance

- **Duration:** ~12 min (17:34 -> 17:46, commit timestamps)
- **Started:** 2026-07-31T17:34:43+02:00 (previous plan's completion commit)
- **Completed:** 2026-07-31T17:46:03+02:00
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `TOTP_INTERVAL_SECONDS = 30` module constant, documenting RFC 6238 section 5.2's default time step; the module already imported `time` at the top, so no new stdlib import was needed there.
- `helpers._is_six_digit_token(token)`: coerces non-strings with `str(...)`, then accepts only exactly six characters all drawn from the literal ASCII digit string `'0123456789'` -- rejects the length-1-to-6 numeric strings `onetimepass==0.2.2`'s own private `_is_possible_token` would otherwise accept, and rejects a unicode character that satisfies `isdigit()` but is not ASCII (a superscript two) without ever reaching `int()`.
- `helpers._find_accepted_interval(token, secret)`: pure function, no ZODB access, no logging. Tries `get_hotp(secret, intervals_no=interval)` for `interval` in `(current_interval, current_interval - 1)` only, in that order, never `current_interval + 1`.
- `helpers.validate_token(token, user=None)` rewritten: format gate first (before the secret is fetched), then the existing no-stored-seed guard (comment preserved verbatim), then `_find_accepted_interval`, then a replay comparison against `two_factor_authentication_last_interval` (refuse and log at INFO with no operand if the matched interval is `<=` the stored one), then a single `setMemberProperties()` write of the matched interval on success.
- `onetimepass` import changed from `valid_totp` to `get_hotp` -- confirmed by grep that `valid_totp` was used nowhere else in `src/imio/`.
- Same-commit regression fix: `test_seed_encryption_round_trip`'s SEC-01 end-to-end assertion now calls `get_totp(seed, as_string=True)` instead of the bare `get_totp(seed)`, with a comment explaining why the zero-padded form is required under the new gate.
- Four new tests on `TestDriftAndReplay` (created by plan 05-01): previous-interval accepted, future-interval refused with a same-seed non-vacuity control, replay refused with the adjacency pair (`current` refused, `current - 1` accepted) asserted explicitly, and the full non-six-digit input matrix from the plan's `<behavior>` block including the non-ASCII-digit edge.
- `test_replay_rejection_log_has_no_username`: attaches a throwaway `logging.Handler` to the process-global `imio.googleauthenticator` logger (level and handler both restored in a `finally` block), proving the accepted submission logs nothing (non-vacuity control) and the replayed submission logs exactly one INFO-or-higher record whose message and `record.args` contain neither the username, the user id, the token, nor the plaintext seed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Drift, replay and the exact-six-digit gate -- one commit** - `69ea86d` (feat)
2. **Task 2: Prove the replay rejection is logged without a username** - `43fdd53` (test)

_No TDD tasks in this plan; each task was a single commit._

## Files Modified

- `src/imio/googleauthenticator/helpers.py` - `TOTP_INTERVAL_SECONDS`, `_is_six_digit_token`, `_find_accepted_interval`, rewritten `validate_token`; `onetimepass` import switched from `valid_totp` to `get_hotp`
- `src/imio/googleauthenticator/tests/test_helpers.py` - SEC-01 regression fix (`as_string=True`); four new tests on `TestDriftAndReplay` (drift, future-rejection, replay/adjacency, format gate); `test_replay_rejection_log_has_no_username`; `import logging` and `from onetimepass import get_hotp` added

## Non-Vacuity Mutation Checks

All four required by the plan's acceptance criteria, each performed by hand (mutate, run the named test, confirm red, restore byte-identical via `diff`, re-run the full suite green):

1. **Narrowing the drift tuple to `(current_interval,)`** turned `test_validate_token_accepts_previous_interval` red (`AssertionError: False is not True`). Restored; full suite green (80 tests).
2. **Removing the replay comparison** (deleting the `if matched <= last_accepted_interval: ... return False` block) turned `test_validate_token_rejects_replayed_interval` red (`AssertionError: True is not False : replayed submission`). Restored; full suite green (80 tests).
3. **Relaxing the length check from `== 6` to `<= 6`** turned `test_validate_token_rejects_non_six_digit_input` red -- specifically an unhandled `ValueError: invalid literal for int() with base 10: ''` from `int(token)` inside `_find_accepted_interval`, since an empty token now passed the format gate. Restored; full suite green (80 tests).
4. **Adding the user id as a `logger.info` argument** (`logger.info('TOTP replay rejected for %s', user.getId())`) turned `test_replay_rejection_log_has_no_username` red (`AssertionError: 'test_user_1_' unexpectedly found in 'TOTP replay rejected for test_user_1_'`). Restored; full suite green (81 tests, run twice in a row to confirm no leaked log handler or level).

## Decisions Made

- P5-08, P5-09, P5-10 and P5-11 followed exactly as the plan specified (see `key-decisions` in frontmatter above). No deviations from the plan's decision table.

## Deviations from Plan

### Auto-fixed Issues

None - the plan's `<action>` and `<read_first>` excerpts matched the current source exactly (module already imported `time`, `valid_totp` confirmed unused elsewhere, `TestDriftAndReplay`'s `setUp`/`tearDown` present as described).

**Total deviations:** 0.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Manual Verification Deferred

Task 2's `<human-check>` item -- submitting a just-expired real Google Authenticator code against a running `bin/instance fg` to prove the server's interval arithmetic agrees with an independent physical clock (MFA-05 backstop truth) -- cannot be exercised in this execution environment (no running instance, no enrolled physical device). Recorded as coverage item D3 with `human_judgment: true`, deferred to the phase's end-of-phase human verification pass per `config.json`'s `human_verify_mode: end-of-phase`.

## Next Phase Readiness

- Plan 05-03 (reset-bar-code lockout) can build directly on the rewritten `validate_token`: it is called unchanged (same signature) from `reset_bar_code.py` and `user_setup.py`, both of which get the drift/replay/format-gate behaviour for free with no call-site change.
- `bin/test -t '!robot'` is green at 81 tests (up from the 80 recorded mid-plan, 76 at phase seed time), run twice in a row with identical results.
- No blockers.

---
*Phase: 05-drift-replay-and-lockout*
*Completed: 2026-07-31*

## Self-Check: PASSED

Both modified files confirmed present on disk; both task commit hashes
(`69ea86d`, `43fdd53`) confirmed in `git log`.
