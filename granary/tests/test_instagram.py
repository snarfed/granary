"""Unit tests for instagram.py."""
import copy
import datetime
import logging
import urllib.parse

from mox3 import mox
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads
import requests

from .. import instagram
from ..instagram import HTML_BASE_URL, Instagram, HEADERS
from .. import source

logger = logging.getLogger(__name__)


def tag_uri(name):
  return util.tag_uri('instagram.com', name)


# Test data.
# The Instagram API returns objects with attributes, not JSON dicts.
USER = {  # Instagram
  'username': 'snarfed',
  'bio': 'foo https://asdf.com bar',
  'website': 'http://snarfed.org',
  'profile_picture': 'http://picture/ryan',
  'full_name': 'Ryan B',
  'counts': {
    'media': 2,
    'followed_by': 10,
    'follows': 33,
  },
  'id': '420973239',
}
ACTOR = {  # ActivityStreams
  'objectType': 'person',
  'id': tag_uri('420973239'),
  'username': 'snarfed',
  'url': 'https://www.instagram.com/snarfed/',
  'urls': [
    {'value': 'https://www.instagram.com/snarfed/'},
    {'value': 'http://snarfed.org'},
    {'value': 'https://asdf.com'},
  ],
  'displayName': 'Ryan B',
  'image': {'url': 'http://picture/ryan'},
  'description': 'foo https://asdf.com bar',
}
COMMENTS = [{  # Instagram
  'created_time': '1349588757',
  'text': '太可爱了。cute，@a_person, very cute',
  'from': {
    'username': 'averygood',
    'profile_picture': 'http://picture/commenter',
    'id': '232927278',
    'full_name': '小正',
  },
  'id': '110',
}]
MEDIA = {  # Instagram
  'id': '123_456',
  'filter': 'Normal',
  'created_time': '1348291542',
  'link': 'https://www.instagram.com/p/ABC123/',
  'user_has_liked': False,
  'attribution': None,
  'location': {
    'id': '520640',
    'name': 'Le Truc',
    'street_address': '123 Main St.',
    'point': {'latitude':37.3, 'longitude':-122.5},
    'url': 'https://instagram.com/explore/locations/520640/',
    },
  'user': USER,
  'comments': {
    'data': COMMENTS,
    'count': len(COMMENTS),
  },
  'images': {
    'low_resolution': {
      'url': 'http://attach/image/small',
      'width': 306,
      'height': 306
    },
    'thumbnail': {
      'url': 'http://attach/image/thumb',
      'width': 150,
      'height': 150
    },
    'standard_resolution': {
      'url': 'http://attach/image/big',
      'width': 612,
      'height': 612
    },
  },
  'tags': ['abc', 'xyz'],
  'users_in_photo': [{'user': USER, 'position': {'x': 1, 'y': 2}}],
  'caption': {
    'created_time': '1348291558',
    'text': 'this picture -> is #abc @foo #xyz',
    'user': {},
    'id': '285812769105340251'
  },
}
VIDEO = {
  'type': 'video',
  'id': '123_456',
  'link': 'https://www.instagram.com/p/ABC123/',
  'videos': {
    'low_resolution': {
      'url': 'http://distilleryvesper9-13.ak.instagram.com/090d06dad9cd11e2aa0912313817975d_102.mp4',
      'width': 480,
      'height': 480
    },
    'standard_resolution': {
      'url': 'http://distilleryvesper9-13.ak.instagram.com/090d06dad9cd11e2aa0912313817975d_101.mp4',
      'width': 640,
      'height': 640
    },
  },
  'users_in_photo': None,
  'filter': 'Vesper',
  'tags': [],
  'comments': {
    'data': COMMENTS,
    'count': len(COMMENTS),
  },
  'caption': None,
  'user': USER,
  'created_time': '1279340983',
  'images': {
    'low_resolution': {
      'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_6.jpg',
      'width': 306,
      'height': 306
    },
    'thumbnail': {
      'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_5.jpg',
      'width': 150,
      'height': 150
    },
    'standard_resolution': {
      'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_7.jpg',
      'width': 612,
      'height': 612
    }
  },
  'location': None
}
COMMENT_OBJS = [{  # ActivityStreams
  'objectType': 'comment',
  'author': {
    'objectType': 'person',
    'id': tag_uri('232927278'),
    'username': 'averygood',
    'displayName': '小正',
    'image': {'url': 'http://picture/commenter'},
    'url': 'https://www.instagram.com/averygood/',
  },
  'content': '太可爱了。cute，@a_person, very cute',
  'id': tag_uri('110'),
  'published': '2012-10-07T05:45:57+00:00',
  'url': 'https://www.instagram.com/p/ABC123/#comment-110',
  'inReplyTo': [{'id': tag_uri('123_456')}],
  'to': [{'objectType':'group', 'alias':'@public'}],
  'tags': [{
    'objectType': 'person',
    'id': tag_uri('a_person'),
    'displayName': 'a_person',
    'url': 'https://www.instagram.com/a_person/',
    'startIndex': 10,
    'length': 9,
  }],
}]
MEDIA_OBJ = {  # ActivityStreams
  'objectType': 'photo',
  'author': ACTOR,
  'content': 'this picture -&gt; is #abc @foo #xyz',
  'id': tag_uri('123_456'),
  'published': '2012-09-22T05:25:42+00:00',
  'url': 'https://www.instagram.com/p/ABC123/',
  'image': {
    'url': 'http://attach/image/big',
    'width': 612,
    'height': 612,
  },
  'to': [{'objectType':'group', 'alias':'@public'}],
  'location': {
    'id': tag_uri('520640'),
    'displayName': 'Le Truc',
    'latitude': 37.3,
    'longitude': -122.5,
    'position': '+37.300000-122.500000/',
    'address': {'formatted': '123 Main St.'},
    'url': 'https://instagram.com/explore/locations/520640/',
  },
  'attachments': [{
    'objectType': 'image',
    'url': 'https://www.instagram.com/p/ABC123/',
    'image': [{
      'url': 'http://attach/image/big',
      'width': 612,
      'height': 612,
    }, {
      'url': 'http://attach/image/small',
      'width': 306,
      'height': 306,
    }, {
      'url': 'http://attach/image/thumb',
      'width': 150,
      'height': 150,
    }],
  }],
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
    },
  'tags': [{
    'objectType': 'person',
    'id': tag_uri('420973239'),
    'username': 'snarfed',
    'url': 'https://www.instagram.com/snarfed/',
    'urls': [
      {'value': 'https://www.instagram.com/snarfed/'},
      {'value': 'http://snarfed.org'},
      {'value': 'https://asdf.com'},
    ],
    'displayName': 'Ryan B',
    'image': {'url': 'http://picture/ryan'},
    'description': 'foo https://asdf.com bar',
  }, {
    'objectType': 'hashtag',
    'id': tag_uri('abc'),
    'displayName': 'abc',
    # TODO?
    # 'startIndex': 32,
    # 'length': 10,
  }, {
    'objectType': 'hashtag',
    'id': tag_uri('xyz'),
    'displayName': 'xyz',
  }, {
    'objectType': 'person',
    'id': tag_uri('foo'),
    'displayName': 'foo',
    'url': 'https://www.instagram.com/foo/',
    'startIndex': 27,
    'length': 4,
  }],
}
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-09-22T05:25:42+00:00',
  'id': tag_uri('123_456'),
  'url': 'https://www.instagram.com/p/ABC123/',
  'actor': ACTOR,
  'object': MEDIA_OBJ,
  }
LIKES = [  # Instagram
  {
    'id': '8',
    'username': 'alizz',
    'full_name': 'Alice',
    'profile_picture': 'http://alice/picture',
  },
  {
    'id': '9',
    'username': 'bobbb',
    'full_name': 'Bob',
    'profile_picture': 'http://bob/picture',
    'website': 'http://bob.com/',
  },
]
MEDIA_WITH_LIKES = copy.deepcopy(MEDIA)
MEDIA_WITH_LIKES['likes'] = {
  'data': LIKES,
  'count': len(LIKES)
}
LIKE_OBJS = [{  # ActivityStreams
    'id': tag_uri('123_456_liked_by_8'),
    'url': 'https://www.instagram.com/p/ABC123/#liked-by-8',
    'objectType': 'activity',
    'verb': 'like',
    'object': { 'url': 'https://www.instagram.com/p/ABC123/'},
    'author': {
      'objectType': 'person',
      'id': tag_uri('8'),
      'displayName': 'Alice',
      'username': 'alizz',
      'url': 'https://www.instagram.com/alizz/',
      'image': {'url': 'http://alice/picture'},
      },
    }, {
    'id': tag_uri('123_456_liked_by_9'),
    'url': 'https://www.instagram.com/p/ABC123/#liked-by-9',
    'objectType': 'activity',
    'verb': 'like',
    'object': { 'url': 'https://www.instagram.com/p/ABC123/'},
    'author': {
      'objectType': 'person',
      'id': tag_uri('9'),
      'displayName': 'Bob',
      'username': 'bobbb',
      'url': 'https://www.instagram.com/bobbb/',
      'urls': [
        {'value': 'https://www.instagram.com/bobbb/'},
        {'value': 'http://bob.com/'},
      ],
      'image': {'url': 'http://bob/picture'},
      },
    },
  ]
