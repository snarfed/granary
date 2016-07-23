"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <granary@ryanb.org>'

import json
import logging
import urllib
import urllib2
import urlparse

import appengine_config

from google.appengine.ext import ndb
import mf2py
import mf2util
from oauth_dropins import facebook
from oauth_dropins import flickr
from oauth_dropins import googleplus
from oauth_dropins import instagram
from oauth_dropins import twitter
from oauth_dropins.webutil import handlers
from oauth_dropins.webutil import util
import webapp2

import activitystreams
from granary import microformats2
from granary import source

API_PARAMS = {
  'access_token',
  'access_token_key',
  'access_token_secret',
  'auth_entity',
  'format',
}


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves the front page."""
  handle_exception = handlers.handle_exception

  def template_file(self):
    return 'granary/templates/index.html'

  def template_vars(self):
    vars = dict(self.request.params)

    entity = None
    key = vars.get('auth_entity')
    if key:
      entity = vars['entity'] = ndb.Key(urlsafe=key).get()

    if entity:
      vars.setdefault('site', vars['entity'].site_name().lower())

    return vars


class DemoHandler(webapp2.RequestHandler):
  """Handles silo requests from the interactive demo form on the front page."""
  handle_exception = handlers.handle_exception

  def get(self):
    site = util.get_required_param(self, 'site')
    group = self.request.get('group_id') or source.ALL
    user = self.request.get('user_id') or source.ME

    if group == source.SEARCH:
      search_query = self.request.get('search_query', '').encode('utf-8')
      activity_id = ''
    else:
      activity_id = self.request.get('activity_id', '').encode('utf-8')
      search_query = ''

    params = {
      'plaintext': 'true',
      'cache': 'false',
      'search_query': search_query,
    }
    params.update({name: val for name, val in self.request.params.items()
                   if name in API_PARAMS})
    return self.redirect('/%s/%s/%s/@app/%s?%s' % (
      site, urllib.quote_plus(user.encode('utf-8')), group, activity_id,
      urllib.urlencode(params)))


class UrlHandler(activitystreams.Handler):
  """Handles AS/mf2 requests from the interactive demo form on the front page."""
  handle_exception = handlers.handle_exception

  def get(self):
    expected_inputs = ('activitystreams', 'html', 'json-mf2')
    input = util.get_required_param(self, 'input')
    if input not in expected_inputs:
      raise exc.HTTPBadRequest('Invalid input: %s, expected one of %r' %
                               (input, expected_inputs))

    # fetch url
    url = util.get_required_param(self, 'url')
    resp = util.urlopen(url)
    if url != resp.geturl():
      url = resp.geturl()
      logging.info('Redirected to %s', url)
    body = resp.read()

    # decode data
    mf2 = None
    if input == 'activitystreams':
      activities = json.loads(body)
    elif input == 'html':
      activities = microformats2.html_to_activities(body, url)
      mf2 = mf2py.parse(doc=body, url=url)
    elif input == 'json-mf2':
      mf2 = json.loads(body)
      mf2['rels'] = {}  # mf2util expects rels
      activities = [microformats2.json_to_object(item)
                    for item in mf2.get('items', [])]

    author = None
    title = None
    if mf2:
      author = microformats2.find_author(mf2)
      title = mf2util.interpret_feed(mf2, url).get('name')

    self.write_response(source.Source.make_activities_base_response(activities),
                        url=url, actor=author, title=title)


application = webapp2.WSGIApplication([
  ('/', FrontPageHandler),
  ('/demo', DemoHandler),
  ('/facebook/start_auth', facebook.StartHandler.to('/facebook/oauth_callback')),
  ('/facebook/oauth_callback', facebook.CallbackHandler.to('/')),
  ('/flickr/start_auth', flickr.StartHandler.to('/flickr/oauth_callback')),
  ('/flickr/oauth_callback', flickr.CallbackHandler.to('/')),
  ('/google\\+/start_auth', googleplus.StartHandler.to('/google+/oauth_callback')),
  ('/google\\+/oauth_callback', googleplus.CallbackHandler.to('/')),
  ('/twitter/start_auth', twitter.StartHandler.to('/twitter/oauth_callback')),
  ('/twitter/oauth_callback', twitter.CallbackHandler.to('/')),
  ('/url', UrlHandler),
] + handlers.HOST_META_ROUTES, debug=appengine_config.DEBUG)
