# coding=utf-8
"""Pixelfed source class, heavily based on Mastodon.

Pixelfed's API is a clone of Mastodon's.
https://docs.pixelfed.org/technical-documentation/api-v1.html
"""
import logging

from . import mastodon


class Pixelfed(mastodon.Mastodon):
  """Pixelfed source class."""
  NAME = 'Pixelfed'

  def user_url(self, username):
    return urllib.parse.urljoin(self.instance, urllib.parse.quote(username))

  def status_url(self, username, id):
    """Returns the local instance URL for a status with a given id."""
    return urllib.parse.urljoin(self.instance, '/p/%s/%s' % (
      urllib.parse.quote(username), id))
