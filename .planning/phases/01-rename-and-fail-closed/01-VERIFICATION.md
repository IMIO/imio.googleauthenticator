---
phase: 01-rename-and-fail-closed
verified: 2026-07-29T09:15:00Z
status: passed
score: 6/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "Ordinary, non-malicious inputs reaching the PAS plugin (unknown username, malformed X-Forwarded-For, trailing blank line in the IP whitelist) do not crash login with an unhandled 500 -- the whitelist/lookup logic this phase touched is fail-closed, not fail-crashed"
  gaps_remaining: []
  regressions: []
---

# Phase 01: Rename and Fail-Closed Verification Report

**Phase Goal:** The package is `imio.googleauthenticator` everywhere — on disk, in the egg, in
the i18n domain, in the GenericSetup profile and its marker file — and any exception inside the
PAS plugin becomes a 500 rather than a silent fallthrough to password-only authentication.

**Verified:** 2026-07-29T09:15:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Fresh clone: `bin/instance` buildout installs the add-on, `collective.googleauthenticator` importable from nowhere, no orphan `.pyc`/`.egg-info` under the old namespace | ✓ VERIFIED | Carried forward from initial pass, no regression: `git status` shows no rename-related changes; `src/imio.googleauthenticator.egg-info` present; no `collective/googleauthenticator` path on disk |
| 2 | A test asserts `google_auth` is registered for `IAuthenticationPlugin` | ✓ VERIFIED | `test_plugin_is_registered_for_authentication` in `tests/test_pas_plugin.py:41-50`, passes in this pass's full run |
| 3 | `python setup.py sdist` produces an archive with `profiles/`, `locales/`, templates | ✓ VERIFIED | No change since initial pass; packaging paths untouched by the CR-01/02/03 fix commits |
| 4 | Dutch translation still renders; catalogues renamed, stale `.mo` deleted | ✓ VERIFIED | No change since initial pass; i18n files untouched by the fix commits |
| 5 (literal) | `_dont_swallow_my_exceptions = True` set; a test asserts a deliberately raised plugin exception yields a 500 rather than authenticating via `source_users` | ✓ VERIFIED | `pas_plugin.py:71`; `test_plugin_exception_is_not_swallowed` and its counterfactual `test_plugin_exception_is_swallowed_without_the_flag` both pass |
| 5 (intent) | Ordinary, non-malicious inputs do not crash login with the same mechanism — fail-closed, not fail-crashed, as the code's own comment states | ✓ VERIFIED | All three previously-failing paths now guarded and regression-tested (see below). Re-read the current source directly (not the SUMMARY) and confirmed each fix is present, wired, and exercised by a passing test |

**Score:** 6/6 truths verified (0 present, behavior-unverified)

### Gap Closure Detail (RENAME-11 fail-closed intent)

Each of the three findings from the previous VERIFICATION.md was re-checked directly against
current source on `HEAD`, not against SUMMARY/REVIEW-FIX claims:

| Finding | Fix location | Verified in source | Regression test | Test passes |
|---------|-------------|---------------------|------------------|-------------|
| CR-01 — `api.user.get()` returns `None` for unmatched username, then unconditional `.getUserName()` raised `AttributeError` | `pas_plugin.py:99-104` | Confirmed: `if user is None: return None` guard present before `user.getUserName()` (commit `0018bca`) | `test_unmatched_username_does_not_crash` (`test_pas_plugin.py:72-95`) — calls `authenticateCredentials({'login': 'no-such-user', ...})` with a bound request, asserts `None` returned | PASS (targeted run + full suite) |
| CR-02 — malformed `X-Forwarded-For` reaches `ipaddress.ip_address()` unguarded, raises `ValueError` | `helpers.py:478-486` | Confirmed: `try/except ValueError` around the final `ipaddress.ip_address(ip)` call, returns `None`, logs at debug (commit `e6d9e57`) | `test_extract_ip_address_from_request_ignores_malformed_ip` (`test_helpers.py:60-67`) — `HTTP_X_FORWARDED_FOR: 'not-an-ip'`, asserts `None` returned | PASS |
| CR-03 — blank whitelist line produces `ip_network('')`, raises `ValueError` | `helpers.py:503-514` (filter blanks) and `helpers.py:517-531` (`get_ip_ranges` per-entry try/except, defense in depth) | Confirmed: both fixes applied as REVIEW-FIX.md's "and/or" suggestion (commit `316d636`) | `test_get_ip_addresses_whitelist_drops_blank_lines` and `test_get_ip_ranges_skips_invalid_entries_instead_of_raising` (`test_helpers.py:30-58`) | PASS |

