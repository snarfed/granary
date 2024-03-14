"""Bluesky source class.

* https://bsky.app/
* https://atproto.com/lexicons/app-bsky-actor
* https://github.com/bluesky-social/atproto/tree/main/lexicons/app/bsky
"""
from datetime import datetime, timezone
import json
import logging
import re
from pathlib import Path
import urllib.parse

import requests

from lexrpc import Client
from lexrpc.base import NSID_RE
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import trim_nulls

from . import as1
from .source import FRIENDS, html_to_text, Source, OMIT_LINK, creation_result

logger = logging.getLogger(__name__)

# via https://atproto.com/specs/handle
HANDLE_REGEX = (
  r'([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+'
  r'[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
)
HANDLE_PATTERN = re.compile(r'^' + HANDLE_REGEX)
DID_WEB_PATTERN = re.compile(r'^did:web:' + HANDLE_REGEX)

# at:// URI regexp
# https://atproto.com/specs/at-uri-scheme#full-at-uri-syntax
# https://atproto.com/specs/record-key#record-key-syntax
# https://atproto.com/specs/nsid
# also see arroba.util.parse_at_uri
_CHARS = 'a-zA-Z0-9-.:'
# TODO: add query and fragment? they're currently unused in the protocol
# https://atproto.com/specs/at-uri-scheme#structure
AT_URI_PATTERN = re.compile(rf"""
    ^at://
     (?P<repo>[{_CHARS}]+)
      (?:/(?P<collection>[a-zA-Z0-9-.]+)
       (?:/(?P<rkey>[{_CHARS}]+))?)?
    $""", re.VERBOSE)

# Maps AT Protocol NSID collections to path elements in bsky.app URLs.
# Used in at_uri_to_web_url.
#
# eg for mapping a URI like:
#   at://did:plc:z72i7hd/app.bsky.feed.generator/mutuals
# to a frontend URL like:
#   https://bsky.app/profile/did:plc:z72i7hdynmk6r22z27h6tvur/feed/mutuals
COLLECTION_TO_BSKY_APP_TYPE = {
  'app.bsky.feed.generator': 'feed',
  'app.bsky.feed.post': 'post',
  'app.bsky.graph.list': 'lists',
}
BSKY_APP_TYPE_TO_COLLECTION = {
  name: coll for coll, name in COLLECTION_TO_BSKY_APP_TYPE.items()
}

# TODO: load from app.bsky.embed.images lexicon
# https://github.com/snarfed/atproto/blob/c0489626327e1ac9c08961ad9ce828793d0d1d43/lexicons/app/bsky/embed/images.json#L13
MAX_IMAGES = 4

# maps AS1 objectType/verb to possible output Bluesky lexicon types.
# used in from_as1
POST_TYPES = tuple(as1.POST_TYPES) + ('bookmark',)
FROM_AS1_TYPES = {
  as1.ACTOR_TYPES: (
    'app.bsky.actor.profile',
    'app.bsky.actor.defs#profileView',
    'app.bsky.actor.defs#profileViewBasic',
    'app.bsky.actor.defs#profileViewDetailed',
  ),
  POST_TYPES: (
    'app.bsky.feed.post',
    'app.bsky.feed.defs#feedViewPost',
    'app.bsky.feed.defs#postView',
  ),
  'share': (
    'app.bsky.feed.repost',
    'app.bsky.feed.defs#feedViewPost',
    'app.bsky.feed.defs#reasonRepost',
  ),
}

BSKY_APP_URL_RE = re.compile(r"""
  ^https://(staging\.)?bsky\.app
  /profile/(?P<id>[^/]+)
  (/(?P<type>post|feed)
   /(?P<tid>[^?]+))?$
  """, re.VERBOSE)

DEFAULT_PDS_DOMAIN = 'bsky.social'
DEFAULT_PDS = f'https://{DEFAULT_PDS_DOMAIN}/'
DEFAULT_APPVIEW = 'https://api.bsky.app'

# label on profiles set to only show them to logged in users
# https://docs.bsky.app/docs/advanced-guides/resolving-identities#for-backend-services
# https://github.com/bluesky-social/atproto/blob/main/packages/api/docs/labels.md#label-behaviors
NO_AUTHENTICATED_LABEL = '!no-unauthenticated'


def url_to_did_web(url):
  """Converts a URL to a ``did:web``.

  In AT Proto, only hostname-based web DIDs are supported.
  Paths are not supported, and will be discarded.

  https://atproto.com/specs/did

  Examples:

  * ``https://foo.com`` => ``did:web:foo.com``
  * ``https://foo.com:3000`` => ``did:web:foo.com``
  * ``https://foo.bar.com/baz/baj`` => ``did:web:foo.bar.com``

  Args:
    url (str)

  Returns:
    str:
  """
  parsed = urllib.parse.urlparse(url)
  if not parsed.hostname:
    raise ValueError(f'Invalid URL: {url}')
  if parsed.netloc != parsed.hostname:
    logger.warning(f"URL {url} contained a port, which will not be included in the DID.")
  if parsed.path and parsed.path != "/":
    logger.warning(f"URL {url} contained a path,  which will not be included in the DID.")

  return f'did:web:{parsed.hostname}'


def did_web_to_url(did):
  """Converts a did:web to a URL.

  In AT Proto, only hostname-based web DIDs are supported.
  Paths are not supported, and will throw an invalid error.

  Examples:

  * ``did:web:foo.com`` => ``https://foo.com``
  * ``did:web:foo.com%3A3000`` => INVALID
  * ``did:web:bar.com:baz:baj`` => INVALID

  https://atproto.com/specs/did

  Args:
    did (str)

  Returns:
    str:
  """
  if not did or not DID_WEB_PATTERN.match(did):
    raise ValueError(f'Invalid did:web: {did}')

  host = did.removeprefix('did:web:')

  host = urllib.parse.unquote(host)
  return f'https://{host}/'


def at_uri_to_web_url(uri, handle=None):
  """Converts an ``at://`` URI to a ``https://bsky.app`` URL.

  https://atproto.com/specs/at-uri-scheme

  Args:
    uri (str): ``at://`` URI
    handle: (str): optional user handle. If not provided, defaults to the DID in
      uri.

  Returns:
    str: ``https://bsky.app`` URL, or None

  Raises:
    ValueError: if uri is not a string or doesn't start with ``at://``
  """
  if not uri:
    return None

  if not uri.startswith('at://'):
    raise ValueError(f'Expected at:// URI, got {uri}')

  parsed = urllib.parse.urlparse(uri)
  did = parsed.netloc

  if not parsed.path:
    return f'{Bluesky.user_url(handle or did)}'

  collection, tid = parsed.path.strip('/').split('/')

  type = COLLECTION_TO_BSKY_APP_TYPE.get(collection)
  if not type:
    return None

  return f'{Bluesky.user_url(handle or did)}/{type}/{tid}'


