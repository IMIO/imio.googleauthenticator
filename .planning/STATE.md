---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 4
current_phase_name: PAS Boundary
status: shipped
stopped_at: Phase 03 shipped as PR #3 (37 commits, gsd/phase-3-encrypted-seeds-and-local-qr -> master), awaiting review/merge. Phase 4 not yet planned.
last_updated: "2026-07-30T18:30:00.000Z"
last_activity: 2026-07-30
last_activity_desc: Phase 03 shipped - PR #3
progress:
  total_phases: 8
  completed_phases: 3
  total_plans: 9
  completed_plans: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-29)

**Core value:** A second factor that actually holds for in-site users, and that can be deployed alongside `imio.dms.mail` without colliding with it.
**Current focus:** Phase 03 — encrypted-seeds-and-local-qr

## Current Position

Phase: 4 — PAS Boundary
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-30 — Phase 03 complete, transitioned to Phase 4

Progress: [████████████████████] 9/9 plans authored (100%) · **3 of 8 roadmap phases complete (38%)**

The plans figure is 100% only because plans exist for the three executed phases; phases 4–8
have no plans yet. The phase figure is the honest one.

## Performance Metrics

**Velocity:**

- Total plans completed: 9
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 2 | - | - |
| 03 | 3 | - | - |

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
| Phase 01 P04 | 25min | 2 tasks | 7 files |
| Phase 02 P01 | 25min | 2 tasks | 4 files |
| Phase 02 P02 | 12min | 2 tasks | 3 files |
| Phase 03 P01 | 35min | 5 tasks | 8 files |
| Phase 03 P02 | 20min | 2 tasks | 4 files |
| Phase 03 P03 | 45min | 2 tasks | 5 files |

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
- [Phase ?]: 01-04: meta_type/PAS_TITLE renamed to iMio in an isolated commit; PAS_ID (google_auth) left untouched, per the roadmap's own commit-isolation requirement.
- [Phase ?]: 01-04: _dont_swallow_my_exceptions = True surfaced two pre-existing bugs (is_whitelisted_client crashing on empty REMOTE_ADDR; a broken getProperty('username') debug line) that had likely been silently disabling the 2FA gate on every request in any deployment; both fixed as blocking Rule 1 auto-fixes.
- [Phase 02]: REG-01 was verified manually after all (UAT 2026-07-29) against a real site-creation log, not by the ordering assertion alone as D-01/D-02 planned. `var/log/instance.log` has zero `no record` / `defines a field ska_secret_key` lines. The 26 `Cannot find registry` INFO lines in that log are stock Plone noise from `plone.app.registry/exportimport/handler.py:67` and all precede our profile import — **do not treat that string as a regression signal in future phases.**
- [Phase 02]: **CORRECTION (supersedes the 02-01 plan's D-04/D-05):** `_setup_secret_key()` was NOT deleted and there is NO lazy mint. CR-02 reverted that design: `setuphandlers._setup_secret_key()` seeds `ska_secret_key` once at install time, and `get_ska_secret_key()` is a pure read that raises `ValueError` on an empty key (fail-closed). Phase 3 must build on the install-time seeding path, not a lazy accessor.
- [Phase ?]: 02-01: REG-05 double-apply test documented as a regression guard against a future schema tightening, not a fix for a currently-firing bug (D-13)
- [Phase ?]: 02-02: BUG-04 fixed via netstring-style length-prefixed join (D-08); test setUp needed a re-login after profile install because PLONE_FIXTURE's cached test-user property sheets predate the add-on's memberdata schema (own-test Rule 1 fix, no production change)
- [Phase ?]: Phase 03-01 Task 1 checkpoint: locked the TOTP-seed encryption-key env var name to IMIO_GOOGLEAUTHENTICATOR_SEED_KEY (human selected the unambiguous option over the shorter IMIO_GA_SEED_KEY plan default). Every plan reference to IMIO_GA_SEED_KEY is substituted with this literal.
- [Phase ?]: Task 1 checkpoint: environment-variable name locked to IMIO_GOOGLEAUTHENTICATOR_SEED_KEY (human overrode plan default IMIO_GA_SEED_KEY).
- [Phase ?]: Task 2 blocking-human package gate: cryptography==3.3.2, ipaddress==1.0.23, qrcode==6.1, cffi==1.15.1, Pillow all approved on live-PyPI-verified provenance.
- [Phase ?]: ska_secret_key control-panel TextLine field (02-SECURITY.md R-02-01) re-deferred again: PasswordWidget blanks an untouched field on Save, so the swap needs its own tested change, not a drive-by.
- [Phase ?]: [Phase 3]: 03-02: base.cfg [instance] deliberately carries no IMIO_GOOGLEAUTHENTICATOR_SEED_KEY entry (whitespace-form buildout can't parse an empty default, and a placeholder would silently suppress the new CRITICAL log); the deployment buildout supplies it, documented in README.rst.
- [Phase ?]: [Phase 3]: 03-02: no docs/ cross-reference added -- docs/index.rst is a stale pre-rename duplicate of an old README never kept in sync; README.rst is the deployer-facing shipped artifact DOC-03 targets.
- [Phase ?]: 03-03: BUG-02 closed by regression test with no production code change -- redirect_url confirmed bound on all three reachable branches of SetupForm.handleSubmit, both by research and by execution (empty diff on user_setup.py).
- [Phase ?]: 03-03: BUG-03 fixed via one shared validate_bar_code_reset_token helper (hmac.compare_digest with str/unicode coercion) used at both reset_bar_code.py comparison sites, not the one the requirement named.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- **External, Phase 3:** the encryption-key `concat::fragment` lives in the separate `industrialisation` repo. Not one of this roadmap's commits. Phase 3 code is testable without it; the feature is not deployable until it ships.
- **Phase 3 (from 02-SECURITY.md R-02-02):** T-02-09 was accepted on the grounds that every `get_ska_secret_key()` component is ASCII by construction. Phase 3 changes `user_secret` to `v1$<fernet token>` — base64, so still ASCII, but this assumption must be **re-checked, not re-assumed**, when that lands.
- **Phase 3 (from 02-SECURITY.md R-02-01):** `browser/controlpanel.py` renders `ska_secret_key` into a form field. Pre-existing and untouched by Phase 2; it is the recorded Phase 3 secret-hygiene deferred idea.
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

Last session: 2026-07-30T10:12:23.316Z
Stopped at: Completed 03-03-PLAN.md -- phase 03 code-complete, ready for verification
Resume file: None
