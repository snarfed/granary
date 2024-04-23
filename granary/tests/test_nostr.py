"""Unit tests for nostr.py."""
from contextlib import contextmanager
from datetime import timedelta
import logging
import secrets

from oauth_dropins.webutil.util import HTTP_TIMEOUT, json_dumps, json_loads
from oauth_dropins.webutil import testutil
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

from .. import nostr
from ..nostr import from_as1, id_for, id_to_uri, is_bech32, to_as1, uri_to_id

NOW_TS = int(testutil.NOW.timestamp())
NOW_ISO = testutil.NOW.replace(tzinfo=None).isoformat()
THEN_TS = NOW_TS - 1
THEN_ISO = (testutil.NOW - timedelta(seconds=1)).replace(tzinfo=None).isoformat()

ID = '3bf0c63fcb93463407af97a5e5ee64fa883d107ef9e558472c4eb9aaaefa459d'
URI = 'nostr:npub180cvv07tjdrrgpa0j7j7tmnyl2yr6yr7l8j4s3evf6u64th6gkwsyjh6w6'

NOTE_NOSTR = {
  'kind': 1,
  'id': '12ab',
  'pubkey': '98fe',
  'content': 'Something to say',
  'tags': [],
}
NOTE_AS1 = {
  'objectType': 'note',
  'id': 'nostr:note1z24swknlsf',
  'author': 'nostr:npub1nrlqrdny0w',
  'content': 'Something to say',
}

logger = logging.getLogger(__name__)


class FakeConnection:
  """Fake of :class:`websockets.sync.client.ClientConnection`."""

  @classmethod
  def reset(cls):
    cls.relay = None
    cls.sent = []
    cls.to_receive = []
    cls.closed = False
    cls.recv_err = cls.send_err = None

  @classmethod
  def send(cls, msg):
    if cls.send_err:
      raise cls.send_err

    assert not cls.closed
    cls.sent.append(json_loads(msg))
    logger.info(msg)

  @classmethod
  def recv(cls, timeout=None):
    assert timeout == HTTP_TIMEOUT

    if not cls.to_receive:
      closed = True
      assert cls.recv_err
      raise cls.recv_err

    msg = cls.to_receive.pop(0)
    logger.info(msg)
    return json_dumps(msg)


@contextmanager
def fake_connect(uri, open_timeout=None, close_timeout=None):
  """Fake of :func:`websockets.sync.client.connect`."""
  assert open_timeout == HTTP_TIMEOUT
  assert close_timeout == HTTP_TIMEOUT
  FakeConnection.relay = uri
  yield FakeConnection


