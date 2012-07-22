#!/usr/bin/python
"""Twitter source class.

Uses the REST API: https://dev.twitter.com/docs/api

TODO: collections for twitter accounts; use as activity target?
TODO: reshare activities for retweets
TODO: in-reply-to for @ mentions?

snarfed_org user id: 139199211

http://groups.google.com/group/activity-streams/browse_thread/thread/5f88499fdd4a7911/1fa8b4eb39f28cd7

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
from webutil import util

API_TIMELINE_URL = \
  'https://api.twitter.com/1/statuses/home_timeline.json?include_entities=true&count=%d'
API_SELF_URL = \
  'https://api.twitter.com/1/statuses/user_timeline.json?include_entities=true&count=%d'
API_STATUS_URL = \
  'https://api.twitter.com/1/statuses/show.json?id=%s&include_entities=true'

class Twitter(source.Source):
  """Implements the ActivityStreams API for Twitter.
  """

  DOMAIN = 'twitter.com'
  FRONT_PAGE_TEMPLATE = 'templates/twitter_index.html'
  AUTH_URL = '/start_auth'

  def get_current_user(self):
    """Returns the current user as a JSON ActivitStreams actor dict."""
    return self.user_to_actor(json.loads(self.urlfetch(API_SELF_URL)))

  def get_activities(self, user_id=None, group_id=None, app_id=None,
                     activity_id=None, start_index=0, count=0):
    """Returns a (Python) list of ActivityStreams activities to be JSON-encoded.

    See method docstring in source.py for details.

    OAuth credentials must be provided in access_token_key and
    access_token_secret query parameters.
    """
    if activity_id:
      tweets = [json.loads(self.urlfetch(API_STATUS_URL % activity_id))]
      total_count = len(tweets)
    else:
      url = API_SELF_URL if group_id == source.SELF else API_TIMELINE_URL
      twitter_count = count + start_index
      tweets = json.loads(self.urlfetch(url % twitter_count))
      tweets = tweets[start_index:]
      total_count = None

    return total_count, [self.tweet_to_activity(t) for t in tweets]

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

    return util.urlfetch(url, **kwargs)

  def tweet_to_activity(self, tweet):
    """Converts a tweet to an activity.

    Args:
      tweet: dict, a decoded JSON tweet

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    object = self.tweet_to_object(tweet)
    activity = {
      'verb': 'post',
      'published': object.get('published'),
      'id': object.get('id'),
      'url': object.get('url'),
      'actor': object.get('author'),
      'object': object,
      }

    # yes, the source field has an embedded HTML link. bleh.
    # https://dev.twitter.com/docs/api/1/get/statuses/show/
    parsed = re.search('<a href="([^"]+)".*>(.+)</a>', tweet.get('source', ''))
    if parsed:
      url, name = parsed.groups()
      activity['generator'] = {'displayName': name, 'url': url}

    return util.trim_nulls(activity)

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
        object['id'] = util.tag_uri(self.DOMAIN, id)
        object['url'] = 'http://twitter.com/%s/status/%d' % (username, id)

    # currently the media list will only have photos. if that changes, though,
    # we'll need to make this conditional on media.type.
    # https://dev.twitter.com/docs/tweet-entities
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

    return util.trim_nulls(object)
      

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

    return util.trim_nulls({
      'displayName': user.get('name'),
      'image': {'url': user.get('profile_image_url')},
      'id': util.tag_uri(self.DOMAIN, username) if username else None,
      'published': self.rfc2822_to_iso8601(user.get('created_at')),
      'url': 'http://twitter.com/%s' % username,
      'location': {'displayName': user.get('location')},
      'username': username,
      'description': user.get('description'),
      })

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

