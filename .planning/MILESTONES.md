# Milestones

## v1.0 Hardened MFA (Shipped: 2026-08-06)

**Delivered:** a forked, undeployable Plone 4.3 two-factor plugin turned into
`imio.googleauthenticator` — seeds encrypted at rest, the second factor unbypassable through
any credentials extractor, brute force stopped by a lockout counter that survives a ZEO
client restart, recovery codes for the lost-phone case, and no resource collision with
`imio.dms.mail`.

**Closeout type:** override_closeout — one requirement (MFA-14) shipped unsatisfied. See Known
Gaps below.

### Stats

| Measure | Value |
|---|---|
| Phases | 8, all with a `*-VERIFICATION.md` reading `status: passed` |
| Plans | 30 |
| Tasks | 69 |
| Quick tasks | 3 (`260805-f5m`, `260806-fsp`, `260806-gfr`) |
| Requirements | 72 of 73 satisfied |
| Test suite at close | 135 tests, 0 failures, 0 errors (`bin/test -t '!robot'`, exit 0) |
| Branch coverage | 90%, enforced in CI |
| Source diff | 105 files, +10,994 / −1,991 lines under `src/`, `setup.py`, buildout configs |
| Python in `src/` | 9,760 lines |
| Phase dates | 2026-07-29 → 2026-08-06 |
| Final commit | `3cfa7fb` |

### Key accomplishments

1. **Renamed the package and stopped it swallowing its own exceptions.** Moved
   `src/collective/` to `src/imio/googleauthenticator/` and renamed every dotted reference,
   GenericSetup identity, i18n domain and resource id. Set
   `_dont_swallow_my_exceptions = True` on the PAS plugin, which turns a plugin crash from a
   silent password-only login into a 500. That flag immediately surfaced two pre-existing
   bugs — a crash on an empty `REMOTE_ADDR` and a broken debug-log property lookup — that had
   been disabling the entire two-factor gate with no error page and no log line.

2. **Encrypted the TOTP seeds at rest and stopped sending them to Google.** Seeds are stored
   Fernet-encrypted (`v1$<token>`) under a key read from the environment, never from the
   ZODB. Enrollment, login, bulk-enable and user-creation all fail closed when the key is
   missing or unusable. QR codes render in-process through `qrcode` instead of being fetched
   from `chart.googleapis.com`, so the seed never leaves the server.

3. **Moved the two-factor redirect out of the PAS plugin and closed the extractor bypass.**
   The redirect now runs in an `IPubBeforeCommit` subscriber and an `IChallengePlugin`,
   not inside `authenticateCredentials`. Every credentials extractor has a test asserting it
   cannot authenticate past the second factor. Fixed the body-leak bug where `setBody('')`
   was a no-op.

4. **Added a lockout counter, replay rejection and clock-drift tolerance that actually
   persist.** Failure counts and lock expiry live in declared memberdata properties, so they
   stay consistent across ZEO clients. All five state writes happen only inside a committing
   view, pinned by a source-grep regression test — a write in the PAS plugin would be
   discarded by `transaction.abort()` and the lock would silently never lock.

5. **Added recovery codes on the same throttled path.** Ten 80-bit base32 codes per user,
   PBKDF2-HMAC-SHA256 hashed under a per-user salt, displayed once at enrollment, consumed on
   use, and routed through the same lockout counter as TOTP attempts so they are not an
   unthrottled way in.

6. **Removed everything that collided with `imio.dms.mail`.** Deleted 507 lines of vendored
   JavaScript and skin templates, deleted the `portal_skins` layer entirely, and added an
   invariant test that fails the day this package names a resource id it does not own. Closed
   an open redirect and a query-string injection in the `next_url` pipe along the way.

7. **Made the build tell the truth.** Test classes moved off the leaking `IntegrationTesting`
   layer, `.coveragerc` scope corrected, branch coverage raised from 84% to 90% with real
   asserting tests, and CI's `test_command` pointed at `bin/test-coverage` so the 90%
   threshold gates every push. All 500 `bin/code-analysis` findings cleared, so the
   pre-commit hook passes without `--no-verify`.

