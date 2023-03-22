"""Convert between ActivityStreams 1 and 2, including ActivityPub.

AS2: http://www.w3.org/TR/activitystreams-core/
     https://www.w3.org/TR/activitypub/
     https://activitypub.rocks/

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
CONTENT_TYPE_LD = 'application/ld+json;profile="https://www.w3.org/ns/activitystreams"'
CONNEG_HEADERS = {
    'Accept': f'{CONTENT_TYPE}; q=0.9, {CONTENT_TYPE_LD}; q=0.8',
}
CONTEXT = 'https://www.w3.org/ns/activitystreams'

PUBLIC_AUDIENCE = 'https://www.w3.org/ns/activitystreams#Public'
# All known Public values, cargo culted from:
# https://socialhub.activitypub.rocks/t/visibility-to-cc-mapping/284
# https://docs.joinmastodon.org/spec/activitypub/#properties-used
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
  # not in AS2 spec; needed for correct round trip conversion
  'hashtag': 'Tag',
  'image': 'Image',
  # not in AS1 spec; needed to identify mentions in eg Bridgy Fed
  'mention': 'Mention',
  'note': 'Note',
  'organization': 'Organization',
  'person': 'Person',
  'place': 'Place',
  'question': 'Question',
  'video': 'Video',
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)
TYPE_TO_OBJECT_TYPE['Note'] = 'note'  # disambiguate

VERB_TO_TYPE = {
  'accept': 'Accept',
  'delete': 'Delete',
  'favorite': 'Like',
  'follow': 'Follow',
  'invite': 'Invite',
  'like': 'Like',
  'post': 'Create',
  'rsvp-maybe': 'TentativeAccept',
  'reject': 'Reject',
  'rsvp-no': 'Reject',
  'rsvp-yes': 'Accept',
  'share': 'Announce',
  'tag': 'Add',
  # not in AS1 spec; undo isn't a real AS1 verb
  # https://activitystrea.ms/specs/json/schema/activity-schema.html#verbs
  'undo': 'Undo',
  'update': 'Update',
}
TYPE_TO_VERB = _invert(VERB_TO_TYPE)
# disambiguate
TYPE_TO_VERB.update({
  'Accept': 'accept',
  'Like': 'like',
  'Reject': 'reject',
})


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
  elif isinstance(obj, str):
    return obj
  elif not isinstance(obj, dict):
    raise ValueError(f'Expected dict, got {obj!r}')

  obj = copy.deepcopy(obj)
  actor = obj.get('actor')
  verb = obj.pop('verb', None)
  obj_type = obj.pop('objectType', None)
  type = (OBJECT_TYPE_TO_TYPE.get(verb or obj_type) or
          VERB_TO_TYPE.get(verb or obj_type) or
          type)

  if context:
    obj['@context'] = context

  def all_from_as1(field, type=None, top_level=False):
    return [from_as1(elem, type=type, context=None, top_level=top_level)
            for elem in util.pop_list(obj, field)]

  inner_objs = all_from_as1('object', top_level=top_level)
  if len(inner_objs) == 1:
    inner_objs = inner_objs[0]
    if verb == 'stop-following':
      type = 'Undo'
      inner_objs = {
        '@context': context,
        'type': 'Follow',
        'actor': actor.get('id') if isinstance(actor, dict) else actor,
        'object': inner_objs.get('id'),
      }

  replies = obj.get('replies', {})

  # to/cc audience, all ids, special caste public/unlisted
  to = sorted(as1.get_ids(obj, 'to'))
  cc = sorted(as1.get_ids(obj, 'cc'))
  to_aliases = [to.get('alias') for to in util.pop_list(obj, 'to')]
  if '@public' in to_aliases and PUBLIC_AUDIENCE not in to:
    to.append(PUBLIC_AUDIENCE)
  elif '@unlisted' in to_aliases and PUBLIC_AUDIENCE not in cc:
    cc.append(PUBLIC_AUDIENCE)

  in_reply_to = util.trim_nulls(all_from_as1('inReplyTo'))
  if len(in_reply_to) == 1:
    in_reply_to = in_reply_to[0]

  attachments = all_from_as1('attachments')

  # Mastodon profile metadata fields
  # https://docs.joinmastodon.org/spec/activitypub/#PropertyValue
  # https://github.com/snarfed/bridgy-fed/issues/323
  if obj_type == 'person' and top_level:
    links = {}
    for link in as1.get_objects(obj, 'url') + as1.get_objects(obj, 'urls'):
      url = link.get('value') or link.get('id')
      name = link.get('displayName')
      if util.is_web(url):
        links[url] = {
          'type': 'PropertyValue',
          'name': name or 'Link',
          'value': util.pretty_link(url, attrs={'rel': 'me'}),
        }
    attachments.extend(links.values())

  # urls
  urls = as1.object_urls(obj)
  if len(urls) == 1:
    urls = urls[0]

  obj.update({
    'type': type,
    'name': obj.pop('displayName', None),
    'actor': from_as1(actor, context=None, top_level=False),
    'attachment': attachments,
    'attributedTo': all_from_as1('author', type='Person'),
    'inReplyTo': in_reply_to,
    'object': inner_objs,
    'tag': all_from_as1('tags'),
    'preferredUsername': obj.pop('username', None),
    'url': urls,
    'urls': None,
    'replies': from_as1(replies, context=None),
    'mediaType': obj.pop('mimeType', None),
    'to': to,
    'cc': cc,
  })

  # question (poll) responses
  # HACK: infer single vs multiple choice from whether
  # votersCount matches the sum of votes for each option. not ideal!
  voters = obj.get('votersCount')
  votes = sum(opt.get('replies', {}).get('totalItems', 0)
              for opt in util.get_list(obj, 'options'))
  vote_field = 'oneOf' if voters == votes else 'anyOf'
  obj[vote_field] = all_from_as1('options')

  # images; separate featured (aka header) and non-featured.
  images = util.get_list(obj, 'image')
  featured = []
  non_featured = []
  if images:
    for img in images:
      # objectType featured is non-standard; granary uses it for u-featured
      # microformats2 images
      if isinstance(img, dict) and img.get('objectType') == 'featured':
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

  # location
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
  def all_to_as1(field):
    return [to_as1(elem) for elem in util.pop_list(obj, field)
            if not (type == 'Person' and elem.get('type') == 'PropertyValue')]

  if not obj:
    return {}
  elif isinstance(obj, str):
    return obj
  elif not isinstance(obj, dict):
    raise ValueError(f'Expected dict, got {obj!r}')

  obj = copy.deepcopy(obj)
  obj.pop('@context', None)

  # type to objectType + verb
  type = obj.pop('type', None)
  if use_type:
    if type and not isinstance(type, str):
      raise ValueError(f'Expected type to be string, got {type!r}')
    obj['objectType'] = TYPE_TO_OBJECT_TYPE.get(type)
    obj['verb'] = TYPE_TO_VERB.get(type)
    inner_obj = as1.get_object(obj)
    if obj.get('inReplyTo') and obj['objectType'] in ('note', 'article'):
      obj['objectType'] = 'comment'
    elif inner_obj.get('type') == 'Event':
      if type == 'Accept':
        obj['verb'] = 'rsvp-yes'
      elif type == 'Reject':
        obj['verb'] = 'rsvp-no'
    if obj['verb'] and not obj['objectType']:
      obj['objectType'] = 'activity'

  # attachments: media, with mediaType image/... or video/..., override type. Eg
  # Mastodon video attachments have type Document (!)
  # https://docs.joinmastodon.org/spec/activitypub/#properties-used
  media_type = obj.pop('mediaType', None)
  if media_type:
    media_type_prefix = media_type.split('/')[0]
    if media_type_prefix in ('audio', 'image', 'video'):
      type = media_type_prefix.capitalize()
      obj.update({
        'objectType': media_type_prefix,
        'mimeType': media_type,
      })

  # attachments: Mastodon profile metadata fields, with type PropertyValue.
  # https://docs.joinmastodon.org/spec/activitypub/#PropertyValue
  #
  # populate into corresponding URL in url/urls fields. have to do this one one
  # level up, in the parent's object, because its data goes into the parent's
  # url/urls fields
  names = {}
  for att in util.get_list(obj, 'attachment'):
    name = att.get('name')
    value = att.get('value')
    if att.get('type') == 'PropertyValue' and value and name and name != 'Link':
      a = util.parse_html(value).find('a')
      if a and a.get('href'):
        names[a['href']] = name

  urls = [{'displayName': names[url], 'value': url} if url in names
          else url
          for url in util.get_list(obj, 'url')]

  # ActivityPub/Mastodon uses icon for profile picture, image for header.
  as1_images = []
  image_urls = set()
  icons = util.pop_list(obj, 'icon')
  images = util.pop_list(obj, 'image')
  # by convention, first element in AS2 images field is banner/header
  if type == 'Person' and images:
    images[0]['objectType'] = 'featured'

  for as2_img in icons + images:
    as1_img = to_as1(as2_img, use_type=False)
    url = util.get_url(as1_img)
    if url not in image_urls:
      as1_images.append(as1_img)
      image_urls.add(url)

  # inner objects
  inner_objs = all_to_as1('object')
  actor = to_as1(as1.get_object(obj, 'actor'))

  if type in ('Create', 'Update'):
    for inner_obj in inner_objs:
      if inner_obj.get('objectType') not in as1.ACTOR_TYPES:
        inner_obj.setdefault('author', {}).update(actor)

  if len(inner_objs) == 1:
    inner_objs = inner_objs[0]
    # special case Undo Follow
    if type == 'Undo' and inner_objs.get('verb') == 'follow':
      obj['verb'] = 'stop-following'
      inner_inner_obj = as1.get_object(inner_objs)
      inner_objs = {
        'id': (inner_inner_obj.get('id') or util.get_url(inner_inner_obj, 'url')
               if isinstance(inner_inner_obj, dict) else inner_inner_obj),
      }

  # audience, public or unlisted or neither
  to = sorted(util.get_list(obj, 'to'))
  cc = sorted(util.get_list(obj, 'cc'))
  as1_to = [{'id': val} for val in to]
  as1_cc = [{'id': val} for val in cc]
  if PUBLICS.intersection(to):
    as1_to.append({'objectType': 'group', 'alias': '@public'})
  elif PUBLICS.intersection(cc):
    as1_to.append({'objectType': 'group', 'alias': '@unlisted'})

  obj.update({
    'displayName': obj.pop('name', None),
    'username': obj.pop('preferredUsername', None),
    'actor': actor['id'] if actor.keys() == set(['id']) else actor,
    'attachments': all_to_as1('attachment'),
    'image': as1_images,
    'inReplyTo': [to_as1(orig) for orig in util.get_list(obj, 'inReplyTo')],
    'location': to_as1(obj.get('location')),
    'object': inner_objs,
    'tags': all_to_as1('tag'),
    'to': as1_to,
    'cc': as1_cc,
    # question (poll) responses
    'options': all_to_as1('anyOf') + all_to_as1('oneOf'),
    'replies': to_as1(obj.get('replies')),
    'url': urls[0] if urls else None,
    'urls': urls if len(urls) > 1 else None,
  })

  # media
  if type in ('Audio', 'Video'):  # this may have been set above
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
    attrib_as1 = to_as1(attrib[0])
    obj.setdefault('author', {}).update(attrib_as1 if isinstance(attrib_as1, dict)
                                        else {'id': attrib_as1})

  return util.trim_nulls(obj)


def is_public(activity):
  """Returns True if the given AS2 object or activity is public or unlisted.

  https://docs.joinmastodon.org/spec/activitypub/#properties-used

  Args:
    activity: dict, AS2 activity or object
  """
  if not isinstance(activity, dict):
    return False

  audience = util.get_list(activity, 'to') + util.get_list(activity, 'cc')
  obj = as1.get_object(activity)
  audience.extend(util.get_list(obj, 'to') + util.get_list(obj, 'cc'))

  return bool(PUBLICS.intersection(audience))
