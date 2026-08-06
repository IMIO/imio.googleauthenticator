# Phase 1: Rename and Fail-Closed - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-28
**Phase:** 1-Rename and Fail-Closed
**Areas discussed:** Fork provenance & metadata, Version & profile version, Translation scope, Developer migration steps

Two things were resolved from code rather than asked: the `imio` namespace declaration style
(settled by `imio.helpers`) and the git remote (already `IMIO/imio.googleauthenticator.git`).
The GPL license question was also not asked — GPL-2.0 is viral for derivative works and matches
`imio.helpers`, so there was nothing to decide.

---

## Area selection

| Option | Description | Selected |
|--------|-------------|----------|
| Fork provenance & metadata | Upstream author/url/AUTHORS.txt, PyPI target | ✓ |
| Version & profile version | setup.py 0.3.0, GS profile 0301 | ✓ |
| Translation scope | Whether Dutch is worth carrying through the rename | ✓ |
| Rename commit shape | Pure `git mv` first vs move+edit together | |

**Notes:** Rename commit shape went to Claude's discretion.

---

## Fork provenance & metadata

### Authorship

| Option | Description | Selected |
|--------|-------------|----------|
| iMio as author, upstream preserved in AUTHORS.txt | setup.py → iMio, AUTHORS.txt keeps 4 upstream names under "Original authors", README fork line | ✓ |
| iMio as author, upstream credited in README only | AUTHORS.txt replaced, credit moves to a README "Origins" section | |
| Keep upstream author, add iMio as maintainer | Most conservative GPL reading, but misrepresents who maintains it | |

**User's choice:** iMio as author, upstream preserved in AUTHORS.txt
**Notes:** Stated up front that GPL-2.0 §1 requires copyright notices to be preserved, so the
question was where attribution lives, not whether. That removed an option rather than adding one.

### Publication target

| Option | Description | Selected |
|--------|-------------|----------|
| Git checkout only | Via mr.developer; RENAME-06 becomes hygiene not a gate | |
| Published to PyPI | RENAME-06 load-bearing; stale MANIFEST.in ships a broken sdist invisibly | ✓ |
| Internal index only | Same rigor, no public metadata concerns | |

**User's choice:** Published to PyPI
**Notes:** This escalated RENAME-06 from hygiene to load-bearing and raised the bar on classifiers
and `long_description` rendering. It is also what made the `MANIFEST.in` comma bug matter.

### Positioning / lifespan disclosure

| Option | Description | Selected |
|--------|-------------|----------|
| State it plainly in README + classifiers | Scope-and-lifespan note; honest Development Status; fixes the false Python 2.6 claim | |
| Fix classifiers only, no lifespan note | Correct the metadata, publish without lifespan commentary | ✓ |
| Publish as-is positioning | Leaves the untested Python 2.6 claim in place | |

**User's choice:** Fix classifiers only, no lifespan note
**Notes:** Concern raised that PyPI visitors will find a maintained-looking Plone 4 MFA package and
be surprised by the Keycloak retirement. User decided against the note. Recorded as their call and
not revisited.

### README screenshots

| Option | Description | Selected |
|--------|-------------|----------|
| Rehost in our repo, rewrite the URL | Keep `docs/_static/`, repoint the rewrite at IMIO raw URLs | ✓ |
| Drop images from long_description | Keep for Sphinx, strip the rewrite hack; text-only PyPI page | |
| Delete the screenshots entirely | Smallest diff, loses the setup walkthrough | |

**User's choice:** Rehost in our repo, rewrite the URL
**Notes:** Discovered that `setup.py` rewrites 10 `.. image:: _static/...` directives to
`github.com/collective/collective.googleauthenticator/raw/master/docs/_static` — so the published
PyPI page would embed screenshots served from upstream's branch. Flagged that the rehosted images
show the pre-rename UI and will go stale when Phase 7 changes the login flow; recorded as deferred.

### Dead weight

| Option | Description | Selected |
|--------|-------------|----------|
| Move LICENSE to root, delete examples/, keep docs/ | LICENSE where PyPI/GitHub look; drop upstream's demo buildout; rename docs/ refs | ✓ |
| Move LICENSE to root, delete both examples/ and docs/ | Also drop the Sphinx build | |
| Rename references, delete nothing | More surface to rename and to rot | |

