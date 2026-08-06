---
phase: 02-registry-seeding-and-import-step-ordering
plan: 02
subsystem: auth
tags: [ska, helpers, testing, security]

requires:
  - phase: 02-registry-seeding-and-import-step-ordering
    plan: 01
    provides: "get_ska_secret_key()'s lazy-mint branch (D-05), which this plan's return-expression edit sits directly below"
provides:
  - "Length-prefixed (netstring-style) join in get_ska_secret_key(), replacing the bare '{0}{1}{2}'.format(...) concatenation"
  - "TestSkaSecretKey.test_get_ska_secret_key -- pins the exact derived string for a known fixture, proves the fixture collides under the old scheme, and asserts the new scheme separates it"
  - "TestSkaSecretKey.test_get_browser_hash -- regression guard pinning get_browser_hash's empty-string (not None) return"
  - "CHANGES.rst bullets for this phase's three user-visible changes"
affects: []

tech-stack:
  added: []
  patterns:
    - "Netstring-style length-prefixed join (u'{0}:{1}'.format(len(part), part) per component, concatenated with no separator) for framing components that must not collide under concatenation"
    - "Re-login (plone.app.testing.login) after installing a profile inside an integration-test setUp, when a test needs a memberdata property the profile just declared -- the fixture-login-cached user's property sheets predate the install"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/tests/test_helpers.py
    - CHANGES.rst

key-decisions:
  - "BUG-04: netstring-style length-prefixed join, exact shape u'2:ab0:2:cd' for fixture (user_secret='ab', browser_hash='', ska_secret_key=u'cd'), per D-08"
  - "get_browser_hash's except branch already returned '' before this plan (D-09 was stale); no production change, only a regression-guard test added, confirmed by reading helpers.py lines 210-225 before writing anything"
  - "Test setUp re-logs in the fixture user (plone.app.testing.login) after _install() -- PLONE_FIXTURE's own login caches the test user's PAS property sheets before this profile's memberdata_properties.xml is applied, so a stale cached sheet silently drops setMemberProperties writes for the newly declared field (own test bug, Rule 1 auto-fix, not a plan deviation in production code)"

requirements-completed: [BUG-04]

coverage:
  - id: D1
    description: "get_ska_secret_key() derives u'2:ab0:2:cd' for the known fixture (user_secret='ab', browser_hash='' via use_browser_hash=False, ska_secret_key=u'cd')"
    requirement: "BUG-04"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_helpers.py#TestSkaSecretKey.test_get_ska_secret_key (EXACT SHAPE group)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Two component tuples sharing the same bare concatenation derive to different keys under the new scheme"
    requirement: "BUG-04"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_helpers.py#TestSkaSecretKey.test_get_ska_secret_key (THE COLLISION IT PREVENTS group)"
        status: pass
    human_judgment: false
  - id: D3
    description: "An already-non-empty ska_secret_key is not re-minted by the derivation"
    requirement: "BUG-04"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_helpers.py#TestSkaSecretKey.test_get_ska_secret_key (MINT UNTOUCHED group)"
        status: pass
    human_judgment: false
  - id: D4
    description: "get_browser_hash returns '' (not None) on a missing/unhashable User-Agent, and a real User-Agent still hashes to a 40-char hex digest"
    requirement: "BUG-04"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_helpers.py#TestSkaSecretKey.test_get_browser_hash"
        status: pass
    human_judgment: false
  - id: D5
    description: "The whole suite stays green with all four ska-derivation consumers unmodified"
    requirement: "BUG-04"
    verification:
      - kind: unit
        ref: "bin/test -t '!robot' (24 tests, 0 failures, 0 errors)"
        status: pass
      - kind: other
        ref: "git diff --stat over pas_plugin.py, browser/forms/token.py, browser/forms/reset_bar_code.py, browser/forms/request_bar_code_reset.py -- empty"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-29
status: complete
---

