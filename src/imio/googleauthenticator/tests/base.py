from plone.testing.z2 import Browser


class BaseTest(object):

    def _get_browser(self):
        browser = Browser(self.app)
        browser.handleErrors = False
        return browser

    def _login_browser(self, browser, user, passwd):
        browser.open(self.portal_url + '/login_form')
        browser.getControl(name='__ac_name').value = user
        browser.getControl(name='__ac_password').value = passwd
        browser.getControl(name='submit').click()
