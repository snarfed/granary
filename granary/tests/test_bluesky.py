"""Unit tests for bluesky.py.

Most tests are via files in testdata/.
"""
import copy
from unittest.mock import patch

from oauth_dropins.webutil import testutil, util
from oauth_dropins.webutil.testutil import NOW, requests_response
from oauth_dropins.webutil.util import trim_nulls
import requests

from ..bluesky import (
  AT_URI_PATTERN,
  at_uri_to_web_url,
  blob_to_url,
  Bluesky,
  did_web_to_url,
  from_as1,
  MAX_IMAGES,
  to_as1,
  url_to_did_web,
  web_url_to_at_uri,
)
from ..source import ALL, FRIENDS, ME, SELF

ACTOR_AS = {
  'objectType': 'person',
  'id': 'did:web:alice.com',
  'displayName': 'Alice',
  'image': [{'url': 'https://alice.com/alice.jpg'}],
  'url': 'https://alice.com/',
  'summary': 'hi there',
}
ACTOR_PROFILE_VIEW_BSKY = {
  '$type': 'app.bsky.actor.defs#profileView',
  'did': 'did:web:alice.com',
  'handle': 'alice.com',
  'displayName': 'Alice',
  'avatar': 'https://alice.com/alice.jpg',
  'description': 'hi there',
}
NEW_BLOB = {  # new blob format: https://atproto.com/specs/data-model#blob-type
  '$type': 'blob',
  'ref': {'$link': 'bafkreim'},
  'mimeType': 'image/jpeg',
  'size': 154296,
}
NEW_BLOB_URL = 'https://bsky.social/xrpc/com.atproto.sync.getBlob?did=did:plc:foo&cid=bafkreim'
OLD_BLOB = {  # old blob format: https://atproto.com/specs/data-model#blob-type
  'cid': 'bafyjrot',
  'mimeType': 'image/jpeg',
}
OLD_BLOB_URL = 'https://bsky.social/xrpc/com.atproto.sync.getBlob?did=did:plc:foo&cid=bafyjrot'
ACTOR_PROFILE_BSKY = {
  '$type': 'app.bsky.actor.profile',
  'displayName': 'Alice',
  'avatar': NEW_BLOB,
  'banner': OLD_BLOB,
  'description': 'hi there',
}

POST_AS = {
  'objectType': 'activity',
  'id': 'at://did/app.bsky.feed.post/tid',
  'verb': 'post',
  'actor': ACTOR_AS,
  'object': {
    'objectType': 'note',
    'id': 'at://did/app.bsky.feed.post/tid',
    'url': 'https://bsky.app/profile/did/post/tid',
    'published': '2007-07-07T03:04:05',
    'content': 'My original post',
  }
}
POST_BSKY = {
  '$type': 'app.bsky.feed.post',
  'text': 'My original post',
  'createdAt': '2007-07-07T03:04:05',
}
POST_VIEW_BSKY = {
  '$type': 'app.bsky.feed.defs#postView',
  'uri': 'at://did/app.bsky.feed.post/tid',
  'cid': 'TODO',
  'record': {
    '$type': 'app.bsky.feed.post',
    'text': 'My original post',
    'createdAt': '2007-07-07T03:04:05',
  },
  'author': {
    '$type': 'app.bsky.actor.defs#profileViewBasic',
    'did': '',
    'handle': '',
  },
  'replyCount': 0,
  'repostCount': 0,
  'likeCount': 0,
  'indexedAt': '2022-01-02T03:04:05+00:00',
}

POST_AUTHOR_AS = copy.deepcopy(POST_AS)
POST_AUTHOR_AS['object'].update({
  'author': ACTOR_AS,
  'url': 'https://bsky.app/profile/alice.com/post/tid',
})
POST_AUTHOR_PROFILE_AS = copy.deepcopy(POST_AUTHOR_AS)
POST_AUTHOR_PROFILE_AS['object']['author'].update({
  'username': 'alice.com',
  'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
})
POST_AUTHOR_PROFILE_AS['actor'].update({
  'username': 'alice.com',
  'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
})
POST_AUTHOR_BSKY = copy.deepcopy(POST_VIEW_BSKY)
POST_AUTHOR_BSKY['author'] = {
  **ACTOR_PROFILE_VIEW_BSKY,
  '$type': 'app.bsky.actor.defs#profileViewBasic',
}
POST_FEED_VIEW_BSKY = {
  '$type': 'app.bsky.feed.defs#feedViewPost',
  'post': POST_AUTHOR_BSKY,
}

FACETS = [{
  '$type': 'app.bsky.richtext.facet',
  'features': [{
    '$type': 'app.bsky.richtext.facet#link',
    'uri': 'http://my/link',
  }],
  'index': {
    'byteStart': 3,
    'byteEnd': 11,
  },
}]
FACET_TAG = {
  'objectType': 'article',
  'url': 'http://my/link',
  'displayName': 'original',
  'startIndex': 3,
  'length': 8,
}
EMBED_EXTERNAL = {
  'description': '',
  'title': 'a link',
  'uri': 'http://my/link',
}
EMBED_EXTERNAL_ATTACHMENT = {
  'objectType': 'link',
  'url': 'http://my/link',
  'displayName': 'a link',
}
POST_AS_EMBED = {
  **POST_AS['object'],
  'attachments': [EMBED_EXTERNAL_ATTACHMENT],
}
POST_BSKY_EMBED = copy.deepcopy(POST_BSKY)
POST_BSKY_EMBED['embed'] = {
  '$type': 'app.bsky.embed.external',
  'external': {
    '$type': 'app.bsky.embed.external#external',
    **EMBED_EXTERNAL,
  },
}

POST_VIEW_BSKY_EMBED = copy.deepcopy(POST_VIEW_BSKY)
POST_VIEW_BSKY_EMBED['record']['embed'] = POST_BSKY_EMBED['embed']
POST_VIEW_BSKY_EMBED['embed'] = {
  '$type': 'app.bsky.embed.external#view',
  'external': {
    '$type': 'app.bsky.embed.external#viewExternal',
    **EMBED_EXTERNAL,
  },
}
POST_AS_IMAGES = copy.deepcopy(POST_AS)
POST_AS_IMAGES['object']['image'] = [{
  'url': NEW_BLOB_URL,
  'displayName': 'my alt text',
}]

EMBED_IMAGES = {
  '$type': 'app.bsky.embed.images',
  'images': [{
    '$type': 'app.bsky.embed.images#image',
    'alt': 'my alt text',
    'image': NEW_BLOB,
  }],
}
POST_BSKY_IMAGES = copy.deepcopy(POST_BSKY)
POST_BSKY_IMAGES['embed'] = EMBED_IMAGES

POST_VIEW_BSKY_IMAGES = copy.deepcopy(POST_VIEW_BSKY)
POST_VIEW_BSKY_IMAGES['record']['embed'] = EMBED_IMAGES
POST_VIEW_BSKY_IMAGES['embed'] = {
  '$type': 'app.bsky.embed.images#view',
  'images': [{
    '$type': 'app.bsky.embed.images#viewImage',
    'alt': 'my alt text',
    'fullsize': NEW_BLOB_URL,
    'thumb': NEW_BLOB_URL,
  }],
}