# Phase 2 Plan 2: Registry Seeding and Import-Step Ordering (ska key separation) Summary

**`get_ska_secret_key`'s bare `"{0}{1}{2}".format(...)` concatenation is replaced with a netstring-style length-prefixed join (`u'2:ab0:2:cd'` for the pinned fixture), with a test that proves the fixture collides under the old scheme and no longer does under the new one, plus a regression guard for `get_browser_hash`'s already-correct empty-string return.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-29T12:54:16Z
- **Completed:** 2026-07-29T13:06:02Z
- **Tasks:** 2
- **Files modified:** 3 (helpers.py, test_helpers.py, CHANGES.rst)

## Accomplishments

- `helpers.py`'s `get_ska_secret_key()` return statement now builds
  `u''.join(u'{0}:{1}'.format(len(part), part) for part in (user_secret, browser_hash, ska_secret_key))`
  instead of `"{0}{1}{2}".format(...)`. Component order (`user_secret`, `browser_hash`,
  `ska_secret_key`) is unchanged; only the framing changed. Nothing else in the
  function was touched -- the lazy-mint branch from plan 02-01 stays exactly as it was.
- New `TestSkaSecretKey` class in `test_helpers.py` (integration layer, real
  `api.user.get_current()` member and real registry via `get_app_settings()`,
  no fake user, no monkeypatch), with two methods:
  - `test_get_ska_secret_key` -- asserts the exact derived string
    `u'2:ab0:2:cd'` for the fixture (`user_secret='ab'`, `browser_hash=''`,
    `ska_secret_key=u'cd'`), asserts the result is `unicode`, asserts the
    fixture genuinely collides under bare concatenation
    (`u'ab'+u''+u'cd' == u'a'+u''+u'bcd'`), then re-derives with the
    second tuple and asserts the two derived keys are `assertNotEqual`, and
    finally confirms the registry value is not re-minted.
  - `test_get_browser_hash` -- asserts `get_browser_hash(request={})` returns
    `''` (via `assertEqual` **and** `assertIsNotNone`, since both `''` and
    `None` are falsy and a truthiness check would not discriminate), and
    that a real `HTTP_USER_AGENT` still hashes to a 40-character hex digest.
    Docstring states explicitly this is a regression guard, not a fix for a
    live bug: `helpers.py` lines 210-225 already returned `''` from the
    `except` branch before this plan touched anything, confirmed by reading
    it first per the task's own instruction. Task 1's length-prefixed
    derivation is what turns that `except` branch from cosmetic into a
    `TypeError`-on-login-path crash guard (`len(None)` raises), so it is
    worth pinning now even though it guards nothing broken today.
- `CHANGES.rst` gained four bullets under `1.0.0 (unreleased)`: the rename
  (pre-existing), the import-step ordering dependency, the lazy
  `ska_secret_key` mint, and the length-prefixed derivation with its
  one-clause invalidation note.

## Task Commits

Each task was committed atomically:

1. **Task 1: Length-prefixed derivation in get_ska_secret_key, with the collision it prevents asserted** - `80382a9` (feat)
2. **Task 2: Regression guard for get_browser_hash's empty-string return, and the changelog line** - `7fd95e3` (test)

## Files Created/Modified

- `src/imio/googleauthenticator/helpers.py` - `get_ska_secret_key`'s return statement replaced with the length-prefixed join (Task 1 only; untouched by Task 2)
- `src/imio/googleauthenticator/tests/test_helpers.py` - New `TestSkaSecretKey` class: `test_get_ska_secret_key` (Task 1), `test_get_browser_hash` (Task 2); module-level imports for `get_app_settings`, `get_browser_hash`, `get_ska_secret_key`, `plone.api`, `plone.app.testing.login`, `plone.app.testing.TEST_USER_NAME`
- `CHANGES.rst` - Three new bullets under `1.0.0 (unreleased)` (Task 2)

## Stale-D-09 Check (Task 2's explicit output requirement)

