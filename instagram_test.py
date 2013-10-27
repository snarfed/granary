#!/usr/bin/python
# -*- eval: (progn (make-local-variable 'before-save-hook) (remove-hook 'before-save-hook 'delete-trailing-whitespace-in-some-modes t)) -*-
#
# (the above line is an Emacs file local variable that says *not* to delete
# trailing whitespace, since some of it in test data is meaningful.)
"""Unit tests for instagram.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import datetime
import httplib2
import json
import mox
import urllib
import urlparse

import instagram
from oauth_dropins.python_instagram.bind import InstagramAPIError
import source
from webutil import testutil
from webutil import util
from webutil.util import Struct
import webapp2


def tag_uri(name):
  return util.tag_uri('instagram.com', name)


# Test data.
# The Instagram API returns objects with attributes, not JSON dicts.
USER = Struct(  # Instagram
  username='snarfed',
  bio='foo',
  website='http://snarfed.org/',
  profile_picture='http://picture/ryan',
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
  'image': {'url': 'http://picture/ryan'},
  'id': tag_uri('snarfed'),
  'url': 'http://snarfed.org/',
  'username': 'snarfed',
  'description': 'foo',
  }
COMMENTS = [Struct(  # Instagram
    created_at=datetime.datetime.fromtimestamp(1349588757),
    text='\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
    user=Struct(
      username='averygood',
      profile_picture='http://picture/commenter',
      id='232927278',
      full_name='\u5c0f\u6b63'
      ),
    id='789'
    )]
MEDIA = Struct(  # Instagram
  id='123_456',
  filter='Normal',
  created_time=datetime.datetime.fromtimestamp(1348291542),
  link='http://instagram.com/p/ABC123/',
  user_has_liked=False,
  attribution=None,
  location=None,
  user=USER,
  comments=COMMENTS,
  comment_count=len(COMMENTS),
  images={
    'low_resolution': Struct(
      url='http://attach/image/small',
      width=306,
      height=306
      ),
    'thumbnail': Struct(
      url='http://attach/image/thumb',
      width=150,
      height=150
      ),
    'standard_resolution': Struct(
      url='http://attach/image/big',
      width=612,
      height=612
      ),
    },
  tags=[Struct(name='abc'), Struct(name='xyz')],
  users_in_photo=[Struct(user=USER, position=Struct(x=1, y=2))],
  caption=Struct(
    created_time='1348291558',
    text='this picture is #abc #xyz',
    user={},
    id='285812769105340251'
    ),
  )
COMMENT_OBJS = [  # ActivityStreams
  {
    'objectType': 'comment',
    'author': {
      'id': tag_uri('averygood'),
      'username': 'averygood',
      'displayName': '\u5c0f\u6b63',
      'image': {'url': 'http://picture/commenter'},
      'url': 'http://instagram.com/averygood',
      },
    'content': '\u592a\u53ef\u7231\u4e86\u3002cute\uff0cvery cute',
    'id': tag_uri('789'),
    'published': '2012-10-06T22:45:57',
    'url': 'http://instagram.com/p/ABC123/',
    'inReplyTo': {'id': tag_uri('123_456')},
    },
]
POST_OBJ = {  # ActivityStreams
  'objectType': 'photo',
  'author': ACTOR,
  'content': 'this picture is #abc #xyz',
  'id': tag_uri('123_456'),
  'published': '2012-09-21T22:25:42',
  'url': 'http://instagram.com/p/ABC123/',
  'image': {'url': 'http://attach/image/big'},
  'attachments': [{
      'objectType': 'image',
      'image': {
        'url': 'http://attach/image/thumb',
        'width': 150,
        'height': 150,
        }
      }, {
      'objectType': 'image',
      'image': {
        'url': 'http://attach/image/small',
        'width': 306,
        'height': 306,
        }
      }, {
      'objectType': 'image',
      'image': {
        'url': 'http://attach/image/big',
        'width': 612,
        'height': 612,
        }
      }],
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
    },
  'tags': [{
      'objectType': 'person',
      'id': tag_uri('snarfed'),
      'url': 'http://instagram.com/snarfed',
      'displayName': 'Ryan B',
      'image': {'url': 'http://picture/ryan'},
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
  'published': '2012-09-21T22:25:42',
  'id': tag_uri('123_456'),
  'url': 'http://instagram.com/p/ABC123/',
  'actor': ACTOR,
  'object': POST_OBJ,
  'title': 'Ryan B: this picture is #abc #xyz',
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
<title>User feed for Ryan B</title>

<subtitle>foo</subtitle>

<logo>http://picture/ryan</logo>
<updated>2012-09-21T22:25:42</updated>
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
  <id>""" + tag_uri('123_456') + """</id>
  <title>Ryan B: this picture is #abc #xyz</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

this picture is #abc #xyz

<p><a href=''>
  <img style='float: left' src='http://attach/image/thumb' /><br />
  </a><br />

</p>
<p></p>

<p><a href=''>
  <img style='float: left' src='http://attach/image/small' /><br />
  </a><br />

</p>
<p></p>

<p><a href=''>
  <img style='float: left' src='http://attach/image/big' /><br />
  </a><br />

</p>
<p></p>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="http://instagram.com/p/ABC123/" />
  <link rel="ostatus:conversation" href="http://instagram.com/p/ABC123/" />
  
    <link rel="ostatus:attention" href="http://instagram.com/snarfed" />
    <link rel="mentioned" href="http://instagram.com/snarfed" />
  
    <link rel="ostatus:attention" href="" />
    <link rel="mentioned" href="" />
  
    <link rel="ostatus:attention" href="" />
    <link rel="mentioned" href="" />
  
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-09-21T22:25:42</published>
  <updated></updated>
  
  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->
  
  
  
  
  <link rel="self" type="application/atom+xml" href="http://instagram.com/p/ABC123/" />
</entry>

</feed>
"""

