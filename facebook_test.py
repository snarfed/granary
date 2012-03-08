#!/usr/bin/python
"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json
import mox
import urllib
import urlparse
import webapp2

import facebook
import testutil

DEFAULT_BATCH_REQUEST = urllib.urlencode(
  {'batch': facebook.API_FRIENDS_BATCH_REQUESTS % {'offset': 0, 'limit': 100}})

# test data
USER = {
  'id': '212038',
  'name': 'Ryan Barrett',
  'link': 'http://www.facebook.com/snarfed.org',
  'username': 'snarfed.org',
  'location': {'id': '123', 'name': 'San Francisco, California'},
  'updated_time': '2012-01-06T02:11:04+0000',
  'bio': 'something about me',
  }
ACTOR = {
  'displayName': 'Ryan Barrett',
  'image': {'url': 'http://graph.facebook.com/snarfed.org/picture?type=large'},
  'id': 'tag:facebook.com,2012:snarfed.org',
  'updated': '2012-01-06T02:11:04+0000',
  'url': 'http://www.facebook.com/snarfed.org',
  'username': 'snarfed.org',
  'description': 'something about me',
  'location': {'id': '123', 'displayName': 'San Francisco, California'},
  }
POST = {
  'id': '212038_10100176064482163',
  'from': {'name': 'Ryan Barrett', 'id': '212038'},
  'story': 'Ryan Barrett added a new photo.',
  'picture': 'https://fbcdn-photos-a.akamaihd.net/hphotos-ak-ash4/420582_10100176064452223_212038_41571100_37729316_s.jpg',
  'link': 'http://snarfed.org/2012-02-22_portablecontacts_for_facebook_and_twitter',
  'message': 'Checking another side project off my list. portablecontacts-unofficial is live!',
  'name': 'PortableContacts for Facebook and Twitter',
  'caption': 'snarfed.org',
  'icon': 'https://s-static.ak.facebook.com/rsrc.php/v1/yx/r/og8V99JVf8G.gif',
  'place': {
    'id': '113785468632283',
    'name': 'Lake Merced',
    'location': {
      'city': 'San Francisco',
      'state': 'CA',
      'country': 'United States',
      'latitude': 37.728193717481,
      'longitude': -122.49336423595
    }
  },
  'type': 'photo',
  'object_id': '10100176064452223',
  'application': {'name': 'Facebook for Android', 'id': '350685531728'},
  'created_time': '2012-03-04T18:20:37+0000',
  'updated_time': '2012-03-04T19:08:16+0000',
}
OBJECT = {
  'objectType': 'note',
  'author': {
    'id': 'tag:facebook.com,2012:212038',
    'displayName': 'Ryan Barrett',
    'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
    },
  'content': 'Checking another side project off my list. portablecontacts-unofficial is live!',
  'id': 'tag:facebook.com,2012:212038_10100176064482163',
  'published': '2012-03-04T18:20:37+0000',
  'updated': '2012-03-04T19:08:16+0000',
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'image': {'url': 'https://fbcdn-photos-a.akamaihd.net/hphotos-ak-ash4/420582_10100176064452223_212038_41571100_37729316_s.jpg'},
  'location': {
    'displayName': 'Lake Merced',
    'id': '113785468632283',
    'position': '+37.728194-122.493364/',
    },
  }
ACTIVITY = {
  'verb': 'post',
  'published': '2012-02-22T20:26:41',
  'id': 'tag:facebook.com,2012:snarfed_org/172417043893731329',
  'url': 'http://facebook.com/snarfed_org/status/172417043893731329',
  'actor': ACTOR,
  'object': OBJECT,
  }


class FacebookTest(testutil.HandlerTest):

  def setUp(self):
    super(FacebookTest, self).setUp()
    self.facebook = facebook.Facebook(self.handler)

  # def test_get_activities(self):
  #   batch_resp = json.dumps(
  #     [None,
  #      {'body': json.dumps({
  #             '1': {'id': '1',
  #                   'name': 'Mr. Foo',
  #                   'link': 'https://www.facebook.com/mr_foo',
  #                   },
  #             '2': {'username': 'msbar',
  #                   'name': 'Ms. Bar',
  #                   'location': {'name': 'Hometown'},
  #                   },
  #             })}])
  #   self.expect_urlfetch('https://graph.facebook.com/',
  #                        batch_resp,
  #                        method='POST',
  #                        payload=DEFAULT_BATCH_REQUEST)
  #   self.mox.ReplayAll()

  #   self.assert_equals((
  #       None,
  #       [{'id': '1',
  #         'displayName': 'Mr. Foo',
  #         'name': {'formatted': 'Mr. Foo'},
  #         'accounts': [{'domain': 'facebook.com', 'userid': '1'}],
  #         'connected': True,
  #         'relationships': ['friend'],
  #         'photos': [{'value': 'http://graph.facebook.com/1/picture?type=large'}],
  #         }, {
  #         'displayName': 'Ms. Bar',
  #         'name': {'formatted': 'Ms. Bar'},
  #         'accounts': [{'domain': 'facebook.com', 'username': 'msbar'}],
  #         'addresses': [{'formatted': 'Hometown', 'type': 'home'}],
  #         'connected': True,
  #         'relationships': ['friend'],
  #         'photos': [{'value': 'http://graph.facebook.com/msbar/picture?type=large'}],
  #         }]),
  #     self.facebook.get_activities())

  # def test_post_to_activity_full(self):
  #   self.assert_equals(ACTIVITY, self.facebook.post_to_activity(POST))

  # def test_post_to_activity_minimal(self):
  #   # just test that we don't crash
  #   self.facebook.post_to_activity({'id': 123, 'text': 'asdf'})

  # def test_post_to_activity_empty(self):
  #   # just test that we don't crash
  #   self.facebook.post_to_activity({})

  def test_post_to_object_full(self):
    self.assert_equals(OBJECT, self.facebook.post_to_object(POST))

  def test_post_to_object_minimal(self):
    # just test that we don't crash
    self.facebook.post_to_object({'id': '123_456', 'text': 'asdf'})

  def test_post_to_object_empty(self):
    self.assert_equals({}, self.facebook.post_to_object({}))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.facebook.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    actor = self.facebook.user_to_actor({'id': '212038'})
    self.assert_equals('tag:facebook.com,2012:212038', actor['id'])
    self.assert_equals('http://graph.facebook.com/212038/picture?type=large',
                       actor['image']['url'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.facebook.user_to_actor({}))
