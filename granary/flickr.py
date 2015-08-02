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
import mf2py
import urllib2


class Flickr(source.Source):

  DOMAIN = 'flickr.com'
  NAME = 'Flickr'

  def __init__(self, access_token_key, access_token_secret, user_id=None):
    """Constructor.

    Args:
      access_token_key: string, OAuth access token key
      access_token_secret: string, OAuth access token secret
      user_id: string, the logged in user's Flickr nsid (optional)
    """
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret
    self.user_id = user_id

  def call_api_method(self, method, params={}):
    """Call a Flickr API method.
    """
    return flickr_auth.call_api_method(
      method, params, self.access_token_key, self.access_token_secret)

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              search_query=None):
    """Get Flickr actvities
    """
    if user_id is None:
      user_id = 'me'
    if group_id is None:
      group_id = source.FRIENDS

    params = {}
    method = None
    solo = False
    extras = ','.join(('date_upload', 'date_taken', 'tags', 'machine_tags',
                      'views', 'media', 'tags', 'machine_tags', 'geo'))

    if activity_id:
      method = 'flickr.photos.getInfo'
      params['photo_id'] = activity_id
      solo = True
    elif group_id == source.SELF:
      method = 'flickr.people.getPhotos'
      params['user_id'] = user_id
      params['extras'] = extras
      params['per_page'] = 50
    elif group_id == source.FRIENDS:
      method = 'flickr.photos.getContactsPhotos'
      params['extras'] = extras
      params['per_page'] = 50
    elif group_id == source.ALL:
      method = 'flickr.photos.getRecent'
      params['extras'] = extras
      params['per_page'] = 50

    assert method
    logging.debug('calling %s with %s', method, params)
    photos_resp = self.call_api_method(method, params)
    logging.debug('response %s', json.dumps(photos_resp, indent=True))

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
    """Get an ActivityStreams object of type 'person' given a Flickr user's nsid.
    If no user_id is provided, this method will make another API requeset to
    find out the currently logged in user's id.

    Args:
      user_id: string, optional

    Returns:
      dict, an ActivityStreams object
    """
    if not user_id:
      user_id = self.user_id

    if not user_id:
      resp = self.call_api_method('flickr.people.getLimits')
      user_id = resp.get('person', {}).get('nsid')

    logging.debug('calling flickr.people.getInfo with user_id %s', user_id)
    resp = self.call_api_method('flickr.people.getInfo', {'user_id': user_id})

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
      'location': {
        'displayName': person.get('location', {}).get('_content'),
      },
      'username': username,
      'description': person.get('description', {}).get('_content'),
    })

    # fetch profile page to get url(s)
    profile_url = person.get('profileurl', {}).get('_content')
    if profile_url:
      try:
        logging.debug('fetching flickr profile page %s', profile_url)
        resp = urllib2.urlopen(
          profile_url, timeout=appengine_config.HTTP_TIMEOUT)
        profile_json = mf2py.parse(doc=resp, url=profile_url)
        # personal site is likely the first non-flickr url
        urls = profile_json.get('rels', {}).get('me', [])
        obj['urls'] = [{'value': u} for u in urls]
        obj['url'] = next(
          (u for u in urls if not u.startswith('https://www.flickr.com/')),
          None)
      except urllib2.URLError, e:
        logging.warning('could not fetch user homepage %s', profile_url)

    return self.postprocess_object(obj)

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
    """Convert a Flickr photo to an ActivityStreams object. Takes either
    data in the expanded form returned by flickr.photos.getInfo or the
    abbreviated form returned by flickr.people.getPhotos.
    """
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

    if isinstance(photo.get('tags'), dict):
      activity['object']['tags'] = [{
          'objectType': 'hashtag',
          'id': self.tag_uri(tag.get('id')),
          'url': 'https://www.flickr.com/search?tags={}'.format(
            tag.get('_content')),
          'displayName': tag.get('raw'),
        } for tag in photo.get('tags', {}).get('tag', [])]
    elif isinstance(photo.get('tags'), basestring):
      activity['object']['tags'] = [{
        'objectType': 'hashtag',
        'url': 'https://www.flickr.com/search?tags={}'.format(
          tag.strip()),
        'displayName': tag.strip(),
      } for tag in photo.get('tags').split(' ') if tag.strip()]

    self.postprocess_activity(activity)
    return activity

  def comment_to_object(self, comment, photo_id):
    """Convert a Flickr comment json object to an ActivityStreams comment.
    """
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
