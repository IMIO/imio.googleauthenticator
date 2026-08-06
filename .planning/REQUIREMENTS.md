# Requirements: imio.googleauthenticator — v1.1 Enrollment Control and Account Safety

**Defined:** 2026-08-06
**Core Value:** A second factor that actually holds for in-site users, and that can be deployed
alongside `imio.dms.mail` without colliding with it.

Numbering continues from v1.0 (`.planning/milestones/v1.0-REQUIREMENTS.md`), where the highest
used were MFA-14, SEC-08, NOTF-03, BUG-06, DOC-04, QUAL-07, COEX-10, RECOV-07, REG-05, KEY-01,
RENAME-12. `UX` and `I18N` are new prefixes.

## v1.1 Requirements

### Global enforcement and enrollment

Covers the operator's requested items 2 and 3, which are the same problem as MFA-14 — the one
v1.0 requirement that shipped unsatisfied.

Decision taken 2026-08-06: "enrollment is never blocked unless the package is uninstalled" is
about **enrollment only**. The failed-attempt lockout shipped in v1.0 (MFA-08..MFA-13) is
unchanged and still applies to second-factor checks at login.

- [x] **MFA-15**: A user whose account existed before this add-on was installed is required to
      present a second factor at login when `globally_enabled` is on

- [x] **MFA-16**: With `globally_enabled` on, a user cannot turn their own second factor off
- [x] **MFA-17**: With `globally_enabled` off, a user can enroll themselves in a second factor
      from their own profile

- [x] **MFA-18**: The enrollment flow is reachable whenever the package is installed, whatever
      the global setting says

- [x] **MFA-19**: A user who was enrolled by the global setting rather than by their own action
      is shown the enrollment page (QR code and secret) before being asked for a code, instead of
      being asked for a code from an application they never set up

**Why MFA-19 is here.** The v1.0 close recorded that bulk enrollment through the control panel
mints a seed for every user but shows nobody a QR code. MFA-15 turns that from a latent problem
into a site-wide lockout the first time an administrator installs the add-on on a populated site.
The two must ship together.

### Account-change safety

Covers requested item 4.

Left for `/gsd-discuss-phase`, not decided here: how long a successful re-authentication stays
valid (single action or a short window), and whether a failed password re-authentication feeds
the same lockout counter as wrong TOTP codes. Feeding the same counter would let a user lock
themselves out of the login form by mistyping a password on a settings page.

- [ ] **SEC-09**: Enabling a second factor requires the user to re-enter their current password
      first

- [ ] **SEC-10**: Disabling a second factor requires the user to re-enter their current password
      first

- [ ] **SEC-11**: Regenerating recovery codes requires the user to re-enter their current
      password first

- [ ] **SEC-12**: A wrong password at the re-authentication prompt refuses the action and leaves
      the user's MFA state — enable flag, seed, recovery codes — unchanged

### Notifications

Covers requested item 6. There is no opt-out: no setting, user preference or memberdata property
suppresses these messages.

Decision taken 2026-08-06: a failed send does **not** block the MFA state change. Mail is not a
hard dependency of enabling or disabling a second factor.

- [ ] **NOTF-04**: The user is emailed when their second factor is enabled
- [ ] **NOTF-05**: The user is emailed when their second factor is disabled
- [ ] **NOTF-06**: The user is emailed when their recovery codes are regenerated
- [ ] **NOTF-07**: A notification that cannot be sent is logged at ERROR; the MFA state change is
      still committed and the user still sees the normal success page

### Defect fixes

- [x] **BUG-07**: A rejected recipient address in the bar-code reset email produces the in-page
      failure message every other failure path in that method uses, not an unhandled error.
      `browser/forms/request_bar_code_reset.py:112-113` catches `SMTPRecipientsRefused` and
      re-raises the same exception type, which the enclosing `except ValueError` cannot catch.
      Recorded as CR-01 in `08-REVIEW.md`; predates the fork; currently untested and uncovered

- [x] **BUG-08**: When an administrator views another user's profile
      (`/@@user-information?userid=<other>`), the `enable_two_factor_authentication` field
      description does not offer the `@@setup-two-factor-authentication` and
      `@@disable-two-factor-authentication` links. Today it does, and neither view accepts a
      target user from the request — both act on `api.user.get_current()` — so an administrator
      clicking "disable" clears their **own** seed, reset token and enable flag and is told it
      succeeded. Covers requested item 8

### Usability

- [x] **UX-01**: After completing MFA setup, the user lands on the site home page rather than
      their own profile page. Covers requested item 1

- [x] **UX-02**: The enrollment page shows the TOTP secret as selectable text alongside the QR
      code, for password managers and desktop TOTP clients. Covers requested item 5. The QR
      already encodes the same secret, so this adds no new secret to the page; it makes it
      copyable

### Translations

Covers requested item 7.

- [ ] **I18N-01**: The three strings the operator named render in French — "These codes are shown
      only this one time and cannot be retrieved again.", "regenerate recovery codes", and "Enter
      the verification code generated by your mobile application. If you have somehow lost your
      bar code, request a bar code reset here."

- [ ] **I18N-02**: Every user-facing string this milestone adds — the password re-authentication
      prompt and its error message, and the three notification emails — has a French translation

