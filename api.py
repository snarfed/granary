"""API handler classes.

Implements the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-Data.xml

Request paths are of the form /user_id/group_id/app_id/activity_id, where
each element is optional. user_id may be @me. group_id may be @all, @friends
(currently identical to @all), or @self. app_id may be @app, but it doesn't
matter, it's currently ignored.

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
import datetime
import logging
import urllib.parse

from oauth_dropins.webutil import handlers
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads
import webapp2
from webob import exc

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
  rss,
  source,
  twitter,
)

XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>%s</response>
"""
ITEMS_PER_PAGE_MAX = 100
ITEMS_PER_PAGE_DEFAULT = 10
RESPONSE_CACHE_TIME = datetime.timedelta(minutes=10)

# default values for each part of the API request path except the site, e.g.
# /twitter/@me/@self/@all/...
PATH_DEFAULTS = ((source.ME,), (source.ALL, source.FRIENDS), (source.APP,), ())
MAX_PATH_LEN = len(PATH_DEFAULTS) + 1

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

canonicalize_domain = handlers.redirect(
  ('granary-demo.appspot.com', 'www.granary.io'), 'granary.io')


class Handler(handlers.ModernHandler):
  """Base class for API handlers.

  Responses are cached for 5m. You can skip the cache by including a cache=false
  query param. Background: https://github.com/snarfed/bridgy/issues/665

  Attributes:
    source: Source subclass
  """
  handle_exception = handlers.handle_exception

  @handlers.cache_response(RESPONSE_CACHE_TIME)
  @canonicalize_domain
  def get(self):
    """Handles an API GET.

    Request path is of the form /site/user_id/group_id/app_id/activity_id ,
    where each element except site is an optional string object id.
    """
    # parse path
    args = urllib.parse.unquote(self.request.path).strip('/').split('/')
    if not args or len(args) > MAX_PATH_LEN:
      raise exc.HTTPNotFound('Expected 1-%d path elements; found %d' %
                             (MAX_PATH_LEN, len(args)))

    # make source instance
    site = args.pop(0)
    if site == 'twitter':
      src = twitter.Twitter(
        access_token_key=util.get_required_param(self, 'access_token_key'),
        access_token_secret=util.get_required_param(self, 'access_token_secret'))
    elif site == 'facebook':
      self.abort(400, 'Sorry, Facebook is no longer available in the REST API. Try the library instead!')
    elif site == 'flickr':
      src = flickr.Flickr(
        access_token_key=util.get_required_param(self, 'access_token_key'),
        access_token_secret=util.get_required_param(self, 'access_token_secret'))
    elif site == 'github':
      src = github.GitHub(
        access_token=util.get_required_param(self, 'access_token'))
    elif site == 'instagram':
      if self.request.get('interactive').lower() == 'true':
        src = instagram.Instagram(scrape=True)
      else:
        self.abort(400, 'Sorry, Instagram is not currently available in the REST API. Try https://instagram-atom.appspot.com/ instead!')
    elif site == 'mastodon':
      src = mastodon.Mastodon(
        instance=util.get_required_param(self, 'instance'),
        access_token=util.get_required_param(self, 'access_token'),
        user_id=util.get_required_param(self, 'user_id'))
    else:
      src_cls = source.sources.get(site)
      if not src_cls:
        raise exc.HTTPNotFound('Unknown site %r' % site)
      src = src_cls(**self.request.params)

    # decode tag URI ids
    for i, arg in enumerate(args):
      parsed = util.parse_tag_uri(arg)
      if parsed:
        domain, id = parsed
        if domain != src.DOMAIN:
          raise exc.HTTPBadRequest('Expected domain %s in tag URI %s, found %s' %
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
            self.abort(429, str(e))
          response = {'items': e.partial}
      else:
        response = src.get_activities_response(*args, **self.get_kwargs())
    except (NotImplementedError, ValueError) as e:
      self.abort(400, str(e))
      # other exceptions are handled by webutil.handlers.handle_exception(),
      # which uses interpret_http_exception(), etc.

    # fetch actor if necessary
    actor = response.get('actor')
    if not actor and self.request.get('format') == 'atom':
      # atom needs actor
      actor = src.get_actor(user_id) if src else {}

    self.write_response(response, actor=actor, url=src.BASE_URL)

  head = get

  def write_response(self, response, actor=None, url=None, title=None,
                     hfeed=None):
    """Converts ActivityStreams activities and writes them out.

    Args:
      response: response dict with values based on OpenSocial ActivityStreams
        REST API, as returned by Source.get_activities_response()
      actor: optional ActivityStreams actor dict for current user. Only used
        for Atom and JSON Feed output.
      url: the input URL
      title: string, used in feed output (Atom, JSON Feed, RSS)
      hfeed: dict, parsed mf2 h-feed, if available
    """
    format = self.request.get('format') or self.request.get('output') or 'json'
    if format not in FORMATS:
      raise exc.HTTPBadRequest('Invalid format: %s, expected one of %r' %
                               (format, FORMATS))

    if 'plaintext' in self.request.params:
      # override content type
      self.response.headers['Content-Type'] = 'text/plain'
    else:
      content_type = FORMATS.get(format)
      if content_type:
        self.response.headers['Content-Type'] = content_type

    if self.request.method == 'HEAD':
      return

    activities = response['items']
    try:
      if format in ('as1', 'json', 'activitystreams'):
        self.response.out.write(json_dumps(response, indent=2))
      elif format == 'as2':
        response.update({
          'items': [as2.from_as1(a) for a in activities],
          'totalItems': response.pop('totalResults', None),
          'updated': response.pop('updatedSince', None),
          'filtered': None,
          'sorted': None,
        })
        self.response.out.write(json_dumps(util.trim_nulls(response), indent=2))
      elif format == 'atom':
        hub = self.request.get('hub')
        reader = self.request.get('reader', 'true').lower()
        if reader not in ('true', 'false'):
          self.abort(400, 'reader param must be either true or false')
        if not actor and hfeed:
          actor = microformats2.json_to_object({
            'properties': hfeed.get('properties', {}),
          })
        self.response.out.write(atom.activities_to_atom(
          activities, actor,
          host_url=url or self.request.host_url + '/',
          request_url=self.request.url,
          xml_base=util.base_url(url),
          title=title,
          rels={'hub': hub} if hub else None,
          reader=(reader == 'true')))
        self.response.headers.add('Link', str('<%s>; rel="self"' % self.request.url))
        if hub:
          self.response.headers.add('Link', str('<%s>; rel="hub"' % hub))
      elif format == 'rss':
        if not title:
          title = 'Feed for %s' % url
        self.response.out.write(rss.from_activities(
          activities, actor, title=title,
          feed_url=self.request.url, hfeed=hfeed,
          home_page_url=util.base_url(url)))
      elif format in ('as1-xml', 'xml'):
        self.response.out.write(XML_TEMPLATE % util.to_xml(response))
      elif format == 'html':
        self.response.out.write(microformats2.activities_to_html(activities))
      elif format in ('mf2-json', 'json-mf2'):
        items = [microformats2.activity_to_json(a) for a in activities]
        self.response.out.write(json_dumps({'items': items}, indent=2))
      elif format == 'jsonfeed':
        try:
          jf = jsonfeed.activities_to_jsonfeed(activities, actor=actor, title=title,
                                               feed_url=self.request.url)
        except TypeError as e:
          raise exc.HTTPBadRequest('Unsupported input data: %s' % e)
        self.response.out.write(json_dumps(jf, indent=2))
    except ValueError as e:
      logging.warning('converting to output format failed', stack_info=True)
      self.abort(400, 'Could not convert to %s: %s' % (format, str(e)))

  def get_kwargs(self):
    """Extracts, normalizes and returns the kwargs for get_activities().

    Returns:
      dict
    """
    start_index = self.get_positive_int('startIndex')
    count = self.get_positive_int('count')

    if count == 0:
      count = ITEMS_PER_PAGE_DEFAULT - start_index
    else:
      count = min(count, ITEMS_PER_PAGE_MAX)

    kwargs = {'start_index': start_index, 'count': count}

    search_query = self.request.get('search_query') or self.request.get('q')
    if search_query:
      kwargs['search_query'] = search_query

    cookie = self.request.get('cookie')
    if cookie:
      kwargs['cookie'] = cookie

    return kwargs

  def get_positive_int(self, param):
    try:
      val = self.request.get(param, 0)
      val = int(val)
      assert val >= 0
      return val
    except (ValueError, AssertionError):
      raise exc.HTTPBadRequest('Invalid %s: %s (should be positive int)' %
                               (param, val))
