# Phase 1: Rename and Fail-Closed - Context

**Gathered:** 2026-07-28
**Status:** Ready for planning

<domain>
## Phase Boundary

The package identifies itself as `imio.googleauthenticator` everywhere — on disk, in the egg, in
the i18n domain and `locales/` filenames, in the GenericSetup profile and its marker file, in the
registry interface path, in `++resource++` prefixes, and in build tooling — and any exception
raised inside the PAS plugin becomes a 500 rather than a silent fallthrough to password-only
authentication.

Requirements: RENAME-01 … RENAME-12, DOC-04.

**Not this phase:** the registry seeding bug (Phase 2), encryption (Phase 3), the PAS boundary
rework (Phase 4), override deletion (Phase 7), lint debt and coverage (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Fork provenance and package metadata

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

### Version and GenericSetup profile version

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

### Translations

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

### Developer migration

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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — constraints, key decisions, and the Out of Scope list
- `.planning/REQUIREMENTS.md` — RENAME-01…12 and DOC-04 as written, plus the Open Decisions table
- `.planning/ROADMAP.md` §"Phase 1: Rename and Fail-Closed" — goal, success criteria, phase notes
  (note D-21 overrides its `PYTHONDONTWRITEBYTECODE` line)

### Research (primary-source, verified against installed eggs)
- `.planning/research/SUMMARY.md` — reconciled build order, same-commit groups, adjudicated
  conflicts; the single most important read
- `.planning/research/PITFALLS.md` — the rename "looks done but isn't" checklist: orphan `.pyc`,
  marker file, i18n filenames, `MANIFEST.in`, `Broken` ZODB objects
- `.planning/research/STACK.md` — verified Python 2.7 version ceilings and executed API surfaces
- `.planning/research/ARCHITECTURE.md` — PAS interface semantics with file:line references
- `.planning/codebase/CONVENTIONS.md` — naming, import ordering, logging patterns to preserve
- `.planning/codebase/TESTING.md` — current test layer setup and its isolation problem

### User-referenced during discussion (follow these for house style)
- `/srv/src/server.dmsmail/src/imio.dms.mail/CHANGES.rst` — **the changelog format to match**
  (D-10): title underlines sized to their titles, `X.Y.Z (unreleased)` single-line headings,
  `- Entry.` + `  [handle]`
- `/srv/src/server.dmsmail/src/imio.helpers/src/imio/__init__.py` — the `imio` namespace
  declaration to copy verbatim: `__import__('pkg_resources').declare_namespace(__name__)`
- `/srv/src/server.dmsmail/src/imio.helpers/setup.py` — `namespace_packages=["imio"]`,
  `license="GPL"`, and the `X.Y.Z.dev0` version convention

### Local files this phase edits (non-obvious ones)
- `base.cfg:52` — `zope_i18n_compile_mo_files = true`, why no `.mo` is shipped (D-14)
- `MANIFEST.in` — the comma bug (below) plus ~9 `src/collective/...` paths
- `src/collective/googleauthenticator/rebuild_i18n.sh` — hardcoded domain (D-15)
- `cleanup.sh` — hardcoded egg-info path (D-22)
- `Makefile:57-82` — `setup`/`cleanall`/`backup`/`restore`; the new target goes here (D-20)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`imio.helpers` namespace declaration** — copy it verbatim rather than inventing one. A mismatch
  between `declare_namespace`, `pkgutil`, and an empty `__init__.py` across `imio.*` packages is
  the breakage research warned about; `imio.googleauthenticator` and `imio.helpers` must agree.
- **`rebuild_i18n.sh`** — already implements the `i18ndude rebuild-pot` + `sync` loop needed for
  D-17/D-18/D-19. Update its domain and reuse it; do not hand-write `.po` headers.
- **`Makefile` target conventions** — `.PHONY:` + `target: deps  ## help text` renders in
  `make help`. The new purge target (D-20) follows this shape.
- **`imio.dms.mail/CHANGES.rst`** — the format authority for D-10, not a guess.

### Established Patterns
- `.isort.cfg`: `force_alphabetical_sort`, `force_single_line`, `line_length = 120`. The rename
  changes first-party import ordering, which is why the ~40-finding lint sweep is deferred to
  Phase 8 rather than done twice.
- Namespace packaging via `namespace_packages` + `pkg_resources.declare_namespace`, mirroring the
  existing `src/collective/__init__.py`.
- Logger names are the dotted package name (`logging.getLogger("collective.googleauthenticator")`)
  — these move with the rename.

### Integration Points
- **The git remote is already `git@github.com:IMIO/imio.googleauthenticator.git`.** Only the code
  lags the repo name, so `url` in `setup.py` (D-01) has a settled target.
- **PAS registration** — `__init__.py`'s `registerMultiPlugin()` and the `meta_type`. Roadmap keeps
  `PAS_ID` (`google_auth`) unchanged and isolates the `meta_type` change in its own commit.
- **GenericSetup marker file** — `setupVarious` guards on
  `context.readDataFile('collective.googleauthenticator.marker.txt')` and **returns silently** on a
  mismatch. Renaming the string without renaming the file means the PAS plugin is never installed,
  with no error.
- **`MANIFEST.in` bug, independent of the rename:**
  `recursive-include src *.zcml, *.pot, *.po, ...` — `MANIFEST.in` does not accept comma-separated
  patterns, so the commas become part of the globs and every pattern on that line is dead except
  the trailing `*.sh`. The sdist is only partly rescued by the explicit `recursive-include` lines
  beneath it. `MANIFEST.in` also includes `CONTRIBUTORS.txt`, which does not exist in this repo.
  Both must be fixed for RENAME-06; the sdist test in success criterion 3 is what catches them.

</code_context>

<specifics>
## Specific Ideas

- **Changelog format:** match `imio.dms.mail/CHANGES.rst` exactly — the user named this file as the
  authority. Underlines sized to their titles, `X.Y.Z (unreleased)` on one heading line,
  `- Entry.` followed by `  [handle]`.
- **French vocabulary:** Claude drafts, user reviews. Expect `vérification en deux étapes` and
  `code de vérification`; defer to iMio house terms wherever the user corrects them.
- **Attribution shape:** upstream's four names under an explicit "Original authors" heading in
  `AUTHORS.txt`, not merged into a flat list — the distinction between original and current
  maintainer should be legible.

</specifics>

<deferred>
## Deferred Ideas

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

</deferred>

---

*Phase: 1-Rename and Fail-Closed*
*Context gathered: 2026-07-28*
