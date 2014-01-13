"""Unit tests for source.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import json
import mox

import source
from webutil import testutil
from webutil import util
import webapp2


LIKES = [{
    'verb': 'like',
    'author': {'id': 'tag:fake.com:5'},
    'object': {'url': 'http://foo/like/5'},
    }, {
    'verb': 'like',
    'author': {'id': 'tag:fake.com:6'},
    'object': {'url': 'http://bar/like/6'},
    },
  ]
ACTIVITY = {
  'id': '1',
  'object': {
    'id': '1',
    'tags': LIKES,
    }
  }

class FakeSource(source.Source):
  DOMAIN = 'fake.com'

  def __init__(self, **kwargs):
    pass


class SourceTest(testutil.HandlerTest):

  def setUp(self):
    super(SourceTest, self).setUp()
    self.source = FakeSource()
    self.mox.StubOutWithMock(self.source, 'get_activities')

  def test_original_post_discovery(self):
    activity = {'object': {
        'objectType': 'article',
        'displayName': 'article abc',
        'url': 'http://example.com/article-abc',
        'tags': [],
        }}
    self.assert_equals(activity, source.Source.original_post_discovery(
        copy.deepcopy(activity)))

    activity['object']['content'] = 'x (not.at end) y (at.the end)'
    source.Source.original_post_discovery(activity)
    self.assert_equals([{'objectType': 'article', 'url': 'http://at.the/end'}],
                       activity['object']['tags'])

    activity['object'].update({
        'content': 'x http://baz/3 y',
        'attachments': [{'objectType': 'article', 'url': 'http://foo/1'}],
        'tags': [{'objectType': 'article', 'url': 'http://bar/2'}],
        })
    source.Source.original_post_discovery(activity)
    self.assert_equals([
        {'objectType': 'article', 'url': 'http://foo/1'},
        {'objectType': 'article', 'url': 'http://bar/2'},
        {'objectType': 'article', 'url': 'http://baz/3'},
        ], activity['object']['tags'])


    # leading parens used to cause us trouble
    activity = {'object': {'content' : 'Foo (http://snarfed.org/xyz)'}}
    source.Source.original_post_discovery(activity)
    self.assert_equals(
      [{'objectType': 'article', 'url': 'http://snarfed.org/xyz'}],
      activity['object']['tags'])

  def test_get_like(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(LIKES[1], self.source.get_like('author', 'activity', '6'))

  def test_get_like_not_found(self):
    activity = copy.deepcopy(ACTIVITY)
    del activity['object']['tags']
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([activity])
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_like('author', 'activity', '6'))

  def test_get_like_no_activity(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([])
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_like('author', 'activity', '6'))

  def test_get_share(self):
    activity = copy.deepcopy(ACTIVITY)
    share = activity['object']['tags'][1]
    share['verb'] = 'share'
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_shares=True).AndReturn([activity])
    self.mox.ReplayAll()
    self.assert_equals(share, self.source.get_share('author', 'activity', '6'))

  def test_get_share_not_found(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_shares=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(None, self.source.get_share('author', 'activity', '6'))
