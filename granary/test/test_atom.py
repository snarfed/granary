"""Unit tests for atom.py."""

import copy

from oauth_dropins.webutil import testutil

from granary import atom

import test_facebook
import test_instagram
import test_twitter


class AtomTest(testutil.HandlerTest):

  def test_activities_to_atom(self):
    for test_module in test_facebook, test_instagram, test_twitter:
      self.assert_multiline_equals(
        test_module.ATOM % {'request_url': 'http://request/url',
                            'host_url': 'http://host/url',
                            'base_url': 'http://base/url',
                            },
        atom.activities_to_atom(
          [copy.deepcopy(test_module.ACTIVITY)],
          test_module.ACTOR,
          request_url='http://request/url?access_token=foo',
          host_url='http://host/url',
          xml_base='http://base/url',
        ))

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

  def test_render_encodes_ampersands(self):
    # only the one unencoded & in a&b should be encoded
    activity = {'object': {'content': 'X <y> http://z?w a&b c&amp;d e&gt;f'}}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assert_multiline_in('X <y> http://z?w a&amp;b c&amp;d e&gt;f', out)
    self.assertNotIn('a&b', out)

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
      {'objectType': 'article', 'url': 'http://a', 'content': 'article content'},
    ]}}], None)
    self.assert_multiline_in("""
<blockquote>
note content
</blockquote>
""", got)
    self.assert_multiline_in("""
<blockquote>
article content
</blockquote>
""", got)

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
