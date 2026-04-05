"""Farcaster.

* https://farcaster.xyz/
* https://snapchain.farcaster.xyz/

TODO:
* fix url field
* change farcaster URIs to https://github.com/farcasterxyz/protocol/discussions/123
* use data_bytes, hash based on it
  https://github.com/farcasterxyz/protocol/discussions/87
* rel-alternate links via "Social Attestations." so complicated :(
  https://github.com/farcasterxyz/protocol/discussions/199
* mapping FIDs <=> DNS domains. unclear whether/how much this is adopted
  https://github.com/farcasterxyz/protocol/discussions/106
* user location, from https://github.com/farcasterxyz/protocol/discussions/196
  (it's a geo:... URL string, https://tools.ietf.org/html/rfc5870, in
  USER_DATA_TYPE_LOCATION)
"""
import copy
from datetime import datetime, timezone
from itertools import zip_longest
import logging
import mimetypes

import grpc
from oauth_dropins.webutil import util

from . import as1, source
from .generated.farcaster import rpc_pb2_grpc
from .generated.farcaster.request_response_pb2 import (
  FidRequest,
  MessagesResponse,
  ReactionsByFidRequest,
)
from .generated.farcaster.message_pb2 import (
  CastId,
  FARCASTER_NETWORK_MAINNET,
  Message,
  MESSAGE_TYPE_CAST_ADD,
  MESSAGE_TYPE_CAST_REMOVE,
  MESSAGE_TYPE_REACTION_ADD,
  MESSAGE_TYPE_REACTION_REMOVE,
  MESSAGE_TYPE_USER_DATA_ADD,
  REACTION_TYPE_LIKE,
  MESSAGE_TYPE_LINK_ADD,
  MESSAGE_TYPE_LINK_REMOVE,
  REACTION_TYPE_RECAST,
  USER_DATA_TYPE_BANNER,
  USER_DATA_TYPE_BIO,
  USER_DATA_TYPE_DISPLAY,
  USER_DATA_TYPE_PFP,
  USER_DATA_TYPE_URL,
  USER_DATA_TYPE_USERNAME,
)

# Maps USER_DATA_TYPE_* constant to AS1 actor field name.
USER_DATA_TYPE_TO_AS1 = {
  USER_DATA_TYPE_DISPLAY:  'displayName',
  USER_DATA_TYPE_USERNAME: 'username',
  USER_DATA_TYPE_BIO:      'summary',
  USER_DATA_TYPE_PFP:      'image',
  USER_DATA_TYPE_BANNER:   'image',
  USER_DATA_TYPE_URL:      'url',
}

DEFAULT_SNAPCHAIN_HOST = 'crackle.farcaster.xyz'
DEFAULT_SNAPCHAIN_PORT = 3383

logger = logging.getLogger(__name__)


