"""Utilities for ActivityStreams 1 objects.

* https://activitystrea.ms/specs/json/schema/activity-schema.html
* http://activitystrea.ms/specs/json/1.0/
"""
import collections
import copy
import logging
from operator import itemgetter
import re
import string

from bs4 import BeautifulSoup
from oauth_dropins.webutil import util

from . import source

logger = logging.getLogger(__name__)

CONTENT_TYPE = 'application/stream+json'

# maps each AS1 RSVP verb to the collection inside an event object that the
# RSVPing actor would go into.
RSVP_VERB_TO_COLLECTION = collections.OrderedDict((  # in priority order
  ('rsvp-yes', 'attending'),
  ('rsvp-no', 'notAttending'),
  ('rsvp-maybe', 'maybeAttending'),
  ('rsvp-interested', 'interested'),
  ('invite', 'invited'),
))
VERBS_WITH_OBJECT = frozenset((
  'accept',
  'block',
  'flag',
  'follow',
  'like',
  'react',
  'reject',
  'share',
  'stop-following',
  'undo',
)) | set(RSVP_VERB_TO_COLLECTION.keys())
VERBS_WITH_ACTOR_OBJECT = frozenset((
  'block',
  'follow',
  'stop-following',
))
CRUD_VERBS = frozenset((
  'delete',
  'post',
  'update',
  # not in AS1 spec, undo isn't a real AS1 verb, but we map it to AS2 Undo
  # https://activitystrea.ms/specs/json/schema/activity-schema.html#verbs
  'undo',
))

# objectTypes that can be actors. technically this is based on AS2 semantics,
# since it's unspecified in AS1.
# https://www.w3.org/TR/activitystreams-core/#actors
# https://activitystrea.ms/specs/json/1.0/#activity
ACTOR_TYPES = frozenset((
  'application',
  'group',
  'organization',
  'person',
  'service',
))

# this isn't well defined 🤷
POST_TYPES = frozenset((
  'article',
  'comment',
  'link',
  'mention',
  'note',
))

# used in original_post_discovery
_PERMASHORTCITATION_RE = re.compile(r'\(([^:\s)]+\.[^\s)]{2,})[ /]([^\s)]+)\)$')

HASHTAG_RE = re.compile(r'(^|\s)[#＃](\w+)\b', re.UNICODE)

# TODO: html2text doesn't escape ]s in link text, which breaks this, eg
# <a href="http://post">ba](r</a> turns into [ba](r](http://post)
MARKDOWN_LINK_RE = re.compile(r'\[(?P<text>.*?)\]\((?P<url>[^ ]*?)( "[^"]*?")?(?<!\\)\)')

AT_MENTION_RE = re.compile(r'(?:^|\W)(@[\w._-]+)(?:$|\W)')


def object_type(obj):
  """Returns the object type, or the verb if it's an activity object.

  Details: http://activitystrea.ms/specs/json/1.0/#activity-object

  Args:
    obj (dict): decoded JSON ActivityStreams object

  Returns:
    str: ActivityStreams object type
  """
  type = obj.get('objectType')
  return type if type and type != 'activity' else obj.get('verb')


def get_object(obj, field='object'):
  """Extracts and returns a field value as an object.

  If the field value is a string, returns an object with it as the id, eg
  ``{'id': val}``. If the field value is a list, returns the first element.

  Args:
    obj (dict): decoded JSON ActivityStreams object
    field (str)

  Returns:
    dict:
  """
  if not obj:
    return {}
  val = util.get_first(obj, field, {}) or {}
  return {'id': val} if isinstance(val, str) else val


def get_objects(obj, field='object'):
  """Extracts and returns a field's values as objects.

  If a field value is a string, generates an object with it as the id, eg
  ``{'id': val}``.

  Args:
    obj (dict): decoded JSON ActivityStreams object
    field (str)

  Returns:
    sequence of dict:
  """
  if not obj:
    return []
  return [{'id': val} if isinstance(val, str) else val
          for val in util.get_list(obj, field)]


