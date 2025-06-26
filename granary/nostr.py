"""Nostr.

* https://nostr.com/
* https://github.com/nostr-protocol/nostr
* https://github.com/nostr-protocol/nips

NIPS implemented:

* 01: base protocol, events, profile metadata
* 02: contacts/followings
* 05: domain identifiers
* 09: deletes
* 10: replies, mentions
* 12: hashtags, locations
* 14: subject tag in notes
* 18: reposts, including 10 for e/p tags
* 19: bech32-encoded ids
* 21: nostr: URI scheme
* 23: articles
* 24: extra fields
* 25: likes, emoji reactions
* 27: text notes
* 39: external identities
* 48: proxy tags
* 50: search
* 92/94: image, video, audio attachments

TODO:

* 11: relay info (like nodeinfo)
* 12: tag queries
* 16, 33: ephemeral/replaceable events
* 17: DMs
* 27: user mentions, note/event mentions
*     the difficulty is that the Nostr tags don't include human-readable
*     text. clients are supposed to get that from their local database.
* 32: tag activities
* 46: "Nostr Connect," signing proxy that holds user's keys
* 65: user relays. what would this be in AS1? anything?
* 73: external content ids
"""
from datetime import datetime, timezone
from hashlib import sha256
import itertools
import logging
import mimetypes
import re
import secrets

import bech32
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import HTTP_TIMEOUT, json_dumps, json_loads
import secp256k1
from websockets.exceptions import ConnectionClosedOK
from websockets.sync.client import connect

from . import as1
from .source import creation_result, FRIENDS, html_to_text, INCLUDE_LINK, OMIT_LINK, Source

logger = logging.getLogger(__name__)

# NIP-19
BECH32_PREFIXES = (
  'naddr',
  'nevent',
  'note',
  'nprofile',
  'npub',
  'nrelay',
  'nsec',
)
BECH32_RE = re.compile(f'^({"|".join(BECH32_PREFIXES)})[a-z0-9]{{50,70}}$')

# Event kinds
# https://github.com/nostr-protocol/nips#event-kinds
KIND_PROFILE = 0          # NIP-01: user profile metadata
KIND_NOTE = 1             # NIP-01: text note
KIND_CONTACTS = 3         # NIP-02: contact list / followings
KIND_DELETE = 5           # NIP-09: event deletion
KIND_REPOST = 6           # NIP-18: repost
KIND_REACTION = 7         # NIP-25: reactions (likes, dislikes, emojis)
KIND_GENERIC_REPOST = 16  # NIP-18: generic repost
KIND_AUTH = 22242         # NIP-42: client authentication
KIND_ARTICLE = 30023      # NIP-23: long-form content
KIND_RELAYS = 10002       # NIP-65: user relays

# NIP-39
# https://github.com/nostr-protocol/nips/blob/master/39.md#claim-types
# maps NIP-39 platform to base URL
PLATFORMS = {
  'github': 'https://github.com/',
  'telegram': 'https://t.me/',
  'twitter': 'https://twitter.com/',
  'mastodon': 'https://',
}

def id_for(event):
  """Generates an id for a Nostr event.

  Args:
    event (dict): Nostr event

  Returns:
    str: 32-character hex-encoded sha256 hash of the event, serialized
    according to NIP-01
  """
  event.setdefault('tags', [])
  event.setdefault('created_at', int(util.now(tz=timezone.utc).timestamp()))

  missing = set(('content', 'created_at', 'kind', 'pubkey', 'tags')) - event.keys()
  assert not missing, f'missing {missing}'

  # don't escape Unicode chars!
  # https://github.com/nostr-protocol/nips/issues/354
  return sha256(json_dumps([
    0,
    event['pubkey'],
    event['created_at'],
    event['kind'],
    event['tags'],
    event['content'],
  ], ensure_ascii=False).encode()).hexdigest()


def uri_for(event):
  """Generates a NIP-19 nostr: URI for a Nostr event.

  Args:
    event (dict): Nostr event

  Returns:
    str: NIP-19 nostr: URI, based on the event's id and kind
  """
  id = event.get('id')
  kind = event.get('kind')
  assert id and kind is not None, event

  prefix = ('note' if kind == KIND_NOTE
            else 'nprofile' if kind == KIND_PROFILE
            else 'nevent')

  return id_to_uri(prefix, id)


