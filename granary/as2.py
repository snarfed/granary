"""Convert between ActivityStreams 1 and 2, including ActivityPub.

* AS2:
   * http://www.w3.org/TR/activitystreams-core/
   * https://www.w3.org/TR/activitypub/
   * https://activitypub.rocks/
* AS1:
   * http://activitystrea.ms/specs/json/1.0/
   * http://activitystrea.ms/specs/json/schema/activity-schema.html
"""
import copy
import datetime
import logging
from os.path import splitext
import re
from urllib.parse import urlparse

from oauth_dropins.webutil import util

from . import as1
from .source import html_to_text, Source

logger = logging.getLogger(__name__)

# ActivityPub Content-Type details:
# https://www.w3.org/TR/activitypub/#retrieving-objects
CONTENT_TYPE = 'application/activity+json'
CONTENT_TYPE_LD = 'application/ld+json'
CONTENT_TYPES = (CONTENT_TYPE, CONTENT_TYPE_LD)
CONTENT_TYPE_LD_PROFILE = 'application/ld+json; profile="https://www.w3.org/ns/activitystreams"'
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept
CONNEG_HEADERS = {
    'Accept': f'{CONTENT_TYPE}, {CONTENT_TYPE_LD_PROFILE}',
}
CONTEXT = 'https://www.w3.org/ns/activitystreams'
MISSKEY_QUOTE_CONTEXT = {'_misskey_quote': 'https://misskey-hub.net/ns#_misskey_quote'}
# https://swicg.github.io/miscellany/#sensitive
SENSITIVE_CONTEXT = {'sensitive': 'as:sensitive'}

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

# https://www.w3.org/TR/activitystreams-core/#actors
OBJECT_TYPE_TO_TYPE = {
  'application': 'Application',
  'article': 'Article',
  'audio': 'Audio',
  'collection': 'Collection',
  'comment': 'Note',
  'event': 'Event',
  'group': 'Group',
  # not in AS2 spec; needed for correct round trip conversion
  'hashtag': 'Tag',
  'image': 'Image',
  'link': 'Link',
  # not in AS1 spec; needed to identify mentions in eg Bridgy Fed
  'mention': 'Mention',
  'note': 'Note',
  'organization': 'Organization',
  'page': 'Page',
  'person': 'Person',
  'place': 'Place',
  'question': 'Question',
  'service': 'Service',
  'video': 'Video',
}
TYPE_TO_OBJECT_TYPE = _invert(OBJECT_TYPE_TO_TYPE)
TYPE_TO_OBJECT_TYPE['Note'] = 'note'  # disambiguate
ACTOR_TYPES = {as2_type for as1_type, as2_type in OBJECT_TYPE_TO_TYPE.items()
               if as1_type in as1.ACTOR_TYPES}
# https://www.w3.org/TR/activitystreams-vocabulary/#object-types
URL_TYPES = ['Article', 'Audio', 'Image', 'Mention', 'Video']

VERB_TO_TYPE = {
  'accept': 'Accept',
  'add': 'Add',
  'block': 'Block',
  'delete': 'Delete',
  'favorite': 'Like',
  # not in AS1 spec
  # https://docs.joinmastodon.org/spec/activitypub/#Flag
  'flag': 'Flag',
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
  'Add': 'add',
  'Like': 'like',
  'Reject': 'reject',
})
TYPES_WITH_OBJECT = {VERB_TO_TYPE[v] for v in as1.VERBS_WITH_OBJECT
                     if v in VERB_TO_TYPE}
CRUD_VERBS = {VERB_TO_TYPE[v] for v in as1.CRUD_VERBS}

# https://github.com/mastodon/mastodon/blob/b4c332104a8b3748f619de250f77c0acc8e80628/app/models/concerns/account/avatar.rb#L6
MASTODON_ALLOWED_IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
MASTODON_ALLOWED_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/gif', 'image/webp')

