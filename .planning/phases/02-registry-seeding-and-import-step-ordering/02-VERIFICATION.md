---
phase: 02-registry-seeding-and-import-step-ordering
verified: 2026-07-29T14:06:22Z
status: gaps_found
score: 8/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "REG-03 / ROADMAP Success Criterion 2: the getSortedImportSteps() ordering assertion is the mechanised control for the <depends name=\"plone.app.registry\"/> declaration -- 'the assertion is the control, not the rename' -- and must fail if the <depends> line is deleted"
    status: failed
    reason: >
      Empirically disproven by removing the line and re-running the exact test. With
      src/imio/googleauthenticator/configure.zcml's <depends name="plone.app.registry"/>
      child element deleted, test_import_step_ordering still passes (0 failures) --
      'imio.googleauthenticator' still sorts after 'plone.app.registry' (index 51 vs 36
      of 52 steps), purely by CPython 2.7 string-hash order among the now dependency-free
      steps. This is precisely the failure mode Phase 2's own goal statement, D-01 and D-03
      name as unacceptable: "the assertion is the control, not the rename" / must not be
      "left to CPython 2.7 string-hash order". As currently written the test does not
      distinguish "ordered by declared dependency" from "ordered by hash-order coincidence",
      so it would not catch a regression where the <depends> line is silently removed --
      exactly the scenario the phase exists to make impossible. Restored the deleted line and
      re-ran the full suite (29 tests, 0 failures, 0 errors) to confirm no residual change was
      left in the tree.
    artifacts:
      - path: "src/imio/googleauthenticator/tests/test_setuphandlers.py"
        issue: "test_import_step_ordering (lines 44-56) asserts steps.index('imio.googleauthenticator') > steps.index('plone.app.registry') on the flattened getSortedImportSteps() tuple. This assertion is satisfied by hash-order coincidence in the current fixture independent of the <depends> declaration -- verified by deleting the declaration and observing the same assertion still pass."
    missing:
      - "A test that actually distinguishes 'ordered because of the declared dependency' from 'ordered by coincidental hash order' -- e.g., assert against portal_setup's recorded per-step dependency graph (the pre-sort dependency declarations GenericSetup parses from ZCML) rather than only the post-sort flattened tuple, or otherwise pin an assertion that would break when <depends> is removed in this exact fixture."
      - "Alternatively, if the flattened-tuple assertion is kept, a documented acknowledgement that it is a snapshot check tied to today's step registry (which changes whenever any other add-on adds/removes an import step) rather than the durable mechanised control the ROADMAP and CONTEXT.md D-01/D-03 claim it to be."
---

# Phase 2: Registry Seeding and Import-Step Ordering Verification Report

