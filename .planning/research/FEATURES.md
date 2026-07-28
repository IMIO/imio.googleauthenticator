# Feature Research

**Domain:** TOTP second-factor hardening in a CMS auth plugin (Plone 4.3 PAS, Python 2.7)
**Researched:** 2026-07-28
**Confidence:** MEDIUM (standards quoted verbatim from primary documents and cross-corroborated; vendor defaults corroborated across two or more sources; local codebase facts read directly = HIGH)

**Scope note:** this file covers only the five hardening items named in the milestone. Enrollment,
the token form, email bar-code reset, the IP whitelist and the control panel already exist and are
not re-researched. Everything in PROJECT.md "Out of Scope" is honoured — no WebAuthn, no SMS, no
`pyotp` swap, no Python 3, no async, no caching.

---

## The standards, in one place

Every parameter below traces to one of these. Cited by number throughout.

| Standard | Section | What it says (verbatim where quoted) |
|---|---|---|
| RFC 6238 | §5.2 | "The verifier **MUST NOT** accept the second attempt of the OTP after the successful validation has been issued for the first OTP, which ensures one-time only use of an OTP." |
| RFC 6238 | §5.2 | X = 30 s default time step. "We RECOMMEND that at most one time step is allowed as the network delay." |
| RFC 6238 | §6 | Validator SHOULD set a specific limit on how many time steps a prover may be out of sync, forward and backward. |
| RFC 4226 | §4 R6 | Shared secret MUST be ≥128 bits, RECOMMENDED 160 bits. |
| RFC 4226 | §7.3 | Throttling param T "SHOULD be set as low as possible, while still ensuring that usability is not significantly impacted". Explicitly offers backoff: "after 1 attempt the server waits 5 seconds, at the second failed attempt it waits 5*2 = 10 seconds, etc." |
| RFC 4226 | §7.4 | Look-ahead window s "SHOULD be set as low as possible". |
| NIST SP 800-63B | §5.2.2 | Verifiers **SHALL** limit consecutive failed authentication attempts on a single account to **no more than 100**. Suggests CAPTCHA or an increasing wait "(e.g., 30 seconds up to an hour)" to avoid locking out legitimate users. |
| NIST SP 800-63B | §5.1.2.2 | Look-up secrets (= recovery codes): **SHALL** have ≥20 bits entropy, **SHALL** come from an approved RBG, **SHALL** be used successfully only once; if <64 bits entropy the verifier **SHALL** rate-limit. |
| OWASP ASVS 4.0 | 2.8.4 | "Verify that time-based OTP can be used only once within the validity period." (CWE-287) |
| OWASP ASVS 4.0 | 2.8.5 | Reuse within the validity period must be **logged and rejected**, with notification to the device holder. (CWE-287) |
| OWASP ASVS 4.0 | 2.2.1 | "no more than 100 failed attempts per hour is possible on a single account" (CWE-307) |
| OWASP ASVS 4.0 | 2.6.1/2.6.2/2.6.3 | Lookup secrets single-use; ≥112 bits entropy **or** salted with a unique random ≥32-bit salt and hashed with an approved one-way hash; resistant to offline attacks. |

**Vendor defaults used as sanity anchors** (Keycloak matters most — it is the successor system):

| System | Drift window | Lockout | Recovery codes |
|---|---|---|---|
| Keycloak | `lookAheadWindow` default **1** | `failureFactor` default **30**, temporary disable, `maxFailureWaitSeconds` default **900 s** | **12** codes, consumed sequentially |
| django-otp | `tolerance` default **1** | exponential, `THROTTLE_FACTOR` **1** → `1·2^(n-1)` s = 1,2,4,8… | n/a (separate static-token plugin) |
| GitHub | — | — | **16** codes, 10 alnum chars, `xxxxx-yyyyy` |
| Google | — | — | **10** codes, 8 digits |
| GitLab | — | — | **10** codes, 16 hex chars |

**This is a real bug class, not a theoretical one.** TOTP-valid-after-use shipped in Craft CMS
(SBA-ADV-20240617-01), the Craft two-factor plugin (SBA-ADV-20240202-02) and Vikunja
(GHSA-p747-qc5p-773r, CVSS 5.7). All three fixes were the same shape as below.

