---
phase: 03-encrypted-seeds-and-local-qr
plan: 03
subsystem: auth
tags: [hmac, constant-time-comparison, z3c.form, regression-test, changelog]

requires:
  - phase: 03-encrypted-seeds-and-local-qr
    plan: 01
    provides: "helpers.get_or_create_secret/ENV_VAR_NAME (IMIO_GOOGLEAUTHENTICATOR_SEED_KEY), Fernet fail-closed wrapper"
  - phase: 03-encrypted-seeds-and-local-qr
    plan: 02
    provides: "boot-time CRITICAL subscriber, README.rst deployment documentation"
provides:
  - "validate_bar_code_reset_token(stored_token, submitted_token) -- one constant-time, type-safe, empty-refusing comparison used at both reset_bar_code.py call sites"
  - "TestSetupForm.test_handleSubmit -- BUG-02 regression guard across all three SetupForm.handleSubmit branches plus the empty-token short circuit, with no production code change"
  - "CHANGES.rst entries covering the whole of Phase 3"
affects: []

tech-stack:
  added: []
  patterns:
    - "hmac.compare_digest wrapped with pre-coercion to str bytes on both operands, so a str/unicode mismatch cannot raise TypeError; empty/falsy operands refused before any comparison"
    - "z3c.form button.Handler.func to reach the undecorated handler function for direct unit testing, bypassing the @buttonAndHandler decorator"

key-files:
  created:
    - src/imio/googleauthenticator/tests/test_user_setup.py
  modified:
    - src/imio/googleauthenticator/helpers.py
    - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
    - src/imio/googleauthenticator/tests/test_helpers.py
    - CHANGES.rst

key-decisions:
  - "BUG-02 closed by regression test only, no production code change -- research and this plan's own execution both confirm redirect_url is bound on all three reachable branches of SetupForm.handleSubmit. Explicitly not a fix."
  - "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY (locked in plan 03-01's Task 1 checkpoint) used throughout -- confirmed zero IMIO_GA_SEED_KEY occurrences in src/base.cfg/README.rst/CHANGES.rst/setup.py/test-4.3.cfg after every commit in this plan."

patterns-established:
  - "Constant-time secret comparison: coerce both operands to the same Python 2 string type before hmac.compare_digest, refuse on any falsy operand, catch UnicodeEncodeError on the coercion step only (the one place in this module where catching an exception on attacker-controlled input is the fail-closed behaviour)."

requirements-completed: [BUG-02, BUG-03]

coverage:
  - id: D1
    description: "The bar-code reset token is compared in constant time through one shared helper used at both reset_bar_code.py call sites (handleSubmit and updateFields); works across all four str/unicode operand combinations; refuses empty/absent stored tokens; returns False rather than raising on non-ASCII input"
    requirement: "BUG-03"
    verification:
      - kind: unit
        ref: "tests/test_helpers.py#TestBarCodeResetToken.test_validate_bar_code_reset_token"
        status: pass
      - kind: other
        ref: "bin/python -c one-liner acceptance criterion (see Verification Detail)"
        status: pass
    human_judgment: false
  - id: D2
    description: "redirect_url is bound on all three reachable branches of SetupForm.handleSubmit (success, exception-inside-try, invalid token) plus the empty-token short circuit that skips the redirect entirely; no production code changed; test docstring states BUG-02 does not reproduce"
    requirement: "BUG-02"
    verification:
      - kind: integration
        ref: "tests/test_user_setup.py#TestSetupForm.test_handleSubmit"
        status: pass
    human_judgment: false
  - id: D3
    description: "CHANGES.rst carries entries for the whole phase: Fernet encryption and no-migration consequence, fail-closed behaviour, the new required IMIO_GOOGLEAUTHENTICATOR_SEED_KEY variable, in-process QR rendering, the dependency swap, the constant-time comparison, and this regression guard"
    requirement: null
    verification:
      - kind: other
        ref: "grep checks against CHANGES.rst (see Verification Detail)"
        status: pass
    human_judgment: false
  - id: D4
    description: "ROADMAP Phase 3 success criterion 4 -- a user enrols with a real authenticator app and logs in end to end -- verified once by a human with a real TOTP app"
    requirement: null
    verification: []
    human_judgment: true
    rationale: "Requires a physical authenticator app (Google Authenticator/FreeOTP/etc.) scanning a QR code rendered by a running bin/instance and a real login round trip -- not executable by an automated agent. Collected into the phase's end-of-phase UAT per workflow.human_verify_mode=end-of-phase; not performed during this execution."

