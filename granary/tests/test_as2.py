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

  def test_from_as1_stop_following_object_str(self):
    self.assertEqual({
      '@context': 'https://www.w3.org/ns/activitystreams',
      'type': 'Undo',
      'id': 'unfollow',
      'actor': 'alice',
      'object': {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'type': 'Follow',
        'actor': 'alice',
        'object': 'bob',
      },
    }, as2.from_as1({
      'objectType': 'activity',
      'verb': 'stop-following',
      'id': 'unfollow',
      'actor': 'alice',
      'object': 'bob',
    }))

  def test_from_as1_icon_prefers_mastodon_allowed_type(self):
    self.assertEqual({
      'type': 'Image',
      'mediaType': 'image/jpeg',
      'url': '/pic',
    }, as2.from_as1({
      'objectType': 'person',
      'image': [
        '/pic.ico',
        {
          'objectType': 'image',
          'mimeType': 'image/jpeg',
          'url': '/pic',
        },
        '/pic.bmp',
      ],
    })['icon'])

  def test_from_as1_icon_prefers_mastodon_allowed_extension(self):
    self.assertEqual('/pic.jpg', as2.from_as1({
      'objectType': 'person',
      'image': [
        '/pic.ico',
        '/pic.jpg',
        '/pic.bmp',
      ],
    })['icon'])


  def test_from_as1_icon_prefers_mastodon_allowed_object(self):
    self.assertEqual({
      'type': 'Image',
      'url': '/pic.jpg',
    }, as2.from_as1({
      'objectType': 'person',
      'image': [
        '/pic.ico',
        {'url': '/pic.jpg'},
        '/pic.bmp',
      ],
    })['icon'])

  def test_bad_input_types(self):
    for bad in 1, [2], (3,):
      for fn in as2.to_as1, as2.from_as1:
        with self.assertRaises(ValueError):
          fn(bad)

    with self.assertRaises(ValueError):
      # wrongly trying to parse mf2 JSON as AS2
      as2.to_as1({'type': ['h-card']})

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

  def test_to_as1_image_attachment(self):
    """This is what Mastodon images look like."""
    self.assertEqual({
      'objectType': 'note',
      'image': [{
        'objectType': 'image',
        'mimeType': 'image/jpeg',
        'url': 'http://pic/ture.jpg',
      }],
      'attachments': [{
        'objectType': 'image',
        'mimeType': 'image/jpeg',
        'url': 'http://pic/ture.jpg',
      }]
    }, as2.to_as1({
      '@context': 'https://www.w3.org/ns/activitystreams',
      'type': 'Note',
      'attachment': [{
        'type': 'Document',
        'mediaType': 'image/jpeg',
        'url': 'http://pic/ture.jpg',
      }],
    }))

  def test_to_as1_image_attachment_mediatype_null(self):
    """This is what Mastodon images look like."""
    self.assertEqual({
      'objectType': 'note',
      'attachments': [{
        'url': 'http://pic/ture.jpg',
      }]
    }, as2.to_as1({
      '@context': 'https://www.w3.org/ns/activitystreams',
      'type': 'Note',
      'attachment': [{
        'mediaType': None,
        'url': 'http://pic/ture.jpg',
      }],
    }))

  def test_to_as1_attachment_composite_value(self):
    """Hubzilla includes attachments like these."""
    value = {
      'guid': '35d25147-cd86-48cb-b3f2-f687310363bd',
      'parent_guid': 'fbeaa30f-c402-4d58-91c0-e4bce187f1ed',
      'text': 'markdown here',
      'author': 'kostikov@zotum.net',
      'created_at': '2023-09-02T19:55:14Z',
      'author_signature': '...',
      'parent_author_signature': '...',
    }

    self.assertEqual({
      'objectType': 'note',
      'attachments': [{
        'displayName': 'zot.diaspora.fields',
        'value': {
          'guid': '35d25147-cd86-48cb-b3f2-f687310363bd',
          'parent_guid': 'fbeaa30f-c402-4d58-91c0-e4bce187f1ed',
          'text': 'markdown here',
          'author': 'kostikov@zotum.net',
          'created_at': '2023-09-02T19:55:14Z',
          'author_signature': '...',
          'parent_author_signature': '...',
        },
      }]
    }, as2.to_as1({
      'type': 'Note',
      'attachment': [{
        'type': 'PropertyValue',
        'name': 'zot.diaspora.fields',
        'value': value,
      }],
    }))

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

    self.assertFalse(is_public({'cc': [publics[1]]}, unlisted=False))

  def test_get_urls(self):
    for val, expected in (
        (None, []),
        ({}, []),
        ([None, 'asdf', {'href': 'qwert'}, {'foo': 'bar'}, 'qwert', {}],
         ['asdf', 'qwert']),
    ):
      self.assertEqual(expected, as2.get_urls({'url': val}))

  def test_lat_lon_float(self):
    '''Pixelfed returns them as strings, even though the spec says floats.'''
    self.assertEqual({
      'objectType': 'note',
      'location': {
        'objectType': 'place',
        'displayName': 'California',
        'longitude': -76.507450,
        'latitude': 38.3004,
        'position': '+38.300400-076.507450/',
      },
    }, as2.to_as1({
      '@context': 'https://www.w3.org/ns/activitystreams',
      'type': 'Note',
      'location': {
        'type': 'Place',
        'name': 'California',
        'longitude': '-76.507450',
        'latitude': '38.300400',
      },
    }))

  def test_lat_lon_not_float(self):
    with self.assertRaises(ValueError):
      as2.to_as1({
        '@context': 'https://www.w3.org/ns/activitystreams',
        'type': 'Note',
        'location': {
          'type': 'Place',
          'longitude': 'xyz',
          'latitude': 'abc',
        },
      })

  def test_address(self):
    for actor in [
        'http://a.b/@me',
        'http://a.b/users/me',
        'http://a.b/profile/me',
        {'id': 'http://a.b/@me'},
        {'id': 'http://a.b/users/me'},
        {'id': 'http://a.b/profile/me'},
        {'preferredUsername': 'me', 'id': 'https://a.b/c'},
        {'preferredUsername': 'me', 'url': 'https://a.b/c'},
        {'preferredUsername': 'me', 'id': 'https://a.b/c', 'url': 'https://d.e/f'},
        {'preferredUsername': 'me', 'id': 'tag:c.d:e', 'url': 'https://a.b/c'},
    ]:
      with self.subTest(actor=actor):
        self.assertEqual('@me@a.b', as2.address(actor))

    for bad in None, {}, '', {'a': 'b'}, {'preferredUsername': 'me'}:
      with self.subTest(actor=bad):
        self.assertIsNone(as2.address(bad))

  def test_person_featured_image_overrides_media_type(self):
    self.assert_equals({
      'objectType': 'person',
      'id': 'https://mastodon.xyz/users/alice',
      'displayName': '@alice@mastodon.xyz',
      'image': [{
        'url': 'https://banner/',
        'objectType': 'featured',
        'mimeType': 'image/jpeg',
       }],
    }, as2.to_as1({
      'type': 'Person',
      'id': 'https://mastodon.xyz/users/alice',
      'image': {
        'mediaType': 'image/jpeg',
        'url': 'https://banner'
      }
    }))

  def test_from_as1_person_propertyvalue_attachment_strips_home_page_slash(self):
    self.assert_equals({
      '@context': 'https://www.w3.org/ns/activitystreams',
      'type': 'Person',
      'id': 'tag:example.com,2011:martin',
      'url': 'https://example.com/',
      'attachment': [{
        'type': 'PropertyValue',
        'name': 'Link',
        'value': '<a rel="me" href="https://example.com"><span class="invisible">https://</span>example.com</a>',
      }],
    }, as2.from_as1({
      'objectType' : 'person',
      'id': 'tag:example.com,2011:martin',
      'url': 'https://example.com/',
    }))

  def test_to_as1_stop_following_object_id(self):
    self.assertEqual({
      'objectType': 'activity',
      'verb': 'stop-following',
      'actor': 'alice',
      'object': 'bob',
    }, as2.to_as1({
      'type': 'Undo',
      'actor': 'alice',
      'object': {
        'type': 'Follow',
        'actor': 'alice',
        'object': 'bob',
      },
    }))

  def test_to_as1_preferred_username(self):
    self.assertEqual({
      'objectType': 'person',
      'displayName': 'alice',
      'username': 'alice',
    }, as2.to_as1({
      'type': 'Person',
      'preferredUsername': 'alice',
    }))

  def test_to_as1_address(self):
    self.assertEqual({
      'objectType': 'person',
      'id': 'http://a.b/@me',
      'displayName': '@me@a.b',
    }, as2.to_as1({
      'type': 'Person',
      'id': 'http://a.b/@me',
    }))
