"""Unit tests for twitter.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import json
import mox

import source
import twitter
from webutil import testutil
from webutil import util


# test data
def tag_uri(name):
  return util.tag_uri('twitter.com', name)

USER = {  # Twitter
  'created_at': 'Sat May 01 21:42:43 +0000 2010',
  'description': 'my description',
  'location': 'San Francisco',
  'name': 'Ryan Barrett',
  'profile_image_url': 'http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg',
  'screen_name': 'snarfed_org',
  }
ACTOR = {  # ActivityStreams
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
TWEET = {  # Twitter
  'created_at': 'Wed Feb 22 20:26:41 +0000 2012',
  'id_str': '100',
  'id': -1,  # we should always use id_str
  'place': {
    'full_name': 'Carcassonne, Aude',
    'id': '31cb9e7ed29dbe52',
    'name': 'Carcassonne',
    'url': 'http://api.twitter.com/1.1/geo/id/31cb9e7ed29dbe52.json',
    },
  'geo':  {
    'type': 'Point',
    'coordinates':  [32.4004416, -98.9852672],
  },
  'user': USER,
  'entities': {
    'media': [{
        'media_url': 'http://p.twimg.com/picture1',
        'url': 'http://t.co/picture',
        'expanded_url': 'http://the/picture1',
        'display_url': 'http://pic.twitter.com/2',
        'indices': [80, 99],
        }, {
        'media_url': 'http://p.twimg.com/picture2',
        'expanded_url': 'http://the/picture2',
        'display_url': 'http://pic.twitter.com/2',
        }],
    'urls': [{
        'expanded_url': 'http://first/link/',
        'url': 'http://t.co/6J2EgYM',
        'indices': [46, 65],
        'display_url': 'first'
        }, {
        'expanded_url': 'http://instagr.am/p/MuW67/',
        'url': 'http://t.co/X',
        'indices': [66, 79],
        'display_url': 'instagr.am/p/MuW67'
      }],
    'hashtags': [{
        'text': 'tcdisrupt',
        'indices': [32, 42]
      }],
    'user_mentions': [{
        'name': 'Twitter',
        'id_str': '783214',
        'id': -1,  # we should always use id_str
        'indices': [0, 8],
        'screen_name': 'foo'
      },
      {
        'name': 'Picture.ly',
        'id_str': '334715534',
        'id': -1,
        'indices': [15, 28],
        'screen_name': 'foo'
      }],
  },
  'text': '@twitter meets @seepicturely at #tcdisrupt <3 http://t.co/6J2EgYM http://t.co/X http://t.co/picture',
  'source': '<a href="http://choqok.gnufolks.org/" rel="nofollow">Choqok</a>',
  'in_reply_to_screen_name': 'other_user',
  'in_reply_to_status_id': 789,
  }
OBJECT = {  # ActivityStreams
  'objectType': 'note',
  'author': ACTOR,
  'content': '@twitter meets @seepicturely at #tcdisrupt <3 first instagr.am/p/MuW67 [picture]',
  'id': tag_uri('100'),
  'published': '2012-02-22T20:26:41',
  'url': 'http://twitter.com/snarfed_org/status/100',
  'image': {'url': 'http://p.twimg.com/picture1'},
  'location': {
    'displayName': 'Carcassonne, Aude',
    'id': '31cb9e7ed29dbe52',
    'url': 'https://maps.google.com/maps?q=32.4004416,-98.9852672',
    },
  'tags': [{
      'objectType': 'image',
      'url': 'http://p.twimg.com/picture1',
      'displayName': '[picture]',
      'startIndex': 71,
      'length': 9,
      }, {
      'objectType': 'image',
      'url': 'http://p.twimg.com/picture2',
      'displayName': '[picture]',
      }, {
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
      'url': 'http://first/link/',
      'displayName': 'first',
      'startIndex': 46,
      'length': 5,
      }, {
      'objectType': 'article',
      'url': 'http://instagr.am/p/MuW67/',
      'displayName': 'instagr.am/p/MuW67',
      'startIndex': 52,
      'length': 18,
      }],
  'attachments': [{
      'objectType': 'image',
      'image': {'url': u'http://p.twimg.com/picture1'},
      }, {
      'objectType': 'image',
      'image': {'url': u'http://p.twimg.com/picture2'},
      }],
  }
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-02-22T20:26:41',
  'id': tag_uri('100'),
  'url': 'http://twitter.com/snarfed_org/status/100',
  'actor': ACTOR,
  'object': OBJECT,
  'title': 'Ryan Barrett: @twitter meets @seepicturely at #tcdisrupt <3 first instagr.am/p/MuW67 [picture]',
  'generator': {'displayName': 'Choqok', 'url': 'http://choqok.gnufolks.org/'},
  'context': {
    'inReplyTo' : [{
      'objectType' : 'note',
      'url' : 'http://twitter.com/other_user/status/789',
      'id' : tag_uri('789'),
      }]
    },
  }


# This is the original tweet and reply chain:
# 100 (snarfed_org) -- 200 (alice) -- 400 (snarfed_org) -- 500 (alice)
#                   \_ 300 (bob)
REPLIES_TO_SNARFED = {'statuses': [{  # Twitter
      'id_str': '200',
      'user': {'screen_name': 'alice'},
      'text': 'reply 200',
      'in_reply_to_status_id_str': '100',
      }, {
      'id_str': '300',
      'user': {'screen_name': 'bob'},
      'text': 'reply 300',
      'in_reply_to_status_id_str': '100',
      }, {
      'id_str': '500',
      'user': {'screen_name': 'alice'},
      'text': 'reply 500',
      'in_reply_to_status_id_str': '400',
      }]}
REPLIES_TO_ALICE = {'statuses': [{
      'id_str': '400',
      'user': {'screen_name': 'snarfed_org'},
      'text': 'reply 400',
      'in_reply_to_status_id_str': '200',
      }]}
REPLIES_TO_BOB = {'statuses': []}

ACTIVITY_WITH_REPLIES = copy.deepcopy(ACTIVITY)  # ActivityStreams
ACTIVITY_WITH_REPLIES['object']['replies'] = {
  'totalItems': 4,
  'items': [{
      'objectType': 'note',
      'id': tag_uri('200'),
      'author': {
        'id': 'tag:twitter.com:alice',
        'username': 'alice',
        'url': 'http://twitter.com/alice',
        },
      'content': 'reply 200',
      'url': 'http://twitter.com/alice/status/200',
      }, {
      'objectType': 'note',
      'id': tag_uri('300'),
      'author': {
        'id': 'tag:twitter.com:bob',
        'username': 'bob',
        'url': 'http://twitter.com/bob',
        },
      'content': 'reply 300',
      'url': 'http://twitter.com/bob/status/300',
      }, {
      'objectType': 'note',
      'id': tag_uri('400'),
      'author': {
        'id': 'tag:twitter.com:snarfed_org',
        'username': 'snarfed_org',
        'url': 'http://twitter.com/snarfed_org',
        },
      'content': 'reply 400',
      'url': 'http://twitter.com/snarfed_org/status/400',
      }, {
      'objectType': 'note',
      'id': tag_uri('500'),
      'author': {
        'id': 'tag:twitter.com:alice',
        'username': 'alice',
        'url': 'http://twitter.com/alice',
        },
      'content': 'reply 500',
      'url': 'http://twitter.com/alice/status/500',
      }],
  }

RETWEETS = [{  # Twitter
    'created_at': 'Wed Feb 24 20:26:41 +0000 2013',
    'id_str': '123',
    'id': -1,  # we should always use id_str
    'user': {
      'name': 'Alice',
      'profile_image_url': 'http://alice/picture',
      'screen_name': 'alizz',
      },
    'retweeted_status': {
      'id_str': '333',
      'id': -1,
      'user': {'screen_name': 'foo'},
      },
  }, {
    'created_at': 'Wed Feb 26 20:26:41 +0000 2013',
    'id_str': '456',
    'id': -1,
    'user': {
      'name': 'Bob',
      'profile_image_url': 'http://bob/picture',
      'screen_name': 'bobbb',
      },
    'retweeted_status': {
      'id_str': '666',
      'id': -1,
      'user': {'screen_name': 'bar'},
      },
    # we replace the content, so this should be stripped
    'entities': {
      'user_mentions': [{
          'name': 'foo',
          'id_str': '783214',
          'indices': [0, 3],
          'screen_name': 'foo',
          }],
      },
    },
]
TWEET_WITH_RETWEETS = copy.deepcopy(TWEET)
TWEET_WITH_RETWEETS['retweets'] = RETWEETS
SHARES = [{  # ActivityStreams
    'id': tag_uri('123'),
    'url': 'http://twitter.com/alizz/status/123',
    'objectType': 'activity',
    'verb': 'share',
    'object': {'url': 'http://twitter.com/foo/status/333'},
    'author': {
      'id': 'tag:twitter.com:alizz',
      'username': 'alizz',
      'displayName': 'Alice',
      'url': 'http://twitter.com/alizz',
      'image': {'url': 'http://alice/picture'},
      },
    'content': '<a href="http://twitter.com/alizz/status/123">retweeted this.</a>',
    'published': '2013-02-24T20:26:41',
    }, {
    'id': tag_uri('456'),
    'url': 'http://twitter.com/bobbb/status/456',
    'objectType': 'activity',
    'verb': 'share',
    'object': {'url': 'http://twitter.com/bar/status/666'},
    'author': {
      'id': 'tag:twitter.com:bobbb',
      'username': 'bobbb',
      'displayName': 'Bob',
      'url': 'http://twitter.com/bobbb',
      'image': {'url': 'http://bob/picture'},
      },
    'content': '<a href="http://twitter.com/bobbb/status/456">retweeted this.</a>',
    'published': '2013-02-26T20:26:41',
    }]
OBJECT_WITH_SHARES = copy.deepcopy(OBJECT)
OBJECT_WITH_SHARES['tags'] += SHARES
ACTIVITY_WITH_SHARES = copy.deepcopy(ACTIVITY)
ACTIVITY_WITH_SHARES['object'] = OBJECT_WITH_SHARES
FAVORITE_EVENT = {  # Twitter
  'event' : 'favorite',
  'created_at' : 'Fri Dec 27 17:25:55 +0000 2013',
  'source': {
    'id_str': '789',
    'screen_name': 'eve',
  },
  'target': USER,
  'target_object' : TWEET,
}
LIKE = {  # ActivityStreams
  'id': tag_uri('100_favorited_by_789'),
  'url': 'http://twitter.com/snarfed_org/status/100',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'http://twitter.com/snarfed_org/status/100'},
  'author': {
    'id': tag_uri('eve'),
    'username': 'eve',
    'url': 'http://twitter.com/eve',
    },
  'content': 'favorited this.',
  'published': '2013-12-27T17:25:55',
  }

ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:georss="http://www.georss.org/georss"
      xmlns:ostatus="http://ostatus.org/schema/1.0"
      xmlns:thr="http://purl.org/syndication/thread/1.0"
      >
<generator uri="https://github.com/snarfed/activitystreams-unofficial" version="0.1">
  activitystreams-unofficial</generator>
<id>http://localhost/</id>
<title>User feed for Ryan Barrett</title>

<subtitle>my description</subtitle>

<logo>http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg</logo>
<updated>2012-02-22T20:26:41</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://twitter.com/snarfed_org</uri>
 <name>Ryan Barrett</name>
</author>

<link href="http://twitter.com/snarfed_org" rel="alternate" type="text/html" />
<link rel="avatar" href="http://a0.twimg.com/profile_images/866165047/ryan_normal.jpg" />
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
</author>

  <activity:object-type>
    http://activitystrea.ms/schema/1.0/note
  </activity:object-type>
  <id>""" + tag_uri('100') + """</id>
  <title>Ryan Barrett: @twitter meets @seepicturely at #tcdisrupt &lt;3 first instagr.am/p/MuW67 [picture]</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

@twitter meets @seepicturely at #tcdisrupt &lt;3 first instagr.am/p/MuW67 [picture]

<p><a href=''>
  <img style='float: left' src='http://p.twimg.com/picture1' /><br />
  </a><br />

</p>
<p></p>

<p><a href=''>
  <img style='float: left' src='http://p.twimg.com/picture2' /><br />
  </a><br />

</p>
<p></p>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="http://twitter.com/snarfed_org/status/100" />
  <link rel="ostatus:conversation" href="http://twitter.com/snarfed_org/status/100" />

    <link rel="ostatus:attention" href="http://p.twimg.com/picture1" />
    <link rel="mentioned" href="http://p.twimg.com/picture1" />

    <link rel="ostatus:attention" href="http://p.twimg.com/picture2" />
    <link rel="mentioned" href="http://p.twimg.com/picture2" />

    <link rel="ostatus:attention" href="http://twitter.com/foo" />
    <link rel="mentioned" href="http://twitter.com/foo" />

    <link rel="ostatus:attention" href="http://twitter.com/foo" />
    <link rel="mentioned" href="http://twitter.com/foo" />

    <link rel="ostatus:attention" href="https://twitter.com/search?q=%%23tcdisrupt" />
    <link rel="mentioned" href="https://twitter.com/search?q=%%23tcdisrupt" />

    <link rel="ostatus:attention" href="http://first/link/" />
    <link rel="mentioned" href="http://first/link/" />

    <link rel="ostatus:attention" href="http://instagr.am/p/MuW67/" />
    <link rel="mentioned" href="http://instagr.am/p/MuW67/" />

  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-02-22T20:26:41</published>
  <updated></updated>

    <thr:in-reply-to ref=\"""" + tag_uri('789') + """\" href="http://twitter.com/other_user/status/789" type="text/html" />

  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->

    <georss:featureName>Carcassonne, Aude</georss:featureName>

  <link rel="self" type="application/atom+xml" href="http://twitter.com/snarfed_org/status/100" />
</entry>

</feed>
"""


