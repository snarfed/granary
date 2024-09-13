"""Utilities for ActivityStreams 1 objects.

* https://activitystrea.ms/specs/json/schema/activity-schema.html
* http://activitystrea.ms/specs/json/1.0/
"""
import collections
import copy
import logging
from operator import itemgetter
import re

from oauth_dropins.webutil import util

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
  to = get_objects(obj, 'to') or get_objects(inner_obj, 'to') or []
  aliases = util.trim_nulls([t.get('alias') for t in to])
  object_types = util.trim_nulls([t.get('objectType') for t in to])

  if '@public' in aliases or ('@unlisted' in aliases and unlisted):
    return True
  elif 'unknown' in object_types:
    return None
  elif aliases:
    return False
  elif 'to' in obj or 'to' in inner_obj:
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

  if not obj or object_type(obj) not in (None, 'note'):
    return None

  tos = util.get_list(obj, 'to')
  others = (util.get_list(obj, 'cc')
            + util.get_list(obj, 'bto')
            + util.get_list(obj, 'bcc'))
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
  a = activity
  for elem in ([a, a.get('object'), a.get('author'), a.get('actor')] +
               a.get('replies', {}).get('items', []) +
               a.get('attachments', []) +
               a.get('tags', [])):
    if elem:
      for obj in util.get_list(elem, field):
        url = obj.get('url')
        if url and not url.startswith(prefix):
          # Note that url isn't URL-encoded here, that's intentional, since
          # cloudimage.io and the caching-proxy Cloudflare worker don't decode.
          obj['url'] = prefix + url
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
    targets.extend(get_ids(o, 'inReplyTo') +
                   get_ids(o, 'tags') +
                   util.get_urls(o, 'tags'))

    verb = o.get('verb')
    if verb in VERBS_WITH_OBJECT:
      # prefer id or url, if available
      # https://github.com/snarfed/bridgy-fed/issues/307
      o_targets = get_ids(o, 'object') or util.get_urls(o, 'object')
      targets.extend(o_targets)
      if not o_targets:
        logger.warning(f'{verb} missing target id/URL')

  return util.dedupe_urls(targets)
