#!/usr/bin/python
"""Facebook source class.

had open streams api which supported activitystreams, but looks like it died in favor of graph api:
https://developers.facebook.com/blog/post/225/
https://developers.facebook.com/blog/post/288/
http://wiki.activitystrea.ms/w/page/1359259/Facebook%20Activity%20Streams

old rest api can get stream in xml format but it's not activitystreams format:
https://developers.facebook.com/docs/reference/rest/stream.get/
e.g. https://api.facebook.com/method/stream.get?access_token=AAADpooqA1u0BALAzULCrcQUhrZA52gz98S7uZCyzJMFyHdyF8WhBZBC9uP0US6n9iYHsMdX11zS2J7DxtW85GvYoLKlvCEZD&format=atom

activity feed plugin is similar but again not activitystreams format:
https://developers.facebook.com/docs/reference/plugins/activity/
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import cgi
import collections
import datetime
try:
  import json
except ImportError:
  import simplejson as json
import re
import urllib
import urlparse

import appengine_config
import source
import util

OAUTH_SCOPES = 'read_stream'
API_URL = 'https://graph.facebook.com/'

# this an old, out of date version of the actual news feed. sigh. :/
# "Note: /me/home retrieves an outdated view of the News Feed. This is currently
# a known issue and we don't have any near term plans to bring them back up into
# parity."
# https://developers.facebook.com/docs/reference/api/#searching
API_FEED_URL = 'https://graph.facebook.com/%s/home'


class Facebook(source.Source):
  """Implements the ActivityStreams API for Facebook.
  """

  DOMAIN = 'facebook.com'
  ITEMS_PER_PAGE = 100
  FRONT_PAGE_TEMPLATE = 'templates/facebook_index.html'
  AUTH_URL = '&'.join((
      ('http://localhost:8000/dialog/oauth/?'
       if appengine_config.MOCKFACEBOOK else
       'https://www.facebook.com/dialog/oauth/?'),
      'scope=%s' % OAUTH_SCOPES,
      'client_id=%s' % appengine_config.FACEBOOK_APP_ID,
      # firefox and chrome preserve the URL fragment on redirects (e.g. from
      # http to https), but IE (6 and 8) don't, so i can't just hard-code http
      # as the scheme here, i need to actually specify the right scheme.
      'redirect_uri=%s://%s/' % (appengine_config.SCHEME, appengine_config.HOST),
      'response_type=token',
      ))

  def get_activities(self, user=None, group=None, app=None, activity=None,
                     start_index=0, count=0):
    """Returns a (Python) list of ActivityStreams activities to be JSON-encoded.

    If an OAuth access token is provided in the access_token query parameter, it
    will be passed on to Facebook. This will be necessary for some people and
    activity details, based on their privacy settings.

    Args:
      user: user id
      group: group id
      app: app id
      activity: activity id
      start_index: int >= 0
      count: int >= 0
    """
    if user is None:
      user = 'me'

    activities = json.loads(self.urlfetch(API_FEED_URL % user)).get('data', [])
    # return None for total_count since we'd have to fetch and count all
    # friends, which doesn't scale.
    return None, [self.post_to_activity(a) for a in activities]

  def get_current_user(self):
    """Returns 'me', which Facebook interprets as the current user.
    """
    return 'me'

  def urlfetch(self, url, **kwargs):
    """Wraps Source.urlfetch() and passes through the access_token query param.
    """
    access_token = self.handler.request.get('access_token')
    if access_token:
      parsed = list(urlparse.urlparse(url))
      # query params are in index 4
      # TODO: when this is on python 2.7, switch to urlparse.parse_qsl
      params = cgi.parse_qsl(parsed[4]) + [('access_token', access_token)]
      parsed[4] = urllib.urlencode(params)
      url = urlparse.urlunparse(parsed)

    return super(Facebook, self).urlfetch(url, **kwargs)

  def post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    object = self.post_to_object(post)
    activity = {
      'verb': 'post',
      'published': object.get('published'),
      'updated': object.get('updated'),
      'id': object.get('id'),
      'url': object.get('url'),
      'actor': object.get('author'),
      'object': object,
      }

    application = post.get('application')
    if application:
      activity['generator'] = {
        'displayName': application.get('name'),
        'id': self.tag_uri(application.get('id')),
        }

    return util.trim_nulls(activity)

  def post_to_object(self, post):
    """Converts a post to an object.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    object = {}

    id = post.get('id')
    if not id:
      return {}

    # TODO: fb posts also include my comments on other things. instead just
    # search for status, photo, link, ...?
    # assert post.get('type') in ('status', 'link', 'photo')

    object = {
      'id': self.tag_uri(str(id)),
      'objectType': 'note',
      'published': post.get('created_time'),
      'updated': post.get('updated_time'),
      'content': post.get('message'),
      'author': self.user_to_actor(post.get('from')),
      # FB post ids are of the form USERID_POSTID
      'url': 'http://facebook.com/' + id.replace('_', '/posts/'),
      'image': {'url': post.get('picture')},
      }

    place = post.get('place')
    if place:
      object['location'] = {
        'displayName': place.get('name'),
        'id': place.get('id'),
        }
      location = place.get('location', {})
      lat = location.get('latitude')
      lon = location.get('longitude')
      if lat and lon:
        # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
        object['location']['position'] = '%+f%+f/' % (lat, lon)

    return util.trim_nulls(object)

  def user_to_actor(self, user):
    """Converts a user to an actor.

    Args:
      user: dict, a decoded JSON Facebook user

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    if not user:
      return {}

    id = user.get('id')
    username = user.get('username')
    handle = username or id
    if not handle:
      return {}

    # facebook implements this as a 302 redirect
    image_url = 'http://graph.facebook.com/%s/picture?type=large' % handle
    actor = {
      'displayName': user.get('name'),
      'image': {'url': image_url},
      'id': self.tag_uri(handle),
      'updated': user.get('updated_time'),
      'url': user.get('link'),
      'username': username,
      'description': user.get('bio'),
      }

    location = user.get('location')
    if location:
      actor['location'] = {'id': location.get('id'),
                           'displayName': location.get('name')}

    return util.trim_nulls(actor)
