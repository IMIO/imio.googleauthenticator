---
phase: 7
slug: coexistence-with-imio-dms-mail
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-04
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `07-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` 4.4.4 via `bin/test`; `unittest2`-style classes; `plone.app.testing` layers (already wired throughout this package) |
| **Config file** | none dedicated — driven by the `[test]` part in `base.cfg` |
| **Quick run command** | `bin/test -t <test_method_or_pattern>` |
| **Full suite command** | `bin/test -t '!robot'` |
| **Estimated runtime** | ~90 seconds full suite (Plone 4.3 layer setup dominates); ~25 s for a single-test run against a warm layer |

`test_robot.py` needs a real browser and is excluded everywhere (`make test` and CI both pass
`-t !robot`). `plone.testing` stays unpinned on purpose — Plone 4.3 supplies 4.1.3, and pinning
5.0.0 introduces the `TestIsolationBroken` guard that every browser test in this package trips.

---

## Sampling Rate

- **After every task commit:** Run the specific new/changed test method for that task,
  e.g. `bin/test -t test_next_url_is_validated_against_the_portal`
- **After every plan wave:** Run `bin/test -t '!robot'`
- **Before `/gsd-verify-work`:** Full suite must be green **and** both human-verify items below
  must be recorded as UAT — not silently skipped
- **Max feedback latency:** ~25 seconds (single test, warm layer)

---

## Per-Task Verification Map

