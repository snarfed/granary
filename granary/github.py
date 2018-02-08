# coding=utf-8
"""GitHub source class. Uses the v4 GraphQL API and the v3 REST API.

API docs:
https://developer.github.com/v4/
https://developer.github.com/apps/building-oauth-apps/authorization-options-for-oauth-apps/#web-application-flow
"""
import collections
import copy
import itertools
import json
import logging
import re
import urllib
import urllib2
import urlparse
import mf2util

import appengine_config
from oauth_dropins.webutil import util
import source

GRAPHQL_USER_ISSUES = """
query {
  viewer {
    issues(last: 10) {
      edges {
        node {
          id url
        }
      }
    }
  }
}
"""
GRAPHQL_REPO_ISSUES = """
query {
  viewer {
    repositories(last: 100) {
      edges {
        node {
          issues(last: 10) {
            edges {
              node {
                id
                url
              }
            }
          }
        }
      }
    }
  }
}
"""


class GitHub(source.Source):
  """GitHub source class. See file docstring and Source class for details.

  Attributes:
    access_token: string, optional, OAuth access token
  """
  DOMAIN = 'github.com'
  BASE_URL = 'https://github.com/'
  NAME = 'GitHub'

  def __init__(self, access_token=None, user_id=None):
    """Constructor.

    If an OAuth access token is provided, it will be passed on to GitHub. This
    will be necessary for some people and contact details, based on their
    privacy settings.

    Args:
      access_token: string, optional OAuth access token
      user_id: string, optional, current user's id (either global or app-scoped)
    """
    self.access_token = access_token
    self.user_id = user_id

  def user_url(self, username):
    return self.BASE_URL + username

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'me', ie the current user.
    """
    if user_id is None:
      user_id = 'me'
    return self.user_to_actor(self.urlopen(user_id))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              fetch_news=False, event_owner_id=None, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    See method docstring in source.py for details.

    Likes, *top-level* replies (ie comments), and reactions are always included.
    They come from the 'comments', 'likes', and 'reactions' fields in the Graph
    API's Post object:
    https://developers.github.com/docs/reference/api/post/

    Threaded comments, ie comments in reply to other top-level comments, require
    an additional API call, so they're only included if fetch_replies is True.

    Mentions are never fetched or included because the API doesn't support
    searching for them.
    https://github.com/snarfed/bridgy/issues/523#issuecomment-155523875

    Additional args:
      fetch_news: boolean, whether to also fetch and include Open Graph news
        stories (/USER/news.publishes). Requires the user_actions.news
        permission. Background in https://github.com/snarfed/bridgy/issues/479
      event_owner_id: string. if provided, only events owned by this user id
        will be returned. avoids (but doesn't entirely prevent) processing big
        non-indieweb events with tons of attendees that put us over app engine's
        instance memory limit. https://github.com/snarfed/bridgy/issues/77
    """
    if search_query:
      raise NotImplementedError()

    activities = []

    if activity_id:
      pass
    else:
      pass

    response = self.make_activities_base_response(util.trim_nulls(activities))
    response['etag'] = etag
    return response

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id, optional
      activity: activity object (optional)
    """
    resp = self.urlopen(API_COMMENT % comment_id)
    return self.comment_to_object(resp, post_author_id=activity_author_id)

  def create(self, obj, include_link=source.OMIT_LINK, ignore_formatting=False):
    """Creates a new issue or comment.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose contents will be a dict with 'id' and
      'url' keys for the newly created GitHub object (or None)
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Previews creating an issue or comment.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose contents will be a unicode string HTML snippet
      or None
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates a new post, comment, like, or RSVP.

    https://developer.github.com/v4/guides/forming-calls/#about-mutations
    https://developer.github.com/v4/mutation/addcomment/
    https://developer.github.com/v3/issues/#create-an-issue

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult

      If preview is True, the contents will be a unicode string HTML
      snippet. If False, it will be a dict with 'id' and 'url' keys
      for the newly created GitHub object.
    """
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')

    if type == 'comment':
      pass
    elif type == 'activity':
      pass
    else:
      return source.creation_result(
        abort=False,
        error_plain='Cannot publish type=%s, verb=%s to GitHub' % (type, verb),
        error_html='Cannot publish type=%s, verb=%s to GitHub' % (type, verb))

    return source.creation_result(resp)

  def post_to_activity(self, post):
    """Converts an issue to an activity.

    Args:
      post: dict, a decoded JSON issue

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    obj = self.post_to_object(post, type='post')
    if not obj:
      return {}

    activity = {
      'verb': VERBS.get(post.get('type', obj.get('objectType')), 'post'),
      'published': obj.get('published'),
      'updated': obj.get('updated'),
      'fb_id': post.get('id'),
      'url': self.post_url(post),
      'actor': obj.get('author'),
      'object': obj,
      }

    post_id = self.parse_id(activity['fb_id']).post
    if post_id:
      activity['id'] = self.tag_uri(post_id)

    application = post.get('application')
    if application:
      activity['generator'] = {
        'displayName': application.get('name'),
        'id': self.tag_uri(application.get('id')),
        }
    return self.postprocess_activity(activity)

  def post_to_object(self, issue):
    """Converts an issue to an object.

    Args:
      post: dict, a decoded JSON issue

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    assert type in (None, 'post', 'comment')

    fb_id = post.get('id')
    post_type = post.get('type')
    status_type = post.get('status_type')
    url = self.post_url(post)
    display_name = None
    message = (post.get('message') or post.get('story') or
               post.get('description') or post.get('name'))

    data = post.get('data', {})
    for field in ('object', 'song'):
      obj = data.get(field)
      if obj:
        fb_id = obj.get('id')
        post_type = obj.get('type')
        url = obj.get('url')
        display_name = obj.get('title')

    id = self.parse_id(fb_id, is_comment=(type == 'comment'))
    if type == 'comment' and not id.comment:
      return {}
    elif type != 'comment' and not id.post:
      return {}

    obj = {
      'id': self.tag_uri(id.post),
      'fb_id': fb_id,
      'objectType': object_type,
      'published': util.maybe_iso8601_to_rfc3339(post.get('created_time')),
      'updated': util.maybe_iso8601_to_rfc3339(post.get('updated_time')),
      'author': author,
      # FB post ids are of the form USERID_POSTID
      'url': url,
      'image': {'url': picture},
      'displayName': display_name,
      'fb_object_id': post.get('object_id'),
      'fb_object_for_ids': post.get('object_for_ids'),
      'to': self.privacy_to_to(post, type=type),
      }

    # comments go in the replies field, according to the "Responses for
    # Activity Streams" extension spec:
    # http://activitystrea.ms/specs/json/replies/1.0/
    comments = post.get('comments', {}).get('data')
    if comments:
      items = util.trim_nulls([self.comment_to_object(c, post_id=post['id'])
                               for c in comments])
      obj['replies'] = {
        'items': items,
        'totalItems': len(items),
        }

    return self.postprocess_object(obj)

  def comment_to_object(self, comment):
    """Converts a comment to an object.

    Args:
      comment: dict, a decoded JSON comment

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    obj = self.post_to_object(comment, type='comment')
    if not obj:
      return obj

    obj['objectType'] = 'comment'

    fb_id = comment.get('id')
    obj['fb_id'] = fb_id
    id = self.parse_id(fb_id, is_comment=True)
    if not id.comment:
      return None

    post_id = id.post or post_id
    post_author_id = id.user or post_author_id
    if post_id:
      obj.update({
        'id': self.tag_uri('%s_%s' % (post_id, id.comment)),
        'url': self.comment_url(post_id, id.comment, post_author_id=post_author_id),
        'inReplyTo': [{
          'id': self.tag_uri(post_id),
          'url': self.post_url({'id': post_id, 'from': {'id': post_author_id}}),
        }],
      })

      parent_id = comment.get('parent', {}).get('id')
      if parent_id:
        obj['inReplyTo'].append({
          'id': self.tag_uri(parent_id),
          'url': self.comment_url(post_id,
                                  parent_id.split('_')[-1],  # strip POSTID_ prefix
                                  post_author_id=post_author_id)
        })

    att = comment.get('attachment')
    if (att and att.get('type') in
         ('photo', 'animated_image_autoplay', 'animated_image_share') and
        not obj.get('image')):
      obj['image'] = {'url': att.get('media', {}).get('image', {}).get('src')}
      obj.setdefault('attachments', []).append({
        'objectType': 'image',
        'image': obj['image'],
        'url': att.get('url'),
      })

    return self.postprocess_object(obj)

  def user_to_actor(self, user):
    """Converts a GitHub v4 user or actor to an ActivityStreams actor.

    Args:
      user: dict, decoded JSON GitHub user or actor

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    if not user:
      return {}

    id = user.get('id')
    username = user.get('login')
    bio = user.get('bio')

    actor = {
      # TODO: orgs, bots
      'objectType': 'person',
      'displayName': user.get('name') or username,
      'id': self.tag_uri(id),
      'username': username,
      'email': user.get('email'),
      'published': util.maybe_iso8601_to_rfc3339(user.get('createdAt')),
      'description': bio,
      'summary': bio,
      'image': {'url': user.get('avatarUrl')},
      'location': {'displayName': user.get('location')},
    }

    # extract web site links. extract_links uniquifies and preserves order
    urls = sum((util.extract_links(user.get(field)) for field in
                ('websiteUrl', 'bio')), [])
    if urls:
      actor['url'] = urls[0]
      if len(urls) > 1:
        actor['urls'] = [{'value': u} for u in urls]

    return util.trim_nulls(actor)
