---
phase: 3
reviewers: [claude]
reviewed_at: 2026-07-30T08:24:45Z
plans_reviewed: [03-01-PLAN.md, 03-02-PLAN.md, 03-03-PLAN.md]
review_independence: degraded
independence_note: >-
  Only one prompt-fed reviewer ran, and it shares a model family with the planner.
  Treat findings as a fresh-context audit, not a cross-model consensus.
lanes_attempted: [gemini, claude, coderabbit]
lanes_failed: [gemini, coderabbit]
---

# Cross-AI Plan Review — Phase 3

> **⚠ Independence is degraded on this run.** `--all` was requested, but only one
> prompt-fed reviewer completed, and it is the **same model family as the planner**.
> A cross-AI review exists to surface *correlated* blind spots; a same-family review
> cannot do that. Findings below are still source-grounded and actionable — treat them
> as a fresh-context audit, and do not read "one reviewer agreed" as consensus.

## Lane Status

| Lane | Result | Detail |
|------|--------|--------|
| gemini | ✗ auth blocked | Installed (0.1.5), but the Google account is a Workspace/Code-Assist account: `Error: This account requires setting the GOOGLE_CLOUD_PROJECT env var`. Exited before reading the prompt. Fix: interactive `gemini` login, or export `GOOGLE_CLOUD_PROJECT`. |
| claude (headless) | ✓ completed | Fresh `claude -p` session, no shared context, read the real repo. **Same model family as the planner** — see the warning above. |
| coderabbit | ✗ inapplicable | Authenticated, but diff-only, and the branch diff against `master` is 456 files vs the free-plan limit of 150. Narrowing to `--dir src` would find nothing regardless: this phase produced plans, not code, so there is no code diff for a diff reviewer at plan time. |
| codex · opencode · qwen · cursor-agent · agy · ollama · lm_studio · llama.cpp | — not installed | No binary / no local server on this host. |

---

## Claude Review (headless, fresh session — same model family as planner)

I have read the referenced source. Writing the review.

# Cross-AI Plan Review — Phase 3: Encrypted Seeds and Local QR

## 1. Summary

These three plans are unusually well-grounded: I checked roughly forty file:line citations against the tree and essentially all of them are exact (`helpers.py:94-104`, `:107-123`, `:126-142`, `:145-167`, `:170-188`, `pas_plugin.py:71`, `:160`, `user_setup.py:68`, `:108`, `reset_bar_code.py:104`, `:154`, `request_bar_code_reset.py:84`, `base.cfg:39-52`, `setup.py:55-64`, `test-4.3.cfg:104-117`). The plans correct two real errors in their own upstream research — the **three** `ipaddress` call sites (`helpers.py:484`, `:505`, `:554`, confirmed) and the **two** reset-token comparison sites (`reset_bar_code.py:104` and `:154`, confirmed) — and plan 03-03 honestly refuses to manufacture a BUG-02 fix that isn't needed (I traced all three branches of `user_setup.py:73-97`; `redirect_url` is bound on every reachable path). The threat models are wired to named tasks and named criteria rather than being decorative.

Against that, there are three blockers that will stop execution or leave a silent hole, and all three come from the same blind spot: the plans model the seed path as `helpers.py` + the two forms + the PAS plugin, and never enumerate the *other* callers of `get_or_create_secret`. There are two more (`controlpanel.py:112` via `helpers.py:434`, and `userdataschema.py:92`), one of which swallows the new `ValueError` into a "Changes saved." message. Plus plan 03-01's `bin/test -t '!robot'` gate is unsatisfiable as written, because the `[testenv]` key it depends on is added by a Wave-2 plan.

## 2. Strengths

- **Same-commit grouping is honoured for the right reason, not ritually.** Plan 03-01 keeps the pin swap and the `unicode` coercion in one commit and states the mechanism: shipping pins without coercion leaves the whitelist inert, shipping coercion without pins is a no-op. Verified — `helpers.py:23` is a bare `import ipaddress`, so which distribution wins is `sys.path` order, exactly as claimed.

