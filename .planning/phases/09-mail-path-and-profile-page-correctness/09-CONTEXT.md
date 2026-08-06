# Phase 9: Mail Path and Profile-Page Correctness - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Four independent corrections to shipped v1.0 code, on the paths the rest of v1.1 builds on. No
new capability; nothing here changes what the second factor does.

1. **BUG-07** — `browser/forms/request_bar_code_reset.py:112-113` catches `SMTPRecipientsRefused`
   and re-raises the same exception type. The enclosing `except ValueError` cannot catch it, so a
   mail server that rejects the recipient produces an error page instead of the in-page failure
   message every other failure path in that method produces. Phase 12 adds three more senders to
   this same path.
2. **BUG-08** — the `enable_two_factor_authentication` field description at
   `userdataschema.py:76-83` carries two links. Neither `@@setup-two-factor-authentication` nor
   `@@disable-two-factor-authentication` accepts a target user from the request; both act on
   `api.user.get_current()`. An administrator who clicks "disable" while viewing someone else's
   profile clears their **own** seed, reset token and enable flag, and is told it succeeded.
3. **UX-01** — a user who finishes enrollment ends on the recovery-codes page, whose only link
   points at their own profile. The criterion asks for the site home page.
4. **UX-02** — the enrollment page shows a QR code but no copyable text form of the same secret.

**Not this phase:**
- Refusing a mismatched `userid` at the view itself. That is a Future Requirement in
  `REQUIREMENTS.md`, with its residual risk recorded there: a bookmarked or hand-typed
  `@@disable-two-factor-authentication` URL still disables the clicker's own second factor.
- Anything in `browser/settings_helper.py`. It drives portal *actions*, a different surface that
  Phase 10 rewrites (MFA-17 inverts its conditions).
