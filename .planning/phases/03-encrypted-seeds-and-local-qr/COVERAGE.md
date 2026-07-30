No external API integration: this phase *removes* the package's only outbound HTTP call (the `chart.googleapis.com` QR GET) and replaces it with in-process `qrcode == 6.1` rendering.

Everything else it touches is local — `cryptography.fernet` (in-process symmetric crypto), `os.environ` (process environment), `ipaddress` (pure-Python parsing), memberdata properties (ZODB) and buildout/`setup.py` pins. No SDK is initialised, no endpoint is called, no credential is exchanged with a third party.

Detector result for the phase scope (ROADMAP §Phase 3 + 03-RESEARCH.md + 03-PATTERNS.md): `{"detected":false,"signals":[]}`.

Note for the seal-time re-run: `otpauth://totp/...` appears in `helpers.get_barcode_image` and looks URL-shaped, but it is a QR *payload* string built and consumed in-process — it is never dereferenced, and after this phase no code path in the package issues an outbound request. `SEC-05`'s acceptance criteria assert exactly that (no `googleapis` host in the returned data URI, no subprocess invoked from `helpers.py`).
