---
phase: 09-mail-path-and-profile-page-correctness
plan: 01
subsystem: auth
tags: [plone, pas-plugin, smtplib, mailhost, tdd]

# Dependency graph
requires: []
provides:
  - "request_bar_code_reset.py's mail-send failure now reports through the form's shared IStatusMessage error path instead of escaping as an unhandled exception"
  - "the failure shape (widened except tuple, no re-raise, generic reused message, success message scoped inside the send try:) that Phase 12's three additional senders will copy"
affects: [12-notification-emails]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mail-send failures caught with `except (SMTPException, socket.error):` at the send-call boundary, routed into the method's existing `if reason is not None:` tail rather than a new reporting path"
    - "A success status-message call moved inside the same try: as the operation it confirms, so a raised exception skips it naturally"

key-files:
  created: []
  modified:
    - src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py
    - src/imio/googleauthenticator/tests/test_request_bar_code_reset.py

key-decisions:
  - "D-09: widen the catch to (SMTPException, socket.error) — SMTPRecipientsRefused is an SMTPException, but a refused connection raises socket.error, which is not"
  - "D-10: delete the inner except/raise re-raise outright; the failure now reaches the method's existing shared reason-reporting tail"
  - "D-11: reuse the existing message _(\"An unexpected error occurred.\") — no new msgid, and no distinct message that would widen the accepted username-enumeration oracle (T-03-26)"
  - "D-12: bar_code_reset_token is not rolled back on a send failure — a stored token grants nothing without the ska signature in the undelivered email"
  - "Pitfall 1 (RESEARCH.md): moved the success IStatusMessage call inside the inner try:, immediately after host.send(...), so a send failure skips it and cannot report both an error and a success on one request"

patterns-established:
  - "Non-vacuity check performed for both new tests: proved red against unmodified/narrowed source, then either applied the real fix or restored byte-identical, before committing"

requirements-completed: [BUG-07]

coverage:
  - id: D1
    description: "A refused-recipient mail send reports the shared in-page error message, with no success message also firing, and the reset token is not rolled back"
    requirement: "BUG-07"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_request_bar_code_reset.py#test_a_refused_recipient_reports_in_page_not_an_error_page"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unreachable mail server (socket.error, not an SMTPException) takes the identical failure path"
    requirement: "BUG-07"
    verification:
      - kind: unit
        ref: "src/imio/googleauthenticator/tests/test_request_bar_code_reset.py#test_an_unreachable_mail_server_reports_the_same_failure"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-06
status: complete
---

# Phase 9 Plan 1: Mail-Send Failure Reporting Summary

**Widened `request_bar_code_reset.py`'s mail-send `except` from a re-raised `SMTPRecipientsRefused` to a non-re-raising `(SMTPException, socket.error)` tuple that routes into the form's existing shared error-reporting tail, with the success message relocated inside the same `try:` so it cannot fire alongside a failure.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments
- Closed BUG-07: a mail server that refuses the recipient, or that is unreachable, now produces the same in-page `Request for bar-code reset is failed! An unexpected error occurred.` message every other failure path in `handleSubmit` already produces, instead of an unhandled exception and a bare Zope error page.
- Both arms of the widened catch tuple are exercised by a dedicated test each, so removing either arm turns a test red.
- The success `IStatusMessage` call was moved inside the inner `try:` (immediately after `host.send(...)`), closing the RESEARCH.md Pitfall 1 hazard where a naive widen-only fix would report both an error and a success on one failed request.
- `bar_code_reset_token`, written before the send, is confirmed (by a passing assertion in the new test) to survive a send failure unrolled-back, per D-12.

## Task Commits

Each task was committed atomically, following the RED → GREEN TDD gate sequence for Task 1's tracer, plus one additional RED-verified test for Task 2:

1. **Task 1 STEP 1 (RED):** `test(09-01): add failing test for BUG-07 refused-recipient handling` — added `_submit_reset_request_with_failing_send` harness and `test_a_refused_recipient_reports_in_page_not_an_error_page`; run against unmodified production source and confirmed it errors with the escaping `SMTPRecipientsRefused`.
2. **Task 1 STEP 2 (GREEN):** `fix(09-01): report a refused-recipient mail failure in-page, not as an error page` — widened the catch, deleted the re-raise, moved the success message inside the inner `try:`, reused the existing generic message.
3. **Task 2:** `test(09-01): exercise the socket.error arm of the BUG-07 catch tuple` — added `test_an_unreachable_mail_server_reports_the_same_failure`; non-vacuity check performed by temporarily narrowing the production catch tuple to `SMTPException` only, confirming this test goes red, then restoring the production file byte-identical before committing.

**Plan metadata:** (this commit, filed alongside STATE.md/ROADMAP.md updates)

## Files Created/Modified
- `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py` — widened `except SMTPRecipientsRefused: raise ...` to `except (SMTPException, socket.error):` with `logger.exception` + reused `reason` message; moved the success `IStatusMessage` call inside the inner `try:`
- `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py` — added `_submit_reset_request_with_failing_send` harness and two new test methods (`test_a_refused_recipient_reports_in_page_not_an_error_page`, `test_an_unreachable_mail_server_reports_the_same_failure`)

