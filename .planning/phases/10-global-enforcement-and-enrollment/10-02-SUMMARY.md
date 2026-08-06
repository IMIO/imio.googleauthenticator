---
phase: 10-global-enforcement-and-enrollment
plan: 02
subsystem: auth
tags: [genericsetup, plone, pas-plugin, testing]

requires:
  - phase: 10-global-enforcement-and-enrollment
    provides: "plan 10-01's _enroll_existing_users (install-time bulk enrollment, flag only, no seed) and the two_factor_authentication_enrolled memberdata property"
provides:
  - "The full MFA-15 install-time matrix proven by test: every pre-existing account, no seed minted, no encryption key required, a second application changes nothing, globally_enabled off enrols nobody, and the Zope-root account is never claimed as enrolled"
  - "RESEARCH.md assumption A1 settled: a per-user install-time failure propagates unswallowed out of setupVarious, through Products.GenericSetup's import-step runner, out of applyProfile -- confirmed by exercising a real failure, not assumed"
  - "test_uninstall_keeps_enrolled_user_data now covers all nine memberdata_properties.xml declarations, not eight"
affects: [10-03, 10-04, 10-05, 10-06]

tech-stack:
  added: []
  patterns:
    - "Injecting a per-user failure through a real collaborator (a small stand-in for plone.api.user.get_users()) rather than a mock framework, following test_user_setup.py's _RaisesOnFirstCall precedent"
    - "Stronger non-vacuity mutations when 'delete the call under test' passes vacuously for a no-change or prohibition assertion -- reintroducing the exact regression (seed minting, root-account enrollment) the assertion is meant to catch, instead of just removing the call"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/tests/test_setuphandlers.py

key-decisions:
  - "No production code change was needed in setuphandlers.py or helpers.py. Plan 10-01's _enroll_existing_users already satisfies every case this plan tests: it has no swallowing except arm (D-04 holds), api.user.get_users() -> portal_membership.listMembers() -> BaseTool.listMembers already returns site-local accounts only (the Zope-root account never reaches the loop), and the has_enabled_two_factor_authentication guard already makes re-application a no-op (D-13 holds)."
  - "RESEARCH.md's assumption A1 holds as originally designed: Products.GenericSetup.tool._doRunImportStep calls its handler with no surrounding try/except, and plone.app.testing.applyProfile's own try/finally only restores the security manager, never catches. An injected ValueError from a per-user write propagates unchanged all the way out of applyProfile. 'Let it raise' does satisfy D-04; no explicit-failure-report rewrite of _enroll_existing_users was needed."
  - "Two of the five non-vacuity checks needed a stronger mutation than 'delete the _enroll_existing_users() call', because that specific removal passes vacuously for a no-change assertion and for a prohibition assertion (see Non-vacuity checks below for both, and why)."

patterns-established:
  - "When a test's core claim is a negative (a prohibition, or 'nothing changed'), the standard non-vacuity mutation ('delete the function call under test') is not automatically sufficient -- it must be checked, and if it passes vacuously, the fix is a stronger, more faithful mutation that reproduces the exact regression the assertion exists to catch."

requirements-completed: [MFA-15]

duration: ~1h
completed: 2026-08-06
status: complete
---

# Phase 10 Plan 02: Install-Time Enrollment Matrix and the D-04 Failure-Reporting Proof Summary

**Five new `test_setuphandlers.py` methods prove the full MFA-15 install-time matrix (every account, no seed, no key, a second install, the setting off, the un-gateable root account) and settle RESEARCH.md's open assumption A1 by actually raising an exception from inside `setupVarious` for the first time in the suite's history — no production code changed, because plan 10-01's `_enroll_existing_users` already satisfied every case.**

## Performance

- **Duration:** ~1h
- **Tasks:** 2 completed
- **Files modified:** 1 (`src/imio/googleauthenticator/tests/test_setuphandlers.py`)

## Accomplishments

