---
phase: quick-260806-gfr
plan: 01
type: execute
wave: 1
depends_on: []
quick_id: 260806-gfr
autonomous: true
requirements: [COEX-06]
files_modified:
  - src/imio/googleauthenticator/profiles/uninstall/componentregistry.xml
  - src/imio/googleauthenticator/profiles/uninstall/actions.xml
  - src/imio/googleauthenticator/profiles/uninstall/browserlayer.xml
  - src/imio/googleauthenticator/profiles/uninstall/controlpanel.xml
  - src/imio/googleauthenticator/profiles/uninstall/registry.xml
  - src/imio/googleauthenticator/profiles/uninstall/imio.googleauthenticator.uninstall.txt
  - src/imio/googleauthenticator/setuphandlers.py
  - src/imio/googleauthenticator/configure.zcml
  - src/imio/googleauthenticator/tests/test_setuphandlers.py
  - CHANGES.rst

must_haves:
  truths:
    - "Applying `imio.googleauthenticator:uninstall` removes the `google_auth` PAS plugin from `acl_users` and from every plugin-type listing it was registered in."
    - "Applying it also removes the local `IUserDataSchemaProvider` utility, the three `portal_actions/user` entries, the `imio.googleauthenticator` browser layer, the `google_authenticator_settings` control-panel configlet, and the `IGoogleAuthenticatorSettings` registry records."
    - "Applying the uninstall profile twice raises nothing and leaves the same state as applying it once."
    - "Re-applying `imio.googleauthenticator:default` after a full uninstall restores all six artifacts — the uninstall is reversible, not destructive."
    - "The eight `portal_memberdata` property declarations and an enrolled user's stored seed survive the uninstall untouched."
    - "`bin/test -t '!robot'` stays green, `bin/test-coverage -t '!robot'` exits 0 at 90% or above, and `bin/code-analysis` exits 0."
  artifacts:
    - src/imio/googleauthenticator/profiles/uninstall/componentregistry.xml
    - src/imio/googleauthenticator/profiles/uninstall/actions.xml
    - src/imio/googleauthenticator/profiles/uninstall/browserlayer.xml
    - src/imio/googleauthenticator/profiles/uninstall/controlpanel.xml
    - src/imio/googleauthenticator/profiles/uninstall/registry.xml
    - src/imio/googleauthenticator/profiles/uninstall/imio.googleauthenticator.uninstall.txt
    - "src/imio/googleauthenticator/setuphandlers.py — `uninstallVarious` plus its plugin-removal helper"
    - "src/imio/googleauthenticator/configure.zcml — a second `genericsetup:importStep`"
    - "src/imio/googleauthenticator/tests/test_setuphandlers.py — two new test methods"
    - CHANGES.rst
  key_links:
    - "`configure.zcml`'s new `genericsetup:importStep` handler points at `imio.googleauthenticator.setuphandlers.uninstallVarious`, which gates on `context.readDataFile('imio.googleauthenticator.uninstall.txt')` — present only in `profiles/uninstall/`, so the step is a no-op for every other profile import in the process, exactly as `setupVarious` gates on `imio.googleauthenticator.marker.txt`."
    - "`pas._delObject(PAS_ID)` reaches `PluggableAuthService._delOb` (PluggableAuthService.py:454-465), which calls `plugins.removePluginById(id)` (PluginRegistry.py:320-327) and deactivates the plugin from every plugin type it is configured in. The delete IS the deactivation — no separate loop is needed."
    - "`profiles/uninstall/componentregistry.xml`'s `interface` attribute is what `_ofs_id` (GenericSetup/components.py:361-371) turns into the OFS id, and that is the same id the install-time factory registration created (components.py:344-356). Getting the interface string wrong makes the removal a silent no-op."
---

<objective>
Widen `profiles/uninstall/` so it reverses what `profiles/default/` registers, closing the
COEX-06 wording/scope mismatch recorded as Gap 2 in `.planning/v1.0-MILESTONE-AUDIT.md`.

Five new profile files remove the local utility, the three user actions, the browser layer,
the control-panel configlet and the settings records. One new import step removes the
`google_auth` PAS plugin, which no GenericSetup profile can do. Two deliberate exclusions —
memberdata properties and `user_registration_fields` — stay excluded, and are pinned by a
test so a future edit cannot quietly start deleting user data.

