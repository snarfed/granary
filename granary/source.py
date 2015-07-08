# coding=utf-8
"""Source base class.

Based on the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service

Uses the 'to' field of the Audience Targeting extension to indicate an
activity's privacy settings. It's set to a group with alias @public or @private,
or unset if unknown.
http://activitystrea.ms/specs/json/targeting/1.0/#anchor3
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import collections
import copy
import logging
import re
import urlparse

from oauth_dropins.webutil import util

ME = '@me'
SELF = '@self'
ALL = '@all'
FRIENDS = '@friends'
APP = '@app'
SEARCH = '@search'

RSVP_TO_EVENT = {
  'rsvp-yes': 'attending',
  'rsvp-no': 'notAttending',
  'rsvp-maybe': 'maybeAttending',
  'invite': 'invited',
  }

# maps lower case string short name to Source subclass. populated by SourceMeta.
sources = {}

CreationResult = collections.namedtuple('CreationResult', [
  'content', 'description', 'abort', 'error_plain', 'error_html'])


def creation_result(content=None, description=None, abort=False,
                    error_plain=None, error_html=None):
  """Create a new CreationResult named tuple, which the result of
  create() and preview_create() to provides a detailed description of
  publishing failures. If abort is False, we should continue looking
  for an entry to publish; if True, we should immediately inform the
  user. error_plain text is sent in response to failed publish
  webmentions; error_html will be displayed to the user when
  publishing interactively.

  Args:
    content: a string HTML snippet for preview_create() or a dict for create()
    description: string HTML snippet describing the publish action, e.g.
      '@-reply' or 'RSVP yes to this event'. The verb itself is surrounded by a
      <span class="verb"> to allow styling. May also include <a> link(s) and
      embedded silo post(s).
    abort: a boolean
    error_plain: a string
    error_html: a string

  Return:
    a CreationResult named tuple
  """
  return CreationResult(content, description, abort, error_plain, error_html)


def object_type(obj):
  """Returns the object type, or the verb if it's an activity object.

  Details: http://activitystrea.ms/specs/json/1.0/#activity-object

  Args:
    obj: decoded JSON ActivityStreams object

  Returns: string, ActivityStreams object type
  """
  type = obj.get('objectType')
  return type if type and type != 'activity' else obj.get('verb')


class SourceMeta(type):
  """Source metaclass. Registers all source classes in the sources global."""
  def __new__(meta, name, bases, class_dict):
    cls = type.__new__(meta, name, bases, class_dict)
    name = getattr(cls, 'NAME', None)
    if name:
      sources[name.lower()] = cls
    return cls


class Source(object):
  """Abstract base class for a source (e.g. Facebook, Twitter).

  Concrete subclasses must override the class constants below and implement
  get_activities().

  Class constants:
    DOMAIN: string, the source's domain
    NAME: string, the source's human-readable name
    FRONT_PAGE_TEMPLATE: string, the front page child template filename
    AUTH_URL: string, the url for the "Authenticate" front page link
    EMBED_POST: string, the HTML for embedding a post. Should have a %(url)s
      placeholder for the post URL and (optionally) a %(content)s placeholder
      for the post content.
  """
  __metaclass__ = SourceMeta

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
      search_query: string, an optional search query, only for use with
         @search group_id

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

    Returns:
      a CreationResult, whose contents will be a dict

      The dict may be None or empty. If the newly created
      object has an id or permalink, they'll be provided in the values
      for 'id' and 'url'.
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

    Returns:
      a CreationResult, whose contents will be a unicode string
      HTML snippet (or None)
    """
    raise NotImplementedError()

  def get_event(self, event_id):
    """Returns a ActivityStreams event activity.

    Args:
      id: string, site-specific event id

    Returns: dict, decoded ActivityStreams activity, or None
    """
    raise NotImplementedError()

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

  def user_to_actor(self, user):
    """Converts a user to an actor.

    The returned object will have at least a 'url' field. If the user has
    multiple URLs, there will also be a 'urls' list field whose elements are
    dicts with 'value': URL.

    Args:
      user: dict, a decoded JSON Facebook user

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
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
    DISPLAY_VERBS = {
      'give': 'gave',
      'like': 'likes',
      'listen': 'listened to',
      'play': 'watched',
      'read': 'read',
      'share': 'shared',
    }

    actor_name = self.actor_name(activity.get('actor'))
    obj = activity.get('object')

    if obj and not activity.get('title'):
      verb = DISPLAY_VERBS.get(activity['verb'])
      obj_name = obj.get('displayName')
      obj_type = TYPE_DISPLAY_NAMES.get(obj.get('objectType'))
      if obj_name and not verb:
        activity['title'] = obj_name
      elif verb and (obj_name or obj_type):
        app = activity.get('generator', {}).get('displayName')
        name = obj_name if obj_name else 'a %s' % (obj_type or 'unknown')
        app = ' on %s' % app if app else ''
        activity['title'] = '%s %s %s%s.' % (actor_name, verb or 'posted',
                                             name, app)

    return util.trim_nulls(activity)

  def postprocess_object(self, obj):
    """Does source-independent post-processing of an object, in place.

    * populates location.position based on latitude and longitude

    Args:
      object: object dict
    """
    loc = obj.get('location')
    if loc:
      lat = loc.get('latitude')
      lon = loc.get('longitude')
      if lat and lon and not loc.get('position'):
        # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
        loc['position'] = '%+f%+f/' % (lat, lon)

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
      if (http not in uds and https not in uds
          # heuristic: ellipsized URLs are probably incomplete, so omit them.
          and not http.endswith('...') and not http.endswith(u'…')):
        uds.append(http)

    obj.setdefault('tags', []).extend(
      {'objectType': 'article', 'url': u} for u in urls
      # same heuristic from above
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
    url = event.get('url')

    rsvps = []
    for verb, field in RSVP_TO_EVENT.items():
      for actor in event.get(field, []):
        rsvp = {'objectType': 'activity',
                'verb': verb,
                'actor': actor,
                'url': url,
                }
        if event_id and 'id' in actor:
          _, actor_id = util.parse_tag_uri(actor['id'])
          rsvp['id'] = util.tag_uri(domain, '%s_rsvp_%s' % (event_id, actor_id))
          if url:
            rsvp['url'] = '#'.join((url, actor_id))
        rsvps.append(rsvp)

    return rsvps

  @staticmethod
  def activity_changed(before, after, log=False):
    """Returns whether two activities or objects differ meaningfully.

    Only compares a few fields: object type, verb, content, location, and image.
    Notably does *not* compare author and published/updated timestamps.

    This has been tested on Facebook posts, comments, and event RSVPs (only
    content and rsvp_status change) and Google+ posts and comments (content,
    updated, and etag change). Twitter tweets and Instagram photo captions and
    comments can't be edited.

    Args:
      before, after: dicts, ActivityStreams activities or objects

    Returns: boolean

    """
    def changed(b, a, field, label):
      b_val = b.get(field)
      a_val = a.get(field)
      if b_val != a_val:
        if log:
          logging.debug('%s[%s] %s => %s', label, field, b_val, a_val)
        return True

    obj_b = before.get('object', {})
    obj_a = after.get('object', {})
    return any(changed(before, after, field, 'activity') or
               changed(obj_b, obj_a, field, 'activity[object]')
               for field in ('objectType', 'verb', 'to', 'content', 'location',
                             'image'))

  @classmethod
  def embed_post(cls, obj):
    """Returns the HTML string for embedding a post object."""
    obj = copy.copy(obj)
    for field in 'url', 'content':
      if field not in obj:
        obj.setdefault(field, obj.get('object', {}).get(field, ''))
    return cls.EMBED_POST % obj

  @classmethod
  def embed_actor(cls, actor):
    return """
