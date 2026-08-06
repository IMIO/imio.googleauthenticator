# Phase 3: Encrypted Seeds and Local QR - Research

**Researched:** 2026-07-30
**Domain:** Fernet symmetric encryption at rest, in-process QR rendering, and a forced
`ipaddress` dependency swap, inside a frozen Plone 4.3 / Python 2.7.18 PAS plugin
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-01 | TOTP seeds are Fernet-encrypted at rest; no plaintext seed ever written to memberdata | `encrypt_seed`/`decrypt_seed` design in Code Examples; call-site rewrite of `generate_secret`/`get_secret`/`get_or_create_secret` in `helpers.py` |
| SEC-02 | Encryption key read per-call from the process environment, never persisted | `get_encryption_key()` pattern (per-call `os.environ.get()`, not module-scope) — Code Examples, Common Pitfalls |
| SEC-03 | Enrollment and validation both fail closed on missing/invalid key | `_get_fernet()` raises, never caught locally; propagates through `_dont_swallow_my_exceptions` (Phase 1) to a 500 — Code Examples, Validation Architecture |
| SEC-04 | Ciphertext carries a `v1$` version prefix | `CIPHERTEXT_VERSION_PREFIX` in Code Examples; Don't Hand-Roll (never retrofit a version tag later) |
| SEC-05 | QR rendered in-process via `qrcode==6.1`; no external call, no subprocess argv | `get_barcode_image()` data-URI rewrite — Architecture Patterns, Code Examples |
| SEC-06 | New seeds are 160 bits of `os.urandom` | `base64.b32encode(os.urandom(20))` — **not** `rebus.b32encode`, see the executed pitfall below |
| SEC-07 | Env var documented and present in `[instance]`, `[testenv]`, CI, Puppet | Environment Availability; Common Pitfalls (env-var scope); the CI-workflow finding under "State of the Art" |
| SEC-08 | Missing key logs CRITICAL at process start, never raises from import/ZCML | `IProcessStarting` subscriber pattern — Code Examples, verified against an installed egg in this stack |
| BUG-02 | `redirect_url` bound on every code path in `user_setup.py` | Current-code re-audit under Common Pitfalls: the bug **does not currently reproduce**; regression test recommended instead of a fix |
| BUG-03 | Bar-code reset token compared constant-time, both operands encoded first | Exact current code at `reset_bar_code.py:104` quoted; fix in Code Examples |
| BUG-05 | `py2-ipaddress` replaced by `ipaddress==1.0.23`, `unicode` coercion at both call sites | Reused verbatim from `.planning/research/STACK.md`'s "ipaddress Collision" section (already HIGH confidence, executed) |
| DOC-03 | Env var and its ZEO-client failure mode documented | Environment Availability; Common Pitfalls; DOC-03 text is drafted in Code Examples |
</phase_requirements>

## Summary

This phase has three independent, well-bounded pieces of work, all forced into the same commit
by the roadmap's own reasoning: Fernet encryption at rest (with fail-closed as the load-bearing
half — encryption without fail-closed is a false sense of security), local QR rendering (without
which the plaintext seed still leaks to `chart.googleapis.com`, making the encryption pointless),
and the `ipaddress` dependency swap that `cryptography` forces mechanically. Two ride-along bug
fixes (BUG-02, BUG-03) piggyback because the files they touch are being rewritten anyway.

Almost everything here was previously researched to HIGH confidence in `.planning/research/
STACK.md` and `.planning/research/PITFALLS.md` by executing real code against the pinned eggs in
this exact buildout (`cryptography==3.3.2`, `qrcode==6.1`, `ipaddress==1.0.23` vs
`py2-ipaddress`). This document does not repeat that verification; it cites it and adds what
those documents could not yet know because Phase 2 hadn't landed: the exact current shape of
every call site the seed passes through, and one **new, executed, high-severity finding** that
contradicts the roadmap's own suggested one-liner.

**The one finding that changes the plan:** `rebus.b32encode(os.urandom(20))` — the literal
upgrade PROJECT.md and ROADMAP.md suggest for SEC-06 — raises `UnicodeDecodeError` on
essentially every call. `rebus`'s `encode()` helper calls Python 2's `str.encode()` on the raw
random bytes before base32-encoding them, which implicitly decodes via the `ascii` codec first;
`os.urandom(20)` almost always contains a byte ≥ 0x80. This was reproduced by direct execution
(5/5 trials failed) against this repo's own `python2.7`, see Common Pitfalls. The fix is to drop
`rebus` for seed generation entirely and use stdlib `base64.b32encode(os.urandom(20))`, which
produces a clean 32-character, unpadded RFC 4648 base32 string — verified round-tripping and
matching exactly what `onetimepass.get_hotp()` expects (`base64.b32decode(secret,
casefold=True)`, read from the installed egg's source). `rebus` becomes an unused dependency and
can be dropped from `install_requires`.

**Primary recommendation:** Add two module-level functions to `helpers.py` —
`encrypt_seed(plaintext)` / `decrypt_seed(ciphertext)` — that wrap `cryptography.fernet.Fernet`
with the `v1$` envelope and the `str`/`unicode` bytes discipline Python 2 demands, route
`generate_secret`/`get_secret`/`get_or_create_secret` through them, replace `get_barcode_image()`
with an in-process `qrcode`-rendered `data:image/png;base64,...` URI (no new BrowserView, no new
permission surface — the smallest diff that satisfies SEC-05), and read the key with a plain
per-call `os.environ.get()` function that is never called at import time.

## Architectural Responsibility Map

This package is a monolithic Zope 2 / Plone 4.3 add-on, not a multi-tier browser/API/CDN
application — there is no separate frontend server or API service. The table below maps each
capability to the closest analogous tier in this codebase's own architecture.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Seed encrypt/decrypt (Fernet) | Backend logic (`helpers.py`) | Storage (memberdata `string` property, unchanged schema) | Pure function pair, called from both the PAS auth boundary and the z3c.form views; no view or storage-schema change needed |
| Encryption key retrieval | Backend logic (`helpers.py`, per-call) | Process/Deploy (buildout `environment-vars` + Puppet `concat::fragment`) | Never persisted; lives only in `os.environ`, injected at process start by buildout/Puppet |
| Fail-closed enforcement | Backend logic (`helpers.py` raises) | Auth boundary (`pas_plugin.py` — exception propagates via `_dont_swallow_my_exceptions`) | The raise happens in the helper; the *consequence* (500 instead of bypass) is a Phase 1 guarantee on the plugin, not new work here |
| QR rendering | View/SSR-equivalent (`browser/forms/user_setup.py`, `reset_bar_code.py` via `helpers.get_barcode_image`) | — | In-process, server-side rendering into an existing z3c.form field description; no client-side JS, no new endpoint |
| `ipaddress` swap | Backend logic (`helpers.py:459,496`) | Deploy (`setup.py`, `test-4.3.cfg` `[versions]`) | Forced by `cryptography`'s own dependency; call sites and pins both need the edit |
| Process-start CRITICAL log | Startup subscriber (`IProcessStarting`, new module) | — | Fires once at Zope startup, independent of any request |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `cryptography` | `== 3.3.2` | Fernet symmetric encryption of TOTP seeds | `[VERIFIED: STACK.md, executed]` Last release publishing a `cp27` wheel (2021-02-07); 3.4 requires Python ≥3.6 and adds a Rust build step. Already pinned and building in `server.dmsmail/versions-base.cfg:219` |
| `ipaddress` | `== 1.0.23` | Hard dependency of `cryptography` on py2; replaces `py2-ipaddress` | `[VERIFIED: STACK.md, executed]` Final release (2019-10-18); both distributions install a top-level `ipaddress` module and cannot coexist — see BUG-05 in Common Pitfalls |
| `qrcode` | `== 6.1` | Local, in-process QR rendering | `[VERIFIED: STACK.md, executed]` Last py2-compatible release (2019-01-14); 7.0 dropped Python 2. Verified rendering a real PNG (848 bytes) and a Pillow-free SVG under this interpreter |
| `cffi` | `== 1.15.1` | `cryptography`'s C FFI dependency on py2 | `[VERIFIED: STACK.md]` Last `cp27` wheel (2022-06-30); already required transitively but not yet pinned in `test-4.3.cfg` |

`enum34==1.1.10` and `six==1.16.0` are also required by `cryptography` on py2 and are **already
pinned** (`test-4.3.cfg:51`, `:22`).

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `base64` | 2.7.18 | `b32encode`/`b32decode` for the 160-bit seed | Always — replaces `rebus.b32encode` for seed generation (see Summary and Common Pitfalls) |
| stdlib `os` | 2.7.18 | `os.urandom(20)` entropy source, `os.environ.get()` key read | Always |
| `zope.processlifetime` | already present transitively (`ZServer` requires it) | `IProcessStarting` event for SEC-08's CRITICAL log | Add a `<subscriber>` — no new `install_requires` line needed, it is already on the path via `ZServer` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `cryptography==3.3.2` Fernet | `pycryptodome` | Only if `cryptography` could not build — it can. Fernet also bundles AES-CBC + HMAC authentication and a versioned token format; hand-rolling that on a raw primitive is exactly where seed encryption goes wrong (see Don't Hand-Roll) |
| Data-URI QR embedding (`data:image/png;base64,...`) | A dedicated `qrcode`-serving `BrowserView` | Only if a separate cacheable image endpoint is wanted. The data-URI is the smaller diff: no new ZCML registration, no new permission check to get right, no second HTTP round trip that could be requested for a different user's seed by URL manipulation. See Common Pitfalls for the authorization risk a separate view would introduce |
| stdlib `base64.b32encode` for the seed | `rebus.b32encode` | Never for raw random bytes — see the executed pitfall in Summary. `rebus` can be dropped from `install_requires` once this is the only call site removed |

