#!/usr/bin/env python
"""Instagram integration test against the live site.

Just checks that fetching and converting snarfed's feed includes 12 activities,
and all the expected fields are non-empty.

https://github.com/snarfed/granary/issues/106
"""
import logging
import sys
import unittest

from granary import instagram
from granary.source import SELF

USERNAME = 'snarfed'


class InstagramTestLive(unittest.TestCase):

  def test_live(self):
    resp = instagram.Instagram().get_activities_response(
      user_id=USERNAME, group_id=SELF, scrape=True,
      fetch_replies=True, fetch_likes=True)

    for field in 'username', 'displayName', 'url', 'image', 'id':
      self.assertTrue(resp['actor'][field], field)

    self.assertTrue(resp['actor']['image']['url'])

    items = resp['items']
    self.assertEqual(12, len(items))

    found = set()
    for a in items:
      self.assertTrue(a['actor'])
      for field in 'id', 'url', 'attachments', 'author', 'image':
        self.assertTrue(a['object'][field], field)
      for field in 'content', 'replies', 'tags':
        if a['object'].get(field):
          found.add(field)

    for field in 'content', 'replies', 'tags':
      self.assertIn(field, found)


if __name__ == '__main__':
  if '--debug' in sys.argv:
    sys.argv.remove('--debug')
    logging.getLogger().setLevel(logging.DEBUG)
  else:
    logging.getLogger().setLevel(logging.CRITICAL + 1)
  unittest.main()
