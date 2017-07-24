"""Unit tests for app.py.
"""
import copy
import httplib
import json
import socket
import xml.sax.saxutils

import mox
import oauth_dropins.webutil.test
from oauth_dropins.webutil import testutil

import appengine_config
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

JSONFEED = {
  'version': 'https://jsonfeed.org/version/1',
  'title': 'JSON Feed',
  'items': [{
    'url': 'https://perma/link',
    'id': 'https://perma/link',
    'content_html': 'foo bar',
    'date_published': '2012-03-04T18:20:37+00:00',
  }, {
    'content_html': 'baz baj',
  }],
}

HTML = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body%(body_class)s>%(extra)s
<article class="h-entry">
  <span class="p-uid"></span>

  <time class="dt-published" datetime="2012-03-04T18:20:37+00:00">2012-03-04T18:20:37+00:00</time>

  <a class="u-url" href="https://perma/link">https://perma/link</a>
  <div class="e-content p-name">

  foo bar
</div>

</article>

<article class="h-entry">
  <span class="p-uid"></span>

  <div class="e-content p-name">

  baz baj
</div>

</article>

</body>
</html>

"""

ATOM_CONTENT = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:georss="http://www.georss.org/georss"
      xmlns:ostatus="http://ostatus.org/schema/1.0"
      xmlns:thr="http://purl.org/syndication/thread/1.0"
      xml:base="http://my/">
<generator uri="https://github.com/snarfed/granary">granary</generator>
<id>http://my/posts.html</id>
<title>my title</title>

<logo>http://my/picture</logo>
<updated>2012-03-04T18:20:37+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/site</uri>
 <name>My Name</name>
</author>

<link rel="alternate" href="http://my/site" type="text/html" />
<link rel="avatar" href="http://my/picture" />
<link rel="self" href="http://localhost/url?url=http://my/posts.html&amp;input=html&amp;output=atom" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/site</uri>
 <name>My Name</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/note</activity:object-type>

  <id>https://perma/link</id>
  <title>foo bar</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">



foo bar

  </div>
  </content>

  <link rel="alternate" type="text/html" href="https://perma/link" />
  <link rel="ostatus:conversation" href="https://perma/link" />

  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T18:20:37+00:00</updated>

  <link rel="self" type="application/atom+xml" href="https://perma/link" />

</entry>
"""


