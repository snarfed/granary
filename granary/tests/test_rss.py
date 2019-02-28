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
  <description>something</description>
  <guid isPermaLink="true">http://perma/link</guid>
</item>""",
      rss.from_activities([{
        'url': 'http://perma/link',
        'objectType': 'article',
        'displayName': 'my post',
        'content': 'something',
        'published': '2019',
      }], feed_url='http://this'),
      ignore_blanks=True)

  def test_from_activities_unknown_mime_type(self):
    self.assert_multiline_in("""
<item>
<title>my post</title>
<link>http://perma/link</link>
<guid isPermaLink="true">http://perma/link</guid>
<enclosure url="http://a/podcast.foo" type=""/>
</item>""",
      rss.from_activities([{
        'url': 'http://perma/link',
        'objectType': 'article',
        'displayName': 'my post',
        'attachments': [{
          'objectType': 'video',
          'stream': {'url': 'http://a/podcast.foo'},
        }],
      }], feed_url='http://this'),
      ignore_blanks=True)
