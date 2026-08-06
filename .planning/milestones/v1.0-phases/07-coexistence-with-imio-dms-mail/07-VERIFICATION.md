---
phase: 07-coexistence-with-imio-dms-mail
verified: 2026-08-05T00:00:00Z
status: passed
score: 5/5 roadmap success criteria verified; 10/10 requirement IDs satisfied
behavior_unverified: 0
overrides_applied: 0
re_verification: false
---

# Phase 7: Coexistence with imio.dms.mail Verification Report

**Phase Goal:** This package and `imio.dms.mail` install alongside each other in either
order and both keep working, with no vendored JavaScript, no skin layer, no resource we
do not own being mutated, and no open redirect.
**Verified:** 2026-08-05
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — the authoritative contract)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Header "Log in" link reaches the token form inside Plone's stock overlay and completes login; 507 vendored lines (`login_form.cpt` 310 + `popupforms.js` 197), `skins.xml`, `registerDirectory`, `skins/` all gone | ✓ VERIFIED | `TokenForm.render()` at `browser/forms/token.py:65-89` inserts `id="login_form"` via `str.replace(..., 1)`, not a class attribute. `test_login_link_reaches_token_form` and `test_token_form_carries_login_form_id` pass (confirmed by direct run). `browser/static/plone_ecmascript/`, `skins/googleauthenticator_custom/login_form.cpt[.metadata]`, `profiles/default/skins.xml` all absent on disk; `configure.zcml` has 0 `cmf:` / `xmlns:cmf` occurrences. **07-UAT.md item 2 confirms the real-browser overlay bind (JS-level proof, which `bin/test` cannot reach).** |
| 2 | Both install orders leave both packages working; `popupforms.js` registered exactly once; the `remove="True"` unregistration entry is deleted | ✓ VERIFIED | `profiles/default/jsregistry.xml` contains only the `main.js` entry, 0 occurrences of `remove=`/`popupforms`. `test_popupforms_js_survives_either_install_order` (synthetic, both orders + double-import, asserts `count() == 1` never 0/2) passes. **07-UAT.md item 1 confirms the real two-egg install in both orders on `server.dmsmail` MOD-1076**, exactly-one overlay registration in each order, `imio.dms.mail` overlay widgets working, 2FA login completing. |
| 3 | Uninstalling restores everything the install profile changed via a real `profiles/uninstall/` with `jsregistry.xml`/`cssregistry.xml` | ✓ VERIFIED | `profiles/uninstall/jsregistry.xml` and `cssregistry.xml` each carry exactly one `remove="True"` entry, id copied verbatim from the matching default file. `test_uninstall_restores_resource_registries` (precondition, removal, coexistence, idempotency, reversibility — 5 assertion groups) passes. |
| 4 | Off-site `next_url` refused, on-site honoured, query-string values URL-encoded on write, same commit as `login_form.cpt` deletion | ✓ VERIFIED | `token.py:171-173` calls `portal_url_tool.isURLInPortal(redirect_url)` and falls back to `context_url` on refusal (refuse-and-fall-back, not warn-and-continue). `adapter.py:123` passes `quote_url=True`. `test_next_url_is_validated_against_the_portal` (both halves) and `test_get_came_from_quotes_the_value` (round-trip + type + no-referer + no-key scenarios) pass. Commit `6c14064` contains the `login_form.cpt` deletion, the `isURLInPortal` guard, and `quote_url=True` together, confirmed via `git show`. |
| 5 | `control_panel_extra.html` and `request_bar_code_reset_email.pt` still render via `ViewPageTemplateFile`, no `restrictedTraverse` remaining | ✓ VERIFIED | `controlpanel.py:85` declares `additional_template = ViewPageTemplateFile(...)`; `request_bar_code_reset.py:50` declares `mail_text_template = ViewPageTemplateFile(...)`. `grep -rn restrictedTraverse src/imio/googleauthenticator/browser/` returns nothing. `test_render_appends_the_extra_links`, `test_no_restrictedTraverse_left_in_browser_code`, and the three pre-existing email tests all pass. |

**Score:** 5/5 ROADMAP success criteria verified.

### Requirement ID Coverage (COEX-01..07, COEX-09, BUG-01, BUG-06)