def get_owner(obj):
  """Returns an object's author or actor.

  Prefers author, then actor. If that's an object, returns its id, if available.
  If neither field exists, but ``obj.objectType`` is in ``ACTOR_TYPES``,
  returns its own id, if available.

  For posts, updates, and deletes, falls back to the inner object's owner if the
  outer activity has no actor.

  Args:
    obj (dict): decoded JSON ActivityStreams object

  Returns:
    str:
  """
  if not obj:
    return None
  elif not isinstance(obj, dict):
    raise ValueError(f'{obj} is not a dict')

  ids = get_ids(obj, 'author') or get_ids(obj, 'actor')
  if ids:
    return ids[0]

  if obj.get('objectType') in ACTOR_TYPES:
    ids = util.get_list(obj, 'id')
    if ids:
      return ids[0]

  if obj.get('verb') in ('post', 'update', 'delete'):
    return get_owner(get_object(obj))


def get_url(obj):
  """Returns the url field's first text value, or ``''``.

  Somewhat duplicates :func:`microformats2.get_text`.
  """
  if not obj:
    return ''

  urls = object_urls(obj)
  if not urls:
    return ''

  return (urls[0] if isinstance(urls, (list, tuple))
          else urls if isinstance(urls, str)
          else '')


def get_ids(obj, field):
  """Extracts and returns a given field's values as ids.

  Args:
    obj (dict): decoded JSON ActivityStreams object
    field (str)

  Returns string values as is. For dict values, returns their inner ``id`` or
  ``url`` field value, in that order of precedence.
  """
  ids = set()
  for elem in util.get_list(obj, field):
    if elem and isinstance(elem, str):
      ids.add(elem)
    elif isinstance(elem, dict):
      id = elem.get('id') or elem.get('url')
      if id:
        ids.add(id)

  return sorted(ids)


def get_id(obj, field):
  """Extracts and returns a given field's id value.

  Args:
    obj (dict): decoded JSON ActivityStreams object
    field (str)

  Returns a string value as is. For dict values, returns its inner ``id``.
  """
  return get_object(obj, field).get('id')


def merge_by_id(obj, field, new):
  """Merges new items by id into a field in an existing AS1 object, in place.

  Merges new items by id into the given field. If it exists, it must be a list.
  Requires all existing and new items in the field to have ids.

  Args:
    obj (dict): AS1 object
    field (str): name of field to merge new items into
    new (sequence of dict): new values to merge in
  """
  merged = {o['id']: o for o in obj.get(field, []) + new}
  obj[field] = sorted(merged.values(), key=itemgetter('id'))


def is_public(obj, unlisted=True):
  """Returns True if the object is public, False if private, None if unknown.

  ...according to the Audience Targeting extension:
  http://activitystrea.ms/specs/json/targeting/1.0/

  Expects values generated by this library: ``objectType`` ``group``, ``alias``
  ``@public``, ``@unlisted``, or ``@private``.

  Also, important point: this defaults to True, ie public. Bridgy depends on
  that and prunes the to field from stored activities in Response objects (in
  ``bridgy/util.prune_activity``). If the default here ever changes, be sure to
  update Bridgy's code.

  Args:
    obj (dict): AS1 activity or object
    unlisted (bool): whether `@unlisted` counts as public or not

  Returns:
    bool:
  """
  if obj is None:
    return None

  inner_obj = get_object(obj)

  def get_to_cc(o):
    return get_objects(o, 'to') + get_objects(o, 'cc')

  if object_type(obj) in CRUD_VERBS:
    to_cc = get_to_cc(inner_obj)
  else:
    to_cc = get_to_cc(obj) or get_to_cc(inner_obj)

  aliases = util.trim_nulls([t.get('alias') for t in to_cc])
  object_types = util.trim_nulls([t.get('objectType') for t in to_cc])

  if '@public' in aliases or ('@unlisted' in aliases and unlisted):
    return True
  elif 'unknown' in object_types:
    return None
  elif aliases:
    return False
  elif to_cc and object_type(inner_obj) not in ACTOR_TYPES:
    # it does at least have some audience that doesn't include public
    return False

  return True