class AppTest(testutil.HandlerTest):

  @staticmethod
  def request_url(path):
    return '%s://%s%s' % (appengine_config.SCHEME, appengine_config.HOST, path)

  def test_url_activitystreams_to_json_mf2(self):
    self.expect_urlopen('http://my/posts.json', json.dumps(ACTIVITIES))
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=activitystreams&output=json-mf2')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])
    self.assert_equals(MF2_JSON, json.loads(resp.body))

  def test_url_activitystreams_to_jsonfeed(self):
    self.expect_urlopen('http://my/posts.json', json.dumps(ACTIVITIES))
    self.mox.ReplayAll()

    path = '/url?url=http://my/posts.json&input=activitystreams&output=jsonfeed'
    resp = app.application.get_response(path)
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])

    expected = copy.deepcopy(JSONFEED)
    expected['feed_url'] = self.request_url(path)
    self.assert_equals(expected, json.loads(resp.body))

  def test_url_activitystreams_to_jsonfeed_not_list(self):
    self.expect_urlopen('http://my/posts.json', json.dumps({'foo': 'bar'}))
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=activitystreams&output=jsonfeed')
    self.assert_equals(400, resp.status_int)

  def test_url_jsonfeed_to_json_mf2(self):
    self.expect_urlopen('http://my/feed.json', json.dumps(JSONFEED))
    self.mox.ReplayAll()

    path = '/url?url=http://my/feed.json&input=jsonfeed&output=json-mf2'
    resp = app.application.get_response(path)
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])

    expected = copy.deepcopy(MF2_JSON)
    expected['items'][0]['properties']['uid'] = [JSONFEED['items'][0]['id']]
    self.assert_equals(expected, json.loads(resp.body))

  def test_url_json_mf2_to_html(self):
    self.expect_urlopen('http://my/posts.json', json.dumps(MF2_JSON))
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=json-mf2&output=html')
    self.assert_equals(200, resp.status_int)
    self.assert_equals(HTML % {
      'body_class': '',
      'extra': '',
    }, resp.body)

  def test_url_html_to_atom(self):
    self.expect_urlopen('http://my/posts.html', HTML % {
      'body_class': ' class="h-feed"',
      'extra': """
<span class="p-name">my title</span>
<div class="p-author h-card">
  <a href="http://my/site">My Name</a>
  <img src="http://my/picture" />
</div>
""",
    })
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_int)
    self.assert_multiline_in(ATOM_CONTENT, resp.body)

  def test_url_html_to_atom_rel_author(self):
    """
    https://github.com/snarfed/granary/issues/98
    https://github.com/kylewm/mf2util/issues/14
    """
    self.expect_urlopen('http://my/posts.html', HTML % {
      'body_class': ' class="h-feed"',
      'extra': """
<span class="p-name">my title</span>
<a href="/author" rel="author"></a>,
"""
    })
    self.expect_urlopen('http://my/author', """
<div class="h-card">
  <a class="u-url" href="http://my/author">Someone Else</a>
  <img class="u-photo" src="http://someone/picture" />
</div>
""", timeout=15)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_int)
    self.assert_multiline_in("""
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/author</uri>
 <name>Someone Else</name>
</author>

<link rel="alternate" href="http://my/author" type="text/html" />
<link rel="avatar" href="http://someone/picture" />
<link rel="self" href="http://localhost/url?url=http://my/posts.html&amp;input=html&amp;output=atom" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/author</uri>
 <name>Someone Else</name>
</author>
""", resp.body)

  def test_url_activitystreams_to_atom_reader_false(self):
    """reader=false should omit location in Atom output.

    https://github.com/snarfed/granary/issues/104
    """
    activity = copy.deepcopy(ACTIVITIES[0])
    activity['object']['location'] = {
      'displayName': 'My place',
      'url': 'http://my/place',
    }
    self.expect_urlopen('http://my/posts.as', json.dumps([activity]))
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.as&input=activitystreams&output=atom&reader=false')
    self.assert_equals(200, resp.status_int, resp.body)
    self.assertNotIn('p-location', resp.body)
    self.assertNotIn('<a class="p-name u-url" href="http://my/place">My place</a>',
                     resp.body)

  def test_url_bad_input(self):
    resp = app.application.get_response('/url?url=http://my/posts.json&input=foo')
    self.assert_equals(400, resp.status_int)

  def test_url_input_not_json(self):
    self.expect_urlopen('http://my/posts', '<html><body>not JSON</body></html>'
                        ).MultipleTimes()
    self.mox.ReplayAll()

    for input in 'activitystreams', 'json-mf2', 'jsonfeed':
      resp = app.application.get_response(
        '/url?url=http://my/posts&input=%s' % input)
      self.assert_equals(400, resp.status_int)

  def test_url_bad_url(self):
    self.expect_urlopen('http://astralandopal.com\\').AndRaise(httplib.InvalidURL(''))
    self.mox.ReplayAll()
    resp = app.application.get_response(
      '/url?url=http://astralandopal.com\\&input=html')
    self.assert_equals(400, resp.status_int)

  def test_url_fetch_fails(self):
    self.expect_urlopen('http://my/posts.html').AndRaise(socket.error(''))
    self.mox.ReplayAll()
    resp = app.application.get_response('/url?url=http://my/posts.html&input=html')
    self.assert_equals(504, resp.status_int)

  def test_cache(self):
    self.expect_urlopen('http://my/posts.html', HTML % {'body_class': '', 'extra': ''})
    self.mox.ReplayAll()

    # first fetch populates the cache
    url = '/url?url=http://my/posts.html&input=html'
    first = app.application.get_response(url)
    self.assert_equals(200, first.status_int)

    # second fetch should use the cache instead of fetching from the silo
    second = app.application.get_response(url)
    self.assert_equals(200, first.status_int)
    self.assert_equals(first.body, second.body)

  def test_hub(self):
    self.expect_urlopen('http://my/posts.html', HTML % {
      'body_class': '',
      'extra': '',
    })
    self.mox.ReplayAll()

    url = '/url?url=http://my/posts.html&input=html&output=atom&hub=http://a/hub'
    resp = app.application.get_response(url)

    self_url = 'http://localhost' + url
    self.assert_equals(200, resp.status_int)
    self.assert_multiline_in('<link rel="hub" href="http://a/hub" />', resp.body)
    self.assert_multiline_in(
      '<link rel="self" href="%s"' % xml.sax.saxutils.escape(self_url), resp.body)

    headers = resp.headers.getall('Link')
    self.assertIn('<http://a/hub>; rel="hub"', headers)
    self.assertIn('<%s>; rel="self"' % self_url, headers)
