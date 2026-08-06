---
phase: 09-mail-path-and-profile-page-correctness
verified: 2026-08-06T13:37:51Z
status: human_needed
score: 8/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Enrol a test user at @@setup-two-factor-authentication on a running instance (bin/instance fg, with IMIO_GOOGLEAUTHENTICATOR_SEED_KEY exported first). Copy the base32 setup key shown beside the QR code as text (not by scanning the image). Enter it into a desktop TOTP client or password manager as a manually-entered setup key. Log out, log in, and submit the code that client shows."
    expected: "The site accepts the code the real TOTP client produced from the copied base32 secret."
    why_human: "Roadmap success criterion 4's second half requires driving a real third-party TOTP client against a live instance -- not automatable in this test suite. Plan 09-04 recorded this as blocked, not passed: no human operator drove it, and bin/instance in this environment has no IMIO_GOOGLEAUTHENTICATOR_SEED_KEY set. This is a locked-open gap, not a code defect."
  - test: "Confirm the two flagged-unverified prohibitions in 09-01-PLAN.md and 09-03-PLAN.md are acceptable as evidenced: (1) the widened except tuple in request_bar_code_reset.py is not extended onto pas_plugin.py's authentication path; (2) get_token_description() does not log, email, or newly persist the seed, and calls get_or_create_secret exactly once with no overwrite-default change."
    expected: "Human sign-off that the verifier's source-reading evidence (below) satisfies both prohibitions."
    why_human: "Both prohibitions are declared verification: unverified / status: flagged-unverified in PLAN frontmatter -- judgment-tier items that this workflow routes to human sign-off rather than an automated gate. The verifier confirmed by reading: pas_plugin.py has a zero-line diff since before this phase (git diff 867280f..HEAD -- pas_plugin.py is empty) and _dont_swallow_my_exceptions = True is still present at line 160; get_token_description() (helpers.py:331-370) calls get_or_create_secret(user, overwrite=overwrite_secret) exactly once, adds no logger call and no new setMemberProperties/setProperty write (confirmed by diff grep), and the QR + text both derive from the same single call."
---

# Phase 9: Mail Path and Profile-Page Correctness Verification Report

