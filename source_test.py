"""Unit tests for source.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import copy
import json
import mox

import source
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
import webapp2

LIKES = [{
    'verb': 'like',
    'author': {'id': 'tag:fake.com:person', 'numeric_id': '5'},
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
RSVPS = [{
    'id': 'tag:fake.com:246_rsvp_11500',
    'objectType': 'activity',
    'verb': 'rsvp-yes',
    'actor': {'displayName': 'Aaron P', 'id': 'tag:fake.com,2013:11500'},
    }, {
    'objectType': 'activity',
    'verb': 'rsvp-no',
    'actor': {'displayName': 'Ryan B'},
    }, {
    'id': 'tag:fake.com:246_rsvp_987',
    'objectType': 'activity',
    'verb': 'rsvp-maybe',
    'actor': {'displayName': 'Foo', 'id': 'tag:fake.com,2013:987'},
    }]
EVENT = {
  'id': 'tag:fake.com:246',
  'objectType': 'event',
  'displayName': 'Homebrew Website Club',
  }
EVENT_WITH_RSVPS = copy.deepcopy(EVENT)
EVENT_WITH_RSVPS.update({
  'attending': [RSVPS[0]['actor']],
  'notAttending': [RSVPS[1]['actor']],
  'maybeAttending': [RSVPS[2]['actor']],
  })


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

  def test_get_like_numeric_id(self):
    self.source.get_activities(user_id='author', activity_id='activity',
                               fetch_likes=True).AndReturn([ACTIVITY])
    self.mox.ReplayAll()
    self.assert_equals(LIKES[0], self.source.get_like('author', 'activity', '5'))

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

  def test_add_rsvps_to_event(self):
    event = copy.deepcopy(EVENT)
    source.Source.add_rsvps_to_event(event, [])
    self.assert_equals(EVENT, event)

    source.Source.add_rsvps_to_event(event, RSVPS)
    self.assert_equals(EVENT_WITH_RSVPS, event)

  def test_get_rsvps_from_event(self):
    self.assert_equals([], source.Source.get_rsvps_from_event(EVENT))
    self.assert_equals(RSVPS, source.Source.get_rsvps_from_event(EVENT_WITH_RSVPS))

  def test_get_rsvps_from_event_bad_id(self):
    event = copy.deepcopy(EVENT)
    for id in None, 'not_a_tag_uri':
      event['id'] = id
      self.assert_equals([], source.Source.get_rsvps_from_event(event))
