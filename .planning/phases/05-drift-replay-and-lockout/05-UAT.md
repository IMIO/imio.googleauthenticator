---
status: testing
phase: 05-drift-replay-and-lockout
source: [05-VERIFICATION.md]
started: 2026-08-01T16:45:00Z
updated: 2026-08-01T16:45:00Z
---

## Current Test

number: 4
name: Token endpoint reveals no lock state end-to-end behind the real proxy
expected: |
  An anonymous, unsigned request naming a locked account and one naming an unlocked or
  nonexistent account produce indistinguishable responses end to end: same HTTP status, no
  proxy-injected error page, no differential caching that would leak lock state.
awaiting: |
  A re-run. The first attempt at tests 4 and 5 returned 404 on all four requests, so neither
  endpoint was exercised. The working URL must be established first -- see attempt_1.rerun_requires
  under test 4 below.

## Tests

### 1. Lockout counter is cumulative across ZEO clients

Restart a real ZEO cluster with two or more clients sharing the same ZODB, enable 2FA for a
test account, submit failed second-factor attempts split across clients (for example 3 against
client A and 2 against client B), and confirm the account still locks at the 5th cumulative
failure rather than each client independently allowing 4.

expected: The lock triggers on the cumulative count across clients, because the counter lives in a memberdata property (ZODB-backed, not RAM).
why_human: 05-01-PLAN.md carries this as an explicit `verification: backstop` truth. The integration-test layer runs one process against one ZODB connection and cannot exercise real inter-client consistency.
result: pass
tested_on: server.dmsmail, multiple instances behind one ZEO server, 2026-08-03
reported: "Ok, I managed to enter wrong OTP on different instances behind the zeoserver. The count is shared between instances. On the 5th wrong OTP, the count resets to 0 and the account is locked for lockout_duration"
note: |
  Matches `helpers.register_failed_second_factor` exactly, including the detail that the
  counter is reset to 0 in the same write that sets the lock -- so a locked account reads 0
  failed attempts, and `two_factor_authentication_locked_until` is the only field that shows
  the lock. This is the backstop truth the single-process integration layer could not reach.

### 2. Control-panel lockout fields persist in a live instance

In a running Plone instance (not the test layer), open the Google Authenticator control panel
as a Manager, confirm "Maximum failed second-factor attempts" and "Lockout duration (seconds)"
render with defaults 5 and 900, change both, save, reload the page, and confirm the new values
persisted.

expected: Both fields render, accept edits, and the edited values are still shown after a page reload.
why_human: 05-01-PLAN.md carries this as an explicit `verification: backstop` truth. `test_control_panel_has_lockout_fields` checks the schema/registry wiring in-process; it does not drive the real z3c.form edit-and-persist round trip through a browser.
result: pass
tested_on: server.dmsmail live instance, 2026-08-03
reported: "Yes, test 2 passed !"
note: |
  Confirms the AutoExtensibleForm plus registry.xml wiring works end to end through a real
  browser, not only via `getUtility(IRegistry)` in the test layer. Tested after commit 452b66c
  restored site JavaScript, so the control panel was exercised with its scripts working.

### 3. Clock-drift tolerance agrees with a real mobile TOTP app

With a real Google Authenticator (or compatible TOTP) mobile app enrolled against a test
account, wait until the displayed code is roughly 1-29 seconds from rolling over to the next
30-second interval, submit that about-to-expire code and confirm it is still accepted (one step
of RFC 6238 drift), then submit the code the app displays immediately after the rollover and
confirm that one is accepted too.

