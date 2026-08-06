---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Enrollment Control and Account Safety
current_phase: 09
current_phase_name: Mail Path and Profile-Page Correctness
status: executing
stopped_at: Completed 09-03-PLAN.md
last_updated: "2026-08-06T12:50:11.425Z"
last_activity: 2026-08-06
last_activity_desc: Phase 09 execution started
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 4
  completed_plans: 3
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-06)

**Core value:** A second factor that actually holds for in-site users, and that can be deployed alongside `imio.dms.mail` without colliding with it.
**Current focus:** Phase 09 — Mail Path and Profile-Page Correctness

## Current Position

Phase: 09 (Mail Path and Profile-Page Correctness) — EXECUTING
Plan: 4 of 4
Status: Ready to execute
Last activity: 2026-08-06 — Phase 09 execution started

Progress: [████████░░] 75% of v1.1

## Performance Metrics

**Velocity:**

- Total plans completed: 30 (all v1.0)
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 2 | - | - |
| 03 | 3 | - | - |
| 04 | 4 | - | - |
| 05 | 5 | - | - |
| 06 | 3 | - | - |
| 07 | 4 | - | - |
| 08 | 5 | - | - |
| 09 | 0 | - | - |

**Recent Trend:**

- Last 5 plans: 25min, 35min, ~20min, ~2h, 35min (Phase 8)
- Trend: Stable

*Updated after each plan completion. The full 30-row per-plan table from v1.0 is preserved in
git history and in each phase's `*-SUMMARY.md`; it was collapsed here at the v1.1 roadmap so
this file stays a digest.*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 09 P01 | 25min | 2 tasks | 2 files |
| Phase 09 P02 | 20min | 1 tasks | 2 files |
| Phase 09 P03 | 25min | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Full log: PROJECT.md Key Decisions table (44 entries). Kept here only where a v1.1 phase has to
build on the decision rather than merely know it happened.

- **[Phase 2 → all]** `get_ska_secret_key()` is a pure read that raises `ValueError` on an empty
  key. There is no lazy mint. Anything reached from an abortable request path must not mint.

- **[Phase 4 → Phase 10]** `authenticateCredentials` decides only; the redirect is issued by an
  `IPubBeforeCommit` subscriber and by `IChallengePlugin.challenge`. The login-form POST returns
  HTTP 200 and never raises, so any Phase 10 enforcement at login has to cover both paths.

- **[Phase 5 → Phases 10, 11]** All second-factor state writes happen inside a committing view,
  never in the PAS plugin. Pinned by the source-grep test
  `tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin`, which lists
  property names and helper function names per file — extend it, don't route around it.

- **[Phase 5 → Phase 10]** The replay and lockout counters are memberdata properties with **no**
  `IEnhancedUserDataSchema` field. Declaring internal state on that schema crashes
  `@@user-information` (no accessor in `adapter.py`) and makes it form-writable.

- **[Phase 6 → Phase 9 UX-01]** `user_setup.py` leaves `redirect_url = None` on the success path
  on purpose — the one-time recovery-code display depends on the response *not* being a 302.
  `plone.z3cform` 0.8.1 blanks the wrapped form only on 302/303.

- **[Phase 7 → all]** No skin layer, no vendored JS, no resource this package does not own. An
  invariant test fails the day a foreign resource id appears.

- **[Phase 8 → all]** `bin/code-analysis` exits 0 and the pre-commit hook passes without
  `--no-verify`. CI runs `bin/test-coverage -t '!robot'` with `--fail-under=90`.

- **[Phase 9 → Phase 12]** BUG-07: widened `request_bar_code_reset.py`'s mail-send catch to
  `(SMTPException, socket.error)`, deleted the re-raise, and moved the success `IStatusMessage`
  call inside the inner `try:` so a send failure cannot also fire the success message. This is
  the failure shape Phase 12's three additional senders should copy.

- **[Phase 9 → Phase 13]** BUG-08: removed both wrong-account links from
  `enable_two_factor_authentication`'s description outright rather than making it conditional —
  the field is the only renderer on `@@user-information`, and a static schema description cannot
  vary per viewer without real machinery (D-14). The shortened description orphans the old msgid
  in the `.po`/`.pot` catalogues, accepted as a Phase 13 (I18N-02) input, not fixed here (D-16).

- [Phase ?]: UX-01: resolved the home-page URL through context/@@plone/navigationRootUrl inside recovery_codes.pt, not the globals_view/navigationRootUrl idiom actions.xml uses -- globals_view is bound only by main_template's global_defines / the CMF action-expression context, and this template renders standalone with no metal:use-macro, so that name would raise a TAL NameError. @@plone is the same view, verified by re-running form.render() and confirming no TAL error plus the correct resolved href.
- [Phase ?]: UX-02: get_token_description() now calls get_or_create_secret exactly once and reuses the value for both the QR and the appended <code> text -- confirmed by source inspection, satisfying D-08 and mitigating T-09-05 (minting/rotating a seed as a display side effect).

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- **Now mapped, was open — Phase 9 (BUG-07):** `browser/forms/request_bar_code_reset.py:112-113`
  catches `SMTPRecipientsRefused` and re-raises the same exception type, which the enclosing
  `except ValueError` cannot catch. Those two lines are uncovered. Phase 12 adds three more
  senders to this path, so it is fixed first.

