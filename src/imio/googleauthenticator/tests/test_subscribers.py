"""
Direct-call tests for ``subscribers.on_process_starting`` (SEC-08). No
layer: the handler touches no Zope state -- its only argument is an event
nobody inspects.
"""
from cryptography.fernet import Fernet
from imio.googleauthenticator import helpers
from imio.googleauthenticator import subscribers

import imio.googleauthenticator
import os
import unittest2 as unittest
import xml.dom.minidom


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

    def test_seed_key_is_present_in_the_test_environment(self):
        """SEC-07: this method deliberately asserts on ``os.environ`` rather
        than setting it -- the opposite of every other test in this phase.
        That is the point: it is the only assertion in the suite that fails
        if ``base.cfg``'s ``[testenv]`` regresses, and it is what turns
        SEC-07's CI-inheritance slot into an observation rather than an
        assumption. Do not "fix" this into a self-contained test that sets
        its own key -- that would delete the signal.
        """
        key = os.environ.get(helpers.ENV_VAR_NAME)
        self.assertTrue(
            key,
            'SEC-07-empty boundary: base.cfg [testenv] must declare a '
            'non-empty {0}'.format(helpers.ENV_VAR_NAME))

        # A declared-but-unusable value is the failure this catches -- the
        # same assertion that proves CI inherits a usable key, not merely a
        # variable name.
        Fernet(key)

        # SEC-07 adjacency / the ZEO-skew failure mode, mechanised: a
        # ciphertext from a different key must not decrypt under this one.
        foreign_key = Fernet.generate_key()
        foreign_token = Fernet(foreign_key).encrypt(b'unrelated-seed')
        foreign_ciphertext = u'{0}{1}'.format(
            helpers.CIPHERTEXT_VERSION_PREFIX, foreign_token.decode('ascii'))
        self.assertRaises(
            ValueError, helpers.decrypt_seed, foreign_ciphertext)

    def test_instance_section_declares_no_seed_key(self):
        """T-03-21b / SEC-07's other half: ``base.cfg``'s ``[instance]`` must
        carry no key, and nothing asserted that until now.

        The threat is rated `high` and is specifically the *tempting* edit: a
        syntactically valid placeholder added so the buildout parses. That
        would encrypt every production seed under a value any reader of this
        repository has, **and** suppress the CRITICAL warning that is supposed
        to announce a missing key -- because the key would no longer be
        absent. Loud failure becomes silent compromise.

        Until this test existed the invariant was held only by plan 03-02's
        prohibition P6 and a one-time grep at execution, neither of which
        survives into CI. ``README.rst`` documents the omission and its
        reasoning; this is the assertion that keeps the documentation true.

        Read as text rather than via ConfigParser: buildout's ``+=`` keys and
        ``${...}`` references are not INI, and ConfigParser's interpolation
        raises on them.
        """
        base_cfg = os.path.join(
            os.path.dirname(imio.googleauthenticator.__file__),
            os.pardir, os.pardir, os.pardir, 'base.cfg')
        self.assertTrue(
            os.path.exists(base_cfg),
            'base.cfg not found at {0} -- if the repository layout moved, '
            'fix this path rather than deleting the test'.format(base_cfg))

        with open(base_cfg) as handle:
            lines = handle.read().splitlines()

        def section(name):
            """Returns the raw lines of one buildout section."""
            out, inside = [], False
            for line in lines:
                if line.startswith('['):
                    if inside:
                        break
                    inside = line.strip() == '[{0}]'.format(name)
                    continue
                if inside:
                    out.append(line)
            return out

        # Non-vacuity control, and it has to come first: if the reader above
        # silently returned nothing, the real assertion below would pass for
        # the wrong reason. [testenv] is known to declare the key.
        self.assertIn(
            helpers.ENV_VAR_NAME, '\n'.join(section('testenv')),
            'The section reader found nothing in [testenv], so the '
            '[instance] assertion below would be vacuous.')

        self.assertNotIn(
            helpers.ENV_VAR_NAME, '\n'.join(section('instance')),
            'base.cfg [instance] must NOT declare {0} (T-03-21b): the '
            'deployment buildout owns that copy. A placeholder here ships a '
            'repo-readable production key and silences the missing-key '
            'CRITICAL log.'.format(helpers.ENV_VAR_NAME))