class NostrTest(testutil.TestCase):

  def setUp(self):
    super().setUp()
    FakeConnection.reset()

  def test_id_for(self):
    self.assertEqual(
      '9adfa2330b391539f46548ff2e088ea964a2f7374898c7335a86e914cbf2e769',
      id_for({
        'pubkey': 'fed987',
        'created_at': NOW_TS,
        'kind': 1,
        'content': 'My plain text',
    }))

  def test_id_to_uri(self):
    self.assertEqual(URI, id_to_uri('npub', ID))

  def test_uri_to_id(self):
    self.assertEqual(ID, uri_to_id(URI))
    self.assertEqual('http://not/nostr', uri_to_id('http://not/nostr'))

  def test_is_bech32(self):
    self.assertTrue(is_bech32('nostr:npubabc'))
    self.assertTrue(is_bech32('neventabc'))
    self.assertFalse(is_bech32('abc'))
    self.assertFalse(is_bech32(None))

  def test_to_from_as1_profile(self):
    person = {
      'objectType': 'person',
      'id': 'nostr:npub1z24szqzphd',
      'displayName': 'Alice',
      'description': 'It me',
      'image': 'http://alice/pic',
      'username': 'alice.com',
      'urls': [
        'https://github.com/semisol',
        'https://twitter.com/semisol_public',
        'https://bitcoinhackers.org/@semisol',
        'https://t.me/1087295469',
      ],
    }
    event = {
      'kind': 0,
      'id': '12ab',
      'pubkey': '12ab',
      'content': json_dumps({
        'name': 'Alice',
        'about': 'It me',
        'picture': 'http://alice/pic',
        'nip05': '_@alice.com',
      }, sort_keys=True),
      'tags': [
        ['i', 'github:semisol', '-'],
        ['i', 'twitter:semisol_public', '-'],
        ['i', 'mastodon:bitcoinhackers.org/@semisol', '-'],
        ['i', 'telegram:1087295469', '-'],
      ],
    }
    self.assert_equals(person, to_as1(event))

    # we don't try to detect which URLs might be Mastodon
    del event['tags'][2]
    self.assert_equals(event, from_as1(person))

  def test_to_as1_profile_bad_nip05(self):
    self.assert_equals({
      'objectType': 'person',
      'id': 'nostr:npub1z24szqzphd',
    }, to_as1({
      'kind': 0,
      'id': '12ab',
      'pubkey': '12ab',
      'content': '{"nip05": {}}',
    }))

  def test_to_from_as1_note(self):
    note = {
      'objectType': 'note',
      'id': 'nostr:note1z24swknlsf',
      'author': 'nostr:npub1nrlqrdny0w',
      'content': 'Something to say',
      'published': NOW_ISO,
    }
    event = {
      'kind': 1,
      'id': '12ab',
      'pubkey': '98fe',
      'content': 'Something to say',
      'created_at': NOW_TS,
      'tags': [],
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))

  def test_from_as1_post_activity(self):
    self.assertEqual(NOTE_NOSTR, from_as1({
      'objectType': 'activity',
      'verb': 'post',
      'object': NOTE_AS1,
    }))

  def test_from_as1_update_activity(self):
    self.assertEqual(NOTE_NOSTR, from_as1({
      'objectType': 'activity',
      'verb': 'update',
      'object': NOTE_AS1,
    }))

  def test_from_as1_reject_activity_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      from_as1({
        'objectType': 'activity',
        'verb': 'reject',
        'object': NOTE_AS1,
      })

  def test_to_from_as1_note_subject_tag(self):
    note = {
      'objectType': 'note',
      'id': 'nostr:note1z24swknlsf',
      'content': 'Something to say',
      'title': 'my thing',
    }
    event = {
      'kind': 1,
      'id': '12ab',
      'content': 'Something to say',
      'tags': [
        ['title', 'my thing'],
        ['subject', 'my thing'],
      ],
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))

  def test_to_from_as1_note_with_hashtag(self):
    note = {
      'objectType': 'note',
      'id': 'nostr:note1z24swknlsf',
      'author': 'nostr:npub1nrlqrdny0w',
      'content': 'Something to say',
      'published': NOW_ISO,
      'tags': [{
        'objectType': 'hashtag',
        'displayName': 'foo',
      }, {
        'objectType': 'hashtag',
        'displayName': 'bar',
      }],
    }
    event = {
      'kind': 1,
      'id': '12ab',
      'pubkey': '98fe',
      'content': 'Something to say',
      'created_at': NOW_TS,
      'tags': [
        ['t', 'foo'],
        ['t', 'bar'],
      ],
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))

  def test_to_from_as1_note_with_location(self):
    note = {
      'objectType': 'note',
      'id': 'nostr:note1z24swknlsf',
      'author': 'nostr:npub1nrlqrdny0w',
      'content': 'Something to say',
      'published': NOW_ISO,
      'location': {
        'displayName': 'my house',
      },
    }
    event = {
      'kind': 1,
      'id': '12ab',
      'pubkey': '98fe',
      'content': 'Something to say',
      'created_at': NOW_TS,
      'tags': [
        ['location', 'my house'],
      ],
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))

  def test_to_from_as1_article(self):
    note = {
      'objectType': 'article',
      'id': 'nostr:note1z24swknlsf',
      'author': 'nostr:npub1nrlqrdny0w',
      'title': 'a thing',
      'summary': 'about the thing',
      'content': 'Something to say',
      'published': NOW_ISO,
    }
    event = {
      'kind': 30023,
      'id': '12ab',
      'pubkey': '98fe',
      'content': 'Something to say',
      'created_at': NOW_TS,
      'tags': [
        # TODO: NIP-33 'd' tag for slug
        ['published_at', str(NOW_TS)],
        ['title', 'a thing'],
        ['subject', 'a thing'],
        ['summary', 'about the thing'],
      ],
    }
    self.assertEqual(note, to_as1(event))
    self.assertEqual(event, from_as1(note))

  def test_to_from_as1_reply(self):
    reply = {
      'objectType': 'note',
      'id': 'nostr:note1z24swknlsf',
      'author': 'nostr:npub1nrlqrdny0w',
      'published': NOW_ISO,
      'content': 'I hereby reply',
      'inReplyTo': 'nostr:nevent1xnxsm5fasn',
    }
    event = {
      'kind': 1,
      'id': '12ab',
      'pubkey': '98fe',
      'content': 'I hereby reply',
      'tags': [
        ['e', '34cd', 'TODO relay', 'reply'],
      ],
      'created_at': NOW_TS,
    }

    self.assertEqual(reply, to_as1(event))
    self.assertEqual(event, from_as1(reply))

  def test_to_from_as1_repost(self):
    repost = {
      'objectType': 'activity',
      'verb': 'share',
      'id': 'nostr:nevent1z24spd6d40',
      'published': NOW_ISO,
      'object': {
        'objectType': 'note',
        'id': 'nostr:note1xnxs50q044',
        'author': 'nostr:npub1nrlqrdny0w',
        'content': 'The orig post',
        'published': THEN_ISO,
      },
    }
    event = {
      'kind': 6,
      'id': '12ab',
      'content': json_dumps({
        'kind': 1,
        'id': '34cd',
        'pubkey': '98fe',
        'content': 'The orig post',
        'created_at': THEN_TS,
        'tags': [],
      }, sort_keys=True),
      'tags': [
        ['e', '34cd', 'TODO relay', 'mention'],
        ['p', '98fe'],
      ],
      'created_at': NOW_TS,
    }

    self.assertEqual(repost, to_as1(event))
    self.assertEqual(event, from_as1(repost))

    del event['content']
    self.assertEqual({
      **repost,
      'object': 'nostr:note1xnxs50q044',
    }, to_as1(event))

  def test_to_from_as1_like(self):
    like = {
      'objectType': 'activity',
      'verb': 'like',
      'id': 'nostr:nevent1z24spd6d40',
      'published': NOW_ISO,
      'object': 'nostr:nevent1xnxsm5fasn',
    }
    event = {
      'kind': 7,
      'id': '12ab',
      'content': '+',
      'tags': [['e', '34cd']],
      'created_at': NOW_TS,
    }

    self.assertEqual(like, to_as1(event))
    self.assertEqual(event, from_as1(like))

  def test_to_from_as1_dislike(self):
    like = {
      'objectType': 'activity',
      'verb': 'dislike',
      'id': 'nostr:nevent1z24spd6d40',
      'published': NOW_ISO,
      'object': 'nostr:nevent1xnxsm5fasn',
    }
    event = {
      'kind': 7,
      'id': '12ab',
      'content': '-',
      'tags': [['e', '34cd']],
      'created_at': NOW_TS,
    }

    self.assertEqual(like, to_as1(event))
    self.assertEqual(event, from_as1(like))

  def test_to_from_as1_reaction(self):
    react = {
      'objectType': 'activity',
      'verb': 'react',
      'id': 'nostr:nevent1z24spd6d40',
      'content': '😀',
      'published': NOW_ISO,
      'object': 'nostr:nevent1xnxsm5fasn',
    }
    event = {
      'kind': 7,
      'id': '12ab',
      'content': '😀',
      'tags': [['e', '34cd']],
      'created_at': NOW_TS,
    }

    self.assertEqual(react, to_as1(event))
    self.assertEqual(event, from_as1(react))

  def test_to_from_as1_delete(self):
    delete = {
      'objectType': 'activity',
      'verb': 'delete',
      'id': 'nostr:nevent1z24spd6d40',
      'published': NOW_ISO,
      'object': 'nostr:nevent1xnxsm5fasn',
      'content': 'a note about the delete',
    }
    event = {
      'kind': 5,
      'id': '12ab',
      'content': 'a note about the delete',
      'tags': [['e', '34cd']],
      'created_at': NOW_TS,
    }

    self.assertEqual(delete, to_as1(event))
    self.assertEqual(event, from_as1(delete))

  def test_to_from_as1_followings(self):
    follow = {
      'objectType': 'activity',
      'verb': 'follow',
      'id': 'nostr:nevent1z24spd6d40',
      'actor': 'nostr:npub1nrlqrdny0w',
      'published': NOW_ISO,
      'object': [
        'nostr:npub1xnxsce33j3',
        {'id': 'nostr:npub1nrlqrdny0w', 'displayName': 'bob'},
      ],
      'content': 'not important',
    }
    event = {
      'kind': 3,
      'id': '12ab',
      'pubkey': '98fe',
      'content': 'not important',
      'tags': [
        ['p', '34cd', 'TODO relay', ''],
        ['p', '98fe', 'TODO relay', 'bob'],
      ],
      'created_at': NOW_TS,
    }

    self.assertEqual(follow, to_as1(event))
    self.assertEqual(event, from_as1(follow))


