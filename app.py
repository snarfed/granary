"""Serves the the front page, discovery files, and OAuth flows.
"""
import logging
import urllib
import urlparse
from xml.etree import ElementTree

import appengine_config

from google.appengine.ext import ndb
import mf2util
from oauth_dropins import (
  facebook,
  flickr,
  github,
  twitter,
)
from oauth_dropins.webutil import handlers, util
import requests
import webapp2
from webob import exc

import api
from granary import (
  as2,
  atom,
  jsonfeed,
  microformats2,
  source,
)
from granary.facebook import Facebook
from granary.flickr import Flickr
from granary.github import GitHub
from granary.instagram import Instagram
from granary.twitter import Twitter

INPUTS = (
  'activitystreams',
  'as1',
  'as2',
  'atom',
  'html',
  'json-mf2',
  'jsonfeed',
  'mf2-json',
)
SILO_DOMAINS = {cls.DOMAIN for cls in (
  Facebook,
  Flickr,
  GitHub,
  Instagram,
  Twitter,
)}


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves the front page."""
  handle_exception = handlers.handle_exception

  @api.canonicalize_domain
  def get(self, *args, **kwargs):
    return super(FrontPageHandler, self).get(*args, **kwargs)

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

  @api.canonicalize_domain
  def get(self):
    site = util.get_required_param(self, 'site')
    user = self.request.get('user_id') or source.ME
    group = self.request.get('group_id') or source.ALL
    if group == '@list':
      group = util.get_required_param(self, 'list')

    activity_id = search_query = ''
    if group == source.SEARCH:
      search_query = self.request.get('search_query', '').encode('utf-8')
    elif group != source.BLOCKS:
      activity_id = self.request.get('activity_id', '').encode('utf-8')

    # pass query params through
    params = dict(self.request.params.items())
    params.update({
      'plaintext': 'true',
      'cache': 'false',
      'search_query': search_query,
    })

    return self.redirect('/%s/%s/%s/@app/%s?%s' % (
      site, urllib.quote_plus(user.encode('utf-8')), group, activity_id,
      urllib.urlencode(params)))


class UrlHandler(api.Handler):
  """Handles URL requests from the interactive demo form on the front page.

  Responses are cached for 10m. You can skip the cache by including a cache=false
  query param. Background: https://github.com/snarfed/bridgy/issues/665
  """
  handle_exception = handlers.handle_exception

  @api.canonicalize_domain
  @handlers.memcache_response(api.RESPONSE_CACHE_TIME)
  def get(self):
    input = util.get_required_param(self, 'input')
    if input not in INPUTS:
      raise exc.HTTPBadRequest('Invalid input: %s, expected one of %r' %
                               (input, INPUTS))
    resp = util.requests_get(util.get_required_param(self, 'url'), gateway=True)
    url = resp.url

    # decode data
    if input in ('activitystreams', 'as1', 'as2', 'mf2-json', 'json-mf2', 'jsonfeed'):
      try:
        body_json = resp.json()
        body_items = (body_json if isinstance(body_json, list)
                      else body_json.get('items') or [body_json])
      except (TypeError, ValueError):
        raise exc.HTTPBadRequest('Could not decode %s as JSON' % url)

    mf2 = None
    if input == 'html':
      mf2 = util.parse_mf2(resp)
    elif input in ('mf2-json', 'json-mf2'):
      mf2 = body_json
      if not hasattr(mf2, 'get'):
        raise exc.HTTPBadRequest(
          'Expected microformats2 JSON input to be dict, got %s' %
          mf2.__class__.__name__)
      mf2.setdefault('rels', {})  # mf2util expects rels

    actor = None
    title = None
    hfeed = None
    if mf2:
      def fetch_mf2_func(url):
        if util.domain_or_parent_in(urlparse.urlparse(url).netloc, SILO_DOMAINS):
          return {'items': [{'type': ['h-card'], 'properties': {'url': [url]}}]}
        return util.fetch_mf2(url, gateway=True)

      try:
        actor = microformats2.find_author(mf2, fetch_mf2_func=fetch_mf2_func)
        title = microformats2.get_title(mf2)
        hfeed = mf2util.find_first_entry(mf2, ['h-feed'])
      except (KeyError, ValueError) as e:
        raise exc.HTTPBadRequest('Could not parse %s as %s: %s' % (url, input, e))

    try:
      if input in ('as1', 'activitystreams'):
        activities = body_items
      elif input == 'as2':
        activities = [as2.to_as1(obj) for obj in body_items]
      elif input == 'atom':
        try:
          activities = atom.atom_to_activities(resp.text)
        except ElementTree.ParseError as e:
          raise exc.HTTPBadRequest('Could not parse %s as XML: %s' % (url, e))
        except ValueError as e:
          raise exc.HTTPBadRequest('Could not parse %s as Atom: %s' % (url, e))
      elif input == 'html':
        activities = microformats2.html_to_activities(resp, url, actor)
      elif input in ('mf2-json', 'json-mf2'):
        activities = [microformats2.json_to_object(item, actor=actor)
                      for item in mf2.get('items', [])]
      elif input == 'jsonfeed':
        activities, actor = jsonfeed.jsonfeed_to_activities(body_json)
    except ValueError as e:
      logging.warning('parsing input failed', exc_info=True)
      self.abort(400, 'Could not parse %s as %s: %s' % (url, input, str(e)))

    self.write_response(source.Source.make_activities_base_response(activities),
                        url=url, actor=actor, title=title, hfeed=hfeed)


application = webapp2.WSGIApplication([
  ('/', FrontPageHandler),
  ('/demo', DemoHandler),
  ('/facebook/start_auth', facebook.StartHandler.to('/facebook/oauth_callback')),
  ('/facebook/oauth_callback', facebook.CallbackHandler.to('/')),
  ('/flickr/start_auth', flickr.StartHandler.to('/flickr/oauth_callback')),
  ('/flickr/oauth_callback', flickr.CallbackHandler.to('/')),
  ('/github/start_auth', github.StartHandler.to('/github/oauth_callback')),
  ('/github/oauth_callback', github.CallbackHandler.to('/')),
  ('/twitter/start_auth', twitter.StartHandler.to('/twitter/oauth_callback')),
  ('/twitter/oauth_callback', twitter.CallbackHandler.to('/')),
  ('/url', UrlHandler),
] + handlers.HOST_META_ROUTES, debug=appengine_config.DEBUG)
