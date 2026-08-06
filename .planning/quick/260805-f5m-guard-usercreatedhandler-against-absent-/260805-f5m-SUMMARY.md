---
status: complete
quick_id: 260805-f5m
description: Guard userCreatedHandler against absent settings records
date: 2026-08-05
requirements: [COEX-10]
---

# Quick Task 260805-f5m — Summary

## What was built

A four-line guard plus its regression test, closing a defect that made this package
break Plone site creation for any site in the same Zope instance that had not installed
its GenericSetup profile.

### Files changed

| File | What the change does |
|------|----------------------|
| `src/imio/googleauthenticator/userdataschema.py` | `userCreatedHandler` now wraps its settings read in `try`/`except KeyError` and returns quietly when this add-on's registry records are absent. The `api.user.get` call moved below the guard so the bail-out path does no user lookup. The two-name parenthesised local import was split into two single-line imports, matching `.isort.cfg`'s `force_single_line`. |
| `src/imio/googleauthenticator/tests/test_setuphandlers.py` | New `test_user_creation_survives_absent_settings_records`, plus the five imports it needs (`setRoles`, `TEST_USER_ID`, `Record`, `IRegistry`, `getUtility`, `IGoogleAuthenticatorSettings`). |
| `.planning/REQUIREMENTS.md` | Adds `COEX-10` and its traceability row. |

## Verification

- **Full suite: exit code 0, 111 tests, 0 failures, 0 errors.** Was 110 before this task;
  the new test is the 111th. Run three times across the task, green each time.
- **Non-vacuity proven, not assumed.** The guard was reverted with `git checkout`, the
  new test re-run, and it errored with
  `KeyError: 'Interface ...IGoogleAuthenticatorSettings defines a field globally_enabled,
  for which there is no record.'` — the same error class the operator hit in production.
  The guard was then restored and the suite re-run green.
- **No new flake8 `E`/`W`/`F` findings.** Nine isort ordering findings (`I001`/`I003`)
  were added across the two files. Four are genuinely attributable to the imports added
  to the test file. The five in `userdataschema.py` are an artifact of `flake8-isort`
  re-diffing an already-misordered import block, proven by a control: adding a single
  no-op line to the function body of the unmodified file, touching no imports, adds one
  finding by itself. The flagged lines are top-level imports that were never edited.
  `bin/code-analysis` already fails on 500 pre-existing findings; Phase 8 (QUAL-06)
  owns that cleanup.

## Deviations from the plan

1. **Executed inline rather than via planner and executor subagents.** The operator was
   in manual command-approval mode, where subagent dispatch would have produced a long
   stream of approval prompts to accept without visible reasoning. Inline execution is
   the same pattern GSD's own `--interactive` execution mode uses; the outcome
   (atomic commits, artifacts under `.planning/quick/`, STATE.md row) is unchanged.
2. **First attempt at the test's registry restore was wrong and was fixed.** Saving the
   `Record` object and re-assigning it fails: `Record.field` resolves the field through
   `registry._fields`, which the delete removes, so the restore itself raised `KeyError`.
   The test now copies the field and value out before deleting and rebuilds a `Record`
   in the `finally` block. Worth noting because the first failure was *in the restore*,
   not in `api.user.create` — the guard was already working at that point.
3. **Splitting the local import did not reduce findings.** It was kept anyway because it
   matches the project's `force_single_line` isort setting.

## Notes for follow-up

This fix stops the crash. It does not address a **separate, larger gap the operator
found during the same session**, which is recorded against Phase 7 plan 07-04 rather
than here: turning on "Globally enabled" does not enrol users who already exist when
this add-on is installed. `is_two_factor_authentication_globally_enabled` is consulted
only by this subscriber and by `browser/settings_helper.py` (menu links); the login gate
at `helpers.py:1021` and `1044` checks only each user's own
`enable_two_factor_authentication` flag; and existing users are enrolled only when an
administrator saves the settings control panel form (`browser/controlpanel.py`
lines 125-132), never at install time. That is unresolved and needs its own decision.

## Self-Check: PASSED
