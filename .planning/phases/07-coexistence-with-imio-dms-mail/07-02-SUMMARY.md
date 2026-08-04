---
phase: 07-coexistence-with-imio-dms-mail
plan: 02
subsystem: auth
tags: [plone, pas, z3cform, viewpagetemplatefile, genericsetup, skins]

requires:
  - phase: 07-coexistence-with-imio-dms-mail
    provides: "plan 07-01's confirmation that control_panel_extra.html and request_bar_code_reset_email.pt were still present and untouched, and that profiles/default/skins.xml / configure.zcml's cmf:registerDirectory were deliberately left registering the skin layer until this plan converted the two live templates"
provides:
  - "GoogleAuthenticatorSettingsEditForm.additional_template and RequestBarCodeResetForm.mail_text_template -- ViewPageTemplateFile class attributes replacing skin-name restrictedTraverse lookups"
  - "Deletion of the skin mechanism entirely: skins/ tree, profiles/default/skins.xml, configure.zcml's cmf:registerDirectory + xmlns:cmf, and the MANIFEST.in include"
  - "tests/test_controlpanel.py -- first-ever coverage of GoogleAuthenticatorSettingsEditForm.render()"
  - "tests/test_generic.py::test_no_restrictedTraverse_left_in_browser_code and tests/test_setuphandlers.py::test_skin_layer_is_removed -- regression pins for both COEX-04 and COEX-05"
affects: [07-03-uninstall-profile, 07-04-human-verify]

tech-stack:
  added: []
  patterns:
    - "ViewPageTemplateFile class attribute (Products.Five.browser.pagetemplatefile) for a view's own auxiliary template fragment, replacing a skin-name restrictedTraverse lookup -- the same idiom browser/forms/user_setup.py already used for recovery_codes.pt, now extended to two more fragments"

key-files:
  created:
    - src/imio/googleauthenticator/browser/templates/control_panel_extra.pt
    - src/imio/googleauthenticator/browser/forms/templates/request_bar_code_reset_email.pt
    - src/imio/googleauthenticator/tests/test_controlpanel.py
  modified:
    - src/imio/googleauthenticator/browser/controlpanel.py
    - src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py
    - src/imio/googleauthenticator/configure.zcml
    - MANIFEST.in
    - src/imio/googleauthenticator/tests/test_generic.py
    - src/imio/googleauthenticator/tests/test_request_bar_code_reset.py
    - src/imio/googleauthenticator/tests/test_setuphandlers.py

key-decisions:
  - "Non-vacuity control for test_render_appends_the_extra_links: called the parent class's render() directly via super(GoogleAuthenticatorSettingsEditForm, form).render() (the same call render() itself makes internally to compute `res`) and asserted the full result both startswith() that base string and is strictly longer -- proving the fragment was appended, not merely present as a coincidental substring."
  - "The Task 1/Task 2 commit boundary drifted from the plan's file split: test_no_restrictedTraverse_left_in_browser_code (COEX-04) and the test_resources_are_registered docstring correction landed in Task 1's commit alongside the other test_generic.py edits, rather than in Task 2's commit with test_setuphandlers.py. Content matches the plan exactly; only which commit it landed in differs."
  - "git mv leaves an empty directory on disk (git does not track empty dirs) -- after relocating both templates out of skins/googleauthenticator_custom/, an explicit rm -rf was still needed before test_skin_layer_is_removed's os.path.exists(skins_dir) assertion could pass, since os.path.exists() is True for an empty directory."

requirements-completed: [COEX-04, COEX-05]

coverage:
  - id: D1
    description: "GoogleAuthenticatorSettingsEditForm.additional_template and RequestBarCodeResetForm.mail_text_template reach their auxiliary templates through ViewPageTemplateFile class attributes; no restrictedTraverse skin-name lookup remains under browser/"
    requirement: COEX-04
    verification:
      - kind: unit
        ref: "tests/test_controlpanel.py#TestGoogleAuthenticatorSettingsEditForm.test_render_appends_the_extra_links"
        status: pass
      - kind: unit
        ref: "tests/test_generic.py#TestGeneric.test_no_restrictedTraverse_left_in_browser_code"
        status: pass
      - kind: unit
        ref: "tests/test_request_bar_code_reset.py#TestRequestBarCodeReset.test_reset_email_survives_a_non_ascii_sender_name"
        status: pass
    human_judgment: false
  - id: D2
    description: "The skin mechanism (skins/ directory, profiles/default/skins.xml, configure.zcml's cmf:registerDirectory + xmlns:cmf, MANIFEST.in's include) is deleted entirely, and no googleauthenticator_custom object is created in portal_skins on install"
    requirement: COEX-05
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_skin_layer_is_removed"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-04
status: complete
---

