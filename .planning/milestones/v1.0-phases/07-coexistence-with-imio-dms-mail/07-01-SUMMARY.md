---
phase: 07-coexistence-with-imio-dms-mail
plan: 01
subsystem: auth
tags: [plone, pas, z3cform, jsregistry, xss, open-redirect, url-encoding]

requires:
  - phase: 04-pas-boundary
    provides: send_2fa_redirect, IPubBeforeCommit-driven challenge redirect, ICameFrom adapter wiring
  - phase: 05-drift-replay-lockout
    provides: the TestTokenFormLockout fixtures (_enable_2fa, _get_browser, _login_browser, _submit_token) this plan's new tests reuse
provides:
  - TokenForm.render() override producing id="login_form" on the served token-form markup
  - Deletion of the vendored plone_ecmascript/popupforms.js client asset and its two jsregistry.xml entries
  - Deletion of the vendored skins/googleauthenticator_custom/login_form.cpt override and its .metadata
  - BUG-01 fix: isURLInPortal validation on the post-token redirect target
  - BUG-06 fix: quote_url=True on CameFromAdapter.getCameFrom()
affects: [07-02-live-templates, 07-03-uninstall-profile, 07-04-human-verify]

tech-stack:
  added: []
  patterns:
    - "z3c.form render() string post-processing to inject an id attribute a template macro cannot emit, documented in a load-bearing docstring rather than a forked template"
    - "Plone's own isURLInPortal idiom reused for redirect-target validation instead of a hand-rolled urlparse host comparison"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/forms/token.py
    - src/imio/googleauthenticator/profiles/default/jsregistry.xml
    - src/imio/googleauthenticator/adapter.py
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/tests/test_setuphandlers.py
    - src/imio/googleauthenticator/tests/test_token.py
    - src/imio/googleauthenticator/tests/test_adapter.py

key-decisions:
  - "R5-vs-WR-03 test placement: followed this repo's own WR-03 precedent (one test method per requirement, grouped by concern) over the plone-write-tests skill's R5 (one class per tested class) -- new COEX-01/COEX-09/BUG-01 tests landed in the existing TestTokenFormLockout class, not a second class, per the plan's explicit resolution."
  - "test_next_url_is_validated_against_the_portal's second (on-site) login uses a recovery code, not a second TOTP code, because both logins land in the same ~30s TOTP interval and validate_token's MFA-06 replay guard would refuse a second acceptance of that interval -- a hazard the plan text did not call out."

requirements-completed: [COEX-01, COEX-02, COEX-03, COEX-09, BUG-01, BUG-06]

coverage:
  - id: D1
    description: "TokenForm.render() inserts id=\"login_form\" on the served token-form markup so Plone's stock overlay script can bind its ajax fetch to it"
    requirement: COEX-01
    verification:
      - kind: unit
        ref: "tests/test_token.py#TestTokenFormLockout.test_token_form_carries_login_form_id"
        status: pass
    human_judgment: false
  - id: D2
    description: "Vendored login_form.cpt override and its .metadata deleted; Plone's own stock login form (restored) is what the header link reaches"
    requirement: COEX-02
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_login_form_override_is_deleted"
        status: pass
    human_judgment: false
  - id: D3
    description: "Vendored plone_ecmascript/popupforms.js and its two jsregistry.xml entries (remove=\"True\" unregistration + our own registration) deleted; Plone's own popupforms.js resource is still registered after install"
    requirement: COEX-03
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_popupforms_js_is_not_vendored"
        status: pass
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_registered_javascript_loads_after_jquery"
        status: pass
    human_judgment: false
  - id: D4
    description: "Header-link-driven login (not a direct POST) reaches the token form and a valid TOTP submitted there completes the login -- automated half only"
    requirement: COEX-09
    verification:
      - kind: unit
        ref: "tests/test_token.py#TestTokenFormLockout.test_login_link_reaches_token_form"
        status: pass
    human_judgment: true
    rationale: "zope.testbrowser has no JavaScript engine, so this test cannot prove the jQuery Tools overlay actually ajax-binds on form#login_form -- only that the markup and redirect chain are correct. The JS-overlay half is the human-verify item plan 07-04 owns."
  - id: D5
    description: "Post-token redirect target validated against the portal with isURLInPortal(); an off-site next_url is refused and falls back to the portal context URL, an on-site one is honoured"
    requirement: BUG-01
    verification:
      - kind: unit
        ref: "tests/test_token.py#TestTokenFormLockout.test_next_url_is_validated_against_the_portal"
        status: pass
    human_judgment: false
  - id: D6
    description: "CameFromAdapter.getCameFrom() percent-encodes the came_from value it reads, round-tripping byte-for-byte through the reader's unquote()"
    requirement: BUG-06
    verification:
      - kind: unit
        ref: "tests/test_adapter.py#TestCameFromAdapter.test_get_came_from_quotes_the_value"
        status: pass
    human_judgment: false

