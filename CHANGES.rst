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
