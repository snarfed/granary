"""Unit tests for as1.py."""
import copy
import re

from oauth_dropins.webutil import testutil

from .. import as1

ACTOR = {
  'id': 'tag:fake.com:444',
  'displayName': 'Bob',
  'url': 'https://plus.google.com/bob',
  'image': {'url': 'https://bob/picture'},
}
NOTE = {
  'objectType': 'note',
  'id': 'tag:fake.com:my-note',
  'url': 'http://fake.com/my-note',
  'content': 'my note',
  'published': '2012-02-22T20:26:41',
}
MENTION = copy.deepcopy(NOTE)
MENTION['tags'] = [{
  'objectType': 'mention',
  'url': 'https://alice',
  'displayName': 'Alice',
}]
LIKES = [{
  'verb': 'like',
  'author': {'id': 'tag:fake.com:person', 'numeric_id': '5'},
  'object': {'url': 'http://foo/like/5'},
}, {
  'verb': 'like',
  'author': {'id': 'tag:fake.com:6'},
  'object': {'url': 'http://bar/like/6'},
}]
REACTIONS = [{
  'id': 'tag:fake.com:apple',
  'verb': 'react',
  'content': '✁',
  'author': {'id': 'tag:fake.com:5'},
  'object': {'url': 'http://foo/like/5'},
}]
SHARES = [{
  'verb': 'share',
  'author': {'id': 'tag:fake.com:3'},
  'object': {'url': 'http://bar/like/3'},
}]
ACTIVITY = {
  'id': '1',
  'object': {
    'id': '1',
    'tags': LIKES + REACTIONS + SHARES,
  },
}
COMMENT = {
  'objectType': 'comment',
  'content': 'A ☕ reply',
  'id': 'tag:fake.com:123456',
  'published': '2012-12-05T00:58:26+00:00',
  'url': 'https://fake.com/123456',
  'inReplyTo': [{
    'id': 'tag:fake.com:123',
    'url': 'https://fake.com/123',
  }],
}
POST = {
  'objectType': 'activity',
  'verb': 'post',
  'id': 'tag:fake.com:123#post',
  'object': COMMENT,
}
UPDATE = {
  'objectType': 'activity',
  'verb': 'update',
  'id': 'tag:fake.com:123456#update',
  'object': COMMENT,
}
DELETE_OF_ID = {
  'objectType': 'activity',
  'verb': 'delete',
  'id': 'tag:fake.com:123456#delete',
  'object': COMMENT['id'],
}
EVENT = {
  'id': 'tag:fake.com:246',
  'objectType': 'event',
  'displayName': 'Homebrew Website Club',
  'url': 'https://facebook.com/246',
  'author': {'displayName': 'Host', 'id': 'tag:fake.com,2013:666'},
}
RSVP_YES = {
  'id': 'tag:fake.com:246_rsvp_11500',
  'objectType': 'activity',
  'verb': 'rsvp-yes',
  'actor': {'displayName': 'Aaron P', 'id': 'tag:fake.com,2013:11500'},
  'url': 'https://facebook.com/246#11500',
}
RSVP_NO = {
  'objectType': 'activity',
  'verb': 'rsvp-no',
  'actor': {'displayName': 'Ryan B'},
  'url': 'https://facebook.com/246',
}
RSVP_MAYBE = {
  'id': 'tag:fake.com:246_rsvp_987',
  'objectType': 'activity',
  'verb': 'rsvp-maybe',
  'actor': {'displayName': 'Foo', 'id': 'tag:fake.com,2013:987'},
  'url': 'https://facebook.com/246#987',
}
INVITE = {
  'id': 'tag:fake.com:246_rsvp_555',
  'objectType': 'activity',
  'verb': 'invite',
  'actor': {'displayName': 'Host', 'id': 'tag:fake.com,2013:666'},
  'object': {'displayName': 'Invit Ee', 'id': 'tag:fake.com,2013:555'},
  'url': 'https://facebook.com/246#555',
}
RSVPS = [RSVP_YES, RSVP_NO, RSVP_MAYBE, INVITE]
EVENT_WITH_RSVPS = copy.deepcopy(EVENT)
EVENT_WITH_RSVPS.update({
  'attending': [RSVP_YES['actor']],
  'notAttending': [RSVP_NO['actor']],
  'maybeAttending': [RSVP_MAYBE['actor']],
  'invited': [INVITE['object']],
})
LIKE = {
  'id': 'tag:fake.com:001_liked_by_222',
  'url': 'http://plus.google.com/001#liked-by-222',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'http://plus.google.com/001'},
  'author': {
    'kind': 'plus#person',
    'id': 'tag:fake.com:222',
    'displayName': 'Alice',
    'url': 'https://profiles.google.com/alice',
    'image': {'url': 'https://alice/picture'},
  },
}
FOLLOW = {
  'id': 'tag:fake.com:333',
  'objectType': 'activity',
  'verb': 'follow',
  'actor': ACTOR['id'],
  'object': 'https://www.realize.be/',
}
FOLLOW_WITH_ACTOR = copy.deepcopy(FOLLOW)
FOLLOW_WITH_ACTOR['actor'] = ACTOR
FOLLOW_WITH_OBJECT = copy.deepcopy(FOLLOW)
FOLLOW_WITH_OBJECT['object'] = ACTOR


