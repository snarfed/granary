"""Unit tests for github.py."""
import copy
from unittest import skip
from unittest.mock import patch

from webutil import testutil, util
from webutil.testutil import requests_response
from webutil.util import json_dumps, json_loads

from .. import github
from ..github import (
  GRAPHQL_BASE,
  GRAPHQL_COMMENT,
  REACTIONS_REST_CHARS,
  REST_COMMENT,
  REST_COMMENT_REACTIONS,
  REST_COMMENTS,
  REST_ISSUE,
  REST_ISSUE_LABELS,
  REST_MARKDOWN,
  REST_NOTIFICATIONS,
  REST_REACTIONS,
)
from .. import source

# test data
def tag_uri(name):
  return util.tag_uri('github.com', name)

USER_GRAPHQL = {  # GitHub
  'id': 'MDQ6VXNlcjc3ODA2OA==',
  'login': 'snarfed',
  'resourcePath': '/snarfed',
  'url': 'https://github.com/snarfed',
  'avatarUrl': 'https://avatars2.githubusercontent.com/u/778068?v=4',
  'email': 'github@ryanb.org',
  'location': 'San Francisco',
  'name': 'Ryan Barrett',
  'websiteUrl': 'https://snarfed.org/',
  'bio': 'foo https://brid.gy/\r\nbar',  # may be null
  'bioHTML': """\
<div>foo <a href="https://brid.gy/" rel="nofollow">https://brid.gy/</a>
bar</div>""",
  'company': 'Bridgy',
  'companyHTML': '<div><a href="https://github.com/bridgy" class="user-mention">bridgy</a></div>',
  'createdAt': '2011-05-10T00:39:24Z',
}
USER_REST = {  # GitHub
  'id': 778068,
  'node_id': 'MDQ6VXNlcjc3ODA2OA==',
  'login': 'snarfed',
  'avatar_url': 'https://avatars2.githubusercontent.com/u/778068?v=4',
  'url': 'https://api.github.com/users/snarfed',
  'html_url': 'https://github.com/snarfed',
  'type': 'User',
  'location': 'San Francisco',
  'name': 'Ryan Barrett',
  'blog': 'https://snarfed.org/',
  'bio': 'foo https://brid.gy/\r\nbar',
  'site_admin': False,
  'company': 'Bridgy',
  'email': 'github@ryanb.org',
  'hireable': None,
  'followers': 20,
  'following': 1,
  'created_at': '2011-05-10T00:39:24Z',
}
ORGANIZATION_REST = {
  'login': 'a_company',
  'id': 789,
  'type': 'Organization',
  'site_admin': False,
  'avatar_url': 'https://avatars0.githubusercontent.com/u/789?v=4',
  'gravatar_id': '',
  'url': 'https://api.github.com/users/color',
  'html_url': 'https://github.com/color',
  'repos_url': 'https://api.github.com/users/color/repos',
}
ACTOR = {  # ActivityStreams
  'objectType': 'person',
  'displayName': 'Ryan Barrett',
  'image': {'url': 'https://avatars2.githubusercontent.com/u/778068?v=4'},
  'id': tag_uri('MDQ6VXNlcjc3ODA2OA=='),
  'published': '2011-05-10T00:39:24+00:00',
  'url': 'https://github.com/snarfed',
  'urls': [
    {'value': 'https://github.com/snarfed'},
    {'value': 'https://snarfed.org/'},
    {'value': 'https://brid.gy/'},
  ],
  'username': 'snarfed',
  'email': 'github@ryanb.org',
  'description': 'foo https://brid.gy/\r\nbar',
  'summary': 'foo https://brid.gy/\r\nbar',
  'location': {'displayName': 'San Francisco'},
  }
