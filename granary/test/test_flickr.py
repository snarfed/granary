# coding=utf-8
"""Unit tests for flickr.py
"""
from __future__ import unicode_literals, print_function

import copy
import json
import mox
import requests
import socket
import urllib
import urllib2

from oauth_dropins import appengine_config
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
from granary import flickr
from granary import source

__author__ = ['Kyle Mahan <kyle@kylewm.com>']


# test data
def tag_uri(name):
  return util.tag_uri('flickr.com', name)

# format for a list of photos like the response to flickr.photos.getRecent
PHOTOS = {
  'photos': {
    'page': 1,
    'pages': 30,
    'perpage': 50,
    'total': '1461',
    'photo': [
      {
        'id': '8998787742',
        'owner': '39216764@N00',
        'secret': '89e6e03647',
        'server': '7459',
        'farm': 8,
        'title': 'Percheron Thunder',
        'ispublic': 1,
        'isfriend': 0,
        'isfamily': 0,
        'dateupload': '1370799634',
        'datetaken': '2013-06-08 03:20:48',
        'datetakengranularity': 0,
        'datetakenunknown': 0,
        'views': '196',
        'tags': 'oregon sistersrodeo',
        'machine_tags': '',
        'latitude': 0,
        'longitude': 0,
        'accuracy': 0,
        'context': 0,
        'media': 'photo',
        'media_status': 'ready'
      },
      {
        'id': '5227327325',
        'owner': '39216764@N00',
        'secret': 'ec6180fb32',
        'server': '4104',
        'farm': 5,
        'title': 'Emo dog & pun',
        'ispublic': 1,
        'isfriend': 0,
        'isfamily': 0,
        'dateupload': '1291338979',
        'datetaken': '2010-11-27 12:54:33',
        'datetakengranularity': 0,
        'datetakenunknown': 0,
        'views': '176',
        'tags': 'idyllwild emodog',
        'machine_tags': '',
        'latitude': 33.746663,
        'longitude': -116.711668,
        'accuracy': 15,
        'context': 0,
        'place_id': 'vaJN5r5TVrjDquPG',
        'woeid': '2426547',
        'geo_is_family': 0,
        'geo_is_friend': 0,
        'geo_is_contact': 0,
        'geo_is_public': 1,
        'media': 'photo',
        'media_status': 'ready'
      },
      {
        'id': '5227922370',
        'owner': '39216764@N00',
        'secret': '5f19cb9767',
        'server': '5246',
        'farm': 6,
        'title': 'Candy canes',
        'ispublic': 1,
        'isfriend': 0,
        'isfamily': 0,
        'dateupload': '1291338921',
        'datetaken': '2010-11-26 17:50:30',
        'datetakengranularity': 0,
        'datetakenunknown': 0,
        'views': '102',
        'tags': 'idyllwild',
        'machine_tags': '',
        'latitude': 33.746288,
        'longitude': -116.712441,
        'accuracy': 16,
        'context': 0,
        'place_id': 'vaJN5r5TVrjDquPG',
        'woeid': '2426547',
        'geo_is_family': 0,
        'geo_is_friend': 0,
        'geo_is_contact': 0,
        'geo_is_public': 1,
        'media': 'photo',
        'media_status': 'ready'
      }
    ]
  },
  'stat': 'ok'
}

