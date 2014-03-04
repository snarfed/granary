"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import json
import mox

import facebook
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
import source


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
  'website': 'https://snarfed.org/',
  }
ACTOR = {  # ActivityStreams
  'displayName': 'Ryan Barrett',
  'image': {'url': 'http://graph.facebook.com/snarfed.org/picture?type=large'},
  'id': tag_uri('snarfed.org'),
  'numeric_id': '212038',
  'updated': '2012-01-06T02:11:04+00:00',
  'url': 'https://snarfed.org/',
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
    'privacy': {'value': 'FRIENDS'},
    }, {
    'id': '124561947600007_672819',
    'from': {
      'name': 'Ron Ald',
      'id': '513046677'
      },
    'message': 'Foo bar!',
    'created_time': '2010-10-28T00:23:04+0000',
    'privacy': {'value': ''},  # empty means public
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
  'privacy': {'value': 'EVERYONE'},
}

EVENT = {  # Facebook; returned by /[event id] and in /[user]/events
  'id': '145304994',
  'owner': {
    'name': 'Aaron P',
    'id': '11500',
  },
  'name': 'Homebrew Website Club',
  'description': 'you should come maybe, kthxbye',
  'start_time': '2014-01-29T18:30:00-0800',
  'end_time': '2014-01-29T19:30:00-0800',
  'timezone': 'America/Los_Angeles',
  'is_date_only': False,
  'location': 'PDX',
  'venue': {
    'name': 'PDX',
  },
  'privacy': 'OPEN',
  'updated_time': '2014-01-22T01:29:15+0000',
  'rsvp_status': 'attending',
}
RSVPS = [  # Facebook; returned by /[event id]/attending (also declined, maybe)
  {'name': 'Aaron P', 'rsvp_status': 'attending', 'id': '11500'},
  {'name': 'Ryan B', 'rsvp_status': 'declined', 'id': '212038'},
  {'name': 'Foo', 'rsvp_status': 'unsure', 'id': '987'},
  {'name': 'Bar', 'rsvp_status': 'not_replied', 'id': '654'},
  ]

COMMENT_OBJS = [  # ActivityStreams
  {
    'objectType': 'comment',
    'author': {
      'id': tag_uri('212038'),
      'numeric_id': '212038',
      'displayName': 'Ryan Barrett',
      'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
      'url': 'http://facebook.com/212038',
      },
    'displayName': 'cc Sam G, Michael M',
    'content': 'cc Sam G, Michael M',
    'id': tag_uri('547822715231468_6796480'),
    'published': '2012-12-05T00:58:26+00:00',
    'url': 'http://facebook.com/547822715231468?comment_id=6796480',
    'inReplyTo': [{'id': tag_uri('547822715231468')}],
    'to': [{'objectType':'group', 'alias':'@private'}],
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
      'numeric_id': '513046677',
      'displayName': 'Ron Ald',
      'image': {'url': 'http://graph.facebook.com/513046677/picture?type=large'},
      'url': 'http://facebook.com/513046677',
      },
    'displayName': 'Foo bar!',
    'content': 'Foo bar!',
    'id': tag_uri('124561947600007_672819'),
    'published': '2010-10-28T00:23:04+00:00',
    'url': 'http://facebook.com/124561947600007?comment_id=672819',
    'inReplyTo': [{'id': tag_uri('124561947600007')}],
    'to': [{'objectType':'group', 'alias':'@public'}],
    },
]
LIKE_OBJS = [{  # ActivityStreams
    'id': tag_uri('10100176064482163_liked_by_100004'),
    'url': 'http://facebook.com/212038/posts/10100176064482163',
    'objectType': 'activity',
    'verb': 'like',
    'object': {'url': 'http://facebook.com/212038/posts/10100176064482163'},
    'author': {
      'id': tag_uri('100004'),
      'numeric_id': '100004',
      'displayName': 'Alice X',
      'url': 'http://facebook.com/100004',
      'image': {'url': 'http://graph.facebook.com/100004/picture?type=large'},
      },
    'displayName': 'Alice X likes this.',
    'content': 'likes this.',
    }, {
    'id': tag_uri('10100176064482163_liked_by_683713'),
    'url': 'http://facebook.com/212038/posts/10100176064482163',
    'objectType': 'activity',
    'verb': 'like',
    'object': {'url': 'http://facebook.com/212038/posts/10100176064482163'},
    'author': {
      'id': tag_uri('683713'),
      'numeric_id': '683713',
      'displayName': 'Bob Y',
      'url': 'http://facebook.com/683713',
      'image': {'url': 'http://graph.facebook.com/683713/picture?type=large'},
      },
    'displayName': 'Bob Y likes this.',
    'content': 'likes this.',
    },
  ]
