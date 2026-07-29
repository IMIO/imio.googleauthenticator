---
phase: 02-registry-seeding-and-import-step-ordering
verified: 2026-07-29T16:30:00Z
status: human_needed
score: 9/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 8/9
  gaps_closed:
    - "REG-03 / ROADMAP Success Criterion 2: the getSortedImportSteps() ordering assertion is the mechanised control for the <depends name=\"plone.app.registry\"/> declaration and must fail if the <depends> line is deleted"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "REG-01 / ROADMAP Success Criterion 1 -- real site-creation smoke check"
    expected: "bin/instance fg, create a new Plone site with imio.googleauthenticator selected in the add-ons list, then grep -e \"no record\" -e \"Cannot find registry\" var/log/instance.log finds no matches"
    why_human: "Deliberately not automated per D-01/D-02 (verification: backstop must_have) -- no second-site fixture exists and no var/log/instance.log from a real site-creation run is available to this verifier. The RECORDS + ORDERING + DECLARATION assertions are the mechanised substitute control and all now pass."
---

# Phase 2: Registry Seeding and Import-Step Ordering Verification Report

**Phase Goal:** Creating a new Plone site with the add-on selected completes without the
`ska_secret_key ... no record` error, and the import-step ordering that makes it complete is
asserted in the suite rather than left to CPython 2.7 string-hash order.
**Verified:** 2026-07-29T16:30:00Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (commits `30c755b`, `f9ed419`)

## Goal Achievement

### What changed since the prior verification

The prior report (`gaps_found`, 8/9) found one blocking gap: `test_import_step_ordering` was
tautological — it stayed green with `<depends name="plone.app.registry"/>` deleted from
`configure.zcml`, purely by CPython 2.7 string-hash coincidence among the now dependency-free
import steps. That is the exact failure mode the phase's own goal statement (and D-01/D-03) name
as unacceptable.

