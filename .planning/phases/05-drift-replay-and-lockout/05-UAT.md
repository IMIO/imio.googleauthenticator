---
status: testing
phase: 05-drift-replay-and-lockout
source: [05-VERIFICATION.md]
started: 2026-08-01T16:45:00Z
updated: 2026-08-01T16:45:00Z
---

## Current Test

number: 1
name: Lockout counter is cumulative across ZEO clients
expected: |
  The lock triggers on the cumulative count across clients, because the counter lives in a
  memberdata property (ZODB-backed, not RAM), not on a per-instance count that a
  client-rotating attacker could multiply.
awaiting: user response

## Tests

### 1. Lockout counter is cumulative across ZEO clients

Restart a real ZEO cluster with two or more clients sharing the same ZODB, enable 2FA for a
test account, submit failed second-factor attempts split across clients (for example 3 against
client A and 2 against client B), and confirm the account still locks at the 5th cumulative
failure rather than each client independently allowing 4.

expected: The lock triggers on the cumulative count across clients, because the counter lives in a memberdata property (ZODB-backed, not RAM).
why_human: 05-01-PLAN.md carries this as an explicit `verification: backstop` truth. The integration-test layer runs one process against one ZODB connection and cannot exercise real inter-client consistency.
result: [pending]

### 2. Control-panel lockout fields persist in a live instance

In a running Plone instance (not the test layer), open the Google Authenticator control panel
as a Manager, confirm "Maximum failed second-factor attempts" and "Lockout duration (seconds)"
render with defaults 5 and 900, change both, save, reload the page, and confirm the new values
persisted.

expected: Both fields render, accept edits, and the edited values are still shown after a page reload.
why_human: 05-01-PLAN.md carries this as an explicit `verification: backstop` truth. `test_control_panel_has_lockout_fields` checks the schema/registry wiring in-process; it does not drive the real z3c.form edit-and-persist round trip through a browser.
result: [pending]

### 3. Clock-drift tolerance agrees with a real mobile TOTP app

With a real Google Authenticator (or compatible TOTP) mobile app enrolled against a test
account, wait until the displayed code is roughly 1-29 seconds from rolling over to the next
30-second interval, submit that about-to-expire code and confirm it is still accepted (one step
of RFC 6238 drift), then submit the code the app displays immediately after the rollover and
confirm that one is accepted too.

expected: Both the code from the interval just before submission and the code from the current interval are accepted, proving the server's `_find_accepted_interval` arithmetic agrees with an independently-clocked real device.
why_human: 05-02-PLAN.md carries this as an explicit `verification: backstop` truth. `test_validate_token_accepts_previous_interval` generates its own code with the same library and clock the code under test uses, so it cannot rule out a systematic arithmetic error that would still self-agree.
result: [pending]

### 4. Token endpoint reveals no lock state end-to-end behind the real proxy

Deploy the current build behind whatever front-end proxy or load balancer the target
environment actually uses. As an anonymous, unauthenticated caller with no `signature` or
`auth_timestamp` query parameters, request `@@google-authenticator-token?auth_user=<locked-account>`
and, separately, `@@google-authenticator-token?auth_user=<unlocked-or-nonexistent-account>`.
Compare the two rendered pages byte-for-byte (status line, headers, body).

expected: The two responses are indistinguishable end-to-end — same HTTP status, no proxy-injected error page, no differential caching that would let an external observer learn lock state.
why_human: 05-04-PLAN.md carries this as an explicit `verification: backstop` truth naming exactly this residual risk: `zope.testbrowser` exercises the view in-process and cannot rule out a difference introduced downstream by the real ZPublisher error/status path or a front-end proxy.
result: [pending]

### 5. Reset-bar-code endpoint reveals no lock state end-to-end behind the real proxy

Same deployment and proxy setup as test 4, but against
`@@reset-bar-code?auth_user=<locked-account>` versus
`@@reset-bar-code?auth_user=<unlocked-but-enrolled-account>`, both anonymous and unsigned,
comparing the two rendered pages byte-for-byte.

expected: The two responses are indistinguishable end-to-end, for the same reason as test 4.
why_human: 05-05-PLAN.md carries this as an explicit `verification: backstop` truth with the identical residual-risk statement, scoped to `@@reset-bar-code`.
result: [pending]

### 6. Forward-looking: second-factor state writes stay on committing paths

