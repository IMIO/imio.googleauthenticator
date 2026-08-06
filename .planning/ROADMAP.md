# Roadmap: imio.googleauthenticator

## Milestones

- ✅ **v1.0 Hardened MFA** — Phases 1-8 (shipped 2026-08-06) — [full roadmap](milestones/v1.0-ROADMAP.md) · [requirements](milestones/v1.0-REQUIREMENTS.md) · [audit](milestones/v1.0-MILESTONE-AUDIT.md) · [summary](MILESTONES.md)
- 🚧 **v1.1 Enrollment Control and Account Safety** — Phases 9-13 (in progress)

## Overview

v1.0 made the second factor hold once a user has one. v1.1 makes getting one — and changing
one — correct. Five phases: clear the standing defects on the paths the feature work builds on,
make `globally_enabled` mean what its own description says without locking a populated site out,
put the account's own password in front of every change to its second factor, tell the user by
email when that second factor changes, and finish with every string a French-speaking user meets
rendering in French.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order. Numbering continues
across milestones — v1.1 starts at Phase 9, never back at 1.

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

### 🚧 v1.1 Enrollment Control and Account Safety (Phases 9-13)

**Milestone Goal:** Make enrollment do what the settings say it does, and make every change to a
user's second factor safe, announced, and readable in French.

- [x] **Phase 9: Mail Path and Profile-Page Correctness** - The standing defects and usability gaps on the paths the rest of the milestone builds on (completed 2026-08-06)
- [ ] **Phase 10: Global Enforcement and Enrollment** - `globally_enabled` covers accounts that predate the install, and nobody is asked for a code from an app they never set up
- [ ] **Phase 11: Re-authentication Before MFA Changes** - The account's own password stands in front of enabling, disabling and regenerating
- [ ] **Phase 12: MFA Change Notifications** - The user is emailed on every second-factor change, and a mail failure never costs them the change
- [ ] **Phase 13: French Translations** - Every string a French-speaking user meets renders in French, including everything this milestone added

## Phase Details

### Phase 9: Mail Path and Profile-Page Correctness

**Goal**: The bar-code reset email fails the way every other failure on that form fails, an
administrator cannot be tricked into clearing their own second factor from someone else's
profile, and the enrollment page hands the user a secret they can actually use.
**Depends on**: Nothing (first v1.1 phase; builds on shipped v1.0 code)
**Requirements**: BUG-07, BUG-08, UX-01, UX-02
**Success Criteria** (what must be TRUE):

  1. A user whose email address the mail server rejects when they request a bar-code reset sees
     the same in-page failure message the form's other failure paths show, and no error page.

  2. An administrator viewing another user's profile at `/@@user-information?userid=<other>` is
     offered no "set it up" and no "disable it" link, so there is no link there that can act on
     the administrator's own account.

  3. A user who finishes MFA setup ends up on the site home page, not on their own profile page.
  4. The enrollment page shows the TOTP secret as selectable text beside the QR code, and it can
     be copied into a password manager or a desktop TOTP client that then produces accepted codes.
**Plans**: 4/4 plans executed

Plans:
**Wave 1**

- [x] 09-01-PLAN.md — BUG-07: a refused or unreachable mail server reports in-page, not as an error page
- [x] 09-02-PLAN.md — BUG-08: the profile field description offers no link that acts on the viewing administrator
- [x] 09-03-PLAN.md — UX-01 + UX-02: enrollment exits to the home page, and shows the secret as copyable text

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 09-04-PLAN.md — phase gate: full suite, coverage and lint over the merged phase, changelog, TOTP-client UAT

**Notes**:

- BUG-07 first, and in this phase rather than with the notifications: Phase 12 adds three new
  senders to this package's mail path, which today has exactly one unhandled
  `SMTPRecipientsRefused` (`browser/forms/request_bar_code_reset.py:112-113` re-raises the same
  exception type the enclosing `except ValueError` cannot catch). Fixing it here means Phase 12
  builds on a mail path whose failure behaviour is defined and covered. Those two lines are
  currently uncovered, so the fix needs its own test to keep the 90% CI gate honest.

