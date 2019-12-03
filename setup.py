"""setuptools setup module for granary.

Docs:
https://packaging.python.org/en/latest/distributing.html
https://setuptools.readthedocs.io/

Based on https://github.com/pypa/sampleproject/blob/master/setup.py
"""
from setuptools import setup, find_packages


setup(name='granary',
      version='2.2',
      description='The social web translator',
      long_description=open('README.md').read(),
      long_description_content_type='text/markdown',
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
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Topic :: Software Development :: Libraries :: Python Modules',
      ],
      keywords='social facebook flickr github instagram twitter activitystreams html microformats2 mf2 atom rss jsonfeed',
      install_requires=[
          # Keep in sync with requirements.txt!
          'beautifulsoup4',
          'brevity>=0.2.17',
          'feedgen>=0.7.0',
          'future',
          'google-cloud-ndb',
          'html2text',
          'humanfriendly',
          'jinja2',
          'mf2util>=0.5.0',
          'oauth-dropins>=3.0',
          'python-dateutil',
          'requests>=2.10.0',
          'ujson',
          'urllib3>=1.14',
          'webapp2>=3.0.0b1',
      ],
      tests_require=['mox3>=0.24.0'],
)
