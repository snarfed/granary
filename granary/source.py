"""Source base class.

Based on the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service

Uses the ``to`` field of the Audience Targeting extension to indicate an
activity's privacy settings. It's set to a group with alias ``@public`` or
``@private``, or unset if unknown.
http://activitystrea.ms/specs/json/targeting/1.0/#anchor3
"""
import collections
import copy
from html import escape, unescape
import logging
import re
import urllib.parse

import brevity
from bs4 import BeautifulSoup
import html2text
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads

from . import as1

logger = logging.getLogger(__name__)

APP = '@app'
ME = '@me'
SELF = '@self'
ALL = '@all'
FRIENDS = '@friends'
SEARCH = '@search'
BLOCKS = '@blocks'
GROUPS = (ME, SELF, ALL, FRIENDS, SEARCH, BLOCKS)

# values for create's include_link param
OMIT_LINK = 'omit'
INCLUDE_LINK = 'include'
INCLUDE_IF_TRUNCATED = 'if truncated'
HTML_ENTITY_RE = re.compile(r'&#?[a-zA-Z0-9]+;')

# maps lower case string short name to Source subclass. populated by SourceMeta.
sources = {}

CreationResult = collections.namedtuple('CreationResult', [
  'content', 'description', 'abort', 'error_plain', 'error_html'])
"""Result of creating a new object in a silo.

  :meth:`create` and :meth:`preview_create` use this to provide a detailed
  description of publishing failures. If ``abort`` is False, we should continue
  looking for an entry to publish; if True, we should immediately inform the
  user. ``error_plain`` text is sent in response to failed publish webmentions;
  ``error_html`` will be displayed to the user when publishing interactively.

  Attributes:
    content (str or dict): str HTML snippet for :meth:`preview_create`, dict for
      :meth:`create`
    description (str): HTML snippet describing the publish action, e.g.
      ``@-reply`` or ``RSVP yes to this event``. The verb itself is surrounded by a
      ``<span class="verb">`` to allow styling. May also include ``<a>`` link(s) and
      embedded silo post(s).
    abort (bool)
    error_plain (str)
    error_html (str)
"""

class RateLimited(BaseException):
  """Raised when an API rate limits us, and we may have a partial result.

  Attributes:
    partial: the partial result, if any. Usually a list.
  """
  def __init__(self, *args, **kwargs):
    self.partial = kwargs.pop('partial', None)
    super(RateLimited, self).__init__(*args, **kwargs)


def html_to_text(html, baseurl='', **kwargs):
  """Converts HTML to plain text with html2text.

  Args:
    html (str): input HTML content
    baseurl (str): base URL to use when resolving relative URLs. Passed through
      to ``HTML2Text``.
    kwargs: html2text options:
      https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options

  Returns:
    str: converted plain text
  """
  if not html:
    return ''

  h = html2text.HTML2Text(baseurl=baseurl)
  h.unicode_snob = True
  h.body_width = 0  # don't wrap lines
  h.ignore_links = True
  h.use_automatic_links = False
  h.ignore_images = True
  for key, val in kwargs.items():
    setattr(h, key, val)

  # hacky monkey patch fix for html2text escaping sequences that are
  # significant in markdown syntax. the X\\Y replacement depends on knowledge
  # of html2text's internals, specifically that it replaces RE_MD_*_MATCHER
  # with \1\\\2. :(:(:(
  html2text.config.RE_MD_DOT_MATCHER = \
    html2text.config.RE_MD_PLUS_MATCHER = \
    html2text.config.RE_MD_DASH_MATCHER = \
      re.compile(r'(X)\\(Y)')

  return '\n'.join(
    # strip trailing whitespace that html2text adds to ends of some lines
    line.rstrip() for line in unescape(h.handle(html)).splitlines())


def load_json(body, url):
  """Utility method to parse a JSON string. Raises HTTPError 502 on failure."""
  try:
    return json_loads(body)
  except (ValueError, TypeError):
    msg = f'Non-JSON response! Returning synthetic HTTP 502.\n{body}'
    logger.error(msg)
    raise urllib.error.HTTPError(url, 502, msg, {}, None)


