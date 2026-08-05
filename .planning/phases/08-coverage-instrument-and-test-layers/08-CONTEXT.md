# Phase 8: Coverage Instrument and Test Layers - Context

**Gathered:** 2026-08-05
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase repairs the build's own instruments. Three of them currently report something other
than the truth:

1. **The coverage measurement.** `.coveragerc` is two lines (`[report] include = …`) with no
   `[run] source`, no `omit`, and no `branch = True`, so the reported figure counts test modules
   as covered code and never measures a branch.
2. **The test-suite isolation.** Every test class runs on `IntegrationTesting`, which only aborts
   at teardown, while six test files call `transaction.commit()` inside test bodies — so state
   leaks forward through the layer. `tests/base.py::_install()` compounds it by driving
   `portal_quickinstaller` through a `Browser` inside the layer, committing once per test class.
3. **The lint gate.** `bin/code-analysis` exits 1 on 500 findings, so the buildout's own
   pre-commit hook has trained every commit in phases 1–7 to use `--no-verify`.

Plus the gate that does not exist: `bin/test-coverage` has no `set -e`, so today a failing test
with ≥90% coverage is a **green** build, and CI does not run coverage at all.

Requirements: QUAL-01 … QUAL-07.

**Not this phase:** any change to the second-factor feature itself. Nothing in `helpers.py`,
`pas_plugin.py`, or the token/recovery flows changes behaviour here, with one bounded exception
recorded in D-08 (a defect that the layer fix reveals is fixed here rather than deferred).
MFA-14 (globally-enabled does not enrol pre-existing accounts) is **not** this phase — it is
unassigned and recorded in `07-UAT.md`.

</domain>

<decisions>
## Implementation Decisions

### Measured baselines — replace the numbers in the docs

Every figure below was measured on 2026-08-05, in this working tree, at commit `a83313d`. Three
of them contradict figures currently written in `CLAUDE.md`, `.planning/codebase/TESTING.md`, or
`ROADMAP.md`. **Use these, not the documents.**

- **D-01:** `bin/code-analysis` reports **500 findings**, not the ~40 `CLAUDE.md` claims and not
  the 318 measured in Phase 1. Breakdown: `I001` 247, `E251` 100, `I004` 73, `I003` 22, `F401` 13,
  `E302` 13, `E265` 9, `E261` 6, `E231` 5, `W292` 4, `W291` 3, `F841` 2, `W293` 1, `E305` 1,
  `E271` 1. Only flake8 runs — every other `plone.recipe.codeanalysis` check is off in the current
  `[code-analysis]` config. Reproduce with `bin/code-analysis`.
  - **342 of the 500 (68%) are isort ordering** (`I001` + `I003` + `I004`), mechanically fixable
    by `bin/isort` against the existing `.isort.cfg`.
  - **100 are `E251`** (spaces around keyword equals), in five files only:
    `browser/controlpanel.py` 54, `browser/forms/request_bar_code_reset.py` 28,
    `userdataschema.py` 12, `__init__.py` 4, `browser/disable_two_factor_authentication.py` 2.
    Mostly `zope.schema` field declarations of the form `TextLine(title = _(u"…"))`.
  - **15 are real defects, not style:** 13 `F401` unused imports and 2 `F841` unused locals.
    **None of the 13 is a public-API re-export** — checked individually, so no `# noqa` judgement
    is needed and all 13 can simply be deleted. Two are worth flagging to the planner:
    `testing.py:2` imports `applyProfile` unused (QUAL-05 starts using it), and
    `browser/controlpanel.py:117` imports `disable_two_factor_authentication_for_users` unused
    inside the settings-save handler.

