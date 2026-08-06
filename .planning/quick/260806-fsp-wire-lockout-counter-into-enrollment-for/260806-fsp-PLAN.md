---
phase: quick-260806-fsp
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/imio/googleauthenticator/browser/forms/user_setup.py
  - src/imio/googleauthenticator/tests/test_user_setup.py
  - CHANGES.rst
autonomous: true
requirements: [MFA-08, MFA-11, MFA-12]
source: ".planning/phases/06-recovery-codes/06-REVIEW.md CR-01 (CRITICAL); .planning/v1.0-MILESTONE-AUDIT.md Gap 1; operator decision 2026-08-06"

must_haves:
  truths:
    - "A locked account submitting a currently-correct TOTP code at @@setup-two-factor-authentication is refused: the enrolment flag is not written and no recovery codes are minted."
    - "The response a locked account gets at that form is indistinguishable from the response a wrong code gets: same status message text and same redirect target (MFA-08 no-oracle)."
    - "One wrong code at that form increments two_factor_authentication_failed_attempts."
    - "A correct code at that form clears two_factor_authentication_failed_attempts and any active lock."
    - "Reaching the configured max_failed_attempts at that form sets two_factor_authentication_locked_until, so is_account_locked reports True."
    - "All second-factor state writes on this path still happen inside the committing form view, never in pas_plugin.py or a subscriber (MFA-12)."
  artifacts:
    - "src/imio/googleauthenticator/browser/forms/user_setup.py — lock gate before validate_token, counter reset on success, counter increment on failure"
    - "src/imio/googleauthenticator/tests/test_user_setup.py — four new lockout tests plus per-method state reset"
    - "CHANGES.rst — one bullet under 1.0.0 (unreleased) ending with [chris-adam]"
  key_links:
    - "user_setup.SetupForm.handleSubmit -> helpers.is_account_locked (runs strictly before validate_token, so a locked account never reaches TOTP arithmetic)"
    - "user_setup.SetupForm.handleSubmit -> helpers.register_failed_second_factor / reset_failed_second_factor (the same counter and lock token.py and reset_bar_code.py already share — one budget, no third)"
    - "profiles/default/actions.xml 'Regenerate recovery codes' -> @@setup-two-factor-authentication -> this TOTP gate (the device-possession check that stops a recovery-code holder minting a fresh set)"
---

<objective>
`SetupForm.handleSubmit` is the only one of the three `validate_token` callers in this
package with no lockout wiring: no `is_account_locked` check before validating, no
`register_failed_second_factor` on failure, no `reset_failed_second_factor` on success.
Because `profiles/default/actions.xml` points the "Regenerate recovery codes" action at the
same view, a caller who already holds an authenticated session (hijacked session, or a login
that skipped the second factor via `ip_addresses_whitelist`) can brute-force six-digit
guesses at it without limit and, on a hit, replace all ten stored recovery-code hashes.

Purpose: close 06-REVIEW.md CR-01 (CRITICAL) / v1.0-MILESTONE-AUDIT.md Gap 1, per the
operator decision of 2026-08-06 — wire this third caller into the counter the other two
already share.

Output: the lock gate and both counter calls in `user_setup.py`, four tests proven
load-bearing by mutation, and a CHANGES.rst bullet.
</objective>

<execution_context>
@/srv/src/imio.googleauthenticator/.claude/gsd-core/workflows/execute-plan.md
@/srv/src/imio.googleauthenticator/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.claude/CLAUDE.md
@.planning/STATE.md
@src/imio/googleauthenticator/browser/forms/user_setup.py
@src/imio/googleauthenticator/browser/forms/reset_bar_code.py
@src/imio/googleauthenticator/tests/test_user_setup.py

Python 2.7 / Plone 4.3 only: no f-strings, `.format()` for interpolation, `unicode`
literals where z3c.form expects them.

Facts already established by reading the sources, so you do not need to re-derive them:

- `helpers.is_account_locked(user)` reads `two_factor_authentication_locked_until`
  (helpers.py:479). `helpers.register_failed_second_factor(user)` increments
  `two_factor_authentication_failed_attempts` and, on reaching
  `get_app_settings().max_failed_attempts`, writes `locked_until = now + lockout_duration`
  and zeroes the counter in the same write (helpers.py:497).
  `helpers.reset_failed_second_factor(user)` zeroes both (helpers.py:531).