class InstagramTest(testutil.HandlerTest):

  def setUp(self):
    super(InstagramTest, self).setUp()
    self.instagram = instagram.Instagram()

  def test_get_actor(self):
    self.mox.StubOutWithMock(self.instagram.api, 'user')
    self.instagram.api.user('foo').AndReturn(USER)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.instagram.get_actor('foo'))

  def test_get_actor_default(self):
    self.mox.StubOutWithMock(self.instagram.api, 'user')
    self.instagram.api.user('self').AndReturn(USER)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.instagram.get_actor())

  def test_get_activities_self(self):
    self.mox.StubOutWithMock(self.instagram.api, 'user_recent_media')
    self.instagram.api.user_recent_media('self').AndReturn(([], {}))
    self.mox.ReplayAll()
    self.assert_equals((0, []),
                       self.instagram.get_activities(group_id=source.SELF))

  def test_get_activities_passes_through_access_token(self):
    self.mox.StubOutWithMock(httplib2.Http, 'request')
    httplib2.Http.request(
      'https://api.instagram.com/v1/users/self/feed.json?access_token=asdf',
      'GET', body=None, headers=mox.IgnoreArg()).AndReturn(
      ({'status': '200'},
       json.dumps({'meta': {'code': 200}, 'data': []})))
    self.mox.ReplayAll()

    self.instagram = instagram.Instagram(access_token='asdf')
    self.instagram.get_activities()

  def test_get_activities_activity_id(self):
    self.mox.StubOutWithMock(self.instagram.api, 'media')
    self.instagram.api.media('000').AndReturn(MEDIA)
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals(
      (1, [ACTIVITY]),
      self.instagram.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_activity_id_not_found(self):
    self.mox.StubOutWithMock(self.instagram.api, 'media')
    self.instagram.api.media('000').AndRaise(
      InstagramAPIError(400, 'APINotFoundError', 'msg'))
    self.mox.ReplayAll()
    self.assert_equals((0, []), self.instagram.get_activities(activity_id='000'))

  def test_get_activities_other_400_error(self):
    self.mox.StubOutWithMock(self.instagram.api, 'media')
    self.instagram.api.media('000').AndRaise(InstagramAPIError(400, 'other', 'msg'))
    self.mox.ReplayAll()
    self.assertRaises(InstagramAPIError, self.instagram.get_activities,
                      activity_id='000')

  def test_media_to_activity(self):
    self.assert_equals(ACTIVITY, self.instagram.media_to_activity(MEDIA))

  def test_media_to_object(self):
    self.assert_equals(POST_OBJ, self.instagram.media_to_object(MEDIA))

  def test_comment_to_object(self):
    for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
      self.assert_equals(obj, self.instagram.comment_to_object(
          cmt, '123_456', 'http://instagram.com/p/ABC123/'))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.instagram.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    self.assert_equals({'id': tag_uri('420973239'), 'username': None},
                       self.instagram.user_to_actor(Struct(id='420973239')))
    self.assert_equals({'id': tag_uri('snarfed'), 'username': 'snarfed'},
                       self.instagram.user_to_actor(Struct(username='snarfed')))
