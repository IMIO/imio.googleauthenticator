---
phase: 05-drift-replay-and-lockout
verified: 2026-08-01T16:30:00Z
status: human_needed
score: 19/19 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 18/19
  gaps_closed:
    - "A locked account is not an oracle at @@reset-bar-code to an anonymous, unsigned caller (closed by plan 05-05, commit be31592: the locked branch now emits the identical \"Setup failed! {0}\" wrapper the wrong-code branch uses, and the false adjacent comment was replaced with an honest, scoped one)."
  gaps_remaining: []
  regressions: []
gaps: []
human_verification:
  - test: "Restart a real ZEO cluster with two or more clients sharing the same ZODB, enable 2FA for a test account, submit failed second-factor attempts split across clients (e.g. 3 against client A, 2 against client B), and confirm the account still locks at the 5th cumulative failure rather than each client independently allowing 4."
    expected: "The lock triggers on the cumulative count across clients, because the counter lives in a memberdata property (ZODB-backed, not RAM), not on a per-instance count that a client-rotating attacker could multiply."
    why_human: "05-01-PLAN.md must_haves carries this as an explicit `verification: backstop` truth. The integration-test layer runs a single process against a single ZODB connection; it cannot exercise real inter-client consistency, which requires an actual multi-client ZEO deployment."
  - test: "In a running Plone instance (not the test layer), open the Google Authenticator control panel as a Manager, confirm 'Maximum failed second-factor attempts' and 'Lockout duration (seconds)' render with defaults 5 and 900, change both, save, reload the page, and confirm the new values persisted."
    expected: "Both fields render, accept edits, and the edited values are still shown after a page reload -- proving the AutoExtensibleForm/registry.xml wiring works end-to-end in a live instance, not just via `getUtility(IRegistry)` in a test."
    why_human: "05-01-PLAN.md must_haves carries this as an explicit `verification: backstop` truth. `test_control_panel_has_lockout_fields` (test_generic.py:112) checks the schema/registry wiring in-process; it does not drive the real z3c.form edit-and-persist round trip through a browser."
  - test: "With a real Google Authenticator (or compatible TOTP) mobile app enrolled against a test account, wait until the app's displayed code is within roughly 1-29 seconds of rolling over to the next 30-second interval, submit that about-to-expire code, and confirm it is still accepted (one step of RFC 6238 drift), then submit the code the app displays immediately after the rollover and confirm that one is accepted too."
    expected: "Both the code from the interval just before submission and the code from the current interval are accepted, proving the server's `_find_accepted_interval` arithmetic (comparing against `current` and `current - 1`) agrees with an independently-clocked, real mobile device rather than only with `onetimepass.get_hotp` called in-process against the same clock the assertion uses."
    why_human: "05-02-PLAN.md must_haves carries this as an explicit `verification: backstop` truth. `test_validate_token_accepts_previous_interval` (test_helpers.py:661) generates its own code with the same library and clock the code under test uses, so it cannot rule out a systematic arithmetic error that would still self-agree."
  - test: "Deploy the current build behind whatever front-end proxy/load balancer the target environment actually uses. As an anonymous, unauthenticated caller with no `signature`/`auth_timestamp` query parameters, submit `@@google-authenticator-token?auth_user=<a-locked-account>` and, separately, `@@google-authenticator-token?auth_user=<an-unlocked-or-nonexistent-account>`. Compare the two rendered pages byte-for-byte (status line, headers, body)."
    expected: "The two responses are indistinguishable end-to-end, not merely at the `zope.testbrowser` in-process level -- same HTTP status, no proxy-injected error page, no differential caching behavior that would let an external observer learn lock state."
    why_human: "05-04-PLAN.md must_haves carries this as an explicit `verification: backstop` truth, naming exactly this residual risk: `zope.testbrowser` exercises the view in-process and cannot rule out a difference introduced downstream by the real ZPublisher error/status path or a front-end proxy."
  - test: "Same deployment/proxy setup as above, but against `@@reset-bar-code?auth_user=<locked-account>` versus `@@reset-bar-code?auth_user=<unlocked-but-enrolled-account>`, both anonymous and unsigned, comparing the two rendered pages byte-for-byte."
    expected: "The two responses are indistinguishable end-to-end for the same reason as the token-form case above."
    why_human: "05-05-PLAN.md must_haves carries this as an explicit `verification: backstop` truth with the identical residual-risk statement, scoped to `@@reset-bar-code` instead of `@@google-authenticator-token`."
  - test: "Code-review only: confirm no future call site writing second-factor state (a property named `two_factor_authentication_*` or a call to `register_failed_second_factor`/`reset_failed_second_factor`) is ever added to `pas_plugin.py`, `subscribers.py`, or any other non-committing code path, as the codebase evolves after this phase."
    expected: "All second-factor state writes continue to originate only from `browser/forms/token.py` and `browser/forms/reset_bar_code.py`, both committing views."
    why_human: "05-03-PLAN.md must_haves records this explicitly as a `verification: backstop` truth: the current source-level guard (a grep-based test) covers `pas_plugin.py` and `subscribers.py` as they exist today, but cannot prove the invariant against files that do not yet exist. Not actionable today; recorded so a future reviewer checks it rather than assuming it is automatically enforced."
