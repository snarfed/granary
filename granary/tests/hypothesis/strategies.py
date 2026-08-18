"""Shared hypothesis strategies for generating AS1 objects."""
from hypothesis import strategies as st
from hypothesis.provisional import urls

TEXT = st.text(max_size=50)
DATES = st.datetimes().map(lambda dt: dt.isoformat()) | TEXT

TAGS = st.lists(st.fixed_dictionaries({}, optional={
  'objectType': st.sampled_from(['hashtag', 'mention', 'article', 'person']),
  'displayName': TEXT,
  'url': urls(),
}), max_size=3)

ACTORS = st.fixed_dictionaries({}, optional={
  'objectType': st.sampled_from(['person', 'group']),
  'id': urls(),
  'url': urls(),
  'displayName': TEXT,
  'username': TEXT,
  'summary': TEXT,
  'email': TEXT,
  'image': urls(),
})

OBJECTS = st.fixed_dictionaries({}, optional={
  'objectType': st.sampled_from(['note', 'article', 'comment', 'image']),
  'id': urls(),
  'url': urls(),
  'displayName': TEXT,
  'title': TEXT,
  'summary': TEXT,
  'content': TEXT,
  'published': DATES,
  'updated': DATES,
  'author': ACTORS,
  'tags': TAGS,
  'image': st.lists(st.fixed_dictionaries({'url': urls()}), max_size=2),
  'inReplyTo': st.lists(st.fixed_dictionaries({'url': urls()}), max_size=2),
  'location': st.fixed_dictionaries({}, optional={
    'displayName': TEXT,
    'latitude': st.floats(min_value=-90, max_value=90),
    'longitude': st.floats(min_value=-180, max_value=180),
  }),
})
