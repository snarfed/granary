"""API view.

Implements the OpenSocial ActivityStreams REST API:
https://opensocial.github.io/spec/2.5.1/Social-API-Server.xml#ActivityStreams-Service
https://opensocial.github.io/spec/2.5.1/Core-API-Server.xml

Request paths are of the form /user_id/group_id/app_id/activity_id, where each
element is optional. user_id may be @me. group_id may be @all, @friends
(currently identical to @all), @self, @me, @search, or @blocks. app_id may be
@app, but it doesn't matter, it's currently ignored.

The supported query parameters are startIndex and count, which are handled as
described in OpenSocial (above) and OpenSearch.

Other relevant activity REST APIs:
http://status.net/wiki/Twitter-compatible_API
http://wiki.activitystrea.ms/w/page/25347165/StatusNet%20Mapping
https://developers.google.com/+/api/latest/activities/list

ActivityStreams specs:
http://activitystrea.ms/specs/

Atom format spec:
http://atomenabled.org/developers/syndication/

"""
import logging
import urllib.parse

from cachetools import cached, LRUCache
from flask import abort, request
from oauth_dropins.webutil import flask_util, util
from oauth_dropins.webutil.flask_util import error, get_required_param
from oauth_dropins.webutil.util import json_dumps, json_loads
from werkzeug.exceptions import BadRequest

import app
from granary import (
  bluesky,
  facebook,
  flickr,
  github,
  instagram,
  mastodon,
  nostr,
  pixelfed,
  meetup,
  reddit,
  source,
  twitter,
)
from granary.source import GROUPS

logger = logging.getLogger(__name__)

ITEMS_PER_PAGE_MAX = 100
ITEMS_PER_PAGE_DEFAULT = 10

# default values for each part of the API request path except the site, e.g.
# /twitter/@me/@self/@all/...
PATH_DEFAULTS = ((source.ME,), (source.ALL, source.FRIENDS), (source.APP,), ())
MAX_PATH_LEN = len(PATH_DEFAULTS) + 1


# cache access tokens in Bluesky instances
@cached(LRUCache(1000))
def bluesky_instance(**kwargs):
  return bluesky.Bluesky(**kwargs)


@app.app.route('/<path:path>', methods=('GET', 'HEAD'))
@flask_util.headers(app.CACHE_CONTROL)
def api(path):
  """Handles an API GET.

  Request path is of the form /site/user_id/group_id/app_id/activity_id ,
  where each element except site is an optional string object id.
  """
  # parse path
  if not path:
    args = []
  else:
    path = urllib.parse.unquote(path).strip('/')
    # allow / chars in activity_id for bluesky because its activity ids are
    # at:// URIs
    maxsplit = MAX_PATH_LEN - 1 if path.startswith('bluesky') else -1
    args = path.split('/', maxsplit=maxsplit)
    if len(args) > MAX_PATH_LEN:
      return f'Expected max {MAX_PATH_LEN} path elements; found {len(args)}', 404

  # make source instance
  site = args.pop(0)
  if site in ('facebook', 'instagram', 'twitter'):
    return f'Sorry, {site.capitalize()} is not available in the REST API. Try the library instead!', 404
  elif site == 'flickr':
    src = flickr.Flickr(
      access_token_key=get_required_param('access_token_key'),
      access_token_secret=get_required_param('access_token_secret'))
  elif site == 'github':
    src = github.GitHub(
      access_token=get_required_param('access_token'))
  elif site == 'mastodon':
    src = mastodon.Mastodon(
      instance=get_required_param('instance'),
      access_token=get_required_param('access_token'),
      user_id=get_required_param('user_id'))
  elif site == 'nostr':
    relay = get_required_param('relay')
    if not relay.startswith('ws://') and  not relay.startswith('wss://'):
      relay = 'wss://' + relay
    src = nostr.Nostr([relay])
  elif site == 'meetup':
    src = meetup.Meetup(
      access_token_key=get_required_param('access_token_key'),
      access_token_secret=get_required_param('access_token_secret'))
  elif site == 'pixelfed':
    src = pixelfed.Pixelfed(
      instance=get_required_param('instance'),
      access_token=get_required_param('access_token'),
      user_id=get_required_param('user_id'))
  elif site == 'reddit':
    # the refresh_token should be returned but is not appearing
    src = reddit.Reddit(refresh_token=get_required_param('refresh_token'))
  elif site == 'bluesky':
    src = bluesky_instance(
      handle=get_required_param('user_id'),
      app_password=request.values.get('app_password'),
      access_token=request.values.get('access_token'),
    )
  else:
    src_cls = source.sources.get(site)
    if not src_cls:
      return f'Unknown site {site}', 404
    src = src_cls(**request.args)

  # decode tag URI ids
  for i, arg in enumerate(args):
    parsed = util.parse_tag_uri(arg)
    if parsed:
      domain, id = parsed
      if domain != src.DOMAIN:
        raise BadRequest(f'Expected domain {src.DOMAIN} in tag URI {arg}, found {domain}')
      args[i] = id

  # handle default path elements
  args = [None if a in defaults else a
          for a, defaults in zip(args, PATH_DEFAULTS)]
  user_id = args[0] if args else None

  # get activities (etc)
  try:
    if len(args) >= 2 and args[1] == '@blocks':
      try:
        response = {'items': src.get_blocklist()}
      except source.RateLimited as e:
        if not e.partial:
          return abort(429, str(e))
        response = {'items': e.partial}
    else:
      response = src.get_activities_response(*args, **get_kwargs())
  except (NotImplementedError, ValueError) as e:
    return abort(400, str(e))
    # other exceptions are handled by webutil.flask_util.handle_exception(),
    # which uses interpret_http_exception(), etc.

  logger.info(f'Got {len(response.get("items", []))} activities')
  logger.debug(f'  activities: {json_dumps(response, indent=2)}')

  # fetch actor if necessary
  actor = response.get('actor')
  if not actor and request.args.get('format') == 'atom':
    # atom needs actor
    if not user_id:
      error('atom output requires user id')
    try:
      actor = src.get_actor(user_id) if src else {}
    except ValueError as e:
      error(f"Couldn't fetch {user_id}: {e}", exc_info=True)
    logger.debug(f'Got actor: {json_dumps(actor, indent=2)}')

  return app.make_response(response, actor=actor, url=src.BASE_URL)


def get_kwargs():
  """Extracts, normalizes and returns the kwargs for get_activities().

  Returns:
    dict
  """
  start_index = get_positive_int('startIndex')
  count = get_positive_int('count')

  if count == 0:
    count = ITEMS_PER_PAGE_DEFAULT - start_index
  else:
    count = min(count, ITEMS_PER_PAGE_MAX)

  kwargs = {'start_index': start_index, 'count': count}

  search_query = request.args.get('search_query') or request.args.get('q')
  if search_query:
    kwargs['search_query'] = search_query

  cookie = request.args.get('cookie')
  if cookie:
    kwargs['cookie'] = cookie

  shares = request.values.get('shares')
  if shares:
    kwargs['include_shares'] = shares.lower() != 'false'

  return kwargs


def get_positive_int(param):
  try:
    val = request.args.get(param, 0)
    val = int(val)
    assert val >= 0
    return val
  except (ValueError, AssertionError):
    raise BadRequest(f'Invalid {param}: {val} (should be positive int)')
