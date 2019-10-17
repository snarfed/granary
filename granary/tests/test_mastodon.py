# coding=utf-8
"""Unit tests for mastodon.py."""
from __future__ import unicode_literals
from future import standard_library
standard_library.install_aliases()

import copy

from oauth_dropins.webutil import testutil, util
from oauth_dropins.webutil.util import json_dumps, json_loads

from granary import appengine_config
from granary import mastodon
from granary import source
from granary.mastodon import (
  API_ACCOUNT,
  API_ACCOUNT_STATUSES,
  API_CONTEXT,
  API_FAVORITE,
  API_FAVORITED_BY,
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

ACCOUNT = {  # Mastodon; https://docs.joinmastodon.org/api/entities/#account
  'id': '23507',
  'username': 'snarfed',
  'acct': 'snarfed',  # fully qualified if on a different instance
  'url': 'http://foo.com/@snarfed',
  'display_name': 'Ryan Barrett',
  'avatar': 'http://foo.com/snarfed.png',
  'created_at': '2017-04-19T20:38:19.704Z',
  'note': 'my note',
  'fields': [{
    'name': 'Web site',
    'value': '<a href="https://snarfed.org" rel="me nofollow noopener" target="_blank"><span class="invisible">https://</span><span class="">snarfed.org</span><span class="invisible"></span></a>',
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
}
ACCOUNT_BOB = {
  'id': '999',
  'username': 'bob',
  'url': 'http://foo.com/@bob',
}
ACTOR_BOB = {
  'objectType': 'person',
  'id': tag_uri('bob'),
  'numeric_id': '999',
  'username': 'bob',
  'displayName': 'bob',
  'url': 'http://foo.com/@bob',
  'urls': [{'value': 'http://foo.com/@bob'}],
}
STATUS = {  # Mastodon; https://docs.joinmastodon.org/api/entities/#status
  'id': '123',
  'url': 'http://foo.com/@snarfed/123',
  'uri': 'http://foo.com/users/snarfed/statuses/123',
  'account': ACCOUNT,
  'content': '<p>foo ☕ bar <a ...>@alice</a> <a ...>#IndieWeb</a></p>',
  'created_at': '2019-07-29T18:35:53.446Z',
  'replies_count': 1,
  'favourites_count': 0,
  'reblogs_count': 0,
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
}
OBJECT = {  # ActivityStreams
  'objectType': 'note',
  'author': ACTOR,
  'content': STATUS['content'],
  'id': tag_uri('123'),
  'published': STATUS['created_at'],
  'url': STATUS['url'],
  'to': [{'objectType': 'group', 'alias': '@public'}],
  'tags': [{
    'objectType': 'mention',
    'id': tag_uri('11018'),
    'url': 'https://other/@alice',
    'displayName': 'alice',
  }, {
    'objectType': 'hashtag',
    'url': 'http://foo.com/tags/indieweb',
    'displayName': 'indieweb',
  }],
}
ACTIVITY = {  # ActivityStreams
  'verb': 'post',
  'published': STATUS['created_at'],
  'id': tag_uri('123'),
  'url': STATUS['url'],
  'actor': ACTOR,
  'object': OBJECT,
  'generator': {'displayName': 'my app', 'url': 'http://app'},
}
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
  'url': 'http://foo.com/@bob/789',
  'account': ACCOUNT_BOB,
  'reblog': STATUS,
}
SHARE_ACTIVITY = {  # ActivityStreams
  'objectType': 'activity',
  'verb': 'share',
  'id': tag_uri(789),
  'url': 'http://foo.com/@bob/789',
  'object': OBJECT,
  'actor': ACTOR_BOB,
}
MEDIA_STATUS = copy.deepcopy(STATUS)  # Mastodon
MEDIA_STATUS['media_attachments'] = [{
  'id': '222',
  'type': 'image',
  'url': 'http://foo.com/image.jpg',
  'description': None,
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
  'url': 'http://foo.com/video.mp4',
  'preview_url': 'http://foo.com/poster.png',
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
  'image': {'url': 'http://foo.com/image.jpg'},
  'attachments': [{
    'objectType': 'image',
    'id': tag_uri(222),
    'image': {'url': 'http://foo.com/image.jpg'},
  }, {
    'objectType': 'video',
    'id': tag_uri(444),
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
SHARE = {  # ActivityStreams
  'id': tag_uri('123_reblogged_by_23507'),
  'url': 'http://foo.com/@snarfed/123#reblogged-by-23507',
  'objectType': 'activity',
  'verb': 'share',
  'object': {'url': 'http://foo.com/@snarfed/123'},
  'author': ACTOR,
}
SHARE_BY_BOB = copy.deepcopy(SHARE)
SHARE_BY_BOB.update({
  'id': tag_uri('123_reblogged_by_999'),
  'url': 'http://foo.com/@snarfed/123#reblogged-by-999',
  'author': ACTOR_BOB,
})
MENTION_NOTIFICATION = {  # Mastodon
  'id': '555',
  'type': 'mention',
  'account': ACCOUNT_BOB,
  'status': MEDIA_STATUS,
  'created_at': '2019-10-15T00:23:37.969Z',
}

class MastodonTest(testutil.TestCase):

  def setUp(self):
    super(MastodonTest, self).setUp()
    self.mastodon = mastodon.Mastodon(INSTANCE, user_id=ACCOUNT['id'],
                                      access_token='towkin')

  def expect_get(self, *args, **kwargs):
    return self._expect_api(self.expect_requests_get, *args, **kwargs)

  def expect_post(self, *args, **kwargs):
    return self._expect_api(self.expect_requests_post, *args, **kwargs)

  def _expect_api(self, fn, path, response=None, **kwargs):
    kwargs.setdefault('headers', {}).update({
      'Authorization': 'Bearer towkin',
    })
    return fn(INSTANCE + path, response=response, **kwargs)

  def test_constructor_look_up_user_id(self):
    self.expect_get(API_VERIFY_CREDENTIALS, ACCOUNT)
    self.mox.ReplayAll()

    m = mastodon.Mastodon(INSTANCE, access_token='towkin')
    self.assertEqual(ACCOUNT['id'], m.user_id)

  def test_get_activities_defaults(self):
    self.expect_get(API_TIMELINE, [STATUS, REPLY_STATUS, MEDIA_STATUS])
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY, REPLY_ACTIVITY, MEDIA_ACTIVITY],
                       self.mastodon.get_activities())

  def test_get_activities_group_id_friends(self):
    self.expect_get(API_TIMELINE, [STATUS, REPLY_STATUS, MEDIA_STATUS])
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY, REPLY_ACTIVITY, MEDIA_ACTIVITY],
                       self.mastodon.get_activities(group_id=source.FRIENDS))

  def test_get_activities_fetch_replies(self):
    self.expect_get(API_TIMELINE, [STATUS])
    self.expect_get(API_CONTEXT % STATUS['id'], {
      'ancestors': [],
      'descendants': [REPLY_STATUS, REPLY_STATUS],
    })
    self.mox.ReplayAll()

    with_replies = copy.deepcopy(ACTIVITY)
    with_replies['object']['replies'] = {
        'items': [REPLY_ACTIVITY, REPLY_ACTIVITY],
    }
    self.assert_equals([with_replies], self.mastodon.get_activities(fetch_replies=True))

  def test_get_activities_fetch_likes(self):
    self.expect_get(API_TIMELINE, [STATUS])
    self.expect_get(API_FAVORITED_BY % STATUS['id'], [ACCOUNT, ACCOUNT])
    self.mox.ReplayAll()

    with_likes = copy.deepcopy(ACTIVITY)
    with_likes['object']['tags'].extend([LIKE, LIKE])
    self.assert_equals([with_likes], self.mastodon.get_activities(fetch_likes=True))

  def test_get_activities_fetch_shares(self):
    self.expect_get(API_TIMELINE, [STATUS])
    self.expect_get(API_REBLOGGED_BY % STATUS['id'], [ACCOUNT, ACCOUNT_BOB])
    self.mox.ReplayAll()

    with_shares = copy.deepcopy(ACTIVITY)
    with_shares['object']['tags'].extend([SHARE, SHARE_BY_BOB])
    self.assert_equals([with_shares], self.mastodon.get_activities(fetch_shares=True))

  def test_get_activities_fetch_mentions(self):
    self.expect_get(API_TIMELINE, [STATUS])
    self.expect_get(API_NOTIFICATIONS, [MENTION_NOTIFICATION], json={
      'exclude_types': ['follow', 'favourite', 'reblog'],
    })
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY, MEDIA_ACTIVITY],
                       self.mastodon.get_activities(fetch_mentions=True))

  def test_get_activities_activity_id(self):
    self.expect_get(API_STATUS % '123', STATUS)
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(activity_id=123))

  def test_get_activities_self_user_id(self):
    self.expect_get(API_ACCOUNT_STATUSES % '456', [STATUS])
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(
      group_id=source.SELF, user_id=456))

  def test_get_activities_self_default_user(self):
    self.expect_get(API_ACCOUNT_STATUSES % ACCOUNT['id'], [STATUS])
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY], self.mastodon.get_activities(group_id=source.SELF))

  def test_get_activities_search(self):
    self.expect_get(API_SEARCH, params={'q': 'indieweb'},
                    response={'statuses': [STATUS, MEDIA_STATUS]})
    self.mox.ReplayAll()
    self.assert_equals([ACTIVITY, MEDIA_ACTIVITY], self.mastodon.get_activities(
        group_id=source.SEARCH, search_query='indieweb'))

  def test_get_activities_search_no_query(self):
    with self.assertRaises(ValueError):
      self.mastodon.get_activities(group_id=source.SEARCH, search_query=None)

  def test_get_activities_group_friends_user_id(self):
    with self.assertRaises(ValueError):
      self.mastodon.get_activities(group_id=source.FRIENDS, user_id='345')

  def test_get_actor(self):
    self.expect_get(API_ACCOUNT % 1, ACCOUNT)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR, self.mastodon.get_actor(1))

  def test_get_actor_current_user(self):
    self.expect_get(API_ACCOUNT % ACCOUNT['id'], ACCOUNT_BOB)
    self.mox.ReplayAll()
    self.assert_equals(ACTOR_BOB, self.mastodon.get_actor())

  def test_get_comment(self):
    self.expect_get(API_STATUS % 1, STATUS)
    self.mox.ReplayAll()
    self.assert_equals(OBJECT, self.mastodon.get_comment(1))

  def test_user_to_actor(self):
    self.assert_equals(ACTOR, self.mastodon.user_to_actor(ACCOUNT))

  def test_user_to_actor_bob(self):
    self.assert_equals(ACTOR_BOB, self.mastodon.user_to_actor(ACCOUNT_BOB))

  def test_make_like(self):
    self.assert_equals(LIKE, self.mastodon._make_like(STATUS, ACCOUNT))

  def test_status_to_object(self):
    self.assert_equals(OBJECT, self.mastodon.status_to_object(STATUS))

  def test_status_to_activity(self):
    self.assert_equals(ACTIVITY, self.mastodon.status_to_activity(STATUS))

  def test_reply_status_to_object(self):
    self.assert_equals(REPLY_OBJECT, self.mastodon.status_to_object(REPLY_STATUS))

  def test_reply_status_to_activity(self):
    self.assert_equals(REPLY_ACTIVITY, self.mastodon.status_to_activity(REPLY_STATUS))

  def test_reblog_status_to_activity(self):
    self.assert_equals(SHARE_ACTIVITY, self.mastodon.status_to_activity(REBLOG_STATUS))

  def test_status_with_media_to_object(self):
    self.assert_equals(MEDIA_OBJECT, self.mastodon.status_to_object(MEDIA_STATUS))

  def test_preview_status(self):
    got = self.mastodon.preview_create(OBJECT)
    self.assertEqual('<span class="verb">toot</span>:', got.description)
    self.assertEqual('foo ☕ bar @alice #IndieWeb', got.content)

  def test_create_status(self):
    self.expect_post(API_STATUSES, json={'status': 'foo ☕ bar @alice #IndieWeb'},
                     response=STATUS)
    self.mox.ReplayAll()

    result = self.mastodon.create(OBJECT)

    self.assert_equals(STATUS, result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)

  def test_create_reply(self):
    self.expect_post(API_STATUSES, json={
      'status': 'foo ☕ bar @alice #IndieWeb',
      'in_reply_to_id': '456',
    }, response=STATUS)
    self.mox.ReplayAll()

    result = self.mastodon.create(REPLY_OBJECT)
    self.assert_equals(STATUS, result.content, result)

  def test_create_reply_other_instance(self):
    for fn in (self.mastodon.preview_create, self.mastodon.create):
      got = fn({
        'content': 'foo ☕ bar',
        'inReplyTo': [{'url': 'http://bad/@other/123'}],
      })
      self.assertTrue(got.abort, got)
      self.assertEqual('Could not find a toot on foo.com to reply to.',
                       got.error_plain)

  def test_create_favorite(self):
    self.expect_post(API_FAVORITE % '123', STATUS)
    self.mox.ReplayAll()

    got = self.mastodon.create(LIKE).content
    self.assert_equals('like', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123', got['url'])

  def test_preview_favorite(self):
    preview = self.mastodon.preview_create(LIKE)
    self.assertEqual('<span class="verb">favorite</span> <a href="http://foo.com/@snarfed/123">this toot</a>.', preview.description)

  def test_create_reblog(self):
    self.expect_post(API_REBLOG % '123', STATUS)
    self.mox.ReplayAll()

    got = self.mastodon.create(SHARE_ACTIVITY).content
    self.assert_equals('repost', got['type'])
    self.assert_equals('http://foo.com/@snarfed/123', got['url'])

  def test_preview_reblog(self):
    preview = self.mastodon.preview_create(SHARE_ACTIVITY)
    self.assertEqual('<span class="verb">boost</span> <a href="http://foo.com/@snarfed/123">this toot</a>.', preview.description)

  def test_preview_with_media(self):
    preview = self.mastodon.preview_create(MEDIA_OBJECT)
    self.assertEqual('<span class="verb">toot</span>:', preview.description)
    self.assertEqual('foo ☕ bar @alice #IndieWeb<br /><br /><video controls src="http://foo.com/video.mp4"><a href="http://foo.com/video.mp4">a fun video</a></video> &nbsp; <img src="http://foo.com/image.jpg" alt="" />',
                     preview.content)

  def test_create_with_media(self):
    self.expect_requests_get('http://foo.com/image.jpg', 'pic 1')
    self.expect_post(API_MEDIA, {'id': 'a'}, files={'file': b'pic 1'})

    self.expect_requests_get('http://foo.com/video.mp4', 'pic 2')
    self.expect_post(API_MEDIA, {'id': 'b'}, files={'file': b'pic 2'})

    self.expect_post(API_STATUSES, json={
      'status': 'foo ☕ bar @alice #IndieWeb',
      'media_ids': ['a', 'b'],
    }, response=STATUS)
    self.mox.ReplayAll()

    result = self.mastodon.create(MEDIA_OBJECT)
    self.assert_equals(STATUS, result.content, result)
