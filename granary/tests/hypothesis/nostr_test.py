"""Property-based tests for nostr.py, using hypothesis.

https://hypothesis.readthedocs.io/
"""
import bech32
from hypothesis import given, strategies as st
from webutil import testutil

from ...nostr import (
  BECH32_PREFIXES,
  BECH32_TLV_PREFIXES,
  bech32_decode,
  bech32_encode,
  id_to_uri,
  uri_to_id,
)

# ids and pubkeys are 32 bytes, ie 64 hex characters
IDS = st.binary(min_size=32, max_size=32).map(bytes.hex)

# bech32_encode only knows how to write the TLVs for nprofile and nevent, whose
# type 0 value is a 32 byte id. naddr's is a `d` tag, nrelay's is a relay URL.
ENCODABLE_PREFIXES = st.sampled_from(
  sorted(set(BECH32_PREFIXES) - set(BECH32_TLV_PREFIXES) | {'nevent', 'nprofile'}))


class NostrHypothesisTest(testutil.TestCase):

  @given(ENCODABLE_PREFIXES, IDS)
  def test_bech32_encode_decode_round_trips(self, prefix, id):
    self.assertEqual(id, bech32_decode(bech32_encode(prefix, id)))

  @given(ENCODABLE_PREFIXES, IDS)
  def test_id_to_uri_uri_to_id_round_trips(self, prefix, id):
    self.assertEqual(id, uri_to_id(id_to_uri(prefix, id)))

  @given(st.text())
  def test_bech32_decode_arbitrary_text(self, val):
    bech32_decode(val)

  @given(st.sampled_from(sorted(BECH32_TLV_PREFIXES)), st.binary(max_size=100))
  def test_bech32_decode_arbitrary_tlv(self, prefix, data):
    """Valid checksum, arbitrary TLV contents: decode or return unchanged."""
    encoded = bech32.bech32_encode(prefix, bech32.convertbits(data, 8, 5))
    got = bech32_decode(encoded)
    if got not in (None, encoded):
      self.assertEqual(bytes.fromhex(got), data[2:34])
