---
phase: 01-rename-and-fail-closed
verified: 2026-07-29T08:13:52Z
status: gaps_found
score: 5/6 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Ordinary, non-malicious inputs reaching the PAS plugin (unknown username, malformed X-Forwarded-For, trailing blank line in the IP whitelist) do not crash login with an unhandled 500 -- the whitelist/lookup logic this phase touched is fail-closed, not fail-crashed, exactly as its own inline comment claims."
    status: failed
    reason: >
      _dont_swallow_my_exceptions = True (commit 60f377f) makes every unhandled exception
      inside authenticateCredentials propagate as a 500 instead of being silently swallowed
      by PAS. The commit audited and fixed exactly the two call sites its own new tests
      exercise, but left three other paths in the same method/call graph unguarded. All
      three are confirmed still present on disk (not hypothetical, not fixed by a later
      commit in this phase):
        - pas_plugin.py:99-101 -- api.user.get(username=login) returns None for any
          username that does not match an account; the very next line calls
          user.getUserName() unconditionally, raising AttributeError. This is the single
          most common failed-login shape (a typo) and now 500s instead of showing "Login
          failed".
        - helpers.py extract_ip_address_from_request (~line 465) -- guards only the empty
          IP case ("if not ip: return None"); a non-empty malformed X-Forwarded-For value
          still reaches ipaddress.ip_address(ip) unguarded and raises ValueError. Client-
          controllable via a proxy header.
        - helpers.py get_ip_addresses_whitelist / get_ip_ranges (~lines 472-508) -- splits
          the whitelist Text field on '\n' without dropping empty entries; a trailing blank
          line (an entirely ordinary textarea edit) produces '' in the list, and
          ipaddress.ip_network('') raises ValueError, uncaught, from the first statement of
          authenticateCredentials -- crashing login for every user on the site the moment an
          admin saves a whitelist with a trailing newline.
      These are the same three findings independently confirmed in 01-REVIEW.md (CR-01,
      CR-02, CR-03) and verified directly against the current source in this pass -- none
      has been fixed since the review ran. The phase's own code comment at
      helpers.py (added in 60f377f) states the intended outcome in these exact words: "keeps
      the whitelist fail-closed instead of fail-crashed" -- the implementation delivers that
      only for the empty-string case, not for the two remaining paths, one of which (CR-03)
      is a site-wide login outage triggered by routine admin configuration, not an attack.
    artifacts:
      - path: "src/imio/googleauthenticator/pas_plugin.py"
        issue: "Lines 99-101: api.user.get() result used without a None check (CR-01)"
      - path: "src/imio/googleauthenticator/helpers.py"
        issue: "extract_ip_address_from_request: non-empty malformed IP unguarded (CR-02); get_ip_addresses_whitelist/get_ip_ranges: empty whitelist entries unguarded (CR-03)"
    missing:
      - "pas_plugin.py: return None when api.user.get(username=login) is None, before calling getUserName()"
      - "helpers.py: wrap ipaddress.ip_address(ip) in try/except ValueError, treating a parse failure as 'no client IP' (same as the empty-IP branch)"
      - "helpers.py: filter empty/blank entries out of the whitelist list before calling ipaddress.ip_network(), and/or make get_ip_ranges skip an individual bad entry rather than raising"
      - "A regression test per fixed path (unknown username, malformed X-Forwarded-For, trailing blank whitelist line) proving each now returns None/False instead of raising, to close the same class of gap CR-01/02/03 exploited (the existing suite only exercises TEST_USER_NAME and well-formed inputs, which is why this shipped invisibly)"
---

# Phase 01: Rename and Fail-Closed Verification Report

**Phase Goal:** The package is `imio.googleauthenticator` everywhere -- on disk, in the egg, in
the i18n domain, in the GenericSetup profile and its marker file -- and any exception inside the
PAS plugin becomes a 500 rather than a silent fallthrough to password-only authentication.