def recipient_if_dm(obj, actor=None):
  """If ``obj`` is a DM, returns the recipient actor's id.

  DMs are ``note``s addressed to a single recipient, ie ``to`` has one value and
  ``cc``, ``bcc``, and ``bto`` have none.

  If ``obj`` isn't a DM, returns None.

  Those fields are based on the Audience Targeting extension:
  http://activitystrea.ms/specs/json/targeting/1.0/

  Args:
    obj (dict): AS1 activity or object
    actor (dict): optional AS1 actor who sent this object. Its followers
      collection is used to identify followers-only posts.

  Returns:
    bool:
  """
  if not obj or is_public(obj):
    return None

  if object_type(obj) == 'post':
    obj = get_object(obj)

  if not obj or object_type(obj) not in (None, 'note', 'comment'):
    return None

  tos = util.get_list(obj, 'to') + util.get_list(obj, 'cc')
  others = util.get_list(obj, 'bto') + util.get_list(obj, 'bcc')
  if not (len(tos) == 1 and len(others) == 0):
    return None

  follow_collections = []
  for a in actor, get_object(obj, 'author'):
    if a:
      follow_collections.extend([a.get('followers'), a.get('following')])

  to = tos.pop()
  if isinstance(to, dict):
    to = to.get('id') or ''

  to_lower = to.lower()
  if to and not is_audience(to) and to not in follow_collections:
    return to


def is_dm(obj, actor=None):
  """Returns True if the object is a DM, ie addressed to a single recipient.

  See :func:`recipient_if_dm` for details.
  """
  return bool(recipient_if_dm(obj, actor=actor))


def is_audience(val):
  """Returns True if val is a "special" AS1 or AS2 audience, eg "public."


  See the AS1 Audience Targeting extension and AS2 spec:
  * http://activitystrea.ms/specs/json/targeting/1.0/
  * https://www.w3.org/TR/activitystreams-vocabulary/#dfn-audience
  """
  if not val or not isinstance(val, str):
    return False

  val = val.lower()
  return (# https://activitystrea.ms/specs/json/targeting/1.0/
          val in ('public', 'unlisted', 'private')
          or val.startswith('https://www.w3.org/')
          or val.startswith('https://w3.org/')
          or val.startswith('@')  # AS1 audience targeting alias, eg @public, @unlisted
          or val.startswith('as:')
          # as2 public constant is https://www.w3.org/ns/activitystreams#Public
          or val.endswith('#public')
          # non-standared heuristic for Mastodon and similar followers/following
          # collections
          or val.endswith('/followers')
          or val.endswith('/following'))


def add_rsvps_to_event(event, rsvps):
  """Adds RSVP objects to an event's attending fields, in place.

  Args:
    event (dict): ActivityStreams event object
    rsvps (sequence of dict): ActivityStreams RSVP activity objects
  """
  for rsvp in rsvps:
    field = RSVP_VERB_TO_COLLECTION.get(rsvp.get('verb'))
    if field:
      event.setdefault(field, []).append(rsvp.get(
          'object' if field == 'invited' else 'actor'))


def get_rsvps_from_event(event):
  """Returns RSVP objects for an event's attending fields.

  Args:
    event (dict): ActivityStreams event object

  Returns:
    sequence of dict: ActivityStreams RSVP activity objects
  """
  id = event.get('id')
  if not id:
    return []
  parsed = util.parse_tag_uri(id)
  if not parsed:
    return []
  domain, event_id = parsed
  url = event.get('url')
  author = event.get('author')

  rsvps = []
  for verb, field in RSVP_VERB_TO_COLLECTION.items():
    for actor in event.get(field, []):
      rsvp = {'objectType': 'activity',
              'verb': verb,
              'object' if verb == 'invite' else 'actor': actor,
              'url': url,
              }

      if event_id and 'id' in actor:
        _, actor_id = util.parse_tag_uri(actor['id'])
        rsvp['id'] = util.tag_uri(domain, f'{event_id}_rsvp_{actor_id}')
        if url:
          rsvp['url'] = '#'.join((url, actor_id))

      if verb == 'invite' and author:
        rsvp['actor'] = author

      rsvps.append(rsvp)

  return rsvps


