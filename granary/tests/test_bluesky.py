"""Unit tests for jsonfeed.py.

Most tests are via files in testdata/.
"""
from oauth_dropins.webutil import testutil

from ..bluesky import from_as1, to_as1

# app.bsky.actor.profile
# /Users/ryan/src/atproto/lexicons/app/bsky/actor/profile.json
# https://github.com/bluesky-social/atproto/blob/main/packages/pds/tests/crud.test.ts#L211-L217
#       {
#         displayName: 'alice',
#         createdAt: new Date().toISOString(),
#       },

# app.bsky.feed.post
# /Users/ryan/src/atproto/lexicons/app/bsky/feed/post.json
# https://github.com/bluesky-social/atproto/blob/main/packages/pds/tests/crud.test.ts#L74-L82
#       record: {
#         $type: 'app.bsky.feed.post',
#         text: 'Hello, world!',
#         createdAt: new Date().toISOString(),
#       },

# app.bsky.feed.repost
# /Users/ryan/src/atproto/lexicons/app/bsky/feed/repost.json
# https://github.com/bluesky-social/atproto/blob/main/packages/pds/tests/seeds/client.ts#L294-L298
#       { subject: subject.raw, createdAt: new Date().toISOString() },


# app.bsky.graph.follow
# /Users/ryan/src/atproto/lexicons/app/bsky/graph/follow.json
# https://github.com/bluesky-social/atproto/blob/main/packages/pds/tests/seeds/client.ts#L183-L190
#       {
#         subject: to.raw,
#         createdAt: new Date().toISOString(),
#       },

# # link/other embed (no test)
# app.bsky.embed.external
# /Users/ryan/src/atproto/lexicons/app/bsky/embed/external.json

# # image
# app.bsky.embed.images
# /Users/ryan/src/atproto/lexicons/app/bsky/embed/images.json
# https://github.com/bluesky-social/atproto/blob/main/packages/pds/tests/crud.test.ts#L178-L191
#       {
#         $type: 'app.bsky.feed.post',
#         text: "Here's a key!",
#         createdAt: new Date().toISOString(),
#         embed: {
#           $type: 'app.bsky.embed.images',
#           images: [
#             { image: { cid: image.cid, mimeType: 'image/jpeg' }, alt: '' },
#           ],
#         },
#       },


class TestBluesky(testutil.TestCase):

    def test_from_as1_actor_from_url(self):
        profile = from_as1({
            'objectType' : 'person',
            'displayName': 'Martin Smith',
        }, from_url='http://www.foo.com')
        self.assert_equals('foo.com', profile['handle'])

    def test_to_as1_missing_objectType(self):
        with self.assertRaises(ValueError):
            to_as1({'foo': 'bar'})

    def test_to_as1_unknown_objectType(self):
        with self.assertRaises(ValueError):
            to_as1({'objectType': 'poll'})

    def test_to_as1_missing_type(self):
        with self.assertRaises(ValueError):
            to_as1({'foo': 'bar'})

    def test_to_as1_unknown_type(self):
        with self.assertRaises(ValueError):
            to_as1({'$type': 'app.bsky.foo'})
