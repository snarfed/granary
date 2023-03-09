"""Convert between ActivityStreams and JSON Feed.

JSON Feed spec: https://jsonfeed.org/version/1
"""
import mimetypes

import mf2util
from oauth_dropins.webutil import util

from . import as1, microformats2

# allowed ActivityStreams objectTypes for attachments
ATTACHMENT_TYPES = {'image', 'audio', 'video'}


def activities_to_jsonfeed(activities, actor=None, title=None, feed_url=None,
                           home_page_url=None):
  """Converts ActivityStreams activities to a JSON feed.

  Args:
    activities: sequence of ActivityStreams activity dicts
    actor: ActivityStreams actor dict, the author of the feed
    title: string, the feed title
    home_page_url: string, the home page URL
    feed_url: the URL of the JSON Feed, if any. Included in the feed_url field.

  Returns:
    dict, JSON Feed data, ready to be JSON-encoded
  """
  try:
    iter(activities)
  except TypeError:
    raise TypeError('activities must be iterable')

  if isinstance(activities, (dict, str)):
    raise TypeError('activities may not be a dict or string')

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
    author = obj.get('author', {})
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
      'author': {
        'name': actor_name(author),
        'url': author.get('url'),
        'avatar': image_url(author),
      },
      'attachments': [],
    }

    for att in obj.get('attachments', []):
      url = (util.get_first(att, 'stream') or util.get_first(att, 'image') or att
            ).get('url')
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
    'version': 'https://jsonfeed.org/version/1',
    'title': title or actor_name(actor) or 'JSON Feed',
    'feed_url': feed_url,
    'home_page_url': home_page_url or actor.get('url'),
    'author': {
      'name': actor_name(actor),
      'url': actor.get('url'),
      'avatar': image_url(actor),
    },
    'items': items,
  }, ignore='content_text')


def jsonfeed_to_activities(jsonfeed):
  """Converts a JSON feed to ActivityStreams activities and actor.

  Args:
    jsonfeed: dict, JSON Feed data

  Returns:
    (activities, actor) tuple, where activities and actor are both
    ActivityStreams object dicts

  Raises:
    ValueError, if jsonfeed isn't a valid JSON Feed dict
  """
  if not hasattr(jsonfeed, 'get'):
    raise ValueError(f'Expected dict (or compatible), got {jsonfeed.__class__.__name__}')

  author = jsonfeed.get('author', {})
  actor = {
    'objectType': 'person',
    'url': author.get('url'),
    'image': [{'url': author.get('avatar')}],
    'displayName': author.get('name'),
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
    author = item.get('author', {})
    if not isinstance(author, dict):
      raise ValueError(f'Expected author to be dict; got {author!r}')
    activities.append({'object': {
      'objectType': 'article' if item.get('title') else 'note',
      'title': item.get('title'),
      'summary': item.get('summary'),
      'content': util.get_first(item, 'content_html') or util.get_first(item, 'content_text'),
      'id': str(item.get('id') or ''),
      'published': item.get('date_published'),
      'updated': item.get('date_modified'),
      'url': item.get('url'),
      'image': [{'url': item.get('image')}],
      'author': {
        'displayName': author.get('name'),
        'image': [{'url': author.get('avatar')}]
      },
      'attachments': [attachment(a) for a in item.get('attachments', [])],
    }})

  return (util.trim_nulls(activities), util.trim_nulls(actor))
