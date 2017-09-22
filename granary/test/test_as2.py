# coding=utf-8
"""Unit tests for as2.py.

Most of the tests are in testdata/. This is just a few things that are too small
for full testdata tests.
"""
from oauth_dropins.webutil import testutil

from granary import as2


class ActivityStreams2Test(testutil.HandlerTest):

  def test_from_as1_blank(self):
    self.assertEqual({}, as2.from_as1(None))
    self.assertEqual({}, as2.from_as1({}))

  def test_to_as1_blank(self):
    self.assertEqual({}, as2.to_as1(None))
    self.assertEqual({}, as2.to_as1({}))

