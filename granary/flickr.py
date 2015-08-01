from apiclient.errors import HttpError
from apiclient.http import BatchHttpRequest
from oauth_dropins.webutil import util
from oauth_dropins import flickr_auth

import appengine_config
import datetime
import functools
import itertools
import json
import logging
import requests
import source
import sys


class Flickr(source.Source):

  DOMAIN = 'flickr.com'
  NAME = 'Flickr'

  def __init__(self, access_token_key, access_token_secret, user_id):
    """Constructor.

    Args:
      access_token_key: string, OAuth access token key
      access_token_secret: string, OAuth access token secret
    """
    logging.debug('token key: %s', access_token_key)
    logging.debug('token sec: %s', access_token_secret)
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret
    self.user_id = user_id

  def call_api_method(self, method, params):
    return flickr_auth.call_api_method(
      method, params, self.access_token_key, self.access_token_secret)

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              search_query=None):
    if user_id is None:
      user_id = 'me'
    if group_id is None:
      group_id = source.FRIENDS

    params = {}
    method = None
    solo = False

    if activity_id:
      method = 'flickr.photos.getInfo'
      params['photo_id'] = activity_id
      solo = True
    elif group_id == source.SELF:
      method = 'flickr.people.getPhotos'
      params['user_id'] = user_id
      params['extras'] = 'date_upload,date_taken,tags,machine_tags,views,media'
      params['per_page'] = 50
    elif group_id == source.FRIENDS:
      method = 'flickr.photos.getContactsPhotos'
      params['extras'] = 'date_upload,date_taken,tags,machine_tags,views,media'
      params['per_page'] = 50
    elif group_id == source.ALL:
      method = 'flickr.photos.getRecent'
      params['extras'] = 'date_upload,date_taken,tags,machine_tags,views,media'
      params['per_page'] = 50

    assert method
    logging.debug('calling %s with %s', method, params)
    photos_resp = self.call_api_method(method, params)
    logging.debug('response %s', json.dumps(photos_resp, indent=True))

    # activities_by_photo = {}
    # if fetch_replies and group_id == source.SELF:
    #   activity_resp = self.call_api_method('flickr.activity.userPhotos', {
    #     'per_page': 50})
    #   for item in activity_resp.get('items', []):
    #     for event in item.get('activity', {}).get('event', []):
    #       activities_by_photo.setdefault(item.get('id'), []).append(event)

    result = {
      'items': []
    }

    if solo:
      photos = [photos_resp.get('photo', {})]
    else:
      photos = photos_resp.get('photos', {}).get('photo', [])

    for photo in photos:
      activity = self.photo_to_activity(photo)

      # TODO consider using 'flickr.activity.userPhotos' when group_id=@self,
      # gives all recent comments and faves, instead of hitting the API for
      # each photo
      if fetch_replies:
        replies = []
        comments_resp = self.call_api_method('flickr.photos.comments.getList', {
          'photo_id': photo.get('id'),
          'max_comment_date': etag,
        })
        for comment in comments_resp.get('comments', {}).get('comment', []):
          replies.append(self.comment_to_object(comment, photo.get('id')))
          activity['object']['replies'] = {
            'items': replies,
            'totalItems': len(replies),
          }

      if fetch_likes:
        faves_resp = self.call_api_method('flickr.photos.getFavorites', {
          'photo_id': photo.get('id'),
        })
        for person in faves_resp.get('photo', {}).get('person', []):
          activity['object'].setdefault('tags', []).append({
            'author': {
              'objectType': 'person',
              'displayName': person.get('realname'),
              'username': person.get('username'),
              'id': self.tag_uri(person.get('nsid')),
              'image': {
                'url': 'https://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
                  person.get('iconfarm'), person.get('iconserver'),
                  person.get('nsid')),
              },
            },
            'url': '{}#liked-by-#{}'.format(
              activity.get9('url'), person.get('nsid')),
            'object': {'url': activity.get('url')},
            'id': self.tag_uri('{}_liked_by_{}'.format(
              photo.get('id'), person.get('nsid'))),
            'objectType': 'activity',
            'verb': 'like',
          })

      result['items'].append(activity)

    return result

  def get_actor(self, user_id=None):
    if user_id is None:
      user_id = self.user_id

    logging.debug('flickr.people.getInfo with user_id %s', user_id)
    resp = self.call_api_method('flickr.people.getInfo', {'user_id': user_id})
    logging.debug('flickr.people.getInfo resp %s', json.dumps(resp, indent=True))

    person = resp.get('person', {})
    username = person.get('username', {}).get('_content')
    obj = util.trim_nulls({
      'objectType': 'person',
      'displayName': person.get('realname', {}).get('_content') or username,
      'image': {
        'url': 'https://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
          person.get('iconfarm'), person.get('iconserver'), person.get('nsid'))
      },
      'id': self.tag_uri(username),
      # numeric_id is our own custom field that always has the source's numeric
      # user id, if available.
      'numeric_id': person.get('nsid'),
      'url': person.get('profileurl', {}).get('_content'),
      'location': {
        'displayName': person.get('location', {}).get('_content'),
      },
      'username': username,
      'description': person.get('description', {}).get('_content'),
    })
    logging.debug('actor %s', json.dumps(obj, indent=True))
    return obj

  def get_comment(self, comment_id, activity_id, activity_author_id=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, required
      activity_author_id: string activity author id, ignored
    """
    resp = self.call_api_method('flickr.photos.comments.getList', {
      'photo_id': activity_id,
    })

    for comment in resp.get('comments', {}).get('comment', []):
      if comment.get('id') == comment_id:
        return self.comment_to_object(resp)

  def photo_to_activity(self, photo):
    owner = photo.get('owner')
    if isinstance(owner, dict):
      owner = owner.get('nsid')

    created = photo.get('dates', {}).get('taken') or photo.get('datetaken')
    published = self.reformat_unix_time(
      photo.get('dates', {}).get('posted') or photo.get('dateupload'))

    photo_permalink = 'https://flickr.com/photos/{}/{}'.format(
      owner, photo.get('id'))

    activity = {
      'url': 'https://flickr.com/photos/{}/{}'.format(owner, photo.get('id')),
      'actor': {
        'numeric_id': owner,
      },
      'object': {
        'displayName': photo.get('title'),
        'url': photo_permalink,
        'id': self.tag_uri(photo.get('id')),
        'image': {
          'url': 'https://farm{}.staticflickr.com/{}/{}_{}_{}.jpg'.format(
            photo.get('farm'), photo.get('server'),
            photo.get('id'), photo.get('secret'), 'b'),
        },
        'objectType': 'photo',
        'created': created,
        'published': published,
      },
      'verb': 'post',
      'created': created,
      'published': published,
    }
    self.postprocess_activity(activity)
    return activity

  def comment_to_object(self, comment, photo_id):
    obj = {
      'objectType': 'comment',
      'url': comment.get('permalink'),
      'id': self.tag_uri('{}_{}'.format(photo_id, comment.get('id'))),
      'inReplyTo': [{'id': self.tag_uri(photo_id)}],
      'content': comment.get('_content'),
      'created': self.reformat_unix_time(comment.get('datecreate')),
      'updated': self.reformat_unix_time(comment.get('datecreate')),
      'author': {
        'objectType': 'person',
        'displayName': comment.get('realname'),
        'username': comment.get('authorname'),
        'id': self.tag_uri(comment.get('author')),
        'image': {
          'url': 'https://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
            comment.get('iconfarm'), comment.get('iconserver'),
            comment.get('author')),
        },
      }
    }
    self.postprocess_object(obj)
    return obj

  def reformat_unix_time(self, ts):
    return ts and datetime.datetime.fromtimestamp(int(ts)).isoformat()


PHOTOS = """
{
 "stat": "ok",
 "photos": {
  "total": "1461",
  "page": 1,
  "perpage": 100,
  "pages": 15,
  "photo": [
   {
    "views": "32",
    "tags": "",
    "secret": "e6a57986ff",
    "datetakengranularity": "0",
    "id": "14921050422",
    "datetakenunknown": 0,
    "isfriend": 0,
    "server": "3872",
    "media_status": "ready",
    "media": "photo",
    "farm": 4,
    "title": "14806801522_ae17468aa1",
    "datetaken": "2014-08-14 17:29:02",
    "isfamily": 0,
    "ispublic": 1,
    "dateupload": "1408062546",
    "machine_tags": "",
    "owner": "39216764@N00"
   },
"""

PHOTO_INFO = """
{
 "stat": "ok",
 "photo": {
  "comments": {
   "_content": "0"
  },
  "server": "7459",
  "title": {
   "_content": "Percheron Thunder"
  },
  "editability": {
   "canaddmeta": 1,
   "cancomment": 1
  },
  "visibility": {
   "ispublic": 1,
   "isfamily": 0,
   "isfriend": 0
  },
  "id": "8998787742",
  "permissions": {
   "permcomment": 3,
   "permaddmeta": 2
  },
  "media": "photo",
  "rotation": 0,
  "originalsecret": "f129836c24",
  "owner": {
   "location": "San Diego, CA, USA",
   "iconserver": "4068",
   "iconfarm": 5,
   "path_alias": "kindofblue115",
   "username": "kindofblue115",
   "nsid": "39216764@N00",
   "realname": "Kyle Mahan"
  },
  "farm": 8,
  "safety_level": "0",
  "originalformat": "jpg",
  "license": "2",
  "secret": "89e6e03647",
  "description": {
   "_content": "This guy was driving the 6 biggest horses I've ever seen"
  },
  "publiceditability": {
   "canaddmeta": 0,
   "cancomment": 1
  },
  "people": {
   "haspeople": 0
  },
  "dates": {
   "takengranularity": "0",
   "lastupdate": "1370800238",
   "takenunknown": 0,
   "taken": "2013-06-08 03:20:48",
   "posted": "1370799634"
  },
  "views": "196",
  "dateuploaded": "1370799634",
  "isfavorite": 0,
  "usage": {
   "canshare": 1,
   "canprint": 1,
   "candownload": 1,
   "canblog": 1
  },
  "tags": {
   "tag": [
    {
     "raw": "oregon",
     "id": "4942564-8998787742-1228",
     "_content": "oregon",
     "author": "39216764@N00",
     "authorname": "kindofblue115",
     "machine_tag": false
    },
    {
     "raw": "sisters rodeo",
     "id": "4942564-8998787742-24046921",
     "_content": "sistersrodeo",
     "author": "39216764@N00",
     "authorname": "kindofblue115",
     "machine_tag": false
    }
   ]
  },
  "urls": {
   "url": [
    {
     "type": "photopage",
     "_content": "https://www.flickr.com/photos/kindofblue115/8998787742/"
    }
   ]
  },
  "notes": {
   "note": []
  }
 }
}
"""

PHOTO_COMMENTS = """
{
  "comments": {
    "photo_id": "8998784856",
    "comment": [
      {
        "id": "4942564-8998784856-72157656523655185",
        "author": "39216764@N00",
        "authorname": "kylewm",
        "iconserver": "4068",
        "iconfarm": 5,
        "datecreate": "1438185302",
        "permalink": "https:\/\/www.flickr.com\/photos\/kindofblue115\/8998784856\/#comment72157656523655185",
        "path_alias": "kindofblue115",
        "realname": "Kyle Mahan",
        "_content": "This is a test comment"
      }
    ]
  },
  "stat": "ok"
}
"""

ACTIVITY_USER_PHOTOS = """
{
 "stat": "ok",
 "items": {
  "total": 4,
  "page": 1,
  "pages": 1,
  "item": [
   {
    "iconserver": "4068",
    "realname": "Kyle Mahan",
    "comments": 1,
    "ownername": "kylewm",
    "id": "8998784856",
    "faves": 0,
    "secret": "5145958eaa",
    "server": "5345",
    "farm": 6,
    "views": 93,
    "type": "photo",
    "iconfarm": 5,
    "notes": 0,
    "title": {
     "_content": "Rodeo sunset"
    },
    "owner": "39216764@N00",
    "activity": {
     "event": [
      {
       "iconserver": "4068",
       "realname": "Kyle Mahan",
       "username": "kylewm",
       "user": "39216764@N00",
       "commentid": "72157656523655185",
       "_content": "This is a test comment",
       "type": "comment",
       "dateadded": "1438185302",
       "iconfarm": 5
      }
     ]
    },
    "media": "photo"
   },
   {
    "iconserver": "4068",
    "realname": "Kyle Mahan",
    "comments": 3,
    "ownername": "kylewm",
    "id": "4075466518",
    "faves": 1,
    "secret": "80f29254ea",
    "server": "2528",
    "farm": 3,
    "views": 60,
    "type": "photo",
    "iconfarm": 5,
    "notes": 0,
    "title": {
     "_content": "Yellow"
    },
    "owner": "39216764@N00",
    "activity": {
     "event": [
      {
       "iconserver": "2824",
       "realname": "John Brian Kirby",
       "username": "9gon",
       "user": "68269724@N06",
       "type": "fave",
       "dateadded": "1436889861",
       "iconfarm": 3
      }
     ]
    },
    "media": "photo"
   },
   {
    "iconserver": "4068",
    "realname": "Kyle Mahan",
    "comments": 1,
    "ownername": "kylewm",
    "id": "4739173072",
    "faves": 3,
    "secret": "fa3cdd0198",
    "server": "4134",
    "farm": 5,
    "views": 163,
    "type": "photo",
    "iconfarm": 5,
    "notes": 0,
    "title": {
     "_content": "Roy G"
    },
    "owner": "39216764@N00",
    "activity": {
     "event": [
      {
       "iconserver": "2824",
       "realname": "John Brian Kirby",
       "username": "9gon",
       "user": "68269724@N06",
       "type": "fave",
       "dateadded": "1436889825",
       "iconfarm": 3
      }
     ]
    },
    "media": "photo"
   },
   {
    "iconserver": "4068",
    "realname": "Kyle Mahan",
    "comments": 2,
    "ownername": "kylewm",
    "id": "5064358742",
    "faves": 1,
    "secret": "7a3846c1a1",
    "server": "4113",
    "farm": 5,
    "views": 159,
    "type": "photo",
    "iconfarm": 5,
    "notes": 0,
    "title": {
     "_content": "Departure of the bride & groom"
    },
    "owner": "39216764@N00",
    "activity": {
     "event": [
      {
       "iconserver": "2824",
       "realname": "John Brian Kirby",
       "username": "9gon",
       "user": "68269724@N06",
       "type": "fave",
       "dateadded": "1436889807",
       "iconfarm": 3
      }
     ]
    },
    "media": "photo"
   }
  ],
  "perpage": 50
 }
}
"""

PERSON_INFO = """
{
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
      "_content": "Trying a little bit of everything, usually with a D40 now more or less permanently affixed with a 35mm f\/1.8 lens, occasionally with a beautiful old Minolta Hi-Matic 7s rangefinder, even more occasionally with a pinhole camera made out of a cereal box :)\n\nI don't like food photography nearly as much as I probably make it look like -- I do like cooking and eating that much though!\n\n\n<a href=\"http:\/\/www.flickriver.com\/photos\/kindofblue115\/\" rel=\"nofollow\">\n<img src=\"https:\/\/s.yimg.com\/pw\/images\/spaceout.gif\" data-blocked-src=\"https:\/\/ec.yimg.com\/ec?url=http%3A%2F%2Fwww.flickriver.com%2Fbadge%2Fuser%2Fall%2Frecent%2Fshuffle%2Fmedium-horiz%2Fffffff%2F333333%2F39216764%40N00.jpg&amp;t=1438359583&amp;sig=5tYM6QkpgJsvYIjzVJcfcA--~C\" title=\"Click to load remote image from www.flickriver.com\" onclick=\"this.onload=this.onerror=function(){this.className=this.className.replace('blocked-loading','blocked-loaded');this.onload=this.onerror=null};this.className=this.className.replace('blocked-image','blocked-loading');this.src=this.getAttribute('data-blocked-src');this.title='';this.onclick=null;if(this.parentNode && this.parentNode.nodeName == 'A') {return false;}\" class=\"blocked-image notsowide\" \/><\/a>\n\nAnd some photos that I find inspirational or otherwise awesome:\n<a href=\"http:\/\/www.flickriver.com\/photos\/kindofblue115\/favorites\/\" rel=\"nofollow\">\n<img src=\"https:\/\/s.yimg.com\/pw\/images\/spaceout.gif\" data-blocked-src=\"https:\/\/ec.yimg.com\/ec?url=http%3A%2F%2Fwww.flickriver.com%2Fbadge%2Fuser%2Ffavorites%2Frecent%2Fshuffle%2Fmedium-horiz%2Fffffff%2F333333%2F39216764%40N00.jpg&amp;t=1438359583&amp;sig=T79khy3J2Q_uUNCNnIgAOw--~C\" title=\"Click to load remote image from www.flickriver.com\" onclick=\"this.onload=this.onerror=function(){this.className=this.className.replace('blocked-loading','blocked-loaded');this.onload=this.onerror=null};this.className=this.className.replace('blocked-image','blocked-loading');this.src=this.getAttribute('data-blocked-src');this.title='';this.onclick=null;if(this.parentNode && this.parentNode.nodeName == 'A') {return false;}\" class=\"blocked-image notsowide\" \/><\/a>"
    },
    "photosurl": {
      "_content": "https:\/\/www.flickr.com\/photos\/kindofblue115\/"
    },
    "profileurl": {
      "_content": "https:\/\/www.flickr.com\/people\/kindofblue115\/"
    },
    "mobileurl": {
      "_content": "https:\/\/m.flickr.com\/photostream.gne?id=4942564"
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
"""
