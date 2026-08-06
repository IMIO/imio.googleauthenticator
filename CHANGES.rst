Changelog
=========

1.0.0 (unreleased)
------------------

- Renamed the package from ``collective.googleauthenticator``.
  [chris-adam]
- Existing databases are discarded, not migrated: the PAS plugin, the
  ``IUserDataSchemaProvider`` utility, the browser layer and the registry records
  all pickle the old module path and unpickle as ``OFS.Uninstalled.Broken``.
  Recreate the Plone site and re-enrol users.
  [chris-adam]
- Previously-issued signed token URLs keep validating: the rename changes none
  of the three inputs to the ``ska`` signing key.
  [chris-adam]
- The ``imio.googleauthenticator`` GenericSetup import step now declares
  ``<depends name="plone.app.registry"/>``, so the registry records it needs
  are seeded deterministically instead of by CPython 2.7 string-hash chance.
  [chris-adam]
- ``ska_secret_key`` is seeded once at install time, without the nested
  ``runImportStepFromProfile`` re-entry the ``<depends>`` declaration above
  makes unnecessary. ``get_ska_secret_key()`` is a pure read and raises if the
  key is missing: minting inside it would write registry state from the PAS
  ``authenticateCredentials()`` path, which ends in ``transaction.abort()`` on
  ``Unauthorized`` and would discard the key after a URL signed with it had
  already been sent to the browser.
  [chris-adam]
- The ``ska`` signing key derivation now length-prefixes its three
  components instead of bare-concatenating them, so two different
  component boundaries can no longer collide on the same key. This
  invalidates any previously issued signed URL -- harmless before any site
  is deployed and any user is enrolled, which is why it ships now.
  [chris-adam]
- TOTP seeds are now Fernet-encrypted at rest, stored as ``v1$<token>``;
  new seeds are 160 bits of ``os.urandom``. **Existing plaintext seeds are
  not migrated**: they carry no ``v1$`` prefix, are refused on read, and
  those users must re-enrol.
  [chris-adam]
- Enrollment and login now fail closed on a missing or invalid encryption
  key: refused outright, never silently downgraded to a plaintext seed and
  never to password-only login.
  [chris-adam]
- New required environment variable ``IMIO_GOOGLEAUTHENTICATOR_SEED_KEY``,
  one per Zope process (per ZEO client, not per database) -- see
  ``README.rst``'s "Seed encryption key (required)" section. A missing key
  logs a ``CRITICAL`` line at process start instead of failing silently at
  first login.
  [chris-adam]
- The enrollment QR code now renders in-process: no request reaches an
  external chart service and the seed appears in no subprocess argv.
  [chris-adam]
- Dependency changes: ``cryptography == 3.3.2``, ``qrcode == 6.1`` and
  ``ipaddress == 1.0.23`` added; the previous base32 encoder and the other
  ``ipaddress`` distribution removed. The ``ipaddress`` swap is mandatory,
  not cosmetic: both distributions install a top-level module of the same
  name, and which one wins is decided by egg ordering, so the previous
  arrangement worked on a dev box and could break every login on a
  differently built host.
  [chris-adam]
- The bar-code reset token comparison is now constant-time; an empty or
  absent stored token no longer matches an empty submitted value.
  [chris-adam]
- A regression test now covers the ``user_setup.py`` redirect invariant.
  The ``UnboundLocalError`` described in earlier notes does not reproduce
  on the current source, so this is a guard rather than a fix.
  [chris-adam]
- Two-step verification setup and bar-code reset now refuse an account that is
  not defined in the Plone site itself, instead of reporting success for a
  second factor that will never be demanded. This plugin lives in the site's
  ``acl_users``, so a Zope-root account (typically the buildout ``inituser``
  ``admin``) is authenticated above the site and its login cannot be
  intercepted; enrolling it previously wrote the flag, stored a seed and said
  "successfully enabled". Root logins remain ungated by design — the package
  targets in-site users — but they are no longer told otherwise.
  [chris-adam]
- Submitting a token for a user with no stored seed is now refused instead of
  raising ``TypeError('Incorrect secret')`` out of ``onetimepass`` as an
  unhandled 500. ``get_secret`` returns ``None`` implicitly for such a user,
  and ``validate_token`` passed it straight through. Guarded in
  ``validate_token``, which all three callers route through, and deliberately
  narrow: an undecryptable stored seed still raises, since answering "wrong
  token" to a broken-key condition would downgrade a fail-closed refusal.
  [chris-adam]
