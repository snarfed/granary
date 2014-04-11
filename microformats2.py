"""Convert ActivityStreams to microformats2 HTML and JSON.

Microformats2 specs: http://microformats.org/wiki/microformats2
"""

import itertools
import logging
import string

from oauth_dropins.webutil import util

# TODO: comments
HENTRY = string.Template("""\
<article class="$types">
  <span class="u-uid">$uid</span>
  $linked_name
  $published
  $updated
$author
  <div class="e-content">
  $invitees
  $content
  </div>
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
    <span class="u-uid">$uid</span>
  </div>
""")
IN_REPLY_TO = string.Template('  <a class="u-in-reply-to" href="$url"></a>')
PHOTO = string.Template('<img class="u-photo" src="$url" alt="$alt" />')


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


def object_to_json(obj, trim_nulls=True):
  """Converts an ActivityStreams object to microformats2 JSON.

  Args:
    obj: dict, a decoded JSON ActivityStreams object
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
  obj_type = object_type(obj)
  types = types_map.get(obj_type, ['h-entry'])

  url = obj.get('url', '')
  content = obj.get('content', '')
  # TODO: extract snippet
  name = obj.get('displayName', obj.get('title', content))

  author = obj.get('author', obj.get('actor', {}))
  author = object_to_json(author, trim_nulls=False)
  if author:
    author['type'] = ['h-card']

  location = object_to_json(obj.get('location', {}), trim_nulls=False)
  if location:
    location['type'] = ['h-card', 'p-location']

  in_reply_tos = obj.get('inReplyTo', [])
  if 'h-as-rsvp' in types and 'object' in obj:
    in_reply_tos.append(obj['object'])
  # TODO: more tags. most will be p-category?
  ret = {
    'type': types,
    'properties': {
      'uid': [obj.get('id', '')],
      'name': [name],
      'url': [url],
      'photo': [obj.get('image', {}).get('url', '')],
      'published': [obj.get('published', '')],
      'updated':  [obj.get('updated', '')],
      'content': [{
          'value': content,
          'html': render_content(obj),
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
                                 if object_type(t) == type]

  if trim_nulls:
    ret = util.trim_nulls(ret)
  return ret


def json_to_object(mf2):
  """Converts microformats2 JSON to an ActivityStreams object.

  Args:
    mf2: dict, decoded JSON microformats2 object

  Returns: dict, ActivityStreams object
  """
  if not mf2:
    return {}

  props = mf2.get('properties', {})
  prop = first_props(props)
  content = prop.get('content', {})
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

  obj = {
    'id': prop.get('uid'),
    'objectType': as_type,
    'verb': as_verb,
    'published': prop.get('published', ''),
    'updated': prop.get('updated', ''),
    'displayName': prop.get('name'),
    'content': content.get('value') or content.get('html'),
    'url': prop.get('url'),
    'image': {'url': prop.get('photo')},
    'location': json_to_object(prop.get('location')),
    'replies': {'items': [json_to_object(c) for c in props.get('comment', [])]},
    # TODO
    # location
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


def object_to_html(obj):
  """Converts an ActivityStreams object to microformats2 HTML.

  Features:
  - linkifies embedded tags and adds links for other tags
  - linkifies embedded URLs
  - adds links, summaries, and thumbnails for attachments and checkins
  - adds a "via SOURCE" postscript

  TODO: convert newlines to <br> or <p>

  Args:
    obj: dict, a decoded JSON ActivityStreams object

  Returns: string, the content field in obj with the tags in the tags field
    converted to links if they have startIndex and length, otherwise added to
    the end.
  """
  return json_to_html(object_to_json(obj, trim_nulls=False))


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
                           for url in get_string_urls(props['in-reply-to']))

  prop = first_props(props)
  author = prop['author']
  if author:
    author['type'].append('p-author')

  content = prop.get('content', {})
  content_html = content.get('html') or content.get('value')

  # if this post is itself a like or repost, link to its target(s).
  likes_and_reposts = []
  for verb in 'like', 'repost':
    if ('h-as-%s' % verb) in obj['type']:
      if not content_html:
        content_html = '%ss this.\n' % verb
      likes_and_reposts += ['<a class="u-%s u-%s-of" href="%s"></a>' %
                            (verb, verb, url) for url in props.get(verb)]

  photo = '\n'.join(PHOTO.substitute(url=url, alt='attachment')
                    for url in props.get('photo', []) if url)

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
    location=hcard_to_html(prop['location']),
    photo=photo,
    in_reply_tos=in_reply_tos,
    invitees='\n'.join([hcard_to_html(i) for i in props.get('invitee', [])]),
    content=content_html,
    comments=comments_html,
    likes_and_reposts='\n'.join(likes_and_reposts),
    linked_name=maybe_linked_name(prop))


def hcard_to_html(hcard):
  """Renders an h-card as HTML.

  Args:
    hcard: dict, decoded JSON h-card

  Returns: string, rendered HTML
  """
  if not hcard:
    return ''

  # extract first value from multiply valued properties
  props = first_props(hcard['properties'])
  photo = (PHOTO.substitute(url=props['photo'], alt=props.get('name', '-'))
           if props.get('photo') else '')
  return HCARD.substitute(props,
                          types=' '.join(hcard['type']),
                          photo=photo,
                          linked_name=maybe_linked_name(props))


def render_content(obj):
  """Renders the content of an ActivityStreams object.

  Includes tags, mentions, and attachments.

  Args:
    obj: decoded JSON ActivityStreams object

  Returns: string, rendered HTML
  """
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
      tags.setdefault(object_type(t), []).append(t)

  # linkify embedded mention tags inside content.
  content = obj.get('content', '')
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

  # linkify embedded links. ignore the "mention" tags that we added ourselves.
  # TODO: fix the bug in test_linkify_broken() in webutil/util_test.py, then
  # uncomment this.
  # if content:
  #   content = util.linkify(content)

  # attachments, e.g. links (aka articles)
  # TODO: use oEmbed? http://oembed.com/ , http://code.google.com/p/python-oembed/
  # TODO: non-article attachments
  for link in obj.get('attachments', []) + tags.pop('article', []):
    if object_type(link) == 'article':
      url = link.get('url')
      name = link.get('displayName', url)
      image = link.get('image', {}).get('url')
      if not image:
        image = obj.get('image', {}).get('url', '')

      content += """\
