"""Convert between ActivityStreams 1 and Atom.

Atom spec: https://tools.ietf.org/html/rfc4287 (RIP atomenabled.org)
"""
import collections
import mimetypes
import re
import urllib.parse
from xml.etree import ElementTree
import xml.sax.saxutils

import jinja2
from oauth_dropins.webutil import util

from . import as1
from . import microformats2
from .source import Source

CONTENT_TYPE = 'application/atom+xml; charset=utf-8'
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

  For example, if field is ``name`` and elem contains ``<name>Ryan</name>``,
  returns ``Ryan``.

  Args:
    elem (ElementTree.Element)
    field (str)

  Returns:
    str or None:
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

  For example, returns ``like`` for field ``verb`` if elem contains::

      <activity:verb>http://activitystrea.ms/schema/1.0/like</activity:verb>

  Args:
    elem (ElementTree.Element)
    field (str)

  Returns:
    str or None:
  """
  type = _text(elem, f'activity:{field}')
  if type:
    return type.split('/')[-1]


class Defaulter(collections.defaultdict):
  """Emulates Django template behavior that returns a special default value that
  can continue to be referenced when an attribute or item lookup fails. Helps
  avoid conditionals in the template itself.

  https://docs.djangoproject.com/en/1.8/ref/templates/language/#variables
  """
  def __init__(self, init={}):
    super().__init__(Defaulter, {k: self.__defaulter(v) for k, v in init.items()})

  @classmethod
  def __defaulter(cls, obj):
    if isinstance(obj, dict):
      return Defaulter(obj)
    elif isinstance(obj, (tuple, list, set)):
      return obj.__class__(cls.__defaulter(elem) for elem in obj)
    else:
      return obj

  def __str__(self):
    return str(super()) if self else ''

  __eq__ = collections.defaultdict.__eq__

  def __hash__(self):
    return super().__hash__() if self else None.__hash__()


def activities_to_atom(activities, actor, title=None, request_url=None,
                       host_url=None, xml_base=None, rels=None, reader=True):
  """Converts ActivityStreams 1 activities to an Atom feed.

  Args:
    activities (list of dict): ActivityStreams activities
    actor (dict): ActivityStreams actor, the author of the feed
    title (str): the feed <title> element. Defaults to ``User feed for [NAME]``
    request_url (str): URL of this Atom feed, if any. Used in a link rel="self".
    host_url (str): home URL for this Atom feed, if any. Used in the top-level
      feed ``<id>`` element.
    xml_base (str): base URL, if any. Used in the top-level ``xml:base``
      attribute.

    rels (dict): rel links to include. Keys are string ``rel``s, values are
      string URLs.
    reader (bool): whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    str: Atom XML
  """
  # Strip query params from URLs so that we don't include access tokens, etc
  host_url = (_remove_query_params(host_url) if host_url
              else 'https://github.com/snarfed/granary')
  if request_url is None:
    request_url = host_url

  _prepare_actor(actor)
  for a in activities:
    _prepare_activity(a, reader=reader)

  updated = (as1.get_object(activities[0]).get('published', '')
             if activities else '')

  if actor is None:
    actor = {}

  return jinja_env.get_template(FEED_TEMPLATE).render(
    actor=Defaulter(actor),
    host_url=host_url,
    items=[Defaulter(a) for a in activities],
    mimetypes=mimetypes,
    rels=rels or {},
    request_url=request_url,
    title=title or 'User feed for ' + as1.actor_name(actor),
    updated=updated,
    VERBS_WITH_OBJECT=as1.VERBS_WITH_OBJECT,
    xml_base=xml_base,
    as1=as1,
  )


def activity_to_atom(activity, xml_base=None, reader=True):
  """Converts a single ActivityStreams 1 activity to an Atom entry.

  Kwargs are passed through to :func:`activities_to_atom`.

  Args:
    xml_base (str): the base URL, if any. Used in the top-level ``xml:base``
      attribute.
    reader (bool): whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    str: Atom XML
  """
  _prepare_activity(activity, reader=reader)
  return jinja_env.get_template(ENTRY_TEMPLATE).render(
    activity=Defaulter(activity),
    mimetypes=mimetypes,
    VERBS_WITH_OBJECT=as1.VERBS_WITH_OBJECT,
    xml_base=xml_base,
    as1=as1,
  )


def atom_to_activities(atom):
  """Converts an Atom feed to ActivityStreams 1 activities.

  Args:
    atom (str): Atom document with top-level ``<feed>`` element

  Returns:
    list of dict: ActivityStreams activities
  """
  assert isinstance(atom, str)
  parser = ElementTree.XMLParser(encoding='UTF-8')
  top = ElementTree.XML(atom.encode('utf-8'), parser=parser)
  if _tag(top) == 'feed':
    author = _author_to_actor(top)
    return [_atom_to_activity(elem, feed_author=author)
            for elem in top if _tag(elem) == 'entry']
  elif _tag(top) == 'entry':
    return [_atom_to_activity(top)]

  raise ValueError(f'Expected root feed or entry tag; got {top.tag}')


def atom_to_activity(atom):
  """Converts an Atom entry to an ActivityStreams 1 activity.

  Args:
    atom (str): Atom document with top-level ``<entry>`` element

  Returns:
    dict: ActivityStreams activity
  """
  got = atom_to_activities(atom)
  if got:
    return got[0]


def _atom_to_activity(entry, feed_author=None):
  """Converts an internal Atom entry element to an ActivityStreams 1 activity.

  Args:
    entry (ElementTree.Element)
    feed_author (dict): optional, AS1 representation of feed author

  Returns:
    dict: ActivityStreams activity
  """
  # default object data from entry. override with data inside activity:object.
  obj_elem = entry.find('activity:object', NAMESPACES)
  obj = _atom_to_object(obj_elem if obj_elem is not None else entry,
                        feed_author=feed_author)

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
    'verb': _as1_value(entry, 'verb') or 'post',
    'id': _text(entry, 'id') or (obj['id'] if obj_elem is None else None),
    'url': _text(entry, 'uri') or (obj['url'] if obj_elem is None else None),
    'object': obj,
    'actor': _author_to_actor(entry, feed_author=feed_author),
    'inReplyTo': obj.get('inReplyTo'),
  }

  return Source.postprocess_activity(a, mentions=True)


def _atom_to_object(elem, feed_author=None):
  """Converts an Atom entry to an ActivityStreams 1 object.

  Args:
    elem (ElementTree.Element)
    feed_author (dict): optional, AS1 representation of feed author

  Returns:
    dict: ActivityStreams object
  """
  self_links = [link for link in elem.iterfind('atom:link', NAMESPACES)
                if link.get('rel') in ('self', 'alternate', None)
                and link.get('type', '').split(';')[0] in ('text/html', '')]
  uri = (_text(elem, 'uri')
         or (self_links[0].get('href') if self_links else None)
         or _text(elem))

  title = _text(elem, 'title')
  return {
    'objectType': _as1_value(elem, 'object-type') or 'article' if title else 'note',
    'id': _text(elem, 'id') or uri,
    'author': _author_to_actor(elem, feed_author=feed_author),
    'url': uri,
    'displayName': title,
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


def _author_to_actor(elem, feed_author=None):
  """Converts an Atom ``<author>`` element to an ActivityStreams 1 actor.

   Looks for ``<author>`` *inside* elem.

  Args:
    elem (ElementTree.Element)
    feed_author (dict): optional, AS1 representation of feed author

  Returns:
    dict: ActivityStreams actor object
  """
  actor = {}

  author = elem.find('atom:author', NAMESPACES)
  if author is not None:
      actor = {
        'objectType': _as1_value(author, 'object-type'),
        'id': _text(author, 'id'),
        'url': _text(author, 'uri'),
        'displayName': _text(author, 'name'),
        'email': _text(author, 'email'),
      }

  if feed_author:
    for field in 'id', 'url':
      # can't setdefault because actor has None values for id and url
      if not actor.get(field):
        actor[field] = feed_author.get(field)

  return actor

def html_to_atom(html, url=None, fetch_author=False, reader=True):
  """Converts microformats2 HTML to an Atom feed.

  Args:
    html (str)
    url (str): URL html came from, optional
    fetch_author (bool): whether to make HTTP request to fetch ``rel-author``
      link
    reader (bool): whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    str: Atom XML
  """
  if fetch_author:
    assert url, 'fetch_author=True requires url!'

  parsed = util.parse_mf2(html, url=url)
  actor = microformats2.find_author(parsed, fetch_mf2_func=util.fetch_mf2)

  return activities_to_atom(
    microformats2.html_to_activities(html, url, actor),
    actor,
    title=microformats2.get_title(parsed),
    xml_base=util.base_url(url),
    host_url=url,
    reader=reader)


def _prepare_activity(a, reader=True):
  """Preprocesses an activity to prepare it to be rendered as Atom.

  Modifies ``a`` in place.

  Args:
    a (dict): ActivityStreams 1 activity
    reader (bool): whether the output will be rendered in a feed reader.
      Currently just includes location if True, not otherwise.

  Returns:
    ``None``
  """
  act_type = as1.object_type(a)
  obj = as1.get_object(a) or a
  primary = obj if (not act_type or act_type == 'post') else a

  # Render content as HTML; escape &s
  obj['rendered_content'] = _encode_ampersands(microformats2.render_content(
    primary, include_location=reader, render_attachments=True,
    # Readers often obey CSS white-space: pre strictly and don't even line wrap,
    # so don't use it.
    # https://forum.newsblur.com/t/android-cant-read-line-pre-formatted-lines/6116
    white_space_pre=False))

  # Make sure every activity has displayName, since Atom <entry> requires the
  # title element. and strip HTML tags, the Atom spec says title is plain text:
  # http://atomenabled.org/developers/syndication/#requiredEntryElements
  display_name = (a.get('displayName') or a.get('content') or obj.get('title')
                  or obj.get('displayName') or obj.get('content') or 'Untitled')
  a['displayName'] = util.ellipsize(xml.sax.saxutils.escape(
    util.parse_html(display_name).get_text('')))

  children = []
  image_urls_seen = set()
  image_atts = []

  # normalize actors
  for elem in a, obj:
    for field in 'actor', 'author':
      elem[field] = as1.get_object(elem, field)
      _prepare_actor(elem[field])

  # normalize attachments, render attached notes/articles
  attachments = a.get('attachments') or obj.get('attachments') or []
  for att in attachments:
    att['stream'] = util.get_first(att, 'stream')
    type = att.get('objectType')

    if type == 'image':
      att['image'] = util.get_first(att, 'image')
      image_atts.append(as1.get_object(att, 'image') or att)
      continue

    if type in ('note', 'article', 'comment', 'service'):
      # only render this attachment's images if at least one is new
      images = set(util.get_urls(att, 'image'))
      render_image = bool(images - image_urls_seen)
      image_urls_seen |= images
      html = microformats2.render_content(
        att, include_location=reader, render_attachments=True,
        render_image=render_image, white_space_pre=False)
      author = att.get('author')
      if author:
        name = microformats2.maybe_linked_name(
          microformats2.object_to_json(author).get('properties') or {})
        html = f'{name.strip()}: {html}'
      children.append(html)

  # render image(s) that we haven't already seen
  for image in image_atts + as1.get_objects(obj, 'image'):
    if not image:
      continue
    url = image.get('url') or image.get('id')
    parsed = urllib.parse.urlparse(url)
    rest = urllib.parse.urlunparse(('', '') + parsed[2:])
    img_src_re = re.compile(r"""src *= *['"] *((https?:)?//%s)?%s *['"]""" %
                            (re.escape(parsed.netloc),
                             _encode_ampersands(re.escape(rest))))
    if (url and url not in image_urls_seen and
        not img_src_re.search(obj['rendered_content'])):
      children.append(microformats2.img(url))
      image_urls_seen.add(url)

  obj['rendered_children'] = [_encode_ampersands(child) for child in children]

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