---

## Local facts that determine the design

Read directly from the codebase (confidence HIGH):

1. **`onetimepass.valid_totp(token, secret)` accepts ZERO drift.** Its body is
   `_is_possible_token(token) and int(token) == get_totp(secret)`, and `get_totp` hardcodes
   `int(time.time()) // 30`. So the package today accepts only the current 30 s step, and
   `helpers.validate_token()` (line 205) gets back a bare `True`/`False` — **no counter**.
2. **`onetimepass.get_hotp(secret, intervals_no)` is public.** It is the counter-level primitive.
   Replay detection and drift tolerance are both trivially expressible on top of it. No `pyotp`
   needed — which is exactly why PROJECT.md can keep that swap out of scope.
3. **`_is_possible_token()` accepts any digit string of length ≤ 6**, and compares via
   `int(token)`, so `"1"`, `"000123"` and `"123"` are all accepted candidates.
4. **`generate_secret()` is `rebus.b32encode(str(uuid4()))`** — base32 of the 36-character UUID
   *string*, i.e. a 36-byte HMAC key carrying ~122 bits of entropy in a 58-character secret.
   122 bits is marginally under RFC 4226 §4 R6's 128-bit MUST.
5. **`hmac.compare_digest` is available** (Python 2.7.7+; we are on 2.7.18). No backport needed for
   constant-time comparison — this also unblocks the `reset_bar_code.py:104` fix in CONCERNS.md.
6. **The plugin already knows the extractor**: `pas_plugin.py:157` reads
   `credentials.get('extractor')`. The hook for the basic-auth fix exists; it is currently dead code
   (`return None` either way).
7. **The plugin's actual deny mechanism is the credentials wipe**, not `return None`
   (`pas_plugin.py:127-133`). Returning `None` only means "this plugin abstains" — PAS keeps
   polling later `IAuthenticationPlugin`s. This is the single most important thing to get right in
   the basic-auth fix.
8. **Nothing is deployed.** No enrolled users, so every storage decision below is greenfield: no
   dual-read, no re-encryption, no upgrade steps.

---

## Feature Landscape

