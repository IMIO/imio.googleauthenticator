import unittest2 as unittest

from Products.CMFCore.utils import getToolByName

from plone import api
from plone.app.testing import applyProfile

from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.helpers import get_ska_secret_key
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest


class TestSetupHandlers(unittest.TestCase, BaseTest):
    """Integration-layer assertions for setupVarious and the import-step
    ordering it depends on.

    One class, one test method (test_setupVarious) carrying several assertion
    groups rather than one method per requirement: the ordering assertion
    tests a ZCML declaration and the mint assertion tests a helpers.py
    function, but both are observable properties of *applying this profile*,
    whose handler is setupVarious -- hence one file, one class, one method,
    several assertion groups (R5).
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        self._install()

    def test_setupVarious(self):
        """Assertion groups, in the order the requirements were written:

        - ORDERING (REG-03): imio.googleauthenticator's import step sorts
          after plone.app.registry -- this is what catches someone deleting
          the <depends> declaration.
        - RECORDS (REG-01/REG-02 outcome): after the default profile is
          applied, all three IGoogleAuthenticatorSettings records exist and
          get_app_settings() returns without raising.
        - NO INSTALL-TIME SEEDING (REG-04): immediately after install,
          ska_secret_key is still the schema default u'' -- nothing seeds it
          during the import step any more.
        - LAZY MINT (REG-04): the first call to get_ska_secret_key() mints
          and persists a non-empty key; a second call returns that same key
          rather than re-rolling it.
        - REG-05 REGRESSION GUARD, not a live bug fix: ska_secret_key is
          TextLine(required=False, default=u''), so an existing non-empty
          unicode value revalidates cleanly on profile re-import today, and
          the "bare <records interface=...> replaces the value with the
          field default on re-import" hole does not fire. It would fire the
          day someone adds required=True or a constraint to that field,
          which is what this group guards against.
        """
        portal_setup = getToolByName(self.portal, 'portal_setup')

        # ORDERING (REG-03)
        steps = portal_setup.getSortedImportSteps()
        self.assertGreater(
            steps.index('imio.googleauthenticator'),
            steps.index('plone.app.registry'),
            'REG-03: imio.googleauthenticator must sort after plone.app.registry')

        # RECORDS (REG-01/REG-02 outcome)
        settings = get_app_settings()
        self.assertIsNotNone(
            settings.globally_enabled,
            'REG-01/REG-02: globally_enabled record must exist after install')
        self.assertIsNotNone(
            settings.ip_addresses_whitelist,
            'REG-01/REG-02: ip_addresses_whitelist record must exist after install')

        # NO INSTALL-TIME SEEDING (REG-04)
        self.assertEqual(
            u'', get_app_settings().ska_secret_key,
            'REG-04: install must not seed ska_secret_key; it stays the schema default')

        # LAZY MINT (REG-04)
        get_ska_secret_key(
            request=self.request, user=api.user.get_current(), use_browser_hash=False)
        minted = get_app_settings().ska_secret_key
        self.assertTrue(
            minted,
            'REG-04: first get_ska_secret_key() call must mint a non-empty key')
        get_ska_secret_key(
            request=self.request, user=api.user.get_current(), use_browser_hash=False)
        self.assertEqual(
            minted, get_app_settings().ska_secret_key,
            'REG-04: second get_ska_secret_key() call must not re-mint the key')

        # REG-05 regression guard: a profile re-apply must not replace an
        # existing ska_secret_key with the field default. Not a live bug fix
        # (see docstring) -- the assertion is equality against the same known
        # literal set below, not mere non-emptiness, which would pass against
        # a fresh re-mint and prove nothing.
        known_value = u'known-test-value-for-reg-05'
        get_app_settings().ska_secret_key = known_value
        applyProfile(self.portal, 'imio.googleauthenticator:default')
        self.assertEqual(
            known_value, get_app_settings().ska_secret_key,
            'REG-05: re-applying the default profile must not reset ska_secret_key')
