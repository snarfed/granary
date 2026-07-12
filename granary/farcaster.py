"""Farcaster.

https://farcaster.xyz/
https://github.com/farcasterxyz/protocol/blob/main/docs/SPECIFICATION.md
https://snapchain.farcaster.xyz/

TODO:

* rel-alternate links via "Social Attestations." so complicated.
  https://github.com/farcasterxyz/protocol/discussions/199
* mapping FIDs <=> DNS domains. unclear whether/how much this is adopted.
  https://github.com/farcasterxyz/protocol/discussions/106
* user location, from https://github.com/farcasterxyz/protocol/discussions/196
  (it's a geo:... URL string, https://tools.ietf.org/html/rfc5870, in
  USER_DATA_TYPE_LOCATION)
"""
import copy
from datetime import datetime, timedelta, timezone
from itertools import zip_longest
import logging
import mimetypes
from os.path import splitext
import re
import threading
from urllib.parse import urlparse

from blake3 import blake3
from cachetools import cached, TTLCache
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
  Ed25519PrivateKey,
  Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import grpc
from webutil import util

from . import as1, source
from .generated.farcaster import rpc_pb2_grpc
from .generated.farcaster.request_response_pb2 import (
  FidRequest,
  MessagesResponse,
  ReactionsByFidRequest,
  UsernameProofRequest,
)
from .generated.farcaster.message_pb2 import (
  CastId,
  FARCASTER_NETWORK_MAINNET,
  HASH_SCHEME_BLAKE3,
  Message,
  MessageData,
  MESSAGE_TYPE_CAST_ADD,
  MESSAGE_TYPE_CAST_REMOVE,
  MESSAGE_TYPE_REACTION_ADD,
  MESSAGE_TYPE_REACTION_REMOVE,
  MESSAGE_TYPE_USER_DATA_ADD,
  REACTION_TYPE_LIKE,
  MESSAGE_TYPE_LINK_ADD,
  MESSAGE_TYPE_LINK_REMOVE,
  REACTION_TYPE_RECAST,
  SIGNATURE_SCHEME_ED25519,
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

# Farcaster message timestamps are seconds since this custom epoch, not the
# Unix epoch: https://docs.farcaster.xyz/learn/what-is-farcaster/messages#timestamps
FARCASTER_EPOCH = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())

# mimetypes doesn't know these video streaming manifest extensions
VIDEO_EXTENSIONS_EXTRA = {'.m3u8', '.mpd'}

# CDN hostnames that Farcaster clients use for image embeds without file
# extensions, eg Cloudflare Images
IMAGE_CDN_HOSTNAMES = {
  'imagedelivery.net',
}

# farcaster:// URIs: https://github.com/farcasterxyz/protocol/discussions/123
# we support:
# * farcaster://[fid]
# * farcaster://@[username]
# * farcaster://[fid]/0x[hash]
# * farcaster://@[username]/0x[hash]
FARCASTER_URI_RE = re.compile(
  r'farcaster://((?P<fid>[0-9]+)|@(?P<username>[a-z0-9][a-z0-9.-]*))(/0x(?P<hash>[0-9a-f]+))?')

# reference web client URLs
# https://docs.farcaster.xyz/reference/farcaster/intent-urls#resource-urls
WEB_RESOURCE_URL_RE = re.compile(
  r'https://farcaster\.xyz/~/(?P<type>profiles|conversations)/(?P<id>.+)')
WEB_URL_RE = re.compile(
  r'https://farcaster\.xyz/(?P<username>[^/~][^/]*)(/(?P<hash>0x[0-9a-f]+))?')

# https://github.com/farcasterxyz/protocol/blob/main/docs/SPECIFICATION.md#hashing
BLAKE3_HASH_LENGTH_BYTES = 20

# https://github.com/farcasterxyz/protocol/blob/main/docs/SPECIFICATION.md#name-server
HANDLE_RE = re.compile(r'[a-z0-9][a-z0-9-]{0,15}')

CACHE_SIZE = 5000
CACHE_TTL = timedelta(hours=6)

logger = logging.getLogger(__name__)


def to_timestamp(dt):
  """Converts a datetime to a Farcaster timestamp.

  (Farcaster timestamps use a custom epoch: 2021-01-01, not 1970-01-01.
  https://docs.farcaster.xyz/learn/what-is-farcaster/messages#timestamps )

  Args:
    dt (datetime, timezone-aware)

  Returns:
    int
  """
  return int(dt.timestamp()) - FARCASTER_EPOCH