---

# Phase 5: Drift, Replay and Lockout Verification Report

**Phase Goal:** A code from the previous time step still works, a code already used never
works again, and brute-forcing the second factor stops after N attempts — with counters that
survive the request they are written in.
**Verified:** 2026-08-01T16:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plan 05-05 landed since the prior
2026-08-01T14:00:00Z VERIFICATION.md, which predates plan 05-05 and is now superseded)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + plan must_haves, merged)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A code from the immediately preceding time step is accepted (RFC 6238 §6) | ✓ VERIFIED | `helpers._find_accepted_interval` tries `(current, current-1)` only (helpers.py:368-370); `test_validate_token_accepts_previous_interval` passes (independently re-run) |
| 2 | A code already consumed is rejected on reuse (RFC 6238 §5.2 MUST NOT) | ✓ VERIFIED | `validate_token` refuses when matched interval ≤ stored `two_factor_authentication_last_interval` (helpers.py:444); `test_validate_token_rejects_replayed_interval` passes |
| 3 | The replay rejection is logged, with no plaintext username in the log line (ASVS 2.8.4/2.8.5) | ✓ VERIFIED | `logger.info('TOTP replay rejected')` (helpers.py:445) — static string literal, no operand at all; `test_replay_rejection_log_has_no_username` asserts on both `record.getMessage()` and `record.args`, with a non-vacuity control on the accepted case (re-read directly, test passes) |
| 4 | 5 consecutive failures lock the account for 900s; the 4th does not | ✓ VERIFIED | `register_failed_second_factor` locks at `>= max_failed_attempts` (default 5, helpers.py:471-503); `test_lockout_after_five_failures` passes |
| 5 | The lock is evaluated BEFORE the token at `@@google-authenticator-token`, and answers identically for a valid and an invalid code while locked | ✓ VERIFIED | `token.py:108` `is_account_locked` gate precedes `token.py:113` `validate_token` (confirmed by direct read); `test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code` passes |
| 6 | A locked account at `@@google-authenticator-token` is not an oracle to an unauthenticated, unsigned caller | ✓ VERIFIED | `token.py:90-111`: `is_account_locked` runs strictly after `validate_user_data`'s success branch and strictly before `validate_token`; `test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account` passes |
| 7 | A locked account at `@@reset-bar-code` is not an oracle to an unauthenticated caller | ✓ VERIFIED (gap closed this cycle, plan 05-05) | `reset_bar_code.py:123-129`: locked branch now emits `_("Setup failed! {0}".format(reason))`, byte-identical to the shared `reason is not None` tail at line 174 (confirmed by direct source read — both wrap the same reason in the same template). Comment above the gate (lines 111-122) now honestly states the two-way scope and cites MFA-08. `test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account` independently re-run: **1 test, 0 failures.** Confirmed the fix is what the SUMMARY claims, not merely that a test with that name exists: read `git show be31592` directly, which shows exactly the one-line wrapper swap described. |
| 8 | The lock expires on its own with no admin action; boundary holds in both directions | ✓ VERIFIED | `is_account_locked` compares `locked_until > int(time.time())` (helpers.py:453-469); `test_lockout_expires_without_admin_action` passes |
| 9 | A successful second factor resets the failure counter | ✓ VERIFIED | `reset_failed_second_factor` called at `token.py:120` and `reset_bar_code.py:145`; `test_successful_second_factor_resets_failed_attempts`, `test_reset_bar_code_lockout_after_five_failures` both pass |
| 10 | Only exactly-6-digit input is a candidate token, gated in helpers.py before onetimepass | ✓ VERIFIED | `_is_six_digit_token` (helpers.py:325-345), called first inside `validate_token` (helpers.py:410-413) before `get_secret`; `test_validate_token_rejects_non_six_digit_input` passes |
| 11 | `max_failed_attempts` / `lockout_duration` editable in control panel, defaults 5 / 900 | ✓ VERIFIED | `browser/controlpanel.py:50-64`: both `Int` fields, `default = 5` / `default = 900`, listed in the rendered fieldset; `test_control_panel_has_lockout_fields` passes |
| 12 | Every new memberdata property has an XML entry and a round-trip test | ✓ VERIFIED | `grep -c 'type="int"' memberdata_properties.xml` = 3 (all three new properties); `test_new_memberdata_properties_round_trip`, `test_memberdata_properties_import_declares_expected_types` both present and pass |
| 13 | The failure counter still increments after a request that ends in `Unauthorized` (write lives in the committing view, not an aborted path) | ✓ VERIFIED | `test_failed_attempt_counter_survives_unauthorized_request` drives a real two-request `Browser` sequence (Basic-Auth 302 into `@@google-authenticator-token`, then a bad-token POST) and asserts the counter reads 1 afterward; read the full test body directly — it is a genuine two-request sequence, not a mocked one |
| 14 | No second-factor state written from `pas_plugin.py` or `subscribers.py` | ✓ VERIFIED | Independent grep in this pass: 0 matches for any of the 3 property names or 3 helper function names in either file; `test_no_second_factor_state_written_from_the_plugin` passes |
| 15 | `@@reset-bar-code` is metered by the same counter/lock, with no separate attempt budget from the login form | ✓ VERIFIED | `reset_bar_code.py` shares `helpers.is_account_locked`/`register_failed_second_factor`; `test_reset_bar_code_lockout_after_five_failures` step 5 asserts the login form is refused too |
| 16 | Counter/lock writes in `reset_bar_code.py` sit outside the existing broad `except Exception` block | ✓ VERIFIED | `reset_failed_second_factor(user)` at line 145, before the `try:` at line 146; `register_failed_second_factor(user)` at line 170, in the `else:` branch, outside the `try` (confirmed by direct read) |
| 17 | `browser/forms/user_setup.py` carries no counter | ✓ VERIFIED | `git diff` across all 5 phase-5 plan commit ranges is empty for this file (confirmed via `git log --follow` scoped check) |
| 18 | `CHANGES.rst` documents the phase and the profile-import requirement | ✓ VERIFIED | `grep` confirms `imio.googleauthenticator:default`, `lockout_duration`, `max_failed_attempts` all present |
| 19 | Full test suite green | ✓ VERIFIED | Independently re-run in this verification pass: `bin/test -t '!robot'` → **84 tests, 0 failures, 0 errors, 19.4s** |

