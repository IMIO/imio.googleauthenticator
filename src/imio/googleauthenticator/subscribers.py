"""
Two event-driven handlers: an ``IProcessStarting`` subscriber that makes an
absent seed-encryption key loud at Zope boot, instead of latent until the
first enrollment or login attempt (SEC-08); and an ``IPubBeforeCommit``
subscriber that drives the 2FA redirect for the login-form POST path, which
returns HTTP 200 and never raises (MFA-02/COEX-08).
"""
from imio.googleauthenticator.helpers import get_encryption_key
from imio.googleauthenticator.pas_plugin import REQUEST_KEY_PENDING
from imio.googleauthenticator.pas_plugin import send_2fa_redirect
from zope.component import adapter
from ZPublisher.interfaces import IPubBeforeCommit

import logging


logger = logging.getLogger("imio.googleauthenticator")


def on_process_starting(event):
    """
    Logs one CRITICAL line naming ``IMIO_GOOGLEAUTHENTICATOR_SEED_KEY`` when
    :func:`get_encryption_key` returns a falsy value, and deliberately does
    **not** raise: a raise on this startup path would also break
    ``bin/instance debug`` and ``bin/test``, which is strictly worse than a
    loud log line nobody can miss. Re-reads the environment through
    :func:`get_encryption_key` on every call rather than caching, matching
    the per-call design plan 03-01 established for the same variable.

    :param zope.processlifetime.IProcessStarting event: Unused; this
        handler inspects no state on the event itself.
    """
    if not get_encryption_key():
        logger.critical(
            'IMIO_GOOGLEAUTHENTICATOR_SEED_KEY is not set; seed encryption '
            'and decryption will fail closed on every enrollment and login '
            'attempt until it is set.')


@adapter(IPubBeforeCommit)
def redirect_pending_2fa(event):
    """
    Drives the 2FA redirect for a login-form POST. ``IPubBeforeCommit``
    fires after ``mapply()`` has already called ``response.setBody(result)``
    and before ``transactions_manager.commit()``
    (``ZPublisher/Publish.py:134-146``) -- the only hook that can still
    intervene on a login POST that never raises ``Unauthorized`` and so
    never reaches a challenge plugin.

    The pending signal is read from ``request.other`` only, never via the
    request's general accessor method: that method falls through to
    environment, ``other``, form data, then cookies
    (``ZPublisher/HTTPRequest.py:1245-1256``), which would turn an internal
    signal into attacker-controlled input -- a forged
    ``?_2fa_pending=1&_2fa_user_id=<victim>`` on any anonymous request
    would otherwise reach ``sign_user_data``.

    ``send_2fa_redirect`` reaches ``sign_user_data`` -> ``get_or_create_
    secret``, which writes memberdata only for a 2FA-enabled user who
    somehow has no seed yet -- pre-existing behaviour relocated from
    ``authenticateCredentials``, not introduced here, and fail-closed
    either way: a discarded mint on an aborted transaction yields a
    signature the token form then rejects. Beyond that one call, this
    handler performs no other write of its own: Phase 5's MFA-12 depends
    on this plugin boundary being write-free from day one.

    :param ZPublisher.interfaces.IPubBeforeCommit event: Exposes the
        in-flight ``request`` this hook acts on.
    """
    request = event.request
    if not request.other.get(REQUEST_KEY_PENDING):
        return

    send_2fa_redirect(request, request.response)
