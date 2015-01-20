"""Facebook source class. Uses the Graph API.

The Audience Targeting 'to' field is set to @public or @private based on whether
the Facebook object's 'privacy' field is 'EVERYONE' or anything else.
https://developers.facebook.com/docs/reference/api/privacy-parameter/

Retrieving @all activities from get_activities() (the default) currently returns
an incomplete set of activities, ie *NOT* exactly the same set as your Facebook
News Feed: https://www.facebook.com/help/327131014036297/

This is complicated, and I still don't fully understand how or why they differ,
but based on lots of experimenting and searching, it sounds like the current
state is that you just can't reproduce the News Feed via Graph API's /me/home,
FQL's stream table, or any other Facebook API, full stop. :(

Random details:

- My access tokens have the read_stream permission.
  https://developers.facebook.com/docs/facebook-login/permissions/v2.2#reference-read_stream

- Lots of FUD on Stack Overflow, etc. that permissions might be the root cause.
  Non-public posts, photos, etc from your friends may not be exposed to an app
  if they haven't added it themselves. Doesn't seem true empirically, since
  get_activities() does return some non-public posts.

- I tried lots of different values for stream_filter/filter_key, both Graph API
  and FQL. No luck.
  https://developers.facebook.com/docs/reference/fql/stream_filter/

- Back in 4/2012, an FB engineer posted on SO that this is expected, and that
  Graph API and FQL shouldn't differ: http://stackoverflow.com/a/10157136/186123

- The API docs *used* to say, "Note: /me/home retrieves an outdated view of the
  News Feed. This is currently a known issue and we don't have any near term
  plans to bring them back up into parity."
  (from old dead https://developers.facebook.com/docs/reference/api/#searching )

See the fql_stream_to_post() method below for code I used to experiment with the
FQL stream table.

TODO:
- friends' new friendships, ie "X is now friends with Y." Not currently
available in /me/home. http://stackoverflow.com/questions/4358026
- when someone likes multiple things (og.likes type), only the first is included
in the data.objects array.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import itertools
import json
import logging
import urllib
import urllib2
import urlparse

import appengine_config
from oauth_dropins import facebook as oauth_facebook
from oauth_dropins.webutil import util
import source
import webapp2

# https://developers.facebook.com/docs/facebook-login/permissions/#reference
OAUTH_SCOPES = ','.join((
    'read_stream',
    'user_actions.news',
    'user_actions.video',
    'user_actions:instapp',
    'user_activities',
    'user_games_activity',
    'user_likes',
    ))

API_OBJECT_URL = 'https://graph.facebook.com/v2.2/%s'
API_SELF_POSTS_URL = 'https://graph.facebook.com/v2.2/%s/posts?offset=%d'
API_HOME_URL = 'https://graph.facebook.com/v2.2/%s/home?offset=%d'
API_RSVP_URL = 'https://graph.facebook.com/v2.2/%s/invited/%s'
API_FEED_URL = 'https://graph.facebook.com/v2.2/me/feed'
API_COMMENTS_URL = 'https://graph.facebook.com/v2.2/%s/comments'
API_LIKES_URL = 'https://graph.facebook.com/v2.2/%s/likes'
API_SHARES_URL = 'https://graph.facebook.com/v2.2/%s/sharedposts'
API_PHOTOS_URL = 'https://graph.facebook.com/v2.2/me/photos'
API_NOTIFICATION_URL = 'https://graph.facebook.com/v2.2/%s/notifications'

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
  'rsvp-yes': 'https://graph.facebook.com/v2.2/%s/attending',
  'rsvp-no': 'https://graph.facebook.com/v2.2/%s/declined',
  'rsvp-maybe': 'https://graph.facebook.com/v2.2/%s/maybe',
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

  def object_url(self, id):
    # Facebook always uses www. They redirect bare facebook.com URLs to it.
    return 'https://www.facebook.com/%s' % id

  user_url = object_url

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
          resp = json.loads(self.urlopen(API_OBJECT_URL % id).read())
          if resp.get('error'):
            logging.warning("Couldn't fetch object %s: %s", id, resp)
          else:
            posts = [resp]
            break
        except urllib2.URLError, e:
          logging.warning("Couldn't fetch object %s: %s", id, e)
      else:
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

    if fetch_shares:
      for post, activity in zip(posts, activities):
        id = post.get('id', '').split('_', 1)[-1]  # strip any USERID_ prefix
        if id:
          try:
            resp = json.loads(self.urlopen(API_SHARES_URL % id).read())
            activity.setdefault('tags', []).extend(
              [self.share_to_object(share) for share in resp.get('data', [])])
          except urllib2.HTTPError, e:
            # /OBJ/sharedposts sometimes 400s, not sure why
            # https://github.com/snarfed/bridgy/issues/348
            if e.code / 100 != 4:
              raise

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
    try:
      resp = self.urlopen(API_OBJECT_URL % comment_id)
    except urllib2.HTTPError, e:
      if e.code == 400 and '_' in comment_id:
        # Facebook may want us to ask for this without the other prefixed id(s)
        resp = self.urlopen(API_OBJECT_URL % comment_id.split('_')[-1])

    return self.comment_to_object(json.loads(resp.read()),
                                  post_author_id=activity_author_id)

  def get_share(self, activity_user_id, activity_id, share_id):
    """Returns an ActivityStreams share activity object.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object
    """
    try:
      return self.share_to_object(
        json.loads(self.urlopen(API_SHARES_URL % share_id).read()))
    except urllib2.HTTPError, e:
      # /OBJ/sharedposts sometimes 400s, not sure why
      # https://github.com/snarfed/bridgy/issues/348
      if e.code / 100 != 4:
        raise

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
    """Creates a new post, comment, like, or RSVP.

    Args:
      obj: ActivityStreams object
      include_link: boolean

    Returns:
      a CreationResult whose contents will be a dict with 'id' and
      'url' keys for the newly created Facebook object (or None)
    """
    return self._create(obj, preview=False, include_link=include_link)

  def preview_create(self, obj, include_link=False):
    """Previews creating a new post, comment, like, or RSVP.

    Args:
      obj: ActivityStreams object
      include_link: boolean

    Returns:
      a CreationResult whose contents will be a unicode string HTML snippet
      or None
    """
    return self._create(obj, preview=True, include_link=include_link)

  def _create(self, obj, preview=None, include_link=False):
    """Creates a new post, comment, like, or RSVP.

    https://developers.facebook.com/docs/graph-api/reference/user/feed#publish
    https://developers.facebook.com/docs/graph-api/reference/object/comments#publish
    https://developers.facebook.com/docs/graph-api/reference/object/likes#publish
    https://developers.facebook.com/docs/graph-api/reference/event#attending

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: boolean

    Returns:
      a CreationResult

      If preview is True, the contents will be a unicode string HTML
      snippet. If False, it will be a dict with 'id' and 'url' keys
      for the newly created Facebook object.
    """
    # TODO: validation, error handling
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')

    base_obj = self.base_object(obj, verb=verb)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')
    if base_id and not base_url:
      base_url = base_obj['url'] = self.object_url(base_id)

    content = self._content_for_create(obj)
    if not content:
      if type == 'activity':
        content = verb
      else:
        return source.creation_result(
          abort=False,  # keep looking for things to post
          error_plain='No content text found.',
          error_html='No content text found.')

    url = obj.get('url')
    if include_link and url:
      content += '\n\n(Originally published at: %s)' % url
    preview_content = util.linkify(content)
    msg_data = {'message': content.encode('utf-8')}
    if appengine_config.DEBUG:
      msg_data['privacy'] = json.dumps({'value': 'SELF'})
    msg_data = urllib.urlencode(msg_data)

    if type == 'comment':
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a Facebook status to reply to.',
          error_html='Could not find a Facebook status to <a href="http://indiewebcamp.com/comment">reply to</a>. '
          'Check that your post has an <a href="http://indiewebcamp.com/comment">in-reply-to</a> '
          'link a Facebook URL or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Facebook.')

      if preview:
        desc = ('<span class="verb">comment</span> on '
                '<a href="%s">this post</a>:\n%s' % (base_url, EMBED_POST % base_url))
        return source.creation_result(content=preview_content, description=desc)
      else:
        resp = json.loads(self.urlopen(API_COMMENTS_URL % base_id,
                                       data=msg_data).read())
        url = self.comment_url(base_id, resp['id'],
                               post_author_id=base_obj.get('author', {}).get('id'))
        resp.update({'url': url, 'type': 'comment'})

    elif type == 'activity' and verb == 'like':
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a Facebook status to like.',
          error_html='Could not find a Facebook status to <a href="http://indiewebcamp.com/favorite">like</a>. '
          'Check that your post has an <a href="http://indiewebcamp.com/favorite">like-of</a> '
          'link a Facebook URL or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Facebook.')

      if preview:
        desc = ('<span class="verb">like</span> <a href="%s">this post</a>:\n%s' %
                (base_url, EMBED_POST % base_url))
        return source.creation_result(description=desc)
      else:
        resp = json.loads(self.urlopen(API_LIKES_URL % base_id, data='').read())
        assert resp.get('success'), resp
        resp = {'type': 'like'}

    elif type == 'activity' and verb in RSVP_ENDPOINTS:
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain="This looks like an RSVP, but it's missing an "
          "in-reply-to link to the Facebook event.",
          error_html="This looks like an <a href='http://indiewebcamp.com/rsvp'>RSVP</a>, "
          "but it's missing an <a href='http://indiewebcamp.com/comment'>in-reply-to</a> "
          "link to the Facebook event.")

      # TODO: event invites
      if preview:
        assert verb.startswith('rsvp-')
        desc = ('<span class="verb">RSVP %s</span> to <a href="%s">this event</a>.' %
                (verb[5:], base_url))
        return source.creation_result(description=desc)
      else:
        resp = json.loads(self.urlopen(RSVP_ENDPOINTS[verb] % base_id, data='').read())
        assert resp.get('success'), resp
        resp = {'type': 'rsvp'}

    elif type in ('note', 'article') and obj.get('image'):
      image_url = obj.get('image').get('url')
      if preview:
        return source.creation_result(
          content='%s<br /><br /><img src="%s" />' % (preview_content, image_url),
          description='<span class="verb">post</span>:')
      else:
        msg_data = {'message': content.encode('utf-8'), 'url': image_url}
        if appengine_config.DEBUG:
          msg_data['privacy'] = json.dumps({'value': 'SELF'})
        msg_data = urllib.urlencode(msg_data)
        resp = json.loads(self.urlopen(API_PHOTOS_URL, data=msg_data).read())
        resp.update({'url': self.post_url(resp), 'type': 'post'})

    elif type in ('note', 'article'):
      if preview:
        return source.creation_result(content=preview_content,
                                      description='<span class="verb">post</span>:')
      else:
        resp = json.loads(self.urlopen(API_FEED_URL, data=msg_data).read())
        resp.update({'url': self.post_url(resp), 'type': 'post'})

    elif type == 'activity' and verb == 'share':
      return source.creation_result(
        abort=True,
        error_plain='Cannot publish shares on Facebook.',
        error_html='Cannot publish <a href="https://www.facebook.com/help/163779957017799">shares</a> '
        'on Facebook. This limitation is imposed by the '
        '<a href="https://developers.facebook.com/docs/graph-api/reference/object/sharedposts/#publish">Facebook Graph API</a>.')

    else:
      return source.creation_result(
        abort=False,
        error_plain='Cannot publish type=%s, verb=%s to Facebook' % (type, verb),
        error_html='Cannot publish type=%s, verb=%s to Facebook' % (type, verb))

    if 'url' not in resp:
      resp['url'] = base_url
    return source.creation_result(resp)

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

  def create_notification(self, user_id, text, link):
    """Sends the authenticated user a notification.

    Uses the Notifications API (beta):
    https://developers.facebook.com/docs/games/notifications/#impl

    Args:
      user_id: string, username or user ID
      text: string, shown to the user in the notification
      link: string URL, the user is redirected here when they click on the
        notification

    Raises: urllib2.HTPPError
    """
    logging.debug('Sending Facebook notification: %r, %s', text, link)
    params = {
      'template': text,
      'href': link,
      # this is a synthetic app access token.
      # https://developers.facebook.com/docs/facebook-login/access-tokens/#apptokens
      'access_token': '%s|%s' % (appengine_config.FACEBOOK_APP_ID,
                                 appengine_config.FACEBOOK_APP_SECRET),
      }
    url = API_NOTIFICATION_URL % user_id
    resp = urllib2.urlopen(urllib2.Request(url, data=urllib.urlencode(params)),
                           timeout=appengine_config.HTTP_TIMEOUT)
    logging.debug('Response: %s %s', resp.getcode(), resp.read())

  def post_url(self, post):
    """Returns a short Facebook URL for a post.

    Args:
      post: Facebook JSON post
    """
    author_id = post.get('from', {}).get('id')

    post_id = post.get('id')
    if not post_id:
      return None

    if author_id:
      post_ids = post_id.split('_')
      if post_ids[0] == author_id:
        post_id = '_'.join(post_ids[1:])
      return 'https://www.facebook.com/%s/posts/%s' % (author_id, post_id)
    else:
      return self.object_url(post_id)

  def comment_url(self, post_id, comment_id, post_author_id=None):
    """Returns a short Facebook URL for a comment.

    Args:
      post_id: Facebook post id
      comment_id: Facebook comment id
    """
    if post_author_id:
      post_id = post_author_id + '/posts/' + post_id
    return 'https://www.facebook.com/%s?comment_id=%s' % (post_id, comment_id)

  def base_object(self, obj, verb=None):
    """Returns the 'base' silo object that an object operates on.

    Includes special handling for Facebook photo URLs, e.g.
    https://www.facebook.com/photo.php?fbid=123&set=a.4.5.6&type=1

    Args:
      obj: ActivityStreams object
      verb: string, optional

    Returns: dict, minimal ActivityStreams object. Usually has at least id and
      url fields; may also have author.
    """
    base_obj = super(Facebook, self).base_object(obj)
    url = base_obj.get('url')
    if url:
      try:
        parsed = urlparse.urlparse(url)
        params = urlparse.parse_qs(parsed.query)
        author_id = (parsed.path.split('/posts/')[0][1:]
                     if '/posts/' in parsed.path else None)
        if author_id:
          base_obj.setdefault('author', {})['id'] = author_id

        # photo URLs look like:
        # https://www.facebook.com/photo.php?fbid=123&set=a.4.5.6&type=1
        # https://www.facebook.com/user/photos/a.12.34.56/78/?type=1&offset=0
        if parsed.path == '/photo.php':
          fbids = params.get('fbid')
          if fbids:
            base_obj['id'] = fbids[0]

        if verb == 'like':
          comment_id = params.get('comment_id')
          if comment_id:
            base_obj['id'] += '_' + comment_id[0]
          elif '_' not in base_obj['id'] and util.is_int(author_id):
            # add author user id prefix. https://github.com/snarfed/bridgy/issues/229
            base_obj['id'] = '%s_%s' % (author_id, base_obj['id'])

      except BaseException, e:
        logging.error(
          "Couldn't parse object URL %s : %s. Falling back to default logic.",
          url, e)

    return base_obj

  def post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    id = post.get('id', '').split('_', 1)[-1]  # strip any USERID_ prefix

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

  def post_to_object(self, post):
    """Converts a post to an object.

    Args:
      post: dict, a decoded JSON post

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    id = post.get('id', '').split('_', 1)[-1]  # strip any USERID_ prefix
    if not id:
      return {}

    post_type = post.get('type')
    status_type = post.get('status_type')
    url = self.post_url(post)
    display_name = None
    message = (post.get('message') or post.get('story') or
               post.get('description') or post.get('name'))

    picture = post.get('picture')
    if isinstance(picture, dict):
      picture = picture.get('data', {}).get('url')

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
      # FB post ids are of the form USERID_POSTID
      'url': url,
      'image': {'url': picture},
      'displayName': display_name,
      'fb_object_id': post.get('object_id'),
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
        'url': self.object_url(t.get('id')),
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

    # Escape HTML characters: <, >, &. Have to do it manually, instead of
    # reusing e.g. cgi.escape, so that we can shuffle over each tag startIndex
    # appropriately. :(
    if message:
      content = copy.copy(message)
      tags = sorted([t for t in obj['tags'] if t.get('startIndex')],
                    key=lambda t: t['startIndex'])

      entities = {'<': '&lt;', '>': '&gt;', '&': '&amp;'}
      i = 0
      while i < len(content):
        if tags and tags[0]['startIndex'] == i:
          tags.pop(0)
        entity = entities.get(content[i])
        if entity:
          content = content[:i] + entity + content[i + 1:]
          for tag in tags:
            tag['startIndex'] += len(entity) - 1
        i += 1

      assert not tags
      obj['content'] = content

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
        'url': self.object_url(id),
        }
      location = place.get('location', None)
      if isinstance(location, dict):
        lat = location.get('latitude')
        lon = location.get('longitude')
        if lat and lon:
          obj['location'].update({'latitude': lat, 'longitude': lon})
    elif 'location' in post:
      obj['location'] = {'displayName': post['location']}

    # comments go in the replies field, according to the "Responses for
    # Activity Streams" extension spec:
    # http://activitystrea.ms/specs/json/replies/1.0/
    comments = post.get('comments', {}).get('data')
    if comments:
      items = [self.comment_to_object(c, post_id=post['id']) for c in comments]
      obj['replies'] = {
        'items': items,
        'totalItems': len(items),
        }

    return self.postprocess_object(obj)

  def comment_to_object(self, comment, post_id=None, post_author_id=None):
    """Converts a comment to an object.

    Args:
      comment: dict, a decoded JSON comment
      post_id: optional string Facebook post id. Only used if the comment id
        doesn't have an embedded post id.
      post_author_id: optional string Facebook post author id. Only used if the
        comment id doesn't have an embedded post author id.

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

    ids = comment.get('id', '').split('_')
    comment_id = ids.pop()
    if ids:
      post_id = ids.pop() or post_id
    if ids:
      post_author_id = ids.pop() or post_author_id

    if post_id:
      if '_' not in obj['id']:
        obj['id'] = self.tag_uri('%s_%s' % (post_id, comment_id))
      obj['url'] = self.comment_url(post_id, comment_id,
                                    post_author_id=post_author_id)
      obj['inReplyTo'] = [{'id': self.tag_uri(post_id)}]

    return self.postprocess_object(obj)

  def share_to_object(self, share):
    """Converts a share (from /OBJECT/sharedposts) to an object.

    Args:
      share: dict, a decoded JSON share

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    obj = self.post_to_object(share)
    if not obj:
      return obj

    att = obj.get('attachments', [])
    obj.update({
      'objectType': 'activity',
      'verb': 'share',
      'object': att.pop(0) if att else {'url': share.get('link')},
    })

    content = obj.get('content')
    if content:
      obj['displayName'] = content
    else:
      obj['content'] = 'shared this.'

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
      'username': username,
      'description': user.get('bio'),
      }

    # extract web site links. extract_links uniquifies and preserves order
    urls = util.extract_links(user.get('website'))
    if not urls:
      urls = util.extract_links(user.get('link')) or [self.user_url(handle)]
    actor['url'] = urls[0]
    if len(urls) > 1:
      actor['urls'] = [{'value': u} for u in urls]

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
        obj['url'] = '%s#%s' % (self.object_url(event_id), user_id)

    return self.postprocess_object(obj)

  def fql_stream_to_post(self, stream, actor=None):
    """Converts an FQL stream row to a Graph API post.

    Currently unused and untested! Use at your own risk.

    https://developers.facebook.com/docs/technical-guides/fql/
    https://developers.facebook.com/docs/reference/fql/stream/

    TODO: place, to, with_tags, message_tags, likes, comments, etc., most
    require extra queries to inflate.

    Args:
      stream: dict, a row from the FQL stream table
      actor: dict, a row from the FQL profile table

    Returns:
      a Graph API post dict

    Here's example code to query FQL and pass the results to this method:

      resp = self.urlopen('https://graph.facebook.com/v2.0/fql?' + urllib.urlencode(
          {'q': json.dumps({
            'stream': '''\
            SELECT actor_id, post_id, created_time, updated_time, attachment,
              privacy, message, description
FROM stream
WHERE filter_key IN (
  SELECT filter_key FROM stream_filter WHERE uid = me())
ORDER BY created_time DESC
LIMIT 50
''',
            'actors': '''\
SELECT id, name, username, url, pic FROM profile WHERE id IN
  (SELECT actor_id FROM #stream)
'''})})).read()

      # resp = appengine_config.read('fql.json')
      results = {q['name']: q['fql_result_set'] for q in json.loads(resp)['data']}
      actors = {a['id']: a for a in results['actors']}
      posts = [self.fql_stream_to_post(row, actor=actors[row['actor_id']])
               for row in results['stream']]
    """
    post = copy.deepcopy(stream)
    post.update({
      'id': stream.pop('post_id', None),
      'type': stream.pop('fb_object_type', None),
      'object_id': stream.pop('fb_object_id', None),
      'from': actor or {'id': stream.pop('actor_id', None)},
      # message, description, name, created_time, updated_time are left in place
      })

    # attachments
    att = stream.pop('attachment', {})
    for media in att.get('media') or [att]:
      type = media.get('type')
      obj = {
        'type': type,
        'url': media.get('href'),
        'title': att.get('name') or att.get('caption') or att.get('description'),
        'data': {'url': media.get('src')},
      }
      # last element of each type wins
      if type == 'photo':
        post['image'] = obj
      elif type == 'link':
        post['link'] = obj['url']

    return util.trim_nulls(post)


application = webapp2.WSGIApplication([
    ('/start_auth', oauth_facebook.StartHandler.to('/facebook/oauth_callback',
                                                   scopes=OAUTH_SCOPES)),
    ('/facebook/oauth_callback', oauth_facebook.CallbackHandler.to('/')),
    ], debug=appengine_config.DEBUG)