def web_url_to_at_uri(url, handle=None, did=None):
  """Converts a ``https://bsky.app`` URL to an ``at://`` URI.

  https://atproto.com/specs/at-uri-scheme

  Currently supports profile, post, and feed URLs with DIDs and handles, eg:

  * ``https://bsky.app/profile/did:plc:123abc``
  * ``https://bsky.app/profile/vito.fyi/post/3jt7sst7vok2u``
  * ``https://bsky.app/profile/bsky.app/feed/mutuals``

  If both ``handle`` and ``did`` are provided, and ``handle`` matches the URL,
  the handle in the resulting URI will be replaced with ``did``.

  Args:
    url (str): ``bsky.app`` URL
    handle (str): Bluesky handle, or None
    did (str): Valid DID, or None

  Returns:
    str: ``at://`` URI, or None

  Raises:
    ValueError: if ``url`` can't be parsed as a ``bsky.app`` profile or post URL
  """
  if not url:
    return None

  match = BSKY_APP_URL_RE.match(url)
  if not match:
    raise ValueError(f"{url} doesn't look like a bsky.app profile or post URL")

  id = match.group('id')
  assert id
  # If a did and handle have been provided explicitly,
  # replace the existing handle with the did.
  if did and handle and id == handle:
    id = did

  rkey = match.group('tid')

  type = match.group('type')
  if type:
    collection = BSKY_APP_TYPE_TO_COLLECTION[type]
    assert rkey
  else:
    collection = 'app.bsky.actor.profile'
    rkey = 'self'

  return f'at://{id}/{collection}/{rkey}'


def from_as1_to_strong_ref(obj, client=None):
  """Converts an AS1 object to an ATProto ``com.atproto.repo.strongRef``.

  Uses AS1 ``id`` or ``url`, converting from bsky.app URL to ``at://`` URI if
  needed.

  Args:
    obj (dict): AS1 object or activity
    client (Bluesky): optional; if provided, this will be used to make API calls
      to PDSes to fetch and populate the ``cid`` field and resolve handle to DID.

  Returns:
    dict: ATProto ``com.atproto.repo.strongRef`` record
  """
  at_uri = Bluesky.post_id((obj.get('id') or as1.get_url(obj))
                           if isinstance(obj, dict) else obj)
  if not at_uri:
    return {
      'uri': '',
      'cid': '',
    }

  cid = ''
  match = AT_URI_PATTERN.match(at_uri)
  if match and client:
    repo, collection, rkey = match.groups()
    if not repo.startswith('did:'):
      handle = repo
      repo = client._client.com.atproto.identity.resolveHandle(handle=handle)['did']
      # only replace first instance of handle in case it's also in collection or rkey
      at_uri = at_uri.replace(handle, repo, 1)

    record = client._client.com.atproto.repo.getRecord(
      repo=repo, collection=collection, rkey=rkey)
    cid = record.get('cid')

  return {
    'uri': at_uri,
    'cid': cid,
  }


def from_as1_datetime(val):
  """Converts an AS1 RFC 3339 datetime string to ATProto ISO 8601.

  Bluesky requires full date and time with time zone, recommends UTC with
  Z suffix, fractional seconds.

  https://atproto.com/specs/lexicon#datetime

  Returns now (ie the current time) if the input datetime can't be parsed.

  Args:
    val (str): RFC 3339 datetime

  Returns:
    str: ATProto compatible ISO 8601 datetime
  """
  try:
    # dt = datetime.fromisoformat(val.strip())
    dt = util.parse_iso8601(val.strip())
  except (AttributeError, TypeError, ValueError):
    logging.debug(f"Couldn't parse {val} as ISO 8601; defaulting to current time")
    dt = util.now()

  if dt.tzinfo:
    dt = util.as_utc(dt)
  # else it's naive, assume it's UTC

  assert dt.utcoffset() is None, dt.utcoffset()
  return dt.isoformat(sep='T', timespec='milliseconds') + 'Z'


def base_object(obj):
  """Returns the "base" Bluesky object that an object operates on.

  If the object is a reply, repost, or like of a Bluesky post, this returns
  that post object. The id in the returned object is the AT protocol URI,
  while the URL is the bsky.app web URL.

  Args:
    obj (dict): ActivityStreams object

  Returns:
    dict: minimal ActivityStreams object. Usually has at least ``id``; may
    also have ``url``, ``author``, etc.
  """
  for field in ('inReplyTo', 'object', 'target'):
    for base in util.get_list(obj, field):
      url = util.get_url(base)
      if not url:
        return {}
      if url.startswith('https://bsky.app/'):
        return {
          'id': web_url_to_at_uri(url),
          'url': url,
        }
      if url.startswith('at://'):
        return {
          'id': url,
          'url': at_uri_to_web_url(url),
        }
  return {}


