#!/usr/bin/python
"""Source base class.

Based on the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service 
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import datetime
try:
  import json
except ImportError:
  import simplejson as json
import logging
from webob import exc

from google.appengine.api import urlfetch

ME = '@me'
SELF = '@self'
ALL = '@all'
FRIENDS = '@friends'
APP = '@app'

class Source(object):
  """Abstract base class for a source (e.g. Facebook, Twitter).

  Concrete subclasses must override the class constants below and implement
  get_activities().

  OAuth credentials may be extracted from the current request's query parameters
  e.g. access_token_key and access_token_secret for Twitter (OAuth 1.0a) and
  access_token for Facebook (OAuth 2.0).

  Attributes:
    handler: the current RequestHandler

  Class constants:
    DOMAIN: string, the source's domain
    FRONT_PAGE_TEMPLATE: string, the front page child template filename
    AUTH_URL = string, the url for the "Authenticate" front page link
  """

  def __init__(self, handler):
    self.handler = handler

  def get_activities(self, user_id=None, group_id=None, app_id=None,
                     activity_id=None, start_index=0, count=0):
    """Return a total count and list of ActivityStreams activities.

    If user_id is provided, only that user's activity(s) are included.
    start_index and count determine paging, as described in the spec:
    http://activitystrea.ms/draft-spec.html#anchor14

    app id is just object id
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#appId

    group id is string id of group or @self, @friends, @all
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#Group-ID

    Args:
      user_id: string object id, defaults to the currently authenticated user
      group_id: string object id, defaults to the current user's friends
      app_id: string object id
      activity_id: string object id
      start_index: int >= 0
      count: int >= 0

    Returns:
      (total_results, activities) tuple
      total_results: int or None (e.g. if it can't be calculated efficiently)
      activities: list of activity dicts to be JSON-encoded
    """
    raise NotImplementedError()

  def urlfetch(self, url, **kwargs):
    """Wraps urlfetch. Passes error responses through to the client.

    ...by raising HTTPException.

    Args:
      url: str
      kwargs: passed through to urlfetch.fetch()

    Returns:
      the HTTP response body
    """
    logging.debug('Fetching %s with kwargs %s', url, kwargs)
    resp = urlfetch.fetch(url, deadline=999, **kwargs)

    if resp.status_code == 200:
      return resp.content
    else:
      logging.warning('GET %s returned %d:\n%s',
                      url, resp.status_code, resp.content)
      self.handler.response.headers.update(resp.headers)
      self.handler.response.out.write(resp.content)
      raise exc.status_map.get(resp.status_code)(resp.content)

  def tag_uri(self, name):
    """Returns a tag URI string for this source and the given string name.

    Example return value: 'tag:twitter.com,2012:snarfed_org/172417043893731329'

    Background on tag URIs: http://taguri.org/
    """
    return 'tag:%s,%d:%s' % (self.DOMAIN, datetime.datetime.now().year, name)
