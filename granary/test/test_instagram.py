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

from granary import instagram
from granary import source
from granary import testutil
from oauth_dropins.webutil import util


def tag_uri(name):
  return util.tag_uri('instagram.com', name)


# Test data.
# The Instagram API returns objects with attributes, not JSON dicts.
USER = {  # Instagram
  'username': 'snarfed',
  'bio': 'foo',
  'website': 'http://snarfed.org/',
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
  'url': 'http://snarfed.org/',
  'displayName': 'Ryan B',
  'image': {'url': 'http://picture/ryan'},
  'description': 'foo',
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
  'link': 'http://instagram.com/p/ABC123/',
  'user_has_liked': False,
  'attribution': None,
  'location': {
    'id': '520640',
    'name': 'Le Truc',
    'street_address': '123 Main St.',
    'point': {'latitude':37.3, 'longitude':-122.5},
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
    'text': 'this picture -> is #abc #xyz',
    'user': {},
    'id': '285812769105340251'
  },
}
VIDEO = {
  'type': 'video',
  'id': '123_456',
  'link': 'http://instagram.com/p/ABC123/',
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
COMMENT_OBJS = [  # ActivityStreams
  {
    'objectType': 'comment',
    'author': {
      'objectType': 'person',
      'id': tag_uri('232927278'),
      'username': 'averygood',
      'displayName': '\u5c0f\u6b63',
      'image': {'url': 'http://picture/commenter'},
      'url': 'http://instagram.com/averygood',
      },
    'content': '\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
    'id': tag_uri('789'),
    'published': '2012-10-07T05:45:57',
    'url': 'http://instagram.com/p/ABC123/#comment-789',
    'inReplyTo': [{'id': tag_uri('123_456')}],
    'to': [{'objectType':'group', 'alias':'@public'}],
    },
]
POST_OBJ = {  # ActivityStreams
  'objectType': 'photo',
  'author': ACTOR,
  'content': 'this picture -&gt; is #abc #xyz',
  'id': tag_uri('123_456'),
  'published': '2012-09-22T05:25:42',
  'url': 'http://instagram.com/p/ABC123/',
  'image': {'url': 'http://attach/image/big'},
  'to': [{'objectType':'group', 'alias':'@public'}],
  'location': {
    'id': '520640',
    'displayName': 'Le Truc',
    'latitude': 37.3,
    'longitude': -122.5,
    'position': '+37.300000-122.500000/',
    'address': {'formatted': '123 Main St.'},
    },
  'attachments': [{
      'objectType': 'image',
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
      'url': 'http://snarfed.org/',
      'displayName': 'Ryan B',
      'image': {'url': 'http://picture/ryan'},
      'description': 'foo',
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
      }],
  }
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-09-22T05:25:42',
  'id': tag_uri('123_456'),
  'url': 'http://instagram.com/p/ABC123/',
  'actor': ACTOR,
  'object': POST_OBJ,
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
    'url': 'http://instagram.com/p/ABC123/#liked-by-8',
    'objectType': 'activity',
    'verb': 'like',
    'object': { 'url': 'http://instagram.com/p/ABC123/'},
    'author': {
      'objectType': 'person',
      'id': tag_uri('8'),
      'displayName': 'Alice',
      'username': 'alizz',
      'url': 'http://instagram.com/alizz',
      'image': {'url': 'http://alice/picture'},
      },
    }, {
    'id': tag_uri('123_456_liked_by_9'),
    'url': 'http://instagram.com/p/ABC123/#liked-by-9',
    'objectType': 'activity',
    'verb': 'like',
    'object': { 'url': 'http://instagram.com/p/ABC123/'},
    'author': {
      'objectType': 'person',
      'id': tag_uri('9'),
      'displayName': 'Bob',
      'username': 'bobbb',
      'url': 'http://bob.com/',
      'image': {'url': 'http://bob/picture'},
      },
    },
  ]
