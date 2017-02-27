# coding=utf-8
"""Unit tests for twitter.py.
"""

import copy
import httplib
import json
import mox
import requests
import socket
import urllib
import urllib2

from oauth_dropins import appengine_config
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import microformats2
from granary import source
from granary import twitter
from granary.twitter import (
  API_FAVORITES, API_LIST_TIMELINE, API_LOOKUP, API_RETWEETS, API_SEARCH,
  API_STATUS, API_TIMELINE, API_USER_TIMELINE, HTML_FAVORITES)

__author__ = ['Ryan Barrett <granary@ryanb.org>']

# test data
def tag_uri(name):
  return util.tag_uri('twitter.com', name)

TIMELINE = twitter.API_TIMELINE % 0

USER = {  # Twitter
  'created_at': 'Sat May 01 21:42:43 +0000 2010',
  'description': 'my description',
  'location': 'San Francisco',
  'name': 'Ryan Barrett',
  'profile_image_url': 'http://a0.twimg.com/profile_images/866165047/ryan.jpg',
  'screen_name': 'snarfed_org',
  'id_str': '888',
  'protected': False,
  'url': 'http://t.co/pUWU4S',
  'entities': {
    'url': {
      'urls': [{
        'url': 'http://t.co/pUWU4S',
        'expanded_url': 'https://snarfed.org/',
      }]},
    'description': {
      'urls': [{
        'url': 'http://t.co/123',
        'expanded_url': 'http://link/123',
      }, {
        'url': 'http://t.co/456',
        'expanded_url': 'http://link/456',
      }]},
    },
  }
ACTOR = {  # ActivityStreams
  'objectType': 'person',
  'displayName': 'Ryan Barrett',
  'image': {
    'url': 'http://a0.twimg.com/profile_images/866165047/ryan.jpg',
    },
  'id': tag_uri('snarfed_org'),
  'numeric_id': '888',
  'published': '2010-05-01T21:42:43+00:00',
  'url': 'https://snarfed.org/',
  'urls': [{'value': 'https://snarfed.org/'},
           {'value': 'http://link/123'},
           {'value': 'http://link/456'},
           ],
  'location': {'displayName': 'San Francisco'},
  'username': 'snarfed_org',
  'description': 'my description',
  }
# Twitter
# (extended tweet: https://dev.twitter.com/overview/api/upcoming-changes-to-tweets )
TWEET = {
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
        'display_url': 'http://pic.twitter.com/1',
        'indices': [83, 102],
      }, {
        # duplicated in extended_entities; we should de-dupe
        'id': 'picture3',
        'media_url': 'http://p.twimg.com/picture3',
      }],
    'urls': [{
        'expanded_url': 'http://first/link/',
        'url': 'http://t.co/6J2EgYM',
        'indices': [49, 68],
        'display_url': 'first'
        }, {
        'expanded_url': 'http://instagr.am/p/MuW67/',
        'url': 'http://t.co/X',
        'indices': [69, 82],
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
  'extended_entities': {
    'media': [{
      'media_url': 'http://p.twimg.com/picture2',
      'expanded_url': 'http://the/picture2',
      'display_url': 'http://pic.twitter.com/2',
    }, {
      # duplicated in entities; we should de-dupe
      'id': 'picture3',
      'media_url': 'http://p.twimg.com/picture3',
    }],
  },
  'full_text': '@twitter meets @seepicturely at #tcdisrupt &lt;3 http://t.co/6J2EgYM http://t.co/X http://t.co/picture',
  'truncated': False,
  'display_text_range': [0, 82],  # includes @twitter, excludes http://t.co/picture
  'source': '<a href="http://choqok.gnufolks.org/" rel="nofollow">Choqok</a>',
  }
TWEET_2 = copy.deepcopy(TWEET)
TWEET_2['user']['name'] = 'foo'
OBJECT = {  # ActivityStreams
  'objectType': 'note',
  'author': ACTOR,
  'content': '@twitter meets @seepicturely at #tcdisrupt &lt;3 first instagr.am/p/MuW67',
  'id': tag_uri('100'),
  'published': '2012-02-22T20:26:41+00:00',
  'url': 'https://twitter.com/snarfed_org/status/100',
  'image': {'url': 'http://p.twimg.com/picture1'},
  'location': {
    'displayName': 'Carcassonne, Aude',
    'id': '31cb9e7ed29dbe52',
    'url': 'https://maps.google.com/maps?q=32.4004416,-98.9852672',
  },
  'to': [{'objectType': 'group', 'alias': '@public'}],
  'tags': [{
      'objectType': 'person',
      'id': tag_uri('foo'),
      'url': 'https://twitter.com/foo',
      'displayName': 'Twitter',
      'startIndex': 0,
      'length': 8,
      }, {
      'objectType': 'person',
      'id': tag_uri('foo'),  # same id as above, shouldn't de-dupe
      'url': 'https://twitter.com/foo',
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
      'startIndex': 49,
      'length': 5,
      }, {
      'objectType': 'article',
      'url': 'http://instagr.am/p/MuW67/',
      'displayName': 'instagr.am/p/MuW67',
      'startIndex': 55,
      'length': 18,
      }],
  'attachments': [{
      'objectType': 'image',
      'image': {'url': u'http://p.twimg.com/picture1'},
      }, {
      'objectType': 'image',
      'image': {'url': u'http://p.twimg.com/picture2'},
      }, {
      'objectType': 'image',
      'image': {'url': u'http://p.twimg.com/picture3'},
      }],
  }
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-02-22T20:26:41+00:00',
  'id': tag_uri('100'),
  'url': 'https://twitter.com/snarfed_org/status/100',
  'actor': ACTOR,
  'object': OBJECT,
  'generator': {'displayName': 'Choqok', 'url': 'http://choqok.gnufolks.org/'},
  }
ACTIVITY_2 = copy.deepcopy(ACTIVITY)
ACTIVITY_2['actor']['displayName'] = 'foo'

