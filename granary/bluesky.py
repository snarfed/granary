"""Bluesky source class.

https://bsky.app/
https://atproto.com/lexicons/app-bsky-actor
https://github.com/bluesky-social/atproto/tree/main/lexicons/app/bsky
"""
import copy
import logging
import urllib.parse

from granary.source import Source, OMIT_LINK
from oauth_dropins.webutil import util


def url_to_did_web(url):
  """Converts a URL to a did:web.

  Examples:
  * 'https://foo.com' => 'did:web:foo.com'
  * 'https://foo.com:3000' => 'did:web:foo.com%3A3000'
  * 'https://bar.com/baz/baj' => 'did:web:bar.com:baz:baj'

  https://w3c-ccg.github.io/did-method-web/#example-creating-the-did

  TODO: require https?

  Args:
    url: str

  Returns: str
  """
  parsed = urllib.parse.urlparse(url)
  if not parsed.netloc:
    raise ValueError(f'Invalid URL: {url}')

  did = f'did:web:{urllib.parse.quote(parsed.netloc)}'
  if parsed.path:
    did += f'{parsed.path.replace("/", ":")}'

  return did.strip(':')


def did_web_to_url(did):
  """Converts a did:web to a URL.

  Examples:
  * 'did:web:foo.com' => 'https://foo.com'
  * 'did:web:foo.com%3A3000' => 'https://foo.com:3000'
  * 'did:web:bar.com:baz:baj' => 'https://bar.com/baz/baj'

  https://w3c-ccg.github.io/did-method-web/#read-resolve

  Args:
    did: str

  Returns: str
  """
  if not did or not did.startswith('did:web:'):
    raise ValueError(f'Invalid did:web: {did}')

  did = did.removeprefix('did:web:')
  if ':' in did:
    host, path = did.split(':', 1)
  else:
    host = did
    path = ''

  host = urllib.parse.unquote(host)
  path = urllib.parse.unquote(path.replace(':', '/'))
  return f'https://{host}/{path}'


