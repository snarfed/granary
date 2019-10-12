# coding=utf-8
"""Unit tests for mastodon.py.
"""
from oauth_dropins.webutil import testutil
import ujson as json

from granary import appengine_config
from granary import as2, mastodon


class MastodonTest(testutil.TestCase):

  def setUp(self):
    super(MastodonTest, self).setUp()
    self.mastodon = mastodon.Mastodon('http://foo.com', username='alice')

  def test_get_activities_defaults(self):
    self.expect_requests_get('http://foo.com/users/alice/outbox?page=true', json.dumps({
      'orderedItems': [
        {'content': 'foo bar'},
        {'content': 'bar baz'},
      ]}), headers=as2.CONNEG_HEADERS)
    self.mox.ReplayAll()

    self.assert_equals([
      {'content': 'foo bar'},
      {'content': 'bar baz'},
    ], self.mastodon.get_activities())
