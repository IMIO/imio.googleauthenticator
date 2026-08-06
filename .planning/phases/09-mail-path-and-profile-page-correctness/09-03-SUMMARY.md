---
phase: 09-mail-path-and-profile-page-correctness
plan: 03
subsystem: auth
tags: [plone, pas-plugin, z3c.form, page-template, totp]

requires:
  - phase: 09-01
    provides: BUG-07's mail-failure message pattern (not directly used here, but this plan lands in the same phase)
  - phase: 09-02
    provides: BUG-08's schema-description edit convention (D-14-style deletion), same phase's non-vacuity discipline
provides:
  - "The recovery-codes page's only link now targets the site's navigation root instead of the user's own profile"
  - "The enrollment page's qr_code field description now carries the base32 TOTP secret as selectable <code> text beside the QR image"
affects: [phase-11-sec-09-reauth-gate, phase-13-i18n-catalogue-rebuild]

tech-stack:
  added: []
  patterns:
    - "TAL @@plone-view traversal for navigationRootUrl inside a standalone (no metal:use-macro) page template, instead of the globals_view name that only exists in main_template's global_defines / CMF action-expression context"
    - "Bind a value-with-a-side-effect (get_or_create_secret) to a local variable once and reuse it for every consumer in the same function, rather than calling it again"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/forms/recovery_codes.pt
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/tests/test_user_setup.py

key-decisions:
  - "Resolved the home-page URL through context/@@plone/navigationRootUrl rather than the globals_view/navigationRootUrl idiom RESEARCH.md and PATTERNS.md proposed: recovery_codes.pt is rendered standalone via self.recovery_codes_template() with no metal:use-macro, so globals_view (bound only by main_template's global_defines or the CMF action-expression context) is not in this template's TAL namespace and would raise a NameError at render time. @@plone is the same view globals_view resolves to, verified by re-running the tracer's <verify> end-to-end after the change."
  - "get_token_description() now calls get_or_create_secret exactly once, binding the result to a local variable reused for both the QR's otpauth:// payload and the appended <code> text -- confirmed by grep against the committed diff (D-08, T-09-05)."

requirements-completed: [UX-01, UX-02]

coverage:
  - id: D1
    description: "The recovery-codes page's only link resolves the site's navigation root and reads \"Continue to the home page\"; the old \"Continue to your profile\" text and its @@personal-information target are gone; the ten one-time recovery codes still render in the same response (RECOV-03 guard)."
    requirement: "UX-01"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_user_setup.py#test_recovery_codes_page_links_to_the_home_page"
        status: pass
    human_judgment: false
  - id: D2
    description: "The enrollment form's qr_code field description contains the user's base32 TOTP secret, wrapped in a <code> element, beside the still-present QR <img> -- produced by exactly one get_or_create_secret call inside get_token_description."
    requirement: "UX-02"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_user_setup.py#test_setup_form_shows_the_secret_as_selectable_text"
        status: pass
    human_judgment: true
    rationale: "Only the automatable half of Phase 9 success criterion 4 is proven here -- that the rendered text equals the stored seed. Whether a real desktop TOTP client fed this string then produces codes the site accepts is a UAT step for plan 09-04, not a unit test (per this plan's own <success_criteria>)."

duration: 25min
completed: 2026-08-06
status: complete
---

# Phase 9 Plan 3: UX-01 Home-Page Redirect and UX-02 Selectable Secret Summary

**Retargeted the recovery-codes page's only link to the navigation root via `@@plone`, and extended `get_token_description()` to show the base32 TOTP secret as a `<code>` element beside the QR, from the single `get_or_create_secret` call already in hand.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-06T12:39:22Z (approx, per STATE.md's prior session timestamp)
- **Completed:** 2026-08-06
- **Tasks:** 2 (Task 1: tracer; Task 2: TDD)
- **Files modified:** 3

## Accomplishments

- A user who finishes MFA enrollment now sees exactly one link on the recovery-codes page, and it targets the site's navigation root (the home page) — not `@@personal-information`.
- The enrollment page's QR-code field description now also carries the plaintext base32 secret as selectable text inside a `<code>` element, produced from the same `get_or_create_secret` call that already built the QR — nothing minted or looked up twice.
- Both fixes are provably confined to their target file: `git diff -- src/imio/googleauthenticator/browser/forms/user_setup.py` is empty across every commit in this plan.

