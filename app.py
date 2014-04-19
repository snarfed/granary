"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <activitystreams@ryanb.org>'

import urllib

import appengine_config
import activitystreams
from oauth_dropins.webutil import handlers
import webapp2

from oauth_dropins import facebook
from oauth_dropins import instagram
from oauth_dropins import twitter
site_module = {'facebook-activitystreams': facebook,
               'instagram-activitystreams': instagram,
               'twitter-activitystreams': twitter,
               }[appengine_config.APP_ID]
oauth_callback_path = {
  'facebook-activitystreams': '/facebook/oauth_callback',
  'instagram-activitystreams': '/instagram/oauth_callback',
  'twitter-activitystreams': '/twitter/oauth_callback',
  }[appengine_config.APP_ID]

class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves /, ie the front page.
  """
  def template_file(self):
    return activitystreams.SOURCE.FRONT_PAGE_TEMPLATE

  def template_vars(self):
    return {'domain': activitystreams.SOURCE.DOMAIN}


application = webapp2.WSGIApplication([
    ('/', FrontPageHandler),
    ('/start_auth', site_module.StartHandler.to(oauth_callback_path)),
    (oauth_callback_path, site_module.CallbackHandler.to('/')),
    ] + handlers.HOST_META_ROUTES,
  debug=appengine_config.DEBUG)
