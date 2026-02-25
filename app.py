"""Serves the the front page, discovery files, and OAuth flows.
"""
import datetime
import functools
import importlib
import logging
import urllib.parse
from xml.etree import ElementTree

from flask import abort, Flask, redirect, render_template, request
import flask_caching
import flask_gae_static
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
from werkzeug.exceptions import BadRequest, HTTPException

from granary import (
  as1,
  as2,
  atom,
  bluesky,
  icalendar,
  jsonfeed,
  microformats2,
  nostr,
  rss,
  source,
)
from granary.facebook import Facebook
from granary.flickr import Flickr
from granary.github import GitHub
from granary.mastodon import Mastodon
from granary.nostr import Nostr
from granary.meetup import Meetup
from granary.pixelfed import Pixelfed
from granary.instagram import Instagram
from granary.twitter import Twitter
from granary.reddit import Reddit

logger = logging.getLogger(__name__)

INPUTS = (
  'activitystreams',
  'as1',
  'as2',
  'atom',
  'bluesky',
  'html',
  'icalendar',
  'json-mf2',
  'jsonfeed',
  'mf2-json',
  'nostr',
  'rss',
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
  name: importlib.import_module(f'oauth_dropins.{name}')
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
  'activitystreams': as1.CONTENT_TYPE,
  'as1': as1.CONTENT_TYPE,
  'as1-xml': 'application/xml; charset=utf-8',
  'as2': as2.CONTENT_TYPE,
  'atom': atom.CONTENT_TYPE,
  'bluesky': 'application/json',
  'html': 'text/html; charset=utf-8',
  'icalendar': icalendar.CONTENT_TYPE,
  'json': 'application/json',
  'json-mf2': 'application/mf2+json',
  'jsonfeed': 'application/feed+json',
  'mf2-json': 'application/mf2+json',
  'nostr': 'application/json',
  'rss': rss.CONTENT_TYPE,
  'xml': 'application/xml; charset=utf-8',
}
XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>%s</response>
"""

CACHE_EXPIRATION = datetime.timedelta(minutes=5)
CACHE_CONTROL = {
  'Cache-Control': f'public, max-age={CACHE_EXPIRATION.total_seconds()}',
}


app = Flask(__name__, static_folder=None)
app.template_folder = './granary/templates'
app.json.compact = False
app.config.from_pyfile('config.py')
app.url_map.converters['regex'] = flask_util.RegexConverter
app.after_request(flask_util.default_modern_headers)
app.register_error_handler(Exception, flask_util.handle_exception)
app.before_request(flask_util.canonicalize_domain(
  ('granary-demo.appspot.com', 'www.granary.io'), 'granary.io'))
if appengine_info.DEBUG or appengine_info.LOCAL_SERVER:
  flask_gae_static.init_app(app)

app.wsgi_app = flask_util.ndb_context_middleware(
    app.wsgi_app, client=appengine_config.ndb_client)

cache = flask_caching.Cache(app)

util.set_user_agent('granary (https://granary.io/)')


@app.route('/')
def front_page():
  """Renders and serves the front page."""
  vars = {
    **dict(request.args),
    'request': request,
    'util': util,
  }
  vars.setdefault('output', vars.get('format'))

  key = vars.get('auth_entity')
  if key:
    vars['entity'] = ndb.Key(urlsafe=key).get()
    if vars['entity']:
      vars.setdefault('site', vars['entity'].site_name().lower())

  if vars.get('site') in ('mastodon', 'pixelfed') and not vars.get('entity'):
    raise BadRequest('missing auth_entity')

  vars.update({
    silo + '_html': module.Start.button_html(
      f'/{silo}/start_auth',
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
@flask_util.headers(CACHE_CONTROL)
@flask_util.cached(cache, timeout=CACHE_EXPIRATION, http_5xx=True)
def url():
  """Handles URL requests from the interactive demo form on the front page.

  Responses are cached for 10m.
  """
  input = request.values['input']
  if input not in INPUTS:
    raise BadRequest(f'Invalid input: {input}, expected one of {INPUTS!r}')

  orig_url = request.values['url']
  # TODO: revert if/when it's back up
  if orig_url.startswith('https://rss-bridge.netlib.re/'):
    return 'Sorry, rss-bridge.netlib.re is down right now.', 502

  try:
    fragment = urllib.parse.urlparse(orig_url).fragment
  except ValueError as e:
    raise BadRequest(f'Invalid url: {e}')

  if fragment and input != 'html':
      raise BadRequest('URL fragments only supported with input=html.')

  headers = {}
  if input == 'as2':
    headers['Accept'] = as2.CONTENT_TYPE

  try:
    resp = util.requests_get(orig_url, headers=headers, gateway=True)
  except ValueError as e:
    raise BadRequest(f'Invalid url: {e}')
  except HTTPException as e:
    # do this manually so that 504s for timeouts get cached
    return flask_util.handle_exception(e)

  final_url = resp.url

  # decode data
  if input in ('activitystreams', 'as1', 'as2', 'bluesky', 'mf2-json',
               'json-mf2', 'jsonfeed', 'nostr'):
    try:
      body_json = resp.json()
      body_items = (body_json if isinstance(body_json, list)
                    else body_json.get('items') or body_json.get('feed')
                    or [body_json])
    except (TypeError, ValueError):
      raise BadRequest(f'Could not decode {final_url} as JSON')

  mf2 = None
  if input == 'html':
    mf2 = util.parse_mf2(resp, id=fragment)
    if id and not mf2:
      raise BadRequest(f'Got fragment {fragment} but no element found with that id.')
  elif input in ('mf2-json', 'json-mf2'):
    mf2 = body_json
    if not hasattr(mf2, 'get'):
      raise BadRequest(
        f'Expected microformats2 JSON input to be dict, got {mf2.__class__.__name__}')
    mf2.setdefault('rels', {})  # mf2util expects rels

  actor = None
  title = None
  hfeed = None
  if mf2:
    logger.debug(f'Got mf2: {json_dumps(mf2, indent=2)}')
    def fetch_mf2_func(url):
      if util.domain_or_parent_in(url, SILO_DOMAINS):
        return {'items': [{'type': ['h-card'], 'properties': {'url': [url]}}]}
      return util.fetch_mf2(url, gateway=True)

    try:
      actor = microformats2.find_author(mf2, fetch_mf2_func=fetch_mf2_func)
      title = microformats2.get_title(mf2)
      hfeed = mf2util.find_first_entry(mf2, ['h-feed'])
    except (KeyError, ValueError, TypeError) as e:
      raise BadRequest(f'Could not parse {final_url} as {input}: {e}')

  try:
    if input in ('as1', 'activitystreams'):
      activities = body_items
    elif input == 'as2':
      activities = [as2.to_as1(obj) for obj in body_items]
    elif input == 'atom':
      activities = atom.atom_to_activities(resp.text)
    elif input == 'bluesky':
      activities = [bluesky.to_as1(obj) for obj in body_items]
    elif input == 'html':
      activities = microformats2.html_to_activities(resp, url=final_url,
                                                    id=fragment, actor=actor)
    elif input in ('json-mf2', 'mf2-json'):
      activities = [microformats2.json_to_object(item, actor=actor)
                    for item in mf2.get('items', [])]
    elif input == 'jsonfeed':
      activities, actor = jsonfeed.jsonfeed_to_activities(body_json)
    elif input == 'nostr':
      activities = [nostr.to_as1(body_json)]
    elif input == 'icalendar':
      activities = icalendar.to_as1(resp.text)
    elif input == 'rss':
      activities = rss.to_activities(resp.text)
    else:
      assert False, f'Please file this as a bug! input {input} not implemented'
  except (AttributeError, ElementTree.ParseError, KeyError, ValueError) as e:
    logger.warning('parsing input failed', exc_info=True)
    return abort(400, f'Could not parse {final_url} as {input}: {str(e)}')

  logger.info(f'Converted {len(activities)} activities to AS1')
  logger.debug(f'  activities: {json_dumps(activities, indent=2)}')

  return make_response(source.Source.make_activities_base_response(activities),
                       url=final_url, actor=actor, title=title, hfeed=hfeed)


@app.route('/<any(scraped,html):_>', methods=('POST',))
def scraped(_):
  """Converts scraped HTML or JSON. Currently only supports Instagram.

  Accepts `POST` requests with silo HTML or JSON as input. Requires
  `site=instagram`, `output=...` (any supported output format), and input in
  either raw request body or MIME multipart encoded file. Requires the request
  or multipart file 's content-type to be either text/html or application/json,
  respectively.
  """
  site = request.values['site']
  if site != 'instagram':
    raise BadRequest(f'Invalid site: {site}, expected instagram')

  expected_types = (FORMATS['json'].split(';')[0], FORMATS['html'].split(';')[0])
  body = type = None

  # MIME multipart
  for name, file in request.files.items():
    type = file.mimetype.split(';')[0]
    body = file.read().decode(file.mimetype_params.get('charset') or 'utf-8')
    logger.debug(f'Examining MIME multipart file {name} {file.filename} {type}')
    if body and type in expected_types:
      break

  if not body or type not in expected_types:
    # raw request body
    logger.debug(f'Examining request body, content type {request.content_type}')
    type = request.content_type
    if type:
      type = type.split(';')[0]
    body = request.get_data(as_text=True)

  if not body or type not in expected_types:
    raise BadRequest(f'No {FORMATS["json"]} or {FORMATS["html"]} body found in request or MIME multipart file')

  logger.info(f'Got input: {util.ellipsize(body, words=999, chars=999)}')

  if type == FORMATS['json']:
    activities, actor = Instagram().scraped_json_to_activities(
      json_loads(body), fetch_extras=False)
  else:
    activities, actor = Instagram().scraped_to_activities(body, fetch_extras=False)
  logger.info(f'Converted {len(activities)} activities to AS1')
  logger.debug(f'Converted to AS1: {json_dumps(activities, indent=2)}')

  title = 'Instagram feed'
  if actor:
    title += f' for {actor.get("username") or actor.get("displayName")}'
  return make_response(source.Source.make_activities_base_response(activities),
                       actor=actor, title=title)


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
  format = request.values.get('format') or request.values.get('output') or 'json'
  if format not in FORMATS:
    raise BadRequest(f'Invalid format: {format}, expected one of {FORMATS!r}')

  headers = {}
  if 'plaintext' in request.values:
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

    elif format == 'bluesky':
      return {'feed': [bluesky.from_as1(a) for a in activities]}, headers

    elif format == 'atom':
      hub = request.values.get('hub')
      reader = request.values.get('reader', 'true').lower()
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
        title = f'Feed for {url}'
      return rss.from_activities(
        activities, actor, title=title,
        feed_url=request.url, hfeed=hfeed,
        home_page_url=util.base_url(url)), headers

    elif format == 'icalendar':
      return icalendar.from_as1(
        activities, actor=actor, title=title), headers

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
        raise BadRequest(f'Unsupported input data: {e}')

    elif format == 'nostr':
      return {
        'items': [nostr.from_as1(a) for a in activities],
      }, headers

    else:
      assert False, f'Please file this as a bug! format {format} not implemented'

  except (AttributeError, KeyError, NotImplementedError, ValueError) as e:
    logger.warning('converting to output format failed', exc_info=True)
    return abort(400, f'Could not convert to {format}: {str(e)}')


def handle_discovery_errors(fn):
  """A wrapper that handles URL discovery errors.

  Used to catch Mastodon and IndieAuth connection failures, etc. Based on
  oauth-dropins's app.handle_discovery_errors.
  """
  @functools.wraps(fn)
  def wrapped(*args, **kwargs):
    try:
      return fn(*args, **kwargs)
    except (ValueError, requests.RequestException) as e:
      logger.warning('', exc_info=True)
      return redirect('/?' + urllib.parse.urlencode({'failure': str(e)}))

  return wrapped


class MastodonStart(mastodon.Start):
  """OAuth starter class with our app name and URL."""
  def app_name(self):
    return 'granary'

  def app_url(self):
    return 'https://granary.io/'

oauth_routes = []
for silo, module in OAUTHS.items():
  start = f'/{silo}/start_auth'
  callback = f'/{silo}/oauth_callback'
  start_cls = MastodonStart if silo == 'mastodon' else module.Start
  start_fn = handle_discovery_errors(start_cls.as_view(start, callback))
  app.add_url_rule(start, view_func=start_fn, methods=['POST'])
  callback_fn = handle_discovery_errors(module.Callback.as_view(callback, '/#logins'))
  app.add_url_rule(callback, view_func=callback_fn)

import api
