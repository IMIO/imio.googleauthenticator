---
phase: 06-recovery-codes
verified: 2026-08-04T08:03:21Z
status: human_needed
score: 5/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Decide whether CR-01 (06-REVIEW.md) — SetupForm.handleSubmit in browser/forms/user_setup.py validates the TOTP code with a bare `validate_token(token)` call and wires no `is_account_locked` / `register_failed_second_factor` / `reset_failed_second_factor`, unlike token.py (the login gate) and reset_bar_code.py (05-03's reset gate) — must be fixed before Phase 6 is considered closed, or explicitly accepted as a deferred/out-of-scope risk."
    expected: "A deliberate, recorded decision: either a follow-up plan wires the shared lockout counter into user_setup.py's handleSubmit (mirroring reset_bar_code.py's shape, per 06-REVIEW.md's suggested fix), or the project record explains why an unthrottled TOTP check gating enrollment AND `regenerate_recovery_codes` (actions.xml's own comment names this exact check as regeneration's sole security gate) is acceptable."
    why_human: "Not mechanically resolvable from source: none of the 5 ROADMAP success criteria or any must_haves.truths in the three PLANs assert this endpoint is rate-limited, so no test failure or missing artifact flags it — this is a risk-acceptance judgment call that needs a human decision, not a code check. Confirmed still present and unaddressed in HEAD (git log shows the review commit `a6b06ec` is the tip of the branch, no follow-up fix commit exists)."
---

# Phase 6: Recovery Codes Verification Report

**Phase Goal:** A user who loses their authenticator device recovers access themselves, once per
code, and that path is throttled exactly like the TOTP path.
**Verified:** 2026-08-04T08:03:21Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Enrollment issues 10 single-use codes of 80 bits each (`os.urandom(10)` -> 16 base32 chars), displayed exactly once and never redisplayed; plaintext never in ZODB, only a per-user-salted hash | ✓ VERIFIED | `helpers.generate_recovery_codes` (helpers.py:607-631): `os.urandom(RECOVERY_CODE_ENTROPY_BYTES=10)` -> `base64.b32encode` -> 16 chars, `RECOVERY_CODE_COUNT=10`; hashed via PBKDF2-HMAC-SHA256 under one `os.urandom(16)` salt, stored hex in two memberdata properties, only the hash tuple and salt written. `SetupForm.render()` (user_setup.py:147-157) shows `recovery_codes.pt` only when `issued_recovery_codes` is populated on that instance; a fresh instance's default is `None`. Plaintext-absence proven by `test_recovery_code_storage_and_validation_edges` (test_helpers.py:822-935): `assertNotIn(code, stored_salt)` / `assertNotIn(code, stored_hash)` for every one of the 10 codes against both stored values. "Never redisplayed" proven by `test_recovery_codes_are_issued_once_at_enrollment` (test_user_setup.py:337+): a **fresh** `SetupForm` instance's `render()` contains none of the 10 codes. |
| 2 | A recovery code is accepted in place of a TOTP token, is consumed on use, and is rejected on a second use | ✓ VERIFIED | `helpers.validate_second_factor` dispatches a 16-char base32 candidate to `validate_recovery_code`, which removes the matched entry **by index** (`stored[:i] + stored[i+1:]`, helpers.py:678-681) in the same `setMemberProperties` call that returns `True`. End-to-end proof: `test_recovery_code_is_accepted_in_place_of_a_token_and_consumed` (test_token.py) — a real `Browser` POST of an unused code logs the user in (10->9 hashes), replay of the same code is refused (still 9), a second unused code still works (9->8), TOTP still works unchanged, four shape-refusal edges and a cross-user code are all refused. |
| 3 | A failed recovery-code attempt increments the SAME counter as a failed TOTP attempt | ✓ VERIFIED | `browser/forms/token.py:113`'s single dispatch call (`valid_token = validate_second_factor(token, user=user)`) sits between the untouched `reset_failed_second_factor` (line 120) and `register_failed_second_factor` (line 140) calls Phase 5 built — no new call site, no new counter. `test_recovery_code_failure_shares_the_totp_lockout_counter` (test_token.py:582-665) proves: one wrong recovery code -> counter reads 1; a **mixed** run of 1 wrong recovery code + 3 wrong TOTP codes + 1 more wrong recovery code (5 failures of two kinds) locks the account, with an explicit non-vacuity control that 4 of the 5 do not yet lock; a genuine code after the lock is cleared resets both the counter and the lock through `reset_failed_second_factor`. `test_second_factor_dispatch_has_exactly_one_call_site_per_outcome` pins the structural invariant by counted source assertion (exactly one `validate_second_factor(`, one `register_failed_second_factor(`, one `reset_failed_second_factor(` in token.py), demonstrated to fail on a deliberately injected second dispatcher call, then restored (06-03-SUMMARY.md deviation log; confirmed against HEAD's `git diff --stat` being empty for token.py). |
| 4 | The user can regenerate the whole set, and every previously issued code stops working | ✓ VERIFIED | `regenerate_recovery_codes` portal action (actions.xml:41-52) routes to `@@setup-two-factor-authentication`, which re-mints via `generate_recovery_codes(user)` on its existing TOTP-accept path — one salt+hashes write per call. `test_recovery_code_regeneration_invalidates_the_previous_set` (test_helpers.py:937+) proves: the stored salt changes between two consecutive calls; every code from the first set fails `validate_recovery_code` afterward; every code from the second set succeeds once; regenerating from 0, 1, and 10 previously-stored hashes each yields exactly 10. `test_regenerate_recovery_codes_action_is_registered` asserts the action is registered with the correct `url_expr` and `available_expr` (see CR-01 caveat below regarding the TOTP gate protecting this action). |
| 5 | The user is warned when 3 or fewer codes remain | ✓ VERIFIED | `validate_recovery_code`'s accept branch (helpers.py, after the consume write, before `return True`) queues a `'warning'`-level `IStatusMessage` when `len(remaining) <= RECOVERY_CODE_LOW_WATERMARK (3)`, guarded on `getRequest() is not None` so an absent request degrades to silence rather than a raise. `test_low_recovery_code_count_warning` (test_token.py:667-774) proves the adjacency boundary both ways (5→4 no warning, 4→3 count boundary), asserts the message is genuinely `warning`-class via the `<dl class="portalMessage warning">` regex, asserts the stored count (not the interpolated markup) at 3, and asserts a failed submission and an anonymous/unsigned submission both render no warning text (T-06-04 oracle prevention). |

