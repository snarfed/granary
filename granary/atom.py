"""Convert between ActivityStreams 1 and Atom.

Atom spec: https://tools.ietf.org/html/rfc4287 (RIP atomenabled.org)
"""
from __future__ import absolute_import, unicode_literals
from future import standard_library
standard_library.install_aliases()
from builtins import str

import collections
import mimetypes
import os
import re
import urllib.parse
from xml.etree import ElementTree
import xml.sax.saxutils

from bs4 import BeautifulSoup
import jinja2
import mf2py
import mf2util
from oauth_dropins.webutil import util

from . import microformats2
from . import source

FEED_TEMPLATE = 'user_feed.atom'
ENTRY_TEMPLATE = 'entry.atom'
# stolen from django.utils.html
UNENCODED_AMPERSANDS_RE = re.compile(r'&(?!(\w+|#\d+);)')
NAMESPACES = {
  'activity': 'http://activitystrea.ms/spec/1.0/',
  'atom': 'http://www.w3.org/2005/Atom',
  'georss': 'http://www.georss.org/georss',
  'thr': 'http://purl.org/syndication/thread/1.0',
}

jinja_env = jinja2.Environment(
  loader=jinja2.PackageLoader(__package__, 'templates'), autoescape=True)


def _encode_ampersands(text):
  return UNENCODED_AMPERSANDS_RE.sub('&amp;', text)


def _tag(elem):
  """Removes the namespace from an ElementTree element tag."""
  return elem.tag.split('}')[-1]


def _text(elem, field=None):
  """Returns the text in an element or child element if it exists.

  For example, if field is 'name' and elem contains <name>Ryan</name>, returns
  'Ryan'.

  Args:
    elem: ElementTree.Element
    field: string

  Returns: string or None

  """
  if field:
    if ':' not in field:
      field = 'atom:' + field
    elem = elem.find(field, NAMESPACES)

  if elem is not None and elem.text:
    text = elem.text
    if not isinstance(elem.text, str):
      text = text.decode('utf-8')
    return text.strip()


def _as1_value(elem, field):
  """Returns an AS1 namespaced schema value if it exists.

  For example, returns 'like' for field 'verb' if elem contains:

    <activity:verb>http://activitystrea.ms/schema/1.0/like</activity:verb>

  Args:
    elem: ElementTree.Element
    field: string

  Returns: string or None
  """
  type = _text(elem, 'activity:%s' % field)
  if type:
    return type.split('/')[-1]


# Emulate Django template behavior that returns a special default value that
# can continue to be referenced when an attribute or item lookup fails. Helps
# avoid conditionals in the template itself.
# https://docs.djangoproject.com/en/1.8/ref/templates/language/#variables
class Defaulter(collections.defaultdict):
  def __init__(self, init={}):
    super(Defaulter, self).__init__(
      Defaulter, {k: self.__defaulter(v) for k, v in init.items()})

  @classmethod
  def __defaulter(cls, obj):
    if isinstance(obj, dict):
      return Defaulter(obj)
    elif isinstance(obj, (tuple, list, set)):
      return obj.__class__(cls.__defaulter(elem) for elem in obj)
    else:
      return obj

  def __unicode__(self):
    return super(Defaulter, self).__unicode__() if self else ''

  __str__ = __unicode__

  def __hash__(self):
    return super(Defaulter, self).__hash__() if self else None.__hash__()


def activities_to_atom(activities, actor, title=None, request_url=None,
                       host_url=None, xml_base=None, rels=None, reader=True):
  """Converts ActivityStreams 1 activities to an Atom feed.

  Args:
    activities: list of ActivityStreams activity dicts
    actor: ActivityStreams actor dict, the author of the feed
    title: string, the feed <title> element. Defaults to 'User feed for [NAME]'
    request_url: the URL of this Atom feed, if any. Used in a link rel="self".
    host_url: the home URL for this Atom feed, if any. Used in the top-level
      feed <id> element.
    xml_base: the base URL, if any. Used in the top-level xml:base attribute.
    rels: rel links to include. dict mapping string rel value to string URL.
    reader: boolean, whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    unicode string with Atom XML
  """
  # Strip query params from URLs so that we don't include access tokens, etc
  host_url = (_remove_query_params(host_url) if host_url
              else 'https://github.com/snarfed/granary')
  if request_url is None:
    request_url = host_url

  for a in activities:
    _prepare_activity(a, reader=reader)

  if actor is None:
    actor = {}
  return jinja_env.get_template(FEED_TEMPLATE).render(
    actor=Defaulter(actor),
    host_url=host_url,
    items=[Defaulter(a) for a in activities],
    mimetypes=mimetypes,
    rels=rels or {},
    request_url=request_url,
    title=title or 'User feed for ' + source.Source.actor_name(actor),
    updated=activities[0]['object'].get('published', '') if activities else '',
    VERBS_WITH_OBJECT=source.VERBS_WITH_OBJECT,
    xml_base=xml_base,
  )


