"""Convert ActivityStreams to Atom.

Atom spec: http://atomenabled.org/developers/syndication/
"""

import collections
import os
import re
import urlparse
import xml.sax.saxutils

from bs4 import BeautifulSoup
import jinja2
import mf2py
import mf2util
from oauth_dropins.webutil import util

import microformats2
import source

FEED_TEMPLATE = 'user_feed.atom'
ENTRY_TEMPLATE = 'entry.atom'
# stolen from django.utils.html
UNENCODED_AMPERSANDS_RE = re.compile(r'&(?!(\w+|#\d+);)')

jinja_env = jinja2.Environment(
  loader=jinja2.PackageLoader(__package__, 'templates'), autoescape=True)


def _encode_ampersands(text):
  return UNENCODED_AMPERSANDS_RE.sub('&amp;', text)


# Emulate Django template behavior that returns a special default value that
# can continue to be referenced when an attribute or item lookup fails. Helps
# avoid conditionals in the template itself.
# https://docs.djangoproject.com/en/1.8/ref/templates/language/#variables
class Defaulter(collections.defaultdict):
  def __init__(self, **kwargs):
    super(Defaulter, self).__init__(Defaulter, **{
      k: (Defaulter(**v) if isinstance(v, dict) else v)
      for k, v in kwargs.items()})

  def __unicode__(self):
    return super(Defaulter, self).__unicode__() if self else u''


def activities_to_atom(activities, actor, title=None, request_url=None,
                       host_url=None, xml_base=None, rels=None, reader=True):
  """Converts ActivityStreams activities to an Atom feed.

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
    items=[Defaulter(**a) for a in activities],
    host_url=host_url,
    request_url=request_url,
    xml_base=xml_base,
    title=title or 'User feed for ' + source.Source.actor_name(actor),
    updated=activities[0]['object'].get('published', '') if activities else '',
    actor=Defaulter(**actor),
    rels=rels or {},
    )


def activity_to_atom(activity, xml_base=None, reader=True):
  """Converts a single ActivityStreams activity to an Atom entry.

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
    activity=Defaulter(**activity),
    xml_base=xml_base,
  )


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
    a: ActivityStreams activity dict
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
    primary, include_location=reader))

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
  image_urls = set()

  # render attached notes/articles
  attachments = a.get('attachments') or obj.get('attachments') or []
  for att in attachments:
    image_urls |= set(img.get('url') for img in util.get_list(att, 'image'))
    if att.get('objectType') in ('note', 'article'):
      html = microformats2.render_content(att, include_location=reader)
      author = att.get('author')
      if author:
        name = microformats2.maybe_linked_name(
          microformats2.object_to_json(author).get('properties', []))
        html = '%s: %s' % (name.strip(), html)
      children.append(html)

  # render image(s) that we haven't already seen
  content = obj.get('content', '')
  for image in util.get_list(obj, 'image'):
    if not image:
      continue
    url = image.get('url')
    parsed = urlparse.urlparse(url)
    scheme = parsed.scheme
    netloc = parsed.netloc
    rest = urlparse.urlunparse(('', '') + parsed[2:])
    img_src_re = re.compile(r"""src *= *['"] *((%s)?//%s)?%s *['"]""" %
                            (scheme, re.escape(netloc), re.escape(rest)))
    if (url and url not in image_urls and
        not img_src_re.search(content)):
      children.append(microformats2.img(image['url'], 'u-photo'))

  obj['rendered_children'] = [_encode_ampersands(html) for html in children]


def _remove_query_params(url):
  parsed = list(urlparse.urlparse(url))
  parsed[4] = ''
  return urlparse.urlunparse(parsed)