- Any change to what `globally_enabled` does (Phase 10), any password gate (Phase 11), any
  notification email (Phase 12), any catalogue rebuild (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### Where the user lands after enrollment (UX-01) — *discussed*

- **D-01:** **Retarget the existing link on the recovery-codes page.** `recovery_codes.pt:24`
  currently reads
  `href="string:${context/absolute_url}/@@personal-information"` with the text "Continue to your
  profile". That link becomes the home-page link. Nothing else in the enrollment flow changes.
  **Rejected:** an acknowledge button ("I have saved my codes") that POSTs and then redirects —
  it forces a deliberate action before the codes leave the screen, but it adds a new form handler
  and a new route to test for a criterion a link already satisfies. **Also rejected:** adding a
  second link beside the existing one — the criterion says the user *ends up* on the home page,
  and two links do not decide where they end up.

- **D-02:** **"Home page" resolves through `globals_view/navigationRootUrl`,** the same expression
  `profiles/default/actions.xml` already uses on all three of this package's action URLs
  (lines 11, 24, 45). Correct inside a subsite, and correct even if the setup form was reached
  from a deeper context. **Rejected:** the bare `context/absolute_url` the template already uses
  (shortest diff, correct today only because the portal action lands the user on the navigation
  root, wrong the moment anyone reaches the form from a folder URL). **Also rejected:** the true
  portal root (sends a subsite user out of their subsite).

- **D-03:** **The refusal redirect stays put.** `user_setup.py:91-93` sends a user whose account is
  not defined inside the Plone site to `@@personal-information` (the T-03-23 arm). That user has
  not finished setup, so criterion 3 does not cover them, and the profile page is where they can
  see their own account state. Not touched by this phase.

- **D-04:** **The link text becomes "Continue to the home page."** A direct rewrite of the existing
  sentence. This retires the msgid "Continue to your profile" and adds a new one, which is a
  Phase 13 input (I18N-02 covers every user-facing string this milestone adds).

**Hard constraint on all of D-01..D-04 — do not work around it.** The success path in
`user_setup.py::handleSubmit` leaves `redirect_url = None` deliberately, and
`user_setup.py:162-176` says so in the source. `plone.z3cform` 0.8.1's `FormWrapper.update()`
blanks the wrapped form only when the response status is 302 or 303, so the one-time recovery-code
display exists *because* that response is not a redirect. UX-01 must be reached from the
recovery-codes page. Restoring a redirect in `handleSubmit` would undo RECOV-03.

### Showing the TOTP secret as text (UX-02) — *discussed*

- **D-05:** **UX-02 stays in Phase 9.** This settles `REQUIREMENTS.md` open question 4, and the
  Phase 9 ↔ Phase 11 mapping recorded as possibly-moving in the traceability table is now fixed at
  Phase 9. Reasoning: the QR beside it already encodes the same secret and is rendered today with
  no gate at all, so the text hands out no secret the page did not already hand out — it adds
  shoulder-surfability and screenshot-readability to a value already on screen. Phase 11's SEC-09
  puts a password prompt in front of this same enrollment action later, so the display inherits
  that gate without the requirement having to move. **Rejected:** moving the criterion to Phase 11
  so the copyable text never ships ungated (it costs Phase 9 a quarter of its scope and leaves the
  ungated QR exposing the same secret in the meantime).

- **D-06:** **Always visible beside the QR.** No reveal control. Hiding the text while displaying
  the code that encodes it protects nothing. No JavaScript, no template logic, nothing added to
  `profiles/default/jsregistry.xml`. **Rejected:** a native `<details>` disclosure (one HTML
  element, no script, keeps the secret out of a casual screenshot — but anyone who opens it or
  photographs the QR gets the same value). **Also rejected:** a JavaScript reveal button (the
  package does own `browser/static/main.js` and registers it, so it is permitted under the
  coexistence rule, but it is new script for a control the visible QR already defeats).

- **D-07:** **Show the base32 secret only, not the `otpauth://` URI.** The base32 string is what
  every authenticator app and password manager asks for under "setup key" or "secret", it is short
  enough to read or retype, and it is exactly what `helpers.get_or_create_secret()` already
  returns — no new formatting code. **Rejected:** the full `otpauth://` URI (carries account name
  and issuer, so a client that accepts it gets a labelled entry, but it is long, ugly on the page,
  and some clients take only a bare secret). **Also rejected:** showing both (covers every client,
  but puts two representations of one secret on the page for a case neither alone fails).

- **D-08:** **Produced by extending `helpers.get_token_description()`** (`helpers.py:330-348`),
  whose return value `SetupForm.updateFields` already assigns to the `qr_code` field's
  description. That function already calls `get_or_create_secret(user, overwrite=overwrite_secret)`
  to build the QR, so the secret is in hand — emitting it beside the image needs no second lookup
  and mints nothing twice. It also keeps the change inside the site-local branch of
  `user_setup.py:196-210`, so a Zope-root account still gets the T-03-23 refusal message and still
  has no seed minted for it. **Rejected:** a second read-only field on `ISetupForm` (cleaner schema
  separation, but it needs its own `get_or_create_secret()` call and its own guard against the
  non-site-local case that `user_setup.py` already handles once). **Also rejected:** rendering it
  from a page template (`SetupForm` has no custom template today — it renders through standard
  z3c.form machinery, so this means adding one).

### Claude's Discretion

Two areas the operator chose not to discuss. Decisions taken and recorded here so downstream
agents do not reopen them.

#### BUG-07 — the mail failure path

- **D-09:** **Catch every SMTP-level and network-level send failure, not only
  `SMTPRecipientsRefused`.** `smtplib.SMTPRecipientsRefused` is a subclass of
  `smtplib.SMTPException` (verified in the project's own Python 2.7:
  `SMTPRecipientsRefused → SMTPException → Exception`), and a refused *connection* — no mail
  server reachable, the common production failure — raises `socket.error`, which is not an
  `SMTPException` at all. Handling only the named exception leaves every sibling failure on this
  path still producing an error page, and Phase 12 is about to add three more senders to it. The
  roadmap's own reason for putting BUG-07 first is "a mail path whose failure behaviour is
  defined and covered", which a one-exception patch does not deliver.
  — **Reversibility:** reversible — one `except` clause in one method.

- **D-10:** **Delete the inner `except SMTPRecipientsRefused: raise SMTPRecipientsRefused(...)`
  re-raise entirely.** Those two lines exist only to re-label an exception with a string nobody
  reads, and they are the defect. The send failure reaches the method's shared
  `if reason is not None:` tail, which is how every other failure in this method already reports
  itself.

- **D-11:** **Reuse the existing message `_("An unexpected error occurred.")`,** the same one the
  `except ValueError` arm sets. BUG-07's wording is "the in-page failure message every other
  failure path in that method uses", so this is what the requirement asks for literally. Two
  further reasons: it adds no msgid, so Phase 13 inherits nothing from this fix; and a distinct
  "we could not email that address" message would tell an anonymous submitter something about the
  address, widening the username-enumeration oracle already accepted at low severity on this form
  (T-03-26). Log the real cause with `logger.exception`, which this method already does on the
  `ValueError` arm.

- **D-12:** **The already-written `bar_code_reset_token` is not rolled back on a send failure.**
  `request_bar_code_reset.py:85` writes the token before the send. A stored token grants nothing
  on its own — the reset URL is usable only with the `ska` signature that went into the email that
  was never delivered — so the only consequence is that an older, unclicked reset link is now
  invalid. Rolling it back is machinery for no gain. Recorded so a reviewer does not read it as an
  oversight.

- **D-13:** **The test reuses the existing harness.** `tests/test_request_bar_code_reset.py`
  already patches `Products.MailHost.MailHost.MailBase._send` (with a comment at lines 31-37
  explaining why it patches `_send` rather than swapping in a mock MailHost). The new test makes
  that patch raise, and asserts the error status message appears and no exception escapes. Lines
  112-113 are currently uncovered, so this test is also what keeps the 90% CI gate honest here.
  It needs the project's standard non-vacuity check: prove it goes red against the unfixed source,
  then restore the source byte-identical.

#### BUG-08 — the wrong-account links

- **D-14:** **Delete both links from the field description outright; do not make the description
  conditional.** The fix site is `userdataschema.py:78-80`, which the roadmap already settled
  (`REQUIREMENTS.md` open question 5 is answered: the schema field description, not
  `settings_helper.py`).
  The deciding fact, verified in the source: `CustomizedUserDataPanel.__init__`
  (`userdataschema.py:38-42`) omits `enable_two_factor_authentication` from
  `@@personal-information`. So the **only** form that renders this description is
  `@@user-information` — the administrator-viewing-another-user surface, which is exactly where
  the links are harmful. No ordinary user reaches these links through this description at all;
  their route is the portal actions in `profiles/default/actions.xml`, which build correct
  `navigationRootUrl` URLs and are Phase 10's business. Deleting the links therefore removes them
  from the only place they render and takes nothing away from anyone.
  **Rejected:** rendering them conditionally when the viewed profile is the viewer's own. A
  `zope.schema` field description is a static class attribute evaluated at import time; making it
  vary per request needs a custom widget or a form override — real machinery for a link that has
  no correct audience on that form.
  — **Reversibility:** reversible — the removed markup is one string literal, recoverable from
  git history and still present in three `.po` catalogues.

- **D-15:** **The replacement description is the first sentence already there:**
  "Enable/disable the two-step verification." The "Click here … or here …" sentence goes. Any edit
  to the string produces a new msgid regardless of how small it is, so there is nothing to gain by
  preserving wording.

- **D-16:** **Do not hand-edit the `.po` / `.pot` catalogues in this phase.** The old msgid appears
  in `locales/imio.googleauthenticator.pot:75` and in the `fr`, `en` and `nl` catalogues, with a
  real French translation in `locales/fr/LC_MESSAGES/imio.googleauthenticator.po:76-77`. After
  D-15 those entries are orphaned and the new msgid falls back to the English literal, so **the
  field description on `@@user-information` reads in English for a French user until Phase 13
  rebuilds the catalogue.** That is a known, accepted consequence and a Phase 13 input, not a
  defect to patch here. Reason for not fixing it in place: Phase 13's roadmap note puts an edit
  inside a translated message off limits under the v1.0 threat model, and Phase 8 hit a
  trailing-whitespace hazard inside quoted strings doing exactly this.

- **D-17:** **The test asserts absence, not wording.** Assert the rendered description contains
  neither `@@setup-two-factor-authentication` nor `@@disable-two-factor-authentication`. An
  assertion on the exact replacement sentence would break on any later copy edit while proving
  nothing about the defect.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/ROADMAP.md` §"Phase 9: Mail Path and Profile-Page Correctness" — the goal, the four
  success criteria, and four phase notes. The notes on BUG-08's fix site and on UX-01 not undoing
  RECOV-03 are load-bearing and are restated as D-14 and the D-01..D-04 constraint
- `.planning/ROADMAP.md` §"Standing constraints for every v1.1 phase" — the six conditions any
  commit in this milestone has to satisfy (Python 2.7 / Plone 4.3, >90% branch coverage,
  `bin/code-analysis` exit 0, memberdata declarations, no state writes in the PAS plugin, no
  foreign resource mutation)
- `.planning/REQUIREMENTS.md` lines 70-93 — BUG-07, BUG-08, UX-01, UX-02 as written
- `.planning/REQUIREMENTS.md` §"Open questions" 4 and 5 — **both are now answered.** Question 4 by
  D-05 (UX-02 stays in Phase 9); question 5 by the roadmap and confirmed in D-14 (the schema field
  description). Questions 1, 2 and 3 remain open and belong to Phases 10 and 11
- `.planning/REQUIREMENTS.md` §"Future Requirements" — "Refuse a mismatched `userid` at the view",
  with the residual risk this phase deliberately does not close
- `.planning/STATE.md` §"Blockers/Concerns" — the BUG-07 entry, and the `flake8-isort` caveat that
  finding counts shift per diff so error **codes** are the signal, not per-file counts
- `.planning/PROJECT.md` — the coexistence constraint (no wholesale skin or resource-registry
  override) that D-06 stays inside, and the Lifespan constraint that caps what any fix here is
  worth
- `.planning/milestones/v1.0-phases/08-coverage-instrument-and-test-layers/08-CONTEXT.md` — the
  measured lint and coverage baselines and the non-vacuity-check convention D-13 inherits

### Source under change (read before editing)
- `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:106-134` — the `host.send`
  call, the `except SMTPRecipientsRefused` re-raise D-10 deletes, the `except ValueError` arm, and
  the shared `if reason is not None:` tail. Lines 98-105 carry the comment on why
  `charset='utf-8'` is not optional — leave it and its argument alone
- `src/imio/googleauthenticator/browser/forms/request_bar_code_reset.py:85` — the
  `bar_code_reset_token` write that precedes the send (D-12)
- `src/imio/googleauthenticator/userdataschema.py:76-83` — the field description D-14/D-15 edit
- `src/imio/googleauthenticator/userdataschema.py:21-42` — `CustomizedUserDataPanel`, whose
  `omit()` call and its comment are the evidence D-14 rests on
- `src/imio/googleauthenticator/browser/forms/recovery_codes.pt:23-26` — the link D-01..D-04 change
- `src/imio/googleauthenticator/browser/forms/user_setup.py:162-176` — the comment block stating
  why the success path must not redirect. Read before touching anything in this file
- `src/imio/googleauthenticator/browser/forms/user_setup.py:189-212` — `updateFields`, the
  site-local / non-site-local branch D-08 must stay inside
- `src/imio/googleauthenticator/helpers.py:330-348` — `get_token_description()`, the function D-08
  extends
- `src/imio/googleauthenticator/profiles/default/actions.xml:11,24,45` — the
  `globals_view/navigationRootUrl` precedent D-02 follows

### Tests
- `src/imio/googleauthenticator/tests/test_request_bar_code_reset.py:31-37` — the
  `MailBase._send` patch harness D-13 reuses, and the comment explaining why it patches `_send`
- `src/imio/googleauthenticator/tests/test_user_setup.py` — where the UX-01 and UX-02 assertions
  belong
- `src/imio/googleauthenticator/tests/test_adapter.py` — the existing guard on what may and may
  not be declared on `IEnhancedUserDataSchema`; BUG-08 changes that schema's text

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The mail-failure test harness already exists.** `test_request_bar_code_reset.py` patches
  `Products.MailHost.MailHost.MailBase._send` and captures what MailHost was handed. BUG-07's test
  needs a raising variant of that patch, not a new harness.
- **`get_or_create_secret()` is already called on the enrollment render path**, inside
  `get_token_description()`. UX-02 needs no new lookup and mints no second seed.
- **`globals_view/navigationRootUrl` is already the package's URL idiom**, used three times in
  `actions.xml`. UX-01 follows an existing convention rather than introducing one.
- **The shared `if reason is not None:` tail in `request_bar_code_reset.py`** is already the single
  place that reports failure on that form. BUG-07 routes a fourth failure into it rather than
  adding a fifth reporting path.

### Established Patterns
- **Non-vacuity checks are mandatory.** Every phase from 1 to 8 proved each new test goes red
  against unmodified source before trusting it, then restored the source byte-identical. Both new
  tests in this phase inherit that.
- **One test method per requirement, grouped by concern** — this repo's WR-03 precedent, chosen
  over the `plone-write-tests` skill's R5 in plan 07-01.
- **Fail-closed over convenient.** `_dont_swallow_my_exceptions = True` has been live since
  Phase 1. D-09 widens an `except` on a *mail send*, which reports a failure to the user; it must
  not be extended to swallow anything on an authentication path.
- **Deliberate deviations are commented in the source, not just in planning docs.** Three separate
  comment blocks in the files this phase touches (`user_setup.py:162-176`,
  `request_bar_code_reset.py:98-105` and `:115-125`, `userdataschema.py:31-42` and `:64-75`) exist
  to stop a later reader "tidying" them away. Anything this phase decides against an obvious
  reading gets the same treatment.

### Integration Points
- **`recovery_codes.pt` is the only exit from a successful enrollment** — the success response is
  deliberately not a redirect, so this template is where UX-01 has to act.
- **The `qr_code` field description is the single slot** through which anything appears beside the
  QR on the enrollment form. UX-02 goes through it (D-08).
- **`@@user-information` is the only form that renders the
  `enable_two_factor_authentication` description**, because `CustomizedUserDataPanel` omits the
  field from `@@personal-information`. That asymmetry is the whole of BUG-08.
- **Phase 12 attaches three new senders** to the `request_bar_code_reset.py` mail pattern. The
  failure handling D-09..D-11 establish is the shape those three will copy.

</code_context>

<specifics>
## Specific Ideas

- **The four items are independent and can be planned in any order or in parallel.** They share no
  file: BUG-07 is `request_bar_code_reset.py`, BUG-08 is `userdataschema.py`, UX-01 is
  `recovery_codes.pt`, UX-02 is `helpers.py`. The only sequencing that matters is the milestone's:
  BUG-07 lands before Phase 12.

- **BUG-08 has a counter-intuitive shape that should be stated plainly to whoever implements it.**
  The obvious reading — "an administrator sees links they should not, so hide them from
  administrators" — is wrong. The links are on the admin form *only*, and the user who ought to
  have them never sees them there. The fix is a deletion, and it makes no user worse off.

- **UX-02 is the requirement most at risk of being over-built.** It is one string emitted beside an
  image that already encodes the same value. The discussion rejected a reveal control, a second
  schema field, a custom template, and a second representation of the secret — all four for the
  same reason: the QR next to it already gives away everything the text does.

- **The "produces accepted codes" half of criterion 4 is not automatable in this suite.** A test
  can assert the base32 secret appears in the rendered description and matches
  `get_or_create_secret()` for that user; whether a real desktop TOTP client then produces an
  accepted code is a UAT step, not a unit test. Plan it as one.

</specifics>

<deferred>
## Deferred Ideas

- **Refusing a mismatched `userid` at `@@setup-two-factor-authentication` and
  `@@disable-two-factor-authentication`.** Already a Future Requirement in `REQUIREMENTS.md`. The
  operator chose on 2026-08-06 to hide the links only. Residual risk, unchanged by this phase: a
  bookmarked or hand-typed `@@disable-two-factor-authentication` URL still silently disables the
  clicker's own second factor and reports success. This will look tempting while editing
  `userdataschema.py` — it is out of scope.

- **Sweeping the orphaned msgids left by D-15** (`locales/imio.googleauthenticator.pot:75` and the
  `fr`, `en`, `nl` catalogues). Phase 13 owns catalogue rebuilds. See D-16.

- **`profiles/default/site_properties.xml`** — recorded dead in Phase 1, still dead, still tied to
  no requirement. Deferred again rather than riding along.

</deferred>

---

*Phase: 9-Mail Path and Profile-Page Correctness*
*Context gathered: 2026-08-06*