- The bar-code reset email no longer fails on a non-ASCII character. The
  ``MailHost.send()`` call passed no ``charset``, so ``_mungeHeaders``
  ASCII-encoded the unicode body and a single accented byte -- from the
  site's ``email_from_name`` or the translated Subject line -- raised
  ``UnicodeEncodeError``. Because that subclasses ``ValueError`` the handler
  swallowed it and reported only "An unexpected error occurred.", leaving a
  locked-out user with no working recovery path.
  [chris-adam]
- A refused login no longer serves the protected page in its response body.
  Previously a 2FA-gated request returned a 302 whose body still contained
  the rendered page, readable by any client that does not follow redirects.
  [chris-adam]
- The 2FA redirect moved out of the PAS plugin's ``authenticateCredentials``
  into an ``IPubBeforeCommit`` subscriber and an ``IChallengePlugin``, so it
  now fires on both the login-form POST (which returns HTTP 200 and never
  raises) and on requests that end in ``Unauthorized``. The plugin itself no
  longer touches the response or performs the redirect.
  [chris-adam]
- Plugin ordering is now set explicitly with ``movePluginsTop`` and
  re-asserted every time the ``imio.googleauthenticator:default`` profile is
  applied, not only on first install. Re-applying the profile now restores
  the ordering if another add-on has displaced the plugin.
  [chris-adam]
- The shared-credentials wipe now runs before delegating to the other
  authentication plugins, so an exception raised mid-login still refuses
  the login rather than leaving intact credentials for a later plugin to
  authenticate on.
  [chris-adam]
- Reviewed whether to deactivate the ``credentials_basic_auth`` extractor as
  defence in depth, and decided to keep it active: see ``README.rst``'s new
  "HTTP Basic Auth, WebDAV, FTP and XML-RPC" section for the decision, the
  evidence behind it and its known gap.
  [chris-adam]
- ``README.rst`` now documents the Zope-root/emergency-user limitation and
  the Basic Auth / WebDAV / FTP / XML-RPC consequence of the above decision,
  including the supported service-account-plus-IP-whitelist alternative for
  scripts and API consumers.
  [chris-adam]
- TOTP validation now accepts the immediately preceding 30-second interval
  as well as the current one, and refuses a code whose interval has
  already been accepted -- a replay of a code already used to log in no
  longer succeeds. The accepted interval is recorded per user.
  [chris-adam]
- Only exactly six ASCII digits are now treated as a candidate token; every
  other shape (too short, too long, non-digit, a non-ASCII digit) is
  refused before the stored seed is ever fetched or decrypted.
  [chris-adam]
- Five consecutive failed second-factor attempts now lock an account for
  900 seconds, evaluated before the submitted code is checked at all, on
  both ``@@google-authenticator-token`` and ``@@reset-bar-code``. The lock
  releases itself once its stored epoch passes -- no administrator action
  is needed -- and a successful second factor clears the counter.
  [chris-adam]
- The attempt limit (``max_failed_attempts``) and the lock duration
  (``lockout_duration``) are new control-panel settings, defaulting to 5
  and 900 seconds.
  [chris-adam]
- **Upgrade note:** this release adds two ``plone.registry`` records
  (``max_failed_attempts``, ``lockout_duration``) and three
  ``portal_memberdata`` properties (the failed-attempts counter, the lock
  epoch, and the last-accepted TOTP interval). It ships **no** GenericSetup
  upgrade step -- consistent with this same section's existing note that
  deployers recreate the Plone site rather than migrate it. The
  ``imio.googleauthenticator:default`` profile must be (re-)imported for
  these records and properties to exist. The failure mode on a site that
  is not reimported is loud, not silent:
  ``registry.forInterface(IGoogleAuthenticatorSettings)`` raises on the two
  missing records, and ``getProperty(...)`` on an undeclared memberdata
  property raises ``ValueError`` rather than returning a falsy default --
  so a lockout that never locks is not among the possible outcomes.
  [chris-adam]
- Both JavaScript registrations in ``profiles/default/jsregistry.xml`` now pin
  their position with ``insert-bottom``. ``BaseRegistry.storeResource`` appends,
  so without a position directive the load order depended on when the profile's
  import step happened to run. Installing onto an existing site appended after
  Plone's own registrations and worked; on a fresh site, where GenericSetup could
  import this step before Plone registered jQuery, ``main.js`` and the vendored
  ``popupforms.js`` landed at positions 0 and 1 with
  ``++resource++plone.app.jquery.js`` at 2. Since cooking merges adjacent
  compatible resources into a single bundle, the ``$ is not defined`` thrown at
  the top of ``main.js`` aborted that bundle before jQuery defined itself, so
  every jQuery-dependent script on the site failed and every Plone overlay form
  rendered as a full page. Observed on a real deployment. Re-importing the step
  repairs a site already in that state, because the importer applies the move to
  an existing resource as well as a new one.
  [chris-adam]