### Table Stakes (the second factor is not credible without these)

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| **F1a. Counter-returning token validation** | Prerequisite for everything else in this milestone | LOW | Replace `valid_totp` with a loop over `get_hotp(secret, T-k)`; return the **matched counter** or `None`. ~6 lines. Also reject any input that is not exactly 6 digits (tightens fact 3). |
| **F1b. Drift tolerance of one backward step** | Without it a code typed at second 29 of its window fails — the classic usability cliff. RFC 6238 §5.2 explicitly allows one step of network delay | LOW | Accept counters **{T, T−1}** only. Effective validity 30–60 s. Same 6 lines as F1a. Matches Keycloak `lookAheadWindow=1` and django-otp `tolerance=1`. |
| **F1c. Replay rejection** | RFC 6238 §5.2 **MUST NOT**; ASVS 2.8.4 | LOW | Store `last_used_totp_counter` (int) in memberdata. Accept iff `matched_counter > last_used_totp_counter`. Write the matched counter on success. This is the standard shape and it costs one integer. |
| **F1d. Log a detected replay** | ASVS 2.8.5 | LOW | One `logger.warning` at the rejection point. No username in plaintext (CONCERNS.md flags `pas_plugin.py:90` logging). |
| **F2a. Failed-attempt counter** | NIST SP 800-63B §5.2.2 **SHALL**; ASVS 2.2.1; CONCERNS.md "No Account Lockout" | LOW | `totp_failed_attempts` (int) in memberdata. Increment on any failed second-factor submission. Reset to 0 on success. |
| **F2b. Time-expiring lock at N=5** | Makes 6-digit brute force infeasible | LOW | `totp_locked_until` (timestamp) in memberdata. On the 5th consecutive failure set it to now + **900 s (15 min)**. Reject submissions while locked without evaluating the token. Self-clearing — **no admin action required**. |
| **F2c. Recovery-code attempts hit the same counter** | Otherwise recovery codes are the un-throttled brute-force path | LOW | Same two fields, one shared check. This is the reason F3 depends on F2. |
| **F3a. 10 single-use recovery codes, hashed** | Only self-service path when the phone is lost; NIST §5.1.2.2; ASVS 2.6.1–2.6.3; CONCERNS.md "No Recovery Codes" | MEDIUM | **10 codes** × **16 base32 chars** from `base64.b32encode(os.urandom(10))` = **80 bits** each. Display grouped `xxxx-xxxx-xxxx-xxxx`, lowercased. Store one salted **SHA-256** per code: `os.urandom(16)` salt, value `salt_hex + ":" + sha256(salt + normalized_code).hexdigest()`, as a list in a memberdata property. |
| **F3b. Consume on use** | NIST §5.1.2.2 "SHALL be used successfully only once"; ASVS 2.6.1 | LOW | On match, remove that entry from the list and write back before completing login. Compare with `hmac.compare_digest`. |
| **F3c. Shown exactly once, at enrollment** | Hashing is pointless if the plaintext can be re-displayed | LOW | Render once on the enrollment page next to the QR code, in a copyable/printable block. Never re-displayable. |
| **F3d. Regenerate the whole set** | Only recovery path when codes are exhausted or exposed | LOW | Button on the user setup page. Generating a new set invalidates the entire old set (GitHub, Google, GitLab all do exactly this). Also shows the new codes once. |
| **F3e. Remaining-count display** | Users must be able to see they are running out before they run out | LOW | Show "N of 10 remaining" on the user setup page; visual warning at **≤3**. At 0, TOTP still works and the existing email bar-code reset remains the fallback. |
| **F4a. Fernet-encrypted seed, key from env** | PROJECT.md core reason the fork exists; ASVS 2.8.2 | MEDIUM | New property `two_factor_authentication_secret_encrypted`; old plaintext property never written. Fernet from `cryptography==3.3.2`. Key read via `os.getenv()`, 32 url-safe-base64 bytes (the Fernet key format). `decrypt(token)` with **no TTL** — a seed does not expire. |
| **F4b. Fail closed when the key is absent** | The single mistake that would silently undo F4a | LOW | Missing/invalid key → raise, log, and refuse the second factor. **Never** fall back to reading or writing plaintext. Fail closed also at enrollment, not just at validation. |
| **F5a. Deny, do not challenge, on the basic-auth extractor** | An auth path that never invokes the challenge makes MFA irrelevant for whoever finds it. Documented class: M365 legacy auth / BAV2ROPC, legacy IMAP/POP3/SMTP; OWASP WSTG 4.11 | MEDIUM | For a 2FA-enrolled user whose credentials came from `credentials_basic_auth`: **wipe the credentials dict** (fact 7 — this is what actually denies), do **not** redirect (a 302 to an HTML form is meaningless to a non-browser client), return `None`. Net effect is a 401. |
| **F5b. Documented consequence** | This breaks scripts/WebDAV/API clients that basic-auth as an enrolled user | LOW (docs) | Conventional answer, no code: those consumers use a non-2FA service account, or are covered by the existing IP whitelist. Deployment note, must not be silently discovered in production. |
| **F6. Cross-ZEO-consistent state** | PROJECT.md constraint. Per-process counters let an attacker rotate ZEO clients and multiply attempts by the client count | LOW | All of F1c, F2a, F2b, F3a live in memberdata properties on the same member record. One write per authenticated request. |

**Recommended parameter set, copy-pasteable into a plan:**

