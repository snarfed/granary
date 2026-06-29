"""Unit tests for app.py."""
import copy
from io import BytesIO
import os.path
import socket
import urllib.parse
from urllib.parse import quote

from granary import as2
from granary.tests import test_bluesky, test_instagram, test_nostr
from webutil import testutil, util
from webutil.testutil import requests_response
from webutil.util import json_dumps, json_loads
import requests

from app import app

client = app.test_client()

AS1 = [{
  'objectType': 'activity',
  'verb': 'post',
  'object': {
    'content': 'foo ☕ bar',
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
  '@context': as2.CONTEXT,
  'type': 'Create',
  'object': {
    'content': 'foo ☕ bar',
    'published': '2012-03-04T18:20:37+00:00',
    'url': 'https://perma/link',
  }
}, {
  '@context': as2.CONTEXT,
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
    'content': ['foo ☕ bar'],
    'published': ['2012-03-04T18:20:37+00:00'],
    'url': ['https://perma/link'],
  },
}, {
  'type': ['h-entry'],
  'properties': {
    'content': ['baz baj'],
  },
}]}

JSONFEED = {
  'version': 'https://jsonfeed.org/version/1.1',
  'title': 'JSON Feed',
  'items': [{
    'url': 'https://perma/link',
    'id': 'https://perma/link',
    'content_html': 'foo ☕ bar',
    'date_published': '2012-03-04T18:20:37+00:00',
  }, {
    'content_html': 'baz baj',
  }],
}

HTML = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body class="%(body_class)s">%(extra)s
<article class="h-entry">
  <span class="p-uid"></span>

  <time class="dt-published" datetime="2012-03-04T18:20:37+00:00">2012-03-04T18:20:37+00:00</time>

  <a class="u-url" href="https://perma/link">perma/link</a>
  <div class="e-content p-name">
foo ☕ bar
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
  <title>foo ☕ bar</title>

  <content type="html"><![CDATA[

foo ☕ bar

  ]]></content>

  <link rel="alternate" type="text/html" href="https://perma/link" />
  <link rel="ostatus:conversation" href="https://perma/link" />
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>

  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T18:20:37+00:00</updated>

  <link rel="self" href="https://perma/link" />

