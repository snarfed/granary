"""Convert between ActivityStreams 1 and 2.

AS2: http://www.w3.org/TR/activitystreams-core/

AS1: http://activitystrea.ms/specs/json/1.0/
     http://activitystrea.ms/specs/json/schema/activity-schema.html
"""
import copy

from oauth_dropins.webutil import util

CONTEXT = 'https://www.w3.org/ns/activitystreams'

# STATE: use:
# file:///Users/ryan/docs/activitystreams_schema_spec_2.0.html#as1properties
# file:///Users/ryan/docs/activitystreams_json_spec_2.0.html#activitystreams-1.0
# file:///Users/ryan/docs/activitystreams_json_spec_2.0.html#deprecated-syntax

def _invert(d):
  return {v: k for k, v in d.items()}

OBJECT_TYPE_TO_TYPE = {
  'person': 'Person'
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)

VERB_TO_TYPE = {
}
TYPE_TO_VERB = _invert(VERB_TO_TYPE)


def from_as1(obj):
  """Converts an ActivityStreams 1 activity or object to ActivityStreams 2.

  Args:
    obj: dict, AS1 activity or object
    type: populated into @type. Overrides normal type inference.

  Returns: dict, AS2 activity or object
  """
  as1 = copy.deepcopy(obj)
  verb = as1.pop('verb', None)
  obj_type = as1.pop('objectType', None)
  type = (OBJECT_TYPE_TO_TYPE.get(verb or obj_type) or
          VERB_TO_TYPE.get(verb or obj_type))
  id = as1.pop('id', None)

  as2 = copy.deepcopy(as1)
  as2.update({
    '@context': CONTEXT,
    '@type': type,
    'type': type,
    '@id': id,
  })

  for image in as2.get('image', []):
    image['@type'] = 'Image'

  return util.trim_nulls(as2)


def to_as1(obj):
  """Converts an ActivityStreams 2 activity or object to ActivityStreams 1.

  Args:
    obj: dict, AS2 activity or object

  Returns: dict, AS1 activity or object
  """
  as2 = copy.deepcopy(obj)
  as2.pop('@context', None)
  as2.pop('type', None)
  type = as2.pop('@type', None)

  as1 = copy.deepcopy(as2)
  as1.update({
    'id': as1.pop('@id', None),
    'objectType': TYPE_TO_OBJECT_TYPE.get(type),
    'verb': TYPE_TO_VERB.get(type),
    'image': [to_as1(img) for img in obj.get('image', [])],
  })

  return util.trim_nulls(as1)
