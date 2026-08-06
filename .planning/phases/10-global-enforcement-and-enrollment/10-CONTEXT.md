# Phase 10: Global Enforcement and Enrollment - Context

**Gathered:** 2026-08-06
**Status:** Ready for planning
**Mode:** Autonomous smart discuss — proposals presented in batch tables, operator accepted or
overrode per area. Every decision below is either the operator's explicit choice or a direct,
stated consequence of one.

<domain>
## Phase Boundary

Make the `globally_enabled` setting mean what its own description says, and make sure every
account it catches can actually enrol instead of being locked out.

This is requirement MFA-14 from the previous milestone — the one requirement that shipped
unsatisfied — restated as five: MFA-15 through MFA-19.

The five things this phase must deliver:

1. **MFA-15** — an account that existed before this add-on was installed is asked for a second
   factor at its next login when `globally_enabled` is on.
2. **MFA-16** — with `globally_enabled` on, a user cannot turn their own second factor off.
3. **MFA-17** — with `globally_enabled` off, a user can enrol themselves from their own profile.
4. **MFA-18** — the enrollment flow is reachable whenever the package is installed, whatever the
   global setting says.
5. **MFA-19** — a user who was enrolled by the global setting rather than by their own action is
   shown the enrollment page (QR code and secret) before being asked for a code, instead of being
   asked for a code from an application they never set up.

**MFA-19 ships with MFA-15, not after it.** Shipping MFA-15 alone is a site-wide lockout the first
time an administrator installs onto a populated site. Success criteria 1 and 2 are one deliverable.

**Not this phase:**
- Any password re-authentication gate in front of MFA changes. That is Phase 11 (SEC-09..SEC-12),
  and open questions 1 and 2 in `REQUIREMENTS.md` belong to it.
- Any notification email about an MFA change. That is Phase 12.
- Any catalogue rebuild or translation work. That is Phase 13.
- Relaxing the failed-attempt lockout shipped in the previous milestone (MFA-08..MFA-13). It is
  unchanged and still applies to second-factor checks at login. Recorded as Out of Scope in
  `REQUIREMENTS.md` and reaffirmed by the roadmap note dated 2026-08-06: "enrollment is never
  blocked unless the package is uninstalled" is about **enrollment only**.
- Building a *new* site-wide un-enroll action. `REQUIREMENTS.md` records leaving that alone as
  defensible under MFA-17. **Correction, found by research after this section was first written:**
  an existing site-wide un-enroll view is live, not commented out — see D-14 below. What is
  commented out is a block in `browser/controlpanel.py`, not the standalone view.

</domain>

<decisions>
## Implementation Decisions

### Where global enforcement is checked — *operator chose the alternative, not the recommendation*

- **D-01:** **Enrol existing accounts at install time, in `setuphandlers.setupVarious`.** The
  operator was offered three approaches (this one; making the login check consult the global
  setting; and documenting a manual post-install step) and chose this one over the recommended
  login-check approach.

  What this buys: the login check and the PAS plugin boundary settled in the previous milestone's
  Phase 4 are not touched at all. It mirrors what saving the settings control panel already does
  (`browser/controlpanel.py:handleSave`), so there is one enrollment mechanism, not two.

  What it costs, recorded so nobody rediscovers it as a surprise: it writes member data for every
  existing account during an install, and it only catches accounts that exist at that moment.
  Accounts created later are covered by the existing `userdataschema.userCreatedHandler`, and an
  administrator turning the setting on later is covered by the existing control-panel save handler
  — so the three paths together cover the realistic cases, but there is no single place that
  enforces the rule.

  **Rejected: making the login check derive enforcement** as `globally_enabled or the user's own
  flag`. It would have covered accounts created by any route and written nothing, but it changes
  behaviour at the PAS boundary. **Also rejected: a documented manual post-install step** — it
  makes a security control depend on a person remembering.

- **D-02:** **Install sets the enable flag and creates NO seed.** This is a direct consequence of
  D-01 combined with the operator's Area 2 choice, which established that a seed is created when
  the enrollment page renders the QR code, not before. Stated explicitly and confirmed with the
  operator before planning.

  Two things this avoids:
  - **No new member-data property is needed.** If install created seeds, every account would have
    a seed nobody had seen, and "has no seed" would stop working as the signal for who must be
    shown the enrollment page — forcing a new property to mark "enrolled by the system, never saw
    the QR". Any such property would need a `profiles/default/memberdata_properties.xml` entry and
    a set/get round-trip test, because `MutablePropertySheet.setProperties` silently discards
    undeclared keys with no error.
  - **No encryption key is needed at install.** Setting a boolean flag needs no key. The existing
    bulk-enrollment helper `enable_two_factor_authentication_for_users` calls
    `get_or_create_secret`, which raises `ValueError` when `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` is
    unset — so reusing it as-is at install would make installation fail on any site without the key
    configured. D-02 sidesteps that entirely.