- BUG-08 is the field description at `userdataschema.py:76-83`, not
  `browser/settings_helper.py` — settings_helper drives portal *actions*, a different surface
  that Phase 10 rewrites. Open question 5 in `REQUIREMENTS.md` picks between the two; the
  wrong-account links live in the schema field. Refusing a mismatched `userid` at the view
  itself is explicitly a Future Requirement, not this phase — the residual risk of a
  hand-typed `@@disable-two-factor-authentication` URL is recorded there.

- UX-01 must not undo RECOV-03. `browser/forms/user_setup.py` deliberately leaves
  `redirect_url = None` on the success path so the ten recovery codes render in that same
  response; the one-time display depends on the response *not* being a 302. "Lands on the home
  page" therefore has to be reached from the recovery-codes page, not by restoring a redirect in
  `handleSubmit`. The comment block at `user_setup.py:162-176` says so in the source.

- UX-02 adds no new secret to the page — the QR at `updateFields` already encodes it — but it
  does make it copyable and shoulder-surfable. Open question 4 asks whether it needs Phase 11's
  re-authentication gate; if the answer is yes, this criterion moves to Phase 11.

### Phase 10: Global Enforcement and Enrollment

**Goal**: `globally_enabled` means what its own description says — every account inside the site
presents a second factor, including accounts that existed before the add-on was installed — and
every account it catches is walked through enrollment instead of being locked out.
**Depends on**: Phase 9
**Requirements**: MFA-15, MFA-16, MFA-17, MFA-18, MFA-19
**Success Criteria** (what must be TRUE):

  1. An account that existed before this add-on was installed is asked for a second factor at its
     next login when `globally_enabled` is on.

  2. A user caught by the global setting who has never enrolled is shown the enrollment page — QR
     code and secret — before being asked for any code, and can complete enrollment from there.

  3. With `globally_enabled` on, a user who tries to turn their own second factor off is refused,
     and still has a working second factor afterwards.

  4. With `globally_enabled` off, a user can enroll themselves from their own profile, and is
     asked for a second factor at their next login.

  5. Whatever the global setting says, an installed site always has a reachable enrollment path —
     no combination of settings leaves a user unable to enroll.
**Plans**: 5/6 plans executed

Plans:
**Wave 1**

- [x] 10-01-PLAN.md — tracer: install enrols a pre-existing account and that account is walked
      through enrollment at login, end to end (MFA-15 + MFA-19 as one deliverable)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 10-02-PLAN.md — the install-time enrollment matrix: idempotency, zero users, the setting off,
      no encryption key, and a partial failure that reports itself (MFA-15, D-04, D-13)

- [x] 10-03-PLAN.md — both disable views refuse while global enforcement is on (MFA-16, D-08, D-18)
- [x] 10-04-PLAN.md — the three link conditions corrected, the regenerate action rewired, and
      tests/test_settings_helper.py created from scratch (MFA-17, MFA-18, D-10, D-11, D-15)

- [x] 10-05-PLAN.md — MFA-19 hardening: the PAS-plugin state-write guard extended, a clean refusal
      on a missing seed key (D-07), and the new property proven memberdata-only (D-17)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 10-06-PLAN.md — phase gate: full suite, branch coverage, lint, changelog, the 18-decision
      ledger, and the two manual verifications

**Notes**:

- MFA-19 ships in this phase, with MFA-15, not after it. The v1.0 close recorded that bulk
  enrollment mints a seed for every user but shows nobody a QR code; MFA-15 turns that latent
  problem into a site-wide lockout the first time an administrator installs onto a populated
  site. Criteria 1 and 2 are one deliverable.

- This is MFA-14, the one v1.0 requirement that shipped unsatisfied, restated as five. Today
  `is_two_factor_authentication_globally_enabled()` is consulted only by
  `userdataschema.userCreatedHandler` and by `browser/settings_helper.py`; the login gate reads
  each user's own `enable_two_factor_authentication` memberdata flag and never the global
  setting. Existing users are enrolled only when an administrator saves the control panel form
  (`browser/controlpanel.py:125-132`); `setuphandlers.setupVarious` enrolls nobody.

- Open question 3 (`REQUIREMENTS.md`) is the design decision here: enroll at install time,
  consult the global setting in the login gate, or both. Three candidate remedies are written up
  in `.planning/milestones/v1.0-phases/07-coexistence-with-imio-dms-mail/07-UAT.md`.

