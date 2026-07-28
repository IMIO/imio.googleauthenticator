# Pitfalls Research

**Domain:** Renaming + hardening a forked Plone 4.3 / Zope 2 / Python 2.7 PAS add-on
**Researched:** 2026-07-28
**Confidence:** HIGH

## How this was verified

Almost every claim below was read out of the exact eggs this buildout pins, or reproduced
locally. Version map (from `/srv/cache/eggs`, Plone 4.3.20):

| Package | Version | Why it matters here |
|---|---|---|
| `Products.GenericSetup` | 1.8.11 | import-step ordering, `runImportStepFromProfile`, `post_handler` |
| `plone.registry` | 1.0.5 | `forInterface` / `registerInterface` semantics |
| `plone.app.registry` | 1.2.5 | `registry.xml` import handler |
| `Products.PluggableAuthService` | 1.11.3 | swallowed plugin exceptions, `_extractUserIds` |
| `Products.CMFQuickInstallerTool` | 3.0.16 | install path vs. site-creation path |
| `Products.CMFPlone` | 4.3.20 | `factory.addPloneSite` |
| `plone.testing` | 4.1.3 (pinned open) / 5.0.0 (blocked) | `TestIsolationBroken` guard |
| `plone.app.testing` | 4.2.7 | `applyProfile`, layer semantics |

Confidence tags: **HIGH** = read from the pinned source above or reproduced on this machine.
**MEDIUM** = official Plone 4.3 docs, or a sound inference from source I read.
**LOW** = plausible, not confirmed — treat as "check this", not "this is true".

---

## Critical Pitfalls

### Pitfall 1: Stale `.pyc` files keep `collective.googleauthenticator` importable after the move

**Confidence: HIGH — reproduced locally.**

**What goes wrong:**
`git mv src/collective src/imio` moves only *tracked* files. `.gitignore` line 1 is `*.py[cod]`,
so all 27 `.pyc` files stay behind in `src/collective/`, including
`src/collective/__init__.pyc` (the `declare_namespace` boilerplate). Python 2.7 imports an
orphan `.pyc` with no `.py` beside it. Reproduced with this buildout's own interpreter:

```
$ bin/python -c "import ns.sub; print(ns.sub.__file__)"   # only .pyc present
ORPHAN PYC IMPORT OK: from-pyc from ./ns/sub/__init__.pyc
```

Result: every dotted name you forget to rename — in `configure.zcml`, `registry.xml`,
`browserlayer.xml`, `componentregistry.xml`, `setuphandlers.py`'s profile id, `testing.py` —
keeps resolving against dead bytecode. `bin/test` is green. A fresh clone, CI, or production is
not. Worse: both namespaces can load at once (see Pitfall 2), and you get two ZCML
registrations for the same views.

**Why it happens:**
Everyone assumes "git moved it, it's moved". Nobody looks at ignored files. The current working
tree already has the full stale set — `git status --porcelain --ignored src` lists them today.

**How to avoid:**
Make the very first commit of the rename phase do the move *and* `git clean -xdf src/`, then
verify the old directory is gone from disk, not just from git. Add
`PYTHONDONTWRITEBYTECODE=1` to `[instance]` `environment-vars` and to `[testenv]` so this can
never re-accumulate.

**Warning signs:**
```bash
find src -name '*.pyc'                 # must be empty after the move
test ! -d src/collective               # must pass
git clean -xdn src                     # dry run: shows what git mv left behind
bin/python -c "import collective.googleauthenticator"   # must ImportError
```

**Phase to address:** Rename — first commit, before any other rename work.

---

### Pitfall 2: The stale `.egg-info` and `develop-eggs` egg-link keep the old distribution alive

**Confidence: HIGH — files inspected on disk.**

**What goes wrong:**
Two artefacts on disk right now name the old package:

- `src/collective.googleauthenticator.egg-info/` (git-ignored) — contains
  `top_level.txt` = `collective`, `namespace_packages.txt` = `collective`, and an
  `entry_points.txt` declaring `[z3c.autoinclude.plugin] target = plone`.
- `develop-eggs/collective.googleauthenticator.egg-link` → `/srv/src/imio.googleauthenticator/src`.

Re-running buildout after the rename **adds** `imio.googleauthenticator.egg-link` and
`src/imio.googleauthenticator.egg-info/`; it does not remove the old ones. `pkg_resources` then
sees two distributions pointing at the same `src/` tree, and `z3c.autoinclude` walks the
`plone` entry point of *both* — so it loads `collective.googleauthenticator`'s ZCML too,
resolving it against the stale `.pyc` from Pitfall 1.

**Why it happens:**
`cleanup.sh` hardcodes `rm src/collective.googleauthenticator.egg-info -rf` and will silently
stop doing anything useful. Buildout never garbage-collects `develop-eggs/`.

**How to avoid:**
In the rename commit: delete both artefacts, update `cleanup.sh`, and re-run
`bin/buildout -N`. Then assert only one egg-link exists.

**Warning signs:**
```bash
ls develop-eggs/ | grep googleauthenticator     # exactly one line, imio.*
ls -d src/*.egg-info                            # exactly one, imio.*
```
Loud secondary detector, and a good one: `__init__.py:initialize()` calls
`registerMultiPlugin(GoogleAuthenticatorPlugin.meta_type)`, and PAS 1.11.3 raises
`RuntimeError('Meta-type (%s) already available to Add List')` on a duplicate. If both the old
and new package initialize, **Zope refuses to start** with that RuntimeError. Treat that
traceback as "you have a stale egg-info/pyc", not as a bug in the rename.

**Phase to address:** Rename.

---

### Pitfall 3: Existing ZODBs silently downgrade to password-only login

**Confidence: HIGH — mechanism is standard ZODB `OFS.Uninstalled.Broken` behaviour; the
affected persistent objects were enumerated from the profiles and setup handler.**

**What goes wrong:**
PROJECT.md correctly says "not deployed yet, no enrolled users, no upgrade steps". That is true
for *users* and false for *databases*. Four kinds of persistent object in any existing
`var/filestorage/Data.fs` — every developer's local DB, any restored staging DB, any
`bin/instance debug` sandbox — pickle the old module path:

| Persistent object | Where | What happens after the rename |
|---|---|---|
| `GoogleAuthenticatorPlugin` instance | `acl_users/google_auth` | Unpickles as `OFS.Uninstalled.Broken`. It no longer provides `IAuthenticationPlugin`, so `plugins.listPlugins(IAuthenticationPlugin)` skips it. **2FA stops running. No error page. Users log in with password only.** |
| `UserDataSchemaProvider` utility | local site manager, from `componentregistry.xml` | Broken utility; the enhanced user-data panel silently loses the 2FA checkbox |
| `IGoogleAuthenticatorLayer` browser layer | `plone.browserlayer` registry, from `browserlayer.xml` | Layer interface unresolvable; layer-bound views 404 |
| Registry records | `portal_registry`, keyed `collective.googleauthenticator.browser.controlpanel.IGoogleAuthenticatorSettings.*` | Orphaned. Invisible to the renamed control panel, still exported by `portal_setup` snapshots forever |

This is the single most dangerous silent failure in the milestone: a security control that
disappears without raising anything.

**Why it happens:**
"Not deployed" is read as "no persistence anywhere". `plone.app.testing` builds a fresh
`DemoStorage` on every run, so the test suite can never reproduce it.

**How to avoid:**
Declare in the rename phase that existing ZODBs are **discarded, not migrated**: `make cleanall`
(or delete `var/filestorage`, `var/blobstorage`), recreate the Plone site, re-run the profile.
Say so in CHANGES.txt so nobody tries to carry a DB forward. Do not write a `zodbupdate` rename
map — nothing of value is in those DBs.

