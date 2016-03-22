# coding=utf-8
"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import copy
import json
import urllib
import urllib2

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import appengine_config
from granary import facebook
from granary import source


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
  'bio': 'something about me http://in.description.com',
  'website': 'https://snarfed.org/',
  }
ACTOR = {  # ActivityStreams
  'objectType': 'person',
  'displayName': 'Ryan Barrett',
  'image': {'url': 'https://graph.facebook.com/v2.2/212038/picture?type=large'},
  'id': tag_uri('snarfed.org'),
  'numeric_id': '212038',
  'updated': '2012-01-06T02:11:04+00:00',
  'url': 'https://snarfed.org',
  'urls': [{'value': 'https://snarfed.org'},
           {'value': 'http://in.description.com'},
           ],
  'username': 'snarfed.org',
  'description': 'something about me http://in.description.com',
  'location': {'id': '123', 'displayName': 'San Francisco, California'},
  }
PAGE = {  # Facebook
  'type': 'page',
  'id': '946432998716566',
  'fb_id': '946432998716566',
  'name': 'Civic Hall',
  'username': 'CivicHallNYC',
  'website': 'http://www.civichall.org',
  'about': 'Introducing Civic Hall, a new home for civic technology and innovation, launching soon in New York City. https://in.about.net',
  'link': 'https://www.facebook.com/CivicHallNYC',
  'category': 'Community organization',
  'category_list': [{'id': '2260', 'name': 'Community Organization'}],
  'cover': {
    'id': '971136052912927',
    'cover_id': '971136052912927',
    'source': 'https://fbcdn-sphotos-g-a.akamaihd.net/hphotos-ak-xap1/v/t1.0-9/s720x720/11406_971136052912927_5570221582083271369_n.png?oh=c95b8aeba2c4ec8fd83c01121429bbd6&oe=552D0DBC&__gda__=1433139526_96765d58172d428585a70e0503431a6d',
  },
  'description': 'Civic Hall, a project of Personal Democracy Media, is a vibrant, collaborative, year-round community center and beautiful http://in.description.gov event space...',
  'is_community_page': False,
  'is_published': True,
  'likes': 357,
  'location': {
    'city': 'New York',
    'country': 'United States',
    'latitude': 40.739799458026,
    'longitude': -73.99110006757,
    'state': 'NY',
  },
}
PAGE_ACTOR = {  # ActivityStreams
  'objectType': 'page',
  'id': tag_uri('CivicHallNYC'),
  'username': 'CivicHallNYC',
  'numeric_id': '946432998716566',
  'displayName': 'Civic Hall',
  'url': 'http://www.civichall.org',
  'urls': [{'value': 'http://www.civichall.org'},
           {'value': 'https://in.about.net'},
           {'value': 'http://in.description.gov'},
           ],
  'image': {'url': 'https://graph.facebook.com/v2.2/946432998716566/picture?type=large'},
  'summary': 'Introducing Civic Hall, a new home for civic technology and innovation, launching soon in New York City. https://in.about.net',
  'description': 'Civic Hall, a project of Personal Democracy Media, is a vibrant, collaborative, year-round community center and beautiful http://in.description.gov event space...',
  # 'location': {},  # TODO
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
  'actions': [{'name': 'See Original', 'link': 'http://ald.com/foobar'}]
}]
SHARE = {  # Facebook
  'id': '321_654',
  'from': {
    'id': '321',
    'name': 'Alice X'
  },
  'message': "sharer's message",
  'picture': 'https://fbcdn-sphotos-e-a.akamaihd.net/hphotos-ak-xaf1/v/t1.0-9/p100x100/777_888_999_n.jpg?oh=x&oe=y&__gda__=z_w',
  'link': 'https://www.facebook.com/sfsymphony/posts/2468',
  'name': 'San Francisco Symphony',
  'description': "original poster's message",
  'type': 'link',
  'status_type': 'shared_story',
  'created_time': '2015-01-17T05:19:19+0000',
  'updated_time': '2015-01-18T05:19:19+0000',
}
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
  'message': 'Checking another side project off my list. portablecontacts-unofficial is live! &3 Super Happy Block Party Hackathon, >\o/< Daniel M.',
  'message_tags': {
    '84': [{
        'id': '283938455011303',
        'name': 'Super Happy Block Party Hackathon',
        'type': 'event',
        'offset': 83,
        'length': 33,
        }],
    '122': [{
        'id': '789',
        'name': 'Daniel M',
        'type': 'user',
        'offset': 124,
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
# based on https://developers.facebook.com/tools/explorer?method=GET&path=10101013177735493
PHOTO = {
  'id': '222',
  'created_time': '2014-04-09T20:44:26+0000',
  'images': [{
      'source': 'https://fbcdn-sphotos-b-a.akamaihd.net/pic.jpg',
      'height': 720,
      'width': 960,
    }],
  'from': {'name': 'Ryan Barrett','id': '212038'},
  'link': 'https://www.facebook.com/photo.php?fbid=222&set=a.333.444.212038',
  'name': 'Stopped in to grab coffee and saw this table topper. Wow. Just...wow.',
  'picture': 'https://fbcdn-photos-b-a.akamaihd.net/pic_s.jpg',
  'source': 'https://fbcdn-sphotos-b-a.akamaihd.net/pic_n.jpg',
  'comments': {
    'data': [{
        'id': '222_10559',
        'created_time': '2014-04-09T20:55:49+0000',
        'from': {'name': 'Alice Alison', 'id': '333'},
        'message': 'woohoo',
      },
    ],
  },
  'likes': {'data': [{'id': '666', 'name': 'Bob Bobertson'}]}
}
PHOTO_POST = copy.deepcopy(POST)
PHOTO_POST['object_id'] = '222'  # points to PHOTO

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
  'comments': {
    'data': [{
        'id': '777',
        'created_time': '2010-10-01T00:23:04+0000',
        'from': {'name': 'Mr. Foo', 'id': '888'},
        'message': 'i hereby comment',
      }],
    },
  'picture': {
    'data': {
      'is_silhouette': False,
      'url': 'https://fbcdn-sphotos-a-a.akamaihd.net/abc/pic_n.jpg?xyz',
    }
  },
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
      'objectType': 'person',
      'id': tag_uri('212038'),
      'numeric_id': '212038',
      'displayName': 'Ryan Barrett',
      'image': {'url': 'https://graph.facebook.com/v2.2/212038/picture?type=large'},
      'url': 'https://www.facebook.com/212038',
      },
    'content': 'cc Sam G, Michael M',
    'id': tag_uri('547822715231468_6796480'),
    'fb_id': '547822715231468_6796480',
    'published': '2012-12-05T00:58:26+00:00',
    'url': 'https://www.facebook.com/547822715231468?comment_id=6796480',
    'inReplyTo': [{
      'id': tag_uri('547822715231468'),
      'url': 'https://www.facebook.com/547822715231468',
    }],
    'to': [{'objectType':'group', 'alias':'@private'}],
    'tags': [{
        'objectType': 'person',
        'id': tag_uri('221330'),
        'url': 'https://www.facebook.com/221330',
        'displayName': 'Sam G',
        'startIndex': 3,
        'length': 5,
        }, {
        'objectType': 'person',
        'id': tag_uri('695687650'),
        'url': 'https://www.facebook.com/695687650',
        'displayName': 'Michael Mandel',
        'startIndex': 10,
        'length': 9,
        }],
    },
  {
    'objectType': 'comment',
    'author': {
      'objectType': 'person',
      'id': tag_uri('513046677'),
      'numeric_id': '513046677',
      'displayName': 'Ron Ald',
      'image': {'url': 'https://graph.facebook.com/v2.2/513046677/picture?type=large'},
      'url': 'https://www.facebook.com/513046677',
      },
    'content': 'Foo bar!',
    'id': tag_uri('124561947600007_672819'),
    'fb_id': '124561947600007_672819',
    'published': '2010-10-28T00:23:04+00:00',
    'url': 'https://www.facebook.com/124561947600007?comment_id=672819',
    'inReplyTo': [{
      'id': tag_uri('124561947600007'),
      'url': 'https://www.facebook.com/124561947600007',
    }],
    'to': [{'objectType':'group', 'alias':'@public'}],
    'upstreamDuplicates': ['http://ald.com/foobar'],
  },
]
LIKE_OBJS = [{  # ActivityStreams
    'id': tag_uri('10100176064482163_liked_by_100004'),
    'url': 'https://www.facebook.com/212038/posts/10100176064482163#liked-by-100004',
    'objectType': 'activity',
    'verb': 'like',
    'object': {'url': 'https://www.facebook.com/212038/posts/10100176064482163'},
    'author': {
      'objectType': 'person',
      'id': tag_uri('100004'),
      'numeric_id': '100004',
      'displayName': 'Alice X',
      'url': 'https://www.facebook.com/100004',
      'image': {'url': 'https://graph.facebook.com/v2.2/100004/picture?type=large'},
      },
    }, {
    'id': tag_uri('10100176064482163_liked_by_683713'),
    'url': 'https://www.facebook.com/212038/posts/10100176064482163#liked-by-683713',
    'objectType': 'activity',
    'verb': 'like',
    'object': {'url': 'https://www.facebook.com/212038/posts/10100176064482163'},
    'author': {
      'objectType': 'person',
      'id': tag_uri('683713'),
      'numeric_id': '683713',
      'displayName': 'Bob Y',
      'url': 'https://www.facebook.com/683713',
      'image': {'url': 'https://graph.facebook.com/v2.2/683713/picture?type=large'},
      },
    },
  ]
