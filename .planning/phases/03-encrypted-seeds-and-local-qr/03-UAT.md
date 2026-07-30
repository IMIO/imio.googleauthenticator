---
status: testing
phase: 03-encrypted-seeds-and-local-qr
source: [03-VERIFICATION.md]
started: 2026-07-30T15:10:00Z
updated: 2026-07-30T15:10:00Z
---

## Current Test

number: 1
name: Enrol with a real TOTP authenticator app and log in end to end
expected: |
  QR renders and is scannable at the size the form displays it (a `data:` URI, with no
  outbound network request visible in the browser's network panel); the `otpauth://`
  label reads as `<username>@<domain>`; the 6-digit code the app shows is accepted at
  enrollment; and the same app's current code, after logout and a fresh
  username/password login, is accepted at `@@google-authenticator-token` and reaches the
  site as the authenticated user.
awaiting: user response

## Tests

### 1. Enrol with a real TOTP authenticator app and log in end to end

expected: QR renders and is scannable as displayed (a `data:` URI — no outbound request in the browser network panel); the `otpauth://` label reads `<username>@<domain>`; the app's 6-digit code is accepted at enrollment; after logout and a fresh username/password login the app's current code is accepted at `@@google-authenticator-token` and the user reaches the site authenticated.
result: [pending]

why_human: Requires a physical or virtual TOTP authenticator app scanning a real QR code
rendered by a running `bin/instance`, plus a live login round trip — not executable by an
automated agent. Deliberately deferred to end-of-phase per
`workflow.human_verify_mode=end-of-phase` (03-03-PLAN.md Task 2's `<verify><human-check>`);
03-03-SUMMARY.md confirms it was not performed during execution.
`test_seed_encryption_round_trip` proves the seed survives Fernet encryption and that
`onetimepass` accepts a computed token — it does not prove what a phone parses, displays,
or accepts as a fresh code.

setup: This phase's feature is not deployable until the `industrialisation` repo's Puppet
`concat::fragment` ships the key (out of repo, tracked). To run this test locally, generate
a key and export it before starting Zope:

    export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY="$(bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())")"
    bin/instance fg

covers: ROADMAP Phase 3 success criterion 4, SEC-06 (160-bit `os.urandom` seed — the
entropy half is machine-verified; the real-app acceptance half is not)

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
