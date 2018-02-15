# coding=utf-8
"""Unit tests for github.py.
"""
import copy
import json

import mox
from oauth_dropins import github as oauth_github
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import appengine_config
from granary import github
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
  'updated_at': '2012-06-10T00:39:24Z',
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
  'number': 6824,
  'url': 'https://github.com/metabase/metabase/issues/6824',
  'resourcePath': '/metabase/metabase/issues/6824',
  'repository': {
    'id': 'MDEwOlJlcG9zaXRvcnkzMDIwMzkzNQ==',
  },
  'author': {
    'avatarUrl': 'https://avatars2.githubusercontent.com/u/778068?v=4',
    'login': 'snarfed',
    'resourcePath': '/snarfed',
    'url': 'https://github.com/snarfed',
  },
  'title': 'an issue title',
  # note that newlines are \r\n in body but \n in bodyHTML and bodyText
  'body': """\
foo bar baz\r
[link](http://www.proficiencylabs.com/)\r
@user mention\r
hash: bf0076f377aeb9b1981118b6dd1e23779bd54502\r
issue: #123\r
""",
  'bodyHTML': """\
<p>foo bar baz
<a href="http://www.proficiencylabs.com/" rel="nofollow">link</a>
<a href="https://github.com/dshanske" class="user-mention">@user</a> mention
hash: <a href=\"https://github.com/pfefferle/wordpress-semantic-linkbacks/commit/bf0076f377aeb9b1981118b6dd1e23779bd54502\" class=\"commit-link\"><tt>bf0076f</tt></a>
issue: TODO
</p>""",
  'bodyText': """\
foo bar baz
link
@user mention
hash: bf0076f377aeb9b1981118b6dd1e23779bd54502
issue: #123
""",
  'state': 'OPEN',
  'closed': False,
  'locked': False,
  'closedAt': None,
  'createdAt': '2018-01-30T19:11:03Z',
  'lastEditedAt': '2018-02-01T19:11:03Z',
  'publishedAt': '2005-01-30T19:11:03Z',
}
ISSUE_REST = {
  'id': 53289448,
  'node_id': 'MDU6SXNzdWU1MzI4OTQ0OA==',
  'number': 333,
  'url': 'https://api.github.com/repos/snarfed/bridgy/issues/333',
  'html_url': 'https://github.com/snarfed/bridgy/issues/333',
  'title': 'add GitHub support',
  'user': USER_REST,
  'labels': [
    {
      'id': 281245471,
      'name': 'new silo',
      'color': 'fbca04',
      'default': False,
      'node_id': 'MDU6TGFiZWwyODEyNDU0NzE='
    }
  ],
  'state': 'open',
  'locked': False,
  'assignee': None,
  'assignees': [

  ],
  'milestone': None,
  'comments': 20,
  'created_at': '2015-01-03T01:12:37Z',
  'updated_at': '2018-02-13T18:40:35Z',
  'closed_at': None,
  'author_association': 'OWNER',
  'body': "...specifically, publish for POSSEing issues and issue comments and backfeed for issue comments. (anything else?)\n\nof all the \'add silo X\' feature requests we have, this is the one i'd use, and use a lot. i don't expect to implement it anytime soon, but i'd love to use it!\n\n(#326 - Instagram publish support for likes - is maybe the one other i'd use, but we already support IG backfeed, so it only half counts. :P)\n",
  'closed_by': None,
}
ISSUE_OBJ = {  # ActivityStreams
  'author': {
    'objectType': 'person',
    'username': 'snarfed',
    'image': {'url': 'https://avatars2.githubusercontent.com/u/778068?v=4'},
    'url': 'https://github.com/snarfed',
  },
  'title': 'an issue title',
  'content': ISSUE_GRAPHQL['body'],
  'id': tag_uri('MDU6SXNzdWUyOTI5MDI1NTI='),
  'published': '2018-01-30T19:11:03+00:00',
  'updated': '2018-02-01T19:11:03+00:00',
  'url': 'https://github.com/metabase/metabase/issues/6824',
  'to': [{'objectType':'group', 'alias':'@public'}],
  'inReplyTo': [{
    'url': 'https://github.com/foo/bar/issues',
  }],
  'state': 'OPEN',
  # 'replies': {
  #   'items': [COMMENT_OBJ],
  #   'totalItems': 1,
  # }
}
COMMENT = {  # GitHub
  'id': 'MDEwOlNQ==',
  'url': 'https://github.com/foo/bar/123#issuecomment-456',
  'author': {
    'objectType': 'person',
    'username': 'snarfed',
    'image': {'url': 'https://avatars2.githubusercontent.com/u/778068?v=4'},
    'url': 'https://github.com/snarfed',
  },
  'body': 'i have something to say here',
  'bodyHTML': 'i have something to say here',
  'createdAt': '2018-01-30T19:11:03Z',
  'lastEditedAt': '2018-02-01T19:11:03Z',
  'publishedAt': '2005-01-30T19:11:03Z',
  # TODO: public or private
}

