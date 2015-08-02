"""Unit tests for flickr.py
"""
from __future__ import unicode_literals, print_function


import copy
import json
import urllib
import urllib2

from oauth_dropins.webutil import util

from oauth_dropins import appengine_config as od_appengine_config
from granary import appengine_config
from granary import flickr
from granary import source
from granary import testutil

__author__ = ['Kyle Mahan <kyle@kylewm.com>']


PHOTOS = {
  "photos": {
    "page": 1,
    "pages": 30,
    "perpage": 50,
    "total": "1461",
    "photo": [
      {
        "id": "8998787742",
        "owner": "39216764@N00",
        "secret": "89e6e03647",
        "server": "7459",
        "farm": 8,
        "title": "Percheron Thunder",
        "ispublic": 1,
        "isfriend": 0,
        "isfamily": 0,
        "dateupload": "1370799634",
        "datetaken": "2013-06-08 03:20:48",
        "datetakengranularity": 0,
        "datetakenunknown": 0,
        "views": "196",
        "tags": "oregon sistersrodeo",
        "machine_tags": "",
        "latitude": 0,
        "longitude": 0,
        "accuracy": 0,
        "context": 0,
        "media": "photo",
        "media_status": "ready"
      },
      {
        "id": "5227327325",
        "owner": "39216764@N00",
        "secret": "ec6180fb32",
        "server": "4104",
        "farm": 5,
        "title": "Emo dog & pun",
        "ispublic": 1,
        "isfriend": 0,
        "isfamily": 0,
        "dateupload": "1291338979",
        "datetaken": "2010-11-27 12:54:33",
        "datetakengranularity": 0,
        "datetakenunknown": 0,
        "views": "176",
        "tags": "idyllwild emodog",
        "machine_tags": "",
        "latitude": 33.746663,
        "longitude": -116.711668,
        "accuracy": 15,
        "context": 0,
        "place_id": "vaJN5r5TVrjDquPG",
        "woeid": "2426547",
        "geo_is_family": 0,
        "geo_is_friend": 0,
        "geo_is_contact": 0,
        "geo_is_public": 1,
        "media": "photo",
        "media_status": "ready"
      },
      {
        "id": "5227922370",
        "owner": "39216764@N00",
        "secret": "5f19cb9767",
        "server": "5246",
        "farm": 6,
        "title": "Candy canes",
        "ispublic": 1,
        "isfriend": 0,
        "isfamily": 0,
        "dateupload": "1291338921",
        "datetaken": "2010-11-26 17:50:30",
        "datetakengranularity": 0,
        "datetakenunknown": 0,
        "views": "102",
        "tags": "idyllwild",
        "machine_tags": "",
        "latitude": 33.746288,
        "longitude": -116.712441,
        "accuracy": 16,
        "context": 0,
        "place_id": "vaJN5r5TVrjDquPG",
        "woeid": "2426547",
        "geo_is_family": 0,
        "geo_is_friend": 0,
        "geo_is_contact": 0,
        "geo_is_public": 1,
        "media": "photo",
        "media_status": "ready"
      }
    ]
  },
  "stat": "ok"
}

PHOTO_INFO = {
  "photo": {
    "id": "5227922370",
    "secret": "5f19cb9767",
    "server": "5246",
    "farm": 6,
    "dateuploaded": "1291338921",
    "isfavorite": 0,
    "license": 2,
    "safety_level": 0,
    "rotation": 0,
    "originalsecret": "aa94c24f68",
    "originalformat": "jpg",
    "owner": {
      "nsid": "39216764@N00",
      "username": "kindofblue115",
      "realname": "Kyle Mahan",
      "location": "San Diego, CA, USA",
      "iconserver": "4068",
      "iconfarm": 5,
      "path_alias": "kindofblue115"
    },
    "title": {
      "_content": "Candy canes"
    },
    "description": {
      "_content": ""
    },
    "visibility": {
      "ispublic": 1,
      "isfriend": 0,
      "isfamily": 0
    },
    "dates": {
      "posted": "1291338921",
      "taken": "2010-11-26 17:50:30",
      "takengranularity": 0,
      "takenunknown": 0,
      "lastupdate": "1295288643"
    },
    "permissions": {
      "permcomment": 3,
      "permaddmeta": 2
    },
    "views": "102",
    "editability": {
      "cancomment": 1,
      "canaddmeta": 1
    },
    "publiceditability": {
      "cancomment": 1,
      "canaddmeta": 0
    },
    "usage": {
      "candownload": 1,
      "canblog": 1,
      "canprint": 1,
      "canshare": 1
    },
    "comments": {
      "_content": 1
    },
    "notes": {
      "note": [

      ]
    },
    "people": {
      "haspeople": 0
    },
    "tags": {
      "tag": [
        {
          "id": "4942564-5227922370-22730",
          "author": "39216764@N00",
          "authorname": "kindofblue115",
          "raw": "idyllwild",
          "_content": "idyllwild",
          "machine_tag": 0
        }
      ]
    },
    "location": {
      "latitude": 33.746288,
      "longitude": -116.712441,
      "accuracy": 16,
      "context": 0,
      "locality": {
        "_content": "Idyllwild-Pine Cove",
        "place_id": "vaJN5r5TVrjDquPG",
        "woeid": "2426547"
      },
      "county": {
        "_content": "Riverside",
        "place_id": "ZNLarLZQUL98qkEJMQ",
        "woeid": "12587702"
      },
      "region": {
        "_content": "California",
        "place_id": "NsbUWfBTUb4mbyVu",
        "woeid": "2347563"
      },
      "country": {
        "_content": "United States",
        "place_id": "nz.gsghTUb4c2WAecA",
        "woeid": "23424977"
      },
      "place_id": "vaJN5r5TVrjDquPG",
      "woeid": "2426547"
    },
    "geoperms": {
      "ispublic": 1,
      "iscontact": 0,
      "isfriend": 0,
      "isfamily": 0
    },
    "urls": {
      "url": [
        {
          "type": "photopage",
          "_content": "https://www.flickr.com/photos/kindofblue115/5227922370/"
        }
      ]
    },
    "media": "photo"
  },
  "stat": "ok"
}

