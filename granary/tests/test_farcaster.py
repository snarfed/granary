"""Unit tests for farcaster.py."""
from blake3 import blake3
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from datetime import datetime, timezone
import logging
from unittest.mock import patch

from google.protobuf import text_format
import grpc
from webutil import testutil, util

from ..farcaster import (
  BLAKE3_HASH_LENGTH_BYTES,
  Farcaster,
  farcaster_uri_to_web_url,
  from_as1,
  sign,
  to_as1,
  uri,
  verify,
  web_url_to_farcaster_uri,
)
from ..generated.farcaster import message_pb2
from ..generated.farcaster.message_pb2 import (
  HASH_SCHEME_BLAKE3,
  MessageData,
  REACTION_TYPE_LIKE,
  SIGNATURE_SCHEME_ED25519,
  SIGNATURE_SCHEME_EIP712,
)
from ..generated.farcaster.request_response_pb2 import (
  FidRequest,
  MessagesResponse,
  ReactionsByFidRequest,
  UsernameProofRequest,
)
from ..generated.farcaster.username_proof_pb2 import UserNameProof

PRIVKEY = Ed25519PrivateKey.generate()
PUBKEY = PRIVKEY.public_key()

logger = logging.getLogger(__name__)


def message(data_text):
  """Generates a Message with data, data_bytes, hash, and signature."""
  msg = text_format.Parse(f"""
data {{
  fid: 123
  timestamp: {testutil.NOW_SECONDS}
  network: FARCASTER_NETWORK_MAINNET
}}
""", message_pb2.Message())
  text_format.Merge(data_text, msg.data)

  msg.data_bytes = msg.data.SerializeToString()
  msg.hash = blake3(msg.data_bytes).digest()[:BLAKE3_HASH_LENGTH_BYTES]
  msg.hash_scheme = HASH_SCHEME_BLAKE3

  return msg


