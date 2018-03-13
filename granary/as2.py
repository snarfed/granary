"""Convert between ActivityStreams 1 and 2.

AS2: http://www.w3.org/TR/activitystreams-core/

AS1: http://activitystrea.ms/specs/json/1.0/
     http://activitystrea.ms/specs/json/schema/activity-schema.html
"""
from __future__ import unicode_literals
from past.builtins import basestring

import copy
import logging

from oauth_dropins.webutil import util

CONTEXT = 'https://www.w3.org/ns/activitystreams'


def _invert(d):
  return {v: k for k, v in d.items()}

OBJECT_TYPE_TO_TYPE = {
  'article': 'Article',
  'audio': 'Audio',
  'collection': 'Collection',
  'comment': 'Note',
  'event': 'Event',
  'image': 'Image',
  'note': 'Note',
  'person': 'Person',
  'place': 'Place',
  'video': 'Video',
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)
TYPE_TO_OBJECT_TYPE['Note'] = 'note'  # disambiguate

VERB_TO_TYPE = {
  'favorite': 'Like',
  'invite': 'Invite',
  'like': 'Like',
  'post': 'Create',
  'rsvp-maybe': 'TentativeAccept',
  'rsvp-no': 'Reject',
  'rsvp-yes': 'Accept',
  'share': 'Announce',
  'tag': 'Add',
  'update': 'Update',
}
TYPE_TO_VERB = _invert(VERB_TO_TYPE)
TYPE_TO_VERB['Like'] = 'like'  # disambiguate

def from_as1(obj, type=None, context=CONTEXT):
  """Converts an ActivityStreams 1 activity or object to ActivityStreams 2.

  Args:
    obj: dict, AS1 activity or object/
    type: string, default type if type inference can't determine a type.
    context: string, included as @context

  Returns: dict, AS2 activity or object
  """
  if not obj:
    return {}
  elif not isinstance(obj, dict):
    raise ValueError('Expected dict, got %r' % obj)

  obj = copy.deepcopy(obj)

  verb = obj.pop('verb', None)
  obj_type = obj.pop('objectType', None)
  type = (OBJECT_TYPE_TO_TYPE.get(verb or obj_type) or
          VERB_TO_TYPE.get(verb or obj_type) or
          type)

  if context:
    obj['@context'] = CONTEXT

  def all_from_as1(field, type=None):
    return [from_as1(elem, type=type, context=None)
            for elem in util.pop_list(obj, field)]

  images = all_from_as1('image', type='Image')
  obj.update({
    'type': type,
    'name': obj.pop('displayName', None),
    'actor': from_as1(obj.get('actor'), context=None),
    'attachment': all_from_as1('attachments'),
    'attributedTo': all_from_as1('author', type='Person'),
    'image': images,
    'inReplyTo': util.trim_nulls([orig.get('id') or orig.get('url')
                                  for orig in obj.get('inReplyTo', [])]),
    'object': from_as1(obj.get('object'), context=None),
    'tag': all_from_as1('tags')
  })

  if obj_type == 'person':
    # TODO: something better. (we don't know aspect ratio though.)
    obj['icon'] = images

  if obj_type in ('audio', 'video'):
    stream = util.pop_list(obj, 'stream')
    if stream:
      url = stream[0].get('url')
      if url:
        obj['url'] = url

  loc = obj.get('location')
  if loc:
    obj['location'] = from_as1(loc, type='Place', context=None)

  obj = util.trim_nulls(obj)
  if list(obj.keys()) == ['url']:
    return obj['url']

  return obj


def to_as1(obj, use_type=True):
  """Converts an ActivityStreams 2 activity or object to ActivityStreams 1.

  Args:
    obj: dict, AS2 activity or object
    use_type: boolean, whether to include objectType and verb

  Returns: dict, AS1 activity or object
  """
  if not obj:
    return {}
  elif isinstance(obj, basestring):
    return {'url': obj}
  elif not isinstance(obj, dict):
    raise ValueError('Expected dict, got %r' % obj)

  obj = copy.deepcopy(obj)

  obj.pop('@context', None)

  type = obj.pop('type', None)
  if use_type:
    obj['objectType'] = TYPE_TO_OBJECT_TYPE.get(type)
    obj['verb'] = TYPE_TO_VERB.get(type)
    if obj.get('inReplyTo') and obj['objectType'] in ('note', 'article'):
      obj['objectType'] = 'comment'
    elif obj['verb'] and not obj['objectType']:
      obj['objectType'] = 'activity'

  def url_or_as1(val):
    return {'url': val} if isinstance(val, basestring) else to_as1(val)

  def all_to_as1(field):
    return [to_as1(elem) for elem in util.pop_list(obj, field)]

  images = []
  # icon first since e.g. Mastodon uses icon for profile picture,
  # image for featured photo.
  for as2_img in util.pop_list(obj, 'icon') + util.pop_list(obj, 'image'):
    as1_img = to_as1(as2_img, use_type=False)
    if as1_img not in images:
      images.append(as1_img)

  obj.update({
    'displayName': obj.pop('name', None),
    'actor': to_as1(obj.get('actor')),
    'attachments': all_to_as1('attachment'),
    'image': images,
    'inReplyTo': [url_or_as1(orig) for orig in util.get_list(obj, 'inReplyTo')],
    'location': url_or_as1(obj.get('location')),
    'object': to_as1(obj.get('object')),
    'tags': all_to_as1('tag'),
  })

  if type in ('Audio', 'Video'):
    obj['stream'] = {'url': obj.pop('url', None)}

  attrib = util.pop_list(obj, 'attributedTo')
  if attrib:
    if len(attrib) > 1:
      logging.warning('ActivityStreams 1 only supports single author; '
                      'dropping extra attributedTo values: %s' % attrib[1:])
    obj['author'] = to_as1(attrib[0])

  return util.trim_nulls(obj)
