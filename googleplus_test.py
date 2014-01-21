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

import googleplus
from oauth_dropins import httplib2
from oauth_dropins.apiclient import discovery
from oauth_dropins.apiclient import http
from oauth_dropins import googleplus as oauth_googleplus
from webutil import testutil
from webutil import util


DISCOVERY_DOC = appengine_config.read('googleplus_api_discovery.json')

def tag_uri(name):
  return util.tag_uri('plus.google.com', name)


ACTIVITY_GP = {  # Google+
  'kind': 'plus#activity',
  'verb': 'post',
  'id': '001',
  'actor': {'id': '444', 'displayName': 'Charles'},
  'object': {
    'content': 'my post',
    'url': 'http://plus.google.com/001',
    },
  }
ACTIVITY_AS = copy.deepcopy(ACTIVITY_GP)  # ActivityStreams
ACTIVITY_AS['id'] = tag_uri('001')
ACTIVITY_AS['object']['author'] = ACTIVITY_GP['actor']
ACTIVITY_AS['object']['to'] = [{'objectType':'group', 'alias':'@public'}]

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
    'to': [{'objectType':'group', 'alias':'@public'}],
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
    'kind': 'plus#person',
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
    'kind': 'plus#person',
    'id': tag_uri('444'),
    'displayName': 'Bob',
    'url': 'https://plus.google.com/bob',
    'image': {'url': 'https://bob/picture'},
    },
  'content': 'reshared this.',
  }


ACTIVITY_GP_EXTRAS = copy.deepcopy(ACTIVITY_GP)  # Google+
ACTIVITY_GP_EXTRAS['object'].update({
  'replies': {'totalItems': 1},
  'plusoners': {'totalItems': 1},
  'resharers': {'totalItems': 1},
  })
ACTIVITY_AS_EXTRAS = copy.deepcopy(ACTIVITY_GP_EXTRAS)  # ActivityStreams
ACTIVITY_AS_EXTRAS['id'] = tag_uri('001')
ACTIVITY_AS_EXTRAS['object'].update({
    'author': ACTIVITY_GP_EXTRAS['actor'],
    'to': [{'objectType':'group', 'alias':'@public'}],
    'replies': {'totalItems': 1, 'items': [COMMENT_AS]},
    'tags': [LIKE, SHARE],
    })


class GooglePlusTest(testutil.HandlerTest):

  def setUp(self):
    super(GooglePlusTest, self).setUp()
    self.auth_entity = oauth_googleplus.GooglePlusAuth(
      key_name='my_key_name',
      user_json=json.dumps({
          'displayName': 'Bob',
          }),
      creds_json=json.dumps({
          'access_token': 'my token',
          'client_id': appengine_config.GOOGLE_CLIENT_ID,
          'client_secret': appengine_config.GOOGLE_CLIENT_SECRET,
          'refresh_token': 'my refresh token',
          'token_expiry': '',
          'token_uri': '',
          'user_agent': '',
          'invalid': '',
          }))
    self.googleplus = googleplus.GooglePlus(auth_entity=self.auth_entity)

  def tearDown(self):
    oauth_googleplus.json_service = None

  def init(self, **kwargs):
    """Sets up the API service from googleplus_test_discovery.

    Pass a requestBuilder or http kwarg to inject expected HTTP requests and
    responses.
    """
    oauth_googleplus.json_service = discovery.build_from_document(
      DISCOVERY_DOC, **kwargs)


  def test_get_comment(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.comments.get': (None, json.dumps(COMMENT_GP)) # None means 200 OK
          }))

    self.assert_equals(COMMENT_AS, self.googleplus.get_comment('234'))

  def test_get_activity(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.get': (None, json.dumps(ACTIVITY_GP))
          }))

    self.assert_equals([ACTIVITY_AS],
                       self.googleplus.get_activities(activity_id='234'))

  def test_get_activities_no_extras_to_fetch(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.list': (None, json.dumps({
                'items': [ACTIVITY_GP, ACTIVITY_GP],
                })),
          },
          # ACTIVITY_GP doesn't say there are any comments, +1s, or shares (via
          # totalItems), so we shouldn't ask for them.
          check_unexpected=True))

    got = self.googleplus.get_activities(fetch_replies=True, fetch_likes=True,
                                         fetch_shares=True)
    self.assert_equals([ACTIVITY_AS, ACTIVITY_AS], got)

  def test_get_activities_fetch_extras(self):
    self.init()
    http_seq = http.HttpMockSequence(
      [({'status': '200'}, json.dumps({'items': [item]})) for item in
       ACTIVITY_GP_EXTRAS, COMMENT_GP, PLUSONER, RESHARER])
    self.auth_entity.http = lambda: http_seq

    got = self.googleplus.get_activities(fetch_replies=True, fetch_likes=True,
                                         fetch_shares=True)
    self.assert_equals([ACTIVITY_AS_EXTRAS], got)

  # def test_get_activities_request_etag(self):
  #   self.init()
  #   http_seq = http.HttpMockSequence(
  #     [({'status': '200'}, json.dumps({'items': [item]}))])
  #   self.auth_entity.http = lambda: http_seq

  #   resp = self.googleplus.get_activities_response(
  #     fetch_replies=True, fetch_likes=True, fetch_shares=True)
  #   self.assertEquals('"my etag"', resp['etag'])

  def test_get_activities_response_etag(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.list': (httplib2.Response({'status': 200}),
                                   json.dumps({'etag': '"my etag"'})),
          }))
    resp = self.googleplus.get_activities_response(
      fetch_replies=True, fetch_likes=True, fetch_shares=True)
    self.assertEquals('"my etag"', resp['etag'])

  def test_get_activities_304_not_modified(self):
    """Requests with matching ETags return 304 Not Modified."""
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.list': (httplib2.Response({'status': 304}), '{}'),
          }))
    self.assert_equals([], self.googleplus.get_activities(
          fetch_replies=True, fetch_likes=True, fetch_shares=True))
