---
phase: 03-encrypted-seeds-and-local-qr
plan: 02
subsystem: auth
tags: [zope-processlifetime, boot-logging, buildout, documentation]

requires:
  - phase: 03-encrypted-seeds-and-local-qr
    plan: 01
    provides: "helpers.get_encryption_key/ENV_VAR_NAME (IMIO_GOOGLEAUTHENTICATOR_SEED_KEY), base.cfg [testenv]'s throwaway Fernet key"
provides:
  - "IProcessStarting subscriber logging CRITICAL once when the seed key is absent/empty, never raising (SEC-08)"
  - "SEC-07 four-places accounting settled: this repo owns [testenv] only; CI inheritance proven by a test that reads (never sets) os.environ; [instance] and the Puppet fragment documented as the deployment's"
  - "README.rst 'Seed encryption key (required)' section (DOC-03)"
affects: [03-03]

tech-stack:
  added: []
  patterns:
    - "zope.processlifetime.IProcessStarting subscriber, no new install_requires (already transitively available via ZServer)"
    - "test that asserts on os.environ rather than setting it, to prove inheritance rather than assume it"

key-files:
  created:
    - src/imio/googleauthenticator/subscribers.py
    - src/imio/googleauthenticator/tests/test_subscribers.py
  modified:
    - src/imio/googleauthenticator/configure.zcml
    - README.rst

key-decisions:
  - "base.cfg [instance] deliberately carries no IMIO_GOOGLEAUTHENTICATOR_SEED_KEY entry -- restated below in full, since it reads as an omission if undocumented."
  - "No docs/ cross-reference added: docs/index.rst is a stale pre-rename duplicate of an old README (still says 'Plone 4', 'GoogleAuthenticator', 'White-listed IP addresses' singular-per-line -- it was never kept in sync with README.rst through Phases 1-3) and the plan's own flagged assumption prefers README.rst as the deployer-facing shipped artifact over docs/'s user-facing usage content. Recorded as an explicit choice, not an oversight."

patterns-established: []

requirements-completed: [SEC-07, SEC-08, DOC-03]

coverage:
  - id: D1
    description: "IProcessStarting subscriber logs CRITICAL exactly once naming IMIO_GOOGLEAUTHENTICATOR_SEED_KEY when the key is absent or an empty string, zero times when present, and never raises in any case; the handler never inspects its event argument"
    requirement: "SEC-08"
    verification:
      - kind: unit
        ref: "tests/test_subscribers.py#TestOnProcessStarting.test_on_process_starting"
        status: pass
      - kind: manual
        ref: "env -u IMIO_GOOGLEAUTHENTICATOR_SEED_KEY bin/instance start / bin/instance stop, var/log/instance.log"
        status: pass
    human_judgment: false
  - id: D2
    description: "The IProcessStarting registration exists in configure.zcml and the file still parses as well-formed XML"
    requirement: "SEC-08"
    verification:
      - kind: unit
        ref: "tests/test_subscribers.py#TestOnProcessStarting.test_on_process_starting (minidom parse + attribute match)"
        status: pass
    human_judgment: false
  - id: D3
    description: "base.cfg [testenv]'s declared value is a genuinely usable Fernet key (non-empty, Fernet(...) does not raise), which is also the mechanised proof that CI (bin/buildout then bin/test) inherits a working key"
    requirement: "SEC-07"
    verification:
      - kind: unit
        ref: "tests/test_subscribers.py#TestOnProcessStarting.test_seed_key_is_present_in_the_test_environment"
        status: pass
    human_judgment: false
  - id: D4
    description: "A ciphertext produced under a different, freshly generated key raises ValueError under decrypt_seed with the [testenv] key in place -- the SEC-07 adjacency assertion and the mechanised form of the ZEO-client-skew failure mode"
    requirement: "SEC-07"
    verification:
      - kind: unit
        ref: "tests/test_subscribers.py#TestOnProcessStarting.test_seed_key_is_present_in_the_test_environment"
        status: pass
    human_judgment: false
  - id: D5
    description: "README.rst documents the key, its generation, all three consequences of its absence, per-ZEO-client scope, the InvalidToken-with-no-ZODB-evidence failure mode, who supplies [instance]'s copy, how a local dev supplies their own, and the industrialisation concat::fragment as an open dependency"
    requirement: "DOC-03"
    verification:
      - kind: manual
        ref: "grep checks against README.rst (see Verification Detail) + docutils publish_doctree with no SEVERE/ERROR"
        status: pass
    human_judgment: false