**Warning signs:**
After the rename, on any DB you did not just create:
```python
# bin/instance debug
app.Plone.acl_users.google_auth.__class__          # must NOT be OFS.Uninstalled.Broken
app.Plone.acl_users.plugins.listPlugins(IAuthenticationPlugin)   # must include google_auth
sorted(k for k in app.Plone.portal_registry.records.keys() if 'googleauthenticator' in k)
```
That last line is also the orphan-record check: no key may start with `collective.`.

**Phase to address:** Rename. Add the plugin-is-active check as a permanent test (see
Pitfall 18) so it can never regress silently again.

---

### Pitfall 4: PAS swallows your plugin's exceptions — every bug becomes a 2FA bypass

**Confidence: HIGH — source read + official Plone 4.3 docs page "PAS eats exceptions".**

**What goes wrong:**
`Products/PluggableAuthService/PluggableAuthService.py`:

```python
_SWALLOWABLE_PLUGIN_EXCEPTIONS = (NameError, AttributeError, KeyError, TypeError, ValueError)
```

and in `_extractUserIds` (line ~648):

```python
for authenticator_id, auth in authenticators:
    try:
        uid_and_info = auth.authenticateCredentials(credentials)
        ...
    except _SWALLOWABLE_PLUGIN_EXCEPTIONS:
        reraise(auth)
        logger.debug('AuthenticationPlugin %s error' % authenticator_id, exc_info=True)
        continue
```

`logger.debug` is invisible at Plone's default log level. `continue` moves on to the next
authenticator — `source_users` — which happily authenticates on password alone. So **any**
`ValueError`, `TypeError`, `KeyError`, `AttributeError` or `NameError` anywhere in
`authenticateCredentials` silently disables the second factor.

This is not hypothetical for the milestone. Every one of these produces a swallowable exception:

- `os.getenv('IMIO_GA_SEED_KEY')` returns `None` → `Fernet(None)` → `TypeError`/`AttributeError`
- key present but wrong length/not base64 → `Fernet(key)` raises `ValueError:
  Fernet key must be 32 url-safe base64-encoded bytes.`
- decrypting a py2 `base64` seed with a bad key → `binascii.Error` (a plain `Exception` in
  Python 2) or `TypeError` from `b64decode`
- the existing `UnboundLocalError` at `user_setup.py:96` — `UnboundLocalError` **is** a
  `NameError` subclass, so it is swallowed
- a lockout/replay counter read from a memberdata property that does not exist yet → `KeyError`

**Why it happens:**
The plugin's contract is "return `None` if not competent". PAS cannot distinguish "not
competent" from "crashed", so it treats a crash as "not competent". `reraise(auth)` is the
opt-out and nobody knows it exists.

**How to avoid:**
One line on the plugin class, and it is the highest value-per-character change in the whole
milestone:

```python
class GoogleAuthenticatorPlugin(BasePlugin):
    _dont_swallow_my_exceptions = True    # PAS reraise() honours this
```

Then make the fail-closed behaviour explicit rather than accidental: if the seed cannot be
decrypted for a user whose `enable_two_factor_authentication` is True, **deny** (return `None`
*after* consuming credentials, or raise) — never fall through to password-only. Also raise the
plugin's own logging from `debug` to `error` for the failure paths (`pas_plugin.py:90,94`
currently log at debug, and per CONCERNS.md leak the username — log the failure, not the user).

**Warning signs:**
- A test that sets the key env var to garbage and asserts the login is **refused**, not granted.
- A test that unsets the key entirely and asserts the same.
- `grep -n "except Exception" src/imio/googleauthenticator/helpers.py` — the six bare handlers
  CONCERNS.md lists (`helpers.py:223,412,429,481`, `reset_bar_code.py:120`,
  `user_setup.py:85`) are the same failure mode one level down: they convert a crash into a
  falsy return.

**Phase to address:** Land `_dont_swallow_my_exceptions = True` **before** the encryption phase
— ideally in the rename phase, as a one-line commit. It converts every later phase's mistakes
from silent bypasses into 500s.

---

### Pitfall 5: The i18n domain rename silently deletes all translations

**Confidence: HIGH — `configure.zcml` uses `<i18n:registerTranslations directory="locales" />`,
whose domain comes from the *filenames* under `locales/`, not from `i18n_domain`.**

**What goes wrong:**
`zope.i18n`'s `registerTranslations` walks `locales/<lang>/LC_MESSAGES/<domain>.po` and derives
the domain from the **file name**. Renaming `MessageFactory('collective.googleauthenticator')`
to `MessageFactory('imio.googleauthenticator')` in the eleven modules that declare it, and the
`i18n_domain=` / `i18n:domain=` attributes in five ZCML/XML files, without renaming

- `locales/collective.googleauthenticator.pot`
- `locales/nl/LC_MESSAGES/collective.googleauthenticator.po`
- `locales/nl/LC_MESSAGES/collective.googleauthenticator.mo` (git-ignored build artefact)
- `I18NDOMAIN=` in `src/.../rebuild_i18n.sh`

leaves a registered `collective.googleauthenticator` domain that nothing looks up, and an
`imio.googleauthenticator` domain with zero messages. Every label falls back to its English
msgid. Nothing errors. The Dutch translation is simply gone, and nobody notices until a Dutch
user complains.

**Why it happens:**
`i18n_domain` in ZCML looks like the authoritative declaration. It is not — it only supplies
the default domain for message ids *declared in that ZCML file*.

**How to avoid:**
Rename the three `locales/` files with `git mv` in the same commit as the `MessageFactory`
change, delete the ignored `.mo`, update `rebuild_i18n.sh`, and let
`zope_i18n_compile_mo_files = true` (already set in `base.cfg` `[testenv]`) regenerate it.

**Warning signs:**
```bash
ls src/imio/googleauthenticator/locales/                      # imio.googleauthenticator.pot only
find src -name 'collective.googleauthenticator.*'             # must be empty
git grep -c "collective" src/ | wc -l                         # must be 0
```
Runtime check: `bin/code-analysis-find-untranslated` is already wired into `bin/code-analysis`.
Also load the control panel with `?set_language=nl` and confirm labels are Dutch.

**Phase to address:** Rename.

---

### Pitfall 6: GenericSetup import-step order is unspecified — and the rename changes it

**Confidence: HIGH — read from `Products/GenericSetup/tool.py:269-276` and
`utils.py:856-905`.**

**What goes wrong:**
This is the actual root cause of `IGoogleAuthenticatorSettings defines a field ska_secret_key,
for which there is no record`. The chain:

1. `configure.zcml` registers the custom step with **no dependencies**:
   ```xml
   <genericsetup:importStep name="collective.googleauthenticator"
       handler="collective.googleauthenticator.setuphandlers.setupVarious" />
   ```
2. `SetupTool.getSortedImportSteps()` (tool.py:269) builds a **Python 2 `set`** of step ids and
   hands it to `_computeTopologicalSort`:
   ```python
   steps = set(_import_step_registry.listSteps())
   steps.update(set(self._import_registry.listSteps()))
   return tuple(_computeTopologicalSort([self.getImportStepMetadata(s) for s in steps]))
   ```
3. `_computeTopologicalSort` (utils.py:856) only orders steps that *declare* dependencies. For a
   dependency-free step it does `result.insert(after + 1, node)` in whatever order the set
   yields — i.e. **CPython 2.7 string-hash order**.

So whether `collective.googleauthenticator` runs before or after `plone.app.registry` (which
does declare `<depends name="componentregistry"/>` and `<depends name="toolset"/>`) is an
accident of string hashing over the whole set of registered step ids.

Two consequences the roadmap must plan around:

- **Renaming the step id from `collective.googleauthenticator` to `imio.googleauthenticator`
  changes its hash and can silently flip the ordering.** If the error disappears after the
  rename, that is *not* evidence the bug is fixed. It will come back when any other add-on adds
  or removes an import step, i.e. the first time this is deployed next to `imio.dms.mail`.
- The site-creation-vs-add-on-install asymmetry is consistent with this: the two paths reach
  `_runImportStepsFromContext` with a different persistent `_import_registry`
  (`applyContext` populates it from each profile's `import_steps.xml` as it goes), so the set
  contents — and therefore the order — differ. **MEDIUM confidence on that specific
  explanation**; see "Warning signs" for how to settle it in one command instead of guessing.

**Why it happens:**
The upstream author hit the ordering problem, and instead of declaring the dependency, worked
around it by re-running the registry step from inside the handler (Pitfall 7). The workaround
hides the cause.

**How to avoid:**
Declare the dependency. GenericSetup 1.8.11's `importStep` directive supports it
(`IImportStepDependsDirective`, zcml.py:167):

```xml
<genericsetup:importStep
    name="imio.googleauthenticator"
    title="imio.googleauthenticator install steps"
    description=""
    handler="imio.googleauthenticator.setuphandlers.setupVarious">
  <depends name="plone.app.registry"/>
</genericsetup:importStep>
```

**Warning signs:**
Do not guess the order — print it. In `bin/instance debug` or a test:
```python
steps = portal.portal_setup.getSortedImportSteps()
steps.index('imio.googleauthenticator') > steps.index('plone.app.registry')   # must be True
```
Make that an assertion in the test suite. It costs two lines and it is the only thing that will
catch a re-flip when a new add-on lands in the same buildout.

**Phase to address:** Registry fix.

---

### Pitfall 7: `runImportStepFromProfile` from inside an import step is not re-entrant

**Confidence: HIGH for the mechanisms below (source read); MEDIUM for which one fires in this
specific site-creation path.**

**What goes wrong:**
`setuphandlers._setup_secret_key` does this from inside `setupVarious`:

```python
portal.portal_setup.runImportStepFromProfile(
    'profile-collective.googleauthenticator:default', 'plone.app.registry')
settings = get_app_settings()          # -> registry.forInterface(..., check=True)
```

Reading `tool.py:329-371`, that call is doing four things you did not ask for:

1. **`self.applyContext(context)`** — mutates the tool's *persistent* import and export step
   registries from the nested profile directory, in the middle of an in-progress import
   (`_updateImportStepsRegistry`, tool.py:1217). Harmless here only because our profile has no
   `import_steps.xml`.
2. **`run_dependencies=True` (the default)** re-runs `plone.app.registry`'s declared
   dependencies — `componentregistry` and `toolset` — **against our profile's context**. Our
   `profiles/default/componentregistry.xml` registers the `IUserDataSchemaProvider` utility, so
   that utility gets registered here and then registered *again* when the outer loop reaches
   `componentregistry` normally.
3. **It fires `BeforeProfileImportEvent` / `ProfileImportedEvent`** for a fake nested "profile
   import". Both GenericSetup's and QuickInstaller's handlers guard on
   `event.full_import`, and `full_import = (set(steps) == set(self.getSortedImportSteps()))`
   is False for a 3-step run, so this one is benign — today. It stops being benign the moment
   anything subscribes to those events without the `full_import` guard.
4. **The registry import can silently do nothing.** `plone/app/registry/exportimport/handler.py:61`:
   ```python
   def importRegistry(context):
       registry = queryUtility(IRegistry)
       if registry is None:
           logger.info("Cannot find registry")
           return
   ```
   `queryUtility`, not `getUtility`. If the local site is not set or `portal_registry` is not
   yet registered as the `IRegistry` utility at that moment, the step **logs at INFO and
   returns**, creating no records — and then `get_app_settings()` two lines later raises the
   `KeyError` you see. This is the silent-failure shape that matches the reported symptom
   exactly.

**Why it happens:**
It looks like "just run that one step early". It is actually a nested re-entry into the import
machinery with a different context, a different purge policy
(`should_purge = (info.get('type') != EXTENSION)` → `False` for our profile), and its own event
storm.

**How to avoid — in order of laziness:**

1. **Best: don't read the registry from an import step at all.** The only reason
   `setupVarious` touches the registry is to seed `ska_secret_key` with a UUID. Move that to a
   lazy accessor — `get_ska_secret_key()` mints and stores the key on first use if it is empty.
   Zero GenericSetup involvement, works on every install path, works on a site created before
   the add-on existed, and needs no ordering guarantee. This also removes the `_setup_secret_key`
   function entirely.
2. **If it must happen at install time: use a profile `post_handler`.** GenericSetup 1.8.11
   supports it (`zcml.py:76`, `registry.py:718`), and `_runImportStepsFromContext` runs it after
   *all* steps of the profile (tool.py, right after the step loop). Official Plone 4.3
   GenericSetup docs recommend `pre_handler`/`post_handler` for exactly this
   (GenericSetup ≥ 1.8.2). Note the handler receives the **setup tool**, not an import context:
   ```xml
   <genericsetup:registerProfile name="default" directory="profiles/default"
       provides="Products.GenericSetup.interfaces.EXTENSION"
       post_handler=".setuphandlers.post_install" />
   ```
   ```python
   def post_install(setup_tool):        # NOT a DirectoryImportContext
       portal = setup_tool.aq_parent    # no readDataFile(), no marker file needed
   ```
   Caveat: `post_handler` is **not** run by `runImportStepFromProfile` nor by upgrade steps.
3. **Keep the custom step but declare `<depends name="plone.app.registry"/>`** (Pitfall 6) and
   delete the nested `runImportStepFromProfile` call.

Also worth knowing: `forInterface(interface, check=False)` and `omit=(...)` exist
(`plone/registry/registry.py:63`) and are the documented escape hatch — but using
`check=False` in `get_app_settings()` converts the loud `KeyError` into `AttributeError` at the
first attribute access, deeper in the stack. Do not use it to paper over the ordering bug.

**Warning signs:**
```bash
grep -rn "runImportStepFromProfile" src/            # should be zero hits after the fix
```
And grep the instance log for the silent path: `grep "Cannot find registry" var/log/instance.log`.

**Phase to address:** Registry fix. Recommend option 1 (lazy accessor) plus the
`<depends>` declaration as belt-and-braces.

---

### Pitfall 8: `<records interface="..."/>` looks unconditional but has three silent holes

**Confidence: HIGH — `plone/registry/registry.py:87-127` and
`plone/app/registry/exportimport/handler.py:292-334`.**

**What goes wrong:**
A bare `<records interface="..." />` is the correct and sufficient idiom **for this schema** —
`IGoogleAuthenticatorSettings` has only `TextLine`, `Bool` and `Text`, all of which have
`IPersistentField` adapters. It calls `registry.registerInterface(interface, omit, prefix)`,
which creates one record per field with the field's `default`. No `<value>` nodes needed.

But `registerInterface` and `forInterface` **do not iterate the same field set**, and that
asymmetry is a trap:

```python
# registerInterface (registry.py:94)
for name, field in getFieldsInOrder(interface):
    if name in omit or field.readonly:      # <-- readonly fields get NO record
        continue
    persistent_field = queryAdapter(field, IPersistentField)
    if persistent_field is None:
        raise TypeError("There is no persistent field equivalent for the field ...")
```
```python
# forInterface (registry.py:71)
for name in getFieldNames(interface):        # <-- includes readonly fields
    if name not in omit and prefix + name not in self:
        raise KeyError("Interface `%s` defines a field `%s`, for which there is no record.")
```

Three holes:

1. **A `readonly=True` field is never registered but is always checked** → `forInterface()`
   raises forever, on every install path, and no amount of re-running the profile fixes it. The
   only cure is `omit=('thatfield',)` at *both* ends.
2. **A field with no `IPersistentField` adapter aborts the whole `<records>` element** with
   `TypeError`. Supported: `TextLine`, `Text`, `Bool`, `Int`, `Float`, `ASCIILine`, `Password`,
   `URI`, `Datetime`, `Choice` (via `vocabularyName`), `List`/`Tuple`/`Set`/`Dict` of those.
   Not supported: `schema.Object`, `plone.namedfile` fields, a `Choice` bound to an
   `IContextSourceBinder`, and any custom field. Relevant if the encryption or lockout phase
   adds settings — keep new registry fields to the simple types.
3. **Re-running the profile silently resets values that no longer validate**
   (registry.py:113-121): the existing value is retained, then `bound_field.validate(value)` is
   run inside a bare `except:` and on failure the value is replaced by the field default. So
   tightening a field (adding `required=True`, narrowing a `Choice`) silently wipes the
   configured value on the next profile run. For `ska_secret_key` that means **the site secret
   can be reset to `u''`, invalidating every in-flight signed URL**, with only an INFO log line.

**Why it happens:**
`<records interface="..."/>` reads as a declaration of "these records exist". It is actually a
call to a function with quiet edge cases.

**How to avoid:**
Keep the schema to persistable, non-readonly, simple fields. Never change a field's
`required`/constraint without an explicit upgrade step. Do not put the encryption key or any
secret-adjacent value in the registry at all (see Pitfall 13).

**Warning signs:**
A test that runs the profile twice and asserts `ska_secret_key` is unchanged the second time.
That single test catches hole 3 and, in passing, proves the install is idempotent.

**Phase to address:** Registry fix; re-check in the encryption phase if it adds settings.

---

### Pitfall 9: Deleting the skins layer also deletes two templates the code still traverses to

**Confidence: HIGH — the skins directory contains four files and two of them are live
dependencies, reached by name via `restrictedTraverse`.**

**What goes wrong:**
`skins/googleauthenticator_custom/` holds:

| File | Role |
|---|---|
| `login_form.cpt` (+ `.metadata`) | the actual override — a stock Plone 4.3 copy, the thing to delete |
| `control_panel_extra.html` | **live**: `controlpanel.py:84` `self.context.restrictedTraverse('control_panel_extra')` |
| `request_bar_code_reset_email.pt` | **live**: `request_bar_code_reset.py:90` `self.context.restrictedTraverse('request_bar_code_reset_email')` |

Both are reachable *only* because `skins.xml` inserts `googleauthenticator_custom` into the skin
path. Remove the skin layer and:

- the control panel raises `AttributeError` inside `render()` → 500 on
  `@@google-authenticator-settings`
- the bar-code reset email raises `AttributeError` — and it is inside a
  `try: ... except SMTPRecipientsRefused` block, so it is *not* caught there, but per
  CONCERNS.md the email path has **zero test coverage**, so CI will not notice. The reset flow
  is the only recovery route users have today.

**Why it happens:**
"Delete the skin/resource overrides" is one line in PROJECT.md, and three of the four files in
the skins directory are not overrides at all.

**How to avoid:**
In the same commit that removes the skin layer, convert both templates to
`ViewPageTemplateFile` on the existing browser views and reference them as attributes, not by
`restrictedTraverse`. Delete only `login_form.cpt` and its `.metadata`. Then remove
`skins.xml`, `profiles/uninstall/skins.xml`, the `<cmf:registerDirectory>` in
`configure.zcml`, the `skins/` directory, and the `MANIFEST.in` line for it.

**Warning signs:**
```bash
grep -rn "restrictedTraverse" src/            # must be zero hits after the rework
```
Plus a test that renders `@@google-authenticator-settings` and asserts 200 **and** that the
"Enable two-step verification for all users" link is present (the current
`test_control_panel_view` only checks the status code, so it would pass with the extra
template silently missing — the `render()` concatenation happens *after* `super().render()`).

**Phase to address:** Challenge rework.

---

### Pitfall 10: `remove="True"` in a resource registry is permanent, and the winner depends on install order

**Confidence: HIGH — `jsregistry.xml` inspected; `profiles/uninstall/` contains only
`skins.xml`.**

**What goes wrong:**
`profiles/default/jsregistry.xml` line 21 does:
```xml
<javascript id="popupforms.js" remove="True" enabled="False" />
```
This is not a scoped override — it deletes Plone's own `popupforms.js` from
`portal_javascripts` for the whole site, persistently. `profiles/uninstall/` has no
`jsregistry.xml`, so **uninstalling the add-on leaves stock Plone permanently without
`popupforms.js`**: all the other AJAX overlays (contact form, folder contents, etc.) quietly
stop being overlays.

And per PROJECT.md the collision is live: `imio.dms.mail`'s `jsregistry.xml:102` re-registers
`popupforms.js`. Since resource registries are plain persistent lists mutated by whichever
profile is applied last, the outcome flips depending on install order — and flips again on any
reinstall or profile re-run of either add-on. Neither product errors. You find out because 2FA
works on one site and not another.

**Why it happens:**
Resource-registry XML has no notion of "scoped to my add-on". `remove="True"` is a global
mutation.

**How to avoid:**
Stop touching `popupforms.js`. The only functional change in the 197-line copy is the commented
out login-overlay binding at line ~60. Replace the whole override with a few lines in the
existing `main.js` (already registered as
`++resource++imio.googleauthenticator/main.js`) that unbind the login overlay after
`popupforms.js` has bound it — registered `insert-after="popupforms.js"`. Then delete
`browser/static/plone_ecmascript/popupforms.js`, both `<javascript>` entries for it, and the
`remove="True"` line.

Whatever the chosen mechanism, add the reverse operations to `profiles/uninstall/`
(`jsregistry.xml` + `cssregistry.xml` removing your own ids) — the uninstall profile is
currently a one-file stub and will otherwise leave debris on every site this ever touches.

**Warning signs:**
```python
# after applying the profile, in a test:
ids = portal.portal_javascripts.getResourceIds()
assert 'popupforms.js' in ids                                  # we must not remove Plone's
assert '++resource++imio.googleauthenticator/main.js' in ids
```
Manually: `@@resourceregistries-controlpanel`, or apply this profile and `imio.dms.mail`'s in
both orders and diff `getResourceIds()`.

**Phase to address:** Challenge rework.

---

### Pitfall 11: Redirecting from inside `authenticateCredentials` — the six traps

**Confidence: HIGH for the mechanisms (PAS 1.11.3 `_extractUserIds` read in full); MEDIUM for
the overlay behaviour, which depends on `plone.app.jquery`'s `prepOverlay`.**

**What goes wrong:** the current design (`pas_plugin.py:139-155`) already performs the
challenge from the plugin. Removing the skin overrides exposes what the overrides were hiding.

1. **The AJAX login overlay swallows the 302.** `popupforms.js` binds
   `prepOverlay({subtype:'ajax', formselector:'form#login_form', noform:'reload'})` to the
   login links. The form is submitted by XHR; jQuery follows the 302 transparently and the
   token form's HTML is injected into the overlay — or discarded, because `formselector` finds
   no `form#login_form` in it. Either way the user never reaches the token form. This is the
   *entire* reason both overrides exist. If you delete them without an alternative, 2FA breaks
   for anyone logging in via the personal-tools link (the normal path). **Verify by clicking
   the header "Log in" link, not by POSTing to `login_form` directly** — a testbrowser test
   POSTs directly and will pass while the real UI is broken.

2. **`response.redirect(url, lock=1)` is load-bearing.** Without `lock=1`, Plone's own
   post-login machinery (`logged_in` → `login_success`, `CookieAuthHelper.challenge` →
   `require_login`) calls `redirect()` again and wins. Keep the lock. Note the flip side: with
   the lock set, a genuine later redirect (e.g. an error page) is also suppressed.

3. **`setCookie('__ac', '', path='/')` must match the path the cookie was set with.** Plone's
   `credentials_cookie_auth` and `plone.session` set `__ac` at `path='/'`, so this works — but
   if the site is served under a VirtualHost path prefix, an expiry at a different path leaves
   the original cookie alive and **every subsequent request re-enters
   `authenticateCredentials`, re-issues the redirect, and you get an infinite redirect loop**.
   Symptom: browser reports "too many redirects" on `@@google-authenticator-token`. Prefer the
   PAS-native `ICredentialsResetPlugin` path (`resetCredentials`) over hand-rolled
   `setCookie`, and assert in a test that after the challenge the response carries no valid
   `__ac`.

4. **Credential consumption is a shared-dict side effect.** The plugin empties the
   `credentials` dict so later `IAuthenticationPlugin`s cannot authenticate. That works because
   PAS passes *the same dict* to every authenticator in the loop — and later plugins then raise
   `KeyError` on `credentials['login']`, which PAS swallows (Pitfall 4). It is load-bearing and
   extremely easy to break: if you set `_dont_swallow_my_exceptions = True` on **your** plugin
   that is fine (the flag is per-plugin, checked via `reraise(auth)`), but do not set it
   globally or on `source_users`. Also note the plugin must stay **first** in the
   `IAuthenticationPlugin` list — `setuphandlers._add_plugin` achieves this with
   `movePluginsDown(interface, all_but_last)`; if that line is refactored, ordering silently
   breaks and `source_users` authenticates before you get a say.

5. **PAS caches `_extractUserIds`.** Before the authenticator loop, PAS does
   `self.ZCacheable_get(view_name='_extractUserIds', keywords=createKeywords(**credentials))`.
   Plone 4.3 does not associate a cache manager with `acl_users` by default, so this returns
   `None` — but if anyone ever does, the redirect side effect happens only on a cache miss and
   the second login attempt is served from cache: **cached 2FA bypass**. Never put
   request-visible side effects in `authenticateCredentials` without knowing this. Low
   likelihood, catastrophic impact — worth a one-line comment in the code.

6. **`IChallengePlugin` is the wrong hook, despite the name.** `PluggableAuthService.challenge()`
   is only reached from `_unauthorized()`, i.e. when something raised `Unauthorized`. After a
   correct password the user *is* authorized, so `challenge()` never fires and a second factor
   implemented there would never run. Additionally `challenge()` only lets challengers of one
   protocol fire (`if protocol is None or protocol == challenger_protocol`) and short-circuits
   on `resp._has_challenged`. Stay in `authenticateCredentials`.

7. **`came_from` becomes `next_url`, unvalidated.** `pas_plugin.py:151` appends
   `&next_url={came_from}` from `ICameFrom`, which `adapter.py` derives from the HTTP
   `Referer`. `token.py:112-113` then redirects to it. That is the open redirect in
   CONCERNS.md. It also breaks on `+` and other reserved characters (the FIXME at
   `helpers.py:310`), because the value is concatenated into a query string rather than
   URL-encoded. Fix both together: `urlencode` on the way in, and on the way out accept only
   paths within the portal (`plone.api.portal.get().absolute_url()` prefix, or reduce to a
   relative path).

**Phase to address:** Challenge rework, with trap 7 folded into the existing "fix open
redirect" requirement.

---

### Pitfall 12: The encryption key is invisible to `bin/test`, `bin/zopepy`, and any client whose `port.cfg` fragment is missing

**Confidence: HIGH for the buildout mechanics (`base.cfg` inspected: `[instance]` has
`environment-vars`, `[test]` uses a separate `environment = testenv` section).**

**What goes wrong:**
`environment-vars` in `[instance]` lands in `parts/instance/etc/zope.conf` and is applied by
`zopectl`/`runzope` at process start. It is **not** shared with:

| Runner | Gets the env var? | Consequence |
|---|---|---|
| `bin/instance fg` / `start` | yes | production behaviour |
| `bin/instance debug` / `run` | yes (same zope.conf) | |
| **`bin/test`** | **no** — `[test]` uses `environment = testenv` | tests exercise the no-key path unless you add it there |
| **`bin/zopepy`, `bin/coverage run bin/test`** | **no** | ditto |
| CI (`package-test-legacy.yml`) | **no** unless the workflow sets it | |
| A second ZEO client whose Puppet fragment did not land | **no** | half of all logins fail |

So the default developer/CI experience is "key absent". Combined with Pitfall 4, that means the
tests will happily run the code path where the plugin crashes and PAS falls through to
password-only — and pass.

The ZEO case is the operational one: the ciphertext lives in the shared ZODB, the key lives in
each client's process environment. One client with a stale or missing `port.cfg` fragment
produces `InvalidToken` for every 2FA user, non-deterministically, depending on which client the
load balancer picked. There is no ZODB-side evidence.

**Why it happens:**
"Set the env var" feels like one change. It is at least four: `[instance]`, `[testenv]`, the CI
workflow, and the Puppet `concat::fragment` in the separate `industrialisation` repo (PROJECT.md
already flags that last one as an out-of-repo dependency — good).

**How to avoid:**
- Add the key to `[testenv]` in `base.cfg` with a fixed, obviously-fake test value, and to the CI
  workflow. Then add a test that *unsets* it and asserts login is **refused**.
- Read the key through one function, never `os.getenv()` at module scope: module-scope
  `getenv` freezes the value at import time, before `zope.conf`'s environment is necessarily in
  place for every runner, and makes it impossible to override in a test.
- Fail loudly and early at startup as well as at use: subscribe to
  `zope.processlifetime.IProcessStarting` and log CRITICAL if the variable is absent. That gets
  it into the instance log at boot rather than at the first failed login. Do **not** raise from
  module import or ZCML — that also kills `bin/test`, `bin/instance debug`, and the i18n
  compile step, for no gain.
- Version the ciphertext now. Store `v1$<fernet-token>` (or use `MultiFernet`) so key rotation
  is possible later. Retrofitting a version tag onto untagged ciphertext requires decrypting
  everything with the old key, which is precisely what you cannot do once the old key is gone.
  Cheap now, impossible later.
- Never write the key to the registry, a memberdata property, or the log; never echo it in an
  error message. Note `test-4.3.cfg` installs `Products.DocFinderTab` and `aws.zope2zcmldoc` —
  through-the-web introspection tools. They are dev-only; make sure they stay out of the
  production buildout.

**Warning signs:**
```bash
grep -n "environment-vars" -A 6 base.cfg          # key present in [instance] AND [testenv]?
bin/instance run -c "import os; print os.environ.get('IMIO_GA_SEED_KEY') is not None"
```
Operational check: log a one-line CRITICAL at startup when the key is missing, then
`grep -c CRITICAL var/log/instance*.log` across all ZEO clients — the count must be 0 on every
client, not just one.

**Phase to address:** Encryption.

---

### Pitfall 13: Coverage measured with `[report] include` and no `[run] source` is inflated

**Confidence: HIGH — `.coveragerc` contains only `[report] include = ...`;
`base.cfg [test-coverage]` runs `bin/coverage run bin/test` with no `--source`;
`createcoverage` 1.5 does the same (`parts = [coveragebinary, 'run', testbinary]`).**

**What goes wrong:**
`coverage` only knows about files it *traced*. `include` under `[report]` filters what is
reported; it does not add un-executed files to the denominator. So a module that no test ever
imports is absent from the report entirely, and the percentage is computed over the subset of
code that was reachable. Turning `--fail-under=90` on against that number gates nothing.

Concretely: the modules most likely to be untested here (`upgrades/to0301.py`,
`browser/forms/request_bar_code_reset.py`, `browser/disable_two_factor_authentication*.py`) are
exactly the ones that may not be imported at all, and their absence *raises* the reported
percentage.

There is a second, opposite inflation: Plone add-ons load their whole package at ZCML time, so
every `import`, `def`, `class` and decorator line in every module registered in
`configure.zcml` is executed during layer setup and counts as covered. Statement coverage on a
Plone package therefore over-reports by a large, unpredictable margin — a module whose function
bodies are never called still shows its top-level lines green.

**Why it happens:**
`.coveragerc` looks correct — it names the right directory. The section header is the problem,
not the path.

**How to avoid:**
```ini
[run]
source = src/imio/googleauthenticator
branch = True
omit =
    */tests/*
    */upgrades/*

[report]
show_missing = True
exclude_lines =
    pragma: no cover
```
`source` under `[run]` makes coverage enumerate the package on disk and report 0%-covered files.
`branch = True` is the honest metric for a package whose import-time lines are free. Expect the
number to **drop sharply** the moment this is fixed — that drop is the truth, not a regression.
Set the gate against the corrected number and raise it from there; do not tune `.coveragerc`
until 90% appears.

**Warning signs:**
```bash
bin/coverage run bin/test -t '!robot' && bin/coverage report -m | wc -l
# the row count must equal the number of .py files under src/imio/googleauthenticator
find src/imio/googleauthenticator -name '*.py' | grep -v tests | wc -l
```
If the second number is larger than the first, the report is lying.

**Phase to address:** Coverage.

---

### Pitfall 14: `bin/test-coverage` reports success when the tests fail

**Confidence: HIGH — the inline template in `base.cfg:82-92` is quoted verbatim below.**

**What goes wrong:**
```bash
#!/bin/bash
export TZ=UTC
${buildout:directory}/bin/coverage run bin/test $*
${buildout:directory}/bin/coverage html
${buildout:directory}/bin/coverage report -m --fail-under=90
```
No `set -e`, no `exit`. The script's exit status is that of `coverage report` alone. **Failing
tests plus ≥90% coverage is a green build.** Since `[test-coverage]` is currently commented out
of the parts list, this lands the moment it is enabled — i.e. exactly when the roadmap turns
coverage enforcement on, and it will look like it is working.

**How to avoid:**
Add `set -e` (or `set -euo pipefail`) as the second line of the template and enable
`[test-coverage]` and `[coverage]` in `base.cfg`'s `parts`. Then deliberately break one test
and confirm `bin/test-coverage; echo $?` is non-zero.

**Warning signs:**
```bash
bin/test-coverage -t '!robot'; echo "exit=$?"     # must be non-zero when a test fails
```
Prove it once with an intentional failure before trusting CI.

**Phase to address:** Coverage — first commit of the phase, before writing any new tests.

---

### Pitfall 15: Moving browser tests to a functional layer changes more than the base class

**Confidence: HIGH — `plone.testing` 4.1.3 and 5.0.0 `z2.py` and `plone.app.testing` 4.2.7
read.**

**What goes wrong:** four separate traps in one refactor.

1. **The current suite has *no* isolation guard.** `plone.testing` 4.1.3's
   `IntegrationTesting.testSetUp` just does `transaction.begin()` and aborts on teardown.
   5.0.0 adds the guard by monkeypatching the module-level function:
   ```python
   def you_broke_it():
       raise TestIsolationBroken("""You are in a Test Layer (IntegrationTesting) ...""")
   transaction.commit = you_broke_it
   ```
   So today `tests/base.py:_install()`'s quickinstaller round-trip commits and **leaks state
   into every subsequent test in the layer**. Tests currently pass partly *because* of that
   leak. Expect tests that "worked" to fail once each gets a clean fixture — those are real
   bugs being revealed, not caused. Budget for it.
   Note the patch is on `transaction.commit`; `transaction.get().commit()` slips past it, so
   5.0.0's guard is necessary but not sufficient evidence of isolation.

2. **`FUNCTIONAL_TESTING` as currently defined drags in `z2.ZSERVER_FIXTURE`**, which starts a
   real HTTP server and binds a TCP port at layer setup. `plone.testing.z2.Browser` publishes
   **in-process** and does not need it. Compare `plone.app.testing`'s own layers
   (`layers.py:331-335`): `PLONE_FUNCTIONAL_TESTING` has no ZSERVER; only `PLONE_ZSERVER` and
   the Robot layer do. Define a plain `FunctionalTesting(bases=(FIXTURE,))` for the browser
   tests and keep ZSERVER on the Robot layer only — otherwise you inherit port-binding
   flakiness and a slower suite for nothing.

3. **Moving the install into `setUpPloneSite` may break `test_product_is_installed`.**
   `plone.app.testing.applyProfile` (helpers.py:96) only calls
   `setupTool.runAllImportStepsFromProfile(profileId)` and re-derives the skin; it does not call
   `portal_quickinstaller.installProduct`. The add-on ends up in
   `listInstalledProducts()` only via QuickInstaller's `IProfileImportedEvent` subscriber
   (`CMFQuickInstallerTool/events.py:70`), which needs `event.full_import` **and** a `REQUEST`
   **and** the product to be discoverable by `qi.listInstallableProducts()`. If any of those is
   absent, `test_product_is_installed` fails on a change that is otherwise correct. Assert
   installedness by something you control — the PAS plugin exists and is registered for
   `IAuthenticationPlugin`, the registry records exist, the browser layer is active — rather
   than by QuickInstaller bookkeeping. Those assertions are also what catches Pitfall 3.

4. **Renaming the layer constants is a rename-phase task with a coverage-phase consequence.**
   `COLLECTIVE_GOOGLEAUTHENTICATOR_*` appear in five test modules plus `testing.py`, and
   `testing.py` also hardcodes `z2.installProduct(app, 'collective.googleauthenticator')` and
   `import collective.googleauthenticator`. `z2.installProduct` with a name that does not
   resolve **logs and continues by default** (`quiet=False` only logs), so a missed rename here
   means `initialize()` never runs, `registerMultiPlugin` never happens, and the ZMI add-list
   entry silently disappears while tests still pass.

**Phase to address:** Coverage (items 1-3); item 4 in Rename, verified in Coverage.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| `forInterface(..., check=False)` to silence the missing-record error | error goes away in one character | converts a clear `KeyError` at install into `AttributeError` deep in a login request; masks the ordering bug permanently | never — fix the ordering |
| Keep `runImportStepFromProfile` and just rename the profile string | smallest diff | keeps a re-entrant call into GenericSetup, keeps the ordering dependency implicit, keeps the silent `"Cannot find registry"` path | never — it is 3 lines to delete |
| Rename `PAS_ID` from `google_auth` | consistency | on any existing ZODB creates a *second* plugin (`_add_plugin` returns early only on id match), leaving a Broken old one still registered for `IAuthenticationPlugin`; `google_auth` is already namespace-neutral and appears in README + `test_pas_plugin.py` | never — rename `PAS_TITLE` only |
| Rename `meta_type` (`'Collective Google Authenticator PAS'`) | consistency | cosmetic ZMI-only gain; `registerMultiPlugin` raises `RuntimeError` on a duplicate, and `plone.app.testing`'s `snapshotMultiPlugins`/`tearDownMultiPlugins` key on it | acceptable, but do it in its own commit so the RuntimeError signal stays interpretable |
| Keep `upgrades/` (the 0301 actions-reorder step) | no work | a whole extra rename surface: `upgrades/configure.zcml`, the `profile-...upgrades:0301` string in `to0301.py`, `<include package=".upgrades"/>`, `upgrades/profiles/0301/actions.xml`, and a second `runImportStepFromProfile` call | delete it — it only ever mattered for sites installed at ≤0.3.0, of which there are none |
| Leave the `.mo` file out of the rename | it is git-ignored anyway | `zope_i18n_compile_mo_files` only recompiles when the `.po` is newer than the `.mo`; `git mv` preserves mtimes | delete the `.mo`, never move it |
| Encrypt seeds without a version prefix | one less field | key rotation becomes impossible without the old key; there is no way to tell v1 from v2 ciphertext | never — `v1$` costs three bytes |
| Enable `--fail-under=90` before fixing `.coveragerc` | green gate today | the gate measures a subset of the code and blocks nothing; the number will collapse when `[run] source` is added | never — fix `.coveragerc` first, then set the gate |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| `imio.dms.mail` resource registries | Overriding/removing `popupforms.js` and assuming your profile wins | Never touch a resource you do not own; add your own id `insert-after` theirs. Verify by applying both profiles in both orders and diffing `portal_javascripts.getResourceIds()` |
| `imio` namespace package | `src/imio/__init__.py` written with `pkgutil.extend_path` or left empty, or `namespace_packages` not declared in `setup.py` | Match the other `imio.*` eggs exactly: `__import__('pkg_resources').declare_namespace(__name__)` plus `namespace_packages=['imio']`. Mixing declaration styles in one namespace makes whichever `imio/__init__.py` is found first win and hides the other subpackage |
| `imio.helpers` (for `zint` QR generation) | Adding it as a dependency in the QR phase, long after the rename | Add `imio.helpers` to `install_requires` **in the rename phase**. It is the only thing that forces `imio.googleauthenticator` and `imio.helpers` into the same process, which is the only way the namespace-package mistake above surfaces before deployment |
| Puppet → `port.cfg` → `environment-vars` | Assuming one place to set the key | Four places: `[instance]`, `[testenv]`, the CI workflow, and the Puppet fragment in the separate `industrialisation` repo. Per-ZEO-client, not per-database |
| `chart.googleapis.com` (current QR source) | Encrypting seeds at rest while still sending the plaintext seed to Google in a URL | Encryption at rest is worthless until the external QR call is gone. Sequence the QR change **before or with** the encryption change, not after |
| GenericSetup profile marker file | Renaming `MessageFactory` and the profile id but not `profiles/default/collective.googleauthenticator.marker.txt` | `setupVarious` guards on `context.readDataFile('<name>.marker.txt') is None` and **returns silently** when it does not match, so the PAS plugin is never added and no error is raised. Rename the file and the string together, and assert the plugin exists after `applyProfile` |
| `check-manifest` / sdist | Leaving `MANIFEST.in`'s eight hardcoded `src/collective/googleauthenticator/...` paths | With no `setuptools_git`, `MANIFEST.in` is the only source for `include_package_data`. Stale paths produce an sdist/egg with **no `profiles/`, no `locales/`, no `skins/`** — the add-on installs but does not appear in the install list. Invisible in dev (develop-egg reads `src/` directly), fatal on release. `bin/check-manifest` is already part of `bin/code-analysis` |

## Performance Traps

Not the risk area for this milestone — PROJECT.md already parks caching and async bulk ops. The
two worth knowing:

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Fernet decrypt per login | negligible | none needed — Fernet is AES-CBC + HMAC, microseconds | never at iMio scale |
| Replay/lockout counters in memberdata | write conflict retries on `portal_memberdata` under concurrent logins for the *same* user | one property write per login attempt, per user — no shared counter object. PROJECT.md's decision is already correct; the trap is "optimising" it into a single shared counter object, which creates a ZODB write hotspot and cross-user `ConflictError`s | only if refactored into shared state |

## Security Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Letting a plugin exception mean "not competent" | complete, silent 2FA bypass on any of five exception types | `_dont_swallow_my_exceptions = True`; fail closed on decrypt failure (Pitfall 4) |
| Renaming the package on a live ZODB | the PAS plugin becomes a Broken object and 2FA silently stops running (Pitfall 3) | discard and recreate DBs; assert the plugin is registered for `IAuthenticationPlugin` in a test |
| `next_url` from `Referer`, unvalidated | open redirect after successful 2FA — phishing/session hand-off | validate against the portal URL; `urlencode` on the way in |
| Reset token compared with `!=` | timing oracle on the bar-code reset token (`reset_bar_code.py:104`) | `hmac.compare_digest` (Python 2.7.7+ has it) |
| `"{0}{1}{2}".format(user_secret, browser_hash, ska_secret_key)` | collidable derived signing key (`helpers.py:259`) | `hmac.new(ska_secret_key, b'\x00'.join((user_secret, browser_hash)), sha256)`, or at minimum a separator that cannot appear in the parts |
| Key in the registry / control panel / log | key lands in the ZODB, in `portal_setup` snapshots (QuickInstaller takes one before *and* after every install), and in exports — defeating the whole point | env var only; never `logger.*` the key or include it in an exception message |
| Trusting `X-Forwarded-For` for the IP whitelist | whitelist bypass by header spoofing → second factor skipped entirely | already in CONCERNS.md; note that `is_whitelisted_client()` is the **first** line of `authenticateCredentials`, so a spoof there is a full bypass, not a degradation |
| Logging usernames + 2FA state at debug | user enumeration from log files | log outcome, not identity (`pas_plugin.py:90,94`) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---|---|---|
| Removing the skin overrides without replacing the overlay fix | clicking the header "Log in" link produces a dead overlay; 2FA users cannot log in at all through the normal UI | unbind the login overlay from your own JS, and test via the header link, not a direct POST |
| Fail-closed with no message | user is denied with "Login failed" and no idea why; support cannot tell a wrong password from a missing server key | distinct, non-leaking status message for "second factor unavailable, contact your administrator" + a CRITICAL server log line |
| No recovery path once the skin-based reset email breaks | user with a lost device has no self-service route and the email flow fails silently | keep `request_bar_code_reset_email` working through the skin removal (Pitfall 9); recovery codes are already an Active requirement |
| Lockout with no unlock story | an attacker can lock out any known username by failing N times | count per (user, IP) or add a time-based auto-unlock; document how an admin clears the counter |

## "Looks Done But Isn't" Checklist

- [ ] **Rename:** `find src -name '*.pyc'` empty **and** `src/collective/` gone from disk — `git mv` alone does neither
- [ ] **Rename:** exactly one `develop-eggs/*googleauthenticator*.egg-link` and one `src/*.egg-info`
- [ ] **Rename:** `git grep -i collective -- src/ setup.py base.cfg .coveragerc MANIFEST.in` returns nothing (excluding `collective.recipe.*` in buildout)
- [ ] **Rename:** the profile **marker file** renamed, not just the string that reads it — otherwise `setupVarious` returns silently and the PAS plugin is never added
- [ ] **Rename:** `locales/*.pot`, `*.po`, `rebuild_i18n.sh`'s `I18NDOMAIN`, and the deleted `.mo`
- [ ] **Rename:** `MANIFEST.in` (8 paths), `.coveragerc`, `base.cfg` `package-name` + `[code-analysis] directory`, `cleanup.sh`, `testing.py`'s `z2.installProduct` string
- [ ] **Rename:** `src/imio/__init__.py` is `declare_namespace`, `setup.py` has `namespace_packages=['imio']`, and `bin/python -c "import imio.helpers, imio.googleauthenticator"` works in one process
- [ ] **Rename:** `bin/python setup.py sdist` then unpack it and confirm `profiles/`, `locales/`, `www/`, `browser/static/` are present
- [ ] **Registry:** `getSortedImportSteps()` puts your step **after** `plone.app.registry` — asserted in a test, not observed once
- [ ] **Registry:** `grep -rn runImportStepFromProfile src/` returns nothing
- [ ] **Registry:** applying the profile **twice** leaves `ska_secret_key` unchanged
- [ ] **Registry:** no `portal_registry` key starts with `collective.`
- [ ] **Encryption:** a test with the env var **unset** asserts login is refused, not granted
- [ ] **Encryption:** a test with a **wrong** key asserts login is refused, not granted
- [ ] **Encryption:** ciphertext carries a version prefix
- [ ] **Encryption:** the key is set in `[instance]`, `[testenv]`, CI, **and** tracked as a Puppet change
- [ ] **Challenge:** login through the header "Log in" link (overlay path) reaches the token form
- [ ] **Challenge:** `grep -rn restrictedTraverse src/` returns nothing, and the control panel still renders its extra links
- [ ] **Challenge:** `popupforms.js` is still in `portal_javascripts` after applying the profile
- [ ] **Challenge:** `profiles/uninstall/` reverses everything `profiles/default/` adds to `portal_javascripts` / `portal_css`
- [ ] **Coverage:** `coverage report` lists every non-test `.py` file in the package
- [ ] **Coverage:** `bin/test-coverage` exits non-zero when a test fails (prove it with a deliberate failure)
- [ ] **Coverage:** `branch = True`, and the gate is set against the post-fix number
- [ ] **Coverage:** `bin/code-analysis` exits 0 so the pre-commit hook stops training people to use `--no-verify`

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| Stale `.pyc` shadowing (P1) | LOW | `git clean -xdf src/`, re-run `bin/buildout -N`, re-run tests. Cheap *if* found early; expensive if a half-renamed commit is merged and CI was green on stale bytecode |
| Stale egg-info / egg-link (P2) | LOW | delete both, `bin/buildout -N`. The `registerMultiPlugin` RuntimeError points straight at it |
| Broken ZODB objects (P3) | LOW now, HIGH later | now: delete `var/filestorage` + `var/blobstorage`, recreate the site. After deployment: a `zodbupdate` rename map plus re-enrolment of every user. **This is the reason to do the rename before any deployment** |
| Silent 2FA bypass shipped (P4) | HIGH | there is no forensic trail — the swallowed exception is logged at `debug`. Recovery is "assume every login since the deploy was single-factor". Prevention is one line; treat it as non-negotiable |
| Import-step order re-flips (P6) | LOW | add the `<depends>` and the ordering assertion. If a site is already broken: re-run the add-on profile (`portal_setup` → Import → `imio.googleauthenticator:default`) to create the records |
| Translations lost (P5) | LOW | rename the `locales` files, restart (the `.mo` recompiles) |
| Encryption key lost / rotated without a version tag | HIGH | every seed is unrecoverable; all users must re-enrol. Mitigated only by the `v1$` prefix and by having the key in Puppet-managed config with a documented backup |
| `popupforms.js` removed from a site, then add-on uninstalled (P10) | MEDIUM | manually re-register the resource in `portal_javascripts`, or ship a proper uninstall profile and re-run it |
| Coverage gate found to be measuring nothing | LOW | fix `.coveragerc`, accept the lower number, re-baseline |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| P1 stale `.pyc` | Rename (commit 1) | `find src -name '*.pyc'` empty; `test ! -d src/collective`; `bin/python -c "import collective.googleauthenticator"` fails |
| P2 stale egg-info / egg-link | Rename | one egg-link, one egg-info; Zope starts without `registerMultiPlugin` RuntimeError |
| P3 broken ZODB objects | Rename | fresh `Data.fs`; test asserts `google_auth` is registered for `IAuthenticationPlugin` |
| P4 PAS swallows exceptions | **Rename (one-line commit), verified in Encryption** | test: garbage key → login refused; test: no key → login refused |
| P5 i18n domain vs filenames | Rename | `find src -name 'collective.googleauthenticator.*'` empty; Dutch control panel renders Dutch |
| P6 import-step ordering | Registry fix | `getSortedImportSteps().index(...)` assertion in the suite |
| P7 nested `runImportStepFromProfile` | Registry fix | `grep -rn runImportStepFromProfile src/` empty; no `"Cannot find registry"` in the log |
| P8 `<records>` semantics | Registry fix | apply profile twice, `ska_secret_key` unchanged |
| P9 skin templates still traversed | Challenge rework | `grep -rn restrictedTraverse src/` empty; control panel renders its extra links |
| P10 resource-registry collision | Challenge rework | `popupforms.js` still registered; both-orders profile diff is empty |
| P11 redirect / cookie / credential traps | Challenge rework | overlay login path reaches the token form; no `__ac` after challenge; no redirect loop |
| P12 env var scope | Encryption | key present in `[instance]`, `[testenv]`, CI; startup CRITICAL when absent; Puppet change tracked |
| P13 `.coveragerc` inflation | Coverage (commit 1) | report row count == file count |
| P14 `test-coverage` exit status | Coverage (commit 1) | deliberate test failure → non-zero exit |
| P15 test-layer semantics | Coverage | browser tests on a ZSERVER-free `FunctionalTesting`; `plone.testing` pin can float to 5.0.0 again |

**Ordering consequence for the roadmap:** the rename must come first (P3 is only cheap while
nothing is deployed), but **P4's one-line fix should ride along in the rename phase**, not wait
for the encryption phase — it is the guard that makes every later phase's mistakes visible
instead of silent. The registry fix should precede the encryption phase, because the encryption
key is read on a code path that the registry seeding bug already destabilises. Coverage should
land its two infrastructure fixes (P13, P14) before any new tests are written, otherwise the
phase measures itself with a broken instrument.

## Sources

- Source read directly from this buildout's pinned eggs in `/srv/cache/eggs`:
  `Products.GenericSetup-1.8.11` (`tool.py`, `utils.py`, `zcml.py`, `registry.py`, `events.py`),
  `plone.registry-1.0.5/registry.py`, `plone.app.registry-1.2.5/exportimport/handler.py` and
  `exportimport/configure.zcml`, `Products.PluggableAuthService-1.11.3/PluggableAuthService.py`,
  `Products.CMFQuickInstallerTool-3.0.16` (`QuickInstallerTool.py`, `events.py`),
  `Products.CMFPlone-4.3.20/factory.py`, `plone.testing-4.1.3/z2.py`,
  `plone.testing-5.0.0/z2.py`, `plone.app.testing-4.2.7` (`helpers.py`, `layers.py`),
  `createcoverage-1.5/script.py` — **HIGH**
- Reproduced on this machine with `bin/python` (Python 2.7.18): orphan `.pyc` import with no
  `.py` present succeeds — **HIGH**
- Working tree inspection: `git status --porcelain --ignored src`, `develop-eggs/`,
  `src/collective.googleauthenticator.egg-info/`, `MANIFEST.in`, `.gitignore`, `base.cfg`,
  `.coveragerc`, `cleanup.sh`, all `profiles/**`, `skins/**`, `browser/static/**` — **HIGH**
- [PAS eats exceptions — Plone Documentation v4.3](https://4.docs.plone.org/old-reference-manuals/pluggable_authentication_service/pas-eats-exceptions.html)
  — confirms `_dont_swallow_my_exceptions` — **HIGH** (corroborates source)
- [Add-on installation and export framework: GenericSetup — Plone Documentation v4.3](https://4.docs.plone.org/develop/addons/components/genericsetup.html)
  — `pre_handler`/`post_handler` from GenericSetup 1.8.2+; `forInterface(check=False)` / `omit`
  — **MEDIUM**
- `.planning/codebase/CONCERNS.md` and `TESTING.md` — the pre-existing bug/coverage inventory
  this document extends rather than repeats — **HIGH**

---
*Pitfalls research for: Plone 4.3 add-on rename + hardening (`collective.googleauthenticator` → `imio.googleauthenticator`)*
*Researched: 2026-07-28*