**Score:** 5/5 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `profiles/default/memberdata_properties.xml` | Two new declared properties | ✓ VERIFIED | `two_factor_authentication_recovery_codes_salt` (`type="string"`), `two_factor_authentication_recovery_codes_hashes` (`type="lines"`) present, flat, no schema tie-in |
| `helpers.py` | Constants + 6 new functions | ✓ VERIFIED | `RECOVERY_CODE_COUNT/ENTROPY_BYTES/LENGTH/SALT_BYTES/ALPHABET/PBKDF2_ITERATIONS(=100000)/LOW_WATERMARK(=3)`; `_normalize_recovery_code_input`, `_is_recovery_code_shape`, `_hash_recovery_code`, `generate_recovery_codes`, `validate_recovery_code`, `validate_second_factor` all present and substantive (read in full, not stubs) |
| `browser/forms/token.py` | Dispatch swap to `validate_second_factor` | ✓ VERIFIED | Line 113: `valid_token = validate_second_factor(token, user=user)`; import present, `validate_token` import removed |
| `browser/forms/user_setup.py` | Mint-and-render on enrollment | ✓ VERIFIED | `issued_recovery_codes = None`, `recovery_codes_template = ViewPageTemplateFile('recovery_codes.pt')`, mint call inside `handleSubmit`'s try block, `render()` override, conditional redirect (`if redirect_url is not None`) |
| `browser/forms/recovery_codes.pt` | One-time display template | ✓ VERIFIED | Renders raw (unformatted) codes via `tal:repeat="code view/issued_recovery_codes"`, carries a prominent shown-once warning, all strings `i18n:translate` |
| `profiles/default/actions.xml` | `regenerate_recovery_codes` action | ✓ VERIFIED | Present in `user` category, reuses `@@show-disable-two-factor-authentication-link` |
| All 8 new test methods across `test_token.py`, `test_helpers.py`, `test_user_setup.py`, `test_generic.py` | Substantive, non-vacuous | ✓ VERIFIED | All 8 confirmed present by line, read in full; none are placeholder assertions — each carries multi-scenario, non-vacuity-controlled coverage |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `token.py:113` | `helpers.validate_second_factor` | direct call, single site | ✓ WIRED | Sits between `reset_failed_second_factor`/`register_failed_second_factor`, both untouched from Phase 5; counted-assertion test guards against a future second call site |
| `user_setup.py` (regeneration action target) | `generate_recovery_codes` | `handleSubmit`'s try block | ✓ WIRED | but gated only by a bare `validate_token(token)` with **no lockout wiring** — see CR-01 below |
| `actions.xml`'s `available_expr` | `@@show-disable-two-factor-authentication-link` | portal action | ✓ WIRED | confirmed the view exists in `settings_helper.py`/`configure.zcml` and is asserted explicitly by `test_regenerate_recovery_codes_action_is_registered` |
| `pas_plugin.py`/`subscribers.py` | (absence of) 5 new writer names | MFA-12 source guard | ✓ WIRED | `test_no_second_factor_state_written_from_the_plugin` extended with all 5 new names, both as absence checks and pinned per-file positive controls; reproduced red per SUMMARY (mutation into `pas_plugin.py`, then `subscribers.py`, then a wrong-file positive control — all failed as expected, then restored byte-identical) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| RECOV-01 | 06-02 | 10 codes, 16 base32 chars, shown once | ✓ SATISFIED | See Truth #1 |
| RECOV-02 | 06-01 | Hashed, one salt/user, plaintext never stored | ✓ SATISFIED | `test_recovery_code_storage_and_validation_edges` |
| RECOV-03 | 06-02 | Never redisplayed | ✓ SATISFIED (WR-03 noted) | See Truth #1; WR-03 below notes the assertion is against the raw form instance, not the registered wrapped view |
| RECOV-04 | 06-01 | Accepted in place of TOTP, consumed on use | ✓ SATISFIED | `test_recovery_code_is_accepted_in_place_of_a_token_and_consumed` |
| RECOV-05 | 06-03 | Shares the TOTP failure counter | ✓ SATISFIED | `test_recovery_code_failure_shares_the_totp_lockout_counter` |
| RECOV-06 | 06-02 | Regenerate whole set, invalidate previous | ✓ SATISFIED (CR-01 caveat) | `test_recovery_code_regeneration_invalidates_the_previous_set`, `test_regenerate_recovery_codes_action_is_registered`; **but see CR-01** — the sole security gate on reaching this regeneration path is an unthrottled TOTP check |
| RECOV-07 | 06-03 | Warn at ≤3 remaining | ✓ SATISFIED | `test_low_recovery_code_count_warning` |