# Phase 07 Plan 02: Convert Live Templates to Descriptors and Delete the Skin Mechanism Summary

**Both remaining live skin templates (the control-panel "Extra" fragment and the bar-code reset email) now render through `ViewPageTemplateFile` class attributes instead of skin-name `restrictedTraverse` lookups, and the entire `portal_skins` layer this package used to register is gone -- directory, GenericSetup profile file, ZCML registration, and packaging include.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-04T15:44Z
- **Tasks:** 2
- **Files modified:** 10 (2 relocated templates, 2 production modules, `configure.zcml`, `MANIFEST.in`, 1 deleted profile file, 3 test files + 1 new test file)

## Accomplishments

- `control_panel_extra.html` and `request_bar_code_reset_email.pt` relocated via `git mv` to `browser/templates/control_panel_extra.pt` and `browser/forms/templates/request_bar_code_reset_email.pt` respectively -- both bodies confirmed byte-identical to their pre-commit originals (diffed against `git show HEAD` of the prior commit).
- `GoogleAuthenticatorSettingsEditForm.additional_template` and `RequestBarCodeResetForm.mail_text_template`, both `ViewPageTemplateFile` class attributes, replace the two skin-name `restrictedTraverse` lookups. `render()` and `handleSubmit` call the new attributes directly; the `mail_text.format(bar_code_reset_url=...)` substitution that fills the template's literal `{bar_code_reset_url}` placeholder is untouched.
- The skin mechanism is fully deleted: `skins/` tree (including the now-empty `googleauthenticator_custom` directory, which required an explicit `rm -rf` after `git mv` -- git does not remove empty directories on its own), `profiles/default/skins.xml`, `configure.zcml`'s `cmf:registerDirectory` element and its now-unused `xmlns:cmf` declaration, and `MANIFEST.in`'s `recursive-include ... skins *` line. `profiles/uninstall/skins.xml` deliberately left in place, per the plan -- plan 07-03 owns it.
- New `tests/test_controlpanel.py::TestGoogleAuthenticatorSettingsEditForm.test_render_appends_the_extra_links` closes the previously **zero-coverage** control-panel `render()` path -- confirmed by reading `test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken`, which instantiates the same form but only ever calls `update()`/`handleSave`, never `render()`.
- Two new regression-pinning tests: `tests/test_generic.py::test_no_restrictedTraverse_left_in_browser_code` (walks every `.py` file under `browser/` via `os.walk`, asserting none contains the string `restrictedTraverse`) and `tests/test_setuphandlers.py::test_skin_layer_is_removed` (four assertions: directory absent, `skins.xml` absent, `configure.zcml` carries no `registerDirectory` element, and the live outcome -- no `googleauthenticator_custom` object created in `portal_skins`, with Plone's own `custom` layer as the non-vacuity control).
- `tests/test_request_bar_code_reset.py`'s `setUp` no longer calls `self.portal.setupCurrentSkin(...)` -- the comment explaining why it was needed ("the email body is a skin template") is now false, and the three pre-existing email tests pass unmodified with no skin bound to the request, proving the relocated template needs none.
- `tests/test_generic.py::test_manifest_ships_the_profile_and_catalogues`'s `required` tuple no longer names the deleted `skins` directive, and `test_resources_are_registered`'s docstring no longer lists `skins.xml`'s directory-view prefix among "the files that must agree" (three remain: the `resourceDirectory` name, the `jsregistry.xml` id, the `cssregistry.xml` id).

## Task Commits

1. **Task 1: Convert both live templates to view-class template descriptors and delete the skin mechanism** - `925ea17` (feat)
2. **Task 2: Pin both deletions with absence assertions** - `726d24d` (test)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `src/imio/googleauthenticator/browser/templates/control_panel_extra.pt` - relocated, byte-identical body
- `src/imio/googleauthenticator/browser/forms/templates/request_bar_code_reset_email.pt` - relocated, byte-identical body
- `src/imio/googleauthenticator/browser/controlpanel.py` - `additional_template` class attribute; `render()` calls it directly
- `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py` - `mail_text_template` class attribute; `handleSubmit` calls it directly
- `src/imio/googleauthenticator/configure.zcml` - `cmf:registerDirectory` and `xmlns:cmf` removed
- `MANIFEST.in` - stale `skins` include line removed
- `src/imio/googleauthenticator/profiles/default/skins.xml` - deleted
- `src/imio/googleauthenticator/tests/test_controlpanel.py` - new file, `TestGoogleAuthenticatorSettingsEditForm.test_render_appends_the_extra_links`
- `src/imio/googleauthenticator/tests/test_generic.py` - MANIFEST tuple edit, docstring correction, new `test_no_restrictedTraverse_left_in_browser_code`
- `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py` - dead `setupCurrentSkin` call and its comment removed from `setUp`
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - new `test_skin_layer_is_removed`

## Decisions Made

- **Non-vacuity control for `test_render_appends_the_extra_links`:** called `super(GoogleAuthenticatorSettingsEditForm, form).render()` directly -- the identical call `render()` itself makes internally to compute `res` -- then asserted `full_result.startswith(base_result)` and `len(full_result) > len(base_result)`. This proves the fragment was actually appended rather than the base form happening to already contain a matching substring, per the plan's own guidance to "pick whichever form is honest given what `super().render()` returns."
- **Task 1/Task 2 commit-boundary drift:** `test_no_restrictedTraverse_left_in_browser_code` and the `test_resources_are_registered` docstring correction (both nominally Task 2) landed in Task 1's commit together with the rest of `test_generic.py`'s edits, since both were edited in the same file-editing pass before the first commit was made. Content is exactly as the plan specifies; only the commit each change belongs to differs from the plan's task split. Documented rather than re-split via a follow-up commit, since re-splitting after the fact would require an amend or a revert-and-reapply, neither of which improves the historical record.
- **`git mv` leaves an empty directory:** relocating both templates out of `skins/googleauthenticator_custom/` with `git mv` emptied the directory in git's index but left it physically present on disk (git does not track or remove empty directories). `test_skin_layer_is_removed`'s `os.path.exists(skins_dir)` assertion caught this immediately (it went red on first run) because `os.path.exists()` returns `True` for an empty directory. Fixed with an explicit `rm -rf`.

## Deviations from Plan

None beyond the two documented above under Decisions Made (the commit-boundary drift and the empty-directory fix), neither of which changed the plan's intended file scope, `<action>` instructions, or `<must_have>`s.

## Non-Vacuity Mutation Checks (per this repo's established standard)

All checks named in the plan's acceptance criteria were run, reproduced red, and restored byte-identical:

1. **Task 1 -- `additional_template` renamed locally so the lookup misses:** `test_render_appends_the_extra_links` went red with `AttributeError: 'GoogleAuthenticatorSettingsEditForm' object has no attribute 'additional_template'`. Restored byte-identical (confirmed via `git diff` against the intended Task 1 edit set); re-ran green.
2. **Task 1 -- `mail_text_template` renamed locally so the lookup misses:** `test_reset_email_survives_a_non_ascii_sender_name` went red with `AttributeError: 'RequestBarCodeResetForm' object has no attribute 'mail_text_template'`. Restored byte-identical; re-ran green.
3. **Task 2 -- re-adding a `cmf:registerDirectory` element to `configure.zcml` without its namespace declaration:** `test_skin_layer_is_removed` could not even run -- ZCML parsing raised `ZopeSAXParseException: ... unbound prefix` before any test executed, which is a *harsher* red than the planned assertion failure but proves the same point: the registration string's absence is load-bearing. Restored byte-identical; full suite re-ran green (107/107).
4. **Task 2 -- pointing the `browser/` walk at a non-existent directory:** `test_no_restrictedTraverse_left_in_browser_code` went red on its own non-vacuity control (`AssertionError: [] is not True : Non-vacuity control: no .py files found...`) before ever reaching the `restrictedTraverse` absence loop -- proving the walk-root guard itself works. Restored byte-identical; re-ran green.

Additionally, both relocated template bodies were diffed against their pre-commit originals (`git show HEAD^:...` for the commit that preceded this plan) with `diff`, producing no output -- confirming the "no TAL edit" claim in the plan's must-haves.

## Issues Encountered

None beyond the empty-directory artifact documented above under Decisions Made, resolved without needing a checkpoint.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 07-03 (uninstall profile) can proceed: `profiles/uninstall/skins.xml` was deliberately left in place per this plan's own instruction, and the deletion of `profiles/default/skins.xml` plus `configure.zcml`'s `cmf:registerDirectory` in this plan means 07-03 now owns the last remaining skins-related registration to reconcile.
- Plan 07-04's human-verify item is unaffected by this plan -- no changes to the login overlay or the `next_url` pipe (plan 07-01's scope) were made here.
- No blockers.

## Self-Check: PASSED

- FOUND: `src/imio/googleauthenticator/browser/templates/control_panel_extra.pt`
- FOUND: `src/imio/googleauthenticator/browser/forms/templates/request_bar_code_reset_email.pt`
- FOUND: `src/imio/googleauthenticator/tests/test_controlpanel.py`
- MISSING (confirmed intentional): `src/imio/googleauthenticator/skins/` -- deleted, per COEX-05
- MISSING (confirmed intentional): `src/imio/googleauthenticator/profiles/default/skins.xml` -- deleted, per COEX-05
- FOUND: commit `925ea17`
- FOUND: commit `726d24d`

---
*Phase: 07-coexistence-with-imio-dms-mail*
*Completed: 2026-08-04*
