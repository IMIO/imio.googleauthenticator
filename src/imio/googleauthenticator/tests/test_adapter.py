"""
Tests for the user-profile schema adapter.
"""

from imio.googleauthenticator import helpers
from imio.googleauthenticator.adapter import CameFromAdapter
from imio.googleauthenticator.adapter import EnhancedUserDataPanelAdapter
from imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING
from imio.googleauthenticator.tests.base import BaseTest
from imio.googleauthenticator.userdataschema import IEnhancedUserDataSchema
from plone.app.users.userdataschema import IUserDataSchema
from Products.CMFCore.utils import getToolByName
from zope.schema import getFieldNames

import unittest2 as unittest


# The three counters plan 05-01 introduced, plus the two recovery-code
# properties plan 06-01 introduced. Named here only to pin the decision that
# they are memberdata, not form fields -- the test above this list works off
# the schema itself and needs no such enumeration.
LOCKOUT_STATE_PROPERTIES = (
    'two_factor_authentication_failed_attempts',
    'two_factor_authentication_locked_until',
    'two_factor_authentication_last_interval',
    'two_factor_authentication_recovery_codes_salt',
    'two_factor_authentication_recovery_codes_hashes',
    )


class TestEnhancedUserDataPanelAdapter(unittest.TestCase, BaseTest):

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']

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


class TestCameFromAdapter(unittest.TestCase, BaseTest):
    """BUG-06: ``CameFromAdapter.getCameFrom()`` must quote what it reads
    out of the referer's query string, since the caller
    (``pas_plugin.send_2fa_redirect``) appends it verbatim to another
    query string as ``&next_url=...``. Single test method per WR-03 --
    this class's shared layer wiring and ``setUp`` shape follow
    ``TestEnhancedUserDataPanelAdapter`` above.
    """

    layer = IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING

    def setUp(self):
        self.app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']

    def test_get_came_from_quotes_the_value(self):
        """Covers four scenarios in one method (R5/WR-03):

        (a) round-trip integrity -- a ``came_from`` value carrying a
        ``+``, a space, an ``&``, an ``=`` and a percent-encoded UTF-8
        character comes back out byte-for-byte once fed through the
        reader's own ``unquote()``.

        (b) type -- the returned value is a ``str``, never a ``unicode``.
        Python 2's ``urllib.quote`` raises ``KeyError`` on a non-ASCII
        ``unicode`` argument, so if a future change ever made the referer
        path yield unicode, this assertion is what fails instead of a
        live login.

        (c) no referer at all -- ``getCameFrom()`` returns ``''`` exactly
        (not ``None``, not the literal string ``'None'``), because
        ``send_2fa_redirect`` guards its append on truthiness and a
        ``'None'`` string would be appended and then refused by BUG-01's
        guard, silently losing a legitimate destination.

        (d) a referer with a query string but no ``came_from`` key --
        also ``''``.
        """
        # (a)/(b): a raw byte value -- a Python 2 ``str``, not ``unicode``
        # -- carrying '+', a space, '&', '=' and the raw UTF-8 bytes for
        # 'e' with an acute accent (the percent-encoded UTF-8 character).
        raw_value = 'plus+space &equals=' + '\xc3\xa9'
        encoded_value = helpers.quote(raw_value)
        self.request.environ['HTTP_REFERER'] = (
            'http://nohost/plone/login_form?came_from=' + encoded_value)

        adapter = CameFromAdapter(self.request)
        result = adapter.getCameFrom()

        self.assertIsInstance(
            result, str,
            'BUG-06: getCameFrom() must return a str, never a unicode -- '
            "Python 2's urllib.quote raises KeyError on a non-ASCII "
            'unicode argument')

        round_tripped = helpers.extract_request_data_from_query_string(
            'came_from=' + result)
        self.assertEqual(
            raw_value, round_tripped.get('came_from'),
            'BUG-06: the value must round-trip byte-for-byte through the '
            "reader's own unquote()")

        # (c): no HTTP_REFERER at all.
        del self.request.environ['HTTP_REFERER']
        self.assertEqual(
            '', CameFromAdapter(self.request).getCameFrom(),
            'a request with no HTTP_REFERER must yield the empty string, '
            "not None and not the literal string 'None'")

        # (d): a referer with a query string but no came_from key.
        self.request.environ['HTTP_REFERER'] = (
            'http://nohost/plone/login_form?other=1')
        self.assertEqual(
            '', CameFromAdapter(self.request).getCameFrom(),
            'a referer whose query string carries no came_from key must '
            'yield the empty string')