## Task Commits

Each task was committed atomically, with a RED/GREEN pair per the project's non-vacuity convention:

1. **Task 1 (tracer): Enrollment ends with a link to the home page, end-to-end**
   - `cea8111` (test) — added `test_recovery_codes_page_links_to_the_home_page`, proven red against the unmodified template
   - `88fbc14` (feat) — retargeted `recovery_codes.pt`'s link to `context/@@plone/navigationRootUrl`, text now "Continue to the home page"
2. **Task 2: The enrollment page shows the secret as selectable text (tdd)**
   - `062866e` (test) — added `test_setup_form_shows_the_secret_as_selectable_text`, proven red against the unmodified helper
   - `2da751e` (feat) — extended `helpers.get_token_description()` to append the base32 secret inside a `<code>` element

**Plan metadata:** (this commit, following SUMMARY.md write)

_Note: both tasks used the project's standard test-then-fix two-commit shape; Task 1 is typed `tracer` in the plan but executed with a real implementation and a real `<verify>`, exactly like `type="auto"`._

## Files Created/Modified

- `src/imio/googleauthenticator/browser/forms/recovery_codes.pt` — the link's `href` now resolves `context/@@plone/navigationRootUrl`, text reads "Continue to the home page"; a template comment records why `globals_view` (the idiom used three times in `actions.xml`) is not used here
- `src/imio/googleauthenticator/helpers.py` — `get_token_description()` binds `get_or_create_secret(...)` to a local variable once and appends `<p>{label} <code>{secret}</code></p>` to the returned markup
- `src/imio/googleauthenticator/tests/test_user_setup.py` — added `test_recovery_codes_page_links_to_the_home_page` and `test_setup_form_shows_the_secret_as_selectable_text`

## Decisions Made

- **Corrected the plan's own implementation-detail warning was followed exactly as written, not the RESEARCH.md/PATTERNS.md shape.** `recovery_codes.pt` is rendered through `self.recovery_codes_template()` with no `metal:use-macro`, so it never receives `main_template`'s `global_defines` and the name `globals_view` is not in its TAL namespace. Verified independently: `form.render()` was called in the passing test and produced no TAL `NameError`/`KeyError`, and the rendered markup contains the resolved `href` matching the test portal's `@@plone` view's `navigationRootUrl()` value (`/plone`), not a raised exception.
- **`get_or_create_secret` is called exactly once inside `get_token_description()`** — confirmed by `awk` extraction + grep count on the committed function body (see verification below), satisfying D-08 and the T-09-05 mitigation.
- No architectural decisions (Rule 4) were needed; both tasks were mechanical, single-file diffs as the plan predicted.

## Deviations from Plan

None — plan executed exactly as written, including the deliberate deviation from RESEARCH.md/PATTERNS.md's suggested `globals_view` expression that the plan itself flagged and corrected in advance.

## Issues Encountered

None. Both non-vacuity checks reproduced red on the first attempt and green on the first fix attempt; `bin/code-analysis` and the full `bin/test -t '!robot'` suite passed without any lint or test iteration needed.

## Non-Vacuity Check Evidence (verbatim red output)

**Task 1 — `test_recovery_codes_page_links_to_the_home_page` against the unmodified `recovery_codes.pt`:**

```
AssertionError: 'Continue to the home page' not found in u'<div>\n\n  <h1>Your recovery codes</h1>\n\n  <p class="portalMessage warning">\n    These codes are shown only this one time and cannot be retrieved again.\n    Write them down or store them in a safe place before leaving this page.\n  </p>\n\n  <ol>\n    <li>\n      <code>NNT4MGBUGE2QFANZ</code>\n    </li>\n    ... [ten <li><code>...</code></li> entries] ...\n  </ol>\n\n  <p>\n    Each code works once, in place of the verification code from your\n    authenticator app, if you ever lose access to your device.\n  </p>\n\n  <p>\n    <a href="/plone/@@personal-information">Continue to your profile</a>\n  </p>\n\n</div>\n' : UX-01: the retargeted link text must be present.

  Ran 1 tests with 1 failures and 0 errors in 1.118 seconds.
```

