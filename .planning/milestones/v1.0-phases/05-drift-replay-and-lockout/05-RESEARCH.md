# Phase 5: Drift, Replay and Lockout - Research

**Researched:** 2026-07-31
**Domain:** `onetimepass==0.2.2` TOTP semantics; `OFS.PropertyManager`/`Products.PlonePAS` memberdata
property typing and round-trip behaviour; z3c.form button-handler state writes
**Confidence:** HIGH (every mechanical claim below was traced in the exact eggs this buildout
resolves and in this repo's own installed source, not from memory)

<user_constraints>
## User Constraints

No `CONTEXT.md` exists for this phase — `/gsd-discuss-phase` was not run (confirmed: no
`*-CONTEXT.md` file in `.planning/phases/05-drift-replay-and-lockout/`). There is therefore no
`## Decisions` / `## Claude's Discretion` / `## Deferred Ideas` to reproduce verbatim. The binding
inputs are ROADMAP.md's Phase 5 "Phase notes" block (reproduced below, verbatim, as the task
instructed they be treated as locked) and REQUIREMENTS.md's MFA-05..MFA-13 (read in full).

### Locked Decisions (ROADMAP.md Phase 5 "Phase notes", ratified by the launching task)

- **MFA-12 is the invariant this phase is built around:** no second-factor state write in the PAS
  plugin or a challenge plugin, ever. `ZPublisher/Publish.py`'s `finally: transactions_manager.abort()`
  discards every write on any request ending in an exception, and `Unauthorized` *is* such an
  exception. A lockout counter written in the plugin is a security control that does not work and
  looks like it does. The token form POST returns 200/302 → `PubBeforeCommit` → `commit()`, and a
  failed second factor is by definition submitted to the token form.
- **MFA-13 exists because the failure is silent:** an undeclared memberdata property is silently
  dropped with no error. A forgotten `memberdata_properties.xml` entry means the counter never
  persists and nothing appears in the log.
- **Open Decision to settle here:** `memberdata_properties.xml` types for the new counters.
  Smoke-test the GenericSetup import; prefer an `int` epoch over `float`/`date` to avoid `DateTime`
  round-tripping. *(Settled below with source evidence, not just a smoke test — see Code Examples
  "Confirmed property-type validation".)*
- The ConflictError worry is a non-issue: storage is an `OOBTree` keyed by user id, cross-user
  writes merge, and `retry_max_count = 3` handles same-user parallel brute force correctly. The
  hazard to design against is `transaction.abort()`, not ConflictError.
