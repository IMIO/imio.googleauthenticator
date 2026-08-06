"""
Tests for ``browser/settings_helper.py`` (D-10, D-11, D-15, MFA-17, MFA-18).

This module does not exist before this plan and there is zero coverage of
``browser/settings_helper.py`` today -- this is new ground, not an
extension. Follows the WR-03 convention this suite uses throughout (one
test method per requirement, grouped by concern), the convention chosen
over the ``plone-write-tests`` skill's one-assertion-per-tested-method
rule in plan 07-01 and reaffirmed in Phase 9. Do not switch conventions.
"""
from imio.googleauthenticator.browser.settings_helper import SettingsHelper
from imio.googleauthenticator.helpers import get_app_settings
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from plone import api
from plone.app.testing import login
from plone.app.testing import TEST_USER_NAME
from plone.testing import z2
from Products.CMFCore.utils import getToolByName

import unittest2 as unittest


class TestSettingsHelper(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.portal_url = api.portal.get().absolute_url()
        # This layer does not isolate registry or member-data writes per
        # test method (tests/test_user_setup.py:129-143,
        # tests/test_token.py:54-75 document the same hazard for their own
        # properties) -- record the incoming value here and restore it in
        # tearDown, rather than letting one test's setting leak into the
        # next.
        self._saved_globally_enabled = get_app_settings().globally_enabled

    def tearDown(self):
        get_app_settings().globally_enabled = self._saved_globally_enabled
        user = api.user.get_current()
        if user is not None and not api.user.is_anonymous():
            user.setMemberProperties(mapping={
                'enable_two_factor_authentication': False,
                'two_factor_authentication_enrolled': False,
                })

    def _set_state(self, globally_enabled, enabled, enrolled):
        """Fixture helper: sets one combination of (globally_enabled, the
        enable flag, enrollment-completed) for the current user.

        Writes through ``api.user.get_current()``, not a separately
        fetched ``api.user.get(username=...)`` object -- the two are
        different MemberData wrappers within the same request, and a
        write through the latter is not visible through the former until
        a transaction boundary, which this test layer does not cross
        between fixture setup and the assertion.
        """
        get_app_settings().globally_enabled = globally_enabled
        user = api.user.get_current()
        user.setMemberProperties(mapping={
            'enable_two_factor_authentication': enabled,
            'two_factor_authentication_enrolled': enrolled,
            })
        return user

    def _conditions(self):
        """Fixture helper: the three SettingsHelper booleans as a tuple.
        Asserting tuples makes a failure name which of the three
        conditions moved.
        """
        helper = SettingsHelper(self.portal, self.request)
        return (
            helper.show_enable_two_factor_authentication_link(),
            helper.show_disable_two_factor_authentication_link(),
            helper.show_regenerate_recovery_codes_link(),
            )

    def test_enable_link_is_offered_to_a_user_who_has_not_completed_enrollment(self):
        """D-10/MFA-17: the install-enrolled case specifically -- flag set
        by install-time bulk enrollment, enrollment not yet completed,
        globally_enabled on. RESEARCH.md's suggested
        ``not has_enabled_two_factor_authentication`` shape would return
        False here, hiding enrollment from every account install just
        enrolled. A future reader simplifying this condition back to the
        flag will look here first.
        """
        self._set_state(globally_enabled=True, enabled=True, enrolled=False)
        enable, _disable, _regenerate = self._conditions()
        self.assertTrue(
            enable,
            'D-10: the enable link must be offered to an install-enrolled '
            'user who has not completed enrollment.')

    def test_enable_link_is_offered_whatever_the_global_setting_says(self):
        """MFA-18: the same unenrolled user, setting on and then off --
        both must offer the link. This is the assertion that fails if
        anyone reintroduces a global-setting term into this condition.

        Also exercises SettingsHelper's own pre-existing
        ``is_two_factor_authentication_globally_enabled`` passthrough
        (registered separately as the
        ``is-two-factor-authentication-globally-enabled`` view) while the
        setting is toggled here anyway -- it had zero coverage before
        this module existed.
        """
        self._set_state(globally_enabled=True, enabled=False, enrolled=False)
        helper = SettingsHelper(self.portal, self.request)
        self.assertTrue(helper.is_two_factor_authentication_globally_enabled())
        enable_on, _d1, _r1 = self._conditions()
        self.assertTrue(enable_on, 'MFA-18: offered with the setting on.')

        self._set_state(globally_enabled=False, enabled=False, enrolled=False)
        helper = SettingsHelper(self.portal, self.request)
        self.assertFalse(helper.is_two_factor_authentication_globally_enabled())
        enable_off, _d2, _r2 = self._conditions()
        self.assertTrue(enable_off, 'MFA-18: offered with the setting off.')

    def test_disable_link_is_offered_only_when_enrolled_and_globally_disabled(self):
        """D-11: all four combinations of (globally_enabled, flag) in one
        method, asserting the single True cell and the three False ones.
        Three-way negative coverage is what distinguishes a correct
        condition from one that is merely True in the one case a
        happy-path test checks.
        """
        self._set_state(globally_enabled=False, enabled=True, enrolled=True)
        _e1, disable, _r1 = self._conditions()
        self.assertTrue(
            disable, 'globally_enabled off, flag set: must be offered.')

        self._set_state(globally_enabled=True, enabled=True, enrolled=True)
        _e2, disable, _r2 = self._conditions()
        self.assertFalse(
            disable, 'globally_enabled on, flag set: must be refused.')

        self._set_state(globally_enabled=False, enabled=False, enrolled=False)
        _e3, disable, _r3 = self._conditions()
        self.assertFalse(
            disable, 'globally_enabled off, flag unset: must be refused.')

        self._set_state(globally_enabled=True, enabled=False, enrolled=False)
        _e4, disable, _r4 = self._conditions()
        self.assertFalse(
            disable, 'globally_enabled on, flag unset: must be refused.')

    def test_regenerate_link_survives_global_enforcement(self):
        """D-15: enrollment completed, globally_enabled on -- the
        regenerate link is offered, and (the pair is the point)
        show_disable_two_factor_authentication_link is False for that
        same user. Before this phase both answers came from one method,
        so they could not differ. This is the regression guard for that
        decoupling (RESEARCH.md Pitfall 2).
        """
        self._set_state(globally_enabled=True, enabled=True, enrolled=True)
        _enable, disable, regenerate = self._conditions()
        self.assertTrue(
            regenerate,
            'D-15: "Regenerate recovery codes" must survive global '
            'enforcement.')
        self.assertFalse(
            disable,
            'D-11: the disable link must still be refused for the same '
            'user -- the two conditions must be able to disagree.')

    def test_every_settings_combination_leaves_enrollment_reachable(self):
        """MFA-18 success criterion 5, as a matrix: for each of
        (globally_enabled on, off) crossed with (enrollment completed,
        not completed), at least one of {enable, regenerate} is True, and
        the portal actually resolves a visible 'user' action to
        @@setup-two-factor-authentication for it. Asserting the resolved
        action list -- not only the three booleans -- is what makes this
        a criterion-5 test: the booleans could all be right while
        actions.xml points one of them at the wrong view, exactly the
        failure mode D-15 describes. The remaining half of criterion 5
        (confirming by judgement that no combination strands a real
        user) is recorded as a manual verification in 10-VALIDATION.md
        and is not claimed by this test.
        """
        portal_actions = getToolByName(self.portal, 'portal_actions')
        combinations = (
            (True, False),
            (True, True),
            (False, False),
            (False, True),
            )
        for globally_enabled, enrolled in combinations:
            self._set_state(
                globally_enabled=globally_enabled, enabled=True,
                enrolled=enrolled)
            enable, _disable, regenerate = self._conditions()
            self.assertTrue(
                enable or regenerate,
                'MFA-18 criterion 5: globally_enabled={0!r}, '
                'enrolled={1!r} must offer at least one route to '
                'enrollment.'.format(globally_enabled, enrolled))

            action_infos = portal_actions.listActionInfos(object=self.portal)
            setup_urls = [
                ai['url'] for ai in action_infos
                if ai['category'] == 'user'
                and ai['url'].endswith('@@setup-two-factor-authentication')
                ]
            self.assertTrue(
                setup_urls,
                'globally_enabled={0!r}, enrolled={1!r}: no visible '
                '"user" action resolves to '
                '@@setup-two-factor-authentication -- a correct '
                'predicate pointed at the wrong view would still fail '
                'here (D-15).'.format(globally_enabled, enrolled))

    def test_all_three_conditions_are_false_for_anonymous(self):
        """A portal action's available_expr is evaluated on anonymous
        requests too, so this is a live path, not a theoretical one.
        """
        self._set_state(globally_enabled=True, enabled=True, enrolled=True)
        z2.logout()
        try:
            enable, disable, regenerate = self._conditions()
        finally:
            z2.logout()
            login(self.portal, TEST_USER_NAME)
        self.assertFalse(enable, 'anonymous: enable link must be False.')
        self.assertFalse(disable, 'anonymous: disable link must be False.')
        self.assertFalse(
            regenerate, 'anonymous: regenerate link must be False.')
