---
phase: 02-registry-seeding-and-import-step-ordering
fixed_at: 2026-07-29T13:53:31Z
review_path: .planning/phases/02-registry-seeding-and-import-step-ordering/02-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-07-29T13:53:31Z
**Source review:** .planning/phases/02-registry-seeding-and-import-step-ordering/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope (critical + warning, per `fix_scope: critical_warning`): 5 (CR-01, CR-02, WR-01, WR-02, WR-03)
- Fixed: 5
- Skipped: 0

Out of scope, untouched: IN-01, IN-02 (Info).

## Fixed Issues

### CR-02: Lazy-minting `ska_secret_key` inside a getter writes registry state from an abort-prone request path

**Files modified:** `src/imio/googleauthenticator/setuphandlers.py`, `src/imio/googleauthenticator/helpers.py`, `src/imio/googleauthenticator/tests/test_setuphandlers.py`
**Commit:** `f9f72bc`
**Applied fix:** This is the important one, and it revises two of this phase's own locked
decisions (D-04, D-05) — done with the user's explicit authorisation, recorded in
`02-01-SUMMARY.md`'s new "Post-review revision" section.

- Restored install-time seeding: `setuphandlers._setup_secret_key()` now calls
  `get_app_settings()` directly and sets `ska_secret_key = unicode(uuid4())` if it is
  empty, called from `setupVarious`. D-04's actual intent (no nested
  `runImportStepFromProfile` re-entry) is kept intact — the restored seeding relies on
  the REG-02 `<depends name="plone.app.registry"/>` declaration to guarantee the
  registry records already exist by the time `setupVarious` runs, so no nested profile
  re-import is needed.
- Made `helpers.get_ska_secret_key()` a pure read again: removed the
  `if not ska_secret_key: ... settings.ska_secret_key = ...` mint branch. In its place,
  an empty `ska_secret_key` at read time now raises `ValueError` (uncaught, fail-closed
  — surfaces as a 500 via `RENAME-11`'s `_dont_swallow_my_exceptions = True`, never a
  silent password-only fallthrough). This satisfies the fix instruction's constraint #3:
  no swallowable-`KeyError` bypass was reintroduced, and no weak/empty key is ever
  silently produced.
- Rewrote `test_setupVarious`'s assertions to match the revised behaviour (install now
  seeds a non-empty key; `get_ska_secret_key()` must NOT mutate the registry — this is
  the "test that actually catches this class of bug" the fix instructions asked for,
  since a happy-path-only test would not have caught CR-02) and split it into five
  separately-named test methods (this also closes WR-03 — see below).

### CR-01: `get_ska_secret_key()` raises unhandled `TypeError` on a falsy/`None` user secret

**Files modified:** `src/imio/googleauthenticator/helpers.py`, `src/imio/googleauthenticator/tests/test_helpers.py`
**Commit:** `8d703e1`
**Applied fix:** `user_secret = user.getProperty('two_factor_authentication_secret')`
changed to `... or ''`, mirroring the existing guard in the sibling `get_secret()`
function, applied right where the review's fix suggestion placed it. Netstring framing
(BUG-04) is untouched — only the input is coerced before `len()` is taken, so the
separation property (and its existing collision test in `test_get_ska_secret_key`) is
unaffected. Added a regression test,
`TestSkaSecretKey.test_get_ska_secret_key_handles_missing_secret_property`, using a
`FakeUser` whose `getProperty` returns `None` regardless of the (absent) default
argument — this both closes CR-01 and satisfies WR-02's "add the falsy/None component
test" fix. Note: CR-01's line sits inside the same function CR-02 revised; both fixes
touch `get_ska_secret_key()`, but the two changes are on non-adjacent lines and were
verified/committed as two separate hunks (CR-02 first, CR-01 second, applied on top).

### WR-01: `get_ska_secret_key()` is a mutating getter with an undocumented side effect

**Files modified:** `src/imio/googleauthenticator/helpers.py` (via commit `f9f72bc`)
**Commit:** `f9f72bc`
**Applied fix:** Dissolved by the CR-02 fix, as the review itself anticipated
("WR-01 largely dissolves once CR-02 makes the getter read-only again"). Verified: after
the CR-02 revision, `get_ska_secret_key()` no longer writes to `plone.registry` under
any code path — it only reads `settings.ska_secret_key` and raises if empty. The
docstring was updated (as part of the CR-02 commit) to state plainly that this function
does NOT mint or persist the key and why, closing the "undocumented side effect" gap
without needing a separate `ensure_ska_secret_key()` split (no side effect remains to
document as a mutation — only the fail-closed raise, which the docstring now covers).
No side effects survive to document further.

