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
# file:///Users/ryan/docs/activitystreams_json_spec_2.0.html#deprecated-syntax

def _invert(d):
  return {v: k for k, v in d.items()}

OBJECT_TYPE_TO_TYPE = {
  'comment': 'Note',
  'person': 'Person',
  'place': 'Place',
  'event': 'Event',
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)

VERB_TO_TYPE = {
}
TYPE_TO_VERB = _invert(VERB_TO_TYPE)


def from_as1(obj, type=None, context=CONTEXT):
  """Converts an ActivityStreams 1 activity or object to ActivityStreams 2.

  Args:
    obj: dict, AS1 activity or object/
    type: string, default @type if type inference can't determine a type.
    context: string, included as @context

  Returns: dict, AS2 activity or object
  """
  if not obj:
    return {}

  obj = copy.deepcopy(obj)

  verb = obj.pop('verb', None)
  obj_type = obj.pop('objectType', None)
  type = (OBJECT_TYPE_TO_TYPE.get(verb or obj_type) or
          VERB_TO_TYPE.get(verb or obj_type) or
          type)

  if context:
    obj['@context'] = CONTEXT

  obj.update({
    '@type': type,
    '@id': obj.pop('id', None),
    'image': [from_as1(img, type='Image', context=False) for img in obj.get('image', [])],
    'inReplyTo': util.trim_nulls([orig.get('url') for orig in obj.get('inReplyTo', [])]),
  })

  loc = obj.get('location')
  if loc:
    obj['location'] = from_as1(loc, type='Place', context=False)

  return util.trim_nulls(obj)


def to_as1(obj):
  """Converts an ActivityStreams 2 activity or object to ActivityStreams 1.

  Args:
    obj: dict, AS2 activity or object

  Returns: dict, AS1 activity or object
  """
  if not obj:
    return {}

  obj = copy.deepcopy(obj)

  obj.pop('@context', None)
  type = obj.pop('@type', None)

  def url_or_as1(val):
    return {'url': val} if isinstance(val, basestring) else to_as1(val)

  obj.update({
    'id': obj.pop('@id', None),
    'objectType': TYPE_TO_OBJECT_TYPE.get(type),
    'verb': TYPE_TO_VERB.get(type),
    'image': [to_as1(img) for img in obj.get('image', [])],
    'inReplyTo': [url_or_as1(orig) for orig in util.get_list(obj, 'inReplyTo')],
    'location': url_or_as1(obj.get('location')),
  })
  return util.trim_nulls(obj)
