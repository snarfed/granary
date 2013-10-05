#!/usr/bin/env python
"""Serves the HTML front page and discovery files.
"""

__author__ = 'Ryan Barrett <activitystreams@ryanb.org>'

import activitystreams
import appengine_config
import webapp2
from webutil import handlers


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves /, ie the front page.
  """
  def template_file(self):
    return activitystreams.SOURCE.FRONT_PAGE_TEMPLATE

  def template_vars(self):
    return {'domain': activitystreams.SOURCE.DOMAIN,
            'auth_url': activitystreams.SOURCE.AUTH_URL,
            }


application = webapp2.WSGIApplication(
  [('/', FrontPageHandler)] + handlers.HOST_META_ROUTES,
  debug=appengine_config.DEBUG)
