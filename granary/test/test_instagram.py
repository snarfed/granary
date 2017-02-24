"""Unit tests for instagram.py.
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import copy
import datetime
import json
import logging
import mox
import StringIO
import urllib
import urllib2
import httplib2

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
import requests

from granary import instagram
from granary import source


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
  'url': 'http://snarfed.org',
  'urls': [{'value': 'http://snarfed.org'},
           {'value': 'https://asdf.com'}],
  'displayName': 'Ryan B',
  'image': {'url': 'http://picture/ryan'},
  'description': 'foo https://asdf.com bar',
}
COMMENTS = [{  # Instagram
  'created_time': '1349588757',
  'text': '\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
  'from': {
    'username': 'averygood',
    'profile_picture': 'http://picture/commenter',
    'id': '232927278',
    'full_name': '\u5c0f\u6b63',
  },
  'id': '789',
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
    'displayName': '\u5c0f\u6b63',
    'image': {'url': 'http://picture/commenter'},
    'url': 'https://www.instagram.com/averygood/',
  },
  'content': '\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
  'id': tag_uri('789'),
  'published': '2012-10-07T05:45:57',
  'url': 'https://www.instagram.com/p/ABC123/#comment-789',
  'inReplyTo': [{'id': tag_uri('123_456')}],
  'to': [{'objectType':'group', 'alias':'@public'}],
}]
MEDIA_OBJ = {  # ActivityStreams
  'objectType': 'photo',
  'author': ACTOR,
  'content': 'this picture -&gt; is #abc @foo #xyz',
  'id': tag_uri('123_456'),
  'published': '2012-09-22T05:25:42',
  'url': 'https://www.instagram.com/p/ABC123/',
  'image': {'url': 'http://attach/image/big'},
  'to': [{'objectType':'group', 'alias':'@public'}],
  'location': {
    'id': '520640',
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
    'url': 'http://snarfed.org',
    'urls': [{'value': 'http://snarfed.org'},
             {'value': 'https://asdf.com'}],
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
  'published': '2012-09-22T05:25:42',
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
      'url': 'http://bob.com',
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
    'url': 'http://distilleryvesper9-13.ak.instagram.com/090d06dad9cd11e2aa0912313817975d_101.mp4'
  },
  'image': {
    'url': 'http://distilleryimage2.ak.instagram.com/11f75f1cd9cc11e2a0fd22000aa8039a_7.jpg'
  },
  'author': ACTOR,
  'url': 'https://www.instagram.com/p/ABC123/',
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
  },
  'to': [{'alias': '@public', 'objectType': 'group'}],
  'published': '2010-07-17T04:29:43',
  'id': 'tag:instagram.com:123_456',
  'objectType': 'video'
}
VIDEO_ACTIVITY = {
  'url': 'https://www.instagram.com/p/ABC123/',
  'object': VIDEO_OBJ,
  'actor': ACTOR,
  'verb': 'post',
  'published': '2010-07-17T04:29:43',
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
<generator uri="https://github.com/snarfed/granary">granary</generator>
<id>%(host_url)s</id>
<title>User feed for Ryan B</title>

<subtitle>foo https://asdf.com bar</subtitle>

<logo>http://picture/ryan</logo>
<updated>2012-09-22T05:25:42</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://snarfed.org</uri>
 <name>Ryan B</name>
</author>

<link rel="alternate" href="http://snarfed.org" type="text/html" />
<link rel="avatar" href="http://picture/ryan" />
<link rel="self" href="%(request_url)s" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://snarfed.org</uri>
 <name>Ryan B</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/photo</activity:object-type>

  <id>https://www.instagram.com/p/ABC123/</id>
  <title>this picture -&gt; is #abc @foo #xyz</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

this picture -&gt; is #abc <a href="https://www.instagram.com/foo/">@foo</a> #xyz
<p>
<a class="link" href="https://www.instagram.com/p/ABC123/">
<img class="thumbnail" src="http://attach/image/big" alt="" />
</a>
</p>
<span class="p-location h-card">
  <a class="p-name u-url" href="https://instagram.com/explore/locations/520640/">Le Truc</a>

</span>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="https://www.instagram.com/p/ABC123/" />
  <link rel="ostatus:conversation" href="https://www.instagram.com/p/ABC123/" />

    <link rel="ostatus:attention" href="http://snarfed.org" />
    <link rel="mentioned" href="http://snarfed.org" />

    <a href="http://snarfed.org">Ryan B</a>

  <link rel="ostatus:attention" href="https://www.instagram.com/foo/" />
  <link rel="mentioned" href="https://www.instagram.com/foo/" />

  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-09-22T05:25:42</published>
  <updated>2012-09-22T05:25:42</updated>

  <georss:point>37.3 -122.5</georss:point>

  <georss:featureName>Le Truc</georss:featureName>

  <link rel="self" type="application/atom+xml" href="https://www.instagram.com/p/ABC123/" />

</entry>

</feed>
"""

