---
phase: 05-drift-replay-and-lockout
verified: 2026-08-01T14:00:00Z
status: gaps_found
score: 18/19 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 15/16
  gaps_closed:
    - "A locked account is not an oracle at @@google-authenticator-token to an unsigned, unauthenticated caller (CR-01, closed by plan 05-04: is_account_locked now runs strictly after validate_user_data succeeds and strictly before validate_token)."
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "A locked account is not an oracle at @@reset-bar-code (ROADMAP Phase 5 Success Criterion 3's 'is not an oracle' clause and MFA-08, extended to this endpoint by plan 05-03's own stated objective: 'closing the anonymous TOTP guessing oracle at @@reset-bar-code', and by that plan's own threat T-05-03, whose claimed mitigation -- 'the locked branch reuses the existing wrong-code message string verbatim ... no distinguishable response' -- is the exact claim this gap falsifies)."
    status: failed
    reason: >
      browser/forms/reset_bar_code.py::ResetBarCodeForm.handleSubmit performs no signature
      check of any kind before consulting is_account_locked (unlike token.py, this view's
      handleSubmit never calls validate_user_data at all -- that call exists only in
      updateFields, a separate render-time code path not exercised by the POST handler).
      An anonymous caller supplying nothing but a real or guessed auth_user query parameter
      -- no password, no ska signature, no auth_timestamp, no correct code -- can therefore
      distinguish a locked account from a merely-wrong-code account, because the two
      branches wrap the identical inner reason string in two different top-level message
      templates: the locked branch (lines 116-122) renders
      "Resetting of the bar-code failed! Invalid token or token expired.", while the
      wrong-code branch (lines 130-167, via the `reason is not None` tail at line
      166-167) renders "Setup failed! Invalid token or token expired.". The comment
      directly above the locked branch (lines 111-115) states "Locked accounts get the
      exact same message as a wrong code, so the response cannot be used as an oracle" --
      this is false: the assembled, user-visible strings differ by their leading
      template, and nothing in tests/test_reset_bar_code.py ever asserts message equality
      between the two branches (confirmed by grep: zero occurrences of either literal
      template, or of addStatusMessage, in that test file). This is a strictly weaker-
      attacker version of the same class of bug plan 05-04 was written to close in
      token.py (CR-01): here there is no signature gate to get behind at all, because
      handleSubmit's control flow is user-not-found -> is_site_local_user ->
      is_account_locked -> validate_token, with no validate_user_data call anywhere in
      that path. `@@reset-bar-code` is registered permission="zope2.View" (configure.zcml
      line 41), confirming anonymous reachability.

      This is squarely in phase scope, not an out-of-phase concern: plan 05-03's own
      Multi-Source Coverage Audit maps MFA-08 to both 05-01 and 05-03; the operator's own
      2026-07-31 scope decision (05-VALIDATION.md Open Question 1, decision P5-12) put
      reset_bar_code.py under the same "not an oracle" invariant as token.py precisely
      because it is anonymously reachable and names its target account the same way; and
      the plan's own acceptance criteria only checked that the embedded `reason` string
      (`grep -c 'Invalid token or token expired'` == 2) was shared, never that the fully
      assembled status message was -- an insufficient test for the property the plan's own
      objective and threat model claimed to establish.
    artifacts:
      - path: "src/imio/googleauthenticator/browser/forms/reset_bar_code.py"
        issue: "Locked-account branch (lines 116-122) wraps its message in \"Resetting of the bar-code failed! {0}\"; the wrong-code branch (lines 130-167) wraps the identical reason in \"Setup failed! {0}\" -- the two rendered messages are distinguishable to an anonymous, unsigned caller, contradicting the adjacent comment and the plan's own T-05-03 mitigation claim."
    missing:
      - "Route the locked-account branch in reset_bar_code.py::handleSubmit through the same \"Setup failed! {0}\" wrapper the wrong-code branch uses (or otherwise make the two assembled status messages byte-identical), so the two failure modes are indistinguishable to a caller who has proven nothing but a username."
      - "A test in tests/test_reset_bar_code.py (mirroring tests/test_token.py::test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account) that submits a wrong code anonymously against a locked account and against an unlocked-but-enrolled account through @@reset-bar-code with no signature at all, and asserts the two rendered status messages are equal -- not merely that both contain the same embedded reason substring."
---

# Phase 5: Drift, Replay and Lockout Verification Report