**Installation:**
```bash
# setup.py install_requires: add
'cryptography==3.3.2',
'ipaddress==1.0.23',      # replaces py2-ipaddress
'qrcode==6.1',
# remove:
# 'py2-ipaddress>2.0.1',
# 'rebus>=0.1',           # its one call site (generate_secret) moves to stdlib base64
```
```ini
# test-4.3.cfg [versions]: add
cryptography = 3.3.2
cffi = 1.15.1
ipaddress = 1.0.23
qrcode = 6.1
# remove:
# py2-ipaddress = 3.4.2
```

**Version verification:** All four pinned versions above were verified in `.planning/research/
STACK.md` by fetching PyPI JSON release metadata filtered for `cp27`/`py2.py3` files with upload
dates, and by executing real code (Fernet round-trip, QR PNG/SVG render, both `ipaddress`
implementations in isolation) against this repo's own pinned eggs. This research session did not
re-run those checks — see `package-legitimacy check` below for why the automated legitimacy gate
alone is insufficient evidence for a two-year-old pinned version.

## Package Legitimacy Audit

| Package | Registry | Age (of pinned version) | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|--------------------------|-----------|--------------|---------|-------------|
| `cryptography` | PyPI | 3.3.2 released 2021-02-07 (~5.5 yrs) | not resolvable by this session's tooling | github.com/pyca/cryptography | `[SUS]` (heuristic: "unknown-downloads", "no-repository" — both against the *latest* release's metadata, not the pinned 3.3.2) | Approved — already pinned and in production in `server.dmsmail/versions-base.cfg:219`; independently confirmed via direct PyPI JSON query in STACK.md (HIGH). Planner: add a `checkpoint:human-verify` before the `install_requires` edit per protocol, but treat as low-risk |
| `ipaddress` | PyPI | 1.0.23 released 2019-10-18 | not resolvable | github.com/phihag/ipaddress | `[SUS]` ("unknown-downloads") | Approved — this is the CPython 3.3+ stdlib module's own official py2 backport, by the module's original author; confirmed via executed round-trip in STACK.md. `checkpoint:human-verify` per protocol |
| `qrcode` | PyPI | 6.1 released 2019-01-14 | not resolvable | github.com/lincolnloop/python-qrcode | `[SUS]` ("unknown-downloads") | Approved — the de facto standard Python QR library (`lincolnloop/python-qrcode`, widely used); confirmed rendering real PNG/SVG in STACK.md. `checkpoint:human-verify` per protocol |
| `cffi` | PyPI | 1.15.1 released 2022-06-30 | not resolvable | github.com/python-cffi/cffi (not returned for the queried/latest version) | `[SUS]` ("too-new", "unknown-downloads", "no-repository" — all against the *current latest* cffi release, not 1.15.1) | Approved — required transitively by `cryptography` on py2 today (unpinned); pinning it is housekeeping, not a new dependency. `checkpoint:human-verify` per protocol |
| `rebus` | PyPI | already an existing dependency (`rebus>=0.1`, resolved 0.2, 2013) | not resolvable | github.com/barseghyanartur/rebus | `[SUS]` ("unknown-downloads") | **Being removed**, not added — its one call site moves to stdlib `base64`. No action needed beyond deleting the `install_requires` line |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** all four newly-relevant packages above, per the
automated heuristic. Every one is independently corroborated by this project's own prior
executed research (`STACK.md`) or by being an existing, already-shipping dependency elsewhere in
the iMio stack (`cryptography` in `server.dmsmail`). The `[SUS]` reasons returned by the tool
(`unknown-downloads`, `no-repository`, `too-new`) are artifacts of the checker resolving each
package's *current latest* PyPI metadata rather than the specific multi-year-old `cp27` release
this buildout pins — this is expected for any Python 2-only pin in 2026 and is not, by itself,
evidence of a supply-chain problem. The planner should still add one lightweight
`checkpoint:human-verify` task before the `install_requires`/`test-4.3.cfg` edit, per the audit
protocol, but it does not need to block on it.

## Architecture Patterns

### System Architecture Diagram

```
Enrollment (SetupForm.handleSubmit / updateFields)
  |
  v
get_token_description() --> get_or_create_secret(user, overwrite=False)
  |                                |
  |                                +--> secret property empty? --> generate_secret(user)
  |                                |         os.urandom(20) --base64.b32encode--> plaintext seed
  |                                |         plaintext seed --encrypt_seed()--> "v1$<fernet-token>"
  |                                |         user.setMemberProperties({'two_factor_authentication_secret': ciphertext})
  |                                |         returns PLAINTEXT seed (in-memory only, this request)
  |                                +--> secret property non-empty? --> decrypt_seed(ciphertext) --> plaintext seed
  |
  v
get_barcode_image(username, domain, plaintext_seed)
  |     builds otpauth://totp/... URI in-process
  |     qrcode.make(uri) --> PNG bytes (io.BytesIO)
  |     base64-encodes PNG --> "data:image/png;base64,..."
  v
<img src="data:image/png;base64,..."> rendered inline in the SetupForm field description
  (no request ever reaches chart.googleapis.com; no subprocess, no argv)

Validation (TokenForm.handleSubmit / SetupForm.handleSubmit)
  |
  v
validate_token(token, user) --> get_secret(user) --> ciphertext = user.getProperty(...)
  |                                                        |
  |                                                        v
  |                                              decrypt_seed(ciphertext)
  |                                                        |
  |                       key missing/garbage --> ValueError, UNCAUGHT here
  |                       (propagates: _dont_swallow_my_exceptions=True, Phase 1, => 500,
  |                        never a plaintext fallback, never password-only)
  |                                                        |
  v                                                        v
onetimepass.valid_totp(token, plaintext_seed)  <-----------+

Process startup (Zope boot, independent of any request)
  |
  v
IProcessStarting subscriber --> get_encryption_key() falsy? --> logger.critical(...)
  (does NOT raise -- a raise here would kill bin/instance debug and bin/test, per PITFALLS.md P12)
```

