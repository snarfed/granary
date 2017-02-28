"""setuptools setup module for granary.

Docs:
https://packaging.python.org/en/latest/distributing.html
http://pythonhosted.org/setuptools/setuptools.html

Based on https://github.com/pypa/sampleproject/blob/master/setup.py
"""
from setuptools import setup, find_packages
from setuptools.command.test import ScanningLoader


class TestLoader(ScanningLoader):
  def __init__(self, *args, **kwargs):
    super(ScanningLoader, self).__init__(*args, **kwargs)
    # webutil/test/__init__.py makes App Engine SDK's bundled libraries importable.
    import oauth_dropins.webutil.test


setup(name='granary',
      version='1.7',
      description='Free yourself from silo API chaff and expose the sweet social data foodstuff inside in standard formats and protocols!',
      long_description=open('README.rst').read(),
      url='https://github.com/snarfed/granary',
      packages=find_packages(),
      include_package_data=True,
      author='Ryan Barrett',
      author_email='granary@ryanb.org',
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
      keywords='facebook twitter google+ twitter activitystreams html microformats2 mf2 atom',
      install_requires=[
          # Keep in sync with requirements.txt!
          'beautifulsoup4',
          'html2text',
          'jinja2',
          'mf2py>=0.2.7',
          'mf2util>=0.5.0',
          'oauth-dropins>=1.7',
          'requests>=2.10.0',
          'requests-toolbelt>=0.6.2',
          'brevity>=0.2.8',
          'urllib3>=1.14',
      ],
      extras_require={
          'appengine-sdk': ['appengine-sdk >= 1.9.40.post0'],
      },
      test_loader='setup:TestLoader',
      test_suite='granary.test',
)
