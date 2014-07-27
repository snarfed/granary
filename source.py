# coding=utf-8
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
import urlparse

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

  def user_url(self, user_id):
    """Returns the URL for a user's profile."""
    raise NotImplementedError()

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

  def create(self, obj, include_link=False):
    """Creates a new object: a post, comment, like, share, or RSVP.

    Subclasses should override this. Different sites will support different
    functionality; check each subclass for details. The actor will usually be
    the authenticated user.

    Args:
      obj: ActivityStreams object. At minimum, must have the content field.
        objectType is strongly recommended.
      include_link: boolean. If True, includes a link to the object
        (if it has one) in the content.

    Returns: dict, possibly empty. If the newly created object has an id or
      permalink, they'll be provided in the values for 'id' and 'url'.

    Raises NotImplementedError if the site doesn't support the object type, and
    other exceptions on other errors.
    """
    raise NotImplementedError()

  def preview_create(self, obj, include_link=False):
    """Previews creating a new object: a post, comment, like, share, or RSVP.

    Returns HTML that previews what create() with the same object will do.

    Subclasses should override this. Different sites will support different
    functionality; check each subclass for details. The actor will usually be
    the authenticated user.

    Args:
      obj: ActivityStreams object. At minimum, must have the content field.
        objectType is strongly recommended.
      include_link: boolean. If True, includes a link to the object
        (if it has one) in the content.

    Returns: unicode string HTML snippet

    Raises NotImplementedError if the site doesn't support the object type, and
    other exceptions on other errors.
    """
    raise NotImplementedError()

  def can_create(self, obj):
    """Sanity-checking whether this source can publish this type of
    object. Attempts to preview the object, catch NotImplementedErrors
    (or better yet DetailedNotImplementedErrors), and report them to
    the user as a helpful error message.

    Args:
      obj: an activitystreams object

    Return:
      a tuple, (boolean, plain text error, html-formatted error)
    """
    try:
      self.preview_create(obj)
      return True, None, None

    except CannotPublishTypeError, e:
      return False, e.plain, e.html

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None):
    """Returns an ActivityStreams comment object.

    Subclasses should override this.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id, optional. Needed for some
        sources (e.g. Facebook) to construct the comment permalink.
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
        if verb == 'invite':
          actor_name = self.actor_name(obj.get('object'))
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

    def article_urls(field):
      return set(util.trim_nulls(a.get('url') for a in obj.get(field, [])
                                 if a.get('objectType') == 'article'))
    attachments = article_urls('attachments')
    tags = article_urls('tags')
    urls = attachments | set(util.extract_links(content))

    # Permashortcitations are short references to canonical copies of a given
    # (usually syndicated) post, of the form (DOMAIN PATH). Details:
    # http://indiewebcamp.com/permashortcitation
    #
    # We consider them an explicit original post link, so we store them in
    # upstreamDuplicates to signal that.
    # http://activitystrea.ms/specs/json/1.0/#id-comparison
    for match in Source._PERMASHORTCITATION_RE.finditer(content):
      http = match.expand(r'http://\1/\2')
      https = match.expand(r'https://\1/\2')
      uds = obj.setdefault('upstreamDuplicates', [])
      if http not in uds and https not in uds:
        uds.append(http)

    obj.setdefault('tags', []).extend(
      {'objectType': 'article', 'url': u} for u in urls
      # heuristic: ellipsized URLs are probably incomplete, so omit them.
      if not u.endswith('...') and not u.endswith(u'…'))
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

    Also, important point: this defaults to true, ie public. Bridgy depends on
    that and prunes the to field from stored activities in Response objects (in
    bridgy/util.prune_activity()). If the default here ever changes, be sure to
    update Bridgy's code.
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
        event.setdefault(field, []).append(rsvp.get(
            'object' if field == 'invited' else 'actor'))

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

  def base_object(self, obj):
    """Returns id and URL of the 'base' silo object that an object operates on.

    For example, if the object is a comment, this returns the post that it's a
    comment on. If it's an RSVP, this returns the event. The id in the returned
    tuple is silo-specific, ie not a tag URI.

    Subclasses may override this.

    Args:
      obj: ActivityStreams object

    Returns: (string id, string URL) tuple. Both may be None.
    """
    # look at in-reply-tos first, then objects (for likes and reposts).
    # technically, the ActivityStreams 'object' field is always supposed to be
    # singular, but microformats2.json_to_object() sometimes returns activities
    # that have a list value, e.g. likes or reposts of multiple objects.
    candidates = []
    for field in ('inReplyTo', 'object'):
      objs = obj.get(field, [])
      if isinstance(objs, dict):
        candidates.append(objs)
      else:
        candidates += objs

    for base_obj in candidates:
      parsed_id = util.parse_tag_uri(base_obj.get('id', ''))
      if parsed_id:
        domain = parsed_id[0]
      else:
        domain = urlparse.urlparse(base_obj.get('url', '')).netloc
      for subdomain in 'www.', 'mobile.':
        if domain.startswith(subdomain):
          domain = domain[len(subdomain):]
      if domain == self.DOMAIN:
        break
    else:
      return (None, None)

    id = base_obj.get('id')
    url = base_obj.get('url')

    if id:
      id = util.parse_tag_uri(id)[1]
    elif url:
      path = urlparse.urlparse(url).path
      if path.endswith('/'):
        path = path[:-1]
      id = path.rsplit('/', 1)[-1]

    return (id, url)

  def _content_for_create(self, obj):
    """Returns the content text to use in create() and preview_create().

    If objectType is note, or it's a comment (or there's an inReplyTo) and the
    original post is on this source, then returns summary if available, then
    content, then displayName.

    Otherwise, returns summary if available, then displayName, then content.

    Args:
      obj: dict, ActivityStreams object

    Returns: string text or None
    """
    type = obj.get('objectType')
    summary = obj.get('summary')
    name = obj.get('displayName')
    content = obj.get('content')
    _, base_url = self.base_object(obj)

    if type == 'note' or (base_url and (type == 'comment' or obj.get('inReplyTo'))):
      ret = summary or content or name
    else:
      ret = summary or name or content
    return ret.strip() if ret else None


class CannotPublishTypeError(BaseException):
  """This indicates the user is trying to publish to a source that
  explicitly does not support it (e.g. RSVPs to Twitter). We can take
  advantage of these specific failures and give the user an informative
  error message.

  This is distinct from NotImplementedError and handled a little
  differently. When a NotImplementedError is caught, publish will
  continue searching the page for an h-entry. CannotPublish, on the
  other hand, means we've hit the item that they intended to publish
  and know that we cannot publish it, so Bridgy will report and error
  and be done.
  """

  def __init__(self, plain, html):
    self.plain = plain
    self.html = html
