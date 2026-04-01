"""Farcaster.

* https://farcaster.xyz/
* https://snapchain.farcaster.xyz/

TODO:
* change farcaster URIs to https://github.com/farcasterxyz/protocol/discussions/123
* use data_bytes, hash based on it
  https://github.com/farcasterxyz/protocol/discussions/87
* rel-alternate links via "Social Attestations." so complicated :(
  https://github.com/farcasterxyz/protocol/discussions/199
* mapping FIDs <=> DNS domains. unclear whether/how much this is adopted
  https://github.com/farcasterxyz/protocol/discussions/106
"""
import copy
from datetime import datetime, timezone
from itertools import zip_longest
import mimetypes

from oauth_dropins.webutil import util

from . import as1
from .generated.farcaster.message_pb2 import (
  FARCASTER_NETWORK_MAINNET,
  Message,
  MESSAGE_TYPE_CAST_ADD,
  MESSAGE_TYPE_REACTION_ADD,
  MESSAGE_TYPE_REACTION_REMOVE,
  REACTION_TYPE_LIKE,
  MESSAGE_TYPE_LINK_ADD,
  MESSAGE_TYPE_LINK_REMOVE,
  REACTION_TYPE_RECAST,
)


def to_as1(msg):
  """Converts a Farcaster Message protobuf to an ActivityStreams 1 object.

  Args:
    msg (message_pb2.Message): Farcaster Message protobuf

  Returns:
    dict: AS1 activity or object
  """
  if not msg or not msg.data:
    return {}

  data = msg.data
  obj = {}  # AS1 return value

  actor_fid = data.fid
  published = None
  if data.timestamp:
    published = datetime.fromtimestamp(data.timestamp, tz=timezone.utc).isoformat()

  msg_type = data.type

  # post
  if msg_type == MESSAGE_TYPE_CAST_ADD:
    cast = data.cast_add_body
    obj.update({
      'objectType': 'note',
      'content': cast.text,
      'content_is_html': False,
      'tags': [],
      'image': [],
      'attachments': [],
      'published': published,
    })

    if actor_fid:
      obj['author'] = f'farcaster:fid:{actor_fid}'

    if msg.hash:
      obj.update({
        'id': f'farcaster:cast:{msg.hash.hex()}',
        'url': f'https://farcaster.xyz/~/conversations/{msg.hash.hex()}',
      })

    if cast.mentions:
      for mention_fid, pos in zip_longest(cast.mentions, cast.mentions_positions):
        obj['tags'].append({
          'objectType': 'mention',
          'url': f'farcaster:fid:{mention_fid}',
          'startIndex': pos,
        })

    for embed in cast.embeds:
      if embed.HasField('url'):
        mimetype, _ = mimetypes.guess_type(embed.url)
        if mimetype and mimetype.startswith('image/'):
          obj['image'].append(embed.url)
        elif mimetype and mimetype.startswith('video/'):
          obj['attachments'].append({
            'objectType': 'video',
            'stream': {'url': embed.url},
          })
        else:
          obj['attachments'].append({
            'objectType': 'link',
            'url': embed.url,
          })
      elif embed.HasField('cast_id'):
        obj['attachments'].append({
          'objectType': 'note',
          'id': f'farcaster:cast:{embed.cast_id.hash.hex()}',
          'author': f'farcaster:fid:{embed.cast_id.fid}',
        })

    if cast.HasField('parent_cast_id'):
      obj['inReplyTo'] = {
        'id': f'farcaster:cast:{cast.parent_cast_id.hash.hex()}',
        'author': f'farcaster:fid:{cast.parent_cast_id.fid}',
      }
    elif cast.HasField('parent_url'):
      obj['inReplyTo'] = cast.parent_url

  # like, repost
  elif msg_type in (MESSAGE_TYPE_REACTION_ADD, MESSAGE_TYPE_REACTION_REMOVE):
    reaction = data.reaction_body
    verb = 'like' if reaction.type == REACTION_TYPE_LIKE else 'share'

    if reaction.HasField('target_cast_id'):
      target_obj = {
        'id': f'farcaster:cast:{reaction.target_cast_id.hash.hex()}',
        'author': f'farcaster:fid:{reaction.target_cast_id.fid}',
      }
    # elif reaction.HasField('target_url'):
    #   target_obj = reaction.target_url

    obj = {
      'objectType': 'activity',
      'verb': verb,
      'actor': f'farcaster:fid:{actor_fid}',
      'object': target_obj,
    }
    if msg_type == MESSAGE_TYPE_REACTION_REMOVE:
      obj = {
        'objectType': 'activity',
        'verb': 'undo',
        'actor': f'farcaster:fid:{actor_fid}',
        'object': obj,
      }

    obj['published'] = published
    if msg.hash:
      obj['id'] = f'farcaster:reaction:{msg.hash.hex()}'

  # follow, unfollow
  elif msg_type in (MESSAGE_TYPE_LINK_ADD, MESSAGE_TYPE_LINK_REMOVE):
    obj = {
      'objectType': 'activity',
      'verb': 'follow',
      'actor': f'farcaster:fid:{actor_fid}',
      'object': f'farcaster:fid:{data.link_body.target_fid}',
    }

    if msg_type == MESSAGE_TYPE_LINK_REMOVE:
      obj = {
      'objectType': 'activity',
        'verb': 'undo',
        'actor': f'farcaster:fid:{actor_fid}',
        'object': obj,
      }

    obj['published'] = published
    if timestamp := data.link_body.displayTimestamp:
      obj['published'] = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

  return util.trim_nulls(obj)