# format for a single photos like the response to flickr.photos.getInfo
PHOTO_INFO = {
  'photo': {
    'id': '5227922370',
    'secret': '5f19cb9767',
    'server': '5246',
    'farm': 6,
    'dateuploaded': '1291338921',
    'isfavorite': 0,
    'license': 2,
    'safety_level': 0,
    'rotation': 0,
    'originalsecret': 'aa94c24f68',
    'originalformat': 'jpg',
    'owner': {
      'nsid': '39216764@N00',
      'username': 'kylewm',
      'realname': 'Kyle Mahan',
      'location': 'San Diego, CA, USA',
      'iconserver': '4068',
      'iconfarm': 5,
      'path_alias': 'kindofblue115'
    },
    'title': {
      '_content': 'Candy canes'
    },
    'description': {
      '_content': ''
    },
    'visibility': {
      'ispublic': 1,
      'isfriend': 0,
      'isfamily': 0
    },
    'dates': {
      'posted': '1291338921',
      'taken': '2010-11-26 17:50:30',
      'takengranularity': 0,
      'takenunknown': 0,
      'lastupdate': '1295288643'
    },
    'permissions': {
      'permcomment': 3,
      'permaddmeta': 2
    },
    'views': '102',
    'editability': {
      'cancomment': 1,
      'canaddmeta': 1
    },
    'publiceditability': {
      'cancomment': 1,
      'canaddmeta': 0
    },
    'usage': {
      'candownload': 1,
      'canblog': 1,
      'canprint': 1,
      'canshare': 1
    },
    'comments': {
      '_content': 1
    },
    'notes': {
      'note': [

      ]
    },
    'people': {
      'haspeople': 0
    },
    'tags': {
      'tag': [
        {
          'id': '4942564-5227922370-22730',
          'author': '39216764@N00',
          'authorname': 'kindofblue115',
          'raw': 'idyllwild',
          '_content': 'idyllwild',
          'machine_tag': 0
        }
      ]
    },
    'location': {
      'latitude': 33.746288,
      'longitude': -116.712441,
      'accuracy': 16,
      'context': 0,
      'locality': {
        '_content': 'Idyllwild-Pine Cove',
        'place_id': 'vaJN5r5TVrjDquPG',
        'woeid': '2426547'
      },
      'county': {
        '_content': 'Riverside',
        'place_id': 'ZNLarLZQUL98qkEJMQ',
        'woeid': '12587702'
      },
      'region': {
        '_content': 'California',
        'place_id': 'NsbUWfBTUb4mbyVu',
        'woeid': '2347563'
      },
      'country': {
        '_content': 'United States',
        'place_id': 'nz.gsghTUb4c2WAecA',
        'woeid': '23424977'
      },
      'place_id': 'vaJN5r5TVrjDquPG',
      'woeid': '2426547'
    },
    'geoperms': {
      'ispublic': 1,
      'iscontact': 0,
      'isfriend': 0,
      'isfamily': 0
    },
    'urls': {
      'url': [
        {
          'type': 'photopage',
          '_content': 'https://www.flickr.com/photos/kindofblue115/5227922370/'
        }
      ]
    },
    'media': 'photo'
  },
  'stat': 'ok'
}

# single PHOTO_INFO response converted to ActivityStreams
ACTIVITY = {
  'verb': 'post',
  'actor': {'numeric_id': '39216764@N00'},
  'created': '2010-11-26 17:50:30',
  'url': 'https://www.flickr.com/photos/kindofblue115/5227922370/',
  'object': {
    'content': 'Candy canes\n',
    'displayName': 'Candy canes',
    'author': {
      'username': 'kylewm',
      'image': {'url': 'https://farm5.staticflickr.com/4068/buddyicons/39216764@N00.jpg'},
      'displayName': 'Kyle Mahan',
      'id': 'tag:flickr.com:kylewm',
      'objectType': 'person'
    },
    'created': '2010-11-26 17:50:30',
    'url': 'https://www.flickr.com/photos/kindofblue115/5227922370/',
    'image': {'url': 'https://farm6.staticflickr.com/5246/5227922370_5f19cb9767_b.jpg'},
    'published': '2010-12-03T01:15:21',
    'id': 'tag:flickr.com:5227922370',
    'tags': [{
      'url': 'https://www.flickr.com/search?tags=idyllwild',
      'displayName': 'idyllwild',
      'id': 'tag:flickr.com:4942564-5227922370-22730',
      'objectType': 'hashtag'
    }],
    'location': {
      'latitude': 33.746288,
      'longitude': -116.712441,
      'position': '+33.746288-116.712441/',
      'objectType': 'place',
    },
    'to': [{'objectType': 'group', 'alias': '@public'}],
    'objectType': 'photo',
  },
  'id': 'tag:flickr.com:5227922370',
  'flickr_id': '5227922370',
  'published': '2010-12-03T01:15:21'
}

# favorites response corresponding to PHOTO_INFO above
PHOTO_FAVORITES = {
  'photo': {
    'person': [
      {
        'nsid': '95922884@N00',
        'username': 'absentmindedprof',
        'realname': 'Jennifer',
        'favedate': '1291599546',
        'iconserver': '5343',
        'iconfarm': 6,
        'contact': 1,
        'friend': 1,
        'family': 0
      }
    ],
    'id': '5227922370',
    'secret': '5f19cb9767',
    'server': '5246',
    'farm': 6,
    'page': 1,
    'pages': 1,
    'perpage': 10,
    'total': 1
  },
  'stat': 'ok'
}

# comments response corresponding to PHOTO_INFO above
PHOTO_COMMENTS = {
  'comments': {
    'photo_id': '5227922370',
    'comment': [
      {
        'id': '4942564-5227922370-72157625845945286',
        'author': '36398523@N00',
        'authorname': 'if winter ends',
        'iconserver': '108',
        'iconfarm': 1,
        'datecreate': '1295288643',
        'permalink': 'https://www.flickr.com/photos/kindofblue115/5227922370/#comment72157625845945286',
        'path_alias': 'if_winter_ends',
        'realname': 'Dusty',
        '_content': 'Love this!'
      }
    ]
  },
  'stat': 'ok'
}