- `test_install_enrolls_every_pre_existing_account_without_a_seed` (D-01/D-02, MFA-15): three
  freshly created accounts all get the flag set and no seed minted, with
  `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` removed from the environment for the duration of the
  profile application — install needs no encryption key.
- `test_install_enrollment_is_idempotent_across_two_profile_applications` (D-13, MFA-15
  adjacency probe): an account holding a flag, a stored seed, and
  `two_factor_authentication_enrolled` before a second (and third) profile application reads
  back all three byte-identical afterwards.
- `test_install_enrolls_nobody_when_globally_enabled_is_off` (D-01): two-halves structure
  mirroring `test_reapply_profile_keeps_plugin_first_and_unique` — refusal while off, then a
  non-vacuity control proving the same accounts do get enrolled once the setting is turned on.
- `test_install_enrolls_no_account_it_cannot_gate` (MFA-15, prohibition, T-03-23): logs in as
  `SITE_OWNER_NAME` against `self.app['acl_users']`, confirms `helpers.is_site_local_user`
  refuses it as a precondition, and confirms install does not set the flag for it.
- `test_install_enrollment_reports_a_failure_instead_of_partially_enrolling` (D-04, Wave 0 gap
  2): a `_FakeApiWithOneFailingUser` collaborator stand-in (module-level, mirroring
  `test_user_setup.py`'s `_RaisesOnFirstCall`) monkeypatches `setuphandlers.api` for the
  duration of one `applyProfile` call so that one of three accounts raises `ValueError` on
  `setMemberProperties`. `self.assertRaises(ValueError, ...)` proves the exception propagates
  out of `applyProfile`; the account processed before the failing one keeps its flag; removing
  the injection and re-running the install enrols both real accounts.
- `test_uninstall_keeps_enrolled_user_data`'s `expected_properties` tuple and docstring updated
  from eight to nine declarations, adding `two_factor_authentication_enrolled` (plan 10-01's new
  property) to the set the uninstall profile must never touch.

## Task Commits

Each task was committed atomically:

1. **Task 1: The install-time enrollment matrix — every account, no seed, twice, and with the setting off** — `0ad65c2` (test)
2. **Task 2: Prove what a partial install-time enrollment actually does to the operator (D-04, Wave 0 gap)** — `03ec8ed` (test)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `src/imio/googleauthenticator/tests/test_setuphandlers.py` — five new test methods, one new
  module-level test collaborator class (`_FakeApiWithOneFailingUser`), three new imports
  (`cryptography.fernet.Fernet`, `imio.googleauthenticator.helpers`,
  `imio.googleauthenticator.setuphandlers`) plus `login`, `SITE_OWNER_NAME`, `TEST_USER_NAME`,
  `plone.testing.z2`, and the `expected_properties` tuple/docstring update in
  `test_uninstall_keeps_enrolled_user_data`.

## Decisions Made

- **No production code change.** Every one of the plan's five behavioural cases was already
  satisfied by plan 10-01's `_enroll_existing_users`. Confirmed this is real, not assumed, via
  the non-vacuity checks below (particularly the two that needed a stronger mutation than
  "delete the call").
- **RESEARCH.md's A1 holds.** Traced the real call chain: `plone.app.testing.applyProfile` ->
  `portal_setup.runAllImportStepsFromProfile` -> `Products.GenericSetup.tool.
  _runImportStepsFromContext` -> `_doRunImportStep`, whose body is `return handler(context)`
  with no surrounding try/except (`Products/GenericSetup/tool.py:1284` in the pinned
  `Products.CMFCore`/`Products.GenericSetup` egg set). `applyProfile`'s own try/finally
  (`plone/app/testing/helpers.py:110-119`) restores the security manager only, never catches.
  An injected `ValueError` reaches `self.assertRaises` unchanged. "Let it raise" satisfies D-04
  as originally designed; no explicit-collect-and-report rewrite of `_enroll_existing_users`
  was required.
- **Users created before, not after, `globally_enabled` is turned on, in every new test that
  creates accounts.** `userdataschema.userCreatedHandler` already consults the same setting on
  `api.user.create()` — flipping it on first would enrol accounts as a side effect of creation
  and make the "starts unset" non-vacuity precondition vacuous. Discovered this the hard way
  (see Issues Encountered).

## Deviations from Plan

None — plan executed exactly as written. The plan explicitly anticipated the possibility that
`_enroll_existing_users` might need a change (particularly for the root-account case) and left
that as a live question ("the site-local case is the one most likely to need it, though
`api.user.get_users()` is expected to return site accounts only") — the answer turned out to be
no change needed, which is itself the plan's own stated non-committal outcome, not a deviation
from it.

## Issues Encountered

- **First draft of `test_install_enrollment_reports_a_failure_instead_of_partially_enrolling`
  set `globally_enabled = True` before calling `api.user.create()` for its two real accounts.**
  Since `userdataschema.userCreatedHandler` also consults `globally_enabled` on user creation,
  both accounts came out of `api.user.create()` already enrolled, and the test's own
  non-vacuity precondition ("both real accounts must start unset") failed immediately —
  caught by running the test, not discovered later. Fixed by moving the `globally_enabled =
  True` assignment to after account creation, with a comment recording why the order matters.
  This is exactly the class of assumption the project's non-vacuity discipline exists to catch
  before it ships silently wrong.

## Non-vacuity checks (mandatory, project convention since Phase 1)

All five methods were run against unmodified source first to confirm they pass (baseline), then
each was falsified against a real source mutation, then the source was restored byte-identical
(`git diff --stat` confirmed empty after every restoration) before the next check began.

**1. `test_install_enrolls_every_pre_existing_account_without_a_seed`** — deleted the
`_enroll_existing_users()` call from `setupVarious`. Real failure output:

```
AssertionError: False is not True : MFA-15/D-01: 'install-enrolls-user-1' must be enrolled by
install when globally_enabled is on -- even with no seed encryption key configured.
```

**2. `test_install_enrolls_nobody_when_globally_enabled_is_off`** — same deletion. Real failure
output (from the test's own second-half non-vacuity control):

```
AssertionError: False is not True : Non-vacuity control: 'install-off-user-1' must be enrolled
once globally_enabled is turned on, or the refusal asserted above could pass even if
_enroll_existing_users had been deleted outright.
```

**3. `test_install_enrollment_is_idempotent_across_two_profile_applications`** — the "delete the
call" mutation does **not** falsify this test: with nothing running at install, the
already-set state trivially stays unchanged, so the no-change assertions pass vacuously. This
was itself a useful negative result, recorded rather than hidden. Escalated to a stronger,
more faithful mutation: reintroduced `get_or_create_secret(user, overwrite=True)`
unconditionally inside the per-user loop — the exact D-02 regression ("seed minting
reintroduced at install") the byte-identical-seed assertion exists to catch. Real failure
output:

```
AssertionError: 'v1$gAAAAABqdLg4jxZbRU9GLiOjsEqHwh6m8I4UH9llrBU9Anaj0sSRXIZCWFrjyztB_iMAEqI6zqgzBdSX3yfBNC7YEuVBvh9XZXCxbEWImwLAowfkN6GsUWRh2yeF0uhjxo1SxWTh0wVI' !=
'v1$gAAAAABqdLg467L99-wXEzEvDY_2O3agAPMbJXXuDH0vpJud9JPBGDs23beVgTT47bMeuetKD22pZrKQBkP8Oh-XhQFiqmtGyNbh3mchmEEgxwuBHh5J2rv9WZPrF7HWkDM9L0-HSgni' : D-13: a
second install must not re-mint an already-stored seed -- byte-identical, since a re-mint
would silently invalidate a working authenticator app.
```

**4. `test_install_enrolls_no_account_it_cannot_gate`** — same "delete the call" mutation does
**not** falsify this test either, for the same reason: it asserts a negative (the root account
is *not* enrolled), and with nothing running, that stays trivially true. This matches the
plan's own frontmatter, which lists this exact statement under `prohibitions` with
`status: flagged-unverified` / `verification: none` — the plan itself flagged that the standard
mutation would not settle it. Escalated to a stronger mutation: added a line inside
`_enroll_existing_users`, after the per-user loop, that also calls
`api.user.get_current().setMemberProperties(...)` — since `applyProfile` always logs in as
`SITE_OWNER_NAME` internally, and the test is itself logged in as `SITE_OWNER_NAME`, this
simulates exactly the regression the prohibition guards against (install also enrolling the
un-gateable root account). Real failure output:

```
AssertionError: True is not False : MFA-15: install must not enrol the Zope-root account -- its
login is authenticated above the site and this plugin can never intercept it.
```

**5. `test_install_enrollment_reports_a_failure_instead_of_partially_enrolling`** — wrapped the
per-user `setMemberProperties` write in `try: ... except Exception: pass` inside
`_enroll_existing_users` — the exact swallowing shape D-04 forbids. Real failure output:

```
AssertionError: ValueError not raised
```

All five mutations were restored byte-identical; `git diff --stat` against
`src/imio/googleauthenticator/setuphandlers.py` was confirmed empty after every restoration.

## User Setup Required

None — no external service configuration required.

## Verification Evidence

- `bin/test -t test_setuphandlers` → **27 tests, 0 failures, 0 errors** (22 pre-existing + 5
  new), reproduced clean and twice more with `--shuffle` under two different random seeds.
- `bin/test -t '!robot'` → **150 tests, 0 failures, 0 errors** (up from the 145-test baseline),
  reproduced three times, twice with `--shuffle` under different random seeds, all green.
- `bin/code-analysis` → exits 0 (Flake8 OK), checked after each task commit.
- Acceptance-criteria greps, all confirmed:
  - `grep -cE '    def test_install_(enrolls|enrollment)' test_setuphandlers.py` → `4` at the
    Task 1 commit, `5` at the Task 2 commit (as expected — Task 2 adds the fifth).
  - `grep -c "'two_factor_authentication_enrolled'," test_setuphandlers.py` → `1`.
  - `test_uninstall_keeps_enrolled_user_data`'s `expected_properties` tuple has nine entries,
    matching the nine `<property>` elements in `profiles/default/memberdata_properties.xml`
    (confirmed by direct read of that file), and its docstring states "nine".
  - `grep -c 'assertRaises' test_setuphandlers.py` → `2` (one is the docstring's own mention of
    `self.assertRaises(ValueError, ...)`, the other is the actual call in the D-04 test's body —
    both from the single new test method; no other method in the file uses `assertRaises`).

## Known Stubs

None.

## Threat Flags

None beyond what the plan's own `<threat_model>` already names and mitigates. All four
mitigate-disposition threats (T-10-07 through T-10-10) are addressed exactly as the plan
describes: T-10-07 by the D-04 test, T-10-08 by the root-account test, T-10-09 unchanged
(no new install entry point was added), T-10-10 by the setting-off/second-application/
root-account cases together.

## Next Phase Readiness

- MFA-15's install-time half is now fully proven by test, including the one previously-flagged
  prohibition and the one previously-open research assumption (A1). Plans 10-03 through 10-06
  can treat `_enroll_existing_users` and the "let it raise" design as settled, not provisional.
- RESEARCH.md's Assumptions Log row A1 and Open Questions item 2 can be closed against this
  plan's evidence.

## Self-Check: PASSED

Confirmed present on disk: `src/imio/googleauthenticator/tests/test_setuphandlers.py` (modified)
and this SUMMARY.md. Confirmed present in `git log --oneline --all`: `0ad65c2`, `03ec8ed`.

---
*Phase: 10-global-enforcement-and-enrollment*
*Completed: 2026-08-06*
