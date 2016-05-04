# coding=utf-8
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
  https://developers.facebook.com/docs/facebook-login/permissions#reference-read_stream

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
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import collections
import copy
import itertools
import json
import logging
import re
import urllib
import urllib2
import urlparse
import mf2util

import appengine_config
from oauth_dropins.webutil import util
import source

# Since API v2.4, we need to explicitly ask for the fields we want from most API
# endpoints with ?fields=...
# https://developers.facebook.com/docs/apps/changelog#v2_4_changes
#   (see the Declarative Fields section)
API_BASE = 'https://graph.facebook.com/v2.6/'
API_COMMENTS_FIELDS = 'id,message,from,created_time,message_tags,parent,attachment'
API_COMMENTS_ALL = 'comments?filter=stream&ids=%s&fields=' + API_COMMENTS_FIELDS
API_COMMENT = '%s?fields=' + API_COMMENTS_FIELDS
# Ideally this fields arg would just be [default fields plus comments], but
# there's no way to ask for that. :/
# https://developers.facebook.com/docs/graph-api/using-graph-api/v2.1#fields
#
# asking for too many fields here causes 500s with either "unknown error" or
# "ask for less info" errors. https://github.com/snarfed/bridgy/issues/664
API_EVENT_FIELDS = 'id,attending,declined,description,end_time,interested,maybe,noreply,name,owner,picture,place,start_time,timezone,updated_time'
API_EVENT = '%s?fields=' + API_EVENT_FIELDS
# /user/home requires the read_stream permission, which you probably don't have.
# details in the file docstring.
# https://developers.facebook.com/docs/graph-api/reference/user/home
# https://github.com/snarfed/granary/issues/26
API_HOME = '%s/home?offset=%d'
API_PHOTOS_UPLOADED = 'me/photos?type=uploaded&fields=id,album,comments,created_time,from,images,likes,link,name,name_tags,object_id,page_story_id,picture,privacy,reactions,shares,updated_time'
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
API_NEWS_PUBLISHES = 'me/news.publishes?fields=' + API_POST_FIELDS
API_PUBLISH_POST = 'me/feed'
API_PUBLISH_COMMENT = '%s/comments'
API_PUBLISH_LIKE = '%s/likes'
API_PUBLISH_PHOTO = 'me/photos'
# the docs say these can't be published to, but they actually can. ¯\_(ツ)_/¯
# https://developers.facebook.com/docs/graph-api/reference/event/attending/#Creating
API_PUBLISH_ALBUM_PHOTO = '%s/photos'
API_PUBLISH_RSVP_ATTENDING = '%s/attending'
API_PUBLISH_RSVP_MAYBE = '%s/maybe'
API_PUBLISH_RSVP_INTERESTED = '%s/interested'
API_PUBLISH_RSVP_DECLINED = '%s/declined'
API_NOTIFICATION = '%s/notifications'

# endpoint for uploading video. note the graph-video subdomain.
# https://developers.facebook.com/docs/graph-api/video-uploads
API_UPLOAD_VIDEO = 'https://graph-video.facebook.com/v2.6/me/videos'

MAX_IDS = 50  # for the ids query param

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
  'rsvp-interested': API_PUBLISH_RSVP_INTERESTED,
}
REACTION_CONTENT = {
  'LOVE': u'❤️',
  'WOW': u'😮',
  'HAHA': u'😆',
  'SAD': u'😢',
  'ANGRY': u'😡',
  # nothing for LIKE (it's a like :P) or for NONE
}

FacebookId = collections.namedtuple('FacebookId', ['user', 'post', 'comment'])