def activity_changed(before, after, inReplyTo=True, log=False):
  """Returns whether two activities or objects differ meaningfully.

  Only compares a few fields: ``objectType``, ``verb``, ``displayName`,
  ``content``, ``summary``, ``location``, and ``image``. Notably does *not*
  compare ``author``, ``published``, or ``updated``.

  Args:
    before (dict): ActivityStreams activity or object
    after (dict): ActivityStreams activity or object
    inReplyTo (bool): whether to return True if ``inReplyTo`` has changed
    log (bool): whether to log each changed field

  Returns:
    bool:
  """
  def changed(b, a, field, label, ignore=None):
    b_val = b.get(field)
    a_val = a.get(field)

    if ignore and isinstance(b_val, dict) and isinstance(a_val, dict):
      b_val = copy.copy(b_val)
      a_val = copy.copy(a_val)
      for field in ignore:
        b_val.pop(field, None)
        a_val.pop(field, None)

    if b_val != a_val and (a_val or b_val):
      if log:
        logger.debug(f'{label}[{field}] {b_val} => {a_val}')
      return True

  obj_b = get_object(before)
  obj_a = get_object(after)
  if any(changed(before, after, field, 'activity') or
         changed(obj_b, obj_a, field, 'activity[object]')
         for field in ('objectType', 'verb', 'to', 'displayName', 'content',
                       'summary', 'location', 'image')):
    return True

  if (inReplyTo and
      (changed(before, after, 'inReplyTo', 'inReplyTo', ignore=('author',)) or
       changed(obj_b, obj_a, 'inReplyTo', 'object.inReplyTo', ignore=('author',)))):
    return True

  return False


def append_in_reply_to(before, after):
  """Appends before's ``inReplyTo`` to ``after``, in place.

  Args:
    before (dict): ActivityStreams activity or object
    after (dict): ActivityStreams activity or object
  """
  obj_b = get_object(before) or before
  obj_a = get_object(after) or after

  if obj_b and obj_a:
    reply_b = util.get_list(obj_b, 'inReplyTo')
    reply_a = util.get_list(obj_a, 'inReplyTo')
    obj_a['inReplyTo'] = util.dedupe_urls(reply_a + reply_b)


def actor_name(actor):
  """Returns the given actor's name if available, otherwise Unknown."""
  if actor:
    return actor.get('displayName') or actor.get('username') or 'Unknown'
  return 'Unknown'


def original_post_discovery(
    activity, domains=None, include_redirect_sources=True,
    include_reserved_hosts=True, max_redirect_fetches=None, **kwargs):
  """Discovers original post links.

  This is a variation on http://indiewebcamp.com/original-post-discovery . It
  differs in that it finds multiple candidate links instead of one, and it
  doesn't bother looking for MF2 (etc) markup because the silos don't let you
  input it. More background:
  https://github.com/snarfed/bridgy/issues/51#issuecomment-136018857

  Original post candidates come from the ``upstreamDuplicates``,
  ``attachments``, and ``tags`` fields, as well as links and
  permashortlinks/permashortcitations in the text content.

  Args:
    activity (dict): activity
    domains (sequence of str) domains, optional. If provided, only links to
      these domains will be considered original and stored in
      ``upstreamDuplicates``. (Permashortcitations are exempt.)
    include_redirect_sources (bool): whether to include URLs that redirect
      as well as their final destination URLs
    include_reserved_hosts (bool): whether to include domains on reserved
      TLDs (eg foo.example) and local hosts (eg http://foo.local/,
      http://my-server/)
    max_redirect_fetches (int): if specified, only make up to this many HTTP
      fetches to resolve redirects.
    kwargs: passed to :func:`requests.head` when following redirects

  Returns:
    (list of str, list of str) tuple: (original post URLs, mentions)
  """
  obj = get_object(activity) or activity
  content = obj.get('content', '').strip()

  # find all candidate URLs
  tags = [t.get('url') for t in obj.get('attachments', []) + obj.get('tags', [])
          if t.get('objectType') in ('article', 'link', 'mention', 'note', None)]
  candidates = (tags + util.extract_links(content) +
                obj.get('upstreamDuplicates', []) +
                util.get_list(obj, 'targetUrl'))

  # Permashortcitations (http://indiewebcamp.com/permashortcitation) are short
  # references to canonical copies of a given (usually syndicated) post, of
  # the form (DOMAIN PATH). We consider them an explicit original post link.
  candidates += [match.expand(r'http://\1/\2') for match in
                 _PERMASHORTCITATION_RE.finditer(content)]

  candidates = util.dedupe_urls(
    util.clean_url(url) for url in candidates
    if url and (url.startswith('http://') or url.startswith('https://')) and
    # heuristic: ellipsized URLs are probably incomplete, so omit them.
    not url.endswith('...') and not url.endswith('…'))

  # check for redirect and add their final urls
  if max_redirect_fetches and len(candidates) > max_redirect_fetches:
    logger.warning(f'Found {len(candidates)} original post candidates, only resolving redirects for the first {max_redirect_fetches}')
  redirects = {}  # maps final URL to original URL for redirects
  for url in candidates[:max_redirect_fetches]:
    resolved = util.follow_redirects(url, **kwargs)
    if (resolved.url != url and
        resolved.headers.get('content-type', '').startswith('text/html')):
      redirects[resolved.url] = url

  candidates.extend(redirects.keys())

  # use domains to determine which URLs are original post links vs mentions
  originals = set()
  mentions = set()
  for url in util.dedupe_urls(candidates):
    if url in redirects.values():
      # this is a redirected original URL. postpone and handle it when we hit
      # its final URL so that we know the final domain.
      continue

    domain = util.domain_from_link(url)
    if not domain:
      continue

    if not include_reserved_hosts and (
        ('.' not in domain
         or domain.split('.')[-1] in (util.RESERVED_TLDS | util.LOCAL_TLDS))):
      continue

    which = (originals if not domains or util.domain_or_parent_in(domain, domains)
             else mentions)
    which.add(url)
    redirected_from = redirects.get(url)
    if redirected_from and include_redirect_sources:
      which.add(redirected_from)

  logger.info(f'Original post discovery found original posts {originals}, mentions {mentions}')
  return originals, mentions


