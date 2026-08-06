---
phase: 10-global-enforcement-and-enrollment
plan: 06
subsystem: auth
tags: [pas-plugin, plone, changelog, phase-gate, validation]

requires:
  - phase: 10-global-enforcement-and-enrollment
    provides: "plans 10-01 through 10-05's full implementation of MFA-15 through MFA-19 and all 18 decisions"
provides:
  - "The merged phase result run and reported honestly: full suite, branch coverage, lint, all real numbers"
  - "CHANGES.rst entry naming MFA-15 through MFA-19, the four operator-facing consequences"
  - "The 18-decision ledger (D-01..D-18), each traced to source, test, or residual"
  - "10-VALIDATION.md filled in: Per-Task Verification Map, Wave 0 Requirements, both Manual-Only Verifications recorded as blocked"
  - "Four deliberate residuals and two flagged planner assumptions recorded for the operator"
affects: []

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - CHANGES.rst
    - .planning/phases/10-global-enforcement-and-enrollment/10-VALIDATION.md

key-decisions:
  - "Both Manual-Only Verifications are recorded as blocked, not passed or failed. This execution environment has no operator and no IMIO_GOOGLEAUTHENTICATOR_SEED_KEY exported to bin/instance (base.cfg sets it for the [testenv] buildout part only) -- the same gap Phase 9 hit for its TOTP-client check and recorded rather than inferred around."
  - "status: validated set on 10-VALIDATION.md because every row is accounted for (green automated verify, or a recorded blocked outcome) -- not because every row was verified end to end. The frontmatter's own lifecycle note is read literally: 'validated' describes contract completeness, not universal pass."

patterns-established: []

requirements-completed: [MFA-15, MFA-16, MFA-17, MFA-18, MFA-19]

duration: ~40min
completed: 2026-08-06
status: complete
---

# Phase 10 Plan 06: The Merged Gate Summary

**The merged result of plans 10-01 through 10-05 is green on all three automated gates (165 tests / 0 failures / 0 errors, 92% branch coverage, `bin/code-analysis` exit 0, proven with a real commit and no `--no-verify`), the changelog names all five operator-facing consequences, all 18 phase decisions are traced to shipped source or a recorded residual, and both genuinely-manual verifications are recorded honestly as blocked rather than inferred as passed.**

## Performance

- **Duration:** ~40min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- Ran the three standing-constraint gates against the exact merged tree left by plan 10-05 (no
  source changes made in this plan) and recorded the real numbers below, matching what the
  orchestrator had independently verified before spawning this plan.
- Wrote the `CHANGES.rst` entry naming MFA-15 through MFA-19: install-time enrollment of
  pre-existing accounts with no seed and enrollment routing at next login; the self-disable and
  bulk-disable refusal while `globally_enabled` is on; the new internal
  `two_factor_authentication_enrolled` property (undeclared on the profile schema, survives
  uninstall); the enable-link/regenerate-link reachability guarantee; and the one surprising
  consequence for an account that was already enrolled before this phase ships — one more
  enrollment page, and a fresh set of recovery codes that invalidates the previous set.
- Made that changelog commit with no `--no-verify`, proving `bin/code-analysis`'s git pre-commit
  hook still passes over the merged phase result — the property Phase 8 plan 08-05 established
  and which CI does not check on its own.
- Filled in `10-VALIDATION.md`'s Per-Task Verification Map (Task ID / Plan / Wave for all eleven
  rows), ticked all three Wave 0 Requirements with the plan that closed each, and recorded both
  Manual-Only Verifications as **blocked** — not passed, not skipped — with the specific reason
  and the step each stopped at.
- Wrote the 18-row decision ledger below, with the four decisions the plan flagged as needing a
  specific word (D-06, D-07, D-14, D-18) each stated in those words.

## Task Commits

Each task was committed atomically:

1. **Task 1: The merged gate — full suite, branch coverage, lint, and the decision ledger** - `100a201` (docs) — `CHANGES.rst`
2. **Task 2: The two verifications a test cannot make** - `7968ce9` (docs) — `10-VALIDATION.md`

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `CHANGES.rst` — one new entry under `1.0.0 (unreleased)` naming MFA-15 through MFA-19
- `.planning/phases/10-global-enforcement-and-enrollment/10-VALIDATION.md` — Per-Task Verification
  Map filled in, Wave 0 Requirements ticked, both Manual-Only Verifications given a recorded
  outcome, frontmatter (`status`, `nyquist_compliant`, `wave_0_complete`) updated to match

