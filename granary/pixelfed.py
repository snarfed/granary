"""Pixelfed source class, heavily based on Mastodon.

Pixelfed's API is a clone of Mastodon's.
https://docs.pixelfed.org/technical-documentation/api-v1.html
"""
import logging
import urllib

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
    return urllib.parse.urljoin(self.instance, urllib.parse.quote(username))

  def status_url(self, username, id):
    """Returns the local instance URL for a status with a given id."""
    return urllib.parse.urljoin(self.instance, f'/p/{urllib.parse.quote(username)}/{id}')

  def get_activities_response(self, *args, **kwargs):
    if kwargs.get('fetch_mentions'):
      logger.info("Ignoring fetch_mentions=True since Pixelfed doesn't yet support notifications")
      kwargs['fetch_mentions'] = False
    return super().get_activities_response(*args, **kwargs)