</entry>
"""


RSS_CONTENT = util.read(os.path.join(
  os.path.dirname(__file__), 'granary/tests/testdata/feed_with_note.rss.xml'))
RSS_ACTIVITIES = json_loads(util.read(os.path.join(
  os.path.dirname(__file__), 'granary/tests/testdata/feed_with_note.as-from-rss.json')))


class AppTest(testutil.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_get = self.start_patch(util.session, 'get')

  def test_front_page_farcaster(self):
    resp = client.get('/?site=farcaster')
    self.assert_equals(200, resp.status_code)
    self.assertIn('farcaster', resp.get_data(as_text=True))

  def test_front_page_mastodon_pixelfed_without_auth_entity(self):
    for site in 'mastodon', 'pixelfed':
      with self.subTest(site=site):
        resp = client.get(f'/?site={site}')
        self.assert_equals(400, resp.status_code)

  def test_url_as1_to_mf2_json(self):
    self.mock_get.return_value = requests_response(AS1)

    resp = client.get('/url?url=http://my/posts.json&input=as1&output=mf2-json')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/mf2+json', resp.headers['Content-Type'])
    self.assert_equals(MF2, resp.json)

  def test_url_as1_to_as2(self):
    self.mock_get.return_value = requests_response(AS1)

    resp = client.get('/url?url=http://my/posts.json&input=as1&output=as2')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/activity+json', resp.headers['Content-Type'])
    self.assert_equals(AS2_RESPONSE, resp.json)

  def test_url_as1_response_to_as2(self):
    self.mock_get.return_value = requests_response(AS1_RESPONSE)

    resp = client.get('/url?url=http://my/posts.json&input=as1&output=as2')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/activity+json',
                       resp.headers['Content-Type'])
    self.assert_equals(AS2_RESPONSE, resp.json)

  def test_url_as2_to_as1(self):
    self.mock_get.return_value = requests_response(AS2)

    resp = client.get('/url?url=http://my/posts.json&input=as2&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(AS1_RESPONSE, resp.json)

  def test_url_as2_response_to_as1(self):
    self.mock_get.return_value = requests_response(AS2_RESPONSE)

    resp = client.get('/url?url=http://my/posts.json&input=as2&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(AS1_RESPONSE, resp.json)

  def test_url_as1_to_jsonfeed(self):
    self.mock_get.return_value = requests_response(AS1)

    path = '/url?url=http://my/posts.json&input=as1&output=jsonfeed'
    resp = client.get(path)
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/feed+json', resp.headers['Content-Type'])

    expected = copy.deepcopy(JSONFEED)
    expected['feed_url'] = 'http://localhost' + path
    self.assert_equals(expected, resp.json)

  def test_url_as1_to_jsonfeed_not_list(self):
    self.mock_get.return_value = requests_response({'foo': 'bar'})

    path = '/url?url=http://my/posts.json&input=as1&output=jsonfeed'
    resp = client.get(path)
    self.assert_equals(200, resp.status_code)
    self.assert_equals({
      'feed_url': f'http://localhost{path}',
      'items': [{'content_text': ''}],
      'title': 'JSON Feed',
      'version': 'https://jsonfeed.org/version/1.1',
    }, resp.json)

  def test_url_jsonfeed_to_json_mf2(self):
    self.mock_get.return_value = requests_response(JSONFEED)

    path = '/url?url=http://my/feed.json&input=jsonfeed&output=json-mf2'
    resp = client.get(path)
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/mf2+json', resp.headers['Content-Type'])

    expected = copy.deepcopy(MF2)
    expected['items'][0]['properties']['uid'] = [JSONFEED['items'][0]['id']]
    self.assert_equals(expected, resp.json)

  def test_url_bad_jsonfeed(self):
    self.mock_get.return_value = requests_response(['not', 'jsonfeed'],
                                                   url='http://my/feed.json')

    path = '/url?url=http://my/feed.json&input=jsonfeed&output=json-mf2'
    resp = client.get(path)
    self.assert_equals(400, resp.status_code)
    self.assertIn('Could not parse http://my/feed.json as jsonfeed',
                  resp.get_data(as_text=True))

  def test_url_json_mf2_to_html(self):
    self.mock_get.return_value = requests_response(MF2)

    resp = client.get('/url?url=http://my/posts.json&input=json-mf2&output=html')
    self.assert_equals(200, resp.status_code)
    self.assert_multiline_equals(HTML % {
      'body_class': '',
      'extra': '',
    }, resp.get_data(as_text=True), ignore_blanks=True)

  def test_url_html_to_as1(self):
    html = HTML % {'body_class': 'h-feed', 'extra': ''}
    self.mock_get.return_value = requests_response(html)

    resp = client.get('/url?url=http://my/posts.html&input=html')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/json', resp.headers['Content-Type'])

    self.assert_equals([{
      'objectType': 'activity',
      'verb': 'post',
      'object': {
        'objectType': 'note',
        'displayName': 'foo ☕ bar',
        'content': 'foo ☕ bar',
        'content_is_html': True,
        'published': '2012-03-04T18:20:37+00:00',
        'url': 'https://perma/link',
      }
    }, {
      'objectType': 'activity',
      'verb': 'post',
      'object': {
        'objectType': 'note',
        'displayName': 'baz baj',
        'content': 'baz baj',
        'content_is_html': True,
      },
    }], resp.json['items'])

  def test_url_html_to_atom(self):
    self.mock_get.return_value = requests_response(HTML % {
      'body_class': 'h-feed',
      'extra': """
<span>my title</span>
<div class="p-author h-card">
  <a href="http://my/site">My Name</a>
  <img src="http://my/picture" />
</div>
""",
    }, url='http://my/posts.html', headers={'Content-Length': '123'})

    resp = client.get('/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_code)
    self.assert_multiline_in(ATOM_CONTENT, resp.get_data(as_text=True),
                             ignore_blanks=True)

  def test_url_html_to_atom_rel_author(self):
    """
    https://github.com/snarfed/granary/issues/98
    https://github.com/kylewm/mf2util/issues/14
    """
    self.mock_get.side_effect = [
      requests_response(HTML % {
        'body_class': 'h-feed',
        'extra': """
