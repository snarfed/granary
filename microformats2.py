"""Convert ActivityStreams to microformats2 HTML and JSON.

Microformats2 specs: http://microformats.org/wiki/microformats2
"""

import xml.sax.saxutils
import itertools
import urlparse
import string

import source
from oauth_dropins.webutil import util

# TODO: comments
HENTRY = string.Template("""\
<article class="$types">
  <span class="u-uid">$uid</span>
  $linked_name
  $summary
  $published
  $updated
$author
  <div class="$content_classes">
  $invitees
  $content
  </div>
$video
$photo
$location
$in_reply_tos
$likes_and_reposts
$comments
</article>
""")
HCARD = string.Template("""\
  <div class="$types">
    $linked_name
    $photo
  </div>
""")
IN_REPLY_TO = string.Template('  <a class="u-in-reply-to" href="$url"></a>')


def get_string_urls(objs):
  """Extracts string URLs from a list of either string URLs or mf2 dicts.

  Many mf2 properties can contain either string URLs or full mf2 objects, e.g.
  h-cites. in-reply-to is the most commenly used example:
  http://indiewebcamp.com/in-reply-to#How_to_consume_in-reply-to

  Args:
    objs: sequence of either string URLs or embedded mf2 objects

  Returns: list of string URLs
  """
  urls = []
  for item in objs:
    if isinstance(item, basestring):
      urls.append(item)
    else:
      itemtype = [x for x in item.get('type', []) if x.startswith('h-')]
      if itemtype:
        urls.extend(item.get('properties', {}).get('url', []))
  return urls


def get_html(val):
  """Returns a string value that may have HTML markup.

  Args:
    value: mf2 property value, either string or
     {'html': '<p>str</p>', 'value': 'str'} dict

  Returns: string or None
  """
  return val.get('html') or val.get('value') if isinstance(val, dict) else val


def get_text(val):
  """Returns a plain text string value. See get_html."""
  return val.get('value') if isinstance(val, dict) else val


def object_to_json(obj, ctx={}, trim_nulls=True):
  """Converts an ActivityStreams object to microformats2 JSON.

  Args:
    obj: dict, a decoded JSON ActivityStreams object
    ctx: dict, a decoded JSON ActivityStreams context
    trim_nulls: boolean, whether to remove elements with null or empty values

  Returns: dict, decoded microformats2 JSON
  """
  if not obj:
    return {}

  types_map = {'article': ['h-entry', 'h-as-article'],
               'comment': ['h-entry', 'p-comment'],
               'like': ['h-entry', 'h-as-like'],
               'note': ['h-entry', 'h-as-note'],
               'person': ['h-card'],
               'place': ['h-card', 'p-location'],
               'share': ['h-entry', 'h-as-repost'],
               'rsvp-yes': ['h-entry', 'h-as-rsvp'],
               'rsvp-no': ['h-entry', 'h-as-rsvp'],
               'rsvp-maybe': ['h-entry', 'h-as-rsvp'],
               'invite': ['h-entry'],
               }
  obj_type = source.object_type(obj)
  types = types_map.get(obj_type, ['h-entry'])

  url = obj.get('url', '')
  content = obj.get('content', '')
  # TODO: extract snippet
  name = obj.get('displayName', obj.get('title'))
  summary = obj.get('summary')

  author = obj.get('author', obj.get('actor', {}))
  author = object_to_json(author, trim_nulls=False)
  if author:
    author['type'] = ['h-card']

  location = object_to_json(obj.get('location', {}), trim_nulls=False)
  if location:
    location['type'] = ['h-card', 'p-location']

  in_reply_tos = obj.get('inReplyTo', []) + ctx.get('inReplyTo', [])
  if 'h-as-rsvp' in types and 'object' in obj:
    in_reply_tos.append(obj['object'])
  # TODO: more tags. most will be p-category?
  ret = {
    'type': types,
    'properties': {
      'uid': [obj.get('id', '')],
      'name': [name],
      'summary': [summary],
      'url': [url],
      'photo': [obj.get('image', {}).get('url', '')],
      'video': [obj.get('stream', {}).get('url')],
      'published': [obj.get('published', '')],
      'updated':  [obj.get('updated', '')],
      'content': [{
          'value': xml.sax.saxutils.unescape(content),
          'html': render_content(obj, include_location=False),
          }],
      'in-reply-to': util.trim_nulls([o.get('url') for o in in_reply_tos]),
      'author': [author],
      'location': [location],
      'comment': [object_to_json(c, trim_nulls=False)
                  for c in obj.get('replies', {}).get('items', [])],
      }
    }

  # rsvp
  if 'h-as-rsvp' in types:
    ret['properties']['rsvp'] = [obj_type[len('rsvp-'):]]
  elif obj_type == 'invite':
    invitee = object_to_json(obj.get('object'), trim_nulls=False)
    invitee['type'].append('p-invitee')
    ret['properties']['invitee'] = [invitee]
  # likes and reposts
  # http://indiewebcamp.com/like#Counterproposal
  for type, prop in ('like', 'like'), ('share', 'repost'):
    if obj_type == type:
      # The ActivityStreams spec says the object property should always be a
      # single object, but it's useful to let it be a list, e.g. when a like has
      # multiple targets, e.g. a like of a post with original post URLs in it,
      # which brid.gy does.
      objs = obj.get('object', [])
      if not isinstance(objs, list):
        objs = [objs]
      ret['properties'][prop] = ret['properties'][prop + '-of'] = \
          [o.get('url') for o in objs]
    else:
      ret['properties'][prop] = [object_to_json(t, trim_nulls=False)
                                 for t in obj.get('tags', [])
                                 if source.object_type(t) == type]

  if trim_nulls:
    ret = util.trim_nulls(ret)
  return ret


