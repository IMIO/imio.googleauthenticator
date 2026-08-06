---
phase: 09-mail-path-and-profile-page-correctness
plan: 04
subsystem: testing
tags: [plone, coverage, flake8, changelog, totp]

# Dependency graph
requires:
  - phase: 09-01
    provides: "BUG-07's mail-failure reporting fix"
  - phase: 09-02
    provides: "BUG-08's wrong-account-link removal"
  - phase: 09-03
    provides: "UX-01's home-page link and UX-02's selectable secret text"
provides:
  - "A single full-suite run, coverage run and lint run over all three wave-1 plans merged together, with the real observed numbers recorded"
  - "A CHANGES.rst entry covering BUG-07, BUG-08, UX-01, UX-02 and the accepted D-16 French-catalogue consequence"
  - "A recorded (blocked, not passed) outcome for the one Phase 9 success criterion that needs a real desktop TOTP client"
affects: [phase-10-globally-enabled-enrollment, phase-11-reauth-gate, phase-12-notification-emails, phase-13-i18n-catalogue-rebuild]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase-gate plan: no production file touched unless a gate fails; the plan's only durable output is a changelog entry and a recorded verification run"

key-files:
  created: []
  modified:
    - CHANGES.rst

key-decisions:
  - "D-16 (restated): the orphaned French translation of the retired enable_two_factor_authentication description is a known, accepted Phase 13 input, recorded in CHANGES.rst so a reader outside .planning/ is not surprised by it."
  - "The manual TOTP-client check (second half of success criterion 4) is recorded as blocked, not passed: this execution has no human operator to drive a real authenticator app, and bin/instance in this environment has no IMIO_GOOGLEAUTHENTICATOR_SEED_KEY set (confirmed empty in the executing shell), which the plan's own action text already flags as a precondition for even starting the check."

patterns-established: []

requirements-completed: [BUG-07, BUG-08, UX-01, UX-02]

coverage:
  - id: D1
    description: "bin/test -t '!robot' is green over all three merged wave-1 plans, including all five new test methods"
    requirement: "BUG-07"
    verification:
      - kind: integration
        ref: "bin/test -t '!robot' (140 tests, 0 failures, 0 errors)"
        status: pass
    human_judgment: false
  - id: D2
    description: "bin/test-coverage -t '!robot' passes --fail-under=90 with the real reported branch-coverage percentage recorded"
    requirement: "BUG-07"
    verification:
      - kind: other
        ref: "bin/test-coverage -t '!robot' (TOTAL 91%, exit 0)"
        status: pass
    human_judgment: false
  - id: D3
    description: "bin/code-analysis exits 0 over the merged phase"
    requirement: "BUG-08"
    verification:
      - kind: other
        ref: "bin/code-analysis (Flake8 OK, exit 0)"
        status: pass
    human_judgment: false
  - id: D4
    description: "CHANGES.rst records BUG-07, BUG-08, UX-01, UX-02 and the accepted D-16 French-translation consequence, in the file's existing bullet-and-attribution style"
    requirement: "UX-01"
    verification:
      - kind: manual_procedural
        ref: "git diff --stat -- CHANGES.rst (37 insertions, CHANGES.rst only)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The displayed base32 secret, entered into a real desktop TOTP client, produces codes the site accepts"
    requirement: "UX-02"
    verification: []
    human_judgment: true
    rationale: "Not automatable in this suite (CONTEXT.md <specifics>), and not performable by this autonomous executor either -- there is no human present to operate a real desktop TOTP client, and bin/instance in this environment has no IMIO_GOOGLEAUTHENTICATOR_SEED_KEY set (confirmed empty), which the plan's own <human-check> text already names as a precondition the check cannot run without. Recorded as blocked, not passed, per the plan's explicit instruction not to mark a skipped check as a pass."

duration: ~20min
completed: 2026-08-06
status: complete
---

# Phase 9 Plan 4: Full-Suite, Coverage and Lint Gates Over the Merged Phase Summary

**Ran the full test suite, the coverage gate and the lint gate once over all three wave-1 plans merged together — 140 tests / 0 failures / 0 errors, 91% branch coverage, `bin/code-analysis` exit 0 — and recorded the phase in `CHANGES.rst`, including the one D-16 consequence and the one manual check this executor could not perform.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 completed
- **Files modified:** 1 (`CHANGES.rst`)

## Accomplishments

