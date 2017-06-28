"""ActivityStreams API handler classes.

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

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import json
import logging
import urllib

from google.appengine.api import memcache
from google.appengine.ext import ndb
from oauth_dropins.webutil import handlers
from oauth_dropins.webutil import util
import webapp2
from webob import exc

from granary import (
  appengine_config,
  atom,
  facebook,
  flickr,
  googleplus,
  instagram,
  jsonfeed,
  microformats2,
  source,
  twitter,
)

XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>%s</response>
"""
ITEMS_PER_PAGE = 100

# default values for each part of the API request path except the site, e.g.
# /twitter/@me/@self/@all/...
PATH_DEFAULTS = ((source.ME,), (source.ALL, source.FRIENDS), (source.APP,), ())
MAX_PATH_LEN = len(PATH_DEFAULTS) + 1


class Handler(handlers.ModernHandler):
  """Base class for ActivityStreams API handlers.

  Response data is cached. Cache key is 'R [PATH]', value is dict with
  'activities' and 'actor' keys. Cache duration defaults to 5m but silos can
  override, eg Instagram sets to 60m. Background:
  https://github.com/snarfed/bridgy/issues/665

  You can skip the cache by including a cache=false query param.

  Attributes:
    source: Source subclass
  """
  handle_exception = handlers.handle_exception

  def get(self):
    """Handles an API GET.

    Request path is of the form /site/user_id/group_id/app_id/activity_id ,
    where each element except site is an optional string object id.
    """
    # parse path
    args = urllib.unquote(self.request.path).strip('/').split('/')
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
      src = facebook.Facebook(
        access_token=util.get_required_param(self, 'access_token'))
    elif site == 'flickr':
      src = flickr.Flickr(
        access_token_key=util.get_required_param(self, 'access_token_key'),
        access_token_secret=util.get_required_param(self, 'access_token_secret'))
    elif site == 'instagram':
      src = instagram.Instagram(scrape=True)
    elif site == 'google+':
      auth_entity = util.get_required_param(self, 'auth_entity')
      src = googleplus.GooglePlus(auth_entity=ndb.Key(urlsafe=auth_entity).get())
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

    # check if request is cached
    cache = self.request.get('cache', '').lower() != 'false'
    if cache:
      cache_key = 'R %s' % self.request.path
      cached = memcache.get(cache_key)
      if cached:
        logging.info('Serving cached response %r', cache_key)
        self.write_response(cached['response'], actor=cached['actor'],
                            url=src.BASE_URL)
        return

    # handle default path elements
    args = [None if a in defaults else a
            for a, defaults in zip(args, PATH_DEFAULTS)]
    user_id = args[0] if args else None

    # get activities
    try:
      response = src.get_activities_response(*args, **self.get_kwargs(src))
    except (NotImplementedError, ValueError) as e:
      self.abort(400, str(e))
      # other exceptions are handled by webutil.handlers.handle_exception(),
      # which uses interpret_http_exception(), etc.

    # fetch actor if necessary
    actor = response.get('actor')
    if not actor and self.request.get('format') == 'atom':
      # atom needs actor
      args = [None if a in defaults else a  # handle default path elements
              for a, defaults in zip(args, PATH_DEFAULTS)]
      user_id = args[0] if args else None
      actor = src.get_actor(user_id) if src else {}

    self.write_response(response, actor=actor, url=src.BASE_URL)

    # cache response
    if cache:
      logging.info('Caching response in %r', cache_key)
      memcache.set(cache_key, {'response': response, 'actor': actor},
                   src.RESPONSE_CACHE_TIME)

  def write_response(self, response, actor=None, url=None, title=None):
    """Converts ActivityStreams activities and writes them out.

    Args:
      response: response dict with values based on OpenSocial ActivityStreams
        REST API, as returned by Source.get_activities_response()
      actor: optional ActivityStreams actor dict for current user. Only used
        for Atom and JSON Feed output.
      url: the input URL
      title: string, Used in Atom and JSON Feed output
    """
    expected_formats = ('activitystreams', 'json', 'atom', 'xml', 'html',
                        'json-mf2', 'jsonfeed')
    format = self.request.get('format') or self.request.get('output') or 'json'
    if format not in expected_formats:
      raise exc.HTTPBadRequest('Invalid format: %s, expected one of %r' %
                               (format, expected_formats))

    activities = response['items']

    self.response.headers.update({
      'Access-Control-Allow-Origin': '*',
      'Strict-Transport-Security':
          'max-age=16070400; includeSubDomains; preload',  # 6 months
    })

    if format in ('json', 'activitystreams'):
      # list of official MIME types:
      # https://www.iana.org/assignments/media-types/media-types.xhtml
      self.response.headers['Content-Type'] = 'application/json'
      self.response.out.write(json.dumps(response, indent=2))
    elif format == 'atom':
      self.response.headers['Content-Type'] = 'application/atom+xml'
      hub = self.request.get('hub')
      reader = self.request.get('reader', 'true').lower()
      if reader not in ('true', 'false'):
        self.abort(400, 'reader param must be either true or false')
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
    elif format == 'xml':
      self.response.headers['Content-Type'] = 'application/xml'
      self.response.out.write(XML_TEMPLATE % util.to_xml(response))
    elif format == 'html':
      self.response.headers['Content-Type'] = 'text/html'
      self.response.out.write(microformats2.activities_to_html(activities))
    elif format == 'json-mf2':
      self.response.headers['Content-Type'] = 'application/json'
      items = [microformats2.object_to_json(a) for a in activities]
      self.response.out.write(json.dumps({'items': items}, indent=2))
    elif format == 'jsonfeed':
      self.response.headers['Content-Type'] = 'application/json'
      jf = jsonfeed.activities_to_jsonfeed(activities, actor=actor, title=title)
      self.response.out.write(json.dumps(jf, indent=2))

    if 'plaintext' in self.request.params:
      # override response content type
      self.response.headers['Content-Type'] = 'text/plain'

  def get_kwargs(self, source):
    """Extracts, normalizes and returns the startIndex, count, and search
    query params.

    Args:
      source: Source instance

    Returns:
      dict with 'start_index' and 'count' keys mapped to integers
    """
    start_index = self.get_positive_int('startIndex')
    count = self.get_positive_int('count')

    if count == 0:
      count = ITEMS_PER_PAGE - start_index
    else:
      count = min(count, ITEMS_PER_PAGE)

    kwargs = {'start_index': start_index, 'count': count}

    search_query = self.request.get('search_query') or self.request.get('q')
    if search_query:
      kwargs['search_query'] = search_query

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


application = webapp2.WSGIApplication([('.*', Handler)],
                                      debug=appengine_config.DEBUG)
