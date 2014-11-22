"""Convert ActivityStreams to Atom.

Atom spec: http://atomenabled.org/developers/syndication/
"""

import logging
import os
import string
import urlparse

from google.appengine.ext.webapp import template
from oauth_dropins.webutil import util
import microformats2
import source

ATOM_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), 'templates', 'user_feed.atom')


def activities_to_atom(activities, actor, title=None, request_url=None,
                       host_url=None):
  """Converts ActivityStreams activites to an Atom feed.

  Args:
    activities: list of ActivityStreams activity dicts
    actor: ActivityStreams actor dict, the author of the feed
    title: string, the feed <title> element. Defaults to 'User feed for [NAME]'
    request_url: the URL of this Atom feed, if any. Used in a link rel="self".
    host_url: the home URL for this Atom feed, if any. Used in the top-level
      feed <id> element.

  Returns: unicode string with Atom XML
  """
  # Strip query params from URLs so that we don't include access tokens, etc
  host_url = (_remove_query_params(host_url) if host_url
              else 'https://github.com/snarfed/activitystreams-unofficial')
  request_url = _remove_query_params(request_url) if request_url else host_url

  for a in activities:
    obj = a.get('object', {})
    # Render content as HTML
    content = obj.get('content')
    if content:
      obj['rendered_content'] = microformats2.render_content(obj)

    # Make sure every activity has the title field, since Atom <entry> requires
    # the title element.
    if not a.get('title'):
      a['title'] = util.ellipsize(
        a.get('displayName') or a.get('content') or obj.get('title') or
        obj.get('displayName') or content or 'Untitled')

    # Normalize attachments.image to always be a list.
    for att in obj.get('attachments', []):
      image = att.get('image')
      if image and not isinstance(image, list):
        att['image'] = [image]

  return template.render(ATOM_TEMPLATE_FILE, {
    'items': activities,
    'host_url': host_url,
    'request_url': request_url,
    'title': title or 'User feed for ' + source.Source.actor_name(actor),
    'updated': activities[0]['object'].get('published') if activities else '',
    'actor': actor,
    })


def _remove_query_params(url):
  parsed = list(urlparse.urlparse(url))
  parsed[4] = ''
  return urlparse.urlunparse(parsed)