def _prepare_actor(actor):
  """Preprocesses an AS1 actor to prepare it to be rendered as Atom.

  Modifies actor in place.

  Args:
    actor (dict): ActivityStreams 1 actor
  """
  if not actor:
    return

  actor['image'] = util.get_first(actor, 'image')
  actor.setdefault('displayName', actor.get('username'))


def _remove_query_params(url):
  parsed = list(urllib.parse.urlparse(url))
  parsed[4] = ''
  return urllib.parse.urlunparse(parsed)


def extract_entries(atom):
  """Extracts ``<entry>`` elements into their own separate XML documents.

  Args:
    atom (str): Atom document with top-level ``<feed>`` or ``<entry>`` element

  Returns:
    list of str: Atom documents with top-level ``<entry>`` element for each entry
  """
  assert isinstance(atom, str), atom.__class__
  ElementTree.register_namespace('', 'http://www.w3.org/2005/Atom')
  parser = ElementTree.XMLParser(encoding='UTF-8')
  top = ElementTree.XML(atom.encode('utf-8'), parser=parser)

  if _tag(top) == 'feed':
    entries = [elem for elem in top if _tag(elem) == 'entry']
  elif _tag(top) == 'entry':
    entries = [top]
  else:
    raise ValueError(f'Expected root feed or entry tag; got {top.tag}')

  header = '<?xml version="1.0" encoding="UTF-8"?>\n'
  return [header + ElementTree.tostring(e, encoding='unicode') for e in entries]
