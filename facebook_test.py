#!/usr/bin/python
# -*- eval: (progn (make-local-variable 'before-save-hook) (remove-hook 'before-save-hook 'delete-trailing-whitespace-in-some-modes t)) -*-
#
# (the above line is an Emacs file local variable that says *not* to delete
# trailing whitespace, since some of it in test data is meaningful.)
"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json
import mox
import urllib
import urlparse
from webutil import webapp2

import facebook
import source
from webutil import testutil
from webutil import util


# test data
def tag_uri(name):
  return util.tag_uri('facebook.com', name)

USER = {  # Facebook
  'id': '212038',
  'name': 'Ryan Barrett',
  'link': 'http://www.facebook.com/snarfed.org',
  'username': 'snarfed.org',
  'location': {'id': '123', 'name': 'San Francisco, California'},
  'updated_time': '2012-01-06T02:11:04+0000',
  'bio': 'something about me',
  }
ACTOR = {  # ActivityStreams
  'displayName': 'Ryan Barrett',
  'image': {'url': 'http://graph.facebook.com/snarfed.org/picture?type=large'},
  'id': tag_uri('snarfed.org'),
  'updated': '2012-01-06T02:11:04+00:00',
  'url': 'http://www.facebook.com/snarfed.org',
  'username': 'snarfed.org',
  'description': 'something about me',
  'location': {'id': '123', 'displayName': 'San Francisco, California'},
  }
COMMENTS = [{  # Facebook
    'id': '212038_547822715231468_6796480',
    'from': {
      'name': 'Ryan Barrett',
      'id': '212038'
      },
    'message': 'cc Sam G, Michael M',
    'message_tags': [{
        'id': '221330',
        'name': 'Sam G',
        'type': 'user',
        'offset': 3,
        'length': 5,
        }, {
        'id': '695687650',
        'name': 'Michael Mandel',
        'type': 'user',
        'offset': 10,
        'length': 9,
        }],
    'created_time': '2012-12-05T00:58:26+0000',
    }, {
    'id': '212038_124561947600007_672819',
    'from': {
      'name': 'Ron Ald',
      'id': '513046677'
      },
    'message': 'Foo bar!',
    'created_time': '2010-10-28T00:23:04+0000'
    }]
