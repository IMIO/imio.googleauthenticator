"""
Tests for the Google Authenticator control panel form.
"""
from imio.googleauthenticator.browser.controlpanel import GoogleAuthenticatorSettingsEditForm
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import unittest2 as unittest


class TestGoogleAuthenticatorSettingsEditForm(unittest.TestCase, BaseTest):
    """COEX-04: the control-panel half of the "Extra" fragment conversion.

    Before this phase, ``GoogleAuthenticatorSettingsEditForm.render()``
    reached its "Extra" fragment (the enable-for-all-users /
    disable-for-all-users links) through
    ``self.context.restrictedTraverse('control_panel_extra')`` -- a lookup
    against the ``googleauthenticator_custom`` skin layer this plan's own
    commit deletes. Nothing in the existing suite called ``render()``:
    ``test_bulk_enable_reports_failure_when_seed_key_is_broken`` in
    ``test_helpers.py`` instantiates this same form and drives ``update()``
    and ``handleSave``, never ``render()``. So this fragment had **zero**
    coverage before this test -- deleting the skin directory without
    converting the lookup to a ``ViewPageTemplateFile`` class attribute
    would have broken the control panel with nothing in ``bin/test``
    noticing. ``render()`` is the method under test.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()

    def test_render_appends_the_extra_links(self):
        # The control panel requires cmf.ManagePortal, exactly as
        # test_bulk_enable_reports_failure_when_seed_key_is_broken does.
        setRoles(self.portal, TEST_USER_ID, ['Manager'])

        form = GoogleAuthenticatorSettingsEditForm(self.portal, self.request)
        form.update()

        # Non-vacuity control: the parent class's own render(), with no
        # fragment appended, called the same way our render() override
        # calls it internally (``res = super(...).render(...)``). Proves
        # the fragment was actually appended below, rather than the base
        # form happening to already contain a matching substring.
        base_result = super(
            GoogleAuthenticatorSettingsEditForm, form).render()
        full_result = form.render()

        self.assertTrue(
            full_result.startswith(base_result),
            'COEX-04: render() must append the "Extra" fragment after the '
            'base form output, not replace or reorder it.')
        self.assertGreater(
            len(full_result), len(base_result),
            'COEX-04: render() must actually append something -- an '
            'unchanged length would mean the fragment was dropped.')

        enable_url = '{0}/@@google-authenticator-enable-for-all-users'.format(
            self.portal.absolute_url())
        disable_url = '{0}/@@google-authenticator-disable-for-all-users'.format(
            self.portal.absolute_url())

        self.assertIn(
            enable_url, full_result,
            'COEX-04: the enable-for-all-users URL must be reachable from '
            'the rendered control panel.')
        self.assertIn(
            disable_url, full_result,
            'COEX-04: the disable-for-all-users URL must be reachable from '
            'the rendered control panel.')
        self.assertIn(
            'Enable two-step verification for all users', full_result,
            'COEX-04: the enable link text must be present.')
        self.assertIn(
            'Disable two-step verification for all users', full_result,
            'COEX-04: the disable link text must be present.')