expected: Both the code from the interval just before submission and the code from the current interval are accepted, proving the server's `_find_accepted_interval` arithmetic agrees with an independently-clocked real device.
why_human: 05-02-PLAN.md carries this as an explicit `verification: backstop` truth. `test_validate_token_accepted_previous_interval` generates its own code with the same library and clock the code under test uses, so it cannot rule out a systematic arithmetic error that would still self-agree.
result: pass
tested_on: server.dmsmail with a real mobile TOTP app enrolled, 2026-08-03
reported: "Ok, that works with both the displayed code and the previously displayed code that expired a few seconds ago."
note: |
  Drift tolerance confirmed against an independently-clocked device, which is what this test
  existed for.

  The operator additionally observed, and asked whether it was intended, that logging in, logging
  out, and logging in again inside the same 30-second window with the same code is refused. It is
  intended: requirement MFA-06 and ROADMAP Phase 5 Success Criterion 1 require a consumed code to
  be rejected on reuse, citing RFC 6238 section 5.2's MUST NOT. In `helpers.validate_token`, a
  successful validation writes the matched interval to the memberdata property
  `two_factor_authentication_last_interval`, and the next submission is refused by
  `if matched <= last_accepted_interval:`, which logs `TOTP replay rejected` with no operands.

  Two consequences of that rule, both correct and worth stating so nobody later reads them as
  defects. It is scoped to the time interval, not the login session, so any second use of the same
  code fails regardless of what happened in between. And because the comparison is `<=`, the
  previous interval's code is also refused once a newer one has been accepted, even though drift
  tolerance would otherwise have accepted it. A legitimate user who logs out and back in must
  therefore wait for the next code, up to 30 seconds.

### 4. Token endpoint reveals no lock state end-to-end behind the real proxy

Deploy the current build behind whatever front-end proxy or load balancer the target
environment actually uses. As an anonymous, unauthenticated caller with no `signature` or
`auth_timestamp` query parameters, request `@@google-authenticator-token?auth_user=<locked-account>`
and, separately, `@@google-authenticator-token?auth_user=<unlocked-or-nonexistent-account>`.
Compare the two rendered pages byte-for-byte (status line, headers, body).

expected: The two responses are indistinguishable end-to-end — same HTTP status, no proxy-injected error page, no differential caching that would let an external observer learn lock state.
why_human: 05-04-PLAN.md carries this as an explicit `verification: backstop` truth naming exactly this residual risk: `zope.testbrowser` exercises the view in-process and cannot rule out a difference introduced downstream by the real ZPublisher error/status path or a front-end proxy.
result: [pending]
attempt_1:
  date: 2026-08-03
  outcome: inconclusive, evidence rejected
  method: |
    Two anonymous `curl -sSi` requests against `localhost:8084/gauth-5`, no cookies, no
    `signature`, no `auth_timestamp`, one naming a locked account and one an unlocked enrolled
    account, compared with `diff` over the full response.
  reported: |
    diff reported one differing line, the `Date` header:
      < Date: Mon, 03 Aug 2026 12:24:55 GMT
      > Date: Mon, 03 Aug 2026 12:25:57 GMT
  why_rejected: |
    Both captures begin `HTTP/1.1 404 Not Found`. The comparison was therefore between two Plone
    404 pages, and the token endpoint was never reached, so it establishes nothing about
    lock-state indistinguishability. Recorded rather than deleted because the run was initially
    accepted as a pass on the strength of the `diff` output alone, without checking the status
    line -- the same shape of mistake that let the 05-03 substring acceptance criterion through.

    The site was reached: the body carries `<title>imio-googleauth-phase-5</title>` and
    `localhost:8084/gauth-5/portal_css/...`, so Plone rendered its own 404 after failing to
    resolve the view name. This package raises `NotFound` nowhere in its non-test source and both
    views are registered `for="*"`, so the cause lies in the request path or in the instance on
    port 8084 not loading the package. The browser session that reproduced earlier findings was on
    port 8081, and `dev.cfg` adds `imio.googleauthenticator` to two separate eggs lists.
  rerun_requires: |
    Responses that are not 404. Establish the working URL from the address bar when the one-time
    code prompt appears during a real login, then reissue it with `signature`, `valid_until` and
    `extra` stripped, keeping only `auth_user`.

### 5. Reset-bar-code endpoint reveals no lock state end-to-end behind the real proxy