**Phase Goal:** Creating a new Plone site with the add-on selected completes without the
`ska_secret_key ... no record` error, and the import-step ordering that makes it complete is
asserted in the suite rather than left to CPython 2.7 string-hash order.
**Verified:** 2026-07-29T14:06:22Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 / REG-01 (`verification: backstop`, D-01/D-02): creating a new Plone site with the add-on selected completes with no `ska_secret_key ... no record` in `var/log/instance.log` | ⚠️ Abstain (`insufficient_spec`) | No automated second-site fixture exists (deliberately, per D-01) and no `var/log/instance.log` from a real site-creation run is available to this verifier. Routed to Human Verification below, per D-02's own design. |
| 2 | SC2 / REG-03: `getSortedImportSteps()` ordering assertion is the mechanised control for the `<depends>` declaration, not tautological hash-order luck | ✗ **FAILED** | Deleted `<depends name="plone.app.registry"/>` from `configure.zcml` and reran `bin/test -t test_import_step_ordering`: **still 0 failures**. `imio.googleauthenticator` sorted at index 51 of 52 (vs. index 35 of 52 with the line present), but still after `plone.app.registry` (index 36) purely by CPython 2.7 string-hash order over the now-dependency-free step set. The test does not detect removal of the very declaration it exists to guard. See Gaps below. |
| 3 | REG-02: import step declares `<depends name="plone.app.registry"/>` | ✓ VERIFIED | `src/imio/googleauthenticator/configure.zcml:50` — present, well-formed (converted self-closing tag to open/close pair, confirmed via `xml.dom.minidom.parse`). |
| 4 | SC3 / REG-04: nested `runImportStepFromProfile` re-entry is gone from `src/`; `ska_secret_key` is reliably non-empty after install | ✓ VERIFIED (mechanism revised, see note) | `grep -rn runImportStepFromProfile src/` returns nothing after a fresh test run recompiles `.pyc` (see note below on the transient stale-`.pyc` artifact). `setuphandlers.setupVarious` calls `_setup_secret_key()`, which seeds `ska_secret_key` directly via `get_app_settings()` if empty (`setuphandlers.py:13-31`) — no nested profile import anywhere. `test_install_seeds_ska_secret_key` passes. **Wording note:** ROADMAP SC3 still reads "ska_secret_key is minted by a lazy accessor on first use" — this is now false; see "Stale ROADMAP wording" below. |
| 5 | SC4 / REG-05: re-applying the default profile leaves a known `ska_secret_key` unchanged | ✓ VERIFIED | `test_reapply_profile_does_not_reset_ska_secret_key` sets a distinctive literal, calls `applyProfile`, and asserts `assertEqual` against that same literal (not a non-emptiness check) — non-vacuous per D-13. Passes. |
| 6 | SC5 / BUG-04: derived `ska` key separates its components — two tuples sharing a bare concatenation derive to different keys | ✓ VERIFIED | `test_get_ska_secret_key`: fixture `('ab','','cd')` and `('a','','bcd')` both concatenate to `'abcd'` (asserted explicitly, proving genuine collision), but derive to `u'2:ab0:2:cd'` (asserted exactly, by equality) vs. a different string (`assertNotEqual`). Manual recomputation confirms `len('ab')=2, len('')=0, len('cd')=2` → `"2:ab"+"0:"+"2:cd"` = `u'2:ab0:2:cd'`. |
| 7 | `get_browser_hash` returns `u''`, never `None`, so `len()` on a login path cannot raise `TypeError` | ✓ VERIFIED | `helpers.py:221-225` `except` branch returns `''`. `test_get_browser_hash` asserts both `assertEqual('', result)` and `assertIsNotNone(result)` (discriminates from a truthiness-only check), plus the 40-char-digest happy path. |
| 8 | Whole suite green; all four `ska` derivation consumers (`pas_plugin.py:160`, `token.py:87`, `reset_bar_code.py:150`, `request_bar_code_reset.py:66`) unmodified | ✓ VERIFIED | `bin/test -t '!robot'` run live by this verifier: **29 tests, 0 failures, 0 errors**. Confirmed all four call sites still call `get_ska_secret_key`/`sign_user_data`/`validate_user_data` unmodified (grep against each file). |
| 9 | CR-01 fix: `get_ska_secret_key()` does not raise `TypeError` on a falsy/`None` user secret | ✓ VERIFIED | `helpers.py:275`: `user.getProperty(...) or ''`. `test_get_ska_secret_key_handles_missing_secret_property` (FakeUser returning `None`) asserts a well-formed `unicode` result. |
| 10 | CR-02 fix: `get_ska_secret_key()` is a pure read and does not mutate the registry | ✓ VERIFIED | `helpers.py:250-269`: no write branch remains; empty key raises `ValueError` (fail-closed, uncaught, surfaces as 500 per `_dont_swallow_my_exceptions = True`). Reproduced the actual pre-fix regression (reverted both D-04's install-time seeding *and* D-05's mint branch simultaneously) and confirmed the suite catches it: 2 test failures (`test_get_ska_secret_key_does_not_mutate_registry`, `test_install_seeds_ska_secret_key`). Reverted the experiment; suite is back to 29/0/0. |

