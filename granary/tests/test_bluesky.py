"""Unit tests for jsonfeed.py.

Most tests are via files in testdata/.
"""
import copy

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil.testutil import NOW, requests_response

from ..bluesky import (
  actor_to_ref,
  did_web_to_url,
  from_as1,
  to_as1,
  url_to_did_web,
)

ACTOR_AS = {
  'objectType' : 'person',
  'displayName': 'Alice',
  'image': [{'url': 'https://alice.com/alice.jpg'}],
  'url': ['http://alice.com/'],
}
ACTOR_REF_BSKY = {
  '$type': 'app.bsky.actor.ref#withInfo',
  'did': 'did:web:alice.com',
  'declaration': {
    '$type': 'app.bsky.system.declRef',
    'cid': 'TODO',
    'actorType': 'app.bsky.system.actorUser',
  },
  'handle': 'alice.com',
  'displayName': 'Alice',
  'avatar': 'https://alice.com/alice.jpg',
}

POST_AS = {
  'objectType': 'activity',
  'verb': 'post',
  'object': {
    'objectType': 'note',
    'published': '2007-07-07T03:04:05',
    'content': 'My post',
    'url': 'http://orig/post',
  }
}
POST_HTML = """
<article class="h-entry">
  <main class="e-content">My post</main>
  <a class="u-url" href="http://orig/post"></a>
  <time class="dt-published" datetime="2007-07-07T03:04:05"></time>
</article>
"""
POST_BSKY = {
  '$type': 'app.bsky.feed.feedViewPost',
  'post': {
    '$type': 'app.bsky.feed.post#view',
    'uri': 'http://orig/post',
    'cid': 'TODO',
    'record': {
      '$type': 'app.bsky.feed.post',
      'text': 'My post',
      'createdAt': '2007-07-07T03:04:05',
    },
    'replyCount': 0,
    'repostCount': 0,
    'upvoteCount': 0,
    'downvoteCount': 0,
    'indexedAt': '2022-01-02T03:04:05+00:00',
    'viewer': {},
  }
}

REPLY_AS = {
  'objectType': 'activity',
  'verb': 'post',
  'object': {
    'objectType': 'comment',
    'published': '2008-08-08T03:04:05',
    'content': 'I hereby reply to this',
    'url': 'http://a/reply',
    'inReplyTo': [{'url': 'http://orig/post'}],
  },
}
REPLY_HTML = """
<article class="h-entry">
  <main class="e-content">I hereby reply to this</a></main>
  <a class="u-in-reply-to" href="http://orig/post"></a>
  <a class="u-url" href="http://a/reply"></a>
  <time class="dt-published" datetime="2008-08-08T03:04:05"></time>
</article>
"""
REPLY_BSKY = copy.deepcopy(POST_BSKY)
REPLY_BSKY['post'].update({
  'uri': 'http://a/reply',
  'record': {
    '$type': 'app.bsky.feed.post',
    'text': 'I hereby reply to this',
    'createdAt': '2008-08-08T03:04:05',
    'reply': {
      '$type': 'app.bsky.feed.post#replyRef',
      'root': {
        '$type': 'com.atproto.repo.strongRef',
        'uri': 'http://orig/post',
        'cid': 'TODO',
      },
      'parent': {
        '$type': 'com.atproto.repo.strongRef',
        'uri': 'http://orig/post',
        'cid': 'TODO',
      },
    },
  },
})

REPOST_AS = {
  'objectType': 'activity',
  'verb': 'share',
  'actor': ACTOR_AS,
  'published': '2007-07-07T03:04:05',
  'content': 'A compelling post',
  'object': {
    'url': 'http://orig/post',
  },
}
REPOST_HTML = """
<article class="h-entry">
  <main class="e-content">A compelling post</main>
  <a class="u-repost-of" href="http://orig/post"></a>
  <time class="dt-published" datetime="2007-07-07T03:04:05"></time>
</article>
"""
REPOST_BSKY = copy.deepcopy(POST_BSKY)
REPOST_BSKY['post']['record'].update({
  '$type': 'app.bsky.feed.post',
  'text': '',
  'createdAt': '',
})
REPOST_BSKY['reason'] = {
  '$type': 'app.bsky.feed.feedViewPost#reasonRepost',
  'by': ACTOR_REF_BSKY,
  'indexedAt': NOW.isoformat(),
}


class TestBluesky(testutil.TestCase):

  def test_url_to_did_web(self):
    for bad in None, '', 'foo', 'did:web:bar.com':
      with self.assertRaises(ValueError):
        url_to_did_web(bad)

    self.assertEqual('did:web:foo.com', url_to_did_web('https://foo.com'))
    self.assertEqual('did:web:foo.com', url_to_did_web('https://foo.com/'))
    self.assertEqual('did:web:foo.com%3A3000', url_to_did_web('https://foo.com:3000'))
    self.assertEqual('did:web:bar.com:baz:baj', url_to_did_web('https://bar.com/baz/baj'))

  def test_did_web_to_url(self):
    for bad in None, '', 'foo' 'https://bar.com':
      with self.assertRaises(ValueError):
        did_web_to_url(bad)

    self.assertEqual('https://foo.com/', did_web_to_url('did:web:foo.com'))
    self.assertEqual('https://foo.com/', did_web_to_url('did:web:foo.com:'))
    self.assertEqual('https://foo.com:3000/', did_web_to_url('did:web:foo.com%3A3000'))
    self.assertEqual('https://bar.com/baz/baj', did_web_to_url('did:web:bar.com:baz:baj'))

  def test_from_as1_post(self):
    self.assert_equals(POST_BSKY, from_as1(POST_AS))

  def test_from_as1_reply(self):
    self.assert_equals(REPLY_BSKY, from_as1(REPLY_AS))

  def test_from_as1_repost(self):
    self.assert_equals(REPOST_BSKY, from_as1(REPOST_AS))

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
    self.assert_equals(ACTOR_REF_BSKY, actor_to_ref(ACTOR_AS))
