"""Unit tests for googleplus.py.

See apiclient/http.py for details on using RequestMockBuilder to mock out Google
API calls. (This is the current doc on apiclient mocks, but it doesn't mention
RequestMockBuilder:
https://developers.google.com/api-client-library/python/guide/mocks )
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import json

from oauth_dropins import appengine_config
appengine_config.GOOGLE_CLIENT_ID = 'my client id'
appengine_config.GOOGLE_CLIENT_SECRET = 'my client secret'

from oauth_dropins.apiclient import discovery
from oauth_dropins.apiclient import http
from oauth_dropins import googleplus as oauth_googleplus
import googleplus
from webutil import testutil
from webutil import util


def tag_uri(name):
  return util.tag_uri('plus.google.com', name)


COMMENT_GP = {  # Google+
  'kind': 'plus#comment',
  'verb': 'post',
  'id': '888',
  'actor': {'id': '777', 'displayName': 'Eve'},
  'object': {'content': 'my content'},
  'inReplyTo': [{'url': 'http://post/url'}],
  }
COMMENT_AS = copy.deepcopy(COMMENT_GP)
COMMENT_AS.update({  # ActivityStreams
    'author': COMMENT_AS.pop('actor'),
    'content': 'my content',
    'id': tag_uri('888'),
    'url': 'http://post/url',
  })
PLUSONER = {  # Google+
  'kind': 'plus#person',
  'id': '222',
  'displayName': 'Alice',
  'url': 'https://profiles.google.com/alice',
  'image': {'url': 'https://alice/picture'},
  }
LIKE = {  # ActivityStreams
  'id': tag_uri('001_liked_by_222'),
  'url': 'http://plus.google.com/001',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'http://plus.google.com/001'},
  'author': {
    'id': tag_uri('222'),
    'displayName': 'Alice',
    'url': 'https://profiles.google.com/alice',
    'image': {'url': 'https://alice/picture'},
    },
  'content': '+1ed this.',
  }
RESHARER = {  # Google+
  'kind': 'plus#person',
  'id': '444',
  'displayName': 'Bob',
  'url': 'https://plus.google.com/bob',
  'image': {'url': 'https://bob/picture'},
  }
SHARE = {  # ActivityStreams
  'id': tag_uri('001_shared_by_444'),
  'url': 'http://plus.google.com/001',
  'objectType': 'activity',
  'verb': 'share',
  'object': {'url': 'http://plus.google.com/001'},
  'author': {
    'id': '444',
    'displayName': 'Bob',
    'url': 'https://plus.google.com/bob',
    'image': {'url': 'https://bob/picture'},
    },
  'content': 'reshared this.',
  'published': '2013-02-24T20:26:41',
  }


class GooglePlusTest(testutil.HandlerTest):

  def setUp(self):
    super(GooglePlusTest, self).setUp()
    self.googleplus = googleplus.GooglePlus(
      auth_entity=oauth_googleplus.GooglePlusAuth(
        key_name='my_key_name',
        user_json=json.dumps({}),
        creds_json=json.dumps({
        'access_token': 'my token',
        'client_id': appengine_config.GOOGLE_CLIENT_ID,
        'client_secret': appengine_config.GOOGLE_CLIENT_SECRET,
        'refresh_token': 'my refresh token',
        'token_expiry': '',
        'token_uri': '',
        'user_agent': '',
        'invalid': '',
        })))

  def tearDown(self):
    oauth_googleplus.json_service = None

  def test_get_comment(self):
    oauth_googleplus.json_service = discovery.build(
      'plus', 'v1', requestBuilder=http.RequestMockBuilder({
          'plus.comments.get': (None, json.dumps(COMMENT_GP)) # None means 200 OK
          }))

    self.assert_equals(COMMENT_AS, self.googleplus.get_comment('234'))

  # def test_get_like_not_found(self):
  #   self.expect_urlopen('https://graph.googleplus.com/000', json.dumps(POST))
  #   self.mox.ReplayAll()
  #   self.assert_equals(None, self.googleplus.get_like('123', '000', '999'))

  # def test_get_like_no_activity(self):
  #   self.expect_urlopen('https://graph.googleplus.com/000', '{}')
  #   self.mox.ReplayAll()
  #   self.assert_equals(None, self.googleplus.get_like('123', '000', '683713'))
