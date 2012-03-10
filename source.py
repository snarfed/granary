#!/usr/bin/python
"""Source base class.

STATE:
finish get_activities(), do _test, then do activitystreams.py

decided to use this REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service 
only one method, get (activities), for now
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


class Source(object):
  """Abstract base class for a source (e.g. Facebook, Twitter).

  Concrete subclasses must override DOMAIN and implement get_activities() and
  get_current_user().

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

  def get_activities(self, user=ME, group=SELF, app=None, activity=None):
    """Return a list and total count of ActivityStreams activities.

    If user_id is provided, only that user's activity(s) are included.
    start_index and count determine paging, as described in the spec:
    http://activitystrea.ms/draft-spec.html#anchor14

    Args:
      user: user id
      group: group id
      app: app id
      activity: activity id

    Returns:
      (total_results, activities) tuple
      total_results: int or None (e.g. if it can't be calculated efficiently)
      activities: list of activity dicts to be JSON-encoded
    """
    raise NotImplementedError()

  def get_current_user(self):
    """Returns the current (authed) user, either integer id or string username.
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
