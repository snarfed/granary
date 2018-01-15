"""Unit tests for canned data in testdata/.
"""
from __future__ import unicode_literals
from future.utils import bytes_to_native_str
from past.builtins import basestring

import glob
import json
import logging
import os

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import as2, jsonfeed, microformats2


def filepairs(ext1, ext2s):
  """Returns all matching pairs of filenames with the given extensions."""
  pairs = []
  for first in glob.glob('*.%s' % ext1):
    for ext2 in ext2s:
      second = first[:-len(ext1)] + ext2
      if os.path.isfile(second):
        pairs.append((first, second))
        break
  return pairs


def read_json(filename):
  """Reads JSON from a file. Attaches the filename to exceptions."""
  try:
    with open(filename) as f:
      return json.loads(f.read())
  except Exception as e:
    e.args = ('%s: ' % filename,) + e.args
    raise


def read(filename):
  """Reads a file, decoding JSON if possible."""
  if os.path.splitext(filename)[1] in ('.html', '.xml'):
    with open(filename) as f:
      return f.read()
  else:
    return read_json(filename)


def create_test_function(fn, original, expected):
  """Create a simple test function that asserts fn(original) == expected."""
  def test(self):
    got = fn(original)
    if isinstance(got, basestring) and isinstance(expected, basestring):
      return self.assert_multiline_equals(expected, got, ignore_blanks=True)
    else:
      return self.assert_equals(expected, got, in_order=True)
  return test

# TODO: use a handler with an HTTPS request so that URL schemes are converted
# self.handler.request = webapp2.Request.blank('/', base_url='https://foo')

# All test data files live in testdata/.
prevdir = os.getcwd()
os.chdir(os.path.join(os.path.dirname(__file__), 'testdata/'))

ACTOR = read_json('actor.as.json')
del ACTOR['id']

# wrap jsonfeed functions to add/remove actors and wrap/unwrap activities
def activity_to_jsonfeed(obj):
  return jsonfeed.activities_to_jsonfeed([{'object': obj}], ACTOR)

def jsonfeed_to_activity(jf):
  activities, actor = jsonfeed.jsonfeed_to_activities(jf)
  assert actor == ACTOR, (actor, ACTOR)
  assert len(activities) == 1
  return activities[0]['object']

def html_to_activity(html):
  return microformats2.html_to_activities(html)[0]['object']

# source extension, destination extension, conversion function, exclude prefix
mappings = (
  ('as.json', ['mf2-from-as.json', 'mf2.json'], microformats2.object_to_json, ()),
  ('as.json', ['mf2-from-as.html', 'mf2.html'], microformats2.object_to_html, ()),
  ('mf2.json', ['as-from-mf2.json', 'as.json'], microformats2.json_to_object, ()),
  ('mf2.json', ['mf2-from-json.html', 'mf2.html'], microformats2.json_to_html,
   # we do not format h-media photos properly in html
   ('note_with_composite_photo',)),
  # not ready yet
  # ('mf2.html', ['as-from-mf2.json', 'as.json'], html_to_activity, ()),
  ('as.json', ['feed-from-as.json', 'feed.json'], activity_to_jsonfeed, ()),
  ('feed.json', ['as-from-feed.json', 'as.json'], jsonfeed_to_activity, ()),
  ('as.json', ['as2-from-as.json', 'as2.json'], as2.from_as1, ()),
  ('as2.json', ['as-from-as2.json', 'as.json'], as2.to_as1, ()),
)

test_funcs = {}
for src_ext, dst_exts, fn, excludes in mappings:
  for src, dst in filepairs(src_ext, dst_exts):
    if any(dst.startswith(exclude) for exclude in excludes):
      continue

    expected = read(dst)
    original = read(src)
    test_name = (
      'test_%s_%s' % (fn.__name__, src[:-len(src_ext)])
    ).replace('.', '_').replace('-', '_').strip('_')
    test_funcs[test_name] = create_test_function(fn, original, expected)

os.chdir(prevdir)


TestDataTest = type(bytes_to_native_str(b'TestDataTest'), (testutil.TestCase,),
                    test_funcs)