def creation_result(content=None, description=None, abort=False,
                    error_plain=None, error_html=None):
  """Creates a new :class:`CreationResult`."""
  return CreationResult(content, description, abort, error_plain, error_html)


class SourceMeta(type):
  """Source metaclass. Registers all source classes in the sources global."""
  def __new__(meta, name, bases, class_dict):
    cls = type.__new__(meta, name, bases, class_dict)
    name = getattr(cls, 'NAME', None)
    if name:
      sources[name.lower()] = cls
    return cls


class Source(object, metaclass=SourceMeta):
  """Abstract base class for a source (e.g. Facebook, Twitter).

  Concrete subclasses must override the class constants below and implement
  :meth:`get_activities`.

  Attributes:
    DOMAIN (str): the source's domain
    BASE_URL (str): optional, the source's base url
    NAME (str): the source's human-readable name
    FRONT_PAGE_TEMPLATE (str): the front page child template filename
    AUTH_URL (str): the url for the "Authenticate" front page link
    EMBED_POST (str): the HTML for embedding a post. Should have a ``%(url)s``
      placeholder for the post URL and optionally a ``%(content)s`` placeholder
      for the post content.
    POST_ID_RE (str): regexp, optional, matches valid post ids. Used in
      :meth:`post_id`.
    HTML2TEXT_OPTIONS (dict): maps str html2text option names to values.
      https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options
    TRUNCATE_TEXT_LENGTH (int): optional character limit to truncate to.
        Defaults to Twitter's limit, 280 characters as of 2019-10-12.
    TRUNCATE_URL_LENGTH (int): optional number of characters that URLs count
        for. Defaults to Twitter's, 23 as of 2019-10-12.
    OPTIMIZED_COMMENTS (bool): whether :meth:`get_comment` is optimized and
      only fetches the requested comment. If False, :meth:`get_comment` fetches
      many or all of the post's comments to find the requested one.
  """
  POST_ID_RE = None
  HTML2TEXT_OPTIONS = {}
  TRUNCATE_TEXT_LENGTH = None
  TRUNCATE_URL_LENGTH = None
  OPTIMIZED_COMMENTS = False

  def user_url(self, user_id):
    """Returns the URL for a user's profile."""
    raise NotImplementedError()

  def get_actor(self, user_id=None):
    """Fetches and returns a user.

    Args:
      user_id (str): defaults to current user

    Returns:
      dict: ActivityStreams actor
    """
    raise NotImplementedError()

  def get_activities(self, *args, **kwargs):
    """Fetches and returns a list of activities.

    See :meth:`get_activities_response` for args and kwargs.

    Returns:
      list of dict: ActivityStreams activities
    """
    return self.get_activities_response(*args, **kwargs)['items']

  def get_activities_response(
      self, user_id=None, group_id=None, app_id=None, activity_id=None,
      start_index=0, count=0, etag=None, min_id=None, cache=None,
      fetch_replies=False, fetch_likes=False, fetch_shares=False,
      include_shares=True, fetch_events=False, fetch_mentions=False,
      search_query=None, scrape=False, **kwargs):
    """Fetches and returns ActivityStreams activities and response details.

    Subclasses should override this. See :meth:`get_activities` for an
    alternative that just returns the list of activities.

    If user_id is provided, only that user's activity(s) are included.
    start_index and count determine paging, as described in the spec:
    http://activitystrea.ms/draft-spec.html#anchor14

    app id is just object id:
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#appId

    group id is string id of group or @self, @friends, @all, @search:
    http://opensocial-resources.googlecode.com/svn/spec/2.0/Social-Data.xml#Group-ID

    The ``fetch_*`` kwargs all default to False because they often require extra
    API round trips. Some sources return replies, likes, and shares in the same
    initial call, so they may be included even if you don't set their kwarg to
    True.

    Args:
      user_id (str): defaults to the currently authenticated user
      group_id (str): one of ``@self``, ``@all``, ``@friends``, ``@search``. defaults
        to ``@friends``
      app_id (str):
      activity_id (str):
      start_index (int): >= 0
      count (int): >= 0
      etag (str): optional ETag to send with the API request. Results will
        only be returned if the ETag has changed. Should include enclosing
        double quotes, e.g. ``"ABC123"``
      min_id (only): return activities with ids greater than this
      cache (dict): optional, used to cache metadata like comment and like counts
        per activity across calls. Used to skip expensive API calls that haven't
        changed.
      fetch_replies (bool): whether to fetch each activity's replies also
      fetch_likes (bool): whether to fetch each activity's likes also
      include_shares (bool): whether to include share activities
      fetch_shares (bool): whether to fetch each activity's shares also
      fetch_events (bool): whether to fetch the user's events also
      fetch_mentions (bool): whether to fetch posts that mention the user
      search_query (str): an optional search query, only for use with
        @search group_id
      scrape (bool): whether to scrape activities from HTML (etc) instead of
        using an API. Not supported by all sources.
      kwargs: some subclasses accept extra kwargs. See their docs for details.

    Returns:
      dict: Response values based on OpenSocial ActivityStreams REST API.

      * http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service
      * http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-Data.xml

      The returned dict has at least these keys:

      * ``items`` (list of dict): activities
      * ``startIndex`` (int or None)
      * ``itemsPerPage`` (int)
      * ``totalResults`` (int or None, eg if it can't be calculated efficiently)
      * ``filtered``: False
      * ``sorted``: False
      * ``updatedSince``: False
      * ``etag`` (str): ETag returned by the API's initial call to get activities

    Raises:
      ValueError: if any argument is invalid for this source
      NotImplementedError: if the source doesn't support the requested
        operation, eg Facebook doesn't support search.
    """
    raise NotImplementedError()

  @classmethod
  def make_activities_base_response(cls, activities, *args, **kwargs):
    """Generates a base response dict for :meth:`get_activities_response`.

    See :meth:`get_activities` for args and kwargs.
    """
    activities = list(activities)
    return {
      'startIndex': kwargs.get('start_index', 0),
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

  def scraped_to_activities(self, scraped, count=None, fetch_extras=False,
                            cookie=None):
    """Converts scraped HTML (or JSON, etc) to AS activities.

    Used for scraping data from the web instead of using an API. Useful for
    sources with APIs that are restricted or have difficult approval processes.

    Args:
      scraped (str): scraped data from a feed of posts
      count (int): number of activities to return, None for all
      fetch_extras: whether to make extra HTTP fetches to get likes, etc.
      cookie (str): optional cookie to be used for subsequent HTTP
        fetches, if necessary.

    Returns:
      (list of dict, dict) tuple: ([AS activities], AS logged in actor (ie viewer))
    """
    raise NotImplementedError()

  def scraped_to_activity(self, scraped):
    """Converts scraped HTML (or JSON, etc) to a single AS activity.

    Used for scraping data from the web instead of using an API. Useful for
    sources with APIs that are restricted or have difficult approval processes.

    Args:
      scraped (str): scraped data from a single post permalink

    Returns:
      (dict, dict) tuple: : (AS activity or None, AS logged in actor (ie viewer))
    """
    raise NotImplementedError()

  def scraped_to_actor(self, scraped):
    """Converts HTML from a profile page to an AS1 actor.

    Args
      html (str): HTML from a profile page

    Returns:
      dict: AS1 actor
    """
    raise NotImplementedError()

  def merge_scraped_reactions(self, scraped, activity):
    """Converts and merges scraped likes and reactions into an activity.

    New likes and emoji reactions are added to the activity in ``tags``.
    Existing likes and emoji reactions in ``tags`` are ignored.

    Args:
      scraped (str): HTML or JSON with likes and/or emoji reactions
      activity (dict): AS activity to merge these reactions into

    Returns:
      list of dict: AS like/react tag objects converted from scraped
    """
    raise NotImplementedError()

  def create(self, obj, include_link=OMIT_LINK, ignore_formatting=False):
    """Creates a new object: a post, comment, like, share, or RSVP.

    Subclasses should override this. Different sites will support different
    functionality; check each subclass for details. The actor will usually be
    the authenticated user.

    Args:
      obj (dict): ActivityStreams object. At minimum, must have the content field.
        objectType is strongly recommended.
      include_link (str): :const:`INCLUDE_LINK`, :const:`OMIT_LINK`, or
        :const:`INCLUDE_IF_TRUNCATED`; whether to include a link to the object
        (if it has one) in the content.
      ignore_formatting (bool): whether to use content text as is, instead of
        converting its HTML to plain text styling (newlines, etc.)

    Returns:
      CreationResult: The result. ``content`` will be a dict or None. If the
      newly created object has an id or permalink, they'll be provided in the
      values for ``id`` and ``url``.
    """
    raise NotImplementedError()

  def preview_create(self, obj, include_link=OMIT_LINK, ignore_formatting=False):
    """Previews creating a new object: a post, comment, like, share, or RSVP.

    Returns HTML that previews what :meth:`create` with the same object will
    do.

    Subclasses should override this. Different sites will support different
    functionality; check each subclass for details. The actor will usually be
    the authenticated user.

    Args:
      obj (dict): ActivityStreams object. At minimum, must have the ``content``
        field. ``objectType`` is strongly recommended.
      include_link (str): :const:`INCLUDE_LINK`, :const:`OMIT_LINK`, or
        :const:`INCLUDE_IF_TRUNCATED`; whether to include a link to the object
        (if it has one) in the content.
      ignore_formatting (bool): whether to use content text as is, instead of
        converting its HTML to plain text styling (newlines, etc.)

    Returns:
      CreationResult: The result. `content` will be a dict or ``None``.
    """
    raise NotImplementedError()

  def delete(self, id):
    """Deletes a post.

    Generally only supports posts that were authored by the authenticating user.

    Args:
      id (str): silo object id

    Returns:
      CreationResult:
    """
    raise NotImplementedError()

  def preview_delete(self, id):
    """Previews deleting a post.

    Args:
      id (str): silo object id

    Returns:
      CreationResult:
    """
    raise NotImplementedError()

  def get_event(self, event_id):
    """Fetches and returns an event.

    Args:
      id (str): site-specific event id

    Returns:
      dict: decoded ActivityStreams activity, or None
    """
    raise NotImplementedError()

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Fetches and returns a comment.

    Subclasses should override this.

    Args:
      comment_id (str): comment id
      activity_id (str): activity id, optional
      activity_author_id (str): activity author id, optional. Needed for some
        sources (e.g. Facebook) to construct the comment permalink.
      activity (dict): activity object, optional. May avoid an API call if
        provided.

    Returns:
      dict: ActivityStreams comment object

    Raises:
      ValueError: if any argument is invalid for this source
    """
    raise NotImplementedError()

  def get_like(self, activity_user_id, activity_id, like_user_id, activity=None):
    """Fetches and returns a 'like'.

    Default implementation that fetches the activity and its likes, then
    searches for a like by the given user. Subclasses should override this if
    they can optimize the process.

    Args:
      activity_user_id (str): id of the user who posted the original activity
      activity_id (str): activity id
      like_user_id (str): id of the user who liked the activity
      activity (dict): activity object, optional. May avoid an API call if
        provided.

    Returns:
      dict: ActivityStreams like activity
    """
    if not activity:
      activity = self._get_activity(activity_user_id, activity_id, fetch_likes=True)
    return self._get_tag(activity, 'like', like_user_id)

  def get_reaction(self, activity_user_id, activity_id, reaction_user_id,
                   reaction_id, activity=None):
    """Fetches and returns a reaction.

    Default implementation that fetches the activity and its reactions, then
    searches for this specific reaction. Subclasses should override this if they
    can optimize the process.

    Args:
      activity_user_id (str): id of the user who posted the original activity
      activity_id (str): activity id
      reaction_user_id (str): id of the user who reacted
      reaction_id (str): id of the reaction
      activity (dict): activity object, optional. May avoid an API call if
        provided.

    Returns:
      dict: ActivityStreams reaction activity
    """
    if not activity:
      activity = self._get_activity(activity_user_id, activity_id, fetch_likes=True)
    return self._get_tag(activity, 'react', reaction_user_id, reaction_id)

  def get_share(self, activity_user_id, activity_id, share_id, activity=None):
    """Fetches and returns a share.

    Args:
      activity_user_id (str): id of the user who posted the original activity
      activity_id (str): activity id
      share_id (str): id of the share object or the user who shared it
      activity (dict): activity object, optional. May avoid an API call if
        provided.

    Returns:
      dict: an ActivityStreams share activity
    """
    if not activity:
      activity = self._get_activity(activity_user_id, activity_id, fetch_shares=True)
    return self._get_tag(activity, 'share', share_id)

  def get_rsvp(self, activity_user_id, event_id, user_id, event=None):
    """Fetches and returns an RSVP.

    Args:
      activity_user_id (str): id of the user who posted the event. unused.
      event_id (str): event id
      user_id (str): user id
      event (dict): AS event activity, optional

    Returns: dict, an ActivityStreams RSVP activity object
    """
    if not event:
      event = self.get_event(event_id)
      if not event:
        return None

    for rsvp in as1.get_rsvps_from_event(event['object']):
      for field in 'actor', 'object':
        id = rsvp.get(field, {}).get('id')
        if id and user_id == util.parse_tag_uri(id)[1]:
          return rsvp

  def get_blocklist(self):
    """Fetches and returns the current user's block list.

    ...ie the users that the current user is blocking. The exact semantics of
    blocking vary from silo to silo.

    Returns:
      sequence of dict: actor objects
    """
    raise NotImplementedError()

  def get_blocklist_ids(self):
    """Returns the current user's block list as a list of silo-specific user ids.

    Returns:
      sequence of int or str: user ids, not globally unique across other sources
    """
    raise NotImplementedError()

  def user_to_actor(self, user):
    """Converts a user to an actor.

    The returned object will have at least a ``url`` field. If the user has
    multiple URLs, there will also be a ``urls`` list field whose elements are
    dicts with ``value`` URL.

    Args:
      user (dict): a decoded JSON silo user object

    Returns:
      dict: ActivityStreams actor
    """
    raise NotImplementedError()

  def _get_activity(self, user_id, activity_id, **kwargs):
    activities = self.get_activities(user_id=user_id, activity_id=activity_id,
                                     **kwargs)
    if activities:
      return activities[0]

  def _get_tag(self, activity, verb, user_id, tag_id=None):
    if not activity:
      return None

    user_tag_id = self.tag_uri(user_id)
    if tag_id:
      tag_id = self.tag_uri(tag_id)

    for tag in activity.get('object', {}).get('tags', []):
      author = tag.get('author', {})
      if (tag.get('verb') == verb and
          (not tag_id or tag_id == tag.get('id')) and
          (author.get('id') == user_tag_id or author.get('numeric_id') == user_id)):
        return tag

  @staticmethod
  def postprocess_activity(activity, mentions=False):
    """Does source-independent post-processing of an activity, in place.

    Right now just populates the ``title`` field.

    Args:
      activity (dict)
      mentions (boolean): whether to detect @-mention links and convert them to
        mention tags
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

    actor_name = as1.actor_name(activity.get('actor'))
    obj = activity.get('object')

    if obj:
      activity['object'] = Source.postprocess_object(obj, mentions=mentions)
      if not activity.get('title'):
        verb = DISPLAY_VERBS.get(activity.get('verb'))
        obj_name = obj.get('displayName')
        obj_type = TYPE_DISPLAY_NAMES.get(obj.get('objectType'))
        if obj_name and not verb:
          activity['title'] = obj_name
        elif verb and (obj_name or obj_type):
          app = activity.get('generator', {}).get('displayName')
          name = obj_name or 'a %s' % (obj_type or 'unknown')
          app = f' on {app}' if app else ''
          activity['title'] = f"{actor_name} {verb or 'posted'} {name}{app}."

    return util.trim_nulls(activity)

  @staticmethod
  def postprocess_object(obj, mentions=False):
    """Does source-independent post-processing of an object, in place.

    * Populates ``location.position`` based on latitude and longitude.
    * Optionally interprets HTML links in content with text starting with ``@``,
      eg ``@user`` or ``@user.com`` or ``@user@instance.com``, as @-mentions
      and adds ``mention`` tags for them.

    Args:
      obj (dict)
      mentions (boolean): whether to detect @-mention links and convert them to
        mention tags

    Returns:
      dict: ``obj``, modified in place
    """
    loc = obj.get('location')
    if loc:
      lat = loc.get('latitude')
      lon = loc.get('longitude')
      if lat and lon and not loc.get('position'):
        # ISO 6709 location string. details: http://en.wikipedia.org/wiki/ISO_6709
        loc['position'] = '%0+10.6f%0+11.6f/' % (lat, lon)

    if mentions:
      # @-mentions to mention tags
      # https://github.com/snarfed/bridgy-fed/issues/493
      # TODO: unify into new textContent field
      # https://github.com/snarfed/granary/issues/729
      content = obj.get('content') or ''
      existing_tags_with_urls = util.trim_nulls({
        t.get('displayName') for t in obj.setdefault('tags', []) if t.get('url')
      })

      for a in util.parse_html(content).find_all('a'):
        href = a.get('href')
        text = a.get_text('').strip()
        if href and text.startswith('@') and text not in existing_tags_with_urls:
          obj.setdefault('tags', []).append({
            'objectType': 'mention',
            'url': href,
            'displayName': text,
          })

    return util.trim_nulls(obj)

  @classmethod
  def embed_post(cls, obj):
    """Returns the HTML string for embedding a post object.

    Args:
      obj (dict): AS1 object with at least ``url``, optionally also ``content``.

    Returns:
      str: HTML
    """
    obj = copy.copy(obj)
    for field in 'url', 'content':
      if field not in obj:
        obj.setdefault(field, obj.get('object', {}).get(field, ''))

    # allow HTML in posts to be rendered safely, avoiding risk of XSS, but
    # allowing posts that could contain HTML to be allowed
    obj['content'] = escape(obj['content'])

    # escape URL, but not with urllib.parse.quote, because it quotes a ton of
    # chars we want to pass through, including most unicode chars.
    obj['url'] = obj['url'].replace('<', '%3C').replace('>', '%3E')

    return cls.EMBED_POST % obj

  @classmethod
  def embed_actor(cls, actor):
    """Returns the HTML string for embedding an actor object."""
    return f"""
<a class="h-card" href="{actor.get('url')}">
 <img class="profile u-photo" src="{actor.get('image', {}).get('url')}" width="32px" /> {actor.get('displayName')}</a>"""

  def tag_uri(self, name):
    """Returns a tag URI string for this source and the given string name."""
    return util.tag_uri(self.DOMAIN, name)

  def base_object(self, obj):
    """Returns the ``base`` silo object that an object operates on.

    For example, if the object is a comment, this returns the post that it's a
    comment on. If it's an RSVP, this returns the event. The id in the returned
    object is silo-specific, ie not a tag URI.

    Subclasses may override this.

    Args:
      obj (dict): ActivityStreams object

    Returns:
      dict: minimal ActivityStreams object. Usually has at least ``id``; may
      also have ``url``, ``author``, etc.
    """
    # look at in-reply-tos first, then objects (for likes and reposts).
    # technically, the ActivityStreams 'object' field is always supposed to be
    # singular, but microformats2.json_to_object() sometimes returns activities
    # that have a list value, e.g. likes or reposts of multiple objects.
    candidates = []
    for field in ('inReplyTo', 'object', 'target'):
      candidates += util.get_list(obj, field)

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

    return self._postprocess_base_object(base_obj)

  @classmethod
  def _postprocess_base_object(cls, obj):
    obj = copy.deepcopy(obj)
    id = obj.get('id')
    url = obj.get('url')

    if id:
      parsed = util.parse_tag_uri(id)
      if parsed:
        obj['id'] = parsed[1]
    elif url:
      obj['id'] = cls.base_id(url)

    return obj

  @classmethod
  def base_id(cls, url):
    """Guesses the id of the object in the given URL.

    Returns:
      str or None
    """
    return urllib.parse.urlparse(url).path.rstrip('/').rsplit('/', 1)[-1] or None

  @classmethod
  def post_id(cls, url):
    """Guesses the post id of the given URL.

    Returns:
      str or None
    """
    id = cls.base_id(url)
    if id and (not cls.POST_ID_RE or cls.POST_ID_RE.match(id)):
      return id

  def _content_for_create(self, obj, ignore_formatting=False, prefer_name=False,
                          strip_first_video_tag=False, strip_quotations=False):
    """Returns content text for :meth:`create` and :meth:`preview_create`.

    Returns ``summary`` if available, then ``content``, then ``displayName``.

    If using ``content``, renders the HTML content to text using html2text so
    that whitespace is formatted like in the browser.

    Args:
      obj (dict): ActivityStreams object
      ignore_formatting (bool): whether to use content text as is, instead of
        converting its HTML to plain text styling (newlines, etc.)
      prefer_name (bool): whether to prefer ``displayName`` to ``content``
      strip_first_video_tag (bool): if true, removes the first ``<video>`` tag.
        useful when it will be uploaded and attached to the post natively in the
        silo.
      strip_quotations (bool): if true, removes ``u-quotation-of`` tags. useful
        when creating quote tweets.

    Returns:
      str: possibly empty
    """
    summary = obj.get('summary', '').strip()
    name = obj.get('displayName', '').strip()
    content = obj.get('content', '').strip()

    # note that unicode() on a BeautifulSoup object preserves HTML and
    # whitespace, even after modifying the DOM, which is important for
    # formatting.
    #
    # The catch is that it adds a '<html><head></head><body>' header and
    # '</body></html>' footer. ah well. harmless.
    soup = util.parse_html(content)
    if strip_first_video_tag:
      video = soup.video or soup.find(class_='u-video')
      if video:
        video.extract()
        content = str(soup)

    if strip_quotations:
      quotations = soup.find_all(class_='u-quotation-of')
      if quotations:
        for q in quotations:
          q.extract()
        content = str(soup)

    # compare to content with HTML tags stripped
    if summary == soup.get_text('').strip():
      # summary and content are the same; prefer content so that we can use its
      # HTML formatting.
      summary = None

    # sniff whether content is HTML or plain text. use html.parser instead of
    # the default html5lib since html.parser is stricter and expects actual
    # HTML tags.
    # https://www.crummy.com/software/BeautifulSoup/bs4/doc/#differences-between-parsers
    is_html = (bool(BeautifulSoup(content, 'html.parser').find()) or
               HTML_ENTITY_RE.search(content))
    if is_html and not ignore_formatting:
      content = html_to_text(content, baseurl=(obj.get('url') or ''),
                             **self.HTML2TEXT_OPTIONS)
    elif not is_html and ignore_formatting:
      content = re.sub(r'\s+', ' ', content)

    return summary or ((name or content) if prefer_name else
                       (content or name)
                       ) or ''

  def truncate(self, content, url, include_link, type=None, quote_url=None,
               **kwargs):
    """Shorten text content to fit within a character limit.

    Character limit and URL character length are taken from
    :const:`TRUNCATE_TEXT_LENGTH` and :const:`TRUNCATE_URL_LENGTH`.

    Args:
      content (str)
      url (str)
      include_link (str): ``OMIT_LINK``, ``INCLUDE_LINK``, or
        ``INCLUDE_IF_TRUNCATED``
      type (str): optional: ``article``, ``note``,
        etc. Also accepts custom type ``dm``.
      quote_url (str): URL, optional. If provided, it will be appended to the
        content, *after* truncating.
      **kwargs: passed through to brevity.shorten

    Return:
      str: the possibly shortened and ellipsized text
    """
    if quote_url:
      kwargs.setdefault('target_length',
        (self.TRUNCATE_TEXT_LENGTH or brevity.WEIGHTS['maxWeightedTweetLength']) -
        (self.TRUNCATE_URL_LENGTH or brevity.WEIGHTS['transformedURLLength']) - 1)
    elif self.TRUNCATE_TEXT_LENGTH is not None:
      kwargs.setdefault('target_length', self.TRUNCATE_TEXT_LENGTH)

    if self.TRUNCATE_URL_LENGTH is not None:
      kwargs.setdefault('link_length', self.TRUNCATE_URL_LENGTH)

    if include_link != OMIT_LINK:
      kwargs.setdefault('permalink', url)  # only include when text is truncated

    if include_link == INCLUDE_LINK:
      kwargs.setdefault('permashortlink', url)  # always include

    if type == 'article':
      kwargs.setdefault('format', brevity.FORMAT_ARTICLE)

    truncated = brevity.shorten(content, **kwargs)

    if quote_url:
      truncated += ' ' + quote_url

    return truncated
