from plone.app.testing import PloneSandboxLayer
from plone.app.testing import applyProfile
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.app.robotframework.testing import REMOTE_LIBRARY_BUNDLE_FIXTURE
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

#    def tearDownZope(self, app):
#        # Uninstall products installed above
#        z2.uninstallProduct(app, 'imio.googleauthenticator')


IMIO_GOOGLEAUTHENTICATOR_FIXTURE = ImiogoogleauthenticatorLayer()
IMIO_GOOGLEAUTHENTICATOR_INTEGRATION_TESTING = IntegrationTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,),
    name="ImiogoogleauthenticatorLayer:Integration"
)
IMIO_GOOGLEAUTHENTICATOR_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE,),
    name="ImiogoogleauthenticatorLayer:Functional"
)
IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING = FunctionalTesting(
    bases=(IMIO_GOOGLEAUTHENTICATOR_FIXTURE, REMOTE_LIBRARY_BUNDLE_FIXTURE, z2.ZSERVER_FIXTURE),
    name="ImiogoogleauthenticatorLayer:Robot"
)
