"""Convert ActivityStreams to microformats2 HTML and JSON.

Microformats2 specs: http://microformats.org/wiki/microformats2
"""

import string

from webutil import util

# TODO: comments
HENTRY = string.Template("""\
<article class="h-entry $h_as">
  <span class="u-uid">$uid</span>
  <a class="u-url u-name" href="$url">$name</a>
  <time class="dt-published" datetime="$published">$published</time>
  <time class="dt-updated" datetime="$updated">$updated</time>

  <div class="h-card">
    <a class="u-url" href="$author_url">
      <img src="$author_image" />
      <span class="p-name">$author_name</span>
    </a>
    <link class="u-uid" href="$author_uid" />
  </div>

  <div class="e-content">
  $photo
$content
  </div>
$location
$in_reply_to
</article>
""")
LOCATION = string.Template("""\
  <div class="h-card p-location">
    <a class="u-url u-name" href="$url">$name</a>
    <span class="u-uid">$uid</span>
  </div>
""")
IN_REPLY_TO = string.Template('<a class="u-in-reply-to" href="$url">')
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

  types = {'comment': 'h-entry', 'note': 'h-entry',
           'person': 'h-card', 'place': 'h-card'}
  h_as = set(('article', 'note', 'collection', 'update'))

  obj_type = obj.get('objectType')
  type = [types.get(obj_type)]
  if obj_type in h_as:
    type.append('h-as-' + obj_type)

  name = obj.get('displayName', obj.get('title', ''))

  author = dict(obj.get('author', {}))
  if author and 'objectType' not in author:
    author['objectType'] = 'person'

  location = dict(obj.get('location', {}))
  if location and 'objectType' not in location:
    location['objectType'] = 'place'

  content = obj.get('content', '')

  ret = {
    'type': type,
    'properties': {
      'uid': [obj.get('id', '')],
      'name': [name],
      'url': [obj.get('url', '')],
      'photo': [obj.get('image', {}).get('url', '')],
      'published': [obj.get('published', '')],
      'updated':  [obj.get('updated', '')],
      'content': [{
          'value': content,
          'html': render_content(obj),
          }],
      'in-reply-to': [r.get('url', '') for r in obj.get('inReplyTo', [])],
      'author': [object_to_json(author)],
      'location': [object_to_json(location)],
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
  props = object_to_json(object, trim_nulls=False)['properties']
  # extract first values
  props = {k: (v[0] if v else '') for k, v in props.items()}

  # TODO: multiple images (in attachments?)
  if props['photo']:
    props['photo'] = PHOTO.substitute(url=props['photo'])

  if props['location']:
    props['location'] = LOCATION.substitute(props['location'])

  if props['in-reply-to']:
    props['in-reply-to'] = IN_REPLY_TO.substitute(url=props['in-reply-to'])

  props['content'] = props['content']['html']

  return HENTRY.substitute(props)


def render_content(obj):
  """Renders the content of an ActivityStreams object.

  Includes tags, mentions, and attachments.

  Args:
    tags: decoded JSON ActivityStreams objects.

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
  if content:
    content = util.linkify(content)

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
      content += '</p>\n'

  # other tags
  content += tags_to_html(tags.pop('hashtag', []), 'freedom-hashtags')
  content += tags_to_html(sum(tags.values(), []), 'freedom-tags')

  return content


def tags_to_html(tags, css_class):
  """Returns an HTML string with links to the given tag objects.

  Args:
    tags: decoded JSON ActivityStreams objects.
    css_class: CSS class for span to enclose tags in
  """
  if tags:
    return ('<p class="%s">' % css_class +
            ', '.join('<a href="%s">%s</a>' % (t.get('url'), t.get('displayName'))
                      for t in tags) +
            '</p>\n')
  else:
    return ''
