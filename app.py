"""Serves the the front page, discovery files, and OAuth flows.
"""
import importlib
import logging
import urllib.parse
from xml.etree import ElementTree

from google.cloud import ndb
import mf2util
from oauth_dropins import (
  facebook,
  flickr,
  github,
  mastodon,
  twitter,
)
from oauth_dropins.webutil import (
  appengine_config,
  appengine_info,
  handlers,
  util,
)
from oauth_dropins.webutil.util import json_dumps, json_loads
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
from granary.mastodon import Mastodon
from granary.meetup import Meetup
from granary.instagram import Instagram
from granary.twitter import Twitter

import api, cron

handlers.JINJA_ENV.loader.searchpath.append('granary')

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
SILOS = (
  'flickr',
  'github',
  'instagram',
  'mastodon',
  'meetup',
  'twitter',
)
OAUTHS = {  # maps oauth-dropins module name to module
  name: importlib.import_module('oauth_dropins.%s' % name)
  for name in SILOS
}
SILO_DOMAINS = {cls.DOMAIN for cls in (
  Facebook,
  Flickr,
  GitHub,
  Instagram,
  Meetup,
  Twitter,
)}
SCOPE_OVERRIDES = {
  # https://developers.facebook.com/docs/reference/login/
  'facebook': 'user_status,user_posts,user_photos,user_events',
  # https://developer.github.com/apps/building-oauth-apps/scopes-for-oauth-apps/
  'github': 'notifications,public_repo',
  # https://docs.joinmastodon.org/api/permissions/
  'mastodon': 'read',
  # https://www.meetup.com/meetup_api/auth/#oauth2-scopes
  'meetup': 'rsvp'
}


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

    vars.update({
      silo + '_html': module.StartHandler.button_html(
        '/%s/start_auth' % silo,
        image_prefix='/oauth_dropins/static/',
        outer_classes='col-lg-2 col-sm-4 col-xs-6',
        scopes=SCOPE_OVERRIDES.get(silo, ''),
      )
      for silo, module in OAUTHS.items()})

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
      search_query = self.request.get('search_query', '')
    elif group != source.BLOCKS:
      activity_id = self.request.get('activity_id', '')

    # pass query params through
    params = dict(self.request.params.items())
    params.update({
      'plaintext': 'true',
      'cache': 'false',
      'search_query': search_query,
    })

    return self.redirect('/%s/%s/%s/@app/%s?%s' % (
      site, urllib.parse.quote_plus(user), group, activity_id,
      urllib.parse.urlencode(params)))


class UrlHandler(api.Handler):
  """Handles URL requests from the interactive demo form on the front page.

  Responses are cached for 10m. You can skip the cache by including a cache=false
  query param. Background: https://github.com/snarfed/bridgy/issues/665
  """
  handle_exception = handlers.handle_exception

  @handlers.cache_response(api.RESPONSE_CACHE_TIME)
  @api.canonicalize_domain
  def get(self):
    input = util.get_required_param(self, 'input')
    if input not in INPUTS:
      raise exc.HTTPBadRequest('Invalid input: %s, expected one of %r' %
                               (input, INPUTS))

    orig_url = util.get_required_param(self, 'url')
    fragment = urllib.parse.urlparse(orig_url).fragment
    if fragment and input != 'html':
        raise exc.HTTPBadRequest('URL fragments only supported with input=html.')

    resp = util.requests_get(orig_url, gateway=True)
    final_url = resp.url

    # decode data
    if input in ('activitystreams', 'as1', 'as2', 'mf2-json', 'json-mf2', 'jsonfeed'):
      try:
        body_json = json_loads(resp.text)
        body_items = (body_json if isinstance(body_json, list)
                      else body_json.get('items') or [body_json])
      except (TypeError, ValueError):
        raise exc.HTTPBadRequest('Could not decode %s as JSON' % final_url)

    mf2 = None
    if input == 'html':
      mf2 = util.parse_mf2(resp, id=fragment)
      if id and not mf2:
        raise exc.HTTPBadRequest('Got fragment %s but no element found with that id.' % fragment)
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
        if util.domain_or_parent_in(urllib.parse.urlparse(url).netloc, SILO_DOMAINS):
          return {'items': [{'type': ['h-card'], 'properties': {'url': [url]}}]}
        return util.fetch_mf2(url, gateway=True)

      try:
        actor = microformats2.find_author(mf2, fetch_mf2_func=fetch_mf2_func)
        title = microformats2.get_title(mf2)
        hfeed = mf2util.find_first_entry(mf2, ['h-feed'])
      except (KeyError, ValueError) as e:
        raise exc.HTTPBadRequest('Could not parse %s as %s: %s' % (final_url, input, e))

    try:
      if input in ('as1', 'activitystreams'):
        activities = body_items
      elif input == 'as2':
        activities = [as2.to_as1(obj) for obj in body_items]
      elif input == 'atom':
        try:
          activities = atom.atom_to_activities(resp.text)
        except ElementTree.ParseError as e:
          raise exc.HTTPBadRequest('Could not parse %s as XML: %s' % (final_url, e))
        except ValueError as e:
          raise exc.HTTPBadRequest('Could not parse %s as Atom: %s' % (final_url, e))
      elif input == 'html':
        activities = microformats2.html_to_activities(resp, url=final_url,
                                                      id=fragment, actor=actor)
      elif input in ('mf2-json', 'json-mf2'):
        activities = [microformats2.json_to_object(item, actor=actor)
                      for item in mf2.get('items', [])]
      elif input == 'jsonfeed':
        activities, actor = jsonfeed.jsonfeed_to_activities(body_json)
    except ValueError as e:
      logging.warning('parsing input failed', stack_info=True)
      self.abort(400, 'Could not parse %s as %s: %s' % (final_url, input, str(e)))

    self.write_response(source.Source.make_activities_base_response(activities),
                        url=final_url, actor=actor, title=title, hfeed=hfeed)

  head = get


class MastodonStart(mastodon.StartHandler):
  """Mastodon OAuth handler wrapper that handles URL discovery errors.

  Used to catch when someone enters a Mastodon instance URL that doesn't exist
  or isn't actually a Mastodon instance.
  """
  def app_name(self):
    return 'granary'

  def handle_exception(self, e, debug):
    if isinstance(e, (ValueError, requests.RequestException, exc.HTTPException)):
      logging.warning('', stack_info=True)
      return self.redirect('/?%s#logins' % urllib.parse.urlencode({'failure': str(e)}))

    return super(MastodonStart, self).handle_exception(e, debug)


oauth_routes = []
for silo, module in OAUTHS.items():
  starter = MastodonStart if silo == 'mastodon' else module.StartHandler
  oauth_routes.extend((
    ('/%s/start_auth' % silo, starter.to('/%s/oauth_callback' % silo)),
    ('/%s/oauth_callback' % silo, module.CallbackHandler.to('/#logins')),
  ))

application = handlers.ndb_context_middleware(webapp2.WSGIApplication([
  ('/', FrontPageHandler),
  ('/demo', DemoHandler),
  ('/url', UrlHandler),
  ('/cron/build_circle', cron.BuildCircle),
] + oauth_routes + handlers.HOST_META_ROUTES + [
  ('.*', api.Handler),
], debug=appengine_info.DEBUG), client=appengine_config.ndb_client)