- MFA-17 inverts a live condition: `settings_helper.show_enable_two_factor_authentication_link`
  currently requires `is_two_factor_authentication_globally_enabled()` to be **True** before it
  will offer the enable link, which is exactly backwards for self-enrollment when the setting is
  off. `show_disable_...` has the mirror problem against MFA-16.

- "Enrollment is never blocked unless the package is uninstalled" is about enrollment only
  (decision 2026-08-06). The failed-attempt lockout shipped in v1.0 (MFA-08..MFA-13) is
  unchanged and still applies to second-factor checks at login. Relaxing it is Out of Scope.

- Any new memberdata property this phase introduces needs a
  `profiles/default/memberdata_properties.xml` entry plus a set/get round-trip test —
  `MutablePropertySheet.setProperties` silently pops undeclared keys with no error. Any new
  MFA state write goes in a committing view, never in the PAS plugin; the source-grep guard
  `tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin` enforces this
  and must be extended, not worked around.

### Phase 11: Re-authentication Before MFA Changes

**Goal**: A walk-up at an unlocked browser cannot change an account's second factor — enabling,
disabling and regenerating recovery codes each require that account's own password.
**Depends on**: Phase 10
**Requirements**: SEC-09, SEC-10, SEC-11, SEC-12
**Success Criteria** (what must be TRUE):

  1. Enabling a second factor asks for the current password first, and does not complete until a
     correct one is given.

  2. Disabling a second factor asks for the current password first, and does not complete until a
     correct one is given.

  3. Regenerating recovery codes asks for the current password first, and does not complete until
     a correct one is given.

  4. A wrong password at that prompt refuses the action and leaves the account's enable flag,
     stored seed and recovery codes exactly as they were — the previous codes still work.
**Plans**: TBD

**Notes**:

- After Phase 10, not before: Phase 10 rewrites the reachability and outcome of the same three
  actions this phase gates. Gating a flow that is about to change means doing it twice.

- Two open questions must be settled at `/gsd-discuss-phase` (they are listed in
  `REQUIREMENTS.md` and deliberately not answered there): how long a successful
  re-authentication stays valid (one action, or a short window covering several changes), and
  whether a failed password re-auth feeds the same lockout counter as wrong TOTP codes. Feeding
  the same counter lets a user lock themselves out of the *login form* by mistyping a password
  on a settings page — the same class of hazard that kept `user_setup.py` off the counter until
  quick task `260806-fsp`.

- Criterion 4 is the one that needs a real negative test per path: `disable()` in
  `browser/disable_two_factor_authentication.py` currently clears the enable flag, the seed and
  the reset token in a single `setMemberProperties` call, so a gate that runs in the wrong place
  leaves a partially cleared account.

- If open question 4 resolves "yes", UX-02 (the plaintext secret on the enrollment page) is
  gated here and its criterion moves from Phase 9 into this phase.

### Phase 12: MFA Change Notifications

**Goal**: A user finds out by email every time their second factor changes, with no opt-out
anywhere, and a mail server that refuses the message never costs them the change.
**Depends on**: Phase 11, Phase 9
**Requirements**: NOTF-04, NOTF-05, NOTF-06, NOTF-07
**Success Criteria** (what must be TRUE):

  1. A user whose second factor is enabled receives an email saying so, and no setting, user
     preference or memberdata property anywhere suppresses it.

  2. A user whose second factor is disabled receives an email saying so.
  3. A user whose recovery codes are regenerated receives an email saying so, and that email does
     not contain the codes themselves.

  4. When the mail server refuses the message, the user still sees the normal success page, the
     change is still in effect after a reload, and the failure appears in the log at ERROR.
**Plans**: TBD

**Notes**:

- Last of the two feature phases, and after Phase 11 by design: these notifications fire on the
  *outcome* of the same three actions Phase 11 puts a gate in front of. Hooking a settled flow is
  cheaper than re-hooking a changing one.

- Depends on Phase 9 for BUG-07. Three new senders on a path with one unhandled
  `SMTPRecipientsRefused` is how criterion 4 turns into a 500 instead of a log line.

- A failed send does **not** block the state change (decision 2026-08-06). Mail is not a hard
  dependency of enabling or disabling a second factor; blocking would let a broken mail server
  block all enrollment. That is recorded in `REQUIREMENTS.md` Out of Scope.