SHARE_OBJ = {  # ActivityStreams
  'id': tag_uri('654'),
  'fb_id': '321_654',
  'url': 'https://www.facebook.com/321/posts/654',
  'objectType': 'activity',
  'verb': 'share',
  'object': {
    'objectType': 'article',
    'url': 'https://www.facebook.com/sfsymphony/posts/2468',
    'content': "original poster's message",
    'displayName': 'San Francisco Symphony',
    'image': {'url': 'https://fbcdn-sphotos-e-a.akamaihd.net/hphotos-ak-xaf1/v/t1.0-9/p100x100/777_888_999_n.jpg?oh=x&oe=y&__gda__=z_w',},
  },
  'author': {
    'objectType': 'person',
    'id': tag_uri('321'),
    'numeric_id': '321',
    'displayName': 'Alice X',
    'url': 'https://www.facebook.com/321',
    'image': {'url': 'https://graph.facebook.com/v2.2/321/picture?type=large'},
  },
  'displayName': "sharer's message",
  'content': "sharer's message",
  'image': {'url': 'https://fbcdn-sphotos-e-a.akamaihd.net/hphotos-ak-xaf1/v/t1.0-9/p100x100/777_888_999_n.jpg?oh=x&oe=y&__gda__=z_w',},
  'published': '2015-01-17T05:19:19+00:00',
  'updated': '2015-01-18T05:19:19+00:00',
}
POST_OBJ = {  # ActivityStreams
  'objectType': 'image',
  'author': {
    'objectType': 'person',
    'id': tag_uri('212038'),
    'numeric_id': '212038',
    'displayName': 'Ryan Barrett',
    'image': {'url': 'https://graph.facebook.com/v2.2/212038/picture?type=large'},
    'url': 'https://www.facebook.com/212038',
    },
  'content': 'Checking another side project off my list. portablecontacts-unofficial is live! &amp;3 Super Happy Block Party Hackathon, &gt;\o/&lt; Daniel M.',
  'id': tag_uri('10100176064482163'),
  'fb_id': '212038_10100176064482163',
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'url': 'https://www.facebook.com/212038/posts/10100176064482163',
  'image': {'url': 'https://fbcdn-photos-a.akamaihd.net/abc_xyz_s.jpg'},
  'attachments': [{
      'objectType': 'image',
      'url': 'http://my.link/',
      'displayName': 'my link name',
      'summary': 'my link caption',
      'content': 'my link description',
      'image': {'url': 'https://fbcdn-photos-a.akamaihd.net/abc_xyz_o.jpg'}
      }],
  'to': [{'objectType':'group', 'alias':'@public'}],
  'location': {
    'displayName': 'Lake Merced',
    'id': '113785468632283',
    'url': 'https://www.facebook.com/113785468632283',
    'latitude': 37.728193717481,
    'longitude': -122.49336423595,
    'position': '+37.728194-122.493364/',
    },
  'tags': [{
      'objectType': 'person',
      'id': tag_uri('234'),
      'url': 'https://www.facebook.com/234',
      'displayName': 'Friend 1',
      }, {
      'objectType': 'person',
      'id': tag_uri('345'),
      'url': 'https://www.facebook.com/345',
      'displayName': 'Friend 2',
      }, {
      'objectType': 'person',
      'id': tag_uri('345'),
      'url': 'https://www.facebook.com/345',
      'displayName': 'Friend 2',
      }, {
      'objectType': 'person',
      'id': tag_uri('456'),
      'url': 'https://www.facebook.com/456',
      'displayName': 'Friend 3',
      }, {
      'objectType': 'person',
      'id': tag_uri('789'),
      'url': 'https://www.facebook.com/789',
      'displayName': 'Daniel M',
      'startIndex': 134,
      'length': 8,
      }, {
      'objectType': 'event',
      'id': tag_uri('283938455011303'),
      'url': 'https://www.facebook.com/283938455011303',
      'displayName': 'Super Happy Block Party Hackathon',
      'startIndex': 87,
      'length': 33,
      },
    ] + LIKE_OBJS,
  'replies': {
    'items': COMMENT_OBJS,
    'totalItems': len(COMMENT_OBJS),
    }
  }

PHOTO_OBJ = {  # ActivityStreams
  'id': tag_uri('222'),
  'fb_id': '222',
  'fb_object_for_ids': ['212038_10100176064482163'],
  'objectType': 'note',
  'url': 'https://www.facebook.com/212038/posts/222',
  'content': 'Stopped in to grab coffee and saw this table topper. Wow. Just...wow.',
  'image': {'url': u'https://fbcdn-photos-b-a.akamaihd.net/pic_s.jpg'},
  'published': '2014-04-09T20:44:26+00:00',
  'author': POST_OBJ['author'],
  'to': [{'alias': '@public', 'objectType': 'group'}],
  'attachments': [{
    'displayName': 'Stopped in to grab coffee and saw this table topper. Wow. Just...wow.',
    'image': {'url':'https://fbcdn-photos-b-a.akamaihd.net/pic_s.jpg'},
    'objectType': 'article',
    'url': 'https://www.facebook.com/photo.php?fbid=222&set=a.333.444.212038',
  }],
  'replies': {
    'totalItems': 1,
    'items': [{
      'id': tag_uri('222_10559'),
      'fb_id': '222_10559',
      'url': 'https://www.facebook.com/222?comment_id=10559',
      'objectType': 'comment',
      'author': {
        'objectType': 'person',
        'id': tag_uri('333'),
        'numeric_id': '333',
        'displayName': 'Alice Alison',
        'image': {'url': 'https://graph.facebook.com/v2.2/333/picture?type=large'},
        'url': 'https://www.facebook.com/333',
        },
      'content': 'woohoo',
      'published': '2014-04-09T20:55:49+00:00',
      'inReplyTo': [{
        'id': tag_uri('222'),
        'url': 'https://www.facebook.com/222',
      }],
    }],
  },
  'tags':[{
    'id': tag_uri('222_liked_by_666'),
    'url': 'https://www.facebook.com/212038/posts/222#liked-by-666',
    'object': {'url': 'https://www.facebook.com/212038/posts/222'},
    'objectType': 'activity',
    'verb': 'like',
    'author': {
      'objectType': 'person',
      'id': tag_uri('666'),
      'numeric_id': '666',
      'displayName': 'Bob Bobertson',
      'url': 'https://www.facebook.com/666',
      'image': {'url': 'https://graph.facebook.com/v2.2/666/picture?type=large'},
    },
  }],
}
PHOTO_POST_OBJ = copy.deepcopy(POST_OBJ)
PHOTO_POST_OBJ['fb_object_id'] = '222'

# file:///Users/ryan/docs/activitystreams_schema_spec_1.0.html#event
EVENT_OBJ = {  # ActivityStreams.
  'objectType': 'event',
  'id': tag_uri('145304994'),
  'fb_id': '145304994',
  'url': 'https://www.facebook.com/145304994',
  'displayName': 'Homebrew Website Club',
  'author': {
    'objectType': 'person',
    'id': tag_uri('11500'),
    'numeric_id': '11500',
    'displayName': 'Aaron P',
    'image': {'url': 'https://graph.facebook.com/v2.2/11500/picture?type=large'},
    'url': 'https://www.facebook.com/11500',
    },
  'image': {'url': 'https://fbcdn-sphotos-a-a.akamaihd.net/abc/pic_n.jpg?xyz'},
  'content': 'you should come maybe, kthxbye',
  'location': {'displayName': 'PDX'},
  'startTime': '2014-01-29T18:30:00-0800',
  'endTime': '2014-01-29T19:30:00-0800',
  'updated': '2014-01-22T01:29:15+00:00',
  'to': [{'alias': '@public', 'objectType': 'group'}],
  'replies': {
    'totalItems': 1,
    'items': [{
        'objectType': 'comment',
        'author': {
          'objectType': 'person',
          'id': tag_uri('888'),
          'numeric_id': '888',
          'displayName': 'Mr. Foo',
          'url': 'https://www.facebook.com/888',
          'image': {'url': 'https://graph.facebook.com/v2.2/888/picture?type=large'},
          },
        'content': 'i hereby comment',
        'id': tag_uri('145304994_777'),
        'fb_id': '777',
        'published': '2010-10-01T00:23:04+00:00',
        'url': 'https://www.facebook.com/145304994?comment_id=777',
        'inReplyTo': [{
          'id': tag_uri('145304994'),
          'url': 'https://www.facebook.com/145304994',
        }],
    }],
  },
}
EVENT_ACTIVITY = {  # ActivityStreams
  'id': tag_uri('145304994'),
  'url': 'https://www.facebook.com/145304994',
  'object': EVENT_OBJ,
}
RSVP_OBJS_WITH_ID = [{
    'id': tag_uri('145304994_rsvp_11500'),
    'objectType': 'activity',
    'verb': 'rsvp-yes',
    'url': 'https://www.facebook.com/145304994#11500',
    'actor': {
      'objectType': 'person',
      'displayName': 'Aaron P',
      'id': tag_uri('11500'),
      'numeric_id': '11500',
      'url': 'https://www.facebook.com/11500',
      'image': {'url': 'https://graph.facebook.com/v2.2/11500/picture?type=large'},
      },
    }, {
    'id': tag_uri('145304994_rsvp_212038'),
    'objectType': 'activity',
    'verb': 'rsvp-no',
    'url': 'https://www.facebook.com/145304994#212038',
    'actor': {
      'objectType': 'person',
      'displayName': 'Ryan B',
      'id': tag_uri('212038'),
      'numeric_id': '212038',
      'url': 'https://www.facebook.com/212038',
      'image': {'url': 'https://graph.facebook.com/v2.2/212038/picture?type=large'},
      },
    }, {
    'id': tag_uri('145304994_rsvp_987'),
    'objectType': 'activity',
    'verb': 'rsvp-maybe',
    'url': 'https://www.facebook.com/145304994#987',
    'actor': {
      'objectType': 'person',
      'displayName': 'Foo',
      'id': tag_uri('987'),
      'numeric_id': '987',
      'url': 'https://www.facebook.com/987',
      'image': {'url': 'https://graph.facebook.com/v2.2/987/picture?type=large'},
      },
    }, {
    'id': tag_uri('145304994_rsvp_654'),
    'objectType': 'activity',
    'verb': 'invite',
    'url': 'https://www.facebook.com/145304994#654',
    'actor': {
      'objectType': 'person',
      'displayName': 'Aaron P',
      'id': tag_uri('11500'),
      'numeric_id': '11500',
      'url': 'https://www.facebook.com/11500',
      'image': {'url': 'https://graph.facebook.com/v2.2/11500/picture?type=large'},
      },
    'object': {
      'objectType': 'person',
      'displayName': 'Bar',
      'id': tag_uri('654'),
      'numeric_id': '654',
      'url': 'https://www.facebook.com/654',
      'image': {'url': 'https://graph.facebook.com/v2.2/654/picture?type=large'},
      },
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
  'url': 'https://www.facebook.com/145304994',
  'object': EVENT_OBJ_WITH_ATTENDEES,
}
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': '2012-03-04T18:20:37+00:00',
  'updated': '2012-03-04T19:08:16+00:00',
  'id': tag_uri('10100176064482163'),
  'fb_id': '212038_10100176064482163',
  'url': 'https://www.facebook.com/212038/posts/10100176064482163',
  'actor': POST_OBJ['author'],
  'object': POST_OBJ,
  'generator': {
    'displayName': 'Facebook for Android',
    'id': tag_uri('350685531728'),
  }
}
PHOTO_ACTIVITY = {
  'id': tag_uri('222'),
  'fb_id': '222',
  'url': 'https://www.facebook.com/212038/posts/222',
  'object': PHOTO_OBJ,
  'actor': PHOTO_OBJ['author'],
  'verb': 'post',
  'published': '2014-04-09T20:44:26+00:00',
}