### Known Gaps

One v1 requirement shipped unsatisfied. It is carried into v1.1 as requested item 3 in
`.planning/MILESTONE-CONTEXT.md`.

- **MFA-14 — turning on `globally_enabled` does not enroll accounts that already existed when
  the add-on is installed.** `is_two_factor_authentication_globally_enabled` is consulted only
  by the user-created event handler and by the code deciding which menu links to show. The
  login gate reads each user's own `enable_two_factor_authentication` memberdata flag and
  never the global setting. Existing users are enrolled only when an administrator saves the
  settings control panel form; `setuphandlers.setupVarious` enrolls nobody. Consequence:
  installing this add-on into an existing `imio.dms.mail` site — the real deployment
  direction — leaves every existing account without a second factor, while the setting's own
  description says it "globally enables the two-step verification for all users" and defaults
  to True. Confirmed by the operator on a real two-egg environment on 2026-08-05: installing
  `imio.dms.mail` first left a Member unenrolled; the reverse order enrolled them.

### Known verification overrides

- No `07-SECURITY.md` was produced for Phase 7. Every other phase has one and the security
  step hook was active, so this is a missing artifact rather than a recorded skip.
- Six verification claims in Phase 5 are marked "backstop" and cannot be proven by an
  in-process test: real ZEO multi-client counter consistency, the control panel's live
  edit-and-persist round trip, real mobile-app clock drift acceptance, and byte-for-byte
  response equality behind a real front-end proxy at two endpoints.
- Under Nyquist validation, phases 1 through 4 are recorded compliant and phases 5 through 8
  are recorded not-validated.

### Blocking deployment dependency (outside this repository)

The Puppet `concat::fragment` that supplies `IMIO_GOOGLEAUTHENTICATOR_SEED_KEY` to each ZEO
client lives in the separate `industrialisation` repository and has **not shipped**. The
package is code-complete and its suite is green, but a production instance started without
that variable cannot decrypt or mint seeds. `base.cfg:54` sets the variable in the `[testenv]`
section only, which reaches `bin/test` and `bin/test-coverage`; the `[instance]` section sets
it nowhere.

### Other technical debt carried forward

Recorded in full in `.planning/milestones/v1.0-MILESTONE-AUDIT.md` under `tech_debt`. The
items most likely to bite:

- A rejected recipient address crashes the bar-code reset email path with a 500 instead of an
  in-page message: `browser/forms/request_bar_code_reset.py:112-113` re-raises
  `SMTPRecipientsRefused` outside the enclosing `except ValueError`. Pre-existing, confirmed
  by `git blame`.
- Bulk enrollment through the control panel mints a seed for every user but shows nobody a QR
  code, so their next login demands a code from an app they never enrolled.
- Turning `globally_enabled` off enrolls nobody out — the disable call in
  `browser/controlpanel.py` is commented out and only writes a debug log line.
- A username-enumeration oracle remains at `browser/forms/request_bar_code_reset.py`, accepted
  as low severity during Phase 3's security review.
- No iMio operations owner has confirmed that nothing authenticates against this site's
  `acl_users` over HTTP Basic Auth. The decision to leave `credentials_basic_auth` active
  rests on a three-repository grep that Phase 4's research records as non-exhaustive.
  `README.rst` tells the deploying operator to perform this check.
- `CLAUDE.md` states the GenericSetup profile version is `0301` matching package version
  `0.3.0`. The actual values are `1000` in `profiles/default/metadata.xml` and `1.0.0.dev0`
  in `setup.py`.

### Archived artifacts

- `.planning/milestones/v1.0-ROADMAP.md`
- `.planning/milestones/v1.0-REQUIREMENTS.md`
- `.planning/milestones/v1.0-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.0-phases/` — all 8 phase directories

---