def activity_to_atom(activity, xml_base=None, reader=True):
  """Converts a single ActivityStreams 1 activity to an Atom entry.

  Kwargs are passed through to :func:`activities_to_atom`.

  Args:
    xml_base: the base URL, if any. Used in the top-level xml:base attribute.
    reader: boolean, whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    unicode string with Atom XML
  """
  _prepare_activity(activity, reader=reader)
  return jinja_env.get_template(ENTRY_TEMPLATE).render(
    activity=Defaulter(activity),
    mimetypes=mimetypes,
    VERBS_WITH_OBJECT=source.VERBS_WITH_OBJECT,
    xml_base=xml_base,
  )


def atom_to_activities(atom):
  """Converts an Atom feed to ActivityStreams 1 activities.

  Args:
    atom: unicode string, Atom document with top-level <feed> element

  Returns:
    list of ActivityStreams activity dicts
  """
  assert isinstance(atom, str)
  parser = ElementTree.XMLParser(encoding='UTF-8')
  feed = ElementTree.XML(atom.encode('utf-8'), parser=parser)
  if _tag(feed) != 'feed':
    raise ValueError('Expected root feed tag; got %s' % feed.tag)
  return [_atom_to_activity(elem) for elem in feed if _tag(elem) == 'entry']


def atom_to_activity(atom):
  """Converts an Atom entry to an ActivityStreams 1 activity.

  Args:
    atom: unicode string, Atom document with top-level <entry> element

  Returns:
    dict, ActivityStreams activity
  """
  assert isinstance(atom, str)
  parser = ElementTree.XMLParser(encoding='UTF-8')
  entry = ElementTree.XML(atom.encode('utf-8'), parser=parser)
  if _tag(entry) != 'entry':
    raise ValueError('Expected root entry tag; got %s' % entry.tag)
  return _atom_to_activity(entry)


def _atom_to_activity(entry):
  """Converts an internal Atom entry element to an ActivityStreams 1 activity.

  Args:
    entry: ElementTree <entry> element

  Returns:
    dict, ActivityStreams activity
  """
  # default object data from entry. override with data inside activity:object.
  obj_elem = entry.find('activity:object', NAMESPACES)
  obj = _atom_to_object(obj_elem if obj_elem is not None else entry)

  content = entry.find('atom:content', NAMESPACES)
  if content is not None:
    # TODO: use 'html' instead of 'text' to include HTML tags. the problem is,
    # if there's an embedded XML namespace, it prefixes *every* tag with that
    # namespace. breaks on e.g. the <div xmlns="http://www.w3.org/1999/xhtml">
    # that our Atom templates wrap HTML content in.
    text = ElementTree.tostring(content, 'utf-8', 'text').decode('utf-8')
    obj['content'] = re.sub(r'\s+', ' ', text.strip())

  point = _text(entry, 'georss:point')
  if point:
    lat, long = point.split(' ')
    obj['location'].update({
      'latitude': float(lat),
      'longitude': float(long),
    })

  a = {
    'objectType': 'activity',
    'verb': _as1_value(entry, 'verb'),
    'id': _text(entry, 'id') or (obj['id'] if obj_elem is None else None),
    'url': _text(entry, 'uri') or (obj['url'] if obj_elem is None else None),
    'object': obj,
    'actor': _author_to_actor(entry),
    'inReplyTo': obj.get('inReplyTo'),
  }

  return source.Source.postprocess_activity(a)


def _atom_to_object(elem):
  """Converts an Atom entry to an ActivityStreams 1 object.

  Args:
    elem: ElementTree.Element

  Returns:
    dict, ActivityStreams object
  """
  uri = _text(elem, 'uri') or _text(elem)
  return {
    'objectType': _as1_value(elem, 'object-type'),
    'id': _text(elem, 'id') or uri,
    'url': uri,
    'title': _text(elem, 'title'),
    'published': _text(elem, 'published'),
    'updated': _text(elem, 'updated'),
    'inReplyTo': [{
      'id': r.attrib.get('ref') or _text(r),
      'url': r.attrib.get('href') or _text(r),
    } for r in elem.findall('thr:in-reply-to', NAMESPACES)],
    'location': {
      'displayName': _text(elem, 'georss:featureName'),
    }
  }


