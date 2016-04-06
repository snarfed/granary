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

<link href="http://my/site" rel="alternate" type="text/html" />
<link rel="avatar" href="http://my/picture" />
<link href="http://localhost/url" rel="self" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri></uri>
 <name></name>
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

  <activity:verb>http://activitystrea.ms/schema/1.0/</activity:verb>
  <published>2012-03-04T18:20:37+00:00</published>
  <updated>2012-03-04T18:20:37+00:00</updated>

  <link rel="self" type="application/atom+xml" href="https://perma/link" />
</entry>
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