ISSUE_GRAPHQL = {  # GitHub
  'id': 'MDU6SXNzdWUyOTI5MDI1NTI=',
  'number': 333,
  'url': 'https://github.com/foo/bar/issues/333',
  'resourcePath': '/foo/bar/issues/333',
  'repository': {
    'id': 'MDEwOlJlcG9zaXRvcnkzMDIwMzkzNQ==',
  },
  'author': USER_GRAPHQL,
  'title': 'an issue title',
  # note that newlines are \r\n in body but \n in bodyHTML and bodyText
  'body': 'foo bar\r\nbaz',
  'bodyHTML': '<p>foo bar\nbaz</p>',
  'bodyText': 'foo bar\nbaz',
  'state': 'OPEN',
  'closed': False,
  'locked': False,
  'closedAt': None,
  'createdAt': '2018-01-30T19:11:03Z',
  'lastEditedAt': '2018-02-01T19:11:03Z',
  'publishedAt': '2005-01-30T19:11:03Z',
}
ISSUE_REST = {  # GitHub
  'id': 53289448,
  'node_id': 'MDU6SXNzdWUyOTI5MDI1NTI=',
  'number': 333,
  'url': 'https://api.github.com/repos/foo/bar/issues/333',
  'html_url': 'https://github.com/foo/bar/issues/333',
  'comments_url': 'https://api.github.com/repos/foo/bar/issues/333/comments',
  'title': 'an issue title',
  'user': USER_REST,
  'body': 'foo bar\nbaz',
  'labels': [{
    'id': 281245471,
    'node_id': 'MDU6TGFiZWwyODEyNDU0NzE=',
    'name': 'new silo',
    'color': 'fbca04',
    'default': False,
  }],
  'state': 'open',
  'locked': False,
  'assignee': None,
  'assignees': [],
  'comments': 20,
  'created_at': '2018-01-30T19:11:03Z',
  'updated_at': '2018-02-01T19:11:03Z',
  'author_association': 'OWNER',
}
ISSUE_OBJ = {  # ActivityStreams
  'objectType': 'issue',
  'id': tag_uri('foo:bar:333'),
  'url': 'https://github.com/foo/bar/issues/333',
  'author': ACTOR,
  'displayName': 'an issue title',
  'content': 'foo bar\nbaz',
  'published': '2018-01-30T19:11:03+00:00',
  'updated': '2018-02-01T19:11:03+00:00',
  'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
  'tags': [{
    'displayName': 'new silo',
    'url': 'https://github.com/foo/bar/labels/new%20silo',
  }],
}
ISSUE_OBJ_WITH_LABELS = copy.deepcopy(ISSUE_OBJ)
ISSUE_OBJ_WITH_LABELS.update({
  'tags': [{
    'objectType': 'person',
    'url': 'https://github.com/someone/',
  }, {
    'url': 'https://flickr.com/a/repo',
  }, {
    'displayName': '  label_1 ',
  }, {
    'displayName': 'label 2\t\n',
    'objectType': 'hashtag',
  }, {
    'displayName': 'label 3',
  }],
})
REPO_REST = {
  'id': 55900011,
  'name': 'bridgy',
  'full_name': 'someone/bridgy',
  'homepage': 'https://brid.gy/',
  'owner': ORGANIZATION_REST,
  'private': True,
  'html_url': 'https://github.com/someone/bridgy',
  'url': 'https://api.github.com/repos/someone/bridgy',
  'issues_url': 'https://api.github.com/repos/color/color/issues{/number}',
  'pulls_url': 'https://api.github.com/repos/color/color/pulls{/number}',
  'description': 'Bridgy pulls comments and likes from social networks back to your web site. You can also use it to publish your posts to those networks.',
  'fork': True,
  'created_at': '2016-04-10T13:19:29Z',
  'updated_at': '2016-04-10T13:19:30Z',
  'git_url': 'git://github.com/someone/bridgy.git',
  'archived': False,
  # ...
}
PULL_REST = {  # GitHub
  'id': 167930804,
  'number': 444,
  'url': 'https://api.github.com/repos/foo/bar/pulls/444',
  'html_url': 'https://github.com/foo/bar/pull/444',
  'user': USER_REST,
  'title': 'a PR to merge',
  'body': 'a PR message',
  'issue_url': 'https://api.github.com/repos/foo/bar/issues/444',
  'diff_url': 'https://github.com/foo/bar/pull/444.diff',
  'patch_url': 'https://github.com/foo/bar/pull/444.patch',
  'state': 'closed',
  'locked': False,
  'created_at': '2018-02-08T10:24:32Z',
  'updated_at': '2018-02-09T21:14:43Z',
  'closed_at': '2018-02-09T21:14:43Z',
  'merged_at': '2018-02-09T21:14:43Z',
  'merge_commit_sha': '6a0c660915237c3753852bba090a4ac603e3e7cd',
  'assignee': None,
  'assignees': [],
  'requested_reviewers': [],
  'requested_teams': [],
  'labels': [],
  'milestone': None,
  'commits_url': 'https://api.github.com/repos/foo/bar/pulls/444/commits',
  'review_comments_url': 'https://api.github.com/repos/foo/bar/pulls/444/comments',
  'review_comment_url': 'https://api.github.com/repos/foo/bar/pulls/comments{/number}',
  'comments_url': 'https://api.github.com/repos/foo/bar/issues/444/comments',
  'statuses_url': 'https://api.github.com/repos/foo/bar/statuses/678a4df6e3bf2f7068a58bb1485258985995ca67',
  'head': {},  # contents of these elided...
  'base': {},
  'author_association': 'CONTRIBUTOR',
  'merged': True,
  'merged_by': USER_REST,
  # this is in PR objects but not issues
  'repo': REPO_REST,
}
PULL_OBJ = {  # ActivityStreams
  'objectType': 'pull-request',
  'id': tag_uri('foo:bar:444'),
  'url': 'https://github.com/foo/bar/pull/444',
  'author': ACTOR,
  'displayName': 'a PR to merge',
  'content': 'a PR message',
  'published': '2018-02-08T10:24:32+00:00',
  'updated': '2018-02-09T21:14:43+00:00',
  'inReplyTo': [{'url': 'https://github.com/foo/bar/tree/master'}],
}
# Note that issue comments and top-level PR comments look identical, and even
# use the same API endpoint, with */issue/*. (This doesn't include diff or
# commit comments, which granary doesn't currently support.)
COMMENT_GRAPHQL = {  # GitHub
  'id': 'MDEwOlNQ==',
  'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
  'author': USER_GRAPHQL,
  'body': 'i have something to say here',
  'bodyHTML': 'i have something to say here',
  'createdAt': '2015-07-23T18:47:58Z',
  'lastEditedAt': '2015-07-23T19:47:58Z',
  'publishedAt': '2005-01-30T19:11:03Z',
}
COMMENT_REST = {  # GitHub
  'id': 456,
  # comments don't yet have node_id, as of 2/14/2018
  'html_url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
  # these API endpoints below still use /issues/, even for PRs
  'url': 'https://api.github.com/repos/foo/bar/issues/comments/456',
  'issue_url': 'https://api.github.com/repos/foo/bar/issues/123',
  'user': USER_REST,
  'created_at': '2015-07-23T18:47:58Z',
  'updated_at': '2015-07-23T19:47:58Z',
  'author_association': 'CONTRIBUTOR',  # or OWNER or NONE
  'body': 'i have something to say here',
}
COMMENT_OBJ = {  # ActivityStreams
  'objectType': 'comment',
  'id': tag_uri('foo:bar:456'),
  'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
  'author': ACTOR,
  'content': 'i have something to say here',
  'inReplyTo': [{'url': 'https://github.com/foo/bar/pull/123'}],
  'published': '2015-07-23T18:47:58+00:00',
  'updated': '2015-07-23T19:47:58+00:00',
}
ISSUE_OBJ_WITH_REPLIES = copy.deepcopy(ISSUE_OBJ)
ISSUE_OBJ_WITH_REPLIES.update({
  'replies': {
    'items': [COMMENT_OBJ, COMMENT_OBJ],
    'totalItems': 2,
  },
  'to': [{'objectType': 'group', 'alias': '@private'}],
})
REACTION_REST = {  # GitHub v3
  'id': 19894970,
  'content': '+1',
  'created_at': '2018-02-21T19:49:16Z',
  'user': USER_REST,
}
REACTION_OBJ = {  # ActivityStreams
  'id': tag_uri('foo:bar:333_thumbs_up_by_snarfed'),
  'url': 'https://github.com/foo/bar/issues/333#thumbs_up-by-snarfed',
  'objectType': 'activity',
  'verb': 'react',
  'author': ACTOR,
  'content': REACTIONS_REST_CHARS['+1'],
  'object': {'url': 'https://github.com/foo/bar/issues/333'},
  'published': '2018-02-21T19:49:16+00:00',
}
REACTION_OBJ_INPUT = {  # ActivityStreams, for create/preview
  'objectType': 'comment',
  'content': REACTIONS_REST_CHARS['+1'],
  'inReplyTo': [{'url': 'https://github.com/foo/bar/pull/123'}],
}
COMMENT_REACTION_OBJ_INPUT = {  # ActivityStreams, for create/preview
  'objectType': 'comment',
  'content': REACTIONS_REST_CHARS['+1'],
  'inReplyTo': [{'url': 'https://github.com/foo/bar/pull/123#issuecomment-456'}],
}
ISSUE_OBJ_WITH_REACTIONS = copy.deepcopy(ISSUE_OBJ)
ISSUE_OBJ_WITH_REACTIONS.update({
  'tags': ISSUE_OBJ['tags'] + [REACTION_OBJ, REACTION_OBJ],
  'to': [{'objectType': 'group', 'alias': '@private'}],
})
LIKE_OBJ = {
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://github.com/foo/bar'},
}
TAG_ACTIVITY = {
  'objectType': 'activity',
  'verb': 'tag',
  'object': [
    {'displayName': 'one'},
    {'displayName': 'three'},
  ],
  'target': {'url': 'https://github.com/foo/bar/issues/456'},
}
NOTIFICATION_PULL_REST = {  # GitHub
  'id': '302190598',
  'unread': False,
  'reason': 'review_requested',
  'updated_at': '2018-02-12T19:17:58Z',
  'last_read_at': '2018-02-12T20:55:10Z',
  'repository': REPO_REST,
  'url': 'https://api.github.com/notifications/threads/302190598',
  'merged': False,
  'subject': {
    'title': 'Foo bar baz',
    # TODO: we translate pulls to issues in these URLs to get the top-level comments
    'url': 'https://api.github.com/repos/foo/bar/pulls/123',
    'latest_comment_url': 'https://api.github.com/repos/foo/bar/pulls/123',
    'type': 'PullRequest',
  },
}
NOTIFICATION_ISSUE_REST = copy.deepcopy(NOTIFICATION_PULL_REST)
NOTIFICATION_ISSUE_REST.update({
  'subject': {'url': 'https://api.github.com/repos/foo/baz/issues/456'},
})
EXPECTED_HEADERS = {
  'Authorization': 'token a-towkin',
}