| Requirement | Plan | Test | Result |
|---|---|---|---|
| COEX-01 | 07-01 | `test_token_form_carries_login_form_id` | pass |
| COEX-02 | 07-01 | `test_login_form_override_is_deleted` | pass |
| COEX-03 | 07-01 / 07-03 | `test_popupforms_js_is_not_vendored`, `test_registered_javascript_loads_after_jquery`, `test_profile_only_registers_resources_it_owns` | pass |
| COEX-04 | 07-02 | `test_render_appends_the_extra_links`, `test_no_restrictedTraverse_left_in_browser_code`, `test_reset_email_survives_a_non_ascii_sender_name` | pass |
| COEX-05 | 07-02 | `test_skin_layer_is_removed` | pass |
| COEX-06 | 07-03 | `test_uninstall_restores_resource_registries` | pass |
| COEX-07 | 07-03 (synthetic) + 07-04 (real, UAT) | `test_popupforms_js_survives_either_install_order` + 07-UAT.md item 1 | pass |
| COEX-09 | 07-01 (automated) + 07-04 (real, UAT) | `test_login_link_reaches_token_form` + 07-UAT.md item 2 | pass |
| BUG-01 | 07-01 | `test_next_url_is_validated_against_the_portal` | pass |
| BUG-06 | 07-01 | `test_get_came_from_quotes_the_value` | pass |

All 10 requirement IDs assigned to this phase are covered by at least one passing test, confirmed by direct execution (not taken from any SUMMARY claim). `REQUIREMENTS.md` marks all ten `Complete` under `Phase 7`, consistent with this evidence. No orphaned requirement IDs found — the union of every plan's `requirements:` frontmatter exactly equals the ROADMAP's Phase 7 requirement list.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `browser/forms/token.py::TokenForm.render()` | new method, `id="login_form"` post-process | ✓ VERIFIED | present, docstring explains rationale, `str.replace(..., 1)` used |
| `browser/static/plone_ecmascript/popupforms.js` | deleted | ✓ VERIFIED | absent, directory gone |
| `skins/googleauthenticator_custom/login_form.cpt[.metadata]` | deleted | ✓ VERIFIED | absent |
| `profiles/default/jsregistry.xml` | `remove="True"` entry gone, `main.js` intact with `insert-bottom="True"` | ✓ VERIFIED | confirmed by direct read |
| `browser/controlpanel.py::additional_template` | new `ViewPageTemplateFile` class attribute | ✓ VERIFIED | present, wired in `render()` |
| `browser/forms/request_bar_code_reset.py::mail_text_template` | new `ViewPageTemplateFile` class attribute | ✓ VERIFIED | present, wired in `handleSubmit`, `.format(bar_code_reset_url=...)` substitution intact |
| `skins/` tree, `profiles/default/skins.xml`, `cmf:registerDirectory` | all deleted | ✓ VERIFIED | absent; 0 `cmf:`/`xmlns:cmf` occurrences in `configure.zcml` |
| `profiles/uninstall/jsregistry.xml`, `cssregistry.xml` | new, one `remove="True"` entry each, id matching default profile | ✓ VERIFIED | present, exactly one entry each, correct ids |
| `profiles/uninstall/skins.xml` | deleted (nothing left to unregister) | ✓ VERIFIED | absent |
| `README.rst` / `docs/index.rst` | no "has been overridden" claims, ownership statement present | ✓ VERIFIED | `grep -c 'has been overridden'` returns 0 in both; ownership prefix statement present in README |
| `CHANGES.rst` | Phase 7 entry with requirement IDs + operator upgrade note | ✓ VERIFIED | `COEX-06`, `BUG-01`, `BUG-06`, `portal_setup` all present |
| `.planning/phases/07.../07-UAT.md` | both human-verify items recorded, not silently skipped | ✓ VERIFIED | both items present with concrete recorded observations (resource counts, overlay behavior, console state) |

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `TokenForm.render()` | `FormWrapper.update()` | `self.contents = self.form_instance.render()` | ✓ WIRED — confirmed by reading `plone.z3cform.layout`'s render path cited in the docstring and by `test_login_link_reaches_token_form` passing end to end |
| emitted `id="login_form"` | stock overlay's `formselector` | literal string agreement | ⚠️ not testable by `bin/test` (no JS engine) — closed by 07-UAT.md item 2 (real browser, overlay bind confirmed) |
| `token.py::handleSubmit`'s `next_url` | `pas_plugin.send_2fa_redirect`'s `&next_url=` append | `CameFromAdapter.getCameFrom()` quoting | ✓ WIRED — `quote_url=True` write end, `isURLInPortal` read-end guard, round-trip proven by `test_get_came_from_quotes_the_value` |
| `profiles/uninstall/jsregistry.xml` | `profiles/default/jsregistry.xml` | mirrored id, `remove="True"` | ✓ WIRED — ids match verbatim, confirmed by direct read and by `test_profile_only_registers_resources_it_owns` |
| `imio.dms.mail`'s bare reposition entry | `portal_javascripts.moveResourceAfter` | synthetic replay | ✓ WIRED (synthetic) — confirmed real by 07-UAT.md item 1 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full suite green | `bin/test -t '!robot'` | `111 tests, 0 failures, 0 errors` (run directly by this verifier) | ✓ PASS |
| Phase-7-specific tests, single-named-test run | `bin/test -t test_token_form_carries_login_form_id -t test_login_link_reaches_token_form -t test_next_url_is_validated_against_the_portal -t test_get_came_from_quotes_the_value -t test_popupforms_js_is_not_vendored -t test_login_form_override_is_deleted -t test_skin_layer_is_removed -t test_uninstall_restores_resource_registries -t test_popupforms_js_survives_either_install_order -t test_profile_only_registers_resources_it_owns -t test_no_restrictedTraverse_left_in_browser_code -t test_render_appends_the_extra_links -t test_registered_javascript_loads_after_jquery` | `13 tests, 0 failures, 0 errors` | ✓ PASS |
| No debt markers introduced by this phase | `grep -n -E "TBD|FIXME|XXX"` on every file this phase's plans modified | Only two pre-existing `FIXME`s in `helpers.py` (blamed to 2014/2015 upstream commits, untouched by this phase's diffs — confirmed via `git show 6c14064 -- helpers.py`, which shows only a docstring rewrite at a different location) | ✓ PASS — no new debt markers |