duration: ~20min
completed: 2026-07-30
status: complete
---

# Phase 3 Plan 2: Encrypted Seeds and Local QR (Boot-Time CRITICAL Log + Documentation) Summary

**A `zope.processlifetime.IProcessStarting` subscriber turns a missing seed key into one CRITICAL log line at boot instead of a silent time-bomb, and `README.rst` writes down the one failure mode that leaves no evidence in the ZODB.**

## Performance

- **Duration:** ~20 min of agent-active work, no checkpoints (plan is `autonomous: true`)
- **Tasks:** 2 (both `type="auto"`)
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `subscribers.on_process_starting(event)` logs one CRITICAL line naming `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` when `helpers.get_encryption_key()` is falsy (absent or empty string) and logs nothing when it is set; the handler contains no `raise`, `try`, or `except` (asserted by an AST walk, not a grep, per the plan's own reasoning about a docstring that says "does not raise")
- Registered for `zope.processlifetime.IProcessStarting` in `configure.zcml`; the ZCML file still parses as well-formed XML
- **End-to-end proof, not just unit test:** `env -u IMIO_GOOGLEAUTHENTICATOR_SEED_KEY bin/instance start` writes the CRITICAL line and Zope still reaches "Ready to handle requests" — see exact log lines below
- SEC-07's four-places accounting settled in code and prose: this repository owns exactly one declaration site (`base.cfg` `[testenv]`, landed in plan 03-01); a new test reads (never sets) `os.environ` to prove that value is both present and a genuinely usable Fernet key, which is the same evidence that CI's `bin/buildout` + `bin/test` inherits a working key; `[instance]` and the Puppet fragment are documented, not declared, in this repository
- `README.rst` gained a "Seed encryption key (required)" subsection between `Buildout` and `ZMI`, covering generation, all three failure consequences (enrollment, login, and — the one an operator is least likely to connect — new account creation), per-ZEO-client scope, the `InvalidToken`-with-no-ZODB-evidence failure mode, who supplies `[instance]`'s copy and how a local developer supplies their own, and the `industrialisation` `concat::fragment` as an explicitly open, out-of-repo dependency

## Task Commits

1. **Task 1: The missing key is loud at boot — IProcessStarting CRITICAL, never a raise** — `754609f` (feat)
2. **Task 2: Settle the four-places accounting, and write the ZEO-skew failure mode down** — `6038396` (docs)

**Plan metadata:** *(this commit)*

## Files Created/Modified

- `src/imio/googleauthenticator/subscribers.py` (new, 30 lines) — `on_process_starting(event)`, module-level `logger`
- `src/imio/googleauthenticator/configure.zcml` — one new `<subscriber for="zope.processlifetime.IProcessStarting" handler=".subscribers.on_process_starting"/>` element, added after the existing user-creation subscriber; `<genericsetup:importStep>` and everything else untouched
- `src/imio/googleauthenticator/tests/test_subscribers.py` (new, 108 lines) — `TestOnProcessStarting` with two methods: `test_on_process_starting` (absent/present/empty key, never-raises, ZCML wiring parse) and `test_seed_key_is_present_in_the_test_environment` (reads `os.environ`, asserts a usable Fernet key, asserts foreign-key non-interop)
- `README.rst` — new `----`-level "Seed encryption key (required)" subsection (48-character underline, matching its `Buildout`/`ZMI` siblings)

## Decisions Made

- **`base.cfg` `[instance]` deliberately carries no `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` entry.** Two reasons, both stated in `README.rst` and restated here because the absence reads as an omission otherwise: (1) `environment-vars` is whitespace-separated `NAME value`; an option reference defaulting to empty would emit a bare token that `plone.recipe.zope2instance` cannot split — a buildout failure, not a graceful absence. (2) The only form that *does* parse is a literal placeholder value, which is strictly worse than absence: production would then encrypt every seed under a key any repository reader can see, and Task 1's CRITICAL log would never fire because the key would no longer be falsy. `grep -c "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" base.cfg` returns exactly `1` (the `[testenv]` line from plan 03-01) — confirmed after this plan's commits, `base.cfg` unchanged. `README.rst` states that the deployment buildout supplies `[instance]`'s copy, the same path `SSO_APPS_CLIENT_SECRET` already takes (`server.dmsmail/base.cfg` → `os.getenv()`).
- **No `docs/` cross-reference added.** `docs/index.rst` is a stale, pre-rename duplicate of an old `README.rst` (still reads "Plone 4", singular "White-listed IP addresses" heading that `README.rst` long ago pluralized to "or IP ranges") — it has evidently not been kept in sync through Phases 1-3, and the plan's own flagged assumption treats `docs/` as user-facing usage documentation rather than deployment documentation. `README.rst` is the shipped artifact a deployer actually reads; adding a stale cross-reference into an already-stale file would not have improved anything.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] README.rst's "export ``VAR=...``" phrasing broke its own acceptance-criteria grep**
- **Found during:** Task 2, verifying acceptance criteria after the first README draft
- **Issue:** `grep -ci "export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" README.rst` returned `0`. The draft wrote `export ``IMIO_GOOGLEAUTHENTICATOR_SEED_KEY=<generated`` (double backticks interrupt the literal space-separated phrase the grep is looking for), and the value itself wrapped onto the next source line.
- **Fix:** Reworded to `run ``export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY=<generated value>``` on a single unbroken clause so the literal phrase `export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` appears intact on one line.
- **Files modified:** `README.rst`
- **Verification:** re-ran the grep, returned `1`
- **Committed in:** `6038396` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (a documentation-vs-acceptance-criteria literal collision, the same class plan 03-01 hit three times). No scope creep, no production code touched by this plan (README.rst and one test file only, plus Task 1's new module/ZCML edit).

## Verification Detail (per plan's `<output>` spec)

### SEC-08 evidence: `env -u IMIO_GOOGLEAUTHENTICATOR_SEED_KEY bin/instance start` / `bin/instance stop`

Entry point used: **ZServer**, `bin/instance start` (the plan's explicitly authorized alternative to `fg`, since `fg` blocks in the foreground and this session drives commands sequentially). `var/log/instance.log`, new lines from this run:

```
2026-07-30T11:50:08 INFO ZServer HTTP server started at Thu Jul 30 11:50:08 2026
	Hostname: 0.0.0.0
	Port: 8080
------
2026-07-30T11:50:09 INFO DocFinderTab Applied patch version 1.0.5.
------
2026-07-30T11:50:10 INFO Plone OpenID system packages not installed, OpenID support not available
------
2026-07-30T11:50:11 INFO Zope Ready to handle requests
------
2026-07-30T11:50:11 CRITICAL imio.googleauthenticator IMIO_GOOGLEAUTHENTICATOR_SEED_KEY is not set; seed encryption and decryption will fail closed on every enrollment and login attempt until it is set.
```

Zope reached "Ready to handle requests" and the CRITICAL line fired one line later (log ordering, not causal — the subscriber runs during process startup, before the socket is fully up in wall-clock terms but the two lines are adjacent in the log). `bin/instance stop` afterward reported a clean `daemon process stopped`, confirmed by `bin/instance status` returning `daemon manager not running` — not a crash.

### `[instance]` restatement

`grep -c "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" base.cfg` → `1` (the `[testenv]` line only, from plan 03-01). `git diff --name-only` for this plan's two commits does not list `base.cfg`. `README.rst` states the deployment buildout supplies `[instance]`'s copy via the `SSO_APPS_CLIENT_SECRET` precedent (`server.dmsmail/base.cfg` → `os.getenv()`).

### `docs/` cross-reference

Not added — see Decisions Made above.

### Open dependency, restated at the end of this plan

The production Fernet key still has to ship as a `concat::fragment` in the separate `industrialisation` repository (`modules/plone/manifests/buildout.pp`). That commit is outside this roadmap and is not filed by this plan. The code in this repository is complete and fully tested without it; the feature remains **not deployable** until that Puppet change lands.

### Other acceptance criteria, run and confirmed

- `bin/test -t test_on_process_starting` → 1 test, 0 failures.
- `bin/test -t test_seed_key_is_present_in_the_test_environment` → 1 test, 0 failures.
- `bin/test -t '!robot'` → **39 tests, 0 failures, 0 errors** (37 from plan 03-01 + 2 new methods in this plan).
- `parts/instance/bin/interpreter -c "import xml.dom.minidom; xml.dom.minidom.parse(...)"` → exits 0 (used `parts/instance/bin/interpreter`, not bare `bin/python`, for the same reason plan 03-01 recorded: `bin/python` is the raw pyenv interpreter with no buildout eggs on `sys.path`).
- `bin/python -c "import ast; ..."` AST walk over `subscribers.py` → `0` `Raise`/`TryExcept`/`TryFinally` nodes.
- `grep -c "zope.processlifetime.IProcessStarting" configure.zcml` → `1`; `grep -c 'handler=".subscribers.on_process_starting"' configure.zcml` → `1`.
- `grep -c 'logging.getLogger("imio.googleauthenticator")' subscribers.py` → `1`; `grep -c "logger.critical" subscribers.py` → `1`.
- `grep -c "assertLogs" test_subscribers.py` → `0`.
- `grep -c "install_requires" setup.py` unchanged from `HEAD~1`; `grep -c "zope.processlifetime" setup.py` → `0` — no new dependency added, `zope.processlifetime` stays transitively available via `ZServer`.
- `wc -l subscribers.py` → `30` (≤ 40 required).
- Zero `import`/`from` statements inside any method body in `test_subscribers.py` (skill R6) — confirmed by grep for indented `import`/`from`.
- `git diff --name-only` for Task 2's commit lists exactly `README.rst` and `src/imio/googleauthenticator/tests/test_subscribers.py` — `base.cfg` absent, `.github/workflows/package-test.yml` absent.
- `grep -c "IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" README.rst` → `2`; `grep -ci "api.user.create\|account creation\|registration" README.rst` → `2`; `grep -c "server.dmsmail" README.rst` → `1`; `grep -ci "export IMIO_GOOGLEAUTHENTICATOR_SEED_KEY" README.rst` → `1`; `grep -c "concat::fragment" README.rst` → `1`; `grep -c "industrialisation" README.rst` → `1`; `grep -c "InvalidToken" README.rst` → `1`; `grep -ci "not deployable" README.rst` → `1`.
- `parts/instance/bin/interpreter -c "import docutils.core, io; docutils.core.publish_doctree(...)"` produced no `SEVERE`/`ERROR` output (checked by grepping stderr for `severe`/`error`, case-insensitive; none found). `bin/python` itself cannot import `docutils` (same egg-path fact as above), so `parts/instance/bin/interpreter` was used instead.
- `git grep -n IMIO_GA_SEED_KEY -- src base.cfg README.rst CHANGES.rst setup.py test-4.3.cfg` → no matches, confirmed after every commit in this plan. The locked variable name `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` (from plan 03-01's Task 1 checkpoint decision) is used everywhere this plan's stale text said `IMIO_GA_SEED_KEY`.
- `bin/code-analysis` exits `1` on 318+ pre-existing findings (unrelated to this plan's changes, though the two new files add a handful of their own `isort` findings in the same accepted category — `I001`/`I003`/`I004`, cosmetic import-ordering only). Both commits used `git commit --no-verify`, as `CLAUDE.md` explicitly authorizes until Phase 8 / QUAL-06.

## User Setup Required

None for this plan's own commits. The real deployment blocker remains the `industrialisation` repo's Puppet `concat::fragment`, tracked as an external dependency (not one of this roadmap's commits) since plan 03-01.

## Next Phase Readiness

- Ready for plan 03-03 (further hardening / real-authenticator confirmation). No blockers introduced by this plan.
- `helpers.ENV_VAR_NAME == 'IMIO_GOOGLEAUTHENTICATOR_SEED_KEY'` remains the locked literal; this plan added no second name anywhere.
- The `ska_secret_key` control-panel field hardening (deferred in plan 03-01) remains explicitly parked, unaffected by this plan.

---
*Phase: 03-encrypted-seeds-and-local-qr*
*Completed: 2026-07-30*

## Self-Check: PASSED
