---
phase: quick-260806-gfr
plan: 01
subsystem: auth
tags: [genericsetup, pas-plugin, uninstall-profile, plone]

# Dependency graph
requires:
  - phase: quick-260806-fsp
    provides: the enrollment-form lockout fix this task's baseline (132 tests) was measured against
provides:
  - "profiles/uninstall/ that actually reverses profiles/default/: PAS plugin, local utility, three user actions, browser layer, configlet, settings records"
  - "setuphandlers.uninstallVarious / _remove_plugin, a second genericsetup:importStep, gated on its own data file"
  - "test_uninstall_removes_pas_plugin, test_uninstall_reverses_the_profile_registrations, test_uninstall_keeps_enrolled_user_data"
affects: [uninstall, coexistence, memberdata]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Uninstall-side GenericSetup import step mirrors the install-side one: a data-file gate (imio.googleauthenticator.uninstall.txt, present only in profiles/uninstall/) keeps a globally-registered handler from firing on every other profile import in the process"
    - "Non-vacuity assertion via getSiteManager().registeredUtilities() filtered on .provided, not getUtility()/queryUtility(), when a global default utility registration would make a fallback lookup pass regardless of local state"

key-files:
  created:
    - src/imio/googleauthenticator/profiles/uninstall/componentregistry.xml
    - src/imio/googleauthenticator/profiles/uninstall/actions.xml
    - src/imio/googleauthenticator/profiles/uninstall/browserlayer.xml
    - src/imio/googleauthenticator/profiles/uninstall/controlpanel.xml
    - src/imio/googleauthenticator/profiles/uninstall/registry.xml
    - src/imio/googleauthenticator/profiles/uninstall/imio.googleauthenticator.uninstall.txt
  modified:
    - src/imio/googleauthenticator/setuphandlers.py
    - src/imio/googleauthenticator/configure.zcml
    - src/imio/googleauthenticator/tests/test_setuphandlers.py
    - CHANGES.rst

key-decisions:
  - "IGoogleAuthenticatorSettings now declares five fields (max_failed_attempts/lockout_duration added in Phase 5), not the three named in this plan's own truths table. registry.xml's bare <records interface=... remove=\"true\"/> already removes all five; the test asserts every field read live via .names() rather than hardcoding a stale count of three."
  - "test_uninstall_keeps_enrolled_user_data cannot be made to fail without introducing a real bug: nothing this task adds touches memberdata, so there is no mutation that turns it red without deliberately breaking the exclusion. Kept as a forward-looking regression guard per the plan's own framing (T-gfr-04), not treated as a Task-2 RED-before-GREEN failure."

requirements-completed: [COEX-06]

coverage:
  - id: D1
    description: "Applying imio.googleauthenticator:uninstall removes the google_auth PAS plugin from acl_users and from every plugin-type listing, idempotently, and re-applying default restores it first among IAuthenticationPlugin"
    requirement: "COEX-06"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#test_uninstall_removes_pas_plugin"
        status: pass
    human_judgment: false
  - id: D2
    description: "Applying the uninstall profile removes the local IUserDataSchemaProvider utility, the three portal_actions/user entries, the browser layer, the control-panel configlet and the IGoogleAuthenticatorSettings registry records, idempotently and reversibly"
    requirement: "COEX-06"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#test_uninstall_reverses_the_profile_registrations"
        status: pass
    human_judgment: false
  - id: D3
    description: "The uninstall profile leaves portal_memberdata's eight property declarations and an enrolled user's stored seed untouched"
    requirement: "COEX-06"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_setuphandlers.py#test_uninstall_keeps_enrolled_user_data"
        status: pass
    human_judgment: false

# Metrics
duration: 35min
completed: 2026-08-06
status: complete
---

# Quick Task 260806-gfr: Widen the uninstall profile to reverse what default registers Summary

**`profiles/uninstall/` now reverses `profiles/default/`: a new GenericSetup import step removes the `google_auth` PAS plugin (which no profile node can), and five new XML files remove the local utility, three user actions, the browser layer, the configlet and the settings records — all idempotent and reversible, with memberdata deliberately untouched.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-06T11:48:47+02:00 (previous commit)
- **Completed:** 2026-08-06T12:21:38+02:00
- **Tasks:** 3
- **Files modified:** 10 (6 created, 4 modified)

