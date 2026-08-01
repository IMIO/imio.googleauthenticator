---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 05
current_phase_name: drift-replay-and-lockout
status: executing
stopped_at: Completed 05-05-PLAN.md
last_updated: "2026-08-01T14:00:51.949Z"
last_activity: 2026-08-01
last_activity_desc: Phase 05 execution started
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 18
  completed_plans: 18
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-31)

**Core value:** A second factor that actually holds for in-site users, and that can be deployed alongside `imio.dms.mail` without colliding with it.
**Current focus:** Phase 05 — drift-replay-and-lockout

## Current Position

Phase: 05 (drift-replay-and-lockout) — EXECUTING
Plan: 2 of 5
Status: Ready to execute
Last activity: 2026-08-01 — Phase 05 execution started

Progress: [████████████████████] 13/13 plans executed · **4 of 8 roadmap phases complete ([██████████] 100%)**

Phases 5–8 still have no plans, so the 13-plan denominator will grow; the phase figure
remains the honest one.

Phase 4 closed on 2026-07-31: all four plans executed, verification passed (5/5 success
criteria), UAT passed (1 item — the operator confirmation that no external consumer uses
HTTP Basic Auth against this site), and the security audit closed all 24 threats
(`04-SECURITY.md`, `threats_open: 0`). Two non-blocking code-review warnings remain open,
recorded as WR-01 and WR-02 in `04-REVIEW.md`.

## Performance Metrics

**Velocity:**

- Total plans completed: 13
- Average duration: —
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 4 | - | - |
| 02 | 2 | - | - |
| 03 | 3 | - | - |
| 04 | 4 | - | - |

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
| Phase 04 P01 | 70min | 2 tasks | 4 files |
| Phase 04 P02 | ~15min (continuation) | 3 tasks | 2 files |
| Phase 04 P03 | 90min | 2 tasks | 3 files |
| Phase 04 P04 | 50min | 2 tasks | 3 files |
| Phase 05 P01 | 16min | 3 tasks | 10 files |
| Phase 05 P02 | 12min | 2 tasks | 2 files |
| Phase 05 P03 | 12min | 3 tasks | 4 files |
| Phase 05 P04 | 20min | 2 tasks | 3 files |
| Phase 05 P05 | 20min | 1 tasks | 3 files |

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
- [Phase ?]: [Phase 4]: 04-01: SEC-03's fail-closed guarantee (broken encryption key raises out of _extractUserIds) preserved via a synchronous get_secret(user) pure-read call inside authenticateCredentials, reconciling the plan's decide-only <action> text with its own acceptance criterion that test_login_is_refused_when_seed_key_is_broken keep passing unmodified.
- [Phase ?]: [Phase 4]: 04-01: Task 2's over-HTTP body-leak assertion submits via Browser.open() with encoded POST data rather than Browser.getControl(...).click() -- _clickSubmit() re-raises mechanize.HTTPError unconditionally and never consults raiseHttpErrors, so the plan's suggested two-switch idiom only works against a directly-posted request.
- [Phase ?]: Phase 04-02: checkpoint answered by human (2026-07-31) — keep credentials_basic_auth active rather than deactivate; recorded as a dated comment in setuphandlers.py; test_plugin_is_first_authenticator is now the sole control against a Basic Auth bypass via plugin reorder.
- [Phase ?]: Phase 04-02: no profiles/uninstall/ counterpart owed (only applied under the unselected 'deactivate' branch); plan 04-03's test_basic_auth_veto must assert through the normal _extractUserIds path, not a direct authenticateCredentials call.
- [Phase ?]: [Phase 4]: 04-03: challenge() added as IChallengePlugin (COEX-08 Unauthorized half), sharing send_2fa_redirect with 04-01's IPubBeforeCommit subscriber; Open Question 3 resolved empirically as not-needed since 04-02's movePluginsTop loop already covers any interface classImplements declares
- [Phase ?]: [Phase 4]: 04-03: five veto tests added (form POST, Basic Auth, both extractors at once, empty credentials, exception path), each proven load-bearing by a recorded mutation check; discovered (by design, not a bug) that HTTP Basic Auth loops forever against this 2FA veto since the client resends the same header on every request including the redirect target
- [Phase ?]: Phase 04-04: DOC-01/DOC-02 README sections added (Zope-root boundary + emergency-user carve-out; the settled credentials_basic_auth 'keep active' decision with WebDAV/FTP/XML-RPC consequence and the service-account+IP-whitelist alternative), each backed by a fact-presence CI test proven load-bearing by a delete-the-section mutation check; 'ZMI -> acl_users' reconciled to read as verification+recovery now that movePluginsTop is profile-authoritative.
- [Phase ?]: [Phase 5]: 05-01: three int memberdata properties (failed_attempts/locked_until/last_interval) declared and round-trip-proven both directly and via the profile import; max_failed_attempts(5)/lockout_duration(900) added to the control panel with zero new form class; lock gate wired into token.py::handleSubmit before validate_user_data/validate_token, reusing the existing generic error message so a locked account is not an oracle.
- [Phase ?]: [Phase 5]: 05-01: MFA-12 pinned by a source-grep test (tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin) asserting pas_plugin.py/subscribers.py never mention the new property names or helper functions, plus a two-request Browser sequence proving the counter survives a request that began in Unauthorized. Both non-vacuity mutation checks (moving the lock gate past the success/failure dispatch; adding a property name to subscribers.py) reproduced red, then restored byte-identical.
- [Phase ?]: [Phase 5]: 05-02: validate_token rewritten -- TOTP_INTERVAL_SECONDS/_is_six_digit_token/_find_accepted_interval added; drift accepted only backward (current, current-1), replay refused via two_factor_authentication_last_interval with a no-operand INFO log, format gate refuses non-six-ASCII-digit input before the seed is ever fetched. Same-commit regression fix: test_seed_encryption_round_trip now uses get_totp(seed, as_string=True). MFA-05 real-device drift-boundary check deferred to end-of-phase human verification (no running instance/physical device in this environment).
- [Phase ?]: [Phase 5]: 05-03: browser/forms/reset_bar_code.py::handleSubmit metered with the same lock gate/counter as token.py -- lock checked after user-not-found/is_site_local_user guards and before validate_token; success branch calls reset_failed_second_factor before the try block (P5-14) so a PropertyValueError surfaces rather than being swallowed. Non-vacuity mutation (removing register_failed_second_factor) reproduced red, restored byte-identical.
- [Phase ?]: [Phase 5]: 05-03: filled the MFA-05/06/07 rows in 05-VALIDATION.md that plan 05-02 left as TBD, and fixed a stale test_token_form sampling-command reference -- documented as a Rule 2 documentation-completeness deviation, not a scope change.
- [Phase ?]: [Phase 5]: 05-04: reordered is_account_locked to run after validate_user_data succeeds and before validate_token in token.py, closing CR-01 (an unsigned caller could learn account lock state from the message string alone). New test proves three-way message equality (locked/unlocked-enrolled/nonexistent) for an anonymous caller with no signature/auth_timestamp; non-vacuity confirmed by reverting the reorder locally and observing the new test go red while the other 6 test_token.py methods stayed green.
- [Phase ?]: [Phase 5]: 05-05: reset_bar_code.py locked branch swapped to the wrong-code path's "Setup failed! {0}" wrapper (was "Resetting of the bar-code failed! {0}"), closing 05-03's T-05-03 message-level oracle claim which was false; new test proves two-way message-list equality (locked/unlocked, same and a different account); non-vacuity RED confirmed against unmodified source before the fix.

