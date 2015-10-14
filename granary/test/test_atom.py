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
                            },
        atom.activities_to_atom(
          [copy.deepcopy(test_module.ACTIVITY)],
          test_module.ACTOR,
          request_url='http://request/url?access_token=foo',
          host_url='http://host/url',
          ))

  def test_title(self):
    self.assertIn('\n<title>my title</title>',
        atom.activities_to_atom([copy.deepcopy(test_facebook.ACTIVITY)],
                                test_facebook.ACTOR,
                                title='my title'))

  def test_strip_html_tags_from_titles(self):
    activity = copy.deepcopy(test_facebook.ACTIVITY)
    activity['displayName'] = '<p>foo &amp; <a href="http://bar">bar</a></p>'
    self.assertIn('<title>foo &amp; bar</title>\n',
                  atom.activities_to_atom([activity], test_facebook.ACTOR))


  def test_render_content_as_html(self):
    self.assertIn('<a href="https://twitter.com/foo">@twitter</a> meets @seepicturely at <a href="https://twitter.com/search?q=%23tcdisrupt">#tcdisrupt</a> &lt;3 <a href="http://first/link/">first</a> <a href="http://instagr.am/p/MuW67/">instagr.am/p/MuW67</a> ',
        atom.activities_to_atom([copy.deepcopy(test_twitter.ACTIVITY)],
                                test_twitter.ACTOR,
                                title='my title'))

  def test_render_with_image(self):
    """Attached images are rendered inline as HTML
    """
    self.assertIn(
      '<img class="thumbnail" src="http://attach/image/big"',
      atom.activities_to_atom([copy.deepcopy(test_instagram.ACTIVITY)],
                              test_instagram.ACTOR,
                              title='my title'))

  def test_render_untitled_image(self):
    """Images should be included even if there is no other content
    """
    activity = copy.deepcopy(test_instagram.ACTIVITY)
    del activity['object']['content']
    self.assertIn(
      '<img class="thumbnail" src="http://attach/image/big"',
      atom.activities_to_atom([activity], test_instagram.ACTOR,
                              title='my title'))

  def test_render_encodes_ampersands(self):
    # only the one unencoded & in a&b should be encoded
    activity = {'object': {'content': 'X <y> http://z?w a&b c&amp;d e&gt;f'}}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assertIn('X <y> http://z?w a&amp;b c&amp;d e&gt;f', out)
    self.assertNotIn('a&b', out)

  def test_updated_defaults_to_published(self):
    activities = [
      {'object': {'published': '2013-12-27T17:25:55+00:00'}},
      {'object': {'published': '2014-12-27T17:25:55+00:00'}},
    ]

    out = atom.activities_to_atom(activities, test_twitter.ACTOR, title='my title')
    self.assertIn('<updated>2014-12-27T17:25:55+00:00</updated>', out)

  def test_escape_urls(self):
    url = 'http://foo/bar?baz&baj'
    activity = {'url': url, 'object': {}}

    out = atom.activities_to_atom([activity], test_twitter.ACTOR, title='my title')
    self.assertIn('<id>http://foo/bar?baz&amp;baj</id>', out)
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
      self.assertIn(expected, out)