| Parameter | Value | Source |
|---|---|---|
| Time step X | 30 s | RFC 6238 §5.2 default; already what `onetimepass` hardcodes |
| Digits | 6 | Existing; Google Authenticator default |
| Accepted counters | `{T, T−1}` (2 candidates, backward only) | RFC 6238 §5.2 one-step network delay; Keycloak `lookAheadWindow=1` |
| Replay rule | accept iff `matched_counter > last_used_totp_counter` | RFC 6238 §5.2; ASVS 2.8.4 |
| Lockout threshold N | **5** consecutive failed second-factor attempts | Well under the NIST §5.2.2 ceiling of 100 |
| Lock duration | **900 s (15 min)**, auto-expiring | Keycloak `maxFailureWaitSeconds` default 900; inside NIST's "30 seconds up to an hour" |
| Counter reset | on any successful second factor (TOTP or recovery code) | django-otp `ThrottlingMixin` semantics |
| Recovery code count | **10** | Google, GitLab; Keycloak 12, GitHub 16 — 10 is the median |
| Recovery code entropy | **80 bits** (`os.urandom(10)`) | ASVS 2.6.3 offline resistance; ≫ NIST §5.1.2.2's 20-bit floor |
| Recovery code encoding | RFC 4648 base32 → 16 chars, displayed `xxxx-xxxx-xxxx-xxxx` | GitLab's 16-char precedent; `os.urandom(10)` → base32 is exactly 16 chars, no padding |
| Recovery code storage | per-code random 16-byte salt + SHA-256 | ASVS 2.6.2 ("unique and random 32-bit salt", approved one-way hash) |
| Recovery code comparison | `hmac.compare_digest` | Available in py2.7.18 |
| Seed cipher | Fernet (AES-128-CBC + HMAC-SHA256) | PROJECT.md decision; `cryptography==3.3.2` |
| Seed key source | `os.getenv()`, injected Puppet → `port.cfg` → `environment-vars` | PROJECT.md; mirrors `SSO_APPS_CLIENT_SECRET` |

**Why N=5 / 15 min is the right pair.** With `{T, T−1}` accepted, each guess has probability
2×10⁻⁶. Five attempts per 15 minutes = 480 attempts/day → expected time to a hit ≈ 1042 days.
Unthrottled at one attempt per second the 10⁶ space falls in days. NIST §5.2.2's 100-per-account is
a **ceiling on what is permissible**, not a target: with a *second* factor there is no legitimate
reason a user needs 100 tries, and RFC 4226 §7.3 says set the throttle "as low as possible" without
hurting usability. Five gives a user two fat-fingers plus a stale-code retry.

**Hard lock vs exponential backoff.** RFC 4226 §7.3 blesses both. Build the **fixed 15-minute
lock**: it is two memberdata fields and one comparison, and the user-facing message is a single
sentence with a concrete number ("try again in 12 minutes"). Exponential backoff (django-otp) needs
the same two fields plus a per-attempt recompute and a message that changes every attempt, for no
security gain at this threshold. Not worth it for a 2-year package.

**What unlocks it: time, not an admin.** See anti-features — admin-unlock-only is both a helpdesk
generator and a denial-of-service primitive.

### Differentiators (nice; mostly not worth it for a 2-year package)

| Feature | Value Proposition | Complexity | Verdict |
|---|---|---|---|
| **Email notification on lockout** | ASVS 2.2.3; the user learns someone is attacking them | LOW | **Worth it.** The MailHost path already exists for bar-code reset. One mail, on lock only — never per failed attempt (see anti-features). |
| **Email notification on recovery-code use** | ASVS 2.2.3; recovery-code use is the highest-signal event in the system | LOW | **Worth it**, same reason and same code path as above. |
| **Bump seed to 160 bits** (`base64.b32encode(os.urandom(20))` → 32 chars) | Current `b32encode(str(uuid4()))` is ~122 bits, marginally under RFC 4226 §4 R6's 128-bit MUST, in a needlessly long 58-char secret | LOW | **Worth it** — one line, and free because nothing is deployed and F4a is rewriting the enrollment write anyway. |
| Progressive backoff per failure (django-otp style) | Slightly better UX for a fumbling legitimate user | MEDIUM | Skip. The fixed lock covers the threat. |
| CAPTCHA as a lockout softener (NIST §5.2.2 suggests it) | Fewer lockouts of real users | HIGH | Skip. New external dependency, accessibility cost, and pointless once the lock is 15 minutes. |
| 8-digit OTP | 100× brute-force space | MEDIUM | Skip. Needs a non-default `digits=8` in the `otpauth://` URI, not all authenticator apps honour it, and the lockout already dominates the math. |
| Per-code "used at" audit trail | Forensics | MEDIUM | Skip. A log line at consumption is enough. |
| Fernet key rotation (`MultiFernet`) | Key compromise recovery | LOW | Defer. Note as `ponytail:` in the code — single-key Fernet now, `MultiFernet` is a one-line upgrade if a rotation is ever needed. |
| Force seed re-enrollment after a recovery code is consumed | Slightly tighter posture | MEDIUM | Skip. Neither GitHub nor Keycloak does this. It turns "I lost my phone" into a two-step ordeal. |