def prefix_urls(activity, field, prefix):
  """Adds a prefix to all matching URL fields, eg to inject a caching proxy.

  Generally used with the ``image`` or ``stream`` fields. For example::

      >>> prefix_urls({'actor': {'image': 'http://image'}}, 'image', 'https://proxy/')
      {'actor': {'image': 'https://proxy/http://image'}}

  Skips any URL fields that already start with the prefix. URLs are *not*
  URL-encoded before adding the prefix. (This is currently used with our
  caching-proxy Cloudflare worker and https://cloudimage.io/ , neither of which
  URL-decodes.)

  Args:
    activity (dict): AS1 activity; modified in place
    prefix (str)
  """
  def update(val):
    if isinstance(val, str) and not val.startswith(prefix):
      return prefix + val
    else:
      assert isinstance(val, dict)
      if (url := val.get('url')) and not url.startswith(prefix):
        val['url'] = prefix + url
      return val

  a = activity
  for elem in ([a, a.get('object'), a.get('author'), a.get('actor')] +
               a.get('replies', {}).get('items', []) +
               a.get('attachments', []) +
               a.get('tags', [])):
    if elem and isinstance(elem, dict):
      if val := elem.get(field):
        if isinstance(val, (tuple, list)):
          elem[field] = [update(e) for e in val]
        elif isinstance(val, (str, dict)):
          elem[field] = update(val)

      if elem is not a:
        prefix_urls(elem, field, prefix)


def object_urls(obj):
  """Returns an object's unique URLs, preserving order."""
  if isinstance(obj, str):
    return obj

  def value(obj):
    got = obj.get('value') if isinstance(obj, dict) else obj
    return got.strip() if got else None

  return util.uniquify(util.trim_nulls(
    value(u) for u in util.get_list(obj, 'url') + util.get_list(obj, 'urls')))


def targets(obj):
  """Collects an AS1 activity or object's targets.

  This is all ids/URLs that are direct "targets" of the activity, eg:

  * the post it's replying to
  * the post it's sharing
  * the post it's reacting to
  * the post it's quoting
  * the actor or other object it's tagging
  * the event it's inviting someone to
  * the event it's RSVPing to
  * the link or object it's bookmarking

  etc...

  Args:
    obj (dict): AS1 object or activity

  Returns:
    list of str: targets
  """
  if not obj:
    return []

  targets = []

  for o in [obj] + get_objects(obj):
    targets.extend(get_ids(o, 'inReplyTo') + quoted_posts(o))

    for tag in get_objects(o, 'tags'):
      if tag.get('objectType') not in ('tag', 'hashtag'):
        targets += [tag.get('id'), tag.get('url')]

    verb = o.get('verb')
    if verb in VERBS_WITH_OBJECT:
      # prefer id or url, if available
      # https://github.com/snarfed/bridgy-fed/issues/307
      o_targets = get_ids(o, 'object') or util.get_urls(o, 'object')
      targets.extend(o_targets)
      if not o_targets:
        logger.warning(f'{verb} missing target id/URL')

  return util.dedupe_urls(targets)


