"""Facebook source class. Supports both Graph API and scraping HTML.

https://developers.facebook.com/docs/graph-api/using-graph-api/
"""
import collections
import copy
from datetime import datetime
import html
import logging
import re
import urllib.error, urllib.parse, urllib.request

from bs4.element import NavigableString, Tag
import dateutil.parser
import mf2util
import oauth_dropins.facebook
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads

from . import as1
from . import source

logger = logging.getLogger(__name__)

# Since API v2.4, we need to explicitly ask for the fields we want from most API
# endpoints with ?fields=...
# https://developers.facebook.com/docs/apps/changelog#v2_4_changes
#   (see the Declarative Fields section)
API_BASE = 'https://graph.facebook.com/v4.0/'
API_COMMENTS_FIELDS = 'id,message,from,created_time,message_tags,parent,attachment'
API_COMMENTS_ALL = 'comments?filter=stream&ids=%s&fields=' + API_COMMENTS_FIELDS
API_COMMENT = '%s?fields=' + API_COMMENTS_FIELDS
# Ideally this fields arg would just be [default fields plus comments], but
# there's no way to ask for that. :/
# https://developers.facebook.com/docs/graph-api/using-graph-api/v2.1#fields
#
# asking for too many fields here causes 500s with either "unknown error" or
# "ask for less info" errors. https://github.com/snarfed/bridgy/issues/664
API_EVENT_FIELDS = 'id,attending,declined,description,end_time,event_times,interested,maybe,noreply,name,owner,picture,place,start_time,timezone,updated_time'
API_EVENT = '%s?fields=' + API_EVENT_FIELDS
# /user/home requires the read_stream permission, which you probably don't have.
# details in the file docstring.
# https://developers.facebook.com/docs/graph-api/reference/user/home
# https://github.com/snarfed/granary/issues/26
API_HOME = '%s/home?offset=%d'
API_PHOTOS_UPLOADED = '%s/photos?type=uploaded&fields=id,album,comments,created_time,from,images,likes,link,name,name_tags,object_id,page_story_id,picture,privacy,reactions,shares,updated_time'
API_ALBUMS = '%s/albums?fields=id,count,created_time,from,link,name,privacy,type,updated_time'
API_POST_FIELDS = 'id,application,caption,comments,created_time,description,from,likes,link,message,message_tags,name,object_id,parent_id,picture,place,privacy,reactions,sharedposts,shares,source,status_type,story,to,type,updated_time,with_tags'
API_SELF_POSTS = '%s/feed?offset=%d&fields=' + API_POST_FIELDS
API_OBJECT = '%s_%s?fields=' + API_POST_FIELDS  # USERID_POSTID
API_SHARES = 'sharedposts?ids=%s'
# by default, me/events only includes events that the user has RSVPed yes,
# maybe, or interested to.
#
# also note that it includes the rsvp_status field, which isn't in
# API_EVENT_FIELDS because individual event objects don't support it.
API_USER_EVENTS = 'me/events?type=created&fields=rsvp_status,' + API_EVENT_FIELDS
API_USER_EVENTS_DECLINED = 'me/events?type=declined&fields=' + API_EVENT_FIELDS
API_USER_EVENTS_NOT_REPLIED = 'me/events?type=not_replied&fields=' + API_EVENT_FIELDS
# https://developers.facebook.com/docs/reference/opengraph/action-type/news.publishes/
API_NEWS_PUBLISHES = '%s/news.publishes?fields=' + API_POST_FIELDS
API_PUBLISH_POST = 'me/feed'
API_PUBLISH_COMMENT = '%s/comments'
API_PUBLISH_LIKE = '%s/likes'
API_PUBLISH_PHOTO = 'me/photos'
# the docs say these can't be published to, but they actually can. ¯\_(ツ)_/¯
# https://developers.facebook.com/docs/graph-api/reference/event/attending/#Creating
API_PUBLISH_ALBUM_PHOTO = '%s/photos'
API_PUBLISH_RSVP_ATTENDING = '%s/attending'
API_PUBLISH_RSVP_MAYBE = '%s/maybe'
API_PUBLISH_RSVP_DECLINED = '%s/declined'
# ...except /interested. POSTing to it returns this 400 error. details in
# https://github.com/snarfed/bridgy/issues/717
# {
#   "error": {
#     "message": "Unsupported post request. Object with ID '1680863225573216' does not exist, cannot be loaded due to missing permissions, or does not support this operation. Please read the Graph API documentation at https://developers.facebook.com/docs/graph-api",
#     "type": "GraphMethodException",
#     "code": 100
#   }
# }
API_PUBLISH_RSVP_INTERESTED = '%s/interested'
API_NOTIFICATION = '%s/notifications'

# endpoint for uploading video. note the graph-video subdomain.
# https://developers.facebook.com/docs/graph-api/video-uploads
API_UPLOAD_VIDEO = 'https://graph-video.facebook.com/v4.0/me/videos'

MAX_IDS = 50  # for the ids query param

M_HTML_BASE_URL = 'https://mbasic.facebook.com/'
M_HTML_TIMELINE_URL = '%s?v=timeline'
M_HTML_REACTIONS_URL = 'ufi/reaction/profile/browser/?ft_ent_identifier=%s'

# Use a modern browser user agent so that we get modern HTML tags like article
# and footer, which we then use to scrape.
SCRAPE_USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0'

