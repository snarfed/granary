"""Flask app config.

http://flask.pocoo.org/docs/2.0/config
"""
from oauth_dropins.webutil import appengine_info, util

JSONIFY_PRETTYPRINT_REGULAR = True

if appengine_info.DEBUG:
  ENV = 'development'
  CACHE_TYPE = 'NullCache'
  GITHUB_CLIENT_ID = util.read('github_client_id_local')
  GITHUB_CLIENT_SECRET = util.read('github_client_secret_local')
  SECRET_KEY = 'sooper seekret'
else:
  ENV = 'production'
  CACHE_TYPE = 'SimpleCache'
  GITHUB_CLIENT_ID = util.read('github_client_id')
  GITHUB_CLIENT_SECRET = util.read('github_client_secret')
  SECRET_KEY = util.read('flask_secret_key')
