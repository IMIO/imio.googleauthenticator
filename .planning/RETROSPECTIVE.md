# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Hardened MFA

**Shipped:** 2026-08-06
**Phases:** 8 | **Plans:** 30 | **Quick tasks:** 3

### What Was Built

- Renamed `collective.googleauthenticator` to `imio.googleauthenticator` across the on-disk
  layout, egg name, i18n domain and catalogue filenames, GenericSetup profile and marker file,
  registry interface path, PAS plugin title and `meta_type`, and `++resource++` prefixes. Set
  `_dont_swallow_my_exceptions = True`, so a plugin crash is a 500 rather than a silent
  password-only login.
- Fernet-encrypted TOTP seeds under an environment-supplied key, fail-closed on every path
  (enrollment, login, bulk enable, user creation), plus in-process QR rendering so the seed no
  longer travels to `chart.googleapis.com`.
- Moved the two-factor redirect out of `authenticateCredentials` into an `IPubBeforeCommit`
  subscriber and an `IChallengePlugin`, with a per-extractor veto assertion.
- Lockout counter, replay rejection and clock-drift tolerance, all stored in declared memberdata
  properties and written only from a committing view.
- Ten PBKDF2-hashed recovery codes per user, shown once, consumed on use, sharing the lockout
  counter.
- Deleted 507 lines of vendored JavaScript and skin templates plus the whole `portal_skins`
  layer, ending the resource collision with `imio.dms.mail`.
- Repaired the coverage instrument, moved the test suite off a leaking layer, raised branch
  coverage from 84% to 90%, and made CI enforce it.

### What Worked

- **Mutation checks as the standard for "this test is load-bearing".** Deleting the guard,
  watching the specific test go red, then restoring byte-identically was applied throughout, and
  it repeatedly earned its cost. In Phase 2 it caught a *tautological* ordering test: the test
  stayed green with `<depends name="plone.app.registry"/>` deleted, passing only by a CPython 2.7
  string-hash coincidence. Without the mutation check that test would have shipped as a security
  control that controlled nothing.
- **Fixing the instrument before trusting the measurement.** Phase 8 repaired `.coveragerc` scope
  and added `set -e` in its own commit, *before* writing a single new test, and proved the build
  could go red by mutating a test rather than by reading the config. The coverage drop that
  followed was the truth rather than a regression.
- **Ordering phases by what a mistake would look like.** The rename went first specifically to
  carry `_dont_swallow_my_exceptions` forward, which converted every later phase's mistakes from
  silent 2FA bypasses into visible 500s. That flag paid for itself immediately, surfacing two
  pre-existing bugs that had been disabling the entire gate with no error and no log line.
- **Real-deployment testing on a two-egg environment.** It found three defects that no in-process
  test found or could have found: the counters crashing `@@user-information` as schema fields,
  the unpositioned `jsregistry.xml` entries that put this package's scripts above jQuery on a
  fresh site, and MFA-14 itself.
- **Operator decisions recorded at the checkpoint, with the rejected alternatives.** Several
  entries in PROJECT.md's Key Decisions table record not just what was chosen but what the
  alternative would have cost — for example keeping `credentials_basic_auth` active. Those rows
  were reusable later instead of being re-litigated.

### What Was Inefficient

- **PROJECT.md evolution lagged behind reality, twice.** Phase 3's requirements were still sitting
  in Active when Phase 4 closed, and Phase 7's four delivered items were still in Active when
  Phase 8 closed. Both were caught and corrected at the following phase transition, but in the
  interval the document was misleading about what remained to do.
- **Lint debt deferred to the last phase grew while it waited.** The `bin/code-analysis` baseline
  went from an estimated ~40, to 318 measured in Phase 1, to 500 by Phase 8 — the growth was
  phases 2 through 7 adding test code with the gate switched off. Clearing 500 findings in one
  phase cost a 41-file commit. Clearing them as they appeared would have cost nothing extra.
- **A requirement that named a behaviour but no call sites got two of three endpoints.** MFA-08
  said "the lock is checked before the token is evaluated" without enumerating where. Three files
  call `validate_token`; Phases 5 and 6 wired two of them. The third was caught by the milestone
  audit, not by the phase, and had to be closed by a quick task afterwards.