## Future Requirements

Acknowledged, tracked, not in this milestone's roadmap.

- **NOTF-01**: Email the user on account lockout (ASVS 2.2.3) — deferred since v1.0
- **NOTF-02**: Email the user when a recovery code is used — deferred since v1.0
- **Refuse a mismatched `userid` at the view.** Make `@@setup-two-factor-authentication` and
  `@@disable-two-factor-authentication` refuse to act when the request carries a `userid` naming
  someone other than the logged-in user. The operator chose on 2026-08-06 to hide the links only
  (BUG-08). **Residual risk, recorded so it is not lost:** a bookmarked or hand-typed
  `@@disable-two-factor-authentication` URL still silently disables the clicker's own second
  factor and reports success

- **An administrator-facing way to disable another user's second factor.** A new feature, not
  part of requested item 8. Would need its own permission check and its own audit trail

- **Turning `globally_enabled` off does not un-enroll anyone** — the disable call in
  `browser/controlpanel.py` is commented out and only writes a debug log line. Under MFA-17,
  users self-enroll when the setting is off, so leaving existing enrollments in place is
  defensible. Revisit if an operator ever needs a real site-wide un-enroll

## Out of Scope

| Feature | Reason |
|---------|--------|
| Relaxing the lockout so it cannot block enrollment | Operator decision 2026-08-06: "never blocked" is about enrollment only. Relaxing it would contradict MFA-08..MFA-13 as shipped |
| Blocking an MFA state change when its notification email fails to send | Operator decision 2026-08-06. A broken mail server would otherwise block all enrollment |
| Emailing recovery codes themselves | Defeats the point of showing them once. A notification that codes *were regenerated* is in scope (NOTF-06); the codes are not |
| Python 3 migration | Keycloak supersedes this package before it would pay off. Carried from v1.0 |
| Plone 5 / Plone 6 support | Same reason. This package dies with Plone 4. Carried from v1.0 |
| MFA for Zope root admins | They live in the root `acl_users`, which an in-site PAS plugin never sees. Architecturally unreachable. Carried from v1.0 |
| WebAuthn / U2F / SMS fallback | Recovery codes already cover the lost-device case. Carried from v1.0 |
| "Remember this device" | Weakens the second factor for a convenience nobody asked for. Carried from v1.0 |

## Open questions for `/gsd-discuss-phase`

These change how the work is built, not whether it is in scope. They are deliberately not
answered here.

1. **Re-authentication lifetime** — is a successful password re-authentication good for one
   action, or for a short window covering several changes?

2. **Re-authentication and the lockout counter** — does a failed password re-auth feed the same
   counter as wrong TOTP codes, or a separate one?

3. **Where global enforcement is checked** — enroll at install time, consult the global setting
   in the login gate, or both. Three candidate remedies are written up in
   `.planning/milestones/v1.0-phases/07-coexistence-with-imio-dms-mail/07-UAT.md`

4. **Whether UX-02 needs the SEC-09..SEC-11 re-authentication gate** — showing the secret as text
   makes it copyable and shoulder-surfable, even though the QR already encodes it

5. **Whether BUG-08's fix belongs in `browser/settings_helper.py`**, which already decides which
   menu links to show, or in the field description itself (`userdataschema.py:76-83`)

## Traceability

Populated during roadmap creation, 2026-08-06. Phase numbering continues from v1.0, which
ended at Phase 8.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MFA-15 | Phase 10 | Complete |
| MFA-16 | Phase 10 | Complete |
| MFA-17 | Phase 10 | Complete |
| MFA-18 | Phase 10 | Complete |
| MFA-19 | Phase 10 | Complete |
| SEC-09 | Phase 11 | Pending |
| SEC-10 | Phase 11 | Pending |
| SEC-11 | Phase 11 | Pending |
| SEC-12 | Phase 11 | Pending |
| NOTF-04 | Phase 12 | Pending |
| NOTF-05 | Phase 12 | Pending |
| NOTF-06 | Phase 12 | Pending |
| NOTF-07 | Phase 12 | Pending |
| BUG-07 | Phase 9 | Complete |
| BUG-08 | Phase 9 | Complete |
| UX-01 | Phase 9 | Complete |
| UX-02 | Phase 9 | Complete |
| I18N-01 | Phase 13 | Pending |
| I18N-02 | Phase 13 | Pending |

**Coverage:**

- v1.1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

Each requirement is mapped to exactly one phase. By phase: Phase 9 — 4, Phase 10 — 5,
Phase 11 — 4, Phase 12 — 4, Phase 13 — 2.

Two mappings are forced rather than chosen, and are recorded in `ROADMAP.md` phase notes:
MFA-19 is in the same phase as MFA-15 because shipping MFA-15 alone is a site-wide lockout on
the first install onto a populated site, and BUG-07 precedes NOTF-04..07 because those three new
senders would otherwise land on a mail path with an unhandled `SMTPRecipientsRefused`.

One mapping may move at `/gsd-discuss-phase` time, driven by open question 4: if showing the
secret as text needs the re-authentication gate, UX-02 moves from Phase 9 to Phase 11.

---
*Requirements defined: 2026-08-06*
*Last updated: 2026-08-06 — traceability populated at roadmap creation (Phases 9-13)*
