"""
IProcessStarting subscriber that makes an absent seed-encryption key loud at
Zope boot, instead of latent until the first enrollment or login attempt
(SEC-08).
"""
import logging

from imio.googleauthenticator.helpers import get_encryption_key

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