- **A known gap found mid-milestone never got a phase.** MFA-14 was found on 2026-08-05 during
  Phase 7 verification and was still unassigned at the close. It was recorded honestly at every
  step, but recording is not scheduling — it shipped as the milestone's one unsatisfied
  requirement.
- **Two of the audit's findings had to be closed by quick tasks after the audit ran.** Both were
  real and both were fixed the same day, but a gap that only the milestone audit finds is a gap
  the phase's own verification was not shaped to find.

### Patterns Established

- **Every guard gets a mutation check.** A green suite proves nothing about whether a specific
  assertion is doing work. Break it, confirm red, restore byte-identically, record it.
- **State that must survive goes in a declared memberdata property, and is written only from a
  view.** `MutablePropertySheet.setProperties` silently pops undeclared properties, and any
  request ending in an exception discards its writes through `transaction.abort()`. Both failure
  modes are invisible. A source-grep regression test enforces the second one.
- **Derive composite keys with a length-prefixed join, never bare concatenation.** Bare
  concatenation of `(user_secret, browser_hash, ska_secret_key)` is collidable at the component
  boundaries. The fix is asserted against a fixture that provably collides under the old scheme,
  so it cannot decay into a cosmetic reformat.
- **Assert the declaration, not only the resulting behaviour.** Testing sorted order proved
  nothing; testing the pre-sort `dependencies` metadata proved the dependency was declared.
- **Prove a gate can fail before trusting it to pass.** Applied to the coverage script and to the
  lint hook.

### Key Lessons

1. **A requirement phrased as a behaviour must enumerate its call sites, or the plan will cover
   only the ones it happened to name.** MFA-08 is the worked example: correct wording, two of
   three endpoints wired, gap found only at the milestone audit.
2. **Silent failure modes need tests written as security controls, and those tests need
   counterfactuals.** In this package the dominant risks — a swallowed exception, an aborted
   transaction, a popped property, an orphan `.pyc`, a coverage gate measuring nothing — all
   produce no error page and no log line. A test is the only observer, and an unverified test is
   not an observer.
3. **Quality gates that are switched off accumulate debt at the rate the project produces code.**
   Turn the gate on early and cheaply, or budget for the cleanup to grow.
4. **An honestly-recorded open item is not a scheduled one.** MFA-14 was written down accurately
   in five places and still shipped unfixed, because nothing turned the record into a phase.
5. **Some defects are only reachable from a real deployment.** Three of this milestone's
   corrections came from a two-egg environment and none of them could have come from `bin/test`.
   Budget for that testing rather than treating it as optional confirmation.

### Cost Observations

- Recorded plan execution: roughly 17 hours across 29 of the 30 plans (Phase 7 plan 04 has no
  recorded duration). Per-plan figures are in `STATE.md` under Performance Metrics.
- Longest single plan: Phase 8 plan 04, about 2 hours, closing the branch-coverage gap from 87%
  to 90%.
- Heaviest phase by recorded time: Phase 4, the PAS boundary, at about 3¾ hours across 4 plans.
  That is consistent with it being the phase that had to establish which code paths commit,
  which everything after it depended on.
- Widest single commit: Phase 8 plan 05, 41 files, clearing the accumulated lint debt.
- **Model mix is not recorded.** No per-session model or token accounting exists in this
  repository, so no figure is given here rather than an estimated one.

---

## Cross-Milestone Trends

*One milestone so far. These tables are seeded, not yet trends.*

### Process Evolution

| Milestone | Phases | Plans | Quick tasks | Key Change |
|-----------|--------|-------|-------------|------------|
| v1.0 | 8 | 30 | 3 | First milestone. Established mutation checks on every guard, and the rule that second-factor state is written only from a committing view. |

### Cumulative Quality

| Milestone | Tests | Coverage | Lint findings | Requirements satisfied |
|-----------|-------|----------|---------------|------------------------|
| v1.0 | 135 | 90% (CI-gated) | 0 (`bin/code-analysis` exits 0) | 72 of 73 |

### Top Lessons (Verified Across Milestones)

*Nothing here yet — a lesson is promoted to this table only after a second milestone confirms it.
The v1.0 candidates most likely to hold are "enumerate call sites in behavioural requirements"
and "prove a gate can fail before trusting it to pass".*
