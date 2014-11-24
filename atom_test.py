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
    self.assertIn('<a href="https://twitter.com/foo">@twitter</a> meets @seepicturely at <a href="https://twitter.com/search?q=%23tcdisrupt">#tcdisrupt</a> &lt;3 <a href="http://first/link/">first</a> <a href="http://instagr.am/p/MuW67/">instagr.am/p/MuW67</a> <a href="http://p.twimg.com/picture1">[picture]</a>',
        atom.activities_to_atom([copy.deepcopy(twitter_test.ACTIVITY)],
                                twitter_test.ACTOR,
                                title='my title'))