### Anti-Features (deliberately NOT to build)

| Feature | Why Requested | Why Problematic | Alternative |
|---|---|---|---|
| **"Remember this device / trust this browser for 30 days"** | The single loudest MFA feature request | A second signed cookie, a second secret, a revocation UI, and it reduces effective MFA coverage to near zero for exactly the users who click it. Also collides with the existing `ska`/browser-hash machinery | Nothing. The IP whitelist already covers the "trusted network" case that motivates this |
| **Admin-unlock-only lockout** ("lock until an administrator clears it") | Feels stricter | Two failures: a helpdesk queue for every fat-fingered code, and a DoS primitive — anyone who knows a username can permanently lock that account with 5 requests | 15-minute self-expiring lock (F2b) |
| **Per-process / in-RAM attempt counters or a `plone.memoize` cache** | "Avoid a ZODB write on every failed login" | An attacker rotates ZEO clients and multiplies allowed attempts by the client count. Already forbidden by PROJECT.md; restated because it is the obvious "optimisation" someone will propose during implementation | Memberdata properties (F6). A write on a failed second factor is not a hot path |
| **Auto-regenerating recovery codes when the last one is used** | "Don't lock users out" | Converts single-use into effectively infinite-use and destroys the signal that something is wrong | Warn at ≤3 remaining (F3e); explicit user-initiated regeneration (F3d) |
| **Re-displaying recovery codes after enrollment** ("let me see them again") | Users lose the printout | Requires reversible storage, which defeats hashing entirely and re-creates the plaintext-seed problem this milestone exists to fix | Regenerate the set (F3d) |
| **Emailing recovery codes to the user** | Convenient delivery | Puts the second factor in the same channel as the password-reset path — the two factors collapse into one. Also leaves them in a mailbox forever | Display once at enrollment, user prints or stores them |
| **Notifying the user on every failed attempt** (maximal reading of ASVS 2.2.3) | Vigilance | A brute-force attempt becomes a mail flood — an amplification DoS against the user and the MailHost | Notify on **lock** and on **recovery-code use** only |
| **Trying to make HTTP Basic Auth work with the second factor** (challenge header, out-of-band code, `password+code` concatenation) | "Don't break our scripts" | There is no interactive channel; every scheme invented here is a bespoke protocol nobody else implements. The whole documented industry answer (M365 legacy auth) is *block the protocol for MFA-enrolled principals* | Deny (F5a) + document the service-account/whitelist workaround (F5b) |
| **Deriving the seed encryption key from the user's password** | "Then even the sysadmin can't read it" | You can no longer validate a token without the password in hand, and every password change requires re-encryption. Structurally incompatible with a PAS challenge flow | Single site-wide Fernet key from `os.getenv()` (F4a) |
| **A "TOTP or plaintext" fallback when the encryption key is missing** | "Don't break the site if Puppet hasn't run" | Silently and permanently undoes F4a, and the failure is invisible | Fail closed and log loudly (F4b). A site with 2FA and no key is misconfigured, not degraded |
| **Adaptive/risk-based MFA, geo-IP, "unusual location" scoring** | Modern-sounding | Months of work, needs a data source, and is precisely what Keycloak provides for free in 1–2 years | Nothing |
| **Swapping `onetimepass` → `pyotp` "while we're in here"** | The pinned lib is from 2013 | Already out of scope in PROJECT.md, and unnecessary: `onetimepass.get_hotp()` already exposes the counter-level primitive F1a needs (local fact 2) | Build F1a on `get_hotp` |
| **Distinguishing "wrong password" from "wrong token" in responses** | Better error messages | Confirms a valid password to an attacker who only has a credential-stuffing list | One generic failure message; detail goes to the log |

---

## Feature Dependencies

