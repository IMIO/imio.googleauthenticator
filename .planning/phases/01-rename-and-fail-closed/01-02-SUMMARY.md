---
phase: 01-rename-and-fail-closed
plan: 02
subsystem: i18n
tags: [zope.i18n, i18ndude, plone, gettext, locales, translation]

# Dependency graph
requires:
  - phase: 01-01
    provides: "Package moved to src/imio/googleauthenticator/, MessageFactory calls renamed to imio.googleauthenticator, testing.py/setuphandlers.py rename complete"
provides:
  - "locales/ catalogues live under the renamed domain filenames (imio.googleauthenticator.pot/.po), so the domain rename from 01-01 actually resolves at runtime"
  - "rebuild_i18n.sh fixed and runnable: correct I18NDOMAIN and a working I18NDUDE path"
  - "Three defective English msgids corrected at source"
  - "French and English catalogues added (fr awaiting user review; en is a full-text override by design)"
  - "Two new behavioural i18n tests: test_control_panel_is_translated_nl, test_corrected_msgid_renders_in_english"
affects: [01-03-packaging-and-metadata, 01-04-pas-identity-and-fail-closed]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Domain-level translate() assertions instead of browser-level rendering, to avoid depending on portal_languages test-site configuration"
    - "English override catalogue where every msgstr duplicates its msgid (D-18), so corrected text renders regardless of which resolution path zope.i18n takes"
    - "Catalogue parse-check via pythongettext.msgfmt.Msgfmt(...).get() -- the exact call zope.i18n.compile.compile_mo_file makes -- rather than GNU msgfmt (absent) or bin/pybabel (wrong in both directions on this tree)"

key-files:
  created:
    - src/imio/googleauthenticator/locales/fr/LC_MESSAGES/imio.googleauthenticator.po
    - src/imio/googleauthenticator/locales/en/LC_MESSAGES/imio.googleauthenticator.po
  modified:
    - src/imio/googleauthenticator/locales/imio.googleauthenticator.pot (renamed + regenerated)
    - src/imio/googleauthenticator/locales/nl/LC_MESSAGES/imio.googleauthenticator.po (renamed + resynced)
    - src/imio/googleauthenticator/rebuild_i18n.sh
    - src/imio/googleauthenticator/browser/controlpanel.py
    - src/imio/googleauthenticator/browser/forms/token.py
    - src/imio/googleauthenticator/browser/forms/user_setup.py
    - src/imio/googleauthenticator/browser/forms/reset_bar_code.py
    - src/imio/googleauthenticator/tests/test_generic.py

key-decisions:
  - "Used the ska_secret_key schema field's title (\"Secret Key\" -> \"Geheime Sleutel\") for test_control_panel_is_translated_nl instead of the plan's suggested \"Google Authenticator settings\" msgid -- that msgid is a stale catalogue entry with no corresponding _(...) call anywhere in current source, so task 2's i18ndude rebuild-pot (which extracts from live source only) would have dropped it and broken the test it exists to protect."
  - "rebuild_i18n.sh's I18NDUDE depth fixed from five levels up (resolves outside the repo) to three, per task 1's accepted one-line scope expansion of CONTEXT's deferred verification -- task 2 depends on the script actually running."
  - "English catalogue (D-18) duplicates every msgid as its own msgstr, deliberately -- ships both the source fix and the override so the corrected text renders whichever path zope.i18n takes."
  - "French translation (D-17) covers every msgid in the regenerated catalogue, using standard Belgian-French Plone vocabulary; flagged via a file-header comment as awaiting user review, not self-approved."
  - "Dutch (D-19) translated only the three entries whose msgid text changed as a direct result of this plan's source corrections. The ~19 other msgids the rebuild surfaced (Cancel, Save, Globally enabled, Google Authenticator, the ZCML action/uninstall strings, etc.) were never in the old, stale catalogue at all -- filling them in is out of this plan's stated scope (D-19 only covers invalidated entries) and risks unreviewed mistranslation. Left untranslated and documented below."

requirements-completed: [RENAME-03, RENAME-07]