# HTML objects from https://www.instagram.com/...
# https://github.com/snarfed/granary/issues/65
# https://github.com/snarfed/bridgy/issues/603
HTML_PHOTO_FULL = {
  'id': '123',
  'code': 'ABC123',
  'location': {
    'name': 'RCA Studio B',
    'id': '345924646',
    'has_public_page': True
  },
  'display_src': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-xfp1\/t51.2885-15\/e35\/12545499_1662965520652470_1466520818_n.jpg',
  'is_video': False,
  'owner': {
    'is_private': False,
    'id': '456',
    'has_blocked_viewer': False,
    'full_name': 'Jerry C',
    'profile_pic_url': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-frc\/t51.2885-19\/10903606_836522793073208_584898992_a.jpg',
    'blocked_by_viewer': False,
    'followed_by_viewer': True,
    'requested_by_viewer': False,
    'username': 'jc',
  },
  'likes': {
    'nodes': [{
      'user': {
        'id': '8',
        'profile_pic_url': 'http:\/\/alice\/picture',
        'username': 'alizz',
        'full_name': 'Alice',
      }
    }, {
      'user': {
        'id': '9',
        'profile_pic_url': 'http:\/\/bob\/picture',
        'username': 'bobbb',
        'full_name': 'Bob',
        'website': 'http://bob.com/',
      }
    }],
    'viewer_has_liked': False,
    'count': 5,
  },
  'caption': 'Elvis hits out of RCA Studio B',
  'comments': {
    'nodes': [],
    'page_info': {
      'has_next_page': False,
      'end_cursor': None,
      'start_cursor': None,
      'has_previous_page': False
    },
    'count': 0,
  },
  'dimensions': {'width': 1080, 'height': 1293},
  'date': 1453063593.0,
}
HTML_VIDEO_FULL = {
  'id': '789',
  'code': 'XYZ789',
  'location': None,
  'display_src': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-xpf1\/t51.2885-15\/s750x750\/sh0.08\/e35\/12424348_567037233461060_1986731502_n.jpg',
  'is_video': True,
  'video_url': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-xtp1\/t50.2886-16\/12604073_746855092124622_46574942_n.mp4',
  'dimensions': {'height': 640, 'width': 640},
  'owner': {
    'is_private': True,
    'id': '456',
    'full_name': 'Jerry C',
    'profile_pic_url': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-frc\/t51.2885-19\/10903606_836522793073208_584898992_a.jpg',
    'username': 'jc',
  },
  'likes': {
    'nodes': [],
    'count': 9,
  },
  'caption': 'Eye of deer \ud83d\udc41 and #selfie from me',
  'comments': {
    'nodes': [{
      'user': {
        'id': '232927278',
        'profile_pic_url': 'http:\/\/picture\/commenter',
        'username': 'averygood',
        'full_name': '\u5c0f\u6b63',
      },
      'id': '789',
      'created_at': 1349588757,
      'text': '\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
    }],
    'count': 1,
  },
  'usertags': {
    'nodes': [{
      'user': {'username': 'ap'},
      'position': {'x': 0.4657777507, 'y': 0.4284444173},
    }],
  },
  'date': 1453036552.0,
}

HTML_VIDEO = copy.deepcopy(HTML_VIDEO_FULL)
del HTML_VIDEO['likes']['nodes']
del HTML_VIDEO['comments']['nodes']

HTML_PHOTO = copy.deepcopy(HTML_PHOTO_FULL)
del HTML_PHOTO['likes']['nodes']
del HTML_PHOTO['comments']['nodes']

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
        'shortcode': 'BQ0ly_FAyWA',
        'dimensions': {'height': 1080, 'width': 1080},
        'display_url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t51.2885-15/s1080x1080/e35/16906679_776417269184045_871950675452362752_n.jpg',
        'is_video': False,
        'edge_media_to_tagged_user': {'edges': []},
      },
    }],
  },
})

HTML_FEED = {  # eg https://www.instagram.com/ when you're logged in
  'environment_switcher_visible_server_guess': True,
  'config': {
    'csrf_token': '...',
    'viewer': {
      'external_url': 'https:\/\/snarfed.org',
      'biography': 'something or other',
      'id': '420973239',
      'full_name': 'Ryan B',
      'profile_pic_url': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-xfa1\/t51.2885-19\/11373714_959073410822287_2004790583_a.jpg',
      'has_profile_pic': True,
      'username': 'snarfed',
    }
  },
  'display_properties_server_guess': {'pixel_ratio': 2.0, 'viewport_width': 1280},
  'qe': {'su': {'g': 'control', 'p': {'enabled': 'false'}}},
  'hostname': 'www.instagram.com',
  'platform': 'web',
  'static_root': '\/\/instagramstatic-a.akamaihd.net\/bluebar\/cf5f70d',
  'gatekeepers': {'sfbf': True, 'addpp': True, 'rhp': True, 'cpp': True},
  'language_code': 'en',
  'country_code': 'US',
  'entry_data': {'FeedPage': [{
    '__path': '\/',
    'suggestedUsersList': None,
    '__get_params': None,
    '__query_string': '?',
    'feed': {'media': {
      'nodes': [
        HTML_PHOTO_FULL,
        HTML_VIDEO_FULL,
      ],
      'page_info': {
        'has_next_page': True,
        'end_cursor': '1163980147673702805',
        'start_cursor': '1164745675899097546',
        'has_previous_page': False
      },
    }},
}]}}

