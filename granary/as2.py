"""Convert between ActivityStreams 1 and 2.

AS2: http://www.w3.org/TR/activitystreams-core/

AS1: http://activitystrea.ms/specs/json/1.0/
     http://activitystrea.ms/specs/json/schema/activity-schema.html
"""
import copy
import datetime
import logging

from oauth_dropins.webutil import util

# ActivityPub Content-Type details:
# https://www.w3.org/TR/activitypub/#retrieving-objects
CONTENT_TYPE = 'application/activity+json'
CONTENT_TYPE_LD = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
CONNEG_HEADERS = {
    'Accept': '%s; q=0.9, %s; q=0.8' % (CONTENT_TYPE, CONTENT_TYPE_LD),
}
CONTEXT = 'https://www.w3.org/ns/activitystreams'


def _invert(d):
  return {v: k for k, v in d.items()}

OBJECT_TYPE_TO_TYPE = {
  'article': 'Article',
  'audio': 'Audio',
  'collection': 'Collection',
  'comment': 'Note',
  'event': 'Event',
  'hashtag': 'Tag',  # not in AS2 spec; needed for correct round trip conversion
  'image': 'Image',
  # not in AS1 spec; needed to identify mentions in eg Bridgy Fed
  'mention': 'Mention',
  'note': 'Note',
  'person': 'Person',
  'place': 'Place',
  'video': 'Video',
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)
TYPE_TO_OBJECT_TYPE['Note'] = 'note'  # disambiguate

VERB_TO_TYPE = {
  'favorite': 'Like',
  'follow': 'Follow',
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
    obj: dict, AS1 activity or object
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
    obj['@context'] = context

  def all_from_as1(field, type=None):
    return [from_as1(elem, type=type, context=None)
            for elem in util.pop_list(obj, field)]

  images = all_from_as1('image', type='Image')
  inner_objs = all_from_as1('object')
  if len(inner_objs) == 1:
    inner_objs = inner_objs[0]

  obj.update({
    'type': type,
    'name': obj.pop('displayName', None),
    'actor': from_as1(obj.get('actor'), context=None),
    'attachment': all_from_as1('attachments'),
    'attributedTo': all_from_as1('author', type='Person'),
    'image': images,
    'inReplyTo': util.trim_nulls([orig.get('id') or orig.get('url')
                                  for orig in obj.get('inReplyTo', [])]),
    'object': inner_objs,
    'tag': all_from_as1('tags'),
    'preferredUsername': obj.pop('username', None),
  })

  if obj_type == 'person':
    # TODO: something better. (we don't know aspect ratio though.)
    obj['icon'] = images
  elif obj_type == 'mention':
    obj['href'] = obj.pop('url', None)
  elif obj_type in ('audio', 'video'):
    stream = util.pop_list(obj, 'stream')
    if stream:
      obj.update({
        'url': stream[0].get('url'),
        # file size in bytes. nonstandard, not in AS2 proper
        'size': stream[0].get('size'),
      })
      duration = stream[0].get('duration')
      if duration:
        try:
          # ISO 8601 duration
          # https://www.w3.org/TR/activitystreams-vocabulary/#dfn-duration
          # https://en.wikipedia.org/wiki/ISO_8601#Durations
          obj['duration'] = util.to_iso8601_duration(
            datetime.timedelta(seconds=duration))
        except TypeError:
          logging.warning('Dropping unexpected duration %r; expected int, is %s',
                          duration, duration.__class__)

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
  elif isinstance(obj, str):
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
    return {'url': val} if isinstance(val, str) else to_as1(val)

  def all_to_as1(field):
    return [to_as1(elem) for elem in util.pop_list(obj, field)]

  images = []
  # icon first since e.g. Mastodon uses icon for profile picture,
  # image for featured photo.
  for as2_img in util.pop_list(obj, 'icon') + util.pop_list(obj, 'image'):
    as1_img = to_as1(as2_img, use_type=False)
    if as1_img not in images:
      images.append(as1_img)

  # inner objects
  inner_objs = all_to_as1('object')
  actor = to_as1(obj.get('actor', {}))

  if type == 'Create':
    for inner_obj in inner_objs:
      inner_obj.setdefault('author', {}).update(actor)

  if len(inner_objs) == 1:
    inner_objs = inner_objs[0]

  obj.update({
    'displayName': obj.pop('name', None),
    'username': obj.pop('preferredUsername', None),
    'actor': actor,
    'attachments': all_to_as1('attachment'),
    'image': images,
    'inReplyTo': [url_or_as1(orig) for orig in util.get_list(obj, 'inReplyTo')],
    'location': url_or_as1(obj.get('location')),
    'object': inner_objs,
    'tags': all_to_as1('tag'),
  })

  # media
  if type in ('Audio', 'Video'):
    duration = util.parse_iso8601_duration(obj.pop('duration', None))
    if duration:
      duration = duration.total_seconds()
    obj['stream'] = {
      'url': obj.pop('url', None),
      # file size in bytes. nonstandard, not in AS1 proper
      'size': obj.pop('size', None),
      'duration': duration or None,
    }
  elif type == 'Mention':
    obj['url'] = obj.pop('href', None)

  # object author
  attrib = util.pop_list(obj, 'attributedTo')
  if attrib:
    if len(attrib) > 1:
      logging.warning('ActivityStreams 1 only supports single author; '
                      'dropping extra attributedTo values: %s' % attrib[1:])
    obj.setdefault('author', {}).update(to_as1(attrib[0]))

  return util.trim_nulls(obj)