## The Merged Gate — Real Numbers

- **`bin/test -t '!robot'`** → **165 tests, 0 failures, 0 errors** (28.1s functional layer + 0.003s
  unit layer). Matches the orchestrator's independently-verified figure exactly.
- **`bin/test-coverage -t '!robot'`** → **165 tests, 0 failures, 0 errors**; **92% branch coverage**
  overall (`TOTAL 1171 67 322 51 92%`), above the 90% CI floor. No file this phase touched dropped
  below its own plan's recorded figure (`browser/settings_helper.py` 100%,
  `browser/disable_two_factor_authentication.py` 100%,
  `browser/disable_two_factor_authentication_for_all_users.py` 100%, `setuphandlers.py` 100%,
  `pas_plugin.py` 81% — unchanged from plan 10-05's own report, its uncovered lines pre-existing
  and unrelated to this phase).
- **`bin/code-analysis`** → exit 0 (Flake8 OK). A real `git commit` (the `CHANGES.rst` commit,
  `100a201`) ran with no `--no-verify` and passed the buildout's git pre-commit hook, which invokes
  this same command.
- **The foreign-resource invariant** (`test_no_restrictedTraverse_left_in_browser_code`,
  `tests/test_generic.py`, COEX-04) is part of the 165-test full-suite run above and passed. This
  phase registered one new `browser:page` (`disable-two-factor-authentication-for-all-users` was
  pre-existing; the new registrations are `show-regenerate-recovery-codes-link` and the
  `@@setup-two-factor-authentication` sessionless-resolution path, neither a skin or
  resource-registry override) and changed one `actions.xml` property
  (`regenerate_recovery_codes`'s `available_expr`) — neither is a resource this package does not
  own, and the invariant test proves that rather than leaving it as an argument.

## The 18-Decision Ledger

| Decision | Traced to |
|---|---|
| D-01 | Source: `setuphandlers.setupVarious` calls `_enroll_existing_users()` (plan 10-01). Test: `test_install_enrolls_every_pre_existing_account_without_a_seed`, `test_install_enrolls_nobody_when_globally_enabled_is_off` (plan 10-02). |
| D-02 | Source: `_enroll_existing_users` sets the flag only, never calls `get_or_create_secret` (plan 10-01). Test: same `test_install_enrolls_every_pre_existing_account_without_a_seed` asserts no seed minted, with `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` removed from the environment for the duration (plan 10-02). |
| D-03 | Source: `pas_plugin.authenticateCredentials` reads only `has_completed_enrollment(user)`, never the global setting, to decide routing (plan 10-01). Test: `test_no_second_factor_state_written_from_the_plugin`'s scope and the routing test `test_routing_decision_reads_enrollment_completion_not_seed_presence` (plan 10-05) both pin this by never consulting `is_two_factor_authentication_globally_enabled()` in that read. |
| D-04 | Source: no swallowing added to `_enroll_existing_users`; the plain per-user write is left to raise (plan 10-01). Test: `test_install_enrollment_reports_a_failure_instead_of_partially_enrolling`, which also settles RESEARCH.md's open assumption A1 — the exception propagates unswallowed through `Products.GenericSetup`'s import-step runner and out of `applyProfile` (plan 10-02). |
| D-05 | Source: `REQUEST_KEY_ENROLLMENT_NEEDED` / `_mark_2fa_pending`'s new parameter, read in `authenticateCredentials` before any URL is signed, consumed by `send_2fa_redirect`'s target-URL selection (plan 10-01). |
| D-06 | **Settled as D-17, mechanism (b).** Mechanism (a) — signing an enrollment URL for a user with no seed — was **rejected**: `sign_user_data` calls `get_or_create_secret(user)` unconditionally, because the user's seed supplies the per-user entropy in the `ska` signing key; removing it would collapse that key to a browser hash plus a site-wide secret shared across every unenrolled user, and bounding that risk would require auditing the pinned `ska 1.7.5` library's internals — out of proportion to declaring one property. Recorded so a future reader does not reopen this as an "optimisation." |
| D-07 | **Scoped in against RESEARCH.md's advice that the phase need not fix the pre-existing 500.** Source: `helpers.is_seed_encryption_available()` + the refusal in `authenticateCredentials`, gated on `enrollment_needed`, between the existing `get_secret(user)` call and `_mark_2fa_pending` (plan 10-05). Test: `test_missing_seed_encryption_key_refuses_cleanly_for_a_seedless_enrolled_user` (both the absent-key and malformed-key shapes). **Closed:** a missing or malformed key on the seedless-enrolled login path (the state install-time bulk enrollment creates at scale) now refuses synchronously in `authenticateCredentials` instead of raising inside `send_2fa_redirect`. **Not closed:** the aborted-transaction seed mint on the `challenge()` path (see Residual 1 below) — that is a different call chain (`IChallengePlugin.challenge` → `send_2fa_redirect` → `sign_user_data` → `get_or_create_secret`), pre-existing, and out of this decision's scope. |
| D-08 | Source: `browser/disable_two_factor_authentication.py`'s `disable()` refuses (error message, redirect to `@@personal-information`) when `globally_enabled` is on, before any read of the caller's own member data (plan 10-03). Test: `test_disable_is_refused_while_globally_enabled_and_mutates_nothing`, `test_disable_is_refused_for_an_unenrolled_user_too`. |
| D-09 | Source: an in-source comment in `disable_two_factor_authentication.py` recording that hiding the menu link is not the control, citing Phase 9's BUG-08 mirror (plan 10-03); `settings_helper.py`'s D-10/D-11 conditions (plan 10-04) are the "hide for tidiness" half. |
| D-10 | Source: `show_enable_two_factor_authentication_link` returns `not has_completed_enrollment(user)` with no global-setting term (plan 10-04), deliberately deviating from RESEARCH.md's recommended `not has_enabled_two_factor_authentication` shape — recorded in-source so an install-enrolled user is never hidden from the enable link. Test: `test_enable_link_is_offered_to_a_user_who_has_not_completed_enrollment`, `test_enable_link_is_offered_whatever_the_global_setting_says`. |
| D-11 | Source: `show_disable_two_factor_authentication_link` returns `has_enabled_two_factor_authentication(user) and not is_two_factor_authentication_globally_enabled()` (plan 10-04). Test: `test_disable_link_is_offered_only_when_enrolled_and_globally_disabled`. |
| D-12 | **Implementer's discretion, exercised.** Two new `MessageFactory('imio.googleauthenticator')` msgids — the self-disable refusal and the bulk-disable refusal — neither names another account; the self-disable message speaks only of "this site" and "your own" account, the bulk message speaks only of "all users" as a class (plan 10-03). Both are new translatable strings and a **Phase 13 input**, not translated by this phase (see Residual 3 / the objective's explicit exclusion). |
| D-13 | Source: install-time enrollment runs inside `setupVarious`'s existing marker-gated block, so it is gated on `imio.googleauthenticator.marker.txt` like the rest of that function, and `_enroll_existing_users`'s own `has_enabled_two_factor_authentication` guard makes re-application a no-op (plan 10-01). Test: `test_install_enrollment_is_idempotent_across_two_profile_applications` (plan 10-02) — non-vacuity required a stronger mutation than "delete the call" because that mutation passes vacuously for a no-change assertion; escalated to reintroducing unconditional seed minting, which correctly turned the test red. |
| D-14 | **Finding, not a change.** `browser/disable_two_factor_authentication_for_all_users.py` is a live, ungated site-wide un-enroll view — confirmed by direct read at 31 lines, no `globally_enabled` check anywhere before this phase. Recorded as found; D-18 is what acted on it (plan 10-03). |
| D-15 | Source: new `show_regenerate_recovery_codes_link` method, keyed on `has_completed_enrollment` with no global-setting term; `profiles/default/actions.xml`'s `regenerate_recovery_codes` action repointed at it instead of reusing the disable link's condition, with the reuse-explaining comment rewritten (plan 10-04). Test: `test_regenerate_link_survives_global_enforcement`, `test_every_settings_combination_leaves_enrollment_reachable` (the criterion-5 matrix), `test_regenerate_recovery_codes_action_is_registered` (updated in `test_generic.py`). |
| D-16 | Source: `SetupForm._resolve_signed_user()` and `action()` (query-string-preserving), mirroring `token.py`'s `auth_user`/`validate_user_data`/`_setupSession` mechanism for the enrollment view (plan 10-01). Test: the tracer's own install→login→QR→code test, `test_enrollment_page_refuses_an_unresolvable_or_absent_auth_user`, and `test_enrollment_page_refuses_an_invalid_signature` (plan 10-05, the resolvable-but-tampered variant). |
| D-17 | **Settled in favour of mechanism (b): a new member-data property.** Source: `two_factor_authentication_enrolled` declared in `memberdata_properties.xml`, `has_completed_enrollment`/`mark_enrollment_completed` its only reader/writer, no schema field, no adapter accessor (plan 10-01). Test: `test_enrollment_completion_property_round_trips_as_a_bool` (`INTERNAL_MEMBERDATA_PROPERTIES`, renamed from `LOCKOUT_STATE_PROPERTIES`, plan 10-05) proves the round trip, schema absence, and `portal_memberdata` presence together — `hasProperty` alone is not a round trip. |
| D-18 | **Operator-approved widening beyond MFA-16's literal wording, decided 2026-08-06.** MFA-16 speaks only of "a user's own second factor"; D-18 extends the same `globally_enabled` refusal to the site-wide un-enroll view found as D-14, because shipping a refusal that stops one user turning their own second factor off while leaving a one-click "disable for everyone" reachable makes the enforcement incoherent. Source: the identical guard as `index()`'s first statement in `disable_two_factor_authentication_for_all_users.py`, with an in-source comment recording the date and reasoning (plan 10-03). Test: `test_disable_for_all_users_is_refused_while_globally_enabled`, `test_disable_for_all_users_on_an_empty_user_list`. Recorded here explicitly so a verifier reading the requirement text does not read plan 03's second view as unplanned work. |

