No external API integration: Phase 5 adds TOTP clock-drift tolerance, replay rejection, and a
failure-count lockout. Every mechanism it touches runs inside the Plone process — `onetimepass`
(TOTP arithmetic), `ska` (URL signing), memberdata properties and `plone.registry` (ZODB), and
two z3c.form browser views (`browser/forms/token.py`, `browser/forms/reset_bar_code.py`). No SDK
is initialised, no remote host is contacted, no credential is exchanged with a third party.

Grep evidence at the phase's final commit: searching non-test source under
`src/imio/googleauthenticator/` for `urllib|httplib|requests\.|urlopen|googleapis|http://|https://`
returns exactly one hit, `helpers.py:6: from urllib import unquote, quote`. That is URL string
encoding and decoding, not a network call. The package has had no outbound HTTP call since Phase 3
replaced the `chart.googleapis.com` QR GET with in-process `qrcode == 6.1` rendering.

Detector result for the phase scope before this file existed:
`{"detected":true,"signals":[{"verb":"consuming","noun":"endpoint"}]}` — a false positive. Both
words come from prose about in-process code paths, not about an external service. The clearest
source is `05-05-PLAN.md:339`, threat T-05-24: "would let a locked account keep **consuming** TOTP
arithmetic against its stored seed at an anonymously reachable **endpoint**". The endpoint named
there is the Plone view `@@reset-bar-code`, reachable over the site's own HTTP surface; "consuming"
describes the server spending TOTP comparisons, not a client consuming a remote API. The phase text
uses "endpoint" throughout to mean one of this package's two browser views.

Same conclusion as Phase 3's COVERAGE.md, reached for the same reason: this package is an
authentication plugin that computes locally. `otpauth://totp/...` in `helpers.get_barcode_image`
still looks URL-shaped, and is still only a QR payload string built and consumed in-process, never
dereferenced.
