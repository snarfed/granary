#!/usr/bin/python
"""Unit tests for activitystreams.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json
import mox
from webob import exc

import activitystreams
import source
import source_test
import testutil


class HandlersTest(testutil.HandlerTest):

  ACTIVITIES = [
    {'id': 2, 'displayName': 'me'},
    {'id': 4},
    {'id': 2, 'displayName': 'Ryan'}]
  SELF_ACTIVITIES = [
    {'id': 2, 'displayName': 'me'},
    {'id': 2, 'displayName': 'Ryan'}]

  def setUp(self):
    super(HandlersTest, self).setUp(application=activitystreams.application)
    activitystreams.SOURCE = source_test.FakeSource
    activitystreams.SOURCE.activities = self.ACTIVITIES
    activitystreams.SOURCE.user_id = 2

  def assert_response(self, url, expected_activities):
    resp = self.application.get_response('/activitystreams' + url)
    self.assertEquals(200, resp.status_int)
    self.assert_equals({
        'startIndex': int(resp.request.get('startIndex', 0)),
        'itemsPerPage': len(expected_activities),
        'totalResults': len(activitystreams.SOURCE.activities),
        'entry': expected_activities,
        'filtered': False,
        'sorted': False,
        'updatedSince': False,
        },
      json.loads(resp.body))

  def test_all_no_activities(self):
    for url in '', '/', '/@me/@all', '/@me/@all/':
      self.setUp()
      activitystreams.SOURCE.activities = []
      self.assert_response(url, [])

  def test_all_get_some_activities(self):
    self.assert_response('/@me/@all/', self.ACTIVITIES)

  def test_self(self):
    self.assert_response('/@me/@self/', self.SELF_ACTIVITIES)

  def test_user_id(self):
    self.assert_response('/@me/@all/2/', self.SELF_ACTIVITIES)

  def test_json_format(self):
    self.assert_response('/@me/@all/?format=json', self.ACTIVITIES)

  def test_xml_format(self):
    resp = self.application.get_response('/activitystreams/@me/@all/?format=xml')
    self.assertEquals(200, resp.status_int)
    self.assertEqual("""\
<?xml version="1.0" encoding="UTF-8"?>
<response>
<entry>
<displayName>me</displayName>
<id>2</id>
</entry>
<entry>
<id>4</id>
</entry>
<entry>
<displayName>Ryan</displayName>
<id>2</id>
</entry>
<itemsPerPage>3</itemsPerPage>
<updatedSince>False</updatedSince>
<startIndex>0</startIndex>
<sorted>False</sorted>
<filtered>False</filtered>
<totalResults>3</totalResults>
</response>
""", resp.body)

  def test_unknown_format(self):
    resp = self.application.get_response('/activitystreams/@me/@all/?format=bad')
    self.assertEquals(400, resp.status_int)

  def test_bad_start_index(self):
    resp = self.application.get_response('/activitystreams/@me/@all/?startIndex=foo')
    self.assertEquals(400, resp.status_int)

  def test_bad_count(self):
    resp = self.application.get_response('/activitystreams/@me/@all/?count=-1')
    self.assertEquals(400, resp.status_int)

  def test_start_index_count_zero(self):
    self.assert_response('/@me/@all/?startIndex=0&count=0', self.ACTIVITIES)

  def test_start_index(self):
    self.assert_response('/@me/@all/?startIndex=1&count=0', self.ACTIVITIES[1:])
    self.assert_response('/@me/@all/?startIndex=2&count=0', self.ACTIVITIES[2:])

  def test_count_past_end(self):
    self.assert_response('/@me/@all/?startIndex=0&count=10', self.ACTIVITIES)
    self.assert_response('/@me/@all/?startIndex=1&count=10', self.ACTIVITIES[1:])

  def test_start_index_past_end(self):
    self.assert_response('/@me/@all/?startIndex=10&count=0', [])
    self.assert_response('/@me/@all/?startIndex=10&count=10', [])

  def test_start_index_subtracts_from_count(self):
    try:
      orig_items_per_page = activitystreams.ITEMS_PER_PAGE
      activitystreams.ITEMS_PER_PAGE = 2
      self.assert_response('/@me/@all/?startIndex=1&count=0', self.ACTIVITIES[1:2])
    finally:
      activitystreams.ITEMS_PER_PAGE = orig_items_per_page

  def test_start_index_and_count(self):
    self.assert_response('/@me/@all/?startIndex=1&count=1', [self.ACTIVITIES[1]])
