# Architecture

**Analysis Date:** 2026-07-28

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Browser / HTTP Request Layer                  │
│    User Forms (login, token validation, setup, disable)          │
│  `src/collective/googleauthenticator/browser/forms/`             │
│  `src/collective/googleauthenticator/www/`                       │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│          View/Form Processing Layer (z3c.form)                   │
│  Token validation, 2FA setup, control panel management           │
│  `src/collective/googleauthenticator/browser/controlpanel.py`    │
│  `src/collective/googleauthenticator/browser/forms/token.py`     │
│  `src/collective/googleauthenticator/browser/forms/user_setup.py`│
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              Application Logic Layer (Helpers)                    │
│  Token generation/validation, secret management, signing         │
│  `src/collective/googleauthenticator/helpers.py`                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│            Authentication/Authorization Layer (PAS)              │
│  GoogleAuthenticatorPlugin (IAuthenticationPlugin)               │
│  Adapter framework (ICameFrom, UserDataPanel)                    │
│  `src/collective/googleauthenticator/pas_plugin.py`              │
│  `src/collective/googleauthenticator/adapter.py`                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│            User Data / Profile Extension Layer                    │
│  Extended user schema with 2FA properties                        │
│  `src/collective/googleauthenticator/userdataschema.py`          │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              Plone / Zope Application Server                      │
│  User management, PAS (PluggableAuthService), sessions           │
│  Registry (plone.registry)                                       │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| GoogleAuthenticatorPlugin | PAS authentication plugin - intercepts login, validates user credentials, redirects to 2FA token screen if enabled | `src/collective/googleauthenticator/pas_plugin.py` |
| EnhancedUserDataPanelAdapter | Exposes 2FA properties (enable_two_factor_authentication, two_factor_authentication_secret, bar_code_reset_token) to user profile UI | `src/collective/googleauthenticator/adapter.py` |
| CameFromAdapter | Extracts post-login redirect URL from HTTP referer since Plone form field removed | `src/collective/googleauthenticator/adapter.py` |
| IEnhancedUserDataSchema | Schema definition extending Plone's user properties with 2FA fields | `src/collective/googleauthenticator/userdataschema.py` |
| Token validation form | z3c.form for collecting and validating one-time password token | `src/collective/googleauthenticator/browser/forms/token.py` |
| User setup form | Generates QR code, presents secret/recovery codes for new 2FA setup | `src/collective/googleauthenticator/browser/forms/user_setup.py` |
| Control panel | Settings form for global 2FA configuration (secret key, IP whitelist, global enable) | `src/collective/googleauthenticator/browser/controlpanel.py` |
| Helper functions | Token generation/validation (TOTP), secret management, URL signing, IP validation | `src/collective/googleauthenticator/helpers.py` |

## Pattern Overview

**Overall:** Plone PAS (PluggableAuthService) authentication plugin with two-step verification middleware.

**Key Characteristics:**
- Extends Plone's user authentication pipeline via PAS plugin interface
- Intercepts credentials during login, validates password, then redirects to 2FA form
- Uses `ska` library for cryptographic signing of URLs to protect redirect flow
- Uses `onetimepass` for TOTP token validation (Google Authenticator compatible)
- Stores 2FA settings in user profile properties (enable flag + secret key)
- Optional IP whitelist to bypass 2FA for trusted networks

## Layers

**Authentication/Authorization (PAS Plugin):**
- Purpose: Intercept Plone login flow and inject 2FA verification step
- Location: `src/collective/googleauthenticator/pas_plugin.py`
- Contains: `GoogleAuthenticatorPlugin(BasePlugin)` implementing `IAuthenticationPlugin`
- Depends on: `plone.api`, `ska`, `adapter.CameFromAdapter`, `helpers` module
- Used by: Plone's PluggableAuthService during login

**View/Form Processing Layer:**
- Purpose: Render user-facing forms for token entry, 2FA setup, and settings
- Location: `src/collective/googleauthenticator/browser/`
- Contains: z3c.form classes, view handlers, control panel registration
- Depends on: `plone.directives.form`, `z3c.form`, `helpers` module
- Used by: HTTP requests to `@@google-authenticator-token`, `@@setup-two-factor-authentication`, etc.

**Application Logic (Helpers):**
- Purpose: Core business logic for TOTP validation, secret generation, URL signing, IP checking
- Location: `src/collective/googleauthenticator/helpers.py`
- Contains: 27+ helper functions for token validation, secret management, whitelisting
- Depends on: `onetimepass`, `ska`, `plone.api`, `plone.registry`
- Used by: PAS plugin, forms, views, user creation handlers