REPLY_AS = {
  'objectType': 'activity',
  'verb': 'post',
  'object': {
    'objectType': 'comment',
    'published': '2008-08-08T03:04:05',
    'content': 'I hereby reply to this',
    'id': 'at://did/app.bsky.feed.post/tid',
    'url': 'https://bsky.app/profile/did/post/tid',
    'inReplyTo': [{
      'id': 'at://did/app.bsky.feed.post/parent-tid',
      'url': 'https://bsky.app/profile/did/post/parent-tid',
    }],
  },
}
REPLY_BSKY = {
  '$type': 'app.bsky.feed.post',
  'text': 'I hereby reply to this',
  'createdAt': '2008-08-08T03:04:05',
  'reply': {
    '$type': 'app.bsky.feed.post#replyRef',
    'root': {
      '$type': 'com.atproto.repo.strongRef',
      'uri': 'at://did/app.bsky.feed.post/parent-tid',
      'cid': 'TODO',
    },
    'parent': {
      '$type': 'com.atproto.repo.strongRef',
      'uri': 'at://did/app.bsky.feed.post/parent-tid',
      'cid': 'TODO',
    },
  },
}
REPLY_POST_VIEW_BSKY = copy.deepcopy(POST_VIEW_BSKY)
REPLY_POST_VIEW_BSKY.update({
  'uri': 'at://did/app.bsky.feed.post/tid',
  'record': REPLY_BSKY,
})

REPOST_AS = {
  'objectType': 'activity',
  'verb': 'share',
  'actor': {
    'objectType': 'person',
    'id': 'did:web:bob.com',
    'displayName': 'Bob',
    'url': ['https://bsky.app/profile/bob.com', 'https://bob.com/'],
  },
  'object': POST_AUTHOR_PROFILE_AS['object'],
}
REPOST_PROFILE_AS = copy.deepcopy(REPOST_AS)
REPOST_PROFILE_AS['actor'].update({
  'username': 'bob.com',
  'url': ['https://bsky.app/profile/bob.com', 'https://bob.com/'],
})

REPOST_BSKY = {
  '$type': 'app.bsky.feed.repost',
  'subject': {
    'uri': 'at://did/app.bsky.feed.post/tid',
    'cid': 'TODO',
  },
  'createdAt': '2022-01-02T03:04:05+00:00',
}
REPOST_BSKY_REASON = {
  '$type': 'app.bsky.feed.defs#reasonRepost',
  'by': {
    '$type': 'app.bsky.actor.defs#profileViewBasic',
    'did': 'did:web:bob.com',
    'handle': 'bob.com',
    'displayName': 'Bob',
  },
  'indexedAt': NOW.isoformat(),
}
REPOST_BSKY_FEED_VIEW_POST = {
  '$type': 'app.bsky.feed.defs#feedViewPost',
  'post': POST_AUTHOR_BSKY,
  'reason': REPOST_BSKY_REASON,
}

THREAD_AS = copy.deepcopy(POST_AS)
THREAD_REPLY_AS = copy.deepcopy(REPLY_AS['object'])
THREAD_REPLY_AS['id'] = 'tag:bsky.app:at://did/app.bsky.feed.post/tid'
THREAD_REPLY2_AS = copy.deepcopy(REPLY_AS['object'])
THREAD_REPLY2_AS['id'] = 'tag:bsky.app:at://did/app.bsky.feed.post/tid2'
THREAD_REPLY2_AS['url'] = 'https://bsky.app/profile/did/post/tid2'
THREAD_REPLY2_AS['inReplyTo'] = [{
  'id': 'at://did/app.bsky.feed.post/tid',
  'url': 'https://bsky.app/profile/did/post/tid'
}]
THREAD_AS['object']['replies'] = {'items': [THREAD_REPLY_AS, THREAD_REPLY2_AS]}
THREAD_AS['object']['author'] = ACTOR_AS
THREAD_AS['object']['author'].update({
  'username': 'alice.com',
  'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
})
THREAD_AS['object']['url'] = 'https://bsky.app/profile/alice.com/post/tid'
THREAD_AS['actor'].update({
  'username': 'alice.com',
  'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
})

THREAD_BSKY = {
  '$type': 'app.bsky.feed.defs#threadViewPost',
  'post': POST_AUTHOR_BSKY,
  'replies': [{
    '$type': 'app.bsky.feed.defs#threadViewPost',
    'post': copy.deepcopy(REPLY_POST_VIEW_BSKY),
    'replies': [{
      '$type': 'app.bsky.feed.defs#threadViewPost',
      'post': copy.deepcopy(REPLY_POST_VIEW_BSKY),
      'replies': [],
    }],
  }],
}
THREAD_BSKY['replies'][0]['replies'][0]['post'].update({
  'uri': 'at://did/app.bsky.feed.post/tid2'
})
THREAD_BSKY['replies'][0]['replies'][0]['post']['record']['reply'].update({
  'parent': {
    '$type': 'com.atproto.repo.strongRef',
    'uri': 'at://did/app.bsky.feed.post/tid',
    'cid': 'TODO'
  }
})

BLOB = {
  '$type': 'blob',
  'ref': 'a CID',
  'mimeType': 'foo/bar',
  'size': 13,
}

POST_FEED_VIEW_WITH_LIKES_BSKY = copy.deepcopy(POST_FEED_VIEW_BSKY)
POST_FEED_VIEW_WITH_LIKES_BSKY['post']['likeCount'] = 1
POST_FEED_VIEW_WITH_REPOSTS_BSKY = copy.deepcopy(POST_FEED_VIEW_BSKY)
POST_FEED_VIEW_WITH_REPOSTS_BSKY['post']['repostCount'] = 1
POST_FEED_VIEW_WITH_REPLIES_BSKY = copy.deepcopy(POST_FEED_VIEW_BSKY)
POST_FEED_VIEW_WITH_REPLIES_BSKY['post']['replyCount'] = 1

LIKE_BSKY = {
  '$type': 'app.bsky.feed.like',
  'subject': {
    'uri': 'at://did/app.bsky.feed.post/tid',
    'cid': 'TODO',
  },
  'createdAt': '2008-08-08T03:04:05',
}

GET_LIKES_LIKE_BSKY = {
  '$type': 'app.bsky.feed.getLikes#like',
  'indexedAt': NOW.isoformat(),
  'createdAt': '2008-08-08T03:04:05',
  'actor': ACTOR_PROFILE_VIEW_BSKY,
}

POST_AUTHOR_PROFILE_WITH_LIKES_AS = copy.deepcopy(POST_AUTHOR_PROFILE_AS)
POST_AUTHOR_PROFILE_WITH_LIKES_AS['object']['tags'] = [{
  'author': copy.deepcopy(ACTOR_AS),
  'id': 'tag:bsky.app:at://did/app.bsky.feed.post/tid_liked_by_did:web:alice.com',
  'objectType': 'activity',
  'verb': 'like',
  'url': 'https://bsky.app/profile/alice.com/post/tid#liked_by_did:web:alice.com',
  'object': {'url': 'https://bsky.app/profile/alice.com/post/tid'}
}]
POST_AUTHOR_PROFILE_WITH_LIKES_AS['object']['tags'][0]['author'].update({
  'id': 'tag:bsky.app:did:web:alice.com',
  'username': 'alice.com',
  'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
})

