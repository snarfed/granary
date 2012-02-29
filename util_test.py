#!/usr/bin/python
"""Unit tests for util.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import unittest

import util


class ToXmlTest(unittest.TestCase):

  def test_empty(self):
    self.assertEqual("""

""", util.to_xml({}))

  def test_flat(self):
    self.assertEqual("""
<a>3.14</a>\n<b>xyz</b>
""", util.to_xml({'a': 3.14, 'b': 'xyz'}))

  def test_none(self):
    self.assertEqual("""
<a></a>
""", util.to_xml({'a': None}))

  def test_empty(self):
    self.assertEqual("""
<a></a>
"""
, util.to_xml({'a': ''}))

  def test_zero(self):
    self.assertEqual("""
<a>0</a>
"""
, util.to_xml({'a': 0}))

  def test_list(self):
    self.assertEqual("""
<a>1</a>
<a>2</a>
""", util.to_xml({'a': [1, 2]}))

  def test_nested(self):
    self.assertEqual("""
<a>
<b>
<c>x</c>
<d>y</d>
</b>
<e>2</e>
<e>3</e>
</a>
""", util.to_xml({'a': {'b': {'c': 'x', 'd': 'y'},
                        'e': (2, 3),
                        }}))