- Control panel follows `imio.dms.mail`'s `RegistryEditForm` + `layout.wrap_form(...,
  ControlPanelFormWrapper)` pattern. *(Evaluated below — see "Alternatives Considered": this
  package already has a working, tested, auto-extensible control panel form and the simplest
  correct move is two new schema fields on the existing interface, not a new form base class.
  Flagged as a recommendation for the planner to confirm, not a re-litigation of the decision to
  make the settings editable.)*
- N=5 / 900 s ≈ 1042 days expected time-to-hit for a 6-digit code; NIST SP 800-63B §5.2.2's 100
  attempts is a ceiling, not a target.

### Claude's Discretion

None recorded (no discuss-phase). Treated as full research discretion within REQUIREMENTS.md's
MFA-05..MFA-13 text and the locked decisions above.

### Deferred Ideas (OUT OF SCOPE)

From REQUIREMENTS.md `## Out of Scope`, relevant to this phase: progressive backoff, CAPTCHA,
8-digit OTP, adaptive/geo MFA ("gold-plating for a package with a 2-year life"); admin-unlock-only
lockout (a DoS primitive); `onetimepass` → `pyotp` migration (unnecessary, `get_hotp` already
exposes what's needed). NOTF-01 (email on lockout) is v2, explicitly acknowledged and not in this
milestone.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MFA-05 | A TOTP code from the immediately preceding time step is accepted (RFC 6238 §6 drift) | `get_hotp(secret, intervals_no=i)` for `i in (current, current-1)` — confirmed exact signature/semantics against the installed `onetimepass==0.2.2` source; see Code Examples |
| MFA-06 | A consumed code is rejected on reuse (RFC 6238 §5.2 MUST NOT), rejection logged without plaintext username | Store the matched interval number (not a code list) as a memberdata property; reject if the newly-matched interval `<=` the stored one; log with no user-identifying field at all (simplest way to satisfy "no plaintext username") |
| MFA-07 | Only exactly-6-digit input is a candidate token | **Research correction:** the `_is_possible_token` the roadmap names is not in this codebase — it is `onetimepass`'s own internal function and accepts `isdigit() and len<=6`. It cannot be patched or overridden. This package must add its own `len(token) == 6` gate in `helpers.py`, checked before any `onetimepass`/`get_hotp` call |
| MFA-08 | 5 consecutive failures lock the account for 900s; lock checked before token, locked answer indistinguishable from wrong-code | Lock check (`locked_until > now`) must run and short-circuit **before** `validate_token` is even called, in `browser/forms/token.py::handleSubmit` only |
| MFA-09 | Lock expires on its own, no admin action | A plain epoch-seconds comparison (`now >= locked_until`); no separate "unlock" code path needed, expiry is implicit in the comparison |
| MFA-10 | N and duration editable in control panel, defaulting to 5 / 900 | Two new `zope.schema.Int` fields on the existing `IGoogleAuthenticatorSettings` interface; no `registry.xml` edit needed (see Architecture Patterns) |
| MFA-11 | Successful second factor resets the failure counter | `browser/forms/token.py::handleSubmit`'s success branch zeroes `two_factor_authentication_failed_attempts` |
| MFA-12 | No second-factor state write in the PAS plugin or a challenge plugin, ever | `pas_plugin.py` and `subscribers.py` are unchanged by this phase; all new `setMemberProperties` calls are confined to `browser/forms/token.py` (and, if the planner extends scope, the other two `validate_token` call sites — see Open Questions) |
| MFA-13 | Every new memberdata property has a `memberdata_properties.xml` entry and a round-trip test | Three new `type="int"` properties; `MutablePropertySheet`/`setMemberProperties` source read directly to confirm the failure mode and the type-validation rule — see Code Examples |
</phase_requirements>

## Summary

Three independent, previously-unverified facts drive this phase's design, all confirmed against
installed source rather than assumed:

**1. `validate_token`'s current implementation has zero drift tolerance and zero replay
protection, and the third-party library's own token-format check is not the fix.**
`helpers.validate_token` (`helpers.py:322-358`) calls `onetimepass.valid_totp(token, secret)`,
which is exactly `_is_possible_token(token) and int(token) == get_totp(secret)`
(`onetimepass/__init__.py`, installed at
`/srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py`) —
`get_totp` computes a **single** interval, `int(time.time()) // 30`, with no forward or backward
tolerance at all, so a code submitted one tick late (any real network/typing delay) already fails
today. **The ROADMAP's own phrasing "`_is_possible_token` currently accepts `"1"` and `"123"`" names
a function that lives inside `onetimepass`, not in this codebase** — it is not imported, not
exported for override, and not patchable without vendoring the library, which is explicitly out of
budget for a 2-year-life package. `onetimepass`'s `_is_possible_token` does `token.isdigit() and
len(token) <= 6` — confirming the roadmap's claim about its behaviour, but the fix has to be a
**new, independent check written in this package's `helpers.py`**, applied before any
`onetimepass`/`get_hotp` call, not a change to the library.

**2. Drift and replay are naturally the same six lines, exactly as the roadmap says, but they need
one piece of state `onetimepass` doesn't manage: the last-accepted interval.**
`get_hotp(secret, intervals_no=i)` (confirmed at `onetimepass/__init__.py`, `get_hotp` function) is
a pure, stateless function: HMAC-SHA1 over `struct.pack('>Q', intervals_no)`, dynamic truncation,
mod 1,000,000. Accepting the immediately-preceding step means comparing the submitted token against
`get_hotp(secret, intervals_no=current)` and `get_hotp(secret, intervals_no=current-1)` **only** —
never `current+1`, since accepting a future code makes no sense for TOTP and the phase notes
explicitly warn against "widening the window forward". `onetimepass.valid_hotp` cannot be reused for
this: its `last`/`trials` parameters search **forward** from `last+1`, which is the opposite
direction (HOTP resync semantics, not TOTP drift), and it has no concept of "the interval before
now" at all. Replay rejection needs one integer of state — the last interval that was actually
matched and accepted — compared with `<=` against any newly-matched interval. Storing this single
integer (not a list of consumed codes) is what the roadmap's research question 2 asks for, and it
is what keeps the property bounded and cheap to validate.

**3. `MutablePropertySheet`'s type-checking is stricter, and its failure mode more specific, than
"round-trips or doesn't" — read directly from `Products.PlonePAS==5.1.1`'s installed source**
(`Products/PlonePAS/sheet.py`, and `Products/PlonePAS/tools/memberdata.py::setMemberProperties`):
the type registered for a property is enforced by `PropertySchema.validate`, and for `'int'` that
inspector is exactly `lambda x: x is None or isinstance(x, int)` — a Python 2 `long` or a `float`
value **fails validation and raises `PropertyValueError`**, it does not silently coerce. `int(x)` on
a value already `< sys.maxint` (true for any Unix epoch for centuries on this 64-bit interpreter)
returns a genuine `int`, so `int(time.time())` is safe to store as `type="int"`; passing `time.time()`
itself (a `float`) would not be. Separately, and this is the "silent" failure CLAUDE.md/MFA-13 warn
about: `MemberData.setMemberProperties` (not the plural `MutablePropertySheet.setProperties`, which
this codebase's call path never reaches) loops `for k, v in mapping.items(): for sheet in sheets: if
not sheet.hasProperty(k): continue` — a key absent from every property sheet's declared property
list is **silently skipped**, no exception, no log line, and `modified` simply never becomes `True`
for that key. This is the exact mechanism `memberdata_properties.xml` entries prevent, and it is why
every new property in this phase needs both the XML entry and a `setMemberProperties()` →
`getProperty()` round-trip test, per MFA-13.

Two more mechanical findings shape the plan directly. First, `<records
interface="imio.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings" />` in the
existing `profiles/default/registry.xml` carries **no explicit field list** — confirmed by reading
`plone.app.registry`'s `RegistryImporter.importRecords` (installed at
`/home/cadam/buildout-cache/eggs/plone.app.registry-1.2.5-py2.7.egg/plone/app/registry/exportimport/handler.py`),
which iterates every field the *Python* interface declares and seeds a record with the schema's
default when the XML supplies no override. Adding two `zope.schema.Int` fields to
`IGoogleAuthenticatorSettings` therefore needs **zero `registry.xml` changes** — the existing blanket
`<records interface="..." />` line already covers them. Second, `helpers.validate_token` is called
from **three** views, not one: `browser/forms/token.py` (the login second factor), but also
`browser/forms/reset_bar_code.py` and `browser/forms/user_setup.py` (enrolment self-test and
bar-code-reset identity confirmation). REQUIREMENTS.md and ROADMAP.md phrase every lockout success
criterion around "the token form view" (singular), so the recommended split is: put the *format +
drift + replay* correctness fix inside shared `helpers.validate_token` (it is correct everywhere a
TOTP code is checked, and none of the three call sites end in an aborted transaction, so a state
write there does not reopen MFA-12), but keep the *lockout counter and 900s lock* strictly inside
`browser/forms/token.py::handleSubmit`, matching the phase's own literal scope. This is flagged as
Open Question 1 below since it is a scope decision, not a mechanical fact.

**Primary recommendation:** Implement drift+replay as a small, pure `helpers.py` function built
directly on `get_hotp` (two calls, `current` and `current-1`, compared to `int(token)`), gated by a
new exact-6-digit format check that does not depend on or patch `onetimepass`. Track replay state as
a single `two_factor_authentication_last_interval` `int` memberdata property, updated only on
successful validation. Implement the lockout counter and 900s lock as two more `int` memberdata
properties (`two_factor_authentication_failed_attempts`,
`two_factor_authentication_locked_until`), written only from `browser/forms/token.py::handleSubmit`,
with the lock check running and short-circuiting before `validate_token` is ever called. Add
`max_failed_attempts` (default 5) and `lockout_duration` (default 900) as two more fields on the
existing `IGoogleAuthenticatorSettings` interface, rendered by the existing
`GoogleAuthenticatorSettingsEditForm` with no new form class. Add all three new memberdata
properties to `memberdata_properties.xml` as `type="int"`, default `0`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| TOTP drift/replay validation | API/Backend (`helpers.validate_token`) | — | Pure computation over a secret and a stored interval; no ZODB write needed for the *check* itself, only for recording acceptance |
| Replay state (last accepted interval) | Database/Storage (memberdata property, `OOBTree`-backed) | API/Backend (write site) | Must survive across requests and ZEO clients; written only from a view that commits normally |
| Lockout counter + lock expiry | Database/Storage (memberdata property) | API/Backend (`browser/forms/token.py`) | Same persistence requirement as replay state; write confined to the one view MFA-12 names |
| Lockout policy (N, duration) | API/Backend (`plone.registry`, `IGoogleAuthenticatorSettings`) | — | Site-wide, admin-configurable, already the pattern this package uses for `globally_enabled`/`ip_addresses_whitelist` |
| Token-format gate (exactly 6 digits) | API/Backend (`helpers.py`) | — | Pre-condition check before any TOTP arithmetic; cannot live in the third-party library |
| Control panel rendering of N/duration | API/Backend (z3c.form `AutoExtensibleForm`) | — | Already-established, already-tested pattern in this codebase; no new tier needed |

## Standard Stack

No new third-party dependency is introduced by this phase. Every function used already ships in
eggs this buildout resolves, and `time`/`os` are stdlib.

### Core (already in the resolved environment — no install step)

| Component | Resolved version | Purpose | Evidence |
|-----------|-------------------|---------|----------|
| `onetimepass` | 0.2.2 | `get_hotp(secret, intervals_no=i)` — pure interval-indexed HOTP computation, the primitive TOTP drift-checking is built on | `[VERIFIED: /srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py]` |
| `Products.PlonePAS` | 5.1.1 | `MutablePropertySheet`/`MemberData.setMemberProperties`/`getProperty` — the memberdata property round-trip mechanics MFA-13 concerns | `[VERIFIED: /home/cadam/buildout-cache/eggs/Products.PlonePAS-5.1.1-py2.7-linux-x86_64.egg/Products/PlonePAS/sheet.py, Products/PlonePAS/tools/memberdata.py]` |
| `plone.app.registry` | 1.2.5 | `RegistryImporter.importRecords` — confirms field-list-free `<records interface=.../>` auto-seeds new schema fields with their defaults | `[VERIFIED: /home/cadam/buildout-cache/eggs/plone.app.registry-1.2.5-py2.7.egg/plone/app/registry/exportimport/handler.py]` |
| `zope.schema` | (already imported in `controlpanel.py`) | `Int` field type for the two new control-panel settings, sibling to the already-used `TextLine`/`Bool`/`Text` | `[VERIFIED: src/imio/googleauthenticator/browser/controlpanel.py imports TextLine, Bool, Text from zope.schema already]` |
| `time` (stdlib) | Python 2.7.18 | `time.time()` for interval math and lockout epoch comparisons | stdlib |

### Alternatives Considered

| Instead of | Could use | Tradeoff |
|------------|-----------|----------|
| A new `int`-based two-call `get_hotp` loop for drift | `onetimepass.valid_hotp(token, secret, last=X, trials=2)` | `valid_hotp` only searches **forward** from `last+1`; it has no backward-looking mode, so it cannot express "accept T or T-1" without reversing its own semantics (which would also silently start accepting *future* codes, the exact anti-pattern the phase warns against) |
| `onetimepass` → `pyotp` (has built-in `valid_window` drift support) | Migrate the TOTP library | Explicitly out of scope per REQUIREMENTS.md: "`onetimepass` → `pyotp`: Unnecessary: `get_hotp(secret, intervals_no=i)` already exposes the window counter replay detection needs" — confirmed true by the code read above |
| Storing the last-accepted **interval number** (one int) | Storing a list/set of consumed codes with a TTL | An unbounded (or manually-pruned) list is more state, more code, and more failure surface for a value a single integer comparison already replaces: any code for an interval `<=` the stored one is necessarily a replay or an out-of-window guess |
| Two new `zope.schema.Int` fields on the existing `IGoogleAuthenticatorSettings` + existing `GoogleAuthenticatorSettingsEditForm` | Following `imio.dms.mail`'s `RegistryEditForm` + `layout.wrap_form(..., ControlPanelFormWrapper)` pattern literally | This package's control panel already is a registry-backed, auto-extensible form (`AutoExtensibleForm` + `getContent()` returning `registry.forInterface(...)`) that already renders every field the schema declares, with an established `test_generic.py` field-presence test pattern to extend. Swapping to `RegistryEditForm` would mean re-implementing `render()`'s `control_panel_extra.html` append and the enable/disable-all-users button handlers on a new base class for no behavioural gain. Recommended: extend the existing schema and form; do not introduce a second form pattern into a package this deliberately small. |

**Installation:** None — no new packages.

## Package Legitimacy Audit

Not applicable. This phase adds zero new third-party packages; it uses `onetimepass==0.2.2` (already
approved and pinned), `Products.PlonePAS`/`plone.app.registry` (transitive Plone 4.3 dependencies),
and `zope.schema` (already imported in this codebase). **Packages removed due to `[SLOP]` verdict:**
none. **Packages flagged as suspicious `[SUS]`:** none.

## Architecture Patterns

### System Architecture Diagram — one request, four sequential gates, one write site

```
POST @@google-authenticator-token
(auth_user, signature, token)
        │
        ▼
┌─────────────────────────────┐
│ validate_user_data (ska)    │  existing, unchanged (SEC/COEX phases)
│ -- signed-URL tamper check  │
└──────────────┬──────────────┘
               │ valid signature
               ▼
┌─────────────────────────────────────────────┐
│ NEW Gate 1 -- lockout check (MFA-08/09)      │
│ locked_until = user.getProperty(             │
│     'two_factor_authentication_locked_until')│
│ if locked_until and now < locked_until:      │
│     show the SAME "Invalid token or token    │
│     expired." message as a wrong code --     │
│     do NOT call validate_token at all        │
└──────────────┬────────────────────────────────┘
               │ not locked (or lock expired)
               ▼
┌─────────────────────────────────────────────┐
│ NEW Gate 2 -- format check (MFA-07)          │
│ len(token) == 6 and token.isdigit()          │
│ -- BEFORE any onetimepass call, because      │
│ onetimepass's own _is_possible_token accepts │
│ isdigit() and len <= 6                       │
└──────────────┬────────────────────────────────┘
               │ exactly 6 digits
               ▼
┌─────────────────────────────────────────────┐
│ NEW Gate 3 -- drift + replay (MFA-05/06)     │
│ current = int(time.time()) // 30             │
│ for i in (current, current - 1):             │
│     if get_hotp(secret, intervals_no=i)      │
│             == int(token):                    │
│         matched = i; break                    │
│ else: reject                                  │
│ last = user.getProperty(                      │
│     'two_factor_authentication_last_interval')│
│ if matched <= last: reject (replay)           │
└──────────────┬───────────────┬────────────────┘
       accepted│               │rejected
               ▼               ▼
  ┌─────────────────────┐  ┌───────────────────────────┐
  │ WRITE (token.py view,│  │ WRITE (token.py view,     │
  │ commits normally):    │  │ commits normally):        │
  │ - last_interval=matched│  │ - failed_attempts += 1    │
  │ - failed_attempts = 0 │  │ - if failed_attempts >= N:│
  │ - _setupSession, log in│ │     locked_until = now+D │
  │                        │  │ - same generic error msg  │
  └─────────────────────┘  └───────────────────────────┘
```

### Recommended Project Structure

No new modules. Changes land in the existing files this package already centralizes logic in:

```
src/imio/googleauthenticator/
├── helpers.py                      # new: token-format gate, drift+replay validate_token rewrite,
│                                    #      replay-interval read/compare (pure, no write here)
├── browser/
│   ├── controlpanel.py              # new: max_failed_attempts, lockout_duration Int fields on
│   │                                 #      the existing IGoogleAuthenticatorSettings
│   └── forms/
│       └── token.py                 # new: lock check before validate_token; failure-counter
│                                     #      increment/reset and lock-set, all in handleSubmit
├── profiles/default/
│   └── memberdata_properties.xml    # new: 3 properties, type="int", default "0"
└── tests/
    ├── test_helpers.py               # extend: drift accepted, replay rejected, exact-6-digit
    │                                  #         gate, replay-log-has-no-username
    └── test_token_form.py            # NEW FILE: lockout end-to-end (lock after N, indistinguishable
                                       #           response, expiry, counter reset, counter survives
                                       #           a request that started with an Unauthorized
                                       #           challenge -- no test file currently covers
                                       #           browser/forms/token.py's handleSubmit directly)
```

### Pattern 1: Pure drift+replay check, separate from the persistence it informs

**What:** A single helper computes which interval (if any) matched, without writing anything. The
caller (which already knows it is inside a normally-committing view) decides whether and what to
persist.
**When to use:** Any TOTP-family library whose validation primitive has no drift/replay support of
its own (true of `onetimepass==0.2.2`'s `valid_totp`).
**Example (the six lines, confirmed buildable from installed `onetimepass`):**
```python
# Source: onetimepass 0.2.2, get_hotp signature and semantics confirmed at
# /srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py
from onetimepass import get_hotp
import time

def _find_accepted_interval(token, secret, last_accepted_interval):
    """Returns the matched interval number, or None. Never checks intervals
    ahead of "now" -- RFC 6238 drift tolerance is backward-looking only."""
    current_interval = int(time.time()) // 30
    for interval in (current_interval, current_interval - 1):
        if get_hotp(secret, intervals_no=interval) == int(token):
            if interval <= last_accepted_interval:
                return None  # RFC 6238 Section 5.2 MUST NOT: already consumed
            return interval
    return None
```
This is a pure function: given the same three arguments it always returns the same answer, so it
can be unit-tested with `test_helpers.py`'s existing `TestSeedEncryption`-style fixtures with no
special layer, and it never touches the ZODB — the caller in `token.py` is the one that writes
`two_factor_authentication_last_interval` on success.

### Pattern 2: Exact-format gate as a precondition, not a library patch

**What:** `onetimepass`'s own internal `_is_possible_token` (not exported, not overridable) accepts
1-to-6-digit numeric strings. MFA-07 needs exactly 6. The fix is a check in this package, run before
`onetimepass`/`get_hotp` is ever called.
**Example:**
```python
def _is_six_digit_token(token):
    token = token if isinstance(token, basestring) else str(token)
    return token.isdigit() and len(token) == 6
```
**Why not patch `onetimepass`:** it is a pinned, last-Python-2.7-release third-party egg; monkeypatching
a private function of a frozen dependency for one call site is exactly the kind of custom solution
this project's own `Don't Hand-Roll` conventions warn against, and it would silently stop protecting
the moment the pin is ever bumped (out of scope, but worth not building a trap for).

### Pattern 3: Control panel field addition with zero XML changes

**What:** Two new `zope.schema.Int` fields on `IGoogleAuthenticatorSettings`
(`src/imio/googleauthenticator/browser/controlpanel.py`), added to the existing `fieldset(...)` field
list. No `registry.xml` change (confirmed above: the blanket `<records interface="..." />` seeds
every field the interface declares, with the schema's own default).
```python
# controlpanel.py -- additive to the existing IGoogleAuthenticatorSettings
max_failed_attempts = Int(
    title=_("Maximum failed second-factor attempts"),
    description=_("After this many consecutive failed token attempts, the "
                  "account is locked for the configured duration."),
    required=True,
    default=5,
    min=1,
    )
lockout_duration = Int(
    title=_("Lockout duration (seconds)"),
    description=_("How long an account stays locked after too many failed "
                  "second-factor attempts."),
    required=True,
    default=900,
    min=1,
    )

fieldset(
    None,
    label=None,
    fields=['ska_secret_key', 'globally_enabled', 'ip_addresses_whitelist',
            'max_failed_attempts', 'lockout_duration'],
    )
```
The existing `GoogleAuthenticatorSettingsEditForm` (`AutoExtensibleForm` + `EditForm`) renders and
saves any field the schema declares with no further code change — confirmed by reading its
`getContent`/`updateFields`/`handleSave`, none of which enumerate fields explicitly.

### Anti-Patterns to Avoid

- **Calling `validate_token` before checking the lock:** defeats the "indistinguishable response"
  requirement (MFA-08's oracle concern) and, worse, would consume/replay-mark a code even while
  locked, wasting the drift window on a login attempt that was refused anyway.
- **Trusting `onetimepass.valid_totp`/`valid_hotp` for format validation:** both delegate to the
  library's own `_is_possible_token`, which accepts 1-6 digits, not exactly 6 — confirmed source
  read, not assumed.
- **Storing `time.time()` (a `float`) into a `type="int"` memberdata property:** `MutablePropertySheet`'s
  `'int'` type inspector is `isinstance(x, int)`, which a `float` fails — always coerce with
  `int(...)` before the `setMemberProperties` call.
- **Writing lockout/replay state from `pas_plugin.py` or `subscribers.py`/`challenge()`:** both are
  either fully write-free by this phase's own predecessor (Phase 4) or reached after
  `transaction.abort()` — any write there is silently discarded, exactly the MFA-12 hazard this
  phase exists to close, not reopen.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HMAC-based one-time-password computation for a specific interval | A custom HMAC-SHA1/dynamic-truncation implementation | `onetimepass.get_hotp(secret, intervals_no=i)` | Already RFC 4226-compliant, already the pinned dependency, already used elsewhere in this codebase |
| Constant-time comparison anywhere a secret/token is checked | A bespoke `==` loop | Not needed here — `get_hotp`/`int() ==` compares small integers (a 6-digit number), which is not a secret-length-dependent timing channel the way `hmac.compare_digest` protects against for `bar_code_reset_token`; the existing `validate_bar_code_reset_token` pattern is the model for those cases, not this one |
| A registry.xml field-value block for two new settings | Hand-writing `<value>` XML nodes for the two new Int fields | Nothing — the existing blanket `<records interface="..." />` already covers any field the Python interface declares |
| A new control-panel form base class | Copying `imio.dms.mail`'s `RegistryEditForm`/`layout.wrap_form` scaffolding | The existing `AutoExtensibleForm`-based `GoogleAuthenticatorSettingsEditForm`, which already auto-renders any schema field |

**Key insight:** Every piece of this phase composes out of functions/classes already present in this
buildout's eggs or this codebase's own `helpers.py`/`controlpanel.py`. The only genuinely new code is
the small format gate and the interval-comparison loop — both a handful of lines each, not new
abstractions.

## Common Pitfalls

### Pitfall 1: Conflating `onetimepass`'s internal token-format check with this package's own code
**What goes wrong:** A plan reads ROADMAP.md's "`_is_possible_token` currently accepts `"1"` and
`"123"`" and goes looking for that function in `helpers.py` or `pas_plugin.py` to edit.
**Why it happens:** The name is written as if it belongs to this codebase; it does not — `grep -rn
"_is_possible_token" src/` returns nothing in this package.
**How to avoid:** The fix is a **new** check in `helpers.py`, run before `onetimepass` is ever
called, not an edit to a third-party pinned egg.
**Warning signs:** Any diff that touches `/srv/cache/eggs/onetimepass-*` or that imports
`onetimepass._is_possible_token` directly (it is not part of `onetimepass.__all__` and is not a
supported import).

### Pitfall 2: Zero-padding trap in the existing SEC-01 regression test
**What goes wrong:** `test_helpers.py::TestSeedEncryption::test_seed_encryption_round_trip` calls
`validate_token(get_totp(seed), user=user)` where `get_totp(seed)` (with the library's default
`as_string=False`) returns a **bare, non-zero-padded `int`** — e.g. `42`, not `"000042"` — because
`get_totp`/`get_hotp` compute `token_base % 1000000` and return it as an `int` with no `str.zfill`.
Once MFA-07's exact-6-digit gate lands, this existing test's own construction will fail the new
format check on any interval where the true TOTP value happens to need fewer than 6 digits (a
roughly 1-in-10 chance per attempt, since leading digits 0-8 out of 0-9 keep it at 6, but a leading
zero drops a digit), making this a real, load-bearing, test-breaking change, not a hypothetical.
**Why it happens:** A real Google Authenticator app always zero-pads what it *displays* to 6
characters; `get_totp(seed)`'s bare-`int()` return value used directly in a test does not.
**How to avoid:** Update that call site to `get_totp(seed, as_string=True)` (already zero-padded
to 6 bytes) — or format the int with `'{:06d}'.format(...)` — as part of *this* phase's changes,
not as a surprise regression discovered later. This is a required, in-scope test fix, not an
incidental side effect to shrug off.
**Warning signs:** `test_seed_encryption_round_trip` starts failing intermittently (only on seeds
whose current TOTP value is under 100000) after the format gate lands, with no code change to that
test file itself.

### Pitfall 3: `MutablePropertySheet`'s type check rejects `float`/`long`, it does not coerce
**What goes wrong:** Writing `user.setMemberProperties(mapping={'two_factor_authentication_locked_until':
time.time() + lockout_duration})` raises `PropertyValueError` inside `MutablePropertySheet.setProperty`
(reached via `MemberData.setMemberProperties` → `sheet.setProperty(user, k, v)` →
`self.validateProperty(id, value)`), because `time.time()` is a `float` and the `'int'` type
inspector is `isinstance(x, int)`.
**Why it happens:** The property-type validator does not attempt any numeric coercion; it is a
strict `isinstance` check per type (confirmed at
`Products/PlonePAS/sheet.py::PropertySchema`).
**How to avoid:** Always wrap with `int(...)` before the write: `int(time.time()) + lockout_duration`
is itself an `int` (int + int = int in Python 2), safe to store.
**Warning signs:** `PropertyValueError` raised inside a `handleSubmit`, swallowed by the existing
broad `except Exception:` blocks in `token.py`'s sibling forms (`user_setup.py`, `reset_bar_code.py`)
— which would turn a broken lockout write into a silent no-op with a generic "unexpected error"
message, exactly the "looks like it works" failure mode this whole phase exists to prevent. Do not
wrap the new lockout-write code in a broad `except Exception` for this reason: let a
`PropertyValueError` surface loudly during development rather than mask a real property-declaration
bug.

### Pitfall 4: Silent memberdata-property drop, not an exception
**What goes wrong:** A new memberdata property is used in code (`getProperty`/`setMemberProperties`)
but its `memberdata_properties.xml` entry is forgotten. `MemberData.setMemberProperties`'s
`if not sheet.hasProperty(k): continue` means the write for that key is **silently skipped** across
every property sheet — no exception, no log line, `getProperty` keeps returning the schema field's
Python-level default (`''`/`False`/whatever `getProperty`'s own default fallback is) forever.
**Why it happens:** `setMemberProperties` is designed to tolerate keys aimed at a *different*
property sheet (e.g. a mapping containing both memberdata and a different plugin's properties) — the
`continue` is correct behaviour for that case and indistinguishable from "declaration forgotten" from
the caller's point of view.
**How to avoid:** The `memberdata_properties.xml` entry and the round-trip test
(`setMemberProperties` then `getProperty` returns what was set, not the default) must land in the
**same commit** as the code that starts writing the property, exactly as MFA-13 requires.
**Warning signs:** A lockout that "never locks" or a failure counter that always reads back `0`
with no error anywhere in the logs — this is precisely the Phase 4 "silent risk" pattern ROADMAP.md
calls this project's dominant risk category.

### Pitfall 5: Scope creep of the lockout write beyond `browser/forms/token.py`
**What goes wrong:** `helpers.validate_token` is also called from `browser/forms/reset_bar_code.py`
and `browser/forms/user_setup.py`. If the failure-counter/lockout logic is embedded inside
`validate_token` itself rather than wrapped around it in `token.py`, a wrong code during **enrolment
self-test** or a **bar-code reset** attempt would also count toward — and potentially trigger — the
account lockout that MFA-08's success criteria describe entirely in terms of "the token form".
**Why it happens:** `validate_token` is the one shared function all three views call, making it the
tempting single insertion point for "any place a code is checked."
**How to avoid:** Keep the format+drift+replay **check** (and its `last_interval` state write, which
is a correctness fix, not a security policy choice, and is safe in all three normally-committing
views) inside `helpers.validate_token`. Keep the **lockout counter and 900s lock** — the specific
policy MFA-08/09/10/11 describe — as a wrapper in `browser/forms/token.py::handleSubmit` only. See
Open Question 1 — this is a scope decision the planner should make explicitly, not silently default
either way.

## Code Examples

### Confirmed `onetimepass` internal token-format check (Q1 -- the mechanical correction)
```python
# Source: onetimepass 0.2.2, installed at
# /srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py
def _is_possible_token(token):
    """Determines if given value is acceptable as a token. Used when validating
    tokens.

    Currently allows only numeric tokens no longer than 6 chars.
    """
    if not isinstance(token, bytes):
        token = six.b(str(token))
    return token.isdigit() and len(token) <= 6
```
This is a private function of the pinned `onetimepass==0.2.2` egg -- not exported in
`onetimepass.__all__` (`['get_hotp', 'get_totp', 'valid_hotp', 'valid_totp']`), not importable as
part of this package's public contract, and not the right place to fix MFA-07.

### Confirmed `get_hotp`/`get_totp` interval arithmetic (Q1)
```python
# Source: onetimepass 0.2.2, get_hotp/get_totp
def get_hotp(secret, intervals_no, as_string=False, casefold=True):
    if isinstance(secret, six.string_types):
        secret = secret.encode('utf-8')
    key = base64.b32decode(secret, casefold=casefold)  # raises TypeError('Incorrect secret')
    msg = struct.pack('>Q', intervals_no)
    hmac_digest = hmac.new(key, msg, hashlib.sha1).digest()
    ob = ord(hmac_digest[19])   # Python 2 path
    o = ob & 15
    token_base = struct.unpack('>I', hmac_digest[o:o + 4])[0] & 0x7fffffff
    token = token_base % 1000000
    return token  # bare int, NOT zero-padded, when as_string=False

def get_totp(secret, as_string=False):
    interv_no = int(time.time()) // 30
    return get_hotp(secret, intervals_no=interv_no, as_string=as_string)
```
Confirms: (a) `get_hotp` is a pure function of `(secret, intervals_no)`, safe to call for `current`
and `current - 1` with no side effects; (b) the 30-second step boundary (`int(time.time()) // 30`) is
the exact arithmetic this phase's drift loop must replicate for "current"; (c) the bare-`int` return
is the source of Pitfall 2 above.

### Confirmed property-type validation and the silent-drop mechanism (MFA-13, Q3)
```python
# Source: Products.PlonePAS 5.1.1, installed at
# /home/cadam/buildout-cache/eggs/Products.PlonePAS-5.1.1-py2.7-linux-x86_64.egg/Products/PlonePAS/sheet.py
PropertySchema.addType('int', lambda x: x is None or isinstance(x, int))
PropertySchema.addType('float', lambda x: x is None or isinstance(x, float))
# 'date' inspector is `lambda x: 1` (accepts anything) but MemberData's own
# getProperty/property-sheet machinery for 'date' round-trips through Zope's
# legacy DateTime, not a bare int/epoch -- this is the "DateTime round-tripping"
# the roadmap's own note warns against, confirmed by this type's inspector
# being unconditionally permissive (i.e. it defers correctness to whatever
# consumes the value, which for 'date' is DateTime-shaped code elsewhere).

class MutablePropertySheet(UserPropertySheet):
    def validateProperty(self, id, value):
        if id not in self._properties:
            raise PropertyValueError('No such property found on this schema')
        proptype = self.getPropertyType(id)
        if not validateValue(proptype, value):
            raise PropertyValueError(
                "Invalid value (%s) for property '%s' of type %s" % (value, id, proptype))

    def setProperty(self, user, id, value):
        self.validateProperty(id, value)   # <-- raises loudly for a DECLARED property, wrong type
        self._properties[id] = value
        ...
```
```python
# Source: Products.PlonePAS 5.1.1, Products/PlonePAS/tools/memberdata.py::MemberData.setMemberProperties
for k, v in mapping.items():
    if v is None and not force_empty:
        continue
    for sheet in sheets:
        if not sheet.hasProperty(k):
            continue          # <-- silently skips an UNDECLARED property, no exception at all
        if IMutablePropertySheet.providedBy(sheet):
            sheet.setProperty(user, k, v)
            modified = True
        else:
            break
if modified:
    self.notifyModified()
```
This confirms **two distinct failure modes**, both real: a declared property given the wrong Python
type raises `PropertyValueError` loudly (Pitfall 3); an undeclared property is silently dropped with
no error at all (Pitfall 4, and the reason MFA-13 exists).

### Confirmed field-list-free registry seeding (control panel, Q6 substitute)
```python
# Source: plone.app.registry 1.2.5, installed at
# /home/cadam/buildout-cache/eggs/plone.app.registry-1.2.5-py2.7.egg/plone/app/registry/exportimport/handler.py
# importRecords (abridged): for a <records interface="X" /> node with no
# child <value> elements, every field the Python interface X declares is
# registered as a record, using the schema field's own default when the XML
# supplies none -- confirmed by reading getFieldNames(interface)-driven
# iteration in this handler.
```
The existing `profiles/default/registry.xml` already reads:
```xml
<registry>
    <records interface="imio.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings" />
</registry>
```
No edit needed here for `max_failed_attempts`/`lockout_duration` — only the Python interface changes.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `onetimepass.valid_totp(token, secret)` -- single-interval, zero drift, zero replay protection | `helpers`-local drift+replay check over `get_hotp(secret, intervals_no=i)` for `i in (current, current-1)`, gated by the last-accepted-interval | This phase | Closes MFA-05/06/07; every existing call site (`token.py`, `reset_bar_code.py`, `user_setup.py`) benefits from the format/drift/replay fix simultaneously, since they share `helpers.validate_token` |
| No account lockout at all | 5-attempt / 900s lockout, state in memberdata, checked before token validation | This phase | Closes MFA-08/09/10/11; brute force against the second factor now costs ~1042 days expected, per the roadmap's own NIST-referenced math |
| Two `plone.registry` settings (`ska_secret_key`, `globally_enabled`, `ip_addresses_whitelist`) | Four settings, same interface, same form | This phase | No new control-panel infrastructure; MFA-10 satisfied by extension, not replacement |

**Deprecated/outdated:** None — `onetimepass==0.2.2` itself is not deprecated for this project's
purposes (Python 2.7 pin makes any newer TOTP library moot, and REQUIREMENTS.md explicitly rules out
migrating to `pyotp`); this phase corrects this codebase's *usage* of it, not the library itself.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The drift+replay correctness fix (format check, `last_interval` write) should live in shared `helpers.validate_token`, reachable from all three call sites, while the lockout counter/lock should be scoped to `browser/forms/token.py` only | Summary, Pitfall 5, Open Question 1 | If the planner instead scopes lockout to all three views (or the format/replay fix to only `token.py`), the observable behaviour differs materially: either enrolment/reset attempts start contributing to login lockouts (a scope the requirements never name), or `reset_bar_code.py`/`user_setup.py` keep accepting non-6-digit or replayed codes after this phase ships. No CONTEXT.md exists to settle this with the user, so it is presented as a recommendation, not a locked fact |
| A2 | `max_failed_attempts`/`lockout_duration` as the two new control-panel field names | Architecture Patterns, Pattern 3 | Cosmetic only — any name works as long as it is wired to the same registry records N and duration are read from in `token.py`; not load-bearing |
| A3 | Property names `two_factor_authentication_failed_attempts`, `two_factor_authentication_locked_until`, `two_factor_authentication_last_interval` | Summary, Recommended Project Structure | Cosmetic only; chosen to match the existing `two_factor_authentication_secret`/`enable_two_factor_authentication` naming convention already in `userdataschema.py` |

**None of A1-A3 concerns a security-relevant mechanical fact** — every mechanical claim in this
research (onetimepass semantics, property-type validation, registry seeding, `setMemberProperties`
failure modes) was read directly from installed source, not assumed. A1 is a scope/design
recommendation flagged for explicit planner confirmation.

## Open Questions

1. **Does the lockout counter/lock apply only to `browser/forms/token.py`, or to all three
   `validate_token` call sites (`reset_bar_code.py`, `user_setup.py` too)?**
   - What we know: REQUIREMENTS.md and ROADMAP.md phrase every MFA-08..11 success criterion around
     "the token form view" (singular); `helpers.validate_token` is in fact shared by three views.
   - What's unclear: whether the requirements' narrow phrasing is a deliberate scope choice or just
     the obvious/primary case, with the other two views an oversight.
   - Recommendation: scope the lockout to `browser/forms/token.py` only for this phase (matching the
     literal requirement text and success criterion 5's "the write lives in the token form view"),
     and record the other two views as a candidate fast-follow if the planner or a later security
     pass decides enrolment/reset also need brute-force protection. Do not silently expand scope
     without a plan-level decision recorded.

2. **What, precisely, does "the failure counter still increments after a request that ends in
   Unauthorized" mean as a test, given `browser/forms/token.py`'s own POST does not itself raise
   `Unauthorized`?**
   - What we know: the *originating* request in the real flow (an anonymous/unauthenticated hit on a
     2FA-protected resource) is the one that ends in `Unauthorized` and triggers Phase 4's
     `challenge()` → redirect to the token form; the *token-form POST itself* is a normal,
     always-200-or-302, always-committing request.
   - What's unclear: whether the test should be a real two-request HTTP sequence (mirroring Phase
     4's `test_challenge_fires_on_unauthorized`/`test_pub_before_commit_fires_on_login_post` idiom)
     that starts with the `Unauthorized`-ending challenge and then submits a bad token, or a
     unit-level call directly against `TokenForm.handleSubmit`.
   - Recommendation: follow Phase 4's own established pattern — a real `plone.testing.z2.Browser`
     round trip proving the counter increments and is independently re-readable afterward, since
     that is the only way to prove the *write itself* survived a real publish/commit cycle rather
     than a unit-level in-memory call that never exercises `transactions_manager.commit()` at all.

## Environment Availability

Skipped — this phase has no external dependency beyond eggs already resolved and verified above
(`onetimepass`, `Products.PlonePAS`, `plone.app.registry`), all present in this buildout's
`parts/omelette` symlink tree / `buildout-cache`.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` via `bin/test` (plone.recipe.zope2instance `[test]` part; `unittest2` in test modules) |
| Config file | `test-4.3.cfg` (buildout-generated `bin/test`); no separate pytest/nose config |
| Quick run command | `bin/test -t test_helpers -t test_token_form -t test_setuphandlers` |
| Full suite command | `bin/test -t '!robot'` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MFA-05 | Code from `T-1` accepted | integration (unit-style, real secret + real `get_hotp`) | `bin/test -t test_validate_token_accepts_previous_interval` | ❌ Wave 0 — new test in `tests/test_helpers.py` |
| MFA-06 | Consumed code rejected on reuse; rejection logged with no plaintext username | integration | `bin/test -t test_validate_token_rejects_replayed_interval -t test_replay_rejection_log_has_no_username` | ❌ Wave 0 — new tests in `tests/test_helpers.py` |
| MFA-07 | Only exactly-6-digit input is a candidate | unit | `bin/test -t test_validate_token_rejects_short_or_long_input` | ❌ Wave 0 — new test in `tests/test_helpers.py`; existing `test_seed_encryption_round_trip` needs the `as_string=True` fix (Pitfall 2) in the same commit |
| MFA-08 | 5 failures lock for 900s; lock checked before token; locked response indistinguishable | integration (real `Browser` POST sequence) | `bin/test -t test_lockout_after_five_failures -t test_locked_account_response_is_generic_for_valid_and_invalid_code` | ❌ Wave 0 — new `tests/test_token_form.py` |
| MFA-09 | Lock expires on its own | integration | `bin/test -t test_lockout_expires_without_admin_action` | ❌ Wave 0 — new `tests/test_token_form.py` (can drive via a stubbed `time.time()` or a `locked_until` set directly in the past) |
| MFA-10 | N and duration editable, default 5/900 | integration (control panel field presence + default) | `bin/test -t test_control_panel_has_lockout_fields` | ❌ Wave 0 — extend `tests/test_generic.py`'s existing field-presence pattern |
| MFA-11 | Success resets counter | integration | `bin/test -t test_successful_login_resets_failed_attempts` | ❌ Wave 0 — new `tests/test_token_form.py` |
| MFA-12 | No write in PAS plugin/challenge plugin | regression (existing Phase 4 tests must still pass unmodified) | `bin/test -t test_challenge_writes_nothing -t '!robot'` | ✅ already exists (`tests/test_challenge.py`); this phase must not touch `pas_plugin.py`'s write-free surfaces |
| MFA-13 | New properties declared + round-trip tested | integration | `bin/test -t test_new_memberdata_properties_round_trip` | ❌ Wave 0 — new test in `tests/test_helpers.py`, modeled on `TestSeedEncryption`'s setUp/login pattern |

### Sampling Rate
- **Per task commit:** `bin/test -t test_helpers -t test_token_form -t test_generic`
- **Per wave merge:** `bin/test -t '!robot'`
- **Phase gate:** Full suite green (`bin/test -t '!robot'`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_helpers.py` — add drift-accepted, replay-rejected, exact-6-digit-format,
  replay-log-no-username, and the three-property round-trip tests; fix
  `test_seed_encryption_round_trip`'s `get_totp(seed)` call to `get_totp(seed, as_string=True)`
  in the same commit as the format gate (Pitfall 2).
- [ ] `tests/test_generic.py` — extend the existing control-panel field-presence pattern
  (`IGoogleAuthenticatorSettings['ska_secret_key']`-style lookups already present) to cover
  `max_failed_attempts`/`lockout_duration`.
- [ ] New `tests/test_token_form.py` — no test file currently exercises
  `browser/forms/token.py::TokenForm.handleSubmit` directly; covers MFA-08/09/11 and Open
  Question 2's real-HTTP-sequence test.
- [ ] Framework install: none — `bin/test` already exists and is the established test runner.

## Security Domain

### Applicable ASVS Categories (Level 1, per `.planning/config.json` `security_asvs_level: 1`)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | This phase directly implements ASVS 2.8's OTP requirements: 2.8.1 (OTP verifier allows a defined tolerance window — the T/T-1 drift), 2.8.4 (OTP verified only once — the replay/last-interval check), 2.2.1-adjacent (verifier effectively limits brute-force via lockout) |
| V3 Session Management | no (this phase) | Unaffected — no session establishment logic changes here, only the second-factor gate ahead of it |
| V4 Access Control | no (this phase) | Unaffected |
| V5 Input Validation | yes | MFA-07's exact-6-digit gate is input validation at the point the token first reaches TOTP logic, before any cryptographic comparison |
| V6 Cryptography | no (this phase) | `get_hotp`'s HMAC-SHA1 computation is unchanged, reused as-is from `onetimepass` |
| V7 Error Handling and Logging | yes | MFA-06 explicitly requires the replay-rejection log line carry no plaintext username (ASVS 2.8.4/2.8.5-adjacent, and the general "do not log secrets/PII" logging discipline this codebase already follows for `validate_bar_code_reset_token`) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| TOTP brute force (guessing 6-digit codes) | Elevation of Privilege | 5-attempt lockout for 900s (MFA-08/09/10), evaluated before the token so a locked account cannot be used as a guessing oracle |
| TOTP replay (reusing a captured/observed valid code) | Elevation of Privilege / Spoofing | Last-accepted-interval comparison (MFA-06), rejecting any code for an interval already consumed |
| Lockout response used as a username/account-existence oracle | Information Disclosure | Identical generic error message ("Invalid token or token expired.") for a locked account regardless of whether the submitted code is actually correct — checked and enforced before `validate_token` runs at all |
| Username disclosure via security-relevant log lines | Information Disclosure | The replay-rejection log line carries no user-identifying field at all (simplest sufficient fix — omission, not hashing) |
| Silent lockout-that-never-locks from an undeclared memberdata property | Tampering (of the security control itself) | `memberdata_properties.xml` entry + round-trip test in the same commit as any new property (MFA-13), following the exact mechanism traced in Code Examples |
| Silent lockout-write failure from a type-mismatched property value | Tampering (of the security control itself) | Always `int(...)`-coerce epoch/counter values before `setMemberProperties`; do not wrap the write in a broad `except Exception` that would mask a `PropertyValueError` (Pitfall 3) |

## Sources

### Primary (HIGH confidence — read directly from the eggs this buildout resolves and this repo's own source)
- `/srv/cache/eggs/onetimepass-0.2.2-py2.7-linux-x86_64.egg/onetimepass/__init__.py` —
  `_is_possible_token`, `get_hotp`, `get_totp`, `valid_hotp`, `valid_totp` (full module read)
- `/home/cadam/buildout-cache/eggs/Products.PlonePAS-5.1.1-py2.7-linux-x86_64.egg/Products/PlonePAS/sheet.py` —
  `PropertySchemaTypeMap`, `MutablePropertySheet.validateProperty`/`setProperty`/`setProperties`
- `/home/cadam/buildout-cache/eggs/Products.PlonePAS-5.1.1-py2.7-linux-x86_64.egg/Products/PlonePAS/tools/memberdata.py` —
  `MemberData.setMemberProperties`, `MemberData.getProperty`
- `/home/cadam/buildout-cache/eggs/plone.app.registry-1.2.5-py2.7.egg/plone/app/registry/exportimport/handler.py` —
  `importRegistry`, `RegistryImporter.importDocument`/`importRecord`/`importRecords`
- `/home/cadam/buildout-cache/eggs/Zope2-2.13.30-py2.7-linux-x86_64.egg/OFS/PropertyManager.py` and
  `ZPublisher/Converters.py` — `type_converters`/`field2int` confirming `'int'` is a standard,
  well-supported property type
- This repo's own `src/imio/googleauthenticator/helpers.py`, `pas_plugin.py`,
  `browser/forms/token.py`, `browser/forms/reset_bar_code.py`, `browser/forms/user_setup.py`,
  `browser/controlpanel.py`, `userdataschema.py`,
  `profiles/default/memberdata_properties.xml`, `profiles/default/registry.xml`,
  `tests/test_helpers.py`, `tests/test_pas_plugin.py`, `tests/base.py` — read in full or in the
  relevant sections
- `.planning/REQUIREMENTS.md` (MFA-05..13 read in full), `.planning/ROADMAP.md` (Phase 4 and Phase 5
  sections read in full), `.planning/phases/04-pas-boundary/04-RESEARCH.md` and
  `04-VERIFICATION.md` (read in full — the PAS-boundary/commit-path findings this phase builds on)

### Secondary (MEDIUM confidence)
- None — every claim above was traceable to an installed source file or this repo's own code; no
  web search was performed or required for this phase's technical questions (consistent with
  `.planning/config.json`'s `brave_search`/`exa_search`/`tavily_search`/`ref_search` all being
  `false`, and with Phase 4's own research finding no need for one either).

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; every function traced to the exact installed egg version.
- Architecture: HIGH — the drift/replay/lockout gate ordering is derived directly from
  `onetimepass`'s literal source and `MutablePropertySheet`'s literal validation/skip logic, not
  inferred.
- Pitfalls: HIGH for the mechanical ones (onetimepass's real format check, property-type validation,
  the silent-skip mechanism, the zero-padding test trap); MEDIUM for the `validate_token`
  call-site-scope recommendation (Assumption A1 — evidence-based but genuinely a scope choice no
  CONTEXT.md settled).

**Research date:** 2026-07-31
**Valid until:** Effectively indefinite for the mechanical `onetimepass`/`PlonePAS`/registry findings
(pinned egg versions; `test-4.3.cfg` does not move without a deliberate pin bump); the
`validate_token` scope recommendation (A1) should be confirmed with the planner/user rather than
assumed stale, since it depends on intent, not on code that could drift.