class GetActivitiesTest(testutil.TestCase):
  last_token = None

  def setUp(self):
    super().setUp()

    self.last_token = 0
    self.mox.stubs.Set(secrets, 'token_urlsafe', self.token)

    FakeConnection.reset()

    nostr.connect = fake_connect

    self.nostr = nostr.Nostr(['ws://relay'])

  def token(self, length):
    self.last_token += 1
    return f'towkin {self.last_token}'

  def test_activity_id(self):
    FakeConnection.to_receive = [
      ['EVENT', 'towkin 1', NOTE_NOSTR],
      ['EOSE', 'towkin 1'],
      ['not', 'reached']
    ]

    self.assert_equals([NOTE_AS1],
                       self.nostr.get_activities(activity_id='ab12'))

    self.assertEqual('ws://relay', FakeConnection.relay)
    self.assertEqual([
      ['REQ', 'towkin 1', {'ids': ['ab12'], 'limit': 20}],
      ['CLOSE', 'towkin 1'],
    ], FakeConnection.sent)
    self.assertEqual([['not', 'reached']], FakeConnection.to_receive)

  def test_user_id(self):
    events = [{
      **NOTE_NOSTR,
      'id': str(i) * 4,
      'content': f"It's {i}",
    } for i in range(3)]
    notes = [{
      **NOTE_AS1,
      'id': id_to_uri('note', str(i) * 4),
      'content': f"It's {i}",
    } for i in range(3)]

    FakeConnection.to_receive = \
      [['EVENT', 'towkin 1', e] for e in events] + [['EOSE', 'towkin 1']]

    self.assert_equals(notes, self.nostr.get_activities(user_id='ab12', count=3))
    self.assertEqual([
      ['REQ', 'towkin 1', {'authors': ['ab12'], 'limit': 3}],
      ['CLOSE', 'towkin 1'],
    ], FakeConnection.sent)
    self.assertEqual([], FakeConnection.to_receive)

  def test_search(self):
    FakeConnection.to_receive = \
      [['EVENT', 'towkin 1', NOTE_NOSTR]] + [['EOSE', 'towkin 1']]

    self.assert_equals([NOTE_AS1],
                       self.nostr.get_activities(search_query='surch'))
    self.assertEqual([
      ['REQ', 'towkin 1', {'search': 'surch', 'limit': 20}],
      ['CLOSE', 'towkin 1'],
    ], FakeConnection.sent)

  def test_fetch_replies(self):
    reply_nostr = {
      'kind': 1,
      'id': '34cd',
      'pubkey': '98fe',
      'content': 'I hereby reply',
      'tags': [['e', '12ab', 'TODO relay', 'reply']],
    }
    reply_as1 = {
      'objectType': 'note',
      'id': 'nostr:note1xnxs50q044',
      'author': 'nostr:npub1nrlqrdny0w',
      'content': 'I hereby reply',
      'inReplyTo': 'nostr:nevent1z24spd6d40',
    }
    FakeConnection.to_receive = [
      ['EVENT', 'towkin 1', NOTE_NOSTR],
      ['EVENT', 'towkin 1', {**NOTE_NOSTR, 'id': '98fe'}],
      ['EOSE', 'towkin 1'],
      ['EVENT', 'towkin 2', reply_nostr],
      ['EVENT', 'towkin 2', reply_nostr],
      ['EOSE', 'towkin 2'],
    ]

    self.assert_equals([
      {**NOTE_AS1, 'replies': {'totalItems': 2, 'items': [reply_as1] * 2}},
      {**NOTE_AS1, 'id': 'nostr:note1nrlq0mz6g2'},
    ], self.nostr.get_activities(user_id='98fe', fetch_replies=True))

    self.assertEqual('ws://relay', FakeConnection.relay)
    self.assertEqual([
      ['REQ', 'towkin 1', {'authors': ['98fe'], 'limit': 20}],
      ['CLOSE', 'towkin 1'],
      ['REQ', 'towkin 2', {'#e': ['12ab', '98fe'], 'limit': 20}],
      ['CLOSE', 'towkin 2'],
    ], FakeConnection.sent)

  def test_fetch_shares(self):
    repost_nostr = {
      'kind': 6,
      'id': '34cd',
      'pubkey': '98fe',
      'tags': [['e', '12ab', 'TODO relay', 'mention']],
    }
    repost_as1 = {
      'objectType': 'activity',
      'actor': 'nostr:npub1nrlqrdny0w',
      'verb': 'share',
      'id': 'nostr:nevent1xnxsm5fasn',
      'object': 'nostr:note1z24swknlsf',
    }

    FakeConnection.to_receive = [
      ['EVENT', 'towkin 1', NOTE_NOSTR],
      ['EOSE', 'towkin 1'],
      ['EVENT', 'towkin 2', repost_nostr],
      ['EVENT', 'towkin 2', repost_nostr],
      ['EOSE', 'towkin 2'],
    ]

    self.assert_equals([
      {**NOTE_AS1, 'tags': [repost_as1, repost_as1]},
    ], self.nostr.get_activities(user_id='98fe', fetch_shares=True))

    self.assertEqual('ws://relay', FakeConnection.relay)
    self.assertEqual([
      ['REQ', 'towkin 1', {'authors': ['98fe'], 'limit': 20}],
      ['CLOSE', 'towkin 1'],
      ['REQ', 'towkin 2', {'#e': ['12ab'], 'limit': 20}],
      ['CLOSE', 'towkin 2'],
    ], FakeConnection.sent)

  def test_ok_false_closes_query(self):
    FakeConnection.to_receive = [
      ['OK', 'towkin 1', False],
      ['EVENT', 'towkin 1', NOTE_NOSTR],
    ]

    self.assert_equals([], self.nostr.get_activities())
    self.assertEqual([['EVENT', 'towkin 1', NOTE_NOSTR]], FakeConnection.to_receive)

  def test_create_note(self):
    FakeConnection.to_receive = [
      ['OK', NOTE_NOSTR['id'], True],
    ]

    result = self.nostr.create(NOTE_AS1)
    self.assert_equals(NOTE_NOSTR, result.content)
    self.assertEqual([['EVENT', NOTE_NOSTR]], FakeConnection.sent)

  def test_create_note_ok_false(self):
    FakeConnection.to_receive = [
      ['OK', NOTE_NOSTR['id'], False, 'foo bar'],
    ]

    result = self.nostr.create(NOTE_AS1)
    self.assertEqual('foo bar', result.error_plain)
    self.assertTrue(result.abort)

  def test_get_actor_npub(self):
    profile = {
      'kind': 0,
      'id': '12ab',
      'pubkey': '12ab',
      'content': json_dumps({
        'name': 'Alice',
        'nip05': '_@alice.com',
      }, sort_keys=True),
    }
    person = {
      'objectType': 'person',
      'id': 'nostr:npub1z24szqzphd',
      'displayName': 'Alice',
      'username': 'alice.com',
    }
    FakeConnection.to_receive = [
      ['EVENT', 'towkin 1', profile],
      ['EOSE', 'towkin 1'],
    ]

    self.assert_equals(person, self.nostr.get_actor(user_id='nostr:npub1z24szqzphd'))
    self.assertEqual([
      ['REQ', 'towkin 1', {'authors': ['12ab'], 'kinds': [0], 'limit': 20}],
      ['CLOSE', 'towkin 1'],
    ], FakeConnection.sent)

  def test_query_connection_closed_ok_send_immediate(self):
    FakeConnection.send_err = ConnectionClosedOK(None, None)

    with fake_connect('wss://my-relay',
                      open_timeout=HTTP_TIMEOUT,
                      close_timeout=HTTP_TIMEOUT,
                      ) as ws:
      self.assertEqual([], self.nostr.query(ws, {}))

  def test_query_connection_closed_ok_recv_immediate(self):
    FakeConnection.recv_err = ConnectionClosedOK(None, None)

    with fake_connect('wss://my-relay',
                      open_timeout=HTTP_TIMEOUT,
                      close_timeout=HTTP_TIMEOUT,
                      ) as ws:
      self.assertEqual([], self.nostr.query(ws, {}))

  def test_query_connection_closed_ok_recv_partial_results(self):
    FakeConnection.to_receive = [
      ['EVENT', 'towkin 1', NOTE_NOSTR],
      ['EVENT', 'towkin 1', NOTE_NOSTR],
    ]
    FakeConnection.recv_err = ConnectionClosedOK(None, None)

    with fake_connect('wss://my-relay',
                      open_timeout=HTTP_TIMEOUT,
                      close_timeout=HTTP_TIMEOUT,
                      ) as ws:
      self.assertEqual([NOTE_NOSTR, NOTE_NOSTR], self.nostr.query(ws, {}))

  def test_query_connection_closed_error_recv_raises(self):
    FakeConnection.to_receive = [
      ['EVENT', 'towkin 1', NOTE_NOSTR],
    ]
    FakeConnection.recv_err = ConnectionClosedError(None, None)

    with fake_connect('wss://my-relay',
                      open_timeout=HTTP_TIMEOUT,
                      close_timeout=HTTP_TIMEOUT,
                      ) as ws:
      with self.assertRaises(ConnectionClosedError):
        self.nostr.query(ws, {})
