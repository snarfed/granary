"""Nostr."""
from datetime import datetime
from hashlib import sha256
import logging

from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads

from . import as1

logger = logging.getLogger(__name__)


def id_for(event):
  """Generates an id for a Nostr event.

  Args:
    event: dict, JSON Nostr event

  Returns: str, 32-character hex-encoded sha256 hash of the event, serialized
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


def from_as1(obj):
  """Converts an ActivityStreams 1 activity or object to a Nostr event.

  Args:
    obj: dict, AS1 activity or object

  Returns: dict, JSON Nostr event
  """
  type = as1.object_type(obj)
  ret = {}

  if type in as1.ACTOR_TYPES:
    ret = {
      'kind': 0,
      'content': json_dumps({
        'name': obj.get('displayName'),
        'about': obj.get('description'),
        'picture': util.get_url(obj, 'image'),
      }),
    }
  elif type in ('article', 'note'):
    published = obj.get('published')
    created_at = int(util.parse_iso8601(published).timestamp()) if published else None
    ret = {
      'kind': 1,
      'content': obj.get('content') or obj.get('summary') or obj.get('displayName'),
      'created_at': created_at,
    }

  return util.trim_nulls(ret)


def to_as1(event):
  """Converts a Nostr event to an ActivityStreams 2 activity or object.

  Args:
    event: dict, JSON Nostr event

  Returns: dict, AS1 activity or object
  """
  if not event:
    return {}

  ret = {}
  kind = event['kind']

  if kind == 0:  # profile
    content = json_loads(event.get('content')) or {}
    ret = {
      'objectType': 'person',
      'displayName': content.get('name'),
      'description': content.get('about'),
      'image': content.get('picture'),
    }
  elif kind == 1:  # note
    created_at = event.get('created_at')
    published = datetime.fromtimestamp(created_at).isoformat() if created_at else None
    ret = {
      'objectType': 'note',
      'content': event.get('content'),
      'published': published,
    }

  return util.trim_nulls(ret)
