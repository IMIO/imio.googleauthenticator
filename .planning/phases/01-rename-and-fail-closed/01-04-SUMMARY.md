---
phase: 01-rename-and-fail-closed
plan: 04
subsystem: auth
tags: [plone, pas-plugin, fail-closed, tdd, security]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Package moved to src/imio/googleauthenticator/, PAS_ID/meta_type/PAS_TITLE left untouched for this plan to own"
  - phase: 01-03
    provides: "README.rst / docs/index.rst rewritten for the new package name (except the PAS_TITLE-quoting line, fenced out for this plan)"
provides:
  - "meta_type and PAS_TITLE renamed to the iMio identity, in an isolated commit; PAS_ID (google_auth) untouched"
  - "_dont_swallow_my_exceptions = True on GoogleAuthenticatorPlugin -- PAS no longer silently swallows a bug on this plugin's authentication path into a password-only fallthrough"
  - "test_plugin_exception_is_not_swallowed (RED then GREEN) and a counterfactual test documenting the pre-fix behaviour"
  - "Two real bugs the fail-closed flag immediately surfaced, both fixed: is_whitelisted_client crashing on an empty REMOTE_ADDR, and a broken user.getProperty('username') debug line"
  - "Phase-wide acceptance grep (src/, setup.py, MANIFEST.in, .coveragerc, cleanup.sh minus RESEARCH false positives) empty -- phase gate closed"
