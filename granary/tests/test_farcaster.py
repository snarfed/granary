"""Unit tests for farcaster.py."""
import copy
import logging
from unittest import skip
from unittest.mock import patch

from google.protobuf import text_format
from oauth_dropins.webutil import testutil, util

from ..farcaster import Farcaster, from_as1, to_as1
from ..generated.farcaster import message_pb2, request_response_pb2

logger = logging.getLogger(__name__)


def message(data_text):
    msg = text_format.Parse("""
data {
  fid: 123
  timestamp: 1640000000
  network: FARCASTER_NETWORK_MAINNET
}
""", message_pb2.Message())
    text_format.Merge(data_text, msg.data)
    return msg


class FarcasterTest(testutil.TestCase):

  def test_cast(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hello Farcaster!"
}
""")
    as1 = {
      'objectType': 'note',
      # 'id': 'farcaster:cast:abcd1234',
      'author': 'farcaster:fid:123',
      'content': 'Hello Farcaster!',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      # 'url': 'https://warpcast.com/~/conversations/abcd1234',
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_cast_with_mentions(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Hey @alice!"
  mentions: 456
  mentions_positions: 4
}
""")
    as1 = {
      'objectType': 'note',
      # 'id': 'farcaster:cast:dff45678',
      'author': 'farcaster:fid:123',
      'content': 'Hey @alice!',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      # 'url': 'https://warpcast.com/~/conversations/dff45678',
      'tags': [{
        'objectType': 'mention',
        'url': 'farcaster:fid:456',
        'startIndex': 4,
      }],
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'note',
      'author': 'farcaster:fid:123',
      'content': 'Check this out',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      'image': ['https://example.com/image.jpg'],
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'note',
      'author': 'farcaster:fid:123',
      'content': 'Watch this',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      'attachments': [{
        'objectType': 'video',
        'stream': {'url': 'https://example.com/video.mp4'},
      }],
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'note',
      'author': 'farcaster:fid:123',
      'content': 'Read this',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      'attachments': [{
        'objectType': 'link',
        'url': 'https://example.com/article',
      }],
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'note',
      'author': 'farcaster:fid:123',
      'content': 'Quoting this',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      'attachments': [{
        'objectType': 'note',
        'id': 'farcaster:cast:abcd123456',
        'author': 'farcaster:fid:789',
      }],
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'note',
      'author': 'farcaster:fid:123',
      'content': 'Replying',
      'content_is_html': False,
      'published': '2021-12-20T11:33:20+00:00',
      'inReplyTo': {
        'id': 'farcaster:cast:abcd789012',
        'author': 'farcaster:fid:456',
      },
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_like(self):
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
    as1 = {
      'objectType': 'activity',
      'verb': 'like',
      # 'id': 'farcaster:reaction:abcd1234ef',
      'actor': 'farcaster:fid:123',
      'published': '2021-12-20T11:33:20+00:00',
      'object': {
        'id': 'farcaster:cast:ef78901234',
        'author': 'farcaster:fid:456',
      },
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'activity',
      'verb': 'undo',
      'actor': 'farcaster:fid:123',
      'published': '2021-12-20T11:33:20+00:00',
      'object': {
        'objectType': 'activity',
        'verb': 'like',
        'actor': 'farcaster:fid:123',
        'object': {
          'id': 'farcaster:cast:ef78901234',
          'author': 'farcaster:fid:456',
        },
      },
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'activity',
      'verb': 'share',
      # 'id': 'farcaster:reaction:abcdef1234',
      'actor': 'farcaster:fid:123',
      'published': '2021-12-20T11:33:20+00:00',
      'object': {
        'id': 'farcaster:cast:ef78901234',
        'author': 'farcaster:fid:456',
      },
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

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
    as1 = {
      'objectType': 'activity',
      'verb': 'undo',
      'actor': 'farcaster:fid:123',
      'published': '2021-12-20T11:33:20+00:00',
      'object': {
        'objectType': 'activity',
        'verb': 'share',
        'actor': 'farcaster:fid:123',
        'object': {
          'id': 'farcaster:cast:ef78901234',
          'author': 'farcaster:fid:456',
        },
      },
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_article(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_ADD
cast_add_body {
  text: "Long form content here"
}
""")
    as1 = {
      'objectType': 'article',
      'author': 'farcaster:fid:123',
      'content': 'Long form content here',
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.assertEqual(msg, from_as1(as1))

  def test_follow(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_ADD
link_body {
  type: "follow"
  target_fid: 456
  displayTimestamp: 1640000000
}
""")
    as1 = {
      'objectType': 'activity',
      'verb': 'follow',
      'actor': 'farcaster:fid:123',
      'object': 'farcaster:fid:456',
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_unfollow(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_REMOVE
link_body {
  type: "follow"
  target_fid: 456
  displayTimestamp: 1640000000
}
""")
    as1 = {
      'actor': 'farcaster:fid:123',
      'objectType': 'activity',
      'verb': 'undo',
      'object': {
        'objectType': 'activity',
        'verb': 'follow',
        'actor': 'farcaster:fid:123',
        'object': 'farcaster:fid:456',
      },
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_block(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_ADD
link_body {
  type: "block"
  target_fid: 456
  displayTimestamp: 1640000000
}
""")
    as1 = {
      'objectType': 'activity',
      'verb': 'block',
      'actor': 'farcaster:fid:123',
      'object': 'farcaster:fid:456',
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_unblock(self):
    msg = message("""
type: MESSAGE_TYPE_LINK_REMOVE
link_body {
  type: "block"
  target_fid: 456
  displayTimestamp: 1640000000
}
""")
    as1 = {
      'actor': 'farcaster:fid:123',
      'objectType': 'activity',
      'verb': 'undo',
      'object': {
        'objectType': 'activity',
        'verb': 'block',
        'actor': 'farcaster:fid:123',
        'object': 'farcaster:fid:456',
      },
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_delete(self):
    msg = message("""
type: MESSAGE_TYPE_CAST_REMOVE
cast_remove_body {
  target_hash: "\\xab\\xcd\\x12\\x34"
}
""")
    as1 = {
      'objectType': 'activity',
      'verb': 'delete',
      'actor': 'farcaster:fid:123',
      'object': 'farcaster:cast:abcd1234',
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.assertEqual(as1, to_as1(msg))
    self.assertEqual(msg, from_as1(as1))

  def test_to_as1_empty(self):
    self.assertEqual({}, to_as1(None))
    self.assertEqual({}, to_as1(message_pb2.Message()))

  def test_to_as1_actor(self):
    resp = request_response_pb2.MessagesResponse(
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
      'id': 'farcaster:fid:456',
      'url': 'https://alice.com/',
      'username': 'alice',
      'displayName': 'Alice',
      'summary': 'Hello world',
      'image': [
        'https://example.com/alice.jpg',
        {'objectType': 'featured', 'url': 'https://example.com/ban.jpg'},
      ],
    }, to_as1(resp))



def user_data_message(fid, user_data_type, value):
  msg = text_format.Parse(f"""
data {{
  fid: {fid}
  timestamp: 1640000000
  network: FARCASTER_NETWORK_MAINNET
  type: MESSAGE_TYPE_USER_DATA_ADD
  user_data_body {{
    type: {user_data_type}
    value: "{value}"
  }}
}}
""", message_pb2.Message())
  return msg


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
    self.assertEqual('https://farcaster.xyz/~/user/123', Farcaster.user_url(123))

  def test_get_actor(self, mock_stub):
    mock_stub.return_value.GetUserDataByFid.return_value = \
      request_response_pb2.MessagesResponse(messages=[
        user_data_message(456, 'USER_DATA_TYPE_DISPLAY', 'Alice'),
        user_data_message(456, 'USER_DATA_TYPE_USERNAME', 'alice'),
        user_data_message(456, 'USER_DATA_TYPE_BIO', 'Hello world'),
        user_data_message(456, 'USER_DATA_TYPE_PFP', 'https://example.com/alice.jpg'),
        user_data_message(456, 'USER_DATA_TYPE_URL', 'https://alice.com/'),
      ])

    fc = Farcaster('snap.chain:3383')
    self.assertEqual({
      'objectType': 'person',
      'id': 'farcaster:fid:456',
      'url': 'https://alice.com/',
      'username': 'alice',
      'displayName': 'Alice',
      'summary': 'Hello world',
      'image': ['https://example.com/alice.jpg'],
    }, fc.get_actor(456))

    mock_stub.return_value.GetUserDataByFid.assert_called_once_with(
      request_response_pb2.FidRequest(fid=456))