### WR-02: No test exercises `get_ska_secret_key()` with a falsy/`None` secret component

**Files modified:** `src/imio/googleauthenticator/tests/test_helpers.py`
**Commit:** `8d703e1` (same commit as CR-01 — the fix instructions named this test as
part of CR-01's own regression coverage requirement)
**Applied fix:** Added `test_get_ska_secret_key_handles_missing_secret_property`
(see CR-01 above). Asserts the derivation returns a well-formed `unicode` result instead
of raising when the secret component is `None`.

### WR-03: `test_setupVarious` bundles five independent assertion groups into one method

**Files modified:** `src/imio/googleauthenticator/tests/test_setuphandlers.py`
**Commit:** `f9f72bc` (bundled with the CR-02 rewrite of this same file, since CR-02
already required rewriting every assertion group's expected values)
**Applied fix:** Split into five methods, each named for its requirement and each with
its own docstring: `test_import_step_ordering` (REG-03),
`test_registry_records_exist_after_install` (REG-01/REG-02), `test_install_seeds_ska_secret_key`
(REG-04, revised), `test_get_ska_secret_key_does_not_mutate_registry` (CR-02 guard),
`test_reapply_profile_does_not_reset_ska_secret_key` (REG-05). A failure in one now
names exactly which requirement broke, per the review's fix suggestion.

## Requirement / decision impact (per task instructions)

- **D-04 and D-05 revised.** Recorded in `02-01-SUMMARY.md`'s new "Post-review revision"
  section: D-04's seeding deletion and D-05's getter-mint are both reversed; D-04's
  actual intent (no nested `runImportStepFromProfile`) is explicitly kept.
- **REG-01, REG-02, REG-03, BUG-04 — still hold**, unaffected by this revision (verified
  by the still-passing `test_import_step_ordering`, `test_registry_records_exist_after_install`,
  and the unchanged `test_get_ska_secret_key` collision test in `test_helpers.py`).
- **REG-05 — still holds**, re-verified against the revised code
  (`test_reapply_profile_does_not_reset_ska_secret_key`).
- **REG-04 — revised, not broken.** The literal wording "`ska_secret_key` is minted by a
  lazy accessor on first use" no longer describes the shipped code; the underlying goal
  (no nested profile re-entry, `ska_secret_key` reliably non-empty) is still met, now via
  install-time seeding instead. `REQUIREMENTS.md`'s REG-04 line was updated to describe
  the actual mechanism rather than left silently mismatched against a `[x]` checkbox.

## Verification

`bin/test -t '!robot'` (full suite, run in the main repo after fast-forwarding the fix
commits from the isolated worktree):

```
Ran 29 tests with 0 failures and 0 errors in 4.309 seconds.
```

Targeted re-run of every new/renamed test named above (`test_import_step_ordering`,
`test_registry_records_exist_after_install`, `test_install_seeds_ska_secret_key`,
`test_get_ska_secret_key_does_not_mutate_registry`, `test_reapply_profile_does_not_reset_ska_secret_key`,
`test_get_ska_secret_key`, `test_get_ska_secret_key_handles_missing_secret_property`):

```
Ran 7 tests with 0 failures and 0 errors in 1.499 seconds.
```

`grep -rn runImportStepFromProfile src/*.py src/**/*.py` — the only match is inside a
docstring in `setuphandlers.py` explaining that the nested re-entry was NOT
reintroduced; no executable call site exists. `grep -c 'check=False'
src/imio/googleauthenticator/helpers.py` returns 0 (no swallowable-bypass reintroduced,
per the fix instructions' constraint #3).

## Unresolved items

None. All 5 in-scope findings (CR-01, CR-02, WR-01, WR-02, WR-03) are fixed and verified
by the full suite. IN-01 and IN-02 (Info) were left untouched per `fix_scope:
critical_warning`.

---

_Fixed: 2026-07-29T13:53:31Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