- **D-02:** **Corrected branch coverage is 84%**, not the catastrophic drop the ROADMAP phase note
  budgeted for. Measured against a probe `.coveragerc` carrying exactly what QUAL-01 specifies
  (`[run] source = src/imio/googleauthenticator`, `omit = */tests/*`, `branch = True`):
  **1048 statements, 131 missed; 286 branches, 60 partial; TOTAL 84%.** Today's reported 95% is
  statement-only with all 14 test modules inside the denominator.
  - Reproduce: write that three-line `[run]` section to a scratch file, then
    `bin/coverage run --rcfile=<file> bin/test -t '!robot'` and
    `bin/coverage report --rcfile=<file> -m`. **`COVERAGE_RCFILE` is silently ignored by the
    installed coverage 4.2** — the env var route produces the old broken number and looks like it
    worked. Pass `--rcfile` explicitly.
  - **Caveat the planner must carry:** measured with the currently-installed **coverage 4.2**, not
    the **5.5** QUAL-03 pins. The figure may shift by a point or two after the pin lands. Re-measure
    once, after the pin, before deciding how many tests the 90% gate needs.
  - The gap is concentrated, not diffuse. Weakest modules:
    `browser/disable_two_factor_authentication.py` **40%** (18 stmts, 10 missed),
    `browser/disable_two_factor_authentication_for_all_users.py` **56%**,
    `browser/controlpanel.py` **68%** (lines 125–158, the enable/disable-all-users save handler),
    `browser/forms/reset_bar_code.py` **76%**, `pas_plugin.py` **80%**,
    `browser/forms/request_bar_code_reset.py` **82%**, `helpers.py` **83%**.

- **D-03:** Suite is at **111 tests, 0 failures, 0 errors** in ~57s (`bin/test -t '!robot'`). That
  is the pre-phase control: any failure appearing after the layer change is fallout, and D-08
  governs it.

- **D-04:** There is **no stale `.coverage` file and no `htmlcov/` directory** in the tree, so the
  ROADMAP phase note's "delete any stale 4.x `.coverage` once" has nothing to delete **today**.
  It becomes true the moment anyone runs coverage before the 5.5 pin lands (including the D-02
  reproduction above, which writes its data file into a scratch directory specifically to avoid
  creating one). The planner should still include the deletion, guarded, because the 4.2→5.5 data
  format change is real.

### Lint debt route (QUAL-06) — *discussed*

- **D-05:** **Fix all 500.** `bin/isort` in place for the 342 ordering findings, hand-fix the 100
  `E251`, the 15 real defects, and the ~43 remaining whitespace/blank-line findings.
  **Rejected:** adding `E251` to `flake8-ignore` (it would clear 100 findings for one config line,
  but `E251` is genuine house style and suppressing it makes those findings permanently invisible
  to whoever inherits this package). **Also rejected:** narrowing `[code-analysis] directory` to
  exclude `tests/` (~140 findings would vanish, but test code is where nearly all new code has
  landed since Phase 2, so excluding it guts the gate).

- **D-06:** The sweep is the **last plan in the phase**. Consequence, accepted deliberately: every
  commit before it still needs `--no-verify`, and the pre-commit hook goes green exactly once, at
  the end. Reason: the isort sweep rewrites the import block of all 14 test files and QUAL-05
  rewrites `setUp` in the same 14 files; sequencing the sweep last means the two edits never
  overlap and the sweep covers whatever the test rewrite added.
  **Rejected:** sweep-first (would make the hook green earlier, but every import the test rewrite
  then adds re-breaks the file it touches). **Also rejected:** split sweep — source modules early,
  `tests/` after the layer rewrite (no overlap either, but two style commits and the hook still red
  until the second).

- **D-07:** Because of D-06, the phase's **first** commit is still QUAL-01 + QUAL-02 (`.coveragerc`
  + `set -e`), per the ROADMAP same-commit requirement. D-06 only fixes where the *style* work
  sits, and does not reorder the instrument work.

### Test-layer migration (QUAL-05, QUAL-07) — *discussed*

