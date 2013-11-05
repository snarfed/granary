#!/usr/bin/python
"""Source base class.

Based on the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import datetime

from webutil import util

ME = '@me'
SELF = '@self'
ALL = '@all'
FRIENDS = '@friends'
APP = '@app'

# use this many chars from the beginning of the content in the title field.
TITLE_LENGTH = 140


class Source(object):
  """Abstract base class for a source (e.g. Facebook, Twitter).

  Concrete subclasses must override the class constants below and implement
  get_activities().

  Class constants:
    DOMAIN: string, the source's domain
    NAME: string, the source's human-readable name
    FRONT_PAGE_TEMPLATE: string, the front page child template filename
    AUTH_URL = string, the url for the "Authenticate" front page link
  """

  def get_actor(self, user_id=None):
    """Returns the current user as a JSON ActivityStreams actor dict."""
    raise NotImplementedError()

  def get_activities(self, user_id=None, group_id=None, app_id=None,
                     activity_id=None, start_index=0, count=0):
    """Return a list and total count of ActivityStreams activities.

    If user_id is provided, only that user's activity(s) are included.
    start_index and count determine paging, as described in the spec:
    http://activitystrea.ms/draft-spec.html#anchor14

    app id is just object id
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#appId

    group id is string id of group or @self, @friends, @all
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#Group-ID

    Args:
      user_id: string object id, defaults to the currently authenticated user
      group_id: string object id, defaults to the current user's friends
      app_id: string object id
      activity_id: string object id
      start_index: int >= 0
      count: int >= 0

    Returns:
      (total_results, activities) tuple
      total_results: int or None (e.g. if it can't be calculated efficiently)
      activities: list of activity dicts to be JSON-encoded
    """
    raise NotImplementedError()

  def postprocess_activity(self, activity):
    """Does source-independent post-processing of an activity, in place.

    Right now just populates the title field.

    Args:
      activity: activity dict
    """
    # maps object type to human-readable name to use in title
    TYPE_DISPLAY_NAMES = {'image': 'photo', 'product': 'gift'}

    # maps verb to human-readable verb
    DISPLAY_VERBS = {'like': 'likes', 'listen': 'listened to',
                     'play': 'watched', 'read': 'read', 'give': 'gave'}

    activity = util.trim_nulls(activity)
    content = activity.get('object', {}).get('content')
    actor_name = self.actor_name(activity.get('actor'))
    object = activity.get('object')

    if 'title' not in activity:
      if content:
        activity['title'] = '%s%s%s' % (
          actor_name + ': ' if actor_name else '',
          content[:TITLE_LENGTH],
          '...' if len(content) > TITLE_LENGTH else '')
      elif object:
        app = activity.get('generator', {}).get('displayName')
        obj_name = object.get('displayName')
        obj_type = TYPE_DISPLAY_NAMES.get(object.get('objectType'), 'unknown')
        activity['title'] = '%s %s %s%s.' % (
          actor_name,
          DISPLAY_VERBS.get(activity['verb'], 'posted'),
          obj_name if obj_name else 'a %s' % obj_type,
          ' on %s' % app if app else '')

    return activity

  @staticmethod
  def actor_name(actor):
    """Returns the given actor's name if available, otherwise Unknown."""
    return actor.get('displayName', 'Unknown') if actor else 'Unknown'


  def tag_uri(self, name):
    """Returns a tag URI string for this source and the given string name."""
    return util.tag_uri(self.DOMAIN, name)
