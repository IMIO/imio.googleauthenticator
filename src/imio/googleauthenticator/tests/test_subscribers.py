"""
Direct-call tests for ``subscribers.on_process_starting`` (SEC-08). No
layer: the handler touches no Zope state -- its only argument is an event
nobody inspects.
"""
import os
import unittest2 as unittest
import xml.dom.minidom

import imio.googleauthenticator
from imio.googleauthenticator import subscribers


class _StubLogger(object):
    """Records ``critical()`` calls in place of the real module logger."""

    def __init__(self):
        self.critical_calls = []

    def critical(self, *args, **kwargs):
        self.critical_calls.append((args, kwargs))


class TestOnProcessStarting(unittest.TestCase):

    def test_on_process_starting(self):
        """SEC-08: CRITICAL exactly once when the key is absent or an
        empty string, never when it is present, and never a raise in any
        of the three cases. Also proves the handler never touches the
        event it is passed (a bare ``object()``), and that the ZCML
        registration wiring it to ``IProcessStarting`` still exists and
        still parses.
        """
        original_logger = subscribers.logger
        original_get_key = subscribers.get_encryption_key
        try:
            # Key absent.
            stub_logger = _StubLogger()
            subscribers.logger = stub_logger
            subscribers.get_encryption_key = lambda: None
            subscribers.on_process_starting(object())
            self.assertEqual(1, len(stub_logger.critical_calls))
            message = stub_logger.critical_calls[0][0][0]
            self.assertIn('IMIO_GOOGLEAUTHENTICATOR_SEED_KEY', message)

            # Key present.
            stub_logger = _StubLogger()
            subscribers.logger = stub_logger
            subscribers.get_encryption_key = lambda: 'anything-non-empty'
            subscribers.on_process_starting(object())
            self.assertEqual(0, len(stub_logger.critical_calls))

            # Key present but empty: the SEC-07-empty boundary. A
            # declared-with-no-value entry must be exactly as loud as an
            # absent one.
            stub_logger = _StubLogger()
            subscribers.logger = stub_logger
            subscribers.get_encryption_key = lambda: ''
            subscribers.on_process_starting(object())
            self.assertEqual(1, len(stub_logger.critical_calls))
        finally:
            subscribers.logger = original_logger
            subscribers.get_encryption_key = original_get_key

        # Wiring: parsed with xml.dom.minidom rather than substring-matched,
        # so this also proves configure.zcml is still well-formed after the
        # edit, and fails the suite if the registration is ever deleted.
        package_dir = os.path.dirname(imio.googleauthenticator.__file__)
        dom = xml.dom.minidom.parse(
            os.path.join(package_dir, 'configure.zcml'))
        matches = [
            element for element in dom.getElementsByTagName('subscriber')
            if element.getAttribute('for') == 'zope.processlifetime.IProcessStarting'
            and element.getAttribute('handler') == '.subscribers.on_process_starting'
        ]
        self.assertEqual(1, len(matches))
