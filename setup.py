from setuptools import find_packages, setup

import pip

try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

links = []
requires = []

try:
    requirements = pip.req.parse_requirements('requirements.txt')
except:
    # new versions of pip requires a session
    requirements = pip.req.parse_requirements(
        'requirements.txt', session=pip.download.PipSession())

for item in requirements:
    # we want to handle package names and also repo urls
    if getattr(item, 'url', None):  # older pip has url
        links.append(str(item.url))
    if getattr(item, 'link', None): # newer pip has link
        links.append(str(item.link))
    if item.req:
        requires.append(str(item.req))

setup(
    name="openstax-egrader",
    version="0.1.4",
    author="m1yag1",
    author_email="mike.arbelaez@openstax.org",
    py_modules=['wsgi'],
    packages=find_packages(),
    include_package_data=True,
    install_requires=requires,
    dependency_links=links
)
