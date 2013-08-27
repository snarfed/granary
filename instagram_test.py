#!/usr/bin/python
# -*- eval: (progn (make-local-variable 'before-save-hook) (remove-hook 'before-save-hook 'delete-trailing-whitespace-in-some-modes t)) -*-
#
# (the above line is an Emacs file local variable that says *not* to delete
# trailing whitespace, since some of it in test data is meaningful.)
"""Unit tests for instagram.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import json
import mox
import urllib
import urlparse
from webutil import webapp2

import instagram
import source
from webutil import testutil
from webutil import util
from webutil.util import Struct


def tag_uri(name):
  return util.tag_uri('instagram.com', name)


# Test data.
# (The Instagram API returns objects with attributes, not JSON dicts.)
USER = Struct(  # Instagram
  username='snarfed',
  bio='foo',
  website='http://snarfed.org/',
  profile_picture='http://images.ak.instagram.com/profiles/profile_420973239_75sq_1371423879.jpg',
  full_name='Ryan B',
  counts={
    'media': 2,
    'followed_by': 10,
    'follows': 33,
    },
  id='420973239',
  )
ACTOR = {  # ActivityStreams
  'displayName': 'Ryan B',
  'image': {'url': 'http://images.ak.instagram.com/profiles/profile_420973239_75sq_1371423879.jpg'},
  'id': tag_uri('snarfed'),
  'url': 'http://snarfed.org/',
  'username': 'snarfed',
  'description': 'foo',
  }
COMMENTS = [{  # Instagram
            'created_time': '1349588757',
            'text': '\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
            'from': {
              'username': 'averygood',
              'profile_picture': 'http://images.ak.instagram.com/profiles/profile_232927278_75sq_1349602693.jpg',
              'id': '232927278',
              'full_name': '\u5c0f\u6b63'
            },
            'id': '296694460841682444'
          }
        ]
POST = {  # Instagram
      'attribution': None,
      'tags': [],
      'type': 'image',
      'location': None,
      'comments': {
        'count': len(COMMENTS),
        'data': COMMENTS,
      },
      'filter': 'Normal',
      'created_time': '1348291542',
      'link': 'http://instagram.com/p/P3aRPTy2Un/',
      'likes': {
        'count': 3,
        'data': [
          {
            'username': 'kokomiwu',
            'profile_picture': 'http://images.ak.instagram.com/profiles/profile_182594824_75sq_1345890199.jpg',
            'id': '182594824',
            'full_name': 'kokomiwu'
          },
          {
            'username': 'ghooody',
            'profile_picture': 'http://images.ak.instagram.com/profiles/profile_202203276_75sq_1374997384.jpg',
            'id': '202203276',
            'full_name': 'Ghada'
          }
        ]
      },
      'images': {
        'low_resolution': {
          'url': 'http://distilleryimage7.s3.amazonaws.com/f4313bc8047511e2b1c522000a1de671_6.jpg',
          'width': 306,
          'height': 306
        },
        'thumbnail': {
          'url': 'http://distilleryimage7.s3.amazonaws.com/f4313bc8047511e2b1c522000a1de671_5.jpg',
          'width': 150,
          'height': 150
        },
        'standard_resolution': {
          'url': 'http://distilleryimage7.s3.amazonaws.com/f4313bc8047511e2b1c522000a1de671_7.jpg',
          'width': 612,
          'height': 612
        }
      },
      'users_in_photo': [],
      'caption': {
        'created_time': '1348291558',
        'text': 'sunbath',
        'from': {
          'username': 'kokomiwu',
          'profile_picture': 'http://images.ak.instagram.com/profiles/profile_182594824_75sq_1345890199.jpg',
          'id': '182594824',
          'full_name': 'kokomiwu'
        },
        'id': '285812769105340251'
      },
      'user_has_liked': False,
      'id': '285812635239933223_182594824',
      'user': {
        'username': 'kokomiwu',
        'website': '',
        'profile_picture': 'http://images.ak.instagram.com/profiles/profile_182594824_75sq_1345890199.jpg',
        'full_name': 'kokomiwu',
        'bio': '',
        'id': '182594824'
      }
    }
COMMENT_OBJS = [  # ActivityStreams
  {
    'objectType': 'comment',
    'author': {
      'id': tag_uri('212038'),
      'displayName': 'Ryan Barrett',
      'image': {'url': 'http://graph.instagram.com/212038/picture?type=large'},
      'url': 'http://instagram.com/212038',
      },
    'content': 'cc Sam G, Michael M',
    'id': tag_uri('212038_547822715231468_6796480'),
    'published': '2012-12-05T00:58:26+00:00',
    'url': 'http://instagram.com/212038/posts/547822715231468?comment_id=6796480',
    'inReplyTo': {'id': tag_uri('212038_547822715231468')},
    'tags': [{
        'objectType': 'person',
        'id': tag_uri('221330'),
        'url': 'http://instagram.com/221330',
        'displayName': 'Sam G',
        'startIndex': 3,
        'length': 5,
        }, {
        'objectType': 'person',
        'id': tag_uri('695687650'),
        'url': 'http://instagram.com/695687650',
        'displayName': 'Michael Mandel',
        'startIndex': 10,
        'length': 9,
        }],
    },
  {
    'objectType': 'comment',
    'author': {
      'id': tag_uri('513046677'),
      'displayName': 'Ron Ald',
      'image': {'url': 'http://graph.instagram.com/513046677/picture?type=large'},
      'url': 'http://instagram.com/513046677',
      },
    'content': 'Foo bar!',
    'id': tag_uri('212038_124561947600007_672819'),
    'published': '2010-10-28T00:23:04+00:00',
    'url': 'http://instagram.com/212038/posts/124561947600007?comment_id=672819',
    'inReplyTo': {'id': tag_uri('212038_124561947600007')},
    },
]
POST_OBJ = {  # ActivityStreams
  'objectType': 'photo',
  'author': {
    'id': tag_uri('212038'),
    'displayName': 'Ryan Barrett',
    'image': {'url': 'http://graph.instagram.com/212038/picture?type=large'},
    'url': 'http://instagram.com/212038',
    },
  'content': 'Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block Party Hackathon, cc Daniel M.',
  'id': tag_uri('212038_10100176064482163'),
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'url': 'http://instagram.com/212038/posts/10100176064482163',
  'image': {'url': 'https://fbcdn-photos-a.akamaihd.net/abc_xyz_s.jpg'},
  'attachments': [{
      'objectType': 'image',
      'url': 'http://my.link/',
      'displayName': 'my link name',
      'summary': 'my link caption',
      'content': 'my link description',
      'image': {'url': 'https://fbcdn-photos-a.akamaihd.net/abc_xyz_o.jpg'}
      }],
  'location': {
    'displayName': 'Lake Merced',
    'id': '113785468632283',
    'url': 'http://instagram.com/113785468632283',
    'latitude': 37.728193717481,
    'longitude': -122.49336423595,
    'position': '+37.728194-122.493364/',
    },
  'tags': [{
      'objectType': 'person',
      'id': tag_uri('234'),
      'url': 'http://instagram.com/234',
      'displayName': 'Friend 1',
      }, {
      'objectType': 'person',
      'id': tag_uri('345'),
      'url': 'http://instagram.com/345',
      'displayName': 'Friend 2',
      }, {
      'objectType': 'person',
      'id': tag_uri('345'),
      'url': 'http://instagram.com/345',
      'displayName': 'Friend 2',
      }, {
      'objectType': 'person',
      'id': tag_uri('456'),
      'url': 'http://instagram.com/456',
      'displayName': 'Friend 3',
      }, {
      'objectType': 'person',
      'id': tag_uri('456'),
      'url': 'http://instagram.com/456',
      'displayName': 'Daniel M',
      'startIndex': 122,
      'length': 8,
      }, {
      'objectType': 'event',
      'id': tag_uri('283938455011303'),
      'url': 'http://instagram.com/283938455011303',
      'displayName': 'Super Happy Block Party Hackathon',
      'startIndex': 84,
      'length': 33,
      },
    ],
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
    }
  }
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'id': tag_uri('212038_10100176064482163'),
  'url': 'http://instagram.com/212038/posts/10100176064482163',
  'actor': POST_OBJ['author'],
  'object': POST_OBJ,
  'title': 'Ryan Barrett: Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block Party Hackathon, cc Daniel M.',
  'generator': {
    'displayName': 'Instagram for Android',
    'id': tag_uri('350685531728'),
    }
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

<subtitle>something about me</subtitle>

<logo>http://graph.instagram.com/snarfed.org/picture?type=large</logo>
<updated>2012-03-04T18:20:37+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://www.instagram.com/snarfed.org</uri>
 <name>Ryan Barrett</name>
</author>

<link href="http://www.instagram.com/snarfed.org" rel="alternate" type="text/html" />
<link rel="avatar" href="http://graph.instagram.com/snarfed.org/picture?type=large" />
<link href="%(request_url)s" rel="self" type="application/atom+xml" />
<!-- TODO -->
<!-- <link href="" rel="hub" /> -->
<!-- <link href="" rel="salmon" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-replies" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-mention" /> -->

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://instagram.com/212038</uri>
 <name>Ryan Barrett</name>
</author>


  <activity:object-type>
    http://activitystrea.ms/schema/1.0/photo
  </activity:object-type>
  <id>""" + tag_uri('212038_10100176064482163') + """</id>
  <title>Ryan Barrett: Checking another side project off my list. portablecontacts-unofficial is live! &lt;3 Super Happy Block Party Hackathon, cc Daniel M.</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

Checking another side project off my list. portablecontacts-unofficial is live! &lt;3 Super Happy Block Party Hackathon, cc Daniel M.

<p><a href='http://my.link/'>
  <img style='float: left' src='https://fbcdn-photos-a.akamaihd.net/abc_xyz_o.jpg' />
  my link name
</a></p>
<p>my link description</p>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="http://instagram.com/212038/posts/10100176064482163" />
  <link rel="ostatus:conversation" href="http://instagram.com/212038/posts/10100176064482163" />
  
    <link rel="ostatus:attention" href="http://instagram.com/234" />
    <link rel="mentioned" href="http://instagram.com/234" />
  
    <link rel="ostatus:attention" href="http://instagram.com/345" />
    <link rel="mentioned" href="http://instagram.com/345" />
  
    <link rel="ostatus:attention" href="http://instagram.com/345" />
    <link rel="mentioned" href="http://instagram.com/345" />
  
    <link rel="ostatus:attention" href="http://instagram.com/456" />
    <link rel="mentioned" href="http://instagram.com/456" />
  
    <link rel="ostatus:attention" href="http://instagram.com/456" />
    <link rel="mentioned" href="http://instagram.com/456" />
  
    <link rel="ostatus:attention" href="http://instagram.com/283938455011303" />
    <link rel="mentioned" href="http://instagram.com/283938455011303" />
  
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T19:08:16+00:00</updated>
  
  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->
  
  
    <georss:point>37.7281937175 -122.493364236</georss:point>
  
  
    <georss:featureName>Lake Merced</georss:featureName>
  
  
  <link rel="self" type="application/atom+xml" href="http://instagram.com/212038/posts/10100176064482163" />
</entry>

</feed>
"""

