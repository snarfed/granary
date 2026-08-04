"""Micropub source class.

Micropub spec: https://micropub.spec.indieweb.org/
"""
import logging

from oauth_dropins import indieauth
from webutil import util

from . import microformats2
from . import source
from .source import creation_result, INCLUDE_LINK, OMIT_LINK, Source

# properties that only the Micropub server should set, never the client
SERVER_OWNED_PROPERTIES = ('url', 'uid', 'author')

logger = logging.getLogger(__name__)


class Micropub(Source):
  """Micropub source class. See file docstring and :class:`Source` for details."""
  NAME = 'Micropub'
  DOMAIN = None
  BASE_URL = None

  def __init__(self, endpoint, access_token, **requests_kwargs):
    """Constructor.

    Args:
      endpoint (str): Micropub endpoint URL
      access_token (str): OAuth Bearer token
      requests_kwargs (dict): passed to :func:`requests.post`
    """
    assert endpoint
    assert access_token
    self.endpoint = endpoint
    self.access_token = access_token
    self.requests_kwargs = requests_kwargs

  @classmethod
  def from_auth(cls, auth_entity, **kwargs):
    """Creates a :class:`Micropub` from an IndieAuth auth entity.

    Discovers the Micropub endpoint by fetching the entity's ``me`` URL.

    Args:
      auth_entity (oauth_dropins.indieauth.IndieAuth)
      kwargs: passed through to the constructor

    Returns:
      Micropub:
    """
    me = auth_entity.key_id()
    resp = util.requests_get(me)
    endpoint = indieauth.discover_endpoint('micropub', resp)
    assert endpoint, f"Couldn't discover Micropub endpoint for {me}"
    return cls(endpoint, auth_entity.access_token(), **kwargs)

  def _post(self, data):
    headers = {'Authorization': f'Bearer {self.access_token}'}
    resp = util.requests_post(self.endpoint, json=data, headers=headers,
                              **self.requests_kwargs)

    try:
      resp.raise_for_status()
    except BaseException as e:
      util.interpret_http_exception(e)
      raise

    return resp

  def create(self, obj, include_link=OMIT_LINK, ignore_formatting=False):
    """Creates a new Micropub post.

    https://micropub.spec.indieweb.org/#create

    Args:
      obj (dict): ActivityStreams object
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult: content will be a dict with ``id`` and ``url`` keys,
      both the new post's URL, if the server returned one in its ``Location``
      response header, otherwise an empty dict.
    """
    mf2 = microformats2.from_as1(obj)
    props = mf2['properties']
    for prop in SERVER_OWNED_PROPERTIES:
      if val := props.pop(prop, None):
        logger.info(f'Ignoring {prop} {val}')

    content = self._content_for_create(obj, ignore_formatting=ignore_formatting)
    url = obj.get('url')
    if include_link == INCLUDE_LINK and url:
      content = content + '\n' + url

    if content:
      props['content'] = [content]
    else:
      props.pop('content', None)

    resp = self._post({'type': mf2['type'], 'properties': props})
    location = resp.headers.get('Location')
    return creation_result({'id': location, 'url': location} if location else {})

  def delete(self, id):
    """Deletes a Micropub post.

    https://micropub.spec.indieweb.org/#delete

    Args:
      id (str): URL of the post to delete. Micropub has no other post
        identifier, so unlike other :class:`Source` subclasses, this must be
        the post's URL, not a silo-specific id.

    Returns:
      CreationResult: content will be ``{'url': id}``
    """
    self._post({'action': 'delete', 'url': id})
    return creation_result({'url': id})