## Decisions Made
- Followed CONTEXT.md's D-09 through D-13 exactly as specified: widen the catch tuple, delete the re-raise, reuse the existing generic message, do not roll back the token, reuse the existing `MailBase._send` monkeypatch harness.
- Applied the RESEARCH.md Pitfall 1 fix (move the success message inside the inner `try:`) exactly as the plan's `<action>` prescribed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test-code bug] Corrected an invalid `SMTPRecipientsRefused` constructor call from the plan's illustrative example**
- **Found during:** Task 1, writing the RED test
- **Issue:** The plan's illustrative text said to drive the harness with `SMTPRecipientsRefused({}, 'sender@example.com')` — two positional arguments. `smtplib.SMTPRecipientsRefused.__init__` (verified live against the project's Python 2.7 interpreter) takes exactly one positional argument, a dict of refused recipients. Calling it with two arguments raises `TypeError` immediately, which is not the failure mode BUG-07 is about and would have made the test assert nothing meaningful about the mail path.
- **Fix:** Used `SMTPRecipientsRefused({'cadam@imio.be': (550, 'Recipient address rejected')})` — a single dict argument matching the real constructor and the shape `Products.MailHost` actually raises it with.
- **Files modified:** `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py`
- **Verification:** Confirmed live: `python2.7 -c "import smtplib; smtplib.SMTPRecipientsRefused({}, 'x')"` raises `TypeError: __init__() takes exactly 2 arguments (3 given)`; the corrected single-dict-argument call constructs successfully and the test runs (and, against unfixed source, errors with the expected escaping exception).
- **Committed in:** the STEP 1 test commit (Task 1)

---

**Total deviations:** 1 auto-fixed (1 test-code correctness fix, Rule 1)
**Impact on plan:** No scope creep — the fix corrects a constructor-arity mistake in the plan's own illustrative example so the test actually exercises the intended failure mode. No production code or decision was affected.

## Issues Encountered
None beyond the deviation above.

## Non-Vacuity Checks (verbatim, per D-13 / project convention)

**Task 1 — RED against unmodified production source** (`bin/test -t test_a_refused_recipient_reports_in_page_not_an_error_page`):
```
Error in test test_a_refused_recipient_reports_in_page_not_an_error_page (imio.googleauthenticator.tests.test_request_bar_code_reset.TestRequestBarCodeReset)
Traceback (most recent call last):
  File "/srv/cache/eggs/unittest2-0.5.1-py2.7-linux-x86_64.egg/unittest2/case.py", line 340, in run
    testMethod()
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/tests/test_request_bar_code_reset.py", line 185, in test_a_refused_recipient_reports_in_page_not_an_error_page
    {'cadam@imio.be': (550, 'Recipient address rejected')}))
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/tests/test_request_bar_code_reset.py", line 77, in _submit_reset_request_with_failing_send
    form.update()
  ...
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py", line 113, in handleSubmit
    raise SMTPRecipientsRefused('Recipient address rejected by server')
SMTPRecipientsRefused: Recipient address rejected by server

  Ran 1 tests with 0 failures and 1 errors in 0.017 seconds.
```
Then the fix was applied (STEP 2) and the same test re-run green (`Ran 1 tests with 0 failures and 0 errors`).

**Task 2 — RED against a temporarily narrowed production catch tuple** (`except (SMTPException,):`, `bin/test -t test_an_unreachable_mail_server_reports_the_same_failure`):
```
Error in test test_an_unreachable_mail_server_reports_the_same_failure (imio.googleauthenticator.tests.test_request_bar_code_reset.TestRequestBarCodeReset)
Traceback (most recent call last):
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/tests/test_request_bar_code_reset.py", line 222, in test_an_unreachable_mail_server_reports_the_same_failure
    TEST_USER_NAME, socket.error(111, 'Connection refused'))
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/tests/test_request_bar_code_reset.py", line 78, in _submit_reset_request_with_failing_send
    form.update()
  ...
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py", line 111, in handleSubmit
    msg_type='text/html'
  File "/srv/cache/eggs/Products.MailHost-2.13.2-py2.7-linux-x86_64.egg/Products/MailHost/MailHost.py", line 237, in send
    self._send(mfrom, mto, messageText, immediate)
  File "/srv/src/imio.googleauthenticator/src/imio/googleauthenticator/tests/test_request_bar_code_reset.py", line 69, in _raise
    raise exception
error: [Errno 111] Connection refused

  Ran 1 tests with 0 failures and 1 errors in 0.012 seconds.
```
`git status --porcelain src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py` was empty afterward, confirming the byte-identical restore before this test was committed.

## Verification Evidence

- `bin/test -t test_request_bar_code_reset`: 5 tests, 0 failures, 0 errors (up from 3 before this plan).
- `bin/test -t '!robot'` (full suite): 137 tests, 0 failures, 0 errors (up from the 135 baseline recorded in PROJECT.md).
- `bin/code-analysis`: exit 0, run after each commit.
- `python2.7 -c "import ast,sys; src=open('.../request_bar_code_reset.py').read(); sys.exit(0 if 'SMTPRecipientsRefused' not in src else 1)"`: exit 0 — the narrow exception name no longer appears in the production module.
- `git diff` confirmed: the `charset='utf-8'` argument and its comment block, the `bar_code_reset_token` write, and the `except ValueError:` arm are all unchanged.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 12 can copy this failure shape (widened tuple catch, no re-raise, reused generic message, success-message-inside-try:) verbatim when it attaches three more senders to this mail path.
- No blockers introduced. BUG-08, UX-01, UX-02 (Plans 02-04 of this phase) are independent and touch disjoint files.

---
*Phase: 09-mail-path-and-profile-page-correctness*
*Completed: 2026-08-06*