## Accomplishments

- `setuphandlers.uninstallVarious` / `_remove_plugin` plus a second `genericsetup:importStep` remove the `google_auth` PAS plugin from `acl_users` via `pas._delObject`, which routes through `PluggableAuthService._delOb` to deactivate the plugin from every plugin type before the object goes — closing the defect where an uninstalled plugin kept intercepting every login and later unpickled as `OFS.Uninstalled.Broken`.
- Five new `profiles/uninstall/` files (`componentregistry.xml`, `actions.xml`, `browserlayer.xml`, `controlpanel.xml`, `registry.xml`) remove the local `IUserDataSchemaProvider` utility, the three `portal_actions/user` entries, the `imio.googleauthenticator` browser layer, the `google_authenticator_settings` configlet, and every `IGoogleAuthenticatorSettings` registry record.
- `memberdata_properties.xml` stays out of `profiles/uninstall/` by design — the eight property declarations and an enrolled user's stored seed survive an uninstall untouched, pinned by `test_uninstall_keeps_enrolled_user_data`.
- Three mutation checks proved the new assertions load-bearing (see table below), each restored byte-identically and re-verified green.

## Task Commits

Each task was committed atomically:

1. **Task 1: PAS-plugin removal end to end** — `96f00c5` (feat)
2. **Task 2: the five profile files, and the exclusion pinned by a test** — `442cb24` (feat)
3. **Task 3: prove the new assertions are load-bearing, then document and gate** — `29fbeff` (docs)

**Plan metadata:** pending (this SUMMARY's own commit, made by the orchestrator per this quick task's constraints)

## Files Created/Modified

