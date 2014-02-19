#!/usr/bin/python
"""Source base class.

Based on the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service

Uses the 'to' field of the Audience Targeting extension to indicate an
activity's privacy settings. It's set to a group with alias @public or @private,
or unset if unknown.
http://activitystrea.ms/specs/json/targeting/1.0/#anchor3
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import datetime
import itertools
import logging
import re

from oauth_dropins.webutil import util

ME = '@me'
SELF = '@self'
ALL = '@all'
FRIENDS = '@friends'
APP = '@app'

RSVP_TO_EVENT = {
  'rsvp-yes': 'attending',
  'rsvp-no': 'notAttending',
  'rsvp-maybe': 'maybeAttending',
  'invite': 'invited',
  }
RSVP_CONTENTS = {
  'rsvp-yes': 'is attending.',
  'rsvp-no': 'is not attending.',
  'rsvp-maybe': 'might attend.',
  'invite': 'is invited.',
  }


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

  def get_activities(self, *args, **kwargs):
    """Fetches and returns a list of ActivityStreams activities.

    See get_activities_response() for args and kwargs.

    Returns:
      list of ActivityStreams activity dicts
    """
    return self.get_activities_response(*args, **kwargs)['items']

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False):
    """Fetches and returns ActivityStreams activities and response details.

    Subclasses should override this. See get_activities() for an alternative
    that just returns the list of activities.

    If user_id is provided, only that user's activity(s) are included.
    start_index and count determine paging, as described in the spec:
    http://activitystrea.ms/draft-spec.html#anchor14

    app id is just object id
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#appId

    group id is string id of group or @self, @friends, @all
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#Group-ID

    The fetch_* kwargs all default to False because they often require extra API
    round trips. Some sources return replies, likes, and shares in the same
    initial call, so they may be included even if you don't set their kwarg to
    True.

    Args:
      user_id: string, defaults to the currently authenticated user
      group_id: string, one of '@self', '@all', '@friends'. defaults to
        'friends'
      app_id: string
      activity_id: string
      start_index: int >= 0
      count: int >= 0
      etag: string, optional ETag to send with the API request. Results will
        only be returned if the ETag has changed. Should include enclosing
        double quotes, e.g. '"ABC123"'
      min_id: only return activities with ids greater than this
      cache: object with get(key), set_multi(dict), and delete_multi(list)
        methods. In practice, this is App Engine's memcache interface:
        https://developers.google.com/appengine/docs/python/memcache/functions
        Used to cache data that's expensive to regenerate, e.g. API calls.
      fetch_replies: boolean, whether to fetch each activity's replies also
      fetch_likes: boolean, whether to fetch each activity's likes also
      fetch_shares: boolean, whether to fetch each activity's shares also
      fetch_events: boolean, whether to fetch the user's events also

    Returns:
      response dict with values based on OpenSocial ActivityStreams REST API:
        http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service
        http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-Data.xml

      It has these keys:
        items: list of activity dicts
        startIndex: int or None
        itemsPerPage: int
        totalResults: int or None (e.g. if it can 't be calculated efficiently)
        filtered: False
        sorted: False
        updatedSince: False
        etag: string etag returned by the API's initial call to get activities
    """
    raise NotImplementedError()

  def _make_activities_base_response(self, activities, *args, **kwargs):
    """Generates a base response dict for get_activities_response().

    See get_activities() for args and kwargs.
    """
    return {'startIndex': kwargs.get('start_index', 0),
            'itemsPerPage': len(activities),
            'totalResults': None if kwargs.get('activity_id') else len(activities),
            # TODO: this is just for compatibility with
            # http://activitystreamstester.appspot.com/
            # the OpenSocial spec says to use entry instead, so switch back
            # to that eventually
            'items': activities,
            'filtered': False,
            'sorted': False,
            'updatedSince': False,
            }

  def get_comment(self, comment_id, activity_id=None):
    """Returns an ActivityStreams comment object.

    Subclasses should override this.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
    """
    raise NotImplementedError()

  def get_like(self, activity_user_id, activity_id, like_user_id):
    """Returns an ActivityStreams 'like' activity object.

    Default implementation that fetches the activity and its likes, then
    searches for a like by the given user. Subclasses should override this if
    they can optimize the process.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      like_user_id: string id of the user who liked the activity
    """
    activities = self.get_activities(user_id=activity_user_id,
                                     activity_id=activity_id,
                                     fetch_likes=True)
    return self._get_tag(activities, 'like', like_user_id)

  def get_share(self, activity_user_id, activity_id, share_id):
    """Returns an ActivityStreams 'share' activity object.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object or the user who shared it
    """
    activities = self.get_activities(user_id=activity_user_id,
                                     activity_id=activity_id,
                                     fetch_shares=True)
    return self._get_tag(activities, 'share', share_id)

  def get_rsvp(self, activity_user_id, event_id, user_id):
    """Returns an ActivityStreams 'rsvp-*' activity object.

    Args:
      activity_user_id: string id of the user who posted the original activity
      event_id: string event id
      user_id: string id of the user who RSVPed
    """
    raise NotImplementedError()

  def _get_tag(self, activities, verb, user_id):
    if not activities:
      return None

    user_tag_id = self.tag_uri(user_id)
    for tag in activities[0].get('object', {}).get('tags', []):
      author = tag.get('author', {})
      if (tag.get('verb') == verb and
          (author.get('id') == user_tag_id or author.get('numeric_id') == user_id)):
        return tag

  def _fetch_like(self, activity):
    """Fetches and injects likes into an activity, in place.

    Subclasses should usually override.

    Args:
      activities: ActivityStreams activity dict

    Returns: same activity dict
    """
    return activity

  def _fetch_share(self, activity):
    """Fetches and injects shares into an activity, in place.

    Subclasses should usually override.

    Args:
      activities: ActivityStreams activity dict

    Returns: same activity dict
    """
    return activity

  def postprocess_activity(self, activity):
    """Does source-independent post-processing of an activity, in place.

    Right now just populates the title field.

    Args:
      activity: activity dict
    """
    activity = util.trim_nulls(activity)
    # maps object type to human-readable name to use in title
    TYPE_DISPLAY_NAMES = {'image': 'photo', 'product': 'gift'}

    # maps verb to human-readable verb
    DISPLAY_VERBS = {'like': 'likes', 'listen': 'listened to',
                     'play': 'watched', 'read': 'read', 'give': 'gave'}

    actor_name = self.actor_name(activity.get('actor'))
    obj = activity.get('object')

    if obj and not activity.get('title'):
      verb = DISPLAY_VERBS.get(activity['verb'])
      obj_name = obj.get('displayName')
      if obj_name and not verb:
        activity['title'] = obj_name
      else:
        app = activity.get('generator', {}).get('displayName')
        obj_type = TYPE_DISPLAY_NAMES.get(obj.get('objectType'), 'unknown')
        name = obj_name if obj_name else 'a %s' % obj_type
        app = ' on %s' % app if app else ''
        activity['title'] = '%s %s %s%s.' % (actor_name, verb or 'posted',
                                             name, app)

    return util.trim_nulls(activity)

  def postprocess_object(self, obj):
    """Does source-independent post-processing of an object, in place.

    Right now just populates the displayName field.

    Args:
      object: object dict
    """
    verb = obj.get('verb')
    content = obj.get('content')
    rsvp_content = RSVP_CONTENTS.get(verb)

    if rsvp_content and not content:
      if verb.startswith('rsvp-'):
        content = obj['content'] = '<data class="p-rsvp" value="%s">%s</data>' % (
          verb.split('-')[1], rsvp_content)
      else:
        content = obj['content'] = rsvp_content

    if content and not obj.get('displayName'):
      actor_name = self.actor_name(obj.get('author') or obj.get('actor'))
      if verb in ('like', 'share'):
        obj['displayName'] = '%s %s' % (actor_name, content)
      elif rsvp_content:
        obj['displayName'] = '%s %s' % (actor_name, rsvp_content)
      else:
        obj['displayName'] = util.ellipsize(content)

    return util.trim_nulls(obj)

  _PERMASHORTCITATION_RE = re.compile(r'\(([^:\s)]+\.[^\s)]{2,})[ /]([^\s)]+)\)$')

  @staticmethod
  def original_post_discovery(activity):
    """Discovers original post links and stores them as tags, in place.

    This is a variation on http://indiewebcamp.com/original-post-discovery . It
    differs in that it finds multiple candidate links instead of one, and it
    doesn't bother looking for MF2 (etc) markup because the silos don't let you
    input it.

    Args:
      activity: activity dict
    """
    obj = activity.get('object') or activity
    content = obj.get('content', '').strip()

    # Permashortcitations are short references to canonical copies of a given
    # (usually syndicated) post, of the form (DOMAIN PATH). Details:
    # http://indiewebcamp.com/permashortcitation
    pscs =  set(match.expand(r'http://\1/\2')
                for match in Source._PERMASHORTCITATION_RE.finditer(content))

    attachments = set(a.get('url') for a in obj.get('attachments', [])
                      if a['objectType'] == 'article')
    urls = util.trim_nulls(util.extract_links(content) | attachments | pscs)
    obj.setdefault('tags', []).extend({'objectType': 'article', 'url': u}
                                      for u in urls)

    return activity

  @staticmethod
  def actor_name(actor):
    """Returns the given actor's name if available, otherwise Unknown."""
    if actor:
      return actor.get('displayName') or actor.get('username') or 'Unknown'
    return 'Unknown'

  @staticmethod
  def is_public(obj):
    """Returns True if the activity or object is public or unspecified.

    ...according to the Audience Targeting extension
    https://developers.google.com/+/api/latest/activities/list#collection

    Expects values generated by this library: objectType group, alias @public or
    @private.
    """
    to = obj.get('to')
    if not to:
      to = obj.get('object', {}).get('to')
    if not to:
      return True  # unset
    return '@public' in set(t.get('alias') for t in to)


  @staticmethod
  def add_rsvps_to_event(event, rsvps):
    """Adds RSVP objects to an event's *attending fields, in place.

    Args:
      event: ActivityStreams event object
      rsvps: sequence of ActivityStreams RSVP activity objects
    """
    for rsvp in rsvps:
      field = RSVP_TO_EVENT.get(rsvp.get('verb'))
      if field:
        event.setdefault(field, []).append(rsvp.get('actor'))

  @staticmethod
  def get_rsvps_from_event(event):
    """Returns RSVP objects for an event's *attending fields.

    Args:
      event: ActivityStreams event object

    Returns: sequence of ActivityStreams RSVP activity objects
    """
    id = event.get('id')
    if not id:
      return []
    parsed = util.parse_tag_uri(id)
    if not parsed:
      return []
    domain, event_id = parsed

    rsvps = []
    for verb, field in RSVP_TO_EVENT.items():
      for actor in event.get(field, []):
        rsvp = {'objectType': 'activity',
                'verb': verb,
                'actor': actor,
                }
        if event_id and 'id' in actor:
          _, actor_id = util.parse_tag_uri(actor['id'])
          rsvp['id'] = util.tag_uri(domain, '%s_rsvp_%s' % (event_id, actor_id))
        rsvps.append(rsvp)

    return rsvps

  def tag_uri(self, name):
    """Returns a tag URI string for this source and the given string name."""
    return util.tag_uri(self.DOMAIN, name)
