"""Google+ source class.

The Google+ API currently only returns public activities and comments, so the
Audience Targeting 'to' field is always set to @public.
https://developers.google.com/+/api/latest/activities/list#collection
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import itertools
import logging

import appengine_config
import source

from apiclient.errors import HttpError
from oauth_dropins.webutil import util


class GooglePlus(source.Source):
  """Implements the ActivityStreams API for Google+.

  The Google+ API already exposes data in ActivityStreams format, so this is
  just a pass through.
  """

  DOMAIN = 'plus.google.com'
  NAME = 'Google+'

  def __init__(self, auth_entity=None, access_token=None):
    """Constructor.

    Currently, only auth_entity is supported. TODO: implement access_token.

    Args:
      access_token: string OAuth access token
      auth_entity: oauth-dropins.googleplus.GooglePlusAuth
    """
    self.access_token = access_token
    self.auth_entity = auth_entity

  def user_url(self, user_id):
    return 'https://%s/%s' % (self.DOMAIN, user_id)

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'me', ie the current user.

    Raises: GooglePlusAPIError
    """
    return self.user_to_actor(self.auth_entity.user_json)

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details. app_id is ignored.

    Replies (comments), likes (+1s), and shares (reshares) each need an extra
    API call per activity. The activity has total counts for them, though, so we
    only make those calls when we know there's something to fetch.
    https://developers.google.com/+/api/latest/comments/list
    https://developers.google.com/+/api/latest/people/listByActivity
    """
    if user_id is None:
      user_id = 'me'

    http = self.auth_entity.http()
    if etag:
      # monkey patch the ETag header in because google-api-python-client doesn't
      # support setting request headers yet:
      # http://code.google.com/p/google-api-python-client/issues/detail?id=121
      orig_request = http.request
      def request_with_etag(*args, **kwargs):
        kwargs.setdefault('headers', {}).update({'If-None-Match': etag})
        return orig_request(*args, **kwargs)
      http.request = request_with_etag

    # https://developers.google.com/+/api/latest/activities
    try:
      if activity_id:
        call = self.auth_entity.api().activities().get(activityId=activity_id)
        activities = [call.execute(http)]
      else:
        call = self.auth_entity.api().activities().list(
          userId=user_id, collection='public', maxResults=count)
        resp = call.execute(http)
        activities = resp.get('items', [])
        etag = resp.get('etag')
    except HttpError, e:
      if e.resp.status == 304:  # Not Modified, from a matching ETag
        activities = []
      else:
        raise

    # batch get memcached counts of comments, likes, reshares for all activities
    cached = {}
    if cache is not None:
      keys = itertools.product(('AGC', 'AGL', 'AGS'), [a['id'] for a in activities])
      cached = cache.get_multi('%s %s' % (prefix, id) for prefix, id in keys)
    # only update the cache at the end, in case we hit an error before then
    cache_updates = {}

    for activity in activities:
      id = activity['id']
      obj = activity.get('object', {})

      # comments
      num_replies = obj.get('replies', {}).get('totalItems')
      if fetch_replies and num_replies and num_replies != cached.get('AGC ' + id):
        call = self.auth_entity.api().comments().list(
          activityId=activity['id'], maxResults=500)
        comments = call.execute(http)
        obj['replies']['items'] = [
          self.postprocess_comment(c) for c in comments['items']]
        cache_updates['AGC ' + id] = num_replies

      # likes
      num_likes = obj.get('plusoners', {}).get('totalItems')
      if fetch_likes and num_likes and num_likes != cached.get('AGL ' + id):
        self.add_tags(activity, 'plusoners', 'like')
        cache_updates['AGL ' + id] = num_likes

      # reshares
      num_shares = obj.get('resharers', {}).get('totalItems')
      if fetch_shares and num_shares and num_shares != cached.get('AGS ' + id):
        self.add_tags(activity, 'resharers', 'share')
        cache_updates['AGS ' + id] = num_shares

      self.postprocess_activity(activity)

    response = self._make_activities_base_response(activities)
    response['etag'] = etag
    if cache_updates and cache is not None:
      cache.set_multi(cache_updates)
    return response

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id. Ignored.
    """
    # https://developers.google.com/+/api/latest/comments
    call = self.auth_entity.api().comments().get(commentId=comment_id)
    cmt = call.execute(self.auth_entity.http())
    return self.postprocess_comment(cmt)

  def postprocess_activity(self, activity):
    """Massage G+'s ActivityStreams dialect into our dialect, in place.

    Args:
      activity: ActivityStreams activity dict.
    """
    activity['object']['author'] = activity['actor']
    activity['object']['to'] = [{'objectType': 'group', 'alias': '@public'}]
    # also convert id to tag URI
    activity['id'] = self.tag_uri(activity['id'])

  def postprocess_comment(self, comment):
    """Hack to pretend comment activities are comment objects.

    G+ puts almost everything in the comment *activity*, not the object
    inside the activity. So, copy over the content and use the activity
    itself.
    """
    comment['content'] = comment['object']['content']
    comment['author'] = comment.pop('actor')
    comment['to'] = [{'objectType': 'group', 'alias': '@public'}]
    # also convert id to tag URI
    comment['id'] = self.tag_uri(comment['id'])
    # G+ comments don't have their own permalinks. :/ so, use the post's.
    comment['url'] = comment['inReplyTo'][0]['url']
    return self.postprocess_object(comment)

  def add_tags(self, activity, collection, verb):
    """Fetches and adds 'like' or 'share' tags to an activity.

    Converts +1s to like and reshares to share activity objects, and stores them
    in place in the 'tags' field of the activity's object.
    Details: https://developers.google.com/+/api/latest/people/listByActivity

    Args:
      activity: dict, G+ activity that was +1ed or reshared
      collection: string, 'plusoners' or 'resharers'
      verb: string, ActivityStreams verb to populate the tags with
    """
    # maps collection to verb to use in content string
    content_verbs = {'plusoners': '+1ed', 'resharers': 'reshared'}

    id = activity['id']
    call = self.auth_entity.api().people().listByActivity(
      activityId=id, collection=collection)
    persons = call.execute(self.auth_entity.http()).get('items', [])
    obj = activity['object']
    tags = obj.setdefault('tags', [])

    for person in persons:
      person_id = person['id']
      person['id'] = self.tag_uri(person['id'])
      tags.append(self.postprocess_object({
        'id': self.tag_uri('%s_%sd_by_%s' % (id, verb, person_id)),
        'objectType': 'activity',
        'verb': verb,
        'url': obj.get('url'),
        'object': {'url': obj.get('url')},
        'author': person,
        'content': '%s this.' % content_verbs[collection],
        }))

    return tags

  def user_to_actor(self, user):
    """Returns a Google+ Person object unchanged.

    https://developers.google.com/+/api/latest/people

    TODO: G+'s Person resource has a multiply-valued 'urls' field. Should
    ideally extract the (first?) non-silo URL and set that as the 'url' field.

    Args:
      user: dict, a decoded JSON Google+ Person

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    return user
