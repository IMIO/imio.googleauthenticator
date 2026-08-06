# Phase 9: Mail Path and Profile-Page Correctness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-06
**Phase:** 9-Mail Path and Profile-Page Correctness
**Areas discussed:** Where the user lands after enrollment (UX-01); Showing the TOTP secret as text (UX-02)

---

## Area selection

Four gray areas were offered. The operator selected two.

| Gray area | Selected |
|-----------|----------|
| Mail failure scope and message (BUG-07) | |
| Removing the wrong-account links (BUG-08) | |
| What "lands on the home page" means (UX-01) | ✓ |
| Showing the secret, and whether it stays here (UX-02) | ✓ |

BUG-07 and BUG-08 therefore fell to Claude's discretion; the decisions taken for them are
recorded in CONTEXT.md as D-09 through D-17 and are listed at the end of this log.

---

## Where the user lands after enrollment (UX-01)

### Q1 — How should the user get from the recovery-codes page to the home page?

| Option | Description | Selected |
|--------|-------------|----------|
| Retarget the existing link | `recovery_codes.pt:24` currently links to `@@personal-information`. Point it at the site home page and relabel it. One attribute plus one string; nothing else in the flow changes. | ✓ |
| Add an acknowledge button that redirects | Replace the link with an "I have saved my codes" button that POSTs and then redirects. Forces a deliberate action, but adds a form handler and a route to test. | |
| Keep both links | Add a home-page link beside the existing profile link. Nobody loses the profile shortcut, but two links do not decide where the user ends up. | |

**User's choice:** Retarget the existing link.

### Q2 — Which URL should "home page" resolve to?

| Option | Description | Selected |
|--------|-------------|----------|
| Navigation root | `globals_view/navigationRootUrl` — the expression `actions.xml` already uses for all three MFA links. Correct in a subsite and correct from a deep context. | ✓ |
| Whatever context the form is on | `context/absolute_url` — shortest diff, correct today only because the portal action lands the user on the navigation root. | |
| Always the true portal root | Predictable, but sends a subsite user out of their subsite. | |

**User's choice:** Navigation root.

### Q3 — Does the non-site-local-user refusal redirect change too?

| Option | Description | Selected |
|--------|-------------|----------|
| Leave it on the profile page | Criterion 3 is about a user who finishes setup; a refused user has not. Keeps the diff to the recovery-codes template. | ✓ |
| Send refusals home too | Every exit from the setup form ends on the home page. More consistent, but moves a redirect no requirement covers. | |

**User's choice:** Leave it on the profile page.

### Q4 — What should the link text say?

| Option | Description | Selected |
|--------|-------------|----------|
| "Continue to the home page" | Direct rewrite of the existing sentence; says where the link goes; obvious French equivalent for Phase 13. | ✓ |
| "I have saved my codes" | Names what the user is confirming, but promises a confirmation step that does not exist on a link. | |
| "Done" | Shortest and trivially translatable, but gives no clue where the user lands. | |

**User's choice:** "Continue to the home page".

**Notes:** The hard constraint stated before the questions and not challenged: the enrollment
success response must stay at HTTP 200, because the one-time recovery-code display depends on it
not being a 302 (RECOV-03, documented in `user_setup.py:162-176`). Every option offered acted on
the recovery-codes page rather than on `handleSubmit`.

---

## Showing the TOTP secret as text (UX-02)

### Q1 — Does this need Phase 11's re-authentication gate, which would move the criterion out of Phase 9?

| Option | Description | Selected |
|--------|-------------|----------|
| Stays in Phase 9 | The QR beside it already encodes the same secret and is shown ungated today. Phase 11's SEC-09 gate goes in front of this whole enrollment flow later, so the display inherits it without the requirement moving. | ✓ |
| Moves to Phase 11 | The copyable text never ships ungated. Costs Phase 9 one of four criteria, enlarges Phase 11, and leaves the ungated QR exposing the same secret meanwhile. | |

**User's choice:** Stays in Phase 9.
**Notes:** This answers `REQUIREMENTS.md` open question 4 and fixes the one traceability mapping
that was recorded as possibly-moving.

### Q2 — Visible on arrival, or behind a reveal control?

| Option | Description | Selected |
|--------|-------------|----------|
| Always visible beside the QR | Hiding text while showing the code that encodes it protects nothing. No JavaScript, nothing added to `jsregistry.xml`. | ✓ |
| Native `<details>` disclosure | One HTML element, no script. Keeps the secret out of a casual screenshot, but anyone who opens it or photographs the QR gets the same value. | |
| Reveal via a JavaScript button | Permitted — the package owns `browser/static/main.js` and registers it — but new script for a control the visible QR defeats. | |

**User's choice:** Always visible beside the QR.

### Q3 — The secret itself, or the full provisioning URI?

| Option | Description | Selected |
|--------|-------------|----------|
| The base32 secret only | What every app asks for under "setup key". Short, and exactly what `get_or_create_secret()` already returns. | ✓ |
| The full `otpauth://` URI | Carries account name and issuer, but long, ugly, and some clients take only a bare secret. | |
| Both, labelled separately | Covers every client, but doubles what a screenshot captures for a case neither alone fails. | |

**User's choice:** The base32 secret only.

### Q4 — Where should the secret text be produced?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend `get_token_description()` | It already calls `get_or_create_secret()` to build the QR, so no second lookup and no second mint. Stays inside the site-local branch, so a Zope-root account still gets the refusal message and no seed. | ✓ |
| A second read-only form field | Cleaner schema separation, but needs its own secret call and its own non-site-local guard. | |
| In the form template | Keeps `helpers.py` untouched, but `SetupForm` has no custom template today. | |

**User's choice:** Extend `get_token_description()`.

---

## Claude's Discretion

The operator did not select these two areas. Decisions taken and recorded in CONTEXT.md:

- **BUG-07 (D-09..D-13)** — catch every SMTP-level *and* network-level send failure rather than
  only `SMTPRecipientsRefused`; delete the pointless inner re-raise; reuse the existing
  "An unexpected error occurred." message rather than adding a msgid or a new enumeration signal;
  leave the already-written `bar_code_reset_token` in place on failure; test through the existing
  `MailBase._send` patch harness.
- **BUG-08 (D-14..D-17)** — delete both links from the field description outright rather than
  making the description conditional, because `CustomizedUserDataPanel` already omits that field
  from `@@personal-information`, so `@@user-information` is the only form that renders it;
  replacement text is the first sentence already present; catalogue cleanup is left to Phase 13;
  the test asserts absence of the two view names, not the replacement wording.

## Deferred Ideas

- Refusing a mismatched `userid` at the two views — already a Future Requirement; residual risk
  restated in CONTEXT.md.
- Sweeping the msgids orphaned by the BUG-08 description edit — Phase 13 owns catalogue rebuilds.
- `profiles/default/site_properties.xml`, dead since Phase 1 and tied to no requirement.
