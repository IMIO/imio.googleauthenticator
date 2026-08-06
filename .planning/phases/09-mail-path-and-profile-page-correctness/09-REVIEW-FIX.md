---
phase: 09-mail-path-and-profile-page-correctness
fixed_at: 2026-08-06T13:29:11Z
review_path: .planning/phases/09-mail-path-and-profile-page-correctness/09-REVIEW.md
iteration: 1
findings_in_scope: 2
fixed: 2
skipped: 0
status: all_fixed
---

# Phase 9: Code Review Fix Report

**Fixed at:** 2026-08-06T13:29:11Z
**Source review:** .planning/phases/09-mail-path-and-profile-page-correctness/09-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 2 (WR-01, WR-02 — the two Warning findings; IN-01 was explicitly out of
  scope per the fix task and was not touched)
- Fixed: 2
- Skipped: 0

## Fixed Issues

### WR-01: Mail-template `.format()` re-substitution can still 500 past the widened catch

**Files modified:**
`src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py`,
`src/imio/googleauthenticator/tests/test_request_bar_code_reset.py`
**Commit:** `b9c7486`
**Applied fix:** Took the catch-tuple option from REVIEW.md's Fix section rather than the
template refactor, per the task's explicit scoping — the refactor touches
`request_bar_code_reset_email.pt`, outside this phase's declared file set, and Phase 12 inherits
whichever shape lands here. Added `KeyError` and `IndexError` to the inner
`except (SMTPException, socket.error):` tuple at
`browser/forms/request_bar_code_reset.py:138`, with a source comment recording why those two
exceptions belong on the inner clause (the `.format()` call) rather than the outer
`except ValueError:` (the `host.send()` failure modes). Added a regression test,
`test_a_stray_curly_brace_in_the_mail_body_reports_in_page_not_a_500`, reusing the existing
`_submit_reset_request` harness (not the failing-send variant — the `.format()` call raises
before `host.send()` is ever reached) with `email_from_name=u'iMio {Team}'`. Non-vacuity
confirmed: against the unfixed source the test errored with an unhandled
`KeyError: u'Team'` escaping out of `handleSubmit`; against the fix it passes, asserting the
in-page failure message and that no mail was ever handed to `MailHost`. Source was restored
byte-identical between the two runs before committing.

### WR-02: `get_token_description()` relies on an unenforced character-set invariant, not escaping

**Files modified:** `src/imio/googleauthenticator/helpers.py`,
`src/imio/googleauthenticator/tests/test_helpers.py`
**Commit:** `30a70f1`
**Applied fix:** Added `from xml.sax.saxutils import escape` (placed alphabetically between
`urlparse` and `zope.component` per this project's isort settings — `bin/code-analysis` confirms
0 exit). In `get_token_description()`, both interpolated values are now escaped at the point of
`.format()`: `secret=escape(secret)` and `url=escape(get_barcode_image(...), {'"': '&quot;'})`.
The `url` value additionally escapes `"` via the `entities` mapping argument, verified in this
project's Python 2.7 to work as documented (`xml.sax.saxutils.escape`'s default entity map covers
`&`/`<`/`>` only; passing `{'"': '&quot;'}` extends it) — load-bearing because `url` lands inside
a double-quoted `src="..."` attribute. A one-line comment records that the escaping is
deliberate because the description is rendered as `structure`. Added a regression test,
`test_get_token_description_escapes_html_metacharacters_in_secret` in `TestSeedEncryption`
(`test_helpers.py`), which monkeypatches `helpers.get_or_create_secret` to return
`'<script>alert(1)</script>'` (standing in for a future code path that could violate the
base32-only invariant) and asserts the raw string is absent from the returned HTML while its
escaped form is present. Non-vacuity confirmed: against the unfixed source the test failed with
the raw `<script>alert(1)</script>` found unescaped in the rendered output; against the fix it
passes. Source was restored byte-identical between the two runs before committing.

## Skipped Issues

None — both in-scope findings were fixed.

## Notes on scope

- **IN-01** (`RequestBarCodeResetForm.updateFields` no-op override) was deliberately not touched,
  per the fix task's explicit instruction: it is Info-severity dead code and deleting a form
  method in a package this size was judged not worth the regression risk at this point in the
  phase.
- No template refactor of `request_bar_code_reset_email.pt` was performed for WR-01 — the
  catch-tuple fix was chosen instead, per the task's explicit rationale (file outside this
  phase's declared `files_modified`; Phase 12 inherits this shape).
- The widened catch on the mail path was not extended to any authentication path;
  `_dont_swallow_my_exceptions = True` (live since Phase 1) is untouched.

## Verification

- `bin/test -t test_request_bar_code_reset`: 6 tests, 0 failures, 0 errors (5 pre-existing + 1 new)
- `bin/test -t test_helpers`: 28 tests, 0 failures, 0 errors (27 pre-existing + 1 new)
- `bin/test -t test_user_setup`: 10 tests, 0 failures, 0 errors (unchanged)
- `bin/test -t '!robot'`: **142 tests, 0 failures, 0 errors** — the constraint text anticipated
  "140 tests, 0 failures, 0 errors" (the pre-fix baseline, independently confirmed in this run
  before any edit), but the same constraint block also mandates one regression test per fix;
  142 = 140 baseline + 2 new regression tests, which is the expected and correct count once both
  mandatory tests are added, not a discrepancy.
- `bin/code-analysis`: exits 0 (re-run after each edit and again after both commits)
- Both regression tests passed their non-vacuity check: each was run against the unfixed source
  first (confirmed to fail/error for the exact reason the finding describes), then the source was
  restored byte-identical via `cp` before re-applying the real fix and committing.
- Both commits went through the real `bin/code-analysis` pre-commit hook (no `--no-verify`).

## Environment note

This run executed inside an isolated git worktree (`gsd-reviewfix/09-<pid>` branch), per this
agent's isolation protocol. Because `bin/test`/`bin/code-analysis` are buildout-generated scripts
hardcoding the main checkout's absolute `src/` path (and the `imio.googleauthenticator.egg-info`
metadata `z3c.autoinclude` needs to resolve the package is likewise gitignored/untracked), two
throwaway wrapper scripts were used to run the exact same buildout-pinned eggs against the
worktree's copy of `src/` instead: the main checkout's own `src/` and its test/lint configuration
were never touched, and the wrappers were discarded with the worktree at cleanup.

---

_Fixed: 2026-08-06T13:29:11Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
