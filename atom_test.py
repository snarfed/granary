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