Purpose: today, uninstalling this add-on leaves the PAS plugin intercepting every login and
a local utility that unpickles as `OFS.Uninstalled.Broken` once the egg is removed.
Output: a `profiles/uninstall/` that is reversible rather than destructive, proven by tests.
</objective>

<context>
@.planning/STATE.md
@CLAUDE.md
@.claude/CLAUDE.md
@src/imio/googleauthenticator/setuphandlers.py
@src/imio/googleauthenticator/configure.zcml
@src/imio/googleauthenticator/profiles/default/actions.xml
@src/imio/googleauthenticator/profiles/default/componentregistry.xml
@src/imio/googleauthenticator/profiles/default/browserlayer.xml
@src/imio/googleauthenticator/profiles/default/controlpanel.xml
@src/imio/googleauthenticator/profiles/default/registry.xml
@src/imio/googleauthenticator/profiles/uninstall/jsregistry.xml
@src/imio/googleauthenticator/tests/test_setuphandlers.py
</context>

<research_findings>
Every removal idiom below was read from this buildout's own pinned eggs under
`parts/omelette/`, not from memory. Cite the file:line when writing the XML comments.

| What | Idiom | Confirmed at | Idempotent because |
|---|---|---|---|
| Browser layer | `<layer name="..." remove="True"/>` | `plone/browserlayer/exportimport.py:60-68` | `unregister_layer`'s `KeyError` is caught and logged |
| Registry records | `<records interface="..." remove="true"/>` | `plone/app/registry/exportimport/handler.py:305,322-334` | `importRecord` logs a warning for a missing record (handler.py:150-156) |
| Configlet | `<configlet action_id="..." remove="True"/>` | `Products/CMFPlone/exportimport/controlpanel.py:115-119` | `unregisterConfiglet` builds an empty selection (PloneControlPanel.py:143-147) |
| portal_actions entries | `<object name="..." remove="True"/>` | `Products/GenericSetup/utils.py:559-564` | guarded by `if obj_id in parent.objectIds()` |
| Local utility | `<utility interface="..." remove="True"/>` | `Products/GenericSetup/components.py:305-312` | `unregisterUtility` returns `False` rather than raising (zope/component/registry.py:129-132) |

Hard constraints found in the same reading:

- **`<records remove="true"/>` must carry no child `<value>` nodes** — `handler.py:322-325`
  raises `ValueError` if it does.
- **The utility removal must NOT carry a `factory` attribute.** The remove branch
  (`components.py:305-312`) reads only `interface` and `name`; `_ofs_id`
  (`components.py:361-371`) derives the OFS id from `interface`.
- **No purge risk.** `componentregistry.xml`, `actions.xml` and `controlpanel.xml` importers
  all purge only under `self.environ.shouldPurge()` (`components.py:85`,
  `CMFCore/exportimport/actions.py:118`, `CMFPlone/exportimport/controlpanel.py:59`).
  The uninstall profile is registered as `EXTENSION` and `applyProfile` passes
  `purge_old=False`, so `shouldPurge()` is `False` and nothing outside our nodes is touched.
- **Nested action removal works** because `ActionCategoryNodeAdapter`
  (`CMFCore/exportimport/actions.py:33-34`) mixes in `ObjectManagerHelpers`, and
  `_initObjects` recurses via `importer.node = child` (`GenericSetup/utils.py:599-602`).
- **`pas._delObject(PAS_ID)` already deactivates.** `PluggableAuthService._delOb`
  (`PluggableAuthService.py:454-465`) calls `plugins.removePluginById(id)`, which
  (`Products/PluginRegistry/PluginRegistry.py:320-327`) deactivates the plugin from every
  plugin type it is configured in. Do not hand-roll a `deactivatePlugin` loop.
- **`MANIFEST.in` already covers the new files** — `recursive-include
  src/imio/googleauthenticator/profiles *`. No packaging change needed.
- **Observation, do not act on it:** `profiles/default/propertiestool.xml` and
  `profiles/default/site_properties.xml` are byte-identical duplicates. Out of scope here.
</research_findings>

<scope_boundary>
**INCLUDED:** the five uninstall XML files, the uninstall marker data file,
`setuphandlers.uninstallVarious` plus its plugin-removal helper, the ZCML import-step
registration, the two new test methods, and the `CHANGES.rst` entry.

**EXCLUDED — deliberately, and the reasons must be written into the code as comments:**