Targeted re-run of exactly these four tests in isolation:
`bin/test -t 'test_unmatched_username_does_not_crash|test_extract_ip_address_from_request_ignores_malformed_ip|test_get_ip_addresses_whitelist_drops_blank_lines|test_get_ip_ranges_skips_invalid_entries_instead_of_raising'`
→ **4 tests, 0 failures, 0 errors**.

Full suite re-run in this pass: `bin/test -t '!robot'` → **21 tests, 0 failures, 0 errors** (up
from 15 tests at the initial verification pass — the 6 new tests are the CR-01/02/03 regressions
plus the WR-01 companion tests added during the same fix pass).

### Additional hardening beyond the original gap (not required, found during re-check)

The fix pass and subsequent security audit closed several adjacent items while addressing the
gap. These were not part of the previous verification's required gap but are confirmed present
and do not regress anything:

- WR-01 (`helpers.py:450-462`): `PRIVATE_IPS_PREFIX` string-prefix match replaced with
  `ipaddress.ip_address(...).is_private`, fixing a false-positive that treated public
  `172.217.0.0/16` as a private proxy hop. Tested by
  `test_extract_ip_address_does_not_treat_public_172_216_as_private` and
  `test_extract_ip_address_still_strips_real_private_hops`.
- WR-04 / T-1-11: raw exception text (`_(str(e))`) removed from all three form sites that
  echoed it to end users, including a third site (`request_bar_code_reset.py:113`) found only
  during the security audit, not the original code review. `grep -rn "_(str(e))" src/` returns
  no matches — confirmed directly in this pass.
- 01-SECURITY.md: `threats_open: 0`, `status: verified`; T-1-05 (the DoS risk this whole gap was
  about) is recorded `accept`ed as a locked trade (loud outage over silent bypass for an MFA
  package) and explicitly notes it was "materially reduced" by the CR-01/02/03 fixes — consistent
  with what this pass independently confirmed in source.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/pas_plugin.py` | `None`-guard after `api.user.get()` | ✓ VERIFIED | Lines 99-104, wired into `authenticateCredentials` |
| `src/imio/googleauthenticator/helpers.py` | `try/except ValueError` in `extract_ip_address_from_request`, blank-filtering in `get_ip_addresses_whitelist`/`get_ip_ranges` | ✓ VERIFIED | Lines 478-486, 503-514, 517-531 |
| `src/imio/googleauthenticator/tests/test_pas_plugin.py` | CR-01 regression test | ✓ VERIFIED | `test_unmatched_username_does_not_crash` |
| `src/imio/googleauthenticator/tests/test_helpers.py` | CR-02/CR-03 regression tests | ✓ VERIFIED | 4 new tests present and passing |

All other artifacts from the initial verification pass (namespace package, marker file,
`MANIFEST.in`, `CHANGES.rst`, `.coveragerc`/`base.cfg`, `upgrades/` removal) are unchanged by
this gap-closure work and remain verified — no regression found.

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pas_plugin.py:authenticateCredentials` | `api.user.get()` result | `if user is None: return None` before `.getUserName()` | ✓ WIRED | Confirmed in source; behaviorally proven by `test_unmatched_username_does_not_crash` |
| `pas_plugin.py:authenticateCredentials` | `helpers.is_whitelisted_client` → `extract_ip_address_from_request` | Direct call chain, first statement | ✓ WIRED | Now returns `None` on malformed input instead of raising; proven by `test_extract_ip_address_from_request_ignores_malformed_ip` |
| `helpers.get_ip_addresses_whitelist` | `helpers.get_ip_ranges` | List of whitelist strings → list of network objects | ✓ WIRED | Blank entries filtered at the source, and `get_ip_ranges` independently defensive; proven by both new tests |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RENAME-01 through RENAME-10, RENAME-12, DOC-04 | 01-01/02/03/04 | Rename on disk, config, i18n, packaging, marker file, plugin identity | ✓ SATISFIED | Unchanged since initial pass; no regression found |
| RENAME-11 | 01-04 | `_dont_swallow_my_exceptions = True`, fail-closed not fail-crashed | ✓ SATISFIED | Both the literal flag AND the fail-closed intent are now met — the three previously-open crash paths are fixed and regression-tested |

