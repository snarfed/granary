#!/usr/bin/env python
"""Instagram integration test against the live site.

Just checks that fetching and converting snarfed's feed includes activities
and all the expected fields are non-empty.

https://github.com/snarfed/granary/issues/106
"""
import logging
import sys
import unittest

from oauth_dropins.webutil import util
from oauth_dropins.instagram import INSTAGRAM_SESSIONID_COOKIE
from granary import instagram
from granary.source import SELF

USERNAME = 'snarfed'


class InstagramTestLive(unittest.TestCase):

  def test_live(self):
    ig = instagram.Instagram(cookie=INSTAGRAM_SESSIONID_COOKIE)
    resp = ig.get_activities_response(
      user_id=USERNAME, group_id=SELF, scrape=True,
      fetch_replies=True, fetch_likes=True, count=10)

    for field in 'username', 'displayName', 'url', 'image', 'id':
      self.assertTrue(resp['actor'][field], field)

    self.assertTrue(resp['actor']['image']['url'])

    items = resp['items']
    self.assertGreaterEqual(10, len(items))

    found = set()
    for a in items:
      self.assertTrue(a['actor'])
      obj = a['object']
      for field in 'id', 'url', 'attachments', 'author', 'image':
        self.assertTrue([field], field)
      for field in 'content', 'replies', 'tags':
        if obj.get(field):
          found.add(field)
      likes = [t for t in obj.get('tags', []) if t.get('verb') == 'like']
      if likes:
        found.add('likes')

    for field in 'content', 'replies', 'tags', 'likes':
      self.assertIn(field, found)


if __name__ == '__main__':
  if '--debug' in sys.argv:
    sys.argv.remove('--debug')
    logging.getLogger().setLevel(logging.DEBUG)
  else:
    logging.getLogger().setLevel(logging.CRITICAL + 1)
  unittest.main()
