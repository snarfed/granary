"""Unit tests for farcaster.py."""
import copy
import logging
from unittest import skip

from google.protobuf import text_format
from oauth_dropins.webutil import testutil, util

from ..farcaster import from_as1, to_as1
from ..generated.farcaster import message_pb2

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
  type: "TODO"
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
  type: "TODO"
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

  def test_to_as1_empty(self):
    self.assertEqual({}, to_as1(None))
    self.assertEqual({}, to_as1(message_pb2.Message()))