def from_as1(obj, from_url=None):
  """Converts an AS1 object to a Bluesky object.

  The objectType field is required.

  Args:
    obj: dict, AS1 object or activity
    from_url: str, optional URL the original object was fetched from.
      Currently unused. TODO: remove?

  Returns: dict, app.bsky.* object

  Raises:
    ValueError
      if the objectType or verb fields are missing or unsupported
  """
  activity = obj
  verb = activity.get('verb') or 'post'
  inner_obj = activity.get('object')
  if inner_obj and verb == 'post':
    obj = inner_obj

  type = obj.get('objectType') or 'note'
  actor = activity.get('actor')

  # TODO: once we're on Python 3.10, switch this to a match statement!
  if type == 'person':
    # banner is featured image, if available
    banner = None
    for img in util.get_list(obj, 'image'):
      url = img.get('url')
      if img.get('objectType') == 'featured' and url:
        banner = url
        break

    url = util.get_url(obj) or obj.get('id') or ''
    try:
      did_web = url_to_did_web(url)
    except ValueError as e:
      logging.info(f"Couldn't generate did:web: {e}")
      did_web = ''

    # handle is username@domain or domain/path, no scheme or query
    username = obj.get('username')
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    if username:
      handle = username
      if domain:
        handle += f'@{domain}'
    elif url:
      handle = domain
      if parsed.path not in ('', '/'):
        handle += parsed.path
    else:
      handle = ''

    ret = {
      '$type': 'app.bsky.actor.profile',
      'displayName': obj.get('displayName'),
      'description': obj.get('summary'),
      'avatar': util.get_url(obj, 'image'),
      'banner': banner,
      'did': did_web,
      # this is a DID
      # atproto/packages/pds/src/api/app/bsky/actor/getProfile.ts#38
      'creator': did_web,
      'declaration': {
        '$type': 'app.bsky.system.declRef',
        # Content ID, aka content-hash fingerprint. Immutable hash that
        # identifies a node in a PDS.
        # https://atproto.com/guides/applications#record-types
        # https://github.com/multiformats/cid
        # https://atproto.com/guides/data-repos#data-layout
        # atproto/lexicons/com/atproto/repo/strongRef.json
        'cid': 'TODO',
        'actorType': 'app.bsky.system.actorUser',
      },
      # TODO: should be more specific than domain, many users will be on shared
      # domains
      'handle': handle,
      'followersCount': 0,
      'followsCount': 0,
      'membersCount': 0,
      'postsCount': 0,
    }

  elif verb == 'share':
    ret = from_as1(inner_obj)
    ret['reason'] = {
      '$type': 'app.bsky.feed.feedViewPost#reasonRepost',
      'by': actor_to_ref(actor),
      'indexedAt': util.now().isoformat(),
    }

  elif verb == 'follow':
    assert actor
    ret = {
      '$type': 'app.bsky.graph.follow',
      'subject': actor.get('id') or actor.get('url'),
      'createdAt': obj.get('published', ''),
    }

  elif verb == 'post' and type in ('article', 'mention', 'note', 'comment'):
    # convert text to HTML and truncate
    src = Bluesky()
    text = src._content_for_create(obj)
    is_html = text != (obj.get('summary') or obj.get('content') or obj.get('name'))
    text = src.truncate(text, None, OMIT_LINK)

    # text tags
    entities = []
    content = obj.get('content')
    for tag in util.get_list(obj, 'tags'):
      url = tag.get('url')
      if url:
        try:
          start = int(tag.get('startIndex'))
          if is_html and start:
            raise NotImplementedError('HTML content is not supported with index tags')
          end = start + int(tag.get('length'))
          tag_text = content[start:end] if content else None
        except (ValueError, IndexError):
          tag_text = start = end = None
        entities.append({
          'type': 'link',
          'value': url,
          'text': tag_text,
          'index': {
            'start': start,
            'end': end,
          },
        })

    # images
    post_embed = record_embed = None
    images = util.get_list(obj, 'image')
    if images:
      post_embed = {
        '$type': 'app.bsky.embed.images#presented',
        'images': [{
          '$type': 'app.bsky.embed.images#presentedImage',
          'thumb': img.get('url'),
          'fullsize': img.get('url'),
          'alt': img.get('displayName'),
        } for img in images[:4]],
      }
      record_embed = {
        '$type': 'app.bsky.embed.images',
        'images': [{
          '$type': 'app.bsky.embed.images#image',
          'image': img.get('url'),
          'alt': img.get('displayName'),
        } for img in images[:4]],
      }
    elif entities:
      post_embed = {
        '$type': 'app.bsky.embed.external#presented',
        'external': [{
          '$type': 'app.bsky.embed.external#presentedExternal',
          'uri': entity['value'],
          'title': entity['text'],
          'description': '',
        } for entity in entities],
      }
      record_embed = {
        '$type': 'app.bsky.embed.external',
        'external': [{
          '$type': 'app.bsky.embed.external#external',
          'uri': entity['value'],
          'title': entity['text'],
          'description': '',
        } for entity in entities],
      }

    author = obj.get('author')

    ret = {
      '$type': 'app.bsky.feed.feedViewPost',
      'post': {
        '$type': 'app.bsky.feed.post#view',
        'uri': util.get_url(obj),
        'cid': 'TODO',
        'record': {
          '$type': 'app.bsky.feed.post',
          'text': text,
          'createdAt': obj.get('published', ''),
          'embed': record_embed,
          'entities': entities,
        },
        'author': actor_to_ref(author) if author else None,
        'embed': post_embed,
        'replyCount': 0,
        'repostCount': 0,
        'upvoteCount': 0,
        'downvoteCount': 0,
        'indexedAt': util.now().isoformat(),
        'viewer': {},
      },
    }

    in_reply_to = util.get_url(obj, 'inReplyTo')
    if in_reply_to:
      ret['post']['record']['reply'] = {
        '$type': 'app.bsky.feed.post#replyRef',
        'root': {
          '$type': 'com.atproto.repo.strongRef',
          'uri': in_reply_to,
          'cid': 'TODO',
        },
        'parent': {
          '$type': 'com.atproto.repo.strongRef',
          'uri': in_reply_to,
          'cid': 'TODO',
        },
      }

  else:
    raise ValueError(f'AS1 object has unknown objectType {type} or verb {verb}')

  # keep some fields that are required by lexicons
  return util.trim_nulls(ret, ignore=(
    'createdAt',
    'description',
    'did',
    'handle',
    'text',
    'viewer',
  ))


