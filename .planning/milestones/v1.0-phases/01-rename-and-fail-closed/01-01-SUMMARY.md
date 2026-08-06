---
phase: 01-rename-and-fail-closed
plan: 01
subsystem: auth
tags: [plone, pas-plugin, buildout, namespace-package, genericsetup, rename]

# Dependency graph
requires: []
provides:
  - "Package lives on disk, in the egg, and in every ZCML/GenericSetup identity as imio.googleauthenticator"
  - "src/imio/__init__.py byte-identical to imio.helpers' namespace declaration"
  - "GenericSetup marker file + setuphandlers.py string renamed together (RENAME-04 invariant)"
  - "upgrades/ deleted, its ZCML include removed"
  - "testing.py layer class/constants/installProduct string renamed; all test-file consumers updated"
  - "Three new behavioural tests: namespace declaration, PAS plugin registration, resource-id agreement"
affects: [01-02-locales-and-translations, 01-03-packaging-and-metadata, 01-04-pas-identity-and-fail-closed]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-move commit (git mv + git clean -xdf, zero content edits), then a buildout-regeneration commit, then a content-rename commit — because bin/test is generated from base.cfg package-name and cannot run between the move and the regenerate"
    - "Behavioural assertions (listPlugins, pkg_resources._namespace_packages, getResourceIds) in place of grep-based rename verification, because the marker-file, namespace and resource-prefix failure modes are all silent"

