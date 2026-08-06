---
phase: 04-pas-boundary
plan: 02
subsystem: auth
tags: [pas, pluginregistry, movePluginsTop, genericsetup, plone4, python2]

# Dependency graph
requires:
  - phase: 04-01
    provides: "the decide-only authenticateCredentials / IPubBeforeCommit redirect this plugin's ordering protects"
provides:
  - "movePluginsTop(interface, [plugin.getId()]) as the explicit, re-asserted-on-every-reinstall ordering mechanism for _add_plugin"
  - "test_plugin_is_first_authenticator, test_reapply_profile_keeps_plugin_first_and_unique, test_plugin_declares_no_challenge_protocol in tests/test_setuphandlers.py"
  - "a recorded, repository-visible decision to keep credentials_basic_auth active (comment block above _add_plugin in setuphandlers.py)"
affects: [04-03, 04-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Split idempotency guard: object creation guarded by objectIds() membership (runs once), activation guarded by listPluginIds() membership (raises KeyError if skipped), ordering unconditional (movePluginsTop is self-idempotent) -- so reinstall is a real recovery for a displaced plugin"
    - "Repository-visible decision record: a checkpoint answer to 'should we mutate a plugin we don't own' is written as a dated comment naming the evidence and its gap, not left implicit in a planning artifact only"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/setuphandlers.py
    - src/imio/googleauthenticator/tests/test_setuphandlers.py

key-decisions:
  - "MFA-03 checkpoint (Task 2), answered by human operator Chris on 2026-07-31: KEEP credentials_basic_auth active. Do NOT deactivate it. Deactivating a plugin this package does not own would be the same global-mutation-with-no-uninstall-counterpart anti-pattern the ROADMAP already condemns for Phase 7's popupforms.js. The research covered three iMio repositories -- imio.dms.mail, server.dmsmail, industrialisation -- and found no live dependency on HTTP Basic Auth against this Plone site's own acl_users, but that search was explicitly non-exhaustive (RESEARCH Assumptions Log A1), so a site-wide deactivation's blast radius if wrong is a silent automation failure with no signal in this repository."
  - "Consequence accepted with the 'keep' decision: correctness stays order-dependent. test_plugin_is_first_authenticator is therefore the ONLY control standing between a future plugin reorder and a Basic Auth bypass, and must never be weakened or deleted -- stated in both the setuphandlers.py comment and this summary so it survives context handoff."
  - "No profiles/uninstall/ counterpart is owed by this plan or by Phase 7 -- that obligation only existed under the 'deactivate' branch and does not apply here."
  - "Guidance for plan 04-03: test_basic_auth_veto must be written asserting the veto through the normal _extractUserIds() path (credentials_basic_auth extractor is still registered and active), NOT through a direct authenticateCredentials call bypassing extraction. Had 'deactivate' been chosen, _extractUserIds would produce no credentials at all and a veto assertion through that path would pass for the wrong (vacuous) reason -- that concern does not apply under 'keep'."

patterns-established:
  - "Pattern: an ordering invariant this package's whole security model rests on is asserted directly (test_plugin_is_first_authenticator) rather than inferred from an implementation detail (movePluginsDown bubbling the most-recent entry to index 0)"

requirements-completed: [MFA-03]

coverage:
  - id: D1
    description: "_add_plugin uses movePluginsTop(interface, [plugin.getId()]) instead of the movePluginsDown accident, and re-asserts ordering on every profile application (not only first install)"
    requirement: "MFA-03"
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#test_plugin_is_first_authenticator"
        status: pass
      - kind: unit
        ref: "tests/test_setuphandlers.py#test_reapply_profile_keeps_plugin_first_and_unique"
        status: pass
    human_judgment: false
  - id: D2
    description: "GoogleAuthenticatorPlugin declares no protocol attribute, so PAS's challenger-protocol fallback keeps it out of HTTPBasicAuthHelper's protocol group"
    requirement: "MFA-03"
    verification:
      - kind: unit
        ref: "tests/test_setuphandlers.py#test_plugin_declares_no_challenge_protocol"
        status: pass
    human_judgment: false
  - id: D3
    description: "credentials_basic_auth deactivation decision settled by human checkpoint (keep active) and recorded visibly in the repository, not left as an unstated assumption"
    verification: []
    human_judgment: true
    rationale: "The decision itself (keep vs. deactivate) was a human judgment call weighing an explicitly non-exhaustive evidence search against a security hardening; no automated test can validate that the recorded rationale is complete, only that the code matches what was decided (covered by the grep-based acceptance criteria run below)."

# Metrics
duration: ~15min (continuation from checkpoint; Task 1 duration recorded separately)
completed: 2026-07-31
status: complete
---

# Phase 04 Plan 02: PAS Plugin Ordering + Basic Auth Decision Summary

**movePluginsTop replaces an accidental movePluginsDown ordering side-effect, re-asserted on every profile reinstall, plus a human-recorded decision to keep credentials_basic_auth active rather than deactivate it.**

## Performance

- **Duration:** Task 1 ~70min (per STATE.md per-plan metrics, recorded by the prior executor agent before the checkpoint); Task 3 (this continuation) ~15min
- **Tasks:** 3 (Task 1: auto: ordering fix; Task 2: checkpoint:decision; Task 3: auto: implement recorded choice)
- **Files modified:** 2 (`src/imio/googleauthenticator/setuphandlers.py`, `src/imio/googleauthenticator/tests/test_setuphandlers.py`)

## Accomplishments

- `_add_plugin` in `setuphandlers.py` now calls `pas.plugins.movePluginsTop(interface, [plugin.getId()])` instead of the previous `movePluginsDown(interface, listPlugins(interface)[:-1])`, which only reached index 0 because the plugin happened to be the most recently activated entry.
- The idempotency guard was split: object creation (`_setObject`) is still guarded by `pluginid not in pas.objectIds()` and runs once; activation is separately guarded by `listPluginIds` membership (because `activatePlugin` raises `KeyError: 'Duplicate plugin id'` for an already-active plugin); ordering (`movePluginsTop`) now runs unconditionally on every profile application, because it is self-idempotent for an already-first plugin. This makes reinstalling the profile a real recovery if a third-party add-on has displaced the plugin from index 0.
- Three new tests in `test_setuphandlers.py`: `test_plugin_is_first_authenticator` (the security control itself), `test_reapply_profile_keeps_plugin_first_and_unique` (proves the re-assert path survives a deliberate displacement + reinstall, and does not raise or duplicate on a second `applyProfile`), and `test_plugin_declares_no_challenge_protocol` (Open Question 3 — asserts the plugin has no `protocol` attribute, keeping it out of `HTTPBasicAuthHelper`'s protocol group).
- The ROADMAP's open `credentials_basic_auth` decision is settled: **keep it active**. Recorded as a dated comment block directly above `_add_plugin` in `setuphandlers.py`, naming the date, the three repositories searched, the veto test that still protects the path, and the load-bearing consequence for `test_plugin_is_first_authenticator`.

## Task Commits

Each task was committed atomically:

1. **Task 1: movePluginsTop, re-asserted on every profile application, with the ordering test as the control** - `b3f5e18` (feat) — completed by the prior executor agent before the checkpoint.
2. **Task 2: checkpoint:decision — deactivate `credentials_basic_auth`?** — no commit (decision task); answered by human operator Chris on 2026-07-31, selecting option B (keep).
3. **Task 3: Implement the recorded choice ("keep" branch)** - `3b2c6d7` (docs) — recorded the decision as a comment block; no code behavior change, no new test (per plan's "keep"/"defer" branch instructions).

**Plan metadata:** (this commit, following SUMMARY.md write)

## Files Created/Modified

- `src/imio/googleauthenticator/setuphandlers.py` — `_add_plugin` restructured (Task 1: `movePluginsTop`, split guard); dated decision-record comment added above `_add_plugin` (Task 3).
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` — three new test methods and `self.pas` added to `setUp` (Task 1). No changes in Task 3 — the "keep" branch adds no test per the plan's own instructions (the `deactivate` branch was the one requiring `test_basic_auth_extractor_is_deactivated`).

## Decisions Made

**MFA-03 checkpoint decision (Task 2), answered by human operator Chris on 2026-07-31: KEEP `credentials_basic_auth` active. Do NOT deactivate it.**

- **Repositories the evidence covered (all three, per 04-RESEARCH.md Assumptions Log A1):** `imio.dms.mail`, `server.dmsmail`, `industrialisation`. No live dependency on HTTP Basic Auth against this Plone site's own `acl_users` was found — `server.dmsmail`'s only `webdav-address` setting is commented out everywhere it appears; no XML-RPC client targeting the site was found; `scripts/run-copy-missing-blobs.py` authenticates *outward* to a different remote site, not into this one; and `pack_zeo.sh` (from `industrialisation`) targets the Zope-root `Control_Panel`, above any Plone site's `acl_users`, so it is unaffected either way.
- **The gap, stated explicitly:** the search covered three repositories, not every iMio repository, and no test can prove the absence of an external consumer. That gap is the reason the "keep" option's stated cost — correctness depending on plugin ordering, enforced only in CI and not at request time — was accepted rather than eliminated.
- **Rationale for "keep" over "deactivate":** deactivating a plugin this package does not own is a site-wide mutation with no uninstall counterpart, structurally the same anti-pattern the ROADMAP condemns for `popupforms.js` in Phase 7. Choosing it would have incurred a `profiles/uninstall/` obligation for a hardening whose necessity the evidence could not confirm.
- **What "keep" does NOT give up:** the Basic Auth credentials path is still vetoed. Plan 04-03's `test_basic_auth_veto` asserts that directly. No global mutation occurs, no uninstall obligation is owed by this plan or by Phase 7.
- **Load-bearing consequence, stated in both the code comment and here:** `test_plugin_is_first_authenticator` is now the *only* thing standing between a future plugin reorder and a Basic Auth bypass. It must never be weakened or deleted.

**Guidance for plan 04-03 (`test_basic_auth_veto`):** write it asserting the veto through the normal `_extractUserIds()` path — `credentials_basic_auth` remains registered and active, so the extractor still produces a credentials dict that this plugin's in-place wipe (per `authenticateCredentials`) must blind. Do **not** write it as a direct `authenticateCredentials` call that bypasses extraction; that concern only applied under the (unselected) `deactivate` branch, where `_extractUserIds` would produce no credentials at all and a veto assertion would pass for the wrong, vacuous reason.

## Deviations from Plan

None - Task 3 executed exactly as the plan's "keep"/"defer" branch specifies: no deactivation code, a comment block recording the decision, date, repositories, veto-test pointer, and the load-bearing consequence for the ordering test.

## Issues Encountered

None. The checkpoint answer was unambiguous (option B, "keep") and the plan's own text specified exactly what the "keep" branch requires — no interpretation was needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04-03 can proceed: `test_basic_auth_veto` should be written against the normal `_extractUserIds()` path (guidance above), and it can rely on `test_plugin_is_first_authenticator` (this plan) as the ordering control it composes with.
- Plan 04-04 (DOC-02) has what it needs: the decision id (`keep`), its date (2026-07-31), the three repositories covered, and the explicit statement that no `profiles/uninstall/` counterpart is owed.
- No blockers carried forward from this plan. The `credentials_basic_auth` ROADMAP open decision is now closed for this milestone.

---
*Phase: 04-pas-boundary*
*Completed: 2026-07-31*

## Self-Check: PASSED

- FOUND: src/imio/googleauthenticator/setuphandlers.py
- FOUND: src/imio/googleauthenticator/tests/test_setuphandlers.py
- FOUND: .planning/phases/04-pas-boundary/04-02-SUMMARY.md
- FOUND commit: b3f5e18 (Task 1)
- FOUND commit: 3b2c6d7 (Task 3)