<p><a class="link" alt="%s" href="%s">
<img class="link-thumbnail" src="%s" alt="%s" />
<span class="link-name">%s</span>
""" % (name, name, url, image, name)
      summary = link.get('summary')
      if summary:
        content += '<span class="link-summary">%s</span>\n' % summary
      content += '</p>'

  # other tags, except likes and (re)shares. they're rendered manually in
  # json_to_html().
  tags.pop('like', [])
  tags.pop('share', [])
  content += tags_to_html(tags.pop('hashtag', []), 'p-category')
  content += tags_to_html(sum(tags.values(), []), 'tag')

  return content


def object_type(obj):
  """Returns the object type, or the verb if it's an activity object.

  Details: http://activitystrea.ms/specs/json/1.0/#activity-object

  Args:
    obj: decoded JSON ActivityStreams object

  Returns: string, ActivityStreams object type
  """
  type = obj.get('objectType')
  return type if type != 'activity' else obj.get('verb')


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
  if tags:
    return ('\n<p class="%s">' % classname +
            ', '.join('<a href="%s">%s</a>' % (t.get('url'), t.get('displayName'))
                      for t in tags) +
            '</p>')
  else:
    return ''


def author_display_name(hcard):
  """Returns a human-readable string display name for an h-card object."""
  name = None
  if hcard:
    props = first_props(hcard.get('properties'))
    name = props.get('name', props.get('uid'))
  return name if name else 'Unknown'


def maybe_linked_name(props):
  """Returns the HTML for a p-name with an optional u-url inside.

  Args:
    props: singly-valued properties dict

  Returns: string HTML
  """
  name = props.get('name', '')
  url = props.get('url')
  html = maybe_linked(name, url, classname='u-url')
  if name:
    html = '<div class="p-name">%s</div>' % html
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
