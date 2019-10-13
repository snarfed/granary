# coding=utf-8
"""Unit tests for mastodon.py."""
from __future__ import unicode_literals
from future import standard_library
standard_library.install_aliases()

import copy

from oauth_dropins.webutil import testutil
import ujson as json

from granary import appengine_config
from granary import as2, mastodon
from granary.mastodon import (
  API_FAVORITE,
  API_STATUSES,
)

INSTANCE = 'http://foo.com'

NOTE = {
  'objectType': 'note',
  'content': 'foo ☕ bar',
}
REPLY = {
  'objectType': 'note',
  'content': 'foo ☕ bar',
  'inReplyTo': [{'url': 'http://foo.com/@other/123'}],
}
LIKE = {
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'http://foo.com/@snarfed/123'},
}

# Mastodon
# https://docs.joinmastodon.org/api/entities/#account
ACCOUNT = {
  'id': '23507',
  'username': 'snarfed',
  'acct': 'snarfed',  # fully qualified if on a different instance
  'url': 'https://mastodon.technology/@snarfed',
  'display_name': 'Ryan Barrett',
  'avatar': 'https://cdn.mastodon.technology/accounts/avatars/000/023/507/original/01401e3558e03feb.png',
  'avatar_static': 'https://cdn.mastodon.technology/accounts/avatars/000/023/507/original/01401e3558e03feb.png',
  'header': 'https://cdn.mastodon.technology/accounts/headers/000/023/507/original/977013e803161a99.jpg',
  'header_static': 'https://cdn.mastodon.technology/accounts/headers/000/023/507/original/977013e803161a99.jpg',
  'note': '<p></p>',
  'created_at': '2017-04-19T20:38:19.704Z',
  'statuses_count': 19,
  'following_count': 12,
  'followers_count': 64,
  'fields': [{
    'verified_at': '2019-04-03T17:32:24.467+00:00',
    'name': 'Web site',
    'value': '<a href=\'https://snarfed.org\' rel=\'me nofollow noopener\' target=\'_blank\'><span class=\'invisible\'>https://</span><span class=\'\'>snarfed.org</span><span class=\'invisible\'></span></a>'
  }],
  'emojis': [],
  'bot': False,
  'locked': False,
}

# https://docs.joinmastodon.org/api/entities/#status
STATUS = {
  'id': '102526179954060294',
  'url': 'https://mastodon.technology/@snarfed/102526179954060294',
  'uri': 'https://mastodon.technology/users/snarfed/statuses/102526179954060294',
  'account': ACCOUNT,
  'in_reply_to_id': '102482741701856532',
  'in_reply_to_account_id': '11018',
  'content': '<p><span class=\'h-card\'><a href=\'https://queer.party/@fluffy\' class=\'u-url mention\'>@<span>fluffy</span></a></span> <span class=\'h-card\'><a href=\'https://mastodon.lubar.me/@ben\' class=\'u-url mention\'>@<span>ben</span></a></span> <span class=\'h-card\'><a href=\'https://fed.brid.gy/r/http://beesbuzz.biz/\' class=\'u-url mention\'>@<span>beesbuzz.biz</span></a></span> nope, no recent bridgy fed changes. it definitely does make the fediverse think your site is an activitypub/mastodon instance, which will trigger requests like these, but that’s always been true. more details: <a href=\'https://github.com/snarfed/bridgy-fed/issues/38\' rel=\'nofollow noopener\' target=\'_blank\'><span class=\'invisible\'>https://</span><span class=\'ellipsis\'>github.com/snarfed/bridgy-fed/</span><span class=\'invisible\'>issues/38</span></a></p>',
  'mentions': [{
    'id': '11018',
    'username': 'fluffy',
    'acct': 'fluffy@queer.party',
    'url': 'https://queer.party/@fluffy',
  }],
  'created_at': '2019-07-29T18:35:53.446Z',
  'media_attachments': [],
  'replies_count': 1,
  'favourites_count': 0,
  'reblogs_count': 0,
  'visibility': 'public',
  'spoiler_text': '',
  'card': {'...'},
  'application': {'website': None, 'name': 'Web'},
  'poll': None,
  'language': 'en',
  'emojis': [],
  'tags': [],
  'reblog': None,
  'muted': False,
  'reblogged': False,
  'favourited': False,
  'sensitive': False,
  'pinned': False,
}

class MastodonTest(testutil.TestCase):

  def setUp(self):
    super(MastodonTest, self).setUp()
    self.mastodon = mastodon.Mastodon(INSTANCE, username='alice',
                                      access_token='towkin')

  def expect_api(self, path, response=None, **kwargs):
    kwargs.setdefault('headers', {}).update({
      'Authorization': 'Bearer towkin',
    })
    return self.expect_requests_post(INSTANCE + path, response=response, **kwargs)

  def test_get_activities_defaults(self):
    self.expect_requests_get('http://foo.com/users/alice/outbox?page=true', json.dumps({
      'orderedItems': [
        {'content': 'foo bar'},
        {'content': 'bar baz'},
      ]}), headers=as2.CONNEG_HEADERS)
    self.mox.ReplayAll()

    self.assert_equals([
      {'content': 'foo bar'},
      {'content': 'bar baz'},
    ], self.mastodon.get_activities())

  def test_create_status(self):
    self.expect_api(API_STATUSES, json={'status': 'foo ☕ bar'}, response=STATUS)
    self.mox.ReplayAll()

    result = self.mastodon.create(NOTE)

    expected = copy.deepcopy(STATUS)
    expected['type'] = 'post'
    self.assert_equals(expected, result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)

  def test_preview_status(self):
    got = self.mastodon.preview_create(NOTE)
    self.assertEqual('<span class="verb">toot</span>:', got.description)
    self.assertEqual('foo ☕ bar', got.content)

  def test_create_status(self):
    self.expect_api(API_STATUSES, json={'status': 'foo ☕ bar'}, response=STATUS)
    self.mox.ReplayAll()

    result = self.mastodon.create(NOTE)

    self.assert_equals(STATUS, result.content, result)
    self.assertIsNone(result.error_plain)
    self.assertIsNone(result.error_html)

  def test_create_reply(self):
    self.expect_api(API_STATUSES, json={
      'status': 'foo ☕ bar',
      'in_reply_to_id': '123',
    }, response=STATUS)
    self.mox.ReplayAll()

    result = self.mastodon.create(REPLY)
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
    self.expect_api(API_FAVORITE % '123')
    self.mox.ReplayAll()

    result = self.mastodon.create(LIKE)
    self.assert_equals({
      'type': 'like',
      'url': 'http://foo.com/@snarfed/123',
    }, result.content, result)

  def test_preview_favorite(self):
    preview = self.mastodon.preview_create(LIKE)
    self.assertEqual('<span class="verb">favorite</span> <a href="http://foo.com/@snarfed/123">this toot</a>.', preview.description)