class Facebook(source.Source):
  """Implements the ActivityStreams API for Facebook.
  """

  DOMAIN = 'facebook.com'
  BASE_URL = 'https://www.facebook.com/'
  NAME = 'Facebook'
  FRONT_PAGE_TEMPLATE = 'templates/facebook_index.html'

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
    return self.user_to_actor(self.urlopen(user_id))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              fetch_news=False, event_owner_id=None, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details.

    Likes, *top-level* replies (ie comments), and reactions are always included.
    They come from the 'comments', 'likes', and 'reactions' fields in the Graph
    API's Post object:
    https://developers.facebook.com/docs/reference/api/post/

    Threaded comments, ie comments in reply to other top-level comments, require
    an additional API call, so they're only included if fetch_replies is True.

    Mentions are never fetched or included because the API doesn't support
    searching for them.
    https://github.com/snarfed/bridgy/issues/523#issuecomment-155523875

    Additional args:
      fetch_news: boolean, whether to also fetch and include Open Graph news
        stories (/USER/news.publishes). Requires the user_actions.news
        permission. Background in https://github.com/snarfed/bridgy/issues/479
      event_owner_id: string. if provided, only events owned by this user id
        will be returned. avoids (but doesn't entirely prevent) processing big
        non-indieweb events with tons of attendees that put us over app engine's
        instance memory limit. https://github.com/snarfed/bridgy/issues/77
    """
    if search_query:
      raise NotImplementedError()

    activities = []

    if activity_id:
      if not user_id:
        if '_' not in activity_id:
          raise NotImplementedError(
            'Facebook activity ids must be of the form USERID_POSTID')
        user_id, activity_id = activity_id.split('_', 1)
      post = self.urlopen(API_OBJECT % (user_id, activity_id))
      if post.get('error'):
        logging.warning("Couldn't fetch object %s: %s", activity_id, post)
        posts = []
      else:
        posts = [post]

    else:
      url = API_SELF_POSTS if group_id == source.SELF else API_HOME
      url = url % (user_id if user_id else 'me', start_index)
      if count:
        url = util.add_query_params(url, {'limit': count})
      headers = {'If-None-Match': etag} if etag else {}
      try:
        resp = self.urlopen(url, headers=headers, _as=None)
        etag = resp.info().get('ETag')
        posts = self._as(list, json.loads(resp.read()))
      except urllib2.HTTPError, e:
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
          posts.extend(self.urlopen(API_NEWS_PUBLISHES, _as=list))
        posts = self._merge_photos(posts)
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

  def _merge_photos(self, posts):
    """Fetches and merges photo objects into posts, replacing matching posts.

    Have to fetch uploaded photos manually since facebook sometimes collapses
    multiple photos into consolidated posts. Also, photo objects don't have the
    privacy field, so we get that from the corresponding post or album, if
    possible.

    https://github.com/snarfed/bridgy/issues/562
    http://stackoverflow.com/questions/12785120

    Populates a custom 'object_for_ids' field in the FB photo objects. This is
    later copied into a custom 'fb_object_for_ids' field in their corresponding
    AS objects.

    Args:
      posts: list of Facebook post object dicts

    Returns: new list of post and photo object dicts
    """
    posts_by_obj_id = {}
    for post in posts:
      obj_id = post.get('object_id')
      if obj_id:
        existing = posts_by_obj_id.get(obj_id)
        if existing:
          logging.warning('merging posts for object_id %s: overwriting %s with %s!',
                          obj_id, existing.get('id'), post.get('id'))
        posts_by_obj_id[obj_id] = post

    albums = None  # lazy loaded, maps facebook id to ActivityStreams object

    photos = self.urlopen(API_PHOTOS_UPLOADED, _as=list)
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
          albums = {a['id']: a for a in self.urlopen(API_ALBUMS % 'me', _as=list)}
        photo['privacy'] = albums.get(album_id, {}).get('privacy')
      else:
        photo['privacy'] = 'custom'  # ie unknown

    return ([p for p in posts if not p.get('object_id')] +
            posts_by_obj_id.values() + photos)

  def _split_id_requests(self, api_call, ids):
    """Splits an API call into multiple to stay under the MAX_IDS limit per call.

    https://developers.facebook.com/docs/graph-api/using-graph-api#multiidlookup

    Args:
      api_call: string with %s placeholder for ids query param
      ids: sequence of string ids

    Returns: merged list of objects from the responses' 'data' fields
    """
    results = {}
    for i in range(0, len(ids), MAX_IDS):
      resp = self.urlopen(api_call % ','.join(ids[i:i + MAX_IDS]))
      for id, objs in resp.items():
        # objs is usually a dict but sometimes a boolean. (oh FB, never change!)
        results.setdefault(id, []).extend(self._as(dict, objs).get('data', []))

    return results

  def _get_events(self, owner_id=None):
    """Fetches the current user's events.

    https://developers.facebook.com/docs/graph-api/reference/user/events/
    https://developers.facebook.com/docs/graph-api/reference/event#edges

    TODO: also fetch and use API_USER_EVENTS_DECLINED, API_USER_EVENTS_NOT_REPLIED

    Args:
      owner_id: string. if provided, only returns events owned by this user

    Returns:
      list of ActivityStreams event objects
    """
    events = self.urlopen(API_USER_EVENTS, _as=list)
    return [self.event_to_activity(event) for event in events
            if not owner_id or owner_id == event.get('owner', {}).get('id')]

  def get_event(self, event_id, owner_id=None):
    """Returns a Facebook event post.

    Args:
      id: string, site-specific event id
      owner_id: string

    Returns: dict, decoded ActivityStreams activity, or None if the event is not
      found or is owned by a different user than owner_id (if provided)
    """
    event = None
    with util.ignore_http_4xx_error():
      event = self.urlopen(API_EVENT % event_id)

    if not event or event.get('error'):
      logging.warning("Couldn't fetch event %s: %s", event_id, event)
      return None

    event_owner_id = event.get('owner', {}).get('id')
    if owner_id and event_owner_id != owner_id:
      logging.info('Ignoring event %s owned by user id %s instead of %s',
                   event.get('name') or event.get('id'), event_owner_id, owner_id)
      return None

    return self.event_to_activity(event)

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id, optional
      activity: activity object (optional)
    """
    try:
      resp = self.urlopen(API_COMMENT % comment_id)
    except urllib2.HTTPError, e:
      if e.code == 400 and '_' in comment_id:
        # Facebook may want us to ask for this without the other prefixed id(s)
        resp = self.urlopen(API_COMMENT % comment_id.split('_')[-1])
      else:
        raise

    return self.comment_to_object(resp, post_author_id=activity_author_id)

  def get_share(self, activity_user_id, activity_id, share_id, activity=None):
    """Returns an ActivityStreams share activity object.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object
      activity: activity object (optional)
    """
    orig_id = '%s_%s' % (activity_user_id, activity_id)

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
      user_id: string id or username. Defaults to 'me', ie the current user.

    Returns:
      sequence of ActivityStream album object dicts
    """
    url = API_ALBUMS % (user_id if user_id is not None else 'me')
    return [self.album_to_object(a) for a in self.urlopen(url, _as=list)]

  def get_reaction(self, activity_user_id, activity_id, reaction_user_id,
                   reaction_id, activity=None):
    """Fetches and returns a reaction.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      reaction_user_id: string id of the user who reacted
      reaction_id: string id of the reaction. one of:
        'love', 'wow', 'haha', 'sad', 'angry'
      activity: activity object (optional)
    """
    if '_' not in reaction_id:  # handle just name of reaction type
      reaction_id = '%s_%s_by_%s' % (activity_id, reaction_id, reaction_user_id)
    return super(Facebook, self).get_reaction(
      activity_user_id, activity_id, reaction_user_id, reaction_id, activity=activity)

  def create(self, obj, include_link=source.OMIT_LINK,
             ignore_formatting=False):
    """Creates a new post, comment, like, or RSVP.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose contents will be a dict with 'id' and
      'url' keys for the newly created Facebook object (or None)
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Previews creating a new post, comment, like, or RSVP.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose contents will be a unicode string HTML snippet
      or None
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates a new post, comment, like, or RSVP.

    https://developers.facebook.com/docs/graph-api/reference/user/feed#publish
    https://developers.facebook.com/docs/graph-api/reference/object/comments#publish
    https://developers.facebook.com/docs/graph-api/reference/object/likes#publish
    https://developers.facebook.com/docs/graph-api/reference/event#attending

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: string
      ignore_formatting: boolean

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
    base_type = base_obj.get('objectType')
    base_url = base_obj.get('url')
    if base_id and not base_url:
      base_url = base_obj['url'] = self.object_url(base_id)

    video_url = util.get_first(obj, 'stream', {}).get('url')
    image_url = util.get_first(obj, 'image', {}).get('url')
    content = self._content_for_create(obj, ignore_formatting=ignore_formatting,
                                       strip_first_video_tag=bool(video_url))

    if not content and not (video_url or image_url):
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
      content += '\n\n(Originally published at: %s)' % url
    preview_content = util.linkify(content)
    if video_url:
      preview_content += ('<br /><br /><video controls src="%s"><a href="%s">'
                          'this video</a></video>' % (video_url, video_url))
    elif image_url:
      preview_content += '<br /><br /><img src="%s" />' % image_url
    if people:
      preview_content += '<br /><br /><em>with %s</em>' % ', '.join(
        '<a href="%s">%s</a>' % (
          tag.get('url'), tag.get('displayName') or 'User %s' % tag['id'])
        for tag in people)
    msg_data = {'message': content.encode('utf-8')}
    if appengine_config.DEBUG:
      msg_data['privacy'] = json.dumps({'value': 'SELF'})

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
        desc = """\
<span class="verb">comment</span> on <a href="%s">this post</a>:
<br /><br />%s<br />""" % (base_url, self.embed_post(base_obj))
        return source.creation_result(content=preview_content, description=desc)
      else:
        if image_url:
          msg_data['attachment_url'] = image_url
        resp = self.urlopen(API_PUBLISH_COMMENT % base_id,
                            data=urllib.urlencode(msg_data))
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
          desc += '<a href="%s">this comment</a>:\n<br /><br />%s%s<br />' % (
            base_url, author, comment.get('content'))
        else:
          desc += '<a href="%s">this post</a>:\n<br /><br />%s<br />' % (
            base_url, self.embed_post(base_obj))
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

      # TODO: event invites
      if preview:
        assert verb.startswith('rsvp-')
        desc = ('<span class="verb">RSVP %s</span> to <a href="%s">this event</a>.' %
                (verb[5:], base_url))
        return source.creation_result(description=desc)
      else:
        resp = self.urlopen(RSVP_PUBLISH_ENDPOINTS[verb] % base_id, data='')
        assert resp.get('success'), resp
        resp = {'type': 'rsvp'}

    elif type in ('note', 'article'):
      if preview:
        return source.creation_result(content=preview_content,
                                      description='<span class="verb">post</span>:')
      else:
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
            msg_data['tags'] = json.dumps([{'tag_uid': tag['id']} for tag in people])
        else:
          api_call = API_PUBLISH_POST
          if people:
            # tags is comma-separated user id string
            # https://developers.facebook.com/docs/graph-api/reference/user/feed#pubfields
            msg_data['tags'] = ','.join(tag['id'] for tag in people)

        resp = self.urlopen(api_call, data=urllib.urlencode(msg_data))
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
        error_plain='Cannot publish type=%s, verb=%s to Facebook' % (type, verb),
        error_html='Cannot publish type=%s, verb=%s to Facebook' % (type, verb))

    if 'url' not in resp:
      resp['url'] = base_url
    return source.creation_result(resp)

  def _get_person_tags(self, obj):
    """Extracts and prepares person tags for Facebook users.

    Args:
      obj: ActivityStreams object

    Returns: sequence of ActivityStreams tag objects with url, id, and optional
      displayName fields. The id field is a raw Facebook user id.
    """
    people = {}  # maps id to tag

    for tag in obj.get('tags', []):
      url = tag.get('url', '')
      id = url.split('/')[-1]
      if (util.domain_from_link(url) == 'facebook.com' and util.is_int(id) and
          tag.get('objectType') == 'person' and
          not tag.get('startIndex')):  # mentions are linkified separately
        tag = copy.copy(tag)
        tag['id'] = id
        people[id] = tag

    return people.values()

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
    url = API_BASE + API_NOTIFICATION % user_id
    resp = util.urlopen(urllib2.Request(url, data=urllib.urlencode(params)))
    logging.debug('Response: %s %s', resp.getcode(), resp.read())

  def post_url(self, post):
    """Returns a short Facebook URL for a post.

    Args:
      post: Facebook JSON post
    """
    fb_id = post.get('id')
    if not fb_id:
      return None

    id = self.parse_id(fb_id)
    author_id = id.user or post.get('from', {}).get('id')
    if author_id and id.post:
      return 'https://www.facebook.com/%s/posts/%s' % (author_id, id.post)

    return self.object_url(fb_id)

  def comment_url(self, post_id, comment_id, post_author_id=None):
    """Returns a short Facebook URL for a comment.

    Args:
      post_id: Facebook post id
      comment_id: Facebook comment id
    """
    if post_author_id:
      post_id = post_author_id + '/posts/' + post_id
    return 'https://www.facebook.com/%s?comment_id=%s' % (post_id, comment_id)

  def base_object(self, obj, verb=None, resolve_numeric_id=False):
    """Returns the 'base' silo object that an object operates on.

    This is mostly a big bag of heuristics for reverse engineering and
    parsing Facebook URLs. Whee.

    Args:
      obj: ActivityStreams object
      verb: string, optional
      resolve_numeric_id: if True, tries harder to populate the numeric_id field
        by making an additional API call to look up the object if necessary.

    Returns: dict, minimal ActivityStreams object. Usually has at least id,
      numeric_id, and url fields; may also have author.
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
      parsed = urlparse.urlparse(url)
      params = urlparse.parse_qs(parsed.query)
      assert parsed.path.startswith('/')
      path = parsed.path.strip('/')
      path_parts = path.split('/')

      if len(path_parts) == 1:
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

      # photo URLs look like:
      # https://www.facebook.com/photo.php?fbid=123&set=a.4.5.6&type=1
      # https://www.facebook.com/user/photos/a.12.34.56/78/?type=1&offset=0
      if path == 'photo.php':
        fbids = params.get('fbid')
        if fbids:
          base_obj['id'] = fbids[0]

      # photo album URLs look like this:
      # https://www.facebook.com/media/set/?set=a.12.34.56
      # c.f. http://stackoverflow.com/questions/18549744
      elif path == 'media/set':
        set_id = params.get('set')
        if set_id and set_id[0].startswith('a.'):
          base_obj['id'] = set_id[0].split('.')[1]

      comment_id = params.get('comment_id') or params.get('reply_comment_id')
      if comment_id:
        base_obj['id'] += '_' + comment_id[0]
        base_obj['objectType'] = 'comment'

      if '_' not in base_id and author.get('numeric_id'):
        # add author user id prefix. https://github.com/snarfed/bridgy/issues/229
        base_obj['id'] = '%s_%s' % (author['numeric_id'], base_id)

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
    obj = self.post_to_object(post)
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

  def post_to_object(self, post, is_comment=False):
    """Converts a post to an object.

    TODO: handle the sharedposts field

    Args:
      post: dict, a decoded JSON post
      is_comment: True if post is actually a comment

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    assert is_comment in (True, False)

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
      link = 'https://www.facebook.com' + link

    if gift:
      object_type = 'product'
    if not object_type:
      if picture and not message:
        object_type = 'image'
      else:
        object_type = 'note'

    id = self.parse_id(fb_id, is_comment=is_comment)
    if is_comment and not id.comment:
      return {}
    elif not is_comment and not id.post:
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
      'to': self.privacy_to_to(post),
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
      'id': '%s_liked_by_%s' % (obj['id'], like.get('id')),
      'url': url + '#liked-by-%s' % like.get('id'),
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
          'id': '%s_%s_by_%s' % (obj['id'], type, id),
          'url': url + '#%s-by-%s' % (type, id),
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
    elif link and not gift:
      att['objectType'] = 'article'
      obj['attachments'] = [att]

    # location
    place = post.get('place')
    if place:
      place_id = place.get('id')
      obj['location'] = {
        'displayName': place.get('name'),
        'id': place_id,
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
      comment: dict, a decoded JSON comment
      post_id: optional string Facebook post id. Only used if the comment id
        doesn't have an embedded post id.
      post_author_id: optional string Facebook post author id. Only used if the
        comment id doesn't have an embedded post author id.

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    obj = self.post_to_object(comment, is_comment=True)
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
        'id': self.tag_uri('%s_%s' % (post_id, id.comment)),
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
    if att and att.get('type') == 'photo' and not obj.get('image'):
      obj['image'] = {'url': att.get('media', {}).get('image', {}).get('src')}
      obj.setdefault('attachments', []).append({
        'objectType': 'image',
        'image': obj['image'],
        'url': att.get('url'),
      })

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

    return self.postprocess_object(obj)

  def user_to_actor(self, user):
    """Converts a user or page to an actor.

    Args:
      user: dict, a decoded JSON Facebook user or page

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
    actor = {
      # FB only returns the type field if you fetch the object with ?metadata=1
      # https://developers.facebook.com/docs/graph-api/using-graph-api#introspection
      'objectType': 'page' if user.get('type') == 'page' else 'person',
      'displayName': user.get('name') or username,
      'id': self.tag_uri(handle),
      'updated': util.maybe_iso8601_to_rfc3339(user.get('updated_time')),
      'username': username,
      'description': user.get('bio') or user.get('description'),
      'summary': user.get('about'),
      }

    # numeric_id is our own custom field that always has the source's numeric
    # user id, if available.
    if util.is_int(id):
      actor.update({
        'numeric_id': id,
        'image': {
          'url': '%s%s/picture?type=large' % (API_BASE, id),
        },
      })

    # extract web site links. extract_links uniquifies and preserves order
    urls = (sum((util.extract_links(user.get(field)) for field in
                ('website', 'about', 'bio', 'description')),
                []) or
            util.extract_links(user.get('link')) or
            [self.user_url(handle)])
    if urls:
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

    if rsvps:
      self.add_rsvps_to_event(
        obj, [self.rsvp_to_object(r, event=event) for r in rsvps])

    # de-dupe the event's RSVPs by (user) id. RSVP_FIELDS is ordered by
    # precedence, so iterate in reverse order so higher precedence fields
    # override.
    id_to_rsvp = {}
    for field in reversed(RSVP_FIELDS):
      for rsvp in event.get(field, {}).get('data', []):
        rsvp = self.rsvp_to_object(rsvp, type=field, event=event)
        id_to_rsvp[rsvp['id']] = rsvp
    self.add_rsvps_to_event(obj, id_to_rsvp.values())

    return self.postprocess_object(obj)

  def event_to_activity(self, event, rsvps=None):
    """Converts a event to an activity.

    Args:
      event: dict, a decoded JSON Facebook event
      rsvps: list of JSON Facebook RSVPs

    Returns: an ActivityStreams activity dict
    """
    obj = self.event_to_object(event, rsvps=rsvps)
    return {'object': obj,
            'id': obj.get('id'),
            'url': obj.get('url'),
            }

  def rsvp_to_object(self, rsvp, type=None, event=None):
    """Converts an RSVP to an object.

    The 'id' field will ony be filled in if event['id'] is provided.

    Args:
      rsvp: dict, a decoded JSON Facebook RSVP
      type: optional Facebook RSVP type, one of RSVP_FIELDS
      event: Facebook event object. May contain only a single 'id' element.

    Returns:
      an ActivityStreams object dict
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
        obj['id'] = self.tag_uri('%s_rsvp_%s' % (event_id, user_id))
        obj['url'] = '%s#%s' % (self.object_url(event_id), user_id)

    return self.postprocess_object(obj)

  def album_to_object(self, album):
    """Converts a photo album to an object.

    Args:
      album: dict, a decoded JSON Facebook album

    Returns:
      an ActivityStreams object dict
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

  @staticmethod
  def privacy_to_to(obj):
    """Converts a Facebook `privacy` field to an ActivityStreams `to` field.

    privacy is sometimes an object:
    https://developers.facebook.com/docs/graph-api/reference/post#fields

    ...and other times a string:
    https://developers.facebook.com/docs/graph-api/reference/album/#readfields

    Args:
      obj: dict, Facebook object (post, album, comment, etc)

    Returns:
      dict (ActivityStreams `to` object) or None if unknown
    """
    privacy = obj.get('privacy')
    if isinstance(privacy, dict):
      privacy = privacy.get('value')

    if obj.get('status_type') == 'wall_post' and not privacy:
      # privacy value '' means it doesn't have an explicit audience set, so it
      # inherits the defaults privacy setting for wherever it was posted: a
      # group, a page, a user's timeline, etc. unfortunately we haven't found a
      # way to get that default setting via the API. so just omit it for at
      # least some known post types like this. background:
      # https://github.com/snarfed/bridgy/issues/559#issuecomment-159642227
      return [{'objectType': 'unknown'}]
    elif privacy and privacy.lower() == 'custom':
      return [{'objectType': 'unknown'}]
    elif privacy is not None:
      public = privacy.lower() in ('', 'everyone', 'open')
      return [{'objectType': 'group', 'alias': '@public' if public else '@private'}]

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
'''})}))

      # resp = appengine_config.read('fql.json')
      results = {q['name']: q['fql_result_set'] for q in resp['data']}
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

  @staticmethod
  def parse_id(id, is_comment=False):
    """Parses a Facebook post or comment id.

    Facebook ids come in different formats:
    * Simple number, usually a user or post: 12
    * Two numbers with underscore, usually POST_COMMENT or USER_POST: 12_34
    * Three numbers with underscores, USER_POST_COMMENT: 12_34_56
    * Three numbers with colons, USER:POST:SHARD: 12:34:63
      (We're guessing that the third part is a shard in some FB internal system.
      In our experience so far, it's always either 63 or the app-scoped user id
      for 63.)
    * Two numbers with colon, POST:SHARD: 12:34
      (We've seen 0 as shard in this format.)
    * Four numbers with colons/underscore, USER:POST:SHARD_COMMENT: 12:34:63_56
    * Five numbers with colons/underscore, USER:EVENT:UNKNOWN:UNKNOWN_UNKNOWN
      Not currently supported! Examples:
111599105530674:998145346924699:10102446236688861:10207188792305341_998153510257216
111599105530674:195181727490727:10102446236688861:10205257726909910_195198790822354

    Background:
    * https://github.com/snarfed/bridgy/issues/305
    * https://developers.facebook.com/bugs/786903278061433/

    Args:
      id: string or integer
      is_comment: boolean

    Returns: FacebookId. Some or all fields may be None.
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
      logging.error('Cowardly refusing Facebook id with unknown format: %s', id)

    return fbid

  def resolve_object_id(self, user_id, post_id, activity=None):
    """Resolve a post id to its Facebook object id, if any.

    Used for photo posts, since Facebook has (at least) two different objects
    (and ids) for them, one for the post and one for each photo.

    This is the same logic that we do for canonicalizing photo objects in
    get_activities() above.

    If activity is not provided, fetches the post from Facebook.

    Args:
      user_id: string Facebook user id who posted the post
      post_id: string Facebook post id
      activity: optional AS activity representation of Facebook post

    Returns: string Facebook object id or None
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
        logging.info('Resolved Facebook post id %r to %r.', post_id, resolved)
        return str(resolved)

  def urlopen(self, url, _as=dict, **kwargs):
    """Wraps urllib2.urlopen() and passes through the access token.

    Args:
      _as: if not None, parses the response as JSON and passes it through _as()
           with this type. if None, returns the response object.

    Returns: decoded JSON object or urlopen response object
    """
    if not url.startswith('http'):
      url = API_BASE + url
    log_url = url
    if self.access_token:
      url = util.add_query_params(url, [('access_token', self.access_token)])
    resp = util.urlopen(urllib2.Request(url, **kwargs))

    if _as is None:
      return resp

    body = resp.read()
    try:
      return self._as(_as, json.loads(body))
    except ValueError:  # couldn't parse JSON
      logging.debug('Response: %s %s', resp.getcode(), body)
      raise

  @staticmethod
  def _as(type, resp):
    """Converts an API response to a specific type.

    If resp isn't the right type, an empty instance of type is returned.

    If type is list, the response is expected to be a dict with the returned
    list in the 'data' field. If the response is a list, it's returned as is.

    Args:
      type: list or dict
      resp: parsed JSON object
    """
    assert type in (list, dict)

    if type is list:
      if isinstance(resp, dict):
        resp = resp.get('data', [])
      else:
        logging.warning('Expected dict response with `data` field, got %s', resp)

    if isinstance(resp, type):
      return resp
    else:
      logging.warning('Expected %s response, got %s', type, resp)
      return type()

  def urlopen_batch(self, urls):
    """Sends a batch of multiple API calls using Facebook's batch API.

    Raises the appropriate urllib2.HTTPError if any individual call returns HTTP
    status code 4xx or 5xx.

    https://developers.facebook.com/docs/graph-api/making-multiple-requests

    Args:
      urls: sequence of string relative API URLs, e.g. ('me', 'me/accounts')

    Returns: sequence of responses, either decoded JSON objects (when possible)
      or raw string bodies

    """
    resps = self.urlopen_batch_full([{'relative_url': url} for url in urls])

    bodies = []
    for url, resp in zip(urls, resps):
      code = int(resp.get('code', 0))
      body = resp.get('body')
      if code / 100 in (4, 5):
        raise urllib2.HTTPError(url, code, body, resp.get('headers'), None)
      bodies.append(body)

    return bodies

  def urlopen_batch_full(self, requests):
    """Sends a batch of multiple API calls using Facebook's batch API.

    Similar to urlopen_batch(), but the requests arg and return value are dicts
    with headers, HTTP status code, etc. Only raises urllib2.HTTPError if the
    outer batch request itself returns an HTTP error.

    https://developers.facebook.com/docs/graph-api/making-multiple-requests

    Args:
      requests: sequence of dict requests in Facebook's batch format, except
      that headers is a single dict, not a list of dicts.

        [{'relative_url': 'me/feed',
          'headers': {'ETag': 'xyz', ...},
         },
         ...
        ]

    Returns: sequence of dict responses in Facebook's batch format, except that
      body is JSON-decoded if possible, and headers is a single dict, not a list
      of dicts.

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
                          for n, v in req['headers'].items()]

    data = 'batch=' + json.dumps(util.trim_nulls(requests),
                                 separators=(',', ':'))  # no whitespace
    resps = self.urlopen('', data=data, _as=list)

    for resp in resps:
      if 'headers' in resp:
        resp['headers'] = {h['name']: h['value'] for h in resp['headers']}

      body = resp.get('body')
      if body:
        try:
          resp['body'] = json.loads(body)
        except (ValueError, TypeError):
          pass

    return resps