- **D-08:** **Failures revealed by the layer fix are fixed in-phase — test-side and code-side
  both.** The phase is not complete until the suite is green on the new layer, however many tests
  break and regardless of whether the fault is in the test or in the code it covers.
  Consequence, accepted: the phase absorbs an unbounded amount of work, because a production
  defect surfaced here has to be fixed here. **Rejected:** fixing test-side only and escalating
  code-side defects as findings (bounded, but it splits one red suite across two phases).
  **Also rejected:** record-everything-fix-nothing (leaves the build red, which contradicts the
  phase's purpose and blocks the CI coverage gate from ever being meaningful).
  — **Reversibility:** costly — the fixes land inside test files that the D-05 style sweep then
  rewrites, so unpicking a layer-fallout fix afterwards means untangling it from the sweep commit.

- **D-09:** **All 14 test files move to one ZSERVER-free `FunctionalTesting` layer.**
  `IntegrationTesting` stops being used by this package. **Rejected:** moving only the seven files
  that structurally require it (the six that call `transaction.commit()` in test bodies —
  `test_challenge` 7×, `test_token` 17×, `test_reset_bar_code` 7×, `test_helpers`,
  `test_pas_plugin`, `test_setuphandlers` — plus `test_generic`, whose `z2.Browser` publish commits
  too). That split is faster but becomes a rule contributors must know, and breaking it fails
  **silently**: an added `transaction.commit()` in a test left on `IntegrationTesting` silently
  reintroduces exactly the leak this requirement exists to close.

- **D-10:** The existing `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` is **edited in place** to
  drop `z2.ZSERVER_FIXTURE`, rather than adding a third layer beside it. It is referenced by no
  test today, and `IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING` declares its own `z2.ZSERVER_FIXTURE`,
  so nothing loses a server it needs. One layer definition changes instead of two.

### Claude's Discretion

Two areas the user chose not to discuss, plus the mechanical items inside the two that were
discussed. Decisions taken and recorded so downstream agents do not reopen them.

#### Closing the coverage gap to 90% (QUAL-04)

- **D-11:** The 6 points from 84% to 90% are closed by **writing real tests** for the four weakest
  modules named in D-02, in that order of weakness. **`# pragma: no cover` is not used to close
  the gap**, and `--fail-under` is not set below 90. Rationale: the two `disable_*` views at 40%
  and 56% and the control-panel save handler at 68% are not unreachable defensive branches — they
  are user-facing code paths with no test at all, which is the same class of untested-security-
  adjacent surface the last five phases have been closing. The one place `# pragma: no cover` is
  defensible is a genuinely unreachable `except` arm, and if the planner finds one it must name the
  arm and say why it cannot be driven, not apply the pragma to reach a number.

- **D-12:** Re-measure the baseline **once** after the coverage 5.5 pin lands and before planning
  which tests to write (see the D-02 caveat). Do not tune `.coveragerc` to make 90% appear — that
  is the ROADMAP's own instruction and it stands.

#### Where the 90% gate is enforced in CI

- **D-13:** Change the single `test_command` line in `.github/workflows/package-test.yml` from
  `bin/test -t !robot` to `bin/test-coverage -t !robot`, and let the gate live in the
  `[test-coverage]` template's existing `--fail-under=90`. The template already forwards `$*`, so
  the robot exclusion passes through. **Rejected:** a second CI job (duplicates the whole buildout
  for one number) and a separate post-test coverage step (the reusable workflow takes one command
  string, so a second step is not expressible without forking the shared workflow).
  — **Research item, must be settled before this is implemented:** whether
  `IMIO/gha-workflows/.github/workflows/package-test-legacy.yml@v1` builds all buildout parts —
  and therefore generates `bin/test-coverage` — before running `test_command`. If it runs a
  narrower `bin/buildout install` target, `bin/test-coverage` will not exist in CI and this
  decision needs a different mechanism. **This is the one open unknown in the phase.**

- **D-14:** `[coverage]` and `[test-coverage]` are uncommented in `base.cfg` `parts +=`;
  `createcoverage` is removed from `parts` and its `createcoverage = 1.5` pin is deleted from
  `test-4.3.cfg`; `coverage = 5.5` is pinned (the commented `#coverage = 4.5.1` line is replaced,
  not left beside it). `plone-helper-scripts` stays commented — it is unrelated to this phase.

#### Mechanical items inside the discussed areas

- **D-15:** `tests/base.py::_install()` is **deleted outright**, not left as a no-op, and all 21
  call sites across 12 files go with it. `_get_browser()` and `_login_browser()` stay — six files
  use them. The install moves to a `setUpPloneSite(self, portal)` method on
  `ImiogoogleauthenticatorLayer` calling
  `applyProfile(portal, 'imio.googleauthenticator:default')`.

- **D-16:** The **11 dead `self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')`
  assignments** are deleted. Twelve files hold one; only `test_generic.py:55` ever asserts on it,
  and that assertion is the QUAL-07 target. The three unused `from plone.app.testing import
  quickInstallProduct` imports (`test_generic.py:6`, `test_pas_plugin.py:10`,
  `test_security.py:4`) go with them — they are already three of the 13 `F401` findings.

- **D-17:** QUAL-07 replaces `test_product_is_installed` with three assertions on things this
  package controls, exactly as ROADMAP success criterion 4 words it: the plugin is registered for
  `IAuthenticationPlugin`, the three `IGoogleAuthenticatorSettings` registry records exist, and the
  browser layer is active. The `portal_quickinstaller` assertion is removed, not kept alongside —
  `applyProfile` does not call `installProduct`, so keeping it means a correct change can still
  fail the test.

- **D-18:** The `E251` pass may be done by a mechanical rewrite rather than 100 hand edits, but the
  control is the same either way: `bin/code-analysis` finding-count delta **plus** a green
  111-test suite on the same commit. Note `flake8-isort` 4.0.0 reports isort findings from a diff,
  so per-file before/after counts are not a reliable "did this commit add findings" signal — check
  error **codes**, per the STATE.md blocker note.

- **D-19:** `CLAUDE.md`'s "318 unfixed findings" paragraph and
  `.planning/codebase/TESTING.md`'s coverage/layer sections are corrected in this phase, since both
  become actively wrong the moment the sweep lands. `TESTING.md` is additionally stale on the
  package name (`collective.*`), the test count (8), and the `createcoverage` command.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — the Quality constraint (>90% coverage enforced in CI via the existing
  `[test-coverage]` part), the `coverage == 5.5` / no-PEP-517 dependency constraints, and the
  Lifespan constraint that caps how much any fix here is worth
- `.planning/REQUIREMENTS.md` lines 97–103 — QUAL-01 … QUAL-07 as written
- `.planning/ROADMAP.md` §"Phase 8: Coverage Instrument and Test Layers" — goal, the five success
  criteria, and the four phase notes. **Its "expect a sharp drop" note is superseded by D-02's
  measured 84%** — the drop is from 95% to 84%, not to something unrecoverable
- `.planning/ROADMAP.md` §"Same-Commit Requirements" — the `.coveragerc` + `set -e` row that makes
  QUAL-01 + QUAL-02 the phase's first commit (see D-07)
- `.planning/STATE.md` §"Blockers/Concerns" — the three Phase 8 entries, including the 500-finding
  re-measurement and the `flake8-isort` diff-reporting caveat that D-18 depends on
- `.planning/phases/02-registry-seeding-and-import-step-ordering/02-CONTEXT.md` — Phase 2's
  decisions; D-13's REG-05 double-apply test is one of the `applyProfile` call sites in
  `test_setuphandlers.py` that D-09's layer change affects
- `.planning/phases/07-coexistence-with-imio-dms-mail/07-UAT.md` — MFA-14 and its three candidate
  remedies. **Out of scope here**, but `controlpanel.py` lines 125–158 (the 68%-covered save
  handler D-02 names) is the code MFA-14 concerns, so D-11's new tests will read as adjacent to it

### Configuration under change (read before editing)
- `.coveragerc` — the two-line file QUAL-01 replaces
- `base.cfg` — `parts +=` (lines with `createcoverage`, and the commented `coverage` /
  `test-coverage`), the `[coverage]` and `[test-coverage]` sections, `[code-analysis]`
  (`directory`, `flake8-ignore`, `pre-commit-hook = True`)
- `test-4.3.cfg` line ~68 `#coverage = 4.5.1` and line ~80 `createcoverage = 1.5` — the two pins
  D-14 changes; line ~25 carries the load-bearing comment on why `plone.testing` stays unpinned
- `.github/workflows/package-test.yml` — the single `test_command` line D-13 changes
- `.isort.cfg` — `force_single_line`, `force_alphabetical_sort`, `line_length = 120`; the config
  `bin/isort` will apply across all 26 `.py` files

### Source read during this discussion (file:line, verified 2026-08-05)
- `src/imio/googleauthenticator/testing.py:33-45` — the three layers.
  `IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` at line 38 carries `z2.ZSERVER_FIXTURE` and is
  referenced by **no** test; `ROBOT_TESTING` at line 42 declares its own. This is D-10's edit site
- `src/imio/googleauthenticator/testing.py:16-30` — `ImiogoogleauthenticatorLayer` defines
  `setUpZope` only; there is **no `setUpPloneSite`** today. D-15 adds one
- `src/imio/googleauthenticator/testing.py:2` — `applyProfile` already imported and unused (one of
  the 13 `F401`); D-15 makes the import live
- `src/imio/googleauthenticator/tests/base.py:5-30` — `_install()`, the Browser-driven
  quickinstaller round trip, with its own comment admitting the layer does not apply the profile
  correctly. D-15 deletes it
- `src/imio/googleauthenticator/tests/test_generic.py:55` — `listInstalledProducts()`, the only
  live use of `qi_tool` and D-17's replacement target
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` — `applyProfile(…':default')` at 186,
  232, 249, 613, 672, 685, 697 and `applyProfile(…':uninstall')` at 570, 594. The most
  layer-sensitive file in the suite and the likeliest source of D-08 fallout
- `src/imio/googleauthenticator/browser/controlpanel.py:117` — the unused
  `disable_two_factor_authentication_for_users` import inside the save handler; `125-158` is the
  68%-covered block

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`[coverage]` and `[test-coverage]` buildout sections already exist** in `base.cfg`, fully
  written, merely absent from `parts +=`. QUAL-03 is two uncommented lines plus the `set -e` and
  pin changes — not new recipe authoring.
- **`IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING` already exists** and is unused, so QUAL-05 edits
  a definition rather than adding one (D-10).
- **`applyProfile` is already imported** in `testing.py` and already used nine times in
  `test_setuphandlers.py`, so the install mechanism QUAL-05 moves to is already exercised by the
  suite — including against the `:uninstall` profile Phase 7 added.
- **`bin/isort` exists** in the buildout, driven by the same `.isort.cfg` `flake8-isort` reads, so
  the 342 ordering findings need no new tool.
- **`_get_browser()` / `_login_browser()`** survive D-15 and keep working on the functional layer —
  six test files depend on them.

### Established Patterns
- **Non-vacuity checks are mandatory in this project.** Every phase from 1 to 7 recorded a mutation
  check proving a new test goes red before it is trusted, and restored the source byte-identical
  afterwards (STATE.md records these per plan). D-11's new tests inherit that requirement; so does
  the QUAL-02 deliberately-failing-test proof, which is itself a mutation check with a name.
- **One test method per requirement, grouped by concern** — this repo's own WR-03 precedent, chosen
  over the `plone-write-tests` skill's R5 in plan 07-01. New tests follow it.
- **Fail-closed over convenient.** `_dont_swallow_my_exceptions = True` has been live since Phase 1
  and every later phase preserved it. Nothing in this phase may re-introduce a swallow to make a
  test or a coverage line pass.
- **isort config is `force_single_line` + `force_alphabetical_sort`**, which is why 342 findings
  exist: the codebase was never written to it. The sweep makes every import block one-per-line and
  alphabetical, which is a large but entirely mechanical diff.

### Integration Points
- **`setUpPloneSite` on `ImiogoogleauthenticatorLayer`** is the single new integration point: it is
  where the profile install moves to, and it is what makes all 21 `_install()` call sites deletable.
- **`test_command` in the CI workflow** is the only place the coverage gate can be enforced, and it
  is one string handed to a shared reusable workflow this repo does not own (D-13's open research
  item).
- **The buildout pre-commit hook** (`pre-commit-hook = True` in `[code-analysis]`) is what makes
  QUAL-06 load-bearing rather than cosmetic: the moment findings hit 0, the hook starts working and
  `--no-verify` stops being routine.

</code_context>

<specifics>
## Specific Ideas

- The **84% figure is the headline of this phase** and it changes the phase's shape from what the
  ROADMAP anticipated. The ROADMAP wrote its notes expecting a possibly-unrecoverable drop and told
  the planner not to commit to an intermediate number. That caution is now unnecessary: the target
  is 6 points, the four weakest modules account for most of the gap, and two of them
  (`disable_two_factor_authentication.py` at 40%, `disable_two_factor_authentication_for_all_users.py`
  at 56%) have essentially no tests at all rather than hard-to-reach branches.

- **`COVERAGE_RCFILE` is a trap here.** The installed coverage 4.2 ignores it silently, so a
  measurement made that way returns the *old broken* number while appearing to have used the new
  config. This was hit once during this discussion. Always pass `--rcfile` explicitly, and sanity
  check the output: a branch-enabled report has `Branch` and `BrPart` columns, a non-branch one
  does not.

- **The `set -e` proof must be a real red build, not an inspection.** ROADMAP success criterion 1
  is explicit and the reason is that the current template's failure mode is invisible: `bin/test`
  exits non-zero, the next line runs anyway, and `coverage report --fail-under=90` exits 0, so the
  script exits 0. Nothing in the output says a test failed.

</specifics>

<deferred>
## Deferred Ideas

- **Deleting `test_robot.py` / `robot_test.txt` and `IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING`.**
  They are excluded from every run (`make test` and the CI `test_command` both pass `-t !robot`),
  need a browser nobody has wired up, and are the only remaining reason a ZSERVER fixture exists in
  `testing.py`. Removing them is not any of QUAL-01…07 and is not needed to reach exit 0 or 90%, so
  it stays out. Worth raising at milestone close.

- **MFA-14 — globally-enabled does not enrol pre-existing accounts.** Open and unassigned, recorded
  in `07-UAT.md` with three candidate remedies. This phase will write tests against
  `controlpanel.py` lines 125–158, which is the code MFA-14 concerns, so the temptation to fix it
  while there will be real. It is a behaviour change and does not belong in a coverage phase.

- **WR-01 / WR-02 from `04-REVIEW.md`** — a user with 2FA enabled but no stored seed hits a broken
  encryption key inside `send_2fa_redirect` rather than synchronously in `authenticateCredentials`,
  giving an uncontrolled error page instead of a clean refusal. Still fail-closed, no bypass. The
  named fix is an unconditional `check_encryption_key_is_usable()` call plus a never-enrolled-state
  test. If D-08 fallout surfaces exactly this path, D-08 governs and it is fixed here; otherwise it
  stays deferred rather than being picked up opportunistically for coverage points.

- **`profiles/default/site_properties.xml`** — recorded in Phase 1 as dead and tied to no
  requirement, flagged then as "a Phase 8 observation". Still dead, still tied to no requirement.
  Deleting it is not QUAL-01…07 and it costs no coverage points, so it stays deferred rather than
  riding along in the style sweep.

</deferred>

---

*Phase: 8-Coverage Instrument and Test Layers*
*Context gathered: 2026-08-05*