## Residuals (four, all deliberate)

1. **The seed minted while signing an enrollment redirect is discarded on the `challenge()` path.**
   That transaction is already aborted, so a first-time enrollee reached that way sees a refusal
   and must retry through the login form. Pre-existing behaviour described in `subscribers.py`;
   reached more often now that install-time enrollment creates more seedless-enrolled accounts.
   Threat register: T-10-26, disposition `accept`.
2. **`browser/controlpanel.py`'s commented-out bulk-disable call stays commented out.** STATE.md's
   open Future Requirement; this phase gates the *existing* bulk-disable view (D-18) but does not
   build the disable-everyone-out-at-once feature the commented block would have been. Threat
   register: T-10-27, disposition `accept`.
3. **Refusing a mismatched `userid` at `@@setup-two-factor-authentication` and
   `@@disable-two-factor-authentication` is still a Future Requirement, carried over from Phase 9.**
   Plan 10-03 makes the disable view look editable again without adding this refusal — a decision,
   not an oversight. Threat register: T-10-28, disposition `accept`.
4. **The `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` Puppet fragment still has not shipped** from the
   separate `industrialisation` repository. Nothing in this phase changes that, and it remains what
   stands between code-complete and deployable — it is also the direct cause of both Manual-Only
   Verifications below being recorded as blocked. Threat register: T-10-29, disposition `transfer`.