POST_OBJ = {  # ActivityStreams
  'objectType': 'image',
  'author': {
    'id': tag_uri('212038'),
    'numeric_id': '212038',
    'displayName': 'Ryan Barrett',
    'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
    'url': 'http://facebook.com/212038',
    },
  'displayName': 'Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block...',
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
  'to':[{'objectType':'group', 'alias':'@public'}],
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
# file:///Users/ryan/docs/activitystreams_schema_spec_1.0.html#event
EVENT_OBJ = {  # ActivityStreams.
  'objectType': 'event',
  'id': tag_uri('145304994'),
  'url': 'http://facebook.com/145304994',
  'displayName': 'Homebrew Website Club',
  'author': {
    'id': tag_uri('11500'),
    'numeric_id': '11500',
    'displayName': 'Aaron P',
    'image': {'url': 'http://graph.facebook.com/11500/picture?type=large'},
    'url': 'http://facebook.com/11500',
    },
  'content': 'you should come maybe, kthxbye',
  'location': {'displayName': 'PDX'},
  'startTime': '2014-01-29T18:30:00-0800',
  'endTime': '2014-01-29T19:30:00-0800',
  'updated': '2014-01-22T01:29:15+00:00',
  'to': [{'alias': '@public', 'objectType': 'group'}],
  }
RSVP_OBJS_WITH_ID = [{
    'id': tag_uri('145304994_rsvp_11500'),
    'objectType': 'activity',
    'verb': 'rsvp-yes',
    'url': 'http://facebook.com/145304994#11500',
    'actor': {
      'displayName': 'Aaron P',
      'id': tag_uri('11500'),
      'numeric_id': '11500',
      'url': 'http://facebook.com/11500',
      'image': {'url': 'http://graph.facebook.com/11500/picture?type=large'},
      },
    'displayName': 'Aaron P is attending.',
    'content': '<data class="p-rsvp" value="yes">is attending.</data>',
    }, {
    'id': tag_uri('145304994_rsvp_212038'),
    'objectType': 'activity',
    'verb': 'rsvp-no',
    'url': 'http://facebook.com/145304994#212038',
    'actor': {
      'displayName': 'Ryan B',
      'id': tag_uri('212038'),
      'numeric_id': '212038',
      'url': 'http://facebook.com/212038',
      'image': {'url': 'http://graph.facebook.com/212038/picture?type=large'},
      },
    'displayName': 'Ryan B is not attending.',
    'content': '<data class="p-rsvp" value="no">is not attending.</data>',
    }, {
    'id': tag_uri('145304994_rsvp_987'),
    'objectType': 'activity',
    'verb': 'rsvp-maybe',
    'url': 'http://facebook.com/145304994#987',
    'actor': {
      'displayName': 'Foo',
      'id': tag_uri('987'),
      'numeric_id': '987',
      'url': 'http://facebook.com/987',
      'image': {'url': 'http://graph.facebook.com/987/picture?type=large'},
      },
    'displayName': 'Foo might attend.',
    'content': '<data class="p-rsvp" value="maybe">might attend.</data>',
    }, {
    'id': tag_uri('145304994_rsvp_654'),
    'objectType': 'activity',
    'verb': 'invite',
    'url': 'http://facebook.com/145304994#654',
    'actor': {
      'displayName': 'Aaron P',
      'id': tag_uri('11500'),
      'numeric_id': '11500',
      'url': 'http://facebook.com/11500',
      'image': {'url': 'http://graph.facebook.com/11500/picture?type=large'},
      },
    'object': {
      'objectType': 'person',
      'displayName': 'Bar',
      'id': tag_uri('654'),
      'numeric_id': '654',
      'url': 'http://facebook.com/654',
      'image': {'url': 'http://graph.facebook.com/654/picture?type=large'},
      },
    'displayName': 'Bar is invited.',
    'content': 'is invited.',
    }]
RSVP_OBJS = copy.deepcopy(RSVP_OBJS_WITH_ID)
for obj in RSVP_OBJS:
  del obj['id']
  del obj['url']
del RSVP_OBJS[3]['actor']
EVENT_OBJ_WITH_ATTENDEES = copy.deepcopy(EVENT_OBJ)
EVENT_OBJ_WITH_ATTENDEES.update({
    'attending': [RSVP_OBJS[0]['actor']],
    'notAttending': [RSVP_OBJS[1]['actor']],
    'maybeAttending': [RSVP_OBJS[2]['actor']],
    'invited': [RSVP_OBJS[3]['object']],
    })
EVENT_ACTIVITY_WITH_ATTENDEES = {  # ActivityStreams
  'id': tag_uri('145304994'),
  'url': 'http://facebook.com/145304994',
  'object': EVENT_OBJ_WITH_ATTENDEES,
}
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'id': tag_uri('10100176064482163'),
  'url': 'http://facebook.com/212038/posts/10100176064482163',
  'actor': POST_OBJ['author'],
  'object': POST_OBJ,
  'title': 'Checking another side project off my list. portablecontacts-unofficial is live! <3 Super Happy Block...',
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
 <uri>https://snarfed.org/</uri>
 <name>Ryan Barrett</name>
</author>

<link href="https://snarfed.org/" rel="alternate" type="text/html" />
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
  <title>Checking another side project off my list. portablecontacts-unofficial is live! &lt;3 Super Happy Block...</title>

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

    self.assert_equals([
        {'id': tag_uri('2'),
         'object': {'content': 'foo',
                    'id': tag_uri('2'),
                    'objectType': 'note',
                    'displayName': 'foo',
                    'url': 'http://facebook.com/2'},
         'title': 'foo',
         'url': 'http://facebook.com/2',
         'verb': 'post'},
        {'id': tag_uri('4'),
         'object': {'content': 'bar',
                    'id': tag_uri('4'),
                    'objectType': 'note',
                    'displayName': 'bar',
                    'url': 'http://facebook.com/4'},
         'title': 'bar',
         'url': 'http://facebook.com/4',
         'verb': 'post'}],
      self.facebook.get_activities())

  def test_get_activities_self(self):
    self.expect_urlopen(
      'https://graph.facebook.com/me/posts?offset=0', '{}')
    self.mox.ReplayAll()
    self.assert_equals([], self.facebook.get_activities(group_id=source.SELF))

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
    self.assert_equals([ACTIVITY], self.facebook.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_activity_id_not_found(self):
    self.expect_urlopen('https://graph.facebook.com/0', 'false')
    self.mox.ReplayAll()
    self.assert_equals([], self.facebook.get_activities(activity_id='0_0'))

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

  def test_get_activities_request_etag(self):
    self.expect_urlopen('https://graph.facebook.com/me/home?offset=0', '{}',
                        headers={'If-none-match': '"my etag"'})
    self.mox.ReplayAll()
    self.facebook.get_activities_response(etag='"my etag"')

  def test_get_activities_response_etag(self):
    self.expect_urlopen('https://graph.facebook.com/me/home?offset=0', '{}',
                        response_headers={'ETag': '"my etag"'})
    self.mox.ReplayAll()
    self.assert_equals('"my etag"',
                       self.facebook.get_activities_response()['etag'])

  def test_get_activities_304_not_modified(self):
    """Requests with matching ETags return 304 Not Modified."""
    self.expect_urlopen('https://graph.facebook.com/me/home?offset=0', '{}',
                        status=304)
    self.mox.ReplayAll()
    self.assert_equals([], self.facebook.get_activities_response()['items'])

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

  def test_get_rsvp(self):
    self.expect_urlopen('https://graph.facebook.com/145304994/invited/456',
                        json.dumps({'data': [RSVPS[0]]}))
    self.mox.ReplayAll()
    self.assert_equals(RSVP_OBJS_WITH_ID[0],
                       self.facebook.get_rsvp('123', '145304994', '456'))

  def test_get_rsvp_not_found(self):
    self.expect_urlopen('https://graph.facebook.com/000/invited/456',
                        json.dumps({'data': []}))
    self.mox.ReplayAll()
    self.assert_equals(None, self.facebook.get_rsvp('123', '000', '456'))

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

  def test_user_to_actor_url_fallback(self):
    user = copy.deepcopy(USER)
    del user['website']
    actor = copy.deepcopy(ACTOR)
    actor['url'] = user['link']
    self.assert_equals(actor, self.facebook.user_to_actor(user))

    del user['link']
    actor['url'] = 'http://facebook.com/snarfed.org'
    self.assert_equals(actor, self.facebook.user_to_actor(user))

  def test_user_to_actor_minimal(self):
    actor = self.facebook.user_to_actor({'id': '212038'})
    self.assert_equals(tag_uri('212038'), actor['id'])
    self.assert_equals('http://graph.facebook.com/212038/picture?type=large',
                       actor['image']['url'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.facebook.user_to_actor({}))

  def test_event_to_object_empty(self):
    self.assert_equals({'objectType': 'event'}, self.facebook.event_to_object({}))

  def test_event_to_object(self):
    self.assert_equals(EVENT_OBJ, self.facebook.event_to_object(EVENT))

  def test_event_to_object_with_rsvps(self):
    self.assert_equals(EVENT_OBJ_WITH_ATTENDEES,
                       self.facebook.event_to_object(EVENT, rsvps=RSVPS))

  def test_event_to_object_with_rsvps(self):
    self.assert_equals(EVENT_OBJ_WITH_ATTENDEES,
                       self.facebook.event_to_object(EVENT, rsvps=RSVPS))

  def test_event_to_activity_with_rsvps(self):
    self.assert_equals(EVENT_ACTIVITY_WITH_ATTENDEES,
                       self.facebook.event_to_activity(EVENT, rsvps=RSVPS))

  def test_rsvp_to_object(self):
    self.assert_equals(RSVP_OBJS, [self.facebook.rsvp_to_object(r) for r in RSVPS])

  def test_rsvp_to_object_event(self):
    objs = [self.facebook.rsvp_to_object(r, event=EVENT) for r in RSVPS]
    self.assert_equals(RSVP_OBJS_WITH_ID, objs)

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
        'displayName': 'Once upon a time.',
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
        'displayName': 'Once upon a time.',
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
        'displayName': "Unknown listened to The Rifle's Spiral on Rdio.",
        'content': "Unknown listened to The Rifle's Spiral on Rdio.",
        })
    post.update({
        'from': USER,
        'application': {'name': 'Rdio', 'id': '88888'},
        })

  def test_create_post(self):
    self.expect_urlopen(
      facebook.API_FEED_URL,
      json.dumps({'id': '123_456'}),
      data='message=my+msg&privacy=%7B%22value%22%3A+%22SELF%22%7D')
    self.mox.ReplayAll()

    obj = copy.deepcopy(POST_OBJ)
    obj.update({
        'objectType': 'note',
        'content': 'my msg',
        })
    self.assert_equals(
      {'id': '123_456', 'url': 'http://facebook.com/123_456', },
      self.facebook.create(obj))

    self.assert_equals('will <span class="verb">post</span> "my msg"',
                       self.facebook.preview_create(obj))

  def test_create_comment(self):
    self.expect_urlopen(
      'https://graph.facebook.com/547822715231468/comments',
      json.dumps({'id': '456_789'}),
      data='message=my+cmt&privacy=%7B%22value%22%3A+%22SELF%22%7D')
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJS[0])
    obj['content'] = 'my cmt'
    self.assert_equals({
        'id': '456_789',
        'url': 'http://facebook.com/547822715231468?comment_id=456_789',
        }, self.facebook.create(obj))

    preview = self.facebook.preview_create(obj)
    self.assertIn('<span class="verb">comment</span>', preview)
    self.assertIn('http://facebook.com/547822715231468', preview)

  def test_create_like(self):
    self.expect_urlopen('https://graph.facebook.com/10100176064482163/likes',
                        'true', data='')
    self.mox.ReplayAll()
    self.assert_equals({'url': 'http://facebook.com/212038/posts/10100176064482163'},
                       self.facebook.create(LIKE_OBJS[0]))

    preview = self.facebook.preview_create(LIKE_OBJS[0])
    self.assertIn('<span class="verb">like</span>', preview)
    self.assertIn('http://facebook.com/212038/posts/10100176064482163', preview)

  def test_create_rsvp(self):
    for endpoint in 'attending', 'declined', 'maybe':#, 'invited/567':
      self.expect_urlopen('https://graph.facebook.com/234/' + endpoint,
                          'true', data='')

    self.mox.ReplayAll()
    for rsvp in RSVP_OBJS_WITH_ID[:3]:
      rsvp = copy.deepcopy(rsvp)
      rsvp['inReplyTo'] = [{'url': 'http://facebook.com/234/'}]
      self.assert_equals({'url': 'http://facebook.com/234/'},
                          self.facebook.create(rsvp))

    preview = self.facebook.preview_create(rsvp)
    self.assertIn('<span class="verb">RSVP maybe</span>', preview)
    self.assertIn('http://facebook.com/234/', preview)

  def test_create_unsupported_type(self):
    for fn in self.facebook.create, self.facebook.preview_create:
      self.assertRaises(NotImplementedError, fn,
                        {'objectType': 'activity', 'verb': 'share'})
