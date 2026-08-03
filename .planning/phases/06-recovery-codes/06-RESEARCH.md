# Phase 6: Recovery Codes - Research

**Researched:** 2026-08-03
**Domain:** Single-use recovery codes as an alternate second factor, sharing Phase 5's lockout counter (Plone 4.3 / Python 2.7.18, PAS plugin architecture)
**Confidence:** HIGH

## Summary

No CONTEXT.md exists for this phase — the user chose to plan without a discuss-phase pass, so
there is no `## User Constraints` section below. The design decisions that would normally live in
CONTEXT.md instead live in ROADMAP.md's Phase 6 section and PROJECT.md's Key Decisions table, and
are quoted verbatim at point of use throughout this document.

This phase adds ten single-use recovery codes as an alternate second factor, hashed with one
per-user salt (already decided in PROJECT.md), consumed on use, regenerable as a full set, and
throttled through the exact counter Phase 5 built (`register_failed_second_factor` /
`is_account_locked` / `reset_failed_second_factor` in `helpers.py`, currently written only from
`browser/forms/token.py` and `browser/forms/reset_bar_code.py`). Every primitive this phase needs
is already available with **zero new dependencies**: `hashlib.pbkdf2_hmac` and
`hmac.compare_digest` are both present and working on this buildout's actual Python 2.7.18
interpreter (verified this session, not assumed), and `base64.b32encode` — already used by
`generate_secret` for the TOTP seed — turns `os.urandom(10)` into exactly 16 base32 characters
with no padding, matching the roadmap's stated shape exactly. `rebus`, which CLAUDE.md's stale
"Key Dependencies" list names as the base32 encoder, is **not actually an installed dependency**
(absent from `setup.py`'s `install_requires`, and `ImportError: No module named rebus` on the
buildout's own interpreter) — a documented correction, not a design choice to relitigate.

The riskiest part of this phase is not cryptographic, it is architectural: the single dispatch
point Phase 5 built in `browser/forms/token.py` must grow a second candidate shape (16-char base32
recovery code) alongside the existing one (exact 6-digit TOTP) **without** touching
`helpers.validate_token`'s existing contract, which nine already-shipped Phase 5 requirements'
tests depend on verbatim. The recommended design adds one new dispatcher function,
`validate_token_or_recovery_code`, used only at that one call site, and a new
`validate_recovery_code` function that performs the hash lookup and the same commit-time state
write pattern `validate_token` already established (write inside the helper, reached only from a
view that returns 200/302 and therefore commits — never from `pas_plugin.py` or a challenge
plugin, per the standing MFA-12 invariant PROJECT.md restates as a hard constraint for this
package's remaining life).

The one-time-display requirement (RECOV-03) has a concrete, already-verified answer rather than a
speculative one: this session read the pinned `plone.z3cform==0.8.1` egg's `FormWrapper.update()`
directly. It skips re-rendering the wrapped form only when the response status is 302/303 (a
redirect). The existing `handleSubmit` pattern in this codebase always redirects on success; this
phase's enrollment success path must be the one exception — generate and store the hashes, then
render the ten plaintext codes **in the same response**, by overriding `SetupForm.render()` to
check an instance flag set inside `handleSubmit`, instead of redirecting. Nothing new is stored
anywhere to make this work: if the user navigates away before the response renders, the codes are
gone, which is precisely what RECOV-03's "never redisplayed" and the roadmap's own out-of-scope
line ("redisplaying codes") require.

**Primary recommendation:** Two new `memberdata_properties.xml` entries
(`two_factor_authentication_recovery_codes_salt` as `string`,
`two_factor_authentication_recovery_codes_hashes` as `lines`), one new helper-module section in
`helpers.py` (generate / hash / validate-and-consume, stdlib `hashlib.pbkdf2_hmac` at 100,000
iterations, SHA-256), one new dispatcher wired into `token.py`'s existing single call site, and a
same-response `render()` override in `user_setup.py` for the one-time display. No new install,
no new dependency, no new browser view, no viewlet, no session/temp-storage mechanism.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECOV-01 | Enrollment issues 10 single-use codes of 80 bits each (`os.urandom(10)` → 16 base32 chars), displayed exactly once, never redisplayed | `base64.b32encode(os.urandom(10))` verified this session to produce exactly 16 chars with no `=` padding (80 bits is an exact multiple of base32's 5-bit block, same precision argument `test_seed_encryption_round_trip` already makes for the 20-byte seed); one-time display via `render()` override, verified against the pinned `plone.z3cform` egg's redirect-skip logic |
| RECOV-02 | Codes stored hashed with one salt per user; plaintext never stored | `hashlib.pbkdf2_hmac('sha256', code, salt, 100000)` (stdlib, verified present and timed on this buildout's Python 2.7.18); salt via `os.urandom(16)`; per-user (not per-code) salt is a locked PROJECT.md decision, re-confirmed against OWASP ASVS's own storage rule for lookup secrets |
| RECOV-03 | Codes displayed exactly once, never redisplayed | Same-response `render()` override (verified pattern, see Architecture Patterns); nothing is stored that could be redisplayed later, which is the actual mechanism that makes "never" true |
| RECOV-04 | Recovery code accepted in place of TOTP token, consumed on use | New `validate_token_or_recovery_code` dispatcher at the one existing call site in `token.py`; consumption = removing the matched hash from the stored `lines` property in the same call, mirroring `validate_token`'s existing replay-write pattern |
| RECOV-05 | Recovery-code failure increments the same counter as TOTP failure | The dispatcher returns a plain `bool`; `token.py`'s existing `register_failed_second_factor`/`reset_failed_second_factor` call sites are untouched, so both code paths already funnel through the one counter with zero new wiring — verified by reading `token.py:113-142` directly |
| RECOV-06 | Regenerating the whole set invalidates all previous codes | `generate_recovery_codes` overwrites both the salt and the hash list in one `setMemberProperties` call; every previously issued code's hash cannot match under the new salt even if the random value coincidentally repeats |
| RECOV-07 | User warned when ≤3 codes remain | `IStatusMessage` added inline at the moment a recovery code is consumed and the remaining count drops to ≤3 — reuses the exact mechanism `drop_login_failed_msg`/the "Welcome!" message already use in this codebase; no new viewlet or schema field |
</phase_requirements>

## Architectural Responsibility Map

This package is a single-tier Zope/Plone monolith (PAS plugin + z3c.form views + ZODB
memberdata) — there is no separate frontend/API/CDN split to misassign work across. The map below
identifies which layer *within* that monolith owns each capability, since that has been the
recurring source of misplaced writes in this project (MFA-12's whole reason for existing).

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Recovery-code generation (10 codes, salt) | Backend/API (browser form view, on successful enrollment) | Database/Storage (ZODB memberdata write) | Generation is a one-shot, authenticated, server-side action — no client-side involvement, no PAS-plugin involvement |
| Recovery-code hashing & storage | Database/Storage (ZODB `OOBTree`-backed memberdata via `MutablePropertySheet`) | — | Same storage substrate Phase 5's counters already use; consistent across ZEO clients by construction |
| Recovery-code validation & consumption | Backend/API (`helpers.py`, called only from the token form view) | — | Must be a view that commits (200/302), never the PAS plugin or a challenge plugin — MFA-12's invariant extends unchanged to this new state |
| One-time display of plaintext codes | Frontend Server/SSR (server-rendered z3c.form template, same request/response as generation) | — | No client-side JS is introduced; the "session-free" design already used for the login-step signed URL does not apply here (this is an authenticated, non-2FA-step request), so a same-response render is simpler and sufficient |
| "≤3 remain" warning | Frontend Server/SSR (`IStatusMessage` queued during the authenticated recovery-code login) | — | Surfaced only to the user who just authenticated, never to an unauthenticated caller — avoids a new pre-auth information-disclosure oracle |
| Throttling of failed recovery-code attempts | Backend/API (`helpers.register_failed_second_factor`, already built) | Database/Storage (the same `two_factor_authentication_failed_attempts`/`_locked_until` properties) | Reuse, not a new mechanism — this is the entire point of RECOV-05 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `hashlib` (stdlib) | Python 2.7.18's bundled version | `pbkdf2_hmac('sha256', ...)` for recovery-code hashing | `hashlib.pbkdf2_hmac` has been in CPython since 2.7.8; **verified present and functional** on this buildout's actual interpreter this session (`bin/python`, confirmed via `bin/test`'s own egg path) — no new dependency for a KDF the stdlib already provides |
| `hmac` (stdlib) | Python 2.7.18's bundled version | `compare_digest` for constant-time hash comparison | Already imported and used in `helpers.py` today (`validate_bar_code_reset_token`); this phase reuses the same import, not a new one |
| `base64` (stdlib) | Python 2.7.18's bundled version | `b32encode(os.urandom(10))` for the 16-char recovery code | Already imported and used in `helpers.py` today (`generate_secret`); same function, different byte count |
| `os` (stdlib) | Python 2.7.18's bundled version | `os.urandom` for both the code bytes and the per-user salt | Already the CSPRNG source this codebase uses everywhere (`generate_secret`, `SEC-06`) |
| `binascii` (stdlib) | Python 2.7.18's bundled version | `hexlify`/`unhexlify` for storing the salt and hash digests as plain-ASCII strings in a `string`/`lines` memberdata property | Avoids raw bytes in a property sheet that GenericSetup/ZODB expect as `str`/`unicode` |

**No new packages are required by this phase.** `cryptography==3.3.2` (already pinned) *does*
ship a PBKDF2 KDF class (`cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC` — confirmed
importable from the pinned egg this session), but it needs a `hashes.SHA256()` object and a
`default_backend()` for the same output stdlib `hashlib.pbkdf2_hmac` produces in one call. Ladder
rung 3 (stdlib) beats rung 5 (already-installed dependency) here — use stdlib.

### Supporting

None. Every capability this phase needs is stdlib, already imported in this codebase, or already
built in Phase 5.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `hashlib.pbkdf2_hmac` | `cryptography.hazmat.primitives.kdf.pbkdf2.PBKDF2HMAC` | Same output, more ceremony (needs a `hashes` object and a backend); no reason to prefer it since the dependency is already present but the API is not simpler |
| PBKDF2-HMAC-SHA256 | Argon2id (OWASP's current top recommendation for *new* systems, see Sources) | Would require a new C-extension dependency (`argon2-cffi` or similar) whose Python 2.7 support and PEP 517 status are unverified and would need separate vetting — disproportionate for hashing 80-bit CSPRNG-random codes that have no dictionary to walk (unlike user-chosen passwords, which is the threat Argon2/OWASP's 600k-iteration PBKDF2 figure actually defends against). `[ASSUMED]` re: argon2-cffi's current Python 2 support status — not verified this session, but irrelevant to the recommendation either way given the "nothing may require PEP 517" constraint |
| One salt per user | One salt per code | Rejected in PROJECT.md already: a per-code salt forces N PBKDF2 runs per login attempt (10 × ~0.117s ≈ 1.17s on this hardware, measured this session) — a DoS lever on a login-adjacent endpoint. A per-user salt costs exactly one PBKDF2 run per attempt (the submitted code is hashed once, then compared via `hmac.compare_digest` against each of the ≤10 stored digests — cheap) |

**Installation:** None. No `install_requires` change, no buildout re-run needed for this phase.

**Version verification:** `hashlib.pbkdf2_hmac` and `hmac.compare_digest` availability confirmed
this session by direct execution on the buildout's own interpreter (`bin/python`, with
`bin/test`'s pinned egg paths injected for the `cryptography` cross-check):

```
python2.7 (2.7.18) -- hashlib.pbkdf2_hmac: True, hmac.compare_digest: True
```

PBKDF2-HMAC-SHA256 timing on this exact interpreter (measured this session, single call, no
warm-up):

| Iterations | Wall time |
|---|---|
| 20,000 | 0.022s |
| 50,000 | 0.054s |
| 100,000 | 0.117s |
| 200,000 | 0.229s |

This matches the roadmap's own carried-forward figure ("100k ≈ 0.113s ... scales linearly on a
slower host") to within measurement noise — the roadmap's number was not a guess.

## Package Legitimacy Audit

**Not applicable — no external packages are installed by this phase.** Every primitive used
(`hashlib`, `hmac`, `base64`, `os`, `binascii`) is part of the Python 2.7.18 standard library
already present in this buildout. `rebus`, mentioned in this phase's research brief and in
`.claude/CLAUDE.md`'s "Key Dependencies" list as the base32 encoder, is confirmed **not** an
actual dependency of this codebase (absent from `setup.py install_requires`; `ImportError: No
module named rebus` on `bin/python`) — that documentation predates the migration to stdlib
`base64.b32encode` in Phase 3's `generate_secret` and is stale. No package legitimacy check
(`npm view` / `pip index versions` / registry scan) applies since nothing new is being added.

## Architecture Patterns

### System Architecture Diagram

```
Authenticated user (already logged in, editing their own profile)
        |
        v
  @@setup-two-factor-authentication (SetupForm.handleSubmit)
        |  TOTP token verified (existing flow, unchanged)
        v
  enable_two_factor_authentication = True   (existing write, unchanged)
        |
        v
  generate_recovery_codes(user)  --------------------> memberdata (ZODB)
        |  returns 10 plaintext codes (in-memory only)      two_factor_authentication_recovery_codes_salt
        v                                                    two_factor_authentication_recovery_codes_hashes
  SetupForm.render() override
  (no redirect issued -- FormWrapper.update() only skips
   re-rendering on a 302/303 status, verified against the
   pinned plone.z3cform egg)
        |
        v
  Same HTTP response renders the 10 codes ONCE.
  Nothing further references the plaintext; it is not
  captured in a closure, session, or second request.


Anonymous login (existing 2FA challenge flow, unchanged up to the token field)
        |
        v
  @@google-authenticator-token (TokenForm.handleSubmit)
        |
        v
  is_account_locked(user)?  --yes--> refuse (existing gate, unchanged)
        | no
        v
  validate_token_or_recovery_code(token, user)   <-- NEW single dispatch point
        |
        +-- exactly 6 ASCII digits --> validate_token(token, user)          (existing, unchanged)
        |                                    |
        |                                    +-- writes two_factor_authentication_last_interval
        |
        +-- 16-char base32 shape ----> validate_recovery_code(token, user)  (NEW)
        |                                    |
        |                                    +-- pbkdf2_hmac(code, stored salt) == a stored hash?
        |                                    +-- on match: remove that hash from the stored list
        |                                    +-- if remaining <= 3: queue an IStatusMessage warning
        |
        +-- matches neither -----------> False
        |
        v
  True  --> reset_failed_second_factor(user); log the user in   (existing, unchanged)
  False --> register_failed_second_factor(user); show generic error  (existing, unchanged)
```

### Recommended Project Structure

No new files. Every change lands in existing modules:

```
src/imio/googleauthenticator/
├── helpers.py                       # + generate_recovery_codes, validate_recovery_code,
│                                     #   validate_token_or_recovery_code, _hash_recovery_code,
│                                     #   _is_recovery_code_shape, _normalize_recovery_code_input
├── browser/forms/
│   ├── token.py                     # swap validate_token(...) -> validate_token_or_recovery_code(...)
│   │                                 #   at the one call site (line ~113); no other change
│   └── user_setup.py                # call generate_recovery_codes after the existing
│                                     #   enable_two_factor_authentication=True write;
│                                     #   override render() for the one-time display
├── profiles/default/
│   └── memberdata_properties.xml    # + two new <property> entries (string, lines)
└── tests/
    ├── test_helpers.py               # + generation/hash/consume/regenerate unit tests
    ├── test_token.py                 # + recovery-code-as-token integration tests (mirrors
    │                                 #   TestTokenFormLockout's existing Browser pattern)
    ├── test_user_setup.py            # + one-time-display / never-redisplayed test
    └── test_pas_plugin.py            # extend the existing MFA-12 source-grep guard
                                       #   (test_no_second_factor_state_written_from_the_plugin)
                                       #   with the two new property names and three new
                                       #   helper function names
```

### Pattern 1: Same-response one-time render (no redirect, no session storage)

**What:** After a successful action, render a different template *in the same response* instead
of redirecting, by setting an instance flag in the button handler and checking it in an
overridden `render()`.

**When to use:** Exactly once in this phase — the recovery-codes-issued page. Do not generalize
this into a reusable base class; there is exactly one call site.

**Example (verified mechanism, illustrative code):**

```python
# Source: this session's direct read of the pinned egg
# /srv/cache/eggs/plone.z3cform-0.8.1-py2.7-linux-x86_64.egg/plone/z3cform/layout.py
#
# FormWrapper.update() (verbatim, lines 39-60):
#     z2.switch_on(self, request_layer=self.request_layer)
#     self.form_instance.update()
#     # If a form action redirected, don't render the wrapped form
#     if self.request.response.getStatus() in (302, 303):
#         self.contents = ""
#         return
#     self.contents = self.form_instance.render()
#
# Consequence: skipping self.request.response.redirect(...) in handleSubmit is
# sufficient and safe -- render() runs normally afterward in the same response.

class SetupForm(form.SchemaForm):
    _recovery_codes = None  # plaintext, in-memory only, never assigned to anything persistent

    @button.buttonAndHandler(_('Verify'))
    def handleSubmit(self, action):
        ...
        if valid_token:
            user = api.user.get_current()
            user.setMemberProperties(mapping={'enable_two_factor_authentication': True})
            self._recovery_codes = generate_recovery_codes(user)  # writes hashes+salt only
            # Deliberately no self.request.response.redirect(...) here.
            return
        ...

    def render(self):
        if self._recovery_codes:
            return RECOVERY_CODES_TEMPLATE(self, self.request)(codes=self._recovery_codes)
        return super(SetupForm, self).render()
```

### Pattern 2: Widen the dispatch point without touching the existing function

**What:** `helpers.validate_token` keeps its exact current signature, behavior, and test
coverage (nine Phase 5 requirements depend on it verbatim). A new function
`validate_token_or_recovery_code` is the only thing `token.py` calls, and it delegates.

**When to use:** Any time an existing, already-tested dispatch function needs a second candidate
shape. Do not add `if`/`elif` branches inside `validate_token` itself.

**Example (illustrative):**

```python
# helpers.py

RECOVERY_CODE_LENGTH = 16
RECOVERY_CODE_ALPHABET = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')  # RFC 4648 base32
RECOVERY_CODE_PBKDF2_ITERATIONS = 100000


def _normalize_recovery_code_input(token):
    """Strips whitespace and the display-only grouping dashes, uppercases.
    The stored hash is always computed over this canonical form -- both at
    generation time and at verification time -- never over the dashed
    display string.
    """
    token = token if isinstance(token, basestring) else str(token)
    return token.replace('-', '').replace(' ', '').upper()


def _is_recovery_code_shape(token):
    return len(token) == RECOVERY_CODE_LENGTH and all(
        c in RECOVERY_CODE_ALPHABET for c in token)


def _hash_recovery_code(code, salt):
    """code and salt are both plain ASCII str at this point."""
    digest = hashlib.pbkdf2_hmac(
        'sha256', code, salt, RECOVERY_CODE_PBKDF2_ITERATIONS)
    return binascii.hexlify(digest)


def generate_recovery_codes(user):
    """Generates 10 fresh codes, overwrites the salt AND the hash list in
    one write (so regeneration invalidates every previous code even if a
    random value coincidentally repeats), and returns the PLAINTEXT codes
    for exactly-once display. Nothing plaintext is persisted.
    """
    salt = binascii.hexlify(os.urandom(16))
    plaintext_codes = [
        base64.b32encode(os.urandom(10)) for _ in range(10)]
    hashes = [_hash_recovery_code(code, salt) for code in plaintext_codes]
    user.setMemberProperties(mapping={
        'two_factor_authentication_recovery_codes_salt': salt,
        'two_factor_authentication_recovery_codes_hashes': tuple(hashes),
    })
    return plaintext_codes


def validate_recovery_code(token, user=None):
    if user is None:
        user = api.user.get_current()
    token = _normalize_recovery_code_input(token)
    if not _is_recovery_code_shape(token):
        return False

    salt = user.getProperty(
        'two_factor_authentication_recovery_codes_salt') or ''
    stored_hashes = user.getProperty(
        'two_factor_authentication_recovery_codes_hashes') or ()
    if not salt or not stored_hashes:
        return False

    candidate = _hash_recovery_code(token, salt)
    for stored_hash in stored_hashes:
        if compare_digest(candidate, stored_hash):
            remaining = tuple(h for h in stored_hashes if h != stored_hash)
            user.setMemberProperties(mapping={
                'two_factor_authentication_recovery_codes_hashes': remaining,
            })
            if len(remaining) <= 3:
                IStatusMessage(getRequest()).addStatusMessage(
                    _(u"You have {0} recovery codes left. Consider "
                      u"generating a new set.".format(len(remaining))),
                    'warning')
            return True
    return False


def validate_token_or_recovery_code(token, user=None):
    """The one new dispatcher. token.py's single call site uses this
    instead of validate_token directly; validate_token itself is untouched.
    """
    if user is None:
        user = api.user.get_current()
    if _is_six_digit_token(token):
        return validate_token(token, user=user)
    if _is_recovery_code_shape(_normalize_recovery_code_input(token)):
        return validate_recovery_code(token, user=user)
    return False
```

### Anti-Patterns to Avoid

- **A per-code salt:** Already rejected in PROJECT.md. Forces N PBKDF2 runs per login attempt
  instead of 1, turning the recovery-code path into a computational DoS lever.
- **Widening `validate_token`'s own body:** Breaks the "same six lines" precedent Phase 5 built
  and risks regressing MFA-05/06/07's already-shipped, already-tested behavior for a completely
  unrelated code shape.
- **A redirect-based one-time display view:** Reintroduces the exact problem a same-response
  render avoids — how to carry plaintext across a second request without storing it anywhere.
- **Writing recovery-code state from `pas_plugin.py` or `subscribers.py`:** Would resurrect
  exactly the MFA-12 hazard Phase 5 closed. Any write must live in a browser form view.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Slow, salted hashing of the recovery code | A custom loop hashing SHA-256 N times | stdlib `hashlib.pbkdf2_hmac('sha256', ...)` | Correctly implements RFC 8018 PBKDF2 (proper HMAC construction, correct iteration semantics); hand-rolled iterative hashing is a classic source of subtly broken KDFs |
| Constant-time comparison of the submitted code's hash against stored hashes | A manual `==` loop, or Python's `==` on hex strings | stdlib `hmac.compare_digest` (already imported in `helpers.py`) | Timing side-channels on secret comparison are solved; this codebase already uses this exact function for `validate_bar_code_reset_token` |
| Base32 encoding of the 10-byte random code | A hand-written alphabet mapper, or the `rebus` package this phase's brief and stale docs mention | stdlib `base64.b32encode` (already used one function above, in `generate_secret`) | `rebus` is not an actual dependency of this codebase (see Package Legitimacy Audit); the seed-generation code already solved this exact problem with zero extra imports |
| One-time "here are your codes" display | A signed one-time-view URL, a server-side session store, or a transient ZODB record with its own expiry/cleanup | Render inline from the same POST response by overriding the form's `render()` | Verified against the pinned `plone.z3cform` egg: no new storage surface, no expiry logic, nothing for a second request to leak |
| Recovery-code brute-force throttling | A second, parallel counter/lockout mechanism scoped to recovery codes | The exact `register_failed_second_factor` / `is_account_locked` / `reset_failed_second_factor` functions Phase 5 already built | This literally is RECOV-05's success criterion; a second counter is not redundant, it is the exact bug (an unthrottled path) this phase exists to prevent |

**Key insight:** This phase adds almost no new *mechanism* — it reuses the existing memberdata
storage substrate, the existing single-dispatch-point pattern, the existing lockout counter, and
the existing stdlib imports `helpers.py` already has open. The only genuinely new piece of logic
is the PBKDF2 hash-and-compare, which is one stdlib call plus one existing stdlib comparison.

## Common Pitfalls

### Pitfall 1: Forgetting the `memberdata_properties.xml` entries
**What goes wrong:** `two_factor_authentication_recovery_codes_salt` and
`_hashes` are written via `setMemberProperties`, but the write silently does nothing — the codes
appear to generate and validate correctly in a single in-memory test, then vanish on the next
request.
**Why it happens:** `MutablePropertySheet.setProperties` (verified this session by reading
`Products.PlonePAS/sheet.py` from the installed egg) pops any key not present in
`self._properties.keys()` with no error at all — the exact MFA-13 hazard, now for two new
properties.
**How to avoid:** Add both entries to `profiles/default/memberdata_properties.xml` in the same
commit as the helper functions, and write a set/get round-trip test for each, per the MFA-13
convention this codebase already follows.
**Warning signs:** A test that creates a user, generates codes, and reads them back *within the
same test method* passes, but a second, separately-committing test (or a real browser round
trip) shows an empty property.

### Pitfall 2: Hashing the display form instead of the canonical form
**What goes wrong:** The stored hash is computed over the code as the user will type it back
(with the display grouping dashes, or in whatever case they paste it), so a validly-typed code
with different-but-equivalent formatting is rejected.
**Why it happens:** Generation and verification must hash the *exact same string*. If generation
hashes the raw ungrouped uppercase code but the display shows a dashed/grouped form, verification
must normalize the submitted input back to the same canonical form before hashing — not the other
way around.
**How to avoid:** `_normalize_recovery_code_input` runs on the submitted value only, before
hashing; the stored hash is always computed over the raw 16-char uppercase string generated by
`generate_recovery_codes`. The dashes are presentation-only and never enter the hash.
**Warning signs:** A code copy-pasted with its display formatting fails on first use, but the
same code retyped without dashes succeeds.

### Pitfall 3: A per-code salt reintroduced by accident
**What goes wrong:** A future edit "improves" security by giving each code its own salt, silently
turning one PBKDF2 call per login attempt into ten.
**Why it happens:** Per-code salting is the more common textbook pattern for hashed secret lists;
it is *wrong here specifically* because of the shared-salt DoS tradeoff PROJECT.md already
reasoned through.
**How to avoid:** Keep `two_factor_authentication_recovery_codes_salt` singular (one value, not a
list), and validate that any patch touching this area doesn't add a per-hash salt field.
**Warning signs:** A recovery-code login attempt takes noticeably longer than ~0.1-0.25s (this
session's measured range for 20k-200k iterations); ten times that is the DoS symptom, not a
performance fluke.

### Pitfall 4: Writing recovery-code state from the PAS plugin or the `IPubBeforeCommit` subscriber
**What goes wrong:** A counter or hash-consumption write placed in `pas_plugin.py` or
`subscribers.py` silently never persists on the request path that most needs it (the
`Unauthorized`-ending challenge path aborts its transaction).
**Why it happens:** Exactly the MFA-12 hazard PROJECT.md restates as a standing constraint;
recovery codes are new *writers* of state Phase 5's invariant already covers for existing state.
**How to avoid:** All new writes (`generate_recovery_codes`, the consume-on-match write inside
`validate_recovery_code`) must be reachable only from `browser/forms/token.py` and
`browser/forms/user_setup.py`. Extend
`tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin`'s
`property_names`/`helper_function_names` tuples with the two new property names and the three new
helper function names — the guard test cannot protect a module it doesn't scan.
**Warning signs:** The extended source-grep test passes trivially without ever having been made
to fail first (no non-vacuity control) — per this codebase's own established pattern (Phase 5's
"reproduced failing" discipline), deliberately introduce one of the forbidden names into
`pas_plugin.py` locally and confirm the test catches it before considering the guard done.

### Pitfall 5: Blindly adopting OWASP's 600,000-iteration PBKDF2-HMAC-SHA256 figure
**What goes wrong:** Setting iterations to 600,000 "because OWASP says so" costs ~0.7s per
recovery-code login attempt on this hardware (linear extrapolation from the measured 100k/0.117s
figure) for no proportionate security gain.
**Why it happens:** OWASP's Password Storage Cheat Sheet figure (confirmed via WebSearch this
session, see Sources) is calibrated against **GPU-accelerated offline cracking of low-entropy,
human-chosen passwords** — a completely different threat model from an 80-bit CSPRNG-random code
with no dictionary to walk. The roadmap's own phase notes already state this explicitly ("not
load-bearing — the codes are 80-bit random values with no dictionary to walk, so iterations are
insurance").
**How to avoid:** Use a value in the roadmap's own pre-agreed 20k-200k range. This research
recommends 100,000 (0.117s measured, matches the roadmap's carried-forward figure, comfortably
mid-range).
**Warning signs:** A code review citing OWASP's cheat sheet as grounds to raise the iteration
count past 200,000 for this specific field, without engaging with the entropy-source difference.

## Code Examples

### `memberdata_properties.xml` additions

```xml
<!-- Source: verified against the installed Products.PlonePAS-*/Products/PlonePAS/sheet.py
     PropertySchema type map ('lines' accepts tuple/list; GenericSetup <element> syntax
     confirmed against an installed third-party profiles.xml example this session) -->
<property name="two_factor_authentication_recovery_codes_salt" type="string"></property>
<property name="two_factor_authentication_recovery_codes_hashes" type="lines">
</property>
```

### `token.py`'s one-line call-site change

```python
# Source: this codebase, browser/forms/token.py:113 (existing line, for context)
# Before:
valid_token = validate_token(token, user=user)
# After:
valid_token = validate_token_or_recovery_code(token, user=user)
```

Nothing else in `token.py`'s `handleSubmit` changes — `reset_failed_second_factor` on success and
`register_failed_second_factor` on failure already wrap this one call site (lines ~118-142),
which is exactly how RECOV-05 is satisfied without new plumbing.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No self-service recovery path; only an emailed, signed bar-code reset link (`request_bar_code_reset.py`) | Ten single-use, PBKDF2-hashed recovery codes, issued at enrollment, throttled by the shared lockout counter | This phase | A lost-device user regains access without an admin action and without an unthrottled brute-force path |
| PBKDF2 (any KDF) as the default choice for new secret-hashing systems | Argon2id is OWASP's current top recommendation for *user-chosen, low-entropy* secrets; PBKDF2-HMAC-SHA256 remains the FIPS-140-compliant choice and is explicitly still endorsed where a compliant/simpler KDF is needed | OWASP Password Storage Cheat Sheet, ongoing | Not a reason to switch here: this project's threat model (high-entropy random codes, no PEP-517-requiring new dependency allowed) is exactly the case where PBKDF2 remains the right-sized, lower-footprint choice |

**Deprecated/outdated:** None specific to this phase's own scope. `.claude/CLAUDE.md`'s
"Key Dependencies" reference to `rebus` for base32 encoding is stale (see Package Legitimacy
Audit) and should not be treated as current.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `argon2-cffi`'s current Python 2.7 support / PEP 517 status | Standard Stack, Alternatives Considered | Low — the recommendation to use stdlib PBKDF2 stands regardless, given the "nothing may require PEP 517" hard constraint; this claim only supports *why* Argon2 wasn't seriously evaluated, not the actual choice made |
| A2 | 100,000 PBKDF2 iterations is the "right" final number vs. some other value in the 20k-200k envelope | Standard Stack / Common Pitfall 5 | Low-Medium — the roadmap itself calls this "not load-bearing"; any value the planner or a checkpoint picks in that range is defensible. This research recommends 100,000 with measured timing evidence, but the exact number is properly a planner/operator call, not a research-settled fact |

**If a checkpoint is warranted:** The iteration-count decision is explicitly called out in
ROADMAP.md as an "Open Decision to settle here" — the planner should surface a
`checkpoint:human-verify` or at minimum record the final chosen value as a decision in STATE.md,
per this phase's own note, rather than silently picking one.

## Open Questions

1. **Should recovery codes also be accepted at `@@reset-bar-code`, not only at
   `@@google-authenticator-token`?**
   - What we know: ROADMAP.md's Phase 6 "Depends on" line names "the single dispatch point in
     the token form" specifically (singular), and `reset_bar_code.py` validates the user's
     *current* TOTP token as proof of identity before resetting the bar code image, a
     conceptually different check than "log in with a second factor."
   - What's unclear: Whether an operator would want a lost-recovery-codes-and-lost-device user to
     be able to use a recovery code to *also* reset their bar code (recovering both at once), or
     whether that's considered out of scope this phase.
   - Recommendation: Scope this phase to `token.py` only, per the roadmap's own explicit wording.
     `reset_bar_code.py` and `user_setup.py` keep calling `validate_token` directly, unchanged.
     If the operator wants recovery-code support there too, it's a small additive follow-up (swap
     the same one call site to the same dispatcher), not a redesign.

2. **Should the "≤3 remain" warning also persist on the personal-information page until the user
   regenerates, rather than firing only at the moment of consumption?**
   - What we know: RECOV-07's literal text ("warned when 3 or fewer codes remain") is satisfied
     by a one-time-per-login `IStatusMessage`, which is the minimal implementation and adds no
     new registration surface (no viewlet, no schema field).
   - What's unclear: Whether iMio's operators would prefer a persistent visual indicator (e.g., a
     small viewlet on `personal-information`) so a user who hasn't needed a recovery code in a
     while still sees the count.
   - Recommendation: Ship the login-time `IStatusMessage` first (satisfies the literal
     requirement with the least new surface); treat a persistent viewlet as an optional
     enhancement, not required for RECOV-07 as written.

## Environment Availability

Skipped — this phase introduces no new external tool, service, or runtime dependency. Every
capability used (`hashlib`, `hmac`, `base64`, `os`, `binascii`) is part of the Python 2.7.18
standard library already present and verified working in this buildout this session.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` via `bin/test` (unittest2-style test cases), `plone.app.testing` layers |
| Config file | None dedicated — test discovery comes from the buildout's `[test]` part (`base.cfg`); layers already defined in `src/imio/googleauthenticator/testing.py` |
| Quick run command | `bin/test -t test_helpers` (unit-level) / `bin/test -t test_token` (integration-level) |
| Full suite command | `bin/test -t '!robot'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RECOV-01 | 10 codes, 16 base32 chars, shown once | unit + integration | `bin/test -t test_helpers` (shape/count); `bin/test -t test_user_setup` (render-once) | ✅ both files exist, new methods needed |
| RECOV-02 | Hashed with one per-user salt, plaintext never stored | unit | `bin/test -t test_helpers` | ✅ exists, new method needed |
| RECOV-03 | Displayed exactly once, never redisplayed | integration (`Browser`) | `bin/test -t test_user_setup` | ✅ exists, new method needed |
| RECOV-04 | Accepted in place of TOTP, consumed on use, rejected on reuse | integration (`Browser` POST to `@@google-authenticator-token`) | `bin/test -t test_token` | ✅ exists (`TestTokenFormLockout`'s `_submit_token` pattern reusable), new methods needed |
| RECOV-05 | Failure increments the same counter as TOTP | integration + source-grep | `bin/test -t test_token` and `bin/test -t test_pas_plugin` | ✅ both exist; `test_pas_plugin.py`'s MFA-12 guard needs its tuples extended |
| RECOV-06 | Regeneration invalidates all previous codes | unit + integration | `bin/test -t test_helpers` / `test_user_setup` | ✅ exists, new methods needed |
| RECOV-07 | Warned when ≤3 remain | integration (`IStatusMessage` assertion after consuming down to 3) | `bin/test -t test_token` | ✅ exists, new method needed |

### Sampling Rate

- **Per task commit:** `bin/test -t test_helpers` and/or `bin/test -t test_token`, whichever the
  task touched
- **Per wave merge:** `bin/test -t '!robot'`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

None — existing test infrastructure (layers, `BaseTest`, `Browser` helpers, the four test files
this phase touches) already covers everything this phase needs. This phase adds new test methods
to `test_helpers.py`, `test_token.py`, `test_user_setup.py`, and `test_pas_plugin.py`; it creates
no new test file and needs no new fixture or `conftest`-equivalent.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | Recovery codes are literally ASVS's "look-up secret" authenticator category (V2.5-equivalent in ASVS 4.0's numbering); this phase's design (CSPRNG generation, one-time use, hashed-with-salt storage, rate-limited via the shared lockout counter) maps directly onto that category's requirements |
| V3 Session Management | No | No new session mechanism is introduced |
| V4 Access Control | No | No new access-control surface; recovery codes authenticate the same account the same way TOTP already does |
| V5 Input Validation | Yes | `_is_recovery_code_shape` gates the submitted value (length + RFC 4648 base32 alphabet) before it ever reaches the KDF, mirroring `_is_six_digit_token`'s existing precedent |
| V6 Cryptography | Yes | PBKDF2-HMAC-SHA256 via stdlib `hashlib.pbkdf2_hmac`, never hand-rolled; `os.urandom` for both codes and salt (same CSPRNG source `generate_secret` already uses) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Offline brute force of a stolen `(salt, hash-list)` pair | Information Disclosure | 80-bit CSPRNG-random codes (2^80 keyspace) plus a per-user salt defeating cross-user precomputation; PBKDF2 iterations add insurance, not the primary defense (the entropy is) |
| Unthrottled recovery-code guessing at the login form | Elevation of Privilege | Reuse of `register_failed_second_factor`/`is_account_locked` — this is the phase's core goal (RECOV-05), not an afterthought |
| Replay of an already-consumed recovery code | Tampering | Consume-on-match write (remove the matched hash from the stored list) inside `validate_recovery_code`, in the same call that determines success — mirrors `validate_token`'s existing `two_factor_authentication_last_interval` write pattern |
| Recovery-code-count oracle for an unauthenticated caller | Information Disclosure | The "≤3 remain" warning fires only after a recovery code has *successfully* authenticated the user this request — never surfaced to a failed or anonymous attempt, mirroring Phase 5's own P5-17 precedent (don't let a message leak state to an unauthenticated caller) |
| Plaintext code or hash appearing in a log line or exception message | Information Disclosure | Never log the plaintext code, the salt, or the computed hash; `validate_recovery_code` logs nothing at all on failure, matching `validate_bar_code_reset_token`'s "do not log either operand" convention already documented in this codebase |
| A future edit reintroducing a per-code salt, multiplying attempt cost | Denial of Service | Pitfall 3 above; keep the salt property singular, not a list |

## Sources

### Primary (HIGH confidence)

- This session's direct execution against the buildout's own Python 2.7.18 interpreter
  (`bin/python`, with `bin/test`'s pinned egg paths for the `cryptography` cross-check):
  `hashlib.pbkdf2_hmac` presence and timing, `hmac.compare_digest` presence,
  `base64.b32encode(os.urandom(10))` producing exactly 16 chars with no padding.
- This session's direct read of `/srv/cache/eggs/plone.z3cform-0.8.1-py2.7-linux-x86_64.egg/plone/z3cform/layout.py`
  (`FormWrapper.update`/`render`) — the redirect-skip mechanism the one-time-display pattern
  depends on.
- This session's direct read of `/srv/cache/eggs/Products.PlonePAS-5.1.1-py2.7-linux-x86_64.egg/Products/PlonePAS/sheet.py`
  (`MutablePropertySheet`, `PropertySchema` type map) — confirms `'lines'` accepts
  `tuple`/`list` and that undeclared properties are silently popped.
- This codebase's own `src/imio/googleauthenticator/helpers.py`, `pas_plugin.py`,
  `browser/forms/token.py`, `browser/forms/user_setup.py`, `browser/forms/reset_bar_code.py`,
  `adapter.py`, `userdataschema.py`, `browser/controlpanel.py`, `subscribers.py`,
  `profiles/default/memberdata_properties.xml`, `setup.py` — read directly this session.
- `.planning/ROADMAP.md` Phase 5 and Phase 6 sections, `.planning/PROJECT.md`'s Key Decisions
  table, `.planning/REQUIREMENTS.md`'s RECOV-01..07 and Open Decisions table.

### Secondary (MEDIUM confidence)

- OWASP Password Storage Cheat Sheet (WebSearch, official OWASP source):
  600,000-iteration PBKDF2-HMAC-SHA256 recommendation for password storage, and Argon2id as the
  current top general recommendation.
- OWASP ASVS / Multifactor Authentication Cheat Sheet (WebSearch, official OWASP source):
  look-up-secret storage (hash with salt below 112 bits of entropy), one-time use, brute-force
  protection expectations.
- NIST SP 800-63B (WebSearch, official NIST source): look-up secrets require ≥20 bits entropy
  minimum, rate-limiting required below 64 bits entropy — this phase's 80-bit codes clear both
  thresholds independent of the rate-limiting this phase adds anyway.

### Tertiary (LOW confidence)

- `argon2-cffi`'s current Python 2.7 / PEP 517 status (not independently verified this session;
  see Assumptions Log A1).

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — every claim verified by direct execution against the buildout's own
  interpreter and pinned eggs this session; zero new dependencies means zero registry/version
  uncertainty.
- Architecture: HIGH — the one-time-render mechanism and the memberdata `lines`-type storage
  were both confirmed by reading the actual installed source of the relevant eggs, not inferred
  from documentation or training knowledge.
- Pitfalls: HIGH — five of six pitfalls are direct extensions of already-documented, already-
  tested hazards this codebase's own Phase 3/4/5 research and code already identified (MFA-12,
  MFA-13, the per-code-salt DoS reasoning); only the OWASP-iteration-count pitfall required new
  external research.

**Research date:** 2026-08-03
**Valid until:** 30 days (stable domain — no framework/library churn risk; the only external
input, OWASP's cheat sheet figures, is cited for context/comparison, not as a pinned dependency
that could silently change under this phase)
