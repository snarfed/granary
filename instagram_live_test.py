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
from granary.source import FRIENDS, SELF

USERNAME = 'snarfed'


class InstagramTestLive(unittest.TestCase):

  def test_live(self):
    ig = instagram.Instagram(cookie=INSTAGRAM_SESSIONID_COOKIE)

    for kwargs in ({'user_id': USERNAME, 'group_id': SELF},
                 {'group_id': FRIENDS}):
      resp = ig.get_activities_response(scrape=True, fetch_replies=True,
                                        fetch_likes=True, count=3, **kwargs)

      for field in 'username', 'displayName', 'url', 'image', 'id':
        self.assertTrue(resp['actor'][field], field)

      self.assertTrue(resp['actor']['image']['url'])

      items = resp['items']
      self.assertEqual(3, len(items))

      found = set()
      for item in items:
        self.check_item(item)
        for field in 'content', 'replies', 'tags':
          if item['object'].get(field):
            found.add(field)
        if self.likes(item):
          found.add('likes')

      for field in 'content', 'replies', 'tags', 'likes':
        self.assertIn(field, found)

    photo = ig.get_activities(scrape=True, fetch_likes=True, fetch_replies=True,
                              activity_id='byuvjTsqJo')[0]
    self.check_item(photo)
    self.assertEqual(1, len(photo['object']['replies']['items']))
    self.assertEqual(7, len(self.likes(photo)))

  def likes(self, item):
    return [t for t in item['object'].get('tags', []) if t.get('verb') == 'like']

  def check_item(self, item):
    self.assertTrue(item['actor'])
    for field in 'id', 'url', 'attachments', 'author', 'image':
      self.assertIn(field, item['object'], field)


if __name__ == '__main__':
  if '--debug' in sys.argv:
    sys.argv.remove('--debug')
    logging.getLogger().setLevel(logging.DEBUG)
  else:
    logging.getLogger().setLevel(logging.CRITICAL + 1)
  unittest.main()