def is_bech32(id):
  if not id:
    return False

  id = id.removeprefix('nostr:')
  for prefix in BECH32_PREFIXES:
    if id.startswith(prefix):
      return True


def bech32_prefix_for(event):
  """Returns the bech32 prefix for a given event, based on its kind.

  Defined by NIP-19: https://nips.nostr.com/19

  Args:
    event (dict): Nostr event

  Returns:
    str: bech32 prefix
  """
  return {
    KIND_NOTE: 'note',      # NIP-10
    KIND_PROFILE: 'nprofile',  # NIP-01
  }.get(event['kind'], 'nevent')


def uri_to_id(uri):
  """Converts a nostr: URI with bech32-encoded id to a hex sha256 hash id.

  Based on NIP-21.

  Args:
    uri (str)

  Returns:
    str: hex
  """
  if not uri:
    return uri

  return bech32_decode(uri.removeprefix('nostr:'))


def id_to_uri(prefix, id):
  """Converts a hex sha256 hash id to a nostr: URI with bech32-encoded id.

  Based on NIP-21.

  Args:
    prefix (str)
    id (str): hex

  Returns:
    str: bech32-encoded
  """
  return 'nostr:' + bech32_encode(prefix, id)


def bech32_decode(val):
  """Converts a bech32-encoded string to its corresponding hex string.

  Based on NIP-19.

  Args:
    val (str): bech32

  Returns:
    str: hex
  """
  if not val or not is_bech32(val):
    return val

  prefix, data = bech32.bech32_decode(val)
  return bytes(bech32.convertbits(data, 5, 8, pad=False)).hex()


def bech32_encode(prefix, hex):
  """Converts a hex string to a bech32-encoded string.

  Based on NIP-19.

  Args:
    prefix (str)
    hex (str)

  Returns:
    str: bech32
  """
  if not hex:
    return hex

  data = bech32.convertbits(bytes.fromhex(hex), 8, 5)
  return bech32.bech32_encode(prefix, data)


def nip05_to_npub(nip05):
  """Resolves a NIP-05 identifier or domain to a bech32-encoded npub public key.

  https://nips.nostr.com/5

  Args:
    nip05 (str): NIP-05 identifier, e.g. "alice@example.com" or "_@example.com"

  Returns:
    str: bech32-encoded npub public key

  Raises:
    ValueError: if nip05 is invalid format or user not found
    requests.HTTPError: if HTTP request fails
  """
  parts = nip05.split('@')
  if len(parts) == 1:
    domain = parts[0]
    user = '_'
  elif len(parts) == 2:
    user, domain = parts
  else:
    raise ValueError(f'Invalid NIP-05 identifier: {nip05}')

  if not user or not domain:
    raise ValueError(f'Invalid NIP-05 identifier: {nip05}')

  url = f'https://{domain}/.well-known/nostr.json?name={user}'

  resp = util.requests_get(url, timeout=HTTP_TIMEOUT)
  resp.raise_for_status()
  data = resp.json()

  if not (pubkey := data.get('names', {}).get(user)):
    raise ValueError(f'User {user} not found at {domain}')

  # convert hex pubkey to npub
  return id_to_uri('npub', pubkey).removeprefix('nostr:')


def id_and_sign(event, privkey):
  """Populates a Nostr event's id and signature, in place.

  Args:
    event (dict)
    privkey (str): bech32-encoded nsec private key

  Returns:
    dict: event, populated with ``id`` and ``sig`` fields
  """
  assert privkey.startswith('nsec') or privkey.startswith('nostr:nsec'), privkey
  privkey = uri_to_id(privkey)
  assert len(privkey) == 64, privkey
  assert not event.get('id') and not event.get('sig'), event

  event['id'] = id_for(event)
  key = secp256k1.PrivateKey(privkey=privkey, raw=False)
  event['sig'] = key.schnorr_sign(bytes.fromhex(event['id']), None, raw=True).hex()
  return event


