"""Facebook source class. Uses the Graph API.

The Audience Targeting 'to' field is set to @public or @private based on whether
the Facebook object's 'privacy' field is 'EVERYONE' or anything else.
https://developers.facebook.com/docs/reference/api/privacy-parameter/

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

import appengine_config
from oauth_dropins.webutil import util
import source

# https://developers.facebook.com/docs/reference/login/
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
API_HOME_URL = 'https://graph.facebook.com/%s/home?offset=%d'
API_RSVP_URL = 'https://graph.facebook.com/%s/invited/%s'
API_FEED_URL = 'https://graph.facebook.com/me/feed'
API_COMMENTS_URL = 'https://graph.facebook.com/%s/comments'
API_LIKES_URL = 'https://graph.facebook.com/%s/likes'

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
RSVP_VERBS = {
  'attending': 'rsvp-yes',
  'declined': 'rsvp-no',
  'unsure': 'rsvp-maybe',
  'not_replied': 'invite',
  }
RSVP_ENDPOINTS = {
  'rsvp-yes': 'https://graph.facebook.com/%s/attending',
  'rsvp-no': 'https://graph.facebook.com/%s/declined',
  'rsvp-maybe': 'https://graph.facebook.com/%s/maybe',
}

# HTML snippet that embeds a post.
# https://developers.facebook.com/docs/plugins/embedded-posts/
EMBED_SCRIPT = """
<div id="fb-root"></div>
<script>(function(d, s, id) {
  var js, fjs = d.getElementsByTagName(s)[0];
  if (d.getElementById(id)) return;
  js = d.createElement(s); js.id = id;
  js.src = "//connect.facebook.net/en_US/all.js#xfbml=1&appId=318683258228687";
  fjs.parentNode.insertBefore(js, fjs);
}(document, 'script', 'facebook-jssdk'));</script>
"""
EMBED_POST = """
<br /><br />
<div class="fb-post" data-href="%s"></div>
<br />
"""

# Values for post.action['name'] that indicate a link back to the original post
SEE_ORIGINAL_ACTIONS=['see original']

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
    return self.user_to_actor(json.loads(
        self.urlopen(API_OBJECT_URL % user_id).read()))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details.

    Replies (ie comments) and likes are always included. They come from the
    'comments' and 'likes' fields in the Graph API's Post object:
    https://developers.facebook.com/docs/reference/api/post/#u_0_3

    Shares are not currently supported, since I haven't yet found a way to get
    them from the API. The sharedposts field / edge seems promising, but I
    haven't been able to get it to work, even with the read_stream OAuth scope.
    http://stackoverflow.com/questions/17373204/information-of-re-shared-status
    http://stackoverflow.com/a/17533380/186123
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
          posts = [json.loads(self.urlopen(API_OBJECT_URL % id).read())]
          break
        except urllib2.URLError, e:
          logging.warning("Couldn't fetch object %s: %s", id, e)
      else:
        posts = []

      if posts == [False]:  # FB returns false for "not found"
        posts = []

    else:
      url = API_SELF_POSTS_URL if group_id == source.SELF else API_HOME_URL
      url = url % (user_id if user_id else 'me', start_index)
      if count:
        url = util.add_query_params(url, {'limit': count})
      headers = {'If-None-Match': etag} if etag else {}
      try:
        resp = self.urlopen(url, headers=headers)
        etag = resp.info().get('ETag')
        posts = json.loads(resp.read()).get('data', [])
      except urllib2.HTTPError, e:
        if e.code == 304:  # Not Modified, from a matching ETag
          posts = []
        else:
          raise

    activities = [self.post_to_activity(p) for p in posts]
    response = self._make_activities_base_response(activities)
    response['etag'] = etag
    return response

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id, optional
    """
    url = API_OBJECT_URL % comment_id
    return self.comment_to_object(json.loads(self.urlopen(url).read()),
                                  post_author_id=activity_author_id)

  def get_share(self, activity_user_id, activity_id, share_id):
    """Not implemented. Returns None.

    I haven't yet found a way to fetch reshares in the Facebook API. :/

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object
    """
    return None

  def get_rsvp(self, activity_user_id, event_id, user_id):
    """Returns an ActivityStreams RSVP activity object.

    Args:


      activity_user_id: string id of the user who posted the event
      event_id: string event id
      user_id: string user id
    """
    url = API_RSVP_URL % (event_id, user_id)
    data = json.loads(self.urlopen(url).read()).get('data')
    return self.rsvp_to_object(data[0], event={'id': event_id}) if data else None

  def create(self, obj, include_link=False):
    """Creates a new post, comment, like, share, or RSVP.

    Args:
      obj: ActivityStreams object
      include_link: boolean

    Returns: dict with 'id' and 'url' keys for the newly created Facebook object
    """
    return self._create(obj, preview=False, include_link=include_link)

  def preview_create(self, obj, include_link=False):
    """Previews creating a new post, comment, like, share, or RSVP.

    Args:
      obj: ActivityStreams object
      include_link: boolean

    Returns: string HTML snippet
    """
    return self._create(obj, preview=True, include_link=include_link)

  def _create(self, obj, preview=None, include_link=False):
    """Creates a new post, comment, like, share, or RSVP.

    https://developers.facebook.com/docs/graph-api/reference/user/feed#publish
    https://developers.facebook.com/docs/graph-api/reference/object/comments#publish
    https://developers.facebook.com/docs/graph-api/reference/object/likes#publish
    https://developers.facebook.com/docs/graph-api/reference/event#attending

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: boolean

    Returns:
      If preview is True, a string HTML snippet. If False, a dict with 'id' and
      'url' keys for the newly created Facebook object.
    """
    # TODO: validation, error handling
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')
    base_id, base_url = self.base_object(obj)
    if base_id and not base_url:
      base_url = 'http://facebook.com/' + base_id


    content = obj.get('content', '')
    url = obj.get('url')
    if include_link and url:
      content += ('<br /><br />(%s)' if preview else '\n\n(%s)') % url
    preview_content = util.linkify(content)

    msg_data = urllib.urlencode({
        'message': content.encode('utf-8'),
        # TODO...or leave it to user's default?
        # 'privacy': json.dumps({'value': 'SELF'}),
        })

    if type == 'comment' and base_url:
      if preview:
        return ('will <span class="verb">comment</span> <em>%s</em> on this post:\n%s' %
                (preview_content, EMBED_POST % base_url))
      else:
        resp = json.loads(self.urlopen(API_COMMENTS_URL % base_id,
                                       data=msg_data).read())
        resp.update({'url': self.comment_url(base_id, resp['id']),
                     'type': 'comment'})

    elif type == 'activity' and verb == 'like':
      if preview:
        return ('will <span class="verb">like</span> this post:\n' +
                EMBED_POST % base_url)
      else:
        resp = json.loads(self.urlopen(API_LIKES_URL % base_id, data='').read())
        assert resp == True, resp
        resp = {'type': 'like'}

    elif type == 'activity' and verb in RSVP_ENDPOINTS:
      # TODO: event invites
      if preview:
        assert verb.startswith('rsvp-')
        return ('will <span class="verb">RSVP %s</span> to '
                '<a href="%s">this event</a>.<br />' % (verb[5:], base_url))
      else:
        resp = json.loads(self.urlopen(RSVP_ENDPOINTS[verb] % base_id, data='').read())
        assert resp == True, resp
        resp = {'type': 'rsvp'}

    elif type in ('note', 'article', 'comment'):
      if preview:
        return ('will <span class="verb">post</span>:<br /><br />'
                '<em>%s</em><br />' % preview_content)
      else:
        resp = json.loads(self.urlopen(API_FEED_URL, data=msg_data).read())
        resp.update({'url': self.post_url(resp), 'type': 'post'})

    else:
      raise NotImplementedError()

    if 'url' not in resp:
      resp['url'] = base_url
    return resp

  def urlopen(self, url, **kwargs):
    """Wraps urllib2.urlopen() and passes through the access token.
    """
    log_url = url
    if self.access_token:
      log_url = util.add_query_params(url, [('access_token',
                                             self.access_token[:4] + '...')])
      url = util.add_query_params(url, [('access_token', self.access_token)])
    logging.info('Fetching %s, kwargs %s', log_url, kwargs)
    return urllib2.urlopen(urllib2.Request(url, **kwargs),
                           timeout=appengine_config.HTTP_TIMEOUT)

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

  def comment_url(self, post_id, comment_id, post_author_id=None):
    """Returns a short Facebook URL for a comment.

    Args:
      post_id: Facebook post id
      comment_id: Facebook comment id
    """
    if post_author_id:
      post_id = post_author_id + '/posts/' + post_id
    return 'http://facebook.com/%s?comment_id=%s' % (post_id, comment_id)

  def post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    id = None
    if post.get('id'):
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
    display_name = None
    message = (post.get('message') or post.get('story') or
               post.get('description') or post.get('name'))

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

    privacy = post.get('privacy', {})
    if isinstance(privacy, dict):
      privacy = privacy.get('value')
    if privacy is not None:
      # privacy value '' means it doesn't have an explicit audience set, so i
      # *think* it inherits from its parent. TODO: use that value as opposed to
      # defaulting to public.
      public = privacy.lower() in ('', 'everyone', 'open')
      obj['to'] = [{'objectType': 'group',
                    'alias': '@public' if public else '@private'}]

    # tags and likes
    tags = itertools.chain(post.get('to', {}).get('data', []),
                           post.get('with_tags', {}).get('data', []),
                           *post.get('message_tags', {}).values())
    obj['tags'] = [self.postprocess_object({
        'objectType': OBJECT_TYPES.get(t.get('type'), 'person'),
        'id': self.tag_uri(t.get('id')),
        'url': 'http://facebook.com/%s' % t.get('id'),
        'displayName': t.get('name'),
        'startIndex': t.get('offset'),
        'length': t.get('length'),
        }) for t in tags]

    obj['tags'] += [self.postprocess_object({
        'id': self.tag_uri('%s_liked_by_%s' % (id, like.get('id'))),
        'url': url,
        'objectType': 'activity',
        'verb': 'like',
        'object': {'url': url},
        'author': self.user_to_actor(like),
        'content': 'likes this.',
        }) for like in post.get('likes', {}).get('data', [])]

    # "See Original" links
    post_actions = post.get('actions',[])
    see_orig_actions = (act for act in post_actions
                        if act.get('name', '').lower() in SEE_ORIGINAL_ACTIONS)
    obj['tags'] += [self.postprocess_object({
      'objectType': 'article',
      'url': act.get('link'),
      'displayName': act.get('name')
    }) for act in see_orig_actions]

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
        'url': 'http://facebook.com/%s' % id,
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
    elif 'location' in post:
      obj['location'] = {'displayName': post['location']}

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

    return self.postprocess_object(obj)

  COMMENT_ID_RE = re.compile('(\d+_)?(\d+)_(\d+)')

  def comment_to_object(self, comment, post_author_id=None):
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
      obj['url'] = self.comment_url(post_id, comment_id,
                                    post_author_id=post_author_id)
      obj['inReplyTo'] = [{'id': self.tag_uri(post_id)}]

    return self.postprocess_object(obj)

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

    url = (user.get('website') or user.get('link') or
           'http://facebook.com/' + handle)

    # facebook implements this as a 302 redirect
    image_url = 'http://graph.facebook.com/%s/picture?type=large' % handle
    actor = {
      'displayName': user.get('name'),
      'image': {'url': image_url},
      'id': self.tag_uri(handle),
      # numeric_id is our own custom field that always has the source's numeric
      # user id, if available.
      'numeric_id': id,
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

  def event_to_object(self, event, rsvps=None):
    """Converts an event to an object.

    Args:
      event: dict, a decoded JSON Facebook event
      rsvps: sequence, optional Facebook RSVPs

    Returns:
      an ActivityStreams object dict
    """
    obj = self.post_to_object(event)
    obj.update({
        'displayName': event.get('name'),
        'objectType': 'event',
        'author': self.user_to_actor(event.get('owner')),
        'startTime': event.get('start_time'),
        'endTime': event.get('end_time'),
      })

    if rsvps is not None:
      rsvps = [self.rsvp_to_object(r, event=event) for r in rsvps]
      self.add_rsvps_to_event(obj, rsvps)

    return self.postprocess_object(obj)

  def event_to_activity(self, event, rsvps=None):
    """Converts a event to an activity.

    Args:
      event: dict, a decoded JSON event

    Returns: an ActivityStreams activity dict
    """
    obj = self.event_to_object(event, rsvps=rsvps)
    return {'object': obj,
            'id': obj.get('id'),
            'url': obj.get('url'),
            }

  def rsvp_to_object(self, rsvp, event=None):
    """Converts an RSVP to an object.

    The 'id' field will ony be filled in if event['id'] is provided.

    Args:
      rsvp: dict, a decoded JSON Facebook RSVP
      event: Facebook event object. May contain only a single 'id' element.

    Returns:
      an ActivityStreams object dict
    """
    verb = RSVP_VERBS.get(rsvp.get('rsvp_status'))
    obj = {
      'objectType': 'activity',
      'verb': verb,
      }
    if verb == 'invite':
      invitee = self.user_to_actor(rsvp)
      invitee['objectType'] = 'person'
      obj.update({
          'object': invitee,
          'actor': self.user_to_actor(event.get('owner')) if event else None,
          })
    else:
      obj['actor'] = self.user_to_actor(rsvp)

    if event:
      user_id = rsvp.get('id')
      event_id = event.get('id')
      if event_id and user_id:
        obj['id'] = self.tag_uri('%s_rsvp_%s' % (event_id, user_id))
        obj['url'] = 'http://facebook.com/%s#%s' % (event_id, user_id)

    return self.postprocess_object(obj)