def json_to_object(mf2):
  """Converts microformats2 JSON to an ActivityStreams object.

  Args:
    mf2: dict, decoded JSON microformats2 object

  Returns: dict, ActivityStreams object
  """
  if not mf2 or not isinstance(mf2, dict):
    return {}

  props = mf2.get('properties', {})
  prop = first_props(props)
  rsvp = prop.get('rsvp')
  rsvp_verb = 'rsvp-%s' % rsvp if rsvp else None
  author = json_to_object(prop.get('author'))

  # maps mf2 type to ActivityStreams objectType and optional verb. ordered by
  # priority.
  types = mf2.get('type', [])
  types_map = [
    ('h-as-rsvp', 'activity', rsvp_verb),
    ('h-as-repost', 'activity', 'share'),
    ('h-as-like', 'activity', 'like'),
    ('p-comment', 'comment', None),
    ('h-as-reply', 'comment', None),
    ('p-location', 'place', None),
    ('h-card', 'person', None),
    ]

  # fallback if none of the above mf2 types are found. maps property (if it
  # exists) to objectType and verb. ordered by priority.
  prop_types_map = [
    ('rsvp', 'activity', rsvp_verb),
    ('invitee', 'activity', 'invite'),
    ('repost', 'activity', 'share'),
    ('repost-of', 'activity', 'share'),
    ('like', 'activity', 'like'),
    ('like-of', 'activity', 'like'),
    ('in-reply-to', 'comment', None),
    ]

  for mf2_type, as_type, as_verb in types_map:
    if mf2_type in types:
      break  # found
  else:
    for p, as_type, as_verb in prop_types_map:
      if p in props:
        break
    else:
      # default
      as_type = 'note' if 'h-as-note' in types else 'article'
      as_verb = None

  photos = [url for url in get_string_urls(props.get('photo', []))
            # filter out relative and invalid URLs (mf2py gives absolute urls)
            if urlparse.urlparse(url).netloc]

  obj = {
    'id': prop.get('uid'),
    'objectType': as_type,
    'verb': as_verb,
    'published': prop.get('published', ''),
    'updated': prop.get('updated', ''),
    'displayName': get_text(prop.get('name')),
    'summary': get_text(prop.get('summary')),
    'content': get_html(prop.get('content')),
    'url': prop.get('url'),
    'image': {'url': photos[0] if photos else None},
    'location': json_to_object(prop.get('location')),
    'replies': {'items': [json_to_object(c) for c in props.get('comment', [])]},
    }

  if as_type == 'activity':
    urls = set(itertools.chain.from_iterable(get_string_urls(props.get(field, []))
        for field in ('like', 'like-of', 'repost', 'repost-of', 'in-reply-to')))
    objects = [{'url': url} for url in urls]
    objects += [json_to_object(i) for i in props.get('invitee', [])]
    obj.update({
        'object': objects[0] if len(objects) == 1 else objects,
        'actor': author,
        })
  else:
    obj.update({
        'inReplyTo': [{'url': url} for url in get_string_urls(props.get('in-reply-to', []))],
        'author': author,
        })

  return util.trim_nulls(obj)