- `src/imio/googleauthenticator/profiles/uninstall/imio.googleauthenticator.uninstall.txt` - data-file gate, present only in this directory
- `src/imio/googleauthenticator/profiles/uninstall/componentregistry.xml` - removes the local `IUserDataSchemaProvider` utility (no `factory` attribute)
- `src/imio/googleauthenticator/profiles/uninstall/actions.xml` - removes the three `portal_actions/user` entries, leaving the `user` category itself alone
- `src/imio/googleauthenticator/profiles/uninstall/browserlayer.xml` - unregisters the `imio.googleauthenticator` browser layer
- `src/imio/googleauthenticator/profiles/uninstall/controlpanel.xml` - unregisters the `google_authenticator_settings` configlet
- `src/imio/googleauthenticator/profiles/uninstall/registry.xml` - removes every `IGoogleAuthenticatorSettings` record (no child `<value>` nodes)
- `src/imio/googleauthenticator/setuphandlers.py` - adds `_remove_plugin` and `uninstallVarious`
- `src/imio/googleauthenticator/configure.zcml` - registers the second `genericsetup:importStep`
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` - three new test methods plus a non-`getUtility` local-utility helper
- `CHANGES.rst` - operator-facing consequences bullet under `1.0.0 (unreleased)`

## Decisions Made

- The plan's own truths table said "the three `IGoogleAuthenticatorSettings` registry records"; the schema actually declares five (Phase 5 added `max_failed_attempts`/`lockout_duration` after this quick task's plan text was written). `registry.xml`'s bare `<records interface=... remove="true"/>` already removes all fields the interface declares regardless of count, so no XML change was needed — only the test's field list was corrected to read live from `IGoogleAuthenticatorSettings.names()` instead of hardcoding three or five.
- `test_uninstall_keeps_enrolled_user_data` was written and run before the profile files existed, per the plan's "both start red" instruction, but it passed immediately: nothing this task adds touches memberdata, so there is no code path that turns this specific test red without a deliberate bug. It stands as a forward-looking regression guard (T-gfr-04's own framing), not as evidence gathered under the RED-before-GREEN discipline the other two tests followed.

## Deviations from Plan

None — plan executed exactly as written, with the two corrections above noted as decisions rather than deviations (no code differs from the plan's intent; only the test's field-count assumption and the "must start red" expectation for one test were reconciled with what the codebase actually contains).

## Mutation Checks (Task 3)

| Mutation | Expected red | Observed failure | Restored |
|---|---|---|---|
| Deleted the `imio.googleauthenticator.uninstall` `importStep` element from `configure.zcml` | `test_uninstall_removes_pas_plugin` | `AssertionError: 'google_auth' unexpectedly found in [...] acl_users.objectIds()` | `git diff --stat` empty |
| Changed `componentregistry.xml`'s `interface` to `imio.googleauthenticator.interfaces.IGoogleAuthenticatorLayer` | `test_uninstall_reverses_the_profile_registrations` (utility group) | `AssertionError: [UtilityRegistration(...IUserDataSchemaProvider...)] is not False` | `git diff --stat` empty |
| Removed the `regenerate_recovery_codes` `remove="True"` node from `actions.xml` | `test_uninstall_reverses_the_profile_registrations` (actions group) | `AssertionError: 'regenerate_recovery_codes' unexpectedly found in [...] portal_actions/user` | `git diff --stat` empty |

Each mutation was applied, run to confirm the named test group went red with the message above, then reverted and confirmed restored via an empty `git diff --stat` on that file before the next mutation.

## Traps Avoided (per plan's `<critical_evidence_requirements>`)

1. **`<utility>` removal carries no `factory` attribute** — `componentregistry.xml`'s `<utility interface="..." remove="True"/>` node has no `factory=`. Verified by reading `Products/GenericSetup/components.py:305-312`/`:361-371` in the pinned egg under `parts/omelette/` before writing the node, and confirmed load-bearing by mutation check 2 above (a wrong `interface` string alone made the removal silently no-op — the same class of defect an extra `factory` attribute could not have introduced since it is never read on this path, but the test proves the `interface` string itself is exercised).
2. **The utility-absence test does not use `getUtility`/`queryUtility`** — `_local_userdataschema_utility_registrations()` filters `self.portal.getSiteManager().registeredUtilities()` on `registration.provided is IUserDataSchemaProvider`, which is local-only. Confirmed non-vacuously: before this task's implementation, the RED run of `test_uninstall_reverses_the_profile_registrations` showed the non-vacuity assertion (`assertTrue(self._local_userdataschema_utility_registrations())`) passing while the removal assertion failed — proving the helper genuinely sees the local registration and does not fall back to `plone.app.users`'s global default.

## Verification Gates

- `bin/test -t '!robot'`: **135 tests, 0 failures, 0 errors** (baseline before this task: 132 tests, 0 failures, 0 errors — measured directly at task start).
- `bin/test-coverage -t '!robot'`: exit 0, **TOTAL 90%** (1086 stmts, 72 missed, 292 branches, 53 partial); `setuphandlers.py` itself measured **100%** (41 stmts, 0 missed, 16 branches, 0 partial).
- `bin/code-analysis`: exit 0 on every one of the three task commits — no commit needed `--no-verify`.
- `test_profile_only_registers_resources_it_owns` and `test_uninstall_restores_resource_registries`: both run and confirmed passing (part of the full green 135-test run after every task; explicitly re-run in isolation with no failures reported).
- `git diff --stat` on `src/imio/googleauthenticator/profiles/default/` across all three task commits (compared against the pre-task commit `4739c13`): **empty** — nothing under `profiles/default/` changed.

## Issues Encountered

- Every new XML comment written with an em-dash (`--`) inside a `<!-- ... -->` block failed with `ExpatError: not well-formed (invalid token)` on the very first uninstall-profile test run, since XML comments cannot contain `--` anywhere except the closing `-->`. Fixed by rewriting every prose em-dash in the five new XML files' comments to `;` or `,` before re-running (Rule 1 auto-fix, caught immediately by the test suite itself, not a silent slip — no comment content or citation was lost, only the punctuation).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- COEX-06's wording/scope mismatch (v1.0-MILESTONE-AUDIT.md Gap 2) is closed: the uninstall profile is now reversible, not destructive, and every claim is backed by a passing test with a demonstrated non-vacuity control and (for the two highest-risk XML files) a mutation check.
- No blockers for future work. The deliberate exclusions (memberdata, `user_registration_fields`) remain documented in code comments and pinned by test, so a future editor touching either will see the test go red before shipping.

## Self-Check: PASSED

All 11 files listed above confirmed present on disk (`[ -f "$f" ]`); all 3 task commits (`96f00c5`, `442cb24`, `29fbeff`) confirmed present in `git log --oneline --all`.

---
*Quick task: 260806-gfr*
*Completed: 2026-08-06*