def from_timestamp(timestamp):
  """Converts a Farcaster timestamp to a datetime.

  (Farcaster timestamps use a custom epoch: 2021-01-01, not 1970-01-01.
  https://docs.farcaster.xyz/learn/what-is-farcaster/messages#timestamps )

  Args:
    timestamp (int)

  Returns:
    datetime: UTC
  """
  return datetime.fromtimestamp(timestamp + FARCASTER_EPOCH, tz=timezone.utc)


def uri(fid_or_username, hash=None):
  """Generates and returns a ``farcaster://`` URI.

  https://github.com/farcasterxyz/protocol/discussions/123

  Args:
    fid_or_username (int or str): numeric FID or username string (without
      leading ``@``)
    hash (bytes)

  Returns:
    str
  """
  if util.is_int(fid_or_username):
    authority = fid_or_username
  else:
    assert isinstance(fid_or_username, str)
    authority = f'@{fid_or_username}'

  result = f'farcaster://{authority}'
  if hash:
    assert isinstance(hash, bytes)
    result += f'/0x{hash.hex()}'

  return result


def farcaster_uri_to_web_url(uri):
  """Converts a ``farcaster://`` URI to a ``https://farcaster.xyz`` URL.

  https://github.com/farcasterxyz/protocol/discussions/123
  https://docs.farcaster.xyz/reference/farcaster/intent-urls#resource-urls

  Args:
    uri (str): ``farcaster://`` URI

  Returns:
    str: ``https://farcaster.xyz`` URL, or None

  Raises:
    ValueError: if uri is not a string or doesn't start with ``farcaster://``
  """
  if not uri:
    return None

  if not uri.startswith('farcaster://'):
    raise ValueError(f'Expected farcaster:// URI, got {uri}')

  if not (match := FARCASTER_URI_RE.fullmatch(uri)):
    return None

  hash = match['hash']
  if username := match['username']:
    if hash:
      return f'https://farcaster.xyz/{username}/0x{hash}'
    return f'https://farcaster.xyz/{username}'

  fid = match['fid']
  if hash:
    return f'https://farcaster.xyz/~/conversations/0x{hash}'
  return Farcaster.user_url(fid)


def web_url_to_farcaster_uri(url):
  """Converts a ``https://farcaster.xyz`` URL to a ``farcaster://`` URI.

  Supports tilde URLs:

  * ``https://farcaster.xyz/~/profiles/[fid]``
  * ``https://farcaster.xyz/~/conversations/0x[hash]``

  And pretty URLs:

  * ``https://farcaster.xyz/[username]``
  * ``https://farcaster.xyz/[username]/0x[hash]``

  Query strings and fragments are stripped before conversion. Tilde
  conversation URLs return None since they contain no username or FID.

  https://docs.farcaster.xyz/reference/farcaster/intent-urls#resource-urls
  https://github.com/farcasterxyz/protocol/discussions/123

  Args:
    url (str): ``farcaster.xyz`` URL

  Returns:
    str: ``farcaster://`` URI, or None for tilde conversation URLs

  Raises:
    ValueError: if ``url`` can't be parsed as a ``farcaster.xyz`` URL
  """
  if not url:
    return None

  parsed = urlparse(url)
  url = parsed._replace(query='', fragment='').geturl()

  if match := WEB_RESOURCE_URL_RE.fullmatch(url):
    if match['type'] == 'profiles':
      return f'farcaster://{match["id"]}'
    return None  # conversations: no username or FID available

  if match := WEB_URL_RE.fullmatch(url):
    username = match['username']
    hash = match['hash']
    if hash:
      return f'farcaster://@{username}/{hash}'
    return f'farcaster://@{username}'

  raise ValueError(f"{url} doesn't look like a farcaster.xyz URL")


def deserialize(msg):
  """Deserializes and returns the ``MessageData`` for a given ``Message``.

  Prefers ``data_bytes`` over ``data`` per the Farcaster spec:
  https://github.com/farcasterxyz/protocol/blob/main/docs/SPECIFICATION.md#hashing
  https://github.com/farcasterxyz/protocol/discussions/87

  Args:
    msg (message_pb2.Message)

  Returns:
    MessageData

  Raises:
    ValueError: if neither ``data`` nor ``data_bytes`` is set
  """
  if msg.HasField('data_bytes'):
    data = MessageData()
    data.ParseFromString(msg.data_bytes)
    return data
  elif msg.HasField('data'):
    return msg.data
  else:
    raise ValueError(f'No data or data_bytes: {msg}')