def object_to_html(obj, ctx={}):
  """Converts an ActivityStreams object to microformats2 HTML.

  Features:
  - linkifies embedded tags and adds links for other tags
  - linkifies embedded URLs
  - adds links, summaries, and thumbnails for attachments and checkins
  - adds a "via SOURCE" postscript

  Args:
    obj: dict, a decoded JSON ActivityStreams object
    ctx: dict, a decoded JSON ActivityStreams context

  Returns: string, the content field in obj with the tags in the tags field
    converted to links if they have startIndex and length, otherwise added to
    the end.
  """
  return json_to_html(object_to_json(obj, ctx=ctx, trim_nulls=False))


def json_to_html(obj):
  """Converts a microformats2 JSON object to microformats2 HTML.

  See object_to_html for details.

  Args:
    obj: dict, a decoded microformats2 JSON object

  Returns: string HTML
  """
  if not obj:
    return ''

  # TODO: handle when h-card isn't first
  if obj['type'][0] == 'h-card':
    return hcard_to_html(obj)

  props = obj['properties']
  in_reply_tos = '\n'.join(IN_REPLY_TO.substitute(url=url)
                           for url in get_string_urls(props.get('in-reply-to', [])))

  prop = first_props(props)
  prop.setdefault('uid', '')
  author = prop.get('author')
  if author:
    author['type'].append('p-author')

  content = prop.get('content', {})
  content_html = content.get('html', '') or content.get('value', '')
  content_classes = ['e-content']
  if not prop.get('name'):
    content_classes.append('p-name')

  summary = ('<div class="p-summary">%s</div>' % prop.get('summary')
             if prop.get('summary') else '')

  # if this post is itself a like or repost, link to its target(s).
  likes_and_reposts = []
  for verb in 'like', 'repost':
    if ('h-as-%s' % verb) in obj['type']:
      if not content_html:
        content_html = '%ss this.\n' % verb
      likes_and_reposts += ['<a class="u-%s u-%s-of" href="%s"></a>' %
                            (verb, verb, url) for url in props.get(verb)]

  photo = '\n'.join(img(url, 'u-photo', 'attachment')
                    for url in props.get('photo', []) if url)
  video = '\n'.join(vid(url, None, 'u-video')
                    for url in props.get('video', []) if url)

  # comments
  # http://indiewebcamp.com/comment-presentation#How_to_markup
  # http://indiewebcamp.com/h-cite
  comments_html = '\n'.join(json_to_html(c) for c in props.get('comment', []))

  # embedded likes and reposts of this post
  # http://indiewebcamp.com/like, http://indiewebcamp.com/repost
  for verb in 'like', 'repost':
    vals = props.get(verb, [])
    if vals and isinstance(vals[0], dict):
      likes_and_reposts += [json_to_html(v) for v in vals]

  return HENTRY.substitute(
    prop,
    published=maybe_datetime(prop.get('published'), 'dt-published'),
    updated=maybe_datetime(prop.get('updated'), 'dt-updated'),
    types=' '.join(obj['type']),
    author=hcard_to_html(author),
    location=hcard_to_html(prop.get('location')),
    photo=photo,
    video=video,
    in_reply_tos=in_reply_tos,
    invitees='\n'.join([hcard_to_html(i) for i in props.get('invitee', [])]),
    content=content_html,
    content_classes=' '.join(content_classes),
    comments=comments_html,
    likes_and_reposts='\n'.join(likes_and_reposts),
    linked_name=maybe_linked_name(props),
    summary=summary)