Code-review only, not a runtime test. As the codebase evolves after this phase, confirm no new
call site writing second-factor state (a property named `two_factor_authentication_*`, or a
call to `register_failed_second_factor` / `reset_failed_second_factor`) is added to
`pas_plugin.py`, `subscribers.py`, or any other non-committing code path.

expected: All second-factor state writes continue to originate only from `browser/forms/token.py` and `browser/forms/reset_bar_code.py`, both committing views.
why_human: 05-03-PLAN.md records this explicitly as a `verification: backstop` truth. The current grep-based guard covers `pas_plugin.py` and `subscribers.py` as they exist today but cannot prove the invariant against files that do not yet exist. Not actionable today; recorded so a future reviewer checks it rather than assuming it is enforced automatically.
result: [pending]

## Field Findings (not Phase 5 gaps)

Two problems reported from real-deployment testing on `server.dmsmail`, fresh site, new user
"cadam", 2026-08-03. Neither is a Phase 5 requirement failure — Phase 5 covers clock drift,
replay rejection, lockout, lock-state indistinguishability and counter persistence (MFA-05
through MFA-13), and `05-VERIFICATION.md` scored 19/19 on those. Recorded here so the
observations are not lost, and deliberately kept out of `## Gaps` so they do not block this
phase or spawn Phase 5 gap-closure plans.

### F-1. Modal forms render as full pages — routed to Phase 7, already planned

Observed: the user-actions view does not open under the logged-in user's name, and `@@new-user`
opens a full page. Both should open in Plone's overlay.

Established from source, not from the running site:
- `profiles/default/jsregistry.xml` carries `<javascript id="popupforms.js" remove="True"
  enabled="False" />`, which unregisters Plone's core overlay-wiring script site-wide, and
  registers this package's vendored copy in its place.
- `browser/static/plone_ecmascript/popupforms.js` is a stale fork of Plone's file. Against
  Plone 4.3.20 it differs in exactly three ways: it uses the old `jQuery.browser` API instead
  of Plone's `msieversion()` helper, it drops `dl.portalMessage.warning` from
  `common_content_filter`, and it comments out the login-form overlay (lines 60-85). Only the
  last is intentional.
- The package also replaces Plone's `login_form.cpt` through a skin layer.

Not established: the runtime cause on the deployment. A first hypothesis — a `jQuery.browser`
TypeError aborting the document-ready handler before any `prepOverlay` call — was tested and
rejected: both this buildout and `server.dmsmail` resolve `plone.app.jquery 1.7.2.1`, where
`jQuery.browser` still exists. Settling it needs the first JavaScript console error on an
affected page and the enabled/order state of the `popupforms.js` entries at
`/portal_javascripts/manage_jsForm`, neither of which is readable from the repository.

Routing: no new item filed, because ROADMAP Phase 7 already covers this. Success Criterion 2
names the `remove="True"` line as "a global mutation with no uninstall counterpart, and it is
why the collision flips on install order"; Success Criterion 3 requires a real
`profiles/uninstall/`; and the Phase 7 notes already record both stale-copy differences found
above. This finding upgrades those from a predicted risk to one observed breaking a live site.

### F-2. Bar-code reset request landed on the login page — FIXED, commit a14b012

Observed: logging in prompted for a one-time code; with no code available the user followed the
bar-code reset link, submitted their username, and arrived at the login page rather than at a
reset view.

Root cause: `browser/forms/request_bar_code_reset.py` redirected to the portal root after
sending the reset email. The caller arrives from the token form, by which point the PAS plugin
has cleared their `__ac` cookie, so they are anonymous; on a site whose root is not anonymously
viewable that redirect lands them on the login form, and the "email sent" confirmation is never
read. Present since the initial upstream import (`4faeac2`); no test covered the redirect
target. Phase 5 never touched the file.

Fix: the handler now returns without redirecting, re-rendering its own form — which is
registered `permission="zope2.View"` and so stays readable while anonymous — with the
confirmation on it, matching what its failure branch already did. Regression test
`test_successful_request_keeps_the_caller_on_the_form` asserts the response carries no
`Location` header and that the confirmation message is queued. Suite: 85 tests, 0 failures.

Separate, not a defect: reaching the reset view directly is not the design.
`@@request-bar-code-reset` emails a signed link to `@@reset-bar-code`, and the signature in that
link is what authorises the reset.

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
