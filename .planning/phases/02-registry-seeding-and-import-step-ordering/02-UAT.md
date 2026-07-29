---
status: testing
phase: 02-registry-seeding-and-import-step-ordering
source: [02-VERIFICATION.md]
started: 2026-07-29T16:45:00Z
updated: 2026-07-29T16:45:00Z
---

## Current Test

number: 1
name: REG-01 / Success Criterion 1 — real site-creation smoke check
expected: |
  Running `bin/instance fg` and creating a new Plone site with
  `imio.googleauthenticator` selected in the add-ons list completes, and

      grep -e "no record" -e "Cannot find registry" var/log/instance.log

  finds no matches.

  Specifically, this string must NOT appear:

      IGoogleAuthenticatorSettings defines a field ska_secret_key,
      for which there is no record

awaiting: user response

## Tests

### 1. REG-01 / SC-1 — creating a new Plone site with the add-on selected completes with no `ska_secret_key ... no record` error in `var/log/instance.log`

expected: `bin/instance fg`, create a new Plone site with `imio.googleauthenticator` selected, then `grep -e "no record" -e "Cannot find registry" var/log/instance.log` finds no matches.
result: [pending]

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
  # Then, back in the repo:
  grep -e "no record" -e "Cannot find registry" var/log/instance.log

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
