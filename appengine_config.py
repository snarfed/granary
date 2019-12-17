from granary.appengine_config import *

# Use lxml for BeautifulSoup explicitly.
from oauth_dropins.webutil import util
util.beautifulsoup_parser = 'lxml'

# Google API clients
creds = None
if DEBUG:
  from google.auth.credentials import AnonymousCredentials
  creds = AnonymousCredentials()

# https://googleapis.dev/python/python-ndb/latest/
# TODO: make thread local?
# https://googleapis.dev/python/python-ndb/latest/migrating.html#setting-up-a-connection
from google.cloud import ndb
ndb_client = ndb.Client(credentials=creds)

import google.cloud.logging
logging_client = google.cloud.logging.Client()

if DEBUG:
  # HACK! work around that the python 3 ndb lib doesn't support dev_appserver.py
  # https://github.com/googleapis/python-ndb/issues/238
  ndb_client.host = 'localhost:8089'
  ndb_client.secure = False

else:
  # https://stackoverflow.com/a/58296028/186123
  # https://googleapis.dev/python/logging/latest/usage.html#cloud-logging-handler
  from google.cloud.logging.handlers import AppEngineHandler, setup_logging
  setup_logging(AppEngineHandler(logging_client, name='stdout'))
