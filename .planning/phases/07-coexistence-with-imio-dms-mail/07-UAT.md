---
status: resolved
phase: 07-coexistence-with-imio-dms-mail
source: [07-04-PLAN.md, 07-VALIDATION.md]
started: 2026-08-05
updated: 2026-08-05
tested_by: operator (Chris)
---

## Current Test

number: —
name: —
awaiting: nothing; both tests reported by the operator

## Tests

### 1. Real two-egg install in both orders alongside imio.dms.mail (COEX-07)

**Why this could not be automated:** the test in `test_setuphandlers.py`
(`test_popupforms_js_survives_either_install_order`) replays `imio.dms.mail`'s real
reposition entry against `portal_javascripts` directly and proves the registry
mechanics in both orders. It cannot prove a real two-egg GenericSetup import
interleaving, because `imio.dms.mail` is not a dependency of this package's buildout
and pulling its dependency tree into `test-4.3.cfg` is a disproportionate change.

environment: fresh Plone site created for each install order, so no artifacts from
before this phase were present. Verified against the `server.dmsmail` MOD-1076
buildout, which lists `imio.googleauthenticator` in `dev.cfg`.

expected: in both orders, Plone's overlay-script resource is registered exactly once
and enabled; an `imio.dms.mail` `prepOverlay` widget still opens as an overlay; 2FA
login completes end to end.

result: **passed**

| Order | Overlay script registrations | imio.dms.mail overlay widget | 2FA login |
|-------|------------------------------|------------------------------|-----------|
| A — `imio.dms.mail` first, then this package | exactly one listed | opens as an overlay | completes end to end |
| B — this package first, then `imio.dms.mail` | exactly one listed | opens as an overlay | completes end to end |

notes:
- The specific `imio.dms.mail` widget exercised was not recorded by name; the operator
  reported overlay widgets working in both orders. Recorded as reported rather than
  filled in.
- **A defect was found while running this test that is outside COEX-07's stated
  criteria.** In Order A, two-factor authentication was **not** forced on an existing
  Plone Member account even though the "Globally enabled" setting was on. In Order B it
  was forced on first login. See the Gaps section below. COEX-07's stated criteria are
  met in both orders — the site works, the resource count is right, overlays work, 2FA
  login works — so this test is recorded as passed, and the enrolment difference is
  carried as a named gap with its own requirement (MFA-14) rather than folded into this
  result.

**Blocker encountered and cleared before this test could run:** creating a site from the
`imio.dms.mail:examples` profile aborted with `KeyError` on the absent `ska_secret_key`
record, because this package's instance-wide user-created subscriber read its registry
settings in a site that had not installed its profile. Fixed in quick task
`260805-f5m` (commit `184f053`), tracked as requirement COEX-10. The operator applied
the same guard inside the `server.dmsmail` buildout to unblock this test; the repository
fix landed afterwards.

### 2. Real browser overlay check on the login path (COEX-09)

**Why this could not be automated:** the automated test proves the token form's markup
and the redirect chain, but cannot prove the jQuery Tools overlay actually binds —
`zope.testbrowser` has no JavaScript engine, and Robot/Selenium is excluded from this
suite everywhere (`make test` and CI both pass `-t !robot`).

environment: `bin/instance fg`, real browser, clicking the header "Log in" link rather
than posting to the form directly.

expected: the login form and the 2FA token form both render inside the same stock Plone
overlay; a valid code completes login; a warning-level status message still renders
inside an overlay elsewhere on the site; the browser JS console reports no errors.

result: **passed**

- The 2FA form renders in the same overlay as the login form overlay.
- Warning status messages work.
- Browser JS console is empty.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

### existing-users-not-enrolled

status: open
requirement: MFA-14
found: 2026-08-05, while running test 1 above
blocks_phase_7: no (decided by the operator; COEX-07's stated criteria are met)

**What is wrong:** turning on the "Globally enabled" setting does not enrol accounts
that already exist when this add-on is installed. Only accounts created afterwards are
enrolled.

**Mechanism, confirmed by reading the code:**

- `is_two_factor_authentication_globally_enabled` is called from exactly two places:
  `userdataschema.userCreatedHandler` (fires only on user creation) and
  `browser/settings_helper.py` (decides which menu links to show).
- The login gate checks only each user's own `enable_two_factor_authentication`
  memberdata flag, at `helpers.py:1021` and `helpers.py:1044`. It never consults the
  global setting.
- Existing users are enrolled only when an administrator saves the settings control
  panel form, at `browser/controlpanel.py:125-132`. `setuphandlers.setupVarious` enrols
  nobody, even though the setting defaults to True.

**Why it matters:** installing this add-on into a running `imio.dms.mail` site is the
real deployment direction, and it is exactly the order that leaves every existing
account without a second factor. The setting's own description in
`browser/controlpanel.py:38` says it "globally enables the two-step verification for
all users", so an administrator reading it would reasonably believe otherwise.

**Candidate remedies, not yet chosen:**

1. Enrol existing users from `setuphandlers.setupVarious` when the setting is on. Simple
   and mirrors the control-panel behaviour, but writes memberdata for every user at
   install time, and raises `ValueError` when the seed encryption key is missing — the
   control panel handles that with an error message, an install step would need care not
   to half-enrol.
2. Make the login gate consult the global setting, so a user with the global setting on
   but no per-user flag is required to enrol at first login. More robust, covers users
   created by any route, and matches what Order B was observed to do. Larger behavioural
   change, and it touches the PAS boundary that Phase 4 settled.
3. Document an explicit post-install operator step: open the settings control panel and
   save it. Cheapest, but leaves a security control depending on a human remembering.
