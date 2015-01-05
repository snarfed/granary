"""Unit test utilities.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import appengine_config

import requests

from oauth_dropins.webutil.testutil import *


class TestCase(HandlerTest):
  """Base test class. Supports mocking requests calls."""

  def setUp(self):
    super(TestCase, self).setUp()
    for method in ('get', 'head', 'post'):
      self.mox.StubOutWithMock(requests, method, use_mock_anything=True)

  def expect_requests_get(self, *args, **kwargs):
    return self._expect_requests_call(*args, method=requests.get, **kwargs)

  def expect_requests_head(self, *args, **kwargs):
    return self._expect_requests_call(*args, method=requests.head, **kwargs)

  def expect_requests_post(self, *args, **kwargs):
    return self._expect_requests_call(*args, method=requests.post, **kwargs)

  def _expect_requests_call(self, url, response='', status_code=200,
                            content_type='text/html', method=requests.get,
                            redirected_url = None, response_headers=None,
                            **kwargs):
    resp = requests.Response()

    if isinstance(response, unicode):
      response = response.encode('utf-8')
      resp.encoding = 'utf-8'
    resp._content = response

    resp.url = url if redirected_url is None else redirected_url
    resp.status_code = status_code
    resp.headers['content-type'] = content_type
    if response_headers is not None:
      resp.headers.update(response_headers)

    kwargs.setdefault('timeout', appengine_config.HTTP_TIMEOUT)
    if method is requests.head:
      kwargs['allow_redirects'] = True

    call = method(url, **kwargs)
    call.AndReturn(resp)
    return call
