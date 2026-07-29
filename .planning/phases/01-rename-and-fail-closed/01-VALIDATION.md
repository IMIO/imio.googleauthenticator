---
phase: 1
slug: rename-and-fail-closed
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false   # no Wave 0 item has landed — the tree still has src/collective/
created: 2026-07-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `01-RESEARCH.md` `## Validation Architecture`. The Per-Task
> Verification Map is filled from the PLAN files (task IDs are final). The
> sign-off boxes and the `status` / `nyquist_compliant` flags stay
> `/gsd-validate-phase`'s to set.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testing` 3.9.7 via `zc.recipe.testrunner` 1.2.1, driven by `bin/test`; test classes are `unittest2.TestCase` + the local `BaseTest` mixin |
| **Config file** | `base.cfg` `[test]` — no standalone test config; the `-s <package>` filter and eggs are **generated** into `bin/test` from `base.cfg:2 package-name` |
| **Quick run command** | `bin/test -t '!robot' -m imio.googleauthenticator.tests.<module>` |
| **Full suite command** | `make test` (== `bin/test -t '!robot'`) |
| **Estimated runtime** | ~7 s including layer setup (baseline: 8 tests, 0 failures, 0 errors — verified locally) |
| **Layer** | `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` (renamed from `COLLECTIVE_…`). Do **not** refactor layers in this phase — layer isolation is QUAL-05. |

**Hard sequencing constraint:** `bin/test` is a *generated* script. After the `git mv`
commit and before any test can run, `bin/buildout -N -c test-4.3.cfg` must regenerate it.
An `ImportError` between those two points is expected, not a rename bug.

---

## Sampling Rate

- **After every task commit:** `bin/test -t '!robot' -m imio.googleauthenticator.tests.<touched module>`
  — **except** the commit-1 (pure move) and commit-2 (buildout regeneration) tasks, where
  `bin/test` cannot run at all. Those two use the RENAME-07 / RENAME-08 shell assertions instead.
- **After every plan wave:** `make test` **and** the RENAME-06 sdist check (nothing in `bin/test`
  or the pre-commit hook covers the sdist).
- **Before `/gsd-verify-work`:** full suite green, `bin/check-manifest` reviewed, the acceptance
  grep for `collective.googleauthenticator` empty, and success-criterion 1 manually confirmed.
- **Max feedback latency:** ~7 s (full suite), ~2 s (single module).
- **Not a gate:** `bin/code-analysis`. It exits 1 with **318** findings and stays that way until
  Phase 8 (QUAL-06). All commits in this phase use `git commit --no-verify`. No plan task may
  attempt to make it green.

---

## Per-Task Verification Map

Filled from the four PLAN files now that task IDs are final. One row per phase requirement (13),
each pointing at the task that owns it. **Automated Command** holds the clause of that task's
`<automated>` chain that proves *this* requirement, copied verbatim from the plan — the full chain
(which covers several requirements at once) lives in the task named in **Task ID**.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01 T2 | 01-01 | 1 | RENAME-01 | — | N/A | unit | `bin/test -t '!robot' -t test_imio_is_a_pkg_resources_namespace` | ❌ W0 | ⬜ pending |
| 01-01 T1 | 01-01 | 1 | RENAME-02 | — | N/A | integration | `bin/test -t '!robot'` (layer setup loads all ZCML) | ✅ | ⬜ pending |
| 01-02 T1, T2 | 01-02 | 2 | RENAME-03 | T-1-07 | A malformed catalogue registers zero messages behind a single warning line | integration + parse gate | `bin/test -t '!robot' -t test_control_panel_is_translated_nl`; plus, per catalogue, `PGT=$(grep -o "'[^']*python_gettext[^']*'" bin/test \| tr -d "'")` then `PYTHONPATH="$PGT" bin/python -c "import sys;from pythongettext.msgfmt import Msgfmt;Msgfmt(open(sys.argv[1]),sys.argv[1]).get()" <po>` | ❌ W0 | ⬜ pending |
| 01-01 T2 | 01-01 | 1 | RENAME-04 | T-1-03 | Plugin present after `applyProfile`, so 2FA runs on a fresh site | integration | `bin/test -t '!robot' -t test_plugin_is_registered_for_authentication` | ❌ W0 | ⬜ pending |
| 01-01 T2 | 01-01 | 1 | RENAME-05 | — | N/A | integration | `bin/test -t '!robot' -t test_resources_are_registered` | ❌ W0 | ⬜ pending |
| 01-03 T2 | 01-03 | 3 | RENAME-06 | — | N/A | build check | `rm -rf dist && bin/python setup.py sdist > /tmp/sdist.log 2>&1 && tar tzf dist/*.tar.gz > /tmp/sdist.list && grep -q 'locales/imio.googleauthenticator.pot' /tmp/sdist.list && grep -q 'profiles/default/registry.xml' /tmp/sdist.list` | ❌ W0 | ⬜ pending |
| 01-01 T1 | 01-01 | 1 | RENAME-07 | — | N/A | build check | `grep defaults .installed.cfg \| grep -q imio.googleauthenticator` (followed through in 01-02 T1 for `rebuild_i18n.sh` and 01-03 T3 for `.coveragerc` / `cleanup.sh`) | ✅ | ⬜ pending |
| 01-01 T1 | 01-01 | 1 | RENAME-08 | T-1-04 | No duplicate namespace load / ambiguous plugin registration | build check | `test ! -d src/collective && test -z "$(find src -name '*.pyc')"` | ✅ | ⬜ pending |
| 01-01 T1 | 01-01 | 1 | RENAME-09 | — | N/A | integration | `test ! -d src/imio/googleauthenticator/upgrades && bin/test -t '!robot'` | ✅ | ⬜ pending |
| 01-04 T1 | 01-04 | 4 | RENAME-10 | — | Exactly one `meta_type` registered | integration | `grep -q "meta_type = 'iMio Google Authenticator PAS'" src/imio/googleauthenticator/pas_plugin.py && bin/test -t '!robot'` (`z2.installProduct` → `RuntimeError` on duplicate) | ✅ | ⬜ pending |
| 01-04 T2 | 01-04 | 4 | RENAME-11 | T-1-01 | Plugin exception → 500, never a password-only login via `source_users` | integration | `bin/test -t '!robot' -t test_plugin_exception_is_not_swallowed` | ❌ W0 | ⬜ pending |
| 01-01 T2 | 01-01 | 1 | RENAME-12 | T-1-02 | `google_auth` present for `IAuthenticationPlugin` — catches a `Broken` object | integration | `bin/test -t '!robot' -t test_plugin_is_registered_for_authentication` (re-asserted in 01-04 T2 after the `meta_type` change) | ❌ W0 | ⬜ pending |
| 01-03 T1 | 01-03 | 3 | DOC-04 | — | N/A | manual-only + build check | `test "$(bin/python setup.py --long-description \| wc -c)" -gt 5000 && grep -q "1.0.0 (unreleased)" CHANGES.rst` — the prose half is manual (see Manual-Only Verifications) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**`File Exists`** is about the assertion, not the requirement: ✅ means the check runs against the
tree as it stands (the existing 8-test suite, or a shell assertion needing no new test), ❌ W0 means
it depends on a Wave 0 test method that does not exist yet. Every row is `⬜ pending` because no plan
in this phase has executed — the tree still has `src/collective/`.

