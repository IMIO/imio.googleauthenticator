---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_phase_name: rename-and-fail-closed
status: executing
stopped_at: Completed 01-01-PLAN.md
last_updated: "2026-07-28T14:40:10.901Z"
last_activity: 2026-07-28
last_activity_desc: Phase 01 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 4
  completed_plans: 1
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-28)

**Core value:** A second factor that actually holds for in-site users, and that can be deployed alongside `imio.dms.mail` without colliding with it.
**Current focus:** Phase 01 — rename-and-fail-closed

## Current Position

Phase: 01 (rename-and-fail-closed) — EXECUTING
Plan: 2 of 4
Status: Ready to execute
Last activity: 2026-07-28 — Phase 01 execution started

Progress: [███░░░░░░░] 25%

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
**Per-Plan Metrics:**

| Plan | Duration | Tasks | Files |
|------|----------|-------|-------|
| Phase 01 P01 | 10min | 2 tasks | 40 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Encryption is sequential Phase 3, not a parallel workstream (`parallelization: false`), placed early for the out-of-repo Puppet lead time and after Phase 2 because the key is read on a path the registry seeding bug destabilises.
- [Roadmap]: `_dont_swallow_my_exceptions = True` lands in Phase 1, not the encryption phase — it converts every later phase's mistakes from silent 2FA bypasses into 500s.
- [Roadmap]: PROJECT.md reversed the QR decision to `qrcode == 6.1`, so `imio.helpers` is no longer pulled into `install_requires`. Phase 1 carries the research-named substitute: an explicit two-package import check for the `imio` namespace declaration.
- [Roadmap]: 71 v1 requirements, not 61 — REQUIREMENTS.md's coverage count was a miscount and has been corrected.
- [Phase ?]: 01-01: Three-commit shape for the move (pure move / buildout regen / content rename), per CONTEXT.md commit-shape decision
- [Phase ?]: 01-01: PAS_ID, meta_type, PAS_TITLE left untouched — plan 01-04 owns them in an isolated commit
- [Phase ?]: 01-01: locales/** filenames and rebuild_i18n.sh I18NDOMAIN left untouched — plan 01-02 owns D-15

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- **External, Phase 3:** the encryption-key `concat::fragment` lives in the separate `industrialisation` repo. Not one of this roadmap's commits. Phase 3 code is testable without it; the feature is not deployable until it ships.
- **Phases 1–7:** `bin/code-analysis` is not clean until Phase 8, so the buildout's pre-commit hook fails until then. Accepted; commits pass with `--no-verify`.
- **Phase 8:** expect pre-existing test failures to surface when the test-layer isolation is fixed (`plone.testing 4.1.3` has no isolation guard; some tests currently pass *because* of a state leak). Real bugs revealed, not caused.
- **Phase 8:** the post-fix coverage baseline is genuinely unknown and cannot be estimated before `[run] source` lands. The figure is expected to drop sharply; the drop is the truth.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-28T14:40:10.890Z
Stopped at: Completed 01-01-PLAN.md
Resume file: None