# response builders (return a fake requests.Response for use as a mock
# return_value or side_effect element)
def graphql_response(data):
  return requests_response({'data': data})

ISSUE_GRAPHQL_RESPONSE = graphql_response({
  'repository': {'issueOrPullRequest': ISSUE_GRAPHQL},
})

def get_labels_graphql_response(labels):
  return graphql_response({
    'repository': {'labels': {'nodes': [{'name': l} for l in labels]}},
  })


class GitHubTest(testutil.TestCase):

  def setUp(self):
    super(GitHubTest, self).setUp()
    self.gh = github.GitHub('a-towkin')
    self.batch = []
    self.batch_responses = []

    self.mock_get = self.start_patch(util.session, 'get')
    self.mock_post = self.start_patch(util.session, 'post')

  # call assertion helpers
  def assert_graphql(self, query):
    """Asserts a GraphQL POST with the given query was made."""
    for c in self.mock_post.call_args_list:
      if c.args[0] == GRAPHQL_BASE and c.kwargs['json'].get('query') == query:
        self.assertEqual('bearer a-towkin', c.kwargs['headers']['Authorization'])
        return

    self.fail(f'No GraphQL call with query {query!r:.100} found')

  def assert_get(self, url, **kwargs):
    self._assert_rest(self.mock_get, url, **kwargs)

  def assert_post(self, url, **kwargs):
    self._assert_rest(self.mock_post, url, **kwargs)

  def _assert_rest(self, mock, url, **kwargs):
    """Asserts a REST GET to url was made."""
    for c in mock.call_args_list:
      if c.args[0] == url:
        self.assertEqual('token a-towkin', c.kwargs['headers']['Authorization'])
        for key, val in kwargs.items():
          if val:
            self.assert_equals(val, c.kwargs[key], key)
        return

    self.fail(f'No GET to {url} found in {[c.args[0] for c in mock.call_args_list]}')

  def test_base_id(self):
    for url, expected in (
        ('https://github.com/a/b/issues/1', 'a:b:1'),
        ('https://github.com/a/b/pull/1', 'a:b:1'),
        ('https://github.com/a/b/issues/1#', 'a:b:1'),
        ('http://github.com/a/b/issues/1#issuecomment=2', 'a:b:1'),
        ('http://github.com/a/b', None),
        ('https://github.com/', None),
        ('https://foo/bar', None),
    ):
      self.assertEqual(expected, self.gh.base_id(url))

  def test_to_as1_actor_graphql(self):
    self.assert_equals(ACTOR, self.gh.to_as1_actor(USER_GRAPHQL))

  def test_to_as1_actor_rest(self):
    self.assert_equals(ACTOR, self.gh.to_as1_actor(USER_REST))

  def test_to_as1_actor_minimal(self):
    actor = self.gh.to_as1_actor({'id': '123'})
    self.assert_equals(tag_uri('123'), actor['id'])

  def test_to_as1_actor_empty(self):
    self.assert_equals({}, self.gh.to_as1_actor({}))

  def test_get_actor(self):
    self.mock_post.return_value = graphql_response({'user': USER_GRAPHQL})
    self.assert_equals(ACTOR, self.gh.get_actor('foo'))
    self.assert_graphql(github.GRAPHQL_USER % {'login': 'foo'})

  def test_get_actor_default(self):
    self.mock_post.return_value = graphql_response({'viewer': USER_GRAPHQL})
    self.assert_equals(ACTOR, self.gh.get_actor())
    self.assert_graphql( github.GRAPHQL_VIEWER)

  def test_get_activities_defaults(self):
    notifs = [copy.deepcopy(NOTIFICATION_PULL_REST),
              copy.deepcopy(NOTIFICATION_ISSUE_REST)]
    del notifs[0]['repository']
    notifs[1].update({
      # check that we don't fetch this since we don't pass fetch_replies
      'comments_url': 'http://unused',
      'repository': {'private': False},
    })

    self.mock_get.side_effect = [
      requests_response(notifs),
      requests_response(PULL_REST),
      requests_response(ISSUE_REST),
    ]

    obj_public_repo = copy.deepcopy(ISSUE_OBJ)
    obj_public_repo['to'] = [{'objectType': 'group', 'alias': '@public'}]
    self.assert_equals([PULL_OBJ, obj_public_repo], self.gh.get_activities())
    self.assert_get(REST_NOTIFICATIONS)
    self.assert_get(NOTIFICATION_PULL_REST['subject']['url'])
    self.assert_get(NOTIFICATION_ISSUE_REST['subject']['url'])

  def test_get_activities_fetch_replies(self):
    self.mock_get.side_effect = [
      requests_response([NOTIFICATION_ISSUE_REST]),
      requests_response(ISSUE_REST),
      requests_response([COMMENT_REST, COMMENT_REST]),
    ]
    self.assert_equals([ISSUE_OBJ_WITH_REPLIES],
                       self.gh.get_activities(fetch_replies=True))
    self.assert_get(REST_NOTIFICATIONS)
    self.assert_get(NOTIFICATION_ISSUE_REST['subject']['url'])
    self.assert_get(ISSUE_REST['comments_url'])

  def test_get_activities_fetch_likes(self):
    self.mock_get.side_effect = [
      requests_response([NOTIFICATION_PULL_REST, NOTIFICATION_ISSUE_REST]),
      requests_response(PULL_REST),
      requests_response(ISSUE_REST),
      requests_response([]),
      requests_response([REACTION_REST, REACTION_REST]),
    ]

    pull_obj = copy.deepcopy(PULL_OBJ)
    pull_obj['to'] = [{'objectType': 'group', 'alias': '@private'}]
    self.assert_equals([pull_obj, ISSUE_OBJ_WITH_REACTIONS],
                       self.gh.get_activities(fetch_likes=True))
    self.assert_get(REST_NOTIFICATIONS)
    self.assert_get(NOTIFICATION_PULL_REST['subject']['url'])
    self.assert_get(NOTIFICATION_ISSUE_REST['subject']['url'])
    self.assert_get(REST_REACTIONS % ('foo', 'bar', 444))
    self.assert_get(REST_REACTIONS % ('foo', 'bar', 333))

  def test_get_activities_self_empty(self):
    self.mock_get.return_value = requests_response([])
    self.assert_equals([], self.gh.get_activities(count=12))
    self.assert_get(f'{REST_NOTIFICATIONS}&per_page=12')

  def test_get_activities_activity_id(self):
    self.mock_get.return_value = requests_response(ISSUE_REST)
    self.assert_equals([ISSUE_OBJ], self.gh.get_activities(activity_id='foo:bar:123'))
    self.assert_get(REST_ISSUE % ('foo', 'bar', 123))

  def test_get_activities_activity_id_fetch_replies_likes(self):
    self.mock_get.side_effect = [
      requests_response(ISSUE_REST),
      requests_response([COMMENT_REST, COMMENT_REST]),
      requests_response([REACTION_REST, REACTION_REST]),
    ]

    expected = copy.deepcopy(ISSUE_OBJ_WITH_REPLIES)
    expected['tags'].extend([REACTION_OBJ, REACTION_OBJ])
    del expected['to']

    self.assert_equals([expected], self.gh.get_activities(
      activity_id='foo:bar:333', fetch_replies=True, fetch_likes=True))
    self.assert_get(REST_ISSUE % ('foo', 'bar', 333))
    self.assert_get(ISSUE_REST['comments_url'])
    self.assert_get(REST_REACTIONS % ('foo', 'bar', 333))

  def test_get_activities_etag_and_since(self):
    self.mock_get.side_effect = [
      requests_response([NOTIFICATION_ISSUE_REST],
                        headers={'Last-Modified': 'Fri, 1 Jan 2099 12:00:00 GMT'}),
      requests_response(ISSUE_REST),
      requests_response([COMMENT_REST, COMMENT_REST]),
    ]

    self.assert_equals({
      'etag': 'Fri, 1 Jan 2099 12:00:00 GMT',
      'startIndex': 0,
      'itemsPerPage': 1,
      'totalResults': 1,
      'items': [ISSUE_OBJ_WITH_REPLIES],
      'filtered': False,
      'sorted': False,
      'updatedSince': False,
    }, self.gh.get_activities_response(etag='Thu, 25 Oct 2012 15:16:27 GMT',
                                       fetch_replies=True))
    self.assert_get(REST_NOTIFICATIONS)
    self.assert_get(NOTIFICATION_ISSUE_REST['subject']['url'])
    self.assert_get(ISSUE_REST['comments_url'] + '?since=2012-10-25T15:16:27Z')
    notif_call = next(c for c in self.mock_get.call_args_list
                      if c.args[0] == REST_NOTIFICATIONS)
    self.assertEqual('Thu, 25 Oct 2012 15:16:27 GMT',
                     notif_call.kwargs['headers']['If-Modified-Since'])

  def test_get_activities_etag_returns_304(self):
    self.mock_get.return_value = requests_response(
      '', status=304, headers={'Last-Modified': 'Fri, 1 Jan 2099 12:00:00 GMT'})

    resp = self.gh.get_activities_response(etag='Thu, 25 Oct 2012 15:16:27 GMT',
                                           fetch_replies=True)
    self.assert_equals('Fri, 1 Jan 2099 12:00:00 GMT', resp['etag'])
    self.assert_equals([], resp['items'])

  def test_get_activities_activity_id_not_found(self):
    self._test_get_activities_activity_id_fails(404)

  def test_get_activities_activity_id_deleted(self):
    self._test_get_activities_activity_id_fails(410)

  def test_get_activities_activity_id_unavailable_for_legal_reasons(self):
    self._test_get_activities_activity_id_fails(451)

  def _test_get_activities_activity_id_fails(self, status):
    self.mock_get.return_value = requests_response({
      'message': 'Not Found',
      'documentation_url': 'https://developer.github.com/v3',
    }, status=status)
    self.assert_equals([], self.gh.get_activities(activity_id='a:b:1'))
    self.assert_get(REST_ISSUE % ('a', 'b', 1))

  def test_get_activities_bad_activity_id(self):
    for bad in 'no_colons', 'one:colon', 'fo:ur:col:ons':
      with self.assertRaises(ValueError):
        self.assert_equals([], self.gh.get_activities(activity_id=bad))

  def test_get_activities_pr_not_found(self):
    self._test_get_activities_pr_fails(404)

  def test_get_activities_pr_deleted(self):
    self._test_get_activities_pr_fails(410)

  def test_get_activities_pr_unavailable_for_legal_reasons(self):
    self._test_get_activities_pr_fails(451)

  def _test_get_activities_pr_fails(self, status):
    self.mock_get.side_effect = [
      requests_response([NOTIFICATION_PULL_REST, NOTIFICATION_ISSUE_REST]),
      requests_response('', status=status),
      requests_response(ISSUE_REST),
    ]

    obj_public_repo = copy.deepcopy(ISSUE_OBJ)
    obj_public_repo['to'] = [{'objectType': 'group', 'alias': '@private'}]
    self.assert_equals([obj_public_repo], self.gh.get_activities())
    self.assert_get(REST_NOTIFICATIONS)
    self.assert_get(NOTIFICATION_PULL_REST['subject']['url'])
    self.assert_get(NOTIFICATION_ISSUE_REST['subject']['url'])

  def test_get_activities_search_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(search_query='foo')

  def test_get_activities_fetch_events_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_events='foo')

  def test_get_activities_fetch_shares_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_shares='foo')

  def test_issue_to_as1_graphql(self):
    obj = copy.deepcopy(ISSUE_OBJ)
    del obj['tags']
    self.assert_equals(obj, self.gh.issue_to_as1(ISSUE_GRAPHQL))

  def test_issue_to_as1_rest(self):
    self.assert_equals(ISSUE_OBJ, self.gh.issue_to_as1(ISSUE_REST))

  def test_issue_to_as1_pull_rest(self):
    self.assert_equals(PULL_OBJ, self.gh.issue_to_as1(PULL_REST))

  def test_issue_to_as1_rest_body_none(self):
    issue = copy.deepcopy(ISSUE_REST)
    issue['body'] = None
    obj = copy.deepcopy(ISSUE_OBJ)
    del obj['content']
    self.assert_equals(obj, self.gh.issue_to_as1(issue))

  def test_issue_to_as1_minimal(self):
    # just test that we don't crash
    self.gh.issue_to_as1({'id': '123', 'body': 'asdf'})

  def test_issue_to_as1_empty(self):
    self.assert_equals({}, self.gh.issue_to_as1({}))

  def test_get_comment_rest(self):
    self.mock_get.return_value = requests_response(COMMENT_REST)
    self.assert_equals(COMMENT_OBJ, self.gh.get_comment('foo:bar:123'))
    self.assert_get(REST_COMMENT % ('foo', 'bar', 'issues', 123))

  def test_get_comment_graphql(self):
    self.mock_post.return_value = graphql_response({'node': COMMENT_GRAPHQL})

    obj = copy.deepcopy(COMMENT_OBJ)
    obj['id'] = 'tag:github.com:foo:bar:MDEwOlNQ=='
    self.assert_equals(obj, self.gh.get_comment('foo:bar:abc'))
    self.assert_graphql( GRAPHQL_COMMENT % {'id': 'abc'})

  def test_get_activities_bad_comment_id(self):
    for bad in 'no_colons', 'one:colon', 'fo:ur:col:ons':
      with self.assertRaises(ValueError):
        self.assert_equals([], self.gh.get_comment(bad))

  def test_comment_to_as1_graphql(self):
    obj = copy.deepcopy(COMMENT_OBJ)
    obj['id'] = tag_uri('foo:bar:' + COMMENT_GRAPHQL['id'])
    self.assert_equals(obj, self.gh.comment_to_as1(COMMENT_GRAPHQL))

  def test_comment_to_as1_rest(self):
    self.assert_equals(COMMENT_OBJ, self.gh.comment_to_as1(COMMENT_REST))

  def test_comment_to_as1_minimal(self):
    # just test that we don't crash
    self.gh.comment_to_as1({'id': '123', 'message': 'asdf'})

  def test_comment_to_as1_empty(self):
    self.assert_equals({}, self.gh.comment_to_as1({}))

  def test_reaction_to_as1_rest(self):
    self.assert_equals(REACTION_OBJ,
                       self.gh.reaction_to_as1(REACTION_REST, ISSUE_OBJ))

  def test_create_comment(self):
    self.mock_post.return_value = requests_response({
        'id': 456,
        'html_url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
      })

    result = self.gh.create(COMMENT_OBJ)
    self.assert_equals({
      'type': 'comment',
      'id': 456,
      'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
    }, result.content, result)
    self.assert_post(REST_COMMENTS % ('foo', 'bar', 123),
                     json={'body': 'i have something to say here'})

  def test_preview_comment(self):
    self.mock_post.side_effect = [
      ISSUE_GRAPHQL_RESPONSE,
      requests_response('<p>rendered!</p>'),
    ]

    preview = self.gh.preview_create(COMMENT_OBJ)
    self.assertEqual('<p>rendered!</p>', preview.content, preview)
    self.assertIn('<span class="verb">comment</span> on <a href="https://github.com/foo/bar/pull/123">foo/bar#123, <em>an issue title</em></a>:', preview.description, preview)
    self.assert_post(REST_MARKDOWN, json={
      'text': 'i have something to say here',
      'mode': 'gfm',
      'context': 'foo/bar',
    })

  @skip('only needed for GraphQL, and we currently use REST to create comments')
  def test_create_comment_escape_quotes(self):
    self.mock_post.return_value = graphql_response(
      {'addComment': {'commentEdge': {'node': {'foo': 'bar'}}}})

    obj = copy.deepcopy(COMMENT_OBJ)
    obj['content'] = """one ' two " three"""
    result = self.gh.create(obj)
    self.assert_equals({'foo': 'bar'}, result.content, result)

  def test_preview_comment_private_repo(self):
    """eg the w3c/AB repo is private and returns repository: None
    https://console.cloud.google.com/errors/CP2z6O3Hub755wE
    """
    self.mock_post.side_effect = [
      graphql_response({'repository': None}),
      requests_response('<p>rendered!</p>'),
    ]

    preview = self.gh.preview_create(COMMENT_OBJ)
    self.assertEqual('<p>rendered!</p>', preview.content, preview)
    self.assertIn('<span class="verb">comment</span> on <a href="https://github.com/foo/bar/pull/123">foo/bar#123</a>:', preview.description, preview)

  def test_create_issue_repo_url(self):
    self._test_create_issue('https://github.com/foo/bar')

  def test_create_issue_issues_url(self):
    self._test_create_issue('https://github.com/foo/bar/issues')

  def _create_issue(self, expected_body, obj):
    """Sets up label + create-issue POST mocks, runs create, checks the request."""
    self.mock_post.side_effect = [
      get_labels_graphql_response([]),
      requests_response({
        'id': '789999',
        'number': '123',
        'url': 'not this one',
        'html_url': 'https://github.com/foo/bar/issues/123',
      }),
    ]
    result = self.gh.create(obj)
    self.assert_post(github.REST_CREATE_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': expected_body,
        'labels': [],
      })
    return result

  def _test_create_issue(self, in_reply_to):
    obj = copy.deepcopy(ISSUE_OBJ)
    obj['inReplyTo'][0]['url'] = in_reply_to
    result = self._create_issue(ISSUE_OBJ['content'].strip(), obj)

    self.assertIsNone(result.error_plain, result)
    self.assert_equals({
      'id': '789999',
      'number': '123',
      'url': 'https://github.com/foo/bar/issues/123',
    }, result.content)

  def test_create_with_image_and_link(self):
    result = self._create_issue('[bar](http://foo/) ![](https://baz/)', {
      'displayName': 'an issue title',
      'content': """
<a href="http://foo/">bar</a>
<img src="https://baz/" />
""",
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(result.error_plain, result)

  def test_create_with_relative_image_and_link(self):
    result = self._create_issue(
      '[foo](http://site/post/foo) ![](http://site/bar/baz)', {
        'url': 'http://site/post/xyz',
        'displayName': 'an issue title',
        'content': """
<a href="foo">foo</a>
<img src="/bar/baz" />
""",
        'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
      })
    self.assertIsNone(result.error_plain, result)

  def test_create_escape_html(self):
    content = 'x &lt;data foo&gt; &amp; y'
    result = self._create_issue(content, {
      'displayName': 'an issue title',
      'content': content,
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(result.error_plain, result)

  def test_create_doesnt_escape_html_inside_code_tag(self):
    """https://github.com/indieweb/fragmention/issues/3"""
    content = 'abc <code>&lt;div style="height: 10000px"&gt;&lt;/div&gt;</code> xyz'
    result = self._create_issue(content, {
      'displayName': 'an issue title',
      'content': content,
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(result.error_plain, result)

  def test_create_blockquote(self):
    content = 'x <blockquote>y</blockquote>'
    result = self._create_issue(content, {
      'displayName': 'an issue title',
      'content': content,
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(result.error_plain, result)

  def test_preview_issue(self):
    self.mock_post.side_effect = [
      get_labels_graphql_response(['new silo']),
      requests_response('<p>rendered!</p>'),
      get_labels_graphql_response(['new silo']),
      requests_response('<p>rendered!</p>'),
    ]

    obj = copy.deepcopy(ISSUE_OBJ)
    for url in 'https://github.com/foo/bar', 'https://github.com/foo/bar/issues':
      obj['inReplyTo'][0]['url'] = url
      preview = self.gh.preview_create(obj)
      self.assertIsNone(preview.error_plain, preview)
      self.assertEqual('<b>an issue title</b><hr><p>rendered!</p>',
                       preview.content)
      self.assertIn(
        f'<span class="verb">create a new issue</span> on <a href="{url}">foo/bar</a> and attempt to add label <span class="verb">new silo</span>:',
        preview.description, preview)

  def test_preview_blockquote(self):
    content = 'x <blockquote>y</blockquote>'
    self.mock_post.side_effect = [
      get_labels_graphql_response(['new silo']),
      requests_response('<p>rendered!</p>'),
    ]

    preview = self.gh.preview_create({
      'title': 'an issue title',
      'content': content,
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(preview.error_plain, preview)
    self.assertEqual('<b>an issue title</b><hr><p>rendered!</p>',
                     preview.content)

  def test_create_issue_private_repo(self):
    """eg the w3c/AB repo is private and returns repository: None
    https://console.cloud.google.com/errors/CMbUj5KyrvH69gE
    """
    self.mock_post.side_effect = [
      graphql_response({'repository': None}),
      requests_response({'html_url': 'https://github.com/foo/bar/issues/123'}),
    ]

    result = self.gh.create({
      'displayName': 'an issue title',
      'content': 'xyz',
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(result.error_plain, result)
    self.assert_post(github.REST_CREATE_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': 'xyz',
        'labels': [],
      })

  def test_create_issue_tags_to_labels(self):
    self.mock_post.side_effect = [
      get_labels_graphql_response(['label 3', 'label_1']),
      requests_response({'html_url': 'http://done'}),
    ]

    result = self.gh.create(ISSUE_OBJ_WITH_LABELS)
    self.assertIsNone(result.error_plain, result)
    self.assert_equals({'url': 'http://done'}, result.content)
    self.assert_post(
                     github.REST_CREATE_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': ISSUE_OBJ['content'].strip(),
        'labels': ['label 3', 'label_1'],
      })

  def test_preview_issue_tags_to_labels(self):
    self.mock_post.side_effect = [
      get_labels_graphql_response(['label_1', 'label 3']),
      requests_response('<p>rendered!</p>'),
    ]

    preview = self.gh.preview_create(ISSUE_OBJ_WITH_LABELS)
    self.assertIsNone(preview.error_plain, preview)
    self.assertIn(
      '<span class="verb">create a new issue</span> on <a href="https://github.com/foo/bar/issues">foo/bar</a> and attempt to add labels <span class="verb">label 3, label_1</span>:',
      preview.description, preview)

  @skip('only needed for GraphQL, and we currently use REST to create comments')
  def test_create_comment_org_access_forbidden(self):
    msg = 'Although you appear to have the correct authorization credentials,\nthe `whatwg` organization has enabled OAuth App access restrictions, meaning that data\naccess to third-parties is limited. For more information on these restrictions, including\nhow to whitelist this app, visit\nhttps://help.github.com/articles/restricting-access-to-your-organization-s-data/\n'

    self.mock_post.return_value = requests_response({
        'errors': [
          {
            'path': ['addComment'],
            'message': msg,
            'type': 'FORBIDDEN',
            'locations': [{'column': 3, 'line': 3}],
          },
        ],
        'data': {
          'addComment': None,
        },
      })

    result = self.gh.create(COMMENT_OBJ)
    self.assertTrue(result.abort)
    self.assertEqual(msg, result.error_plain)

  def test_create_comment_without_in_reply_to(self):
    """https://github.com/snarfed/bridgy/issues/824"""
    obj = copy.deepcopy(COMMENT_OBJ)
    obj['inReplyTo'] = [{'url': 'http://foo.com/bar'}]

    for fn in (self.gh.preview_create, self.gh.create):
      result = fn(obj)
      self.assertTrue(result.abort)
      self.assertIn('You need an in-reply-to GitHub repo, issue, PR, or comment URL.',
                    result.error_plain)

  def test_create_in_reply_to_bad_fragment(self):
    obj = copy.deepcopy(COMMENT_OBJ)
    obj['inReplyTo'] = [{'url': 'https://github.com/foo/bar/pull/123#bad-456'}]

    for fn in (self.gh.preview_create, self.gh.create):
      result = fn(obj)
      self.assertTrue(result.abort)
      self.assertIn('Please remove the fragment #bad-456 from your in-reply-to URL.',
                    result.error_plain)

  def test_create_star_with_like_verb(self):
    self._test_create_star('like')

  def test_create_star_with_favorite_verb(self):
    self._test_create_star('favorite')

  def _test_create_star(self, verb):
    self.mock_post.side_effect = [
      graphql_response({'repository': {'id': 'ABC123'}}),
      graphql_response({
        'addStar': {'starrable': {'url': 'https://github.com/foo/bar'}},
      }),
    ]

    obj = copy.deepcopy(LIKE_OBJ)
    obj['verb'] = verb
    result = self.gh.create(obj)
    self.assert_equals({
      'url': 'https://github.com/foo/bar/stargazers',
    }, result.content, result)
    self.assert_graphql(github.GRAPHQL_REPO % {'owner': 'foo', 'repo': 'bar'})
    self.assert_graphql(github.GRAPHQL_ADD_STAR % {'starrable_id': 'ABC123'})

  def test_preview_star_with_like_verb(self):
    self._test_preview_star('like')

  def test_preview_star_with_favorite_verb(self):
    self._test_preview_star('favorite')

  def _test_preview_star(self, verb):
    obj = copy.deepcopy(LIKE_OBJ)
    obj['verb'] = verb
    preview = self.gh.preview_create(obj)
    self.assertEqual('<span class="verb">star</span> <a href="https://github.com/foo/bar">foo/bar</a>.', preview.description, preview)

  def test_create_reaction_issue(self):
    self.mock_post.return_value = requests_response({
        'id': 456,
        'content': '+1',
        'user': {'login': 'snarfed'},
      })

    result = self.gh.create(REACTION_OBJ_INPUT)
    self.assert_equals({
      'id': 456,
      'url': 'https://github.com/foo/bar/pull/123#+1-by-snarfed',
      'type': 'react',
    }, result.content, result)
    self.assert_post(REST_REACTIONS % ('foo', 'bar', 123),
                     json={'content': '+1'})

  def test_preview_reaction_issue(self):
    self.mock_post.return_value = ISSUE_GRAPHQL_RESPONSE

    preview = self.gh.preview_create(REACTION_OBJ_INPUT)
    self.assertEqual(u'<span class="verb">react 👍</span> to <a href="https://github.com/foo/bar/pull/123">foo/bar#123, <em>an issue title</em></a>.', preview.description)

  def test_create_reaction_issue_comment(self):
    self.mock_post.return_value = requests_response({
        'id': 'DEF456',
        'content': '+1',
        'user': {'login': 'snarfed'},
      })

    result = self.gh.create(COMMENT_REACTION_OBJ_INPUT)
    self.assert_equals({
      'id': 'DEF456',
      'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
      'type': 'react',
    }, result.content, result)
    self.assert_post(REST_COMMENT_REACTIONS % ('foo', 'bar', 'issues', 456),
                     json={'content': '+1'})

  def test_preview_reaction_issue_comment(self):
    self.mock_get.return_value = requests_response(COMMENT_REST)

    preview = self.gh.preview_create(COMMENT_REACTION_OBJ_INPUT)
    self.assertEqual(u'<span class="verb">react 👍</span> to <a href="https://github.com/foo/bar/pull/123#issuecomment-456">a comment on foo/bar#123, <em>i have something to say here</em></a>.', preview.description, preview)

  def test_create_add_label(self):
    self.mock_post.side_effect = [
      get_labels_graphql_response(['one', 'two']),
      requests_response({
        'id': 'DEF456',
        'node_id': 'MDU6TGFiZWwyMDgwNDU5NDY=',
        'name': 'an issue',
        # ¯\_(ツ)_/¯ https://developer.github.com/v3/issues/labels/#add-labels-to-an-issue
        'default': True,
      }),
    ]

    result = self.gh.create(TAG_ACTIVITY)
    self.assert_equals({
      'url': 'https://github.com/foo/bar/issues/456',
      'type': 'tag',
      'tags': ['one'],
    }, result.content, result)
    self.assert_post(REST_ISSUE_LABELS % ('foo', 'bar', 456), json=['one'])

  def test_preview_add_label(self):
    self.mock_post.return_value = get_labels_graphql_response(['one', 'two'])

    preview = self.gh.preview_create(TAG_ACTIVITY)
    self.assertIsNone(preview.error_plain, preview)
    self.assertEqual(
      'add label <span class="verb">one</span> to <a href="https://github.com/foo/bar/issues/456">foo/bar#456</a>.',
      preview.description, preview)

  def test_preview_sanitizes_comment_body_html(self):
    self.mock_get.return_value = requests_response({
      **COMMENT_REST,
      'body': 'hello <script>alert("xss")</script> world',
    })

    preview = self.gh.preview_create(COMMENT_REACTION_OBJ_INPUT)
    self.assertIn('hello world', preview.description)
    self.assertNotIn('<script>', preview.description)
    self.assertNotIn('alert', preview.description)

  def test_preview_sanitizes_issue_title_html(self):
    self.mock_post.side_effect = [
      graphql_response({
        'repository': {
          'issueOrPullRequest': {
            **ISSUE_GRAPHQL,
            'title': 'title <em>with</em> <script>alert("xss")</script> html',
          },
        },
      }),
      requests_response('<p>rendered!</p>'),
    ]

    preview = self.gh.preview_create(COMMENT_OBJ)
    self.assertIn('title with html', preview.description)
    self.assertNotIn('<script>', preview.description)
    self.assertNotIn('alert', preview.description)

  def test_preview_sanitizes_label_html(self):
    self.mock_post.return_value = get_labels_graphql_response(
      ['<em>safe</em><script>xss</script>', 'other'])

    preview = self.gh.preview_create({
      **TAG_ACTIVITY,
      'object': [{'displayName': '<em>safe</em><script>xss</script>'}],
    })
    self.assertIn('safe', preview.description)
    self.assertNotIn('<script>', preview.description)
    self.assertNotIn('alert', preview.description)
    self.assertNotIn('<em>', preview.description)

  def test_create_add_label_no_tags(self):
    activity = copy.deepcopy(TAG_ACTIVITY)
    activity['object'] = []
    result = self.gh.create(activity)
    self.assertTrue(result.abort)
    self.assertEqual('No tags found in tag post!', result.error_plain)

  def test_create_add_label_no_matching(self):
    self.mock_post.return_value = get_labels_graphql_response(['one', 'two'])

    activity = copy.deepcopy(TAG_ACTIVITY)
    activity['object'] = [{'displayName': 'three'}]
    result = self.gh.create(activity)
    self.assertTrue(result.abort)
    self.assertEqual("""No tags in [three] matched <a href="https://github.com/foo/bar/issues/456">foo/bar#456</a>'s existing labels [one, two].""", result.error_html, result)

  def test_create_preserves_linked_urls(self):
    self.assert_equals(
      'x [http://foo/bar](http://foo/bar) y',
      self.gh._content_for_create({
        'content': 'x <a href="http://foo/bar">http://foo/bar</a> y',
      }))

  def test_create_convert_profile_url_to_mention(self):
    self.mock_post.side_effect = [
      ISSUE_GRAPHQL_RESPONSE,
      requests_response('<p>rendered!</p>'),
    ]

    comment = copy.deepcopy(COMMENT_OBJ)
    comment['content'] = 'x https://github.com/foo y'
    self.gh.preview_create(comment)
    self.assert_post(REST_MARKDOWN, json={'text': 'x @foo y', 'mode': 'gfm',
                                         'context': 'foo/bar'})

  def test_create_profile_url_in_html_link(self):
    self.mock_post.side_effect = [
      ISSUE_GRAPHQL_RESPONSE,
      requests_response('<p>rendered!</p>'),
    ]

    comment = copy.deepcopy(COMMENT_OBJ)
    comment['content'] = '<a href="https://github.com/foo">text</a>'
    self.gh.preview_create(comment)
    self.assert_post(REST_MARKDOWN, json={'text': '[text](https://github.com/foo)',
                                         'mode': 'gfm', 'context': 'foo/bar'})

  def test_create_convert_profile_url_to_mention_unchanged(self):
    comment = copy.deepcopy(COMMENT_OBJ)

    for input in (
        'https://github.com.com/foo',
        'github.com/foo',
        'https://github.com/foo/bar',
        'https://github.com/foo?bar=baz',
        'https://github.com/not@user+name',
    ):
      with self.subTest(input):
        self.mock_post.reset_mock()
        self.mock_post.side_effect = [
          ISSUE_GRAPHQL_RESPONSE,
          requests_response('<p>rendered!</p>'),
        ]
        comment['content'] = input
        self.gh.preview_create(comment)
        self.assert_post(REST_MARKDOWN, json={'text': input, 'mode': 'gfm',
                                              'context': 'foo/bar'})