**User Data Schema:**
- Purpose: Define and manage 2FA-related user profile fields
- Location: `src/collective/googleauthenticator/userdataschema.py`
- Contains: `IEnhancedUserDataSchema` interface, `UserDataSchemaProvider` adapter, user creation event handler
- Depends on: `plone.app.users`, `Products.PluggableAuthService`
- Used by: Plone's user management system during user creation and profile updates

**Initialization/Setup:**
- Purpose: Generic Setup (GS) profile and installation handlers
- Location: `src/collective/googleauthenticator/setuphandlers.py`, `src/collective/googleauthenticator/profiles/`
- Contains: PAS plugin registration, secret key generation on install
- Depends on: `Products.PluggableAuthService`, `plone.registry`
- Used by: Plone installation process

## Data Flow

### Primary Login Flow (with 2FA enabled)

1. User enters credentials in `/login_form` (`pas_plugin.py:66-80`)
   - Credentials dict created by Plone's login machinery

2. `GoogleAuthenticatorPlugin.authenticateCredentials()` intercepts (`pas_plugin.py:66`)
   - Checks if client IP is whitelisted via `helpers.is_whitelisted_client()` → bypass 2FA if yes
   - Retrieves user via `plone.api.user.get(username=login)`
   - Reads `enable_two_factor_authentication` property from user profile

3. If 2FA enabled, password validation phase (`pas_plugin.py:98-125`)
   - Iterates through other PAS authentication plugins to validate password
   - Continues only if password is valid, else returns `None` (auth failed)

4. Credential clearing and redirect preparation (`pas_plugin.py:127-155`)
   - Clears credentials dict to prevent duplicate authentication by other plugins
   - Clears session cookie to logout user temporarily
   - Signs user data (username + hash) via `helpers.sign_user_data()` using `ska` library
   - Builds signed URL to `@@google-authenticator-token` view
   - Appends `came_from` URL via `adapter.CameFromAdapter.getCameFrom()`

5. Browser redirects to token validation view (`pas_plugin.py:153`)
   - User sees `browser/forms/token.py:TokenForm`

6. User enters TOTP code, form handler validates (`browser/forms/token.py:62-130`)
   - Extracts and verifies signed data via `helpers.validate_user_data()`
   - Validates token via `helpers.validate_token()` (uses `onetimepass.valid_totp()`)
   - If both valid, sudos login user and redirects to original destination
   - If invalid, shows error message

### Alternative Flows

**2FA Disabled:** Plugin returns `None` early, login continues via standard Plone authentication.

**Whitelisted IP:** Plugin returns `None` immediately (`pas_plugin.py:80`), bypasses all 2FA checks.

**Setup New 2FA:** User navigates to `@@setup-two-factor-authentication`
- Form renders QR code via `helpers.get_token_description()` (Google Charts API)
- Secret generated via `helpers.generate_secret()`
- User scans code with Google Authenticator app
- User enters test token to confirm before saving

**State Management:**
- No server-side session state during 2FA flow
- Uses cryptographic URL signing (`ska` library) instead: URL contains `auth_user` and signature
- Secret key for signing combines user's 2FA secret + browser hash + global site secret
- Browser hash provides device-binding (different browser = different signature)

## Key Abstractions

**TOTP Token Generation/Validation:**
- Purpose: Generate time-based one-time passwords compatible with Google Authenticator
- Examples: `helpers.validate_token()`, `helpers.get_secret()`, `helpers.generate_secret()`
- Pattern: Delegates to `onetimepass.valid_totp()` for RFC 4226/4328 compliance

**URL Signing & Verification:**
- Purpose: Protect redirect flow from URL tampering during 2FA verification step
- Examples: `helpers.sign_user_data()`, `helpers.validate_user_data()`, `helpers.get_ska_secret_key()`
- Pattern: Uses `ska` library with composite secret (user secret + browser hash + global secret)

**IP Whitelist Validation:**
- Purpose: Allow trusted networks to bypass 2FA
- Examples: `helpers.is_whitelisted_client()`, `helpers.extract_ip_address_from_request()`, `helpers.get_ip_ranges()`
- Pattern: Supports CIDR notation for IP ranges, handles proxy headers (`X-Forwarded-For`)

**Browser Fingerprinting:**
- Purpose: Tie signed URLs to a specific browser to prevent session hijacking
- Examples: `helpers.get_browser_hash()`
- Pattern: SHA1 hash of `User-Agent` header included in `ska` signing key

