# coding=utf-8
"""Unit tests for atom.py."""

import copy

import mox
from oauth_dropins.webutil import testutil
import requests

from granary import atom

import test_facebook
import test_instagram
import test_twitter

INSTAGRAM_ATOM_ENTRY = u"""\
<?xml version="1.0" encoding="UTF-8"?>
<entry xml:lang="en-US"
       xmlns="http://www.w3.org/2005/Atom"
       xmlns:activity="http://activitystrea.ms/spec/1.0/"
       xmlns:georss="http://www.georss.org/georss"
       xmlns:ostatus="http://ostatus.org/schema/1.0"
       xmlns:thr="http://purl.org/syndication/thread/1.0"
       >
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://snarfed.org</uri>
 <name>Ryan B</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/photo</activity:object-type>
  <id>https://www.instagram.com/p/ABC123/</id>
  <title>this picture -&gt; is #abc @foo #xyz</title>
  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">
this picture -&gt; is #abc <a href="https://www.instagram.com/foo/">@foo</a> #xyz
<p>
<a class="link" href="https://www.instagram.com/p/ABC123/">
<img class="thumbnail" src="http://attach/image/big" alt="" />
</a>
</p>
<p>  <span class="p-location h-card">
  <data class="p-uid" value="tag:instagram.com:520640"></data>
  <a class="p-name u-url" href="https://instagram.com/explore/locations/520640/">Le Truc</a>
</span>
</p>
  </div>
  </content>

  <link rel="alternate" type="text/html" href="https://www.instagram.com/p/ABC123/" />
  <link rel="ostatus:conversation" href="https://www.instagram.com/p/ABC123/" />
    <link rel="ostatus:attention" href="http://snarfed.org" />
    <link rel="mentioned" href="http://snarfed.org" />
    <a href="http://snarfed.org">Ryan B</a>
  <link rel="ostatus:attention" href="https://www.instagram.com/foo/" />
  <link rel="mentioned" href="https://www.instagram.com/foo/" />
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>
  <published>2012-09-22T05:25:42</published>
  <updated>2012-09-22T05:25:42</updated>
  <georss:point>37.3 -122.5</georss:point>
  <georss:featureName>Le Truc</georss:featureName>
  <link rel="self" type="application/atom+xml" href="https://www.instagram.com/p/ABC123/" />
</entry>
"""


