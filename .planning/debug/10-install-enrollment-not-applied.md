---
status: diagnosed
trigger: "For existing users, nothing is asked and they can log in without setting MFA. (MFA-15 first-install enrollment failure, reported on server.dmsmail site \"PARAF-503\", 2026-08-07)"
created: 2026-08-07T00:00:00Z
updated: 2026-08-07T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED (see Resolution)
test: n/a — investigation complete, diagnose-only mode
expecting: n/a
next_action: none — awaiting fix in a separate phase/plan

## Symptoms

expected: an account that existed before `imio.googleauthenticator` was installed must be
  enrolled (`enable_two_factor_authentication = True`) at install time, when
  `globally_enabled` is on (MFA-15).
actual: pre-existing accounts on the real "PARAF-503" `server.dmsmail` site are not enrolled;
  they log in with no second-factor prompt at all. Accounts created AFTER install ARE
  prompted correctly.
errors: none — this is a silent no-op, not an exception.
reproduction: cannot be reproduced inside this package's own isolated test process (see
  Resolution > why the test passes). Requires the real multi-add-on `server.dmsmail`
  Zope process.
started: first production install of `imio.googleauthenticator` onto a pre-populated
  `imio.dms.mail:examples` site, with `globally_enabled` already on.

## Eliminated

- hypothesis: `is_two_factor_authentication_globally_enabled()` returns `False` during
    install because the `IGoogleAuthenticatorSettings` registry records do not exist yet
    (i.e. the declared `<depends name="plone.app.registry"/>` doesn't actually guarantee
    our own `registry.xml` ran first).
  evidence: `_computeTopologicalSort` (Products/GenericSetup/utils.py:856-905) enforces a
    declared dependency edge unconditionally — a node with edges cannot be inserted into
    `result` until every edge target is already present (`len(edges) > resolved` gate),
    regardless of how many other steps exist or in what order the graph is iterated. This is
    categorically different from the *undirected* case (no edge at all), where placement is
    driven only by the input list order (see Resolution). `plone.app.registry` is itself a
    zero/near-zero-dependency step, so it resolves early in every pass and our step, which
    depends on it, can only land after it — every time, in every process. Confirmed further by
    `test_import_step_declares_registry_dependency` and `test_import_step_ordering` both
    passing, and by `registry.xml` (profiles/default/registry.xml:3) actually declaring the
    `IGoogleAuthenticatorSettings` records that `plone.app.registry` (run against our own
    profile context) imports before `setupVarious` runs.
  timestamp: 2026-08-07

- hypothesis: `api.user.get_users()` does not see accounts created by a different add-on's
    profile (`imio.dms.mail:examples`).
  evidence: users live in `acl_users`/`portal_memberdata`, not in any per-add-on namespace;
    `plone.api.user.get_users()` → `portal_membership.listMembers()` lists every site-local
    member regardless of which install step created the account. The operator's own timeline
    also rules this out structurally: `imio.dms.mail:examples` ran to completion (accounts
    already exist and are usable) in an earlier, separate QuickInstaller transaction, and
    `imio.googleauthenticator` was installed "afterwards" in its own later transaction — there
    is no concurrency between the two profile applications for this scenario. (Existing test
    `test_install_enrolls_no_account_it_cannot_gate` independently confirms `get_users()`'s
    site-local-only scope.)
  timestamp: 2026-08-07

## Evidence

- timestamp: 2026-08-07
  checked: src/imio/googleauthenticator/setuphandlers.py (full file) and configure.zcml
  found: `setupVarious` calls `_setup_secret_key()`, then `_add_plugin(pas)`, then
    `_enroll_existing_users()`. The `imio.googleauthenticator` import step
    (configure.zcml:43-50) declares exactly one dependency:
    `<depends name="plone.app.registry"/>`. No dependency on any memberdata/property step is
    declared anywhere in configure.zcml.
  implication: nothing forces `_enroll_existing_users()` (which calls
    `user.setMemberProperties(mapping={'enable_two_factor_authentication': True})`) to run
    after the step that declares that property on `portal_memberdata`.