**Verified:** 2026-07-29T08:13:52Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Fresh clone: `bin/instance` buildout installs the add-on, `collective.googleauthenticator` importable from nowhere, no orphan `.pyc`/`.egg-info` under the old namespace | VERIFIED | `find . -iname "*collective.googleauthenticator*"` and `find . -path "*collective/googleauthenticator*"` both empty (excluding `.git`); the only `collective/*.pyc` hits are `parts/omelette/collective/{__init__,z3cform/__init__}.pyc`, a git-ignored buildout omelette symlink tree for the unrelated third-party `collective.z3cform` egg, not this package's old namespace. `src/imio.googleauthenticator.egg-info` present and correctly named; `src/imio/__init__.py` declares the `imio` namespace |
| 2 | A test asserts `google_auth` is registered for `IAuthenticationPlugin` | VERIFIED | `test_plugin_is_registered_for_authentication` in `tests/test_pas_plugin.py:39-48` asserts `PAS_ID` (`google_auth`) in `listPlugins(IAuthenticationPlugin)`; `bin/test -t '!robot'` run in this pass: 15 tests, 0 failures, 0 errors |
| 3 | `python setup.py sdist` produces an archive with `profiles/`, `locales/`, templates | VERIFIED | Built `imio.googleauthenticator-1.0.0.dev0.tar.gz` in this pass; `tar tzf` shows 17 `profiles/` entries (incl. `default/` and `uninstall/`), 12 `locales/` entries (pot + 3 language `.po`), and `www/add_google_authenticator_form.zpt` |
| 4 | Dutch translation still renders; catalogues `git mv`-ed to new domain filenames, stale `.mo` deleted | VERIFIED | `locales/{en,fr,nl}/LC_MESSAGES/imio.googleauthenticator.{po,mo}` all present under the new domain name, no stale `collective.googleauthenticator.*` catalogue files anywhere on disk; `test_control_panel_is_translated_nl` and `test_corrected_msgid_renders_in_english` both pass in the 15-test run |
| 5 (literal) | `_dont_swallow_my_exceptions = True` set; a test asserts a deliberately raised plugin exception yields a 500 rather than authenticating via `source_users` | VERIFIED | `pas_plugin.py:71` sets the flag; `test_plugin_exception_is_not_swallowed` injects a `ValueError` via `is_whitelisted_client` and asserts `_extractUserIds` raises; `test_plugin_exception_is_swallowed_without_the_flag` is the counterfactual proving the flag is what changes the behavior. Both pass |
| 5 (intent) | Ordinary, non-malicious inputs do not crash login with the same mechanism -- fail-closed, not fail-crashed, as the code's own comment states | ✗ FAILED | Three unguarded exception paths confirmed live in current source (see Gaps) -- an unknown username, a malformed `X-Forwarded-For` value, and a trailing blank line in the admin IP whitelist textarea each 500 the login flow via the exact same `_dont_swallow_my_exceptions` mechanism this phase introduced |

