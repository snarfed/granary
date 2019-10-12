# coding=utf-8
"""Mastodon source class.

Mastodon is an ActivityPub implementation, but it also has a REST + OAuth 2 API
independent of AP. API docs: https://docs.joinmastodon.org/api/
"""
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()

import urllib.parse

from oauth_dropins.webutil import util
import ujson as json

from . import appengine_config
from . import as2
from . import source


class Mastodon(source.Source):
  """Mastodon source class. See file docstring and Source class for details.

  Attributes:
    instance: string, base URL of Mastodon instance, eg https://mastodon.social/
    access_token: string, optional, OAuth access token
  """
  DOMAIN = 'N/A'
  BASE_URL = 'N/A'
  NAME = 'Mastodon'

  def __init__(self, instance, username=None, access_token=None):
    """Constructor.

    Args:
      instance: string, base URL of Mastodon instance, eg https://mastodon.social/
      username: string, optional, current user's username on this instance
      access_token: string, optional OAuth access token
    """
    assert instance
    self.instance = instance
    self.username = username
    self.access_token = access_token

  def user_url(self, username):
    return urllib.parse.urljoin(self.instance, '@' + username)

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, fetch_replies=False,
                              fetch_likes=False, fetch_shares=False,
                              fetch_events=False, fetch_mentions=False,
                              search_query=None, **kwargs):
    """Fetches toots and converts them to ActivityStreams activities.

    See :meth:`Source.get_activities_response` for details.
    """
    if (fetch_shares or fetch_events or fetch_mentions or search_query or
        group_id or user_id or activity_id):
      raise NotImplementedError()

    assert self.username
    # XXX TODO: brittle
    url = urllib.parse.urljoin(self.instance,
                               '/users/%s/outbox?page=true' % self.username)
    resp = util.requests_get(url, headers=as2.CONNEG_HEADERS)
    activities = [as2.to_as1(a) for a in
                  json.loads(resp.text).get('orderedItems', [])]

    response = self.make_activities_base_response(util.trim_nulls(activities))
    return response