- **Full suite:** `bin/test -t '!robot'` — **140 tests, 0 failures, 0 errors** (matches the orchestrator's independently-observed number). All five new test methods from plans 09-01/02/03 are present and ran: `test_a_refused_recipient_reports_in_page_not_an_error_page`, `test_an_unreachable_mail_server_reports_the_same_failure`, `test_enable_flag_description_offers_no_wrong_account_links`, `test_recovery_codes_page_links_to_the_home_page`, `test_setup_form_shows_the_secret_as_selectable_text`.
- **Coverage gate:** `bin/test-coverage -t '!robot'` exits **0**. Reported **TOTAL 91%** branch coverage (`1089` statements, `69` missed, `292` branches, `52` partial), above the `--fail-under=90` threshold. `request_bar_code_reset.py` is now **89%** covered with the uncovered lines shifted to `56, 141-145` — the roadmap's previously-recorded uncovered pair at `112-113` (the re-raise BUG-07 deleted) no longer exists as a coverage gap; the file's line numbers moved because the fix removed code, not because coverage regressed.
- **Lint gate:** `bin/code-analysis` exits **0** (`Flake8 OK`), run twice — once before the changelog edit, once after — confirming the documentation-only change did not disturb it.
- **Changed-file-set check:** `git diff --name-only d65826b^ 2da751e -- src/` returns exactly the seven files the three wave-1 plans declared: `request_bar_code_reset.py`, `test_request_bar_code_reset.py`, `helpers.py`, `test_adapter.py`, `userdataschema.py`, `recovery_codes.pt`, `test_user_setup.py`. No `locales/`, `profiles/`, or `browser/static/` path appears, and neither `pas_plugin.py` nor `browser/settings_helper.py` does.
- **Changelog:** added a Phase 9 entry to `CHANGES.rst`'s `1.0.0 (unreleased)` section, one bullet per fix (BUG-07, BUG-08, UX-01, UX-02) plus one bullet recording the accepted D-16 consequence, each closed with `[chris-adam]` in the file's existing style. `git diff --stat -- CHANGES.rst` confirms only that file changed (37 insertions).
- **Manual TOTP-client check:** attempted and recorded as **blocked**, not passed — see "Known Stubs" / Deviations below.

## Task Commits

1. **Task 1: The whole suite, the coverage gate and the lint gate** — no commit. Per the plan's own `<files>` note ("none — this task changes no file unless a gate fails"), all three gates passed on the first run, so nothing needed fixing and no commit was made for this task.
2. **Task 2: Changelog, and the one check a test cannot make** — `240ca34` (docs): `docs(09-04): record Phase 9 fixes in CHANGES.rst`.

**Plan metadata:** (this commit, filed alongside STATE.md/ROADMAP.md updates)

## Files Created/Modified

- `CHANGES.rst` — five new bullets under `1.0.0 (unreleased)`: BUG-07 (mail-send failure reporting), BUG-08 (wrong-account links removed), UX-01 (home-page link), UX-02 (selectable secret text), and the accepted D-16 orphaned-French-translation consequence.

## Decisions Made

- No new decisions were needed for Task 1 — all three gates passed on the first run, so the "if any gate fails, fix and re-run" branch of the plan's `<action>` was never exercised.
- Task 2 followed D-16 as written: the changelog is where a reader outside `.planning/` learns about the orphaned French translation, and no `.po`/`.pot` file was touched.
- The manual TOTP-client check's outcome (blocked, not attempted-and-passed) is recorded honestly per the plan's explicit instruction ("A skipped or blocked check is recorded as such, with the reason, never as a pass") and per this plan's own critical constraint not to write a test claiming to automate it.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1-4 auto-fixes were needed: every gate passed on the first run, so no production file was touched by this plan.

## Issues Encountered

None for the automated gates. The manual TOTP-client check could not be performed — see "Known Stubs" below; this is not an issue with the plan or the code, it is a limitation of running plan 09-04 through an autonomous, non-interactive executor with no human operator and no seed key configured for `bin/instance` in this environment.

## Verification Evidence

**`bin/test -t '!robot'`:**
```
Ran 136 tests with 0 failures and 0 errors in 27.578 seconds.  (Functional layer)
Ran 4 tests with 0 failures and 0 errors in 0.002 seconds.     (UnitTests layer)
Total: 140 tests, 0 failures, 0 errors in 32.334 seconds.
```

**`bin/test-coverage -t '!robot'`** (exit 0):
```
Total: 140 tests, 0 failures, 0 errors in 42.398 seconds.
...
TOTAL                                                                                      1089     69    292     52    91%
```
Notable per-file lines: `request_bar_code_reset.py` 89% (missing 56, 141-145 — not the old 112-113 pair, which was the re-raise BUG-07 deleted); `helpers.py` 85%; `userdataschema.py` 98%; `pas_plugin.py` 80% (untouched by this phase). No file this phase modified regressed below its own prior baseline; the milestone-wide 90% floor is met at 91%.

**`bin/code-analysis`** (run twice, before and after the CHANGES.rst edit):
```
Flake8...............................[ OK ] in ~1.6-1.9s
The command "bin/code-analysis" exited with 0.
```

**Changed-file-set:**
```
$ git diff --name-only d65826b^ 2da751e -- src/
src/imio/googleauthenticator/browser/forms/recovery_codes.pt
src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py
src/imio/googleauthenticator/helpers.py
src/imio/googleauthenticator/tests/test_adapter.py
src/imio/googleauthenticator/tests/test_request_bar_code_reset.py
src/imio/googleauthenticator/tests/test_user_setup.py
src/imio/googleauthenticator/userdataschema.py
```
Exactly the seven files the acceptance criteria list; nothing else.

**`git diff --stat -- CHANGES.rst`:**
```
CHANGES.rst | 37 +++++++++++++++++++++++++++++++++++++
1 file changed, 37 insertions(+)
```

## Known Stubs

- **The manual TOTP-client verification (Phase 9 success criterion 4, second half) is not performed — recorded as blocked, not passed.** `09-VALIDATION.md`'s Manual-Only Verifications table names this exact check. This execution is a non-interactive autonomous plan run with no human present to enrol a test user through a browser, copy a base32 secret, and enter it into a real desktop TOTP client or password manager. In addition, `env | grep -i SEED_KEY` in the executing shell confirmed `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` is **not set**, which the plan's own `<human-check>` text already names as a precondition ("`bin/instance` does not have `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` set... so export it in the shell before starting the instance, or this check cannot run at all"). Per the plan's acceptance criteria, this is recorded here as a genuinely blocked check, not silently passed and not automated with a fake test. A human operator with shell access to export the seed key and a real TOTP client (or password manager) must perform the five-step script in `09-VALIDATION.md`'s Manual-Only Verifications table before this half of criterion 4 can be marked done.

## Threat Flags

None. This plan's only change is a documentation edit (`CHANGES.rst`); no new network endpoint, auth path, file-access pattern, or schema change was introduced.

## User Setup Required

**Yes — to close the one remaining manual check.** A human with access to a running `bin/instance fg` (with `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` exported in the shell first — it is not set by `base.cfg` outside the `[testenv]` section) and a real desktop TOTP client or password manager needs to:
1. Enrol a test user at `@@setup-two-factor-authentication`.
2. Copy the base32 setup key shown beside the QR code as text (not by scanning the image).
3. Enter it into the TOTP client as a manually-entered setup key.
4. Log out, log in, and submit the code the client shows.
5. Confirm the site accepts it.

No other external service configuration is required by this plan.

## Next Phase Readiness

- Phase 9 is complete: all four success criteria's automatable halves are proven, the milestone's six standing constraints (Python 2.7/Plone 4.3 only, >90% coverage, `bin/code-analysis` exit 0, memberdata declaration discipline, no PAS-plugin state writes, no foreign-resource mutation) hold across every commit in the phase, and `CHANGES.rst` records the phase for a reader outside `.planning/`.
- The one open item is the manual TOTP-client check (D5 above / the Known Stubs entry), which needs a human operator and is not a blocker for Phase 10-13 planning — it is orthogonal to the code paths those phases touch.
- Phase 12 inherits BUG-07's failure shape (widened catch tuple, no re-raise, reused generic message, success-message-inside-try) verbatim for its three additional senders.
- Phase 13 inherits two catalogue inputs: the orphaned French translation (D-16, now also recorded in `CHANGES.rst`) and the two new msgids from UX-01/UX-02 (the "Setup key:" label and "Continue to the home page" text), per plan 09-03's SUMMARY.

## Self-Check: PASSED

- FOUND: `CHANGES.rst` (modified, `git diff --stat` confirms 37 insertions)
- FOUND commit: `240ca34` (`docs(09-04): record Phase 9 fixes in CHANGES.rst`)
- FOUND: `bin/test -t '!robot'` exit — 140 tests, 0 failures, 0 errors (verified by direct run, not inferred)
- FOUND: `bin/test-coverage -t '!robot'` exit 0, TOTAL 91% (verified by direct run with explicit `echo "EXIT=$?"` capture)
- FOUND: `bin/code-analysis` exit 0 (verified twice by direct run)

---
*Phase: 09-mail-path-and-profile-page-correctness*
*Completed: 2026-08-06*