def _author_to_actor(elem):
  """Converts an Atom <author> element to an ActivityStreams 1 actor.

   Looks for <author> *inside* elem.

  Args:
    elem: ElementTree.Element

  Returns:
    dict, ActivityStreams actor object
  """
  author = elem.find('atom:author', NAMESPACES)
  if author is not None:
      return {
        'objectType': _as1_value(author, 'object-type'),
        'id': _text(author, 'id'),
        'url': _text(author, 'uri'),
        'displayName': _text(author, 'name'),
        'email': _text(author, 'email'),
      }


def html_to_atom(html, url=None, fetch_author=False, reader=True):
  """Converts microformats2 HTML to an Atom feed.

  Args:
    html: string
    url: string URL html came from, optional
    fetch_author: boolean, whether to make HTTP request to fetch rel-author link
    reader: boolean, whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    unicode string with Atom XML
  """
  if fetch_author:
    assert url, 'fetch_author=True requires url!'

  parsed = mf2py.parse(doc=html, url=url)
  actor = microformats2.find_author(
    parsed, fetch_mf2_func=lambda url: mf2py.parse(url=url))

  return activities_to_atom(
    microformats2.html_to_activities(html, url, actor),
    actor,
    title=mf2util.interpret_feed(parsed, url).get('name'),
    xml_base=util.base_url(url),
    host_url=url,
    reader=reader)


def _prepare_activity(a, reader=True):
  """Preprocesses an activity to prepare it to be rendered as Atom.

  Modifies a in place.

  Args:
    a: ActivityStreams 1 activity dict
    reader: boolean, whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.
  """
  act_type = source.object_type(a)
  if not act_type or act_type == 'post':
    primary = a.get('object', {})
  else:
    primary = a
  obj = a.setdefault('object', {})

  # Render content as HTML; escape &s
  obj['rendered_content'] = _encode_ampersands(microformats2.render_content(
    primary, include_location=reader, render_attachments=True))

  # Make sure every activity has the title field, since Atom <entry> requires
  # the title element.
  if not a.get('title'):
    a['title'] = util.ellipsize(_encode_ampersands(
      a.get('displayName') or a.get('content') or obj.get('title') or
      obj.get('displayName') or obj.get('content') or 'Untitled'))

  # strip HTML tags. the Atom spec says title is plain text:
  # http://atomenabled.org/developers/syndication/#requiredEntryElements
  a['title'] = xml.sax.saxutils.escape(BeautifulSoup(a['title']).get_text(''))

  children = []
  image_urls_seen = set()
  image_atts = []

  # normalize attachments, render attached notes/articles
  attachments = a.get('attachments') or obj.get('attachments') or []
  for att in attachments:
    att['stream'] = util.get_first(att, 'stream')
    type = att.get('objectType')

    if type == 'image':
      image_atts.append(util.get_first(att, 'image'))
      continue

    image_urls_seen |= set(util.get_urls(att, 'image'))
    if type in ('note', 'article'):
      html = microformats2.render_content(att, include_location=reader,
                                          render_attachments=True)
      author = att.get('author')
      if author:
        name = microformats2.maybe_linked_name(
          microformats2.object_to_json(author).get('properties', []))
        html = '%s: %s' % (name.strip(), html)
      children.append(html)

  # render image(s) that we haven't already seen
  for image in image_atts + util.get_list(obj, 'image'):
    if not image:
      continue
    url = image.get('url')
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme
    netloc = parsed.netloc
    rest = urllib.parse.urlunparse(('', '') + parsed[2:])
    img_src_re = re.compile(r"""src *= *['"] *((https?:)?//%s)?%s *['"]""" %
                            (re.escape(netloc), re.escape(rest)))
    if (url and url not in image_urls_seen and
        not img_src_re.search(obj['rendered_content'])):
      children.append(microformats2.img(url))
      image_urls_seen.add(url)

  obj['rendered_children'] = [_encode_ampersands(html) for html in children]

  # make sure published and updated are strict RFC 3339 timestamps
  for prop in 'published', 'updated':
    val = obj.get(prop)
    if val:
      obj[prop] = util.maybe_iso8601_to_rfc3339(val)
      # Atom timestamps are even stricter than RFC 3339: they can't be naive ie
      # time zone unaware. They must have either an offset or the Z suffix.
      # https://www.feedvalidator.org/docs/error/InvalidRFC3339Date.html
      if not util.TIMEZONE_OFFSET_RE.search(obj[prop]):
        obj[prop] += 'Z'

def _remove_query_params(url):
  parsed = list(urllib.parse.urlparse(url))
  parsed[4] = ''
  return urllib.parse.urlunparse(parsed)
