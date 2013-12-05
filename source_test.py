"""Unit tests for source.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import mox

import source
from webutil import testutil
from webutil import util
import webapp2


class FakeSource(source.Source):
  def __init__(self, **kwargs):
    pass


class SourceTest(testutil.HandlerTest):

  def setUp(self):
    super(SourceTest, self).setUp()
    self.source = FakeSource()

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