- **The third `ipaddress` call site is a genuine, load-bearing correction.** `helpers.py:482-488` is a `while` loop whose `except ValueError: break` sits directly on `ip_address(proxies[0])`. `AddressValueError` subclasses `ValueError`, so RESEARCH.md's two-site fix would break out on iteration 1, leaving `ip = proxies[0]` — the leftmost, attacker-supplied hop — and then `helpers.py:505` (coerced under the partial fix) would parse it happily. That is a real whitelist bypass, and only fixing all three closes it. The plan's `grep -cE "ipaddress\.ip_(address|network)\(_to_unicode_ip\(" == 3` mechanises it.

- **The `str`/`unicode` discipline is right on every boundary I checked.** Memberdata `two_factor_authentication_secret` is `type="string"` (`memberdata_properties.xml:4`), so `OFS` coerces the stored `unicode` ciphertext through `str()` — safe because Fernet output is ASCII, and `decrypt_seed` is specified to accept either type. `except (ValueError, TypeError)` around `Fernet(key)` is correct for py2's `binascii` behaviour.

- **The non-vacuity control in plan 03-01 Task 4 is the right instinct.** `test_pas_plugin.py:97-122` already demonstrates the counterfactual shape (swallowed → truthy `user_ids` → password-only login), so asserting `_extractUserIds` *raises* is a meaningful control rather than rhetoric — and requiring the good-key pass *textually before* the two raising assertions is exactly the discipline that stops a vacuous test.

- **`base64.b32encode` over `rebus`.** Verified `helpers.py:100` is `rebus.b32encode(str(uuid4()))` and `rebus` has exactly two references (`:24` import, `:100` use), so the drop is clean. Requiring a real `onetimepass.get_totp` round-trip rather than a mock is the assertion shape that would actually have caught the `UnicodeDecodeError`.

- **Plan 03-03's honesty gate is mechanised, not promised.** `git diff --name-only HEAD~1` must not list `user_setup.py`, plus an empty-diff check on that file. That is the correct way to make "we did not invent a fix" auditable.