def user_data_message(fid, user_data_type, value):
  escaped = (value.replace('\\', '\\\\').replace('"', '\\"')
             .replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t'))
  return message(f"""
fid: {fid}
timestamp: {testutil.NOW_SECONDS}
network: FARCASTER_NETWORK_MAINNET
type: MESSAGE_TYPE_USER_DATA_ADD
user_data_body {{
  type: {user_data_type}
  value: "{escaped}"
}}
""")


class FarcasterTest(testutil.TestCase):

  def test_cast(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hello Farcaster!"
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Hello Farcaster!',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_cast_with_hash(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hello Farcaster!"
}
""")
    self.assertEqual({
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Hello Farcaster!',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
    }, to_as1(msg))

  def test_cast_with_mentions(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hey @alice!"
  mentions: 456
  mentions_positions: 4
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Hey @alice!',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
      'tags': [{
        'objectType': 'mention',
        'url': 'farcaster://456',
        'startIndex': 4,
      }],
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_cast_with_image_embed(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Check this out"
  embeds {
    url: "https://example.com/image.jpg"
  }
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Check this out',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
      'image': ['https://example.com/image.jpg'],
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_cast_with_video_embed(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Watch this"
  embeds {
    url: "https://example.com/video.mp4"
  }
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Watch this',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
      'attachments': [{
        'objectType': 'video',
        'stream': {'url': 'https://example.com/video.mp4'},
      }],
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_cast_with_link_embed(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Read this"
  embeds {
    url: "https://example.com/article"
  }
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Read this',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
      'attachments': [{
        'objectType': 'link',
        'url': 'https://example.com/article',
      }],
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_cast_with_cast_embed(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Quoting this"
  embeds {
    cast_id {
      fid: 789
      hash: "\\253\\315\\0224V"
    }
  }
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Quoting this',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
      'attachments': [{
        'objectType': 'note',
        'id': 'farcaster://789/0xabcd123456',
        'author': 'farcaster://789',
      }],
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_cast_post_activity(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hello Farcaster!"
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'post',
      'object': {
        'objectType': 'note',
        'id': f'farcaster://123/0x{msg.hash.hex()}',
        'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
        'author': 'farcaster://123',
        'content': 'Hello Farcaster!',
        'content_is_html': False,
        'published': '2022-01-02T03:04:05+00:00',
      },
    }
    self.assertEqual(msg, from_as1(obj))

  def test_reply(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Replying"
  parent_cast_id {
    fid: 456
    hash: "\\253\\315x\\220\\022"
  }
}
""")
    obj = {
      'objectType': 'note',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{msg.hash.hex()}',
      'author': 'farcaster://123',
      'content': 'Replying',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
      'inReplyTo': {
        'id': 'farcaster://456/0xabcd789012',
        'author': 'farcaster://456',
      },
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_like_cast(self):
    msg = message("""
type: MESSAGE_TYPE_REACTION_ADD
reaction_body {
  type: REACTION_TYPE_LIKE
  target_cast_id {
    fid: 456
    hash: "\\357x\\220\\0224"
  }
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'like',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'actor': 'farcaster://123',
      'published': '2022-01-02T03:04:05+00:00',
      'object': {
        'id': 'farcaster://456/0xef78901234',
        'author': 'farcaster://456',
      },
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_unlike(self):
    msg = message("""
type: MESSAGE_TYPE_REACTION_REMOVE
reaction_body {
  type: REACTION_TYPE_LIKE
  target_cast_id {
    fid: 456
    hash: "\\357x\\220\\0224"
  }
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'undo',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'actor': 'farcaster://123',
      'published': '2022-01-02T03:04:05+00:00',
      'object': {
        'objectType': 'activity',
        'verb': 'like',
        'actor': 'farcaster://123',
        'object': {
          'id': 'farcaster://456/0xef78901234',
          'author': 'farcaster://456',
        },
      },
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_like_url_target(self):
    msg = message("""
type: MESSAGE_TYPE_REACTION_ADD
reaction_body {
  type: REACTION_TYPE_LIKE
  target_url: "https://example.com/post"
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'like',
      'id': 'farcaster://123/0x69291c4fa8c659e62b28724378a67ea02d83b6ee',
      'actor': 'farcaster://123',
      'object': 'https://example.com/post',
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(msg, from_as1(obj))
    self.assertEqual(obj, to_as1(msg))

  def test_recast(self):
    msg = message("""
type: MESSAGE_TYPE_REACTION_ADD
reaction_body {
  type: REACTION_TYPE_RECAST
  target_cast_id {
    fid: 456
    hash: "\\357x\\220\\0224"
  }
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'share',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'actor': 'farcaster://123',
      'published': '2022-01-02T03:04:05+00:00',
      'object': {
        'id': 'farcaster://456/0xef78901234',
        'author': 'farcaster://456',
      },
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_unrecast(self):
    msg = message("""
type: MESSAGE_TYPE_REACTION_REMOVE
reaction_body {
  type: REACTION_TYPE_RECAST
  target_cast_id {
    fid: 456
    hash: "\\357x\\220\\0224"
  }
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'undo',
      'id': f'farcaster://123/0x{msg.hash.hex()}',
      'actor': 'farcaster://123',
      'published': '2022-01-02T03:04:05+00:00',
      'object': {
        'objectType': 'activity',
        'verb': 'share',
        'actor': 'farcaster://123',
        'object': {
          'id': 'farcaster://456/0xef78901234',
          'author': 'farcaster://456',
        },
      },
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_article(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Long form content here"
}
""")
    obj = {
      'objectType': 'article',
      'author': 'farcaster://123',
      'content': 'Long form content here',
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(msg, from_as1(obj))

  def test_follow(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_ADD
link_body {
  type: "follow"
  target_fid: 456
  displayTimestamp: 1641092645
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'follow',
      'actor': 'farcaster://123',
      'object': 'farcaster://456',
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_unfollow(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_REMOVE
link_body {
  type: "follow"
  target_fid: 456
  displayTimestamp: 1641092645
}
""")
    obj = {
      'actor': 'farcaster://123',
      'objectType': 'activity',
      'verb': 'undo',
      'object': {
        'objectType': 'activity',
        'verb': 'follow',
        'actor': 'farcaster://123',
        'object': 'farcaster://456',
      },
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_block(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_ADD
link_body {
  type: "block"
  target_fid: 456
  displayTimestamp: 1641092645
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'block',
      'actor': 'farcaster://123',
      'object': 'farcaster://456',
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_unblock(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_REMOVE
link_body {
  type: "block"
  target_fid: 456
  displayTimestamp: 1641092645
}
""")
    obj = {
      'actor': 'farcaster://123',
      'objectType': 'activity',
      'verb': 'undo',
      'object': {
        'objectType': 'activity',
        'verb': 'block',
        'actor': 'farcaster://123',
        'object': 'farcaster://456',
      },
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_delete(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_REMOVE
cast_remove_body {
  target_hash: "\\xab\\xcd\\x12\\x34"
}
""")
    obj = {
      'objectType': 'activity',
      'verb': 'delete',
      'actor': 'farcaster://123',
      'object': 'farcaster://123/0xabcd1234',
      'published': '2022-01-02T03:04:05+00:00',
    }
    self.assertEqual(obj, to_as1(msg))
    self.assertEqual(msg, from_as1(obj))

  def test_to_as1_empty(self):
    self.assertEqual({}, to_as1(None))
    self.assertEqual({}, to_as1('not a message'))

  def test_to_as1_actor_minimal(self):
    resp = MessagesResponse(
      messages=[user_data_message(456, 'USER_DATA_TYPE_DISPLAY', 'Alice')])

    self.assertEqual({
      'objectType': 'person',
      'id': 'farcaster://456',
      'url': 'https://farcaster.xyz/~/profiles/456',
      'displayName': 'Alice',
    }, to_as1(resp))

  def test_to_as1_actor(self):
    resp = MessagesResponse(
      messages=[
        user_data_message(456, 'USER_DATA_TYPE_DISPLAY', 'Alice'),
        user_data_message(456, 'USER_DATA_TYPE_USERNAME', 'alice'),
        user_data_message(456, 'USER_DATA_TYPE_BIO', 'Hello world'),
        user_data_message(456, 'USER_DATA_TYPE_PFP', 'https://example.com/alice.jpg'),
        user_data_message(456, 'USER_DATA_TYPE_BANNER', 'https://example.com/ban.jpg'),
        user_data_message(456, 'USER_DATA_TYPE_URL', 'https://alice.com/'),
      ],
    )
    self.assertEqual({
      'objectType': 'person',
      'id': 'farcaster://456',
      'url': 'https://alice.com/',
      'urls': [
        'https://alice.com/',
        'https://farcaster.xyz/~/profiles/456',
      ],
      'username': 'alice',
      'displayName': 'Alice',
      'summary': 'Hello world',
      'image': [
        'https://example.com/alice.jpg',
        {'objectType': 'featured', 'url': 'https://example.com/ban.jpg'},
      ],
    }, to_as1(resp))

  def test_from_as1_actor(self):
    self.assertEqual([
      user_data_message(456, 'USER_DATA_TYPE_DISPLAY', 'Alice'),
      user_data_message(456, 'USER_DATA_TYPE_USERNAME', 'alice'),
      user_data_message(456, 'USER_DATA_TYPE_BIO', 'Hello world'),
      user_data_message(456, 'USER_DATA_TYPE_PFP', 'https://example.com/alice.jpg'),
      user_data_message(456, 'USER_DATA_TYPE_BANNER', 'https://example.com/ban.jpg'),
      user_data_message(456, 'USER_DATA_TYPE_URL', 'https://alice.com/'),
    ], from_as1({
      'objectType': 'person',
      'id': 'farcaster://456',
      'displayName': 'Alice',
      'username': 'alice',
      'summary': 'Hello world',
      'image': [
        'https://example.com/alice.jpg',
        {'objectType': 'featured', 'url': 'https://example.com/ban.jpg'},
      ],
      'url': 'https://alice.com/',
    }))

  def test_from_as1_actor_minimal(self):
    self.assertEqual([
      user_data_message(123, 'USER_DATA_TYPE_DISPLAY', 'Bob'),
    ], from_as1({
      'objectType': 'person',
      'id': 'farcaster://123',
      'displayName': 'Bob',
    }))

  def test_from_as1_data_bytes(self):
    msg = from_as1({
      'objectType': 'note',
      'author': 'farcaster://123',
      'content': 'Hello Farcaster!',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
    })
    self.assertEqual(r"""data {
  type: MESSAGE_TYPE_CAST_ADD
  fid: 123
  timestamp: 1641092645
  network: FARCASTER_NETWORK_MAINNET
  cast_add_body {
    text: "Hello Farcaster!"
  }
}
hash: "W\214W\311.\223\216^Q\322\377\013\227\221\344\301 W7\303"
hash_scheme: HASH_SCHEME_BLAKE3
data_bytes: "\010\001\020{\030\245\254\304\216\006 \001*\022\"\020Hello Farcaster!"
""", str(msg))

  def test_from_as1_html_link_mention_hashtag(self):
    self.assertEqual(message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "foo bar @alice #news"
  mentions: 456
  mentions_positions: 8
}
"""), from_as1({
      'objectType': 'note',
      'author': 'farcaster://123',
      'published': '2022-01-02T03:04:05+00:00',
      'content': 'foo <a href="https://example.com">bar</a> @alice #news',
      'tags': [{
        'objectType': 'mention',
        'url': 'farcaster://456',
        'displayName': 'alice',
      }, {
        'objectType': 'hashtag',
        'displayName': 'news',
      }],
    }))

  def test_from_as1_plain_text_url_mention_hashtag(self):
    self.assertEqual(message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "foo @alice #news https://example.com"
  mentions: 456
  mentions_positions: 4
}
"""), from_as1({
      'objectType': 'note',
      'author': 'farcaster://123',
      'published': '2022-01-02T03:04:05+00:00',
      'content': 'foo @alice #news https://example.com',
      'tags': [{
        'objectType': 'mention',
        'url': 'farcaster://456',
        'displayName': 'alice',
      }, {
        'objectType': 'hashtag',
        'displayName': 'news',
      }],
    }))

  def test_to_as1_deserializes_data_bytes(self):
    data = text_format.Parse("""
fid: 123
timestamp: 1641092645
network: FARCASTER_NETWORK_MAINNET
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "From data_bytes!" }
""", MessageData())
    data_bytes = data.SerializeToString()
    hash_ = blake3(data_bytes).digest()[:20]
    msg = message_pb2.Message()
    msg.data_bytes = data_bytes
    msg.hash = hash_
    msg.hash_scheme = HASH_SCHEME_BLAKE3
    self.assertEqual({
      'objectType': 'note',
      'id': f'farcaster://123/0x{hash_.hex()}',
      'url': f'https://farcaster.xyz/~/conversations/0x{hash_.hex()}',
      'author': 'farcaster://123',
      'content': 'From data_bytes!',
      'content_is_html': False,
      'published': '2022-01-02T03:04:05+00:00',
    }, to_as1(msg))

  def test_to_as1_data_bytes_overwrites_data(self):
    # data_bytes content should win over msg.data
    data = text_format.Parse("""
fid: 123
timestamp: 1641092645
network: FARCASTER_NETWORK_MAINNET
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "From data_bytes!" }
""", MessageData())
    data_bytes = data.SerializeToString()
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "From msg.data!" }
""")
    msg.data_bytes = data_bytes
    msg.hash = blake3(data_bytes).digest()[:20]
    msg.hash_scheme = HASH_SCHEME_BLAKE3
    self.assertEqual('From data_bytes!', to_as1(msg)['content'])

  def test_sign(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hello Farcaster!"
}
""")
    sign(msg, PRIVKEY)

    self.assertEqual(SIGNATURE_SCHEME_ED25519, msg.signature_scheme)
    self.assertEqual(msg.signer, PUBKEY.public_bytes(Encoding.Raw, PublicFormat.Raw))

    # these shouldn't raise
    Ed25519PublicKey.from_public_bytes(msg.signer).verify(msg.signature, msg.hash)
    verify(msg)

  def test_verify_hash_valid_data_only(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    sign(msg, PRIVKEY)
    msg.ClearField('data_bytes')
    verify(msg)  # shouldn't raise

  def test_verify_hash_missing(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    sign(msg, PRIVKEY)
    msg.ClearField('hash')

    with self.assertRaisesRegex(ValueError, 'Missing hash'):
      verify(msg)

  def test_verify_hash_mismatch(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    sign(msg, PRIVKEY)
    msg.hash = b'\x00' * 20

    with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
      verify(msg)

  def test_verify_hash_mismatch_data_only(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    sign(msg, PRIVKEY)
    msg.hash = b'\x00' * 20
    msg.ClearField('data_bytes')

    with self.assertRaisesRegex(ValueError, 'Hash mismatch'):
      verify(msg)

  def test_verify_missing_signature(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")

    with self.assertRaisesRegex(ValueError, 'Missing hash or signature or signer'):
      verify(msg)

  def test_verify_unknown_signature_scheme(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    msg.signature_scheme = SIGNATURE_SCHEME_EIP712
    msg.signer = PUBKEY.public_bytes(Encoding.Raw, PublicFormat.Raw)
    msg.signature = PRIVKEY.sign(msg.hash)

    with self.assertRaisesRegex(ValueError, 'Unknown signature scheme'):
      verify(msg)

  def test_verify_bad_signature(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    msg.signature_scheme = SIGNATURE_SCHEME_ED25519
    msg.signer = PUBKEY.public_bytes(Encoding.Raw, PublicFormat.Raw)
    msg.signature = b'\x00' * 64

    with self.assertRaisesRegex(ValueError, 'Signature verification failed'):
      verify(msg)

  def test_uri(self):
    HASH = bytes.fromhex('abcd')
    for fid_or_username, hash, expected in [
        (123, None, 'farcaster://123'),
        (123, HASH, 'farcaster://123/0xabcd'),
        ('snarfed', None, 'farcaster://@snarfed'),
        ('snarfed', HASH, 'farcaster://@snarfed/0xabcd'),
    ]:
      with self.subTest(fid_or_username=fid_or_username):
        self.assertEqual(expected, uri(fid_or_username, hash=hash))

  def test_farcaster_uri_to_web_url(self):
    for uri, expected in [
        (None, None),
        ('', None),
        ('farcaster://123', 'https://farcaster.xyz/~/profiles/123'),
        ('farcaster://123/0xabcd', 'https://farcaster.xyz/~/conversations/0xabcd'),
        ('farcaster://@snarfed', 'https://farcaster.xyz/snarfed'),
        ('farcaster://@snarfed/0xabcd', 'https://farcaster.xyz/snarfed/0xabcd'),
    ]:
      with self.subTest(uri=uri):
        self.assertEqual(expected, farcaster_uri_to_web_url(uri))

    with self.assertRaises(ValueError):
      farcaster_uri_to_web_url('https://farcaster.xyz/~/profiles/123')

  def test_web_url_to_farcaster_uri(self):
    for url, kwargs, expected in [
        (None, {}, None),
        ('', {}, None),
        # tilde URLs
        ('https://farcaster.xyz/~/profiles/123', {}, 'farcaster://123'),
        ('https://farcaster.xyz/~/conversations/0xabcd', {}, None),
        # pretty URLs
        ('https://farcaster.xyz/snarfed', {}, 'farcaster://@snarfed'),
        ('https://farcaster.xyz/snarfed/0xd687db55', {},
         'farcaster://@snarfed/0xd687db55'),
        # query and fragment stripped
        ('https://farcaster.xyz/~/profiles/123?foo=bar', {}, 'farcaster://123'),
        ('https://farcaster.xyz/snarfed#foo', {}, 'farcaster://@snarfed'),
    ]:
      with self.subTest(url=url):
        self.assertEqual(expected, web_url_to_farcaster_uri(url, **kwargs))

    with self.assertRaises(ValueError):
      web_url_to_farcaster_uri('https://example.com/foo')


@patch('granary.farcaster.rpc_pb2_grpc.HubServiceStub')
class FarcasterClientTest(testutil.TestCase):
  """Tests for the Farcaster client class.

  We mock HubServiceStub directly instead of using grpcio-testing
  (https://grpc.github.io/grpc/python/grpc_testing.html). grpcio-testing
  requires two threads per RPC call — one to block on the stub call and one to
  dequeue it and send a response — which adds complexity without testing
  anything extra, since we're faking the server response either way.
  """

  def test_user_url(self, _):
    self.assertEqual('https://farcaster.xyz/~/profiles/123', Farcaster.user_url(123))

  def test_get_actor(self, mock_stub):
    mock_stub.return_value.GetUserDataByFid.return_value = \
      MessagesResponse(messages=[
        user_data_message(456, 'USER_DATA_TYPE_DISPLAY', 'Alice'),
        user_data_message(456, 'USER_DATA_TYPE_USERNAME', 'alice'),
        user_data_message(456, 'USER_DATA_TYPE_BIO', 'Hello world'),
        user_data_message(456, 'USER_DATA_TYPE_PFP', 'https://example.com/alice.jpg'),
        user_data_message(456, 'USER_DATA_TYPE_URL', 'https://alice.com/'),
      ])

    fc = Farcaster()
    self.assertEqual({
      'objectType': 'person',
      'id': 'farcaster://456',
      'url': 'https://alice.com/',
      'urls': [
        'https://alice.com/',
        'https://farcaster.xyz/~/profiles/456',
      ],
      'username': 'alice',
      'displayName': 'Alice',
      'summary': 'Hello world',
      'image': ['https://example.com/alice.jpg'],
    }, fc.get_actor(456))

    mock_stub.return_value.GetUserDataByFid.assert_called_once_with(
      FidRequest(fid=456))

  def test_get_fid(self, mock_stub):
    mock_stub.return_value.GetUsernameProof.return_value = \
      UserNameProof(fid=456, name=b'alice')

    fc = Farcaster()
    self.assertEqual(456, fc.get_fid('alice'))

    mock_stub.return_value.GetUsernameProof.assert_called_once_with(
      UsernameProofRequest(name=b'alice'))

  def test_get_fid_not_found(self, mock_stub):
    mock_stub.return_value.GetUsernameProof.return_value = UserNameProof()

    fc = Farcaster()
    self.assertIsNone(fc.get_fid('nope'))

  def test_get_fid_rpc_error(self, mock_stub):
    mock_stub.return_value.GetUsernameProof.side_effect = grpc.RpcError('boom')

    fc = Farcaster()
    self.assertIsNone(fc.get_fid('alice'))

  def test_get_activities_response_bad_user_id(self, mock_stub):
    fc = Farcaster()
    with self.assertRaisesRegex(ValueError, 'user_id must be a Farcaster FID'):
      fc.get_activities_response(user_id='not-an-int')

  def test_get_activities_response(self, mock_stub):
    cast = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hello!" }
""")
    mock_stub.return_value.GetCastsByFid.return_value = \
      MessagesResponse(messages=[cast])

    fc = Farcaster()
    resp = fc.get_activities_response(user_id='123')

    self.assertEqual({
      'startIndex': 0,
      'itemsPerPage': 1,
      'totalResults': 1,
      'filtered': False,
      'sorted': False,
      'updatedSince': False,
      'items': [{
        'objectType': 'activity',
        'verb': 'post',
        'actor': 'farcaster://123',
        'object': {
          'objectType': 'note',
          'id': f'farcaster://123/0x{cast.hash.hex()}',
          'url': f'https://farcaster.xyz/~/conversations/0x{cast.hash.hex()}',
          'author': 'farcaster://123',
          'content': 'Hello!',
          'content_is_html': False,
          'published': '2022-01-02T03:04:05+00:00',
        },
      }],
    }, resp)
    mock_stub.return_value.GetCastsByFid.assert_called_once_with(
      FidRequest(fid=123, reverse=True))

  def test_get_activities_response_count(self, mock_stub):
    mock_stub.return_value.GetCastsByFid.return_value = \
      MessagesResponse()

    fc = Farcaster()
    fc.get_activities_response(user_id='123', count=10)

    mock_stub.return_value.GetCastsByFid.assert_called_once_with(
      FidRequest(fid=123, page_size=10, reverse=True))

  def test_get_activities_response_fetch_likes(self, mock_stub):
    mock_stub.return_value.GetCastsByFid.return_value = \
      MessagesResponse()
    like = message("""
type: MESSAGE_TYPE_REACTION_ADD
reaction_body {
  type: REACTION_TYPE_LIKE
  target_cast_id { fid: 456  hash: "\\xab\\xcd" }
}
""")
    mock_stub.return_value.GetReactionsByFid.return_value = \
      MessagesResponse(messages=[like])

    fc = Farcaster('snap.chain')
    resp = fc.get_activities_response(user_id='123', fetch_likes=True)

    self.assertEqual([{
      'objectType': 'activity',
      'verb': 'like',
      'id': f'farcaster://123/0x{like.hash.hex()}',
      'actor': 'farcaster://123',
      'object': {
        'id': 'farcaster://456/0xabcd',
        'author': 'farcaster://456',
      },
      'published': '2022-01-02T03:04:05+00:00',
    }], resp['items'])
    mock_stub.return_value.GetReactionsByFid.assert_called_once_with(
      ReactionsByFidRequest(fid=123, reaction_type=REACTION_TYPE_LIKE, reverse=True))

  def test_get_activities_response_fetch_mentions(self, mock_stub):
    mention = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body { text: "Hey @alice!"  mentions: 123  mentions_positions: 4 }
""")
    mock_stub.return_value.GetCastsByFid.return_value = \
      MessagesResponse()
    mock_stub.return_value.GetCastsByMention.return_value = \
      MessagesResponse(messages=[mention])

    fc = Farcaster()
    resp = fc.get_activities_response(user_id='123', fetch_mentions=True)

    self.assertEqual(1, len(resp['items']))
    self.assertEqual('Hey @alice!', resp['items'][0]['object']['content'])
    mock_stub.return_value.GetCastsByMention.assert_called_once_with(
      FidRequest(fid=123, reverse=True))