def hcard_to_html(hcard):
  """Renders an h-card as HTML.

  Args:
    hcard: dict, decoded JSON h-card

  Returns: string, rendered HTML
  """
  if not hcard:
    return ''

  # extract first value from multiply valued properties
  prop = first_props(hcard['properties'])
  prop.setdefault('uid', '')
  photo = prop.get('photo')
  return HCARD.substitute(
    prop,
    types=' '.join(hcard['type']),
    photo=img(photo, 'u-photo', prop.get('name', '')) if photo else '',
    linked_name=maybe_linked_name(hcard['properties']))


def render_content(obj, include_location=True):
  """Renders the content of an ActivityStreams object.

  Includes tags, mentions, and attachments.

  Args:
    obj: decoded JSON ActivityStreams object
    include_location: whether to render location, if provided

  Returns: string, rendered HTML
  """
  content = obj.get('content', '')

  # extract tags. preserve order but de-dupe, ie don't include a tag more than
  # once.
  seen_ids = set()
  mentions = []
  tags = {}  # maps string objectType to list of tag objects
  for t in obj.get('tags', []):
    id = t.get('id')
    if id and id in seen_ids:
      continue
    seen_ids.add(id)

    if 'startIndex' in t and 'length' in t:
      mentions.append(t)
    else:
      tags.setdefault(source.object_type(t), []).append(t)

  # linkify embedded mention tags inside content.
  if mentions:
    mentions.sort(key=lambda t: t['startIndex'])
    last_end = 0
    orig = content
    content = ''
    for tag in mentions:
      start = tag['startIndex']
      end = start + tag['length']
      content += orig[last_end:start]
      content += '<a href="%s">%s</a>' % (
        tag['url'], orig[start:end])
      last_end = end

    content += orig[last_end:]

  # convert newlines to <br>s
  # do this *after* linkifying tags so we don't have to shuffle indices over
  content = content.replace('\n', '<br />\n')

  # linkify embedded links. ignore the "mention" tags that we added ourselves.
  # TODO: fix the bug in test_linkify_broken() in webutil/util_test.py, then
  # uncomment this.
  # if content:
  #   content = util.linkify(content)

  # attachments, e.g. links (aka articles)
  # TODO: use oEmbed? http://oembed.com/ , http://code.google.com/p/python-oembed/
  for tag in obj.get('attachments', []) + tags.pop('article', []):
    name = tag.get('displayName', '')
    open_a_tag = False
    if tag.get('objectType') == 'video':
      video = tag.get('stream') or obj.get('stream')
      if video:
        if isinstance(video, list):
          video = video[0]
        poster = tag.get('image', {})
        if poster and isinstance(poster, list):
          poster = poster[0]
        if video.get('url'):
          content += '\n<p>%s</p>' % vid(
            video['url'], poster.get('url'), 'thumbnail')
    else:
      content += '\n<p>'
      url = tag.get('url') or obj.get('url')
      if url:
        content += '\n<a class="link" href="%s">' % url
        open_a_tag = True
      image = tag.get('image') or obj.get('image')
      if image:
        if isinstance(image, list):
          image = image[0]
        if image.get('url'):
          content += '\n' + img(image['url'], 'thumbnail', name)
    if name:
      content += '\n<span class="name">%s</span>' % name
    if open_a_tag:
      content += '\n</a>'
    summary = tag.get('summary')
    if summary and summary != name:
      content += '\n<span class="summary">%s</span>' % summary
    content += '\n</p>'

  # location
  loc = obj.get('location')
  if include_location and loc:
    loc_mf2 = object_to_json(loc)
    loc_mf2['type'] = ['h-card', 'p-location']
    content += '\n' + hcard_to_html(loc_mf2)

  # other tags, except likes and (re)shares. they're rendered manually in
  # json_to_html().
  tags.pop('like', [])
  tags.pop('share', [])
  content += tags_to_html(tags.pop('hashtag', []), 'p-category')
  content += tags_to_html(tags.pop('mention', []), 'u-mention')
  content += tags_to_html(sum(tags.values(), []), 'tag')

  return content


