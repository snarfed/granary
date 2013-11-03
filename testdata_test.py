"""Unit tests for canned data in testdata/.
"""

import glob
import json
import logging
import os
import unittest

import microformats2
from webutil import testutil

# All test data files live in testdata/.
os.chdir('testdata/')


def filepairs(ext1, ext2):
  """Returns all matching pairs of filenames with the given extensions.
  """
  pairs = []
  for first in glob.glob('*.%s' % ext1):
    second = first[:-len(ext1)] + ext2
    if os.path.isfile(second):
      pairs.append((first, second))
  return pairs


def read_json(filename):
  """Reads JSON from a file. Attaches the filename to exceptions.
  """
  try:
    with open(filename) as f:
      return json.loads(f.read())
  except Exception, e:
    e.args = ('%s: ' % filename,) + e.args
    raise


class TestDataTest(testutil.HandlerTest):
  def test_activitystreams_to_uf2_json(self):
    # source extension, destination extention, conversion function
    mappings = (('as.json', 'uf2.json', microformats2.object_to_json),
#                ('as.json', 'uf2.html', microformats2.object_to_html),
                )

    for src_ext, dst_ext, fn in mappings:
      for src, dst in filepairs(src_ext, dst_ext):
        if src.startswith('comment'):
          continue
        if os.path.splitext(dst_ext)[1] in ('.html', '.xml'):
          expected = open(dst).read()
        else:
          expected = read_json(dst)
        try:
          self.assert_equals(expected, fn(read_json(src)))
        except Exception, e:
          logging.error('%s => %s', src, dst)
          raise
