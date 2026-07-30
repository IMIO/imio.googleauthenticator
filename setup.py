from setuptools import setup, find_packages
import os

version = '1.0.0.dev0'

try:
    readme = open('README.rst').read()
    readme = readme.replace('.. image:: _static', '.. figure:: https://github.com/IMIO/imio.googleauthenticator/raw/master/docs/_static')
except:
    readme = ''

try:
    changelog = open('CHANGES.rst').read()
except:
    changelog = ''

long_description = (
    readme
    + '\n' +
    #'Contributors\n'
    #'============\n'
    #+ '\n' +
    #open('CONTRIBUTORS.txt').read()
    #+ '\n' +
    changelog
+ '\n')

setup(
    name = 'imio.googleauthenticator',
    version = version,
    description = "Two-step verification for Plone 4 using the Google Authenticator app.",
    long_description = long_description,
    # Get more strings from
    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
        "Environment :: Web Environment",
        "Framework :: Plone",
        "Framework :: Plone :: 4.3",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords = 'google authenticator, two-step verification, multi-factor authentication, two-factor authentication',
    author = 'iMio',
    author_email = 'support-docs@imio.be',
    url = 'https://github.com/IMIO/imio.googleauthenticator',
    license = 'GPL',
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    namespace_packages = ['imio', ],
    include_package_data = True,
    zip_safe = False,
    install_requires = [
        'setuptools',
        # -*- Extra requirements: -*-
        'plone.api>=1.1.0',
        'plone.directives.form>=1.1',
        'onetimepass==0.2.2',
        'ska>=1.1',
        'cryptography==3.3.2',
        'ipaddress==1.0.23',
        'qrcode==6.1',
        'Pillow',
    ],
    extras_require = {'test': ['plone.app.testing', 'plone.app.robotframework']},
    entry_points = """
        # -*- Entry points: -*-
        [z3c.autoinclude.plugin]
        target = plone
    """,
)