class TwitterTest(testutil.HandlerTest):

  def setUp(self):
    super(TwitterTest, self).setUp()
    self.twitter = twitter.Twitter('key', 'secret')

  def test_get_actor(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/users/lookup.json?screen_name=foo',
      json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.twitter.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/account/verify_credentials.json',
      json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.twitter.get_actor())

  def test_get_activities(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/home_timeline.json?'
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

    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/home_timeline.json?'
      'include_entities=true&count=2',
      json.dumps([TWEET, tweet2]))
    self.mox.ReplayAll()

    got = self.twitter.get_activities(start_index=1, count=1)
    self.assert_equals((None, [activity2]), got)

  def test_get_activities_activity_id(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/show.json?id=000&include_entities=true',
      json.dumps(TWEET))
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals(
      (1, [ACTIVITY]),
      self.twitter.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_self(self):
    self.expect_urlopen('https://api.twitter.com/1.1/statuses/user_timeline.json?'
                         'include_entities=true&count=0',
                         '[]')
    self.mox.ReplayAll()

    self.assert_equals((None, []),
                       self.twitter.get_activities(group_id=source.SELF))

  def test_get_activities_fetch_replies(self):
    tweet = copy.deepcopy(TWEET)
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/home_timeline.json?include_entities=true&count=0',
      json.dumps([tweet]))
    self.expect_urlopen(
      'https://api.twitter.com/1.1/search/tweets.json?q=%40snarfed_org&include_entities=true&result_type=recent&count=100',
      json.dumps(REPLIES_TO_SNARFED))
    self.expect_urlopen(
      'https://api.twitter.com/1.1/search/tweets.json?q=%40alice&include_entities=true&result_type=recent&count=100',
      json.dumps(REPLIES_TO_ALICE))
    self.expect_urlopen(
      'https://api.twitter.com/1.1/search/tweets.json?q=%40bob&include_entities=true&result_type=recent&count=100',
      json.dumps(REPLIES_TO_BOB))
    self.mox.ReplayAll()

    self.assert_equals((None, [ACTIVITY_WITH_REPLIES]),
                       self.twitter.get_activities(fetch_replies=True))

  def test_get_activities_fetch_shares(self):
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/home_timeline.json?include_entities=true&count=0',
      json.dumps([tweet]))
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/retweets.json?id=100',
      json.dumps(RETWEETS))
    self.mox.ReplayAll()

    got = self.twitter.get_activities(fetch_shares=True)
    self.assert_equals((None, [ACTIVITY_WITH_SHARES]), got)

  def test_get_activities_fetch_shares_no_retweets(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/home_timeline.json?include_entities=true&count=0',
      json.dumps([TWEET]))
    # we should only ask the API for retweets when retweet_count > 0
    self.mox.ReplayAll()

    self.assert_equals((None, [ACTIVITY]),
                       self.twitter.get_activities(fetch_shares=True))

  def test_get_comment(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/show.json?id=123&include_entities=true',
      json.dumps(TWEET))
    self.mox.ReplayAll()
    self.assert_equals(OBJECT, self.twitter.get_comment('123'))

  def test_get_share(self):
    self.expect_urlopen(
      'https://api.twitter.com/1.1/statuses/show.json?id=123&include_entities=true',
      json.dumps(RETWEETS[0]))
    self.mox.ReplayAll()
    self.assert_equals(SHARES[0], self.twitter.get_share('user', 'tweet', '123'))

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

  def test_tweet_to_object_with_retweets(self):
    self.assert_equals(OBJECT_WITH_SHARES,
                       self.twitter.tweet_to_object(TWEET_WITH_RETWEETS))

  def test_retweet_to_object(self):
    for retweet, share in zip(RETWEETS, SHARES):
      self.assert_equals(share, self.twitter.retweet_to_object(retweet))

    # not a retweet
    self.assertEquals(None, self.twitter.retweet_to_object(TWEET))

  def test_streaming_event_to_object(self):
    self.assert_equals(LIKE, self.twitter.streaming_event_to_object(FAVORITE_EVENT))

    # not a favorite event
    follow = {
      'event': 'follow',
      'source': USER,
      'target': USER,
      'target_object': TWEET,
      }
    self.assertEquals(None, self.twitter.streaming_event_to_object(follow))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.twitter.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    # just test that we don't crash
    self.twitter.user_to_actor({'screen_name': 'snarfed_org'})

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.twitter.user_to_actor({}))

  def test_oauth(self):
    def check_headers(headers):
      sig = dict(headers)['Authorization']
      return (sig.startswith('OAuth ') and
              'oauth_token="key"' in sig and
              'oauth_signature=' in sig)

    self.expect_urlopen(
      'https://api.twitter.com/1.1/users/lookup.json?screen_name=foo',
      json.dumps(USER),
      headers=mox.Func(check_headers))
    self.mox.ReplayAll()

    self.twitter.get_actor('foo')