## Two Flagged Planner Assumptions (open questions for the operator, not resolved)

Both are recorded in plan 10-04's own frontmatter as `EDGE-MFA-17-unclassified` and
`EDGE-MFA-18-unclassified`, and restated here as open rather than settled:

1. **MFA-17's "from their own profile"** — does this requirement mean only the portal-action
   surface `settings_helper.py`/`actions.xml` drives (what this phase implements), or does it also
   include the `@@personal-information` schema-field surface that Phase 9/BUG-08 emptied? This
   phase's work covers the former only.
2. **MFA-18's "reachable"** — does this requirement extend to an anonymous or non-site-local
   account (e.g. the Zope-root account, which plan 10-02 proved install deliberately does not
   enrol), or is it scoped to ordinary site-local accounts only? This phase's work assumes the
   latter.

If a future reviewer determines either reading was meant more broadly, `settings_helper.py` and
`actions.xml` as they stand today would need revisiting — not a gap this phase introduces, but one
it did not have the mandate to resolve on its own.

## Decisions Made

See `key-decisions` in frontmatter: both concern how the two Manual-Only Verifications are recorded
(blocked, not passed) and why `10-VALIDATION.md`'s `status` is set to `validated` despite that.

## Deviations from Plan

None — plan executed exactly as written. No source code was touched; this plan is the gate, not a
build step, and the merged result left by plans 10-01 through 10-05 already satisfied every
automated acceptance criterion without further change.

