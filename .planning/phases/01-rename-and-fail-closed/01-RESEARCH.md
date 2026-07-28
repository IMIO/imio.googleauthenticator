# Phase 1: Rename and Fail-Closed - Research

**Researched:** 2026-07-28
**Domain:** Package/namespace rename of a Plone 4.3 / Python 2.7 PAS add-on (`collective.googleauthenticator` → `imio.googleauthenticator`) + one-line PAS fail-closed hardening
**Confidence:** HIGH

## Summary

This phase adds **no new runtime dependency and no new library**. Everything it needs is either
already installed in this buildout or is a `git mv`. That makes it a *mechanical* phase whose only
real risk is the class of failures where the rename **looks** complete and is not — and every one of
those failures is silent. The project-level research (`.planning/research/PITFALLS.md`) already
enumerated that class; this document's job was to **verify each claim against this working tree and
this interpreter**, correct the ones that were wrong, and find the ones that were missed. Six
corrections and four new findings came out of that, listed under "Corrections to Upstream Research".

The rename surface is now fully enumerated: **61 tracked files** contain the string `collective`,
of which **~50 are real rename targets** and 11 are false positives (`collective.recipe.*`,
`collective.upgrade`, `buildout.plonetest` URLs, the `collective` mr.developer remote alias).
`git clean -xdn src/` shows exactly **31** untracked artefacts to purge (29 `.pyc`, the `.mo`, the
stale `egg-info` directory) — one command covers RENAME-08 *and* D-14. `bin/test` is a **generated**
script that hardcodes `-s collective.googleauthenticator` from `base.cfg:2 package-name`, so the
rename is not testable until `bin/buildout -N` regenerates it: that is a hard sequencing constraint,
not a nicety.

For the fail-closed half, `Products.PluggableAuthService-1.11.3`'s `reraise()` was read directly and
does exactly what PITFALLS P4 claims. The nuance the planner needs is that **the flag is per-plugin
and read off the plugin instance**, so setting it on `GoogleAuthenticatorPlugin` changes nothing
about the credentials-wipe side effect that later plugins depend on. The test that proves it is an
integration test against `acl_users._extractUserIds(request, plugins)` — the exact method that owns
the `except _SWALLOWABLE_PLUGIN_EXCEPTIONS: reraise(auth); continue` block — with a `ValueError`
injected from `pas_plugin.is_whitelisted_client`, a genuine collaborator on line 80 of the method
under test.

**Primary recommendation:** Sequence as five commits — (1) `git mv src/collective src/imio` +
`git clean -xdf src/` + `rm develop-eggs/collective.googleauthenticator.egg-link`, pure move, no
content edits; (2) `bin/buildout -N` prerequisites: `base.cfg` `package-name`/`[code-analysis]
directory` + `setup.py` + `src/imio/__init__.py` (content edits that unblock the test runner);
(3) all remaining dotted-name, profile, marker-file, locales, MANIFEST.in and tooling edits;
(4) `meta_type` + `PAS_TITLE` alone; (5) `_dont_swallow_my_exceptions = True` + its test. Do not
rename `PAS_ID`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Fork provenance and package metadata

- **D-01:** `setup.py` `author` becomes iMio with a team `author_email`; `url` points at
  `https://github.com/IMIO/imio.googleauthenticator`. `AUTHORS.txt` keeps the four upstream names
  (Artur Barseghyan, Kim Chee Leong, Pawel Lewicki, Peter Uittenbroek) under an "Original authors"
  heading and adds iMio. README gains a short "Forked from collective.googleauthenticator" line.
  — **Reversibility:** costly — once published to PyPI the author/url metadata is baked into a
  released sdist; changing it later means a new release, and GPL-2.0 §1 requires the upstream
  notices stay regardless.
- **D-02:** License stays GPL. Not a preference — GPL-2.0 is viral for derivative works, and it
  matches `imio.helpers` (`license="GPL"`). All new code in later phases inherits it.
  — **Reversibility:** one-way — relicensing a GPL-2.0 derivative needs consent from every
  upstream copyright holder.
- **D-03:** The package **is published to PyPI**. This makes RENAME-06 load-bearing rather than
  hygiene: a develop-egg reads `src/` directly, so a broken `MANIFEST.in` is invisible in
  development and only bites someone installing the release.
  — **Reversibility:** one-way — a name published to PyPI cannot be reclaimed or renamed.
- **D-04:** Classifiers corrected: drop `Programming Language :: Python :: 2.6` (asserts support
  that was never tested and contradicts the 2.7 pin), add `Framework :: Plone :: 4.3` and a
  license classifier.
- **D-05:** **No lifespan or deprecation note in published metadata.** Raised that PyPI visitors
  will find this as a maintained-looking Plone 4 MFA package and be surprised by the Keycloak
  retirement; user's explicit decision is to fix classifiers only. Recorded as decided — do not
  re-litigate.
- **D-06:** README screenshots are rehosted in this repo. `docs/_static/` stays, and `setup.py`'s
  image-rewrite hack repoints from
  `github.com/collective/collective.googleauthenticator/raw/master/docs/_static` to the IMIO repo.
  Without this, the PyPI page would embed images served from upstream's branch.
- **D-07:** `LICENSE.txt` moves from `docs/` to the repo root (PyPI and GitHub look there).
  `examples/simple/` is deleted — upstream's demo buildout, superseded by this repo's
  `Makefile` + `test-4.3.cfg` layout. `docs/` is kept, with its dotted-name references renamed.

#### Version and GenericSetup profile version

