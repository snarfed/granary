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

  # def test_get_activities(self):
  #   self.expect_urlfetch(
  #     'https://api.twitter.com/1/account/verify_credentials.json',
  #     '{"id": 9, "friends_count": 5}')
  #   self.expect_urlfetch(
  #     'https://api.twitter.com/1/friends/ids.json?user_id=9',
  #     '{"ids": [123, 456]}')
  #   self.expect_urlfetch(
  #     'https://api.twitter.com/1/users/lookup.json?user_id=123,456',
  #     json.dumps([{
  #         'id': 123,
  #         'screen_name': 'foo',
  #         'name': 'Mr. Foo',
  #         'location': 'Hometown',
  #         'url': 'http://foo.com/',
  #         'profile_image_url': 'http://foo.com/pic.jpg',
  #         }, {
  #         'id': 456,
  #         'name': 'Ms. Bar',
  #         }]))
  #   self.mox.ReplayAll()

  #   self.assert_equals(
  #       (5,
  #        [{'id': '123',
  #          'displayName': 'Mr. Foo',
  #          'name': {'formatted': 'Mr. Foo'},
  #          'accounts': [{'domain': 'twitter.com',
  #                        'userid': '123',
  #                        'username': 'foo'}],
  #          'addresses': [{'formatted': 'Hometown', 'type': 'home'}],
  #          'photos': [{'value': 'http://foo.com/pic.jpg', 'primary': 'true'}],
  #          'urls': [{'value': 'http://foo.com/', 'type': 'home'}],
  #          },
  #         {'id': '456',
  #          'displayName': 'Ms. Bar',
  #          'name': {'formatted': 'Ms. Bar'},
  #          'accounts': [{'domain': 'twitter.com', 'userid': '456'}],
  #          }]),
  #     self.twitter.get_activities())

  # def test_get_activities_user_id(self):
  #   self.expect_urlfetch(
  #     'https://api.twitter.com/1/users/lookup.json?user_id=123',
  #     '[{"id": 123}]')
  #   self.mox.ReplayAll()
  #   self.assert_equals((1, []), self.twitter.get_activities(user_id=123))

  # def test_get_activities_user_id_no_results(self):
  #   self.expect_urlfetch(
  #     'https://api.twitter.com/1/users/lookup.json?user_id=123',
  #     '[]')
  #   self.mox.ReplayAll()
  #   self.assert_equals(
  #       (0, [{'id': '139199211',
  #             'accounts': [{'domain': 'twitter.com', 'userid': '139199211'}],
  #             }]),
  #       self.twitter.get_activities(user_id=123))

  def test_get_current_user(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/account/verify_credentials.json',
      '{"id": 9, "friends_count": 5}')
    self.mox.ReplayAll()
    self.assert_equals(9, self.twitter.get_current_user())

  # def test_to_activity_id_only(self):
  #   self.assert_equals(
  #       {'id': '139199211',
  #        'accounts': [{'domain': 'twitter.com', 'userid': '139199211'}],
  #        },
  #       self.twitter.to_activity({'id': 139199211}))

  # def test_to_activity_minimal(self):
  #   self.assert_equals({
  #       'id': '139199211',
  #       'displayName': 'Ryan Barrett',
  #       'name': {'formatted': 'Ryan Barrett'},
  #       'accounts': [{'domain': 'twitter.com', 'userid': '139199211'}],
  #       },
  #     self.twitter.to_activity({
  #       'id': 139199211,
  #       'name': 'Ryan Barrett',
  #       }))

  def test_to_activity_full(self):
    self.assert_equals({
        'verb': 'post',
        'published': '2012-02-22T20:26:41',
        'id': 'tag:twitter.com,2012:snarfed_org/172417043893731329',
        'actor': {
        #   'url': 'http://twitter.com/snarfed_org',
        #   'objectType' : 'person',
        #   'id': 'tag:example.org,2011:martin',
        #   'image': {
        #     'url': 'http://example.org/martin/image',
        #     'width': 250,
        #     'height': 250
        #     },
          'displayName': 'Martin Smith'
        },
        'object': {
          'url': 'http://twitter.com/snarfed_org/status/172417043893731329',
          'id': 'tag:twitter.com,2012:snarfed_org/172417043893731329'
          },
        },
      self.twitter.to_activity({
        'contributors': None,
        'coordinates': None,
        'created_at': 'Wed Feb 22 20:26:41 +0000 2012',
        'entities': {u'hashtags': [],
                      'urls': [{u'display_url': 'snarfed.org/2012-02-22_por\u2026',
                                 'expanded_url': 'http://snarfed.org/2012-02-22_portablecontacts_for_facebook_and_twitter',
                                 'indices': [72, 92],
                                 'url': 'http://t.co/SuqMPgp3'}],
                      'user_mentions': []},
        'favorited': False,
        'geo': None,
        'id': 172417043893731329,
        'id_str': '172417043893731329',
        'in_reply_to_screen_name': None,
        'in_reply_to_status_id': None,
        'in_reply_to_status_id_str': None,
        'in_reply_to_user_id': None,
        'in_reply_to_user_id_str': None,
        'place': None,
        'possibly_sensitive': False,
        'retweet_count': 0,
        'retweeted': False,
        'source': 'web',
        'text': 'portablecontacts-unofficial: PortableContacts for Facebook and Twitter! http://t.co/SuqMPgp3',
        'truncated': False,
        'user': {'contributors_enabled': False,
                 'created_at': 'Sat May 01 21:42:43 +0000 2010',
                 'default_profile': True,
                 'default_profile_image': False,
                 'description': '',
                 'favourites_count': 0,
                 'follow_request_sent': False,
                 'followers_count': 75,
                 'following': None,
                 'friends_count': 81,
                 'geo_enabled': False,
                 'id': 139199211,
                 'id_str': '139199211',
                 'is_translator': False,
                 'lang': 'en',
                 'listed_count': 1,
                 'location': 'San Francisco',
                 'name': 'Ryan Barrett',
                 'notifications': None,
                 'profile_background_color': 'C0DEED',
                 'profile_background_image_url': 'http://a0.twimg.com/images/themes/theme1/bg.png',
                 'profile_background_image_url_https': 'https://si0.twimg.com/images/themes/theme1/bg.png',
                 'profile_background_tile': False,
                 'profile_image_url': 'http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg',
                 'profile_image_url_https': 'https://si0.twimg.com/profile_images/866165047/ryan_normal.jpg',
                 'profile_link_color': '0084B4',
                 'profile_sidebar_border_color': 'C0DEED',
                 'profile_sidebar_fill_color': 'DDEEF6',
                 'profile_text_color': '333333',
                 'profile_use_background_image': True,
                 'protected': False,
                 'screen_name': 'snarfed_org',
                 'show_all_inline_media': False,
                 'statuses_count': 110,
                 'time_zone': 'Pacific Time (US & Canada)',
                 'url': 'http://snarfed.org/',
                 'utc_offset': -28800,
                 'verified': False,
                 },
        }))