**Score:** 19/19 truths verified (0 present, behavior-unverified). All truths are confirmed against
the actual source and against independently re-run tests in this verification pass — not accepted
on the strength of any SUMMARY.md's narrative.

### Independent confirmation of the plan 05-05 gap closure

Read `git show be31592` directly rather than trusting `05-05-SUMMARY.md`'s description of it: the
commit's entire diff on `reset_bar_code.py` is the wrapper string on the locked branch
(`"Resetting of the bar-code failed! {0}"` → `"Setup failed! {0}"`) and the five-line comment above
it. Re-ran the new test in isolation (`bin/test -t
test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account` → 1 test, 0 failures)
and the whole non-robot suite (84 tests, 0 failures). `grep -v '^\s*#' ... | grep -c 'Setup failed'`
returns 2 (locked branch + shared tail) and the same pipeline for `'Resetting of the bar-code
failed'` returns 3 (user-not-found, non-site-local, invalid-reset-token) — matching the plan's own
stated acceptance criteria exactly.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/helpers.py` | `is_account_locked`, `register_failed_second_factor`, `reset_failed_second_factor`, `_is_six_digit_token`, `_find_accepted_interval`, `TOTP_INTERVAL_SECONDS`, rewritten `validate_token` | ✓ VERIFIED | All present, all wired into both form views |
| `src/imio/googleauthenticator/userdataschema.py` | 3 new `Int` fields + omit-list entries | ✓ VERIFIED | Confirmed by grep |
| `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` | 3 `type="int"` entries | ✓ VERIFIED | `grep -c 'type="int"'` = 3 |
| `src/imio/googleauthenticator/browser/controlpanel.py` | `max_failed_attempts`, `lockout_duration` | ✓ VERIFIED | Present, defaults 5/900 |
| `src/imio/googleauthenticator/browser/forms/token.py` | lock gate after signature check, before token check | ✓ VERIFIED | Line order: `validate_user_data`(90) < `is_account_locked`(108) < `validate_token`(113) |
| `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` | lock gate + counter writes, no oracle | ✓ VERIFIED | Gate wired, message wrapper now identical to the shared tail, comment now honest — the prior cycle's ORPHANED CLAIM is resolved |
| `src/imio/googleauthenticator/tests/test_token.py` | 6 test methods incl. CR-01 closure test | ✓ VERIFIED | All present and passing |
| `src/imio/googleauthenticator/tests/test_reset_bar_code.py` | lockout + bypass proof + message-equality proof | ✓ VERIFIED | 2 test methods (`grep -c 'def test_'` = 2); both present and passing |
| `CHANGES.rst` | phase entries + profile-import note | ✓ VERIFIED | Present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `token.py::handleSubmit` | `helpers.is_account_locked` | gate call, post-signature-check | ✓ WIRED | Line order confirmed |
| `token.py::handleSubmit` | `helpers.register_failed_second_factor`/`reset_failed_second_factor` | success/failure branches | ✓ WIRED | Confirmed by direct read |
| `reset_bar_code.py::handleSubmit` | `helpers.is_account_locked` | gate call, pre-`validate_token` | ✓ WIRED | Line order confirmed (123 < 132) |
| `reset_bar_code.py::handleSubmit` | `helpers.register_failed_second_factor`/`reset_failed_second_factor` | outside the `try/except Exception` block | ✓ WIRED | Confirmed: `reset_failed_second_factor` at 145 (before `try:` at 146), `register_failed_second_factor` at 170 (in `else:`, outside `try`) |
| `helpers.validate_token` | `two_factor_authentication_last_interval` | single `setMemberProperties` write | ✓ WIRED | Confirmed in source |
| `pas_plugin.py` / `subscribers.py` | (must NOT write second-factor state) | — | ✓ VERIFIED (absence) | 0 grep matches for any of the 3 property names or 3 helper function names, independently re-checked this pass |
| `reset_bar_code.py`'s locked branch | the shared `reason is not None` tail | identical message wrapper | ✓ WIRED (new this cycle) | Both emit `"Setup failed! {0}".format(reason)` verbatim; confirmed by direct read of lines 126 and 174 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full non-robot suite | `bin/test -t '!robot'` | 84 tests, 0 failures, 0 errors, 19.4s | ✓ PASS |
| New oracle-closure test in isolation | `bin/test -t test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account` | 1 test, 0 failures, 0 errors | ✓ PASS |
| Locked-vs-wrong-code message wrapper identity | `grep -v '^\s*#' reset_bar_code.py \| grep -c 'Setup failed'` / `'Resetting of the bar-code failed'` | 2 / 3 | ✓ PASS |
| Gate ordering (MFA-08, both endpoints) | `grep -n` on `token.py` and `reset_bar_code.py` | `is_account_locked(` precedes `validate_token(` in both | ✓ PASS |
| No second-factor writes from PAS plugin/subscribers | `grep` for property/function names | 0 matches | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` convention; verification relies on
`bin/test` (zope.testrunner), independently re-run above.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| MFA-05 | 05-02 | Previous-interval code accepted | ✓ SATISFIED | Truth #1 |
| MFA-06 | 05-02 | Replayed code refused, logged without username | ✓ SATISFIED | Truths #2, #3 |
| MFA-07 | 05-02 | Only exactly-6-digit input is a candidate | ✓ SATISFIED | Truth #10 |
| MFA-08 | 05-01, 05-03, 05-04, 05-05 | N failures lock; lock before token; not an oracle | ✓ SATISFIED | Truths #4-7: both `@@google-authenticator-token` (05-04) and `@@reset-bar-code` (05-05) close the oracle |
| MFA-09 | 05-01 | Lock self-expires | ✓ SATISFIED | Truth #8 |
| MFA-10 | 05-01 | N/duration editable, defaults 5/900 | ✓ SATISFIED | Truth #11 |
| MFA-11 | 05-01, 05-03 | Success resets counter | ✓ SATISFIED | Truth #9 |
| MFA-12 | 05-01 | No state written from PAS plugin/challenge plugin | ✓ SATISFIED | Truths #13, #14 |
| MFA-13 | 05-01 | Properties declared + round-trip tested | ✓ SATISFIED | Truth #12 |

All 9 phase-5 requirement IDs (MFA-05..13) are claimed across the five plans' `requirements:`
frontmatter (05-01: MFA-08/09/10/11/12/13; 05-02: MFA-05/06/07; 05-03: MFA-08/11/12; 05-04: MFA-08;
05-05: MFA-08). No orphaned requirement IDs found for this phase.

**Documentation note (not a code gap):** `REQUIREMENTS.md`'s checklist (line 55) marks `MFA-08`
`[x]` while every other MFA line (52-54, 56-60) is still `[ ]`, and the traceability table
(lines 191-199) still marks all of MFA-05..13, including MFA-08, as "Gaps Found." Both markers are
now stale given this verification's findings (all 9 satisfied) and should be updated in the next
`/gsd-progress`/ship pass. This is a documentation-sync issue, not a code defect, and does not
change any truth's status above.

### Independent Judgment: WR-01 and WR-02 (05-REVIEW.md, current cycle)

Neither open warning falsifies a stated Phase 5 Success Criterion; both are recorded here as
accepted, documented residual risk rather than silently dropped.

**WR-01 (`@@reset-bar-code` has no signature check, so an anonymous caller can drive the shared
lockout counter for any known/guessed username, with no IP-level rate limit bounding the *number of
distinct accounts* one attacker can lock at once):** Success Criterion 3 requires that 5 failures
lock the account, the lock is checked before the token, the locked account is not an oracle, and
the lock self-expires. All four hold, per-account, regardless of who triggered the failures — the
criterion says nothing about *who is authorized to cause a lock*, only about the lock's behavior
once triggered. The mass-lockout DoS WR-01 describes is a distinct availability concern the phase's
own plan 05-03 explicitly named, bounded (`lockout_duration`, self-expiring), and accepted by
operator decision (T-05-08/P5-13, `05-03-PLAN.md`), and it is the same disposition the standing
`Out of Scope` table in REQUIREMENTS.md gives to "Admin-unlock-only lockout... a DoS primitive": the
project's own posture already treats a bounded, self-clearing lockout as an acceptable tradeoff
class. Tested (`test_reset_bar_code_lockout_after_five_failures` asserts the bound), documented
(05-REVIEW.md WR-01, this file), and reversible (an IP/session throttle is additive, not a redesign)
— a Warning, not a Phase 5 blocker.

**WR-02 (the three new lockout/replay `Int` schema fields have no `readonly=True`; the personal
preferences form's `omit()` is the only barrier to self-editing today):** none of the five stated
Success Criteria concern schema-level write protection beyond what the current, actually-exposed UI
enforces — and the current UI (`CustomizedUserDataPanel.__init__`'s `omit()`) does enforce it today,
confirmed by the fact that no test or code path in this phase exposes an edit form for these fields
without that `omit()` applied. WR-02 names a *future* risk (a hypothetical consumer of
`IEnhancedUserDataSchema` that renders the schema without re-applying `omit()`), not a present
violation of any truth verified above. A Warning, not a blocker — `readonly=True` is a cheap,
independent hardening step worth taking opportunistically, but its absence does not make any of the
five Success Criteria false today.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `helpers.py` | 644, 672 | Pre-existing `FIXME` markers (dated 2014, predates this phase) | ℹ️ Info | Not introduced by phase 5; unrelated to lockout/drift/replay code |
| `browser/forms/token.py` | ~130 | Pre-existing `TODO` (dated 2015, predates this phase) | ℹ️ Info | Unrelated to phase-5 changes |
| `userdataschema.py` | 86-102 | New `Int` lockout/replay fields have no `readonly=True`; `omit()` is the sole barrier | ⚠️ Warning | WR-02, judged above — not a phase gap |
| `reset_bar_code.py` | 72-171 | Reset-form counter consumable with no signature check at all (accepted, bounded DoS) | ⚠️ Warning | WR-01, judged above — not a phase gap |
| `controlpanel.py` | 148-152 | Dead `disable_two_factor_authentication_for_users` fetch/import | ℹ️ Info | Pre-existing, unrelated to this phase |

No unresolved `TBD`/`FIXME`/`XXX` markers were introduced by phase 5's own commits (all found
markers predate the phase, independently re-confirmed by grep in this pass).

### Human Verification Required

See the `human_verification` frontmatter list above (6 items, all traceable to explicit
`verification: backstop` truths recorded in the phase's own five PLAN.md files). These are runtime
claims about a real ZEO cluster, a real running control panel, a real mobile-app clock, and a real
front-end proxy — none of which the integration-test layer can exercise. `config.json` sets
`workflow.human_verify_mode: end-of-phase`, and this is that end-of-phase point: all five plans have
executed and the phase's last remaining code gap (the `@@reset-bar-code` oracle) is closed, so these
backstop items now surface rather than being deferred further. None of the six items describes a
code defect — each is present, wired, and covered by an in-process test that this verification
independently re-ran and confirmed passing; what remains is confirmation against real infrastructure
this test environment does not have.

### Gaps Summary

No gaps remain. The single BLOCKER carried by the prior verification cycle — the `@@reset-bar-code`
message-level lock-state oracle — is closed by plan 05-05 (commit `be31592`), independently
confirmed in this pass by direct source read, an isolated re-run of the new test, and a full-suite
re-run (84 tests, 0 failures, 0 errors). All 19 observable truths behind the phase's 5 ROADMAP
success criteria are verified against the actual source and independently re-run tests, not against
any SUMMARY.md's narrative. Two open code-review Warnings (WR-01, WR-02) are judged above as
accepted, documented residual risk that does not falsify any stated Success Criterion.

Status is `human_needed` rather than `passed` because six truths across the phase's five plans are
explicitly marked `verification: backstop` in PLAN.md frontmatter — claims about real ZEO-cluster
behavior, a real running control panel, a real mobile TOTP app, and real front-end-proxy behavior —
none of which an in-process integration test can prove. This is the intended `end-of-phase` human
gate (`config.json`'s `human_verify_mode`), not a new finding; it was deferred by design through
plans 05-01 through 05-05 and surfaces now because this is the last verification pass before the
phase closes.

---

_Verified: 2026-08-01T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
</content>
