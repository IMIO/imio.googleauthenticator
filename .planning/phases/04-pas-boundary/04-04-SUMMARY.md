---
phase: 04-pas-boundary
plan: 04
subsystem: docs
tags: [readme, changelog, restructuredtext, plone4, python2, docs-as-code]

# Dependency graph
requires:
  - phase: 04-01
    provides: "the decide-only authenticateCredentials / IPubBeforeCommit + IChallengePlugin redirect this plan's changelog and README describe"
  - phase: 04-02
    provides: "the settled credentials_basic_auth 'keep active' decision (dated 2026-07-31, three repositories, explicit non-exhaustive caveat) that DOC-02 documents verbatim, and movePluginsTop as the mechanism the reconciled 'ZMI -> acl_users' section now describes"
  - phase: 04-03
    provides: "the full veto surface (form POST, Basic Auth, both at once, empty, exception path) and the empirical finding that Basic Auth loops forever against a 2FA-enabled account -- context for DOC-02's protocol-consequence paragraph"
provides:
  - "README.rst section 'What two-step verification does not cover' (DOC-01): the Zope-root/emergency-user boundary, its mechanism, and the deployment-side consequence"
  - "README.rst section 'HTTP Basic Auth, WebDAV, FTP and XML-RPC' (DOC-02): the unconditional protocol consequence, the settled credentials_basic_auth decision with its evidence and gap, the service-account + IP-whitelist alternative, and the pre-deployment check"
  - "README.rst 'ZMI -> acl_users' section reconciled to read as verification + recovery (movePluginsTop is now profile-authoritative), not a manual install instruction"
  - "tests/test_generic.py::test_readme_documents_zope_root_limitation, test_readme_documents_basic_auth_consequence -- CI assertions on load-bearing identifiers, each proven load-bearing by a delete-the-section mutation check"
  - "CHANGES.rst 1.0.0 (unreleased) entries for the phase as it actually shipped"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level _read_readme() helper in test_generic.py, backing the two new doc tests without adding new method-body imports (skill rule R6); the pre-existing DOC-03 test's own method-body imports are left untouched, per the plan's explicit instruction not to mix an unrelated refactor into this diff"
    - "Documentation requirements get a CI assertion on load-bearing identifiers (Control_Panel, acl_users, inituser, credentials_basic_auth, WebDAV, XML-RPC, ip_addresses_whitelist, enable_two_factor_authentication), never on prose, so rewording a paragraph stays free and silently dropping the fact it carries does not -- the same pattern DOC-03 (phase 3) established, now applied to two more requirements"

key-files:
  created: []
  modified:
    - README.rst
    - src/imio/googleauthenticator/tests/test_generic.py
    - CHANGES.rst

key-decisions:
  - "DOC-02's test asserts the branch that was actually taken (credentials_basic_auth kept ACTIVE) via the identifier 'index 0' -- the phrase the README uses for what protects that path under the 'keep' branch. If MFA-03's decision is ever reversed to 'deactivate', this assertion (and the README paragraph it checks) must be updated together; the test's docstring says so explicitly."
  - "The two new README sections are placed between the existing 'Notes' section and 'Implementation details', per the plan's placement instruction: operational scope an operator should hit before the internals, not folded into 'Notes' or 'Implementation details' themselves."
  - "'ZMI -> acl_users' rewritten as verification + recovery: same ordered plugin list and 'critical!' emphasis kept (an operator who finds the order wrong still needs it), one sentence added on why it's critical (the credentials wipe only blinds authenticators listed after google_auth), and the recovery path is now 're-apply the imio.googleauthenticator:default profile', matching what 04-02 actually made authoritative (movePluginsTop, re-asserted on every profile application) rather than telling an operator to hand-edit the list."
  - "docs/index.rst was not touched, per phase 3's precedent that it is a stale pre-rename duplicate never kept in sync; verified via git diff --name-only showing no docs/index.rst entry in either task's commit."