def quoted_posts(obj):
  """Returns the ids that an object or activity is quoting.

  In AS1, we define quoted posts as attachments with ``objectType: note``.

  Arg:
    obj (dict): AS1 object or activity

  Returns:
    sequence of string ids, possibly empty
  """
  if obj.get('verb') in CRUD_VERBS:
    obj = get_object(obj)

  return [a['id'] for a in get_objects(obj, 'attachments')
          if a.get('id') and a.get('objectType') == 'note']


def mentions(obj):
  """Returns an object or activity's mention tags.

  Their ``url`` fields are extracted and returned, not ``id`, but in the common case
  the values are interpreted as ids.

  Arg:
    obj (dict): AS1 object or activity

  Returns:
    sequence of string URLs, possibly empty
  """
  if obj.get('verb') in CRUD_VERBS:
    obj = get_object(obj)

  return [t['url'] for t in get_objects(obj, 'tags')
          if t.get('url') and t.get('objectType') == 'mention']


def is_content_html(obj):
  """Returns True if ``obj.content`` is HTML, False otherwise.

  Args:
    obj (dict): AS1 object
  """
  if (is_html := obj.get('content_is_html')) is not None:
    return is_html

  content = obj.get('content') or ''
  # use html.parser to require HTML tags, not add them by default
  # https://www.crummy.com/software/BeautifulSoup/bs4/doc/#differences-between-parsers
  return (bool(util.parse_html(content, features='html.parser').find())
          or source.HTML_ENTITY_RE.search(content))


def expand_tags(obj):
  """Expands mention, hashtag, article (link) tags and indices from content.

  If ``obj.content`` is plain text, detects URLs, @-mentions, and hashtags and adds
  them to ``obj.tags`` if they're not already there. If they are, but don't have
  ``startIndex`` or ``length``, adds those fields. If ``obj.content`` is HTML, does
  nothing.

  Also, for ``mention`` and ``hashtag`` tags without ``startIndex``/``length``, tries
  to infer and populate their indices by searching ``content`` for their ``name``.

  Modifies ``obj`` in place.

  Args:
    obj (dict): AS1 object
  """
  if not obj or is_content_html(obj):
    return

  if obj.get('verb') in ('post', 'update'):
    expand_tags(get_object(obj))
    return

  if not (content := obj.get('content')):
    return

  tags = obj['tags'] = util.get_list(obj, 'tags')

  tag_ranges = []
  for tag in tags:
    start = tag.get('startIndex')
    length = tag.get('length')
    if start is not None and length is not None:
      tag_ranges.append(range(start, start + length))

  # try to infer indices for tags without them
  for tag in tags:
    if 'startIndex' in tag:
      continue

    # for article/link tags, search for the URL
    type = tag.get('objectType')
    if type in ('article', 'link'):
      if url := tag.get('url'):
        start = content.find(url)
        tag_range = range(start, start + len(url))
        if start >= 0 and not util.overlaps(tag_range, tag_ranges):
          tag_ranges.append(tag_range)
          tag['startIndex'] = start
          tag['length'] = len(url)
      continue

    name = tag.get('displayName', '').strip().lstrip('@#')
    if not type:
      if name:
        type = tag['objectType'] = 'hashtag'
      else:
        continue

    # guess index at first location found in text
    prefix = ('#' if type == 'hashtag'
              else '@' if type == 'mention'
              else '')
    # can't use \b at beginning because # and @ and emoji aren't word-constituent chars
    begin = string.punctuation.replace("-", "")
    end = string.punctuation.replace("-", "").replace("@", "").replace(".", "")
    match = re.search(
        fr'(^|[\s{begin}])({prefix}{re.escape(name)}(?:@{util.HOST_RE.pattern})?)($|[\s{end}])',
        content, flags=re.IGNORECASE)

    if not match and type == 'mention' and '@' in name:
      # try without @[server] suffix
      username = name.split('@')[0]
      match = re.search(fr'(^|\s)(@{username})\b', content)

    if match:
      start = match.start(2)
      length = len(match.group(2))
      tag_range = range(start, start + length)
      if not util.overlaps(tag_range, tag_ranges):
        tag_ranges.append(tag_range)
        tag['startIndex'] = start
        tag['length'] = length

  # generate tags for plain text @-mentions
  for match in AT_MENTION_RE.finditer(content):
    handle = match.group(1).strip()
    start = match.start(1)
    length = len(match.group(1))
    tag_range = range(start, start + length)
    if not util.overlaps(tag_range, tag_ranges):
      tag_ranges.append(tag_range)
      tags.append({
        'objectType': 'mention',
        'displayName': handle,
        'startIndex': start,
        'length': length,
      })