- **D-03:** **The login check keeps reading only the user's own flag.** `pas_plugin.py:197-202`
  reads `enable_two_factor_authentication` and is not changed to consult the global setting. Under
  D-01 the flag is already set for everyone who should present a second factor.

- **D-04:** **Install-time enrollment must not partially enrol without saying so.** The existing
  helper `enable_two_factor_authentication_for_users` (`helpers.py`) re-raises `ValueError` but
  swallows every other per-user exception with `logger.debug(str(e))`. At install that would mean
  some accounts enrolled and some not, with nothing visible to the operator. Whatever this phase
  uses at install must either enrol everyone or report plainly that it did not.

### How a caught user reaches enrollment (MFA-19) — *operator accepted, with one correction*

- **D-05:** **A user whose flag is set but who has not completed enrollment is sent to the
  enrollment page, not the code-entry page.** The routing decision is made in the login path before
  any URL is signed.

- **D-06:** **The invariant the plan must satisfy: a user is never sent to the code-entry page
  unless they have actually completed enrollment.** The mechanism is deliberately left to research
  and planning, because verifying the code turned up a constraint that rules out the obvious
  approach — see the note below. Two mechanisms are acceptable; pick one with reasons:

  - **(a)** Do not create the seed when signing an enrollment redirect — requires solving the
    signing-key problem in the note below.
  - **(b)** Track completed enrollment in a new member-data property. If chosen, it **must** have a
    `profiles/default/memberdata_properties.xml` entry and a set/get round-trip test.

  **The constraint that forces this choice, verified in the source:** `sign_user_data`
  (`helpers.py:857-886`) calls `get_or_create_secret(user)` unconditionally at line 878, and it has
  to — the user's seed is one of the three inputs to the signing key built by `get_ska_secret_key`,
  alongside the global `ska_secret_key` registry record and a hash of the User-Agent. You cannot
  sign a URL for a user whose seed does not exist yet.

  In the normal flow this is harmless: the login check decides "send to enrollment" *before*
  signing, then signing creates the seed, then the enrollment page renders the QR for that same
  seed — all in one request chain, so the seed is never unseen for any meaningful period. **The
  residual hazard is a user who abandons enrollment after that redirect.** They now hold a seed, so
  "has no seed" is false, and at their next login they would be sent to the code-entry page for an
  application they never set up. That is the lockout MFA-19 exists to prevent, reached by a
  different route.

- **D-07:** **A missing or broken seed encryption key on this path must produce a clean refusal,
  not an error page.** `.planning/STATE.md` records this from the previous milestone's review
  (04-REVIEW.md WR-01/WR-02): for a user with the flag set but no stored seed, a missing
  `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` raises inside `send_2fa_redirect` rather than synchronously
  in `authenticateCredentials`, giving an uncontrolled error page. It is still fail-closed and
  there is no bypass, but this phase creates exactly that account state, so it moves onto the
  critical path here.

### Refusing self-disable, and the profile menu links — *operator accepted both*

- **D-08:** **The refusal lives in the disable view itself.**
  `browser/disable_two_factor_authentication.py` currently clears the flag, the seed and the reset
  token for whoever calls it, with no condition at all. It must refuse when `globally_enabled` is
  on. This is the actual security control.

- **D-09:** **The disable menu link is hidden as well, but hiding it is not the control.** Phase 9
  just dealt with the mirror of this problem (BUG-08): a link that acts on the wrong account cannot
  be fixed by hiding it, because a bookmarked or hand-typed URL still works. Same reasoning here —
  hide the link for tidiness, refuse in the view for safety.

- **D-10:** **The enable link is offered whenever the user is not enrolled, whatever the global
  setting says.** This is MFA-17 and MFA-18 together.
  `settings_helper.show_enable_two_factor_authentication_link` currently requires
  `is_two_factor_authentication_globally_enabled()` to be **True** before offering the enable link
  — which is backwards for self-enrollment when the setting is off, and its own docstring at
  `settings_helper.py:32` says the condition should be False. The code and its documentation
  already disagree; this phase settles it in favour of the docstring's intent, generalised: offer
  the link based on whether the user is enrolled, not on the global setting.

