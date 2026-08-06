---
phase: 07-coexistence-with-imio-dms-mail
plan: 03
subsystem: auth
tags: [plone, genericsetup, resourceregistries, uninstall, jsregistry, cssregistry, docs]

requires:
  - phase: 07-coexistence-with-imio-dms-mail
    provides: "plan 07-01's deletion of the vendored popupforms.js/jsregistry.xml removal entry, and the promoted ownership-prefix assumption-delta decision this plan's invariant test pins"
  - phase: 07-coexistence-with-imio-dms-mail
    provides: "plan 07-02's deletion of profiles/default/skins.xml and the skin mechanism, which is what makes profiles/uninstall/skins.xml obsolete"
provides:
  - "profiles/uninstall/jsregistry.xml and profiles/uninstall/cssregistry.xml -- unregister exactly ++resource++imio.googleauthenticator/main.js and main.css"
  - "test_uninstall_restores_resource_registries, test_popupforms_js_survives_either_install_order, test_profile_only_registers_resources_it_owns -- three new TestSetupHandlers methods"
  - "README.rst/docs/index.rst corrected to state the ownership invariant instead of claiming an override of Plone's login form/overlay script"
  - "CHANGES.rst Phase 7 entry with the operator upgrade note for a ZODB where the old removal entry already ran"
affects: [07-04-human-verify]

tech-stack:
  added: []
  patterns:
    - "GenericSetup uninstall profile scoped to exactly the ids the matching default-profile file registers, verified by an XML-parsing invariant test rather than a code comment"
    - "Synthetic collision replay via the resource-registry tool's own moveResourceAfter, standing in for a second package's real jsregistry.xml reposition entry when that package's egg is not installed in the test fixture"

key-files:
  created:
    - src/imio/googleauthenticator/profiles/uninstall/jsregistry.xml
    - src/imio/googleauthenticator/profiles/uninstall/cssregistry.xml
  modified:
    - src/imio/googleauthenticator/tests/test_setuphandlers.py
    - README.rst
    - docs/index.rst
    - CHANGES.rst

key-decisions:
  - "profiles/uninstall/skins.xml deleted in the same commit that adds the two new registry-uninstall files, rather than a separate commit -- keeps the uninstall profile directory from ever being empty on disk between commits."
  - "The synthetic collision test (test_popupforms_js_survives_either_install_order) replays imio.dms.mail's reposition via portal_javascripts.moveResourceAfter('popupforms.js', 'form_tabbing.js') directly, rather than constructing and importing a fake profile fragment -- both ids are the verbatim ones read from the real imio.dms.mail source, and moveResourceAfter is the exact tool method GenericSetup's own _initResources dispatches an insert-after directive to."
  - "No explicit tearDown reset was needed for the registry-mutating tests: test_uninstall_restores_resource_registries's own step (e) re-applies the default profile as its last action, which restores the installed state other tests in the layer expect. Verified by re-running the full '!robot' suite (110/110 green) rather than assumed."

requirements-completed: [COEX-03, COEX-06, COEX-07]

coverage:
  - id: D1
    description: "profiles/uninstall/ unregisters exactly ++resource++imio.googleauthenticator/main.js and main.css, leaves Plone's own popupforms.js registered, is idempotent, and is reversible by re-applying the default profile"
    requirement: COEX-06
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_uninstall_restores_resource_registries"
        status: pass
    human_judgment: false
  - id: D2
    description: "imio.dms.mail's real bare reposition entry for popupforms.js does not duplicate or delete that resource, replayed in both application orders and under a repeated profile import -- the automated half of the coexistence proof"
    requirement: COEX-07
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_popupforms_js_survives_either_install_order"
        status: pass
    human_judgment: true
    rationale: "This is a synthetic replay against portal_javascripts, not a real two-egg install of imio.dms.mail alongside this package. The docstring says so explicitly. The real proof is plan 07-04's human-verify item; a verification report claiming COEX-07 is fully automated by this test alone would be wrong."
  - id: D3
    description: "Every id attribute across all four resource-registry profile files (default and uninstall, jsregistry and cssregistry) begins with ++resource++imio.googleauthenticator/ -- the ownership invariant that keeps the collision closed against future edits"
    requirement: COEX-03
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#TestSetupHandlers.test_profile_only_registers_resources_it_owns"
        status: pass
    human_judgment: false
  - id: D4
    description: "README.rst and docs/index.rst no longer claim this package overrides Plone's login form or overlay script; both now state the ownership invariant and its imio.dms.mail coexistence consequence"
    verification:
      - kind: unit
        ref: "tests/test_generic.py#TestGeneric.test_long_description_does_not_fall_into_setup_pys_bare_except"
        status: pass
      - kind: other
        ref: "grep -c 'has been overridden' README.rst docs/index.rst -- both 0"
        status: pass
    human_judgment: false
  - id: D5
    description: "CHANGES.rst carries the Phase 7 entry with requirement ids and the operator recovery instruction for a ZODB where the old removal entry already ran"
    verification:
      - kind: other
        ref: "grep -q 'COEX-06' CHANGES.rst; grep -q 'BUG-01' CHANGES.rst; grep -q 'portal_setup' CHANGES.rst -- all succeed"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-04
