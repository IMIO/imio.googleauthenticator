---
phase: 05
slug: drift-replay-and-lockout
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-03
---

# Phase 05 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: authored at plan time. All five plans (`05-01-PLAN.md` through `05-05-PLAN.md`)
carry a `<threat_model>` block, so this is verification of a pre-existing register, not a
retroactive reconstruction.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Anonymous HTTP to `@@google-authenticator-token` | Registered `permission="zope2.View"`, so reachable with no credentials. The caller supplies `auth_user` and a `ska` signature; the `__ac` cookie has already been cleared by the PAS plugin, so every request here is anonymous. | Username, TOTP code, `ska` signature, lock state (must not cross) |
| Anonymous HTTP to `@@reset-bar-code` | Also `permission="zope2.View"`, also takes its target account from an attacker-supplied `auth_user` query parameter. | Username, TOTP code, bar-code reset signature, lock state (must not cross) |
| Zope publisher transaction boundary | `ZPublisher` runs `finally: transactions_manager.abort()`, and `Unauthorized` is such an exception. A counter written on an aborting path is a security control that does not work and looks like it does. | Failure counter, lock deadline, last accepted TOTP interval |
| ZEO client to shared ZODB | Four instances (ports 8081 to 8084) serve one database. State kept per-instance in RAM would let an attacker multiply attempts by rotating clients. | Failure counter, lock deadline |
| Stored seed at rest | The TOTP seed is encrypted; the key is supplied by the environment and never stored in the ZODB (Phase 3). | Encrypted seed, encryption key (must not cross into ZODB, logs or exception text) |

---

## Threat Register