All 7 RECOV-01..07 requirement IDs are declared across the three plans' frontmatter (`requirements: [RECOV-02, RECOV-04]`, `[RECOV-01, RECOV-03, RECOV-06]`, `[RECOV-05, RECOV-07]`) and cross-referenced against REQUIREMENTS.md — no orphaned RECOV requirement exists.

### Anti-Patterns Found

None of the mechanical grep categories (TBD/FIXME/XXX, TODO/HACK/PLACEHOLDER, empty returns, hardcoded-empty props) were found in this phase's modified files beyond pre-existing, out-of-scope `bin/code-analysis` isort debt already documented in CLAUDE.md/06-02-SUMMARY.md.

One finding surfaced by reading the code directly (not a mechanical grep pattern, so it does not trip Step 7's automatic gate, but is real and confirmed):

### CR-01 (carried from 06-REVIEW.md, confirmed unresolved in HEAD)

`browser/forms/user_setup.py:94` — `SetupForm.handleSubmit` validates the submitted code with a bare `validate_token(token)` call. Unlike `token.py` (the login gate, which checks `is_account_locked` before validating and calls `register_failed_second_factor`/`reset_failed_second_factor` on the outcome) and `reset_bar_code.py` (05-03's reset gate, same shape), `user_setup.py` imports none of `is_account_locked`, `register_failed_second_factor`, `reset_failed_second_factor` — confirmed by direct grep against the file (zero matches).

This matters specifically for this phase because `actions.xml`'s own comment names this exact, unthrottled TOTP check as the **sole security gate** for `regenerate_recovery_codes`: "that form validates a currently valid TOTP code before it writes." An account reachable with only a password (pre-enrollment, or after a self-service disable that leaves the seed intact) lets an attacker submit unlimited six-digit guesses at `@@setup-two-factor-authentication` with zero rate limiting — a 1,000,000-value keyspace with no throttling — to both seize the TOTP association and mint a fresh, durable, TOTP-independent set of 10 recovery codes that outlives a later password change.

This is **not a fresh Phase 6 regression** — the missing lockout wiring in `user_setup.py` predates this phase (05-03 wired `reset_bar_code.py` but never `user_setup.py`) — but Phase 6 materially raises the stakes by making this exact unthrottled check the gate for minting a persistent backdoor credential. No `must_haves.truth` in any of the three 06-0x-PLAN.md files, and no ROADMAP success criterion, explicitly requires this endpoint to be rate-limited, so this does not mechanically FAIL any of the phase's 5 stated success criteria — hence it is not treated as a BLOCKER here. But it is a confirmed, unresolved CRITICAL finding in this phase's own code review (`06-REVIEW.md`, `status: issues_found`), with no follow-up fix commit in the branch (`git log` shows `a6b06ec` — the review commit itself — as HEAD; no subsequent commit touches `user_setup.py`'s lockout wiring).

**Routed to human verification** rather than either silently passing or unilaterally blocking, since accepting or fixing this is a risk/scope judgment call, not a mechanical check.

Other 06-REVIEW.md findings (not re-litigated here as blockers, since none are must-haves in the PLAN frontmatter, but worth carrying forward):
- **WR-01**: an exception inside `generate_recovery_codes` leaves `enable_two_factor_authentication=True` with zero recovery codes stored, while the earlier "successfully enabled" status message has already been queued alongside the later "Setup failed!" message — a contradictory pair shown to the user. Confirmed present in `user_setup.py:106-124` (the success message precedes the mint call inside the same `try`).
- **WR-02**: no GenericSetup upgrade step exists for the two new memberdata properties, so a site upgraded in place (rather than freshly installed) will silently drop both new properties on `setMemberProperties` per this project's own documented "undeclared properties are silently popped" hazard. This repeats the same open gap Phase 5 left for its own three properties.
- **WR-03**: RECOV-03's "shown once" guarantee is asserted only against the raw `SetupForm` instance (`.render()` called directly), never through the actually-registered `SetupFormView = wrap_form(SetupForm)` view a real browser request reaches; a future `plone.z3cform` pin bump could silently break the mechanism with no test failing.

None of WR-01/02/03 are must-haves in the PLAN frontmatter and none contradict a stated ROADMAP success criterion, so they are recorded here as carried-forward context rather than gaps of this verification.

### Test Suite

`bin/test -t '!robot'` run directly by this verifier: **98 tests, 0 failures, 0 errors** (94 integration + 4 unit), matching all three SUMMARY.md claims. All 8 new recovery-code test methods individually confirmed present and passing:
- `test_token.py`: `test_recovery_code_is_accepted_in_place_of_a_token_and_consumed`, `test_recovery_code_failure_shares_the_totp_lockout_counter`, `test_low_recovery_code_count_warning`, `test_second_factor_dispatch_has_exactly_one_call_site_per_outcome` (11 tests in file, 0 failures)
- `test_helpers.py`: `test_recovery_code_storage_and_validation_edges`, `test_recovery_code_regeneration_invalidates_the_previous_set`
- `test_user_setup.py`: `test_recovery_codes_are_issued_once_at_enrollment` (plus `test_handleSubmit`'s 5 scenarios)
- `test_generic.py`: `test_regenerate_recovery_codes_action_is_registered`
- `test_adapter.py`: `LOCKOUT_STATE_PROPERTIES` extended with both new property names, exercised by the existing guard tests
- `test_pas_plugin.py`: `test_no_second_factor_state_written_from_the_plugin` extended with all 5 new writer names, restructured positive controls

All test bodies read in full and confirmed non-vacuous (real multi-scenario assertions, explicit non-vacuity controls, fixture guards against accidentally-valid test codes) — none are placeholder or tautological assertions.

### Human Verification Required

### 1. CR-01 risk-acceptance decision

**Test:** Read `06-REVIEW.md`'s CR-01 finding and this report's CR-01 section above; decide whether to (a) plan and execute a follow-up fix wiring `is_account_locked`/`register_failed_second_factor`/`reset_failed_second_factor` into `user_setup.py`'s `handleSubmit` (mirroring `reset_bar_code.py`), or (b) explicitly accept and record the residual risk before Phase 6 is closed and Phase 7 begins.
**Expected:** A recorded decision either way — not silence.
**Why human:** This is a scope/risk-acceptance call. No must-have in any 06-0x-PLAN.md and no ROADMAP success criterion for Phase 6 mandates rate-limiting this endpoint, so it cannot be mechanically failed; but it is a confirmed, currently-unaddressed CRITICAL finding directly touching RECOV-06's regeneration mechanism, which only a human can weigh against the package's 1-2 year lifespan and threat model.

### Gaps Summary

No must-have truth, artifact, or key link failed. All 5 ROADMAP success criteria and all 7 RECOV-01..07 requirements are backed by real, substantive, passing tests that were read in full and independently re-run (98/98 green). The one open item is CR-01 — an unresolved, confirmed CRITICAL code-review finding that does not mechanically falsify any stated success criterion but represents a genuine security gap in the sole gate protecting RECOV-06's regeneration path, and is routed to human decision rather than silently passed or used to block the phase outright.

---

*Verified: 2026-08-04T08:03:21Z*
*Verifier: Claude (gsd-verifier)*
