"""Unit tests for app.py.
"""

import json

import oauth_dropins.webutil.test
from oauth_dropins.webutil import testutil

import app


ACTIVITIES = [{
  'object': {
    'content': 'foo bar',
    'published': '2012-03-04T18:20:37+00:00',
    'url': 'https://perma/link',
  }
}, {
  'object': {
    'content': 'baz baj',
  },
}]

MF2_JSON = {'items': [{
  'type': [u'h-entry'],
  'properties': {
    'content': [{
      'value': 'foo bar',
      'html': 'foo bar',
    }],
    'published': ['2012-03-04T18:20:37+00:00'],
    'url': ['https://perma/link'],
  },
}, {
  'type': [u'h-entry'],
  'properties': {
    'content': [{
      'value': 'baz baj',
      'html': 'baz baj',
    }],
  },
}]}


class AppTest(testutil.HandlerTest):
  def test_url_activitystreams_json_mf2(self):
    self.expect_urlopen('http://my/posts.json', json.dumps(ACTIVITIES))
    self.mox.ReplayAll()
    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=activitystreams&output=json-mf2')
    self.assert_equals(200, resp.status_int)
    self.assert_equals(MF2_JSON, json.loads(resp.body))