Severity and disposition are carried verbatim from the plans. Where the same threat identifier
appears in more than one plan against a different component, both rows are kept.

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-05-01 | Elevation of Privilege | `token.py::handleSubmit` | high | mitigate | Lock after `max_failed_attempts` (5) for `lockout_duration` (900 s), capping brute force per window. `test_lockout_after_five_failures` | closed |
| T-05-02 | Elevation of Privilege / Spoofing | `helpers.validate_token` | high | mitigate | Accepted interval stored; any matched interval `<=` it refused. `test_validate_token_rejects_replayed_interval` | closed |
| T-05-03 | Information Disclosure | `token.py::handleSubmit` | high | mitigate | Locked account answers a correct and an incorrect code identically. `test_locked_account_response_is_the_same_for_a_valid_and_an_invalid_code` | closed |
| T-05-03 | Information Disclosure | `reset_bar_code.py`, locked response | medium | mitigate | **Superseded by T-05-23 — this row's claim was false.** See the audit trail note below. | superseded |
| T-05-04 | Information Disclosure | replay-rejection log line | medium | mitigate | Log call carries no operand: no username, user id, token, secret or interval. `test_replay_rejection_log_has_no_username` | closed |
| T-05-05 | Tampering (of the control) | `memberdata_properties.xml`, `userdataschema.py` | high | mitigate | An undeclared property is silently popped by `setMemberProperties`, giving a lockout that never locks. Closed by the XML entries plus round-trip and profile-import tests | closed |
| T-05-06 | Tampering (of the control) | `helpers.register_failed_second_factor` | medium | mitigate | Every value `int()`-coerced before the write; the three helpers contain no `except`, so a declaration bug surfaces as a 500 rather than a silent no-op | closed |
| T-05-06 | Tampering (of the control) | counter write inside `reset_bar_code.py::handleSubmit` | high | mitigate | Both calls placed outside the file's broad `except Exception`. Verified in current source: `reset_failed_second_factor` at line 145 precedes `try:` at 146; `register_failed_second_factor` at 170 follows `except Exception:` at 166 | closed |
| T-05-07 | Tampering (of the control) | `pas_plugin.py`, `subscribers.py` | high | mitigate | No second-factor state write on a path the publisher aborts. Verified in current source: zero matches for the three counter names and three helper names in either file. `test_no_second_factor_state_written_from_the_plugin`, `test_failed_attempt_counter_survives_unauthorized_request` | closed |
| T-05-08 | Denial of Service | `reset_bar_code.py::handleSubmit` | medium | accept | An anonymous party can lock a named account with 5 wrong codes. Bounded to `lockout_duration` by self-expiry. Decision P5-13 | closed (accepted) |
| T-05-09 | Elevation of Privilege | `helpers` lock comparison | medium | mitigate | `locked_until > int(time.time())` on a plain int epoch, no `DateTime` round-trip. `test_lockout_expires_without_admin_action` | closed |
| T-05-10 | Denial of Service | `browser/forms/user_setup.py` | medium | mitigate | Deliberately excluded from the counter, so a user cannot lock themselves out mid-enrolment | closed |
| T-05-12 | Spoofing | `is_account_locked` for a Zope-root account | low | accept | Root memberdata returns `''`, coerced to unlocked. This plugin cannot gate a root login at all, so the lock would be decorative | closed (accepted) |
| T-05-13 | Elevation of Privilege | `helpers._find_accepted_interval` | high | mitigate | Candidate tuple is exactly `(current, current - 1)`; no forward window. `test_validate_token_rejects_future_interval` | closed |
| T-05-14 | Denial of Service | `helpers._is_six_digit_token` | medium | mitigate | ASCII digit membership tested explicitly, so a `unicode` string passing `isdigit()` is refused rather than raising an anonymously reachable 500 | closed |
| T-05-15 | Information Disclosure | `validate_token` decryption path | medium | accept | An undecryptable seed raises rather than answering "wrong token". Downgrading it would be a silent security downgrade. Unchanged from Phase 3 | closed (accepted) |
| T-05-16 | Elevation of Privilege | `reset_bar_code.py::handleSubmit` | high | mitigate | The unmetered path was an anonymous TOTP guessing oracle; the same lock and counter now gate it, evaluated before `validate_token`. `test_reset_bar_code_lockout_after_five_failures` | closed |
| T-05-17 | Information Disclosure | `reset_bar_code.py` distinct failure messages | low | accept | An unlocked attacker still learns which check failed. Pre-existing, bounded by the 5-attempt lock | closed (accepted) |
| T-05-18 | Information Disclosure | `token.py` lock gate position | high | mitigate | Gate moved behind successful `validate_user_data`, so an unsigned caller learns nothing. Verified in current source at line 108, and end to end by UAT test 4 | closed |
| T-05-19 | Information Disclosure | same handler, timing | low | accept | Residual timing difference upstream of the gate, dominated by Zope and `ska` HMAC overhead | closed (accepted) |
| T-05-20 | Elevation of Privilege | gate position relative to `validate_token` (token form) | high | mitigate | Verified in current source: `is_account_locked` at `token.py:108` precedes `validate_token` at 113 | closed |
| T-05-21 | Tampering (of the control) | counter call sites in `token.py` | high | mitigate | Calls not relocated onto an aborting path; zero matches in `pas_plugin.py` and `subscribers.py` | closed |
| T-05-22 | Information Disclosure | locked-account message string (token form) | medium | mitigate | Locked branch reuses the wrong-code message verbatim, so a signed caller cannot distinguish a lock from a wrong code | closed |
| T-05-23 | Information Disclosure | `reset_bar_code.py` locked-branch message wrapper | high | mitigate | Supersedes T-05-03. Both branches now emit `Setup failed! {0}` with the same reason. Asserted by equality of the full ordered message list in `test_no_signature_response_is_identical_for_a_locked_and_an_unlocked_account`, and confirmed end to end by UAT test 5 | closed |
| T-05-24 | Elevation of Privilege | gate position relative to `validate_token` (reset form) | high | mitigate | Verified in current source: `is_account_locked` at `reset_bar_code.py:123` precedes `validate_token` at 132 | closed |
| T-05-25 | Tampering (of the control) | counter call sites in `reset_bar_code.py` | high | mitigate | Verified by line position as recorded against T-05-06 above | closed |
| T-05-26 | Information Disclosure | `user not found` and `is_site_local_user` branches | medium | accept | A username-existence probe remains. Pre-existing, distinct from lock state, decision P5-17 | closed (accepted) |
| T-05-27 | Information Disclosure | message channel after the fix, residual | low | accept | Locked leg writes no property, wrong-code leg does; the timing and write-volume difference is not measurable across a network | closed (accepted) |
| T-05-SC | Tampering | dependency declarations | low | accept | This phase adds, removes and upgrades no package. `setup.py`, `test-4.3.cfg` and `requirements-4.3.txt` untouched | closed (accepted) |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-05-A | T-05-08 | An anonymous caller can lock a named account with five wrong codes. Both alternatives are worse: leaving the path unmetered restores T-05-16's guessing oracle, and admin-unlock-only lockout is ruled out in `REQUIREMENTS.md` as a denial-of-service primitive. Bounded to `lockout_duration` by MFA-09's self-expiry | operator, decision P5-13 | 2026-07-31 |
| R-05-B | T-05-26, T-05-17 | Username existence and which-check-failed remain disclosed at `@@reset-bar-code`. Pre-existing, predating Phase 5, and distinct from the lock-state oracle this phase closed. Fixing it later is strictly additive to the same two branches, and collapsing those messages would also remove the assurance a legitimate administrator needs that a Zope-root account cannot be gated by this plugin | operator, decision P5-17 | 2026-08-01 |
| R-05-C | T-05-12 | A Zope-root account is never locked, because its memberdata wrapper returns `''`. Accepted because this plugin cannot intercept a root login at all, so the lock would be decorative | plan 05-01 | 2026-07-31 |
| R-05-D | T-05-15 | An undecryptable stored seed raises out of `validate_token` and produces an error page rather than a clean "wrong token" refusal. Accepted deliberately and unchanged from Phase 3; downgrading it to a wrong-token answer would be a silent security downgrade | plan 05-02, carried from Phase 3 | 2026-07-31 |
| R-05-E | T-05-19, T-05-27 | Residual timing and write-volume differences between the locked and unlocked paths at both endpoints. Dominated by Zope request overhead, the `ska` HMAC every such request performs, and ZODB commit noise; not measurable across a network at the precision required | plans 05-04, 05-05 | 2026-08-01 |
| R-05-F | T-05-SC | No package legitimacy checkpoint is owed, because the phase adds no dependency | plans 05-01 to 05-05 | 2026-07-31 |

