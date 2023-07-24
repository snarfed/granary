"""Unit tests for nostr.py."""
from oauth_dropins.webutil.util import json_dumps, json_loads
from oauth_dropins.webutil import testutil

from ..nostr import from_as1, id_for, to_as1

NOW_TS = int(testutil.NOW.timestamp())
NOW_ISO = testutil.NOW.replace(tzinfo=None).isoformat()

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

  def test_to_from_as1_profile(self):
    person = {
      'objectType': 'person',
      'displayName': 'Alice',
      'description': 'It me',
      'image': 'http://alice/pic',
      'username': 'alice.com',
    }
    event = {
      'kind': 0,
      'content': json_dumps({
        'name': 'Alice',
        'about': 'It me',
        'picture': 'http://alice/pic',
        'nip05': '_@alice.com',
      }),
    }
    self.assertEqual(person, to_as1(event))
    self.assertEqual(event, from_as1(person))

  def test_to_from_as1_note(self):
    note = {
      'objectType': 'note',
      'content': 'Something to say',
      'published': NOW_ISO,
    }
    event = {
      'kind': 1,
      'content': 'Something to say',
      'created_at': NOW_TS,
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))