**Score:** 5/6 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/__init__.py` | Namespace package declaration | VERIFIED | `__import__('pkg_resources').declare_namespace(__name__)` |
| `setup.py` | `namespace_packages = ['imio']` | VERIFIED | Line 52 |
| `src/imio/googleauthenticator/profiles/default/imio.googleauthenticator.marker.txt` | Renamed marker file matching `setupVarious`'s check | VERIFIED | File present; `setuphandlers.py:53` reads `imio.googleauthenticator.marker.txt` |
| `MANIFEST.in` | 8 `src/imio/googleauthenticator/...` paths | VERIFIED | `recursive-include src/imio/googleauthenticator/{locales,profiles} *` etc.; sdist build proves inclusion |
| `CHANGES.rst` | Records rename + non-migration of existing DBs | VERIFIED | 1.0.0 (unreleased) section documents both explicitly |
| `src/imio/googleauthenticator/pas_plugin.py` | `_dont_swallow_my_exceptions = True`, renamed `meta_type`/`PAS_TITLE`, unchanged `PAS_ID` | VERIFIED | Line 59 `meta_type = 'iMio Google Authenticator PAS'`, line 71 flag set, `PAS_ID` still `google_auth` (checked in `setuphandlers.py`) |
| `src/imio/googleauthenticator/upgrades/` | Deleted | VERIFIED | Directory does not exist (`ls` exit 2 / not found) |
| `.coveragerc`, `base.cfg` | Updated `package-name`/`directory`/`include` | VERIFIED | Both reference `imio.googleauthenticator` / `src/imio/googleauthenticator` |
| `cleanup.sh` | Purges `src/imio.googleauthenticator.egg-info` | VERIFIED | Confirmed on disk |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `testing.py` | Zope product registration | `z2.installProduct(app, 'imio.googleauthenticator')` | WIRED | Confirmed in file, and the full integration-test layer boots and runs 15 tests successfully against it |
| `setuphandlers.py` | GenericSetup marker | `context.readDataFile('imio.googleauthenticator.marker.txt')` | WIRED | Matches the actual marker filename on disk; behaviorally proven by `test_plugin_is_registered_for_authentication` (a mismatch would make it fail, per the test's own docstring) |
| `pas_plugin.py:authenticateCredentials` | `helpers.is_whitelisted_client` | Direct call, first statement | WIRED, but see gap | The call and its downstream helpers are reachable, wired, and exercised by the test suite -- the gap is in what happens when the *content* of that call raises on ordinary input, not in the wiring itself |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RENAME-01 | 01-01 | Package on disk/setup.py/namespace | SATISFIED | `src/imio/`, `setup.py:52`, `src/imio/__init__.py` |
| RENAME-02 | 01-01 | All dotted refs updated | SATISFIED | No `collective` string in reviewed source/config files (grep) |
| RENAME-03 | 01-02 | Dutch translation survives rename | SATISFIED | `locales/nl/**` under new domain filenames, tests pass |
| RENAME-04 | 01-01 | Marker file renamed | SATISFIED | File + behavioral test |
| RENAME-05 | 01-01 | `++resource++` prefixes match | SATISFIED | `test_resources_are_registered` passes |
| RENAME-06 | 01-03 | `MANIFEST.in` 8 paths, sdist proof | SATISFIED | sdist built and inspected in this pass |
| RENAME-07 | 01-01/02/03 | Build/tooling config updated | SATISFIED | `.coveragerc`, `base.cfg`, `cleanup.sh`, `testing.py` all confirmed |
| RENAME-08 | 01-01 | Stale `.pyc`/`.egg-info` purged | SATISFIED | No old-namespace artifacts found on disk |
| RENAME-09 | 01-01 | `upgrades/` deleted | SATISFIED | Directory absent |
| RENAME-10 | 01-04 | `meta_type`/`PAS_TITLE` renamed, `PAS_ID` unchanged | SATISFIED | Confirmed in `pas_plugin.py` |
| RENAME-11 | 01-04 | `_dont_swallow_my_exceptions = True` | SATISFIED (flag) / BLOCKED (fail-closed intent) | Flag set and tested; but 3 confirmed unguarded exception paths in the exact call graph this flag now propagates from (see Gaps) contradict the stated fail-closed design intent |
| RENAME-12 | 01-01 | Test asserts plugin registered | SATISFIED | `test_plugin_is_registered_for_authentication` passes |
| DOC-04 | 01-03 | `CHANGES.txt`/`.rst` records rename | SATISFIED | Confirmed above |

No orphaned requirements: all 13 IDs (RENAME-01..12, DOC-04) appear in the `requirements:` frontmatter of the four phase-01 plans, matching REQUIREMENTS.md's phase-1 allocation exactly.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/imio/googleauthenticator/pas_plugin.py` | 99-101 | Unchecked `None` from `api.user.get()` used unconditionally | Blocker | Any unknown/mistyped username 500s login (CR-01) |
| `src/imio/googleauthenticator/helpers.py` | ~460-467 | `ipaddress.ip_address(ip)` unguarded for non-empty malformed input | Blocker | Malformed `X-Forwarded-For` 500s login (CR-02) |
| `src/imio/googleauthenticator/helpers.py` | ~486-508 | Empty whitelist entries not filtered before `ipaddress.ip_network()` | Blocker | Trailing blank line in admin whitelist setting 500s login site-wide for every user (CR-03) |
| `src/imio/googleauthenticator/pas_plugin.py` | 94 | `credentials['login']` direct key access (no `.get()`) | Warning | Same exception class as CR-01 if a future/reconfigured extractor omits `login` (WR-01, not currently triggerable) |
| `src/imio/googleauthenticator/helpers.py` | 444 | `PRIVATE_IPS_PREFIX` treats all of `172.0.0.0/8` as private | Warning | Pre-existing, adjacent to the hardened code, not introduced by this phase (WR-02) |
| `src/imio/googleauthenticator/helpers.py` | 310, 338 | Pre-existing `:FIXME:` docstring notes (2014/2015, upstream) | Info | Not touched by this phase's diff (confirmed via `git blame`); tracked separately as BUG-06, allocated to Phase 7 in REQUIREMENTS.md -- not a phase-01 debt marker |

None of the three Blocker anti-patterns are hypothetical or attacker-only: CR-01 fires on the single most common failed-login shape (a typo), and CR-03 fires on a routine admin textarea edit and crashes login for every user on the site.

### Human Verification Required

None. All findings above are confirmed directly against source and reproducible by inspection/test; no visual, real-time, or external-service behavior is in question for this phase.

### Gaps Summary

The rename itself (RENAME-01 through RENAME-10, RENAME-12, DOC-04) is complete, clean, and
verified directly against the codebase: no stray `collective` references, no orphaned artifacts,
sdist proves packaging, Dutch translation round-trips, and the plugin-registration test passes.

RENAME-11 is where the phase falls short of its own stated goal. The success criterion as written
("`_dont_swallow_my_exceptions = True` is set... and a test asserts a deliberately raised plugin
exception yields a 500") is met literally -- the flag is set, and the one deliberately-injected
exception the phase's own test suite raises does propagate to a 500 as intended.

But the phase goal's framing -- "any exception inside the PAS plugin becomes a 500 rather than a
silent fallthrough to password-only authentication" -- and the implementation's own inline comment
("keeps the whitelist fail-closed instead of fail-crashed") describe a broader intent: turning on
`_dont_swallow_my_exceptions` should not, by itself, convert *ordinary* operational conditions into
site-wide outages. Three such conditions were audited by the independent code review (01-REVIEW.md)
and independently reconfirmed against the live source in this verification pass:

- an unknown/mistyped username (CR-01) -- the most common failed-login case there is,
- a malformed `X-Forwarded-For` value (CR-02) -- reachable via a proxy header,
- a trailing blank line in the admin IP whitelist setting (CR-03) -- an ordinary textarea edit that
  crashes login for every user on the site, site-wide, until an admin edits the setting back.

None of these are attacks; none require unusual configuration. They are the direct, self-inflicted
consequence of the exact commit (`60f377f`) that this phase's own success criterion #5 asks for,
and they were not caught by that commit's own test suite because every existing test uses a valid
username and well-formed inputs. This is not "goal achieved with follow-up work deferred to a later
phase" -- REQUIREMENTS.md maps no later phase to fixing these three paths (they are not BUG-01
through BUG-06's Phase 2/3/7 items; those cover unrelated bugs), and the phase's own text frames
"fail-closed, not fail-crashed" as this phase's job. Treating it as done risks shipping a change
that trades a low-severity latent 2FA-bypass-on-crash for a high-severity, routinely-triggerable
site-wide login outage -- worse than the problem it was meant to fix.

**Recommended fix (small, scoped, matches 01-REVIEW.md's suggested patches):**
1. `pas_plugin.py`: return `None` immediately when `api.user.get(username=login)` is `None`.
2. `helpers.py` `extract_ip_address_from_request`: wrap `ipaddress.ip_address(ip)` in
   `try/except ValueError`, treating a parse failure like the existing empty-IP branch.
3. `helpers.py` `get_ip_addresses_whitelist`/`get_ip_ranges`: filter blank entries before building
   ranges (and/or make `get_ip_ranges` skip an individual invalid entry rather than raising).
4. One regression test per path, since the existing suite's blind spot (valid username, well-formed
   inputs only) is exactly why this shipped unnoticed.

---

_Verified: 2026-07-29T08:13:52Z_
_Verifier: Claude (gsd-verifier)_
