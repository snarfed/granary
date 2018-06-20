# Load packages from virtualenv
# https://cloud.google.com/appengine/docs/python/tools/libraries27#vendoring
from google.appengine.ext import vendor
try:
  vendor.add('local')
except ValueError as e:
  import logging
  logging.warning("Couldn't set up App Engine vendor virtualenv! %s", e)

from granary.appengine_config import *

# Make requests and urllib3 play nice with App Engine.
# https://github.com/snarfed/bridgy/issues/396
# http://stackoverflow.com/questions/34574740
from requests_toolbelt.adapters import appengine
appengine.monkeypatch()

def webapp_add_wsgi_middleware(app):
  # # uncomment for app stats
  # appstats_CALC_RPC_COSTS = True
  # from google.appengine.ext.appstats import recording
  # app = recording.appstats_wsgi_middleware(app)

  # # uncomment for instance_info concurrent requests recording
  # from oauth_dropins.webutil import instance_info
  # app = instance_info.concurrent_requests_wsgi_middleware(app)

  return app