COMMENT_OBJS = [{  # ActivityStreams
  'objectType': 'comment',
  'author': {
    'objectType': 'person',
    'id': tag_uri('36398523@N00'),
    'displayName': 'Dusty',
    'username': 'if winter ends',
    'image': {'url': 'https://farm1.staticflickr.com/108/buddyicons/36398523@N00.jpg'},
    'url': 'https://www.flickr.com/people/if_winter_ends/',
  },
  'content': 'Love this!',
  'id': tag_uri('4942564-5227922370-72157625845945286'),
  'updated': '2011-01-17T18:24:03',
  'published': '2011-01-17T18:24:03',
  'url': 'https://www.flickr.com/photos/kindofblue115/5227922370/#comment72157625845945286',
  'inReplyTo': [{
    'id': tag_uri('5227922370'),
  }],
}]

ACTIVITY_WITH_COMMENTS = copy.deepcopy(ACTIVITY)
ACTIVITY_WITH_COMMENTS['object']['replies'] = {
  'totalItems': len(COMMENT_OBJS),
  'items': COMMENT_OBJS,
}

FAVORITE_OBJS = [{
  'author': {
    'displayName': 'Jennifer',
    'id': 'tag:flickr.com:95922884@N00',
    'image': {'url': 'https://farm6.staticflickr.com/5343/buddyicons/95922884@N00.jpg'},
    'objectType': 'person',
    'username': 'absentmindedprof'
  },
  'id': tag_uri('5227922370_liked_by_95922884@N00'),
  'object': {'url': 'https://www.flickr.com/photos/kindofblue115/5227922370/'},
  'objectType': 'activity',
  'url': 'https://www.flickr.com/photos/kindofblue115/5227922370/#liked-by-95922884@N00',
  'verb': 'like'
}]

ACTIVITY_WITH_FAVES = copy.deepcopy(ACTIVITY)
ACTIVITY_WITH_FAVES['object']['tags'] += FAVORITE_OBJS

# response from flickr.people.getInfo
PERSON_INFO = {
  'person': {
    'id': '39216764@N00',
    'nsid': '39216764@N00',
    'ispro': 0,
    'can_buy_pro': 0,
    'iconserver': '4068',
    'iconfarm': 5,
    'path_alias': 'kindofblue115',
    'has_stats': 1,
    'username': {
      '_content': 'kylewm'
    },
    'realname': {
      '_content': 'Kyle Mahan'
    },
    'mbox_sha1sum': {
      '_content': '049cf71f4b437dc0ab497e107f7b7d2c55a096d4'
    },
    'location': {
      '_content': 'San Diego, CA, USA'
    },
    'timezone': {
      'label': 'Pacific Time (US & Canada); Tijuana',
      'offset': '-08:00',
      'timezone_id': 'PST8PDT'
    },
    'description': {
      '_content': 'Trying a little bit of everything'
    },
    'photosurl': {
      '_content': 'https://www.flickr.com/photos/kindofblue115/'
    },
    'profileurl': {
      '_content': 'https://www.flickr.com/people/kindofblue115/'
    },
    'mobileurl': {
      '_content': 'https://m.flickr.com/photostream.gne?id=4942564'
    },
    'photos': {
      'firstdatetaken': {
        '_content': '2005-12-27 18:29:07'
      },
      'firstdate': {
        '_content': '1159222380'
      },
      'count': {
        '_content': '1461'
      },
      'views': {
        '_content': '7459'
      }
    }
  },
  'stat': 'ok'
}

CONTACTS_PHOTOS = {
  'photos': {
    'photo': [{
      'id': '1234',
      'secret': '22',
      'owner': '5555',
      'server': '99',
      'farm': 4,
      'title': 'First Photo',
      'dateupload': '1370799634',
      'datetaken': '2013-06-08 03:20:48',
      'tags': 'tag1 tag2',
      'media': 'photo',
      'ispublic': 0,
      'isfriend': 1,
      'isfamily': 1,
      'iscontact': 0,
    }, {
      'id': '2345',
      'secret': '33',
      'owner': '6666',
      'server': '88',
      'farm': 4,
      'title': 'Second Photo',
      'dateupload': '1291338979',
      'datetaken': '2010-11-27 12:54:33',
      'tags': 'tag1 tag2',
      'media': 'photo',
      'ispublic': 1,
      'isfriend': 0,
      'isfamily': 0,
      'iscontact': 0,
    }],
  },
}