- **Requirement coverage is exact.** 03-01 ∪ 03-02 ∪ 03-03 = SEC-01…08, BUG-02, BUG-03, BUG-05, DOC-03 = the 12 requirements ROADMAP assigns Phase 3, with no ID declared twice (so `requirements.ready-ids`' shared-ID gate is a no-op here).

## 3. Concerns

### HIGH — Plan 03-01's `bin/test -t '!robot'` gate cannot pass; the key it needs arrives in Wave 2

`test_generic.py:43-47`:

```python
def test_user_setup_view(self):
    browser = self._get_browser()          # base.py:32 sets handleErrors = False
    self._login_browser(browser, TEST_USER_NAME, TEST_USER_PASSWORD)
    browser.open('{0}/@@setup-two-factor-authentication'.format(self.portal_url))
    self.assertEqual(browser.headers.get('status'), '200 Ok', ...)
```

That renders `SetupForm` → `user_setup.py:108` `get_token_description()` → `helpers.py:186` `get_or_create_secret(user)`. TEST_USER is created by `PLONE_FIXTURE` **before** our ZCML loads (`testing.py:16-26` is `setUpZope` on a layer whose base is `PLONE_FIXTURE`), so `userCreatedHandler` never fired for it and the property is empty — the `generate_secret` branch is taken, which after 03-01 calls `encrypt_seed` → `_get_fernet()` → `ValueError`. The read branch would need the key too, so it fails either way.

`IMIO_GA_SEED_KEY` reaches `bin/test` only through `base.cfg` `[testenv]` (`base.cfg:47` `environment = testenv`), and **plan 03-02 Task 2(b) adds it — Wave 2**. Plan 03-01's `files_modified` excludes both `base.cfg` and `test_generic.py`, so the executor hits a red suite on the phase's headline plan and must deviate on an unlisted file.

`test_token_view` (`test_generic.py:49-53`) is safe — `TokenForm.updateFields` (`token.py:122-154`) never touches the seed.

**Fix:** either move the `[testenv]` line into plan 03-01 (and relax 03-02's `grep -c "IMIO_GA_SEED_KEY" base.cfg >= 2` accordingly), or add `test_generic.py` to 03-01 with an env-var `setUp`/`tearDown`. The first is cleaner and keeps 03-02's `[instance]`/README work intact.

### HIGH — Plan 03-01 Task 4's PAS test crashes in `is_whitelisted_client()` before it reaches the crypto path

The plan names `test_plugin_exception_is_not_swallowed` (`test_pas_plugin.py:52-70`) as "the exact shape to copy", then instructs a bare `self.pas._extractUserIds(request, self.pas.plugins)` with no other setup. But that existing test *monkeypatches `is_whitelisted_client` away* — which is precisely what hides the problem.

`pas_plugin.py:91` is `if is_whitelisted_client():` with no argument → `helpers.py:567` → `helpers.py:570` `extract_ip_address_from_request(request=None)` → `helpers.py:467-470`:

```python
if not request:
    request = getRequest()
ip = request.get('REMOTE_ADDR')
```

`TestPas.setUp` (`test_pas_plugin.py:26-32`) never binds the global request, and `plone.app.testing`'s `IntegrationTesting` doesn't either. The repo already documents this: `test_unmatched_username_does_not_crash`'s docstring (`test_pas_plugin.py:81-85`) says explicitly that `authenticateCredentials()`'s first statement "calls `zope.globalrequest.getRequest()` with no argument, so this test needs a request bound the same way a real HTTP request would — plain `zope.globalrequest.setRequest()`". No existing test calls `_extractUserIds` without patching `is_whitelisted_client`.

So all three of Task 4's steps break on `AttributeError: 'NoneType' object has no attribute 'get'`: the good-key control "must complete without raising" fails, and `assertRaises(ValueError, ...)` sees `AttributeError`. The plan's own criterion correctly forbids widening to `Exception`, which leaves the executor improvising on the phase's single most important security test — and the obvious improvisation (patch `is_whitelisted_client`) is fine, while the other one (widen the assertion) silently guts it.

**Fix:** one line. Add `setRequest(request)` with `setRequest(None)` in the `finally`, exactly as `test_unmatched_username_does_not_crash` does, and point `<read_first>` at *that* test as the shape rather than at line 52-70. With it bound, the path is clean: whitelist empty → `REMOTE_ADDR` absent → `helpers.py:502` returns `None` → `is_whitelisted_client` False → delegation → `source_users` authorises → `sign_user_data` (`pas_plugin.py:160`) → `get_or_create_secret` → `decrypt_seed`. The design is sound; only the instruction is incomplete.

### HIGH — The new `ValueError` is swallowed on the bulk-enable path, and no plan guards it

`helpers.py:432-439`:

```python
for user in users:
    try:
        get_or_create_secret(user)
        if not has_enabled_two_factor_authentication(user):
            user.setMemberProperties(mapping={'enable_two_factor_authentication': True})
    except Exception as e:
        logger.debug(str(e))
```

This is reached from `controlpanel.py:109-113` on **every** control-panel Save, because `globally_enabled` defaults to `True` (`controlpanel.py:41`) — and again from `@@google-authenticator-enable-for-all-users` (`controlpanel.py:86`). With the key missing or malformed, `get_or_create_secret` raises, the `except Exception` swallows it at DEBUG, the loop skips every user, and `controlpanel.py:121` then shows **"Changes saved."**

That is the exact silent-downgrade class this phase exists to eliminate, on what is plausibly the *first* thing an operator does before the Puppet fragment ships. Plan 03-01's prohibition P1 enumerates only `_get_fernet`, `encrypt_seed`, `decrypt_seed`, `get_secret`, `get_or_create_secret` — not the caller — and there is no acceptance criterion, threat row, or grep anywhere in the three plans that touches `helpers.py:438`.

**Fix:** add to plan 03-01 Task 3 — let `ValueError` out of that loop (or at minimum re-raise it and log at `error`/`critical`, and surface a failure status message instead of "Changes saved."), with a criterion like `grep -c "except Exception" helpers.py` pinned to its post-edit value. It is a two-line change in a file the plan already opens.

### MEDIUM-HIGH — Plan 03-02's `[instance] environment-vars` form is probably unparseable, and the unguided fallback is the risky one

`base.cfg:40-41` is:

```ini
environment-vars +=
    PYTHONBREAKPOINT pdbp.set_trace
```

i.e. whitespace-separated `NAME value`. Plan 03-02 Task 2(a) proposes an option reference "that itself defaults to an empty value … so a developer who supplies nothing gets an absent key and the Task-1 CRITICAL line rather than a buildout error." With an empty value the emitted line is the bare token `IMIO_GA_SEED_KEY`, and `plone.recipe.zope2instance` splits each line into exactly two parts — that is a buildout failure, not a graceful absence. The plan's own acceptance criterion (`grep -c "IMIO_GA_SEED_KEY" bin/instance >= 1`) then becomes unsatisfiable in the developer default case.

The plan does hedge ("fall back to the simplest thing that does and record which form you used") but names no fallback. The tempting one — a literal placeholder value — is the dangerous outcome: a production instance would then encrypt seeds under a repo-visible key and **never fire Task 1's CRITICAL log**, which is strictly worse than no key at all. Prohibition P3 forbids a *real* key in the repo; it does not forbid a *working* fake one.

There is also a precedent mismatch. `PROJECT.md:200-205` records the `SSO_APPS_CLIENT_SECRET` path as `industrialisation/.../buildout.pp:188` → **`server.dmsmail/base.cfg:102`** → `os.getenv()`. That is the *deployment* buildout, not the package's. Plan 03-02 puts the declaration in this package's `base.cfg` `[instance]`, diverging from the pattern it cites.

**Fix:** the lazy option is to not declare it in `[instance]` at all — keep `[testenv]` (needed for `bin/test`), and document in DOC-03 that the deployment buildout supplies `[instance]`'s copy, following `server.dmsmail/base.cfg:102`. If `[instance]` must carry it, add a prohibition: it must never hold a syntactically valid Fernet key.

### MEDIUM — `userCreatedHandler` is a third fail-closed surface: untested and undocumented

`userdataschema.py:90-93`:

```python
user = api.user.get(username=principal.getId())
if is_two_factor_authentication_globally_enabled():
    get_or_create_secret(user)
    user.setMemberProperties(mapping={'enable_two_factor_authentication': True,})
```

`globally_enabled` defaults True (`controlpanel.py:41`), so **every user creation** now goes through `encrypt_seed`. With no key, the `ValueError` propagates out of an `IPrincipalCreatedEvent` subscriber — the transaction aborts and the user record is rolled back, so registration and `api.user.create` stop working entirely.

That is defensible fail-closed behaviour, but it is a distinct blast radius from "login is refused", it has no test in any plan, and DOC-03 (plan 03-02 Task 2(c)) documents only enrollment and login failure. An operator reading the README would not learn that a missing key also means no new accounts.

**Fix:** one line in DOC-03's failure-mode list, and one assertion in plan 03-01 Task 4 (`assertRaises(ValueError, api.user.create, ...)` with the key unset) — the cheapest way to pin all three surfaces.

### MEDIUM — Two dropped threads from the phase's own inputs

- **ROADMAP Phase 3 success criterion 4** is "A user enrolls with a real authenticator app and logs in end to end." No plan contains a `checkpoint:human-verify` for it. Plan 03-01's `onetimepass.get_totp` round-trip is the closest thing, and it is not the same claim.
- **`STATE.md:106`** parks a Phase-3 item explicitly: "`browser/controlpanel.py` renders `ska_secret_key` into a form field. Pre-existing and untouched by Phase 2; it is the recorded Phase 3 secret-hygiene deferred idea." Confirmed at `controlpanel.py:28-34`. None of the three plans mentions it — not even to re-defer it with a reason.

By contrast, STATE.md's *other* Phase-3 carry-forward (the `02-SECURITY.md` R-02-02 ASCII assumption) is closed properly by plan 03-01's `test_ciphertext_is_a_safe_ska_key_component`. The asymmetry looks like an oversight rather than a decision.

### MEDIUM — Plan 03-03's standalone acceptance one-liner is a Python 2 `SyntaxError`

```
bin/python -c "... assert not v(u'é', 'abc'); print('ok')"
```

Python 2 rejects a non-ASCII byte in `-c` source with no encoding declaration: `SyntaxError: Non-ASCII character '\xc3' in file <string>`. The check fails before testing anything. Use `u'\xe9'`.

### MEDIUM-LOW — SEC-02's "per-call" property is asserted only by grep

Every fail-closed test in 03-01 and 03-02 injects by rebinding `helpers.get_encryption_key` / `subscribers.get_encryption_key` — which correctly exercises the *callers* but never proves the function reads `os.environ` fresh. The only evidence for the requirement's headline property is `grep ... "os.environ.get(ENV_VAR_NAME)" == 1`, which a module-scope `_KEY = os.environ.get(ENV_VAR_NAME)` would also satisfy. Three lines fix it: set the env var to key A, `encrypt_seed`; set it to key B; assert `decrypt_seed` raises — no rebinding.

### LOW-MEDIUM — Three criteria are brittle against the plans' own instructions

- Plan 03-02: `grep -cE "^ *(raise|try:|except)" subscribers.py == 0`, while the same task requires a docstring stating the handler "deliberately does **not** raise". Any wrapped docstring line beginning with `raise` fails the check.
- Plan 03-03: `grep -c "compare_digest" helpers.py == 2` (import + one call), while the same task asks for a docstring explaining the constant-time comparison. Same for `_to_unicode_ip( == 4` in plan 03-01.

Anchor these to code lines (e.g. filter `^\s*#` and docstring bodies) or state the count as a minimum.

### LOW-MEDIUM — Plan 03-02 Task 1's `bin/instance` check is order-dependent and its command is wrong

The criterion is `bin/instance -O Plone fg` "with `IMIO_GA_SEED_KEY` unset". Once Task 2(a) adds the variable to `[instance] environment-vars`, `bin/instance` always sets it and the check becomes irreproducible. Task 1 does precede Task 2, but the plan never says the check must be captured before Task 2 lands. Also `-O Plone` is not a `plone.recipe.zope2instance` flag; the invocation is `bin/instance fg`.

### LOW — The "incidentally drops Django" note asks the executor to assert something unverified

Plan 03-01 Task 3(b) tells the executor to record in the SUMMARY that "this phase incidentally drops Django from the resolved egg set", on the premise that `django-nine = 0.2.7` / `Django = 1.11.29` (`test-4.3.cfg:105`, `:113`) were reachable only through `rebus`. `django-nine` is `ska`'s Django-integration dependency (same author), and `ska>=1.1` stays in `install_requires` (`setup.py:61`). More likely the pins survive. Ask the executor to *check* (`bin/buildout` output, or `pkg_resources.get_distribution('rebus').requires()` before removal) rather than to assert.

### LOW — `Pillow` is a call-time dependency of `qrcode.make()` and lives only in `base.cfg`

`qrcode.make()` returns a `PilImage` whose `.save(buf, 'PNG')` needs Pillow. `Pillow` is in `base.cfg:27` `[buildout] eggs` but not in `setup.py install_requires`. Fine for this buildout and for any Plone deployment, but the dependency is now load-bearing on the enrollment path and undeclared. One line in `install_requires`, or a note.

## 4. Suggestions

1. **Move the `[testenv] IMIO_GA_SEED_KEY` line into plan 03-01** and adjust plan 03-02's `base.cfg` grep to `>= 2`. This is the smallest change that makes 03-01's own gate reachable.
2. **Add `setRequest(request)` / `setRequest(None)` to plan 03-01 Task 4**, and repoint `<read_first>` at `test_unmatched_username_does_not_crash` (`test_pas_plugin.py:72-95`) as the shape.
3. **Enumerate all five `get_or_create_secret` callers in plan 03-01's `<read_first>`** — `helpers.py:186` (`get_token_description`), `helpers.py:319` (`sign_user_data`), `helpers.py:434` (bulk enable), `userdataschema.py:92` (user creation), `reset_bar_code.py:155`. Then decide each one's fail-closed behaviour explicitly. Two of the five (`helpers.py:434`, `userdataschema.py:92`) are currently unconsidered, and one of those swallows.
4. **Unswallow `helpers.py:438`** and make the control-panel Save report failure instead of "Changes saved.", with a threat row and a criterion.
5. **Drop `[instance]` from plan 03-02, or forbid a valid placeholder there.** Document that the deployment buildout owns it, matching `server.dmsmail/base.cfg:102`.
6. **Add one behavioural SEC-02 test** (mutate `os.environ`, not the function) and one `api.user.create` fail-closed assertion.
7. **Add a `checkpoint:human-verify` to plan 03-03** for ROADMAP criterion 4 (real authenticator app, end to end) — it is the last plan of the phase and the natural place, alongside the restatement of the Puppet dependency the plan already schedules there.
8. **Re-defer or address `STATE.md:106`** (`ska_secret_key` in a control-panel field) in writing, so the thread is closed rather than lost.
9. Fix the `u'é'` literal (`u'\xe9'`), the `bin/instance -O Plone fg` invocation, and the three docstring-fragile greps.

## 5. Risk Assessment

**Overall: MEDIUM-HIGH.**

The design is right and the research is unusually well-verified against the tree — I did not find a single wrong line citation of consequence, the `v1$` envelope and `str`/`unicode` discipline are correct for CPython 2.7, the three-call-site `ipaddress` correction closes a real bypass, and the fail-closed architecture (raise in `helpers.py`, propagate through `_dont_swallow_my_exceptions` at `pas_plugin.py:71`) is sound.

The risk is concentrated and fixable. Two of the three HIGH findings are execution blockers that surface loudly (a red suite, a wrong-exception-type test) — annoying but self-announcing, and each is a one-to-three-line fix. The third is the one that matters: `helpers.py:438`'s `except Exception: logger.debug(str(e))`, reachable from `controlpanel.py:112` on every Save with `globally_enabled` defaulting True, turns a missing key into **"Changes saved." with zero users enrolled**. That is the same silent-security-control-removal shape as the CR-02 abort bug Phase 2 fixed and the `_dont_swallow_my_exceptions` gap Phase 1 fixed, in the one file this phase rewrites, and no prohibition, threat row, or grep in any of the three plans touches it. A phase whose stated thesis is "fail-closed is the one mistake that silently undoes everything" should not ship with an unexamined `except Exception` on the enrollment path.

With items 1–4 folded in, I would put this at LOW-MEDIUM and consider it ready to execute.

---

## Consensus Summary

**No consensus is available.** One prompt-fed reviewer completed and it shares a model
family with the planner, so nothing below is corroborated by a second independent system.
This section records what the single reviewer found and how much weight each finding
carries on its own evidence — not agreement.

### Findings that stand on verifiable evidence (highest priority)

These cite specific source lines and a concrete failure mechanism, so they are checkable
without a second reviewer. Verify each against the tree before acting.

1. **HIGH — `helpers.py:438`'s `except Exception: logger.debug(str(e))` swallows the new
   `ValueError` on the bulk-enable path.** Reachable from `controlpanel.py:112` on *every*
   control-panel Save (`globally_enabled` defaults `True` at `controlpanel.py:41`), and from
   `@@google-authenticator-enable-for-all-users` at `controlpanel.py:86`. With the key
   missing, every user is skipped and `controlpanel.py:121` still reports **"Changes saved."**
   No prohibition, threat row, or grep in any of the three plans touches this line. This is
   the same silent-control-removal shape Phase 1 and Phase 2 each had to fix, in the one
   file this phase rewrites — and it lands on the most likely first operator action before
   the Puppet fragment ships.

2. **HIGH — Plan 03-01's own `bin/test -t '!robot'` gate is unsatisfiable as written.**
   `test_generic.py:43-47` renders `SetupForm` → `user_setup.py:108` →
   `helpers.py:186 get_or_create_secret`, and TEST_USER is created by `PLONE_FIXTURE`
   *before* this package's ZCML loads, so `userCreatedHandler` never fired and the property
   is empty → `encrypt_seed` → `ValueError`. The `IMIO_GA_SEED_KEY` that would satisfy it
   reaches `bin/test` only via `base.cfg [testenv]`, which **plan 03-02 adds in Wave 2**.
   Wave 1 therefore ends on a red suite, on the phase's headline plan, forcing a deviation
   on a file not in `files_modified`.

3. **HIGH — Plan 03-01 Task 4's PAS test crashes before reaching the crypto path.**
   `pas_plugin.py:91` calls `is_whitelisted_client()` with no argument →
   `helpers.py:467-470` → `getRequest()` returns `None` → `AttributeError`. The plan points
   `<read_first>` at `test_pas_plugin.py:52-70`, which monkeypatches `is_whitelisted_client`
   away and so hides this. `assertRaises(ValueError, ...)` would see `AttributeError`; the
   plan correctly forbids widening to `Exception`, which leaves the executor improvising on
   the phase's single most important security test. One-line fix: `setRequest(request)` /
   `setRequest(None)`, per the already-documented shape at `test_pas_plugin.py:72-95`.

4. **MEDIUM — Two more `get_or_create_secret` callers were never enumerated.**
   `userdataschema.py:92` (every user creation, `globally_enabled` default `True`) means a
   missing key also stops **account creation entirely** — defensible fail-closed, but a
   different blast radius from "login refused", untested, and absent from DOC-03's
   failure-mode list.

5. **MEDIUM — Two threads dropped from the phase's own inputs.** ROADMAP success
   criterion 4 ("enrolls with a real authenticator app and logs in end to end") has no
   `checkpoint:human-verify` in any plan. And `STATE.md:106` explicitly parks a Phase-3
   item — `controlpanel.py:28-34` rendering `ska_secret_key` into a form field — which no
   plan mentions, not even to re-defer it.

Lower-severity items (an `[instance] environment-vars` syntax risk, a Python 2 `SyntaxError`
in a `bin/python -c` acceptance one-liner, three docstring-fragile grep counts, an
unverified "drops Django" claim, undeclared `Pillow`) are in the full review above.

### What the reviewer confirmed rather than criticised

Recorded because it narrows what a second reviewer would need to re-check: ~40 `file:line`
citations were verified against the tree with no consequential error; the three-call-site
`ipaddress` correction closes a **real** whitelist bypass (`helpers.py:482-488`'s
`except ValueError: break` sits directly on `ip_address(proxies[0])`, and
`AddressValueError` subclasses `ValueError`); the `str`/`unicode` discipline is correct at
every boundary checked, including memberdata `type="string"` coercion of the ASCII
ciphertext; `rebus` has exactly two references so the drop is clean; and requirement
coverage is exactly the 12 IDs with no duplicates.

### Divergent views

None recordable — a single reviewer cannot diverge. **This is the gap in this run**, not a
sign of agreement. Restoring a second, different-family lane (gemini auth, or a `codex`
install) is what would make the HIGH findings above either corroborated or contested.

### Reviewer verdict

**MEDIUM-HIGH risk**, reducing to **LOW-MEDIUM** with findings 1–4 folded in. The reviewer's
own summary: *"A phase whose stated thesis is 'fail-closed is the one mistake that silently
undoes everything' should not ship with an unexamined `except Exception` on the enrollment
path."*
