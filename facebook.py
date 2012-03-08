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

OAUTH_SCOPES = ','.join((
    'email',
    'user_about_me',
    'user_birthday',
    'user_education_history',
    'user_location',
    'user_notes',
    'user_website',
    'user_work_history',
    # see comment in file docstring
    # 'user_address',
    # 'user_mobile_phone',
    ))

API_URL = 'https://graph.facebook.com/'
API_USER_URL = 'https://graph.facebook.com/%s'

# a single batch graph API request that returns all details for the current
# user's friends. the first embedded request gets the current user's list of
# friends; the second gets their details, using JSONPath syntax to depend on the
# first.
#
# copied from
# https://developers.facebook.com/docs/reference/api/batch/#operations
#
# also note that the docs only discuss including the access token inside the
# batch JSON value, but including it in the query parameter of the POST URL
# works fine too.
# See "Specifying different access tokens for different operations" in
# https://developers.facebook.com/docs/reference/api/batch/#operations
API_FRIENDS_BATCH_REQUESTS = json.dumps([
    {'method': 'GET', 'name': 'friends', 'relative_url':
       'me/friends?offset=%(offset)d&limit=%(limit)d'},
    {'method': 'GET', 'relative_url': '?ids={result=friends:$.data.*.id}'},
    ])


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

  def get_activities(self, user_id=None, start_index=0, count=0):
    """Returns a (Python) list of ActivityStreams activities to be JSON-encoded.

    If an OAuth access token is provided in the access_token query parameter, it
    will be passed on to Facebook. This will be necessary for some people and
    activity details, based on their privacy settings.

    Args:
      user_id: integer or string. if provided, only this user will be returned.
      start_index: int >= 0
      count: int >= 0
    """
    if user_id is not None:
      resp = self.urlfetch(API_USER_URL % user_id)
      friends = [json.loads(resp)]
    else:
      if count == 0:
        limit = self.ITEMS_PER_PAGE - start_index
      else:
        limit = min(count, self.ITEMS_PER_PAGE)
      batch = urllib.urlencode({'batch': API_FRIENDS_BATCH_REQUESTS %
                                {'offset': start_index, 'limit': limit}})
      resp = self.urlfetch(API_URL, payload=batch, method='POST')
      # the batch response is a list of responses to the individual batch
      # requests, e.g.
      #
      # [null, {'body': "{'1': {...}, '2': {...}}"}]
      #
      # details: https://developers.facebook.com/docs/reference/api/batch/
      #
      # the first response will be null since the second depends on it
      # and facebook omits responses to dependency requests.
      friends = json.loads(json.loads(resp)[1]['body']).values()

    # return None for total_count since we'd have to fetch and count all
    # friends, which doesn't scale.
    return None, [self.to_activity(user) for user in friends]

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
    author = object.get('author')

    return util.trim_nulls({
      'verb': 'post',
      'published': object.get('published'),
      'id': object.get('id'),
      'url': object.get('url'),
      'actor': author,
      'object': object,
      # TODO
      'audience': self.user_to_actor(post.get('from'))
      })

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
      # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
      lat = place.get('location', {}).get('latitude')
      lon = place.get('location', {}).get('longitude')
      if lat and lon:
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