key-files:
  created:
    - src/imio/__init__.py
  modified:
    - src/imio/googleauthenticator/** (whole moved subtree, ~35 files with dotted-name edits)
    - src/imio/googleauthenticator/testing.py
    - src/imio/googleauthenticator/setuphandlers.py
    - src/imio/googleauthenticator/profiles/default/imio.googleauthenticator.marker.txt (renamed)
    - src/imio/googleauthenticator/profiles/default/metadata.xml
    - src/imio/googleauthenticator/tests/test_generic.py
    - src/imio/googleauthenticator/tests/test_pas_plugin.py
    - base.cfg
    - setup.py

key-decisions:
  - "Three commits for task 1 (pure move / buildout regen / content rename), per CONTEXT.md 'Rename commit shape' — the move is untestable by construction so it stays isolated and small enough to review by rename detection."
  - "PAS_ID, meta_type and PAS_TITLE left untouched — explicitly out of scope, owned by plan 01-04's own commit so a duplicate-meta_type RuntimeError stays legible as 'stale artefact' rather than 'rename bug'."
  - "locales/** filenames and rebuild_i18n.sh's I18NDOMAIN left untouched — owned by plan 01-02 (D-15); MessageFactory calls in source ARE renamed here per RESEARCH §B, since that's a distinct rename surface from the locale filenames that define the actual i18n domain at runtime."
  - "No imio.helpers dependency added for the namespace test — RESEARCH Adjudication A-1: it would pull plone.dexterity/pyjwt/cryptography into a Plone 4.3 pin set. Used the pkg_resources._namespace_packages + namespace_packages.txt assertion instead."

requirements-completed: [RENAME-01, RENAME-02, RENAME-04, RENAME-05, RENAME-07, RENAME-08, RENAME-09, RENAME-12]

coverage:
  - id: D1
    description: "Package moved to src/imio/googleauthenticator/, buildout regenerated, and the pre-existing 8-test suite green under the new name"
    requirement: "RENAME-01"
    verification:
      - kind: integration
        ref: "bin/test -t '!robot' (8 tests, 0 failures, 0 errors, post-move)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every dotted reference (imports, MessageFactory, logger names, ZCML attributes, GenericSetup XML) renamed to imio.googleauthenticator"
    requirement: "RENAME-02"
    verification:
      - kind: unit
        ref: "git grep -i collective -- src/imio/ (excluding locales/**) returns only the three PAS-identity strings explicitly out of scope for this plan"
        status: pass
    human_judgment: false
  - id: D3
    description: "GenericSetup marker file renamed alongside the setuphandlers.py string it is compared against"
    requirement: "RENAME-04"
    verification:
      - kind: integration
        ref: "tests/test_pas_plugin.py#test_plugin_is_registered_for_authentication"
        status: pass
    human_judgment: false
  - id: D4
    description: "++resource++ prefix agreement across resourceDirectory name, jsregistry.xml (2 ids), cssregistry.xml, and skins.xml"
    requirement: "RENAME-05"
    verification:
      - kind: integration
        ref: "tests/test_generic.py#test_resources_are_registered"
        status: pass
    human_judgment: false
  - id: D5
    description: "base.cfg package-name / [code-analysis] directory, setup.py name/namespace_packages regenerated via bin/buildout -N"
    requirement: "RENAME-07"
    verification:
      - kind: unit
        ref: "grep 'package-name = imio.googleauthenticator' base.cfg && grep defaults .installed.cfg"
        status: pass
    human_judgment: false
  - id: D6
    description: "Orphan .pyc, stale egg-info and stale egg-link purged; exactly one develop-egg and one egg-info remain"
    requirement: "RENAME-08"
    verification:
      - kind: unit
        ref: "find src -name '*.pyc' (empty); ls develop-eggs/ | grep -c googleauthenticator == 1; ls -d src/*.egg-info == 1"
        status: pass
    human_judgment: false
  - id: D7
    description: "upgrades/ deleted along with its ZCML include; layer setup completes with no ConfigurationError"
    requirement: "RENAME-09"
    verification:
      - kind: integration
        ref: "bin/test -t '!robot' (layer setup succeeds, no ZCML error)"
        status: pass
    human_judgment: false
  - id: D8
    description: "New test asserts PAS registration via listPlugins(IAuthenticationPlugin), catching a Broken plugin or marker-file mismatch that objectIds() cannot see"
    requirement: "RENAME-12"
    verification:
      - kind: unit
        ref: "tests/test_pas_plugin.py#test_plugin_is_registered_for_authentication"
        status: pass
    human_judgment: false
  - id: D9
    description: "Namespace declaration byte-identical to imio.helpers, proven by pkg_resources assertion, no imio.helpers dependency added"
    verification:
      - kind: unit
        ref: "tests/test_generic.py#test_imio_is_a_pkg_resources_namespace"
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-28
status: complete
---

# Phase 1 Plan 1: Move and rename to imio.googleauthenticator, suite green Summary

**Package moved from src/collective/ to src/imio/googleauthenticator/, every dotted reference and GenericSetup identity renamed, buildout regenerated, and the suite green at 11 tests (8 pre-existing + 3 new behavioural assertions for namespace, PAS registration, and resource-id agreement).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-28T16:28Z
- **Completed:** 2026-07-28T16:38Z
- **Tasks:** 2 completed
- **Files modified:** ~40 (1 created, 4 deleted, 2 renamed, ~35 content-edited)

## Accomplishments
- Package moved with `git mv src/collective src/imio`, 31 stale untracked artefacts purged (29 `.pyc`, stale `.mo`, stale `egg-info`), stale `develop-eggs/` egg-link removed
- `base.cfg`/`setup.py` updated and `bin/buildout -N` regenerated `bin/test`, the egg-link, and the egg-info under the new name
- Every remaining dotted reference (imports, `MessageFactory`, logger names, ZCML `i18n_domain`/`resourceDirectory`/`class`/`layer`, all GenericSetup XML) renamed across ~35 files
- GenericSetup marker file `git mv`-ed and the `setuphandlers.py` string it's compared against renamed in the same commit; `upgrades/` deleted along with its ZCML include; profile version bumped 0301 → 1000
- `testing.py`'s layer class, four module constants, and `installProduct` string renamed; all five test-file consumers plus the two literal product-id strings (`tests/base.py`, `test_generic.py`) updated
- Three new behavioural tests added: `test_imio_is_a_pkg_resources_namespace`, `test_plugin_is_registered_for_authentication`, `test_resources_are_registered` — each proves a rename surface that a clean `git grep` cannot see
- `bin/test -t '!robot'` green: 11 tests, 0 failures, 0 errors (up from the pre-existing 8)

## Task Commits

Each task was committed atomically (task 1 required three commits per its own action, since a pure move is untestable by construction and the buildout regeneration is a hard sequencing gate):

1. **Task 1, commit 1: pure move** — `7ff9062` (refactor) — `git mv src/collective src/imio` + `git clean -xdf src/` + stale egg-link removal, zero content edits
2. **Task 1, commit 2: buildout prerequisites + regenerate** — `464a427` (chore) — `base.cfg`, `setup.py`, `src/imio/__init__.py`, then `bin/buildout -N -c test-4.3.cfg`
3. **Task 1, commit 3: remaining dotted-name/GenericSetup renames** — `9952f46` (refactor) — every remaining `collective.googleauthenticator` reference, marker file rename, `upgrades/` deletion, `testing.py` full rename
4. **Task 2: three behavioural assertions** — `2910aa8` (test)

**Plan metadata:** pending (this commit, `docs(01-01): complete move-and-rename plan`)

_Note: Task 2 carried `tdd="true"` in the plan, but the behavior under test already existed from task 1's commits — see Deviations below for why RED/GREEN was not forced._

## Files Created/Modified
- `src/imio/__init__.py` — namespace declaration, byte-copied from `imio.helpers`
- `src/imio/googleauthenticator/**` — whole subtree moved and dotted-name-renamed
- `src/imio/googleauthenticator/testing.py` — layer class, 4 constants, 3 layer names, `installProduct` string
- `src/imio/googleauthenticator/setuphandlers.py` — imports, `MessageFactory`, marker-file string, profile-id string (PAS_ID/PAS_TITLE untouched)
- `src/imio/googleauthenticator/profiles/default/imio.googleauthenticator.marker.txt` — renamed from the old marker filename
- `src/imio/googleauthenticator/profiles/default/metadata.xml` — version 0301 → 1000
- `src/imio/googleauthenticator/tests/test_generic.py` — 2 new test methods
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` — 1 new test method
- `base.cfg` — `package-name`, `[code-analysis] directory`
- `setup.py` — `name`, `namespace_packages`

## Decisions Made
- Kept the three-commit shape for task 1 exactly as the plan prescribed (pure move / buildout regen / content rename) — each carries its own shell-assertion gate since `bin/test` cannot run between them.
- Did not touch `rebuild_i18n.sh`'s `I18NDOMAIN` despite an initial blanket-sed pass catching it — reverted after checking the phase's Multi-Source Coverage Audit, which assigns D-15 to plan 01-02, not this plan.
- Left `PAS_ID`, `meta_type`, and `PAS_TITLE` untouched per the plan's explicit instruction (plan 01-04 owns them in an isolated commit, so a duplicate-`meta_type` `RuntimeError` stays legible as "stale artefact").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, self-corrected before commit] Reverted an out-of-scope edit to `rebuild_i18n.sh`**
- **Found during:** Task 1, commit 3 (blanket `sed` pass across Python/ZCML/XML files)
- **Issue:** The blanket `sed 's/collective\.googleauthenticator/imio.googleauthenticator/g'` used to rename `MessageFactory`/logger calls also matched `rebuild_i18n.sh`'s `I18NDOMAIN="collective.googleauthenticator"` line. That file (and D-15, the `I18NDOMAIN` update) is explicitly owned by plan 01-02 per the phase's Multi-Source Coverage Audit table, not this plan — it's not in this plan's `files_modified` frontmatter list and not mentioned in task 1's `<action>`.
- **Fix:** `git checkout -- src/imio/googleauthenticator/rebuild_i18n.sh` before staging commit 3, restoring the old `I18NDOMAIN` value. Verified with `grep` that the revert was clean.
- **Files modified:** none (reverted before commit; not part of any committed diff)
- **Verification:** `git diff` on the file showed no changes after the revert; the file was excluded from commit 3's `git add`.
- **Committed in:** n/a — caught before staging, so no commit needed correcting.

---

**Total deviations:** 1 self-corrected (caught and fixed before commit, no committed impact)
**Impact on plan:** None on the shipped commits — the out-of-scope edit never reached a commit. Documented here per the deviation-tracking convention so plan 01-02's executor knows this file is still in its original pre-rename state, unmodified.

## Issues Encountered

**Task 2's `tdd="true"` attribute vs. already-existing behavior.** The plan's TDD execution flow (RED test-must-fail, then GREEN implementation) does not fit task 2 cleanly: the behavior all three new tests assert (the namespace declaration, PAS registration, resource-id agreement) was already fully implemented by task 1's three commits. Writing the tests first would not produce a failing RED phase — they pass immediately, which is the exact "fail-fast" trip condition the TDD reference describes for when a test passes unexpectedly before implementation exists.

Resolution: followed task 2's own `<action>` text literally, which describes a single "add three test methods... commit" step, not a RED/GREEN split. This reads as intentional in the plan — the tests are regression/behavioral assertions catching up with rename behavior that task 1 (the tracer-equivalent, atomic move-and-rename) already established, not net-new feature development requiring a failing-first cycle. All three tests were verified individually (`bin/test -t <name>`, each exactly 1 test, 0 failures) before the single commit.

## TDD Gate Compliance

Task 2 was marked `tdd="true"` but committed as a single `test(...)` commit with no preceding `feat(...)` implementation commit, because the implementation (task 1) predates the tests by design — the rename established the behavior, and task 2's tests are the permanent regression guard for it, not a net-new feature. No RED-phase failing-test commit exists for this reason; each new test was verified to pass individually and the full suite verified green at 11 tests before the single commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-02 (locales/translations) can proceed: `locales/**` filenames and `rebuild_i18n.sh`'s `I18NDOMAIN` are untouched and in their original pre-rename state, exactly as this plan left them.
- Plan 01-03 (packaging/metadata) can proceed: `setup.py`'s `version`, `author`, `url`, `classifiers` are still pre-phase values; only `name` and `namespace_packages` were touched here.
- Plan 01-04 (PAS identity + fail-closed) can proceed: `PAS_ID`, `meta_type`, `PAS_TITLE` are all untouched; the marker-file/GenericSetup identity chain this plan built is the foundation `test_plugin_is_registered_for_authentication` will extend for the fail-closed test.
- No blockers. `bin/test -t '!robot'` is green at 11 tests, 0 failures, 0 errors.

---
*Phase: 01-rename-and-fail-closed*
*Completed: 2026-07-28*

## Self-Check: PASSED

- FOUND: `src/imio/__init__.py`
- FOUND: `src/imio/googleauthenticator/testing.py`
- FOUND: `src/imio/googleauthenticator/profiles/default/imio.googleauthenticator.marker.txt`
- FOUND commit: `7ff9062` (pure move)
- FOUND commit: `464a427` (buildout regen)
- FOUND commit: `9952f46` (content rename)
- FOUND commit: `2910aa8` (behavioural tests)