**Phase Goal:** The bar-code reset email fails the way every other failure on that form fails, an
administrator cannot be tricked into clearing their own second factor from someone else's
profile, and the enrollment page hands the user a secret they can actually use.
**Verified:** 2026-08-06T13:37:51Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | BUG-07: a refused-recipient mail send reports the shared in-page error message, no error page, success message cannot co-fire | ✓ VERIFIED | `request_bar_code_reset.py:138-157` — `except (SMTPException, socket.error, KeyError, IndexError):` (no re-raise), success `IStatusMessage` call at lines 134-137 sits inside the inner `try:` immediately after `host.send(...)`. `bin/test -t test_a_refused_recipient_reports_in_page_not_an_error_page` — 1 test, 0 failures (run live). |
| 2 | BUG-07: an unreachable mail server (`socket.error`, not `SMTPException`) takes the identical path | ✓ VERIFIED | Same catch tuple includes `socket.error` explicitly. `bin/test -t test_an_unreachable_mail_server_reports_the_same_failure` — pass (run live, part of the 5-test batch below). |
| 3 | BUG-07: `bar_code_reset_token` write is not rolled back on send failure (D-12) | ✓ VERIFIED | `request_bar_code_reset.py:86` writes the token before the inner `try:` at line 89; the widened `except` at line 138 has no compensating write. Test asserts the property is non-empty after a failed send (per 09-01-PLAN.md behavior spec; SUMMARY confirms). |
| 4 | BUG-08: `@@user-information`'s `enable_two_factor_authentication` description offers no link that acts on the viewing administrator's own account | ✓ VERIFIED | `userdataschema.py:83-87` description is now `_('Enable/disable the two-step verification.')` — no `<a `, no `@@setup-two-factor-authentication`, no `@@disable-two-factor-authentication`. `CustomizedUserDataPanel.omit()` (lines 38-42) still covers only `@@personal-information`, confirming `@@user-information` is the sole renderer. `bin/test -t test_enable_flag_description_offers_no_wrong_account_links` — pass (run live). |
| 5 | UX-01: the recovery-codes page's only link targets the navigation root, reads "Continue to the home page", and the ten one-time recovery codes still render in the same response (RECOV-03 guard) | ✓ VERIFIED | `recovery_codes.pt:35-36` — `href="string:${context/@@plone/navigationRootUrl}"`, text "Continue to the home page". `bin/test -t test_recovery_codes_page_links_to_the_home_page` — pass (run live); test asserts anchor `href` equals the live `@@plone` view's `navigationRootUrl()`, absence of "Continue to your profile" and `@@personal-information`, and presence of all issued codes in the same markup. |
| 6 | UX-01: `user_setup.py`'s success path is untouched — `redirect_url` still stays `None`, T-03-23 refusal redirect untouched (D-03) | ✓ VERIFIED | `git diff 867280f..HEAD -- src/imio/googleauthenticator/browser/forms/user_setup.py` is empty — zero lines changed. |
| 7 | UX-02: the enrollment page's `qr_code` field description carries the base32 secret as selectable text beside the QR, produced from exactly one `get_or_create_secret()` call | ✓ VERIFIED | `helpers.py:353` — single `secret = get_or_create_secret(user, overwrite=overwrite_secret)` call, reused for both `get_barcode_image(...)` (line 366) and the `<code>{secret}</code>` text (line 369-370). `bin/test -t test_setup_form_shows_the_secret_as_selectable_text` — pass (run live). |
| 8 | UX-02: the rendered secret and QR URL are HTML-escaped at the point of interpolation (review-fix WR-02), and only the base32 secret is shown, not the `otpauth://` URI | ✓ VERIFIED | `helpers.py:365-370` — `escape(get_barcode_image(...), {'"': '&quot;'})` and `escape(secret)`; the `otpauth://` string only appears inside `get_barcode_image()`'s QR-image construction (helpers.py:239), never in the returned description text. `bin/test -t test_get_token_description_escapes_html_metacharacters_in_secret` — pass (run live). |
| 9 | UX-02 (full criterion 4, second half): a real desktop TOTP client fed the displayed secret produces codes the site accepts | ⬜ NOT AUTOMATABLE — human verification required | 09-04-SUMMARY.md and 09-VALIDATION.md both record this as **blocked, not passed** — no human operator drove a real TOTP client, and `bin/instance` in this environment lacks `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`. Correctly not claimed as passed by the executor. |

