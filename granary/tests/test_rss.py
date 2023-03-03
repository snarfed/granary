# coding=utf-8
"""Unit tests for rss.py."""
from oauth_dropins.webutil import testutil

from .. import rss


class RssTest(testutil.TestCase):

  def test_from_activities_bad_published_datetime(self):
    self.assert_multiline_in("""
<item>
  <title>my post</title>
  <link>http://perma/link</link>
  <description><![CDATA[something
""",
      rss.from_activities([{
        'url': 'http://perma/link',
        'objectType': 'article',
        'displayName': 'my post',
        'content': 'something',
        'published': '2019',
      }], feed_url='http://this'),
      ignore_blanks=True)

  def test_from_activities_unknown_mime_type(self):
    got = rss.from_activities([{
      'url': 'http://perma/link',
      'objectType': 'article',
      'displayName': 'my post',
      'attachments': [{
        'objectType': 'video',
        'stream': {'url': 'http://a/podcast.foo'},
      }],
    }], feed_url='http://this')

    self.assert_multiline_in("""
<item>
<title>my post</title>
<link>http://perma/link</link>
<description><![CDATA[
""", got, ignore_blanks=True)
    self.assert_multiline_in("""
<guid isPermaLink="true">http://perma/link</guid>
<enclosure url="http://a/podcast.foo" length="0" type=""/>
</item>""", got, ignore_blanks=True)

  def test_from_activities_published_updated_bad_type(self):
    for field in 'published', 'updated':
      got = rss.from_activities([{
        field: {'a': 3},
        'content': 'foo bar',
      }], feed_url='http://this')
      self.assertNotIn(field, got)

  def test_from_activities_hashtag(self):
    for field in 'published', 'updated':
      got = rss.from_activities([{
        'content': 'foo bar',
        'attachments': [{
          'objectType': 'audio',
          'stream': {'url': 'http://a/podcast.mp3'},
        }],
        'tags': [{
          'displayName': '#ahashtag'
        }],
      }], feed_url='http://this')
      self.assertNotIn(field, got)

  def test_from_activities_share_string_object(self):
    got = rss.from_activities([{
      'objectType': 'activity',
      'verb': 'share',
      'object': 'https://fireburn.ru/posts/1617172734',
      'content': 'foo bar',
    }], feed_url='http://this')
    # TODO: finish implementing reposts in rss
    self.assertIn('foo bar', got)

  def test_item_with_two_enclosures(self):
    got = rss.from_activities([{
      'attachments': [{
        'objectType': 'audio',
        'stream': {'url': 'http://a/podcast.mp3'},
      }, {
        'objectType': 'video',
        'stream': {'url': 'http://a/vidjo.mov'},
      }],
    }], feed_url='http://this')
    self.assert_multiline_in(
      '<enclosure url="http://a/podcast.mp3" length="0" type="audio/mpeg"/>', got)
    self.assertNotIn(
      '<enclosure url="http://a/vidjo.mov" length="0" type="video/quicktime"/>', got)

  def test_hfeed_photo(self):
    got = rss.from_activities([], feed_url='http://this', hfeed={
      'type': ['h-feed'],
      'properties': {
        'name': ['2toPonder'],
        'photo': ['https://a/photo'],
      }})
    self.assert_multiline_in("""\
<image>
  <url>https://a/photo</url>
  <title>-</title>
  <link>http://this</link>
</image>""", got)

  def test_title_html(self):
    got = rss.from_activities([{
        'objectType': 'article',
        'content': '<x>A</x> <y> <z>B C</z>',
      }], feed_url='http://this')
    self.assert_multiline_in("""\
<item>
<title>A  B C</title>
""", got)

  def test_author(self):
    got = rss.from_activities([{
        'content': 'foo bar',
        'author': {
          'objectType':'person',
          'displayName':'Mrs. Baz',
        },
      }], feed_url='http://this')
    self.assert_multiline_in('<author>- (Mrs. Baz)</author>', got)

  def test_order(self):
    got = rss.from_activities([
      {'content': 'first'},
      {'content': 'second'},
    ], feed_url='http://this')
    self.assertLess(got.find('<title>first</title>'), got.find('<title>second</title>'))
