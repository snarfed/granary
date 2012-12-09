#!/usr/bin/python
"""Facebook source class. Uses the Graph API.
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
from webutil import util

OAUTH_SCOPES = 'read_stream'

API_OBJECT_URL = 'https://graph.facebook.com/%s'
API_SELF_POSTS_URL = 'https://graph.facebook.com/%s/posts?offset=%d&limit=%d'
# this an old, out of date version of the actual news feed. sigh. :/
# "Note: /me/home retrieves an outdated view of the News Feed. This is currently
# a known issue and we don't have any near term plans to bring them back up into
# parity."
# https://developers.facebook.com/docs/reference/api/#searching
API_FEED_URL = 'https://graph.facebook.com/%s/home?offset=%d&limit=%d'


class Facebook(source.Source):
  """Implements the ActivityStreams API for Facebook.
  """

  DOMAIN = 'facebook.com'
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

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'me', ie the current user.
    """
    if user_id is None:
      user_id = 'me'
    return self.user_to_actor(json.loads(self.urlfetch(API_OBJECT_URL % user_id)))

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
        'id': util.tag_uri(self.DOMAIN, application.get('id')),
        }

    return util.trim_nulls(activity)

  # maps facebook graph api object types to ActivityStreams objectType.
  OBJECT_TYPES = {
    'application': 'application',
    'checkin': 'note',
    'event': 'event',
    'group': 'group',
    'link': 'note',
    'location': 'place',
    'page': 'page',
    'photo': 'photo',
    'post': 'note',
    'status': 'note',
    'user': 'person',
    }

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

    object = {
      'id': util.tag_uri(self.DOMAIN, str(id)),
      'objectType': self.OBJECT_TYPES.get(post.get('type'), 'note'),
      'published': post.get('created_time'),
      'updated': post.get('updated_time'),
      'author': self.user_to_actor(post.get('from')),
      # FB post ids are of the form USERID_POSTID
      'url': 'http://facebook.com/' + id.replace('_', '/posts/'),
      'image': {'url': post.get('picture')},
      }

    # linkify mention tags in content. note that the message_tags field is a
    # dict in posts and a list in comments. see facebook_test.py for examples.
    content = post.get('message', '')
    mtags = post.get('message_tags', [])
    if isinstance(mtags, dict):
      mtags = sum(mtags.values(), [])  # sum joins the singleton lists together
    mtags.sort(key=lambda t: t['offset'])

    if mtags:
      last_end = 0
      orig = content
      content = ''
      for tag in mtags:
        start = tag['offset']
        end = start + tag['length']

        content += orig[last_end:start]
        content += '<a class="fb-mention" href="http://facebook.com/profile.php?id=%s">%s</a>' % (
          tag['id'], orig[start:end])
        last_end = end

      content += orig[last_end:]

    # linkify embedded links
    object['content'] = linkify(content)

    # to and with tags. use a dict to uniquify by id.
    tags = {}
    for field in 'to', 'with_tags':
      for tag in post.get(field, {}).get('data', []):
        id = tag.get('id')
        if id:
          tags[id] = {
            'objectType': 'person',
            'id': util.tag_uri(self.DOMAIN, id),
            'url': 'http://facebook.com/%s' % id,
            'displayName': tag.get('name'),
            }

    object['tags'] = sorted(tags.values(), key=lambda t: t['id'])

    # location
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
        object['location'].update({
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
      object['replies'] = {
        'items': items,
        'totalItems': len(items),
        }

    return util.trim_nulls(object)

  COMMENT_ID_RE = re.compile('(\d+)_(\d+)_(\d+)')

  def comment_to_object(self, comment):
    """Converts a comment to an object.

    Args:
      comment: dict, a decoded JSON comment

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    object = self.post_to_object(comment)
    if not object:
      return object

    object['objectType'] = 'comment'

    match = self.COMMENT_ID_RE.match(comment.get('id', ''))
    if match:
      object['url'] = 'http://facebook.com/%s/posts/%s?comment_id=%s' % match.groups()
      object['inReplyTo'] = {
        'id': util.tag_uri(self.DOMAIN, '%s_%s' % match.group(1, 2)),
        }

    return object

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
      'id': util.tag_uri(self.DOMAIN, handle),
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


def linkify(text):
  """Adds HTML links to URLs in the given plain text.

  For example: linkify("Hello http://tornadoweb.org!") would return
  Hello <a href="http://tornadoweb.org">http://tornadoweb.org</a>!

  Ignores URLs starting with 'http://facebook.com/profile.php?id=' since they
  may have been added to "mention" tags in main().

  Based on https://github.com/silas/huck/blob/master/huck/utils.py#L59
  """
  # I originally used the regex from
  # http://daringfireball.net/2010/07/improved_regex_for_matching_urls
  # but it gets all exponential on certain patterns (such as too many trailing
  # dots), causing the regex matcher to never return. This regex should avoid
  # those problems.
  _URL_RE = re.compile(ur"""\b((?:([\w-]+):(/{1,3})|www[.])(?:(?:(?:[^\s&()]|&amp;|&quo
t;)*(?:[^!"#$%&'()*+,.:;<=>?@\[\]^`{|}~\s]))|(?:\((?:[^\s&()]|&amp;|&quot;)*\)))+)""")

  def make_link(m):
    url = m.group(1)
    if url.startswith('http://facebook.com/profile.php?id='):
      # this is a "mention" tag that we added ourselves. leave it alone.
      return url
    proto = m.group(2)
    href = m.group(1)
    if not proto:
      href = 'http://' + href
    return u'<a href="%s">%s</a>' % (href, url)
 
  return _URL_RE.sub(make_link, text)


