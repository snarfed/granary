#!/usr/bin/python
"""ActivityStreams API handler classes.

Implements the OpenSocial ActivityStreams REST API:
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-Data.xml

Request paths are of the form /user_id/group_id/app_id/activity_id, where
each element is optional. user_id may be @me. group_id may be @all, @friends
(currently identical to @all), or @self. app_id may be @app, but it doesn't
matter, it's currently ignored.

The supported query parameters are startIndex and count, which are handled as
described in OpenSocial (above) and OpenSearch.

Other relevant activity REST APIs:
http://status.net/wiki/Twitter-compatible_API
http://wiki.activitystrea.ms/w/page/25347165/StatusNet%20Mapping
https://developers.google.com/+/api/latest/activities/list

ActivityStreams specs:
http://activitystrea.ms/specs/
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json
import logging
import re
import os
import urllib
from webob import exc

import appengine_config
import facebook
import instagram
import source
import twitter
from webutil import util
from webutil import webapp2

from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

# maps app id to source class
SOURCE = {
  'facebook-activitystreams': facebook.Facebook,
  'instagram-activitystreams': instagram.Instagram,
  'twitter-activitystreams': twitter.Twitter,
  }.get(appengine_config.APP_ID)

XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>%s</response>
"""
ATOM_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__), 'templates', 'user_feed.atom')
ITEMS_PER_PAGE = 100

# default values for each part of the API request path, e.g. /@me/@self/@all/...
PATH_DEFAULTS = ((source.ME,), (source.ALL, source.FRIENDS), (source.APP,), ())
MAX_PATH_LEN = len(PATH_DEFAULTS)


class Handler(webapp2.RequestHandler):
  """Base class for ActivityStreams API handlers.

  Attributes:
    source: Source subclass
  """

  def source_class(self):
    """Return the Source subclass to use. May be overridden by subclasses."""
    return SOURCE

  def get(self):
    """Handles an API GET.

    Request path is of the form /user_id/group_id/app_id/activity_id , where
    each element is an optional string object id.
    """
    source = self.source_class()(self)

    # parse path
    args = urllib.unquote(self.request.path).strip('/').split('/')
    if len(args) > MAX_PATH_LEN:
      raise exc.HTTPNotFound()
    elif args == ['']:
      args = []

    # handle default path elements
    args = [None if a in defaults else a
            for a, defaults in zip(args, PATH_DEFAULTS)]
    user_id = args[0] if args else None
    paging_params = self.get_paging_params()

    # extract format
    format = self.request.get('format', 'json')
    if format not in ('json', 'atom', 'xml'):
      raise exc.HTTPBadRequest('Invalid format: %s, expected json, atom, xml' %
                               format)

    # get activities and build response
    total_results, activities = source.get_activities(*args, **paging_params)

    response = {'startIndex': paging_params['start_index'],
                'itemsPerPage': len(activities),
                'totalResults': total_results,
                # TODO: this is just for compatibility with
                # http://activitystreamstester.appspot.com/
                # the OpenSocial spec says to use entry instead, so switch back
                # to that eventually
                'items': activities,
                'filtered': False,
                'sorted': False,
                'updatedSince': False,
                }

    if format == 'atom':
      # strip the access token from the request URL before returning
      params = dict(self.request.GET.items())
      if 'access_token' in params:
        del params['access_token']
      request_url = '%s?%s' % (self.request.path_url, urllib.urlencode(params))
      actor = source.get_actor(user_id)
      response.update({
          'host_url': self.request.host_url + "/",
          'request_url': request_url,
          'title': 'User feed for ' + actor.get('displayName', 'unknown'),
          'updated': activities[0]['object'].get('published') if activities else '',
          'actor': actor,
          })

    # encode and write response
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    if format == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.out.write(json.dumps(response, indent=2))
    else:
      self.response.headers['Content-Type'] = 'text/xml'
      if format == 'xml':
        self.response.out.write(XML_TEMPLATE % util.to_xml(response))
      else:
        assert format == 'atom'
        self.response.out.write(template.render(ATOM_TEMPLATE_FILE, response))

    if 'plaintext' in self.request.params:
      # override response content type
      self.response.headers['Content-Type'] = 'text/plain'

  def get_paging_params(self):
    """Extracts, normalizes and returns the startIndex and count query params.

    Returns:
      dict with 'start_index' and 'count' keys mapped to integers
    """
    start_index = self.get_positive_int('startIndex')
    count = self.get_positive_int('count')

    if count == 0:
      count = ITEMS_PER_PAGE - start_index
    else:
      count = min(count, ITEMS_PER_PAGE)

    return {'start_index': start_index, 'count': count}

  def get_positive_int(self, param):
    try:
      val = self.request.get(param, 0)
      val = int(val)
      assert val >= 0
      return val
    except (ValueError, AssertionError):
      raise exc.HTTPBadRequest('Invalid %s: %s (should be positive int)' %
                               (param, val))


def render_html(obj, source_name=None):
  """Renders an ActivityStreams object to HTML and returns the result.

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
  content += render_tags_html(tags.pop('hashtag', []), 'freedom-hashtags')
  content += render_tags_html(sum(tags.values(), []), 'freedom-tags')

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


def render_tags_html(tags, css_class):
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


application = webapp2.WSGIApplication([('.*', Handler)],
                                      debug=appengine_config.DEBUG)

def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
