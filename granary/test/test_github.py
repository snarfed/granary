# coding=utf-8
"""Unit tests for github.py.
"""
import copy
import json

from mox3 import mox
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import appengine_config
from granary import github
from granary.github import (
  GRAPHQL_BASE,
  REACTIONS_REST_CHARS,
  REST_API_COMMENT,
  REST_API_COMMENT_REACTIONS,
  REST_API_COMMENTS,
  REST_API_ISSUE,
  REST_API_NOTIFICATIONS,
  REST_API_REACTIONS,
)
from granary import source

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
  'url': 'https://snarfed.org/',
  'urls': [
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
  'title': 'an issue title',
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
  'comments_url': 'https://api.github.com/repos/foo/bar/issues/444/comments',
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
  'title': 'a PR to merge',
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
  'published': '2012-12-05T00:58:26+00:00',
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
STAR_OBJ = {
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://github.com/foo/bar'},
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
  'Accept': 'application/vnd.github.squirrel-girl-preview+json',
}
class GitHubTest(testutil.TestCase):

  def setUp(self):
    super(GitHubTest, self).setUp()
    self.gh = github.GitHub('a-towkin')
    self.batch = []
    self.batch_responses = []

  def expect_graphql(self, response=None, **kwargs):
    return self.expect_requests_post(GRAPHQL_BASE, headers={
        'Authorization': 'bearer a-towkin',
      }, response={'data': response}, **kwargs)

  def expect_rest(self, url, response=None, **kwargs):
    kwargs.setdefault('headers', {}).update(EXPECTED_HEADERS)
    return self.expect_requests_get(url, response=response, **kwargs)

  def expect_graphql_issue(self):
    self.expect_graphql(json={
      'query': github.GRAPHQL_ISSUE_OR_PR % {
        'owner': 'foo',
        'repo': 'bar',
        'number': 123,
      },
    }, response={
      'repository': {
        'issueOrPullRequest': ISSUE_GRAPHQL,
      },
    })

  def expect_graphql_get_labels(self, labels):
    self.expect_graphql(json={
      'query': github.GRAPHQL_REPO_LABELS % {
        'owner': 'foo',
        'repo': 'bar',
      },
    }, response={
      'repository': {
        'labels': {
          'nodes': [{'name': l} for l in labels],
        },
      },
    })

  def expect_graphql_add_reaction(self):
    self.expect_graphql(json={
      'query': github.GRAPHQL_ADD_REACTION % {
        'subject_id': ISSUE_GRAPHQL['id'],
        'content': 'THUMBS_UP',
      },
    }, response={
      'addReaction': {
        'reaction': {
          'id': 'DEF456',
          'content': 'THUMBS_UP',
          'user': {
            'login': 'snarfed',
          },
        },
      },
    })

  def expect_markdown_render(self, body):
    rendered = '<p>rendered!</p>'
    self.expect_requests_post(
      github.REST_API_MARKDOWN, headers=EXPECTED_HEADERS, response=rendered, json={
        'text': body,
        'mode': 'gfm',
        'context': 'foo/bar',
      })
    return rendered

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
      self.assertEquals(expected, self.gh.base_id(url))

  def test_user_to_actor_graphql(self):
    self.assert_equals(ACTOR, self.gh.user_to_actor(USER_GRAPHQL))

  def test_user_to_actor_rest(self):
    self.assert_equals(ACTOR, self.gh.user_to_actor(USER_REST))

  def test_user_to_actor_minimal(self):
    actor = self.gh.user_to_actor({'id': '123'})
    self.assert_equals(tag_uri('123'), actor['id'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.gh.user_to_actor({}))

  def test_get_actor(self):
    self.expect_graphql(json={'query': github.GRAPHQL_USER % {'login': 'foo'}},
                        response={'user': USER_GRAPHQL})
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.gh.get_actor('foo'))

  def test_get_actor_default(self):
    self.expect_graphql(json={'query': github.GRAPHQL_VIEWER},
                        response={'viewer': USER_GRAPHQL})
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.gh.get_actor())

  def test_get_activities_defaults(self):
    notifs = [copy.deepcopy(NOTIFICATION_PULL_REST),
              copy.deepcopy(NOTIFICATION_ISSUE_REST)]
    del notifs[0]['repository']
    notifs[1].update({
      # check that we don't fetch this since we don't pass fetch_replies
      'comments_url': 'http://unused',
      'repository': {'private': False},
    })

    self.expect_rest(REST_API_NOTIFICATIONS, notifs)
    self.expect_rest(NOTIFICATION_PULL_REST['subject']['url'], PULL_REST)
    self.expect_rest(NOTIFICATION_ISSUE_REST['subject']['url'], ISSUE_REST)
    self.mox.ReplayAll()

    obj_public_repo = copy.deepcopy(ISSUE_OBJ)
    obj_public_repo['to'] = [{'objectType': 'group', 'alias': '@public'}]
    self.assert_equals([PULL_OBJ, obj_public_repo], self.gh.get_activities())

  def test_get_activities_fetch_replies(self):
    self.expect_rest(REST_API_NOTIFICATIONS, [NOTIFICATION_ISSUE_REST])
    self.expect_rest(NOTIFICATION_ISSUE_REST['subject']['url'], ISSUE_REST)
    self.expect_rest(ISSUE_REST['comments_url'], [COMMENT_REST, COMMENT_REST])
    self.mox.ReplayAll()

    self.assert_equals([ISSUE_OBJ_WITH_REPLIES],
                       self.gh.get_activities(fetch_replies=True))

  def test_get_activities_fetch_likes(self):
    self.expect_rest(REST_API_NOTIFICATIONS,
                     [NOTIFICATION_PULL_REST, NOTIFICATION_ISSUE_REST])
    self.expect_rest(NOTIFICATION_PULL_REST['subject']['url'], PULL_REST)
    self.expect_rest(REST_API_REACTIONS % ('foo', 'bar', 444), [])
    self.expect_rest(NOTIFICATION_ISSUE_REST['subject']['url'], ISSUE_REST)
    self.expect_rest(REST_API_REACTIONS % ('foo', 'bar', 333),
                     [REACTION_REST, REACTION_REST])
    self.mox.ReplayAll()

    pull_obj = copy.deepcopy(PULL_OBJ)
    pull_obj['to'] = [{'objectType': 'group', 'alias': '@private'}]
    self.assert_equals([pull_obj, ISSUE_OBJ_WITH_REACTIONS],
                       self.gh.get_activities(fetch_likes=True))

  def test_get_activities_self_empty(self):
    self.expect_rest(REST_API_NOTIFICATIONS, [])
    self.mox.ReplayAll()
    self.assert_equals([], self.gh.get_activities())

  def test_get_activities_activity_id(self):
    self.expect_rest(REST_API_ISSUE % ('foo', 'bar', 123), ISSUE_REST)
    self.mox.ReplayAll()
    self.assert_equals([ISSUE_OBJ], self.gh.get_activities(activity_id='foo:bar:123'))

  def test_get_activities_etag_and_since(self):
    self.expect_rest(REST_API_NOTIFICATIONS, [NOTIFICATION_ISSUE_REST],
                     headers={'If-Modified-Since': 'Thu, 25 Oct 2012 15:16:27 GMT'},
                     response_headers={'Last-Modified': 'Fri, 1 Jan 2099 12:00:00 GMT'})
    self.expect_rest(NOTIFICATION_ISSUE_REST['subject']['url'], ISSUE_REST)
    self.expect_rest(ISSUE_REST['comments_url'] + '?since=2012-10-25T15:16:27Z',
                     [COMMENT_REST, COMMENT_REST])
    self.mox.ReplayAll()

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

  def test_get_activities_etag_returns_304(self):
    self.expect_rest(REST_API_NOTIFICATIONS, status_code=304,
                     headers={'If-Modified-Since': 'Thu, 25 Oct 2012 15:16:27 GMT'},
                     response_headers={'Last-Modified': 'Fri, 1 Jan 2099 12:00:00 GMT'})
    self.mox.ReplayAll()

    resp = self.gh.get_activities_response(etag='Thu, 25 Oct 2012 15:16:27 GMT',
                                           fetch_replies=True)
    self.assert_equals('Fri, 1 Jan 2099 12:00:00 GMT', resp['etag'])
    self.assert_equals([], resp['items'])

  def test_get_activities_activity_id_not_found(self):
    self.expect_rest(REST_API_ISSUE % ('a', 'b', 1), {
      'message': 'Not Found',
      'documentation_url': 'https://developer.github.com/v3',
    }, status_code=404)
    self.mox.ReplayAll()
    self.assert_equals([], self.gh.get_activities(activity_id='a:b:1'))

  def test_get_activities_repo_not_found(self):
    self.expect_rest(REST_API_NOTIFICATIONS,
                     [NOTIFICATION_PULL_REST, NOTIFICATION_ISSUE_REST])
    self.expect_rest(NOTIFICATION_PULL_REST['subject']['url'], '', status_code=404)
    self.expect_rest(NOTIFICATION_ISSUE_REST['subject']['url'], ISSUE_REST)
    self.mox.ReplayAll()

    obj_public_repo = copy.deepcopy(ISSUE_OBJ)
    obj_public_repo['to'] = [{'objectType': 'group', 'alias': '@private'}]
    self.assert_equals([obj_public_repo], self.gh.get_activities())

  def test_get_activities_search_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(search_query='foo')

  def test_get_activities_fetch_events_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_events='foo')

  def test_get_activities_fetch_shares_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_shares='foo')

  def test_issue_to_object_graphql(self):
    obj = copy.deepcopy(ISSUE_OBJ)
    del obj['tags']
    self.assert_equals(obj, self.gh.issue_to_object(ISSUE_GRAPHQL))

  def test_issue_to_object_rest(self):
    self.assert_equals(ISSUE_OBJ, self.gh.issue_to_object(ISSUE_REST))

  def test_issue_to_object_pull_rest(self):
    self.assert_equals(PULL_OBJ, self.gh.issue_to_object(PULL_REST))

  def test_issue_to_object_minimal(self):
    # just test that we don't crash
    self.gh.issue_to_object({'id': '123', 'body': 'asdf'})

  def test_issue_to_object_empty(self):
    self.assert_equals({}, self.gh.issue_to_object({}))

  def test_get_comment(self):
    self.expect_rest(REST_API_COMMENT % ('foo', 'bar', 123), COMMENT_REST)
    self.mox.ReplayAll()
    self.assert_equals(COMMENT_OBJ, self.gh.get_comment('foo:bar:123'))

  def test_comment_to_object_graphql(self):
    obj = copy.deepcopy(COMMENT_OBJ)
    obj['id'] = tag_uri('foo:bar:' + COMMENT_GRAPHQL['id'])
    self.assert_equals(obj, self.gh.comment_to_object(COMMENT_GRAPHQL))

  def test_comment_to_object_rest(self):
    self.assert_equals(COMMENT_OBJ, self.gh.comment_to_object(COMMENT_REST))

  def test_comment_to_object_minimal(self):
    # just test that we don't crash
    self.gh.comment_to_object({'id': '123', 'message': 'asdf'})

  def test_comment_to_object_empty(self):
    self.assert_equals({}, self.gh.comment_to_object({}))

  def test_reaction_to_object_rest(self):
    self.assert_equals(REACTION_OBJ,
                       self.gh.reaction_to_object(REACTION_REST, ISSUE_OBJ))

  def test_create_comment(self):
    self.expect_graphql_issue()
    self.expect_graphql(json={
      'query': github.GRAPHQL_ADD_COMMENT % {
        'subject_id': ISSUE_GRAPHQL['id'],
        'body': 'i have something to say here',
      },
    }, response={
      'addComment': {
        'commentEdge': {
          'node': {
            'id': '456',
            'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
          },
        },
      },
    })
    self.mox.ReplayAll()

    result = self.gh.create(COMMENT_OBJ)
    self.assert_equals({
      'id': '456',
      'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
    }, result.content, result)

  def test_preview_comment(self):
    self.expect_graphql_issue()
    rendered = self.expect_markdown_render('i have something to say here')
    self.mox.ReplayAll()

    preview = self.gh.preview_create(COMMENT_OBJ)
    self.assertEquals(rendered, preview.content, preview)
    self.assertIn('<span class="verb">comment</span> on <a href="https://github.com/foo/bar/pull/123">foo/bar#123, <em>an issue title</em></a>:', preview.description, preview)

  def test_create_comment_escape_quotes(self):
    self.expect_graphql_issue()
    self.expect_graphql(json={
      'query': github.GRAPHQL_ADD_COMMENT % {
        'subject_id': ISSUE_GRAPHQL['id'],
        'body': r"""one ' two \" three""",
      },
    }, response={'addComment': {'commentEdge': {'node': {'foo': 'bar'}}}})
    self.mox.ReplayAll()

    obj = copy.deepcopy(COMMENT_OBJ)
    obj['content'] = """one ' two " three"""
    result = self.gh.create(obj)
    self.assert_equals({'foo': 'bar'}, result.content, result)

  def test_create_issue_repo_url(self):
    self._test_create_issue('https://github.com/foo/bar')

  def test_create_issue_issues_url(self):
    self._test_create_issue('https://github.com/foo/bar/issues')

  def _test_create_issue(self, in_reply_to):
    self.expect_graphql_get_labels([])
    self.expect_requests_post(github.REST_API_CREATE_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': ISSUE_OBJ['content'].strip(),
        'labels': [],
      }, response={
        'id': '789999',
        'number': '123',
        'url': 'not this one',
        'html_url': 'https://github.com/foo/bar/issues/123',
      }, headers=EXPECTED_HEADERS)
    self.mox.ReplayAll()

    obj = copy.deepcopy(ISSUE_OBJ)
    obj['inReplyTo'][0]['url'] = in_reply_to
    result = self.gh.create(obj)

    self.assertIsNone(result.error_plain, result)
    self.assert_equals({
      'id': '789999',
      'number': '123',
      'url': 'https://github.com/foo/bar/issues/123',
    }, result.content)

  def test_create_with_image_and_link(self):
    self.expect_graphql_get_labels([])
    self.expect_requests_post(github.REST_API_CREATE_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': '[bar](http://foo/) ![](https://baz/)',
        'labels': [],
      }, response={
        'html_url': 'https://github.com/foo/bar/issues/123',
      }, headers=EXPECTED_HEADERS)
    self.mox.ReplayAll()

    result = self.gh.create({
      'url': 'https://github.com/foo/bar/issues/333',
      'title': 'an issue title',
      'content': """
<a href="http://foo/">bar</a>
<img src="https://baz/" />
""",
      'inReplyTo': [{'url': 'https://github.com/foo/bar/issues'}],
    })
    self.assertIsNone(result.error_plain, result)
    self.assert_equals({
      'url': 'https://github.com/foo/bar/issues/123',
    }, result.content)

  def test_preview_issue(self):
    for i in range(2):
      self.expect_graphql_get_labels(['new silo'])
      rendered = self.expect_markdown_render(ISSUE_OBJ['content'].strip())
    self.mox.ReplayAll()

    obj = copy.deepcopy(ISSUE_OBJ)
    for url in 'https://github.com/foo/bar', 'https://github.com/foo/bar/issues':
      obj['inReplyTo'][0]['url'] = url
      preview = self.gh.preview_create(obj)
      self.assertIsNone(preview.error_plain, preview)
      self.assertEquals('<b>an issue title</b><hr>' + rendered, preview.content)
      self.assertIn(
        '<span class="verb">create a new issue</span> on <a href="%s">foo/bar</a> and attempt to add label <span class="verb">new silo</span>:' % url,
        preview.description, preview)

  def test_create_issue_tags_to_labels(self):
    self.expect_graphql_get_labels(['label 3', 'label_1'])
    resp = {'html_url': 'http://done'}
    self.expect_requests_post(github.REST_API_CREATE_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': ISSUE_OBJ['content'].strip(),
        'labels': ['label 3', 'label_1'],
      }, response=resp, headers=EXPECTED_HEADERS)
    self.mox.ReplayAll()

    result = self.gh.create(ISSUE_OBJ_WITH_LABELS)
    self.assertIsNone(result.error_plain, result)
    self.assert_equals({'url': 'http://done'}, result.content)

  def test_preview_issue_tags_to_labels(self):
    self.expect_graphql_get_labels(['label_1', 'label 3'])
    rendered = self.expect_markdown_render(ISSUE_OBJ_WITH_LABELS['content'].strip())
    self.mox.ReplayAll()

    preview = self.gh.preview_create(ISSUE_OBJ_WITH_LABELS)
    self.assertIsNone(preview.error_plain, preview)
    self.assertIn(
      '<span class="verb">create a new issue</span> on <a href="https://github.com/foo/bar/issues">foo/bar</a> and attempt to add labels <span class="verb">label 3, label_1</span>:',
      preview.description, preview)

  def test_create_comment_without_in_reply_to(self):
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
      self.assertIn('You need an in-reply-to GitHub repo, issue, PR, or comment URL.',
                    result.error_plain)

  def test_create_star(self):
    self.expect_graphql(json={
      'query': github.GRAPHQL_REPO % {
        'owner': 'foo',
        'repo': 'bar',
      },
    }, response={
      'repository': {
        'id': 'ABC123',
      },
    })
    self.expect_graphql(json={
      'query': github.GRAPHQL_ADD_STAR % {
        'starrable_id': 'ABC123',
      },
    }, response={
      'addStar': {
        'starrable': {
          'url': 'https://github.com/foo/bar',
        },
      },
    })
    self.mox.ReplayAll()

    result = self.gh.create(STAR_OBJ)
    self.assert_equals({
      'url': 'https://github.com/foo/bar/stargazers',
    }, result.content, result)

  def test_preview_star(self):
    preview = self.gh.preview_create(STAR_OBJ)
    self.assertEquals('<span class="verb">star</span> <a href="https://github.com/foo/bar">foo/bar</a>.', preview.description, preview)

  def test_create_reaction_issue(self):
    self.expect_graphql_issue()
    self.expect_graphql_add_reaction()
    self.mox.ReplayAll()

    result = self.gh.create(REACTION_OBJ_INPUT)
    self.assert_equals({
      'id': 'DEF456',
      'url': 'https://github.com/foo/bar/pull/123#thumbs_up-by-snarfed',
      'type': 'react',
    }, result.content, result)

  def test_preview_reaction_issue(self):
    self.expect_graphql_issue()
    self.mox.ReplayAll()

    preview = self.gh.preview_create(REACTION_OBJ_INPUT)
    self.assertEquals(u'<span class="verb">react 👍</span> to <a href="https://github.com/foo/bar/pull/123">foo/bar#123, <em>an issue title</em></a>.', preview.description)

  def test_create_reaction_comment(self):
    self.expect_graphql_issue()
    self.expect_rest(REST_API_COMMENT % ('foo', 'bar', 456), COMMENT_REST)
    self.expect_requests_post(
      REST_API_COMMENT_REACTIONS % ('foo', 'bar', 456), headers=EXPECTED_HEADERS,
      json={
        'content': '+1',
      }, response={
        'id': 'DEF456',
        'content': '+1',
        'user': {'login': 'snarfed'},
      })
    self.mox.ReplayAll()

    result = self.gh.create(COMMENT_REACTION_OBJ_INPUT)
    self.assert_equals({
      'id': 'DEF456',
      'url': 'https://github.com/foo/bar/pull/123#issuecomment-456',
      'type': 'react',
    }, result.content, result)

  def test_preview_reaction_comment(self):
    self.expect_graphql_issue()
    self.expect_rest(REST_API_COMMENT % ('foo', 'bar', 456), COMMENT_REST)
    self.mox.ReplayAll()

    preview = self.gh.preview_create(COMMENT_REACTION_OBJ_INPUT)
    self.assertEquals(u'<span class="verb">react 👍</span> to <a href="https://github.com/foo/bar/pull/123#issuecomment-456">a comment on foo/bar#123, <em>i have something to say here</em></a>.', preview.description)
