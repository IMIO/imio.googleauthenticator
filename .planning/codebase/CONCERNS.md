# Codebase Concerns

**Analysis Date:** 2026-07-28

## Tech Debt

**Python 2 Only (EOL Since 2020):**
- Issue: Codebase is exclusively Python 2.6/2.7 compatible; Python 2 reached end-of-life in January 2020
- Files: All Python files in `src/collective/googleauthenticator/`
- Specific markers: `basestring` (lines 141, 164 in `helpers.py`), `unicode()` call (line 44 in `setuphandlers.py`), `implements()` vs `@implementer()` (line 99 in `adapter.py`, line 100 in `adapter.py`)
- Impact: Cannot use modern Python features; no security updates available; incompatible with Python 3; blocks future dependency upgrades
- Fix approach: Migrate to Python 3. Use `six` library or conditional imports for immediate compatibility layer, then full Python 3 migration

**Plone 4 Only:**
- Issue: Targets Plone 4 exclusively (from setup.py classifiers and imports like `Products.PluggableAuthService`)
- Files: `setup.py`, all browser/plugin code
- Impact: Cannot be used with Plone 5/6; Plone 4 is severely outdated
- Reinforced by the buildout layout: only `test-4.3.cfg` / `requirements-4.3.txt` exist. The
  scripts-buildout layout supports 5.2/6.0/6.1 side by side, but those configs were
  deliberately not added
- Fix approach: Add support for Plone 5+ while maintaining Plone 4 compatibility, then
  deprecate Plone 4. Mechanically this means copying `test-6.x.cfg` /
  `requirements-6.x.txt` from IMIO/scripts-buildout and adding the matching
  `tests-current` matrix job to `.github/workflows/package-test.yml`

**Deprecated Plone APIs:**
- Issue: Uses deprecated private/internal APIs that may break between versions
- Files: 
  - `browser/forms/token.py:103` - `acl_users.session._setupSession()` (underscore prefix indicates private API)
  - `browser/forms/token.py:133`, `pas_plugin.py:141` - `response.setCookie('__ac', '', path='/')` (deprecated cookie handling)
- Impact: Code may break with Plone security updates or internal refactoring
- Fix approach: Use public Plone authentication APIs; replace setCookie with modern response methods

**Hardcoded TODO/FIXME Markers:**
- Issue: Unresolved placeholder TODOs indicating incomplete features
- Files:
  - `browser/forms/token.py:106-107` - "Is there a nicer way of resolving the @@google_authenticator_token_form URL?"
  - `browser/forms/user_setup.py:94` - Same URL resolution issue
  - `helpers.py:134, 156` - "Return hashed version if hashed is set to True" (unused hashing parameter)
- Impact: Features are half-implemented; URL resolution pattern is unclear to maintainers
- Fix approach: Either complete hashing implementation or remove parameters; create utility for URL resolution

**Disabled Feature:**
- Issue: Two-factor authentication disabling is commented out and non-functional
- Files: `browser/controlpanel.py:117` - `disable_two_factor_authentication_for_users(users)` call is commented out
- Impact: Admins cannot disable 2FA for all users from control panel; inconsistent state management
- Fix approach: Uncomment and test, or explicitly document why disabling is not allowed and remove the UI option

**String Escaping FIXME:**
- Issue: Plone escapes special characters (e.g., '+') in URL values; workaround exists but marked as fragile
- Files: `helpers.py:310-312, 338-340` - `extract_request_data_from_query_string()` and `extract_request_data()`
- Impact: May fail silently with certain payload characters; security implications unclear
- Fix approach: Document why escaping happens and whether it's a security feature or bug; add tests for edge cases

**Lint Debt Blocks the Pre-Commit Hook:**
- Issue: `bin/code-analysis` exits 1 on ~40 pre-existing findings, and `base.cfg` sets
  `pre-commit-hook = True` / `return-status-codes = True`, so buildout installs a git hook
  that fails every commit
- Files: mostly `src/collective/googleauthenticator/tests/` — `I001`/`I003`/`I004` isort
  ordering, `F401` unused imports (`plone.testing.z2.Browser`, several
  `plone.app.testing` constants in `test_security.py` and `test_pas_plugin.py`),
  `W292`/`W293` whitespace, `E302`, `E271`
- Impact: Every commit needs `--no-verify`, which trains contributors to bypass the hook
  entirely — so genuinely new lint errors will also sail through. CI does not run
  code-analysis, so nothing catches them