def from_as1(obj, out_type=None, blobs=None, client=None):
  """Converts an AS1 object to a Bluesky object.

  Converts to ``record`` types by default, eg ``app.bsky.actor.profile`` or
  ``app.bsky.feed.post``. Use ``out_type`` to convert to a different type, eg
  ``app.bsky.actor.defs#profileViewBasic`` or ``app.bsky.feed.defs#feedViewPost``.

  The ``objectType`` field is required.

  Args:
    obj (dict): AS1 object or activity
    out_type (str): desired output lexicon ``$type``
    blobs (dict): optional mapping from str URL to ``blob`` dict to use in the
      returned object. If not provided, or if this doesn't have an ``image`` or
      similar URL in the input object, its output blob will be omitted.
    client (Bluesky): optional; if provided, this will be used to make API calls
      to PDSes to fetch and populate CIDs for records referenced by replies,
      likes, reposts, etc.

  Returns:
    dict: ``app.bsky.*`` object

  Raises:
    ValueError: if the ``objectType`` or ``verb`` fields are missing or
      unsupported

  """
  activity = obj
  inner_obj = as1.get_object(activity)
  verb = activity.get('verb') or 'post'
  if inner_obj and verb == 'post':
    obj = inner_obj

  type = as1.object_type(obj)
  if not type:
    raise ValueError(f"Missing objectType or verb")

  actor = as1.get_object(activity, 'actor')
  if blobs is None:
    blobs = {}

  # validate out_type
  if out_type:
    for in_types, out_types in FROM_AS1_TYPES.items():
      if type in in_types and out_type in out_types:
        break
    else:
      raise ValueError(f"{type} {verb} doesn't support out_type {out_type}")

  # TODO: once we're on Python 3.10, switch this to a match statement!
  if type in as1.ACTOR_TYPES:
    # avatar and banner. banner is featured image, if available
    avatar = util.get_url(obj, 'image')
    banner = None
    for img in util.get_list(obj, 'image'):
      url = img.get('url')
      if img.get('objectType') == 'featured' and url:
        banner = url
        break

    ret = {
      'displayName': obj.get('displayName'),
      'description': html_to_text(obj.get('summary')),
      'avatar': blobs.get(avatar),
      'banner': blobs.get(banner),
    }
    if not out_type or out_type == 'app.bsky.actor.profile':
      return trim_nulls({**ret, '$type': 'app.bsky.actor.profile'})

    url = as1.get_url(obj)
    id = obj.get('id')
    if not url and id:
      parsed = util.parse_tag_uri(id)
      if parsed:
        # This is only really formatted as a URL to keep url_to_did_web happy.
        url = f'https://{parsed[0]}'

    did_web = ''
    if id and id.startswith('did:web:'):
      did_web = id
    else:
      try:
        did_web = url_to_did_web(url)
      except ValueError as e:
        logger.info(f"Couldn't generate did:web: {e}")

    # handles must be hostnames
    # https://atproto.com/specs/handle
    username = obj.get('username')
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc
    did_web_bare = did_web.removeprefix('did:web:')
    handle = (username if username and HANDLE_PATTERN.match(username)
              else did_web_bare if ':' not in did_web_bare
              else domain if domain
              else '')

    ret.update({
      '$type': out_type,
      # TODO: more specific than domain, many users will be on shared domains
      'did': id if id and id.startswith('did:') else did_web,
      'handle': handle,
      'avatar': avatar,
      'banner': banner,
    })
    # WARNING: this includes description, which isn't technically in this
    # #profileViewBasic. hopefully clients should just ignore it!
    # https://atproto.com/specs/lexicon#authority-and-control
    return trim_nulls(ret, ignore=('did', 'handle'))

  elif type == 'share':
    if not out_type or out_type == 'app.bsky.feed.repost':
      return {
        '$type': 'app.bsky.feed.repost',
        'subject': from_as1_to_strong_ref(inner_obj, client=client),
        'createdAt': from_as1_datetime(obj.get('published')),
      }
    elif out_type == 'app.bsky.feed.defs#reasonRepost':
      return {
        '$type': 'app.bsky.feed.defs#reasonRepost',
        'by': from_as1(actor, out_type='app.bsky.actor.defs#profileViewBasic'),
        'indexedAt': from_as1_datetime(None),
      }
    elif out_type == 'app.bsky.feed.defs#feedViewPost':
      return {
        '$type': 'app.bsky.feed.defs#feedViewPost',
        'post': from_as1(inner_obj, out_type='app.bsky.feed.defs#postView'),
        'reason': from_as1(obj, out_type='app.bsky.feed.defs#reasonRepost'),
      }

  elif type == 'like':
    return {
      '$type': 'app.bsky.feed.like',
      'subject': from_as1_to_strong_ref(inner_obj, client=client),
      'createdAt': from_as1_datetime(obj.get('published')),
    }

  elif type == 'follow':
    if not inner_obj:
      raise ValueError('follow activity requires actor and object')
    return {
      '$type': 'app.bsky.graph.follow',
      'subject': inner_obj.get('id'),  # DID
      'createdAt': from_as1_datetime(obj.get('published')),
    }

  elif verb == 'post' and type in POST_TYPES:
    # convert text to HTML and truncate
    src = Bluesky('unused')
    content = obj.get('content')
    text = obj.get('summary') or content or obj.get('name') or ''
    text = src.truncate(html_to_text(text), None, OMIT_LINK)

    facets = []
    if text == content:
      # convert index-based to facets
      for tag in util.get_list(obj, 'tags'):
        facet = {
          '$type': 'app.bsky.richtext.facet',
        }

        type = tag.get('objectType')
        url = tag.get('url')
        if not url:
          continue

        if type == 'mention':
          facet['features'] = [{
            '$type': 'app.bsky.richtext.facet#mention',
            # TODO: support bsky.app URLs with handles by resolving them?
            'did': (url if url.startswith('did:')
                    else url.removeprefix(f'{Bluesky.BASE_URL}/profile/')
                      if url.startswith(f'{Bluesky.BASE_URL}/profile/did:')
                    else ''),
          }]
        else:
          facet['features'] = [{
            '$type': 'app.bsky.richtext.facet#link',
            'uri': url,
          }]

        try:
          start = int(tag['startIndex'])
          if start and obj.get('content_is_html'):
            raise NotImplementedError('HTML content is not supported with index tags')
          end = start + int(tag['length'])

          facet['index'] = {
            # convert indices from Unicode chars (code points) to UTF-8 encoded bytes
            # https://github.com/snarfed/atproto/blob/5b0c2d7dd533711c17202cd61c0e101ef3a81971/lexicons/app/bsky/richtext/facet.json#L34
            'byteStart': len(content[:start].encode()),
            'byteEnd': len(content[:end].encode()),
          }
        except (KeyError, ValueError, IndexError, TypeError):
          pass

        facets.append(facet)

    # images
    images_embed = images_record_embed = None
    images = as1.get_objects(obj, 'image')

    if images:
      images_embed = {
        '$type': 'app.bsky.embed.images#view',
        'images': [{
          '$type': 'app.bsky.embed.images#viewImage',
          'thumb': img.get('url'),
          'fullsize': img.get('url'),
          'alt': img.get('displayName') or '',
        } for img in images[:4]],
      }
      images_record_embed = {
        '$type': 'app.bsky.embed.images',
        'images': [{
          '$type': 'app.bsky.embed.images#image',
          'image': blobs.get(util.get_url(img)) or {},
          'alt': img.get('displayName') or '',
        } for img in images[:4]],
      }

    # article/note attachments
    record_embed = record_record_embed = external_embed = external_record_embed = None

    for att in util.get_list(obj, 'attachments'):
      if not att.get('objectType') in ('article', 'link', 'note'):
        continue

      id = att.get('id') or ''
      url = att.get('url') or ''
      if (id.startswith('at://') or id.startswith(Bluesky.BASE_URL) or
          url.startswith('at://') or url.startswith(Bluesky.BASE_URL)):
        # quoted Bluesky post
        embed = from_as1(att).get('post') or {}
        embed['value'] = embed.pop('record', None)
        record_embed = {
          '$type': f'app.bsky.embed.record#view',
          'record': {
            **embed,
            '$type': f'app.bsky.embed.record#viewRecord',
            # override these so that trim_nulls below will remove them
            'likeCount': None,
            'replyCount': None,
            'repostCount': None,
          },
        }
        record_record_embed = {
          '$type': f'app.bsky.embed.record',
          'record': from_as1_to_strong_ref(att, client=client),
        }
      else:
        # external link
        external_record_embed = {
          '$type': f'app.bsky.embed.external',
          'external': {
            '$type': f'app.bsky.embed.external#external',
            'uri': url or id,
            'title': att.get('displayName'),
            'description': att.get('summary') or att.get('content') or '',
          }
        }
        external_embed = {
          '$type': f'app.bsky.embed.external#view',
          'external': {
            **external_record_embed['external'],
            '$type': f'app.bsky.embed.external#viewExternal',
            'thumb': util.get_first(att, 'image'),
          },
        }

    if record_embed and (images_embed or external_embed):
      embed = {
        '$type': 'app.bsky.embed.recordWithMedia#view',
        'record': record_embed,
        'media': images_embed or external_embed,
      }
      record_embed = {
        '$type': 'app.bsky.embed.recordWithMedia',
        'record': record_record_embed,
        'media' : images_record_embed or external_record_embed,
      }
    else:
      embed = record_embed or images_embed or external_embed
      record_embed = record_record_embed or images_record_embed or external_record_embed

    # in reply to
    reply = None
    in_reply_to = base_object(obj)
    if in_reply_to:
      parent_ref = from_as1_to_strong_ref(in_reply_to, client=client)
      reply = {
        '$type': 'app.bsky.feed.post#replyRef',
        # we don't know what the actual root is, so just use parent. callers can
        # look it up and override if they really need it.
        # TODO: fix now that we're fetching parent with client
        'root': parent_ref,
        'parent': parent_ref,
      }

    ret = trim_nulls({
      '$type': 'app.bsky.feed.post',
      'text': text,
      'createdAt': from_as1_datetime(obj.get('published')),
      'embed': record_embed,
      'facets': facets,
      'reply': reply,
    }, ignore=('alt', 'createdAt', 'cid', 'description', 'text', 'title', 'uri'))

    if not out_type or out_type == 'app.bsky.feed.post':
      return ret

    # author
    author = as1.get_object(obj, 'author')
    author.setdefault('objectType', 'person')
    author = from_as1(author, out_type='app.bsky.actor.defs#profileViewBasic')

    ret = trim_nulls({
      '$type': 'app.bsky.feed.defs#postView',
      'uri': obj.get('id') or obj.get('url') or '',
      'cid': '',
      'record': ret,
      'author': author,
      'embed': embed,
      'replyCount': 0,
      'repostCount': 0,
      'likeCount': 0,
      'indexedAt': from_as1_datetime(None),
    }, ignore=('author', 'createdAt', 'cid', 'description', 'indexedAt',
               'record', 'text', 'title', 'uri'))

    if out_type == 'app.bsky.feed.defs#postView':
      return ret
    elif out_type == 'app.bsky.feed.defs#feedViewPost':
      return {
        '$type': out_type,
        'post': ret,
      }

    assert False, "shouldn't happen"

  raise ValueError(f'AS1 object has unknown objectType {type} verb {verb}')


