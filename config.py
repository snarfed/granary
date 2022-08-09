"""Flask app config.

http://flask.pocoo.org/docs/2.0/config
"""
from oauth_dropins.webutil import appengine_info, util

if appengine_info.DEBUG:
  ENV = 'development'
  CACHE_TYPE = 'NullCache'
  SECRET_KEY = 'sooper seekret'
else:
  ENV = 'production'
  CACHE_TYPE = 'SimpleCache'
  SECRET_KEY = util.read('flask_secret_key')