**Phase Goal:** A code from the previous time step still works, a code already used never
works again, and brute-forcing the second factor stops after N attempts — with counters
that survive the request they are written in.
**Verified:** 2026-08-01T14:00:00Z
**Status:** gaps_found
**Re-verification:** Yes — after gap closure (plan 05-04 landed since the prior
2026-07-31T16:19:57Z VERIFICATION.md, which predates plan 05-04 and is now superseded)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + plan must_haves, merged)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A code from the immediately preceding time step is accepted (RFC 6238 §6) | ✓ VERIFIED | `helpers._find_accepted_interval` tries `(current, current-1)` only (helpers.py:368-370); `tests/test_helpers.py::TestDriftAndReplay.test_validate_token_accepts_previous_interval` passes |
| 2 | A code already consumed is rejected on reuse (RFC 6238 §5.2 MUST NOT) | ✓ VERIFIED | `validate_token` refuses when matched interval ≤ stored `two_factor_authentication_last_interval`; `test_validate_token_rejects_replayed_interval` passes, including the adjacency pair |
| 3 | The replay rejection is logged, with no plaintext username in the log line (ASVS 2.8.4/2.8.5) | ✓ VERIFIED | `logger.info` call carries no operand; `test_replay_rejection_log_has_no_username` asserts on both `record.getMessage()` and `record.args`, with a non-vacuity control on the accepted-submission case |
| 4 | 5 consecutive failures lock the account for 900s; the 4th does not | ✓ VERIFIED | `helpers.register_failed_second_factor` locks at `>= max_failed_attempts` (default 5); `tests/test_token.py::test_lockout_after_five_failures` |
| 5 | The lock is evaluated BEFORE the token at `@@google-authenticator-token`, and answers identically for a valid and an invalid code while locked | ✓ VERIFIED | `token.py:108` `is_account_locked` gate precedes `token.py:113` `validate_token`; `test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code` passes unmodified |
| 6 | A locked account at `@@google-authenticator-token` is not an oracle to an **unauthenticated, unsigned** caller (CR-01) | ✓ VERIFIED (gap closed this cycle) | `token.py:90-111`: `is_account_locked` now runs strictly after `validate_user_data`'s success branch and strictly before `validate_token`; `test_no_signature_response_is_identical_for_a_locked_and_an_unknown_account` proves three-way message equality (locked / unlocked-enrolled / nonexistent) for a caller with no `signature`/`auth_timestamp`. Confirmed by direct code review, not just the SUMMARY's claim: line order verified with `grep -n`, `validate_user_data` (90) < `is_account_locked` (108) < `validate_token` (113) |
| 7 | A locked account at `@@reset-bar-code` is not an oracle to an unauthenticated caller | ✗ FAILED | See Gaps below. `reset_bar_code.py` has no signature check anywhere in `handleSubmit`, and the locked-account message ("Resetting of the bar-code failed! ...") differs from the wrong-code message ("Setup failed! ..."), confirmed by direct source read of lines 111-122 and 162-167 |
| 8 | The lock expires on its own with no admin action; boundary holds in both directions | ✓ VERIFIED | `is_account_locked` compares `locked_until > int(time.time())`; `test_lockout_expires_without_admin_action` asserts both directions with no sleep/monkeypatch |
| 9 | A successful second factor resets the failure counter | ✓ VERIFIED | `reset_failed_second_factor` called on `token.py:120` and `reset_bar_code.py:138`; `test_successful_second_factor_resets_failed_attempts`, `test_reset_bar_code_lockout_after_five_failures` |
| 10 | Only exactly-6-digit input is a candidate token, gated in helpers.py before onetimepass | ✓ VERIFIED | `_is_six_digit_token` (helpers.py:325-345) checks ASCII-digit membership, called first inside `validate_token` before `get_secret`; `test_validate_token_rejects_non_six_digit_input` covers the full matrix incl. non-ASCII digit |
| 11 | `max_failed_attempts` / `lockout_duration` editable in control panel, defaults 5 / 900 | ✓ VERIFIED | `browser/controlpanel.py:50-58`; `test_control_panel_has_lockout_fields` |
| 12 | Every new memberdata property has an XML entry and a round-trip test | ✓ VERIFIED | `grep -c 'type="int"' memberdata_properties.xml` = 3; `test_new_memberdata_properties_round_trip`, `test_memberdata_properties_import_declares_expected_types` |
| 13 | The failure counter still increments after a request that ends in `Unauthorized` (write lives in the committing view, not an aborted path) | ✓ VERIFIED | `test_failed_attempt_counter_survives_unauthorized_request` drives a real two-request `Browser` sequence; `grep` confirms zero occurrences of the property names or helper functions in `pas_plugin.py`/`subscribers.py` |
| 14 | No second-factor state written from `pas_plugin.py` or `subscribers.py` | ✓ VERIFIED | `test_no_second_factor_state_written_from_the_plugin` (source-grep with positive control); independently re-confirmed by direct grep in this verification pass (0 matches) |
| 15 | `@@reset-bar-code` is metered by the same counter/lock, with no separate attempt budget from the login form | ✓ VERIFIED | `reset_bar_code.py:116` gate shares `helpers.is_account_locked`/`register_failed_second_factor`; `test_reset_bar_code_lockout_after_five_failures` step 5 asserts the login form is refused too |
| 16 | Counter/lock writes in `reset_bar_code.py` sit outside the existing broad `except Exception` block | ✓ VERIFIED | `reset_failed_second_factor(user)` at line 138, before the `try:` at line 139; `register_failed_second_factor(user)` at line 163, in the `else:` branch, outside the `try` |
| 17 | `browser/forms/user_setup.py` carries no counter | ✓ VERIFIED | `git diff` empty for this file across all 4 plans (confirmed in each SUMMARY; file untouched by any phase-5 commit) |
| 18 | `CHANGES.rst` documents the phase and the profile-import requirement | ✓ VERIFIED | `grep -c 'imio.googleauthenticator:default'`, `lockout_duration`, `max_failed_attempts` all present |
| 19 | Full test suite green | ✓ VERIFIED | Independently re-run in this verification pass: `bin/test -t '!robot'` → 83 tests, 0 failures, 0 errors |

