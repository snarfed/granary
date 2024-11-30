"""Unit tests for source.py."""
import copy
import re
from unittest.mock import patch

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from .. import facebook
from .. import instagram
from .. import source
from ..source import (
  html_to_text,
  INCLUDE_IF_TRUNCATED,
  INCLUDE_LINK,
  OMIT_LINK,
  Source,
)
from .. import twitter

from .test_as1 import (
  ACTIVITY,
  EVENT,
  EVENT_WITH_RSVPS,
  INVITE,
  LIKES,
  REACTIONS,
  RSVP_MAYBE,
  RSVP_NO,
  RSVP_YES,
  SHARES,
)

EVENT_ACTIVITY_WITH_RSVPS = {'object': EVENT_WITH_RSVPS}


class FakeSource(Source):
  DOMAIN = 'fake.com'
  EMBED_POST = 'foo %(url)s bar'


class FakeHTMLSource(Source):
  DOMAIN = 'fake.com'
  EMBED_POST = '%(content)s'


class SourceTest(testutil.TestCase):

  def setUp(self):
    super(SourceTest, self).setUp()
    self.source = FakeSource()
    self.mox.StubOutWithMock(self.source, 'get_activities')
    self.mox.StubOutWithMock(self.source, 'get_event')

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
    self.source.get_activities(
      user_id='author', activity_id='activity', fetch_likes=True
      ).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(REACTIONS[0], self.source.get_reaction(
      'author', 'activity', '5', 'apple'))

  def test_get_reaction_with_activity(self):
    # skips fetch
    self.assert_equals(REACTIONS[0], self.source.get_reaction(
      'author', 'activity', '5', 'apple', activity=ACTIVITY))

  def test_get_reaction_not_found(self):
    self.source.get_activities(
      user_id='author', activity_id='activity', fetch_likes=True
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

  def test_base_object_tag(self):
    self.assert_equals({
      'id': 'taggee',
      'url': 'http://fake.com/taggee',
    }, self.source.base_object({
      'objectType': 'activity',
      'verb': 'tag',
      'object': {'displayName': 'one'},
      'target': {'url': 'http://fake.com/taggee'},
    }))

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
      self.assertEqual('xy\nz', cfc(base, {'content':
                                           '<p>x<a href="l">y</a><br />z</p>'}))

      # preserve whitespace in non-HTML content, except if ignore_formatting
      for content, expected, expected_ignore in (
          ('a   b\n\nc', 'a   b\n\nc', 'a b c'),
          ('c<a&b\nhai', 'c<a&b\nhai', 'c<a&b hai'),
          ('  the<br />text ', 'the\ntext', 'the<br />text'),
          ('abc &amp; xyz', 'abc & xyz', 'abc &amp; xyz'),
      ):
        self.assertEqual(expected,
                         cfc(base, {'content': content}, ignore_formatting=False))
        self.assertEqual(expected_ignore,
                         cfc(base, {'content': content}, ignore_formatting=True))

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
        'content': '<video class="u-video" loop="loop"><a href="xyz">a video</a>'
                   '</video>Watching waves break.',
      }, strip_first_video_tag=True))

    # Odd bug triggered by specific combination of leading <span> and trailing #
    # https://github.com/snarfed/bridgy/issues/656
    self.assertEqual('2016. #',
                     cfc({'objectType': 'note'}, {'content': '<span /> 2016. #'}))
    # double check our hacky fix. (programming is the worst!)
    self.assertEqual('XY', cfc({'objectType': 'note'}, {'content': 'XY'}))

    # test stripping .u-quotation-of
    # https://github.com/snarfed/bridgy/issues/723
    self.assertEqual('Watching waves break.', cfc({'objectType': 'note'}, {'content': """
Watching  \t waves
 break.
<cite class="h-cite u-quotation-of">
  <a class="u-url" href="https://twitter.com/schnarfed/status/448205453911015425">
    A provocative statement.
  </a>
</cite>"""}, strip_quotations=True))

  def test_sources_global(self):
    self.assertEqual(facebook.Facebook, source.sources['facebook'])
    self.assertEqual(instagram.Instagram, source.sources['instagram'])
    self.assertEqual(twitter.Twitter, source.sources['twitter'])

  def test_post_id(self):
    self.assertEqual('1', self.source.post_id('http://x/y/1'))
    self.assertEqual('1', self.source.post_id('http://x/y/1/'))
    self.assertIsNone(self.source.post_id('http://x/'))
    self.assertIsNone(self.source.post_id(''))

    # test POST_ID
    FakeSource.POST_ID_RE = re.compile('^$')
    self.assertIsNone(self.source.post_id('http://x/y/1'))

    FakeSource.POST_ID_RE = re.compile('^a+$')
    self.assertIsNone(self.source.post_id('http://x/y/1'))
    self.assertEqual('aaa', self.source.post_id('http://x/y/aaa'))

  def test_embed_post_escapes_url(self):
    self.assert_equals('foo http://%3Ca%3Eb bar',
                       self.source.embed_post({'url': 'http://<a>b'}))

  def test_embed_post_escapes_html(self):
    self.assert_equals('x &gt; 2 &amp;&amp; x &lt; 7',
      FakeHTMLSource().embed_post({'content': 'x > 2 && x < 7' }))

  def test_truncate(self):
    """A bunch of tests to exercise the text shortening algorithm."""
    truncate = self.source.truncate
    self.source.TRUNCATE_TEXT_LENGTH = 140

    orig = (
      'Hey #indieweb, the coming storm of webmention Spam may not be '
      'far away. Those of us that have input fields to send webmentions '
      'manually may already be getting them')
    expected = (
      'Hey #indieweb, the coming storm of webmention Spam may not '
      'be far away. Those of us that have input fields to send… '
      'https://ben.thatmustbe.me/note/2015/1/31/1/')
    result = truncate(orig, 'https://ben.thatmustbe.me/note/2015/1/31/1/',
                      INCLUDE_LINK)
    self.assertEqual(expected, result)

    orig = (
      'Despite names,\n'
      'ind.ie&indie.vc are NOT #indieweb @indiewebcamp\n'
      'indiewebcamp.com/2014-review#Indie_Term_Re-use\n'
      '@iainspad @sashtown @thomatronic (ttk.me t4_81)')
    expected = (
      'Despite names,\n'
      'ind.ie&indie.vc are NOT #indieweb @indiewebcamp\n'
      'indiewebcamp.com/2014-review#Indie_Term_Re-use\n'
      '@iainspad @sashtown…')
    result = truncate(orig, 'http://tantek.com/1234', OMIT_LINK)
    self.assertEqual(expected, result)

    orig = expected = (
      '@davewiner I stubbed a page on the wiki for '
      'https://indiewebcamp.com/River4. Edits/improvmnts from users are '
      'welcome! @kevinmarks @julien51 @aaronpk')
    result = truncate(orig, 'https://kylewm.com/5678', INCLUDE_IF_TRUNCATED)
    self.assertEqual(expected, result)

    orig = expected = (
      'This is a long tweet with (foo.com/parenthesized-urls) and urls '
      'that wikipedia.org/Contain_(Parentheses), a url with a query '
      'string;foo.withknown.com/example?query=parameters')
    result = truncate(orig, 'https://foo.bar/', INCLUDE_IF_TRUNCATED)
    self.assertEqual(expected, result)

    orig = (
      'This is a long tweet with (foo.com/parenthesized-urls) and urls '
      'that wikipedia.org/Contain_(Parentheses), that is one charc too '
      'long:foo.withknown.com/example?query=parameters')
    expected = (
      'This is a long tweet with (foo.com/parenthesized-urls) and urls '
      'that wikipedia.org/Contain_(Parentheses), that is one charc too '
      'long…')
    result = truncate(orig, 'http://foo.com/', OMIT_LINK)
    self.assertEqual(expected, result)

    # test case-insensitive link matching
    orig = (
      'The Telegram Bot API is the best bot API ever. Everyone should '
      'learn from it, especially Matrix.org, which currently requires a '
      'particular URL structure and registration files.')
    expected = (
      'The Telegram Bot API is the best bot API ever. Everyone should learn '
      'from it, especially Matrix.org… '
      'https://unrelenting.technology/notes/2015-09-05-00-35-13')
    result = truncate(orig, 'https://unrelenting.technology/notes/2015-09-05-00-35-13',
                      INCLUDE_IF_TRUNCATED)
    self.assertEqual(expected, result)

    orig = ('Leaving this here for future reference. Turn on debug menu '
      'in Mac App Store `defaults write com.apple.appstore ShowDebugMenu '
      '-bool true`')
    expected = ('Leaving this here for future reference. Turn on debug menu '
      'in Mac App Store `defaults write com.apple.appstore ShowDebugMenu…')
    result = truncate(orig, 'http://foo.com', OMIT_LINK)
    self.assertEqual(expected, result)

    self.source.TRUNCATE_TEXT_LENGTH = 20
    self.source.TRUNCATE_URL_LENGTH = 5

    orig = 'ok http://foo.co/bar ellipsize http://foo.co/baz'
    expected = 'ok http://foo.co/bar ellipsize…'
    result = truncate(orig, 'http://foo.com', OMIT_LINK)
    self.assertEqual(expected, result)

    orig = 'too long\nextra whitespace\tbut should include url'
    expected = 'too long… http://obj.ca'
    result = truncate(orig, 'http://obj.ca', INCLUDE_LINK)
    self.assertEqual(expected, result)

    orig = expected = 'trailing slash http://www.foo.co/'
    result = truncate(orig, 'http://www.foo.co/', OMIT_LINK)
    self.assertEqual(expected, result)

  def test_postprocess_object_mentions(self):
    obj = {
      'objectType': 'note',
      'content': 'hi <a href="http://foo">@bar</a>',
    }
    obj_with_tag = {  # because postprocess_object modifies obj
      **obj,
      'tags': [{
        'objectType': 'mention',
        'url': 'http://foo',
        'displayName': '@bar',
      }],
    }

    self.assert_equals(obj, Source.postprocess_object(obj))
    self.assert_equals(obj_with_tag, Source.postprocess_object(obj, mentions=True))

  def test_postprocess_object_mention_existing_tag(self):
    obj = {
      'objectType': 'note',
      'content': 'hi <a href="http://foo">@bar</a>',
      'tags': [{
        'objectType': 'mention',
        'url': 'http://other/link',
        'displayName': '@bar',
      }],
    }
    expected = copy.deepcopy(obj)  # because postprocess_object modifies obj

    self.assert_equals(expected, Source.postprocess_object(obj))
    self.assert_equals(expected, Source.postprocess_object(obj, mentions=True))

  def test_postprocess_object_location(self):
    obj = {
      'location': {
        'latitude': -1.23,
        'longitude': 4.56,
      },
    }
    obj_with_pos = {  # because postprocess_object modifies obj
      'location': {
        'latitude': -1.23,
        'longitude': 4.56,
        'position': '-1.230000+4.560000/',
      },
    }

    self.assert_equals(obj_with_pos, Source.postprocess_object(obj_with_pos))
    self.assert_equals(obj_with_pos, Source.postprocess_object(obj))

  def test_postprocess_object_location_not_dict(self):
    obj = {
      'location': 'asdf',
    }
    self.assert_equals(obj, Source.postprocess_object(obj))

  @patch('requests.get', return_value=testutil.requests_response("""\
<html>
<head>
  <title>A poast</title>
  <meta property="og:image" content="http://pic" />
  <meta property="og:title" content="Titull" />
  <meta property="og:description" content="Descrypshun" />
</head>
</html>""", url='http://foo/bar'))
  def test_postprocess_object_first_link_to_attachment(self, mock_get):
    self.assert_equals({
      'objectType': 'note',
      'content': 'hi <a href="http://foo/bar">foo</a> <a href="http://baz">baz</a>',
      'attachments': [{
        'objectType': 'link',
        'url': 'http://foo/bar',
        'displayName': 'Titull',
        'summary': 'Descrypshun',
        'image': [{'url': 'http://pic'}],
      }],
    }, Source.postprocess_object({
      'objectType': 'note',
      'content': 'hi <a href="http://foo/bar">foo</a> <a href="http://baz">baz</a>'
    }, first_link_to_attachment=True),
    ignore=['facets'])

  def test_postprocess_object_first_link_to_attachment_no_link(self):
    self.assert_equals({
      'objectType': 'note',
      'content': 'fooey',
    }, Source.postprocess_object({
      'objectType': 'note',
      'content': 'fooey',
    }, first_link_to_attachment=True))

  @patch('requests.get', return_value=testutil.requests_response(
    status=404, url='http://foo/bar'))
  def test_postprocess_object_first_link_to_attachment_fetch_fails(self, mock_get):
    self.assert_equals({
      'objectType': 'note',
      'content': 'hi <a href="http://foo/bar">foo</a>'
    }, Source.postprocess_object({
      'objectType': 'note',
      'content': 'hi <a href="http://foo/bar">foo</a>'
    }, first_link_to_attachment=True),
    ignore=['facets'])

  def test_html_to_text_empty(self):
    self.assertEqual('', html_to_text(None))
    self.assertEqual('', html_to_text(''))