- **Now mapped, was open — Phase 10 (MFA-15..19, was MFA-14):** `globally_enabled` does not
  enroll accounts that existed when the add-on was installed. The login gate reads each user's
  own `enable_two_factor_authentication` flag, never the global setting;
  `setuphandlers.setupVarious` enrolls nobody; only saving the control panel form enrolls anyone.
  Confirmed on a real two-egg environment 2026-08-05. Bulk enrollment also mints a seed without
  ever showing a QR code, which is why MFA-19 ships in the same phase.

- **Phase 10 / Phase 11 (from 04-SECURITY.md R-04-C):** do not attach lockout or replay state to
  the `send_2fa_redirect` call chain. It is write-free in its own body but reaches
  `sign_user_data` → `get_or_create_secret`, which writes a memberdata seed for a 2FA-enabled
  user who has none. Relevant because Phase 10 changes who reaches that path.

- **Phase 10 (from 04-REVIEW.md WR-01/WR-02):** for a user with 2FA enabled but no stored seed, a
  broken or missing `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` raises inside `send_2fa_redirect` rather
  than synchronously in `authenticateCredentials`, giving an uncontrolled error page instead of a
  clean refusal. Still fail-closed, no bypass. Phase 10 creates exactly this state — enrolled by
  the global setting, no seed yet — so it is now on the critical path.

- **Phase 13 (lint):** `flake8-isort` 4.0.0 reports findings from a diff, so a file's finding
  count shifts when any line in it changes. Check error codes, not per-file counts.

- **External, blocks deployment not development:** the `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`
  `concat::fragment` lives in the separate `industrialisation` repo and has not shipped.
  `base.cfg:54` sets it for `[testenv]` only. Nothing in v1.1 can close this.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260805-f5m | Guard userCreatedHandler against absent settings records (COEX-10) | 2026-08-05 | 184f053 | [260805-f5m-guard-usercreatedhandler-against-absent-](./quick/260805-f5m-guard-usercreatedhandler-against-absent-/) |
| 260806-fsp | Wire the lockout counter into the enrollment form's TOTP check — closes 06-REVIEW.md CR-01 (CRITICAL) / v1.0 audit Gap 1 | 2026-08-06 | 8acfd42 | [260806-fsp-wire-lockout-counter-into-enrollment-for](./quick/260806-fsp-wire-lockout-counter-into-enrollment-for/) |
| 260806-gfr | Widen the uninstall profile to reverse the PAS plugin, local utility, actions, browser layer, configlet and registry records — closes v1.0 audit Gap 2 (COEX-06) | 2026-08-06 | 29fbeff | [260806-gfr-widen-the-uninstall-profile-to-reverse-w](./quick/260806-gfr-widen-the-uninstall-profile-to-reverse-w/) |

## Deferred Items

Deferred by explicit decision at the v1.0 close, 2026-08-06. Full detail in
`.planning/MILESTONES.md` and `.planning/milestones/v1.0-MILESTONE-AUDIT.md`. The two entries
that v1.1 picks up are now mapped to phases and repeated under Blockers above.

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| requirement | MFA-14 — `globally_enabled` does not enroll pre-existing accounts | **Mapped to Phase 10** as MFA-15..MFA-19 | 2026-08-06 |
| bug | Rejected recipient address crashes the bar-code reset email path | **Mapped to Phase 9** as BUG-07 | 2026-08-06 |
| tech debt | Bulk enrollment mints seeds but shows nobody a QR code | **Mapped to Phase 10** as MFA-19 | 2026-08-06 |
| tech debt | Turning `globally_enabled` off enrolls nobody out (disable call commented out) | Open — Future Requirement, deliberately not in v1.1 | 2026-08-06 |
| missing artifact | No `07-SECURITY.md` for Phase 7 | Accepted | 2026-08-06 |
| verification | Six Phase 5 claims marked "backstop" — real ZEO multi-client counters, live control-panel round trip, real mobile clock drift, proxy byte-equality at two endpoints | Unprovable in-process; accepted | 2026-08-06 |
| verification | Nyquist validation records phases 5 through 8 as not-validated | Accepted | 2026-08-06 |
| deployment | Puppet `concat::fragment` for the seed key not shipped (`industrialisation` repo) | Blocking real deployment | 2026-08-06 |
| tech debt | Username-enumeration oracle at `request_bar_code_reset.py` | Accepted low severity (T-03-26) | 2026-08-06 |
| tech debt | No operations owner has confirmed nothing uses HTTP Basic Auth against this site's `acl_users` | Open; `README.rst` asks the deploying operator to check | 2026-08-06 |
| docs | `CLAUDE.md` states profile version `0301` / package `0.3.0`; actual values are `1000` and `1.0.0.dev0` | Open | 2026-08-06 |

## Session Continuity

Last session: 2026-08-06T12:50:11.413Z
Stopped at: Completed 09-03-PLAN.md
Resume file: None

## Operator Next Steps

- `/gsd-plan-phase 9` to plan the first v1.1 phase. Phase 9 has four independent corrections
  (BUG-07, BUG-08, UX-01, UX-02) and is the cheapest phase in the milestone.

- Five open questions are recorded at the end of `.planning/REQUIREMENTS.md` and are deliberately
  unanswered. Questions 4 and 5 must be settled before Phase 9 (question 4 decides whether UX-02
  stays in Phase 9 or moves to Phase 11); question 3 before Phase 10; questions 1 and 2 before
  Phase 11. `/gsd-discuss-phase` is where they get answered.

- Outside this repository: get the `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` `concat::fragment` shipped
  in `industrialisation`. Nothing here can be deployed until it is, and v1.1 does not change that.
