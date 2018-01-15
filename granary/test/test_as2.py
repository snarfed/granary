# coding=utf-8
"""Unit tests for as2.py.

Most of the tests are in testdata/. This is just a few things that are too small
for full testdata tests.
"""
from __future__ import unicode_literals

from oauth_dropins.webutil import testutil

from granary import as2


class ActivityStreams2Test(testutil.TestCase):

  def test_from_as1_blank(self):
    self.assertEqual({}, as2.from_as1(None))
    self.assertEqual({}, as2.from_as1({}))

  def test_to_as1_blank(self):
    self.assertEqual({}, as2.to_as1(None))
    self.assertEqual({}, as2.to_as1({}))

  def test_bad_input_types(self):
    for bad in 1, [2], (3,):
      for fn in as2.to_as1, as2.from_as1:
        with self.assertRaises(ValueError):
          fn(bad)

    with self.assertRaises(ValueError):
      as2.from_as1('z')