**User's choice:** Move LICENSE to root, delete examples/, keep docs/
**Notes:** `LICENSE.txt` and `LICENSE.GPL` currently live in `docs/`, where neither PyPI nor GitHub
finds them. `builddocs.sh` is not a buildout part.

---

## Version & profile version

### Package version

| Option | Description | Selected |
|--------|-------------|----------|
| Restart at 1.0.0.dev0 | New name, new lineage; honest for production MFA; matches imio.helpers convention | ✓ |
| Continue at 0.4.0.dev0 | Acknowledges upstream continuity; understates a login-guarding package | |
| Restart at 0.1.0.dev0 | Cleanest break; discards the signal that the codebase is mature | |

**User's choice:** Restart at 1.0.0.dev0

### GenericSetup profile version

| Option | Description | Selected |
|--------|-------------|----------|
| Reset to 1000 | Matches 1.0.0, headroom for 1001+; safe since no site has the profile under the new id | ✓ |
| Keep 0301 | Minimal diff, but implies an upgrade history that no longer exists | |
| Reset to 1 | Simplest, but diverges from the 4-digit convention | |

**User's choice:** Reset to 1000

### Changelog history

| Option | Description | Selected |
|--------|-------------|----------|
| Keep history below a new 1.0.0 heading | Preserves provenance; long_description concatenates the changelog | ✓ |
| Archive history, start clean | Cleanest PyPI page, loses context of what the package already did | |
| Keep only the 0.3.0 entries | Arbitrary cut-off; 0.3.0 was never released | |

**User's choice:** Keep history below a new 1.0.0 heading

### DOC-04 audience

| Option | Description | Selected |
|--------|-------------|----------|
| iMio devs with local dev databases | Accurate — nothing is deployed | |
| Anyone who installed collective.googleauthenticator | Public upgrade warning; broader reach | ✓ |
| Both, as separate notes | Dev line plus a README not-a-drop-in-replacement section | |

**User's choice:** Anyone who installed collective.googleauthenticator
**Notes:** Flagged that a public upgrade warning risks promising a migration story that was never
built or tested. Resolved by framing it as an explicit **non**-migration notice — not a drop-in
replacement, no migration path, existing installs must re-enroll — which serves the chosen audience
honestly.

### Free-text instruction

**User's response (to the "more questions?" gate):** "Reformat CHANGES.txt the same way
`@src/imio.dms.mail/CHANGES.rst`"

**Notes:** Read that file as the format authority and added it to canonical refs. Format: `Changelog`
with a matching `=`-underline, `X.Y.Z (unreleased)` single-line headings with matching `-`-underlines,
entries as `- Description.` + `  [handle]`. Mechanical consequences traced: `git mv` to `CHANGES.rst`,
plus `setup.py:13` and `MANIFEST.in:1`. While checking, found the `MANIFEST.in` comma bug and the
stale `CONTRIBUTORS.txt` include — both independent of the rename.

---

## Translation scope

### i18n domain

| Option | Description | Selected |
|--------|-------------|----------|
| Rename it | Consistent; requires git mv of .pot/.po, .mo deletion, ZCML + rebuild_i18n.sh updates | ✓ |
| Keep the old domain | Nearly free, zero silent-loss risk, but ships a domain naming a foreign project | |

**User's choice:** Rename it

### Languages

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Dutch as-is | 41/42 complete, free to carry | |
| Keep Dutch, note French as deferred | Plus a deferred idea for French | |
| Drop Dutch, keep only the .pot | Discards 41 working translations | |

**User's choice (free text):** "Keep Dutch, add French and English"
**Notes:** Accepted as an expansion of RENAME-03, justified because the locales machinery is already
open this phase. Investigation showed msgids *are* English source text, so an `en` translation is
normally redundant — but several msgids are defective (`controlpanel.py:45` "ommit", a string missing
the word "code", one with a trailing space), which gave the English request a real basis. That turned
into the two follow-up questions below.

### Defective English msgids

| Option | Description | Selected |
|--------|-------------|----------|
| Fix the msgids in source | Correct where developers read them; ~3 Dutch entries go fuzzy | |
| Ship an en/.po override | Dutch untouched, but the typo stays in Python source forever | |
| Both | Fix source and ship the override | ✓ |

