"""Unit tests for canned data in testdata/.
"""

import glob
import json
import logging
import os
import unittest

import microformats2
from oauth_dropins.webutil import testutil

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
  def test_testdata(self):
    # TODO: use a handler with an HTTPS request so that URL schemes are converted
    # self.handler.request = webapp2.Request.blank('/', base_url='https://foo')

    # source extension, destination extention, conversion function
    mappings = (('as.json', 'mf2.json', microformats2.object_to_json),
                ('mf2.json', 'as.json', microformats2.json_to_object),
                ('as.json', 'mf2.html', microformats2.object_to_html),
                # ('mf2.html', 'as.json', microformats2.html_to_object),
                )

    failed = False
    for src_ext, dst_ext, fn in mappings:
      for src, dst in filepairs(src_ext, dst_ext):
        # TODO
        if dst in ('article_with_comments.as.json',
                   'article_with_likes.as.json',
                   'article_with_reposts.as.json',
                   'comment.as.json',
                   'like.as.json',
                   'like_multiple_urls.as.json',
                   'note.as.json',
                   'repost.as.json',
                   'rsvp.as.json',
                   ):
          continue
        if os.path.splitext(dst_ext)[1] in ('.html', '.xml'):
          expected = open(dst).read()
        else:
          expected = read_json(dst)
        try:
          self.assert_equals(expected, fn(read_json(src)),
                             '\n%s:1:\n' % os.path.abspath(dst))
        except AssertionError, e:
          logging.exception('')
          failed = True

    assert not failed