def verify(msg):
  """Verifies a ``MessageData``'s hash and signature.

  Args:
    msg (message_pb2.Message)

  Raises:
    ValueError: if ``hash`` or ``signature`` are invalid or missing
  """
  if not msg.hash or not msg.signature or not msg.signer:
    raise ValueError(f'Missing hash or signature or signer: {msg}')
  if msg.signature_scheme != SIGNATURE_SCHEME_ED25519:
    raise ValueError(f'Unknown signature scheme: {msg.signature_scheme}')

  if msg.HasField('data_bytes'):
    data_bytes = msg.data_bytes
  elif msg.HasField('data'):
    data_bytes = msg.data.SerializeToString()
  else:
    raise ValueError(f'No data or data_bytes: {msg}')

  hash = blake3(data_bytes).digest()[:BLAKE3_HASH_LENGTH_BYTES]
  if hash != msg.hash:
    raise ValueError(f'Hash mismatch: expected {hash.hex()}, got {msg.hash.hex()}')

  try:
    Ed25519PublicKey.from_public_bytes(msg.signer).verify(msg.signature, msg.hash)
  except InvalidSignature as e:
    raise ValueError(f'Signature verification failed: {e}') from e


def hash_for(msg):
  """Serializes ``MessageData`` into ``data_bytes`` and populates ``hash``.

  Args:
    msg (message_pb2.Message)

  Returns:
    bytes: the blake3 hash, also stored in ``msg.hash``
  """
  msg.data_bytes = msg.data.SerializeToString()
  msg.hash = blake3(msg.data_bytes).digest()[:BLAKE3_HASH_LENGTH_BYTES]
  msg.hash_scheme = HASH_SCHEME_BLAKE3
  return msg.hash


def hash_and_sign(msg, privkey):
  """Hashes and signs a ``Message``.

  Populates the ``hash``, ``signer``, and ``signature`` fields.

  https://github.com/farcasterxyz/protocol/blob/main/docs/SPECIFICATION.md#2-message-specifications

  Args:
    msg (message_pb2.Message)
    privkey (Ed25519PrivateKey): private key to sign with

  Returns:
    message_pb2.Message: msg, populated with hash and signature fields
  """
  hash_for(msg)
  msg.signature = privkey.sign(msg.hash)
  msg.signer = privkey.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
  msg.signature_scheme = SIGNATURE_SCHEME_ED25519
  return msg