def verify(event):
  """Verifies a Nostr event's signature using the key in its ``pubkey`` field.

  Args:
    event (dict)

  Returns:
    bool: True if the signature is valid, False otherwise, eg if the signature is
      invalid, or if the ``id`` or ``sig`` or ``pubkey`` fields are missing, or if
      ``id`` is not the event's correct hash
  """
  if (not (sig := event.get('sig'))
      or not (id := event.get('id'))
      or not (pubkey := event.get('pubkey'))):
    return False

  if id != id_for(event):
    return False

  # secp256k1-py generates and expects 33-byte public keys, not 32. the difference
  # seems to be a prefix byte that's always either 0x02 or 0x03. not sure why, but it
  # doesn't seem to matter, we can just arbitrarily tack 0x02 onto a 32-byte key and
  # it still generates and verifies signatures fine.
  # https://github.com/snarfed/bridgy-fed/issues/446#issuecomment-2925960330
  if len(pubkey) != 64:
    return False

  try:
    key = secp256k1.PublicKey(bytes.fromhex('02' + pubkey), raw=True)
    return key.schnorr_verify(bytes.fromhex(id), bytes.fromhex(sig), None, raw=True)
  except (TypeError, ValueError):
    return False


def pubkey_from_privkey(privkey):
  """Returns the hex-encoded public key for a hex-encoded private key.

  Removes the leading 0x02 or 0x03 byte prefix that secp256k1-py includes.
  Background:
  https://github.com/snarfed/bridgy-fed/issues/446#issuecomment-2925960330

  Note that :func:`verify` does the inverse; it adds a 0x02 prefix internally, which
  secp256k1-py needs to load the public key.

  Args:
    privkey (str): hex secp256k1 private key

  Returns:
    str: corresponding hex secp256k1 public key
  """
  privkey = secp256k1.PrivateKey(bytes.fromhex(privkey), raw=True)
  pubkey = privkey.pubkey.serialize().hex()[2:]
  assert len(pubkey) == 64
  return pubkey


