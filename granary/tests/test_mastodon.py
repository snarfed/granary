"""Unit tests for mastodon.py."""
import copy
from unittest.mock import patch

from webutil import testutil, util
from webutil.testutil import requests_response
from webutil.util import HTTP_TIMEOUT, json_dumps, json_loads
from requests import HTTPError

from .. import mastodon
from .. import source
from ..mastodon import (
  API_ACCOUNT,
  API_ACCOUNT_STATUSES,
  API_BLOCKS,
  API_CONTEXT,
  API_FAVORITE,
  API_FAVORITED_BY,
  API_FOLLOW,
  API_MEDIA,
  API_NOTIFICATIONS,
  API_REBLOG,
  API_REBLOGGED_BY,
  API_SEARCH,
  API_STATUS,
  API_STATUSES,
  API_TIMELINE,
  API_VERIFY_CREDENTIALS,
)

def tag_uri(name):
  return util.tag_uri('foo.com', name)

INSTANCE = 'http://foo.com'

# headers that util.requests_* add to every Mastodon API call
AUTH_HEADERS = {'Authorization': 'Bearer towkin', 'User-Agent': util.user_agent}

ACCOUNT = {  # Mastodon; https://docs.joinmastodon.org/api/entities/#account
  'id': '23507',
  'username': 'snarfed',
  'acct': 'snarfed',  # fully qualified if on a different instance
  'url': 'http://foo.com/@snarfed',
  'display_name': 'Ryan Barrett',
  'avatar': 'http://foo.com/snarfed.png',
  'created_at': '2017-04-19T20:38:19.704Z',
  'note': 'my note',
  'followers_count': 456,
  'following_count': 123,
  'fields': [{
    'name': 'foo',
    'value': '<a href="https://snarfed.org" rel="me nofollow noopener" target="_blank"><span class="invisible">https://</span><span class="">snarfed.org</span></a>',
    'verified_at': '2019-04-03T17:32:24.467+00:00',
  }],
}
ACTOR = {  # ActivityStreams
  'objectType': 'person',
  'displayName': 'Ryan Barrett',
  'username': 'snarfed',
  'id': tag_uri('snarfed'),
  'numeric_id': '23507',
  'url': 'http://foo.com/@snarfed',
  'urls': [
    {'value': 'http://foo.com/@snarfed'},
    {'value': 'https://snarfed.org'},
  ],
  'image': {'url': 'http://foo.com/snarfed.png'},
  'description': 'my note',
  'published': '2017-04-19T20:38:19.704Z',
  'followers': {'totalItems': 456},
  'following': {'totalItems': 123},
}
ACCOUNT_REMOTE = {
  'id': '999',
  'username': 'bob',
  'acct': 'bob@other.net',
  'url': 'http://other.net/@bob',
  'uri': 'http://other.net/users/bob',
}
ACTOR_REMOTE = {
  'objectType': 'person',
  'id': 'http://other.net/users/bob',
  'numeric_id': '999',
  'username': 'bob',
  'displayName': 'bob@other.net',
  'url': 'http://other.net/@bob',
  'urls': [{'value': 'http://other.net/@bob'}],
}
STATUS = {  # Mastodon; https://docs.joinmastodon.org/api/entities/#status
  'id': '123',
  'url': 'http://foo.com/@snarfed/123',
  'uri': 'http://foo.com/users/snarfed/statuses/123',
  'account': ACCOUNT,
  'content': '<p>foo ☕ <a href="...">bar</a></p>',
  'created_at': '2019-07-29T18:35:53.446Z',
  'visibility': 'public',
  'mentions': [{
    'username': 'alice',
    'url': 'https://other/@alice',
    'id': '11018',
    'acct': 'alice@other',
  }],
  'tags': [{
    'url': 'http://foo.com/tags/indieweb',
    'name': 'indieweb'
  }],
  'application': {
    'name': 'my app',
    'website': 'http://app',
  },
  'card': {
     'url': 'https://an/article',
     'title': 'my title',
     'description': 'my description',
     'image': 'https://an/image',
  },
}
OBJECT = {  # ActivityStreams
  'objectType': 'note',
  'author': ACTOR,
  'content': STATUS['content'],
  'id': STATUS['uri'],
  'numeric_id': STATUS['id'],
  'published': STATUS['created_at'],
  'url': STATUS['url'],
  'to': [{'objectType': 'group', 'alias': '@public'}],
  'tags': [{
    'objectType': 'person',
    'id': 'https://other/users/alice',
    'url': 'https://other/@alice',
    'displayName': 'alice',
  }, {
    'objectType': 'hashtag',
    'url': 'http://foo.com/tags/indieweb',
    'displayName': 'indieweb',
  }, {
    'objectType': 'article',
    'url': 'https://an/article',
    'displayName': 'my title',
    'content': 'my description',
    'image': {'url': 'https://an/image'},
  }],
}
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': STATUS['created_at'],
  'id': STATUS['uri'],
  'numeric_id': STATUS['id'],
  'url': STATUS['url'],
  'actor': ACTOR,
  'object': OBJECT,
  'generator': {'displayName': 'my app', 'url': 'http://app'},
}
STATUS_REMOTE = copy.deepcopy(STATUS)
STATUS_REMOTE.update({
  'id': '999',
  'account': ACCOUNT_REMOTE,
  'url': 'http://other.net/@bob/888',
  'uri': 'http://other.net/users/bob/statuses/888',
})
OBJECT_REMOTE = copy.deepcopy(OBJECT)
OBJECT_REMOTE.update({
  'id': STATUS_REMOTE['uri'],
  'numeric_id': STATUS_REMOTE['id'],
  'author': ACTOR_REMOTE,
  'url': 'http://other.net/@bob/888',
})
REPLY_STATUS = copy.deepcopy(STATUS)  # Mastodon
REPLY_STATUS.update({
  'in_reply_to_id': '456',
  'in_reply_to_account_id': '11018',
})
REPLY_OBJECT = copy.deepcopy(OBJECT)  # ActivityStreams
REPLY_OBJECT['inReplyTo'] = [{
  'url': 'http://foo.com/web/statuses/456',
  'id': tag_uri('456'),
}]
REPLY_ACTIVITY = copy.deepcopy(ACTIVITY)  # ActivityStreams
REPLY_ACTIVITY.update({
  'object': REPLY_OBJECT,
  'context': {'inReplyTo': REPLY_OBJECT['inReplyTo']},
})
REBLOG_STATUS = {  # Mastodon
  'id': '789',
  'url': 'http://other.net/@bob/789',
  'uri': 'http://other.net/users/bob/statuses/789',
  'account': ACCOUNT_REMOTE,
  'reblog': STATUS,
}
SHARE_ACTIVITY = {  # ActivityStreams
  'objectType': 'activity',
  'verb': 'share',
  'id': REBLOG_STATUS['uri'],
  'numeric_id': REBLOG_STATUS['id'],
  'url': 'http://other.net/@bob/789',
  'object': OBJECT,
  'actor': ACTOR_REMOTE,
}
MEDIA_STATUS = copy.deepcopy(STATUS)  # Mastodon
MEDIA_STATUS['media_attachments'] = [{
  'id': '222',
  'type': 'image',
  'url': 'http://foo.com/image.jpg',
  'description': 'a fun image',
  'meta': {
     'small': {
        'height': 202,
        'size': '400x202',
        'width': 400,
        'aspect': 1.98019801980198
     },
     'original': {
        'height': 536,
        'aspect': 1.97761194029851,
        'size': '1060x536',
        'width': 1060
     }
  },
}, {
  'id': '444',
  'type': 'gifv',
  'url': 'http://use/remote/url/instead',
  'preview_url': 'http://foo.com/poster.png',
  'remote_url': 'http://foo.com/video.mp4',
  'description': 'a fun video',
  'meta': {
     'width': 640,
     'height': 480,
     'small': {
        'width': 400,
        'height': 300,
        'aspect': 1.33333333333333,
        'size': '400x300'
     },
     'aspect': 1.33333333333333,
     'size': '640x480',
     'duration': 6.13,
     'fps': 30,
     'original': {
        'frame_rate': '30/1',
        'duration': 6.134,
        'bitrate': 166544,
        'width': 640,
        'height': 480
     },
     'length': '0:00:06.13'
  },
}]
MEDIA_OBJECT = copy.deepcopy(OBJECT)  # ActivityStreams
MEDIA_OBJECT.update({
  'image': {
    'url': 'http://foo.com/image.jpg',
    'displayName': 'a fun image',
  },
  'attachments': [{
    'objectType': 'image',
    'numeric_id': '222',
    'displayName': 'a fun image',
    'image': {
      'url': 'http://foo.com/image.jpg',
      'displayName': 'a fun image',
    },
  }, {
    'objectType': 'video',
    'numeric_id': '444',
    'displayName': 'a fun video',
    'stream': {'url': 'http://foo.com/video.mp4'},
    'image': {'url': 'http://foo.com/poster.png'},
  }],
})
MEDIA_ACTIVITY = copy.deepcopy(ACTIVITY)  # ActivityStreams
MEDIA_ACTIVITY['object'] = MEDIA_OBJECT
LIKE = {  # ActivityStreams
  'id': tag_uri('123_favorited_by_23507'),
  'url': OBJECT['url'] + '#favorited-by-23507',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': OBJECT['url']},
  'author': ACTOR,
}
LIKE_REMOTE = copy.deepcopy(LIKE)
LIKE_REMOTE['object']['url'] = OBJECT_REMOTE['url']
SHARE = {  # ActivityStreams
  'id': tag_uri('123_reblogged_by_23507'),
  'url': 'http://foo.com/@snarfed/123#reblogged-by-23507',
  'objectType': 'activity',
  'verb': 'share',
  'object': {'url': 'http://foo.com/@snarfed/123'},
  'author': ACTOR,
}
SHARE_REMOTE = copy.deepcopy(SHARE)
SHARE_REMOTE['object']['url'] = OBJECT_REMOTE['url']
SHARE_BY_REMOTE = copy.deepcopy(SHARE)
SHARE_BY_REMOTE.update({
  'id': tag_uri('123_reblogged_by_999'),
  'url': 'http://foo.com/@snarfed/123#reblogged-by-999',
  'author': ACTOR_REMOTE,
})
MENTION_NOTIFICATION = {  # Mastodon
  'id': '555',
  'type': 'mention',
  'account': ACCOUNT_REMOTE,
  'status': MEDIA_STATUS,
  'created_at': '2019-10-15T00:23:37.969Z',
}
STATUS_WITH_COUNTS = copy.deepcopy(STATUS)
STATUS_WITH_COUNTS.update({  # Mastodon
  'replies_count': 1,
  'favourites_count': 2,
  'reblogs_count': 3,
})
STATUS_WITH_EMOJI = copy.deepcopy(STATUS)
STATUS_WITH_EMOJI.update({  # Mastodon
  'content': '<p>foo ☕ <br>:one: bar</p> :two:',
  'emojis': [{
    'shortcode': 'one',
    'visible_in_picker': True,
    'url': 'http://foo.com/one',
    'static_url': '...'
  }, {
    'shortcode': 'two',
    'url': 'http://foo.com/two',
  }],
})
OBJECT_WITH_EMOJI = copy.deepcopy(OBJECT)
OBJECT_WITH_EMOJI['content'] = """\
<p>foo ☕ <br><img alt="one" src="http://foo.com/one" style="height: 1em"> \
bar</p> <img alt="two" src="http://foo.com/two" style="height: 1em">"""