- The replay and lockout counters are no longer declared on
  ``IEnhancedUserDataSchema``. They were never form fields in intent -- they are
  written only by ``helpers.py`` through ``setMemberProperties`` and persist by
  virtue of their ``memberdata_properties.xml`` entry, which a schema field
  neither provides nor replaces. Declaring them broke
  ``plone.app.users``' ``@@user-information``, the form an administrator uses to
  edit another user's profile: that view is not overridden by this package, so it
  rendered all six schema fields, and ``adapter.py`` supplies an accessor for only
  the original three -- ``AttributeError: 'EnhancedUserDataPanelAdapter' object
  has no attribute 'two_factor_authentication_failed_attempts'``. The
  ``omit()`` in ``CustomizedUserDataPanel`` never covered it, being registered for
  ``personal-information`` alone. Removing the fields also removes the write path
  by which a user could have set their own lockout deadline to zero.
  [chris-adam]
- ``@@request-bar-code-reset`` no longer redirects to the portal root once it
  has sent the reset email. The caller reaches that form from the token form,
  by which point the PAS plugin has cleared their ``__ac`` cookie, so they are
  anonymous: on any site whose root is not anonymously viewable the redirect
  sent them to the login form, the "email sent" confirmation was never read,
  and the bounce looked like the reset had failed. The form now re-renders
  itself with the confirmation, as its failure branch already did.
  [chris-adam]
- Deleted the vendored login-form override (``skins/googleauthenticator_custom/
  login_form.cpt``) and the vendored copy of Plone's overlay script
  (``browser/static/plone_ecmascript/popupforms.js``), along with the entire
  skin layer (``skins/`` directory, ``profiles/default/skins.xml``, and
  ``configure.zcml``'s filesystem-directory registration). Plone's own stock
  login form and overlay script are now used unmodified (COEX-02, COEX-03,
  COEX-05).
  [chris-adam]
- ``TokenForm`` now renders ``id="login_form"`` on the served
  ``@@google-authenticator-token`` markup, the selector Plone's own untouched
  overlay script binds its ajax fetch on, so the token step loads inside the
  same overlay the stock login form uses (COEX-01, COEX-09).
  [chris-adam]
- The two auxiliary templates the control panel and the bar-code reset email
  used to reach through a skin-name ``restrictedTraverse`` lookup
  (``control_panel_extra.html``, ``request_bar_code_reset_email.pt``) are now
  ``ViewPageTemplateFile`` class attributes on their respective views (COEX-04).
  [chris-adam]
- Added a real ``profiles/uninstall/`` for this package's own two resources:
  ``++resource++imio.googleauthenticator/main.js`` and ``main.css``. Uninstalling
  no longer leaves the whole site without Plone's overlay script, is idempotent,
  and is reversible by re-applying the default profile (COEX-06).
  [chris-adam]
- Proved, in both application orders and under a repeated profile import, that
  this package's own profile does not collide with ``imio.dms.mail``'s bare
  reposition entry for Plone's stock ``popupforms.js`` resource (COEX-07,
  automated half; the real two-egg install is a manual verification item).
  [chris-adam]
- The post-token redirect target is now validated against the portal with
  ``isURLInPortal()`` before redirecting: an off-site ``next_url`` is refused
  and falls back to the portal context URL instead of being honoured (BUG-01).
  [chris-adam]
- ``CameFromAdapter.getCameFrom()`` now percent-encodes the ``came_from`` value
  it reads, so a value containing ``&``, ``=``, ``+`` or a space can no longer
  forge or truncate the ``&next_url=...`` query-string parameter it is appended
  to (BUG-06).
  [chris-adam]

  **Upgrade note.** A site that already applied a previous version of this
  package's ``profiles/default/jsregistry.xml`` had Plone's own
  ``popupforms.js`` resource unregistered from ``portal_javascripts``. This
  release does not re-register it -- nothing in this package can, only
  Plone's own ``Products.CMFPlone`` profile registers that resource. On such
  a site, upgrading the egg and re-applying this package's profile will
  **not** bring the overlay script back. Recover by re-running
  ``Products.CMFPlone``'s own ``jsregistry`` import step from
  ``portal_setup``, or by recreating the site. The stale
  ``googleauthenticator_custom`` skin layer left in ``portal_skins`` on the
  same site is the second such leftover artifact to clear.
  [chris-adam]
