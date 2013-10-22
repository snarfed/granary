"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <activitystreams@ryanb.org>'

import urllib

import activitystreams
import appengine_config
import webapp2
from webutil import handlers

from oauth_dropins import facebook
from oauth_dropins import instagram
from oauth_dropins import twitter
site_module = {'facebook-activitystreams': facebook,
               'instagram-activitystreams': instagram,
               'twitter-activitystreams': twitter,
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
    ('/start_auth', site_module.StartHandler.to('/oauth_callback')),
    ('/oauth_callback', CallbackHandler.to('/')),
    ] + handlers.HOST_META_ROUTES,
  debug=appengine_config.DEBUG)