status: complete
---

# Phase 07 Plan 03: Uninstall Profile, Coexistence Proof, and Documentation Correction Summary

**A `profiles/uninstall/` scoped to exactly `main.js`/`main.css`, an invariant test that fails the day any of the four resource-registry files names an id this package does not own, a synthetic replay of `imio.dms.mail`'s real reposition entry proving the collision stays closed in both install orders, and three shipped documents corrected to stop claiming an override that no longer exists.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-04T16:04Z
- **Tasks:** 2
- **Files modified:** 6 (2 new XML files, 1 test file, 3 documentation files)

## Accomplishments

- `profiles/uninstall/jsregistry.xml` and `profiles/uninstall/cssregistry.xml` each carry exactly one entry, mirroring `profiles/default/jsregistry.xml`/`cssregistry.xml`'s surviving ids verbatim plus `remove="True"`, and nothing else. `profiles/uninstall/skins.xml` deleted in the same commit -- plan 07-02 already removed the skin layer it used to un-register, and an uninstall profile directory carrying a file with nothing left to un-register is exactly the unexecuted-path hazard RESEARCH.md's Open Question 1 flagged.
- `test_uninstall_restores_resource_registries` proves, in one method per WR-03: both resources are registered before the uninstall (non-vacuity); both are gone after it; **Plone's own `popupforms.js` is still registered** after the uninstall (the assertion that actually matters -- uninstalling this add-on must not leave the whole site without Plone's overlay script); applying the uninstall profile twice raises nothing and changes nothing (`BaseRegistry.unregisterResource` filters the resource tuple, so a missing id is a no-op); and re-applying the default profile re-registers both resources, proving the uninstall is reversible rather than destructive.
- `test_popupforms_js_survives_either_install_order` replays the real `imio.dms.mail` fragment -- `<javascript id="popupforms.js" insert-after="form_tabbing.js" />`, read verbatim from `imio/dms/mail/profiles/default/jsregistry.xml` around line 102 -- via `portal_javascripts.moveResourceAfter('popupforms.js', 'form_tabbing.js')`, and asserts `popupforms.js` appears exactly once (never 0, never 2, via `list.count()` rather than `assertIn`) in both application orders and under a repeated default-profile import.
- `test_profile_only_registers_resources_it_owns` parses all four resource-registry profile files with `minidom` and asserts every `<javascript>`/`<stylesheet>` `id` attribute starts with `++resource++imio.googleauthenticator/`, with a non-vacuity control on the total node count (>= 4). This is the invariant promoted from plan 07-01's assumption-delta decision.
- `README.rst` and `docs/index.rst`'s "Notes" bullets rewritten: this package ships no override of Plone's login form and no copy of `popupforms.js`; `TokenForm` renders the `id="login_form"` attribute the stock overlay script binds on; and the coexistence consequence is stated explicitly -- registering only resources under this package's own prefix, and never unregistering one it does not own, means installing alongside `imio.dms.mail` (which repositions `popupforms.js`) cannot break it regardless of install order.
- `CHANGES.rst` gained the Phase 7 entry citing COEX-01 through COEX-07, BUG-01 and BUG-06, plus an explicit upgrade note: a site that already applied the old removal entry has `popupforms.js` unregistered from `portal_javascripts`, this release cannot re-register it (only Plone's own profile does), and the recovery is re-running `Products.CMFPlone`'s `jsregistry` import step from `portal_setup` or recreating the site -- with the stale `googleauthenticator_custom` skin layer named as the second leftover artifact.

## Task Commits

1. **Task 1: Ship an uninstall profile scoped to this package's own two resources, and pin the ownership invariant** - `31cb9a9` (feat)
2. **Task 2: Correct the three documents that still describe this package as overriding Plone's assets** - `0ca0566` (docs)

**Plan metadata:** pending (this commit)

## Files Created/Modified

- `src/imio/googleauthenticator/profiles/uninstall/jsregistry.xml` - new, unregisters `++resource++imio.googleauthenticator/main.js` only
- `src/imio/googleauthenticator/profiles/uninstall/cssregistry.xml` - new, unregisters `++resource++imio.googleauthenticator/main.css` only
- `src/imio/googleauthenticator/profiles/uninstall/skins.xml` - deleted, nothing left to un-register
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - added `CSSREGISTRY_XML`/`UNINSTALL_JSREGISTRY_XML`/`UNINSTALL_CSSREGISTRY_XML` module constants, `_replay_dms_mail_reposition` helper, and the three new test methods
- `README.rst` - corrected "Notes" bullets, ownership statement
- `docs/index.rst` - same correction, matched to README.rst per the standing "stale duplicate, minimal sync" decision
- `CHANGES.rst` - Phase 7 entry with requirement ids and the operator upgrade note

## Decisions Made

- **`skins.xml` deletion co-located with the two new files, one commit**: keeps the uninstall profile directory from ever being observed empty in git history, addressing RESEARCH.md Open Question 1 (an unexecuted empty-uninstall-directory path).
- **Synthetic replay via `moveResourceAfter` directly, not a fabricated GenericSetup import**: the real `imio.dms.mail` entry carries no attribute but `id` and `insert-after`, and `_initResources` (read from the installed `Products.ResourceRegistries` egg) dispatches that shape straight to `moveResourceAfter` with no registration call at all -- calling the tool method directly is the same operation, not an approximation of it.
- **No dedicated `tearDown` reset added**: `test_uninstall_restores_resource_registries`'s reversibility assertion (step (e), re-applying the default profile) restores the installed state as a side effect, and the full `!robot` suite re-run at 110/110 green confirms no state leaked into the shared integration layer. Documented explicitly per the plan's instruction rather than assumed.

## Deviations from Plan

None - plan executed exactly as written. Both tasks landed in the file scope and commit shape the plan specified (one commit each), and no Rule 1-4 auto-fix was needed.

## Non-Vacuity Mutation Checks (per this repo's established standard)

All three mutation checks the plan's acceptance criteria named were run, reproduced red, and restored byte-identical:

1. **Task 1 - changed the id in `profiles/uninstall/jsregistry.xml` from `main.js` to a non-existent `main-nonexistent.js`:** `test_uninstall_restores_resource_registries` went red with `AssertionError: '++resource++imio.googleauthenticator/main.js' unexpectedly found in [...]` -- the uninstall no longer removed the real resource. Restored byte-identical; re-ran green.
2. **Task 1 - re-added a `<javascript id="popupforms.js" remove="True"/>` entry to `profiles/default/jsregistry.xml`:** both named tests went red. `test_popupforms_js_survives_either_install_order` failed its own non-vacuity control (`'popupforms.js' not found` -- the default profile's own re-application had just deleted it before the reposition replay ran). `test_profile_only_registers_resources_it_owns` failed with `Lists differ: [] != [u'popupforms.js']` -- the reintroduced bare id violates the ownership invariant. Restored byte-identical; both re-ran green.
3. **Task 1 - added a bare `<javascript id="popupforms.js" remove="True"/>` entry to `profiles/uninstall/jsregistry.xml`:** `test_profile_only_registers_resources_it_owns` went red with the same `Lists differ: [] != [u'popupforms.js']` failure. Restored byte-identical; re-ran green.

Full `bin/test -t '!robot'` suite re-ran green (110/110) after each restoration, confirming no state leaked into the shared integration layer from any of the mutations or their fixes.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Operational Note (carried forward per the plan's instruction, not a code task)

**Deleting the removal entry from `profiles/default/jsregistry.xml` (plan 07-01) stops this package deleting Plone's `popupforms.js` resource on *future* installs. It does not heal a ZODB where that deletion already happened.** Nothing in this package re-registers `popupforms.js` -- only `Products.CMFPlone`'s own profile does. On the MOD-1076 `server.dmsmail` evaluation site (or any site that ran a previous version of this package's install), upgrading the egg and re-applying this package's profile will **not** bring the overlay script back. The recovery, now written into `CHANGES.rst`'s Phase 7 entry: re-run `Products.CMFPlone`'s own `jsregistry` import step from `portal_setup`, or recreate the site. The stale `googleauthenticator_custom` skin layer left in `portal_skins` on that same site (from a version predating plan 07-02) is the second such leftover artifact to clear. Both belong in the operator handover; plan 07-04's checkpoint carries this forward into its human-verify instructions.

## Next Phase Readiness

- Plan 07-04 (human-verify) is unblocked: this plan's automated tests close COEX-06 and the invariant half of COEX-03, and prove COEX-07's automated half (both install orders, synthetic replay). The residual for 07-04 is the real two-egg install of `imio.googleauthenticator` alongside `imio.dms.mail` and the operator-facing MOD-1076 recovery instructions above.
- No blockers.

## Self-Check: PASSED

- FOUND: `src/imio/googleauthenticator/profiles/uninstall/jsregistry.xml`
- FOUND: `src/imio/googleauthenticator/profiles/uninstall/cssregistry.xml`
- MISSING (confirmed intentional): `src/imio/googleauthenticator/profiles/uninstall/skins.xml` -- deleted, nothing left to un-register
- FOUND: commit `31cb9a9`
- FOUND: commit `0ca0566`

---
*Phase: 07-coexistence-with-imio-dms-mail*
*Completed: 2026-08-04*