patterns-established:
  - "A documentation section is proven load-bearing, not merely present, by a recorded delete-the-section-then-confirm-red mutation check performed once during execution and restored to a byte-identical file afterward (diff -q confirmed) -- the same standard phase 3's DOC-03 test set, now demonstrated rather than only asserted for two more requirements."

requirements-completed: [DOC-01, DOC-02]

coverage:
  - id: D1
    description: "README.rst states the Zope-root/inituser boundary, names the mechanism (this plugin's password pre-check delegates to the site's own IAuthenticationPlugins, none of which resolve a root account), names PAS's own emergency-user carve-out with its source location, and states the deployment-side consequence (restrict /Control_Panel and the root ZMI, or ship no root password) -- explicitly out of scope for this package"
    requirement: "DOC-01"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_generic.py#test_readme_documents_zope_root_limitation"
        status: pass
    human_judgment: false
  - id: D2
    description: "README.rst states the human/protocol-shaped consequence of 2FA over Basic Auth/WebDAV/FTP/XML-RPC unconditionally, records the settled credentials_basic_auth 'keep active' decision (dated, with its three-repository evidence and explicit non-exhaustive caveat), names the real service-account + IP-whitelist alternative, and states the pre-deployment operator check"
    requirement: "DOC-02"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_generic.py#test_readme_documents_basic_auth_consequence"
        status: pass
    human_judgment: false
  - id: D3
    description: "Both new tests are proven load-bearing, not merely passing: deleting the DOC-01 section (or the DOC-02 section) from README.rst makes the corresponding test go red; the file was restored to a byte-identical state afterward (diff -q confirmed against a pre-edit copy)"
    verification:
      - kind: manual_procedural
        ref: "mutation check run during execution -- see 'Mutation Checks' section below for both transcripts"
        status: pass
    human_judgment: false
  - id: D4
    description: "'ZMI -> acl_users' no longer instructs an operator to hand-order the plugin list; it reads as a verification step plus a profile-reapply recovery, consistent with 04-02's movePluginsTop mechanism"
    requirement: null
    verification: []
    human_judgment: true
    rationale: "Whether the rewritten prose 'reads as verification and recovery, not a manual install step' to an actual operator is a qualitative judgment about tone and clarity that no identifier-presence assertion can settle -- the CI tests above cover the facts the section must retain, not how it reads."
  - id: D5
    description: "CHANGES.rst's 1.0.0 (unreleased) section gained entries for phase 4 as it actually shipped (response-body-leak fix, IPubBeforeCommit/IChallengePlugin redirect split, movePluginsTop re-assertion, credentials wipe before delegation, the credentials_basic_auth decision, and the new README sections), sourced from 04-01/04-02/04-03's summaries rather than their plans, with no released version section touched"
    requirement: null
    verification:
      - kind: other
        ref: "git diff CHANGES.rst shows additions only, above the 0.3.0 (unreleased) heading; full suite green after the edit"
        status: pass
    human_judgment: false

# Metrics
duration: ~50min
completed: 2026-07-31
status: complete
---

# Phase 04 Plan 04: DOC-01/DOC-02 README Sections + Changelog Summary

**Two new README.rst sections (Zope-root/emergency-user boundary; Basic Auth/WebDAV/FTP/XML-RPC consequence with the settled `credentials_basic_auth` decision), the "ZMI -> acl_users" section reconciled to read as verification-and-recovery, two CI-enforced fact-presence tests each proven load-bearing by a delete-the-section mutation check, and the phase 4 changelog.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-07-31 (session start, continuing from 04-03)
- **Completed:** 2026-07-31
- **Tasks:** 2 (both `type="auto"`)
- **Files modified:** 3 (`README.rst`, `src/imio/googleauthenticator/tests/test_generic.py`, `CHANGES.rst`)

## Accomplishments