def from_as1(obj, privkey=None, remote_relay='', from_protocol=None):
  """Converts an ActivityStreams 1 activity or object to a Nostr event.

  Args:
    obj (dict): AS1 activity or object
    privkey (str): optional bech32-encoded private key to sign the event with. Also
      used to set the output event's ``pubkey`` field if ``obj`` doesn't have an
      ``nsec`` id
    remote_relays (sequence of str): optional sequence of remote relays where the
      "target" of this object - followee, in-reply-to, repost-of, etc - can be
      fetched.
    from_protocol (str): optional source protocol for NIP-48 proxy tag. Supported
      values: 'activitypub', 'atproto', 'web'

  Returns:
    dict: Nostr event
  """
  type = as1.object_type(obj)
  id = obj.get('id')
  inner_obj = as1.get_object(obj)
  inner_hex_id = uri_to_id(inner_obj.get('id'))
  pubkey = uri_to_id(as1.get_owner(obj))

  if privkey:
    privkey = privkey.removeprefix('nostr:')
    if not pubkey:
      pubkey = pubkey_from_privkey(uri_to_id(privkey))

  content = (html_to_text(obj.get('content') or obj.get('summary'))
             or obj.get('displayName') or '')
  event = {
    'pubkey': pubkey,
    'content': content,
    'tags': [],
  }

  published = obj.get('published')
  if published:
    event['created_at'] = int(util.parse_iso8601(published).timestamp())

  # NIP-48 proxy tag
  if from_protocol and id and not id.startswith('nostr:'):
    event['tags'].append(['proxy', id, from_protocol])

  # types
  if type in as1.ACTOR_TYPES:
    content = {
      'name': obj.get('displayName'),
      'about': obj.get('summary'),
      'website': obj.get('url') or util.get_first(obj, 'urls'),
    }

    if username := obj.get('username'):
      if '@' in username:
        content['nip05'] = username
      elif re.fullmatch(util.DOMAIN_RE, username):
        content['nip05'] = f'_@{username}'

    for img in as1.get_objects(obj, 'image'):
      if url := img.get('url') or img.get('id'):
        field = 'banner' if img.get('objectType') == 'featured' else 'picture'
        content.setdefault(field, url)

    event.update({
      'kind': KIND_PROFILE,
      # don't escape Unicode chars!
      # https://github.com/nostr-protocol/nips/issues/354
      'content': json_dumps(util.trim_nulls(content), sort_keys=True,
                            ensure_ascii=False),
    })

    if id:
      event['pubkey'] = uri_to_id(id)

    for url in as1.object_urls(obj):
      for platform, base_url in PLATFORMS.items():
        # we don't known which URLs might be Mastodon, so don't try to guess
          if platform != 'mastodon' and url.startswith(base_url):
            event['tags'].append(
              ['i', f'{platform}:{url.removeprefix(base_url)}', '-'])

  elif type in ('post', 'update'):
    return from_as1(inner_obj, privkey=privkey, remote_relay=remote_relay,
                    from_protocol=from_protocol)

  elif type in ('article', 'note'):
    event.update({
      'kind': KIND_NOTE if type == 'note' else KIND_ARTICLE,
    })

    in_reply_to = as1.get_object(obj, 'inReplyTo')
    if in_reply_to:
      id = uri_to_id(in_reply_to.get('id'))
      # https://nips.nostr.com/10
      # Kind 1 events with e tags are replies to other kind 1 events. Kind 1 replies MUST NOT be used to reply to other kinds, use NIP-22 instead.
      # ["e", <event-id>, <relay-url>, <marker>, <pubkey>]
      # Where:
      #     <event-id> is the id of the event being referenced.
      #     <relay-url> is the URL of a recommended relay associated with the reference. Clients SHOULD add a valid <relay-url> field, but may instead leave it as "".
      #     <marker> is optional and if present is one of "reply", "root".
      #     <pubkey> is optional, SHOULD be the pubkey of the author of the referenced event
      event['tags'].append(['e', id, remote_relay, 'reply'])
      author = as1.get_object(in_reply_to, 'author').get('id')
      if author:
        event['tags'].append(['p', uri_to_id(orig_event.get('pubkey'))])

    if type == 'article' and published:
      event['tags'].append(['published_at', str(event['created_at'])])

    if title := obj.get('title'):
      event['tags'].extend([
        ['title', title],
        ['subject', title],  # NIP-14 subject tag
      ])

    if summary := obj.get('summary'):
      event['tags'].append(['summary', summary])

    for tag in util.get_list(obj, 'tags'):
      name = tag.get('displayName')
      if name and tag.get('objectType') == 'hashtag':
        event['tags'].append(['t', name])

    if location := as1.get_object(obj, 'location').get('displayName'):
      event['tags'].append(['location', location])

    # imeta tags for images, video, audio
    video_audio = [as1.get_object(att, 'stream')
                   for att in as1.get_objects(obj, 'attachments')]
    for img in as1.get_objects(obj, 'image') + video_audio:
      if url := img.get('url') or img.get('id'):
        tag = ['imeta', f'url {url}']
        if alt := img.get('displayName'):
          tag.append(f'alt {alt}')
        if mime := img.get('mimeType') or mimetypes.guess_type(url, strict=False)[0]:
          tag.append(f'm {mime}')
        event['tags'].append(tag)
        # add to text content if necessary
        if url not in event['content']:
          event['content'] += ' ' + url

  elif type == 'share':
    event.update({
      'kind': KIND_REPOST,
    })

    if inner_obj:
      orig_event = from_as1(inner_obj, from_protocol=from_protocol)
      event['content'] = json_dumps(orig_event, sort_keys=True, ensure_ascii=False)
      event['tags'] = [
        # https://nips.nostr.com/18
        # "The repost event MUST include an e tag with the id of the note that is being reposted. That tag MUST include a relay URL as its third entry to indicate where it can be fetched."
        ['e', orig_event.get('id'), remote_relay, 'mention'],
        ['p', orig_event.get('pubkey')],
      ]

  elif type in ('like', 'dislike', 'react'):
    event.update({
      'kind': KIND_REACTION,
      'content': '+' if type == 'like'
                 else '-' if type == 'dislike'
                 else obj.get('content'),
      'tags': [['e', inner_hex_id]],
    })

  elif type == 'delete':
    event.update({
      'kind': KIND_DELETE,
      # TODO: include kind of the object being deleted, in a `k` tag. we'd have
      # to fetch it first. :/
      'tags': [['e', inner_hex_id]],
    })

  elif type == 'follow':
    event.update({
      'kind': KIND_CONTACTS,
      # https://nips.nostr.com/2
      # Each tag entry should contain the key for the profile, a relay URL where events from that key can be found (can be set to an empty string if not needed), and a local name (or "petname") for that profile (can also be set to an empty string or not provided), i.e., ["p", <32-bytes hex key>, <main relay URL>, <petname>].
      'tags': [['p', uri_to_id(o['id']), remote_relay, o.get('displayName') or '']
               for o in as1.get_objects(obj) if o.get('id')]
    })

  else:
    raise NotImplementedError(f'Unsupported activity/object type: {type}')

  event = util.trim_nulls(event, ignore=['tags', 'content'])

  if privkey:
    id_and_sign(event, privkey)
  elif pubkey:
    event['id'] = id_for(event)

  return event