class AtomTest(testutil.HandlerTest):

  def test_activities_to_atom(self):
    for test_module in test_facebook, test_instagram, test_twitter:
      request_url = 'http://request/url?access_token=foo'
      host_url = 'http://host/url'
      base_url = 'http://base/url'
      self.assert_multiline_equals(
        test_module.ATOM % {
          'request_url': request_url,
          'host_url': host_url,
          'base_url': base_url,
        },
        atom.activities_to_atom(
          [copy.deepcopy(test_module.ACTIVITY)],
          test_module.ACTOR,
          request_url=request_url,
          host_url=host_url,
          xml_base=base_url
        ),
        ignore_blanks=True)

  def test_activity_to_atom(self):
    self.assert_multiline_equals(
      INSTAGRAM_ATOM_ENTRY,
      atom.activity_to_atom(copy.deepcopy(test_instagram.ACTIVITY)),
      ignore_blanks=True)

  def test_atom_to_activity(self):
    expected = {
      'objectType': 'activity',
      'verb': 'post',
      'id': 'https://www.instagram.com/p/ABC123/',
      'actor': {
        'displayName': 'Ryan B',
        'objectType': 'person',
        'url': 'http://snarfed.org',
      },
      'object': {
        'id': 'https://www.instagram.com/p/ABC123/',
        'objectType': 'photo',
        'title': 'this picture -> is #abc @foo #xyz',
        'content': 'this picture -> is #abc @foo #xyz Le Truc',
        'published': '2012-09-22T05:25:42',
        'updated': '2012-09-22T05:25:42',
        'location': {
          'displayName': 'Le Truc',
          'latitude': 37.3,
          'longitude': -122.5,
          'position': '+37.300000-122.500000/',
        },
      },
    }
    self.assert_equals(expected, atom.atom_to_activity(INSTAGRAM_ATOM_ENTRY))

  def test_atom_to_activity_like(self):
    for atom_obj, as_obj in (
        ('foo', {'id': 'foo', 'url': 'foo'}),
        ('<id>foo</id>', {'id': 'foo'}),
        ('<uri>foo</uri>', {'id': 'foo', 'url': 'foo'}),
      ):
      self.assert_equals({
        'url': 'like-url',
        'objectType': 'activity',
        'verb': 'like',
        'object': as_obj,
      }, atom.atom_to_activity(u"""\
<?xml version="1.0" encoding="UTF-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:activity="http://activitystrea.ms/spec/1.0/">
<uri>like-url</uri>
<activity:verb>http://activitystrea.ms/schema/1.0/like</activity:verb>
<activity:object>%s</activity:object>
</entry>
""" % atom_obj))

  def test_activity_to_atom_like(self):
    for obj in {'id': 'foo', 'url': 'foo'}, {'id': 'foo'}, {'url': 'foo'}:
      self.assert_multiline_in("""\
<activity:verb>http://activitystrea.ms/schema/1.0/like</activity:verb>
<activity:object>foo</activity:object>
""", atom.activity_to_atom({
        'url': 'like-url',
        'objectType': 'activity',
        'verb': 'like',
        'object': obj,
      }), ignore_blanks=True)

  def test_atom_to_activity_reply(self):
    expected = {
      'objectType': 'activity',
      'id': 'reply-url',
      'url': 'reply-url',
      'inReplyTo': [{'id': 'foo-id', 'url': 'foo-url'}],
      'object': {
        'id': 'reply-url',
        'url': 'reply-url',
        'content': u'I hereby ☕ reply.',
        'inReplyTo': [{'id': 'foo-id', 'url': 'foo-url'}],
      },
    }
    self.assert_equals(expected, atom.atom_to_activity(u"""\
<?xml version="1.0" encoding="UTF-8"?>
<entry xmlns="http://www.w3.org/2005/Atom"
       xmlns:thr="http://purl.org/syndication/thread/1.0">
<uri>reply-url</uri>
<thr:in-reply-to ref="foo-id" href="foo-url" />
<content>I hereby ☕ reply.</content>
</entry>
"""))

  def test_atom_to_activity_in_reply_to_text(self):
    expected = {
      'objectType': 'activity',
      'inReplyTo': [{'id': 'my-inreplyto', 'url': 'my-inreplyto'}],
      'object': {
        'inReplyTo': [{'id': 'my-inreplyto', 'url': 'my-inreplyto'}],
      },
    }
    self.assert_equals(expected, atom.atom_to_activity(u"""\
<?xml version="1.0" encoding="UTF-8"?>
<entry xmlns:thr="http://purl.org/syndication/thread/1.0">
<thr:in-reply-to>my-inreplyto</thr:in-reply-to>
</entry>
"""))

  def test_title(self):
    self.assert_multiline_in(
      '\n<title>my title</title>',
      atom.activities_to_atom([copy.deepcopy(test_facebook.ACTIVITY)],
                              test_facebook.ACTOR, title='my title'))

  def test_strip_html_tags_from_titles(self):
    activity = copy.deepcopy(test_facebook.ACTIVITY)
    activity['displayName'] = '<p>foo &amp; <a href="http://bar">bar</a></p>'
    self.assert_multiline_in(
      '<title>foo &amp; bar</title>\n',
      atom.activities_to_atom([activity], test_facebook.ACTOR))

  def test_render_content_as_html(self):
    self.assert_multiline_in(
      '<a href="https://twitter.com/foo">@twitter</a> meets @seepicturely at <a href="https://twitter.com/search?q=%23tcdisrupt">#tcdisrupt</a> &lt;3 <a href="http://first/link/">first</a> <a href="http://instagr.am/p/MuW67/">instagr.am/p/MuW67</a> ',
      atom.activities_to_atom([copy.deepcopy(test_twitter.ACTIVITY)],
                              test_twitter.ACTOR, title='my title'))

  def test_render_with_images(self):
    """Attached images are rendered inline as HTML."""
    activity = copy.deepcopy(test_instagram.ACTIVITY)
    activity['object']['attachments'].append(
      {'objectType': 'image', 'image': {'url': 'http://image/2'}})

    got = atom.activities_to_atom([activity],test_instagram.ACTOR, title='')
    self.assert_multiline_in(
      '<img class="thumbnail" src="http://attach/image/big"', got)
    self.assert_multiline_in(
      '<img class="thumbnail" src="http://image/2"', got)

  def test_render_untitled_image(self):
    """Images should be included even if there is no other content
    """
    activity = copy.deepcopy(test_instagram.ACTIVITY)
    del activity['object']['content']
    self.assert_multiline_in(
      '<img class="thumbnail" src="http://attach/image/big"',
      atom.activities_to_atom([activity], test_instagram.ACTOR,
                              title='my title'))

  def test_render_share(self):
    activity = {
      'verb': 'share',
      'content': "sharer's comment",
      'object': {
        'content': 'original object',
        'author': {'displayName': 'Mr. Foo'},
      },
    }

    out = atom.activities_to_atom([activity], {})
    self.assert_multiline_in("""
<title>sharer's comment</title>
""", out)
    self.assert_multiline_in("""
sharer's comment
""", out)
    self.assertNotIn('original object', out)

  def test_render_share_no_content(self):
    activity = {
      'verb': 'share',
      'object': {
        'content': 'original object',
        'author': {'displayName': 'Mr. Foo'},
      },
    }

    out = atom.activities_to_atom([activity], {})
    self.assert_multiline_in("""
Shared <a href="#">a post</a> by   <span class="h-card">

<span class="p-name">Mr. Foo</span>

</span>
original object
""", out)

  def test_render_share_of_obj_with_attachments(self):
    """This is e.g. a retweet of a quote tweet."""
    activity = {
      'verb': 'share',
      'object': {
        'content': 'RT @quoter: comment',
        'attachments': [{
          'objectType': 'note',
          'content': 'quoted text',
        }],
      },
    }

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assert_multiline_in("""
RT @quoter: comment

<blockquote>
quoted text
</blockquote>
""", out)

  def test_render_event_omits_object_type_verb(self):
    activity = {'object': {'content': 'X <y> http://z?w a&b c&amp;d e&gt;f'}}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assert_multiline_in('X <y> http://z?w a&amp;b c&amp;d e&gt;f', out)
    self.assertNotIn('a&b', out)

  def test_render_encodes_ampersands(self):
    # only the one unencoded & in a&b should be encoded
    activity = {'object': {'content': 'X <y> http://z?w a&b c&amp;d e&gt;f'}}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assert_multiline_in('X <y> http://z?w a&amp;b c&amp;d e&gt;f', out)
    self.assertNotIn('a&b', out)

  def test_render_encodes_ampersands_in_quote_tweets(self):
    activity = {'object': {
      'content': 'outer',
      'attachments': [{
        'objectType': 'note',
        'content': 'X <y> http://z?w a&b c&amp;d e&gt;f',
      }],
    }}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assert_multiline_in('X <y> http://z?w a&amp;b c&amp;d e&gt;f', out)
    self.assertNotIn('a&b', out)

  def test_render_missing_object_type_and_verb(self):
    activity = {'object': {'content': 'foo'}}
    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assertNotIn('>http://activitystrea.ms/schema/1.0/<', out)

  def test_updated_defaults_to_published(self):
    activities = [
      {'object': {'published': '2013-12-27T17:25:55+00:00'}},
      {'object': {'published': '2014-12-27T17:25:55+00:00'}},
    ]

    out = atom.activities_to_atom(activities, test_twitter.ACTOR, title='my title')
    self.assert_multiline_in('<updated>2014-12-27T17:25:55+00:00</updated>', out)

  def test_escape_urls(self):
    url = 'http://foo/bar?baz&baj'
    activity = {'url': url, 'object': {}}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assert_multiline_in('<id>http://foo/bar?baz&amp;baj</id>', out)
    self.assertNotIn(url, out)

  def test_object_only(self):
    out = atom.activities_to_atom([{'object': {
      'displayName': 'Den oberoende sociala webben 2015',
      'id': 'http://voxpelli.com/2015/09/oberoende-sociala-webben-2015/',
      'author': {
        'image': {'url': 'http://voxpelli.com/avatar.jpg'},
        'url': 'http://voxpelli.com/',
      },
      'url': 'http://voxpelli.com/2015/09/oberoende-sociala-webben-2015/',
    }}], test_twitter.ACTOR)

    for expected in (
        '<link rel="alternate" type="text/html" href="http://voxpelli.com/2015/09/oberoende-sociala-webben-2015/" />',
        '<link rel="self" type="application/atom+xml" href="http://voxpelli.com/2015/09/oberoende-sociala-webben-2015/" />',
        '<uri>http://voxpelli.com/</uri>',
        ):
      self.assert_multiline_in(expected, out)

  def test_attachments(self):
    got = atom.activities_to_atom([{'object': {'attachments': [
      {'objectType': 'note', 'url': 'http://p', 'content': 'note content'},
      {'objectType': 'x', 'url': 'http://x'},
      {'objectType': 'article',
       'url': 'http://a',
       'content': 'article content',
       'author': {
         'displayName': 'Mr. Foo',
         'url': 'http://x/',
         # image shouldn't be included
         'image': {'url': 'http://x/avatar.jpg'},
       },
      },
    ]}}], None)
    self.assert_multiline_in("""
<blockquote>
note content
</blockquote>
""", got)
    self.assert_multiline_in("""
<blockquote>
<a class="p-name u-url" href="http://x/">Mr. Foo</a>: article content
</blockquote>
""", got)

  def test_to_people(self):
    got = atom.activities_to_atom([{
      'object': {
        'objectType': 'note',
        'content': 'an extended tweet reply',
        'to': [{
          'objectType': 'group',
          'alias': '@public',
        }, {
          'objectType': 'person',
          'url': 'https://twitter.com/A',
          'displayName': 'aye',
        }, {
          'objectType': 'person',
          'id': 'B',
          'url': 'https://twitter.com/B',
          'displayName': 'bee',
        }],
      },
    }], None)
    self.assert_multiline_in("""
<p>In reply to
<a class="h-card p-name u-url" href="https://twitter.com/A">aye</a>,

<a class="h-card p-name u-url" href="https://twitter.com/B">bee</a>:</p>
""", got)

  def test_rels(self):
    got = atom.activities_to_atom([], {}, rels={'foo': 'bar', 'baz': 'baj'})
    self.assert_multiline_in('<link rel="foo" href="bar" />', got)
    self.assert_multiline_in('<link rel="baz" href="baj" />', got)

  def test_xml_base(self):
    self.assert_multiline_in("""
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:georss="http://www.georss.org/georss"
      xmlns:ostatus="http://ostatus.org/schema/1.0"
      xmlns:thr="http://purl.org/syndication/thread/1.0"
      xml:base="http://my.xml/base">
""", atom.activities_to_atom([], {}, xml_base='http://my.xml/base'))

  def test_html_to_atom(self):
    self.assert_multiline_equals("""\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xmlns:activity="http://activitystrea.ms/spec/1.0/"
      xmlns:georss="http://www.georss.org/georss"
      xmlns:ostatus="http://ostatus.org/schema/1.0"
      xmlns:thr="http://purl.org/syndication/thread/1.0"
      xml:base="https://my.site/">
<generator uri="https://github.com/snarfed/granary">granary</generator>
<id>https://my.site/feed</id>
<title>my title</title>

<logo>http://my/picture</logo>
<updated></updated>
<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/site</uri>
 <name>My Name</name>
</author>

<link rel="alternate" href="http://my/site" type="text/html" />
<link rel="avatar" href="http://my/picture" />
<link rel="self" href="https://my.site/feed" type="application/atom+xml" />

<entry>

<author>
 <activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
 <uri>http://my/site</uri>
 <name>My Name</name>
</author>

  <activity:object-type>http://activitystrea.ms/schema/1.0/note</activity:object-type>

  <id>http://my/post</id>
  <title>my content</title>

  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">

my content

  </div>
  </content>

  <link rel="alternate" type="text/html" href="http://my/post" />
  <link rel="ostatus:conversation" href="http://my/post" />
  <activity:verb>http://activitystrea.ms/schema/1.0/post</activity:verb>

  <published></published>
  <updated></updated>

  <link rel="self" type="application/atom+xml" href="http://my/post" />

</entry>

</feed>
""", atom.html_to_atom("""\
<div class="h-feed">
<div class="p-author h-card">
  <a href="http://my/site">My Name</a>
  <img src="http://my/picture" />
</div>

<span class="p-name">my title</span>

<article class="h-entry">
<a class="u-url" href="http://my/post" />
<div class="e-content">my content</div>
</article>
</div>
""", 'https://my.site/feed'),
    ignore_blanks=True)

  def test_html_to_atom_fetch_author(self):
    """Based on http://tantek.com/ .
    https://github.com/snarfed/granary/issues/98
    https://github.com/kylewm/mf2util/issues/14
    """
    with self.assertRaises(AssertionError):
      # fetch_author requires url
      atom.html_to_atom('', fetch_author=True)

    html = u"""\
<body class="h-card vcard">
<img class="photo u-photo" src="photo.jpg" alt=""/>
<a class="u-url u-uid" rel="author" href="/author"></a>
<h1 class="p-name fn">Tantek Çelik</h1>

<div class="h-feed section stream" id="updates">
<span class="p-name"></span><ol>
<li class="h-entry hentry as-note">
<p class="p-name entry-title e-content entry-content article">
going to Homebrew Website Club
</p></li>
</ol></div></body>
"""

    self.expect_requests_get(
      'https://my.site/author', html, headers=mox.IgnoreArg(), timeout=None,
      response_headers={'content-type': 'text/html; charset=utf-8'})
    self.mox.ReplayAll()

    got = atom.html_to_atom(html, 'https://my.site/', fetch_author=True)
    self.assert_multiline_in(u"""\
<author>
<activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
<uri>https://my.site/author</uri>
<name>Tantek Çelik</name>
</author>

<link rel="alternate" href="https://my.site/author" type="text/html" />
<link rel="avatar" href="https://my.site/photo.jpg" />
<link rel="self" href="https://my.site/" type="application/atom+xml" />

<entry>
<author>
<activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
<uri>https://my.site/author</uri>
<name>Tantek Çelik</name>
</author>
""".encode('utf-8'), got.encode('utf-8'), ignore_blanks=True)

  def test_media_enclosures(self):
    self.assert_multiline_in("""\
<link rel="enclosure" href="http://a/podcast.mp3" />

<link rel="enclosure" href="http://a/vidjo.mov" />
""",
      atom.activities_to_atom([{
        'object': {
          'content': 'foo bar',
          'attachments': [{
            'objectType': 'audio',
            'url': 'http://a/podcast.mp3',
          }, {
            'objectType': 'video',
            'url': 'http://a/vidjo.mov',
          }],
        },
      }], {}))

  def test_reader_param_and_location(self):
    activity = {
      'object': {
        'content': 'foo',
        'location': {
          'displayName': 'My place',
          'url': 'http://my/place',
        },
      },
    }
    location = '<a class="p-name u-url" href="http://my/place">My place</a>'

    self.assert_multiline_in(
      location, atom.activities_to_atom([activity], {}, reader=True))
    self.assertNotIn(
      location, atom.activities_to_atom([activity], {}, reader=False))

  def test_image_outside_content(self):
    """image field (from e.g. mf2 u-photo) should be rendered in content.

    https://github.com/snarfed/granary/issues/113
    """
    activity = {
      'object': {
        'content': 'foo',
        'image': [
          {"url": "http://pics/1.jpg"},
          {"url": "http://pics/2.jpg"},
        ],
      },
    }

    self.assert_multiline_in("""\
<blockquote>
<img class="u-photo" src="http://pics/1.jpg" alt="" />
</blockquote>

<blockquote>
<img class="u-photo" src="http://pics/2.jpg" alt="" />
</blockquote>
""", atom.activities_to_atom([activity], {}))

  def test_image_duplicated_in_content(self):
    """If an image is already in the content, don't render a duplicate.

    https://github.com/snarfed/granary/issues/113
    """
    for url in 'http://pics/1.jpg?foo', '/1.jpg?foo':
      activity = {
        'object': {
          'content': 'foo <img src="%s"> bar' % url,
          'image': [
            {"url": "http://pics/1.jpg?foo"},
            {"url": "http://pics/2.jpg"},
          ],
        },
      }

    got = atom.activities_to_atom([activity], {})
    self.assertNotIn('<img class="u-photo" src="http://pics/1.jpg?foo" alt="" />', got)
    self.assert_multiline_in("""\
<blockquote>
<img class="u-photo" src="http://pics/2.jpg" alt="" />
</blockquote>
""", got)

  def test_image_duplicated_in_attachment(self):
    """If an image is also in an attachment, don't render a duplicate.

    https://github.com/snarfed/twitter-atom/issues/8
    """
    activity = {
      'object': {
        'content': 'foo bar',
        'image': [
          {'url': 'http://pics/1.jpg'},
          {'url': 'http://pics/2.jpg'},
        ],
        'attachments': [{
          'objectType': 'note',
          'image': {'url': 'http://pics/2.jpg'},
        }, {
          'objectType': 'image',
          'image': {'url': 'http://pics/1.jpg'},
        }],
      },
    }

    got = atom.activities_to_atom([activity], {})
    self.assertNotIn('<img class="u-photo" src="http://pics/1.jpg" alt="" />', got)
    self.assertNotIn('<img class="u-photo" src="http://pics/2.jpg" alt="" />', got)

  def test_context_in_reply_to(self):
    """context.inReplyTo should be translated to thr:in-reply-to."""
    activity = {
      'context': {'inReplyTo': [{
        'id': 'the:orig',
        'url': 'http://orig',
      }]},
      'object': {'id': 'my:reply'},
    }

    self.assert_multiline_in(
      '<thr:in-reply-to ref="the:orig" href="http://orig" type="text/html" />',
      atom.activities_to_atom([activity], {}))

  def test_object_in_reply_to(self):
    """inReplyTo should be translated to thr:in-reply-to."""
    activity = {'object': {
      'id': 'my:reply',
      'inReplyTo': [{
        'id': 'the:orig',
        'url': 'http://orig',
      }],
    }}

    self.assert_multiline_in(
      '<thr:in-reply-to ref="the:orig" href="http://orig" type="text/html" />',
      atom.activities_to_atom([activity], {}))

  def test_author_email(self):
    """inReplyTo should be translated to thr:in-reply-to."""
    activity = {'object': {
      'content': 'foo',
      'author': {
        'displayName': 'Mrs. Foo',
        'email': 'mrs@foo.com',
      },
    }}

    self.assert_multiline_in("""\
<author>
<activity:object-type>http://activitystrea.ms/schema/1.0/person</activity:object-type>
<uri></uri>
<name>Mrs. Foo</name>
<email>mrs@foo.com</email>
</author>
""", atom.activities_to_atom([activity], {}), ignore_blanks=True)
