# Technology Stack

**Analysis Date:** 2026-07-28

## Languages

**Primary:**
- Python 2.6/2.7 - Legacy support for Plone 4.x ecosystem

**Secondary:**
- ZCML - Zope configuration language used throughout
- JavaScript - Minimal client-side logic in `src/collective/googleauthenticator/browser/static/`
- HTML/TAL - Plone page templates for views

## Runtime

**Environment:**
- Zope application server
- Python 2.7+ (deprecated, legacy support)

**Package Manager:**
- setuptools - Primary package manager
- Buildout - Complex dependency and configuration management system (`buildout.cfg`)
- Lockfile: Buildout uses pinned versions in extended configs

## Frameworks

**Core:**
- Plone 4.3.x - CMS/portal framework
- Zope 2 - Application server and framework foundation
- Zope Component Architecture (ZCA) - Component framework for plugin registration
- Products.PluggableAuthService (PAS) - Authentication and authorization plugin system

**Forms & UI:**
- plone.directives.form (>=1.1) - Form framework via ZCML
- plone.app.registry - Control panel and registry for settings
- plone.autoform - Automatic form generation
- z3c.form - Advanced form framework
- Products.PageTemplates - Template engine for views

**Testing:**
- plone.app.testing - Plone testing infrastructure
- plone.app.robotframework - Robot Framework integration for browser automation
- plone.testing - Core Zope testing utilities

**Build/Dev:**
- plone.recipe.codeanalysis - Code quality analysis (flake8, PEP8)
- Sphinx - Documentation generation
- collective.recipe.omelette - Egg inspection tool

## Key Dependencies

**Critical:**
- plone.api (>=1.1.0) - Plone API for user/content management (`src/collective/googleauthenticator/helpers.py`, `src/collective/googleauthenticator/pas_plugin.py`)
- onetimepass (==0.2.2) - TOTP token generation and validation (`src/collective/googleauthenticator/helpers.py:205` via `valid_totp()`)
- ska (>=1.1) - Cryptographic URL signing for secure data passage (`src/collective/googleauthenticator/helpers.py:22`, `pas_plugin.py:144`)
- rebus (>=0.1) - Base32 encoding for secrets (`src/collective/googleauthenticator/helpers.py:100`)

**Infrastructure:**
- py2-ipaddress (>2.0.1) - IPv4/IPv6 address handling for IP whitelisting (`src/collective/googleauthenticator/helpers.py:459`)
- Products.PluggableAuthService - Plone authentication plugin architecture (`src/collective/googleauthenticator/__init__.py`)
- Products.CMFCore - Content management framework permissions
- Products.statusmessages - Status message system for user feedback
- zope.component - Component registry and utilities
- zope.i18n - Internationalization framework
- zope.i18nmessageid - Message factory for i18n
- zope.schema - Schema definition system
- zope.interface - Interface definitions and component contracts

## Configuration

**Environment:**
- Buildout configuration: `buildout.cfg` (extends plone.app.testing and QA configs)
- Application settings registry via plone.app.registry interface `IGoogleAuthenticatorSettings` (`src/collective/googleauthenticator/browser/controlpanel.py:24`)
- Settings stored in Plone's ZODB registry, not environment variables

**Build:**
- `setup.py` - Package definition and dependencies
- `buildout.cfg` - Buildout configuration with test runners, code analysis, documentation
- `setup.cfg` - isort configuration for import sorting (force_alphabetical_sort, force_single_line)
- Examples in `examples/simple/` with buildout configs for different Plone versions

## Configuration Settings

**Application Settings (stored in Plone registry):**
- `ska_secret_key` - Site-wide secret for URL signing (TextLine, required)
- `globally_enabled` - Force two-factor authentication for all users (Bool, default=True)
- `ip_addresses_whitelist` - CIDR/IP ranges to skip 2FA (Text, newline-separated)

## Platform Requirements

**Development:**
- Python 2.7+ (EOL - legacy codebase)
- setuptools for building
- Buildout for environment setup
- Plone 4.2.6 or higher
- Google Authenticator mobile app (iOS, Android, Blackberry, Windows Phone)

**Production:**
- Zope application server
- ZODB object database (included with Zope)
- Email server (implicit dependency for password reset emails)
- Python 2.7 runtime environment (legacy - no modern support)

---

*Stack analysis: 2026-07-28*