**Score:** 8/9 machine-checkable truths verified (1 failed: REG-03 ordering assertion is tautological). 1 additional truth (REG-01/SC1) is a declared `verification: backstop` and is excluded from the denominator per its own design (D-02) — routed to Human Verification instead.

### Stale ROADMAP wording (REG-04 / SC3)

Per the task brief's explicit instruction to judge this rather than pattern-match it: ROADMAP.md's
Phase 2 Success Criterion 3 still reads *"`ska_secret_key` is minted by a lazy accessor on first
use rather than by a nested profile import."* This is **stale text**, not a real unmet criterion.
After the post-review revision (commits `f9f72bc`, `8d703e1`, `b4caafc`, `51ecc93`, `be8990d`,
authorized by the user to reopen locked decisions D-04/D-05):

- `ska_secret_key` is **seeded at install time** by `setuphandlers._setup_secret_key()`, not by a
  lazy accessor.
- `get_ska_secret_key()` is a **pure read** that raises `ValueError` if the key is unexpectedly
  empty — it never mints.
- The part of SC3 that *is* still true and still verified: `grep -r runImportStepFromProfile src/`
  returns nothing, and there is no nested profile re-entry anywhere in `src/`.

`REQUIREMENTS.md`'s REG-04 row was already corrected (commit `51ecc93`) to describe the actual
mechanism. **Recommendation:** update `ROADMAP.md`'s Phase 2 Success Criterion 3 wording to match
(drop "minted by a lazy accessor on first use", replace with "seeded reliably at install time"),
so a future reader of ROADMAP.md alone is not pointed at a mechanism that no longer exists. This is
a documentation-accuracy recommendation, not a gap — the underlying REG-04 intent (no nested
re-entry, a reliably non-empty key) is met, verified above.

### `.pyc` transience note (REG-04 grep clause)

