---
phase: 1
slug: rename-and-fail-closed
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `01-RESEARCH.md` `## Validation Architecture`. The Per-Task
> Verification Map is filled by `/gsd-validate-phase` once task IDs exist.

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

*Filled by `/gsd-validate-phase` once PLAN task IDs exist. Requirement → command mapping is
already fixed in `01-RESEARCH.md` `## Validation Architecture` → "Phase Requirements → Test Map".*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | RENAME-01 | — | N/A | unit | `bin/test -t test_imio_is_a_pkg_resources_namespace` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-02 | — | N/A | integration | `bin/test -t '!robot'` (layer setup loads all ZCML) | ✅ | ⬜ pending |
| TBD | TBD | TBD | RENAME-03 | — | N/A | integration | `bin/test -t test_control_panel_is_translated_nl` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-04 | T-1-03 | Plugin present after `applyProfile`, so 2FA runs on a fresh site | integration | `bin/test -t test_plugin_is_registered_for_authentication` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-05 | — | N/A | integration | `bin/test -t test_resources_are_registered` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-06 | — | N/A | build check | `bin/python setup.py sdist && tar tzf dist/*.tar.gz \| grep -E 'locales/.*\.pot\|profiles/default/'` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-07 | — | N/A | build check | `grep defaults .installed.cfg \| grep imio` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-08 | T-1-04 | No duplicate namespace load / ambiguous plugin registration | build check | `test ! -d src/collective && ! find src -name '*.pyc' \| grep -q .` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-09 | — | N/A | integration | `bin/test -t '!robot'` + `test ! -d src/imio/googleauthenticator/upgrades` | ✅ | ⬜ pending |
| TBD | TBD | TBD | RENAME-10 | — | Exactly one `meta_type` registered | integration | `bin/test -t '!robot'` (`z2.installProduct` → `RuntimeError` on duplicate) | ✅ | ⬜ pending |
| TBD | TBD | TBD | RENAME-11 | T-1-01 | Plugin exception → 500, never a password-only login via `source_users` | integration | `bin/test -t test_plugin_exception_is_not_swallowed` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | RENAME-12 | T-1-02 | `google_auth` present for `IAuthenticationPlugin` — catches a `Broken` object | integration | `bin/test -t test_plugin_is_registered_for_authentication` | ❌ W0 | ⬜ pending |
| TBD | TBD | TBD | DOC-04 | — | N/A | manual-only | Read `CHANGES.rst`; `bin/python -c "import setup"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

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

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
      (commit-1 / commit-2 are the known exception — see Sampling Rate)
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
