---
status: testing
phase: 04-pas-boundary
source: [04-VERIFICATION.md]
started: 2026-07-31T00:00:00Z
updated: 2026-07-31T00:00:00Z
---

## Current Test

number: 1
name: Confirm with iMio operations owners that no cron job, script, WebDAV mount, FTP client or XML-RPC integration authenticates against this Plone site's own acl_users over HTTP Basic Auth.
expected: |
  No live external consumer of credentials_basic_auth against this site is found, or any found
  consumer is migrated to the service-account + ip_addresses_whitelist alternative documented in
  README.rst before this package is deployed with 2FA enabled for real users.
awaiting: user response

## Tests

### 1. Confirm with iMio operations owners that no external consumer depends on HTTP Basic Auth against this Plone site's acl_users

expected: No cron job, script, WebDAV mount, FTP client or XML-RPC integration authenticates against this site over `Authorization: Basic`; or any such consumer found is migrated to the service-account plus `ip_addresses_whitelist` alternative documented in README.rst before deployment.
result: [pending]

why_human: The decision recorded at plan 04-02's checkpoint on 2026-07-31 — keep `credentials_basic_auth` active — rests on a grep search across three iMio repositories (`imio.dms.mail`, `server.dmsmail`, `industrialisation`) that 04-RESEARCH.md explicitly documents as non-exhaustive (Assumptions Log A1). No test in this repository can prove the absence of an external consumer. `04-VALIDATION.md` records this in its Manual-Only Verifications table as NOT DONE, and the DOC-02 section of README.rst instructs the operator to perform this check before deploying.

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
