"""Unit tests for source.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import mox

import source
from webutil import testutil
from webutil import util
import webapp2


LIKES = [{
    'verb': 'like',
    'author': {'id': 'tag:fake.com,2013:5'},
    'object': {'url': 'http://foo/like/5'},
    }, {
    'verb': 'like',
    'author': {'id': 'tag:fake.com,2013:6'},
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
    self.assert_equals(activity, self.source.original_post_discovery(
        copy.deepcopy(activity)))

    activity['object'].update({
        'content': 'x (sn.fd 123) y (xy zz) y (a.bc/D/EF) z',
        'attachments': [{'objectType': 'article', 'url': 'http://foo/1'}],
        'tags': [{'objectType': 'article', 'url': 'http://bar/2'}],
        })
    self.source.original_post_discovery(activity)
    self.assert_equals([
            {'objectType': 'article', 'url': 'http://sn.fd/123'},
            {'objectType': 'article', 'url': 'http://a.bc/D/EF'},
            {'objectType': 'article', 'url': 'http://foo/1'},
            {'objectType': 'article', 'url': 'http://bar/2'},
            ], activity['object']['tags'])


    # leading parens used to cause us trouble
    activity = {'object': {'content' : 'Foo (http://snarfed.org/xyz)'}}
    self.source.original_post_discovery(activity)
    self.assert_equals(
      [{'objectType': 'article', 'url': 'http://snarfed.org/xyz'}],
      activity['object']['tags'])

  def test_get_like(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn((1, [ACTIVITY]))
    self.mox.ReplayAll()
    self.assert_equals(LIKES[1], self.source.get_like('author', 'activity', '6'))

  # def test_get_like_not_found(self):
  #   self.expect_urlopen('https://graph.facebook.com/000', json.dumps(POST))
  #   self.mox.ReplayAll()
  #   self.assert_equals(None, self.facebook.get_like('123', '000', '999'))

  # def test_get_like_no_activity(self):
  #   self.expect_urlopen('https://graph.facebook.com/000', '{}')
  #   self.mox.ReplayAll()
  #   self.assert_equals(None, self.facebook.get_like('123', '000', '683713'))

