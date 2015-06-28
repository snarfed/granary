"""Unit tests for canned data in testdata/.
"""

import glob
import json
import logging
import os

from granary import microformats2
from granary import testutil


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
  def test_testdata(self):
    # TODO: use a handler with an HTTPS request so that URL schemes are converted
    # self.handler.request = webapp2.Request.blank('/', base_url='https://foo')

    # All test data files live in testdata/.
    os.chdir(os.path.join(os.path.dirname(__file__), 'testdata/'))

    # source extension, destination extension, conversion function, exclude prefix
    mappings = (
      ('as.json', 'mf2.json', microformats2.object_to_json,
       # as and mf2 do not have feature parity for these types, some
       # info is lost in translation.
       # TODO support asymmetric comparisons (possibly: extension types
       # like .mf2-from-as.json would supersede .mf2.json if present)
       ('in_reply_to','repost_of_with_h_cite', 'nested_author',
        'note_with_composite_photo')),
      ('as.json', 'mf2.html', microformats2.object_to_html,
       ('in_reply_to','repost_of_with_h_cite', 'nested_author',
      #  'note_with_composite_photo'
      )), # see above
      ('mf2.json', 'as.json', microformats2.json_to_object,
       # these have tags, which we don't generate
       ('note.', 'article_with_')),
      ('mf2.json', 'mf2.html', microformats2.json_to_html,
       ('in_reply_to','repost_of_with_h_cite', 'nested_author',
        'note_with_composite_photo')), # see above
      )

    failed = False
    for src_ext, dst_ext, fn, excludes in mappings:
      for src, dst in filepairs(src_ext, dst_ext):
        excluded = False
        for exclude in excludes:
          if dst.startswith(exclude):
            excluded = True
        if excluded:
          continue

        if os.path.splitext(dst_ext)[1] in ('.html', '.xml'):
          expected = open(dst).read()
        else:
          expected = read_json(dst)
        try:
          self.assert_equals(expected, fn(read_json(src)),
                             '\n%s:1:\n' % os.path.abspath(dst))
        except AssertionError:
          logging.exception('')
          failed = True

    os.chdir('..')
    assert not failed
