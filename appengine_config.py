# Load packages from virtualenv
# https://cloud.google.com/appengine/docs/python/tools/libraries27#vendoring
from google.appengine.ext import vendor
try:
  vendor.add('local')
except ValueError as e:
  import logging
  logging.warning("Couldn't set up App Engine vendor virtualenv! %s", e)

from granary.appengine_config import *

# stub out the multiprocessing module. it's not supported on App Engine
# Standard, but humanfriendly uses it for some terminal animation thing that we
# don't need.
import sys
from types import ModuleType

class DummyProcessing(ModuleType):
  pass
sys.modules['multiprocessing'] = DummyProcessing

# Make requests and urllib3 play nice with App Engine.
# https://github.com/snarfed/bridgy/issues/396
# http://stackoverflow.com/questions/34574740
from requests_toolbelt.adapters import appengine
appengine.monkeypatch()
