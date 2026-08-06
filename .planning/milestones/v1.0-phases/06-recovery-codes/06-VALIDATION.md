---
phase: 6
slug: recovery-codes
# status lifecycle: draft (seeded by plan-phase) → validated (set by validate-phase §6)
# audit-milestone §5.5 distinguishes NOT-VALIDATED (draft) from PARTIAL (validated + nyquist_compliant: false) (#2117)
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-03
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `zope.testrunner` via `bin/test`, unittest2-style test cases on `plone.app.testing` layers |
| **Config file** | None dedicated — discovery comes from the buildout `[test]` part in `base.cfg`; layers live in `src/imio/googleauthenticator/testing.py` |
| **Quick run command** | `bin/test -t test_helpers` (unit) / `bin/test -t test_token` (integration) |
| **Full suite command** | `bin/test -t '!robot'` |
| **Estimated runtime** | ~90 seconds full suite (layer setup dominates); ~20 seconds for a single `-t` selector |

---

## Sampling Rate

- **After every task commit:** Run `bin/test -t test_helpers` and/or `bin/test -t test_token` — whichever file the task touched
- **After every plan wave:** Run `bin/test -t '!robot'`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

Task IDs are assigned when PLAN.md files are written; `/gsd-validate-phase 6` fills this table
against the real task list. The requirement-level map below is lifted from
`06-RESEARCH.md` § Validation Architecture and is the contract each task's `<verify>` must satisfy.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | RECOV-01 | — | 10 codes issued, 16 base32 characters each, 80 bits of entropy per code | unit + integration | `bin/test -t test_helpers` / `bin/test -t test_user_setup` | ✅ both files exist | ⬜ pending |
| TBD | TBD | TBD | RECOV-02 | T-6 Information Disclosure | Plaintext codes appear nowhere in the ZODB; only a PBKDF2 hash with one per-user salt | unit | `bin/test -t test_helpers` | ✅ exists | ⬜ pending |
| TBD | TBD | TBD | RECOV-03 | T-6 Information Disclosure | Codes rendered exactly once, in the same response that generates them; never redisplayed | integration (`Browser`) | `bin/test -t test_user_setup` | ✅ exists | ⬜ pending |
| TBD | TBD | TBD | RECOV-04 | T-6 Tampering (replay) | A code authenticates in place of a TOTP token, is consumed on use, and is refused on a second use | integration (`Browser` POST to `@@google-authenticator-token`) | `bin/test -t test_token` | ✅ exists | ⬜ pending |
| TBD | TBD | TBD | RECOV-05 | T-6 Elevation of Privilege | A failed recovery-code attempt increments the same lockout counter as a failed TOTP attempt | integration + source grep | `bin/test -t test_token` / `bin/test -t test_pas_plugin` | ✅ both exist | ⬜ pending |
| TBD | TBD | TBD | RECOV-06 | — | Regenerating the set invalidates every previously issued code | unit + integration | `bin/test -t test_helpers` / `bin/test -t test_user_setup` | ✅ both exist | ⬜ pending |
| TBD | TBD | TBD | RECOV-07 | T-6 Information Disclosure | The user is warned when 3 or fewer codes remain, and only after a successful authentication | integration (`IStatusMessage`) | `bin/test -t test_token` | ✅ exists | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None. Existing test infrastructure covers all phase requirements — the `plone.app.testing` layers,
the shared base test case, and the `Browser` helpers are already in place. This phase adds test
methods to four existing files (`test_helpers.py`, `test_token.py`, `test_user_setup.py`,
`test_pas_plugin.py`); it creates no new test file and needs no new fixture.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A real Google Authenticator user, having lost their phone, logs in with a printed recovery code | RECOV-04 | End-to-end path crosses a real browser session and a physical second device that no automated test in this package drives (`test_robot.py` is excluded everywhere) | Enrol a test user, save the 10 codes, delete the authenticator entry from the phone, log in with one saved code, confirm access and confirm the same code is refused on a second login |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