1. **`memberdata_properties.xml`** — the eight property declarations stay. Removing them
   destroys every enrolled user's encrypted seed and recovery-code hashes. An uninstall is
   often temporary; irreversible user-data loss is worse than a few orphan declarations, and
   keeping them is what lets a reinstall restore working 2FA for already-enrolled users.
2. **`propertiestool.xml` / `site_properties.xml`** — do not try to remove the
   `enable_two_factor_authentication` element from `user_registration_fields`. That property
   belongs to Plone; this package only appends one element. Removing our element means
   rewriting a list we do not own, which `.claude/CLAUDE.md`'s coexistence constraint
   forbids.

**Do not change anything under `profiles/default/`.**
</scope_boundary>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: PAS-plugin removal end to end — the uninstall import step</name>
  <files>src/imio/googleauthenticator/profiles/uninstall/imio.googleauthenticator.uninstall.txt, src/imio/googleauthenticator/setuphandlers.py, src/imio/googleauthenticator/configure.zcml, src/imio/googleauthenticator/tests/test_setuphandlers.py</files>
  <behavior>
    Thinnest path that touches every layer this task adds — data-file gate, handler, ZCML
    registration — driven by one test written first and run red before the handler exists:

    - `google_auth` is in `acl_users.objectIds()` before the uninstall profile is applied
      (non-vacuity), and absent after.
    - `google_auth` is absent from `pas.plugins.listPluginIds(IAuthenticationPlugin)` after.
    - Applying `imio.googleauthenticator:uninstall` a second time raises nothing and leaves
      the plugin still absent.
    - Re-applying `imio.googleauthenticator:default` puts the plugin back, at index 0 of
      `listPlugins(IAuthenticationPlugin)`.
    - `setupVarious` is unaffected: applying the uninstall profile must not re-run the
      install path, and applying the default profile must not run the uninstall path.
  </behavior>
  <action>
Create the data-file gate `profiles/uninstall/imio.googleauthenticator.uninstall.txt`. Give
it one line of prose mirroring `profiles/default/imio.googleauthenticator.marker.txt`'s
role: its presence, not its content, is what tells `uninstallVarious` this is our uninstall
profile and not some other product's. It must NOT be named
`imio.googleauthenticator.marker.txt`, or `setupVarious` would fire on the uninstall import
and reinstall the plugin the same transaction just removed.

In `setuphandlers.py`, add a module-level helper and a handler beneath the existing
`setupVarious`:

`_remove_plugin(pas, pluginid=PAS_ID)` — return early when `pluginid not in
pas.objectIds()`, otherwise call `pas._delObject(pluginid)`. That single call is the whole
removal: `PluggableAuthService._delOb` (PluggableAuthService.py:454-465) routes to
`plugins.removePluginById(id)`, which deactivates the plugin from every plugin type it is
configured in (Products/PluginRegistry/PluginRegistry.py:320-327) before the object goes.
Write that mechanism into the docstring with the file:line references, so a future reader
does not add a redundant `deactivatePlugin` loop. The `objectIds()` guard is what makes a
second application a no-op instead of an `AttributeError`.

`uninstallVarious(context)` — same shape as `setupVarious`: return immediately when
`context.readDataFile('imio.googleauthenticator.uninstall.txt') is None`, then
`portal = context.getSite()` and `_remove_plugin(portal.acl_users)`. Document in the
docstring why this needs a handler at all: a GenericSetup profile can remove a configlet, a
layer, a utility and a record, but it cannot remove a PAS plugin object, and leaving the
plugin behind means it keeps intercepting every login after the add-on is uninstalled — and
unpickles as `OFS.Uninstalled.Broken` inside `acl_users` if the egg is later removed. State
that this handler does NOT touch memberdata: see the exclusion note this plan's Task 2 pins.

In `configure.zcml`, add a second `genericsetup:importStep` next to the existing one, named
`imio.googleauthenticator.uninstall`, handler
`imio.googleauthenticator.setuphandlers.uninstallVarious`, with a title in the same style as
the install step. It needs no `<depends>` — nothing it does reads the registry.