CONTACTS_PHOTOS_ACTIVITIES = [{
  'verb': 'post',
  'actor': {'numeric_id': '5555'},
  'created': '2013-06-08 03:20:48',
  'url': 'https://www.flickr.com/photos/5555/1234/',
  'object': {
    'content': 'First Photo\n',
    'displayName': 'First Photo',
    'created': '2013-06-08 03:20:48',
    'url': 'https://www.flickr.com/photos/5555/1234/',
    'image': {
      'url': 'https://farm4.staticflickr.com/99/1234_22_b.jpg'
    },
    'published': '2013-06-09T17:40:34',
    'id': 'tag:flickr.com:1234',
    'tags': [{
      'url': 'https://www.flickr.com/search?tags=tag1',
      'displayName': 'tag1',
      'objectType': 'hashtag'
    }, {
      'url': 'https://www.flickr.com/search?tags=tag2',
      'displayName': 'tag2',
      'objectType': 'hashtag'
    }],
    'to': [{'objectType': 'group', 'alias': '@private'}],
    'objectType': 'photo'
  },
  'id': 'tag:flickr.com:1234',
  'flickr_id': '1234',
  'published': '2013-06-09T17:40:34'
}, {
  'verb': 'post',
  'actor': {'numeric_id': '6666'}, 'created': '2010-11-27 12:54:33',
  'url': 'https://www.flickr.com/photos/6666/2345/',
  'object': {
    'content': 'Second Photo\n',
    'displayName': 'Second Photo',
    'created': '2010-11-27 12:54:33',
    'url': 'https://www.flickr.com/photos/6666/2345/',
    'image': {
      'url': 'https://farm4.staticflickr.com/88/2345_33_b.jpg'
    },
    'published': '2010-12-03T01:16:19',
    'id': 'tag:flickr.com:2345',
    'tags': [{
      'url': 'https://www.flickr.com/search?tags=tag1',
      'displayName': 'tag1',
      'objectType': 'hashtag'
    }, {
      'url': 'https://www.flickr.com/search?tags=tag2',
      'displayName': 'tag2',
      'objectType': 'hashtag'
    }],
    'to': [{'objectType': 'group', 'alias': '@public'}],
    'objectType': 'photo'
  },
  'id': 'tag:flickr.com:2345',
  'flickr_id': '2345',
  'published': '2010-12-03T01:16:19'
}]

ACTOR = {
  'objectType': 'person',
  'displayName': 'Kyle Mahan',
  'image': {
    'url': 'https://farm5.staticflickr.com/4068/buddyicons/39216764@N00.jpg',
  },
  'id': 'tag:flickr.com:kylewm',
  'location': {'displayName': 'San Diego, CA, USA'},
  'description': 'Trying a little bit of everything',
  'url': 'https://kylewm.com/',
  'urls': [
    {'value': 'https://www.flickr.com/people/kindofblue115/'},
    {'value': 'https://www.flickr.com/people/kindofblue115/contacts/'},
    {'value': 'https://kylewm.com/'},
  ],
  'username': 'kylewm',
  'numeric_id': '39216764@N00',
}

PROFILE_HTML = """
<html>
  <body>
    <a href='https://www.flickr.com/people/kindofblue115/' rel='me'>Profile</a>
    <a href='https://www.flickr.com/people/kindofblue115/contacts/' rel='me'>Contacts</a>
    <a href='https://kylewm.com/' rel='me'>kylewm.com</a>
  </body>
</html>
"""

# an AS photo post with person tags
OBJECT = {
  # microformats2 returns images as lists now
  'image': [{
    'url': 'https://jeena.net/photos/IMG_20150729_181700.jpg',
  }],
  'url': 'https://jeena.net/photos/164',
  'content': 'First Homebrew Website Club in Gothenburg #IndieWeb',
  'updated': '2015-07-29T17:14:34+0000',
  'author': {
    'image': [{
      'url': 'https://jeena.net/avatar.jpg',
    }],
    'url': 'https://jeena.net/',
    'displayName': 'Jeena',
    'objectType': 'person',
  },
  'tags': [{
    'url': 'https://www.flickr.com/photos/vanderven/',
    'displayName': 'Martijn van der Ven',
    'objectType': 'person',
  }, {
    'url': 'https://flickr.com/people/oskarsson/',
    'objectType': 'person',
  }, {
    'url': 'https://flickr.com/photos/382@123/',
    'displayName': 'Jeena',
    'objectType': 'person',
  }, {
    'displayName': 'indieweb',
    'objectType': 'hashtag',
  }, {
    'displayName': 'homebrew website club',
    'objectType': 'hashtag',
  }],
  'location': {
    'objectType': 'place',
    'latitude': 57.7020124,
    'longitude': 11.6135007,
  },
  'published': '2015-07-29T17:14:34+0000',
  'displayName': 'Photo #164',
  'objectType': 'note',
}

