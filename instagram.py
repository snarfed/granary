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

# Maps Instagram media type to ActivityStreams objectType.
OBJECT_TYPES = {'image': 'photo', 'video': 'video'}


class Instagram(source.Source):
  """Implements the ActivityStreams API for Instagram."""

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

  def media_to_activity(self, media):
    """Converts a media to an activity.

    Args:
      media: python_instagram.models.Media

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    # Instagram timestamps are evidently all PST.
    # http://stackoverflow.com/questions/10320607
    object = self.media_to_object(post)
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

  def media_to_object(self, media):
    """Converts a media to an object.

    Args:
      media: python_instagram.models.Media

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    # TODO: location, hashtags, person tags, mentions
    id = media.id

    object = {
      'id': self.tag_uri(id),
      'objectType': OBJECT_TYPES.get(media.type, 'photo'),
      'published': util.maybe_timestamp_to_rfc3339(media.created_time),
      'author': self.user_to_actor(media.user),
      'content': media.caption.text if media.caption else None,
      'url': media.link,
      'attachments': [{
          'objectType': 'image',
          'image': {
            'url': image.url,
            'width': image.width,
            'height': image.height,
            }
          } for image in media.images.values()],
      # comments go in the replies field, according to the "Responses for
      # Activity Streams" extension spec:
      # http://activitystrea.ms/specs/json/replies/1.0/
      'replies': {
        'items': [self.comment_to_object(c, id, media.link)
                  for c in media.comments],
        'totalItems': media.comments_count,
        }
      }

    for version in ('standard_resolution', 'low_resolution', 'thumbnail'):
      image = media.images.get(version)
      if image:
        object['image'] = {'url': image.url}
        break

    # # tags
    # tags = itertools.chain(media.get('to', {}).get('data', []),
    #                        media.get('with_tags', {}).get('data', []),
    #                        *media.get('message_tags', {}).values())
    # object['tags'] = [{
    #       'objectType': OBJECT_TYPES.get(t.type, 'person'),
    #       'id': self.tag_uri(t.id),
    #       'url': 'http://instagram.com/%s' % t.id,
    #       'displayName': t.name,
    #       'startIndex': t.offset,
    #       'length': t.length,
    #       } for t in tags]

    # # location
    # place = media.place
    # if place:
    #   id = place.id
    #   object['location'] = {
    #     'displayName': place.name,
    #     'id': id,
    #     'url': 'http://instagram.com/' + id,
    #     }
    #   location = place.get('location', None)
    #   if isinstance(location, dict):
    #     lat = location.latitude
    #     lon = location.longitude
    #     if lat and lon:
    #       object['location'].update({
    #           'latitude': lat,
    #           'longitude': lon,
    #           # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
    #           'position': '%+f%+f/' % (lat, lon),
    #           })

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
