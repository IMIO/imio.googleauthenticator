---
status: complete
phase: 02-registry-seeding-and-import-step-ordering
source: [02-VERIFICATION.md]
started: 2026-07-29T16:45:00Z
updated: 2026-07-29T16:50:00Z
---

## Current Test

[testing complete]

## Tests

### 1. REG-01 / SC-1 — creating a new Plone site with the add-on selected completes with no `ska_secret_key ... no record` error in `var/log/instance.log`

expected: `bin/instance fg`, create a new Plone site with `imio.googleauthenticator` selected, then `grep -e "no record" -e "Cannot find registry" var/log/instance.log` finds no matches.
result: pass
reported: "It appeared many times but I found no proof it comes from this package" — 26 `Cannot find registry` lines, no `no record` lines.
evidence: |
  Site creation ran twice (11:21 and 16:27 on 2026-07-29); `var/log/instance.log`
  from the real run was inspected directly.

  DECISIVE CRITERION — CLEAN. `grep -e "no record" -e "defines a field"` over
  `var/log/instance.log` and `var/log/instance-Z2.log`: zero matches. No
  `IGoogleAuthenticatorSettings defines a field ska_secret_key, for which there is
  no record`. No ERROR, WARNING or Traceback anywhere in the 16:27 run.

  SECOND GREP PATTERN IS A FALSE POSITIVE. The 26 `Cannot find registry` hits are
  emitted by `plone.app.registry-1.2.5/plone/app/registry/exportimport/handler.py:67`
  — a `logger.info` in the `queryUtility(IRegistry) is None` early-return branch. It
  fires for any profile whose `registry.xml` step runs before the `IRegistry` local
  utility exists, which during Plone site creation is every registry step queued
  ahead of `plone.app.registry`'s own profile. On the success path that handler logs
  nothing, so absence of a line for our profile is the success signal.

  NOT ATTRIBUTABLE TO THIS PACKAGE — timeline proof:
    - 11:21 run: last `Cannot find registry` 11:21:34 (line 2708);
      `Applying main profile profile-imio.googleauthenticator:default` 11:21:35 (line 2892).
    - 16:27 run: last `Cannot find registry` 16:27:42 (line 3206);
      `Applying main profile profile-imio.googleauthenticator:default` 16:27:43 (line 3390).
  All 26 occurrences precede our profile's import; zero occur inside its block.
  Immediately before our profile: `No upgrades available for profile
  profile-plone.app.registry:default` — the registry dependency resolving ahead of
  us, i.e. the REG-02 `<depends>` ordering doing its job.

test_definition_defect: |
  The `-e "Cannot find registry"` half of this grep is over-broad — it matches
  stock Plone 4.3 site-creation noise in every build and cannot distinguish our
  package. A future re-run should grep only for the attributable string:
      grep -e "no record" -e "defines a field ska_secret_key" var/log/instance.log
  Corrected in `reproduce` below. Not a code defect; no gap raised.

why_human: Deliberately not automated per D-01/D-02 — this is a declared
`verification: backstop` must_have. No second-site fixture exists (by design), and no
`var/log/instance.log` from a real site-creation run is available to the verifier. The
mechanised substitute controls all pass: the RECORDS assertion
(`test_registry_records_exist_after_install`), the DECLARATION assertion
(`test_import_step_declares_registry_dependency` — proven to fail when the `<depends>`
line is deleted), and the ORDERING assertion (`test_import_step_ordering`).

reproduce: |
  bin/instance fg
  # In another shell: browse to http://localhost:8080, add a Plone site,
  # tick "Google Authenticator plugin (imio.googleauthenticator)" in the
  # add-ons list on the site-creation form.
  # Then, back in the repo — attributable strings only, NOT "Cannot find registry":
  grep -e "no record" -e "defines a field ska_secret_key" var/log/instance.log

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