Task IDs are assigned by the planner; this table is keyed by requirement so it survives
re-planning. The planner must map each row onto a concrete task ID in its PLAN.md.

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| COEX-01 | `TokenForm`'s rendered `<form>` tag carries `id="login_form"` | integration (Browser content assertion) | `bin/test -t test_token_form_carries_login_form_id` | ❌ W0 | ⬜ pending |
| COEX-02 | `login_form.cpt` and its `.metadata` no longer exist on disk | unit (filesystem fact) | `bin/test -t test_login_form_override_is_deleted` | ❌ W0 | ⬜ pending |
| COEX-03 | Vendored `popupforms.js`, its `jsregistry.xml` entries, and the `remove="True"` line are all gone | unit (filesystem + `minidom` XML assertion) | `bin/test -t test_popupforms_js_is_not_vendored` | ❌ W0 | ⬜ pending |
| COEX-04 | `control_panel_extra` and `request_bar_code_reset_email` still render; no `restrictedTraverse` remains | integration (1 existing test + 1 **new**) + unit (source-grep) | `bin/test -t test_render_appends_the_extra_links`; `bin/test -t test_reset_email_survives_a_non_ascii_sender_name`; `bin/test -t test_no_restrictedTraverse_left_in_browser_code` | ❌ W0 (control-panel test, **new file** `tests/test_controlpanel.py`) / ✅ (email test) / ❌ W0 (grep test) | ⬜ pending |
| COEX-05 | Skin layer, `skins.xml`, `registerDirectory` and `skins/` are gone | unit (filesystem + ZCML source-grep) | `bin/test -t test_skin_layer_is_removed` | ❌ W0 | ⬜ pending |
| COEX-06 | `profiles/uninstall/` restores every install-time registry change | integration (`applyProfile` install→uninstall, assert `portal_javascripts` / `portal_css` sets) | `bin/test -t test_uninstall_restores_resource_registries` | ❌ W0 | ⬜ pending |
| COEX-07 | Both install orders leave both packages working; `popupforms.js` registered exactly once | integration (synthetic collision using `imio.dms.mail`'s real XML fragment) | `bin/test -t test_popupforms_js_survives_either_install_order` | ❌ W0 | ⬜ pending |
| COEX-09 | Header "Log in" link reaches the token form and completes | integration (`Browser.getLink().click()` proves markup + redirect chain) | `bin/test -t test_login_link_reaches_token_form` | ❌ W0 | ⬜ pending |
| BUG-01 | Off-site `next_url` refused; on-site honoured | integration (`tests/test_token.py`) | `bin/test -t test_next_url_is_validated_against_the_portal` | ❌ W0 | ⬜ pending |
| BUG-06 | Query-string values survive the quoting round-trip | unit (`tests/test_adapter.py`, new `TestCameFromAdapter`) | `bin/test -t test_get_came_from_quotes_the_value` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

### Plan mapping (assigned 2026-08-04 by plan-phase)

| Requirement | Plan / task |
|---|---|
| COEX-01, COEX-03, COEX-09 (automated) | 07-01 Task 1 (tracer) |
| COEX-02, BUG-01, BUG-06 | 07-01 Task 2 (one commit, per ROADMAP criterion 4) |
| COEX-04, COEX-05 (production change) | 07-02 Task 1 (one commit) |
| COEX-04, COEX-05 (absence assertions) | 07-02 Task 2 |
| COEX-06, COEX-07 (synthetic), COEX-03 (ownership invariant) | 07-03 Task 1 |
| documentation correctness | 07-03 Task 2 |
| COEX-07, COEX-09 (manual halves) | 07-04 Tasks 1 and 2 |

### Corrections to this file, made at plan time

1. **`test_control_panel_view` does not exist.** This file and `07-RESEARCH.md` both marked the
   control-panel half of COEX-04 as already covered. Verified false: nothing in the suite calls
   `GoogleAuthenticatorSettingsEditForm.render()` or opens `@@google-authenticator-settings`.
   `tests/test_helpers.py::test_bulk_enable_reports_failure_when_seed_key_is_broken` instantiates the
   form and calls `update()` and `handleSave`, never `render()`. The row above is corrected: the
   control-panel fragment had **zero** coverage, and the new test is
   `test_render_appends_the_extra_links` in a **new** `tests/test_controlpanel.py` (R5: one test file
   per production file).

2. **Two pre-existing tests must be EDITED, not merely kept green.** Neither is listed as a Wave 0
   item because neither is new, but both go red if the phase's deletions land without them:
   - `tests/test_setuphandlers.py::test_registered_javascript_loads_after_jquery` — its `ours` tuple
     names the vendored resource id and asserts it is registered. `07-RESEARCH.md`'s Pitfall 4 claims
     both jsregistry tests need no edit; that is correct for
     `test_every_javascript_registration_pins_its_position` (which parses the XML and skips removal
     nodes) and **wrong** for this one. Edited in 07-01 Task 1.
   - `tests/test_generic.py::test_manifest_ships_the_profile_and_catalogues` — its `required` tuple
     asserts the `MANIFEST.in` directive for the deleted skin directory. Edited in 07-02 Task 1.
   - `tests/test_request_bar_code_reset.py::setUp` — its `setupCurrentSkin` call becomes dead once the
     email body is no longer a skin template. Removed in 07-02 Task 1.

3. **One test added beyond this map**, from the phase's assumption-delta decision:
   `tests/test_setuphandlers.py::test_profile_only_registers_resources_it_owns` (07-03 Task 1) asserts
   every `id` in all four of this package's resource-registry profile files begins with
   `++resource++imio.googleauthenticator/`. It is the invariant that goes red if a future phase
   reintroduces the singular-owner assumption COEX-03 removes.

---

## Wave 0 Requirements

- [ ] `tests/test_adapter.py` — add a `TestCameFromAdapter` class (none exists today; only
      `TestEnhancedUserDataPanelAdapter` is present) to cover BUG-06
- [ ] Source-grep test asserting no `restrictedTraverse` remains in `browser/` (COEX-04).
      Precedent for the style: the existing MFA-12 source-grep test in `tests/test_pas_plugin.py`
- [ ] Synthetic `imio.dms.mail`-collision fixture (COEX-07) — constructs the exact
      `<javascript id="popupforms.js" insert-after="form_tabbing.js" />` entry, quoted verbatim
      from `/srv/src/imio.dms.mail/imio/dms/mail/profiles/default/jsregistry.xml:87`, and applies
      it via `portal_javascripts` both before and after this package's own profile import
- [ ] Filesystem/XML assertion tests for COEX-02, COEX-03 and COEX-05 (deletion facts)
- [ ] Install→uninstall registry round-trip test for COEX-06
- [ ] Browser tests for COEX-01 and COEX-09
- [ ] New `tests/test_controlpanel.py` with `test_render_appends_the_extra_links` (COEX-04) — the
      control-panel fragment's coverage is genuinely zero today, see Correction 1 above
- **Framework install: none.** `zope.testrunner`, `plone.app.testing` and
  `plone.testing.z2.Browser` are already fully wired in this package.

---

## Manual-Only Verifications

Both items below are genuinely outside `bin/test`'s reach. They must be recorded as
`checkpoint:human-verify` and carried into UAT — not marked green by an automated proxy.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real two-egg install in both orders, with `imio.dms.mail` actually present | COEX-07 (full proof; the synthetic collision test covers the registry mechanics only) | `imio.dms.mail` is not a dependency of this package's buildout, and pulling its ~40-egg tree into `test-4.3.cfg` is a disproportionate change | Use the existing `server.dmsmail` MOD-1076 evaluation environment, which already stages `imio.googleauthenticator` alongside the real `imio.dms.mail`. Install A-then-B, confirm both work and `popupforms.js` appears exactly once in `portal_javascripts`; reset; install B-then-A; confirm the same. |
| Clicking the real header "Log in" link in a JS-capable browser and completing login through the stock overlay | COEX-09 (full proof; the automated test covers markup + redirect chain only) | `bin/test` has no JS engine. Selenium/Robot are excluded from this suite everywhere. | Run `bin/instance fg`. As a 2FA-enabled user, click the header "Log in" link (do not POST to `login_form` directly). Confirm the token form appears **inside** Plone's stock overlay, that entering a valid token completes the login, and that a `portalMessage` warning still renders inside an overlay elsewhere on the site. |

---

## Validation Sign-Off

- [ ] All tasks have an `<automated>` verify command or a declared Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without an automated verify
- [ ] Wave 0 covers every ❌ reference in the map above
- [ ] No watch-mode flags in any command
- [ ] Feedback latency < 30s for the per-task command
- [ ] Both manual-only verifications recorded as `checkpoint:human-verify` in a PLAN.md
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
