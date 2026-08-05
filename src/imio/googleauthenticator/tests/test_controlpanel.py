"""
Tests for the Google Authenticator control panel form.
"""
from imio.googleauthenticator.browser.controlpanel import GoogleAuthenticatorSettingsEditForm
from imio.googleauthenticator.helpers import get_or_create_secret
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from Products.statusmessages.interfaces import IStatusMessage

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

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

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

    def _fill_required_save_widgets(self, form):
        """``max_failed_attempts``/``lockout_duration`` are ``Int``,
        ``required=True``. With no request value for either,
        ``handleSave``'s own ``extractData()`` call reports a
        ``RequiredMissing`` error for each and returns before ever
        reaching the ``globally_enabled`` branch this task's tests target
        -- both must be filled for ``handleSave`` to run past that guard.
        """
        widgets = form.groups[0].widgets
        self.request.form[widgets['max_failed_attempts'].name] = u'5'
        self.request.form[widgets['lockout_duration'].name] = u'900'

    def test_bulk_disable_view_reports_info_and_disables_an_enabled_user(self):
        """T-08-13/QUAL-04: the bulk disable view had zero tests before
        this method (56% coverage, plan 08-01's baseline). Copies the
        already-tested enable sibling's call shape verbatim (PATTERNS.md)
        so the two are easy to diff against each other, and asserts the
        *effect* on a real user, not only the message: this view only
        touches users for whom 2FA is currently enabled
        (``disable_two_factor_authentication_for_users``), so the
        precondition below matters.
        """
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        get_or_create_secret(user, overwrite=True)
        self.assertTrue(
            user.getProperty('enable_two_factor_authentication'),
            'precondition: the user must start enabled, or the '
            'disabled-after assertion below is vacuous')

        IStatusMessage(self.request).show()  # drain prior messages
        view = self.portal.restrictedTraverse(
            '@@google-authenticator-disable-for-all-users')
        view.request = self.request
        view.index()

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('info', types)

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertFalse(
            refetched_user.getProperty('enable_two_factor_authentication'),
            'T-08-13: the bulk disable view must actually disable a '
            'previously-enabled user, not only report success.')

    def test_handleSave_globally_disabled_applies_changes_without_disabling_anyone(self):
        """QUAL-04: the ``globally_enabled is False`` branch's bulk-disable
        call is commented out today (deferred MFA-14-adjacent behaviour,
        out of scope per this plan's own prohibition) -- it logs and falls
        through to applying changes. This asserts exactly that: the
        settings change is applied (an ``'info'`` changes-saved message
        and the control-panel redirect) and no user is disabled as a side
        effect of saving.
        """
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': True})
        flag_before = user.getProperty('enable_two_factor_authentication')

        form = GoogleAuthenticatorSettingsEditForm(self.portal, self.request)
        form.update()
        widget_name = form.groups[0].widgets['globally_enabled'].name
        # An unchecked single checkbox submits no value for its own name,
        # only the hidden "-empty-marker" sibling z3c.form renders beside
        # it -- this is what distinguishes "unchecked" from "field absent
        # entirely" (the neither-branch test below).
        self.request.form[widget_name + '-empty-marker'] = u'1'
        self._fill_required_save_widgets(form)

        IStatusMessage(self.request).show()  # drain prior messages
        handleSave = GoogleAuthenticatorSettingsEditForm.handleSave.func
        handleSave(form, None)

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('info', types)
        self.assertNotIn('error', types)
        location = self.request.response.getHeader('location')
        self.assertTrue(
            location and location.endswith('/plone_control_panel'),
            'got {0!r}'.format(location))

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertEqual(
            flag_before,
            refetched_user.getProperty('enable_two_factor_authentication'),
            'QUAL-04: saving with globally_enabled=False must not disable '
            'any user -- the bulk-disable call in that branch is '
            'deliberately commented out.')

    def test_handleSave_neither_true_nor_false_applies_changes_without_enrolling_anyone(self):
        """QUAL-04: when no ``globally_enabled`` value is present in the
        extracted data at all (the widget's name and its empty-marker are
        both absent from the request -- a state a browser never submits,
        but ``data.get('globally_enabled', None)`` must still tolerate),
        both the enable and disable branches are skipped and the handler
        goes straight to applying changes.
        """
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        user = api.user.get_current()
        user.setMemberProperties(
            mapping={'enable_two_factor_authentication': False})

        form = GoogleAuthenticatorSettingsEditForm(self.portal, self.request)
        form.update()
        self._fill_required_save_widgets(form)

        IStatusMessage(self.request).show()  # drain prior messages
        handleSave = GoogleAuthenticatorSettingsEditForm.handleSave.func
        handleSave(form, None)

        types = [m.type for m in IStatusMessage(self.request).show()]
        self.assertIn('info', types)
        self.assertNotIn('error', types)
        location = self.request.response.getHeader('location')
        self.assertTrue(
            location and location.endswith('/plone_control_panel'),
            'got {0!r}'.format(location))

        refetched_user = api.user.get(username=TEST_USER_NAME)
        self.assertFalse(
            refetched_user.getProperty('enable_two_factor_authentication'),
            'QUAL-04: the neither-branch must not enable 2FA for anyone.')
