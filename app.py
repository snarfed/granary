"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <granary@ryanb.org>'

import urllib

from google.appengine.ext import ndb
from oauth_dropins import facebook
from oauth_dropins import googleplus
from oauth_dropins import instagram
from oauth_dropins import twitter
from oauth_dropins.webutil import handlers
from oauth_dropins.webutil import util
import webapp2

import appengine_config
import activitystreams
from granary import source


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves the front page."""
  def template_file(self):
    return 'granary/templates/index.html'

  def template_vars(self):
    vars = dict(self.request.params)
    key = vars.get('auth_entity')
    if key:
      vars['entity'] = ndb.Key(urlsafe=key).get()

    return vars


class DemoHandler(webapp2.RequestHandler):
  """Handles requests from the interactive demo form on the front page."""
  def get(self):
    params = {name: val for name, val in self.request.params.items()
              if name == 'format' or name.startswith('access_token')}
    return self.redirect('/%s/@me/%s/@app/%s?plaintext=true&%s' % (
      util.get_required_param(self, 'site'),
      self.request.get('group_id', source.ALL),
      self.request.get('activity_id', ''),
      urllib.urlencode(params)))


application = webapp2.WSGIApplication([
  ('/', FrontPageHandler),
  ('/demo', DemoHandler),
  ('/facebook/start_auth', facebook.StartHandler.to('/facebook/oauth_callback')),
  ('/facebook/oauth_callback', facebook.CallbackHandler.to('/')),
  ('/google\\+/start_auth', googleplus.StartHandler.to('/google+/oauth_callback')),
  ('/google\\+/oauth_callback', googleplus.CallbackHandler.to('/')),
  ('/instagram/start_auth', instagram.StartHandler.to('/instagram/oauth_callback')),
  ('/instagram/oauth_callback', instagram.CallbackHandler.to('/')),
  ('/twitter/start_auth', twitter.StartHandler.to('/twitter/oauth_callback')),
  ('/twitter/oauth_callback', twitter.CallbackHandler.to('/')),
] + handlers.HOST_META_ROUTES, debug=appengine_config.DEBUG)