**Not in this map, by design:** `bin/code-analysis`. See Sampling Rate — 318 findings, exit 1, not a
gate until Phase 8, and every commit here uses `git commit --no-verify`.

---

## Wave 0 Requirements

- [ ] `tests/testing.py` renamed — layer class + 4 constants + the `z2.installProduct` string.
      **Blocks every other test file**; must land before any new test.
- [ ] `tests/test_pas_plugin.py` — add `test_plugin_is_registered_for_authentication`
      (RENAME-04, RENAME-12) and `test_plugin_exception_is_not_swallowed` (RENAME-11).
- [ ] `tests/test_generic.py` — add `test_imio_is_a_pkg_resources_namespace` (RENAME-01),
      `test_control_panel_is_translated_nl` (RENAME-03), `test_resources_are_registered` (RENAME-05).
- [ ] `tests/test_generic.py:28` — path-rename the literal in `test_product_is_installed`
      (leave the *approach* for QUAL-07).
- [ ] Explicit plan task for the sdist assertion — **no test-framework hook exists**;
      `bin/check-manifest` is not wired into `bin/code-analysis`.
- [ ] Framework install: **none needed** — `bin/test` exists and the baseline is green.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `bin/instance` starts and a fresh Plone site installs the add-on with the PAS plugin present | Success criterion 1 | Needs a real Zope process and a browser; no automated equivalent | `bin/instance fg` → create a Plone site with the add-on selected → inspect `acl_users/plugins` in the ZMI for `google_auth` under Authentication |
| `CHANGES.rst` records the rename and the DB-discard instruction | DOC-04 | Prose quality is not assertable | Read `CHANGES.rst`; the automatable half is that `setup.py`'s `long_description` build does not silently fall into its bare `except:` |

---

## Validation Sign-Off

`/gsd-validate-phase` owns these boxes and owns flipping `status` and `nyquist_compliant` in the
frontmatter. The planner does not tick them; an honest `draft` is better than a premature `true`.
What the planner *can* record is the evidence measured against the four PLAN files as they stand —
each note below is a fact about the plans, not a sign-off:

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
      — measured: all 8 tasks across 01-01…01-04 carry an `<automated>` block; no `MISSING` marker
      remains anywhere in the set.
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
      (commit-1 / commit-2 are the known exception — see Sampling Rate)
      — measured: the longest run without a `bin/test` invocation is the pure-move / buildout pair
      inside 01-01 T1, which is the documented exception.
- [ ] Wave 0 covers all MISSING references
      — measured: the six Wave 0 items below name every test method the map marks `❌ W0`.
- [ ] No watch-mode flags
      — measured: no `--watch`, `-w` or equivalent in any `<automated>` block; `bin/test` has no
      watch mode.
- [ ] Feedback latency < 10s
      — measured: ~7 s full suite, ~2 s single module (RESEARCH `## Environment Availability`).
- [ ] `nyquist_compliant: true` set in frontmatter
      — deliberately still `false`. `/gsd-validate-phase` sets it.

**Approval:** pending — `/gsd-validate-phase` has not run. `status: draft`,
`nyquist_compliant: false` and `wave_0_complete: false` are all current and correct as of this
revision; none is the planner's to flip.
