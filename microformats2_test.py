"""Unit tests for source.py.

Most of the tests are in testdata/. This is just a few things that are too small
for full testdata tests.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import microformats2
from oauth_dropins.webutil import testutil


class Microformats2Test(testutil.HandlerTest):

  def test_properties_override_h_as_article(self):
    for prop, verb in (('like', 'like'),
                       ('like-of', 'like'),
                       ('repost', 'share'),
                       ('repost-of', 'share')):
      obj = microformats2.json_to_object(
        {'type': ['h-entry', 'h-as-note'],
          'properties': {prop: ['http://foo/bar']}})
      self.assertEquals('activity', obj['objectType'])
      self.assertEquals(verb, obj['verb'])

    obj = microformats2.json_to_object(
      {'type': ['h-entry', 'h-as-article'],
       'properties': {'rsvp': ['no']}})
    self.assertEquals('activity', obj['objectType'])
    self.assertEquals('rsvp-no', obj['verb'])

  def test_h_as_article(self):
    obj = microformats2.json_to_object({'type': ['h-entry', 'h-as-article']})
    self.assertEquals('article', obj['objectType'])
