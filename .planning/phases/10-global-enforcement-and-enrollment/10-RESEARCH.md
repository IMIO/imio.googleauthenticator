# Phase 10: Global Enforcement and Enrollment - Research

**Researched:** 2026-08-06
**Domain:** PAS login-flow routing, `ska`-signed anonymous redirects, memberdata state, GenericSetup
install-time handlers — all internal to this repository. No new third-party package is needed.
**Confidence:** HIGH for source-level facts (all read directly, with line numbers, in this session).
MEDIUM for the one open design question (D-06), resolved below with reasoning, not just assertion.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Enrol existing accounts at install time, in `setuphandlers.setupVarious`. Rejected
  alternatives: making the login check consult the global setting; a documented manual
  post-install step.
- **D-02:** Install sets the enable flag and creates NO seed. No new member-data property is
  needed for *that* reason alone (D-06 below needs one for a different reason). No encryption key
  is needed at install.
- **D-03:** The login check keeps reading only the user's own flag. `pas_plugin.py:197-202` is not
  changed to consult the global setting.
- **D-04:** Install-time enrollment must not partially enrol without saying so. Whatever this
  phase uses at install must either enrol everyone or report plainly that it did not.
- **D-05:** A user whose flag is set but who has not completed enrollment is sent to the
  enrollment page, not the code-entry page. The routing decision is made in the login path before
  any URL is signed.
- **D-06:** The invariant the plan must satisfy: a user is never sent to the code-entry page
  unless they have actually completed enrollment. Two mechanisms are acceptable: (a) do not create
  the seed when signing an enrollment redirect; (b) track completed enrollment in a new
  member-data property, with a `memberdata_properties.xml` entry and a round-trip test if chosen.
  Research must settle which and say why (settled below: **(b)**).
- **D-07:** A missing or broken seed encryption key on this path must produce a clean refusal, not
  an error page. This phase creates exactly the account state (flag set, no seed) that makes the
  existing WR-01/WR-02 hazard in `send_2fa_redirect` reachable, so it is now on the critical path.
- **D-08:** The refusal to self-disable lives in the disable view itself
  (`browser/disable_two_factor_authentication.py`), gated on `globally_enabled`. This is the
  actual security control.
- **D-09:** The disable menu link is hidden as well, but hiding it is not the control.
- **D-10:** The enable link (`show_enable_two_factor_authentication_link`) is offered whenever the
  user is not enrolled, whatever the global setting says (MFA-17 + MFA-18).
- **D-11:** `show_disable_two_factor_authentication_link` is offered only when the user is
  enrolled **and** the global setting is off.
- **D-12 (discretion):** Wording of the self-disable refusal message is at the implementer's
  discretion, subject to: new translatable msgid, must not mention other accounts.
- **D-13 (discretion):** Whether install-time enrollment runs directly in `setupVarious` or in a
  helper it calls is at the implementer's discretion. Not discretionary: gated on
  `imio.googleauthenticator.marker.txt` like the rest of `setupVarious`, and idempotent —
  installing twice must not change anything the first install already did.

### Claude's Discretion

Everything not covered by D-01..D-11 above, subject to D-12/D-13's stated constraints. In
particular: the exact shape of the new member-data property from D-06(b) (name, whether it needs
a schema/adapter exposure — settled below, against the verification brief's literal wording, in
favour of the repo's own established "internal state gets no schema field" precedent), and the
exact target view/mechanism for MFA-19's anonymous enrollment redirect (settled below with two
named options and a recommendation).

### Deferred Ideas (OUT OF SCOPE)