### Recommended Project Structure

No new files are required. All changes fit inside existing modules:

```
src/imio/googleauthenticator/
├── helpers.py              # + get_encryption_key, _get_fernet, encrypt_seed, decrypt_seed
│                            #   generate_secret/get_secret/get_or_create_secret rewritten
│                            #   get_barcode_image rewritten (local qrcode, data URI)
│                            #   extract_ip_address_from_request / get_ip_ranges: ipaddress swap only
├── subscribers.py           # NEW: on_process_starting (SEC-08)
├── configure.zcml           # + <subscriber for="zope.processlifetime.IProcessStarting" .../>
├── browser/forms/
│   ├── user_setup.py        # BUG-02 regression test only (see Common Pitfalls — no code bug found)
│   └── reset_bar_code.py    # BUG-03: hmac.compare_digest with both sides encoded
└── tests/
    ├── test_helpers.py      # encrypt/decrypt round-trip, fail-closed, v1$ prefix, seed entropy
    └── test_setuphandlers.py or a new test_subscribers.py  # IProcessStarting CRITICAL log
```

### Pattern 1: Per-call key read, never module scope

**What:** `get_encryption_key()` calls `os.environ.get(...)` fresh on every invocation.
**When to use:** Always, for this key. Module-scope `os.getenv()` (the pattern
`imio.helpers/__init__.py:44-55` uses for `SSO_APPS_CLIENT_SECRET`) freezes the value at import
time — before `bin/test`'s environment is necessarily populated, and impossible to override
per-test. The roadmap's phase notes call this divergence out explicitly so it does not read as
an oversight.
**Example:**
```python
# Pattern verified against this repo's own reference implementation of the analogous
# SSO_APPS_CLIENT_SECRET key (server.dmsmail/src/imio.helpers/src/imio/helpers/__init__.py:46),
# deliberately inverted from module-scope to per-call per this phase's ROADMAP notes.
import os

ENV_VAR_NAME = 'IMIO_GA_SEED_KEY'  # [ASSUMED] naming convention — see Assumptions Log


def get_encryption_key():
    return os.environ.get(ENV_VAR_NAME)
```

### Pattern 2: Fail-closed via propagation, not via a caught fallback

**What:** `encrypt_seed`/`decrypt_seed` raise `ValueError` on any failure (missing key, malformed
key, `InvalidToken`). Neither function catches its own exception to fall back to anything.
**When to use:** Both enrollment (`generate_secret`) and validation (`get_secret`).
**Example:** see Code Examples below — this pattern is the entire point of SEC-03 and is asserted
by two tests per the ROADMAP's own success criteria, not by one.

### Anti-Patterns to Avoid

- **A `BrowserView` endpoint for the QR image, addressable by a request parameter naming the
  target user:** creates a fresh authorization surface (which user's QR am I allowed to see?)
  that the data-URI approach never has to answer, because the image is embedded server-side
  during the *already-authorized* enrollment form render. If a separate endpoint is ever wanted
  later, it must scope strictly to `api.user.get_current()` and never accept a username/user-id
  parameter.
- **Catching `InvalidToken` (or any exception) inside `authenticateCredentials` or a challenge
  plugin to "gracefully" fall back:** this is precisely the silent-bypass shape Pitfall 4
  (`.planning/research/PITFALLS.md`) documents. Let it propagate.
- **`os.getenv()` at module import time for this key:** see Pattern 1.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Authenticated symmetric encryption of the seed | A raw AES-CBC + custom HMAC scheme | `cryptography.fernet.Fernet` | Fernet already bundles AES-128-CBC + HMAC-SHA256 authentication and a versioned token format (its own internal version byte, timestamp, IV, ciphertext, HMAC) — hand-rolling any piece of this is exactly where seed-at-rest encryption schemes go wrong |
| Base32 seed encoding | `rebus.b32encode` for raw random bytes | stdlib `base64.b32encode` | `rebus`'s padding-then-`str.encode()` trick was written for encoding short ASCII text (`str(uuid4())`), not raw binary entropy — see the executed pitfall in Summary |
| QR code rendering | Hand-writing a QR bitmap encoder, or shelling out to a system tool | `qrcode==6.1` (pure Python, in-process) | Already the resolved, research-adjudicated decision (PROJECT.md reversed the earlier `imio.helpers`+`zint` plan after finding the seed leaks into subprocess argv) |
| Key-presence + malformed-key validation | A single `except Exception` around `Fernet(key)` | `except (ValueError, TypeError)` explicitly | On py2, a base64-malformed key raises `TypeError` from `binascii`, not `ValueError` — catching only `ValueError` produces a confusing raw `TypeError` traceback instead of an operator-readable message |

**Key insight:** every "don't hand-roll" item above is also a fail-closed correctness
requirement, not just a convenience: a hand-rolled encoding or cipher construction is exactly
where a subtle bug becomes a silent downgrade, and this phase's entire point is that a downgrade
must never be silent.

## Common Pitfalls

### Pitfall A: `rebus.b32encode(os.urandom(N))` raises `UnicodeDecodeError` on almost every call

**Confidence: HIGH — executed directly against this repo's own `python2.7` interpreter (5/5
trials failed).**

**What goes wrong:** `rebus`'s internal `encode()` helper (read from
`/srv/cache/eggs/rebus-0.2-py2.7-linux-x86_64.egg/rebus/__init__.py`) does:
```python
changed_text = binary_type((text + (padding_count * DEFAULT_SUFFIX)).encode())
```
`text + padding` is a Python 2 `str` (bytes). Calling `.encode()` on a `str` with no other
codecs installed implicitly **decodes it via `ascii` first**, then re-encodes. `os.urandom(20)`
is uniformly random bytes 0–255; the probability that all 20 bytes are ASCII (< 0x80) is
`0.5**20 ≈ 1e-6`. Reproduced live:
```
$ python2.7 -c "
import os
DEFAULT_SUFFIX = '\n'
def encode_repro(text, step=5):
    return str((text + ((int(len(text)/step)+1)*step - len(text)) * DEFAULT_SUFFIX).encode())
for _ in range(5):
    try:
        encode_repro(os.urandom(20))
        print('OK')
    except Exception as e:
        print('FAIL', type(e).__name__)
"
FAIL UnicodeDecodeError
FAIL UnicodeDecodeError
FAIL UnicodeDecodeError
FAIL UnicodeDecodeError
FAIL UnicodeDecodeError
```
This directly contradicts the literal code PROJECT.md and ROADMAP.md suggest for SEC-06
(`b32encode(os.urandom(20))`), which — if read as "keep using `rebus.b32encode`" — would make
every enrollment attempt crash.

