"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <granary@ryanb.org>'

import httplib
import json
import logging
import urllib
import urllib2
import urlparse

import appengine_config

from google.appengine.api import memcache
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
from webob import exc

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

URL_CACHE_TIME = 5 * 60  # 5m


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


class DemoHandler(handlers.ModernHandler):
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
  """Handles AS/mf2 requests from the interactive demo form on the front page.

  Fetched URL data is cached for 5m. Cache key is 'U [URL]', value is dict with
  'url' and 'body'. Background: https://github.com/snarfed/bridgy/issues/665

  You can skip the cache by including a cache=false query param.
  """
  handle_exception = handlers.handle_exception

  def get(self):
    expected_inputs = ('activitystreams', 'html', 'json-mf2')
    input = util.get_required_param(self, 'input')
    if input not in expected_inputs:
      raise exc.HTTPBadRequest('Invalid input: %s, expected one of %r' %
                               (input, expected_inputs))
    url, body = self._urlopen(util.get_required_param(self, 'url'))

    # decode data
    mf2 = None
    if input == 'html':
      mf2 = mf2py.parse(doc=body, url=url)
    elif input == 'json-mf2':
      mf2 = json.loads(body)
      mf2.setdefault('rels', {})  # mf2util expects rels

    actor = None
    title = None
    if mf2:
      def fetch_mf2_func(url):
        _, doc = self._urlopen(url)
        return mf2py.parse(doc=doc, url=url)
      actor = microformats2.find_author(mf2, fetch_mf2_func=fetch_mf2_func)
      title = mf2util.interpret_feed(mf2, url).get('name')

    if input == 'activitystreams':
      activities = json.loads(body)
    elif input == 'html':
      activities = microformats2.html_to_activities(body, url, actor)
    elif input == 'json-mf2':
      activities = [microformats2.json_to_object(item, actor=actor)
                    for item in mf2.get('items', [])]

    self.write_response(source.Source.make_activities_base_response(activities),
                        url=url, actor=actor, title=title)

  def _urlopen(self, url):
    # check if request is cached
    cache = self.request.get('cache', '').lower() != 'false'
    cache_key = 'U %s' % url
    cached = memcache.get(cache_key) if cache else None

    if cached:
      logging.info('Serving cached response %r', cache_key)
      url = cached['url']
      body = cached['body']
    else:
      # fetch url
      try:
        resp = util.urlopen(url)
      except (ValueError, httplib.InvalidURL) as e:
        self.abort(400, str(e))
        # other exceptions are handled by webutil.handlers.handle_exception(),
        # which uses interpret_http_exception(), etc.

      if url != resp.geturl():
        url = resp.geturl()
        logging.info('Redirected to %s', url)
      body = resp.read()

      if cache:
        logging.info('Caching response in %r', cache_key)
        memcache.set(cache_key, {'url': url, 'body': body}, URL_CACHE_TIME)

    return url, body


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