class MastodonTest(testutil.BaseTestCase):

  def setUp(self):
    super(MastodonTest, self).setUp()
    self.mastodon = mastodon.Mastodon(INSTANCE, user_id=ACCOUNT['id'],
                                      access_token='towkin')

    self.mock_get = self.start_patch('get')
    self.mock_post = self.start_patch('post')

  def start_patch(self, method):
    # TODO: replace with self.enterContext(patch.object(...)) once our Python
    # floor is >= 3.11.
    patcher = patch.object(util.session, method)
    mock = patcher.start()
    self.addCleanup(patcher.stop)
    return mock

  def assert_call(self, mock, path, **kwargs):
    """Asserts a Mastodon API call to ``INSTANCE + path``.

    Checks the bearer token, User-Agent, timeout, and stream that
    :func:`util.requests_*` add to every call. Extra kwargs (eg ``params``,
    ``json``, ``data``) are checked too, if passed. Searches all calls made
    to ``mock``, not just the most recent.
    """
    url = INSTANCE + path
    for c in mock.call_args_list:
      if c.args[0] != url:
        continue
      self.assertEqual(AUTH_HEADERS, c.kwargs['headers'])
      self.assertEqual(HTTP_TIMEOUT, c.kwargs['timeout'])
      self.assertTrue(c.kwargs['stream'])
      for key, val in kwargs.items():
        if val:
          self.assert_equals(val, c.kwargs[key], key)
      return
    self.fail(f'No call to {url} in {[c.args[0] for c in mock.call_args_list]}')

  def assert_get(self, path, **kwargs):
    self.assert_call(self.mock_get, path, **kwargs)

  def assert_post(self, path, **kwargs):
    self.assert_call(self.mock_post, path, **kwargs)

  def test_constructor_look_up_user_id(self):
    self.mock_get.return_value = requests_response(ACCOUNT)
    m = mastodon.Mastodon(INSTANCE, access_token='towkin')
    self.assertEqual(ACCOUNT['id'], m.user_id)
    self.assert_get(API_VERIFY_CREDENTIALS)

  def test_get_activities_defaults(self):
    self.mock_get.return_value = requests_response([
      STATUS,
      REPLY_STATUS,
      MEDIA_STATUS,
    ])
    self.assert_equals([ACTIVITY, REPLY_ACTIVITY, MEDIA_ACTIVITY],
                       self.mastodon.get_activities())
    self.assert_get(API_TIMELINE)

  def test_get_activities_group_id_friends(self):
    self.mock_get.return_value = requests_response([
      STATUS,
      REPLY_STATUS,
      MEDIA_STATUS,
    ])
    self.assert_equals([ACTIVITY, REPLY_ACTIVITY, MEDIA_ACTIVITY],
                       self.mastodon.get_activities(group_id=source.FRIENDS))
    self.assert_get(API_TIMELINE)

  def test_get_activities_include_shares_false(self):
    self.mock_get.return_value = requests_response([
      STATUS,
      REBLOG_STATUS,
      REPLY_STATUS,
    ])
    self.assert_equals([ACTIVITY, REPLY_ACTIVITY],
                       self.mastodon.get_activities(include_shares=False))
    self.assert_get(API_TIMELINE)

  def test_get_activities_fetch_replies(self):
    self.mock_get.side_effect = [
      requests_response([STATUS_WITH_COUNTS]),
      requests_response({
        'ancestors': [],
        'descendants': [REPLY_STATUS, REPLY_STATUS],
      }),
    ]

    with_replies = copy.deepcopy(ACTIVITY)
    with_replies['object']['replies'] = {
        'items': [REPLY_ACTIVITY, REPLY_ACTIVITY],
    }
    cache = {}
    self.assert_equals([with_replies], self.mastodon.get_activities(
      fetch_replies=True, cache=cache))
    self.assert_equals(1, cache['AMRE 123'])
    self.assert_get(API_TIMELINE)
    self.assert_get(API_CONTEXT % STATUS['id'])

  def test_get_activities_fetch_likes(self):
    self.mock_get.side_effect = [
      requests_response([STATUS_WITH_COUNTS]),
      requests_response([ACCOUNT, ACCOUNT]),
    ]

    with_likes = copy.deepcopy(ACTIVITY)
    with_likes['object']['tags'].extend([LIKE, LIKE])
    cache = {}
    self.assert_equals([with_likes], self.mastodon.get_activities(
      fetch_likes=True, cache=cache))
    self.assert_equals(2, cache['AMF 123'])
    self.assert_get(API_TIMELINE)
    self.assert_get(API_FAVORITED_BY % STATUS['id'])

  def test_get_activities_fetch_shares(self):
    self.mock_get.side_effect = [
      requests_response([STATUS_WITH_COUNTS]),
      requests_response([ACCOUNT, ACCOUNT_REMOTE]),
    ]

    with_shares = copy.deepcopy(ACTIVITY)
    with_shares['object']['tags'].extend([SHARE, SHARE_BY_REMOTE])
    cache = {}
    self.assert_equals([with_shares], self.mastodon.get_activities(
      fetch_shares=True, cache=cache))
    self.assert_equals(3, cache['AMRB 123'])
    self.assert_get(API_TIMELINE)
    self.assert_get(API_REBLOGGED_BY % STATUS['id'])

  def test_get_activities_fetch_replies_likes_shares_counts_zero(self):
    self.mock_get.return_value = requests_response([STATUS])
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(
      fetch_replies=True, fetch_likes=True, fetch_shares=True))
    self.assert_get(API_TIMELINE)

  def test_get_activities_fetch_mentions(self):
    self.mock_get.side_effect = [
      requests_response([STATUS]),
      requests_response([MENTION_NOTIFICATION]),
    ]
    self.assert_equals([ACTIVITY, MEDIA_ACTIVITY],
                       self.mastodon.get_activities(fetch_mentions=True))
    self.assert_get(API_TIMELINE)
    self.assert_get(API_NOTIFICATIONS,
                    params={'exclude_types[]': ['follow', 'favourite', 'reblog']})

  def test_get_activities_fetch_mentions_null_status(self):
    """https://console.cloud.google.com/errors/CNvulo670obn4AE"""
    notif = copy.deepcopy(MENTION_NOTIFICATION)
    notif['status'] = None
    self.mock_get.side_effect = [
      requests_response([]),
      requests_response([notif]),
    ]
    self.assert_equals([], self.mastodon.get_activities(fetch_mentions=True))

  def test_get_activities_activity_id(self):
    self.mock_get.return_value = requests_response(STATUS)
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(activity_id=123))
    self.assert_get(API_STATUS % '123')

  def test_get_activities_self_user_id(self):
    self.mock_get.return_value = requests_response([STATUS])
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(
      group_id=source.SELF, user_id=456))
    self.assert_get(API_ACCOUNT_STATUSES % '456')

  def test_get_activities_self_default_user(self):
    self.mock_get.return_value = requests_response([STATUS])
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(group_id=source.SELF))
    self.assert_get(API_ACCOUNT_STATUSES % ACCOUNT['id'])

  def test_get_activities_search_without_count(self):
    self.mock_get.return_value = requests_response({'statuses': [STATUS, MEDIA_STATUS]})
    self.assert_equals([ACTIVITY, MEDIA_ACTIVITY], self.mastodon.get_activities(
        group_id=source.SEARCH, search_query='indieweb'))
    self.assert_get(API_SEARCH, params={
      'q': 'indieweb',
      'resolve': True,
      'offset': 0,
    })

  def test_get_activities_search_with_count(self):
    self.mock_get.return_value = requests_response({'statuses': [STATUS, MEDIA_STATUS]})
    self.assert_equals([ACTIVITY, MEDIA_ACTIVITY], self.mastodon.get_activities(
        group_id=source.SEARCH, search_query='indieweb', count=123))
    self.assert_get(API_SEARCH, params={
      'q': 'indieweb',
      'resolve': True,
      'offset': 0,
      'limit': 123,
    })

  def test_get_activities_search_no_query(self):
    with self.assertRaises(ValueError):
      self.mastodon.get_activities(group_id=source.SEARCH, search_query=None)

  def test_get_activities_group_friends_user_id(self):
    with self.assertRaises(ValueError):
      self.mastodon.get_activities(group_id=source.FRIENDS, user_id='345')

  def test_get_activities_start_index_count(self):
    self.mock_get.return_value = requests_response([STATUS, REPLY_STATUS])
    self.assert_equals([REPLY_ACTIVITY],
                       self.mastodon.get_activities(start_index=1, count=1))
    self.assert_get(API_TIMELINE, params={'limit': 2})

  def test_get_activities_start_index_count_zero(self):
    self.mock_get.return_value = requests_response([STATUS])
    self.assert_equals([ACTIVITY],
                       self.mastodon.get_activities(start_index=0, count=0))
    self.assert_get(API_TIMELINE)

  def test_get_activities_count_past_end(self):
    self.mock_get.return_value = requests_response([STATUS])
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(count=9))
    self.assert_get(API_TIMELINE, params={'limit': 9})

  def test_get_activities_start_index_past_end(self):
    self.mock_get.return_value = requests_response([STATUS])
    self.assert_equals([], self.mastodon.get_activities(start_index=9))
    self.assert_get(API_TIMELINE)

  def test_get_activities_fetch_cache(self):
    statuses = [copy.deepcopy(STATUS), copy.deepcopy(STATUS)]
    statuses[0]['id'] += '_a'
    statuses[1]['id'] += '_b'

    responses = []
    for count in (1, 2):
      for s in statuses:
        s['replies_count'] = s['reblogs_count'] = s['favourites_count'] = count
      # first fetch this iteration fetches details (counts changed)
      responses.append(requests_response(copy.deepcopy(statuses)))
      for s in statuses:
        responses.append(requests_response({}))   # context
        responses.append(requests_response({}))   # favorited by
        responses.append(requests_response([]))   # reblogged by
      # shouldn't fetch details this time because counts haven't changed
      responses.append(requests_response(copy.deepcopy(statuses)))
    self.mock_get.side_effect = responses

    cache = {}
    for _ in range(4):
      self.mastodon.get_activities(fetch_replies=True, fetch_shares=True,
                                   fetch_likes=True, cache=cache)

  def test_get_activities_returns_non_json(self):
    self.mock_get.return_value = requests_response('<html>', content_type='text/html')
    with self.assertRaises(HTTPError) as e:
      self.mastodon.get_activities()
    self.assert_equals(502, e.exception.response.status_code)

  def test_get_activities_json_truncated(self):
    self.mock_get.return_value = requests_response(
      '{"foo": "bar", "oops', content_type='application/json')
    with self.assertRaises(HTTPError) as e:
      self.mastodon.get_activities()
    self.assert_equals(502, e.exception.response.status_code)
    self.assertIn('Unterminated string', str(e.exception))

  def test_get_activities_returns_content_type_text(self):
    """Truth Social does this.

    https://console.cloud.google.com/errors/detail/CMqz0Me7nebCsAE;time=P30D?project=brid-gy
    """
    self.mock_get.return_value = requests_response(
      [STATUS, REPLY_STATUS, MEDIA_STATUS], content_type='text/plain;charset=UTF-8')
    self.assert_equals([ACTIVITY, REPLY_ACTIVITY, MEDIA_ACTIVITY],
                        self.mastodon.get_activities())

  def test_get_activities_200_error(self):
    """Sharkey returns errors as HTTP 200 with `error` field in JSON body.

    Example:
      {
        "error": {
          "message": "Authentication failed. Please ensure your token is correct.",
          "code": "AUTHENTICATION_FAILED",
          "id": "b0a7f5f8-dc2f-4171-b91f-de88ad238e14",
          "kind": "client"
        }
      }
    """
    self.mock_get.return_value = requests_response({
        'error': {
          'message': 'Authentication failed. Please ensure your token is correct.',
          'code': 'AUTHENTICATION_FAILED',
          'id': 'b0a7f5f8-dc2f-4171-b91f-de88ad238e14',
          'kind': 'client',
        }
    })

    with self.assertRaises(HTTPError) as e:
      self.mastodon.get_activities()
    self.assert_equals(401, e.exception.response.status_code)
    self.assertIn('AUTHENTICATION_FAILED', str(e.exception))

    with self.assertRaises(ValueError):
      self.mastodon.get_activities(group_id=source.SEARCH, search_query=None)

  def test_get_actor(self):
    self.mock_get.return_value = requests_response(ACCOUNT)
    self.assert_equals(ACTOR, self.mastodon.get_actor(1))
    self.assert_get(API_ACCOUNT % 1)

  def test_get_actor_current_user(self):
    self.mock_get.return_value = requests_response(ACCOUNT_REMOTE)
    self.assert_equals(ACTOR_REMOTE, self.mastodon.get_actor())
    self.assert_get(API_ACCOUNT % ACCOUNT['id'])

  def test_get_comment(self):
    self.mock_get.return_value = requests_response(STATUS)
    self.assert_equals(OBJECT, self.mastodon.get_comment(1))
    self.assert_get(API_STATUS % 1)

  def test_to_as1_actor(self):
    self.assert_equals(ACTOR, self.mastodon.to_as1_actor(ACCOUNT))

  def test_to_as1_actor_remote(self):
    self.assert_equals(ACTOR_REMOTE, self.mastodon.to_as1_actor(ACCOUNT_REMOTE))

  def test_to_as1_actor_username_acct_conflict(self):
    with self.assertRaises(ValueError):
      self.mastodon.to_as1_actor({
        'username': 'alice',
        'acct': 'eve@xyz',
      })

  def test_actor_id(self):
    user = {
      'id': 'aye dee',
      'uri': 'yew arr aye',
      'url': 'yew arr ell',
    }
    self.assertEqual('yew arr aye', self.mastodon.actor_id(user))

    del user['uri']
    self.assertIsNone(self.mastodon.actor_id(user))

  def test_make_like(self):
    self.assert_equals(LIKE, self.mastodon._make_like(STATUS, ACCOUNT))

  def test_status_to_as1_object(self):
    self.assert_equals(OBJECT, self.mastodon.status_to_as1_object(STATUS))

  def test_status_to_as1_object_custom_emoji(self):
    self.assert_equals(OBJECT_WITH_EMOJI,
                       self.mastodon.status_to_as1_object(STATUS_WITH_EMOJI))

  def test_status_to_as1_object_mention_with_null_url(self):
    obj = self.mastodon.status_to_as1_object({
      **STATUS,
      'mentions': [{
        'username': 'bob',
        'url': None,
        'id': '22222',
        'acct': 'bob@example.com',
      }],
    })
    self.assertEqual({
      'objectType': 'person',
      'id': tag_uri('22222'),
      'displayName': 'bob',
    }, obj['tags'][0])

  def test_status_to_as1_activity(self):
    self.assert_equals(ACTIVITY, self.mastodon.status_to_as1_activity(STATUS))

  def test_reply_status_to_as1_object(self):
    self.assert_equals(REPLY_OBJECT, self.mastodon.status_to_as1_object(REPLY_STATUS))

  def test_reply_status_to_as1_activity(self):
    self.assert_equals(REPLY_ACTIVITY, self.mastodon.status_to_as1_activity(REPLY_STATUS))

  def test_reblog_status_to_as1_activity(self):
    self.assert_equals(SHARE_ACTIVITY, self.mastodon.status_to_as1_activity(REBLOG_STATUS))

  def test_status_with_media_to_object(self):
    self.assert_equals(MEDIA_OBJECT, self.mastodon.status_to_as1_object(MEDIA_STATUS))

  def test_preview_status(self):
    self.mastodon.TRUNCATE_TEXT_LENGTH = 20
    self.mastodon.TRUNCATE_URL_LENGTH = 5

    for content, expected in (
        ('foo ☕ bar', 'foo ☕ bar'),
        ('too long, will be ellipsized', 'too long, will be…'),
        ('<p>foo ☕ <a>bar</a></p>', 'foo ☕ bar'),
        ('#Asdf ☕ bar', '<a href="http://foo.com/tags/Asdf">#Asdf</a> ☕ bar'),
        ('foo ☕ @alice', 'foo ☕ <a href="http://foo.com/@alice">@alice</a>'),
        ('foo @alice@x.com ☕', 'foo <a href="https://x.com/@alice">@alice</a> ☕'),
        ('link asdf.com', 'link <a href="http://asdf.com">asdf.com</a>'),
      ):
      obj = copy.deepcopy(OBJECT)
      obj['content'] = content
      got = self.mastodon.preview_create(obj)
      self.assertEqual('<span class="verb">toot</span>:', got.description)
      self.assertEqual(expected, got.content)

  def test_create_status(self):
    self.mock_post.return_value = requests_response(STATUS)
    result = self.mastodon.create(OBJECT)

    self.assert_equals(STATUS, result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)
    self.assert_post(API_STATUSES, json={'status': 'foo ☕ bar'})

  def test_create_bookmark(self):
    self.mock_post.return_value = requests_response(STATUS)
    result = self.mastodon.create({
      'objectType': 'activity',
      'verb': 'post',
      'content': 'foo ☕ bar',
      'object': {
        'objectType': 'bookmark',
        'targetUrl': 'https://example.com/foo',
      }
    })

    self.assert_equals(STATUS, result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)
    self.assert_post(API_STATUSES, json={'status': 'foo ☕ bar'})

  def test_create_reply(self):
    self.mock_post.return_value = requests_response(STATUS)
    result = self.mastodon.create(REPLY_OBJECT)
    self.assert_equals(STATUS, result.content, result)
    self.assert_post(API_STATUSES, json={
      'status': 'foo ☕ bar',
      'in_reply_to_id': '456',
    })

  def test_preview_reply(self):
    preview = self.mastodon.preview_create(REPLY_OBJECT)
    self.assertIn('<span class="verb">reply</span> to <a href="http://foo.com/web/statuses/456">this toot</a>: ', preview.description)
    self.assert_equals('foo ☕ bar', preview.content)

  def test_base_object_empty(self):
    self.assert_equals({}, self.mastodon.base_object({'inReplyTo': []}))
    self.assert_equals({}, self.mastodon.base_object({'object': {}}))
    self.assert_equals({}, self.mastodon.base_object({'target': []}))

  def test_base_object_local(self):
    self.assert_equals({
      'id': '123',
      'url': 'http://foo.com/@xyz/123',
    }, self.mastodon.base_object({
      'object': {'url': 'http://foo.com/@xyz/123'},
    }))

  def test_base_object_no_url(self):
    self.assert_equals({}, self.mastodon.base_object({
      'object': {'foo': 'bar'},
    }))

  def test_base_object_bookmark(self):
    self.assert_equals({}, self.mastodon.base_object({
      'object': {
        'objectType': 'bookmark',
        'targetUrl': 'http://bar.com/baz',
      },
    }))

  def test_base_object_two_remote(self):
    bad = {'url': 'http://bad/456'}
    remote = {'url': STATUS_REMOTE['uri']}

    self.mock_get.side_effect = [
      requests_response('', status=404),
      requests_response({'statuses': [STATUS_REMOTE]}),
    ]

    expected = copy.deepcopy(OBJECT_REMOTE)
    expected['id'] = STATUS_REMOTE['id']
    self.assert_equals(expected, self.mastodon.base_object({
      'inReplyTo': [bad, remote],
    }))
    self.assert_equals(
      [{'q': 'http://bad/456', 'resolve': True},
       {'q': STATUS_REMOTE['uri'], 'resolve': True}],
      [c.kwargs['params'] for c in self.mock_get.call_args_list])

  def test_base_object_account(self):
    self.mock_get.return_value = requests_response({'accounts': [ACCOUNT_REMOTE]})

    expected = {
      **ACTOR_REMOTE,
      'id': ACCOUNT_REMOTE['id'],
    }
    self.assert_equals(expected, self.mastodon.base_object({
      'object': ACCOUNT_REMOTE['uri'],
    }))
    self.assert_get(API_SEARCH,
                     params={'q': ACCOUNT_REMOTE['uri'], 'resolve': True})

  def test_embed_post(self):
    embed = self.mastodon.embed_post({'url': 'http://foo.com/bar'})
    self.assertIn('<script src="http://foo.com/embed.js"', embed)
    self.assertIn('<iframe src="http://foo.com/bar/embed"', embed)

  def test_status_url(self):
    self.assertEqual('http://foo.com/web/statuses/456',
                     self.mastodon.status_url(456))

  def test_create_reply_remote(self):
    url = STATUS_REMOTE['url']
    self.mock_get.return_value = requests_response({'statuses': [STATUS_REMOTE]})
    self.mock_post.return_value = requests_response(STATUS)

    got = self.mastodon.create({
      'content': 'foo ☕ bar',
      'inReplyTo': [{'url': url}],
    })
    self.assert_equals(STATUS, got.content, got)
    self.assert_get(API_SEARCH, params={'q': url, 'resolve': True})
    self.assert_post(API_STATUSES, json={
      'status': 'foo ☕ bar',
      'in_reply_to_id': STATUS_REMOTE['id'],
    })

  def test_preview_reply_remote(self):
    url = STATUS_REMOTE['url']
    self.mock_get.return_value = requests_response({'statuses': [STATUS_REMOTE]})

    preview = self.mastodon.preview_create({
      'content': 'foo ☕ bar',
      'inReplyTo': [{'url': url}],
    })
    self.assertIn(
      f'<span class="verb">reply</span> to <a href="{url}">this toot</a>: ',
      preview.description)
    self.assert_equals('foo ☕ bar', preview.content)

  def test_create_non_mastodon_reply(self):
    self.mock_get.return_value = requests_response({})
    self.mock_post.return_value = requests_response(STATUS)

    got = self.mastodon.create({
      'content': 'foo ☕ bar',
      'inReplyTo': [{'url': 'http://not/mastodon'}],
    })
    self.assert_equals(STATUS, got.content, got)
    self.assert_get(API_SEARCH,
                     params={'q': 'http://not/mastodon', 'resolve': True})
    self.assert_post(API_STATUSES, json={'status': 'foo ☕ bar'})

  def test_create_favorite_with_like_verb(self):
    self._test_create_favorite('like')

  def test_create_favorite_with_favorite_verb(self):
    self._test_create_favorite('favorite')

  def _test_create_favorite(self, verb):
    self.mock_post.return_value = requests_response(STATUS)

    obj = copy.deepcopy(LIKE)
    obj['verb'] = verb
    got = self.mastodon.create(obj).content
    self.assert_equals('like', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123#favorited-by-23507', got['url'])
    self.assert_post(API_FAVORITE % '123')

  def test_preview_favorite_with_like_verb(self):
    self._test_preview_favorite('like')

  def test_preview_favorite_with_favorite_verb(self):
    self._test_preview_favorite('favorite')

  def _test_preview_favorite(self, verb):
    obj = copy.deepcopy(LIKE)
    obj['verb'] = verb
    preview = self.mastodon.preview_create(obj)
    self.assertIn('<span class="verb">favorite</span> <a href="http://foo.com/@snarfed/123">this toot</a>: ', preview.description)

  def test_create_favorite_remote(self):
    url = STATUS_REMOTE['url']
    self.mock_get.return_value = requests_response({'statuses': [STATUS_REMOTE]})
    self.mock_post.return_value = requests_response(STATUS_REMOTE)

    got = self.mastodon.create(LIKE_REMOTE).content
    self.assert_equals('like', got['type'])
    self.assert_equals(url + '#favorited-by-23507', got['url'])
    self.assert_get(API_SEARCH, params={'q': url, 'resolve': True})
    self.assert_post(API_FAVORITE % '999')

  def test_preview_favorite_remote(self):
    url = STATUS_REMOTE['url']
    self.mock_get.return_value = requests_response({'statuses': [STATUS_REMOTE]})

    preview = self.mastodon.preview_create(LIKE_REMOTE)
    self.assertIn(
      f'<span class="verb">favorite</span> <a href="{url}">this toot</a>: ',
      preview.description)

  def test_create_reblog(self):
    self.mock_post.return_value = requests_response(STATUS)

    got = self.mastodon.create(SHARE_ACTIVITY).content
    self.assert_equals('repost', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123', got['url'])
    self.assert_post(API_REBLOG % '123')

  def test_preview_reblog(self):
    preview = self.mastodon.preview_create(SHARE_ACTIVITY)
    self.assertIn('<span class="verb">boost</span> <a href="http://foo.com/@snarfed/123">this toot</a>: ', preview.description)

  def test_create_reblog_remote(self):
    url = STATUS_REMOTE['url']
    self.mock_get.return_value = requests_response({'statuses': [STATUS_REMOTE]})
    self.mock_post.return_value = requests_response(STATUS)

    got = self.mastodon.create(SHARE_REMOTE).content
    self.assert_equals('repost', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123', got['url'])
    self.assert_get(API_SEARCH, params={'q': url, 'resolve': True})
    self.assert_post(API_REBLOG % '999')

  def test_preview_reblog_remote(self):
    url = STATUS_REMOTE['url']
    self.mock_get.return_value = requests_response({'statuses': [STATUS_REMOTE]})

    preview = self.mastodon.preview_create(SHARE_REMOTE)
    self.assertIn(
      f'<span class="verb">boost</span> <a href="{url}">this toot</a>: ',
      preview.description)

  def test_create_follow(self):
    actor_url = 'https://foo.com/@other'
    self.mock_get.return_value = requests_response(
      {'accounts': [{'id': '23507', 'url': actor_url}]})
    self.mock_post.return_value = requests_response({'id': '23507', 'following': True})

    result = self.mastodon.create({
      'objectType': 'activity',
      'verb': 'follow',
      'object': {'url': actor_url},
    })
    self.assertEqual({
      'type': 'follow',
      'id': '23507',
      'following': True,
      'url': None,
    }, result.content)
    self.assert_get(API_SEARCH,
                     params={'q': actor_url, 'resolve': True})
    self.assert_post(API_FOLLOW % '23507')

  def test_preview_follow(self):
    actor_url = 'https://foo.com/@other'
    self.mock_get.return_value = requests_response(
      {'accounts': [{'id': '23507', 'url': actor_url}]})

    preview = self.mastodon.preview_create({
      'objectType': 'activity',
      'verb': 'follow',
      'object': {'url': actor_url},
    })

    self.assertEqual('<span class="verb">follow</span> this user',
                     preview.description, preview.error_plain)

  def test_create_follow_no_url(self):
    result = self.mastodon.create({
      'objectType': 'activity',
      'verb': 'follow',
      'object': {},
    })

    self.assertTrue(result.abort)
    self.assertEqual('Could not find user  to follow.', result.error_plain)
    self.assertEqual('Could not find user  to follow.', result.error_html)

  def test_create_follow_not_found(self):
    self.mock_get.return_value = requests_response({'accounts': []})

    result = self.mastodon.create({
      'objectType': 'activity',
      'verb': 'follow',
      'object': {'url': 'https://foo.com/@nonexistent'},
    })

    self.assertTrue(result.abort)
    self.assertEqual(f'Could not find user https://foo.com/@nonexistent to follow.', result.error_plain)
    self.assertEqual(f'Could not find user <a href="https://foo.com/@nonexistent">foo.com/@nonexistent</a> to follow.', result.error_html)

  def test_preview_with_media(self):
    preview = self.mastodon.preview_create(MEDIA_OBJECT)
    self.assertEqual('<span class="verb">toot</span>:', preview.description)
    self.assertEqual('foo ☕ bar<br /><br /><video controls src="http://foo.com/video.mp4"><a href="http://foo.com/video.mp4">a fun video</a></video> &nbsp; <img src="http://foo.com/image.jpg" alt="a fun image" />',
                     preview.content)

  def test_preview_create_override_truncate_text_length(self):
    m = mastodon.Mastodon(INSTANCE, access_token='towkin',
                          user_id=ACCOUNT['id'], truncate_text_length=8)
    got = m.preview_create(OBJECT)
    self.assertEqual('foo ☕…', got.content)

    self.mock_post.return_value = requests_response(STATUS)
    result = m.create(OBJECT)
    self.assert_equals(STATUS, result.content, result)
    self.assert_post(API_STATUSES, json={'status': 'foo ☕…'})

  def test_create_with_media(self):
    self.mock_get.side_effect = [
      requests_response('pic 2'),  # video.mp4
      requests_response('pic 1'),  # image.jpg
    ]
    self.mock_post.side_effect = [
      requests_response({'id': 'a'}),   # API_MEDIA video
      requests_response({'id': 'b'}),   # API_MEDIA image
      requests_response(STATUS),        # API_STATUSES
    ]

    obj = copy.deepcopy(MEDIA_OBJECT)
    del obj['image']['displayName']
    result = self.mastodon.create(obj)
    self.assert_equals(STATUS, result.content, result)

    self.assertEqual(['http://foo.com/video.mp4', 'http://foo.com/image.jpg'],
                     [c.args[0] for c in self.mock_get.call_args_list])
    # files are uploaded as multipart streams, so check their contents separately
    self.assertEqual(
      [INSTANCE + API_MEDIA, INSTANCE + API_MEDIA, INSTANCE + API_STATUSES],
      [c.args[0] for c in self.mock_post.call_args_list])
    self.assertEqual({'description': 'a fun video'},
                     self.mock_post.call_args_list[0].kwargs['data'])
    self.assertEqual({}, self.mock_post.call_args_list[1].kwargs['data'])
    self.assert_post(API_STATUSES, json={'status': 'foo ☕ bar', 'media_ids': ['a', 'b']})
    self.assertEqual(
      b'pic 2', self.mock_post.call_args_list[0].kwargs['files']['file'].read())
    self.assertEqual(
      b'pic 1', self.mock_post.call_args_list[1].kwargs['files']['file'].read())

  def test_create_with_too_many_media(self):
    image_urls = [f'http://my/picture/{i}' for i in range(mastodon.MAX_MEDIA)]
    obj = {
      'objectType': 'note',
      'stream': {'url': 'http://my/video'},
      'image': [{'url': url} for url in image_urls],
      # duplicate video and images to check that they're de-duped
      'attachments': [{'objectType': 'video', 'stream': {'url': 'http://my/video'}}] +
        [{'objectType': 'image', 'url': url} for url in image_urls],
    }

    # test preview
    preview = self.mastodon.preview_create(obj)
    self.assertEqual('<span class="verb">toot</span>:', preview.description)
    self.assertEqual("""\
<br /><br />\
<video controls src="http://my/video"><a href="http://my/video">this video</a></video> \
&nbsp; <img src="http://my/picture/0" alt="" /> \
&nbsp; <img src="http://my/picture/1" alt="" /> \
&nbsp; <img src="http://my/picture/2" alt="" />""",
                     preview.content)

    # test create: downloads the video then MAX_MEDIA-1 images
    self.mock_get.side_effect = (
      [requests_response('vid')] +
      [requests_response('pic') for _ in image_urls[:-1]])
    self.mock_post.side_effect = (
      [requests_response({'id': str(i)}) for i in range(mastodon.MAX_MEDIA)] +
      [requests_response(STATUS)])

    result = self.mastodon.create(obj)
    self.assert_equals(STATUS, result.content, result)

    # downloads the video then MAX_MEDIA - 1 images
    self.assertEqual(['http://my/video'] + [f'http://my/picture/{i}'
                                            for i in range(len(image_urls) - 1)],
                     [c.args[0] for c in self.mock_get.call_args_list])
    # video then images uploaded to API_MEDIA, then the status to API_STATUSES.
    # files are uploaded as multipart streams, so check their contents separately.
    self.assertEqual(
      [INSTANCE + API_MEDIA] * mastodon.MAX_MEDIA + [INSTANCE + API_STATUSES],
      [c.args[0] for c in self.mock_post.call_args_list])
    for c in self.mock_post.call_args_list[:mastodon.MAX_MEDIA]:
      self.assertEqual({}, c.kwargs['data'])
    self.assert_post(API_STATUSES, json={'status': '', 'media_ids': ['0', '1', '2', '3']})
    self.assertEqual(
      b'vid', self.mock_post.call_args_list[0].kwargs['files']['file'].read())
    for c in self.mock_post.call_args_list[1:mastodon.MAX_MEDIA]:
      self.assertEqual(b'pic', c.kwargs['files']['file'].read())

  def test_delete(self):
    with patch.object(util.session, 'delete',
                      return_value=requests_response({})) as mock_delete:
      result = self.mastodon.delete(456)

    self.assert_equals({'url': 'http://foo.com/web/statuses/456'},
                       result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)
    self.assert_call(mock_delete, API_STATUS % '456')

  def test_preview_delete(self):
    got = self.mastodon.preview_delete('456')
    self.assertIn('<span class="verb">delete</span> <a href="http://foo.com/web/statuses/456">this toot</a>.', got.description)
    self.assertIsNone(got.error_plain)
    self.assertIsNone(got.error_html)

  def test_get_blocklist_ids(self):
    self.mock_get.return_value = requests_response([{'id': 1}, {'id': 2}])
    self.assert_equals([1, 2], self.mastodon.get_blocklist_ids())
    self.assert_get(API_BLOCKS)

  def test_get_blocklist_ids_paging(self):
    self.mock_get.side_effect = [
      requests_response([{'id': 1}, {'id': 2}], headers={
        'Link': '<http://foo.com/prev>; rel="prev", <http://foo.com/next>; rel="next"',
      }),
      requests_response([{'id': 3}, {'id': 4}], headers={
        'Link': '<http://foo.com/prev>; rel="prev"',
      }),
    ]
    self.assert_equals([1, 2, 3, 4], self.mastodon.get_blocklist_ids())
    self.assertEqual([INSTANCE + API_BLOCKS, 'http://foo.com/next'],
                     [c.args[0] for c in self.mock_get.call_args_list])

  def test_get_follows(self):
    self._test_get_follows_or_followers(self.mastodon.get_follows, mastodon.API_FOLLOWING)

  def test_get_followers(self):
    self._test_get_follows_or_followers(self.mastodon.get_followers, mastodon.API_FOLLOWERS)

  def _test_get_follows_or_followers(self, method, api_url):
    self.mock_get.side_effect = [
      requests_response([
        {'id': 1, 'username': 'alice'},
        {'id': 2, 'username': 'bob'},
      ], headers={
        'Link': '<http://foo.com/prev>; rel="prev", <http://foo.com/next>; rel="next"',
      }),
      requests_response([{'id': 3, 'username': 'eve'}], headers={
        'Link': '<http://foo.com/prev>; rel="prev"',
      }),
    ]
    self.assert_equals([{
      'objectType': 'person',
      'id': 'tag:foo.com:alice',
      'numeric_id': 1,
      'username': 'alice',
      'displayName': 'alice',
    }, {
      'objectType': 'person',
      'id': 'tag:foo.com:bob',
      'numeric_id': 2,
      'username': 'bob',
      'displayName': 'bob',
    }, {
      'objectType': 'person',
      'id': 'tag:foo.com:eve',
      'numeric_id': 3,
      'username': 'eve',
      'displayName': 'eve',
    }], method())

  @patch.object(mastodon, 'MAX_FOLLOWING', 3)
  def _test_get_follows_or_followers_max(self):
    self.mock_get.side_effect = [
      requests_response([{'id': 1}, {'id': 2}],
                        headers={'Link': '<http://foo.com/next>; rel="next"'}),
      requests_response([{'id': 3}, {'id': 4}]),
    ]
    self.assert_equals([{'id': 1}, {'id': 2}, {'id': 3}], self.mastodon.get_follows())