POST_OBJ_WITH_LIKES = copy.deepcopy(POST_OBJ)
POST_OBJ_WITH_LIKES['tags'] += LIKE_OBJS
ACTIVITY_WITH_LIKES = copy.deepcopy(ACTIVITY)
ACTIVITY_WITH_LIKES['object'] = POST_OBJ_WITH_LIKES
VIDEO_OBJ = {
  'attachments': [{
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
  'url': 'http://instagram.com/p/ABC123/',
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
  'url': 'http://instagram.com/p/ABC123/',
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
      >
<generator uri="https://github.com/snarfed/granary" version="0.1">
  granary</generator>
<id>%(host_url)s</id>
<title>User feed for Ryan B</title>

<subtitle>foo</subtitle>

<logo>http://picture/ryan</logo>
<updated>2012-09-22T05:25:42</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://snarfed.org/</uri>
 <name>Ryan B</name>
</author>

<link href="http://snarfed.org/" rel="alternate" type="text/html" />
<link rel="avatar" href="http://picture/ryan" />
<link href="%(request_url)s" rel="self" type="application/atom+xml" />
<!-- TODO -->
<!-- <link href="" rel="hub" /> -->
<!-- <link href="" rel="salmon" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-replies" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-mention" /> -->

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://snarfed.org/</uri>
 <name>Ryan B</name>
</author>

  <activity:object-type>
    http://activitystrea.ms/schema/1.0/photo
  </activity:object-type>
  <id>http://instagram.com/p/ABC123/</id>
  <title>this picture -&gt; is #abc #xyz</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

this picture -&gt; is #abc #xyz
<p>
<a class="link" href="http://instagram.com/p/ABC123/">
<img class="thumbnail" src="http://attach/image/big" alt="" />
</a>
</p>
<div class="h-card p-location">
  <div class="p-name">Le Truc</div>

</div>

<a class="tag" href="http://snarfed.org/">Ryan B</a>
  </div>
  </content>

  <link rel="alternate" type="text/html" href="http://instagram.com/p/ABC123/" />
  <link rel="ostatus:conversation" href="http://instagram.com/p/ABC123/" />

    <link rel="ostatus:attention" href="http://snarfed.org/" />
    <link rel="mentioned" href="http://snarfed.org/" />

    <link rel="ostatus:attention" href="" />
    <link rel="mentioned" href="" />

    <link rel="ostatus:attention" href="" />
    <link rel="mentioned" href="" />

  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-09-22T05:25:42</published>
  <updated></updated>

  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->

  <georss:point>37.3 -122.5</georss:point>

  <georss:featureName>Le Truc</georss:featureName>

  <link rel="self" type="application/atom+xml" href="http://instagram.com/p/ABC123/" />
</entry>

</feed>
"""


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

  def test_get_activities_activity_id(self):
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
      group_id=source.SEARCH, search_query='indieweb'))

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

  def test_media_to_activity(self):
    self.assert_equals(ACTIVITY, self.instagram.media_to_activity(MEDIA))

  def test_media_to_object(self):
    obj = self.instagram.media_to_object(MEDIA)
    self.assert_equals(POST_OBJ, obj)

    # check that the images are ordered the way we expect, largest to smallest
    self.assertEquals(POST_OBJ['attachments'][0]['image'],
                      obj['attachments'][0]['image'])

  def test_media_to_object_with_likes(self):
    self.assert_equals(POST_OBJ_WITH_LIKES,
                       self.instagram.media_to_object(MEDIA_WITH_LIKES))

  def test_comment_to_object(self):
    for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
      self.assert_equals(obj, self.instagram.comment_to_object(
          cmt, '123_456', 'http://instagram.com/p/ABC123/'))

  def test_user_to_actor(self):
    self.assert_equals(ACTOR, self.instagram.user_to_actor(USER))

  def test_user_to_actor_url_fallback(self):
    user = copy.deepcopy(USER)
    del user['website']
    actor = copy.deepcopy(ACTOR)
    actor['url'] = 'http://instagram.com/snarfed'
    self.assert_equals(actor, self.instagram.user_to_actor(user))

  def test_user_to_actor_displayName_fallback(self):
    self.assert_equals({
      'objectType': 'person',
      'id': tag_uri('420973239'),
      'username': 'snarfed',
      'displayName': 'snarfed',
      'url': 'http://instagram.com/snarfed',
    }, self.instagram.user_to_actor({
      'id': '420973239',
      'username': 'snarfed',
    }))

  def test_user_to_actor_minimal(self):
    self.assert_equals({'id': tag_uri('420973239'), 'username': None},
                       self.instagram.user_to_actor({'id': '420973239'}))
    self.assert_equals({'id': tag_uri('snarfed'), 'username': 'snarfed'},
                       self.instagram.user_to_actor({'username': 'snarfed'}))

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
    del to_publish['url']

    self.mox.ReplayAll()
    preview = instagram.Instagram(
      allow_comment_creation=True).preview_create(to_publish)

    self.assertIn('comment', preview.description)
    self.assertIn('this post', preview.description)
    self.assertIn('very cute', preview.content)

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
      'url': 'http://instagram.com/p/zHA5BLo1Mo/',
      }, self.instagram.base_object({
        'id': tag_uri('123_456_liked_by_789'),
        'object': {'url': 'http://instagram.com/p/zHA5BLo1Mo/'},
      }))

    # with only URL, we don't know id
    self.assertEquals(
      {'url': 'http://instagram.com/p/zHA5BLo1Mo/'},
      self.instagram.base_object({
        'object': {'url': 'http://instagram.com/p/zHA5BLo1Mo/'},
      }))