POST_AUTHOR_PROFILE_WITH_REPOSTS_AS = copy.deepcopy(POST_AUTHOR_PROFILE_AS)
POST_AUTHOR_PROFILE_WITH_REPOSTS_AS['object']['tags'] = [{
  'author': copy.deepcopy(ACTOR_AS),
  'id': 'tag:bsky.app:at://did/app.bsky.feed.post/tid_reposted_by_did:web:alice.com',
  'objectType': 'activity',
  'verb': 'share',
  'url': 'https://bsky.app/profile/alice.com/post/tid#reposted_by_did:web:alice.com',
  'object': {'url': 'https://bsky.app/profile/alice.com/post/tid'}
}]
POST_AUTHOR_PROFILE_WITH_REPOSTS_AS['object']['tags'][0]['author'].update({
  'id': 'tag:bsky.app:did:web:alice.com',
  'username': 'alice.com',
  'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
})

class BlueskyTest(testutil.TestCase):

  def setUp(self):
    self.bs = Bluesky(handle='handull', did='did:dyd', access_token='towkin')
    util.now = lambda **kwargs: testutil.NOW

  def assert_equals(self, expected, actual, ignore=(), **kwargs):
    ignore = list(ignore) + ['uri']
    return super().assert_equals(expected, actual, ignore=ignore, in_order=True,
                                 **kwargs)

  def assert_call(self, mock, method, json=None):
    mock.assert_any_call(f'https://bsky.social/xrpc/{method}', data=None,
                         json=json, headers={
                           'Authorization': 'Bearer towkin',
                           'Content-Type': 'application/json',
                           'User-Agent': util.user_agent,
                         })

  def test_at_uri_pattern(self):
    for input, expected in [
        ('', False),
        ('foo', False),
        ('http://bar', False),
        ('at://', False),
        ('at:////', False),
        ('at://x/y/z', True),
        ('at://x / y/z', False),
        (' at://x/y/z ', False),
        ('at://did:plc:foo/a.b/123', True),
    ]:
      with self.subTest(input=input):
        self.assertEqual(expected, AT_URI_PATTERN.match(input) is not None)

  def test_url_to_did_web(self):
    for bad in None, '', 'foo', 'did:web:bar.com':
      with self.assertRaises(ValueError):
        url_to_did_web(bad)

    self.assertEqual('did:web:foo.com', url_to_did_web('https://foo.com'))
    self.assertEqual('did:web:foo.com', url_to_did_web('https://foo.com/'))
    self.assertEqual('did:web:foo.com', url_to_did_web('https://foo.com:3000'))
    self.assertEqual('did:web:foo.bar.com', url_to_did_web('https://foo.bar.com/baz/baj'))

  def test_did_web_to_url(self):
    for bad in None, '', 'foo' 'https://bar.com', 'did:web:foo.com:path':
      with self.assertRaises(ValueError):
        did_web_to_url(bad)

    self.assertEqual('https://foo.com/', did_web_to_url('did:web:foo.com'))
    self.assertEqual('https://foo.bar.com/', did_web_to_url('did:web:foo.bar.com'))

  def test_user_url(self):
    self.assertEqual('https://bsky.app/profile/snarfed.org',
                     Bluesky.user_url('snarfed.org'))

    self.assertEqual('https://bsky.app/profile/snarfed.org',
                     Bluesky.user_url('@snarfed.org'))

  def test_user_to_actor(self):
    self.assert_equals({
      'objectType': 'person',
      'displayName': 'Alice',
      'summary': 'hi there',
    }, Bluesky.user_to_actor(ACTOR_PROFILE_BSKY))

  def test_post_url(self):
    self.assertEqual('https://bsky.app/profile/snarfed.org/post/3jv3wdw2hkt25',
                     Bluesky.post_url('snarfed.org', '3jv3wdw2hkt25'))

  def test_at_uri_to_web_url(self):
    self.assertEqual(None, at_uri_to_web_url(''))

    at_uri = 'at://did:plc:asdf/app.bsky.feed.post/3jv3wdw2hkt25'
    self.assertEqual(
      'https://bsky.app/profile/did:plc:asdf/post/3jv3wdw2hkt25',
      at_uri_to_web_url(at_uri))
    self.assertEqual(
      'https://bsky.app/profile/snarfed.org/post/3jv3wdw2hkt25',
      at_uri_to_web_url(at_uri, handle='snarfed.org'))

    at_uri_profile = 'at://did:plc:asdf'
    self.assertEqual(
      'https://bsky.app/profile/did:plc:asdf',
      at_uri_to_web_url(at_uri_profile))
    self.assertEqual(
      'https://bsky.app/profile/snarfed.org',
      at_uri_to_web_url(at_uri_profile, handle='snarfed.org'))

    self.assertEqual(
      'https://bsky.app/profile/did:plc:asdf/lists/123',
      at_uri_to_web_url('at://did:plc:asdf/app.bsky.graph.list/123'))

    with self.assertRaises(ValueError):
      at_uri_to_web_url('http://not/at/uri')

  def test_web_url_to_at_uri(self):
    for url, expected in (
        ('', None),
        ('https://bsky.app/profile/foo.com', 'at://foo.com'),
        ('https://bsky.app/profile/did:plc:foo', 'at://did:plc:foo'),
        ('https://bsky.app/profile/did:plc:foo/post/3jv3wdw2hkt25',
         'at://did:plc:foo/app.bsky.feed.post/3jv3wdw2hkt25'),
        ('https://bsky.app/profile/bsky.app/feed/mutuals',
         'at://bsky.app/app.bsky.feed.generator/mutuals'),
    ):
      self.assertEqual(expected, web_url_to_at_uri(url))

      self.assertEqual(
        'at://did:plc:foo',
        web_url_to_at_uri('https://bsky.app/profile/foo.com', handle='foo.com', did='did:plc:foo')
      )

      self.assertEqual(
        'at://foo.com',
        web_url_to_at_uri('https://bsky.app/profile/foo.com', did='did:plc:foo')
      )

      self.assertEqual(
        'at://foo.com',
        web_url_to_at_uri('https://bsky.app/profile/foo.com', handle='foo.com')
      )

      self.assertEqual(
        'at://foo.com',
        web_url_to_at_uri('https://bsky.app/profile/foo.com', handle='alice.com', did='did:plc:foo')
      )

    for url in ('at://foo', 'http://not/bsky.app', 'https://bsky.app/x'):
      with self.assertRaises(ValueError):
        web_url_to_at_uri(url)

  def test_from_as1_unsupported_out_type(self):
    with self.assertRaises(ValueError):
      from_as1({'objectType': 'image'}, out_type='foo')  # no matching objectType

    with self.assertRaises(ValueError):
      from_as1({'objectType': 'person'}, out_type='foo')  # mismatched out_type

  def test_from_as1_post(self):
    self.assert_equals(POST_BSKY, from_as1(POST_AS), ignore=['uri'])

  def test_from_as1_post_out_type_postView(self):
    got = from_as1(POST_AS, out_type='app.bsky.feed.defs#postView')
    self.assert_equals(POST_VIEW_BSKY, got, ignore=['uri'])

  def test_from_as1_post_out_type_feedViewPost(self):
    got = from_as1(POST_AUTHOR_AS, out_type='app.bsky.feed.defs#feedViewPost')
    self.assert_equals(POST_FEED_VIEW_BSKY, got, ignore=['uri'])

  def test_from_as1_post_with_author(self):
    expected = copy.deepcopy(POST_AUTHOR_BSKY)
    got = from_as1(POST_AUTHOR_AS, out_type='app.bsky.feed.defs#postView')
    self.assert_equals(expected, got)

  def test_from_as1_post_html_skips_tag_indices(self):
    post_as = copy.deepcopy(POST_AS)
    post_as['object'].update({
      'content': '<em>some html</em>',
      'content_is_html': True,
      # not set because content is HTML
      # 'tags': [FACET_TAG],
    })

    # with self.assertRaises(NotImplementedError):
    self.assert_equals({
      '$type': 'app.bsky.feed.post',
      'text': '_some html_',
      'createdAt': '2007-07-07T03:04:05',
    },from_as1(post_as))

  def test_from_as1_post_without_tag_indices(self):
    post_as = copy.deepcopy(POST_AS)
    post_as['object']['tags'] = [{
      'url': 'http://my/link',
    }]

    expected = {
      **POST_BSKY,
      'facets': copy.deepcopy(FACETS)
    }
    del expected['facets'][0]['index']

    self.assert_equals(expected, from_as1(post_as))

  def test_from_as1_tag_without_url(self):
    self.assert_equals({
      '$type': 'app.bsky.feed.post',
      'text': 'foo',
      'createdAt': '2022-01-02T03:04:05+00:00',
    }, from_as1({
      'objectType': 'note',
      'content': 'foo',
      'tags': [{
        'objectType': 'mention',
      }],
    }))

  def test_from_as1_tag_did_mention(self):
    self.assert_equals({
      '$type': 'app.bsky.feed.post',
      'text': 'foo',
      'createdAt': '2022-01-02T03:04:05+00:00',
      'facets': [{
        '$type': 'app.bsky.richtext.facet',
        'features': [{
          '$type': 'app.bsky.richtext.facet#mention',
          'did': 'did:plc:foo',
        }],
      }],
    }, from_as1({
      'objectType': 'note',
      'content': 'foo',
      'tags': [{
        'objectType': 'mention',
        'url': 'did:plc:foo',
      }],
    }))

  def test_from_as1_post_with_image(self):
    expected = copy.deepcopy(POST_BSKY_IMAGES)
    del expected['embed']['images'][0]['image']
    self.assert_equals(expected, from_as1(POST_AS_IMAGES))

  def test_from_as1_post_with_image_blobs(self):
    expected = copy.deepcopy(POST_BSKY_IMAGES)
    expected['embed']['images'][0]['image'] = BLOB
    self.assert_equals(expected, from_as1(POST_AS_IMAGES, blobs={NEW_BLOB_URL: BLOB}))

  def test_from_as1_post_view_with_image(self):
    expected = copy.deepcopy(POST_VIEW_BSKY_IMAGES)
    del expected['record']['embed']['images'][0]['image']
    got = from_as1(POST_AS_IMAGES, out_type='app.bsky.feed.defs#postView')
    self.assert_equals(expected, got)

  def test_from_as1_post_content_html(self):
    self.assertEqual({
      '$type': 'app.bsky.feed.post',
      'text': 'Some\n_HTML_',
      'createdAt': '2022-01-02T03:04:05+00:00',
    }, from_as1({
      'objectType': 'note',
      'content': '<p>Some <br> <em>HTML</em></p>',
    }))

  def test_from_as1_object_vs_activity(self):
    obj = {
      'objectType': 'note',
      'content': 'foo',
    }
    activity = {
      'verb': 'post',
      'object': obj,
    }
    self.assert_equals(from_as1(obj), from_as1(activity))

  def test_from_as1_actor(self):
    expected = {
      '$type': 'app.bsky.actor.profile',
      'displayName': 'Alice',
      'description': 'hi there',
    }
    self.assert_equals(expected, from_as1(ACTOR_AS))
    self.assert_equals(expected, from_as1(ACTOR_AS, out_type='app.bsky.actor.profile'))

  def test_from_as1_actor_blobs(self):
    self.assert_equals({
      '$type': 'app.bsky.actor.profile',
      'displayName': 'Alice',
      'description': 'hi there',
      'avatar': BLOB,
    }, from_as1(ACTOR_AS, blobs={'https://alice.com/alice.jpg': BLOB}))

  def test_from_as1_actor_profileView(self):
    for type in ('app.bsky.actor.defs#profileView',
                 'app.bsky.actor.defs#profileViewBasic',
                 'app.bsky.actor.defs#profileViewDetailed',
                 ):
      self.assert_equals({
        **ACTOR_PROFILE_VIEW_BSKY,
        '$type': type,
      }, from_as1(ACTOR_AS, out_type=type))

  def test_from_as1_actor_handle(self):
    for expected, fields in (
        ('', {}),
        ('fooey.bsky.social', {'username': 'fooey.bsky.social'}),
        ('fooey.com', {'username': 'fooey.com', 'url': 'http://my/url', 'id': 'tag:nope'}),
        ('foo.com', {'url': 'http://foo.com'}),
        ('foo.com', {'url': 'http://foo.com/path'}),
    ):
      self.assert_equals(expected, from_as1({
        'objectType': 'person',
        **fields,
      }, out_type='app.bsky.actor.defs#profileView')['handle'])

  def test_from_as1_actor_id_not_url(self):
    """Tests error handling when attempting to generate did:web."""
    self.assertEqual('did:web:foo.com', from_as1({
      'objectType': 'person',
      'id': 'tag:foo.com,2001:bar',
    }, out_type='app.bsky.actor.defs#profileView')['did'])

  def test_from_as1_actor_description_html(self):
    self.assertEqual({
      '$type': 'app.bsky.actor.profile',
      'description': 'Some\n_HTML_',
    }, from_as1({
      'objectType': 'person',
      'summary': '<p>Some <br> <em>HTML</em></p>',
    }))

  def test_from_as1_composite_url(self):
    self.assertEqual({
      '$type': 'app.bsky.actor.defs#profileView',
      'did': 'did:web:rodentdisco.co.uk',
      'handle': 'rodentdisco.co.uk',
    }, from_as1({
      'objectType': 'person',
      'url': {
        "displayName": "my web site",
        "value": "https://rodentdisco.co.uk/author/dan/"
      },
    }, out_type='app.bsky.actor.defs#profileView'))

  def test_from_as1_embed(self):
    self.assert_equals(POST_BSKY_EMBED, from_as1(POST_AS_EMBED))

  def test_from_as1_embed_out_type_postView(self):
    got = from_as1(POST_AS_EMBED, out_type='app.bsky.feed.defs#postView')
    self.assert_equals(POST_VIEW_BSKY_EMBED, got)

  def test_from_as1_facet_link_and_embed(self):
    expected = copy.deepcopy(POST_BSKY_EMBED)
    expected['facets'] = FACETS

    self.assert_equals(expected, from_as1({
      **POST_AS_EMBED,
      'tags': [FACET_TAG],
    }))

  def test_from_as1_repost(self):
    self.assert_equals(REPOST_BSKY, from_as1(REPOST_AS))

  def test_from_as1_repost_reasonRepost(self):
    got = from_as1(REPOST_AS, out_type='app.bsky.feed.defs#reasonRepost')
    self.assert_equals(REPOST_BSKY_REASON, got)

  def test_from_as1_repost_feedViewPost(self):
    got = from_as1(REPOST_AS, out_type='app.bsky.feed.defs#feedViewPost')
    self.assert_equals(REPOST_BSKY_FEED_VIEW_POST, got)

  def test_from_as1_reply(self):
    self.assert_equals(REPLY_BSKY, from_as1(REPLY_AS))
    self.assert_equals(REPLY_BSKY, from_as1(REPLY_AS['object']))

  def test_from_as1_reply_postView(self):
    for input in REPLY_AS, REPLY_AS['object']:
      got = from_as1(input, out_type='app.bsky.feed.defs#postView')
      self.assert_equals(REPLY_POST_VIEW_BSKY, got)

  def test_from_as1_follow_no_object(self):
    with self.assertRaises(ValueError):
      from_as1({
        'objectType': 'activity',
        'verb': 'follow',
        'actor': 'at://did:plc:foo/com.atproto.actor.profile/123',
      })

  def test_from_as1_image_string_id(self):
    self.assert_equals({
      '$type': 'app.bsky.feed.post',
      'text': '',
      'createdAt': '2022-01-02T03:04:05+00:00',
      'embed': {
        '$type': 'app.bsky.embed.images',
        'images': [{
          '$type': 'app.bsky.embed.images#image',
          'alt': '',
        }],
      }
    }, from_as1({
      'objectType': 'note',
      'image': ['http://foo'],
    }))

  def test_to_as1_profile(self):
    self.assert_equals({
      'objectType': 'person',
      'id': 'did:plc:foo',
      'username': 'han.dull',
      'displayName': 'Alice',
      'summary': 'hi there',
      'image': [{
        'url': NEW_BLOB_URL,
      }, {
        'objectType': 'featured',
        'url': OLD_BLOB_URL,
      }],
      'url': ['https://bsky.app/profile/han.dull', 'https://han.dull/'],
    }, to_as1(ACTOR_PROFILE_BSKY, repo_did='did:plc:foo', repo_handle='han.dull'))

  def test_to_as1_profile_bsky_social_handle_is_not_url(self):
    self.assert_equals({
      'objectType': 'person',
      'username': 'alice.bsky.social',
      'url': ['https://bsky.app/profile/alice.bsky.social'],
    }, to_as1({'$type': 'app.bsky.actor.profile'}, repo_handle='alice.bsky.social'))

  def test_to_as1_profile_view(self):
    self.assert_equals({
      **ACTOR_AS,
      'username': 'alice.com',
      'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
      }, to_as1(ACTOR_PROFILE_VIEW_BSKY))

  def test_to_as1_profile_no_repo_did_handle_or_pds(self):
    self.assert_equals({
      'objectType': 'person',
      'displayName': 'Alice',
      'summary': 'hi there',
    }, to_as1(ACTOR_PROFILE_BSKY, repo_did=None, pds='http://foo'))
    self.assert_equals({
      'objectType': 'person',
      'id': 'did:plc:foo',
      'displayName': 'Alice',
      'summary': 'hi there',
    }, to_as1(ACTOR_PROFILE_BSKY, repo_did='did:plc:foo', pds=None))

  def test_to_as1_post(self):
    self.assert_equals({
      'objectType': 'note',
      'content': 'My original post',
      'published': '2007-07-07T03:04:05',
    }, to_as1(POST_BSKY))

  def test_to_as1_post_uri(self):
    self.assert_equals({
      'id': 'at://alice.com/app.bsky.feed.post/123',
      'url': 'https://bsky.app/profile/alice.com/post/123',
      'objectType': 'note',
      'content': 'My original post',
      'published': '2007-07-07T03:04:05',
    }, to_as1(POST_BSKY, uri='at://alice.com/app.bsky.feed.post/123'))

  def test_to_as1_post_view(self):
    self.assert_equals(POST_AS['object'], to_as1(POST_VIEW_BSKY))

  def test_from_as1_feed_view_post(self):
    self.assert_equals(POST_AUTHOR_PROFILE_AS['object'], to_as1(POST_FEED_VIEW_BSKY))

  def test_to_as1_post_with_author(self):
    self.assert_equals(POST_AUTHOR_PROFILE_AS['object'], to_as1(POST_AUTHOR_BSKY))

  def test_to_as1_post_type_kwarg(self):
    post_bsky = copy.deepcopy(POST_AUTHOR_BSKY)
    type = post_bsky.pop('$type')
    del post_bsky['author']['$type']
    self.assert_equals(POST_AUTHOR_PROFILE_AS['object'], to_as1(post_bsky, type=type))

  def test_to_as1_post_with_image_no_repo_did(self):
    self.assert_equals(trim_nulls({
      **POST_AS_IMAGES['object'],
      'id': None,
      'image': None,
      'url': None,
    }), to_as1(POST_BSKY_IMAGES))

  def test_to_as1_post_with_image_repo_did(self):
    self.assert_equals(trim_nulls({
      **POST_AS_IMAGES['object'],
      'id': None,
      'url': None,
      'author': 'did:plc:foo',
    }), to_as1(POST_BSKY_IMAGES, repo_did='did:plc:foo'))

  def test_to_as1_post_view_with_image(self):
    self.assert_equals(POST_AS_IMAGES['object'], to_as1(POST_VIEW_BSKY_IMAGES))

  def test_to_as1_reply(self):
    self.assert_equals(trim_nulls({
      **REPLY_AS['object'],
      'id': None,
      'url': None,
    }), to_as1(REPLY_BSKY))

  def test_to_as1_reply_postView(self):
    self.assert_equals(REPLY_AS['object'], to_as1(REPLY_POST_VIEW_BSKY))

  def test_to_as1_repost(self):
    self.assert_equals({
      'objectType': 'activity',
      'verb': 'share',
      'object': 'at://did/app.bsky.feed.post/tid',
      'published': '2022-01-02T03:04:05+00:00',
    }, to_as1(REPOST_BSKY))

  def test_to_as1_repost_uri(self):
    self.assert_equals({
      'objectType': 'activity',
      'verb': 'share',
      'id': 'at://alice.com/app.bsky.feed.repost/123',
      'url': 'https://bsky.app/profile/did/post/tid#reposted_by_alice.com',
      'object': 'at://did/app.bsky.feed.post/tid',
      'published': '2022-01-02T03:04:05+00:00',
    }, to_as1(REPOST_BSKY, uri='at://alice.com/app.bsky.feed.repost/123'))

  def test_to_as1_like_uri(self):
    self.assert_equals({
      'objectType': 'activity',
      'verb': 'like',
      'id': 'at://alice.com/app.bsky.feed.like/123',
      'url': 'https://bsky.app/profile/did/post/tid#liked_by_alice.com',
      'object': 'at://did/app.bsky.feed.post/tid',
    }, to_as1(LIKE_BSKY, uri='at://alice.com/app.bsky.feed.like/123'))

  def test_to_as1_listView(self):
    self.assert_equals({
      'objectType': 'service',
      'displayName': 'Mai Lyst',
      'id': 'at://did:alice/app.bsky.graph.list/987',
      'url': 'https://bsky.app/profile/did:alice/lists/987',
      'summary': 'a lyst',
      'image': 'https://cdn.bsky.app/lyst@jpeg',
      'author': {
        'objectType': 'person',
        'id': 'did:alice',
        'url': ['https://bsky.app/profile/alice.com', 'https://alice.com/'],
        'username': 'alice.com',
        'image': [{'url': 'https://cdn.bsky.app/alice@jpeg'}]
      }
    }, to_as1({
      '$type': 'app.bsky.graph.defs#listView',
      'avatar': 'https://cdn.bsky.app/lyst@jpeg',
      'cid': 'TODO',
      'creator': {
        'avatar': 'https://cdn.bsky.app/alice@jpeg',
        'did': 'did:alice',
        'name': 'Alice',
        'handle': 'alice.com',
      },
      'description': 'a lyst',
      'indexedAt': '2023-11-06T21:08:33.376Z',
      'name': 'Mai Lyst',
      'purpose': 'app.bsky.graph.defs#curatelist',
      'uri': 'at://did:alice/app.bsky.graph.list/987',
    }))

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

  def test_to_as1_embed(self):
    self.assert_equals(trim_nulls({
      **POST_AS_EMBED,
      'id': None,
      'url': None,
    }), to_as1(POST_BSKY_EMBED))

  def test_to_as1_embed_post_view(self):
    self.assert_equals(POST_AS_EMBED, to_as1(POST_VIEW_BSKY_EMBED))

  def test_to_as1_embed_block(self):
    self.assertIsNone(to_as1({
      '$type': 'app.bsky.embed.record#viewBlocked',
      'uri': 'unused',
    }))

  def test_to_as1_facet_link_and_embed(self):
    bsky = copy.deepcopy(POST_BSKY_EMBED)
    bsky['facets'] = FACETS

    self.assert_equals(trim_nulls({
      **POST_AS_EMBED,
      'id': None,
      'url': None,
      'tags': [FACET_TAG],
    }), to_as1(bsky))

  def test_blob_to_url(self):
    self.assertIsNone(blob_to_url(blob={'foo': 'bar'}, repo_did='x', pds='y'))
    self.assertEqual(NEW_BLOB_URL, blob_to_url(blob=NEW_BLOB,
                                               repo_did='did:plc:foo'))
    self.assertEqual(OLD_BLOB_URL, blob_to_url(blob=OLD_BLOB,
                                               repo_did='did:plc:foo'))

  def test_constructor_access_token(self):
    bs = Bluesky('handull', access_token='towkin')
    self.assertEqual({
      'accessJwt': 'towkin',
      'refreshJwt': None,
    }, bs.client.session)

  @patch('requests.post')
  def test_constructor_app_password(self, mock_post):
    session = {
      'handle': 'real.han.dull',
      'did': 'did:plc:me',
      'accessJwt': 'towkin',
      'refreshJwt': 'reephrush',
    }
    mock_post.return_value = requests_response(session)

    bs = Bluesky('handull', app_password='pazzwurd')
    bs.client  # trigger login
    self.assertEqual('real.han.dull', bs.handle)
    self.assertEqual('did:plc:me', bs.did)
    self.assertEqual(session, bs.client.session)

    mock_post.assert_called_once_with(
      'https://bsky.social/xrpc/com.atproto.server.createSession',
      json={'identifier': 'handull', 'password': 'pazzwurd'},
      data=None,
      headers={
        'Content-Type': 'application/json',
        'User-Agent': util.user_agent,
      },
    )

  @patch('requests.get')
  def test_get_activities_friends(self, mock_get):
    mock_get.return_value = requests_response({
      'cursor': 'timestamp::cid',
      'feed': [POST_FEED_VIEW_BSKY, REPOST_BSKY_FEED_VIEW_POST],
    })

    expected_repost = copy.deepcopy(REPOST_AS)
    expected_repost['actor']['username'] = 'bob.com'
    self.assert_equals([POST_AUTHOR_PROFILE_AS, expected_repost],
                       self.bs.get_activities(group_id=FRIENDS))

    self.assert_call(mock_get, 'app.bsky.feed.getTimeline')

  @patch('requests.get')
  def test_get_activities_activity_id(self, mock_get):
    mock_get.return_value = requests_response({
      'thread': THREAD_BSKY,
    })

    self.assert_equals([POST_AUTHOR_PROFILE_AS],
                       self.bs.get_activities(activity_id='at://id'))
    self.assert_call(mock_get, 'app.bsky.feed.getPostThread?uri=at%3A%2F%2Fid&depth=1')

  def test_get_activities_bad_activity_id(self):
    with self.assertRaises(ValueError):
      self.bs.get_activities(activity_id='not_at_uri')

  @patch('requests.get')
  def test_get_activities_self_user_id(self, mock_get):
    mock_get.return_value = requests_response({
      'cursor': 'timestamp::cid',
      'feed': [POST_AUTHOR_BSKY],
    })

    self.assert_equals([POST_AUTHOR_PROFILE_AS],
                       self.bs.get_activities(group_id=SELF, user_id='alice.com'))
    self.assert_call(mock_get, 'app.bsky.feed.getAuthorFeed?actor=alice.com')

  @patch('requests.get')
  def test_get_activities_prefers_did(self, mock_get):
    mock_get.return_value = requests_response({
      'feed': [],
    })

    self.bs.did = 'did:alice'
    self.assert_equals([], self.bs.get_activities(group_id=SELF))
    self.assert_call(mock_get, 'app.bsky.feed.getAuthorFeed?actor=did%3Aalice')

  @patch('requests.get')
  def test_get_activities_with_likes(self, mock_get):
    mock_get.side_effect = [
      requests_response({
        'cursor': 'timestamp::cid',
        'feed': [POST_FEED_VIEW_WITH_LIKES_BSKY],
      }),
      requests_response({
        'cursor': 'timestamp::cid',
        'uri': 'at://did/app.bsky.feed.post/tid',
        'likes': [GET_LIKES_LIKE_BSKY]
      })
    ]

    cache = {}
    self.assert_equals(
      [POST_AUTHOR_PROFILE_WITH_LIKES_AS],
      self.bs.get_activities(fetch_likes=True, cache=cache)
    )
    self.assert_call(mock_get, 'app.bsky.feed.getTimeline')
    self.assert_call(mock_get,
        'app.bsky.feed.getLikes?uri=at%3A%2F%2Fdid%2Fapp.bsky.feed.post%2Ftid')
    self.assert_equals(1, cache.get('ABL at://did/app.bsky.feed.post/tid'))

  @patch('requests.get')
  def test_get_activities_with_reposts(self, mock_get):
    mock_get.side_effect = [
      requests_response({
        'cursor': 'timestamp::cid',
        'feed': [POST_FEED_VIEW_WITH_REPOSTS_BSKY],
      }),
      requests_response({
        'cursor': 'timestamp::cid',
        'uri': 'at://did/app.bsky.feed.post/tid',
        'repostedBy': [ACTOR_PROFILE_VIEW_BSKY]
      })
    ]

    cache = {}
    self.assert_equals(
      [POST_AUTHOR_PROFILE_WITH_REPOSTS_AS],
      self.bs.get_activities(fetch_shares=True, cache=cache)
    )
    self.assert_call(mock_get, 'app.bsky.feed.getTimeline')
    self.assert_call(mock_get,
        'app.bsky.feed.getRepostedBy?uri=at%3A%2F%2Fdid%2Fapp.bsky.feed.post%2Ftid')
    self.assert_equals(1, cache.get('ABRP at://did/app.bsky.feed.post/tid'))

  @patch('requests.get')
  def test_get_activities_include_shares(self, mock_get):
    mock_get.return_value = requests_response({
      'cursor': 'timestamp::cid',
      'feed': [POST_FEED_VIEW_BSKY, REPOST_BSKY_FEED_VIEW_POST],
    })

    self.assert_equals(
      [POST_AUTHOR_PROFILE_AS, REPOST_PROFILE_AS],
      self.bs.get_activities(include_shares=True)
    )

  @patch('requests.get')
  def test_get_activities_with_replies(self, mock_get):
    mock_get.side_effect = [
      requests_response({
        'cursor': 'timestamp::cid',
        'feed': [POST_FEED_VIEW_WITH_REPLIES_BSKY],
      }),
      requests_response({
        'thread': THREAD_BSKY,
      })
    ]

    cache = {}
    self.assert_equals([THREAD_AS],
                       self.bs.get_activities(fetch_replies=True, cache=cache))
    self.assert_call(mock_get,'app.bsky.feed.getTimeline')
    self.assert_call(mock_get,
        'app.bsky.feed.getPostThread?uri=at%3A%2F%2Fdid%2Fapp.bsky.feed.post%2Ftid')
    self.assert_equals(1, cache.get('ABR at://did/app.bsky.feed.post/tid'))

  @patch('requests.get')
  def test_get_actor(self, mock_get):
    mock_get.return_value = requests_response({
      **ACTOR_PROFILE_VIEW_BSKY,
      '$type': 'app.bsky.actor.defs#profileViewDetailed',
    })

    self.assert_equals(ACTOR_AS, self.bs.get_actor(user_id='me.com'))
    self.assert_call(mock_get, 'app.bsky.actor.getProfile?actor=me.com')

  @patch('requests.get')
  def test_get_actor_default(self, mock_get):
    mock_get.return_value = requests_response({
      **ACTOR_PROFILE_VIEW_BSKY,
      '$type': 'app.bsky.actor.defs#profileViewDetailed',
    })

    self.assert_equals(ACTOR_AS, self.bs.get_actor())
    self.assert_call(mock_get, 'app.bsky.actor.getProfile?actor=handull')

  @patch('requests.get')
  def test_get_comment(self, mock_get):
    mock_get.return_value = requests_response({
      'thread': THREAD_BSKY,
    })

    self.assert_equals(POST_AUTHOR_PROFILE_AS['object'],
                       self.bs.get_comment(comment_id='at://id'))
    self.assert_call(mock_get, 'app.bsky.feed.getPostThread?uri=at%3A%2F%2Fid&depth=1')

  def test_post_id(self):
    for input, expected in [
        (None, None),
        ('', None),
        ('abc', None),
        ('http://foo', None),
        ('https://bsky.app/profile/foo', None),
        ('at://did:plc:foo', None),
        ('at://did/post/tid', 'at://did/post/tid'),
        ('https://bsky.app/profile/did/post/tid', 'at://did/app.bsky.feed.post/tid'),
    ]:
      with self.subTest(input=input):
        self.assertEqual(expected, self.bs.post_id(input))

  def test_preview_post(self):
    self.bs.TRUNCATE_TEXT_LENGTH = 20

    for content, expected in (
        ('foo ☕ bar', 'foo ☕ bar'),
        ('too long, will be ellipsized', 'too long, will be…'),
        ('<p>foo ☕ <a>bar</a></p>', 'foo ☕ bar'),
        # TODO
        # ('#Asdf ☕ bar', '<a href="http://foo.com/tags/Asdf">#Asdf</a> ☕ bar'),
        # @-mention
        # ('foo ☕ @alice.com', 'foo ☕ <a href="http://bsky.app/profile/alice.com">@alice.com</a>'),
        # ('link asdf.com', 'link <a href="http://asdf.com">asdf.com</a>'),
      ):
      with self.subTest(content=content, expected=expected):
        obj = copy.deepcopy(POST_AS['object'])
        obj['content'] = content
        got = self.bs.preview_create(obj)
        self.assertEqual('<span class="verb">post</span>:', got.description)
        self.assertEqual(expected, got.content)

  @patch('requests.post')
  def test_create_post(self, mock_post):
    at_uri = 'at://did:me/app.bsky.feed.post/abc123'
    mock_post.return_value = requests_response({'uri': at_uri})

    self.assert_equals({
      'id': at_uri,
      'url': 'https://bsky.app/profile/handull/post/abc123',
    }, self.bs.create(POST_AS['object']).content)

    self.assert_call(mock_post, 'com.atproto.repo.createRecord', json={
      'repo': 'did:dyd',
      'collection': 'app.bsky.feed.post',
      'record': POST_BSKY,
    })

  @patch('requests.post')
  def test_create_reply(self, mock_post):
    at_uri = 'at://did:me/app.bsky.feed.post/abc123'
    mock_post.return_value = requests_response({'uri': at_uri})

    self.assert_equals({
      'id': at_uri,
      'url': 'https://bsky.app/profile/handull/post/abc123',
    }, self.bs.create(REPLY_AS['object']).content)

    self.assert_call(mock_post, 'com.atproto.repo.createRecord', json={
      'repo': 'did:dyd',
      'collection': 'app.bsky.feed.post',
      'record': REPLY_BSKY,
    })

  def test_preview_reply(self):
    preview = self.bs.preview_create(REPLY_AS['object'])
    self.assertIn('<span class="verb">reply</span> to <a href="https://bsky.app/profile/did/post/parent-tid">this post</a>:', preview.description)
    self.assert_equals('I hereby reply to this', preview.content)

  @patch('requests.post')
  def test_create_reply_remote(self, mock_post):
    url = STATUS_REMOTE['url']
    self.expect_get(API_SEARCH, params={'q': url, 'resolve': True},
                    response={'statuses': [STATUS_REMOTE]})
    self.expect_post(API_STATUSES, json={
      'status': 'foo ☕ bar',
      'in_reply_to_id': STATUS_REMOTE['id'],
    }, response=POST)
    self.mox.ReplayAll()

    got = self.bs.create({
      'content': 'foo ☕ bar',
      'inReplyTo': [{'url': url}],
    })
    self.assert_equals(POST, got.content, got)

  def test_preview_reply_remote(self):
    url = STATUS_REMOTE['url']
    self.expect_get(API_SEARCH, params={'q': url, 'resolve': True},
                    response={'statuses': [STATUS_REMOTE]})
    self.mox.ReplayAll()

    preview = self.bs.preview_create({
      'content': 'foo ☕ bar',
      'inReplyTo': [{'url': url}],
    })
    self.assertIn(
      f'<span class="verb">reply</span> to <a href="{url}">this post</a>: ',
      preview.description)
    self.assert_equals('foo ☕ bar', preview.content)

  @patch('requests.post')
  def test_create_non_atproto_reply(self, mock_post):
    self.expect_get(API_SEARCH, params={'q': 'http://not/atproto', 'resolve': True},
                    response={})
    self.expect_post(API_STATUSES, json={'status': 'foo ☕ bar'}, response=POST)
    self.mox.ReplayAll()

    got = self.bs.create({
      'content': 'foo ☕ bar',
      'inReplyTo': [{'url': 'http://not/atproto'}],
    })
    self.assert_equals(POST, got.content, got)

  @patch('requests.post')
  def test_create_like(self):
    self.expect_post(API_LIKE % '123', POST)
    self.mox.ReplayAll()

    got = self.bs.create(LIKE).content
    self.assert_equals('like', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123#liked-by-23507', got['url'])

  def test_preview_like(self):
    obj = copy.deepcopy(LIKE)
    preview = self.bs.preview_create(obj)
    self.assertIn('<span class="verb">like</span> <a href="http://foo.com/@snarfed/123">this post</a>: ', preview.description)

  @patch('requests.post')
  def test_create_like_remote(self, mock_post):
    url = STATUS_REMOTE['url']
    self.expect_get(API_SEARCH, params={'q': url, 'resolve': True},
                    response={'statuses': [STATUS_REMOTE]})
    self.expect_post(API_LIKE % '999', STATUS_REMOTE)
    self.mox.ReplayAll()

    got = self.bs.create(LIKE_REMOTE).content
    self.assert_equals('like', got['type'])
    self.assert_equals(url + '#liked-by-23507', got['url'])

  def test_preview_like_remote(self):
    url = STATUS_REMOTE['url']
    self.expect_get(API_SEARCH, params={'q': url, 'resolve': True},
                    response={'statuses': [STATUS_REMOTE]})
    self.mox.ReplayAll()

    preview = self.bs.preview_create(LIKE_REMOTE)
    self.assertIn(
      f'<span class="verb">like</span> <a href="{url}">this post</a>: ',
      preview.description)

  @patch('requests.post')
  def test_create_repost(self, mock_post):
    self.expect_post(API_REPOST % '123', POST)
    self.mox.ReplayAll()

    got = self.bs.create(SHARE_ACTIVITY).content
    self.assert_equals('repost', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123', got['url'])

  def test_preview_repost(self):
    preview = self.bs.preview_create(SHARE_ACTIVITY)
    self.assertIn('<span class="verb">boost</span> <a href="http://foo.com/@snarfed/123">this post</a>: ', preview.description)

  @patch('requests.post')
  def test_create_repost_remote(self, mock_post):
    url = STATUS_REMOTE['url']
    self.expect_get(API_SEARCH, params={'q': url, 'resolve': True},
                    response={'statuses': [STATUS_REMOTE]})
    self.expect_post(API_REPOST % '999', POST)
    self.mox.ReplayAll()

    got = self.bs.create(SHARE_REMOTE).content
    self.assert_equals('repost', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123', got['url'])

  def test_preview_repost_remote(self):
    url = STATUS_REMOTE['url']
    self.expect_get(API_SEARCH, params={'q': url, 'resolve': True},
                    response={'statuses': [STATUS_REMOTE]})
    self.mox.ReplayAll()

    preview = self.bs.preview_create(SHARE_REMOTE)
    self.assertIn(
      f'<span class="verb">boost</span> <a href="{url}">this post</a>: ',
      preview.description)

  def test_preview_with_media(self):
    preview = self.bs.preview_create(MEDIA_OBJECT)
    self.assertEqual('<span class="verb">post</span>:', preview.description)
    self.assertEqual('foo ☕ bar<br /><br /><video controls src="http://foo.com/video.mp4"><a href="http://foo.com/video.mp4">a fun video</a></video> &nbsp; <img src="http://foo.com/image.jpg" alt="a fun image" />',
                     preview.content)

  def test_preview_create_override_truncate_text_length(self):
    bs = Bluesky(INSTANCE, access_token='towkin',
                 user_id=ACCOUNT['id'], truncate_text_length=8)
    got = m.preview_create(OBJECT)
    self.assertEqual('foo ☕…', got.content)

    self.expect_post(API_STATUSES, json={'status': 'foo ☕…'}, response=POST)
    self.mox.ReplayAll()

    result = bs.create(OBJECT)
    self.assert_equals(POST, result.content, result)

  @patch('requests.post')
  def test_create_with_media(self, mock_post):
    self.expect_requests_get('http://foo.com/image.jpg', 'pic 1')
    self.expect_post(API_MEDIA, {'id': 'b'}, files={'file': b'pic 1'}, data={})
    self.expect_post(API_STATUSES, json={
      'status': 'foo ☕ bar',
      'media_ids': ['a', 'b'],
    }, response=POST)
    self.mox.ReplayAll()

    obj = copy.deepcopy(MEDIA_OBJECT)
    del obj['image']['displayName']
    result = self.bs.create(obj)
    self.assert_equals(POST, result.content, result)

  @patch('requests.post')
  def test_create_with_too_many_media(self, mock_post):
    image_urls = [f'http://my/picture/{i}' for i in range(MAX_IMAGES + 1)]
    obj = {
      'objectType': 'note',
      'image': [{'url': url} for url in image_urls],
      # duplicate images to check that they're de-duped
      'attachments': [{'objectType': 'image', 'url': url} for url in image_urls],
    }

    # test preview
    preview = self.bs.preview_create(obj)
    self.assertEqual('<span class="verb">post</span>:', preview.description)
    self.assertEqual("""\
<br /><br />\
&nbsp; <img src="http://my/picture/0" alt="" /> \
&nbsp; <img src="http://my/picture/1" alt="" /> \
&nbsp; <img src="http://my/picture/2" alt="" />""",
                     preview.content)

    # test create
    for i, url in enumerate(image_urls[:-1]):
      self.expect_requests_get(f'http://my/picture/{i}', 'pic')
      self.expect_post(API_MEDIA, {'id': str(i + 1)}, files={'file': b'pic'}, data={})

    self.expect_post(API_STATUSES, json={
      'status': '',
      'media_ids': ['0', '1', '2', '3'],
    }, response=POST)
    self.mox.ReplayAll()
    result = self.bs.create(obj)
    self.assert_equals(POST, result.content, result)

  def test_delete(self):
    self.expect_delete(API_STATUS % '456')
    self.mox.ReplayAll()

    result = self.bs.delete(456)
    self.assert_equals({'url': 'http://foo.com/web/statuses/456'},
                       result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)

  def test_preview_delete(self):
    got = self.bs.preview_delete('456')
    self.assertIn('<span class="verb">delete</span> <a href="http://foo.com/web/statuses/456">this post</a>.', got.description)
    self.assertIsNone(got.error_plain)
    self.assertIsNone(got.error_html)
