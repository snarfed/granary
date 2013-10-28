"""Unit tests for canned data in testdata/.
"""

import glob
import json
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


class TestDataTest(testutil.HandlerTest):
  def test_activitystreams_to_uf2_json(self):
    for src, dst in filepairs('as.json', 'uf2.json'):
      with open(src) as srcf, open(dst) as dstf:
        converters = {'object': microformats2.object_to_json,
                      'actor': None,#microformats2.actor_to_json,
                      }
        fn = converters[src.split('_')[0]]
        if not fn:
          continue
        self.assert_equals(json.loads(dstf.read()), fn(json.loads(srcf.read())))
