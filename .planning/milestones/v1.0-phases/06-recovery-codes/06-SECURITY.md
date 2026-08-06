---
phase: 06
slug: recovery-codes
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: 2026-08-04
---

# Phase 06 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

The register below was written during planning, inside the `<threat_model>` blocks of
`06-01-PLAN.md`, `06-02-PLAN.md` and `06-03-PLAN.md`. This audit verifies that each
mitigation named there is present in the code that was actually written.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Anonymous browser to the token entry form (`@@google-authenticator-token`) | The form is registered with the `zope2.View` permission. The submitted `token` field and the `auth_user` query parameter are both fully attacker-controlled. | A submitted six-digit code or sixteen-character recovery code |
| `helpers.py` to the member-data store in the ZODB | Reads and writes go through `setMemberProperties` / `getProperty` on a property sheet backed by a persistent tree. Property names that are not declared are dropped silently rather than raising. | Recovery-code salt and hash list |
| Process memory to persistent storage | The plaintext recovery codes cross this boundary exactly once, in one direction, and only as a hash. Any other crossing (a log line, a cookie, an exception message, a session) would be a defect. | Ten plaintext recovery codes |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-06-01 | Information Disclosure | Offline guessing of the stored salt-and-hash pair after a database compromise | medium | mitigate | Each code is 10 random bytes (80 bits) from `os.urandom`, base32-encoded to 16 characters; one 16-byte random salt per user; PBKDF2-HMAC-SHA256 at 100,000 iterations. Confirmed at `helpers.py:54`, `:59`, `:69`, `:601`, `:624`, `:626`. | closed |
| T-06-02 | Elevation of Privilege | Recovery-code guessing at the token entry form with no rate limit | high | mitigate | The recovery-code branch is reachable only through the single `validate_second_factor` call at `browser/forms/token.py:113`. The account-lock check runs before it (line 108); the failure counter is incremented after it on the failure path (line 140) and cleared on the success path (line 120). No second counter and no second call site. | closed |
| T-06-03 | Tampering | Reuse of a recovery code that was already spent | high | mitigate | The matched entry is removed by list index (`stored[:i] + stored[i + 1:]`, `helpers.py:689`) in the same call that returns success, so two identical stored entries cannot both be spent by one submission. | closed |
| T-06-04 | Information Disclosure | The number of remaining codes acting as a signal to an unauthenticated or failed caller | medium | mitigate | The low-count message is queued inside the branch that has already accepted the code, after the write and before returning success (`helpers.py:708-715`). A failed or anonymous submission cannot reach it. | closed |
| T-06-05 | Information Disclosure | A plaintext code, the salt, or a computed hash reaching a log line or an exception message | high | mitigate | No logging call anywhere in `helpers.py` takes a code, salt, hash, or count as an argument (all calls checked). In `browser/forms/user_setup.py` the only logging call on the enrollment path is `logger.exception("Two-step verification setup failed")` (line 123), a fixed string with no argument. | closed |
| T-06-06 | Denial of Service | A per-code salt making one submitted code cost ten key-derivation runs on a login-adjacent page | medium | mitigate | The salt property is declared `type="string"` — a single value, not a list — in `profiles/default/memberdata_properties.xml:9`. One submitted code therefore costs exactly one key-derivation call regardless of how many hashes are stored. | closed |
| T-06-07 | Information Disclosure | Plaintext codes stored in the visitor's browser because Plone 4 keeps queued status messages in a cookie | high | mitigate | The codes are written into the response body by `browser/forms/recovery_codes.pt` only. No status message anywhere carries a code: the enrollment success message is a fixed translated string, and the failure message interpolates only one of two fixed translated strings. | closed |
| T-06-08 | Spoofing | Someone holding one stolen recovery code, or a hijacked session, minting a fresh durable set | medium | mitigate | Regeneration goes through the setup form, which requires a currently valid code from the authenticator app before it writes anything (`browser/forms/user_setup.py:94`). That form deliberately keeps calling `validate_token` rather than the recovery-code-accepting dispatcher, so one recovery code cannot produce a new set. See accepted risk R-06-01 for the residual gap in this control. | closed |
| T-06-09 | Spoofing | A locked account revealing its state through how long the response takes | low | accept | The account-lock check returns before the key-derivation call is ever reached, so a locked account produces no timing signal at all. For an unlocked account, a valid and an invalid sixteen-character code cost one identical key-derivation call. | closed |
| T-06-10 | Information Disclosure | A "Regenerate recovery codes" menu item shown to someone who never enrolled | low | mitigate | The menu item's availability expression is `portal/@@show-disable-two-factor-authentication-link`, which is true only when the feature is switched on globally and this user has enrolled (`profiles/default/actions.xml:45`). | closed |
| T-06-11 | Denial of Service | A user losing their whole set by re-entering the setup form and regenerating without meaning to | low | accept | Regeneration requires a valid code from the authenticator app, so it cannot happen by a stray click. A confirmation step was rejected as new attack surface for an outcome the user can recover from themselves. | closed |
| T-06-12 | Information Disclosure | A browser or intermediate cache retaining the response body that displayed the codes | low | accept | Outside this application's control. The response is authenticated and served over the deployment's transport encryption. Adding cache-control headers to this one response is a possible later change, not a phase 6 requirement. | closed |
| T-06-13 | Denial of Service | The low-count message raising an error on the login path and refusing an otherwise valid code | medium | mitigate | When no current request exists, the message is skipped and the code is still accepted (`helpers.py:709`, `if request is not None`). This is deliberately not a blanket exception handler, so a real write failure still surfaces rather than producing a code that looks spent and is not. | closed |
| T-06-14 | Tampering | A later edit adding a second, unmetered place where a second factor is checked | high | mitigate | `tests/test_token.py` counts the call sites in `browser/forms/token.py` by reading its source: exactly one dispatcher call, one failure-counter call, one reset call; and asserts the dispatcher is absent from `browser/forms/user_setup.py` and `browser/forms/reset_bar_code.py`. The assertion was made to fail against a deliberately injected second call before being accepted. | closed |
| T-06-15 | Tampering | Recovery-code state written from `pas_plugin.py` or `subscribers.py`, where an aborted transaction discards it, producing a control that appears present and never fires | high | mitigate | `tests/test_pas_plugin.py` reads the source of both modules and refuses the two new property names and all three new helper function names. The check was made to fail against a deliberately introduced name in each of the two guarded modules before being accepted. | closed |
| T-06-16 | Information Disclosure | The remaining code count leaking through how long the response takes rather than through its content | low | accept | One submitted code costs exactly one key-derivation call regardless of how many hashes are stored, because the salt is per user. The constant-time comparison loop over at most ten 64-character strings is negligible against a roughly 0.1-second key derivation. | closed |
| T-06-SC | Tampering | Package-manager installs pulling a substituted package | n/a | n/a | This phase adds no dependencies. Every primitive used (`hashlib`, `hmac`, `base64`, `os`, `binascii`) is in the Python 2.7.18 standard library already present in this build. | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above the "high" blocking setting count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-06-01 | T-06-08 (residual) | The setup form at `browser/forms/user_setup.py:94` checks the authenticator code with no rate limiting: it does not consult the account lock before checking, and does not touch the failure counter on either outcome. The login form (`browser/forms/token.py`) and the seed-reset form (`browser/forms/reset_bar_code.py`) both do all three. Because the "Regenerate recovery codes" menu item points at this same form, that unmetered check is what stands in front of minting a fresh set of ten codes. The exposure is bounded: the same page renders the account's own authenticator QR code, which contains the secret, to any logged-in site-local user who opens it (`browser/forms/user_setup.py:169`), so repeated guessing gains an attacker nothing they could not read directly off the page. The gap predates this phase — phase 5 added the rate limiting to the seed-reset form and did not extend it here. Closing it remains worthwhile for consistency between the three places a second factor is checked, and is a candidate for a later phase. | Chris | 2026-08-04 |

Recorded from the manual-verification decision in `06-UAT.md`, test 1.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-08-04 | 17 | 17 | 0 | Claude (orchestrator, ASVS level 1 source verification) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-08-04
