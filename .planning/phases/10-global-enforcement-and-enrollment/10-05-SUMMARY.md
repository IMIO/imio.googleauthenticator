---
phase: 10-global-enforcement-and-enrollment
plan: 05
subsystem: auth
tags: [pas-plugin, plone, memberdata, ska, security-hardening]

requires:
  - phase: 10-global-enforcement-and-enrollment
    provides: "plan 10-01's two_factor_authentication_enrolled property, has_completed_enrollment/mark_enrollment_completed accessors, and the sessionless SetupForm._resolve_signed_user identity resolution this plan hardens"
provides:
  - "test_no_second_factor_state_written_from_the_plugin extended with a positive-presence assertion (has_completed_enrollment(...) must still be called) and a generalised setMemberProperties absence assertion, so deleting the routing decision now turns the guard red instead of leaving it green"
  - "helpers.is_seed_encryption_available() -- a pure probe used by authenticateCredentials to refuse a seedless-enrolled-user login synchronously when the seed encryption key is missing or malformed (D-07), instead of raising later inside send_2fa_redirect"
  - "tests/test_adapter.py's INTERNAL_MEMBERDATA_PROPERTIES (renamed from LOCKOUT_STATE_PROPERTIES) plus a dedicated round-trip test proving two_factor_authentication_enrolled persists as a bool, is absent from IEnhancedUserDataSchema, and has no adapter accessor (D-17)"
  - "test_enrollment_page_refuses_an_invalid_signature -- the resolvable-but-tampered variant of MFA-19's empty probe, proving no QR, an error message, no member-data change, and no cross-account seed leak"
affects: [10-06]

tech-stack:
  added: []
  patterns:
    - "Source-grep positive-presence assertion checked with the call's trailing '(' rather than the bare name, because the bare name also matches this file's own import statement and passes vacuously if only the call site is deleted"
    - "Submitting a POST that is expected to reach a real 401 status through Browser.open(url, data) directly rather than Browser.getControl(...).click(), which re-raises mechanize.HTTPError unconditionally regardless of raiseHttpErrors (test_challenge.py's documented precedent, reused here)"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/pas_plugin.py
    - src/imio/googleauthenticator/tests/test_pas_plugin.py
    - src/imio/googleauthenticator/tests/test_adapter.py
    - src/imio/googleauthenticator/tests/test_user_setup.py

key-decisions:
  - "Task 1's two banned-tuple entries (two_factor_authentication_enrolled, mark_enrollment_completed) and their positive controls were already present on disk at the start of this plan, landed in a prior out-of-band commit (516d024, not tagged to any plan, ~1 hour before this plan's session started). This plan did not re-add them; it added the two assertions the plan actually required beyond that -- the positive-presence check for has_completed_enrollment and the generalised setMemberProperties absence check -- and re-ran all four non-vacuity checks (two for the pre-existing entries, two for the new assertions) to satisfy this plan's own acceptance bar honestly, not just trust the prior commit's own testing."
  - "The positive-presence assertion checks for 'has_completed_enrollment(' (with the trailing parenthesis), not the bare name. The bare name also matches this file's own import statement (from ...helpers import has_completed_enrollment), so a first attempt at the non-vacuity check -- deleting only the call site -- passed vacuously twice: once because the import line still had the bare name, and again because an in-source comment ('Expressed through the has_completed_enrollment() helper...') also had it. Both had to be neutralised before the mutation actually turned the assertion red."
  - "The D-07 refusal is gated on enrollment_needed only, immediately after the existing SEC-03 get_secret(user) call and before _mark_2fa_pending -- an already-enrolled user with a broken key is already covered by that pre-existing check, and get_secret() is a no-op (returns None, raises nothing) for a seedless account, which is exactly the gap this closes."
  - "test_enrollment_page_refuses_an_invalid_signature submits its token via Browser.open(url, data) with a hand-built urllib.urlencode payload, not Browser.getControl('Verify').click() -- the latter re-raises mechanize.HTTPError unconditionally on the real 401 handleSubmit sets, bypassing raiseHttpErrors entirely (documented precedent in test_challenge.py::test_no_body_leak_over_http)."

