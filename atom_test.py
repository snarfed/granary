"""Unit tests for atom.py."""

import copy

import atom
import facebook_test
import instagram_test
from oauth_dropins.webutil import testutil
import twitter_test


class AtomTest(testutil.HandlerTest):

  def test_activities_to_atom(self):
    for test_module in facebook_test, instagram_test, twitter_test:
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
        atom.activities_to_atom([copy.deepcopy(facebook_test.ACTIVITY)],
                                facebook_test.ACTOR,
                                title='my title'))

  def test_render_content_as_html(self):
    self.assertIn('<a href="https://twitter.com/foo">@twitter</a> meets @seepicturely at <a href="https://twitter.com/search?q=%23tcdisrupt">#tcdisrupt</a> &lt;3 <a href="http://first/link/">first</a> <a href="http://instagr.am/p/MuW67/">instagr.am/p/MuW67</a> ',
        atom.activities_to_atom([copy.deepcopy(twitter_test.ACTIVITY)],
                                twitter_test.ACTOR,
                                title='my title'))

  def test_render_with_image(self):
    """Attached images are rendered inline as HTML
    """
    self.assertIn(
      '<img class="thumbnail" src="http://attach/image/big"',
      atom.activities_to_atom([copy.deepcopy(instagram_test.ACTIVITY)],
                              instagram_test.ACTOR,
                              title='my title'))

  def test_render_untitled_image(self):
    """Images should be included even if there is no other content
    """
    activity = copy.deepcopy(instagram_test.ACTIVITY)
    del activity['object']['content']
    self.assertIn(
      '<img class="thumbnail" src="http://attach/image/big"',
      atom.activities_to_atom([activity], instagram_test.ACTOR,
                              title='my title'))

  def test_render_encodes_ampersands(self):
    # only the one unencoded & in a&b should be encoded
    activity = {'object': {'content': 'X <y> http://z?w a&b c&amp;d e&gt;f'}}

    out = atom.activities_to_atom([activity], twitter_test.ACTOR, title='my title')
    self.assertIn('X <y> http://z?w a&amp;b c&amp;d e&gt;f', out)
    self.assertNotIn('a&b', out)

  def test_escape_urls(self):
    url = 'http://foo/bar?baz&baj'
    activity = {'url': url, 'object': {}}

    out = atom.activities_to_atom([activity], twitter_test.ACTOR, title='my title')
    self.assertIn('<id>http://foo/bar?baz&amp;baj</id>', out)
    self.assertNotIn(url, out)

