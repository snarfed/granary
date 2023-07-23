"""Unit tests for nostr.py."""
from oauth_dropins.webutil import testutil

from ..nostr import from_as1, to_as1


{
  'id': '...',
  'pubkey': '...',
  'created_at': int(testutil.NOW.timestamp()),
  'kind': 0,
  'content': '{"name": "Alice", "about": "It me", "picture": "http://alice/pic"}',
  'sig': '...',
}

class NostrTest(testutil.TestCase):

  def test_to_as1_profile(self):
    self.assertEqual({
      'objectType': 'person',
      'displayName': 'Alice',
      'description': 'It me',
      'image': 'http://alice/pic',
    }, to_as1({
      'kind': 0,
      'content': '{"name": "Alice", "about": "It me", "picture": "http://alice/pic"}',
    }))

  def test_to_as1_note(self):
    self.assertEqual({
      'objectType': 'note',
      'content': 'Something to say',
      'published': testutil.NOW.replace(tzinfo=None).isoformat(),
    }, to_as1({
      'kind': 1,
      'content': 'Something to say',
      'created_at': int(testutil.NOW.timestamp()),
    }))

  def test_from_as1_profile(self):
    self.assertEqual({
      'kind': 0,
      'content': '{"name":"Alice","about":"It me","picture":"http://alice/pic"}',
    }, from_as1({
      'objectType': 'person',
      'displayName': 'Alice',
      'description': 'It me',
      'image': 'http://alice/pic',
    }))

  def test_from_as1_note(self):
    self.assertEqual({
      'kind': 1,
      'content': 'Something to say',
      'created_at': int(testutil.NOW.timestamp()),
    }, from_as1({
      'objectType': 'note',
      'content': 'Something to say',
      'published': testutil.NOW.isoformat(),
    }))
