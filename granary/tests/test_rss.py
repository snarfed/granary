"""Unit tests for rss.py."""
from oauth_dropins.webutil import testutil

from .. import rss


class RssTest(testutil.TestCase):

  def test_from_as1_bad_published_datetime(self):
    self.assert_multiline_in("""
<item>
  <title>my post</title>
  <link>http://perma/link</link>
  <description><![CDATA[something
""",
      rss.from_as1([{
        'url': 'http://perma/link',
        'objectType': 'article',
        'displayName': 'my post',
        'content': 'something',
        'published': '2019',
      }], feed_url='http://this'),
      ignore_blanks=True)

  def test_from_as1_unknown_mime_type(self):
    got = rss.from_as1([{
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

  def test_from_as1_published_updated_bad_type(self):
    for field in 'published', 'updated':
      got = rss.from_as1([{
        field: {'a': 3},
        'content': 'foo bar',
      }], feed_url='http://this')
      self.assertNotIn(field, got)

  def test_from_as1_hashtag(self):
    for field in 'published', 'updated':
      got = rss.from_as1([{
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

  def test_from_as1_share_string_object_with_content(self):
    got = rss.from_as1([{
      'objectType': 'activity',
      'verb': 'share',
      'object': 'https://fireburn.ru/posts/1617172734',
      'content': 'foo bar',
    }], feed_url='http://this')
    self.assertIn('foo bar', got)

  def test_from_as1_share_string_object(self):
    got = rss.from_as1([{
      'objectType': 'activity',
      'verb': 'share',
      'object': {
        'author': {
          'objectType': 'person',
          'displayName': 'Bob',
          'url': 'http://example.com/bob',
        },
        'content': 'The original post',
        'url': 'http://example.com/original/post',
        'objectType': 'article',
      },
    }], feed_url='http://this')
    self.assert_multiline_in("""
<description><![CDATA[Shared <a href="http://example.com/original/post">a post</a> by   <span class="h-card">
<a class="p-name u-url" href="http://example.com/bob">Bob</a>
</span>
The original post]]></description>
""", got, ignore_blanks=True)

  def test_from_as1_missing_objectType_verb(self):
    self.assert_multiline_in("""
<item>
<description><![CDATA[foo bar]]></description>
<author>alice@example.com (Alice)</author>
</item>

<item>
<title>a thing I wrote</title>
<link>http://read/this</link>
<description><![CDATA[its gud]]></description>
<guid isPermaLink="true">http://read/this</guid>
</item>
""", rss.from_as1([{
    'object': {
      'objectType': 'note',
      'content': 'foo bar',
      'author': {
        'displayName': 'Alice',
        'url': 'http://it/me',
        'image': 'http://my/pic.jpg',
        'email': 'alice@example.com',
      },
    },
  }, {
    'object': {
      'objectType': 'article',
      'id': 'http://my/article',
      'title': 'a thing I wrote',
      'summary': 'its gud',
      'url': 'http://read/this',
    },
  }], feed_url='http://this'), ignore_blanks=True)

  def test_from_as1_item_with_two_enclosures(self):
    got = rss.from_as1([{
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

  def test_from_as1_item_with_image_enclosure(self):
    got = rss.from_as1([{
      'objectType': 'note',
      'image': [{
        'url': 'http://pic.png',
        'mimeType': 'image/png',
      }],
    }], feed_url='http://this')
    self.assert_multiline_in('<enclosure url="http://pic.png" length="0" type="image/png"/>', got)

  def test_render_html_image(self):
    got = rss.from_as1([{
      'objectType': 'note',
      'image': ['http://pic/ture.jpeg'],
    }], feed_url='http://this')
    self.assert_multiline_in(
      '<img class="u-photo" src="http://pic/ture.jpeg" alt="" />', got)

  def test_hfeed_photo(self):
    got = rss.from_as1([], feed_url='http://this', hfeed={
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

  def test_content_html(self):
    got = rss.from_as1([{
        'objectType': 'note',
        'content': '<x>A</x> <y> <z>B C</z>',
      }], feed_url='http://this')
    self.assert_multiline_in("""\
<description><![CDATA[<x>A</x> <y> <z>B C</z>]]></description>
""", got)

  def test_title_html(self):
    got = rss.from_as1([{
        'objectType': 'article',
        'displayName': '<x>A</x> <y> <z>B C</z>',
      }], feed_url='http://this')
    self.assert_multiline_in("""\
<item>
<title>A  B C</title>
""", got)

  def test_author(self):
    got = rss.from_as1([{
        'content': 'foo bar',
        'author': {
          'objectType':'person',
          'displayName':'Mrs. Baz',
          'email': 'baz@example.com',
        },
      }], feed_url='http://this')
    self.assert_multiline_in('<author>baz@example.com (Mrs. Baz)</author>', got)

  def test_author_string_id(self):
    got = rss.from_as1([{
        'content': 'foo bar',
        'author': 'tag:bob',  # should be ignored for RSS
      }], feed_url='http://this')
    self.assertNotRegex(got, r'<author>.*</author>')

  def test_order(self):
    got = rss.from_as1([
      {'content': 'first'},
      {'content': 'second'},
    ], feed_url='http://this')
    self.assertLess(got.find('<description><![CDATA[first]]></description>'),
                    got.find('<description><![CDATA[second]]></description>'))

  def test_to_as1_title_object_type_article(self):
    self.assert_equals({
      'objectType': 'article',
      'content': 'some text',
      'displayName': 'my title',
    }, rss.to_as1(
"""\
<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0">
<channel>
  <item>
    <title>my title</title>
    <description>some text</description>
  </item>
</channel>
</rss>
""")[0]['object'])

  def test_to_as1_title_is_description_object_type_note(self):
    self.assert_equals({
      'objectType': 'note',
      'content': 'lorem ipsum foosum barsum',
    }, rss.to_as1(
"""\
<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0">
<channel>
  <item>
    <title>lorem ipsum foosum barsum</title>
    <description>lorem ipsum foosum barsum</description>
  </item>
</channel>
</rss>
""")[0]['object'])

  def test_to_as1_title_is_ellipsized_description_object_type_note(self):
    self.assert_equals({
      'objectType': 'note',
      'content': 'lorem ipsum foosum barsum',
    }, rss.to_as1(
"""\
<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0">
<channel>
  <item>
    <title>lorem ips…</title>
    <description>lorem ipsum foosum barsum</description>
  </item>
</channel>
</rss>
""")[0]['object'])

  def test_to_as1_media_content_image(self):
    """Based on Mastodon's RSS. https://github.com/snarfed/granary/issues/674"""
    self.assert_equals({
      'objectType': 'note',
      'content': 'foo bar',
      'image': [{
        'url': 'https://files.mastodon.social/abc.png',
        'mimeType': 'image/png',
        'length': 97310,
        'displayName': 'some alt text',
      }, {
        'url': 'https://files.mastodon.social/def.jpg',
      }],
    }, rss.to_as1(
"""\
<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0" xmlns:webfeeds="http://webfeeds.org/rss/1.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <item>
    <description>foo bar</description>
    <media:content url="https://files.mastodon.social/abc.png" type="image/png" fileSize="97310" medium="image">
      <media:description type="plain">some alt text</media:description>
    </media:content>
    <media:content url="https://files.mastodon.social/def.jpg" />
    </item>
</channel>
</rss>
""")[0]['object'])

  def test_to_as1_image_enclosure(self):
    self.assert_equals({
      'objectType': 'note',
      'image': [{
        'url': 'http://pic',
        'mimeType': 'image/jpeg',
      }],
    }, rss.to_as1(
"""\
<?xml version='1.0' encoding='UTF-8'?>
<rss version="2.0">
<channel>
  <item>
    <enclosure url="http://pic" type="image/jpeg" />
  </item>
</channel>
</rss>
""")[0]['object'])