No orphaned requirements: all 13 IDs (RENAME-01..12, DOC-04) appear in the `requirements:`
frontmatter of the four phase-01 plans, matching REQUIREMENTS.md's phase-1 allocation.

Note: REQUIREMENTS.md's phase-1 rows (lines 162-173, 232) still literally read "Gaps Found" —
this is the traceability table left over from the initial verification pass and is a document
freshness issue, not a code gap. It should be updated to reflect this passed re-verification as
part of the normal ship/complete workflow; it is not itself a phase-goal blocker.

### Anti-Patterns Found

None introduced by the gap-closure commits. Scanned `pas_plugin.py` and `helpers.py` diffs
(`0018bca`, `e6d9e57`, `316d636`, plus the WR-01/WR-04 commits) for debt markers
(`TBD`/`FIXME`/`XXX`), placeholder text, and swallow-everything `except Exception: pass` —
none found. The two exception handlers added (CR-02, CR-03) narrowly catch `ValueError` only,
consistent with the fail-closed intent, and both log at debug level before returning a safe
default. Pre-existing `:FIXME:` docstring notes in `helpers.py:310,338` are untouched by this
diff (confirmed via `git blame`) and were already tracked as BUG-06/Phase 7 in the initial pass.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Unknown username does not crash login | `bin/test -t test_unmatched_username_does_not_crash` | 1 test, 0 failures | ✓ PASS |
| Malformed X-Forwarded-For does not crash | `bin/test -t test_extract_ip_address_from_request_ignores_malformed_ip` | 1 test, 0 failures | ✓ PASS |
| Blank whitelist line does not crash | `bin/test -t test_get_ip_addresses_whitelist_drops_blank_lines` | 1 test, 0 failures | ✓ PASS |
| `get_ip_ranges` skips bad entries instead of raising | `bin/test -t test_get_ip_ranges_skips_invalid_entries_instead_of_raising` | 1 test, 0 failures | ✓ PASS |
| Full suite regression | `bin/test -t '!robot'` | 21 tests, 0 failures, 0 errors | ✓ PASS |

### Human Verification Required

None. 01-UAT.md records 29/29 automated + manual UAT checks passed, including the three human
checkpoints, prior to this re-verification. All findings in this pass are confirmed directly
against source and by passing tests; no visual, real-time, or external-service behavior is in
question.

### Gaps Summary

The single gap from the initial verification pass — three unguarded exception paths
(CR-01/02/03) that turned `_dont_swallow_my_exceptions = True` into a site-wide/ordinary-input
DoS rather than the intended fail-closed behavior — has been closed:

- Each of the three paths now has an explicit guard (`None`-check, `try/except ValueError`,
  blank-entry filtering) confirmed present in the current source, not just claimed in a summary.
- Each has a dedicated regression test that exercises exactly the previously-crashing input and
  asserts safe behavior; all four targeted tests pass, and the full 21-test suite passes with
  zero failures and zero errors (up from 15 tests at the initial pass).
- A follow-up security audit (01-SECURITY.md) independently found and closed one more
  information-disclosure site (T-1-11, `request_bar_code_reset.py`) using the same pattern as
  the code review's WR-04 fix, and confirmed `threats_open: 0`.

No regressions were introduced: the rename-only truths (1-4) and artifacts from the initial pass
are unchanged and still hold. The phase goal — package fully renamed AND fail-closed exception
handling that doesn't itself become an ordinary-input DoS — is achieved.

---

_Verified: 2026-07-29T09:15:00Z_
_Verifier: Claude (gsd-verifier)_
