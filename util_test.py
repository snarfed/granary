#!/usr/bin/python
"""Unit tests for util.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import unittest

import util


class ToXmlTest(unittest.TestCase):

  def test_no_values(self):
    self.assertEqual('', util.to_xml({}))

  def test_flat(self):
    self.assertEqual("""
<a>3.14</a>\n<b>xyz</b>
""", util.to_xml({'a': 3.14, 'b': 'xyz'}))

  def test_none(self):
    self.assertEqual("""
<a></a>
""", util.to_xml({'a': None}))

  def test_empty_string(self):
    self.assertEqual("""
<a></a>
"""
, util.to_xml({'a': ''}))

  def test_empty_dict(self):
    self.assertEqual("""
<a></a>
"""
, util.to_xml({'a': {}}))

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


class TrimNullsTest(unittest.TestCase):

  def test_none(self):
    self.assertEqual(None, util.trim_nulls(None))

  def test_string(self):
    self.assertEqual('foo', util.trim_nulls('foo'))

  def test_empty_list(self):
    self.assertEqual([], util.trim_nulls([]))

  def test_empty_dict(self):
    self.assertEqual({}, util.trim_nulls({}))

  def test_simple_dict_with_nulls(self):
    self.assertEqual({}, util.trim_nulls({1: None, 2: [], 3: {}}))

  def test_simple_dict(self):
    self.assertEqual({1: 2, 3: 4}, util.trim_nulls({1: 2, 3: 4}))

  def test_simple_dict_with_nones(self):
    self.assertEqual({3: 4, 2: 9}, util.trim_nulls({1: None, 3: 4, 5: [], 2: 9}))

  def test_nested_dict_with_nones(self):
    self.assertEqual({1: {3: 4}}, util.trim_nulls({1: {2: [], 3: 4}, 5: {6: None}}))

