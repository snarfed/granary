"""Unit tests for app.py.
"""
from __future__ import unicode_literals
import copy
import json
import socket
import xml.sax.saxutils

import appengine_config
from google.appengine.api import memcache
import oauth_dropins.webutil.test
from oauth_dropins.webutil import testutil_appengine
import requests

import app


AS1 = [{
  'objectType': 'activity',
  'verb': 'post',
  'object': {
    'content': 'foo bar',
    'published': '2012-03-04T18:20:37+00:00',
    'url': 'https://perma/link',
  }
}, {
  'objectType': 'activity',
  'verb': 'post',
  'object': {
    'content': 'baz baj',
  },
}]
AS1_RESPONSE = {
  'items': AS1,
  'itemsPerPage': 2,
  'filtered': False,
  'sorted': False,
  'startIndex': 0,
  'totalResults': 2,
  'updatedSince': False,
}

AS2 = [{
  '@context': 'https://www.w3.org/ns/activitystreams',
  'type': 'Create',
  'object': {
    'content': 'foo bar',
    'published': '2012-03-04T18:20:37+00:00',
    'url': 'https://perma/link',
  }
}, {
  '@context': 'https://www.w3.org/ns/activitystreams',
  'type': 'Create',
  'object': {
    'content': 'baz baj',
  },
}]
AS2_RESPONSE = {
  'items': AS2,
  'itemsPerPage': 2,
  'startIndex': 0,
  'totalItems': 2,
  'updated': False,
}