---

## Security Audit Trail

### Security Audit 2026-08-03

| Metric | Count |
|--------|-------|
| Threats found | 28 rows (27 distinct identifiers; T-05-03 appears twice) |
| Closed | 27 |
| Superseded | 1 |
| Open | 0 |
| Open at or above `high` | 0 |

Verification depth: ASVS level 1, blocking threshold `high`. The documented short-circuit applies —
`threats_open: 0` with the register authored at plan time at level 1 — so no auditor subagent was
spawned. Verification went beyond grep depth deliberately, for the reason in the next note.

**Why this audit did not rely on cited test names alone.** T-05-23 exists because T-05-03 was
recorded in `05-03-PLAN.md` as mitigated when it was not: it claimed the locked branch at
`@@reset-bar-code` reused the wrong-code message so no distinguishable response existed. The
embedded reason was indeed shared, but the two branches wrapped it in different top-level
templates about 45 lines apart, and the acceptance criterion offered — a substring count of
`Invalid token or token expired` — could only ever check the half that was true. A register that
has been wrong once in exactly this way should not be re-blessed by confirming that the named
tests exist. The three structural mitigations were therefore checked against current source:

- Lock evaluated before token arithmetic: `is_account_locked` at `token.py:108` precedes
  `validate_token` at 113; at `reset_bar_code.py:123` precedes 132.
- Counter writes outside the broad `except Exception` in `reset_bar_code.py`:
  `reset_failed_second_factor` at line 145 precedes `try:` at 146, and
  `register_failed_second_factor` at 170 follows `except Exception:` at 166.
- No second-factor state write in a non-committing path: zero matches for the three counter
  property names and three helper function names in `pas_plugin.py` and `subscribers.py`.

All 13 tests cited as mitigation evidence exist, and the full suite passes: 90 tests, 0 failures,
0 errors under `bin/test -t '!robot'`.

**End-to-end confirmation from UAT.** Two threats were additionally confirmed on a live
`server.dmsmail` deployment behind the real front-end proxy, which no in-process test can do:
T-05-18 (UAT test 4) and T-05-23 (UAT test 5). Both produced responses identical but for the
`Date` header, with matching status line, `Content-Length`, `Expires` and `Set-Cookie`. UAT test 1
also confirmed T-05-07's premise on real hardware: the failure counter is shared across four ZEO
clients, so it is not a per-instance RAM count an attacker could multiply by rotating clients.

### Changes landing after `05-VERIFICATION.md` was written

Three code changes landed during UAT, after the verification report. None opens a threat; one
closes an additional finding.

| Commit | Change | Security effect |
|--------|--------|-----------------|
| `6634113` | Removed the three lockout counters from `IEnhancedUserDataSchema` | Closes code-review finding WR-02 in `05-REVIEW.md`, which flagged that a single view's `omit()` call was the only barrier against a user editing their own `two_factor_authentication_locked_until` to zero. A field that is not on the schema cannot be written by any profile form. Also fixes a crash in `@@user-information`, recorded as UAT gap G-05-A. The `memberdata_properties.xml` entries are untouched, so T-05-05 remains closed and is now additionally covered by a persistence control in `tests/test_adapter.py` |
| `a14b012` | `@@request-bar-code-reset` no longer redirects to the portal root after sending the reset email | No threat. The old target was `self.context.absolute_url()`, an in-site URL, so this was never an open redirect; the defect was that an anonymous caller was bounced to a login page and never saw the confirmation |
| `452b66c` | `profiles/default/jsregistry.xml` pins both script registrations below jQuery | Not a Phase 5 threat, and belongs to Phase 7's scope. Recorded because the symptom was severe: on a fresh site the unpositioned registrations landed above jQuery, and the resulting `$ is not defined` aborted the cooked bundle before jQuery loaded, leaving every jQuery-dependent script on the site dead |

### Known, unaddressed — carried forward

- **Username existence at `@@reset-bar-code`** (T-05-26, R-05-B). Out of scope by decision P5-17.
- **Resource overrides that mutate what this package does not own.** `jsregistry.xml` still removes
  Plone's core `popupforms.js` with no uninstall counterpart, and a skin layer still replaces
  `login_form.cpt`. Phase 7 Success Criteria 2 and 3 own this.
- **The committing-path invariant against future code.** The source-level guard in
  `tests/test_pas_plugin.py` covers `pas_plugin.py` and `subscribers.py` as they exist today and
  cannot cover files that do not yet exist. Phase 6 adds recovery codes and, by its Success
  Criterion 3, new writers of the same counter — whoever plans it should extend that guard.

---

## Sign-Off

| Field | Value |
|-------|-------|
| Phase | 05 — drift-replay-and-lockout |
| Requirements | MFA-05 to MFA-13 |
| ASVS level | 1 |
| Blocking threshold | high |
| Open threats at or above threshold | 0 |
| Verdict | THREAT-SECURE |
| Audited | 2026-08-03 |
