---
status: complete
phase: 01-rename-and-fail-closed
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md]
started: 2026-07-29T08:56:15Z
updated: 2026-07-29T09:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. French catalogue wording matches iMio house style
expected: French catalogue is a genuine full translation using Belgian-French Plone vocabulary, but is explicitly a review draft, not merge-ready final — iMio house terms may differ on some strings. Automated tests prove it compiles and resolves; only a human can confirm the wording.
result: pass
reported: "I updated the .po file with the translation I want"
resolution: |
  User replaced "bar-code" with "MFA" across 13 French strings, settling the house
  terminology the draft deferred. Re-verified after the edit: all three catalogues
  (fr, nl, en) compile via pythongettext.Msgfmt — the exact call zope.i18n.compile
  makes — and the fr catalogue's 60 entries have 0 {N} placeholder mismatches
  between msgid and msgstr.
coverage_id: D7 (01-02)
reason_for_human: human_judgment

### 2. Remaining bin/check-manifest diffs are acceptable dev-file noise
expected: A real sdist build ships the pot, all three locale catalogues, the marker file, registry.xml, the ZMI template and main.css, with no .pyc/.mo path and no "no files found matching" warning. bin/check-manifest still exits 1 — its remaining diffs are dev/tooling files (buildout configs, .planning/, .claude/, lint config) legitimately absent from the sdist. Confirm that residual exit-1 is acceptable.
result: pass
reported: "treat it as noise"
resolution: |
  Decision: bin/check-manifest's exit 1 is accepted as dev-file noise and NOT
  silenced. Its suggested rules (include *.md, *.sh, base.cfg, checkouts.cfg,
  test-4.3.cfg) would ship buildout and planning files inside the release.

  Re-verified at UAT time on current HEAD: bin/python setup.py sdist exits 0 and
  the archive contains the pot, all three .po catalogues, the marker file, all
  four GenericSetup registry XMLs, the ZMI .zpt and main.css — with no .pyc and
  no .mo. The single build warning ("no previously-included files matching
  '*.pyc' found") is the global-exclude matching nothing, which is the desired
  state.

  Everything check-manifest reports as missing from the sdist is dev/tooling:
  .claude/, .planning/, .coveragerc, .isort.cfg, CLAUDE.md, Makefile, base.cfg,
  checkouts.cfg, test-4.3.cfg, builddocs.sh, cleanup.sh.
coverage_id: D4 (01-03)
reason_for_human: human_judgment

### 3. ZMI walkthrough: google_auth listed under Authentication
expected: Run `bin/instance fg`, wait for "Zope Ready to handle requests" with no startup error. Create a Plone site through the browser UI, install the add-on, then open acl_users → plugins → Authentication and confirm `google_auth` is listed. The executor confirmed clean startup but could not do the interactive browser half; the automated test test_plugin_is_registered_for_authentication is the behavioural proxy.
result: pass
reported: "pass"
resolution: |
  User performed the interactive ZMI walkthrough and confirmed google_auth is
  listed under acl_users → plugins → Authentication. This closes RESEARCH
  assumption A5's untested baseline: bin/instance starts cleanly on this tree,
  so a future instance-startup problem will not be mistaken for a
  rename/fail-closed defect. The automated proxy (test 29,
  test_plugin_is_registered_for_authentication) is now backed by the literal
  browser check the plan asked for.
coverage_id: D5 (01-04)
reason_for_human: human_judgment

### 4. Package moved to src/imio/googleauthenticator/, suite green under new name
expected: Package moved to src/imio/googleauthenticator/, buildout regenerated, and the pre-existing 8-test suite green under the new name
result: pass
source: automated
coverage_id: D1 (01-01)

### 5. Every dotted reference renamed to imio.googleauthenticator
expected: Every dotted reference (imports, MessageFactory, logger names, ZCML attributes, GenericSetup XML) renamed to imio.googleauthenticator
result: pass
source: automated
coverage_id: D2 (01-01)

### 6. GenericSetup marker file renamed alongside its setuphandlers.py string
expected: GenericSetup marker file renamed alongside the setuphandlers.py string it is compared against
result: pass
source: automated
coverage_id: D3 (01-01)

### 7. ++resource++ prefix agreement across registries
expected: ++resource++ prefix agreement across resourceDirectory name, jsregistry.xml (2 ids), cssregistry.xml, and skins.xml
result: pass
source: automated
coverage_id: D4 (01-01)

### 8. base.cfg / setup.py package name regenerated
expected: base.cfg package-name / [code-analysis] directory, setup.py name/namespace_packages regenerated via bin/buildout -N
result: pass
source: automated
coverage_id: D5 (01-01)

### 9. Orphan .pyc, stale egg-info and egg-link purged
expected: Orphan .pyc, stale egg-info and stale egg-link purged; exactly one develop-egg and one egg-info remain
result: pass
source: automated
coverage_id: D6 (01-01)

### 10. upgrades/ deleted with its ZCML include, no ConfigurationError
expected: upgrades/ deleted along with its ZCML include; layer setup completes with no ConfigurationError
result: pass
source: automated
coverage_id: D7 (01-01)

### 11. PAS registration asserted via listPlugins(IAuthenticationPlugin)
expected: New test asserts PAS registration via listPlugins(IAuthenticationPlugin), catching a Broken plugin or marker-file mismatch that objectIds() cannot see
result: pass
source: automated
coverage_id: D8 (01-01)

### 12. imio namespace declaration byte-identical to imio.helpers
expected: Namespace declaration byte-identical to imio.helpers, proven by pkg_resources assertion, no imio.helpers dependency added
result: pass
source: automated
coverage_id: D9 (01-01)

### 13. Catalogues moved to the imio.googleauthenticator domain filenames
expected: Catalogues moved to imio.googleauthenticator.pot / nl/LC_MESSAGES/imio.googleauthenticator.po; no old-domain filename or .mo remains under src/
result: pass
source: automated
coverage_id: D1 (01-02)

### 14. rebuild_i18n.sh resolves I18NDUDE and the renamed domain
expected: rebuild_i18n.sh runs: I18NDOMAIN=imio.googleauthenticator and I18NDUDE resolves to an existing executable from the package directory (three levels up, not five)
result: pass
source: automated
coverage_id: D2 (01-02)

### 15. Dutch resolves through the renamed domain
expected: Dutch still resolves through the renamed domain — proven by translate() on a live schema-field msgid, not a stale/dead catalogue entry
result: pass
source: automated
coverage_id: D3 (01-02)

### 16. Three defective English msgids corrected at source
expected: Three defective English msgids corrected at source (ommit → omitted; missing 'code' in token form description; trailing space on the token field title, fixed at both source sites)
result: pass
source: automated
coverage_id: D4 (01-02)

### 17. Corrected English text renders under target language en
expected: Corrected English text renders under target language en — RESEARCH Open Question 1's resolution, indifferent to which resolution path zope.i18n takes
result: pass
source: automated
coverage_id: D5 (01-02)

### 18. All three catalogues compile via zope.i18n's exact call
expected: All three catalogues (nl, fr, en) compile via the exact call zope.i18n.compile.compile_mo_file makes
result: pass
source: automated
coverage_id: D6 (01-02)

### 19. setup.py metadata rewritten for iMio
expected: setup.py version 1.0.0.dev0, author iMio / support-docs@imio.be, url IMIO/imio.googleauthenticator, license GPL, classifiers corrected (2.6 dropped, Plone 4.3 + GPLv2 added), changelog read from CHANGES.rst, README image-rewrite URL repointed to the IMIO repo
result: pass
source: automated
coverage_id: D1 (01-03)

### 20. CHANGES.rst in house style with 1.0.0 (unreleased)
expected: CHANGES.rst in house style with a 1.0.0 (unreleased) heading carrying the rename entry, the DOC-04 non-migration notice, and a note that previously-issued signed URLs keep validating; upstream history retained below with resized headings
result: pass
source: automated
coverage_id: D2 (01-03)

### 21. AUTHORS.txt attribution kept, LICENSE.txt at repo root
expected: AUTHORS.txt keeps the four upstream names under an explicit Original authors heading and adds iMio; LICENSE.txt moved to the repository root with the upstream notice intact plus an iMio copyright line
result: pass
source: automated
coverage_id: D3 (01-03)

### 22. .coveragerc / cleanup.sh paths renamed, make purge added
expected: .coveragerc's [report] include and cleanup.sh's egg-info path renamed; .hgignore and .hg.packed deleted; Makefile purge target added (idempotent, tolerant of absent files, listed in make help, verified running twice with no git-status change)
result: pass
source: automated
coverage_id: D5 (01-03)

### 23. README / docs / CLAUDE.md renamed, 318 baseline recorded
expected: README.rst / docs/index.rst renamed (title+underlines, buildout snippet, Forked from line, dead doc links replaced with a single IMIO repo link, TODOS.rst raw link repointed); docs/conf.py Sphinx project/htmlhelp_basename/epub_title renamed; CLAUDE.md naming section inverted and the bin/code-analysis baseline corrected to 318 (184 isort); .planning/STATE.md records the 318 baseline for Phase 8
result: pass
source: automated
coverage_id: D6 (01-03)

### 24. Suite green at 13 tests throughout plan 01-03
expected: bin/test -t '!robot' remains green at 13 tests, 0 failures, 0 errors throughout all three tasks
result: pass
source: automated
coverage_id: D7 (01-03)

### 25. meta_type / PAS_TITLE renamed to iMio, PAS_ID unchanged
expected: pas_plugin.py's meta_type and setuphandlers.py's PAS_TITLE renamed to iMio (parenthesised distro name), PAS_ID='google_auth' byte-identical to before; ZMI add-form heading and README.rst/docs/index.rst quoted title updated to match; isolated commit touching only these 5 files
result: pass
source: automated
coverage_id: D1 (01-04)

### 26. Phase-wide acceptance grep for the old namespace returns empty
expected: Phase-wide acceptance grep (old namespace across src/, setup.py, MANIFEST.in, .coveragerc, cleanup.sh, minus RESEARCH Section F false positives) returns empty — the phase gate plan 01-04 owns
result: pass
source: automated
coverage_id: D2 (01-04)

### 27. _dont_swallow_my_exceptions = True, exception escapes PAS
expected: _dont_swallow_my_exceptions = True added to GoogleAuthenticatorPlugin with a comment naming the fallthrough it prevents; test_plugin_exception_is_not_swallowed injects a ValueError through is_whitelisted_client and asserts it escapes acl_users._extractUserIds instead of falling through to source_users
result: pass
source: automated
coverage_id: D3 (01-04)

### 28. Suite green and repeatable after the fail-closed flag landed
expected: Full suite green and repeatable after the fail-closed flag landed: 15 tests, 0 failures, 0 errors, run twice in a row with identical results, proving the collaborator patch and the counterfactual's attribute deletion both restore state correctly
result: pass
source: automated
coverage_id: D4 (01-04)

### 29. google_auth still listed under IAuthenticationPlugin after rename
expected: test_plugin_is_registered_for_authentication (carried over from plan 01-01, still passing) confirms google_auth is listed under IAuthenticationPlugin after the meta_type rename — the behavioural proxy for the ZMI check in test 3
result: pass
source: automated
coverage_id: D6 (01-04)

## Summary

total: 29
passed: 29
issues: 0
pending: 0
skipped: 0
blocked: 0

## Notes

**Code review fixes landed after these SUMMARYs were written.** `01-VERIFICATION.md`
(status `gaps_found`) recorded one gap: three unguarded crash paths that
`_dont_swallow_my_exceptions = True` turned into 500s — the same CR-01/CR-02/CR-03
findings in `01-REVIEW.md`. All three were fixed and committed after verification ran:

| Gap path | Fix commit |
|----------|-----------|
| `pas_plugin.py` unknown username → `AttributeError` | `0018bca` (+ test fix `c556eab`) |
| `helpers.py` malformed `X-Forwarded-For` → `ValueError` | `e6d9e57` |
| `helpers.py` blank line in IP whitelist → `ValueError` | `316d636` |

Four Warning-severity findings were also fixed (`5156972`, `d4c2a99`, `24e58c4`,
`719884e`). Regression tests were added for each Critical fix; suite verified green at
**21 tests, 0 failures, 0 errors** on committed HEAD.

The `01-VERIFICATION.md` gap is therefore stale — it describes code that no longer
exists. It must be re-run (`/gsd-verify-work` completion re-checks it) before the phase
can transition.

## Gaps

[none yet]
