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
  'url': 'https://alice.com/',
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
TAGS = [{
  'url': 'http://my/link',
  'startIndex': 8,
  'length': 4,
}]
ENTITIES = [{
  "type": "link",
  "value": "http://my/link",
  "text": "link",
  "index": {
    "start": 8,
    "end": 12,
  },
}]
EMBED_EXTERNAL = {
  'description': '',
  'title': 'link',
  'uri': 'http://my/link',
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
  'content': 'A compelling post',
  'object': {
    'objectType': 'note',
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

  def test_from_as1_post_html(self):
    post_as = copy.deepcopy(POST_AS)
    post_as['object']['content'] = """
    <p class="h-event">
      <a class="u-url p-name" href="http://h.w/c">
        Homebrew Website Club</a>
      is <em>tonight</em>!
      <img class="shadow" src="/pour_over_coffee_stand.jpg" /></p>
    <time class="dt-start">6:30pm PST</time> at
    <a href="https://wiki.mozilla.org/SF">Mozilla SF</a> and
    <a href="https://twitter.com/esripdx">Esri Portland</a>.<br />Join us!
    """
    self.assert_equals("""\
Homebrew Website Club is _tonight_!

6:30pm PST at Mozilla SF and Esri Portland.
Join us!""", from_as1(post_as)['post']['record']['text'])

  def test_from_as1_post_html_with_tag_indices_not_implemented(self):
    post_as = copy.deepcopy(POST_AS)
    post_as['object'].update({
      'content': '<em>some html</em>',
      'tags': TAGS,
    })

    with self.assertRaises(NotImplementedError):
      from_as1(post_as)

  def test_from_as1_post_with_tag_indices(self):
    post_as = copy.deepcopy(POST_AS)
    post_as['object'].update({
      'content': 'A note. link too',
      'tags': TAGS,
    })

    post_bsky = copy.deepcopy(POST_BSKY)
    post_bsky['post']['record'].update({
      'text': 'A note. link too',
      'entities': ENTITIES,
      'embed': {
        '$type': 'app.bsky.embed.external',
        'external': [{
          '$type': 'app.bsky.embed.external#external',
          **EMBED_EXTERNAL,
        }],
      },
    })
    post_bsky['post']['embed'] = {
      '$type': 'app.bsky.embed.external#presented',
      'external': [{
        '$type': 'app.bsky.embed.external#presentedExternal',
        **EMBED_EXTERNAL,
      }],
    }

    self.assert_equals(post_bsky, from_as1(post_as))

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

  def test_from_as1_actor_handle(self):
    for expected, fields in (
        ('', {}),
        ('fooey', {'username': 'fooey'}),
        ('fooey@my', {'username': 'fooey', 'url': 'http://my/url', 'id': 'tag:nope'}),
        ('foo,2001:extra', {'id': 'tag:foo,2001:extra'}),
        ('url/with/path', {'url': 'http://url/with/path'}),
        ('foo', {'url': 'http://foo/'}),
    ):
      self.assert_equals(expected, from_as1({
        'objectType' : 'person',
        **fields,
      })['handle'])

  def test_from_as1_actor_id_not_url(self):
    """Tests error handling when attempting to generate did:web."""
    self.assertEqual('', from_as1({
      'objectType' : 'person',
      'id': 'tag:foo.com,2001:bar',
    })['did'])

  def test_to_as1_post(self):
    self.assert_equals(POST_AS['object'], to_as1(POST_BSKY))

  def test_to_as1_reply(self):
    self.assert_equals(REPLY_AS['object'], to_as1(REPLY_BSKY))

  def test_to_as1_repost(self):
    repost_as = copy.deepcopy(REPOST_AS)
    del repost_as['content']
    self.assert_equals(repost_as, to_as1(REPOST_BSKY))

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
