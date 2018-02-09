# coding=utf-8
"""GitHub source class. Uses the v4 GraphQL API and the v3 REST API.

API docs:
https://developer.github.com/v4/
https://developer.github.com/apps/building-oauth-apps/authorization-options-for-oauth-apps/#web-application-flow
"""
import logging
import re
import urlparse

import appengine_config
from oauth_dropins import github as oauth_github
from oauth_dropins.webutil import util
import source

REST_API_ISSUE = 'https://api.github.com/repos/%s/%s/issues'
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
                id url
              }
            }
          }
        }
      }
    }
  }
}
"""
GRAPHQL_ISSUE_OR_PR = """
query {
  repository(owner: "%(owner)s", name: "%(repo)s") {
    issueOrPullRequest(number: %(number)s) {
      ... on Issue {id}
      ... on PullRequest {id}
    }
  }
}
"""
GRAPHQL_ADD_COMMENT = """
mutation {
  addComment(input: {subjectId: "%(subject_id)s", body: "%(body)s"}) {
    commentEdge {
      node {
        id url
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
  POST_ID_RE = re.compile('^[0-9]+$')
  # https://github.com/moby/moby/issues/679#issuecomment-18307522
  REPO_NAME_RE = re.compile('^[A-Za-z0-9_.-]+$')

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

  def graphql(self, json):
    """Makes a v4 GraphQL API call.

    Args:
      json: GraphQL JSON payload with top-level 'query' or 'mutation' field

    Returns: dict, parsed JSON response
    """
    return util.requests_post(oauth_github.API_GRAPHQL, json=json, headers={
      'Authorization': 'bearer %s' % self.access_token,
    }, ).json()['data']

  def rest(self, url, data):
    """Makes a v3 REST API call.

    Args:
      json: GraphQL JSON payload with top-level 'query' or 'mutation' field

    Returns: dict, parsed JSON response
    """
    return util.requests_post(url, data=data, headers={
      'Authorization': 'token %s' % self.access_token,
    }).json()

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              fetch_news=False, event_owner_id=None, **kwargs):
    """Fetches issues and comments and converts them to ActivityStreams activities.

    See method docstring in source.py for details.
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
    """Creates a new issue or comment.

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

    type = source.object_type(obj)
    if type and type not in ('activity', 'comment', 'note', 'article'):
      return source.creation_result(
        abort=False, error_plain='Cannot publish %s to GitHub' % type)

    # in_reply_to = obj.get('inReplyTo')
    base_obj = self.base_object(obj)
    base_url = base_obj.get('url')
    if not base_url:  # or not in_reply_to
      return source.creation_result(
        abort=True,
        error_plain='You need an in-reply-to GitHub repo, issue, or PR URL.')

    content = self._content_for_create(obj, ignore_formatting=ignore_formatting)
    url = obj.get('url')
    if include_link == source.INCLUDE_LINK and url:
      content += '\n\n(Originally published at: %s)' % url
    # TODO: render markdown
    preview_content = content

    parsed = urlparse.urlparse(base_url)
    path = parsed.path.strip('/').split('/')
    if len(path) == 2:
      # new issue
      owner, repo = path
      if preview:
        return source.creation_result(content=preview_content, description="""\
<span class="verb">create a new issue</span> on <a href="%s">%s/%s</a>:
<br /><br />%s<br />""" % (base_url, owner, repo, preview_content))
      else:
        resp = self.rest(REST_API_ISSUE % (owner, repo), {
          'title': 'i have an issue',
          'body': content,
        })
        return source.creation_result(resp)

    elif len(path) == 4 and path[2] in ('issues', 'pull'):
      # comment
      owner, repo, _, number = path
      if preview:
        return source.creation_result(content=preview_content, description="""\
<span class="verb">comment</span> on <a href="%s">%s/%s#%s</a>:
<br /><br />%s<br />""" % (base_url, owner, repo, number, preview_content))
      else:  # create
        issue = self.graphql({'query': GRAPHQL_ISSUE_OR_PR % locals()})
        resp = self.graphql({'mutation': GRAPHQL_ADD_COMMENT % {
          'subject_id': issue['repository']['issueOrPullRequest']['id'],
          'body': content,
        }})
        return source.creation_result(resp['addComment']['commentEdge']['node'])

    return source.creation_result(
      abort=False,
      error_plain="%s doesn't look like a GitHub repo, issue, or PR URL." % base_url)

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

    # ...

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
