"""Instagram source class.

Instagram's API doesn't tell you if a user has marked their account private or
not, so the Audience Targeting 'to' field is currently always set to @public.
http://help.instagram.com/448523408565555
https://groups.google.com/forum/m/#!topic/instagram-api-developers/DAO7OriVFsw
https://groups.google.com/forum/#!searchin/instagram-api-developers/private
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import datetime
import json
import logging
import operator
import re
import string
import urllib
import urllib2
import urlparse
import xml.sax.saxutils

import appengine_config
from oauth_dropins.webutil import util
import requests
import source

# Maps Instagram media type to ActivityStreams objectType.
OBJECT_TYPES = {'image': 'photo', 'video': 'video'}

API_USER_URL = 'https://api.instagram.com/v1/users/%s'
API_USER_MEDIA_URL = 'https://api.instagram.com/v1/users/%s/media/recent'
API_USER_FEED_URL = 'https://api.instagram.com/v1/users/self/feed'
API_USER_LIKES_URL = 'https://api.instagram.com/v1/users/%s/media/liked'
API_MEDIA_URL = 'https://api.instagram.com/v1/media/%s'
API_MEDIA_SEARCH_URL = 'https://api.instagram.com/v1/tags/%s/media/recent'
API_MEDIA_SHORTCODE_URL = 'https://api.instagram.com/v1/media/shortcode/%s'
API_MEDIA_POPULAR_URL = 'https://api.instagram.com/v1/media/popular'
API_MEDIA_LIKES_URL = 'https://api.instagram.com/v1/media/%s/likes'
API_COMMENT_URL = 'https://api.instagram.com/v1/media/%s/comments'

HTML_BASE_URL = (appengine_config.read('instagram_scrape_base') or
                 'https://www.instagram.com/')
HTML_MEDIA = HTML_BASE_URL + 'p/%s/'
HTML_PROFILE = HTML_BASE_URL + '%s/'

# URL-safe base64 encoding. used in Instagram.id_to_shortcode()
BASE64 = string.ascii_uppercase + string.ascii_lowercase + string.digits + '-_'

MENTION_RE = re.compile(r'@([A-Za-z0-9._]+)')


class Instagram(source.Source):
  """Implements the ActivityStreams API for Instagram."""

  DOMAIN = 'instagram.com'
  BASE_URL = 'https://www.instagram.com/'
  NAME = 'Instagram'
  FRONT_PAGE_TEMPLATE = 'templates/instagram_index.html'
  RESPONSE_CACHE_TIME = 60 * 60  # 60m

  EMBED_POST = """
  <script async defer src="//platform.instagram.com/en_US/embeds.js"></script>
  <blockquote class="instagram-media" data-instgrm-captioned data-instgrm-version="4"
              style="margin: 0 auto; width: 100%%">
    <p><a href="%(url)s" target="_top">%(content)s</a></p>
  </blockquote>
  """

  def __init__(self, access_token=None, allow_comment_creation=False, scrape=False):
    """Constructor.

    If an OAuth access token is provided, it will be passed on to Instagram.
    This will be necessary for some people and contact details, based on their
    privacy settings.

    Args:
      access_token: string, optional OAuth access token
      allow_comment_creation: boolean, optionally disable comment creation,
        useful if the app is not approved to create comments.
      scrape: boolean, whether to scrape instagram.com's HTML (True) or use
      the API (False)
    """
    self.access_token = access_token
    self.allow_comment_creation = allow_comment_creation
    self.scrape = scrape

  def urlopen(self, url, **kwargs):
    """Wraps urllib2.urlopen() and passes through the access token."""
    log_url = url
    if self.access_token:
      # TODO add access_token to the data parameter for POST requests
      url = util.add_query_params(url, [('access_token', self.access_token)])
    resp = util.urlopen(urllib2.Request(url, **kwargs))
    return resp if kwargs.get('data') else json.loads(resp.read()).get('data')

  @classmethod
  def user_url(cls, username):
    return '%s%s/' % (cls.BASE_URL, username)

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'self', ie the current user.

    Raises: InstagramAPIError
    """
    if user_id is None:
      assert self.scrape is False, 'get_actor() requires user_id when scraping'
      user_id = 'self'

    if self.scrape:
      return self.get_activities_response(group_id=source.SELF, user_id=user_id
                                         ).get('actor')
    else:
      return self.user_to_actor(util.trim_nulls(
        self.urlopen(API_USER_URL % user_id) or {}))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              scrape=False, cookie=None, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details. app_id is ignored.
    Supports min_id, but not ETag, since Instagram doesn't support it.

    http://instagram.com/developer/endpoints/users/#get_users_feed
    http://instagram.com/developer/endpoints/users/#get_users_media_recent

    Likes are always included, regardless of the fetch_likes kwarg. They come
    bundled in the 'likes' field of the API Media object:
    http://instagram.com/developer/endpoints/media/#

    Mentions are never fetched or included because the API doesn't support
    searching for them.
    https://github.com/snarfed/bridgy/issues/523#issuecomment-155523875

    Shares are never fetched included since there is no share feature.

    Instagram only supports search over hashtags, so if search_query is set, it
    must begin with #.

    May populate a custom 'ig_like_count' property in media objects. (Currently
    only when scraping.)

    Args (beyond Source.get_activities_response):
      scrape: if True, scrapes HTML from instagram.com instead of using the API.
        Populates the user's actor object in the 'actor' response field.
        Useful for apps that haven't yet been approved in the new permissions
        approval process. Currently only supports group_id=SELF. Also supports
        passing a shortcode as activity_id as well as the internal API id.
        http://developers.instagram.com/post/133424514006/instagram-platform-update
      cookie: string, only used if scrape=True

    Raises: InstagramAPIError
    """
    if scrape or self.scrape:
      if not (activity_id or
              (group_id == source.SELF and user_id) or
              (group_id == source.FRIENDS and cookie)):
        raise NotImplementedError(
          'Scraping only supports activity_id, user_id and group_id=@self, or cookie and group_id=@friends.')
      return self._scrape(user_id=user_id, activity_id=activity_id, cookie=cookie,
                          fetch_extras=fetch_replies or fetch_likes, cache=cache)

    if user_id is None:
      user_id = 'self'
    if group_id is None:
      group_id = source.FRIENDS

    if search_query:
      if search_query.startswith('#'):
        search_query = search_query[1:]
      else:
        raise NotImplementedError(
          'Instagram only supports search over hashtags, so search_query must '
          'begin with the # character.')

    # TODO: paging
    media = []
    kwargs = {}
    if min_id is not None:
      kwargs['min_id'] = min_id

    activities = []
    try:
      media_url = (API_MEDIA_URL % activity_id if activity_id else
                   API_USER_MEDIA_URL % user_id if group_id == source.SELF else
                   API_MEDIA_POPULAR_URL if group_id == source.ALL else
                   API_MEDIA_SEARCH_URL % search_query if group_id == source.SEARCH else
                   API_USER_FEED_URL if group_id == source.FRIENDS else None)
      assert media_url
      media = self.urlopen(util.add_query_params(media_url, kwargs))
      if media:
        if activity_id:
          media = [media]
        activities += [self.media_to_activity(m) for m in util.trim_nulls(media)]

      if group_id == source.SELF and fetch_likes:
        # add the user's own likes
        liked = self.urlopen(
          util.add_query_params(API_USER_LIKES_URL % user_id, kwargs))
        if liked:
          user = self.urlopen(API_USER_URL % user_id)
          activities += [self.like_to_object(user, l['id'], l['link'])
                         for l in liked]

    except urllib2.HTTPError, e:
      code, body = util.interpret_http_exception(e)
      # instagram api should give us back a json block describing the
      # error. but if it's an error for some other reason, it probably won't
      # be properly formatted json.
      try:
        body_obj = json.loads(body) if body else {}
      except ValueError:
        body_obj = {}

      if body_obj.get('meta', {}).get('error_type') == 'APINotFoundError':
        logging.exception(body_obj.get('meta', {}).get('error_message'))
      else:
        raise e

    return self.make_activities_base_response(activities)

  def _scrape(self, user_id=None, activity_id=None, cookie=None,
              fetch_extras=False, cache=None, shortcode=None):
    """Scrapes a user's profile or feed and converts the media to activities.

    Args:
      user_id: string
      activity_id: string, e.g. '1020355224898358984_654594'
      fetch_extras: boolean
      cookie: string
      shortcode: string, e.g. '4pB6vEx87I'

    Returns: dict activities API response
    """
    assert user_id or activity_id or shortcode or cookie
    assert not (activity_id and shortcode)

    if not shortcode:
      shortcode = self.id_to_shortcode(activity_id)

    url = (HTML_MEDIA % shortcode if shortcode
           else HTML_PROFILE % user_id if user_id
           else HTML_BASE_URL)
    kwargs = {}
    if cookie:
      kwargs = {'headers': {'Cookie': cookie}}
    resp = util.requests_get(url, allow_redirects=False, **kwargs)
    if ((cookie and 'not-logged-in' in resp.text) or
        (resp.status_code in (301, 302) and
         '/accounts/login' in resp.headers.get('Location', ''))):
      resp.status_code = 401
      raise requests.HTTPError('401 Unauthorized', response=resp)
    elif resp.status_code == 404:
      if activity_id:
        return self._scrape(shortcode=activity_id, cookie=cookie)
      # otherwise not found, fall through and return empty response
    else:
      resp.raise_for_status()

    activities, actor = self.html_to_activities(resp.text)

    if fetch_extras and not activity_id:
      # batch get cached counts of comments and likes for all activities
      cached = {}
      # don't update the cache until the end, in case we hit an error before
      cache_updates = {}
      if cache is not None:
        keys = []
        for activity in activities:
          _, id = util.parse_tag_uri(activity['id'])
          keys.extend(['AIL ' + id, 'AIC ' + id])
        cached = cache.get_multi(keys)

      for i, activity in enumerate(activities):
        obj = activity['object']
        _, id = util.parse_tag_uri(activity['id'])
        likes = obj.get('ig_like_count') or 0
        comments = obj.get('replies', {}).get('totalItems') or 0
        likes_key = 'AIL %s' % id
        comments_key = 'AIC %s' % id

        if (likes and likes != cached.get(likes_key) or
            comments and comments != cached.get(comments_key)):
          url = activity['url'].replace(self.BASE_URL, HTML_BASE_URL)
          full_activity, _ = self.html_to_activities(util.requests_get(url).text)
          if full_activity:
            activities[i] = full_activity[0]
            cache_updates.update({likes_key: likes, comments_key: comments})

      if cache_updates and cache is not None:
        cache.set_multi(cache_updates)

    resp = self.make_activities_base_response(activities)
    resp['actor'] = actor
    return resp

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, required
      activity_author_id: string activity author id. Ignored.
      activity: activity object, optional. Avoids fetching the activity.
    """
    if not activity:
      activity = self._get_activity(None, activity_id)
    if activity:
      tag_id = self.tag_uri(comment_id)
      for reply in activity.get('object', {}).get('replies', {}).get('items', []):
        if reply.get('id') == tag_id:
          return reply

  def get_share(self, activity_user_id, activity_id, share_id, activity=None):
    """Not implemented. Returns None. Resharing isn't a feature of Instagram.
    """
    return None

  def create(self, obj, include_link=source.OMIT_LINK, ignore_formatting=False):
    """Creates a new comment or like.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns: a CreationResult. if successful, content will have and 'id' and
             'url' keys for the newly created Instagram object
    """
    return self._create(obj, include_link=include_link, preview=False,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Preview a new comment or like.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns: a CreationResult. if successful, content and description
             will describe the new instagram object.
    """
    return self._create(obj, include_link=include_link, preview=True,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, include_link=source.OMIT_LINK, preview=None,
              ignore_formatting=False):
    """Creates a new comment or like.

    The OAuth access token must have been created with scope=comments+likes (or
    just one, respectively).
    http://instagram.com/developer/authentication/#scope

    To comment, you need to apply for access:
    https://docs.google.com/spreadsheet/viewform?formkey=dFNydmNsUUlEUGdySWFWbGpQczdmWnc6MQ

    http://instagram.com/developer/endpoints/comments/#post_media_comments
    http://instagram.com/developer/endpoints/likes/#post_likes

    Args:
      obj: ActivityStreams object
      include_link: string
      preview: boolean

    Returns: a CreationResult. if successful, content will have and 'id' and
             'url' keys for the newly created Instagram object
    """
    # TODO: validation, error handling
    type = obj.get('objectType')
    verb = obj.get('verb')
    base_obj = self.base_object(obj)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')

    logging.debug(
      'instagram create request with type=%s, verb=%s, id=%s, url=%s',
      type, verb, base_id, base_url)

    if type == 'comment':
      # most applications are not approved by instagram to create comments;
      # better to give a useful error message than try and fail.
      if not self.allow_comment_creation:
        return source.creation_result(
          abort=True,
          error_plain='Cannot publish comments on Instagram',
          error_html='<a href="http://instagram.com/developer/endpoints/comments/#post_media_comments">Cannot publish comments</a> on Instagram. The Instagram API technically supports creating comments, but <a href="http://stackoverflow.com/a/26889101/682648">anecdotal</a> <a href="http://stackoverflow.com/a/20229275/682648">evidence</a> suggests they are very selective about which applications they approve to do so.')
      content = obj.get('content', '').encode('utf-8')
      content = content if ignore_formatting else source.html_to_text(content)
      if preview:
        return source.creation_result(
          content=content,
          description='<span class="verb">comment</span> on <a href="%s">'
                      'this post</a>:\n%s' % (base_url, self.embed_post(base_obj)))

      self.urlopen(API_COMMENT_URL % base_id, data=urllib.urlencode({
        'access_token': self.access_token,
        'text': content,
      }))
      # response will be empty even on success, see
      # http://instagram.com/developer/endpoints/comments/#post_media_comments.
      # TODO where can we get the comment id?
      obj = self.comment_to_object({}, base_id, None)
      return source.creation_result(obj)

    elif type == 'activity' and verb == 'like':
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain='Could not find an Instagram post to like.',
          error_html='Could not find an Instagram post to <a href="http://indiewebcamp.com/like">like</a>. '
          'Check that your post has a like-of link to an Instagram URL or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Instagram.')

      if preview:
        return source.creation_result(
          description='<span class="verb">like</span> <a href="%s">'
                      'this post</a>:\n%s' % (base_url, self.embed_post(base_obj)))

      if not base_id:
        shortcode = self.post_id(base_url)
        logging.debug('looking up media by shortcode %s', shortcode)
        media_entry = self.urlopen(API_MEDIA_SHORTCODE_URL % shortcode) or {}
        base_id = media_entry.get('id')
        base_url = media_entry.get('link')

      logging.info('posting like for media id id=%s, url=%s',
                   base_id, base_url)
      # no response other than success/failure
      self.urlopen(API_MEDIA_LIKES_URL % base_id, data=urllib.urlencode({
        'access_token': self.access_token
      }))
      # TODO use the stored user_json rather than looking it up each time.
      # oauth-dropins auth_entities should have the user_json.
      me = self.urlopen(API_USER_URL % 'self')
      return source.creation_result(
        self.like_to_object(me, base_id, base_url))

    return source.creation_result(
      abort=True,
      error_plain='Cannot publish this post on Instagram. Instagram does not support posting photos or videos from 3rd party applications.',
      error_html='Cannot publish this post on Instagram. Instagram <a href="http://instagram.com/developer/endpoints/media/#get_media_popular">does not support</a> posting photos or videos from 3rd party applications.')

  def media_to_activity(self, media):
    """Converts a media to an activity.

    http://instagram.com/developer/endpoints/media/#get_media

    Args:
      media: JSON object retrieved from the Instagram API

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    # Instagram timestamps are evidently all PST.
    # http://stackoverflow.com/questions/10320607
    object = self.media_to_object(media)
    activity = {
      'verb': 'post',
      'published': object.get('published'),
      'id': object['id'],
      'url': object.get('url'),
      'actor': object.get('author'),
      'object': object,
      }

    return self.postprocess_activity(activity)

  def media_to_object(self, media):
    """Converts a media to an object.

    Args:
      media: JSON object retrieved from the Instagram API

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    id = media.get('id')

    user = media.get('user', {})
    content = xml.sax.saxutils.escape(media.get('caption', {}).get('text', ''))
    object = {
      'id': self.tag_uri(id),
      # TODO: detect videos. (the type field is in the JSON respose but not
      # propagated into the Media object.)
      'objectType': OBJECT_TYPES.get(media.get('type', 'image'), 'photo'),
      'published': util.maybe_timestamp_to_rfc3339(media.get('created_time')),
      'author': self.user_to_actor(user),
      'content': content,
      'url': media.get('link'),
      'to': [{
        'objectType': 'group',
        'alias': '@private' if user.get('is_private') else '@public',
      }],
      'attachments': [{
        'objectType': 'video' if 'videos' in media else 'image',
        # ActivityStreams 2.0 allows image to be a JSON array.
        # http://jasnell.github.io/w3c-socialwg-activitystreams/activitystreams2.html#link
        'image': sorted(
          media.get('images', {}).values(),
          # sort by size, descending, since atom.py
          # uses the first image in the list.
          key=operator.itemgetter('width'), reverse=True),
        # video object defined in
        # http://activitystrea.ms/head/activity-schema.html#rfc.section.4.18
        'stream': sorted(
          media.get('videos', {}).values(),
          key=operator.itemgetter('width'), reverse=True),
      }],
      # comments go in the replies field, according to the "Responses for
      # Activity Streams" extension spec:
      # http://activitystrea.ms/specs/json/replies/1.0/
      'replies': {
        'items': [self.comment_to_object(c, id, media.get('link'))
                  for c in media.get('comments', {}).get('data', [])],
        'totalItems': media.get('comments', {}).get('count'),
      },
      'tags': [{
        'objectType': 'hashtag',
        'id': self.tag_uri(tag),
        'displayName': tag,
        # TODO: url
      } for tag in media.get('tags', [])] +
      [self.user_to_actor(user.get('user'))
       for user in media.get('users_in_photo', [])] +
      [self.like_to_object(user, id, media.get('link'))
       for user in media.get('likes', {}).get('data', [])] +
      [{
        'objectType': 'person',
        'id': self.tag_uri(mention.group(1)),
        'displayName': mention.group(1),
        'url': self.user_url(mention.group(1)),
        'startIndex': mention.start(),
        'length': mention.end() - mention.start(),
        } for mention in MENTION_RE.finditer(content)],
    }

    for version in ('standard_resolution', 'low_resolution', 'thumbnail'):
      image = media.get('images').get(version)
      if image:
        object['image'] = {'url': image.get('url')}
        break

    for version in ('standard_resolution', 'low_resolution', 'low_bandwidth'):
      video = media.get('videos', {}).get(version)
      if video:
        object['stream'] = {'url': video.get('url')}
        break

    # http://instagram.com/developer/endpoints/locations/
    if 'location' in media:
      media_loc = media.get('location', {})
      object['location'] = {
        'id': media_loc.get('id'),
        'displayName': media_loc.get('name'),
        'latitude': media_loc.get('point', {}).get('latitude'),
        'longitude': media_loc.get('point', {}).get('longitude'),
        'address': {'formatted': media_loc.get('street_address')},
        'url': (media_loc.get('id')
                and 'https://instagram.com/explore/locations/%s/'
                % media_loc.get('id')),
      }

    return self.postprocess_object(object)

  def comment_to_object(self, comment, media_id, media_url):
    """Converts a comment to an object.

    Args:
      comment: JSON object retrieved from the Instagram API
      media_id: string
      media_url: string

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    return self.postprocess_object({
      'objectType': 'comment',
      'id': self.tag_uri(comment.get('id')),
      'inReplyTo': [{'id': self.tag_uri(media_id)}],
      'url': '%s#comment-%s' % (media_url, comment.get('id')) if media_url else None,
      # TODO: add PST time zone
      'published': util.maybe_timestamp_to_rfc3339(comment.get('created_time')),
      'content': comment.get('text'),
      'author': self.user_to_actor(comment.get('from')),
      'to': [{'objectType': 'group', 'alias': '@public'}],
    })

  def like_to_object(self, liker, media_id, media_url):
    """Converts a like to an object.

    Args:
      liker: JSON object from the Instagram API, the user who does the liking
      media_id: string
      media_url: string

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    return self.postprocess_object({
        'id': self.tag_uri('%s_liked_by_%s' % (media_id, liker.get('id'))),
        'url': '%s#liked-by-%s' % (media_url, liker.get('id')) if media_url else None,
        'objectType': 'activity',
        'verb': 'like',
        'object': {'url': media_url},
        'author': self.user_to_actor(liker),
    })

  def user_to_actor(self, user):
    """Converts a user to an actor.

    Args:
      user: JSON object from the Instagram API

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    if not user:
      return {}

    id = user.get('id')
    username = user.get('username')
    actor = {
      'id': self.tag_uri(id or username),
      'username': username,
      'objectType': 'person',
    }
    if not id or not username:
      return actor

    urls = sum((util.extract_links(user.get(field)) for field in ('website', 'bio')),
               [])
    if urls:
      actor['url'] = urls[0]
      if len(urls) > 1:
        actor['urls'] = [{'value': u} for u in urls]
    else:
      actor['url'] = self.user_url(username)

    actor.update({
      'displayName': user.get('full_name') or username,
      'image': {'url': user.get('profile_picture')},
      'description': user.get('bio')
    })

    return util.trim_nulls(actor)

  def base_object(self, obj):
    """Extends the default base_object() to avoid using shortcodes as object ids.
    """
    base_obj = super(Instagram, self).base_object(obj)

    base_id = base_obj.get('id')
    if base_id and not base_id.replace('_', '').isdigit():
      # this isn't id. it's probably a shortcode.
      del base_obj['id']
      id = obj.get('id')
      if id:
        parsed = util.parse_tag_uri(id)
        if parsed and '_' in parsed[1]:
          base_obj['id'] = parsed[1].split('_')[0]

    return base_obj

  @staticmethod
  def id_to_shortcode(id):
    """Converts a media id to the shortcode used in its instagram.com URL.

    Based on http://carrot.is/coding/instagram-ids , which determined that
    shortcodes are just URL-safe base64 encoded ids.
    """
    if not id:
      return None

    if isinstance(id, basestring):
      parts = id.split('_')
      if not util.is_int(parts[0]):
        return id
      id = int(parts[0])

    A = ord('A')
    chars = []
    while id > 0:
      id, rem = divmod(id, 64)
      chars.append(BASE64[rem])

    return ''.join(reversed(chars))

  def html_to_activities(self, html):
    """Converts Instagram HTML to ActivityStreams activities.

    The input HTML may be from:
    * a user's feed, eg https://www.instagram.com/ while logged in
    * a user's profile, eg https://www.instagram.com/snarfed/
    * a photo or video, eg https://www.instagram.com/p/BBWCSrfFZAk/

    Args:
      html: unicode string

    Returns:
      ([ActivityStreams activities], ActivityStreams viewer actor)
    """
    # extract JSON data blob
    script_start = '<script type="text/javascript">window._sharedData = '
    start = html.find(script_start)
    if start == -1:
      return [], None

    # App Engine's Python 2.7.5 json module doesn't support unpaired surrogate
    # Unicode chars, so it chokes on some JSON docs. Monkey patch in simplejson
    # to fix that.
    # https://code.google.com/p/googleappengine/issues/detail?id=12823
    # http://stackoverflow.com/questions/15236742
    try:
      import simplejson
      json_module = simplejson
    except ImportError:
      json_module = json

    start += len(script_start)
    end = html.index(';</script>', start)
    data = json_module.loads(html[start:end])

    entry_data = data.get('entry_data', {})
    activities = []

    # find media
    medias = []
    profile_user = None
    for page in entry_data.get('FeedPage', []):
      medias.extend(page.get('feed', {}).get('media', {}).get('nodes', []))
    for page in entry_data.get('ProfilePage', []):
      profile_user = page.get('user', {})
      medias.extend(profile_user.get('media', {}).get('nodes', []))
    medias.extend(page.get('media') for page in entry_data.get('PostPage', []))

    for media in util.trim_nulls(medias):
      # preprocess to make its field names match the API's
      dims = media.get('dimensions', {})
      owner = media.get('owner', {})
      media.update({
        'link': 'https://www.instagram.com/p/%s/' % media.get('code'),
        'user': owner,
        'created_time': media.get('date'),
        'caption': {'text': media.get('caption')},
        'images': {'standard_resolution': {
          'url': media.get('display_src').replace('\/', '/'),
          'width': dims.get('width'),
          'height': dims.get('height'),
        }},
        'users_in_photo': media.get('usertags', {}).get('nodes', []),
      })

      id = media.get('id')
      owner_id = owner.get('id')
      if id and owner_id:
        media['id'] = '%s_%s' % (id, owner_id)

      comments = media.setdefault('comments', {}).setdefault('nodes', [])
      likes = media.setdefault('likes', {}).setdefault('nodes', [])
      for obj in [media] + comments + likes:
        obj['user']['profile_picture'] = \
          obj['user'].get('profile_pic_url', '').replace('\/', '/')

      media['comments']['data'] = comments
      for c in media['comments']['data']:
        c['from'] = c['user']
        c['created_time'] = c['created_at']
      media['likes']['data'] = [l['user'] for l in likes]

      if media.get('is_video'):
        media.update({
          'type': 'video',
          'videos': {'standard_resolution': {
            'url': media.get('video_url', '').replace('\/', '/'),
            'width': dims.get('width'),
            'height': dims.get('height'),
          }},
        })

      activity = self.media_to_activity(util.trim_nulls(media))
      activity['object']['ig_like_count'] = media['likes'].get('count', 0)
      self.postprocess_object(activity['object'])
      activities.append(super(Instagram, self).postprocess_activity(activity))

    actor = None
    viewer = data.get('config', {}).get('viewer') or profile_user or None
    if viewer:
      profile = viewer.get('profile_pic_url')
      if profile:
        viewer['profile_picture'] = profile.replace('\/', '/')
      website = viewer.get('external_url')
      if website:
        viewer['website'] = website.replace('\/', '/')
      viewer.setdefault('bio', viewer.get('biography'))
      actor = self.user_to_actor(viewer)
      if viewer.get('is_private'):
        actor['to'] = [{'objectType':'group', 'alias':'@private'}]

    return activities, actor