In `tests/test_setuphandlers.py`, add the test method described in `<behavior>` to the
existing `TestSetupHandlers` class. Write it and run it red before the handler exists. Its
final action must be re-applying `imio.googleauthenticator:default`, following
`test_uninstall_restores_resource_registries`'s discipline — these tests mutate site-wide
registrations, and the layer is per-test `DemoStorage`-isolated but the class's other methods
still expect installed state.
  </action>
  <verify>
    <automated>bin/test -t '!robot' -t 'test_setuphandlers'</automated>
  </verify>
  <done>The new PAS-plugin test method passes; `test_plugin_is_first_authenticator` and `test_reapply_profile_keeps_plugin_first_and_unique` still pass unmodified; the full `bin/test -t '!robot'` suite is green at 132 tests or more, 0 failures, 0 errors.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: the five profile files, and the exclusion pinned by a test</name>
  <files>src/imio/googleauthenticator/profiles/uninstall/componentregistry.xml, src/imio/googleauthenticator/profiles/uninstall/actions.xml, src/imio/googleauthenticator/profiles/uninstall/browserlayer.xml, src/imio/googleauthenticator/profiles/uninstall/controlpanel.xml, src/imio/googleauthenticator/profiles/uninstall/registry.xml, src/imio/googleauthenticator/tests/test_setuphandlers.py</files>
  <behavior>
    Two new test methods. Both start red.

    `test_uninstall_reverses_the_profile_registrations` — five artifacts, each asserted
    present first (non-vacuity), absent after one uninstall, still absent after a second
    (idempotency), and present again after re-applying the default profile (reversibility):

    - the local `IUserDataSchemaProvider` utility;
    - all three `portal_actions/user` entries — `enable_two_factor_authentication`,
      `disable_two_factor_authentication`, `regenerate_recovery_codes`;
    - the `imio.googleauthenticator` browser layer;
    - the `google_authenticator_settings` control-panel configlet;
    - the three `IGoogleAuthenticatorSettings` registry records.

    `test_uninstall_keeps_enrolled_user_data` — the deliberate exclusion:

    - all eight names in `profiles/default/memberdata_properties.xml` are in
      `portal_memberdata.propertyIds()` before the uninstall and still there after;
    - a value written to `two_factor_authentication_secret` on a test user before the
      uninstall reads back byte-identical after it.
  </behavior>
  <action>
Write both test methods first and run them red, then add the five XML files.

**`componentregistry.xml`** — one `<utility>` node under `<utilities>`, carrying
`interface="plone.app.users.userdataschema.IUserDataSchemaProvider"` and `remove="True"`, and
NO `factory` attribute (`components.py:305-312` ignores it on this path, and `_ofs_id` at
`components.py:361-371` derives the OFS id from `interface` alone). Comment it as the
highest-value entry in the directory: an uninstalled add-on whose egg is later removed leaves
this registration unpickling as `OFS.Uninstalled.Broken`.

**`actions.xml`** — mirror `profiles/default/actions.xml`'s nesting exactly: outer
`<object name="portal_actions" meta_type="Plone Actions Tool">`, inner
`<object name="user" meta_type="CMF Action Category">` with no `remove` attribute (the
category belongs to Plone — only its three children are ours), and inside it one
`<object name="..." remove="True"/>` per action id. Comment that the recursion is real, via
`ObjectManagerHelpers` on `ActionCategoryNodeAdapter`
(`CMFCore/exportimport/actions.py:33-34`), and that leaving these behind renders menu entries
pointing at views that no longer resolve.

**`browserlayer.xml`** — `<layers>` with one `<layer name="imio.googleauthenticator"
remove="True"/>`. No `interface` attribute is read on the remove path
(`plone/browserlayer/exportimport.py:60-68`).

**`controlpanel.xml`** — mirror the default file's root element including `purge="False"`,
with one `<configlet action_id="google_authenticator_settings" remove="True"/>` and no child
`<permission>`.

**`registry.xml`** — `<registry>` with one `<records
interface="imio.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings"
remove="true"/>`. It must contain no child nodes at all: `handler.py:322-325` raises
`ValueError` on a removal node carrying values. Comment the operator consequence — this
discards `ska_secret_key`, so any token URL still in flight stops validating and a reinstall
mints a fresh key; enrolled users still log in, because the seed-encryption key is the
`IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` environment variable, not this record.

For the utility assertion, read the site manager's own registrations rather than
`getUtility`/`queryUtility`: `plone.app.users` registers a global default
`IUserDataSchemaProvider`, so a lookup falls back to it and would pass with our local
registration already gone. Use a list comprehension over
`self.portal.getSiteManager().registeredUtilities()` filtered on
`r.provided is IUserDataSchemaProvider` — that iterates local registrations only. A small
helper method on the test class keeps both call sites honest.