- Making the login check consult the global setting directly (D-01's rejected alternative).
- **A site-wide un-enroll action.** CONTEXT.md/ROADMAP.md describe this as "commented out and
  only logs" — **this claim is only half true; see "Claims CONTEXT.md does not support" below.**
  It remains out of scope for this phase's deliverables regardless.
- Refusing a mismatched `userid` at `@@setup-two-factor-authentication` /
  `@@disable-two-factor-authentication`.
- `profiles/default/site_properties.xml`.
- Any password re-authentication gate (Phase 11), notification email (Phase 12), catalogue
  rebuild/translation (Phase 13), or relaxing the failed-attempt lockout (out of scope permanently).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MFA-15 | Pre-existing account is asked for a second factor at next login when `globally_enabled` is on | D-01's install-time enrollment target: `setuphandlers.setupVarious` (lines 81-97). A narrow, non-swallowing helper sets the flag for every user without minting a seed — see "Architecture Patterns > Install-time enrollment". |
| MFA-16 | With `globally_enabled` on, a user cannot turn their own second factor off | `browser/disable_two_factor_authentication.py` (40 lines, no condition today) gets the D-08 refusal. Verified: nothing else in the shipped code path clears `enable_two_factor_authentication` for a single user except this view — see "Don't Hand-Roll" for the one exception that must NOT be touched by this phase (the bulk disable view). |
| MFA-17 | With `globally_enabled` off, a user can enrol themselves from their own profile | `settings_helper.show_enable_two_factor_authentication_link` (lines 25-43) inverted per D-10. `@@setup-two-factor-authentication` (`browser/forms/user_setup.py`) is the existing, unchanged self-service target. |
| MFA-18 | Enrollment flow reachable whenever installed, whatever the global setting says | Same D-10 fix. Confirmed reachable at `permission="zope2.View"`, `for="*"` in `browser/configure.zcml:48-53` regardless of `globally_enabled`. |
| MFA-19 | System-enrolled user is shown the enrollment page before being asked for a code | The hard part. `pas_plugin.py` routing (D-05) + D-06(b)'s new property + the anonymous-reachability gap in `SetupForm` documented below (`token.py` vs `user_setup.py` mechanism mismatch) is the actual design work this phase must do. |

</phase_requirements>

## Summary

Four of the five requirements (MFA-16, 17, 18, and the "enrol the flag" half of MFA-15) are small,
mechanical, well-precedented changes to files this milestone's CONTEXT.md and ROADMAP.md already
name correctly, with line numbers that this session confirmed. The fifth, MFA-19, is where the
real design work is, and CONTEXT.md's own D-06 flags it honestly as unresolved. This research
settles it: **use mechanism (b), a new member-data property**, because mechanism (a) (sign an
enrollment URL for a seedless user by dropping the seed component from the signing key) collapses
the signing key's per-user entropy to something shared across every not-yet-enrolled user with the
same browser User-Agent, and there is no way to bound that cost without auditing the pinned `ska`
library's own signature construction — a much larger and riskier piece of work than adding one
memberdata property that this repository already has four precedents for.

The second, larger finding this research surfaces and CONTEXT.md does not: **the existing
enrollment view (`@@setup-two-factor-authentication` / `SetupForm`) has no mechanism to identify a
user from a signed URL.** It only works through `api.user.get_current()` — it assumes a live
session. But the login path clears the `__ac` cookie *before* redirecting (`pas_plugin.py:102`,
`send_2fa_redirect`), exactly as it does before redirecting to `@@google-authenticator-token`. The
token form (`browser/forms/token.py`) handles this by reading a signed `auth_user` query parameter
and calling `validate_user_data()` to authenticate the request itself, then calling
`self.context.acl_users.session._setupSession(...)` on success to actually log the user in
(`token.py:108-153`). `SetupForm` has none of this. Redirecting an unenrolled, cookie-cleared user
straight to `@@setup-two-factor-authentication` as CONTEXT.md's phrasing implies would land them
on a form that treats them as anonymous, shows no QR code (`updateFields` gates the barcode field
behind `is_anonymous() is False`, `user_setup.py:193`), and 401s on submit (`handleSubmit`'s first
line, `user_setup.py:69-70`). This is not a corner case; it is the exact path every MFA-15-enrolled,
never-seen-a-QR user will take at their next login. The plan must add signed-URL/`auth_user`
handling and a post-verification `_setupSession` call to the enrollment path, mirroring
`token.py`'s existing pattern, not simply point a redirect at the existing view.

**Primary recommendation:** implement D-06 with a new memberdata property (e.g.
`two_factor_authentication_enrolled`, following the existing naming convention), keep it off
`IEnhancedUserDataSchema` (internal state, same precedent as the lockout/replay counters), route in
`pas_plugin.py`/`send_2fa_redirect` by reading that property (a read, not a write — the existing
guard test already tolerates reads of `enable_two_factor_authentication` the same way), and extend
`SetupForm` (or a thin sibling view reusing its helpers) with the same anonymous signed-request
handling `TokenForm` already has, setting the new property and calling `_setupSession` once a
first token is verified.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Bulk enrollment at install | Install/GenericSetup handler (`setuphandlers.py`) | Memberdata (writes the flag) | D-01; runs once per profile application, inside the install transaction |
| Login-time routing decision (code page vs enrollment page) | PAS plugin / challenge boundary (`pas_plugin.py`) | Memberdata (reads two flags) | D-05; must happen before any URL is signed, and must not write |
| Signed-URL issuance | PAS plugin (`send_2fa_redirect`) | `ska` library (`helpers.sign_user_data`) | Existing mechanism; D-06 changes only which target URL gets signed |
| Anonymous identity resolution after redirect | Browser view (`token.py` today; `user_setup.py` needs the same) | `helpers.validate_user_data` | The one piece MFA-19 is missing; see Summary |
| Enrollment completion state | Memberdata property (new) | — | D-06(b); write happens only in the committing view, on first successful token verification |
| Self-disable refusal | Browser view (`disable_two_factor_authentication.py`) | Portal action visibility (`settings_helper.py`) | D-08/D-09; the view is the control, the action link is cosmetic |
| Link visibility (enable/disable/regenerate) | Portal actions (`actions.xml`) + `settings_helper.py` | — | D-10/D-11; see "Claims CONTEXT.md does not support" for a collateral-damage risk here |

## Standard Stack

No new package is introduced by this phase. Every mechanism needed (`ska` for URL signing,
`plone.registry` for the global setting, memberdata properties for per-user state,
`Products.GenericSetup` import steps for install-time work) is already a pinned, in-use dependency.
**Package Legitimacy Audit is not applicable** — no `npm install` / `pip install` equivalent for
this phase.

## Architecture Patterns

### System flow this phase changes

```
Login POST (password correct, 2FA flag set)
        |
        v
pas_plugin.authenticateCredentials()  [read-only: enable flag + NEW enrolled-flag]
        |  (decide target, do not sign yet -- D-05)
        v
_mark_2fa_pending(request, user, target)   <- request.other, not ZODB
        |
        v
IPubBeforeCommit subscriber (login POST)  OR  challenge() (Unauthorized path)
        |
        v
send_2fa_redirect(request, response)
        |  clears __ac cookie
        |  picks url= '@@google-authenticator-token'  (enrolled)
        |         or '@@<enrollment-target>'          (not yet enrolled -- NEW)
        |  sign_user_data(...)  -> mints seed here if absent (pre-existing, D-07's hazard)
        v
302 to signed URL, body cleared
        |
        v
Browser view reads auth_user + signature from the request (NOT a session)
   - token.py already does this (validate_user_data, then _setupSession on success)
   - the enrollment target needs the SAME pattern added -- it has none today
        |
        v
On first successful token verification: write the NEW "enrolled" property,
call _setupSession (this request had no session), THEN show recovery codes
exactly as the authenticated self-service path already does (RECOV-03).
```

### Install-time enrollment (D-01/D-02/D-04/D-13)

`setuphandlers.py:81-97` today:

```python
def setupVarious(context):
    if context.readDataFile('imio.googleauthenticator.marker.txt') is None:
        return
    portal = context.getSite()
    _setup_secret_key()
    pas = portal.acl_users
    _add_plugin(pas)
```

The marker-file gate (line 88) already proves another add-on's install never reaches this
function — `context.readDataFile` returns `None` for a profile that does not ship
`imio.googleauthenticator.marker.txt`, and `imio.dms.mail`'s or any other package's install
therefore returns at line 90 before `_setup_secret_key`/`_add_plugin`/the new call ever run. This
answers the "would installing another add-on re-trigger it?" question directly: **no**, confirmed
by the existing gate, not by inference.

Installing **this** add-on's own profile twice (reinstall/reapply) **does** re-run `setupVarious`
— `_add_plugin`'s own docstring (lines 52-57) says its ordering re-assertion runs "on *every*
profile application, not only on first install," which is only true because the marker-file gate
matches every time this profile (not another's) is applied. A new enrollment step added here would
run on every reapplication too. D-13's idempotency requirement is satisfiable trivially, the same
way `_add_plugin`'s own object-creation guard (`if pluginid not in installed`) is idempotent: guard
the per-user write on the current state, e.g.

```python
if is_two_factor_authentication_globally_enabled():
    for user in api.user.get_users():
        if not has_enabled_two_factor_authentication(user):
            user.setMemberProperties(
                mapping={'enable_two_factor_authentication': True})
```

Do **not** reuse `enable_two_factor_authentication_for_users` (`helpers.py:1031-1052`) as-is for
this. Two reasons, both already flagged in CONTEXT.md and confirmed here by reading it:

1. Line 1040 calls `get_or_create_secret(user)` **before** the `has_enabled_two_factor_authentication`
   check — D-02 explicitly does not want a seed minted at install.
2. Line 1050-1051's `except Exception as e: logger.debug(str(e))` swallows every per-user failure
   silently. D-04 requires the opposite: either everyone gets enrolled, or the operator is told
   plainly. A narrower helper (D-13's discretion) that does not wrap the loop body in a swallowing
   `except` satisfies this by construction — an unswallowed exception aborts the GenericSetup
   import step, which surfaces to whoever ran the install as a visible failure (a traceback in the
   ZMI / a failed `bin/test` setup / a failed buildout `make setup`), which **is** "reporting
   plainly" in an install context that has no `IStatusMessage` to write to. [ASSUMED: the exact
   rollback semantics of a raised exception inside a GenericSetup import step during Plone 4.3's
   add-on install were not verified against a live install in this session — no existing test in
   `test_setuphandlers.py` exercises an install-time exception path. Confidence: MEDIUM. If this
   matters for the plan's negative-path test, verify it with a real install rather than trusting
   this description.]

The existing `ValueError`-only-reraise branch (line 1044, `except ValueError: raise`) exists
*because* `get_or_create_secret` can raise it — irrelevant to install-time enrollment once the
seed-creation call is removed, since setting a boolean property raises nothing comparable.

### Routing decision and the `pas_plugin.py`/`send_2fa_redirect` boundary (D-05/D-07)

`pas_plugin.py:197-202` today reads only one flag:

```python
two_factor_authentication_enabled = user.getProperty(
    'enable_two_factor_authentication')
```

D-05's routing decision needs a second, read-only fact at the same point: whether this user has
completed enrollment. Both reads happen before `_mark_2fa_pending(self.REQUEST, user)` (line 263)
— which already is the "decide, don't act" seam this plugin uses today; it needs to carry one more
piece of information (which page to send the user to) alongside the existing user-id payload.
`send_2fa_redirect` (`pas_plugin.py:77-135`) is where the actual signed URL gets built
(`sign_user_data(request=request, user=user, url='@@google-authenticator-token')`, line 104-105);
that `url=` argument is the one thing that needs to vary per the routing decision.

D-07's hazard (WR-01/WR-02) is: `sign_user_data` → `get_or_create_secret` → `get_ska_secret_key`
all run inside `send_2fa_redirect`, which is reached from `IPubBeforeCommit`/`challenge()`, **after**
the transaction that would otherwise carry a clean refusal has already committed its decision to
redirect. If `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` is unset or broken, `get_or_create_secret` (for a
seedless MFA-15-enrolled user, which is now the *common* case, not an edge case) raises `ValueError`
inside this call chain, which — per the existing `RENAME-11` `_dont_swallow_my_exceptions` design —
is not swallowed and surfaces as an uncontrolled 500, not the clean refusal `get_secret()`'s
synchronous check inside `authenticateCredentials` (line 257, `get_secret(user)`) already produces
for *enrolled* users with a *broken* stored seed. This 500 risk is pre-existing (recorded in
STATE.md as WR-01/WR-02) and this phase does not have to fix it, but it moves onto the critical
path here because MFA-15 is what puts flag-set/no-seed accounts into normal existence at scale.
**Recorded for the plan, not solved by this research:** if the plan wants a controlled refusal
here rather than accepting the pre-existing 500, it needs a synchronous seed-encryption-key check
before the redirect decision, mirroring what `get_secret(user)` already does at
`pas_plugin.py:257` for the enrolled branch — but that call is a pure read and cannot itself
create a seed to check against for a never-enrolled user, so this may not be closable without
also touching `get_ska_secret_key`'s key-presence check (`helpers.py:818-828`, which already
raises `ValueError` if `ska_secret_key` itself, the site-wide component, is empty — this part
already fails closed with a clear message; it's the *user-seed* component's absence that is the
new gap).

### D-06 settled: mechanism (b), with the exact cost of (a) shown

`sign_user_data` (`helpers.py:857-886`) calls `get_or_create_secret(user)` unconditionally at
**line 878**, confirmed. `get_ska_secret_key` (`helpers.py:787-844`) composes its key as:

```python
user_secret = user.getProperty('two_factor_authentication_secret') or ''
...
return u''.join(
    u'{0}:{1}'.format(len(part), part)
    for part in (user_secret, browser_hash, ska_secret_key))
```

`get_ska_secret_key` itself does **not** raise for a missing `user_secret` — it coerces to `''`
(line 834, the `or ''`). The `ValueError`-on-seedless-signing behaviour comes entirely from
`sign_user_data`'s own prior call to `get_or_create_secret`, not from `get_ska_secret_key`. This
means mechanism (a) — "skip minting, sign anyway" — is *mechanically* simple: skip the
`get_or_create_secret` call for this one redirect path and let `user_secret` come through as `''`.

The cost is what CONTEXT.md's D-06 note gestures at but does not fully spell out, and this
research settles it: with `user_secret == ''`, the composite signing key for **every** currently
unenrolled user reduces to `browser_hash` (a SHA1 of the `User-Agent` header — attacker-supplied,
low-entropy, shared by every user of the same browser/OS combination) plus the one site-wide
`ska_secret_key`. That is: the per-user entropy this signing scheme is designed to provide
(`two_factor_authentication_secret`, unique per account) disappears entirely for the one
population this phase newly creates at scale (every pre-existing account, right after install).
Whether this is *exploitable* depends on exactly how the pinned `ska==1.7.5` library constructs
its signature from `secret_key` (a proper keyed MAC would still bind the signature to the specific
`auth_user` in the signed payload even with a shared key; a weaker construction might not) —
auditing that is out of scope for this research and would be a materially larger effort than
adding one property. **This is the "solving the signing-key problem" D-06 refers to, and it is not
solved here; it is why (b) is recommended instead.**

Mechanism (b) is bounded and precedented four times already in this exact codebase
(`two_factor_authentication_failed_attempts`, `_locked_until`, `_last_interval`,
`_recovery_codes_salt`/`_hashes` — all memberdata-only, all undeclared on
`IEnhancedUserDataSchema`). The verification brief for this research asked whether the schema
declaration + adapter accessor steps are needed; **the codebase's own precedent, stated explicitly
in `userdataschema.py`'s docstring at lines 64-74, says no**:

> "The replay and lockout counters ... are deliberately NOT declared here. They are internal
> state ... Declaring them here would render them on every profile form this package does not
> override — crashing `@@user-information` with `AttributeError`, since `adapter.py` supplies no
> accessor for them — and would make a user's own lockout deadline form-writable."

A new "has completed enrollment" property is exactly this kind of internal state — nothing a user
should read or edit through any profile form. **Recommendation: `memberdata_properties.xml` entry
only, no `IEnhancedUserDataSchema` field, no `adapter.py` accessor**, following the counter
precedent exactly, not the fuller schema+adapter shape the verification brief described generically
for "mechanism (b)."

**Whether an existing property already carries this signal implicitly (checked, as asked):**
`two_factor_authentication_recovery_codes_hashes` (written by `generate_recovery_codes`,
`helpers.py:626-654`, called from `user_setup.py:149` only *after* a first successful token
verification) is non-empty exactly for a user who has completed enrollment at least once — a
tempting reuse. **It is not safe to reuse as the sole signal.** `validate_recovery_code`
(`helpers.py:657-739`) *consumes* a matched code by removing it from the stored tuple
(lines 709-711); a user who has used all ten recovery codes over time (the exact scenario the
recovery-code feature exists for — a lost device, repeatedly) would have this property regress to
an empty tuple, which is indistinguishable from "never enrolled" by this signal alone, and would
wrongly route a fully-enrolled user back to the enrollment/QR page at their next login. A dedicated
property that is set once, on first success, and never cleared by normal recovery-code consumption
is required.

### The gap CONTEXT.md does not name: `SetupForm` has no anonymous/signed-URL path

Confirmed by reading both views side by side:

- `browser/configure.zcml:24-29` and `:48-53` register `@@google-authenticator-token`
  (`token.py`) and `@@setup-two-factor-authentication` (`user_setup.py`) **identically**:
  `for="*"`, `permission="zope2.View"`. Both are reachable by an anonymous request at the
  permission-declaration level.
- `token.py`'s `TokenForm.handleSubmit` (lines 90-178) reads `self.request.get('auth_user', '')`
  (line 108), calls `validate_user_data(request=self.request, user=user)` (lines 115-116) to
  authenticate the *request itself* against the `ska` signature — no session, no cookie needed —
  and on a valid token calls `self.context.acl_users.session._setupSession(username, ...)`
  (lines 152-153) to establish the session that did not exist when the request arrived.
- `user_setup.py`'s `SetupForm.handleSubmit` (lines 68-71) does the opposite: `if
  bool(api.user.is_anonymous()) is True: ... setStatus(401...); return False` — it refuses
  immediately for exactly the request state `send_2fa_redirect` creates (cookie cleared,
  line 102 of `pas_plugin.py`). Its `updateFields` (lines 189-212) additionally hides the QR-code
  field description entirely when anonymous (the `if bool(api.user.is_anonymous()) is False:`
  guard at line 193 wraps the whole barcode-rendering block).

**Consequence for the plan:** redirecting an MFA-15-enrolled, never-seen-a-QR user straight to
`@@setup-two-factor-authentication` produces a 401-on-submit, QR-less form — the exact lockout
MFA-19 exists to prevent, reached by a different mechanism than the one D-06's note describes. The
plan must give the enrollment target the same `auth_user`+signature identity resolution `token.py`
has, and the same post-verification `_setupSession` call, before a QR/secret can be shown and a
token accepted from a signed-but-sessionless request. Two shapes are viable; this research does not
pick one, since it is implementation-shape, not a locked decision:

- **(A) Extend `SetupForm` in place**, branching on presence of a valid `auth_user` param the same
  way `token.py` branches on it, and calling `_setupSession` in the success branch when the
  request arrived anonymous-but-signed. Reuses `get_token_description`, `validate_token`,
  `generate_recovery_codes` untouched. Risk: `test_user_setup.py` (29KB, the largest test module
  besides `test_helpers.py`) exercises the authenticated self-service path extensively; any change
  to `is_anonymous()` gating must preserve every one of those tests' preconditions exactly, or
  they will need co-updating alongside the new branch.
- **(B) A new, narrow view** dedicated to the anonymous/signed enrollment redirect, built from the
  same helpers, leaving `SetupForm` completely untouched. Costs a new file/view registration; buys
  isolation from the existing self-service test suite.

Given this repo's "Don't Hand-Roll" and reuse-what-exists conventions (see below), **(A) is the
lighter-weight choice**, but the planner should weigh it against the blast radius on
`test_user_setup.py` before committing either way in the PLAN.md.

### Recommended shape for `settings_helper.py` (D-10/D-11)

```python
# D-10 (MFA-17/MFA-18): offer the enable link whenever the user is not
# enrolled, regardless of the global setting.
def show_enable_two_factor_authentication_link(self):
    if api.user.is_anonymous():
        return False
    user = api.user.get_current()
    return not has_enabled_two_factor_authentication(user)

# D-11 (MFA-16 mirror): offer the disable link only when the user is
# enrolled AND the global setting is off (self-enrolled users only).
def show_disable_two_factor_authentication_link(self):
    if api.user.is_anonymous():
        return False
    user = api.user.get_current()
    return (
        has_enabled_two_factor_authentication(user) and
        not is_two_factor_authentication_globally_enabled()
    )
```

Both docstrings (lines 26-34, 46-54) already state this intended behaviour in prose; only the
`is_two_factor_authentication_globally_enabled() and` clause needs inverting/removing, confirmed
by reading the file directly — this is not a subtle judgement call, the code and its own comment
disagree today exactly as CONTEXT.md says.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Identifying a user from a request with no session | A new ad-hoc signed-token scheme | `helpers.validate_user_data` / `sign_user_data`, exactly as `token.py` already uses them | This is the one mechanism this whole package is built around; a second one for enrollment would be an unreviewed second attack surface |
| Establishing a session after anonymous verification | Setting `__ac` manually | `self.context.acl_users.session._setupSession(username, response)` — `token.py:152-153`'s existing call | Already the one place in this codebase that does this; copying it is lower-risk than a new construction |
| Bulk per-user enrollment loop | A second copy of `enable_two_factor_authentication_for_users`'s loop with different behaviour bolted on | A narrow sibling helper, or a parameterised version of the same function (implementer's choice per D-13) | The existing function's loop/guard shape (`if not has_enabled_two_factor_authentication`) is correct; only the seed-minting call and the exception-swallowing need to differ |

**Key insight:** every mechanism this phase needs already exists somewhere in this file tree in a
tested form (signed-URL identity resolution, session setup, per-user bulk iteration, internal-state
memberdata properties). The work is composition and one new property, not new cryptography or a
new state-storage pattern.

## Common Pitfalls

### Pitfall 1: Trusting D-06's "no seed" framing to mean "no signing-key change needed"

**What goes wrong:** implementing D-05's routing without also touching `send_2fa_redirect`'s
target-URL selection, then discovering at test time that the enrollment page 401s.
**Why it happens:** the CONTEXT.md phrasing describes the *destination* (enrollment page) but the
existing `SetupForm` genuinely cannot serve an anonymous, cookie-cleared request — this is not
obvious without reading `user_setup.py`'s `is_anonymous()` guards directly (done in this session).
**How to avoid:** treat "make `@@setup-two-factor-authentication` reachable from the login-redirect
path" as its own explicit task, not a side effect of picking a URL string.
**Warning signs:** a manual/functional test where the redirect lands correctly but shows no QR
code, or a 401 on the first token submission.

### Pitfall 2: The `regenerate_recovery_codes` portal action silently loses visibility

**What goes wrong:** `profiles/default/actions.xml:41-52`'s `regenerate_recovery_codes` action
reuses `show_disable_two_factor_authentication_link` as its own `available_expr` (line 47,
explained in the surrounding comment as "reuses the same view ... rather than adding a fourth
`SettingsHelper` method"). D-11 changes that method's meaning to "enrolled AND global setting is
off." Applying D-11 with no other change makes "Regenerate recovery codes" disappear from the menu
for every user under global enforcement — a user who never asked to disable anything loses the
ability to regenerate their own codes purely as a side effect of the MFA-16 fix.
**Why it happens:** the two concerns (disable-eligibility, regenerate-eligibility) were
deliberately collapsed onto one predicate before this phase's requirements existed, and CONTEXT.md
does not mention this coupling at all — it was not visible without reading `actions.xml` directly.
**How to avoid:** give `regenerate_recovery_codes` its own `available_expr` — either a new
`SettingsHelper.show_regenerate_recovery_codes_link` (just "user is enrolled," no global-setting
term at all) or point it at `show_enable_two_factor_authentication_link`'s logical negation. This
was not asked for by any locked decision, so flag it in the plan rather than silently "fixing" it
outside the phase's stated scope, but it must not ship broken.
**Warning signs:** manual UAT of criterion 3/4 (globally_enabled on) finds "Regenerate recovery
codes" missing from the personal menu for an already-enrolled user.

### Pitfall 3: Believing the "no site-wide un-enroll exists" framing

**What goes wrong:** assuming MFA-16's per-account refusal (D-08) is the only lever that can turn
off a user's second factor, when planning what to leave alone.
**Why it happens:** CONTEXT.md's Deferred Ideas section says the disable-for-all-users path "is
commented out and only writes a debug log line" — true for `controlpanel.py`'s `handleSave`
button (line 152, `# disable_two_factor_authentication_for_users(users)` is commented out) —
**but there is a second, live, entirely separate view that is not commented out**:
`browser/disable_two_factor_authentication_for_all_users.py`'s
`DisableTwoFactorAuthenticationForAllUsers.index()` (lines 19-31) calls
`disable_two_factor_authentication_for_users(users)` unconditionally, with **no `globally_enabled`
check at all**, and is wired to a real, rendered link in the control panel's
`additional_template` (`controlpanel.py:104-112`, `disable_url=...
@@google-authenticator-disable-for-all-users`, registered at `permission="cmf.ManagePortal"` in
`configure.zcml:72-79`). An administrator clicking that link while `globally_enabled` is `True`
mass-disables every user's second factor in one click — a working bypass of MFA-16's intent at
scale, that D-08's single-view refusal does not touch because it lives in a different view
entirely.
**How to avoid:** this is explicitly out of scope for this phase per CONTEXT.md's Deferred Ideas
("revisit only if an operator actually needs it") — but the plan should record this precisely
(this research does, above) rather than let the phase close believing the claim in
CONTEXT.md/ROADMAP.md was fully accurate. It was not; only the `handleSave` half of it was.
**Warning signs:** none for this phase's own tests — this is a pre-existing gap, not something
Phase 10 introduces or is required to close.

## Code Examples

### Existing anonymous identity resolution to mirror (`token.py:107-153`)

```python
# Source: src/imio/googleauthenticator/browser/forms/token.py
user = None
username = self.request.get('auth_user', '')
if username:
    user = api.user.get(username=username)
    user_data_validation_result = validate_user_data(
        request=self.request, user=user)
    if not user_data_validation_result.result:
        IStatusMessage(self.request).addStatusMessage(...)
        return
...
if valid_token:
    if user is not None:
        reset_failed_second_factor(user)
    self.context.acl_users.session._setupSession(
        username, self.context.REQUEST.RESPONSE)
```

### Existing internal-state-property precedent to copy for D-06(b) (`memberdata_properties.xml`)

```xml
<!-- Source: src/imio/googleauthenticator/profiles/default/memberdata_properties.xml -->
<property name="two_factor_authentication_failed_attempts" type="int">0</property>
```

A new boolean property for "has completed enrollment" follows this exact one-line pattern
(`type="boolean"`, default `False`), same file, no other file touched for its persistence — the
schema/adapter exposure the generic mechanism-(b) description implies is explicitly *not* part of
this repo's own precedent (see D-06 discussion above).

### Idempotent per-user guard already proven in this codebase (`setuphandlers.py:58-61`)

```python
# Source: src/imio/googleauthenticator/setuphandlers.py, _add_plugin
installed = pas.objectIds()
if pluginid not in installed:
    plugin = GoogleAuthenticatorPlugin(pluginid, title=PAS_TITLE)
    pas._setObject(pluginid, plugin)
```

The same "check current state before writing" shape is the right model for the install-time
per-user enrollment loop.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A raised exception inside `setuphandlers.setupVarious` during a GenericSetup profile import aborts that import step visibly (traceback/failed install) rather than being silently swallowed by QuickInstaller. | Architecture Patterns > Install-time enrollment | If wrong, D-04's "report plainly" requirement is not met by "just let it raise," and the plan needs an explicit `try/except` that surfaces an operator-visible message through some other channel (there is no `IStatusMessage` target during a GenericSetup import). |
| A2 | The pinned `ska==1.7.5` library's `sign_url`/`validate_signed_request_data` implement a proper keyed MAC over the full signed payload (including `auth_user`), such that mechanism (a)'s reduced per-user entropy does not immediately enable cross-user forgery, only a reduction in defense-in-depth. | D-06 settled section | Not verified by reading `ska`'s source in this session — if `ska`'s construction is weaker than a standard HMAC (e.g. vulnerable to length-extension or key-reuse issues), mechanism (a)'s cost could be worse than described (a genuine forgery path), which would make mechanism (b) even more clearly correct — this assumption does not change the recommendation, only how strongly the cost of (a) should be described. |
| A3 | Option (A) for the anonymous-enrollment gap (extend `SetupForm` in place) is lower-risk than option (B) (a new dedicated view), based on this repo's general reuse conventions. | Architecture Patterns > "gap CONTEXT.md does not name" | This is a judgement call, not a locked decision; if `test_user_setup.py`'s existing preconditions turn out to be extensively coupled to `is_anonymous()` being a hard gate, option (B) may actually be cheaper. The plan should re-evaluate this once it reads `test_user_setup.py` in full. |

## Open Questions

1. **Exact target view/URL name for the anonymous enrollment redirect.**
   - What we know: it must resolve identity from a signed `auth_user` param (like `token.py`), and
     must call `_setupSession` on first success.
   - What's unclear: whether it reuses `@@setup-two-factor-authentication` (option A above) or a
     new view name (option B). Not locked by CONTEXT.md — Claude's Discretion territory, but
     material enough to the plan's task breakdown that it should be decided explicitly in
     PLAN.md, not discovered mid-implementation.
   - Recommendation: default to option (A) unless reading `test_user_setup.py` in full during
     planning surfaces a reason not to.

2. **Whether the install-time exception-propagation behaviour (A1 above) actually satisfies D-04
   without further work.**
   - What we know: the code-level mechanism (let it raise) is simple and consistent with this
     repo's "loud failure over silent" convention elsewhere (`handleSave`'s own `ValueError`
     handling reports an explicit `IStatusMessage`, but that is a form submission with a request
     to write to — `setupVarious` is not).
   - What's unclear: what an administrator running `bin/instance` against a real site actually
     sees when a GenericSetup import step raises during add-on activation via the Plone UI.
   - Recommendation: treat this as a Wave-0-style verification item during planning — a real (or
     `plone.app.testing`-layer) install-time-exception test settles it cheaply.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` | Any path that calls `get_or_create_secret`/`sign_user_data`/`decrypt_seed` — now reachable at scale via MFA-15/MFA-19 | ✗ in this dev/research environment (per `.planning/STATE.md`'s "Outstanding outside this roadmap": only `base.cfg`'s `[testenv]` sets it, `bin/instance` does not) | — | `bin/test`/`bin/test-coverage` set it per-test (confirmed: `tests/test_pas_plugin.py:37` sets `os.environ[helpers.ENV_VAR_NAME] = Fernet.generate_key()` in `setUp`); no fallback exists for a real deployed instance — this is the pre-existing, out-of-repo blocker STATE.md already tracks, unaffected by this phase |

**Missing dependencies with no fallback:** none new — the seed key gap is pre-existing and outside
this repository's commits (tracked in STATE.md; not this phase's problem to close).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `zope.testrunner` via `bin/test` (buildout `[test]` part), `unittest2.TestCase` + this repo's `BaseTest` mixin (`tests/base.py`) |
| Config file | none dedicated — driven by `test-4.3.cfg`/`base.cfg` buildout parts; coverage scoped by `.coveragerc` (`source = src/imio/googleauthenticator`, `branch = True`) |
| Quick run command | `bin/test -t test_setuphandlers` / `-t test_disable_two_factor_authentication` / `-t test_pas_plugin` (per-module; per CLAUDE.md's documented pattern `bin/test -t test_product_is_installed`) |
| Full suite command | `bin/test -t \!robot` (Makefile `test` target) or `bin/test-coverage -t \!robot` for the coverage-gated run |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MFA-15 | Install-time bulk enrollment sets the flag for every pre-existing user, no seed minted | integration | `bin/test -t test_setuphandlers` (new test method) | ✅ extend `tests/test_setuphandlers.py` (1097 lines, 22 existing test methods, none covering per-user enrollment today) |
| MFA-15 (D-04) | Install does not silently partial-enrol | integration | `bin/test -t test_setuphandlers` (new negative test, e.g. inject a `setMemberProperties` failure for one user and assert the exception propagates) | ✅ same file |
| MFA-16 | Self-disable refused while `globally_enabled` is on; flag/seed/token unchanged | unit/integration | `bin/test -t test_disable_two_factor_authentication` | ✅ extend `tests/test_disable_two_factor_authentication.py` (116 lines, 3 existing methods, none covering the `globally_enabled` gate — it does not exist in source yet) |
| MFA-17/MFA-18 | Enable/disable link visibility inverted per D-10/D-11 | unit | `bin/test -t test_settings_helper` (new file) | ❌ **no `test_settings_helper.py` exists at all** — zero pre-existing coverage of `settings_helper.py`; this is the one module the plan must create tests for from scratch, not extend |
| MFA-19 | Flag-set-but-unenrolled user is routed to the enrollment page, not the token page; can complete enrollment from a signed, sessionless redirect | integration | `bin/test -t test_pas_plugin` (routing decision) + `bin/test -t test_user_setup` (anonymous/signed submission path, new tests) | ✅ both files exist; both need substantial new coverage, not just extension of an existing case |
| D-06(b) property | Set/get round-trip, declared in `memberdata_properties.xml` | unit | `bin/test -t test_adapter` or a new small module, per this repo's existing round-trip-test convention for undeclared internal properties (see `tests/test_adapter.py`'s docstring reference at `userdataschema.py:74`) | ✅ `tests/test_adapter.py` exists and already documents this convention for the lockout/replay counters — follow the same shape |

### Sampling Rate

- **Per task commit:** the single most relevant module (`bin/test -t test_<module>`)
- **Per wave merge:** `bin/test -t \!robot` (full suite, no coverage gate)
- **Phase gate:** `bin/test-coverage -t \!robot` (branch coverage ≥ 90%, per the Standing Constraint)
  green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_settings_helper.py` — does not exist; needed for MFA-16/17/18's link-condition
      correctness (D-10/D-11) and for Pitfall 2's `regenerate_recovery_codes` collateral check
