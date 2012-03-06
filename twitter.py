#!/usr/bin/python
"""Twitter source class.

Uses the REST API: https://dev.twitter.com/docs/api

TODO: collections for twitter accounts; use as activity target?
TODO: reshare activities for retweets
TODO: in-reply-to for @ mentions?

snarfed_org user id: 139199211

http://groups.google.com/group/activity-streams/browse_thread/thread/5f88499fdd4a7911/1fa8b4eb39f28cd7

this looks promising but is actually wrong in lots of ways. :(
https://gist.github.com/645256

example schema mapping:
http://wiki.activitystrea.ms/w/page/1359317/Twitter%20Examples

Python code to pretty-print JSON responses from Twitter REST API:

pprint(json.loads(urllib.urlopen(
  'https://api.twitter.com/1/statuses/show.json?id=172417043893731329&include_entities=1').read()))
pprint(json.loads(urllib.urlopen(
  'https://api.twitter.com/1/users/lookup.json?screen_name=snarfed_org').read()))
pprint(json.loads(urllib.urlopen(
  'https://api.twitter.com/1/followers/ids.json?screen_name=snarfed_org').read()))
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import cgi
import collections
import datetime
try:
  import json
except ImportError:
  import simplejson as json
import logging
import re
import urlparse

import appengine_config
import source
import tweepy

API_FRIENDS_URL = 'https://api.twitter.com/1/friends/ids.json?user_id=%d'
API_USERS_URL = 'https://api.twitter.com/1/users/lookup.json?user_id=%s'
API_ACCOUNT_URL = 'https://api.twitter.com/1/account/verify_credentials.json'


class Twitter(source.Source):
  """Implements the ActivityStreams API for Twitter.
  """

  DOMAIN = 'twitter.com'
  ITEMS_PER_PAGE = 100
  FRONT_PAGE_TEMPLATE = 'templates/twitter_index.html'
  AUTH_URL = '/start_auth'

  def get_activities(self, user_id=None, start_index=0, count=0):
    """Returns a (Python) list of ActivityStreams activities to be JSON-encoded.

    OAuth credentials must be provided in access_token_key and
    access_token_secret query parameters if the current user is protected, or to
    receive any protected friends in the returned activities.

    Args:
      user_id: integer or string. if provided, only this user will be returned.
      start_index: int >= 0
      count: int >= 0
    """
    if user_id is not None:
      ids = [user_id]
      total_count = 1
    else:
      cur_user = json.loads(self.urlfetch(API_ACCOUNT_URL))
      total_count = cur_user.get('friends_count')
      resp = self.urlfetch(API_FRIENDS_URL % cur_user['id'])
      # TODO: unify with Facebook.get_activities()
      if count == 0:
        end = self.ITEMS_PER_PAGE - start_index
      else:
        end = start_index + min(count, self.ITEMS_PER_PAGE)
      ids = json.loads(resp)['ids'][start_index:end]

    if not ids:
      return 0, []

    ids_str = ','.join(str(id) for id in ids)
    resp = json.loads(self.urlfetch(API_USERS_URL % ids_str))

    if user_id is not None and len(resp) == 0:
      # the specified user id doesn't exist
      total_count = 0

    return total_count, [self.to_activity(user) for user in resp]

  def get_current_user(self):
    """Returns the currently authenticated user's id.
    """
    resp = self.urlfetch(API_ACCOUNT_URL)
    return json.loads(resp)['id']

  def urlfetch(self, url, **kwargs):
    """Wraps Source.urlfetch(), signing with OAuth if there's an access token.

    TODO: unit test this
    """
    request = self.handler.request
    access_token_key = request.get('access_token_key')
    access_token_secret = request.get('access_token_secret')
    if access_token_key and access_token_secret:
      logging.info('Found access token key %s and secret %s',
                   access_token_key, access_token_secret)
      auth = tweepy.OAuthHandler(appengine_config.TWITTER_APP_KEY,
                                 appengine_config.TWITTER_APP_SECRET)
      auth.set_access_token(access_token_key, access_token_secret)
      method = kwargs.get('method', 'GET')
      headers = kwargs.setdefault('headers', {})

      parsed = urlparse.urlparse(url)
      url_without_query = urlparse.urlunparse(list(parsed[0:4]) + ['', ''])
      auth.apply_auth(url_without_query, method, headers,
                      # TODO: switch to urlparse.parse_qsl after python27 runtime
                      dict(cgi.parse_qsl(parsed.query)))
      logging.info('Populated Authorization header from access token: %s',
                   headers.get('Authorization'))

    return super(Twitter, self).urlfetch(url, **kwargs)

  def tweet_to_activity(self, tweet):
    """Converts a tweet to an activity.

    Args:
      tweet: dict, a decoded JSON tweet

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    object = self.tweet_to_object(tweet)
    author = object.get('author')

    return {
      'verb': 'post',
      'published': object.get('published'),
      'id': object.get('id'),
      'url': object.get('url'),
      'actor': author,
      'object': object,
      }

  def tweet_to_object(self, tweet):
    """Converts a tweet to an object.

    Args:
      tweet: dict, a decoded JSON tweet

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    object = {}

    id = tweet.get('id')
    if not id:
      return {}

    object = {
      'objectType': 'note',
      'published': self.rfc2822_to_iso8601(tweet.get('created_at')),
      'content': tweet.get('text'),
      }

    user = tweet.get('user')
    if user:
      object['author'] = self.user_to_actor(user)
      username = object['author'].get('username')
      if username:
        object['id'] = self.tag_uri('%s/%d' % (username, id))
        object['url'] = 'http://twitter.com/%s/status/%d' % (username, id)

    media_url = tweet.get('entities', {}).get('media', [{}])[0].get('media_url')
    if media_url:
      object['image'] = {'url': media_url}

    place = tweet.get('place')
    if place:
      object['location'] = {
        'displayName': place.get('full_name'),
        'id': place.get('id'),
        'url': place.get('url'),
        }

    return object
      

  def user_to_actor(self, user):
    """Converts a tweet to an activity.

    Args:
      user: dict, a decoded JSON Twitter user

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    username = user.get('screen_name')
    if not username:
      return {}

    return {
      'displayName': user.get('name'),
      'image': {'url': user.get('profile_image_url')},
      'id': self.tag_uri(username) if username else None,
      'published': self.rfc2822_to_iso8601(user.get('created_at')),
      'url': 'http://twitter.com/%s' % username,
      'location': {'displayName': user.get('location')},
      'username': username,
      'description': user.get('description'),
      }

  @staticmethod
  def rfc2822_to_iso8601(time_str):
    """Converts a timestamp string from RFC 2822 format to ISO 8601.

    Example RFC 2822 timestamp string generated by Twitter:
      'Wed May 23 06:01:13 +0000 2007'

    Resulting ISO 8610 timestamp string:
      '2007-05-23T06:01:13'
    """
    if not time_str:
      return None

    without_timezone = re.sub(' [+-][0-9]{4} ', ' ', time_str)
    dt = datetime.datetime.strptime(without_timezone, '%a %b %d %H:%M:%S %Y')
    return dt.isoformat()

