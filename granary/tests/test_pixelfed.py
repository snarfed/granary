"""Unit tests for pixelfed.py."""
import copy

from oauth_dropins.webutil import testutil, util
from oauth_dropins.webutil.util import json_dumps, json_loads

from .. import mastodon, pixelfed
from . import test_mastodon


ACCOUNT = copy.deepcopy(test_mastodon.ACCOUNT)
ACCOUNT.update({
  'fields': None,
  'created_at': 1492634299.704,
})

ACTOR = copy.deepcopy(test_mastodon.ACTOR)
ACTOR['urls'] = [{'value': 'http://foo.com/@snarfed'}]

REPLY_STATUS = copy.deepcopy(test_mastodon.REPLY_STATUS)
REPLY_STATUS['in_reply_to_id'] = int(REPLY_STATUS['in_reply_to_id'])


class PixelfedTest(testutil.TestCase):

  def setUp(self):
    super(PixelfedTest, self).setUp()
    self.pixelfed = pixelfed.Pixelfed(
      test_mastodon.INSTANCE, user_id=ACCOUNT['id'], access_token='towkin')

  def test_to_as1_actor_fields_null(self):
    self.assertEqual(ACTOR, self.pixelfed.to_as1_actor(ACCOUNT))

  def test_reply_status_to_object(self):
    self.assert_equals(test_mastodon.REPLY_OBJECT,
                       self.pixelfed.status_to_object(REPLY_STATUS))

  def test_user_url(self):
    self.assert_equals('http://foo.com/bar', self.pixelfed.user_url('bar'))

  def test_status_url(self):
    self.assert_equals('http://foo.com/p/bar/123',
                       self.pixelfed.status_url('bar', 123))

  def test_get_activities_fetch_mentions(self):
    self.expect_requests_get(
      test_mastodon.INSTANCE + test_mastodon.API_TIMELINE,
      params={},
      response=[REPLY_STATUS],
      headers={'Authorization': 'Bearer towkin'},
      content_type='application/json')
    self.mox.ReplayAll()

    self.assert_equals([test_mastodon.REPLY_ACTIVITY],
                       self.pixelfed.get_activities(fetch_mentions=True))