- ``@@setup-two-factor-authentication`` (enrollment, and its reuse as the
  recovery-code regeneration form) now shares the same lockout counter as
  the login token form and the bar-code reset form: a locked account is
  refused before its TOTP code is even checked, a wrong code counts as a
  failed attempt, and a correct code clears the counter. Previously this
  was the only one of the three ``validate_token`` callers with no limit,
  so a caller already holding an authenticated session could brute-force
  six-digit codes without limit and, on a hit, replace a user's stored
  recovery-code hashes with a freshly minted set (CR-01).
  [chris-adam]
- Uninstalling now removes the ``google_auth`` PAS plugin, so two-step
  verification stops being enforced at login and no broken object survives
  in ``acl_users`` if the egg is later removed. It also removes the local
  user-data-schema utility, the three user menu actions, the browser layer,
  the control-panel configlet and the settings records -- including
  ``ska_secret_key``, so signed token URLs still in flight stop validating
  and a reinstall mints a fresh key. Enrolled users' memberdata is
  deliberately kept: the property declarations, the encrypted seeds and the
  recovery-code hashes all survive, so a reinstall restores working
  two-step verification instead of stranding everyone who had enrolled
  (COEX-06 widening, v1.0-MILESTONE-AUDIT.md Gap 2).
  [chris-adam]
- A rejected or unreachable mail server on the bar-code reset form now
  reports itself with the same in-page failure message every other error on
  that form already produces, instead of escaping as an unhandled exception
  and a bare Zope error page. The ``except SMTPRecipientsRefused: raise
  SMTPRecipientsRefused(...)`` re-raise -- which the enclosing
  ``except ValueError`` could not catch -- was deleted outright, and the
  catch now also covers ``socket.error`` (an unreachable server, not an
  ``SMTPException`` at all) (BUG-07).
  [chris-adam]
- The ``enable_two_factor_authentication`` profile field's description no
  longer links to ``@@setup-two-factor-authentication`` or
  ``@@disable-two-factor-authentication``. Both views act on the *viewing*
  user's own account, never on the profile being viewed, and this
  description is the only thing ``@@user-information`` (the
  administrator-viewing-another-user form) renders for the field -- so an
  administrator viewing someone else's profile who clicked "disable" cleared
  their own second factor while being told it had succeeded (BUG-08).
  [chris-adam]
- A user who finishes enrollment now lands on a recovery-codes page whose
  one link goes to the site's home page -- resolved through
  ``context/@@plone/navigationRootUrl`` -- instead of back to their own
  profile (UX-01).
  [chris-adam]
- The enrollment page now shows the base32 TOTP secret as selectable
  ``<code>`` text beside the QR code, produced from the same
  ``get_or_create_secret()`` call already used to build the QR, so nothing
  is minted or looked up twice (UX-02).
  [chris-adam]
- **Known consequence.** Shortening the ``enable_two_factor_authentication``
  field description above (BUG-08) retires its old message id. The French
  translation of the old two-link text, at
  ``locales/fr/LC_MESSAGES/imio.googleauthenticator.po:76-77``, is now
  orphaned, so that field reads in English for a French-speaking
  administrator until the message catalogues are rebuilt. This is
  deliberate and accepted, not a defect, and is an input for the catalogue
  rebuild rather than something patched in this release.
  [chris-adam]

0.3.0 (unreleased)
------------------

- Add support for whitelisting IP ranges. Single IP addresses can still
  be used and mixed and matched with ranges.
  [lgraf]
- Move the [enable|disable]_two_factor_authentication actions before the
  logout action, that 'logout' is still at the bottom of the menu.
  [lgraf]
- Use the default "You're now logged in" message and translate it
  in the 'plone' domain. That way, it will look the same as with
  the regular Plone login and be translated in all languages.
  [lgraf]
- Disable unloadProtection for controlpanel form.
  (Gets rid of "Leave this page?" message when editing settings)
  [lgraf]
- Avoid prematurely logging user in (before token has been verified)
  [lgraf]
- Make sure to handle exceptions in auth plugins properly.
  [lgraf]
- Consider all authentication plugins when checking credentials.
  [lgraf]

0.2.5 (2014-06-20)
------------------

- Improved PAS plugin.

0.2.4
-----

- Minor fixes.

0.2.3
-----

- Making sure the URL to reset the bar-code in template is not escaped.

0.2.2
-----

- Send e-mail in "text/html" format for requst bar code reset template.

0.2.1
-----

- Fix typo in `helpers.extract_ip_address_from_request` (proxy related).

0.2
---

- Now admins are able to force the two-step verification for all users (app control panel).
- Omit two-step verification for white-listed IP addresses (app control panel).
- Links to enable/disable two-step verification moved from "Personal preferences" page to
  Plone menu (next to "Log out").

0.1.1
-----

- Fixes in manifest.

0.1
---

- Initial release (no longer available on PyPI), with two-step verification, bar-code/token recover,
  basic app control panel.