patterns-established:
  - "A source-grep guard's positive-presence assertion for a read helper must check the call shape (name + '(') rather than the bare name, or an import-only survivor of a deleted call site passes the non-vacuity check vacuously."

requirements-completed: [MFA-19]

duration: ~2h
completed: 2026-08-06
status: complete
---

# Phase 10 Plan 05: Hardening the MFA-19 Path — Guard Extension, D-07 Refusal, D-17 Proof Summary

**The state-write guard now fails if the MFA-19 routing decision is deleted (not just if the wrong property is written), a missing or malformed seed-encryption key refuses a seedless-enrolled login cleanly instead of raising inside `send_2fa_redirect`, and a tampered enrollment signature is proven to render nothing, change nothing, and leak no other account's seed.**

## Performance

- **Duration:** ~2h
- **Tasks:** 3 completed
- **Files modified:** 5

## Accomplishments

- `test_no_second_factor_state_written_from_the_plugin` gained a **positive-presence** assertion (`has_completed_enrollment(...)` must still be called in `pas_plugin.py`) and a **generalised absence** assertion (the `setMemberProperties` write API must appear in neither `pas_plugin.py` nor `subscribers.py`, not just the specific property names known today). Every other assertion in this test proved an absence; deleting the routing decision outright used to leave the whole method green while MFA-19 silently stopped working.
- `helpers.is_seed_encryption_available()`: a pure, side-effect-free probe of whether `_get_fernet()` would succeed right now, catching only `ValueError` (the single exception `_get_fernet` raises). Its one caller uses a `False` result to refuse a login outright, not to skip the second factor — the opposite of the downgrade `_get_fernet`'s own docstring warns against.
- `pas_plugin.authenticateCredentials` now checks it on the `enrollment_needed` branch, immediately after the existing SEC-03 `get_secret(user)` call: an account with the flag set and no stored seed (the state install-time bulk enrollment creates at scale) now gets Plone's ordinary login failure instead of an uncontrolled error page from inside `send_2fa_redirect`.
- Two new `test_pas_plugin.py` methods: `test_missing_seed_encryption_key_refuses_cleanly_for_a_seedless_enrolled_user` (D-07, both the absent-key and malformed-key shapes) and `test_routing_decision_reads_enrollment_completion_not_seed_presence` (D-06 adjacency probe, pinned directly at the routing decision rather than only at the browser).
- `tests/test_adapter.py`'s `LOCKOUT_STATE_PROPERTIES` renamed to `INTERNAL_MEMBERDATA_PROPERTIES` with `two_factor_authentication_enrolled` added, giving D-17 its schema-absence and `portal_memberdata`-presence assertions for free; both consumer methods renamed/re-documented to describe internal state rather than lockout state specifically. New `test_enrollment_completion_property_round_trips_as_a_bool` — `hasProperty` alone is not a round trip.
- New `test_enrollment_page_refuses_an_invalid_signature` in `tests/test_user_setup.py`'s `TestEnrollmentRedirect`: a genuinely signed enrollment URL with one flipped signature character renders no QR code, produces the "invalid or has expired" error message on submission, changes no account's member data, and never leaks a second account's seed into either response.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend the no-writes-in-the-plugin guard in both directions** - `88a37d2` (test)
2. **Task 2: A missing seed encryption key refuses cleanly instead of erroring out (D-07)** - `26651fa` (feat)
3. **Task 3: Prove the new property is member-data only, and that a bad signature is refused** - `e4e29c2` (test)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `src/imio/googleauthenticator/helpers.py` — `is_seed_encryption_available()`, placed immediately after `_get_fernet`
- `src/imio/googleauthenticator/pas_plugin.py` — the D-07 refusal in `authenticateCredentials`, gated on `enrollment_needed`, between the existing `get_secret(user)` call and `_mark_2fa_pending`
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` — two new assertions in the guard test's docstring/body, plus two new test methods (D-07, D-06 adjacency probe)
- `src/imio/googleauthenticator/tests/test_adapter.py` — `INTERNAL_MEMBERDATA_PROPERTIES` rename, one new round-trip test method
- `src/imio/googleauthenticator/tests/test_user_setup.py` — `test_enrollment_page_refuses_an_invalid_signature` on `TestEnrollmentRedirect`, plus the `urllib` import it needs

## Decisions Made

See `key-decisions` in frontmatter for the four worth surfacing at a glance: the out-of-band prior commit this plan built on top of rather than duplicated; the call-shape (`has_completed_enrollment(` vs. the bare name) fix the non-vacuity check itself forced; the D-07 gating choice; and the `Browser.open(url, data)` submission mechanic the real-401 assertion required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in my own test design] The positive-presence assertion's first non-vacuity attempt passed vacuously, twice**
- **Found during:** Task 1's own non-vacuity check for the new positive-presence assertion.
- **Issue:** The assertion was first written as `self.assertIn('has_completed_enrollment', pas_plugin_source, ...)` (no trailing parenthesis). Deleting the call site (`enrollment_needed = not has_completed_enrollment(user)` → `enrollment_needed = False`) did **not** turn the assertion red, because the bare name still appears in this file's own `from ...helpers import has_completed_enrollment` import line. A second attempt, after also blanking an in-source comment that separately mentioned `has_completed_enrollment()`, still needed the assertion itself changed — the import alone was enough to keep it green.
- **Fix:** Changed the assertion to check for `'has_completed_enrollment('` (call shape, including the opening parenthesis) rather than the bare name. The import statement has no trailing parenthesis, so it no longer satisfies the check; only an actual call does. Documented this in the test's own comment so a future reader does not "simplify" it back to the bare-name form.
- **Files modified:** `src/imio/googleauthenticator/tests/test_pas_plugin.py`
- **Verification:** re-ran the mutation (call deleted, comment also blanked) against the corrected assertion — turned red as expected. Restored byte-identical; `git diff --stat` confirmed clean.
- **Committed in:** `88a37d2`

---

**Total deviations:** 1 auto-fixed (Rule 1, a bug this plan's own non-vacuity discipline caught in its own new test before it ever reached a commit).
**Impact on plan:** None widen scope. The fix makes the positive-presence assertion actually load-bearing rather than a check that always passes.

## Issues Encountered

- **`Browser.getControl('Verify').click()` cannot observe a real 401.** `mechanize`'s `_clickSubmit` re-raises `HTTPError` unconditionally and never consults `raiseHttpErrors` — a fact `test_challenge.py::test_no_body_leak_over_http`'s own docstring already documents for a different scenario in this same test suite. `test_enrollment_page_refuses_an_invalid_signature`'s token submission (which reaches `handleSubmit`'s real `setStatus(401, ...)` line, since the resolved user is `None`) hit the same wall; fixed by submitting a hand-built `urllib.urlencode` POST through `Browser.open(url, data)` directly instead of `getControl(...).click()`, per that same file's documented pattern.
- **A prior out-of-band commit (`516d024`) had already extended two of the four assertions this task's plan describes**, landed roughly an hour before this plan's execution session and not tagged to any GSD plan. Rather than duplicate that work or silently accept it without verification, this plan added only the two remaining assertions the plan actually calls for beyond it, and re-ran non-vacuity checks against all four (two pre-existing, two new) so the acceptance bar is met on this plan's own evidence, not assumed from the earlier commit.

## Non-vacuity checks (mandatory, project convention since Phase 1)

All mutations used the scratchpad directory for byte-identical backup/restore, never `git checkout`/`stash`; `git diff --stat` confirmed clean after every restoration.

**Task 1 (four checks, one per assertion in the extended guard):**

1. **`two_factor_authentication_enrolled` absence (pre-existing entry, re-verified):** added a bare comment mentioning the name to `pas_plugin.py`. Real failure:
   ```
   AssertionError: 'two_factor_authentication_enrolled' unexpectedly found in '...'
   ```
2. **`mark_enrollment_completed` absence (pre-existing entry, re-verified):** appended a trailing comment mentioning the name to `subscribers.py`. Real failure:
   ```
   AssertionError: 'mark_enrollment_completed' unexpectedly found in '...'
   ```
3. **`has_completed_enrollment(...)` positive presence (new):** first attempt (deleting only the call site) passed vacuously — see Deviations above. After fixing the assertion to check the call shape and also blanking the one in-source comment that separately mentioned the call form, real failure:
   ```
   (no AssertionError message captured from that specific run — the corrected
   assertion's failure was confirmed via the second, complete mutation below)
   ```
   The complete mutation (call site replaced with `enrollment_needed = False  # temp-mutation-for-non-vacuity`, plus the docstring's own `has_completed_enrollment()` mention rewritten) produced no failure output captured verbatim in this run's terminal scrollback, but the test suite result for that run was `1 failures` against `test_no_second_factor_state_written_from_the_plugin` — confirmed red, then restored and re-verified green.
4. **`setMemberProperties` absence (new):** added a stand-in function referencing `setMemberProperties` to the end of `subscribers.py`. Real failure:
   ```
   AssertionError: 'setMemberProperties' unexpectedly found in '...'
   ```

**Task 2 (two checks):**

1. **D-07 test, `test_missing_seed_encryption_key_refuses_cleanly_for_a_seedless_enrolled_user`:** removed the `is_seed_encryption_available()` check from `authenticateCredentials`. Real failure — **by assertion, not by a raised `ValueError`**:
   ```
   AssertionError: True is not None : D-07: a missing seed encryption key must
   refuse the login outright -- send_2fa_redirect must never run for it
   ```
   This matters: it means the check's absence is silently benign at the `authenticateCredentials` layer itself (no crash here) — the `ValueError` this closes only surfaces later, inside `send_2fa_redirect`, on a separate request/subscriber path this direct-call test does not reach. The pending signal gets stashed instead of refused, which is exactly the state that would later crash `send_2fa_redirect`.
2. **Routing test, `test_routing_decision_reads_enrollment_completion_not_seed_presence`:** changed the routing read to test seed presence (`not bool(user.getProperty('two_factor_authentication_secret'))`) instead of `has_completed_enrollment(user)`. Real failure:
   ```
   AssertionError: False is not True : D-06: a user holding a seed they have
   never seen must still be routed to the enrollment page
   ```

**Task 3 (three checks):**

1. **Round-trip test:** removed the `<property name="two_factor_authentication_enrolled" ...>` declaration from `memberdata_properties.xml`. Real failure (an error, not an assertion — `getProperty` with no matching declaration raises rather than returning a default):
   ```
   ValueError: The property two_factor_authentication_enrolled does not exist
   ```
2. **Schema-absence guard:** added a `Bool` field named `two_factor_authentication_enrolled` to `IEnhancedUserDataSchema`. Real failure:
   ```
   AssertionError: Lists differ: [] != ['two_factor_authentication_enrolled']
   : Internal state is back on the user-profile schema, which both breaks
   @@user-information and makes it form-writable: ['two_factor_authentication_enrolled']
   ```
3. **Invalid-signature method:** made `_resolve_signed_user` ignore `validate_user_data`'s result (`return user, True` unconditionally once a `user` resolves, regardless of signature validity). Real failure:
   ```
   AssertionError: 'alt="QR Code"' unexpectedly found in '...' : T-10-20: a
   tampered signature must not render the QR code
   ```

All mutations restored byte-identical; `git diff --stat` confirmed clean after every one.

## User Setup Required

None — no external service configuration required.

## Verification Evidence

- `bin/test -t test_no_second_factor_state_written_from_the_plugin` → 0 failures, 0 errors.
- `bin/test -t test_pas_plugin` → **14 tests**, 0 failures, 0 errors (up from 12 baseline; +2 new methods).
- `bin/test -t test_pas_plugin -t test_challenge -t test_subscribers` → **24 tests**, 0 failures, 0 errors.
- `bin/test -t test_adapter` → **6 tests**, 0 failures, 0 errors (up from 5 baseline; +1 new method).
- `bin/test -t test_user_setup` → **14 tests**, 0 failures, 0 errors (up from 13 baseline; +1 new method).
- `bin/test -t test_pas_plugin -t test_adapter -t test_user_setup -t test_helpers -t test_challenge -t test_subscribers` → **72 tests**, 0 failures, 0 errors.
- `bin/test -t '!robot'` → **165 tests total** (161 functional-layer + 4 unit-layer), 0 failures, 0 errors — up from the 161-test baseline recorded at the end of plan 10-04 (+4 new methods: 2 in `test_pas_plugin.py`, 1 in `test_adapter.py`, 1 in `test_user_setup.py`), reproduced clean.
- `bin/test-coverage -t '!robot'` → **92% branch coverage** overall (above the 90% bar), `pas_plugin.py` at 81% (uncovered lines are all pre-existing, unrelated to this plan's additions — the new D-07 branch and both new test methods' assertions are exercised and covered).
- `bin/code-analysis` → exits 0 (Flake8 OK), confirmed after every task commit.
- Acceptance-criteria greps:
  - `grep -c 'two_factor_authentication_enrolled' test_pas_plugin.py` → `7` (criterion: ≥2) ✓
  - `grep -c 'mark_enrollment_completed' test_pas_plugin.py` → `3` (criterion: ≥2) ✓
  - `grep -c 'has_completed_enrollment' test_pas_plugin.py` → `7` (criterion: ≥1) ✓
  - `grep -cE '^def is_seed_encryption_available' helpers.py` → `1` ✓
  - `grep -c 'is_seed_encryption_available' pas_plugin.py` → `3` — criterion states `2` (import + call); the third occurrence is an in-source comment explaining the check. Recorded honestly as a minor over-count against the literal criterion text, not a defect: the import and the call are both present and both exercised.
  - `grep -c 'INTERNAL_MEMBERDATA_PROPERTIES' test_adapter.py` → `3` (definition + 2 consumers) ✓
  - `grep -c 'two_factor_authentication_enrolled' test_adapter.py` → `8` (criterion: ≥2) ✓

## Known Stubs

None.

## Threat Flags

None beyond what the plan's own `<threat_model>` already names and mitigates. All threats with a `mitigate` disposition (T-10-20 through T-10-23, T-10-25) are addressed exactly as the plan describes: T-10-20 by `test_enrollment_page_refuses_an_invalid_signature`, T-10-21 by the D-07 refusal and its two test methods, T-10-22 by the renamed `INTERNAL_MEMBERDATA_PROPERTIES` tuple and its round-trip test, T-10-23 by the extended guard's positive-presence and generalised-absence assertions, T-10-25 by `is_seed_encryption_available`'s own docstring. T-10-24 (the discarded seed mint on the `challenge()` path) is an accepted residual per the plan's own disposition, unchanged by this plan. T-10-SC is not applicable — no package installs in this plan.

## Next Phase Readiness

- The MFA-19 path is now hardened on all three fronts the plan named: the state-write guard, the D-07 refusal, and the D-17 member-data-only proof plus the tampered-signature refusal.
- Plan 10-06 can build on `is_seed_encryption_available()` and the extended guard's two new assertions without re-deriving either.
- The `is_seed_encryption_available` occurrence-count deviation noted above (3 vs. the criterion's literal `2`) is cosmetic only — both required elements (import, call) are present and covered; no follow-up needed.

## Self-Check: PASSED

All 5 modified files and this SUMMARY.md confirmed present on disk; all three task commit hashes (`88a37d2`, `26651fa`, `e4e29c2`) confirmed present in `git log --oneline --all`.

Verified directly: `[ -f <path> ]` for all 6 files (all FOUND), and `git log --oneline --all | grep -q <hash>` for all 3 commit hashes (all FOUND).

---
*Phase: 10-global-enforcement-and-enrollment*
*Completed: 2026-08-06*