def from_as1(obj):
  """Converts an ActivityStreams 1 activity or object to a Farcaster Message.

  Args:
    obj (dict): AS1 activity or object

  Returns:
    message_pb2.Message: Farcaster Message protobuf
  """
  obj = copy.deepcopy(obj)
  msg = Message()
  data = msg.data

  type = as1.object_type(obj)
  if type in ('post', 'update'):
    type = as1.object_type(as1.get_object(obj))

  inner_obj = as1.get_object(obj)
  inner_type = as1.object_type(inner_obj)
  author = as1.get_owner(obj)
  if author and author.startswith('farcaster:fid:'):
    data.fid = int(author.removeprefix('farcaster:fid:'))

  data.network = FARCASTER_NETWORK_MAINNET

  published = (util.parse_iso8601(obj['published']) if obj.get('published')
               else util.now(tz=timezone.utc))
  data.timestamp = int(published.timestamp())

  # posts
  if type in ('note', 'article', 'comment'):
    data.type = MESSAGE_TYPE_CAST_ADD
    cast = data.cast_add_body

    content = obj.get('content', '')
    cast.text = content

    # mentions
    mentions = []
    mention_positions = []
    for tag in as1.get_objects(obj, 'tags'):
      if tag.get('objectType') == 'mention':
        url = tag.get('url', '')
        if url.startswith('farcaster:fid:'):
          fid = int(url.removeprefix('farcaster:fid:'))
          cast.mentions.append(fid)
          if 'startIndex' in tag:
            cast.mentions_positions.append(tag['startIndex'])

    # images
    for img in as1.get_objects(obj, 'image'):
      if url := as1.get_url(img) or img.get('id'):
        cast.embeds.add().url = url

    for att in as1.get_objects(obj, 'attachments'):
      att_type = as1.object_type(att)
      if att_type == 'note':
        id = att.get('id', '')
        author = att.get('author', '')
        if id.startswith('farcaster:cast:') and author.startswith('farcaster:fid:'):
          embed = cast.embeds.add()
          embed.cast_id.fid = int(author.removeprefix('farcaster:fid:'))
          embed.cast_id.hash = bytes.fromhex(id.removeprefix('farcaster:cast:'))
      elif att_type in ('video', 'audio'):
        if url := as1.get_url(util.get_first(att, 'stream')):
          cast.embeds.add().url = url
      elif att_type == 'link':
        if url := as1.get_url(att):
          cast.embeds.add().url = url

    # reply
    if ((in_reply_to := as1.get_object(obj, 'inReplyTo'))
            and (id := in_reply_to.get('id'))):
        if id.startswith('farcaster:cast:'):
          if ((author := in_reply_to.get('author', ''))
              and author.startswith('farcaster:fid:')):
            cast.parent_cast_id.fid = int(author.removeprefix('farcaster:fid:'))
            cast.parent_cast_id.hash = bytes.fromhex(id.removeprefix('farcaster:cast:'))
        elif util.is_web(id):
          cast.parent_url = id

  # likes/reposts
  elif type in ('like', 'share'):
    data.type = MESSAGE_TYPE_REACTION_ADD
    reaction = data.reaction_body
    reaction.type = REACTION_TYPE_LIKE if type == 'like' else REACTION_TYPE_RECAST

    if target := inner_obj.get('id', ''):
      if target.startswith('farcaster:cast:'):
        author = inner_obj.get('author', '')
        if author.startswith('farcaster:fid:'):
          reaction.target_cast_id.fid = int(author.removeprefix('farcaster:fid:'))
          reaction.target_cast_id.hash = bytes.fromhex(target.removeprefix('farcaster:cast:'))
      elif util.is_web(target):
        reaction.target_url = target

  # follow
  elif type == 'follow':
    data.type = MESSAGE_TYPE_LINK_ADD
    data.link_body.type = 'TODO'
    if inner_obj_id := inner_obj.get('id'):
      data.link_body.target_fid = int(inner_obj_id.removeprefix('farcaster:fid:'))
    data.link_body.displayTimestamp = data.timestamp

  # undo like/repost
  elif type == 'undo' and inner_type in ('like', 'share'):
    data.type = MESSAGE_TYPE_REACTION_REMOVE
    data.reaction_body.MergeFrom(from_as1(inner_obj).data.reaction_body)

  # unfollow
  elif type == 'undo' and inner_type == 'follow':
    data.type = MESSAGE_TYPE_LINK_REMOVE
    data.link_body.type = 'TODO'
    if followee_id := as1.get_object(inner_obj).get('id'):
      data.link_body.target_fid = int(followee_id.removeprefix('farcaster:fid:'))
    data.link_body.displayTimestamp = data.timestamp

  return msg
