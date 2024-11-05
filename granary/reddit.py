"""Reddit source class.

Not thread safe!

Reddit API docs:

* https://github.com/reddit-archive/reddit/wiki/API
* https://www.reddit.com/dev/api
* https://www.reddit.com/prefs/apps

PRAW API docs:
https://praw.readthedocs.io/
"""
import logging
import threading
import urllib.parse

from cachetools import cachedmethod, TTLCache
from oauth_dropins import reddit
from oauth_dropins.webutil import util
import praw
from prawcore.exceptions import NotFound

from . import source

logger = logging.getLogger(__name__)

USER_CACHE_TIME = 5 * 60  # 5 minute expiration, in seconds
user_cache = TTLCache(1000, USER_CACHE_TIME)
user_cache_lock = threading.RLock()


class Reddit(source.Source):
  """Reddit source class. See file docstring and :class:`source.Source` for details."""

  DOMAIN = 'reddit.com'
  BASE_URL = 'https://reddit.com'
  NAME = 'Reddit'
  OPTIMIZED_COMMENTS = True

  def __init__(self, refresh_token):
    self.api = praw.Reddit(
      client_id=reddit.REDDIT_APP_KEY,
      client_secret=reddit.REDDIT_APP_SECRET,
      refresh_token=refresh_token,
      user_agent=util.user_agent,
      # https://praw.readthedocs.io/en/stable/getting_started/configuration/options.html#basic-configuration-options
      check_for_updates=False)
    self.api.read_only = True

  @classmethod
  def post_id(self, url):
    """Guesses the post id of the given URL.

    Args:
      url (str)

    Returns:
      str or None:
    """
    path_parts = urllib.parse.urlparse(url).path.rstrip('/').split('/')
    if len(path_parts) >= 2:
      return path_parts[-2]

  @cachedmethod(lambda self: user_cache, lock=lambda self: user_cache_lock,
                key=lambda self, user: getattr(user, 'name', None))
  def praw_to_as1_actor(self, praw_user):
    """Converts a PRAW Redditor to an actor.

    Makes external calls to fetch data from the Reddit API.

    https://praw.readthedocs.io/en/latest/code_overview/models/redditor.html

    Caches fetched user data for 5m to avoid repeating user profile API requests
    when fetching multiple comments or posts from the same author. Background:
    https://github.com/snarfed/bridgy/issues/1021

    Ideally this would be part of PRAW, but they seem uninterested:

    * https://github.com/praw-dev/praw/issues/131
    * https://github.com/praw-dev/praw/issues/1140

    Args:
      user (praw.models.Redditor)

    Returns:
      dict: ActivityStreams actor
    """
    try:
      user = reddit.praw_to_user(praw_user)
    except NotFound:
      logger.debug(f'User not found: {praw_user} {repr(praw_user)}', exc_info=True)
      return {}

    return self.to_as1_actor(user)

  praw_to_actor = praw_to_as1_actor
  """Deprecated! Use :meth:`praw_to_as1_actor` instead."""

  def to_as1_actor(self, user):
    """Converts a dict user to an actor.

    Args:
      user (dict): Reddit user

    Returns:
      dict: ActivityStreams actor
    """
    username = user.get('name')
    if not username:
      return {}

    # trying my best to grab all the urls from the profile description
    urls = [f'{self.BASE_URL}/user/{username}/']
    description = None

    subreddit = user.get('subreddit')
    if subreddit:
      url = subreddit.get('url')
      if url:
        urls.append(self.BASE_URL + url)
      description = subreddit.get('description')
      urls += util.trim_nulls(util.extract_links(description))

    image = user.get('icon_img')

    return util.trim_nulls({
      'objectType': 'person',
      'displayName': username,
      'image': {'url': image},
      'id': self.tag_uri(username),
      # numeric_id is our own custom field that always has the source's numeric
      # user id, if available.
      'numeric_id': user.get('id'),
      'published': util.maybe_timestamp_to_iso8601(user.get('created_utc')),
      'url': urls[0],
      'urls': [{'value': u} for u in urls] if len(urls) > 1 else None,
      'username': username,
      'description': description,
    })

  user_to_actor = to_as1_actor
  """Deprecated! Use :meth:`to_as1_actor` instead."""

  def to_as1_object(self, thing, type):
    """Converts a PRAW object to an AS1 object.

    Currently only returns public content.

    Note that this will make external API calls to lazily load some attributes.

    Args:
      thing (praw.models.Submission or praw.models.Comment)
      type (str): either ``submission`` or ``comment``, which content to get

    Returns:
      dict: ActivityStreams object
      """
    id = getattr(thing, 'id', None)
    if not id:
      return {}

    published = util.maybe_timestamp_to_iso8601(getattr(thing, 'created_utc', None))
    obj = {
      'id': self.tag_uri(id),
      'url': self.BASE_URL + thing.permalink,
      'published': published,
      'to': [{
        'objectType': 'group',
        'alias': '@public',
      }],
    }

    user = getattr(thing, 'author', None)
    if user:
      obj['author'] = self.praw_to_as1_actor(user)

    if type == 'submission':
      content = getattr(thing, 'selftext', None)
      obj.update({
        'displayName': getattr(thing, 'title', None),
        'content': content,
        'objectType': 'note',
        'tags': [{
          'objectType': 'article',
          'url': t,
          'displayName': t,
        } for t in util.extract_links(content)],
      })

      url = getattr(thing, 'url', None)
      if url:
        obj.update({
          'objectType': 'bookmark',
          'targetUrl': url,
        })

    elif type == 'comment':
      obj.update({
        'content': getattr(thing, 'body_html', None),
        'objectType': 'comment',
      })
      reply_to = thing.parent()
      if reply_to:
        obj['inReplyTo'] = [{
          'id': self.tag_uri(getattr(reply_to, 'id', None)),
          'url': self.BASE_URL + getattr(reply_to, 'permalink', None),
        }]

    return self.postprocess_object(obj)

  praw_to_object = to_as1_object
  """Deprecated! Use :meth:`to_as1_object` instead."""

  def to_as1_activity(self, thing, type):
    """Converts a PRAW submission or comment to an activity.

    Note that this will make external API calls to lazily load some attributes.

    * https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
    * https://praw.readthedocs.io/en/latest/code_overview/models/comment.html

    Args:
      thing (praw.models.Submission or praw.models.Comment)
      type (str): whether to get submission or comment content

    Returns:
      dict: ActivityStreams activity
    """
    obj = self.praw_to_object(thing, type)
    if not obj:
      return {}

    activity = {
      'verb': 'post',
      'id': obj['id'],
      'url': self.BASE_URL + getattr(thing, 'permalink', None),
      'actor': obj.get('author'),
      'object': obj,
    }
    return self.postprocess_activity(activity)

  praw_to_activity = to_as1_activity
  """Deprecated! Use :meth:`to_as1_activity` instead."""

  def _fetch_replies(self, activities, cache=None):
    """Fetches and injects comments into a list of activities, in place.

    Only includes top level comments!

    Args:
      activities (list of dict)
      cache (dict): cache as described in :meth:`Source.get_activities_response`
    """
    for activity in activities:
      id = util.parse_tag_uri(activity.get('id'))[1]
      subm = self.api.submission(id=id)

      cache_key = f'ARR {id}'
      if cache and cache.get(cache_key) == subm.num_comments:
        continue

      # for v0 we will use just the top level comments because threading is hard.
      # feature request: https://github.com/snarfed/bridgy/issues/1014
      subm.comments.replace_more()
      replies = [self.praw_to_activity(top_level_comment, 'comment')
                 for top_level_comment in subm.comments]
      items = [r.get('object') for r in replies]
      activity['object']['replies'] = {
        'items': items,
        'totalItems': len(items),
      }
      if cache is not None:
        cache[cache_key] = subm.num_comments

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=None,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None, **kwargs):
    """Fetches submissions and ActivityStreams activities.

    Currently only implements ``activity_id``, ``search_query`` and
    ``fetch_replies``.
    """
    if activity_id:
      submissions = [self.api.submission(id=activity_id)]
    elif search_query:
      submissions = self.api.subreddit('all').search(search_query, sort='new', limit=count)
    else:
      submissions = self._redditor(user_id).submissions.new(limit=count)

    activities = [self.praw_to_activity(s, 'submission') for s in submissions]

    if fetch_replies:
      self._fetch_replies(activities, cache=cache)

    return self.make_activities_base_response(activities)

  def get_actor(self, user_id=None):
    """Fetches a Reddit user and converts them to an AS1 actor.

    Args:
      user_id (str)

    Returns
      dict: AS1 actor, or ``{}`` if the user isn't found
    """
    return self.praw_to_as1_actor(self._redditor(user_id=user_id))

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id (str): comment id
      activity_id (str): activity id; ignored!
      activity_author_id (str): activity author id; ignored!
      activity (dict): activity object; ignored!

    Returns:
      dict: ActivityStreams object
    """
    return self.praw_to_object(self.api.comment(id=comment_id), 'comment')

  def user_url(self, username):
    """Returns the Reddit URL for a given user."""
    return f'https://{self.DOMAIN}/user/{username}'

  def _redditor(self, user_id=None):
    """Returns the Redditor for a given user id."""
    # Oddly user.me() returns None when in read only mode
    # https://praw.readthedocs.io/en/stable/code_overview/reddit/user.html#praw.models.User.me
    self.api.read_only = False
    r = self.api.redditor(user_id) if user_id else self.api.user.me()
    self.api.read_only = True
    return r
