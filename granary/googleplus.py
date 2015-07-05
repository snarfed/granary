"""Google+ source class.

The Google+ API currently only returns public activities and comments, so the
Audience Targeting 'to' field is always set to @public.
https://developers.google.com/+/api/latest/activities/list#collection
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import functools
import itertools

import appengine_config
import source

from apiclient.errors import HttpError
from apiclient.http import BatchHttpRequest
from oauth_dropins.webutil import util


class GooglePlus(source.Source):
  """Implements the ActivityStreams API for Google+.

  The Google+ API already exposes data in ActivityStreams format, so this is
  just a pass through.
  """

  DOMAIN = 'plus.google.com'
  NAME = 'Google+'

  # HTML snippet for embedding a post.
  # https://developers.google.com/+/web/embedded-post/
  EMBED_POST = """
  <script async defer type="text/javascript"
          src="https://apis.google.com/js/platform.js"></script>
  <div class="g-post" data-href="%(url)s">
    <p><a href="%(url)s" target="_top">%(content)s</a></p>
  </div>
  """

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
                              fetch_shares=False, fetch_events=False,
                              search_query=None):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details. app_id is ignored.

    Replies (comments), likes (+1s), and shares (reshares) each need an extra
    API call per activity. The activity has total counts for them, though, so we
    only make those calls when we know there's something to fetch.
    https://developers.google.com/+/api/latest/comments/list
    https://developers.google.com/+/api/latest/people/listByActivity

    We also batch those calls into a single HTTP request, so there are at most
    two HTTP requests total, one to get activities and optionally one to get new
    responses.
    https://developers.google.com/api-client-library/python/guide/batch
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

    # prepare batch API requests for comments, likes and reshares
    # https://developers.google.com/api-client-library/python/guide/batch
    batch = BatchHttpRequest()
    for activity in activities:
      # comments
      id = activity['id']
      num_replies = activity.get('object', {}).get('replies', {}).get('totalItems')
      if fetch_replies and num_replies and num_replies != cached.get('AGC ' + id):
        call = self.auth_entity.api().comments().list(activityId=id, maxResults=500)

        def set_comments(req_id, resp, exc, activity=None):
          obj = activity.get('object', {})
          if exc is None:
            obj['replies']['items'] = [
              self.postprocess_comment(c) for c in resp['items']]
            cache_updates['AGC ' + activity['id']] = obj['replies']['totalItems']
          else:
            obj.pop('replies', None)
            code, body = util.interpret_http_exception(exc)
            if code not in ('404', '500'):  # these happen; ignore them
              raise exc

        batch.add(call, callback=functools.partial(set_comments, activity=activity))

      # likes
      if fetch_likes:
        self.maybe_add_tags(batch, activity, cached, cache_updates,
                            'plusoners', 'like')

      # reshares
      if fetch_shares:
        self.maybe_add_tags(batch, activity, cached, cache_updates,
                            'resharers', 'share')

    if batch._requests:
      batch.execute(http)

    for a in activities:
      self.postprocess_activity(a)

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
    # G+ comments don't have their own permalinks, and I can't make one up like
    # I do with Instagram comments/likes and Facebook RSVPs because G+ has JS
    # that intercepts fragments and tries to redirect to them as the path. :/
    # so, just use the post's URL, unchanged.
    comment['url'] = comment['inReplyTo'][0]['url']
    return self.postprocess_object(comment)

  def maybe_add_tags(self, batch, activity, cached, cache_updates, collection, verb):
    """Fetches and adds 'like' or 'share' tags to an activity.

    Just adds a request and callback to the batch. Does not execute the batch.

    Converts +1s to like and reshares to share activity objects, and stores them
    in place in the 'tags' field of the activity's object.
    Details: https://developers.google.com/+/api/latest/people/listByActivity

    Args:
      batch: BatchHttpRequest
      activity: dict, G+ activity that was +1ed or reshared
      cached: dict of cache values. (not cache object above.)
      cache_updates: dict, values to write back to cache
      collection: string, 'plusoners' or 'resharers'
      verb: string, ActivityStreams verb to populate the tags with
    """
    # maps collection to cache prefix
    cache_prefixes = {'plusoners': 'AGL ', 'resharers': 'AGS '}

    id = activity['id']
    obj = activity['object']

    count = obj.get(collection, {}).get('totalItems')
    cache_key = cache_prefixes[collection] + id
    if not count or count == cached.get(cache_key):
      return

    call = self.auth_entity.api().people().listByActivity(
      activityId=id, collection=collection)

    def set_tags(req_id, resp, exc):
      if exc is None:
        tags = obj.setdefault('tags', [])
        for person in resp.get('items', []):
          person_id = person['id']
          person['id'] = self.tag_uri(person['id'])
          tags.append(self.postprocess_object({
            'id': self.tag_uri('%s_%sd_by_%s' % (id, verb, person_id)),
            'objectType': 'activity',
            'verb': verb,
            'url': obj.get('url'),
            'object': {'url': obj.get('url')},
            'author': person,
            }))
        cache_updates[cache_key] = count
      else:
        obj.pop(collection, None)
        code, body = util.interpret_http_exception(exc)
        if code not in ('404', '500'):  # these happen; ignore them
          raise exc

    batch.add(call, callback=set_tags)

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
    urls = user.get('urls')
    if urls and not user.get('url'):
      user['url'] = urls[0].get('value')
    return user
