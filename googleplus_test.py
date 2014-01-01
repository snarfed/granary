"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import json
import mox

import googleplus
import source
from webutil import testutil
from webutil import util


# def tag_uri(name):
#   return util.tag_uri('plus.google.com', name)


# PLUSONER = {  # Google+
#   'kind': 'plus#person',
#   'id': '222',
#   'displayName': 'Alice',
#   'url': 'https://profiles.google.com/alice',
#   'image': {'url': 'https://alice/picture'},
#   }
# LIKE = {  # ActivityStreams
#   'id': tag_uri('001_liked_by_222'),
#   'url': 'http://plus.google.com/001',
#   'objectType': 'activity',
#   'verb': 'like',
#   'object': {'url': 'http://plus.google.com/001'},
#   'author': {
#     'id': tag_uri('222'),
#     'displayName': 'Alice',
#     'url': 'https://profiles.google.com/alice',
#     'image': {'url': 'https://alice/picture'},
#     },
#   'content': '+1ed this.',
#   }
# RESHARER = {  # Google+
#   'kind': 'plus#person',
#   'id': '444',
#   'displayName': 'Bob',
#   'url': 'https://plus.google.com/bob',
#   'image': {'url': 'https://bob/picture'},
#   }
# SHARE = {  # ActivityStreams
#   'id': tag_uri('001_shared_by_444'),
#   'url': 'http://plus.google.com/001',
#   'objectType': 'activity',
#   'verb': 'share',
#   'object': {'url': 'http://plus.google.com/001'},
#   'author': {
#     'id': '444',
#     'displayName': 'Bob',
#     'url': 'https://plus.google.com/bob',
#     'image': {'url': 'https://bob/picture'},
#     },
#   'content': 'reshared this.',
#   'published': '2013-02-24T20:26:41',
#   }

# class GooglePlusTest(testutil.HandlerTest):

#   def setUp(self):
#     super(GooglePlusTest, self).setUp()
#     self.googleplus = googleplus.GooglePlus()

#   def test_get_like(self):
#     self.expect_urlopen('https://graph.googleplus.com/000', json.dumps(POST))
#     self.mox.ReplayAll()
#     self.assert_equals(LIKE_OBJS[1], self.googleplus.get_like('123', '000', '683713'))

#   def test_get_like_not_found(self):
#     self.expect_urlopen('https://graph.googleplus.com/000', json.dumps(POST))
#     self.mox.ReplayAll()
#     self.assert_equals(None, self.googleplus.get_like('123', '000', '999'))

#   def test_get_like_no_activity(self):
#     self.expect_urlopen('https://graph.googleplus.com/000', '{}')
#     self.mox.ReplayAll()
#     self.assert_equals(None, self.googleplus.get_like('123', '000', '683713'))

#   def test_like(self):
#     activity = {
#         'id': tag_uri('10100747369806713'),
#         'verb': 'like',
#         'title': 'Unknown likes a photo.',
#         'url': 'http://googleplus.com/10100747369806713',
#         'object': {
#           'objectType': 'image',
#           'id': tag_uri('214721692025931'),
#           'url': 'http://instagram.com/p/eJfUHYh-x8/',
#           }
#         }
#     post = {
#         'id': '10100747369806713',
#         'type': 'og.likes',
#         'data': {
#           'object': {
#             'id': '214721692025931',
#             'url': 'http://instagram.com/p/eJfUHYh-x8/',
#             'type': 'instapp:photo',
#             }
#           }
#         }
#     self.assert_equals(activity, self.googleplus.post_to_activity(post))