def to_as1(msg):
  """Converts a Farcaster protobuf to an ActivityStreams 1 object or actor.

  Ids are farcaster:// URIs: https://github.com/farcasterxyz/protocol/discussions/123

  Args:
    msg (message_pb2.Message or MessagesResponse):
      Farcaster Message protobuf or MessagesResponse (user data messages)

  Returns:
    dict: AS1 activity, object, or actor
  """
  # actor, from GetUserDataByFid response
  if isinstance(msg, MessagesResponse):
    actor = {}
    fid = None

    for m in msg.messages:
      if (data := deserialize(m)) and data.type == MESSAGE_TYPE_USER_DATA_ADD:
        if not fid:
          fid = data.fid
        assert data.fid == fid

        body = data.user_data_body
        if field := USER_DATA_TYPE_TO_AS1.get(body.type):
          if field == 'image':
            img = ({'objectType': 'featured', 'url': body.value}
                   if body.type == USER_DATA_TYPE_BANNER
                   else body.value)
            actor.setdefault('image', []).append(img)
          elif field == 'url':
            actor['url'] = body.value
            if fid:
              actor['urls'] = [body.value, Farcaster.user_url(fid)]
          else:
            actor[field] = body.value

    return util.trim_nulls({
      'url': Farcaster.user_url(fid) if fid else None,  # default
      **actor,
      'objectType': 'person',
      'id': uri(fid) if fid else None,
    })

  # all other object types
  if not msg or not isinstance(msg, Message):
    return {}

  if not (data := deserialize(msg)):
    return {}

  obj = {}  # AS1 return value
  actor_fid = data.fid
  msg_type = data.type
  published = None
  if data.timestamp:
    published = from_timestamp(data.timestamp).isoformat()

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
      obj['author'] = uri(actor_fid)

    if msg.hash:
      obj.update({
        'id': uri(actor_fid, msg.hash),
        'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      })

    if cast.mentions:
      for mention_fid, pos in zip_longest(cast.mentions, cast.mentions_positions):
        obj['tags'].append({
          'objectType': 'mention',
          'url': uri(mention_fid),
          'startIndex': pos,
        })

    for embed in cast.embeds:
      if embed.HasField('url'):
        # technically we should HEAD the URL and look at its Content-Type
        mimetype, _ = mimetypes.guess_type(embed.url)
        parsed = urlparse(embed.url)
        is_image = ((mimetype and mimetype.startswith('image/'))
                    or parsed.hostname in IMAGE_CDN_HOSTNAMES)
        is_video = ((mimetype and mimetype.startswith('video/'))
                    or splitext(parsed.path)[1] in VIDEO_EXTENSIONS_EXTRA)
        if is_image:
          obj['image'].append(embed.url)
        elif is_video:
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
          'id': uri(embed.cast_id.fid, embed.cast_id.hash),
          'author': uri(embed.cast_id.fid),
        })

    if cast.HasField('parent_cast_id'):
      obj['inReplyTo'] = uri(cast.parent_cast_id.fid, cast.parent_cast_id.hash)
    elif cast.HasField('parent_url'):
      obj['inReplyTo'] = cast.parent_url

  # delete
  elif msg_type == MESSAGE_TYPE_CAST_REMOVE:
    obj = {
      'objectType': 'activity',
      'verb': 'delete',
      'actor': uri(actor_fid),
      'object': uri(actor_fid, data.cast_remove_body.target_hash),
      'published': published,
    }

  # like, repost
  elif msg_type in (MESSAGE_TYPE_REACTION_ADD, MESSAGE_TYPE_REACTION_REMOVE):
    reaction = data.reaction_body
    verb = 'like' if reaction.type == REACTION_TYPE_LIKE else 'share'

    if reaction.HasField('target_cast_id'):
      target_obj = {
        'id': uri(reaction.target_cast_id.fid, reaction.target_cast_id.hash),
        'author': uri(reaction.target_cast_id.fid),
      }
    elif reaction.HasField('target_url'):
      target_obj = reaction.target_url

    obj = {
      'objectType': 'activity',
      'verb': verb,
      'actor': uri(actor_fid),
      'object': target_obj,
    }
    if msg_type == MESSAGE_TYPE_REACTION_REMOVE:
      obj = {
        'objectType': 'activity',
        'verb': 'undo',
        'actor': uri(actor_fid),
        'object': obj,
      }

    obj['published'] = published
    if msg.hash:
      obj['id'] = uri(actor_fid, msg.hash)

  # follow, block, unfollow, unblock
  elif msg_type in (MESSAGE_TYPE_LINK_ADD, MESSAGE_TYPE_LINK_REMOVE):
    obj = {
      'objectType': 'activity',
      'verb': data.link_body.type,
      'actor': uri(actor_fid),
      'object': uri(data.link_body.target_fid),
    }

    if msg_type == MESSAGE_TYPE_LINK_REMOVE:
      obj = {
      'objectType': 'activity',
        'verb': 'undo',
        'actor': uri(actor_fid),
        'object': obj,
      }

    obj['published'] = published
    if timestamp := data.link_body.displayTimestamp:
      obj['published'] = from_timestamp(timestamp).isoformat()

  return util.trim_nulls(obj)