# https://codeberg.org/fediverse/fep/src/branch/main/fep/e232/fep-e232.md#user-content-examples
QUOTE_RE_SUFFIX = re.compile(r'\s+RE: <?[^\s]+>?\s?$')

# https://socialhub.activitypub.rocks/t/fep-d556-server-level-actor-discovery-using-webfinger/3861/3
# https://codeberg.org/fediverse/fep/src/branch/main/fep/d556/fep-d556.md
SERVER_ACTOR_PREFIXES = (
  '/',
  '/accounts/peertube',
  '/actor',
  '/i/actor',
  '/internal/fetch',
  '/wp-json/activitypub/1.0/application',
)


def get_urls(obj, key='url'):
  """Returns ``link['href']`` or ``link``, for each ``link`` in ``obj[key]``."""
  return util.dedupe_urls(link.get('href') if isinstance(link, dict) else link
                          for link in util.get_list(obj, key))


def from_as1(obj, type=None, context=CONTEXT, top_level=True):
  """Converts an ActivityStreams 1 activity or object to ActivityStreams 2.

  Args:
    obj (dict): AS1 activity or object
    type (str): default type if type inference can't determine a type.
    context (str): included as ``@context``

  Returns:
    dict: AS2 activity or object
  """
  if not obj:
    return {}
  elif isinstance(obj, str):
    if type in URL_TYPES:
      obj = {'type': type, 'url': obj}
    else:
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

  def all_from_as1(field, type=None, top_level=False, compact=False):
    got = [from_as1(elem, type=type, context=None, top_level=top_level)
           for elem in util.pop_list(obj, field)]
    return got[0] if compact and len(got) == 1 else got

  inner_objs = all_from_as1('object', top_level=top_level, compact=True)
  if verb == 'stop-following':
    type = 'Undo'
    inner_objs = {
      '@context': context,
      'type': 'Follow',
      'actor': actor.get('id') if isinstance(actor, dict) else actor,
      'object': inner_objs.get('id') if isinstance(inner_objs, dict) else inner_objs,
    }

  replies = obj.get('replies', {})

  # to/cc audience, all ids, special caste public/unlisted
  to = sorted(as1.get_ids(obj, 'to'))
  cc = sorted(as1.get_ids(obj, 'cc'))
  to_aliases = [to.get('alias') for to in util.pop_list(obj, 'to')
                if isinstance(to, dict)]
  if '@public' in to_aliases and PUBLIC_AUDIENCE not in to:
    to.append(PUBLIC_AUDIENCE)
  elif '@unlisted' in to_aliases and PUBLIC_AUDIENCE not in cc:
    cc.append(PUBLIC_AUDIENCE)

  in_reply_to = util.trim_nulls(all_from_as1('inReplyTo', compact=True))

  # tags and attachments. extract quoted posts from attachments
  # https://codeberg.org/fediverse/fep/src/branch/main/fep/e232/fep-e232.md
  tags = all_from_as1('tags')
  atts = util.pop_list(obj, 'attachments')
  attachments = []
  quotes = []
  quote_url = None
  for att in atts:
    id = att.get('id')
    url = att.get('url')
    href = id or url
    if att.get('objectType') == 'note' and href:
      quote = from_as1(att, context=None, top_level=False)
      quote.update({
        'type': 'Link',
        'mediaType': CONTENT_TYPE_LD_PROFILE,
        'href': href,
      })

      if not quotes:
        # first quote, add it to top level object
        obj.update({
          '@context': util.get_list(obj, '@context') + [MISSKEY_QUOTE_CONTEXT],
          # https://misskey-hub.net/ns#_misskey_quote
          '_misskey_quote': href,
          # https://socialhub.activitypub.rocks/t/repost-share-with-quote-a-k-a-attach-someone-elses-post-to-your-own-post/659/19
          'quoteUrl': href,
        })
        content = obj.setdefault('content', '')
        if not QUOTE_RE_SUFFIX.search(html_to_text(content)):
          if content:
            obj['content'] += '<br><br>'
          url = url or id
          obj['content'] += f'RE: <a href="{url}">{url}</a>'
          quote['name'] = f'RE: {url}'

      quote.pop('id', None)
      quote.pop('url', None)
      quotes.append(quote)

    else:  # not a quote
      attachments.append(from_as1(att, context=None, top_level=False))

  tags.extend(quotes)

  # Mastodon profile metadata fields into attachments
  # https://docs.joinmastodon.org/spec/activitypub/#PropertyValue
  # https://github.com/snarfed/bridgy-fed/issues/323
  #
  # Note that the *anchor text* in the HTML in value, not just the href, must
  # contain the full URL! Mastodon requires that for profile link verification,
  # so that the visible URL people see matches the actual link.
  # https://github.com/snarfed/bridgy-fed/issues/560
  if obj_type in as1.ACTOR_TYPES and top_level:
    links = {}
    for link in as1.get_objects(obj, 'url') + as1.get_objects(obj, 'urls'):
      url = link.get('value') or link.get('id')
      name = link.get('displayName')
      if util.is_web(url):
        parsed = urlparse(url)
        if parsed.path == '/':
          url = url.removesuffix('/')
        scheme = f'{parsed.scheme}://'
        visible = url.removeprefix(scheme)
        links[url] = {
          'type': 'PropertyValue',
          'name': name or 'Link',
          'value': f'<a rel="me" href="{url}"><span class="invisible">{scheme}</span>{visible}</a>',
        }

        pv_context = {
          'schema': 'http://schema.org#',
          'PropertyValue': 'schema:PropertyValue'
        }
        context = util.get_list(obj, '@context')
        if context and pv_context not in context:
          obj['@context'] = context + [pv_context]

    attachments.extend(links.values())

  # urls
  urls = as1.object_urls(obj)
  if len(urls) == 1:
    urls = urls[0]

  display_name = obj.pop('displayName', None)
  title = obj.pop('title', None)

  obj.update({
    'type': type,
    'name': display_name or title,
    'actor': from_as1(actor, context=None, top_level=False),
    'attachment': attachments,
    'attributedTo': all_from_as1('author', type='Person', compact=True),
    'inReplyTo': in_reply_to,
    'object': inner_objs,
    'tag': tags,
    # note that preferredUsername comes from ActivityPub, not AS2
    # https://www.w3.org/TR/activitypub/#actor-objects
    # ...and username isn't officially in AS1
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

  # images. separate featured (aka header) and non-featured, prioritize types
  # that Mastodon allowlists
  images = util.get_list(obj, 'image')
  if images:
    featured = []
    non_featured = []
    icon = None

    for img in images:
      # objectType featured is non-standard; granary uses it for u-featured
      # microformats2 images
      if isinstance(img, dict) and img.get('objectType') == 'featured':
        featured.append(img)
        continue

      non_featured.append(img)

      if not icon:
        img_url = img if isinstance(img, str) else img.get('url')
        ext = splitext(urlparse(img_url).path)[1]
        if ((isinstance(img, dict)
             and img.get('mimeType') in MASTODON_ALLOWED_IMAGE_TYPES)
            or ext in MASTODON_ALLOWED_IMAGE_EXTS):
          icon = img

    # prefer non-featured first for icon, featured for image. ActivityPub/Mastodon
    # use icon for profile picture, image for header.
    if obj_type in as1.ACTOR_TYPES:
      obj['icon'] = from_as1(icon or (non_featured + featured)[0], type='Image',
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

  # sensitive
  # https://swicg.github.io/miscellany/#sensitive
  if 'sensitive' in obj:
    obj['@context'] = util.get_list(obj, '@context') + [SENSITIVE_CONTEXT]

  obj = util.trim_nulls(obj)
  if list(obj.keys()) == ['url']:
    return obj['url']

  return obj


def to_as1(obj, use_type=True):
  """Converts an ActivityStreams 2 activity or object to ActivityStreams 1.

  Args:
    obj (dict): AS2 activity or object
    use_type (bool): whether to include ``objectType`` and ``verb``

  Returns:
    dict: AS1 activity or object
  """
  def all_to_as1(field):
    return [to_as1(elem) for elem in util.pop_list(obj, field)
            if not (type in ACTOR_TYPES and elem.get('type') == 'PropertyValue')]

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
      obj['mimeType'] = media_type
      # don't override featured objectType for banner
      if obj.get('objectType') != 'featured':
        obj['objectType'] = media_type_prefix

  # attachments: Mastodon profile metadata fields, with type PropertyValue.
  # https://docs.joinmastodon.org/spec/activitypub/#PropertyValue
  #
  # populate into corresponding URL in url/urls fields. have to do this one one
  # level up, in the parent's object, because its data goes into the parent's
  # url/urls fields
  names = {}
  attachments = util.get_list(obj, 'attachment')
  for att in attachments:
    name = att.get('name')
    value = att.get('value')
    if (att.get('type') == 'PropertyValue' and name and name != 'Link'
        and value and isinstance(value, str)):
      a = util.parse_html(value).find('a')
      if a and a.get('href'):
        names[a['href']] = name

  urls = [{'displayName': names[url], 'value': url} if url in names else url
          for url in get_urls(obj)]

  # media links. more for them is populated below!
  if type in ('Audio', 'Video'):
    for link in util.get_list(obj, 'url'):
      if isinstance(link, dict):
        for tag in util.get_list(link, 'tag'):
          media_type = tag.get('mediaType') or ''
          href = tag.get('href')
          if media_type.split('/')[0] == type.lower():
            obj['stream'] = {'url': href}
            obj['mimeType'] = media_type
            break

  # ActivityPub/Mastodon uses icon for profile picture, image for header.
  as1_images = []
  image_urls = set()
  icons = util.pop_list(obj, 'icon')
  images = util.pop_list(obj, 'image')
  # by convention, first element in AS2 images field is banner/header
  if type in ACTOR_TYPES and images:
    if isinstance(images[0], str):
      images[0] = {'url': images[0]}
    images[0]['objectType'] = 'featured'

  img_atts = [a for a in attachments
              if a.get('type') == 'Image'
              or (a.get('mediaType') or '').startswith('image/')]
  for as2_img in icons + images + img_atts:
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
      if (isinstance(inner_obj, dict)
          and inner_obj.get('objectType') not in as1.ACTOR_TYPES):
        author = inner_obj.setdefault('author', {})
        if isinstance(author, dict):
          author.update(actor)

  if len(inner_objs) == 1:
    inner_objs = inner_objs[0]
    # special case Undo Follow
    if (type == 'Undo' and isinstance(inner_objs, dict)
        and inner_objs.get('verb') == 'follow'):
      obj['verb'] = 'stop-following'
      inner_inner_obj = as1.get_object(inner_objs)
      inner_objs = (inner_inner_obj.get('id') or util.get_url(inner_inner_obj, 'url')
                    if isinstance(inner_inner_obj, dict) else inner_inner_obj)

  # audience, public or unlisted or neither
  to = sorted(as1.get_ids(obj, 'to'))
  cc = sorted(as1.get_ids(obj, 'cc'))
  as1_to = [{'id': val} for val in to]
  as1_cc = [{'id': val} for val in cc]
  if PUBLICS.intersection(to):
    as1_to.append({'objectType': 'group', 'alias': '@public'})
  elif PUBLICS.intersection(cc):
    as1_to.append({'objectType': 'group', 'alias': '@unlisted'})

  # note that preferredUsername is in ActivityPub, not AS2
  # https://www.w3.org/TR/activitypub/#actor-objects
  preferred_username = obj.pop('preferredUsername', None)
  displayName = obj.pop('name', None) or preferred_username
  if not displayName and obj.get('objectType') in as1.ACTOR_TYPES:
    displayName = address(obj)

  # attachments, tags
  attachments = all_to_as1('attachment')
  tags_as1 = []
  quote_urls = []
  for tag in util.pop_list(obj, 'tag'):
    if isinstance(tag, str):
      tags_as1.append(tag)

    elif (tag.get('type') == 'Link'  # TODO: Link subtypes?
          and tag.get('mediaType') in (CONTENT_TYPE_LD_PROFILE, CONTENT_TYPE)
          and tag.get('href')):
      # quoted post
      # https://codeberg.org/fediverse/fep/src/branch/main/fep/e232/fep-e232.md
      quote = to_as1(tag)
      url = quote.pop('href')
      quote_urls.append(url)
      quote.update({
        'objectType': 'note',
        'id': url,
        'displayName': None,
      })
      attachments.append(quote)

      # remove RE: ... text suffix if it's there
      #
      # TODO: do full HTML parsing of content, look for innerText that matches
      # name, and update those links' targets. that's technically FEP-e232's
      # intent, but way too complicated for right now.
      # https://socialhub.activitypub.rocks/t/fep-e232-object-links/2722/29
      obj.setdefault('content', '')
      obj['content'] = re.sub(
        fr'(\s|(<br>)+)?RE: (</span>)?(<a href="{url}">)?<?{url}>?(</a>)?\s?$', '',
        obj['content'])
      continue

    else:
      # other tag
      tags_as1.append(to_as1({
        'url': tag.pop('href', None),
        'name': tag.pop('tag', None),  # rare
        **tag,
      }))

  # check quote post fields on the top level object
  # https://misskey-hub.net/ns#_misskey_quote
  # https://socialhub.activitypub.rocks/t/repost-share-with-quote-a-k-a-attach-someone-elses-post-to-your-own-post/659/19
  for quote_field in '_misskey_quote', 'quoteUrl':
    if quote_url := obj.pop(quote_field, None):
      if quote_url not in quote_urls:
        attachments.append({
          'objectType': 'note',
          'url': quote_url,
        })
        quote_urls.append(quote_url)

  obj.update({
    'displayName': displayName,
    # username isn't officially in AS1
    'username': preferred_username,
    'actor': actor['id'] if actor.keys() == set(['id']) else actor,
    'attachments': attachments,
    'image': as1_images,
    'inReplyTo': [to_as1(orig) for orig in util.get_list(obj, 'inReplyTo')],
    'location': to_as1(obj.get('location')),
    'object': inner_objs,
    'tags': tags_as1,
    'to': as1_to,
    'cc': as1_cc,
    # question (poll) responses
    'options': all_to_as1('anyOf') + all_to_as1('oneOf'),
    'replies': to_as1(obj.get('replies')),
    'url': urls[0] if urls else None,
    'urls': urls if len(urls) > 1 else None,
  })

  # enforce that lat/lon are float. (Pixelfed currently returns them as strings)
  for field in 'latitude', 'longitude':
    val = obj.get(field)
    if val:
      if not util.is_float(val):
        raise ValueError(f'Expected float for {field} in {obj.get("id")}; got {val}')
      obj[field] = float(val)

  # media
  if type in ('Audio', 'Video'):  # this may have been set above
    duration = util.parse_iso8601_duration(obj.pop('duration', None))
    if duration:
      duration = duration.total_seconds()

    obj.setdefault('stream', {
      # file size in bytes. nonstandard, not in AS1 proper
      'size': obj.pop('size', None),
      'duration': duration or None,
    })
    obj['stream'].setdefault('url', obj.pop('url', None))

  # object author
  attrib = util.pop_list(obj, 'attributedTo')
  if attrib:
    if len(attrib) > 1:
      logger.warning(f'ActivityStreams 1 only supports single author; dropping extra attributedTo values: {attrib[1:]}')
    attrib_as1 = to_as1(attrib[0])
    obj.setdefault('author', {}).update(attrib_as1 if isinstance(attrib_as1, dict)
                                        else {'id': attrib_as1})

  return util.trim_nulls(Source.postprocess_object(obj))


def is_public(activity, unlisted=True):
  """Returns True if the given AS2 object or activity is public or unlisted.

  https://docs.joinmastodon.org/spec/activitypub/#properties-used

  Args:
    activity (dict): AS2 activity or object
    unlisted (bool): whether unlisted, ie public in cc instead of to counts as
      public or not
  """
  if not isinstance(activity, dict):
    return False

  audience = util.get_list(activity, 'to')
  obj = as1.get_object(activity)
  audience.extend(util.get_list(obj, 'to'))

  if unlisted:
    audience.extend(util.get_list(obj, 'cc') + util.get_list(activity, 'cc'))

  return bool(PUBLICS.intersection(audience))


def address(actor):
  """Returns an actor's fediverse handle aka WebFinger address aka @-@.

  There's no standard for this, it's just a heuristic that uses
  ``preferredUsername`` and ``id`` or ``url`` if available,
  otherwise detects and transforms common user profile URLs.

  Args:
    actor (dict): AS2 JSON actor or str actor id

  Returns:
    str: handle, eg ``@user@example.com``, or None
  """
  if not actor:
    return None

  if isinstance(actor, dict):
    host = (urlparse(actor.get('id')).netloc
            or urlparse(util.get_url(actor)).netloc)
    username = actor.get('preferredUsername')
    if username and host:
      return f'@{username}@{host}'

  urls = ([actor.get('id'), util.get_url(actor)] if isinstance(actor, dict)
          else [actor])

  for url in urls:
    if url:
      match = re.match(r'^https?://(.+)/(users/|profile/|@)(.+)$', url)
      if match:
        return match.expand(r'@\3@\1')


def link_tags(obj):
  """Adds HTML links to ``content`` for tags with ``startIndex`` and ``length``.

  ``content`` is modified in place. If ``content_is_html`` is ``true``, does
  nothing. Otherwise, sets it to ``true`` if at least one link is added. Tags
  without ``startIndex``/``length`` are ignored.

  TODO: duplicated in :func:`microformats2.render_content`. unify?

  Args:
    obj (dict): AS2 JSON object
  """
  content = obj.get('content')
  if not content or obj.get('content_is_html'):
    return

  # extract indexed tags, preserving order
  tags = [tag for tag in obj.get('tag', [])
          if 'startIndex' in tag and 'length' in tag and
          ('href' in tag or 'url' in tag)]
  tags.sort(key=lambda t: t['startIndex'])

  # linkify embedded mention tags inside content.
  last_end = 0
  orig = content
  linked = ''
  for tag in tags:
    url = tag.get('href') or tag.get('url')
    start = tag['startIndex']
    if start < last_end:
      logger.warning(f'tag indices overlap! skipping {url}')
      continue
    end = start + tag['length']
    linked = f"{linked}{orig[last_end:start]}<a href=\"{url}\">{orig[start:end]}</a>"
    last_end = end
    obj['content_is_html'] = True
    del tag['startIndex']
    del tag['length']

  obj['content'] = linked + orig[last_end:]


def is_server_actor(actor):
  """Returns True if this is the instance's server actor, False otherwise.

  Server actors are non-user actors used for fetching remote objects, sending
  ``Flag`` activities, etc. Background:
  * https://seb.jambor.dev/posts/understanding-activitypub-part-4-threads/#the-instance-actor
  * https://codeberg.org/fediverse/fep/src/branch/main/fep/d556/fep-d556.md

  Right now, this just uses a well-known set of paths as a heuristic.

  TODO: actually do a WebFinger lookup of the root path, eg
  ``webfinger?resource=https://example.com/``, and use FEP-d556 to determine the
  server actor.

  Args:
    actor (dict): AS2 actor

  Returns:
    bool:
  """
  id = actor.get('id')
  if not id:
    return False

  return urlparse(id).path in SERVER_ACTOR_PREFIXES
