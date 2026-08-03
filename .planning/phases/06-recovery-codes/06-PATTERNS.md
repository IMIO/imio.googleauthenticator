# Phase 6: Recovery Codes - Pattern Map

**Mapped:** 2026-08-03
**Files analyzed:** 8 (4 modified source, 4 modified test)
**Analogs found:** 8 / 8 (all in-file — no new files, no new file has zero analog)

RESEARCH.md's "Recommended Project Structure" already names every file this phase touches (no
new files at all — this maps each modified file to the *closest existing pattern within the
same or a sibling file* rather than to an external file, since most of the new code is added
to files that already contain the closest analog).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/imio/googleauthenticator/helpers.py` (+ `generate_recovery_codes`, `_hash_recovery_code`, `validate_recovery_code`, `validate_token_or_recovery_code`, `_is_recovery_code_shape`, `_normalize_recovery_code_input`) | service/utility | CRUD (hash generate/store) + request-response (validate/consume) | `generate_secret` (lines 185-198) for generation+store; `validate_token` (lines 375-450) for validate+consume-on-match; `validate_bar_code_reset_token` (lines 723-768) for constant-time compare | exact |
| `src/imio/googleauthenticator/browser/forms/token.py` (swap `validate_token` → `validate_token_or_recovery_code` at line 113) | controller/route (z3c.form) | request-response | itself, `handleSubmit` (lines 64-142) — one-line call-site swap only | exact |
| `src/imio/googleauthenticator/browser/forms/user_setup.py` (`generate_recovery_codes` call + `render()` override) | controller/route (z3c.form) | request-response, one-shot display | itself, `SetupForm.handleSubmit` (lines 56-116) for the write-after-validate shape; `plone.z3cform.layout.FormWrapper.update()` (pinned egg, `layout.py` lines 39-60) for the redirect-skip mechanism the `render()` override depends on | exact (mechanism verified against installed egg, not guessed) |
| `src/imio/googleauthenticator/profiles/default/memberdata_properties.xml` (+2 `<property>` entries) | config/migration | CRUD (schema declaration) | itself — 6 existing `<property>` entries, same file | exact |
| `src/imio/googleauthenticator/tests/test_helpers.py` (+ generation/hash/consume/regenerate unit tests) | test | CRUD / request-response | `test_seed_encryption_round_trip` (lines 259-311, ZODB-plaintext-absence pattern) + `test_new_memberdata_properties_round_trip` (lines 610-659, MFA-13 round-trip pattern) | exact |
| `src/imio/googleauthenticator/tests/test_token.py` | test | request-response | `TestTokenFormLockout`'s `_submit_token` Browser pattern (named in RESEARCH.md; not re-read here, reuse verbatim per RESEARCH.md's own note) | exact |
| `src/imio/googleauthenticator/tests/test_user_setup.py` | test | one-shot display | same-file existing `SetupForm` Browser tests (structure only, not separately excerpted — file's existing pattern is already the used analog per RESEARCH.md) | role-match |
| `src/imio/googleauthenticator/tests/test_pas_plugin.py` (extend `test_no_second_factor_state_written_from_the_plugin`'s tuples) | test | source-grep guard | itself, lines 348-414 (the exact function to extend, not merely a pattern to mimic) | exact |

**No upgrade step is needed or planned.** Checked: no `upgrades/` directory exists anywhere in
this package today (`find` came up empty); `profiles/default/metadata.xml` is version `1000`,
not `0301` as `CLAUDE.md` claims (that reference is stale). RESEARCH.md's own "Recommended
Project Structure" does not list an upgrade step for this phase either — the two new
`memberdata_properties.xml` entries are picked up by the existing GenericSetup profile import on
next `portal_setup` re-run, same mechanism Phase 5's three properties used, with no dedicated
upgrade step written for those either. Do not invent `upgrades/to0301.py`-shaped machinery for
this phase; there is no existing analog for it in this codebase and RESEARCH.md doesn't call for
one.

## Pattern Assignments

### `helpers.py` — generation half (`generate_recovery_codes`, hashing)

**Analog:** `generate_secret` (lines 185-198)

```python
def generate_secret(user):
    """
    Generates secret for the user. 160 bits of ``os.urandom``, stdlib
    base32-encoded -- the previous third-party encoder ASCII-decodes its
    input before encoding and rejects raw entropy.

    :param Products.PlonePAS.tools.memberdata user:
    """
    secret = base64.b32encode(os.urandom(20))
    # logger.debug(secret)
    ciphertext = encrypt_seed(secret)
    user.setMemberProperties(
        mapping={'two_factor_authentication_secret': ciphertext})
    return secret
