# coding=utf-8
"""Unit tests for source.py.
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import copy

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import facebook
from granary import googleplus
from granary import instagram
from granary import source
from granary.source import Source
from granary import twitter
import test_facebook
import test_googleplus


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
  'content': u'✁',
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
EVENT = {
  'id': 'tag:fake.com:246',
  'objectType': 'event',
  'displayName': 'Homebrew Website Club',
  'url': 'https://facebook.com/246',
  'author': {'displayName': 'Host', 'id': 'tag:fake.com,2013:666'},
}
EVENT_WITH_RSVPS = copy.deepcopy(EVENT)
EVENT_WITH_RSVPS.update({
  'attending': [RSVP_YES['actor']],
  'notAttending': [RSVP_NO['actor']],
  'maybeAttending': [RSVP_MAYBE['actor']],
  'invited': [INVITE['object']],
})
EVENT_ACTIVITY_WITH_RSVPS = {'object': EVENT_WITH_RSVPS}


class FakeSource(Source):
  DOMAIN = 'fake.com'


class SourceTest(testutil.TestCase):

  def setUp(self):
    super(SourceTest, self).setUp()
    self.source = FakeSource()
    self.mox.StubOutWithMock(self.source, 'get_activities')
    self.mox.StubOutWithMock(self.source, 'get_event')

  def check_original_post_discovery(self, obj, originals, mentions=None,
                                    **kwargs):
    got = Source.original_post_discovery({'object': obj}, **kwargs)
    self.assertItemsEqual(originals, got[0])
    self.assertItemsEqual(mentions or [], got[1])

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
    for ellipsis in '...', u'…':
      url = 'foo.com/1' + ellipsis
      check({'content': 'x (%s)' % url,
             'attachments': [{'objectType': 'article', 'url': 'http://' + url}]},
            [])

    # exclude ellipsized PSCs and PSLs
    for separator in '/', ' ':
      for ellipsis in '...', u'…':
        check({'content': 'x (ttk.me%s123%s)' % (separator, ellipsis)}, [])

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

  def test_original_post_discovery_follow_redirects(self):
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

  def test_get_like(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(LIKES[1], self.source.get_like('author', 'activity', '6'))

  def test_get_like_with_activity(self):
    # skips fetch
    self.assert_equals(LIKES[1], self.source.get_like(
      'author', 'activity', '6', activity=ACTIVITY))

  def test_get_like_numeric_id(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(LIKES[0], self.source.get_like('author', 'activity', '5'))

  def test_get_like_not_found(self):
    activity = copy.deepcopy(ACTIVITY)
    del activity['object']['tags']
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([activity])
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_like('author', 'activity', '6'))

  def test_get_like_no_activity(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([])
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_like('author', 'activity', '6'))

  def test_get_reaction(self):
    self.source.get_activities(user_id='author', activity_id='activity'
                               ).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(REACTIONS[0], self.source.get_reaction(
      'author', 'activity', '5', 'apple'))

  def test_get_reaction_with_activity(self):
    # skips fetch
    self.assert_equals(REACTIONS[0], self.source.get_reaction(
      'author', 'activity', '5', 'apple', activity=ACTIVITY))

  def test_get_reaction_not_found(self):
    self.source.get_activities(user_id='author', activity_id='activity'
                               ).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assertIsNone(self.source.get_reaction('author', 'activity', '5', 'foo'))

  def test_get_share(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_shares=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(SHARES[0], self.source.get_share('author', 'activity', '3'))

  def test_get_share_with_activity(self):
    # skips fetch
    self.assert_equals(SHARES[0], self.source.get_share(
      'author', 'activity', '3', activity=ACTIVITY))

  def test_get_share_not_found(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_shares=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_share('author', 'activity', '6'))

  def test_add_rsvps_to_event(self):
    event = copy.deepcopy(EVENT)
    Source.add_rsvps_to_event(event, [])
    self.assert_equals(EVENT, event)

    Source.add_rsvps_to_event(event, RSVPS)
    self.assert_equals(EVENT_WITH_RSVPS, event)

  def test_get_rsvps_from_event(self):
    self.assert_equals([], Source.get_rsvps_from_event(EVENT))
    self.assert_equals(RSVPS, Source.get_rsvps_from_event(EVENT_WITH_RSVPS))

  def test_get_rsvps_from_event_bad_id(self):
    event = copy.deepcopy(EVENT)
    for id in None, 'not_a_tag_uri':
      event['id'] = id
      self.assert_equals([], Source.get_rsvps_from_event(event))

  def test_get_rsvp(self):
    self.source.get_event('1').MultipleTimes().AndReturn(EVENT_ACTIVITY_WITH_RSVPS)
    self.mox.ReplayAll()
    self.assert_equals(RSVP_YES, self.source.get_rsvp('unused', '1', '11500'))
    self.assert_equals(RSVP_MAYBE, self.source.get_rsvp('unused', '1', '987'))
    self.assert_equals(INVITE, self.source.get_rsvp('unused', '1', '555'))

  def test_get_rsvp_not_found(self):
    self.source.get_event('1').AndReturn(EVENT_ACTIVITY_WITH_RSVPS)
    self.source.get_event('2').AndReturn({'object': EVENT})
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_rsvp('123', '1', 'xyz'))
    self.assert_equals(None, self.source.get_rsvp('123', '2', '11500'))

  def test_get_rsvp_event_not_found(self):
    self.source.get_event('1').AndReturn(None)
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_rsvp('123', '1', '456'))

  def test_get_rsvp_with_event(self):
    # skips event fetch
    self.assert_equals(RSVP_YES, self.source.get_rsvp(
      'unused', '1', '11500', event=EVENT_ACTIVITY_WITH_RSVPS))

  def test_base_object_multiple_objects(self):
    like = copy.deepcopy(LIKES[0])
    like['object'] = [like['object'], {'url': 'http://fake.com/second/'}]
    self.assert_equals({'id': 'second', 'url': 'http://fake.com/second/'},
                       self.source.base_object(like))

  def test_content_for_create(self):
    def cfc(base, extra, **kwargs):
      obj = base.copy()
      obj.update(extra)
      return self.source._content_for_create(obj, **kwargs)

    self.assertEqual('', cfc({}, {}))

    for base in ({'objectType': 'article'},
                 {'inReplyTo': {'url': 'http://not/fake'}},
                 {'objectType': 'comment', 'object': {'url': 'http://not/fake'}}):
      self.assertEqual('', cfc(base, {}))
      self.assertEqual('c', cfc(base, {'content': ' c '}))
      self.assertEqual('c', cfc(base, {'content': 'c', 'displayName': 'n'}))
      self.assertEqual('s', cfc(base, {'content': 'c', 'displayName': 'n',
                                       'summary': 's'}))
      self.assertEqual('c<a&b\nhai', cfc(base, {'content': 'c<a&b\nhai'},
                                         ignore_formatting=True))
      # when the text of content and summary are the same, content should
      # override so we can use its formatting
      self.assertEqual('the\ntext', cfc(base, {'content': '  the<br />text',
                                               'summary': 'thetext  '}))

    for base in ({'objectType': 'note'},
                 {'inReplyTo': {'url': 'http://fake.com/post'}},
                 {'objectType': 'comment',
                  'object': {'url': 'http://fake.com/post'}}):
      self.assertEqual('', cfc(base, {}))
      self.assertEqual('n', cfc(base, {'displayName': 'n'}))
      self.assertEqual('c', cfc(base, {'displayName': 'n', 'content': 'c'}))
      self.assertEqual('n', cfc(base, {'displayName': 'n', 'content': 'c'},
                                prefer_name=True))
      self.assertEqual('s', cfc(base, {'displayName': 'n', 'content': 'c',
                                       'summary': ' s '}))
      self.assertEqual('s', cfc(base, {'displayName': 'n', 'content': 'c',
                                       'summary': ' s '},
                                prefer_name=True))

      # test stripping <video>
      # https://github.com/snarfed/bridgy/issues/612#issuecomment-175096511
      # based on http://tantek.com/2016/010/t2/waves-break-rush-lava-rocks
      self.assertEqual('Watching waves break.', cfc(base, {
        'content': '<video class="u-video" loop="loop"><a href="xyz>a video</a>'
                   '</video>Watching waves break.',
      }, strip_first_video_tag=True))

    # Odd bug triggered by specific combination of leading <span> and trailing #
    # https://github.com/snarfed/bridgy/issues/656
    self.assertEqual('2016. #',
                     cfc({'objectType': 'note'}, {'content': '<span /> 2016. #'}))
    # double check our hacky fix. (programming is the worst!)
    self.assertEqual('XY', cfc({'objectType': 'note'}, {'content': 'XY'}))

  def test_activity_changed(self):
    fb_post = test_facebook.ACTIVITY
    fb_post_edited = copy.deepcopy(fb_post)
    fb_post_edited['object']['updated'] = '2016-01-02T00:58:26+00:00'

    fb_comment = test_facebook.COMMENT_OBJS[0]
    fb_comment_edited = copy.deepcopy(fb_comment)
    fb_comment_edited['published'] = '2016-01-02T00:58:26+00:00'

    gp_like = test_googleplus.LIKE
    gp_like_edited = copy.deepcopy(gp_like)
    gp_like_edited['author'] = test_googleplus.RESHARER

    for before, after in (({}, {}),
                          ({'x': 1}, {'y': 2}),
                          ({'to': None}, {'to': ''}),
                          (fb_post, fb_post_edited),
                          (fb_comment, fb_comment_edited),
                          (gp_like, gp_like_edited)):
      self.assertFalse(self.source.activity_changed(before, after, log=True),
                                                    '%s\n%s' % (before, after))

    fb_comment_edited['content'] = 'new content'
    gp_like_edited['to'] = [{'objectType':'group', 'alias':'@private'}]

    fb_invite = test_facebook.INVITE_OBJ
    self.assertEqual('invite', fb_invite['verb'])
    fb_rsvp = test_facebook.RSVP_YES_OBJ

    for before, after in ((fb_comment, fb_comment_edited),
                          (gp_like, gp_like_edited),
                          (fb_invite, fb_rsvp)):
      self.assertTrue(self.source.activity_changed(before, after, log=True),
                                                   '%s\n%s' % (before, after))

  def test_sources_global(self):
    self.assertEquals(facebook.Facebook, source.sources['facebook'])
    self.assertEquals(googleplus.GooglePlus, source.sources['google+'])
    self.assertEquals(instagram.Instagram, source.sources['instagram'])
    self.assertEquals(twitter.Twitter, source.sources['twitter'])

  def test_post_id(self):
    self.assertEquals('1', self.source.post_id('http://x/y/1'))
    self.assertEquals('1', self.source.post_id('http://x/y/1/'))
    self.assertIsNone(self.source.post_id('http://x/'))
    self.assertIsNone(self.source.post_id(''))

  def test_strip_html_tags(self):
    self.assertEquals('', source.strip_html_tags(''))
    self.assertEquals('foo', source.strip_html_tags('foo'))
    self.assertEquals('xyz', source.strip_html_tags(
      '<p>x<a href="l">y</a><br />z</p>'))

  def test_is_public(self):
    for obj in ({'to': [{'objectType': 'unknown'}]},
                {'to': [{'objectType': 'unknown'},
                        {'objectType': 'unknown'}]},
                {'to': [{'alias': 'xyz'},
                        {'objectType': 'unknown'}]},
               ):
      self.assertIsNone(Source.is_public(obj), `obj`)
      self.assertIsNone(Source.is_public({'object': obj}), `obj`)

    for obj in ({},
                {'privacy': 'xyz'},
                {'to': []},
                {'to': [{}]},
                {'to': [{'objectType': 'group'}]},
                {'to': [{'objectType': 'group', 'alias': '@public'}]},
                {'to': [{'objectType': 'group', 'alias': '@private'},
                        {'objectType': 'group', 'alias': '@public'}]},
                {'to': [{'alias': '@public'},
                        {'alias': '@private'}]},
               ):
      self.assertTrue(Source.is_public(obj), `obj`)
      self.assertTrue(Source.is_public({'object': obj}), `obj`)

    for obj in ({'to': [{'objectType': 'group', 'alias': '@private'}]},
                {'to': [{'objectType': 'group', 'alias': 'xyz'}]},
                {'to': [{'alias': 'xyz'}]},
                {'to': [{'alias': 'xyz'},
                        {'alias': '@private'}]},
                {'to': [{'objectType': 'group'},
                        {'alias': 'xyz'},
                        {'alias': '@private'}]},
               ):
      self.assertFalse(Source.is_public(obj), `obj`)
      self.assertFalse(Source.is_public({'object': obj}), `obj`)
