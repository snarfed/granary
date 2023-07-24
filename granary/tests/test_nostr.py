"""Unit tests for nostr.py."""
from oauth_dropins.webutil import testutil

from ..nostr import from_as1, id_for, to_as1

NOW_TS = int(testutil.NOW.timestamp())


class NostrTest(testutil.TestCase):

  def test_id_for(self):
    self.assertEqual(
      '9adfa2330b391539f46548ff2e088ea964a2f7374898c7335a86e914cbf2e769',
      id_for({
        'pubkey': 'fed987',
        'created_at': NOW_TS,
        'kind': 1,
        'content': 'My plain text',
    }))

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
      'created_at': NOW_TS,
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
      'created_at': NOW_TS,
    }, from_as1({
      'objectType': 'note',
      'content': 'Something to say',
      'published': testutil.NOW.isoformat(),
    }))
