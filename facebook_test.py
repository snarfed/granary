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
  'published': '2012-03-04T18:20:37+0000',
  'updated': '2012-03-04T19:08:16+0000',
  'id': 'tag:facebook.com,2012:212038_10100176064482163',
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'actor': OBJECT['author'],
  'object': OBJECT,
  'generator': {
    'displayName': 'Facebook for Android',
    'id': 'tag:facebook.com,2012:350685531728',
    }
  }


class FacebookTest(testutil.HandlerTest):

  def setUp(self):
    super(FacebookTest, self).setUp()
    self.facebook = facebook.Facebook(self.handler)

  def test_get_activities(self):
    resp = json.dumps({'data': [
          {'id': '1_2', 'message': 'foo'},
          {'id': '3_4', 'message': 'bar'},
          ]})
    self.expect_urlfetch(facebook.API_FEED_URL % 'me', resp)
    self.mox.ReplayAll()

    self.assert_equals((
        None,
        [{'id': 'tag:facebook.com,2012:1_2',
          'object': {'content': 'foo',
                     'id': 'tag:facebook.com,2012:1_2',
                     'objectType': 'note',
                     'url': 'http://facebook.com/1/posts/2'},
          'url': 'http://facebook.com/1/posts/2',
          'verb': 'post'},
         {'id': 'tag:facebook.com,2012:3_4',
          'object': {'content': 'bar',
                     'id': 'tag:facebook.com,2012:3_4',
                     'objectType': 'note',
                     'url': 'http://facebook.com/3/posts/4'},
          'url': 'http://facebook.com/3/posts/4',
          'verb': 'post'},
         ]),
      self.facebook.get_activities())

  def test_get_activities_user_id(self):
    self.expect_urlfetch('https://graph.facebook.com/123/feed', '{}')
    self.mox.ReplayAll()
    self.assert_equals([], self.facebook.get_activities(user=123)[1])

  def test_get_activities_user_id_passes_through_access_token(self):
    self.expect_urlfetch('https://graph.facebook.com/123/feed?access_token=asdf',
                         '{"id": 123}')
    self.mox.ReplayAll()

    handler = webapp2.RequestHandler(webapp2.Request.blank('/?access_token=asdf'),
                                     webapp2.Response())
    self.facebook = facebook.Facebook(handler)
    self.facebook.get_activities(user=123)[1]

  def test_post_to_activity_full(self):
    self.assert_equals(ACTIVITY, self.facebook.post_to_activity(POST))

  def test_post_to_activity_minimal(self):
    # just test that we don't crash
    self.facebook.post_to_activity({'id': '123_456', 'message': 'asdf'})

  def test_post_to_activity_empty(self):
    # just test that we don't crash
    self.facebook.post_to_activity({})

  def test_post_to_object_full(self):
    self.assert_equals(OBJECT, self.facebook.post_to_object(POST))

  def test_post_to_object_minimal(self):
    # just test that we don't crash
    self.facebook.post_to_object({'id': '123_456', 'message': 'asdf'})

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