- Fix approach: One mechanical `bin/isort --apply` + whitespace/unused-import sweep over
  `src/`, in its own commit, then the hook becomes useful again

**No Coverage Measurement in CI:**
- Issue: The removed `.travis.yml` ran `bin/createcoverage` and uploaded to Coveralls.
  `.github/workflows/package-test.yml` has no coverage job
- Cause: `IMIO/gha-workflows` only ships `package-test-coverage.yml`, which is uv/Python 3
  based (`.venv/bin/coverage`, default python 3.13) and has no Python 2.7 equivalent
- Impact: Coverage is now measurable only locally via `bin/createcoverage`; regressions in
  the (already thin) test suite go unnoticed. `.coveragerc` is still present and correct
- Fix approach: Either run `bin/createcoverage` as a custom step against the py2 runner, or
  accept local-only coverage until the Python 3 migration

**CI Depends on a Self-Hosted Python 2 Runner:**
- Issue: `.github/workflows/package-test.yml` requires `runner_label: gha-runners-docs-py2`
- Impact: Not buildable on stock GitHub-hosted runners; if iMio retires that runner pool,
  CI stops working with no fallback. Forks outside the iMio org cannot run CI at all
- Fix approach: Nothing cheap — Python 2.7 is unavailable on current ubuntu-latest images.
  Real fix is the Python 3 migration

**Tests Violate Plone Test Isolation:**
- Issue: `tests/base.py:_install()` drives a `plone.testing.z2.Browser` (quickinstaller
  round-trip) inside an `IntegrationTesting` layer, which commits a transaction
- Files: `tests/base.py`, `tests/test_generic.py`, `tests/test_pas_plugin.py`,
  `tests/test_security.py`
- Impact: Caps `plone.testing` at Plone 4.3's 4.1.3 — the pin cannot move to 5.0.0, whose
  `TestIsolationBroken` guard makes all 6 browser tests error. Documented in `test-4.3.cfg`
  and `.planning/codebase/TESTING.md`
- Fix approach: Move those classes onto `COLLECTIVE_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING`,
  already defined but unused in `src/collective/googleauthenticator/testing.py`. The
  in-layer install workaround (see the comment in `base.py:16-17`) should also be replaced
  by `applyProfile` in the layer's `setUpPloneSite`

## Known Bugs

**Open Redirect Vulnerability:**
- Symptoms: User redirected to attacker-controlled URL after successful 2FA authentication
- Files: `browser/forms/token.py:112-113`
- Trigger: POST to `@@google-authenticator-token` with `next_url=https://attacker.com` in signed request
- Root cause: Line 112 accepts `next_url` from request data without validation: `redirect_url = request_data.get('next_url', context_url)` then redirects (line 113)
- Workaround: Manually verify redirect URLs in browser before clicking
- Fix: Validate that `next_url` is within site domain; use `request.BASE_IMPLICIT_REDIRECT_EXCEPTION` or Zope's redirect validator

**Variable May Be Unbound:**
- Symptoms: UnboundLocalError on failed form submission
- Files: `browser/forms/user_setup.py:96`
- Trigger: Form submission with validation errors; `redirect_url` is only set inside the `if valid_token:` block (line 74) but is referenced unconditionally at line 96
- Code flow: If `api.user.is_anonymous()` check passes, but `extractData()` fails (line 63) or token is invalid, `redirect_url` is never assigned
- Fix: Initialize `redirect_url` before the try-except block or ensure all code paths set it

**Token Comparison Without Timing-Attack Protection:**
- Symptoms: Timing attacks may leak information about valid tokens
- Files: `browser/forms/reset_bar_code.py:104` - Plain string comparison `if bar_code_reset_token != signature_token:`
- Impact: Attacker could potentially guess tokens by measuring response times
- Fix: Use `hmac.compare_digest()` or constant-time comparison from `secrets` module

## Security Considerations

**Bare Exception Handling:**
- Risk: Exception details may leak information; specific exception types should be caught
- Files: 
  - `helpers.py:223-225` - except Exception (get_browser_hash)
  - `helpers.py:412-413` - except Exception (enable_two_factor_authentication_for_users)
  - `helpers.py:429-430` - except Exception (disable_two_factor_authentication_for_users)
  - `helpers.py:481-483` - except Exception (get_ip_addresses_whitelist)
  - `browser/forms/reset_bar_code.py:120-121` - except Exception (in handleSubmit)
  - `browser/forms/user_setup.py:85-86` - except Exception (in handleSubmit)