```
F1a. counter-returning validate_token()   <- the keystone; nothing else works without it
    ├──enables──> F1b. drift tolerance {T, T-1}
    ├──enables──> F1c. replay rejection (needs the MATCHED counter, not a bool)
    │                 └──requires──> F6. memberdata storage (last_used_totp_counter)
    └──enables──> F1d. replay logging

F2a. failed-attempt counter
    └──requires──> F6. memberdata storage (totp_failed_attempts, totp_locked_until)
        └──enables──> F2b. 15-min lock at N=5
                          └──required-by──> F3a. recovery codes (F2c: shared counter)

F3a. recovery codes (hashed, in memberdata)
    ├──requires──> F2b. lockout   (else recovery codes are the unthrottled path)
    ├──requires──> F6. memberdata storage
    ├──enables──> F3b. consume on use
    ├──enables──> F3c. show once at enrollment
    ├──enables──> F3d. regenerate whole set
    └──enables──> F3e. remaining-count warning

F4a. Fernet-encrypted seed
    ├──requires──> F4b. fail closed on missing key   (same commit, not a follow-up)
    ├──requires──> env-var key injection (industrialisation repo — OUTSIDE this roadmap)
    ├──touches──> get_secret() / get_or_create_secret(), which F1a calls
    └──pointless-without──> local QR generation (seed must stop going to chart.googleapis.com)

F5a. close the basic-auth bypass   <- INDEPENDENT of F1-F4, and gates their value

F6. memberdata property storage   <- shared substrate for F1c, F2a, F2b, F3a
```

### Dependency Notes

- **F1c (replay) requires F1a, not just a flag.** This is the crux. `valid_totp` returns a bare
  boolean, so there is nothing to compare against a stored counter. And the moment you accept *any*
  drift (F1b), "the current counter" is no longer the counter that was accepted — you must persist
  the counter that actually **matched**. Replay detection and drift tolerance are therefore the same
  six lines of code and belong in the same commit. Splitting them produces a window where drift is
  accepted but replay is not detected — a strictly worse state than today.
- **F1c, F2a/F2b and F3a all write to the same memberdata record.** Plan them as one storage change:
  one round of memberdata property registration in the GenericSetup profile, one
  `setMemberProperties` mapping per request. Three separate phases would mean three profile edits
  and up to three writes per authentication.
- **F2b must be checked *before* the token is evaluated**, not after — otherwise a locked account is
  still an oracle (django-otp models this as an explicit `verify_is_allowed()` pre-check).
- **F3a requires F2b (F2c).** An 80-bit recovery code is not guessable, so this is belt-and-braces
  rather than load-bearing — but the counter must be shared so that mixing TOTP and recovery-code
  guesses cannot double the allowance.
- **F4a touches `get_secret()`, which F1a calls.** Low conflict (encryption changes *where the seed
  comes from*, F1a changes *what is done with it*) but they are adjacent lines. Sequence them, do
  not parallelise them into two agents editing `helpers.py`.
- **F4a is worthless without local QR generation.** PROJECT.md already states this: encrypting the
  seed at rest while still shipping it in a URL to `chart.googleapis.com` protects nothing. Same
  phase.
- **F4a has an out-of-repo prerequisite:** the `concat::fragment` in the `industrialisation` repo.
  Code can land and be tested first (tests set the env var themselves), but the feature is not
  *deployable* until that change ships. Already flagged in PROJECT.md Constraints; repeated here
  because it is the one dependency a roadmap can silently drop.
- **F5a conflicts with nothing but gates everything.** Replay rejection, lockout and encryption are
  all defences on the challenge path. If a parallel path skips the challenge entirely, hardening the
  challenge path is theatre. Order F5a early.
- **F5a's deny mechanism is credential-wiping, not `return None`** (local fact 7). If this is
  implemented as `return None` alone, PAS will simply ask the next `IAuthenticationPlugin` and the
  bypass remains — with a test that appears to pass. Flag this for deeper review at plan time.

---

## MVP Definition

All five milestone items ship. The question is ordering, and the sequencing that falls out of the
dependency graph is:

### Launch With (this milestone)

- [ ] **F5a + F5b — close the basic-auth bypass** — do first; every later defence is on the
      challenge path and is moot while a parallel path skips it. Also self-contained.
- [ ] **F6 + F1a + F1b + F1c + F1d + F2a + F2b + F2c** — one phase. The memberdata schema, the
      counter-returning validator, drift, replay and lockout are one coherent change to
      `helpers.validate_token()` plus four properties. Splitting them creates intermediate states
      that are less safe than the current one.
- [ ] **F3a–F3e — recovery codes** — after lockout exists (F2c), and after F1a so the token form has
      one dispatch point.
