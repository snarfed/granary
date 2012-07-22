#!/usr/bin/python
"""Unit tests for activitystreams.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json

import activitystreams
import facebook_test
import source
from webutil import testutil


class FakeSource(source.Source):
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
    self.mox.StubOutWithMock(FakeSource, 'get_activities')

  def get_response(self, url, *args, **kwargs):
    kwargs.setdefault('start_index', 0)
    kwargs.setdefault('count', activitystreams.ITEMS_PER_PAGE)

    FakeSource.get_activities(*args, **kwargs)\
        .AndReturn((9, self.activities))
    self.mox.ReplayAll()

    return activitystreams.application.get_response(url)

  def check_request(self, url, *args, **kwargs):
    resp = self.get_response(url, *args, **kwargs)
    self.assertEquals(200, resp.status_int)
    self.assert_equals({
        'startIndex': int(resp.request.get('startIndex', 0)),
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
    self.mox.StubOutWithMock(FakeSource, 'get_current_user')
    FakeSource.get_current_user().AndReturn(facebook_test.ACTOR)
    self.activities = [facebook_test.ACTIVITY]
    resp = self.get_response('?format=atom')
    self.assertEquals(200, resp.status_int)
    self.assert_multiline_equals("""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:ostatus="http://ostatus.org/schema/1.0">
<generator uri="https://github.com/snarfed/activitystreams-unofficial" version="0.1">
  activitystreams-unofficial</generator>
<id>http://localhost?format=atom</id>
<title>User feed for Ryan Barrett</title>
<subtitle>something about me</subtitle>
<logo>http://graph.facebook.com/snarfed.org/picture?type=large</logo>
<updated>2012-01-06T02:11:04+0000</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://www.facebook.com/snarfed.org</uri>
 <name>Ryan Barrett</name>
 <link rel="alternate" type="text/html" href="http://www.facebook.com/snarfed.org" />
 <link rel="avatar" href="http://graph.facebook.com/snarfed.org/picture?type=large" />
</author>

<link href="http://www.facebook.com/snarfed.org" rel="alternate" type="text/html" />
<link href="http://localhost?format=atom" rel="self" type="application/atom+xml" />
<!-- TODO -->
<!-- <link href="" rel="hub" /> -->
<!-- <link href="" rel="salmon" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-replies" /> -->
<!-- <link href="" rel="http://salmon-protocol.org/ns/salmon-mention" /> -->

<entry>
  <activity:object-type>
    http://activitystrea.ms/schema/1.0/note
  </activity:object-type>
  <id>tag:facebook.com,2012:212038_10100176064482163</id>
  <title>Checking another side project off my list. portablecontacts-unofficial is live!</title>
  <content type="text">Checking another side project off my list. portablecontacts-unofficial is live!</content>
  <link rel="alternate" type="text/html" href="http://facebook.com/212038/posts/10100176064482163" />
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-03-04T18:20:37+0000</published>
  <updated>2012-03-04T19:08:16+0000</updated>
  <!-- <link rel="ostatus:conversation" href="" /> -->
  <!-- http://www.georss.org/simple -->
  <georss:point>
    37.7281937175 -122.493364236
  </georss:point>
  <georss:featureName>Lake Merced</georss:featureName>
  <link rel="self" type="application/atom+xml" href="http://facebook.com/212038/posts/10100176064482163" />
</entry>

</feed>
""", resp.body)

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