MF2 = {'items': [{
  'type': ['h-entry'],
  'properties': {
    'content': [{
      'value': 'foo bar',
      'html': 'foo bar',
    }],
    'published': ['2012-03-04T18:20:37+00:00'],
    'url': ['https://perma/link'],
  },
}, {
  'type': ['h-entry'],
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
<generator uri="https://granary.io/">granary</generator>
<id>http://my/posts.html</id>
<title>User feed for My Name</title>

<logo>http://my/picture</logo>
<updated>2012-03-04T18:20:37+00:00</updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/site</uri>
 <name>My Name</name>
</author>

<link rel="alternate" href="http://my/posts.html" type="text/html" />
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
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>

  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T18:20:37+00:00</updated>

  <link rel="self" type="application/atom+xml" href="https://perma/link" />

</entry>
"""


class AppTest(testutil_appengine.HandlerTest):

  @staticmethod
  def request_url(path):
    return '%s://%s%s' % (appengine_config.SCHEME, appengine_config.HOST, path)

  def test_url_as1_to_mf2_json(self):
    self.expect_requests_get('http://my/posts.json', AS1)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=as1&output=mf2-json')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])
    self.assert_equals(MF2, json.loads(resp.body))

  def test_url_as1_to_as2(self):
    self.expect_requests_get('http://my/posts.json', AS1)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=as1&output=as2')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/activity+json', resp.headers['Content-Type'])
    self.assert_equals(AS2_RESPONSE, json.loads(resp.body))

  def test_url_as1_response_to_as2(self):
    self.expect_requests_get('http://my/posts.json', AS1_RESPONSE)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=as1&output=as2')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/activity+json', resp.headers['Content-Type'])
    self.assert_equals(AS2_RESPONSE, json.loads(resp.body))

  def test_url_as2_to_as1(self):
    self.expect_requests_get('http://my/posts.json', AS2)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=as2&output=as1')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(AS1_RESPONSE, json.loads(resp.body))

  def test_url_as2_response_to_as1(self):
    self.expect_requests_get('http://my/posts.json', AS2_RESPONSE)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=as2&output=as1')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(AS1_RESPONSE, json.loads(resp.body))

  def test_url_as1_to_jsonfeed(self):
    self.expect_requests_get('http://my/posts.json', AS1)
    self.mox.ReplayAll()

    path = '/url?url=http://my/posts.json&input=as1&output=jsonfeed'
    resp = app.application.get_response(path)
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])

    expected = copy.deepcopy(JSONFEED)
    expected['feed_url'] = self.request_url(path)
    self.assert_equals(expected, json.loads(resp.body))

    # TODO: drop?
  # def test_url_as1_to_jsonfeed_not_list(self):
  #   self.expect_requests_get('http://my/posts.json', {'foo': 'bar'})
  #   self.mox.ReplayAll()

  #   resp = app.application.get_response(
  #     '/url?url=http://my/posts.json&input=as1&output=jsonfeed')
  #   self.assert_equals(400, resp.status_int)

  def test_url_jsonfeed_to_json_mf2(self):
    self.expect_requests_get('http://my/feed.json', JSONFEED)
    self.mox.ReplayAll()

    path = '/url?url=http://my/feed.json&input=jsonfeed&output=json-mf2'
    resp = app.application.get_response(path)
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])

    expected = copy.deepcopy(MF2)
    expected['items'][0]['properties']['uid'] = [JSONFEED['items'][0]['id']]
    self.assert_equals(expected, json.loads(resp.body))

  def test_url_bad_jsonfeed(self):
    self.expect_requests_get('http://my/feed.json', ['not', 'jsonfeed'])
    self.mox.ReplayAll()

    path = '/url?url=http://my/feed.json&input=jsonfeed&output=json-mf2'
    resp = app.application.get_response(path)
    self.assert_equals(400, resp.status_int)
    self.assertIn('Could not parse http://my/feed.json as JSON Feed', resp.body)

  def test_url_json_mf2_to_html(self):
    self.expect_requests_get('http://my/posts.json', MF2)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.json&input=json-mf2&output=html')
    self.assert_equals(200, resp.status_int)
    self.assert_multiline_equals(HTML % {
      'body_class': '',
      'extra': '',
    }, resp.body, ignore_blanks=True)

  def test_url_html_to_atom(self):
    self.expect_requests_get('http://my/posts.html', HTML % {
      'body_class': ' class="h-feed"',
      'extra': """
<span>my title</span>
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
    self.assert_multiline_in(ATOM_CONTENT, resp.body, ignore_blanks=True)

  def test_url_html_to_atom_rel_author(self):
    """
    https://github.com/snarfed/granary/issues/98
    https://github.com/kylewm/mf2util/issues/14
    """
    self.expect_requests_get('http://my/posts.html', HTML % {
      'body_class': ' class="h-feed"',
      'extra': """
<span class="p-name">my title</span>
<a href="/author" rel="author"></a>,
"""
    })
    self.expect_requests_get('http://my/author', """
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

<link rel="alternate" href="http://my/posts.html" type="text/html" />
<link rel="alternate" href="http://my/author" type="text/html" />
<link rel="avatar" href="http://someone/picture" />
<link rel="self" href="http://localhost/url?url=http://my/posts.html&amp;input=html&amp;output=atom" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/author</uri>
 <name>Someone Else</name>
</author>
""", resp.body, ignore_blanks=True)

  def test_url_html_to_atom_skip_silo_rel_authors(self):
    self.expect_requests_get('http://my/posts.html', HTML % {
      'body_class': ' class="h-feed"',
      'extra': """
<span class="p-name">my title</span>
<a href="https://plus.google.com/+Author" rel="author"></a>,
"""
    })
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_int)
    self.assert_multiline_in("""
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://plus.google.com/+Author</uri>
</author>

<link rel="alternate" href="http://my/posts.html" type="text/html" />
<link rel="alternate" href="https://plus.google.com/+Author" type="text/html" />
<link rel="self" href="http://localhost/url?url=http://my/posts.html&amp;input=html&amp;output=atom" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://plus.google.com/+Author</uri>
</author>
""", resp.body, ignore_blanks=True)

  def test_url_html_to_json_mf2(self):
    html = HTML % {'body_class': ' class="h-feed"', 'extra': ''}
    self.expect_requests_get('http://my/posts.html', html)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.html&input=html&output=json-mf2')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/json', resp.headers['Content-Type'])

    expected = copy.deepcopy(MF2)
    for obj in expected['items']:
      obj['properties']['name'] = [obj['properties']['content'][0]['value'].strip()]
    self.assert_equals(expected, json.loads(resp.body))

  def test_url_html_to_html(self):
    html = HTML % {'body_class': ' class="h-feed"', 'extra': ''}
    self.expect_requests_get('http://my/posts.html', html)
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.html&input=html&output=html')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('text/html; charset=utf-8', resp.headers['Content-Type'])

    self.assert_multiline_in("""\
<time class="dt-published" datetime="2012-03-04T18:20:37+00:00">2012-03-04T18:20:37+00:00</time>
<a class="p-name u-url" href="https://perma/link">foo bar</a>
<div class="e-content">
foo bar
</div>
""", resp.body, ignore_blanks=True)
    self.assert_multiline_in("""\
<span class="p-name">baz baj</span>
<div class="e-content">
baz baj
</div>
""", resp.body, ignore_blanks=True)

  def test_url_atom_to_as1(self):
    self.expect_requests_get('http://feed', ATOM_CONTENT + '</feed>\n')
    self.mox.ReplayAll()

    resp = app.application.get_response('/url?url=http://feed&input=atom&output=as1')
    self.assert_equals(200, resp.status_int)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals({
      'items': [{
        'id': 'https://perma/link',
        'objectType': 'activity',
        'verb': 'post',
        'actor': {
          'objectType': 'person',
          'displayName': 'My Name',
          'url': 'http://my/site',
        },
        'object': {
          'id': 'https://perma/link',
          'objectType': 'note',
          'title': 'foo bar',
          'content': 'foo bar',
          'published': '2012-03-04T18:20:37+00:00',
          'updated': '2012-03-04T18:20:37+00:00',
        },
      }],
      'itemsPerPage': 1,
      'totalResults': 1,
      'startIndex': 0,
      'sorted': False,
      'filtered': False,
      'updatedSince': False,
    }, json.loads(resp.body))

  def test_url_atom_to_as1_parse_error(self):
    self.expect_requests_get('http://feed', 'not valid xml')
    self.mox.ReplayAll()

    resp = app.application.get_response('/url?url=http://feed&input=atom&output=as1')
    self.assert_equals(400, resp.status_int)
    self.assertIn('Could not parse http://feed as XML: ', resp.body)

  def test_url_atom_to_as1_not_atom(self):
    self.expect_requests_get('http://feed', """\
<?xml version="1.0" encoding="UTF-8"?>
<rss>
not atom!
</rss>""")
    self.mox.ReplayAll()

    resp = app.application.get_response('/url?url=http://feed&input=atom&output=as1')
    self.assert_equals(400, resp.status_int)
    self.assertIn('Could not parse http://feed as Atom: ', resp.body)

  def test_url_as1_to_atom_reader_false(self):
    """reader=false should omit location in Atom output.

    https://github.com/snarfed/granary/issues/104
    """
    activity = copy.deepcopy(AS1[0])
    activity['object']['location'] = {
      'displayName': 'My place',
      'url': 'http://my/place',
    }
    self.expect_requests_get('http://my/posts.as', [activity])
    self.mox.ReplayAll()

    resp = app.application.get_response(
      '/url?url=http://my/posts.as&input=as1&output=atom&reader=false')
    self.assert_equals(200, resp.status_int, resp.body)
    self.assertNotIn('p-location', resp.body)
    self.assertNotIn('<a class="p-name u-url" href="http://my/place">My place</a>',
                     resp.body)

  def test_url_bad_input(self):
    resp = app.application.get_response('/url?url=http://my/posts.json&input=foo')
    self.assert_equals(400, resp.status_int)

  def test_url_input_not_json(self):
    self.expect_requests_get('http://my/posts', '<html><body>not JSON</body></html>'
                        ).MultipleTimes()
    self.mox.ReplayAll()

    for input in 'as1', 'as2', 'activitystreams', 'json-mf2', 'jsonfeed':
      resp = app.application.get_response(
        '/url?url=http://my/posts&input=%s' % input)
      self.assert_equals(400, resp.status_int)

  def test_url_bad_url(self):
    self.expect_requests_get('http://astralandopal.com\\'
                            ).AndRaise(requests.exceptions.MissingSchema('foo'))
    self.mox.ReplayAll()
    resp = app.application.get_response(
      '/url?url=http://astralandopal.com\\&input=html')
    self.assert_equals(400, resp.status_int)

  def test_url_fetch_fails(self):
    self.expect_requests_get('http://my/posts.html').AndRaise(socket.timeout(''))
    self.mox.ReplayAll()
    resp = app.application.get_response('/url?url=http://my/posts.html&input=html')
    self.assert_equals(504, resp.status_int)

  def test_cache(self):
    self.expect_requests_get('http://my/posts.html', HTML % {'body_class': '', 'extra': ''})
    self.mox.ReplayAll()

    # first fetch populates the cache
    url = '/url?url=http://my/posts.html&input=html'
    first = app.application.get_response(url)
    self.assert_equals(200, first.status_int)

    # second fetch should use the cache instead of fetching from the silo
    second = app.application.get_response(url)
    self.assert_equals(200, first.status_int)
    self.assert_equals(first.body, second.body)

  def test_skip_caching_big_responses(self):
    self.mox.stubs.Set(memcache, 'MAX_VALUE_SIZE', 100)

    self.expect_requests_get('http://my/posts.html', 'x' * 101)
    self.mox.ReplayAll()

    first = app.application.get_response('/url?url=http://my/posts.html&input=html')
    self.assert_equals(200, first.status_int)


  def test_hub(self):
    self.expect_requests_get('http://my/posts.html', HTML % {
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


  def test_bad_mf2_json_input_400s(self):
    """If a user sends JSON Feed input, but claims it's mf2 JSON, return 400.

    https://console.cloud.google.com/errors/COyl7MTulffpuAE
    """
    self.expect_requests_get('http://some/jf2', {
      'data': {
        'type': 'feed',
        'items': [{
          'type': 'entry',
          'published': '2018-05-24T08:58:44+02:00',
          'url': 'https://realize.be/notes/1463',
          'content': {
            'text': 'foo',
            'html': '<p>bar</p>',
        },
      }],
    }})
    self.mox.ReplayAll()
    resp = app.application.get_response('/url?url=http://some/jf2&input=mf2-json')
    self.assert_equals(400, resp.status_int)