**Why it happens:** `rebus.b32encode` was designed to encode short ASCII text (its own test
suite only ever feeds it strings like `'abcdefghij...'`), not raw binary entropy. `str(uuid4())`
(the current code) is always ASCII, so the bug never surfaced before.

**How to avoid:** Use stdlib `base64.b32encode(os.urandom(20))` instead. Verified:
```python
>>> import os, base64
>>> seed = os.urandom(20)
>>> b32 = base64.b32encode(seed)      # '7D6Z7TN45FK5GNWUXTOPK3QGKMZNOV3P', 32 chars, no '=' padding
>>> base64.b32decode(b32) == seed
True
```
20 bytes is an exact multiple of the base32 block size (5 bytes → 8 chars), so no `=` padding
appears — matching the property `rebus.b32encode` was actually being used for (a signature-free
string). This is also **exactly** the decode path `onetimepass.get_hotp()` uses internally
(`base64.b32decode(secret, casefold=True)`, read from the installed egg), so no other call site
needs to change. `rebus` becomes unused and can be dropped from `install_requires`.

**Warning signs:** any test that calls the real `generate_secret()` (not a mocked one) and
asserts the returned seed decodes with `onetimepass.get_hotp` will fail loudly on this — write
that test, not a mock-based one, so this class of bug cannot hide again.

**Phase to address:** Encryption (this phase), same commit as the Fernet work since both touch
`generate_secret`.

---

### Pitfall B: BUG-02's `UnboundLocalError` does not currently reproduce — verify before "fixing"

**Confidence: HIGH — full control-flow trace of the current source, all three branches.**

**What was checked:** ROADMAP.md and PROJECT.md both cite `user_setup.py:96` for an
`UnboundLocalError` on `redirect_url`. Reading the current file in full (post-Phase-1's WR-04
fix, commit `719884e`):
```python
reason = None
if valid_token:
    try:
        ...
        redirect_url = "{0}/@@personal-information".format(self.context.absolute_url())
    except Exception:
        logger.exception("Two-step verification setup failed")
        reason = _("An unexpected error occurred.")
else:
    reason = _("Invalid token or token expired.")

if reason is not None:
    IStatusMessage(self.request).addStatusMessage(_("Setup failed! {0}".format(reason)), 'error')
    redirect_url = "{0}/@@setup-two-factor-authentication".format(self.context.absolute_url())

self.request.response.redirect(redirect_url)
```
Tracing every branch: `valid_token` True + no exception → `redirect_url` set in the `try`,
`reason` stays `None`, the `if reason is not None` block is skipped, `redirect_url` is already
bound. `valid_token` True + exception → `reason` set, `redirect_url` **not** set in the `try`,
but the `if reason is not None` block sets it. `valid_token` False → `reason` set directly, same
fallback block sets `redirect_url`. **`redirect_url` is bound on every reachable path in the
code as it exists today.**

**Why it happens (best guess):** the description in ROADMAP.md/PROJECT.md likely predates a
fix that landed incidentally elsewhere (Phase 1's fail-closed audit fixed several similar
"crashes on ordinary input" bugs; this may be one, or the description may simply be stale
relative to an earlier iteration of this file).

**How to avoid re-litigating a non-bug:** Phase 3 is already rewriting this handler's secret
handling (`get_or_create_secret` → now decrypts/encrypts, can raise `ValueError` on a bad key).
**Do not** "fix" `redirect_url` binding — there is nothing to fix. Instead:
1. Add a regression test locking in the invariant across all three branches (valid token/success,
   valid token/exception, invalid token), asserting the correct redirect target in each case.
2. Note explicitly in the plan/commit that BUG-02 was found already-resolved during Phase 3
   research, so the requirement is satisfied by a **regression test**, not a code change — this
   keeps REQUIREMENTS.md traceability honest without inventing a fix for a bug that isn't there.
3. Watch the *new* failure mode this phase introduces: `get_or_create_secret` can now raise
   `ValueError` (missing/bad key) from inside the `try` at enrollment. That exception is caught
   by the existing bare `except Exception:` and converted to `reason = "An unexpected error
   occurred."` — which does **not** satisfy SEC-03's fail-closed requirement in spirit (it fails
   *safe* in the sense that no plaintext seed is stored, but it presents as a generic error
   rather than a loud, distinguishable failure). Decide explicitly whether the enrollment
   fail-closed test should assert on this generic message or whether `ValueError` needs to be
   re-raised past this handler (matching the roadmap's "never downgraded... never password-only"
   framing, which is about *login*, not enrollment UX) — see Open Questions.

**Phase to address:** Encryption (this phase) — as a regression test, not a fix.

---

### Pitfall C: BUG-03's exact current code, and why a naive `!=`→`compare_digest` swap breaks every reset

**Confidence: HIGH — exact file:line read; `hmac.compare_digest` str/unicode behavior reused
from `.planning/research/STACK.md` (executed there).**

**Current code**, `browser/forms/reset_bar_code.py:104`:
```python
bar_code_reset_token = user.getProperty('bar_code_reset_token')
if bar_code_reset_token != signature_token:
```
`bar_code_reset_token` is stored as a `str` — `request_bar_code_reset.py:84` does
`user.setMemberProperties(mapping={'bar_code_reset_token': str(signature),})`. `signature_token`
is `self.request.get('signature', '')` — `unicode`, from the request. `!=` compares across
`str`/`unicode` without raising (Python 2 falls back to a byte-by-byte compare, or a
`UnicodeWarning` at worst for non-ASCII content), so today's comparison works but is not
constant-time — a timing oracle on the reset token.

**Why a naive swap breaks it:** `hmac.compare_digest(a, b)` raises `TypeError: 'unicode' does not
have the buffer interface` (or `'str' does not have the buffer interface` the other way) when
`a` and `b` are different types on Python 2 — verified in STACK.md. Swapping the operator without
encoding both sides first turns "works but insecure" into "crashes on every single reset
attempt".

**How to avoid:** encode both sides to the same type before comparing:
```python
from hmac import compare_digest

bar_code_reset_token = (user.getProperty('bar_code_reset_token') or '')
if isinstance(bar_code_reset_token, unicode):
    bar_code_reset_token = bar_code_reset_token.encode('ascii')
signature_token = signature_token.encode('ascii') if isinstance(signature_token, unicode) else signature_token

if not compare_digest(bar_code_reset_token, signature_token):
    reason = _("Invalid bar-code reset token.")
    ...
```

**Phase to address:** Encryption (this phase) — same file, same commit as any other secret-path
edit, per the roadmap's phase notes.

---

### Pitfall D: `ska` signing-key derivation reads the *ciphertext*, not the plaintext seed — re-verify the ASCII assumption

**Confidence: MEDIUM — reasoning verified, not yet executed against a real Fernet token inside
the netstring join.**

