"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import json
import mox
import urllib
import urlparse

import facebook
import source
from webutil import testutil
from webutil import util
import webapp2


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
    'id': '547822715231468_6796480',
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
    'id': '124561947600007_672819',
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
  'message': 'Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block Party Hackathon, cc Daniel M.',
  'message_tags': {
    '84': [{
        'id': '283938455011303',
        'name': 'Super Happy Block Party Hackathon',
        'type': 'event',
        'offset': 84,
        'length': 33,
        }],
    '122': [{
        'id': '456',
        'name': 'Daniel M',
        'type': 'user',
        'offset': 122,
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
  'likes': {
    'data': [{'id': '100004', 'name': 'Alice X'},
             {'id': '683713', 'name': 'Bob Y'},
             ],
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
    'id': tag_uri('547822715231468_6796480'),
    'published': '2012-12-05T00:58:26+00:00',
    'url': 'http://facebook.com/547822715231468?comment_id=6796480',
    'inReplyTo': [{'id': tag_uri('547822715231468')}],
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
    'id': tag_uri('124561947600007_672819'),
    'published': '2010-10-28T00:23:04+00:00',
    'url': 'http://facebook.com/124561947600007?comment_id=672819',
    'inReplyTo': [{'id': tag_uri('124561947600007')}],
    },
]
LIKE_OBJS = [{  # ActivityStreams
    'id': tag_uri('10100176064482163_liked_by_100004'),
    'objectType': 'activity',
    'verb': 'like',
    'object': {'url': 'http://facebook.com/212038/posts/10100176064482163'},
    'author': {
      'id': tag_uri('100004'),
      'displayName': 'Alice X',
      'url': 'http://facebook.com/100004',
      },
    }, {
    'id': tag_uri('10100176064482163_liked_by_683713'),
    'objectType': 'activity',
    'verb': 'like',
    'object': {'url': 'http://facebook.com/212038/posts/10100176064482163'},
    'author': {
      'id': tag_uri('683713'),
      'displayName': 'Bob Y',
      'url': 'http://facebook.com/683713',
      },
    },
  ]
POST_OBJ = {  # ActivityStreams
  'objectType': 'image',
  'author': {
    'id': tag_uri('212038'),
    'displayName': 'Ryan Barrett',
    'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
    'url': 'http://facebook.com/212038',
    },
  'content': 'Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block Party Hackathon, cc Daniel M.',
  'id': tag_uri('10100176064482163'),
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
      'startIndex': 122,
      'length': 8,
      }, {
      'objectType': 'event',
      'id': tag_uri('283938455011303'),
      'url': 'http://facebook.com/283938455011303',
      'displayName': 'Super Happy Block Party Hackathon',
      'startIndex': 84,
      'length': 33,
      },
    ] + LIKE_OBJS,
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
    }
  }
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'id': tag_uri('10100176064482163'),
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'actor': POST_OBJ['author'],
  'object': POST_OBJ,
  'title': 'Ryan Barrett: Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block Party Hackathon, cc Daniel M.',
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
<id>http://localhost/</id>
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
    http://activitystrea.ms/schema/1.0/image
  </activity:object-type>
  <id>""" + tag_uri('10100176064482163') + """</id>
  <title>Ryan Barrett: Checking another side project off my list. portablecontacts-unofficial is live! &lt;3 Super Happy Block Party Hackathon, cc Daniel M.</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

Checking another side project off my list. portablecontacts-unofficial is live! &lt;3 Super Happy Block Party Hackathon, cc Daniel M.

<p><a href='http://my.link/'>
  <img style='float: left' src='https://fbcdn-photos-a.akamaihd.net/abc_xyz_o.jpg' /><br />
  my link name</a><br />
