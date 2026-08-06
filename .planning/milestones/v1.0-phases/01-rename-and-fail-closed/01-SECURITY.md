---
phase: 01
slug: rename-and-fail-closed
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
block_on: high
created: 2026-07-29
---

# Phase 01 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

Register origin: **authored at plan time** — all four of `01-01-PLAN.md` … `01-04-PLAN.md`
carry a `<threat_model>` block. This audit verifies those mitigations exist; it does not
scan for new threats (ASVS L1, grep-depth verification).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| unauthenticated HTTP → `acl_users` PAS chain | Untrusted credentials cross here on every login attempt. Phase 01 changes the plugin's identity, its installation, and what happens when it raises. | Username, password, TOTP token |
| plugin exception → ZPublisher error handling | The escape route opened by `_dont_swallow_my_exceptions`. Everything an operator or attacker sees about a plugin failure crosses here. | Exception type, traceback, error page |
| GenericSetup profile import → ZODB | Install-time writes that decide whether the second factor runs at all. | Plugin registration, `ska_secret_key` |
| filesystem build artefacts → `pkg_resources` / `z3c.autoinclude` | Stale bytecode or a duplicate egg-link decides which code the process actually loads. | Python modules, ZCML |
| filesystem catalogue files → `zope.i18n` domain registry | Read at ZCML load; a filename mismatch or parse error is absorbed with a log line and no error path. | Translated UI strings |
| repository source tree → published sdist | Everything crossing here is distributed to installers; the develop-egg reads the source tree directly and hides mistakes at this boundary. | Package contents |
| Zope product registration → ZMI add list | Where the renamed `meta_type` takes effect; a duplicate refuses startup. | `meta_type` string |
| documentation → operator action | `CHANGES.rst` tells an existing installation its database is discarded, not migrated. | Upgrade instructions |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-1-01 | Spoofing (auth bypass) | `authenticateCredentials` exception swallowed by PAS → fallthrough to password-only auth | critical | mitigate | `_dont_swallow_my_exceptions = True` at `pas_plugin.py:71`; `test_plugin_exception_is_not_swallowed` injects through a real collaborator, plus a counterfactual test | closed |
| T-1-02 | Spoofing (auth bypass) | Renamed modules unpickle as `OFS.Uninstalled.Broken`; `listPlugins` then skips the plugin | critical | mitigate | Databases discarded not migrated (DOC-04 notice + `make purge`); `test_plugin_is_registered_for_authentication` is the standing guard | closed |
| T-1-03 | Spoofing (auth bypass) | `setuphandlers.setupVarious` marker-file guard | critical | mitigate | Marker file and the compared string renamed together — `profiles/default/imio.googleauthenticator.marker.txt` matches `setuphandlers.py:53`; registration test is the acceptance check | closed |
| T-1-04 | Tampering | Orphan `.pyc` / stale egg-link under the old namespace → both namespaces load, ambiguous plugin registration | high | mitigate | Verified: 0 old-namespace `.pyc`, 0 old-namespace dirs, exactly 1 egg-link (`imio.googleauthenticator.egg-link`), 1 egg-info. `meta_type` shipped in an isolated commit so a duplicate-registration error stays readable | closed |
| T-1-05 | Denial of Service | Every in-site user, once a plugin bug is a hard failure rather than a degradation to password-only | medium | accept | Locked trade in CONTEXT.md — for an MFA package a loud outage beats a silent bypass. Break-glass is the Zope root admin, which no in-site PAS plugin runs for. **Materially reduced during this audit cycle**: the three crash paths that made this concrete (CR-01/02/03) were fixed in `0018bca`, `e6d9e57`, `316d636` | closed |
| T-1-06 | Information Disclosure | `portal_registry` keys orphaned under the old interface prefix, retained in `portal_setup` snapshots | low | accept | No `Data.fs` in this checkout; any other checkout discards its database | closed |
| T-1-07 | Denial of Service (translation layer) | `compile_mo_file` returns silently on IO/PO syntax error — a malformed catalogue registers zero messages | low | mitigate | All three catalogues compile via `pythongettext.Msgfmt` (re-verified at UAT after the French terminology edit, incl. 0 placeholder mismatches across 60 entries); `test_control_panel_is_translated_nl` is the standing assertion | closed |
| T-1-08 | Information Disclosure | Compiled catalogue / bytecode / build dir shipped in the sdist | low | mitigate | `MANIFEST.in` carries `global-exclude *.pyc` and `*.mo`; sdist rebuilt at UAT — archive contains the pot, three `.po`, marker, registries, `.zpt`, `main.css` and no `.pyc`/`.mo` | closed |
| T-1-09 | Information Disclosure | Translated strings on the token and enrollment forms | low | accept | The msgid corrections change wording only; none adds account-specific information | closed |
| T-1-10 | Spoofing (auth bypass, downstream) | Operator upgrades an existing upstream install in place on a broken-unpickle database — second factor silently stops running | high | mitigate | `CHANGES.rst:9-12` carries the explicit non-migration notice ("Existing databases are discarded, not migrated … Recreate the Plone site and re-enrol users"); `make purge` removes the local database so no one half-migrates by accident | closed |
| T-1-11 | Information Disclosure | Failure presentation on the fail-closed path; raw exception text echoed into status messages | medium | mitigate | Presentation kept a plain uniform server error. `_(str(e))` echoes removed from all three form sites — `reset_bar_code.py` and `user_setup.py` in `719884e`, and **`request_bar_code_reset.py` in `08687ac`, found open during this audit** (the code review had named only the first two). `grep -rn "_(str(e))" src/` now returns nothing. The two pre-existing username-carrying debug lines in `pas_plugin.py` were not widened by this phase and remain Phase 4 work | closed |
| T-1-12 | Tampering | Supply chain — package-manager installs | high | mitigate | Phase installs no package: `git diff <phase-base>..HEAD -- setup.py` shows no `install_requires` or dependency-line change. RESEARCH "Package Legitimacy Audit" records zero additions | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `workflow.security_block_on` (high) count toward `threats_open`*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-01 | T-1-05 | For an MFA package a loud outage beats a silent bypass. Break-glass path is the Zope root administrator, which an in-site PAS plugin never runs for by construction. Locked trade recorded in `01-CONTEXT.md`; Phase 4 DOC-01 documents the exclusion | Locked in CONTEXT.md | 2026-07-29 |
| R-02 | T-1-06 | No `Data.fs` exists in this checkout; any other checkout discards its database rather than migrating. If a carried-forward database is ever in play, assert no registry record key retains the old prefix | Plan 01-01 threat model | 2026-07-29 |
| R-03 | T-1-09 | The three msgid corrections change wording only; none adds account-specific information to a message. The stronger constraint (a refusal must not reveal enrollment state) is registered as a prohibition in plan 01-04 | Plan 01-02 threat model | 2026-07-29 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-29 | 12 | 12 | 0 | `/gsd-secure-phase 01` (orchestrator, ASVS L1 grep-depth) |

### 2026-07-29 — findings from this audit

One mitigation was **not** in place when the audit started:

- **T-1-11** — `request_bar_code_reset.py:113` still echoed `_(str(e))` to end users on a
  form reachable by unauthenticated users. The code review's WR-04 named only
  `reset_bar_code.py` and `user_setup.py`, so the fixer patched two of three sites. Closed
  by `08687ac`, matching the pattern already applied at the other two: log server-side with
  `logger.exception`, show a generic message. Suite re-verified green (21 tests, 0 failures,
  0 errors) after the change.

Context carried in from the code-review cycle that ran immediately before this audit: the
three crash paths recorded as a gap in `01-VERIFICATION.md` (CR-01/02/03) were fixed in
`0018bca`, `e6d9e57`, `316d636`, with regression tests. That materially reduces the concrete
surface behind accepted risk R-01 (T-1-05), though the acceptance itself stands.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-29
