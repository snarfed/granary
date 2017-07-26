#!/usr/bin/env python
"""Google+ integration test against the live site.

Just checks that fetching and converting Ryan's feed includes 12 activities,
and all the expected fields are non-empty.

https://github.com/snarfed/granary/issues/106
"""
import logging
import re
import sys
import unittest

from granary import googleplus
from granary.source import SELF
import requests

URL = 'https://plus.google.com/+RyanBarrett'


class GooglePlusTestLive(unittest.TestCase):

  def test_live(self):
    resp = requests.get(URL)
    resp.raise_for_status()

    activities = googleplus.GooglePlus().html_to_activities(resp.text)
    self.assertEqual(10, len(activities))

    import json; print json.dumps(activities, indent=2)

    found = set()
    for a in activities:
      self.assertTrue(a['actor'])
      for field in 'id', 'url':
        self.assertTrue(a['object'][field], field)
      for field in 'content', 'replies', 'tags', 'image':
        if a['object'].get(field):
          found.add(field)

    for field in 'content', 'replies', 'tags', 'image':
      self.assertIn(field, found)


if __name__ == '__main__':
  if '--debug' in sys.argv:
    sys.argv.remove('--debug')
    logging.getLogger().setLevel(logging.DEBUG)
  else:
    logging.getLogger().setLevel(logging.CRITICAL + 1)
  unittest.main()
