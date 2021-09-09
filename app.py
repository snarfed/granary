"""Serves the the front page, discovery files, and OAuth flows.
"""
import datetime
import importlib
import logging
import urllib.parse
from xml.etree import ElementTree

from flask import abort, Flask, redirect, render_template, request
from flask_caching import Cache
from google.cloud import ndb
import mf2util
from oauth_dropins import (
  facebook,
  flickr,
  github,
  mastodon,
  pixelfed,
  twitter,
  reddit,
)
from oauth_dropins.webutil import (
  appengine_config,
  appengine_info,
  flask_util,
  util,
)
from oauth_dropins.webutil.util import json_dumps, json_loads
import requests
from werkzeug.exceptions import BadRequest

from granary import (
  as2,
  atom,
  jsonfeed,
  microformats2,
  rss,
  source,
)
from granary.facebook import Facebook
from granary.flickr import Flickr
from granary.github import GitHub
from granary.mastodon import Mastodon
from granary.meetup import Meetup
from granary.pixelfed import Pixelfed
from granary.instagram import Instagram
from granary.twitter import Twitter
from granary.reddit import Reddit


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
SILOS = [
  'flickr',
  'github',
  'instagram',
  'mastodon',
  'pixelfed',
  'meetup',
  'twitter',
  'reddit',
]
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
  'meetup': 'rsvp',
  # https://docs.pixelfed.org/technical-documentation/api-v1.html
  'pixelfed': 'read',
}
# map granary format name to MIME type. list of official MIME types:
# https://www.iana.org/assignments/media-types/media-types.xhtml
FORMATS = {
  'activitystreams': 'application/stream+json',
  'as1': 'application/stream+json',
  'as1-xml': 'application/xml',
  'as2': 'application/activity+json',
  'atom': 'application/atom+xml',
  'html': 'text/html',
  'json': 'application/json',
  'json-mf2': 'application/mf2+json',
  'jsonfeed': 'application/json',
  'mf2-json': 'application/mf2+json',
  'rss': 'application/rss+xml',
  'xml': 'application/xml',
}
XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>%s</response>
"""

RESPONSE_CACHE_TIME = datetime.timedelta(minutes=10)


app = Flask('bridgy-fed')
app.template_folder = './granary/templates'
app.config.from_pyfile('config.py')
app.url_map.converters['regex'] = flask_util.RegexConverter
app.after_request(flask_util.default_modern_headers)
app.register_error_handler(Exception, flask_util.handle_exception)
app.before_request(flask_util.canonicalize_domain(
  ('granary-demo.appspot.com', 'www.granary.io'), 'granary.io'))

app.wsgi_app = flask_util.ndb_context_middleware(
    app.wsgi_app, client=appengine_config.ndb_client)

cache = Cache(app)


@app.route('/')
def front_page():
  """Renders and serves the front page."""
  vars = dict(request.args)

  key = vars.get('auth_entity')
  if key:
    vars['entity'] = ndb.Key(urlsafe=key).get()
    if vars['entity']:
      vars.setdefault('site', vars['entity'].site_name().lower())

  vars.update({
    silo + '_html': module.Start.button_html(
      '/%s/start_auth' % silo,
      image_prefix='/oauth_dropins_static/',
      outer_classes='col-lg-2 col-sm-4 col-xs-6',
      scopes=SCOPE_OVERRIDES.get(silo, ''),
    )
    for silo, module in OAUTHS.items()})

  return render_template('index.html', **vars)


@app.route('/demo')
def demo():
  """Handles silo requests from the interactive demo form on the front page."""
  site = request.values['site']
  user = request.args.get('user_id', '')
  group = request.args.get('group_id', '')
  if group == '@list':
    group = request.values['list']

  activity_id = search_query = ''
  if group == source.SEARCH:
    search_query = request.args.get('search_query', '')
  elif group != source.BLOCKS:
    activity_id = request.args.get('activity_id', '')

  # pass query params through
  params = dict(request.args.items())
  params.update({
    'plaintext': 'true',
    'cache': 'false',
    'search_query': search_query,
  })

  path = '/'.join(urllib.parse.quote_plus(part, safe='@')
                  for part in (site, user, group, '@app', activity_id))
  return redirect(f'/{path}?{urllib.parse.urlencode(params)}')


@app.route('/url', methods=('GET', 'HEAD'))
@flask_util.cached(cache, RESPONSE_CACHE_TIME)
def url():
  """Handles URL requests from the interactive demo form on the front page.

  Responses are cached for 10m. You can skip the cache by including a cache=false
  query param. Background: https://github.com/snarfed/bridgy/issues/665
  """
  input = request.values['input']
  if input not in INPUTS:
    raise BadRequest('Invalid input: %s, expected one of %r' %
                             (input, INPUTS))

  orig_url = request.values['url']
  # TODO: revert if/when it's back up
  if orig_url.startswith('https://rss-bridge.netlib.re/'):
    return 'Sorry, rss-bridge.netlib.re is down right now.', 502

  fragment = urllib.parse.urlparse(orig_url).fragment
  if fragment and input != 'html':
      raise BadRequest('URL fragments only supported with input=html.')

  resp = util.requests_get(orig_url, gateway=True)
  final_url = resp.url

  # decode data
  if input in ('activitystreams', 'as1', 'as2', 'mf2-json', 'json-mf2', 'jsonfeed'):
    try:
      body_json = resp.json()
      body_items = (body_json if isinstance(body_json, list)
                    else body_json.get('items') or [body_json])
    except (TypeError, ValueError):
      raise BadRequest('Could not decode %s as JSON' % final_url)

  mf2 = None
  if input == 'html':
    mf2 = util.parse_mf2(resp, id=fragment)
    if id and not mf2:
      raise BadRequest('Got fragment %s but no element found with that id.' % fragment)
  elif input in ('mf2-json', 'json-mf2'):
    mf2 = body_json
    if not hasattr(mf2, 'get'):
      raise BadRequest(
        'Expected microformats2 JSON input to be dict, got %s' %
        mf2.__class__.__name__)
    mf2.setdefault('rels', {})  # mf2util expects rels

  actor = None
  title = None
  hfeed = None
  if mf2:
    logging.info(f'Got mf2: {json_dumps(mf2, indent=2)}')
    def fetch_mf2_func(url):
      if util.domain_or_parent_in(urllib.parse.urlparse(url).netloc, SILO_DOMAINS):
        return {'items': [{'type': ['h-card'], 'properties': {'url': [url]}}]}
      return util.fetch_mf2(url, gateway=True)

    try:
      actor = microformats2.find_author(mf2, fetch_mf2_func=fetch_mf2_func)
      title = microformats2.get_title(mf2)
      hfeed = mf2util.find_first_entry(mf2, ['h-feed'])
    except (KeyError, ValueError) as e:
      raise BadRequest('Could not parse %s as %s: %s' % (final_url, input, e))

  try:
    if input in ('as1', 'activitystreams'):
      activities = body_items
    elif input == 'as2':
      activities = [as2.to_as1(obj) for obj in body_items]
    elif input == 'atom':
      try:
        activities = atom.atom_to_activities(resp.text)
      except ElementTree.ParseError as e:
        raise BadRequest('Could not parse %s as XML: %s' % (final_url, e))
      except ValueError as e:
        raise BadRequest('Could not parse %s as Atom: %s' % (final_url, e))
    elif input == 'html':
      activities = microformats2.html_to_activities(resp, url=final_url,
                                                    id=fragment, actor=actor)
    elif input in ('mf2-json', 'json-mf2'):
      activities = [microformats2.json_to_object(item, actor=actor)
                    for item in mf2.get('items', [])]
    elif input == 'jsonfeed':
      activities, actor = jsonfeed.jsonfeed_to_activities(body_json)
  except ValueError as e:
    logging.warning('parsing input failed', exc_info=True)
    return abort(400, 'Could not parse %s as %s: %s' % (final_url, input, str(e)))

  logging.info(f'Converted to AS1: {json_dumps(activities, indent=2)}')

  return make_response(source.Source.make_activities_base_response(activities),
                       url=final_url, actor=actor, title=title, hfeed=hfeed)


def make_response(response, actor=None, url=None, title=None, hfeed=None):
  """Converts ActivityStreams activities and returns a Flask response.

  Args:
    response: response dict with values based on OpenSocial ActivityStreams
      REST API, as returned by Source.get_activities_response()
    actor: optional ActivityStreams actor dict for current user. Only used
      for Atom and JSON Feed output.
    url: the input URL
    title: string, used in feed output (Atom, JSON Feed, RSS)
    hfeed: dict, parsed mf2 h-feed, if available
  """
  format = request.args.get('format') or request.args.get('output') or 'json'
  if format not in FORMATS:
    raise BadRequest('Invalid format: %s, expected one of %r' %
                             (format, FORMATS))

  headers = {}
  if 'plaintext' in request.args:
    # override content type
    headers['Content-Type'] = 'text/plain'
  else:
    content_type = FORMATS.get(format)
    if content_type:
      headers['Content-Type'] = content_type

  if request.method == 'HEAD':
    return '', headers

  activities = response['items']
  try:
    if format in ('as1', 'json', 'activitystreams'):
      return response, headers

    elif format == 'as2':
      response.update({
        'items': [as2.from_as1(a) for a in activities],
        'totalItems': response.pop('totalResults', None),
        'updated': response.pop('updatedSince', None),
        'filtered': None,
        'sorted': None,
      })
      return util.trim_nulls(response), headers

    elif format == 'atom':
      hub = request.args.get('hub')
      reader = request.args.get('reader', 'true').lower()
      if reader not in ('true', 'false'):
        return abort(400, 'reader param must be either true or false')
      if not actor and hfeed:
        actor = microformats2.json_to_object({
          'properties': hfeed.get('properties', {}),
        })

      # encode/quote Unicode chars in URLs; only ASCII is safe in HTTP headers
      link_self = urllib.parse.quote(request.url, safe=':/?&=%')
      headers['Link'] = [f'<{link_self}>; rel="self"']
      if hub:
        link_hub = urllib.parse.quote(hub, safe=':/?&=')
        headers['Link'].append(f'<{link_hub}>; rel="hub"')

      return atom.activities_to_atom(
        activities, actor,
        host_url=url or request.host_url + '/',
        request_url=request.url,
        xml_base=util.base_url(url),
        title=title,
        rels={'hub': hub} if hub else None,
        reader=(reader == 'true'),
      ), headers

    elif format == 'rss':
      if not title:
        title = 'Feed for %s' % url
      return rss.from_activities(
        activities, actor, title=title,
        feed_url=request.url, hfeed=hfeed,
        home_page_url=util.base_url(url)), headers

    elif format in ('as1-xml', 'xml'):
      return XML_TEMPLATE % util.to_xml(response), headers

    elif format == 'html':
      return microformats2.activities_to_html(activities), headers

    elif format in ('mf2-json', 'json-mf2'):
      return {
        'items': [microformats2.activity_to_json(a) for a in activities],
      }, headers

    elif format == 'jsonfeed':
      try:
        return jsonfeed.activities_to_jsonfeed(
          activities, actor=actor, title=title, feed_url=request.url,
        ), headers
      except TypeError as e:
        raise BadRequest('Unsupported input data: %s' % e)

  except ValueError as e:
    logging.warning('converting to output format failed', exc_info=True)
    return abort(400, 'Could not convert to %s: %s' % (format, str(e)))


oauth_routes = []
for silo, module in OAUTHS.items():
  start = f'/{silo}/start_auth'
  callback = f'/{silo}/oauth_callback'
  app.add_url_rule(start, view_func=module.Start.as_view(start, callback),
                   methods=['POST'])
  app.add_url_rule(callback, view_func=module.Callback.as_view(callback, '/#logins'))

import api
