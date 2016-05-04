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

import copy
import datetime
import functools
import itertools
import json
import logging
import requests
import source
import sys
import mf2py
import mf2util
import urllib2
import urlparse

import appengine_config
from oauth_dropins.webutil import util
from oauth_dropins import flickr_auth

from apiclient.errors import HttpError
from apiclient.http import BatchHttpRequest


class Flickr(source.Source):

  DOMAIN = 'flickr.com'
  BASE_URL = 'https://www.flickr.com/'
  NAME = 'Flickr'

  API_EXTRAS = ','.join(('date_upload', 'date_taken', 'views', 'media',
                         'description', 'tags', 'machine_tags', 'geo',
                         'path_alias'))

  def __init__(self, access_token_key, access_token_secret,
               user_id=None, path_alias=None):
    """Constructor.

    If they are not provided, user_id and path_alias will be looked up via the
    API on first use.

    Args:
      access_token_key: string, OAuth access token key
      access_token_secret: string, OAuth access token secret
      user_id: string, the logged in user's Flickr nsid. (optional)
      path_alias: string, the logged in user's path_alias, replaces user_id in
        canonical profile and photo urls (optional)
    """
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret
    self._user_id = user_id
    self._path_alias = path_alias

  def call_api_method(self, method, params={}):
    """Call a Flickr API method.
    """
    return flickr_auth.call_api_method(
      method, params, self.access_token_key, self.access_token_secret)

  def upload(self, params, file):
    """Upload a photo or video via the Flickr API.
    """
    return flickr_auth.upload(
      params, file, self.access_token_key, self.access_token_secret)

  def create(self, obj, include_link=source.OMIT_LINK,
             ignore_formatting=False):
    """Creates a photo, comment, or favorite.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose content will be a dict with 'id', 'url',
      and 'type' keys (all optional) for the newly created Flickr
      object (or None)

    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Preview creation of a photo, comment, or favorite.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose description will be an HTML summary of
      what publishing will do, and whose content will be an HTML preview
      of the result (or None)
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates or previews creating for the previous two methods.

    https://www.flickr.com/services/api/upload.api.html
    https://www.flickr.com/services/api/flickr.photos.comments.addComment.html
    https://www.flickr.com/services/api/flickr.favorites.add.html
    https://www.flickr.com/services/api/flickr.photos.people.add.html

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: string
      ignore_formatting: boolean

    Return:
      a CreationResult
    """
    # photo, comment, or like
    type = source.object_type(obj)
    logging.debug('publishing object type %s to Flickr', type)
    link_text = '(Originally published at: %s)' % obj.get('url')

    image_url = util.get_first(obj, 'image', {}).get('url')
    video_url = util.get_first(obj, 'stream', {}).get('url')
    content = self._content_for_create(obj, ignore_formatting=ignore_formatting,
                                       strip_first_video_tag=bool(video_url))

    if (video_url or image_url) and type in ('note', 'article'):
      name = obj.get('displayName')
      people = self._get_person_tags(obj)
      hashtags = [t.get('displayName') for t in obj.get('tags', [])
                  if t.get('objectType') == 'hashtag' and t.get('displayName')]
      lat = obj.get('location', {}).get('latitude')
      lng = obj.get('location', {}).get('longitude')

      # if name does not represent an explicit title, then we'll just
      # use it as the title and wipe out the content
      if name and content and not mf2util.is_name_a_title(name, content):
        name = content
        content = None

      # add original post link
      if include_link == source.INCLUDE_LINK:
        content = ((content + '\n\n') if content else '') + link_text

      if preview:
        preview_content = ''
        if name:
          preview_content += '<h4>%s</h4>' % name
        if content:
          preview_content += '<div>%s</div>' % content
        if hashtags:
          preview_content += '<div> %s</div>' % ' '.join('#' + t for t in hashtags)
        if people:
          preview_content += '<div> with %s</div>' % ', '.join(
            ('<a href="%s">%s</a>' % (
              p.get('url'), p.get('displayName') or 'User %s' % p.get('id'))
             for p in people))
        if lat and lng:
          preview_content += '<div> at <a href="https://maps.google.com/maps?q=%s,%s">%s, %s</a></div>' % (lat, lng, lat, lng)

        if video_url:
          preview_content += ('<video controls src="%s"><a href="%s">this video'
                              '</a></video>' % (video_url, video_url))
        else:
          preview_content += '<img src="%s" />' % image_url

        return source.creation_result(content=preview_content, description='post')

      params = []
      if name:
        params.append(('title', name))
      if content:
        params.append(('description', content))
      if hashtags:
        params.append(
          ('tags', ','.join('"%s"' % t if ' ' in t else t for t in hashtags)))

      file = util.urlopen(video_url or image_url)
      resp = self.upload(params, file)
      photo_id = resp.get('id')
      resp.update({
        'type': 'post',
        'url': self.photo_url(self.path_alias() or self.user_id(), photo_id),
      })
      if video_url:
        resp['granary_message'] = \
          "Note that videos take time to process before they're visible."

      # add person tags
      for person_id in sorted(p.get('id') for p in people):
        self.call_api_method('flickr.photos.people.add', {
          'photo_id': photo_id,
          'user_id': person_id,
        })

      # add location
      if lat and lng:
        self.call_api_method('flickr.photos.geo.setLocation', {
            'photo_id': photo_id,
            'lat': lat,
            'lon': lng,
        })

      return source.creation_result(resp)

    base_obj = self.base_object(obj)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')

    # maybe a comment on a flickr photo?
    if type == 'comment' or obj.get('inReplyTo'):
      if not base_id:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a photo to comment on.',
          error_html='Could not find a photo to <a href="http://indiewebcamp.com/reply">comment on</a>. '
          'Check that your post has an <a href="http://indiewebcamp.com/comment">in-reply-to</a> '
          'link to a Flickr photo or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Flickr.')

      if include_link == source.INCLUDE_LINK:
        content += '\n\n' + link_text
      if preview:
        return source.creation_result(
          content=content,
          description='comment on <a href="%s">this photo</a>.' % base_url)

      resp = self.call_api_method('flickr.photos.comments.addComment', {
        'photo_id': base_id,
        'comment_text': content,
      })
      resp = resp.get('comment', {})
      resp.update({
        'type': 'comment',
        'url': resp.get('permalink'),
      })
      return source.creation_result(resp)

    if type == 'like':
      if not base_id:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a photo to favorite.',
          error_html='Could not find a photo to <a href="http://indiewebcamp.com/like">favorite</a>. '
          'Check that your post has an <a href="http://indiewebcamp.com/like">like-of</a> '
          'link to a Flickr photo or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Flickr.')
      if preview:
        return source.creation_result(
          description='favorite <a href="%s">this photo</a>.' % base_url)

      # this method doesn't return any data
      self.call_api_method('flickr.favorites.add', {
        'photo_id': base_id,
      })
      # TODO should we canonicalize the base_url (e.g. removing trailing path
      # info like "/in/contacts/")
      return source.creation_result({
        'type': 'like',
        'url': '%s#favorited-by-%s' % (base_url, self.user_id()),
      })

    return source.creation_result(
      abort=False,
      error_plain='Cannot publish type=%s to Flickr.' % type,
      error_html='Cannot publish type=%s to Flickr.' % type)

  def _get_person_tags(self, obj):
    """Extract person tags that refer to Flickr users.

    Uses https://www.flickr.com/services/api/flickr.urls.lookupUser.html
    to find the NSID for a particular URL.

    Args:
      obj: ActivityStreams object that may contain person targets

    Returns:
      a sequence of ActivityStream person objects augmented with 'id' equal to
      the Flickr user's NSID
    """
    people = {}  # maps id to tag
    for tag in obj.get('tags', []):
      url = tag.get('url', '')
      if (util.domain_from_link(url) == 'flickr.com' and
          tag.get('objectType') == 'person'):
        resp = self.call_api_method('flickr.urls.lookupUser', {'url': url})
        id = resp.get('user', {}).get('id')
        if id:
          tag = copy.copy(tag)
          tag['id'] = id
          people[id] = tag
    return people.values()

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None, **kwargs):
    """Fetches Flickr photos and converts them to ActivityStreams activities.

    See method docstring in source.py for details.

    Mentions are not fetched or included because they don't exist in Flickr.
    https://github.com/snarfed/bridgy/issues/523#issuecomment-155523875
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

    if not method:
      raise NotImplementedError()

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
    resp = self.call_api_method('flickr.people.getInfo', {
      'user_id': user_id or self.user_id(),
    })
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
        resp = util.urlopen(profile_url)
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

  def get_comment(self, comment_id, activity_id, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, required
      activity_author_id: string activity author id, ignored
      activity: activity object (optional)
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
    if isinstance(owner, dict):
      owner_id = owner.get('nsid')
      path_alias = owner.get('path_alias')
    else:
      owner_id = owner
      path_alias = photo.get('pathalias')

    created = photo.get('dates', {}).get('taken') or photo.get('datetaken')
    published = util.maybe_timestamp_to_rfc3339(
      photo.get('dates', {}).get('posted') or photo.get('dateupload'))

    # TODO replace owner_id with path_alias?
    photo_permalink = self.photo_url(path_alias or owner_id, photo.get('id'))

    title = photo.get('title')
    if isinstance(title, dict):
      title = title.get('_content', '')

    public = (photo.get('visibility') or photo).get('ispublic')

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
          'url': u'https://farm{}.staticflickr.com/{}/{}_{}_{}.jpg'.format(
            photo.get('farm'), photo.get('server'),
            photo.get('id'), photo.get('secret'), 'b'),
        },
        'content': '\n'.join((
          title, photo.get('description', {}).get('_content', ''))),
        'objectType': 'photo',
        'created': created,
        'published': published,
        'to': [{'objectType': 'group',
                'alias': '@public' if public else '@private'}],
      },
      'verb': 'post',
      'created': created,
      'published': published,
    }

    if isinstance(owner, dict):
      activity['object']['author'] = {
        'objectType': 'person',
        'displayName': owner.get('realname') or owner.get('username'),
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
          'url': u'https://www.flickr.com/search?tags={}'.format(
            tag.get('_content')),
          'displayName': tag.get('raw'),
        } for tag in photo.get('tags', {}).get('tag', [])]
    elif isinstance(photo.get('tags'), basestring):
      activity['object']['tags'] = [{
        'objectType': 'hashtag',
        'url': u'https://www.flickr.com/search?tags={}'.format(
          tag.strip()),
        'displayName': tag.strip(),
      } for tag in photo.get('tags').split(' ') if tag.strip()]

    # location is represented differently in a list of photos vs a
    # single photo info
    lat = photo.get('latitude') or photo.get('location', {}).get('latitude')
    lng = photo.get('longitude') or photo.get('location', {}).get('longitude')
    if lat and lng and float(lat) != 0 and float(lng) != 0:
      activity['object']['location'] = {
        'objectType': 'place',
        'latitude': float(lat),
        'longitude': float(lng),
      }

    self.postprocess_object(activity['object'])
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
        'displayName': person.get('realname') or person.get('username'),
        'username': person.get('username'),
        'id': self.tag_uri(person.get('nsid')),
        'image': {
          'url': self.get_user_image(person.get('iconfarm'),
                                     person.get('iconserver'),
                                     person.get('nsid')),
        },
      },
      'created': util.maybe_timestamp_to_rfc3339(photo_activity.get('favedate')),
      'url': u'{}#liked-by-{}'.format(
        photo_activity.get('url'), person.get('nsid')),
      'object': {'url': photo_activity.get('url')},
      'id': self.tag_uri(u'{}_liked_by_{}'.format(
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
        'displayName': comment.get('realname') or comment.get('authorname'),
        'username': comment.get('authorname'),
        'id': self.tag_uri(comment.get('author')),
        'url': self.user_url(comment.get('path_alias') or comment.get('author')),
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
    if server == 0:
      return u'https://www.flickr.com/images/buddyicon.gif'
    return u'https://farm{}.staticflickr.com/{}/buddyicons/{}.jpg'.format(
      farm, server, author)

  def user_id(self):
    """Get the nsid of the currently authorized user. The first time this
    is called, it will invoke the flickr.people.getLimits api method.

    https://www.flickr.com/services/api/flickr.people.getLimits.html

    Return:
      a string
    """
    if not self._user_id:
      resp = self.call_api_method('flickr.people.getLimits')
      self._user_id = resp.get('person', {}).get('nsid')
    return self._user_id

  def path_alias(self):
    """Get the path_alias of the currently authorized user. The first time this
    is called, it will invoke the flickr.people.getInfo api method.

    https://www.flickr.com/services/api/flickr.people.getInfo.html

    Return:
      a string
    """
    if not self._path_alias:
      resp = self.call_api_method('flickr.people.getInfo', {
        'user_id': self.user_id(),
      })
      self._path_alias = resp.get('person', {}).get('path_alias')
    return self._path_alias

  def user_url(self, user_id):
    """Convert a user's path_alias to their Flickr profile page URL.

    Args:
      user_id (string): user's alphanumeric nsid or path alias

    Returns:
      string, a profile URL
    """
    return user_id and 'https://www.flickr.com/people/%s/' % user_id

  def photo_url(self, user_id, photo_id):
    """Construct a url for a photo given user id and the photo id
    Args:
      user_id (string): alphanumeric user ID or path alias
      photo_id (string): numeric photo ID

    Returns:
      string, the photo URL
    """
    return u'https://www.flickr.com/photos/%s/%s/' % (user_id, photo_id)

  @classmethod
  def post_id(cls, url):
    """Used when publishing comments or favorites. Flickr photo ID is the
    3rd path component rather than the first.
    """
    parts = urlparse.urlparse(url).path.split('/')
    if len(parts) >= 4 and parts[1] == 'photos':
      return parts[3]
