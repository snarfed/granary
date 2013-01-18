#!/usr/bin/python
"""Unit tests for twitter.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
try:
  import json
except ImportError:
  import simplejson as json

import source
import twitter
from webutil import testutil
from webutil import util


# test data
def tag_uri(name):
  return util.tag_uri('twitter.com', name)

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
  'id': tag_uri('snarfed_org'),
  'published': '2010-05-01T21:42:43',
  'url': 'http://twitter.com/snarfed_org',
  'location': {'displayName': 'San Francisco'},
  'username': 'snarfed_org',
  'description': 'my description',
  }
TWEET = {
  'created_at': 'Wed Feb 22 20:26:41 +0000 2012',
  'id': 172417043893731329,
  'place': {
    'full_name': 'Carcassonne, Aude',
    'id': '31cb9e7ed29dbe52',
    'name': 'Carcassonne',
    'url': 'http://api.twitter.com/1/geo/id/31cb9e7ed29dbe52.json',
    },
  'geo':  {
    'type': 'Point',
    'coordinates':  [32.4004416, -98.9852672],
  },
  'user': USER,
  'entities': {
    'media': [{'media_url': 'http://p.twimg.com/AnJ54akCAAAHnfd.jpg'}],
    'urls': [{
        'expanded_url': 'http://instagr.am/p/MuW67/',
        'url': 'http://t.co/6J2EgYM',
        'indices': [43, 62],
        'display_url': 'instagr.am/p/MuW67/'
      }],
    'hashtags': [{
        'text': 'tcdisrupt',
        'indices': [32, 42]
      }],
    'user_mentions': [{
        'name': 'Twitter',
        'id_str': '783214',
        'id': 783214,
        'indices': [0, 8],
        'screen_name': 'foo'
      },
      {
        'name': 'Picture.ly',
        'id_str': '334715534',
        'id': 334715534,
        'indices': [15, 28],
        'screen_name': 'foo'
      }],
  },
  'text': '@twitter meets @seepicturely at #tcdisrupt http://t.co/6J2EgYM',
  'source': '<a href="http://choqok.gnufolks.org/" rel="nofollow">Choqok</a>',
  'in_reply_to_screen_name': 'other_user',
  'in_reply_to_status_id': 789,
  }
OBJECT = {
  'objectType': 'note',
  'author': ACTOR,
  'content': '@twitter meets @seepicturely at #tcdisrupt http://t.co/6J2EgYM',
  'id': tag_uri('172417043893731329'),
  'published': '2012-02-22T20:26:41',
  'url': 'http://twitter.com/snarfed_org/status/172417043893731329',
  'image': {'url': 'http://p.twimg.com/AnJ54akCAAAHnfd.jpg'},
  'location': {
    'displayName': 'Carcassonne, Aude',
    'id': '31cb9e7ed29dbe52',
    'url': 'https://maps.google.com/maps?q=32.4004416,-98.9852672',
    },
  'tags': [{
      'objectType': 'person',
      'id': tag_uri('foo'),
      'url': 'http://twitter.com/foo',
      'displayName': 'Twitter',
      'startIndex': 0,
      'length': 8,
      }, {
      'objectType': 'person',
      'id': tag_uri('foo'),  # same id as above, shouldn't de-dupe
      'url': 'http://twitter.com/foo',
      'displayName': 'Picture.ly',
      'startIndex': 15,
      'length': 13,
      }, {
      'objectType': 'hashtag',
      'url': 'https://twitter.com/search?q=%23tcdisrupt',
      'startIndex': 32,
      'length': 10,
      }, {
      'objectType': 'article',
      'url': 'http://instagr.am/p/MuW67/',
      'startIndex': 43,
      'length': 19,
      }],
  'attachments': [{
      'objectType': 'image',
      'image': {'url': u'http://p.twimg.com/AnJ54akCAAAHnfd.jpg'},
      }],
  }
ACTIVITY = {
  'verb': 'post',
  'published': '2012-02-22T20:26:41',
  'id': tag_uri('172417043893731329'),
  'url': 'http://twitter.com/snarfed_org/status/172417043893731329',
  'actor': ACTOR,
  'object': OBJECT,
  'title': 'Ryan Barrett: @twitter meets @seepicturely at #tcdisrupt http://t.co/6J2Eg...',
  'generator': {'displayName': 'Choqok', 'url': 'http://choqok.gnufolks.org/'},
  'context': {
    'inReplyTo' : {
      'objectType' : 'note',
      'url' : 'http://twitter.com/other_user/status/789',
      'id' : tag_uri('789'),
      }
    },
  }

ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:ostatus="http://ostatus.org/schema/1.0"
      xmlns:thr="http://purl.org/syndication/thread/1.0"
      >
<generator uri="https://github.com/snarfed/activitystreams-unofficial" version="0.1">
  activitystreams-unofficial</generator>
<id>%(request_url)s</id>
<title>User feed for Ryan Barrett</title>
<subtitle>my description</subtitle>
<logo>http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg</logo>
<updated></updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://twitter.com/snarfed_org</uri>
 <name>Ryan Barrett</name>
 <link rel="alternate" type="text/html" href="http://twitter.com/snarfed_org" />
 <link rel="avatar" href="http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg" />
</author>

<link href="http://twitter.com/snarfed_org" rel="alternate" type="text/html" />
<link href="%(request_url)s" rel="self" type="application/atom+xml" />
<!-- TODO -->
<!-- <link href="" rel="hub" /> -->
<!-- <link href="" rel="salmon" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-replies" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-mention" /> -->

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://twitter.com/snarfed_org</uri>
 <name>Ryan Barrett</name>
 <link rel="alternate" type="text/html" href="http://twitter.com/snarfed_org" />
 <link rel="avatar" href="http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg" />
</author>


  <activity:object-type>
    http://activitystrea.ms/schema/1.0/note
  </activity:object-type>
  <id>""" + tag_uri('172417043893731329') + """</id>
  <title>Ryan Barrett: @twitter meets @seepicturely at #tcdisrupt http://t.co/6J2Eg...</title>

  <content type="text/html">

@twitter meets @seepicturely at #tcdisrupt http://t.co/6J2EgYM

<p><a href=''>
  <img style='float: left' src='http://p.twimg.com/AnJ54akCAAAHnfd.jpg' />
  
</a></p>
<p></p>

  </content>

  <link rel="alternate" type="text/html" href="http://twitter.com/snarfed_org/status/172417043893731329" />
  <link rel="ostatus:conversation" href="http://twitter.com/snarfed_org/status/172417043893731329" />
  
    <link rel="ostatus:attention" href="http://twitter.com/foo" />
    <link rel="mentioned" href="http://twitter.com/foo" />
  
    <link rel="ostatus:attention" href="http://twitter.com/foo" />
    <link rel="mentioned" href="http://twitter.com/foo" />
  
    <link rel="ostatus:attention" href="https://twitter.com/search?q=%%23tcdisrupt" />
    <link rel="mentioned" href="https://twitter.com/search?q=%%23tcdisrupt" />
  
    <link rel="ostatus:attention" href="http://instagr.am/p/MuW67/" />
    <link rel="mentioned" href="http://instagr.am/p/MuW67/" />
  
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-02-22T20:26:41</published>
  <updated></updated>
  
    <thr:in-reply-to ref=\"""" + tag_uri('789') + """\"
                     href="http://twitter.com/other_user/status/789"
                     type="text/html" />
  
  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->
  <georss:point>
     
  </georss:point>
  <georss:featureName>Carcassonne, Aude</georss:featureName>
  <link rel="self" type="application/atom+xml" href="http://twitter.com/snarfed_org/status/172417043893731329" />
</entry>

</feed>
"""


class TwitterTest(testutil.HandlerTest):

  def setUp(self):
    super(TwitterTest, self).setUp()
    self.twitter = twitter.Twitter(self.handler)

  def test_get_actor(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/users/lookup.json?screen_name=foo',
      json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.twitter.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/account/verify_credentials.json',
      json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.twitter.get_actor())

  def test_get_activities(self):
    self.expect_urlfetch(
      'https://api.twitter.com/1/statuses/home_timeline.json?'
      'include_entities=true&count=0',
      json.dumps([TWEET, TWEET]))
    self.mox.ReplayAll()
    self.assert_equals((None, [ACTIVITY, ACTIVITY]),
                       self.twitter.get_activities())

  def test_get_activities_start_index_count(self):
    tweet2 = copy.deepcopy(TWEET)
    tweet2['user']['name'] = 'foo'
    activity2 = copy.deepcopy(ACTIVITY)
    activity2['actor']['displayName'] = 'foo'
    activity2['title'] = activity2['title'].replace('Ryan Barrett: ', 'foo: ')

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
