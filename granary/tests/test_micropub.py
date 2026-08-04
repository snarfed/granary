"""Unit tests for micropub.py."""
from unittest.mock import patch

from oauth_dropins import indieauth
from requests import HTTPError
from webutil import testutil, util
from webutil.appengine_config import ndb_client
from webutil.testutil import requests_response

from .. import micropub
from ..micropub import Micropub
from ..source import CreationResult

ENDPOINT = 'http://mp.example/micropub'
TOKEN = 'towkin'


class MicropubTest(testutil.TestCase):

  def setUp(self):
    super().setUp()
    self.micropub = Micropub(ENDPOINT, TOKEN)
    self.mock_post = self.start_patch(util.session, 'post')

  def assert_post(self, **kwargs):
    self.mock_post.assert_called_once()
    args, call_kwargs = self.mock_post.call_args
    self.assertEqual((ENDPOINT,), args)
    self.assertEqual(f'Bearer {TOKEN}', call_kwargs['headers']['Authorization'])
    for key, val in kwargs.items():
      self.assert_equals(val, call_kwargs[key])

  @patch.object(util, 'requests_get')
  def test_from_auth_entity_header(self, mock_get):
    mock_get.return_value = requests_response(
      '', url='http://me/', headers={'Link': f'<{ENDPOINT}>; rel="micropub"'})
    with ndb_client.context():
      auth_entity = indieauth.IndieAuth(id='http://me/', user_json='{}',
                                        access_token_str=TOKEN)

    mp = Micropub.from_auth_entity(auth_entity)
    self.assertEqual(ENDPOINT, mp.endpoint)
    self.assertEqual(TOKEN, mp.access_token)

  @patch.object(util, 'requests_get')
  def test_from_auth_entity_html(self, mock_get):
    mock_get.return_value = requests_response(
      f'<link rel="micropub" href="{ENDPOINT}">', url='http://me/')
    with ndb_client.context():
      auth_entity = indieauth.IndieAuth(id='http://me/', user_json='{}',
                                        access_token_str=TOKEN)

    mp = Micropub.from_auth_entity(auth_entity)
    self.assertEqual(ENDPOINT, mp.endpoint)
    self.assertEqual(TOKEN, mp.access_token)

  @patch.object(util, 'requests_get')
  def test_from_auth_entity_no_endpoint(self, mock_get):
    mock_get.return_value = requests_response('', url='http://me/')
    with ndb_client.context():
      auth_entity = indieauth.IndieAuth(id='http://me/', user_json='{}',
                                        access_token_str=TOKEN)

    with self.assertRaises(AssertionError):
      Micropub.from_auth_entity(auth_entity)

  def test_create_note(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/post'})
    result = self.micropub.create({
      'objectType': 'note',
      'content': 'foo bar',
    })

    self.assert_equals({'id': 'http://my/post', 'url': 'http://my/post'},
                       result.content, result)
    self.assertIsNone(result.error_plain)
    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {'content': ['foo bar']},
    })

  def test_create_reply(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/reply'})
    result = self.micropub.create({
      'objectType': 'comment',
      'content': '@hey great post',
      'inReplyTo': [{'url': 'http://reply/target'}],
    })

    self.assert_equals({'id': 'http://my/reply', 'url': 'http://my/reply'},
                       result.content, result)
    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {
        'content': ['@hey great post'],
        'in-reply-to': ['http://reply/target'],
      },
    })

  def test_create_like(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/like'})
    result = self.micropub.create({
      'objectType': 'activity',
      'verb': 'like',
      'object': {'url': 'http://liked/post'},
    })

    self.assert_equals({'id': 'http://my/like', 'url': 'http://my/like'},
                       result.content, result)
    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {'like-of': ['http://liked/post']},
    })

  def test_create_repost(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/repost'})
    result = self.micropub.create({
      'objectType': 'activity',
      'verb': 'share',
      'object': {'url': 'http://reposted/post'},
    })

    self.assert_equals({'id': 'http://my/repost', 'url': 'http://my/repost'},
                       result.content, result)
    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {'repost-of': ['http://reposted/post']},
    })

  def test_create_rsvp(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/rsvp'})
    result = self.micropub.create({
      'objectType': 'activity',
      'verb': 'rsvp-yes',
      'object': 'http://event/1',
    })

    self.assert_equals({'id': 'http://my/rsvp', 'url': 'http://my/rsvp'},
                       result.content, result)
    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {
        'rsvp': ['yes'],
        'in-reply-to': ['http://event/1'],
      },
    })

  def test_create_with_photo(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/post'})
    self.micropub.create({
      'objectType': 'note',
      'content': 'foo bar',
      'image': [{'url': 'http://a/photo'}],
    })

    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {
        'content': ['foo bar'],
        'photo': ['http://a/photo'],
      },
    })

  def test_create_include_link(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/post'})

    self.micropub.create({
      'objectType': 'note',
      'content': 'foo bar',
      'url': 'http://my/post',
    }, include_link=micropub.source.INCLUDE_LINK)

    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {'content': ['foo bar\nhttp://my/post']},
    })

  def test_create_strips_server_owned_properties(self):
    self.mock_post.return_value = requests_response(
      '', headers={'Location': 'http://my/post'})
    obj = {
      'objectType': 'note',
      'id': 'http://existing/post',
      'url': 'http://existing/post',
      'author': {'objectType': 'person', 'url': 'http://me/'},
      'content': 'foo bar',
    }
    self.micropub.create(obj)

    self.assert_post(json={
      'type': ['h-entry'],
      'properties': {'content': ['foo bar']},
    })

  def test_create_no_location_header(self):
    self.mock_post.return_value = requests_response('', status=202)
    result = self.micropub.create({
      'objectType': 'note',
      'content': 'foo bar',
    })

    self.assert_equals({}, result.content, result)
    self.assertIsNone(result.error_plain)

  def test_create_error(self):
    self.mock_post.return_value = requests_response(
      {'error': 'invalid_request', 'error_description': 'nope'}, status=400)

    with self.assertRaises(HTTPError):
      self.micropub.create({
        'objectType': 'note',
        'content': 'foo bar',
      })

  def test_delete(self):
    self.mock_post.return_value = requests_response('')
    result = self.micropub.delete('http://my/post')

    self.assert_equals({'url': 'http://my/post'}, result.content, result)
    self.assertIsNone(result.error_plain)
    self.assert_post(json={'action': 'delete', 'url': 'http://my/post'})

  def test_delete_error(self):
    self.mock_post.return_value = requests_response(
      {'error': 'not_found'}, status=404)
    with self.assertRaises(HTTPError):
      self.micropub.delete('http://my/post')
