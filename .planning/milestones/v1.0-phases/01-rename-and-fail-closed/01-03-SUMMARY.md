---
phase: 01-rename-and-fail-closed
plan: 03
subsystem: packaging
tags: [setuptools, sdist, manifest.in, changelog, makefile, sphinx]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Package moved to src/imio/googleauthenticator/, setup.py name/namespace_packages already renamed"
  - phase: 01-02
    provides: "locales/fr and locales/en catalogues alongside nl, all under the imio.googleauthenticator domain filenames"
provides:
  - "setup.py distribution metadata (version, author, url, license, classifiers) matching the locked decisions"
  - "CHANGES.rst in imio.dms.mail house style, carrying the rename + DOC-04 non-migration notice, upstream history retained below"
  - "LICENSE.txt at the repository root"
  - "MANIFEST.in fully rewritten -- sdist ships profiles, all three locale directories, ZMI templates and static resources, with no .pyc/.mo"
  - "Makefile purge target for post-rename developer cleanup"
  - "Build tooling (.coveragerc, cleanup.sh) and documentation (README.rst, docs/index.rst, docs/conf.py, CLAUDE.md) naming the new package"
  - "318-finding bin/code-analysis baseline recorded in CLAUDE.md and .planning/STATE.md for Phase 8"
affects: [01-04-pas-identity-and-fail-closed, phase-8-quality]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MANIFEST.in rewritten wholesale from a distutils.filelist.FileList-verified template rather than path-substituted, since four independent defects (literal commas, missing CONTRIBUTORS.txt, locales/nl-only scoping, missing global-exclude) needed fixing at once"
    - "bin/check-manifest's remaining diffs (dev/tooling files, not code) recorded with justification rather than chased to exit 0, since it is not wired into bin/code-analysis and the sdist is the actual acceptance surface"

key-files:
  created: []
  modified:
    - setup.py
    - MANIFEST.in
    - CHANGES.rst (renamed from CHANGES.txt)
    - AUTHORS.txt
    - LICENSE.txt (renamed from docs/LICENSE.txt)
    - .coveragerc
    - cleanup.sh
    - Makefile
    - README.rst
    - docs/index.rst
    - docs/conf.py
    - CLAUDE.md
    - .planning/STATE.md

key-decisions:
  - "Task 1's first commit (92fef48) only captured the pure git-mv renames and the examples/ deletion -- a multi-path `git add` failed atomically on an already-renamed pathspec and silently left setup.py/AUTHORS.txt/CHANGES.rst/LICENSE.txt content edits unstaged. Caught before moving to task 2 and corrected with a follow-up commit (9dc6317) rather than an amend, per the no-amend-unless-asked rule. See Deviations."
  - "profiles/default/site_properties.xml left in place per the plan's explicit instruction: dead (byte-identical to propertiestool.xml, RESEARCH O-3) but tied to no requirement or decision; recorded as a Phase 8 observation, not deleted."
  - "Only 0.3.0 (folded 'unreleased' status into the heading) and 0.2.5 (PyPI-verified 2014-06-20) carry a date in the reformatted CHANGES.rst; the remaining upstream headings (0.2.4 down to 0.1) keep their pre-existing but PyPI-unverified dates dropped, per the plan's instruction not to invent/carry forward unverified dates."

requirements-completed: [RENAME-06, RENAME-07, DOC-04]