my link caption
</p>
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
    self.facebook = facebook.Facebook()

  def test_get_actor(self):
    self.expect_urlopen('https://graph.facebook.com/foo', json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.facebook.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlopen('https://graph.facebook.com/me', json.dumps(USER))
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.facebook.get_actor())

  def test_get_activities_defaults(self):
    resp = json.dumps({'data': [
          {'id': '1_2', 'message': 'foo'},
          {'id': '3_4', 'message': 'bar'},
          ]})
    self.expect_urlopen(
      'https://graph.facebook.com/me/home?offset=0', resp)
    self.mox.ReplayAll()

    self.assert_equals((
        None,
        [{'id': tag_uri('2'),
          'object': {'content': 'foo',
                     'id': tag_uri('2'),
                     'objectType': 'note',
                     'url': 'http://facebook.com/2'},
          'title': 'Unknown: foo',
          'url': 'http://facebook.com/2',
          'verb': 'post'},
         {'id': tag_uri('4'),
          'object': {'content': 'bar',
                     'id': tag_uri('4'),
                     'objectType': 'note',
                     'url': 'http://facebook.com/4'},
          'title': 'Unknown: bar',
          'url': 'http://facebook.com/4',
          'verb': 'post'},
         ]),
      self.facebook.get_activities())

  def test_get_activities_self(self):
    self.expect_urlopen(
      'https://graph.facebook.com/me/posts?offset=0', '{}')
    self.mox.ReplayAll()
    self.assert_equals((None, []),
                       self.facebook.get_activities(group_id=source.SELF))

  def test_get_activities_passes_through_access_token(self):
    self.expect_urlopen(
      'https://graph.facebook.com/me/home?offset=0&access_token=asdf',
      '{"id": 123}')
    self.mox.ReplayAll()

    self.facebook = facebook.Facebook(access_token='asdf')
    self.facebook.get_activities()

  def test_get_activities_activity_id(self):
    self.expect_urlopen('https://graph.facebook.com/123_000', json.dumps(POST))
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals(
      (1, [ACTIVITY]),
      self.facebook.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_activity_id_not_found(self):
    self.expect_urlopen('https://graph.facebook.com/0', 'false')
    self.mox.ReplayAll()
    self.assert_equals((0, []), self.facebook.get_activities(activity_id='0_0'))

  def test_get_activities_start_index_and_count(self):
    self.expect_urlopen(
      'https://graph.facebook.com/me/posts?offset=3&limit=5', '{}')
    self.mox.ReplayAll()
    self.facebook.get_activities(group_id=source.SELF,start_index=3, count=5)

  def test_get_activities_activity_id(self):
    self.expect_urlopen('https://graph.facebook.com/34', '{}')
    self.mox.ReplayAll()
    self.facebook.get_activities(activity_id='34', user_id='12')

  def test_get_activities_activity_id_strips_user_id_prefix(self):
    self.expect_urlopen('https://graph.facebook.com/34', '{}')
    self.mox.ReplayAll()
    self.facebook.get_activities(activity_id='12_34')

  def test_get_activities_activity_id_fallback_to_user_id_prefix(self):
    self.expect_urlopen('https://graph.facebook.com/34', '{}', status=404)
    self.expect_urlopen('https://graph.facebook.com/12_34', '{}')
    self.mox.ReplayAll()
    self.facebook.get_activities(activity_id='12_34')

  def test_get_activities_activity_id_fallback_to_user_id_param(self):
    self.expect_urlopen('https://graph.facebook.com/34', '{}', status=400)
    self.expect_urlopen('https://graph.facebook.com/12_34', '{}', status=500)
    self.expect_urlopen('https://graph.facebook.com/56_34', '{}')
    self.mox.ReplayAll()
    self.facebook.get_activities(activity_id='12_34', user_id='56')

  def test_get_comment(self):
    self.expect_urlopen('https://graph.facebook.com/123_456',
                        json.dumps(COMMENTS[0]))
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJS[0], self.facebook.get_comment('123_456'))

  def test_get_like(self):
    self.expect_urlopen('https://graph.facebook.com/000', json.dumps(POST))
    self.mox.ReplayAll()
    self.assert_equals(LIKE_OBJS[1], self.facebook.get_like('123', '000', '683713'))

  def test_get_like_not_found(self):
    self.expect_urlopen('https://graph.facebook.com/000', json.dumps(POST))
    self.mox.ReplayAll()
    self.assert_equals(None, self.facebook.get_like('123', '000', '999'))

  def test_get_like_no_activity(self):
    self.expect_urlopen('https://graph.facebook.com/000', '{}')
    self.mox.ReplayAll()
    self.assert_equals(None, self.facebook.get_like('123', '000', '683713'))

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

  def test_picture_without_message(self):
    self.assert_equals({  # ActivityStreams
        'objectType': 'image',
        'id': tag_uri('445566'),
        'url': 'http://facebook.com/445566',
        'image': {'url': 'http://its/a/picture'},
        }, self.facebook.post_to_object({  # Facebook
          'id': '445566',
          'picture': 'http://its/a/picture',
          'source': 'https://from/a/source',
          }))

  def test_like(self):
    activity = {
        'id': tag_uri('10100747369806713'),
        'verb': 'like',
        'title': 'Unknown likes a photo.',
        'url': 'http://facebook.com/10100747369806713',
        'object': {
          'objectType': 'image',
          'id': tag_uri('214721692025931'),
          'url': 'http://instagram.com/p/eJfUHYh-x8/',
          }
        }
    post = {
        'id': '10100747369806713',
        'type': 'og.likes',
        'data': {
          'object': {
            'id': '214721692025931',
            'url': 'http://instagram.com/p/eJfUHYh-x8/',
            'type': 'instapp:photo',
            }
          }
        }
    self.assert_equals(activity, self.facebook.post_to_activity(post))

    activity.update({
        'title': 'Ryan Barrett likes a photo on Instagram.',
        'actor': ACTOR,
        'generator': {'displayName': 'Instagram', 'id': tag_uri('12402457428')},
        'url': 'http://facebook.com/212038/posts/10100747369806713',
        })
    activity['object']['author'] = ACTOR
    post.update({
        'from': USER,
        'application': {'name': 'Instagram', 'id': '12402457428'},
        })
    self.assert_equals(activity, self.facebook.post_to_activity(post))

  def test_story_as_content(self):
    self.assert_equals({
        'id': tag_uri('101007473698067'),
        'url': 'http://facebook.com/101007473698067',
        'objectType': 'note',
        'content': 'Once upon a time.',
      }, self.facebook.post_to_object({
        'id': '101007473698067',
        'story': 'Once upon a time.',
        }))

  def test_name_as_content(self):
    self.assert_equals({
        'id': tag_uri('101007473698067'),
        'url': 'http://facebook.com/101007473698067',
        'objectType': 'note',
        'content': 'Once upon a time.',
      }, self.facebook.post_to_object({
        'id': '101007473698067',
        'name': 'Once upon a time.',
        }))

  def test_gift(self):
    self.assert_equals({
        'id': tag_uri('10100747'),
        'actor': ACTOR,
        'verb': 'give',
        'title': 'Ryan Barrett gave a gift.',
        'url': 'http://facebook.com/212038/posts/10100747',
        'object': {
          'id': tag_uri('10100747'),
          'author': ACTOR,
          'url': 'http://facebook.com/212038/posts/10100747',
          'objectType': 'product',
          },
      }, self.facebook.post_to_activity({
        'id': '10100747',
        'from': USER,
        'link': '/gifts/12345',
        }))

  def test_music_listen(self):
    post = {
      'id': '10100747',
      'type': 'music.listens',
      'data': {
        'song': {
          'id': '101507345',
          'url': 'http://www.rdio.com/artist/The_Shins/album/Port_Of_Morrow_1/track/The_Rifle%27s_Spiral/',
          'type': 'music.song',
          'title': "The Rifle's Spiral",
          }
        },
      }
    activity = {
        'id': tag_uri('10100747'),
        'verb': 'listen',
        'title': "Unknown listened to The Rifle's Spiral.",
        'url': 'http://facebook.com/10100747',
        'object': {
          'id': tag_uri('101507345'),
          'url': 'http://www.rdio.com/artist/The_Shins/album/Port_Of_Morrow_1/track/The_Rifle%27s_Spiral/',
          'objectType': 'audio',
          'displayName': "The Rifle's Spiral",
          },
      }
    self.assert_equals(activity, self.facebook.post_to_activity(post))

    activity.update({
        'title': "Unknown listened to The Rifle's Spiral on Rdio.",
        'generator': {'displayName': 'Rdio', 'id': tag_uri('88888')},
        })
    activity['object'].update({
        'title': "Unknown listened to The Rifle's Spiral on Rdio.",
        'content': "Unknown listened to The Rifle's Spiral on Rdio.",
        })
    post.update({
        'from': USER,
        'application': {'name': 'Rdio', 'id': '88888'},
        })