coverage:
  - id: D1
    description: "Catalogues moved to imio.googleauthenticator.pot / nl/LC_MESSAGES/imio.googleauthenticator.po; no old-domain filename or .mo remains under src/"
    requirement: "RENAME-03"
    verification:
      - kind: unit
        ref: "find src/imio/googleauthenticator/locales -name 'collective.*' (empty); find src -name '*.mo' (empty); git ls-files lists both renamed files"
        status: pass
    human_judgment: false
  - id: D2
    description: "rebuild_i18n.sh runs: I18NDOMAIN=imio.googleauthenticator and I18NDUDE resolves to an existing executable from the package directory (three levels up, not five)"
    requirement: "RENAME-07"
    verification:
      - kind: integration
        ref: "sh rebuild_i18n.sh (run from src/imio/googleauthenticator/) exits 0, produces fr/en catalogues and resyncs nl"
        status: pass
    human_judgment: false
  - id: D3
    description: "Dutch still resolves through the renamed domain -- proven by translate() on a live schema-field msgid, not a stale/dead catalogue entry"
    verification:
      - kind: integration
        ref: "tests/test_generic.py#test_control_panel_is_translated_nl"
        status: pass
    human_judgment: false
  - id: D4
    description: "Three defective English msgids corrected at source (ommit -> omitted; missing 'code' in token form description; trailing space on the token field title, fixed at both source sites)"
    verification:
      - kind: unit
        ref: "grep -rn 'ommit' src/imio/googleauthenticator/ (empty, .pyc regenerated clean); grep for the corrected token.py phrase; grep for the trailing-space title (empty) in both reset_bar_code.py and user_setup.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "Corrected English text renders under target language en -- RESEARCH Open Question 1's resolution, indifferent to which resolution path zope.i18n takes"
    verification:
      - kind: integration
        ref: "tests/test_generic.py#test_corrected_msgid_renders_in_english"
        status: pass
    human_judgment: false
  - id: D6
    description: "All three catalogues (nl, fr, en) compile via the exact call zope.i18n.compile.compile_mo_file makes"
    verification:
      - kind: unit
        ref: "PYTHONPATH=<python_gettext egg> bin/python -c \"...Msgfmt(open(f), f).get()...\" for each of nl/fr/en .po -- all exit 0"
        status: pass
    human_judgment: false
  - id: D7
    description: "French catalogue is a genuine full translation using Belgian-French Plone vocabulary, but is explicitly a review draft, not a merge-ready final -- iMio house terms may differ on some strings"
    verification: []
    human_judgment: true
    rationale: "Translation quality/terminology is a linguistic judgment call the plan itself defers to human review (D-17); automated tests can only prove the catalogue compiles and resolves, not that the wording matches iMio house style."

duration: ~35min
completed: 2026-07-29
status: complete
---

# Phase 1 Plan 2: Locales, translations, and the three defective msgids Summary

**Catalogues moved to the renamed i18n domain filenames with a passing behavioural Dutch-translation test, rebuild_i18n.sh's broken `I18NDUDE` path and stale `I18NDOMAIN` fixed, three defective English msgids corrected at source, and new French (draft, awaiting review) and English (full-text override) catalogues generated through the now-working `i18ndude` wrapper -- suite green at 13 tests.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-07-29T09:10Z (approx, first file reads)
- **Completed:** 2026-07-29T09:24Z
- **Tasks:** 2 completed
- **Files modified:** 9 (2 renamed, 2 created, 5 content-edited)

## Accomplishments
- `locales/collective.googleauthenticator.pot` and `locales/nl/LC_MESSAGES/collective.googleauthenticator.po` `git mv`-ed to the `imio.googleauthenticator` domain filenames (D-13) -- this is what makes plan 01-01's renamed `MessageFactory` calls actually resolve, since the i18n domain comes from the catalogue filename, not from any `i18n_domain` attribute
- `rebuild_i18n.sh` fixed: `I18NDOMAIN` renamed and the `I18NDUDE` path corrected from five levels up (resolves outside the repository) to three (D-15, pre-existing defect, task 2 depends on the script running)
- Three defective msgids corrected at source: the whitelist description's "ommit" -> "omitted" typo (`controlpanel.py`), the missing "code" in the token form description (`token.py`), and a trailing space on the token field title declared at two source sites (`reset_bar_code.py` and `user_setup.py`, both fixed)
- `locales/fr/LC_MESSAGES/imio.googleauthenticator.po` created and fully translated (59 msgids, standard Belgian-French Plone vocabulary), flagged for user review before merge (D-17)
- `locales/en/LC_MESSAGES/imio.googleauthenticator.po` created as a full-text override catalogue -- every msgstr duplicates its (corrected) msgid by design (D-18)
- Dutch resynced against the regenerated template; the three entries invalidated by the msgid corrections re-translated (D-19)
- Two new behavioural tests added: `test_control_panel_is_translated_nl` (domain-rename proof) and `test_corrected_msgid_renders_in_english` (D-18's acceptance test / RESEARCH Open Question 1's resolution)
- All three catalogues (nl, fr, en) verified to compile via `pythongettext.msgfmt.Msgfmt(...).get()`, the exact call `zope.i18n.compile.compile_mo_file` makes
- `bin/test -t '!robot'` green: 13 tests, 0 failures, 0 errors (up from 12 after task 1, 11 before this plan)

## Task Commits

Each task was committed atomically:

