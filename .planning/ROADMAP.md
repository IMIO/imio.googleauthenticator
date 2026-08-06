# Roadmap: imio.googleauthenticator

## Milestones

- ✅ **v1.0 Hardened MFA** — Phases 1-8 (shipped 2026-08-06) — [full roadmap](milestones/v1.0-ROADMAP.md) · [requirements](milestones/v1.0-REQUIREMENTS.md) · [audit](milestones/v1.0-MILESTONE-AUDIT.md) · [summary](MILESTONES.md)

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order. Numbering continues
across milestones — the next milestone starts at Phase 9, never back at 1.

<details>
<summary>✅ v1.0 Hardened MFA (Phases 1-8) — SHIPPED 2026-08-06</summary>

- [x] **Phase 1: Rename and Fail-Closed** (4/4 plans) — completed 2026-07-29 — `imio.googleauthenticator` everywhere, and a plugin exception becomes a 500 instead of a password-only login
- [x] **Phase 2: Registry Seeding and Import-Step Ordering** (2/2 plans) — completed 2026-07-29 — new Plone sites install cleanly, and the ordering that makes them clean is asserted rather than accidental
- [x] **Phase 3: Encrypted Seeds and Local QR** (3/3 plans) — completed 2026-07-30 — seeds are Fernet-encrypted at rest, never sent to Google, and never fall back to plaintext
- [x] **Phase 4: PAS Boundary** (4/4 plans) — completed 2026-07-31 — the second factor cannot be bypassed by any credentials extractor, and the refusal leaks nothing
- [x] **Phase 5: Drift, Replay and Lockout** (5/5 plans) — completed 2026-08-03 — a replayed code fails, brute force stops at N attempts, and the counters actually persist
- [x] **Phase 6: Recovery Codes** (3/3 plans) — completed 2026-08-04 — a user who loses their phone gets back in without an admin, on a throttled path
- [x] **Phase 7: Coexistence with imio.dms.mail** (4/4 plans) — completed 2026-08-05 — both packages install in either order with no vendored JavaScript, no skin layer, and no open redirect
- [x] **Phase 8: Coverage Instrument and Test Layers** (5/5 plans) — completed 2026-08-06 — the build fails when tests fail, the coverage number means something, and `bin/code-analysis` exits 0

Full phase detail, success criteria, build-order rationale, same-commit requirement groups and
open decisions are preserved in [`milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md).
Phase working directories are archived under `milestones/v1.0-phases/`.

</details>

### 📋 v1.1 (not yet planned)

Scope is captured verbatim from the operator in
[`MILESTONE-CONTEXT.md`](MILESTONE-CONTEXT.md) — eight requested items, plus MFA-14 carried
over from v1.0. No phases exist yet; run `/gsd-new-milestone` to turn that context into
requirements and a roadmap.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Rename and Fail-Closed | v1.0 | 4/4 | Complete | 2026-07-29 |
| 2. Registry Seeding and Import-Step Ordering | v1.0 | 2/2 | Complete | 2026-07-29 |
| 3. Encrypted Seeds and Local QR | v1.0 | 3/3 | Complete | 2026-07-30 |
| 4. PAS Boundary | v1.0 | 4/4 | Complete | 2026-07-31 |
| 5. Drift, Replay and Lockout | v1.0 | 5/5 | Complete | 2026-08-03 |
| 6. Recovery Codes | v1.0 | 3/3 | Complete | 2026-08-04 |
| 7. Coexistence with imio.dms.mail | v1.0 | 4/4 | Complete | 2026-08-05 |
| 8. Coverage Instrument and Test Layers | v1.0 | 5/5 | Complete | 2026-08-06 |

## Carried into the next milestone

- **MFA-14** — turning on `globally_enabled` does not enroll accounts that already existed when
  the add-on is installed. The only v1.0 requirement that shipped unsatisfied. Described in
  full in [`MILESTONES.md`](MILESTONES.md) under Known Gaps.
- **The seed-key Puppet fragment has not shipped.** It lives in the separate
  `industrialisation` repository. Until it does, a production instance cannot decrypt or mint
  seeds. This is not one of this repository's commits, and it is the single thing standing
  between "code-complete" and "deployable".
