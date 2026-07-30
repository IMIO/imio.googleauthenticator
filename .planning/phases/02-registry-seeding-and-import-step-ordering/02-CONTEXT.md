# Phase 2: Registry Seeding and Import-Step Ordering - Context

**Gathered:** 2026-07-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Installing this add-on seeds the `IGoogleAuthenticatorSettings` registry records reliably instead
of relying on CPython 2.7 string-hash order over GenericSetup step ids; the ordering that makes it
work is *declared* (`<depends name="plone.app.registry"/>`) and *asserted* in the suite; the nested
`runImportStepFromProfile` re-entry is gone, with `ska_secret_key` minted by a lazy accessor; and
the derived `ska` signing key stops being a bare concatenation of its three components.

Requirements: REG-01 … REG-05, BUG-04.

**Not this phase:** seed encryption and the `SKA_*`/Fernet key handling (Phase 3), the PAS
credentials-boundary rework (Phase 4), replay + lockout state (Phase 5), recovery codes (Phase 6),
override deletion and `id = 'login_form'` (Phase 7), lint debt and coverage (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### REG-01 verification strategy — *discussed*

- **D-01:** REG-01 is proven by the **ordering assertion only**. No manual site-creation run is
  performed and recorded, and no automated second-site fixture
  (`addPloneSite(app, ..., extension_ids=(...))`) is added. Rejected the automated route on cost:
  a real second Plone site inside the layer is ~30–60s of suite time on a suite Phase 8 already
  has to repair. Rejected the manual-run-and-paste route as evidence that decays the moment
  anything else changes.

- **D-02:** ROADMAP success criterion 1 ("Creating a new Plone site … completes with no
  `IGoogleAuthenticatorSettings defines a field ska_secret_key, for which there is no record` in
  `var/log/instance.log`") is carried in `must_haves` as a **structured backstop marker** —
  `{ statement: <the check>, verification: backstop }` — not as a plain truth and not as a
  parenthetical note. Consequence, and the point of choosing it: at verify time the verifier
  cannot confirm it from any artifact, so it abstains to `human_needed` rather than silently
  passing. This is the honest disposition given D-01, and it is the *only* must_have in this
  phase that is not machine-checkable.

- **D-03:** The mechanised control asserts **both halves**, as two assertions:
  1. *Ordering* — `steps = portal.portal_setup.getSortedImportSteps()`, then
     `steps.index('imio.googleauthenticator') > steps.index('plone.app.registry')`. This is
     REG-03 as written, and it is what catches someone deleting the `<depends>` line.
  2. *Outcome* — after the profile is applied, all three `IGoogleAuthenticatorSettings` records
     exist and `get_app_settings()` returns without raising. This is the property the original
     bug report was actually about, and it survives any future restructuring away from `<depends>`.

  Ordering-only was rejected because it is tied to one mechanism; outcome-only was rejected
  because REG-03 names `getSortedImportSteps()` explicitly.

### Claude's Discretion

Three areas the user chose not to discuss. Decisions taken and recorded so downstream agents do
not re-open them.

#### Lazy mint mechanics (REG-04)

- **D-04:** `_setup_secret_key` is **deleted outright** — both the nested
  `runImportStepFromProfile` and the seeding that followed it. `setupVarious` is left doing only
  the marker-file guard and `_add_plugin`. No install-time seeding is retained as a fallback:
  keeping it would put a registry read back inside the import step, which is the exact coupling
  REG-04 exists to remove.

- **D-05:** The mint lives **inside `get_ska_secret_key()`**, unconditionally, as a single
  `if not ska_secret_key:` branch. No `create=` keyword argument and no separate
  `get_or_create_ska_secret_key()` wrapper — one branch, one birthplace for the key. Randomness
  stays `unicode(uuid4())`, unchanged from the deleted `_setup_secret_key`; raising the site key's
  entropy is not asked for by any Phase 2 requirement and belongs with Phase 3's `SEC-06` work
  (see Deferred Ideas).

- **D-06:** Two consequences of D-05 are **accepted, with reasons recorded**, so they are not
  rediscovered as bugs:
  - *The mint can fire from the PAS plugin.* `pas_plugin.py:160` calls `sign_user_data` →
    `get_ska_secret_key`, and PROJECT.md's constraint is that writes on that path are lost when the
    request aborts. Accepted because the failure is self-healing rather than silent: a lost mint
    means the URL just signed will not validate, the user retries, and the next request mints
    again. It is not the lockout-counter hazard that constraint was written for — losing a counter
    increment means the lock never locks, whereas losing a mint means one failed login.
  - *The mint can fire from an unauthenticated request.* `validate_user_data` (`token.py:87`,
    `reset_bar_code.py:150`) also routes through `get_ska_secret_key`. Accepted: the write is
    idempotent, bounded to once per site, and reaches the same state the first login attempt would
    have reached anyway.
  - *Concurrent mints across ZEO clients resolve correctly.* Two clients writing the same registry
    record conflict, ZODB retries the request, and the retry re-reads the now-committed non-empty
    value and skips the branch. This is the same merge-and-retry reasoning PROJECT.md already
    records for `OOBTree` storage.

- **D-07:** When the record is **missing entirely** (not merely empty), `get_app_settings()`'s
  `KeyError` **propagates**. It is not caught, and `forInterface(check=False)` is not used —
  research names that as the escape hatch that converts a loud `KeyError` into an `AttributeError`
  deeper in the stack. With `_dont_swallow_my_exceptions = True` live from Phase 1, that surfaces
  as a 500, which is the correct fail-closed behaviour for an MFA package.

#### `ska` key separation (BUG-04)

- **D-08:** `helpers.py:259`'s `"{0}{1}{2}".format(user_secret, browser_hash, ska_secret_key)` is
  replaced with a **length-prefixed join** — each component rendered as `<len>:<value>` and
  concatenated, netstring-style. A single-delimiter scheme (`u"|".join(...)`) was rejected: it is
  only safe while no component can contain the delimiter, and Phase 3 changes `user_secret` into a
  `v1$<fernet token>` ciphertext, so the "this character can't appear" argument expires one phase
  from now. An HMAC-based derivation was rejected as overkill — the stated defect is collidability,
  not weak derivation, and hashing on the login path buys nothing here.
  — **Reversibility:** costly — the derivation feeds `sign_user_data`, `validate_user_data` and
  `request_bar_code_reset.py:66`; changing it later invalidates every signed token URL in flight
  and every outstanding bar-code-reset email link. Free *now* only because nothing is deployed and
  no users are enrolled, which is precisely why this sits in Phase 2 rather than later.

- **D-09:** `get_browser_hash` (`helpers.py:210-224`) is fixed **in this phase** to
  `return ''` from its `except` branch. Today it falls off the end and returns `None`, which
  `format()` renders as the literal string `"None"`; under D-08's length-prefixing, `len(None)`
  raises `TypeError` instead — so BUG-04 converts a latent wrong-key bug into a crash on a login
  path, and the two changes must land together. `''` is the right value: it is exactly what
  `use_browser_hash=False` already produces, and a client with no `User-Agent` gets no device
  binding either way — the current `"None"` is a constant, so it binds nothing today. No security
  regression, and it matches how Phase 1 fixed the three other crash-on-ordinary-input paths.

#### Import-step guard scope (REG-02)

- **D-10:** Keep the custom import step and add `<depends name="plone.app.registry"/>` to it in
  `configure.zcml:44-49`. `post_handler` (research's Pitfall 7 option 2) is **rejected**: it is not
  run by `runImportStepFromProfile` nor by upgrade steps, and that caveat costs more than the
  ordering guarantee is worth when one `<depends>` line achieves the same thing.

- **D-11:** The `<depends>` is retained **even though D-04 leaves `setupVarious` no longer reading
  the registry**, which makes it strictly belt-and-braces for this phase. Kept because REG-02 and
  REG-03 mandate it, because Phase 3 puts registry reads back on install-adjacent paths, and
  because it is one line guarded by a permanent assertion (D-03).

- **D-12:** `profiles/default/registry.xml`'s bare `<records interface="…"/>` stays as-is. It is
  the correct idiom for this schema — `TextLine`, `Bool` and `Text` all have `IPersistentField`
  adapters and none is `readonly`, so neither of Pitfall 8's first two holes applies.

- **D-13:** REG-05's double-apply test is a **regression guard, not a live bug fix** — and the plan
  must say so, or someone will go looking for a bug that isn't there. `ska_secret_key` is
  `TextLine(required=False, default=u'')` (`browser/controlpanel.py:28-33`), so an existing
  non-empty unicode revalidates cleanly on re-import and Pitfall 8's hole 3 does not fire today.
  It fires the day someone adds `required=True` or a constraint. The test must set a **known**
  value, re-apply the profile, and assert **equality with that value** — asserting merely
  "non-empty" would pass against a fresh re-mint and prove nothing.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` — constraints (notably the `transaction.abort()` / state-writes rule that
  D-06 reasons against), Key Decisions, Out of Scope
- `.planning/REQUIREMENTS.md` — REG-01…REG-05 and BUG-04 as written, plus the Open Decisions table
  (none of the four land in this phase)
- `.planning/ROADMAP.md` §"Phase 2: Registry Seeding and Import-Step Ordering" — goal, the five
  success criteria, and the phase notes carrying the site-creation-asymmetry MEDIUM
- `.planning/phases/01-rename-and-fail-closed/01-CONTEXT.md` — Phase 1's decisions, in particular
  D-09 (profile version reset to `1000`) and the fail-closed break-glass reasoning

### Research (primary-source, read against the installed eggs)
- `.planning/research/PITFALLS.md` §"Pitfall 6" (lines 278-347) — `getSortedImportSteps()` builds a
  Python 2 `set`; `_computeTopologicalSort` inserts dependency-free steps in string-hash order.
  **The root cause. Read before touching `configure.zcml`.**
- `.planning/research/PITFALLS.md` §"Pitfall 7" (lines 351-439) — the four things
  `runImportStepFromProfile` does that nobody asked for, and the three fix options ranked
- `.planning/research/PITFALLS.md` §"Pitfall 8" (lines 443-504) — the three silent holes in
  `<records interface="…"/>`; hole 3 is what REG-05 guards against
- `.planning/research/SUMMARY.md` lines 48-50, 164, 249 — the reconciled account, including the
  explicit warning that a post-rename disappearance of the error is **not** evidence of a fix
- `.planning/codebase/TESTING.md` — current layer setup and the known isolation problem
- `.planning/codebase/CONVENTIONS.md` — naming, import ordering, logging patterns to preserve

### Source read during this discussion (file:line, verified)
- `src/imio/googleauthenticator/setuphandlers.py:33-44` — `_setup_secret_key`, the 3-line nested
  import plus the seeding that D-04 deletes
- `src/imio/googleauthenticator/configure.zcml:44-49` — the dependency-free `importStep`
  declaration that D-10 amends
- `src/imio/googleauthenticator/profiles/default/metadata.xml` — already declares
  `<dependency>profile-plone.app.registry:default</dependency>`. **This is a *profile* dependency
  and does not order import steps** — do not mistake it for the fix
- `src/imio/googleauthenticator/helpers.py:228-259` — `get_ska_secret_key`, the bare concat
- `src/imio/googleauthenticator/helpers.py:210-224` — `get_browser_hash` and its `None` return
- `src/imio/googleauthenticator/browser/controlpanel.py:24-48` —
  `IGoogleAuthenticatorSettings`; three fields, all persistable, none readonly
- `/srv/cache/eggs/plone.app.registry-1.7.9-py2.7.egg/plone/app/registry/exportimport/configure.zcml:10-18`
  — the step id is `plone.app.registry`, and it declares **three** dependencies:
  `componentregistry`, `toolset`, `typeinfo`. PITFALLS.md line 304 lists only the first two —
  minor correction, relevant if anyone reasons about the sort by hand

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`tests/base.py` + `IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING`** — the existing layer already
  applies the profile (`test_generic.py:_install()`), so both new tests hang off machinery that
  exists. `IntegrationTesting` aborts its transaction per test, so a double-`applyProfile` (D-13)
  does not leak into sibling tests.
- **`test_generic.py:test_product_is_installed`** — the closest analog for the new setup tests:
  same layer, same `qi_tool` fixture, same shape.

### Established Patterns
- `.isort.cfg`: `force_alphabetical_sort`, `force_single_line`, `line_length = 120`. New imports in
  `helpers.py` and the test module follow it; the lint sweep itself is Phase 8.
- Helpers are thin, snake_case, `get_`/`is_`/`validate_`-prefixed, with reStructuredText
  `:param Type name:` docstrings. D-05's mint branch lives inside an existing helper rather than
  introducing a new public function.

### Integration Points
- **`pas_plugin.py:160`** (`sign_user_data`) is the *only* caller on an abort-prone path. The two
  `validate_user_data` callers — `token.py:87` and `reset_bar_code.py:150` — are views, which
  commit. `request_bar_code_reset.py:66` calls `get_ska_secret_key` directly. Four call sites
  total; all four are affected by D-08's derivation change.
- **The marker-file guard** — `setupVarious` returns silently unless
  `context.readDataFile('imio.googleauthenticator.marker.txt')` is non-None. D-04 shrinks the
  function but must not touch this guard.
- **`_dont_swallow_my_exceptions = True`** (Phase 1) is what makes D-07's propagating `KeyError` a
  visible 500 rather than a fallthrough to password-only auth.

</code_context>

<specifics>
## Specific Ideas

- **The assertion is the control, not the rename.** The roadmap says it twice and research says it
  three times: if the `no record` error disappears after Phase 1's rename, that is a changed string
  hash, not a fix. Any plan that treats "we can't reproduce it any more" as evidence is wrong.
- **Settle the carried-forward MEDIUM by observation, not argument.** Which of the four
  `runImportStepFromProfile` mechanisms fires on the site-creation path is unresolved. Research is
  explicit that the recommended fix does not depend on the answer, so it is **not** a blocker for
  this phase — if it is cheap to print `getSortedImportSteps()` while writing D-03's test, record
  what it shows; do not spend a task on it.

</specifics>

<deferred>
## Deferred Ideas

- **Raise the `ska_secret_key` entropy** — `unicode(uuid4())` is ~122 bits for what is a signing
  key. `binascii.hexlify(os.urandom(32))` is a one-line upgrade. Belongs with Phase 3, which
  already touches secret entropy for `SEC-06` (the 160-bit TOTP seed) and can change both under one
  rationale. Not in scope here: no Phase 2 requirement asks about entropy.
- **`ska_secret_key` is rendered into the control-panel HTML** — `browser/controlpanel.py` puts the
  site signing key in a form field, so it is visible to anyone reaching the control panel and lands
  in browser history/caches. Phase 3 is the secret-handling phase and the right place to decide
  whether it becomes write-only or leaves the registry entirely (PROJECT.md's Pitfall 13 line
  already leans that way for secret-adjacent values).
- **A manual site-creation smoke run** — explicitly not done (D-01). If REG-01's backstop truth
  (D-02) reaches verify-phase and someone wants to close it by hand, this is the procedure:
  `bin/instance fg`, create a site with the add-on ticked, then
  `grep -e "no record" -e "Cannot find registry" var/log/instance.log`.

</deferred>

---

*Phase: 2-Registry Seeding and Import-Step Ordering*
*Context gathered: 2026-07-29*