- timestamp: 2026-08-07
  checked: `Products.CMFPlone-4.3.20-py2.7.egg/Products/CMFPlone/exportimport/configure.zcml`
    (lines 63-69, 154-158) and `.../exportimport/memberdata_properties.py`
  found: the import step that actually processes `profiles/default/memberdata_properties.xml`
    is a **globally-registered, generic** step named `memberdata-properties`
    (`Products.CMFPlone.exportimport.memberdata_properties.importMemberDataProperties`),
    reused across every add-on's own profile the same way `plone.app.registry` is (it reads
    `context.readDataFile('memberdata_properties.xml')` from whichever profile is the current
    import context). Its own declared dependency is only `<depends name="componentregistry"/>`
    — it does not depend on `imio.googleauthenticator`, and (confirmed above)
    `imio.googleauthenticator` does not depend on it either. Neither step names the other.
  implication: the relative order between `imio.googleauthenticator` (which writes the
    property) and `memberdata-properties` (which declares the property) is **completely
    unconstrained** by GenericSetup's dependency graph. There is no edge between them at all.

- timestamp: 2026-08-07
  checked: `Products.GenericSetup-1.8.11-py2.7-linux-x86_64.egg/Products/GenericSetup/tool.py`
    lines 268-276 (`getSortedImportSteps`) and `Products/GenericSetup/utils.py` lines 856-905
    (`_computeTopologicalSort`) — read in full, not from memory.
  found: `getSortedImportSteps` builds its input as
    `steps = set(_import_step_registry.listSteps()); steps.update(set(self._import_registry.listSteps()))`
    — a Python 2 `set` of step-id strings — then does
    `step_infos = [self.getImportStepMetadata(step) for step in steps]`, iterating the *set*,
    not a sorted or registration-ordered sequence. `_import_step_registry` is the
    module-level, **process-wide** registry populated once by every `genericsetup:importStep`
    ZCML directive loaded anywhere in that Zope process (every egg's ZCML, whether or not the
    corresponding add-on profile has ever been applied to any given site) — its total size is
    a function of how many packages are configured into that specific buildout's ZCML, not of
    anything about the site being installed into.
    `_computeTopologicalSort` then walks this list once per outer pass: a node whose
    dependency edges are ALL already resolved is inserted at `result.insert(after + 1, node)`;
    for a node with **zero edges**, `after` stays `-1`, so it is inserted at **position 0** —
    i.e. every zero/mutually-unconstrained-dependency node gets pushed to the front of
    whatever has been placed so far, in the exact order the *set* happened to hand them to the
    loop. Two nodes with no edge between them (our case) therefore land in an order determined
    entirely by CPython 2.7's `set` iteration order for that specific set of id strings — which
    is a function of the *set's total membership* (hash-table size/bucket layout), not of
    anything semantically meaningful.
  implication: this is exactly the mechanism the test docstring
    (test_setuphandlers.py:129-150) already observed in miniature ("purely by CPython 2.7
    string-hash order... index 51 vs 36 of 52") for a *different* pair
    (`imio.googleauthenticator` vs `plone.app.registry`, before the `<depends>` was added) —
    but for THAT pair the dependency IS now declared, so the ordering is pinned regardless of
    hash order (see Eliminated). For `imio.googleauthenticator` vs `memberdata-properties`,
    no such pin exists, so the "52-step" number from the isolated test fixture is a
    process-specific artifact, not a general guarantee — a differently-sized ZCML load
    (a real `server.dmsmail` buildout, with `imio.dms.mail` and its own dependency tree
    contributing many more `genericsetup:importStep` registrations to the same process-wide
    registry) is not guaranteed to reproduce it.

- timestamp: 2026-08-07
  checked: empirically reproduced `_computeTopologicalSort` (byte-for-byte copy of
    utils.py:856-905, run under the project's pinned Python 2.7.18 interpreter) against a
    minimal graph containing `componentregistry`, `plone.app.registry`,
    `memberdata-properties` (deps: `componentregistry`) and `imio.googleauthenticator` (deps:
    `plone.app.registry`), plus a variable number of extra zero-dependency "other add-on step"
    nodes standing in for the additional `genericsetup:importStep` registrations a larger
    buildout (like `server.dmsmail`) contributes.
  found: with 0-12 extra unrelated steps in the set, `imio.googleauthenticator` sorted AFTER
    `memberdata-properties` (safe). At 20+ extra unrelated steps, the SAME algorithm, on the
    SAME two nodes with the SAME declared dependencies, flipped the order:
    `imio.googleauthenticator` sorted BEFORE `memberdata-properties`.
    ```
    extra unrelated steps=  0 -> imio.googleauthenticator sorts AFTER (safe)
    extra unrelated steps=  8 -> imio.googleauthenticator sorts AFTER (safe)
    extra unrelated steps= 12 -> imio.googleauthenticator sorts AFTER (safe)
    extra unrelated steps= 20 -> imio.googleauthenticator sorts BEFORE (BUG: properties not yet declared)
    extra unrelated steps= 30 -> imio.googleauthenticator sorts BEFORE (BUG: properties not yet declared)
    extra unrelated steps= 50 -> imio.googleauthenticator sorts BEFORE (BUG: properties not yet declared)
    extra unrelated steps= 80 -> imio.googleauthenticator sorts BEFORE (BUG: properties not yet declared)
    ```
  implication: this is not a theoretical concern — the real GenericSetup sort algorithm
    demonstrably flips the relative order of these two specific, undeclared-to-each-other
    steps purely as a function of how many *other*, wholly unrelated steps happen to share the
    same process-wide step registry. A `server.dmsmail` buildout (many more add-ons than this
    package's own isolated `bin/test` process) is exactly the kind of environment where this
    flip is plausible. (Scratch script, not committed:
    `/tmp/claude-1000/-srv-src-imio-googleauthenticator/4753ad15-7804-436f-abf3-4df2a24d25bf/scratchpad/repro_step_order.py`)

- timestamp: 2026-08-07
  checked: `Products.PlonePAS-5.1.1-py2.7-linux-x86_64.egg/Products/PlonePAS/sheet.py`,
    `MutablePropertySheet.setProperties` (lines 112-126) — the method
    `user.setMemberProperties(mapping=...)` ultimately routes to.
  found:
    ```python
    def setProperties(self, user, mapping):
        prop_keys = self._properties.keys()
        prop_update = mapping.copy()
        for key, value in tuple(prop_update.items()):
            if key not in prop_keys:
                prop_update.pop(key)
                continue
            self.validateProperty(key, value)
        self._properties.update(prop_update)
        ...
    ```
  implication: this is the exact, verified mechanism behind the CLAUDE.md constraint
    ("undeclared memberdata properties are silently popped ... with no error"). If
    `enable_two_factor_authentication` is not yet in `self._properties.keys()` (i.e. not yet
    declared on `portal_memberdata` because `memberdata-properties` hasn't run yet for this
    profile), the key is popped from `prop_update` and dropped — no exception, no log line,
    `setProperties` returns normally having done nothing. This is precisely
    `_enroll_existing_users`'s write call
    (`user.setMemberProperties(mapping={'enable_two_factor_authentication': True})`,
    setuphandlers.py:117-119) if `imio.googleauthenticator`'s step ran before
    `memberdata-properties`.

- timestamp: 2026-08-07
  checked: whether a test could catch this within the current test layer
    (testing.py:12-52, `ImiogoogleauthenticatorLayer.setUpPloneSite`)
  found: `setUpPloneSite` applies `imio.googleauthenticator:default` once at layer setup,
    before any test method runs, in the SAME Zope process the whole `bin/test` run uses. By
    the time `test_install_enrolls_every_pre_existing_account_without_a_seed` (or any other
    test) calls `applyProfile` again, `enable_two_factor_authentication` is already a declared
    `portal_memberdata` property from the FIRST application — so the write always succeeds
    from then on, whatever the real step order happened to be on that first pass. No test in
    this suite ever observes a truly pre-install state where the property is undeclared.
    Separately and more fundamentally: `_import_step_registry`'s size is fixed by which eggs'
    ZCML is loaded into THIS package's own isolated `bin/test` process (the test docstring's
    own "52" steps) — this process can never load `imio.dms.mail`'s ZCML (it is not a
    dependency of this package; CLAUDE.md is explicit that this buildout is deliberately
    reduced to only this package's own target), so no test written inside this repository can
    reproduce the actual step-count/order that exists in a real `server.dmsmail` process. A
    test that *would* have caught the underlying gap regardless of hash-order luck is a
    declaration-level one: `assertIn('memberdata-properties', metadata['dependencies'])` on
    the `imio.googleauthenticator` step (mirroring
    `test_import_step_declares_registry_dependency`'s existing pattern for
    `plone.app.registry`) — this assertion would fail today, because
    `configure.zcml` (lines 43-50) declares no such dependency. That gap is exactly the root
    cause.

## Resolution

root_cause: "`imio.googleauthenticator`'s GenericSetup import step
  (src/imio/googleauthenticator/configure.zcml:43-50) declares a dependency on
  `plone.app.registry` but NOT on the `memberdata-properties` step (globally registered by
  Products.CMFPlone, which imports profiles/default/memberdata_properties.xml and is what
  actually declares `enable_two_factor_authentication` — and the other eight MFA properties —
  on `portal_memberdata`). GenericSetup's `_computeTopologicalSort`
  (Products/GenericSetup/utils.py:856-905) only orders steps that share a declared dependency
  edge; two steps with no edge between them are ordered by Python 2.7 `set` iteration order
  over the full, process-wide `_import_step_registry` (Products/GenericSetup/tool.py:268-276),
  which is a function of how many OTHER add-ons' import steps happen to be registered in that
  specific Zope process — not of anything about the site. In this package's own isolated test
  process (52 total registered steps) the order happens to place `imio.googleauthenticator`
  after `memberdata-properties`, so `_enroll_existing_users`'s
  `user.setMemberProperties(mapping={'enable_two_factor_authentication': True})` succeeds. In
  a real `server.dmsmail` buildout, which loads substantially more add-ons' ZCML into the same
  process (empirically reproduced: the order flips once ~20+ more unrelated steps are added to
  the same registry, using the real, unmodified sort algorithm), the same call can silently
  no-op via `MutablePropertySheet.setProperties`'s undeclared-property pop
  (Products/PlonePAS/sheet.py:112-126) — no exception, no log line, and every pre-existing
  account is left unenrolled with no error visible to the operator. This matches the reported
  symptom exactly: pre-existing accounts get no MFA prompt, while accounts created AFTER
  install (which go through `userdataschema.userCreatedHandler`, a live per-user creation
  event handler that runs long after both of these one-time install steps have already
  finished) are enrolled correctly."
fix: "(not applied — diagnosis only, per instructions). What a correct fix needs to change:
  add `<depends name=\"memberdata-properties\"/>` to the `imio.googleauthenticator` import
  step in configure.zcml, alongside the existing `<depends name=\"plone.app.registry\"/>`.
  This closes the same class of gap the `plone.app.registry` dependency already closes for
  the registry records — it converts an undefined, environment-dependent ordering into a
  topologically guaranteed one, exactly as proven safe in the Eliminated section above for the
  registry-records case. A regression test should also be added mirroring
  `test_import_step_declares_registry_dependency`/`test_import_step_ordering`, asserting
  `'memberdata-properties' in metadata['dependencies']` — this is the assertion that is
  missing today and that would have caught this defect regardless of any hash-order luck. Any
  fix should also double check whether `_add_plugin`'s PAS-plugin creation
  (`setuphandlers.py:50-81`) has a similar undeclared-order exposure, though that path does
  not touch memberdata properties and was out of scope for this investigation (a separate
  agent is diagnosing a related failure — do not duplicate that work here)."
verification: "not run — diagnosis only. Fix should be verified per the standard checklist:
  add the dependency, add the declaration+outcome test pair, run
  `bin/test -t test_setuphandlers` and the full suite (`bin/test -t '!robot'`, currently 167
  tests / 0 failures) to confirm no regression, and ideally re-run the empirical
  `_computeTopologicalSort` probe with the new edge added to confirm the order is now pinned
  independent of extra-step count (as already demonstrated for the `plone.app.registry` case)."
files_changed: []
