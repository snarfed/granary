# coding=utf-8
"""reddit.com source class.
"""

from . import source
import logging
from oauth_dropins import reddit
from oauth_dropins.webutil import appengine_info, util
import re
import urllib.parse, urllib.request

import praw

if appengine_info.DEBUG:
  REDDIT_APP_KEY = util.read('reddit_app_key_local')
  REDDIT_APP_SECRET = util.read('reddit_app_secret_local')
else:
  REDDIT_APP_KEY = util.read('reddit_app_key')
  REDDIT_APP_SECRET = util.read('reddit_app_secret')


def get_reddit_api(refresh_token):
  return praw.Reddit(client_id=REDDIT_APP_KEY,
             client_secret=REDDIT_APP_SECRET,
             refresh_token=refresh_token,
             user_agent='oauth-dropin reddit api')


class Reddit(source.Source):

  DOMAIN = 'reddit.com'
  BASE_URL = 'https://reddit.com'
  NAME = 'reddit'

  def __init__(self, refresh_token):
    self.refresh_token = refresh_token

  def user_to_actor(self, user):
    """Converts a praw Redditor to an actor.
    https://praw.readthedocs.io/en/latest/code_overview/models/redditor.html

    Args:
      user: praw Redditor object

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    username = user.name
    if not username:
      return {}


    # trying my best to grab all the urls from the profile description

    description = ''
    if user.subreddit:
      user_url = self.BASE_URL + user.subreddit.get('url')
      urls = [user_url]
      description = user.subreddit['public_description']
      profile_urls = util.extract_links(description)
      urls += util.trim_nulls(profile_urls)
    else:
      urls = [self.BASE_URL + '/user/' + username]

    image = user.icon_img

    return util.trim_nulls({
      'objectType': 'person',
      'displayName': username,
      'image': {'url': image},
      'id': self.tag_uri(username),
      # numeric_id is our own custom field that always has the source's numeric
      # user id, if available.
      'numeric_id': user.id,
      'published': util.maybe_timestamp_to_iso8601(user.created_utc),
      'url': urls[0],
      'urls': [{'value': u} for u in urls] if len(urls) > 1 else None,
      'username': username,
      'description': description,
      })


  def praw_to_object(self, thing, type):
    """
    Converts a praw object to an object.

    Args:
      thng: a praw object, Sumbission or Comment
      type: string to denote whether to get submission or comment content

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
      """
    obj = {}

    # always prefer id_str over id to avoid any chance of integer overflow.
    # usually shouldn't matter in Python, but still.
    id = thing.id
    if not id:
      return {}

    published = util.maybe_timestamp_to_iso8601(thing.created_utc)

    obj = {
      'id': self.tag_uri(id),
      'objectType': 'note',
      'published': published,
      'to': [],
      }

    user = thing.author
    if user:
      obj['author'] = self.user_to_actor(user)
      username = obj['author'].get('username')

    obj['to'].append({
      'objectType': 'group',
      'alias': '@public',
      })

    obj['url'] = self.BASE_URL + thing.permalink

    if type == 'submission':
      obj['content'] = thing.title
    elif type == 'comment':
      obj['content'] = thing.body

    return self.postprocess_object(obj)


  def praw_to_activity(self, thing, type):
    """Converts a praw submission or comment to an activity.
    https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
    https://praw.readthedocs.io/en/latest/code_overview/models/comment.html

    Args:
      thng: a praw object, Sumbission or Comment
      type: string to denote whether to get submission or comment content

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    obj = self.praw_to_object(thing, type)
    actor = obj['author']

    activity = {
      'verb': 'post',
      'id': thing.id,
      'url': self.BASE_URL + thing.permalink,
      'actor': actor,
      'object': obj
      }

    return self.postprocess_activity(activity)

  def fetch_replies(self, r, activities):
    """Fetches and injects reddit comments into a list of activities, in place.

    limitations: Only includes top level comments
    Args:
      r: praw api object for querying submissions in activities
      activities: list of activity dicts

    Returns:
      same activities list
    """
    for activity in activities:
      subm = r.submission(id=activity['id'])

      # for v0 we will use just the top level comments because threading is hard
      subm.comments.replace_more()
      replies = []
      for top_level_comment in subm.comments:
        replies.append(self.praw_to_activity(top_level_comment, 'comment'))

      items = [r['object'] for r in replies]
      activity['object']['replies'] = {
        'items': items,
        'totalItems': len(items),
        }

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                activity_id=None, start_index=0, count=0,
                etag=None, min_id=None, cache=None,
                fetch_replies=False, fetch_likes=False,
                fetch_shares=False, fetch_events=False,
                fetch_mentions=False, search_query=None, **kwargs):
    """
    Fetches reddit submissions and ActivityStreams activities.

    Currently only implements activity_id, search_query and fetch_replies
    """

    activities = []

    r = get_reddit_api(self.refresh_token)
    r.read_only = True

    if activity_id:
      subm = r.submission(id=activity_id)
      activities.append(self.praw_to_activity(subm, 'submission'))

    if search_query:
      sr = r.subreddit("all")
      subms = sr.search(search_query)
      activities.extend([self.praw_to_activity(subm, 'submission') for subm in subms])

    if fetch_replies:
      self.fetch_replies(r, activities)

    return self.make_activities_base_response(activities)