PHOTO_FAVORITES = {
  "photo": {
    "person": [
      {
        "nsid": "95922884@N00",
        "username": "absentmindedprof",
        "realname": "Jennifer",
        "favedate": "1291599546",
        "iconserver": "5343",
        "iconfarm": 6,
        "contact": 1,
        "friend": 1,
        "family": 0
      }
    ],
    "id": "5227922370",
    "secret": "5f19cb9767",
    "server": "5246",
    "farm": 6,
    "page": 1,
    "pages": 1,
    "perpage": 10,
    "total": 1
  },
  "stat": "ok"
}

PHOTO_COMMENTS = {
  "comments": {
    "photo_id": "5227922370",
    "comment": [
      {
        "id": "4942564-5227922370-72157625845945286",
        "author": "36398523@N00",
        "authorname": "if winter ends",
        "iconserver": "108",
        "iconfarm": 1,
        "datecreate": "1295288643",
        "permalink": "https://www.flickr.com/photos/kindofblue115/5227922370/#comment72157625845945286",
        "path_alias": "if_winter_ends",
        "realname": "",
        "_content": "Love this!"
      }
    ]
  },
  "stat": "ok"
}

PERSON_INFO = {
  "person": {
    "id": "39216764@N00",
    "nsid": "39216764@N00",
    "ispro": 0,
    "can_buy_pro": 0,
    "iconserver": "4068",
    "iconfarm": 5,
    "path_alias": "kindofblue115",
    "has_stats": 1,
    "username": {
      "_content": "kindofblue115"
    },
    "realname": {
      "_content": "Kyle Mahan"
    },
    "mbox_sha1sum": {
      "_content": "049cf71f4b437dc0ab497e107f7b7d2c55a096d4"
    },
    "location": {
      "_content": "San Diego, CA, USA"
    },
    "timezone": {
      "label": "Pacific Time (US & Canada); Tijuana",
      "offset": "-08:00",
      "timezone_id": "PST8PDT"
    },
    "description": {
      "_content": "Trying a little bit of everything"
    },
    "photosurl": {
      "_content": "https://www.flickr.com/photos/kindofblue115/"
    },
    "profileurl": {
      "_content": "https://www.flickr.com/people/kindofblue115/"
    },
    "mobileurl": {
      "_content": "https://m.flickr.com/photostream.gne?id=4942564"
    },
    "photos": {
      "firstdatetaken": {
        "_content": "2005-12-27 18:29:07"
      },
      "firstdate": {
        "_content": "1159222380"
      },
      "count": {
        "_content": "1461"
      },
      "views": {
        "_content": "7459"
      }
    }
  },
  "stat": "ok"
}

ACTOR = {
  'objectType': 'person',
  'displayName': 'Kyle Mahan',
  'image': {
    'url': 'https://farm5.staticflickr.com/4068/buddyicons/39216764@N00.jpg',
  },
  'id': 'tag:flickr.com:kindofblue115',
  'location': {'displayName': 'San Diego, CA, USA'},
  'description': 'Trying a little bit of everything',
  'url': 'https://kylewm.com/',
  'urls': [
    {'value': 'https://www.flickr.com/people/kindofblue115/'},
    {'value': 'https://www.flickr.com/people/kindofblue115/contacts/'},
    {'value': 'https://kylewm.com/'},
  ],
  'username': 'kindofblue115',
  'numeric_id': '39216764@N00',
}

PROFILE_HTML = """
<html>
  <body>
    <a href="https://www.flickr.com/people/kindofblue115/" rel="me">Profile</a>
    <a href="https://www.flickr.com/people/kindofblue115/contacts/" rel="me">Contacts</a>
    <a href="https://kylewm.com/" rel="me">kylewm.com</a>
  </body>
</html>
"""

class FlickrTest(testutil.TestCase):

  def setUp(self):
    super(FlickrTest, self).setUp()
    appengine_config.FLICKR_APP_KEY = 'fake'
    appengine_config.FLICKR_APP_SECRET = 'fake'
    od_appengine_config.FLICKR_APP_KEY = 'fake'
    od_appengine_config.FLICKR_APP_SECRET = 'fake'
    self.flickr = flickr.Flickr('key', 'secret')

  def expect_call_api_method(self, method, params, result):
    full_params = {
      'nojsoncallback': 1,
      'format': 'json',
      'api_key': 'fake',
      'method': method,
    }
    full_params.update(params)
    self.expect_urlopen('https://api.flickr.com/services/rest?'
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
      'flickr.people.getLimits', {}, json.dumps({"person": {
        "nsid": "39216764@N00",
        "photos": {"maxdisplaypx": "1024", "maxupload": "209715200"},
        "videos": {"maxduration": "180", "maxupload": "1073741824"}
      }, "stat": "ok"}))

    self.expect_call_api_method(
      'flickr.people.getInfo', {'user_id': '39216764@N00'},
      json.dumps(PERSON_INFO))

    self.expect_urlopen(
      'https://www.flickr.com/people/kindofblue115/',
      PROFILE_HTML)

    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.flickr.get_actor())