MEDIA_OBJ_WITH_LIKES = copy.deepcopy(MEDIA_OBJ)
MEDIA_OBJ_WITH_LIKES['tags'] += LIKE_OBJS
ACTIVITY_WITH_LIKES = copy.deepcopy(ACTIVITY)
ACTIVITY_WITH_LIKES['object'] = MEDIA_OBJ_WITH_LIKES
VIDEO_OBJ = {
  'attachments': [{
    'url': 'https://www.instagram.com/p/ABC123/',
    'image': [{
      'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_7.jpg',
      'width': 612,
      'height': 612
    }, {
      'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_6.jpg',
      'width': 306,
      'height': 306
    }, {
      'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_5.jpg',
      'width': 150,
      'height': 150
    }],
    'stream': [{
      'url': 'http://distilleryvesper9-13.ak.instagram.com/090d06dad9cd11e2aa0912313817975d_101.mp4',
      'width': 640,
      'height': 640
    }, {
      'url': 'http://distilleryvesper9-13.ak.instagram.com/090d06dad9cd11e2aa0912313817975d_102.mp4',
      'width': 480,
      'height': 480
    }],
    'objectType': 'video'
  }],
  'stream': {
    'url': 'http://distilleryvesper9-13.ak.instagram.com/090d06dad9cd11e2aa0912313817975d_101.mp4',
    'width': 640,
    'height': 640
  },
  'image': {
    'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_7.jpg',
    'width': 612,
    'height': 612
  },
  'author': ACTOR,
  'url': 'https://www.instagram.com/p/ABC123/',
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
  },
  'to': [{'alias': '@public', 'objectType': 'group'}],
  'published': '2010-07-17T04:29:43+00:00',
  'id': 'tag:instagram.com:123_456',
  'objectType': 'video'
}
VIDEO_ACTIVITY = {
  'url': 'https://www.instagram.com/p/ABC123/',
  'object': VIDEO_OBJ,
  'actor': ACTOR,
  'verb': 'post',
  'published': '2010-07-17T04:29:43+00:00',
  'id': 'tag:instagram.com:123_456'
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
<title>User feed for Ryan B</title>

<subtitle>foo https://asdf.com bar</subtitle>

<logo>http://picture/ryan</logo>
<updated>2012-09-22T05:25:42+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://www.instagram.com/snarfed/</uri>
 <name>Ryan B</name>
</author>

<link rel="alternate" href="%(host_url)s" type="text/html" />
<link rel="alternate" href="https://www.instagram.com/snarfed/" type="text/html" />
<link rel="avatar" href="http://picture/ryan" />
<link rel="self" href="%(request_url)s" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://www.instagram.com/snarfed/</uri>
 <name>Ryan B</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/photo</activity:object-type>

  <id>tag:instagram.com:123_456</id>
  <title>this picture -&gt; is #abc @foo #xyz</title>

  <content type="html"><![CDATA[

this picture -&gt; is #abc <a href="https://www.instagram.com/foo/">@foo</a> #xyz
<p>
<a class="link" href="https://www.instagram.com/p/ABC123/">
<img class="u-photo" src="http://attach/image/big" alt="" />
</a>
</p>
<p>  <span class="p-location h-card">
  <data class="p-uid" value="tag:instagram.com:520640"></data>
  <a class="p-name u-url" href="https://instagram.com/explore/locations/520640/">Le Truc</a>

</span>
</p>

  ]]></content>

  <link rel="alternate" type="text/html" href="https://www.instagram.com/p/ABC123/" />
  <link rel="ostatus:conversation" href="https://www.instagram.com/p/ABC123/" />

    <link rel="ostatus:attention" href="https://www.instagram.com/snarfed/" />
    <link rel="mentioned" href="https://www.instagram.com/snarfed/" />

  <link rel="ostatus:attention" href="https://www.instagram.com/foo/" />
  <link rel="mentioned" href="https://www.instagram.com/foo/" />

  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>

  <published>2012-09-22T05:25:42+00:00</published>
  <updated>2012-09-22T05:25:42+00:00</updated>

  <georss:point>37.3 -122.5</georss:point>

  <georss:featureName>Le Truc</georss:featureName>

  <link rel="self" href="https://www.instagram.com/p/ABC123/" />
  <link rel="enclosure" href="http://attach/image/big" type="" />

</entry>

</feed>
"""

# HTML objects from https://www.instagram.com/...
# https://github.com/snarfed/granary/issues/65
# https://github.com/snarfed/bridgy/issues/603
HTML_PHOTO_FULL = {
  'id': '123',
  '__typename': 'GraphImage',
  'code': 'ABC123',
  'location': {
    'name': 'RCA Studio B',
    'id': '345924646',
    'has_public_page': True
  },
  'display_src': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfp1/t51.2885-15/e35/12545499_1662965520652470_1466520818_n.jpg',
  'is_video': False,
  'owner': {
    'is_private': False,
    'id': '456',
    'has_blocked_viewer': False,
    'full_name': 'Jerry C',
    'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-frc/t51.2885-19/10903606_836522793073208_584898992_a.jpg',
    'blocked_by_viewer': False,
    'followed_by_viewer': True,
    'requested_by_viewer': False,
    'username': 'jc',
  },
  'edge_media_to_caption': {'edges': [{'node': {
    'text': 'Elvis hits out of RCA Studio B',
  }}]},
  'edge_media_preview_like': {
    'count': 5,
    'edges': [],  # requires extra fetch as of ~8/2018, issue #840
  },
  'viewer_has_liked': False,
  'edge_media_to_comment': {
    'edges': [],
    'page_info': {
      'has_next_page': False,
      'end_cursor': None,
      'start_cursor': None,
      'has_previous_page': False
    },
    'count': 0,
  },
  'dimensions': {'width': 1080, 'height': 1293},
  'taken_at_timestamp': 1453063593,
}

# individual likes need extra fetch as of 8/2018, to eg GET:
# https://www.instagram.com/graphql/query/?query_hash=...&variables={"shortcode":"...","include_reel":false,"first":24}
# (https://github.com/snarfed/bridgy/issues/840)
HTML_PHOTO_LIKES_RESPONSE = {
  'status': 'ok',
  'data': {
    'shortcode_media': {
      'id': '123',
      'shortcode': 'ABC123',
      'edge_liked_by': {
        'count': 9,
        'edges': [{
          'node': {
            'id': '8',
            'profile_pic_url': 'http://alice/picture',
            'username': 'alizz',
            'full_name': 'Alice',
          },
        }, {
          'node': {
            'id': '9',
            'profile_pic_url': 'http://bob/picture',
            'username': 'bobbb',
            'full_name': 'Bob',
            'website': 'http://bob.com/',
          },
        }],  # ...
        # 'page_info': {...},
      },
    },
  },
}

# v2 likes in v2 item 'likers' field
HTML_LIKES_V2 = [{
  'pk': 8,
  'username': 'alizz',
  'full_name': 'Alice',
  # commented out to match LIKE_OBJS, but it is there in IG
  # 'is_private': False,
  'profile_pic_id': '777_8',
  'profile_pic_url': 'http://alice/picture',
}, {
  'pk': 9,
  'username': 'bobbb',
  'full_name': 'Bob',
  'profile_pic_id': '7777_9',
  'profile_pic_url': 'http://bob/picture',
}]

HTML_VIDEO_FULL = {
  'id': '789',
  '__typename': 'GraphVideo',
  'code': 'XYZ789',
  'location': None,
  'display_src': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xpf1/t51.2885-15/s750x750/sh0.08/e35/12424348_567037233461060_1986731502_n.jpg',
  'is_video': True,
  'video_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xtp1/t50.2886-16/12604073_746855092124622_46574942_n.mp4',
  'dimensions': {'height': 640, 'width': 640},
  'owner': {
    'is_private': True,
    'id': '456',
    'full_name': 'Jerry C',
    'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-frc/t51.2885-19/10903606_836522793073208_584898992_a.jpg',
    'username': 'jc',
  },
  'edge_media_to_caption': {'edges': [{'node': {
    'text': 'Eye of deer 👁 and #selfie from me',
  }}]},
  'edge_media_preview_like': {
    'edges': [],
    'count': 9,
  },
  'edge_media_to_comment': {
    'edges': [{'node': {
      'owner': {
        'id': '232927278',
        'profile_pic_url': 'http://picture/commenter',
        'username': 'averygood',
        'full_name': '小正',
      },
      'id': '110',
      'created_at': 1349588757,
      'text': '太可爱了。cute，@a_person, very cute',
      'edge_threaded_comments': {
        'count': 1,
        'edges': [{
          'node': {
            'id': '220',
            'text': 'hah, i have no tips whatsoever',
            'created_at': 1594392712,
            'owner': {
              'id': '420973239',
              'profile_pic_url': 'http://picture/commenter/2',
              'username': 'someone',
            },
          }
        }],
      },
    }}],
    'count':  1,
  },
  'edge_media_to_tagged_user':  {
    'edges':  [{'node':  {
      'user':  {'username':  'ap'},
      'x':  0.4657777507,
      'y':  0.4284444173},
    }],
  },
  'taken_at_timestamp':  1453036552,
}
HTML_VIDEO_EXTRA_COMMENT_OBJ = {  # ActivityStreams
  'objectType': 'comment',
  'author': {
    'objectType': 'person',
    'id': tag_uri('420973239'),
    'displayName': 'someone',
    'username': 'someone',
    'image': {'url': 'http://picture/commenter/2'},
    'url': 'https://www.instagram.com/someone/',
  },
  'content': 'hah, i have no tips whatsoever',
  'id': tag_uri('220'),
  'published': '2020-07-10T14:51:52+00:00',
  'url': 'https://www.instagram.com/p/XYZ789/#comment-220',
  'inReplyTo': [{'id': tag_uri('789_456')}],
  'to': [{'objectType':'group', 'alias':'@public'}],
}

HTML_VIDEO = copy.deepcopy(HTML_VIDEO_FULL)
del HTML_VIDEO['edge_media_preview_like']['edges']
del HTML_VIDEO['edge_media_to_comment']['edges']

HTML_PHOTO = copy.deepcopy(HTML_PHOTO_FULL)
del HTML_PHOTO['edge_media_preview_like']['edges']
del HTML_PHOTO['edge_media_to_comment']['edges']

# based on https://www.instagram.com/p/BQ0mDB2gV_O/
HTML_MULTI_PHOTO = copy.deepcopy(HTML_PHOTO)
HTML_MULTI_PHOTO.update({
  'edge_sidecar_to_children': {
    'edges': [{
      'node': {
        '__typename': 'GraphVideo',
        'id': '1455954809369749561',
        'shortcode': 'BQ0ly9lgWg5',
        'dimensions': {'height': 640, 'width': 640},
        'display_url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t51.2885-15/s640x640/e15/16789781_644256779091860_6907514546886279168_n.jpg',
        'video_url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t50.2886-16/16914332_634350210109260_5674637823722913792_n.mp4',
        'video_view_count': 0,
        'is_video': True,
        'edge_media_to_tagged_user': {'edges': []},
      },
    }, {
      'node': {
        '__typename': 'GraphImage',
        'id': '1455954810972087680',
        'dimensions': {'height': 1080, 'width': 1080},
        'display_url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t51.2885-15/s1080x1080/e35/16906679_776417269184045_871950675452362752_n.jpg',
        'accessibility_caption': 'this is my alt text',
        'is_video': False,
        'edge_media_to_tagged_user': {'edges': []},
      },
    }],
  },
})

HTML_SUGGESTED_USERS = {
  'suggested_users': [{
    'id': '123',
    'username': 'ms_person',
    'full_name': 'Ms Person',
    'biography': 'a person who did stuff',
    'profile_pic_url': 'https://scontent.cdninstagram.com/t51.2885-19/s150x150/13398501_243709166011988_1998688411_a.jpg',
    'edge_followed_by': {'count': 106},
    'is_private': True,
    'is_verified': False,
    'is_viewer': False,
  }],
  '__typename': 'GraphSuggestedUserFeedUnit',
}

HTML_VIEWER_CONFIG = {
  'csrf_token': '...',
  'viewer': {
    'external_url': 'https://snarfed.org',
    'biography': 'something or other',
    'id': '420973239',
    'full_name': 'Ryan B',
    'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_a.jpg',
    'has_profile_pic': True,
    'username': 'snarfed',
  },
}
HTML_FEED = {  # eg old https://www.instagram.com/ when you're logged in
  'environment_switcher_visible_server_guess': True,
  'config': HTML_VIEWER_CONFIG,
  'display_properties_server_guess': {'pixel_ratio': 2.0, 'viewport_width': 1280},
  'qe': {'su': {'g': 'control', 'p': {'enabled': 'false'}}},
  'hostname': 'www.instagram.com',
  'platform': 'web',
  'static_root': '//instagramstatic-a.akamaihd.net/bluebar/cf5f70d',
  'gatekeepers': {'sfbf': True, 'addpp': True, 'rhp': True, 'cpp': True},
  'language_code': 'en',
  'country_code': 'US',
  'entry_data': {'FeedPage': [{'graphql': {'user': {
    'id': '420973239',
    'profile_pic_url': 'https://instagram.fsnc1-1.fna.fbcdn.net/t51.2885-19/11373714_959073410822287_2004790583_a.jpg',
    'username': 'snarfed',
    'edge_web_feed_timeline': {
      'page_info': {
        'has_next_page': True,
        'end_cursor': '...',
      },
      'edges': [
        {'node': HTML_PHOTO_FULL},
        {'node': HTML_VIDEO_FULL},
        {'node': HTML_SUGGESTED_USERS},
      ],
    },
  }}}]},
}
HTML_DEFINES = {  # eg new https://www.instagram.com/ when you're logged in
  'define': [
    ["IntlCurrentLocale", [], {"code": "en_US"}, 5954],
    ["CookieDomain", [], {"domain": "instagram.com"}, 6421],
    ["XIGSharedData", [], {"raw": json_dumps(HTML_FEED), 'native': '...'}, 6186],
  ],
}

# Included with window.__additionalDataLoaded('feed_v2', ...)
# Extracted from https://www.instagram.com/ on 2021-11-24
HTML_PHOTO_V2_FULL = {
  'taken_at': 1450063593,
  'pk': 123,
  'id': '123_456',
  'media_type': 1,  # image?
  'code': 'ABC123',
  'filter_type': 0,
  'product_type': 'feed',

  'user': {
    'pk': 456,
    'username': 'jc',
    'full_name': 'Jerry C',
    'is_private': False,
    'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-frc/t51.2885-19/10903606_836522793073208_584898992_a.jpg',
    'is_verified': False,
  },

  'caption': {
    'pk': 777,
    'text': 'Elvis hits out of RCA Studio B',
    'type': 1,
    'created_at': 1453063593,
    'created_at_utc': 1453063593,
    'content_type': 'comment',
    # 'user': {...}
  },
  'image_versions2': {
   'candidates': [{
     'width': 1080,
     'height': 1293,
     'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfp1/t51.2885-15/e35/12545499_1662965520652470_1466520818_n.jpg',
   },
   # ...
   ]
  },
  'original_width': 1080,
  'original_height': 1293,

  'location': {
    'name': 'RCA Studio B',
    'short_name': 'RCA foo',
    'pk': 345924646,
    'address': '123 A St',
    'city': 'B, California',
    'lng': -121.1,
    'lat': 38.2,
  },

  'like_count': 5,
  'like_and_view_counts_disabled': False,
  'comment_likes_enabled': True,
  'has_more_comments': True,
  'preview_comments': [],
  'comments': [],
  'comment_count': 0,
}

HTML_PHOTO_V2_LIKES = copy.deepcopy(HTML_PHOTO_V2_FULL)
HTML_PHOTO_V2_LIKES['likers'] = HTML_LIKES_V2

HTML_VIDEO_V2_FULL = {
  'pk': 789,
  'id': '789',
  'code': 'XYZ789',
  'media_type': 2,  # video?
  'has_audio': True,
  'is_unified_video': True,
  'product_type': 'igtv',

  'user': {
    'pk': 456,
    'username': 'jc',
    'full_name': 'Jerry C',
    'is_private': True,
    'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-frc/t51.2885-19/10903606_836522793073208_584898992_a.jpg',
    'is_verified': False,
  },

  'caption': {
    'pk': 999,
    'text': 'Eye of deer 👁 and #selfie from me',
    'type': 1,
    'created_at': 1453036552,
    'created_at_utc': 1453036552,
    'content_type': 'comment',
    # 'user': {...}
  },

  'video_duration': 30.0,
  'video_versions': [{
    'type': 101,
    'width': 640,
    'height': 640,
    'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xtp1/t50.2886-16/12604073_746855092124622_46574942_n.mp4',
    'id': '6099'
  }],

  'image_versions2': {
    'candidates': [
      {
        'width': 640,
        'height': 640,
        'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xpf1/t51.2885-15/s750x750/sh0.08/e35/12424348_567037233461060_1986731502_n.jpg'
      },
      # ...
    ]},

  'comment_count': 2,
  'comments': [{
    'pk': 110,
    'media_id': 789,
    'user_id': 232927278,
    'text': '太可爱了。cute，@a_person, very cute',
    'type': 0,
    'created_at': 1349588757,
    'created_at_utc': 1349588757,
    'content_type': 'comment',
    'user': {
      'pk': 232927278,
      'username': 'averygood',
      'full_name': '小正',
      'profile_pic_url': 'http://picture/commenter',
    },
  }, {
    'pk': 220,
    'parent_comment_id': 110,
    'media_id': 789,
    'user_id': 13539831,
    'text': 'hah, i have no tips whatsoever',
    'type': 2,
    'created_at': 1594392712,
    'created_at_utc': 1594392712,
    'content_type': 'comment',
    'user': {
      'pk': 420973239,
      'username': 'someone',
      'profile_pic_url': 'http://picture/commenter/2',
    },
  }],

  'like_count': 9,

  'usertags': {
    'in': [{
      'user': {
        'username': 'ap',
      },
    }],
  },
}

HTML_VIDEO_V2 = copy.deepcopy(HTML_VIDEO_V2_FULL)
HTML_VIDEO_V2['comments'] = []

# comments need extra fetch with media id (not shortcode) as of 1/2022, eg GET:
# https://i.instagram.com/api/v1/media/500668086457901672/comments/?can_support_threading=true&permalink_enabled=false
HTML_VIDEO_V2_COMMENTS_RESPONSE = {
  'caption': HTML_VIDEO_V2_FULL['caption'],
  'comment_count': HTML_VIDEO_V2_FULL['comment_count'],
  'comments': HTML_VIDEO_V2_FULL['comments'],
  'comment_likes_enabled': True,
  'preview_comments': [],
}

HTML_FEED_V2 = {
  'hide_like_and_view_counts': 0,
  'is_direct_v2_enabled': True,
  'items': None,
  'num_results': 12,
  'status': 'ok',
  'feed_items': [
    {'media_or_ad': HTML_PHOTO_V2_FULL},
    {'media_or_ad': HTML_VIDEO_V2_FULL},
  ],
}

HTML_PROFILE = {  # eg https://www.instagram.com/snarfed
  'config': {
    'csrf_token': '6a5737e3f1a23873f98d96e12974e2d5',
    'viewer': None,
  },
  '...': '...',  # many of the same top-level fields as in HTML_FEED
  'entry_data': {'ProfilePage': [{'graphql': {'user': {
    'external_url': 'http://snarfed.org',
    'is_private': False,
    'has_blocked_viewer': False,
    'is_verified': False,
    'blocked_by_viewer': False,
    'edge_owner_to_timeline_media': {
      'count': 1,
      'edges': [
        {'node': HTML_PHOTO},
        {'node': HTML_VIDEO},
      ],
      'page_info': {
        'has_next_page': True,
        'end_cursor': '1151679169740247288',
        'start_cursor': '1178482373937173104',
        'has_previous_page': False,
      },
    },
    'full_name': 'Ryan B',
    'biography': 'something or other',
    'id': '420973239',
    'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_a.jpg',
    'follows_viewer': False,
    'followed_by_viewer': False,
    'has_requested_viewer': False,
    'country_block': None,
    'followed_by': {'count': 458},
    'requested_by_viewer': False,
    'follows': {'count': 295},
    'username': 'snarfed',
    'external_url': 'https://snarfed.org',
  }}}]},
}
HTML_PROFILE_PRIVATE = copy.deepcopy(HTML_PROFILE)
HTML_PROFILE_PRIVATE['entry_data']['ProfilePage'][0]['graphql']['user']['is_private'] = True

# eg https://i.instagram.com/api/v1/users/web_profimle_info/?username=snarfed
# HTTP fetch needs Cookie and X-IG-App-ID headers
# data is similar to HTML_PRELOAD_DATA
HTML_PROFILE_JSON = {
  'data': {
    'user': {
      'edge_owner_to_timeline_media': {
        'count': 159,
        'edges': [
          {'node': HTML_PHOTO},
          {'node': HTML_VIDEO},
        ],
      },
      'id': '420973239',
      'fbid': '17841401357176577',
      'username': 'snarfed',
      'full_name': 'Ryan B',
      'external_url': 'https://snarfed.org',
      'biography': 'something or other',
      'is_private': False,
      'is_verified': False,
      'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_a.jpg',
      'profile_pic_url_hd': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_hd.jpg',
      'followed_by_viewer': False,
      'follows_viewer': False,
      'edge_followed_by': {'count': 168},
      'edge_follow': {'count': 111},
    },
  },
}
HTML_PHOTO_PAGE = {  # eg https://www.instagram.com/p/ABC123/
  'config': {
    'csrf_token': 'xyz',
    'viewer': None,
  },
  '...': '...',  # many of the same top-level fields as in HTML_FEED and HTML_PROFILE
  'entry_data': {'PostPage': [{'graphql': {'shortcode_media': HTML_PHOTO_FULL}}]},
}

HTML_VIDEO_PAGE = {  # eg https://www.instagram.com/p/ABC123/
  'graphql': {'shortcode_media': HTML_VIDEO_FULL},
}

HTML_MULTI_PHOTO_PAGE = {  # eg https://www.instagram.com/p/BQ0mDB2gV_O/
  'config': {
    'csrf_token': 'xyz',
    'viewer': None,
  },
  'entry_data': {'PostPage': [{'graphql': {'shortcode_media': HTML_MULTI_PHOTO}}]},
}
# Returned by logged in https://www.instagram.com/ as of 2018-02-15 ish. nothing
# really usable in this blob, so we have to fetch the preload link.
HTML_USELESS_FEED = {
  'activity_counts': {
    # ...
  },
  'config': {
    'csrf_token': '...',
    # ...
  },
  'hostname': 'www.instagram.com',
  'nonce': '...',
  'platform': 'web',
  'entry_data': {'FeedPage': [{'graphql': None,}]},
  'qe': {
    '004e9939': {
      'g': '',
      'p': None,
    },
    # ...
  },
}
# eg https://www.instagram.com/graphql/query/?query_hash=d6f4...&variables={}
# data is similar to HTML_PROFILE_JSON
HTML_PRELOAD_DATA = {
  'data': {
    'user': {
      'edge_web_feed_timeline': {
        'edges': [
          {'node': HTML_PHOTO_FULL},
          {'node': HTML_VIDEO_FULL},
        ],
        'page_info': {
          'end_cursor': 'KGkA...==',
          'has_next_page': True,
        }
      },
      'id': '420973239',
      'username': 'snarfed',
      'full_name': 'Ryan B',
      'profile_pic_url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_a.jpg',
      'external_url': 'https://snarfed.org',
      'biography': 'something or other',
    }
  },
  'status': 'ok',
}

HTML_HEADER_TEMPLATE = """
<!DOCTYPE html>
<html>
...
<link href="https://www.instagram.com/" rel="alternate" hreflang="x-default" />
%s
...
<body>
<script type="text/javascript">%s"""
HTML_HEADER = HTML_HEADER_TEMPLATE % ('', 'window._sharedData = ')
HTML_HEADER_2 = HTML_HEADER_TEMPLATE % ('', "window.__additionalDataLoaded('feed', ")
HTML_HEADER_3 = HTML_HEADER_TEMPLATE % ('', "window.__additionalDataLoaded('/p/B3Q5Fa8Ja4D/', ")

HTML_PRELOAD_URL = '/graphql/query/?query_hash=cba321&variables={}'
HTML_HEADER_PRELOAD = HTML_HEADER_TEMPLATE % (
  f'<link rel="preload" href="{HTML_PRELOAD_URL}" as="fetch" type="application/json" crossorigin />',
  'window._sharedData = ')
HTML_FOOTER = """\
;</script>
<script src="//instagramstatic-a.akamaihd.net/h1/bundles/en_US_Commons.js/907dcce6a88a.js" type="text/javascript"></script>
...
</body>
</html>
"""

HTML_VIEWER = {
  'displayName': 'Ryan B',
  'id': tag_uri('420973239'),
  'image': {'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_a.jpg'},
  'objectType': 'person',
  'url': 'https://www.instagram.com/snarfed/',
  'urls': [
    {'value': 'https://www.instagram.com/snarfed/'},
    {'value': 'https://snarfed.org'},
  ],
  'username': 'snarfed',
  'description': 'something or other',
}
HTML_VIEWER_PUBLIC = copy.deepcopy(HTML_VIEWER)
HTML_VIEWER_PUBLIC['to'] = [{'alias': '@public', 'objectType': 'group'}]
HTML_ACTOR = {
  'displayName': 'Jerry C',
  'id': tag_uri('456'),
  'image': {'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-frc/t51.2885-19/10903606_836522793073208_584898992_a.jpg'},
  'objectType': 'person',
  'url': 'https://www.instagram.com/jc/',
  'username': 'jc',
  'to': [{'alias': '@public', 'objectType': 'group'}],
}
HTML_ACTOR_PRIVATE = copy.deepcopy(HTML_ACTOR)
HTML_ACTOR_PRIVATE['to'][0]['alias'] = '@private'
HTML_PHOTO_ACTIVITY = {  # ActivityStreams
  # Photo
  'verb': 'post',
  'published': '2016-01-17T20:46:33+00:00',
  'id': tag_uri('123_456'),
  'url': 'https://www.instagram.com/p/ABC123/',
  'actor': HTML_ACTOR,
  'object': {
    'objectType': 'photo',
    'author': HTML_ACTOR,
    'content': 'Elvis hits out of RCA Studio B',
    'id': tag_uri('123_456'),
    'ig_shortcode': 'ABC123',
    'published': '2016-01-17T20:46:33+00:00',
    'url': 'https://www.instagram.com/p/ABC123/',
    'image': {
      'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfp1/t51.2885-15/e35/12545499_1662965520652470_1466520818_n.jpg',
      'width': 1080,
      'height': 1293,
    },
    'to': [{'objectType':'group', 'alias':'@public'}],
    'location': {
      'id': tag_uri('345924646'),
      'displayName': 'RCA Studio B',
      'url': 'https://instagram.com/explore/locations/345924646/',
    },
    'attachments': [{
      'objectType': 'image',
      'url': 'https://www.instagram.com/p/ABC123/',
      'image': [{
        'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfp1/t51.2885-15/e35/12545499_1662965520652470_1466520818_n.jpg',
        'width': 1080,
        'height': 1293,
      }],
    }],
    'replies': {'totalItems': 0},
    'ig_like_count': 5,
  },
}
HTML_PHOTO_ACTIVITY_FULL = copy.deepcopy(HTML_PHOTO_ACTIVITY)
HTML_PHOTO_ACTIVITY_LIKES = copy.deepcopy(HTML_PHOTO_ACTIVITY)
HTML_PHOTO_ACTIVITY_LIKES['object']['tags'] = LIKE_OBJS

HTML_VIDEO_ACTIVITY = {  # ActivityStreams
  # Video
  'verb': 'post',
  'published': '2016-01-17T13:15:52+00:00',
  'id': tag_uri('789_456'),
  'url': 'https://www.instagram.com/p/XYZ789/',
  'actor': HTML_ACTOR_PRIVATE,
  'object': {
    'objectType': 'video',
    'author': HTML_ACTOR_PRIVATE,
    'content': 'Eye of deer \ud83d\udc41 and #selfie from me',
    'content': 'Eye of deer 👁 and #selfie from me',
    'id': tag_uri('789_456'),
    'ig_shortcode': 'XYZ789',
    'published': '2016-01-17T13:15:52+00:00',
    'url': 'https://www.instagram.com/p/XYZ789/',
    'image': {
      'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xpf1/t51.2885-15/s750x750/sh0.08/e35/12424348_567037233461060_1986731502_n.jpg',
      'width': 640,
      'height': 640,
    },
    'to': [{'objectType':'group', 'alias':'@private'}],
    'replies': {'totalItems': 1},
    'ig_like_count': 9,
    'stream': {
      'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xtp1/t50.2886-16/12604073_746855092124622_46574942_n.mp4',
      'width': 640,
      'height': 640,
    },
    'attachments': [{
      'objectType': 'video',
      'url': 'https://www.instagram.com/p/XYZ789/',
      'stream': [{
        'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xtp1/t50.2886-16/12604073_746855092124622_46574942_n.mp4',
        'width': 640,
        'height': 640,
      }],
      'image': [{
        'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xpf1/t51.2885-15/s750x750/sh0.08/e35/12424348_567037233461060_1986731502_n.jpg',
        'width': 640,
        'height': 640,
      }],
    }],
    'tags': [{
      'objectType': 'person',
      'id': tag_uri('ap'),
      'username': 'ap',
      'displayName': 'ap',
      'url': 'https://www.instagram.com/ap/',
    }],
  },
}
HTML_VIDEO_ACTIVITY_FULL = copy.deepcopy(HTML_VIDEO_ACTIVITY)
HTML_VIDEO_ACTIVITY_FULL['object']['replies'] = {
  'items': copy.deepcopy(COMMENT_OBJS) + [HTML_VIDEO_EXTRA_COMMENT_OBJ],
  'totalItems': len(COMMENT_OBJS) + 1,
}
HTML_VIDEO_ACTIVITY_FULL['object']['replies']['items'][0].update({
  'url': 'https://www.instagram.com/p/XYZ789/#comment-110',
  'inReplyTo': [{'id': tag_uri('789_456')}],
})

HTML_MULTI_PHOTO_ACTIVITY = copy.deepcopy(HTML_PHOTO_ACTIVITY)  # ActivityStreams
HTML_MULTI_PHOTO_ACTIVITY['object']['attachments'] = [{
  'objectType': 'video',
  'url': 'https://www.instagram.com/p/BQ0ly9lgWg5/',
  'stream': [{
    'url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t50.2886-16/16914332_634350210109260_5674637823722913792_n.mp4',
    'width': 640,
    'height': 640,
  }],
  'image': [{
    'url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t51.2885-15/s640x640/e15/16789781_644256779091860_6907514546886279168_n.jpg',
    'width': 640,
    'height': 640,
  }],
}, {
  'objectType': 'image',
  'url': 'https://www.instagram.com/p/ABC123/',
  'image': [{
    'url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t51.2885-15/s1080x1080/e35/16906679_776417269184045_871950675452362752_n.jpg',
    'displayName': 'this is my alt text',
    'width': 1080,
    'height': 1080,
  }],
}]

HTML_V2_SUGGESTED_USERS = {
  'suggested_users': {
    'type': 2,
    'suggestions': [
      # ...
    ],
    'landing_site_type': 'suggested_user',
    'title': 'Suggested for You',
    'view_all_text': 'See All',
    'landing_site_title': 'Discover People',
    'cards_size': 'large',
    'id': '60155560',
    'tracking_token': '...',
    # ...
  },
}

HTML_ACTIVITIES = [HTML_PHOTO_ACTIVITY, HTML_VIDEO_ACTIVITY]
HTML_ACTIVITIES_FULL = [HTML_PHOTO_ACTIVITY_FULL, HTML_VIDEO_ACTIVITY_FULL]
HTML_ACTIVITIES_FULL_LIKES = [HTML_PHOTO_ACTIVITY_LIKES, HTML_VIDEO_ACTIVITY_FULL]

HTML_FEED_COMPLETE = HTML_HEADER + json_dumps(HTML_FEED) + HTML_FOOTER

HTML_FEED_COMPLETE_2 = HTML_HEADER_2 + json_dumps(HTML_PRELOAD_DATA['data']) + ')' + HTML_FOOTER

HTML_FEED_COMPLETE_4 = """\
<!DOCTYPE html><html class="..."><script nonce="..."></script>
...
<body>
...
<script>requireLazy(["JSScheduler","ServerJS","ScheduledApplyEach"],function(JSScheduler,ServerJS,ScheduledApplyEach){qpl_inl("...","tierOneBeforeScheduler");JSScheduler.runWithPriority(3,function(){qpl_inl("...","tierOneInsideScheduler");(new ServerJS()).handleWithCustomApplyEach(ScheduledApplyEach,\
""" + json_dumps(HTML_DEFINES) + ');});})' + HTML_FOOTER

HTML_FEED_COMPLETE_V2 = HTML_HEADER + json_dumps(HTML_FEED_V2) + HTML_FOOTER
HTML_PHOTO_ACTIVITY_V2_FULL = copy.deepcopy(HTML_PHOTO_ACTIVITY_FULL)
HTML_PHOTO_ACTIVITY_V2_FULL['object']['location'].update({
  'latitude': 38.2,
  'longitude': -121.1,
  'position': '+38.200000-121.100000/',
  'address': {'formatted': '123 A St'},
})
HTML_PHOTO_ACTIVITY_V2_LIKES = copy.deepcopy(HTML_PHOTO_ACTIVITY_V2_FULL)
HTML_PHOTO_ACTIVITY_V2_LIKES['object']['tags'] = LIKE_OBJS
HTML_VIDEO_ACTIVITY_V2_FULL = copy.deepcopy(HTML_VIDEO_ACTIVITY_FULL)
HTML_VIDEO_ACTIVITY_V2_FULL['object']['replies']['items'][1]['inReplyTo'].append(
  {'id': tag_uri('220')})
HTML_ACTIVITIES_FULL_V2 = [HTML_PHOTO_ACTIVITY_V2_FULL, HTML_VIDEO_ACTIVITY_V2_FULL]

HTML_PROFILE_COMPLETE = HTML_HEADER + json_dumps(HTML_PROFILE) + HTML_FOOTER
HTML_PROFILE_PRIVATE_COMPLETE = HTML_HEADER + json_dumps(HTML_PROFILE_PRIVATE) + HTML_FOOTER
HTML_PHOTO_COMPLETE = HTML_HEADER_3 + json_dumps(HTML_PHOTO_PAGE) + HTML_FOOTER
HTML_VIDEO_COMPLETE = HTML_HEADER_3 + json_dumps(HTML_VIDEO_PAGE) + HTML_FOOTER
HTML_MULTI_PHOTO_COMPLETE = HTML_HEADER + json_dumps(HTML_MULTI_PHOTO_PAGE) + HTML_FOOTER
HTML_PHOTO_MISSING_HEADER = json_dumps(HTML_PHOTO_PAGE) + HTML_FOOTER
HTML_PHOTO_MISSING_FOOTER = HTML_HEADER + json_dumps(HTML_PHOTO_PAGE)


class InstagramTest(testutil.TestCase):

  def setUp(self):
    super(InstagramTest, self).setUp()
    self.instagram = Instagram()
    instagram._last_rate_limited = instagram._last_rate_limited_exc = None

  def expect_requests_get(self, url, resp='', cookie=None, **kwargs):
    kwargs.setdefault('allow_redirects', False)
    if cookie:
      # instagram scraper sets USER-AGENT and App ID headers when cookie that
      # begins with sessionid= is set
      kwargs.setdefault('headers', HEADERS)['Cookie'] = 'sessionid=' + cookie
    if not url.startswith('http'):
      url = HTML_BASE_URL + url
    return super(InstagramTest, self).expect_requests_get(url, resp, **kwargs)

  def test_get_actor(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/foo',
                        json_dumps({'data': USER}))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.instagram.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self',
                        json_dumps({'data': USER}))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.instagram.get_actor())

  def test_get_actor_scrape(self):
    self.expect_requests_get('foo/', HTML_PROFILE_COMPLETE)
    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTOR, Instagram(scrape=True).get_actor('foo'))

  def test_get_activities_self(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self/media/recent',
                        json_dumps({'data': []}))
    self.mox.ReplayAll()
    self.assert_equals([], self.instagram.get_activities(group_id=source.SELF))

  def test_get_activities_self_fetch_likes(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self/media/recent',
                        json_dumps({'data': [MEDIA]}))
    self.expect_urlopen('https://api.instagram.com/v1/users/self/media/liked',
                        json_dumps({'data': [MEDIA_WITH_LIKES]}))
    self.expect_urlopen('https://api.instagram.com/v1/users/self',
                        json_dumps({'data': LIKES[0]}))
    self.mox.ReplayAll()
    self.assert_equals(
      [ACTIVITY, LIKE_OBJS[0]],
      self.instagram.get_activities(group_id=source.SELF, fetch_likes=True))

  def test_get_activities_passes_through_access_token(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/users/self/feed?access_token=asdf',
      json_dumps({'meta': {'code': 200}, 'data': []}))
    self.mox.ReplayAll()

    self.instagram = Instagram(access_token='asdf')
    self.instagram.get_activities()

  def test_get_activities_activity_id_shortcode(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        json_dumps({'data': MEDIA}))
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals([ACTIVITY], self.instagram.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_activity_id_not_found(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        '{"meta":{"error_type":"APINotFoundError"}}',
                        status=400)
    self.mox.ReplayAll()
    self.assert_equals([], self.instagram.get_activities(activity_id='000'))

  def test_get_activities_with_likes(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self/feed',
                        json_dumps({'data': [MEDIA_WITH_LIKES]}))
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY_WITH_LIKES], self.instagram.get_activities())

  def test_get_activities_other_400_error(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        'BAD REQUEST', status=400)
    self.mox.ReplayAll()
    self.assertRaises(urllib.error.HTTPError, self.instagram.get_activities,
                      activity_id='000')

  def test_get_activities_min_id(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/users/self/media/recent?min_id=135',
      json_dumps({'data': []}))
    self.mox.ReplayAll()
    self.instagram.get_activities(group_id=source.SELF, min_id='135')

  def test_get_activities_search(self):
    self.expect_urlopen('https://api.instagram.com/v1/tags/indieweb/media/recent',
                        json_dumps({'data': [MEDIA]}))
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY], self.instagram.get_activities(
      group_id=source.SEARCH, search_query='#indieweb'))

  def test_get_activities_search_non_hashtag(self):
    with self.assertRaises(ValueError):
      self.instagram.get_activities(search_query='foo')

  def test_get_activities_scrape_self(self):
    self.expect_requests_get('x/', HTML_PROFILE_COMPLETE +
                             # check that we ignore this for profile fetches
                             ' not-logged-in ')
    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTIVITIES, self.instagram.get_activities(
      user_id='x', group_id=source.SELF, scrape=True))

  def test_get_activities_response_scrape_self_viewer(self):
    self.expect_requests_get('x/', HTML_PROFILE_COMPLETE)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      user_id='x', group_id=source.SELF, scrape=True)
    self.assert_equals(HTML_ACTIVITIES, resp['items'])
    self.assert_equals(HTML_VIEWER_PUBLIC, resp['actor'])

  def test_get_activities_scrape_self_fetch_extras(self):
    self.expect_requests_get('x/', HTML_PROFILE_COMPLETE, cookie='kuky')
    self.expect_requests_get('p/ABC123/', HTML_PHOTO_COMPLETE, cookie='kuky')
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'ABC123',
                             HTML_PHOTO_LIKES_RESPONSE, cookie='kuky')
    self.expect_requests_get('p/XYZ789/', HTML_VIDEO_COMPLETE, cookie='kuky')
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'XYZ789', {}, cookie='kuky')

    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTIVITIES_FULL_LIKES, self.instagram.get_activities(
      user_id='x', group_id=source.SELF, fetch_likes=True, fetch_replies=True,
      scrape=True, cookie='kuky'))

  def test_get_activities_scrape_fetch_extras_cache(self):
    # first time, cache is cold
    self.expect_requests_get('x/', HTML_PROFILE_COMPLETE, cookie='kuky')
    self.expect_requests_get('p/ABC123/', HTML_PHOTO_COMPLETE, cookie='kuky')
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'ABC123',
                             HTML_PHOTO_LIKES_RESPONSE, cookie='kuky')
    self.expect_requests_get('p/XYZ789/', HTML_VIDEO_COMPLETE, cookie='kuky')
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'XYZ789', {}, cookie='kuky')

    # second time, comment and like counts are unchanged, so no media page fetches
    self.expect_requests_get('x/', HTML_PROFILE_COMPLETE, cookie='kuky')

    # third time, video comment count changes, like counts stay the same
    profile = copy.deepcopy(HTML_PROFILE)
    profile['entry_data']['ProfilePage'][0]['graphql']['user']\
      ['edge_owner_to_timeline_media']['edges'][1]['node']\
      ['edge_media_to_comment']['count'] = 3
    self.expect_requests_get('x/',
                             HTML_HEADER + json_dumps(profile) + HTML_FOOTER,
                             cookie='kuky')
    video = copy.deepcopy(HTML_VIDEO_FULL)
    video['edge_media_to_comment']['count'] = 4
    self.expect_requests_get('p/XYZ789/',
                             HTML_HEADER + json_dumps(video) + HTML_FOOTER,
                             cookie='kuky')

    self.mox.ReplayAll()

    cache = {}
    for _ in range(3):
      self.instagram.get_activities(user_id='x', group_id=source.SELF,
                                    fetch_likes=True, fetch_replies=True,
                                    scrape=True, cache=cache, cookie='kuky')

    self.assert_equals({
      'AIC 123_456': 0,  # photo
      'AIL 123_456': 5,
      'AIC 789_456': 1,  # video
      'AIL 789_456': 9,
    }, cache)

  def test_get_activities_scrape_missing_data(self):
    self.expect_requests_get('x/', """
<!DOCTYPE html>
<html><body>
</body></html>
""")
    self.mox.ReplayAll()
    self.assert_equals([], self.instagram.get_activities(
      user_id='x', group_id=source.SELF, scrape=True))

  def test_get_activities_scrape_fetch_likes_no_cookie_error(self):
    with self.assertRaises(NotImplementedError):
      self.instagram.get_activities(user_id='x', group_id=source.SELF,
                                    fetch_likes=True, scrape=True)

  def test_get_activities_scrape_friends_cookie(self):
    self.expect_requests_get(HTML_BASE_URL, HTML_FEED_COMPLETE, cookie='kuky')
    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTIVITIES_FULL, self.instagram.get_activities(
      user_id='self', group_id=source.FRIENDS, scrape=True, cookie='kuky'))

  def test_get_activities_response_scrape_friends_viewer(self):
    self.expect_requests_get(HTML_BASE_URL, HTML_FEED_COMPLETE, cookie='kuky')
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.FRIENDS, scrape=True, cookie='kuky')
    self.assert_equals(HTML_ACTIVITIES_FULL, resp['items'])
    self.assert_equals(HTML_VIEWER, resp['actor'])

  def test_get_activities_scrape_cookie_not_logged_in(self):
    self.expect_requests_get(HTML_BASE_URL, '<html>not-logged-in</html>',
                             cookie='kuky')
    self.mox.ReplayAll()

    with self.assertRaises(requests.HTTPError) as cm:
      self.instagram.get_activities(group_id=source.FRIENDS, scrape=True,
                                    cookie='kuky')

    self.assertEqual('401 Unauthorized', str(cm.exception))
    self.assertEqual(401, cm.exception.response.status_code)

  def test_get_activities_scrape_activity_id(self):
    self.expect_requests_get('p/BDG6Ms_J0vQ/', HTML_PHOTO_COMPLETE)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, scrape=True, activity_id='1208909509631101904_942513')
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], resp['items'])
    self.assertIsNone(resp['actor'])

  def test_get_activities_scrape_activity_id_shortcode(self):
    self.expect_requests_get('p/BDG6Ms_J0vQ/', HTML_PHOTO_COMPLETE)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, scrape=True, activity_id='BDG6Ms_J0vQ')
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], resp['items'])

  def test_get_activities_scrape_activity_id_shortcode_404(self):
    self.expect_requests_get('p/B7/', status_code=404)
    self.expect_requests_get('p/123_ABC/', HTML_PHOTO_COMPLETE)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, scrape=True, activity_id='123_ABC')
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], resp['items'])

  def test_get_activities_scrape_cookie_redirects_to_login(self):
    self.expect_requests_get(
      HTML_BASE_URL,
      status_code=302,
      redirected_url='https://www.instagram.com/accounts/login/?next=/',
      cookie='kuky')
    self.mox.ReplayAll()

    with self.assertRaises(requests.HTTPError) as cm:
      self.instagram.get_activities(group_id=source.FRIENDS, scrape=True,
                                    cookie='kuky')

    self.assertEqual('401 Unauthorized', str(cm.exception))
    self.assertEqual(401, cm.exception.response.status_code)

  def test_get_activities_scrape_options_not_implemented(self):
    for group_id in None, source.ALL, source.SEARCH:
      with self.assertRaises(NotImplementedError):
        self.instagram.get_activities(user_id='x', group_id=group_id, scrape=True)

    with self.assertRaises(NotImplementedError):
      # SELF requires user_id
      self.instagram.get_activities(group_id=source.SELF, scrape=True)

    with self.assertRaises(NotImplementedError):
      # FRIENDS requires cookie
      self.instagram.get_activities(group_id=source.FRIENDS, scrape=True)

  def test_get_activities_scrape_not_found(self):
    self.expect_requests_get('foo/', status_code=404)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, user_id='foo', scrape=True)
    self.assertIsNone(resp['actor'])
    self.assertEqual([], resp['items'])

  def test_get_activities_scrape_rate_limited(self):
    # first attempt: rate limited
    self.expect_requests_get(HTML_BASE_URL, status_code=429, cookie='kuky')
    # third attempt ignore rate limit lock. fourth limit is past lock.
    for _ in range(2):
      self.expect_requests_get('x/', HTML_PROFILE_COMPLETE)
    self.mox.ReplayAll()

    # first attempt makes the fetch, gets the 429 response, and sets the
    # global rate limit lock. second attempt sees the lock and short circuits.
    with self.assertRaises(requests.HTTPError) as cm:
      self.instagram.get_activities(group_id=source.FRIENDS, scrape=True,
                                    cookie='kuky')
    self.assertEqual(429, cm.exception.response.status_code)

    # second attempt sees the lock and short circuits, even though it's for a
    # different path (profile vs front page).
    with self.assertRaises(requests.HTTPError) as cm:
      Instagram().get_activities(user_id='x', group_id=source.SELF, scrape=True)
    self.assertEqual(429, cm.exception.response.status_code)

    self.assert_equals(HTML_ACTIVITIES, Instagram().get_activities(
      user_id='x', group_id=source.SELF, scrape=True, ignore_rate_limit=True))

    # move rate limit lock back beyond threshold, third attempt should try again.
    instagram._last_rate_limited -= (instagram.RATE_LIMIT_BACKOFF +
                                     datetime.timedelta(seconds=5))
    self.assert_equals(HTML_ACTIVITIES, Instagram().get_activities(
      user_id='x', group_id=source.SELF, scrape=True))

  def test_get_video(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/5678',
                        json_dumps({'data': VIDEO}))
    self.mox.ReplayAll()
    self.assert_equals([VIDEO_ACTIVITY],
                       self.instagram.get_activities(activity_id='5678'))

  def test_get_comment(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/123_456',
                        json_dumps({'data': MEDIA}))
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJS[0],
                       self.instagram.get_comment('110', activity_id='123_456'))

  def test_get_comment_not_found(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/123_456',
                        json_dumps({'data': MEDIA}))
    self.mox.ReplayAll()
    self.assertIsNone(self.instagram.get_comment('111', activity_id='123_456'))

  def test_get_comment_scrape(self):
    self.expect_requests_get('p/BDG6Ms_J0vQ/', HTML_VIDEO_COMPLETE)
    self.mox.ReplayAll()

    ig = Instagram(scrape=True)
    self.assert_equals(HTML_VIDEO_ACTIVITY_FULL['object']['replies']['items'][0],
                       ig.get_comment('110', activity_id='1208909509631101904_942513'))

  def test_get_comment_with_activity(self):
    # skips API call
    self.assert_equals(COMMENT_OBJS[0],
                          self.instagram.get_comment('110', activity=ACTIVITY))

  def test_get_like(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        json_dumps({'data': MEDIA_WITH_LIKES}))
    self.mox.ReplayAll()
    self.assert_equals(LIKE_OBJS[1], self.instagram.get_like('123', '000', '9'))

  def test_get_like_not_found(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        json_dumps({'data': MEDIA}))
    self.mox.ReplayAll()
    self.assertIsNone(self.instagram.get_like('123', '000', 'xyz'))

  def test_get_like_no_activity(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        '{"meta":{"error_type":"APINotFoundError"}}',
                        status=400)
    self.mox.ReplayAll()
    self.assertIsNone(self.instagram.get_like('123', '000', '9'))

  def test_get_like_scrape(self):
    self.expect_requests_get('p/BDG6Ms_J0vQ/', HTML_PHOTO_COMPLETE,
                             cookie='kuky')
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'ABC123',
                             HTML_PHOTO_LIKES_RESPONSE, cookie='kuky')
    self.mox.ReplayAll()

    ig = Instagram(scrape=True, cookie='kuky')
    self.assert_equals(LIKE_OBJS[0],
                       ig.get_like('456', '1208909509631101904_942513', '8'))

  def test_media_to_activity(self):
    self.assert_equals(ACTIVITY, self.instagram.media_to_activity(MEDIA))

  def test_media_to_object(self):
    obj = self.instagram.media_to_object(MEDIA)
    self.assert_equals(MEDIA_OBJ, obj)

    # check that the images are ordered the way we expect, largest to smallest
    self.assertEqual(MEDIA_OBJ['attachments'][0]['image'],
                     obj['attachments'][0]['image'])

  def test_media_to_object_with_likes(self):
    self.assert_equals(MEDIA_OBJ_WITH_LIKES,
                       self.instagram.media_to_object(MEDIA_WITH_LIKES))

  def test_comment_to_object(self):
    for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
      self.assert_equals(obj, self.instagram.comment_to_object(
          cmt, '123_456', 'https://www.instagram.com/p/ABC123/'))

  def test_user_to_actor(self):
    self.assert_equals(ACTOR, self.instagram.user_to_actor(USER))

  def test_user_to_actor_url_fallback(self):
    user = copy.deepcopy(USER)
    del user['website']
    del user['bio']
    actor = copy.deepcopy(ACTOR)
    actor['url'] = 'https://www.instagram.com/snarfed/'
    del actor['urls']
    del actor['description']
    self.assert_equals(actor, self.instagram.user_to_actor(user))

  def test_user_to_actor_displayName_fallback(self):
    self.assert_equals({
      'objectType': 'person',
      'id': tag_uri('420973239'),
      'username': 'snarfed',
      'displayName': 'snarfed',
      'url': 'https://www.instagram.com/snarfed/',
    }, self.instagram.user_to_actor({
      'id': '420973239',
      'username': 'snarfed',
    }))

  def test_user_to_actor_minimal(self):
    self.assert_equals({
      'id': tag_uri('420973239'),
      'username': None,
      'objectType': 'person',
    }, self.instagram.user_to_actor({'id': '420973239'}))

    self.assert_equals({
      'id': tag_uri('snarfed'),
      'username': 'snarfed',
      'displayName': 'snarfed',
      'objectType': 'person',
      'url': 'https://www.instagram.com/snarfed/',
    }, self.instagram.user_to_actor({'username': 'snarfed'}))

  def test_preview_like(self):
    # like obj doesn't have a url prior to publishing
    to_publish = copy.deepcopy(LIKE_OBJS[0])
    del to_publish['url']

    self.mox.ReplayAll()
    preview = self.instagram.preview_create(to_publish)

    self.assertIn('like', preview.description)
    self.assertIn('this post', preview.description)

  def test_create_like(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/media/shortcode/ABC123',
      json_dumps({'data': MEDIA}))

    self.expect_urlopen(
      'https://api.instagram.com/v1/media/123_456/likes',
      '{"meta":{"status":200}}', data='access_token=None')

    self.expect_urlopen(
      'https://api.instagram.com/v1/users/self',
      json_dumps({'data': {
        'id': '8',
        'username': 'alizz',
        'full_name': 'Alice',
        'profile_picture': 'http://alice/picture',
      }}))

    # like obj doesn't have url or id prior to publishing
    to_publish = copy.deepcopy(LIKE_OBJS[0])
    del to_publish['id']
    del to_publish['url']

    self.mox.ReplayAll()
    self.assertEqual(source.creation_result(LIKE_OBJS[0]),
                     self.instagram.create(to_publish))

  def test_preview_comment(self):
    # comment obj doesn't have a url prior to publishing
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    to_publish['content'] = 'very<br />cute'
    del to_publish['url']

    self.mox.ReplayAll()
    preview = Instagram(allow_comment_creation=True).preview_create(to_publish)

    self.assertIn('comment', preview.description)
    self.assertIn('this post', preview.description)
    self.assertIn('very\ncute', preview.content)

  def test_create_comment(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/media/123_456/comments',
      '{"meta":{"status":200}}',
      data=urllib.parse.urlencode({'access_token': self.instagram.access_token,
                             'text': COMMENTS[0]['text']}))

    self.mox.ReplayAll()
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    del to_publish['url']

    result = Instagram(allow_comment_creation=True).create(to_publish)
    # TODO instagram does not give back a comment object; not sure how to
    # get the comment id. for now, just check that creation was successful
    # self.assert_equals(source.creation_result(COMMENT_OBJS[0]),
    #                       self.instagram.create(to_publish))
    self.assertTrue(result.content)
    self.assertFalse(result.abort)

  def test_create_comment_unauthorized(self):
    # a more realistic test. this is what happens when you try to
    # create comments with the API, with an unapproved app
    self.expect_urlopen(
      'https://api.instagram.com/v1/media/123_456/comments',
      data=urllib.parse.urlencode({'access_token': self.instagram.access_token,
                             'text': COMMENTS[0]['text']}),
      response='{"meta": {"code": 400, "error_type": u"OAuthPermissionsException", "error_message": "This request requires scope=comments, but this access token is not authorized with this scope. The user must re-authorize your application with scope=comments to be granted write permissions."}}',
      status=400)

    self.mox.ReplayAll()
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    del to_publish['url']

    self.assertRaises(urllib.error.HTTPError, Instagram(
      allow_comment_creation=True).create, to_publish)

  def test_create_comments_disabled(self):
    """Check that comment creation raises a sensible error when it's
    disabled on our side.
    """
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    del to_publish['url']

    preview = self.instagram.preview_create(to_publish)
    self.assertTrue(preview.abort)
    self.assertIn('Cannot publish comments', preview.error_plain)
    self.assertIn('Cannot', preview.error_html)

    create = self.instagram.create(to_publish)
    self.assertTrue(create.abort)
    self.assertIn('Cannot publish comments', create.error_plain)
    self.assertIn('Cannot', create.error_html)

  def test_base_object(self):
    self.assertEqual({
      'id': '123',
      'url': 'https://www.instagram.com/p/zHA5BLo1Mo/',
      }, self.instagram.base_object({
        'id': tag_uri('123_456_liked_by_789'),
        'object': {'url': 'https://www.instagram.com/p/zHA5BLo1Mo/'},
      }))

    # with only URL, we don't know id
    self.assertEqual(
      {'url': 'https://www.instagram.com/p/zHA5BLo1Mo/'},
      self.instagram.base_object({
        'object': {'url': 'https://www.instagram.com/p/zHA5BLo1Mo/'},
      }))

  def test_scraped_to_activities_feed(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_FEED_COMPLETE)
    self.assert_equals(HTML_ACTIVITIES_FULL, activities)
    self.assert_equals(HTML_VIEWER, viewer)

    activities, _ = self.instagram.scraped_to_activities(HTML_FEED_COMPLETE_2)
    self.assert_equals(HTML_ACTIVITIES_FULL, activities)

    _, viewer = self.instagram.scraped_to_activities(HTML_FEED_COMPLETE_4)
    self.assert_equals(HTML_VIEWER, viewer)

  def test_scraped_to_activities_feed_v2(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_FEED_COMPLETE_V2)
    self.assert_equals(HTML_ACTIVITIES_FULL_V2, activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_profile(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_PROFILE_COMPLETE)
    self.assert_equals(HTML_ACTIVITIES, activities)
    self.assert_equals(HTML_VIEWER_PUBLIC, viewer)

  def test_scraped_to_activities_profile_private(self):
    _, actor = self.instagram.scraped_to_activities(HTML_PROFILE_PRIVATE_COMPLETE)
    self.assert_equals([{'objectType':'group', 'alias':'@private'}], actor['to'])

  def test_scraped_to_activities_profile_fill_in_owner(self):
    profile = copy.deepcopy(HTML_PROFILE)
    user = profile['entry_data']['ProfilePage'][0]['graphql']['user']
    user['edge_owner_to_timeline_media']['edges'][0]['node']['owner'] = {
      'id': user['id'],
    }

    activities, _ = self.instagram.scraped_to_activities(
      HTML_HEADER + json_dumps(profile) + HTML_FOOTER)
    self.assertEqual(HTML_VIEWER_PUBLIC, activities[0]['actor'])
    self.assertEqual(HTML_VIEWER_PUBLIC, activities[0]['object']['author'])

  def test_scraped_to_activities_profile_wrong_id_dont_fill_in_owner(self):
    profile = copy.deepcopy(HTML_PROFILE)
    user = profile['entry_data']['ProfilePage'][0]['graphql']['user']
    other_id = user['id'] + '999'
    user['edge_owner_to_timeline_media']['edges'][0]['node']['owner'] = {
      'id': other_id,
    }

    activities, _ = self.instagram.scraped_to_activities(
      HTML_HEADER + json_dumps(profile) + HTML_FOOTER)
    expected = {
      'id': tag_uri(other_id),
      'objectType': 'person',
    }
    self.assertEqual(expected, activities[0]['actor'])
    self.assertEqual(expected, activities[0]['object']['author'])

  def test_scraped_json_to_activities_profile(self):
    activities, actor = self.instagram.scraped_json_to_activities(HTML_PROFILE_JSON)
    self.assert_equals(HTML_ACTIVITIES, activities)
    self.assert_equals(HTML_VIEWER_PUBLIC, actor)

  def test_scraped_to_activities_json_input(self):
    activities, actor = self.instagram.scraped_to_activities(
      json_dumps(HTML_PROFILE_JSON))
    self.assert_equals(HTML_ACTIVITIES, activities)
    self.assert_equals(HTML_VIEWER_PUBLIC, actor)

  def test_scraped_json_to_activities_suggested_users(self):
    activities, actor = self.instagram.scraped_json_to_activities(
      {'feed_items': [HTML_V2_SUGGESTED_USERS]})
    self.assert_equals([], activities)
    self.assert_equals(None, actor)

  def test_scraped_to_activities_photo_no_fetch_extras(self):
    activities, viewer = self.instagram.scraped_to_activities(
      HTML_PHOTO_COMPLETE, fetch_extras=False)
    self.assert_equals([HTML_PHOTO_ACTIVITY], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_photo_fetch_extras(self):
    self.instagram.cookie = 'kuky'
    self.expect_requests_get(
      instagram.HTML_LIKES_URL % 'ABC123', HTML_PHOTO_LIKES_RESPONSE,
      headers=mox.IgnoreArg())
    self.mox.ReplayAll()

    activities, viewer = self.instagram.scraped_to_activities(
      HTML_PHOTO_COMPLETE, fetch_extras=True)
    self.assert_equals([HTML_PHOTO_ACTIVITY_LIKES], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activity_photo_no_fetch_extras(self):
    self.assert_equals(
      (HTML_PHOTO_ACTIVITY, None),
      self.instagram.scraped_to_activity(HTML_PHOTO_COMPLETE, fetch_extras=False))

  def test_scraped_to_activity_photo_with_viewer(self):
    page = copy.deepcopy(HTML_PHOTO_PAGE)
    page['config'] = HTML_VIEWER_CONFIG
    html = HTML_HEADER + json_dumps(page) + HTML_FOOTER

    self.assert_equals((HTML_PHOTO_ACTIVITY, HTML_VIEWER),
                       self.instagram.scraped_to_activity(html))

  def test_scraped_to_activity_photo_fetch_extras(self):
    self.instagram.cookie = 'kuky'
    self.expect_requests_get(
      instagram.HTML_LIKES_URL % 'ABC123', HTML_PHOTO_LIKES_RESPONSE,
      headers=mox.IgnoreArg())
    self.mox.ReplayAll()

    activity, actor = self.instagram.scraped_to_activity(
      HTML_PHOTO_COMPLETE, fetch_extras=True)
    self.assert_equals(HTML_PHOTO_ACTIVITY_LIKES, activity)
    self.assertIsNone(actor)

  def test_scraped_to_activities_photo_edge_media_to_parent_comment(self):
    """https://github.com/snarfed/granary/issues/164"""
    self.instagram.cookie = 'kuky'
    self.expect_requests_get(
      instagram.HTML_LIKES_URL % 'ABC123', HTML_PHOTO_LIKES_RESPONSE,
      headers=mox.IgnoreArg())
    self.mox.ReplayAll()

    page = copy.deepcopy(HTML_PHOTO_PAGE)
    media = page['entry_data']['PostPage'][0]['graphql']['shortcode_media']
    media['edge_media_to_parent_comment'] = media.pop('edge_media_to_comment')
    activities, _ = self.instagram.scraped_to_activities(
      HTML_HEADER + json_dumps(page) + HTML_FOOTER, fetch_extras=True)
    self.assert_equals([HTML_PHOTO_ACTIVITY_LIKES], activities)

  def test_scraped_to_activities_video(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_VIDEO_COMPLETE)
    self.assert_equals([HTML_VIDEO_ACTIVITY_FULL], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_multi_photo(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_MULTI_PHOTO_COMPLETE)
    self.assert_equals([HTML_MULTI_PHOTO_ACTIVITY], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_multi_photo_omit_auto_alt_text(self):
    multi = copy.deepcopy(HTML_MULTI_PHOTO_PAGE)
    multi['entry_data']['PostPage'][0]['graphql']['shortcode_media']\
        ['edge_sidecar_to_children']['edges'][1]['node']['accessibility_caption'] = \
        instagram.AUTO_ALT_TEXT_PREFIXES[1] + 'foo bar'
    html = HTML_HEADER + json_dumps(multi) + HTML_FOOTER

    expected = copy.deepcopy(HTML_MULTI_PHOTO_ACTIVITY)
    del expected['object']['attachments'][1]['image'][0]['displayName']

    activities, _ = self.instagram.scraped_to_activities(html)
    self.assert_equals([expected], activities)

  def test_scraped_to_activities_photo_v2(self):
    html = HTML_HEADER_3 + json_dumps({'items': [HTML_PHOTO_V2_FULL]}) + HTML_FOOTER
    activities, viewer = self.instagram.scraped_to_activities(html)
    self.assert_equals([HTML_PHOTO_ACTIVITY_V2_FULL], activities)

  def test_scraped_to_activities_photo_v2_likes(self):
    html = HTML_HEADER_3 + json_dumps({'items': [HTML_PHOTO_V2_LIKES]}) + HTML_FOOTER
    activities, viewer = self.instagram.scraped_to_activities(html)

    expected = copy.deepcopy(HTML_PHOTO_ACTIVITY_V2_LIKES)
    # v2 likes don't have user website field
    del expected['object']['tags'][1]['author']['urls']
    self.assert_equals([expected], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_video_v2(self):
    html = HTML_HEADER_3 + json_dumps({'items': [HTML_VIDEO_V2_FULL]}) + HTML_FOOTER
    activities, viewer = self.instagram.scraped_to_activities(html)
    self.assert_equals([HTML_VIDEO_ACTIVITY_V2_FULL], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_video_v2_no_fetch_extras(self):
    html = HTML_HEADER_3 + json_dumps({'items': [HTML_VIDEO_V2]}) + HTML_FOOTER
    activities, viewer = self.instagram.scraped_to_activities(html, fetch_extras=False)

    expected = copy.deepcopy(HTML_VIDEO_ACTIVITY)
    expected['object']['replies']['totalItems'] = 2
    self.assert_equals([expected], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_photos_v2_fetch_extras(self):
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'ABC123',
                             HTML_PHOTO_LIKES_RESPONSE, cookie='kuky')
    self.mox.ReplayAll()
    ig = Instagram(scrape=True, cookie='kuky')
    html = HTML_HEADER_2 + json_dumps({'items': [HTML_PHOTO_V2_FULL]}) + HTML_FOOTER
    activities, _ = ig.scraped_to_activities(html, fetch_extras=True)
    self.assert_equals([HTML_PHOTO_ACTIVITY_V2_LIKES], activities)

  def test_scraped_to_activities_video_v2_fetch_comments(self):
    self.expect_requests_get(instagram.HTML_COMMENTS_URL % '789',
                             HTML_VIDEO_V2_COMMENTS_RESPONSE, cookie='kuky')
    self.expect_requests_get(instagram.HTML_LIKES_URL % 'XYZ789',
                             {}, cookie='kuky')
    self.mox.ReplayAll()

    video_empty_comments = copy.deepcopy(HTML_VIDEO_V2_FULL)
    video_empty_comments['comments'] = []
    ig = Instagram(scrape=True, cookie='kuky')
    html = HTML_HEADER_2 + json_dumps({'items': [video_empty_comments]}) + HTML_FOOTER
    activities, _ = ig.scraped_to_activities(html, fetch_extras=True)
    self.assert_equals([HTML_VIDEO_ACTIVITY_V2_FULL], activities)

  def test_scraped_to_activities_photo_v2_no_user(self):
    photo = copy.deepcopy(HTML_PHOTO_V2_FULL)
    del photo['user']
    html = HTML_HEADER_3 + json_dumps({'items': [photo]}) + HTML_FOOTER
    activities, viewer = self.instagram.scraped_to_activities(html)

    activity = copy.deepcopy(HTML_PHOTO_ACTIVITY_V2_FULL)
    activity['object']['id'] = activity['id'] = 'tag:instagram.com:123'
    del activity['actor']
    del activity['object']['author']
    del activity['object']['to']
    self.assert_equals([activity], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_missing_profile_picture_external_url(self):
    data = copy.deepcopy(HTML_FEED)
    data['config']['viewer']['profile_pic_url'] = None
    data['config']['viewer']['external_url'] = None
    _, viewer = self.instagram.scraped_to_activities(
      HTML_HEADER + json_dumps(data) + HTML_FOOTER)

    expected = copy.deepcopy(HTML_VIEWER)
    del expected['urls']
    del expected['image']
    self.assert_equals(expected, viewer)

  def test_scraped_to_activities_missing_video_url(self):
    data = copy.deepcopy(HTML_FEED)
    del data['entry_data']['FeedPage'][0]['graphql']['user']\
            ['edge_web_feed_timeline']['edges'][1]['node']['video_url']
    activities, _ = self.instagram.scraped_to_activities(
      HTML_HEADER + json_dumps(data) + HTML_FOOTER)

    expected = copy.deepcopy(HTML_ACTIVITIES_FULL)
    del expected[1]['object']['stream']
    del expected[1]['object']['attachments'][0]['stream'][0]['url']
    self.assert_equals(expected, activities)

  def test_scraped_to_activities_missing_header(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_PHOTO_MISSING_HEADER)
    self.assert_equals([], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_missing_footer(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_PHOTO_MISSING_FOOTER)
    self.assert_equals([], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_trims_nulls(self):
    activities, viewer = self.instagram.scraped_to_activities(HTML_HEADER + json_dumps({
      'entry_data': {
        'FeedPage': [{
          'feed': {
            'media': {
              'nodes': None,
            }
          }
        }],
        'ProfilePage': {'graphql': {'user': None}},
        'PostPage': None,
      },
    }) + HTML_FOOTER)
    self.assert_equals([], activities)
    self.assertIsNone(viewer)

  def test_scraped_to_activities_preload_fetch(self):
    """https://github.com/snarfed/granary/issues/140"""
    url = urllib.parse.urljoin(HTML_BASE_URL, HTML_PRELOAD_URL)
    self.expect_requests_get(url, HTML_PRELOAD_DATA, cookie='kuky')
    self.mox.ReplayAll()

    html = HTML_HEADER_PRELOAD + json_dumps(HTML_USELESS_FEED) + HTML_FOOTER
    activities, viewer = self.instagram.scraped_to_activities(html, cookie='kuky')

    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL, HTML_VIDEO_ACTIVITY_FULL],
                       activities)
    self.assert_equals(HTML_VIEWER, viewer)

  def test_scraped_to_activities_preload_fetch_bad_json(self):
    """https://console.cloud.google.com/errors/CP_w8ai-7JLfvAE"""
    url = urllib.parse.urljoin(HTML_BASE_URL, HTML_PRELOAD_URL)
    self.expect_requests_get(url, '{bad: ["json', cookie='kuky')
    self.mox.ReplayAll()

    html = HTML_HEADER_PRELOAD + json_dumps(HTML_USELESS_FEED) + HTML_FOOTER
    with self.assertRaises(requests.HTTPError) as cm:
      self.instagram.scraped_to_activities(html, cookie='kuky')

    self.assertEqual(504, cm.exception.response.status_code)

  def test_merge_scraped_comments(self):
    activity = copy.deepcopy(HTML_VIDEO_ACTIVITY)
    got = self.instagram.merge_scraped_comments(
      json_dumps(HTML_VIDEO_V2_COMMENTS_RESPONSE), activity)

    expected = copy.deepcopy(HTML_VIDEO_ACTIVITY_V2_FULL)
    self.assert_equals(HTML_VIDEO_ACTIVITY_V2_FULL['object']['replies']['items'], got)
    self.assert_equals(HTML_VIDEO_ACTIVITY_V2_FULL, activity)

  def test_merge_scraped_reactions(self):
    activity = copy.deepcopy(HTML_PHOTO_ACTIVITY)
    got = self.instagram.merge_scraped_reactions(
      json_dumps(HTML_PHOTO_LIKES_RESPONSE), activity)
    self.assert_equals(LIKE_OBJS, got)
    self.assert_equals(HTML_PHOTO_ACTIVITY_LIKES, activity)

  def test_scraped_to_actor(self):
    self.assert_equals(HTML_VIEWER_PUBLIC,
                       self.instagram.scraped_to_actor(HTML_PROFILE_COMPLETE))
    self.assertIsNone(self.instagram.scraped_to_actor(HTML_VIDEO_COMPLETE))

  def test_id_to_shortcode(self):
    for shortcode, id in (
        (None, None),
        (None, ''),
        ('BDJ7Nr5Nxpa', 1209758400153852506),
        ('BDJ7Nr5Nxpa', '1209758400153852506'),
        ('BDJ7Nr5Nxpa', '1209758400153852506_1103525'),
        ('BDJ7Nr5Nxpa', 'BDJ7Nr5Nxpa'),
        ('BDJ7N_5Nxpa', 'BDJ7N_5Nxpa'),
    ):
      self.assertEqual(shortcode, self.instagram.id_to_shortcode(id))