duration: 70min
completed: 2026-08-04
status: complete
---

# Phase 07 Plan 01: Restore Stock Login Overlay and Close the next_url Pipe Summary

**Deleted 507 lines of vendored client-side/skin code (popupforms.js + login_form.cpt) that collided with imio.dms.mail's own jsregistry.xml, replaced the vendoring with a one-line `render()` post-process that inserts `id="login_form"` on the token form, and closed an open redirect (BUG-01) plus a query-string injection (BUG-06) at the two ends of the `next_url` pipe.**

## Performance

- **Duration:** 70 min
- **Started:** 2026-08-04T14:46:59Z (per STATE.md's pre-existing "Phase 07 execution started" timestamp)
- **Completed:** 2026-08-04T15:12:16Z
- **Tasks:** 2
- **Files modified:** 8 (5 modified + 2 deleted in Task 1's scope; 6 modified + 2 deleted in Task 2's scope, with token.py and the two test files touched by both)

## Accomplishments

- `TokenForm.render()` override makes the served `@@google-authenticator-token` markup carry `id="login_form"`, the exact selector Plone's own untouched overlay script binds its ajax overlay on -- restoring COEX-01 without forking `plone.z3cform`'s `titlelessform` macro.
- Deleted the vendored `browser/static/plone_ecmascript/popupforms.js` and both `jsregistry.xml` entries tied to it (the `remove="True"` unregistration of Plone's own copy, and the registration of ours). This package now registers only its own `++resource++imio.googleauthenticator/main.js`, closing the install-order collision with `imio.dms.mail`'s bare reposition entry for the same stock resource id.
- Deleted the vendored `skins/googleauthenticator_custom/login_form.cpt` override and its byte-identical-to-stock `.metadata` file, restoring Plone's own stock login form (three-hunk delta, confirmed below).
- BUG-01: `token.py`'s `handleSubmit` now validates the post-token redirect target with `portal_url_tool.isURLInPortal()` before redirecting -- an off-site `next_url` is refused and falls back to the portal context URL, never a warn-and-continue, never a rewrite.
- BUG-06: `CameFromAdapter.getCameFrom()` now passes `quote_url=True` to `extract_next_url_from_referer`, so a `came_from` containing `&`, `=`, `+` or a space can no longer forge or truncate the `&next_url=...` parameter `pas_plugin.send_2fa_redirect` appends it to.
- Two stale docstrings (in `adapter.py` and `helpers.py`) that claimed Plone's `came_from` field "had to be taken out of the login form" were corrected to say the value is read from the referer's query string, independently of whatever hidden inputs the login form itself renders.

## Task Commits

1. **Task 1: End-to-end "log in through the header link and land on a bindable token form"** - `df39c1d` (feat)
2. **Task 2: Delete the vendored login-form override and close both ends of the next_url pipe** - `6c14064` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `src/imio/googleauthenticator/browser/forms/token.py` - added `render()` (COEX-01) and the `isURLInPortal` redirect guard (BUG-01)
- `src/imio/googleauthenticator/profiles/default/jsregistry.xml` - removed the two vendored-asset entries; `main.js` unchanged
- `src/imio/googleauthenticator/browser/static/plone_ecmascript/popupforms.js` - deleted (COEX-03), directory removed with it
- `src/imio/googleauthenticator/skins/googleauthenticator_custom/login_form.cpt` - deleted (COEX-02)
- `src/imio/googleauthenticator/skins/googleauthenticator_custom/login_form.cpt.metadata` - deleted (COEX-02)
- `src/imio/googleauthenticator/adapter.py` - `quote_url=True` (BUG-06) + docstring correction
- `src/imio/googleauthenticator/helpers.py` - docstring correction only, no logic change
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - fixed `test_registered_javascript_loads_after_jquery`; added `test_popupforms_js_is_not_vendored`, `test_login_form_override_is_deleted`
- `src/imio/googleauthenticator/tests/test_token.py` - added `test_token_form_carries_login_form_id`, `test_login_link_reaches_token_form`, `test_next_url_is_validated_against_the_portal`
- `src/imio/googleauthenticator/tests/test_adapter.py` - added `TestCameFromAdapter` class with `test_get_came_from_quotes_the_value`

## Decisions Made

- **R5-vs-WR-03 test placement** (recorded per the plan's explicit instruction): the plone-write-tests skill's R5 (one test class per tested class, one method per tested method) was overridden in favor of this repo's own WR-03 precedent (one method per *requirement*, grouped by concern). The three new `TokenForm`-facing tests landed in the existing `TestTokenFormLockout` class rather than a new class, reusing its `_enable_2fa`/`_get_browser`/`_login_browser`/`_submit_token` fixtures and the Fernet-key `setUp`/`tearDown` pair.
- **TOTP-interval hazard in the BUG-01 test, found during execution, not called out in the plan**: `test_next_url_is_validated_against_the_portal` needs two *successful* logins in one method (off-site refused, on-site honoured). Two genuine TOTP logins moments apart land in the same or an adjacent ~30-second interval, and `validate_token`'s MFA-06 replay guard refuses a second acceptance of an already-accepted interval. Worked around by using a recovery code (`helpers.generate_recovery_codes`) for the second login instead of a second TOTP code -- recovery codes are not subject to the per-interval guard, and this matches the established precedent in `test_recovery_code_is_accepted_in_place_of_a_token_and_consumed` of alternating credential kinds across sequential logins in one test.
- Confirmed the vendored `login_form.cpt` diff against the stock `Products.CMFPlone` copy is exactly the three hunks the plan's read_first step described (dropping `plone context/@@plone`/`nav_root plone/navigationRootUrl`, building `mail_password` from `portal_url` instead of `nav_root`, and removing the hidden `came_from` input) -- no discrepancy found.
- `browser.getLink('Log in', index=0)` reached the header action with no ambiguity error in either direction; the try/except fallback the plan sketched for a possible `zope.testbrowser`/`mechanize` ambiguity exception was never needed, since `index=0` disambiguates deterministically without raising.

## Deviations from Plan

None - plan executed exactly as written. The TOTP-interval workaround above is a test-fixture choice within the plan's own instructions (the plan named the two behaviors to assert but not the mechanism for making both logins succeed independently), not a deviation from any `<action>` instruction, `<must_have>`, or file scope.

## Non-Vacuity Mutation Checks (per this repo's established standard)

All four required mutation checks were run, reproduced red, and restored byte-identical:

1. **Task 1 - `render()` override reverted to a bare `super().render()` call:** `test_token_form_carries_login_form_id` went red -- the rendered form tag carried `id="form"` (z3c.form's own default), not `id="login_form"`. Restored byte-identical; re-ran green.
2. **Task 2 - `isURLInPortal` guard removed:** `test_next_url_is_validated_against_the_portal` went red with a live `NotFound: no default view (root default view was probably deleted)` error, because the redirect actually reached `http://evil.example.com/` inside the test's fake-host publishing environment -- direct proof the guard's absence is the vulnerability, not merely a missing assertion. Restored byte-identical; re-ran green.
3. **Task 2 - `quote_url=True` reverted to the bare call:** `test_get_came_from_quotes_the_value` went red with `AssertionError: 'plus+space &equals=\xc3\xa9' != 'plus+space '` -- the round-tripped value was truncated at the unquoted `&`, exactly the injection BUG-06 closes. Restored byte-identical; re-ran green.

(The acceptance criteria list a fourth non-vacuity check under Task 1's bullet list that duplicates check #1 above -- both text passages describe the same `render()` mutation; only one run was needed.)

## Issues Encountered

None beyond the TOTP-interval hazard documented above under Decisions Made, which was resolved without needing a checkpoint.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 07-02 can now convert `control_panel_extra.html` and `request_bar_code_reset_email.pt` to `ViewPageTemplateFile` -- both are confirmed still present and untouched (`test -e ... control_panel_extra.html` passed as an acceptance criterion), and `profiles/default/skins.xml`/`configure.zcml` were deliberately left registering the skin layer per the plan's instruction, since 07-02 needs it until it converts those two live templates.
- Plan 07-03 can proceed with the uninstall-profile work; this plan's `assumption_delta_decision` (promote: this package registers/repositions/unregisters only ids under its own `++resource++imio.googleauthenticator/` prefix) is now true in the default profile, and 07-03's planned `test_profile_only_registers_resources_it_owns` invariant test has no known counter-example left to find in `profiles/default/`.
- Plan 07-04's human-verify item (the jQuery Tools overlay actually binding and ajax-loading the token form fragment in a real browser) is unblocked and ready -- this plan's automated tests prove the markup and redirect chain but explicitly cannot prove the JS-level bind, per COEX-09's documented honest limitation.
- No blockers.

## Self-Check: PASSED

- FOUND: `src/imio/googleauthenticator/browser/forms/token.py`
- FOUND: `src/imio/googleauthenticator/browser/static/plone_ecmascript/` deleted
- FOUND: `src/imio/googleauthenticator/skins/googleauthenticator_custom/login_form.cpt` deleted
- FOUND: `src/imio/googleauthenticator/tests/test_adapter.py`
- FOUND: commit `df39c1d`
- FOUND: commit `6c14064`

---
*Phase: 07-coexistence-with-imio-dms-mail*
*Completed: 2026-08-04*
