# Stack Research

**Domain:** TOTP second factor inside a frozen Plone 4.3 / Python 2.7.18 PAS plugin
**Researched:** 2026-07-28
**Confidence:** HIGH

## Verification Method

Every version claim and every API claim below was verified one of two ways. Nothing here comes
from recall.

1. **Executed** in this repo's own interpreter, `/srv/src/imio.googleauthenticator/bin/python`
   (Python 2.7.18, GCC 13.2.0), against the actual eggs in `/srv/cache/eggs/`. Where output is
   quoted, it is real output.
2. **PyPI release metadata** — the `/pypi/<pkg>/json` endpoint, filtered for files whose
   filename carries a `cp27` ABI tag or whose `python_version` is `py2.py3`, then sorted by
   version. The "ceiling" for a package is the newest release that still published such a file.
   Upload dates are included so the claim is falsifiable.

Two claims are labelled MEDIUM below and say so explicitly. Everything else is HIGH.

## Bottom Line

Four of the six capabilities need **no new dependency at all** — Python 2.7.18's standard
library covers them. `cryptography==3.3.2` is confirmed good and is the only genuinely new
runtime dependency worth taking, plus `qrcode==6.1` for QR (or `imio.helpers`, see below).

**One blocking discovery:** adding `cryptography` pulls in the `ipaddress` backport, which
collides with the `py2-ipaddress` this package already uses and **breaks login for every user**
in a way that depends on `sys.path` ordering. This is not optional cleanup; it must be handled
in the same phase that introduces encryption. Details in
[The `ipaddress` Collision](#the-ipaddress-collision-blocking).

## Recommended Stack

### Core Technologies (new runtime dependencies)

| Technology | Version | Purpose | Why this version is the ceiling |
|------------|---------|---------|-----------------|
| `cryptography` | `== 3.3.2` | Fernet symmetric encryption of TOTP seeds | Last release publishing a `cp27` wheel — `cryptography-3.3.2-cp27-cp27m-*.whl`, uploaded 2021-02-07, `Requires-Python: >=2.7,!=3.0.*…`. The next release, 3.4, moved to `>=3.6` **and** introduced the Rust build requirement. Already pinned and building at `server.dmsmail/versions-base.cfg:219`. Verified importable and functional in this venv. |
| `ipaddress` | `== 1.0.23` | Hard dependency of `cryptography` on py2 | Final release (2019-10-18); the module is stdlib from py3.3 so the backport stopped. **Replaces `py2-ipaddress`** — see the collision section. |
| `qrcode` | `== 6.1` | Local QR generation | Last py2-compatible release: `qrcode-6.1-py2.py3-none-any.whl`, 2019-01-14. 7.0 is py3-only. Verified working — installed into a scratch dir and rendered a real `otpauth://` PNG under this interpreter. |

`enum34 == 1.1.10`, `six == 1.16.0` and `cffi == 1.15.1` are also required by `cryptography` on
py2. The first two are **already pinned** in `test-4.3.cfg` (lines 22, 55). `cffi` is not
pinned yet and must be added.

Verified dependency set, read from the installed distribution rather than assumed:

```
$ pkg_resources.get_distribution('cryptography').requires()
['cffi>=1.12', 'enum34', 'ipaddress', 'six>=1.4.1']
```

### Standard Library — Use These, Add Nothing

Four of the six capabilities need no dependency. All four confirmed present in this interpreter.

| Capability | Use | Verified |
|---|---|---|
| Hash recovery codes | `hashlib.pbkdf2_hmac` | `hasattr(hashlib, 'pbkdf2_hmac') → True`. Landed in 2.7.8; this is 2.7.18. |
| Constant-time compare | `hmac.compare_digest` | `hasattr(hmac, 'compare_digest') → True`. Landed in 2.7.7. |
| Generate recovery codes / salts | `os.urandom` + `base64.b32encode` | `base64.b32encode(os.urandom(5))` → `'DINIL2II'` — 8 chars, 40 bits, no ambiguous characters. |
| Which TOTP window a code belongs to | `int(time.time()) // 30` | Trivially correct; matches `onetimepass`'s own internal computation exactly (see its `get_totp`). |

### Development Tools

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| `coverage` | `== 5.5` | Coverage measurement + the >90% gate | Last `cp27` wheel: `coverage-5.5-cp27-cp27m-*.whl`, 2021-02-28, `Requires-Python: >=2.7,…,<4`. 6.0 requires py3.6+. `--fail-under` and `--precision` both confirmed present. Egg already in `/srv/cache/eggs/coverage-5.5-py2.7-linux-x86_64.egg`. |
| `createcoverage` | — | **Delete it** | Redundant. See [Coverage](#coverage-to-90). |

## Exact APIs, Per Capability

### 1. Seed encryption at rest — Fernet

Verified by execution against `cryptography 3.3.2`:

```python
from cryptography.fernet import Fernet, InvalidToken

key = Fernet.generate_key()   # -> str (py2 bytes), len 44
                              #    e.g. 'smPMD98Zdr8N1oZN9EV4Pe5Lq9O5LTk0XL1xCTin27U='
f = Fernet(key)
token = f.encrypt(b'JBSWY3DPEHPK3PXP')   # -> str, len 120 for a 16-byte seed
f.decrypt(token)                          # -> 'JBSWY3DPEHPK3PXP'
```

**The injected key is used raw. `PBKDF2HMAC` is not needed.** Generate the key once with
`Fernet.generate_key()`, hand the 44-character string to Puppet, read it with `os.getenv()`, pass
it straight to `Fernet()`. A KDF would only be needed if the env var held a human-chosen
passphrase, and there is no reason to make it one. `PBKDF2HMAC` *is* importable from
`cryptography.hazmat.primitives.kdf.pbkdf2` in 3.3.2 if that ever changes.

**Bytes discipline — this bites on py2.** `Fernet()` and `decrypt()` both reject `unicode`:

| Input | Result |
|---|---|
| `Fernet(str_key)` | works |
| `Fernet(unicode_key)` | `TypeError: character mapping must return integer, None or unicode` |
| `f.decrypt(unicode_token)` | `TypeError` |

`os.getenv()` returns `str` on py2, so the key path is safe as written. The *token* path is the
risk: it round-trips through a Plone memberdata property, and Plone coerces freely between
`str` and `unicode`. Fernet tokens are pure ASCII (URL-safe base64 plus `=` padding), so the fix
is one call at each boundary — `.encode('ascii')` before `decrypt`, `.decode('ascii')` before
storing. Do not skip this; it will pass a unit test that uses `str` and fail in a live site.

**Exception types, all confirmed by execution:**

| Failure | Raised |
|---|---|
| Wrong key, or tampered token | `cryptography.fernet.InvalidToken` |
| Garbage / non-token input | `TypeError` |
| Key is valid base64 but not 32 bytes | `ValueError: Fernet key must be 32 url-safe base64-encoded bytes.` |
| Key is not valid base64 | `TypeError: Incorrect padding` |

Note the last one: on py2, `binascii` raises `TypeError`, **not** `ValueError`. Key-validation
code at startup must catch `(ValueError, TypeError)` or a misconfigured env var produces a bare
`TypeError` instead of a readable "your key is malformed" message.

Also present in 3.3.2 and worth knowing: `f.extract_timestamp(token)`, and
`MultiFernet([new, old]).rotate(token)` — a working key-rotation path, should a key ever leak.
`decrypt(token, ttl=...)` also exists, but is not useful here: a seed has no expiry.

### 2. Recovery codes — stdlib only

```python
import os, base64, hashlib, hmac

def make_codes(n=10):
    # 40 bits each; base32 avoids 0/O and 1/I confusion when read off a screen
    return [base64.b32encode(os.urandom(5)) for _ in range(n)]

salt = os.urandom(16)                      # ONE salt per user, stored beside the hashes
def hash_code(code, salt):
    return hashlib.pbkdf2_hmac('sha256', code, salt, 100000)
```

**Iteration count: 100 000.** Measured on this hardware:

| Iterations | Time |
|---|---|
| 20 000 | 0.020 s |
| 100 000 | 0.113 s |
| 260 000 | 0.273 s |

100 000 costs 0.113 s, which is invisible in a recovery flow that runs once per lost phone.
Note that the codes are 40-bit random values, not human passwords — cryptographically a single
SHA-256 would already be sufficient, because there is no dictionary to walk. The iterations are
cheap insurance against someone later shortening the codes for "usability".

**Use one salt per user, not one per code.** With a shared per-user salt you hash the submitted
code **once** and compare the result against all N stored hashes. With per-code salts you must
run PBKDF2 N times per attempt — 10 codes × 0.113 s = 1.1 s on a login-adjacent endpoint, which
is a denial-of-service lever handed to an attacker. A per-user salt still defeats cross-user
rainbow tables, which is the only thing salts are for here.

Verification, and single-use consumption:

```python
candidate = hash_code(submitted, salt)
match = next((h for h in stored_hashes if hmac.compare_digest(h, candidate)), None)
if match is not None:
    stored_hashes.remove(match)   # single-use: persist the shortened list
```

`hmac.compare_digest` behaviour on py2, verified by execution:

| Comparison | Result |
|---|---|
| `str` vs `str` | works |
| `unicode` vs `unicode` | works — including non-ASCII |
| `str` vs `unicode` | `TypeError: 'unicode' does not have the buffer interface` |

So it is constant-time for both types but **will not compare across them**. Encode both sides
before calling. This applies equally to the existing bug at `reset_bar_code.py:104`, where the
reset token arrives from the request (`unicode`) and the stored value is a memberdata `string`
(`str`) — a naive `compare_digest` swap there raises `TypeError` on every request. Encode first.

Since PBKDF2 output is raw bytes, either store `binascii.hexlify(...)` in a `lines` memberdata
property or keep the raw bytes; hex is friendlier to a property that Plone may treat as text.

### 3. TOTP replay rejection — what `onetimepass 0.2.2` actually gives you

I read the installed source at
`/srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py`.

**`valid_totp` cannot support replay detection.** Its entire body is:

```python
return _is_possible_token(token) and int(token) == get_totp(secret)
```

It returns a bool. It tells you nothing about which window matched.

**But nothing needs to be computed by hand.** `onetimepass` exports `get_hotp`, which takes the
interval number directly, and that is the missing primitive:

```python
import time
from onetimepass import get_hotp

def matched_window(token, secret, drift=1):
    """Return the interval number the token belongs to, or None."""
    now = int(time.time()) // 30
    for i in range(now - drift, now + drift + 1):
        if get_hotp(secret, intervals_no=i, as_string=True) == token:
            return i
    return None
```

Verified by execution — `matched_window` returned `59507657` for the current window's code,
`59507656` for the previous window's, and `None` for a code from five windows ago. Replay
rejection is then: store the returned integer in a memberdata property and refuse any login
whose `matched_window` is `<=` the stored value.

Two things the source review turned up that the roadmap should know:

- **`valid_totp` has zero clock-drift tolerance.** It compares against the current window only.
  A user submitting a code that was valid when they read it, one second before the window
  rolled, is rejected today. Replacing it with `matched_window(..., drift=1)` fixes an existing
  usability bug for free, and the replay counter is what makes widening the window safe.
- **Do not use `valid_hotp` for this.** It returns an interval, which looks tempting, but it
  scans *forward* from `last + 1` with `trials=1000` by default. It cannot see the previous
  window, and it would accept a code valid over eight hours in the future.

`_is_possible_token` also rejects anything longer than 6 digits, so recovery codes must take a
separate code path — which they do anyway.

`onetimepass` stays. PROJECT.md already ruled the `pyotp` swap out of scope, and this research
confirms there is no reason to revisit that: the library exposes exactly the primitive needed.

### 4. Failed-attempt lockout — stdlib only

An integer counter and a `float` timestamp in memberdata properties. `time.time()` is the whole
dependency. Nothing to research.

Per PROJECT.md's constraint this state lives in memberdata, not a RAM cache, so it is consistent
across ZEO clients. One note for the plan: memberdata writes on failed attempts mean a
**write transaction on an unauthenticated code path**, which is a ZODB conflict-error surface if
one account is attacked concurrently. Not a stack decision, but it belongs in PITFALLS.

### 5. QR code generation — two viable routes

PROJECT.md has already decided on `imio.helpers` + `zint` type 58. That works, and I confirmed
the mechanics. But the verification turned up a leak in it that the roadmap should see before
committing, because the entire point of this change is to stop leaking the seed.

Confirmed for the zint route:
- `zint 2.13.0` is installed at `/usr/local/bin/zint`; `zint -t` confirms **`58 QRCODE`**.
- `imio.helpers 1.3.15` ships `barcode.generate_barcode(data, barcode=92, ...)` returning a
  `BytesIO`; it invokes `subprocess.Popen` with an argument **list**, so there is no shell and
  no shell-injection surface.

**The leak: the seed lands in the process argv.** `generate_barcode` passes the payload as
`--data=otpauth://totp/...?secret=<SEED>`, which is visible in `ps` and `/proc/<pid>/cmdline`
to any local user on the Zope host for the lifetime of the subprocess. That is far better than
posting the seed to `chart.googleapis.com`, but it is not nothing, and it is avoidable. I tested
`--input=/dev/stdin` as a workaround: zint rejects it (`Error 79`), so the only alternatives are
argv or a temp file on disk.

**Recommendation: `qrcode == 6.1`.** It renders in-process — no subprocess, no argv, no temp
file, no leak — and I verified it under this exact interpreter:

```python
import qrcode, io
img = qrcode.make('otpauth://totp/Plone:bob?secret=JBSWY3DPEHPK3PXP&issuer=Plone')
buf = io.BytesIO(); img.save(buf, 'PNG')   # 848 bytes, magic '\x89PNG'
```

`Pillow` is already in `base.cfg:27`, so the PNG path adds nothing. There is also a pure-Python
SVG factory needing no Pillow at all (`qrcode.image.svg.SvgPathImage`, verified: 14 583 bytes
of valid SVG), if avoiding the imaging stack in a view is preferable.

The trade is one small new pinned egg (`qrcode==6.1`, pure Python, single module) against
`imio.helpers`, which is Puppet-deployed but is a large Plone add-on carrying its own dependency
tree into a package that currently does not depend on it. Both are defensible; `qrcode` is the
smaller change and the one without the argv leak. **This decision is the roadmap's to make** —
PROJECT.md's reasoning ("the helper and the `zint` binary already exist") is sound, it simply
predates the argv finding. If the zint route is kept, note the leak as an accepted risk rather
than leaving it undiscovered.

### 6. Coverage to >90%

`coverage == 5.5`. Add it to `test-4.3.cfg` `[versions]`, replacing the commented-out
`#coverage = 4.5.1` at line 68. Nothing in the buildout chain pins `coverage` — I fetched
`buildout.plonetest/qa.cfg` and confirmed it defines a `[createcoverage]` part and a
`[coverage-sh]` script but sets **no** `coverage` version. The `4.2` currently resolved
(visible in `bin/createcoverage`'s `sys.path`) is just free resolution, so an explicit pin takes
effect cleanly.

`--fail-under=90` works. Confirmed by introspecting `coverage.cmdline.Opts` under 5.5: both
`fail_under` and `precision` are present. So `base.cfg:89`'s existing
`coverage report -m --fail-under=90` needs no change.

Coverage 5.x stores its data file as SQLite rather than the 4.x pickle. `sqlite3` imports fine
in this venv (SQLite 3.45.1), so this is a non-issue — but it does mean a stale `.coverage`
file from a 4.x run must be deleted once, or the first 5.5 run errors on an unreadable file.

**Delete `createcoverage`.** There are currently three coverage mechanisms in play:
`createcoverage` (active in `base.cfg:17`), `coverage-sh` (inherited from `qa.cfg`, not in
`parts`), and `[coverage]` + `[test-coverage]` (defined in `base.cfg:78-92`, commented out of
`parts`). Only the third enforces the 90% threshold this milestone needs. Enable it, drop
`createcoverage` from `parts` and drop `createcoverage = 1.5` from the pins. `createcoverage`
declares only `coverage>=3.7` (verified) so it does not constrain the upgrade — it is simply
redundant.

`.coveragerc` needs two changes beyond the rename:

```ini
[run]
source = src/imio/googleauthenticator

[report]
omit = */tests/*
show_missing = True
```

The current file has only `[report] include = src/collective/googleauthenticator/*`. As written,
test modules are counted in the denominator, which inflates the percentage — a package can clear
`--fail-under=90` on the strength of its own test files. Omitting `*/tests/*` makes the 90% mean
what the milestone intends.

## The `ipaddress` Collision (BLOCKING)

**This is the one finding that changes the plan.** It is verified by execution, not inferred.

`cryptography 3.3.2` requires the `ipaddress` backport. This package currently depends on
`py2-ipaddress>2.0.1` (`setup.py:62`, resolved to `3.4.2`). **Both distributions install a
top-level module named `ipaddress`** — confirmed on disk at
`/srv/cache/eggs/py2_ipaddress-3.4.2-py2.7-linux-x86_64.egg/ipaddress.py`. They cannot coexist;
whichever egg comes first on `sys.path` wins.

Their APIs diverge on exactly the call this package makes. Verified by running each in isolation:

| Call | `py2-ipaddress 3.4.2` | `ipaddress 1.0.23` |
|---|---|---|
| `ip_address('192.168.1.1')` (str) | `192.168.1.1` | **`AddressValueError`** |
| `ip_address(u'192.168.1.1')` | `192.168.1.1` | `192.168.1.1` |
| `ip_network('10.0.0.0/8')` (str) | `10.0.0.0/8` | **`AddressValueError`** |
| `ip_network(u'10.0.0.0/8')` | `10.0.0.0/8` | `10.0.0.0/8` |

And the race is real — with both eggs on the path, order alone decides:

```
PYTHONPATH=py2_ipaddress:ipaddress  -> py2_ipaddress-3.4.2 wins
PYTHONPATH=ipaddress:py2_ipaddress  -> ipaddress-1.0.23 wins, ip_address(str) raises
```

**Consequence if unhandled: total login failure.** `helpers.py:459` is
`return ipaddress.ip_address(ip)` where `ip = request.get('REMOTE_ADDR')` — a `str` in Zope. The
`AddressValueError` is not caught in `extract_ip_address_from_request`, so it propagates through
`is_whitelisted_client` into the PAS plugin. Every login attempt raises. And because it is
decided by egg ordering, it can work on a developer machine and fail on a Puppet-built one.

**Fix — do this in the same phase that introduces `cryptography`:**

1. Remove `py2-ipaddress>2.0.1` from `setup.py` `install_requires`; add `ipaddress`.
2. Remove `py2-ipaddress = 3.4.2` from `test-4.3.cfg`; add `ipaddress = 1.0.23`.
3. Coerce to `unicode` at both call sites — `ipaddress.ip_address(ip.decode('ascii'))` at
   `helpers.py:459`, and the same for each `net` in `get_ip_ranges` at `helpers.py:496`.
4. `tests/test_helpers.py:8-9` imports `IPv4Network` / `IPv4Address`, which exist in both, so
   those imports are fine — but any test feeding a `str` literal needs a `u` prefix.

Net effect: one fewer dependency, and the whitelist now runs on the same `ipaddress`
implementation `cryptography` uses. PROJECT.md files `py2-ipaddress` under "parks every concern
whose only real fix is Python 3" — that classification is wrong here. This is not a Python 3
problem, it is a straight swap, and adding `cryptography` forces it.

## Installation

Add to `setup.py` `install_requires`:

```python
'cryptography',
'ipaddress',        # replaces py2-ipaddress
'qrcode',           # only if the qrcode route is chosen over imio.helpers
```

Remove: `'py2-ipaddress>2.0.1'`.

Add to `test-4.3.cfg` `[versions]`:

```ini
# py2.7 ceilings — see .planning/research/STACK.md for why each is the last release
cryptography = 3.3.2
cffi = 1.15.1
ipaddress = 1.0.23
qrcode = 6.1
coverage = 5.5
```

Remove: `py2-ipaddress = 3.4.2`, `createcoverage = 1.5`, and the commented `#coverage = 4.5.1`.
Already pinned and correct: `enum34 = 1.1.10` (line 55), `six = 1.16.0` (line 22).

`base.cfg` — uncomment `coverage` and `test-coverage` in `parts` (lines 19-20), remove
`createcoverage` (line 17).

## Alternatives Considered

| Recommended | Alternative | When the alternative wins |
|-------------|-------------|-------------------------|
| `cryptography==3.3.2` Fernet | `pycryptodome` | Only if `cryptography` could not build. It can — the `cp27` wheel exists and the egg is already built here. Fernet also bundles AES-CBC + HMAC authentication and a versioned token format; hand-rolling that on a raw AES primitive is exactly where seed encryption goes wrong. |
| `cryptography==3.3.2` Fernet | `ska` (already a dependency) | Never. `ska` signs, it does not encrypt. Reusing it for confidentiality would be a category error. |
| raw injected Fernet key | `PBKDF2HMAC` over a passphrase | Only if operations insist on a human-typed secret. There is no reason to — `Fernet.generate_key()` output travels through Puppet exactly as `SSO_APPS_CLIENT_SECRET` already does. |
| `qrcode==6.1` | `imio.helpers` + `zint` type 58 | If avoiding a new pinned egg matters more than keeping the seed out of process argv, or if a future need for other barcode symbologies makes the helper pay for itself. |
| stdlib `hashlib.pbkdf2_hmac` | `passlib`, `bcrypt` | Never here. `pbkdf2_hmac` is in 2.7.18 and OpenSSL-backed. Adding a password library to hash ten random 40-bit strings is dependency for its own sake. |
| `coverage==5.5` | `coverage==4.5.1` | Only if the SQLite data-file format caused a problem, which it does not — `sqlite3` is present. |
| `onetimepass` + `get_hotp` | `pyotp` | Never — already out of scope in PROJECT.md, and `get_hotp` provides the window number that replay detection needs. |

## What NOT to Use

| Avoid | Why | Use instead |
|-------|-----|-------------|
| `cryptography >= 3.4` | `Requires-Python: >=3.6`, and 3.4 added a Rust toolchain requirement to the build. Cannot install on 2.7 at any effort. | `cryptography == 3.3.2` |
| `coverage >= 6.0` | Requires py3.6+. | `coverage == 5.5` |
| `qrcode >= 7.0` | Dropped py2. | `qrcode == 6.1` |
| `cffi >= 2.0` | `Requires-Python: >=3.9`. Last `cp27` wheel is 1.15.1 (2022-06-30). | `cffi == 1.15.1` |
| `py2-ipaddress` (any version) | Collides with the `ipaddress` module `cryptography` requires; the winner is `sys.path`-order dependent and the losing case breaks every login. | `ipaddress == 1.0.23` with `unicode` inputs |
| `ska > 1.7.5` | Needs `setuptools>=61` / PEP 517, which cannot install under 2.7. Already correctly pinned at `test-4.3.cfg:29`. | keep `1.7.5` |
| `onetimepass.valid_hotp` for TOTP | Scans forward only from `last+1` with `trials=1000` — cannot see the previous window and would accept codes valid 8+ hours in the future. | `get_hotp(secret, intervals_no=i)` over `now-1 .. now+1` |
| `onetimepass.valid_totp` for the new path | Returns a bare bool, so replay detection is impossible; also has zero drift tolerance. | the `matched_window` helper above |
| A RAM cache for replay / lockout state | Per-instance state lets an attacker multiply attempts by rotating ZEO clients. Already a PROJECT.md constraint; restating because it is the obvious shortcut. | memberdata properties |
| `createcoverage` | Third redundant coverage mechanism; does not enforce a threshold. | `[coverage]` + `[test-coverage]` in `base.cfg` |
| Anything requiring PEP 517 / `setuptools>=61` | `requirements-4.3.txt` pins `setuptools 44.1.1`; PEP 517 builds cannot run. Any candidate dependency publishing only a `pyproject.toml` sdist with no `cp27`/`py2.py3` wheel is unusable, regardless of what its code supports. | check for a `cp27` or `py2.py3` file on PyPI before pinning anything |

## New Memberdata Properties

The state this milestone adds all lives in `profiles/default/memberdata_properties.xml`, which
currently declares three properties. Suggested additions, with the Plone memberdata types:

| Property | Type | Holds |
|---|---|---|
| `two_factor_authentication_secret` | `string` | *existing* — becomes the Fernet token (ASCII, ~120 chars) instead of the plaintext seed |
| `last_totp_interval` | `int` | highest window number already consumed → replay rejection |
| `failed_2fa_attempts` | `int` | consecutive failures → lockout |
| `lockout_until` | `float` | `time.time()` expiry, `0` when not locked |
| `recovery_code_hashes` | `lines` | hex-encoded PBKDF2 digests; entries removed as consumed |
| `recovery_code_salt` | `string` | hex-encoded 16-byte per-user salt |

A Fernet token is longer than the base32 seed it replaces but is still ASCII and still fits a
`string` property with no schema change. Because PROJECT.md confirms nothing is deployed and no
users are enrolled, no upgrade step or re-encryption pass is needed.

## Version Compatibility

| Package | Compatible with | Notes |
|-----------|-----------------|-------|
| `cryptography 3.3.2` | `cffi 1.15.1`, `enum34 1.1.10`, `ipaddress 1.0.23`, `six 1.16.0` | Requirement set read from the installed distribution: `['cffi>=1.12', 'enum34', 'ipaddress', 'six>=1.4.1']`. Import and full Fernet round-trip executed successfully in this venv. |
| `cryptography 3.3.2` | `py2-ipaddress` — **NO** | Module-name collision. Blocking; see above. |
| `coverage 5.5` | py2.7 `sqlite3` | Present (SQLite 3.45.1). Delete any stale 4.x `.coverage` file once. |
| `qrcode 6.1` | `Pillow` (already in `base.cfg:27`) | Verified with `Pillow 6.2.2`. The `SvgPathImage` factory needs no Pillow at all. |
| `onetimepass 0.2.2` | `six` | Only dependency; already pinned. |
| `ska 1.7.5` | py2.7 | Ceiling — later versions need PEP 517. Already pinned. |

## Confidence

| Claim | Level | Basis |
|---|---|---|
| `cryptography` py2 ceiling is 3.3.2 | HIGH | PyPI `cp27` wheel list; last is 3.3.2 (2021-02-07). Egg builds and runs here. |
| Fernet API surface, key format, exception types | HIGH | Executed in this venv; every value and exception name quoted is real output. |
| Raw key works, no KDF needed | HIGH | Executed — `Fernet(Fernet.generate_key())` round-trips. |
| `hashlib.pbkdf2_hmac` present in 2.7.18 | HIGH | Executed: `True`, plus a real digest and timings. |
| `hmac.compare_digest` present, and str/unicode behaviour | HIGH | Executed all four type combinations. |
| `coverage` py2 ceiling is 5.5, `--fail-under` works | HIGH | PyPI `cp27` wheel list; `Opts.fail_under` introspected under 5.5. |
| `onetimepass` exposes the window via `get_hotp` | HIGH | Read the installed source; executed a working `matched_window`. |
| `ipaddress` / `py2-ipaddress` collision breaks login | HIGH | Executed both modules in isolation and both `sys.path` orderings. Call site read at `helpers.py:459`. |
| `qrcode 6.1` is the py2 ceiling and works | HIGH | PyPI wheel list; installed to a scratch dir and rendered PNG + SVG under this interpreter. |
| `zint` type 58 = QR, and the argv leak | HIGH | `zint -t` output; `imio.helpers/barcode.py` source read; `--input=/dev/stdin` tested and rejected. |
| PBKDF2 100 000 iterations is the right count | MEDIUM | Timings are measured here, but "right" is a judgement about a rare flow, and it is calibrated to this machine — a slower production host scales linearly. Any value in 20k–200k is defensible. |
| Suggested memberdata property types | MEDIUM | Types follow Plone 4.3 memberdata conventions and the existing file, but I did not execute a GenericSetup import to confirm `float` and `lines` behave as expected for these fields. Worth a smoke test in the phase that adds them. |

## Sources

- **Executed locally** — `/srv/src/imio.googleauthenticator/bin/python` (2.7.18) against
  `/srv/cache/eggs/`: `cryptography 3.3.2`, `coverage 5.5`, `onetimepass 0.2.2`,
  `py2_ipaddress 3.4.2`, `ipaddress 1.0.23`, `qrcode 6.1`, `Pillow 6.2.2`, plus stdlib
  `hashlib` / `hmac` / `os.urandom` / `sqlite3`. HIGH.
- **PyPI JSON release metadata** — `pypi.org/pypi/{cryptography,coverage,qrcode,cffi,enum34,ipaddress,createcoverage}/json`,
  filtered on `cp27` / `py2.py3` files with upload dates. HIGH.
- **Source read** — `onetimepass/__init__.py` and `imio/helpers/barcode.py` from the installed
  eggs; `helpers.py:440-510` in this repo. HIGH.
- **`zint 2.13.0`** — `zint -t` and `zint --help` on this host. HIGH.
- **`buildout.plonetest/qa.cfg`** — fetched from `raw.githubusercontent.com` to confirm it sets
  no `coverage` pin. HIGH.
- Repo files: `setup.py`, `test-4.3.cfg`, `base.cfg`, `.coveragerc`,
  `profiles/default/memberdata_properties.xml`, `.planning/PROJECT.md`,
  `.planning/codebase/STACK.md`.

---
*Stack research for: TOTP hardening within a frozen Plone 4.3 / Python 2.7.18 stack*
*Researched: 2026-07-28*
