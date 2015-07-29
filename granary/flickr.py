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

  def __init__(self, access_token_key, access_token_secret):
    """Constructor.

    Args:
      access_token_key: string, OAuth access token key
      access_token_secret: string, OAuth access token secret
    """
    logging.debug('token key: %s', access_token_key)
    logging.debug('token sec: %s', access_token_secret)
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret

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

    if activity_id:
      method = 'flickr.photos.getInfo'
      params['photo_id'] = activity_id
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

    for photo in photos_resp.get('photos', {}).get('photo', []):
      photo_permalink = 'https://flickr.com/photos/{}/{}'.format(
        photo.get('owner'), photo.get('id'))
      activity = {
        'url': 'https://flickr.com/photos/{}/{}'.format(
          photo.get('owner'), photo.get('id')),
        'actor': {
          'numeric_id': photo.get('owner'),
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
          'created': photo.get('datetaken'),
          'published': self.reformat_unix_time(photo.get('dateupload')),
        },
        'verb': 'post',
        'created': photo.get('datetaken'),
        'published': self.reformat_unix_time(photo.get('dateupload')),
      }

      if fetch_replies or True:
        replies = []
        comments_resp = self.call_api_method('flickr.photos.comments.getList', {
          'photo_id': photo.get('id'),
        })
        for comment in comments_resp.get('comments', {}).get('comment', []):
          replies.append({
            'objectType': 'comment',
            'url': comment.get('permalink'),
            'id': self.tag_uri('{}_{}'.format(
              photo.get('id'), comment.get('id'))),
            'inReplyTo': [{'id': self.tag_uri(photo.get('id'))}],
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
          })

          activity['object']['replies'] = {
            'items': util.trim_nulls(replies),
            'totalItems': len(replies),
          }

      if fetch_likes or True:
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
              photo_permalink, person.get('nsid')),
            'object': {'url': photo_permalink},
            'id': self.tag_uri('{}_liked_by_{}'.format(
              photo.get('id'), person.get('nsid'))),
            'objectType': 'activity',
            'verb': 'like',
          })

      result['items'].append(activity)

    return result

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
