#!/usr/bin/python
"""Unit tests for twitter.py.

TODO: test for null values, e.g. for utc_offset
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json

import testutil
import twitter


class TwitterTest(testutil.HandlerTest):

  def setUp(self):
    super(TwitterTest, self).setUp()
    self.twitter = twitter.Twitter(self.handler)

  def test_get_activities(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/account/verify_credentials.json',
      '{"id": 9, "friends_count": 5}')
    self.expect_urlfetch(
      'https://api.twitter.com/1/friends/ids.json?user_id=9',
      '{"ids": [123, 456]}')
    self.expect_urlfetch(
      'https://api.twitter.com/1/users/lookup.json?user_id=123,456',
      json.dumps([{
          'id': 123,
          'screen_name': 'foo',
          'name': 'Mr. Foo',
          'location': 'Hometown',
          'url': 'http://foo.com/',
          'profile_image_url': 'http://foo.com/pic.jpg',
          }, {
          'id': 456,
          'name': 'Ms. Bar',
          }]))
    self.mox.ReplayAll()

    self.assert_equals(
        (5,
         [{'id': '123',
           'displayName': 'Mr. Foo',
           'name': {'formatted': 'Mr. Foo'},
           'accounts': [{'domain': 'twitter.com',
                         'userid': '123',
                         'username': 'foo'}],
           'addresses': [{'formatted': 'Hometown', 'type': 'home'}],
           'photos': [{'value': 'http://foo.com/pic.jpg', 'primary': 'true'}],
           'urls': [{'value': 'http://foo.com/', 'type': 'home'}],
           },
          {'id': '456',
           'displayName': 'Ms. Bar',
           'name': {'formatted': 'Ms. Bar'},
           'accounts': [{'domain': 'twitter.com', 'userid': '456'}],
           }]),
      self.twitter.get_activities())

  def test_get_activities_user_id(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/users/lookup.json?user_id=123',
      '[{"id": 123}]')
    self.mox.ReplayAll()
    self.assert_equals((1, []), self.twitter.get_activities(user_id=123))

  def test_get_activities_user_id_no_results(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/users/lookup.json?user_id=123',
      '[]')
    self.mox.ReplayAll()
    self.assert_equals(
        (0, [{'id': '139199211',
              'accounts': [{'domain': 'twitter.com', 'userid': '139199211'}],
              }]),
        self.twitter.get_activities(user_id=123))

  def test_get_current_user(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/account/verify_credentials.json',
      '{"id": 9, "friends_count": 5}')
    self.mox.ReplayAll()
    self.assert_equals(9, self.twitter.get_current_user())

  def test_to_activity_id_only(self):
    self.assert_equals(
        {'id': '139199211',
         'accounts': [{'domain': 'twitter.com', 'userid': '139199211'}],
         },
        self.twitter.to_activity({'id': 139199211}))

  def test_to_activity_minimal(self):
    self.assert_equals({
        'id': '139199211',
        'displayName': 'Ryan Barrett',
        'name': {'formatted': 'Ryan Barrett'},
        'accounts': [{'domain': 'twitter.com', 'userid': '139199211'}],
        },
      self.twitter.to_activity({
        'id': 139199211,
        'name': 'Ryan Barrett',
        }))

  def test_to_activity_full(self):
    self.assert_equals({
        'id': '139199211',
        'displayName': 'Ryan Barrett',
        'name': {'formatted': 'Ryan Barrett'},
        'accounts': [{'domain': 'twitter.com',
                      'userid': '139199211',
                      'username': 'snarfed_org',
                      }],
        'addresses': [{'formatted': 'San Francisco, CA',
                       'type': 'home',
                       }],
        'published': '2007-05-23T06:01:13',
        'photos': [{'value': 'http://a1.twimg.com/profile_images/866165047/ryan_normal.jpg',
                    'primary': 'true',
                    }],
        'urls': [{'value': 'http://snarfed.org/',
                  'type': 'home',
                  }],
        'utcOffset': '-08:00',
        'note': 'something about me',
        },
      self.twitter.to_activity({
          'description': 'something about me',
          'id': 139199211,
          'id_str': '139199211',
          'location': 'San Francisco, CA',
          'name': 'Ryan Barrett',
          'profile_image_url': 'http://a1.twimg.com/profile_images/866165047/ryan_normal.jpg',
          'screen_name': 'snarfed_org',
          'created_at': 'Wed May 23 06:01:13 +0000 2007',
          'url': 'http://snarfed.org/',
          'utc_offset': -28800,
          }))
