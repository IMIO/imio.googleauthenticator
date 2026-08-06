---
phase: 02-registry-seeding-and-import-step-ordering
plan: 01
subsystem: auth
tags: [genericsetup, plone.registry, pas, ska, testing]

requires:
  - phase: 01-rename-and-fail-closed
    provides: "_dont_swallow_my_exceptions = True on the PAS plugin, so a propagating KeyError from get_app_settings() surfaces as a 500 rather than a silent password-only fallthrough"
provides:
  - "Declared import-step ordering: imio.googleauthenticator's GenericSetup import step depends on plone.app.registry"
  - "A permanent test asserting that ordering via getSortedImportSteps(), rather than relying on it holding by accident"
  - "ska_secret_key no longer seeded at install time; setupVarious does only the marker-file guard and _add_plugin"
  - "ska_secret_key minted lazily, once, inside get_ska_secret_key() on first use"
  - "A regression guard proving a profile re-apply does not reset an existing ska_secret_key"
affects: [02-02-ska-key-separation]

tech-stack:
  added: []
  patterns:
    - "Import-step ordering declared via <depends name=\"...\"/> child element on genericsetup:importStep, asserted in the suite via portal_setup.getSortedImportSteps()"
    - "Lazy-mint-on-first-use: a single 'if not <value>:' branch inside the accessor is the sole birthplace of a registry-backed secret, no separate get_or_create wrapper"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_setuphandlers.py
  modified:
    - src/imio/googleauthenticator/configure.zcml
    - src/imio/googleauthenticator/setuphandlers.py
    - src/imio/googleauthenticator/helpers.py

key-decisions:
  - "REG-01 is proven by the ordering assertion alone (D-01/D-02) — no second-site fixture, no manual site-creation run; the ROADMAP log-check criterion is a verification:backstop must_have that the verifier should abstain on, not fail"
  - "_setup_secret_key deleted outright with no install-time seeding fallback retained (D-04)"
  - "Mint lives inside get_ska_secret_key() as one unconditional 'if not ska_secret_key:' branch, no create= kwarg, no get_or_create_ska_secret_key() wrapper (D-05)"
  - "REG-05's double-apply test documented in its own docstring as a regression guard against a future schema tightening, not a fix for a currently-firing bug (D-13)"

requirements-completed: [REG-01, REG-02, REG-03, REG-04, REG-05]

coverage:
  - id: D1
    description: "imio.googleauthenticator's import step is declared to run after plone.app.registry (<depends name=\"plone.app.registry\"/>)"
    requirement: "REG-02"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#TestSetupHandlers.test_setupVarious (ORDERING group)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The resulting order is asserted via getSortedImportSteps(), not left to string-hash chance"
    requirement: "REG-03"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#TestSetupHandlers.test_setupVarious (ORDERING group)"
        status: pass
    human_judgment: false
  - id: D3
    description: "After install, all three IGoogleAuthenticatorSettings records exist and get_app_settings() returns without raising (REG-01 outcome half)"
    requirement: "REG-01"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#TestSetupHandlers.test_setupVarious (RECORDS group)"
        status: pass
    human_judgment: true
    rationale: "REG-01's ROADMAP criterion is a var/log/instance.log check from a real site-creation run (D-01/D-02), which this phase deliberately does not automate. The mechanised RECORDS/ORDERING assertions are the proven control; the log-based backstop must_have is out of reach for this test suite and is left to human verification per D-02."
  - id: D4
    description: "No install-time seeding of ska_secret_key remains; _setup_secret_key and its runImportStepFromProfile re-entry are deleted from src/, .pyc included"
    requirement: "REG-04"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#TestSetupHandlers.test_setupVarious (NO INSTALL-TIME SEEDING group)"
        status: pass
      - kind: other
        ref: "grep -r runImportStepFromProfile src/ (exits non-zero, no output)"
        status: pass
    human_judgment: false
  - id: D5
    description: "get_ska_secret_key() mints and persists a non-empty key on first use, and does not re-mint on a second call"
    requirement: "REG-04"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#TestSetupHandlers.test_setupVarious (LAZY MINT group)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Re-applying imio.googleauthenticator:default over an existing known ska_secret_key leaves it byte-identical"
    requirement: "REG-05"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#TestSetupHandlers.test_setupVarious (REG-05 group)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-29
status: complete
---

# Phase 2 Plan 1: Registry Seeding and Import-Step Ordering Summary

