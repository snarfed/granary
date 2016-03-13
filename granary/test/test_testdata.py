"""Unit tests for canned data in testdata/.
"""

import glob
import json
import logging
import os

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import microformats2


def filepairs(ext1, ext2s):
  """Returns all matching pairs of filenames with the given extensions.
  """
  pairs = []
  for first in glob.glob('*.%s' % ext1):
    for ext2 in ext2s:
      second = first[:-len(ext1)] + ext2
      if os.path.isfile(second):
        pairs.append((first, second))
        break
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


def create_test_function(fn, original, expected):
  """Create a simple test function that asserts
  fn(original) == expected"""
  return lambda self: self.assert_equals(expected, fn(original))


# TODO: use a handler with an HTTPS request so that URL schemes are converted
# self.handler.request = webapp2.Request.blank('/', base_url='https://foo')

# All test data files live in testdata/.
prevdir = os.getcwd()
os.chdir(os.path.join(os.path.dirname(__file__), 'testdata/'))

# source extension, destination extension, conversion function, exclude prefix
mappings = (
  ('as.json', ['mf2-from-as.json', 'mf2.json'], microformats2.object_to_json, ()),
  ('as.json', ['mf2-from-as.html', 'mf2.html'], microformats2.object_to_html, ()),
  ('mf2.json', ['as-from-mf2.json', 'as.json'], microformats2.json_to_object, ()),
  ('mf2.json', ['mf2-from-json.html', 'mf2.html'], microformats2.json_to_html,
   # we do not format h-media photos properly in html
   ('note_with_composite_photo',)),
)

test_funcs = {}
for src_ext, dst_exts, fn, excludes in mappings:
  for src, dst in filepairs(src_ext, dst_exts):
    if any(dst.startswith(exclude) for exclude in excludes):
      continue

    if os.path.splitext(dst)[1] in ('.html', '.xml'):
      expected = open(dst).read()
    else:
      expected = read_json(dst)
    original = read_json(src)

    test_name = (
      'test_%s_%s' % (fn.__name__, src[:-len(src_ext)])
    ).replace('.', '_').replace('-', '_').strip('_')
    test_funcs[test_name] = create_test_function(fn, original, expected)

os.chdir(prevdir)


TestDataTest = type('TestDataTest', (testutil.HandlerTest,), test_funcs)
