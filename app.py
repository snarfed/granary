"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <activitystreams@ryanb.org>'

import appengine_config
import activitystreams
from oauth_dropins.webutil import handlers
import webapp2


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves /, ie the front page.
  """
  def template_file(self):
    return activitystreams.SOURCE.FRONT_PAGE_TEMPLATE

  def template_vars(self):
    return {'domain': activitystreams.SOURCE.DOMAIN}


application = webapp2.WSGIApplication([
    ('/', FrontPageHandler),
    ] + handlers.HOST_META_ROUTES,
  debug=appengine_config.DEBUG)