COMMENT_OBJ = {  # ActivityStreams
  'objectType': 'comment',
  # 'author': {
  #   'objectType': 'person',
  #   'id': tag_uri('212038'),
  #   'displayName': 'Ryan Barrett',
  #   'image': {'url': 'https://graph.github.com/v2.10/212038/picture?type=large'},
  #   'url': 'https://www.github.com/212038',
  # },
  'content': 'i have something to say here',
  'id': tag_uri('MDEwOlNQ=='),
  'published': '2012-12-05T00:58:26+00:00',
  'url': 'https://github.com/foo/bar/pull/123#comment-xyz',
  'inReplyTo': [{
    'url': 'https://github.com/foo/bar/pull/123',
  }],
  # 'to': [{'objectType':'group', 'alias':'@private'}],
}
STAR_OBJ = {
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://github.com/foo/bar'},
}


class GitHubTest(testutil.HandlerTest):

  def setUp(self):
    super(GitHubTest, self).setUp()
    self.gh = github.GitHub('a-towkin')
    self.batch = []
    self.batch_responses = []

  def expect_graphql(self, response=None, **kwargs):
    return self.expect_requests_post(oauth_github.API_GRAPHQL, headers={
        'Authorization': 'bearer a-towkin',
      }, response={'data': response}, **kwargs)

  def expect_markdown_render(self, body):
    rendered = '<p>rendered!</p>'
    self.expect_requests_post(github.REST_API_MARKDOWN, headers={
      'Authorization': 'token a-towkin',
    }, response=rendered, json={
      'text': body,
      'mode': 'gfm',
      'context': 'foo/bar',
    })
    return rendered

  def test_user_to_actor_graphql(self):
    self.assert_equals(ACTOR, self.gh.user_to_actor(USER_GRAPHQL))

  def test_user_to_actor_rest(self):
    self.assert_equals(ACTOR, self.gh.user_to_actor(USER_REST))

  def test_user_to_actor_minimal(self):
    actor = self.gh.user_to_actor({'id': '123'})
    self.assert_equals(tag_uri('123'), actor['id'])

  def test_user_to_actor_empty(self):
    self.assert_equals({}, self.gh.user_to_actor({}))

  # def test_get_actor(self):
  #   self.expect_urlopen('foo', USER)
  #   self.mox.ReplayAll()
  #   self.assert_equals(ACTOR, self.gh.get_actor('foo'))

  # def test_get_actor_default(self):
  #   self.expect_urlopen('me', USER)
  #   self.mox.ReplayAll()
  #   self.assert_equals(ACTOR, self.gh.get_actor())

  # def test_get_activities_defaults(self):
  #   resp = {'data': [
  #         {'id': '1_2', 'message': 'foo'},
  #         {'id': '3_4', 'message': 'bar'},
  #         ]}
  #   self.expect_urlopen('me/home?offset=0', resp)
  #   self.mox.ReplayAll()

  #   self.assert_equals([
  #       {'id': tag_uri('2'),
  #        'object': {'content': 'foo',
  #                   'id': tag_uri('2'),
  #                   'objectType': 'note',
  #                   'url': 'https://www.github.com/1/posts/2'},
  #        'url': 'https://www.github.com/1/posts/2',
  #        'verb': 'post'},
  #       {'id': tag_uri('4'),
  #        'object': {'content': 'bar',
  #                   'id': tag_uri('4'),
  #                   'objectType': 'note',
  #                   'url': 'https://www.github.com/3/posts/4'},
  #        'url': 'https://www.github.com/3/posts/4',
  #        'verb': 'post'}],
  #     self.gh.get_activities())

  # def test_get_activities_self_empty(self):
  #   self.expect_urlopen(API_ME_POSTS, {})
  #   self.expect_urlopen(API_PHOTOS_UPLOADED, {})
  #   self.mox.ReplayAll()
  #   self.assert_equals([], self.gh.get_activities(group_id=source.SELF))

  # def test_get_activities_activity_id_not_found(self):
  #   self.expect_urlopen(API_OBJECT % ('0', '0'), {
  #     'error': {
  #       'message': '(#803) Some of the aliases you requested do not exist: 0',
  #       'type': 'OAuthException',
  #       'code': 803
  #     }
  #   })
  #   self.mox.ReplayAll()
  #   self.assert_equals([], self.gh.get_activities(activity_id='0_0'))

  # def test_get_activities_start_index_and_count(self):
  #   self.expect_urlopen('me/home?offset=3&limit=5', {})
  #   self.mox.ReplayAll()
  #   self.gh.get_activities(start_index=3, count=5)

  # def test_get_activities_start_index_count_zero(self):
  #   self.expect_urlopen('me/home?offset=0', {'data': [POST, FB_NOTE]})
  #   self.mox.ReplayAll()
  #   self.assert_equals([ACTIVITY, FB_NOTE_ACTIVITY],
  #                      self.gh.get_activities(start_index=0, count=0))

  # def test_get_activities_count_past_end(self):
  #   self.expect_urlopen('me/home?offset=0&limit=9', {'data': [POST]})
  #   self.mox.ReplayAll()
  #   self.assert_equals([ACTIVITY], self.gh.get_activities(count=9))

  # def test_get_activities_start_index_past_end(self):
  #   self.expect_urlopen('me/home?offset=0', {'data': [POST]})
  #   self.mox.ReplayAll()
  #   self.assert_equals([ACTIVITY], self.gh.get_activities(offset=9))

  # def test_get_activities_activity_id_with_user_id(self):
  #   self.expect_urlopen(API_OBJECT % ('12', '34'), {'id': '123'})
  #   self.mox.ReplayAll()
  #   obj = self.gh.get_activities(activity_id='34', user_id='12')[0]['object']

  # def test_get_activities_fetch_replies(self):
  #   post2 = copy.deepcopy(POST)
  #   post2['id'] = '222'
  #   post3 = copy.deepcopy(POST)
  #   post3['id'] = '333'
  #   self.expect_urlopen('me/home?offset=0',
  #                       {'data': [POST, post2, post3]})
  #   self.expect_urlopen(API_COMMENTS_ALL % '212038_10100176064482163,222,333',
  #     {'222': {'data': [{'id': '777', 'message': 'foo'},
  #                       {'id': '888', 'message': 'bar'}]},
  #      '333': {'data': [{'id': '999', 'message': 'baz'},
  #                       {'id': COMMENTS[0]['id'], 'message': 'omitted!'}]},
  #     })
  #   self.mox.ReplayAll()

  #   activities = self.gh.get_activities(fetch_replies=True)
  #   self.assert_equals(...)

  def test_get_activities_search_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(search_query='foo')

  def test_get_activities_activity_id_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(activity_id='foo')

  def test_get_activities_fetch_likes_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_likes='foo')

  def test_get_activities_fetch_events_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_events='foo')

  def test_get_activities_fetch_shares_not_implemented(self):
    with self.assertRaises(NotImplementedError):
      self.gh.get_activities(fetch_shares='foo')

  # def test_get_comment(self):
  #   self.expect_urlopen(API_COMMENT % '123_456', COMMENTS[0])
  #   self.mox.ReplayAll()
  #   self.assert_equals(COMMENT_OBJS[0], self.gh.get_comment('123_456'))

  # def test_comment_to_object_full(self):
  #   for cmt, obj in zip(COMMENTS, COMMENT_OBJS):
  #     self.assert_equals(obj, self.gh.comment_to_object(cmt))

  # def test_comment_to_object_minimal(self):
  #   # just test that we don't crash
  #   self.gh.comment_to_object({'id': '123_456_789', 'message': 'asdf'})

  # def test_comment_to_object_empty(self):
  #   self.assert_equals({}, self.gh.comment_to_object({}))

  def test_create_comment(self):
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
            'url': 'https://github.com/foo/bar/pull/123#comment-456',
          },
        },
      },
    })
    self.mox.ReplayAll()

    result = self.gh.create(COMMENT_OBJ)
    self.assert_equals({
      'id': '456',
      'url': 'https://github.com/foo/bar/pull/123#comment-456',
    }, result.content, result)

  def test_preview_comment(self):
    rendered = self.expect_markdown_render('i have something to say here')
    self.mox.ReplayAll()

    preview = self.gh.preview_create(COMMENT_OBJ)
    self.assertEquals(rendered, preview.content, preview)
    self.assertIn('<span class="verb">comment</span> on <a href="https://github.com/foo/bar/pull/123">foo/bar#123</a>:', preview.description, preview)

  def test_create_issue_repo_url(self):
    self._test_create_issue('https://github.com/foo/bar')

  def test_create_issue_issues_url(self):
    self._test_create_issue('https://github.com/foo/bar/issues')

  def _test_create_issue(self, in_reply_to):
    self.expect_requests_post(github.REST_API_ISSUE % ('foo', 'bar'), json={
        'title': 'an issue title',
        'body': ISSUE_GRAPHQL['body'].strip(),
      }, headers={
        'Authorization': 'token a-towkin',
      }, response={
        'id': '789999',
        'number': '123',
        'url': 'not this one',
        'html_url': 'https://github.com/foo/bar/issues/123',
      })
    self.mox.ReplayAll()

    obj = copy.deepcopy(ISSUE_OBJ)
    obj['inReplyTo'][0]['url'] = in_reply_to
    self.assert_equals({
      'id': '789999',
      'number': '123',
      'url': 'https://github.com/foo/bar/issues/123',
    }, self.gh.create(obj).content)

  def test_preview_issue(self):
    for i in range(2):
      rendered = self.expect_markdown_render(ISSUE_GRAPHQL['body'].strip())
    self.mox.ReplayAll()

    obj = copy.deepcopy(ISSUE_OBJ)
    for url in 'https://github.com/foo/bar', 'https://github.com/foo/bar/issues':
      obj['inReplyTo'][0]['url'] = url
      preview = self.gh.preview_create(obj)
      self.assertEquals('<b>an issue title</b><hr>' + rendered, preview.content)
      self.assertIn(
        '<span class="verb">create a new issue</span> on <a href="%s">foo/bar</a>:' % url,
        preview.description, preview)

  def test_create_comment_without_in_reply_to(self):
    obj = copy.deepcopy(COMMENT_OBJ)
    obj['inReplyTo'] = [{'url': 'http://foo.com/bar'}]

    for fn in (self.gh.preview_create, self.gh.create):
      result = fn(obj)
      self.assertTrue(result.abort)
      self.assertIn('You need an in-reply-to GitHub repo, issue, or PR URL.',
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
          'url': 'https://github.com/foo/bar/pull/123#comment-456',
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

