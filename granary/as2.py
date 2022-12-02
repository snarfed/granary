"""Convert between ActivityStreams 1 and 2.

AS2: http://www.w3.org/TR/activitystreams-core/

AS1: http://activitystrea.ms/specs/json/1.0/
     http://activitystrea.ms/specs/json/schema/activity-schema.html
"""
import copy
import datetime
import logging

from oauth_dropins.webutil import util

from . import as1

logger = logging.getLogger(__name__)

# ActivityPub Content-Type details:
# https://www.w3.org/TR/activitypub/#retrieving-objects
CONTENT_TYPE = 'application/activity+json'
CONTENT_TYPE_LD = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
CONNEG_HEADERS = {
    'Accept': f'{CONTENT_TYPE}; q=0.9, {CONTENT_TYPE_LD}; q=0.8',
}
CONTEXT = 'https://www.w3.org/ns/activitystreams'

PUBLIC_AUDIENCE = 'https://www.w3.org/ns/activitystreams#Public'
# All known Public values, cargo culted from:
# https://socialhub.activitypub.rocks/t/visibility-to-cc-mapping/284
PUBLICS = frozenset((
    PUBLIC_AUDIENCE,
    'as:Public',
    'Public',
))

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


def from_as1(obj, type=None, context=CONTEXT, top_level=True):
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
    raise ValueError(f'Expected dict, got {obj!r}')

  obj = copy.deepcopy(obj)

  verb = obj.pop('verb', None)
  obj_type = obj.pop('objectType', None)
  type = (OBJECT_TYPE_TO_TYPE.get(verb or obj_type) or
          VERB_TO_TYPE.get(verb or obj_type) or
          type)

  if context:
    obj['@context'] = context

  def all_from_as1(field, type=None):
    return [from_as1(elem, type=type, context=None, top_level=False)
            for elem in util.pop_list(obj, field)]

  inner_objs = all_from_as1('object')
  if len(inner_objs) == 1:
    inner_objs = inner_objs[0]

  obj.update({
    'type': type,
    'name': obj.pop('displayName', None),
    'actor': from_as1(obj.get('actor'), context=None, top_level=False),
    'attachment': all_from_as1('attachments'),
    'attributedTo': all_from_as1('author', type='Person'),
    'inReplyTo': util.trim_nulls([orig.get('id') or orig.get('url')
                                  for orig in obj.get('inReplyTo', [])]),
    'object': inner_objs,
    'tag': all_from_as1('tags'),
    'preferredUsername': obj.pop('username', None),
    'url': as1.object_urls(obj),
  })
  obj.pop('urls', None)

  # images; separate featured (aka header) and non-featured.
  images = util.get_list(obj, 'image')
  featured = []
  non_featured = []
  if images:
    for img in images:
      # objectType featured is non-standard; granary uses it for u-featured
      # microformats2 images
      if img.get('objectType') == 'featured':
        featured.append(img)
      else:
        non_featured.append(img)

    # prefer non-featured first for icon, featured for image. ActivityPub/Mastodon
    # use icon for profile picture, image for header.
    if obj_type == 'person':
      obj['icon'] = from_as1((non_featured or featured)[0], type='Image',
                             context=None, top_level=False)
    obj['image'] = [from_as1(img, type='Image', context=None)
                    for img in featured + non_featured]
    if len(obj['image']) == 1:
      obj['image'] = obj['image'][0]

  # other type-specific fields
  if obj_type == 'mention':
    obj['href'] = util.get_first(obj, 'url')
    obj.pop('url', None)
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
          logger.warning(f'Dropping unexpected duration {duration!r}; expected int, is {duration.__class__}')
  elif obj_type == 'person' and top_level:
    # Mastodon-specific metadata property fields
    # https://github.com/snarfed/bridgy-fed/issues/323
    obj['attachment'].extend({
      'type': 'PropertyValue',
      'name': 'Link',
      'value': util.pretty_link(url, attrs={'rel': 'me'}),
    } for url in obj['url'] if util.is_web(url))

  urls = util.get_list(obj, 'url')
  if len(urls) == 1:
    obj['url'] = urls[0]

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
    raise ValueError(f'Expected dict, got {obj!r}')

  obj = copy.deepcopy(obj)
  obj.pop('@context', None)

  type = obj.pop('type', None)
  if use_type:
    if type and not isinstance(type, str):
      raise ValueError(f'Expected type to be string, got {type!r}')
    obj['objectType'] = TYPE_TO_OBJECT_TYPE.get(type)
    obj['verb'] = TYPE_TO_VERB.get(type)
    if obj.get('inReplyTo') and obj['objectType'] in ('note', 'article'):
      obj['objectType'] = 'comment'
    elif obj['verb'] and not obj['objectType']:
      obj['objectType'] = 'activity'

  def url_or_as1(val):
    return {'url': val} if isinstance(val, str) else to_as1(val)

  def all_to_as1(field):
    return [to_as1(elem) for elem in util.pop_list(obj, field)
            if not (type == 'Person' and elem.get('type') == 'PropertyValue')]

  images = []
  # ActivityPub/Mastodon uses icon for profile picture, image for header.
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

  # attachments. if mediaType is image/..., override type
  attachments = all_to_as1('attachment')
  for att in attachments:
    if att.get('mediaType', '').split('/')[0] == 'image':
      att['objectType'] = 'image'

  obj.update({
    'displayName': obj.pop('name', None),
    'username': obj.pop('preferredUsername', None),
    'actor': actor,
    'attachments': attachments,
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
      logger.warning(f'ActivityStreams 1 only supports single author; dropping extra attributedTo values: {attrib[1:]}')
    obj.setdefault('author', {}).update(to_as1(attrib[0]))

  return util.trim_nulls(obj)


def is_public(activity):
  """Returns True if the given AS2 object or activity is public, False otherwise.

  Args:
    activity: dict, AS2 activity or object
  """
  if not isinstance(activity, dict):
    return False

  audience = util.get_list(activity, 'to') + util.get_list(activity, 'cc')
  obj = activity.get('object')
  if isinstance(obj, dict):
    audience.extend(util.get_list(obj, 'to') + util.get_list(obj, 'cc'))

  return bool(PUBLICS.intersection(audience))