1. **Task 1: Move the catalogues to the new domain filenames and prove Dutch still renders** - `7090723` (feat)
2. **Task 2: Correct the defective English msgids, then generate the French and English catalogues** - `8ae0408` (feat)

**Plan metadata:** pending (this commit, `docs(01-02): complete locales and translations plan`)

_Note: Task 1 carried `tdd="true"` in the plan. The single test method (`test_control_panel_is_translated_nl`) was written and run individually before the full-suite check and before commit, but was committed together with its supporting production changes (the `git mv` and `rebuild_i18n.sh` fixes) in one commit rather than split into separate RED/GREEN commits -- the behavior under test (the domain now resolving) and the change that establishes it (the `git mv`) are the same atomic unit of work; splitting them would leave an intermediate commit where the test asserts a domain rename that hasn't happened yet, which is not a meaningful RED state to preserve. See TDD Gate Compliance below._

## Files Created/Modified
- `src/imio/googleauthenticator/locales/imio.googleauthenticator.pot` - renamed from `collective.googleauthenticator.pot`, header `Domain:` corrected, then regenerated by `i18ndude rebuild-pot` in task 2
- `src/imio/googleauthenticator/locales/nl/LC_MESSAGES/imio.googleauthenticator.po` - renamed, then resynced; 3 entries re-translated after the msgid corrections
- `src/imio/googleauthenticator/locales/fr/LC_MESSAGES/imio.googleauthenticator.po` - new, full French translation, awaiting review
- `src/imio/googleauthenticator/locales/en/LC_MESSAGES/imio.googleauthenticator.po` - new, full-text override (msgstr = corrected msgid for every entry)
- `src/imio/googleauthenticator/rebuild_i18n.sh` - `I18NDOMAIN` and `I18NDUDE` path corrected
- `src/imio/googleauthenticator/browser/controlpanel.py` - "ommit" -> "omitted"
- `src/imio/googleauthenticator/browser/forms/token.py` - added "code" to the form description
- `src/imio/googleauthenticator/browser/forms/user_setup.py` - removed trailing space from token field title
- `src/imio/googleauthenticator/browser/forms/reset_bar_code.py` - removed trailing space from token field title (same msgid, second source site)
- `src/imio/googleauthenticator/tests/test_generic.py` - 2 new test methods, 2 new imports

## Decisions Made
- Substituted the "Secret Key" schema-field-title msgid for the plan's suggested "Google Authenticator settings" msgid in `test_control_panel_is_translated_nl` -- see Deviations below, this is the one substantive deviation in this plan.
- Kept the accepted one-line `I18NDUDE` path fix in task 1 as originally scoped by the plan (CONTEXT's Deferred Ideas asked only for verification; the check found a genuine defect, and task 2 needed the script to run).
- Did not attempt to fill in Dutch translations for the ~19 msgids the rebuild-pot step surfaced that were never in the old catalogue at all (see Deviations).
- Did not touch `token.py`'s `.format()`-before-translation construction on the "Invalid data. Details: {0}" status message, despite noticing it makes that msgid dynamic and therefore untranslatable -- per the plan's explicit instruction, this is a real defect but not one of D-18's three, and `token.py` is rewritten wholesale in Phase 7.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in the plan's expected test value] Substituted a live msgid for the plan's suggested stale one in `test_control_panel_is_translated_nl`**
- **Found during:** Task 1 (writing the Dutch-translation behavioural test)
- **Issue:** The plan's `<action>` and `<behavior>` text names `Google Authenticator instellingen` (msgid `Google Authenticator settings`, referenced at `controlpanel.py:28`) as the expected translated value. Grepping current source found no `_(...)` call anywhere producing that msgid -- `controlpanel.py:28` is currently `ska_secret_key = TextLine(`, not a label declaration. The catalogue entry is a stale leftover from an earlier upstream revision (before the control-panel label text changed to just "Google Authenticator"), confirmed by checking the pre-01-01 upstream source. Using it would have made the test pass immediately after task 1's `git mv` (the stale entry is still present at that point) but then silently break after task 2's `i18ndude rebuild-pot` step, which extracts msgids from live source only and would drop an entry with no corresponding call site -- exactly the kind of silent regression this test exists to catch, and task 2's own acceptance criteria requires this test to still pass at 13 tests green.
- **Fix:** Used the `ska_secret_key` schema field's `title` (`Secret Key` -> `Geheime Sleutel`) instead: live in source, discriminates (Dutch differs from English), and untouched by task 2's msgid corrections.
- **Files modified:** `src/imio/googleauthenticator/tests/test_generic.py` (documented inline in the test's docstring)
- **Verification:** `bin/test -t test_control_panel_is_translated_nl` passes both immediately after task 1 and again after task 2's full catalogue regeneration; `bin/test -t '!robot'` green at both 12 (after task 1) and 13 (after task 2) tests.
- **Committed in:** `7090723` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 -- a plan-text/source mismatch that would have silently broken the test it was meant to protect)
**Impact on plan:** No scope creep. The substitution preserves the exact intent stated in the plan (a live, discriminating, task-2-safe msgid) while using a value that actually exists in source. Documented in the test's own docstring for future readers.

