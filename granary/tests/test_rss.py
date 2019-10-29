# coding=utf-8
"""Unit tests for rss.py."""
from __future__ import absolute_import, unicode_literals

from granary import appengine_config
from oauth_dropins.webutil import testutil

from granary import rss


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

  def test_item_with_two_enclosures(self):
    got = rss.from_activities([{
      # 'objectType': 'article',
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
