# coding=utf-8
"""Flickr source class.

Uses Flickr's REST API https://www.flickr.com/services/api/

TODO: Fetching feeds with comments and/or favorites is very request
intensive right now. It would be ideal to find a way to batch
requests, make requests asynchronously, or make better calls to the
API itself. Maybe use flickr.activity.userPhotos
(https://www.flickr.com/services/api/flickr.activity.userPhotos.html)
when group_id=SELF.
"""

__author__ = ['Kyle Mahan <kyle@kylewm.com>']

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

import appengine_config
from oauth_dropins.webutil import util
from oauth_dropins import flickr_auth

from apiclient.errors import HttpError
from apiclient.http import BatchHttpRequest


class Flickr(source.Source):

  DOMAIN = 'flickr.com'
  NAME = 'Flickr'

  API_EXTRAS = ','.join(('date_upload', 'date_taken', 'views', 'media',
                         'description' 'tags', 'machine_tags', 'geo'))

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

    if activity_id:
      params['photo_id'] = activity_id
      method = 'flickr.photos.getInfo'
    else:
      params['extras'] = self.API_EXTRAS
      params['per_page'] = 50
      if group_id == source.SELF:
        params['user_id'] = user_id
        method = 'flickr.people.getPhotos'
      if group_id == source.FRIENDS:
        method = 'flickr.photos.getContactsPhotos'
      if group_id == source.ALL:
        method = 'flickr.photos.getRecent'

    assert method
    photos_resp = self.call_api_method(method, params)

    result = {'items': []}
    if activity_id:
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
          activity['object'].setdefault('tags', []).append(
            self.like_to_object(person, activity))

      result['items'].append(activity)

    return util.trim_nulls(result)

  def get_actor(self, user_id=None):
    """Get an ActivityStreams object of type 'person' given a Flickr user's nsid.
    If no user_id is provided, this method will make another API request to
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
      self.user_id = user_id = resp.get('person', {}).get('nsid')
    resp = self.call_api_method('flickr.people.getInfo', {'user_id': user_id})
    return self.user_to_actor(resp)

  def user_to_actor(self, resp):
    """Convert a Flickr user dict into an ActivityStreams actor.
    """
    person = resp.get('person', {})
    username = person.get('username', {}).get('_content')
    obj = util.trim_nulls({
      'objectType': 'person',
      'displayName': person.get('realname', {}).get('_content') or username,
      'image': {
        'url': self.get_user_image(person.get('iconfarm'),
                                   person.get('iconserver'),
                                   person.get('nsid')),
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
      logging.debug('checking comment id %s', comment.get('id'))
      # comment id is the in form ###-postid-commentid
      if (comment.get('id') == comment_id or
              comment.get('id').split('-')[-1] == comment_id):
        logging.debug('found comment matching %s', comment_id)
        return self.comment_to_object(comment, activity_id)

  def photo_to_activity(self, photo):
    """Convert a Flickr photo to an ActivityStreams object. Takes either
    data in the expanded form returned by flickr.photos.getInfo or the
    abbreviated form returned by flickr.people.getPhotos.

    Args:
      photo: dict response from Flickr

    Returns:
      dict, an ActivityStreams object
    """
    owner = photo.get('owner')
    owner_id = owner.get('nsid') if isinstance(owner, dict) else owner

    created = photo.get('dates', {}).get('taken') or photo.get('datetaken')
    published = util.maybe_timestamp_to_rfc3339(
      photo.get('dates', {}).get('posted') or photo.get('dateupload'))

    photo_permalink = 'https://www.flickr.com/photos/{}/{}/'.format(
      owner_id, photo.get('id'))

    title = photo.get('title')
    if isinstance(title, dict):
      title = title.get('_content', '')

    activity = {
      'id': self.tag_uri(photo.get('id')),
      'flickr_id': photo.get('id'),
      'url': photo_permalink,
      'actor': {
        'numeric_id': owner_id,
      },
      'object': {
        'displayName': title,
        'url': photo_permalink,
        'id': self.tag_uri(photo.get('id')),
        'image': {
          'url': 'https://farm{}.staticflickr.com/{}/{}_{}_{}.jpg'.format(
            photo.get('farm'), photo.get('server'),
            photo.get('id'), photo.get('secret'), 'b'),
        },
        'content': '\n'.join((
          title, photo.get('description', {}).get('_content', ''))),
        'objectType': 'photo',
        'created': created,
        'published': published,
      },
      'verb': 'post',
      'created': created,
      'published': published,
    }

    if isinstance(owner, dict):
      activity['object']['author'] = {
        'objectType': 'person',
        'displayName': owner.get('realname'),
        'username': owner.get('username'),
        'id': self.tag_uri(owner.get('username')),
        'image': {
          'url': self.get_user_image(owner.get('iconfarm'),
                                     owner.get('iconserver'),
                                     owner.get('nsid')),
        },
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

  def like_to_object(self, person, photo_activity):
    """Convert a Flickr favorite into an ActivityStreams like tag.

    Args:
      person: dict, the person object from Flickr
      photo_activity: dict, the ActivityStreams object representing
        the photo this like belongs to

    Returns:
      dict, an ActivityStreams object
    """
    return {
      'author': {
        'objectType': 'person',
        'displayName': person.get('realname'),
        'username': person.get('username'),
        'id': self.tag_uri(person.get('nsid')),
        'image': {
          'url': self.get_user_image(person.get('iconfarm'),
                                     person.get('iconserver'),
                                     person.get('nsid')),
        },
      },
      'created': util.maybe_timestamp_to_rfc3339(photo_activity.get('favedate')),
      'url': '{}#liked-by-{}'.format(
        photo_activity.get('url'), person.get('nsid')),
      'object': {'url': photo_activity.get('url')},
      'id': self.tag_uri('{}_liked_by_{}'.format(
        photo_activity.get('flickr_id'), person.get('nsid'))),
      'objectType': 'activity',
      'verb': 'like',
    }

  def comment_to_object(self, comment, photo_id):
    """Convert a Flickr comment json object to an ActivityStreams comment.

    Args:
      comment: dict, the comment object from Flickr
      photo_id: string, the Flickr ID of the photo that this comment belongs to

    Returns:
      dict, an ActivityStreams object
    """
    obj = {
      'objectType': 'comment',
      'url': comment.get('permalink'),
      'id': self.tag_uri(comment.get('id')),
      'inReplyTo': [{'id': self.tag_uri(photo_id)}],
      'content': comment.get('_content', ''),
      'published': util.maybe_timestamp_to_rfc3339(comment.get('datecreate')),
      'updated': util.maybe_timestamp_to_rfc3339(comment.get('datecreate')),
      'author': {
        'objectType': 'person',
        'displayName': comment.get('realname'),
        'username': comment.get('authorname'),
        'id': self.tag_uri(comment.get('author')),
        'url': self.user_url(comment.get('path_alias')),
        'image': {
          'url': self.get_user_image(comment.get('iconfarm'),
                                     comment.get('iconserver'),
                                     comment.get('author')),
        },
      }
    }
    self.postprocess_object(obj)
    return obj

  def get_user_image(self, farm, server, author):
    """Convert fields from a typical Flickr response into the buddy icon
    URL.

    ref: https://www.flickr.com/services/api/misc.buddyicons.html
    """
    return 'https://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
      farm, server, author)

  def user_url(self, handle):
    """Convert a user's screen name to their Flickr profile page URL.

    Args:
      handle: string, the Flickr user's screen name

    Returns:
      string, a profile URL
    """
    return handle and 'https://www.flickr.com/people/%s/' % handle