def to_as1(event):
  """Converts a Nostr event to an ActivityStreams 2 activity or object.

  Args:
    event (dict):  Nostr event

  Returns:
    dict: AS1 activity or object
  """
  if not event:
    return {}

  obj = {}
  if id := event.get('id'):
    obj['id'] = id_to_uri('nevent', id)

  kind = event['kind']
  tags = event.get('tags', [])
  content = event.get('content')

  if kind == KIND_PROFILE:  # profile
    content = json_loads(content) if content else {}
    nip05_domain = (content['nip05'].removeprefix('_@')
                    if isinstance(content.get('nip05'), str)
                    else '')
    obj.update({
      'objectType': 'person',
      'id': id_to_uri('npub', event['pubkey']),
      'displayName': content.get('display_name') or content.get('name'),
      'summary': content.get('about'),
      'username': nip05_domain,
      'urls': [],
    })

    obj['image'] = []
    if picture := content.get('picture'):
      obj['image'].append(picture)
    if banner := content.get('banner'):
      obj['image'].append({'url': banner, 'objectType': 'featured'})

    if website := content.get('website'):
      obj['url'] = website
      obj['urls'].append(website)

    for tag in tags:
      if tag[0] == 'i':
        platform, identity = tag[1].split(':')
        base_url = PLATFORMS.get(platform)
        if base_url:
          obj['urls'].append(base_url + identity)

  elif kind in (KIND_NOTE, KIND_ARTICLE):  # note, article
    obj.update({
      'objectType': 'note' if kind == KIND_NOTE else 'article',
      # TODO: render Markdown to HTML?
      'content': event.get('content'),
      'image': [],
      'attachments': [],
      'tags': [],
    })

    if id:
      obj['id'] = id_to_uri('note', id)

    pubkey = event.get('pubkey')
    if pubkey:
      obj['author'] = id_to_uri('npub', pubkey)

    for tag in tags:
      type = tag[0]
      if type == 'e' and tag[-1] == 'reply':
        obj['inReplyTo'] = id_to_uri('nevent', tag[1])
      elif type == 't' and len(tag) >= 2:
        obj['tags'].extend({'objectType': 'hashtag', 'displayName': t}
                           for t in tag[1:])
      elif type in ('title', 'summary'):
        obj[type] = tag[1]
      elif type == 'subject':  # NIP-14 subject tag
        obj.setdefault('title', tag[1])
      elif type == 'location':
        obj['location'] = {'displayName': tag[1]}
      elif type == 'imeta':
        metas = dict(val.split(maxsplit=1) for val in tag[1:])
        if url := metas.get('url'):
          mime = metas.get('m') or mimetypes.guess_type(url, strict=False)[0]
          type = mime.split('/')[0]
          if type == 'image':
            obj['image'].append({
              'objectType': 'image',
              'url': url,
              'mimeType': mime,
              'displayName': metas.get('alt'),
            })
          elif type in ('video', 'audio'):
            obj['attachments'].append({
              'objectType': type,
              'displayName': metas.get('alt'),
              'stream': {
                'url': url,
                'mimeType': mime,
              },
            })
          else:
            continue
          # remove from text content
          obj['content'] = obj['content'].replace(url, '').rstrip()

  elif kind in (KIND_REPOST, KIND_GENERIC_REPOST):  # repost
    obj.update({
      'objectType': 'activity',
      'verb': 'share',
    })
    for tag in tags:
      if tag[0] == 'e' and tag[-1] == 'mention':
        obj['object'] = id_to_uri('note', tag[1])
    if content and content.startswith('{'):
      obj['object'] = to_as1(json_loads(content))

  elif kind == KIND_REACTION:  # like/reaction
    obj.update({
      'objectType': 'activity',
    })

    if content == '+':
      obj['verb'] = 'like'
    elif content == '-':
      obj['verb'] = 'dislike'
    else:
      obj['verb'] = 'react'
      obj['content'] = content

    for tag in tags:
      if tag[0] == 'e':
        obj['object'] = id_to_uri('nevent', tag[1])

  elif kind == KIND_DELETE:  # delete
    obj.update({
      'objectType': 'activity',
      'verb': 'delete',
      'object': [],
      'content': content,
    })

    for tag in tags:
      # TODO: support NIP-33 'a' tags
      if tag[0] == 'e':
        obj['object'].append(id_to_uri('nevent', tag[1]))

  elif kind == KIND_CONTACTS:  # follow
    obj.update({
      'objectType': 'activity',
      'verb': 'follow',
      'object': [],
      'content': content,
    })

    for tag in tags:
      if tag[0] == 'p':
        name = tag[3] if len(tag) >= 4 else None
        id = id_to_uri('npub', tag[1])
        obj['object'].append({'id': id, 'displayName': name} if name else id)

  # common fields
  created_at = event.get('created_at')
  if created_at:
    obj['published'] = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()

  if isinstance(obj.get('object'), list) and len(obj['object']) == 1:
    obj['object'] = obj['object'][0]

  if obj.get('objectType') == 'activity' and (pubkey := event.get('pubkey')):
    obj['actor'] = id_to_uri('npub', pubkey)

  return util.trim_nulls(Source.postprocess_object(obj))