- Emailing the recovery codes themselves stays Out of Scope — it defeats the point of showing
  them once. Criterion 3 is a notification that codes *were* regenerated, nothing more.

- Notification on lockout (NOTF-01) and on recovery-code *use* (NOTF-02) are Future
  Requirements, not this phase.

- `request_bar_code_reset.py:98-105` records why `charset='utf-8'` is not optional on
  `MailHost.send`: without it a single accented character aborts the send. The three new senders
  inherit that, and Phase 13 puts accented characters in all of them.

### Phase 13: French Translations

**Goal**: Every string a French-speaking user meets in this package renders in French, including
every string this milestone added.
**Depends on**: Phase 12
**Requirements**: I18N-01, I18N-02
**Success Criteria** (what must be TRUE):

  1. The three strings the operator named render in French: "These codes are shown only this one
     time and cannot be retrieved again.", "regenerate recovery codes", and the token-form
     instruction "Enter the verification code generated by your mobile application. If you have
     somehow lost your bar code, request a bar code reset here."

  2. The password re-authentication prompt and its wrong-password error message render in French.
  3. The three MFA change notification emails arrive in French for a user in a French locale.
  4. After a catalogue rebuild, no msgid added anywhere in v1.1 is left untranslated in the
     French catalogue.
**Plans**: TBD

**Notes**:

- Last by dependency, not by preference: I18N-02 covers the strings SEC-09..11 and NOTF-04..06
  introduce, so it cannot complete before Phases 11 and 12 do. I18N-01 has no such dependency
  and could land any time; it is here so this phase is a coherent "the package reads in French"
  deliverable rather than a one-requirement leftover.

- `src/imio/googleauthenticator/rebuild_i18n.sh` and `locales/` carry the `imio.googleauthenticator`
  domain after the Phase 1 rename. Phase 1 also recorded roughly 19 pre-existing untranslated
  msgids surfaced by a `rebuild-pot` run and deferred them; criterion 1 names the three the
  operator actually asked for, and criterion 4 is scoped to v1.1 additions — clearing the rest
  is optional, not a gate.

- Watch `bin/code-analysis` on the `.po`/`.pot` sweep and the trailing-whitespace hazard Phase 8
  hit inside quoted strings: an edit inside a translated message is exactly the case the v1.0
  threat model put off limits.

## Progress

**Execution Order:**
Phases execute in numeric order: 9 → 10 → 11 → 12 → 13

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
| 9. Mail Path and Profile-Page Correctness | v1.1 | 4/4 | Complete    | 2026-08-06 |
| 10. Global Enforcement and Enrollment | v1.1 | 5/6 | In Progress|  |
| 11. Re-authentication Before MFA Changes | v1.1 | 0/TBD | Not started | - |
| 12. MFA Change Notifications | v1.1 | 0/TBD | Not started | - |
| 13. French Translations | v1.1 | 0/TBD | Not started | - |

## Standing constraints for every v1.1 phase

Carried from v1.0 and still binding. These are not phase goals; they are the conditions any
phase's commits have to satisfy.

- Python 2.7.18 / Plone 4.3 only. Nothing may require PEP 517 — `requirements-4.3.txt` pins
  `setuptools 44.1.1`.

- Branch coverage stays above 90%, enforced in CI by `bin/test-coverage -t '!robot'`.
- `bin/code-analysis` keeps exiting 0 — the buildout's git pre-commit hook depends on it.
- Every new memberdata property needs a `profiles/default/memberdata_properties.xml` entry plus
  a set/get round-trip test; `MutablePropertySheet.setProperties` silently pops undeclared keys.

- Every MFA state write happens inside a committing view, never in the PAS plugin or a challenge
  plugin. A write in the plugin is discarded by `transaction.abort()` on any request that raises.

- No wholesale skin or resource-registry override, and nothing that mutates a resource this
  package does not own — `imio.dms.mail` has to install in either order.

## Outstanding outside this roadmap

- **The seed-key Puppet fragment has not shipped.** It lives in the separate `industrialisation`
  repository. Until it does, a production instance cannot decrypt or mint seeds — `base.cfg:54`
  sets `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` in the `[testenv]` section only, so `bin/test` and
  `bin/test-coverage` have it and `bin/instance` does not. This is not one of this repository's
  commits, and it remains the single thing standing between "code-complete" and "deployable".
  v1.1 does not change that and cannot close it.
