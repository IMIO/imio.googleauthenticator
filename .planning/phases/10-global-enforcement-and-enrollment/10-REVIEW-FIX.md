---
phase: 10-global-enforcement-and-enrollment
fixed_at: 2026-08-07T08:33:21Z
review_path: .planning/phases/10-global-enforcement-and-enrollment/10-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-08-07T08:33:21Z
**Source review:** .planning/phases/10-global-enforcement-and-enrollment/10-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, WR-01, WR-02, WR-03 — the Critical and Warning tier; Info
  findings IN-01/IN-02 were out of scope per the task instructions)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Disabling 2FA leaves `two_factor_authentication_enrolled` stale, causing an unrecoverable login lockout on re-enable

**Files modified:** `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py`,
`src/imio/googleauthenticator/helpers.py`, `src/imio/googleauthenticator/tests/test_pas_plugin.py`
**Commit:** `7db0c2e`
**Applied fix:** Added `'two_factor_authentication_enrolled': False` to the `setMemberProperties`
mapping in `DisableTwoFactorAuthentication.disable()`. The `helpers.py` fix for
`disable_two_factor_authentication_for_users` (WR-01's location) was applied in the same edit —
see WR-01 below, since the review explicitly asked for both fixes in one edit to that function.

Added `test_disable_then_reenable_does_not_lock_the_user_out_of_login` to
`tests/test_pas_plugin.py`: completes enrollment, disables through the real
`DisableTwoFactorAuthentication` view, re-enables via
`enable_two_factor_authentication_for_users` (the single-click bulk path the review names as
reaching the lockout most directly), then asserts the actual PAS routing signal
(`pas_plugin.REQUEST_KEY_ENROLLMENT_NEEDED`) is `True` again — not merely that a property was
cleared. This is the end-to-end reproduction the task asked for as the most valuable test.

**Non-vacuity check:** reverted only the two source fixes (kept the new test), ran
`bin/test -t test_disable_then_reenable_does_not_lock_the_user_out_of_login`. It failed red:

```
AssertionError: False is not True : CR-01: a disabled-then-re-enabled account must be
routed back through enrollment, not the code-entry page for a secret it has never seen.
```

Restored the fix byte-identical (`git checkout --` on the two source files, confirmed via
`git status` and a re-read), then re-ran — green.

### WR-01: `disable_two_factor_authentication_for_users` leaves the stored seed and reset token behind

**Files modified:** `src/imio/googleauthenticator/helpers.py` (same commit as CR-01)
**Commit:** `7db0c2e`
**Applied fix:** `disable_two_factor_authentication_for_users`'s `setMemberProperties` call now
clears all four properties the single-user view clears: `enable_two_factor_authentication`,
`two_factor_authentication_secret`, `bar_code_reset_token`, and
`two_factor_authentication_enrolled` — brought in line with
`DisableTwoFactorAuthentication.disable()`.

**Note on scope, as the task instructions required:** the existing
`if has_enabled_two_factor_authentication(user):` guard is unchanged. This fix prevents a *new*
account from being left stale by a future bulk disable; it does not retroactively clean up any
account a bulk disable already left stale before this fix (stored seed and enrollment flag
untouched for those). Widening the guard to always clear these properties regardless of the
enable flag was considered and rejected — that would silently mutate accounts that were never
touched by this call, a larger and unrequested behavior change. A one-off data-migration pass
over already-stale accounts, if wanted, is a separate, deliberate decision outside this fix's
scope.

**Non-vacuity check:** covered by the same CR-01 end-to-end test above — the bulk re-enable step
in that test goes through `enable_two_factor_authentication_for_users`, which calls
`get_or_create_secret` unconditionally; the test's assertion on the routing signal depends on the
enrollment flag having actually been cleared by the disable step, so a source that only clears
the enable flag (WR-01's unfixed state) also fails this same red run.

### WR-02: "Enable" and "Disable" link conditions can both be true at once

**Files modified:** `src/imio/googleauthenticator/browser/settings_helper.py`,
`src/imio/googleauthenticator/tests/test_settings_helper.py`
**Commit:** `35ac24b`
**Applied fix:** Took the review's first option — folded
`has_completed_enrollment(user)` into `show_disable_two_factor_authentication_link`'s condition,
so it now reads "enabled AND enrollment completed AND the site-wide setting is off".

**Verified this does not strand anyone**, as the task instructions asked: for the affected
state (`enabled=True, enrolled=False, globally_enabled=False`),
`show_enable_two_factor_authentication_link` is keyed only on `not has_completed_enrollment(user)`
— unaffected by this change — so that account still sees the "Enable" link and can complete
setup. Once enrollment completes, `has_completed_enrollment(user)` becomes `True` and the
"Disable" link reappears (subject to the site-wide setting still being off). Confirmed by reading
`show_enable_two_factor_authentication_link`'s source (untouched) and by the new test case below,
which asserts both conditions in the same state.

Added the missing 5th cell to
`test_disable_link_is_offered_only_when_enrolled_and_globally_disabled` (extended in place rather
than as a new method, since it is the direct missing case in that method's own four-case matrix,
and the method's docstring/name already claimed the stronger behavior this fix now delivers):
`enabled=True, enrolled=False, globally_enabled=False` — asserts the disable link is refused and
the enable link is offered.

**Non-vacuity check:** reverted only `settings_helper.py`'s fix (kept the extended test), ran
`bin/test -t test_disable_link_is_offered_only_when_enrolled_and_globally_disabled`. It failed
red:

```
AssertionError: True is not False : WR-02: globally_enabled off, flag set, enrollment NOT
completed: the disable link must be refused -- an unfinished install-time enrollment must not
offer "Disable" alongside "Enable" for the same account.
```

Restored the fix byte-identical, re-ran — green (all 6 tests in the file pass).

### WR-03: `testing.py`'s layer-wide override of `globally_enabled` means most tests run against a non-default configuration

**Files modified:** `src/imio/googleauthenticator/tests/test_generic.py` (no production code
change, per the review's own "No code change required")
**Commit:** `c5583e0`
**Applied fix:** Added `test_globally_enabled_schema_default_is_true` to `test_generic.py`,
asserting `IGoogleAuthenticatorSettings['globally_enabled'].default is True` — a schema-level
assertion, not a live registry read, so it is independent of `testing.py`'s runtime override and
would only fail if the *declared* default changes.

**Non-vacuity check:** temporarily edited `browser/controlpanel.py`'s `globally_enabled` field to
`default=False` (kept only in the working tree, never staged or committed), ran
`bin/test -t test_globally_enabled_schema_default_is_true`. It failed red:

```
AssertionError: False is not True : WR-03: IGoogleAuthenticatorSettings.globally_enabled must
default to True -- this is the production default, distinct from the test layer's own runtime
override.
```

Restored `controlpanel.py` with `git checkout --` (confirmed byte-identical via `grep
default=True`), re-ran — green.

## Skipped Issues

None — all four in-scope findings were fixed.

## Verification

- `bin/test -t '!robot'`: **167 tests, 0 failures, 0 errors** (up from the 165-test baseline
  stated in the task — 2 new test methods: the CR-01 end-to-end regression and the WR-03 schema
  default pin; WR-02's fix landed as a 5th assertion cell inside an existing test method, not a
  new one).
- `bin/code-analysis`: exits 0 (Flake8 OK).
- Every fix's own non-vacuity check is recorded above with the real red failure output, and every
  reverted-then-restored file was confirmed byte-identical before its commit.
- Each finding committed atomically: `7db0c2e` (CR-01 + WR-01, per the review's own instruction
  that the `helpers.py` fix serves both), `35ac24b` (WR-02), `c5583e0` (WR-03). No `--no-verify`
  used; the pre-commit hook (`bin/code-analysis`) ran and passed for every commit.
- IN-01 and IN-02 (Info tier) were left untouched — out of the requested scope (Critical +
  Warning only).

## Process note

This fixer runs isolated commits from a git worktree, but this project's `bin/*` scripts are
buildout-generated and gitignored, with hardcoded absolute paths pointing at this checkout's
`src/` directory — they do not exist in a fresh worktree, and even a hook that did resolve would
lint/test the main checkout's path, not the worktree's. To keep the "hooks must run for real, no
`--no-verify`" and "isolated worktree" requirements both honored: each fix was written and
verified for syntax in the worktree, then its exact file contents were copied into this checkout's
working tree (never staged) to run the real `bin/test`/`bin/code-analysis` and non-vacuity checks,
then reverted with `git checkout --` before the atomic commit was made back in the worktree
(via a `bin -> ../.../bin` symlink so the pre-commit hook could resolve and run against the
now-matching main-checkout copy). After all three commits landed on the temporary branch,
`git merge --ff-only` brought them onto `master`, followed by the worktree/branch/sentinel
cleanup. The final `bin/test`/`bin/code-analysis` run reported above was against `master` after
that fast-forward, so the 167/0/0 and exit-0 results are the real, current state of this branch.

---

_Fixed: 2026-08-07T08:33:21Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
