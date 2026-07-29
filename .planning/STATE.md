---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 01
current_phase_name: rename-and-fail-closed
status: executing
stopped_at: Completed 01-03-PLAN.md
last_updated: "2026-07-29T07:40:24.085Z"
last_activity: 2026-07-29
last_activity_desc: Phase 01 execution started
progress:
  total_phases: 1
  completed_phases: 0
  total_plans: 4
  completed_plans: 3
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-28)

**Core value:** A second factor that actually holds for in-site users, and that can be deployed alongside `imio.dms.mail` without colliding with it.
**Current focus:** Phase 01 — rename-and-fail-closed

## Current Position

Phase: 01 (rename-and-fail-closed) — EXECUTING
Plan: 3 of 4
Status: Ready to execute
Last activity: 2026-07-29 — Phase 01 execution started

Progress: [████████░░] 75%

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
| Phase 01 P02 | 35min | 2 tasks | 9 files |
| Phase 01 P03 | 30min | 3 tasks | 13 files |

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
- [Phase ?]: 01-02: Used the live ska_secret_key schema field's title (Secret Key -> Geheime Sleutel) for test_control_panel_is_translated_nl instead of the plan's suggested stale 'Google Authenticator settings' msgid, which has no corresponding _(...) call in current source and would have been dropped by i18ndude's rebuild-pot.
- [Phase ?]: 01-02: Dutch translations completed only for the three msgids this plan's own source corrections invalidated (D-19 scope); ~19 pre-existing untranslated msgids the rebuild-pot surfaced are documented as a deferred gap, not silently filled or ignored.
- [Phase ?]: 01-03: Task 1's first commit (92fef48) silently dropped its content edits due to an atomic multi-path git add failure; corrected with a follow-up commit (9dc6317) rather than an amend.
- [Phase ?]: 01-03: profiles/default/site_properties.xml left in place (dead per RESEARCH O-3) -- tied to no requirement, recorded as a Phase 8 observation.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- **External, Phase 3:** the encryption-key `concat::fragment` lives in the separate `industrialisation` repo. Not one of this roadmap's commits. Phase 3 code is testable without it; the feature is not deployable until it ships.
- **Phases 1–7:** `bin/code-analysis` is not clean until Phase 8, so the buildout's pre-commit hook fails until then. Accepted; commits pass with `--no-verify`.
- **Phase 8:** expect pre-existing test failures to surface when the test-layer isolation is fixed (`plone.testing 4.1.3` has no isolation guard; some tests currently pass *because* of a state leak). Real bugs revealed, not caused.
- **Phase 8:** the post-fix coverage baseline is genuinely unknown and cannot be estimated before `[run] source` lands. The figure is expected to drop sharply; the drop is the truth.
- **Phase 8:** the corrected `bin/code-analysis` baseline is **318 findings** (not the ~40 the pre-rename `CLAUDE.md` claimed), measured in plan 01-03 (RESEARCH C-6 / Open Question 4). 184 of the 318 (58%) are `isort` findings, and the rename actively perturbs first-party import ordering. QUAL-06 must be planned against 318.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-07-29T07:40:24.074Z
Stopped at: Completed 01-03-PLAN.md
Resume file: None
