#!/usr/bin/env python
"""Serves the HTML front page and discovery files.

The discovery files inside /.well-known/ include host-meta (XRD), and
host-meta.xrds (XRDS-Simple), and host-meta.jrd (JRD ie JSON).
"""

__author__ = 'Ryan Barrett <portablecontacts@ryanb.org>'

import logging
import os
import urlparse

import appengine_config
import activitystreams

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template

# Included in most static HTTP responses.
BASE_HEADERS = {
  'Cache-Control': 'max-age=300',
  'X-XRDS-Location': 'https://%s/.well-known/host-meta.xrds' %
    appengine_config.HOST,
  'Access-Control-Allow-Origin': '*',
  }
BASE_TEMPLATE_VARS = {
  'domain': activitystreams.SOURCE.DOMAIN,
  'host': appengine_config.HOST,
  'auth_url': activitystreams.SOURCE.AUTH_URL,
  }


class TemplateHandler(webapp.RequestHandler):
  """Renders and serves a template based on class attributes.

  Subclasses must override template_file() and may also override content_type().

  Attributes:
    template_vars: dict
  """
  def __init__(self, *args, **kwargs):
    super(TemplateHandler, self).__init__(*args, **kwargs)
    self.template_vars = dict(BASE_TEMPLATE_VARS)

  def template_file(self):
    """Returns the string template file path."""
    raise NotImplementedError()

  def content_type(self):
    """Returns the string content type."""
    return 'text/html'

  def get(self):
    self.response.headers['Content-Type'] = self.content_type()
    # can't update() because wsgiref.headers.Headers doesn't have it.
    for key, val in BASE_HEADERS.items():
      self.response.headers[key] = val
    self.template_vars.update(self.request.params)
    self.response.out.write(template.render(self.template_file(),
                                            self.template_vars))


class FrontPageHandler(TemplateHandler):
  """Renders and serves /, ie the front page.
  """
  def template_file(self):
    return activitystreams.SOURCE.FRONT_PAGE_TEMPLATE


class HostMetaXrdsHandler(TemplateHandler):
  """Renders and serves the /.well-known/host-meta.xrds XRDS-Simple file.
  """
  def content_type(self):
    return 'application/xrds+xml'

  def template_file(self):
    return 'templates/host-meta.xrds'


class XrdOrJrdHandler(TemplateHandler):
  """Renders and serves an XRD or JRD file.

  JRD is served if the request path ends in .json, or the query parameters
  include 'format=json', or the request headers include
  'Accept: application/json'.

  Subclasses must override template_prefix().
  """
  def content_type(self):
    return 'application/json' if self.is_jrd() else 'application/xrd+xml'

  def template_file(self):
    return self.template_prefix() + ('.jrd' if self.is_jrd() else '.xrd')

  def is_jrd(self):
    """Returns True if JRD should be served, False if XRD."""
    return (os.path.splitext(self.request.path)[1] == '.json' or
            self.request.get('format') == 'json' or
            self.request.headers.get('Accept') == 'application/json')


class HostMetaHandler(XrdOrJrdHandler):
  """Renders and serves the /.well-known/host-meta file.
  """
  def template_prefix(self):
    return 'templates/host-meta'


def main():
  application = webapp.WSGIApplication(
      [('/', FrontPageHandler),
       ('/\.well-known/host-meta(?:\.json)?', HostMetaHandler),
       ('/\.well-known/host-meta.xrds', HostMetaXrdsHandler),
       ],
      debug=appengine_config.DEBUG)
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
