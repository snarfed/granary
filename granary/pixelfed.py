"""Pixelfed source class, heavily based on Mastodon.

Pixelfed's API is a clone of Mastodon's.
https://docs.pixelfed.org/technical-documentation/api-v1.html
"""
import logging
import urllib.parse
from urllib.parse import urljoin

from oauth_dropins.webutil import util

from . import mastodon

logger = logging.getLogger(__name__)


class Pixelfed(mastodon.Mastodon):
  """Pixelfed source class."""
  NAME = 'Pixelfed'
  TYPE_LABELS = {
    'post': 'post',
    'comment': 'comment',
    'repost': 'share',
    'like': 'like',
  }

  def user_url(self, username):
    return urljoin(self.instance, urllib.parse.quote(username))

  def status_url(self, username, id):
    """Returns the local instance URL for a status with a given id."""
    return urljoin(self.instance, f'/p/{urllib.parse.quote(username)}/{id}')

  def actor_id(self, user):
    """Returns the ActivityPub actor id for an API user object.

    This is complicated in Pixelfed:
    https://github.com/pixelfed/pixelfed/discussions/6182

    Args:
      user (dict): user API object

    Returns:
      str or None
    """
    if url := user.get('url'):
      if util.domain_from_link(url) == util.domain_from_link(self.instance):
        # local user
        if acct := (user.get('acct') or user.get('username')):
          return urljoin(url, f'/users/{acct}')
      else:
        # remote user
        return url

  def get_activities_response(self, *args, **kwargs):
    if kwargs.get('fetch_mentions'):
      logger.info("Ignoring fetch_mentions=True since Pixelfed doesn't yet support notifications")
      kwargs['fetch_mentions'] = False
    return super().get_activities_response(*args, **kwargs)