# Maps Facebook Graph API type, status_type, or Open Graph data type to
# ActivityStreams objectType.
# https://developers.facebook.com/docs/graph-api/reference/post#fields
OBJECT_TYPES = {
  'application': 'application',
  'created_note': 'article',
  'event': 'event',
  'group': 'group',
  'instapp:photo': 'image',
  'link': 'note',
  'location': 'place',
  'music.song': 'audio',
  'note': 'article',  # amusing mismatch between FB and AS/mf2
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
# The fields in an event object that contain invited and RSVPed users. Slightly
# different from the rsvp_status field values, just to keep us entertained. :/
# Ordered by precedence.
RSVP_FIELDS = ('attending', 'declined', 'maybe', 'interested', 'noreply')
# Maps rsvp_status field to AS verb.
RSVP_VERBS = {
  'attending': 'rsvp-yes',
  'declined': 'rsvp-no',
  'maybe': 'rsvp-maybe',
  'unsure': 'rsvp-maybe',
  'not_replied': 'invite',
  'noreply': 'invite',
  # 'interested' RSVPs actually have rsvp_status='unsure', so this is only used
  # for rsvp_to_object(type='invited').
  'interested': 'rsvp-interested',
}
# Maps AS verb to API endpoint for publishing RSVP.
RSVP_PUBLISH_ENDPOINTS = {
  'rsvp-yes': API_PUBLISH_RSVP_ATTENDING,
  'rsvp-no': API_PUBLISH_RSVP_DECLINED,
  'rsvp-maybe': API_PUBLISH_RSVP_MAYBE,
  'rsvp-interested': None,  # not supported. see API_PUBLISH_RSVP_INTERESTED
}
# https://developers.facebook.com/docs/graph-api/reference/post/reactions
REACTION_CONTENT = {
  'ANGRY': '😡',
  'CARE': '🤗',
  'HAHA': '😆',
  'LOVE': '❤️',
  'PRIDE': '🏳️‍🌈',
  'SAD': '😢',
  'THANKFUL': '🌼',  # https://github.com/snarfed/bridgy/issues/748
  'WOW': '😮',
  # nothing for LIKE (it's a like :P) or for NONE
}

FacebookId = collections.namedtuple('FacebookId', ['user', 'post', 'comment'])


class Facebook(source.Source):
  """Facebook source class. See file docstring and :class:`Source` for details.

  Attributes:
    access_token (str): optional, OAuth access token
    user_id (str): optional, current user's id (either global or app-scoped)
    scrape (bool): whether to scrape mbasic.facebook.com's HTML (True) or use
      the API (False)
    cookie_c_user (str): optional c_user cookie to use when scraping
    cookie_xs (str): optional xs cookie to use when scraping
  """
  DOMAIN = 'facebook.com'
  BASE_URL = 'https://www.facebook.com/'
  NAME = 'Facebook'
  FRONT_PAGE_TEMPLATE = 'templates/facebook_index.html'
  POST_ID_RE = re.compile('^[0-9_:]+$')  # see parse_id() for gory details
  OPTIMIZED_COMMENTS = True

  # HTML snippet for embedding a post.
  # https://developers.facebook.com/docs/plugins/embedded-posts/
  EMBED_POST = """
  <div id="fb-root"></div>
  <script async defer
          src="//connect.facebook.net/en_US/all.js#xfbml=1&appId=318683258228687">
  </script>
  <div class="fb-post" data-href="%(url)s">
    <div class="fb-xfbml-parse-ignore"><a href="%(url)s">%(content)s</a></div>
  </div>
  """

  def __init__(self, access_token=None, user_id=None, scrape=False,
               cookie_c_user=None, cookie_xs=None):
    """Constructor.

    If an OAuth access token is provided, it will be passed on to Facebook. This
    will be necessary for some people and contact details, based on their
    privacy settings.

    If ``scrape`` is True, ``cookie_c_user`` and ``cookie_xs`` must be provided.

    Args:
      access_token (str): optional OAuth access token
      user_id (str): optional, current user's id (either global or app-scoped)
      scrape (bool): whether to scrape ``mbasic.facebook.com``'s HTML (True) or
        use the API (False)
      cookie_c_user (str): optional ``c_user`` cookie to use when scraping
      cookie_xs (str): optional ``xs`` cookie to use when scraping
    """
    if scrape:
      assert cookie_c_user and cookie_xs
    self.access_token = access_token
    self.user_id = user_id
    self.scrape = scrape
    self.cookie_c_user = cookie_c_user
    self.cookie_xs = cookie_xs

  def object_url(self, id):
    # Facebook always uses www. They redirect bare facebook.com URLs to it.
    return f'https://www.facebook.com/{id}'

  user_url = object_url

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id (str): id or username. Defaults to ``me``, ie the current user.
    """
    if user_id is None:
      user_id = 'me'
    return self.user_to_actor(self.urlopen(user_id))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              fetch_news=False, event_owner_id=None, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    See :meth:`Source.get_activities_response` for details.

    Likes, *top-level* replies (ie comments), and reactions are always included.
    They come from the ``comments``, ``likes``, and ``reactions`` fields in the
    Graph API's Post object:
    https://developers.facebook.com/docs/reference/api/post/

    Threaded comments, ie comments in reply to other top-level comments, require
    an additional API call, so they're only included if fetch_replies is True.

    Mentions are never fetched or included because the API doesn't support
    searching for them.
    https://github.com/snarfed/bridgy/issues/523#issuecomment-155523875

    Most parameters are documented in :meth:`Source.get_activities_response`.
    Additional parameters are documented here.

    Args:
      fetch_news (bool): whether to also fetch and include Open Graph news
        stories (``/USER/news.publishes``). Requires the ``user_actions.news``
        permission. Background in https://github.com/snarfed/bridgy/issues/479
      event_owner_id (str): if provided, only events owned by this user id
        will be returned. Avoids (but doesn't entirely prevent) processing big
        non-indieweb events with tons of attendees that put us over App Engine's
        instance memory limit. https://github.com/snarfed/bridgy/issues/77

    """
    if search_query:
      raise NotImplementedError()

    if self.scrape:
      return self._scrape_m(user_id=user_id, activity_id=activity_id,
                            fetch_replies=fetch_replies, fetch_likes=fetch_likes,
                            **kwargs)

    activities = []

    if activity_id:
      if not user_id:
        if '_' not in activity_id:
          raise ValueError(
            'Facebook activity ids must be of the form USERID_POSTID')
        user_id, activity_id = activity_id.split('_', 1)
      post = self.urlopen(API_OBJECT % (user_id, activity_id))
      if post.get('error'):
        logger.warning(f"Couldn't fetch object {activity_id}: {post}")
        posts = []
      else:
        posts = [post]

    else:
      url = API_SELF_POSTS if group_id == source.SELF else API_HOME
      user_id = user_id or 'me'
      url = url % (user_id, start_index)
      if count:
        url = util.add_query_params(url, {'limit': count})
      headers = {'If-None-Match': etag} if etag else {}
      try:
        resp = self.urlopen(url, headers=headers, _as=None)
        etag = resp.info().get('ETag')
        posts = self._as(list, source.load_json(resp.read(), url))
      except urllib.error.HTTPError as e:
        if e.code == 304:  # Not Modified, from a matching ETag
          posts = []
        else:
          raise

      if group_id == source.SELF:
        # TODO: save and use ETag for all of these extra calls
        # TODO: use batch API to get photos, events, etc in one request
        # https://developers.facebook.com/docs/graph-api/making-multiple-requests
        # https://github.com/snarfed/bridgy/issues/44
        if fetch_news:
          posts.extend(self.urlopen(API_NEWS_PUBLISHES % user_id, _as=list))
        posts = self._merge_photos(posts, user_id)
        if fetch_events:
          activities.extend(self._get_events(owner_id=event_owner_id))
      else:
        # for group feeds, filter out some shared_story posts because they tend
        # to be very tangential - friends' likes, related posts, etc.
        #
        # don't do it for individual people's feeds, e.g. the current user's,
        # because posts with attached links are also status_type == shared_story
        posts = [p for p in posts if p.get('status_type') != 'shared_story']

    id_to_activity = {}
    fetch_comments_ids = []
    fetch_shares_ids = []
    for post in posts:
      activity = self.post_to_activity(post)
      activities.append(activity)
      id = post.get('id')
      if id:
        id_to_activity[id] = activity

      type = post.get('type')
      status_type = post.get('status_type')
      if type != 'note' and status_type != 'created_note':
        fetch_comments_ids.append(id)
        if type != 'news.publishes':
          fetch_shares_ids.append(id)

    # don't fetch extras for Facebook notes. if you pass /comments a note id, it
    # 400s with "notes API is deprecated for versions ..."
    # https://github.com/snarfed/bridgy/issues/480
    if fetch_shares and fetch_shares_ids:
      # some sharedposts requests 400, not sure why.
      # https://github.com/snarfed/bridgy/issues/348
      with util.ignore_http_4xx_error():
        for id, shares in self._split_id_requests(API_SHARES, fetch_shares_ids).items():
          activity = id_to_activity.get(id)
          if activity:
            activity['object'].setdefault('tags', []).extend(
              [self.share_to_object(share) for share in shares])

    if fetch_replies and fetch_comments_ids:
      # some comments requests 400, not sure why.
      with util.ignore_http_4xx_error():
        for id, comments in self._split_id_requests(API_COMMENTS_ALL,
                                                    fetch_comments_ids).items():
          activity = id_to_activity.get(id)
          if activity:
            replies = activity['object'].setdefault('replies', {}
                                       ).setdefault('items', [])
            existing_ids = {reply['fb_id'] for reply in replies}
            for comment in comments:
              if comment['id'] not in existing_ids:
                replies.append(self.comment_to_object(comment))

    response = self.make_activities_base_response(util.trim_nulls(activities))
    response['etag'] = etag
    return response

  def _merge_photos(self, posts, user_id):
    """Fetches and merges photo objects into posts, replacing matching posts.

    Have to fetch uploaded photos manually since facebook sometimes collapses
    multiple photos into consolidated posts. Also, photo objects don't have the
    privacy field, so we get that from the corresponding post or album, if
    possible.

    * https://github.com/snarfed/bridgy/issues/562
    * http://stackoverflow.com/questions/12785120

    Populates a custom ``object_for_ids`` field in the FB photo objects. This is
    later copied into a custom ``fb_object_for_ids`` field in their
    corresponding AS objects.

    Args:
      posts (list of dict): Facebook post objects
      user_id (str): Facebook user id
 
    Returns:
      list of dict: new post and photo objects
    """
    assert user_id

    posts_by_obj_id = {}
    for post in posts:
      obj_id = post.get('object_id')
      if obj_id:
        existing = posts_by_obj_id.get(obj_id)
        if existing:
          logger.warning(f"merging posts for object_id {obj_id}: overwriting {existing.get('id')} with {post.get('id')}!")
        posts_by_obj_id[obj_id] = post

    albums = None  # lazy loaded, maps facebook id to ActivityStreams object

    photos = self.urlopen(API_PHOTOS_UPLOADED % user_id, _as=list)
    for photo in photos:
      album_id = photo.get('album', {}).get('id')
      post = posts_by_obj_id.pop(photo.get('id'), {})
      if post.get('id'):
        photo.setdefault('object_for_ids', []).append(post['id'])
      privacy = post.get('privacy')

      if privacy and privacy.get('value') != 'CUSTOM':
        photo['privacy'] = privacy
      elif album_id:
        if albums is None:
          albums = {a['id']: a for a in self.urlopen(API_ALBUMS % user_id, _as=list)}
        photo['privacy'] = albums.get(album_id, {}).get('privacy')
      else:
        photo['privacy'] = 'custom'  # ie unknown

    return ([p for p in posts if not p.get('object_id')] +
            list(posts_by_obj_id.values()) + photos)

  def _split_id_requests(self, api_call, ids):
    """Splits an API call into multiple to stay under the ``MAX_IDS`` limit per call.

    https://developers.facebook.com/docs/graph-api/using-graph-api#multiidlookup

    Args:
      api_call (str): with ``%s` placeholder for ``ids`` query param
      ids (sequence of str): ids

    Returns:
      list of dict: merged objects from the responses' ``data`` fields
    """
    results = {}
    for i in range(0, len(ids), MAX_IDS):
      resp = self.urlopen(api_call % ','.join(ids[i:i + MAX_IDS]))
      for id, objs in resp.items():
        # objs is usually a dict but sometimes a bool. (oh FB, never change!)
        results.setdefault(id, []).extend(self._as(dict, objs).get('data', []))

    return results

  def _get_events(self, owner_id=None):
    """Fetches the current user's events.

    * https://developers.facebook.com/docs/graph-api/reference/user/events/
    * https://developers.facebook.com/docs/graph-api/reference/event#edges

    TODO: also fetch and use ``API_USER_EVENTS_DECLINED``,
    ``API_USER_EVENTS_NOT_REPLIED``.

    Args:
      owner_id (str): if provided, only returns events owned by this user

    Returns:
      list of dict: ActivityStreams event objects
    """
    events = self.urlopen(API_USER_EVENTS, _as=list)
    return [self.event_to_activity(event) for event in events
            if not owner_id or owner_id == event.get('owner', {}).get('id')]

  def get_event(self, event_id, owner_id=None):
    """Returns a Facebook event post.

    Args:
      id (str): site-specific event id
      owner_id (str)

    Returns:
      dict: ActivityStreams activity, or None if the event is not found or is
      owned by a different user than ``owner_id`` (if provided)
    """
    event = None
    with util.ignore_http_4xx_error():
      event = self.urlopen(API_EVENT % event_id)

    if not event or event.get('error'):
      logger.warning(f"Couldn't fetch event {event_id}: {event}")
      return None

    event_owner_id = event.get('owner', {}).get('id')
    if owner_id and event_owner_id != owner_id:
      label = event.get('name') or event.get('id')
      logger.info(f'Ignoring event {label} owned by user id {event_owner_id} instead of {owner_id}')
      return None

    return self.event_to_activity(event)

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id (str): comment id
      activity_id (str): activity id, optional
      activity_author_id (str): activity author id, optional
      activity (dict): activity object (optional)

    Returns:
      dict:
    """
    try:
      resp = self.urlopen(API_COMMENT % comment_id)
    except urllib.error.HTTPError as e:
      if e.code == 400 and '_' in comment_id:
        # Facebook may want us to ask for this without the other prefixed id(s)
        resp = self.urlopen(API_COMMENT % comment_id.split('_')[-1])
      else:
        raise

    return self.comment_to_object(resp, post_author_id=activity_author_id)

  def get_share(self, activity_user_id, activity_id, share_id, activity=None):
    """Returns an ActivityStreams share activity object.

    Args:
      activity_user_id (str): id of the user who posted the original activity
      activity_id (str): activity id
      share_id (str): id of the share object
      activity (dict): activity object, optional

    Returns:
      dict:
    """
    orig_id = f'{activity_user_id}_{activity_id}'

    # shares sometimes 400, not sure why.
    # https://github.com/snarfed/bridgy/issues/348
    shares = {}
    with util.ignore_http_4xx_error():
      shares = self.urlopen(API_SHARES % orig_id, _as=dict)

    shares = shares.get(orig_id, {}).get('data', [])
    if not shares:
      return

    for share in shares:
      id = share.get('id')
      if not id:
        continue
      user_id, obj_id = id.split('_', 1)  # strip user id prefix
      if share_id == id == share_id or share_id == obj_id:
        with util.ignore_http_4xx_error():
          return self.share_to_object(self.urlopen(API_OBJECT % (user_id, obj_id)))

  def get_albums(self, user_id=None):
    """Fetches and returns a user's photo albums.

    Args:
      user_id (str): id or username. Defaults to ``me``, ie the current user.

    Returns:
      sequence of dict: ActivityStream album objects
    """
    url = API_ALBUMS % (user_id or 'me')
    return [self.album_to_object(a) for a in self.urlopen(url, _as=list)]

  def get_reaction(self, activity_user_id, activity_id, reaction_user_id,
                   reaction_id, activity=None):
    """Fetches and returns a reaction.

    Args:
      activity_user_id (str): id of the user who posted the original activity
      activity_id (str): activity id
      reaction_user_id (str): id of the user who reacted
      reaction_id (str): id of the reaction. one of: ``love``, ``wow``,
        ``haha``, ``sad``, ``angry``, ``thankful``, ``pride``, ``care``
      activity (dict): activity object (optional)

    Returns:
      dict:
    """
    if '_' not in reaction_id:  # handle just name of reaction type
      reaction_id = f'{activity_id}_{reaction_id}_by_{reaction_user_id}'
    return super(Facebook, self).get_reaction(
      activity_user_id, activity_id, reaction_user_id, reaction_id, activity=activity)

  def create(self, obj, include_link=source.OMIT_LINK,
             ignore_formatting=False):
    """Creates a new post, comment, like, or RSVP.

    Args:
      obj (dict): ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult or None: contents will be a dict with ``id`` and
      ``url`` keys for the newly created Facebook object
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Previews creating a new post, comment, like, or RSVP.

    Args:
      obj (dict): ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult or None: contents will be an HTML snippet
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates a new post, comment, like, or RSVP.

    * https://developers.facebook.com/docs/graph-api/reference/user/feed#publish
    * https://developers.facebook.com/docs/graph-api/reference/object/comments#publish
    * https://developers.facebook.com/docs/graph-api/reference/object/likes#publish
    * https://developers.facebook.com/docs/graph-api/reference/event#attending

    Args:
      obj (dict): ActivityStreams object
      preview (bool)
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult: if ``preview`` is True, the contents will be a HTML
      snippet. If False, it will be a dict with ``id`` and ``url`` keys for the
      newly created Facebook object.
    """
    # TODO: validation, error handling
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')

    base_obj = self.base_object(obj, verb=verb)
    base_id = base_obj.get('id')
    base_type = base_obj.get('objectType')
    base_url = base_obj.get('url')
    if base_id and not base_url:
      base_url = base_obj['url'] = self.object_url(base_id)

    video_url = util.get_first(obj, 'stream', {}).get('url')
    image_url = util.get_first(obj, 'image', {}).get('url')
    content = self._content_for_create(obj, ignore_formatting=ignore_formatting,
                                       strip_first_video_tag=bool(video_url))

    if not content and not video_url and not image_url:
      if type == 'activity':
        content = verb
      else:
        return source.creation_result(
          abort=False,  # keep looking for things to post
          error_plain='No content text found.',
          error_html='No content text found.')

    name = obj.get('displayName')
    if name and mf2util.is_name_a_title(name, content):
        content = name + u"\n\n" + content

    people = self._get_person_tags(obj)

    url = obj.get('url')
    if include_link == source.INCLUDE_LINK and url:
      content += f'\n\n(Originally published at: {url})'
    preview_content = util.linkify(content)
    if video_url:
      preview_content += f'<br /><br /><video controls src="{video_url}"><a href="{video_url}">this video</a></video>'
    elif image_url:
      preview_content += f'<br /><br /><img src="{image_url}" />'
    if people:
      preview_content += '<br /><br /><em>with %s</em>' % ', '.join(
        '<a href="%s">%s</a>' % (
          tag.get('url'), tag.get('displayName') or 'User %s' % tag['id'])
        for tag in people)
    msg_data = collections.OrderedDict({'message': content.encode('utf-8')})

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
        desc = f"""<span class="verb">comment</span> on <a href="{base_url}">this post</a>:
<br /><br />{self.embed_post(base_obj)}<br />"""
        return source.creation_result(content=preview_content, description=desc)
      else:
        if image_url:
          msg_data['attachment_url'] = image_url
        resp = self.urlopen(API_PUBLISH_COMMENT % base_id,
                            data=urllib.parse.urlencode(msg_data))
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
      elif base_type in ('person', 'page'):
        return source.creation_result(
          abort=True,
          error_plain="Sorry, the Facebook API doesn't support liking pages.",
          error_html='Sorry, <a href="https://developers.facebook.com/docs/graph-api/reference/user/likes#Creating">'
          "the Facebook API doesn't support liking pages</a>.")

      if preview:
        desc = '<span class="verb">like</span> '
        if base_type == 'comment':
          comment = self.comment_to_object(self.urlopen(base_id))
          author = comment.get('author', '')
          if author:
            author = self.embed_actor(author) + ':\n'
          desc += f"<a href=\"{base_url}\">this comment</a>:\n<br /><br />{author}{comment.get('content')}<br />"
        else:
          desc += f'<a href="{base_url}">this post</a>:\n<br /><br />{self.embed_post(base_obj)}<br />'
        return source.creation_result(description=desc)

      else:
        resp = self.urlopen(API_PUBLISH_LIKE % base_id, data='')
        assert resp.get('success'), resp
        resp = {'type': 'like'}

    elif type == 'activity' and verb in RSVP_PUBLISH_ENDPOINTS:
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain="This looks like an RSVP, but it's missing an "
          "in-reply-to link to the Facebook event.",
          error_html="This looks like an <a href='http://indiewebcamp.com/rsvp'>RSVP</a>, "
          "but it's missing an <a href='http://indiewebcamp.com/comment'>in-reply-to</a> "
          "link to the Facebook event.")
      elif verb == 'rsvp-interested':
        # API doesn't support creating "interested" RSVPs.
        # https://github.com/snarfed/bridgy/issues/717
        msg = 'Sorry, the Facebook API doesn\'t support creating "interested" RSVPs. Try a "maybe" RSVP instead!'
        return source.creation_result(abort=True, error_plain=msg, error_html=msg)

      # can't RSVP to multi-instance aka recurring events
      # https://developers.facebook.com/docs/graph-api/reference/event/#u_0_8
      event = self.urlopen(API_EVENT % base_id)
      if event.get('event_times'):
        return source.creation_result(
          abort=True,
          error_plain="That's a recurring event. Please RSVP to a specific instance!",
          error_html='<a href="%s">That\'s a recurring event.</a> Please RSVP to a specific instance!' % base_url)

      # TODO: event invites
      if preview:
        assert verb.startswith('rsvp-')
        desc = f'<span class="verb">RSVP {verb[5:]}</span> to <a href="{base_url}">this event</a>.'
        return source.creation_result(description=desc)
      else:
        resp = self.urlopen(RSVP_PUBLISH_ENDPOINTS[verb] % base_id, data='')
        assert resp.get('success'), resp
        resp = {'type': 'rsvp'}

    elif type in ('note', 'article'):
      if preview:
        return source.creation_result(content=preview_content,
                                      description='<span class="verb">post</span>:')
      if video_url:
        api_call = API_UPLOAD_VIDEO
        msg_data.update({
          'file_url': video_url,
          'description': msg_data.pop('message', ''),
        })
      elif image_url:
        api_call = API_PUBLISH_PHOTO
        msg_data['url'] = image_url
        # use Timeline Photos album, if we can find it, since it keeps photo
        # posts separate instead of consolidating them into a single "X added
        # n new photos..." post.
        # https://github.com/snarfed/bridgy/issues/571
        for album in self.urlopen(API_ALBUMS % 'me', _as=list):
          id = album.get('id')
          if id and album.get('type') == 'wall':
            api_call = API_PUBLISH_ALBUM_PHOTO % id
            break
        if people:
          # tags is JSON list of dicts with tag_uid fields
          # https://developers.facebook.com/docs/graph-api/reference/user/photos#Creating
          msg_data['tags'] = json_dumps([{'tag_uid': tag['id']} for tag in people])
      else:
        api_call = API_PUBLISH_POST
        if people:
          # tags is comma-separated user id string
          # https://developers.facebook.com/docs/graph-api/reference/user/feed#pubfields
          msg_data['tags'] = ','.join(tag['id'] for tag in people)

      resp = self.urlopen(api_call, data=urllib.parse.urlencode(msg_data))
      resp.update({'url': self.post_url(resp), 'type': 'post'})
      if video_url and not resp.get('success', True):
        msg = 'Video upload failed.'
        return source.creation_result(abort=True, error_plain=msg, error_html=msg)

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
        error_plain=f'Cannot publish type={type}, verb={verb} to Facebook',
        error_html=f'Cannot publish type={type}, verb={verb} to Facebook')

    if 'url' not in resp:
      resp['url'] = base_url
    return source.creation_result(resp)

  def _get_person_tags(self, obj):
    """Extracts and prepares person tags for Facebook users.

    Args:
      obj (dict): ActivityStreams object

    Returns:
      sequence of dict: ActivityStreams tag objects with ``url``, ``id``, and
      optional ``displayName`` fields. The ``id`` field is a raw Facebook user
      id.
    """
    people = {}  # maps id to tag

    for tag in obj.get('tags', []):
      url = tag.get('url', '')
      id = url.split('/')[-1]
      if (util.domain_from_link(url) == self.DOMAIN and util.is_int(id) and
          tag.get('objectType') == 'person' and
          not tag.get('startIndex')):  # mentions are linkified separately
        tag = copy.copy(tag)
        tag['id'] = id
        people[id] = tag

    return sorted(people.values(), key=lambda t: t['id'])

  def create_notification(self, user_id, text, link):
    """Sends the authenticated user a notification.

    Uses the Notifications API (beta):
    https://developers.facebook.com/docs/games/notifications/#impl

    Args:
      user_id (str): username or user ID
      text (str): shown to the user in the notification
      link (str): relative URL, the user is redirected here when they click on
        the notification. Note that only the path and query parameters are used!
        they're combined with the domain in your Facebook app's Game App URL:
        https://developers.facebook.com/docs/games/services/appnotifications#parameters

    Raises:
      urllib3.HTPPError
    """
    logger.debug(f'Sending Facebook notification: {text!r}, {link}')
    params = {
      'template': text,
      'href': link,
      # this is a synthetic app access token.
      # https://developers.facebook.com/docs/facebook-login/access-tokens/#apptokens
      'access_token': f'{oauth_dropins.facebook.FACEBOOK_APP_ID}|{oauth_dropins.facebook.FACEBOOK_APP_SECRET}',
    }
    url = API_BASE + API_NOTIFICATION % user_id
    resp = util.urlopen(urllib.request.Request(url, data=urllib.parse.urlencode(params)))
    logger.debug(f'Response: {resp.getcode()} {resp.read()}')

  def post_url(self, post):
    """Returns a short Facebook URL for a post.

    Args:
      post (dict): Facebook post
    """
    fb_id = post.get('id')
    if not fb_id:
      return None

    id = self.parse_id(fb_id)
    author_id = id.user or post.get('from', {}).get('id')
    if author_id and id.post:
      return f'https://www.facebook.com/{author_id}/posts/{id.post}'

    return self.object_url(fb_id)

  def comment_url(self, post_id, comment_id, post_author_id=None):
    """Returns a short Facebook URL for a comment.

    Args:
      post_id (str): Facebook post id
      comment_id (str): Facebook comment id
    """
    if post_author_id:
      post_id = post_author_id + '/posts/' + post_id
    return f'https://www.facebook.com/{post_id}?comment_id={comment_id}'

  @classmethod
  def base_id(cls, url):
    """Guesses the id of the object in the given URL.

    Returns:
      str or None:
    """
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    event_id = params.get('event_time_id')
    if event_id:
      return event_id[0]

    return super(Facebook, cls).base_id(url)

  def base_object(self, obj, verb=None, resolve_numeric_id=False):
    """Returns the 'base' silo object that an object operates on.

    This is mostly a big bag of heuristics for reverse engineering and
    parsing Facebook URLs. Whee.

    Args:
      obj (dict): ActivityStreams object
      verb (str): optional
      resolve_numeric_id (bool): if True, tries harder to populate the
        numeric_id field by making an additional API call to look up the object
        if necessary.

    Returns:
      dict: minimal ActivityStreams object. Usually has at least ``id``,
      ``numeric_id``, and ``url`` fields; may also have ``author``.
    """
    base_obj = super(Facebook, self).base_object(obj)

    url = base_obj.get('url')
    if not url:
      return base_obj

    author = base_obj.setdefault('author', {})
    base_id = base_obj.get('id')
    if base_id and not base_obj.get('numeric_id'):
      if util.is_int(base_id):
        base_obj['numeric_id'] = base_id
      elif resolve_numeric_id:
        base_obj = self.user_to_actor(self.urlopen(base_id))

    try:
      parsed = urllib.parse.urlparse(url)
      params = urllib.parse.parse_qs(parsed.query)
      assert parsed.path.startswith('/')
      path = parsed.path.strip('/')
      path_parts = path.split('/')

      if path == 'photo.php':
        # photo URLs look like:
        # https://www.facebook.com/photo.php?fbid=123&set=a.4.5.6&type=1
        # https://www.facebook.com/user/photos/a.12.34.56/78/?type=1&offset=0
        fbids = params.get('fbid')
        base_id = base_obj['id'] = fbids[0] if fbids else None

      elif len(path_parts) == 1:
        # maybe a profile/page URL?
        if not base_obj.get('objectType'):
          base_obj['objectType'] = 'person'  # or page
        if not base_id:
          base_id = base_obj['id'] = path_parts[0]
        # this is a gross hack - adding the FB username field to an AS object
        # and then re-running user_to_actor - but it's an easy/reusable way to
        # populate image, displayName, etc.
        if not base_obj.get('username') and not util.is_int(base_id):
          base_obj['username'] = base_id
        base_obj.update({k: v for k, v in self.user_to_actor(base_obj).items()
                         if k not in base_obj})

      elif len(path_parts) >= 3 and path_parts[1] == 'posts':
        author_id = path_parts[0]
        if not author.get('id'):
          author['id'] = author_id
        if util.is_int(author_id) and not author.get('numeric_id'):
          author['numeric_id'] = author_id

      # photo album URLs look like this:
      # https://www.facebook.com/media/set/?set=a.12.34.56
      # c.f. http://stackoverflow.com/questions/18549744
      elif path == 'media/set':
        set_id = params.get('set')
        if set_id and set_id[0].startswith('a.'):
          base_obj['id'] = set_id[0].split('.')[1]

      # single instances of recurring (aka multi-instance) event URLs look like this:
      # https://www.facebook.com/events/123/?event_time_id=456
      event_id = params.get('event_time_id')
      if event_id:
        event_id = event_id[0]
        base_obj.update({
          'id': event_id,
          'numeric_id': event_id,
          'url': self.object_url(event_id)
        })

      comment_id = params.get('comment_id') or params.get('reply_comment_id')
      if comment_id:
        base_obj['id'] += '_' + comment_id[0]
        base_obj['objectType'] = 'comment'

      if (base_id and '_' not in base_id and
          author.get('numeric_id') and not event_id):
        # add author user id prefix. https://github.com/snarfed/bridgy/issues/229
        base_obj['id'] = f"{author['numeric_id']}_{base_id}"

    except BaseException as e:
      logger.warning(
        "Couldn't parse object URL %s : %s. Falling back to default logic.",
        url, e, exc_info=True)

    return base_obj

  def post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post (dict): a decoded JSON post

    Returns:
      dict: ActivityStreams activity
    """
    obj = self.post_to_object(post, type='post')
    if not obj:
      return {}

    activity = {
      'verb': VERBS.get(post.get('type', obj.get('objectType')), 'post'),
      'published': obj.get('published'),
      'updated': obj.get('updated'),
      'fb_id': post.get('id'),
      'url': self.post_url(post),
      'actor': obj.get('author'),
      'object': obj,
    }

    post_id = self.parse_id(activity['fb_id']).post
    if post_id:
      activity['id'] = self.tag_uri(post_id)

    application = post.get('application')
    if application:
      activity['generator'] = {
        'displayName': application.get('name'),
        'id': self.tag_uri(application.get('id')),
      }
    return self.postprocess_activity(activity)

  def post_to_object(self, post, type=None):
    """Converts a post to an object.

    TODO: handle the ``sharedposts`` field

    Args:
      post (dict): a decoded JSON post
      type (str): object type: None, ``post``, or ``comment``

    Returns:
      dict: ActivityStreams object
    """
    assert type in (None, 'post', 'comment')

    fb_id = post.get('id')
    post_type = post.get('type')
    status_type = post.get('status_type')
    url = self.post_url(post)
    display_name = None
    message = (post.get('message') or post.get('story') or
               post.get('description') or post.get('name'))

    picture = post.get('picture')
    if isinstance(picture, dict):
      picture = picture.get('data', {}).get('url')
    # if the user posted this picture, try to get a larger size.
    if (picture and picture.endswith('_s.jpg') and
        (post_type == 'photo' or status_type == 'added_photos')):
      picture = picture[:-6] + '_o.jpg'

    data = post.get('data', {})
    for field in ('object', 'song'):
      obj = data.get(field)
      if obj:
        fb_id = obj.get('id')
        post_type = obj.get('type')
        url = obj.get('url')
        display_name = obj.get('title')

    object_type = OBJECT_TYPES.get(status_type) or OBJECT_TYPES.get(post_type)
    author = self.user_to_actor(post.get('from'))
    link = post.get('link', '')
    gift = link.startswith('/gifts/')

    if link.startswith('/'):
      link = urllib.parse.urljoin(self.BASE_URL, link)

    if gift:
      object_type = 'product'
    if not object_type:
      if picture and not message:
        object_type = 'image'
      else:
        object_type = 'note'

    id = self.parse_id(fb_id, is_comment=(type == 'comment'))
    if type == 'comment' and not id.comment:
      return {}
    elif type != 'comment' and not id.post:
      return {}

    obj = {
      'id': self.tag_uri(id.post),
      'fb_id': fb_id,
      'objectType': object_type,
      'published': util.maybe_iso8601_to_rfc3339(post.get('created_time')),
      'updated': util.maybe_iso8601_to_rfc3339(post.get('updated_time')),
      'author': author,
      # FB post ids are of the form USERID_POSTID
      'url': url,
      'image': {'url': picture},
      'displayName': display_name,
      'fb_object_id': post.get('object_id'),
      'fb_object_for_ids': post.get('object_for_ids'),
      'to': self.privacy_to_to(post, type=type),
    }

    # message_tags is a dict in most post types, but a list in some other object
    # types, e.g. comments.
    message_tags = post.get('message_tags', [])
    if isinstance(message_tags, dict):
      message_tags = sum(message_tags.values(), [])  # flatten
    elif not isinstance(message_tags, list):
      message_tags = list(message_tags)  # fingers crossed! :P

    # tags and likes
    tags = (self._as(list, post.get('to', {})) +
            self._as(list, post.get('with_tags', {})) +
            message_tags)
    obj['tags'] = [self.postprocess_object({
      'objectType': OBJECT_TYPES.get(t.get('type'), 'person'),
      'id': self.tag_uri(t.get('id')),
      'url': self.object_url(t.get('id')),
      'displayName': t.get('name'),
      'startIndex': t.get('offset'),
      'length': t.get('length'),
    }) for t in tags]

    obj['tags'] += [self.postprocess_object({
      'id': f"{obj['id']}_liked_by_{like.get('id')}",
      'url': url + f"#liked-by-{like.get('id')}",
      'objectType': 'activity',
      'verb': 'like',
      'object': {'url': url},
      'author': self.user_to_actor(like),
    }) for like in self._as(list, post.get('likes', {}))]

    for reaction in self._as(list, post.get('reactions', {})):
      id = reaction.get('id')
      type = reaction.get('type', '')
      content = REACTION_CONTENT.get(type)
      if content:
        type = type.lower()
        obj['tags'].append(self.postprocess_object({
          'id': f"{obj['id']}_{type}_by_{id}",
          'url': url + f'#{type}-by-{id}',
          'objectType': 'activity',
          'verb': 'react',
          'content': content,
          'object': {'url': url},
          'author': self.user_to_actor(reaction),
        }))

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

    # is there an attachment? prefer to represent it as a picture (ie image
    # object), but if not, fall back to a link.
    att = {
      'url': link or url,
      'image': {'url': picture},
      'displayName': post.get('name'),
      'summary': post.get('caption'),
      'content': post.get('description'),
    }

    if post_type == 'photo' or status_type == 'added_photos':
      att['objectType'] = 'image'
      obj['attachments'] = [att]
    elif link and not gift:
      att['objectType'] = 'article'
      obj['attachments'] = [att]

    # location
    place = post.get('place')
    if place:
      place_id = place.get('id')
      obj['location'] = {
        'displayName': place.get('name'),
        'id': self.tag_uri(place_id),
        'url': self.object_url(place_id),
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
      items = util.trim_nulls([self.comment_to_object(c, post_id=post['id'])
                               for c in comments])
      obj['replies'] = {
        'items': items,
        'totalItems': len(items),
      }

    return self.postprocess_object(obj)

  def comment_to_object(self, comment, post_id=None, post_author_id=None):
    """Converts a comment to an object.

    Args:
      comment (dict): a decoded JSON comment
      post_id (str): optional Facebook post id. Only used if the comment id
        doesn't have an embedded post id.
      post_author_id (str): optional Facebook post author id. Only used if the
        comment id doesn't have an embedded post author id.

    Returns:
      dict: ActivityStreams object
    """
    obj = self.post_to_object(comment, type='comment')
    if not obj:
      return obj

    obj['objectType'] = 'comment'

    fb_id = comment.get('id')
    obj['fb_id'] = fb_id
    id = self.parse_id(fb_id, is_comment=True)
    if not id.comment:
      return None

    post_id = id.post or post_id
    post_author_id = id.user or post_author_id
    if post_id:
      obj.update({
        'id': self._comment_id(post_id, id.comment),
        'url': self.comment_url(post_id, id.comment, post_author_id=post_author_id),
        'inReplyTo': [{
          'id': self.tag_uri(post_id),
          'url': self.post_url({'id': post_id, 'from': {'id': post_author_id}}),
        }],
      })

      parent_id = comment.get('parent', {}).get('id')
      if parent_id:
        obj['inReplyTo'].append({
          'id': self.tag_uri(parent_id),
          'url': self.comment_url(post_id,
                                  parent_id.split('_')[-1],  # strip POSTID_ prefix
                                  post_author_id=post_author_id)
        })

    att = comment.get('attachment')
    if (att and att.get('type') in
         ('photo', 'animated_image_autoplay', 'animated_image_share') and
        not obj.get('image')):
      obj['image'] = {'url': att.get('media', {}).get('image', {}).get('src')}
      obj.setdefault('attachments', []).append({
        'objectType': 'image',
        'image': obj['image'],
        'url': att.get('url'),
      })

    return self.postprocess_object(obj)

  def _comment_id(self, post_id, comment_id):
    return self.tag_uri(f'{post_id}_{comment_id}')

  def share_to_object(self, share):
    """Converts a share (from ``/OBJECT/sharedposts``) to an object.

    Args:
      share (dict): JSON share

    Returns:
      dict: ActivityStreams object
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

    return self.postprocess_object(obj)

  def user_to_actor(self, user):
    """Converts a user or page to an actor.

    Args:
      user (dict): Facebook user or page object

    Returns:
      dict: ActivityStreams actor
    """
    if not user:
      return {}

    id = user.get('id')
    username = user.get('username')
    handle = username or id
    if not handle:
      return {}

    # extract web site links. extract_links uniquifies and preserves order
    urls = (util.extract_links(user.get('link')) or [self.user_url(handle)]) + sum(
      (util.extract_links(user.get(field)) for field in
       ('website', 'about', 'description')), [])

    actor = {
      # FB only returns the type field if you fetch the object with ?metadata=1
      # https://developers.facebook.com/docs/graph-api/using-graph-api#introspection
      'objectType': 'page' if user.get('type') == 'page' else 'person',
      'displayName': user.get('name') or username,
      'id': self.tag_uri(handle),
      'updated': util.maybe_iso8601_to_rfc3339(user.get('updated_time')),
      'username': username,
      'description': user.get('description') or user.get('about'),
      'summary': user.get('about'),
      'url': urls[0],
      'urls': [{'value': u} for u in urls] if len(urls) > 1 else None,
    }

    # numeric_id is our own custom field that always has the source's numeric
    # user id, if available.
    if util.is_int(id):
      actor.update({
        'numeric_id': id,
        'image': {
          'url': f'{API_BASE}{id}/picture?type=large',
        },
      })

    location = user.get('location')
    if location:
      actor['location'] = {'id': location.get('id'),
                           'displayName': location.get('name')}

    return util.trim_nulls(actor)

  def event_to_object(self, event, rsvps=None):
    """Converts an event to an object.

    Args:
      event (dict): Facebook event object
      rsvps (sequence of dict): optional Facebook RSVPs

    Returns:
      dict: ActivityStreams object
    """
    obj = self.post_to_object(event)
    obj.update({
      'displayName': event.get('name'),
      'objectType': 'event',
      'author': self.user_to_actor(event.get('owner')),
      'startTime': event.get('start_time'),
      'endTime': event.get('end_time'),
    })

    if rsvps:
      as1.add_rsvps_to_event(
        obj, [self.rsvp_to_object(r, event=event) for r in rsvps])

    # de-dupe the event's RSVPs by (user) id. RSVP_FIELDS is ordered by
    # precedence, so iterate in reverse order so higher precedence fields
    # override.
    id_to_rsvp = {}
    for field in reversed(RSVP_FIELDS):
      for rsvp in event.get(field, {}).get('data', []):
        rsvp = self.rsvp_to_object(rsvp, type=field, event=event)
        id_to_rsvp[rsvp['id']] = rsvp
    as1.add_rsvps_to_event(obj, id_to_rsvp.values())

    return self.postprocess_object(obj)

  def event_to_activity(self, event, rsvps=None):
    """Converts a event to an activity.

    Args:
      event (dict): Facebook event object
      rsvps (list of dict): Facebook RSVP objects

    Returns:
      dict: ActivityStreams activity
    """
    obj = self.event_to_object(event, rsvps=rsvps)
    return {'object': obj,
            'id': obj.get('id'),
            'url': obj.get('url'),
            }

  def rsvp_to_object(self, rsvp, type=None, event=None):
    """Converts an RSVP to an object.

    The ``id`` field will ony be filled in if ``event['id']`` is provided.

    Args:
      rsvp (dict): Facebook RSVP object
      type (str): optional Facebook RSVP type, one of ``RSVP_FIELDS``
      event (dict): Facebook event object. May contain only a single ``id`
        element.

    Returns:
      dict: ActivityStreams object
    """
    verb = RSVP_VERBS.get(type or rsvp.get('rsvp_status'))
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
        obj['id'] = self.tag_uri(f'{event_id}_rsvp_{user_id}')
        obj['url'] = f'{self.object_url(event_id)}#{user_id}'

    return self.postprocess_object(obj)

  def album_to_object(self, album):
    """Converts a photo album to an object.

    Args:
      album (dict): Facebook album object

    Returns:
      dict: ActivityStreams object
    """
    if not album:
      return {}

    id = album.get('id')
    return self.postprocess_object({
      'id': self.tag_uri(id),
      'fb_id': id,
      'url': album.get('link'),
      'objectType': 'collection',
      'author': self.user_to_actor(album.get('from')),
      'displayName': album.get('name'),
      'totalItems': album.get('count'),
      'to': self.privacy_to_to(album),
      'published': util.maybe_iso8601_to_rfc3339(album.get('created_time')),
      'updated': util.maybe_iso8601_to_rfc3339(album.get('updated_time')),
    })

  def privacy_to_to(self, obj, type=None):
    """Converts a Facebook ``privacy`` field to an ActivityStreams ``to`` field.

    ``privacy`` is sometimes an object:
    https://developers.facebook.com/docs/graph-api/reference/post#fields

    ...and other times a string:
    https://developers.facebook.com/docs/graph-api/reference/album/#readfields

    Args:
      obj (dict): Facebook object (post, album, comment, etc)
      type (str): object type: None, ``post``, or ``comment``

    Returns:
      dict: ActivityStreams ``to`` object, or None if unknown
    """
    privacy = obj.get('privacy')
    if isinstance(privacy, dict):
      privacy = privacy.get('value')

    from_id = obj.get('from', {}).get('id')
    if (type == 'post' and not privacy and
        (from_id and self.user_id and from_id != self.user_id)):
      # privacy value '' means it doesn't have an explicit audience set, so it
      # inherits the defaults privacy setting for wherever it was posted: a
      # group, a page, a user's timeline, etc. unfortunately we haven't found a
      # way to get that default setting via the API. so, approximate that
      # by checking whether the current user posted it or someone else.
      # https://github.com/snarfed/bridgy/issues/559#issuecomment-159642227
      # https://github.com/snarfed/bridgy/issues/739#issuecomment-290118032
      return [{'objectType': 'unknown'}]
    elif privacy and privacy.lower() == 'custom':
      return [{'objectType': 'unknown'}]
    elif privacy is not None:
      public = privacy.lower() in ('', 'everyone', 'open')
      return [{'objectType': 'group', 'alias': '@public' if public else '@private'}]

  def email_to_object(self, html):
    """Converts a Facebook HTML notification email to an AS1 object.

    Arguments:
      html: str

    Returns:
      dict: ActivityStreams object, or None if ``html`` couldn't be parsed
    """
    soup = util.parse_html(html)
    type = None

    type = 'comment'
    descs = self._find_all_text(soup, r'commented on( your)?')

    if not descs:
      type = 'like'
      descs = self._find_all_text(soup, r'likes your')

    if not descs:
      return None

    links = descs[-1].find_all('a')
    name_link = links[0]
    name = name_link.get_text(strip=True)
    profile_url = name_link['href']
    resp_url = self._sanitize_url(links[1]['href'])
    post_url, comment_id = util.remove_query_param(resp_url, 'comment_id')

    if type == 'comment':
      # comment emails have a second section with a preview rendering of the
      # comment, picture and date and comment text are there.
      name_link = soup.find_all('a', string=re.compile(name))[1]

    picture = name_link.find_previous('img')['src']
    when = name_link.find_next('td')
    comment = when.find_next('span', class_=re.compile(r'mb_text'))
    if not comment:
      return None

    obj = {
      'author': {
        'objectType': 'person',
        'displayName': name,
        'image': {'url': picture},
        'url': self._sanitize_url(profile_url),
      },
      # TODO
      'to': [{'objectType': 'group', 'alias': '@public'}],
    }

    obj['published'] = self._scraped_datetime(when)

    # extract Facebook post ID from URL
    url_parts = urllib.parse.urlparse(resp_url)
    path = url_parts.path.strip('/').split('/')
    url_params = urllib.parse.parse_qs(url_parts.query)
    if len(path) == 3 and path[1] == 'posts':
      post_id = path[2]
    else:
      post_id = (util.get_first(url_params, 'story_fbid') or
                 util.get_first(url_params, 'fbid') or '')

    if type == 'comment':
      obj.update({
        # TODO: check that this works on urls to different types of posts, eg photos
        'objectType': 'comment',
        'id': self._comment_id(post_id, comment_id),
        'url': resp_url,
        'content': comment.get_text(strip=True),
        'inReplyTo': [{'url': post_url}],
      })
    elif type == 'like':
      liker_id = self.base_id(obj['author']['url'])
      obj.update({
        'objectType': 'activity',
        'verb': 'like',
        # TODO: handle author URLs for users without usernames
        'id': self.tag_uri(f'{post_id}_liked_by_{liker_id}'),
        'url': post_url + f'#liked-by-{liker_id}',
        'object': {'url': post_url},
      })

    return util.trim_nulls(obj)

  @staticmethod
  def _find_all_text(soup, regexp):
    """BeautifulSoup utility to search for text and returns a :class:bs4.`Tag`.

    I'd rather just use ``soup.find(string=...)`, but it returns a
    :class:bs4.`NavigableString` instead of a :class:bs4.`Tag`, and I need a
    :class:bs4.`Tag` so I can look at the elements inside it.
    https://www.crummy.com/software/BeautifulSoup/bs4/doc/#the-string-argument

    Args:
      soup (BeautifulSoup)
      regexp (str): must match target's text after stripping whitespace
    """
    regexp = re.compile(regexp)
    return soup.find_all(lambda tag: any(regexp.match(c.string.strip())
                                         for c in tag.contents if c.string))

  @classmethod
  def _sanitize_url(cls, url):
    """Normalizes a URL from a notification email.

    Specifically, removes the parts that only let the receiving user use it, and
    removes some personally identifying parts.

    Example profile URLs:
    * ``https://www.facebook.com/nd/?snarfed.org&amp;aref=123&amp;medium=email&amp;mid=1a2b3c&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=image``
    * ``https://www.facebook.com/n/?snarfed.org&amp;lloc=actor_profile&amp;aref=789&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com``
    * ``https://mbasic.facebook.com/story.php?story_fbid=10104372282388114&id=27301982&refid=17&_ft_=mf_story_key.123%3Atop_level_post_id.456%3Atl_objid.789%3Acontent_owner_id_new.012%3Athrowback_story_fbid.345%3Astory_location.4%3Astory_attachment_style.share%3Athid.678&__tn__=%2AW-R``

    Example post URLs:
    * ``https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com``
    * ``https://www.facebook.com/n/?permalink.php&amp;story_fbid=123&amp;id=456&amp;aref=789&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.2.34567890.ABCxyz&amp;n_m=recipient%40example.com``
    * ``https://www.facebook.com/n/?photo.php&amp;fbid=123&amp;set=a.456&amp;type=3&amp;comment_id=789&amp;force_theater=true&amp;aref=123&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com``

    Args:
      url (str)

    Returns (str): sanitized URL
    """
    if util.domain_from_link(url) != cls.DOMAIN and not url.startswith(M_HTML_BASE_URL):
      return url

    url = url.replace(M_HTML_BASE_URL, cls.BASE_URL)
    parsed = urllib.parse.urlparse(url)
    parts = list(parsed)

    if parsed.path in ('/nd/', '/n/', '/story.php'):
      query = urllib.parse.unquote(html.unescape(parsed.query))
      if parsed.path in ('/nd/', '/n/'):
        new_path, query = query.split('&', 1)
        parts[2] = new_path
      new_query = [(k, v) for k, v in urllib.parse.parse_qsl(query)
                   if k in ('story_fbid', 'fbid', 'id', 'comment_id')]
      parts[4] = urllib.parse.urlencode(new_query)
      parts[5] = ''  # fragment

    return urllib.parse.urlunparse(parts)

  @staticmethod
  def _scraped_datetime(tag):
    """Tries to parse a datetime string scraped from HTML (web or email).

    Examples seen in the wild:
    * ``December 14 at 12:35 PM``
    * ``5 July at 21:50``

    Args:
      tag: bs4.BeautifulSoup or bs4.Tag
    """
    if not tag:
      return None

    try:
      # sadly using parse(fuzzy=True) here makes too many mistakes on relative
      # time strings seen on mbasic, eg '22 hrs [ago]', 'Yesterday at 12:34 PM'
      parsed = dateutil.parser.parse(tag.get_text(strip=True), default=util.now())
      return parsed.isoformat('T')
    except (ValueError, OverflowError):
      logger.debug(f"Couldn't parse datetime string {tag!r}")

  def _scrape_m(self, user_id=None, activity_id=None, fetch_replies=False,
                fetch_likes=False, **kwargs):
    """Scrapes a user's timeline or a post and converts it to activities.

    Args:
      user_id (str)
      activity_id (str)
      fetch_replies (bool)
      fetch_likes (bool)
      kwargs: passed through to ``scraped_to_activity``

    Returns:
      dict: activities API response
    """
    user_id = user_id or self.user_id or ''
    if not (self.cookie_c_user and self.cookie_xs):
      raise NotImplementedError('Scraping requires c_user and xs cookies.')

    def get(url, *params, allow_redirects=False):
      url = urllib.parse.urljoin(M_HTML_BASE_URL, url % params)
      cookie = f'c_user={self.cookie_c_user}; xs={self.cookie_xs}'
      resp = util.requests_get(url, allow_redirects=allow_redirects, headers={
        'Cookie': cookie,
        'User-Agent': SCRAPE_USER_AGENT,
      })
      resp.raise_for_status()
      return resp

    if activity_id:
      # permalinks with classic ids now redirect to URLs with pfbid ids
      # https://about.fb.com/news/2022/09/deterring-scraping-by-protecting-facebook-identifiers/

      resp = get(activity_id, allow_redirects=True)
      activities = [self.scraped_to_activity(resp.text, **kwargs)[0]]
    else:
      resp = get(M_HTML_TIMELINE_URL, user_id)
      activities, _ = self.scraped_to_activities(resp.text, **kwargs)
      if fetch_replies:
        # fetch and convert individual post permalinks
        # TODO: cache?
        fbids = [a['fb_id'] for a in activities]
        activities = []
        for id in fbids:
          resp = get(id)
          activities.append(self.scraped_to_activity(resp.text)[0])

    if fetch_likes:
      # fetch and convert likes
      # TODO: cache?
      for activity in activities:
        resp = get(M_HTML_REACTIONS_URL, activity['fb_id'])
        self.merge_scraped_reactions(resp.text, activity)

    return self.make_activities_base_response(activities)

  def scraped_to_activities(self, scraped, log_html=False, **kwargs):
    """Converts HTML from an ``mbasic.facebook.com`` timeline to AS1 activities.

    Args:
      scraped (str): HTML
      log_html (bool)
      kwargs: unused

    Returns:
      tuple: ([AS activities], AS logged in actor (ie viewer))
    """
    soup = util.parse_html(scraped)
    if log_html:
      logging.info(soup.prettify())

    activities = []
    for post in soup.find_all(('article', 'div'), id=re.compile('u_0_.+')):
      permalink = post.find(href=re.compile(r'^/story\.php\?'))
      if not permalink:
        logger.debug('Skipping one due to missing permalink')
        continue

      header = post.find('header')
      if header and ('Suggested for you' in header.stripped_strings or
                     'is with' in header.stripped_strings):
        logger.debug(f'Skipping {header.stripped_strings}')
        continue

      post_id, owner_id = self._extract_scraped_ids(post)
      if not post_id or not owner_id:
        url = urllib.parse.urljoin(self.BASE_URL, permalink['href'])
        query = urllib.parse.urlparse(url).query
        parsed = urllib.parse.parse_qs(query)
        # story_fbid stopped being useful in May 2022, it switched to an opaque
        # token that changes regularly, even for the same post.
        # https://github.com/snarfed/facebook-atom/issues/27
        ft = util.get_first(parsed, '_ft_') or ''
        for elem in ft.split(':'):
          if elem.startswith('top_level_post_id.') or elem.startswith('mf_objid.'):
            post_id = elem.split('.')[1]
            if post_id:
              break
        else:
          post_id = util.get_first(parsed, 'story_fbid')

        owner_id = parsed['id'][0]

      author = self._m_html_author(post)
      if not author:
        logger.debug('Skipping due to missing author')
        continue
      author['id'] = self.tag_uri(owner_id)

      footer = post.footer
      if not footer:
        logger.debug('Skipping due to missing footer')
        continue

      public = footer and ('Public' in footer.stripped_strings or
                           # https://github.com/snarfed/bridgy/issues/1036
                           'Доступно всем' in footer.stripped_strings)

      to = ({'objectType': 'group', 'alias': '@public'} if public
            else {'objectType': 'unknown'})
      id = self.tag_uri(post_id)

      # pictures and videos. (remove from post so any text, eg "Play Video,"
      # isn't included in the content.)
      attachments = []
      for a in post.find_all('a', href=re.compile(r'^/photo\.php\?')):
        if a.img:
          alt = a.img.get('alt')
          attachments.append({
            'objectType': 'image',
            'displayName': alt,
            'image': {
              'url': a.img.get('src'),
              'displayName': alt,
            }})
        a.extract()
      for a in post.find_all('a', href=re.compile(r'^/video_redirect/\?')):
        vid = urllib.parse.parse_qs(urllib.parse.urlparse(a['href']).query).get('src')
        attachments.append({
          'objectType': 'video',
          'stream': {'url': vid[0] if vid else None},
          'image': {'url': a.img.get('src') if a.img else None},
        })
        a.extract()

      # link attachments
      attachments.extend(self._scrape_attachments(post))

      # comment count
      # TODO: internationalize this :/
      comments_count = None
      comments_link = post.find('a', string=re.compile('Comment'))
      if comments_link:
        tokens = comments_link.string.split()
        if tokens and util.is_int(tokens[0]):
          comments_count = int(tokens[0])

      # reaction count
      reactions_count = None
      react_link = post.find('a', href=re.compile('^/reactions/picker/'))
      if react_link:
        prev = react_link.find_previous_siblings('a')
        if prev:
          count_text = prev[-1].get_text(' ', strip=True)
          if util.is_int(count_text):
            reactions_count = int(count_text)

      url = self._sanitize_url(urllib.parse.urljoin(self.BASE_URL, f'/{post_id}'))
      activities.append({
        'objectType': 'activity',
        'verb': 'post',
        'id': id,
        'fb_id': post_id,
        'url': url,
        'actor': author,
        'object': {
          'objectType': 'note',
          'id': id,
          'fb_id': post_id,
          'url': url,
          'content': self._scraped_content(post),
          'published': self._scraped_datetime(footer.abbr),
          'author': author,
          'to': [to],
          'replies': {'totalItems': comments_count},
          'fb_reaction_count': reactions_count,
          'attachments': attachments,
        },
      })

    return util.trim_nulls(activities), None

  def scraped_to_activity(self, scraped, log_html=False, **kwargs):
    """Converts HTML from an ``mbasic.facebook.com`` post page to an AS1 activity.

    Args:
      scraped (str): HTML from an mbasic.facebook.com post permalink
      log_html (bool)
      kwargs: unused

    Returns:
      tuple: (dict AS activity or None, AS logged in actor (ie viewer))
    """
    soup = util.parse_html(scraped)
    if log_html:
      logging.info(soup.prettify())

    view = soup.find(id='m_story_permalink_view') or soup.find(id='MPhotoContent')
    if not view:
      return None, None

    published = view.find('abbr')
    footer = view.find('footer')
    if not footer and published:
      footer = published.parent.parent

    if view['id'] == 'MPhotoContent':
      body_parts = self._div(view, 0)
    else:
      body_parts = footer.find_previous_sibling('div')
      if body_parts and not body_parts.get_text('', strip=True):
        body_parts = body_parts.find_previous_sibling('div')
    if not body_parts:
      return None, None

    # author
    author = {}
    header = body_parts.find('header')
    actor_link = body_parts.find('a', class_='actor-link')
    if header:
      author = self._m_html_author(header)
    elif actor_link:
      author = self._profile_url_to_actor(actor_link['href'])
      author['displayName'] = actor_link.get_text(' ', strip=True)

    # visibility
    public = footer and ('Public' in footer.stripped_strings or
                         # https://github.com/snarfed/bridgy/issues/1036
                         'Доступно всем' in footer.stripped_strings)

    # post activity
    activity = {
      'objectType': 'activity',
      'verb': 'post',
      'actor': author,
      'object': {
        'objectType': 'note',
        'content': self._scraped_content(body_parts),
        'published': self._scraped_datetime(published),
        'author': author,
        'to': [{'objectType': 'group', 'alias': '@public'} if public
               else {'objectType': 'unknown'}],
      },
    }

    # photo
    action_bar = soup.find(id='MPhotoActionbar')
    if action_bar:
      photo = action_bar.find_previous_sibling('div')
      if photo:
        img = photo.find('img')
        if img:
          activity['object'].update({
            'objectType': 'photo',
            'image': {
              'url': img.get('src'),
              'displayName': img.get('alt'),
            }
          })

    post_id, owner_id = self._extract_scraped_ids(soup)
    if not post_id or not owner_id:
      return activity, None

    # numeric ids
    ids = {
      'id': self.tag_uri(post_id),
      'fb_id': post_id,
      'url': f'{self.BASE_URL}{post_id}',
    }
    activity.update(ids)
    activity['object'].update(ids)

    author['id'] = self.tag_uri(owner_id)
    if not author.get('url'):
      author['url'] = urllib.parse.urljoin(self.BASE_URL, owner_id)

    # link attachments
    activity['object']['attachments'] = []
    for div in body_parts.find_all('div', recursive=False)[1:]:
      activity['object']['attachments'].extend(self._scrape_attachments(div))

    # comments
    replies = []
    for comment in soup.find_all(id=re.compile(r'^\d+$')):
      # TODO: images in replies, eg:
      # https://mbasic.facebook.com/story.php?story_fbid=10104354535433154&id=212038&#10104354543447094
      replies.append({
        'objectType': 'comment',
        'id': self._comment_id(post_id, comment['id']),
        'url': util.add_query_params(ids['url'], {'comment_id': comment['id']}),
        'content': self._scraped_content(comment),
        'author': self._m_html_author(comment, 'h3'),
        'published': self._scraped_datetime(comment.find('abbr')),
        'inReplyTo': [{'id': ids['id'], 'url': ids['url']}],
      })

    if replies:
      activity['object']['replies'] = {
        'items': replies,
        'totalItems': len(replies),
      }

    return util.trim_nulls(activity), None

  @staticmethod
  def _extract_scraped_ids(soup):
    """Tries to scrape post id and owner id out of parsed HTML.

    Background on the time-limited ``pfbid`` param and why we don't want to use
    it in permalinks:
    https://about.fb.com/news/2022/09/deterring-scraping-by-protecting-facebook-identifiers/
    Args:
      soup (bs4.BeautifulSoup or bs4.Tag)

    Returns:
      (str or None, str or None) tuple: (post id, owner id)
    """
    post_id = owner_id = None

    post_id_re = re.compile('mf_story_key|top_level_post_id')
    data_ft_div = (soup if post_id_re.search(soup.get('data-ft', ''))
                   else soup.find(attrs={'data-ft': post_id_re}))

    if data_ft_div:
      data_ft = json_loads(html.unescape(data_ft_div['data-ft']))
      # prefer top_level_post_id, mf_story_key doesn't always work in FB URLs
      # that we construct, eg https://www.facebook.com/[mf_story_key]
      post_id = data_ft.get('top_level_post_id') or data_ft.get('mf_story_key')
      owner_id = str(data_ft.get('content_owner_id_new')
                     if 'mf_story_key' in data_ft  # this post is from a user
                     else data_ft.get('page_id'))  # this post is from a group

    if post_id and not post_id.startswith('pfbid'):
      return post_id, owner_id

    comment_form = soup.find('form', action=re.compile('^/a/comment.php'))
    if comment_form:
      query = urllib.parse.urlparse(comment_form['action']).query
      parsed = urllib.parse.parse_qs(query)
      post_id = parsed['ft_ent_identifier'][0]
      owner_id = parsed['av'][0]

    return post_id, owner_id

  def merge_scraped_reactions(self, scraped, activity):
    """Converts and merges scraped likes and reactions into an activity.

    New likes and emoji reactions are added to the activity in ``tags``.
    Existing likes and emoji reactions in ``tags`` are ignored.

    Args:
      scraped (str): HTML from an
        ``mbasic.facebook.com/ufi/reaction/profile/browser/`` page
      activity (dict): AS activity to merge these reactions into

    Returns:
      list of dict: AS like/react tag objects converted from scraped
    """
    soup = util.parse_html(scraped)

    tags = []
    for reaction in soup.find_all('li'):
      if reaction.get_text(' ', strip=True) == 'See More':
        continue
      imgs = reaction.find_all('img')
      if len(imgs) < 2:
        continue
      # TODO: profile pic is imgs[0]
      type = imgs[1]['alt'].lower()
      type_str = 'liked' if type == 'like' else type

      author = self._m_html_author(reaction, 'h3')
      if 'id' not in author:
        continue
      _, username = util.parse_tag_uri(author['id'])

      tag = {
        'objectType': 'activity',
        'verb': 'like' if type == 'like' else 'react',
        'id': self.tag_uri(f"{activity['fb_id']}_{type_str}_by_{username}"),
        'url': activity['url'] + f'#{type_str}-by-{username}',
        'object': {'url': activity['url']},
        'author': author,
      }
      if type != 'like':
        tag['content'] = REACTION_CONTENT.get(type.upper())
      tags.append(tag)

    as1.merge_by_id(activity['object'], 'tags', tags)
    return tags

  def scraped_to_actor(self, scraped):
    """Converts HTML from a profile about page to an AS1 actor.

    Args:
      scraped (str): HTML from an ``mbasic.facebook.com`` post permalink

    Returns:
      dict: AS1 actor
    """
    soup = util.parse_html(scraped)
    root = soup.find(id='root')
    if not root:
      return None

    # summary/tagline
    summary_div = self._div(root, 0, 0, 1, 1)
    # if this is the logged in user, there will be an extra div and an Edit Bio
    # link after it
    summary = ''
    if summary_div:
      summary = (self._div(summary_div, 0) or summary_div
                 ).get_text(' ', strip=True)

    # confusingly, the HTML has this as id=bio in HTML, but UI calls it "About
    # [name]" and calls the summary snippet above "bio" instead.
    about = None
    bio = root.find(id='bio')
    if bio:
      for edit_link in bio.find_all(
          'a', href=re.compile(r'^/profile/edit/infotab/section/forms/\?section=bio')):
        edit_link.clear()
      bio = self._div_text(bio, 0, 0)

    # web sites
    websites = []
    for label in root.find_all('a', href=re.compile(
        r'^/editprofile.php\?type=contact&edit=website')):
      websites.append(label.find_parent('td').find_next_sibling('td')
                      .get_text(' ', strip=True))

    websites += util.extract_links(summary) + util.extract_links(about)

    # name, profile picture
    name = soup.title.get_text(' ', strip=True)

    actor = {
      'objectType': 'person',
      'displayName': name,
      'description': bio,
      'summary': summary,
      'urls': [{'value': url} for url in websites],
    }

    # profile picture
    if name:
      img = soup.find('img', alt=re.compile(f'^{name},.*'))
      if img:
        actor['image'] = {'url': img['src']}

    profile = root.find('a', href=re.compile(r'[?&]v=timeline'))
    if profile:
      actor.update(self._profile_url_to_actor(profile['href']))
      actor['urls'].insert(0, {'value': actor['url']})

    return util.trim_nulls(actor)

  @classmethod
  def _scraped_content(cls, tag):
    """Extract and process content.

    Args:
      tag (bs4.Tag)

    Returns:
      str:
    """
    # TODO: distinguish between text elements with actual whitespace
    # before/after and without. this adds space to all of them, including
    # before punctuation, so you end up with eg 'Oh hi, Jeeves .'
    # (also apply any fix to scraped_to_activity().)
    try:
      content = cls._div(tag, 0, 0)
    except IndexError:
      logger.debug('Skipping due to non-post format (searching for content)')
      return ''

    if not content:
      return ''

    # remove outer tags
    while content.name in ('div', 'span', 'p'):
      elems = [t for t in content.contents if not
               (isinstance(t, NavigableString) and t.string.strip() == '')]
      if len(elems) == 1 and isinstance(elems[0], Tag):
        content = elems[0]
      else:
        break

    # join embedded links without whitespace
    for link in content.find_all(
        'a', href=re.compile(r'^https://lm\.facebook\.com/l\.php')):
      new_link = util.pretty_link(cls._unwrap_link(link))
      link.replace_with(util.parse_html(new_link).a)

    # remove Facebook's "... More" when content is ellipsized
    more = content.find('a', href=re.compile(r'^/story\.php'), string='More')
    if more:
      more.extract()

    return str(content)

  @classmethod
  def _scrape_attachments(cls, tag):
    """Extracts link attachments from a post.

    Args:
      tag (bs4.Tag): ``a`` or ``img`` tag

    Returns:
      list of dict: AS1 attachment objects
    """
    atts = []
    for link in tag.find_all('a', href=re.compile(r'^https://lm\.facebook\.com/l\.php')):
      url = cls._unwrap_link(link)
      name = link.h3
      img = link.img
      # all links in post text are wrapped, so check h3 and img so that we only
      # trigger on actual attachments
      if url and name and img:
        atts.append({
          'objectType': 'article',
          'url': url,
          'displayName': name.get_text(' ', strip=True),
          'image': {'url': cls._unwrap_link(img)},
        })

    return atts

  @staticmethod
  def _unwrap_link(tag):
    """Extracts the destination URL from a wrapped link.

    Currently supported:

    * ``https://lm.facebook.com/l.php?u=...`` (links)
    * ``https://external-sjc3-1.xx.fbcdn.net/safe_image.php?url=...`` (images)

    Args:
      tag (bs4.Tag): ``a`` or ``img`` tag

    Returns:
      str or None: URL
    """
    if tag:
      query = urllib.parse.parse_qs(
        urllib.parse.urlparse(tag.get('href') or tag.get('src')).query)
      url = query.get('u') or query.get('url')
      if url:
        return util.remove_query_param(url[0], 'fbclid')[0]

  def _m_html_author(self, soup, tag='strong'):
    """Finds an author link in ``mbasic.facebook.com`` HTML and converts it to AS1.

    Args:
      soup (bs4.BeautifulSoup)
      tag (str): optional, HTML tag surrounding ``<a>``

    Returns:
      dict: AS1 actor
    """
    if not soup:
      return {}

    author = soup.find(tag)
    if not author:
      return {}

    author = author.find('a')
    url = author.get('href')
    if not url:
      return {}
    actor = self._profile_url_to_actor(author['href'])
    actor['displayName'] = author.get_text(' ', strip=True)

    return actor

  def _profile_url_to_actor(self, url):
    """Converts a profile URL to an AS1 actor.

    Args:
      url (str)

    Returns:
      dict: AS1 actor, or ``{}`` if the profile URL can't be parsed
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.strip('/')
    params = urllib.parse.parse_qs(parsed.query)

    id = params.get('id')
    if id:
      id = id[0]

    lst = params.get('lst')
    if lst:
      # lst param is '[logged in user id]:[displayed user id]:[unknown]'
      id = urllib.parse.unquote(lst[0]).split(':')[1]

    username = None
    if not path.endswith('.php'):
      username = path

    if id or username:
      return {
        'objectType': 'person',
        'id': self.tag_uri(id or username),
        'numeric_id': id,
        'url': urllib.parse.urljoin(self.BASE_URL, username or id),
        'username': username,
      }

    return {}

  @staticmethod
  def _div(tag, *args):
    """Returns a descendant ``div`` via a given path of ``div``s.

    Args:
      *args: ``div`` indexes to navigate down. eg ``[1, 0, 2]`` means the second
        ``div`` child of tag, then that ``div``'s first ``div`` child, then that
        ``div``'s third ``div`` child.
    Returns:
      bs4.Tag: ...or None if the given path doesn't exist
    """
    assert args

    try:
      for index in args:
        tag = tag.find_all('div', recursive=False)[index]
      return tag
    except IndexError:
      return None

  @staticmethod
  def _div_text(tag, *args):
    """Returns the text inside a ``div``.

    Args:
      tag (bs4.Tag)
      *args: see :meth:`_div`

    Returns:
      str: or None if the given path doesn't exist
    """
    div = Facebook._div(tag, *args)
    return div.get_text(' ', strip=True) if div else None

  @staticmethod
  def parse_id(id, is_comment=False):
    r"""Parses a Facebook post or comment id.

    Facebook ids come in different formats:

    * Simple number, usually a user or post: ``12``
    * Two numbers with underscore, usually ``POST_COMMENT`` or ``USER_POST``\:
      ``12_34``
    * Three numbers with underscores, ``USER_POST_COMMENT``\: ``12_34_56``
    * Three numbers with colons, ``USER:POST:SHARD``\: ``12:34:63``
      (We're guessing that the third part is a shard in some FB internal system.
      In our experience so far, it's always either 63 or the app-scoped user id
      for 63.)
    * Two numbers with colon, ``POST:SHARD``\: ``12:34``
      (We've seen 0 as shard in this format.)
    * Four numbers with colons/underscore, ``USER:POST:SHARD_COMMENT``\:
      ``12:34:63_56``
    * Five numbers with colons/underscore, ``USER:EVENT:UNKNOWN:UNKNOWN_UNKNOWN``\.
      Not currently supported! Examples:
         * ``111599105530674:998145346924699:10102446236688861:10207188792305341_998153510257216``
         * ``111599105530674:195181727490727:10102446236688861:10205257726909910_195198790822354``

    Background:

    * https://github.com/snarfed/bridgy/issues/305
    * https://developers.facebook.com/bugs/786903278061433/

    Args:
      id (str or int)
      is_comment (bool)

    Returns:
      FacebookId: Some or all fields may be None.
    """
    assert is_comment in (True, False), is_comment

    blank = FacebookId(None, None, None)
    if id in (None, '', 'login.php'):
      # some FB permalinks redirect to login.php, e.g. group and non-public posts
      return blank

    id = str(id)
    user = None
    post = None
    comment = None

    by_colon = id.split(':')
    by_underscore = id.split('_')

    # colon id?
    if len(by_colon) in (2, 3) and all(by_colon):
      if len(by_colon) == 3:
        user = by_colon.pop(0)
      post, shard = by_colon
      parts = shard.split('_')
      if len(parts) >= 2 and parts[-1]:
        comment = parts[-1]
    elif len(by_colon) == 2 and all(by_colon):
      post = by_colon[0]
    # underscore id?
    elif len(by_underscore) == 3 and all(by_underscore):
      user, post, comment = by_underscore
    elif len(by_underscore) == 2 and all(by_underscore):
      if is_comment:
        post, comment = by_underscore
      else:
        user, post = by_underscore
    # plain number?
    elif util.is_int(id):
      if is_comment:
        comment = id
      else:
        post = id

    fbid = FacebookId(user, post, comment)

    for sub_id in user, post, comment:
      if sub_id and not re.match(r'^[0-9a-zA-Z]+$', sub_id):
        fbid = blank

    if fbid == blank:
      logger.error(f'Cowardly refusing Facebook id with unknown format: {id}')

    return fbid

  def resolve_object_id(self, user_id, post_id, activity=None):
    """Resolve a post id to its Facebook object id, if any.

    Used for photo posts, since Facebook has (at least) two different objects
    (and ids) for them, one for the post and one for each photo.

    This is the same logic that we do for canonicalizing photo objects in
    :meth:`get_activities` above.

    If activity is not provided, fetches the post from Facebook.

    Args:
      user_id (str): Facebook user id who posted the post
      post_id (str): Facebook post id
      activity (dict): optional AS activity representation of Facebook post

    Returns:
      str: Facebook object id or None
    """
    assert user_id, user_id
    assert post_id, post_id

    if activity:
      fb_id = (activity.get('fb_object_id') or
               activity.get('object', {}).get('fb_object_id'))
      if fb_id:
        return str(fb_id)

    parsed = self.parse_id(post_id)
    if parsed.post:
      post_id = parsed.post

    with util.ignore_http_4xx_error():
      post = self.urlopen(API_OBJECT % (user_id, post_id))
      resolved = post.get('object_id')
      if resolved:
        logger.info(f'Resolved Facebook post id {post_id!r} to {resolved!r}.')
        return str(resolved)

  def urlopen(self, url, _as=dict, **kwargs):
    """Wraps :func:`urllib2.urlopen()` and passes through the access token.

    Args:
      _as (type): if not None, parses the response as JSON and passes it through
        :meth:`_as` with this type. if None, returns the response object.

    Returns:
      dict: decoded JSON response
    """
    if not url.startswith('http'):
      url = API_BASE + url
    if self.access_token:
      url = util.add_query_params(url, [('access_token', self.access_token)])
    resp = util.urlopen(urllib.request.Request(url, **kwargs))

    if _as is None:
      return resp

    body = resp.read()
    try:
      return self._as(_as, source.load_json(body, url))
    except ValueError:  # couldn't parse JSON
      logger.debug(f'Response: {resp.getcode()} {body}')
      raise

  @staticmethod
  def _as(type, resp):
    """Converts an API response to a specific type.

    If ``resp`` isn't the right type, an empty instance of ``type`` is returned.

    If ``type`` is ``list``, the response is expected to be a ``dict`` with the
    returned list in the ``data`` field. If the response is a list, it's
    returned as is.

    Args:
      type (list or dict)
      resp (dict): parsed JSON object
    """
    assert type in (list, dict)

    if type is list:
      if isinstance(resp, dict):
        resp = resp.get('data', [])
      else:
        logger.warning(f'Expected dict response with `data` field, got {resp}')

    if isinstance(resp, type):
      return resp
    else:
      logger.warning(f'Expected {type} response, got {resp}')
      return type()

  def urlopen_batch(self, urls):
    """Sends a batch of multiple API calls using Facebook's batch API.

    Raises the appropriate :class:`urllib2.HTTPError` if any individual call
    returns HTTP status code 4xx or 5xx.

    https://developers.facebook.com/docs/graph-api/making-multiple-requests

    Args:
      urls (sequence of str): relative API URLs, eg [``me``, ``me/accounts``]

    Returns:
      sequence of dict: responses, either decoded JSON objects (when possible)
      or raw str bodies
    """
    resps = self.urlopen_batch_full([{'relative_url': url} for url in urls])

    bodies = []
    for url, resp in zip(urls, resps):
      code = int(resp.get('code', 0))
      body = resp.get('body')
      if code // 100 in (4, 5):
        raise urllib.error.HTTPError(url, code, body, resp.get('headers'), None)
      bodies.append(body)

    return bodies

  def urlopen_batch_full(self, requests):
    """Sends a batch of multiple API calls using Facebook's batch API.

    Similar to :meth:`urlopen_batch`, but the requests arg and return value are
    dicts with headers, HTTP status code, etc. Raises :class:`urllib2.HTTPError`
    if the outer batch request itself returns an HTTP error.

    https://developers.facebook.com/docs/graph-api/making-multiple-requests

    Args:
      requests (sequence of dict): requests in Facebook's batch format, except
        that headers is a single dict, not a list of dicts, e.g.::

          [{'relative_url': 'me/feed',
            'headers': {'ETag': 'xyz', ...},
           },
           ...
          ]

    Returns:
      sequence of dict: responses in Facebook's batch format, except that body
      is JSON-decoded if possible, and headers is a single dict, not a list of
      dicts, e.g.::

          [{'code': 200,
            'headers': {'ETag': 'xyz', ...},
            'body': {...},
           },
           ...
          ]
    """
    for req in requests:
      if 'method' not in req:
        req['method'] = 'GET'
      if 'headers' in req:
        req['headers'] = [{'name': n, 'value': v}
                          for n, v in sorted(req['headers'].items())]

    data = 'batch=' + json_dumps(util.trim_nulls(requests), sort_keys=True)
    resps = self.urlopen('', data=data, _as=list)

    for resp in resps:
      if 'headers' in resp:
        resp['headers'] = {h['name']: h['value'] for h in resp['headers']}

      body = resp.get('body')
      if body:
        try:
          resp['body'] = json_loads(body)
        except (ValueError, TypeError):
          pass

    return resps