**Score:** 18/19 truths verified (0 present, behavior-unverified)

### Independent Judgment: Does the `@@reset-bar-code` message-oracle count as a Phase 5 gap?

**Ruling: yes, it is a phase gap, not an out-of-scope finding.** Reasoning:

1. **The phase's own plan put this endpoint under the same invariant.** Plan 05-03's `<objective>`
   states its purpose in exactly these words: *"Close the anonymous TOTP guessing oracle at
   `@@reset-bar-code`"*. The plan's own threat model, T-05-03 (Information Disclosure, severity
   `medium`, disposition `mitigate`), claims: *"The locked branch reuses the existing wrong-code
   message string verbatim, so no new i18n msgid and no distinguishable response."* That claim is
   what CR-01 (this cycle's code review) falsifies by direct inspection. A plan cannot both declare
   an invariant as its stated purpose and then be judged to have never been in scope for it.
2. **It is the same class of defect the phase already treated as blocking once.** Plan 05-04 exists
   *solely* because the equivalent defect in `token.py` was rated CRITICAL and treated as a phase
   gap after the first VERIFICATION.md run. Applying a different disposition to the structurally
   identical defect in the sibling endpoint the very next plan targeted would be inconsistent
   without a stated reason, and no such reason exists — if anything the `reset_bar_code.py` case is
   *worse*, since there is no signature-validating code path at all in `handleSubmit` to move the
   gate behind (unlike `token.py`, which at least performs `validate_user_data`).
3. **ROADMAP Phase 5 Success Criterion 3's wording ("is not an oracle") is a property of the lock
   the phase built, not of one specific view.** The operator's own 2026-07-31 scope decision
   (recorded in `05-VALIDATION.md` Open Question 1 and decision P5-12) explicitly extended the
   lockout — and by necessary implication the "must not be an oracle" property that makes a lockout
   safe to ship — to `reset_bar_code.py`, specifically because leaving it unmetered would make the
   phase goal "false while appearing met." An oracle that discloses lock state is the message-level
   analogue of the same failure the scope decision was written to prevent.
4. **The plan's own acceptance criteria were the actual proximate cause, and are precisely
   fixable.** `05-03-PLAN.md`'s acceptance criterion checked only that the embedded `reason` string
   appeared twice (`grep -c 'Invalid token or token expired'` == 2) — it never checked the fully
   assembled, user-visible message. This is a narrow, well-defined test gap with a precise fix
   (documented in `missing[]` above), not a design question requiring a human decision.

Given this, the gap is recorded as a **BLOCKER** (must-have FAILED) rather than a WARNING, and MFA-08
is not fully satisfied at phase end — `@@google-authenticator-token`'s oracle is closed (verified),
`@@reset-bar-code`'s is not.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/helpers.py` | `is_account_locked`, `register_failed_second_factor`, `reset_failed_second_factor`, `_is_six_digit_token`, `_find_accepted_interval`, `TOTP_INTERVAL_SECONDS`, rewritten `validate_token` | ✓ VERIFIED | All present, all wired into both form views |
| `src/imio/googleauthenticator/userdataschema.py` | 3 new `Int` fields + omit-list entries | ✓ VERIFIED | Confirmed by grep |
| `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` | 3 `type="int"` entries | ✓ VERIFIED | `grep -c 'type="int"'` = 3 |
| `src/imio/googleauthenticator/browser/controlpanel.py` | `max_failed_attempts`, `lockout_duration` | ✓ VERIFIED | Present, defaults 5/900 |
| `src/imio/googleauthenticator/browser/forms/token.py` | lock gate after signature check, before token check | ✓ VERIFIED | Line order: `validate_user_data`(90) < `is_account_locked`(108) < `validate_token`(113) |
| `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` | lock gate + counter writes, no oracle | ⚠️ ORPHANED CLAIM | Gate exists and is wired (before `validate_token`), but the "not an oracle" claim in the adjacent comment is false — see Gaps |
| `src/imio/googleauthenticator/tests/test_token.py` | 6 test methods incl. CR-01 closure test | ✓ VERIFIED | All 6 present and passing |
| `src/imio/googleauthenticator/tests/test_reset_bar_code.py` | lockout + bypass proof | ✓ VERIFIED (for what it tests) | Present and passing, but does not test message equality — the exact gap this report identifies |
| `CHANGES.rst` | phase entries + profile-import note | ✓ VERIFIED | Present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `token.py::handleSubmit` | `helpers.is_account_locked` | gate call, post-signature-check | ✓ WIRED | Line order confirmed |
| `token.py::handleSubmit` | `helpers.register_failed_second_factor`/`reset_failed_second_factor` | success/failure branches | ✓ WIRED | Unmoved by 05-04's reorder (grep confirms zero changed lines touching these identifiers) |
| `reset_bar_code.py::handleSubmit` | `helpers.is_account_locked` | gate call, pre-`validate_token` | ✓ WIRED (mechanically) | But not preceded by any signature check — see Gaps |
| `reset_bar_code.py::handleSubmit` | `helpers.register_failed_second_factor`/`reset_failed_second_factor` | outside the `try/except Exception` block | ✓ WIRED | Line order confirmed (138 before 139 `try:`; 163 in `else:`, outside `try`) |
| `helpers.validate_token` | `two_factor_authentication_last_interval` | single `setMemberProperties` write | ✓ WIRED | Confirmed in source |
| `pas_plugin.py` / `subscribers.py` | (must NOT write second-factor state) | — | ✓ VERIFIED (absence) | 0 grep matches for any of the 3 property names or 3 helper function names |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full non-robot suite | `bin/test -t '!robot'` | 83 tests, 0 failures, 0 errors, 17.8s | ✓ PASS |
| Reset-bar-code and token-form line order (MFA-08 gate placement) | `grep -n` on both files | Confirmed as documented above | ✓ PASS |
| No second-factor writes from PAS plugin/subscribers | `grep` for property/function names | 0 matches | ✓ PASS |
| Anonymous reachability of `@@reset-bar-code` | `configure.zcml` permission check | `permission="zope2.View"`, `for="*"` | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` convention; verification relies on
`bin/test` (zope.testrunner), run above.

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|---|---|---|---|---|
| MFA-05 | 05-02 | Previous-interval code accepted | ✓ SATISFIED | Truth #1 |
| MFA-06 | 05-02 | Replayed code refused, logged without username | ✓ SATISFIED | Truths #2, #3 |
| MFA-07 | 05-02 | Only exactly-6-digit input is a candidate | ✓ SATISFIED | Truth #10 |
| MFA-08 | 05-01, 05-03, 05-04 | N failures lock; lock before token; not an oracle | ✗ BLOCKED | Truths #4-7: token-form side fully satisfied (05-04 closed CR-01), reset-bar-code side still an oracle (new gap) |
| MFA-09 | 05-01 | Lock self-expires | ✓ SATISFIED | Truth #8 |
| MFA-10 | 05-01 | N/duration editable, defaults 5/900 | ✓ SATISFIED | Truth #11 |
| MFA-11 | 05-01, 05-03 | Success resets counter | ✓ SATISFIED | Truth #9 |
| MFA-12 | 05-01 | No state written from PAS plugin/challenge plugin | ✓ SATISFIED | Truths #13, #14 |
| MFA-13 | 05-01 | Properties declared + round-trip tested | ✓ SATISFIED | Truth #12 |

All 9 phase-5 requirement IDs (MFA-05..13) are claimed across the four plans' `requirements:`
frontmatter (05-01: MFA-08/09/10/11/12/13; 05-02: MFA-05/06/07; 05-03: MFA-08/11/12; 05-04: MFA-08).
No orphaned requirement IDs found for this phase.

**Documentation note (not a code gap):** `REQUIREMENTS.md` line 55 marks `MFA-08` `[x]` (complete)
in the checklist while the traceability table below it (lines 191-199) still marks all of
MFA-05..13, including MFA-08, as "Gaps Found" — a stale/inconsistent pair of markers left over from
the prior verification cycle (see commit `27a65b1`, "revert premature Complete requirements"). This
is a documentation-sync issue for the next `/gsd-progress`/ship pass, not a code defect, and does not
change any truth's status above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `browser/forms/reset_bar_code.py` | 111-122 vs 162-167 | False comment ("exact same message... cannot be used as an oracle") contradicted by the actual two-template implementation | 🛑 Blocker | This is the gap above, not a separate finding |
| `helpers.py` | 644, 672 | Pre-existing `FIXME` markers (dated 2014, commit `4faeac2`, predates this phase) | ℹ️ Info | Not introduced by phase 5; unrelated to lockout/drift/replay code |
| `browser/forms/token.py` | 130 | Pre-existing `TODO` (dated 2015, commit `4e29c5cb`, predates this phase) | ℹ️ Info | Unrelated to phase-5 changes |
| `userdataschema.py` | 86-102 | New `Int` lockout/replay fields have no `readonly=True`; `omit()` in `CustomizedUserDataPanel.__init__` is the sole barrier to self-editing | ⚠️ Warning | Carried forward from 05-REVIEW.md WR-02, explicitly deferred (not a phase gap; documented tradeoff) |
| `reset_bar_code.py` | 72-164 | Reset-form counter consumable with no signature check at all (accepted DoS, bounded by `lockout_duration`) | ⚠️ Warning | Carried forward from 05-REVIEW.md WR-01/decision P5-13; documented, tested, accepted tradeoff — distinct from the message-oracle gap above |
| `controlpanel.py` | 148-152 | Dead `disable_two_factor_authentication_for_users` fetch/import | ℹ️ Info | Pre-existing, unrelated to this phase |

No unresolved `TBD`/`FIXME`/`XXX` markers were introduced by phase 5's own commits (all found markers
predate the phase, confirmed via `git blame`).

### Human Verification Required

None beyond what is already recorded as backstop items in the plan frontmatter (control-panel field
persistence through a running instance, and a real Google Authenticator app at the drift boundary) —
both already deferred to end-of-phase human verification per `config.json`'s
`human_verify_mode: end-of-phase`, and neither affects the automated-verification status above.

### Gaps Summary

One BLOCKER remains: the same "locked account must not be an oracle" property that plan 05-04 closed
for `@@google-authenticator-token` (CR-01) is still open for `@@reset-bar-code`, introduced when
05-03 metered that endpoint and reachable by a strictly weaker attacker (no signature check exists
in that view's submit path at all). The phase's own plan 05-03 declared closing exactly this class
of oracle as its objective and claimed in its own threat model that the message was verbatim-shared;
neither the plan's acceptance criteria nor its tests actually checked the fully-assembled message,
only the embedded `reason` substring, so the defect shipped and was not caught until this
verification's independent source read (confirmed also by the fresh code review, 05-REVIEW.md CR-01
in this cycle's numbering). The fix is narrow and precisely specified in `missing[]` above: make the
two message templates identical, and add a test that would have caught this the first time.

Every other must-have — drift acceptance, replay rejection and its no-username log, the exact-6-digit
gate, the lockout threshold and its self-expiry, the reset-on-success behavior, the MFA-12
write-only-from-a-committing-view invariant (including survival across an `Unauthorized`-ending
request), and the memberdata-property declaration/round-trip/profile-import chain — is verified
against the actual source and an independently re-run full test suite (83 tests, 0 failures), not
merely against SUMMARY.md's claims.

---

_Verified: 2026-08-01T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
