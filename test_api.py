"""Unit tests for api.py."""
import copy
import socket

from oauth_dropins.webutil import testutil

from granary import instagram
from granary import source
from granary.tests import test_facebook
from granary.tests import test_instagram
from granary.tests import test_twitter

import api
from app import app, cache

client = app.test_client()


class FakeSource(source.Source):
  NAME = 'Fake'
  DOMAIN = 'fa.ke'
  BASE_URL = 'http://fa.ke/'

  def __init__(self, **kwargs):
    pass


class ApiTest(testutil.TestCase):

  activities = [{'foo': '☕ bar'}]

  def setUp(self):
    super(ApiTest, self).setUp()
    app.testing = True
    self.mox.StubOutWithMock(FakeSource, 'get_activities_response')
    cache.clear()

  def reset(self):
    self.mox.UnsetStubs()
    self.mox.ResetAll()
    api.SOURCE = FakeSource
    self.mox.StubOutWithMock(FakeSource, 'get_activities_response')

  def get_response(self, url, *args, **kwargs):
    start_index = kwargs.setdefault('start_index', 0)
    kwargs.setdefault('count', api.ITEMS_PER_PAGE_DEFAULT)
    method = kwargs.pop('method', 'GET')

    FakeSource.get_activities_response(*args, **kwargs).AndReturn({
        'startIndex': start_index,
        'itemsPerPage': 1,
        'totalResults': 9,
        'items': self.activities,
        'filtered': False,
        'sorted': False,
        'updatedSince': False,
        })
    self.mox.ReplayAll()

    return client.open(url, method=method)

  def check_request(self, url, *args, **kwargs):
    resp = self.get_response('/fake' + url, *args, **kwargs)
    self.assertEqual(200, resp.status_code)
    self.assert_equals({
        'startIndex': int(kwargs.get('start_index', 0)),
        'itemsPerPage': 1,
        'totalResults': 9,
        'items': [{'foo': '☕ bar'}],
        'filtered': False,
        'sorted': False,
        'updatedSince': False,
        }, resp.json)
    return resp

  def test_all_defaults(self):
    self.check_request('/')

  def test_me(self):
    self.check_request('/@me', None)

  def test_user_id(self):
    self.check_request('/123', '123')

  def test_user_id_tag_uri(self):
    self.check_request('/tag:fa.ke:123', '123')

  def test_all(self):
    self.check_request('/123/@all', '123', None)

  def test_friends(self):
    self.check_request('/123/@friends/', '123', None)

  def test_self(self):
    self.check_request('/123/@self/', '123', '@self')

  def test_blocks(self):
    self.mox.StubOutWithMock(FakeSource, 'get_blocklist')
    blocks = [{'blockee': '1'}, {'blockee': '2'}]
    FakeSource.get_blocklist().AndReturn(blocks)
    self.mox.ReplayAll()

    resp = client.get('/fake/123/@blocks/')
    self.assertEqual(200, resp.status_code)
    self.assert_equals({'items': blocks}, resp.json)

  def test_blocks_rate_limited(self):
    self.mox.StubOutWithMock(FakeSource, 'get_blocklist')
    FakeSource.get_blocklist().AndRaise(source.RateLimited('foo', partial=[]))
    self.mox.ReplayAll()

    resp = client.get('/fake/123/@blocks/')
    self.assertEqual(429, resp.status_code)

  def test_blocks_rate_limited_partial(self):
    self.mox.StubOutWithMock(FakeSource, 'get_blocklist')
    blocks = [{'blockee': '1'}, {'blockee': '2'}]
    FakeSource.get_blocklist().AndRaise(source.RateLimited('foo', partial=blocks))
    self.mox.ReplayAll()

    resp = client.get('/fake/123/@blocks/')
    self.assertEqual(200, resp.status_code)
    self.assert_equals({'items': blocks}, resp.json)

  def test_group_id(self):
    self.check_request('/123/456', '123', '456')

  def test_app(self):
    self.check_request('/123/456/@app/', '123', '456', None)

  def test_app_id(self):
    self.check_request('/123/456/789/', '123', '456', '789')

  def test_app_id_tag_uri(self):
    self.check_request('/123/456/tag:fa.ke:789/', '123', '456', '789')

  def test_activity_id(self):
    self.check_request('/123/456/789/000/', '123', '456', '789', '000')

  def test_activity_id_tag_uri(self):
    self.check_request('/tag:fa.ke:123/456/tag:fa.ke:789/tag:fa.ke:000/',
                       '123', '456', '789', '000')

  def test_activity_id_tag_uri_wrong_domain(self):
    resp = client.get('/fake/123/456/789/tag:foo.bar:000/')
    self.assertEqual(400, resp.status_code)

  def test_defaults_and_activity_id(self):
    self.check_request('/@me/@all/@app/000/', None, None, None, '000')

  def test_as1_format(self):
    resp = self.check_request('/@me/?format=as1', None)
    self.assertEqual('application/stream+json', resp.headers['Content-Type'])

  def test_json_format(self):
    resp = self.check_request('/@me/?format=json', None)
    self.assertEqual('application/json', resp.headers['Content-Type'])

  def test_as1_xml_format(self):
    resp = self.get_response('/fake/?format=as1-xml')
    self.assertEqual(200, resp.status_code)
    self.assertEqual('application/xml; charset=utf-8', resp.headers['Content-Type'])
    self.assert_multiline_equals("""\
<?xml version="1.0" encoding="UTF-8"?>
<response>
<filtered>False</filtered>
<items>
  <foo>☕ bar</foo>
</items>
<itemsPerPage>1</itemsPerPage>
<sorted>False</sorted>
<startIndex>0</startIndex>
<totalResults>9</totalResults>
<updatedSince>False</updatedSince>
</response>
""", resp.get_data(as_text=True))

  def test_xml_format(self):
    resp = self.get_response('/fake/?format=xml')
    self.assertEqual(200, resp.status_code)
    self.assertEqual('application/xml; charset=utf-8', resp.headers['Content-Type'])

  def test_as2_format(self):
    resp = self.get_response('/fake/?format=as2')
    self.assertEqual(200, resp.status_code)
    self.assertEqual('application/activity+json', resp.headers['Content-Type'])

  def test_atom_format(self):
    for test_module in test_facebook, test_instagram, test_twitter:
      with self.subTest(test_module):
        self.reset()
        self.mox.StubOutWithMock(FakeSource, 'get_actor')
        FakeSource.get_actor('456').AndReturn(test_module.ACTOR)
        self.activities = [copy.deepcopy(test_module.ACTIVITY)]

        # include access_token param to check that it gets stripped
        resp = self.get_response('/fake/456/?format=atom&access_token=foo&a=b&cache=false', '456')
        self.assertEqual(200, resp.status_code)
        self.assertEqual('application/atom+xml; charset=utf-8',
                         resp.headers['Content-Type'])
        self.assert_multiline_equals(
          test_module.ATOM % {
            'request_url': 'http://localhost/fake/456/?format=atom&amp;access_token=foo&amp;a=b&amp;cache=false',
            'host_url': 'http://fa.ke/',
            'base_url': 'http://fa.ke/',
          },
          resp.get_data(as_text=True), ignore_blanks=True)

  def test_atom_format_no_user_id(self):
    resp = self.get_response('/fake/?format=atom')
    self.assertEqual(400, resp.status_code)

  def test_atom_format_cant_fetch_actor(self):
    self.mox.StubOutWithMock(FakeSource, 'get_actor')
    FakeSource.get_actor('456').AndRaise(ValueError('foo'))

    resp = self.get_response('/fake/456/?format=atom', '456')
    self.assertEqual(400, resp.status_code)

  def test_html_format(self):
    resp = self.get_response('/fake/?format=html')
    self.assertEqual(200, resp.status_code)
    self.assertEqual('text/html; charset=utf-8', resp.headers['Content-Type'])

  def test_rss_format(self):
    resp = self.get_response('/fake/?format=rss')
    self.assertEqual(200, resp.status_code)
    self.assertEqual('application/rss+xml; charset=utf-8', resp.headers['Content-Type'])

  def test_unknown_format(self):
    resp = self.get_response('/fake/?format=bad')
    self.assertEqual(400, resp.status_code)

  def test_instagram_blocked(self):
    resp = client.get('/instagram/@me/@friends/@app/?interactive=true')
    self.assert_equals(404, resp.status_code)

  def test_bad_start_index(self):
    resp = client.get('/fake/?startIndex=foo')
    self.assertEqual(400, resp.status_code)

  def test_bad_count(self):
    resp = client.get('/fake/?count=-1')
    self.assertEqual(400, resp.status_code)

  def test_start_index(self):
    expected_count = api.ITEMS_PER_PAGE_DEFAULT - 2
    self.check_request('/?startIndex=2', start_index=2, count=expected_count)

  def test_count(self):
    self.check_request('/?count=3', count=3)

  def test_start_index_and_count(self):
    self.check_request('/?startIndex=4&count=5', start_index=4, count=5)

  def test_count_greater_than_items_per_page(self):
    self.check_request('/?count=999', count=api.ITEMS_PER_PAGE_MAX)

  @testutil.enable_flask_caching(app, cache)
  def test_cache(self):
    FakeSource.get_activities_response(
      '123', None, start_index=0, count=api.ITEMS_PER_PAGE_DEFAULT,
    ).AndReturn({'items': ['x']})
    FakeSource.get_activities_response(
      '123', None, start_index=0, count=api.ITEMS_PER_PAGE_DEFAULT,
    ).AndReturn({'items': ['a']})
    self.mox.ReplayAll()

    # first fetches populate the cache. make sure query params are included in
    # cache key.
    first_x = client.get('/fake/123/@all/?x=y')
    first_a = client.get('/fake/123/@all/?a=b')

    # second fetches should use the cache instead of fetching from the silo
    second_x = client.get('/fake/123/@all/?x=y')
    self.assert_equals({'items': ['x']}, second_x.json)

    second_a = client.get('/fake/123/@all/?a=b')
    self.assert_equals({'items': ['a']}, second_a.json)

  def test_cache_false_query_param(self):
    first = self.get_response('/fake/123/@all/?cache=false', '123', None)
    self.reset()
    second = self.get_response('/fake/123/@all/?cache=false', '123', None)
    self.assert_equals(first.get_data(), second.get_data())

  def test_shares_false_query_param(self):
    # just test that the query param gets translated to the include_shares kwarg
    self.get_response('/fake/?shares=false', include_shares=False)

  def test_get_activities_connection_error(self):
    FakeSource.get_activities_response(
      None, start_index=0, count=api.ITEMS_PER_PAGE_DEFAULT
    ).AndRaise(socket.timeout(''))
    self.mox.ReplayAll()
    resp = client.get('/fake/@me')
    self.assertEqual(504, resp.status_code)

  def test_http_head(self):
    resp = self.get_response('/fake/?format=html', method='HEAD')
    self.assertEqual(200, resp.status_code)
    self.assertEqual('text/html; charset=utf-8', resp.headers['Content-Type'])
    self.assertEqual('', resp.get_data(as_text=True))

  def test_unknown_site(self):
    resp = client.get('/bad/')
    self.assertEqual(404, resp.status_code)
    self.assertEqual('Unknown site bad', resp.get_data(as_text=True))
