"""Convert between ActivityStreams and RSS 2.0.

RSS 2.0 spec: http://www.rssboard.org/rss-specification
"""
from __future__ import absolute_import, unicode_literals
from builtins import str
from past.builtins import basestring

import mimetypes

from feedgen.feed import FeedGenerator
import mf2util
from oauth_dropins.webutil import util

from . import microformats2

# allowed ActivityStreams objectTypes for media enclosures
ENCLOSURE_TYPES = {'audio', 'video'}


def from_activities(activities, actor=None, title=None, description=None,
                    feed_url=None, home_page_url=None, image_url=None):
  """Converts ActivityStreams activities to an RSS 2.0 feed.

  Args:
    activities: sequence of ActivityStreams activity dicts
    actor: ActivityStreams actor dict, the author of the feed
    title: string, the feed title
    description, the feed description
    home_page_url: string, the home page URL
    # feed_url: the URL of this RSS feed, if any
    image_url: the URL of an image representing this feed

  Returns:
    unicode string with RSS 2.0 XML
  """
  try:
    iter(activities)
  except TypeError:
    raise TypeError('activities must be iterable')

  if isinstance(activities, (dict, basestring)):
    raise TypeError('activities may not be a dict or string')

  fg = FeedGenerator()
  fg.id(feed_url)
  fg.link(href=feed_url, rel='self')
  fg.link(href=home_page_url, rel='alternate')
  fg.title(title)
  fg.description(description)
  fg.generator('granary', uri='https://granary.io/')
  if image_url:
    fg.image(image_url)

  latest = None
  for activity in activities:
    obj = activity.get('object') or activity
    if obj.get('objectType') == 'person':
      continue

    item = fg.add_entry()
    url = obj.get('url')
    item.id(obj.get('id') or url)
    item.link(href=url)
    item.guid(url, permalink=True)

    item.title(obj.get('title') or obj.get('displayName'))
    content = microformats2.render_content(
      obj, include_location=True, render_attachments=False) or obj.get('summary')
    if content:
      item.content(content, type='CDATA')

    item.category([{'term': t.displayName} for t in obj.get('tags', [])
                  if t.displayName and t.verb not in ('like', 'react', 'share')])

    author = obj.get('author', {})
    item.author({
      'name': author.get('displayName') or author.get('username'),
      'uri': author.get('url'),
    })

    for prop in 'published', 'updated':
      val = obj.get(prop)
      if val:
        dt = util.parse_iso8601(val)
        getattr(item, prop)(dt)
        if not latest or dt > latest:
          latest = dt

    enclosures = False
    for att in obj.get('attachments', []):
      stream = util.get_first(att, 'stream') or att
      if not stream:
        continue

      url = stream.get('url')
      mime = mimetypes.guess_type(url)[0] if url else None
      if (att.get('objectType') in ENCLOSURE_TYPES or
          mime and mime.split('/')[0] in ENCLOSURE_TYPES):
        enclosures = True
        item.enclosure(url=url, type=mime) # TODO: length (bytes)

        item.load_extension('podcast')
        duration = stream.get('duration')
        if duration:
          item.podcast.itunes_duration(duration)

  if enclosures:
    fg.load_extension('podcast')
    if actor:
      fg.podcast.itunes_author(actor.get('displayName') or actor.get('username'))
    fg.podcast.itunes_image(image_url)
    if description:
      fg.podcast.itunes_subtitle(description)
    fg.podcast.itunes_explicit('no')
    fg.podcast.itunes_block(False)

  if latest:
    fg.lastBuildDate(dt)

  return fg.rss_str(pretty=True)