duration: ~45min
completed: 2026-07-30
status: complete
---

# Phase 3 Plan 3: Encrypted Seeds and Local QR (Ride-Along Bug Closure + Changelog) Summary

**One constant-time `validate_bar_code_reset_token` helper closes the timing oracle at both `reset_bar_code.py` comparison sites; a four-scenario regression test proves `SetupForm.handleSubmit`'s `redirect_url` is bound on every reachable branch with zero production-code change; `CHANGES.rst` now documents the whole phase for an upgrading reader.**

## Performance

- **Duration:** ~45 min of agent-active work, no checkpoints (plan is `autonomous: true`)
- **Tasks:** 2 (both `type="auto" tdd="true"`)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- `validate_bar_code_reset_token(stored_token, submitted_token)` added to `helpers.py`: coerces both operands to the same Python 2 string type before `hmac.compare_digest`, refuses any falsy operand before comparing (closing the both-empty-strings-match hole the previous `==`/`!=` tests had), and returns `False` rather than raising on a non-ASCII submitted value
- **Both** reset-token comparison sites in `reset_bar_code.py` (`handleSubmit` and `updateFields`) now route through the shared helper -- the requirement named only one, research found two
- `TestBarCodeResetToken.test_validate_bar_code_reset_token` covers all four `str`/`unicode` combinations, a same-length mismatch, a differing-length mismatch, all empty/`None` combinations, and a non-ASCII operand
- `TestSetupForm.test_handleSubmit` drives all three reachable branches of `SetupForm.handleSubmit` (valid token/no exception, valid token/exception inside `try`, invalid token) plus the empty-token short circuit, asserting the exact `Location` redirect target for each -- **zero lines of `user_setup.py` changed**
- `CHANGES.rst` gained 7 new entries under `1.0.0 (unreleased)` covering the whole phase: seed encryption + no-migration consequence, fail-closed behaviour, the new required environment variable, in-process QR rendering, the dependency swap (with the egg-ordering hazard explained), the constant-time reset-token comparison, and this plan's regression guard

## Task Commits

1. **Task 1: BUG-03 -- one constant-time reset-token comparison, used at both call sites** -- `aa9f5fb` (fix)
2. **Task 2: BUG-02 -- lock the redirect invariant with a regression test, add no fix, and write the changelog** -- `f61be76` (test)

**Plan metadata:** *(this commit)*

## Files Created/Modified

- `src/imio/googleauthenticator/helpers.py` -- `from hmac import compare_digest` added to the stdlib import group; new `validate_bar_code_reset_token(stored_token, submitted_token)` placed next to `validate_user_data`
- `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` -- one new import line; `handleSubmit`'s `bar_code_reset_token != signature_token` and `updateFields`'s `bar_code_reset_token == token` both replaced with calls to the shared helper; nothing else in the file touched
- `src/imio/googleauthenticator/tests/test_helpers.py` -- one new import line; new `TestBarCodeResetToken` class (no layer -- pure function, no Zope state)
- `src/imio/googleauthenticator/tests/test_user_setup.py` (new, 193 lines) -- `TestSetupForm` with one `test_handleSubmit` method driving all four scenarios
- `CHANGES.rst` -- 7 new entries under the existing `1.0.0 (unreleased)` heading; no version bump, no release date

## Decisions Made

- **BUG-02 closed with no production change.** Confirmed by execution, not just by the plan's own research: `git diff HEAD~1 -- src/imio/googleauthenticator/browser/forms/user_setup.py` after Task 2's commit is empty. `redirect_url` really is bound on every reachable branch; the test's docstring states this explicitly so a future reader does not go looking for a fix that was never made.
- **Locked environment-variable name honored throughout.** Every place this plan's own text said `IMIO_GA_SEED_KEY` (the test-setup fixture, the `CHANGES.rst` entry, the acceptance-criteria greps) used `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` instead, per plan 03-01's Task 1 checkpoint decision. `git grep -n IMIO_GA_SEED_KEY -- src base.cfg README.rst CHANGES.rst setup.py test-4.3.cfg` returns no matches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `TestSetupForm.test_handleSubmit`'s TextLine widget requires unicode, not str**
- **Found during:** Task 2, first run of the new test
- **Issue:** Setting the token widget's request value as a plain `str` (e.g. `'123456'`) produced a `WrongType` extraction error rather than the expected success -- the TextLine field's converter requires `unicode` input, a call-shape detail this plan's `<behavior>` section didn't specify.
- **Fix:** `_build_form()` coerces any `str` token value to `unicode` (`.decode('ascii')`) before setting it on the request.
- **Files modified:** `src/imio/googleauthenticator/tests/test_user_setup.py`
- **Verification:** `bin/test -t test_handleSubmit` green
- **Committed in:** `f61be76` (Task 2 commit)

