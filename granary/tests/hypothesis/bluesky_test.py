"""Property-based tests for bluesky.py, using hypothesis.

https://hypothesis.readthedocs.io/
"""
from string import ascii_letters, digits

from hypothesis import given, strategies as st
from hypothesis.provisional import domains, urls
from lexrpc.base import Base
from webutil import testutil

from ...bluesky import (
  at_uri_to_web_url,
  Bluesky,
  COLLECTION_TO_BSKY_APP_TYPE,
  did_web_to_url,
  from_as1,
  LEXRPC,
  url_to_did_web,
  web_url_to_at_uri,
)
from .strategies import ACTORS, OBJECTS, TEXT

# a separate lexrpc instance that validates, unlike bluesky.LEXRPC, so that it
# can serve as an independent oracle for from_as1's output
VALIDATOR = Base(truncate=False, validate=True)

# urlparse lower cases hostnames
HOSTS = domains().map(str.lower)
DIDS = st.from_regex(r'did:plc:[a-z2-7]{24}', fullmatch=True)
COLLECTIONS = st.sampled_from(sorted(COLLECTION_TO_BSKY_APP_TYPE))
RKEYS = st.text(alphabet=ascii_letters + digits + '.:~_-', min_size=1, max_size=16)

# objectType is optional in OBJECTS, and from_as1 raises ValueError without one,
# and on inReplyTo that isn't a Bluesky post, neither of which is what these
# tests are about. mapping instead of filtering keeps every generated example.
POSTS = st.builds(lambda obj, type: {**obj, 'objectType': type, 'inReplyTo': None},
                  OBJECTS, st.sampled_from(['note', 'article', 'comment']))

# brevity never truncates the permalink itself, so a link longer than the whole
# limit overflows it. real permalinks are nowhere near that long.
SHORT_URLS = urls().filter(lambda url: len(url) <= 100)

# HTML content with links and runs of multi-byte characters, to generate facets,
# and long enough to sometimes truncate them
LINKED_CONTENT = st.lists(
  TEXT
  | urls().map(lambda url: f'<a href="{url}">a é😀 link</a>')
  | st.builds(lambda n, char: char * n,
              st.integers(min_value=0, max_value=400), st.sampled_from('éü😀')),
  max_size=6,
).map(' '.join)


class BlueskyHypothesisTest(testutil.TestCase):

  @given(HOSTS)
  def test_url_to_did_web_round_trips(self, host):
    url = f'https://{host}/'
    self.assertEqual(url, did_web_to_url(url_to_did_web(url)))

  @given(DIDS | HOSTS, COLLECTIONS, RKEYS)
  def test_at_uri_to_web_url_round_trips(self, authority, collection, rkey):
    uri = f'at://{authority}/{collection}/{rkey}'
    self.assertEqual(uri, web_url_to_at_uri(at_uri_to_web_url(uri)))

  @given(POSTS)
  def test_from_as1_post_validates(self, obj):
    post = from_as1(obj)
    VALIDATOR.validate(post['$type'], 'record', post)

  @given(ACTORS)
  def test_from_as1_actor_validates(self, actor):
    profile = from_as1({**actor, 'objectType': 'person'})
    VALIDATOR.validate('app.bsky.actor.profile', 'record', profile)

  @given(LINKED_CONTENT)
  def test_from_as1_facet_indices_are_valid(self, content):
    post = from_as1({'objectType': 'note', 'content': content})
    text = post['text'].encode()

    for facet in post.get('facets', []):
      index = facet['index']
      start, end = index['byteStart'], index['byteEnd']
      self.assertLess(start, end)
      self.assertLessEqual(end, len(text))
      # the facet must start and end on UTF-8 character boundaries
      text[start:end].decode()

  @given(st.text(max_size=2000), SHORT_URLS)
  def test_truncate_fits_in_max_graphemes(self, content, url):
    max_graphemes = LEXRPC.defs['app.bsky.feed.post']['record']['properties']['text']['maxGraphemes']
    truncated = Bluesky('handle.com').truncate(content, url, type='note')
    self.assertLessEqual(len(truncated), max_graphemes)