- [ ] **F4a + F4b + local QR + 160-bit seed** — encryption, fail-closed, `zint`, and the seed-length
      bump, together. All four touch the enrollment/`get_secret` path exactly once.

### Add After Validation (v1.x)

- [ ] **Email on lockout / on recovery-code use** — ASVS 2.2.3, one MailHost call each, reusing the
      existing bar-code-reset mail path. Add once the core is verified and the mail template pattern
      is settled.

### Future Consideration (never, for this package)

- [ ] Everything in the anti-feature table.
- [ ] Fernet key rotation (`MultiFernet`) — leave a `ponytail:` comment naming the upgrade path.
- [ ] Progressive backoff, CAPTCHA, 8-digit OTP, adaptive MFA — Keycloak's problem in 1–2 years.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---|---|---|---|
| F5a. Deny basic-auth for enrolled users | HIGH (closes total bypass) | LOW | **P1** |
| F1a. Counter-returning validation | HIGH (keystone) | LOW | **P1** |
| F1c. Replay rejection | HIGH (RFC MUST NOT) | LOW | **P1** |
| F2b. Lockout, N=5 / 900 s | HIGH (NIST SHALL) | LOW | **P1** |
| F4a+F4b. Encrypted seed, fail closed | HIGH (raison d'être of the fork) | MEDIUM | **P1** |
| Local QR generation | HIGH (F4a is void without it) | LOW | **P1** |
| F3a–F3d. Recovery codes | HIGH (only self-service recovery) | MEDIUM | **P1** |
| F1b. Drift `{T, T−1}` | MEDIUM (removes a real usability cliff) | LOW | **P1** (free with F1a) |
| F1d. Replay logging | MEDIUM (ASVS 2.8.5) | LOW | **P1** (one line) |
| F5b. Document the basic-auth consequence | MEDIUM (avoids a production surprise) | LOW | **P1** |
| F3e. Remaining-count warning | MEDIUM | LOW | **P2** |
| 160-bit seed | LOW (fixes a marginal RFC 4226 §4 R6 miss) | LOW | **P2** |
| Email on lockout / recovery-code use | LOW–MEDIUM | LOW | **P2** |
| Progressive backoff, CAPTCHA, 8 digits, key rotation | LOW | MEDIUM–HIGH | **P3** |

---

## Competitor Feature Analysis

| Feature | Keycloak (the successor) | django-otp / django-two-factor-auth | Our Approach |
|---|---|---|---|
| Drift window | `lookAheadWindow` default 1 | `tolerance` default 1 (previous tokens) | `{T, T−1}` — 1 backward step, per RFC 6238 §5.2 |
| Replay rejection | Enforced per credential | Stores last-used `t` on the device | Store `last_used_totp_counter`, require strictly greater |
| Lockout threshold | `failureFactor` 30 | none by default; exponential per-device backoff | **N = 5** (much lower — this is a second factor, not a password) |
| Lock duration | `waitIncrementSeconds` scaled, `maxFailureWaitSeconds` 900 | `1·2^(n-1)` s | Fixed **900 s**, auto-expiring |
| Unlock | Time; admin can also clear | Time | Time only. No admin-unlock (anti-feature) |
| Recovery codes | 12, consumed sequentially | Static-token plugin, no fixed count | **10**, any order, 16 base32 chars, salted SHA-256 |
| Recovery-code redisplay | No | No | No |
| Seed at rest | DB, optionally with a vault-backed key | DB, plaintext by default | Fernet, key from `os.getenv()`, fail closed |
| Non-interactive auth paths | Blocked for MFA-enrolled principals | n/a | Deny basic auth for enrolled users |

---

## Sources

**Primary standards** (verbatim quotes, MEDIUM confidence — fetched from the publishers and
cross-corroborated by independent search results):

- RFC 6238, *TOTP: Time-Based One-Time Password Algorithm* — §5.2, §6 — https://www.rfc-editor.org/rfc/rfc6238.txt
- RFC 4226, *HOTP: An HMAC-Based One-Time Password Algorithm* — §4 R6, §7.3, §7.4 — https://www.rfc-editor.org/rfc/rfc4226.txt
- NIST SP 800-63B, *Digital Identity Guidelines: Authentication and Lifecycle Management* — §5.1.2.2, §5.2.2 — https://pages.nist.gov/800-63-3/sp800-63b.html and https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63B-4.pdf
- OWASP ASVS 4.0, V2 Authentication — 2.2.1, 2.2.3, 2.6.1–2.6.3, 2.8.1–2.8.5 — https://github.com/OWASP/ASVS/blob/master/4.0/en/0x11-V2-Authentication.md
- OWASP Multifactor Authentication Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html
- OWASP WSTG 4.11, *Testing Multi-Factor Authentication* — https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/04-Authentication_Testing/11-Testing_Multi-Factor_Authentication

**Real vulnerabilities in this exact bug class** (MEDIUM confidence):

- Vikunja GHSA-p747-qc5p-773r, *TOTP Reuse During Validity Window*, CVSS 5.7 — https://github.com/go-vikunja/vikunja/security/advisories/GHSA-p747-qc5p-773r
- SBA Research SBA-ADV-20240617-01, *Craft CMS TOTP Valid After Use* — https://github.com/sbaresearch/advisories/tree/public/2024/SBA-ADV-20240617-01_CraftCMS_TOTP_Valid_After_Use
- SBA Research SBA-ADV-20240202-02, *Craft CMS Two-Factor Plugin TOTP Valid After Use* — https://github.com/sbaresearch/advisories/tree/public/2024/SBA-ADV-20240202-02_CraftCMS_Plugin_Two-Factor_Authentication_TOTP_Valid_After_Use

**Implementation defaults** (MEDIUM where corroborated by two sources, LOW where single-source):

- Keycloak OTP policy `lookAheadWindow` — https://www.keycloak.org/docs-api/latest/javadocs/org/keycloak/models/OTPPolicy.html and https://wjw465150.gitbooks.io/keycloak-documentation/content/server_admin/topics/authentication/otp-policies.html
- Keycloak brute-force detection defaults — https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/24.0/html/server_administration_guide/mitigating_security_threats and https://phasetwo.io/docs/security/brute-force-detection/
- Keycloak Recovery Authentication Codes (12 codes) — https://www.keycloak.org/2025/10/recovery-codes
- django-otp throttling and TOTP tolerance — https://django-otp-official.readthedocs.io/en/stable/overview.html and https://django-otp-official.readthedocs.io/en/stable/_modules/django_otp/plugins/otp_totp/models.html
- GitHub 2FA recovery codes (16 × 10 chars) — https://docs.github.com/en/authentication/securing-your-account-with-two-factor-authentication-2fa/configuring-two-factor-authentication-recovery-methods
- Google backup codes (10 × 8 digits) — https://support.google.com/accounts/answer/1187538
- GitLab recovery codes (10 × 16 hex) — https://docs.gitlab.com/user/profile/account/two_factor_authentication/
- 6-digit OTP brute-force feasibility without throttling — https://lukeplant.me.uk/blog/posts/6-digit-otp-for-two-factor-auth-is-brute-forceable-in-3-days/
- Legacy/basic-auth MFA bypass class (BAV2ROPC, M365) — https://redcanary.com/blog/threat-detection/bav2ropc/ and https://www.kroll.com/en/publications/cyber/securing-microsoft-365-avoiding-multi-factor-authentication-bypass-vulnerabilities

**Local codebase** (HIGH confidence — read directly):

- `/srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py` — `valid_totp`, `get_totp`, `get_hotp`, `_is_possible_token`
- `/srv/src/imio.googleauthenticator/src/collective/googleauthenticator/helpers.py` — `generate_secret` (l.93), `get_secret` (l.125), `get_or_create_secret` (l.144), `get_barcode_image` (l.107), `validate_token` (l.191)
- `/srv/src/imio.googleauthenticator/src/collective/googleauthenticator/pas_plugin.py` — `authenticateCredentials` (l.66), credential wipe (l.127-133), extractor check (l.157)
- `/srv/src/imio.googleauthenticator/.planning/PROJECT.md`, `/srv/src/imio.googleauthenticator/.planning/codebase/CONCERNS.md`

---
*Feature research for: TOTP second-factor hardening, imio.googleauthenticator*
*Researched: 2026-07-28*
