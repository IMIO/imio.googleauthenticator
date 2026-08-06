---
phase: 9
slug: mail-path-and-profile-page-correctness
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-06
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `bin/test` (`plone.app.testing` layers), `unittest2` test classes |
| **Config file** | none — layers and fixtures are Python (`testing.py`, `tests/base.py`); coverage config is `.coveragerc` |
| **Quick run command** | `bin/test -t test_request_bar_code_reset` / `bin/test -t test_user_setup` / `bin/test -t test_adapter` |
| **Full suite command** | `bin/test -t '!robot'` |
| **Estimated runtime** | ~60–120 seconds full suite (Plone 4.3 layer setup dominates); single-module runs are faster |

---

## Sampling Rate

- **After every task commit:** Run the scoped module command for the file just changed
  (`bin/test -t test_request_bar_code_reset`, `-t test_user_setup`, or `-t test_adapter` /
  the new `test_userdataschema` module).
- **After every plan wave:** Run `bin/test -t '!robot'`
- **Before `/gsd-verify-work`:** Full suite green, plus `bin/test-coverage -t '!robot'` at
  `--fail-under=90`
- **Max feedback latency:** ~120 seconds

---

## Per-Task Verification Map

> Task IDs are assigned when PLAN.md files are written. This table is seeded from the
> research's Phase Requirements → Test Map and is filled in by `/gsd-validate-phase`.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | BUG-07 | — | A rejected or unreachable mail server produces the form's shared in-page error message and no Zope error page; no distinguishing message that would widen the username-enumeration oracle (T-03-26) | integration | `bin/test -t test_request_bar_code_reset` | ✅ existing file, new method | ⬜ pending |
| TBD | TBD | TBD | BUG-08 | Confused-deputy admin link | `@@user-information` field description contains neither `@@setup-two-factor-authentication` nor `@@disable-two-factor-authentication` | unit (schema-level) | `bin/test -t test_adapter` (or new `test_userdataschema`) | ❌ W0 — no existing test asserts on the field description text | ⬜ pending |
| TBD | TBD | TBD | UX-01 | — | Recovery-codes page link targets the navigation root, text reads "Continue to the home page" | integration (template render) | `bin/test -t test_user_setup` | ✅ existing file; existing test already renders the form and inspects markup | ⬜ pending |
| TBD | TBD | TBD | UX-02 | — | Base32 secret appears in the rendered `qr_code` field description and equals `get_or_create_secret()` for that user | unit / integration | `bin/test -t test_user_setup` (or `-t test_helpers` for `get_token_description()`) | ❌ W0 — `get_token_description()` has no dedicated test today | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] BUG-08 field-description assertion — add to `src/imio/googleauthenticator/tests/test_adapter.py`
      (already imports `IEnhancedUserDataSchema`) or create `tests/test_userdataschema.py`. A plain
      `zope.schema` field-attribute assertion needs no Zope request or traversal.
- [ ] UX-02 secret-in-description assertion — extend `src/imio/googleauthenticator/tests/test_user_setup.py`,
      which already builds a real `SetupForm` and calls `.update()` / `.render()`.
- [ ] BUG-07 raising-mail test — extend `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py`'s
      existing `Products.MailHost.MailHost.MailBase._send` monkeypatch with a raising variant.

No framework install needed — `zope.testrunner`, `unittest2`, and all three target test files
already exist and already exercise the exact forms and functions this phase modifies.

**Project convention (inherited from phases 1–8):** every new test gets a non-vacuity check —
prove it goes red against the unmodified source, then restore the source byte-identical.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| The displayed base32 secret, typed or pasted into a real desktop TOTP client or password manager, produces codes the site accepts | UX-02 | A unit test can assert the secret string is rendered and matches `get_or_create_secret()`, but it cannot drive a third-party TOTP client. CONTEXT.md `<specifics>` states this half of criterion 4 is a UAT step, not a unit test. | 1. Enrol a test user at `@@setup-two-factor-authentication`. 2. Copy the base32 text shown beside the QR code. 3. Enter it into a desktop TOTP client (or password manager) as a manually-entered setup key. 4. Log out, log in, and submit the code the client shows. 5. Confirm the site accepts it. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