FB_NOTE = {
  'id': '101007473698067',
  'type': 'note',
}
FB_CREATED_NOTE = {
  'id': '101007473698067',
  'type': 'status',
  'status_type': 'created_note',
}
FB_NOTE_ACTIVITY = {
  'id': tag_uri('101007473698067'),
  'fb_id': '101007473698067',
  'url': 'https://www.facebook.com/101007473698067',
  'verb': 'post',
  'object': {
    'id': tag_uri('101007473698067'),
    'fb_id': '101007473698067',
    'url': 'https://www.facebook.com/101007473698067',
    'objectType': 'article',
  },
}
FB_LINK = {
  'id': '555',
  'status_type': 'shared_story',
  'type': 'link',
  'link': 'http://a/link',
}
FB_LINK_ACTIVITY = {
  'id': tag_uri('555'),
  'fb_id': '555',
  'url': 'https://www.facebook.com/555',
  'verb': 'post',
  'object': {
    'id': tag_uri('555'),
    'fb_id': '555',
    'url': 'https://www.facebook.com/555',
    'objectType': 'note',
    'attachments': [{
      'objectType': 'article',
      'url': 'http://a/link',
    }],
  },
}
FB_NEWS_PUBLISH = {
  'id': '555',
  'type': 'news.publishes',
  'no_feed_story': False,
  'photos': ['10207402663015202'],
  'publish_time': '2015-09-20T12:52:56+0000',
  'data': {
    'article': {
      'id': '881901168553792',
      'title': 'Keine Hektik',
      'type': 'article',
      'url': 'http://drikkes.com/?p=9965'
    }
  },
  'application': {}, # ...
}
FB_NEWS_PUBLISH_ACTIVITY =  {
  'id': 'tag:facebook.com:555',
  'fb_id': '555',
  'verb': 'post',
  'object': {
    'id': 'tag:facebook.com:555',
    'fb_id': '555',
    'objectType': 'note',
    'url': 'https://www.facebook.com/555',
  },
  'url': 'https://www.facebook.com/555',
}
ALBUM = {  # Facebook
  'id': '1520022318322674',
  'name': 'Bridgy Photos',
  'can_upload': True,
  'count': 2,
  'cover_photo': '1520050698319836',
  'from': {
    'name': u'Snoøpy Barrett',
    'id': '1407574399567467'
  },
  'link': 'https://www.facebook.com/album.php?fbid=1520022318322674&id=1407574399567467&aid=1073741827',
  'privacy': 'everyone',
  'type': 'app',
  'created_time': '2015-11-16T22:10:42+0000',
  'updated_time': '2015-11-19T02:34:16+0000',
}
ALBUM_OBJ = {  # ActivityStreams
  'id': tag_uri('1520022318322674'),
  'fb_id': '1520022318322674',
  'objectType': 'collection',
  'displayName': 'Bridgy Photos',
  'totalItems': 2,
  'author': {
    'objectType': 'person',
    'id': tag_uri('1407574399567467'),
    'numeric_id': '1407574399567467',
    'displayName': u'Snoøpy Barrett',
    'image': {'url': 'https://graph.facebook.com/v2.2/1407574399567467/picture?type=large'},
    'url': 'https://www.facebook.com/1407574399567467',
    },
  'url': 'https://www.facebook.com/album.php?fbid=1520022318322674&id=1407574399567467&aid=1073741827',
  'to': [{'objectType':'group', 'alias':'@public'}],
  'published': '2015-11-16T22:10:42+00:00',
  'updated': '2015-11-19T02:34:16+00:00',
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
<title>User feed for Ryan Barrett</title>

<subtitle>something about me http://in.description.com</subtitle>

<logo>https://graph.facebook.com/v2.2/212038/picture?type=large</logo>
<updated>2012-03-04T18:20:37+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://snarfed.org</uri>
 <name>Ryan Barrett</name>
</author>

<link href="https://snarfed.org" rel="alternate" type="text/html" />
<link rel="avatar" href="https://graph.facebook.com/v2.2/212038/picture?type=large" />
<link href="%(request_url)s" rel="self" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://www.facebook.com/212038</uri>
 <name>Ryan Barrett</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/image</activity:object-type>

  <id>https://www.facebook.com/212038/posts/10100176064482163</id>
  <title>Checking another side project off my list. portablecontacts-unofficial is live! &amp;3 Super Happy Block...</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

Checking another side project off my list. portablecontacts-unofficial is live! &amp;3 <a href="https://www.facebook.com/283938455011303">Super Happy Block Party Hackathon</a>, &gt;\o/&lt; <a href="https://www.facebook.com/789">Daniel M</a>.
<p>
<a class="link" href="http://my.link/">
<img class="thumbnail" src="https://fbcdn-photos-a.akamaihd.net/abc_xyz_o.jpg" alt="my link name" />
<span class="name">my link name</span>
</a>
<span class="summary">my link caption</span>
</p>
<span class="p-location h-card">
  <a class="p-name u-url" href="https://www.facebook.com/113785468632283">Lake Merced</a>

</span>

  </div>
  </content>

  <link rel="alternate" type="text/html" href="https://www.facebook.com/212038/posts/10100176064482163" />
  <link rel="ostatus:conversation" href="https://www.facebook.com/212038/posts/10100176064482163" />

    <link rel="ostatus:attention" href="https://www.facebook.com/234" />
    <link rel="mentioned" href="https://www.facebook.com/234" />

    <a href="https://www.facebook.com/234">Friend 1</a>

    <link rel="ostatus:attention" href="https://www.facebook.com/345" />
    <link rel="mentioned" href="https://www.facebook.com/345" />

    <a href="https://www.facebook.com/345">Friend 2</a>

    <link rel="ostatus:attention" href="https://www.facebook.com/345" />
    <link rel="mentioned" href="https://www.facebook.com/345" />

    <a href="https://www.facebook.com/345">Friend 2</a>

    <link rel="ostatus:attention" href="https://www.facebook.com/456" />
    <link rel="mentioned" href="https://www.facebook.com/456" />

    <a href="https://www.facebook.com/456">Friend 3</a>

    <link rel="ostatus:attention" href="https://www.facebook.com/789" />
    <link rel="mentioned" href="https://www.facebook.com/789" />

    <link rel="ostatus:attention" href="https://www.facebook.com/283938455011303" />
    <link rel="mentioned" href="https://www.facebook.com/283938455011303" />

  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T19:08:16+00:00</updated>

    <georss:point>37.7281937175 -122.493364236</georss:point>

    <georss:featureName>Lake Merced</georss:featureName>

  <link rel="self" type="application/atom+xml" href="https://www.facebook.com/212038/posts/10100176064482163" />
</entry>

</feed>
"""


class FacebookTest(testutil.HandlerTest):

  def setUp(self):
    super(FacebookTest, self).setUp()
    self.fb = facebook.Facebook()
    self.batch = []
    self.batch_responses = []

  def expect_urlopen(self, url, response=None, **kwargs):
    if not url.startswith('http'):
      url = facebook.API_BASE + url
    return super(FacebookTest, self).expect_urlopen(
      url, response=json.dumps(response), **kwargs)

  def expect_batch_req(self, url, response, status=200, headers={},
                       response_headers=None):
    batch.append({
      'method': 'GET',
      'relative_url': url,
      'headers': [{'name': n, 'value': v} for n, v in headers.items()],
    })
    batch_responses.append(util.trim_nulls({
      'code': status,
      'body': json.dumps(response),
      'headers': response_headers,
    }))

  def replay_batch(self):
    self.expect_urlopen(
      facebook.API_BASE,
      data='batch=' + json.dumps(batch, separators=(',', ':')),
      response=batch_responses)
    self.mox.ReplayAll()

  def test_get_actor(self):
    self.expect_urlopen('foo', USER)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.fb.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_urlopen('me', USER)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.fb.get_actor())

  def test_get_activities_defaults(self):
    resp = {'data': [
          {'id': '1_2', 'message': 'foo'},
          {'id': '3_4', 'message': 'bar'},
          ]}
    self.expect_urlopen('me/home?offset=0', resp)
    self.mox.ReplayAll()

    self.assert_equals([
        {'id': tag_uri('2'),
         'fb_id': '1_2',
         'object': {'content': 'foo',
                    'id': tag_uri('2'),
                    'fb_id': '1_2',
                    'objectType': 'note',
                    'url': 'https://www.facebook.com/1/posts/2'},
         'url': 'https://www.facebook.com/1/posts/2',
         'verb': 'post'},
        {'id': tag_uri('4'),
         'fb_id': '3_4',
         'object': {'content': 'bar',
                    'id': tag_uri('4'),
                    'fb_id': '3_4',
                    'objectType': 'note',
                    'url': 'https://www.facebook.com/3/posts/4'},
         'url': 'https://www.facebook.com/3/posts/4',
         'verb': 'post'}],
      self.fb.get_activities())

  def test_get_activities_fetch_shares(self):
    self.expect_urlopen('me/home?offset=0',
                        {'data': [
                          {'id': '1_2', 'message': 'foo'},
                          {'id': '3_4', 'message': 'bar'},
                        ]})
    self.expect_urlopen('sharedposts?ids=2,4', {
        '2': {'data': [SHARE, SHARE]},
        '4': {'data': []},
      })
    self.mox.ReplayAll()

    got = self.fb.get_activities(fetch_shares=True)
    self.assert_equals([SHARE_OBJ, SHARE_OBJ], got[0]['object']['tags'])
    self.assertNotIn('tags', got[1])
    self.assertNotIn('tags', got[1]['object'])

  def test_get_activities_home_returns_bool(self):
    self.expect_urlopen('me/home?offset=0', True)
    # self.expect_urlopen('me/photos/uploaded', [])
    # self.expect_urlopen('me/events', {})
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities())

  def test_get_activities_fetch_shares_returns_list(self):
    self.expect_urlopen('me/home?offset=0', {'data': [{'id': '1_2'}]})
    self.expect_urlopen('sharedposts?ids=2', ['asdf'])
    self.mox.ReplayAll()

    got = self.fb.get_activities(fetch_shares=True)
    self.assertNotIn('tags', got[0]['object'])
    self.assertNotIn('tags', got[0])

  def test_get_activities_fetch_shares_returns_boolean(self):
    self.expect_urlopen('me/home?offset=0', {'data': [{'id': '1_2'}]})
    self.expect_urlopen('sharedposts?ids=2', {'2': False})
    self.mox.ReplayAll()

    got = self.fb.get_activities(fetch_shares=True)
    self.assertNotIn('tags', got[0]['object'])
    self.assertNotIn('tags', got[0])

  def test_get_activities_self_empty(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', {})
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(group_id=source.SELF))

  def test_get_activities_self_photo_and_event(self):
    self.expect_urlopen('me/feed?offset=0', {'data': [PHOTO_POST]})
    self.expect_urlopen('me/photos/uploaded', {'data': [PHOTO]})
    self.expect_urlopen('me/events', {'data': [EVENT]})
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.expect_urlopen(facebook.API_EVENT_RSVPS % '145304994', {'data': RSVPS})

    self.mox.ReplayAll()
    self.assert_equals(
      [EVENT_ACTIVITY_WITH_ATTENDEES, PHOTO_ACTIVITY],
      self.fb.get_activities(group_id=source.SELF, fetch_events=True))

  def test_get_activities_self_merge_photos(self):
    """
    https://github.com/snarfed/bridgy/issues/562
    """
    self.expect_urlopen('me/feed?offset=0', {'data': [
      {'id': '1', 'object_id': '11',   # has photo but no album
       'privacy': {'value': 'EVERYONE'}},
      {'id': '3', 'object_id': '33'},  # has photo but no album
      {'id': '5', 'object_id': '55'},  # no photo
      {'id': '6', 'object_id': '66',   # this is a consolidated post
       'privacy': {'value': 'CUSTOM'}},
      {'id': '7', 'object_id': '77',   # ditto, and photo has no album
       'privacy': {'value': 'CUSTOM'}},
    ]})
    self.expect_urlopen('me/photos/uploaded', {'data': [
      {'id': '11'},
      {'id': '22', 'album': '222'},  # no matching post
      {'id': '33', 'album': '333'},  # no matching album
      {'id': '44', 'album': '444'},  # no matching post or album
      {'id': '66', 'album': '666'},  # consolidated posts...
      {'id': '77'},
    ]})
    self.expect_urlopen('me/albums', {'data': [
      {'id': '222', 'privacy': 'friends'},   # no post
      {'id': '666', 'privacy': 'everyone'},  # consolidated post
    ]})

    self.mox.ReplayAll()
    self.assert_equals([
      {'fb_id': '11', 'to': [{'objectType':'group', 'alias':'@public'}]},
      {'fb_id': '22', 'to': [{'objectType':'group', 'alias':'@private'}]},
      {'fb_id': '33'},
      {'fb_id': '44'},
      {'fb_id': '5'},
      {'fb_id': '66', 'to': [{'objectType':'group', 'alias':'@public'}]},
      {'fb_id': '77', 'to': [{'objectType': 'unknown'}]},
    ], [{k: v for k, v in activity['object'].items() if k in ('fb_id', 'to')}
        for activity in self.fb.get_activities(group_id=source.SELF)])

  def test_get_activities_self_photos_returns_list(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', [])
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(group_id=source.SELF))

  def test_get_activities_self_owned_event_rsvps(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('me/events', {'data': [EVENT]})
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.expect_urlopen(facebook.API_EVENT_RSVPS % '145304994', {'data': RSVPS})

    self.mox.ReplayAll()
    self.assert_equals([EVENT_ACTIVITY_WITH_ATTENDEES], self.fb.get_activities(
      group_id=source.SELF, fetch_events=True, event_owner_id=EVENT['owner']['id']))

  def test_get_activities_self_unowned_event_no_rsvps(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('me/events', {'data': [EVENT]})
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)

    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(
      group_id=source.SELF, fetch_events=True, event_owner_id='xyz'))

  def test_get_activities_self_event_400s(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('me/events', {'data': [EVENT]})
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT, status=400)

    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(
      group_id=source.SELF, fetch_events=True))

  def test_get_activities_self_event_rsvps_400s(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('me/events', {'data': [EVENT]})
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.expect_urlopen(facebook.API_EVENT_RSVPS % '145304994', {'data': RSVPS},
                        status=400)

    self.mox.ReplayAll()
    self.assert_equals([EVENT_ACTIVITY], self.fb.get_activities(
      group_id=source.SELF, fetch_events=True))

  def test_get_activities_self_events_returns_list(self):
    self.expect_urlopen('me/feed?offset=0', {})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('me/events', [])
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(
      group_id=source.SELF, fetch_events=True))

  def test_get_activities_passes_through_access_token(self):
    self.expect_urlopen('me/home?offset=0&access_token=asdf', {"id": 123})
    self.mox.ReplayAll()

    self.fb = facebook.Facebook(access_token='asdf')
    self.fb.get_activities()

  def test_get_activities_activity_id_overrides_others(self):
    self.expect_urlopen('123_000', POST)
    self.expect_urlopen('000', POST)
    self.mox.ReplayAll()

    # activity id overrides user, group, app id and ignores startIndex and count
    self.assert_equals([ACTIVITY], self.fb.get_activities(
        user_id='123', group_id='456', app_id='789', activity_id='000',
        start_index=3, count=6))

  def test_get_activities_activity_id_not_found(self):
    for id in '0_0', '0':
      self.expect_urlopen('%s' % id, {
          'error': {
            'message': '(#803) Some of the aliases you requested do not exist: 0',
            'type': 'OAuthException',
            'code': 803
          }
        })
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(activity_id='0_0'))

  def test_get_activities_start_index_and_count(self):
    self.expect_urlopen('me/home?offset=3&limit=5', {})
    self.mox.ReplayAll()
    self.fb.get_activities(start_index=3, count=5)

  def test_get_activities_activity_id_with_user_id(self):
    """Check that we fetch both forms of the id and merge the results."""
    self.expect_urlopen('12_34', {'id': '123'})
    self.expect_urlopen('34', {'message': 'x'})
    self.mox.ReplayAll()

    obj = self.fb.get_activities(activity_id='34', user_id='12')[0]['object']
    self.assertEquals('123', obj['fb_id'])
    self.assertEquals('x', obj['content'])

  def test_get_activities_activity_id_with_prefix(self):
    """Check that we fetch both forms of the id and merge the results."""
    self.expect_urlopen('12_34', {'id': '123'})
    self.expect_urlopen('34', {'message': 'x'})
    self.mox.ReplayAll()

    obj = self.fb.get_activities(activity_id='12_34')[0]['object']
    self.assertEquals('123', obj['fb_id'])
    self.assertEquals('x', obj['content'])

  def test_get_activities_activity_id_fallback_to_strip_prefix(self):
    self.expect_urlopen('12_34', {}, status=404)
    self.expect_urlopen('34', {})
    self.mox.ReplayAll()
    self.fb.get_activities(activity_id='12_34')

  def test_get_activities_activity_id_fallback_to_user_id_param(self):
    self.expect_urlopen('12_34', {}, status=400)
    self.expect_urlopen('56_34', {}, status=500)
    self.expect_urlopen('34', {})
    self.mox.ReplayAll()
    self.fb.get_activities(activity_id='12_34', user_id='56')

  def test_get_activities_request_etag(self):
    self.expect_urlopen('me/home?offset=0', {},
                        headers={'If-none-match': '"my etag"'})
    self.mox.ReplayAll()
    self.fb.get_activities_response(etag='"my etag"')

  def test_get_activities_response_etag(self):
    self.expect_urlopen('me/home?offset=0', {},
                        response_headers={'ETag': '"my etag"'})
    self.mox.ReplayAll()
    self.assert_equals('"my etag"',
                       self.fb.get_activities_response()['etag'])

  def test_get_activities_304_not_modified(self):
    """Requests with matching ETags return 304 Not Modified."""
    self.expect_urlopen('me/home?offset=0', {}, status=304)
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities_response()['items'])

  def test_get_activities_sharedposts_400(self):
    self.expect_urlopen('me/home?offset=0',
                        {'data': [{'id': '1_2'}, {'id': '3_4'}]})
    self.expect_urlopen('sharedposts?ids=2,4', status=400)
    self.mox.ReplayAll()

    got = self.fb.get_activities(fetch_shares=True)
    for activity in got:
      self.assertNotIn('tags', activity)
      self.assertNotIn('tags', activity['object'])

  def test_get_activities_too_many_ids(self):
    ids = ['1', '2', '3', '4', '5']
    self.expect_urlopen('me/home?offset=0', {'data': [{'id': id} for id in ids]})
    self.expect_urlopen('sharedposts?ids=1,2', {'1': {'data': [{'id': '222'}]}})
    self.expect_urlopen('sharedposts?ids=3,4', {'2': {'data': [{'id': '444'}]}})
    self.expect_urlopen('sharedposts?ids=5', {})
    self.expect_urlopen('comments?filter=stream&ids=1,2',
                        {'1': {'data': [{'id': '111'}]}})
    self.expect_urlopen('comments?filter=stream&ids=3,4',
                        {'1': {'data': [{'id': '333'}]}})
    self.expect_urlopen('comments?filter=stream&ids=5', {})
    self.mox.ReplayAll()

    try:
      orig_max_ids = facebook.MAX_IDS
      facebook.MAX_IDS = 2
      activities = self.fb.get_activities(fetch_replies=True, fetch_shares=True)
    finally:
      facebook.MAX_IDS = orig_max_ids

    self.assert_equals(ids, [a['fb_id'] for a in activities])

    obj0 = activities[0]['object']
    self.assert_equals(['111', '333'], [r['fb_id'] for r in obj0['replies']['items']])
    self.assert_equals(['222'], [t['fb_id'] for t in obj0['tags']])

    obj1 = activities[1]['object']
    self.assert_equals(['444'], [t['fb_id'] for t in obj1['tags']])

  def test_get_event(self):
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.expect_urlopen(facebook.API_EVENT_RSVPS % '145304994', {'data': RSVPS})
    self.mox.ReplayAll()
    self.assert_equals(EVENT_ACTIVITY_WITH_ATTENDEES,
                       self.fb.get_event('145304994'))

  def test_get_event_user_id_not_owner(self):
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.mox.ReplayAll()
    got = self.fb.get_event('145304994', owner_id='xyz')
    self.assert_equals(None, got)

  def test_get_event_user_id_owner(self):
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.expect_urlopen(facebook.API_EVENT_RSVPS % '145304994', {})
    self.mox.ReplayAll()
    got = self.fb.get_event('145304994', owner_id=EVENT['owner']['id'])
    self.assert_equals(EVENT_ACTIVITY, got)

  def test_get_event_returns_list(self):
    self.expect_urlopen(facebook.API_EVENT % '145304994', ['xyz'])
    self.mox.ReplayAll()
    self.assertIsNone(self.fb.get_event('145304994'))

  def test_get_activities_group_excludes_shared_story(self):
    self.expect_urlopen(
      'me/home?offset=0',
      {'data': [{'id': '1_2', 'status_type': 'shared_story'}]})
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities())

  def test_get_activities_self_includes_shared_story(self):
    post = {'id': '1', 'status_type': 'shared_story'}
    activity = self.fb.post_to_activity(post)

    self.expect_urlopen('me/feed?offset=0', {'data': [post]})
    self.expect_urlopen('me/photos/uploaded', {})
    self.mox.ReplayAll()
    self.assert_equals([activity], self.fb.get_activities(group_id=source.SELF))

  def test_get_activities_fetch_replies(self):
    post2 = copy.deepcopy(POST)
    post2['id'] = '222'
    post3 = copy.deepcopy(POST)
    post3['id'] = '333'
    self.expect_urlopen('me/home?offset=0',
                        {'data': [POST, post2, post3]})
    self.expect_urlopen('comments?filter=stream&ids=10100176064482163,222,333',
      {'222': {'data': [{'id': '777', 'message': 'foo'},
                        {'id': '888', 'message': 'bar'}]},
       '333': {'data': [{'id': '999', 'message': 'baz'},
                        {'id': COMMENTS[0]['id'], 'message': 'omitted!'}]},
      })
    self.mox.ReplayAll()

    activities = self.fb.get_activities(fetch_replies=True)
    base_ids = ['547822715231468_6796480', '124561947600007_672819']
    self.assert_equals([base_ids, base_ids + ['777', '888'], base_ids + ['999']],
                       [[c['fb_id'] for c in a['object']['replies']['items']]
                        for a in activities])

  def test_get_activities_fetch_replies_400s(self):
    post = copy.deepcopy(POST)
    del post['comments']
    self.expect_urlopen('me/home?offset=0', {'data': [post]})
    self.expect_urlopen('comments?filter=stream&ids=10100176064482163', status=400)
    self.mox.ReplayAll()

    activity = copy.deepcopy(ACTIVITY)
    del activity['object']['replies']
    self.assert_equals([activity], self.fb.get_activities(fetch_replies=True))

  def test_get_activities_skips_extras_if_no_posts(self):
    self.expect_urlopen('me/feed?offset=0', {'data': []})
    self.expect_urlopen('me/photos/uploaded', {})
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_activities(
      group_id=source.SELF, fetch_shares=True, fetch_replies=True))

  def test_get_activities_extras_skips_notes_includes_links(self):
    # first call returns just notes
    self.expect_urlopen('me/feed?offset=0',
                        {'data': [FB_NOTE, FB_CREATED_NOTE]})
    self.expect_urlopen('me/photos/uploaded', {})

    # second call returns notes and link
    self.expect_urlopen('me/feed?offset=0',
                        {'data': [FB_NOTE, FB_CREATED_NOTE, FB_LINK]})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('sharedposts?ids=555', [])
    self.expect_urlopen('comments?filter=stream&ids=555', {})

    self.mox.ReplayAll()

    for expected in ([FB_NOTE_ACTIVITY, FB_NOTE_ACTIVITY],
                     [FB_NOTE_ACTIVITY, FB_NOTE_ACTIVITY, FB_LINK_ACTIVITY]):
      self.assert_equals(expected, self.fb.get_activities(
        group_id=source.SELF, fetch_shares=True, fetch_replies=True))

  def test_get_activities_matches_extras_with_correct_activity(self):
    self.expect_urlopen('me/feed?offset=0', {'data': [POST]})
    self.expect_urlopen('me/photos/uploaded', {})
    self.expect_urlopen('me/events', {'data': [EVENT]})
    self.expect_urlopen(facebook.API_EVENT % '145304994', EVENT)
    self.expect_urlopen(facebook.API_EVENT_RSVPS % '145304994', {})
    self.expect_urlopen('sharedposts?ids=10100176064482163',
                        {'10100176064482163': {'data': [SHARE]}})
    self.expect_urlopen('comments?filter=stream&ids=10100176064482163',
                        {'10100176064482163': {'data': COMMENTS}})

    self.mox.ReplayAll()
    activity = copy.deepcopy(ACTIVITY)
    activity['object']['tags'].append(SHARE_OBJ)
    self.assert_equals([EVENT_ACTIVITY, activity], self.fb.get_activities(
      group_id=source.SELF, fetch_events=True, fetch_shares=True, fetch_replies=True))

  def test_get_activities_self_fetch_news(self):
    self.expect_urlopen('me/feed?offset=0', {'data': [POST]})
    self.expect_urlopen('me/news.publishes', {'data': [FB_NEWS_PUBLISH]})
    self.expect_urlopen('me/photos/uploaded', {})
    # should only fetch sharedposts for POST, not FB_NEWS_PUBLISH
    self.expect_urlopen('sharedposts?ids=10100176064482163', {})

    self.mox.ReplayAll()
    got = self.fb.get_activities(group_id=source.SELF, fetch_news=True,
                                 fetch_shares=True)
    self.assert_equals([ACTIVITY, FB_NEWS_PUBLISH_ACTIVITY], got)

  def test_get_activities_canonicalizes_ids_with_colons(self):
    """https://github.com/snarfed/bridgy/issues/305"""
    # translate post id and comment ids to same ids in new colon-based format
    post = copy.deepcopy(POST)
    activity = copy.deepcopy(ACTIVITY)
    post['id'] = activity['object']['fb_id'] = activity['fb_id'] = \
        '212038:10100176064482163:11'

    reply = activity['object']['replies']['items'][0]
    post['comments']['data'][0]['id'] = reply['fb_id'] = \
        '12345:547822715231468:987_6796480'
    reply['url'] = 'https://www.facebook.com/12345/posts/547822715231468?comment_id=6796480'
    reply['inReplyTo'][0]['url'] = 'https://www.facebook.com/12345/posts/547822715231468'

    self.expect_urlopen('me/home?offset=0', {'data': [post]})
    self.mox.ReplayAll()

    self.assert_equals([activity], self.fb.get_activities())

  def test_get_activities_ignores_bad_comment_ids(self):
    """https://github.com/snarfed/bridgy/issues/305"""
    bad_post = copy.deepcopy(POST)
    bad_post['id'] = '90^90'

    post_with_bad_comment = copy.deepcopy(POST)
    post_with_bad_comment['comments']['data'].append(
      {'id': '12^34', 'message': 'bad to the bone'})

    self.expect_urlopen('me/home?offset=0', {'data': [bad_post, post_with_bad_comment]})
    self.mox.ReplayAll()

    # should only get the base activity, without the extra comment, and not the
    # bad activity at all
    self.assert_equals([ACTIVITY], self.fb.get_activities())

  def test_get_activities_search_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.fb.get_activities(search_query='foo')

  def test_get_comment(self):
    self.expect_urlopen(
      '123_456?fields=id,message,from,created_time,message_tags,parent',
      COMMENTS[0])
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJS[0], self.fb.get_comment('123_456'))

  def test_get_comment_activity_author_id(self):
    self.expect_urlopen(
      '123_456?fields=id,message,from,created_time,message_tags,parent',
      COMMENTS[0])
    self.mox.ReplayAll()

    obj = self.fb.get_comment('123_456', activity_author_id='my-author')
    self.assert_equals(
      'https://www.facebook.com/my-author/posts/547822715231468?comment_id=6796480',
      obj['url'])

  def test_get_comment_400s_id_with_underscore(self):
    self.expect_urlopen(
      '123_456_789?fields=id,message,from,created_time,message_tags,parent',
      {}, status=400)
    self.expect_urlopen(
      '789?fields=id,message,from,created_time,message_tags,parent',
      COMMENTS[0])
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJS[0], self.fb.get_comment('123_456_789'))

  def test_get_comment_400s_id_without_underscore(self):
    self.expect_urlopen(
      '123?fields=id,message,from,created_time,message_tags,parent',
      {}, status=400)
    self.mox.ReplayAll()
    self.assertRaises(urllib2.HTTPError, self.fb.get_comment, '123')

  def test_get_share(self):
    self.expect_urlopen('123', SHARE)
    self.mox.ReplayAll()
    self.assert_equals(SHARE_OBJ, self.fb.get_share('', '', '123'))

  def test_get_share_400s(self):
    self.expect_urlopen('123', {}, status=400)
    self.mox.ReplayAll()
    self.assertIsNone(self.fb.get_share('', '', '123'))

  def test_get_share_500s(self):
    self.expect_urlopen('123', {}, status=500)
    self.mox.ReplayAll()
    self.assertRaises(urllib2.HTTPError, self.fb.get_share, '', '', '123')

  def test_get_like(self):
    self.expect_urlopen('123_000', POST)
    self.expect_urlopen('000', POST)
    self.mox.ReplayAll()
    self.assert_equals(LIKE_OBJS[1], self.fb.get_like('123', '000', '683713'))

  def test_get_like_not_found(self):
    self.expect_urlopen('123_000', POST)
    self.expect_urlopen('000', POST)
    self.mox.ReplayAll()
    self.assert_equals(None, self.fb.get_like('123', '000', '999'))

  def test_get_like_no_activity(self):
    self.expect_urlopen('123_000', {})
    self.expect_urlopen('000', {})
    self.mox.ReplayAll()
    self.assert_equals(None, self.fb.get_like('123', '000', '683713'))

  def test_get_rsvp(self):
    self.expect_urlopen('145304994/invited/456', {'data': [RSVPS[0]]})
    self.mox.ReplayAll()
    self.assert_equals(RSVP_OBJS_WITH_ID[0],
                       self.fb.get_rsvp('123', '145304994', '456'))

  def test_get_rsvp_not_found(self):
    self.expect_urlopen('000/invited/456', {'data': []})
    self.mox.ReplayAll()
    self.assert_equals(None, self.fb.get_rsvp('123', '000', '456'))

  def test_get_albums_empty(self):
    self.expect_urlopen('000/albums', {'data': []})
    self.mox.ReplayAll()
    self.assert_equals([], self.fb.get_albums(user_id='000'))

  def test_get_albums(self):
    album_2 = copy.deepcopy(ALBUM)
    album_2['id'] = '2'
    album_2_obj = copy.deepcopy(ALBUM_OBJ)
    album_2_obj.update({
      'id': tag_uri('2'),
      'fb_id': '2',
    })

    self.expect_urlopen('me/albums', {'data': [ALBUM, album_2]})
    self.mox.ReplayAll()
    self.assert_equals([ALBUM_OBJ, album_2_obj], self.fb.get_albums())

  def test_post_to_activity_full(self):
    self.assert_equals(ACTIVITY, self.fb.post_to_activity(POST))

  def test_post_to_activity_minimal(self):
    # just test that we don't crash
    self.fb.post_to_activity({'id': '123_456', 'message': 'asdf'})

  def test_post_to_activity_empty(self):
    # just test that we don't crash
    self.fb.post_to_activity({})

  def test_post_to_activity_unknown_id_format(self):
    """See https://github.com/snarfed/bridgy/issues/305"""
    self.assert_equals({}, self.fb.post_to_activity({'id': '123^456'}))

  def test_post_to_object_full(self):
    self.assert_equals(POST_OBJ, self.fb.post_to_object(POST))

  def test_post_to_object_minimal(self):
    # just test that we don't crash
    self.fb.post_to_object({'id': '123_456', 'message': 'asdf'})

  def test_post_to_object_empty(self):
    self.assert_equals({}, self.fb.post_to_object({}))

  def test_post_to_object_expands_relative_links(self):
    post = copy.copy(POST)
    post['link'] = '/relative/123'

    post_obj = copy.deepcopy(POST_OBJ)
    post_obj['attachments'][0]['url'] = 'https://www.facebook.com/relative/123'
    self.assert_equals(post_obj, self.fb.post_to_object(post))

  def test_post_to_object_colon_id(self):
    """See https://github.com/snarfed/bridgy/issues/305"""
    id = '12:34:56'
    self.assert_equals({
      'objectType': 'note',
      'id': tag_uri('34'),
      'fb_id': id,
      'content': 'asdf',
      'url': 'https://www.facebook.com/12/posts/34',
    }, self.fb.post_to_object({
      'id': id,
      'message': 'asdf',
    }))

  def test_post_to_object_unknown_id_format(self):
    """See https://github.com/snarfed/bridgy/issues/305"""
    self.assert_equals({}, self.fb.post_to_object({'id': '123^456'}))

  def test_post_to_object_with_comment_unknown_id_format(self):
    """See https://github.com/snarfed/bridgy/issues/305"""
    post = copy.deepcopy(POST)
    post['comments']['data'].append({'id': '123 456^789'})
    self.assert_equals(POST_OBJ, self.fb.post_to_object(post))

  def test_post_to_object_message_tags_list(self):
    post = copy.copy(POST)
    tags = post['message_tags'].values()
    post['message_tags'] = tags[0] + tags[1]  # both lists
    self.assert_equals(POST_OBJ, self.fb.post_to_object(post))

  def test_post_to_object_with_only_count_of_likes(self):
    post = copy.copy(POST)
    post['likes'] = 5  # count instead of actual like objects
    obj = copy.copy(POST_OBJ)
    obj['tags'] = [t for t in obj['tags'] if t.get('verb') != 'like']
    self.assert_equals(obj, self.fb.post_to_object(post))

  def test_post_to_object_photo_post(self):
    self.assert_equals(PHOTO_POST_OBJ, self.fb.post_to_object(PHOTO_POST))

  def test_comment_to_object_full(self):
    for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
      self.assert_equals(obj, self.fb.comment_to_object(cmt))

  def test_comment_to_object_minimal(self):
    # just test that we don't crash
    self.fb.comment_to_object({'id': '123_456_789', 'message': 'asdf'})

  def test_comment_to_object_empty(self):
    self.assert_equals({}, self.fb.comment_to_object({}))

  def test_comment_to_object_post_author_id(self):
    obj = self.fb.comment_to_object(COMMENTS[0], post_author_id='my-author')
    self.assert_equals(
      'https://www.facebook.com/my-author/posts/547822715231468?comment_id=6796480',
      obj['url'])

  def test_comment_to_object_colon_id(self):
    """See https://github.com/snarfed/bridgy/issues/305"""
    id = '12:34:56_78'
    self.assert_equals({
      'objectType': 'comment',
      'id': tag_uri('34_78'),
      'fb_id': id,
      'content': 'asdf',
      'url': 'https://www.facebook.com/12/posts/34?comment_id=78',
      'inReplyTo': [{
        'id': tag_uri('34'),
        'url': 'https://www.facebook.com/12/posts/34',
      }],
    }, self.fb.comment_to_object({
      'id': id,
      'message': 'asdf',
    }))

  def test_comment_to_object_unknown_id_format(self):
    """See https://github.com/snarfed/bridgy/issues/305"""
    self.assert_equals({}, self.fb.comment_to_object({'id': '123 456^789'}))

  def test_comment_to_object_with_parent_comment(self):
    """See https://github.com/snarfed/bridgy/issues/435"""
    self.assert_equals({
      'objectType': 'comment',
      'id': tag_uri('34_78'),
      'fb_id': '34_78',
      'content': "now you're giving me all sorts of ideas!",
      'url': 'https://www.facebook.com/34?comment_id=78',
      'inReplyTo': [
        {'id': tag_uri('34'),
         'url': 'https://www.facebook.com/34'},
        {'id': tag_uri('34_56'),
         'url': 'https://www.facebook.com/34?comment_id=56'},
      ],
    }, self.fb.comment_to_object({
      'id': '34_78',
      'message': "now you're giving me all sorts of ideas!",
      'parent': {
        'message': 'You put coffee on tortilla chips?',
        'id': '34_56'
      },
    }))

  def test_share_to_object_empty(self):
    self.assert_equals({}, self.fb.share_to_object({}))

  def test_share_to_object_minimal(self):
    # just test that we don't crash
    self.fb.share_to_object({'id': '123_456_789', 'message': 'asdf'})

  def test_share_to_object_full(self):
    self.assert_equals(SHARE_OBJ, self.fb.share_to_object(SHARE))

  def test_share_to_object_no_message(self):
    share = copy.deepcopy(SHARE)
    del share['message']

    share_obj = copy.deepcopy(SHARE_OBJ)
    share_obj.update({
      'content': share['description'],
      'displayName': share['description'],
    })
    self.assert_equals(share_obj, self.fb.share_to_object(share))

    del share['description']
    del share['name']
    del share_obj['content']
    del share_obj['displayName']
    del share_obj['object']['content']
    del share_obj['object']['displayName']
    self.assert_equals(share_obj, self.fb.share_to_object(share))

  def test_user_to_actor_full(self):
    self.assert_equals(ACTOR, self.fb.user_to_actor(USER))

  def test_user_to_actor_page(self):
    self.assert_equals(PAGE_ACTOR, self.fb.user_to_actor(PAGE))

  def test_user_to_actor_url_fallback(self):
    user = copy.deepcopy(USER)
    actor = copy.deepcopy(ACTOR)
    del user['website']
    del actor['urls']
    user['bio'] = actor['description'] = 'no links'
    actor['url'] = user['link']
    self.assert_equals(actor, self.fb.user_to_actor(user))

    del user['link']
    actor['url'] = 'https://www.facebook.com/snarfed.org'
    self.assert_equals(actor, self.fb.user_to_actor(user))

  def test_user_to_actor_displayName_fallback(self):
    self.assert_equals({
      'objectType': 'person',
      'id': tag_uri('snarfed.org'),
      'username': 'snarfed.org',
      'displayName': 'snarfed.org',
      'url': 'https://www.facebook.com/snarfed.org',
    }, self.fb.user_to_actor({
      'username': 'snarfed.org',
    }))

  def test_user_to_actor_multiple_urls(self):
    actor = self.fb.user_to_actor({
      'id': '123',
      'website': """
x
http://a
y.com
http://b http://c""",
      'link': 'http://x',  # website overrides link
      })
    self.assertEquals('http://a', actor['url'])
    self.assertEquals(
      [{'value': 'http://a'}, {'value': 'http://b'}, {'value': 'http://c'}],
      actor['urls'])

    actor = self.fb.user_to_actor({
      'id': '123',
      'link': 'http://b http://c	http://a',
      })
    self.assertEquals('http://b', actor['url'])
    self.assertEquals(
      [{'value': 'http://b'}, {'value': 'http://c'}, {'value': 'http://a'}],
      actor['urls'])

  def test_user_to_actor_minimal(self):
    actor = self.fb.user_to_actor({'id': '212038'})
    self.assert_equals(tag_uri('212038'), actor['id'])
    self.assert_equals('https://graph.facebook.com/v2.2/212038/picture?type=large',
                       actor['image']['url'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.fb.user_to_actor({}))

  def test_event_to_object_empty(self):
    self.assert_equals({'objectType': 'event'}, self.fb.event_to_object({}))

  def test_event_to_object(self):
    self.assert_equals(EVENT_OBJ, self.fb.event_to_object(EVENT))

  def test_event_to_object_with_rsvps(self):
    self.assert_equals(EVENT_OBJ_WITH_ATTENDEES,
                       self.fb.event_to_object(EVENT, rsvps=RSVPS))

  def test_event_to_activity_with_rsvps(self):
    self.assert_equals(EVENT_ACTIVITY_WITH_ATTENDEES,
                       self.fb.event_to_activity(EVENT, rsvps=RSVPS))

  def test_rsvp_to_object(self):
    self.assert_equals(RSVP_OBJS, [self.fb.rsvp_to_object(r) for r in RSVPS])

  def test_rsvp_to_object_event(self):
    objs = [self.fb.rsvp_to_object(r, event=EVENT) for r in RSVPS]
    self.assert_equals(RSVP_OBJS_WITH_ID, objs)

  def test_picture_without_message(self):
    self.assert_equals({  # ActivityStreams
      'objectType': 'image',
      'id': tag_uri('445566'),
      'fb_id': '445566',
      'url': 'https://www.facebook.com/445566',
      'image': {'url': 'http://its/a/picture'},
    }, self.fb.post_to_object({  # Facebook
      'id': '445566',
      'picture': 'http://its/a/picture',
      'source': 'https://from/a/source',
    }))

  def test_like(self):
    activity = {
        'id': tag_uri('10100747369806713'),
        'fb_id': '10100747369806713',
        'verb': 'like',
        'title': 'Unknown likes a photo.',
        'url': 'https://www.facebook.com/10100747369806713',
        'object': {
          'objectType': 'image',
          'id': tag_uri('214721692025931'),
          'fb_id': '214721692025931',
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
    self.assert_equals(activity, self.fb.post_to_activity(post))

    activity.update({
        'title': 'Ryan Barrett likes a photo on Instagram.',
        'actor': ACTOR,
        'generator': {'displayName': 'Instagram', 'id': tag_uri('12402457428')},
        'url': 'https://www.facebook.com/212038/posts/10100747369806713',
        })
    activity['object']['author'] = ACTOR
    post.update({
        'from': USER,
        'application': {'name': 'Instagram', 'id': '12402457428'},
        })
    self.assert_equals(activity, self.fb.post_to_activity(post))

  def test_story_as_content(self):
    self.assert_equals({
        'id': tag_uri('101007473698067'),
        'fb_id': '101007473698067',
        'url': 'https://www.facebook.com/101007473698067',
        'objectType': 'note',
        'content': 'Once upon a time.',
      }, self.fb.post_to_object({
        'id': '101007473698067',
        'story': 'Once upon a time.',
        }))

  def test_name_as_content(self):
    self.assert_equals({
        'id': tag_uri('101007473698067'),
        'fb_id': '101007473698067',
        'url': 'https://www.facebook.com/101007473698067',
        'objectType': 'note',
        'content': 'Once upon a time.',
      }, self.fb.post_to_object({
        'id': '101007473698067',
        'name': 'Once upon a time.',
        }))

  def test_gift(self):
    self.assert_equals({
        'id': tag_uri('10100747'),
        'fb_id': '10100747',
        'actor': ACTOR,
        'verb': 'give',
        'title': 'Ryan Barrett gave a gift.',
        'url': 'https://www.facebook.com/212038/posts/10100747',
        'object': {
          'id': tag_uri('10100747'),
          'fb_id': '10100747',
          'author': ACTOR,
          'url': 'https://www.facebook.com/212038/posts/10100747',
          'objectType': 'product',
          },
      }, self.fb.post_to_activity({
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
        'fb_id': '10100747',
        'verb': 'listen',
        'title': "Unknown listened to The Rifle's Spiral.",
        'url': 'https://www.facebook.com/10100747',
        'object': {
          'id': tag_uri('101507345'),
          'fb_id': '101507345',
          'url': 'http://www.rdio.com/artist/The_Shins/album/Port_Of_Morrow_1/track/The_Rifle%27s_Spiral/',
          'objectType': 'audio',
          'displayName': "The Rifle's Spiral",
          },
      }
    self.assert_equals(activity, self.fb.post_to_activity(post))

    activity.update({
        'title': "Unknown listened to The Rifle's Spiral on Rdio.",
        'generator': {'displayName': 'Rdio', 'id': tag_uri('88888')},
        })
    activity['object'].update({
        'content': "Unknown listened to The Rifle's Spiral on Rdio.",
        })
    post.update({
        'from': USER,
        'application': {'name': 'Rdio', 'id': '88888'},
        })

  def test_facebook_note(self):
    """https://github.com/snarfed/bridgy/issues/480"""
    self.assert_equals(FB_NOTE_ACTIVITY, self.fb.post_to_activity(FB_NOTE))
    self.assert_equals(FB_NOTE_ACTIVITY,
                       self.fb.post_to_activity(FB_CREATED_NOTE))

  def test_link_type(self):
    """https://github.com/snarfed/bridgy/issues/502#issuecomment-160480559"""
    self.assert_equals(FB_LINK_ACTIVITY, self.fb.post_to_activity(FB_LINK))

  def test_privacy_to_to(self):
    """https://github.com/snarfed/bridgy/issues/559#issuecomment-159642227
    (among others)
    """
    for expected, inputs in (
        (None, [{}]),
        ([{'objectType': 'group', 'alias':'@private'}],
         ({'privacy': 'friends'}, {'privacy': {'value': 'FRIENDS'}},
          {'privacy': 'all_friends'}, {'privacy': {'value': 'ALL_FRIENDS'}})),
        ([{'objectType': 'group', 'alias':'@public'}],
         ({'privacy': ''}, {'privacy': {'value': ''}},
          {'privacy': 'open'}, {'privacy': {'value': 'OPEN'}},
          {'privacy': 'everyone'}, {'privacy': {'value': 'EVERYONE'}})),
        ([{'objectType': 'unknown'}],
         ({'privacy': 'custom'}, {'privacy': {'value': 'CUSTOM'}},
          {'status_type': 'wall_post', 'privacy': {'value': ''}})),
        ):
      for input in inputs:
        self.assert_equals(expected, self.fb.privacy_to_to(input), input)

  def test_album_to_object_empty(self):
    self.assert_equals({}, self.fb.album_to_object({}))

  def test_album_to_object_minimal(self):
    # just test that we don't crash
    self.fb.album_to_object({'id': '123_456_789', 'name': 'asdf'})

  def test_album_to_object_full(self):
    self.assert_equals(ALBUM_OBJ, self.fb.album_to_object(ALBUM))

  def test_create_post(self):
    self.expect_urlopen(facebook.API_FEED, {'id': '123_456'}, data=urllib.urlencode({
        'message': 'my msg',
        'tags': '234,345,456',
      }))
    self.mox.ReplayAll()

    obj = copy.deepcopy(POST_OBJ)
    del obj['image']
    obj.update({
        'objectType': 'note',
        'content': 'my msg',
        })
    self.assert_equals({
      'id': '123_456',
      'url': 'https://www.facebook.com/123/posts/456',
      'type': 'post',
    }, self.fb.create(obj).content)

    preview = self.fb.preview_create(obj)
    self.assertEquals('<span class="verb">post</span>:', preview.description)
    self.assertEquals('my msg<br /><br /><em>with <a href="https://www.facebook.com/234">Friend 1</a>, <a href="https://www.facebook.com/345">Friend 2</a>, <a href="https://www.facebook.com/456">Friend 3</a></em>', preview.content)

  def test_create_post_include_link(self):
    self.expect_urlopen(facebook.API_FEED, {}, data=urllib.urlencode({
      'message': 'my content\n\n(Originally published at: http://obj.co)',
    }))
    self.mox.ReplayAll()

    obj = copy.deepcopy(POST_OBJ)
    del obj['image']
    del obj['tags']  # skip person tags
    obj.update({
        'objectType': 'article',
        'content': 'my content',
        # displayName shouldn't override content
        'displayName': 'my content',
        'url': 'http://obj.co',
        })
    self.fb.create(obj, include_link=True)
    preview = self.fb.preview_create(obj, include_link=True)
    self.assertEquals(
      'my content\n\n(Originally published at: <a href="http://obj.co">http://obj.co</a>)',
      preview.content)

  def test_create_post_with_title(self):
    self.expect_urlopen(facebook.API_FEED, {}, data=urllib.urlencode({
      'message': 'my title\n\nmy content\n\n(Originally published at: http://obj.co)',
    }))
    self.mox.ReplayAll()

    obj = copy.deepcopy(POST_OBJ)
    del obj['image']
    del obj['tags']  # skip person tags
    obj.update({
        'objectType': 'article',
        'content': 'my content',
        # displayName shouldn't override content
        'displayName': 'my title',
        'url': 'http://obj.co',
        })
    self.fb.create(obj, include_link=True)
    preview = self.fb.preview_create(obj, include_link=True)
    self.assertEquals(
      'my title\n\nmy content\n\n(Originally published at: <a href="http://obj.co">http://obj.co</a>)',
      preview.content)

  def test_create_post_with_no_title(self):
    self.expect_urlopen(facebook.API_FEED, {}, data=urllib.urlencode({
      'message': 'my\ncontent\n\n(Originally published at: http://obj.co)',
    }))
    self.mox.ReplayAll()

    obj = copy.deepcopy(POST_OBJ)
    del obj['image']
    del obj['tags']  # skip person tags
    obj.update({
        'objectType': 'article',
        'content': 'my<br />content',
        # displayName shouldn't override content
        'displayName': 'my\ncontent',
        'url': 'http://obj.co',
        })
    self.fb.create(obj, include_link=True)
    preview = self.fb.preview_create(obj, include_link=True)
    self.assertEquals(
      'my\ncontent\n\n(Originally published at: <a href="http://obj.co">http://obj.co</a>)',
      preview.content)

  def test_create_comment(self):
    self.expect_urlopen('547822715231468/comments', {'id': '456_789'},
                        data='message=my+cmt')
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJS[0])
    # summary should override content
    obj['summary'] = 'my cmt'
    self.assert_equals({
      'id': '456_789',
      'url': 'https://www.facebook.com/547822715231468?comment_id=456_789',
      'type': 'comment'
    }, self.fb.create(obj).content)

    preview = self.fb.preview_create(obj)
    self.assertEquals('my cmt', preview.content)
    self.assertIn('<span class="verb">comment</span> on <a href="https://www.facebook.com/547822715231468">this post</a>:', preview.description)
    self.assertIn('<div class="fb-post" data-href="https://www.facebook.com/547822715231468">', preview.description)

  def test_create_comment_other_domain(self):
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJS[0])
    obj.update({'summary': 'my cmt', 'inReplyTo': [{'url': 'http://other'}]})

    for fn in (self.fb.preview_create, self.fb.create):
      result = fn(obj)
      self.assertTrue(result.abort)
      self.assertIn('Could not', result.error_plain)

  def test_create_comment_on_post_urls(self):
    # maps original post URL to expected comment URL
    urls = {
      'https://www.facebook.com/snarfed.org/posts/333':
        'https://www.facebook.com/snarfed.org/posts/333?comment_id=456_789',
      'https://www.facebook.com/photo.php?fbid=333&set=a.4.4&permPage=1':
        'https://www.facebook.com/333?comment_id=456_789',
      }

    for _ in urls:
      self.expect_urlopen('333/comments', {'id': '456_789'},
                          data='message=my+cmt')
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJS[0])
    for post_url, cmt_url in urls.items():
      obj.update({
          'inReplyTo': [{'url': post_url}],
          'content': 'my cmt',
          })
      self.assert_equals({
        'id': '456_789',
        'url': cmt_url,
        'type': 'comment',
      }, self.fb.create(obj).content)

  def test_create_comment_with_photo(self):
    self.expect_urlopen(
      '547822715231468/comments', {'id': '456_789'},
      data=urllib.urlencode({'message': 'cc Sam G, Michael M',
                             'attachment_url': 'http://pict/ure'}))
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJS[0])
    obj.update({
      'image': {'url': 'http://pict/ure'},
      'tags': [],  # skip person tags
    })
    self.assert_equals({
      'id': '456_789',
      'url': 'https://www.facebook.com/547822715231468?comment_id=456_789',
      'type': 'comment'
    }, self.fb.create(obj).content)

    preview = self.fb.preview_create(obj)
    self.assertEquals('cc Sam G, Michael M<br /><br /><img src="http://pict/ure" />',
                      preview.content)
    self.assertIn('<span class="verb">comment</span> on <a href="https://www.facebook.com/547822715231468">this post</a>:', preview.description)
    self.assertIn('<div class="fb-post" data-href="https://www.facebook.com/547822715231468">', preview.description)

  def test_create_comment_m_facebook_com(self):
    self.expect_urlopen('12_90/comments', {'id': '456_789'},
                        data='message=cc+Sam+G%2C+Michael+M')
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJS[0])
    obj['inReplyTo'] = {
      'url': 'https://m.facebook.com/photo.php?fbid=12&set=a.34.56.78&comment_id=90',
    }
    created = self.fb.create(obj)
    self.assert_equals({
      'id': '456_789',
      'url': 'https://www.facebook.com/12_90?comment_id=456_789',
      'type': 'comment'
    }, created.content, created)

  def test_create_like(self):
    for url in ('212038_1234/likes',
                '1234/likes',
                '135_79/likes',
                '78_90/likes',
                '12_90/likes',
                '12/likes',
                ):
      self.expect_urlopen(url, {"success": True}, data='')
    self.mox.ReplayAll()

    like = copy.deepcopy(LIKE_OBJS[0])
    for url in (
        'https://www.facebook.com/212038/posts/1234',
        'https://www.facebook.com/snarfed.org/posts/1234',
        'https://www.facebook.com/snarfed.org/posts/135?comment_id=79&offset=0&total_comments=1&pnref=story',
        'https://www.facebook.com/NovemberProjectSF/photos/a.12.34.56/78/?type=1&reply_comment_id=90&offset=0&total_comments=9',
        'https://www.facebook.com/photo.php?fbid=12&set=a.34.56.78&type=1&comment_id=90&offset=0&total_comments=3&pnref=story',
        'https://www.facebook.com/media/set/?set=a.12.34.56'):
      like['object']['url'] = url
      self.assert_equals({'url': url, 'type': 'like'},
                         self.fb.create(like).content)

  def test_create_like_page(self):
    result = self.fb.create({
      'objectType': 'activity',
      'verb': 'like',
      'object': {'url': 'https://facebook.com/MyPage'},
    })
    self.assertTrue(result.abort)
    for err in result.error_plain, result.error_html:
      self.assertIn("the Facebook API doesn't support liking pages", err)

  def test_create_like_page_preview(self):
    preview = self.fb.preview_create({
      'objectType': 'activity',
      'verb': 'like',
      'object': {'url': 'https://facebook.com/MyPage'},
    })
    self.assertTrue(preview.abort)
    for err in preview.error_plain, preview.error_html:
      self.assertIn("the Facebook API doesn't support liking pages", err)

  def test_create_like_post_preview(self):
    preview = self.fb.preview_create(LIKE_OBJS[0])
    self.assertIn('<span class="verb">like</span> <a href="https://www.facebook.com/212038/posts/10100176064482163">this post</a>:', preview.description)
    self.assertIn('<div class="fb-post" data-href="https://www.facebook.com/212038/posts/10100176064482163">', preview.description)

  def test_create_like_comment_preview(self):
    like = copy.deepcopy(LIKE_OBJS[0])
    like['object']['url'] = 'https://www.facebook.com/foo/posts/135?reply_comment_id=79'
    self.expect_urlopen('135_79', COMMENTS[0])
    self.mox.ReplayAll()

    preview = self.fb.preview_create(like)
    self.assert_equals("""\
<span class="verb">like</span> <a href="https://www.facebook.com/foo/posts/135?reply_comment_id=79">this comment</a>:
<br /><br />
<a class="h-card" href="https://www.facebook.com/212038">
  <img class="profile u-photo" src="https://graph.facebook.com/v2.2/212038/picture?type=large" width="32px" /> Ryan Barrett</a>:
cc Sam G, Michael M<br />""", preview.description)

  def test_create_rsvp(self):
    for endpoint in 'attending', 'declined', 'maybe':
      self.expect_urlopen('234/' + endpoint, {"success": True}, data='')

    self.mox.ReplayAll()
    for rsvp in RSVP_OBJS_WITH_ID[:3]:
      rsvp = copy.deepcopy(rsvp)
      rsvp['inReplyTo'] = [{'url': 'https://www.facebook.com/234/'}]
      self.assert_equals({'url': 'https://www.facebook.com/234/', 'type': 'rsvp'},
                         self.fb.create(rsvp).content)

    preview = self.fb.preview_create(rsvp)
    self.assertEquals('<span class="verb">RSVP maybe</span> to '
                      '<a href="https://www.facebook.com/234/">this event</a>.',
                      preview.description)

  def test_create_unsupported_type(self):
    for fn in self.fb.create, self.fb.preview_create:
      result = fn({'objectType': 'activity', 'verb': 'share'})
      self.assertTrue(result.abort)
      self.assertIn('Cannot publish shares', result.error_plain)
      self.assertIn('Cannot publish', result.error_html)

  def test_create_rsvp_without_in_reply_to(self):
    for rsvp in RSVP_OBJS_WITH_ID[:3]:
      rsvp = copy.deepcopy(rsvp)
      rsvp['inReplyTo'] = [{'url': 'https://foo.com/1234'}]
      result = self.fb.create(rsvp)
      self.assertTrue(result.abort)
      self.assertIn('missing an in-reply-to', result.error_plain)

  def test_create_comment_without_in_reply_to(self):
    obj = copy.deepcopy(COMMENT_OBJS[0])
    obj['inReplyTo'] = [{'url': 'http://foo.com/bar'}]

    for fn in (self.fb.preview_create, self.fb.create):
      preview = fn(obj)
      self.assertTrue(preview.abort)
      self.assertIn('Could not find a Facebook status to reply to', preview.error_plain)
      self.assertIn('Could not find a Facebook status to', preview.error_html)

  def test_create_like_without_object(self):
    obj = copy.deepcopy(LIKE_OBJS[0])
    del obj['object']

    for fn in (self.fb.preview_create, self.fb.create):
      preview = fn(obj)
      self.assertTrue(preview.abort)
      self.assertIn('Could not find a Facebook status to like', preview.error_plain)
      self.assertIn('Could not find a Facebook status to', preview.error_html)

  def test_create_with_photo(self):
    obj = {
      'objectType': 'note',
      'content': 'my caption',
      'image': {'url': 'http://my/picture'},
    }

    # test preview
    preview = self.fb.preview_create(obj)
    self.assertEquals('<span class="verb">post</span>:', preview.description)
    self.assertEquals('my caption<br /><br /><img src="http://my/picture" />',
                      preview.content)

    # test create
    self.expect_urlopen('me/albums', {'data': []})
    self.expect_urlopen(facebook.API_PHOTOS, {'id': '123_456'},
                        data='url=http%3A%2F%2Fmy%2Fpicture&message=my+caption')
    self.mox.ReplayAll()
    self.assert_equals({
      'id': '123_456',
      'url': 'https://www.facebook.com/123/posts/456',
      'type': 'post'}, self.fb.create(obj).content)

  def test_create_with_photo_uses_timeline_photos_album(self):
    """https://github.com/snarfed/bridgy/issues/571"""
    obj = {
      'objectType': 'note',
      'image': [{'url': 'http://my/picture'}],
    }

    self.expect_urlopen('me/albums', {'data': [
      {'id': '1', 'name': 'foo bar'},
      {'id': '2', 'type': 'wall'},
    ]})
    self.expect_urlopen('2/photos', {}, data=urllib.urlencode({
      'url': 'http://my/picture', 'message': ''}))
    self.mox.ReplayAll()
    self.assert_equals({'type': 'post', 'url': None}, self.fb.create(obj).content)

  def test_create_with_photo_and_person_tags(self):
    obj = {
      'objectType': 'note',
      'image': {'url': 'http://my/picture'},
      'tags': [{
        'objectType': 'person',
        'displayName': 'Foo',
        'url': 'https://www.facebook.com/234',
      }, {
        'objectType': 'person',
        'url': 'https://www.facebook.com/345',
      }],
    }

    # test preview
    preview = self.fb.preview_create(obj)
    self.assertEquals(
      '<br /><br /><img src="http://my/picture" /><br /><br /><em>with '
      '<a href="https://www.facebook.com/234">Foo</a>, '
      '<a href="https://www.facebook.com/345">User 345</a></em>',
      preview.content)

    # test create
    self.expect_urlopen('me/albums', {'data': []})
    self.expect_urlopen(
      facebook.API_PHOTOS, {'id': '123_456'}, data=urllib.urlencode({
        'url': 'http://my/picture',
        'message': '',
        'tags': json.dumps([{'tag_uid': '234'}, {'tag_uid': '345'}]),
      }))
    self.mox.ReplayAll()
    self.assert_equals({
      'id': '123_456',
      'url': 'https://www.facebook.com/123/posts/456',
      'type': 'post',
    }, self.fb.create(obj).content)

  def test_create_with_video(self):
    obj = {
      'objectType': 'note',
      'displayName': 'my \n caption should be removed ',
      'content': 'my <br /> caption <video class="x" y>should be removed </video>',
      'stream': {'url': 'http://my/video'},
    }

    # test preview
    preview = self.fb.preview_create(obj)
    self.assertEquals('<span class="verb">post</span>:', preview.description)
    self.assertEquals('my\ncaption<br /><br /><video controls src="http://my/video">'
                      '<a href="http://my/video">this video</a></video>',
                      preview.content)

    # test create
    self.expect_urlopen(facebook.API_VIDEOS, {}, data=urllib.urlencode({
      'file_url': 'http://my/video', 'description': 'my\ncaption'}))
    self.mox.ReplayAll()
    self.assert_equals({'type': 'post', 'url': None}, self.fb.create(obj).content)

  def test_create_notification(self):
    appengine_config.FACEBOOK_APP_ID = 'my_app_id'
    appengine_config.FACEBOOK_APP_SECRET = 'my_app_secret'
    params = {
      'template': 'my text',
      'href': 'my link',
      'access_token': 'my_app_id|my_app_secret',
      }
    self.expect_urlopen('my-username/notifications', '',
                        data=urllib.urlencode(params))
    self.mox.ReplayAll()
    self.fb.create_notification('my-username', 'my text', 'my link')

  def test_base_object_resolve_numeric_id(self):
    self.expect_urlopen('MyPage', PAGE)
    self.mox.ReplayAll()

    self.assert_equals(PAGE_ACTOR, self.fb.base_object(
      {'object': {'url': 'https://facebook.com/MyPage'}},
      resolve_numeric_id=True))

  def test_parse_id(self):
    def check(expected, id, is_comment):
      got = facebook.Facebook.parse_id(id, is_comment=is_comment)
      self.assertEquals(facebook.FacebookId(*expected), got,
                        '%s %s, got %s' % (id, is_comment, got))

    blank = facebook.FacebookId(None, None, None)

    # bad
    for id in (None, '', 'abc', '12_34^56', '12_34_56_78', '12__34',
               '_12_34', '12_34_', '12:34:', ':12:34', 'login.php'):
      for is_comment in True, False:
        check((None, None, None), id, is_comment)

    # these depend on is_comment
    check((None, '12', None), '12', False)
    check((None, None, '12'),'12',  True)
    check(('12', '34', None), '12_34', False)
    check((None, '12', '34'), '12_34', True)

    # these don't
    for id, expected in (
        ('12_34_56', ('12', '34', '56')),
        ('12:34:56', ('12', '34', None)),
        ('12:34:56_78', ('12', '34', '78')),
        ('12:34:56_', ('12', '34', None)),
        ('34:56', (None, '34', None)),
        ('34:56_78', (None, '34', '78')),
      ):
      check(expected, id, False)
      check(expected, id, True)

  def test_resolve_object_id(self):
    for i in range(3):
      self.expect_urlopen('111_222', {'id': '0', 'object_id': '333'})
    self.mox.ReplayAll()

    for id in '222', '222:0', '111_222_9':
      self.assertEqual('333', self.fb.resolve_object_id(111, id))

  def test_resolve_object_id_fetch_400s(self):
    self.expect_urlopen('111_222', {}, status=400)
    self.mox.ReplayAll()
    self.assertIsNone(self.fb.resolve_object_id('111', '222'))

  def test_resolve_object_id_with_activity(self):
    """If we pass an activity with fb_object_id, use that, don't fetch from FB."""
    obj = {'fb_object_id': 333}
    act = {'object': obj}

    for activity in obj, act:
      self.assertEqual('333', self.fb.resolve_object_id(
                                '111', '222', activity=activity))

  def test_urlopen_batch(self):
    self.expect_urlopen('',
      data='batch=[{"method":"GET","relative_url":"abc"},'
                  '{"method":"GET","relative_url":"def"}]',
      response=[{'code': 200, 'body': '{"abc": 1}'},
                {'code': 200, 'body': '{"def": 2}'}])
    self.mox.ReplayAll()

    self.assert_equals(({'abc': 1}, {'def': 2}),
                       self.fb.urlopen_batch(('abc', 'def')))

  def test_urlopen_batch_error(self):
    self.expect_urlopen('',
      data='batch=[{"method":"GET","relative_url":"abc"},'
                  '{"method":"GET","relative_url":"def"}]',
      response=[{'code': 304},
                {'code': 499, 'body': 'error body'}])
    self.mox.ReplayAll()

    try:
      self.fb.urlopen_batch(('abc', 'def'))
      assert False, 'expected HTTPError'
    except urllib2.HTTPError, e:
      self.assertEqual(499, e.code)
      self.assertEqual('error body', e.reason)

  def test_urlopen_batch_full(self):
    self.expect_urlopen('',
      data='batch=[{"headers":[{"name":"X","value":"Y"},'
                              '{"name":"U","value":"V"}],'
                   '"method":"GET","relative_url":"abc"},'
                  '{"method":"GET","relative_url":"def"}]',
      response=[{'code': 200, 'body': '{"json": true}'},
                {'code': 200, 'body': 'not json'}])
    self.mox.ReplayAll()

    self.assert_equals(
      [{'code': 200, 'body': {"json": True}},
       {'code': 200, 'body': 'not json'}],
      self.fb.urlopen_batch_full((
        {'relative_url': 'abc', 'headers': {'X': 'Y', 'U': 'V'}},
        {'relative_url': 'def'})))

  def test_urlopen_batch_full_errors(self):
    resps = [{'code': 501},
             {'code': 499, 'body': 'error body'}]
    self.expect_urlopen('',
      data='batch=[{"method":"GET","relative_url":"abc"},'
                  '{"method":"GET","relative_url":"def"}]',
      response=resps)
    self.mox.ReplayAll()

    self.assert_equals(resps, self.fb.urlopen_batch_full(
      [{'relative_url': 'abc'}, {'relative_url': 'def'}]))
