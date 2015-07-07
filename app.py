"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <granary@ryanb.org>'

import appengine_config
import activitystreams

from google.appengine.ext import ndb
from oauth_dropins import facebook
from oauth_dropins import googleplus
from oauth_dropins import instagram
from oauth_dropins import twitter
from oauth_dropins.webutil import handlers
import webapp2

# https://developers.facebook.com/docs/facebook-login/permissions/#reference
FACEBOOK_OAUTH_SCOPES = ','.join((
    'read_stream',
    'user_actions.news',
    'user_actions.video',
    'user_actions:instapp',
    'user_activities',
    'user_games_activity',
    'user_likes',
    ))


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves /, ie the front page.
  """
  def template_file(self):
    return 'granary/templates/index.html'

  def template_vars(self):
    vars = dict(self.request.params)
    key = vars.get('auth_entity')
    if key:
      vars['entity'] = ndb.Key(urlsafe=key).get()

    return vars


application = webapp2.WSGIApplication([
  ('/', FrontPageHandler),
  ('/facebook/start_auth', facebook.StartHandler.to('/facebook/oauth_callback',
                                                    scopes=FACEBOOK_OAUTH_SCOPES)),
  ('/facebook/oauth_callback', facebook.CallbackHandler.to('/')),
  ('/google+/start_auth', googleplus.StartHandler.to('/googleplus/oauth_callback')),
  ('/google+/oauth_callback', googleplus.CallbackHandler.to('/')),
  ('/instagram/start_auth', instagram.StartHandler.to('/instagram/oauth_callback')),
  ('/instagram/oauth_callback', instagram.CallbackHandler.to('/')),
  ('/twitter/start_auth', twitter.StartHandler.to('/twitter/oauth_callback')),
  ('/twitter/oauth_callback', twitter.CallbackHandler.to('/')),
] + handlers.HOST_META_ROUTES, debug=appengine_config.DEBUG)