def add_tags_for_html_content_links(obj):
  """Adds tags for links in HTML ``obj.content``.

  Adds ``link`` tags to ``obj.tags`` for any HTML links in content that don't already
  have tags.

  If content is plain text, does nothing.

  Modifies ``obj`` in place.

  Args:
    obj (dict): AS1 object
  """
  return _handle_html_content(obj, to_plain_text=False)


def convert_html_content_to_text(obj):
  """If ``obj.content`` is HTML, converts it to plain text and adds link tags.

  Adds ``link`` tags to ``obj.tags`` for any HTML links in content that don't already
  have tags.

  If content is plain text, does nothing.

  Modifies ``obj`` in place.

  Args:
    obj (dict): AS1 object
  """
  return _handle_html_content(obj, to_plain_text=True)


def _handle_html_content(obj, to_plain_text=False):
  """Adds tags for links in HTML ``obj.content``, optionally converts it to text.

  Adds ``link`` tags to ``obj.tags`` for any HTML links in content that don't already
  have tags. Tags will include ``startIndex`` and ``length`` if ``to_plain_text`` is
  True.

  If content is plain text, does nothing.

  Modifies ``obj`` in place.

  Args:
    obj (dict): AS1 object
    to_plain_text (bool): whether to convert ``obj.content`` to plain text and set
      ``obj.content_is_html``
  """
  if not is_content_html(obj):
    return

  content = source.html_to_text(obj.get('content', ''), ignore_links=False)

  tags = obj.setdefault('tags', [])
  in_reply_tos = get_ids(obj, 'inReplyTo')
  existing_tags = {}  # maps string displayName to dict tag object

  for tag in tags:
    # normalize and store tag names we already have. for @-@ webfinger addresses,
    # store username as well as full address
    if name := tag.get('displayName'):
      name = name.strip().lstrip('@#')
      existing_tags.setdefault(name.lower(), tag)
      parts = name.split('@')
      if len(parts) == 2:
        existing_tags.setdefault(parts[0], tag)

    if to_plain_text:
      # clear existing tag indices since we're modifying content
      tag.pop('startIndex', None)
      tag.pop('length', None)

  # extract HTML links, convert to plain text, add tags with indices
  while link := MARKDOWN_LINK_RE.search(content):
    start, end = link.span()
    content = content[:start] + link['text'] + content[end:]
    url = link['url'].replace(r'\(', '(').replace(r'\)', ')')
    text = link['text'].strip()

    if not text:
      continue

    # our regexp isn't perfect, so skip links that we can't extract a
    # clean URL from
    if not util.is_web(url) or not util.is_url(url) or url in in_reply_tos:
      continue

    type = 'link'
    if not re.search(r'\s', text):
      if text.startswith('@'):
        type = 'mention'
      elif text.startswith('#'):
        type = 'hashtag'

    # do we already have this tag? for @-@ webfinger addresses, check username
    # as well as full address. if we do, only update its indices, at most.
    normalized_text = text.strip().lstrip('@#').lower()
    tag = (existing_tags.get(normalized_text)
           or existing_tags.get(normalized_text.split('@')[0]))
    if not tag:
      tag = {
        'objectType': type,
        'displayName': text,
        'url': url,
      }
      tags.append(tag)

    if to_plain_text:
      tag.update({
        'startIndex': start,
        'length': len(link['text']),
      })

  if to_plain_text:
    obj.update({
      'content': content,
      'content_is_html': False,
    })