- **DOC-01** ("What two-step verification does not cover"): states the boundary and its mechanism (this plugin sees only logins the site's own PAS authenticates; a Zope-root account like `inituser`'s `admin` is authenticated above the site, and this plugin's password pre-check delegates to the site's other `IAuthenticationPlugin`s, none of which can resolve a root account, so it declines to veto); names PAS's own emergency-user carve-out (`_extractUserIds` tries it before and after the authenticator loop, upstream comment "Emergency user via HTTP basic auth always wins", `PluggableAuthService.py` lines 630-636 and 677-679 — confirmed against the actual installed egg at `/srv/cache/eggs/Products.PluggableAuthService-1.11.3-py2.7-linux-x86_64.egg/`); and states the deployment-side consequence (restrict `/Control_Panel` and the root ZMI, or ship no root password — nothing inside the site can close this).
- **DOC-02** ("HTTP Basic Auth, WebDAV, FTP and XML-RPC"): states the unconditional protocol consequence first (a 2FA-enabled human account can't use those protocols regardless of configuration); records the settled MFA-03 decision (`credentials_basic_auth` kept **active**, dated 2026-07-31, the three repositories searched and what was found, the explicit non-exhaustive caveat) rather than hedging across both branches; names the real, already-shipped alternative (service account with `enable_two_factor_authentication` false + `ip_addresses_whitelist` CIDR entry); and points at the pre-deployment operator check (confirm with ops that no script authenticates over Basic Auth — no test can prove that absence).
- **"ZMI -> acl_users" reconciled**: kept the ordered plugin list and "critical!" emphasis, added the one-sentence reason (the credentials wipe only blinds authenticators listed after `google_auth`), and replaced the "make sure" instruction with a verification step plus a profile-reapply recovery — matching what 04-02 actually shipped (`movePluginsTop`, re-asserted on every profile application).
- Two new test methods in `tests/test_generic.py`, backed by a module-level `_read_readme()` helper (added rather than reusing/refactoring the pre-existing DOC-03 test, per the plan's explicit instruction not to mix an unrelated change into this diff): `test_readme_documents_zope_root_limitation` and `test_readme_documents_basic_auth_consequence`. Both assert on identifiers, never prose.
- `CHANGES.rst`'s `1.0.0 (unreleased)` section now records phase 4 as it shipped, sourced from the `04-01`/`04-02`/`04-03` summaries.
- `bin/test -t '!robot'` — **67 tests, 0 failures, 0 errors** (up from 65 before this plan; the two new DOC tests are the only additions).

## Task Commits

Each task was committed atomically:

1. **Task 1: DOC-01 and DOC-02 in README.rst, each with a fact-presence test** - `fd1e854` (docs)
2. **Task 2: Changelog** - `6bd4264` (docs)

**Plan metadata:** (this commit, following SUMMARY.md write)

## Files Created/Modified

- `README.rst` — added "What two-step verification does not cover" and "HTTP Basic Auth, WebDAV, FTP and XML-RPC" sections between "Notes" and "Implementation details"; reconciled "ZMI -> acl_users".
- `src/imio/googleauthenticator/tests/test_generic.py` — added a module-level `import os` / `import imio.googleauthenticator`, a module-level `_read_readme()` helper, and `test_readme_documents_zope_root_limitation` / `test_readme_documents_basic_auth_consequence`. The pre-existing `test_readme_documents_the_deployment_key_and_its_failure_mode` (DOC-03) is untouched.
- `CHANGES.rst` — six new bullets in `1.0.0 (unreleased)` covering phase 4 as shipped; no released version section touched.

## Decisions Made

- **DOC-02's test asserts the branch actually taken.** `credentials_basic_auth` was kept active (04-02's checkpoint), so the README names the plugin's index-0 ordering as what protects that path, and the test asserts the literal phrase "index 0" that the README uses for it — a branch-specific check, not a generic one, so a future reversal of the decision without a README update goes red rather than staying silently stale.
- **Placement of the new sections**: directly after "Notes", before "Implementation details" — operational scope an operator should hit before internals, per the plan's explicit instruction.
- **"ZMI -> acl_users" kept, not replaced**: the ordered list and "critical!" emphasis stay (an operator who finds the order wrong in the ZMI still needs the reference list and the reason it matters); only the framing changed from "make sure" (manual install step) to "verify... and if wrong, re-apply the profile" (verification + recovery).
- **`docs/index.rst` left untouched**, per phase 3's established precedent that it is a stale pre-rename duplicate never kept in sync with `README.rst`. Verified via `git diff --name-only` on both task commits.

## Mutation Checks

Both required by the plan's acceptance criteria, run once during execution and recorded here (not merely claimed):

**DOC-01**: temporarily deleted the "What two-step verification does not cover" section from `README.rst` (a Python one-liner slicing the file between that heading and the next), ran `bin/test -t test_readme_documents_zope_root_limitation` — **failed** with `AssertionError: 'inituser' not found in ...` (the first-checked fact after the section was removed). Confirmed red, then restored the file.

**DOC-02**: temporarily deleted the "HTTP Basic Auth, WebDAV, FTP and XML-RPC" section, ran `bin/test -t test_readme_documents_basic_auth_consequence` — **failed** with `AssertionError: 'credentials_basic_auth' not found in ...`. Confirmed red, then restored the file.

After both checks, `README.rst` was restored from a saved pre-edit copy and confirmed **byte-identical** via `diff -q` before Task 1's commit was made — the mutation checks left no trace in the committed diff.

## reStructuredText Validity

`docutils` is not importable under `bin/python` or the system `python3` (`ModuleNotFoundError: No module named 'docutils'` in both). Built a throwaway virtualenv in the scratchpad directory (`python3 -m venv` + `pip install docutils`) solely to run the check the plan's acceptance criteria specify — this installs nothing into the project's own buildout/eggs and is not part of the shipped dependency set. `docutils.core.publish_doctree(...)` with `report_level=1, halt_level=5` (forcing every diagnostic to surface) produced **no output at all** for both `README.rst` and `CHANGES.rst` after this plan's edits — clean, no `SEVERE`/`ERROR`/`WARNING` nodes.

## Deviations from Plan

None - plan executed exactly as written. The only executor discretion exercised was Task 1(d)'s explicitly-offered choice to add a small module-level `_read_readme()` helper rather than repeating the three-line path construction in both new tests, which the plan named as the executor's call.

## Issues Encountered

- `docutils` is not installed anywhere reachable from `bin/python` or system `python3`; worked around with a throwaway venv per the plan's own fallback instruction ("state in the summary that the check could not be run and why" — in this case it *could* be run, just not with the interpreters named in the acceptance criteria text).
- The `PluggableAuthService.py` egg path named in the plan's `read_first` notes (`/srv/cache/eggs/Products.PluggableAuthService-1.11.3-py2.7-linux-x86_64.egg/...`) was confirmed to exist and match exactly — no substitution needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 (pas-boundary) is now complete: all four plans (04-01 through 04-04) executed, `bin/test -t '!robot'` at 67 tests / 0 failures / 0 errors.
- All 11 of the phase's edge-probe rows are now accounted for (04-01: 2, 04-02: 3, 04-03: 4, 04-04: 2 — 11 of 11), the last two (`DOC-01 unclassified`, `DOC-02 concurrency`) carried as `verification: backstop` per this plan's `<flagged_assumptions>`, since documentation genuinely has no edge case in the probe's sense.
- `credentials_basic_auth`'s ROADMAP open decision (closed by 04-02) is now also documented in the shipped, deployer-facing artefact — no longer only in a planning summary.
- No blockers carried forward. Phase 5 planning can proceed without any open item from this phase.

---
*Phase: 04-pas-boundary*
*Completed: 2026-07-31*

## Self-Check: PASSED

- FOUND: README.rst
- FOUND: src/imio/googleauthenticator/tests/test_generic.py
- FOUND: CHANGES.rst
- FOUND: .planning/phases/04-pas-boundary/04-04-SUMMARY.md
- FOUND commit: fd1e854 (Task 1)
- FOUND commit: 6bd4264 (Task 2)
- Full suite: 67 tests, 0 failures, 0 errors (`bin/test -t '!robot'`)