class As1Test(testutil.TestCase):

  def test_is_public(self):
    self.assertIsNone(as1.is_public(None))

    for obj in (
        {'to': [{'objectType': 'unknown'}]},
        {'to': [{'objectType': 'unknown'},
                {'objectType': 'unknown'}]},
        {'to': [{'alias': 'xyz'},
                {'objectType': 'unknown'}]},
    ):
      with self.subTest(obj=obj):
        self.assertIsNone(as1.is_public(obj))
        self.assertIsNone(as1.is_public({'object': obj}))

    for obj in (
        {},
        {'privacy': 'xyz'},
        {'to': [{'objectType': 'group', 'alias': '@unlisted'}]},
        {'to': [{'objectType': 'group', 'alias': '@public'}]},
        {'to': [{'objectType': 'group', 'alias': '@private'},
                {'objectType': 'group', 'alias': '@public'}]},
        {'to': [{'alias': '@public'},
                {'alias': '@private'}]},
    ):
      with self.subTest(obj=obj):
        self.assertTrue(as1.is_public(obj))
        self.assertTrue(as1.is_public({'object': obj}))


    self.assertFalse(as1.is_public({
      'to': [{'objectType': 'group', 'alias': '@unlisted'}],
    }, unlisted=False))


    for obj in (
        {'to': []},
        {'to': [{}]},
        {'to': ['someone']},
        {'to': [{'objectType': 'group'}]},
        {'to': [{'objectType': 'group', 'alias': '@private'}]},
        {'to': [{'objectType': 'group', 'alias': 'xyz'}]},
        {'to': [{'alias': 'xyz'}]},
        {'to': [{'alias': 'xyz'},
                {'alias': '@private'}]},
        {'to': [{'objectType': 'group'},
                {'alias': 'xyz'},
                {'alias': '@private'}]},
    ):
      with self.subTest(obj=obj):
        self.assertFalse(as1.is_public(obj))
        self.assertFalse(as1.is_public({'object': obj}))

  def test_recipient_if_dm(self):
    actor = {
      'id': 'https://alice',
      'followers': 'http://the/follow/ers',
      'following': 'http://the/follow/ing',
    }

    for obj in (
        None,
        {},
        {'to': [{'objectType': 'unknown'}]},
        {'to': [{'objectType': 'unknown'}, {'objectType': 'unknown'}]},
        {'to': [{'alias': '@public'}]},
        {'to': [{'alias': '@unlisted'}]},
        {'to': ['did:eve'],
         'cc': ['did:bob']},
        {'to': ['did:eve'],
         'bcc': ['did:bob']},
        {'to': ['did:eve'],
         'bto': ['did:bob']},
        {'to': [{'id': 'https://www.w3.org/ns/activitystreams#Public'},
                {'objectType': 'group', 'alias': '@public'}]},
        {'to': [{'id': 'https://www.w3.org/ns/activitystreams#Public'}]},
        {'to': 'https://www.w3.org/ns/activitystreams#Public'},
        # not a note
        {'objectType': 'person', 'to': 'http://recip'},
        # not creates
        {
          'objectType': 'activity',
          'verb': 'update',
          'object': {'to': ['http://bob']},
        },
        {
          'objectType': 'activity',
          'verb': 'delete',
          'object': {'to': ['http://bob']},
        },
        ):
      with self.subTest(obj=obj):
        self.assertIsNone(as1.recipient_if_dm(obj))
        self.assertIsNone(as1.recipient_if_dm(obj, actor=actor))
        self.assertFalse(as1.is_dm(obj))
        self.assertFalse(as1.is_dm(obj, actor=actor))

    # followers/ing collections
    for obj in (
        {'to': 'http://the/follow/ers'},
        {'to': 'http://the/follow/ers', 'objectType': 'note'},
        {'to': ['http://the/follow/ers']},
        {'to': ['http://the/follow/ing']},
        {'to': [{'id': 'http://the/follow/ers'}]},
    ):
      with self.subTest(obj=obj):
        self.assertTrue(as1.recipient_if_dm(obj))
        self.assertIsNone(as1.recipient_if_dm(obj, actor=actor))
        self.assertIsNone(as1.recipient_if_dm({**obj, 'author': actor}))
        self.assertIsNone(as1.recipient_if_dm({
          'objectType': 'activity',
          'verb': 'post',
          'object': {**obj, 'author': actor},
        }))

    # /followers, /following heuristic
    for obj in (
        {'to': 'http://the/followers'},
        {'to': ['http://the/followers']},
        {'to': ['http://the/following']},
        {'to': [{'id': 'http://the/followers'}]},
    ):
      with self.subTest(obj=obj):
        self.assertIsNone(as1.recipient_if_dm(obj))
        self.assertIsNone(as1.recipient_if_dm(obj, actor=actor))
        self.assertIsNone(as1.recipient_if_dm({**obj, 'author': actor}))

    self.assertEqual('http://bob', as1.recipient_if_dm({'to': ['http://bob']}, actor))
    self.assertTrue('http://bob', as1.is_dm({'to': ['http://bob']}, actor))

    create = {
      'objectType': 'activity',
      'verb': 'post',
      'object': {
        'to': ['http://bob'],
      },
    }
    self.assertEqual('http://bob', as1.recipient_if_dm(create, actor))
    self.assertTrue('http://bob', as1.is_dm(create, actor))

    self.assertEqual('bob', as1.recipient_if_dm({'to': ['bob']}, actor))
    self.assertEqual('did:bob', as1.recipient_if_dm({'to': ['did:bob']}, actor))
    self.assertEqual('did:bob', as1.recipient_if_dm({
      'object': {'to': ['did:bob']},
      'to': ['did:bob'],
    }))
    self.assertEqual('did:bob', as1.recipient_if_dm({
      'objectType': 'activity',
      'verb': 'post',
      'object': {'to': ['did:bob']},
    }))

    # self DM is still DM I guess
    self.assertEqual('http://alice',
                     as1.recipient_if_dm({'to': ['http://alice']}, actor))

  def test_is_audience(self):
    for val in (
        None,
        '',
        {},
        'unknown',
        'did:user',
        'user.com',
        'http://user.com/',
        'http://mas.to/@user',
    ):
      with self.subTest(val=val):
        self.assertFalse(as1.is_audience(val))

    for val in (
        'Public',
        'as:Public',
        '@public',
        '@unlisted',
        '@private',
        'https://www.w3.org/ns/activitystreams#Public',
        'https://www.w3.org/ns/xyz',
        'http://mas.to/@user/followers',
    ):
      with self.subTest(val=val):
        self.assertTrue(as1.is_audience(val))

  def test_activity_changed(self):
    fb_post = copy.deepcopy(ACTIVITY)
    fb_post['object']['updated'] = '2016-01-02T00:00:00+00:00'
    fb_post_edited = copy.deepcopy(fb_post)
    fb_post_edited['object']['updated'] = '2016-01-02T00:58:26+00:00'

    fb_comment = COMMENT
    fb_comment_edited = copy.deepcopy(fb_comment)
    fb_comment_edited['published'] = '2016-01-02T00:58:26+00:00'

    gp_like = LIKE
    gp_like_edited = copy.deepcopy(gp_like)
    gp_like_edited['author'] = ACTOR

    for before, after in (({}, {}),
                          ({'x': 1}, {'y': 2}),
                          ({'to': None}, {'to': ''}),
                          (fb_post, fb_post_edited),
                          (fb_comment, fb_comment_edited),
                          (gp_like, gp_like_edited)):
      self.assertFalse(as1.activity_changed(before, after, log=True),
                       f'{before}\n{after}')

    fb_comment_edited_inReplyTo = copy.deepcopy(fb_comment_edited)
    fb_comment_edited_inReplyTo['inReplyTo'].append({
      'id': 'tag:fake.com:000000000000000',
      'url': 'https://www.facebook.com/000000000000000',
    })
    fb_comment_edited['content'] = 'new content'
    gp_like_edited['to'] = [{'objectType':'group', 'alias':'@private'}]

    fb_invite = INVITE
    self.assertEqual('invite', fb_invite['verb'])
    fb_rsvp = RSVP_YES

    for before, after in ((fb_comment, fb_comment_edited),
                          (fb_comment, fb_comment_edited_inReplyTo),
                          (gp_like, gp_like_edited),
                          (fb_invite, fb_rsvp)):
      self.assertTrue(as1.activity_changed(before, after, log=True),
                      f'{before}\n{after}')

    self.assertFalse(as1.activity_changed(
      fb_comment, fb_comment_edited_inReplyTo, inReplyTo=False, log=True))

  def test_activity_changed_in_reply_to_author_name(self):
    first = copy.copy(COMMENT)
    first['inReplyTo'][0]['author'] = copy.deepcopy(ACTOR)

    second = copy.copy(COMMENT)
    second['inReplyTo'][0]['author'] = copy.deepcopy(ACTOR)
    second['inReplyTo'][0]['author']['displayName'] = 'other'
    self.assertFalse(as1.activity_changed(first, second, log=True))

  def test_append_in_reply_to(self):
    fb_comment_before = copy.deepcopy(COMMENT)
    fb_comment_after_same = copy.deepcopy(fb_comment_before)
    as1.append_in_reply_to(fb_comment_before,fb_comment_after_same)
    self.assertEqual(COMMENT, fb_comment_before)
    self.assertEqual(COMMENT, fb_comment_after_same)

    fb_comment_after_diff = copy.deepcopy(fb_comment_before)
    fb_comment_after_targ = copy.deepcopy(fb_comment_before)
    fb_comment_after_diff['inReplyTo'] = ['new']
    fb_comment_after_targ['inReplyTo'] = fb_comment_after_diff.get('inReplyTo')+fb_comment_before.get('inReplyTo')
    as1.append_in_reply_to(fb_comment_before,fb_comment_after_diff)
    self.assertEqual(fb_comment_after_targ,fb_comment_after_diff)

  def test_add_rsvps_to_event(self):
    event = copy.deepcopy(EVENT)
    as1.add_rsvps_to_event(event, [])
    self.assert_equals(EVENT, event)

    as1.add_rsvps_to_event(event, RSVPS)
    self.assert_equals(EVENT_WITH_RSVPS, event)

  def test_get_rsvps_from_event(self):
    self.assert_equals([], as1.get_rsvps_from_event(EVENT))
    self.assert_equals(RSVPS, as1.get_rsvps_from_event(EVENT_WITH_RSVPS))

  def test_get_rsvps_from_event_bad_id(self):
    event = copy.deepcopy(EVENT)
    for id in None, 'not_a_tag_uri':
      event['id'] = id
      self.assert_equals([], as1.get_rsvps_from_event(event))
  def check_original_post_discovery(self, obj, originals, mentions=None,
                                    **kwargs):
    got = as1.original_post_discovery({'object': obj}, **kwargs)
    self.assert_equals(originals, got[0])
    self.assert_equals(mentions or [], got[1])

  def test_original_post_discovery(self):
    check = self.check_original_post_discovery

    # noop
    obj = {
      'objectType': 'article',
      'displayName': 'article abc',
      'url': 'http://example.com/article-abc',
      'tags': [],
    }
    check(obj, [])

    # attachments and tags become upstreamDuplicates
    check({'tags': [{'url': 'http://a', 'objectType': 'article'},
                    {'url': 'http://b'}],
           'attachments': [{'url': 'http://c', 'objectType': 'mention'}]},
          ['http://a/', 'http://b/', 'http://c/'])

    # non-article objectType
    urls = [{'url': 'http://x.com/y', 'objectType': 'image'}]
    check({'attachment': urls}, [])
    check({'tags': urls}, [])

    # permashortcitations
    check({'content': 'x (not.at end) y (at.the end)'}, ['http://at.the/end'])

    # merge with existing tags
    obj.update({
      'content': 'x http://baz/3 yyyy',
      'attachments': [{'objectType': 'article', 'url': 'http://foo/1'}],
      'tags': [{'objectType': 'article', 'url': 'http://bar/2'}],
    })
    check(obj, ['http://foo/1', 'http://bar/2', 'http://baz/3'])

    # links become upstreamDuplicates
    check({'content': 'asdf http://first ooooh http://second qwert'},
          ['http://first/', 'http://second/'])
    check({'content': 'x http://existing y',
           'upstreamDuplicates': ['http://existing']},
          ['http://existing/'])

    # leading parens used to cause us trouble
    check({'content': 'Foo (http://snarfed.org/xyz)'}, ['http://snarfed.org/xyz'])

    # don't duplicate http and https
    check({'content': 'X http://mention Y https://both Z http://both2',
           'upstreamDuplicates': ['http://upstream', 'http://both', 'https://both2']},
          ['http://upstream/', 'https://both/', 'https://both2/', 'http://mention/'])

    # don't duplicate PSCs and PSLs with http and https
    for scheme in 'http', 'https':
      url = scheme + '://foo.com/1'
      check({'content': 'x (foo.com/1)', 'tags': [{'url': url}]}, [url])

    check({'content': 'x (foo.com/1)', 'attachments': [{'url': 'http://foo.com/1'}]},
          ['http://foo.com/1'])
    check({'content': 'x (foo.com/1)', 'tags': [{'url': 'https://foo.com/1'}]},
          ['https://foo.com/1'])

    # exclude ellipsized URLs
    for ellipsis in '...', '…':
      url = 'foo.com/1' + ellipsis
      check({'content': f'x ({url})',
             'attachments': [{'objectType': 'article', 'url': 'http://' + url}]},
            [])

    # exclude ellipsized PSCs and PSLs
    for separator in '/', ' ':
      for ellipsis in '...', '…':
        check({'content': f'x (ttk.me{separator}123{ellipsis})'}, [])

    # domains param
    obj = {
      'content': 'x http://me.x.y/a y',
      'upstreamDuplicates': ['http://me.x.y/b'],
      'attachments': [{'url': 'http://me.x.y/c'}],
      'tags': [{'url': 'http://me.x.y/d'}],
    }
    links = ['http://me.x.y/a', 'http://me.x.y/b', 'http://me.x.y/c', 'http://me.x.y/d']
    check(obj, links)
    for domains in [], ['me.x.y'], ['foo', 'x.y']:
      check(obj, links, domains=domains)

    check(obj, [], mentions=links, domains=['e.x.y', 'not.me.x.y', 'alsonotme'])

    # utm_* query params
    check({'content': 'asdf http://other/link?utm_source=x&utm_medium=y&a=b qwert',
           'upstreamDuplicates': ['http://or.ig/post?utm_campaign=123']},
          ['http://or.ig/post', 'http://other/link?a=b'])

    # invalid URLs
    check({'upstreamDuplicates': [''],
           'tags': [{'url': 'http://bad]'}]},
          [])

    # bookmarks should include targetUrl
    check({'targetUrl': 'http://or.ig/'}, ['http://or.ig/'])

  def test_original_post_discovery_max_redirect_fetches(self):
    self.expect_requests_head('http://other/link', redirected_url='http://a'
                              ).InAnyOrder()
    self.expect_requests_head('http://sho.rt/post', redirected_url='http://b'
                              ).InAnyOrder()
    self.mox.ReplayAll()

    obj = {
      'content': 'asdf http://other/link qwert',
      'upstreamDuplicates': ['http://sho.rt/post', 'http://next/post'],
    }
    self.check_original_post_discovery(
      obj, ['http://a/', 'http://b/', 'http://next/post'], max_redirect_fetches=2)

  def test_original_post_discovery_follow_redirects_false(self):
    self.expect_requests_head('http://other/link',
                              redirected_url='http://other/link/redirected'
                             ).MultipleTimes()
    self.expect_requests_head('http://sho.rt/post',
                              redirected_url='http://or.ig/post/redirected'
                             ).MultipleTimes()
    self.mox.ReplayAll()

    obj = {
      'content': 'asdf http://other/link qwert',
      'upstreamDuplicates': ['http://sho.rt/post'],
    }
    originals = ['http://sho.rt/post', 'http://or.ig/post/redirected']
    mentions = ['http://other/link', 'http://other/link/redirected']

    check = self.check_original_post_discovery
    check(obj, originals + mentions)
    check(obj, originals, mentions=mentions, domains=['or.ig'])
    check(obj, ['http://or.ig/post/redirected', 'http://other/link/redirected'],
          include_redirect_sources=False)

  def test_original_post_discovery_excludes(self):
    """Should exclude reserved hosts, non-http(s) URLs, and missing domains."""
    obj = {
      'content': 'foo',
      'upstreamDuplicates': [
        'http://sho.rt/post',
        # local
        'http://localhost',
        'http://other/link',
        'http://y.local/path'
        # reserved
        'https://x.test/',
        # not http
        'file://foo.com/Ryan/.npmrc'
        'git@github.com:snarfed/granary.git',
        '/home/ryan/foo',
        'mailto:x@y.z',
        # missing domain
        'http:///foo/bar',
        'file:///Users/Ryan/.npmrc',
      ],
    }
    self.check_original_post_discovery(
      obj, ['http://sho.rt/post'], include_reserved_hosts=False)

  def test_original_post_discovery_exclude_hosts(self):
    obj = {
      'content': 'http://other/link https://x.test/ http://y.local/path',
      'upstreamDuplicates': ['http://localhost', 'http://sho.rt/post'],
    }
    self.check_original_post_discovery(
      obj, ['http://sho.rt/post'], include_reserved_hosts=False)

  def test_prefix_urls(self):
    for field in 'image', 'stream':
      with self.subTest(field):
        BEFORE = lambda: copy.deepcopy({field: {'url': 'xyz'}})
        AFTER = lambda: copy.deepcopy({field: {'url': 'abcxyz'}})
        activity = {
          'actor': BEFORE(),
          'object': {
            'author': BEFORE(),
            'replies': {'items': [BEFORE(), BEFORE(), AFTER()]},
            'attachments': [BEFORE(), {'author': BEFORE()}],
            'tags': [BEFORE(), {'actor': BEFORE()}],
          },
        }
        as1.prefix_urls(activity, field, 'abc')
        self.assert_equals({
          'actor': AFTER(),
          'object': {
            'author': AFTER(),
            'replies': {'items': [AFTER(), AFTER(), AFTER()]},
            'attachments': [AFTER(), {'author': AFTER()}],
            'tags': [AFTER(), {'actor': AFTER()}],
          },
        }, activity)

    # TODO: missing tests

  def test_object_urls(self):
    for expected, actor in (
        ([], {}),
        ([], {'displayName': 'foo'}),
        ([], {'url': None, 'urls': []}),
        (['http://foo'], {'url': 'http://foo'}),
        (['http://foo'], {'urls': [{'value': 'http://foo'}]}),
        (['http://foo', 'https://bar', 'http://baz'], {
          'url': 'http://foo',
          'urls': [{'value': 'https://bar'},
                   {'value': 'http://foo'},
                   {'value': 'http://baz'},
          ],
        }),
        (['https://www.jvt.me/img/profile.jpg'], {
          'url': {
            'value': 'https://www.jvt.me/img/profile.jpg',
            'alt': "Jamie Tanna's profile image",
          },
        }),
        # url field is list, invalid AS1, but we can be forgiving
        (['http://one', 'http://two', 'http://three'], {
          'url': ['http://one', 'http://two'],
          'urls': ['http://three'],
        }),
    ):
      self.assertEqual(expected, as1.object_urls(actor))

  def test_get_ids(self):
    for expected, obj in (
        ([], {}),
        ([], {'y': 'a'}),
        ([], {'x': ''}),
        ([], {'x': {}}),
        ([], {'x': {'foo': 'bar'}}),
        ([], {'x': [{}, '']}),
        (['b'], {'x': 'b'}),
        (['b'], {'y': 'a', 'x': 'b'}),
        (['b'], {'x': ['', 'b']}),
        (['b'], {'x': {'id': 'b'}}),
        (['b'], {'x': {'url': 'b'}}),
        (['b'], {'x': {'id': 'b', 'url': 'c'}}),
        (['b'], {'x': [{}, 'b']}),
        (['b'], {'x': [{'id': 'b'}, '']}),
        (['b', 'd'], {'x': ['b', 'd']}),
        (['b', 'd'], {'x': [{'id': 'b'}, {'url': 'd'}]}),
    ):
      with self.subTest(obj=obj):
        self.assertEqual(expected, sorted(as1.get_ids(obj, 'x')), obj)

  def test_get_object(self):
    for expected, obj in (
        ({}, None),
        ({}, {}),
        ({}, []),
        ({}, {'f': None}),
        ({}, {'f': {}}),
        ({'id': 'x'}, {'f': 'x'}),
        ({'y': 'z'}, {'f': {'y': 'z'}}),
        ({'id': 'x'}, {'f': ['x']}),
        ({'y': 'z'}, {'f': [{'y': 'z'}]}),
    ):
      with self.subTest(obj=obj):
        self.assertEqual(expected, as1.get_object(obj, 'f'))

  def test_get_objects(self):
    for expected, obj in (
        ([], None),
        ([], {}),
        ([], []),
        ([], {'f': None}),
        ([], {'f': {}}),
        ([], {'f': []}),
        ([{'id': 'x'}], {'f': 'x'}),
        ([{'id': 'x'}], {'f': ['x']}),
        ([{'y': 'z'}], {'f': {'y': 'z'}}),
        ([{'y': 'z'}], {'f': [{'y': 'z'}]}),
        ([{'id': 'x'}, {'y': 'z'}], {'f': ['x', {'y': 'z'}]}),
    ):
      with self.subTest(obj=obj):
        self.assertEqual(expected, as1.get_objects(obj, 'f'))

  def test_get_owner(self):
    with self.assertRaises(ValueError):
      as1.get_owner('x')

    for expected, obj in (
        (None, None),
        (None, {}),
        (None, {'x': 'y'}),
        ('a', {'author': 'a'}),
        ('a', {'actor': 'a'}),
        ('a', {'author': 'a', 'actor': 'b'}),
        ('a', {'author': {'id': 'a'}}),
        ('a', {'author': {'url': 'a'}}),
        ('a', {'id': 'a', 'objectType': 'organization'}),
        (None, {'x': 'y', 'objectType': 'organization'}),
        (None, {'verb': 'post', 'object': {}}),
        ('a', {'verb': 'post', 'object': {'author': 'a'}}),
        ('a', {'verb': 'update', 'object': {'actor': 'a'}}),
        ('abc', {'verb': 'delete', 'object': {'author': {'id': 'abc'}}}),
    ):
      with self.subTest(obj=obj):
        self.assertEqual(expected, as1.get_owner(obj))

  def test_targets(self):
    for expected, obj in [
        ([], None),
        ([], {}),
        ([], {'id': 'a'}),
        ([], {'object': 'a'}),
        ([], {'object': {'id': 'a'}}),
        ([], {'objectType': 'note', 'id': 'a'}),
        ([], {'verb': 'post', 'id': 'a', 'object': 'b'}),
        ([], {'verb': 'post', 'id': 'a', 'object': {'id': 'b'}}),
        ([], {'verb': 'update', 'id': 'a', 'object': 'b'}),
        ([], {'verb': 'delete', 'id': 'a', 'object': 'b'}),
        (['x'], {'verb': 'like', 'id': 'a', 'object': 'x'}),
        (['x'], {'verb': 'react', 'id': 'a', 'object': 'x'}),
        (['x'], {'verb': 'react', 'id': 'a', 'object': {'id': 'x'}}),
        (['x'], {'verb': 'react', 'id': 'a', 'object': {'url': 'x'}}),
        (['x'], {'id': 'a', 'inReplyTo': 'x'}),
        (['x'], {'id': 'a', 'inReplyTo': {'id': 'x'}}),
        (['x'], {'id': 'a', 'inReplyTo': {'url': 'x'}}),
        (['x'], {
          'verb': 'post',
          'id': 'a',
          'object': {'id': 'b', 'inReplyTo': 'x'},
        }),
        (['x'], {
          'verb': 'update',
          'id': 'a',
          'object': {'id': 'b', 'inReplyTo': 'x'},
        }),
        (['x'], {
          'verb': 'delete',
          'id': 'a',
          'object': {'id': 'b', 'inReplyTo': 'x'},
        }),
        (['x'], {
          'verb': 'share',
          'id': 'a',
          'object': 'x',
        }),
        (['y', 'x'], {
          'verb': 'share',
          'id': 'a',
          'object': {'id': 'y', 'inReplyTo': 'x'},
        }),
        (['x', 'y'], {'tags': ['x', 'y']}),
        (['x', 'y'], {'tags': [{'id': 'x'}, {'url': 'y'}]}),
        (['x', 'y'], {'tags': [{'id': 'x'}, {'url': 'y'}]}),
        (['x'], {'tags': [{'url': 'x', 'objectType': 'mention'}]}),
    ]:
      with self.subTest(expected=expected, obj=obj):
        self.assertCountEqual(expected, as1.targets(obj))

  def test_get_url(self):
    for obj, expected in (
        (None, ''),
        ('', ''),
        ('foo', 'foo'),
        ({'url': 'foo'}, 'foo'),
        ({'url': ['foo', 'bar']}, 'foo'),
        ({'url': {'value': 'foo'}}, 'foo'),
    ):
      with self.subTest(expected=expected, obj=obj):
        self.assertEqual(expected, as1.get_url(obj))