- **D-11:** **`show_disable_two_factor_authentication_link` gets the mirror treatment:** offered
  only when the user is enrolled **and** the global setting is off. It currently requires the
  global setting to be True, which is exactly the case where MFA-16 says disabling must be refused.

### Added after research — findings the first pass did not anticipate

- **D-14:** **A live, ungated site-wide un-enroll view exists.**
  `browser/disable_two_factor_authentication_for_all_users.py` is 31 lines, fully live, and clears
  the enable flag, seed and reset token for **every** account with no check on `globally_enabled`
  at all. An earlier draft of this document said this path was commented out; that was wrong, and
  the wrong sentence has been corrected in the Deferred section. Whether this phase gates that view
  is an operator scope decision — recorded here so it is not mistaken for nonexistent by anyone
  reading only the requirements.

- **D-15:** **The "Regenerate recovery codes" portal action must not lose its visibility when
  global enforcement is on.** `profiles/default/actions.xml:41-52` gives
  `regenerate_recovery_codes` the `available_expr`
  `portal/@@show-disable-two-factor-authentication-link` — deliberately reusing the disable link's
  condition, with a comment at lines 33-39 saying why ("rather than adding a fourth SettingsHelper
  method for the same boolean"). D-11 changes that condition to require the global setting to be
  **off**, which would hide "Regenerate recovery codes" from exactly the users under global
  enforcement. That is a regression this phase must not ship. The action needs its own condition:
  visible when the user is enrolled, independent of the global setting. The comment in
  `actions.xml` explaining the old reuse must be updated at the same time, not left contradicting
  the new code.

- **D-18:** **The site-wide un-enroll view is gated in this phase too — operator decision,
  2026-08-06.** `browser/disable_two_factor_authentication_for_all_users.py` gets the same
  `globally_enabled` refusal that D-08 adds to the single-user view. Reason the operator was given
  and accepted: shipping a refusal that stops one user turning their own second factor off, while
  leaving a one-click "disable for everyone" reachable, makes the enforcement incoherent. It is a
  small change to a 31-line view and it reuses the refusal that D-08 is already writing.
  This slightly widens the phase beyond MFA-16 as literally worded (which speaks only of a user's
  own second factor). Recorded as a deliberate widening, not scope creep, so the verifier does not
  read it as unplanned work. Rejected: leaving it and recording a Future Requirement; and deleting
  the view outright, which has a larger blast radius across ZCML, actions, and any control-panel
  link.

- **D-16:** **The enrollment page is not reachable by a user whose session cookie was just
  cleared, and that must be fixed for MFA-19 to work at all.** Research found that
  `@@setup-two-factor-authentication` (`SetupForm`) has no way to identify a user from a signed
  URL: it returns 401 and hides the QR code for any anonymous request. The login path clears the
  `__ac` cookie before redirecting, so a user sent there by D-05 arrives anonymous and sees
  nothing. `browser/forms/token.py` already solves this exact problem for the code-entry page,
  using an `auth_user` request parameter, `validate_user_data`, and `_setupSession`. The enrollment
  target needs the same treatment. Without it, MFA-19 still locks people out — just by a different
  route than the one D-06 was worried about.
  Whether that means extending `SetupForm` or adding a separate view is at the implementer's
  discretion; research flagged a blast-radius risk against `tests/test_user_setup.py` for the
  extend-in-place option.

- **D-17:** **D-06 is settled in favour of mechanism (b): a new member-data property recording
  that enrollment was completed.** Research rejected mechanism (a) — signing an enrollment URL for
  a user with no seed — because the user's seed supplies the per-user entropy in the signing key,
  and removing it collapses that key to a browser hash plus a site-wide secret shared across every
  unenrolled user. Bounding that risk would mean auditing the internals of the pinned `ska 1.7.5`
  library, which is out of proportion to declaring one property.
  The property follows the precedent already used for the lockout and replay counters: declared in
  `profiles/default/memberdata_properties.xml`, **not** exposed on the user-facing schema or the
  adapter. It needs a set/get round-trip test, because `MutablePropertySheet.setProperties`
  silently discards undeclared keys with no error.

### Claude's Discretion

Areas not discussed. Decisions recorded here so downstream agents do not reopen them.

- **D-12:** **The wording of the refusal a user sees when they try to disable while the global
  setting is on** is at the implementer's discretion, subject to two constraints: it is a new
  translatable message id (a Phase 13 input, like every other string this milestone adds), and it
  must not state or imply anything about other accounts.

- **D-13:** **Whether install-time enrollment runs inside `setupVarious` directly or in a helper it
  calls** is at the implementer's discretion. What is not discretionary: it is gated on the
  `imio.googleauthenticator.marker.txt` data file like the rest of `setupVarious`, so re-running
  another add-on's install does not trigger it, and it is idempotent — installing twice must not
  change anything the first install already did.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/ROADMAP.md` §"Phase 10: Global Enforcement and Enrollment" — the goal, the five
  success criteria, and six phase notes. The notes on MFA-19 shipping with MFA-15, on the MFA-17
  condition inversion, and on member-data declaration are load-bearing and are restated above as
  D-02, D-10 and D-06.
- `.planning/ROADMAP.md` §"Standing constraints for every v1.1 phase" — the six conditions any
  commit in this milestone must satisfy: Python 2.7 / Plone 4.3, branch coverage above 90%,
  `bin/code-analysis` exit 0, member-data declarations, no MFA state written from the PAS plugin,
  and no mutation of a resource this package does not own.
- `.planning/REQUIREMENTS.md` lines 22-39 — MFA-15 through MFA-19 as written, plus the paragraph
  headed "Why MFA-19 is here".
- `.planning/REQUIREMENTS.md` §"Open questions" 3 — **now answered** by D-01. Questions 1 and 2
  belong to Phase 11. Questions 4 and 5 were answered in Phase 9.
- `.planning/REQUIREMENTS.md` §"Out of Scope" — the failed-attempt lockout is not relaxed.
- `.planning/STATE.md` §"Blockers/Concerns" — three entries name Phase 10 directly. Read all three;
  D-07 restates one of them.
- `.planning/milestones/v1.0-phases/07-coexistence-with-imio-dms-mail/07-UAT.md` lines 95-136 — the
  original finding, the confirmed mechanism, and the three candidate approaches D-01 chose between.
- `.planning/PROJECT.md` — the constraint that MFA state writes go in a committing view and never
  in the PAS plugin, and why: any request ending in an exception discards its writes, and
  `Unauthorized` is re-raised on the login path.

### Source under change (read before editing)
- `src/imio/googleauthenticator/setuphandlers.py:81-98` — `setupVarious`, the marker-file gate, and
  the two things it does today (`_setup_secret_key`, `_add_plugin`). D-01 adds to this.
- `src/imio/googleauthenticator/browser/disable_two_factor_authentication.py` — the whole file is
  40 lines. It clears the flag, seed and reset token unconditionally. D-08 adds the refusal.
- `src/imio/googleauthenticator/browser/settings_helper.py:25-63` — both link conditions, and the
  docstrings that already contradict the code. D-10 and D-11 change these.
- `src/imio/googleauthenticator/pas_plugin.py:166-260` — `authenticateCredentials`. D-03 says the
  flag read at lines 197-202 is unchanged; D-05 changes where a user is sent afterwards.
- `src/imio/googleauthenticator/pas_plugin.py:77-130` — `send_2fa_redirect`, the shared redirect
  builder. D-07's hazard lives here.
- `src/imio/googleauthenticator/helpers.py:857-886` — `sign_user_data`, and the
  `get_or_create_secret(user)` call at line 878 that D-06's note is about.
- `src/imio/googleauthenticator/helpers.py:306-328` — `get_or_create_secret`, which writes a seed
  via `generate_secret` when none exists.
- `src/imio/googleauthenticator/helpers.py:1031-1052` — `enable_two_factor_authentication_for_users`,
  the existing bulk-enrollment helper, including the `except ValueError: raise` comment explaining
  why a key failure is total rather than per-user, and the `except Exception: logger.debug` arm
  that D-04 is about.
- `src/imio/googleauthenticator/browser/controlpanel.py:114-145` — `handleSave`, the existing
  enrollment mechanism D-01 mirrors, including how it reports a seed-encryption failure to the
  operator rather than claiming success.
- `src/imio/googleauthenticator/userdataschema.py` — `userCreatedHandler`, the third enrollment
  path, which already consults the global setting.
- `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` — required reading if
  and only if D-06 mechanism (b) is chosen.

### Tests
- `src/imio/googleauthenticator/tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin`
  — a source-level guard that no MFA state is written from the PAS plugin. The roadmap says it
  **must be extended, not worked around**.
- `src/imio/googleauthenticator/tests/test_setuphandlers.py` — where D-01's install behaviour is
  tested, including the idempotency requirement in D-13.
- `src/imio/googleauthenticator/tests/test_settings_helper.py` — if present; otherwise the link
  conditions need new coverage for D-10 and D-11.
- `src/imio/googleauthenticator/tests/test_controlpanel.py` — the existing bulk-enrollment tests,
  which show the established shape for testing enrollment over a set of users.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Three enrollment paths already exist**, and D-01 adds a fourth that mirrors the first:
  the control panel save handler (`controlpanel.py:handleSave`), the user-creation handler
  (`userdataschema.userCreatedHandler`), and the per-user setup form. Install-time enrollment
  should look like the control-panel one, not invent a shape.
- **`enable_two_factor_authentication_for_users` already iterates users and sets the flag** — but
  it also calls `get_or_create_secret`, which D-02 does not want at install. Either it grows a
  parameter or install uses a narrower helper; that is an implementation choice, but the existing
  function's error handling (D-04) is the part to be careful with.
- **The marker-file gate in `setupVarious`** is the established way to make install work run only
  for this add-on and not when another product is installed.
- **`browser/controlpanel.py:handleSave` already models how to report a seed-encryption failure**
  to an operator instead of silently claiming success. D-04 needs the same honesty at install.

### Established Patterns
- **Non-vacuity checks are mandatory.** Every phase from 1 to 9 proved each new test goes red
  against unmodified source before trusting it, then restored the source byte-identical.
- **One test method per requirement, grouped by concern** — this repo's precedent, chosen over the
  `plone-write-tests` skill's rule in plan 07-01 and reaffirmed in Phase 9.
- **Deliberate deviations are commented in the source, not only in planning documents.** Several
  comment blocks in the files this phase touches exist to stop a later reader tidying them away.
  Anything this phase decides against an obvious reading gets the same treatment.
- **Hiding an affordance is not a control.** Established one phase ago by BUG-08 and restated here
  as D-09.

### Integration Points
- **`setupVarious` runs inside the install transaction.** The project constraints note that
  QuickInstaller snapshots `portal_setup` before and after every install, so anything added there
  is visible to that snapshot and must not be half-done.
- **The login path is the only place that decides where a user goes after their password is
  accepted.** D-05's routing choice has to live there, and it must not write state (D-03, and the
  guard test).
- **`settings_helper` drives the portal actions in `profiles/default/actions.xml`**, which is the
  route an ordinary user takes to enrollment — as distinct from the schema field description that
  Phase 9 emptied, which only ever rendered on the administrator's view of another user.

</code_context>

<specifics>
## Specific Ideas

- **The operator overrode the recommendation on the biggest decision.** D-01 chose install-time
  enrollment over making the login check consult the global setting. Do not re-litigate it during
  planning or execution. The trade-off is recorded in D-01 in full, including what it costs.

- **MFA-15 and MFA-19 are one deliverable, not two.** Enrolling existing accounts without also
  routing them to enrollment is a site-wide lockout on the first install onto a populated site.
  If the phase has to be split across plans, these two do not go in different waves in a way that
  could ship one without the other.

- **The `settings_helper` conditions are inverted today, and the docstrings say so.** The code
  requires the global setting to be True where the docstring says False. This is not a subtle
  judgement call — the file already documents the intended behaviour and does the opposite.

- **D-06 is the one place this phase's design is deliberately left open.** Both acceptable
  mechanisms are named with their consequences. Research should settle it and say why. It should
  not be discovered mid-execution.

- **Criterion 5 is a statement about combinations, not a single check.** "No combination of
  settings leaves a user unable to enrol" needs the global setting on and off, crossed with the
  user enrolled and not enrolled — four cases, and the enrollment path must be reachable in all of
  them. Plan it as a matrix, not as one test.

</specifics>

<deferred>
## Deferred Ideas

- **Making the login check consult the global setting directly.** Rejected as D-01's alternative,
  not because it is wrong — it is arguably more robust — but because the operator chose the
  smaller behavioural change. If a future account-creation route is ever found that bypasses both
  `userCreatedHandler` and install, this is the fix to revisit.

- **A site-wide un-enroll action.** The disable-for-all-users path in `browser/controlpanel.py` is
  commented out and only logs. `REQUIREMENTS.md` records leaving it that way as defensible, to be
  revisited only if an operator actually needs it.

- **Refusing a mismatched `userid` at `@@setup-two-factor-authentication` and
  `@@disable-two-factor-authentication`.** Still a Future Requirement in `REQUIREMENTS.md`, carried
  over from Phase 9. This phase adds a condition to the disable view (D-08) and will make that view
  look editable again — the `userid` refusal is still out of scope.

- **`profiles/default/site_properties.xml`** — recorded dead in Phase 1, still dead, still tied to
  no requirement. Deferred again rather than riding along.

</deferred>

---

*Phase: 10-Global Enforcement and Enrollment*
*Context gathered: 2026-08-06*