**Score:** 8/9 truths verified programmatically; 1 requires human execution (never claimed passed by the phase itself).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py` | widened non-re-raising catch, success message inside inner `try:` | ✓ VERIFIED | Read in full; matches must_haves exactly, plus review-fix WR-01 (`KeyError, IndexError` added to same tuple) |
| `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py` | raising harness + 2 failure-path tests (+1 WR-01 regression test) | ✓ VERIFIED | 6 test methods present: `test_reset_email_survives_a_non_ascii_sender_name`, `test_successful_request_keeps_the_caller_on_the_form`, `test_reset_request_stores_a_reset_token`, `test_a_refused_recipient_reports_in_page_not_an_error_page`, `test_a_stray_curly_brace_in_the_mail_body_reports_in_page_not_a_500`, `test_an_unreachable_mail_server_reports_the_same_failure` |
| `src/imio/googleauthenticator/userdataschema.py` | one-sentence, link-free description | ✓ VERIFIED | Field description is exactly `'Enable/disable the two-step verification.'`; comment above records the deliberate deletion and Phase 13 consequence |
| `src/imio/googleauthenticator/tests/test_adapter.py` | schema-level absence assertion | ✓ VERIFIED | `test_enable_flag_description_offers_no_wrong_account_links` present at line 126 |
| `src/imio/googleauthenticator/browser/forms/recovery_codes.pt` | single link resolving navigation root | ✓ VERIFIED | Read in full (39 lines); one anchor, correct expression, explanatory comment on why `globals_view` is not used |
| `src/imio/googleauthenticator/helpers.py` | `get_token_description()` returns QR + base32 secret text | ✓ VERIFIED | Read in full; single secret lookup, escaped interpolation (WR-02 applied) |
| `src/imio/googleauthenticator/tests/test_user_setup.py` | one test per requirement | ✓ VERIFIED | `test_recovery_codes_page_links_to_the_home_page`, `test_setup_form_shows_the_secret_as_selectable_text` present |
| `CHANGES.rst` | Phase 9 entry covering all four fixes + D-16 consequence | ✓ VERIFIED | Lines 272, 281, 286, 291, 294-297 cover BUG-07, BUG-08, UX-01, UX-02, and the orphaned French translation |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `host.send(...)` failure | `if reason is not None:` tail | widened `except` tuple, `reason = _("An unexpected error occurred.")` | ✓ WIRED | Confirmed by source read and by live test run |
| success `IStatusMessage` call | inner `try:` | moved inside, immediately after `host.send(...)` | ✓ WIRED | Confirmed — lines 134-137 sit before the `except` at line 138, inside the `try:` opened at line 89 |
| `SetupForm.handleSubmit` success path | `recovery_codes.pt` link | `redirect_url` stays `None` -> `render()` -> template's retargeted anchor | ✓ WIRED | `user_setup.py` diff is empty (zero changes); template diff confirmed; live test confirms both codes and link render together |
| `SetupForm.updateFields` site-local branch | `get_token_description()` | one `get_or_create_secret()` call feeding both QR and text | ✓ WIRED | Single call confirmed by direct source read at `helpers.py:353` |
| `CustomizedUserDataPanel.__init__`'s `omit()` | `@@user-information` as sole renderer | `omit()` call unchanged, still covers only `@@personal-information` | ✓ WIRED | `userdataschema.py:38-42` diff-free relative to the omit() call itself (only the field description below it changed) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| BUG-07 | 09-01 | Rejected recipient mail send reports in-page, not as error page | ✓ SATISFIED | Source + live test run |
| BUG-08 | 09-02 | No wrong-account link on `@@user-information` | ✓ SATISFIED | Source + live test run |
| UX-01 | 09-03 | Enrollment ends with a home-page link, RECOV-03 intact | ✓ SATISFIED | Source + live test run |
| UX-02 | 09-03 | Secret shown as selectable text, one call, escaped, otpauth URI not shown | ✓ SATISFIED (automatable half); ⬜ human_needed (TOTP-client half) | Source + live test run; second half explicitly recorded blocked, never claimed passed |

Cross-referenced against `REQUIREMENTS.md` lines 189-192: BUG-07, BUG-08, UX-01, UX-02 all map to Phase 9 and only Phase 9 — no orphaned requirements found for this phase.

### Anti-Patterns Found

None blocking. `grep` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` across all seven changed source/test files found only two pre-existing `TODO` comments in `helpers.py` (lines 255, 317, both predating this phase, confirmed absent from `git diff 867280f..HEAD -- helpers.py`) and two pre-existing `FIXME` comments (lines 895, 923, also predating this phase and outside the diff). No new debt markers were introduced by this phase.

Two Warning-level findings from `09-REVIEW.md` (WR-01: `.format()` `KeyError`/`IndexError` gap; WR-02: unescaped secret/URL interpolation) were both fixed and regression-tested per `09-REVIEW-FIX.md`, confirmed present in the current source (`except (..., KeyError, IndexError):` and `escape(...)` calls both read directly from the file).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Refused-recipient mail send reports in-page | `bin/test -t test_a_refused_recipient_reports_in_page_not_an_error_page` | 1 test, 0 failures, 0 errors | ✓ PASS |
| Unreachable mail server / stray-brace body / wrong-account-links / home-page link / selectable secret / escaped secret (batch) | `bin/test -t test_recovery_codes_page_links_to_the_home_page -t test_setup_form_shows_the_secret_as_selectable_text -t test_enable_flag_description_offers_no_wrong_account_links -t test_a_stray_curly_brace_in_the_mail_body_reports_in_page_not_a_500 -t test_get_token_description_escapes_html_metacharacters_in_secret` | 5 tests, 0 failures, 0 errors | ✓ PASS |
| Lint gate | `bin/code-analysis` | `Flake8 OK`, exit 0 | ✓ PASS |
| Diff scope: `user_setup.py`, `pas_plugin.py`, `locales/`, `profiles/`, `browser/static/` untouched | `git diff 867280f..HEAD --name-only` filtered | Only the 8 declared files changed | ✓ PASS |

