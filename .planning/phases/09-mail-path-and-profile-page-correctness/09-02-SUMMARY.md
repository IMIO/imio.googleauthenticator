---
phase: 09-mail-path-and-profile-page-correctness
plan: 02
subsystem: auth
tags: [plone, pas-plugin, zope-schema, confused-deputy, i18n]

# Dependency graph
requires:
  - phase: 05
    provides: "IEnhancedUserDataSchema and CustomizedUserDataPanel.omit(), the schema/panel this plan edits"
provides:
  - "enable_two_factor_authentication field description with no wrong-account links"
  - "schema-level test proving the description offers no @@setup-two-factor-authentication or @@disable-two-factor-authentication link"
affects: [phase-13-i18n-catalogue-rebuild]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deletion-over-mitigation for a confused-deputy affordance: remove the link from the only context that renders it rather than making the description conditional per viewer"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/userdataschema.py
    - src/imio/googleauthenticator/tests/test_adapter.py

key-decisions:
  - "D-14: delete both links outright rather than making the description conditional on viewer identity -- a zope.schema description is a static class attribute evaluated at import time"
  - "D-15: replacement text is the sentence already there, 'Enable/disable the two-step verification.'"
  - "D-16: .po/.pot catalogues untouched this phase; the old msgid is orphaned until Phase 13's rebuild"
  - "D-17: test asserts absence of the two view names and of any anchor markup, never the replacement wording"

patterns-established:
  - "Deliberate source deviations get a short comment above the changed code, not only a planning-doc mention (matches userdataschema.py's existing CustomizedUserDataPanel.__init__ comment)"

requirements-completed: [BUG-08]

coverage:
  - id: D1
    description: "enable_two_factor_authentication's description no longer contains @@setup-two-factor-authentication, @@disable-two-factor-authentication, or any <a > anchor markup"
    requirement: BUG-08
    verification:
      - kind: unit
        ref: "tests/test_adapter.py#test_enable_flag_description_offers_no_wrong_account_links"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-06
status: complete
---

# Phase 9 Plan 2: Remove Wrong-Account Links from the 2FA Profile Field Summary

**Deleted the setup/disable links from `enable_two_factor_authentication`'s schema description, the only place they rendered, closing a confused-deputy affordance on the admin-facing `@@user-information` form.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-08-06T12:31:47Z
- **Completed:** 2026-08-06T12:37:32Z
- **Tasks:** 1 (TDD: test then fix)
- **Files modified:** 2

## Accomplishments
- Added a schema-level test (`test_enable_flag_description_offers_no_wrong_account_links`) asserting the description carries neither `@@setup-two-factor-authentication`, `@@disable-two-factor-authentication`, nor any `<a ` anchor markup — proven RED against the unmodified schema first.
- Replaced the two-sentence, two-link description on `IEnhancedUserDataSchema['enable_two_factor_authentication']` with the single sentence that already opened it, leaving title, type (`Bool`) and `required=False` unchanged.
- Added a short in-source comment above the field recording why the deletion is safe and that the orphaned msgid is a known Phase 13 input — matching the package's existing convention of commenting deliberate deviations (`CustomizedUserDataPanel.__init__`'s comment three lines above).

## Task Commits

Each task was committed atomically (TDD RED/GREEN):

1. **Task 1 STEP 1 (RED):** add failing test for BUG-08 wrong-account links — `0e2e569` (test)
2. **Task 1 STEP 2 (GREEN):** remove wrong-account links from the description — `9a8b71f` (fix)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `src/imio/googleauthenticator/userdataschema.py` — `enable_two_factor_authentication`'s description shortened to one sentence; three-line comment added recording the deliberate deletion and its Phase 13 consequence.
- `src/imio/googleauthenticator/tests/test_adapter.py` — new test method on `TestEnhancedUserDataPanelAdapter` asserting absence of both view names and anchor markup in the field description.

## Decisions Made
- Followed D-14 through D-17 exactly as CONTEXT.md specified: delete outright (not conditional), replacement is the pre-existing first sentence, catalogues untouched, test asserts absence not wording. No deviation from the plan's decisions.

## Deviations from Plan

None — plan executed exactly as written. No Rule 1-4 auto-fixes were needed; the fix was the single string-literal deletion the plan specified.

## Non-Vacuity Check (verbatim RED output)

Ran `bin/test -t test_enable_flag_description_offers_no_wrong_account_links` against the unmodified `userdataschema.py`, before any source edit:

```
Failure in test test_enable_flag_description_offers_no_wrong_account_links (imio.googleauthenticator.tests.test_adapter.TestEnhancedUserDataPanelAdapter)
Traceback (most recent call last):
  File "/srv/cache/eggs/unittest2-0.5.1-py2.7-linux-x86_64.egg/unittest2/case.py", line 340, in run
    testMethod()
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/tests/test_adapter.py", line 145, in test_enable_flag_description_offers_no_wrong_account_links
    'The description still links to the setup view, which acts on '
  File "/srv/cache/eggs/unittest2-0.5.1-py2.7-linux-x86_64.egg/unittest2/case.py", line 820, in assertNotIn
    self.fail(self._formatMessage(msg, standardMsg))
  File "/srv/cache/eggs/unittest2-0.5.1-py2.7-linux-x86_64.egg/unittest2/case.py", line 415, in fail
    raise self.failureException(msg)
AssertionError: '@@setup-two-factor-authentication' unexpectedly found in u'Enable/disable the two-step verification. Click <a href="@@setup-two-factor-authentication"> here</a> to set it up or <a href="@@disable-two-factor-authentication">here</a> to disable it.' : The description still links to the setup view, which acts on the viewer's own account, not the profile being viewed.

  Ran 1 tests with 1 failures and 0 errors in 0.005 seconds.
```

Test then committed alone (RED gate), the fix applied, and the same test re-run GREEN before the fix commit (GREEN gate).

## TDD Gate Compliance

- RED gate: `test(09-02): add failing test for BUG-08 wrong-account links` — `0e2e569`
- GREEN gate: `fix(09-02): remove wrong-account links from the 2FA profile field description` — `9a8b71f`
- No REFACTOR commit needed — the fix was already minimal.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- BUG-08 closed. `@@user-information` now offers no link that acts on the viewing administrator's own account.
- The `.po`/`.pot` catalogues carry an orphaned msgid for the old two-sentence description; this is expected and tracked as a Phase 13 (I18N-02) input per D-16 — no action needed here.
- No blockers for the remaining Phase 9 plans (UX-01, UX-02), which touch disjoint files (`recovery_codes.pt`, `helpers.py`).

---
*Phase: 09-mail-path-and-profile-page-correctness*
*Completed: 2026-08-06*

## Self-Check: PASSED

- FOUND: src/imio/googleauthenticator/userdataschema.py
- FOUND: src/imio/googleauthenticator/tests/test_adapter.py
- FOUND: this SUMMARY.md
- FOUND commit 0e2e569 (test, RED gate)
- FOUND commit 9a8b71f (fix, GREEN gate)