def actor_to_ref(actor):
  """Converts an AS1 actor to a Bluesky `app.bsky.actor.ref#withInfo`.

  Args:
    actor: dict, AS1 actor

  Returns: dict, `app.bsky.actor.ref#withInfo` object
  """
  if not actor:
    return None

  actor = copy.deepcopy(actor)
  actor.setdefault('objectType', 'person')

  ref = {
    k: v for k, v in from_as1(actor).items()
      if k in ('avatar', 'declaration', 'did', 'displayName', 'handle', 'indexedAt')
  }
  ref['$type'] = 'app.bsky.actor.ref#withInfo'
  return ref


def to_as1(obj):
  """Converts a Bluesky object to an AS1 object.

  The $type field is required.

  Args:
    profile: dict, app.bsky.* object

  Returns: dict, AS1 object

  Raises:
    ValueError
    if the $type field is missing or unsupported
  """
  if not obj:
    return {}

  type = obj.get('$type')
  if not type:
    raise ValueError('Bluesky object missing $type field')

  # TODO: once we're on Python 3.10, switch this to a match statement!
  if type in ('app.bsky.actor.profile', 'app.bsky.actor.ref#withInfo'):
    images = [{'url': obj.get('avatar')}]
    banner = obj.get('banner')
    if banner:
      images.append({'url': obj.get('banner'), 'objectType': 'featured'})

    did = obj.get('did')

    ret = {
      'objectType': 'person',
      'displayName': obj.get('displayName'),
      'summary': obj.get('description'),
      'image': images,
      'url': did_web_to_url(did) if did else None,
    }

  elif type == 'app.bsky.feed.post':
    tags = []
    for entity in obj.get('entities', []):
      if entity.get('type') == 'link':
        index = entity.get('index')
        start = index.get('start', 0)
        end = index.get('end', 0)
        tags.append({
          'url': entity.get('value'),
          'startIndex': start,
          'length': end - start,
        })

    in_reply_to = obj.get('reply', {}).get('parent', {}).get('uri')

    ret = {
      'objectType': 'comment' if in_reply_to else 'note',
      'content': obj.get('text', ''),
      'inReplyTo': [{'url': in_reply_to}],
      'published': obj.get('createdAt', ''),
      'tags': tags,
    }

  elif type == 'app.bsky.feed.post#view':
    ret = to_as1(obj.get('record'))
    ret.update({
      'url': obj.get('uri'),
      'author': to_as1(obj.get('author')),
      'image': to_as1(obj.get('embed')),
    })

  elif type == 'app.bsky.embed.images#presented':
    ret = [{
      'url': img.get('fullsize'),
      'displayName': img.get('alt'),
    } for img in obj.get('images', [])]

  elif type == 'app.bsky.feed.feedViewPost':
    ret = to_as1(obj.get('post'))
    reason = obj.get('reason')
    if reason and reason.get('$type') == 'app.bsky.feed.feedViewPost#reasonRepost':
      ret = {
        'objectType': 'activity',
        'verb': 'share',
        'object': ret,
        'actor': to_as1(reason.get('by')),
      }

  elif type == 'app.bsky.graph.follow':
    ret = {
      'objectType': 'activity',
      'verb': 'follow',
      'actor': {
        'url': obj.get('subject'),
      },
    }

  else:
    raise ValueError(f'Bluesky object has unknown $type: {type}')

  return util.trim_nulls(ret)


class Bluesky(Source):
  """Bluesky source class. See file docstring and Source class for details."""

  DOMAIN = 'bsky.app'
  BASE_URL = 'https://bsky.app'
  NAME = 'Bluesky'
  TRUNCATE_TEXT_LENGTH = 256  # TODO: load from feed.post lexicon
