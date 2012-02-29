#!/usr/bin/python
"""Unit tests for facebook.py.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json
import mox
import urllib
import urlparse
import webapp2

import facebook
import testutil

DEFAULT_BATCH_REQUEST = urllib.urlencode(
  {'batch': facebook.API_FRIENDS_BATCH_REQUESTS % {'offset': 0, 'limit': 100}})


class FacebookTest(testutil.HandlerTest):

  def setUp(self):
    super(FacebookTest, self).setUp()
    self.facebook = facebook.Facebook(self.handler)

  def test_get_activities(self):
    batch_resp = json.dumps(
      [None,
       {'body': json.dumps({
              '1': {'id': '1',
                    'name': 'Mr. Foo',
                    'link': 'https://www.facebook.com/mr_foo',
                    },
              '2': {'username': 'msbar',
                    'name': 'Ms. Bar',
                    'location': {'name': 'Hometown'},
                    },
              })}])
    self.expect_urlfetch('https://graph.facebook.com/',
                         batch_resp,
                         method='POST',
                         payload=DEFAULT_BATCH_REQUEST)
    self.mox.ReplayAll()

    self.assert_equals((
        None,
        [{'id': '1',
          'displayName': 'Mr. Foo',
          'name': {'formatted': 'Mr. Foo'},
          'accounts': [{'domain': 'facebook.com', 'userid': '1'}],
          'connected': True,
          'relationships': ['friend'],
          'photos': [{'value': 'http://graph.facebook.com/1/picture?type=large'}],
          }, {
          'displayName': 'Ms. Bar',
          'name': {'formatted': 'Ms. Bar'},
          'accounts': [{'domain': 'facebook.com', 'username': 'msbar'}],
          'addresses': [{'formatted': 'Hometown', 'type': 'home'}],
          'connected': True,
          'relationships': ['friend'],
          'photos': [{'value': 'http://graph.facebook.com/msbar/picture?type=large'}],
          }]),
      self.facebook.get_activities())

  def test_get_activities_user_id(self):
    self.expect_urlfetch('https://graph.facebook.com/123', '{}')
    self.mox.ReplayAll()
    self.assert_equals([], self.facebook.get_activities(user_id=123)[1])

  def test_get_activities_user_id_passes_through_access_token(self):
    self.expect_urlfetch('https://graph.facebook.com/123?access_token=asdf',
                         '{"id": 123}')
    self.mox.ReplayAll()

    handler = webapp2.RequestHandler(webapp2.Request.blank('/?access_token=asdf'),
                                     webapp2.Response())
    self.facebook = facebook.Facebook(handler)
    self.facebook.get_activities(user_id=123)[1]

  def test_get_all_activities_passes_through_access_token(self):
    self.expect_urlfetch('https://graph.facebook.com/?access_token=asdf',
                         '[null, {"body": "{}"}]',
                         method='POST',
                         payload=DEFAULT_BATCH_REQUEST)
    self.mox.ReplayAll()

    handler = webapp2.RequestHandler(webapp2.Request.blank('/?access_token=asdf'),
                                     webapp2.Response())
    self.facebook = facebook.Facebook(handler)
    self.facebook.get_activities()

  def test_to_activity_id_only(self):
    self.assert_equals({
        'id': '212038',
        'accounts': [{'domain': 'facebook.com', 'userid': '212038'}],
        'connected': True,
        'relationships': ['friend'],
        'photos': [{'value': 'http://graph.facebook.com/212038/picture?type=large'}],
        },
      self.facebook.to_activity({'id': '212038'}))

  def test_to_activity_username_only(self):
    self.assert_equals({
        'accounts': [{'domain': 'facebook.com', 'username': 'foo'}],
        'connected': True,
        'relationships': ['friend'],
        'photos': [{'value': 'http://graph.facebook.com/foo/picture?type=large'}],
        },
      self.facebook.to_activity({'username': 'foo'}))

  def test_to_activity_minimal(self):
    self.assert_equals({
        'id': '212038',
        'displayName': 'Ryan Barrett',
        'name': {'formatted': 'Ryan Barrett'},
        'accounts': [{'domain': 'facebook.com', 'userid': '212038'}],
        'addresses': [{'formatted': 'San Francisco, California',
                       'type': 'home',
                       }],
        'connected': True,
        'relationships': ['friend'],
        'photos': [{'value': 'http://graph.facebook.com/212038/picture?type=large'}],
        },
      self.facebook.to_activity({
        'id': '212038',
        'name': 'Ryan Barrett',
        'location': {'id': '123', 'name': 'San Francisco, California'},
        }))

  def test_to_activity_full(self):
    self.assert_equals({
        'id': '212038',
        'displayName': 'Ryan Barrett',
        'name': {'formatted': 'Ryan Barrett',
                 'givenName': 'Ryan',
                 'familyName': 'Barrett',
                 },
        'accounts': [{'domain': 'facebook.com',
                      'userid': '212038',
                      'username': 'snarfed.org',
                      }],
        'birthday': '1980-10-01',
        'addresses': [{
          'streetAddress': '1 Palm Dr.',
          'locality': 'Palo Alto',
          'region': 'California',
          'postalCode': '94301',
          'country': 'United States',
          'type': 'home',
          }],
        'phoneNumbers': [{'value': '1234567890', 'type': 'mobile'}],
        'gender': 'male',
        'emails': [{'value': 'ryan@example.com',
                    'type': 'home',
                    'primary': 'true',
                    }],
        'urls': [{'value': 'http://snarfed.org/',
                  'type': 'home',
                  }],
        'organizations': [
          {'name': 'Google', 'type': 'job', 'title': 'Software Engineer',
           'startDate': '2002-01', 'endDate': '2010-01'},
          {'name': 'IBM', 'type': 'job'},
          {'name': 'Polytechnic', 'type': 'school', 'endDate': '2002'},
          {'name': 'Stanford', 'type': 'school', 'endDate': '2002'},
          ],
        'utcOffset': '-08:00',
        'updated': '2012-01-06T02:11:04+0000',
        'connected': True,
        'relationships': ['friend'],
        'note': 'something about me',
        'photos': [{'value': 'http://graph.facebook.com/212038/picture?type=large'}],
        },
      self.facebook.to_activity({
          'id': '212038',
          'name': 'Ryan Barrett',
          'first_name': 'Ryan',
          'last_name': 'Barrett',
          'link': 'http://www.facebook.com/snarfed.org',
          'username': 'snarfed.org',
          'birthday': '10/01/1980',
          'location': {
            'id': '123',
            'name': 'San Francisco, California'
            },
          'address': {
            'street': '1 Palm Dr.',
            'city': 'Palo Alto',
            'state': 'California',
            'country': 'United States',
            'zip': '94301',
            },
          'mobile_phone': '1234567890',
          'work': [{
              'employer': {'id': '104958162837', 'name': 'Google'},
              'projects': [{
                  'id': '399089423614',
                  'name': 'App Engine',
                  'start_date': '2005-01',
                  'end_date': '2010-01'
                  }, {
                  'id': '100680586640141',
                  'name': 'Moneta',
                  'start_date': '2002-01',
                  'end_date': '2006-01',
                  }],
              'position': 'Software Engineer',
              }, {
              'employer': {'name': 'IBM'},
              }],
          'education': [{
              'school': {'id': '7590844925','name': 'Polytechnic'},
              'year': {
                'id': '194878617211512',
                'name': '2002'
                },
              'type': 'High School'
              }, {
              'school': {'id': '6192688417', 'name': 'Stanford'},
              'year': '2002',
              'type': 'Graduate School'
              }],
          'gender': 'male',
          'email': 'ryan@example.com',
          'website': 'http://snarfed.org/',
          'timezone': -8,
          'updated_time': '2012-01-06T02:11:04+0000',
          'bio': 'something about me',
          }))

  def test_to_activity_birthday_without_year(self):
    activity = self.facebook.to_activity({'birthday': '2/28'})
    self.assertEqual('0000-02-28', activity['birthday'])

  def test_to_activity_work_projects_without_start_and_end_date(self):
    activity = self.facebook.to_activity({
        'work': [{'projects': [{'start_date': '2005-01'},
                               {'end_date': '2010-01'}]}]
        })

    org = activity['organizations'][0]
    self.assertEqual(None, org['startDate'])
    self.assertEqual('2010-01', org['endDate'])

  def _test_paging(self, start_index, count, expected_offset, expected_limit):
    batch = facebook.API_FRIENDS_BATCH_REQUESTS % {
        'offset': expected_offset,
        'limit': expected_limit}
    def comp(actual):
      """Mox comparator that compares expected string batch request to actual
      url-encoded POST payload."""
      self.assert_equals(json.loads(batch),
                         json.loads(urlparse.parse_qs(actual)['batch'][0]))
      return True

    self.expect_urlfetch('https://graph.facebook.com/',
                         '[null, {"body": "{}"}]',
                         payload=mox.Func(comp),
                         method='POST')
    self.mox.ReplayAll()
    self.facebook.get_activities(start_index=start_index, count=count)

  def test_paging_defaults(self):
    self._test_paging(0, 0, 0, facebook.Facebook.ITEMS_PER_PAGE)

  def test_paging_count_too_big(self):
    self._test_paging(0, facebook.Facebook.ITEMS_PER_PAGE + 1,
                      0, facebook.Facebook.ITEMS_PER_PAGE)

  def test_paging_start_index_subtracts_from_limit(self):
    self._test_paging(3, 0, 3, facebook.Facebook.ITEMS_PER_PAGE - 3)

  def test_paging_start_index_with_count(self):
    self._test_paging(2, 4, 2, 4)