def to_as1(obj, type=None, uri=None, repo_did=None, repo_handle=None,
           pds=DEFAULT_PDS):
  """Converts a Bluesky object to an AS1 object.

  Args:
    obj (dict): ``app.bsky.*`` object
    type (str): optional ``$type`` to parse with, only used if ``obj['$type']``
      is unset
    uri (str): optional ``at://`` URI of this object. Used to populate the
      ``id`` and ``url`` fields for some object types, eg posts.
    repo_did (str): optional DID of the repo this object is from. Required to
      generate image URLs.
    repo_handle (str): optional handle of the user whose repo this object is from
    pds (str): base URL of the PDS that currently serves this object's repo.
      Required to generate image URLs. Defaults to ``https://bsky.social/``.

  Returns:
    dict: AS1 object

  Raises:
    ValueError: if the ``$type`` field is missing or unsupported
  """
  if not obj:
    return {}

  type = obj.get('$type') or type
  if not type:
    raise ValueError('Bluesky object missing $type field')

  uri_authority = None
  if uri:
    if not uri.startswith('at://'):
      raise ValueError('Expected at:// uri, got {uri}')
    if parsed := AT_URI_PATTERN.match(uri):
      uri_authority = parsed.group(1)

  # for nested to_as1 calls, if necessary
  kwargs = {'repo_did': repo_did, 'repo_handle': repo_handle, 'pds': pds}

  # TODO: once we're on Python 3.10, switch this to a match statement!
  if type in ('app.bsky.actor.profile',
              'app.bsky.actor.defs#profileView',
              'app.bsky.actor.defs#profileViewBasic',
              'app.bsky.actor.defs#profileViewDetailed',
              ):
    images = [{'url': obj.get('avatar')}]
    banner = obj.get('banner')
    if banner:
      images.append({'url': obj.get('banner'), 'objectType': 'featured'})

    handle = obj.get('handle')
    did = obj.get('did')
    if type == 'app.bsky.actor.profile':
      if not handle:
        handle = repo_handle
      if not did:
        did = repo_did

    urls = []
    if handle:
      urls.append(Bluesky.user_url(handle))
      if not util.domain_or_parent_in(handle, [DEFAULT_PDS_DOMAIN]):
        urls.append(f'https://{handle}/')
    elif did and did.startswith('did:web:'):
      urls.extend([did_web_to_url(did), Bluesky.user_url(did)])

    ret = {
      'objectType': 'person',
      'id': did,
      'url': urls,
      'displayName': obj.get('displayName'),
      'username': obj.get('handle') or repo_handle,
      'summary': obj.get('description'),
      'image': images,
    }

    # avatar and banner are blobs in app.bsky.actor.profile; convert to URLs
    if type == 'app.bsky.actor.profile':
      repo_did = repo_did or did
      if repo_did and pds:
        for img in ret['image']:
          img['url'] = blob_to_url(blob=img['url'], repo_did=repo_did, pds=pds)
      else:
        ret['image'] = []

    # convert public view opt-out to unlisted AS1 audience targeting
    # https://docs.bsky.app/docs/advanced-guides/resolving-identities#for-backend-services
    # https://activitystrea.ms/specs/json/targeting/1.0/
    labels = (obj.get('labels', {}).get('values', [])
                if type == 'app.bsky.actor.profile'
              else obj.get('labels', []))
    for label in labels:
      if label.get('val') == NO_AUTHENTICATED_LABEL and not label.get('neg'):
        ret['to'] = [{
          'objectType': 'group',
          'alias': '@unlisted',
        }]

  elif type == 'app.bsky.feed.post':
    text = obj.get('text', '')

    # convert facets to tags
    tags = []
    for facet in obj.get('facets', []):
      tag = {}

      for feat in facet.get('features', []):
        if feat.get('$type') == 'app.bsky.richtext.facet#link':
          tag.update({
            'objectType': 'article',
            'url': feat.get('uri'),
          })
        elif feat.get('$type') == 'app.bsky.richtext.facet#mention':
          tag.update({
            'objectType': 'mention',
            'url': Bluesky.user_url(feat.get('did')),
          })

      index = facet.get('index', {})
      # convert indices from UTF-8 encoded bytes to Unicode chars (code points)
      # https://github.com/snarfed/atproto/blob/5b0c2d7dd533711c17202cd61c0e101ef3a81971/lexicons/app/bsky/richtext/facet.json#L34
      byte_start = index.get('byteStart')
      byte_end = index.get('byteEnd')

      try:
        if byte_start is not None:
          tag['startIndex'] = len(text.encode()[:byte_start].decode())
        if byte_end is not None:
          tag['displayName'] = text.encode()[byte_start:byte_end].decode()
          tag['length'] = len(tag['displayName'])
      except UnicodeDecodeError as e:
        logger.warning(f"Couldn't apply facet {facet} to unicode text: {text}")

      tags.append(tag)

    in_reply_to = obj.get('reply', {}).get('parent', {}).get('uri')

    ret = {
      'objectType': 'comment' if in_reply_to else 'note',
      'id': uri,
      'url': at_uri_to_web_url(uri),
      'content': text,
      'inReplyTo': [{
        'id': in_reply_to,
        'url': at_uri_to_web_url(in_reply_to),
      }],
      'published': obj.get('createdAt', ''),
      'tags': tags,
      'author': repo_did,
    }

    # embeds
    embed = obj.get('embed') or {}
    embed_type = embed.get('$type')
    if embed_type == 'app.bsky.embed.images':
      ret['image'] = to_as1(embed, **kwargs)
    elif embed_type in ('app.bsky.embed.external', 'app.bsky.embed.record'):
      ret['attachments'] = [to_as1(embed, **kwargs)]
    elif embed_type == 'app.bsky.embed.recordWithMedia':
      # TODO
      # ret['attachments'] = [to_as1(embed.get('record', {}).get('record'),
      #                              type='com.atproto.repo.strongRef', **kwargs)]
      ret['attachments'] = []
      media = embed.get('media')
      media_type = media.get('$type')
      if media_type == 'app.bsky.embed.external':
        ret['attachments'].append(to_as1(media, **kwargs))
      elif media_type == 'app.bsky.embed.images':
        ret['image'] = to_as1(media, **kwargs)
      else:
        assert False, f'Unknown embed media type: {media_type}'

  elif type in ('app.bsky.feed.defs#postView', 'app.bsky.embed.record#viewRecord'):
    ret = to_as1(obj.get('record') or obj.get('value'), **kwargs)
    author = obj.get('author') or {}
    uri = obj.get('uri')
    ret.update({
      'id': uri,
      'url': (at_uri_to_web_url(uri, handle=author.get('handle'))
              if uri.startswith('at://') else None),
      'author': to_as1(author, type='app.bsky.actor.defs#profileViewBasic', **kwargs),
    })

    # convert embeds to attachments
    for embed in util.get_list(obj, 'embeds') + util.get_list(obj, 'embed'):
      embed_type = embed.get('$type')

      if embed_type == 'app.bsky.embed.images#view':
        ret.setdefault('image', []).extend(to_as1(embed, **kwargs))

      elif embed_type in ('app.bsky.embed.external#view',
                          'app.bsky.embed.record#view'):
        ret['attachments'] = [to_as1(embed, **kwargs)]

      elif embed_type == 'app.bsky.embed.recordWithMedia#view':
        ret['attachments'] = [to_as1(embed.get('record', {}).get('record'), **kwargs)]
        media = embed.get('media')
        media_type = media.get('$type')
        if media_type == 'app.bsky.embed.external#view':
          ret.setdefault('attachments', []).append(to_as1(media, **kwargs))
        elif media_type == 'app.bsky.embed.images#view':
          ret.setdefault('image', []).extend(to_as1(media, **kwargs))
        else:
          assert False, f'Unknown embed media type: {media_type}'

  elif type == 'app.bsky.embed.images':
    if repo_did and pds:
      ret = []
      for img in obj.get('images', []):
        image = img.get('image')
        if image:
          url = blob_to_url(blob=image, repo_did=repo_did, pds=pds)
          ret.append({'url': url, 'displayName': img['alt']}
                     if img.get('alt') else url)
    else:
      ret = []

  elif type == 'app.bsky.embed.images#view':
    ret = [{
      'url': img.get('fullsize'),
      'displayName': img.get('alt'),
    } for img in obj.get('images', [])]

  elif type in ('app.bsky.embed.external', 'app.bsky.embed.external#view'):
    ret = to_as1(obj.get('external'), type='app.bsky.embed.external#viewExternal',
                 **kwargs)

  elif type in ('app.bsky.embed.external#external',
                'app.bsky.embed.external#viewExternal'):
    ret = {
      'objectType': 'link',
      'url': obj.get('uri'),
      'displayName': obj.get('title'),
      'summary': obj.get('description'),
      'image': obj.get('thumb'),
    }

  elif type == 'app.bsky.embed.record':
    return None
    # TODO
    # return (to_as1(record, **kwargs, type='com.atproto.repo.strongRef')
    #         if record else None)

  elif type == 'app.bsky.embed.record#view':
    record = obj.get('record')
    return to_as1(record, **kwargs) if record else None

  elif type == 'app.bsky.embed.record#viewNotFound':
    return None

  elif type in ('app.bsky.embed.record#viewNotFound',
                'app.bsky.embed.record#viewBlocked'):
    return None

  elif type == 'app.bsky.feed.defs#feedViewPost':
    ret = to_as1(obj.get('post'), type='app.bsky.feed.defs#postView', **kwargs)
    reason = obj.get('reason')
    if reason and reason.get('$type') == 'app.bsky.feed.defs#reasonRepost':
      uri = obj.get('post', {}).get('viewer', {}).get('repost')
      ret = {
        'objectType': 'activity',
        'verb': 'share',
        'id': uri,
        'url': at_uri_to_web_url(uri),
        'object': ret,
        'actor': to_as1(reason.get('by'),
                        type='app.bsky.actor.defs#profileViewBasic', **kwargs),
      }

  elif type == 'app.bsky.feed.like':
    subject = obj.get('subject', {}).get('uri')
    ret = {
      'objectType': 'activity',
      'verb': 'like',
      'id': uri,
      'object': subject,
      'actor': repo_did,
    }
    if subject and uri_authority:
      if web_url := at_uri_to_web_url(subject):
        # synthetic fragment
        ret['url'] = f'{web_url}#liked_by_{uri_authority}'

  elif type == 'app.bsky.graph.follow':
    ret = {
      'objectType': 'activity',
      'verb': 'follow',
      'id': uri,
      'url': at_uri_to_web_url(uri),
      'object': obj.get('subject'),
      'actor': repo_did,
    }

  elif type == 'app.bsky.feed.repost':
    subject = obj.get('subject', {}).get('uri')
    ret = {
      'objectType': 'activity',
      'verb': 'share',
      'id': uri,
      'object': subject,
      'actor': repo_did,
      'published': obj.get('createdAt'),
    }
    if subject and uri_authority:
      if web_url := at_uri_to_web_url(subject):
        # synthetic fragment
        ret['url'] = f'{web_url}#reposted_by_{uri_authority}'

  elif type == 'app.bsky.feed.defs#threadViewPost':
    return to_as1(obj.get('post'), type='app.bsky.feed.defs#postView', **kwargs)

  elif type in ('app.bsky.feed.defs#generatorView',
                'app.bsky.graph.defs#listView'):
    uri = obj.get('uri')
    ret = {
      'objectType': 'service',
      'id': uri,
      'url': at_uri_to_web_url(uri),
      'displayName': (obj.get('displayName')  # generator
                      or obj.get('name')),    # list
      'summary': obj.get('description'),
      'image': obj.get('avatar'),
      'author': to_as1(obj.get('creator'), type='app.bsky.actor.defs#profileView',
                       **kwargs),
    }

  elif type == 'app.bsky.feed.defs#blockedPost':
    uri = obj.get('uri') or uri
    return {
      'objectType': 'note',
      'id': uri,
      'url': at_uri_to_web_url(uri),
      'blocked': True,
      'author': obj.get('blockedAuthor', {}).get('did'),
    }
    return to_as1(obj.get('post'), type='app.bsky.feed.defs#postView', **kwargs)

  else:
    raise ValueError(f'Bluesky object has unknown $type: {type}')

  ret = trim_nulls(ret)
  # ugly hack
  if isinstance(ret, dict) and ret.get('author') == {'objectType': 'person'}:
    del ret['author']

  return ret