The fix (commit `30c755b`) adds `test_import_step_declares_registry_dependency`, which asserts
`portal_setup.getImportStepMetadata('imio.googleauthenticator')['dependencies']` contains
`'plone.app.registry'` — the pre-sort declaration GenericSetup parsed from ZCML, not the post-sort
flattened tuple. `test_import_step_ordering` is kept, re-docstringed as the outcome check ("on its
own it proves nothing... the two together assert both the declaration and its effect"), rather than
deleted or left silently mischaracterized.

Commit `f9ed419` updates the stale ROADMAP SC-2/SC-3 wording and the stale `CHANGES.rst` bullet
flagged in the prior report.

### Independent re-verification of the fix (not taken on trust)

Ran the exact experiment myself, from a clean tree, rather than accepting the SUMMARY/orchestrator's
account:

1. `find . -name '*.pyc' -delete` (avoids the stale-`.pyc` false-positive noted in the prior report).
2. `bin/test -t '!robot'` on the unmodified tree: **`Ran 30 tests with 0 failures and 0 errors`**
   (was 29 at the prior verification — the one new test).
3. Deleted `<depends name="plone.app.registry"/>` from `configure.zcml` (converted the
   `genericsetup:importStep` block back to self-closing), confirmed the edit is still well-formed
   XML (`xml.dom.minidom.parse` exits 0).
4. `bin/test -t test_import_step_declares_registry_dependency` on the mutated tree:
   **1 failure** — `AssertionError: 'plone.app.registry' not found in ()`. This is the new control
   catching the exact regression it exists to catch.
5. `bin/test -t test_import_step_ordering` on the same mutated tree: **0 failures** — confirms the
   kept outcome-check test is *still* tautological on its own in this fixture (as its docstring now
   says explicitly), which is exactly why the declaration test above is the one that must exist.
6. Restored `configure.zcml` from a pre-edit backup, confirmed `git status` is clean and
   `git diff --stat` is empty, re-ran `bin/test -t '!robot'`: back to 30/0/0.

This closes the gap: a future deletion of the `<depends>` line is now caught by
`test_import_step_declares_registry_dependency`, independent of whether the topological sort's
emergent order happens to still agree with it.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 / REG-01 (`verification: backstop`, D-01/D-02): creating a new Plone site with the add-on selected completes with no `ska_secret_key ... no record` in `var/log/instance.log` | ⚠️ Abstain (`insufficient_spec`) | No automated second-site fixture exists (deliberately, per D-01) and no `var/log/instance.log` from a real site-creation run is available to this verifier. Routed to Human Verification below, per D-02's own design. Unchanged from prior verification. |
| 2 | SC2 / REG-03: the ordering assertion is a genuine mechanised control for the `<depends>` declaration, not tautological hash-order luck | ✓ **VERIFIED (gap closed)** | `test_import_step_declares_registry_dependency` asserts `getImportStepMetadata(...)['dependencies']` contains `'plone.app.registry'`. Independently reproduced: deleting the `<depends>` line makes this test fail (`'plone.app.registry' not found in ()`), while `test_import_step_ordering` alone still passes on the same mutated tree — confirming the declaration test, not the ordering test, is the real control. Both tests are retained, and `test_import_step_ordering`'s docstring now says in words that it proves nothing on its own. |
| 3 | REG-02: import step declares `<depends name="plone.app.registry"/>` | ✓ VERIFIED | `src/imio/googleauthenticator/configure.zcml:50` — present, well-formed (`xml.dom.minidom.parse` exits 0). |
| 4 | SC3 / REG-04: nested `runImportStepFromProfile` re-entry is gone from `src/`; `ska_secret_key` is reliably non-empty after install | ✓ VERIFIED | `grep -rn runImportStepFromProfile src/` (after a fresh `.pyc` purge) returns nothing, exit 1. `setuphandlers.setupVarious` calls `_setup_secret_key()`, a direct `get_app_settings()` read + conditional assignment — no nested profile import. `test_install_seeds_ska_secret_key` passes. ROADMAP SC3 wording now matches this implementation exactly (commit `f9ed419`): "seeded once at install time by `setuphandlers._setup_secret_key()`, with `get_ska_secret_key()` a pure read" — the stale "lazy accessor" phrasing flagged in the prior report is gone. |
| 5 | SC4 / REG-05: re-applying the default profile leaves a known `ska_secret_key` unchanged | ✓ VERIFIED | `test_reapply_profile_does_not_reset_ska_secret_key` sets a distinctive literal, calls `applyProfile`, asserts `assertEqual` against that same literal. Passes in the full suite run. |
| 6 | SC5 / BUG-04: derived `ska` key separates its components — two tuples sharing a bare concatenation derive to different keys | ✓ VERIFIED | `test_get_ska_secret_key`: fixture collision asserted explicitly, then exact-string equality (`u'2:ab0:2:cd'`) and `assertNotEqual` against the second fixture's derivation. Passes. |
| 7 | `get_browser_hash` returns `u''`, never `None`, so `len()` on a login path cannot raise `TypeError` | ✓ VERIFIED | `helpers.py:221-225` `except` branch returns `''`, unchanged. `test_get_browser_hash` asserts `assertEqual('', result)` and `assertIsNotNone(result)`. Passes. |
| 8 | Whole suite green; all four `ska` derivation consumers unmodified | ✓ VERIFIED | `bin/test -t '!robot'` run live by this verifier: **30 tests, 0 failures, 0 errors**. `git diff --stat` over `pas_plugin.py`, `browser/forms/token.py`, `browser/forms/reset_bar_code.py`, `browser/forms/request_bar_code_reset.py` across the whole phase's commit range is empty — no changes. |
| 9 | CR-01 fix: `get_ska_secret_key()` does not raise `TypeError` on a falsy/`None` user secret | ✓ VERIFIED | `helpers.py:275`: `user.getProperty(...) or ''`. `test_get_ska_secret_key_handles_missing_secret_property` passes. |
| 10 | CR-02 fix: `get_ska_secret_key()` is a pure read and does not mutate the registry | ✓ VERIFIED | `helpers.py:250-269`: no write branch; empty key raises `ValueError` (fail-closed). `test_get_ska_secret_key_does_not_mutate_registry` passes. |

**Score:** 9/9 machine-checkable truths verified (the REG-03 gap from the prior verification is
closed). 1 additional truth (REG-01/SC1) is a declared `verification: backstop` and is excluded
from the denominator per its own design (D-02) — routed to Human Verification instead, unchanged
from the prior report.

### Regression Check on Previously-Passed Truths

The gap-closure commits touched `test_setuphandlers.py`, `CHANGES.rst`, and `ROADMAP.md` — files
that back several of the 8 previously-verified truths. Re-checked each:

- **REG-02 / configure.zcml**: unchanged by the gap-closure commits; still present and well-formed.
- **REG-04 / setuphandlers.py, helpers.py**: unchanged by the gap-closure commits (only
  `test_setuphandlers.py` was touched, adding a new test method and re-docstringing an existing
  one — no assertion in the five pre-existing methods was weakened or removed).
- **REG-05, BUG-04, CR-01, CR-02**: their backing test methods (`test_reapply_profile_does_not_reset_ska_secret_key`,
  `test_get_ska_secret_key`, `test_get_ska_secret_key_handles_missing_secret_property`,
  `test_get_ska_secret_key_does_not_mutate_registry`) are byte-for-byte unchanged; confirmed by
  reading the current file and comparing against the prior verification's evidence.
- **Whole-suite regression**: `bin/test -t '!robot'` — 30/0/0, no new failures, one new test
  (the count previously was 29).

No regressions found.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/configure.zcml` | Declared import-step ordering | ✓ VERIFIED | `<depends name="plone.app.registry"/>` present at line 50, well-formed XML. Unchanged since prior verification. |
| `src/imio/googleauthenticator/setuphandlers.py` | Install-time seeding, no nested re-entry | ✓ VERIFIED | 71 lines. `_setup_secret_key()` — direct `get_app_settings()` call + conditional assignment; no `runImportStepFromProfile`. Unchanged. |
| `src/imio/googleauthenticator/helpers.py` | `get_ska_secret_key` — pure read, netstring derivation | ✓ VERIFIED | No mint branch; fail-closed `raise ValueError`; `u''.join(...)` derivation present. Unchanged. |
| `src/imio/googleauthenticator/tests/test_setuphandlers.py` | Ordering/declaration/records/seed/mutation/reapply assertions | ✓ VERIFIED | 143 lines, 6 well-named methods (was 5). New `test_import_step_declares_registry_dependency` is the closed gap; `test_import_step_ordering` retained with an honest, self-limiting docstring. |
| `src/imio/googleauthenticator/tests/test_helpers.py` | `TestSkaSecretKey` — derivation, collision, browser-hash guard | ✓ VERIFIED | 200 lines, unchanged since prior verification. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `configure.zcml` | GenericSetup import-step topological sort | `<depends name="plone.app.registry"/>` | ✓ WIRED (gap closed) | Declaration present, well-formed, and now proven to be the actual control: `test_import_step_declares_registry_dependency` fails when the line is removed, independent of the emergent hash-order coincidence that used to mask its absence. |
| `helpers.py get_ska_secret_key` | `plone.registry IGoogleAuthenticatorSettings.ska_secret_key` | Pure read, `ValueError` if empty | ✓ WIRED | Unchanged; no write path remains. |
| `setuphandlers.setupVarious` | `helpers.get_app_settings` | `_setup_secret_key()` seeds `ska_secret_key` at install | ✓ WIRED | Unchanged. |

### Behavioral Spot-Checks / Probe Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green | `bin/test -t '!robot'` (run live by this verifier, `.pyc` purged first) | `Ran 30 tests with 0 failures and 0 errors` | ✓ PASS |
| No nested re-entry in source | `grep -rn runImportStepFromProfile src/` | no output, exit 1 | ✓ PASS |
| Declaration control genuinely catches removal | Deleted `<depends>` line, reran `bin/test -t test_import_step_declares_registry_dependency` on the mutated tree | 1 failure — `'plone.app.registry' not found in ()` | ✓ PASS — the gap is closed |
| Kept outcome-check is honestly self-limiting | Same mutated tree, reran `bin/test -t test_import_step_ordering` | 0 failures — confirms this test alone still cannot detect the removal, matching its own updated docstring | ✓ PASS (documents the limitation rather than hiding it) |
| Reverted mutation leaves a clean tree | `git status`, `git diff --stat` after restoring `configure.zcml` | clean tree, empty diff | ✓ PASS |
| No `check=False` bypass reintroduced | `grep -n check=False src/imio/googleauthenticator/helpers.py` | no match | ✓ PASS |
| Four `ska`-derivation consumers unmodified across the whole phase | `git diff --stat` over `pas_plugin.py`, `browser/forms/token.py`, `browser/forms/reset_bar_code.py`, `browser/forms/request_bar_code_reset.py` (full phase range) | empty | ✓ PASS |
| No project-declared `scripts/*/tests/probe-*.sh` | `find scripts -path '*/tests/probe-*.sh'` | none found; phase is not migration/probe-based | N/A — SKIPPED |

All experimental file edits made during this re-verification (`configure.zcml`) were reverted from
a pre-edit backup; `git status` confirms a clean working tree and the full suite is green (30/0/0)
at time of writing this report.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| REG-01 | 02-01 | Site install completes without the `ska_secret_key ... no record` error | ⚠️ NEEDS HUMAN | `verification: backstop` per D-02; DECLARATION/ORDERING/RECORDS assertions are the mechanised proxy — all now pass, including the previously-flagged gap. |
| REG-02 | 02-01 | `<depends name="plone.app.registry"/>` declared | ✓ SATISFIED | `configure.zcml:50` |
| REG-03 | 02-01 | Ordering asserted via a genuine mechanised control, not string-hash chance | ✓ **SATISFIED (was BLOCKED)** | `test_import_step_declares_registry_dependency` — independently reproduced to fail on `<depends>` removal |
| REG-04 | 02-01 | No nested re-entry; `ska_secret_key` reliably non-empty | ✓ SATISFIED | `setuphandlers._setup_secret_key`, `test_install_seeds_ska_secret_key`; ROADMAP/REQUIREMENTS wording now matches the shipped mechanism |
| REG-05 | 02-01 | Re-apply does not reset `ska_secret_key` | ✓ SATISFIED | `test_reapply_profile_does_not_reset_ska_secret_key` |
| BUG-04 | 02-02 | Derived key separates its components | ✓ SATISFIED | `test_get_ska_secret_key` |

No orphaned requirements — all 6 IDs mapped to this phase in `REQUIREMENTS.md` (lines 174-178, 219)
appear in a plan's `requirements` frontmatter and are accounted for above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/imio/googleauthenticator/helpers.py` | 336, 364 | Pre-existing `FIXME` markers | ℹ️ Info | Predate this phase (Lukas Graf, 2015); not introduced or touched by Phase 2's commits, including the gap-closure commits. Not this phase's debt. |

The previously-flagged stale `CHANGES.rst` bullet is fixed (commit `f9ed419`) and no longer an
anti-pattern. No blocking debt markers (`TBD`/`FIXME`/`XXX` without a tracked-issue reference) were
introduced by this phase's own commits, including the two gap-closure commits reviewed here.

### Human Verification Required

### 1. REG-01 / ROADMAP Success Criterion 1 — real site-creation smoke check

**Test:** `bin/instance fg`, create a new Plone site with `imio.googleauthenticator` selected in the
add-ons list, then `grep -e "no record" -e "Cannot find registry" var/log/instance.log`.
**Expected:** No matches — the site installs cleanly with no `IGoogleAuthenticatorSettings defines a
field ska_secret_key, for which there is no record` line.
**Why human:** Deliberately not automated per D-01 (cost of a second-site fixture judged not worth
it; the DECLARATION/RECORDS/ORDERING mechanised assertions are the substitute control, and all three
now pass, including the previously-flagged gap). This verifier has no `var/log/instance.log` from a
real site-creation run to inspect, so it abstains (`insufficient_spec`) rather than guessing, per
D-02's own explicit design. Unchanged from the prior verification — this item was never part of the
gap, and closing the gap does not remove the need for this one backstop check.

### Gaps Summary

**No gaps remain.** The single blocking gap from the prior verification — the REG-03 ordering
assertion being tautological and not an actual control for the `<depends>` declaration — is closed.
This was independently re-verified in this session (not taken on trust from the SUMMARY or the
orchestrator's account): deleting `<depends name="plone.app.registry"/>` now makes
`test_import_step_declares_registry_dependency` fail with the exact error the gap-closure commit
claims (`'plone.app.registry' not found in ()`), while the old `test_import_step_ordering` test
predictably still passes on its own — confirming the new test, not the old one, is what actually
guards the requirement, and that the old test's docstring is now honest about its own limits.

All 8 previously-verified truths were re-checked for regression given that the gap-closure commits
touched `test_setuphandlers.py`, `CHANGES.rst`, and `ROADMAP.md` — none regressed; the five
pre-existing test methods in `test_setuphandlers.py` are byte-identical to what was verified before.

The stale `CHANGES.rst` bullet and stale ROADMAP SC3 wording flagged as non-blocking documentation
issues in the prior report are also both fixed (commit `f9ed419`), confirmed by direct diff
inspection.

The one remaining item — REG-01's `var/log/instance.log` smoke check — is an intentionally
un-automated `verification: backstop` must_have (D-01/D-02), not a gap. It routes this phase to
`human_needed` rather than `passed`, exactly as it did in the prior verification; nothing about
closing the REG-03 gap changes that routing.

---

_Verified: 2026-07-29T16:30:00Z_
_Verifier: Claude (gsd-verifier)_