For the browser layer, reuse `plone.browserlayer.utils.registered_layers()` and
`imio.googleauthenticator.interfaces.IGoogleAuthenticatorLayer`, the idiom
`tests/test_generic.py:70` already uses. For the configlet, compare against
`[a.id for a in portal_controlpanel.listActions()]`. For the records, use
`getUtility(IRegistry).records` membership on the three
`'{0}.{1}'.format(IGoogleAuthenticatorSettings.__identifier__, field)` names — not
`get_app_settings()`, which raises once the records are gone and would make the absence
assertion an exception rather than a check.

Both methods must end by re-applying `imio.googleauthenticator:default`, for the same
isolation reason as Task 1. `test_uninstall_keeps_enrolled_user_data` needs the seed written
through `user.setMemberProperties`; `.claude/CLAUDE.md` warns that undeclared memberdata
properties are silently popped, so assert the read-back rather than trusting the write.

Python 2.7 only: `.format()`, no f-strings.
  </action>
  <verify>
    <automated>bin/test -t '!robot' -t 'test_setuphandlers'</automated>
  </verify>
  <done>Both new test methods pass; `test_profile_only_registers_resources_it_owns` and `test_uninstall_restores_resource_registries` still pass unmodified; full `bin/test -t '!robot'` green with 0 failures and 0 errors.</done>
</task>

<task type="auto">
  <name>Task 3: prove the new assertions are load-bearing, then document and gate</name>
  <files>src/imio/googleauthenticator/tests/test_setuphandlers.py, CHANGES.rst</files>
  <action>
**Mutation checks.** Each new assertion has to be shown to fail when the thing it claims to
prove is taken away. Run three, each restored byte-identically afterwards and re-run green:

1. Delete the `uninstallVarious` import-step element from `configure.zcml`. Task 1's PAS
   test must go red.
2. Change the `interface` attribute in `profiles/uninstall/componentregistry.xml` to a
   different existing interface's dotted name. The utility group of Task 2's first test must
   go red — this is the check that the OFS-id derivation is actually being exercised, not the
   one most likely to pass for the wrong reason.
3. Remove one of the three `<object ... remove="True"/>` nodes from
   `profiles/uninstall/actions.xml`. The actions group must go red, naming the surviving id.

Record the results as a three-row table (mutation, expected red, observed failure message,
restored) in the task's commit message body. If any mutation stays green, the corresponding
assertion is vacuous — fix the test, do not adjust the mutation.

**Verification gates.** All four must hold before the final commit:

- `bin/test -t '!robot'` — green, 0 failures, 0 errors. Baseline before this task was 132
  tests; the count must go up, not down.
- `bin/test-coverage -t '!robot'` — exit 0, TOTAL 90% or above. `setuphandlers.py` gains new
  lines, so confirm rather than assume; if the new handler drops TOTAL below the gate, the
  shortfall is in this plan's own new code and belongs in this plan's tests.
- `bin/code-analysis` — exit 0, so the commit passes the buildout's pre-commit hook without
  `--no-verify`. Run `bin/isort -rc -y src/` first if the new imports moved anything.
- `test_profile_only_registers_resources_it_owns` — still passes. The five new files are not
  resource registries and its four-file tuple does not name them, so it should be
  unaffected. Confirm by running it, rather than reasoning about it.

**`CHANGES.rst`.** Add one bullet under the existing `1.0.0 (unreleased)` heading, in the
surrounding style, ending with the `[chris-adam]` attribution line. It must state the
operator-visible consequences, not the file list:

- uninstalling now removes the `google_auth` PAS plugin, so 2FA stops being enforced at
  login and no broken object survives in `acl_users` if the egg is later removed;
- it also removes the local user-data-schema utility, the three user menu actions, the
  browser layer, the control-panel configlet and the settings records — including
  `ska_secret_key`, so token URLs still in flight stop validating and a reinstall mints a
  fresh key;
- enrolled users' memberdata is deliberately kept: the property declarations, the encrypted
  seeds and the recovery-code hashes all survive, so a reinstall restores working 2FA
  instead of stranding everyone who had enrolled.
  </action>
  <verify>
    <automated>bin/test -t '!robot' && bin/test-coverage -t '!robot' && bin/code-analysis</automated>
  </verify>
  <done>Three mutation checks each reproduced red and were restored byte-identically, recorded as a table in the commit body; `bin/test -t '!robot'` green with more than 132 tests and 0 failures; `bin/test-coverage -t '!robot'` exit 0 at 90% or above; `bin/code-analysis` exit 0 and the final commit made without `--no-verify`; `CHANGES.rst` carries the new bullet under `1.0.0 (unreleased)` ending with the `[chris-adam]` attribution.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator → `portal_setup` profile import | A Manager applies the uninstall profile; every mutation below happens with `ManagePortal` already held, so this is a correctness boundary, not an authentication one |