**What to check:** `get_ska_secret_key()` (Phase 2's shape) reads
`user.getProperty('two_factor_authentication_secret')` directly and folds it into the derived
`ska` signing key via the length-prefixed netstring join
(`u'{0}:{1}'.format(len(part), part)`). After this phase, that property holds `v1$<fernet-token>`
— not the plaintext seed. This is almost certainly fine and requires **no code change** to
`get_ska_secret_key`: a Fernet token is URL-safe base64 (`A-Za-z0-9-_=`), pure ASCII, and the
`v1$` prefix is ASCII, so the component is still a plain ASCII string suitable for `len()` and
string formatting. **This is exactly the assumption STATE.md flags as "must be re-checked, not
re-assumed"** (from `02-SECURITY.md` R-02-02) — it was accepted on the grounds that every
`get_ska_secret_key()` component is ASCII by construction, and this phase is precisely where that
construction changes.

**What could still go wrong:** if `setMemberProperties` or `getProperty` silently coerces the
stored `unicode` ciphertext to a `str` (or vice versa) in a way that mangles the URL-safe base64
alphabet (it should not — the alphabet is ASCII-only both ways), or if a future ciphertext
version ever needed a delimiter character that collides with the netstring format. Neither is
expected, but should be an explicit assertion in a test, not silently assumed a second time.

**How to avoid:** add one test that stores a real `v1$<fernet-token>` value via
`setMemberProperties`, calls `get_ska_secret_key()`, and asserts no exception and a string result
of the expected form — closing the loop STATE.md opened rather than carrying the assumption
forward a third time.

**Phase to address:** Encryption (this phase) — one test, no production code change expected.

---

### Pitfall E: the CI-workflow item in SEC-07 likely needs no `.github/workflows` edit at all

**Confidence: HIGH — the reusable workflow's source was read directly via `gh api`.**

**What was checked:** `.github/workflows/package-test.yml` calls
`IMIO/gha-workflows/.github/workflows/package-test-legacy.yml@v1`, which only exposes fixed
inputs (`buildout_config_file`, `test_command`, etc.) and one secret
(`mattermost_webhook_url`) — there is **no generic mechanism to inject an arbitrary extra
environment variable** into the composite action it delegates to
(`IMIO/gha/plone-package-test-notify@v4`). Read directly:
```yaml
- name: Run tests
  uses: IMIO/gha/plone-package-test-notify@v4
  with:
    BUILDOUT_CONFIG_FILE: ${{ inputs.buildout_config_file }}
    ...
    TEST_COMMAND: ${{ inputs.test_command }}   # defaults to 'bin/test'
```
Since CI only ever runs `bin/buildout` (with our `test-4.3.cfg`) and then `bin/test`, and
`bin/test`'s generated runner already sources its environment from `[test] environment =
testenv` (confirmed in `base.cfg:46-47`; this is the exact mechanism PITFALLS.md's Pitfall 12
table already documents), **the key reaches CI automatically once it is added to `[testenv]` in
`base.cfg`** — no separate `.github/workflows/package-test.yml` change is possible or necessary
given this reusable workflow's fixed input surface.

**How to avoid wasted work:** do not add a task to edit `.github/workflows/package-test.yml`.
Instead, document in DOC-03 that CI inherits the key transitively through `[testenv]`, and word
SEC-07's "CI workflow" checklist item as "confirmed inherited via `[testenv]`", not as a fourth
independent edit.

**Phase to address:** Encryption (this phase), documentation only.

---

### Pitfall F (carried forward, cited not re-derived): the `ipaddress` / `py2-ipaddress` collision

**Confidence: HIGH — fully verified by execution in `.planning/research/STACK.md`; reused
verbatim rather than re-verified in this session, since nothing about the buildout's egg
resolution has changed since 2026-07-28.**

Both `py2-ipaddress` and `ipaddress` install a top-level module of the same name; whichever
lands first on `sys.path` wins, and the module `cryptography` needs (`ipaddress==1.0.23`)
rejects the plain `str` this package's `helpers.py:459` and `:496` currently pass —
`ip_address('192.168.1.1')` raises `AddressValueError` under `ipaddress==1.0.23`, but
`ip_address(u'192.168.1.1')` succeeds. Fix: remove `py2-ipaddress` from `setup.py` and
`test-4.3.cfg`, add `ipaddress==1.0.23`, and coerce to `unicode` at both call sites:
```python
# helpers.py:459 (extract_ip_address_from_request)
return ipaddress.ip_address(ip.decode('ascii'))
# helpers.py:496 (get_ip_ranges, inside the loop)
ranges.append(ipaddress.ip_network(net.decode('ascii') if isinstance(net, str) else net))
```
`tests/test_helpers.py:17-18` already imports `from ipaddress import IPv4Network, IPv4Address` —
those names exist in both implementations, so no test-import change is needed. Full detail,
including the concrete `AddressValueError`/success table for each implementation, is in
`.planning/research/STACK.md` §"The `ipaddress` Collision (BLOCKING)" — read that section before
touching `helpers.py`'s IP-whitelist code.

**Phase to address:** Encryption (this phase), same commit as the Fernet work per the roadmap's
same-commit grouping.

## Code Examples

### `helpers.py` — key retrieval, fail-closed Fernet wrapper, `v1$` envelope

```python
# Source: this phase's own design, following cryptography 3.3.2's verified exception
# contract (.planning/research/STACK.md, executed) and the SSO_APPS_CLIENT_SECRET
# env-var pattern already used elsewhere in the iMio stack (imio.helpers/__init__.py),
# deliberately inverted to per-call per this phase's ROADMAP notes.
import base64
import os

from cryptography.fernet import Fernet, InvalidToken

ENV_VAR_NAME = 'IMIO_GA_SEED_KEY'  # [ASSUMED] naming convention -- confirm before locking
CIPHERTEXT_VERSION_PREFIX = 'v1$'


def get_encryption_key():
    """
    Reads the Fernet key from the process environment on every call (SEC-02).
    Never at module scope -- see Architecture Patterns, Pattern 1.

    :return string or None:
    """
    return os.environ.get(ENV_VAR_NAME)


def _get_fernet():
    """
    Fail closed (SEC-03): a missing or malformed key raises here and is
    NEVER caught in this module. With _dont_swallow_my_exceptions = True
    (Phase 1) on the PAS plugin, that turns into a 500 on the login path
    instead of a silent fallthrough to plaintext or password-only auth.

    :raises ValueError: key absent, or key present but malformed.
    """
    key = get_encryption_key()
    if not key:
        raise ValueError(
            '{0} is not set; refusing to encrypt/decrypt a TOTP seed'.format(ENV_VAR_NAME))
    if isinstance(key, unicode):
        key = key.encode('ascii')
    try:
        return Fernet(key)
    except (ValueError, TypeError) as e:
        # ValueError: right-shaped base64, wrong length.
        # TypeError: not valid base64 at all -- binascii raises TypeError on py2,
        # not ValueError. Catch both or a malformed key produces a bare TypeError
        # traceback instead of an operator-readable message.
        raise ValueError('{0} is malformed: {1}'.format(ENV_VAR_NAME, e))


def encrypt_seed(plaintext_seed):
    """
    :param str plaintext_seed: base32 TOTP seed (ASCII).
    :return unicode: 'v1$<fernet-token>' (SEC-01, SEC-04).
    """
    fernet = _get_fernet()
    if isinstance(plaintext_seed, unicode):
        plaintext_seed = plaintext_seed.encode('ascii')
    token = fernet.encrypt(plaintext_seed)
    return u'{0}{1}'.format(CIPHERTEXT_VERSION_PREFIX, token.decode('ascii'))


def decrypt_seed(ciphertext):
    """
    :param ciphertext: 'v1$<fernet-token>'; str or unicode (Plone coerces
        memberdata properties between the two freely).
    :return str: the plaintext base32 seed.
    :raises ValueError: unknown/missing version prefix, missing/malformed key,
        or a token that fails to decrypt. Always fail closed (SEC-03) --
        never a plaintext or None fallback.
    """
    if not ciphertext or not ciphertext.startswith(CIPHERTEXT_VERSION_PREFIX):
        raise ValueError('Unrecognized or missing ciphertext version prefix')
    token = ciphertext[len(CIPHERTEXT_VERSION_PREFIX):]
    if isinstance(token, unicode):
        token = token.encode('ascii')
    fernet = _get_fernet()
    try:
        return fernet.decrypt(token)
    except InvalidToken:
        raise ValueError(
            'TOTP seed ciphertext failed to decrypt -- wrong key or tampered value')
```

### `helpers.py` — seed generation, storage, and retrieval rewritten

```python
# Source: this phase's design; base64.b32encode replaces rebus.b32encode for the
# reason executed and documented in Common Pitfalls (Pitfall A).
def generate_secret(user):
    """
    Generates a 160-bit secret for the user (SEC-06; RFC 4226 SS4 R6's
    128-bit minimum). Stores it Fernet-encrypted (SEC-01) and returns the
    PLAINTEXT seed for this request only, so the caller can render the QR
    code once, at enrollment.

    :param Products.PlonePAS.tools.memberdata user:
    :return str: plaintext base32 seed.
    """
    plaintext_seed = base64.b32encode(os.urandom(20))
    ciphertext = encrypt_seed(plaintext_seed)
    user.setMemberProperties(
        mapping={'two_factor_authentication_secret': ciphertext})
    return plaintext_seed


def get_secret(user=None, hashed=False):
    """
    Gets the user's plaintext TOTP secret, decrypting the stored ciphertext.
    Fails closed: a missing/malformed key or a tampered ciphertext raises
    ValueError, uncaught -- never a plaintext fallback (SEC-03).
    """
    if user is None:
        user = api.user.get_current()
    if user:
        ciphertext = user.getProperty('two_factor_authentication_secret')
        if isinstance(ciphertext, basestring) and ciphertext:
            return decrypt_seed(ciphertext)


def get_or_create_secret(user, overwrite=False):
    """
    Same public contract as today: returns the PLAINTEXT seed either way.
    """
    if user is None:
        user = api.user.get_current()
    if overwrite:
        return generate_secret(user)

    ciphertext = user.getProperty('two_factor_authentication_secret')
    if isinstance(ciphertext, basestring) and ciphertext:
        return decrypt_seed(ciphertext)
    return generate_secret(user)
```

### `helpers.py` — local QR rendering, replacing the Google Charts call

```python
# Source: qrcode==6.1 API verified by execution in .planning/research/STACK.md
# (real PNG rendered, 848 bytes, under this exact interpreter).
import io

import qrcode


def get_barcode_image(username, domain, secret):
    """
    Renders the enrollment QR in-process (SEC-05): no request reaches
    chart.googleapis.com, and no subprocess/argv ever carries the seed.

    :return string: a data: URI, embeddable directly as an <img src="...">.
    """
    otpauth_uri = "otpauth://totp/{0}@{1}?secret={2}".format(
        username, domain, secret)
    img = qrcode.make(otpauth_uri)
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    png_b64 = base64.b64encode(buf.getvalue())
    return 'data:image/png;base64,{0}'.format(png_b64)
```
`get_token_description()` needs no change beyond this — it already wraps whatever
`get_barcode_image()` returns in `'<div><img src="{url}" alt="QR Code" /></div>'`.

### `IProcessStarting` subscriber — SEC-08's CRITICAL log

```python
# Source: pattern read verbatim from an installed egg already in this exact stack's
# eggs cache -- Products.PloneMeeting-4.2.28.9's events.zcml/events.py, which
# registers exactly this hook shape against zope.processlifetime.IProcessStarting
# (already available transitively via ZServer's own requires.txt -- no new
# install_requires entry needed).
# subscribers.py
import logging

from imio.googleauthenticator.helpers import get_encryption_key

logger = logging.getLogger("imio.googleauthenticator")


def on_process_starting(event):
    """
    Logs CRITICAL if the encryption key is absent at Zope startup (SEC-08).
    Deliberately does NOT raise: a raise here would also kill bin/instance
    debug and bin/test, which is worse than a loud log line -- see
    PITFALLS.md Pitfall 12/4.
    """
    if not get_encryption_key():
        logger.critical(
            "IMIO_GA_SEED_KEY is not set. Two-factor authentication seed "
            "encryption/decryption will fail closed on every enrollment and "
            "login attempt until this is fixed.")
```
```xml
<!-- configure.zcml, alongside the existing userCreatedHandler subscriber -->
<subscriber
    for="zope.processlifetime.IProcessStarting"
    handler=".subscribers.on_process_starting"
    />
```

### Fail-closed test shape (both enrollment and validation, both missing and garbage key)

```python
# Follows Phase 1's established pattern: inject the failure via a real collaborator
# (monkeypatch helpers.get_encryption_key), not by monkeypatching the method under test.
import os
import unittest2 as unittest

from imio.googleauthenticator import helpers


class TestFailClosed(unittest.TestCase):

    def test_decrypt_seed_refuses_when_key_unset(self):
        original = helpers.get_encryption_key
        helpers.get_encryption_key = lambda: None
        try:
            with self.assertRaises(ValueError):
                helpers.decrypt_seed(u'v1$whatever')
        finally:
            helpers.get_encryption_key = original

    def test_decrypt_seed_refuses_when_key_is_garbage(self):
        original = helpers.get_encryption_key
        helpers.get_encryption_key = lambda: 'not-a-valid-fernet-key'
        try:
            with self.assertRaises(ValueError):
                helpers.decrypt_seed(u'v1$whatever')
        finally:
            helpers.get_encryption_key = original

    # Mirror both tests for encrypt_seed() (enrollment path) and for the full
    # login flow through validate_token()/get_secret() (validation path) --
    # ROADMAP success criterion 2 requires BOTH enrollment and validation
    # covered, not one representative test.
```

### Generating the Fernet key for `[testenv]` / Puppet (DOC-03)

```bash
# One-liner to generate a key value, for the [testenv] fake test value and,
# out of repo, for the real Puppet concat::fragment:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Plaintext base32 seed in a memberdata `string` property | `v1$<fernet-token>` ciphertext, same property, same schema | This phase | No memberdata-schema migration needed — confirmed no enrolled users exist (PROJECT.md) |
| QR seed sent to `chart.googleapis.com` in a GET query string | `qrcode==6.1` rendered in-process, embedded as a `data:` URI | This phase | Removes an external network dependency and a plaintext-seed-in-URL leak entirely |
| `str(uuid4())` (~122 bits) via `rebus.b32encode` | `os.urandom(20)` (160 bits) via stdlib `base64.b32encode` | This phase | Also fixes the `UnicodeDecodeError` crash `rebus.b32encode` has on raw entropy (Pitfall A) |
| `py2-ipaddress>2.0.1` | `ipaddress==1.0.23` | This phase, forced by adding `cryptography` | One fewer dependency; whitelist code now runs on the same `ipaddress` implementation `cryptography` uses |

**Deprecated/outdated:**
- `rebus` as a dependency: its one call site (`generate_secret`) is replaced by stdlib
  `base64.b32encode`; drop it from `install_requires` once nothing else references it (confirmed
  by `grep -rn rebus src/` — one hit, `helpers.py:100`, plus the `setup.py` line).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Environment variable is named `IMIO_GA_SEED_KEY` | Code Examples, Environment Availability | Cosmetic only — a rename before merge is a find-and-replace across `helpers.py`, `subscribers.py`, `base.cfg`, and the (out-of-repo) Puppet fragment. No functional risk either way, but the name should be locked in `/gsd-discuss-phase` or by the planner before the Puppet-side ticket is filed, since that repo is out of this milestone's commits and a later rename means a second cross-repo coordination |
| A2 | The reset-form's `reason` variable, and the general "raise `ValueError` from `get_or_create_secret`, let it surface as `_("An unexpected error occurred.")`" is acceptable enrollment-time fail-closed behavior (Pitfall B) | Common Pitfalls (Pitfall B), Open Questions | If the intended fail-closed contract requires a *distinguishable* enrollment failure message (not the generic "unexpected error"), the existing bare `except Exception:` in `user_setup.py`'s `handleSubmit` needs to special-case `ValueError` from the secret helpers before this phase's fail-closed test can pass as literally worded by the ROADMAP |
| A3 | `data:image/png;base64,...` embedding is acceptable for the QR image (vs. a dedicated BrowserView) | Architecture Patterns, Alternatives Considered | Low risk — functionally equivalent and smaller attack surface; only matters if a future requirement needs the QR image independently cacheable or fetchable outside the enrollment page render |

## Open Questions

1. **Does an exception raised inside `SetupForm.updateFields()` (via `get_token_description()` →
   `get_or_create_secret()` → `generate_secret()` → `encrypt_seed()`, on a missing/garbage key)
   propagate to a 500, or does `z3c.form`'s form-update lifecycle swallow it?**
   - What we know: reading `z3c.form-3.7.1`'s `form.py` `update()`/`__call__()` shows no
     surrounding `try/except` around `updateWidgets()`/`updateFields()` in the base classes this
     package uses (`form.SchemaForm`, `AutoExtensibleForm`). No pin for `z3c.form` exists in
     `test-4.3.cfg`, so the resolved version should be confirmed once `bin/buildout` runs.
   - What's unclear: whether `plone.autoform.form.AutoExtensibleForm` (which composes the
     `updateFields` hook this package overrides) wraps field-description construction in its own
     try/except — not traced in this session.
   - Recommendation: write the enrollment-side fail-closed test first (before assuming the
     propagation works) and observe the actual response; if it is swallowed, the fix is likely a
     one-line `raise` in `user_setup.py`'s bare `except Exception:` for `ValueError` specifically
     (re-raise rather than convert to a generic message), or moving the `get_or_create_secret`
     call earlier in `handleSubmit` where the existing try/except already exists deliberately.