- `helpers.validate_token(token, user=None)` falls back to `api.user.get_current()` and, on
  success, writes `two_factor_authentication_last_interval` — so two genuine TOTP
  acceptances inside the same ~30s interval are refused as a replay (MFA-06). This bit
  07-01; it is why the tests below need `last_interval` zeroed per method and at most one
  success per method.
- Recovery-code state lives in `two_factor_authentication_recovery_codes_salt` and
  `two_factor_authentication_recovery_codes_hashes` (memberdata_properties.xml lines 9-10).
- `reset_bar_code.py` lines 111-171 is the shape to follow, with one deliberate deviation
  spelled out in Task 2.
- All test classes in this package run on `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`;
  the integration layer was deleted in Phase 8.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add the four lockout tests, proven RED against the unfixed source</name>
  <files>src/imio/googleauthenticator/tests/test_user_setup.py</files>
  <action>
Add four test methods to the existing `TestSetupForm` class rather than a second class —
this repo's own WR-03/P5-07 precedent (07-01 decision: new lockout tests landed in the
existing `TestTokenFormLockout` class). Reusing `_build_form`, `_clear_location` and the
existing `setUp` avoids duplicating ~50 lines of z3c.form request mechanics. Extend the
class docstring with one short paragraph saying the class now also covers the CR-01 lockout
wiring, so the BUG-02-only framing does not mislead the next reader.

Drive the form the way the existing methods do: `form = self._build_form(u'123456')` then
`SetupForm.handleSubmit.func(form, None)`, and `self._clear_location()` between submits.
Do NOT stub `user_setup.validate_token` in these four — use a real code,
`get_totp(helpers.get_secret(user), as_string=True)` from `onetimepass`, so the tests
measure the real gate. For a wrong code use six digits that differ from the correct one
(mirror `test_reset_bar_code.py::_wrong_code`).

State hygiene, both directions:
- In `setUp`, right after the existing `get_or_create_secret(..., overwrite=True)` call, add
  one `setMemberProperties` that zeroes `enable_two_factor_authentication`,
  `two_factor_authentication_failed_attempts`, `two_factor_authentication_locked_until`,
  `two_factor_authentication_last_interval`, and both recovery-code properties. Two
  independent reasons: the MemberData cache is not isolated per test method on this layer
  (see the comment already in `setUp`), and a `last_interval` written by an earlier method
  in the same 30s window would make a genuinely correct code read as a replay.
- Add the same reset to `tearDown`, mirroring `test_reset_bar_code.py`'s tearDown, so a lock
  or counter cannot leak into a later class sharing the layer.

The four tests, each re-fetching the user with `api.user.get(username=TEST_USER_NAME)` after
the submit rather than trusting the pre-submit object, and each carrying a non-vacuity
control assertion:

1. Locked account, correct code, refused. Set `locked_until` to a future epoch, capture the
   stored recovery-code hashes before the submit, assert the account really is locked
   (`helpers.is_account_locked`) as the precondition, submit the correct code, then assert:
   `enable_two_factor_authentication` still falsy, the stored hashes tuple unchanged, and
   `form.issued_recovery_codes` is None. State assertions before any message/return-value
   assertion, the discipline
   `test_handleSubmit_refuses_an_account_not_defined_in_this_site` already uses.
2. Wrong code increments the counter: assert the counter is 0 first, submit, assert 1.
3. Correct code clears the counter: seed the counter to a nonzero value below the maximum,
   assert that value is what was seeded, submit the correct code, assert the counter is 0
   and that enrolment did succeed (so the test cannot pass by the submit being rejected).
4. Reaching the maximum locks: read `int(helpers.get_app_settings().max_failed_attempts)`
   rather than hardcoding 5. Submit a wrong code `max - 1` times, assert `locked_until` is
   still 0 (non-vacuity control), submit once more, assert `helpers.is_account_locked` is
   True and that `locked_until` is no further ahead than `lockout_duration` seconds.

Run the module and record the result: against the unmodified `user_setup.py` all four MUST
fail. That RED run is the first half of this plan's non-vacuity evidence — quote the four
failure lines in the SUMMARY. Commit as `test(260806-fsp): ...`.
  </action>
  <verify>
    <automated>bin/test -t '!robot' -m test_user_setup 2>&amp;1 | tail -30   # expect 4 failures, one per new test, against unmodified user_setup.py</automated>
  </verify>
  <done>Four new test methods exist in `TestSetupForm`; `setUp` and `tearDown` both reset the enrolment, lockout, replay and recovery-code properties; the module runs with exactly the four new methods failing and every pre-existing method in the file still passing; the four failure lines are recorded.</done>
