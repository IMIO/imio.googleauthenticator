---
status: passed
phase: 09-mail-path-and-profile-page-correctness
source: [09-VERIFICATION.md]
started: 2026-08-06T13:40:00Z
updated: 2026-08-06T13:55:00Z
completed: 2026-08-06T13:55:00Z
---

## Current Test

none — all tests complete

## Tests

### 1. A real TOTP client fed the displayed base32 secret produces codes the site accepts

expected: The site accepts the code the real TOTP client produced from the copied base32 secret.

steps:
  1. Export `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`, then start the instance with `bin/instance fg`.
  2. Enrol a test user at `@@setup-two-factor-authentication`.
  3. Copy the base32 setup key shown beside the QR code **as text** — do not scan the image.
     This is the whole point of UX-02; scanning the QR would test the pre-existing path.
  4. Enter that key into a desktop TOTP client or a password manager as a manually-entered
     setup key.
  5. Log out, log back in, and submit the code that client shows.

why_human: Roadmap success criterion 4's second half requires driving a real third-party TOTP
client against a live instance. It is not automatable in this suite. Plan 09-04 recorded it as
blocked rather than passed — no human operator drove it, and `bin/instance` in this environment
has no `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` set. This is a known open gap, not a code defect.

result: PASSED (operator, 2026-08-06). The operator enrolled by copying the base32 setup key
text into a TOTP application rather than scanning the QR code, and the site accepted the codes
that application produced.

Two further checks were made on the same running instance and also passed:
  - The "Continue to the home page" link on the recovery-codes page landed on the site home
    page (UX-01, success criterion 3).
  - Viewing a member's profile as an administrator, the two-step-verification field description
    no longer shows the links that would have acted on the administrator's own account
    (BUG-08, success criterion 2).

### 2. Sign-off on two judgment-tier prohibitions

expected: Human sign-off that the verifier's source-reading evidence satisfies both prohibitions.

the two prohibitions:
  1. The widened `except` tuple in `request_bar_code_reset.py` is not extended onto
     `pas_plugin.py`'s authentication path.
  2. `get_token_description()` does not log, email, or newly persist the seed, and calls
     `get_or_create_secret` exactly once with no change to the overwrite default.

evidence the verifier recorded:
  - `git diff 867280f..HEAD -- src/imio/googleauthenticator/pas_plugin.py` is empty — that file
    has a zero-line diff for the whole phase, and `_dont_swallow_my_exceptions = True` is still
    present at line 160.
  - `get_token_description()` (`helpers.py:331-370`) calls
    `get_or_create_secret(user, overwrite=overwrite_secret)` exactly once, adds no logger call
    and no new `setMemberProperties` / `setProperty` write, and the QR and the text both derive
    from that single call.

why_human: Both are declared `verification: unverified` / `status: flagged-unverified` in the
PLAN frontmatter. They are judgment-tier items that this workflow routes to human sign-off
rather than an automated gate.

result: PASSED (operator, 2026-08-06). Signed off on the evidence above, which was re-confirmed
live at sign-off time: `git diff --stat 867280f..HEAD -- src/imio/googleauthenticator/pas_plugin.py`
returned empty, `_dont_swallow_my_exceptions = True` is still at `pas_plugin.py:160`, and
`get_token_description()` contains exactly one `get_or_create_secret` call with no `logger`
call and no `setMemberProperties` / `setProperty` write.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
