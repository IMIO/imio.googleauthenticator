"""
Tests for the user-profile schema adapter.
"""

import unittest2 as unittest

from Products.CMFCore.utils import getToolByName
from plone.app.users.userdataschema import IUserDataSchema
from zope.schema import getFieldNames

from imio.googleauthenticator.adapter import EnhancedUserDataPanelAdapter
from imio.googleauthenticator.testing import \
    IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from imio.googleauthenticator.userdataschema import IEnhancedUserDataSchema

# The three counters plan 05-01 introduced. Named here only to pin the
# decision that they are memberdata, not form fields -- the test above this
# list works off the schema itself and needs no such enumeration.
LOCKOUT_STATE_PROPERTIES = (
    'two_factor_authentication_failed_attempts',
    'two_factor_authentication_locked_until',
    'two_factor_authentication_last_interval',
    )


class TestEnhancedUserDataPanelAdapter(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.qi_tool = getToolByName(self.portal, 'portal_quickinstaller')
        self._install()

    def _own_schema_fields(self):
        """The fields this package adds, excluding Plone's own -- so a gap in
        Plone's stock adapter could never be reported as ours.
        """
        return sorted(
            set(getFieldNames(IEnhancedUserDataSchema))
            - set(getFieldNames(IUserDataSchema)))

    def test_every_field_this_package_adds_is_readable_from_the_adapter(self):
        """Every field on ``IEnhancedUserDataSchema`` must be gettable from
        ``EnhancedUserDataPanelAdapter``.

        ``zope.formlib``'s ``setUpEditWidgets`` calls ``field.get(adapter)``
        for every field the form renders, and that is a plain ``getattr`` --
        ``AccountPanelSchemaAdapter`` defines no ``__getattr__`` fallback. A
        schema field with no matching adapter property therefore raises
        ``AttributeError`` and takes the entire profile form down.

        ``CustomizedUserDataPanel.omit(...)`` does not protect against this: it
        is registered for the view name ``personal-information`` only, so
        ``plone.app.users``' ``@@user-information`` -- the form an
        administrator uses to edit somebody else's profile -- renders whatever
        the schema declares. Plan 05-01 added three ``Int`` counters to the
        schema without adapter accessors, and that form began failing with
        ``AttributeError: 'EnhancedUserDataPanelAdapter' object has no
        attribute 'two_factor_authentication_failed_attempts'``.

        Asserted across the whole schema rather than against the three known
        names, so a field added later without an accessor fails here rather
        than in production.
        """
        adapter = EnhancedUserDataPanelAdapter(self.portal)
        own_fields = self._own_schema_fields()

        self.assertTrue(
            own_fields,
            'Non-vacuity control: this package declares no schema fields of '
            'its own, so the assertion below could not fail.')
        missing = [name for name in own_fields if not hasattr(adapter, name)]
        self.assertEqual(
            [], missing,
            'These schema fields have no adapter accessor, so any profile '
            'form rendering them raises AttributeError: {0}'.format(missing))

    def test_lockout_state_is_memberdata_only_and_never_a_form_field(self):
        """The replay and lockout counters must not be schema fields.

        They are internal state written only by ``helpers.py`` through
        ``setMemberProperties``, and read only through ``getProperty``. What
        makes them persist is their ``memberdata_properties.xml`` entry, not a
        schema entry -- an undeclared memberdata property is silently popped by
        ``MutablePropertySheet.setProperties``, which is what that file guards
        against.

        Keeping them off the schema does two things at once. It stops any
        profile form from rendering a field the adapter cannot supply (the
        ``AttributeError`` above), and it removes the write path the code
        review flagged: as schema fields they were plain writable ``Int``s
        whose only barrier against a user editing their own
        ``two_factor_authentication_locked_until`` to 0 was one view's
        ``omit()`` call. A field that does not exist needs no barrier.
        """
        schema_fields = getFieldNames(IEnhancedUserDataSchema)

        leaked = [name for name in LOCKOUT_STATE_PROPERTIES
                  if name in schema_fields]
        self.assertEqual(
            [], leaked,
            'Lockout state is back on the user-profile schema, which both '
            'breaks @@user-information and makes it form-writable: '
            '{0}'.format(leaked))

    def test_lockout_state_still_persists_as_memberdata(self):
        """Non-vacuity control for the test above: proves removing the schema
        fields did not remove the properties themselves. Without this, an
        accidental deletion of the ``memberdata_properties.xml`` entries would
        leave the assertion above passing while every counter silently stopped
        persisting -- the exact failure mode that file exists to prevent.
        """
        memberdata = getToolByName(self.portal, 'portal_memberdata')

        for name in LOCKOUT_STATE_PROPERTIES:
            self.assertTrue(
                memberdata.hasProperty(name),
                '{0} is not declared in portal_memberdata, so '
                'setMemberProperties will silently pop it.'.format(name))