**2. [Rule 1 - Bug] `ZPublisher.HTTPRequest.get()` caches resolved values in `request.other`, defeating a later scenario's `request.form` overwrite**
- **Found during:** Task 2, scenario 4 (empty token) unexpectedly redirected instead of short-circuiting
- **Issue:** Resetting `self.request.form = {}` between scenarios was not enough: `HTTPRequest.get()` (which z3c.form widgets call during extraction) caches the first value it resolves for a given key into `self.request.other`, so scenario 4's fresh, empty `request.form` still read back scenario 1's stale `u'123456'` token value from that cache. This is a mechanism of the shared test-request object, not a production bug.
- **Fix:** `_build_form()` also clears `self.request.other` alongside `self.request.form` before every scenario.
- **Files modified:** `src/imio/googleauthenticator/tests/test_user_setup.py`
- **Verification:** `bin/test -t test_handleSubmit` green; scenario 4 now genuinely exercises the required-field short circuit (`errors` non-empty, `result is False`, no `Location` header set)
- **Committed in:** `f61be76` (Task 2 commit)

**3. [Rule 1 - Bug] Cross-test secret-leakage hazard (same class as 03-01-SUMMARY.md Deviation #2) hit `TestSetupForm.setUp` too**
- **Found during:** Task 2, first full-suite run (isolated `test_handleSubmit` run was green; the full suite errored)
- **Issue:** `BaseTest._install()` commits inside a real testbrowser call, so a `two_factor_authentication_secret` ciphertext written by an earlier test method under a *different* Fernet key survived into `TestSetupForm`'s fresh key. `form.update()` (via `updateFields()` -> `get_token_description()` -> `get_or_create_secret(overwrite=False)`) then tried to decrypt that stale ciphertext under the new key and raised `ValueError: Ciphertext failed to decrypt`.
- **Fix:** `setUp` now calls `helpers.get_or_create_secret(api.user.get_current(), overwrite=True)` immediately after setting the fresh key, forcing a new secret encrypted under this test's own key before any code path can read the stale one.
- **Files modified:** `src/imio/googleauthenticator/tests/test_user_setup.py`
- **Verification:** `bin/test -t '!robot'` green across three repeated runs (41/41 each time)
- **Committed in:** `f61be76` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (2 own-test-file mechanics -- widget type coercion and request caching -- and 1 recurrence of the cross-test secret-leakage hazard already documented in plan 03-01). No scope creep; no production behaviour changed beyond Task 1's `helpers.py`/`reset_bar_code.py` edits, and `user_setup.py` remains byte-identical to `HEAD~2`.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None for this plan's own commits. Task 2's `<human-check>` -- ROADMAP Phase 3 success criterion 4, a real authenticator app enrolling and logging in end to end -- was **not performed during this execution**. `workflow.human_verify_mode` is `end-of-phase` (confirmed via `gsd-tools query config-get workflow.human_verify_mode` -> `end-of-phase`), so per that mode this `<verify><human-check>` block is deliberately left in the plan for the phase-level verifier to harvest into `03-UAT.md`, rather than executed mid-plan. The steps as written in the plan (export a real key, `bin/instance fg`, scan the QR with a real app, enrol, log out/in, confirm the login round trip) remain to be run by a human at end-of-phase.

## Next Phase Readiness

- All of Phase 3's code-level work is complete and tested: `bin/test -t '!robot'` is green at **41 tests, 0 failures, 0 errors**, stable across three repeated runs.
- **The `industrialisation` repo's Puppet `concat::fragment` for `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` is still open.** Restated here, at the end of the phase's last plan, per the plan's own instruction: Phase 3's code is complete and fully tested without it, but the feature remains **not deployable** until that out-of-repo commit lands. Not one of this roadmap's commits.
- **Both of `STATE.md`'s Phase-3 carry-forwards are now accounted for.** (1) The `ska_secret_key` control-panel `TextLine` field (02-SECURITY.md R-02-01) was closed by an explicit re-deferral in plan 03-01 Task 5 (Plone 4.3's `PasswordWidget` blanks an untouched field on Save, so the swap needs its own tested change, not a drive-by) -- unaffected by this plan. (2) The T-02-09 ASCII-by-construction re-check (02-SECURITY.md R-02-02) was closed by assertion in plan 03-01's `test_ciphertext_is_a_safe_ska_key_component`. Neither is this plan's business; both are noted here so the phase can be marked done with nothing silently dropped.