(Full-suite 142/0/0 and 91% coverage were independently confirmed by the orchestrator per the task brief; this verifier additionally ran the five named phase-9 tests live rather than trusting the SUMMARY narration, per the behavioral-evidence requirement.)

### Decisions-That-Forbid-Work — Honored

| Decision | Check | Result |
|----------|-------|--------|
| D-12 (no token rollback on send failure) | `request_bar_code_reset.py` diff | Confirmed: token write at line 86 has no compensating write in the widened `except` |
| D-16 (no `.po`/`.pot` edits this phase) | `git log -- src/imio/googleauthenticator/locales/` | No commits since before Phase 9 (last touch was Phase 1 rename work) |
| D-06 (no reveal control, no JS, no `jsregistry.xml` entry) | `git diff --name-only 867280f..HEAD` | No `browser/static/`, no `profiles/default/jsregistry.xml` in the changed-file list |
| D-03 (refusal redirect at `user_setup.py:91-93` untouched) | `git diff 867280f..HEAD -- user_setup.py` | Empty diff — zero lines |
| Deferred: mismatched-`userid` refusal, orphaned-msgid sweep, `site_properties.xml` | inspection of diff scope | None of the three appear in the changed-file list; correctly left for later/never |

## Human Verification Required

### 1. Real TOTP client acceptance (Phase 9 success criterion 4, second half)

**Test:** Enrol a test user at `@@setup-two-factor-authentication` on a running instance
(`bin/instance fg`, with `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` exported first — it is not set by
`base.cfg` outside the `[testenv]` section). Copy the base32 setup key shown beside the QR code as
text, not by scanning the image. Enter it into a desktop TOTP client or password manager as a
manually-entered setup key. Log out, log in, and submit the code that client shows.
**Expected:** The site accepts the code.
**Why human:** Cannot be automated in this suite — no test can drive a real third-party TOTP
client. The phase itself recorded this as **blocked**, not passed, in both `09-04-SUMMARY.md` and
`09-VALIDATION.md`, and explicitly declined to fake a passing test for it. This is the honest,
expected state of an autonomous run with no human operator present — not a defect.

### 2. Judgment-tier prohibitions sign-off

**Test:** Review the two `verification: unverified` / `status: flagged-unverified` prohibitions in
`09-01-PLAN.md` (no widening of exception handling onto the auth/challenge path) and
`09-03-PLAN.md` (no new persistence/logging of the seed; no double-minting).
**Expected:** Confirm the verifier's source-based evidence is sufficient: `pas_plugin.py` has a
zero-line diff across the whole phase and `_dont_swallow_my_exceptions = True` is still present;
`get_token_description()` adds no `logger` call and no new `setMemberProperties`/`setProperty`
write, and calls `get_or_create_secret` exactly once.
**Why human:** These are judgment-tier prohibitions per PLAN frontmatter, not auto-resolvable —
they route to human sign-off rather than a mechanical pass/fail gate, per the verification
protocol's fail-closed handling of unresolved prohibitions.

## Gaps Summary

No code-level gaps. All four ROADMAP success criteria have their automatable halves fully
implemented, tested (live-confirmed by this verifier, not just SUMMARY narration), and lint/scope
clean. The phase's own artifacts (`09-VALIDATION.md`, `09-04-SUMMARY.md`) are honest about the one
piece that is genuinely not automatable — the real-TOTP-client half of success criterion 4 — and
correctly recorded it as blocked rather than papering over it with a fake pass. That single item,
plus the two judgment-tier prohibitions the plans themselves flagged as unverified, are the reason
this report is `human_needed` rather than `passed`: nothing here is a defect in the implementation,
but nothing here should be silently marked complete on automated evidence alone either.

---

_Verified: 2026-08-06T13:37:51Z_
_Verifier: Claude (gsd-verifier)_
