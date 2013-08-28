#!/usr/bin/python
"""Instagram source class.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import cgi
import datetime
import itertools
import json
import re
import urllib
import urlparse

import appengine_config
from python_instagram.client import InstagramAPI
import source
from webutil import util

# maps instagram graph api object types to ActivityStreams objectType.
OBJECT_TYPES = {
  'application': 'application',
  'event': 'event',
  'group': 'group',
  'link': 'article',
  'location': 'place',
  'page': 'page',
  'photo': 'photo',
  'post': 'note',
  'user': 'person',
  }


class Instagram(source.Source):
  """Implements the ActivityStreams API for Instagram.
  """

  DOMAIN = 'instagram.com'
  FRONT_PAGE_TEMPLATE = 'templates/instagram_index.html'
  AUTH_URL = '&'.join((
      'https://api.instagram.com/oauth/authorize?',
      'client_id=%s' % appengine_config.INSTAGRAM_CLIENT_ID,
      # firefox and chrome preserve the URL fragment on redirects (e.g. from
      # http to https), but IE (6 and 8) don't, so i can't just hard-code http
      # as the scheme here, i need to actually specify the right scheme.
      'redirect_uri=%s://%s/' % (appengine_config.SCHEME, appengine_config.HOST),
      'response_type=token',
      ))

  def __init__(self, *args):
    super(Instagram, self).__init__(*args)
    self.api = InstagramAPI(
      client_id=appengine_config.INSTAGRAM_CLIENT_ID,
      client_secret=appengine_config.INSTAGRAM_CLIENT_SECRET,
      access_token=self.handler.request.get('access_token'))

  # @staticmethod
  # def media_url(id):
  #   return 'http://instagram.com/p/%s/' % id

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'me', ie the current user.
    """
    if user_id is None:
      user_id = 'self'
    return self.user_to_actor(self.api.user(user_id))

  def get_activities(self, user_id=None, group_id=None, app_id=None,
                     activity_id=None, start_index=0, count=0):
    """Returns a (Python) list of ActivityStreams activities to be JSON-encoded.

    See method docstring in source.py for details.

    OAuth credentials must be provided in the access_token query parameter.
    """
    if user_id is None:
      user_id = 'me'

    if activity_id:
      posts = [json.loads(self.urlfetch(API_OBJECT_URL % activity_id))]
      if posts == [False]:  # FB returns false for "not found"
        posts = []
      total_count = len(posts)
    else:
      url = API_SELF_POSTS_URL if group_id == source.SELF else API_FEED_URL
      url = url % (user_id, start_index, count)
      posts = json.loads(self.urlfetch(url)).get('data', [])
      total_count = None

    return total_count, [self.post_to_activity(p) for p in posts]

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

    return util.urlfetch(url, **kwargs)

  def post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    # Instagram timestamps are evidently all PST.
    # http://stackoverflow.com/questions/10320607
    object = self.post_to_object(post)
    activity = {
      'verb': 'post',
      'published': object.published,
      'updated': object.updated,
      'id': object.id,
      'url': object.url,
      'actor': object.author,
      'object': object,
      }

    application = post.application
    if application:
      activity['generator'] = {
        'displayName': application.name,
        'id': self.tag_uri(application.id),
        }

    self.postprocess_activity(activity)
    return util.trim_nulls(activity)

  def post_to_object(self, post):
    """Converts a post to an object.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    object = {}

    id = post.id
    if not id:
      return {}

    post_type = post.type
    status_type = post.status_type
    url = 'http://instagram.com/' + id.replace('_', '/posts/')
    picture = post.picture

    object = {
      'id': self.tag_uri(str(id)),
      'objectType': OBJECT_TYPES.get(post_type, 'note'),
      'published': util.maybe_iso8601_to_rfc3339(post.created_time),
      'updated': util.maybe_iso8601_to_rfc3339(post.updated_time),
      'author': self.user_to_actor(post.xyzxfrom),
      'content': post.message,
      # FB post ids are of the form USERID_POSTID
      'url': url,
      'image': {'url': picture},
      }

    # tags
    tags = itertools.chain(post.get('to', {}).get('data', []),
                           post.get('with_tags', {}).get('data', []),
                           *post.get('message_tags', {}).values())
    object['tags'] = [{
          'objectType': OBJECT_TYPES.get(t.type, 'person'),
          'id': self.tag_uri(t.id),
          'url': 'http://instagram.com/%s' % t.id,
          'displayName': t.name,
          'startIndex': t.offset,
          'length': t.length,
          } for t in tags]

    # is there an attachment? prefer to represent it as a picture (ie image
    # object), but if not, fall back to a link.
    link = post.link
    att = {
        'url': link if link else url,
        'image': {'url': picture},
        'displayName': post.name,
        'summary': post.caption,
        'content': post.description,
        }

    if (picture and picture.endswith('_s.jpg') and
        (post_type == 'photo' or status_type == 'added_photos')):
      # a picture the user posted. get a larger size.
      att.update({
          'objectType': 'image',
          'image': {'url': picture[:-6] + '_o.jpg'},
          })
      object['attachments'] = [att]
    elif link:
      att['objectType'] = 'article'
      object['attachments'] = [att]

    # location
    place = post.place
    if place:
      id = place.id
      object['location'] = {
        'displayName': place.name,
        'id': id,
        'url': 'http://instagram.com/' + id,
        }
      location = place.get('location', None)
      if isinstance(location, dict):
        lat = location.latitude
        lon = location.longitude
        if lat and lon:
          object['location'].update({
              'latitude': lat,
              'longitude': lon,
              # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
              'position': '%+f%+f/' % (lat, lon),
              })

    # comments go in the replies field, according to the "Responses for
    # Activity Streams" extension spec:
    # http://activitystrea.ms/specs/json/replies/1.0/
    comments = post.get('comments', {}).data
    if comments:
      items = [self.comment_to_object(c) for c in comments]
      object['replies'] = {
        'items': items,
        'totalItems': len(items),
        }

    return util.trim_nulls(object)

  def comment_to_object(self, comment, media_id, media_url):
    """Converts a comment to an object.

    Args:
      comment: python_instagram.models.Comment
      media_id: string
      media_url: string

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    return {
      'objectType': 'comment',
      'id': self.tag_uri(comment.id),
      'inReplyTo': {'id': self.tag_uri(media_id)},
      'url': media_url,
      # TODO: add PST time zone
      'published': util.maybe_timestamp_to_rfc3339(comment.created_at),
      'content': comment.text,
      'author': self.user_to_actor(comment.user),
      }

  def user_to_actor(self, user):
    """Converts a user to an actor.

    Args:
      user: python_instagram.models.Comment

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    if not user:
      return {}

    id = getattr(user, 'id', None)
    username = getattr(user, 'username', None)
    if not id or not username:
      return {'id': self.tag_uri(id or username),
              'username': username}

    url = getattr(user, 'website', None)
    if not url:
      url = 'http://instagram.com/' + username

    actor = {
      'displayName': user.full_name,
      'image': {'url': user.profile_picture},
      'id': self.tag_uri(username),
      'url': url,
      'username': username,
      'description': getattr(user, 'bio', None)
      }

    return util.trim_nulls(actor)
