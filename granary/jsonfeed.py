"""Convert between ActivityStreams and JSON Feed.

JSON Feed spec: https://jsonfeed.org/version/1
"""
import mimetypes

from oauth_dropins.webutil import util

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

  if isinstance(activities, (dict, basestring)):
    raise TypeError('activities may not be a dict or string')

  def image_url(obj):
    return util.get_first(obj, 'image', {}).get('url')

  def actor_name(obj):
    return obj.get('displayName') or obj.get('username')

  if not actor:
    actor = {}

  items = []
  for activity in activities:
    obj = activity.get('object') or activity
    if obj.get('objectType') == 'person':
      continue
    author = obj.get('author', {})
    item = {
      'id': obj.get('id') or obj.get('url'),
      'url': obj.get('url'),
      'image': image_url(obj),
      'title': obj.get('title'),
      'summary': obj.get('summary'),
      'content_html': obj.get('content'),
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
      url = att.get('url') or att.get('image', {}).get('url') or ''
      mime = mimetypes.guess_type(url)[0]
      if (att.get('objectType') in ATTACHMENT_TYPES or
          mime and mime.split('/')[0] in ATTACHMENT_TYPES):
        item['attachments'].append({
          'url': url,
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
    raise ValueError('Expected dict (or compatible), got %s' % jsonfeed.__class__)

  author = jsonfeed.get('author', {})
  actor = {
    'objectType': 'person',
    'url': author.get('url'),
    'image': [{'url': author.get('avatar')}],
    'displayName': author.get('name'),
  }

  activities = [{'object': {
    'objectType': 'article' if item.get('title') else 'note',
    'title': item.get('title'),
    'summary': item.get('summary'),
    'content': item.get('content_html') or item.get('content_text'),
    'id': unicode(item.get('id') or ''),
    'published': item.get('date_published'),
    'updated': item.get('date_modified'),
    'url': item.get('url'),
    'image': [{'url':  item.get('image')}],
    'author': {
      'displayName': item.get('author', {}).get('name'),
      'image': [{'url': item.get('author', {}).get('avatar')}]
    },
    'attachments': [{
      'url': att.get('url'),
      'objectType': att.get('mime_type', '').split('/')[0],
      'title': att.get('title'),
    } for att in item.get('attachments', [])],
  }} for item in jsonfeed.get('items', [])]

  return (util.trim_nulls(activities), util.trim_nulls(actor))