- Current mitigation: Exceptions logged at debug level
- Recommendations: Catch specific exceptions (ValueError, AttributeError, etc.); add logging that doesn't leak secrets

**IP Address Extraction Relies on Unvalidated Headers:**
- Risk: `X-Forwarded-For` header can be spoofed by client; implementation acknowledges this (line 435 in `helpers.py`)
- Files: `helpers.py:433-459` - `extract_ip_address_from_request()`
- Current mitigation: Private IP addresses filtered; assumes one proxy
- Recommendations: Validate X-Forwarded-For against known proxy list; only trust reverse proxy in your control; consider IP allowlisting unreliable and secondary to other auth factors

**Secret Key Generation Not Cryptographically Sound:**
- Risk: Browser hash concatenation without separators creates potential collision space
- Files: `helpers.py:259` - `return "{0}{1}{2}".format(user_secret, browser_hash, ska_secret_key)` 
- Impact: If user_secret ends with same bytes browser_hash starts with, collision is possible
- Fix: Use `":".join()` or derive key with HKDF/PBKDF2

**Logging Includes Sensitive Data:**
- Risk: Username and auth state written to logs
- Files: `pas_plugin.py:90, 94-95` - logs include username and two-factor authentication enabled status
- Current mitigation: Lines are at debug level
- Recommendations: Hash usernames before logging; consider logging only success/failure without user context

**URL Generation for QR Codes:**
- Risk: QR code URL uses external service (chart.googleapis.com) with secret embedded
- Files: `helpers.py:107-123` - `get_barcode_image()` generates Google Charts URL with OTP secret
- Impact: Secret is transmitted to Google; MITM can intercept
- Fix: Generate QR code locally using qrcode library; only display image, don't transmit secret externally

## Performance Bottlenecks

**Linear Scan for IP Whitelisting:**
- Problem: Every login checks if client IP is in whitelist
- Files: `helpers.py:499-510` - `is_whitelisted_client()` creates list of IP networks, then checks membership
- Cause: `get_ip_ranges()` called per request; list comprehension in line 496
- Current capacity: Works fine with ~100 IPs; becomes slow with 1000+
- Improvement path: Cache `get_ip_ranges()` result in registry or memory (with TTL); pre-compile ranges at startup

**No Caching of User Properties:**
- Problem: Every helper function calls `user.getProperty()` without caching
- Files: Multiple calls in helpers.py (lines 138, 163, 252, 396)
- Cause: Each call traverses user object properties
- Improvement path: Cache user properties in request-local storage (use `getRequest()` cache); invalidate on user modification

## Fragile Areas

**Form URL Reconstruction:**
- Files: `browser/forms/token.py:56-59`, `browser/forms/reset_bar_code.py:61-65`
- Why fragile: Manually rebuilds request URL using `getURL()` + `QUERY_STRING`; if query parameters change structure, breaks
- Safe modification: Use Plone URL generation utilities; test with complex query strings including special characters
- Test coverage: No tests for query string reconstruction with non-ASCII or reserved characters

**Token Validation Flow Depends on Side Effects:**
- Files: `browser/forms/token.py:73-94`
- Why fragile: `extractData()` called before username extraction; if form schema changes, extraction may fail silently
- Safe modification: Add explicit username validation before token check; add debug logging
- Test coverage: test_pas_plugin.py has minimal coverage; no tests for invalid username scenarios

**Browser Hash-Based Security:**
- Files: `helpers.py:210-225`
- Why fragile: Browser detection via User-Agent is unreliable (can be spoofed); SHA1 is cryptographically weakened
- Safe modification: Treat browser hash as additional signal, not primary authentication; document limitations
- Test coverage: No tests for User-Agent parsing; no tests for hash collisions

**Email Sending with No Delivery Confirmation:**
- Files: `browser/forms/request_bar_code_reset.py:87-102`
- Why fragile: Email send failure may raise exception, but user doesn't know if email was queued; MailHost.send() behavior is unpredictable across Plone versions
- Safe modification: Add try-catch around send(); store request in user property if send fails; add resend mechanism
- Test coverage: Email sending is not tested

## Scaling Limits

**User Iteration for Bulk Operations:**
- Current capacity: Enabling/disabling 2FA for all users iterates through all users (no pagination)
- Limit: Will timeout with >10,000 users
- Scaling path: Implement async task queue (Celery/RQ) for bulk operations; add progress tracking

**Registry Lookups in Request Handler:**
- Current capacity: `get_app_settings()` called multiple times per request
- Limit: Registry queries can block under high concurrency
- Scaling path: Cache settings in memory with TTL; invalidate on control panel save

