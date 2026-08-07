---
status: root-cause-confirmed
phase: 10-global-enforcement-and-enrollment
found: 2026-08-07
found_by: operator UAT on server.dmsmail site MOD-1076 / MOD-1076-1
evidence: /srv/src/server.dmsmail/var/log/instance1.log
severity: blocker
supersedes: the two earlier hypotheses for "existing users are never asked"
---

# The login plugin raises on every request because a settings record is missing

## What the operator observed

Running a real Plone site (`MOD-1076`, then `MOD-1076-1`) in the `server.dmsmail` buildout, with
`imio.googleauthenticator` checked out at commit `13da4ae` (which contains all of Phase 10 plus the
Phase 10 code-review fixes):

> "For existing users, nothing is asked and they can log in without setting MFA."

## Root cause, proven from the instance log

`/srv/src/server.dmsmail/var/log/instance1.log`, line 1207155 onward, timestamp `260807 152305`:

```
Module Products.PluggableAuthService.PluggableAuthService, line 652, in _extractUserIds
Module imio.googleauthenticator.pas_plugin, line 215, in authenticateCredentials
Module imio.googleauthenticator.helpers, line 1290, in is_whitelisted_client
Module imio.googleauthenticator.helpers, line 1248, in get_ip_addresses_whitelist
Module imio.googleauthenticator.helpers, line 189, in get_app_settings
Module plone.registry.registry, line 78, in forInterface
KeyError: 'Interface `imio.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings`
defines a field `max_failed_attempts`, for which there is no record.'
```

`authenticateCredentials` calls `is_whitelisted_client()` as its first piece of real work. That
reaches `get_app_settings()`, which calls `plone.registry`'s `forInterface()`. That raises
`KeyError` because the site's registry has no record for the `max_failed_attempts` field.

**The plugin therefore raises before it checks anything at all.** It never reads the user's enable
flag, never decides on a redirect, never applies a second factor. The user logs in normally.

This is a **fail-open** failure of a security control: an incomplete registry does not refuse the
login, it skips the second factor entirely.

## Why the record is missing

| Fact | Evidence |
|---|---|
| `max_failed_attempts` and `lockout_duration` were added to the settings interface on 2026-07-31 | `git log -S max_failed_attempts` → commit `bb528fe`, previous milestone |
| `registry.xml` creates records from the interface, not from an explicit field list | `profiles/default/registry.xml` contains only `<records interface="…IGoogleAuthenticatorSettings" />` |
| The GenericSetup profile version has never changed | `profiles/default/metadata.xml` says `1000`; the instance log confirms `profile imported id=imio.googleauthenticator:default version=1000` on every import from 2026-08-03 onward |
| There is no upgrade step and no upgrades package | `ls src/imio/googleauthenticator/upgrades` → does not exist |
| The site has had the add-on installed repeatedly since 2026-08-03 | Five `profile imported` entries in the log: 2026-08-03 14:04, 08-04 14:36, 08-05 10:09, 08-07 10:51, 08-07 15:28 |

A site whose registry was created before those two fields existed keeps a registry that is missing
them. Re-importing the profile with the "upgrade" dependency strategy does not add them, because
the profile version never changed and no upgrade step exists to re-import the registry.

## This contradicts a decision made during Phase 10 planning

Phase 10's planner explicitly decided **no profile version bump and no upgrade step**, recording the
reason as: the package has never been deployed, and five earlier member-data properties were added
the same way.

That reason is factually wrong. The instance log shows the package has been installed on real sites
since 2026-08-03. The consequence is that no registry change and no member-data change made after a
site's first install ever reaches that site.

## What a correct fix needs to change

1. **Bump the GenericSetup profile version** in `profiles/default/metadata.xml` from `1000`.
2. **Add an upgrade step** that re-imports the `registry` and `memberdata-properties` steps, so an
   existing site gains records and properties added after its first install. The project's own
   `CLAUDE.md` documents this as the required process and names
   `genericsetup:upgradeStep` in `upgrades/configure.zcml` as the shape to follow. No `upgrades/`
   package currently exists, so it has to be created.
3. **Stop the login plugin failing open.** Even with an upgrade step, a missing or unreadable
   settings record must not let a login through without a second factor. Decide deliberately
   whether an incomplete configuration should refuse the login or fall back to requiring the second
   factor, and make that explicit rather than incidental.

## Still unexplained — do not treat as solved

The operator also reported: "For new users, the OTP is asked but they can reset it" — meaning
accounts created after the install are asked for a code without first being shown the enrollment
page.

A separate investigation (`.planning/debug/10-enrollment-routing-lands-on-code-entry.md`) could NOT
reproduce this. It built a new account and drove a real login twice, through both redirect paths,
and both times the user correctly landed on the enrollment page with a valid signed link.

On a site where `authenticateCredentials` raises on every request, nobody would be asked for a code
at all — so that observation cannot have come from the same site state as the failure above. It
needs its own reproduction before anyone tries to fix it. The instance log ends immediately after
the 2026-08-07 15:28 install, so any login attempts on `MOD-1076-1` after that point are not yet
recorded in it.

## Files involved

- `src/imio/googleauthenticator/helpers.py:189` — `get_app_settings`, where the `KeyError` is raised
- `src/imio/googleauthenticator/helpers.py:1248` — `get_ip_addresses_whitelist`
- `src/imio/googleauthenticator/helpers.py:1290` — `is_whitelisted_client`
- `src/imio/googleauthenticator/pas_plugin.py:215` — `authenticateCredentials`, first real call
- `src/imio/googleauthenticator/profiles/default/metadata.xml` — profile version, never bumped
- `src/imio/googleauthenticator/profiles/default/registry.xml` — creates records from the interface
- `src/imio/googleauthenticator/browser/controlpanel.py:52,60` — the two fields with no records