affects: [phase-3-encryption, phase-4-second-factor-integrity, phase-8-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RED/GREEN TDD for the fail-closed test: wrote test_plugin_exception_is_not_swallowed first (observed failing with the correct 'ValueError not raised' message, confirming the request-setup assumption RESEARCH A1), then added the class attribute to make it pass, in separate commits."
    - "Injected the failure through a real collaborator (is_whitelisted_client, module-namespace patch on pas_plugin, restored in finally) rather than monkeypatching authenticateCredentials itself, so the assertion exercises PAS's own except/reraise/continue block in _extractUserIds."

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/pas_plugin.py
    - src/imio/googleauthenticator/setuphandlers.py
    - src/imio/googleauthenticator/www/add_google_authenticator_form.zpt
    - src/imio/googleauthenticator/tests/test_pas_plugin.py
    - src/imio/googleauthenticator/helpers.py
    - README.rst
    - docs/index.rst

key-decisions:
  - "meta_type/PAS_TITLE rename shipped as its own commit (d3317bb), touching only the 5 declared files, so a duplicate-meta_type RuntimeError at layer setup stays legible as 'stale artefact' rather than 'rename bug' -- verified clean by running the layer setup after that commit alone."
  - "Fixed two pre-existing bugs that _dont_swallow_my_exceptions immediately surfaced, both outside the plan's declared file list (helpers.py) or inside the method body but outside the explicitly-protected inner delegation loop (pas_plugin.py:101). Documented as Rule 1/3 deviations below rather than left broken, since the plan's own acceptance criterion (full suite green, repeatable) cannot be met otherwise."
  - "Did not add a None-guard for api.user.get() returning None (AttributeError on a nonexistent username), since no test in this suite exercises that path and CONTEXT.md's fail-closed blast-radius decision explicitly accepts a bug on this path producing a loud failure rather than a silent bypass. Left as a live risk for a future phase to harden defensively if it surfaces."

requirements-completed: [RENAME-10, RENAME-11]

coverage:
  - id: D1
    description: "pas_plugin.py's meta_type and setuphandlers.py's PAS_TITLE renamed to iMio (parenthesised distro name), PAS_ID='google_auth' byte-identical to before; ZMI add-form heading and README.rst/docs/index.rst quoted title updated to match; isolated commit touching only these 5 files"
    requirement: "RENAME-10"
    verification:
      - kind: unit
        ref: "grep checks on all 5 files + git show --name-only HEAD (5 files) after commit d3317bb"
        status: pass
      - kind: integration
        ref: "bin/test -t '!robot' immediately after the meta_type commit -- 13 tests, 0 failures, 0 errors, layer setup succeeds (no duplicate-meta_type RuntimeError)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Phase-wide acceptance grep (old namespace across src/, setup.py, MANIFEST.in, .coveragerc, cleanup.sh, minus RESEARCH Section F false positives) returns empty -- the phase gate this plan owns"
    requirement: "RENAME-10"
    verification:
      - kind: unit
        ref: "git grep -i collective -- src/ setup.py MANIFEST.in .coveragerc cleanup.sh | grep -v false-positives -- empty, verified after commit d3317bb and again at plan completion"
        status: pass
    human_judgment: false
  - id: D3
    description: "_dont_swallow_my_exceptions = True added to GoogleAuthenticatorPlugin with a comment naming the fallthrough it prevents and its per-plugin scoping; test_plugin_exception_is_not_swallowed injects a ValueError through is_whitelisted_client (a real collaborator, not a monkeypatch of the method under test) and asserts it escapes acl_users._extractUserIds instead of falling through to source_users"
    requirement: "RENAME-11"
    verification:
      - kind: integration
        ref: "tests/test_pas_plugin.py#test_plugin_exception_is_not_swallowed -- observed RED ('ValueError not raised') in commit c558136 before the flag existed, GREEN in commit 60f377f after"
        status: pass
      - kind: integration
        ref: "tests/test_pas_plugin.py#test_plugin_exception_is_swallowed_without_the_flag -- counterfactual, documents the pre-fix swallow-and-fall-through behaviour"
        status: pass
    human_judgment: false
  - id: D4
    description: "Full suite green and repeatable after the fail-closed flag landed: 15 tests, 0 failures, 0 errors, run twice in a row with identical results, proving the collaborator patch and the counterfactual's attribute deletion both restore state correctly"
    verification:
      - kind: integration
        ref: "bin/test -t '!robot' run twice consecutively post-commit 60f377f"
        status: pass
    human_judgment: false
  - id: D5
    description: "bin/instance starts cleanly on this tree (RESEARCH assumption A5's untested baseline) -- 'Zope Ready to handle requests' with no startup error, established so a future unrelated instance-startup problem is not mistaken for a rename/fail-closed defect. The full manual ZMI walkthrough (create a site through the browser UI, confirm acl_users/plugins lists google_auth under Authentication) was NOT performed interactively -- no human or browser-automation tool was available to this executor. The equivalent fact is proven behaviourally by the automated suite instead (D3/D6)."
    verification:
      - kind: manual_procedural
        ref: "timeout 25 bin/instance fg -- INFO Zope Ready to handle requests, clean shutdown on SIGTERM, no traceback"
        status: pass
    human_judgment: true
    rationale: "The plan's <human-check> asks for an interactive ZMI walkthrough after starting bin/instance fg, which needs a human at a browser. This executor confirmed the automatable half (clean startup) and substituted the automated test_plugin_is_registered_for_authentication assertion for the ZMI-listing check, but a human should still do the literal walkthrough once before relying on this in production."
  - id: D6
    description: "test_plugin_is_registered_for_authentication (carried over from plan 01-01, still passing) confirms google_auth is listed under IAuthenticationPlugin after this plan's meta_type rename -- the behavioural proxy for the ZMI check in D5"
    verification:
      - kind: integration
        ref: "tests/test_pas_plugin.py#test_plugin_is_registered_for_authentication"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-07-29
status: complete
---

# Phase 1 Plan 4: PAS identity rename and fail-closed exception handling Summary

**Renamed the PAS plugin's meta_type/title to iMio in an isolated commit (plugin id untouched), added `_dont_swallow_my_exceptions = True` proven by a RED-then-GREEN test that injects a failure through a real collaborator, and fixed two pre-existing bugs the flag immediately surfaced -- a crash on empty REMOTE_ADDR and a broken debug-log property lookup -- both of which were silently masking the entire 2FA gate before this plan.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-29T09:40Z (approx, first file reads)
- **Completed:** 2026-07-29T09:55Z
- **Tasks:** 2 completed (task 2 split RED/GREEN per its `tdd="true"` attribute)
- **Files modified:** 7 (5 in task 1's isolated commit, 2 more in task 2 plus the RED-test-only file)

## Accomplishments
- `pas_plugin.py`'s `meta_type` renamed `'iMio Google Authenticator PAS'`; `setuphandlers.py`'s `PAS_TITLE` renamed to `'Google Authenticator plugin (imio.googleauthenticator)'`; `PAS_ID = 'google_auth'` left byte-identical. Shipped as a single isolated commit touching only these two files plus the ZMI add-form heading (`www/add_google_authenticator_form.zpt`) and the two docs quoting the title (`README.rst`, `docs/index.rst`).
- Phase-wide acceptance grep run immediately after that commit and again at the end of this plan: `git grep -i collective -- src/ setup.py MANIFEST.in .coveragerc cleanup.sh` (minus RESEARCH Section F's named false positives) returns nothing -- the phase gate plans 01-01/01-03 deliberately deferred to this plan.
- `_dont_swallow_my_exceptions = True` added to `GoogleAuthenticatorPlugin`, with a comment recording the three facts RESEARCH Pitfall 7 names: the swallowable-exception tuple it defeats, the per-plugin scoping (later plugins' post-credentials-wipe `KeyError` still gets swallowed, which the veto depends on), and that the plugin's own inner delegation loop (lines calling `reraise()` on *other* plugins) is deliberately left untouched for Phase 4.
- `test_plugin_exception_is_not_swallowed` written first and observed failing (`AssertionError: ValueError not raised`) before the flag existed -- confirming RESEARCH's one open assumption (A1: the request-setup via `request.form['__ac_name']`/`__ac_password'` does reach `_extractUserIds`) held on the first try, no iteration needed. Then made to pass by adding the flag. A companion counterfactual test (`test_plugin_exception_is_swallowed_without_the_flag`) documents the exact pre-fix behaviour and passed immediately (proving it was measuring the right thing).
- Turning the flag on surfaced two real, previously-silent bugs on the authentication path (both fixed, see Deviations): `helpers.extract_ip_address_from_request` crashing on an empty `REMOTE_ADDR`, and `pas_plugin`'s debug log calling a non-existent `getProperty('username')`. Both had been happening on *every single request* through this plugin and were silently absorbed by PAS's swallow -- meaning the entire 2FA gate had likely never actually engaged in any deployment before this plan, independent of the rename.
- Full suite green at 15 tests (13 carried forward + 2 new), 0 failures, 0 errors, run twice consecutively with identical results.

## Task Commits

Each task was committed atomically (task 2 split RED/GREEN per its `tdd="true"` attribute):

1. **Task 1: Rename the plugin meta_type and title -- isolated commit, plugin id untouched** - `d3317bb` (feat)
2. **Task 2, RED: failing test for fail-closed exception handling** - `c558136` (test)
3. **Task 2, GREEN: the flag, plus the two bugs it surfaced** - `60f377f` (feat)

**Plan metadata:** pending (this commit, `docs(01-04): complete pas-identity-and-fail-closed plan`)

## Files Created/Modified
- `src/imio/googleauthenticator/pas_plugin.py` - `meta_type` renamed; `_dont_swallow_my_exceptions = True` with scoping comment; `getProperty('username')` -> `getUserName()` bugfix
- `src/imio/googleauthenticator/setuphandlers.py` - `PAS_TITLE` renamed; `PAS_ID` untouched
- `src/imio/googleauthenticator/www/add_google_authenticator_form.zpt` - ZMI add-form heading renamed
- `src/imio/googleauthenticator/helpers.py` - `extract_ip_address_from_request` returns `None` on empty `REMOTE_ADDR` instead of raising; `is_whitelisted_client` treats `None` as not-whitelisted
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` - `test_plugin_exception_is_not_swallowed`, `test_plugin_exception_is_swallowed_without_the_flag`
- `README.rst` / `docs/index.rst` - quoted plugin title updated

## Decisions Made
- Kept task 1's meta_type/title rename in a single isolated commit exactly as the plan required, verifying the layer setup (no duplicate-`meta_type` error) immediately after that commit and before starting task 2.
- Followed the plan's TDD split literally for task 2 despite the flag itself being a one-line addition: wrote the test against the *absence* of the flag first, observed the specific failure message, then added the flag -- this is what caught and proved RESEARCH assumption A1 correct on the first attempt.
- Fixed two crash bugs the flag surfaced (see Deviations) rather than leaving the suite red, since the plan's own acceptance criteria require a green, repeatable suite. Left the `api.user.get()` returning `None` case (nonexistent username -> `AttributeError`) unguarded, since it doesn't currently block anything and CONTEXT.md's fail-closed blast-radius decision explicitly accepts a loud failure over a silent bypass on this path.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, blocking] `is_whitelisted_client` crashed on empty `REMOTE_ADDR`**
- **Found during:** Task 2, GREEN phase -- immediately after adding the flag, the entire suite went from 15/0/0 to 0 failures/13 errors, every one of them a 500 during the test browser's login.
- **Issue:** `helpers.extract_ip_address_from_request` calls `ipaddress.ip_address(ip)` unconditionally; when `REMOTE_ADDR` is empty (as it is under `plone.testing`'s test browser, and potentially in a misconfigured front end), this raises `ValueError`. Because `is_whitelisted_client()` is the *first statement* of `authenticateCredentials`, this fired on literally every single authentication attempt PAS made through this plugin -- previously silently swallowed (falling through to `source_users`, i.e. this was silently disabling the whole 2FA gate whenever it happened), now a loud 500 on every request.
- **Fix:** `extract_ip_address_from_request` returns `None` when `ip` is falsy instead of calling `ipaddress.ip_address('')`; `is_whitelisted_client` treats a `None` IP as "not whitelisted" (fail closed on the whitelist itself, rather than crashing).
- **Files modified:** `src/imio/googleauthenticator/helpers.py`
- **Verification:** Full suite went from 13 errors to 2 errors after this fix alone (isolated by reverting the pas_plugin.py debug-line fix and re-running); `bin/test -t '!robot'` green after both fixes.
- **Committed in:** `60f377f`

**2. [Rule 1 - Bug, blocking] Debug log line called a non-existent memberdata property**
- **Found during:** Task 2, GREEN phase, same investigation as above -- after fixing the IP bug, 2 errors remained, both `ValueError: The property username does not exist`.
- **Issue:** `pas_plugin.py`'s existing debug line `logger.debug("Found user: {0}".format(user.getProperty('username')))` calls `getProperty('username')`, which is not a declared MemberData property in Plone's schema (or this package's `IEnhancedUserDataSchema`) -- it always raised `ValueError` on every real login (format-string arguments evaluate eagerly, so this ran unconditionally, not just when debug logging was enabled). Previously silently swallowed by PAS; now surfaced.
- **Fix:** Switched to `user.getUserName()`, the correct existing API returning the same information. This is a like-for-like bugfix, not new logging -- the username-in-debug-log surface the plan's prohibition names (owned by Phase 4) is unchanged in scope, just no longer crashing.
- **Files modified:** `src/imio/googleauthenticator/pas_plugin.py`
- **Verification:** `bin/test -t '!robot'` -- 15 tests, 0 failures, 0 errors, run twice consecutively with identical results.
- **Committed in:** `60f377f`

---

**Total deviations:** 2 auto-fixed (both Rule 1/blocking bugs the fail-closed flag itself surfaced)
**Impact on plan:** Both fixes were necessary for the plan's own acceptance criteria (full green, repeatable suite) to be achievable at all -- without them, `_dont_swallow_my_exceptions = True` would 500 every single request in this codebase, test or production. Neither touches the inner delegation loop (`pas_plugin.py`'s `for plugid, authplugin in auth_plugins:` block) the plan explicitly protects; both are pre-existing, previously-silent bugs unrelated to the rename or to Phase 4's boundary rework. No scope creep beyond what was required to make the flag safe to ship.

## Issues Encountered

**RESEARCH assumption A1 held on first try.** The request-setup for `test_plugin_exception_is_not_swallowed` (`request.form['__ac_name']`/`'__ac_password'` on `self.layer['request']`, then calling `_extractUserIds` directly) reached the plugin's `authenticateCredentials` exactly as RESEARCH predicted -- the RED-phase failure was the expected "ValueError not raised" (i.e. the exception was reached and swallowed), not a setup failure, so no iteration was needed.

**Fail-closed blast radius materialized exactly as CONTEXT.md anticipated -- but in the test suite, not just as a documented production risk.** CONTEXT.md's "Claude's Discretion" section predicted that turning on `_dont_swallow_my_exceptions` would convert every latent bug on the authentication path into a hard failure and explicitly accepted that trade. What was not anticipated (and RESEARCH did not flag) was that the *entire test suite's login helper* (`tests/base.py`'s `_install()`/`_login_browser()`) would hit two such bugs on every single call. Both are documented above as required auto-fixes.

## User Setup Required

None - no external service configuration required.

**Recommended follow-up (not blocking):** a human should run through the plan's original `<human-check>` once -- `bin/instance fg`, create a fresh Plone site through the browser, install the add-on, and confirm `acl_users/plugins` lists `google_auth` under Authentication in the ZMI. This executor confirmed `bin/instance` starts cleanly (`INFO Zope Ready to handle requests`, no traceback) but could not drive a browser through the ZMI walkthrough itself; the automated suite's `test_plugin_is_registered_for_authentication` proves the equivalent fact at the object-model level.

## Next Phase Readiness

- Phase 1 (rename-and-fail-closed) is complete: all 4 plans landed, the phase-wide acceptance grep is empty, and the full suite is green at 15 tests.
- Phase 4 (second-factor integrity) can proceed: the inner delegation loop in `authenticateCredentials` is exactly as it was before this phase (untouched by both this plan's flag and its bugfixes), ready for the boundary rework the roadmap assigns there.
- Phase 3 (encryption) inherits a plugin that now fails loudly rather than silently on the authentication path -- relevant since Phase 3 adds its own fail-closed-on-missing-key behaviour on the same code path.
- Worth flagging for whoever picks up Phase 4 or later: the two bugs fixed here (`is_whitelisted_client` crashing on empty `REMOTE_ADDR`, and the `getProperty('username')` typo) had almost certainly been silently disabling the entire 2FA gate on every request in any deployment before this phase, independent of the rename -- not just a theoretical fail-closed blast radius, a real pre-existing correctness gap this plan's own change exposed and closed.
- No blockers. `bin/test -t '!robot'` is green at 15 tests, 0 failures, 0 errors, verified repeatable.

---
*Phase: 01-rename-and-fail-closed*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `src/imio/googleauthenticator/pas_plugin.py`
- FOUND: `src/imio/googleauthenticator/setuphandlers.py`
- FOUND: `src/imio/googleauthenticator/www/add_google_authenticator_form.zpt`
- FOUND: `src/imio/googleauthenticator/helpers.py`
- FOUND: `src/imio/googleauthenticator/tests/test_pas_plugin.py`
- FOUND: `README.rst`, `docs/index.rst`
- FOUND commit: `d3317bb` (task 1: meta_type/title rename)
- FOUND commit: `c558136` (task 2 RED: failing fail-closed test)
- FOUND commit: `60f377f` (task 2 GREEN: flag + two bugfixes)
