#!/usr/bin/python
"""Unit tests for source.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

from webob import exc

import source
import testutil


class FakeSource(source.Source):
  # {user id: {group id: {activity id, app id}}}
  activities = None
  user_id = 0

  def get_activities(self, user=source.ME, group=source.SELF, app=None,
                     activity=None, start_index=0, count=0):
    if user:
      ret = [a for a in self.activities if a['id'] == user]
    else:
      ret = self.activities

    return len(self.activities), ret[start_index:count + start_index]

  def get_current_user(self):
    return self.user_id


class SourceTest(testutil.HandlerTest):
  def setUp(self):
    super(SourceTest, self).setUp()
    self.source = FakeSource(self.handler)

  def test_urlfetch(self):
    self.expect_urlfetch('http://my/url', 'hello', foo='bar')
    self.mox.ReplayAll()
    self.assertEquals('hello', self.source.urlfetch('http://my/url', foo='bar'))

  def test_urlfetch_error_passes_through(self):
    self.expect_urlfetch('http://my/url', 'my error', status=408)
    self.mox.ReplayAll()

    try:
      self.source.urlfetch('http://my/url')
    except exc.HTTPException, e:
      self.assertEquals(408, e.status_int)
      self.assertEquals('my error', self.response.body)
