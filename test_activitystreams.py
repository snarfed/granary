"""Unit tests for activitystreams.py.
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import copy
import json

from oauth_dropins.webutil import testutil

import activitystreams
from granary import source
from granary.test import test_facebook
from granary.test import test_instagram
from granary.test import test_twitter


class FakeSource(source.Source):
  def __init__(self, **kwargs):
    pass


class HandlerTest(testutil.HandlerTest):

  activities = [{'foo': 'bar'}]

  def setUp(self):
    super(HandlerTest, self).setUp()
    self.reset()

  def reset(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    activitystreams.SOURCE = FakeSource
    self.mox.StubOutWithMock(FakeSource, 'get_activities_response')

  def get_response(self, url, *args, **kwargs):
    start_index = kwargs.setdefault('start_index', 0)
    kwargs.setdefault('count', activitystreams.ITEMS_PER_PAGE)

    FakeSource.get_activities_response(*args, **kwargs).AndReturn({
        'startIndex': start_index,
        'itemsPerPage': 1,
        'totalResults': 9,
        'items': self.activities,
        'filtered': False,
        'sorted': False,
        'updatedSince': False,
        })
    self.mox.ReplayAll()

    return activitystreams.application.get_response(url)

  def check_request(self, url, *args, **kwargs):
    resp = self.get_response(url, *args, **kwargs)
    self.assertEquals(200, resp.status_int)
    self.assert_equals({
        'startIndex': int(kwargs.get('start_index', 0)),
        'itemsPerPage': 1,
        'totalResults': 9,
        'items': [{'foo': 'bar'}],
        'filtered': False,
        'sorted': False,
        'updatedSince': False,
        },
      json.loads(resp.body))

  def test_all_defaults(self):
    self.check_request('/')

  def test_me(self):
    self.check_request('/@me', None)

  def test_user_id(self):
    self.check_request('/123/', '123')

  def test_all(self):
    self.check_request('/123/@all/', '123', None)

  def test_friends(self):
    self.check_request('/123/@friends/', '123', None)

  def test_self(self):
    self.check_request('/123/@self/', '123', '@self')

  def test_group_id(self):
    self.check_request('/123/456', '123', '456')

  def test_app(self):
    self.check_request('/123/456/@app/', '123', '456', None)

  def test_app_id(self):
    self.check_request('/123/456/789/', '123', '456', '789')

  def test_activity_id(self):
    self.check_request('/123/456/789/000/', '123', '456', '789', '000')

  def test_defaults_and_activity_id(self):
    self.check_request('/@me/@all/@app/000/', None, None, None, '000')

  def test_json_format(self):
    self.check_request('/@me/?format=json', None)

  def test_xml_format(self):
    resp = self.get_response('?format=xml')
    self.assertEquals(200, resp.status_int)
    self.assert_multiline_equals("""\
<?xml version="1.0" encoding="UTF-8"?>
<response>
<items>
<foo>bar</foo>
</items>
<itemsPerPage>1</itemsPerPage>
<updatedSince>False</updatedSince>
<startIndex>0</startIndex>
<sorted>False</sorted>
<filtered>False</filtered>
<totalResults>9</totalResults>
</response>
""", resp.body)

  def test_atom_format(self):
    for test_module in test_facebook, test_instagram, test_twitter:
      self.reset()
      self.mox.StubOutWithMock(FakeSource, 'get_actor')
      FakeSource.get_actor(None).AndReturn(test_module.ACTOR)
      self.activities = [copy.deepcopy(test_module.ACTIVITY)]

      # include access_token param to check that it gets stripped
      resp = self.get_response('?format=atom&access_token=foo&a=b')
      self.assertEquals(200, resp.status_int)
      self.assert_multiline_equals(
        test_module.ATOM % {'request_url': 'http://localhost',
                            'host_url': 'http://localhost/'},
        resp.body)

  def test_unknown_format(self):
    resp = activitystreams.application.get_response('?format=bad')
    self.assertEquals(400, resp.status_int)

  def test_bad_start_index(self):
    resp = activitystreams.application.get_response('?startIndex=foo')
    self.assertEquals(400, resp.status_int)

  def test_bad_count(self):
    resp = activitystreams.application.get_response('?count=-1')
    self.assertEquals(400, resp.status_int)

  def test_start_index(self):
    expected_count = activitystreams.ITEMS_PER_PAGE - 2
    self.check_request('?startIndex=2', start_index=2, count=expected_count)

  def test_count(self):
    self.check_request('?count=3', count=3)

  def test_start_index_and_count(self):
    self.check_request('?startIndex=4&count=5', start_index=4, count=5)

  def test_count_greater_than_items_per_page(self):
    self.check_request('?count=999', count=activitystreams.ITEMS_PER_PAGE)

    # TODO: move to facebook and/or twitter since they do implementation
  # def test_start_index_count_zero(self):
  #   self.check_request('?startIndex=0&count=0', self.ACTIVITIES)

  # def test_start_index(self):
  #   self.check_request('?startIndex=1&count=0', self.ACTIVITIES[1:])
  #   self.check_request('?startIndex=2&count=0', self.ACTIVITIES[2:])

  # def test_count_past_end(self):
  #   self.check_request('?startIndex=0&count=10', self.ACTIVITIES)
  #   self.check_request('?startIndex=1&count=10', self.ACTIVITIES[1:])

  # def test_start_index_past_end(self):
  #   self.check_request('?startIndex=10&count=0', [])
  #   self.check_request('?startIndex=10&count=10', [])

  # def test_start_index_subtracts_from_count(self):
  #   try:
  #     orig_items_per_page = activitystreams.ITEMS_PER_PAGE
  #     activitystreams.ITEMS_PER_PAGE = 2
  #     self.check_request('?startIndex=1&count=0', self.ACTIVITIES[1:2])
  #   finally:
  #     activitystreams.ITEMS_PER_PAGE = orig_items_per_page

  # def test_start_index_and_count(self):
  #   self.check_request('?startIndex=1&count=1', [self.ACTIVITIES[1]])
