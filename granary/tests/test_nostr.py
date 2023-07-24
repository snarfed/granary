"""Unit tests for nostr.py."""
from datetime import timedelta

from oauth_dropins.webutil.util import json_dumps, json_loads
from oauth_dropins.webutil import testutil

from ..nostr import from_as1, id_for, to_as1

NOW_TS = int(testutil.NOW.timestamp())
NOW_ISO = testutil.NOW.replace(tzinfo=None).isoformat()
THEN_TS = NOW_TS - 1
THEN_ISO = (testutil.NOW - timedelta(seconds=1)).replace(tzinfo=None).isoformat()


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
      'id': 'nostr:npub987fed',
      'displayName': 'Alice',
      'description': 'It me',
      'image': 'http://alice/pic',
      'username': 'alice.com',
    }
    event = {
      'kind': 0,
      'pubkey': '987fed',
      'content': json_dumps({
        'name': 'Alice',
        'about': 'It me',
        'picture': 'http://alice/pic',
        'nip05': '_@alice.com',
      }, sort_keys=True),
    }
    self.assertEqual(person, to_as1(event))
    self.assertEqual(event, from_as1(person))

  def test_to_from_as1_note(self):
    note = {
      'objectType': 'note',
      'id': 'nostr:noteabc123',
      'author': {'id': 'nostr:npub987fed'},
      'content': 'Something to say',
      'published': NOW_ISO,
    }
    event = {
      'kind': 1,
      'id': 'abc123',
      'pubkey': '987fed',
      'content': 'Something to say',
      'created_at': NOW_TS,
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))

  def test_to_from_as1_reply(self):
    reply = {
      'objectType': 'note',
      'id': 'nostr:noteabc123',
      'author': {'id': 'nostr:npub987fed'},
      'published': NOW_ISO,
      'content': 'I hereby reply',
      'inReplyTo': 'nostr:notedef456',
    }
    event = {
      'kind': 1,
      'id': 'abc123',
      'pubkey': '987fed',
      'content': 'I hereby reply',
      'tags': [
        ['e', 'def456', 'TODO relay', 'reply'],
      ],
      'created_at': NOW_TS,
    }

    self.assertEqual(reply, to_as1(event))
    self.assertEqual(event, from_as1(reply))

  def test_to_from_as1_repost(self):
    repost = {
      'objectType': 'activity',
      'verb': 'share',
      'id': 'nostr:neventabc123',
      'published': NOW_ISO,
      'object': {
        'objectType': 'note',
        'id': 'nostr:notedef456',
        'author': {'id': 'nostr:npub987fed'},
        'content': 'The orig post',
        'published': THEN_ISO,
      },
    }
    event = {
      'kind': 6,
      'id': 'abc123',
      'content': json_dumps({
        'kind': 1,
        'id': 'def456',
        'pubkey': '987fed',
        'content': 'The orig post',
        'created_at': THEN_TS,
      }, sort_keys=True),
      'tags': [
        ['e', 'def456', 'TODO relay', 'mention'],
        ['p', '987fed'],
      ],
      'created_at': NOW_TS,
    }

    self.assertEqual(repost, to_as1(event))
    self.assertEqual(event, from_as1(repost))

    del event['content']
    self.assertEqual({
      **repost,
      'object': 'nostr:notedef456',
    }, to_as1(event))
