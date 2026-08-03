---
phase: 06-recovery-codes
plan: 02
subsystem: auth
tags: [z3c.form, plone.z3cform, page-template, cmf-action, python2]

# Dependency graph
requires:
  - phase: 06-recovery-codes (plan 01)
    provides: generate_recovery_codes, validate_recovery_code, validate_second_factor -- the substrate this plan wires into the UI
provides:
  - "SetupForm.handleSubmit mints ten recovery codes on the enrollment success path and skips the redirect on that one path so the same HTTP 200 response can render them"
  - "SetupForm.render() override: recovery_codes.pt when issued_recovery_codes is populated, the ordinary form otherwise -- the entire one-time-display mechanism"
  - "regenerate_recovery_codes portal action in the user category, reusing the existing enrolled-user availability view and the setup form's own TOTP check as the regeneration gate"
affects: [06-03-lockout-sharing-and-low-count-warning, 07-documentation, 08-code-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One render() override intercepting before super().render() runs, rather than a second view or a reusable mixin -- there is exactly one call site for 'show something else in this response' in the whole package."
    - "Skip-the-redirect-on-one-path is the entire same-response display mechanism: plone.z3cform 0.8.1's FormWrapper.update() only blanks contents and returns early on a 302/303 status, so a bare 200 is sufficient for the wrapped form's render() to run normally."
    - "Portal action reuse over a fourth SettingsHelper method: regenerate_recovery_codes's available_expr is the identical @@show-disable-two-factor-authentication-link view enable/disable already share, since 'globally enabled and this user has enrolled' is exactly regeneration's availability condition too."

key-files:
  created:
    - src/imio/googleauthenticator/browser/forms/recovery_codes.pt
  modified:
    - src/imio/googleauthenticator/browser/forms/user_setup.py
    - src/imio/googleauthenticator/profiles/default/actions.xml
    - src/imio/googleauthenticator/tests/test_user_setup.py
    - src/imio/googleauthenticator/tests/test_helpers.py
    - src/imio/googleauthenticator/tests/test_generic.py

key-decisions:
  - "test_handleSubmit scenario 1's redirect assertion changed from 'ends with /@@personal-information' to 'location header is None' -- a deliberate RECOV-03 behaviour change, not a test bent to fit code. The old assertion encoded the pre-recovery-codes contract; the new one is what 'render the codes in the same response' requires by plone.z3cform's own redirect-vs-render branching."
  - "Regeneration has no dedicated view: the existing @@setup-two-factor-authentication form, re-entered, is the regeneration path. Its TOTP-before-write gate is what stops a stolen recovery code from perpetuating itself into a fresh set (T-06-08)."

patterns-established:
  - "A form meant to display something other than itself in one specific response overrides render() to intercept before the inherited render() runs -- never a second registered view for a single-response special case."

requirements-completed: [RECOV-01, RECOV-03, RECOV-06]

coverage:
  - id: D1
    description: "Completing enrollment at @@setup-two-factor-authentication issues exactly ten codes, each 16 base32 characters with no padding, and the ten plaintext codes are rendered in the body of the same HTTP 200 response that generated them (no Location header)."
    requirement: "RECOV-01"
    verification:
      - kind: integration
        ref: "tests/test_user_setup.py#TestSetupForm.test_handleSubmit (scenario 1)"
        status: pass
      - kind: integration
        ref: "tests/test_user_setup.py#TestSetupForm.test_recovery_codes_are_issued_once_at_enrollment"
        status: pass
    human_judgment: false
  - id: D2
    description: "A second GET/render of the setup form after enrollment shows no code -- nothing persisted by the enrollment write can be read back into plaintext, so 'never redisplayed' holds by construction."
    requirement: "RECOV-03"
    verification:
      - kind: integration
        ref: "tests/test_user_setup.py#TestSetupForm.test_recovery_codes_are_issued_once_at_enrollment (fresh-form half)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Regeneration overwrites the salt and hash list in one write so a previous-set code never validates afterwards, and produces a full ten regardless of whether zero, one, or ten hashes were stored before."
    requirement: "RECOV-06"
    verification:
      - kind: integration
        ref: "tests/test_helpers.py#TestDriftAndReplay.test_recovery_code_regeneration_invalidates_the_previous_set"
        status: pass
    human_judgment: false
  - id: D4
    description: "An already-enrolled user reaches regeneration from a rendered portal action, invisible to a user who has not enrolled; regeneration is the setup form itself, so it still demands a valid TOTP code before it writes."
    requirement: "RECOV-06"
    verification:
      - kind: integration
        ref: "tests/test_generic.py#TestGeneric.test_regenerate_recovery_codes_action_is_registered"
        status: pass
      - kind: integration
        ref: "tests/test_user_setup.py#TestSetupForm.test_handleSubmit (scenario 3: rejected token mints nothing)"
        status: pass
    human_judgment: false
  - id: D5
    description: "BUG-02 preserved: redirect_url stays bound on every reachable handleSubmit branch, including the two new ones (success-without-redirect, and a generate_recovery_codes failure), with no UnboundLocalError/NameError."
    verification:
      - kind: integration
        ref: "tests/test_user_setup.py#TestSetupForm.test_handleSubmit (all 5 scenarios)"
        status: pass
    human_judgment: false

duration: ~50min
completed: 2026-08-03
status: complete
---

# Phase 6 Plan 2: Recovery-Code Enrollment Display and Regeneration Summary

**Enrollment mints ten recovery codes and renders them once via a `render()` override on the un-redirected success response; regeneration is the same setup form re-entered through a new portal action, gated by the existing TOTP check.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3
- **Files modified:** 5 (1 created, 5 modified, including the new template)

## Accomplishments

- `SetupForm.handleSubmit` mints ten codes via `generate_recovery_codes(user)` immediately after the success status message is queued, sets `redirect_url = None`, and the final `self.request.response.redirect(...)` call is now conditional on `redirect_url is not None` -- the entire mechanism `plone.z3cform` 0.8.1's `FormWrapper.update()` (read directly from the pinned egg) needs to render the wrapped form's contents in the same response instead of blanking them for a 302.
- A new `render()` override on `SetupForm`: renders `recovery_codes.pt` when `issued_recovery_codes` is populated, otherwise delegates to the inherited `render()`. Exactly one new method; no new base class, no second view.
- `recovery_codes.pt`: a one-time warning, the ten raw (unformatted) codes in an ordered list, a plain-language usage line, and a link back to `@@personal-information`.
- `regenerate_recovery_codes` portal action in the `user` category: `url_expr` routes to `@@setup-two-factor-authentication` (no dedicated regeneration view), `available_expr` reuses `@@show-disable-two-factor-authentication-link` verbatim (globally enabled and this user has enrolled) rather than a fourth `SettingsHelper` method.
- `test_handleSubmit` extended to five scenarios (was three, then four): scenario 1 now asserts no redirect plus ten 16-character codes (a deliberate RECOV-03 behaviour change, see Decisions below); scenarios 2/3 assert `issued_recovery_codes` stays `None`; a new scenario 5 proves a `generate_recovery_codes` failure lands in the existing `except Exception` path with no `UnboundLocalError`/`NameError`.
- `test_recovery_codes_are_issued_once_at_enrollment`: proves the `render()` half end to end -- all ten codes and the one-time warning text appear in the post-enrollment render, and a **fresh** `SetupForm` instance's render contains none of them.
- `test_recovery_code_regeneration_invalidates_the_previous_set`: two consecutive `generate_recovery_codes` calls prove the salt changes, every first-set code is refused afterwards, every second-set code validates once, and regenerating from zero/one/ten previously-stored hashes each yields exactly ten.
- `test_regenerate_recovery_codes_action_is_registered`: asserts both `url_expr` and `available_expr` explicitly, not just the action's existence -- a wrong `available_expr` would misrepresent a security control's state to a non-enrolled user (T-03-23/T-03-21 class).

## Task Commits

1. **Task 1: Issue the codes at enrollment and render them once** -- `dc9deb5` (feat)
2. **Task 2: A visible regeneration path -- one portal action, no new view** -- `6c035ac` (feat)
3. **Task 3: Prove issue-once, never-again, and regeneration-invalidates-all** -- `fdfde6c` (test)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `src/imio/googleauthenticator/browser/forms/user_setup.py` - `issued_recovery_codes`/`recovery_codes_template` class attributes, the mint-and-skip-redirect change inside `handleSubmit`, the new `render()` override
- `src/imio/googleauthenticator/browser/forms/recovery_codes.pt` - new one-time display template
- `src/imio/googleauthenticator/profiles/default/actions.xml` - new `regenerate_recovery_codes` CMF Action
- `src/imio/googleauthenticator/tests/test_user_setup.py` - `test_handleSubmit` scenario changes + new scenario 5; new `test_recovery_codes_are_issued_once_at_enrollment`; `_build_form` fixture fix (see Deviations)
- `src/imio/googleauthenticator/tests/test_helpers.py` - new `test_recovery_code_regeneration_invalidates_the_previous_set` on `TestDriftAndReplay`; `tearDown` extended to clear the two recovery-code properties between test methods
- `src/imio/googleauthenticator/tests/test_generic.py` - new `test_regenerate_recovery_codes_action_is_registered`

## Decisions Made

- **RECOV-03 deliberate behaviour change, recorded per the plan's requirement:** `test_handleSubmit` scenario 1 used to assert `location` ends with `/@@personal-information`. It now asserts `location` is `None`, plus `form.issued_recovery_codes` is a list of ten 16-character strings and `enable_two_factor_authentication` stays `True`. The old assertion encoded "enrollment redirects"; RECOV-03 requires the success response to render the codes instead, which by `FormWrapper.update()`'s own status-code branching means it must not carry a 302/303. The redirect for that one path is what was removed, deliberately.
- Regeneration has no dedicated view or `SettingsHelper` method -- it is the setup form re-entered, reusing `@@show-disable-two-factor-authentication-link` as-is, because that view already means exactly the condition regeneration needs, and the form's existing TOTP check is what keeps a stolen recovery code from perpetuating itself into a fresh set (T-06-08).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, self-introduced, caught before any commit] Malformed XML comment broke every install**
- **Found during:** Task 2, first `bin/test -t test_generic` run
- **Issue:** The explanatory comment added above the new `regenerate_recovery_codes` action in `actions.xml` used `--` (double hyphen) inside an XML comment body twice ("re-entered -- that", "boolean. --"). XML comments may not contain `--` anywhere except as the closing `-->`, so `xml.dom.minidom` (and GenericSetup's importer) raised `ExpatError: not well-formed (invalid token)`, which surfaced as every `_install()`-based test in `test_generic.py` getting an HTTP 500 during profile import.
- **Fix:** Reworded the comment to avoid `--` entirely (one hyphen, "re-entered; that" / "boolean.").
- **Files modified:** `src/imio/googleauthenticator/profiles/default/actions.xml`
- **Verification:** `python2 -c "import xml.dom.minidom as m; m.parse(...)"` confirmed well-formed; `bin/test -t test_generic` then passed 15/15.
- **Committed in:** `6c035ac` (Task 2 commit -- the bug never reached a commit of its own, since it was caught and fixed before staging)

**2. [Rule 3 - Blocking, test-only] `_build_form`'s `other.clear()` silently strips attributes a real request always has**
- **Found during:** Task 3, writing `test_recovery_codes_are_issued_once_at_enrollment`
- **Issue:** `_build_form` calls `self.request.other.clear()` to invalidate a stale cached form value (pre-existing mechanism, unrelated to this plan). `ZPublisher.HTTPRequest.__init__` normally seeds `other['RESPONSE']` and `other['URL']` alongside `self.response`/the script path; clearing `other` wipes both. No prior test in this file ever called `.render()` on the unwrapped `SetupForm` (existing tests only call `handleSubmit` directly and inspect response headers), so this was latent and unexercised until this plan's new test needed a real `render()` call, which drives Plone's standalone default form page template -- that template needs `request.RESPONSE` (unconditionally, in `main_template.pt`) and, via `z3c.form.form.Form.action`, `request.getURL()` (which needs `other['URL']`).
- **Fix:** In `_build_form`, after `self.request.other.clear()`: restore `other['RESPONSE'] = self.request.response`, restore `other['URL'] = self.portal_url` (a valid-enough URL for this fixture's purposes), and set `form.__name__ = 'setup-two-factor-authentication'` (mirroring what `plone.z3cform.layout.FormWrapper.__init__` does in production, avoiding one further `request.getURL()` call site in `plone.app.z3cform`'s macros).
- **Files modified:** `src/imio/googleauthenticator/tests/test_user_setup.py` (test-only; no production code touched)
- **Verification:** `bin/test -t test_user_setup` green (4 tests); re-ran `bin/test -t test_generic`, `test_pas_plugin`, `test_token` afterward to confirm the shared helper's changed behaviour didn't regress anything else using it.
- **Committed in:** `fdfde6c` (Task 3 commit)

**3. `--no-verify` used on all three task commits**
- Per this plan's explicit `<action>` instruction and the project's documented pre-existing 318-finding `bin/code-analysis` debt (CLAUDE.md, scheduled for Phase 8/QUAL-06). Confirmed before each commit that `bin/code-analysis` findings on touched files are exclusively pre-existing isort (`I001`/`I003`/`I004`) noise from an already-out-of-order import block, plus three pre-existing `E265`/`E231`/`E305` findings already present in `user_setup.py` before this plan. No new finding was introduced by this plan's own edits.

---

**Total deviations:** 2 auto-fixed (1 Rule 1 self-caught bug, 1 Rule 3 test-fixture fix) + 1 documented `--no-verify` justification.
**Impact on plan:** Both fixes were necessary to complete the plan as written; neither touches production behaviour beyond what the plan specified. No scope creep.

## Issues Encountered

None beyond the two documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `validate_second_factor` (06-01) and the enrollment/regeneration UI (this plan) are both in place; plan 06-03 can now wire `RECOV-05`'s shared-lockout-counter proof and the low-recovery-code-count warning without touching either.
- `bin/test -t '!robot'` is green at 95 tests (up from 92 at the end of 06-01).
- The `<flagged_assumptions>` RECOV-03 unresolved edge (browser back-button re-POST / cache / screenshot copies outside the application's control) remains open, as recorded in the plan -- out of scope for this plan and not silently dismissed.
- The RECOV-06 "display order matches storage order" backstop truth was not pinned by any assertion in this plan, consistent with the plan's own note that nothing in the implementation depends on that order.

---
*Phase: 06-recovery-codes*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 6 created/modified source files exist on disk (`recovery_codes.pt` created; `user_setup.py`,
`actions.xml`, `test_user_setup.py`, `test_helpers.py`, `test_generic.py` modified); all three task
commits (`dc9deb5`, `6c035ac`, `fdfde6c`) confirmed present in `git log --oneline`.
