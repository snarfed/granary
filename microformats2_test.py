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

  def test_json_to_object_html_content(self):
    both = {'properties': {'content': [{'value': 'my val', 'html': 'my html'}]}}
    html = {'properties': {'content': [{'html': 'my html'}]}}
    value = {'properties': {'content': [{'value': 'my val'}]}}
    neither = {'properties': {'content': [{}]}}

    jto = microformats2.json_to_object
    for json, html_content, expected in (
      (both, True, 'my html'), (html, True, 'my html'), (html, False, 'my html'),
      (both, False, 'my val'), (value, True, 'my val'), (value, False, 'my val'),
      (neither, True, None), (neither, False, None)):
      self.assertEquals(expected, jto(json, html_content=html_content).get('content'))

  def test_photo_property_is_not_url(self):
    """handle the case where someone (incorrectly) marks up the caption
    with p-photo
    """
    mf2 = {'properties':
           {'photo': ['the caption', 'http://example.com/image.jpg']}}
    obj = microformats2.json_to_object(mf2)
    self.assertEquals('http://example.com/image.jpg', obj['image']['url'])

  def test_photo_property_has_no_url(self):
    """handle the case where the photo property is *only* text, not a url"""
    mf2 = {'properties':
           {'photo': ['the caption', 'alternate text']}}
    obj = microformats2.json_to_object(mf2)
    self.assertFalse(obj.get('image'))
