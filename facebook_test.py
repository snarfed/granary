#!/usr/bin/python
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

# test data
USER = {
  'id': '212038',
  'name': 'Ryan Barrett',
  'link': 'http://www.facebook.com/snarfed.org',
  'username': 'snarfed.org',
  'location': {'id': '123', 'name': 'San Francisco, California'},
  'updated_time': '2012-01-06T02:11:04+0000',
  'bio': 'something about me',
  }
ACTOR = {
  'displayName': 'Ryan Barrett',
  'image': {'url': 'http://graph.facebook.com/snarfed.org/picture?type=large'},
  'id': 'tag:facebook.com,2012:snarfed.org',
  'updated': '2012-01-06T02:11:04+0000',
  'url': 'http://www.facebook.com/snarfed.org',
  'username': 'snarfed.org',
  'description': 'something about me',
  'location': {'id': '123', 'displayName': 'San Francisco, California'},
  }
POST = {
  'id': '212038_10100176064482163',
  'from': {'name': 'Ryan Barrett', 'id': '212038'},
  'story': 'Ryan Barrett added a new photo.',
  'picture': 'https://fbcdn-photos-a.akamaihd.net/hphotos-ak-ash4/420582_10100176064452223_212038_41571100_37729316_s.jpg',
  'link': 'http://snarfed.org/2012-02-22_portablecontacts_for_facebook_and_twitter',
  'message': 'Checking another side project off my list. portablecontacts-unofficial is live!',
  'name': 'PortableContacts for Facebook and Twitter',
  'caption': 'snarfed.org',
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
}
OBJECT = {
  'objectType': 'note',
  'author': {
    'id': 'tag:facebook.com,2012:212038',
    'displayName': 'Ryan Barrett',
    'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
    },
  'content': 'Checking another side project off my list. portablecontacts-unofficial is live!',
  'id': 'tag:facebook.com,2012:212038_10100176064482163',
  'published': '2012-03-04T18:20:37+0000',
  'updated': '2012-03-04T19:08:16+0000',
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'image': {'url': 'https://fbcdn-photos-a.akamaihd.net/hphotos-ak-ash4/420582_10100176064452223_212038_41571100_37729316_s.jpg'},
  'location': {
    'displayName': 'Lake Merced',
    'id': '113785468632283',
    'latitude': 37.728193717481,
    'longitude': -122.49336423595,
    'position': '+37.728194-122.493364/',
    },
  }
ACTIVITY = {
  'verb': 'post',
  'published': '2012-03-04T18:20:37+0000',
  'updated': '2012-03-04T19:08:16+0000',
  'id': 'tag:facebook.com,2012:212038_10100176064482163',
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'actor': OBJECT['author'],
  'object': OBJECT,
  'generator': {
    'displayName': 'Facebook for Android',
    'id': 'tag:facebook.com,2012:350685531728',
    }
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
<subtitle>something about me</subtitle>
<logo>http://graph.facebook.com/snarfed.org/picture?type=large</logo>
<updated>2012-01-06T02:11:04+0000</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://www.facebook.com/snarfed.org</uri>
 <name>Ryan Barrett</name>
 <link rel="alternate" type="text/html" href="http://www.facebook.com/snarfed.org" />
 <link rel="avatar" href="http://graph.facebook.com/snarfed.org/picture?type=large" />
</author>

<link href="http://www.facebook.com/snarfed.org" rel="alternate" type="text/html" />
<link href="%(request_url)s" rel="self" type="application/atom+xml" />
<!-- TODO -->
<!-- <link href="" rel="hub" /> -->
<!-- <link href="" rel="salmon" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-replies" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-mention" /> -->

<entry>
  <activity:object-type>
    http://activitystrea.ms/schema/1.0/note
  </activity:object-type>
  <id>tag:facebook.com,2012:212038_10100176064482163</id>
  <title>Checking another side project off my list. portablecontacts-unofficial is live!</title>
  <content type="text">Checking another side project off my list. portablecontacts-unofficial is live!</content>
  <link rel="alternate" type="text/html" href="http://facebook.com/212038/posts/10100176064482163" />
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-03-04T18:20:37+0000</published>
  <updated>2012-03-04T19:08:16+0000</updated>
  
  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->
  <georss:point>
    37.7281937175 -122.493364236
  </georss:point>
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
        [{'id': 'tag:facebook.com,2012:1_2',
          'object': {'content': 'foo',
                     'id': 'tag:facebook.com,2012:1_2',
                     'objectType': 'note',
                     'url': 'http://facebook.com/1/posts/2'},
          'url': 'http://facebook.com/1/posts/2',
          'verb': 'post'},
         {'id': 'tag:facebook.com,2012:3_4',
          'object': {'content': 'bar',
                     'id': 'tag:facebook.com,2012:3_4',
                     'objectType': 'note',
                     'url': 'http://facebook.com/3/posts/4'},
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
    self.assert_equals(OBJECT, self.facebook.post_to_object(POST))

  def test_post_to_object_minimal(self):
    # just test that we don't crash
    self.facebook.post_to_object({'id': '123_456', 'message': 'asdf'})

  def test_post_to_object_empty(self):
    self.assert_equals({}, self.facebook.post_to_object({}))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.facebook.user_to_actor(USER))

  def test_user_to_actor_minimal(self):
    actor = self.facebook.user_to_actor({'id': '212038'})
    self.assert_equals('tag:facebook.com,2012:212038', actor['id'])
    self.assert_equals('http://graph.facebook.com/212038/picture?type=large',
                       actor['image']['url'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.facebook.user_to_actor({}))