```

**Pattern to copy:** single `os.urandom` → `base64.b32encode` → store call, one
`setMemberProperties` mapping, plaintext returned but never logged (the commented-out
`# logger.debug(secret)` is a deliberate marker in this codebase — never uncomment it, and never
add an equivalent for the recovery-code plaintext or the derived hash). `generate_recovery_codes`
extends this exact shape to 10 codes in one `setMemberProperties` call (both `_salt` and
`_hashes` keys in the same mapping, per RESEARCH.md's regeneration-invalidates-all requirement).

### `helpers.py` — validation + consume-on-match (`validate_recovery_code`)

**Analog:** `validate_token` (lines 375-450), specifically the shape check → secret fetch →
match → replay-style write pattern

```python
def validate_token(token, user=None):
    if user is None:
        user = api.user.get_current()

    if not _is_six_digit_token(token):
        return False

    secret = get_secret(user)
    if not secret:
        return False

    last_accepted_interval = int(
        user.getProperty('two_factor_authentication_last_interval') or 0)

    matched = _find_accepted_interval(token, secret)
    if matched is None:
        return False

    if matched <= last_accepted_interval:
        logger.info('TOTP replay rejected')
        return False

    user.setMemberProperties(
        mapping={'two_factor_authentication_last_interval': int(matched)})
    return True
```

**Pattern to copy:** every gate is `return False` before the next step (shape → stored-state
presence → match → replay-window check), and the state write (`setMemberProperties`) happens
only once, at the very end, only on the accept path, inside the helper — never in the caller.
`validate_recovery_code` mirrors this exactly: shape check (`_is_recovery_code_shape`) → stored
salt/hashes presence → `hmac.compare_digest` loop match → consume-on-match write (remove the
matched hash, `setMemberProperties` with the shortened tuple) — same "one write, on accept only,
inside the helper" discipline that makes MFA-12 hold.

### `helpers.py` — constant-time compare precedent

**Analog:** `validate_bar_code_reset_token` (lines 723-768)

```python
def validate_bar_code_reset_token(stored_token, submitted_token):
    if not stored_token or not submitted_token:
        return False
    try:
        if isinstance(stored_token, unicode):
            stored_token = stored_token.encode('ascii')
        if isinstance(submitted_token, unicode):
            submitted_token = submitted_token.encode('ascii')
    except UnicodeEncodeError:
        return False
    return compare_digest(stored_token, submitted_token)
```

**Pattern to copy:** `hmac.compare_digest` is already imported at the top of `helpers.py`
(`from hmac import compare_digest`, line 5) — reuse that import, do not add a second one. Empty
operand refuses before comparison. Same "do not log either operand" convention this function's
own docstring states applies verbatim to `validate_recovery_code` (never log the plaintext code,
the salt, or the computed hash — RESEARCH.md's threat-pattern table restates this explicitly).

### `browser/forms/token.py` — one-line dispatcher swap

**Analog:** itself, lines 108-118 (surrounding context for the one call site)

```python
if user is not None and is_account_locked(user):
    msg = _("Invalid token or token expired.")
    IStatusMessage(self.request).addStatusMessage(msg, 'error')
    return

valid_token = validate_token(token, user=user)      # <-- change to validate_token_or_recovery_code

if valid_token:
    if user is not None:
        reset_failed_second_factor(user)
    ...
else:
    if user is not None:
        register_failed_second_factor(user)
    msg = _("Invalid token or token expired.")
    IStatusMessage(self.request).addStatusMessage(msg, 'error')
```

**Pattern to copy:** literally nothing else in this file changes. `reset_failed_second_factor` /
`register_failed_second_factor` already wrap this one call site — RECOV-05 is satisfied by
changing only the right-hand side of line 113's assignment. Add the new import
(`validate_token_or_recovery_code`) alongside the existing `from imio.googleauthenticator.helpers
import ...` block (lines 18-24), same one-name-per-line style already used there.

### `browser/forms/user_setup.py` — write-after-validate + same-response render

**Analog:** itself, `SetupForm.handleSubmit` (lines 56-116) for where the new write lands;
`plone.z3cform.layout.FormWrapper.update()` (pinned egg) for why skipping the redirect is safe

```python
# Existing shape (user_setup.py, lines 93-103) — the write this phase's write follows:
if valid_token:
    try:
        user = api.user.get_current()
        user.setMemberProperties(mapping={'enable_two_factor_authentication': True,})
        IStatusMessage(self.request).addStatusMessage(
            _("Two-step verification is successfully enabled for your account."),
            'info')
        redirect_url = "{0}/@@personal-information".format(self.context.absolute_url())
    except Exception:
        logger.exception("Two-step verification setup failed")
        reason = _("An unexpected error occurred.")
```

```python
# Verified mechanism this override depends on — direct read of the pinned egg,
# /srv/cache/eggs/plone.z3cform-0.8.1-py2.7-linux-x86_64.egg/plone/z3cform/layout.py,
# FormWrapper.update(), lines 39-60:
#     z2.switch_on(self, request_layer=self.request_layer)
#     self.form_instance.update()
#     # If a form action redirected, don't render the wrapped form
#     if self.request.response.getStatus() in (302, 303):
#         self.contents = ""
#         return
#     self.contents = self.form_instance.render()
```

**Pattern to copy:** insert `self._recovery_codes = generate_recovery_codes(user)` immediately
after the existing `enable_two_factor_authentication` write, inside the same `try` block (so a
failure here hits the same `except Exception: logger.exception(...)` path, not a new one).
Deliberately skip the existing `self.request.response.redirect(redirect_url)` call on this one
success path only — `FormWrapper.update()` (verified above) only skips re-rendering on 302/303,
so omitting the redirect is sufficient for `render()` to run normally afterward in the same
response. Override `render()` to check the instance flag first, else fall through to
`super(SetupForm, self).render()` — exactly one new method, no new base class, no template file
beyond what RESEARCH.md's Pattern 1 already specifies.

### `profiles/default/memberdata_properties.xml`

**Analog:** itself — the file already has this exact shape for Phase 5's three properties

```xml
<?xml version="1.0"?>
<object name="portal_memberdata" meta_type="Plone Memberdata Tool">
  <property name="enable_two_factor_authentication" type="boolean">False</property>
  <property name="two_factor_authentication_secret" type="string"></property>
  <property name="bar_code_reset_token" type="string"></property>
  <property name="two_factor_authentication_failed_attempts" type="int">0</property>
  <property name="two_factor_authentication_locked_until" type="int">0</property>
  <property name="two_factor_authentication_last_interval" type="int">0</property>
</object>
```

**Pattern to copy:** append, in the same file, in the same flat list, no grouping/comment
needed (none of the existing six have one):

```xml
  <property name="two_factor_authentication_recovery_codes_salt" type="string"></property>
  <property name="two_factor_authentication_recovery_codes_hashes" type="lines"></property>
```

## Shared Patterns

### MFA-13: undeclared-property round trip test

**Source:** `tests/test_helpers.py::test_new_memberdata_properties_round_trip` (lines 610-659)
**Apply to:** any new `memberdata_properties.xml` entry — write one round-trip test per new
property in the same style: `setMemberProperties` then `getProperty`, asserting the exact type
and value, in the *same* test method as the declaration (this file's existing convention groups
all of a phase's new-property round trips into one method with a shared `setUp`/`tearDown` that
manages `helpers.ENV_VAR_NAME`, not one method per property).

### MFA-12: no second-factor state written from the plugin

**Source:** `tests/test_pas_plugin.py::test_no_second_factor_state_written_from_the_plugin`
(lines 348-414)
**Apply to:** the two new property names and three new helper function names this phase adds.
Extend the existing `property_names` and `helper_function_names` tuples (lines 378-391) in
place — do not write a parallel test. Per this codebase's own established discipline (quoted in
RESEARCH.md's Pitfall 4), deliberately introduce one of the forbidden names into `pas_plugin.py`
locally first and confirm the extended test catches it, before considering the guard done —
mirrors this test's own "positive controls" section (lines 403-414) which exists for exactly this
non-vacuity reason.

### Constant-time comparison

**Source:** `helpers.py:723-768` (`validate_bar_code_reset_token`), import already at
`helpers.py:5`
**Apply to:** `validate_recovery_code`'s hash-list comparison loop. Reuse the existing
`from hmac import compare_digest` import; do not add a second `import hmac`.

### ZODB plaintext-absence assertion

**Source:** `tests/test_helpers.py::test_seed_encryption_round_trip` (lines 259-311),
specifically `self.assertNotIn(seed, stored, 'SEC-01')` (line 279)
**Apply to:** a new test asserting the plaintext recovery codes never appear as a substring of
either stored memberdata property (`..._salt`, `..._hashes`) after `generate_recovery_codes` —
same `assertNotIn(plaintext_code, stored_value)` shape, one assertion per stored property, same
one-line docstring-tag convention (`'SEC-01'`-style) if this phase carries a REQUIREMENTS.md ID
to tag it with (RECOV-02).

## No Analog Found

None — every file this phase touches already has a same-file or same-repo analog of equal or
higher match quality; RESEARCH.md's own "Recommended Project Structure" and "Code Examples"
sections already verified every mechanism (the `plone.z3cform` redirect-skip, the
`MutablePropertySheet` silent-pop hazard, the PBKDF2/`compare_digest` stdlib availability)
against the actual installed eggs and interpreter this session, so nothing here is inferred from
outside the codebase.

## Metadata

**Analog search scope:** `src/imio/googleauthenticator/helpers.py`,
`src/imio/googleauthenticator/browser/forms/token.py`,
`src/imio/googleauthenticator/browser/forms/user_setup.py`,
`src/imio/googleauthenticator/profiles/default/memberdata_properties.xml`,
`src/imio/googleauthenticator/tests/test_helpers.py`,
`src/imio/googleauthenticator/tests/test_pas_plugin.py`, plus a confirmatory search for any
`upgrades/` directory or `to0301.py`-shaped file (none exists).
**Files scanned:** 8 source/test files fully or targeted-read; 1 negative-result search
(upgrade step machinery).
**Pattern extraction date:** 2026-08-03