### Requirements Coverage

Already presented above (10/10). No `ORPHANED` requirements found for Phase 7 in `REQUIREMENTS.md`.

### Anti-Patterns Found

None blocking. Two pre-existing `FIXME` comments in `helpers.py` (lines 875, 903) predate this phase by over a decade and were not touched by any Phase 7 commit — not attributable to this phase's work.

## Out-of-scope items correctly excluded from this phase's verdict

- **COEX-10** (instance-wide `userCreatedHandler` crash against an uninstalled site) — fixed in quick task `260805-f5m` (commit `184f053`), found while running 07-04's human verification but not a Phase 7 requirement. `REQUIREMENTS.md` correctly attributes it to the quick task, not Phase 7.
- **MFA-14** (existing accounts not enrolled when `globally_enabled` is turned on) — new, unassigned requirement recorded as an open gap in `07-UAT.md`. The operator explicitly decided it does not block Phase 7, on the grounds that COEX-07's stated criteria (both install orders work, resource count correct, overlays work, 2FA login completes) are met in both orders. Not counted as a Phase 7 gap.
- **`bin/code-analysis`** now fails on 500 pre-existing findings (up from the previously recorded 318, per `STATE.md`'s 2026-08-05 re-measurement) — explicitly Phase 8 / QUAL-06 scope, not a Phase 7 gap.

## Note on a `backstop`-verification truth (not a gap)

`07-03-PLAN.md`'s must-haves includes one truth marked `verification: backstop`: that a GenericSetup profile import interrupted mid-way leaves `portal_javascripts` either fully pre- or fully post-import, because the import runs inside one ZODB transaction. This is a platform-level (Zope/ZODB) transactional guarantee, not a behavior this phase's code introduces, and the plan itself marked it unverifiable by a test in this suite — it is a documented, accepted design assumption underlying every `applyProfile`-based test in this codebase, not unique to Phase 7's deliverables. It does not gate any ROADMAP success criterion and is not treated as a gap or as a new human-verification item.

## Human Verification

Both items this phase genuinely required (COEX-07's real two-egg install, COEX-09's real-browser overlay bind) were already performed by the operator and are recorded with concrete observations in `07-UAT.md` (resource counts as numbers, overlay behavior, login completion, JS console state) — not closed on the strength of the automated/synthetic halves alone, satisfying plan 07-04's blocking prohibition. No new item requiring human testing was found during this verification.

One minor observation, not rising to a gap: 07-UAT.md's item 1 notes "The specific `imio.dms.mail` widget exercised was not recorded by name" — plan 07-04's acceptance criteria asked for a *named* widget. The operator recorded this explicitly as a known shortfall in the record itself rather than silently, and COEX-07's stated criteria (resource count, both packages functional, 2FA login) are otherwise fully met and recorded with concrete numbers. This is not treated as reopening the already-closed human checkpoint.

## Gaps Summary

None. All five ROADMAP success criteria are observably true in the codebase; all ten requirement IDs are covered by passing tests; the two items requiring real human verification were performed and recorded, not skipped or proxied; the full test suite (111 tests) passes with 0 failures; no vendored JavaScript, no skin layer, and no resource this package does not own is mutated; the open redirect (BUG-01) and query-string injection (BUG-06) are both closed with passing non-vacuity-checked tests.

---
*Verified: 2026-08-05*
*Verifier: Claude (gsd-verifier)*
