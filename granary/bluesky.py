"""Bluesky source class.

https://bsky.app/
https://atproto.com/lexicons/app-bsky-actor
https://github.com/bluesky-social/atproto/tree/main/lexicons/app/bsky
"""
import logging

from oauth_dropins.webutil import util


def from_as1(obj):
  """Converts an AS1 object to a Bluesky object.

  The objectType field is required.

  Args:
    profile: dict, AS1 object

  Returns: dict, app.bsky.* object

  Raises:
    ValueError
    if the objectType field is missing or unsupported
  """
  type = obj.get('objectType')
  if not type:
    raise ValueError('AS1 object missing objectType field')

  # TODO: once we're on Python 3.10, switch this to a match statement!
  if type == 'person':
    ret = {
      '$type': 'app.bsky.actor.profile',
      'displayName': obj.get('displayName'),
      'description': obj.get('summary'),
      'avatar': util.get_url(obj, 'image'),
    }

  elif type in ('article', 'mention', 'note'):
    entities = []
    for tag in util.get_list(obj, 'tags'):
      url = tag.get('url')
      if url:
        try:
          start = int(tag.get('startIndex'))
          end = start + int(tag.get('length'))
        except ValueError:
            start = end = None
        entities.append({
          'type': 'link',
          'value': url,
          'index': {
            'start': start,
            'end': end,
          },
        })

    ret = {
      '$type': 'app.bsky.feed.post',
      'text': obj.get('content'),
      'createdAt': obj.get('published'),
      'embed': {
        'images': util.get_urls(obj, 'image'),
      },
      'entities': entities,
    }

  elif type == 'share':
    ret = {
      '$type': 'app.bsky.',
    }

  elif type == 'follow':
    ret = {
      '$type': 'app.bsky.',
    }

  else:
    raise ValueError(f'AS1 object has unknown objectType: {type}')

  return util.trim_nulls(ret)


def to_as1(obj):
  """Converts a Bluesky object to an AS1 object.

  The $type field is required.

  Args:
    profile: dict, app.bsky.* object

  Returns: dict, AS1 object

  Raises:
    ValueError
    if the $type field is missing or unsupported
  """
  type = obj.get('$type')
  if not type:
    raise ValueError('Bluesky object missing $type field')

  # TODO: once we're on Python 3.10, switch this to a match statement!
  if type == 'app.bsky.actor.profile':
    return {
    }
  elif type == 'app.bsky.feed.post':
    return {
    }
  elif type == 'app.bsky.feed.repost':
    return {
    }
  elif type == 'app.bsky.graph.follow':
    return {
    }

  raise ValueError(f'Bluesky object has unknown $type: {type}')


# class Bluesky(source.Source):
#   """Bluesky source class. See file docstring and Source class for details."""

#   DOMAIN = 'bsky.app'
#   BASE_URL = 'https://bsky.app'
#   NAME = 'Bluesky'
#   # OPTIMIZED_COMMENTS = None  # TODO

#   def __init__(self):
#     pass