## Issues Encountered

**Stale `.pyc` bytecode transiently matched a fixed string.** After correcting "ommit" -> "omitted" in `controlpanel.py`, a `grep -rn 'ommit' src/` briefly matched a stale, gitignored `controlpanel.pyc` compiled before the source edit. Deleted it (Python 2 recompiles automatically; the file is gitignored and untracked, so this had no effect on any commit).

**`.mo` files regenerate on every `bin/test` run.** `zope_i18n_compile_mo_files` is on, so running the test suite writes a compiled `.mo` next to each `.po` in `src/imio/googleauthenticator/locales/**/LC_MESSAGES/`. These are gitignored and untracked, but the plan's literal verify one-liner runs `bin/test` and then immediately checks `find src -name '*.mo'` is empty in the same breath -- an ordering issue in the verify script itself (not something this plan's changes caused). Worked around by deleting the regenerated `.mo` files between test runs and before each commit, matching the task's own instruction ("if one has reappeared, delete it"); this has no effect on the git history since the files are gitignored and were never staged.

**The rebuild-pot step surfaced ~19 previously-never-extracted msgids.** The old, stale `.pot`/`.po` files predate several ZCML actions (`Cancel`, `Save`, `Globally enabled`, `Google Authenticator`, `Disable/Enable two-step verification for all users`, the two "Google Authenticator Plone..." action-title strings, `Uninstall Postlogin Action`, `Forbidden for anonymous`, `Forms for imio.googleauthenticator`, the two "for all users" success messages, `Changes saved.`, `Edit cancelled.`) that were apparently never captured in any prior i18ndude run. These now exist in the regenerated `.pot`/`en`/`fr` catalogues (English is trivially covered since msgstr=msgid; French is fully translated as part of the from-scratch draft) but remain untranslated in Dutch, since D-19 only scopes redoing the entries this plan's own msgid corrections invalidated (three entries), not completing a catalogue whose Dutch was already incomplete for unrelated reasons before this plan touched it. Recorded here rather than silently filled in without a translation review path, and rather than silently ignored.

## TDD Gate Compliance

Task 1 carried `tdd="true"`. `test_control_panel_is_translated_nl` was authored and run individually (`bin/test -t test_control_panel_is_translated_nl`, 1 test, 0 failures) before being folded into the single task-1 commit alongside the `git mv` and `rebuild_i18n.sh` fixes it verifies. No separate `test(...)`-only RED commit exists, because the test can only meaningfully fail (RED) after the domain rename it asserts either hasn't happened or has been done wrong -- both of which are the same production change (the `git mv` + pot header edit) that task 1's own `<action>` bundles into one step. Splitting into RED/GREEN would create an intermediate commit whose "RED" state is "the catalogues haven't been moved yet," which is not informative as a standalone commit. This mirrors 01-01's documented resolution for the same tension.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 01-03 (packaging/metadata) can proceed: nothing this plan touched (`locales/**`, `rebuild_i18n.sh`, the three `browser/**` msgid fixes, `tests/test_generic.py`) overlaps `setup.py`'s packaging fields.
- Plan 01-04 (PAS identity + fail-closed) can proceed: `PAS_ID`, `meta_type`, `PAS_TITLE` untouched by this plan.
- Known gap for future attention (not blocking): the French catalogue is a draft awaiting iMio house-terminology review before merge (D-17's own stated gate). The ~19 pre-existing Dutch gaps documented above are pre-existing, not newly introduced, and are a reasonable target for a future translation-completeness pass if desired.
- No blockers. `bin/test -t '!robot'` is green at 13 tests, 0 failures, 0 errors.

---
*Phase: 01-rename-and-fail-closed*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `src/imio/googleauthenticator/locales/imio.googleauthenticator.pot`
- FOUND: `src/imio/googleauthenticator/locales/nl/LC_MESSAGES/imio.googleauthenticator.po`
- FOUND: `src/imio/googleauthenticator/locales/fr/LC_MESSAGES/imio.googleauthenticator.po`
- FOUND: `src/imio/googleauthenticator/locales/en/LC_MESSAGES/imio.googleauthenticator.po`
- FOUND: `src/imio/googleauthenticator/rebuild_i18n.sh`
- FOUND commit: `7090723` (task 1: move catalogues, prove Dutch renders)
- FOUND commit: `8ae0408` (task 2: correct msgids, add fr/en catalogues)