</task>

<task type="auto">
  <name>Task 2: Wire the lock gate and both counter calls into SetupForm.handleSubmit</name>
  <files>src/imio/googleauthenticator/browser/forms/user_setup.py</files>
  <action>
Add three single-line imports from `imio.googleauthenticator.helpers` — `is_account_locked`,
`register_failed_second_factor`, `reset_failed_second_factor` — placed in the existing
alphabetical single-line block per `.isort.cfg` (`force_single_line`,
`force_alphabetical_sort`).

In `handleSubmit`, after the existing `is_site_local_user()` guard (which keeps its own
distinct message by decision P5-17 — it explains the account is not defined in this Plone
site) and after `token = data.get('token', '')`:

- Hoist `user = api.user.get_current()` out of the `if valid_token:` block to just below the
  token extraction, so one user object serves the lock check, the validation call and both
  counter calls. Pass it explicitly as `validate_token(token, user=user)` instead of relying
  on the helper's internal fallback. Placing the hoist after the `is_site_local_user()`
  guard means a Zope-root account returns before `is_account_locked` ever sees a user with
  no property sheet.
- Restructure the existing `valid_token` dispatch into a three-arm chain whose first arm is
  the lock check: locked sets `reason` to the same wrong-code text
  (`Invalid token or token expired.`) and falls through; the second arm validates the token
  and, on success, calls `reset_failed_second_factor(user)` immediately before the existing
  `try:` block; the else arm calls `register_failed_second_factor(user)` and sets the same
  `reason`. Keep the existing `try:` body, its `except Exception` arm, the RECOV-03 comment
  block and the `redirect_url = None` mechanism byte-identical — that `None` is the entire
  one-time recovery-code display.

DELIBERATE DEVIATION from `reset_bar_code.py`, record it in the SUMMARY: there the locked
arm adds its message and returns, which is equivalent to falling through because that
handler's failure tail is message-only. Here the wrong-code path also binds `redirect_url`
and redirects to the setup form, so an early `return` in the locked arm would leave the
locked response at 200-with-no-Location while a wrong code gets a 302 — reinstating exactly
the message-plus-response oracle 05-05 closed on the reset form. So the locked arm must
reach the shared `if reason is not None:` tail and produce the same message and the same
redirect target as a wrong code. Add a comment at the locked arm saying it and the
wrong-code arm must be changed together or the lock becomes readable from the response
(MFA-08), cross-referencing the equivalent comment in `reset_bar_code.py`.

`reset_failed_second_factor(user)` goes *before* the `try:`, not inside it, per decision
P5-14: a `PropertyValueError` from a mis-declared memberdata property must surface as a 500,
not be caught by `except Exception` and reported as an unexpected error.

`handleSubmit` runs in a committing view, which is where MFA-12 requires second-factor state
writes to happen. Do not move any write into `pas_plugin.py` or a subscriber.

Re-run the module: the four new tests turn GREEN and the pre-existing methods in the file
stay green (they stub `user_setup.validate_token` by module-attribute rebinding, which the
restructured chain still routes through). Then run the whole suite. Commit as
`fix(260806-fsp): ...`.
  </action>
  <verify>
    <automated>bin/test -t '!robot' 2>&amp;1 | tail -15   # expect 132 tests, 0 failures, 0 errors (baseline was 128)</automated>
  </verify>
  <done>The lock gate runs before `validate_token`; success resets the counter before the `try:`; failure registers one attempt; the locked response carries the same status message and the same redirect target as a wrong code; full suite green with 4 more tests than the 128 baseline and no regressions.</done>
</task>

<task type="auto">
  <name>Task 3: Mutation-prove each test, then close the gates and the changelog</name>
  <files>src/imio/googleauthenticator/browser/forms/user_setup.py, CHANGES.rst</files>
  <action>
Three mutation checks against the now-green suite. For each: remove exactly one guard from
`user_setup.py`, run `bin/test -t '!robot' -m test_user_setup`, record which methods went
red, then restore and confirm `git diff --stat src/imio/googleauthenticator/browser/forms/user_setup.py`
reports nothing — byte-identical restoration, the discipline 05-01/05-03/05-05 used.

1. Delete the `is_account_locked` arm — test 1 must go red.
2. Delete the `register_failed_second_factor(user)` call — tests 2 and 4 must go red.
3. Delete the `reset_failed_second_factor(user)` call — test 3 must go red.