<span class="p-name">my title</span>
<a href="/author" rel="author"></a>,
""",
      }, url='http://my/posts.html'),
      requests_response("""
<div class="h-card">
  <a class="u-url" href="http://my/author">Someone Else</a>
  <img class="u-photo" src="http://someone/picture" />
</div>
""", url='http://my/author'),
    ]

    resp = client.get('/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_code)
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
""", resp.get_data(as_text=True), ignore_blanks=True)

  def test_url_html_to_atom_skip_silo_rel_authors(self):
    self.mock_get.return_value = requests_response(HTML % {
      'body_class': 'h-feed',
      'extra': """
<span class="p-name">my title</span>
<a href="https://twitter.com/Author" rel="author"></a>,
""",
    }, url='http://my/posts.html')

    resp = client.get('/url?url=http://my/posts.html&input=html&output=atom')
    self.assert_equals(200, resp.status_code)
    self.assert_multiline_in("""
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://twitter.com/Author</uri>
</author>

<link rel="alternate" href="http://my/posts.html" type="text/html" />
<link rel="alternate" href="https://twitter.com/Author" type="text/html" />
<link rel="self" href="http://localhost/url?url=http://my/posts.html&amp;input=html&amp;output=atom" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>https://twitter.com/Author</uri>
</author>
""", resp.get_data(as_text=True), ignore_blanks=True)

  def test_url_html_to_json_mf2(self):
    html = HTML % {'body_class': 'h-feed', 'extra': ''}
    self.mock_get.return_value = requests_response(html)

    resp = client.get('/url?url=http://my/posts.html&input=html&output=json-mf2')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/mf2+json', resp.headers['Content-Type'])

    expected = copy.deepcopy(MF2)
    for obj in expected['items']:
      obj['properties']['name'] = [obj['properties']['content'][0].strip()]
    self.assert_equals(expected, resp.json)

  def test_url_html_to_html(self):
    html = HTML % {'body_class': 'h-feed', 'extra': ''}
    self.mock_get.return_value = requests_response(html)

    resp = client.get('/url?url=http://my/posts.html&input=html&output=html')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('text/html; charset=utf-8', resp.headers['Content-Type'])

    self.assert_multiline_in("""\
<time class="dt-published" datetime="2012-03-04T18:20:37+00:00">2012-03-04T18:20:37+00:00</time>
<a class="p-name u-url" href="https://perma/link">foo ☕ bar</a>
<div class="e-content">
foo ☕ bar
</div>
""", resp.get_data(as_text=True), ignore_blanks=True)
    self.assert_multiline_in("""\
<span class="p-name">baz baj</span>
<div class="e-content">
baz baj
</div>
""", resp.get_data(as_text=True), ignore_blanks=True)

  def test_url_html_meta_charset(self):
    html = HTML % {'body_class': 'h-feed', 'extra': ''}
    resp = requests_response(html)
    resp.encoding = 'ISO-8859-1'
    self.mock_get.return_value = resp

    resp = client.get('/url?url=http://my/posts.html&input=html&output=html')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('text/html; charset=utf-8', resp.headers['Content-Type'])

    self.assert_multiline_in("""\
<time class="dt-published" datetime="2012-03-04T18:20:37+00:00">2012-03-04T18:20:37+00:00</time>
<a class="p-name u-url" href="https://perma/link">foo ☕ bar</a>
<div class="e-content">
foo ☕ bar
</div>
""", resp.get_data(as_text=True), ignore_blanks=True)
    self.assert_multiline_in("""\
<span class="p-name">baz baj</span>
<div class="e-content">
baz baj
</div>
""", resp.get_data(as_text=True), ignore_blanks=True)

  def test_url_html_fragment(self):
    self.mock_get.return_value = requests_response("""
<div id="abc" class="h-entry"></div>
<div class="h-entry"></div>
<div id="def" class="h-entry"><div class="e-content">foo</div></div>
""")

    resp = client.get('/url?url=http://my/posts.html%23def&input=html&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals([{
      'objectType': 'activity',
      'verb': 'post',
      'object': {
        'objectType': 'note',
        'content': 'foo',
        'content_is_html': True,
      },
    }], resp.json['items'])

  def test_url_html_fragment_not_found(self):
    self.mock_get.return_value = requests_response("""
<div id="abc" class="h-entry"></div>
<div id="def" class="h-entry"><div class="e-content">foo</div></div>
<div class="h-entry"></div>
""")

    resp = client.get('/url?url=http://my/posts.html%23xyz&input=html&output=as1')
    self.assert_equals(400, resp.status_code)
    self.assertIn('Got fragment xyz but no element found with that id.',
                  resp.get_data(as_text=True))

  def test_url_fragment_not_html(self):
    resp = client.get('/url?url=http://my/posts.json%23xyz&input=as2')
    self.assert_equals(400, resp.status_code)
    self.assertIn('URL fragments only supported with input=html.',
                  resp.get_data(as_text=True))

  def test_url_atom_to_as1(self):
    self.mock_get.return_value = requests_response(ATOM_CONTENT + '</feed>\n')

    resp = client.get('/url?url=http://feed&input=atom&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals({
      'items': [{
        'id': 'https://perma/link',
        'url': 'https://perma/link',
        'objectType': 'activity',
        'verb': 'post',
        'actor': {
          'objectType': 'person',
          'displayName': 'My Name',
          'url': 'http://my/site',
        },
        'title': 'foo ☕ bar',
        'object': {
          'id': 'https://perma/link',
          'url': 'https://perma/link',
          'objectType': 'note',
          'author': {
            'objectType': 'person',
            'displayName': 'My Name',
            'url': 'http://my/site',
          },
          'displayName': 'foo ☕ bar',
          'content': 'foo ☕ bar',
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
    }, resp.json)

  def test_url_atom_to_as1_parse_error(self):
    self.mock_get.return_value = requests_response('not valid xml', url='http://feed')

    resp = client.get('/url?url=http://feed&input=atom&output=as1')
    self.assert_equals(400, resp.status_code)
    self.assertIn('Could not parse http://feed as atom: ',
                  resp.get_data(as_text=True))

  def test_url_atom_to_as1_not_atom(self):
    self.mock_get.return_value = requests_response("""\
<?xml version="1.0" encoding="UTF-8"?>
<rss>
not atom!
</rss>""", url='http://feed')

    resp = client.get('/url?url=http://feed&input=atom&output=as1')
    self.assert_equals(400, resp.status_code)
    self.assertIn('Could not parse http://feed as atom: ',
                  resp.get_data(as_text=True))

  def test_url_rss_to_as1(self):
    self.mock_get.return_value = requests_response(RSS_CONTENT)

    resp = client.get('/url?url=http://feed&input=rss&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(RSS_ACTIVITIES, [a['object'] for a in resp.json['items']])

  def test_url_rss_to_as1_parse_error(self):
    """feedparser.parse returns empty on bad input RSS."""
    self.mock_get.return_value = requests_response('not valid xml')

    resp = client.get('/url?url=http://feed&input=rss&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals([], resp.json['items'])

  def test_url_rss_to_as1_not_rss(self):
    """feedparser.parse returns empty on bad input RSS."""
    self.mock_get.return_value = requests_response("""\
<?xml version="1.0" encoding="UTF-8"?>
<atom>
not RSS!
</atom>""")

    resp = client.get('/url?url=http://feed&input=rss&output=as1')
    self.assert_equals(200, resp.status_code)
    self.assert_equals([], resp.json['items'])

  def test_url_as1_to_atom_reader_false(self):
    """reader=false should omit location in Atom output.

    https://github.com/snarfed/granary/issues/104
    """
    activity = copy.deepcopy(AS1[0])
    activity['object']['location'] = {
      'displayName': 'My place',
      'url': 'http://my/place',
    }
    self.mock_get.return_value = requests_response([activity])

    resp = client.get('/url?url=http://my/posts.as&input=as1&output=atom&reader=false')
    self.assert_equals(200, resp.status_code, resp.get_data(as_text=True))
    self.assertNotIn('p-location', resp.get_data(as_text=True))
    self.assertNotIn('<a class="p-name u-url" href="http://my/place">My place</a>',
                     resp.get_data(as_text=True))

  def test_url_as1_to_atom_if_missing_actor_use_hfeed(self):
    mf2 = {'items': [{
      'type': ['h-feed'],
      'properties': {
        'name': ['2toPonder'],
        'summary': ['A Two Minute Podcast on Trends of Learning'],
        'photo': ['https://foo/art.jpg'],
      },
      # no children
    }]}
    self.mock_get.return_value = requests_response(mf2)

    resp = client.get('/url?url=http://my/posts&input=json-mf2&output=atom')
    self.assert_equals(200, resp.status_code, resp.get_data(as_text=True))
    self.assertIn('<title>2toPonder</title>', resp.get_data(as_text=True))
    self.assertIn('<logo>https://foo/art.jpg</logo>', resp.get_data(as_text=True))

  def test_url_as1_to_bluesky(self):
    self.mock_get.return_value = requests_response([
      test_bluesky.POST_AS,
      test_bluesky.REPLY_AS,
    ])

    resp = client.get('/url?url=http://my/posts&input=as1&output=bluesky')
    self.assert_equals(200, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals({
      'feed': [
        test_bluesky.POST_BSKY,
        test_bluesky.REPLY_BSKY_NO_CIDS,
      ],
    }, resp.json, ignore=['fooOriginalUrl', 'fooOriginalText'])

  def test_url_as1_to_nostr(self):
    self.mock_get.return_value = requests_response([test_nostr.NOTE_AS1])

    resp = client.get('/url?url=http://my/posts&input=as1&output=nostr')
    self.assert_equals(200, resp.status_code, resp.get_data(as_text=True))

    expected = {
      **test_nostr.NOTE_NOSTR,
      'tags': [],
    }
    del expected['sig']
    self.assert_equals({'items': [expected]}, resp.json)

  def test_url_as1_to_farcaster(self):
    note = {
      'objectType': 'note',
      'author': 'farcaster://123',
      'content': 'Hello Farcaster!',
      'published': '2021-12-20T11:33:20+00:00',
    }
    self.mock_get.return_value = requests_response([note])

    resp = client.get('/url?url=http://my/note&input=as1&output=farcaster')
    self.assert_equals(200, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals({
      'items': [{
        'data': {
          'castAddBody': {'text': 'Hello Farcaster!'},
          'fid': '123',
          'network': 'FARCASTER_NETWORK_MAINNET',
          'timestamp': 1640000000,
          'type': 'MESSAGE_TYPE_CAST_ADD',
        },
        'dataBytes': 'CAEQexiA1IGOBiABKhIiEEhlbGxvIEZhcmNhc3RlciE=',
        'hash': 'xyT+Siarn7gjw6jIKIcXmhC4hGo=',
        'hashScheme': 'HASH_SCHEME_BLAKE3',
      }],
    }, resp.json)

  def test_url_nostr_to_as1(self):
    self.mock_get.return_value = requests_response(test_nostr.NOTE_NOSTR)

    resp = client.get('/url?url=http://nostr/posts&input=nostr&output=as1')
    self.assert_equals(200, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals([test_nostr.NOTE_AS1], resp.json['items'])

  def test_url_bad_input(self):
    resp = client.get('/url?url=http://my/posts.json&input=foo')
    self.assert_equals(400, resp.status_code)

  def test_url_input_not_json(self):
    self.mock_get.return_value = requests_response('<html><body>not JSON</body></html>')

    for input in 'as1', 'as2', 'activitystreams', 'json-mf2', 'jsonfeed':
      resp = client.get(f'/url?url=http://my/posts&input={input}')
      self.assert_equals(400, resp.status_code)

  def test_url_json_input_not_dict(self):
    self.mock_get.return_value = requests_response('[1, 2]')

    for input in 'as2', 'json-mf2', 'jsonfeed':
      resp = client.get(f'/url?url=http://my/posts&input={input}')
      self.assert_equals(400, resp.status_code)

    resp = client.get('/url?url=http://my/posts&input=as1&output=as2')
    self.assert_equals(400, resp.status_code)

  def _test_bad_url(self, url, err):
    self.mock_get.side_effect = err
    resp = client.get(f'/url?url={url}&input=html')
    self.assert_equals(400, resp.status_code, resp.get_data(as_text=True))

  def test_url_bad_url_backslash(self):
    self._test_bad_url('http://astralandopal.com\\',
                       requests.exceptions.MissingSchema('foo'))

  def test_url_bad_url_invalid(self):
    self._test_bad_url("-2093%25'%20UNION%20ALL%20SELECT%2015%2C15%2C15%2C15",
                       requests.exceptions.InvalidURL('foo'))

  def test_url_bad_url_invalid_brackets(self):
    url = 'http://[DOMAIN]/'
    # Python 3.11+ rejects invalid IPv6 brackets when parsing the URL; older
    # versions don't, so the bad URL instead fails when we try to fetch it.
    try:
      urllib.parse.urlparse(url)
    except ValueError:
      expected = 'Invalid url'
    else:
      self.mock_get.side_effect = requests.exceptions.InvalidURL('foo')
      expected = 'Bad URL'
    resp = client.get(f'/url?url={url}&input=html&output=atom')
    self.assert_equals(400, resp.status_code)
    self.assertIn(expected, resp.get_data(as_text=True))

  def test_url_fetch_fails(self):
    self.mock_get.side_effect = socket.timeout('')
    resp = client.get('/url?url=http://my/posts.html&input=html')
    self.assert_equals(504, resp.status_code)

  def test_url_response_too_big(self):
    self.mock_get.return_value = requests_response(
      '', headers={'Content-Length': str(util.MAX_HTTP_RESPONSE_SIZE + 1)})
    resp = client.get('/url?url=http://my/posts.html&input=html')
    self.assert_equals(util.HTTP_RESPONSE_TOO_BIG_STATUS_CODE, resp.status_code)

  def test_url_404(self):
    self.mock_get.return_value = requests_response('foo', status=404)
    resp = client.get('/url?url=http://my/posts.html&input=html')
    self.assert_equals(502, resp.status_code)

  def test_hub(self):
    self.mock_get.return_value = requests_response(HTML % {
      'body_class': '',
      'extra': '',
    })

    url = '/url?url=http://my/posts.html&input=html&output=atom&hub=http://a/hub'
    resp = client.get(url)

    self_url = 'http://localhost' + url
    self.assert_equals(200, resp.status_code)
    self.assert_multiline_in('<link rel="hub" href="http://a/hub" />',
                             resp.get_data(as_text=True))
    self.assert_multiline_in(
      '<link rel="self" href="http://localhost/url?url=http://my/posts.html&amp;input=html&amp;output=atom&amp;hub=http://a/hub"',
      resp.get_data(as_text=True))

    self.assertCountEqual((
      '<http://a/hub>; rel="hub"',
      '<http://localhost/url?url=http://my/posts.html&input=html&output=atom&hub=http://a/hub>; rel="self"',
    ), resp.headers.getlist('Link'))

  def test_encode_urls_in_link_headers(self):
    self.mock_get.return_value = requests_response(AS1)

    url = '/url?url=http://my/as1&input=as1&output=atom&hub=http://a/%E2%98%95'
    resp = client.get(url)
    self.assertCountEqual(
      ('<http://a/%E2%98%95>; rel="hub"',
       '<http://localhost/url?url=http://my/as1&input=as1&output=atom&hub=http://a/%E2%98%95>; rel="self"'),
      resp.headers.getlist('Link'))

  def test_bad_mf2_json_input_400s(self):
    """If a user sends JSON Feed input, but claims it's mf2 JSON, return 400.

    https://console.cloud.google.com/errors/COyl7MTulffpuAE
    """
    self.mock_get.return_value = requests_response({
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
    resp = client.get('/url?url=http://some/jf2&input=mf2-json')
    self.assert_equals(400, resp.status_code)

  def test_url_head(self):
    self.mock_get.return_value = requests_response(AS1)

    resp = client.head('/url?url=http://my/posts.json&input=as1&output=mf2-json')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/mf2+json', resp.headers['Content-Type'])
    self.assert_equals('', resp.get_data(as_text=True))

  def test_url_head_bad_output(self):
    self.mock_get.return_value = requests_response(AS1)

    resp = client.head('/url?url=http://my/posts.json&input=as1&output=foo')
    self.assert_equals(400, resp.status_code)
    self.assert_equals('', resp.get_data(as_text=True))

  def test_scraped_no_content_type(self):
    resp = client.post('/scraped', data={
      'site': 'instagram',
      'input': (BytesIO('{}'.encode()), 'file'),
    })
    self.assert_equals(400, resp.status_code)

  def test_scraped_bad_content_type(self):
    resp = client.post('/scraped?site=instagram&output=as1',
                       data=test_instagram.HTML_FEED_COMPLETE_V2,
                       content_type='application/pdf')
    self.assert_equals(400, resp.status_code)

  def test_scraped_html_instagram_no_file_input(self):
    resp = client.post('/scraped?site=instagram&output=as1')
    self.assert_equals(400, resp.status_code)

  def test_scraped_html_instagram_to_as1_raw_body(self):
    expected = copy.deepcopy(AS1_RESPONSE)
    expected['items'] = test_instagram.HTML_ACTIVITIES_FULL_V2

    resp = client.post('/scraped?site=instagram&output=as1',
                       data=test_instagram.HTML_FEED_COMPLETE_V2,
                       content_type='text/html')
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(expected, resp.json)

  def test_scraped_html_instagram_to_as1_form_encoded(self):
    expected = copy.deepcopy(AS1_RESPONSE)
    expected['items'] = test_instagram.HTML_ACTIVITIES_FULL_V2

    html_file = BytesIO(test_instagram.HTML_FEED_COMPLETE_V2.encode())

    resp = client.post('/scraped', data={
      'site': 'instagram',
      'input': (html_file, 'file.html'),
      'output': 'as1',
    })
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(expected, resp.json)

  def test_scraped_json_instagram_to_as1_raw_body(self):
    expected = copy.deepcopy(AS1_RESPONSE)
    expected['items'] = test_instagram.HTML_ACTIVITIES

    resp = client.post('/scraped?site=instagram&output=as1',
                       json=test_instagram.HTML_PROFILE_JSON)
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/stream+json', resp.headers['Content-Type'])
    self.assert_equals(expected, resp.json)

  def test_scraped_json_instagram_to_as1_form_encoded(self):
    expected = copy.deepcopy(AS1_RESPONSE)
    expected['items'] = test_instagram.HTML_ACTIVITIES

    html_file = BytesIO(json_dumps(test_instagram.HTML_PROFILE_JSON).encode())
    resp = client.post('/scraped', data={
      'site': 'instagram',
      'input': (html_file, 'file.json'),
    })
    self.assert_equals(200, resp.status_code)
    self.assert_equals('application/json', resp.headers['Content-Type'])
    self.assert_equals(expected, resp.json)

  def test_demo(self):
    resp = client.get('/demo?site=sayt&user_id=me&group_id=@groop&activity_id=123')
    self.assert_equals(302, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals('/sayt/me/@groop/@app/123?site=sayt&user_id=me&group_id=%40groop&activity_id=123&plaintext=true&cache=false&search_query=',
                       resp.headers['Location'])

  def test_demo_search(self):
    resp = client.get('/demo?site=sayt&user_id=me&group_id=@search&search_query=foo')
    self.assert_equals(302, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals('/sayt/me/@search/@app/?site=sayt&user_id=me&group_id=%40search&search_query=foo&plaintext=true&cache=false',
                       resp.headers['Location'])

  def test_demo_list(self):
    resp = client.get('/demo?site=sayt&user_id=me&group_id=@list&list=ly%E2%98%95zt')
    self.assert_equals(302, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals('/sayt/me/ly%E2%98%95zt/@app/?site=sayt&user_id=me&group_id=%40list&list=ly%E2%98%95zt&plaintext=true&cache=false&search_query=',
                       resp.headers['Location'])

  def test_demo_non_ascii_params(self):
    # %E2%98%95 is ☕
    resp = client.get(
      '/demo?site=%E2%98%95&user_id=%E2%98%95&group_id=%E2%98%95&activity_id=%E2%98%95&search_query=%E2%98%95&format=%E2%98%95')
    self.assert_equals(302, resp.status_code, resp.get_data(as_text=True))
    self.assert_equals('/%E2%98%95/%E2%98%95/%E2%98%95/@app/%E2%98%95?site=%E2%98%95&user_id=%E2%98%95&group_id=%E2%98%95&activity_id=%E2%98%95&search_query=&format=%E2%98%95&plaintext=true&cache=false',
                       resp.headers['Location'])