def blob_to_url(*, blob, repo_did, pds=DEFAULT_PDS):
  """Generates a URL for a blob.

  Supports both new and old style blobs:
  https://atproto.com/specs/data-model#blob-type

  The resulting URL is a ``com.atproto.sync.getBlob`` XRPC call to the PDS.

  For blobs on the official ``bsky.social`` PDS, we could consider using their CDN
  instead: ``https://av-cdn.bsky.app/img/avatar/plain/[DID]/[CID]@jpeg``

  They also run a resizing image proxy on ``cdn.bsky.social`` with URLs like
  ``https://cdn.bsky.social/imgproxy/[SIG]/rs:fit:2000:2000:1:0/plain/[CID]@jpeg``,
  not sure how to generate signatures for it yet.

  Args:
    blob (dict)
    repo_did (str): DID of the repo that owns this blob
    pds (str): base URL of the PDS that serves this repo. Defaults to
      :const:`DEFAULT_PDS`

  Returns:
    str: URL for this blob, or None if ``blob`` is empty or has no CID
  """
  if not blob:
    return None

  assert repo_did and pds

  cid = blob.get('ref', {}).get('$link') or blob.get('cid')
  if cid:
    path = f'/xrpc/com.atproto.sync.getBlob?did={repo_did}&cid={cid}'
    return urllib.parse.urljoin(pds, path)