def from_as1(obj, username=None):
  """Converts an ActivityStreams 1 activity or object to a Farcaster Message.

  Args:
    obj (dict): AS1 activity or object
    username (str): if provided, overrides the username from ``obj``

  Returns:
    message_pb2.Message or list of message_pb2.Message: Farcaster Message
      protobuf, or list of Messages if ``obj`` is an actor
  """
  type = as1.object_type(obj)
  if type in ('post', 'update'):
    type = as1.object_type(as1.get_object(obj))
    obj = as1.get_object(obj)

  # actor/profile: return one USER_DATA Message per field
  if type in as1.ACTOR_TYPES:
    return _from_as1_actor(obj, username=username)

  msg = Message()
  data = msg.data

  inner_obj = as1.get_object(obj)
  inner_id = inner_obj.get('id')
  inner_id_match = FARCASTER_URI_RE.fullmatch(inner_id or '')
  inner_type = as1.object_type(inner_obj)
  author = as1.get_owner(obj) or ''

  if ((match := FARCASTER_URI_RE.fullmatch(author))
      and match['fid'] and not match['hash']):
    data.fid = int(match['fid'])

  data.network = FARCASTER_NETWORK_MAINNET

  published = (util.parse_iso8601(obj['published']) if obj.get('published')
               else util.now(tz=timezone.utc))
  data.timestamp = to_timestamp(published)

  as1.convert_html_content_to_text(obj)
  as1.expand_tags(obj)

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
        match = FARCASTER_URI_RE.fullmatch(tag.get('url', ''))
        if match and match['fid'] and not match['hash']:
          cast.mentions.append(int(match['fid']))
          if 'startIndex' in tag:
            cast.mentions_positions.append(tag['startIndex'])

    # images
    for img in as1.get_objects(obj, 'image'):
      if url := as1.get_url(img) or img.get('id'):
        cast.embeds.add().url = url

    for att in as1.get_objects(obj, 'attachments'):
      att_type = as1.object_type(att)
      if att_type == 'note':
        author = att.get('author', '')
        if ((match := FARCASTER_URI_RE.fullmatch(att.get('id', '')))
            and match['fid'] and match['hash']):
          embed = cast.embeds.add()
          embed.cast_id.fid = int(match['fid'])
          embed.cast_id.hash = bytes.fromhex(match['hash'])
      elif att_type in ('video', 'audio'):
        if url := as1.get_url(util.get_first(att, 'stream')):
          cast.embeds.add().url = url
      elif att_type == 'link':
        if url := as1.get_url(att):
          cast.embeds.add().url = url

    # reply
    if ((in_reply_to := as1.get_object(obj, 'inReplyTo'))
        and (id := in_reply_to.get('id'))):
      if ((match := FARCASTER_URI_RE.fullmatch(id))
          and match['fid'] and match['hash']):
        cast.parent_cast_id.fid = int(match['fid'])
        cast.parent_cast_id.hash = bytes.fromhex(match['hash'])
      elif util.is_web(id):
        cast.parent_url = id

  # likes/reposts
  elif type in ('like', 'share'):
    data.type = MESSAGE_TYPE_REACTION_ADD
    reaction = data.reaction_body
    reaction.type = REACTION_TYPE_LIKE if type == 'like' else REACTION_TYPE_RECAST

    if inner_id_match and inner_id_match['fid'] and inner_id_match['hash']:
      reaction.target_cast_id.fid = int(inner_id_match['fid'])
      reaction.target_cast_id.hash = bytes.fromhex(inner_id_match['hash'])
    elif util.is_web(inner_id):
      reaction.target_url = inner_id

  # follow, block
  elif type in ('follow', 'block'):
    data.type = MESSAGE_TYPE_LINK_ADD
    data.link_body.type = type
    if inner_id_match and inner_id_match['fid'] and not inner_id_match['hash']:
      data.link_body.target_fid = int(inner_id_match['fid'])
    data.link_body.displayTimestamp = data.timestamp

  # delete post
  elif type == 'delete':
    data.type = MESSAGE_TYPE_CAST_REMOVE
    if inner_id_match and inner_id_match['hash']:
      data.cast_remove_body.target_hash = bytes.fromhex(inner_id_match['hash'])

  # undo like/repost
  elif type == 'undo' and inner_type in ('like', 'share'):
    data.type = MESSAGE_TYPE_REACTION_REMOVE
    data.reaction_body.MergeFrom(from_as1(inner_obj).data.reaction_body)

  # unfollow, unblock
  elif type == 'undo' and inner_type in ('follow', 'block'):
    data.type = MESSAGE_TYPE_LINK_REMOVE
    data.link_body.type = inner_type
    target_id = as1.get_object(inner_obj).get('id', '')
    if ((match := FARCASTER_URI_RE.fullmatch(target_id))
        and match['fid'] and not match['hash']):
      data.link_body.target_fid = int(match['fid'])
    data.link_body.displayTimestamp = data.timestamp

  hash_for(msg)
  return msg


def _from_as1_actor(obj, username=None):
  """Converts an ActivityStreams 1 actor to Farcaster USER_DATA Messages.

  Args:
    obj (dict): AS1 actor
    username (str): if provided, overrides the username from ``obj``

  Returns:
    list of message_pb2.Message:
  """
  assert as1.object_type(obj) in as1.ACTOR_TYPES

  fid = None
  if ((match := FARCASTER_URI_RE.fullmatch(obj.get('id', '')))
      and match['fid'] and not match['hash']):
    fid = int(match['fid'])

  published = (util.parse_iso8601(obj['published']) if obj.get('published')
               else util.now(tz=timezone.utc))
  timestamp = to_timestamp(published)

  def add(user_data_type, value):
    msg = Message()
    msg.data.type = MESSAGE_TYPE_USER_DATA_ADD
    msg.data.network = FARCASTER_NETWORK_MAINNET
    msg.data.timestamp = timestamp
    if fid:
      msg.data.fid = fid
    msg.data.user_data_body.type = user_data_type
    msg.data.user_data_body.value = value
    hash_for(msg)
    msgs.append(msg)

  msgs = []
  if val := obj.get('displayName'):
    add(USER_DATA_TYPE_DISPLAY, val)
  if val := username or obj.get('username'):
    add(USER_DATA_TYPE_USERNAME, val)
  if val := obj.get('summary'):
    add(USER_DATA_TYPE_BIO, val)
  for img in as1.get_objects(obj, 'image'):
    if img.get('objectType') == 'featured':
      if url := img.get('url'):
        add(USER_DATA_TYPE_BANNER, url)
    elif url := as1.get_url(img) or img.get('id'):
      add(USER_DATA_TYPE_PFP, url)
  if val := obj.get('url'):
    add(USER_DATA_TYPE_URL, val)

  return msgs