If any test stays green under its own mutation it is not evidence: fix the test, not the
record. Write the three results into the SUMMARY as a table (mutation, methods red, restored
clean yes/no).

Then the remaining gates: `bin/test-coverage -t '!robot'` must exit 0 (the CI gate is 90%
branch coverage; the baseline is TOTAL 90%, so report the new figure), and
`bin/code-analysis` must exit 0 so the pre-commit hook passes without `--no-verify`.

Finally add one bullet to `CHANGES.rst` under the existing `1.0.0 (unreleased)` heading, in
the house style — prose naming the enrolment/regeneration form as the third caller now
sharing the lockout counter, and the brute-force-a-fresh-recovery-code-set consequence it
closes, ending with a `[chris-adam]` attribution line. Commit as `docs(260806-fsp): ...`.
  </action>
  <verify>
    <automated>bin/test-coverage -t '!robot' &gt;/dev/null 2&gt;&amp;1; echo "coverage exit=$?"; bin/code-analysis &gt;/dev/null 2&gt;&amp;1; echo "lint exit=$?"; git diff --stat src/imio/googleauthenticator/browser/forms/user_setup.py; grep -c 'chris-adam' CHANGES.rst</automated>
  </verify>
  <done>All three mutation checks reproduced red on the expected methods and were restored with an empty diff; `bin/test-coverage -t '!robot'` exits 0 at 90% or above; `bin/code-analysis` exits 0; CHANGES.rst carries the new bullet under 1.0.0 (unreleased).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| authenticated session -> @@setup-two-factor-authentication POST | An attacker-held session (hijacked cookie, or a login that skipped the second factor via `ip_addresses_whitelist`) submits guessed six-digit codes. The submitted token is untrusted input; before this change it was rate-limited by nothing. |
| form response -> caller | The status message and HTTP response of a refusal are readable by an unauthenticated-in-practice attacker and must not disclose lock state. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-fsp-01 | Elevation of Privilege | `user_setup.SetupForm.handleSubmit` | critical | mitigate | Unmetered TOTP guessing mints a fresh recovery-code set (`generate_recovery_codes`). Task 2 gates on `is_account_locked` before `validate_token` and counts every failure into the shared counter, so the guess budget is `max_failed_attempts` per `lockout_duration`. |
| T-fsp-02 | Information Disclosure | the locked-arm refusal response | medium | mitigate | A distinct message or a distinct response shape makes lock state an oracle. Task 2's locked arm reaches the shared failure tail, so message text and redirect target match the wrong-code path exactly (the 05-05 finding, applied here before it can be introduced). |
| T-fsp-03 | Denial of Service | shared lockout counter | low | accept | A caller who can reach this form can now lock the account for `lockout_duration`. Same bounded, self-clearing exposure already accepted for the reset path under T-05-08/P5-13, and this form needs an authenticated session to reach at all. |
</threat_model>

<verification>
- `bin/test -t '!robot'`: 132 tests, 0 failures, 0 errors (baseline 128).
- `bin/test-coverage -t '!robot'` exits 0, TOTAL at or above 90%.
- `bin/code-analysis` exits 0; the commits do not need `--no-verify`.
- All four new tests recorded RED against the unfixed source in Task 1, and each recorded RED again under removal of its own guard in Task 3, with byte-identical restoration.
- `grep -n 'is_account_locked' src/imio/googleauthenticator/browser/forms/user_setup.py` shows the call above the `validate_token` call, not below it.
</verification>

<success_criteria>
All three of `token.py`, `reset_bar_code.py` and `user_setup.py` check the lock before
validating a TOTP code, count failures into one shared counter and clear it on success.
06-REVIEW.md CR-01 / v1.0-MILESTONE-AUDIT.md Gap 1 is closed with mutation-proven tests, the
one-time recovery-code display behaviour is unchanged, and the three gates
(`bin/test`, `bin/test-coverage`, `bin/code-analysis`) are green.
</success_criteria>

<output>
Create `.planning/quick/260806-fsp-wire-lockout-counter-into-enrollment-for/260806-fsp-SUMMARY.md` when done, including:
- the Task 1 RED evidence (four failure lines),
- the Task 3 mutation table (mutation, methods red, restored clean),
- the new coverage figure,
- the deliberate deviation from `reset_bar_code.py`'s early-return shape and why.
</output>
