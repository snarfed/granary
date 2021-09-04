"""Convert between ActivityStreams and RSS 2.0.

RSS 2.0 spec: http://www.rssboard.org/rss-specification

Apple iTunes Podcasts feed requirements:
https://help.apple.com/itc/podcasts_connect/#/itc1723472cb

Notably:
* Valid RSS 2.0.
* Each podcast item requires <guid>.
* Images should be JPEG or PNG, 1400x1400 to 3000x3000.
* HTTP server that hosts assets and files should support range requests.
"""
from datetime import datetime, time
import logging
import mimetypes

from feedgen.feed import FeedGenerator
import mf2util
from oauth_dropins.webutil import util

from . import microformats2

# allowed ActivityStreams objectTypes for media enclosures
ENCLOSURE_TYPES = {'audio', 'video'}


def from_activities(activities, actor=None, title=None, feed_url=None,
                    home_page_url=None, hfeed=None):
  """Converts ActivityStreams activities to an RSS 2.0 feed.

  Args:
    activities: sequence of ActivityStreams activity dicts
    actor: ActivityStreams actor dict, the author of the feed
    title: string, the feed title
    feed_url: string, the URL for this RSS feed
    home_page_url: string, the home page URL
    hfeed: dict, parsed mf2 h-feed, if available

  Returns:
    unicode string with RSS 2.0 XML
  """
  try:
    iter(activities)
  except TypeError:
    raise TypeError('activities must be iterable')

  if isinstance(activities, (dict, str)):
    raise TypeError('activities may not be a dict or string')

  fg = FeedGenerator()
  fg.id(feed_url)
  assert feed_url
  fg.link(href=feed_url, rel='self')
  if home_page_url:
    fg.link(href=home_page_url, rel='alternate')
  # TODO: parse language from lang attribute:
  # https://github.com/microformats/mf2py/issues/150
  fg.language('en')
  fg.generator('granary', uri='https://granary.io/')

  hfeed = hfeed or {}
  actor = actor or {}
  image = (util.get_url(hfeed.get('properties', {}), 'photo') or
           util.get_url(actor, 'image'))
  if image:
    fg.image(image)

  props = hfeed.get('properties') or {}
  content = microformats2.get_text(util.get_first(props, 'content', ''))
  summary = util.get_first(props, 'summary', '')
  desc = content or summary or '-'
  fg.description(desc)  # required
  fg.title(title or util.ellipsize(desc))  # required

  latest = None
  feed_has_enclosure = False
  for activity in activities:
    obj = activity.get('object') or activity
    if obj.get('objectType') == 'person':
      continue

    item = fg.add_entry()
    url = obj.get('url')
    id = obj.get('id') or url
    item.id(id)
    item.link(href=url)
    item.guid(url, permalink=True)

    # title (required)
    title = (obj.get('title') or obj.get('displayName') or
             util.ellipsize(obj.get('content', '-')))
    # strip HTML tags
    title = util.parse_html(title).get_text('').strip()
    item.title(title)

    content = microformats2.render_content(
      obj, include_location=True, render_attachments=True, render_image=True)
    if not content:
      content = obj.get('summary')
    if content:
      item.content(content, type='CDATA')

    categories = [
      {'term': t['displayName']} for t in obj.get('tags', [])
      if t.get('displayName') and
      t.get('verb') not in ('like', 'react', 'share') and
      t.get('objectType') not in ('article', 'person', 'mention')]
    item.category(categories)

    author = obj.get('author', {})
    author = {
      'name': author.get('displayName') or author.get('username'),
      'uri': author.get('url'),
      'email': author.get('email') or '-',
    }
    item.author(author)

    published = obj.get('published') or obj.get('updated')
    if published and isinstance(published, str):
      try:
        dt = mf2util.parse_datetime(published)
        if not isinstance(dt, datetime):
          dt = datetime.combine(dt, time.min)
        if not dt.tzinfo:
          dt = dt.replace(tzinfo=util.UTC)
        item.published(dt)
        if not latest or dt > latest:
          latest = dt
      except ValueError:  # bad datetime string
        pass

    item_has_enclosure = False
    for att in obj.get('attachments', []):
      stream = util.get_first(att, 'stream') or att
      if not stream:
        continue

      url = stream.get('url') or ''
      mime = mimetypes.guess_type(url)[0] or ''
      if (att.get('objectType') in ENCLOSURE_TYPES or
          mime and mime.split('/')[0] in ENCLOSURE_TYPES):
        if item_has_enclosure:
          logging.info('Warning: item %s already has an RSS enclosure, skipping additional enclosure %s',
                       id, url)
          continue

        item_has_enclosure = feed_has_enclosure = True
        item.enclosure(url=url, type=mime, length=str(stream.get('size', '')))
        item.load_extension('podcast')
        duration = stream.get('duration')
        if duration:
          item.podcast.itunes_duration(duration)

  if feed_has_enclosure:
    fg.load_extension('podcast')
    fg.podcast.itunes_author(actor.get('displayName') or actor.get('username'))
    if summary:
      fg.podcast.itunes_summary(summary)
    fg.podcast.itunes_explicit('no')
    fg.podcast.itunes_block(False)
    name = author.get('name')
    if name:
      fg.podcast.itunes_author(name)
    if image:
      fg.podcast.itunes_image(image)
    fg.podcast.itunes_category(categories)

  if latest:
    fg.lastBuildDate(latest)

  return fg.rss_str(pretty=True).decode('utf-8')