# This is the original tweet and reply chain:
# 100 (snarfed_org) -- 200 (alice) -- 400 (snarfed_org) -- 500 (alice)
#                   \_ 300 (bob)
REPLIES_TO_SNARFED = {'statuses': [{  # Twitter
      'id_str': '200',
      'user': {'screen_name': 'alice'},
      'text': 'reply 200',
      'in_reply_to_status_id_str': '100',
      'in_reply_to_screen_name': 'snarfed_org',
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

REPLY_OBJS = [{  # ActivityStreams
    'objectType': 'note',
    'id': tag_uri('200'),
    'author': {
      'objectType': 'person',
      'id': 'tag:twitter.com:alice',
      'username': 'alice',
      'displayName': 'alice',
      'url': 'https://twitter.com/alice',
      },
    'content': 'reply 200',
    'url': 'https://twitter.com/alice/status/200',
    }, {
    'objectType': 'note',
    'id': tag_uri('300'),
    'author': {
      'objectType': 'person',
      'id': 'tag:twitter.com:bob',
      'username': 'bob',
      'displayName': 'bob',
      'url': 'https://twitter.com/bob',
      },
    'content': 'reply 300',
    'url': 'https://twitter.com/bob/status/300',
    }, {
    'objectType': 'note',
    'id': tag_uri('400'),
    'author': {
      'objectType': 'person',
      'id': 'tag:twitter.com:snarfed_org',
      'username': 'snarfed_org',
      'displayName': 'snarfed_org',
      'url': 'https://twitter.com/snarfed_org',
      },
    'content': 'reply 400',
    'url': 'https://twitter.com/snarfed_org/status/400',
    }, {
    'objectType': 'note',
    'id': tag_uri('500'),
    'author': {
      'objectType': 'person',
      'id': 'tag:twitter.com:alice',
      'username': 'alice',
      'displayName': 'alice',
      'url': 'https://twitter.com/alice',
      },
    'content': 'reply 500',
    'url': 'https://twitter.com/alice/status/500',
    }]
ACTIVITY_WITH_REPLIES = copy.deepcopy(ACTIVITY)  # ActivityStreams
ACTIVITY_WITH_REPLIES['object']['replies'] = {
  'totalItems': 4,
  'items': REPLY_OBJS,
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
      'text': 'retweeted text',
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
    'url': 'https://twitter.com/alizz/status/123',
    'objectType': 'activity',
    'verb': 'share',
    'object': {'url': 'https://twitter.com/foo/status/333'},
    'author': {
      'objectType': 'person',
      'id': 'tag:twitter.com:alizz',
      'username': 'alizz',
      'displayName': 'Alice',
      'url': 'https://twitter.com/alizz',
      'image': {'url': 'http://alice/picture'},
      },
    'published': '2013-02-24T20:26:41+00:00',
    }, {
    'id': tag_uri('456'),
    'url': 'https://twitter.com/bobbb/status/456',
    'objectType': 'activity',
    'verb': 'share',
    'object': {'url': 'https://twitter.com/bar/status/666'},
    'content': 'RT <a href="https://twitter.com/bar">@bar</a>: retweeted text',
    'author': {
      'objectType': 'person',
      'id': 'tag:twitter.com:bobbb',
      'username': 'bobbb',
      'displayName': 'Bob',
      'url': 'https://twitter.com/bobbb',
      'image': {'url': 'http://bob/picture'},
      },
    'published': '2013-02-26T20:26:41+00:00',
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
LIKE_OBJ = {  # ActivityStreams
  'id': tag_uri('100_favorited_by_789'),
  'url': 'https://twitter.com/snarfed_org/status/100#favorited-by-789',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://twitter.com/snarfed_org/status/100'},
  'author': {
    'objectType': 'person',
    'id': tag_uri('eve'),
    'numeric_id': '789',
    'username': 'eve',
    'displayName': 'eve',
    'url': 'https://twitter.com/eve',
    },
  'published': '2013-12-27T17:25:55+00:00',
  }
FAVORITES_HTML = u"""  # Twitter, from /i/activity/favorited_popup?id=...
<ol class="activity-popup-users">
    <li class="js-stream-item stream-item stream-item
" data-item-id="353" id="stream-item-user-353" data-item-type="user">
    <!-- snipped <div class="account"... -->
  <div class="content">
        <div class="stream-item-header">
          <a class="account-group js-user-profile-link" href="/ge" >
            <img class="avatar js-action-profile-avatar " src="https://twimg/353" alt="" data-user-id="353"/>
            <strong class="fullname js-action-profile-name">George</strong>
              <span class="username js-action-profile-name">@ge</span></a>
        </div>
      </div>
    </div>
    </li>

  <li class="js-stream-item stream-item stream-item">
    <!-- snipped <div class="account"... -->
    <div class="content">
      <div class="stream-item-header">
        <a class="account-group js-user-profile-link" href="/ge" >
          <span class="username js-action-profile-name">@jo</span></a>
      </div>
    </div>
  </li>

  <li class="js-stream-item stream-item stream-item">
    <div class="content">
      <div class="stream-item-header">
        <a class="account-group js-user-profile-link" href="/c_foo" >
          <img class="avatar js-action-profile-avatar  " src="https://pbs.twimg.com/profile_images/123/abc_normal.jpg" alt="" data-user-id="23238890"/>
          <strong class="fullname js-action-profile-name">Charles <span class="Emoji Emoji--forLinks" style="background-image:url('https://abs.twimg.com/emoji/v2/72x72/000.png')" title="Hot beverage" aria-label="Emoji: Hot beverage">&nbsp;</span><span class="visuallyhidden" aria-hidden="true">☕</span> Foo</strong>
            <span class="username js-action-profile-name">@c_foo</span>
        </a>
      </div>
    </div>
  </li>
</ol>
"""
LIKES_FROM_HTML = [{  # ActivityStreams
  'id': tag_uri('100_favorited_by_353'),
  'url': 'https://twitter.com/snarfed_org/status/100#favorited-by-353',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://twitter.com/snarfed_org/status/100'},
  'author': {
    'objectType': 'person',
    'id': tag_uri('ge'),
    'numeric_id': '353',
    'username': 'ge',
    'displayName': 'George',
    'url': 'https://twitter.com/ge',
    'image': {'url': 'https://twimg/353'},
  },
}, {
  'url': 'https://twitter.com/snarfed_org/status/100',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://twitter.com/snarfed_org/status/100'},
  'author': {
    'objectType': 'person',
    'id': tag_uri('jo'),
    'username': 'jo',
    'displayName': 'jo',
    'url': 'https://twitter.com/jo',
  },
}, {
  'id': tag_uri('100_favorited_by_23238890'),
  'url': 'https://twitter.com/snarfed_org/status/100#favorited-by-23238890',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://twitter.com/snarfed_org/status/100'},
  'author': {
    'objectType': 'person',
    'id': tag_uri('c_foo'),
    'numeric_id': '23238890',
    'username': 'c_foo',
    'displayName': u'Charles ☕ Foo',
    'url': 'https://twitter.com/c_foo',
    'image': {'url': u'https://pbs.twimg.com/profile_images/123/abc.jpg'},
  },
}]
OBJECT_WITH_LIKES = copy.deepcopy(OBJECT)
OBJECT_WITH_LIKES['tags'] += LIKES_FROM_HTML
ACTIVITY_WITH_LIKES = copy.deepcopy(ACTIVITY)
ACTIVITY_WITH_LIKES['object'] = OBJECT_WITH_LIKES

QUOTE_TWEET = {
  'id': 2345,
  'id_str': '2345',
  'is_quote_status': True,
  'quoted_status_id_str': TWEET['id_str'],
  'quoted_status': TWEET,
  'text': 'I agree with this https://t.co/ww6HD8KroG',
  'user': {'screen_name': 'kylewmahan'},
  'entities': {
    'urls': [{
      'url': 'https://t.co/ww6HD8KroG',
      'expanded_url': 'https://twitter.com/snarfed_org/status/100',
      'display_url': u'twitter.com/schnar…',
      'indices': [18, 41],
    }],
  },
}
QUOTE_ACTOR = {
  'displayName': 'kylewmahan',
  'id': 'tag:twitter.com:kylewmahan',
  'objectType': 'person',
  'url': 'https://twitter.com/kylewmahan',
  'username': 'kylewmahan'
}
QUOTE_ACTIVITY = {
  'id': 'tag:twitter.com:2345',
  'url': 'https://twitter.com/kylewmahan/status/2345',
  'verb': 'post',
  'actor': QUOTE_ACTOR,
  'object': {
    'id': 'tag:twitter.com:2345',
    'url': 'https://twitter.com/kylewmahan/status/2345',
    'objectType': 'note',
    'content': 'I agree with this ',
    'attachments': [OBJECT],
    'author': QUOTE_ACTOR,
  },
}
RETWEETED_QUOTE_TWEET = {
  'id': 6789,
  'id_str': '6789',
  'retweeted_status': QUOTE_TWEET,
  'is_quote_status': True,
  'quoted_status_id_str': TWEET['id_str'],
  'text': 'RT @kylewmahan: I agree with this ',
  'user': USER,
}
QUOTE_SHARE = {
  'id': tag_uri('6789'),
  'url': 'https://twitter.com/snarfed_org/status/6789',
  'verb': 'share',
  'actor': ACTOR,
  'object': QUOTE_ACTIVITY['object'],
}


ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:georss="http://www.georss.org/georss"
      xmlns:ostatus="http://ostatus.org/schema/1.0"
      xmlns:thr="http://purl.org/syndication/thread/1.0"
      xml:base="%(base_url)s">
<generator uri="https://github.com/snarfed/granary">granary</generator>
<id>%(host_url)s</id>
<title>User feed for Ryan Barrett</title>

<subtitle>my description</subtitle>

<logo>http://a0.twimg.com/profile_images/866165047/ryan.jpg</logo>
<updated>2012-02-22T20:26:41+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://snarfed.org/</uri>
 <name>Ryan Barrett</name>
</author>

<link rel="alternate" href="https://snarfed.org/" type="text/html" />
<link rel="avatar" href="http://a0.twimg.com/profile_images/866165047/ryan.jpg" />
<link rel="self" href="%(request_url)s" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://snarfed.org/</uri>
 <name>Ryan Barrett</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/note</activity:object-type>

  <id>https://twitter.com/snarfed_org/status/100</id>
  <title>@twitter meets @seepicturely at #tcdisrupt &lt;3 first instagr.am/p/MuW67</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

<a href="https://twitter.com/foo">@twitter</a> meets @seepicturely at <a href="https://twitter.com/search?q=%%23tcdisrupt">#tcdisrupt</a> &lt;3 <a href="http://first/link/">first</a> <a href="http://instagr.am/p/MuW67/">instagr.am/p/MuW67</a>
<p>
<a class="link" href="https://twitter.com/snarfed_org/status/100">
<img class="thumbnail" src="http://p.twimg.com/picture1" alt="" />
</a>
</p>
<p>
<a class="link" href="https://twitter.com/snarfed_org/status/100">
<img class="thumbnail" src="http://p.twimg.com/picture2" alt="" />
</a>
</p>
<p>
<a class="link" href="https://twitter.com/snarfed_org/status/100">
<img class="thumbnail" src="http://p.twimg.com/picture3" alt="" />
</a>
</p>
<span class="p-location h-card">
<a class="p-name u-url" href="https://maps.google.com/maps?q=32.4004416,-98.9852672">Carcassonne, Aude</a>

</span>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="https://twitter.com/snarfed_org/status/100" />
  <link rel="ostatus:conversation" href="https://twitter.com/snarfed_org/status/100" />

    <link rel="ostatus:attention" href="https://twitter.com/foo" />
    <link rel="mentioned" href="https://twitter.com/foo" />

    <a href="https://twitter.com/foo">Twitter</a>

    <link rel="ostatus:attention" href="https://twitter.com/foo" />
    <link rel="mentioned" href="https://twitter.com/foo" />

    <link rel="ostatus:attention" href="https://twitter.com/search?q=%%23tcdisrupt" />
    <link rel="mentioned" href="https://twitter.com/search?q=%%23tcdisrupt" />

    <link rel="ostatus:attention" href="http://first/link/" />
    <link rel="mentioned" href="http://first/link/" />

    <link rel="ostatus:attention" href="http://instagr.am/p/MuW67/" />
    <link rel="mentioned" href="http://instagr.am/p/MuW67/" />

  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-02-22T20:26:41+00:00</published>
  <updated>2012-02-22T20:26:41+00:00</updated>

    <georss:featureName>Carcassonne, Aude</georss:featureName>

  <link rel="self" type="application/atom+xml" href="https://twitter.com/snarfed_org/status/100" />

</entry>

</feed>
"""


class TwitterTest(testutil.TestCase):

  def setUp(self):
    super(TwitterTest, self).setUp()
    self.maxDiff = None
    appengine_config.TWITTER_APP_KEY = 'fake'
    appengine_config.TWITTER_APP_SECRET = 'fake'
    self.orig_max_tweet_length = twitter.MAX_TWEET_LENGTH
    self.orig_tco_length = twitter.TCO_LENGTH
    self.twitter = twitter.Twitter('key', 'secret')

  def tearDown(self):
    twitter.MAX_TWEET_LENGTH = self.orig_max_tweet_length
    twitter.TCO_LENGTH = self.orig_tco_length

  def expect_urlopen(self, url, response=None, params=None, **kwargs):
    if not url.startswith('http'):
      url = twitter.API_BASE + url
    if params:
      url += '?' + urllib.urlencode(params)
      kwargs.setdefault('data', '')
    if not isinstance(response, basestring):
      response=json.dumps(response)
    return super(TwitterTest, self).expect_urlopen(
      url, response=response, **kwargs)

  def test_get_actor(self):
    self.expect_urlopen('users/show.json?screen_name=foo', USER)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.twitter.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlopen('account/verify_credentials.json', USER)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.twitter.get_actor())

  def test_get_activities(self):
    self.expect_urlopen(TIMELINE, [TWEET, TWEET])
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY, ACTIVITY], self.twitter.get_activities())

  def test_get_activities_start_index_count(self):
    self.expect_urlopen(API_TIMELINE % 2, [TWEET, TWEET_2])
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_2],
                       self.twitter.get_activities(start_index=1, count=1))

  def test_get_activities_start_index_count_zero(self):
    self.expect_urlopen(API_TIMELINE % 0, [TWEET, TWEET_2])
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY, ACTIVITY_2],
                       self.twitter.get_activities(start_index=0, count=0))

  def test_get_activities_count_past_end(self):
    self.expect_urlopen(API_TIMELINE % 9, [TWEET])
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY], self.twitter.get_activities(count=9))

  def test_get_activities_start_index_past_end(self):
    self.expect_urlopen(API_TIMELINE % 0, [])
    self.mox.ReplayAll()
    self.assert_equals([], self.twitter.get_activities(start_index=9))

  def test_get_activities_activity_id(self):
    self.expect_urlopen(API_STATUS % '000', TWEET)
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals([ACTIVITY], self.twitter.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_bad_activity_id(self):
    """https://github.com/snarfed/bridgy/issues/719"""
    self.assertRaises(ValueError, self.twitter.get_activities,
                      activity_id='123:abc')

  def test_get_activities_self(self):
    self.expect_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': ''}, [])
    self.mox.ReplayAll()

    self.assert_equals([], self.twitter.get_activities(group_id=source.SELF))

  def test_get_activities_self_fetch_likes(self):
    self.expect_urlopen(API_FAVORITES % '', [TWEET_2])
    self.expect_urlopen(
      'account/verify_credentials.json', FAVORITE_EVENT['source'])
    self.expect_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': ''}, [TWEET])
    self.mox.ReplayAll()

    got = self.twitter.get_activities(group_id=source.SELF, fetch_likes=True)
    like_obj = copy.copy(LIKE_OBJ)
    del like_obj['published']
    self.assert_equals([like_obj, ACTIVITY], got)

  def test_get_activities_for_screen_name(self):
    self.expect_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': 'schnarfed'},
                        [])
    self.mox.ReplayAll()

    self.assert_equals([], self.twitter.get_activities(user_id='schnarfed',
                                                       group_id=source.SELF))

  def test_get_activities_list_explicit_user(self):
    self.expect_urlopen(API_LIST_TIMELINE % {
      'count': 0,
      'slug': 'testlist',
      'owner_screen_name': 'schnarfed',
    }, [])
    self.mox.ReplayAll()

    self.assert_equals([], self.twitter.get_activities(group_id='testlist', user_id='schnarfed'))

  def test_get_activities_list_implicit_user(self):
    self.expect_urlopen('account/verify_credentials.json',
                        {'screen_name': 'schnarfed'})
    self.expect_urlopen(API_LIST_TIMELINE % {
      'count': 0,
      'slug': 'testlist',
      'owner_screen_name': 'schnarfed',
    }, [])
    self.mox.ReplayAll()

    self.assert_equals([], self.twitter.get_activities(group_id='testlist'))

  def test_get_activities_fetch_replies(self):
    self.expect_urlopen(TIMELINE, [TWEET])

    search = API_SEARCH + '&since_id=567'
    self.expect_urlopen(search % {'q': '%40snarfed_org', 'count': 100},
                        REPLIES_TO_SNARFED)
    self.expect_urlopen(search % {'q': '%40alice', 'count': 100}, REPLIES_TO_ALICE)
    self.expect_urlopen(search % {'q': '%40bob', 'count': 100}, REPLIES_TO_BOB)
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_WITH_REPLIES],
                       self.twitter.get_activities(fetch_replies=True, min_id='567'))

  def test_get_activities_fetch_mentions(self):
    self.expect_urlopen(TIMELINE, [])
    self.expect_urlopen('account/verify_credentials.json',
                        {'screen_name': 'schnarfed'})
    search_url = API_SEARCH % {'q': '%40schnarfed', 'count': 100} + '&since_id=567'
    self.expect_urlopen(search_url, {
      'statuses': [
        # reply to me
        {'id_str': '1', 'text': '@schnarfed foo',
         'in_reply_to_status_id_str': '11'},
        # reply to a tweet that @-mentions me
        {'id_str': '2', 'text': '@eve bar, cc @schnarfed',
         'in_reply_to_status_id_str': '12'},
        # reply to a tweet that doesn't @-mention me
        {'id_str': '3', 'text': '@frank baz, cc @schnarfed',
         'in_reply_to_status_id_str': '13'},
        # normal tweet that @-mentions me
        {'id_str': '4', 'text': 'mention @schnarfed'},
        # self mention
        {'id_str': '5', 'text': '@schnarfed mentions himself',
         'user': {'screen_name': 'schnarfed'}},
        # retweet of a tweet that mentions me
        {'id_str': '6', 'retweeted_status': {'id_str': '4'}},
      ]})
    self.expect_urlopen(API_LOOKUP % '11,12,13',
      [{'id_str': '11', 'user': {'screen_name': 'schnarfed'}},
       {'id_str': '12', 'entities': {'user_mentions': [{'screen_name': 'schnarfed'}]}},
       {'id_str': '13', 'text': 'barrey'},
      ])
    self.mox.ReplayAll()

    # fetch_replies as well as fetch_mentions to make sure we don't try to find
    # replies to the mentions. https://github.com/snarfed/bridgy/issues/631
    got = self.twitter.get_activities(fetch_mentions=True, fetch_replies=True,
                                      min_id='567')
    self.assert_equals([tag_uri('3'), tag_uri('4')], [a['id'] for a in got])

  def test_get_activities_quote_tweets(self):
    twitter.QUOTE_SEARCH_BATCH_SIZE = 5  # reduce the batch size for testing
    # search for 8 tweets to make sure we split them up into groups of <= 5
    tweets = []
    for id in xrange(1000, 1008):
      tweet = copy.deepcopy(TWEET)
      tweet['id'] = id
      tweet['id_str'] = str(id)
      tweets.append(tweet)

    self.expect_urlopen(TIMELINE, tweets)

    # search @-mentions returns nothing
    self.expect_urlopen('account/verify_credentials.json',
                        {'screen_name': 'schnarfed'})
    self.expect_urlopen(twitter.API_SEARCH % {
      'q': urllib.quote_plus('@schnarfed'),
      'count': 100,
    } + '&since_id=567', {'statuses': []})

    # first search returns no results
    self.expect_urlopen(twitter.API_SEARCH % {
      'q': urllib.quote_plus('1000 OR 1001 OR 1002 OR 1003 OR 1004'),
      'count': 100,
    } + '&since_id=567', {'statuses': []})

    # second search finds a quote tweet for 1006 and an RT of that
    quote_tweet = copy.deepcopy(QUOTE_TWEET)
    quote_tweet['quoted_status_id_str'] = '1006'
    retweeted_quote_tweet = copy.deepcopy(RETWEETED_QUOTE_TWEET)
    retweeted_quote_tweet['quoted_status_id_str'] = '1006'
    self.expect_urlopen(twitter.API_SEARCH % {
      'q': urllib.quote_plus('1005 OR 1006 OR 1007'),
      'count': 100,
    } + '&since_id=567', {
      'statuses': [quote_tweet, retweeted_quote_tweet],
    })

    self.mox.ReplayAll()
    got = self.twitter.get_activities(fetch_mentions=True, min_id='567')
    self.assertEqual(9, len(got))

    # should include quote tweet
    self.assert_equals(QUOTE_ACTIVITY, got[-1])

    # shouldn't include RT of quote tweet
    self.assertNotIn('tag:twitter.com:6789', [a.get('id') for a in got])

  def test_get_activities_fetch_shares(self):
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    self.expect_urlopen(TIMELINE, [tweet])
    self.expect_urlopen(API_RETWEETS % '100' + '&since_id=567', RETWEETS)
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_WITH_SHARES],
                       self.twitter.get_activities(fetch_shares=True, min_id='567'))

  def test_get_activities_fetch_shares_no_retweets(self):
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    self.expect_urlopen(TIMELINE, [tweet])
    self.expect_urlopen(API_RETWEETS % '100'
                       ).AndRaise(urllib2.HTTPError('url', 404, 'msg', {}, None))
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_shares=True))

  def test_get_activities_fetch_shares_404s(self):
    self.expect_urlopen(TIMELINE, [TWEET])
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_shares=True))

  def test_get_activities_fetch_cache(self):
    # Test with multiple tweets to cover the bug described in
    # https://github.com/snarfed/bridgy/issues/22#issuecomment-56329848 :
    # util.CacheDict.get_multi() didn't originally handle generator args.
    tweets = [copy.deepcopy(TWEET), copy.deepcopy(TWEET)]
    tweets[0]['id_str'] += '_a'
    tweets[1]['id_str'] += '_b'

    for count in (1, 2):
      for t in tweets:
        t['retweet_count'] = t['favorite_count'] = count
      self.expect_urlopen(TIMELINE, tweets)
      self.expect_urlopen(API_RETWEETS % '100_a', [])
      self.expect_urlopen(API_RETWEETS % '100_b', [])
      self.expect_urlopen(HTML_FAVORITES % '100_a', {})
      self.expect_urlopen(HTML_FAVORITES % '100_b', {})
      # shouldn't fetch this time because counts haven't changed
      self.expect_urlopen(TIMELINE, tweets)

    self.mox.ReplayAll()
    cache = util.CacheDict()
    for i in range(4):
      self.twitter.get_activities(fetch_shares=True, fetch_likes=True,
                                  cache=cache)

  def test_get_activities_fetch_likes(self):
    tweet = copy.deepcopy(TWEET)
    tweet['favorite_count'] = 1
    self.expect_urlopen(TIMELINE, [tweet])
    self.expect_urlopen('https://twitter.com/i/activity/favorited_popup?id=100',
      {'htmlUsers': FAVORITES_HTML})
    self.mox.ReplayAll()

    cache = util.CacheDict()
    self.assert_equals([ACTIVITY_WITH_LIKES],
                       self.twitter.get_activities(fetch_likes=True, cache=cache))
    self.assert_equals(1, cache['ATF 100'])

  def test_get_activities_favorites_404(self):
    tweet = copy.deepcopy(TWEET)
    tweet['favorite_count'] = 1
    self.expect_urlopen(TIMELINE, [tweet])
    self.expect_urlopen('https://twitter.com/i/activity/favorited_popup?id=100'
      ).AndRaise(urllib2.HTTPError('url', 404, 'msg', {}, None))
    self.mox.ReplayAll()

    cache = util.CacheDict()
    self.assert_equals([ACTIVITY],
                       self.twitter.get_activities(fetch_likes=True, cache=cache))
    self.assertNotIn('ATF 100', cache)

  def test_get_activities_fetch_likes_no_favorites(self):
    self.expect_urlopen(TIMELINE, [TWEET])
    # we should only ask the API for retweets when favorites_count > 0
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_likes=True))

  def test_get_activities_private_activity_skips_fetch_likes_and_retweets(self):
    tweet = copy.deepcopy(TWEET)
    tweet['user']['protected'] = True
    tweet['favorite_count'] = tweet['retweet_count'] = 1

    self.expect_urlopen(TIMELINE, [tweet])
    # no HTML favorites fetch or /statuses/retweets API call
    self.mox.ReplayAll()

    activity = copy.deepcopy(ACTIVITY)
    activity['object']['to'][0]['alias'] = '@private'
    self.assert_equals([activity], self.twitter.get_activities(
      fetch_likes=True, fetch_shares=True))

  def test_retweet_limit(self):
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    self.expect_urlopen(TIMELINE, [tweet] * (twitter.RETWEET_LIMIT + 2))

    for i in range(twitter.RETWEET_LIMIT):
      self.expect_urlopen(API_RETWEETS % 100 + '&since_id=567', RETWEETS)

    self.mox.ReplayAll()
    self.assert_equals(([ACTIVITY_WITH_SHARES] * twitter.RETWEET_LIMIT) +
                       [ACTIVITY, ACTIVITY],
                       self.twitter.get_activities(fetch_shares=True, min_id='567'))

  def test_get_activities_request_etag(self):
    self.expect_urlopen(TIMELINE, [], headers={'If-none-match': '"my etag"'})
    self.mox.ReplayAll()
    self.twitter.get_activities_response(etag='"my etag"')

  def test_get_activities_response_etag(self):
    self.expect_urlopen(TIMELINE, [], response_headers={'ETag': '"my etag"'})
    self.mox.ReplayAll()
    self.assert_equals('"my etag"', self.twitter.get_activities_response()['etag'])

  def test_get_activities_304_not_modified(self):
    """Requests with matching ETags return 304 Not Modified."""
    self.expect_urlopen(TIMELINE, [], status=304)
    self.mox.ReplayAll()
    self.assert_equals([], self.twitter.get_activities_response()['items'])

  def test_get_activities_min_id(self):
    """min_id shouldn't be passed to the initial request, just the derived ones."""
    self.expect_urlopen(TIMELINE, [])
    self.mox.ReplayAll()
    self.twitter.get_activities_response(min_id=135)

  def test_get_activities_retries(self):
    for exc in (httplib.HTTPException('Deadline exceeded: foo'),
                socket.error('asdf'),
                urllib2.HTTPError('url', 501, 'msg', {}, None)):
      for i in range(twitter.RETRIES):
        self.expect_urlopen(TIMELINE).AndRaise(exc)
      self.expect_urlopen(TIMELINE, [])
      self.mox.ReplayAll()
      self.assertEquals([], self.twitter.get_activities_response()['items'])
      self.mox.ResetAll()

    # other exceptions shouldn't retry
    for exc in (httplib.HTTPException('not a deadline'),
                urllib2.HTTPError('url', 403, 'not a 5xx', {}, None)):
      self.expect_urlopen(TIMELINE).AndRaise(exc)
      self.mox.ReplayAll()
      self.assertRaises(exc.__class__, self.twitter.get_activities_response)
      self.mox.ResetAll()

  def test_get_activities_search(self):
    self.expect_urlopen(twitter.API_SEARCH % {'q': 'indieweb', 'count': 0}, {
      'statuses': [TWEET, TWEET],
      'search_metadata': {
        'max_id': 250126199840518145,
      },
    })
    self.mox.ReplayAll()
    self.assert_equals(
      [ACTIVITY, ACTIVITY], self.twitter.get_activities(
        group_id=source.SEARCH, search_query='indieweb'))

  def test_get_activities_search_no_query(self):
    with self.assertRaises(ValueError):
      self.twitter.get_activities(group_id=source.SEARCH, search_query=None)

  def test_get_activities_search_with_unicode_char(self):
    self.expect_urlopen(twitter.API_SEARCH % {'q': u'%E2%98%95+foo', 'count': 0},
                        {'statuses': []})
    self.mox.ReplayAll()
    self.assert_equals([], self.twitter.get_activities(
        group_id=source.SEARCH, search_query=u'☕ foo'))

  def test_get_comment(self):
    self.expect_urlopen(API_STATUS % '123', TWEET)
    self.mox.ReplayAll()
    self.assert_equals(OBJECT, self.twitter.get_comment('123'))

  def test_get_comment_bad_comment_id(self):
    """https://github.com/snarfed/bridgy/issues/719"""
    self.assertRaises(ValueError, self.twitter.get_comment, '123:abc')

  def test_get_share(self):
    self.expect_urlopen(API_STATUS % '123', RETWEETS[0])
    self.mox.ReplayAll()
    self.assert_equals(SHARES[0], self.twitter.get_share('user', 'tweet', '123'))

  def test_get_share_bad_id(self):
    """https://github.com/snarfed/bridgy/issues/719"""
    self.assertRaises(ValueError, self.twitter.get_share, None, None, '123:abc')

  def test_tweet_to_activity_full(self):
    self.assert_equals(ACTIVITY, self.twitter.tweet_to_activity(TWEET))

  def test_tweet_to_activity_minimal(self):
    # just test that we don't crash
    self.twitter.tweet_to_activity({'id': 123, 'text': 'asdf'})

  def test_tweet_to_activity_empty(self):
    # just test that we don't crash
    self.twitter.tweet_to_activity({})

  def test_quote_tweet_to_activity(self):
    self.assert_equals(QUOTE_ACTIVITY, self.twitter.tweet_to_activity(QUOTE_TWEET))

  def test_quote_tweet_to_activity_without_quoted_tweet_url_entity(self):
    quote_tweet = copy.deepcopy(QUOTE_TWEET)
    quote_tweet['entities']['urls'][0]['expanded_url'] = 'http://foo/bar'

    self.assert_equals(u'I agree with this twitter.com/schnar…',
                       self.twitter.tweet_to_activity(quote_tweet)['object']['content'])

    del quote_tweet['entities']
    self.assert_equals('I agree with this https://t.co/ww6HD8KroG',
                       self.twitter.tweet_to_activity(quote_tweet)['object']['content'])

  def test_tweet_to_object_unicode_high_code_points(self):
    """Test Unicode high code point chars.

    The first three unicode chars in the text are the '100' emoji, which is a
    high code point, ie above the Basic Multi-lingual Plane (ie 16 bits). The
    emacs font i use doesn't render it, so it looks blank.

    First discovered in https://twitter.com/schnarfed/status/831552681210556416
    """
    obj = self.twitter.tweet_to_object({
      'id_str': '831552681210556416',
      'text': u'💯💯💯 (by @itsmaeril) https://t.co/pWrOHzuHkP',
      'entities': {
        'user_mentions': [{
          'screen_name': 'itsmaeril',
          'indices': [8, 18]
        }],
        'media': [{
          'indices': [20, 43],
          'media_url': 'http://pbs.twimg.com/media/C4pEu77UkAAVy9l.jpg',
        }]
      },
    })
    self.assert_equals(u'💯💯💯 (by @itsmaeril) ', obj['content'])
    self.assert_equals(
      u'💯💯💯 (by <a href="https://twitter.com/itsmaeril">@itsmaeril</a>) ',
      microformats2.render_content(obj).splitlines()[0])

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

  def test_tweet_to_activity_display_text_range(self):
    self.assert_equals({
      'objectType': 'note',
      # should only have the text inside display_text_range
      'content': 'i hereby reply',
      'id': tag_uri('100'),
      # both tags are outside display_text_range, so they shouldn't have
      # startIndex or length
      'tags': [{
        'objectType': 'person',
        'id': tag_uri('OP'),
        'url': 'https://twitter.com/OP',
      }, {
        'objectType': 'article',
        'url': 'http://full/quoted/tweet',
      }],
      'to': [{
        'objectType': 'person',
        'id': tag_uri('OP'),
        'url': 'https://twitter.com/OP',
      }],
    }, self.twitter.tweet_to_object({
      'id_str': '100',
      'full_text': '@OP i hereby reply http://quoted/tweet',
      'truncated': False,
      'display_text_range': [4, 18],
      'entities': {
        'user_mentions': [{
          'screen_name': 'OP',
          'indices': [0, 3],
        }],
        'urls': [{
          'expanded_url': 'http://full/quoted/tweet',
          'url': 'http://quoted/tweet',
          'indices': [19, 38],
        }],
      },
    }))

  def test_tweet_to_object_entity_indices_handle_display_urls(self):
    tweet = {
      'id_str': '123',
      'full_text': '@schnarfed Hey Ryan, You might find this semi-related and interesting: https://t.co/AFGvnvG72L Heard about it from @danshipper this week.',
      'display_text_range': [11, 137],
      'entities': {
        'urls': [{
            'url': 'https://t.co/AFGvnvG72L',
            'expanded_url': 'https://www.onename.io/',
            'display_url': 'onename.io',
            'indices': [71, 94],
            }],
        'user_mentions': [{
            'screen_name': 'danshipper',
            'name': 'Dan Shipper',
            'indices': [115, 126],
            }],
        },
      }

    obj = self.twitter.tweet_to_object(tweet)
    for tag in obj['tags']:
      if tag['displayName'] == 'Dan Shipper':
        self.assertEquals(91, tag['startIndex'])
        self.assertEquals(11, tag['length'])
        break
    else:
      self.fail('Dan Shipper not found')

    self.assertEquals('Hey Ryan, You might find this semi-related and interesting: <a href="https://www.onename.io/">onename.io</a> Heard about it from <a href="https://twitter.com/danshipper">@danshipper</a> this week.',
                      microformats2.render_content(obj))

  def test_tweet_to_object_retweet_with_entities(self):
    """Retweets with entities should use the entities in the retweet object."""
    tweet = {
      'id_str': '123',
      'text': 'not the full retweeted text',
      'entities': {'urls': [{
        'url': 'https://t.co/AFGvnvG72L',
        'expanded_url': 'https://www.onename.io/',
        'display_url': 'onename.io',
        'indices': [4, 8],
      }]},
      'retweeted_status': {
        'id_str': '456',
        'user': {'screen_name': 'orig'},
        'text': 'a @danshipper https://t.co/AFGvnvG72L ok',
        'entities': {
          'urls': [{
              'url': 'https://t.co/AFGvnvG72L',
              'expanded_url': 'https://www.onename.io/',
              'display_url': 'onename.io',
              'indices': [14, 37],
              }],
          'user_mentions': [{
              'screen_name': 'danshipper',
              'name': 'Dan Shipper',
              'indices': [2, 13],
              }],
          },
        }
      }

    obj = self.twitter.tweet_to_object(tweet)
    self.assert_equals([{
      'objectType': 'person',
      'id': tag_uri('danshipper'),
      'url': 'https://twitter.com/danshipper',
      'displayName': 'Dan Shipper',
      'startIndex': 51,
      'length': 11,
      }, {
      'objectType': 'article',
      'url': 'https://www.onename.io/',
      'displayName': 'onename.io',
      'startIndex': 63,
      'length': 10,
      }], obj['tags'])

    self.assert_equals('RT <a href="https://twitter.com/orig">@orig</a>: a <a href="https://twitter.com/danshipper">@danshipper</a> <a href="https://www.onename.io/">onename.io</a> ok',
                      microformats2.render_content(obj))

  def test_tweet_to_object_multiple_pictures_only_one_picture_link(self):
    self.assert_equals({
      'id': tag_uri('726480459488587776'),
      'objectType': 'note',
      'content': u'\u2611 Harley Davidson Museum\u00ae \u2611 Schlitz .... \u2611 Milwaukee ',
      'attachments': [{'objectType': 'image'}, {'objectType': 'image'}],
    }, self.twitter.tweet_to_object({
      'id_str': '726480459488587776',
      'text': u'\u2611 Harley Davidson Museum\u00ae \u2611 Schlitz .... \u2611 Milwaukee https://t.co/6Ta5P8A2cs',
      'extended_entities': {
        'media': [{
          'id_str': '1',
          'indices': [53, 76],
        }, {
          'id_str': '2',
          'indices': [53, 76],
        }],
      },
    }))

  def test_reply_tweet_to_activity(self):
    tweet = copy.deepcopy(TWEET)
    tweet.update({
      'in_reply_to_screen_name': 'other_user',
      'in_reply_to_status_id': 789,
      })
    expected = [{
      'url' : 'https://twitter.com/other_user/status/789',
      'id' : tag_uri('789'),
    }]

    activity = self.twitter.tweet_to_activity(tweet)
    self.assert_equals({'inReplyTo': expected}, activity['context'])
    self.assert_equals(expected, activity['object']['inReplyTo'])

    direct_obj = self.twitter.tweet_to_object(tweet)
    self.assert_equals(expected, direct_obj['inReplyTo'])

  def test_tweet_to_activity_on_retweet(self):
    self.assert_equals({
        'verb': 'share',
        'url': 'https://twitter.com/rt_author/status/444',
        'actor': {
            'displayName': 'rt_author',
            'id': tag_uri('rt_author'),
            'objectType': 'person',
            'url': 'https://twitter.com/rt_author',
            'username': 'rt_author'
          },
        'id': tag_uri(444),
        'object': {
          'author': {
            'displayName': 'orig_author',
            'id': tag_uri('orig_author'),
            'objectType': 'person',
            'url': 'https://twitter.com/orig_author',
            'username': 'orig_author'
          },
          'objectType': 'note',
          'content': 'my long original tweet',
          'id': tag_uri(333),
          'url': 'https://twitter.com/orig_author/status/333',
          }
        },
      self.twitter.tweet_to_activity({
        'id_str': '444',
        'text': 'truncated',
        'user': {'id': 888, 'screen_name': 'rt_author'},
        'retweeted_status': {
          'id_str': '333',
          'text': 'my long original tweet',
          'user': {'id': 777, 'screen_name': 'orig_author'},
          },
        }))

  def test_tweet_to_activity_retweet_of_quote_tweet(self):
    self.assert_equals(QUOTE_SHARE,
                       self.twitter.tweet_to_activity(RETWEETED_QUOTE_TWEET))

  def test_protected_tweet_to_object(self):
    tweet = copy.deepcopy(TWEET)
    tweet['user']['protected'] = True
    obj = copy.deepcopy(OBJECT)
    obj['to'][0]['alias'] = '@private'
    self.assert_equals(obj, self.twitter.tweet_to_object(tweet))

  def test_retweet_to_object(self):
    for retweet, share in zip(RETWEETS, SHARES):
      self.assert_equals(share, self.twitter.retweet_to_object(retweet))

    # not a retweet
    self.assertEquals(None, self.twitter.retweet_to_object(TWEET))

  def test_streaming_event_to_object(self):
    self.assert_equals(LIKE_OBJ,
                       self.twitter.streaming_event_to_object(FAVORITE_EVENT))

    # not a favorite event
    follow = {
      'event': 'follow',
      'source': USER,
      'target': USER,
      'target_object': TWEET,
      }
    self.assertEquals(None, self.twitter.streaming_event_to_object(follow))

  def test_favorites_html_to_likes(self):
    self.assert_equals([], self.twitter.favorites_html_to_likes(TWEET, ""))
    likes = self.twitter.favorites_html_to_likes(TWEET, FAVORITES_HTML)
    self.assert_equals(LIKES_FROM_HTML, likes)

    # https://console.cloud.google.com/errors/16941961690170721544
    for like in likes:
      self.assertEquals(unicode, like['author']['displayName'].__class__)

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.twitter.user_to_actor(USER))

  def test_user_to_actor_url_fallback(self):
    user = copy.deepcopy(USER)
    del user['entities']
    actor = copy.deepcopy(ACTOR)
    del actor['urls']
    actor['url'] = 'http://t.co/pUWU4S'
    self.assert_equals(actor, self.twitter.user_to_actor(user))

    del user['url']
    actor['url'] = 'https://twitter.com/snarfed_org'
    self.assert_equals(actor, self.twitter.user_to_actor(user))

  def test_user_to_actor_displayName_fallback(self):
    self.assert_equals({
      'objectType': 'person',
      'id': tag_uri('schnarfed'),
      'username': 'schnarfed',
      'displayName': 'schnarfed',
      'url': 'https://twitter.com/schnarfed',
    }, self.twitter.user_to_actor({
      'screen_name': 'schnarfed',
    }))

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

    self.expect_urlopen('users/show.json?screen_name=foo',
      USER,
      headers=mox.Func(check_headers))
    self.mox.ReplayAll()

    self.twitter.get_actor('foo')

  def test_urlopen_not_json(self):
    self.expect_urlopen(twitter.API_BASE + 'xyz', 'not json'
      ).MultipleTimes(twitter.RETRIES + 1)
    self.mox.ReplayAll()

    try:
      self.twitter.urlopen('xyz')
      self.fail('Expected HTTPError')
    except urllib2.HTTPError, e:
      self.assertEqual(502, e.code)

  def test_get_activities_not_json(self):
    self.expect_urlopen(TIMELINE, 'not json')
    self.mox.ReplayAll()

    try:
      self.twitter.get_activities()
      self.fail('Expected HTTPError')
    except urllib2.HTTPError, e:
      self.assertEqual(502, e.code)

  def test_create_tweet(self):
    twitter.MAX_TWEET_LENGTH = 20
    twitter.TCO_LENGTH = 5

    dots = u'…'
    original = (
      'my status',
      'too long, will be ellipsized',
      'url shorten http://foo.co/bar',
      'url http://foo.co/bar ellipsize http://foo.co/baz',
      'long url http://www.foo.co/bar/baz/baj/biff/boof',
      'trailing slash http://www.foo.co/',
      'fragment http://foo.co/#bar',
      'exactly twenty chars',
      'just over twenty one chars',  # would trunc after 'one' if we didn't account for the ellipsis
      'HTML<br/>h &amp; h',
      "to @schnarfed's user",
      'a #hashyytag',
    )
    created = (
      'my status',
      'too long, will be' + dots,
      'url shorten http://foo.co/bar',
      'url http://foo.co/bar ellipsize' + dots,
      'long url http://www.foo.co/bar/baz/baj/biff/boof',
      'trailing slash http://www.foo.co/',
      'fragment http://foo.co/#bar',
      'exactly twenty chars',
      'just over twenty' + dots,
      'HTML\nh & h',
      "to @schnarfed's user",
      'a #hashyytag',
    )
    previewed = (
      'my status',
      'too long, will be' + dots,
      'url shorten <a href="http://foo.co/bar">foo.co/bar</a>',
      'url <a href="http://foo.co/bar">foo.co/bar</a> ellipsize' + dots,
      'long url <a href="http://www.foo.co/bar/baz/baj/biff/boof">foo.co/bar/baz/baj/bi...</a>',
      'trailing slash <a href="http://www.foo.co/">foo.co</a>',
      'fragment <a href="http://foo.co/#bar">foo.co/#bar</a>',
      'exactly twenty chars',
      'just over twenty' + dots,
      'HTML\nh & h',
      'to <a href="https://twitter.com/schnarfed">@schnarfed</a>\'s user',
      'a <a href="https://twitter.com/hashtag/hashyytag">#hashyytag</a>',
    )

    for content in created:
      self.expect_urlopen(twitter.API_POST_TWEET, TWEET,
                          params={'status': content.encode('utf-8')})
    self.mox.ReplayAll()

    tweet = copy.deepcopy(TWEET)
    tweet.update({
        'id': '100',
        'url': 'https://twitter.com/snarfed_org/status/100',
        'type': 'post',
        })

    obj = copy.deepcopy(OBJECT)
    del obj['image']
    for preview, orig in zip(previewed, original):
      obj['content'] = orig
      self.assert_equals(tweet, self.twitter.create(obj).content)

      got = self.twitter.preview_create(obj)
      self.assertEquals('<span class="verb">tweet</span>:', got.description)
      self.assertEquals(preview, got.content)

  def test_tweet_truncate(self):
    """A bunch of tests to exercise the tweet shortening algorithm
    """
    twitter.MAX_TWEET_LENGTH = 140
    twitter.TCO_LENGTH = 23

    orig = (
      u'Hey #indieweb, the coming storm of webmention Spam may not be '
      u'far away. Those of us that have input fields to send webmentions '
      u'manually may already be getting them')
    expected = (
      u'Hey #indieweb, the coming storm of webmention Spam may not '
      u'be far away. Those of us that have input fields to send… '
      u'https://ben.thatmustbe.me/note/2015/1/31/1/')
    result = self.twitter._truncate(
      orig, 'https://ben.thatmustbe.me/note/2015/1/31/1/',
      source.INCLUDE_LINK, 'note')
    self.assertEquals(expected, result)

    orig = expected = (
      u'Despite names,\n'
      u'ind.ie&indie.vc are NOT #indieweb @indiewebcamp\n'
      u'indiewebcamp.com/2014-review#Indie_Term_Re-use\n'
      u'@iainspad @sashtown @thomatronic (ttk.me t4_81)')
    result = self.twitter._truncate(
      orig, 'http://tantek.com/1234', source.OMIT_LINK, 'note')
    self.assertEquals(expected, result)

    orig = expected = (
      u'@davewiner I stubbed a page on the wiki for '
      u'https://indiewebcamp.com/River4. Edits/improvmnts from users are '
      u'welcome! @kevinmarks @julien51 @aaronpk')
    result = self.twitter._truncate(
      orig, 'https://kylewm.com/5678', source.INCLUDE_IF_TRUNCATED,
      'note')
    self.assertEquals(expected, result)

    orig = expected = (
      u'This is a long tweet with (foo.com/parenthesized-urls) and urls '
      u'that wikipedia.org/Contain_(Parentheses), a url with a query '
      u'string;foo.withknown.com/example?query=parameters')
    result = self.twitter._truncate(
      orig, 'https://foo.bar/', source.INCLUDE_IF_TRUNCATED, 'note')
    self.assertEquals(expected, result)

    orig = (
      u'This is a long tweet with (foo.com/parenthesized-urls) and urls '
      u'that wikipedia.org/Contain_(Parentheses), that is one charc too '
      u'long:foo.withknown.com/example?query=parameters')
    expected = (
      u'This is a long tweet with (foo.com/parenthesized-urls) and urls '
      u'that wikipedia.org/Contain_(Parentheses), that is one charc too '
      u'long:…')
    result = self.twitter._truncate(
      orig, 'http://foo.com/', source.OMIT_LINK, 'note')
    self.assertEquals(expected, result)

    # test case-insensitive link matching
    orig = (
      u'The Telegram Bot API is the best bot API ever. Everyone should '
      u'learn from it, especially Matrix.org, which currently requires a '
      u'particular URL structure and registration files.')
    expected = (
      u'The Telegram Bot API is the best bot API ever. Everyone should learn '
      u'from it, especially Matrix.org… '
      u'https://unrelenting.technology/notes/2015-09-05-00-35-13')
    result = self.twitter._truncate(
      orig, 'https://unrelenting.technology/notes/2015-09-05-00-35-13',
      source.INCLUDE_IF_TRUNCATED,
      'note')
    self.assertEquals(expected, result)

    orig = (u'Leaving this here for future reference. Turn on debug menu '
      u'in Mac App Store `defaults write com.apple.appstore ShowDebugMenu '
      u'-bool true`')
    expected = (u'Leaving this here for future reference. Turn on debug menu '
      u'in Mac App Store `defaults write com.apple.appstore ShowDebugMenu…')
    result = self.twitter._truncate(orig, 'http://foo.com', source.OMIT_LINK, 'note')
    self.assertEquals(expected, result)

    twitter.MAX_TWEET_LENGTH = 20
    twitter.TCO_LENGTH = 5

    orig = u'url http://foo.co/bar ellipsize http://foo.co/baz'
    expected = u'url http://foo.co/bar ellipsize…'
    result = self.twitter._truncate(
      orig, 'http://foo.com', source.OMIT_LINK, 'note')
    self.assertEquals(expected, result)

    orig = u'too long\nextra whitespace\tbut should include url'
    expected = u'too long… http://obj.ca'
    result = self.twitter._truncate(
      orig, 'http://obj.ca', source.INCLUDE_LINK, 'note')
    self.assertEquals(expected, result)

    orig = expected = u'trailing slash http://www.foo.co/'
    result = self.twitter._truncate(
      orig, 'http://www.foo.co/', source.OMIT_LINK, 'note')
    self.assertEquals(expected, result)

  def test_no_ellipsize_real_tweet(self):
    orig = """\
Despite names,
ind.ie&indie.vc are NOT #indieweb @indiewebcamp
indiewebcamp.com/2014-review#Indie_Term_Re-use
@iainspad @sashtown @thomatronic (ttk.me t4_81)"""

    preview = """\
Despite names,
ind.ie&indie.vc are NOT <a href="https://twitter.com/hashtag/indieweb">#indieweb</a> <a href="https://twitter.com/indiewebcamp">@indiewebcamp</a>
<a href="http://indiewebcamp.com/2014-review#Indie_Term_Re-use">indiewebcamp.com/2014-review#In...</a>
<a href="https://twitter.com/iainspad">@iainspad</a> <a href="https://twitter.com/sashtown">@sashtown</a> <a href="https://twitter.com/thomatronic">@thomatronic</a> (ttk.me t4_81)"""

    self.expect_urlopen(twitter.API_POST_TWEET, TWEET, params={'status': orig})
    self.mox.ReplayAll()

    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj['content'] = orig.replace("\n", '<br />').replace('&', '&amp;')
    obj['url'] = 'http://tantek.com/2015/013/t1/names-ind-ie-indie-vc-not-indieweb'

    actual_preview = self.twitter.preview_create(
      obj, include_link=source.OMIT_LINK).content
    self.assertEquals(preview, actual_preview)

    self.twitter.create(obj, include_link=source.OMIT_LINK)

  def test_ellipsize_real_tweet(self):
    """Test ellipsizing a tweet that was giving us trouble. If you do not
    account for the ellipsis when determining where to truncate, it will
    truncate after 'send' and the result will be 141 characters.
    """
    orig = ('Hey #indieweb, the coming storm of webmention Spam may not be '
            'far away. Those of us that have input fields to send webmentions '
            'manually may already be getting them')

    content = (u'Hey #indieweb, the coming storm of webmention Spam may not '
               u'be far away. Those of us that have input fields to send… '
               u'https://ben.thatmustbe.me/note/2015/1/31/1/')

    preview = (u'Hey <a href="https://twitter.com/hashtag/indieweb">#indieweb</a>, '
               u'the coming storm of webmention Spam may not '
               u'be far away. Those of us that have input fields to send… '
               u'<a href="https://ben.thatmustbe.me/note/2015/1/31/1/">ben.thatmustbe.me/note/2015/1/31...</a>')

    self.expect_urlopen(twitter.API_POST_TWEET, TWEET,
                        params={'status': content.encode('utf-8')})
    self.mox.ReplayAll()

    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj['content'] = orig
    obj['url'] = 'https://ben.thatmustbe.me/note/2015/1/31/1/'

    self.twitter.create(obj, include_link=source.INCLUDE_LINK)
    actual_preview = self.twitter.preview_create(obj, include_link=source.INCLUDE_LINK).content
    self.assertEquals(preview, actual_preview)

  def test_tweet_article_has_different_format(self):
    """Articles are published with a slightly different format:
    "The Title: url", instead of "The Title (url)"
    """
    preview = self.twitter.preview_create({
      'objectType': 'article',
      'displayName': 'The Article Title',
      'url': 'http://example.com/article',
    }, include_link=source.INCLUDE_LINK).content
    self.assertEquals(
      'The Article Title: <a href="http://example.com/article">example.com/'
      'article</a>', preview)

  def test_create_tweet_note_prefers_summary_then_content_then_name(self):
    obj = copy.deepcopy(OBJECT)

    obj.update({
        'objectType': 'note',
        'summary': 'my summary',
        'displayName': 'my name',
        'content': 'my content',
        'image': None,
        })
    result = self.twitter.preview_create(obj)
    self.assertEquals('my summary', result.content)

    del obj['summary']
    result = self.twitter.preview_create(obj)
    self.assertEquals('my content', result.content)

    del obj['content']
    result = self.twitter.preview_create(obj)
    self.assertIn('my name', result.content)

  def test_create_tweet_article_prefers_summary_then_name_then_content(self):
    obj = copy.deepcopy(OBJECT)

    obj.update({
        'objectType': 'article',
        'summary': 'my summary',
        'displayName': 'my name',
        'content': 'my<br />content',
        'image': None,
        })
    result = self.twitter.preview_create(obj)
    self.assertIn('my summary', result.content)

    del obj['summary']
    result = self.twitter.preview_create(obj)
    self.assertIn('my name', result.content)

    del obj['displayName']
    result = self.twitter.preview_create(obj)
    self.assertIn('my\ncontent', result.content)

  def test_create_tweet_include_link(self):
    twitter.MAX_TWEET_LENGTH = 20
    twitter.TCO_LENGTH = 5

    self.expect_urlopen(twitter.API_POST_TWEET, TWEET,
                        params={'status': 'too long… http://obj.ca'})
    self.mox.ReplayAll()

    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj.update({
        'content': 'too long\nextra whitespace\tbut should include url',
        'url': 'http://obj.ca',
        })
    self.twitter.create(obj, include_link=source.INCLUDE_LINK)
    result = self.twitter.preview_create(obj, include_link=source.INCLUDE_LINK)
    self.assertIn(u'too long… <a href="http://obj.ca">obj.ca</a>',
                  result.content)

  def test_create_tweet_include_link_if_truncated(self):
    twitter.MAX_TWEET_LENGTH = 20
    twitter.TCO_LENGTH = 5

    cases = [(
      u'too long\nextra whitespace\tbut should include url',
      u'http://obj.ca',
      u'too long… http://obj.ca',
      u'too long… <a href="http://obj.ca">obj.ca</a>',
    ), (
      u'short and sweet',
      u'http://obj.ca',
      u'short and sweet',
      u'short and sweet',
    )]

    for _, _, expected, _ in cases:
      self.expect_urlopen(twitter.API_POST_TWEET, TWEET,
                          params={'status': expected.encode('utf-8')})

    self.mox.ReplayAll()

    obj = copy.deepcopy(OBJECT)
    del obj['image']

    for content, url, _, expected in cases:
      obj.update({'content': content, 'url': url})
      self.twitter.create(
        obj, include_link=source.INCLUDE_IF_TRUNCATED)
      result = self.twitter.preview_create(
        obj, include_link=source.INCLUDE_IF_TRUNCATED)
      self.assertIn(expected, result.content)

  def test_create_recognize_note(self):
    """Use post-type-discovery to recognize a note with non-trivial html content.
    We'll know it was successful if it respects the rich content and includes
    newlines in the output.
    """
    obj = microformats2.json_to_object({
      "type": ["h-entry"],
      "properties": {
        "author": [
          {
            "properties": {
              "name": ["Tantek \u00c7elik"],
              "photo": ["http://tantek.com/logo.jpg"],
              "url": ["http://tantek.com/"]
            },
            "type": ["h-card"],
            "value": "",
          }
        ],
        "content": [
          {
            "html": "https://instagram.com/p/9XVBIRA9cj/<br /><br />Social Web session @W3C #TPAC2015 in Sapporo, Hokkaido, Japan.",
            "value": " https://instagram.com/p/9XVBIRA9cj/Social Web session @W3C #TPAC2015 in Sapporo, Hokkaido, Japan."
          }
        ],
        "name": ["https://instagram.com/p/9XVBIRA9cj/Social Web session @W3C #TPAC2015 in Sapporo, Hokkaido, Japan."],
        "photo": ["https://igcdn-photos-b-a.akamaihd.net/hphotos-ak-xaf1/t51.2885-15/e35/12145332_1662314194043465_2009449288_n.jpg"],
        "published": ["2015-10-27T19:48:00-0700"],
        "syndication": [
          "https://www.facebook.com/photo.php?fbid=10101948228396473",
          "https://twitter.com/t/status/659200761427980288"
        ],
        "uid": ["http://tantek.com/2015/300/t1/social-web-session-w3c-tpac2015"],
        "updated": ["2015-10-27T19:48:00-0700"],
        "url": ["http://tantek.com/2015/300/t1/social-web-session-w3c-tpac2015"],
      },
    })

    result = self.twitter.preview_create(obj, include_link=source.OMIT_LINK)
    self.assertIn('instagram.com/p/9XVBIRA9cj</a>\n\nSocial Web session <a href="https://twitter.com/W3C">@W3C</a> <a href="https://twitter.com/hashtag/TPAC2015">#TPAC2015</a> in Sapporo, Hokkaido, Japan.', result.content)

  def test_create_tweet_with_location_hcard(self):
    self._test_create_tweet_with_location({
      'location': [{
        'type': ['h-card'],
        'properties': {
          'name': ['Timeless Coffee Roasters'],
          'locality': ['Oakland'],
          'region': ['California'],
          'latitude': ['37.83'],
          'longitude': ['-122.25'],
          'url': ['https://kylewm.com/venues/timeless-coffee-roasters-oakland-california'],
        },
        'value': 'Timeless Coffee Roasters',
      }]})

  def test_create_tweet_with_location_geo(self):
    self._test_create_tweet_with_location({
      'geo': [{
        'properties': {
          'latitude': ['37.83'],
          'longitude': ['-122.25'],
        },
      }]
    })

  def test_create_tweet_with_location_geo_url(self):
    self._test_create_tweet_with_location({
      'geo': ['geo:37.83,-122.25;foo=bar'],
    })

  def test_create_tweet_with_location_top_level(self):
    self._test_create_tweet_with_location({
      'latitude': ['37.83'],
      'longitude': ['-122.25'],
    })

  def _test_create_tweet_with_location(self, props):
    mf2 = {
      'type': ['h-entry'],
      'properties': {
        'author': [{
          'type': ['h-card'],
          'properties': {
            'name': ['Kyle Mahan'],
            'photo': ['https://kylewm.com/static/img/users/kyle.jpg'],
            'url': ['https://kylewm.com'],
          },
          'value': 'Kyle Mahan',
        }],
        'name': ['Checked in to Timeless Coffee Roasters'],
        'url': ['https://kylewm.com/2015/11/checked-into-timeless-coffee-roasters'],
        'uid': ['https://kylewm.com/2015/11/checked-into-timeless-coffee-roasters'],
        'shortlink': ['https://kylewm.com/c/4e01'],
        'published': ['2015-11-01T15:34:38-08:00'],
        'content': [{
            'html': '<p>Checked in to Timeless Coffee Roasters</p>',
            'value': 'Checked in to Timeless Coffee Roasters',
          }]
      }
    }
    mf2['properties'].update(props)
    obj = microformats2.json_to_object(mf2)

    result = self.twitter.preview_create(obj, include_link=source.OMIT_LINK)
    self.assertIn('37.83, -122.25', result.content)

    self.expect_urlopen(twitter.API_POST_TWEET, TWEET, params={
      'status': 'Checked in to Timeless Coffee Roasters',
      'lat': '37.83',
      'long': '-122.25',
    })
    self.mox.ReplayAll()
    self.twitter.create(obj, include_link=source.OMIT_LINK)

  def test_create_reply(self):
    # tuples: (content, in-reply-to url, expected tweet, expected preview)
    testdata = (
      # reply with @-mention of author
      ('foo @you', 'http://twitter.com/you/status/100', 'foo @you',
       'foo <a href="https://twitter.com/you">@you</a>'),
      # reply without @-mention of in-reply-to author
      ('foo', 'http://twitter.com/you/status/100', 'foo', 'foo'),
      # replies with leading @-mentions, should be removed
      ('@you foo', 'http://twitter.com/you/status/100', 'foo', 'foo'),
      ('@YoU foo', 'http://twitter.com/you/status/100', 'foo', 'foo'),
      # photo URL. tests Twitter.base_object()
      ('foo', 'http://twitter.com/you/status/100/photo/1', 'foo', 'foo'),
      # mobile.twitter.com URL. the mobile should be stripped from embed.
      ('foo', 'http://mobile.twitter.com/you/status/100', 'foo', 'foo'),
      )

    for _, _, status, _ in testdata:
      self.expect_urlopen(twitter.API_POST_TWEET, TWEET, params={
        'status': status,
        'in_reply_to_status_id': 100,
        'auto_populate_reply_metadata': 'true',
      })
    self.mox.ReplayAll()

    tweet = copy.deepcopy(TWEET)
    obj = copy.deepcopy(REPLY_OBJS[0])

    for content, url, _, expected_preview in testdata:
      tweet.update({
          'id': '100',
          'url': 'https://twitter.com/snarfed_org/status/100',
          'type': 'comment',
          })
      obj.update({'inReplyTo': [{'url': url}], 'content': content})
      self.assert_equals(tweet, self.twitter.create(obj).content)

      preview = self.twitter.preview_create(obj)
      self.assertEquals(expected_preview, preview.content)
      self.assertIn('<span class="verb">@-reply</span> to <a href="http://twitter.com/you/status/100">this tweet</a>:', preview.description)

  def test_create_reply_objectType_comment(self):
    obj = {
      'objectType': 'comment',
      'content': 'my content',
      'inReplyTo': [{'url': 'http://twitter.com/you/status/100'}],
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertIn('<span class="verb">@-reply</span> to <a href="http://twitter.com/you/status/100">this tweet</a>:', preview.description)
    self.assertEquals('my content', preview.content)

    # test create
    self.expect_urlopen(twitter.API_POST_TWEET, {'url': 'http://posted/tweet'},
                        params={
                          'status': 'my content',
                          'in_reply_to_status_id': '100',
                          'auto_populate_reply_metadata': 'true',
                        })
    self.mox.ReplayAll()
    self.assert_equals({'url': 'http://posted/tweet', 'type': 'comment'},
                       self.twitter.create(obj).content)

  def test_create_reply_to_self_omits_mention(self):
    for i in range(3):
      self.expect_urlopen(
        twitter.API_POST_TWEET, {'url': 'http://posted/tweet'},
        params={
          'status': 'my content',
          'in_reply_to_status_id': '100',
          'auto_populate_reply_metadata': 'true',
        })
    self.mox.ReplayAll()

    for username, reply_to in ('me', 'me'), ('ME', 'ME'), ('Me', 'mE'):
      tw = twitter.Twitter('key', 'secret', username=username)
      obj = {
        'objectType': 'comment',
        'content': 'my content',
        'inReplyTo': [{'url': 'http://twitter.com/%s/status/100' % reply_to}],
      }

      # test preview
      preview = tw.preview_create(obj)
      self.assertIn('@-reply</span> to <a href="%s">this tweet</a>:' %
                      obj['inReplyTo'][0]['url'],
                    preview.description)
      self.assertEquals('my content', preview.content)

      # test create
      self.assert_equals({'url': 'http://posted/tweet', 'type': 'comment'},
                         tw.create(obj).content)

  def test_create_favorite(self):
    self.expect_urlopen(twitter.API_POST_FAVORITE, TWEET, params={'id': 100})
    self.mox.ReplayAll()
    self.assert_equals({'url': 'https://twitter.com/snarfed_org/status/100',
                        'type': 'like'},
                       self.twitter.create(LIKES_FROM_HTML[0]).content)

    preview = self.twitter.preview_create(LIKES_FROM_HTML[0])
    self.assertIn("""\
<span class="verb">favorite</span>
<a href="https://twitter.com/snarfed_org/status/100">this tweet</a>:""",
                  preview.description)

  def test_create_retweet(self):
    self.expect_urlopen(twitter.API_POST_RETWEET % 333, TWEET, params={'id': 333})
    self.mox.ReplayAll()

    tweet = copy.deepcopy(TWEET)
    tweet.update({
        'id': '100',
        'url': 'https://twitter.com/snarfed_org/status/100',
        'type': 'repost',
        })
    self.assert_equals(tweet, self.twitter.create(SHARES[0]).content)

    preview = self.twitter.preview_create(SHARES[0])
    self.assertIn("""\
<span class="verb">retweet</span>
<a href="https://twitter.com/foo/status/333">this tweet</a>:""",
                  preview.description)

  def test_create_quote_tweet(self):
    self.expect_urlopen(
      twitter.API_POST_TWEET, {'url': 'http://posted/tweet'},
      params={
        'status': 'I agree with this https://twitter.com/snarfed_org/status/100',
      })
    self.mox.ReplayAll()

    created = self.twitter.create(QUOTE_ACTIVITY['object'])
    self.assert_equals({'url': 'http://posted/tweet', 'type': 'post'},
                       created.content, created)

    preview = self.twitter.preview_create(QUOTE_ACTIVITY['object'])
    self.assertEquals('I agree with this <a href="https://twitter.com/snarfed_org/status/100">twitter.com/snarfed_org/st...</a>', preview.content)
    self.assertIn("""\
<span class="verb">quote</span>
<a href="https://twitter.com/snarfed_org/status/100">this tweet</a>:""",
                  preview.description)

  def test_create_quote_tweet_strips_quotation(self):
    self.expect_urlopen(twitter.API_POST_TWEET, {}, params={
        'status': 'I agree with this https://twitter.com/snarfed_org/status/100',
      })
    self.mox.ReplayAll()

    obj = copy.deepcopy(QUOTE_ACTIVITY['object'])
    obj['content'] = 'I\tagree\n<cite class="u-quotation-of h-cite">foo</cite>\nwith this'
    created = self.twitter.create(obj)

  def test_create_quote_tweet_truncated_content(self):
    self.expect_urlopen(twitter.API_POST_TWEET, {}, params={
        'status':(u'X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X… https://twitter.com/snarfed_org/status/100').encode('utf-8'),
      })
    self.mox.ReplayAll()

    obj = copy.deepcopy(QUOTE_ACTIVITY['object'])
    obj['content'] = u'X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X'
    created = self.twitter.create(obj)

  def test_create_unsupported_type(self):
    for fn in self.twitter.create, self.twitter.preview_create:
      result = fn({'objectType': 'activity', 'verb': 'rsvp-yes'})
      self.assertTrue(result.abort)
      self.assertIn('Cannot publish RSVPs', result.error_plain)
      self.assertIn('not supported', result.error_html)

  def test_create_reply_without_in_reply_to(self):
    obj = {
      'objectType': 'comment',
      'inReplyTo': [{'url': 'http://foo.com/bar'},
                    {'url': 'http://baz.com/bat'}],
      'content': '@foo reply'
    }
    for fn in (self.twitter.preview_create, self.twitter.create):
      preview = fn(obj)
      self.assertTrue(preview.abort)
      self.assertIn('Could not find a tweet to reply to', preview.error_plain)
      self.assertIn('Could not find a tweet to', preview.error_html)

  def test_create_like_without_object(self):
    obj = {
      'objectType': 'activity',
      'verb': 'like',
      'object': [{'url': 'http://foo.com/bar'},
                 {'url': 'http://plus.google.com/1234'}],
    }
    for fn in (self.twitter.preview_create, self.twitter.create):
      preview = fn(obj)
      self.assertTrue(preview.abort)
      self.assertIn('Could not find a tweet to like', preview.error_plain)
      self.assertIn('Could not find a tweet to', preview.error_html)

  def test_create_retweet_without_object(self):
    obj = {
      'objectType': 'activity',
      'verb': 'share',
      'object': [{'url': 'http://foo.com/bar'}],
    }
    for fn in (self.twitter.preview_create, self.twitter.create):
      preview = fn(obj)
      self.assertTrue(preview.abort)
      self.assertIn('Could not find a tweet to retweet', preview.error_plain)
      self.assertIn('Could not find a tweet to', preview.error_html)

  def test_create_with_multiple_photos(self):
    image_urls = ['http://my/picture/%d' % i for i in range(twitter.MAX_MEDIA + 1)]
    obj = {
      'objectType': 'note',
      'content': """\
the caption. extra long so we can check that it accounts for the pic-twitter-com link. almost at 140 chars, just type a little more, and even more, ok done""",
      'image': [{'url': url} for url in image_urls],
    }

    ellipsized = u"""\
the caption. extra long so we can check that it accounts for the pic-twitter-com link. almost at 140 chars, just type a little more, and…"""
    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertEquals('<span class="verb">tweet</span>:', preview.description)
    self.assertEquals(ellipsized + '<br /><br />' +
                      ' &nbsp; '.join('<img src="%s" />' % url
                                      for url in image_urls[:-1]),
                      preview.content)

    # test create
    for i, url in enumerate(image_urls[:-1]):
      content = 'picture response %d' % i
      self.expect_urlopen(url, content)
      self.expect_requests_post(twitter.API_UPLOAD_MEDIA,
                                json.dumps({'media_id_string': str(i)}),
                                files={'media': content},
                                headers=mox.IgnoreArg())
    self.expect_urlopen(twitter.API_POST_TWEET, {'url': 'http://posted/picture'},
                        params={
                          'status': ellipsized.encode('utf-8'),
                          'media_ids': '0,1,2,3',
                        })
    self.mox.ReplayAll()
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)

  def test_create_reply_with_photo(self):
    obj = {
      'objectType': 'note',
      'content': 'my content',
      'inReplyTo': [{'url': 'http://twitter.com/you/status/100'}],
      'image': {'url': 'http://my/picture'},
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertIn('<span class="verb">@-reply</span> to <a href="http://twitter.com/you/status/100">this tweet</a>:', preview.description)
    self.assertEquals('my content<br /><br /><img src="http://my/picture" />',
                      preview.content)

    # test create
    self.expect_urlopen('http://my/picture', 'picture response')
    self.expect_requests_post(twitter.API_UPLOAD_MEDIA,
                              json.dumps({'media_id_string': '123'}),
                              files={'media': 'picture response'},
                              headers=mox.IgnoreArg())
    self.expect_urlopen(twitter.API_POST_TWEET, {'url': 'http://posted/picture'},
                        params={
                          'status': 'my content',
                          'in_reply_to_status_id': '100',
                          'media_ids': '123',
                          'auto_populate_reply_metadata': 'true',
                        })
    self.mox.ReplayAll()
    self.assert_equals({'url': 'http://posted/picture', 'type': 'comment'},
                       self.twitter.create(obj).content)

  def test_create_with_photo_no_content(self):
    obj = {
      'objectType': 'note',
      'image': {'url': 'http://my/picture'},
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertEquals('<span class="verb">tweet</span>:', preview.description)
    self.assertEquals('<br /><br /><img src="http://my/picture" />', preview.content)

    # test create
    self.expect_urlopen('http://my/picture', 'picture response')
    self.expect_requests_post(twitter.API_UPLOAD_MEDIA,
                              json.dumps({'media_id_string': '123'}),
                              files={'media': 'picture response'},
                              headers=mox.IgnoreArg())
    self.expect_urlopen(twitter.API_POST_TWEET, {'url': 'http://posted/picture'},
                        params={
                          'status': '',
                          'media_ids': '123',
                        })
    self.mox.ReplayAll()
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)

  def test_create_with_photo_error(self):
    obj = {
      'objectType': 'note',
      'content': 'my caption',
      'image': {'url': 'http://my/picture'},
    }

    self.expect_urlopen('http://my/picture', 'picture response')
    self.expect_requests_post(twitter.API_UPLOAD_MEDIA,
                              json.dumps({'media_id_string': '123'}),
                              files={'media': 'picture response'},
                              headers=mox.IgnoreArg())
    self.expect_urlopen(twitter.API_POST_TWEET, {'url': 'http://posted/picture'},
                        params={
                          'status': 'my caption',
                          'media_ids': '123',
                        }, status=403)
    self.mox.ReplayAll()
    self.assertRaises(urllib2.HTTPError, self.twitter.create, obj)

  def test_create_with_photo_wrong_type(self):
    obj = {
      'objectType': 'note',
      'image': {'url': 'http://my/picture.tiff'},
    }
    self.expect_urlopen('http://my/picture.tiff', '')
    self.mox.ReplayAll()

    ret = self.twitter.create(obj)
    self.assertTrue(ret.abort)
    for msg in ret.error_plain, ret.error_html:
      self.assertEquals('Twitter only supports JPG, PNG, GIF, and WEBP images; '
                        'http://my/picture.tiff looks like image/tiff', msg)

  def test_create_with_video(self):
    try:
      orig_size = twitter.UPLOAD_CHUNK_SIZE
      self._test_create_with_video()
    finally:
      twitter.UPLOAD_CHUNK_SIZE = orig_size

  def _test_create_with_video(self):
    obj = {
      'objectType': 'note',
      'content': """\
the caption.\nextra long so we can check that it accounts for the pic-twitter-com link. <video xyz>should be removed. </video> almost at 140 chars, just type a little more, ok done.""",
      'stream': {'url': 'http://my/video'},
    }
    ellipsized = u"""\
the caption. extra long so we can check that it accounts for the pic-twitter-com link. almost at 140 chars, just type a little more, ok…"""

    # test preview
    self.assertEquals(ellipsized +
      '<br /><br /><video controls src="http://my/video">'
      '<a href="http://my/video">this video</a></video>',
      self.twitter.preview_create(obj).content)

    # test create
    content = 'video response'
    self.expect_urlopen('http://my/video', content,
                        response_headers={'Content-Length': len(content)})

    self.expect_urlopen(twitter.API_UPLOAD_MEDIA, {'media_id_string': '9'},
                        params={
                          'command': 'INIT',
                          'media_type': 'video/mp4',
                          'total_bytes': len(content),
                        })

    twitter.UPLOAD_CHUNK_SIZE = 5
    for i, chunk in (0, 'video'), (1, ' resp'), (2, 'onse'):
      self.expect_requests_post(
        twitter.API_UPLOAD_MEDIA, '',
        data={'command': 'APPEND', 'media_id': '9', 'segment_index': i},
        files={'media': chunk},
        headers=mox.IgnoreArg())

    self.expect_urlopen(twitter.API_UPLOAD_MEDIA, {},
                        params={
                          'command': 'FINALIZE',
                          'media_id': '9',
                        })

    self.expect_urlopen(twitter.API_POST_TWEET, {'url': 'http://posted/video'},
                        params={
                          'status': ellipsized.encode('utf-8'),
                          'media_ids': '9',
                        })

    self.mox.ReplayAll()
    self.assert_equals({'url': 'http://posted/video', 'type': 'post'},
                       self.twitter.create(obj).content)

  def test_create_with_video_too_big(self):
    self.expect_urlopen(
      'http://my/video', '',
      response_headers={'Content-Length': twitter.MAX_VIDEO_SIZE + 1})
    self.mox.ReplayAll()

    ret = self.twitter.create({
      'objectType': 'note',
      'stream': {'url': 'http://my/video'},
    })
    self.assertTrue(ret.abort)
    self.assertIn("larger than Twitter's 15MB limit.", ret.error_plain)
    self.assertIn("larger than Twitter's 15MB limit.", ret.error_html)

  def test_create_with_video_wrong_type(self):
    self.expect_urlopen('http://my/video', '',
                        response_headers={'Content-Type': 'video/unknown'})
    self.expect_urlopen('http://my/video.mov', '')
    self.mox.ReplayAll()

    for url in 'http://my/video', 'http://my/video.mov':
      ret = self.twitter.create({
        'objectType': 'note',
        'stream': {'url': url},
      })
      self.assertTrue(ret.abort)
      for msg in ret.error_plain, ret.error_html:
        self.assertIn('Twitter only supports MP4 videos', msg)