HTML_PROFILE = {  # eg https://www.instagram.com/snarfed
  'config': {
    'csrf_token': '6a5737e3f1a23873f98d96e12974e2d5',
    'viewer': None,
  },
  '...': '...',  # many of the same top-level fields as in HTML_FEED
  'entry_data': {'ProfilePage': [{'user': {
    'external_url': 'http:\/\/snarfed.org',
    'is_private': False,
    'has_blocked_viewer': False,
    'is_verified': False,
    'blocked_by_viewer': False,
    'media': {
      'nodes': [
        HTML_PHOTO,
        HTML_VIDEO,
      ],
      'page_info': {
        'has_next_page': True,
        'end_cursor': '1151679169740247288',
        'start_cursor': '1178482373937173104',
        'has_previous_page': False,
      },
      'count': 471,
    },
    'full_name': 'Ryan B',
    'biography': 'something or other',
    'id': '420973239',
    'profile_pic_url': 'https:\/\/scontent-sjc2-1.cdninstagram.com\/hphotos-xfa1\/t51.2885-19\/11373714_959073410822287_2004790583_a.jpg',
    'follows_viewer': False,
    'followed_by_viewer': False,
    'has_requested_viewer': False,
    'country_block': None,
    'followed_by': {'count': 458},
    'requested_by_viewer': False,
    'follows': {'count': 295},
    'username': 'snarfed',
    'external_url': 'https:\/\/snarfed.org',
  }}]},
}
HTML_PROFILE_PRIVATE = copy.deepcopy(HTML_PROFILE)
HTML_PROFILE_PRIVATE['entry_data']['ProfilePage'][0]['user']['is_private'] = True

HTML_PHOTO_PAGE = {  # eg https://www.instagram.com/p/ABC123/
  'config': {
    'csrf_token': 'xyz',
    'viewer': None,
  },
  '...': '...',  # many of the same top-level fields as in HTML_FEED and HTML_PROFILE
  'entry_data': {'PostPage': [{'media': HTML_PHOTO_FULL}]},
}

HTML_VIDEO_PAGE = {  # eg https://www.instagram.com/p/ABC123/
  'config': {
    'csrf_token': 'xyz',
    'viewer': None,
  },
  '...': '...',
  'entry_data': {'PostPage': [{'media': HTML_VIDEO_FULL}]},
}

HTML_MULTI_PHOTO_PAGE = {  # eg https://www.instagram.com/p/BQ0mDB2gV_O/
  'config': {
    'csrf_token': 'xyz',
    'viewer': None,
  },
  'entry_data': {'PostPage': [{'media': HTML_MULTI_PHOTO}]},
}


HTML_HEADER = """
<!DOCTYPE html>
...
<link href="https://www.instagram.com/" rel="alternate" hreflang="x-default" />
...
<body>
<script type="text/javascript">window._sharedData = """
HTML_FOOTER = """
;</script>
<script src="//instagramstatic-a.akamaihd.net/h1/bundles/en_US_Commons.js/907dcce6a88a.js" type="text/javascript"></script>
<script src="//instagramstatic-a.akamaihd.net/h1/bundles/en_US_FeedPage.js/d0ffd22d18b5.js" type="text/javascript"></script>
...
</body>
</html>
"""