REPLY_OBJ = {
  'inReplyTo': [{
    'url': 'https://www.flickr.com/photos/marietta_wood_works/21904325000/in/contacts/',
  }],
  'displayName': 'punkins!',
  'author': {
    'url': 'https://kylewm.com',
    'image': [{'url': 'https://kylewm.com/static/img/users/kyle.jpg'}],
    'displayName': 'Kyle Mahan', 'objectType': 'person',
  },
  'url': 'https://kylewm.com/2015/11/punkins',
  'content': 'punkins!',
  'published': '2015-11-15T09:58:35-0800',
  'id': 'https://kylewm.com/2015/11/punkins',
  'objectType': 'comment',
}

LIKE_OBJ = {
  'object': [{
    'url': 'https://www.flickr.com/photos/marietta_wood_works/21904325000/in/contacts/',
  }],
  'author': {
    'url': 'https://kylewm.com',
    'image': [{'url': 'https://kylewm.com/static/img/users/kyle.jpg'}],
    'displayName': 'Kyle Mahan', 'objectType': 'person',
  },
  'url': 'https://kylewm.com/2015/11/like-of-alber',
  'content': 'punkins!',
  'published': '2015-11-15T09:58:35-0800',
  'id': 'https://kylewm.com/2015/11/like-of-alber',
  'objectType': 'activity',
  'verb': 'like',
}

# uploads send oauth params along with the post data; it's useful to
# be able to check that they exist, but ignore their values.
IGNORED_OAUTH_PARAMS = [
  ('oauth_nonce', mox.IsA(str)),
  ('oauth_timestamp', mox.IsA(str)),
  ('oauth_version', mox.IsA(str)),
  ('oauth_signature_method', mox.IsA(str)),
  ('oauth_consumer_key', mox.IsA(str)),
  ('oauth_token', mox.IsA(str)),
  ('oauth_signature', mox.IsA(str)),
]


