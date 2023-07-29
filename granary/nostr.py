"""Nostr.

NIPS implemented:

* 01: base protocol, events, profile metadata
* 05: domain identifiers
* 09: deletes
* 10: replies, mentions
* 12: articles
* 14: subject tag in notes
* 18: reposts, including 10 for e/p tags
* 19: bech32-encoded ids
* 21: nostr: URI scheme
* 25: likes, emoji reactions
* 27: text notes
* 39: external identities
"""
from datetime import datetime
from hashlib import sha256
import logging

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


def id_from_as1(id):
  """Converts a Nostr bech32 id to a hex sha256 hash id.

  May optionally have nostr: URI prefix and/or bech32 plain or TLV prefix.

  Based on NIP-19 and NIP-21.
  """
  if not id:
    return id

  if id.startswith('nostr:'):
    id = id.removeprefix('nostr:')

  for prefix in BECH32_PREFIXES:
    id = id.removeprefix(prefix)

  # TODO: bech32-decode
  return id


def from_as1(obj):
  """Converts an ActivityStreams 1 activity or object to a Nostr event.

  Args:
    obj: dict, AS1 activity or object

  Returns: dict, JSON Nostr event
  """
  type = as1.object_type(obj)
  event = {
    'id': id_from_as1(obj.get('id')),
    'pubkey': id_from_as1(as1.get_owner(obj)),
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
      id = id_from_as1(in_reply_to.get('id'))
      event['tags'].append(['e', id, 'TODO relay', 'reply'])
      author = as1.get_object(in_reply_to, 'author').get('id')
      if author:
        event['tags'].append(['p', id_from_as1(orig_event.get('pubkey'))])

    if type == 'article' and published:
      event['tags'].append(['published_at', str(event['created_at'])])

    if title := obj.get('title'):
      event['tags'].extend([
        ['title', title],
        ['subject', title],  # NIP-14 subject tag
      ])

    if summary := obj.get('summary'):
      event['tags'].append(['summary', summary])

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
      'tags': [['e', id_from_as1(liked)]],
    })

  elif type == 'delete':
    event.update({
      'kind': 5,
      'tags': [['e', id_from_as1(as1.get_object(obj).get('id'))]],
    })

  return util.trim_nulls(event)


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
    'id': f'nostr:nevent{id}',
  }

  if kind == 0:  # profile
    content = json_loads(content) or {}
    obj.update({
      'objectType': 'person',
      'id': f'nostr:npub{event["pubkey"]}',
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
      'id': f'nostr:note{id}',
      # TODO: render Markdown to HTML
      'content': event.get('content'),
    })

    pubkey = event.get('pubkey')
    if pubkey:
      obj['author'] = {'id': f'nostr:npub{pubkey}'}

    for tag in tags:
      if tag[0] == 'e' and tag[-1] == 'reply':
        # TODO: bech32-encode id
        obj['inReplyTo'] = f'nostr:note{tag[1]}'
      elif tag[0] in ('title', 'summary'):
        obj[tag[0]] = tag[1]
      elif tag[0] == 'subject':  # NIP-14 subject tag
        obj.setdefault('title', tag[1])

  elif kind in (6, 16):  # repost
    obj.update({
      'objectType': 'activity',
      'verb': 'share',
    })
    for tag in tags:
      if tag[0] == 'e' and tag[-1] == 'mention':
        # TODO: bech32-encode id
        obj['object'] = f'nostr:note{tag[1]}'
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
        # TODO: bech32-encode id
        obj['object'] = f'nostr:nevent{tag[1]}'

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
        obj['object'].append(f'nostr:nevent{tag[1]}')

    if len(obj['object']) == 1:
      obj['object'] = obj['object'][0]

  # common fields
  created_at = event.get('created_at')
  if created_at:
    obj['published'] = datetime.fromtimestamp(created_at).isoformat()

  return util.trim_nulls(obj)