**Declared `<depends name="plone.app.registry"/>` on the import step, deleted the nested `runImportStepFromProfile` re-seeding, moved `ska_secret_key`'s mint into a single lazy branch inside `get_ska_secret_key()`, and asserted all of it — ordering, records, no-seeding, mint, and re-apply survival — in one committed test method.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-29T12:43:04Z
- **Completed:** 2026-07-29
- **Tasks:** 2
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments

- `configure.zcml`'s `imio.googleauthenticator` import step now declares `<depends name="plone.app.registry"/>`, converting the previously self-closing directive to an open tag with a matching close, so GenericSetup's topological sort orders this package's step after `plone.app.registry` deterministically instead of by CPython 2.7 string-hash chance.
- `setuphandlers.py`'s `_setup_secret_key` (the nested `portal_setup.runImportStepFromProfile('profile-imio.googleauthenticator:default', 'plone.app.registry')` re-entry plus its seeding) is deleted outright, along with its call site and the now-dead `from uuid import uuid4` / `from imio.googleauthenticator.helpers import get_app_settings` imports. `setupVarious` does only the marker-file guard and `_add_plugin`.
- `helpers.py`'s `get_ska_secret_key()` gained a single `if not ska_secret_key:` branch: mints `unicode(uuid4())` and writes it back to the registry on first use, then falls through to the existing return unchanged. No `create=` kwarg, no `get_or_create_ska_secret_key()` wrapper.
- New `tests/test_setuphandlers.py::TestSetupHandlers.test_setupVarious` — one integration-layer test method with five assertion groups: ORDERING (REG-03), RECORDS (REG-01/REG-02 outcome), NO INSTALL-TIME SEEDING (REG-04), LAZY MINT (REG-04), and REG-05's double-apply regression guard.
- All stale git-ignored `.pyc` build artefacts under `src/` were removed (28 files, including the one carrying the deleted `_setup_secret_key` symbol).

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "installing the add-on yields a usable ska_secret_key"** - `5decb52` (feat)
2. **Task 2: REG-05 double-apply regression guard** - `ed59eae` (test)

**Plan metadata:** _pending — final docs commit below_

_Note: Task 1 is `type="tracer"` — committed as a full working slice, then its `<verify>` was re-run end-to-end before Task 2 (auto mode active); it passed, so expansion proceeded without a checkpoint._

## Files Created/Modified

- `src/imio/googleauthenticator/configure.zcml` - Added `<depends name="plone.app.registry"/>` to the `imio.googleauthenticator` import step
- `src/imio/googleauthenticator/setuphandlers.py` - Deleted `_setup_secret_key` and its call site plus two dead imports; `setupVarious` now only guards the marker file and calls `_add_plugin`
- `src/imio/googleauthenticator/helpers.py` - Added the `if not ska_secret_key:` lazy-mint branch inside `get_ska_secret_key()`
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - New: `TestSetupHandlers.test_setupVarious`, five assertion groups

## Decisions Made

- Followed CONTEXT.md's D-01 through D-13 as written; no new decisions were required during execution — implementation matched the pattern map (`02-PATTERNS.md`) exactly, including the exact target shapes for all three production edits.
- Confirmed via `grep -rn 'ska_secret_key' src/imio/googleauthenticator/*.py src/imio/googleauthenticator/browser/*.py src/imio/googleauthenticator/browser/forms/*.py` that exactly four call sites route through `get_ska_secret_key`/`sign_user_data` (the flagged REG-04 assumption): `helpers.py` itself (definition + 2 internal calls) and `request_bar_code_reset.py:66`. No fifth consumer reads `settings.ska_secret_key` directly.
- Printed `getSortedImportSteps()` once while writing the ordering assertion (the carried-forward MEDIUM, settled by observation per CONTEXT.md `<specifics>`): the sorted tuple places `u'plone.app.registry'` at index 34 and `u'imio.googleauthenticator'` at index 35, i.e. immediately after it — full tuple:

  ```
  (u'rolemap', u'sharing', u'plone-difftool', u'properties', u'toolset', u'cookie_authentication',
   u'catalog', u'workflow', u'update-workflow-rolemap', u'uid_catalog', u'various',
   u'reference_catalog', u'componentregistry', u'portal-transforms-various', u'skins',
   u'cssregistry', u'jquerytools-various', u'jsregistry', u'actions',
   u'plonetheme.sunburst-various', u'controlpanel', u'atcttool', u'tinymce_settings',
   u'archetypes-various', u'archetypetool', u'difftool', u'memberdata-properties', u'plonepas',
   u'plone_outputfilters_various', u'browserlayer', u'tinymce_various', u'mailhost',
   u'content_type_registry', u'propertiestool', u'viewlets', u'mimetypes-registry-various',
   u'plone.app.registry', u'imio.googleauthenticator', u'action-icons', u'languagetool',
   u'typeinfo', u'factorytool', u'cmfeditions_various', u'repositorytool', u'content',
   u'contentrules', u'portlets', u'plone-final', u'plone-content', u'plone.app.theming',
   u'various-calendar', u'caching_policy_mgr', u'collective.z3cform.datetimewidget_various')
  ```

  This does not settle which of `runImportStepFromProfile`'s four mechanisms fired on this site's pre-fix path (that question is now moot — the mechanism is deleted), but it does confirm the `<depends>` declaration produces the intended adjacency on this suite's fixture.

