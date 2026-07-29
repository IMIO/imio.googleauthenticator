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
- ``ska_secret_key`` is no longer seeded at install time; it is minted once,
  lazily, on first use of ``get_ska_secret_key()``.
  [chris-adam]
- The ``ska`` signing key derivation now length-prefixes its three
  components instead of bare-concatenating them, so two different
  component boundaries can no longer collide on the same key. This
  invalidates any previously issued signed URL -- harmless before any site
  is deployed and any user is enrolled, which is why it ships now.
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