## Verification Detail (per plan's `<output>` spec)

- **Resolved `z3c.form` version:** `3.2.11`. `SetupForm.handleSubmit` confirmed to be a `z3c.form.button.Handler` instance with a `.func` attribute holding the undecorated function, exactly as the plan's flagged assumption predicted; `SetupForm.handleSubmit.func(form, None)` worked as specified. `form.widgets['token'].name` resolved to `'form.widgets.token'`, also exactly as predicted -- the one-line fallback (`print(widget_name)`) was wired in but never needed to fire.
- **BUG-02 honesty check:** `git diff HEAD~1 -- src/imio/googleauthenticator/browser/forms/user_setup.py` (relative to Task 2's commit `f61be76`) is empty. `git diff --name-only HEAD~1` for that commit lists exactly `CHANGES.rst` and `src/imio/googleauthenticator/tests/test_user_setup.py`.
- **`grep -rn --include=*.py -E "bar_code_reset_token *(==|!=)" src/`:** no output -- zero matches anywhere in `src/`, confirming no bare equality/inequality comparison of that token survives in the package (not just excluded from `tests/`).
- **Task 2's `<human-check>` (ROADMAP Phase 3 success criterion 4):** not performed by this execution -- see "User Setup Required" above. Recorded here as required by the plan's `<output>` spec: this is the one criterion of the five in Phase 3 with no automated assertion, and it needs a physical authenticator app, which an automated agent does not have. It is left for the phase's end-of-phase UAT collection (`workflow.human_verify_mode = end-of-phase`).
- **Puppet dependency restatement:** see "Next Phase Readiness" above -- still open, still out of this roadmap's commits, phase is code-complete but not deployable until it lands.
- **`ska_secret_key`-in-a-form-field carry-forward:** see "Next Phase Readiness" above -- closed by explicit re-deferral in plan 03-01 Task 5, not silently dropped.
- **Additional acceptance-criteria evidence gathered during execution:**
  - `grep -c "validate_bar_code_reset_token" src/imio/googleauthenticator/browser/forms/reset_bar_code.py` -> `3` (import + both call sites).
  - `grep -c "from hmac import compare_digest" src/imio/googleauthenticator/helpers.py` -> `1`; same grep on `reset_bar_code.py` -> `0`.
  - `grep -v '^ *#' src/imio/googleauthenticator/browser/forms/reset_bar_code.py | grep -cE "bar_code_reset_token *(==|!=)"` -> `0`.
  - `grep -c "compare_digest" src/imio/googleauthenticator/helpers.py` -> `4` (>= 2 required); `grep -vE "^ *#" src/imio/googleauthenticator/helpers.py | grep -cE "return compare_digest\("` -> exactly `1`.
  - `parts/instance/bin/interpreter -c "from imio.googleauthenticator.helpers import validate_bar_code_reset_token as v; assert v('abc', u'abc'); assert v(u'abc', 'abc'); assert not v('', ''); assert not v(None, 'abc'); assert not v(u'\xe9', 'abc'); print('ok')"` -> `ok` (`bin/python` has no buildout eggs on `sys.path`, same pre-existing repo-shape fact plan 03-01 recorded; `parts/instance/bin/interpreter` used instead).
  - `grep -c "validate_token = " src/imio/googleauthenticator/tests/test_user_setup.py` -> `7`; `grep -c "finally:" ...` -> `3`; `grep -c "UnboundLocalError" ...` -> `4`.
  - `grep -c "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" CHANGES.rst` -> `1`; `grep -ci "re-enrol\|re-enroll" CHANGES.rst` -> `2`; `grep -c "\[chris-adam\]" CHANGES.rst` increased from `6` to `13` (+7, >= 5 required); `grep -c "1.0.0 (unreleased)" CHANGES.rst` -> `1`; `grep -c "version = '1.0.0.dev0'" setup.py` -> `1`.
  - Zero `import`/`from` statements inside any method body of `test_user_setup.py`; the one pre-existing such statement inside `test_helpers.py` (line 73, `TestIPWhitelisting.test_get_ip_addresses_whitelist_drops_blank_lines`) predates this plan (landed in plan 03-01) and was not introduced here.
  - `bin/code-analysis` is not a gate per `CLAUDE.md`/plan `<verification>`; both commits used `git commit --no-verify`.

---
*Phase: 03-encrypted-seeds-and-local-qr*
*Completed: 2026-07-30*

## Self-Check: PASSED