## Dependencies at Risk

**onetimepass==0.2.2 (Pinned):**
- Risk: Very old package (last release ~2014); may have security issues
- Current alternatives: `pyotp` is actively maintained; drop-in compatible
- Migration plan: Switch to `pyotp` (same API); update imports; test with existing secrets

**rebus==0.1 (Pinned):**
- Risk: Minimal package; only used for base32 encoding
- Current alternatives: `base64.b32encode()` from stdlib (Python 3), or keep external package
- Migration plan: Either add `base64` usage or upgrade to maintained fork; document why external dependency needed

**ska==1.7.5 (Pinned, at ceiling):**
- Risk: 1.7.5 is the **last release supporting Python 2.7** — pinned in `test-4.3.cfg`
  `[versions]`. There is no upgrade path while the package stays on 2.7: 1.8.x+ dropped the
  Python 2 classifiers and 1.11.x requires `setuptools>=61` (PEP 517), which cannot install
  under 2.7. `setup.py` still declares the loose `ska>=1.1`, so the buildout pin is the only
  thing preventing a broken install
- Current alternatives: None (custom signing not worth it)
- Migration plan: Unblocked only by the Python 3 migration; audit ska's signing behaviour
  for changes between 1.7.5 and current before lifting the pin

**py2-ipaddress>2.0.1:**
- Risk: Backport for Python 2; not needed for Python 3
- Current alternatives: `ipaddress` module in stdlib (Python 3+)
- Migration plan: Remove on Python 3 migration

## Missing Critical Features

**No Account Lockout:**
- Problem: No limit on failed 2FA attempts; brute force possible
- Blocks: Cannot claim security compliance for FIDO2 or similar standards
- Workaround: Implement at reverse proxy level (fail2ban)
- Fix scope: Add attempt counter to user profile; lock after N failed attempts; exponential backoff

**No Recovery Codes:**
- Problem: If user loses phone/app, must contact admin; no self-service recovery
- Blocks: Cannot meet common security requirements (HIPAA, SOC 2)
- Workaround: Users must request bar code reset via email
- Fix scope: Generate 10 single-use recovery codes during setup; store hashed; document in UI

**No Backup Authentication Methods:**
- Problem: Only supports TOTP; no U2F, WebAuthn, or backup phone
- Blocks: Accessibility compliance; users with lost devices can't log in
- Workaround: Admin can disable 2FA (if enabled)
- Fix scope: Add WebAuthn support; add SMS/email OTP as fallback

**No Session Expiry:**
- Problem: 2FA token valid indefinitely; no time limit enforced
- Blocks: Compliance with security best practices (tokens should expire)
- Current behavior: SKA library uses lifetime param (2 hours for bar code reset), but token validation has no expiry
- Fix scope: Store issue time with token; validate on submission

## Test Coverage Gaps

**2FA Authentication Bypass Scenarios:**
- What's not tested: Whitelisted IPs, disabled authentication plugin, form submission errors
- Files: `tests/test_pas_plugin.py`, `tests/test_security.py`
- Risk: Regression could allow bypass; no automated detection
- Priority: High (affects security)

**Email Functionality:**
- What's not tested: Email sending, SMTP errors, malformed addresses, bounced mail
- Files: `browser/forms/request_bar_code_reset.py`
- Risk: Users may think bar code reset request succeeded when email never arrives
- Priority: High (affects usability and recovery)

**Open Redirect Prevention:**
- What's not tested: Attacks via `next_url` parameter; cross-domain redirects
- Files: `browser/forms/token.py:112-113`
- Risk: Session hijacking via phishing link with embedded attacker domain
- Priority: Critical (security vulnerability)

**IP Whitelisting Edge Cases:**
- What's not tested: IPv6 addresses, malformed ranges, proxy chain behavior, VPN edge cases
- Files: `helpers.py:433-510`
- Risk: Whitelist bypass; incorrect blocking of legitimate users
- Priority: Medium

**Form Validation Edge Cases:**
- What's not tested: Non-ASCII characters in username, SQL injection in form fields, tokens with special characters
- Files: All form handlers in `browser/forms/`
- Risk: Injection attacks, encoding errors
- Priority: Medium

**Control Panel Bulk Operations:**
- What's not tested: Enabling/disabling 2FA for all users; operation with 1000+ users
- Files: `browser/controlpanel.py:109-118`
- Risk: Timeout; inconsistent state; no rollback
- Priority: Medium

---

*Concerns audit: 2026-07-28*