2. **Should the `data:` URI embedding change the existing `IStatusMessage`/error-handling shape
   around `get_token_description()` calls, given it can now raise where it never could before?**
   - What we know: both `user_setup.py`'s `updateFields()` and `reset_bar_code.py`'s
     `updateFields()` call `get_token_description()` outside any try/except today.
   - What's unclear: whether an uncaught `ValueError` there is acceptable (arguably yes — it is
     the fail-closed behavior SEC-03 wants) or whether it needs a friendlier operator-facing
     message than a bare Zope 500 traceback page.
   - Recommendation: match Phase 1's decision on this exact tradeoff (a plain 500, no custom
     error view, revisited "in Phase 3, where fail-closed-on-missing-key lands on the same path" —
     `01-CONTEXT.md` deferred item). This phase is that revisit; the discretion is available but
     the default (plain 500) is already the documented fallback if no richer message is built.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `cryptography` (cp27 wheel) | Fernet encryption (SEC-01) | Not yet installed in this dev sandbox's `bin/python` — no built buildout present here (`make setup` not yet run in this workspace) | target `3.3.2` | none — this is the phase's core dependency; `make buildout` must succeed with it pinned |
| `qrcode` (py2.py3 wheel) | Local QR (SEC-05) | Same as above | target `6.1` | none |
| `ipaddress` (py2.py3 wheel) | Forced by `cryptography` (BUG-05) | Same as above | target `1.0.23` | none |
| `python2.7` interpreter | All of the above; used directly in this research session to reproduce Pitfall A | Available (`/home/cadam/.pyenv/shims/python2.7`, 2.7.18) | 2.7.18 | — |
| `IMIO_GA_SEED_KEY` (or final chosen name) in `[instance]`/`[testenv]` | SEC-02, SEC-03, SEC-07 | Not yet added to `base.cfg` | — | none for production; tests must set an obviously-fake value themselves per the phase notes |
| Puppet `concat::fragment` in the separate `industrialisation` repo | Real deployment of the key (SEC-07) | Out of repo, out of this milestone's commits (tracked explicitly in ROADMAP.md "External Dependency") | — | Code lands and is fully tested here without it; the feature is not *deployable* until that Puppet change ships — do not let this block merging Phase 3's code |

