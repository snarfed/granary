"""Redirects from *-activitystreams.appspot.com to granary-demo.appspot.com.
"""
import os
import urlparse

from google.appengine.api import app_identity
import webapp2


class Redirect(webapp2.RequestHandler):
  def get(self):
    parts = list(urlparse.urlparse(self.request.url))
    parts[0] = 'https'
    parts[1] = 'granary-demo.appspot.com'

    if parts[2].startswith('/@me/'):
      site = app_identity.get_application_id().split('-')[0]
      parts[2] = site + parts[2]

    return self.redirect(urlparse.urlunparse(parts), permanent=True)


application = webapp2.WSGIApplication([
  ('.*', Redirect),
])