def first_props(props):
  """Converts a multiply-valued dict to singly valued.

  Args:
    props: dict of properties, where each value is a sequence

  Returns: corresponding dict with just the first value of each sequence, or ''
    if the sequence is empty
  """
  if not props:
    return {}

  prop = {}
  for k, v in props.items():
    if not v:
      prop[k] = ''
    elif isinstance(v, (tuple, list)):
      prop[k] = v[0]
    else:
      prop[k] = v

  return prop


def tags_to_html(tags, classname):
  """Returns an HTML string with links to the given tag objects.

  Args:
    tags: decoded JSON ActivityStreams objects.
    classname: class for span to enclose tags in
  """
  return ''.join('\n<a class="%s" href="%s">%s</a>' % (classname, t['url'],
                                                       t.get('displayName', ''))
                 for t in tags if t.get('url'))


def author_display_name(hcard):
  """Returns a human-readable string display name for an h-card object."""
  name = None
  if hcard:
    prop = first_props(hcard.get('properties'))
    name = prop.get('name') or prop.get('uid')
  return name if name else 'Unknown'


def maybe_linked_name(props):
  """Returns the HTML for a p-name with an optional u-url inside.

  Args:
    props: *multiply-valued* properties dict

  Returns: string HTML
  """
  prop = first_props(props)
  name = prop.get('name') or ''
  url = prop.get('url')
  html = maybe_linked(name, url, classname='u-url')
  if name:
    html = '<div class="p-name">%s</div>' % html

  extra_urls = props.get('url', [])[1:]
  if extra_urls:
    html += '\n' + '\n'.join(maybe_linked('', url, classname='u-url')
                             for url in extra_urls)

  return html


def img(src, cls, alt):
  """Returns an <img> string with the given src, class, and alt.

  Args:
    src: string, url of the image
    cls: string, css class applied to the img tag

  Returns: string
  """
  return '<img class="%s" src="%s" alt=%s />' % (
      cls, src, xml.sax.saxutils.quoteattr(alt))


def vid(src, poster, cls):
  """Returns an <video> string with the given src and class

  Args:
    src: string, url of the video
    poster: sring, optional. url of the poster or preview image
    cls: string, css class applied to the video tag

  Returns: string
  """
  html = '<video class="%s" src="%s"' % (cls, src)
  if poster:
    html += ' poster="%s"' % poster
  html += ' controls>'

  html += 'Your browser does not support the video tag. '
  html += '<a href="%s">Click here to view directly' % src
  if poster:
    html += '<img src="%s"/>' % poster
  html += '</a></video>'
  return html


def maybe_linked(text, url, classname=None):
  """Wraps text in an <a href=...> iff a non-empty url is provided.

  Args:
    text: string
    url: string or None
    classname: string, optional class attribute

  Returns: string
  """
  classname = 'class="%s"' % classname if classname else ''
  return ('<a %s href="%s">%s</a>' % (classname, url, text)) if url else text


def maybe_datetime(str, classname):
  """Returns a <time datetime=...> elem if str is non-empty.

  Args:
    str: string RFC339 datetime or None
    classname: string class name

  Returns: string
  """
  if str:
    return '<time class="%s" datetime="%s">%s</time>' % (classname, str, str)
  else:
    return ''