## Entry Points

**PAS Plugin Interface:**
- Location: `src/collective/googleauthenticator/pas_plugin.py:66`
- Triggers: Every user login attempt (via `authenticateCredentials()` method)
- Responsibilities: Intercept credentials, validate password, redirect to 2FA form if needed

**Zope Initialize Hook:**
- Location: `src/collective/googleauthenticator/__init__.py:13-22`
- Triggers: When Plone loads the product
- Responsibilities: Register PAS plugin class with `registerMultiPlugin()`

**Generic Setup Install Profile:**
- Location: `src/collective/googleauthenticator/profiles/default/`
- Triggers: When add-on is installed via Plone control panel
- Responsibilities: Register control panel, browser layer, CSS/JS, register adapter factories

**Event Handlers:**
- Location: `src/collective/googleauthenticator/userdataschema.py:76-96`
- Triggers: `IPrincipalCreatedEvent` when new user created
- Responsibilities: If globally_enabled setting true, generate secret and enable 2FA for new users

## Architectural Constraints

- **Threading:** Single-threaded Zope2 WSGI application. No explicit threading used. Global request accessed via `getRequest()`.
- **Global state:** 
  - `sk.SECRET_KEY` in `plone.registry` (Global settings)
  - Module-level logger instances in each file
  - No session state during 2FA flow (uses signed URLs)
- **Circular imports:** None detected. Adapter callbacks create loose coupling between `pas_plugin` and `adapter`.
- **Authentication ordering:** Plugin position in PAS plugin list matters. Typically ordered last so standard auth plugins run first, this plugin only validates 2FA on successful password auth.
- **User property mutation:** User 2FA properties set via `user.setMemberProperties()` (Plone MemberData mutation API). No direct database writes.

## Anti-Patterns

### Credentials Dictionary Mutation (Design Compromise)

**What happens:** Plugin deletes all keys from credentials dict after password validation to prevent other auth plugins from processing (`pas_plugin.py:132-133`).

**Why it's wrong:** Mutating shared state (the credentials dict) is a side effect that breaks composition. Other plugins may expect credentials to survive the authentication chain.

**Do this instead:** This is a deliberate workaround for Plone's PAS architecture limitation. The plugin has no other way to say "consume these credentials" without mutation. Document as accepted technical debt tied to PAS design.

### Bearer Token in Query String (Security Shortcut)

**What happens:** Signed user data passed in URL query string during 2FA redirect (`pas_plugin.py:144-151`).

**Why it's wrong:** Query strings are logged in access logs, referer headers, browser history. Passing authentication data in URLs violates HTTP security best practices.

**Do this instead:** Use POST with hidden form fields or HTTP-only cookies. Short-term: ensure access logs are sanitized and rotated. Long-term: refactor to POST-based flow using session tokens instead of signed URLs.

### Browser Hash Fingerprinting (Weak Binding)

**What happens:** User-Agent header hashed as part of signing key to bind session to browser (`helpers.py:210-225`).

**Why it's wrong:** User-Agent easily spoofed and varies within same browser (updates). Not cryptographically sound device binding.

**Do this instead:** Remove reliance on User-Agent, use HTTP-only session cookies with SameSite=Strict flag instead of URL-based signing. If device binding needed long-term, implement WebAuthn.

## Error Handling

**Strategy:** Pass validation results up the call stack, let views/forms handle display. Logging at DEBUG level for troubleshooting, INFO level for auth failures.

**Patterns:**
- Token validation returns boolean; form checks and shows error to user
- User data signing/verification uses `ska` library's `SignatureValidationResult` object
- PAS plugin catches plugin exceptions, logs, and continues with next plugin (per `Products.PluggableAuthService` protocol)
- IP validation swallows address parsing exceptions, treats as not-whitelisted
- User property lookups return empty string if property missing, no exceptions

## Cross-Cutting Concerns

**Logging:** Python `logging` module at module level. Debug-level logs for token generation, validation steps, IP checking. Info-level for auth failures.

**Validation:** 
- TOTP validation via `onetimepass.valid_totp()` (RFC 4226/4328 compliant)
- URL signing validation via `ska.validate_signed_request_data()` (time-window tolerance included)
- IP range validation via `ipaddress` stdlib (handles CIDR notation, IPv4/IPv6)

**Authentication:** PAS plugin architecture handles credential extraction → this plugin only validates 2FA. Standard Plone auth plugins validate password before this one sees it.

---

*Architecture analysis: 2026-07-28*
