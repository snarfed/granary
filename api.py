"""API view.

Implements the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-Data.xml

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

from flask import abort, request
from oauth_dropins.webutil import flask_util, util
from oauth_dropins.webutil.util import json_dumps, json_loads
from werkzeug.exceptions import BadRequest

import app
from granary import (
  as2,
  atom,
  facebook,
  flickr,
  github,
  instagram,
  jsonfeed,
  mastodon,
  microformats2,
  pixelfed,
  meetup,
  reddit,
  rss,
  source,
  twitter,
)
from granary.source import GROUPS

ITEMS_PER_PAGE_MAX = 100
ITEMS_PER_PAGE_DEFAULT = 10

# default values for each part of the API request path except the site, e.g.
# /twitter/@me/@self/@all/...
PATH_DEFAULTS = ((source.ME,), (source.ALL, source.FRIENDS), (source.APP,), ())
MAX_PATH_LEN = len(PATH_DEFAULTS) + 1


# TODO
# canonicalize_domain = handlers.redirect(
#   ('granary-demo.appspot.com', 'www.granary.io'), 'granary.io')

SILOS = ','.join(app.SILOS)
@app.app.route(f'/<any({SILOS}):site>/<path:path>', methods=('GET', 'HEAD'))
@app.app.route(f'/<any({SILOS}):site>/', methods=('GET', 'HEAD'),
               defaults={'path': None})
@flask_util.cached(app.cache, app.RESPONSE_CACHE_TIME)
def api(site, path):
  """Handles an API GET.

  Request path is of the form /site/user_id/group_id/app_id/activity_id ,
  where each element except site is an optional string object id.
  """
  # parse path
  if not path:
    args = []
  else:
    args = urllib.parse.unquote(path).strip('/').split('/')
    if len(args) > MAX_PATH_LEN:
      return f'Expected max {MAX_PATH_LEN} path elements; found {len(args) + 1}', 404

  # make source instance
  if site == 'twitter':
    src = twitter.Twitter(
      access_token_key=flask_util.get_required_param('access_token_key'),
      access_token_secret=flask_util.get_required_param('access_token_secret'))
  elif site == 'facebook':
    return abort(400, 'Sorry, Facebook is no longer available in the REST API. Try the library instead!')
  elif site == 'flickr':
    src = flickr.Flickr(
      access_token_key=flask_util.get_required_param('access_token_key'),
      access_token_secret=flask_util.get_required_param('access_token_secret'))
  elif site == 'github':
    src = github.GitHub(
      access_token=flask_util.get_required_param('access_token'))
  elif site == 'instagram':
    if request.args.get('interactive').lower() == 'true':
      src = instagram.Instagram(scrape=True)
    else:
      return abort(400, 'Sorry, Instagram is not currently available in the REST API. Try the library instead!')
  elif site == 'mastodon':
    src = mastodon.Mastodon(
      instance=flask_util.get_required_param('instance'),
      access_token=flask_util.get_required_param('access_token'),
      user_id=flask_util.get_required_param('user_id'))
  elif site == 'meetup':
    src = meetup.Meetup(
      access_token_key=flask_util.get_required_param('access_token_key'),
      access_token_secret=flask_util.get_required_param('access_token_secret'))
  elif site == 'pixelfed':
    src = pixelfed.Pixelfed(
      instance=flask_util.get_required_param('instance'),
      access_token=flask_util.get_required_param('access_token'),
      user_id=flask_util.get_required_param('user_id'))
  elif site == 'reddit':
    src = reddit.Reddit(refresh_token=flask_util.get_required_param('refresh_token')) # the refresh_roken should be returned but is not appearing
  else:
    src_cls = source.sources.get(site)
    src = src_cls(**request.args)

  # decode tag URI ids
  for i, arg in enumerate(args):
    parsed = util.parse_tag_uri(arg)
    if parsed:
      domain, id = parsed
      if domain != src.DOMAIN:
        raise BadRequest('Expected domain %s in tag URI %s, found %s' %
                                 (src.DOMAIN, arg, domain))
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
    # other exceptions are handled by webutil.handlers.handle_exception(),
    # which uses interpret_http_exception(), etc.

  logging.info(f'Got activities: {json_dumps(response, indent=2)}')

  # fetch actor if necessary
  actor = response.get('actor')
  if not actor and request.args.get('format') == 'atom':
    # atom needs actor
    actor = src.get_actor(user_id) if src else {}
    logging.info(f'Got actor: {json_dumps(actor, indent=2)}')

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

  return kwargs


def get_positive_int(param):
  try:
    val = request.args.get(param, 0)
    val = int(val)
    assert val >= 0
    return val
  except (ValueError, AssertionError):
    raise BadRequest('Invalid %s: %s (should be positive int)' %
                             (param, val))
