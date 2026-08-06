from plone import api
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import TEST_USER_NAME
from plone.testing import z2
from zope.configuration import xmlconfig


class ImiogoogleauthenticatorLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        # Load ZCML
        import imio.googleauthenticator
        xmlconfig.file(
            'configure.zcml',
            imio.googleauthenticator,
            context=configurationContext
        )

        # Install products that use an old-style initialize() function
        z2.installProduct(app, 'imio.googleauthenticator')

    def setUpPloneSite(self, portal):
        applyProfile(portal, 'imio.googleauthenticator:default')

        # Test-fixture hygiene (MFA-15): globally_enabled defaults True
        # (browser/controlpanel.py's schema default), so the applyProfile()
        # call above runs setuphandlers._enroll_existing_users() with
        # enforcement already on -- it enrols PLONE_FIXTURE's TEST_USER_NAME,
        # which exists in `portal` before our profile is applied. The whole
        # rest of this suite assumes TEST_USER_NAME starts with 2FA
        # disabled (every test class's own tearDown resets it to False for
        # the same reason); undo that one-time install-time enrolment here,
        # and turn the setting off, so a later applyProfile() call made
        # from inside an individual test (several re-apply the profile
        # mid-test, e.g. to prove idempotency) does not silently re-enrol
        # it a second time.
        from imio.googleauthenticator.helpers import get_app_settings
        get_app_settings().globally_enabled = False
        test_user = api.user.get(username=TEST_USER_NAME)
        if test_user is not None:
            test_user.setMemberProperties(
                mapping={'enable_two_factor_authentication': False})

#    def tearDownZope(self, app):
#        # Uninstall products installed above
#        z2.uninstallProduct(app, 'imio.googleauthenticator')


IMIO_GOOGLEAUTHENTICATOR_FIXTURE = ImiogoogleauthenticatorLayer()
IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,),
    name="ImiogoogleauthenticatorLayer:Functional"
)
IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE, REMOTE_LIBRARY_BUNDLE_FIXTURE, z2.ZSERVER_FIXTURE),
    name="ImiogoogleauthenticatorLayer:Robot"
)