**Missing dependencies with no fallback:** `cryptography==3.3.2`, `qrcode==6.1`,
`ipaddress==1.0.23` must all resolve and build successfully the first time `bin/buildout` runs
after this phase's `setup.py`/`test-4.3.cfg` edits — this is not yet verified in this specific
workspace (no built `bin/` present), though it was verified in a prior session's buildout per
STACK.md. Re-run `bin/buildout -c test-4.3.cfg` early in the phase to catch any drift.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` via `bin/test` (buildout-generated), `unittest2` |
| Config file | none dedicated — driven by `test-4.3.cfg` + `base.cfg` `[test]`/`[testenv]` |
| Quick run command | `bin/test -t test_helpers` (or `-t "helpers"` per Makefile's documented pattern) |
| Full suite command | `bin/test -t '!robot'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-01 | Seed stored as `v1$<fernet-token>`, never plaintext | unit | `bin/test -t test_helpers` | ❌ new tests in `test_helpers.py` |
| SEC-02 | Key read per-call, never persisted | unit | `bin/test -t test_helpers` | ❌ new |
| SEC-03 | Enrollment refused (missing key, garbage key) | unit | `bin/test -t test_helpers` | ❌ new |
| SEC-03 | Validation/login refused (missing key, garbage key) | integration | `bin/test -t test_pas_plugin` or `test_helpers` | ❌ new |
| SEC-04 | Ciphertext carries `v1$` prefix | unit | `bin/test -t test_helpers` | ❌ new |
| SEC-05 | QR renders in-process; no external call | unit | `bin/test -t test_helpers` (assert `get_barcode_image` returns a `data:` URI, contains no `googleapis.com`) | ❌ new |
| SEC-06 | Seed is 160 bits, decodable by `onetimepass` | unit | `bin/test -t test_helpers` (assert `len(base64.b32decode(seed)) == 20` and a real `get_hotp` round-trip) | ❌ new |
| SEC-08 | CRITICAL log at process start when key absent | unit (subscriber called directly with a stub event; no full Zope boot needed) | `bin/test -t test_subscribers` or a new class in `test_setuphandlers.py` | ❌ new |
| BUG-02 | `redirect_url` bound on every path | unit | `bin/test -t test_generic` or a new `test_user_setup.py` | ❌ new (regression, not a fix — Pitfall B) |
| BUG-03 | Constant-time, type-safe reset-token comparison | unit | `bin/test -t test_generic` or new `test_reset_bar_code.py` | ❌ new |
| BUG-05 | `ipaddress==1.0.23` whitelist still matches | integration (existing) | `bin/test -t test_helpers` (`TestIPWhitelisting`, already present) | ✅ existing — extend, don't replace |

### Sampling Rate

- **Per task commit:** `bin/test -t test_helpers` (fastest feedback for the encryption/QR/
  ipaddress work, which all lives in `helpers.py`)