### Pending Todos

[From .planning/todos/pending/ — ideas captured during sessions]

None yet.

### Blockers/Concerns

[Issues that affect future work]

- **External, Phase 3:** the encryption-key `concat::fragment` lives in the separate `industrialisation` repo. Not one of this roadmap's commits. Phase 3 code is testable without it; the feature is not deployable until it ships.
- **Phase 3 (from 02-SECURITY.md R-02-02):** T-02-09 was accepted on the grounds that every `get_ska_secret_key()` component is ASCII by construction. Phase 3 changes `user_secret` to `v1$<fernet token>` — base64, so still ASCII, but this assumption must be **re-checked, not re-assumed**, when that lands.
- **Phase 3 (from 02-SECURITY.md R-02-01):** `browser/controlpanel.py` renders `ska_secret_key` into a form field. Pre-existing and untouched by Phase 2; it is the recorded Phase 3 secret-hygiene deferred idea.
- **Phase 5 (from 04-SECURITY.md R-04-C):** do NOT attach lockout or replay state to the `send_2fa_redirect` call chain. `challenge()` and the `IPubBeforeCommit` subscriber are write-free in their own bodies, but `send_2fa_redirect` reaches `sign_user_data` → `get_or_create_secret`, which writes a memberdata seed for a 2FA-enabled user who has none. That mint is fail-closed and not attacker-reachable, so it does not reopen T-04-05 or T-04-24 — but the write-free guarantee MFA-12 inherits covers the handler bodies, not everything reachable from them. No test currently pins that branch in either direction.
- **Phase 5 (from 04-REVIEW.md WR-01/WR-02):** for a user with 2FA enabled but no stored seed, a broken or missing `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` does not raise synchronously in `authenticateCredentials` — it raises later inside `send_2fa_redirect`, giving an uncontrolled error page instead of a clean refusal. Still fail-closed, no bypass. The fix is an unconditional `check_encryption_key_is_usable()` call plus a test for the never-enrolled state.
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

Last session: 2026-08-01T14:00:51.939Z
Stopped at: Completed 05-05-PLAN.md
Resume file: None