class Farcaster(source.Source):
  """Farcaster source class. See file docstring and :class:`Source` for details.

  Attributes:
    hub (rpc_pb2_grpc.HubServiceStub): gRPC client
  """

  DOMAIN = 'farcaster.xyz'
  BASE_URL = 'https://farcaster.xyz/'
  NAME = 'Farcaster'

  def __init__(self, host=DEFAULT_SNAPCHAIN_HOST, port=DEFAULT_SNAPCHAIN_PORT,
               log_requests_responses=False):
    """Constructor.

    Args:
      host (str): snapchain node host, eg ``snapchain.farcaster.xyz``
      port (int): snapchain node port, default 3383
      log_requests_responses (boolean): whether to log request and response
        bodies at DEBUG level
    """
    assert host
    assert port

    addr = f'{host}:{port}'
    logger.info(f'Connecting to Farcaster Snapchain node {addr}')

    channel = grpc.secure_channel(addr, grpc.ssl_channel_credentials())

    if log_requests_responses:
      interceptor = util.GrpcLoggingInterceptor(logger=logger, level=logging.DEBUG)
      channel = grpc.intercept_channel(channel, interceptor)

    self.hub = rpc_pb2_grpc.HubServiceStub(channel)

  @classmethod
  def user_url(cls, fid):
    """Returns the Farcaster URL for a user with the given FID.

    https://docs.farcaster.xyz/reference/farcaster/intent-urls#resource-urls

    Args:
      fid (int): Farcaster user ID

    Returns:
      str: URL
    """
    return f'https://farcaster.xyz/~/profiles/{fid}'

  def get_actor(self, fid):
    """Fetches and returns a Farcaster user as an AS1 actor dict.

    Args:
      fid (int): Farcaster user ID

    Returns:
      dict: AS1 actor
    """
    resp = self.hub.GetUserDataByFid(FidRequest(fid=fid))
    return to_as1(resp)

  @cached(TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_TTL.total_seconds()),
          lock=threading.Lock())
  def get_fid(self, username):
    """Resolves a Farcaster username to its FID via the hub.

    Uses the ``GetUsernameProof`` RPC:
    https://snapchain.farcaster.xyz/reference/grpcapi/usernameproof

    Args:
      username (str): eg ``alice`` or ``alice.eth``

    Returns:
      int: FID, or None if the username isn't registered or the RPC fails
    """
    try:
      proof = self.hub.GetUsernameProof(
        UsernameProofRequest(name=username.encode('utf-8')))
      if proof.fid:
        return proof.fid

    except grpc.RpcError as e:
      logger.info(f'GetUsernameProof({username!r}) failed: {e}')

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
    page_kwargs = {'reverse': True}
    if count:
      page_kwargs['page_size'] = count
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
          messages=[self.hub.GetCast(CastId(fid=fid, hash=cast_hash))]))
      else:
        add_activities(self.hub.GetCastsByFid(FidRequest(fid=fid, **page_kwargs)))

      if fetch_mentions:
        add_activities(self.hub.GetCastsByMention(FidRequest(fid=fid, **page_kwargs)))

      if fetch_likes:
        add_activities(self.hub.GetReactionsByFid(ReactionsByFidRequest(
          fid=fid, reaction_type=REACTION_TYPE_LIKE, **page_kwargs)))

      if fetch_shares:
        add_activities(self.hub.GetReactionsByFid(
          ReactionsByFidRequest(
            fid=fid, reaction_type=REACTION_TYPE_RECAST, **page_kwargs)))

    return self.make_activities_base_response(
      activities, activity_id=activity_id, start_index=start_index)
