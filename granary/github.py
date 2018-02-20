# coding=utf-8
"""GitHub source class. Uses the v4 GraphQL API and the v3 REST API.

API docs:
https://developer.github.com/v4/
https://developer.github.com/apps/building-oauth-apps/authorization-options-for-oauth-apps/#web-application-flow
"""
import datetime
import logging
import re
import rfc822
import urllib
import urlparse

import appengine_config
from oauth_dropins import github as oauth_github
from oauth_dropins.webutil import util
import source

REST_API_BASE = 'https://api.github.com'
REST_API_ISSUE = REST_API_BASE + '/repos/%s/%s/issues/%s'
REST_API_CREATE_ISSUE = REST_API_BASE + '/repos/%s/%s/issues'
# currently unused; we use 'comments_url' in the issue or PR instead
REST_API_COMMENTS = REST_API_BASE + '/repos/%s/%s/issues/%s/comments'
REST_API_COMMENT = REST_API_BASE + '/repos/%s/%s/issues/comments/%s'
REST_API_MARKDOWN = REST_API_BASE + '/markdown'
REST_API_NOTIFICATIONS = REST_API_BASE + '/notifications?all=true&participating=true'
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
GRAPHQL_REPO = """
query {
  repository(owner: "%(owner)s", name: "%(repo)s") {
    id
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
GRAPHQL_ADD_STAR = """
mutation {
  addStar(input: {starrableId: "%(starrable_id)s"}) {
    starrable {
      id
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

  def __init__(self, access_token=None):
    """Constructor.

    Args:
      access_token: string, optional OAuth access token
    """
    self.access_token = access_token

  def user_url(self, username):
    return self.BASE_URL + username

  def graphql(self, graphql):
    """Makes a v4 GraphQL API call.

    Args:
      graphql: string GraphQL operation

    Returns: dict, parsed JSON response
    """
    resp = util.requests_post(
      oauth_github.API_GRAPHQL, json={'query': graphql},
      headers={
        'Authorization': 'bearer %s' % self.access_token,
      })
    resp.raise_for_status()
    result = resp.json()
    assert 'errors' not in result, result
    return result['data']

  def rest(self, url, data=None, **kwargs):
    """Makes a v3 REST API call.

    Uses HTTP POST if data is provided, otherwise GET.

    Args:
      data: dict, JSON payload for POST requests

    Returns: `requests.Response`
    """
    kwargs['headers'] = kwargs.get('headers') or {}
    kwargs['headers'].update({'Authorization': 'token %s' % self.access_token})

    if data is None:
      resp = util.requests_get(url, **kwargs)
    else:
      resp = util.requests_post(url, json=data, **kwargs)
    resp.raise_for_status()
    return resp

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None,
                              public_only=True, **kwargs):
    """Fetches issues and comments and converts them to ActivityStreams activities.

    See :meth:`Source.get_activities_response` for details.

    *Not comprehensive!* Uses the notifications API (v3 REST).

    https://developer.github.com/v3/activity/notifications/
    https://developer.github.com/v3/issues/
    https://developer.github.com/v3/issues/comments/

    The notifications API call supports Last-Modified/If-Modified-Since headers
    and 304 Not Changed responses. If provided, etag should be an RFC2822
    timestamp, usually the exact value returned in a Last-Modified header. It
    will also be passed to the comments API endpoint as the since= value
    (converted to ISO 8601).
    """
    if (fetch_likes or fetch_shares or fetch_events or fetch_mentions or search_query):
      raise NotImplementedError()

    since = None
    etag_parsed = rfc822.parsedate(etag)
    if etag_parsed:
      since = datetime.datetime(*etag_parsed[:6])

    activities = []

    if activity_id:
      parts = tuple(activity_id.split(':'))
      assert len(parts) == 3
      issue = self.rest(REST_API_ISSUE % parts).json()
      activities = [self.issue_to_object(issue)]

    else:
      notifs = self.rest(REST_API_NOTIFICATIONS,
                         headers={'If-Modified-Since': etag} if etag else None)
      etag = notifs.headers.get('Last-Modified')
      for notif in notifs.json():
        id = notif.get('id')
        subject_url = notif.get('subject').get('url')
        if not subject_url:
          logging.info('Skipping thread %s, missing subject!', id)
          continue
        split = subject_url.split('/')
        if len(split) <= 2 or split[-2] != 'issues':
          # TODO: pull requests with 'pulls' in subject URL
          logging.info("Skipping thread %s with subject %s, only issues right now",
                       id, subject_url)
          continue

        issue = self.rest(subject_url).json()
        obj = self.issue_to_object(issue)

        private = notif.get('repository', {}).get('private')
        if private is not None:
          obj['to'] = [{
            'objectType': 'group',
            'alias': '@private' if private else '@public',
          }]

        comments_url = issue.get('comments_url')
        if fetch_replies and comments_url:
          if since:
            comments_url += '?since=%s' % since.isoformat() + 'Z'
          comments = self.rest(comments_url).json()
          comment_objs = list(util.trim_nulls(
            self.comment_to_object(c) for c in comments))
          obj['replies'] = {
            'items': comment_objs,
            'totalItems': len(comment_objs),
          }

        activities.append(obj)

    response = self.make_activities_base_response(util.trim_nulls(activities))
    response['etag'] = etag
    return response

  def get_comment(self, comment_id, **kwargs):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id, of the form REPO-OWNER_REPO-NAME_ID,
        e.g. snarfed:bridgy:456789
    """
    parts = tuple(comment_id.split(':'))
    assert len(parts) == 3
    comment = self.rest(REST_API_COMMENT % parts).json()
    return self.comment_to_object(comment)

  def render_markdown(self, markdown, owner, repo):
    """Uses the GitHub API to render GitHub-flavored Markdown to HTML.

    https://developer.github.com/v3/markdown/
    https://github.github.com/gfm/

    Args:
      markdown: unicode string, input
      owner and repo: strings, the repo to render in, for context. affects git
        hashes #XXX for issues/PRs.

    Returns: unicode string, rendered HTML
    """
    return self.rest(REST_API_MARKDOWN, {
      'text': markdown,
      'mode': 'gfm',
      'context': '%s/%s' % (owner, repo),
    }).text

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
    if type and type not in ('issue', 'comment', 'activity', 'note', 'article', 'like'):
      return source.creation_result(
        abort=False, error_plain='Cannot publish %s to GitHub' % type)

    base_obj = self.base_object(obj)
    base_url = base_obj.get('url')
    if not base_url:
      return source.creation_result(
        abort=True,
        error_plain='You need an in-reply-to GitHub repo, issue, or PR URL.')

    content = orig_content = self._content_for_create(
      obj, ignore_formatting=ignore_formatting)
    url = obj.get('url')
    if include_link == source.INCLUDE_LINK and url:
      content += '\n\n(Originally published at: %s)' % url

    path = urlparse.urlparse(base_url).path.strip('/').split('/')
    owner, repo = path[:2]

    if len(path) == 2 or (len(path) == 3 and path[2] == 'issues'):
      if type == 'like':  # star
        if preview:
          return source.creation_result(description="""\
<span class="verb">star</span> <a href="%s">%s/%s</a>.""" %
              (base_url, owner, repo))
        else:
          issue = self.graphql(GRAPHQL_REPO % locals())
          resp = self.graphql(GRAPHQL_ADD_STAR % {
            'starrable_id': issue['repository']['id'],
          })
          return source.creation_result({
            'url': base_url + '/stargazers',
          })

      else:  # new issue
        title = util.ellipsize(obj.get('displayName') or obj.get('title') or
                               orig_content)
        if preview:
          preview_content = '<b>%s</b><hr>%s' % (
            title, self.render_markdown(content, owner, repo))
          return source.creation_result(content=preview_content, description="""\
  <span class="verb">create a new issue</span> on <a href="%s">%s/%s</a>:""" %
              (base_url, owner, repo))
        else:
          resp = self.rest(REST_API_CREATE_ISSUE % (owner, repo), {
            'title': title,
            'body': content,
          }).json()
          resp['url'] = resp.pop('html_url')
          return source.creation_result(resp)

    elif len(path) == 4 and path[2] in ('issues', 'pull'):
      # comment
      owner, repo, _, number = path
      if preview:
        preview_content = self.render_markdown(content, owner, repo)
        return source.creation_result(content=preview_content, description="""\
<span class="verb">comment</span> on <a href="%s">%s/%s#%s</a>:""" %
            (base_url, owner, repo, number))
      else:  # create
        issue = self.graphql(GRAPHQL_ISSUE_OR_PR % locals())
        resp = self.graphql(GRAPHQL_ADD_COMMENT % {
          'subject_id': issue['repository']['issueOrPullRequest']['id'],
          'body': content,
        })
        return source.creation_result(resp['addComment']['commentEdge']['node'])

    return source.creation_result(
      abort=False,
      error_plain="%s doesn't look like a GitHub repo, issue, or PR URL." % base_url)

  @classmethod
  def issue_to_object(cls, issue):
    """Converts a GitHub issue to ActivityStreams.

    Handles both v4 GraphQL and v3 REST API issue objects.

    https://developer.github.com/v4/object/issue/
    https://developer.github.com/v3/issues/

    Args:
      issue: dict, decoded JSON GitHub issue

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    obj = cls._to_object(issue, repo_id=True)
    if not obj:
      return obj

    repo_url = re.sub(r'/(issue|pull)s?/[0-9]+$', '', obj['url'])

    obj.update({
      'objectType': 'issue',
      'inReplyTo': [{'url': repo_url + '/issues'}],
      'tags': [{
        'displayName': l['name'],
        'url': '%s/labels/%s' % (repo_url, urllib.quote(l['name'])),
      } for l in issue.get('labels', []) if l.get('name')],
    })
    return cls.postprocess_object(obj)

  @classmethod
  def comment_to_object(cls, comment):
    """Converts a GitHub comment to ActivityStreams.

    Handles both v4 GraphQL and v3 REST API issue objects.

    https://developer.github.com/v4/object/issue/
    https://developer.github.com/v3/issues/

    Args:
      comment: dict, decoded JSON GitHub issue

    Returns:
      an ActivityStreams comment dict, ready to be JSON-encoded
    """
    obj = cls._to_object(comment, repo_id=True)
    if not obj:
      return obj

    obj.update({
      'objectType': 'comment',
      # url is e.g. https://github.com/foo/bar/pull/123#issuecomment-456
      'inReplyTo': [{'url': util.fragmentless(obj['url'])}],
    })
    return cls.postprocess_object(obj)

  @classmethod
  def user_to_actor(cls, user):
    """Converts a GitHub user to an ActivityStreams actor.

    Handles both v4 GraphQL and v3 REST API user objects.

    https://developer.github.com/v4/object/user/
    https://developer.github.com/v3/users/

    Args:
      user: dict, decoded JSON GitHub user

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    actor = cls._to_object(user)
    if not actor:
      return actor

    username = user.get('login')
    bio = user.get('bio')

    actor.update({
      # TODO: orgs, bots
      'objectType': 'person',
      'displayName': user.get('name') or username,
      'username': username,
      'email': user.get('email'),
      'description': bio,
      'summary': bio,
      'image': {'url': user.get('avatarUrl') or user.get('avatar_url')},
      'location': {'displayName': user.get('location')},
    })

    # extract web site links. extract_links uniquifies and preserves order
    urls = sum((util.extract_links(user.get(field)) for field in
                ('websiteUrl',  # GraphQL
                 'blog',  # REST
                 'bio',   # both
                )), [])
    if urls:
      actor['url'] = urls[0]
      if len(urls) > 1:
        actor['urls'] = [{'value': u} for u in urls]

    return cls.postprocess_object(actor)

  @classmethod
  def _to_object(cls, input, repo_id=False):
    """Starts to convert aHub GraphQL or REST API object to ActivityStreams.

    Args:
      input: dict, decoded JSON GraphQL or REST object
      repo_id: boolean, whether to inject repo owner and name into id

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    if not input:
      return {}

    id = input.get('node_id') or input.get('id')
    number = input.get('number')
    url = input.get('html_url') or input.get('url') or ''
    if repo_id and id and url:
      # inject repo owner and name
      path = urlparse.urlparse(url).path.strip('/').split('/')
      owner, repo = path[:2]
      # join with : because github allows ., _, and - in repo names. (see
      # REPO_NAME_RE.)
      id = ':'.join((owner, repo, str(number or id)))

    return {
      'id': cls.tag_uri(id),
      'url': url,
      'author': cls.user_to_actor(input.get('author') or input.get('user')),
      'title': input.get('title'),
      'content': input.get('body'),
      'published': util.maybe_iso8601_to_rfc3339(input.get('createdAt') or
                                                 input.get('created_at')),
      'updated': util.maybe_iso8601_to_rfc3339(input.get('lastEditedAt') or
                                               input.get('updated_at')),
    }
