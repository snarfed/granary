"""Unit tests for app.py.
"""

import json

import oauth_dropins.webutil.test
from oauth_dropins.webutil import testutil

import app


ACTIVITIES = [{
  'verb': 'post',
  'object': {
    'content': 'foo bar',
    'published': '2012-03-04T18:20:37+00:00',
    'url': 'https://perma/link',
  }
}, {
  'verb': 'post',
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

HTML = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body%s>
<article class="h-entry h-as-article">
  <span class="u-uid"></span>

  <time class="dt-published" datetime="2012-03-04T18:20:37+00:00">2012-03-04T18:20:37+00:00</time>

  <a class="u-url" href="https://perma/link"></a>
  <div class="e-content p-name">

  foo bar
  </div>

</article>

<article class="h-entry h-as-article">
  <span class="u-uid"></span>

  <div class="e-content p-name">

  baz baj
  </div>

</article>

</body>
</html>

"""

ATOM_CONTENT = """\
  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

<br />
<br />
  %s<br />
  
  </div>
  </content>
"""


class AppTest(testutil.HandlerTest):

  def test_url_activitystreams_to_json_mf2(self):
    self.expect_urlopen('http://my/posts.json', json.dumps(ACTIVITIES))
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=activitystreams&output=json-mf2')
    self.assert_equals(200, resp.status_int)
    self.assert_equals(MF2_JSON, json.loads(resp.body))

  def test_url_json_mf2_to_html(self):
    self.expect_urlopen('http://my/posts.json', json.dumps(MF2_JSON))
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=json-mf2&output=html')
    self.assert_equals(200, resp.status_int)
    self.assert_equals(HTML % '', resp.body)

  def test_url_html_to_atom(self):
    self.expect_urlopen('http://my/posts.html', HTML % ' class="h-feed"')
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_int)
    self.assertIn(ATOM_CONTENT % 'foo bar', resp.body)
    self.assertIn(ATOM_CONTENT % 'baz baj', resp.body)