POST = {  # Facebook
  'id': '212038_10100176064482163',
  'from': {'name': 'Ryan Barrett', 'id': '212038'},
  'to': {'data': [
      {'name': 'Friend 1', 'id': '234'},
      {'name': 'Friend 2', 'id': '345'},
      ]},
  'with_tags': {'data': [
      {'name': 'Friend 2', 'id': '345'}, # same id, tags shouldn't be de-duped
      {'name': 'Friend 3', 'id': '456'},
      ]},
  'story': 'Ryan Barrett added a new photo.',
  'picture': 'https://fbcdn-photos-a.akamaihd.net/abc_xyz_s.jpg',
  'message': 'Checking another side project off my list. portablecontacts-unofficial is live!  cc Super Happy Block Party Hackathon, Daniel M.',
  'message_tags': {
    '84': [{
        'id': '283938455011303',
        'name': 'Super Happy Block Party Hackathon',
        'type': 'event',
        'offset': 84,
        'length': 33,
        }],
    '119': [{
        'id': '456',
        'name': 'Daniel M',
        'type': 'user',
        'offset': 119,
        'length': 8,
        }],
    },
  'link': 'http://my.link/',
  'name': 'my link name',
  'caption': 'my link caption',
  'description': 'my link description',
  'icon': 'https://s-static.ak.facebook.com/rsrc.php/v1/yx/r/og8V99JVf8G.gif',
  'place': {
    'id': '113785468632283',
    'name': 'Lake Merced',
    'location': {
      'city': 'San Francisco',
      'state': 'CA',
      'country': 'United States',
      'latitude': 37.728193717481,
      'longitude': -122.49336423595
    }
  },
  'type': 'photo',
  'object_id': '10100176064452223',
  'application': {'name': 'Facebook for Android', 'id': '350685531728'},
  'created_time': '2012-03-04T18:20:37+0000',
  'updated_time': '2012-03-04T19:08:16+0000',
  'comments': {
    'data': COMMENTS,
    'count': len(COMMENTS),
    },
}
COMMENT_OBJS = [  # ActivityStreams
  {
    'objectType': 'comment',
    'author': {
      'id': tag_uri('212038'),
      'displayName': 'Ryan Barrett',
      'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
      'url': 'http://facebook.com/212038',
      },
    'content': 'cc Sam G, Michael M',
    'id': tag_uri('212038_547822715231468_6796480'),
    'published': '2012-12-05T00:58:26+00:00',
    'url': 'http://facebook.com/212038/posts/547822715231468?comment_id=6796480',
    'inReplyTo': {'id': tag_uri('212038_547822715231468')},
    'tags': [{
        'objectType': 'person',
        'id': tag_uri('221330'),
        'url': 'http://facebook.com/221330',
        'displayName': 'Sam G',
        'startIndex': 3,
        'length': 5,
        }, {
        'objectType': 'person',
        'id': tag_uri('695687650'),
        'url': 'http://facebook.com/695687650',
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
      'image': {'url': 'http://graph.facebook.com/513046677/picture?type=large'},
      'url': 'http://facebook.com/513046677',
      },
    'content': 'Foo bar!',
    'id': tag_uri('212038_124561947600007_672819'),
    'published': '2010-10-28T00:23:04+00:00',
    'url': 'http://facebook.com/212038/posts/124561947600007?comment_id=672819',
    'inReplyTo': {'id': tag_uri('212038_124561947600007')},
    },
]
POST_OBJ = {  # ActivityStreams
  'objectType': 'photo',
  'author': {
    'id': tag_uri('212038'),
    'displayName': 'Ryan Barrett',
    'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
    'url': 'http://facebook.com/212038',
    },
  'content': 'Checking another side project off my list. portablecontacts-unofficial is live!  cc Super Happy Block Party Hackathon, Daniel M.',
  'id': tag_uri('212038_10100176064482163'),
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'url': 'http://facebook.com/212038/posts/10100176064482163',
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
    'url': 'http://facebook.com/113785468632283',
    'latitude': 37.728193717481,
    'longitude': -122.49336423595,
    'position': '+37.728194-122.493364/',
    },
  'tags': [{
      'objectType': 'person',
      'id': tag_uri('234'),
      'url': 'http://facebook.com/234',
      'displayName': 'Friend 1',
      }, {
      'objectType': 'person',
      'id': tag_uri('345'),
      'url': 'http://facebook.com/345',
      'displayName': 'Friend 2',
      }, {
      'objectType': 'person',
      'id': tag_uri('345'),
      'url': 'http://facebook.com/345',
      'displayName': 'Friend 2',
      }, {
      'objectType': 'person',
      'id': tag_uri('456'),
      'url': 'http://facebook.com/456',
      'displayName': 'Friend 3',
      }, {
      'objectType': 'person',
      'id': tag_uri('456'),
      'url': 'http://facebook.com/456',
      'displayName': 'Daniel M',
      'startIndex': 119,
      'length': 8,
      }, {
      'objectType': 'event',
      'id': tag_uri('283938455011303'),
      'url': 'http://facebook.com/283938455011303',
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
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'actor': POST_OBJ['author'],
  'object': POST_OBJ,
  'title': 'Ryan Barrett: Checking another side project off my list. portablecontacts-unofficial is live!  cc Super Happy Block Party Hackathon, Daniel M.',
  'generator': {
    'displayName': 'Facebook for Android',
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
<id>%(request_url)s</id>
<title>User feed for Ryan Barrett</title>

<subtitle>something about me</subtitle>

<logo>http://graph.facebook.com/snarfed.org/picture?type=large</logo>
<updated>2012-03-04T18:20:37+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://www.facebook.com/snarfed.org</uri>
 <name>Ryan Barrett</name>
</author>

<link href="http://www.facebook.com/snarfed.org" rel="alternate" type="text/html" />
<link rel="avatar" href="http://graph.facebook.com/snarfed.org/picture?type=large" />
<link href="%(request_url)s" rel="self" type="application/atom+xml" />
<!-- TODO -->
<!-- <link href="" rel="hub" /> -->
<!-- <link href="" rel="salmon" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-replies" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-mention" /> -->

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://facebook.com/212038</uri>
 <name>Ryan Barrett</name>
</author>


  <activity:object-type>
    http://activitystrea.ms/schema/1.0/photo
  </activity:object-type>
  <id>""" + tag_uri('212038_10100176064482163') + """</id>
  <title>Ryan Barrett: Checking another side project off my list. portablecontacts-unofficial is live!  cc Super Happy Block Party Hackathon, Daniel M.</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

Checking another side project off my list. portablecontacts-unofficial is live!  cc Super Happy Block Party Hackathon, Daniel M.

<p><a href='http://my.link/'>
  <img style='float: left' src='https://fbcdn-photos-a.akamaihd.net/abc_xyz_o.jpg' />
  my link name
</a></p>
<p>my link description</p>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="http://facebook.com/212038/posts/10100176064482163" />
  <link rel="ostatus:conversation" href="http://facebook.com/212038/posts/10100176064482163" />
  
    <link rel="ostatus:attention" href="http://facebook.com/234" />
    <link rel="mentioned" href="http://facebook.com/234" />
  
    <link rel="ostatus:attention" href="http://facebook.com/345" />
    <link rel="mentioned" href="http://facebook.com/345" />
  
    <link rel="ostatus:attention" href="http://facebook.com/345" />
    <link rel="mentioned" href="http://facebook.com/345" />
  
    <link rel="ostatus:attention" href="http://facebook.com/456" />
    <link rel="mentioned" href="http://facebook.com/456" />
  
    <link rel="ostatus:attention" href="http://facebook.com/456" />
    <link rel="mentioned" href="http://facebook.com/456" />
  
    <link rel="ostatus:attention" href="http://facebook.com/283938455011303" />
    <link rel="mentioned" href="http://facebook.com/283938455011303" />
  
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T19:08:16+00:00</updated>
  
  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->
  
  
    <georss:point>37.7281937175 -122.493364236</georss:point>
  
  
    <georss:featureName>Lake Merced</georss:featureName>
  
  
  <link rel="self" type="application/atom+xml" href="http://facebook.com/212038/posts/10100176064482163" />
</entry>

</feed>
"""

class FacebookTest(testutil.HandlerTest):

  def setUp(self):
    super(FacebookTest, self).setUp()
    self.facebook = facebook.Facebook(self.handler)

  def test_get_actor(self):
    self.expect_urlfetch('https://graph.facebook.com/foo', json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.facebook.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlfetch('https://graph.facebook.com/me', json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.facebook.get_actor())

  def test_get_activities_defaults(self):
    resp = json.dumps({'data': [
          {'id': '1_2', 'message': 'foo'},
          {'id': '3_4', 'message': 'bar'},
          ]})
    self.expect_urlfetch(
      'https://graph.facebook.com/me/home?offset=0&limit=0', resp)
    self.mox.ReplayAll()

    self.assert_equals((
        None,
        [{'id': tag_uri('1_2'),
          'object': {'content': 'foo',
                     'id': tag_uri('1_2'),
                     'objectType': 'note',
                     'url': 'http://facebook.com/1/posts/2'},
          'title': 'foo',
          'url': 'http://facebook.com/1/posts/2',
          'verb': 'post'},
         {'id': tag_uri('3_4'),
          'object': {'content': 'bar',
                     'id': tag_uri('3_4'),
                     'objectType': 'note',
                     'url': 'http://facebook.com/3/posts/4'},
          'title': 'bar',
          'url': 'http://facebook.com/3/posts/4',
          'verb': 'post'},
         ]),
      self.facebook.get_activities())

  def test_get_activities_self(self):
    self.expect_urlfetch(
      'https://graph.facebook.com/me/posts?offset=0&limit=0', '{}')
    self.mox.ReplayAll()
    self.assert_equals((None, []),
                       self.facebook.get_activities(group_id=source.SELF))

  def test_get_activities_passes_through_access_token(self):
    self.expect_urlfetch(
      'https://graph.facebook.com/me/home?offset=0&limit=0&access_token=asdf',
      '{"id": 123}')
    self.mox.ReplayAll()

    handler = webapp2.RequestHandler(webapp2.Request.blank('/?access_token=asdf'),
                                     webapp2.Response())
    self.facebook = facebook.Facebook(handler)
    self.facebook.get_activities()

  def test_get_activities_activity_id(self):
    self.expect_urlfetch('https://graph.facebook.com/000', json.dumps(POST))
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals(
      (1, [ACTIVITY]),
      self.facebook.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_activity_id_not_found(self):
    self.expect_urlfetch('https://graph.facebook.com/000', 'false')
    self.mox.ReplayAll()
    self.assert_equals((0, []), self.facebook.get_activities(activity_id='000'))

  def test_post_to_activity_full(self):
    self.assert_equals(ACTIVITY, self.facebook.post_to_activity(POST))

  def test_post_to_activity_minimal(self):
    # just test that we don't crash
    self.facebook.post_to_activity({'id': '123_456', 'message': 'asdf'})

  def test_post_to_activity_empty(self):
    # just test that we don't crash
    self.facebook.post_to_activity({})

  def test_post_to_object_full(self):
    self.assert_equals(POST_OBJ, self.facebook.post_to_object(POST))

  def test_post_to_object_minimal(self):
    # just test that we don't crash
    self.facebook.post_to_object({'id': '123_456', 'message': 'asdf'})

  def test_post_to_object_empty(self):
    self.assert_equals({}, self.facebook.post_to_object({}))

  def test_comment_to_object_full(self):
    for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
      self.assert_equals(obj, self.facebook.comment_to_object(cmt))

  def test_comment_to_object_minimal(self):
    # just test that we don't crash
    self.facebook.comment_to_object({'id': '123_456_789', 'message': 'asdf'})

  def test_comment_to_object_empty(self):
    self.assert_equals({}, self.facebook.comment_to_object({}))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.facebook.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    actor = self.facebook.user_to_actor({'id': '212038'})
    self.assert_equals(tag_uri('212038'), actor['id'])
    self.assert_equals('http://graph.facebook.com/212038/picture?type=large',
                       actor['image']['url'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.facebook.user_to_actor({}))
