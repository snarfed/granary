"""Flask app config.

http://flask.pocoo.org/docs/2.0/config
"""
import logging
import secrets

from webutil import appengine_info, util

if appengine_info.DEBUG:
  ENV = 'development'
  CACHE_TYPE = 'NullCache'
  SECRET_KEY = secrets.token_hex(32)
else:
  ENV = 'production'
  CACHE_TYPE = 'SimpleCache'
  SECRET_KEY = util.read('flask_secret_key')

  for logger in ('api', 'app', 'websockets.client'):
    logging.getLogger(logger).setLevel(logging.INFO)