Same deployment and proxy setup as test 4, but against
`@@reset-bar-code?auth_user=<locked-account>` versus
`@@reset-bar-code?auth_user=<unlocked-but-enrolled-account>`, both anonymous and unsigned,
comparing the two rendered pages byte-for-byte.

expected: The two responses are indistinguishable end-to-end, for the same reason as test 4.
why_human: 05-05-PLAN.md carries this as an explicit `verification: backstop` truth with the identical residual-risk statement, scoped to `@@reset-bar-code`.
result: [pending]
attempt_1:
  date: 2026-08-03
  outcome: inconclusive, evidence rejected
  reported: |
    diff over /tmp/reset-locked.txt and /tmp/reset-unlocked.txt reported one differing line, the
    `Date` header.
  why_rejected: |
    Both captures begin `HTTP/1.1 404 Not Found`, exactly as in test 4's rejected attempt. The
    `@@reset-bar-code` endpoint was never reached. This is the endpoint plan 05-05 changed, so it
    is the one whose end-to-end behaviour is least established by anything else.

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

### F-1. No JavaScript runs at all on the deployment — cause found, FIXED in 452b66c

Resolved after this section was first written, and since confirmed working on the affected
`server.dmsmail` site by the operator on 2026-08-03 after re-importing the profile's `jsregistry`
import step: overlay forms render as overlays again.

The operator read the live registry order off the
affected site on 2026-08-03: `++resource++imio.googleauthenticator/main.js` 1st,
`++resource++imio.googleauthenticator/plone_ecmascript/popupforms.js` 2nd,
`++resource++plone.app.jquery.js` 3rd.

Root cause: `profiles/default/jsregistry.xml` declared no position directive, and
`Products.ResourceRegistries` 2.2.13 `BaseRegistry.storeResource` simply appends, so the final
order depended on when the profile's import step ran. Installing onto an existing site appends
after Plone's registrations and works, which is exactly why the integration test layer showed
these two at positions 42 and 43 and never reproduced the fault. On a fresh site, where
GenericSetup can import this step before Plone registers jQuery, they landed at 0 and 1. Cooking
merges adjacent compatible resources into one bundle, so the `$ is not defined` thrown by
`main.js`'s top-level `$(document).ready(...)` aborted that bundle before jQuery defined itself,
and every jQuery-dependent script on the site failed.

Fix: `insert-bottom="True"` on both entries, which also repairs an already-broken site on
profile re-import because the importer applies the move to existing resources too. Regression
test `test_every_javascript_registration_pins_its_position` in `tests/test_setuphandlers.py`
parses the XML and fails if any registering entry omits a position directive; confirmed to fail
when the directives are stripped. Suite: 90 tests, 0 failures.

The original analysis, kept because two of its hypotheses were wrong and the record of why
matters:



Observed: the user-actions view does not open under the logged-in user's name, and `@@new-user`
opens a full page. Both should open in Plone's overlay.

The browser console (supplied 2026-08-03) shows this is not an overlay problem. Roughly twenty
errors fire on one page load, all of the form `$ is not defined` or `jQuery is not defined`,
across packages with nothing to do with this one: Plone's own `table_sorter.js`,
`collective.js.fancytree`, `ckeditor_vars`, `plonetheme.imioapps`, `collective.contact.plonegroup`,
`imio.actionspanel`, `plone.formwidget.autocomplete`, and inline scripts in `useractions` itself.

**jQuery is absent from the page.** Overlays cannot work as a consequence — `prepOverlay` is a
jQuery Tools plugin and cannot exist without jQuery — so the full-page forms are a symptom, not
the defect. This package's `browser/static/main.js` is merely the first victim in console order:
it calls `$(document).ready(...)` at top level, so it is among the first scripts to touch `$`.

Two hypotheses were formed and both were rejected on evidence:
- A `jQuery.browser` TypeError in the vendored `popupforms.js` aborting the ready handler before
  any `prepOverlay` call. Rejected: both this buildout and `server.dmsmail` resolve
  `plone.app.jquery 1.7.2.1`, where `jQuery.browser` still exists.
