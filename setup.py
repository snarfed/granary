"""setuptools setup module for activitystreams-unofficial.

Docs:
https://packaging.python.org/en/latest/distributing.html
http://pythonhosted.org/setuptools/setuptools.html

Based on https://github.com/pypa/sampleproject/blob/master/setup.py
"""
import unittest

from setuptools import setup, find_packages
from setuptools.command.test import ScanningLoader


class TestLoader(ScanningLoader):
  def __init__(self, *args, **kwargs):
    super(ScanningLoader, self).__init__(*args, **kwargs)
    # test/__init__.py makes App Engine SDK's bundled libraries importable.
    import oauth_dropins.test


setup(name='activitystreams-unofficial',
      version='1.0',
      description='Fetches and converts data between Facebook, Google+, Instagram, and Twitter native APIs, ActivityStreams, microformats2 HTML and JSON, Atom, and more.',
      long_description=open('README.rst').read(),
      url='https://github.com/snarfed/activitystreams-unofficial',
      packages=find_packages(exclude='test'),
      author='Ryan Barrett',
      author_email='activitystreams@ryanb.org',
      license='Public domain',
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: Developers',
          'Environment :: Web Environment',
          'License :: OSI Approved :: MIT License',
          'License :: Public Domain',
          'Programming Language :: Python :: 2',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
      keywords='activitystreams facebook twitter google+ twitter microformats2 mf2 atom',
      install_requires=[
          # Keep in sync with requirements.txt!
          'beautifulsoup4',
          'mf2py>=0.2.6',
          'oauth-dropins',
          'requests',
      ],
      test_loader='setup:TestLoader',
      test_suite='activitystreams_unofficial.test',
)