class Bluesky(Source):
  """Bluesky source class. See file docstring and :class:`Source` class for
  details.

  Attributes:
    handle (str)
    did (str)
    client (lexrpc.Client)
  """
  DOMAIN = 'bsky.app'
  BASE_URL = 'https://bsky.app'
  NAME = 'Bluesky'
  TRUNCATE_TEXT_LENGTH = 300  # TODO: load from app.bsky.feed.post lexicon
  POST_ID_RE = AT_URI_PATTERN
  TYPE_LABELS = {
    'post': 'post',
    'comment': 'reply',
    'repost': 'repost',
    'like': 'like',
  }

  _client = None
  _app_password = None

  def __init__(self, handle, did=None, access_token=None, refresh_token=None,
               app_password=None, session_callback=None):
    """Constructor.

    Args:
      handle (str): username, eg ``snarfed.bsky.social`` or ``snarfed.org``
      did (str): did:plc or did:web, optional
      access_token (str): optional
      refresh_token (str): optional
      app_password (str): optional
      session_callback (callable, dict => None): passed to :class:`lexrpc.Client`
        constructor, called when a new session is created or refreshed
    """
    self.handle = handle
    self.did = did
    self._app_password = app_password

    headers = {'User-Agent': util.user_agent}
    self._client = Client(access_token=access_token, refresh_token=refresh_token,
                          headers=headers, session_callback=session_callback)

  @property
  def client(self):
    if not self._client.session and self._app_password:
      # log in
      resp = self._client.com.atproto.server.createSession({
        'identifier': self.did or self.handle,
        'password': self._app_password,
      })
      self.handle = resp['handle']
      self.did = resp['did']

    return self._client

  @classmethod
  def user_url(cls, handle):
    """Returns the profile URL for a given handle.

    Args:
      handle (str)

    Returns:
      str: profile URL
    """
    return f'{cls.BASE_URL}/profile/{handle.lstrip("@")}'

  @classmethod
  def user_to_actor(cls, user, **kwargs):
    """Converts a user to an actor.

    Args:
      user (dict): an ``app.bsky.actor.profile`` record
      kwargs: passed through to :func:`to_as1`

    Returns:
      dict: ActivityStreams actor
    """
    return to_as1(user, **kwargs)

  @classmethod
  def post_url(cls, handle, tid):
    """Returns the post URL for a given handle and tid.

    Args:
      handle (str)
      tid (str)

    Returns:
      str: profile URL
    """
    return f'{cls.user_url(handle)}/post/{tid}'

  @classmethod
  def post_id(cls, url):
    """Returns the `at://` URI for the given URL if it's for a post.

    Also see ``arroba.util.parse_at_uri``.

    Returns:
      str or None
    """
    if not url:
      return None

    if not AT_URI_PATTERN.match(url):
      try:
        url = web_url_to_at_uri(url)
      except ValueError:
        return None

    if (len(url.removeprefix('at://').split('/')) == 3
        # only return at:// URIs for posts, not profiles
        and not url.endswith('/app.bsky.actor.profile/self')):
      return url

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, fetch_replies=False,
                              fetch_likes=False, fetch_shares=False,
                              include_shares=True, fetch_mentions=False,
                              search_query=None, start_index=None, count=None,
                              cache=None, **kwargs):
    """Fetches posts and converts them to AS1 activities.

    See :meth:`Source.get_activities_response` for more information.

    Bluesky-specific details:

    Args:
      activity_id (str): an ``at://`` URI
    """
    assert not start_index

    params = {}
    if count is not None:
      params['limit'] = count

    posts = None
    handle = self.handle
    if activity_id:
      if not activity_id.startswith('at://'):
        raise ValueError(f'Expected activity_id to be at:// URI; got {activity_id}')
      resp = self.client.app.bsky.feed.getPostThread({}, uri=activity_id, depth=1)
      posts = [resp.get('thread', {})]

    elif group_id in (None, FRIENDS):
      resp = self.client.app.bsky.feed.getTimeline({}, **params)
      posts = resp.get('feed', [])

    else:  # eg group_id SELF
      actor = user_id or self.did or self.handle
      if not actor:
        raise ValueError('user_id is required')
      resp = self.client.app.bsky.feed.getAuthorFeed({}, actor=actor, **params)
      posts = resp.get('feed', [])

    if cache is None:
      # for convenience, throwaway object just for this method
      cache = {}

    activities = []

    for post in posts:
      reason = post.get('reason')
      is_repost = reason and reason.get('$type') == 'app.bsky.feed.defs#reasonRepost'
      if is_repost and not include_shares:
        continue

      activity = self.postprocess_activity(self._post_to_activity(post))
      activities.append(activity)
      obj = activity['object']
      id = obj.get('id')
      tags = obj.setdefault('tags', [])

      if is_repost:
        # If it's a repost we're not interested in responses to it.
        continue
      bs_post = post.get('post')
      if bs_post and id:
        # Likes
        like_count = bs_post.get('likeCount')
        if fetch_likes and like_count and like_count != cache.get('ABL ' + id):
          likers = self.client.app.bsky.feed.getLikes({}, uri=bs_post.get('uri'))
          tags.extend(self._make_like(bs_post, l.get('actor')) for l in likers.get('likes'))
          cache['ABL ' + id] = like_count

        # Reposts
        repost_count = bs_post.get('repostCount')
        if fetch_shares and repost_count and repost_count != cache.get('ABRP ' + id):
          reposters = self.client.app.bsky.feed.getRepostedBy({}, uri=bs_post.get('uri'))
          tags.extend(self._make_share(bs_post, r) for r in reposters.get('repostedBy'))
          cache['ABRP ' + id] = repost_count

        # Replies
        reply_count = bs_post.get('replyCount')
        if fetch_replies and reply_count and reply_count != cache.get('ABR ' + id):
          replies = self._get_replies(bs_post.get('uri'))
          replies = [to_as1(reply, 'app.bsky.feed.defs#threadViewPost') for reply in replies]
          for r in replies:
            r['id'] = self.tag_uri(r['id'])
          obj['replies'] = {
            'items': replies,
          }
          cache['ABR ' + id] = reply_count

    resp = self.make_activities_base_response(util.trim_nulls(activities))
    return resp

  def get_actor(self, user_id=None):
    """Fetches and returns a user.

    Args:
      user_id (str): either handle or DID; defaults to current user

    Returns:
      dict: ActivityStreams actor
    """
    if user_id is None:
      user_id = self.did or self.handle
    profile = self.client.app.bsky.actor.getProfile({}, actor=user_id)
    return to_as1(profile, type='app.bsky.actor.defs#profileViewDetailed')

  def get_comment(self, comment_id, **kwargs):
    """Fetches and returns a comment.

    Args:
      comment_id: string status id
      **kwargs: unused

    Returns: dict, ActivityStreams object

    Raises:
      :class:`ValueError`: if comment_id is invalid
    """
    post_thread = self.client.app.bsky.feed.getPostThread({}, uri=comment_id, depth=1)
    obj = to_as1(post_thread.get('thread'), 'app.bsky.feed.defs#threadViewPost')
    return obj

  def _post_to_activity(self, post):
    """Converts a post to an activity.

    Args:
      post: Bluesky post app.bluesky.feed.defs#feedViewPost

    Returns: AS1 activity
    """
    obj = to_as1(post, type='app.bsky.feed.defs#feedViewPost')
    if obj.get('objectType') == 'activity':
      return obj
    return {
      'id': obj.get('id'),
      'verb': 'post',
      'actor': obj.get('author'),
      'object': obj,
      'objectType': 'activity',
    }

  def _make_like(self, post, actor):
    return self._make_like_or_share(post, actor, 'like')

  def _make_share(self, post, actor):
    return self._make_like_or_share(post, actor, 'share')

  def _make_like_or_share(self, post, actor, verb):
    """Generates and returns a ActivityStreams like object.

    Args:
      post: dict, Bluesky app.bsky.feed.defs#feedViewPost
      actor: dict, Bluesky app.bsky.actor.defs#profileView
      verb: string, 'like' or 'share'

    Returns: dict, AS1 like activity
    """
    assert verb in ('like', 'share')
    label = 'liked' if verb == 'like' else 'reposted'
    url = at_uri_to_web_url(post.get('uri'), post.get('author').get('handle'))
    actor_id = actor.get('did')
    author = to_as1(actor, 'app.bsky.actor.defs#profileView')
    author['id'] = self.tag_uri(author['id'])
    suffix = f'{label}_by_{actor_id}'
    return {
      'id': self.tag_uri(f'{post.get("uri")}_{suffix}'),
      'url': f'{url}#{suffix}',
      'objectType': 'activity',
      'verb': verb,
      'object': {'url': url},
      'author': author,
    }

  def _get_replies(self, uri):
    """
    Gets the replies to a specific post and returns them
    in ascending order of creation. Does not include the original post.

    Args:
      uri: string, post uri

    Returns: list, Bluesky app.bsky.feed.defs#threadViewPost
    """
    ret = []
    resp = self.client.app.bsky.feed.getPostThread({}, uri=uri)
    thread = resp.get('thread')
    if thread:
      ret = self._recurse_replies(thread)
    return sorted(ret, key = lambda thread: thread.get('post', {}).get('record', {}).get('createdAt') or '')

  # TODO this ought to take a depth limit.
  def _recurse_replies(self, thread):
    """
    Recurses through a Bluesky app.bsky.feed.defs#threadViewPost
    and returns its replies as a list.

    Args:
      thread: dict, Bluesky app.bsky.feed.defs#threadViewPost

    Returns: list, Bluesky app.bsky.feed.defs#threadViewPost
    """
    ret = []
    for r in thread.get('replies', []):
        ret += [r]
        ret += self._recurse_replies(r)
    return ret

  def create(self, obj, include_link=OMIT_LINK, ignore_formatting=False):
    """Creates a post, reply, repost, or like.

    Args:
      obj: ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult: whose content will be a dict with ``id``, ``url``, and
      ``type`` keys (all optional) for the newly created object (or None)
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=OMIT_LINK,
                     ignore_formatting=False):
    """Preview creating a post, reply, repost, or like.

    Args:
      obj: ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult: content will be a str HTML snippet or None
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=OMIT_LINK,
              ignore_formatting=False):
    assert preview in (False, True)
    assert self.did
    type = obj.get('objectType')
    verb = obj.get('verb')

    base_obj = self.base_object(obj)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')

    is_reply = type == 'comment' or obj.get('inReplyTo')
    atts = obj.get('attachments', [])
    images = util.dedupe_urls(util.get_list(obj, 'image') +
                              [a for a in atts if a.get('objectType') == 'image'])
    has_media = images and (type in ('note', 'article') or is_reply)

    # prefer displayName over content for articles
    #
    # TODO: handle activities as well as objects? ie pull out ['object'] here if
    # necessary?
    prefer_content = type == 'note' or (base_url and is_reply)
    preview_description = ''
    content = self._content_for_create(
      obj, ignore_formatting=ignore_formatting, prefer_name=not prefer_content)

    if not content:
      if type == 'activity':
        content = verb
      elif has_media:
        content = ''
      else:
        return creation_result(
          abort=False,  # keep looking for things to publish,
          error_plain='No content text found.',
          error_html='No content text found.')

    # truncate and ellipsize content if necessary
    url = obj.get('url')
    content = self.truncate(content, url, include_link, type)

    # facet for link to original post, if any
    url_facets = []
    if url:
      url_index = content.rfind(url)
      if url_index != -1:
        byte_start = len(content[:url_index].encode())
        url_facets = [{
          '$type': 'app.bsky.richtext.facet',
          'features': [{
            '$type': 'app.bsky.richtext.facet#link',
            'uri': url,
          }],
          'index': {
            'byteStart': byte_start,
            'byteEnd': byte_start + len(url.encode()),
          },
        }]

    # TODO linkify mentions and hashtags
    preview_content = util.linkify(content, pretty=True, skip_bare_cc_tlds=True)

    post_label = f"{self.NAME} {self.TYPE_LABELS['post']}"

    if type == 'activity' and verb == 'like':
      if not base_url:
        return creation_result(
          abort=True,
          error_plain=f"Could not find a {post_label} to {self.TYPE_LABELS['like']}.",
          error_html=f"Could not find a {post_label} to <a href=\"http://indiewebcamp.com/like\">{self.TYPE_LABELS['like']}</a>. Check that your post has the right <a href=\"http://indiewebcamp.com/like\">u-like-of link</a>.")

      if preview:
        preview_description += f"<span class=\"verb\">{self.TYPE_LABELS['like']}</span> <a href=\"{base_url}\">this {self.TYPE_LABELS['post']}</a>."
        return creation_result(description=preview_description)
      else:
        like_atp = from_as1(obj, client=self)
        result = self.client.com.atproto.repo.createRecord({
          'repo': self.did,
          'collection': like_atp['$type'],
          'record': like_atp,
        })
        return creation_result({
          'id': result['uri'],
          'url': at_uri_to_web_url(like_atp['subject']['uri']) + '/liked-by'
        })

    elif type == 'activity' and verb == 'share':
      if not base_url:
        return creation_result(
          abort=True,
          error_plain=f"Could not find a {post_label} to {self.TYPE_LABELS['repost']}.",
          error_html=f"Could not find a {post_label} to <a href=\"http://indiewebcamp.com/repost\">{self.TYPE_LABELS['repost']}</a>. Check that your post has the right <a href=\"http://indiewebcamp.com/repost\">repost-of</a> link.")

      if preview:
          preview_description += f"<span class=\"verb\">{self.TYPE_LABELS['repost']}</span> <a href=\"{base_url}\">this {self.TYPE_LABELS['post']}</a>."
          return creation_result(description=preview_description)
      else:
        repost_atp = from_as1(obj, client=self)
        result = self.client.com.atproto.repo.createRecord({
          'repo': self.did,
          'collection': repost_atp['$type'],
          'record': repost_atp,
        })
        return creation_result({
          'id': result['uri'],
          'url': at_uri_to_web_url(repost_atp['subject']['uri']) + '/reposted-by'
        })

    elif (type in ('note', 'article') or is_reply or
          (type == 'activity' and verb == 'post')):  # probably a bookmark
      # TODO: add bookmarked URL and facet
      # tricky because we only want to do that if it's not truncated away
      data = {'status': content}
      if is_reply and base_url:
        preview_description += f"<span class=\"verb\">{self.TYPE_LABELS['comment']}</span> to <a href=\"{base_url}\">this {self.TYPE_LABELS['post']}</a>:"
        data['in_reply_to_id'] = base_id
      else:
        preview_description += f"<span class=\"verb\">{self.TYPE_LABELS['post']}</span>:"

      videos = util.dedupe_urls(
        [obj] + [a for a in atts if a.get('objectType') == 'video'], key='stream')
      if videos:
        logger.warning(f'Found {len(videos)} videos, but Bluesky doesn\'t support video yet.')

      if len(images) > MAX_IMAGES:
        images = images[:MAX_IMAGES]
        logger.warning(f'Found {len(images)} images! Only using the first {MAX_IMAGES}: {images!r}')

      if preview:
        media_previews = [
          f"<img src=\"{util.get_url(img)}\" alt=\"{img.get('displayName') or ''}\" />"
          for img in images
        ]
        if media_previews:
          preview_content += '<br /><br />' + ' &nbsp; '.join(media_previews)

        return creation_result(content=preview_content,
                               description=preview_description)

      else:
        blobs = self.upload_media(images)
        post_atp = from_as1(obj, blobs=blobs, client=self)
        post_atp.update({
          'text': content,
          'facets': url_facets,
        })
        result = self.client.com.atproto.repo.createRecord({
          'repo': self.did,
          'collection': post_atp['$type'],
          'record': post_atp,
        })
        return creation_result({
          'id': result['uri'],
          'url': at_uri_to_web_url(result['uri'], handle=self.handle),
        })

    return creation_result(
      abort=False,
      error_plain=f'Cannot publish type={type}, verb={verb} to Bluesky',
      error_html=f'Cannot publish type={type}, verb={verb} to Bluesky')

  def delete(self, at_uri):
    """Deletes a record.

    Args:
      at_uri (str): at:// URI of record delete

    Returns:
      CreationResult: content is dict with ``url`` and ``id`` fields
    """
    match = AT_URI_PATTERN.match(at_uri)
    if not match:
      raise ValueError(f'Expected at:// URI, got {at_uri}')

    authority, collection, rkey = match.groups()
    self.client.com.atproto.repo.deleteRecord({
      'repo': authority,
      'collection': collection,
      'rkey': rkey,
    })
    return creation_result({
      'id': at_uri,
      'url': at_uri_to_web_url(at_uri),
    })

  def preview_delete(self, at_uri):
    """Previews deleting a record.

    Args:
      at_uri (str): at:// URI of record delete

    Returns:
      CreationResult:
    """
    url = at_uri_to_web_url(at_uri)
    return creation_result(description=f'<span class="verb">delete</span> <a href="{url}">this</a>.')

  def base_object(self, obj):
    return base_object(obj)

  def upload_media(self, media):
    blobs = {}

    for obj in media:
      url = util.get_url(obj, key='stream') or util.get_url(obj)
      if not url or url in blobs:
        continue

      with util.requests_get(url, stream=True) as fetch:
        fetch.raise_for_status()
        upload = self.client.com.atproto.repo.uploadBlob(
          input=fetch.raw,
          headers={'Content-Type': fetch.headers['Content-Type']}
        )

      blobs[url] = upload['blob']

    return blobs