class InstagramTest(testutil.HandlerTest):

  def setUp(self):
    super(InstagramTest, self).setUp()
    self.instagram = instagram.Instagram(self.handler)

  # def test_get_actor(self):
  #   self.expect_urlfetch('https://graph.instagram.com/foo', json.dumps(USER))
  #   self.mox.ReplayAll()
  #   self.assert_equals(ACTOR, self.instagram.get_actor('foo'))

  # def test_get_actor_default(self):
  #   self.expect_urlfetch('https://graph.instagram.com/me', json.dumps(USER))
  #   self.mox.ReplayAll()
  #   self.assert_equals(ACTOR, self.instagram.get_actor())

  # def test_get_activities_defaults(self):
  #   resp = json.dumps({'data': [
  #         {'id': '1_2', 'message': 'foo'},
  #         {'id': '3_4', 'message': 'bar'},
  #         ]})
  #   self.expect_urlfetch(
  #     'https://graph.instagram.com/me/home?offset=0&limit=0', resp)
  #   self.mox.ReplayAll()

  #   self.assert_equals((
  #       None,
  #       [{'id': tag_uri('1_2'),
  #         'object': {'content': 'foo',
  #                    'id': tag_uri('1_2'),
  #                    'objectType': 'note',
  #                    'url': 'http://instagram.com/1/posts/2'},
  #         'title': 'foo',
  #         'url': 'http://instagram.com/1/posts/2',
  #         'verb': 'post'},
  #        {'id': tag_uri('3_4'),
  #         'object': {'content': 'bar',
  #                    'id': tag_uri('3_4'),
  #                    'objectType': 'note',
  #                    'url': 'http://instagram.com/3/posts/4'},
  #         'title': 'bar',
  #         'url': 'http://instagram.com/3/posts/4',
  #         'verb': 'post'},
  #        ]),
  #     self.instagram.get_activities())

  # def test_get_activities_self(self):
  #   self.expect_urlfetch(
  #     'https://graph.instagram.com/me/posts?offset=0&limit=0', '{}')
  #   self.mox.ReplayAll()
  #   self.assert_equals((None, []),
  #                      self.instagram.get_activities(group_id=source.SELF))

  # def test_get_activities_passes_through_access_token(self):
  #   self.expect_urlfetch(
  #     'https://graph.instagram.com/me/home?offset=0&limit=0&access_token=asdf',
  #     '{"id": 123}')
  #   self.mox.ReplayAll()

  #   handler = webapp2.RequestHandler(webapp2.Request.blank('/?access_token=asdf'),
  #                                    webapp2.Response())
  #   self.instagram = instagram.Instagram(handler)
  #   self.instagram.get_activities()

  # def test_get_activities_activity_id(self):
  #   self.expect_urlfetch('https://graph.instagram.com/000', json.dumps(POST))
  #   self.mox.ReplayAll()

  #   # activity id overrides user, group, app id and ignores startIndex and count
  #   self.assert_equals(
  #     (1, [ACTIVITY]),
  #     self.instagram.get_activities(
  #       user_id='123', group_id='456', app_id='789', activity_id='000',
  #       start_index=3, count=6))

  # def test_get_activities_activity_id_not_found(self):
  #   self.expect_urlfetch('https://graph.instagram.com/000', 'false')
  #   self.mox.ReplayAll()
  #   self.assert_equals((0, []), self.instagram.get_activities(activity_id='000'))

  # def test_post_to_activity_full(self):
  #   self.assert_equals(ACTIVITY, self.instagram.post_to_activity(POST))

  # def test_post_to_activity_minimal(self):
  #   # just test that we don't crash
  #   self.instagram.post_to_activity({'id': '123_456', 'message': 'asdf'})

  # def test_post_to_activity_empty(self):
  #   # just test that we don't crash
  #   self.instagram.post_to_activity({})

  # def test_post_to_object_full(self):
  #   self.assert_equals(POST_OBJ, self.instagram.post_to_object(POST))

  # def test_post_to_object_minimal(self):
  #   # just test that we don't crash
  #   self.instagram.post_to_object({'id': '123_456', 'message': 'asdf'})

  # def test_post_to_object_empty(self):
  #   self.assert_equals({}, self.instagram.post_to_object({}))

  # def test_comment_to_object_full(self):
  #   for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
  #     self.assert_equals(obj, self.instagram.comment_to_object(cmt))

  # def test_comment_to_object_minimal(self):
  #   # just test that we don't crash
  #   self.instagram.comment_to_object({'id': '123_456_789', 'message': 'asdf'})

  # def test_comment_to_object_empty(self):
  #   self.assert_equals({}, self.instagram.comment_to_object({}))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.instagram.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    self.assert_equals({'id': tag_uri('420973239'), 'username': None},
                       self.instagram.user_to_actor(Struct(id='420973239')))
    self.assert_equals({'id': tag_uri('snarfed'), 'username': 'snarfed'},
                       self.instagram.user_to_actor(Struct(username='snarfed')))