class FlickrTest(testutil.TestCase):

  def setUp(self):
    super(FlickrTest, self).setUp()
    appengine_config.FLICKR_APP_KEY = 'fake'
    appengine_config.FLICKR_APP_SECRET = 'fake'
    self.flickr = flickr.Flickr('key', 'secret')

  def expect_call_api_method(self, method, params, result):
    full_params = {
      'nojsoncallback': 1,
      'format': 'json',
      'method': method,
    }
    full_params.update(params)
    return self.expect_urlopen('https://api.flickr.com/services/rest?'
                               + urllib.urlencode(full_params), result)

  def test_get_actor(self):
    self.expect_call_api_method('flickr.people.getInfo', {
      'user_id': '39216764@N00'
    }, json.dumps(PERSON_INFO))

    self.expect_urlopen(
      'https://www.flickr.com/people/kindofblue115/',
      PROFILE_HTML)

    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.flickr.get_actor('39216764@N00'))

  def test_get_actor_default(self):
    # extra call to find the user id
    self.expect_call_api_method(
      'flickr.people.getLimits', {}, json.dumps({'person': {
        'nsid': '39216764@N00',
        'photos': {'maxdisplaypx': '1024', 'maxupload': '209715200'},
        'videos': {'maxduration': '180', 'maxupload': '1073741824'}
      }, 'stat': 'ok'}))

    self.expect_call_api_method(
      'flickr.people.getInfo', {'user_id': '39216764@N00'},
      json.dumps(PERSON_INFO))

    self.expect_urlopen(
      'https://www.flickr.com/people/kindofblue115/',
      PROFILE_HTML)

    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.flickr.get_actor())

  def test_get_activities_defaults(self):
    self.expect_call_api_method(
      'flickr.photos.getContactsPhotos', {
        'extras': flickr.Flickr.API_EXTRAS,
        'per_page': 50,
      }, json.dumps(CONTACTS_PHOTOS))

    self.mox.ReplayAll()
    self.assert_equals(CONTACTS_PHOTOS_ACTIVITIES, self.flickr.get_activities())

  def test_get_activities_specific(self):
    self.expect_call_api_method(
      'flickr.photos.getInfo', {
        'photo_id': '5227922370',
      }, json.dumps(PHOTO_INFO))

    self.mox.ReplayAll()
    self.assert_equals(
      [ACTIVITY],
      self.flickr.get_activities(activity_id='5227922370'))

  def test_get_activities_with_comments(self):
    self.expect_call_api_method(
      'flickr.photos.getInfo', {
        'photo_id': '5227922370',
      }, json.dumps(PHOTO_INFO))

    self.expect_call_api_method('flickr.photos.comments.getList', {
        'photo_id': '5227922370',
    }, json.dumps(PHOTO_COMMENTS))

    self.mox.ReplayAll()
    self.assert_equals(
      [ACTIVITY_WITH_COMMENTS], self.flickr.get_activities(
        activity_id='5227922370', fetch_replies=True))

  def test_get_activities_with_faves(self):
    self.expect_call_api_method(
      'flickr.photos.getInfo', {
        'photo_id': '5227922370',
      }, json.dumps(PHOTO_INFO))

    self.expect_call_api_method('flickr.photos.getFavorites', {
        'photo_id': '5227922370',
    }, json.dumps(PHOTO_FAVORITES))

    self.mox.ReplayAll()
    self.assert_equals(
      [ACTIVITY_WITH_FAVES], self.flickr.get_activities(
        activity_id='5227922370', fetch_likes=True))

  def test_favorite_without_display_name(self):
    """Make sure faves fall back to the username if the user did not
    supply a real name.
    """
    faves = copy.deepcopy(PHOTO_FAVORITES)
    del faves['photo']['person'][0]['realname']

    self.expect_call_api_method(
      'flickr.photos.getInfo', {
        'photo_id': '5227922370',
      }, json.dumps(PHOTO_INFO))

    self.expect_call_api_method('flickr.photos.getFavorites', {
        'photo_id': '5227922370',
    }, json.dumps(faves))

    self.mox.ReplayAll()
    resp = self.flickr.get_activities(
      activity_id='5227922370', fetch_likes=True)

    like = next(tag for tag in resp[0]['object']['tags']
                if tag.get('verb') == 'like')
    self.assert_equals('absentmindedprof', like['author']['displayName'])

  def test_comment_without_display_name(self):
    """Make sure comments fall back to the username if the user did not
    supply a real name.
    """
    comments = copy.deepcopy(PHOTO_COMMENTS)
    del comments['comments']['comment'][0]['realname']

    self.expect_call_api_method(
      'flickr.photos.getInfo', {
        'photo_id': '5227922370',
      }, json.dumps(PHOTO_INFO))

    self.expect_call_api_method('flickr.photos.comments.getList', {
        'photo_id': '5227922370',
    }, json.dumps(comments))

    self.mox.ReplayAll()
    resp = self.flickr.get_activities(
      activity_id='5227922370', fetch_replies=True)

    comment = resp[0]['object']['replies']['items'][0]
    self.assert_equals('if winter ends', comment['author']['displayName'])

  def test_get_comment(self):
    """get_comment should fetch the list of comments for a photo, and then
    iteratively look for the comment by id.
    """
    self.expect_call_api_method(
      'flickr.photos.comments.getList', {
        'photo_id': '5227922370',
      }, json.dumps(PHOTO_COMMENTS))
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJS[0], self.flickr.get_comment(
      '4942564-5227922370-72157625845945286', '5227922370'))

  def test_search_raises_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.flickr.get_activities(group_id=source.SEARCH, search_query='foo')

  def _expect_lookup_users(self):
    """Several tests use this to lookup Flickr NSIDs for the three people
    tagged in OBJECT.
    """
    for url, user_id in [('https://www.flickr.com/photos/vanderven/', '123@1'),
                         ('https://flickr.com/people/oskarsson/', '456@4'),
                         ('https://flickr.com/photos/382@123/', '382@123')]:
      self.expect_call_api_method(
        'flickr.urls.lookupUser', {'url': url},
        json.dumps({'user': {'id': user_id}}))

  def test_preview_create_photo(self):
    self._expect_lookup_users()
    self.mox.ReplayAll()
    preview = self.flickr.preview_create(
      OBJECT, include_link=source.INCLUDE_LINK)
    self.assertEquals('post', preview.description)
    self.assertIn('Photo #164', preview.content)
    self.assertIn(
      'First Homebrew Website Club in Gothenburg #IndieWeb',
      preview.content)
    self.assertIn(
      '\n\n(Originally published at: https://jeena.net/photos/164)',
      preview.content)
    self.assertIn(
      '<img src="https://jeena.net/photos/IMG_20150729_181700.jpg"',
      preview.content)
    self.assertIn(
      '<a href="https://www.flickr.com/photos/vanderven/">Martijn van der Ven</a>',
      preview.content)
    self.assertIn(
      '<a href="https://flickr.com/people/oskarsson/">User 456@4</a>',
      preview.content)
    self.assertIn(
      '<a href="https://flickr.com/photos/382@123/">Jeena</a>',
      preview.content)
    # hashtags
    self.assertIn('#indieweb #homebrew website club', preview.content)
    self.assertIn('57.7020124, 11.6135007', preview.content)

  def test_create_photo_success(self):
    """Check that successfully uploading an image returns the expected
    response.
    """
    data = [
      ('title', 'Photo #164'),
      ('description', 'First Homebrew Website Club in Gothenburg #IndieWeb'
       '\n\n(Originally published at: https://jeena.net/photos/164)'),
      ('tags', 'indieweb,"homebrew website club"'),
    ] + IGNORED_OAUTH_PARAMS

    self._expect_lookup_users()

    # fetch the image
    self.expect_urlopen('https://jeena.net/photos/IMG_20150729_181700.jpg',
                        'picture response')

    # upload to Flickr
    self.expect_requests_post(
      'https://up.flickr.com/services/upload',
      data=data, files={'photo': 'picture response'},
      response="""\
<?xml version="1.0" encoding="utf-8" ?>
<rsp stat="ok">
  <photoid>9876</photoid>
</rsp>
""")

    # lookup user id
    self.expect_call_api_method(
      'flickr.people.getLimits', {},
      json.dumps({'person': {'nsid': '39216764@N00'}}))

    # lookup path alias
    self.expect_call_api_method(
      'flickr.people.getInfo', {'user_id': '39216764@N00'},
      json.dumps({'person': {'nsid': '39216764@N00',
                             'path_alias': 'kindofblue115'}}))

    # add person tags
    for user_id in ['123@1', '382@123', '456@4']:
      self.expect_call_api_method(
        'flickr.photos.people.add', {'photo_id': '9876', 'user_id': user_id},
        '{"stat": "ok"}')

    # add location
    self.expect_call_api_method(
      'flickr.photos.geo.setLocation', {
        'photo_id': '9876', 'lat': 57.7020124, 'lon': 11.6135007
      }, '{"stat": "ok"}')

    self.mox.ReplayAll()
    self.assertEquals({
      'id': '9876',
      'url': 'https://www.flickr.com/photos/kindofblue115/9876/',
      'type': 'post',
    }, self.flickr.create(OBJECT, include_link=source.INCLUDE_LINK).content)

  def test_create_photo_failure(self):
    """If uploading returns a failure, interpret it correctly.
    """
    data = [
      ('title', 'Photo #164'),
      ('description', 'First Homebrew Website Club in Gothenburg #IndieWeb'),
      ('tags', 'indieweb,"homebrew website club"'),
    ] + IGNORED_OAUTH_PARAMS

    self._expect_lookup_users()

    # fetch the image
    self.expect_urlopen('https://jeena.net/photos/IMG_20150729_181700.jpg',
                        'picture response')

    # upload to Flickr
    self.expect_requests_post(
      'https://up.flickr.com/services/upload',
      data=data, files={'photo': 'picture response'},
      response="""\
<?xml version="1.0" encoding="utf-8" ?>
<rsp stat="fail">
  <err code="98" msg="Login Failed" />
</rsp>
""")
    self.mox.ReplayAll()

    self.assertRaises(urllib2.HTTPError, self.flickr.create, OBJECT)

  def test_create_video_success(self):
    self.flickr._user_id = '39216764@N00'
    self.flickr._path_alias = 'kindofblue115'

    obj = {
      'objectType': 'note',
      'stream': {'url': 'https://jeena.net/videos/xyz.mp4'},
      'image': [{'url': 'https://jeena.net/photos/xyz.jpg'}],
      'url': 'https://jeena.net/videos/164',
      # the <video> tag should be removed, but other formatting should be preserved
      'content': 'check<br />out <video>my video</video>',
    }

    # preview
    preview = self.flickr.preview_create(obj)
    self.assertEquals('post', preview.description)
    self.assertEquals(
      '<div>check\nout</div>'
        '<video controls src="https://jeena.net/videos/xyz.mp4">'
        '<a href="https://jeena.net/videos/xyz.mp4">this video</a></video>',
      preview.content)

    # create
    self.expect_urlopen('https://jeena.net/videos/xyz.mp4', 'video response')
    self.expect_requests_post(
      'https://up.flickr.com/services/upload',
      data=[
        ('description', 'check\nout'),
      ] + IGNORED_OAUTH_PARAMS,
      files={'photo': 'video response'},
      response="""\
<?xml version="1.0" encoding="utf-8" ?>
<rsp stat="ok">
  <photoid>9876</photoid>
</rsp>
""")
    self.mox.ReplayAll()

    self.assert_equals({
      'id': '9876',
      'url': 'https://www.flickr.com/photos/kindofblue115/9876/',
      'type': 'post',
      'granary_message':
        "Note that videos take time to process before they're visible.",
    }, self.flickr.create(obj).content)

  def test_create_strips_video_tag_and_name_matches_content(self):
    preview = self.flickr.preview_create({
      'objectType': 'note',
      'stream': {'url': 'https://jeena.net/videos/xyz.mp4'},
      'displayName': 'my content should hide',
      'content': 'my content <video>should hide</video>',
    }).content
    self.assertTrue(preview.startswith('<h4>my content</h4>'), preview)
    self.assertNotIn('should hide', preview)

  def test_create_video_too_big(self):
    self.expect_urlopen('http://foo/xyz.mp4', 'video response')
    self.expect_requests_post(
      'https://up.flickr.com/services/upload',
      data=[('description', 'foo')] + IGNORED_OAUTH_PARAMS,
      files={'photo': 'video response'}
    ).AndRaise(requests.exceptions.ConnectionError(socket.error(
      'Request exceeds 10 MiB limit for URL: https://up.flickr.com/services/upload')))
    self.mox.ReplayAll()

    err = 'Sorry, photos and videos must be under 10MB.'
    self.assert_equals(
      source.creation_result(error_plain=err, error_html=err),
      self.flickr.create({
        'objectType': 'note',
        'stream': {'url': 'http://foo/xyz.mp4'},
        'url': 'http://foo/xyz',
        'content': 'foo',
      }))

  def test_preview_create_comment(self):
    preview = self.flickr.preview_create(
      REPLY_OBJ, include_link=source.INCLUDE_LINK)
    self.assertEquals(
      'comment on <a href="https://www.flickr.com/photos/marietta_wood_works/'
      '21904325000/in/contacts/">this photo</a>.',
      preview.description)
    self.assertEquals(
      'punkins!\n\n'
      '(Originally published at: https://kylewm.com/2015/11/punkins)',
      preview.content)

  def test_create_comment(self):
    self.expect_call_api_method('flickr.photos.comments.addComment', {
      'photo_id': '21904325000',
      'comment_text': 'punkins!\n\n'
      '(Originally published at: https://kylewm.com/2015/11/punkins)',
    }, json.dumps({
      'comment': {
        'id': '4942564-21904325000-72157661220102352',
        'author': '39216764@N00',
        'authorname': 'kylewm',
        'datecreate': '1447612679',
        'permalink': 'https://www.flickr.com/photos/marietta_wood_works/'
        '21904325000/#comment72157661220102352',
        'path_alias': 'kindofblue115',
        'realname': 'Kyle Mahan',
        '_content': 'punkins!'
      },
      'stat': 'ok'
    }))

    self.mox.ReplayAll()

    reply_content = self.flickr.create(
      REPLY_OBJ, include_link=source.INCLUDE_LINK).content
    self.assertEquals(
      '4942564-21904325000-72157661220102352',
      reply_content.get('id'))
    self.assertEquals(
      'https://www.flickr.com/photos/marietta_wood_works/21904325000/'
      '#comment72157661220102352',
      reply_content.get('url'))

  # https://github.com/snarfed/bridgy/issues/692
  def test_create_comment_encodes_unicode(self):
    self.expect_call_api_method('flickr.photos.comments.addComment', {
      'photo_id': '28733650665',
      'comment_text': u'these ‘are smart’ quotes'.encode('utf-8'),
    }, json.dumps({
      'comment': {
        'id': '123456',
        'permalink': 'https://www.flickr.com/comment/123456',
      },
    }))
    self.mox.ReplayAll()

    reply_content = self.flickr.create({
      'objectType': 'comment',
      'content': u'these ‘are smart’ quotes',
      'inReplyTo': [{
        'url': 'https://www.flickr.com/photos/58071954@N08/28733650665/',
      }],
    }).content
    self.assertEquals('123456', reply_content['id'])
    self.assertEquals('https://www.flickr.com/comment/123456', reply_content['url'])

  def test_create_favorite(self):
    """Favoriting a photo generates a URL using a fake fragment id
    """
    self.expect_call_api_method(
      'flickr.favorites.add', {'photo_id': '21904325000'},
      json.dumps({'stat': 'ok'}))

    self.expect_call_api_method(
      'flickr.people.getLimits', {},
      json.dumps({'person': {'nsid': '39216764@N00'}}))

    self.mox.ReplayAll()
    self.assertEquals({
      'type': 'like',
      'url': 'https://www.flickr.com/photos/marietta_wood_works/21904325000/in/contacts/#favorited-by-39216764@N00',
    }, self.flickr.create(LIKE_OBJ).content)

  def test_photo_to_activity_uses_path_alias_if_username_has_spaces(self):
    photo = PHOTO_INFO['photo']
    photo['owner'].update({
      'username': 'Foo Bar',
      'path_alias': 'my_alias',
    })

    activity = self.flickr.photo_to_activity(photo)
    self.assert_equals({
      'objectType': 'person',
      'id': 'tag:flickr.com:my_alias',
      'username': 'my_alias',
      'displayName': 'Kyle Mahan',
      'image': {
        'url': 'https://farm5.staticflickr.com/4068/buddyicons/39216764@N00.jpg',
      },
    }, activity['object']['author'])
