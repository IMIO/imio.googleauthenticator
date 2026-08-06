# Phase 8: Coverage Instrument and Test Layers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-05
**Phase:** 8-coverage-instrument-and-test-layers
**Areas offered:** Lint debt route (QUAL-06), Coverage shortfall policy (QUAL-04), Where the 90%
gate lives in CI, Test-layer migration scope (QUAL-05/07)
**Areas selected for discussion:** Lint debt route (QUAL-06), Test-layer migration scope (QUAL-05/07)

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Lint debt route (QUAL-06) | 500 findings; 342 mechanically fixable by isort, 100 E251, 13 F401 needing judgement. Fix all, or widen flake8-ignore? | ✓ |
| Coverage shortfall policy (QUAL-04) | What to do if corrected branch coverage lands well under 90% — write tests, pragma, or ratchet | |
| Where the 90% gate lives in CI | CI hands one `test_command` string to a shared reusable workflow | |
| Test-layer migration scope (QUAL-05/07) | All 14 test files vs only the Browser-driven ones; what to do with revealed failures | ✓ |

**Notes:** All four areas were grounded in measurements taken during the discussion rather than in
the project documents, three of which turned out to be wrong: `bin/code-analysis` reports 500
findings (CLAUDE.md says ~40), corrected branch coverage is 84% (the reported figure is 95%), and
no stale `.coverage` file exists yet.

---

## Lint debt route (QUAL-06)

### Question 1 — How do we get `bin/code-analysis` to exit 0?

| Option | Description | Selected |
|--------|-------------|----------|
| Fix all 500 | Run `bin/isort` in place (342 gone), hand-fix the 100 E251 and the 58 others. Largest diff, touches every `.py` file, but the gate then means what it says | ✓ |
| Auto-fix isort, suppress cosmetic codes | isort sweep plus `E251` added to `flake8-ignore`; hand-fix only the 15 real defects. Smallest diff; 100 real findings become permanently invisible | |
| Fix all 500, exclude tests from the gate | Same as fixing everything, plus narrowing `[code-analysis] directory` to exclude `tests/`. Cuts ~140 findings; test code stops being linted | |

**User's choice:** Fix all 500.
**Notes:** Recorded as D-05. The suppression option was the cheapest by a wide margin — one config
line for 100 findings — and was declined. The exclude-tests option would also have removed future
test code from the gate, which is where nearly all new code has landed since Phase 2.

### Question 2 — Where does the sweep sit relative to the test-layer rewrite?

Context given: the isort sweep rewrites the import block of all 14 test files, and QUAL-05 rewrites
`setUp` in the same 14 files.

| Option | Description | Selected |
|--------|-------------|----------|
| Lint sweep last | Test-layer and coverage work first, style sweep as the final plan. Hook goes green once, at the end; commits before it still need `--no-verify` | ✓ |
| Lint sweep first | Hook green for the rest of the phase, but every import the test rewrite adds re-breaks the file until fixed | |
| Split: source now, tests after | Sweep the 12 non-test modules early, `tests/` after the layer rewrite. No overlap, but two style commits and the hook stays red until the second | |

**User's choice:** Lint sweep last.
**Notes:** Recorded as D-06. Accepts continued `--no-verify` for the rest of the phase in exchange
for the two edits never overlapping. Does not change the ROADMAP's same-commit requirement that
`.coveragerc` + `set -e` is the phase's first commit (D-07).

---

## Test-layer migration scope (QUAL-05/07)

Context given, measured during the discussion: 12 of 14 test files call `self._install()` (21 call
sites); six call `transaction.commit()` inside test bodies (`test_challenge` 7×, `test_token` 17×,
`test_reset_bar_code` 7×, plus `test_helpers`, `test_pas_plugin`, `test_setuphandlers`); 12 assign
`self.qi_tool` in `setUp` but only `test_generic.py:55` ever asserts on it.

### Question 1 — Which tests move to the ZSERVER-free FunctionalTesting layer?

| Option | Description | Selected |
|--------|-------------|----------|
| All 14 files, one layer | `IntegrationTesting` stops being used; nobody can silently reintroduce the leak by adding a commit to an "integration" test | |
| Only the seven that commit or browse | Faster, but the split becomes a rule contributors must know, and breaking it fails silently | |
| All 14, and delete the unused ZSERVER layer | Same as the first, and drop `z2.ZSERVER_FIXTURE` from the existing unused `FUNCTIONAL_TESTING` rather than adding a third layer — `ROBOT_TESTING` declares its own | ✓ |

**User's choice:** All 14, and delete the unused ZSERVER layer.
**Notes:** Recorded as D-09 and D-10. Chose the uniform migration over the faster split
specifically because the split's failure mode is silent, and took the extra step of editing the
existing layer definition in place rather than leaving a dead ZSERVER-bearing layer beside a new one.

### Question 2 — What happens to tests that fail once the isolation is fixed?

Context given: the ROADMAP explicitly budgets for this and calls it revealed pre-existing bugs
rather than regressions, but does not settle who fixes them. `test_setuphandlers.py` is the likeliest
casualty — it applies the `:default` profile 8 times and `:uninstall` twice.

| Option | Description | Selected |
|--------|-------------|----------|
| Fix all of them in-phase | Not done until green on the new layer, test-side and code-side both. Honest; phase absorbs unbounded work | ✓ |
| Fix test-side, escalate code-side | Bounded, keeps real bugs visible as findings with a decision point, but splits one red suite across two phases | |
| Record everything, fix nothing | Cheapest, but leaves the build red and blocks the CI coverage gate | |

**User's choice:** Fix all of them in-phase.
**Notes:** Recorded as D-08 with a `costly` reversibility rating — the fallout fixes land inside test
files that the D-05 style sweep later rewrites, so unpicking one afterwards means untangling it from
the sweep commit.

---

## Claude's Discretion

Two offered areas the user declined to discuss. Both were presented back with the decision Claude
intended to take, and the user approved writing the context on that basis rather than revising them.

- **Closing the coverage gap (QUAL-04)** → D-11, D-12. Write real tests for the four weakest
  modules; no `# pragma: no cover` used to reach the number; re-measure once after the coverage 5.5
  pin lands, because the 84% baseline was measured on the installed 4.2.
- **CI enforcement point** → D-13, D-14. Swap the single `test_command` line for
  `bin/test-coverage -t !robot`; buildout parts and pins cleaned up per QUAL-03. Carries the phase's
  one open research item: whether the shared `IMIO/gha-workflows` legacy workflow builds the
  `test-coverage` part before running the command.
- **Mechanical items inside the two discussed areas** → D-15 to D-19: deleting `_install()` and its
  21 call sites, the 11 dead `qi_tool` assignments, what replaces `test_product_is_installed`, how
  the E251 pass is controlled, and correcting the stale figures in `CLAUDE.md` and
  `.planning/codebase/TESTING.md`.

## Deferred Ideas

- Deleting `test_robot.py` / `robot_test.txt` and the ROBOT layer — excluded from every run, needs a
  browser nobody has wired up, but not one of QUAL-01…07.
- MFA-14 (globally-enabled does not enrol pre-existing accounts) — open and unassigned. This phase
  writes tests against the exact code it concerns (`controlpanel.py` 125–158), so the temptation is
  real; it is a behaviour change and stays out.
- WR-01 / WR-02 from `04-REVIEW.md` — unless D-08 fallout surfaces that exact path, in which case
  D-08 governs.
- `profiles/default/site_properties.xml` — dead since Phase 1, tied to no requirement, worth no
  coverage points; stays deferred rather than riding along in the style sweep.
