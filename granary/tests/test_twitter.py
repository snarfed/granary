"""Unit tests for twitter.py."""
from collections import OrderedDict
import copy
import http.client
import io
import socket
import urllib.error
import urllib.parse
import unittest
from unittest.mock import patch

from oauth_dropins import twitter_auth
import requests
from requests import RequestException
from webutil import testutil, util
from webutil.testutil import requests_response, UrlopenResult
from webutil.util import json_dumps, json_loads

from .. import microformats2
from .. import source
from .. import twitter
from ..twitter import (
  API_BLOCK_IDS,
  API_BLOCKS,
  API_FAVORITES,
  API_LIST_TIMELINE,
  API_LIST_ID_TIMELINE,
  API_LOOKUP,
  API_RETWEETS,
  API_SEARCH,
  API_STATUS,
  API_TIMELINE,
  API_USER_TIMELINE,
  RETWEET_LIMIT,
  SCRAPE_LIKES_URL,
  Twitter,
)

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
USER_2 = {
  'name': 'Alice Foo',
  'screen_name': 'alice',
  'id_str': '777',
}
USER_3 = {
  'name': 'Bob Bar',
  'screen_name': 'bob',
  'id_str': '666',
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
  'url': 'https://twitter.com/snarfed_org',
  'urls': [
    {'value': 'https://twitter.com/snarfed_org'},
    {'value': 'https://snarfed.org/'},
    {'value': 'http://link/123'},
    {'value': 'http://link/456'},
  ],
  'location': {'displayName': 'San Francisco'},
  'username': 'snarfed_org',
  'description': 'my description',
}
ACTOR_2 = {
  'objectType': 'person',
  'displayName': 'Alice Foo',
  'id': tag_uri('alice'),
  'numeric_id': '777',
  'username': 'alice',
  'url': 'https://twitter.com/alice',
}
ACTOR_3 = {
  'objectType': 'person',
  'displayName': 'Bob Bar',
  'id': tag_uri('bob'),
  'numeric_id': '666',
  'username': 'bob',
  'url': 'https://twitter.com/bob',
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
        'id': 'picture1',
        'media_url_https': 'https://p.twimg.com/picture1',
        'media_url': 'should ignore',
        'url': 'http://t.co/picture',
        'expanded_url': 'http://the/picture1',
        'display_url': 'http://pic.twitter.com/1',
        'indices': [83, 102],
        'type': 'photo',
        'ext_alt_text': 'the alt text',
     }, {
        # duplicated in extended_entities; we should de-dupe
        'id': 'picture3',
        'media_url': 'http://p.twimg.com/picture3',
        'type': 'photo',
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
      'type': 'photo',
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
  'image': {'url': 'http://p.twimg.com/picture2'},
  'location': {
    'displayName': 'Carcassonne, Aude',
    'id': tag_uri('31cb9e7ed29dbe52'),
    'url': 'https://maps.google.com/maps?q=32.4004416,-98.9852672',
  },
  'to': [{'objectType': 'group', 'alias': '@public'}],
  'tags': [{
    'objectType': 'mention',
    'id': tag_uri('foo'),
    'url': 'https://twitter.com/foo',
    'displayName': 'Twitter',
    'startIndex': 0,
    'length': 8,
  }, {
    'objectType': 'mention',
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
    'image': {'url': 'http://p.twimg.com/picture2'},
  }, {
    'image': {'url': 'http://p.twimg.com/picture3'},
  }, {
    'objectType': 'image',
    'image': {
      'url': 'https://p.twimg.com/picture1',
      'displayName': 'the alt text',
    },
    'displayName': 'the alt text',
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
LIKES_SCRAPED = {
  'globalObjects': {
    'tweets': None,
    'users': {
      '353': {
        'id_str': '353',
        'name': 'George',
        'screen_name': 'ge',
        'profile_image_url_https': 'https://twimg/353',
      },
      '???': {
        'screen_name': 'jo',
      },
      '23238890': {
        'id_str': '23238890',
        'name': 'Charles ☕ Foo',
        'screen_name': 'c_foo',
        'profile_image_url_https': 'https://pbs.twimg.com/profile_images/123/abc.jpg',
      },
    }
  }
}
LIKE_OBJECTS = [{  # ActivityStreams
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
    'displayName': 'Charles ☕ Foo',
    'url': 'https://twitter.com/c_foo',
    'image': {'url': 'https://pbs.twimg.com/profile_images/123/abc.jpg'},
  },
}]
OBJECT_WITH_LIKES = copy.deepcopy(OBJECT)
OBJECT_WITH_LIKES['tags'] += LIKE_OBJECTS
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
      'display_url': 'twitter.com/schnar…',
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
<generator uri="https://granary.io/">granary</generator>
<id>%(host_url)s</id>
<title>User feed for Ryan Barrett</title>

<subtitle>my description</subtitle>

<logo>http://a0.twimg.com/profile_images/866165047/ryan.jpg</logo>
<updated>2012-02-22T20:26:41+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://twitter.com/snarfed_org</uri>
 <name>Ryan Barrett</name>
</author>

<link rel="alternate" href="%(host_url)s" type="text/html" />
<link rel="alternate" href="https://twitter.com/snarfed_org" type="text/html" />
<link rel="avatar" href="http://a0.twimg.com/profile_images/866165047/ryan.jpg" />
<link rel="self" href="%(request_url)s" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://twitter.com/snarfed_org</uri>
 <name>Ryan Barrett</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/note</activity:object-type>

  <id>tag:twitter.com:100</id>
  <title>@twitter meets @seepicturely at #tcdisrupt &lt;3 first instagr.am/p/MuW67</title>

  <content type="html"><![CDATA[

<a href="https://twitter.com/foo">@twitter</a> meets @seepicturely at <a href="https://twitter.com/search?q=%%23tcdisrupt">#tcdisrupt</a> &lt;3 <a href="http://first/link/">first</a> <a href="http://instagr.am/p/MuW67/">instagr.am/p/MuW67</a>
<p>
<a class="link" href="https://twitter.com/snarfed_org/status/100">
<img class="u-photo" src="http://p.twimg.com/picture2" alt="" />
</a>
</p>
<p>
<a class="link" href="https://twitter.com/snarfed_org/status/100">
<img class="u-photo" src="http://p.twimg.com/picture3" alt="" />
</a>
</p>
<p>
<a class="link" href="https://twitter.com/snarfed_org/status/100">
<img class="u-photo" src="https://p.twimg.com/picture1" alt="the alt text" />
</a>
</p>
<p>  <span class="p-location h-card">
<data class="p-uid" value="tag:twitter.com:31cb9e7ed29dbe52"></data>
<a class="p-name u-url" href="https://maps.google.com/maps?q=32.4004416,-98.9852672">Carcassonne, Aude</a>

</span>
</p>

  ]]></content>

  <link rel="alternate" type="text/html" href="https://twitter.com/snarfed_org/status/100" />
  <link rel="ostatus:conversation" href="https://twitter.com/snarfed_org/status/100" />

    <link rel="ostatus:attention" href="https://twitter.com/foo" />
    <link rel="mentioned" href="https://twitter.com/foo" />

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

  <link rel="self" href="https://twitter.com/snarfed_org/status/100" />

<link rel="enclosure" href="http://p.twimg.com/picture2" type="" />
<link rel="enclosure" href="https://p.twimg.com/picture1" type="" />
</entry>

</feed>
"""


class TwitterTest(testutil.TestCase):

  def setUp(self):
    super().setUp()
    twitter_auth.TWITTER_APP_KEY = 'fake'
    twitter_auth.TWITTER_APP_SECRET = 'fake'
    self.twitter = twitter.Twitter('key', 'secret')
    self.mock_urlopen = self.start_patch(util.urllib.request, 'urlopen')
    self.mock_get = self.start_patch(util.session, 'get')
    self.mock_post = self.start_patch(util.session, 'post')

  def urlopen_returns(self, resp, status=200, headers={}):
    """Minimal helper for setting urlopen results.

    Needed because many tests call urlopen multiple times, and we reuse
    UrlopenResults, and they have a pointer into the response buffer that seeks and
    doesn't reset.
    """
    if not isinstance(resp, str):
      resp = json_dumps(resp)

    self.mock_urlopen.return_value = UrlopenResult(status, resp, headers=headers)

  def assert_urlopen(self, url):
    """Assert mock_urlopen was called with this URL (full or relative to API_BASE)."""
    if not url.startswith('http'):
      url = twitter.API_BASE + url
    super().assert_urlopen(url)

  def test_get_actor(self):
    self.urlopen_returns(USER)
    self.assert_equals(ACTOR, self.twitter.get_actor('foo'))
    self.assert_urlopen('users/show.json?screen_name=foo')

  def test_get_actor_default(self):
    self.urlopen_returns(USER)
    self.assert_equals(ACTOR, self.twitter.get_actor())
    self.assert_urlopen('account/verify_credentials.json')

  def test_get_activities(self):
    self.urlopen_returns([TWEET, TWEET])
    self.assert_equals([ACTIVITY, ACTIVITY], self.twitter.get_activities())
    self.assert_urlopen(TIMELINE)

  def test_get_activities_start_index_count(self):
    self.urlopen_returns([TWEET, TWEET_2])
    self.assert_equals([ACTIVITY_2],
                       self.twitter.get_activities(start_index=1, count=1))
    self.assert_urlopen(API_TIMELINE % 2)

  def test_get_activities_start_index_count_zero(self):
    self.urlopen_returns([TWEET, TWEET_2])
    self.assert_equals([ACTIVITY, ACTIVITY_2],
                       self.twitter.get_activities(start_index=0, count=0))
    self.assert_urlopen(API_TIMELINE % 0)

  def test_get_activities_count_past_end(self):
    self.urlopen_returns([TWEET])
    self.assert_equals([ACTIVITY], self.twitter.get_activities(count=9))
    self.assert_urlopen(API_TIMELINE % 9)

  def test_get_activities_start_index_past_end(self):
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(start_index=9))
    self.assert_urlopen(API_TIMELINE % 0)

  def test_get_activities_activity_id(self):
    self.urlopen_returns(TWEET)
    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals([ACTIVITY], self.twitter.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))
    self.assert_urlopen(API_STATUS % 0)

  def test_get_activities_bad_user_id(self):
    """https://console.cloud.google.com/errors/CKWWrPrqy-21NQ"""
    self.assertRaises(ValueError, self.twitter.get_activities,
                      user_id='Foo Bar')

  def test_get_activities_bad_activity_id(self):
    """https://github.com/snarfed/bridgy/issues/719"""
    self.assertRaises(ValueError, self.twitter.get_activities,
                      activity_id='123:abc')

  def test_get_activities_activity_id_with_space(self):
    self.urlopen_returns(TWEET)
    self.assert_equals([ACTIVITY], self.twitter.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000 '))
    self.assert_urlopen(API_STATUS % 0)

  def test_get_activities_self(self):
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(group_id=source.SELF))
    self.assert_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': ''})

  def test_get_activities_self_fetch_likes(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, [TWEET_2]),
      UrlopenResult(200, FAVORITE_EVENT['source']),
      UrlopenResult(200, [TWEET]),
    ]
    self.twitter = twitter.Twitter('key', 'secret', scrape_headers={'x': 'y'})
    got = self.twitter.get_activities(group_id=source.SELF, fetch_likes=True)
    like_obj = copy.copy(LIKE_OBJ)
    del like_obj['published']
    self.assert_equals([like_obj, ACTIVITY], got)
    self.assert_urlopen(API_FAVORITES % '')
    self.assert_urlopen('account/verify_credentials.json')
    self.assert_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': ''})

  def test_get_activities_for_screen_name(self):
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(user_id='schnarfed',
                                                       group_id=source.SELF))
    self.assert_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': 'schnarfed'})

    # @ prefix should also work
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(user_id='@schnarfed',
                                                       group_id=source.SELF))
    self.assert_urlopen(API_USER_TIMELINE % {'count': 0, 'screen_name': 'schnarfed'})

  def test_get_activities_list_explicit_user(self):
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(group_id='testlist',
                                                       user_id='schnarfed'))
    self.assert_urlopen(API_LIST_TIMELINE % {
      'count': 0,
      'slug': 'testlist',
      'owner_screen_name': 'schnarfed',
    })

  def test_get_activities_list_implicit_user(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, {'screen_name': 'schnarfed'}),
      UrlopenResult(200, []),
    ]
    self.assert_equals([], self.twitter.get_activities(group_id='testlist'))
    self.assert_urlopen('account/verify_credentials.json')
    self.assert_urlopen(API_LIST_TIMELINE % {
      'count': 0,
      'slug': 'testlist',
      'owner_screen_name': 'schnarfed',
    })

  def test_get_activities_list_url_encode(self):
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(
      group_id='foo &bar', user_id='schnarfed'))
    self.assert_urlopen(API_LIST_TIMELINE % {
      'count': 0,
      'slug': 'foo%20%26bar',
      'owner_screen_name': 'schnarfed',
    })

  def test_get_activities_list_id(self):
    self.urlopen_returns([])
    self.assert_equals([], self.twitter.get_activities(group_id='123'))
    self.assert_urlopen(API_LIST_ID_TIMELINE % {'count': 0, 'list_id': '123'})

  def test_get_activities_fetch_replies(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, [TWEET]),
      UrlopenResult(200, REPLIES_TO_SNARFED),
      UrlopenResult(200, REPLIES_TO_ALICE),
      UrlopenResult(200, REPLIES_TO_BOB),
    ]
    self.assert_equals([ACTIVITY_WITH_REPLIES],
                       self.twitter.get_activities(fetch_replies=True, min_id='567'))
    search = API_SEARCH + '&since_id=567'
    self.assert_urlopen(TIMELINE)
    self.assert_urlopen(search % {'q': '%40snarfed_org', 'count': 100})
    self.assert_urlopen(search % {'q': '%40alice', 'count': 100})
    self.assert_urlopen(search % {'q': '%40bob', 'count': 100})

  def test_get_activities_fetch_mentions(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, []),
      UrlopenResult(200, {'screen_name': 'schnarfed'}),
      UrlopenResult(200, {
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
        ]}),
      UrlopenResult(200, 
        [{'id_str': '11', 'user': {'screen_name': 'schnarfed'}},
         {'id_str': '12', 'entities': {'user_mentions': [{'screen_name': 'schnarfed'}]}},
         {'id_str': '13', 'text': 'barrey'},
        ]),
    ]
    # fetch_replies as well as fetch_mentions to make sure we don't try to find
    # replies to the mentions. https://github.com/snarfed/bridgy/issues/631
    got = self.twitter.get_activities(fetch_mentions=True, fetch_replies=True,
                                      min_id='567')
    self.assert_equals([tag_uri('3'), tag_uri('4')], [a['id'] for a in got])
    self.assert_urlopen(TIMELINE)
    self.assert_urlopen('account/verify_credentials.json')
    self.assert_urlopen(
      API_SEARCH % {'q': '%40schnarfed', 'count': 100} + '&since_id=567')
    self.assert_urlopen(API_LOOKUP % '11,12,13')

  def test_get_activities_quote_tweets(self):
    twitter.QUOTE_SEARCH_BATCH_SIZE = 5  # reduce the batch size for testing
    # search for 8 tweets to make sure we split them up into groups of <= 5
    tweets = []
    for id in range(1000, 1008):
      tweet = copy.deepcopy(TWEET)
      tweet['id'] = id
      tweet['id_str'] = str(id)
      tweets.append(tweet)

    # second search finds a quote tweet for 1006 and an RT of that
    quote_tweet = copy.deepcopy(QUOTE_TWEET)
    quote_tweet['quoted_status_id_str'] = '1006'
    retweeted_quote_tweet = copy.deepcopy(RETWEETED_QUOTE_TWEET)
    retweeted_quote_tweet['quoted_status_id_str'] = '1006'

    self.mock_urlopen.side_effect = [
      UrlopenResult(200, tweets),
      # search @-mentions returns nothing
      UrlopenResult(200, {'screen_name': 'schnarfed'}),
      UrlopenResult(200, {'statuses': []}),
      # first search returns no results
      UrlopenResult(200, {'statuses': []}),
      # second search finds a quote tweet for 1006 and an RT of that
      UrlopenResult(200, {'statuses': [quote_tweet, retweeted_quote_tweet]}),
    ]
    got = self.twitter.get_activities(fetch_mentions=True, min_id='567')
    self.assertEqual(9, len(got))

    # should include quote tweet
    self.assert_equals(QUOTE_ACTIVITY, got[-1])

    # shouldn't include RT of quote tweet
    self.assertNotIn('tag:twitter.com:6789', [a.get('id') for a in got])
    self.assert_urlopen(TIMELINE)
    self.assert_urlopen('account/verify_credentials.json')
    self.assert_urlopen(twitter.API_SEARCH % {
      'q': urllib.parse.quote_plus('@schnarfed'),
      'count': 100,
    } + '&since_id=567')
    self.assert_urlopen(twitter.API_SEARCH % {
      'q': urllib.parse.quote_plus('1000 OR 1001 OR 1002 OR 1003 OR 1004'),
      'count': 100,
    } + '&since_id=567')
    self.assert_urlopen(twitter.API_SEARCH % {
      'q': urllib.parse.quote_plus('1005 OR 1006 OR 1007'),
      'count': 100,
    } + '&since_id=567')

  def test_get_activities_include_shares_false(self):
    self.urlopen_returns([TWEET] + RETWEETS + [TWEET_2])
    self.assert_equals([ACTIVITY, ACTIVITY_2],
                       self.twitter.get_activities(include_shares=False))
    self.assert_urlopen(TIMELINE)

  def test_get_activities_fetch_shares(self):
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, [tweet]),
      UrlopenResult(200, RETWEETS),
    ]
    self.assert_equals([ACTIVITY_WITH_SHARES],
                       self.twitter.get_activities(fetch_shares=True, min_id='567'))
    self.assert_urlopen(TIMELINE)
    self.assert_urlopen(API_RETWEETS % '100' + '&since_id=567')

  def test_get_activities_fetch_shares_404s(self):
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, [tweet]),
      urllib.error.HTTPError('url', 404, 'msg', {}, None),
    ]
    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_shares=True))
    self.assert_urlopen(TIMELINE)
    self.assert_urlopen(API_RETWEETS % '100')

  def test_get_activities_fetch_shares_403s_error_code_200(self):
    """https://github.com/snarfed/bridgy/issues/688#issuecomment-520600329"""
    tweet = copy.deepcopy(TWEET)
    tweet['retweet_count'] = 1
    resp = json_dumps({
      'errors': [{
        'code': 200,
        'message': 'Forbidden.',
      }],
    })
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, [tweet]),
      urllib.error.HTTPError('url', 403, resp, {}, None),
    ]
    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_shares=True))
    self.assert_urlopen(TIMELINE)
    self.assert_urlopen(API_RETWEETS % '100')

  def test_get_activities_fetch_shares_no_retweets(self):
    self.urlopen_returns([TWEET])
    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_shares=True))
    self.assert_urlopen(TIMELINE)

  def test_get_activities_fetch_cache(self):
    tweets = [copy.deepcopy(TWEET), copy.deepcopy(TWEET)]
    tweets[0]['id_str'] += '_a'
    tweets[1]['id_str'] += '_b'

    urlopen_side_effect = []
    session_get_side_effect = []
    for count in (1, 2):
      for t in tweets:
        t['retweet_count'] = t['favorite_count'] = count
      urlopen_side_effect += [
        UrlopenResult(200, tweets),
        UrlopenResult(200, []),
        UrlopenResult(200, []),
        # shouldn't fetch this time because counts haven't changed
        UrlopenResult(200, tweets),
      ]
      session_get_side_effect += [
        requests_response({}),
        requests_response({'globalObjects': {'users': {}}}),
      ]

    self.mock_urlopen.side_effect = urlopen_side_effect
    self.mock_get.side_effect = session_get_side_effect
    self.twitter = twitter.Twitter('key', 'secret', scrape_headers={'x': 'y'})
    cache = {}
    for _ in range(4):
      self.twitter.get_activities(fetch_shares=True, fetch_likes=True,
                                  cache=cache)

  def test_get_activities_fetch_likes_no_scrape_headers(self):
    with self.assertRaises(NotImplementedError):
      self.twitter.get_activities(fetch_likes=True)

  def test_get_activities_fetch_likes(self):
    tweet = copy.deepcopy(TWEET)
    tweet['favorite_count'] = 1
    self.urlopen_returns([tweet])
    self.mock_get.return_value = requests_response(LIKES_SCRAPED)
    self.twitter = twitter.Twitter('key', 'secret', scrape_headers={'x': 'y'})
    cache = {}
    self.assert_equals([ACTIVITY_WITH_LIKES],
                       self.twitter.get_activities(fetch_likes=True, cache=cache))
    self.assert_equals(1, cache['ATF 100'])
    self.assert_urlopen(TIMELINE)

  def test_get_activities_favorites_404(self):
    tweet = copy.deepcopy(TWEET)
    tweet['favorite_count'] = 1
    self.urlopen_returns([tweet])
    self.mock_get.side_effect = RequestException('url')
    cache = {}
    self.twitter = twitter.Twitter('key', 'secret', scrape_headers={'x': 'y'})
    self.assert_equals([ACTIVITY],
                       self.twitter.get_activities(fetch_likes=True, cache=cache))
    self.assertNotIn('ATF 100', cache)
    self.assert_urlopen(TIMELINE)

  def test_get_activities_fetch_likes_no_favorites(self):
    self.urlopen_returns([TWEET])
    # we should only ask the API for retweets when favorites_count > 0
    self.twitter = twitter.Twitter('key', 'secret', scrape_headers={'x': 'y'})
    self.assert_equals([ACTIVITY], self.twitter.get_activities(fetch_likes=True))
    self.assert_urlopen(TIMELINE)

  def test_get_activities_private_activity_skips_fetch_likes_and_retweets(self):
    tweet = copy.deepcopy(TWEET)
    tweet['user']['protected'] = True
    tweet['favorite_count'] = tweet['retweet_count'] = 1
    self.urlopen_returns([tweet])
    # no HTML favorites fetch or /statuses/retweets API call
    activity = copy.deepcopy(ACTIVITY)
    activity['object']['to'][0]['alias'] = '@private'
    self.twitter = twitter.Twitter('key', 'secret', scrape_headers={'x': 'y'})
    self.assert_equals([activity], self.twitter.get_activities(
      fetch_likes=True, fetch_shares=True))
    self.assert_urlopen(TIMELINE)

  def test_retweet_limit(self):
    tweets = [{**copy.deepcopy(TWEET), 'id_str': str(i), 'retweet_count': 1}
              for i in range(1, RETWEET_LIMIT + 2)]
    self.mock_urlopen.side_effect = (
      [UrlopenResult(200, tweets)] +
      [UrlopenResult(200, RETWEETS) for _ in range(1, RETWEET_LIMIT + 1)]
    )
    self.twitter.get_activities(fetch_shares=True)
    self.assert_urlopen(TIMELINE)
    for i in range(1, RETWEET_LIMIT + 1):
      self.assert_urlopen(API_RETWEETS % i)

  def test_get_activities_request_etag(self):
    self.urlopen_returns([])
    self.twitter.get_activities_response(etag='"my etag"')
    self.assert_urlopen(TIMELINE)

  def test_get_activities_response_etag(self):
    self.urlopen_returns([], headers={'ETag': '"my etag"'})
    self.assert_equals('"my etag"', self.twitter.get_activities_response()['etag'])
    self.assert_urlopen(TIMELINE)

  def test_get_activities_304_not_modified(self):
    """Requests with matching ETags return 304 Not Modified."""
    self.mock_urlopen.side_effect = urllib.error.HTTPError(
      'url', 304, 'Not Modified', {}, None)
    self.assert_equals([], self.twitter.get_activities_response()['items'])

  def test_get_activities_min_id(self):
    """min_id shouldn't be passed to the initial request, just the derived ones."""
    self.urlopen_returns([])
    self.twitter.get_activities_response(min_id=135)
    self.assert_urlopen(TIMELINE)

  def test_get_activities_retries(self):
    for exc in (http.client.HTTPException('Deadline exceeded: foo'),
                socket.timeout('asdf'),
                urllib.error.HTTPError('url', 501, 'msg', {}, None)):
      self.mock_urlopen.side_effect = (
        [exc] * twitter.RETRIES + [UrlopenResult(200, [])]
      )
      self.assertEqual([], self.twitter.get_activities_response()['items'])

    # other exceptions shouldn't retry
    for exc in (http.client.HTTPException('not a deadline'),
                urllib.error.HTTPError('url', 403, 'not a 5xx', {}, None)):
      self.mock_urlopen.side_effect = exc
      self.assertRaises(exc.__class__, self.twitter.get_activities_response)

  def test_get_activities_search(self):
    self.urlopen_returns({
      'statuses': [TWEET, TWEET],
      'search_metadata': {
        'max_id': 250126199840518145,
      },
    })
    self.assert_equals(
      [ACTIVITY, ACTIVITY], self.twitter.get_activities(
        group_id=source.SEARCH, search_query='indieweb'))
    self.assert_urlopen(twitter.API_SEARCH % {'q': 'indieweb', 'count': 0})

  def test_get_activities_search_no_query(self):
    with self.assertRaises(ValueError):
      self.twitter.get_activities(group_id=source.SEARCH, search_query=None)

  def test_get_activities_search_with_unicode_char(self):
    self.urlopen_returns({'statuses': []})
    self.assert_equals([], self.twitter.get_activities(
        group_id=source.SEARCH, search_query='☕ foo'))
    self.assert_urlopen(twitter.API_SEARCH % {'q': '%E2%98%95+foo', 'count': 0})

  def test_get_comment(self):
    self.urlopen_returns(TWEET)
    self.assert_equals(OBJECT, self.twitter.get_comment('123'))
    self.assert_urlopen(API_STATUS % '123')

  def test_get_comment_bad_comment_id(self):
    """https://github.com/snarfed/bridgy/issues/719"""
    self.assertRaises(ValueError, self.twitter.get_comment, '123:abc')

  def test_get_share(self):
    self.urlopen_returns(RETWEETS[0])
    self.assert_equals(SHARES[0], self.twitter.get_share('user', 'tweet', '123'))
    self.assert_urlopen(API_STATUS % '123')

  def test_get_share_bad_id(self):
    """https://github.com/snarfed/bridgy/issues/719"""
    self.assertRaises(ValueError, self.twitter.get_share, None, None, '123:abc')

  def test_get_blocklist(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, {'users': [USER], 'next_cursor_str': '9'}),
      UrlopenResult(200, {'users': [USER_2, USER_3], 'next_cursor_str': '0'}),
    ]
    self.assert_equals([ACTOR, ACTOR_2, ACTOR_3], self.twitter.get_blocklist())
    self.assert_urlopen(API_BLOCKS % '-1')
    self.assert_urlopen(API_BLOCKS % '9')

  def test_get_blocklist_rate_limited(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, {'users': [USER], 'next_cursor_str': '3'}),
      UrlopenResult(200, {'users': [USER_2, USER_3], 'next_cursor_str': '6'}),
      urllib.error.HTTPError('url', 429, 'Too Many Requests', {}, None),
    ]
    with self.assertRaises(source.RateLimited) as e:
      self.twitter.get_blocklist()

    self.assertEqual([ACTOR, ACTOR_2, ACTOR_3], e.exception.partial)
    self.assert_urlopen(API_BLOCKS % '-1')
    self.assert_urlopen(API_BLOCKS % '3')
    self.assert_urlopen(API_BLOCKS % '6')

  def test_get_blocklist_other_http_error(self):
    self.mock_urlopen.side_effect = urllib.error.HTTPError('url', 406, 'Not Acceptable', {}, None)
    with self.assertRaises(urllib.error.HTTPError) as e:
      self.twitter.get_blocklist()
    self.assertEqual(406, e.exception.code)
    self.assert_urlopen(API_BLOCKS % '-1')

  def test_get_blocklist_ids(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, {'ids': ['1', '2'], 'next_cursor_str': '9'}),
      UrlopenResult(200, {'ids': ['4', '5'], 'next_cursor_str': '0'}),
    ]
    self.assert_equals(['1', '2', '4', '5'], self.twitter.get_blocklist_ids())
    self.assert_urlopen(API_BLOCK_IDS % '-1')
    self.assert_urlopen(API_BLOCK_IDS % '9')

  def test_get_blocklist_ids_rate_limited(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, {'ids': ['1', '2'], 'next_cursor_str': '3'}),
      UrlopenResult(200, {'ids': ['4', '5'], 'next_cursor_str': '6'}),
      urllib.error.HTTPError('url', 429, 'Too Many Requests', {}, None),
    ]
    with self.assertRaises(source.RateLimited) as e:
      self.twitter.get_blocklist_ids()

    self.assertEqual(['1', '2', '4', '5'], e.exception.partial)
    self.assert_urlopen(API_BLOCK_IDS % '-1')
    self.assert_urlopen(API_BLOCK_IDS % '3')
    self.assert_urlopen(API_BLOCK_IDS % '6')

  def test_tweet_to_as1_activity_full(self):
    self.assert_equals(ACTIVITY, self.twitter.tweet_to_as1_activity(TWEET))

  def test_tweet_to_as1_activity_minimal(self):
    # just test that we don't crash
    self.twitter.tweet_to_as1_activity({'id': 123, 'text': 'asdf'})

  def test_tweet_to_as1_activity_empty(self):
    # just test that we don't crash
    self.twitter.tweet_to_as1_activity({})

  def test_quote_tweet_to_as1_activity(self):
    self.assert_equals(QUOTE_ACTIVITY, self.twitter.tweet_to_as1_activity(QUOTE_TWEET))

  def test_quote_tweet_to_as1_activity_without_quoted_tweet_url_entity(self):
    quote_tweet = copy.deepcopy(QUOTE_TWEET)
    quote_tweet['entities']['urls'][0]['expanded_url'] = 'http://foo/bar'

    self.assert_equals('I agree with this twitter.com/schnar…',
                       self.twitter.tweet_to_as1_activity(quote_tweet)['object']['content'])

    del quote_tweet['entities']
    self.assert_equals('I agree with this https://t.co/ww6HD8KroG',
                       self.twitter.tweet_to_as1_activity(quote_tweet)['object']['content'])

  def test_remove_quote_tweet_link(self):
    """https://twitter.com/orbuch/status/1386432051751030788"""
    self.assert_equals({
      'objectType': 'note',
      'id': 'tag:twitter.com:1386432051751030788',
      'attachments': [{
        'objectType': 'note',
        'id': 'tag:twitter.com:1386425010223423490',
        'url': 'https://twitter.com/drvolts/status/1386425010223423490',
        'author': {
          'objectType': 'person',
          'id': 'tag:twitter.com:drvolts',
          'numeric_id': '22737278',
          'displayName': 'drvolts',
          'url': 'https://twitter.com/drvolts',
          'username': 'drvolts',
        },
      }],
    }, self.twitter.tweet_to_as1_object({
      'id_str' : '1386432051751030788',
      'full_text' : 'https://t.co/kp2kgqV7Yx',
      'entities' : {
        'urls' : [{
          'url' : 'https://t.co/kp2kgqV7Yx',
          'display_url' : 'twitter.com/drvolts/status…',
          'expanded_url' : 'https://twitter.com/drvolts/status/1386425010223423490',
          'indices' : [0, 23]
        }],
      },
      'quoted_status' : {
        'id_str' : '1386425010223423490',
        'user' : {
          'screen_name' : 'drvolts',
          'id_str' : '22737278',
          'url' : 'https://t.co/SjJyrHY9Mx',
        },
      },
    }))

  def test_remove_quote_tweet_link_with_photo(self):
    """https://twitter.com/bradfitz/status/1382912988835848199"""
    self.assert_equals({
      'objectType': 'note',
      'id': 'tag:twitter.com:1382912988835848199',
      'content': "Kid isn't quite to chess yet, but working on the simul puzzles... ",
      'image': {'url': 'https://pbs.twimg.com/media/EzEX1VJVEAYK9tp.jpg'},
      'attachments': [{
        'image': {'url': 'https://pbs.twimg.com/media/EzEX1VJVEAYK9tp.jpg'},
        'objectType': 'image',
      }, {
        'objectType': 'note',
        'id': 'tag:twitter.com:1382705862263853066',
        'content': 'Kasparov in simul play in the 1980s.',
      }],
    } , self.twitter.tweet_to_as1_object({
      'id_str' : '1382912988835848199',
      'full_text' : "Kid isn't quite to chess yet, but working on the simul puzzles... https://t.co/gXs8YWcWOM https://t.co/7BfZyXQn4q",
      'display_text_range' : [0, 89],
      'entities' : {
        'media' : [{
          'display_url' : 'pic.twitter.com/7BfZyXQn4q',
          'expanded_url' : 'https://twitter.com/bradfitz/status/1382912988835848199/photo/1',
          'id_str' : '1382912765556232198',
          'indices' : [90, 113],
          'media_url_https' : 'https://pbs.twimg.com/media/EzEX1VJVEAYK9tp.jpg',
          'type' : 'photo',
          'url' : 'https://t.co/7BfZyXQn4q',
        }],
        'urls' : [{
          'display_url' : 'twitter.com/olimpiuurcan/s…',
          'expanded_url' : 'https://twitter.com/olimpiuurcan/status/1382705862263853066',
          'indices' : [66, 89],
          'url' : 'https://t.co/gXs8YWcWOM',
        }],
      },
      'is_quote_status' : True,
      'quoted_status_id_str' : '1382705862263853066',
      'quoted_status' : {
        'display_text_range' : [0, 36],
        'full_text' : 'Kasparov in simul play in the 1980s. https://t.co/gXJ088nBKU',
        'id_str' : '1382705862263853066',
      },
      'quoted_status_permalink' : {
        'expanded' : 'https://twitter.com/olimpiuurcan/status/1382705862263853066',
      },
    }))

  def test_tweet_to_as1_object_unicode_high_code_points(self):
    """Test Unicode high code point chars.

    The first three unicode chars in the text are the '100' emoji, which is a
    high code point, ie above the Basic Multi-lingual Plane (ie 16 bits). The
    emacs font i use doesn't render it, so it looks blank.

    First discovered in https://twitter.com/schnarfed/status/831552681210556416
    """
    obj = self.twitter.tweet_to_as1_object({
      'id_str': '831552681210556416',
      'text': '💯💯💯 (by @itsmaeril) https://t.co/pWrOHzuHkP',
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
    self.assert_equals('💯💯💯 (by @itsmaeril) ', obj['content'])
    self.assert_equals(
      '💯💯💯 (by <a href="https://twitter.com/itsmaeril">@itsmaeril</a>) ',
      microformats2.render_content(obj).splitlines()[0])

  def test_tweet_to_as1_object_full(self):
    self.assert_equals(OBJECT, self.twitter.tweet_to_as1_object(TWEET))

  def test_tweet_to_as1_object_minimal(self):
    # just test that we don't crash
    self.twitter.tweet_to_as1_object({'id': 123, 'text': 'asdf'})

  def test_tweet_to_as1_object_empty(self):
    self.assert_equals({}, self.twitter.tweet_to_as1_object({}))

  def test_tweet_to_as1_object_with_retweets(self):
    self.assert_equals(OBJECT_WITH_SHARES,
                          self.twitter.tweet_to_as1_object(TWEET_WITH_RETWEETS))

  def test_tweet_to_as1_activity_display_text_range(self):
    self.assert_equals({
      'objectType': 'note',
      # should only have the text inside display_text_range
      'content': 'i hereby reply',
      'id': tag_uri('100'),
      # both tags are outside display_text_range, so they shouldn't have
      # startIndex or length
      'tags': [{
        'objectType': 'mention',
        'id': tag_uri('OP'),
        'url': 'https://twitter.com/OP',
      }, {
        'objectType': 'article',
        'url': 'http://full/quoted/tweet',
      }],
      'to': [{
        'objectType': 'mention',
        'id': tag_uri('OP'),
        'url': 'https://twitter.com/OP',
      }],
    }, self.twitter.tweet_to_as1_object({
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

  def test_tweet_to_as1_object_entity_indices_handle_display_urls(self):
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

    obj = self.twitter.tweet_to_as1_object(tweet)
    for tag in obj['tags']:
      if tag['displayName'] == 'Dan Shipper':
        self.assertEqual(91, tag['startIndex'])
        self.assertEqual(11, tag['length'])
        break
    else:
      self.fail('Dan Shipper not found')

    self.assertEqual('Hey Ryan, You might find this semi-related and interesting: <a href="https://www.onename.io/">onename.io</a> Heard about it from <a href="https://twitter.com/danshipper">@danshipper</a> this week.',
                      microformats2.render_content(obj))

  def test_tweet_to_as1_object_multiple_entities_for_same_url(self):
    self.assertEqual({
      'content': 'a-link a-link',
      'id': 'tag:twitter.com:123',
      'objectType': 'note',
      'tags': [{
        'objectType': 'article',
        'url': 'https://a/link',
        'displayName': 'a-link',
        'startIndex': 0,
        'length': 6,
      }, {
        'objectType': 'article',
        'url': 'https://a/link',
        'displayName': 'a-link',
        'startIndex': 7,
        'length': 6,
      }]}, self.twitter.tweet_to_as1_object({
        'id_str': '123',
        'full_text': 'http://t.co/1 http://t.co/1',
        'entities': {
          'urls': [{
            'url': 'http://t.co/1',
            'expanded_url': 'https://a/link',
            'display_url': 'a-link',
            'indices': [0, 13],
          }, {
            'url': 'http://t.co/1',
            'expanded_url': 'https://a/link',
            'display_url': 'a-link',
            'indices': [14, 27],
          }],
        },
      }))

  def test_tweet_to_as1_object_retweet_with_entities(self):
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

    obj = self.twitter.tweet_to_as1_object(tweet)
    self.assert_equals([{
      'objectType': 'mention',
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

  def test_tweet_to_as1_object_multiple_pictures_only_one_picture_link(self):
    self.assert_equals({
      'id': tag_uri('726480459488587776'),
      'objectType': 'note',
      'content': '☑ Harley Davidson Museum® ☑ Schlitz .... ☑ Milwaukee ',
    }, self.twitter.tweet_to_as1_object({
      'id_str': '726480459488587776',
      'text': '☑ Harley Davidson Museum® ☑ Schlitz .... ☑ Milwaukee https://t.co/6Ta5P8A2cs',
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

  def test_tweet_to_as1_object_preserve_whitespace(self):
    text = r"""\
  ( •_•)                           (•_• ) 
  ( ง )ง                           ୧( ୧ )
   /︶\                             /︶\ """
    tweet = {
      'id_str': '1',
      'full_text': text,
    }
    obj = {
      'objectType': 'note',
      'id': tag_uri('1'),
      'content': text,
    }
    self.assert_equals(obj, self.twitter.tweet_to_as1_object(tweet))

  def test_reply_tweet_to_as1_activity(self):
    tweet = copy.deepcopy(TWEET)
    tweet.update({
      'in_reply_to_screen_name': 'other_user',
      'in_reply_to_status_id': 789,
    })
    expected = [{
      'url' : 'https://twitter.com/other_user/status/789',
      'id' : tag_uri('789'),
    }]

    activity = self.twitter.tweet_to_as1_activity(tweet)
    self.assert_equals({'inReplyTo': expected}, activity['context'])
    self.assert_equals(expected, activity['object']['inReplyTo'])

    direct_obj = self.twitter.tweet_to_as1_object(tweet)
    self.assert_equals(expected, direct_obj['inReplyTo'])

  def test_tweet_to_as1_activity_on_retweet(self):
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
      self.twitter.tweet_to_as1_activity({
        'id_str': '444',
        'text': 'truncated',
        'user': {'id': 888, 'screen_name': 'rt_author'},
        'retweeted_status': {
          'id_str': '333',
          'text': 'my long original tweet',
          'user': {'id': 777, 'screen_name': 'orig_author'},
          },
        }))

  def test_tweet_to_as1_activity_retweet_of_quote_tweet(self):
    self.assert_equals(QUOTE_SHARE,
                       self.twitter.tweet_to_as1_activity(RETWEETED_QUOTE_TWEET))

  def test_protected_tweet_to_as1_object(self):
    tweet = copy.deepcopy(TWEET)
    tweet['user']['protected'] = True
    obj = copy.deepcopy(OBJECT)
    obj['to'][0]['alias'] = '@private'
    self.assert_equals(obj, self.twitter.tweet_to_as1_object(tweet))

  def test_retweet_to_as1(self):
    for retweet, share in zip(RETWEETS, SHARES):
      self.assert_equals(share, self.twitter.retweet_to_as1(retweet))

    # not a retweet
    self.assertEqual(None, self.twitter.retweet_to_as1(TWEET))

  def test_video_tweet_to_as1_object(self):
    tweet = copy.deepcopy(TWEET)
    media = tweet['entities']['media'][0]

    # extended_entities has full video data and type 'video'. entities just has
    # image URLs and incorrect type 'photo'. details:
    # https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/extended-entities-object
    tweet['extended_entities'] = {
      'media': [{
        'id': media['id'],     # check de-duping
        'indices': media['indices'],
        'media_url': 'http://pbs.twimg.com/tweet_video_thumb/9182.jpg',
        'media_url_https': 'https://pbs.twimg.com/tweet_video_thumb/9182.jpg',
        'url': 'https://t.co/YUY4GGWKbP',
        'display_url': 'pic.twitter.com/YUY4GGWKbP',
        'expanded_url': 'https://twitter.com/bradfitz/status/9182/photo/1',
        'type': 'animated_gif',
        'sizes': {
          'medium': {'w': 350, 'h': 310, 'resize': 'fit'},
          # ...
        },
        'video_info': {
          'aspect_ratio': [35, 31],
          'variants': [{
            'bitrate': 1,
            'content_type': 'video/mp4',
            'url': 'https://video.twimg.com/tweet_video/bad.mp4'
          }, {
            # should pick this one since it's the highest bitrate
            'bitrate': 2,
            'content_type': 'video/mp4',
            'url': 'https://video.twimg.com/tweet_video/9182.mp4'
          }, {
            # this is an HLS video (playlist) with all the different variants.
            # we should ignore it.
            #
            # https://twittercommunity.com/t/retiring-mp4-video-output-support-on-august-1st-2016/66045
            # https://twittercommunity.com/t/retiring-mp4-video-output/66093
            # https://twittercommunity.com/t/mp4-still-appears-despite-of-retiring-announcment/788
            'content_type': 'application/x-mpegURL',
            'url': 'https://video.twimg.com/ext_tw_video/9182.m3u8',
          }],
        },
      }],
    }

    obj = self.twitter.tweet_to_as1_object(tweet)
    self.assert_equals([{
      'objectType': 'video',
      'stream': {'url': 'https://video.twimg.com/tweet_video/9182.mp4'},
      'image': {'url': 'https://pbs.twimg.com/tweet_video_thumb/9182.jpg'},
    }, {
      'objectType': 'image',
      'image': {'url': 'http://p.twimg.com/picture3'},
    }], obj['attachments'])
    self.assert_equals({'url': 'https://video.twimg.com/tweet_video/9182.mp4'},
                          obj['stream'])
    self.assertNotIn('image', obj)

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
    self.assertEqual(None, self.twitter.streaming_event_to_object(follow))

  def test_to_as1_actor_full(self):
    self.assert_equals(ACTOR, self.twitter.to_as1_actor(USER))

  def test_to_as1_actor_url_fallback(self):
    user = copy.deepcopy(USER)
    del user['entities']
    actor = copy.deepcopy(ACTOR)
    del actor['urls']
    actor['url'] = 'https://twitter.com/snarfed_org'
    self.assert_equals(actor, self.twitter.to_as1_actor(user))

  def test_to_as1_actor_displayName_fallback(self):
    self.assert_equals({
      'objectType': 'person',
      'id': tag_uri('schnarfed'),
      'username': 'schnarfed',
      'displayName': 'schnarfed',
      'url': 'https://twitter.com/schnarfed',
    }, self.twitter.to_as1_actor({
      'screen_name': 'schnarfed',
    }))

  def test_to_as1_actor_minimal(self):
    # just test that we don't crash
    self.twitter.to_as1_actor({'screen_name': 'snarfed_org'})

  def test_to_as1_actor_empty(self):
    self.assert_equals({}, self.twitter.to_as1_actor({}))

  def test_oauth(self):
    self.urlopen_returns(USER)
    self.twitter.get_actor('foo')
    req = self.mock_urlopen.call_args.args[0]
    headers = dict(req.header_items())
    sig = headers['Authorization'].decode('utf-8')
    self.assertTrue(sig.startswith('OAuth '))
    self.assertIn('oauth_token="key"', sig)
    self.assertIn('oauth_signature=', sig)

  def test_urlopen_not_json(self):
    # return_value is returned for every call, so this covers all retries
    self.urlopen_returns('not json')
    with self.assertRaises(urllib.error.HTTPError) as cm:
      self.twitter.urlopen('xyz')
    self.assertEqual(502, cm.exception.code)
    self.assert_urlopen(twitter.API_BASE + 'xyz')

  def test_get_activities_not_json(self):
    self.urlopen_returns('not json')
    with self.assertRaises(urllib.error.HTTPError) as cm:
      self.twitter.get_activities()
    self.assertEqual(502, cm.exception.code)
    self.assert_urlopen(TIMELINE)

  def test_create_tweet(self):
    self.twitter.TRUNCATE_TEXT_LENGTH = 20
    self.twitter.TRUNCATE_URL_LENGTH = 5

    dots = '…'
    original = (
      'my status',
      'too long, will be ellipsized',
      'url shorten http://foo.co/bar',
      'url http://foo.co/bar ellipsyz http://foo.co/baz',
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
      'url http://foo.co/bar ellipsyz' + dots,
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
      'url <a href="http://foo.co/bar">foo.co/bar</a> ellipsyz' + dots,
      'long url <a title="foo.co/bar/baz/baj/biff/boof" href="http://www.foo.co/bar/baz/baj/biff/boof">foo.co/bar/baz/baj/bi...</a>',
      'trailing slash <a href="http://www.foo.co/">foo.co</a>',
      'fragment <a href="http://foo.co/#bar">foo.co/#bar</a>',
      'exactly twenty chars',
      'just over twenty' + dots,
      'HTML\nh & h',
      'to <a href="https://twitter.com/schnarfed">@schnarfed</a>\'s user',
      'a <a href="https://twitter.com/hashtag/hashyytag">#hashyytag</a>',
    )

    tweet = copy.deepcopy(TWEET)
    tweet.update({
        'id': '100',
        'url': 'https://twitter.com/snarfed_org/status/100',
        'type': 'post',
        })

    obj = copy.deepcopy(OBJECT)
    del obj['image']
    for preview, orig in zip(previewed, original):
      self.urlopen_returns(TWEET)
      obj['content'] = orig
      self.assert_equals(tweet, self.twitter.create(obj).content)

      got = self.twitter.preview_create(obj)
      self.assertEqual('<span class="verb">tweet</span>:', got.description)
      self.assertEqual(preview, got.content)

    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({'status': 'my status'}))

  def test_no_ellipsize_real_tweet(self):
    orig = """\
Despite names,
ind.ie&indie.vc are NOT #indieweb @indiewebcamp
indiewebcamp.com/2014-review#Indie_Term_Re-use
@iainspad @sashtown @thomatronic (ttk.me t4_81)"""

    preview = """\
Despite names,
ind.ie&indie.vc are NOT <a href="https://twitter.com/hashtag/indieweb">#indieweb</a> <a href="https://twitter.com/indiewebcamp">@indiewebcamp</a>
<a title="indiewebcamp.com/2014-review#Indie_Term_Re-use" href="http://indiewebcamp.com/2014-review#Indie_Term_Re-use">indiewebcamp.com/2014-review#In...</a>
<a href="https://twitter.com/iainspad">@iainspad</a> <a href="https://twitter.com/sashtown">@sashtown</a> <a href="https://twitter.com/thomatronic">@thomatronic</a> (ttk.me t4_81)"""

    self.urlopen_returns(TWEET)
    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj['content'] = orig.replace("\n", '<br />').replace('&', '&amp;')
    obj['url'] = 'http://tantek.com/2015/013/t1/names-ind-ie-indie-vc-not-indieweb'

    actual_preview = self.twitter.preview_create(
      obj, include_link=source.OMIT_LINK).content
    self.assertEqual(preview, actual_preview)

    self.twitter.create(obj, include_link=source.OMIT_LINK)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({'status': orig}))

  def test_ellipsize_real_tweet(self):
    """Test ellipsizing a tweet that was giving us trouble. If you do not
    account for the ellipsis when determining where to truncate, it will
    truncate after 'send' and the result will be one char too long.
    """
    self.twitter.TRUNCATE_TEXT_LENGTH = 140

    orig = ('Hey #indieweb, the coming storm of webmention Spam may not be '
            'far away. Those of us that have input fields to send webmentions '
            'manually may already be getting them')

    content = ('Hey #indieweb, the coming storm of webmention Spam may not '
               'be far away. Those of us that have input fields to send… '
               'https://ben.thatmustbe.me/note/2015/1/31/1/')

    preview = ('Hey <a href="https://twitter.com/hashtag/indieweb">#indieweb</a>, '
               'the coming storm of webmention Spam may not '
               'be far away. Those of us that have input fields to send… '
               '<a title="ben.thatmustbe.me/note/2015/1/31/1" href="https://ben.thatmustbe.me/note/2015/1/31/1/">ben.thatmustbe.me/note/2015/1/31...</a>')

    self.urlopen_returns(TWEET)
    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj['content'] = orig
    obj['url'] = 'https://ben.thatmustbe.me/note/2015/1/31/1/'

    self.twitter.create(obj, include_link=source.INCLUDE_LINK)
    actual_preview = self.twitter.preview_create(obj, include_link=source.INCLUDE_LINK).content
    self.assertEqual(preview, actual_preview)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({'status': content.encode('utf-8')}))

  def test_create_preview_dont_autolink_at_mentions_inside_urls(self):
    """Don't autolink @-mentions inside urls.

    https://github.com/snarfed/bridgy/issues/527#issuecomment-346302800
    """
    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj['content'] = '時空黑洞都出現了，非常歡樂！LOL https://medium.com/@abc/xyz'
    self.assertEqual(
      '時空黑洞都出現了，非常歡樂！LOL <a href="https://medium.com/@abc/xyz">medium.com/@abc/xyz</a>',
      self.twitter.preview_create(obj).content)

  def test_tweet_article_has_different_format(self):
    """Articles are published with a slightly different format:
    "The Title: url", instead of "The Title (url)"
    """
    preview = self.twitter.preview_create({
      'objectType': 'article',
      'displayName': 'The Article Title',
      'url': 'http://example.com/article',
    }, include_link=source.INCLUDE_LINK).content
    self.assertEqual(
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
    self.assertEqual('my summary', result.content)

    del obj['summary']
    result = self.twitter.preview_create(obj)
    self.assertEqual('my content', result.content)

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
    self.twitter.TRUNCATE_TEXT_LENGTH = 20
    self.twitter.TRUNCATE_URL_LENGTH = 5

    self.urlopen_returns(TWEET)
    obj = copy.deepcopy(OBJECT)
    del obj['image']
    obj.update({
        'content': 'too long\nextra whitespace\tbut should include url',
        'url': 'http://obj.ca',
        })
    self.twitter.create(obj, include_link=source.INCLUDE_LINK)
    result = self.twitter.preview_create(obj, include_link=source.INCLUDE_LINK)
    self.assertIn('too long… <a href="http://obj.ca">obj.ca</a>',
                  result.content)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(
        {'status': 'too long… http://obj.ca'}))

  def test_create_tweet_include_link_if_truncated(self):
    self.twitter.TRUNCATE_TEXT_LENGTH = 20
    self.twitter.TRUNCATE_URL_LENGTH = 5

    cases = [(
      'too long\nextra whitespace\tbut should include url',
      'http://obj.ca',
      'too long… http://obj.ca',
      'too long… <a href="http://obj.ca">obj.ca</a>',
    ), (
      'short and sweet',
      'http://obj.ca',
      'short and sweet',
      'short and sweet',
    )]

    obj = copy.deepcopy(OBJECT)
    del obj['image']

    for content, url, _, expected in cases:
      self.urlopen_returns(TWEET)
      obj.update({'content': content, 'url': url})
      self.twitter.create(
        obj, include_link=source.INCLUDE_IF_TRUNCATED)
      result = self.twitter.preview_create(
        obj, include_link=source.INCLUDE_IF_TRUNCATED)
      self.assertIn(expected, result.content)

    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(
        {'status': 'too long… http://obj.ca'.encode('utf-8')}))
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(
        {'status': 'short and sweet'.encode('utf-8')}))

  def test_create_recognize_note(self):
    """Use post-type-discovery to recognize a note with non-trivial html content.
    We'll know it was successful if it respects the rich content and includes
    newlines in the output.
    """
    obj = microformats2.json_to_object({
      'type': ['h-entry'],
      'properties': {
        'author': [{
          'properties': {
            'name': ['Tantek Çelik'],
            'photo': ['http://tantek.com/logo.jpg'],
            'url': ['http://tantek.com/']
          },
          'type': ['h-card'],
          'value': '',
        }],
        'content': [{
          'html': 'https://instagram.com/p/9XVBIRA9cj/<br /><br />Social Web session @W3C #TPAC2015 in Sapporo, Hokkaido, Japan.',
          'value': ' https://instagram.com/p/9XVBIRA9cj/Social Web session @W3C #TPAC2015 in Sapporo, Hokkaido, Japan.'
        }],
        'name': ['https://instagram.com/p/9XVBIRA9cj/Social Web session @W3C #TPAC2015 in Sapporo, Hokkaido, Japan.'],
        'photo': ['https://igcdn-photos-b-a.akamaihd.net/hphotos-ak-xaf1/t51.2885-15/e35/12145332_1662314194043465_2009449288_n.jpg'],
        'published': ['2015-10-27T19:48:00-0700'],
        'syndication': [
          'https://www.facebook.com/photo.php?fbid=10101948228396473',
          'https://twitter.com/t/status/659200761427980288'
        ],
        'uid': ['http://tantek.com/2015/300/t1/social-web-session-w3c-tpac2015'],
        'updated': ['2015-10-27T19:48:00-0700'],
        'url': ['http://tantek.com/2015/300/t1/social-web-session-w3c-tpac2015'],
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

    self.urlopen_returns(TWEET)
    self.twitter.create(obj, include_link=source.OMIT_LINK)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('lat', '37.83'),
        ('long', '-122.25'),
        ('status', 'Checked in to Timeless Coffee Roasters'),
      ])))

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
      # photo and video URLs. tests Twitter.base_object()
      ('foo', 'http://twitter.com/you/status/100/photo/1', 'foo', 'foo'),
      ('foo', 'http://twitter.com/you/status/100/video/1', 'foo', 'foo'),
      # mobile.twitter.com URL. the mobile should be stripped from embed.
      ('foo', 'http://mobile.twitter.com/you/status/100', 'foo', 'foo'),
      )

    tweet = copy.deepcopy(TWEET)
    obj = copy.deepcopy(REPLY_OBJS[0])

    for content, url, _, expected_preview in testdata:
      self.urlopen_returns(TWEET)

      tweet.update({
          'id': '100',
          'url': 'https://twitter.com/snarfed_org/status/100',
          'type': 'comment',
          })
      obj.update({'inReplyTo': [{'url': url}], 'content': content})
      self.assert_equals(tweet, self.twitter.create(obj).content)

      preview = self.twitter.preview_create(obj)
      self.assertEqual(expected_preview, preview.content)
      self.assertIn('<span class="verb">@-reply</span> to <a href="http://twitter.com/you/status/100">this tweet</a>:', preview.description)

    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('auto_populate_reply_metadata', 'true'),
        ('in_reply_to_status_id', 100),
        ('status', 'foo @you'),
      ])))

  def test_create_reply_objectType_comment(self):
    obj = {
      'objectType': 'comment',
      'content': 'my content',
      'inReplyTo': [{'url': 'http://twitter.com/you/status/100'}],
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertIn('<span class="verb">@-reply</span> to <a href="http://twitter.com/you/status/100">this tweet</a>:', preview.description)
    self.assertEqual('my content', preview.content)

    # test create
    self.urlopen_returns({'url': 'http://posted/tweet'})
    self.assert_equals({'url': 'http://posted/tweet', 'type': 'comment'},
                       self.twitter.create(obj).content)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('auto_populate_reply_metadata', 'true'),
        ('in_reply_to_status_id', '100'),
        ('status', 'my content'),
      ])))

  def test_create_reply_to_self_omits_mention(self):
    for username, reply_to in ('me', 'me'), ('ME', 'ME'), ('Me', 'mE'):
      self.urlopen_returns({'url': 'http://posted/tweet'})
      tw = twitter.Twitter('key', 'secret', username=username)
      obj = {
        'objectType': 'comment',
        'content': 'my content',
        'inReplyTo': [{'url': f'http://twitter.com/{reply_to}/status/100'}],
      }

      # test preview
      preview = tw.preview_create(obj)
      self.assertIn(f"@-reply</span> to <a href=\"{obj['inReplyTo'][0]['url']}\">this tweet</a>:",
                    preview.description)
      self.assertEqual('my content', preview.content)

      # test create
      self.assert_equals({'url': 'http://posted/tweet', 'type': 'comment'},
                         tw.create(obj).content)

    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('auto_populate_reply_metadata', 'true'),
        ('in_reply_to_status_id', '100'),
        ('status', 'my content'),
      ])))

  def test_create_preview_favorite_with_like_verb(self):
    self._test_create_preview_favorite('like')

  def test_create_preview_favorite_with_favorite_verb(self):
    self._test_create_preview_favorite('favorite')

  def _test_create_preview_favorite(self, verb):
    obj = copy.deepcopy(LIKE_OBJECTS[0])
    obj['verb'] = verb

    self.urlopen_returns(TWEET)
    resp = self.twitter.create(obj)
    self.assert_equals({
      'url': 'https://twitter.com/snarfed_org/status/100',
      'type': 'like',
    }, resp.content)
    self.assert_urlopen(
      twitter.API_POST_FAVORITE + '?' + urllib.parse.urlencode({'id': 100}))

    preview = self.twitter.preview_create(LIKE_OBJECTS[0])
    self.assertIn("""\
<span class="verb">like</span>
<a href="https://twitter.com/snarfed_org/status/100">this tweet</a>:""",
                  preview.description)

  def test_create_favorite_of_video_url(self):
    like = copy.deepcopy(LIKE_OBJECTS[0])
    like['object']['url'] = 'https://twitter.com/snarfed_org/status/100/video/1'

    self.urlopen_returns(TWEET)
    self.assert_equals({'url': 'https://twitter.com/snarfed_org/status/100',
                        'type': 'like'},
                       self.twitter.create(like).content)
    self.assert_urlopen(
      twitter.API_POST_FAVORITE + '?' + urllib.parse.urlencode({'id': 100}))

    preview = self.twitter.preview_create(like)
    self.assertIn("""\
<span class="verb">like</span>
<a href="https://twitter.com/snarfed_org/status/100">this tweet</a>:""",
                  preview.description)

  def test_create_retweet(self):
    self.urlopen_returns(TWEET)
    tweet = copy.deepcopy(TWEET)
    tweet.update({
        'id': '100',
        'url': 'https://twitter.com/snarfed_org/status/100',
        'type': 'repost',
        })
    self.assert_equals(tweet, self.twitter.create(SHARES[0]).content)
    self.assert_urlopen(
      twitter.API_POST_RETWEET % 333 + '?' + urllib.parse.urlencode({'id': 333}))

    preview = self.twitter.preview_create(SHARES[0])
    self.assertIn("""\
<span class="verb">retweet</span>
<a href="https://twitter.com/foo/status/333">this tweet</a>:""",
                  preview.description)

  def test_create_quote_tweet(self):
    self.urlopen_returns({'url': 'http://posted/tweet'})
    created = self.twitter.create(QUOTE_ACTIVITY['object'])
    self.assert_equals({'url': 'http://posted/tweet', 'type': 'post'},
                       created.content, created)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({
        'status': 'I agree with this https://twitter.com/snarfed_org/status/100',
      }))

    preview = self.twitter.preview_create(QUOTE_ACTIVITY['object'])
    self.assertEqual('I agree with this <a title="twitter.com/snarfed_org/status/100" href="https://twitter.com/snarfed_org/status/100">twitter.com/snarfed_org/st...</a>', preview.content)
    self.assertIn("""\
<span class="verb">quote</span>
<a href="https://twitter.com/snarfed_org/status/100">this tweet</a>:""",
                  preview.description)

  def test_create_quote_tweet_strips_quotation(self):
    self.urlopen_returns({})
    obj = copy.deepcopy(QUOTE_ACTIVITY['object'])
    obj['content'] = 'I\tagree\n<cite class="u-quotation-of h-cite">foo</cite>\nwith this'
    created = self.twitter.create(obj)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({
        'status': 'I agree with this https://twitter.com/snarfed_org/status/100',
      }))

  def test_create_quote_tweet_truncated_content(self):
    self.twitter.TRUNCATE_TEXT_LENGTH = 140
    self.urlopen_returns({})
    obj = copy.deepcopy(QUOTE_ACTIVITY['object'])
    obj['content'] = 'X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X'
    created = self.twitter.create(obj)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({
        'status': ('X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X X… https://twitter.com/snarfed_org/status/100').encode('utf-8'),
      }))

  def test_create_rsvp(self):
    content = "i'm going to a thing"
    self.urlopen_returns({})
    obj = {
      'objectType': 'activity',
      'verb': 'rsvp-yes',
      'content': content,
    }
    result = self.twitter.create(obj)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({'status': content}))

    preview = self.twitter.preview_create(obj)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual(content, preview.content)

  def test_create_rsvp_without_content_error(self):
    for fn in self.twitter.create, self.twitter.preview_create:
      result = fn({'objectType': 'activity', 'verb': 'rsvp-yes'})
      self.assertIsNone(result.content)
      for msg in result.error_plain, result.error_html:
        self.assertEqual('No content text found.', msg)

  def test_create_unsupported_type_error(self):
    for fn in self.twitter.create, self.twitter.preview_create:
      result = fn({'objectType': 'activity', 'verb': 'react'})
      self.assertIsNone(result.content)
      for msg in result.error_plain, result.error_html:
        self.assertIn('Cannot publish type=activity, verb=react', msg)

  def test_create_non_twitter_reply(self):
    self.urlopen_returns({})
    obj = {
      'objectType': 'comment',
      'inReplyTo': [{'url': 'http://foo.com/bar'},
                    {'url': 'http://baz.com/bat'}],
      'content': 'I reply!'
    }

    created = self.twitter.create(obj)
    self.assertFalse(created.abort)
    self.assert_equals({'type': 'post'}, created.content)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({'status': 'I reply!'}))

    preview = self.twitter.preview_create(obj)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual('I reply!', preview.content)

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

  def test_create_bookmark(self):
    content = "i'm bookmarking a thing"
    self.urlopen_returns({})
    activity = {
      "objectType": "activity",
      "verb": "post",
      "content": content,
      "object": {
        "objectType": "bookmark",
        "targetUrl": "https://example.com/foo"
      }
    }
    self.twitter.create(activity)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode({'status': content}))

    preview = self.twitter.preview_create(activity)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual(content, preview.content)

  def test_create_with_multiple_photos(self):
    self.twitter.TRUNCATE_TEXT_LENGTH = 140

    image_urls = [f'http://my/picture/{i}' for i in range(twitter.MAX_MEDIA + 1)]
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
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual(ellipsized + '<br /><br />' +
                      ' &nbsp; '.join(f'<img src="{url}" alt="" />'
                                      for url in image_urls[:-1]),
                      preview.content)

    # test create
    urlopen_side_effect = []
    session_post_side_effect = []
    for i, url in enumerate(image_urls[:-1]):
      content = f'picture response {i}'
      urlopen_side_effect.append(
        UrlopenResult(200, content, headers={'Content-Length': '3'}))
      session_post_side_effect.append(
        requests_response({'media_id_string': str(i)}))
    urlopen_side_effect.append(
      UrlopenResult(200, {'url': 'http://posted/picture'}))
    self.mock_urlopen.side_effect = urlopen_side_effect
    self.mock_post.side_effect = session_post_side_effect
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)
    self.assert_urlopen(image_urls[0])
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '0,1,2,3'),
        ('status', ellipsized.encode('utf-8')),
      ])))

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
    self.assertEqual('my content<br /><br /><img src="http://my/picture" alt="" />',
                      preview.content)

    # test create
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, 'picture response', headers={'Content-Length': '3'}),
      UrlopenResult(200, {'url': 'http://posted/picture'}),
    ]
    self.mock_post.return_value = requests_response({'media_id_string': '123'})
    self.assert_equals({'url': 'http://posted/picture', 'type': 'comment'},
                       self.twitter.create(obj).content)
    self.assert_urlopen('http://my/picture')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('auto_populate_reply_metadata', 'true'),
        ('in_reply_to_status_id', '100'),
        ('media_ids', '123'),
        ('status', 'my content'),
      ])))

  def test_create_with_photo_no_content(self):
    obj = {
      'objectType': 'note',
      'image': {'url': 'http://my/picture'},
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual('<br /><br /><img src="http://my/picture" alt="" />',
                     preview.content)

    # test create
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, 'picture response', headers={'Content-Length': '3'}),
      UrlopenResult(200, {'url': 'http://posted/picture'}),
    ]
    self.mock_post.return_value = requests_response({'media_id_string': '123'})
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)
    self.assert_urlopen('http://my/picture')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '123'),
        ('status', ''),
      ])))

  def test_create_with_photo_error(self):
    obj = {
      'objectType': 'note',
      'content': 'my caption',
      'image': {'url': 'http://my/picture'},
    }

    self.mock_urlopen.side_effect = [
      UrlopenResult(200, 'picture response', headers={'Content-Length': '3'}),
      urllib.error.HTTPError('url', 403, 'Forbidden', {}, None),
    ]
    self.mock_post.return_value = requests_response({'media_id_string': '123'})
    self.assertRaises(urllib.error.HTTPError, self.twitter.create, obj)
    self.assert_urlopen('http://my/picture')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)

  def test_create_with_photo_upload_error(self):
    self.urlopen_returns(
      'picture response', headers={'Content-Length': '3'})
    self.mock_post.return_value = requests_response('', status=400)
    self.assertRaises(requests.HTTPError, self.twitter.create, {
      'objectType': 'note',
      'image': {'url': 'http://my/picture'},
    })
    self.assert_urlopen('http://my/picture')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)

  def test_create_with_photo_wrong_type(self):
    obj = {
      'objectType': 'note',
      'image': {'url': 'http://my/picture.tiff'},
    }
    self.urlopen_returns('', headers={'Content-Length': '3'})
    ret = self.twitter.create(obj)
    self.assertTrue(ret.abort)
    for msg in ret.error_plain, ret.error_html:
      self.assertIn('Twitter only supports JPG, PNG, GIF, and WEBP images;', msg)
      self.assertIn('looks like image/tiff', msg)
    self.assert_urlopen('http://my/picture.tiff')

  def test_create_with_photo_with_alt(self):
    obj = {
      'objectType': 'note',
      'image': {
        'url': 'http://my/picture.png',
        'displayName': 'some alt text',
      },
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual('<br /><br /><img src="http://my/picture.png" alt="some alt text" />',
                     preview.content)

    # test create
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, 'picture response', headers={'Content-Length': '3'}),
      UrlopenResult(200, {'url': 'http://posted/picture'}),
    ]
    self.mock_post.side_effect = [
      requests_response({'media_id_string': '123'}),
      requests_response(''),
    ]
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)
    self.assert_urlopen('http://my/picture.png')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_requests_post(twitter.API_MEDIA_METADATA)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '123'),
        ('status', ''),
      ])))

  def test_create_with_photo_too_big(self):
    self.urlopen_returns(
      '', headers={'Content-Length': str(twitter.MAX_IMAGE_SIZE + 1)})
    # test create
    got = self.twitter.create({
      'objectType': 'note',
      'image': {'url': 'http://my/picture.png'},
    })
    self.assertTrue(got.abort)
    self.assertIn("larger than Twitter's 5MB limit:", got.error_plain)
    self.assert_urlopen('http://my/picture.png')

  def test_create_with_photo_with_alt_error(self):
    self.urlopen_returns(
      'picture response', headers={'Content-Length': '3'})
    self.mock_post.side_effect = [
      requests_response({'media_id_string': '123'}),
      requests_response('', status=400),
    ]
    self.assertRaises(requests.HTTPError, self.twitter.create, {
      'objectType': 'note',
      'image': {
        'url': 'http://my/picture.png',
        'displayName': 'some alt text',
      },
    })
    self.assert_urlopen('http://my/picture.png')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_requests_post(twitter.API_MEDIA_METADATA)

  def test_create_with_photo_alt_is_not_trimmed_when_short(self):
    obj = {
      'objectType': 'note',
      'image': {
        'url': 'http://my/picture.png',
        'displayName': 'Black Cat\'s face framed in a window of a grey hidey hole in his tower, looking a little bit crabby',
      },
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual('<br /><br /><img src="http://my/picture.png" alt="Black Cat\'s face framed in a window of a grey hidey hole in his tower, looking a little bit crabby" />',
                     preview.content)

    # test create
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, 'picture response', headers={'Content-Length': '3'}),
      UrlopenResult(200, {'url': 'http://posted/picture'}),
    ]
    self.mock_post.side_effect = [
      requests_response({'media_id_string': '123'}),
      requests_response(''),
    ]
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)
    self.assert_urlopen('http://my/picture.png')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_requests_post(twitter.API_MEDIA_METADATA)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '123'),
        ('status', ''),
      ])))

  def test_create_with_photo_alt_trimmed_when_too_large(self):
    obj = {
      'objectType': 'note',
      'image': {
        'url': 'http://my/picture.png',
        'displayName': '1a871f1abf22f3963bcf65f9bf9084d85c70d23f59d36b21c9776cf4e8e5919150e753e20c39afb353ca0253062794f931468e48c111fdc9549eba886717f8578ba92ef237b762663195ba73ab61339795a7e902e90548813c77cfa9381e459ec0dd04d6122b00e75906cf52363a1f61d6c70df6631020bc102e28c4c9895302fbcc19f4912c5a71334d09c84d279ec9deb1e6b23cb82a5ed7145c9d6320c04dbc2f0a9a0b99a61fd4e807782af4e13567db8759be6e5543c9da3c9ba72ca29266fca72652d29d961939961fb1acd622d0b and this extra bit will be trimmed',
      },
    }

    # test preview
    preview = self.twitter.preview_create(obj)
    self.assertEqual('<span class="verb">tweet</span>:', preview.description)
    self.assertEqual('<br /><br /><img src="http://my/picture.png" alt="1a871f1abf22f3963bcf65f9bf9084d85c70d23f59d36b21c9776cf4e8e5919150e753e20c39afb353ca0253062794f931468e48c111fdc9549eba886717f8578ba92ef237b762663195ba73ab61339795a7e902e90548813c77cfa9381e459ec0dd04d6122b00e75906cf52363a1f61d6c70df6631020bc102e28c4c9895302fbcc19f4912c5a71334d09c84d279ec9deb1e6b23cb82a5ed7145c9d6320c04dbc2f0a9a0b99a61fd4e807782af4e13567db8759be6e5543c9da3c9ba72ca29266fca72652d29d961939961fb1acd622d..." />',
                     preview.content)

    # test create
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, 'picture response', headers={'Content-Length': '3'}),
      UrlopenResult(200, {'url': 'http://posted/picture'}),
    ]
    self.mock_post.side_effect = [
      requests_response({'media_id_string': '123'}),
      requests_response(''),
    ]
    self.assert_equals({'url': 'http://posted/picture', 'type': 'post'},
                       self.twitter.create(obj).content)
    self.assert_urlopen('http://my/picture.png')
    self.assert_requests_post(twitter.API_UPLOAD_MEDIA)
    self.assert_requests_post(twitter.API_MEDIA_METADATA)
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '123'),
        ('status', ''),
      ])))

  def test_create_with_video_wait_for_processing(self):
    self.twitter.TRUNCATE_TEXT_LENGTH = 140

    obj = {
      'objectType': 'note',
      'content': """\
the caption.\nextra long so we can check that it accounts for the pic-twitter-com link. <video xyz>should be removed. </video> almost at 140 chars, just type a little more, ok done.""",
      'stream': {'url': 'http://my/video'},
    }
    ellipsized = u"""\
the caption. extra long so we can check that it accounts for the pic-twitter-com link. almost at 140 chars, just type a little more, ok…"""

    # test create
    content = 'video response'
    twitter.UPLOAD_CHUNK_SIZE = 5

    resp_finalize = {
      'media_id': 9,
      'media_id_string': '9',
      'processing_info': {
        'state': 'pending',
        'check_after_secs': 5,
      }
    }
    resp_in_progress = {
      'media_id': 9,
      'media_id_string': '9',
      'processing_info': {
        'state': 'in_progress',
        'check_after_secs': 9999,
      }
    }
    resp_succeeded = {
      'media_id': 9,
      'media_id_string': '9',
      'processing_info': {
        'state': 'succeeded',
      }
    }
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, content, headers={'Content-Length': str(len(content))}),
      UrlopenResult(200, {'media_id_string': '9'}),
      UrlopenResult(200, resp_finalize),
      UrlopenResult(200, resp_in_progress),
      UrlopenResult(200, resp_succeeded),
      UrlopenResult(200, {'url': 'http://posted/video'}),
    ]
    def consume_chunk(*args, **kwargs):
      kwargs.get('files', {}).get('media', io.StringIO()).read()
      return requests_response('')
    self.mock_post.side_effect = consume_chunk
    with patch.object(twitter, 'sleep_fn'):
      self.assert_equals({'url': 'http://posted/video', 'type': 'post'},
                         self.twitter.create(obj).content)
    self.assert_urlopen('http://my/video')
    self.assert_urlopen(
      twitter.API_UPLOAD_MEDIA + '?' + urllib.parse.urlencode({
        'command': 'INIT',
        'media_type': 'video/mp4',
        'media_category': 'tweet_video',
        'total_bytes': len(content),
      }))
    self.assert_requests_post(
      twitter.API_UPLOAD_MEDIA,
      data={'command': 'APPEND', 'media_id': '9', 'segment_index': 0})
    self.assert_urlopen(
      twitter.API_UPLOAD_MEDIA + '?' + urllib.parse.urlencode({
        'command': 'FINALIZE',
        'media_id': '9',
      }))
    self.assert_urlopen(twitter.API_UPLOAD_MEDIA + '?command=STATUS&media_id=9')
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '9'),
        ('status', ellipsized.encode('utf-8')),
      ])))

  def test_create_with_video(self):
    self.twitter.TRUNCATE_TEXT_LENGTH = 140

    obj = {
      'objectType': 'note',
      'content': """\
the caption.\nextra long so we can check that it accounts for the pic-twitter-com link. <video xyz>should be removed. </video> almost at 140 chars, just type a little more, ok done.""",
      'stream': {'url': 'http://my/video'},
    }
    ellipsized = u"""\
the caption. extra long so we can check that it accounts for the pic-twitter-com link. almost at 140 chars, just type a little more, ok…"""

    # test preview
    self.assertEqual(ellipsized +
      '<br /><br /><video controls src="http://my/video">'
      '<a href="http://my/video">this video</a></video>',
      self.twitter.preview_create(obj).content)

    # test create
    content = 'video response'
    twitter.UPLOAD_CHUNK_SIZE = 5
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, content, headers={'Content-Length': str(len(content))}),
      UrlopenResult(200, {'media_id_string': '9'}),
      UrlopenResult(200, {'media_id': 9, 'media_id_string': '9', 'size': 11065}),
      UrlopenResult(200, {'url': 'http://posted/video'}),
    ]
    def consume_chunk(*args, **kwargs):
      kwargs.get('files', {}).get('media', io.StringIO()).read()
      return requests_response('')
    self.mock_post.side_effect = consume_chunk
    self.assert_equals({'url': 'http://posted/video', 'type': 'post'},
                       self.twitter.create(obj).content)
    self.assert_urlopen('http://my/video')
    self.assert_urlopen(
      twitter.API_UPLOAD_MEDIA + '?' + urllib.parse.urlencode({
        'command': 'INIT',
        'media_type': 'video/mp4',
        'media_category': 'tweet_video',
        'total_bytes': len(content),
      }))
    self.assert_requests_post(
      twitter.API_UPLOAD_MEDIA,
      data={'command': 'APPEND', 'media_id': '9', 'segment_index': 0})
    self.assert_urlopen(
      twitter.API_UPLOAD_MEDIA + '?' + urllib.parse.urlencode({
        'command': 'FINALIZE',
        'media_id': '9',
      }))
    self.assert_urlopen(
      twitter.API_POST_TWEET + '?' + urllib.parse.urlencode(sorted([
        ('media_ids', '9'),
        ('status', ellipsized.encode('utf-8')),
      ])))

  def test_create_with_video_too_big(self):
    self.urlopen_returns(
      '', headers={'Content-Length': str(twitter.MAX_VIDEO_SIZE + 1)})
    ret = self.twitter.create({
      'objectType': 'note',
      'stream': {'url': 'http://my/video'},
    })
    self.assertTrue(ret.abort)
    self.assertIn("larger than Twitter's 512MB limit:", ret.error_plain)
    self.assertIn("larger than Twitter's 512MB limit:", ret.error_html)
    self.assert_urlopen('http://my/video')

  def test_create_with_video_wrong_type(self):
    self.mock_urlopen.side_effect = [
      UrlopenResult(200, '', headers={'Content-Type': 'video/unknown'}),
      UrlopenResult(200, ''),
    ]
    for url in 'http://my/video', 'http://my/video.mov':
      ret = self.twitter.create({
        'objectType': 'note',
        'stream': {'url': url},
      })
      self.assertTrue(ret.abort)
      for msg in ret.error_plain, ret.error_html:
        self.assertIn('Twitter only supports MP4 videos', msg)
    self.assert_urlopen('http://my/video')
    self.assert_urlopen('http://my/video.mov')

  def test_tweet_to_as1_object_archive_date_format(self):
    """Twitter archive created_at values are in a form of ISO 8601."""
    tweet = copy.deepcopy(TWEET)
    tweet['created_at'] = '2012-02-22 20:26:41 +0000'
    obj = copy.deepcopy(OBJECT)
    obj['published'] = '2012-02-22 20:26:41 +0000'
    self.assert_equals(obj, self.twitter.tweet_to_as1_object(tweet))

  def test_delete(self):
    resp = {'o': 'k'}
    self.urlopen_returns(resp)
    self.assertEqual(resp, self.twitter.delete('789').content)
    self.assert_urlopen(
      twitter.API_DELETE_TWEET + '?' + urllib.parse.urlencode({'id': '789'}))

  def test_preview_delete(self):
    preview = self.twitter.preview_delete('123')
    self.assertIn('<a href="https://twitter.com/_/status/123">this tweet</a>',
                  preview.description)
    self.assertIsNone(preview.content)

  def test_base_object_no_url(self):
    self.assert_equals({}, self.twitter.base_object({
      'object': {'foo': 'bar'},
    }))

  def test_base_object_bookmark(self):
    self.assert_equals({}, self.twitter.base_object({
      'object': {
        'objectType': 'bookmark',
        'targetUrl': 'http://bar.com/baz',
      },
    }))

