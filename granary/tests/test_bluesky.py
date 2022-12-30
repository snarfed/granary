"""Unit tests for jsonfeed.py.

Most tests are via files in testdata/.
"""
from oauth_dropins.webutil import testutil

from ..bluesky import (
  actor_to_ref,
  from_as1,
  to_as1,
)

ACTOR = {
  'objectType' : 'person',
  'displayName': 'Alice',
  'image': [{'url': 'https://alice.com/avatar'}],
  'url': ['http://alice.com/'],
}
ACTOR_REF = {  # app.bsky.actor.ref
  'did': 'TODO',
  'declaration': {
    'cid': 'TODO',
    'actorType': 'app.bsky.system.actorUser',
  },
  'handle': 'alice.com',
  'displayName': 'Alice',
  'avatar': 'https://alice.com/avatar',
}


class TestBluesky(testutil.TestCase):

    def test_from_as1_activity(self):
      obj = {
        'objectType': 'note',
        'content': 'foo',
      }
      activity = {
        'verb': 'post',
        'object': obj,
      }
      self.assert_equals(from_as1(obj), from_as1(activity))

    def test_to_as1_missing_objectType(self):
        with self.assertRaises(ValueError):
            to_as1({'foo': 'bar'})

    def test_to_as1_unknown_objectType(self):
        with self.assertRaises(ValueError):
            to_as1({'objectType': 'poll'})

    def test_to_as1_missing_type(self):
        with self.assertRaises(ValueError):
            to_as1({'foo': 'bar'})

    def test_to_as1_unknown_type(self):
        with self.assertRaises(ValueError):
            to_as1({'$type': 'app.bsky.foo'})

    def test_actor_to_ref(self):
      self.assert_equals(ACTOR_REF, actor_to_ref(ACTOR))