**User's choice:** Both
**Notes:** Flagged that the override becomes redundant once msgids are correct — 42 extra strings to
keep in sync for no identified benefit. User chose Both. Recorded as decided and not re-argued.

### French authorship

| Option | Description | Selected |
|--------|-------------|----------|
| I write them, you review | Claude drafts 42 strings, user corrects house terminology | ✓ |
| Scaffold empty, human fills in | Machinery now, translation later; English fallback meanwhile | |
| I write them, no review needed | Riskier for strings users read during a failed login | |

**User's choice:** I write them, you review

---

## Additional gray areas (second round)

| Option | Description | Selected |
|--------|-------------|----------|
| Fail-closed blast radius & break-glass | A plugin bug now locks out all in-site users; Zope root becomes break-glass | |
| What the user sees on failure | Raw 500 vs custom error view that must not leak 2FA state | |
| Developer migration steps | Nothing purges .pyc + egg-info + stale Data.fs together | ✓ |
| How the fail-closed test is built | Monkeypatch vs test subclass vs real broken input | |

**User's choice:** Developer migration steps
**Notes:** The other three went to Claude's discretion and are recorded as decisions in CONTEXT.md.

---

## Developer migration steps

### Form

| Option | Description | Selected |
|--------|-------------|----------|
| Extend cleanup.sh, reference from CHANGES.rst | Nearly free since cleanup.sh is renamed anyway | |
| New Makefile target | Discoverable via `make help`, consistent with the repo's driver | ✓ |
| Prose instructions only | Least code, but the skipped step's failure mode is silent | |

**User's choice:** New Makefile target
**Notes:** Checked the Makefile rather than assuming — `backup`/`restore` are gated on
`old_plone`/`plone` for Plone version switches, so they do *not* silently restore a stale `Data.fs`.
The real gap is that `make cleanall` removes `bin include lib … parts` but not `var/`, not `.pyc`,
and not `src/*.egg-info`, while `cleanup.sh` gets only the egg-info.

### .pyc policy

| Option | Description | Selected |
|--------|-------------|----------|
| Prevent permanently | `PYTHONDONTWRITEBYTECODE=1` in base.cfg environment-vars + purge | |
| Clean once | Purge the 27 existing files and move on | ✓ |

**User's choice:** Clean once
**Notes:** This **overrides the Phase 1 roadmap note** specifying `PYTHONDONTWRITEBYTECODE=1`.
Residual risk stated and accepted: Phases 3–7 move and delete modules, so a new orphan `.pyc` can
appear and Python 2.7 imports it with no `.py` beside it, silently. The new Makefile target is the
remedy. Logged as a deferred item for reconsideration.

---

## Claude's Discretion

- **Rename commit shape** — pure `git mv` commit first, then content edits, so git's rename
  detection survives across ~30 moved files and the diff stays reviewable.
- **Fail-closed blast radius and break-glass** — accept that a plugin bug locks out every in-site
  user including Site Admins, with the Zope root admin (excluded from MFA as out of scope) serving
  as break-glass. State this in DOC-01 so the exclusion reads as intentional. A loud outage beats a
  silent 2FA bypass.
- **Failure presentation** — plain Zope 500 for now; no custom error view, which is easy to get
  wrong with respect to leaking whether 2FA is enabled. Revisit in Phase 3.
- **Fail-closed test construction** — raise from a real collaborator the plugin calls, not a
  monkeypatch of `authenticateCredentials` itself, so the test exercises the PAS path that
  `_SWALLOWABLE_PLUGIN_EXCEPTIONS` would otherwise absorb.

## Deferred Ideas

- Refresh README screenshots after Phase 7 changes the login flow
- Release tooling (`zest.releaser` / `fullrelease`) for whoever cuts 1.0.0
- Verify `rebuild_i18n.sh`'s `../../../../../bin/i18ndude` path — resolves two levels above the repo
  root; unchanged by the rename
- `PYTHONDONTWRITEBYTECODE=1` — rejected here, reconsider if Phases 3–7 hit an orphan `.pyc`
- Custom error view for the fail-closed 500 — Phase 3
- French translation of Phase 5 and Phase 6 strings (lockout, recovery codes) in their own phases