<a class="h-card" href="%s">
 <img class="profile u-photo" src="%s" width="32px" /> %s</a>""" % (
   actor.get('url'),
   actor.get('image', {}).get('url'),
   actor.get('displayName'))

  def tag_uri(self, name):
    """Returns a tag URI string for this source and the given string name."""
    return util.tag_uri(self.DOMAIN, name)

  def base_object(self, obj):
    """Returns the 'base' silo object that an object operates on.

    For example, if the object is a comment, this returns the post that it's a
    comment on. If it's an RSVP, this returns the event. The id in the returned
    object is silo-specific, ie not a tag URI.

    Subclasses may override this.

    Args:
      obj: ActivityStreams object

    Returns: dict, minimal ActivityStreams object. Usually has at least id; may
      also have url, author, etc.
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
        domain = util.domain_from_link(base_obj.get('url', ''))
      if domain == self.DOMAIN:
        break
    else:
      return {}

    base_obj = copy.deepcopy(base_obj)
    id = base_obj.get('id')
    url = base_obj.get('url')

    if id:
      parsed = util.parse_tag_uri(id)
      if parsed:
        base_obj['id'] = parsed[1]
    elif url:
      path = urlparse.urlparse(url).path
      base_obj['id'] = path.rstrip('/').rsplit('/', 1)[-1]

    return base_obj

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
    summary = obj.get('summary')
    name = obj.get('displayName')
    content = obj.get('content')

    ret = summary or content or name
    return ret.strip() if ret else None
