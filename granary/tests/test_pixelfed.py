"""Unit tests for pixelfed.py."""
import copy
from unittest.mock import patch

from webutil import testutil, util
from webutil.testutil import requests_response
from webutil.util import json_dumps, json_loads

from .. import mastodon, pixelfed
from . import test_mastodon


ACCOUNT = {
  **test_mastodon.ACCOUNT,
  'fields': None,
  'created_at': 1492634299.704,
}
ACTOR = {
  **test_mastodon.ACTOR,
  'id': 'http://foo.com/users/snarfed',
  'urls': [{'value': 'http://foo.com/@snarfed'}],
}
REPLY_STATUS = {
  **test_mastodon.REPLY_STATUS,
  'in_reply_to_id': int(test_mastodon.REPLY_STATUS['in_reply_to_id']),
}
REPLY_OBJECT = copy.deepcopy(test_mastodon.REPLY_OBJECT)
REPLY_OBJECT['author']['id'] = 'http://foo.com/users/snarfed'
REPLY_ACTIVITY = copy.deepcopy(test_mastodon.REPLY_ACTIVITY)
REPLY_ACTIVITY['actor']['id'] = 'http://foo.com/users/snarfed'
REPLY_ACTIVITY['object'] = REPLY_OBJECT


class PixelfedTest(testutil.TestCase):

  def setUp(self):
    super(PixelfedTest, self).setUp()
    self.pixelfed = pixelfed.Pixelfed(
      test_mastodon.INSTANCE, user_id=ACCOUNT['id'], access_token='towkin')

  def test_to_as1_actor_fields_null(self):
    self.assertEqual(ACTOR, self.pixelfed.to_as1_actor(ACCOUNT))

  def test_reply_status_to_object(self):
    self.assert_equals(REPLY_OBJECT, self.pixelfed.status_to_object(REPLY_STATUS))

  def test_user_url(self):
    self.assert_equals('http://foo.com/bar', self.pixelfed.user_url('bar'))

  def test_status_url(self):
    self.assert_equals('http://foo.com/p/bar/123',
                       self.pixelfed.status_url('bar', 123))

  @patch.object(util.session, 'get',
               return_value=requests_response([REPLY_STATUS]))
  def test_get_activities_fetch_mentions(self, mock_get):
    self.assert_equals([REPLY_ACTIVITY],
                       self.pixelfed.get_activities(fetch_mentions=True))
    self.assertEqual(test_mastodon.INSTANCE + test_mastodon.API_TIMELINE,
                     mock_get.call_args.args[0])
    self.assertEqual('Bearer towkin',
                     mock_get.call_args.kwargs['headers']['Authorization'])

  def test_actor_id(self):
    local_user = {
      'id': '123',
      'url': 'https://foo.com/alice',  # self.pixelfed.instance is https://foo.com
      'username': 'alice',
      'acct': 'alice',
    }
    self.assertEqual('https://foo.com/users/alice',
                     self.pixelfed.actor_id(local_user))

    remote_user = {
      'id': '456',
      'url': 'https://oth.er/users/bob',
      'username': 'bob',
      'acct': 'bob@oth.er',
    }
    self.assertEqual('https://oth.er/users/bob',
                     self.pixelfed.actor_id(remote_user))

    self.assertIsNone(self.pixelfed.actor_id({}))

