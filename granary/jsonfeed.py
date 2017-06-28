"""Convert between ActivityStreams and JSON Feed.

JSON Feed spec: https://jsonfeed.org/version/1
"""

from source import Source
from oauth_dropins.webutil import util


def activities_to_jsonfeed(activities, actor, feed_url=None):
  """Converts ActivityStreams activities to a JSON feed.

  Args:
    activities: sequence of ActivityStreams activity dicts
    actor: ActivityStreams actor dict, the author of the feed
    feed_url: the URL of the JSON Feed, if any. Included in the feed_url field.

  Returns:
    dict, JSON Feed data, ready to be JSON-encoded
  """
  def get_image(obj):
    return util.get_first(obj, 'image', {}).get('url')

  return util.trim_nulls({
    'version': 'https://jsonfeed.org/version/1',
    'feed_url': feed_url,
    'author': {
      'name': Source.actor_name(actor),
      'url': actor.get('url'),
      'avatar': get_image(actor),
    },
    'items': [{
      'id': a.get('id'),
      'url': a.get('url'),
      'image': get_image(a),
      'summary': a.get('summary'),
      'content_text': a.get('content'),
      # 'content_html': TODO
      'date_published': a.get('published'),
      'date_modified': a.get('updated'),
      'author': {
        'name': Source.actor_name(a.get('author', {})),
        'url': a.get('author', {}).get('url'),
        'avatar': get_image(a.get('author', {})),
      },
    } for a in activities],
  })


def jsonfeed_to_activities(jsonfeed):
  """Converts a JSON feed to ActivityStreams activities and actor.

  Args:
    jsonfeed: dict, JSON Feed data

  Returns:
    (activities, actor) tuple, where activities and actor are both
    ActivityStreams object dicts
  """
  author = jsonfeed.get('author', {})
  actor = {
    'objectType': 'person',
    'url': author.get('url'),
    'image': [{'url': author.get('avatar')}],
    'displayName': author.get('name'),
  }

  activities = [{
    'objectType': 'article' if item.get('title') else 'note',
    'summary': item.get('summary'),
    'content': item.get('content_html') or item.get('content_text'),
    'id': unicode(item.get('id')),
    'published': item.get('date_published'),
    'updated': item.get('date_modified'),
    'url': item.get('url'),
    'image': [{'url':  item.get('image')}],
    'author': {
      'displayName': item.get('author', {}).get('name'),
      'image': [{'url': item.get('author', {}).get('avatar')}]
    },
  } for item in jsonfeed.get('items', [])]

  return util.trim_nulls((activities, actor))
