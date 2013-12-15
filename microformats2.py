"""Convert ActivityStreams to microformats2 HTML and JSON.

Microformats2 specs: http://microformats.org/wiki/microformats2
"""

import logging
import string

from webutil import util

# TODO: comments
HENTRY = string.Template("""\
<article class="$types">
  <span class="u-uid">$uid</span>
  $maybe_linked_name
  <time class="dt-published" datetime="$published">$published</time>
  <time class="dt-updated" datetime="$updated">$updated</time>
$author
  <div class="e-content">
  $content
  $photo
  </div>
$location
$in_reply_tos
$likes
$comments
</article>
""")
HCARD = string.Template("""\
  <div class="$types">
    $maybe_linked_name
    $photo
    <span class="u-uid">$uid</span>
  </div>
""")
IN_REPLY_TO = string.Template('  <a class="u-in-reply-to" href="$url" />')
PHOTO = string.Template('<img class="u-photo" src="$url" />')


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
               }
  obj_type = obj.get('objectType')
  types = types_map.get(obj_type, ['h-entry'])

  url = obj.get('url', '')
  content = obj.get('content', '')
  # TODO: extract snippet
  name = obj.get('displayName', obj.get('title', content))

  author = object_to_json(obj.get('author', {}), trim_nulls=False)
  if author:
    author['type'] = ['h-card']

  location = object_to_json(obj.get('location', {}), trim_nulls=False)
  if location:
    location['type'] = ['h-card', 'p-location']

  # TODO: do i need this for standalone (non-embedded) like rendering?
  # if obj_type == 'like':
  #   likes = [obj.get('url', '')]
  likes = [object_to_json(t) for t in obj.get('tags', [])
           if t.get('objectType') == 'like']
  for like in likes:
    like['properties']['like'] = [url]

  # TODO: convert tags to p-category
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
      'in-reply-to': util.trim_nulls([o.get('url') for o in
                                      obj.get('inReplyTo', [])]),
      'author': [author],
      'location': [location],
      'comment': [object_to_json(c) for c in obj.get('replies', {}).get('items', [])],
      'like': likes,
      }
    }
  if trim_nulls:
    ret = util.trim_nulls(ret)
  return ret


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
  if not obj:
    return ''

  jsn = object_to_json(obj, trim_nulls=False)
  # TODO: handle when h-card isn't first
  if jsn['type'][0] == 'h-card':
    return hcard_to_html(jsn)

  props = jsn['properties']
  in_reply_tos = '\n'.join(IN_REPLY_TO.substitute(url=url)
                           for url in props['in-reply-to'])

  # extract first value from multiply valued properties
  props = {k: v[0] if v else '' for k, v in props.items()}

  author = props['author']
  if author:
    author['type'].append('p-author')

  content_html = props.get('content', {}).get('html', '')

  # if this post is itself a like, link to the target of the like.
  if obj['objectType'] == 'like':
    logging.info('@ %s', props)
    url = props.get('url')
    like = props.get('like')
    content_html = ' '.join([
      '<a href="%s">likes</a>' % url if url else 'likes',
      '<a class="u-like" href="%s">this.</a>' % like if like else 'this.',
      content_html])

  # TODO: multiple images (in attachments?)
  photo = PHOTO.substitute(url=props['photo']) if props['photo'] else ''

  # comments
  # http://indiewebcamp.com/comment-presentation#How_to_markup
  # http://indiewebcamp.com/h-cite
  comments = obj.get('replies', {}).get('items', [])
  comments_html = '\n'.join(object_to_html(c) for c in comments)

  # embedded likes of this post
  # http://indiewebcamp.com/like
  likes_html = '\n'.join(object_to_html(tag) for tag in obj.get('tags', [])
                         if tag['objectType'] == 'like')

  return HENTRY.substitute(props,
                           types=' '.join(jsn['type']),
                           author=hcard_to_html(author),
                           location=hcard_to_html(props['location']),
                           photo=photo,
                           in_reply_tos=in_reply_tos,
                           content=content_html,
                           comments=comments_html,
                           likes=likes_html,
                           maybe_linked_name=maybe_linked_name(props))


def hcard_to_html(hcard):
  """Renders an h-card as HTML.

  Args:
    hcard: dict, decoded JSON h-card

  Returns: string, rendered HTML
  """
  if not hcard:
    return ''

  # extract first value from multiply valued properties
  props = {k: v[0] if v else '' for k, v in hcard['properties'].items()}
  photo = PHOTO.substitute(url=props['photo']) if props['photo'] else ''
  return HCARD.substitute(props,
                          types=' '.join(hcard['type']),
                          photo=photo,
                          maybe_linked_name=maybe_linked_name(props))


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
      tags.setdefault(t['objectType'], []).append(t)

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
      content += '<a class="mention" href="%s">%s</a>' % (
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
    if link.get('objectType') == 'article':
      url = link.get('url')
      name = link.get('displayName', url)
      image = link.get('image', {}).get('url')
      if not image:
        image = obj.get('image', {}).get('url', '')

      content += """\
<p><a class="link" alt="%s" href="%s">
<img class="link-thumbnail" src="%s" />
<span class="link-name">%s</span>
""" % (name, url, image, name)
      summary = link.get('summary')
      if summary:
        content += '<span class="link-summary">%s</span>\n' % summary
      content += '</p>'

  # other tags, except likes. they're rendered manually with object_to_html().
  tags.pop('like', [])
  content += tags_to_html(tags.pop('hashtag', []), 'p-category')
  content += tags_to_html(sum(tags.values(), []), 'tag')

  return content


def tags_to_html(tags, css_class):
  """Returns an HTML string with links to the given tag objects.

  Args:
    tags: decoded JSON ActivityStreams objects.
    css_class: CSS class for span to enclose tags in
  """
  if tags:
    return ('\n<p class="%s">' % css_class +
            ', '.join('<a href="%s">%s</a>' % (t.get('url'), t.get('displayName'))
                      for t in tags) +
            '</p>')
  else:
    return ''


def maybe_linked_name(props):
  """Returns the HTML for a p-name with an optional u-url inside.

  Args:
    props: singly-valued properties dict

  Returns: string HTML
  """
  name = props.get('name', '')
  url = props.get('url')
  html = name
  if url:
    html = '<a class="u-url" href="%s">%s</a>' % (url, html)
  if name:
    html = '<div class="p-name">%s</div>' % html
  return html