- This package's resources being registered above jQuery. Rejected:
  `Products.ResourceRegistries` 2.2.13 `BaseRegistry.storeResource` appends
  (`resources.append(resource)`), and this package's `jsregistry.xml` gives no `insert-before` /
  `insert-after` / `insert-top` directive, so its entries land at the bottom of the registry.

What is still unknown is why jQuery itself is not on the page, which cannot be determined from
the repository. It needs the live state of `/portal_javascripts/manage_jsForm` on the affected
site: whether the jQuery resource is present and enabled, and its position.

Separately, and independent of the above, two real defects in this package were confirmed by
reading source. `profiles/default/jsregistry.xml` carries `<javascript id="popupforms.js"
remove="True" enabled="False" />`, which unregisters Plone's core overlay script site-wide with no
uninstall counterpart, and substitutes `browser/static/plone_ecmascript/popupforms.js`, a stale
fork that against Plone 4.3.20 uses the old `jQuery.browser` API instead of the `msieversion()`
helper, drops `dl.portalMessage.warning` from `common_content_filter`, and comments out the
login-form overlay (lines 60-85, the only intentional change). The package also replaces Plone's
`login_form.cpt` through a skin layer. Both override resources this package does not own.

Routing: no new item filed. ROADMAP Phase 7 already covers all of it — Success Criterion 2 names
the `remove="True"` line as "a global mutation with no uninstall counterpart, and it is why the
collision flips on install order", Success Criterion 3 requires a real `profiles/uninstall/`, and
the Phase 7 notes already record both stale-copy differences. Whether the missing jQuery is also
Phase 7's is undecided until the registry state is known.

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
passed: 3
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

- gap_id: G-05-A
  truth: "Every memberdata property plan 05-01 added can be read and written without breaking any
    user-profile form. ROADMAP Phase 5 Success Criterion 5 required a memberdata_properties.xml
    entry and a setMemberProperties/getProperty round-trip test for each new property; both were
    delivered, but nothing exercised the schema-to-form path those properties also entered."
  status: resolved
  reason: "Reported from real-deployment testing on server.dmsmail 2026-08-03: opening another
    user's profile as an administrator raised AttributeError: 'EnhancedUserDataPanelAdapter' object
    has no attribute 'two_factor_authentication_failed_attempts'. Plan 05-01 declared the three
    counters as Int fields on IEnhancedUserDataSchema; adapter.py supplies accessors for only the
    original three fields, and zope.formlib's setUpEditWidgets does a plain getattr per rendered
    field. CustomizedUserDataPanel.omit() did not cover it, being registered for the view name
    personal-information alone, while plone.app.users' @@user-information is not overridden by this
    package and renders whatever the schema declares."
  severity: major
  test: null
  found_by: field-testing
  artifacts:
    - path: "src/imio/googleauthenticator/userdataschema.py"
      issue: "Three Int schema fields that were never meant to be form fields"
    - path: "src/imio/googleauthenticator/adapter.py"
      issue: "No accessors for those three fields; zero test coverage before this gap"
  missing:
    - "Remove the three counters from IEnhancedUserDataSchema; memberdata_properties.xml is what
      makes them persist, and a schema field neither provides nor replaces that"
    - "Cover the schema-to-adapter invariant so a field added later without an accessor fails in
      the suite rather than in production"
  resolved_by: 6634113
  resolved_at: 2026-08-03
  also_closes: "Code-review finding WR-02 in 05-REVIEW.md, which flagged that a per-view omit()
    was the only barrier against a user editing their own two_factor_authentication_locked_until.
    Fields that no longer exist need no barrier."
  verification_note: "05-VERIFICATION.md scored 19/19 with gaps: [] and did not catch this. The
    blind spot was EnhancedUserDataPanelAdapter having no tests at all. tests/test_adapter.py is
    new and closes it. Suite: 88 tests, 0 failures."