Before this verifier ran any tests, `grep -rn runImportStepFromProfile src/` matched a **stale,
git-ignored `.pyc`** (`setuphandlers.pyc`, compiled before the `be8990d` docstring-reword commit,
14:52 vs. the `.py`'s 14:57 mtime). Running `bin/test` recompiled it against current source and the
grep went clean. `.pyc` files are `*.py[cod]`-ignored build artifacts (confirmed via
`git check-ignore`), not tracked, and this package's own tests set no `PYTHONDONTWRITEBYTECODE`
env var in the actually-invoked `bin/test`/`Makefile`/`base.cfg` (a grep for it found no matches
outside prose). This is not a functional gap — the source has zero occurrences and a real
`bin/instance` / `make test` run naturally regenerates a matching `.pyc` — but it means the literal
`grep -r runImportStepFromProfile src/` command is not an *idempotent* invariant independent of when
it is last run relative to a source edit; a CI step that runs the grep without first triggering a
compile could intermittently flag a stale artifact. Not blocking; noted for awareness.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/configure.zcml` | Declared import-step ordering | ✓ VERIFIED | `<depends name="plone.app.registry"/>` present at line 50, well-formed XML. |
| `src/imio/googleauthenticator/setuphandlers.py` | Install-time seeding, no nested re-entry | ✓ VERIFIED (revised) | 71 lines. `_setup_secret_key()` restored (post-CR-02) as a direct `get_app_settings()` call + conditional assignment; no `runImportStepFromProfile`. |
| `src/imio/googleauthenticator/helpers.py` | `get_ska_secret_key` — pure read, netstring derivation | ✓ VERIFIED (revised) | Mint branch removed; fail-closed `raise ValueError`; `u''.join(u'{0}:{1}'.format(len(part), part) for part in ...)` derivation present. |
| `src/imio/googleauthenticator/tests/test_setuphandlers.py` | Ordering/records/seed/mutation/reapply assertions | ⚠️ PARTIALLY VERIFIED | 112 lines, 5 well-named methods (WR-03 fix). All pass, but `test_import_step_ordering` is the tautological assertion flagged above. |
| `src/imio/googleauthenticator/tests/test_helpers.py` | `TestSkaSecretKey` — derivation, collision, browser-hash guard | ✓ VERIFIED | 199 lines (>130 min), collision fixture and exact-string assertions confirmed by manual recomputation. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `configure.zcml` | GenericSetup import-step topological sort | `<depends name="plone.app.registry"/>` | ⚠️ PRESENT BUT UNPROVEN AS CONTROLLING | Declaration present and well-formed; **empirically shown not to be what makes the assertion pass** (see gap above) — removing it left the assertion green. |
| `helpers.py get_ska_secret_key` | `plone.registry IGoogleAuthenticatorSettings.ska_secret_key` | Pure read, `ValueError` if empty | ✓ WIRED | Confirmed no write path remains; confirmed by reverting the fix (mint branch + no install seeding) and observing the suite catch it. |
| `setuphandlers.setupVarious` | `helpers.get_app_settings` | `_setup_secret_key()` seeds `ska_secret_key` at install | ✓ WIRED | `setupVarious` calls `_setup_secret_key()` unconditionally (after the marker-file guard), which reads/writes via `get_app_settings()`. |

### Behavioral Spot-Checks / Probe Execution

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite green | `bin/test -t '!robot'` (run live by this verifier) | `Ran 29 tests with 0 failures and 0 errors` | ✓ PASS |
| No nested re-entry in source | `grep -rn runImportStepFromProfile src/` (after fresh compile) | no output, exit 1 | ✓ PASS |
| `<depends>` declared | `grep -n depends src/imio/googleauthenticator/configure.zcml` | `<depends name="plone.app.registry"/>` | ✓ PASS |
| Ordering assertion is a genuine control | Deleted `<depends>` line, reran `bin/test -t test_import_step_ordering` | 0 failures (test still passes without the declaration) | ✗ **FAIL** — this is the finding driving `gaps_found` |
| CR-02 regression is genuinely caught | Reverted D-04 (install seeding) + D-05 (pure-read fix) simultaneously, reran `bin/test -t '!robot'` | 2 failures (`test_get_ska_secret_key_does_not_mutate_registry`, `test_install_seeds_ska_secret_key`) | ✓ PASS — confirms the real regression scenario is protected |
| No `check=False` bypass reintroduced | `grep -n check=False src/imio/googleauthenticator/helpers.py` | no match | ✓ PASS |
| No project-declared `scripts/*/tests/probe-*.sh` | `find scripts -path '*/tests/probe-*.sh'` | none found; phase is not migration/probe-based | N/A — SKIPPED, no probes declared for this phase |

All experimental file edits made during this verification (`configure.zcml`, `test_setuphandlers.py`
temporary print, `helpers.py`, `setuphandlers.py`) were reverted; `git status` confirms a clean
working tree and the full suite is green (29/0/0) at time of writing this report.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| REG-01 | 02-01 | Site install completes without the `ska_secret_key ... no record` error | ⚠️ NEEDS HUMAN | `verification: backstop` per D-02; RECORDS/ORDERING assertions are the mechanised proxy (RECORDS passes; ORDERING is the flagged gap above) |
| REG-02 | 02-01 | `<depends name="plone.app.registry"/>` declared | ✓ SATISFIED | `configure.zcml:50` |
| REG-03 | 02-01 | Ordering asserted via `getSortedImportSteps()`, not string-hash chance | ✗ **BLOCKED** | Assertion present but tautological in this fixture — see gap |
| REG-04 | 02-01 | No nested re-entry; `ska_secret_key` reliably non-empty | ✓ SATISFIED (mechanism revised, ROADMAP wording stale) | `setuphandlers._setup_secret_key`, `test_install_seeds_ska_secret_key` |
| REG-05 | 02-01 | Re-apply does not reset `ska_secret_key` | ✓ SATISFIED | `test_reapply_profile_does_not_reset_ska_secret_key` |
| BUG-04 | 02-02 | Derived key separates its components | ✓ SATISFIED | `test_get_ska_secret_key` |

No orphaned requirements — all 6 IDs mapped to this phase in `REQUIREMENTS.md` (lines 174-178, 219)
appear in a plan's `requirements` frontmatter and are accounted for above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `CHANGES.rst` | 20-21 | Stale changelog bullet: *"`ska_secret_key` is no longer seeded at install time; it is minted once, lazily, on first use of `get_ska_secret_key()`"* | ⚠️ Warning | This is the **opposite** of the current, post-review behavior (seeding *is* restored at install time; the getter is a pure read that never mints). Last touched in commit `7fd95e3` (plan 02-02), before the CR-02 revision commits (`f9f72bc` onward) that flipped this exact behavior. Not fixed in any of the five post-review commits. A future reader (including a Phase 3 developer) relying on `CHANGES.rst` for this package's actual behavior will be misled. |
| `src/imio/googleauthenticator/helpers.py` | 134, 156, 336, 364 | Pre-existing `TODO`/`FIXME` markers | ℹ️ Info | Predate this phase (`git blame` → `4e29c5cb`, Lukas Graf 2015); not introduced or touched by Phase 2's commits. Not this phase's debt. |

No blocking debt markers (`TBD`/`FIXME`/`XXX` without a tracked-issue reference) were introduced by
this phase's own commits.

### Human Verification Required

### 1. REG-01 / ROADMAP Success Criterion 1 — real site-creation smoke check

**Test:** `bin/instance fg`, create a new Plone site with `imio.googleauthenticator` selected in the
add-ons list, then `grep -e "no record" -e "Cannot find registry" var/log/instance.log`.
**Expected:** No matches — the site installs cleanly with no `IGoogleAuthenticatorSettings defines a
field ska_secret_key, for which there is no record` line.
**Why human:** Deliberately not automated per D-01 (cost of a second-site fixture judged not worth
it; the RECORDS/ORDERING mechanised assertions are the substitute control). This verifier has no
`var/log/instance.log` from a real site-creation run to inspect, so it abstains (`insufficient_spec`)
rather than guessing, per D-02's own explicit design.

### Gaps Summary

**One blocking gap: REG-03 / Success Criterion 2's ordering assertion does not actually control what
it claims to control.** The phase's central premise — stated in its own goal, in D-01, and in D-03 —
is that "the assertion is the control, not the rename," specifically so that a future deletion of
`<depends name="plone.app.registry"/>` is caught by the suite rather than silently passing on
CPython 2.7 string-hash luck. Deleting that exact line and re-running the exact test that is meant
to catch it shows **the test still passes** — `imio.googleauthenticator` still sorts after
`plone.app.registry` in this fixture's dependency-free hash order, just at a different (much later)
position. The mechanism the whole phase exists to eliminate (accidental hash-order correctness) is
still what makes this specific assertion green today; it is simply coincidental that it currently
agrees with the intended, declared order. This does not mean the `<depends>` declaration is wrong or
useless — REG-02 is satisfied and the declaration is real and correct — but the REG-03 test as
written provides no actual regression protection for it, contradicting the phase's own stated
purpose and its own explicit warning not to rely on hash-order coincidence.

Recommended fix: assert against GenericSetup's pre-sort dependency declarations for this step (what
`portal_setup` parsed from ZCML) rather than only the post-sort flattened tuple — or find another
assertion shape that provably breaks when `<depends>` is removed in this exact test fixture.

**Everything else in the phase holds up under adversarial re-execution**, including the two most
security-relevant behaviors (CR-01's falsy-secret guard and CR-02's no-registry-mutation guard),
both of which were independently reproduced by this verifier by reverting the actual fix and
confirming the suite fails. The stale `CHANGES.rst` bullet and the ROADMAP's stale SC3 wording are
non-blocking documentation-accuracy issues, called out above with concrete recommended edits.

---

_Verified: 2026-07-29T14:06:22Z_
_Verifier: Claude (gsd-verifier)_