## Deviations from Plan

None - plan executed exactly as written. Both production edits and the test module matched `02-PATTERNS.md`'s target shapes; no auto-fixes, no blocking issues, no architectural questions arose.

## Issues Encountered

None. The sandboxed `find`/`grep` wrappers in this environment don't support GNU-style `-delete`/`--include` flags used in the plan's literal verify command — worked around with `find ... | xargs rm -f` and separate per-directory `grep` invocations to the same effect; no functional difference in what was checked.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `get_ska_secret_key()`'s bare `"{0}{1}{2}".format(...)` concatenation (BUG-04) is untouched here by design — plan 02-02 owns the netstring-style join (D-08) and the `get_browser_hash` `None`→`''` check (D-09, already satisfied in the installed tree per `02-PATTERNS.md`).
- REG-01's ROADMAP log-check criterion remains a `verification: backstop` must_have (D-02): the ordering/records assertions are the mechanised control; a manual `bin/instance fg` site-creation smoke run is documented in `02-CONTEXT.md <deferred>` if anyone wants to close it by hand, but is not required by this plan.
- Full suite (`bin/test -t '!robot'`) is green at 22 tests, 0 failures, 0 errors, after both task commits.

---
*Phase: 02-registry-seeding-and-import-step-ordering*
*Completed: 2026-07-29*

## Self-Check: PASSED

All created files and both task commit hashes verified present on disk / in git log.

## Post-review revision

Code review (`02-REVIEW.md`, CR-02) found that lazy-minting `ska_secret_key` inside
`get_ska_secret_key()` (D-05) — reached with no install-time seeding fallback (D-04) —
writes registry state from `sign_user_data()` inside
`GoogleAuthenticatorPlugin.authenticateCredentials()`, a request path that ends in
`transaction.abort()` on `Unauthorized`. That discards the mint after a signed URL
using it was already redirected to, leaving a 2FA-enabled user's first login stuck in
a permanently-invalid-signature loop with no self-recovery. This is exactly the class
of hazard `.claude/CLAUDE.md` names ("all state writes in the token form view").

**D-04 and D-05 are revised** (with the user's explicit authorisation to reopen locked
decisions):

- Install-time seeding is restored in `setuphandlers._setup_secret_key()`, called from
  `setupVarious`. D-04's actual intent — no nested `runImportStepFromProfile` re-entry —
  is kept intact: the restored seeding is a direct `get_app_settings()` call, relying on
  the REG-02 `<depends name="plone.app.registry"/>` declaration to guarantee the registry
  records already exist by the time `setupVarious` runs.
- `get_ska_secret_key()` is a pure read again: the `if not ska_secret_key:` mint branch
  is removed and replaced with a fail-closed `raise ValueError(...)` if the key is
  unexpectedly empty at read time (not caught anywhere — surfaces as a 500 via
  RENAME-11's `_dont_swallow_my_exceptions = True`, never a silent password-only
  fallthrough).

Also fixed in the same review pass: CR-01 (a falsy/`None`
`two_factor_authentication_secret` crashed `get_ska_secret_key()` with `TypeError`;
coerced with `or ''`), and WR-03 (`test_setupVarious`'s five bundled assertion groups
split into five separately-named test methods).

**Requirement status after revision:**

- REG-01, REG-02, REG-03 — unaffected, still hold as originally verified (import-step
  ordering and registry-records-exist are untouched by this revision).
- REG-04 — revised. "No install-time seeding path remains" no longer holds by design;
  it is superseded by the fix for CR-02. The parts of REG-04 that still hold: no nested
  `runImportStepFromProfile` re-entry exists anywhere in `src/`, and `ska_secret_key` is
  guaranteed non-empty (now seeded at install rather than lazily minted).
- REG-05 — still holds; re-verified against the revised code (the double-apply guard
  test is unchanged in intent, only relocated into its own method).
- BUG-04 — still holds; the netstring-style separation is untouched by this revision.

See `02-REVIEW-FIX.md` for the fix-by-fix disposition and `bin/test` results.