coverage:
  - id: D1
    description: "setup.py version 1.0.0.dev0, author iMio / support-docs@imio.be, url IMIO/imio.googleauthenticator, license GPL, classifiers corrected (2.6 dropped, Plone 4.3 + GPLv2 added), changelog read from CHANGES.rst, README image-rewrite URL repointed to the IMIO repo"
    requirement: "RENAME-06"
    verification:
      - kind: unit
        ref: "bin/python setup.py --version == '1.0.0.dev0'; bin/python setup.py --long-description | wc -c == 13042 (> 5000); grep -c collective setup.py == 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "CHANGES.rst in house style with a 1.0.0 (unreleased) heading carrying the rename entry, the DOC-04 non-migration notice, and a note that previously-issued signed URLs keep validating; upstream history retained below with resized headings"
    requirement: "DOC-04"
    verification:
      - kind: unit
        ref: "grep '1.0.0 (unreleased)' CHANGES.rst; title/heading underline lengths verified programmatically (9, 18 chars) to match their titles"
        status: pass
    human_judgment: false
  - id: D3
    description: "AUTHORS.txt keeps the four upstream names under an explicit Original authors heading and adds iMio; LICENSE.txt moved to the repository root with the upstream notice intact plus an iMio copyright line"
    verification:
      - kind: unit
        ref: "grep 'Original authors' AUTHORS.txt; test -f LICENSE.txt && test ! -f docs/LICENSE.txt; grep iMio LICENSE.txt"
        status: pass
    human_judgment: false
  - id: D4
    description: "MANIFEST.in rewritten wholesale (comma bug fixed, locales scoped at the directory not nl/, CONTRIBUTORS.txt dropped, LICENSE.txt added, global-exclude for .pyc/.mo); a real sdist build ships the pot, all three locale catalogues, the marker file, registry.xml, the ZMI template and main.css, with no .pyc/.mo path and no 'no files found matching' warning"
    requirement: "RENAME-06"
    verification:
      - kind: integration
        ref: "bin/python setup.py sdist (exit 0, no missing-file warning); tar tzf dist/*.tar.gz verified against 8 required paths + absence of .pyc/.mo"
        status: pass
    human_judgment: true
    rationale: "bin/check-manifest still exits 1 -- its remaining diffs are dev/tooling files (buildout configs, .planning/, .claude/, lint config) legitimately absent from the sdist. Automated checks confirm the sdist is correct; whether the remaining check-manifest diffs are acceptable dev-file noise is a judgment call recorded here for a human to confirm."
  - id: D5
    description: ".coveragerc's [report] include and cleanup.sh's egg-info path renamed; .hgignore and .hg.packed (the third config naming the old egg-info path) deleted; Makefile purge target added (idempotent, tolerant of absent files, listed in make help, verified running twice with no git-status change)"
    requirement: "RENAME-07"
    verification:
      - kind: unit
        ref: "grep 'src/imio/googleauthenticator' .coveragerc; grep 'src/imio.googleauthenticator.egg-info' cleanup.sh; test ! -f .hgignore; make help | grep purge; make purge (twice, exit 0 both times, git status --porcelain unchanged)"
        status: pass
    human_judgment: false
  - id: D6
    description: "README.rst / docs/index.rst renamed (title+underlines, buildout snippet, Forked from line, dead doc links replaced with a single IMIO repo link, TODOS.rst raw link repointed); docs/conf.py Sphinx project/htmlhelp_basename/epub_title renamed; CLAUDE.md naming section inverted and the bin/code-analysis baseline corrected to 318 (184 isort); .planning/STATE.md Blockers/Concerns records the 318 baseline for Phase 8"
    verification:
      - kind: unit
        ref: "grep -c 'Forked from' README.rst == 1; grep imio.googleauthenticator docs/conf.py; grep 318 CLAUDE.md .planning/STATE.md; plan-scoped grep over setup.py/MANIFEST.in/.coveragerc/cleanup.sh (minus RESEARCH false positives) empty"
        status: pass
    human_judgment: false
  - id: D7
    description: "bin/test -t '!robot' remains green at 13 tests, 0 failures, 0 errors throughout all three tasks"
    verification:
      - kind: integration
        ref: "bin/test -t '!robot' (run after each task's changes)"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-07-29
status: complete
---

# Phase 1 Plan 3: Packaging metadata, MANIFEST.in rewrite, build tooling and documentation Summary

