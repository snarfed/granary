"""Convert ActivityStreams to microformats2 HTML and JSON.

Microformats2 specs: http://microformats.org/wiki/microformats2
"""

from webutil import util


def object_to_json(obj):
  """Converts an ActivityStreams object to microformats2 JSON.

  Args:
    obj: dict, a decoded JSON ActivityStreams object

  Returns: dict, decoded microformats2 JSON
  """
  types = {'note': 'h-entry'}

  return {
    'type': [types[obj['objectType']]],
    'properties': {
      'name': [obj.get('displayName')],
      'url': [obj.get('url')],
      'published': [obj.get('published')],
      'updated':  [obj.get('updated')],
      'content': [{
          'html': obj.get('content'),
          'value': obj.get('content'),
          }],
      },
    }


def object_to_html(obj, source_name=None):
  """Converts an ActivityStreams object to microformats2 HTML.

  Features:
  - linkifies embedded tags and adds links for other tags
  - linkifies embedded URLs
  - adds links, summaries, and thumbnails for attachments and checkins
  - adds a "via SOURCE" postscript

  TODO: convert newlines to <br> or <p>

  Args:
    obj: dict, a decoded JSON ActivityStreams object
    source_name: string, human-readable name of the source, e.g. 'Twitter'

  Returns: string, the content field in obj with the tags in the tags field
    converted to links if they have startIndex and length, otherwise added to
    the end.
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
      tags.setdefault(t['objectType'], []).append(t)

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
      content += '<a class="freedom-mention" href="%s">%s</a>' % (
        tag['url'], orig[start:end])
      last_end = end

    content += orig[last_end:]

  # linkify embedded links. ignore the "mention" tags that we added ourselves.
  if content:
    content = '<p>' + util.linkify(content) + '</p>\n'

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
<p><a class="freedom-link" alt="%s" href="%s">
<img class="freedom-link-thumbnail" src="%s" />
<span class="freedom-link-name">%s</span>
""" % (name, url, image, name)
      summary = link.get('summary')
      if summary:
        content += '<span class="freedom-link-summary">%s</span>\n' % summary
      content += '</p>\n'

  # checkin
  location = obj.get('location')
  if location and 'displayName' in location:
    place = location['displayName']
    url = location.get('url')
    if url:
      place = '<a href="%s">%s</a>' % (url, place)
    content += '<p class="freedom-checkin">at %s</p>\n' % place

  # other tags
  content += tags_to_html(tags.pop('hashtag', []), 'freedom-hashtags')
  content += tags_to_html(sum(tags.values(), []), 'freedom-tags')

  # photo

  # TODO: expose as option
  # Uploaded photos are scaled to this width in pixels. They're also linked to
  # the full size image.
  SCALED_IMG_WIDTH = 500

  # add image
  # TODO: multiple images (in attachments?)
  image_url = obj.get('image', {}).get('url')
  if image_url:
    content += """
<p><a class="shutter" href="%s">
  <img class="alignnone shadow" src="%s" width="%s" />
</a></p>
""" % (image_url, image_url, str(SCALED_IMG_WIDTH))

  # "via SOURCE"
  url = obj.get('url')
  if source_name or url:
    via = ('via %s' % source_name) if source_name else 'original'
    if url:
      via = '<a href="%s">%s</a>' % (url, via)
    content += '<p class="freedom-via">%s</p>' % via

  # TODO: for comments
  # # note that wordpress strips many html tags (e.g. br) and almost all
  # # attributes (e.g. class) from html tags in comment contents. so, convert
  # # some of those tags to other tags that wordpress accepts.
  # content = re.sub('<br */?>', '<p />', comment.content)

  # # since available tags are limited (see above), i use a fairly unique tag
  # # for the "via ..." link - cite - that site owners can use to style.
  # #
  # # example css on my site:
  # #
  # # .comment-content cite a {
  # #     font-size: small;
  # #     color: gray;
  # # }
  # content = '%s <cite><a href="%s">via %s</a></cite>' % (
  #   content, comment.source_post_url, comment.source.type_display_name())

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