def to_as1(msg):
  """Converts a Farcaster protobuf to an ActivityStreams 1 object or actor.

  Args:
    msg (message_pb2.Message or MessagesResponse):
      Farcaster Message protobuf or MessagesResponse (user data messages)

  Returns:
    dict: AS1 activity, object, or actor
  """
  # actor, from GetUserDataByFid response
  if isinstance(msg, MessagesResponse):
    fid = msg.messages[0].data.fid if msg.messages else None
    actor = {
      'objectType': 'person',
      'id': f'farcaster:fid:{fid}' if fid else None,
      'url': Farcaster.user_url(fid) if fid else None,
      'image': [],
    }

    for m in msg.messages:
      if m.data.type == MESSAGE_TYPE_USER_DATA_ADD:
        body = m.data.user_data_body
        if field := USER_DATA_TYPE_TO_AS1.get(body.type):
          if field == 'image':
            actor['image'].append({'objectType': 'featured', 'url': body.value}
                                  if body.type == USER_DATA_TYPE_BANNER
                                  else body.value)
          else:
            actor[field] = body.value

    return util.trim_nulls(actor)

  # all other object types
  if not msg or not isinstance(msg, Message) or not msg.data:
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

  # delete
  elif msg_type == MESSAGE_TYPE_CAST_REMOVE:
    obj = {
      'objectType': 'activity',
      'verb': 'delete',
      'actor': f'farcaster:fid:{actor_fid}',
      'object': f'farcaster:cast:{data.cast_remove_body.target_hash.hex()}',
      'published': published,
    }

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

  # follow, block, unfollow, unblock
  elif msg_type in (MESSAGE_TYPE_LINK_ADD, MESSAGE_TYPE_LINK_REMOVE):
    obj = {
      'objectType': 'activity',
      'verb': data.link_body.type,
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
  inner_id = inner_obj.get('id')
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

    if inner_id:
      if inner_id.startswith('farcaster:cast:'):
        author = inner_obj.get('author', '')
        if author.startswith('farcaster:fid:'):
          reaction.target_cast_id.fid = int(author.removeprefix('farcaster:fid:'))
          reaction.target_cast_id.hash = bytes.fromhex(
            inner_id.removeprefix('farcaster:cast:'))
      elif util.is_web(inner_id):
        reaction.target_url = inner_id

  # follow, block
  elif type in ('follow', 'block'):
    data.type = MESSAGE_TYPE_LINK_ADD
    data.link_body.type = type
    if inner_id:
      data.link_body.target_fid = int(inner_id.removeprefix('farcaster:fid:'))
    data.link_body.displayTimestamp = data.timestamp

  # delete post
  elif type == 'delete' and inner_id and inner_id.startswith('farcaster:cast:'):
    data.type = MESSAGE_TYPE_CAST_REMOVE
    data.cast_remove_body.target_hash = bytes.fromhex(
      inner_id.removeprefix('farcaster:cast:'))

  # undo like/repost
  elif type == 'undo' and inner_type in ('like', 'share'):
    data.type = MESSAGE_TYPE_REACTION_REMOVE
    data.reaction_body.MergeFrom(from_as1(inner_obj).data.reaction_body)

  # unfollow, unblock
  elif type == 'undo' and inner_type in ('follow', 'block'):
    data.type = MESSAGE_TYPE_LINK_REMOVE
    data.link_body.type = inner_type
    if followee_id := as1.get_object(inner_obj).get('id'):
      data.link_body.target_fid = int(followee_id.removeprefix('farcaster:fid:'))
    data.link_body.displayTimestamp = data.timestamp

  return msg


class Farcaster(source.Source):
  """Farcaster source class. See file docstring and :class:`Source` for details.

  Attributes:
    _hub (rpc_pb2_grpc.HubServiceStub): gRPC client
  """

  DOMAIN = 'farcaster.xyz'
  BASE_URL = 'https://farcaster.xyz/'
  NAME = 'Farcaster'

  def __init__(self, host=DEFAULT_SNAPCHAIN_HOST, port=DEFAULT_SNAPCHAIN_PORT):
    """Constructor.

    Args:
      host (str): snapchain node host, eg ``snapchain.farcaster.xyz``
      port (int): snapchain node port, default 3383
    """
    assert host
    assert port
    addr = f'{host}:{port}'
    logger.info(f'Connecting to Farcaster Snapchain node {addr}')
    channel = grpc.secure_channel(addr, grpc.ssl_channel_credentials())
    self._hub = rpc_pb2_grpc.HubServiceStub(channel)

  @classmethod
  def user_url(cls, fid):
    """Returns the Farcaster URL for a user with the given FID.

    Args:
      fid (int): Farcaster user ID

    Returns:
      str: URL
    """
    return f'https://farcaster.xyz/~/user/{fid}'

  def get_actor(self, fid):
    """Fetches and returns a Farcaster user as an AS1 actor dict.

    Args:
      fid (int): Farcaster user ID

    Returns:
      dict: AS1 actor
    """
    resp = self._hub.GetUserDataByFid(FidRequest(fid=fid))
    return to_as1(resp)

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, fetch_replies=False,
                              fetch_likes=False, fetch_shares=False,
                              include_shares=True, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              start_index=0, count=0, **kwargs):
    """Fetches casts and reactions and returns them as AS1 activities.

    See :meth:`Source.get_activities_response` for details. ``group_id``,
    ``fetch_replies``, ``fetch_events``, and ``search_query`` are not yet supported.
    ``user_id`` is a Farcaster FID (integer or string).
    """
    if user_id and not util.is_int(user_id):
      raise ValueError(f'user_id must be a Farcaster FID (integer), got {user_id!r}')
    elif activity_id and not user_id:
      raise ValueError('activity_id requires user_id')

    fid = int(user_id) if user_id else None
    page_kwargs = {'page_size': count} if count else {}
    activities = []

    def add_activities(resp):
      for msg in resp.messages:
        obj = to_as1(msg)
        if obj.get('objectType') != 'activity':
          obj = {
            'objectType': 'activity',
            'verb': 'post',
            'object': obj,
            'actor': obj.get('author'),
          }
        activities.append(self.postprocess_activity(obj))

    if fid:
      if activity_id:
        cast_hash = bytes.fromhex(activity_id.removeprefix('farcaster:cast:'))
        add_activities(MessagesResponse(
          messages=[self._hub.GetCast(CastId(fid=fid, hash=cast_hash))]))
      else:
        add_activities(self._hub.GetCastsByFid(FidRequest(fid=fid, **page_kwargs)))

      if fetch_mentions:
        add_activities(self._hub.GetCastsByMention(FidRequest(fid=fid, **page_kwargs)))

      if fetch_likes:
        add_activities(self._hub.GetReactionsByFid(ReactionsByFidRequest(
          fid=fid, reaction_type=REACTION_TYPE_LIKE, **page_kwargs)))

      if fetch_shares:
        add_activities(self._hub.GetReactionsByFid(
          ReactionsByFidRequest(
            fid=fid, reaction_type=REACTION_TYPE_RECAST, **page_kwargs)))

    return self.make_activities_base_response(
      activities, activity_id=activity_id, start_index=start_index)