class Nostr(Source):
  """Nostr source class. See file docstring and :class:`Source` for details.

  Attributes:
    relays (sequence of str): relay hostnames
  """
  DOMAIN = None
  BASE_URL = None
  NAME = 'Nostr'

  def __init__(self, relays=(), privkey=None):
    """Constructor.

    Args:
      relays (sequence of str)
      privkey (str): optional bech32-encoded private key of the current user.
        Required by :meth:`create` in order to sign events.
    """
    self.relays = relays

    if privkey:
      assert is_bech32(privkey), privkey

    self.privkey = privkey
    self.hex_pubkey = pubkey_from_privkey(uri_to_id(privkey)) if privkey else None

  @classmethod
  def user_url(cls, nprofile):
    nprofile = nprofile.removeprefix('nostr:')
    assert nprofile.startswith('nprofile')
    return f'https://coracle.social/people/{nprofile}'

  def get_actor(self, user_id=None):
    """Fetches and returns a Nostr user profile.

    Args:
      user_id (str): NIP-21 ``nostr:npub...``

    Returns:
      dict: AS1 actor object
    """
    if not user_id or not user_id.removeprefix('nostr:').startswith('npub'):
      raise ValueError(f'Expected nostr:npub..., got {user_id}')

    id = uri_to_id(user_id)

    # query for activities
    logger.debug(f'connecting to {self.relays[0]}')
    with connect(self.relays[0],
                 open_timeout=HTTP_TIMEOUT,
                 close_timeout=HTTP_TIMEOUT,
                 ) as websocket:
      events = self.query(websocket, {
        'authors': [id],
        'kinds': [KIND_PROFILE],
      })

    if events:
      # will we ever get multiple here? if so, assume the last is the most recent?
      return to_as1(events[-1])

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, fetch_replies=False,
                              fetch_likes=False, fetch_shares=False,
                              include_shares=True, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              start_index=None, count=None, cache=None, **kwargs):
    """Fetches events and converts them to AS1 activities.

    See :meth:`Source.get_activities_response` for more information.
    """
    assert not start_index
    assert not cache
    assert not fetch_mentions
    assert not fetch_events

    # build query filter
    filter = {
      'limit': count or 20,
    }

    if activity_id:
      if is_bech32(activity_id):
        activity_id = uri_to_id(activity_id)
      filter['ids'] = [activity_id]

    if user_id:
      if is_bech32(user_id):
        user_id = uri_to_id(user_id)
      filter['authors'] = [user_id]

    if search_query:
      filter['search'] = search_query

    events = []

    # query for activities
    logger.debug(f'connecting to {self.relays[0]}')
    with connect(self.relays[0],
                 open_timeout=HTTP_TIMEOUT,
                 close_timeout=HTTP_TIMEOUT,
                 ) as websocket:
      events = self.query(websocket, filter)
      event_ids = [e['id'] for e in events]
      # maps raw Nostr id to activity
      activities = {uri_to_id(a['id']): a
                    for a in [to_as1(e) for e in events]}
      assert len(activities) == len(events)

      # query for replies/shares
      if event_ids and (fetch_replies or fetch_shares):
        for event in self.query(websocket, {'#e': event_ids}):
          obj = to_as1(event)
          if in_reply_to := obj.get('inReplyTo'):
            activity = activities.get(uri_to_id(in_reply_to))
            if activity:
              replies = activity.setdefault('replies', {
                'items': [],
                'totalItems': 0,
              })
              replies['items'].append(obj)
              replies['totalItems'] += 1
          elif obj.get('verb') == 'share':
            activity = activities.get(uri_to_id(as1.get_object(obj).get('id')))
            if activity:
              activity.setdefault('tags', []).append(obj)

    return self.make_activities_base_response(util.trim_nulls(activities.values()))

  def query(self, websocket, filter):
    """Runs a Nostr ``REQ`` query on an open websocket.

    Sends the query, collects the responses, and closes the ``REQ`` subscription.
    If ``limit`` is not set on the filter, it defaults to 20.

    Args:
      websocket (websockets.sync.client.ClientConnection)
      filter (dict):  NIP-01 ``REQ`` filter
      limit (int)

    Returns:
      list of dict: Nostr events
    """
    limit = filter.setdefault('limit', 20)

    subscription = secrets.token_urlsafe(16)
    req = ['REQ', subscription, filter]

    try:
      logger.debug(f'{websocket.remote_address} <= {req}')
      websocket.send(json_dumps(req))
    except ConnectionClosedOK as err:
      logger.warning(err)
      return []

    events = []
    try:
      while True:
        msg = websocket.recv(timeout=HTTP_TIMEOUT)
        logger.debug(f'{websocket.remote_address} => {msg}')

        resp = json_loads(msg)
        if resp[:3] == ['OK', subscription, False]:
          return events
        elif resp[:2] == ['EVENT', subscription]:
          event = resp[2]
          if verify(event):
            events.append(event)
          else:
            logger.warning(f'Invalid signature for event {event.get("id")}')
        elif resp[0] == 'AUTH' and len(resp) >= 2:
          auth = ['AUTH', id_and_sign({
            'kind': KIND_AUTH,
            'pubkey': self.hex_pubkey,
            'content': '',
            'tags': [
              ['relay', f'wss://{websocket.remote_address[0]}/'],
              ['challenge', resp[1]],
            ],
          }, self.privkey)]
          logger.debug(f'{websocket.remote_address} <= {auth}')
          websocket.send(json_dumps(auth))
        elif len(events) >= limit or resp[:2] == ['EOSE', subscription]:
          break

      close = ['CLOSE', subscription]
      logger.debug(f'{websocket.remote_address} <= {close}')
      websocket.send(json_dumps(close))

    except ConnectionClosedOK as err:
      logger.warning(err)

    return events

  def create(self, obj, include_link=OMIT_LINK, ignore_formatting=False):
    """Creates a new object: a post, comment, like, repost, etc.

    See :meth:`Source.create` docstring for details.
    """
    assert self.privkey
    type = as1.object_type(obj)
    url = obj.get('url')
    is_reply = type == 'comment' or obj.get('inReplyTo')
    base_obj = self.base_object(obj)
    base_url = base_obj.get('url')
    prefer_content = type == 'note' or (base_url and is_reply)

    event = from_as1(obj, privkey=self.privkey)
    content = self._content_for_create(
      obj, ignore_formatting=ignore_formatting, prefer_name=not prefer_content) or ''
    if include_link == INCLUDE_LINK and url:
      content += '\n' + url
    event['content'] = content

    event.setdefault('pubkey', self.hex_pubkey)
    event['id'] = id_for(event)

    missing = (set(('content', 'created_at', 'kind', 'id', 'pubkey', 'tags'))
               - event.keys())
    assert not missing, f'missing {missing}'

    logger.debug(f'connecting to {self.relays[0]}')
    with connect(self.relays[0],
                 open_timeout=HTTP_TIMEOUT,
                 close_timeout=HTTP_TIMEOUT,
                 ) as websocket:
      create = ['EVENT', event]
      logger.debug(f'{websocket.remote_address} <= {create}')
      try:
        websocket.send(json_dumps(create))
        msg = websocket.recv(timeout=HTTP_TIMEOUT)
      except ConnectionClosedOK as cc:
        logger.warning(cc)
        return

    resp = json_loads(msg)
    if resp[:3] == ['OK', event['id'], True]:
      return creation_result(event)

    return creation_result(error_plain=resp[-1], abort=True)

  def delete(self, id):
    """Deletes a post.

    Args:
      id (str): bech32-encoded id of the event to delete
    """
    return self.create({
      'objectType': 'activity',
      'verb': 'delete',
      'object': id,
      'published': util.now(tz=timezone.utc).isoformat(),
    })

  @classmethod
  def _postprocess_base_object(cls, obj):
    # don't mess with ids
    return obj
