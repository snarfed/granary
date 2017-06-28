# coding=utf-8
"""Unit tests for jsonfeed.py."""

from oauth_dropins.webutil import testutil

from granary.jsonfeed import activities_to_jsonfeed, jsonfeed_to_activities


class JsonFeedTest(testutil.HandlerTest):

  def test_activities_to_jsonfeed_empty(self):
      self.assert_equals({
        'version': 'https://jsonfeed.org/version/1',
        'title': 'JSON Feed',
      }, activities_to_jsonfeed([{}], {}))

  def test_activities_to_jsonfeed_extra_fields(self):
      self.assert_equals({
        'version': 'https://jsonfeed.org/version/1',
        'title': 'a something',
        'feed_url': 'http://a/feed',
        'home_page_url': 'http://a/home',
      }, activities_to_jsonfeed(
        [{}], {}, title='a something', feed_url='http://a/feed',
        home_page_url='http://a/home'))

  def test_activities_to_jsonfeed_skip_people(self):
      self.assert_equals({
        'version': 'https://jsonfeed.org/version/1',
        'title': 'JSON Feed',
      }, activities_to_jsonfeed([{
        'objectType': 'person',
        'displayName': 'somebody',
      }], {}))

  def test_jsonfeed_to_activities_empty(self):
      self.assert_equals(([], {'objectType': 'person'}),
                         jsonfeed_to_activities({}))
