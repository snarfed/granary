"""Unit tests for canned data in testdata/.
"""
import copy
import glob
import logging
import os

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads

from .. import as2, bluesky, jsonfeed, microformats2, rss

logger = logging.getLogger(__name__)


def filepairs(ext1, ext2s):
  """Returns all matching pairs of filenames with the given extensions."""
  pairs = []
  for first in glob.glob(f'*.{ext1}'):
    for ext2 in ext2s:
      second = first[:-len(ext1)] + ext2
      if os.path.isfile(second):
        pairs.append((first, second))
        break
  return pairs


def read_json(filename):
  """Reads JSON from a file. Attaches the filename to exceptions."""
  try:
    with open(filename, encoding='utf-8') as f:
      # note that ujson allows embedded newlines in strings, which we have in eg
      # note_with_whitespace.as.json and friends.
      return json_loads(f.read())
  except Exception as e:
    e.args = (f'{filename}: ',) + e.args
    raise


def read(filename, ignore_fields=()):
  """Reads a file, decoding JSON if possible, optionally ignoring some fields."""
  if os.path.splitext(filename)[1] in ('.html', '.xml'):
    with open(filename, encoding='utf-8') as f:
      return f.read()
  else:
    return discard_fields(read_json(filename), ignore_fields)


def discard_fields(obj, fields):
  if isinstance(obj, dict):
    return {k: discard_fields(v, fields) for k, v in obj.items()
            if k not in fields}
  elif isinstance(obj, (tuple, list, set, frozenset)):
    return [discard_fields(elem, fields) for elem in obj]
  else:
    return obj


def create_test_function(fn, original, expected, **kwargs):
  """Create a simple test function that asserts fn(original) == expected.

  kwargs are passed to assert_equals (but not assert_multiline_equals).
  """
  def test(self):
    got = fn(original)
    if isinstance(got, str) and isinstance(expected, str):
      return self.assert_multiline_equals(expected, got, ignore_blanks=True)
    else:
      return self.assert_equals(expected, got, in_order=True, **kwargs)

  return test


# All test data files live in testdata/.
prevdir = os.getcwd()
os.chdir(os.path.join(os.path.dirname(__file__), 'testdata/'))

ACTOR = read('actor.as.json', ignore_fields=('id', 'username'))

# wrap jsonfeed functions to add/remove actors and wrap/unwrap activities
def activity_to_jsonfeed(obj):
  return jsonfeed.activities_to_jsonfeed([{'object': obj}], ACTOR)

def jsonfeed_to_activity(jf):
  activities, actor = jsonfeed.jsonfeed_to_activities(jf)
  expected_actor = copy.deepcopy(ACTOR)
  del expected_actor['summary']
  assert actor == expected_actor, (actor, expected_actor)
  assert len(activities) == 1
  return activities[0]

def html_to_activity(html):
  return microformats2.html_to_activities(html)[0]['object']

def rss_from_activities(activities):
  hfeed = {
    'properties': {
      'content': [{'value': 'some stuff by meee'}],
    },
  }
  return rss.from_activities(
    activities, actor=ACTOR, title='Stuff', feed_url='http://site/feed',
    home_page_url='http://site/', hfeed=hfeed)

def rss_to_objects(feed):
  return [a['object'] for a in rss.to_activities(feed)]

def bluesky_to_as1(record):
  return bluesky.to_as1(record, repo_did='did:plc:foo', repo_handle='example.com')

def bluesky_from_as1(record):
  return bluesky.from_as1(record, original_fields_prefix='foo')

# source extension, destination extension, conversion function, exclude prefix,
# ignore fields. destinations take precedence in the order they appear. only the
# first (source, dest) pair for a given prefix is tested. this is how eg
# mf2-from-as.json gets tested even if as.json exists.
mappings = (
  ('as.json', ['mf2-from-as.json', 'mf2.json'], microformats2.object_to_json,
  # doesn't handle h-feed yet
   ('feed_with_audio_video',), ()),
  ('as.json', ['mf2-from-as.html', 'mf2.html'], microformats2.object_to_html, (), ()),
  ('mf2.json', ['as-from-mf2.json', 'as.json'], microformats2.json_to_object,
  # doesn't handle h-feed yet
   ('feed_with_audio_video',), ()),
  ('mf2.json', ['mf2-from-json.html', 'mf2.html'], microformats2.json_to_html,
   # we do not format h-media photos properly in html
   ('note_with_composite_photo',), ()),
  # not ready yet
  # ('mf2.html', ['as-from-mf2.json', 'as.json'], html_to_activity, ()),
  ('as.json', ['feed-from-as.json', 'feed.json'], activity_to_jsonfeed, (), ()),
  ('feed.json', ['as-from-feed.json', 'as.json'], jsonfeed_to_activity, (), ()),
  ('as.json', ['as2-from-as.json', 'as2.json'], as2.from_as1, (), ()),
  ('as2.json', ['as-from-as2.json', 'as.json'], as2.to_as1, (), ()),
  ('as.json', ['rss.xml'], rss_from_activities, (), ()),
  ('rss.xml', ['as-from-rss.json', 'as.json'], rss_to_objects, (), ()),
  ('as.json', ['bsky-from-as.json', 'bsky.json'], bluesky_from_as1,
   ('comment_inreplyto_id',), ('avatar', 'banner')),
  ('bsky.json', ['as.json'], bluesky_to_as1, (), ('location', 'updated')),
  ('bsky.json', ['as-from-bsky.json'], bluesky_to_as1, (), ()),
)

test_funcs = {}
for src_ext, dst_exts, fn, exclude_prefixes, ignore_fields in mappings:
  for src, dst in filepairs(src_ext, dst_exts):
    if any(dst.startswith(prefix) for prefix in exclude_prefixes):
      continue

    expected = read(dst, ignore_fields)
    original = read(src, ignore_fields)
    test_name = (
      f'test_{fn.__module__.split(".")[-1]}_{fn.__name__}_{src[:-len(src_ext)]}'
    ).replace('.', '_').replace('-', '_').strip('_')
    # assert test_name not in test_funcs, test_name
    test_funcs[test_name] = create_test_function(fn, original, expected, ignore=[])

os.chdir(prevdir)


TestDataTest = type('TestDataTest', (testutil.TestCase,), test_funcs)