**setup.py/CHANGES.rst/AUTHORS.txt/LICENSE.txt now carry the locked distribution identity (version 1.0.0.dev0, iMio authorship, GPL, corrected classifiers) with the DOC-04 non-migration notice; MANIFEST.in was rewritten wholesale and a real sdist build proves it ships the profiles, all three locale catalogues and the ZMI/static resources with no compiled artefacts; a new idempotent `make purge` target, and README/docs/CLAUDE.md/STATE.md now name the package and record the corrected 318-finding lint baseline for Phase 8.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-07-29T07:30Z (approx, first file reads)
- **Completed:** 2026-07-29T07:38Z
- **Tasks:** 3 completed
- **Files modified:** 13 (2 renamed/moved, 1 deleted directory, 2 deleted files, ~10 content-edited)

## Accomplishments
- `setup.py`: version `1.0.0.dev0`, `author='iMio'`/`author_email='support-docs@imio.be'`, `url` repointed at the IMIO repo, `license='GPL'`, Python 2.6 classifier dropped, `Framework :: Plone :: 4.3` and the GPLv2 classifier added, changelog `open()` repointed to `CHANGES.rst`, README image-rewrite URL repointed at the IMIO repo
- `CHANGES.txt` -> `CHANGES.rst`, reformatted to `imio.dms.mail`'s house style: a new `1.0.0 (unreleased)` heading (18-char underline, verified) carrying the rename entry, the DOC-04 public-facing non-migration notice (existing databases discarded, not migrated -- recreate the site and re-enrol users), and a note that previously-issued signed token URLs keep validating; full upstream history retained below with headings resized to their own title length, `0.3.0`'s parenthesised release-state folded into its heading, and `0.2.5` dated `(2014-06-20)` from the verified PyPI record
- `AUTHORS.txt`: the four upstream names under an explicit `Original authors` heading, iMio added under `Current maintainer`
- `docs/LICENSE.txt` -> `LICENSE.txt` at the repo root; upstream copyright notice kept verbatim on line 1, an iMio copyright line added on line 2
- `examples/` deleted (upstream's demo buildout, confirmed unreferenced by a repo-wide grep before deletion)
- `MANIFEST.in` fully rewritten from the RESEARCH-verified template: the comma bug on the pattern line fixed, the locales include rescoped from `nl/` to the `locales/` directory (so plan 01-02's `fr/` and `en/` catalogues ship), the nonexistent `CONTRIBUTORS.txt` include dropped, `LICENSE.txt` added, `global-exclude *.pyc`/`*.mo` added
- Real `bin/python setup.py sdist` build: exits 0, no `no files found matching` warning, archive contains the `.pot`, all three `locales/{nl,fr,en}/LC_MESSAGES/*.po`, `profiles/default/imio.googleauthenticator.marker.txt`, `profiles/default/registry.xml`, `www/add_google_authenticator_form.zpt`, `browser/static/main.css`, and no `.pyc`/`.mo` path
- `bin/check-manifest` still exits 1; its remaining diffs are dev/tooling files (`.coveragerc`, `Makefile`, `base.cfg`, `checkouts.cfg`, `test-4.3.cfg`, `.isort.cfg`, `.planning/**`, `.claude/**`) that are legitimately absent from the sdist -- recorded here with justification, not chased to a clean exit (RESEARCH C-5: it is not wired into `bin/code-analysis`)
- `.coveragerc`'s `[report] include` and `cleanup.sh`'s egg-info path renamed to the new package location (Phase 8/QUAL-01 owns the rest of `.coveragerc`)
- `.hgignore` and `.hg.packed` deleted -- dead Mercurial leftovers, and `.hgignore` was the third config naming the old egg-info path (RENAME-07)
- New `Makefile` `purge` target: removes stale `.pyc` under the old namespace, the old egg-info directory, and the local database (`var/filestorage/Data.fs` + `var/blobstorage`); listed in `make help`; verified idempotent -- running it twice exits 0 both times with no change to `git status --porcelain`
- `README.rst` / `docs/index.rst`: title and both underlines renamed (24 chars, matching), a "Forked from collective.googleauthenticator" line added, the buildout install snippet renamed, the two dead documentation-host links (readthedocs, pythonhosted) replaced with a single link to the IMIO repository, the `TODOS.rst` raw-content link repointed at the IMIO repo. The `PAS_TITLE` quote at both files' line 129/131 is left untouched -- plan 01-04's commit
- `docs/conf.py`: Sphinx `project`, `htmlhelp_basename`, `epub_title` and the commented `epub_basename` renamed
- `CLAUDE.md`: naming section inverted (repo and package now agree, in the current dotted name), the `bin/code-analysis` finding count corrected from the stale "~40" to the measured **318** (184 of them isort findings, actively perturbed by the rename), and the marker-file reference renamed
- `.planning/STATE.md`'s `### Blockers/Concerns` list carries a new bullet recording the 318-finding baseline for Phase 8 (QUAL-06), per RESEARCH Open Question 4
- `bin/test -t '!robot'` green at 13 tests, 0 failures, 0 errors, checked after every task

## Task Commits

Each task was committed atomically (task 1 required a follow-up correction commit -- see Deviations):

1. **Task 1: Distribution metadata, changelog, attribution and licence placement** - `92fef48` (feat, incomplete) + `9dc6317` (fix, completes the content edits)
2. **Task 2: Rewrite MANIFEST.in and prove the sdist ships the profiles, catalogues and templates** - `662dd85` (feat)
3. **Task 3: Build tooling, the developer purge target, and the documentation that names the package** - `ca96f01` (feat)

**Plan metadata:** pending (this commit, `docs(01-03): complete packaging and metadata plan`)

## Files Created/Modified
- `setup.py` - version, author/author_email, url, license, classifiers, changelog filename, README image-rewrite URL
- `CHANGES.rst` - renamed from `CHANGES.txt`, reformatted to house style, new `1.0.0 (unreleased)` section
- `AUTHORS.txt` - `Original authors` heading, iMio current-maintainer entry
- `LICENSE.txt` - moved from `docs/`, iMio copyright line added
- `MANIFEST.in` - full rewrite
- `.coveragerc` - `[report] include` path
- `cleanup.sh` - egg-info path
- `Makefile` - new `purge` target
- `README.rst` / `docs/index.rst` - title, underlines, Forked-from line, buildout snippet, doc links
- `docs/conf.py` - Sphinx `project`, `htmlhelp_basename`, `epub_title`, commented `epub_basename`
- `CLAUDE.md` - naming section, `bin/code-analysis` finding count, marker-file reference
- `.planning/STATE.md` - Blockers/Concerns bullet recording the 318-finding baseline
- `.hgignore`, `.hg.packed` - deleted
- `examples/` - deleted

## Decisions Made
- Followed the plan's MANIFEST.in replacement verbatim rather than path-substituting the existing file, per RESEARCH's measured `distutils.filelist.FileList` diff (+5/-1 files, four independent defects).
- Kept `profiles/default/site_properties.xml` in place despite it being dead code (RESEARCH O-3) -- the plan explicitly scopes its deletion out of this phase, recorded here as an observation for Phase 8.
- Only folded verified dates into the `0.3.0` (unreleased) and `0.2.5` (2014-06-20, PyPI-verified) changelog headings; the other upstream headings' pre-existing but PyPI-unverified dates were dropped rather than carried forward, per the plan's "do not invent dates" instruction.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, self-caught before task 2] Task 1's first commit silently dropped its own content edits**
- **Found during:** Task 1, immediately after committing `92fef48` and moving to task 2's read-only verification
- **Issue:** `git commit --no-verify` for task 1 was preceded by `git add setup.py CHANGES.rst AUTHORS.txt LICENSE.txt CHANGES.txt docs/LICENSE.txt examples`. `git add` treats a multi-path invocation atomically: because `CHANGES.txt` no longer existed on disk (already `git mv`-ed to `CHANGES.rst` earlier in the same task), the whole command failed with `fatal: pathspec 'CHANGES.txt' did not match any files` and staged **none** of the listed paths. The subsequent `git status --short` output was misread as confirming a clean stage (it showed the *pre-existing* staged state from the earlier `git mv`/`git rm` calls, with the real content edits appearing as unstaged ` M` rather than staged `M `), so the commit went through containing only the pure `git mv` renames and the `examples/` deletion -- none of `setup.py`'s metadata, `CHANGES.rst`'s reformatted content, `AUTHORS.txt`'s new heading, or `LICENSE.txt`'s added copyright line.
- **Fix:** Caught before starting task 2 by re-running the task 1 acceptance checks against the actual commit (`git show --stat 92fef48`), which showed only renames/deletions and no content diffs. Staged the four files individually (`git add setup.py AUTHORS.txt CHANGES.rst LICENSE.txt`, this time confirmed via `git status --short` showing `M ` not ` M`) and committed the missing content as a new commit rather than amending, per the no-amend-unless-requested rule.
- **Files modified:** `setup.py`, `AUTHORS.txt`, `CHANGES.rst`, `LICENSE.txt` (all already-correct working-tree content; only the git staging was fixed)
- **Verification:** Re-ran task 1's full acceptance criteria (`bin/python setup.py --version`, `--long-description` byte count, `grep` checks on all four files) against the corrected `HEAD` and confirmed all pass; `bin/test -t '!robot'` still green at 13 tests.
- **Committed in:** `9dc6317`

---

**Total deviations:** 1 self-caught and fixed (Rule 1 -- a git-staging bug that silently produced an incomplete commit, corrected before any downstream task depended on it)
**Impact on plan:** No lost work and no scope creep -- the working-tree content was always correct; only the commit history needed a follow-up commit to actually contain it. All of task 1's acceptance criteria pass against the corrected two-commit sequence.

## Issues Encountered

None beyond the git-staging deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-04 (PAS identity + fail-closed) can proceed: `PAS_ID`, `meta_type`, `PAS_TITLE`, and the `README.rst`/`docs/index.rst` line quoting `PAS_TITLE` are all untouched by this plan, exactly as scoped.
- Plan 01-04 task 1 owns the phase-wide acceptance grep (the one that also covers `src/`) -- this plan's plan-scoped grep (`setup.py`, `MANIFEST.in`, `.coveragerc`, `cleanup.sh`, minus RESEARCH's false positives) is clean.
- Phase 8 (QUAL-01, QUAL-06) has what it needs: `.coveragerc`'s `[report] include` is renamed (ready for QUAL-01's full rewrite), and both `CLAUDE.md` and `.planning/STATE.md` record the corrected 318-finding `bin/code-analysis` baseline.
- No blockers. `bin/test -t '!robot'` is green at 13 tests, 0 failures, 0 errors. `bin/python setup.py sdist` builds cleanly with the ship-ready `MANIFEST.in`.

---
*Phase: 01-rename-and-fail-closed*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `setup.py`, `MANIFEST.in`, `CHANGES.rst`, `AUTHORS.txt`, `LICENSE.txt`
- FOUND: `.coveragerc`, `cleanup.sh`, `Makefile`, `README.rst`, `docs/index.rst`, `docs/conf.py`
- FOUND: `CLAUDE.md`, `.planning/STATE.md`
- CONFIRMED ABSENT: `.hgignore`, `.hg.packed`, `examples/`
- FOUND commit: `92fef48` (task 1, incomplete stage)
- FOUND commit: `9dc6317` (task 1 correction commit)
- FOUND commit: `662dd85` (task 2: MANIFEST.in rewrite)
- FOUND commit: `ca96f01` (task 3: build tooling + documentation)