- **Per wave merge:** `bin/test -t '!robot'`
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus a manual
  `bin/buildout -c test-4.3.cfg` confirming the new pins resolve and build cleanly (this has not
  yet been executed against the edited config in this workspace)

### Wave 0 Gaps

- [ ] No test file yet asserts a real `generate_secret()`/`decrypt_seed()` round-trip decodes via
      `onetimepass.get_hotp` (the test that would have caught Pitfall A) — write this before any
      mock-based encryption test, per the "verify negative claims" philosophy
- [ ] No existing test drives `IProcessStarting` — a stub-event unit test calling
      `subscribers.on_process_starting(event)` directly (no full Zope boot) covers SEC-08 cheaply
- [ ] Confirm `bin/buildout -c test-4.3.cfg` succeeds with the four new/changed pins before
      writing any test that depends on them being importable

*(Framework itself is not a gap — `zope.testrunner`/`bin/test` already covers every layer this
phase needs; only the specific new test cases are missing.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | TOTP seed confidentiality is the entire point of this phase; `cryptography.fernet.Fernet`, never a hand-rolled cipher |
| V3 Session Management | no (unchanged this phase) | — |
| V4 Access Control | partial | The QR data-URI is embedded only inside the already-permission-checked `SetupForm`/`ResetBarCodeForm` render path (`api.user.is_anonymous()` checks already present); no new endpoint, no new access-control surface |
| V5 Input Validation | yes | Ciphertext version-prefix check (`v1$`) before attempting decrypt; key format validated (`ValueError`/`TypeError` both caught) before use |
| V6 Cryptography (Stored Cryptography Verification Requirements, ASVS 6.2) | yes | Fernet (AES-128-CBC + HMAC-SHA256, authenticated) — never a hand-rolled scheme; key never in ZODB, memberdata, logs, or exception messages (V6.4.1-equivalent: no secrets in logs) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| TOTP seed readable from a ZODB dump / backup | Information Disclosure | Fernet encryption at rest (SEC-01); key lives only in process environment, never in the database that is being read |
| Seed leaked via subprocess argv (`ps`, `/proc/<pid>/cmdline`) to any local user | Information Disclosure | In-process `qrcode` rendering — no subprocess ever invoked for QR generation (SEC-05) |
| Encryption silently downgrading to plaintext (or to password-only login) when the key is broken | Elevation of Privilege (silent security-control removal) | Fail-closed: `encrypt_seed`/`decrypt_seed` raise and are never caught locally; `_dont_swallow_my_exceptions=True` (Phase 1) turns that into a loud 500, never a bypass |
| Reset-token comparison timing oracle | Information Disclosure (side-channel) | `hmac.compare_digest`, both operands encoded to the same type first (Pitfall C) |
| `ipaddress` module-shadowing silently disabling the IP whitelist on one deployment but not another | Tampering / inconsistent security posture across hosts | Explicit dependency swap (`py2-ipaddress` removed, `ipaddress==1.0.23` pinned) rather than relying on `sys.path` egg-ordering luck |
| Encryption key logged or echoed in an error message | Information Disclosure | `_get_fernet()`'s error messages name the env var, never its value; no `logger.*` call anywhere touches `get_encryption_key()`'s return value |
| A new QR-serving endpoint disclosing another user's seed via a manipulated request parameter | Information Disclosure / Access Control | Not built — the data-URI approach embeds the image only for `api.user.get_current()` inside the already-permission-checked form render (Anti-Patterns) |

## Sources

### Primary (HIGH confidence)

- Executed directly in this session: `rebus-0.2-py2.7-linux-x86_64.egg`'s `encode()` source
  (`/srv/cache/eggs/rebus-0.2-py2.7-linux-x86_64.egg/rebus/__init__.py`), reproduced failing
  against `os.urandom(20)` on this repo's own `python2.7` (2.7.18) — 5/5 trials
- Executed directly in this session: stdlib `base64.b32encode(os.urandom(20))` round-trip,
  confirmed exact-length no-padding output and successful `b32decode`
- Read directly: `onetimepass-0.2.2`'s `__init__.py` source (via a locally cached wheel path
  metadata check) — confirms `get_hotp` calls `base64.b32decode(secret, casefold=casefold)`
- Read directly, this repo's own source tree: `helpers.py`, `pas_plugin.py`, `setuphandlers.py`,
  `adapter.py`, `userdataschema.py`, `browser/controlpanel.py`, `browser/forms/{user_setup,
  reset_bar_code, request_bar_code_reset, token}.py`, `configure.zcml`, `browser/configure.zcml`,
  `testing.py`, `tests/{base.py,test_helpers.py,test_pas_plugin.py}`, `memberdata_properties.xml`
- Read directly: `Products.PloneMeeting-4.2.28.9`'s `events.zcml`/`events.py` (installed egg in
  this exact stack's cache) for the `IProcessStarting` subscriber ZCML shape and handler
  signature; `zope.processlifetime-1.0` egg confirmed present; `ZServer-4.0.2`'s
  `EGG-INFO/requires.txt` confirms `zope.processlifetime` is already transitively available
- Read directly via `gh api`: `IMIO/gha-workflows`'s `package-test-legacy.yml` full source,
  confirming no generic env-var passthrough exists to the composite test action
- `.planning/research/STACK.md` and `.planning/research/PITFALLS.md` — this project's own prior
  HIGH-confidence, execution-verified research (cryptography 3.3.2 Fernet API/exceptions, the
  `ipaddress`/`py2-ipaddress` collision, `qrcode==6.1` PNG/SVG rendering) — reused, not
  re-derived, per this session's research priorities
- `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`
  — locked decisions and requirement text for this phase
- `.planning/phases/02-registry-seeding-and-import-step-ordering/02-CONTEXT.md`, `02-PATTERNS.md`
  — Phase 2's `get_ska_secret_key`/netstring-join shape this phase builds on without re-deriving
- `.planning/phases/01-rename-and-fail-closed/01-CONTEXT.md` — the "plain 500, no custom error
  view, revisit in Phase 3" deferred decision this phase's Open Question 2 answers

### Secondary (MEDIUM confidence)

- `z3c.form-3.7.1-py2.7.egg`'s `form.py` `update()`/`__call__()` read to check for exception
  swallowing around `updateFields()` — base class shows none, but `plone.autoform`'s
  `AutoExtensibleForm` (which actually implements the overridden hook) was not itself traced;
  see Open Question 1
- WebSearch corroboration that `zope.processlifetime.IProcessStarting` "is triggered after the
  component registry has been loaded and Zope is starting up" — used only as a secondary
  confirmation of the primary (installed-egg) source above

### Tertiary (LOW confidence)

- none — every claim above traces to executed code, direct source reads in this exact stack, or
  this project's own prior HIGH-confidence research

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions and APIs reused from prior execution-verified research
  (STACK.md), cross-checked again where this session had reason to (rebus, onetimepass)
- Architecture: HIGH — every call site read directly from the current source tree, not inferred
- Pitfalls: HIGH for A/B/C/E/F (all executed or directly read); MEDIUM for D (reasoning sound,
  not yet executed against a real Fernet token)

**Research date:** 2026-07-30
**Valid until:** 30 days for the stack pins (stable, py2.7-frozen ecosystem, unlikely to move);
re-verify immediately if `bin/buildout` is run in a workspace that has not yet built this
buildout, since none of the four new/changed pins have been resolved in *this* workspace
specifically (only in the STACK.md research session's environment)

---
*Phase: 3-Encrypted Seeds and Local QR*
*Research completed: 2026-07-30*
