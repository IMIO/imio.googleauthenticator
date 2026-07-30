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
