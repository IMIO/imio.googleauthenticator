# External Integrations

**Analysis Date:** 2026-07-28

## APIs & External Services

**QR Code Generation:**
- Google Charts API - Generates QR codes for Google Authenticator setup
  - Endpoint: `https://chart.googleapis.com/chart` (HTTP GET)
  - Used in: `src/collective/googleauthenticator/helpers.py:122` via `get_barcode_image()`
  - Parameters: `chs` (size), `chld` (error correction), `cht` (type=qr), `chl` (otpauth URI)
  - No authentication required (public endpoint)
  - Fallback: None - QR code generation will fail if API is unavailable

**User Authentication:**
- Plone's PluggableAuthService (PAS) - Built-in authentication framework
  - Integration point: `src/collective/googleauthenticator/pas_plugin.py:GoogleAuthenticatorPlugin`
  - Role: Implements `IAuthenticationPlugin` interface
  - Interaction: Chains with other PAS plugins (session, source_users)

## Data Storage

**Databases:**
- Plone ZODB (Zope Object Database)
  - Default object database included with Zope
  - User data extension: Stores two new properties per user:
    - `enable_two_factor_authentication` (Boolean)
    - `two_factor_authentication_secret` (String - Base32 encoded secret)
  - Location: Embedded in user records via `Products.PlonePAS.tools.memberdata`
  - ORM/Client: Direct Plone API via `plone.api.user` (`src/collective/googleauthenticator/helpers.py:48`)

**Settings Storage:**
- Plone Registry (via plone.app.registry)
  - Interface: `IGoogleAuthenticatorSettings` (`src/collective/googleauthenticator/browser/controlpanel.py:24`)
  - Settings stored as registry entries (ZODB-backed)
  - Accessed via: `plone.registry.interfaces.IRegistry` utility

**File Storage:**
- Local filesystem only (no external file services)
- QR code images generated on-demand via Google Charts API (not stored)

**Caching:**
- None - No external caching service (Redis, Memcached, etc.)
- In-memory caching via Python function decorators optional (not implemented)

## Authentication & Identity

**Auth Provider:**
- Custom implementation + Plone PAS chain
  - Primary: Plone's built-in user authentication
  - Secondary: Google Authenticator TOTP token validation
  - Implementation: `src/collective/googleauthenticator/pas_plugin.py:GoogleAuthenticatorPlugin`

**Two-Factor Authentication:**
- TOTP (Time-based One-Time Password) via Google Authenticator
  - Validation library: onetimepass (==0.2.2)
  - Validator function: `src/collective/googleauthenticator/helpers.py:191` via `valid_totp()`
  - Token format: 6-digit codes, 30-second validity window
  - Secret storage: Base32-encoded 128-bit secrets in user profile

**URL Signing (for secure token passing):**
- ska library (>=1.1) - Cryptographic URL signing
  - Function: `src/collective/googleauthenticator/helpers.py:272` via `sign_user_data()`
  - Purpose: Pass user context to token validation view without session
  - Secret key composition: User secret + browser hash + site secret_key
  - Validation: `src/collective/googleauthenticator/helpers.py:372` via `validate_user_data()`

## Monitoring & Observability

**Error Tracking:**
- None - No external error tracking service
- Logging: Python standard `logging` module to stdout
  - Logger: `"collective.googleauthenticator"` (`src/collective/googleauthenticator/helpers.py:30`)
  - Log levels: DEBUG (helpers), INFO (PAS plugin activity)

**Logs:**
- Standard output via Python logger
- No external log aggregation (Splunk, DataDog, etc.)
- Buildout recipe `plone.recipe.codeanalysis` provides quality reports

## CI/CD & Deployment

**Hosting:**
- Any Zope application server (standalone, via buildout)
- No cloud-specific hosting required
- No containerization (Docker) in base package

**CI Pipeline:**
- GitHub Actions: `.github/workflows/package-test.yml`, triggered on push, pull_request,
  and workflow_dispatch
- Delegates to iMio's reusable workflow
  `IMIO/gha-workflows/.github/workflows/package-test-legacy.yml@v1` — the repo holds no
  build steps of its own
- Inputs: `buildout_config_file: test-4.3.cfg`, `requirements_file: requirements-4.3.txt`,
  `runner_label: gha-runners-docs-py2` (self-hosted Python 2 runner),
  `test_command: 'bin/test -t !robot'`
- Single job (`tests-plone4`). No `tests-current` matrix and no coverage job: the
  `package-test-coverage.yml` and `package-test-uv.yml` reusable workflows are uv/Python 3
  based, with no Python 2.7 equivalent
- The reusable workflow optionally posts to Mattermost via a `mattermost_webhook_url`
  secret; this repo does not pass one
- CI does **not** run `bin/code-analysis`, so the package's outstanding lint debt does not
  fail the build
- **Travis CI was removed** (`.travis.yml` deleted). The old pipeline also pushed coverage
  to Coveralls and notified `irc.freenode.org#plone-testing`; neither survives.

**Version Control:**
- Git remote: git@github.com:IMIO/imio.googleauthenticator.git (iMio fork)
- `setup.py` metadata and README still point upstream at
  https://github.com/collective/collective.googleauthenticator

## Environment Configuration

**Required Settings (application level):**
- `ska_secret_key` - Site secret for URL signing (must be set in control panel)
  - Location: Plone control panel → "Google Authenticator"
  - Setting: `IGoogleAuthenticatorSettings.ska_secret_key`
- `globally_enabled` - Force 2FA for all users (default: True)
- `ip_addresses_whitelist` - IP ranges/addresses to skip 2FA (optional)

**Secrets Location:**
- Plone ZODB registry (encrypted at rest if ZODB encryption enabled)
- No `.env` files or environment variable configuration
- Secrets configured via Plone control panel web interface

**No External Service Credentials Required:**
- Google Charts API: Public endpoint, no authentication
- TOTP validation: Client-side secret-based, no API credentials
- Email: Implicit via Plone's MailHost (configured separately in Plone)

## Webhooks & Callbacks

**Incoming:**
- None - No external webhooks consumed

**Outgoing:**
- Implicit email notifications (via Plone MailHost)
  - Trigger: Password reset / bar code reset requests
  - System: Configured in Plone's control panel
  - Not explicitly modeled in collective.googleauthenticator

## User Data Flow

**Setup Flow:**
1. User navigates to `@@google-authenticator-enable-two-factor`
2. View generates QR code via `get_barcode_image()` → Google Charts API
3. User scans QR code with Google Authenticator mobile app
4. User submits TOTP token from mobile app
5. Token validated via `valid_totp()` against stored secret
6. User property `enable_two_factor_authentication` set to True

**Login Flow:**
1. User logs in with username/password
2. PAS chain reaches `GoogleAuthenticatorPlugin.authenticateCredentials()`
3. If 2FA enabled: Password validated, credentials consumed, redirect to `@@google-authenticator-token`
4. URL signed with `sign_url()` using `ska` library (secret = user secret + browser hash + site secret)
5. User submits TOTP token on token validation page
6. Token validated, user properties verified, session established

**IP Whitelisting:**
- Check at: `src/collective/googleauthenticator/helpers.py:499` via `is_whitelisted_client()`
- Extracts client IP from `REMOTE_ADDR` or `HTTP_X_FORWARDED_FOR`
- Uses ipaddress library to match against CIDR ranges
- If match: 2FA requirement skipped entirely

---

*Integration audit: 2026-07-28*