## Issues Encountered

None. The three automated gates reproduced the orchestrator's independently-verified figures
exactly (165 tests / 0 failures / 0 errors; 92% branch coverage; `bin/code-analysis` exit 0) on the
first run of each, with a clean working tree at the start.

## User Setup Required

None beyond what is already recorded as Residual 4 above and in both blocked Manual-Only
Verifications: a real Plone 4.3 instance with `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` exported and an
operator to drive a browser through enrollment. Neither is available in this execution
environment.

## Manual Verification Outcomes

Both recorded in `10-VALIDATION.md`'s Manual-Only Verifications table, reproduced here per this
plan's own acceptance criteria:

1. **A real install onto a populated site (MFA-15 + MFA-19, criteria 1 and 2).** **BLOCKED.**
   `base.cfg:54` sets `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` for the `[testenv]` buildout part only;
   confirmed absent from this execution shell's environment (`env | grep
   IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` → no output). There is no running, populated Plone 4.3
   instance and no operator or browser available in this session. Stopped before step 1 — same
   precedent Phase 9 set for its manual TOTP-client check, recorded as blocked rather than assumed.
2. **The four-way settings matrix confirmed by judgement (MFA-18, criterion 5).** **BLOCKED** for
   the judgement half. The automatable half is green:
   `test_every_settings_combination_leaves_enrollment_reachable` (plan 10-04) proves all four
   cells (`globally_enabled` × enrollment-completed) resolve to at least one rendered portal
   action pointing at `@@setup-two-factor-authentication`, via `portal_actions.listActionInfos()`
   — not just the booleans feeding `available_expr`. The judgement that a real user in each state
   can actually *complete* enrollment, not merely be offered a link, needs the same running site
   and human as verification 1 and was not attempted for the same reason.

Neither verification is described as automated anywhere in this phase's artifacts. A partial
result recorded honestly is worth more than a claim.

## Non-vacuity checks (mandatory, project convention since Phase 1)

Not applicable to this plan — no new test was written and no production code was changed. The
non-vacuity discipline was exercised by plans 10-01 through 10-05 for every test this phase added;
this plan only re-ran the resulting suite and coverage gate as a whole.

## Known Stubs

None.

## Threat Flags

None new. This plan closes the register's remaining `accept`/`transfer` rows (T-10-26 through
T-10-29) as residuals rather than gaps — see the Residuals section above. Every `mitigate`-
disposition threat from plans 10-01 through 10-05 was already confirmed shipped by each plan's own
SUMMARY before this gate ran.

## Next Phase Readiness

- Phase 10 is complete: all five ROADMAP success criteria have either a green automated test or a
  recorded manual outcome (two blocked, not inferred), all 18 decisions are traced, and the three
  standing constraints this phase could have broken (coverage, lint, no foreign-resource mutation)
  are all green over the merged result.
- Phase 11 (Re-authentication Before MFA Changes) can proceed: it depends on Phase 10 rewriting
  the reachability and outcome of the same three actions (enable, disable, regenerate) it is about
  to gate, and that rewrite is now settled, not provisional.
- Both blocked Manual-Only Verifications remain open items for whoever has access to a real,
  seed-keyed Plone 4.3 instance and an operator — not blockers to Phase 11's start, since Phase
  11's own scope does not depend on either verification's outcome.

## Self-Check: PASSED

Confirmed present on disk: `CHANGES.rst` (modified, contains the MFA-15..19 entry) and
`.planning/phases/10-global-enforcement-and-enrollment/10-VALIDATION.md` (modified, `status:
validated`), and this SUMMARY.md. Confirmed present in `git log --oneline --all`: `100a201` (the
`CHANGES.rst` commit) and `7968ce9` (the `10-VALIDATION.md` commit).

---
*Phase: 10-global-enforcement-and-enrollment*
*Completed: 2026-08-06*