Confirmed explicitly: `helpers.py` lines 210-225 (`get_browser_hash`) **matched**
Task 2's `read_first` expectation exactly -- the `except` branch already reads
`return ''`, not a fall-off-the-end `None`. `02-CONTEXT.md`'s D-09 describing a
`None` return is stale (likely fixed incidentally during Phase 1's fail-closed
work per `02-01-SUMMARY.md`'s "Next Phase Readiness" note); no production
edit was made in Task 2, per its explicit instruction to stop and report if
the tree differed -- it did not differ, so only the regression-guard test was
added.

## Exact Derived String Pinned (Task 2's explicit output requirement)

For the fixture `(user_secret='ab', browser_hash='' [use_browser_hash=False],
ska_secret_key=u'cd')`, `get_ska_secret_key(...)` returns exactly
`u'2:ab0:2:cd'`, asserted by `assertEqual`, not substring/length/regex.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in own test fixture] `setUp` re-logs in the test user after installing the add-on**

- **Found during:** Task 1, writing `test_get_ska_secret_key`
- **Issue:** `setMemberProperties(mapping={'two_factor_authentication_secret': 'ab'})`
  silently did not persist the value -- `get_ska_secret_key` derived
  `u'0:0:2:cd'` instead of the expected `u'2:ab0:2:cd'`. Root cause traced via
  direct inspection: `PLONE_FIXTURE`'s layer `testSetUp()` logs in
  `TEST_USER_NAME` (`plone.testing.z2.login`) *before* this plan's
  `TestSkaSecretKey.setUp()` runs and calls `self._install()`, which applies
  `memberdata_properties.xml` for the first time. The login call constructs
  and caches a PAS `PloneUser` whose `_propertysheets` (in
  `Products.PlonePAS.plugins.ufactory.PloneUser`) are computed from
  `portal_memberdata`'s schema *at that moment* -- before the add-on's three
  new properties exist. `MemberData.getUser()` returns that same cached
  object via acquisition, so `Products.PlonePAS.sheet.MutablePropertySheet.setProperties`
  never finds `two_factor_authentication_secret` in the cached sheet's
  `_properties` and silently drops it (exactly the class of hazard
  `CLAUDE.md` documents for undeclared properties -- here the property *is*
  declared, but the cached sheet predates the declaration). Confirmed by
  printing `acl_users.getUserById(user.getId())`'s freshly-computed sheet,
  which does have the property.
- **Fix:** `setUp()` calls `plone.app.testing.login(self.portal, TEST_USER_NAME)`
  again immediately after `self._install()`, forcing a fresh `PloneUser`
  (and fresh property sheets) to be built against the now-current
  `portal_memberdata` schema.
- **Files modified:** `src/imio/googleauthenticator/tests/test_helpers.py`
  (test fixture only; no production code touched)
- **Commit:** `80382a9`

### None Other

No further deviations. Task 1's production edit and Task 2's test-only
addition matched `02-PATTERNS.md`'s target shapes exactly; no blocking
issues, no architectural questions.

## Issues Encountered

The `setMemberProperties` staleness above was the only real obstacle; once
root-caused via direct inspection of `Products.PlonePAS` internals
(`ufactory.py`, `property.py`, `sheet.py`), the fix was a one-line addition
to the test fixture, not a production change.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BUG-04, REG-01 through REG-05 are now all complete; Phase 2 (registry
  seeding and import-step ordering) is fully executed across both plans.
- The `costly`-reversibility prohibition on this plan (Task 1) stands: the
  derivation must not be reopened once any user is enrolled or any signed
  URL is in flight, without an explicit migration.
- Full suite (`bin/test -t '!robot'`) is green at 24 tests, 0 failures, 0
  errors, after both task commits.

---
*Phase: 02-registry-seeding-and-import-step-ordering*
*Completed: 2026-07-29*

## Self-Check: PASSED

All created/modified files and both task commit hashes verified present on disk / in git log.
