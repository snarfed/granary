"""Nostr.

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
* 25: likes, emoji reactions
* 27: text notes
* 39: external identities

TODO:

* 01: relay protocol, both client and server?
* 05: DNS verification?
* 11: relay info (like nodeinfo)
* 12: tag queries
* 16, 33: ephemeral/replaceable events
* 27: user mentions, note/event mentions
* 32: tag activities
* 46: "Nostr Connect," signing proxy that holds user's keys
* 65: user relays. what would this be in AS1? anything?
"""
from datetime import datetime
from hashlib import sha256
import logging

import bech32
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads

from . import as1

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
    event: dict, JSON Nostr event

  Returns:
    str, 32-character hex-encoded sha256 hash of the event, serialized
    according to NIP-01
  """
  event.setdefault('tags', [])
  assert event.keys() == set(('content', 'created_at', 'kind', 'pubkey', 'tags'))
  return sha256(json_dumps([
    0,
    event['pubkey'],
    event['created_at'],
    event['kind'],
    event['tags'],
    event['content'],
  ]).encode()).hexdigest()


def uri_to_id(uri):
  """Converts a nostr: URI with bech32-encoded id to a hex sha256 hash id.

  Based on NIP-19 and NIP-21.

  Args:
    uri: str

  Returns:
    str
  """
  if not uri:
    return uri

  prefix, data = bech32.bech32_decode(uri.removeprefix('nostr:'))
  return bytes(bech32.convertbits(data, 5, 8, pad=False)).hex()


def id_to_uri(prefix, id):
  """Converts a hex sha256 hash id to a nostr: URI with bech32-encoded id.

  Based on NIP-19 and NIP-21.

  Args:
    prefix: str
    id: str

  Returns:
    str
  """
  if not id:
    return id

  data = bech32.convertbits(bytes.fromhex(id), 8, 5)
  return 'nostr:' + bech32.bech32_encode(prefix, data)


def from_as1(obj):
  """Converts an ActivityStreams 1 activity or object to a Nostr event.

  Args:
    obj: dict, AS1 activity or object

  Returns: dict, JSON Nostr event
  """
  type = as1.object_type(obj)
  event = {
    'id': uri_to_id(obj.get('id')),
    'pubkey': uri_to_id(as1.get_owner(obj)),
    'content': obj.get('content') or obj.get('summary') or obj.get('displayName'),
    'tags': [],
  }

  published = obj.get('published')
  if published:
    event['created_at'] = int(util.parse_iso8601(published).timestamp())

  # types
  if type in as1.ACTOR_TYPES:
    nip05 = obj.get('username', '')
    if '@' not in nip05:
      nip05 = f'_@{nip05}'
    event.update({
      'kind': 0,
      'pubkey': event['id'],
      'content': json_dumps({
        'name': obj.get('displayName'),
        'about': obj.get('description'),
        'picture': util.get_url(obj, 'image'),
        'nip05': nip05,
      }, sort_keys=True),
    })
    for url in as1.object_urls(obj):
      for platform, base_url in PLATFORMS.items():
        # we don't known which URLs might be Mastodon, so don't try to guess
          if platform != 'mastodon' and url.startswith(base_url):
            event['tags'].append(
              ['i', f'{platform}:{url.removeprefix(base_url)}', '-'])

  elif type in ('article', 'note'):
    event.update({
      'kind': 1 if type == 'note' else 30023,
    })
    # TODO: convert HTML to Markdown

    in_reply_to = as1.get_object(obj, 'inReplyTo')
    if in_reply_to:
      id = uri_to_id(in_reply_to.get('id'))
      event['tags'].append(['e', id, 'TODO relay', 'reply'])
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

  elif type == 'share':
    event.update({
      'kind': 6,
    })

    inner_obj = as1.get_object(obj)
    if inner_obj:
      orig_event = from_as1(inner_obj)
      event['content'] = json_dumps(orig_event, sort_keys=True)
      event['tags'] = [
        ['e', orig_event.get('id'), 'TODO relay', 'mention'],
        ['p', orig_event.get('pubkey')],
      ]

  elif type in ('like', 'dislike', 'react'):
    liked = as1.get_object(obj).get('id')
    event.update({
      'kind': 7,
      'content': '+' if type == 'like'
                 else '-' if type == 'dislike'
                 else obj.get('content'),
      'tags': [['e', uri_to_id(liked)]],
    })

  elif type == 'delete':
    event.update({
      'kind': 5,
      'tags': [['e', uri_to_id(as1.get_object(obj).get('id'))]],
    })

  elif type == 'follow':
    event.update({
      'kind': 3,
      'tags': [
        ['p', uri_to_id(o['id']), 'TODO relay', o.get('displayName') or '']
        for o in as1.get_objects(obj)
        if o.get('id')
      ],
    })

  return util.trim_nulls(event, ignore=['tags'])


def to_as1(event):
  """Converts a Nostr event to an ActivityStreams 2 activity or object.

  Args:
    event: dict, JSON Nostr event

  Returns: dict, AS1 activity or object
  """
  if not event:
    return {}

  kind = event['kind']
  id = event.get('id')
  tags = event.get('tags', [])
  content = event.get('content')
  obj = {
    'id': id_to_uri('nevent', id)
  }

  if kind == 0:  # profile
    content = json_loads(content) or {}
    obj.update({
      'objectType': 'person',
      'id': id_to_uri('npub', event['pubkey']),
      'displayName': content.get('name'),
      'description': content.get('about'),
      'image': content.get('picture'),
      'username': content.get('nip05', '').removeprefix('_@'),
      'urls': [],
    })
    for tag in tags:
      if tag[0] == 'i':
        platform, identity = tag[1].split(':')
        base_url = PLATFORMS.get(platform)
        if base_url:
          obj['urls'].append(base_url + identity)

  elif kind in (1, 30023):  # note, article
    obj.update({
      'objectType': 'note' if kind == 1 else 'article',
      'id': id_to_uri('note', id),
      # TODO: render Markdown to HTML
      'content': event.get('content'),
      'tags': [],
    })

    pubkey = event.get('pubkey')
    if pubkey:
      obj['author'] = {'id': id_to_uri('npub', pubkey)}

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

  elif kind in (6, 16):  # repost
    obj.update({
      'objectType': 'activity',
      'verb': 'share',
    })
    for tag in tags:
      if tag[0] == 'e' and tag[-1] == 'mention':
        obj['object'] = id_to_uri('note', tag[1])
    if content and content.startswith('{'):
      obj['object'] = to_as1(json_loads(content))

  elif kind == 7:  # like/reaction
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

  elif kind == 5:  # delete
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

  elif kind == 3:  # follow
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
    obj['published'] = datetime.fromtimestamp(created_at).isoformat()

  if isinstance(obj.get('object'), list) and len(obj['object']) == 1:
    obj['object'] = obj['object'][0]

  return util.trim_nulls(obj)