- [ ] No existing test exercises an exception raised from inside `setuphandlers.setupVarious` —
      needed to settle Assumption A1 before trusting D-04's "report plainly" wording is satisfied
      by "let it raise"
- [ ] No existing test exercises `SetupForm`/`user_setup.py` with an anonymous request carrying a
      valid signed `auth_user` param (the mode MFA-19 needs) — `test_user_setup.py` (29KB) is
      entirely authenticated-session-based today per its existing test names

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | This phase changes *routing* within the existing PAS/`ska`-signed-URL authentication mechanism; no new authentication primitive is introduced. Reuse `helpers.validate_user_data`/`sign_user_data` exactly as `token.py` does — do not invent a second signing scheme (see Don't Hand-Roll) |
| V3 Session Management | yes | `_setupSession` is Zope's own session plugin call, already used by `token.py`; the enrollment path must call it identically, not roll a custom cookie/session write |
| V4 Access Control | yes | D-08's self-disable refusal is the access-control decision this phase adds; it must live in the view (server-side), never rely on the hidden link (D-09) — client-side/UI-only hiding is not a control |
| V5 Input Validation | yes (pre-existing, unchanged) | `_is_six_digit_token`/`_is_recovery_code_shape` in `helpers.py` already gate token shape before any decrypt/HMAC work; this phase adds no new user-controlled input surface beyond the existing `auth_user`/signature pair `token.py` already validates |
| V6 Cryptography | yes (pre-existing, unchanged by this phase's recommendation) | `ska`'s HMAC-style signing and `cryptography.fernet` seed encryption are unchanged. **Mechanism (a), if chosen against this research's recommendation, would be a V6-relevant change** (reducing signing-key entropy for a whole user population) and would need its own threat-model note if pursued |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Signed-URL replay/reuse across users if the signing key loses per-user binding | Spoofing | Keep the seed (per-user secret) as one of the three signing-key components for every signed URL, including any new enrollment-redirect URL — this is exactly why mechanism (b), not (a), is recommended |
| Bulk-disable link with no `globally_enabled` gate undermining a per-account refusal | Elevation of Privilege (admin action bypasses a user-facing control's intent) | Out of scope for this phase per CONTEXT.md's Deferred Ideas, but recorded precisely above (Pitfall 3) so it is not lost |
| Portal-action visibility used as if it were the access-control decision | Tampering (a hidden-but-not-refused action is reachable by direct URL) | D-08/D-09 already correctly separate "hide the link" (cosmetic) from "refuse in the view" (the actual control) — preserve this separation for MFA-19's new routing too: the enrollment redirect target must refuse a code-entry-page submission for an unenrolled user server-side, not merely avoid linking to it |

## Sources

### Primary (HIGH confidence — read directly this session, with line numbers cited throughout)

- `src/imio/googleauthenticator/setuphandlers.py` (162 lines, full file read)
- `src/imio/googleauthenticator/pas_plugin.py` (306 lines, full file read)
- `src/imio/googleauthenticator/helpers.py` (1229 lines, full file read)
- `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py` (41 lines, full file)
- `src/imio/googleauthenticator/browser/settings_helper.py` (64 lines, full file)
- `src/imio/googleauthenticator/browser/forms/user_setup.py` (217 lines, full file)
- `src/imio/googleauthenticator/browser/forms/token.py` (217 lines, full file)
- `src/imio/googleauthenticator/browser/controlpanel.py` (171 lines, full file)
- `src/imio/googleauthenticator/browser/enable_two_factor_authentication_for_all_users.py` (full)
- `src/imio/googleauthenticator/browser/disable_two_factor_authentication_for_all_users.py` (full)
- `src/imio/googleauthenticator/browser/configure.zcml` (full file)
- `src/imio/googleauthenticator/subscribers.py` (full file)
- `src/imio/googleauthenticator/userdataschema.py` (full file)
- `src/imio/googleauthenticator/adapter.py` (full file)
- `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` (full file)
- `src/imio/googleauthenticator/profiles/default/actions.xml` (full file)
- `src/imio/googleauthenticator/tests/test_pas_plugin.py` (489 lines, full file, incl. the D-06
  routing guard test `test_no_second_factor_state_written_from_the_plugin`)
- `src/imio/googleauthenticator/tests/test_disable_two_factor_authentication.py` (full file)
- `src/imio/googleauthenticator/tests/test_setuphandlers.py`, `test_controlpanel.py`,
  `test_helpers.py` (test-method inventories, not full read)
- `.planning/phases/10-global-enforcement-and-enrollment/10-CONTEXT.md`,
  `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md`,
  `.planning/milestones/v1.0-phases/07-coexistence-with-imio-dms-mail/07-UAT.md:95-136`,
  `.planning/config.json` (full read for `workflow.nyquist_validation`/`security_enforcement`)
- `CLAUDE.md`, `.claude/CLAUDE.md` (project constraints)

### Secondary (MEDIUM confidence)

- General knowledge of Plone/GenericSetup import-step transaction behaviour, used only for
  Assumption A1 — not verified against a live install in this session.
- General knowledge of HMAC/keyed-MAC security properties, used to reason about mechanism (a)'s
  cost without auditing `ska==1.7.5`'s own source (Assumption A2).

### Tertiary (LOW confidence)

None — this research performed no web search or external documentation lookup; all findings are
either direct source reads (HIGH) or explicitly flagged reasoning/assumptions (MEDIUM, logged
above).

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new dependency
- Architecture (routing, signing, install-time enrollment mechanics): HIGH — every claim traced to
  a specific file and line range read in this session
- The D-06 mechanism choice: MEDIUM — the recommendation (b) is well-supported by repo precedent
  and a structural argument against (a); the *exact* residual risk of (a) is bounded by an
  unaudited third-party library (Assumption A2)
- Pitfalls (especially the `SetupForm` anonymous-reachability gap and the `regenerate_recovery_codes`
  action coupling): HIGH — both are directly observable in the source, not inferred

**Research date:** 2026-08-06
**Valid until:** Stable until the underlying source files change — this is an internal-source
research artifact, not tied to an external library's release cadence. Re-verify line numbers if
Phase 9's commits or this phase's own early plans touch any of the files listed under Sources
before this document is consumed.
