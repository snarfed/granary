# coding=utf-8
"""Unit tests for as2.py.

Most of the tests are in testdata/. This is just a few things that are too small
for full testdata tests.
"""
from oauth_dropins.webutil import testutil

from .. import as2
from ..as2 import is_public, PUBLICS


class ActivityStreams2Test(testutil.TestCase):

  def test_from_as1_blank(self):
    self.assertEqual({}, as2.from_as1(None))
    self.assertEqual({}, as2.from_as1({}))

  def test_to_as1_blank(self):
    self.assertEqual({}, as2.to_as1(None))
    self.assertEqual({}, as2.to_as1({}))

  def test_from_as1_context(self):
    self.assertEqual({
      'id': 'foo',
      '@context': 'bar',
    }, as2.from_as1({'id': 'foo'}, context='bar'))

  def test_bad_input_types(self):
    for bad in 1, [2], (3,):
      for fn in as2.to_as1, as2.from_as1:
        with self.assertRaises(ValueError):
          fn(bad)

    with self.assertRaises(ValueError):
      # wrongly trying to parse mf2 JSON as AS2
      as2.to_as1({'type': ['h-card']})

  def test_from_as1_misc(self):
    as2.from_as1({
      "objectType": "activity",
      "verb": "follow",
      "actor": {
        "objectType": "person",
        "image": [{
          "url": {
            "value": "https://www.jvt.me/img/profile.jpg",
            "alt": "Jamie Tanna's profile image"
          }
        }],
      },
    })

  def test_to_as1_in_reply_to_string(self):
    self._test_to_as1_in_reply_to('http://x.y/z')

  def test_to_as1_in_reply_to_list(self):
    self._test_to_as1_in_reply_to(['http://x.y/z'])

  def _test_to_as1_in_reply_to(self, in_reply_to):
    as1 = as2.to_as1({
      '@context': 'https://www.w3.org/ns/activitystreams',
      'type': 'Note',
      'content': 'foo bar baz',
      'inReplyTo': in_reply_to,
    })
    self.assertEqual(['http://x.y/z'], as1['inReplyTo'])

  def test_is_public(self):
    publics = list(PUBLICS)
    for result, input in (
        (True, {'to': [publics[1]]}),
        (True, {'cc': [publics[1]]}),
        (True, {'to': ['foo', publics[0]], 'cc': ['bar', publics[2]]}),
        (False, {}),
        (False, {'to': ['foo']}),
        (False, {'cc': ['bar']}),
        (False, {'to': ['foo'], 'cc': ['bar']}),
    ):
      self.assertEqual(result, is_public(input))
      self.assertEqual(result, is_public({'object': input}))
      input['object'] = 'foo'
      self.assertEqual(result, is_public(input))

    self.assertFalse(is_public('foo'))