HTML_VIEWER = {
  'displayName': 'Ryan B',
  'id': tag_uri('420973239'),
  'image': {'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfa1/t51.2885-19/11373714_959073410822287_2004790583_a.jpg'},
  'objectType': 'person',
  'url': 'https://snarfed.org',
  'username': 'snarfed',
  'description': 'something or other',
}
HTML_ACTOR = {
  'displayName': 'Jerry C',
  'id': tag_uri('456'),
  'image': {'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-frc/t51.2885-19/10903606_836522793073208_584898992_a.jpg'},
  'objectType': 'person',
  'url': 'https://www.instagram.com/jc/',
  'username': 'jc',
}
HTML_PHOTO_ACTIVITY = {  # ActivityStreams
  # Photo
  'verb': 'post',
  'published': '2016-01-17T20:46:33',
  'id': tag_uri('123_456'),
  'url': 'https://www.instagram.com/p/ABC123/',
  'actor': HTML_ACTOR,
  'object': {
    'objectType': 'photo',
    'author': HTML_ACTOR,
    'content': 'Elvis hits out of RCA Studio B',
    'id': tag_uri('123_456'),
    'published': '2016-01-17T20:46:33',
    'url': 'https://www.instagram.com/p/ABC123/',
    'image': {'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xfp1/t51.2885-15/e35/12545499_1662965520652470_1466520818_n.jpg'},
    'to': [{'objectType':'group', 'alias':'@public'}],
    'location': {
      'id': '345924646',
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
HTML_PHOTO_ACTIVITY_FULL['object']['tags'] = LIKE_OBJS

HTML_VIDEO_ACTIVITY = {  # ActivityStreams
  # Video
  'verb': 'post',
  'published': '2016-01-17T13:15:52',
  'id': tag_uri('789_456'),
  'url': 'https://www.instagram.com/p/XYZ789/',
  'actor': HTML_ACTOR,
  'object': {
    'objectType': 'video',
    'author': HTML_ACTOR,
    'content': 'Eye of deer \ud83d\udc41 and #selfie from me',
    'id': tag_uri('789_456'),
    'published': '2016-01-17T13:15:52',
    'url': 'https://www.instagram.com/p/XYZ789/',
    'image': {'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xpf1/t51.2885-15/s750x750/sh0.08/e35/12424348_567037233461060_1986731502_n.jpg'},
    'to': [{'objectType':'group', 'alias':'@private'}],
    'replies': {'totalItems': 1},
    'ig_like_count': 9,
    'stream': {
      'url': 'https://scontent-sjc2-1.cdninstagram.com/hphotos-xtp1/t50.2886-16/12604073_746855092124622_46574942_n.mp4',
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
    }],
  },
}
HTML_VIDEO_ACTIVITY_FULL = copy.deepcopy(HTML_VIDEO_ACTIVITY)
HTML_VIDEO_ACTIVITY_FULL['object']['replies'] = {
  'items': copy.deepcopy(COMMENT_OBJS),
  'totalItems': len(COMMENT_OBJS),
}
HTML_VIDEO_ACTIVITY_FULL['object']['replies']['items'][0].update({
  'url': 'https://www.instagram.com/p/XYZ789/#comment-789',
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
  'url': 'https://www.instagram.com/p/BQ0ly_FAyWA/',
  'image': [{
    'url': 'https://instagram.fsnc1-2.fna.fbcdn.net/t51.2885-15/s1080x1080/e35/16906679_776417269184045_871950675452362752_n.jpg',
    'width': 1080,
    'height': 1080,
  }],
}]

HTML_ACTIVITIES = [HTML_PHOTO_ACTIVITY, HTML_VIDEO_ACTIVITY]
HTML_ACTIVITIES_FULL = [HTML_PHOTO_ACTIVITY_FULL, HTML_VIDEO_ACTIVITY_FULL]

HTML_FEED_COMPLETE = HTML_HEADER + json.dumps(HTML_FEED) + HTML_FOOTER
HTML_PROFILE_COMPLETE = HTML_HEADER + json.dumps(HTML_PROFILE) + HTML_FOOTER
HTML_PROFILE_PRIVATE_COMPLETE = HTML_HEADER + json.dumps(HTML_PROFILE_PRIVATE) + HTML_FOOTER
HTML_PHOTO_COMPLETE = HTML_HEADER + json.dumps(HTML_PHOTO_PAGE) + HTML_FOOTER
HTML_VIDEO_COMPLETE = HTML_HEADER + json.dumps(HTML_VIDEO_PAGE) + HTML_FOOTER
HTML_MULTI_PHOTO_COMPLETE = HTML_HEADER + json.dumps(HTML_MULTI_PHOTO_PAGE) + HTML_FOOTER
HTML_PHOTO_MISSING_HEADER = json.dumps(HTML_PHOTO_PAGE) + HTML_FOOTER
HTML_PHOTO_MISSING_FOOTER = HTML_HEADER + json.dumps(HTML_PHOTO_PAGE)


class InstagramTest(testutil.HandlerTest):

  def setUp(self):
    super(InstagramTest, self).setUp()
    self.instagram = instagram.Instagram()

  def test_get_actor(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/foo',
                        json.dumps({'data': USER}))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.instagram.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self',
                        json.dumps({'data': USER}))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.instagram.get_actor())

  def test_get_actor_scrape(self):
    self.expect_requests_get(instagram.HTML_BASE_URL + 'foo/',
                             HTML_PROFILE_COMPLETE, allow_redirects=False)
    self.mox.ReplayAll()
    self.assert_equals(HTML_VIEWER, instagram.Instagram(scrape=True).get_actor('foo'))

  def test_get_activities_self(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self/media/recent',
                        json.dumps({'data': []}))
    self.mox.ReplayAll()
    self.assert_equals([], self.instagram.get_activities(group_id=source.SELF))

  def test_get_activities_self_fetch_likes(self):
    self.expect_urlopen('https://api.instagram.com/v1/users/self/media/recent',
                        json.dumps({'data': [MEDIA]}))
    self.expect_urlopen('https://api.instagram.com/v1/users/self/media/liked',
                        json.dumps({'data': [MEDIA_WITH_LIKES]}))
    self.expect_urlopen('https://api.instagram.com/v1/users/self',
                        json.dumps({'data': LIKES[0]}))
    self.mox.ReplayAll()
    self.assert_equals(
      [ACTIVITY] + [LIKE_OBJS[0]],
      self.instagram.get_activities(group_id=source.SELF, fetch_likes=True))

  def test_get_activities_passes_through_access_token(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/users/self/feed?access_token=asdf',
      json.dumps({'meta': {'code': 200}, 'data': []}))
    self.mox.ReplayAll()

    self.instagram = instagram.Instagram(access_token='asdf')
    self.instagram.get_activities()

  def test_get_activities_activity_id_shortcode(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        json.dumps({'data': MEDIA}))
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
                        json.dumps({'data': [MEDIA_WITH_LIKES]}))
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY_WITH_LIKES], self.instagram.get_activities())

  def test_get_activities_other_400_error(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        'BAD REQUEST', status=400)
    self.mox.ReplayAll()
    self.assertRaises(urllib2.HTTPError, self.instagram.get_activities,
                      activity_id='000')

  def test_get_activities_min_id(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/users/self/media/recent?min_id=135',
      json.dumps({'data': []}))
    self.mox.ReplayAll()
    self.instagram.get_activities(group_id=source.SELF, min_id='135')

  def test_get_activities_search(self):
    self.expect_urlopen('https://api.instagram.com/v1/tags/indieweb/media/recent',
                        json.dumps({'data': [MEDIA]}))
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY], self.instagram.get_activities(
      group_id=source.SEARCH, search_query='#indieweb'))

  def test_get_activities_search_non_hashtag(self):
    with self.assertRaises(ValueError):
      self.instagram.get_activities(search_query='foo')

  def test_get_activities_scrape_self(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'x/', HTML_PROFILE_COMPLETE +
        # check that we ignore this for profile fetches
        ' not-logged-in ',
      allow_redirects=False)
    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTIVITIES, self.instagram.get_activities(
      user_id='x', group_id=source.SELF, scrape=True))

  def test_get_activities_response_scrape_self_viewer(self):
    self.expect_requests_get(instagram.HTML_BASE_URL + 'x/',
                             HTML_PROFILE_COMPLETE, allow_redirects=False)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      user_id='x', group_id=source.SELF, scrape=True)
    self.assert_equals(HTML_ACTIVITIES, resp['items'])
    self.assert_equals(HTML_VIEWER, resp['actor'])

  def test_get_activities_scrape_self_fetch_extras(self):
    self.expect_requests_get(instagram.HTML_BASE_URL + 'x/',
                             HTML_PROFILE_COMPLETE, allow_redirects=False)
    self.expect_requests_get(instagram.HTML_BASE_URL + 'p/ABC123/',
                             HTML_PHOTO_COMPLETE)
    self.expect_requests_get(instagram.HTML_BASE_URL + 'p/XYZ789/',
                             HTML_VIDEO_COMPLETE)

    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTIVITIES_FULL, self.instagram.get_activities(
      user_id='x', group_id=source.SELF, fetch_likes=True, fetch_replies=True,
      scrape=True))

  def test_get_activities_scrape_fetch_extras_cache(self):
    # first time, cache is cold
    self.expect_requests_get(instagram.HTML_BASE_URL + 'x/',
                             HTML_PROFILE_COMPLETE, allow_redirects=False)
    self.expect_requests_get(instagram.HTML_BASE_URL + 'p/ABC123/',
                             HTML_PHOTO_COMPLETE)
    self.expect_requests_get(instagram.HTML_BASE_URL + 'p/XYZ789/',
                             HTML_VIDEO_COMPLETE)

    # second time, comment and like counts are unchanged, so no media page fetches
    self.expect_requests_get(instagram.HTML_BASE_URL + 'x/',
                             HTML_PROFILE_COMPLETE, allow_redirects=False)

    # third time, video comment count changes, like counts stay the same
    profile = copy.deepcopy(HTML_PROFILE)
    profile['entry_data']['ProfilePage'][0]['user']['media']['nodes'][1]\
      ['comments']['count'] = 3
    self.expect_requests_get(instagram.HTML_BASE_URL + 'x/',
                             HTML_HEADER + json.dumps(profile) + HTML_FOOTER,
                             allow_redirects=False)
    video = copy.deepcopy(HTML_VIDEO_FULL)
    video['comments']['count'] = 4
    self.expect_requests_get(instagram.HTML_BASE_URL + 'p/XYZ789/',
                             HTML_HEADER + json.dumps(video) + HTML_FOOTER)

    self.mox.ReplayAll()

    cache = util.CacheDict()
    for i in range(3):
      self.instagram.get_activities(user_id='x', group_id=source.SELF,
                                    fetch_likes=True, fetch_replies=True,
                                    scrape=True, cache=cache)

    self.assert_equals({
      'AIC 123_456': 0,  # photo
      'AIL 123_456': 5,
      'AIC 789_456': 1,  # video
      'AIL 789_456': 9,
    }, cache)

  def test_get_activities_scrape_missing_data(self):
    self.expect_requests_get(instagram.HTML_BASE_URL + 'x/', """
<!DOCTYPE html>
<html><body>
</body></html>
""", allow_redirects=False)
    self.mox.ReplayAll()
    self.assert_equals([], self.instagram.get_activities(
      user_id='x', group_id=source.SELF, scrape=True))

  def test_get_activities_scrape_friends_cookie(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL, HTML_FEED_COMPLETE, allow_redirects=False,
      headers={'Cookie': 'my cookie'})
    self.mox.ReplayAll()
    self.assert_equals(HTML_ACTIVITIES_FULL, self.instagram.get_activities(
      group_id=source.FRIENDS, scrape=True, cookie='my cookie'))

  def test_get_activities_response_scrape_friends_viewer(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL, HTML_FEED_COMPLETE, allow_redirects=False,
      headers={'Cookie': 'my cookie'})
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.FRIENDS, scrape=True, cookie='my cookie')
    self.assert_equals(HTML_ACTIVITIES_FULL, resp['items'])
    self.assert_equals(HTML_VIEWER, resp['actor'])

  def test_get_activities_scrape_cookie_not_logged_in(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL, '<html>not-logged-in</html>',
      allow_redirects=False, headers={'Cookie': 'my cookie'})
    self.mox.ReplayAll()

    with self.assertRaises(requests.HTTPError) as cm:
      self.instagram.get_activities(group_id=source.FRIENDS, scrape=True,
                                    cookie='my cookie')

    self.assertEquals('401 Unauthorized', cm.exception.message)
    self.assertEquals(401, cm.exception.response.status_code)

  def test_get_activities_scrape_activity_id(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'p/BDG6Ms_J0vQ/', HTML_PHOTO_COMPLETE,
      allow_redirects=False)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, scrape=True, activity_id='1208909509631101904_942513')
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], resp['items'])
    self.assertIsNone(resp['actor'])

  def test_get_activities_scrape_activity_id_shortcode(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'p/BDG6Ms_J0vQ/', HTML_PHOTO_COMPLETE,
      allow_redirects=False)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, scrape=True, activity_id='BDG6Ms_J0vQ')
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], resp['items'])

  def test_get_activities_scrape_activity_id_shortcode_404(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'p/B7/', status_code=404,
      allow_redirects=False)
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'p/123_ABC/', HTML_PHOTO_COMPLETE,
      allow_redirects=False)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, scrape=True, activity_id='123_ABC')
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], resp['items'])

  def test_get_activities_scrape_cookie_redirects_to_login(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL,
      allow_redirects=False,
      headers={'Cookie': 'my cookie'},
      status_code=302,
      redirected_url='https://www.instagram.com/accounts/login/?next=/')
    self.mox.ReplayAll()

    with self.assertRaises(requests.HTTPError) as cm:
      self.instagram.get_activities(group_id=source.FRIENDS, scrape=True,
                                    cookie='my cookie')

    self.assertEquals('401 Unauthorized', cm.exception.message)
    self.assertEquals(401, cm.exception.response.status_code)

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
    self.expect_requests_get(instagram.HTML_BASE_URL + 'foo/',
                             allow_redirects=False, status_code=404)
    self.mox.ReplayAll()

    resp = self.instagram.get_activities_response(
      group_id=source.SELF, user_id='foo', scrape=True)
    self.assertIsNone(resp['actor'])
    self.assertEquals([], resp['items'])

  def test_get_activities_scrape_error(self):
    self.expect_requests_get(instagram.HTML_BASE_URL,
                             headers={'Cookie': 'my cookie'},
                             allow_redirects=False,
                             status_code=429)
    self.mox.ReplayAll()

    with self.assertRaises(requests.HTTPError) as cm:
      a = self.instagram.get_activities(group_id=source.FRIENDS, scrape=True,
                                        cookie='my cookie')

    self.assertEquals(429, cm.exception.response.status_code)

  def test_get_video(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/5678',
                        json.dumps({'data': VIDEO}))
    self.mox.ReplayAll()
    self.assert_equals([VIDEO_ACTIVITY], self.instagram.get_activities(activity_id='5678'))

  def test_get_comment(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/123_456',
                        json.dumps({'data': MEDIA}))
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJS[0],
                       self.instagram.get_comment('789', activity_id='123_456'))

  def test_get_comment_not_found(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/123_456',
                        json.dumps({'data': MEDIA}))
    self.mox.ReplayAll()
    self.assert_equals(None, self.instagram.get_comment('111', activity_id='123_456'))

  def test_get_comment_scrape(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'p/BDG6Ms_J0vQ/', HTML_VIDEO_COMPLETE,
      allow_redirects=False)
    self.mox.ReplayAll()

    ig = instagram.Instagram(scrape=True)
    self.assert_equals(HTML_VIDEO_ACTIVITY_FULL['object']['replies']['items'][0],
                       ig.get_comment('789', activity_id='1208909509631101904_942513'))

  def test_get_comment_with_activity(self):
    # skips API call
    self.assert_equals(COMMENT_OBJS[0],
                       self.instagram.get_comment('789', activity=ACTIVITY))

  def test_get_like(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        json.dumps({'data': MEDIA_WITH_LIKES}))
    self.mox.ReplayAll()
    self.assert_equals(LIKE_OBJS[1], self.instagram.get_like('123', '000', '9'))

  def test_get_like_not_found(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        json.dumps({'data': MEDIA}))
    self.mox.ReplayAll()
    self.assert_equals(None, self.instagram.get_like('123', '000', 'xyz'))

  def test_get_like_no_activity(self):
    self.expect_urlopen('https://api.instagram.com/v1/media/000',
                        '{"meta":{"error_type":"APINotFoundError"}}',
                        status=400)
    self.mox.ReplayAll()
    self.assert_equals(None, self.instagram.get_like('123', '000', '9'))

  def test_get_like_scrape(self):
    self.expect_requests_get(
      instagram.HTML_BASE_URL + 'p/BDG6Ms_J0vQ/', HTML_PHOTO_COMPLETE,
      allow_redirects=False)
    self.mox.ReplayAll()

    ig = instagram.Instagram(scrape=True)
    self.assert_equals(LIKE_OBJS[0],
                       ig.get_like('456', '1208909509631101904_942513', '8'))

  def test_media_to_activity(self):
    self.assert_equals(ACTIVITY, self.instagram.media_to_activity(MEDIA))

  def test_media_to_object(self):
    obj = self.instagram.media_to_object(MEDIA)
    self.assert_equals(MEDIA_OBJ, obj)

    # check that the images are ordered the way we expect, largest to smallest
    self.assertEquals(MEDIA_OBJ['attachments'][0]['image'],
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
      'objectType': 'person',
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
      json.dumps({'data': MEDIA}))

    self.expect_urlopen(
      'https://api.instagram.com/v1/media/123_456/likes',
      '{"meta":{"status":200}}', data='access_token=None')

    self.expect_urlopen(
      'https://api.instagram.com/v1/users/self',
      json.dumps({'data': {
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
    self.assert_equals(source.creation_result(LIKE_OBJS[0]),
                       self.instagram.create(to_publish))

  def test_preview_comment(self):
    # comment obj doesn't have a url prior to publishing
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    to_publish['content'] = 'very<br />cute'
    del to_publish['url']

    self.mox.ReplayAll()
    preview = instagram.Instagram(
      allow_comment_creation=True).preview_create(to_publish)

    self.assertIn('comment', preview.description)
    self.assertIn('this post', preview.description)
    self.assertIn('very\ncute', preview.content)

  def test_create_comment(self):
    self.expect_urlopen(
      'https://api.instagram.com/v1/media/123_456/comments',
      '{"meta":{"status":200}}',
      data=urllib.urlencode({'access_token': self.instagram.access_token,
                             'text': COMMENTS[0]['text']}))

    self.mox.ReplayAll()
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    del to_publish['url']

    result = instagram.Instagram(allow_comment_creation=True).create(to_publish)
    # TODO instagram does not give back a comment object; not sure how to
    # get the comment id. for now, just check that creation was successful
    # self.assert_equals(source.creation_result(COMMENT_OBJS[0]),
    #                   self.instagram.create(to_publish))
    self.assertTrue(result.content)
    self.assertFalse(result.abort)

  def test_create_comment_unauthorized(self):
    # a more realistic test. this is what happens when you try to
    # create comments with the API, with an unapproved app
    self.expect_urlopen(
      'https://api.instagram.com/v1/media/123_456/comments',
      data=urllib.urlencode({'access_token': self.instagram.access_token,
                             'text': COMMENTS[0]['text']}),
      response='{"meta": {"code": 400, "error_type": u"OAuthPermissionsException", "error_message": "This request requires scope=comments, but this access token is not authorized with this scope. The user must re-authorize your application with scope=comments to be granted write permissions."}}',
      status=400)

    self.mox.ReplayAll()
    to_publish = copy.deepcopy(COMMENT_OBJS[0])
    del to_publish['url']

    self.assertRaises(urllib2.HTTPError, instagram.Instagram(
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
    self.assertEquals({
      'id': '123',
      'url': 'https://www.instagram.com/p/zHA5BLo1Mo/',
      }, self.instagram.base_object({
        'id': tag_uri('123_456_liked_by_789'),
        'object': {'url': 'https://www.instagram.com/p/zHA5BLo1Mo/'},
      }))

    # with only URL, we don't know id
    self.assertEquals(
      {'url': 'https://www.instagram.com/p/zHA5BLo1Mo/'},
      self.instagram.base_object({
        'object': {'url': 'https://www.instagram.com/p/zHA5BLo1Mo/'},
      }))

  def test_html_to_activities_feed(self):
    activities, viewer = self.instagram.html_to_activities(HTML_FEED_COMPLETE)
    self.assert_equals(HTML_ACTIVITIES_FULL, activities)
    self.assert_equals(HTML_VIEWER, viewer)

  def test_html_to_activities_profile(self):
    activities, viewer = self.instagram.html_to_activities(HTML_PROFILE_COMPLETE)
    self.assert_equals(HTML_ACTIVITIES, activities)
    self.assert_equals(HTML_VIEWER, viewer)

  def test_html_to_activities_profile_private(self):
    _, actor = self.instagram.html_to_activities(HTML_PROFILE_PRIVATE_COMPLETE)
    self.assert_equals([{'objectType':'group', 'alias':'@private'}], actor['to'])

  def test_html_to_activities_photo(self):
    activities, viewer = self.instagram.html_to_activities(HTML_PHOTO_COMPLETE)
    self.assert_equals([HTML_PHOTO_ACTIVITY_FULL], activities)
    self.assertIsNone(viewer)

  def test_html_to_activities_video(self):
    activities, viewer = self.instagram.html_to_activities(HTML_VIDEO_COMPLETE)
    self.assert_equals([HTML_VIDEO_ACTIVITY_FULL], activities)
    self.assertIsNone(viewer)

  def test_html_to_activities_multi_photo(self):
    activities, viewer = self.instagram.html_to_activities(HTML_MULTI_PHOTO_COMPLETE)
    self.assert_equals([HTML_MULTI_PHOTO_ACTIVITY], activities)
    self.assertIsNone(viewer)

  def test_html_to_activities_missing_profile_picture_external_url(self):
    data = copy.deepcopy(HTML_FEED)
    data['config']['viewer']['profile_pic_url'] = None
    data['config']['viewer']['external_url'] = None
    _, viewer = self.instagram.html_to_activities(
      HTML_HEADER + json.dumps(data) + HTML_FOOTER)

    expected = copy.deepcopy(HTML_VIEWER)
    expected['url'] = 'https://www.instagram.com/snarfed/'
    del expected['image']
    self.assert_equals(expected, viewer)

  def test_html_to_activities_missing_video_url(self):
    data = copy.deepcopy(HTML_FEED)
    del data['entry_data']['FeedPage'][0]['feed']['media']['nodes'][1]['video_url']
    activities, _ = self.instagram.html_to_activities(
      HTML_HEADER + json.dumps(data) + HTML_FOOTER)

    expected = copy.deepcopy(HTML_ACTIVITIES_FULL)
    del expected[1]['object']['stream']
    del expected[1]['object']['attachments'][0]['stream'][0]['url']
    self.assert_equals(expected, activities)

  def test_html_to_activities_missing_header(self):
    activities, viewer = self.instagram.html_to_activities(HTML_PHOTO_MISSING_HEADER)
    self.assert_equals([], activities)
    self.assertIsNone(viewer)

  def test_html_to_activities_missing_footer(self):
    activities, viewer = self.instagram.html_to_activities(HTML_PHOTO_MISSING_FOOTER)
    self.assert_equals([], activities)
    self.assertIsNone(viewer)

  def test_html_to_activities_trims_nulls(self):
    activities, viewer = self.instagram.html_to_activities(HTML_HEADER + json.dumps({
      'entry_data': {
        'FeedPage': [{
          'feed': {
            'media': {
              'nodes': None,
            }
          }
        }],
        'ProfilePage': {'user': None},
        'PostPage': None,
      },
    }) + HTML_FOOTER)
    self.assert_equals([], activities)
    self.assertIsNone(viewer)

  def test_id_to_shortcode(self):
    for shortcode, id in (
        (None, None),
        (None, ''),
        ('BDJ7Nr5Nxpa', 1209758400153852506),
        ('BDJ7Nr5Nxpa', '1209758400153852506'),
        ('BDJ7Nr5Nxpa', '1209758400153852506'),
        ('BDJ7Nr5Nxpa', '1209758400153852506_1103525'),
        ('BDJ7Nr5Nxpa', 'BDJ7Nr5Nxpa'),
        ('BDJ7N_5Nxpa', 'BDJ7N_5Nxpa'),
    ):
      self.assertEquals(shortcode, self.instagram.id_to_shortcode(id))
