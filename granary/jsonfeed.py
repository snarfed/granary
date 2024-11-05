"""Convert between ActivityStreams and JSON Feed.

JSON Feed spec: https://jsonfeed.org/version/1.1
"""
import mimetypes

import mf2util
from oauth_dropins.webutil import util

from . import as1, microformats2
from .source import Source

# allowed ActivityStreams objectTypes for attachments
ATTACHMENT_TYPES = {'image', 'audio', 'video'}


def from_as1(activities, actor=None, title=None, feed_url=None, home_page_url=None):
  """Converts ActivityStreams activities to a JSON feed.

  Args:
    activities (sequence of dict): ActivityStreams activities
    actor (dict): ActivityStreams actor, the author of the feed
    title (str): the feed title
    home_page_url (str): the home page URL
    feed_url (str): the URL of the JSON Feed, if any. Included in the
      ``feed_url`` field.

  Returns:
    dict: JSON Feed data
  """
  try:
    iter(activities)
  except TypeError:
    raise TypeError('activities must be iterable')

  if isinstance(activities, (dict, str)):
    raise TypeError('activities may not be a dict or str')

  def image_url(obj):
    return util.get_first(obj, 'image', {}).get('url')

  def actor_name(obj):
    return obj.get('displayName') or obj.get('username')

  if not actor:
    actor = {}

  items = []
  for activity in activities:
    obj = as1.get_object(activity) or activity
    if obj.get('objectType') == 'person':
      continue
    author = as1.get_object(obj, 'author')
    content = microformats2.render_content(
      obj, include_location=True, render_attachments=True,
      # Readers often obey CSS white-space: pre strictly and don't even line wrap,
      # so don't use it. https://github.com/snarfed/granary/issues/456
      white_space_pre=False)
    obj_title = obj.get('title') or obj.get('displayName')
    item = {
      'id': obj.get('id') or obj.get('url'),
      'url': obj.get('url'),
      'image': image_url(obj),
      'title': obj_title if mf2util.is_name_a_title(obj_title, content) else None,
      'summary': obj.get('summary'),
      'content_html': content,
      'date_published': obj.get('published'),
      'date_modified': obj.get('updated'),
      'authors': [{
        'name': actor_name(author),
        'url': author.get('url'),
        'avatar': image_url(author),
      }],
      'attachments': [],
    }

    for att in obj.get('attachments', []):
      url = util.get_url(att, 'stream') or util.get_url(att, 'image')
      mime = mimetypes.guess_type(url)[0] if url else None
      if (att.get('objectType') in ATTACHMENT_TYPES or
          mime and mime.split('/')[0] in ATTACHMENT_TYPES):
        item['attachments'].append({
          'url': url or '',
          'mime_type': mime,
          'title': att.get('title'),
        })

    if not item['content_html']:
      item['content_text'] = ''
    items.append(item)

  return util.trim_nulls({
    'version': 'https://jsonfeed.org/version/1.1',
    'title': title or actor_name(actor) or 'JSON Feed',
    'feed_url': feed_url,
    'home_page_url': home_page_url or actor.get('url'),
    'authors': [{
      'name': actor_name(actor),
      'url': actor.get('url'),
      'avatar': image_url(actor),
    }],
    'items': items,
  }, ignore='content_text')


activities_to_jsonfeed = from_as1
"""Deprecated! Use :meth:`from_as1` instead."""


def to_as1(jsonfeed):
  """Converts a JSON feed to ActivityStreams activities and actor.

  Args:
    jsonfeed (dict): JSON Feed data

  Returns:
    tuple: ``(activities, actor)``, where activities and actor are both
    ActivityStreams object dicts

  Raises:
    ValueError: if jsonfeed isn't a valid JSON Feed dict
  """
  if not hasattr(jsonfeed, 'get'):
    raise ValueError(f'Expected dict (or compatible), got {jsonfeed.__class__.__name__}')

  feed_author = util.get_first(jsonfeed, 'authors', default={})
  actor = {
    'objectType': 'person',
    'url': feed_author.get('url'),
    'image': [{'url': feed_author.get('avatar')}],
    'displayName': feed_author.get('name'),
  }

  def attachment(jf):
    if not hasattr(jf, 'get'):
      raise ValueError(f'Expected attachment to be dict; got {jf!r}')
    url = jf.get('url')
    type = jf.get('mime_type', '').split('/')[0]
    as1 = {
      'objectType': type,
      'title': jf.get('title'),
    }
    if type in ('audio', 'video'):
      as1['stream'] = {'url': url}
    else:
      as1['url'] = url
    return as1

  activities = []
  for item in jsonfeed.get('items', []):
    author = util.get_first(item, 'authors') or feed_author
    if not isinstance(author, dict):
      raise ValueError(f'Expected author to be dict; got {author!r}')
    activities.append(Source.postprocess_activity({
      'objectType': 'article' if item.get('title') else 'note',
      'title': item.get('title'),
      'summary': item.get('summary'),
      'content': (util.get_first(item, 'content_html')
                  or util.get_first(item, 'content_text')),
      'id': str(item.get('id') or ''),
      'published': item.get('date_published'),
      'updated': item.get('date_modified'),
      'url': item.get('url'),
      'image': [{'url': item.get('image')}],
      'author': {
        'displayName': author.get('name'),
        'image': author.get('avatar'),
        'url': author.get('url'),
      },
      'attachments': [attachment(a) for a in item.get('attachments', [])],
    }))

  return (util.trim_nulls(activities), util.trim_nulls(actor))


jsonfeed_to_activities = to_as1
"""Deprecated! Use :meth:`to_as1` instead."""