- **D-08:** `setup.py` version restarts at `1.0.0.dev0` (new package name, new lineage; matches
  `imio.helpers`' `X.Y.Z.dev0` convention for the unreleased head).
- **D-09:** GenericSetup profile version in `profiles/default/metadata.xml` resets `0301` → `1000`,
  giving headroom for future steps (1001, 1002…). Safe because no deployed site has this profile
  registered under the new name, and `upgrades/` is being deleted, so there is no upgrade path to
  preserve.
  — **Reversibility:** costly — once any site has the profile at 1000, lowering it would make GS
  believe upgrade steps are pending.
- **D-10:** `CHANGES.txt` → `CHANGES.rst`, reformatted to the `imio.dms.mail/CHANGES.rst` house
  style: `Changelog` with an `=`-underline matching its title length, version headings as
  `X.Y.Z (unreleased)` / `X.Y.Z (YYYY-MM-DD)` on one line with a matching `-`-underline, entries as
  `- Description.` followed by `  [handle]`. Upstream's `[lgraf]`-style entries already match the
  entry convention. Two references must follow the filename change: `setup.py:13`
  (`open('CHANGES.txt')`) and `MANIFEST.in:1` (`include CHANGES.txt`).
- **D-11:** Upstream changelog history is **retained below** a new `1.0.0 (unreleased)` heading
  rather than archived — consistent with keeping `AUTHORS.txt`, and `long_description` concatenates
  the changelog, so the history is what a PyPI reader sees for context.
- **D-12:** DOC-04's note is written **public-facing**, for anyone who installed
  `collective.googleauthenticator`. Framed as an explicit **non**-migration notice: not a drop-in
  replacement, no migration path provided, existing installs must re-enroll users. This framing is
  deliberate — the user chose the public-facing audience, and an honest non-migration notice serves
  it without promising a path that was never built or tested.

#### Translations

- **D-13:** The i18n domain is renamed to `imio.googleauthenticator`. This is the silent-loss trap:
  the domain is taken from the `locales/` **filenames**, not from `i18n_domain`, so the `.pot` and
  `nl/LC_MESSAGES/*.po` must be `git mv`-ed to the new filenames or the translation disappears with
  no error.
- **D-14:** The tracked `.mo` file
  (`locales/nl/LC_MESSAGES/collective.googleauthenticator.mo`) is removed with `git rm` — it is a
  build artifact keyed to the old domain filename. No `.mo` needs shipping for any language:
  `base.cfg:52` already sets `zope_i18n_compile_mo_files = true`, so Zope compiles `.mo` from `.po`
  at startup.
- **D-15:** `rebuild_i18n.sh` hardcodes `I18NDOMAIN="collective.googleauthenticator"` and must be
  updated. **This is an addition to RENAME-07**, which lists `.coveragerc`, `base.cfg`,
  `cleanup.sh` and `testing.py` but not this script.
- **D-16:** Dutch is kept. It is real work, not a stub — 42 msgids with only 1 empty `msgstr`.
- **D-17:** A **French** translation is added, authored by Claude and submitted for user review.
  Standard vocabulary (`vérification en deux étapes`, `code de vérification`), but iMio house terms
  may differ, so review is expected before merge. This is an accepted expansion of RENAME-03's
  scope — justified because the locales machinery is already open in this phase.
- **D-18:** The defective English msgids are fixed **in source** — `controlpanel.py:45` "ommit",
  a string reading "entering the verification generated by" (missing "code"), and one with a
  trailing space. **And** an `en/LC_MESSAGES/*.po` override is shipped. Flagged that the override
  becomes redundant once msgids are correct (msgids *are* the English source text, and Plone renders
  the msgid when no translation exists), leaving 42 extra strings to keep in sync for no benefit;
  the user chose both. Recorded as decided — implement both, do not re-litigate.
- **D-19:** Fixing the msgids changes them, so `i18ndude sync` will mark roughly 3 Dutch entries
  fuzzy/untranslated. Those Dutch strings must be redone in this phase, via `rebuild_i18n.sh`.

#### Developer migration

- **D-20:** A **new Makefile target** performs the post-rename developer purge: `.pyc` files under
  the old namespace, `src/collective.googleauthenticator.egg-info`, and
  `var/filestorage/Data.fs` + `var/blobstorage`. Nothing existing does this — `make cleanall`
  removes `bin include lib … parts` but not `var/`, not `.pyc`, not `src/*.egg-info`;
  `cleanup.sh` gets the egg-info only. Discoverable via `make help` alongside the other targets.
- **D-21:** The `.pyc` problem is **cleaned once, not prevented**. **This overrides the Phase 1
  roadmap note specifying `PYTHONDONTWRITEBYTECODE=1`.** Residual risk accepted and recorded:
  Phases 3–7 move and delete modules, so a new orphan `.pyc` can appear later and Python 2.7 will
  import it with no `.py` beside it — silently. The new Makefile target is the remedy when that
  happens.
- **D-22:** `cleanup.sh` still hardcodes `rm src/collective.googleauthenticator.egg-info -rf` and
  must be renamed (already covered by RENAME-07).

### Claude's Discretion

Four areas the user chose not to discuss. Decisions taken, recorded so downstream agents do not
re-open them:

- **Rename commit shape:** a pure `git mv` commit first, then content edits in following commits.
  Git's rename detection degrades when content changes in the same commit, and this phase moves
  ~30 files — splitting keeps the diff reviewable. Consistent with the roadmap already isolating
  `meta_type` into its own commit so `registerMultiPlugin`'s duplicate-`meta_type` `RuntimeError`
  stays interpretable as "stale artefact" rather than "rename bug".
- **Fail-closed blast radius and break-glass:** once RENAME-11 stops exceptions being swallowed, a
  bug in the plugin locks out **every in-site user including Site Admins**, rather than degrading
  to password-only. The recovery path is the Zope root admin — the account deliberately excluded
  from MFA as out of scope. That exclusion now does double duty as the break-glass mechanism.
  Decision: accept this, and state it in DOC-01 alongside the out-of-scope rationale, so the
  exclusion reads as intentional rather than as an oversight. Fail-closed is the correct trade
  for an MFA package; a silent 2FA bypass is strictly worse than a loud outage.
- **Failure presentation:** a plain Zope 500 for now, no custom error view. It must not leak
  whether 2FA is enabled for an account, and a bespoke error page is easy to get wrong in that
  respect. Revisit in Phase 3, where fail-closed-on-missing-key lands on the same path and the
  operational need for a clearer message will be concrete.
- **Fail-closed test construction:** inject the failure by raising from a real collaborator the
  plugin calls (not a monkeypatch of `authenticateCredentials` itself), so the test exercises the
  actual PAS call path that `_SWALLOWABLE_PLUGIN_EXCEPTIONS` would otherwise absorb. A monkeypatch
  of the method under test would pass while proving nothing about PAS's behaviour.

### Deferred Ideas (OUT OF SCOPE)

- **Refresh the README screenshots** — the rehosted images (D-06) show the pre-rename UI. Phase 7
  changes the login flow (`id = 'login_form'`, token form inside Plone's stock overlay), so they go
  stale then. Retake after Phase 7, not now.
- **Release tooling** — `zest.releaser` / `fullrelease` setup for whoever cuts the first `1.0.0`.
  Not needed to complete this phase; publication (D-03) only becomes real at release time.
- **Verify `rebuild_i18n.sh`'s i18ndude path** — `I18NDUDE="../../../../../bin/i18ndude"` resolves
  to two levels *above* the repo root when run from the package directory, which looks wrong. The
  depth is unchanged by `collective/` → `imio/`, so the rename neither causes nor fixes it. Worth
  one check when D-15 touches the file.
- **`PYTHONDONTWRITEBYTECODE=1`** — rejected for this phase (D-21). Reconsider if a later phase
  hits an orphan `.pyc`, which is a live risk for Phases 3–7.
- **Custom error view for the fail-closed 500** — deferred to Phase 3, where
  fail-closed-on-missing-key lands on the same code path.
- **French translation of later phases' strings** — recovery codes (Phase 6) and lockout messages
  (Phase 5) add new msgids. Those need French too, in their own phases.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RENAME-01 | Package is `imio.googleauthenticator` on disk, in `setup.py`, in the egg name, with `namespace_packages=['imio']` and a `declare_namespace` `src/imio/__init__.py` | "Rename Surface Inventory" §A; `Code Examples` → namespace declaration byte-copy + the zero-dependency namespace test (Pitfall 3) |
| RENAME-02 | All dotted references updated — `configure.zcml`, `overrides.zcml`, registry interface path, `MessageFactory`, logger names, `IUserDataSchemaProvider` registration | "Rename Surface Inventory" §B/§C — complete file:line list, 50 real targets + 11 false positives named |
| RENAME-03 | Dutch translation survives — `locales/*.pot` and `locales/nl/**` `git mv`-ed, stale `.mo` deleted | Pitfall 1 — `zope.i18n 3.7.4/zcml.py:84-89` read: domain comes from the **`.mo`** filename, `.pot` is never read at runtime; `git clean -xdf src/` already deletes the untracked `.mo` (correction C-2) |
| RENAME-04 | GS marker file renamed alongside the compared string | Pitfall 2 — file is `profiles/default/collective.googleauthenticator.marker.txt`, string at `setuphandlers.py:53`; verification is the RENAME-12 assertion, not a grep |
| RENAME-05 | `++resource++` prefixes in `jsregistry.xml` / `cssregistry.xml` match | "Rename Surface Inventory" §C — plus the **two surfaces RENAME-05 omits**: `browser/configure.zcml:10` (the `resourceDirectory` name that *defines* the prefix) and `profiles/default/skins.xml:4` (`directory="collective.googleauthenticator:skins/…"`) |
| RENAME-06 | `MANIFEST.in`'s hardcoded paths updated, verified by sdist containing `profiles/`, `locales/`, templates | Pitfall 4 — **empirically measured**: 9 paths (not 8); all 11 comma-suffixed patterns on line 5 are dead; the `.pot` is missing from today's sdist; verified replacement template in `Code Examples` |
| RENAME-07 | `.coveragerc`, `base.cfg` (`package-name`, `[code-analysis] directory`), `cleanup.sh`, `testing.py` | "Rename Surface Inventory" §D + **Pitfall 5** — `base.cfg:2` also drives `bin/test`'s `-s` filter and its eggs, so `bin/buildout -N` is a hard prerequisite before any test can run |
| RENAME-08 | 27 orphan `.pyc` + stale `egg-info` purged | Pitfall 6 — measured: **29** `.pyc`, and `git clean -xdf src/` removes all 31 artefacts in one command; the `develop-eggs/` egg-link needs a separate `rm` |
| RENAME-09 | `upgrades/` deleted | `configure.zcml:22` `<include package=".upgrades" />` must go in the same commit or ZCML fails at startup — the one loud failure in this phase |
| RENAME-10 | `meta_type` and `PAS_TITLE` renamed; `PAS_ID` unchanged | "Rename Surface Inventory" §E — 4 sites; `registerMultiPlugin` `RuntimeError` verified in PAS 1.11.3 source |
| RENAME-11 | `_dont_swallow_my_exceptions = True` | `reraise()` read verbatim from PAS 1.11.3; per-plugin semantics confirmed; `Code Examples` → the flag + the test |
| RENAME-12 | Test asserts the plugin is registered for `IAuthenticationPlugin` | `PluginRegistry.listPlugins` read: it filters on `_satisfies()` and logs the miss at **debug** — this is exactly why `objectIds()` (what `test_plugin_is_installed` checks today) cannot catch a Broken object |
| DOC-04 | `CHANGES` records the rename and that existing DBs are discarded, not migrated | D-10/D-11/D-12 + verified PyPI facts: upstream's last release is **0.2.5 (2014-06-20)**; `0.3.0` was never published, so the non-migration notice's real audience is 0.2.5 installs |
</phase_requirements>

---

## Architectural Responsibility Map

This phase changes no tier boundary. The map records which tier *owns* each artefact being renamed,
so the planner can group edits by the mechanism that consumes them rather than by file type.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Package identity on disk / in the egg | Build & packaging (`setup.py`, `MANIFEST.in`, `src/imio/__init__.py`) | — | `pkg_resources`/`setuptools` resolve the distribution and the namespace; nothing in Zope reads these |
| Buildout tooling identity | Build & packaging (`base.cfg` `package-name`, `[code-analysis] directory`, `.coveragerc`, `cleanup.sh`) | — | Consumed by `bin/buildout` at generation time, **not** at runtime — hence the regenerate-before-test constraint |
| ZCML / component registration | Zope configuration (`configure.zcml`, `overrides.zcml`, `browser/configure.zcml`) | — | Read once at process start; failures here are loud |
| GenericSetup profile identity | Persistence / site setup (`profiles/**`, marker file, `metadata.xml`) | Zope configuration (`registerProfile`, `importStep`) | Written into the ZODB on install; a mismatch here fails **silently** (marker file) or orphans records (registry interface path) |
| i18n domain | Zope configuration (`registerTranslations`) | Build & packaging (`MANIFEST.in`, `rebuild_i18n.sh`) | Domain is derived from `locales/**` **filenames** at ZCML time; `i18n_domain=` attributes only set defaults for ids declared in that file |
| PAS plugin identity (`meta_type`, `PAS_TITLE`) | Zope product registration (`registerMultiPlugin`) | Persistence (`plone.app.testing` `snapshotMultiPlugins` keys on `meta_type`) | Process-global registry; duplicate raises at startup |
| PAS plugin **id** (`PAS_ID = 'google_auth'`) | Persistence (`acl_users` object id) | — | **Deliberately unchanged** — renaming it creates a second plugin on any existing ZODB |
| Exception propagation on the authentication path | API / auth tier (`GoogleAuthenticatorPlugin._dont_swallow_my_exceptions`) | Publisher (ZPublisher renders the 500) | The only behaviour change in the phase; read by `PAS.reraise()` off the plugin instance |
| Developer environment purge | Build & tooling (`Makefile` target) | — | Operates on `var/` and untracked artefacts; no code path depends on it |

---

## Standard Stack

### Core

No new library. Every tool this phase needs is already resolved in this buildout.
Versions below were read from `/srv/cache/eggs` on this machine and confirmed present on
`bin/test` / `bin/instance` `sys.path`. `[VERIFIED: executed locally — grep of generated bin/test and bin/instance]`

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `Products.PluggableAuthService` | 1.11.3 | `reraise()` honours `_dont_swallow_my_exceptions`; `registerMultiPlugin` raises on duplicate `meta_type` | The PAS the buildout pins; the flag is PAS's own documented opt-out |
| `Products.PluginRegistry` | **1.11** | `listPlugins()` filters on `_satisfies()` — the RENAME-12 assertion target | Ships with PAS |
| `zope.i18n` | 3.7.4 | `registerTranslations` derives the domain from `locales/<lang>/LC_MESSAGES/<domain>.mo`; `compile_mo_file` compiles `.po`→`.mo` when `po_mtime > mo_mtime` | Plone 4.3's pinned i18n layer |
| `python-gettext` | 1.0 | The compiler `zope.i18n.compile` imports; absent ⇒ `logger.critical` and **zero** translations | Required for D-14 ("ship no `.mo`") to hold — verified present on both runners |
| `i18ndude` (`bin/i18ndude`) | present | `rebuild-pot` + `sync` for D-17/D-18/D-19 | Already a buildout script; `rebuild_i18n.sh` wraps it |
| `check-manifest` (`bin/check-manifest`) | present | Detects the `MANIFEST.in` gaps; **exit 1** today | Already a buildout script — but see correction C-5: it is *not* wired into `bin/code-analysis` |
| `setuptools` | 44.1.1 | `sdist`, `find_packages`, `namespace_packages` | Pinned by `requirements-4.3.txt`; nothing may need PEP 517 |
| `plone.app.testing` / `plone.testing` | 4.2.7 / 4.1.3 | The existing `IntegrationTesting` layer both new tests attach to | Already in use; layer refactor is Phase 8's job |

### Supporting

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `git mv` (directory form) | `git mv src/collective src/imio` moves **both** `__init__.py` and the package subtree in one operation | Commit 1, pure move |
| `git clean -xdf src/` | Removes all 31 untracked artefacts: 29 `.pyc`, the `.mo`, `src/collective.googleauthenticator.egg-info/` | Commit 1, immediately after the `git mv` |
| `bin/buildout -N` | Regenerates `bin/test` (whose `-s` filter and eggs come from `base.cfg` `package-name`) and creates `imio.googleauthenticator.egg-link` / `egg-info` | Mandatory after commit 2, before any `bin/test` run |
| `bin/python setup.py sdist` | RENAME-06's verification; also emits the `no files found matching '*.pot,'` warnings that prove the comma bug | Verification of commit 3 |
| `distutils.filelist.FileList` | Evaluate a `MANIFEST.in` template read-only, without building | Used in this research to verify the replacement template; useful in a test |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Zero-dependency namespace assertion via `pkg_resources._namespace_packages` | Add `imio.helpers` to `install_requires` (research's original) or to `extras_require['test']`, then `import imio.helpers, imio.googleauthenticator` | **Rejected — see Adjudication A-1.** `imio.helpers` 1.3.16 pulls `plone.dexterity`, `plone.app.relationfield`, `plone.app.intid`, `z3c.unconfigure`, `collective.fingerpointing`, `pyjwt`, `cryptography` into a Plone **4.3** pin set. That is a large, unbudgeted resolution risk for a signal the 3-line assertion already gives. |
| `git clean -xdf src/` for the `.mo` | `git rm` the `.mo` (D-14 as written) | **`git rm` fails** — the `.mo` is untracked (`.gitignore:36` is `*.mo`; `git ls-files locales/` lists only `.gitkeep`, `.pot`, `nl/**.po`). Correction C-2. |
| A single `git mv` + edits commit | Separate move and edit commits | Locked by CONTEXT (Claude's Discretion). Also mechanically necessary: `bin/test` cannot run between the move and the `base.cfg` edit + `bin/buildout -N`, so the move commit is untestable by construction and must be small enough to review by eye. |
| Integration test on `acl_users._extractUserIds` for RENAME-11 | Functional testbrowser POST asserting HTTP 500 | Recommend the integration test as **primary** (it is the method that owns the `except`/`reraise`/`continue` block, and it can assert the `source_users` counterfactual directly). A browser-level 500 test is a weaker restatement and needs a functional layer this phase is not refactoring. See Adjudication A-2. |
| `PYTHONDONTWRITEBYTECODE=1` | — | Rejected by D-21. Do not reintroduce. |

**Installation:** none. No `pip install`, no new `install_requires` entry, no new `[versions]` pin.

---

## Package Legitimacy Audit

**This phase installs no external package.** The legitimacy gate is therefore not applicable in its
usual form. Recorded for completeness:

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| *(none added)* | — | — | — | — | — | — |
| `imio.helpers` *(considered, rejected)* | PyPI — `HTTP 200`, latest **1.3.16**, `license = GPL` `[VERIFIED: pypi.org/pypi/imio.helpers/json]` | mature | n/a | github.com/imio/imio.helpers | OK | **NOT ADDED** — see Adjudication A-1 |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

**Name-availability check for D-03 (publish to PyPI):**

| Name | PyPI | Meaning |
|------|------|---------|
| `imio.googleauthenticator` | **HTTP 404** | **Available.** D-03 is unblocked. `[VERIFIED: pypi.org/pypi/imio.googleauthenticator/json → 404]` |
| `imio-googleauthenticator` (normalised) | HTTP 404 | No squatter on the dashed form either |
| `collective.googleauthenticator` | HTTP 200 — latest **0.2.5**, uploaded **2014-06-20**, author `Goldmund, Wyldebeast & Wunderliebe`, license `GPL 2.0` | Upstream. **`0.3.0` was never released to PyPI** — DOC-04's audience is 0.2.5 installs `[VERIFIED: pypi.org JSON API]` |

---

## Architecture Patterns

### System Architecture Diagram

Two independent flows change in this phase. The first is the identity-resolution chain — the reason
a partial rename is silent. The second is the authentication path, where the only behaviour change
lands.

**Flow 1 — how the package name is resolved, and where a miss fails silently**

```
                      setup.py  name= / namespace_packages=['imio']
                          │
                          ├──► bin/buildout ──► develop-eggs/imio.googleauthenticator.egg-link
                          │                     src/imio.googleauthenticator.egg-info/
                          │                       ├─ top_level.txt        = imio
                          │                       ├─ namespace_packages.txt = imio
                          │                       └─ entry_points.txt  [z3c.autoinclude.plugin]
                          │                                                  │
  base.cfg package-name ──┴──► bin/test  defaults = ['-s', '<package-name>']  │
       (base.cfg:2)                      eggs    = <package-name>[test]       │
                                             │                               │
                                             ▼                               ▼
                                    LOUD: ImportError            z3c.autoinclude walks the
                                    if -s name is stale          'plone' entry point of EVERY
                                                                 matching distribution
                                                                          │
   src/imio/__init__.py                                                   ▼
   declare_namespace(__name__) ──► pkg_resources._namespace_packages   configure.zcml loaded
                                   imio.__path__ = [multi-entry]            │
                                                                            ├─► i18n:registerTranslations
                                                                            │     directory="locales"
                                                                            │        │
                                                                            │        ▼
                                                                            │   domain := <basename>.mo
                                                                            │   (compiled from <basename>.po
                                                                            │    when po_mtime > mo_mtime)
                                                                            │        │
                                                                            │   SILENT: wrong basename ⇒
                                                                            │   domain registered with 0 msgs,
                                                                            │   every label falls back to msgid
                                                                            │
                                                                            ├─► genericsetup:registerProfile
                                                                            │     directory="profiles/default"
                                                                            │
                                                                            ├─► genericsetup:importStep
                                                                            │     handler=…setuphandlers.setupVarious
                                                                            │        │
                                                                            │        ▼
                                                                            │   readDataFile('<name>.marker.txt')
                                                                            │        │
                                                                            │   is None ──► return   ◄── SILENT:
                                                                            │        │                   PAS plugin
                                                                            │        ▼                   never added
                                                                            │   _add_plugin(acl_users)
                                                                            │        │
                                                                            │        ▼
                                                                            │   acl_users/google_auth  (PAS_ID — unchanged)
                                                                            │   activatePlugin(IAuthenticationPlugin)
                                                                            │
                                                                            ├─► browser:resourceDirectory name=…
                                                                            │        │
                                                                            │        ▼  ++resource++<name>/…
                                                                            │   must match jsregistry.xml + cssregistry.xml ids
                                                                            │   SILENT: 404 on the asset only
                                                                            │
                                                                            └─► cmf:registerDirectory skins
                                                                                 must match skins.xml directory="<name>:skins/…"

   five:registerPackage initialize=.initialize
        │
        ▼
   registerMultiPlugin(GoogleAuthenticatorPlugin.meta_type)
        │
        └─► meta_type already in MultiPlugins ──► RuntimeError, Zope refuses to start
                                                 ◄── LOUD, and the correct reading is
                                                     "stale egg-info/.pyc", not "rename bug"
```

**Flow 2 — the authentication path, and what `_dont_swallow_my_exceptions` changes**

```
  HTTP request
      │
      ▼
  PluggableAuthService.validate(request)                     PAS 1.11.3:232
      │
      ▼
  _extractUserIds(request, plugins)                          PAS 1.11.3:577
      │
      ├─ for extractor_id, extractor in extractors:          (credentials_cookie_auth,
      │      credentials = extractor.extractCredentials(…)    credentials_basic_auth, …)
      │
      └─ for authenticator_id, auth in authenticators:       ordered; google_auth must be first
             │
             ├─ try: uid_and_info = auth.authenticateCredentials(credentials)
             │
             │      google_auth ──► is_whitelisted_client()  pas_plugin.py:80
             │                  ──► credentials['login']     pas_plugin.py:83
             │                  ──► api.user.get(…)          pas_plugin.py:88
             │                  ──► delegate to every other IAuthenticationPlugin (:105-121)
             │                  ──► WIPE credentials dict    pas_plugin.py:132-133   ◄─ the veto
             │                  ──► setCookie('__ac','')     pas_plugin.py:141
             │                  ──► sign_user_data(…)        pas_plugin.py:144
             │                  ──► response.redirect(…, lock=1); return None
             │
             └─ except (NameError, AttributeError, KeyError, TypeError, ValueError):
                    reraise(auth)          ◄── reads auth._dont_swallow_my_exceptions
                    │                          BEFORE: absent ⇒ return  ⇒ swallowed
                    │                          AFTER:  True   ⇒ bare raise
                    ├── swallowed path ──► logger.debug(...)  ⇒ invisible
                    │                      continue          ⇒ next authenticator = source_users
                    │                                        ⇒ AUTHENTICATED ON PASSWORD ALONE
                    │
                    └── raised path ──────► propagates out of validate()
                                            ⇒ ZPublisher error handling
                                            ⇒ HTTP 500, no session granted
```

The important structural point: **`reraise()` is called once per plugin, with that plugin as the
argument.** The credentials-wipe at `pas_plugin.py:132-133` makes *later* plugins raise `KeyError`
on `credentials['login']`, and those calls pass `source_users` (etc.) to `reraise()`, which has no
flag and therefore keeps swallowing. Setting the flag on `GoogleAuthenticatorPlugin` does not
disturb the veto. `[VERIFIED: Products.PluggableAuthService-1.11.3/PluggableAuthService.py:81, :88-93, :648-664]`

### Recommended Project Structure

```
src/
├── imio/
│   ├── __init__.py                    # declare_namespace ONLY, byte-copied from imio.helpers
│   └── googleauthenticator/
│       ├── __init__.py                # MessageFactory('imio.googleauthenticator') + initialize()
│       ├── configure.zcml             # <include package=".upgrades"/> REMOVED (RENAME-09)
│       ├── overrides.zcml
│       ├── pas_plugin.py              # meta_type + _dont_swallow_my_exceptions
│       ├── setuphandlers.py           # PAS_TITLE renamed, PAS_ID untouched, marker string renamed
│       ├── testing.py                 # layer class + 3 constants + installProduct string
│       ├── browser/
│       │   ├── configure.zcml         # resourceDirectory name= — RENAME-05's hidden half
│       │   └── static/
│       ├── locales/
│       │   ├── imio.googleauthenticator.pot
│       │   ├── nl/LC_MESSAGES/imio.googleauthenticator.po    # git mv, 3 fuzzy after D-19
│       │   ├── fr/LC_MESSAGES/imio.googleauthenticator.po    # NEW (D-17)
│       │   └── en/LC_MESSAGES/imio.googleauthenticator.po    # NEW (D-18)
│       ├── profiles/
│       │   ├── default/
│       │   │   ├── imio.googleauthenticator.marker.txt       # git mv (RENAME-04)
│       │   │   ├── metadata.xml                              # 0301 -> 1000 (D-09)
│       │   │   ├── registry.xml browserlayer.xml componentregistry.xml
│       │   │   ├── controlpanel.xml  jsregistry.xml  cssregistry.xml  skins.xml
│       │   │   ├── actions.xml  memberdata_properties.xml
│       │   │   └── propertiestool.xml  site_properties.xml   # duplicates — see Observation O-3
│       │   └── uninstall/
│       ├── skins/                     # untouched here; Phase 7 owns it
│       ├── tests/
│       ├── www/
│       └── rebuild_i18n.sh            # I18NDOMAIN (D-15) + the depth bug (Observation O-1)
└── (src/collective/ GONE from disk, not just from git)
```

Deleted this phase: `src/imio/googleauthenticator/upgrades/` (RENAME-09), `examples/` (D-07).
Moved: `docs/LICENSE.txt` → `./LICENSE.txt` (D-07). Renamed: `CHANGES.txt` → `CHANGES.rst` (D-10).

### Pattern 1: Pure-move commit, then content edits

**What:** commit 1 contains `git mv` + `git clean` and **zero** content changes.
**When to use:** any rename touching >10 files.
**Why it is load-bearing here, not just tidy:** between the move and the `base.cfg` `package-name`
edit, `bin/test` still hardcodes `-s collective.googleauthenticator` and raises `ImportError`. The
move commit is therefore **untestable by construction**. The only available review mechanism is
`git log --follow` / rename detection, which degrades if content changes in the same commit.

```bash
git mv src/collective src/imio
git clean -xdf src/                                          # 29 .pyc + the .mo + stale egg-info
rm -f develop-eggs/collective.googleauthenticator.egg-link   # NOT under src/; git clean misses it
git commit --no-verify -m "refactor: move src/collective -> src/imio (pure rename)"
```

### Pattern 2: Regenerate before verifying

**What:** `bin/buildout -N` after the `base.cfg` + `setup.py` edits and before any `bin/test`.
**Why:** `base.cfg:2 package-name` feeds three generated artefacts, verified in `.installed.cfg`:

```ini
[test]
defaults = ['-s', 'collective.googleauthenticator', '--auto-color', '--auto-progress']
eggs = Plone
	plone.app.upgrade
	collective.googleauthenticator [test]
	pdbp
```

plus `base.cfg:66 [code-analysis] directory`. `[omelette]` and `[robot]` inherit `${test:eggs}`.
`[VERIFIED: .installed.cfg [test] section, this checkout]`

### Pattern 3: Same-commit coupling for `upgrades/` deletion

`configure.zcml:22` is `<include package=".upgrades" />`. Deleting the directory without deleting
that line is a `ConfigurationError` at ZCML load — loud, but it will abort `bin/test`'s layer setup
with a stack trace that reads like a rename bug. Ship both in one commit.

### Pattern 4: Isolate `meta_type` in its own commit

`registerMultiPlugin` raises `RuntimeError('Meta-type (%s) already available to Add List')` on a
duplicate. `[VERIFIED: PAS-1.11.3/PluggableAuthService.py registerMultiPlugin]` If `meta_type` moves
in the same commit as anything else, that traceback becomes ambiguous. Alone, it is unambiguously
"a stale artefact is also registering". Four sites move together: `pas_plugin.py:59` (`meta_type`),
`setuphandlers.py:10` (`PAS_TITLE`), `www/add_google_authenticator_form.zpt:7` (the ZMI add-form
heading), `README.rst:129` / `docs/index.rst:129` (the quoted `PAS_TITLE`).

### Anti-Patterns to Avoid

- **Renaming `PAS_ID`.** `_add_plugin` returns early only on an **id** match, so a renamed id
  creates a *second* plugin on any existing ZODB while leaving the Broken old one still activated
  for `IAuthenticationPlugin`. `google_auth` is already namespace-neutral. Locked out of scope.
- **Trusting `git grep` as the completion test.** The marker-file trap, the i18n-filename trap and
  the `MANIFEST.in` trap all pass a clean grep. Behavioural assertions (RENAME-12's
  `listPlugins`, an sdist listing, a Dutch label render) are the only evidence.
- **Trusting `pas.objectIds()` as the installedness test.** A `Broken` object still appears in
  `objectIds()`. `test_plugin_is_installed` (`test_pas_plugin.py:29-30`) checks exactly that and is
  therefore blind to the failure RENAME-12 exists to catch. Add the `listPlugins` assertion; do not
  merely rename the existing test.
- **Renaming the `.mo` alongside the `.po`.** `compile_mo_file` only recompiles when
  `po_mtime > mo_mtime`, and `git mv` preserves mtimes — a moved `.mo` is never regenerated and
  silently freezes the old catalogue. Delete it. `[VERIFIED: zope.i18n-3.7.4/compile.py:26-46]`
- **`recursive-include` with comma-separated patterns.** The syntax is space-separated. Every one of
  the 11 comma-suffixed patterns on `MANIFEST.in:5` matches nothing (measured — see Pitfall 4).
- **Assuming `bin/python` can import the package.** `bin/python` is the bare virtualenv interpreter
  with **8 `sys.path` entries and no eggs**. `bin/python -c "import collective.googleauthenticator"`
  fails today, before any rename, so that checklist line proves nothing. `bin/zopepy` would work but
  `[plone-helper-scripts]` is commented out of `base.cfg` `parts` and `bin/zopepy` does not exist.
  Use `bin/test`. `[VERIFIED: executed locally]`

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Purging orphan bytecode + stale egg-info | A `find`/`rm` script | `git clean -xdf src/` | Measured: removes exactly the 31 wanted artefacts (29 `.pyc`, the `.mo`, `src/collective.googleauthenticator.egg-info/`) and nothing else — `git status --porcelain src/` shows no untracked non-ignored files to lose |
| Deleting the stale `.mo` | `git rm` (D-14 as written) | the same `git clean -xdf src/` | The `.mo` is untracked; `git rm` errors |
| Compiling `.mo` from `.po` | `msgfmt` in a Makefile target or a shipped `.mo` | `zope_i18n_compile_mo_files` | Verified set in **both** runners: `parts/instance/etc/zope.conf:12` and `bin/test:282`; and in the deployment target `server.dmsmail/base.cfg:95` |
| Rewriting `.pot`/`.po` headers for `fr`/`en` | Hand-authored PO headers | `bin/i18ndude` via the existing `rebuild_i18n.sh` (D-15) | It already implements the `rebuild-pot` + per-language `sync` loop; hand-written headers get `Plural-Forms` and charset wrong |
| Detecting the `MANIFEST.in` gap | Eyeballing `tar tzf` | `bin/check-manifest` (**exit 1** today) plus one `setup.py sdist` assertion | `check-manifest` already enumerates the exact missing patterns; it is *not* run by `bin/code-analysis`, so it must be an explicit step |
| Evaluating a `MANIFEST.in` change without a build | Building sdists in a loop | `distutils.filelist.FileList().process_template_line()` | Read-only; this is how the replacement template below was verified (+5 files / −1) |
| Proving the `imio` namespace declaration | Adding `imio.helpers` as a dependency | `pkg_resources._namespace_packages` + `namespace_packages.txt` assertions | 3 lines, no dependency, catches all three failure modes — see Adjudication A-1 |
| Proving PAS no longer swallows | A bespoke fake plugin class | Patch a real collaborator (`pas_plugin.is_whitelisted_client`) and call `acl_users._extractUserIds` | That method **is** the `except`/`reraise`/`continue` block; a fake plugin tests your fake |
| Renaming the `imio` namespace boilerplate | Writing it from memory | Byte-copy `/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py` | Mixed declaration styles in one namespace make whichever `imio/__init__.py` is found first win and hide the other subpackage |

**Key insight:** every hand-rolled alternative in this table replaces a *verification* mechanism, and
verification is the entire value of this phase. The rename edits themselves are trivial; what is
hard is knowing they are complete. Spend the effort on the four behavioural assertions
(`listPlugins`, sdist contents, a Dutch label, `_extractUserIds` raising) and let existing tools do
the mechanical work.

---

## Runtime State Inventory

Mandatory for a rename phase. Every category answered explicitly; "None" is stated where nothing was
found, with how that was established.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data (ZODB)** | **None on this machine.** `var/filestorage/` is empty and `var/blobstorage/` is empty — no `Data.fs` exists, so there is nothing to unpickle as `OFS.Uninstalled.Broken` here. `[VERIFIED: executed locally — find var, ls var/filestorage]` Pitfall P3's four Broken-object classes (`acl_users/google_auth`, the `IUserDataSchemaProvider` utility, `IGoogleAuthenticatorLayer`, and `portal_registry` keys prefixed `collective.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings.*`) remain live risks for **other developers' checkouts and any restored staging DB**. | Code/config change only on this machine. For other developers: **data discard**, not migration — the D-20 Makefile target removes `var/filestorage/Data.fs` + `var/blobstorage`; DOC-04 must state DBs are discarded. Add the RENAME-12 `listPlugins` assertion as the permanent regression guard. |
| **Live service config (outside git)** | **None.** This package has no external service integration in Phase 1: no n8n workflow, no Datadog service name, no Tailscale tag, no Cloudflare tunnel. The one external call the package makes today is `chart.googleapis.com` for QR rendering — a stateless GET with no registered configuration — and Phase 3 removes it. `[VERIFIED: git grep of the package for http/https endpoints]` The **deployment** buildout (`server.dmsmail`) will need an egg-name change when it starts consuming this package, but that repo is out of this roadmap's commits and this phase does not yet make the package a dependency of it. | None this phase. Note for the milestone: `server.dmsmail` must reference `imio.googleauthenticator`, not the old name, whenever it adopts the package. |
| **OS-registered state** | **None.** No Windows Task Scheduler entry, no pm2 saved process list, no launchd plist, no systemd unit references this package. The only process-level artefact is `parts/instance/etc/zope.conf`, which is **buildout-generated** and regenerated by `bin/buildout`. `[VERIFIED: zope.conf is under parts/, which .gitignore:14 ignores]` | None — regeneration is automatic. Do not hand-edit `parts/`. |
| **Secrets / env vars** | **None renamed.** The only env vars in play are `PYTHONBREAKPOINT` (`base.cfg:41,49`) and `zope_i18n_compile_mo_files` (`zope.conf:12`, `bin/test:282`) — neither contains the package name. `ska_secret_key` is a `plone.registry` record, not an env var, and Phase 2 owns it. The encryption-key env var is Phase 3. `[VERIFIED: grep environment-vars base.cfg; sed zope.conf <environment>]` | None. |
| **Build artefacts / installed packages** | **Four, all stale after the source rename.** (1) `src/collective.googleauthenticator.egg-info/` — untracked; `top_level.txt=collective`, `namespace_packages.txt=collective`, and an `entry_points.txt` declaring `[z3c.autoinclude.plugin] target = plone`, so it makes the *old* distribution's ZCML autoincludable. (2) `develop-eggs/collective.googleauthenticator.egg-link` → `/srv/src/imio.googleauthenticator/src`. (3) **29** orphan `.pyc` files under `src/collective/` including `src/collective/__init__.pyc` (the `declare_namespace` boilerplate) — Python 2.7 imports an orphan `.pyc` with no `.py` beside it. (4) The generated `bin/test`, `bin/instance`, `bin/omelette`, `bin/robot`, `bin/code-analysis*` scripts, which embed the old egg path and the old `-s` filter. `[VERIFIED: executed locally — git clean -xdn src/ (31 items), ls develop-eggs/, .installed.cfg]` | (1)+(3): `git clean -xdf src/`. (2): explicit `rm -f develop-eggs/collective.googleauthenticator.egg-link` — `develop-eggs/` is outside `src/`, so `git clean -xdf src/` **does not** reach it. (4): `bin/buildout -N` after the `base.cfg`/`setup.py` edits, **before** any `bin/test`. |

**The canonical question — after every file in the repo is updated, what still has the old string
cached, stored or registered?** On this machine: the four build artefacts above, and nothing else.
No database, no external service, no OS registration, no secret. That is an unusually clean answer,
and it is the direct consequence of the package being undeployed — which is precisely why the
roadmap put this phase first.

---

## Common Pitfalls

### Pitfall 1: The i18n domain comes from the `.mo` filename, not the `.po` and not `i18n_domain`

**What goes wrong:** renaming `MessageFactory('collective.googleauthenticator')` in the eleven
modules that declare it, plus the five `i18n_domain=` / `i18n:domain=` attributes, without renaming
`locales/**` leaves a `collective.googleauthenticator` domain nothing looks up and an
`imio.googleauthenticator` domain with zero messages. Every label falls back to its English msgid.
Nothing errors.

**Why it happens — the exact mechanism**, read from `zope.i18n-3.7.4/zcml.py:65-102`:

```python
def registerTranslations(_context, directory):
    for language in os.listdir(path):
        lc_messages_path = os.path.join(path, language, 'LC_MESSAGES')
        if os.path.isdir(lc_messages_path):
            if config.COMPILE_MO_FILES:
                for domain_file in os.listdir(lc_messages_path):
                    if domain_file.endswith('.po'):
                        compile_mo_file(domain_file[:-3], lc_messages_path)
            for domain_file in os.listdir(lc_messages_path):
                if domain_file.endswith('.mo'):          # <-- the .mo, not the .po
                    domain = domain_file[:-3]            # <-- domain := basename
```

Three consequences the planner must design around, none of them in the upstream research:

1. **The registration loop iterates `.mo` files only.** A `.po` with no compiled `.mo` registers
   *nothing*. D-14 ("ship no `.mo`") therefore depends entirely on `zope_i18n_compile_mo_files`
   and on `python-gettext` being importable. Both verified present (Standard Stack), and
   `server.dmsmail/base.cfg:95` sets the flag for the deployment target — so D-14 is safe, but it
   is safe *because of those three facts*, not automatically.
2. **`compile_mo_file` returns silently on any failure** — `except (IOError, OSError, PoSyntaxError): logger.warn(...)`
   — and `HAS_PYTHON_GETTEXT = False` produces only `logger.critical`. A PO syntax error in the new
   French file (D-17) costs the entire language with one `warn` line.
   `[VERIFIED: zope.i18n-3.7.4/compile.py:16-46]`
3. **The `.pot` is never read at runtime.** It matters only to `i18ndude sync`. So the `.pot` being
   absent from today's sdist (Pitfall 4) breaks downstream *contributors*, not end users — worth
   knowing so the sdist assertion is written for the right reason.

**How to avoid:** `git mv` the `.pot` and `nl/LC_MESSAGES/*.po` in the same commit as the
`MessageFactory` change; let `git clean -xdf src/` delete the untracked `.mo`; update
`rebuild_i18n.sh`'s `I18NDOMAIN` (D-15).

**Warning signs:**
```bash
find src -name 'collective.googleauthenticator.*'   # must be empty
ls src/imio/googleauthenticator/locales/            # imio.googleauthenticator.pot + en/ fr/ nl/
```
Behavioural: render the control panel with `?set_language=nl` and confirm a Dutch label. Note
`bin/code-analysis-find-untranslated` reports **SKIP** and is *not* wired into `bin/code-analysis`
(correction C-5) — it cannot serve as this check.

---

### Pitfall 2: `setupVarious` returns silently when the marker file name does not match

**What goes wrong:** `setuphandlers.py:53` is
`if context.readDataFile('collective.googleauthenticator.marker.txt') is None: return`.
The file is `profiles/default/collective.googleauthenticator.marker.txt`. Rename the string without
renaming the file (or vice versa) and the handler returns before `_add_plugin(pas)` — **the PAS
plugin is never added, and no error is raised.** The add-on still appears installed: the browser
layer registers, the control panel registers, the registry records are created. Only the second
factor is missing.

**Why it happens:** it is a two-file invariant with no compiler and no test. The string and the
filename live in different directories and are never compared by anything.

**How to avoid:** `git mv` the marker file and edit the string in the same commit, and make
RENAME-12's assertion the acceptance test — `listPlugins(IAuthenticationPlugin)` is empty of
`google_auth` in exactly this failure mode.

**Warning signs:** the RENAME-12 test. A grep cannot see this; both halves grep clean when only one
was changed.

---

### Pitfall 3: The `imio` namespace has three ways to be wrong and none of them raise

**What goes wrong:** `src/imio/__init__.py` written as `pkgutil.extend_path`, or left empty, or
`namespace_packages=['imio']` omitted from `setup.py`. Whichever `imio/__init__.py` is found first on
`sys.path` then wins and the other `imio.*` subpackage becomes invisible. On a box with only this
package installed, all three mistakes look fine.

**The mechanism, executed on this machine** against the current `collective` namespace:

```
_namespace_packages: [None, 'Products', 'Shared', 'Shared.DC', 'collective', 'five',
                      'plone', 'plone.app', 'plone.directives', 'z3c', 'zc', 'zope', 'zope.app']
collective.__path__: ['/srv/src/imio.googleauthenticator/src/collective',
                      '/srv/cache/eggs/collective.z3cform.datetimewidget-1.2.9-py2.7.egg/collective',
                      '/srv/cache/eggs/collective.monkeypatcher-1.2.1-py2.7.egg/collective']
get_distribution('collective.googleauthenticator')
    .get_metadata('namespace_packages.txt').split() == ['collective']
```
`[VERIFIED: executed locally with bin/test's sys.path injected]`

**How to avoid:** byte-copy the declaration and assert the mechanism (see `Code Examples`). The
declaration to copy, verbatim from `/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py`:

```python
# -*- coding: utf-8 -*-
__import__('pkg_resources').declare_namespace(__name__)
```

Note the current `src/collective/__init__.py` has the `declare_namespace` line but **no coding
cookie** — copy `imio.helpers`' version including the cookie so the two `imio.*` eggs are
byte-identical.

**Warning signs:** the 3-line assertion in `Code Examples`. Do **not** use
`bin/python -c "import imio.helpers, imio.googleauthenticator"` — `bin/python` has no eggs on its
path and the command fails regardless (Anti-Patterns).

---

### Pitfall 4: `MANIFEST.in` — 9 stale paths, 11 dead patterns, and the `.pot` already missing

**What goes wrong:** measured on the current tree, `MANIFEST.in:5` is

```
recursive-include src *.zcml, *.pot, *.po, *.css, *.js, *.xml, *.txt, *.cpt, *.pt, *.metadata, *.zpt, *.sh
```

`recursive-include` takes **space-separated** patterns. The commas become part of each glob, so
`*.zcml,`, `*.pot,` … `*.zpt,` all match nothing — only the trailing comma-free `*.sh` works.
Building the sdist emits the proof:

```
warning: no files found matching '*.zcml,' under directory 'src'
warning: no files found matching '*.pot,' under directory 'src'
...
warning: no files found matching 'CONTRIBUTORS.txt'
```

Lines 6–14 partly rescue it, but not completely. **Today's sdist is already missing**
`locales/collective.googleauthenticator.pot`, `locales/.gitkeep`, `tests/robot_test.txt`,
`upgrades/configure.zcml` and `upgrades/profiles/0301/actions.xml`.
`[VERIFIED: executed locally — bin/python setup.py sdist + tarfile diff against src/]`

Three further facts the requirement text does not capture:

- It is **9** hardcoded `src/collective/…` paths (lines 6–14), not 8.
- `MANIFEST.in:2` is `include CONTRIBUTORS.txt`, and that file **does not exist** in this repo.
- `MANIFEST.in:6` is scoped to `locales/nl`. D-17 adds `fr/` and D-18 adds `en/`, so a
  path-only rename leaves both **new languages out of the sdist** — a silent release-only failure of
  exactly the kind RENAME-06 exists to prevent.

**How to avoid:** the replacement template below, verified with `distutils.filelist.FileList`
to capture the current tree's non-`.py` files **+5 / −1** relative to today (gains the `.pot`,
`.gitkeep`, `robot_test.txt` and the two `upgrades/` files that are being deleted anyway; loses the
`.mo`, which is intended).

**Warning signs:**
```bash
bin/check-manifest ; echo $?        # currently 1; must be 0 or its remaining diffs justified
bin/python setup.py sdist 2>&1 | grep "no files found"   # must be silent
tar tzf dist/*.tar.gz | grep -E 'locales/.*\.pot|locales/(nl|fr|en)/|profiles/|www/|browser/static/'
```

---

### Pitfall 5: `bin/test` is generated from `base.cfg` `package-name` — the rename is untestable until buildout re-runs

**What goes wrong:** `bin/test`'s test-search filter and its egg list are generated, not read at
run time:

```ini
[test]
defaults = ['-s', 'collective.googleauthenticator', '--auto-color', '--auto-progress']
eggs = Plone
	plone.app.upgrade
	collective.googleauthenticator [test]
```

After `git mv`, that filter names a module that no longer exists. `bin/test` then dies with
`ImportError: No module named collective.googleauthenticator` from
`zope/testing/testrunner/find.py:335`. `[VERIFIED: executed locally]`

**Why it matters:** this is the *good* case — it is loud. The planner's mistake to avoid is
scheduling a "run the tests" verification step against the move commit, concluding the rename broke
something, and debugging in the wrong place. The correct reading is "regenerate first".

**How to avoid:** put `base.cfg:2 package-name`, `base.cfg:66 [code-analysis] directory`,
`setup.py` (`name`, `namespace_packages`, `packages`), and `src/imio/__init__.py` in commit 2, then
`bin/buildout -N`, and only then start asserting. Note `bin/buildout -N` **adds** the new egg-link
and egg-info without removing the old ones — hence the explicit `rm` in commit 1.

**Warning signs:**
```bash
grep -n "defaults" .installed.cfg | grep googleauthenticator   # must say imio.*
ls develop-eggs/ | grep googleauthenticator                    # exactly one line
ls -d src/*.egg-info                                           # exactly one, imio.*
```

---

### Pitfall 6: 29 orphan `.pyc`, and `git clean -xdf src/` does not reach `develop-eggs/`

**What goes wrong:** `.gitignore:1` is `*.py[cod]`, so `git mv src/collective src/imio` leaves the
entire compiled tree behind under `src/collective/`, `src/collective/__init__.pyc` included. Python
2.7 imports an orphan `.pyc` with no `.py` beside it, so every dotted name you forget to rename keeps
resolving against dead bytecode: `bin/test` green, fresh clone broken.

Two measured corrections to the requirement text: it is **29** `.pyc` files, not 27, and one
command covers all of it:

```
$ git clean -xdn src/ | wc -l
31
$ git clean -xdn src/
Would remove src/collective.googleauthenticator.egg-info/
Would remove src/collective/__init__.pyc
… 28 more .pyc …
Would remove src/collective/googleauthenticator/locales/nl/LC_MESSAGES/collective.googleauthenticator.mo
```
`[VERIFIED: executed locally]` `git status --porcelain src/` is clean, so nothing wanted is at risk.

**The trap inside the fix:** `develop-eggs/` is at the repo root, not under `src/`.
`git clean -xdf src/` leaves `develop-eggs/collective.googleauthenticator.egg-link` in place, and
that egg-link plus the new one gives `pkg_resources` two distributions pointing at the same `src/`
tree — `z3c.autoinclude` then walks the `plone` entry point of both and loads the old ZCML.

**Warning signs:**
```bash
test ! -d src/collective                    # must pass — gone from DISK, not just from git
find src -name '*.pyc'                      # must be empty
ls develop-eggs/ | grep -c googleauthenticator   # must be 1
```
Loud secondary detector: if both distributions initialize, `registerMultiPlugin` raises
`RuntimeError('Meta-type (...) already available to Add List')` and **Zope refuses to start**. Read
that traceback as "stale artefact", never as "rename bug" — which is the whole reason `meta_type`
gets its own commit (Pattern 4).

---

### Pitfall 7: PAS swallows five exception types and falls through to `source_users`

**What goes wrong:** `PluggableAuthService.py:81`

```python
_SWALLOWABLE_PLUGIN_EXCEPTIONS = ( NameError, AttributeError, KeyError, TypeError, ValueError )
```

and `_extractUserIds` (~:648):

```python
except _SWALLOWABLE_PLUGIN_EXCEPTIONS:
    reraise( auth )
    msg = 'AuthenticationPlugin %s error' % ( authenticator_id, )
    logger.debug( msg, exc_info=True )
    continue
```

with `reraise` at :88-93:

```python
def reraise(plugin):
    try:
        doreraise = plugin._dont_swallow_my_exceptions
    except AttributeError:
        return
    if doreraise:
        raise
```

`logger.debug` is invisible at Plone's default level, and `continue` reaches `source_users`, which
authenticates on password alone. Any `ValueError`/`TypeError`/`KeyError`/`AttributeError`/`NameError`
anywhere in `authenticateCredentials` is therefore a **silent, total, untraceable 2FA bypass**.
Note `UnboundLocalError` is a `NameError` subclass, so the existing `user_setup.py:96` bug is in this
class too. `[VERIFIED: Products.PluggableAuthService-1.11.3 source, read directly]`

**Why it happens:** the plugin contract is "return `None` if not competent", and PAS cannot
distinguish "not competent" from "crashed".

**How to avoid:** one class attribute. Three properties of the mechanism the planner should know:

1. **The flag is read off the plugin instance passed to `reraise()`.** Setting it on
   `GoogleAuthenticatorPlugin` affects only our plugin. The credentials-wipe at
   `pas_plugin.py:132-133` deliberately makes *later* plugins raise `KeyError`; those `reraise()`
   calls receive `source_users` (etc.), which has no flag, so the veto keeps working unchanged.
2. **`raise` is bare** — it re-raises the live exception with its original traceback. Python 2 does
   not clear `sys.exc_info()` on leaving an `except` block, so this works from inside `reraise`'s own
   `try/except AttributeError`.
3. **The plugin's own inner delegation loop is untouched.** `pas_plugin.py:113-117` catches the
   swallowable set from *other* plugins and calls `reraise(authplugin)`. Our flag does not apply
   there. Leave that loop alone in this phase; Phase 4 owns the boundary rework.

**Warning signs:** the test in `Code Examples`. Assert both directions — the exception propagates
**and** `source_users` did not silently produce a user id.

---

### Pitfall 8: `configure.zcml:22` still includes `.upgrades` after RENAME-09 deletes it

**What goes wrong:** `<include package=".upgrades" />` against a deleted package is a ZCML
`ConfigurationError` at process/layer start. Loud, but it surfaces during `bin/test`'s layer setup
as a stack trace that reads like a rename failure.

**How to avoid:** delete the directory and the `<include>` line in one commit. Four other references
go with it, all inside `upgrades/`: `upgrades/configure.zcml` (handler, `profile=`, title),
`upgrades/to0301.py` (`profile-collective.googleauthenticator.upgrades:0301`), and
`upgrades/profiles/0301/actions.xml`. Also drop `*/upgrades/*` from any `.coveragerc` `omit` you
were about to write — the directory will not exist.

---

## Code Examples

### RENAME-01 — the namespace declaration and its zero-dependency assertion

```python
# src/imio/__init__.py
# Source: byte-copy of /srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py
# -*- coding: utf-8 -*-
__import__('pkg_resources').declare_namespace(__name__)
```

```python
# setup.py (excerpt)
    name='imio.googleauthenticator',
    version='1.0.0.dev0',                      # D-08
    packages=find_packages('src'),
    package_dir={'': 'src'},
    namespace_packages=['imio'],               # RENAME-01
    license='GPL',                             # D-02, matches imio.helpers
    url='https://github.com/IMIO/imio.googleauthenticator',   # D-01
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Plone',
        'Framework :: Plone :: 4.3',                                        # D-04
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)', # D-04
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',            # 2.6 dropped, D-04
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
```

```python
# src/imio/googleauthenticator/tests/test_generic.py (add)
# Mechanism verified by execution against the current 'collective' namespace.
def test_imio_is_a_pkg_resources_namespace(self):
    """Catches: empty src/imio/__init__.py, a pkgutil-style declaration, and a
    missing namespace_packages=['imio'] in setup.py. No new dependency needed."""
    import pkg_resources
    import imio.googleauthenticator  # noqa
    self.assertIn('imio', pkg_resources._namespace_packages)
    dist = pkg_resources.get_distribution('imio.googleauthenticator')
    self.assertEqual(
        dist.get_metadata('namespace_packages.txt').split(), ['imio'])
```

### RENAME-06 — the verified `MANIFEST.in` replacement

Measured with `distutils.filelist.FileList` against the current tree: **+5 files / −1** versus
today (gains the `.pot`, `locales/.gitkeep`, `tests/robot_test.txt` and the two `upgrades/` files
being deleted; loses the `.mo`). Note the fix to line 5 is literally *delete the commas*.

```
include *.rst
include *.txt
include LICENSE.txt
recursive-include docs *
recursive-include src *.zcml *.pot *.po *.xml *.txt *.css *.js *.pt *.cpt *.zpt *.metadata *.html *.sh
recursive-include src/imio/googleauthenticator/locales *
recursive-include src/imio/googleauthenticator/profiles *
recursive-include src/imio/googleauthenticator/skins *
recursive-include src/imio/googleauthenticator/browser/static *
recursive-include src/imio/googleauthenticator/www *
global-exclude *.pyc
global-exclude *.mo
```

Changes versus the current file: commas → spaces on the pattern line; `locales/nl` → `locales` so
D-17's `fr/` and D-18's `en/` ship; `include CONTRIBUTORS.txt` dropped (file does not exist);
`include CHANGES.txt` → covered by `include *.rst` after D-10 renames it to `CHANGES.rst`;
`LICENSE.txt` added (D-07 moves it to the root); `global-exclude *.mo` so a locally compiled
catalogue never leaks into a release.

Read-only verification, no build required:

```python
from distutils.filelist import FileList
fl = FileList(); fl.findall('.')
for line in open('MANIFEST.in'):
    if line.strip():
        fl.process_template_line(line.rstrip('\n'))
got = set(f.replace('./', '', 1) for f in fl.files)
assert 'src/imio/googleauthenticator/locales/imio.googleauthenticator.pot' in got
```

### RENAME-11 — the flag

```python
# src/imio/googleauthenticator/pas_plugin.py
class GoogleAuthenticatorPlugin(BasePlugin):
    """Google Authenticator PAS Plugin"""

    meta_type = 'iMio Google Authenticator PAS'   # RENAME-10, own commit
    security = ClassSecurityInfo()

    # RENAME-11. PAS's _SWALLOWABLE_PLUGIN_EXCEPTIONS (NameError, AttributeError,
    # KeyError, TypeError, ValueError) otherwise make any bug here a silent
    # fallthrough to source_users -- i.e. authentication on password alone, logged
    # only at DEBUG. reraise() (PAS 1.11.3:88-93) reads this attribute off the
    # plugin instance, so it is scoped to us: later plugins still get their
    # post-credentials-wipe KeyError swallowed, which the veto depends on.
    _dont_swallow_my_exceptions = True
```

### RENAME-11 — the test (integration, real collaborator, real PAS call path)

```python
# src/imio/googleauthenticator/tests/test_pas_plugin.py (add)
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from imio.googleauthenticator import pas_plugin
from imio.googleauthenticator.setuphandlers import PAS_ID


def _boom(*a, **kw):
    raise ValueError('deliberate: injected via a real collaborator')


class TestFailClosed(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.pas = getToolByName(self.portal, 'acl_users')
        self.portal_url = api.portal.get().absolute_url()
        self._install()

    # RENAME-12. objectIds() cannot catch this: a Broken object still appears
    # there. PluginRegistry.listPlugins filters on _satisfies() and logs the miss
    # at DEBUG, so a Broken plugin -- or a marker-file mismatch that never added
    # it -- is invisible without this assertion.
    def test_plugin_is_registered_for_authentication(self):
        registered = [pid for pid, _p
                      in self.pas.plugins.listPlugins(IAuthenticationPlugin)]
        self.assertIn(PAS_ID, registered)

    # RENAME-11. is_whitelisted_client is a genuine collaborator: pas_plugin.py:80
    # is the first statement of authenticateCredentials. Patching it -- rather than
    # authenticateCredentials itself -- means the ValueError is raised from inside
    # the method PAS calls, so _extractUserIds' own
    #   except _SWALLOWABLE_PLUGIN_EXCEPTIONS: reraise(auth); continue
    # block is the code under test.
    def test_plugin_exception_is_not_swallowed(self):
        original = pas_plugin.is_whitelisted_client
        pas_plugin.is_whitelisted_client = _boom
        try:
            request = self.layer['request']
            request.form['__ac_name'] = TEST_USER_NAME
            request.form['__ac_password'] = TEST_USER_PASSWORD
            # Fail closed: the exception must escape (-> HTTP 500), NOT be
            # swallowed into a fallthrough that authenticates via source_users.
            self.assertRaises(
                ValueError,
                self.pas._extractUserIds, request, self.pas.plugins)
        finally:
            pas_plugin.is_whitelisted_client = original
```

Notes for the implementer:
- Patch `pas_plugin.is_whitelisted_client` (the name bound in the plugin's module namespace by
  `from ...helpers import is_whitelisted_client`), **not** `helpers.is_whitelisted_client` — the
  `from X import Y` form means the helpers-module attribute is no longer consulted.
- `_extractUserIds` is private but it is the method that owns the swallow. If a public entry point
  is preferred, `acl_users.validate(request)` reaches it, but needs `request['PUBLISHED']` and
  `_getObjectContext` set up — more setup, no extra assurance.
- A companion negative test (delete the class attribute, assert `_extractUserIds` returns a
  `source_users` id instead of raising) documents the counterfactual and is cheap. Optional; the
  positive test is the requirement.

### RENAME-04 / RENAME-12 — the marker-file invariant, asserted behaviourally

```python
    def test_setup_handler_actually_ran(self):
        """A marker-file/string mismatch makes setupVarious return silently at
        setuphandlers.py:53, so the plugin is never added -- with no error and a
        clean git grep. This is the only assertion that sees it."""
        registered = [pid for pid, _p
                      in self.pas.plugins.listPlugins(IAuthenticationPlugin)]
        self.assertIn(PAS_ID, registered)
```

### D-10 — the changelog format, from the named authority

`/srv/src/server.dmsmail/src/imio.dms.mail/CHANGES.rst`, first lines, whitespace-exact
(`·` = space): `[VERIFIED: cat -A of the file]`

```rst
Changelog
=========

1.0.0 (unreleased)
------------------

- Renamed the package from ``collective.googleauthenticator``.
  [chris-adam]
- Existing databases are discarded, not migrated: the PAS plugin, the
  ``IUserDataSchemaProvider`` utility, the browser layer and the registry records
  all pickle the old module path and unpickle as ``OFS.Uninstalled.Broken``.
  Recreate the Plone site and re-enrol users.
  [chris-adam]
```

Title underline sized to its title; version heading on one line with a matching `-` underline;
entries as `- Text.` then two-space-indented `[handle]`; **no blank line between entries**.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `include`/`recursive-include` with comma-separated patterns | Space-separated patterns | Always — commas were never valid distutils syntax | The bug predates the fork; fixing it is independent of the rename and is what makes RENAME-06's sdist assertion meaningful |
| Ship a compiled `.mo` in the distribution | Ship `.po` only; `zope_i18n_compile_mo_files` compiles at ZCML load | zope.i18n 3.5+ | Verified set in `parts/instance/etc/zope.conf:12`, `bin/test:282`, and `server.dmsmail/base.cfg:95`. Requires `python-gettext` (present, 1.0) |
| `pkgutil.extend_path` namespace packages | `pkg_resources.declare_namespace` + `namespace_packages=` in `setup.py` | Convention across all `imio.*` and `collective.*` eggs on Python 2 | Mixing styles inside one namespace is the failure mode; match `imio.helpers` byte-for-byte |
| GS upgrade steps carried indefinitely | Deleted when no site exists at the old version | This fork, RENAME-09 | Removes five rename surfaces and a second `runImportStepFromProfile` call that Phase 2 would otherwise have to reason about |
| Assert installedness via `portal_quickinstaller.listInstalledProducts()` | Assert things the package controls: plugin registered for `IAuthenticationPlugin`, registry records present, browser layer active | Established by Pitfall P15/3 in the project research | `applyProfile` does not call `installProduct`, so the QuickInstaller assertion is both fragile and blind to a Broken plugin. RENAME-12 adopts the robust form; Phase 8 (QUAL-07) finishes the job |

**Deprecated / dead in this tree:**
- `upgrades/` — only ever applied to sites installed at ≤0.3.0, of which none exist (RENAME-09).
- `examples/simple/` — upstream's demo buildout, superseded by `Makefile` + `test-4.3.cfg` (D-07).
- `.hgignore` / `.hg.packed` — Mercurial leftovers; `.hgignore:16` still names
  `^src/collective.googleauthenticator\.egg-info`. Dead weight, and one more copy of the old name.
  See Observation O-2.
- `profiles/default/site_properties.xml` — byte-identical to `propertiestool.xml` and not a
  recognised GenericSetup step filename, so it is never imported. Observation O-3.
- `MANIFEST.in:2 include CONTRIBUTORS.txt` — the file does not exist.

---

## Corrections to Upstream Research

Every item below was verified against this working tree or this interpreter and **contradicts** a
claim in `.planning/research/PITFALLS.md`, `REQUIREMENTS.md` or `01-CONTEXT.md`. The planner should
treat this document as authoritative on these six points.

| # | Claim as written | Verified reality | Consequence for the plan |
|---|---|---|---|
| **C-1** | "all 27 git-ignored `.pyc` files" (RENAME-08, PITFALLS P1) | **29** `.pyc`; `git clean -xdn src/` lists **31** artefacts total | Cosmetic in the requirement, but the acceptance check must be `find src -name '*.pyc'` **empty**, not a count |
| **C-2** | "The **tracked** `.mo` file … is removed with `git rm`" (D-14) | The `.mo` is **untracked** — `.gitignore:36` is `*.mo`, and `git ls-files locales/` returns only `.gitkeep`, `.pot`, `nl/**.po`. `git rm` errors | Drop the `git rm` task. `git clean -xdf src/` (already required by RENAME-08) deletes it. One fewer step |
| **C-3** | "`base.cfg:52` already sets `zope_i18n_compile_mo_files = true`, so Zope compiles `.mo` at startup" (D-14) | `base.cfg:51-52` is the **`[testenv]`** section — it reaches `bin/test` only. `bin/instance` gets the flag from `parts/instance/etc/zope.conf:12`, which comes from the recipe/`buildout.plonetest`, **not** from `base.cfg`. Both verified present, and `server.dmsmail/base.cfg:95` covers deployment | D-14's conclusion holds; its stated reason is wrong. Do not "tidy" `base.cfg` on the assumption that line is what makes `bin/instance` work. Also: `python-gettext 1.0` must stay resolvable — it is the compiler |
| **C-4** | "`MANIFEST.in`'s **eight** hardcoded `src/collective/...` paths" (RENAME-06) | **Nine** (lines 6–14). And the real gap is broader: all 11 comma-suffixed patterns on line 5 are dead, `CONTRIBUTORS.txt` does not exist, and `locales/nl` scoping will exclude D-17's `fr/` and D-18's `en/` | Rewrite `MANIFEST.in`, do not path-substitute it. Verified template in `Code Examples` |
| **C-5** | "`bin/check-manifest` is already part of `bin/code-analysis`" and "`bin/code-analysis-find-untranslated` is already wired into `bin/code-analysis`" (PITFALLS P5, integration-gotchas table) | **False for both.** `bin/code-analysis` runs **Flake8 only** — its own output is a single `Flake8 … [ FAILURE ]` line. `bin/code-analysis-find-untranslated` reports `[ SKIP ]` when invoked directly | The sdist check (RENAME-06) and any i18n check need **explicit** tasks. Neither is covered by the pre-commit hook or CI |
| **C-6** | "`bin/code-analysis` … ~40 pre-existing findings" (CLAUDE.md, roadmap phase notes, QUAL-06) | **318** findings: `I001` 126, `E251` 78, `I004` 45, `I003` 13, `E302` 13, `F401` 12, `E265` 9, `E261` 6, `E231` 5, `W292` 4, `W291` 3, and 4 singletons. **184 of them (58%) are isort findings**, and `.isort.cfg` sets `force_alphabetical_sort` with no `known_first_party`, so `collective.*` → `imio.*` moves every first-party import's alphabetical position | Does not change this phase (Phase 8 owns QUAL-06, commits here use `--no-verify`). But Phase 8 is sized against a number that is **8× too small**, and the rename actively perturbs 58% of it. Flag for roadmap/STATE, and re-baseline QUAL-06 after this phase lands |

### Adjudications

**A-1 — `imio.helpers` namespace early-warning: use the 3-line assertion, do not add the dependency.**
The roadmap phase note requires "an explicit two-package import check
(`bin/python -c \"import imio.helpers, imio.googleauthenticator\"`)". Two verified problems.
(i) **`bin/python` cannot run it.** It is the bare virtualenv interpreter — 8 `sys.path` entries, no
eggs; `bin/python -c "import collective.googleauthenticator"` already fails today. The
eggs-on-path interpreter would be `bin/zopepy`, but `[plone-helper-scripts]` is commented out of
`base.cfg` `parts` and `bin/zopepy` does not exist.
(ii) **`imio.helpers` is not resolvable here.** It sits in the shared cache
(`/srv/cache/eggs/imio.helpers-1.3.15-…`) but is on no `sys.path` in this buildout, and adding it —
even to `extras_require['test']` — drags `plone.dexterity`, `plone.app.relationfield`,
`plone.app.intid`, `z3c.unconfigure`, `collective.fingerpointing`, `pyjwt` and `cryptography` into a
Plone **4.3** pin set. That is an unbudgeted buildout-resolution risk inside a phase whose whole
value is being mechanical.
**Decision:** implement the assertion in `Code Examples` instead
(`pkg_resources._namespace_packages` + `namespace_packages.txt`), which is 3 lines, needs no
dependency, and catches all three ways the declaration can be wrong.
**Cost of the road not taken, stated honestly:** the assertion cannot detect a *mismatch* with
another `imio.*` egg that declares the namespace differently. That residual risk is small and
bounded: `imio.helpers`' `src/imio/__init__.py` was read directly and uses `declare_namespace`, and
the instruction is to byte-copy it. Revisit if a second `imio.*` package ever lands in this buildout
for another reason.

**A-2 — RENAME-11's test: integration on `_extractUserIds`, not a browser 500.**
Success criterion 5 says "yields a 500 rather than authenticating on password alone via
`source_users`". The 500 is a *symptom* of PAS re-raising; the security property is the
`source_users` counterfactual. `_extractUserIds` is the method containing
`except _SWALLOWABLE_PLUGIN_EXCEPTIONS: reraise(auth); … continue`, so an `assertRaises` there
tests the mechanism directly and can also assert the counterfactual in one place.
**Cost of the road not taken:** no end-to-end evidence that ZPublisher actually renders 500 rather
than, say, a Plone error page with a 200. That gap is real but cheap to close later, and Phase 3
lands fail-closed-on-missing-key on the same path with a concrete operational need for the response
shape (CONTEXT: "Failure presentation … Revisit in Phase 3"). A functional 500 test belongs there.

### Observations (not requirements; cheap while the file is open)

- **O-1 — `rebuild_i18n.sh`'s i18ndude path is provably wrong.** `I18NDUDE="../../../../../bin/i18ndude"`
  from `src/imio/googleauthenticator/` resolves to `/srv/bin/i18ndude`, which does not exist
  (`ls: cannot access '/srv/bin/i18ndude'`). The correct depth is three: `../../../bin/i18ndude`.
  The rename does not change the depth, so this neither causes nor fixes it — but D-15 opens the
  file and D-17/D-18/D-19 depend on the script running. Fix it there. `[VERIFIED: executed locally]`
- **O-2 — `.hgignore:16` names the old egg-info path.** Mercurial is not in use (`.hg/` is ignored;
  `.hg.packed` is a leftover). It is one more copy of the old name and would fail a strict
  `git grep -i collective` acceptance check. Either update it or delete both files.
- **O-3 — `profiles/default/site_properties.xml` is dead.** Byte-identical to `propertiestool.xml`
  and not a recognised GenericSetup step filename, so it is never imported. Deleting it removes a
  file from the profile-rename surface.
- **O-4 — `<i18n:registerTranslations>` is declared twice**: `configure.zcml:11`
  (`directory="locales"`) and `browser/configure.zcml:7` (`directory="../locales"`). Both resolve to
  the same directory, and `zope.i18n`'s `handler()` merges catalogues into one domain, so it is
  harmless — but both must be renamed consistently, and the duplicate is worth a one-line note so
  nobody "fixes" only one.
- **O-5 — D-18 mentions "one" trailing-space msgid; there are two.**
  `"2. Enter the verification code to activate two-step verification "` (declared at **both**
  `browser/forms/reset_bar_code.py:36` and `browser/forms/user_setup.py:37`) and
  `"Invalid data. Details: {0} "` (`browser/forms/token.py:92`). Fixing the first changes two source
  sites for one msgid. That, plus `controlpanel.py:45` "ommit" and `token.py:52`'s missing "code",
  is **4 msgid edits across 5 source lines** — so D-19's "roughly 3 Dutch entries go fuzzy" is a
  slight undercount; expect 3–4.

---

## Rename Surface Inventory

Complete, measured. **61 tracked files** contain `collective` (case-insensitive);
**11 occurrences across 5 files are false positives.**
`[VERIFIED: executed locally — git grep -c -i collective]`

### §A — Filesystem moves (`git mv`, commit 1)

| From | To |
|------|-----|
| `src/collective/` (whole subtree, incl. `__init__.py`) | `src/imio/` — one `git mv src/collective src/imio` |
| `src/imio/googleauthenticator/locales/collective.googleauthenticator.pot` | `…/imio.googleauthenticator.pot` |
| `…/locales/nl/LC_MESSAGES/collective.googleauthenticator.po` | `…/imio.googleauthenticator.po` |
| `…/profiles/default/collective.googleauthenticator.marker.txt` | `…/imio.googleauthenticator.marker.txt` |
| `CHANGES.txt` | `CHANGES.rst` (D-10) |
| `docs/LICENSE.txt` | `./LICENSE.txt` (D-07) |
| *(delete)* `src/imio/googleauthenticator/upgrades/` | RENAME-09 |
| *(delete)* `examples/` | D-07 |

### §B — Python source (dotted imports, `MessageFactory`, logger names) — 15 files, 41 lines

`__init__.py:7,11` · `adapter.py:6,12,82,83` · `helpers.py:26,28,30` · `pas_plugin.py:27,28,29,32` ·
`setuphandlers.py:5,6,8,15,38,53` · `testing.py:12,18,21,26,30,33,34,35,36,38,39,40,42,43,44` ·
`userdataschema.py:16,18,87` · `browser/controlpanel.py:19,21,99` ·
`browser/settings_helper.py:7,11` · `browser/disable_two_factor_authentication.py:8` ·
`browser/disable_two_factor_authentication_for_all_users.py:8,10` ·
`browser/enable_two_factor_authentication_for_all_users.py:8,10` ·
`browser/forms/token.py:18,19,20,21,23,27` · `browser/forms/user_setup.py:18,20,22` ·
`browser/forms/reset_bar_code.py:17,19,21` · `browser/forms/request_bar_code_reset.py:20,22,24`

Tests: `tests/base.py:25,26` · `tests/test_generic.py:8,9,10,15,28` ·
`tests/test_helpers.py:3,4,5,7,14` · `tests/test_pas_plugin.py:6,8,9,10,15` ·
`tests/test_robot.py:1,11` · `tests/test_security.py:8,9,10,15`

`testing.py` is the densest file (15 hits) and carries three renames at once: the layer **class**
name `CollectivegoogleauthenticatorLayer`, the three module constants
`COLLECTIVE_GOOGLEAUTHENTICATOR_{FIXTURE,INTEGRATION_TESTING,FUNCTIONAL_TESTING,ROBOT_TESTING}`, and
the `z2.installProduct(app, '<name>')` string. **`z2.installProduct` with an unresolvable name logs
and continues** (`quiet=False` only logs), so a missed rename there means `initialize()` never runs,
`registerMultiPlugin` never happens, and the ZMI add-list entry vanishes **while tests still pass**.

### §C — ZCML and GenericSetup XML — 12 files

| File | Lines / attribute | Note |
|------|-------------------|------|
| `configure.zcml` | 9 (`i18n_domain`), 33 (profile description), 46/47/49 (`importStep` name, title, handler) | **also delete line 22** `<include package=".upgrades" />` |
| `overrides.zcml` | 4 (`i18n_domain`) | |
| `browser/configure.zcml` | 5 (`i18n_domain`), **10 (`resourceDirectory name=`)**, 111 (`class=`), 113 (`layer=`) | line 10 **defines** the `++resource++` prefix — RENAME-05's hidden half |
| `profiles/default/registry.xml` | 3 (`<records interface=…>`) | the record-key prefix; old keys become orphans in any existing ZODB |
| `profiles/default/browserlayer.xml` | layer `name=` **and** `interface=` | both |
| `profiles/default/componentregistry.xml` | `factory=` | the `IUserDataSchemaProvider` utility |
| `profiles/default/controlpanel.xml` | 4 (`i18n:domain`), 12 (`appId=`) | `appId` is what QuickInstaller uses to hide the configlet on uninstall |
| `profiles/default/cssregistry.xml` | `id="++resource++…/main.css"` | RENAME-05 |
| `profiles/default/jsregistry.xml` | 2 × `id="++resource++…"` | RENAME-05; the `popupforms.js remove="True"` line is Phase 7's |
| `profiles/default/skins.xml` | 4 `directory="collective.googleauthenticator:skins/…"` | **package prefix in a directory-view path — not named by RENAME-05** |
| `profiles/default/actions.xml` | 2 × `i18n:domain` | |
| `profiles/default/metadata.xml` | `<version>0301</version>` → `1000` | D-09 |
| `skins/…/request_bar_code_reset_email.pt` | 7 (`i18n:domain`) | template survives to Phase 7 |
| `www/add_google_authenticator_form.zpt` | 7 | "Collective Google Authenticator PAS plugin" → §E |
| `browser/static/main.js` | 4 (comment) | |

### §D — Build and tooling — 6 files

| File | Line | Change | Consumer |
|------|------|--------|----------|
| `base.cfg` | 2 | `package-name` | `bin/test` `-s` filter **and** `[test] eggs`; inherited by `[omelette]`, `[robot]` |
| `base.cfg` | 66 | `[code-analysis] directory` | `bin/code-analysis*` |
| `.coveragerc` | 2 | `[report] include` path | Phase 8 rewrites this section entirely (QUAL-01) — path-substitute only |
| `cleanup.sh` | 3 | `rm src/collective.googleauthenticator.egg-info -rf` | D-22 |
| `MANIFEST.in` | 1–14 | full rewrite | `Code Examples` |
| `setup.py` | 8, 29, 47, 51 | image URL (D-06), `name`, `url` (D-01), `namespace_packages` | |
| `src/imio/googleauthenticator/rebuild_i18n.sh` | 3 (+ 2, per O-1) | `I18NDOMAIN` | D-15 |
| `.hgignore` | 16 | egg-info path | Observation O-2 |
| `README.rst` | 2, 116, 119, 129, 211, 212, 242 | + "Forked from" line (D-01) | |
| `docs/index.rst` | 2, 116, 119, 129, 209, 210, 240 | near-duplicate of README | |
| `docs/conf.py` | 3, 50, 183, 266, 272 | Sphinx `project`, `htmlhelp_basename`, `epub_title` | |

### §E — PAS identity (own commit, Pattern 4) — 4 sites

`pas_plugin.py:59` `meta_type = 'Collective Google Authenticator PAS'` ·
`setuphandlers.py:10` `PAS_TITLE = 'Google Authenticator plugin (collective.googleauthenticator)'` ·
`www/add_google_authenticator_form.zpt:7` (the ZMI add-form heading) ·
`README.rst:129` / `docs/index.rst:129` (the quoted `PAS_TITLE`).
**`setuphandlers.py:11 PAS_ID = 'google_auth'` — DO NOT TOUCH.**

### §F — False positives (leave alone) — 11 occurrences, 5 files

`base.cfg:6` (`raw.githubusercontent.com/collective/buildout.plonetest/…`), `:29`
(commented `collective.profiler`), `:55` (`collective.recipe.omelette`), `:83`
(`collective.recipe.template`) · `checkouts.cfg:15,16` (the `collective` mr.developer remote alias
and its push URL) · `test-4.3.cfg:4` (plonetest URL), `:29` (`collective.upgrade = 1.5`), `:34`
(`collective.z3cform.datagridfield = 1.3.3`) · `docs/LICENSE.GPL:*`, `docs/LICENSE.txt:*` (GPL
boilerplate) · `CLAUDE.md` (documentation — update as part of the phase's doc work, not as a code
rename).

Acceptance grep, false positives excluded:
```bash
git grep -i collective -- src/ setup.py MANIFEST.in .coveragerc cleanup.sh .hgignore \
  | grep -v 'collective\.\(recipe\|upgrade\|z3cform\|profiler\)' \
  | grep -v 'buildout\.plonetest'
# must be empty
```

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_extractUserIds(request, plugins)` reaches our plugin in an `IntegrationTesting` layer when `request.form['__ac_name']`/`__ac_password'` are set — i.e. Plone 4.3's `credentials_cookie_auth` extracts from the request form. Not executed in this session. | Code Examples → RENAME-11 test | The test needs its request set up differently (e.g. `request._auth` for the basic-auth extractor, or `DumbHTTPExtractor`). Costs one iteration during implementation, not a redesign — the `assertRaises` target and the injection point are both verified. |
| A2 | Copying `imio.helpers`' `src/imio/__init__.py` byte-for-byte plus `namespace_packages=['imio']` is sufficient for the two packages to coexist in one process. Inferred from reading both files; **not executed together** (`imio.helpers` is not on this buildout's `sys.path`). | Adjudication A-1, Pitfall 3 | If wrong, the failure appears only when a second `imio.*` egg lands in the same process — i.e. at deployment. Mitigation: the byte-copy makes divergence impossible by construction, and the `_namespace_packages` assertion catches the local half. |
| A3 | The `docs/_static/*.png` files already committed here are the images D-06's rewritten URL should point at (no re-capture needed now). | User Constraints → D-06 | A broken PyPI image on the first release. Cheap to fix in a follow-up; the Deferred list already schedules a re-capture after Phase 7. |
| A4 | French vocabulary `vérification en deux étapes` / `code de vérification` matches iMio house terms. | User Constraints → D-17 | CONTEXT already routes this through user review before merge, so the risk is a review round, not a defect. |
| A5 | `bin/instance fg` starts cleanly today (success criterion 1's baseline). Not started in this session — it binds a port. The ZCML *does* load cleanly, evidenced by the 8-test suite passing through `xmlconfig.file('configure.zcml')` + `z2.installProduct`. | Validation Architecture → V-1 | If `bin/instance` has an unrelated pre-existing problem, criterion 1 fails for a reason this phase did not cause. Cheap to establish before starting: `bin/instance fg` once, on the current tree. |
| A6 | `zope_i18n_compile_mo_files` is set in whatever production buildout ultimately consumes this egg. Verified for `server.dmsmail/base.cfg:95`, which is the named target; **not** verified for any other consumer. | Pitfall 1, C-3 | Shipping no `.mo` means a consumer without the flag gets zero translations, with only a `logger.critical`. Bounded: `server.dmsmail` is the only planned consumer. |

**Nothing in the Corrections table, the Rename Surface Inventory, or the Pitfalls is assumed** —
each was executed or read from source on this machine.

---

## Open Questions

1. **Does `en/LC_MESSAGES/*.po` (D-18) actually render, or does Plone short-circuit to the msgid?**
   - What we know: `registerTranslations` registers an `en` catalogue like any other, and
     `TranslationDomain` resolves by negotiated language. So the file *will* be registered.
   - What's unclear: whether Plone's language negotiation for a default-English site routes through
     the `en` catalogue or falls back to the msgid before consulting it. CONTEXT already records
     that the override is redundant once msgids are correct.
   - Recommendation: implement both as decided (D-18 is locked, "do not re-litigate"). Add one
     assertion that an English label renders the corrected text — that assertion is valuable whether
     the text comes from the catalogue or the msgid, and it is the acceptance test for the msgid
     fixes either way.

2. **Should the `MANIFEST.in` rewrite carry Phase 7's deletions early?**
   - What we know: the template includes `recursive-include …/skins *` and `*.cpt`/`*.metadata`
     patterns for files Phase 7 deletes (COEX-02, COEX-05).
   - What's unclear: nothing technical — leaving them is harmless (`recursive-include` on a
     nonexistent directory produces a warning, not an error).
   - Recommendation: keep them. Removing them now couples Phase 1's `MANIFEST.in` to Phase 7's
     scope, and the warning is a useful reminder. Phase 7 drops the lines with the directories.

3. **How is `git clean -xdf src/` sequenced relative to `git mv`?**
   - What we know: both orders work. After `git mv src/collective src/imio`, the untracked `.pyc`
     tree remains at `src/collective/` and is still under `src/`, so `git clean -xdf src/` still
     reaches it and removes the now-empty directory.
   - Recommendation: `git mv` then `git clean`, in that order, in one commit — the post-condition
     `test ! -d src/collective` then holds at commit time and is directly assertable.

4. **What is the corrected QUAL-06 baseline, and does Phase 8 still fit?**
   - What we know: 318 findings, not ~40 (C-6); 184 are isort findings that this rename perturbs.
   - What's unclear: how many of the 318 `bin/isort` can fix mechanically. Likely most of the 184
     isort ones plus `E251`'s 78 (`keyword = value` spacing, mechanically fixable).
   - Recommendation: out of scope here — but record the corrected number in STATE.md
     Blockers/Concerns now, while the evidence is fresh, so Phase 8 is not planned against 40.

---

## Environment Availability

All probes executed on this machine, this session.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `git` (with `mv`, `clean -xdf`) | RENAME-01, RENAME-03, RENAME-04, RENAME-08 | ✓ | repo on `master`, clean tree | — |
| `bin/buildout` | Pitfall 5 — regenerate `bin/test` after the `base.cfg` edit | ✓ | zc.buildout 2.13.3 | — |
| `bin/test` (`zc.recipe.testrunner`) | RENAME-11, RENAME-12, all assertions | ✓ | `zope.testing 3.9.7`; **8 tests, 0 failures, 0 errors** on the current tree | — |
| `bin/python` | `setup.py sdist` | ✓ | 2.7.18 — bare virtualenv, **8 `sys.path` entries, no eggs** | cannot import the package; use `bin/test` for anything needing eggs |
| `bin/zopepy` | an eggs-on-path REPL | ✗ | — | `[plone-helper-scripts]` is commented out of `base.cfg` `parts`; use `bin/test` |
| `setuptools` | `sdist`, `namespace_packages` | ✓ | 44.1.1 (pinned) | — nothing may need PEP 517 |
| `bin/check-manifest` | RENAME-06 | ✓ | **exit 1** today, with a full "suggested MANIFEST.in rules" list | — but it is **not** run by `bin/code-analysis` (C-5) |
| `bin/i18ndude` | D-17, D-18, D-19 via `rebuild_i18n.sh` | ✓ | present in `bin/` | note the wrong `I18NDUDE` path in the script (O-1) |
| `python-gettext` | D-14 — `.po` → `.mo` at ZCML load | ✓ | 1.0, on both `bin/test` and `bin/instance` paths | none — without it `zope.i18n` logs CRITICAL and registers no catalogue |
| `zope_i18n_compile_mo_files` | D-14 | ✓ | `parts/instance/etc/zope.conf:12`, `bin/test:282`, `server.dmsmail/base.cfg:95` | — |
| `bin/code-analysis` | QUAL-06 (Phase 8) | ✓ | **318 findings, exit 1**; installed as a `.git/hooks/pre-commit` running `bin/code-analysis --return-status-codes` | commits in this phase need `--no-verify` (accepted, STATE.md) |
| `bin/instance` | Success criterion 1 | ✓ | script generated; **not started this session** (see A5) | — |
| `var/filestorage/Data.fs` | The Broken-ZODB risk | ✗ (**absent — this is good**) | — | nothing to purge here; the D-20 target exists for other developers |
| PyPI reachability | D-03 name check | ✓ | `imio.googleauthenticator` → HTTP 404 (available) | — |
| `imio.helpers` on this buildout's path | the rejected two-package import check | ✗ | in `/srv/cache/eggs` but on no `sys.path` here | Adjudication A-1 — use the `pkg_resources` assertion instead |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `bin/zopepy` → use `bin/test`; `imio.helpers` → the
`pkg_resources._namespace_packages` assertion; `Data.fs` → nothing to do on this machine.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `zope.testing` 3.9.7 via `zc.recipe.testrunner` 1.2.1, driven by `bin/test`; test classes are `unittest2.TestCase` + the local `BaseTest` mixin |
| Config file | `base.cfg` `[test]` (`environment = testenv`) — the `-s <package>` filter and eggs are **generated** into `bin/test` from `base.cfg:2 package-name`; there is no standalone test config file |
| Quick run command | `bin/test -t '!robot' -m imio.googleauthenticator.tests.test_pas_plugin` |
| Full suite command | `make test` (== `bin/test -t '!robot'`) |
| Baseline (current tree) | **8 tests, 0 failures, 0 errors**, ~7 s including layer setup `[VERIFIED: executed locally]` |
| Layer | `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING` (renamed from `COLLECTIVE_…`). All 8 existing tests use it, including the ones that drive a `z2.Browser` inside it — the isolation problem QUAL-05 owns. **Do not refactor layers in this phase.** |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RENAME-01 | `imio` is a `pkg_resources` namespace and the dist declares it | unit | `bin/test -t test_imio_is_a_pkg_resources_namespace` | ❌ Wave 0 — add to `tests/test_generic.py` |
| RENAME-02 | Package imports and all ZCML loads; no `collective.*` dotted name resolves | integration | `bin/test -t '!robot'` (layer setup executes `xmlconfig.file('configure.zcml')`) — plus the §F acceptance grep | ✅ covered by layer setup once `testing.py` is renamed |
| RENAME-03 | A Dutch label renders in Dutch after the domain rename | integration | `bin/test -t test_control_panel_is_translated_nl` | ❌ Wave 0 — new test; render `@@google-authenticator-settings` with `?set_language=nl` and assert a known Dutch string |
| RENAME-04 | `setupVarious` ran (marker file matched) | integration | `bin/test -t test_plugin_is_registered_for_authentication` | ❌ Wave 0 — same assertion as RENAME-12 |
| RENAME-05 | `++resource++imio.googleauthenticator/main.{js,css}` are registered | integration | `bin/test -t test_resources_are_registered` | ❌ Wave 0 — assert both ids in `portal_javascripts`/`portal_css` `getResourceIds()`; also asserts `browser/configure.zcml:10` and `skins.xml` agree |
| RENAME-06 | sdist contains `profiles/`, `locales/**` (incl. the `.pot`, `nl/`, `fr/`, `en/`), `www/`, `browser/static/` | build check | `bin/python setup.py sdist && tar tzf dist/*.tar.gz \| grep -E 'locales/.*\.pot\|locales/(nl\|fr\|en)/\|profiles/default/\|www/'` — plus `bin/check-manifest; echo $?` | ❌ Wave 0 — **no automated hook exists** (C-5); must be an explicit plan task. Optionally encode as a unit test using `distutils.filelist.FileList` (see `Code Examples`) so it runs in `bin/test` |
| RENAME-07 | `bin/test`, `bin/code-analysis` and `.coveragerc` name the new package | build check | `grep defaults .installed.cfg \| grep imio` ; `ls develop-eggs/ \| grep -c googleauthenticator` → 1 ; `ls -d src/*.egg-info` → 1 | ❌ Wave 0 — shell assertions in the plan, not `bin/test` (they describe generated artefacts) |
| RENAME-08 | No orphan bytecode, no stale distribution | build check | `test ! -d src/collective && ! find src -name '*.pyc' \| grep -q . && ! find src -name 'collective.googleauthenticator.*' \| grep -q .` | ❌ Wave 0 |
| RENAME-09 | `upgrades/` gone and not included | integration | `bin/test -t '!robot'` (a stale `<include package=".upgrades"/>` fails layer setup loudly) + `test ! -d src/imio/googleauthenticator/upgrades` | ✅ covered by layer setup |
| RENAME-10 | Zope starts with exactly one `meta_type` registered | integration | `bin/test -t '!robot'` — `z2.installProduct` runs `initialize()`, so a duplicate `meta_type` raises `RuntimeError` during layer setup | ✅ covered by layer setup |
| RENAME-11 | A plugin exception propagates instead of falling through to `source_users` | integration | `bin/test -t test_plugin_exception_is_not_swallowed` | ❌ Wave 0 — `Code Examples` |
| RENAME-12 | `google_auth` is registered for `IAuthenticationPlugin` | integration | `bin/test -t test_plugin_is_registered_for_authentication` | ❌ Wave 0 — **must be a new assertion**, not a rename of `test_plugin_is_installed` (which checks `objectIds()` and is blind to a Broken object) |
| DOC-04 | `CHANGES.rst` records the rename and the DB-discard | manual-only | Read `CHANGES.rst`; `bin/python -c "import setup"` proves `open('CHANGES.rst')` resolves | ❌ Wave 0 — prose; the automatable part is that `setup.py`'s `long_description` build does not silently fall into its bare `except:` |
| Criterion 1 | `bin/instance` starts; a fresh Plone site installs the add-on with the plugin present | manual-only | `bin/instance fg`, create a site with the add-on selected, then `acl_users/plugins` in the ZMI | ❌ human-verify — needs a real Zope process and a browser; `human_verify_mode: end-of-phase` |

### Sampling Rate

- **Per task commit:** `bin/test -t '!robot' -m imio.googleauthenticator.tests.<touched module>`
  — except for the commit-1 (pure move) and commit-2 (buildout regeneration) tasks, where
  `bin/test` **cannot run** until `bin/buildout -N` completes (Pitfall 5). For those two, the
  per-commit checks are the shell assertions in the RENAME-07/RENAME-08 rows above.
- **Per wave merge:** `make test` (full suite, `!robot`) **and** the RENAME-06 sdist check, since
  nothing in `bin/test` or the pre-commit hook covers the sdist (C-5).
- **Phase gate:** full suite green, `bin/check-manifest` reviewed, the §F acceptance grep empty,
  and criterion 1 manually confirmed before `/gsd-verify-work`.
- **Not a gate:** `bin/code-analysis`. It exits 1 with 318 findings and stays that way until
  Phase 8 (QUAL-06). Commits use `--no-verify`. Do not let a plan task try to make it green.

### Wave 0 Gaps

- [ ] `tests/testing.py` renamed — layer class + 4 constants + `z2.installProduct` string. Blocks
      every other test file; must land before any new test.
- [ ] `tests/test_pas_plugin.py` — add `test_plugin_is_registered_for_authentication`
      (RENAME-04, RENAME-12) and `test_plugin_exception_is_not_swallowed` (RENAME-11).
- [ ] `tests/test_generic.py` — add `test_imio_is_a_pkg_resources_namespace` (RENAME-01),
      `test_control_panel_is_translated_nl` (RENAME-03),
      `test_resources_are_registered` (RENAME-05).
- [ ] `tests/test_generic.py:28` — `test_product_is_installed` still asserts via
      `portal_quickinstaller.listInstalledProducts()`. Path-rename it in this phase (it is a
      literal string); leave the *approach* for QUAL-07.
- [ ] Explicit plan task for the sdist assertion — **no test framework hook exists** (C-5).
- [ ] Framework install: **none needed.** `bin/test` exists and the baseline is green.

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`. This phase's only behavioural change is on
the authentication path, so V2 dominates.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | **yes** | `_dont_swallow_my_exceptions = True` (RENAME-11) converts every swallowable exception on the authentication path from a silent single-factor login into a 500. ASVS 2.2.1 (anti-automation / controls must not fail open). The RENAME-12 `listPlugins` assertion is the control that proves the second factor is *installed at all* — a Broken plugin is a fail-open that no test currently detects. |
| V3 Session Management | no | This phase grants no session and does not touch `plone.session`, the `__ac` cookie handling, or `session._setupSession()`. Phase 4 owns the grant point. |
| V4 Access Control | no | No permission, role, or `security.declare*` change. |
| V5 Input Validation | no | No new input surface. The `next_url` open redirect (BUG-01) and the `+`-escaping FIXME (BUG-06) are **live today and deliberately out of scope** — Phase 7. Do not "fix them while you are in the file"; CONTEXT scopes them elsewhere and BUG-01 must ship with the override deletion. |
| V6 Cryptography | no | No crypto in this phase. The `ska` derived-key concatenation weakness (BUG-04) is Phase 2; Fernet is Phase 3. The `ska` signing key is a composite of the user secret, the global `ska_secret_key` and a `User-Agent` SHA1 — **renaming does not change any of those three inputs**, so previously-issued signed URLs keep validating. Worth one line in DOC-04 for anyone holding a live token URL across the upgrade. |
| V7 Error Handling & Logging | **yes** | The 500 must not leak whether 2FA is enabled for an account (CONTEXT: "Failure presentation"). A plain Zope 500 satisfies this by being uniform; a bespoke error view is what risks the oracle, which is exactly why one is deferred. Separately, `pas_plugin.py:90,94` log the **username** at `debug` — a user-enumeration surface. Out of scope here (Phase 4's DOC-01/logging work), but do not *add* identity to any new log line in this phase. |

### Known Threat Patterns for Plone 4.3 / PAS

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Plugin exception swallowed → authentication proceeds on password alone via `source_users` | Spoofing (auth bypass) | `_dont_swallow_my_exceptions = True` (RENAME-11), asserted by `test_plugin_exception_is_not_swallowed` |
| Renamed module → `OFS.Uninstalled.Broken` plugin → `listPlugins` skips it → second factor silently stops running | Spoofing (auth bypass) | Discard DBs rather than migrate (D-20, DOC-04); permanent `listPlugins(IAuthenticationPlugin)` assertion (RENAME-12) |
| Marker-file mismatch → `setupVarious` returns → plugin never installed on a *new* site | Spoofing (auth bypass) | Same `listPlugins` assertion after `applyProfile` (RENAME-04) |
| Orphan `.pyc` / duplicate egg-link → both namespaces load → duplicate ZCML, ambiguous plugin registration | Tampering | `git clean -xdf src/` + explicit egg-link `rm`; `registerMultiPlugin`'s `RuntimeError` is the loud backstop |
| Fail-closed lockout of every in-site user, Site Admins included | Denial of Service (accepted) | Break-glass is the Zope **root** `acl_users` admin, which is architecturally outside this in-site PAS plugin (`_tryEmergencyUserAuthentication` bypasses every plugin by construction). CONTEXT locks this trade and routes the rationale into DOC-01. Correct for an MFA package: a loud outage beats a silent bypass. |
| Orphaned `portal_registry` keys under the `collective.*` prefix persisting in `portal_setup` snapshots | Information Disclosure (minor) | No `Data.fs` exists here, so nothing to orphan on this machine. On any other checkout, the DB is discarded. Assert `not any(k.startswith('collective.') for k in portal_registry.records)` if a carried-forward DB is ever in play. |

---

## Project Constraints (from CLAUDE.md)

Actionable directives extracted from `./CLAUDE.md` and `./.claude/CLAUDE.md`. Treat with the same
authority as CONTEXT.md's locked decisions.

| Directive | Source | Implication for this phase |
|-----------|--------|----------------------------|
| The distribution and Python package is `collective.googleauthenticator`; the repo name appears nowhere in the code | `CLAUDE.md` §Naming | **This phase inverts that statement.** `CLAUDE.md` must be updated as part of the phase — it becomes the *repo* name that matches and the old dotted name that disappears. `CLAUDE.md` has 4 `collective` occurrences. |
| Python 2.7 / Plone 4.3 only; no Python 3, no Plone 5/6 branch | `CLAUDE.md` §Stack | No `six`, no `__future__` imports, no f-strings. `print` statements stay if present. |
| `make setup plone=4.3` / `make buildout` / `make test` / `bin/test -t '!robot'`; **never edit `bin/*`** | `CLAUDE.md` §Commands | The rename must go through `base.cfg` + `bin/buildout`, never by hand-editing generated scripts. |
| `bin/code-analysis` currently FAILS on pre-existing style debt; commits need `--no-verify` | `CLAUDE.md` §Commands | Every commit in this phase uses `--no-verify`. The real count is **318**, not ~40 (C-6). |
| `test_robot.py` needs a real browser and is excluded everywhere | `CLAUDE.md` §Commands | Rename `test_robot.py`'s imports; never try to run it. |
| All pins live in `test-4.3.cfg` `[versions]`; buildout appends resolved pins itself — commit those additions | `CLAUDE.md` §Version pinning | This phase adds no pin. If `bin/buildout` appends anything after the rename, commit it. |
| `ska = 1.7.5` and the unpinned `plone.testing` are load-bearing — do not "upgrade" them | `CLAUDE.md` §Version pinning | Do not touch either. Pinning `plone.testing 5.0.0` would trip `TestIsolationBroken` in every browser test in this package. |
| `snake_case` with `get_`/`set_`/`validate_`/`is_`/`has_` prefixes; `I`-prefixed interfaces; reST docstrings with `:param Type name:` / `:return type:` | `CLAUDE.md` §Conventions | New test methods follow `test_<snake_case>`; any new helper follows the prefix convention. |
| `.isort.cfg`: `force_single_line`, `force_alphabetical_sort`, `line_length = 120`; there is no `setup.cfg` | `CLAUDE.md` §Conventions | Renamed imports will land in the wrong alphabetical position. **Accepted** — QUAL-06 is Phase 8, and fixing it here means fixing it twice. |
| GS profile version is a zero-padded string matching the package version | `CLAUDE.md` §Conventions | D-09 sets `1000` for `1.0.0.dev0`. Consistent. |
| `.planning/codebase/` predates the buildout migration and still refers to `buildout.cfg`, `setup.cfg`, `.travis.yml` — none of which exist | `CLAUDE.md` §Further reading | Do not trust `.planning/codebase/*` on build tooling. This document's Rename Surface Inventory was measured against the current tree. |
| Seed encryption key never in the ZODB, a memberdata property, a log line, or an exception message | `.claude/CLAUDE.md` §Constraints | Phase 3. No key handling in this phase — do not add any. |
| Must coexist with `imio.dms.mail`: no wholesale skin or resource-registry overrides, nothing that mutates a resource we do not own | `.claude/CLAUDE.md` §Constraints | The offending `popupforms.js remove="True"` line stays for now (Phase 7 / COEX-03). Rename its `++resource++` ids and change nothing else about `jsregistry.xml`. |
| Undeclared memberdata properties are silently popped — every new property needs a `memberdata_properties.xml` entry and a round-trip test | `.claude/CLAUDE.md` §Constraints | No new property in this phase. `memberdata_properties.xml` needs no rename (it names properties, not the package). |
| **GSD workflow enforcement:** no direct repo edits outside a GSD workflow | `.claude/CLAUDE.md` | This research made **zero** repo edits. All verification used read-only inspection, `git clean -xdn` (dry run), `distutils.filelist` evaluation, and an `sdist` written to `/tmp`. |

---

## Sources

### Primary (HIGH confidence — executed or read on this machine, this session)

- **Executed against this buildout's interpreters:**
  `bin/test -t '!robot'` (8 tests, 0 failures) · `bin/test -s imio.googleauthenticator`
  (ImportError, proving the generated `-s` filter) · `bin/python setup.py sdist` + `tarfile` diff
  against `src/` · `distutils.filelist.FileList.process_template_line` on both the current and the
  proposed `MANIFEST.in` (+5/−1) · `pkg_resources._namespace_packages` /
  `get_distribution(...).get_metadata('namespace_packages.txt')` with `bin/test`'s `sys.path`
  injected · `git clean -xdn src/` (31 items) · `git grep -c -i collective` (61 files) ·
  `bin/check-manifest` (exit 1) · `bin/code-analysis` (Flake8 only, 318 findings, exit 1) ·
  `bin/code-analysis-find-untranslated` (SKIP) · `bin/python -c "import bin/python's sys.path"`
  (8 entries, no eggs) · `ls /srv/bin/i18ndude` (absent) · `find var` (no `Data.fs`).
- **Source read from the exact pinned eggs in `/srv/cache/eggs`:**
  `Products.PluggableAuthService-1.11.3/PluggableAuthService.py` —
  `_SWALLOWABLE_PLUGIN_EXCEPTIONS` (:81), `reraise` (:88-93), `_extractUserIds` (:577-685),
  `validate` (:232-287), `registerMultiPlugin` ·
  `Products.PluginRegistry-1.11/PluginRegistry.py` — `listPlugins` / `_satisfies` filtering with a
  `logger.debug` on the miss · `zope.i18n-3.7.4/zcml.py` (`registerTranslations` :65-102,
  `handler` :49-62) and `zope.i18n-3.7.4/compile.py` (`compile_mo_file`, `HAS_PYTHON_GETTEXT`).
- **This checkout, read in full:** `setup.py`, `MANIFEST.in`, `base.cfg`, `test-4.3.cfg`,
  `checkouts.cfg`, `.coveragerc`, `.gitignore`, `.hgignore`, `.isort.cfg`, `cleanup.sh`, `Makefile`,
  `AUTHORS.txt`, `CHANGES.txt`, `.installed.cfg` `[test]`, `parts/instance/etc/zope.conf`,
  `.github/workflows/package-test.yml`, `.git/hooks/pre-commit`, all of `src/collective/**`
  (source, ZCML, `profiles/**`, `locales/**`, `skins/**`, `www/**`, `tests/**`), `docs/**`,
  `examples/**`.
- **Sibling repos read for house style / precedent:**
  `/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py` (the namespace declaration to
  byte-copy) · `/srv/src/server.dmsmail/src/imio.helpers/setup.py` (`namespace_packages=["imio"]`,
  `license="GPL"`, `X.Y.Z.dev0`, the GPLv2 classifier string) ·
  `/srv/src/server.dmsmail/src/imio.dms.mail/CHANGES.rst` (`cat -A`, whitespace-exact) ·
  `/srv/src/server.dmsmail/base.cfg:95` (`zope_i18n_compile_mo_files`).
- **PyPI JSON API:** `pypi.org/pypi/imio.googleauthenticator/json` → **404** ·
  `pypi.org/pypi/imio-googleauthenticator/json` → 404 ·
  `pypi.org/pypi/collective.googleauthenticator/json` → 200, latest **0.2.5**, uploaded
  2014-06-20, 7 releases, author `Goldmund, Wyldebeast & Wunderliebe`, license `GPL 2.0` ·
  `pypi.org/pypi/imio.helpers/json` → 200, latest **1.3.16**, license `GPL`.
- **Project research, consumed as upstream input and corrected where it conflicted with the
  above:** `.planning/research/SUMMARY.md`, `.planning/research/PITFALLS.md`,
  `.planning/REQUIREMENTS.md`, `.planning/STATE.md`,
  `.planning/phases/01-rename-and-fail-closed/01-CONTEXT.md`.

### Secondary (MEDIUM confidence)

- [PAS eats exceptions — Plone Documentation v4.3](https://4.docs.plone.org/old-reference-manuals/pluggable_authentication_service/pas-eats-exceptions.html)
  — corroborates `_dont_swallow_my_exceptions`. Cited only as corroboration; the source was read
  directly.

### Tertiary (LOW confidence)

- None relied upon. No web search or MCP documentation provider was used: the phase adds no
  library, and every question was answerable from installed source or by execution. Because no
  external provider was queried, the `research-plan` / `classify-confidence` seams had no fetch to
  arbitrate — the confidence tiers above derive from local primary source, which is the highest tier
  those seams assign.

---

## Metadata

**Confidence breakdown:**

| Area | Level | Reason |
|------|-------|--------|
| Rename surface inventory | **HIGH** | Enumerated by `git grep -c -i` across 61 files, with file:line, and false positives individually classified. No inference. |
| Runtime state inventory | **HIGH** | All five categories probed on this machine. The dangerous category (ZODB) is empirically absent; the build-artefact category is enumerated by `git clean -xdn`. |
| `MANIFEST.in` / sdist | **HIGH** | Measured twice — an actual `sdist` diffed against `src/`, then the replacement template evaluated with `distutils.filelist`. The `.pot` gap and the dead comma patterns are observed facts, not readings of the syntax. |
| i18n mechanism | **HIGH** | `zope.i18n-3.7.4/zcml.py` and `compile.py` read line by line; `python-gettext` and the `zope_i18n_compile_mo_files` flag confirmed on both runners and in the deployment buildout. |
| Fail-closed mechanism | **HIGH** | `reraise()`, `_SWALLOWABLE_PLUGIN_EXCEPTIONS` and the `_extractUserIds` authenticator loop read verbatim from PAS 1.11.3. |
| Fail-closed **test wiring** | **MEDIUM** | The `assertRaises` target and the injection point are verified; the request-setup detail for credential extraction is assumption A1 and may need one iteration. |
| Corrections to upstream research (C-1…C-6) | **HIGH** | Each is a measurement on this tree that contradicts a written claim. |
| Adjudication A-1 (`imio.helpers`) | **HIGH** on the mechanics (`bin/python` has no eggs; `bin/zopepy` absent; `imio.helpers` not importable here), **MEDIUM** on the judgement that the dependency tree would be problematic under Plone 4.3 pins — the resolution was not attempted, only read off `imio.helpers`' `install_requires`. |
| PyPI availability | **HIGH** | Direct JSON API, HTTP status recorded. |
| Criterion 1 (`bin/instance` starts) | **MEDIUM** | Assumption A5 — not started this session. ZCML loads cleanly, evidenced by the green suite. |

**Overall confidence:** HIGH. No new library, no new API surface, and every claim either executed or
read from the pinned source. The residual uncertainty is concentrated in two named assumptions
(A1 test wiring, A5 `bin/instance` baseline), both cheap to settle in the first minutes of execution.

**Research date:** 2026-07-28
**Valid until:** 2026-08-27 (30 days — nothing here is fast-moving: the eggs are pinned, Plone 4.3 is
frozen, and the tree is pre-rename). **Invalidated early by:** any `bin/buildout` run that changes
pins, any commit that touches `src/`, or the arrival of a `var/filestorage/Data.fs` on this machine
(which would move the Runtime State Inventory's first row from "None" to "migration required").
