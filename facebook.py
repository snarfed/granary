"""Facebook source class. Uses the Graph API.

TODO:
- friends' new friendships, ie "X is now friends with Y." Not currently
available in /me/home. http://stackoverflow.com/questions/4358026
- when someone likes multiple things (og.likes type), only the first is included
in the data.objects array.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import datetime
import itertools
import json
import logging
import re
import urllib
import urllib2
import urlparse

import appengine_config
import source
from webutil import util

OAUTH_SCOPES = ','.join((
    'friends_actions.music',
    'friends_actions.news',
    'friends_actions.video',
    'friends_actions:instapp',
    'friends_activities',
    'friends_games_activity',
    'friends_likes',
    'friends_notes',
    'friends_photos',
    'friends_relationships',
    'read_stream',
    'user_actions.news',
    'user_actions.video',
    'user_actions:instapp',
    'user_activities',
    'user_games_activity',
    'user_likes',
    ))

API_OBJECT_URL = 'https://graph.facebook.com/%s'
API_SELF_POSTS_URL = 'https://graph.facebook.com/%s/posts?offset=%d'
# this an old, out of date version of the actual news feed. sigh. :/
# "Note: /me/home retrieves an outdated view of the News Feed. This is currently
# a known issue and we don't have any near term plans to bring them back up into
# parity."
# https://developers.facebook.com/docs/reference/api/#searching
API_FEED_URL = 'https://graph.facebook.com/%s/home?offset=%d'

# Maps Facebook Graph API post type or Open Graph data type to ActivityStreams
# objectType.
OBJECT_TYPES = {
  'application': 'application',
  'event': 'event',
  'group': 'group',
  'instapp:photo': 'image',
  'link': 'article',
  'location': 'place',
  'music.song': 'audio',
  'page': 'page',
  'photo': 'image',
  'post': 'note',
  'user': 'person',
  'website': 'article',
  }

# Maps Facebook Graph API post type *and ActivityStreams objectType* to
# ActivityStreams verb.
VERBS = {
  'books.reads': 'read',
  'music.listens': 'listen',
  'og.likes': 'like',
  'product': 'give',
  'video.watches': 'play',
}


class Facebook(source.Source):
  """Implements the ActivityStreams API for Facebook.
  """

  DOMAIN = 'facebook.com'
  NAME = 'Facebook'
  FRONT_PAGE_TEMPLATE = 'templates/facebook_index.html'

  def __init__(self, access_token=None):
    """Constructor.

    If an OAuth access token is provided, it will be passed on to Facebook. This
    will be necessary for some people and contact details, based on their
    privacy settings.

    Args:
      access_token: string, optional OAuth access token
    """
    self.access_token = access_token

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'me', ie the current user.
    """
    if user_id is None:
      user_id = 'me'
    return self.user_to_actor(json.loads(self.urlread(API_OBJECT_URL % user_id)))

  def get_activities(self, user_id=None, group_id=None, app_id=None,
                     activity_id=None, start_index=0, count=0, etag=None,
                     fetch_replies=False, fetch_likes=False, fetch_shares=False):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details.

    Replies (ie comments) and likes are always included. They come from the
    'comments' and 'likes' fields in the Graph API's Post object:
    https://developers.facebook.com/docs/reference/api/post/#u_0_3

    Shares are not currently supported, since I haven't yet found a way to get
    them from the API. The sharedposts field / edge seems promising, but I
    haven't been able to get it to work, even with the read_stream OAuth scope.
    http://stackoverflow.com/questions/17373204/information-of-re-shared-status
    """
    if activity_id:
      # Sometimes Facebook requires post ids in USERID_POSTID format; sometimes
      # it doesn't accept that format. I can't tell which is which yet, so try
      # them all.
      ids_to_try = [activity_id]
      if '_' in activity_id:
        user_id_prefix, activity_id = activity_id.split('_', 1)
        ids_to_try.insert(0, activity_id)
      if user_id:
        ids_to_try.append('%s_%s' % (user_id, activity_id))

      for id in ids_to_try:
        try:
          posts = [json.loads(self.urlread(API_OBJECT_URL % id))]
          break
        except urllib2.URLError, e:
          logging.warning("Couldn't fetch object %s: %s", id, e)
      else:
        posts = []

      if posts == [False]:  # FB returns false for "not found"
        posts = []

    else:
      url = API_SELF_POSTS_URL if group_id == source.SELF else API_FEED_URL
      url = url % (user_id if user_id else 'me', start_index)
      if count:
        url = util.add_query_params(url, {'limit': count})
      posts = json.loads(self.urlread(url)).get('data', [])

    return [self.post_to_activity(p) for p in posts]

  def get_comment(self, comment_id, activity_id=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
    """
    url = API_OBJECT_URL % comment_id
    return self.comment_to_object(json.loads(self.urlread(url)))

  def get_share(self, activity_user_id, activity_id, share_id):
    """Not implemented. Returns None.

    I haven't yet found a way to fetch reshares in the Facebook API. :/

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object
    """
    return None

  def urlread(self, url):
    """Wraps urllib2.urlopen() and passes through the access token.
    """
    log_url = url
    if self.access_token:
      log_url = util.add_query_params(url, [('access_token',
                                             self.access_token[:4] + '...')])
      url = util.add_query_params(url, [('access_token', self.access_token)])
    logging.info('Fetching %s', log_url)
    return urllib2.urlopen(url, timeout=999).read()

  def post_url(self, post):
    """Returns a short Facebook URL for a post.

    Args:
      post: Facebook JSON post
    """
    post_id = post.get('id')
    if not post_id:
      return None
    author_id = post.get('from', {}).get('id')
    if author_id:
      return 'http://facebook.com/%s/posts/%s' % (author_id, post_id)
    else:
      return 'http://facebook.com/%s' % post_id

  def post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    id = None
    if 'id' in post:
      # strip USERID_ prefix if it's there
      post['id'] = post['id'].split('_', 1)[-1]
      id = post['id']

    obj = self.post_to_object(post)
    activity = {
      'verb': VERBS.get(post.get('type', obj.get('objectType')), 'post'),
      'published': obj.get('published'),
      'updated': obj.get('updated'),
      'id': self.tag_uri(id) if id else None,
      'url': self.post_url(post),
      'actor': obj.get('author'),
      'object': obj,
      }

    application = post.get('application')
    if application:
      activity['generator'] = {
        'displayName': application.get('name'),
        'id': self.tag_uri(application.get('id')),
        }
    return self.postprocess_activity(activity)

  def post_to_object(self, post, remove_id_prefix=False):
    """Converts a post to an object.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    id = post.get('id')
    if not id:
      return {}

    post_type = post.get('type')
    status_type = post.get('status_type')
    url = self.post_url(post)
    picture = post.get('picture')
    message = post.get('message') or post.get('story') or post.get('name')
    display_name = None

    data = post.get('data', {})
    for field in ('object', 'song'):
      obj = data.get(field)
      if obj:
        id = obj.get('id')
        post_type = obj.get('type')
        url = obj.get('url')
        display_name = obj.get('title')

    object_type = OBJECT_TYPES.get(post_type)
    author = self.user_to_actor(post.get('from'))
    link = post.get('link', '')

    if link.startswith('/gifts/'):
      object_type = 'product'
    if not object_type:
      if picture and not message:
        object_type = 'image'
      else:
        object_type = 'note'

    obj = {
      'id': self.tag_uri(str(id)),
      'objectType': object_type,
      'published': util.maybe_iso8601_to_rfc3339(post.get('created_time')),
      'updated': util.maybe_iso8601_to_rfc3339(post.get('updated_time')),
      'author': author,
      'content': message,
      # FB post ids are of the form USERID_POSTID
      'url': url,
      'image': {'url': picture},
      'displayName': display_name,
      }

    # tags and likes
    tags = itertools.chain(post.get('to', {}).get('data', []),
                           post.get('with_tags', {}).get('data', []),
                           *post.get('message_tags', {}).values())
    obj['tags'] = [{
        'objectType': OBJECT_TYPES.get(t.get('type'), 'person'),
        'id': self.tag_uri(t.get('id')),
        'url': 'http://facebook.com/%s' % t.get('id'),
        'displayName': t.get('name'),
        'startIndex': t.get('offset'),
        'length': t.get('length'),
        } for t in tags]

    obj['tags'] += [{
        'id': self.tag_uri('%s_liked_by_%s' % (id, like.get('id'))),
        'url': url,
        'objectType': 'activity',
        'verb': 'like',
        'object': {'url': url},
        'author': self.user_to_actor(like),
        'content': 'likes this.',
        } for like in post.get('likes', {}).get('data', [])]

    # is there an attachment? prefer to represent it as a picture (ie image
    # object), but if not, fall back to a link.
    att = {
        'url': link if link else url,
        'image': {'url': picture},
        'displayName': post.get('name'),
        'summary': post.get('caption'),
        'content': post.get('description'),
        }

    if (picture and picture.endswith('_s.jpg') and
        (post_type == 'photo' or status_type == 'added_photos')):
      # a picture the user posted. get a larger size.
      att.update({
          'objectType': 'image',
          'image': {'url': picture[:-6] + '_o.jpg'},
          })
      obj['attachments'] = [att]
    elif link and not link.startswith('/gifts/'):
      att['objectType'] = 'article'
      obj['attachments'] = [att]

    # location
    place = post.get('place')
    if place:
      id = place.get('id')
      obj['location'] = {
        'displayName': place.get('name'),
        'id': id,
        'url': 'http://facebook.com/' + id,
        }
      location = place.get('location', None)
      if isinstance(location, dict):
        lat = location.get('latitude')
        lon = location.get('longitude')
        if lat and lon:
          obj['location'].update({
              'latitude': lat,
              'longitude': lon,
              # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
              'position': '%+f%+f/' % (lat, lon),
              })

    # comments go in the replies field, according to the "Responses for
    # Activity Streams" extension spec:
    # http://activitystrea.ms/specs/json/replies/1.0/
    comments = post.get('comments', {}).get('data')
    if comments:
      items = [self.comment_to_object(c) for c in comments]
      obj['replies'] = {
        'items': items,
        'totalItems': len(items),
        }

    return util.trim_nulls(obj)

  COMMENT_ID_RE = re.compile('(\d+_)?(\d+)_(\d+)')

  def comment_to_object(self, comment):
    """Converts a comment to an object.

    Args:
      comment: dict, a decoded JSON comment

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    # the message_tags field is different in comment vs post. in post, it's a
    # dict of lists, in comment it's just a list. so, convert it to post style
    # here before running post_to_object().
    comment = dict(comment)
    comment['message_tags'] = {'1': comment.get('message_tags', [])}

    obj = self.post_to_object(comment)
    if not obj:
      return obj

    obj['objectType'] = 'comment'

    match = self.COMMENT_ID_RE.match(comment.get('id', ''))
    if match:
      post_author, post_id, comment_id = match.groups()
      obj['url'] = 'http://facebook.com/%s?comment_id=%s' % (post_id, comment_id)
      obj['inReplyTo'] = [{'id': self.tag_uri(post_id)}]

    return obj

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

    url = user.get('link')
    if not url:
      url = 'http://facebook.com/' + handle

    # facebook implements this as a 302 redirect
    image_url = 'http://graph.facebook.com/%s/picture?type=large' % handle
    actor = {
      'displayName': user.get('name'),
      'image': {'url': image_url},
      'id': self.tag_uri(handle),
      'updated': util.maybe_iso8601_to_rfc3339(user.get('updated_time')),
      'url': url,
      'username': username,
      'description': user.get('bio'),
      }

    location = user.get('location')
    if location:
      actor['location'] = {'id': location.get('id'),
                           'displayName': location.get('name')}

    return util.trim_nulls(actor)