**Task 2 — `test_setup_form_shows_the_secret_as_selectable_text` against the unmodified `get_token_description()`:**

```
AssertionError: '5HVWDJD2M67RMXNJB4YMUOABTVAQR636' not found in u'<div><img src="data:image/png;base64,iVBORw0KGgo...AAAAElFTkSuQmCC" alt="QR Code" /></div>' : The base32 secret must appear as text beside the QR code.

  Ran 1 tests with 1 failures and 0 errors in 0.057 seconds.
```

Both sources were restored (via the normal STEP1-commit / STEP2-edit sequence, never manually reverted) and then fixed in the very next commit.

## `form.render()` TAL-error proof

The plan's highest-risk item was proving the corrected `context/@@plone/navigationRootUrl` expression resolves in `recovery_codes.pt`'s actual namespace (a standalone-rendered template with no `main_template` macro), rather than raising the TAL `NameError` the `globals_view` spelling would have produced. Proof: `test_recovery_codes_page_links_to_the_home_page` calls `form.render()` (which internally calls `self.recovery_codes_template()`) and asserts on the *returned markup string* — a raised TAL error would have surfaced as an uncaught exception failing the test with a traceback through `zope.pagetemplate`, not a clean `AssertionError`. The test passed cleanly (`bin/test -t test_recovery_codes_page_links_to_the_home_page` — "Ran 1 tests with 0 failures and 0 errors"), and the rendered `href` matched `self.portal.restrictedTraverse('@@plone').navigationRootUrl()`'s live value, confirming the expression both parses and resolves to the correct value, not merely that it parses.

## Verification Run Log

- `bin/test -t test_recovery_codes_page_links_to_the_home_page` — 1 test, 0 failures, 0 errors
- `bin/test -t test_setup_form_shows_the_secret_as_selectable_text` — 1 test, 0 failures, 0 errors
- `bin/test -t test_user_setup` — 10 tests, 0 failures, 0 errors (every pre-existing method, including `test_recovery_codes_are_issued_once_at_enrollment` and `test_handleSubmit_refuses_an_account_not_defined_in_this_site`, still green)
- `bin/test -t test_helpers` — 26 tests (+1 unit layer), 0 failures, 0 errors
- `bin/test -t '!robot'` (full suite) — 140 tests, 0 failures, 0 errors
- `bin/code-analysis` — exits 0 (Flake8 OK), confirmed after each commit
- `git diff -- src/imio/googleauthenticator/browser/forms/user_setup.py` — empty, confirmed after both tasks
- `git diff --name-only` for this plan's four feature/test commits — exactly `recovery_codes.pt`, `helpers.py`, `tests/test_user_setup.py`; no `profiles/default/jsregistry.xml`, no `browser/static/*`, no new `.pt` file
- Single `get_or_create_secret(` call inside `get_token_description`'s body, confirmed via `awk` range extraction + grep count

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced by this plan.

## Threat Flags

None beyond what the plan's own `<threat_model>` already registered (T-09-04, T-09-05, T-09-06, T-09-SC) — no new network endpoint, auth path, file-access pattern, or schema change was introduced.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- UX-01 and UX-02 are both fully implemented and unit-tested for their automatable half.
- The remaining half of Phase 9 success criterion 4 — that a real desktop TOTP client fed the displayed base32 secret produces codes the site accepts — is explicitly deferred to a UAT step in plan 09-04, per this plan's own `<success_criteria>`.
- No blockers for the rest of Phase 9 or for Phase 11 (SEC-09's re-authentication gate will sit in front of this same enrollment action later) or Phase 13 (the new "Setup key:" msgid and the retired-but-never-translated "Continue to your profile" msgid are both first-time-addition inputs for the catalogue rebuild, carrying no orphaned-translation risk per RESEARCH.md's Additional Finding).

---
*Phase: 09-mail-path-and-profile-page-correctness*
*Completed: 2026-08-06*

## Self-Check: PASSED

All four created/modified files and all four commit hashes (`cea8111`, `88fbc14`, `062866e`, `2da751e`) were confirmed present on disk / in `git log` before this SUMMARY was finalized.
