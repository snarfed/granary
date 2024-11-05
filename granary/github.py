"""GitHub source class. Uses the v4 GraphQL API and the v3 REST API.

API docs:

* https://developer.github.com/v4/
* https://developer.github.com/v3/
* https://developer.github.com/apps/building-oauth-apps/authorization-options-for-oauth-apps/#web-application-flow
"""
import datetime
import email.utils
import html
import logging
import re
import urllib.parse

from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads
import requests

from . import as1
from . import source

logger = logging.getLogger(__name__)

REST_BASE = 'https://api.github.com'
REST_ISSUE = REST_BASE + '/repos/%s/%s/issues/%s'
REST_CREATE_ISSUE = REST_BASE + '/repos/%s/%s/issues'
REST_ISSUE_LABELS = REST_BASE + '/repos/%s/%s/issues/%s/labels'
REST_COMMENTS = REST_BASE + '/repos/%s/%s/issues/%s/comments'
REST_REACTIONS = REST_BASE + '/repos/%s/%s/issues/%s/reactions'
REST_COMMENT = REST_BASE + '/repos/%s/%s/%s/comments/%s'
REST_COMMENT_REACTIONS = REST_BASE + '/repos/%s/%s/%s/comments/%s/reactions'
REST_MARKDOWN = REST_BASE + '/markdown'
REST_NOTIFICATIONS = REST_BASE + '/notifications?all=true&participating=true'
GRAPHQL_BASE = 'https://api.github.com/graphql'
GRAPHQL_BOT_FIELDS = 'id avatarUrl createdAt login url'
GRAPHQL_ORG_FIELDS = 'id avatarUrl description location login name url websiteUrl'
GRAPHQL_USER_FIELDS = 'id avatarUrl bio company createdAt location login name url websiteUrl' # not email, it requires an additional oauth scope
GRAPHQL_USER = """
query {
  user(login: "%(login)s") {
    """ + GRAPHQL_USER_FIELDS + """
  }
}
"""
GRAPHQL_VIEWER = """
query {
  viewer {
    """ + GRAPHQL_USER_FIELDS + """
  }
}
"""
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
GRAPHQL_REPO = """
query {
  repository(owner: "%(owner)s", name: "%(repo)s") {
    id
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
GRAPHQL_REPO_LABELS = """
query {
  repository(owner: "%(owner)s", name: "%(repo)s") {
    labels(first:100) {
      nodes {
        name
      }
    }
  }
}
"""
GRAPHQL_ISSUE_OR_PR = """
query {
  repository(owner: "%(owner)s", name: "%(repo)s") {
    issueOrPullRequest(number: %(number)s) {
      ... on Issue {id title}
      ... on PullRequest {id title}
    }
  }
}
"""
GRAPHQL_COMMENT = """
query {
  node(id:"%(id)s") {
    ... on IssueComment {
      id url body createdAt
      author {
        ... on Bot {""" + GRAPHQL_BOT_FIELDS + """}
        ... on Organization {""" + GRAPHQL_ORG_FIELDS + """}
        ... on User {""" + GRAPHQL_USER_FIELDS + """}
      }
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
GRAPHQL_ADD_REACTION = """
mutation {
  addReaction(input: {subjectId: "%(subject_id)s", content: %(content)s}) {
    reaction {
      id content
      user {login}
    }
  }
}
"""

# key is unicode emoji string, value is GraphQL ReactionContent enum value.
# https://developer.github.com/v4/enum/reactioncontent/
# https://developer.github.com/v3/reactions/#reaction-types
REACTIONS_GRAPHQL = {
  u'👍': 'THUMBS_UP',
  u'👎': 'THUMBS_DOWN',
  u'😆': 'LAUGH',
  u'😕': 'CONFUSED',
  u'❤️': 'HEART',
  u'🎉': 'HOORAY',
  u'🚀': 'ROCKET',
  u'👀': 'EYES',
}
# key is 'content' field value, value is unicode emoji string.
# https://developer.github.com/v3/reactions/#reaction-types
REACTIONS_REST = {
  u'👍': '+1',
  u'👎': '-1',
  u'😆': 'laugh',
  u'😕': 'confused',
  u'❤️': 'heart',
  u'🎉': 'hooray',
  u'🚀': 'rocket',
  u'👀': 'eyes',
}
REACTIONS_REST_CHARS = {char: name for name, char, in REACTIONS_REST.items()}


# preserve some HTML elements instead of converting them. eg <code> so that
# GitHub renders HTML entities like &gt; inside them instead of leaving them
# escaped. background:
# https://chat.indieweb.org/dev/2019-12-24#t1577174464779200
# https://github.com/snarfed/bridgy/issues/957
PRESERVE_TAGS = ('code', 'blockquote')

HTTP_NON_FATAL_CODES = (
  404,  # issue/PR or repo was probably deleted
  410,  # ditto
  451,  # Unavailable for Legal Reasons, eg DMCA takedown
)


def tag_placeholders(self, tag, attrs, start):
  if tag in PRESERVE_TAGS:
    self.o(f'~~~BRIDGY-{tag}-TAG-START~~~' if start else f'~~~BRIDGY-{tag}-TAG-END~~~')
    return True


def replace_placeholders(text):
  for tag in PRESERVE_TAGS:
    text = text.replace(f'~~~BRIDGY-{tag}-TAG-START~~~', f'<{tag}>')\
               .replace(f'~~~BRIDGY-{tag}-TAG-END~~~', f'</{tag}>')

  return text


class GitHub(source.Source):
  """GitHub source class. See file docstring and :class:`Source` for details.

  Attributes:
    access_token (str): optional, OAuth access token
  """
  DOMAIN = 'github.com'
  BASE_URL = 'https://github.com/'
  NAME = 'GitHub'
  # username:repo:id
  POST_ID_RE = re.compile(r'^[A-Za-z0-9-]+:[A-Za-z0-9_.-]+:[0-9]+$')
  # https://github.com/shinnn/github-username-regex#readme
  # (this slightly overspecifies; it allows multiple consecutive hyphens and
  # leading/trailing hyphens. oh well.)
  USER_NAME_RE = re.compile(r'[A-Za-z0-9-]+')
  USER_URL_RE = re.compile(fr"""
    (?<!]\(|=['"])  # don't match on Markdown links or HTML attributes
    \b
    {re.escape(BASE_URL)}
    ({USER_NAME_RE.pattern})
    \b
    (?![/?_+#@.])  # don't match on URLs that continue past username
  """, re.VERBOSE)

  # https://github.com/moby/moby/issues/679#issuecomment-18307522
  REPO_NAME_RE = re.compile(r'[A-Za-z0-9_.-]+')
  # https://github.com/Alir3z4/html2text/blob/master/docs/usage.md#available-options
  HTML2TEXT_OPTIONS = {
    'ignore_images': False,
    'ignore_links': False,
    'protect_links': False,
    'use_automatic_links': False,
    'tag_callback': tag_placeholders,
  }
  OPTIMIZED_COMMENTS = True

  def __init__(self, access_token=None):
    """Constructor.

    Args:
      access_token (str): optional OAuth access token
    """
    self.access_token = access_token

  def user_url(self, username):
    return self.BASE_URL + username

  @classmethod
  def base_id(cls, url):
    """Extracts and returns a ``USERNAME:REPO:ID`` id for an issue or PR.

    Args:
      url (str):

    Returns:
      str or None:
    """
    parts = urllib.parse.urlparse(url).path.strip('/').split('/')
    if len(parts) == 4 and util.is_int(parts[3]):
      return ':'.join((parts[0], parts[1], parts[3]))

  def graphql(self, graphql, kwargs):
    """Makes a v4 GraphQL API call.

    Args:
      graphql (str): GraphQL operation

    Returns:
      dict: parsed JSON response
    """
    escaped = {k: (email.utils.quote(v) if isinstance(v, str) else v)
               for k, v in kwargs.items()}
    resp = util.requests_post(
      GRAPHQL_BASE, json={'query': graphql % escaped},
      headers={
        'Authorization': f'bearer {self.access_token}',
      })
    resp.raise_for_status()
    result = resp.json()

    errs = result.get('errors')
    if errs:
      logger.warning(result)
      raise ValueError('\n'.join(e.get('message') for e in errs))

    return result['data']

  def rest(self, url, data=None, parse_json=True, **kwargs):
    """Makes a v3 REST API call.

    Uses HTTP POST if data is provided, otherwise GET.

    Args:
      data (dict): JSON payload for POST requests
      json (bool): whether to parse the response body as JSON and return it as a
        dict. If False, returns a :class:`requests.Response` instead.

    Returns:
      dict: decoded from JSON response if ``json=True``, otherwise
        :class:`requests.Response`
    """
    kwargs['headers'] = kwargs.get('headers') or {}
    kwargs['headers'].update({
      'Authorization': f'token {self.access_token}',
    })

    if data is None:
      resp = util.requests_get(url, **kwargs)
    else:
      resp = util.requests_post(url, json=data, **kwargs)
    resp.raise_for_status()

    return resp.json() if parse_json else resp

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

    Also note that start_index is not currently supported.

    * https://developer.github.com/v3/activity/notifications/
    * https://developer.github.com/v3/issues/
    * https://developer.github.com/v3/issues/comments/

    ``fetch_likes`` determines whether emoji reactions are fetched:
    https://help.github.com/articles/about-conversations-on-github#reacting-to-ideas-in-comments

    The notifications API call supports ``Last-Modified``/``If-Modified-Since``
    headers and ``304 Not Changed`` responses. If provided, ``etag`` should be
    an RFC2822 timestamp, usually the exact value returned in a
    ``Last-Modified`` header. It will also be passed to the comments API
    endpoint as the ``since=`` value (converted to ISO8601).
    """
    if fetch_shares or fetch_events or fetch_mentions or search_query:
      raise NotImplementedError()

    etag_parsed = email.utils.parsedate(etag)
    since = datetime.datetime(*etag_parsed[:6]) if etag_parsed else None
    issues = []
    activities = []

    if activity_id:
      # single issue
      parts = tuple(activity_id.split(':'))
      if len(parts) != 3:
        raise ValueError('GitHub activity ids must be of the form USER:REPO:ISSUE_OR_PR')
      try:
        issues = [self.rest(REST_ISSUE % parts)]
        activities = [self.issue_to_object(issues[0])]
      except BaseException as e:
        code, body = util.interpret_http_exception(e)
        if util.is_int(code) and int(code) in HTTP_NON_FATAL_CODES:
          activities = []
        else:
          raise

    else:
      # all issues/PRs, based on notifications
      url = REST_NOTIFICATIONS
      if count:
        url += f'&per_page={count}'
      resp = self.rest(url, parse_json=False,
                       headers={'If-Modified-Since': etag} if etag else None)
      etag = resp.headers.get('Last-Modified')
      notifs = [] if resp.status_code == 304 else resp.json()

      for notif in notifs:
        id = notif.get('id')
        subject_url = notif.get('subject').get('url')
        if not subject_url:
          logger.info(f'Skipping thread {id}, missing subject!')
          continue
        split = subject_url.split('/')
        if len(split) <= 2 or split[-2] not in ('issues', 'pulls'):
          logger.info(
            'Skipping thread %s with subject %s, only issues and PRs right now',
            id, subject_url)
          continue

        try:
          issue = self.rest(subject_url)
        except requests.HTTPError as e:
          if e.response.status_code in HTTP_NON_FATAL_CODES:
            util.interpret_http_exception(e)
            continue
          raise

        obj = self.issue_to_object(issue)

        private = notif.get('repository', {}).get('private')
        if private is not None:
          obj['to'] = [{
            'objectType': 'group',
            'alias': '@private' if private else '@public',
          }]

        issues.append(issue)
        activities.append(obj)

    # add comments and reactions, if requested
    assert len(issues) == len(activities)
    for issue, obj in zip(issues, activities):
      comments_url = issue.get('comments_url')
      if fetch_replies and comments_url:
        if since:
          comments_url += f'?since={since.isoformat()}' + 'Z'
        comments = self.rest(comments_url)
        comment_objs = list(util.trim_nulls(
          self.comment_to_object(c) for c in comments))
        obj['replies'] = {
          'items': comment_objs,
          'totalItems': len(comment_objs),
        }

      if fetch_likes:
        issue_url = issue['url'].replace('pulls', 'issues')
        reactions = self.rest(issue_url + '/reactions')
        obj.setdefault('tags', []).extend(
          self.reaction_to_object(r, obj) for r in reactions)

    response = self.make_activities_base_response(util.trim_nulls(activities))
    response['etag'] = etag
    return response

  def get_actor(self, user_id=None):
    """Fetches and returns a user.

    Args:
      user_id (str): defaults to current user

    Returns:
      dict: ActivityStreams actor object
    """
    if user_id:
      user = self.graphql(GRAPHQL_USER, {'login': user_id})['user']
    else:
      user = self.graphql(GRAPHQL_VIEWER, {})['viewer']

    return self.to_as1_actor(user)

  def get_comment(self, comment_id, **kwargs):
    """Fetches and returns a comment.

    Args:
      comment_id (str): comment id (either REST or GraphQL), of the form
        ``REPO-OWNER:REPO-NAME:ID``, e.g. ``snarfed:bridgy:456789``

    Returns:
      dict: an ActivityStreams comment object
    """
    parts = comment_id.split(':')
    if len(parts) != 3:
      raise ValueError('GitHub comment ids must be of the form USER:REPO:COMMENT_ID')

    id = parts[-1]
    if util.is_int(id):  # REST API id
      parts.insert(2, 'issues')
      comment = self.rest(REST_COMMENT % tuple(parts))
    else:  # GraphQL node id
      comment = self.graphql(GRAPHQL_COMMENT, {'id': id})['node']

    return self.comment_to_object(comment)

  def render_markdown(self, markdown, owner, repo):
    """Uses the GitHub API to render GitHub-flavored Markdown to HTML.

    * https://developer.github.com/v3/markdown/
    * https://github.github.com/gfm/

    Args:
      markdown (str): input
      owner and repo (strs): the repo to render in, for context. affects git
        hashes #XXX for issues/PRs.

    Returns:
      str: rendered HTML
    """
    return self.rest(REST_MARKDOWN, {
      'text': markdown,
      'mode': 'gfm',
      'context': f'{owner}/{repo}',
    }, parse_json=False).text

  def create(self, obj, include_link=source.OMIT_LINK, ignore_formatting=False):
    """Creates a new issue or comment.

    Args:
      obj (dict): ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult or None: contents will be a dict with ``id`` and
      ``url`` keys for the newly created GitHub object
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Previews creating an issue or comment.

    Args:
      obj (dict): ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult or None: ``contents`` will be a str HTML snippet
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates a new issue or comment.

    When creating a new issue, if the authenticated user is a collaborator on
    the repo, tags that match existing labels are converted to those labels and
    included.

    * https://developer.github.com/v4/guides/forming-calls/#about-mutations
    * https://developer.github.com/v4/mutation/addcomment/
    * https://developer.github.com/v4/mutation/addreaction/
    * https://developer.github.com/v3/issues/#create-an-issue

    Args:
      obj (dict): ActivityStreams object
      preview (bool)
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult: If preview is True, the contents will be a str HTML
      snippet. If False, it will be a dict with ``id`` and ``url`` keys for the
      newly created GitHub object.
    """
    assert preview in (False, True)

    type = as1.object_type(obj)
    if type and type not in ('issue', 'comment', 'activity', 'note', 'article',
                             'like', 'favorite', 'tag'):
      return source.creation_result(
        abort=False, error_plain=f'Cannot publish {type} to GitHub')

    base_obj = self.base_object(obj)
    base_url = base_obj.get('url')
    if not base_url:
      return source.creation_result(
        abort=True,
        error_plain='You need an in-reply-to GitHub repo, issue, PR, or comment URL.')

    content = orig_content = replace_placeholders(html.escape(
      self._content_for_create(obj, ignore_formatting=ignore_formatting),
      quote=False))

    # convert GitHub user profile URLs to @-mentions,
    # eg https://github.com/snarfed to @snarfed
    content = self.USER_URL_RE.sub(r'@\1', content)

    url = obj.get('url')
    if include_link == source.INCLUDE_LINK and url:
      content += f'\n\n(Originally published at: {url})'

    parsed = urllib.parse.urlparse(base_url)
    path = parsed.path.strip('/').split('/')
    owner, repo = path[:2]
    if len(path) == 4:
      number = path[3]

    # TODO: support #pullrequestreview-* URLs for top-level PR comments too.
    # Haven't yet gotten those to work via either the issues or pulls APIs.
    # https://github.com/snarfed/bridgy/issues/955#issuecomment-788478848
    comment_id = re.match(r'^(discussion_r|issuecomment-)([0-9]+)$', parsed.fragment)
    comment_type = None
    if comment_id:
      comment_type = 'issues' if comment_id.group(1) == 'issuecomment-' else 'pulls'
      comment_id = comment_id.group(2)
    elif parsed.fragment:
      return source.creation_result(
        abort=True,
        error_plain=f'Please remove the fragment #{parsed.fragment} from your in-reply-to URL.')

    if type == 'comment':  # comment or reaction
      if not (len(path) == 4 and path[2] in ('issues', 'pull')):
        return source.creation_result(
          abort=True, error_plain='GitHub comment requires in-reply-to issue or PR URL.')

      is_reaction = orig_content in REACTIONS_GRAPHQL
      if preview:
        if comment_id:
          comment = self.rest(REST_COMMENT % (owner, repo, comment_type,
                                                  comment_id))
          target_link = f"<a href=\"{base_url}\">a comment on {owner}/{repo}#{number}, <em>{util.ellipsize(comment['body'])}</em></a>"
        else:
          resp = self.graphql(GRAPHQL_ISSUE_OR_PR, locals())
          issue = (resp.get('repository') or {}).get('issueOrPullRequest')
          target_link = '<a href="%s">%s/%s#%s%s</a>' % (
            base_url, owner, repo, number,
            (', <em>%s</em>' % issue['title']) if issue else '')

        if is_reaction:
          preview_content = None
          desc = f'<span class="verb">react {orig_content}</span> to {target_link}.'
        else:
          preview_content = self.render_markdown(content, owner, repo)
          desc = f'<span class="verb">comment</span> on {target_link}:'
        return source.creation_result(content=preview_content, description=desc)

      else:  # create
        # we originally used the GraphQL API to create issue comments and
        # reactions, but it often gets rejected against org repos due to access
        # controls. oddly, the REST API works fine in those same cases.
        # https://github.com/snarfed/bridgy/issues/824
        if is_reaction:
          if comment_id:
            api_url = REST_COMMENT_REACTIONS % (owner, repo, comment_type,
                                                    comment_id)
            reacted = self.rest(api_url, data={
              'content': REACTIONS_REST.get(orig_content),
            })
            url = base_url
          else:
            api_url = REST_REACTIONS % (owner, repo, number)
            reacted = self.rest(api_url, data={
              'content': REACTIONS_REST.get(orig_content),
            })
            url = f"{base_url}#{reacted['content'].lower()}-by-{reacted['user']['login']}"

          return source.creation_result({
            'id': reacted.get('id'),
            'url': url,
            'type': 'react',
          })

        else:
          try:
            api_url = REST_COMMENTS % (owner, repo, number)
            commented = self.rest(api_url, data={'body': content})
            return source.creation_result({
              'id': commented.get('id'),
              'url': commented.get('html_url'),
              'type': 'comment',
            })
          except ValueError as e:
            return source.creation_result(abort=True, error_plain=str(e))

    elif type in ('like', 'favorite'):  # star
      if not (len(path) == 2 or (len(path) == 3 and path[2] == 'issues')):
        return source.creation_result(
          abort=True, error_plain='GitHub like requires in-reply-to repo URL.')

      if preview:
        return source.creation_result(
          description=f'<span class="verb">star</span> <a href="{base_url}">{owner}/{repo}</a>.')

      issue = self.graphql(GRAPHQL_REPO, locals())
      resp = self.graphql(GRAPHQL_ADD_STAR, {
        'starrable_id': issue['repository']['id'],
      })
      return source.creation_result({
        'url': base_url + '/stargazers',
      })

    elif type == 'tag':  # add label
      if not (len(path) == 4 and path[2] in ('issues', 'pull')):
        return source.creation_result(
          abort=True, error_plain='GitHub tag post requires tag-of issue or PR URL.')

      tags = set(util.trim_nulls(t.get('displayName', '').strip()
                                 for t in util.get_list(obj, 'object')))
      if not tags:
        return source.creation_result(
          abort=True, error_plain='No tags found in tag post!')

      existing_labels = self.existing_labels(owner, repo)
      labels = sorted(tags & existing_labels)
      issue_link = f'<a href="{base_url}">{owner}/{repo}#{number}</a>'
      if not labels:
        return source.creation_result(
          abort=True,
          error_html=f"No tags in [{', '.join(sorted(tags))}] matched {issue_link}'s existing labels [{', '.join(sorted(existing_labels))}].")

      if preview:
        return source.creation_result(
          description=f"add label{'s' if len(labels) > 1 else ''} <span class=\"verb\">{', '.join(labels)}</span> to {issue_link}.")

      resp = self.rest(REST_ISSUE_LABELS % (owner, repo, number), labels)
      return source.creation_result({
        'url': base_url,
        'type': 'tag',
        'tags': labels,
      })

    else:  # new issue
      if not (len(path) == 2 or (len(path) == 3 and path[2] == 'issues')):
        return source.creation_result(
          abort=True, error_plain='New GitHub issue requires in-reply-to repo URL')

      title = util.ellipsize(obj.get('displayName') or obj.get('title') or
                             orig_content)
      tags = set(util.trim_nulls(t.get('displayName', '').strip()
                                 for t in util.get_list(obj, 'tags')))
      labels = sorted(tags & self.existing_labels(owner, repo))

      if preview:
        preview_content = f'<b>{title}</b><hr>{self.render_markdown(content, owner, repo)}'
        preview_labels = ''
        if labels:
          preview_labels = f" and attempt to add label{'s' if len(labels) > 1 else ''} <span class=\"verb\">{', '.join(labels)}</span>"
        return source.creation_result(content=preview_content, description=f"""<span class="verb">create a new issue</span> on <a href="{base_url}">{owner}/{repo}</a>{preview_labels}:""")
      else:
        resp = self.rest(REST_CREATE_ISSUE % (owner, repo), {
          'title': title,
          'body': content,
          'labels': labels,
        })
        resp['url'] = resp.pop('html_url')
        return source.creation_result(resp)

    return source.creation_result(
      abort=False,
      error_plain=f"{base_url} doesn't look like a GitHub repo, issue, or PR URL.")

  def existing_labels(self, owner, repo):
    """Fetches and returns a repo's labels.

    Args:
      owner (str): GitHub username or org that owns the repo
      repo (str)

    Returns:
      set of str:
    """
    resp = self.graphql(GRAPHQL_REPO_LABELS, locals())

    repo = resp.get('repository')
    if not repo:
      return set()

    return {node['name'] for node in repo['labels']['nodes']}

  def issue_to_as1(self, issue):
    """Converts a GitHub issue or pull request to ActivityStreams.

    Handles both v4 GraphQL and v3 REST API issue and PR objects.

    * https://developer.github.com/v4/object/issue/
    * https://developer.github.com/v4/object/pullrequest/
    * https://developer.github.com/v3/issues/
    * https://developer.github.com/v3/pulls/

    Args:
      issue (dict): GitHub issue or PR

    Returns:
      dict: ActivityStreams object
    """
    obj = self._to_as1(issue, repo_id=True)
    if not obj:
      return obj

    repo_url = re.sub(r'/(issue|pull)s?/[0-9]+$', '', obj['url'])
    if issue.get('merged') is not None:
      type = 'pull-request'
      in_reply_to = repo_url + '/tree/' + (issue.get('base', {}).get('ref') or 'master')
    else:
      type = 'issue'
      in_reply_to = repo_url + '/issues'

    obj.update({
      'objectType': type,
      'inReplyTo': [{'url': in_reply_to}],
      'tags': [{
        'displayName': l['name'],
        'url': f"{repo_url}/labels/{urllib.parse.quote(l['name'])}",
      } for l in issue.get('labels', []) if l.get('name')],
    })
    return self.postprocess_object(obj)

  issue_to_object = issue_to_as1
  """Deprecated! Use :meth:`issue_to_as1` instead."""

  pr_to_as1 = issue_to_as1

  pr_to_object = pr_to_as1
  """Deprecated! Use :meth:`pr_to_as1` instead."""

  def comment_to_as1(self, comment):
    """Converts a GitHub comment to ActivityStreams.

    Handles both v4 GraphQL and v3 REST API issue objects.

    * https://developer.github.com/v4/object/issue/
    * https://developer.github.com/v3/issues/

    Args:
      comment (dict): GitHub issue

    Returns:
      dict: ActivityStreams comment
    """
    obj = self._to_as1(comment, repo_id=True)
    if not obj:
      return obj

    obj.update({
      'objectType': 'comment',
      # url is e.g. https://github.com/foo/bar/pull/123#issuecomment-456
      'inReplyTo': [{'url': util.fragmentless(obj['url'])}],
    })
    return self.postprocess_object(obj)

  comment_to_object = comment_to_as1
  """Deprecated! Use :meth:`comment_to_as1` instead."""

  def reaction_to_as1(self, reaction, target):
    """Converts a GitHub emoji reaction to ActivityStreams.

    Handles v3 REST API reaction objects.

    https://developer.github.com/v3/reactions/

    Args:
      reaction (dict): v3 GitHub reaction
      target (dict): ActivityStreams object of reaction

    Returns:
      dict: ActivityStreams reaction
    """
    obj = self._to_as1(reaction)
    if not obj:
      return obj

    content = REACTIONS_REST_CHARS.get(reaction.get('content'))
    enum = (REACTIONS_GRAPHQL.get(content) or '').lower()
    author = self.to_as1_actor(reaction.get('user'))
    username = author.get('username')

    obj.update({
      'objectType': 'activity',
      'verb': 'react',
      'id': target['id'] + f'_{enum}_by_{username}',
      'url': target['url'] + f'#{enum}-by-{username}',
      'author': author,
      'content': content,
      'object': {'url': target['url']},
    })
    return self.postprocess_object(obj)

  reaction_to_object = reaction_to_as1
  """Deprecated! Use :meth:`reaction_to_as1` instead."""

  def to_as1_actor(self, user):
    """Converts a GitHub user to an ActivityStreams actor.

    Handles both v4 GraphQL and v3 REST API user objects.

    * https://developer.github.com/v4/object/user/
    * https://developer.github.com/v3/users/

    Args:
      user (dict): GitHub user

    Returns:
      dict: ActivityStreams actor
    """
    actor = self._to_as1(user)
    if not actor:
      return actor

    username = user.get('login')
    desc = user.get('bio') or user.get('description')

    actor.update({
      # TODO: orgs, bots
      'objectType': 'person',
      'displayName': user.get('name') or username,
      'username': username,
      'email': user.get('email'),
      'description': desc,
      'summary': desc,
      'image': {'url': user.get('avatarUrl') or user.get('avatar_url') or user.get('url')},
      'location': {'displayName': user.get('location')},
    })

    # extract web site links. extract_links uniquifies and preserves order
    urls = sum((util.extract_links(user.get(field)) for field in (
      'html_url',  # REST
      'url',  # both
      'websiteUrl',  # GraphQL
      'blog',  # REST
      'bio',   # both
    )), [])
    urls = [u for u in urls if util.domain_from_link(u) != 'api.github.com']
    if urls:
      actor['url'] = urls[0]
      if len(urls) > 1:
        actor['urls'] = [{'value': u} for u in urls]

    return self.postprocess_object(actor)

  user_to_actor = to_as1_actor
  """Deprecated! Use :meth:`to_as1_actor` instead."""

  def _to_as1(self, input, repo_id=False):
    """Starts to convert a GraphQL or REST API object to ActivityStreams.

    Args:
      input (dict): GraphQL or REST object
      repo_id (bool): whether to inject repo owner and name into id

    Returns:
      dict: ActivityStreams object
    """
    if not input:
      return {}

    id = input.get('node_id') or input.get('id')
    number = input.get('number')
    url = input.get('html_url') or input.get('url') or ''
    if repo_id and id and url:
      # inject repo owner and name
      path = urllib.parse.urlparse(url).path.strip('/').split('/')
      owner, repo = path[:2]
      # join with : because github allows ., _, and - in repo names. (see
      # REPO_NAME_RE.)
      id = ':'.join((owner, repo, str(number or id)))

    return {
      'id': self.tag_uri(id),
      'url': url,
      'author': self.to_as1_actor(input.get('author') or input.get('user')),
      'displayName': input.get('title'),
      'content': (input.get('body') or '').replace('\r\n', '\n'),
      'published': util.maybe_iso8601_to_rfc3339(input.get('createdAt') or
                                                 input.get('created_at')),
      'updated': util.maybe_iso8601_to_rfc3339(input.get('lastEditedAt') or
                                               input.get('updated_at')),
    }
