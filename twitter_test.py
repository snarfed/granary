#!/usr/bin/python
"""Unit tests for twitter.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json

import source
from webutil import testutil
import twitter


# test data
USER = {
  'created_at': 'Sat May 01 21:42:43 +0000 2010',
  'description': 'my description',
  'location': 'San Francisco',
  'name': 'Ryan Barrett',
  'profile_image_url': 'http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg',
  'screen_name': 'snarfed_org',
  }
ACTOR = {
  'displayName': 'Ryan Barrett',
  'image': {
    'url': 'http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg',
    },
  'id': 'tag:twitter.com,2012:snarfed_org',
  'published': '2010-05-01T21:42:43',
  'url': 'http://twitter.com/snarfed_org',
  'location': {'displayName': 'San Francisco'},
  'username': 'snarfed_org',
  'description': 'my description',
  }
TWEET = {
  'created_at': 'Wed Feb 22 20:26:41 +0000 2012',
  'id': 172417043893731329,
  'place': {'full_name': 'Carcassonne, Aude',
            'id': '31cb9e7ed29dbe52',
            'name': 'Carcassonne',
            'url': 'http://api.twitter.com/1/geo/id/31cb9e7ed29dbe52.json',
            },
  'text': 'portablecontacts-unofficial: PortableContacts for Facebook and Twitter! http://t.co/SuqMPgp3',
  'user': USER,
  'entities': {'media': [{'media_url': 'http://p.twimg.com/AnJ54akCAAAHnfd.jpg'}]},
  'source': '<a href="http://choqok.gnufolks.org/" rel="nofollow">Choqok</a>',
  }
OBJECT = {
  'objectType': 'note',
  'author': ACTOR,
  'content': 'portablecontacts-unofficial: PortableContacts for Facebook and Twitter! http://t.co/SuqMPgp3',
  'id': 'tag:twitter.com,2012:172417043893731329',
  'published': '2012-02-22T20:26:41',
  'url': 'http://twitter.com/snarfed_org/status/172417043893731329',
  'image': {'url': 'http://p.twimg.com/AnJ54akCAAAHnfd.jpg'},
  'location': {
    'displayName': 'Carcassonne, Aude',
    'id': '31cb9e7ed29dbe52',
    'url': 'http://api.twitter.com/1/geo/id/31cb9e7ed29dbe52.json',
    },
  }
ACTIVITY = {
  'verb': 'post',
  'published': '2012-02-22T20:26:41',
  'id': 'tag:twitter.com,2012:172417043893731329',
  'url': 'http://twitter.com/snarfed_org/status/172417043893731329',
  'actor': ACTOR,
  'object': OBJECT,
  'generator': {'displayName': 'Choqok', 'url': 'http://choqok.gnufolks.org/'}
  }


class TwitterTest(testutil.HandlerTest):

  def setUp(self):
    super(TwitterTest, self).setUp()
    self.twitter = twitter.Twitter(self.handler)

  def test_get_activities(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/statuses/home_timeline.json?'
      'include_entities=true&count=0',
      json.dumps([TWEET, TWEET]))
    self.mox.ReplayAll()
    self.assert_equals((None, [ACTIVITY, ACTIVITY]),
                       self.twitter.get_activities())

  def test_get_activities_start_index_count(self):
    tweet2 = dict(TWEET)
    tweet2['user']['name'] = 'foo'
    activity2 = dict(ACTIVITY)
    activity2['actor']['displayName'] = 'foo'

    self.expect_urlfetch(
      'https://api.twitter.com/1/statuses/home_timeline.json?'
      'include_entities=true&count=2',
      json.dumps([TWEET, tweet2]))
    self.mox.ReplayAll()

    got = self.twitter.get_activities(start_index=1, count=1)
    self.assert_equals((None, [activity2]), got)

  def test_get_activities_activity_id(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/statuses/show.json?id=000&include_entities=true',
      json.dumps(TWEET))
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals(
      (1, [ACTIVITY]),
      self.twitter.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_self(self):
    self.expect_urlfetch('https://api.twitter.com/1/statuses/user_timeline.json?'
                         'include_entities=true&count=0',
                         '[]')
    self.mox.ReplayAll()

    self.assert_equals((None, []),
                       self.twitter.get_activities(group_id=source.SELF))

  def test_tweet_to_activity_full(self):
    self.assert_equals(ACTIVITY, self.twitter.tweet_to_activity(TWEET))

  def test_tweet_to_activity_minimal(self):
    # just test that we don't crash
    self.twitter.tweet_to_activity({'id': 123, 'text': 'asdf'})

  def test_tweet_to_activity_empty(self):
    # just test that we don't crash
    self.twitter.tweet_to_activity({})

  def test_tweet_to_object_full(self):
    self.assert_equals(OBJECT, self.twitter.tweet_to_object(TWEET))

  def test_tweet_to_object_minimal(self):
    # just test that we don't crash
    self.twitter.tweet_to_object({'id': 123, 'text': 'asdf'})

  def test_tweet_to_object_empty(self):
    self.assert_equals({}, self.twitter.tweet_to_object({}))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.twitter.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    # just test that we don't crash
    self.twitter.user_to_actor({'screen_name': 'snarfed_org'})

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.twitter.user_to_actor({}))
