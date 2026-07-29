from  imio.googleauthenticator.testing import IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING
from plone.testing import layered
import robotsuite
import unittest


def test_suite():
    suite = unittest.TestSuite()
    suite.addTests([
        layered(robotsuite.RobotTestSuite("robot_test.txt"),
                layer=IMIO_GOOGLEAUTHENTICATOR_ROBOT_TESTING)
    ])
    return suite