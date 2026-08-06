# Phase 2: Registry Seeding and Import-Step Ordering - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-29
**Phase:** 2-registry-seeding-and-import-step-ordering
**Areas discussed:** REG-01 verification strategy

---

## Area selection

Four gray areas were offered; one was selected.

| Area | Description | Selected |
|------|-------------|----------|
| Lazy mint mechanics | REG-04 turns a read path into a write path — which request commits it, PAS-plugin abort risk, ZEO concurrency | |
| ska key separation (BUG-04) | Delimiter vs length-prefix vs HMAC; the `get_browser_hash` `None` path | |
| Import-step guard scope | Keep `<depends>` once the handler stops reading the registry, or use `post_handler` | |
| REG-01 verification strategy | How to prove a symptom that isn't unit-reproducible | ✓ |

**Notes:** The three unselected areas were resolved under Claude's Discretion (D-04…D-13 in
CONTEXT.md) rather than left open.

---

## REG-01 verification strategy

### Q1 — How do we prove REG-01?

| Option | Description | Selected |
|--------|-------------|----------|
| Manual run + ordering assertion | One recorded `bin/instance fg` site creation, grep `var/log/instance.log` for `no record` and `Cannot find registry`, paste the empty output into the phase SUMMARY; ordering assertion as the permanent control | |
| Add an automated site-creation test | `addPloneSite(app, 'reg01', extension_ids=('imio.googleauthenticator:default',))` in a fresh site, asserting no exception plus records present. Proves the literal REG-01 sentence forever, at ~30–60s of suite time | |
| Ordering assertion only | Treat REG-01 as satisfied by construction once the nested import is gone and the dependency is declared | ✓ |

**User's choice:** Ordering assertion only.
**Notes:** Claude flagged before the question that the lazy accessor (REG-04) makes the original
`KeyError` unreachable on the install path regardless of step order, so the ordering assertion is
really guarding Phase 3+ rather than REG-01 itself. Consequence of this choice — that success
criterion 1 ends up with no evidence attached — was raised immediately as Q2 rather than left
implicit.

### Q2 — How does the plan carry ROADMAP success criterion 1?

| Option | Description | Selected |
|--------|-------------|----------|
| Backstop truth | `{ statement, verification: backstop }` in `must_haves`; the verifier abstains to `human_needed` rather than silently passing | ✓ |
| Narrow the criterion to what's asserted | Rewrite ROADMAP criterion 1 to claim only what the phase proves; nothing left unevidenced, but the roadmap stops claiming the user-visible symptom is verified | |
| Leave it and accept the flag | Write it as a plain truth and deal with the verifier's complaint in verify-phase | |

**User's choice:** Backstop truth.
**Notes:** Recorded as D-02. This is the only must_have in the phase that is not machine-checkable;
CONTEXT.md says so explicitly so the planner does not try to invent a check for it.

### Q3 — What does the mechanised control assert?

| Option | Description | Selected |
|--------|-------------|----------|
| Both ordering and outcome | `steps.index(...)` comparison **and** post-`applyProfile` records-exist / `get_app_settings()` doesn't raise | ✓ |
| Ordering index only | Exactly REG-03 as worded; minimal and directly traceable, but tied to the `<depends>` mechanism | |
| Outcome only | Tests the property that matters and survives refactoring, but doesn't satisfy REG-03, which names `getSortedImportSteps()` explicitly | |

**User's choice:** Both ordering and outcome.
**Notes:** Recorded as D-03. Before this question Claude verified against the installed egg that
the step id is `plone.app.registry` and that it declares three dependencies
(`componentregistry`, `toolset`, `typeinfo`) — PITFALLS.md line 304 lists only two. The correction
is carried into CONTEXT.md's canonical refs.

### Q4 — Continue or write context?

| Option | Description | Selected |
|--------|-------------|----------|
| I'm ready for context | Write CONTEXT.md; unpicked areas get Claude's decisions with rationale | ✓ |
| Explore more gray areas | Surface further areas — e.g. how the ska-collision test picks colliding component tuples, whether the REG-05 double-apply test pollutes the shared layer | |

**User's choice:** I'm ready for context.

---

## Claude's Discretion

Three areas the user chose not to discuss, resolved with rationale in CONTEXT.md:

- **Lazy mint mechanics (D-04…D-07)** — `_setup_secret_key` deleted outright with no install-time
  fallback; the mint is one unconditional branch inside `get_ska_secret_key()`; three consequences
  (PAS-plugin abort, unauthenticated trigger, ZEO concurrency) accepted with reasons; a missing
  record propagates its `KeyError` rather than being papered over with `forInterface(check=False)`.
- **ska key separation (D-08, D-09)** — length-prefixed netstring join, chosen over a `|` delimiter
  because Phase 3 turns `user_secret` into `v1$<fernet token>` and the "this character can't
  appear" argument expires; `get_browser_hash`'s `None` return fixed to `''` in the same change,
  because length-prefixing turns that latent wrong-key bug into a `TypeError` on a login path.
- **Import-step guard scope (D-10…D-13)** — `<depends>` on the custom step, `post_handler`
  rejected for its `runImportStepFromProfile`/upgrade-step caveat; the `<depends>` kept even though
  D-04 makes it belt-and-braces; `<records interface="…"/>` left as-is; REG-05 documented as a
  regression guard, with the test required to assert equality against a known value rather than
  mere non-emptiness.

## Deferred Ideas

- Raise the `ska_secret_key` entropy from `uuid4()` (~122 bits) — Phase 3, alongside SEC-06.
- `ska_secret_key` is rendered into the control-panel HTML form — Phase 3 decides whether it
  becomes write-only or leaves the registry.
- The manual site-creation smoke run, explicitly not done here — procedure recorded in CONTEXT.md
  in case someone closes D-02's backstop by hand at verify time.