| uninstalled add-on → surviving login path | Anything the uninstall fails to remove keeps executing after the operator believes the add-on is gone |
| uninstall → enrolled users' stored secrets | Irreversible data loss is reachable here by an over-broad profile |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-gfr-01 | Denial of Service | `setuphandlers.uninstallVarious` | high | mitigate | The data-file gate keys on `imio.googleauthenticator.uninstall.txt`, which exists only in `profiles/uninstall/`. Without it the step fires on every other product's profile import in the process and deletes `google_auth` from any site that installs anything — the same instance-wide-subscriber class of defect as COEX-10. Task 1 asserts applying the default profile does not run the uninstall path. |
| T-gfr-02 | Tampering | `profiles/uninstall/componentregistry.xml` | medium | mitigate | A wrong `interface` string makes the removal a silent no-op — `components.py:306` skips when `queryUtility` finds nothing, with no error. Mutation check 2 in Task 3 is the control that the string is load-bearing. |
| T-gfr-03 | Denial of Service | `profiles/uninstall/actions.xml`, `controlpanel.xml`, `componentregistry.xml` | high | mitigate | A `purge`-triggering import would wipe every configlet, action and local utility in the site, not just ours. Verified not reachable: all three importers purge only under `environ.shouldPurge()`, the profile is `EXTENSION`, and `applyProfile` passes `purge_old=False`. Nodes stay scoped to our own ids regardless. |
| T-gfr-04 | Repudiation | `memberdata_properties.xml` (excluded) | critical | mitigate | Removing the property declarations would destroy every enrolled user's encrypted seed and recovery-code hashes with no recovery path and no log line. Excluded by design and pinned by `test_uninstall_keeps_enrolled_user_data`, so a future edit that starts deleting user data turns the suite red. |
| T-gfr-05 | Information Disclosure | `profiles/uninstall/registry.xml` | low | accept | Removing the records discards `ska_secret_key`, invalidating token URLs in flight. Accepted: that is the correct direction for a secret at uninstall, and the seed-encryption key is the `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` environment variable, so a reinstall still decrypts existing seeds. Recorded in `CHANGES.rst` as an operator consequence. |
| T-gfr-06 | Elevation of Privilege | `acl_users/google_auth` left in place | critical | mitigate | This is the defect being fixed: today the plugin survives an uninstall and keeps intercepting logins, and unpickles as `OFS.Uninstalled.Broken` once the egg is removed — a `Broken` object in the PAS chain. `_remove_plugin` plus Task 1's absent-from-every-`listPluginIds` assertion closes it. |
| T-gfr-SC | Tampering | npm/pip/cargo installs | high | accept | No package-manager install in this plan. No new dependency, no `setup.py` change; `MANIFEST.in` already covers the new profile files. |
</threat_model>

<verification>
1. `bin/test -t '!robot'` — 0 failures, 0 errors, test count above the 132 baseline.
2. `bin/test-coverage -t '!robot'` — exit 0, TOTAL 90% or above.
3. `bin/code-analysis` — exit 0; the final commit lands without `--no-verify`.
4. `test_profile_only_registers_resources_it_owns` and
   `test_uninstall_restores_resource_registries` pass unmodified.
5. Three mutation checks reproduced red and restored byte-identically, recorded as a table.
6. Nothing under `profiles/default/` changed — `git diff --stat` on that directory is empty.
</verification>

<success_criteria>
- `profiles/uninstall/` holds seven files: the two existing resource-registry files, the five
  new ones, plus the uninstall marker data file.
- Applying `imio.googleauthenticator:uninstall` removes the PAS plugin, the local utility,
  the three user actions, the browser layer, the configlet and the settings records.
- Applying it twice raises nothing and changes nothing.
- Re-applying `imio.googleauthenticator:default` restores all six.
- Memberdata declarations and a stored seed survive the uninstall, pinned by a test.
- All four verification gates pass and `CHANGES.rst` records the operator consequences.
</success_criteria>

<output>
Create `.planning/quick/260806-gfr-widen-the-uninstall-profile-to-reverse-w/260806-gfr-SUMMARY.md` when done.
</output>
