# coding=utf-8
"""Unit tests for googleplus.py.

See googleapiclient/http.py for details on using RequestMockBuilder to mock out
Google API calls. (This is the current doc on apiclient mocks, but it doesn't
mention RequestMockBuilder:
https://developers.google.com/api-client-library/python/guide/mocks )

TODO: figure out how to check the query parameters. Right now they're ignored. :/
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import copy
from email.message import Message
from email.mime.multipart import MIMEMultipart
import json
import os

from apiclient import discovery
from apiclient import http
import httplib2
from oauth_dropins import googleplus as oauth_googleplus
from oauth_dropins.webutil import util
from oauth_dropins.webutil import testutil

from granary import appengine_config
appengine_config.GOOGLE_CLIENT_ID = 'my client id'
appengine_config.GOOGLE_CLIENT_SECRET = 'my client secret'
from granary import googleplus


DISCOVERY_DOC = appengine_config.read(
  os.path.join(os.path.dirname(__file__), '../../googleplus_api_discovery.json'))

def tag_uri(name):
  return util.tag_uri('plus.google.com', name)


ACTIVITY_GP = {  # Google+
  'kind': 'plus#activity',
  'verb': 'post',
  'id': '001',
  'actor': {'id': '444', 'displayName': 'Charles'},
  'object': {
    'content': 'my post',
    'url': 'http://plus.google.com/001',
    },
  }
ACTIVITY_AS = {  # ActivityStreams
  'kind': 'plus#activity',
  'verb': 'post',
  'id': tag_uri('001'),
  'actor': {'id': tag_uri('444'), 'displayName': 'Charles'},
  'object': {
    'content': 'my post',
    'url': 'http://plus.google.com/001',
    'author': {'id': tag_uri('444'), 'displayName': 'Charles'},
    'to': [{'objectType':'group', 'alias':'@public'}],
    },
  }

COMMENT_GP = {  # Google+
  'kind': 'plus#comment',
  'verb': 'post',
  'id': 'zyx.888',
  'actor': {'id': '777', 'displayName': 'Eve'},
  'object': {'content': 'my content'},
  'inReplyTo': [{'url': 'http://post/url'}],
}
COMMENT_AS = {  # ActivityStreams
  'kind': 'plus#comment',
  'verb': 'post',
  'id': tag_uri('zyx.888'),
  'url': 'http://post/url#zyx%23888',
  'author': {'id': tag_uri('777'), 'displayName': 'Eve'},
  'content': 'my content',
  'object': {'content': 'my content'},
  'inReplyTo': [{'url': 'http://post/url'}],
  'to': [{'objectType':'group', 'alias':'@public'}],
  }
PLUSONER = {  # Google+
  'kind': 'plus#person',
  'id': '222',
  'displayName': 'Alice',
  'url': 'https://profiles.google.com/alice',
  'image': {'url': 'https://alice/picture'},
  }
LIKE = {  # ActivityStreams
  'id': tag_uri('001_liked_by_222'),
  'url': 'http://plus.google.com/001#liked-by-222',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'http://plus.google.com/001'},
  'author': {
    'kind': 'plus#person',
    'id': tag_uri('222'),
    'displayName': 'Alice',
    'url': 'https://profiles.google.com/alice',
    'image': {'url': 'https://alice/picture'},
    },
  }
RESHARER = {  # Google+
  'kind': 'plus#person',
  'id': '444',
  'displayName': 'Bob',
  'url': 'https://plus.google.com/bob',
  'image': {'url': 'https://bob/picture'},
  }
SHARE = {  # ActivityStreams
  'id': tag_uri('001_shared_by_444'),
  'url': 'http://plus.google.com/001#shared-by-444',
  'objectType': 'activity',
  'verb': 'share',
  'object': {'url': 'http://plus.google.com/001'},
  'author': {
    'kind': 'plus#person',
    'id': tag_uri('444'),
    'displayName': 'Bob',
    'url': 'https://plus.google.com/bob',
    'image': {'url': 'https://bob/picture'},
    },
  }


ACTIVITY_GP_EXTRAS = copy.deepcopy(ACTIVITY_GP)  # Google+
ACTIVITY_GP_EXTRAS['object'].update({
  'replies': {'totalItems': 1},
  'plusoners': {'totalItems': 1},
  'resharers': {'totalItems': 1},
  })
ACTIVITY_AS_EXTRAS = copy.deepcopy(ACTIVITY_AS)  # ActivityStreams
ACTIVITY_AS_EXTRAS['object'].update({
  'replies': {'totalItems': 1, 'items': [COMMENT_AS]},
  'plusoners': {'totalItems': 1},
  'resharers': {'totalItems': 1},
  'tags': [LIKE, SHARE],
  })

# HTML from http://plus.google.com/
HTML_ACTIVITY_GP = [
 ["..."],
 [1002, None, None, None, None, [1001, "z13gjrz4ymeldtd5f04chnrixnvpjjqy42o"],
 {"33558957" : [
   "",
   "",
   "",
   "David Barrett",
   "",
   1440425513401,
   None,
   [],  # first comment (if any) would be here
   "z13gjrz4ymeldtd5f04chnrixnvpjjqy42o",
   "",
   "a:ext:client.sharebox.108380595987.apps.googleusercontent.com",
   [None],
   [None],
   "",
   None,
   [None],
   "105815303293125791402",
   [None],
   "https://lh4.googleusercontent.com/-OvNQMFbbks0/AAAAAAAAAAI/AAAAAAAAOuo/YXnsx5bfWxo/photo.jpg",
   None,
   u"Hi! It’s been a while since I’ve written because we’ve been hard at work, but I’m very happy to take the wraps off our latest feature (or really, series of features): Realtime Expense Reports. I know I’ve been hyping this up for a long time, and you’re…",
   "+DavidBarrettQuinthar/posts/VefFHLMoCqV",
   0,
   0,
   "./105815303293125791402",
   [None], None,
   [ # location
     41.230564,
     9.172682,
     "(41.2305630, 9.1726818)",
     "",
     None,
     "/maps/api/staticmap?center=41.230564,9.172682&zoom=14&size=300x220&sensor=false&markers=41.230564,9.172682&client=google-buzz&signature=GDLZ49Fe0-uc4BoVt-e7p-OmZ50%3D",
     ["1152921504606846977", "-7273273746059208260"],
     "",
     "https://maps.google.com?ll=41.230564,9.172682&q=41.230564,9.172682",
     None,
     "https://maps-api-ssl.google.com/maps/api/staticmap?center=41.230564,9.172682&zoom=15&size=100x100&sensor=false&client=google-buzz&signature=Doqggt3WB5BQzKieZRSA2VwHRXM%3D",
     0, None, 412305629, 91726818, None, None, [None]
   ],
   "", 0, 0, 0, 1, None, 0, 1, None, 0,
   1440425513401,
   ] + [None] * 58 + [  # collapsed for brevity
   [
     [335, 0],
     "http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/",
     None, None, None, None,
     [
       1440425513266,
       "http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/",
       "http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/",
       "http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/",
       [None], [None], [None]
     ],
     "http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/",
     {
       "39748951" : [
         "http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/",
         "http://0.gravatar.com/blavatar/ee4c59993abdb971416349dee59ca9d1?s=200&ts=1440425508",
         "Realtime Expense Reports are Here! (And so much more...)",
         "Hi! It's been a while since I've written because we've been hard at work, but I'm very happy to take the wraps off our latest feature (or really, series of features): Realtime Expense Reports. I kn...",
         None,
         ["//lh6.googleusercontent.com/proxy/IvWQIbjjvIWCUhTACtHDQRysGY2NYqf-A6XWPOGMLdr4W5BHFjIeQw4ZOTDrkDA2oc1kKfCgkV7gT-iQIFvOaeUhtfEf_3BPBTNsmesTGSawvh5kednyc-Oi8MPmpdRZ_SE2=w120-h120",
          120, 120, None, None, None, None, 120,
          [2,
           "https://lh6.googleusercontent.com/proxy/IvWQIbjjvIWCUhTACtHDQRysGY2NYqf-A6XWPOGMLdr4W5BHFjIeQw4ZOTDrkDA2oc1kKfCgkV7gT-iQIFvOaeUhtfEf_3BPBTNsmesTGSawvh5kednyc-Oi8MPmpdRZ_SE2=w800-h800"]],
         "//s2.googleusercontent.com/s2/favicons?domain=blog.expensify.com",
         [[[350, 335, 0], "http://quinthar.com/",
           {"41007156" : ["http://quinthar.com/", None, None, None, None, None,
                          None, [None], None, None, [None]]}]],
         None, None, [None], "blog.expensify.com",] + [None] * 172 + [# collapsed for brevity
           [[339, 338, 336, 335, 0],
            "http://0.gravatar.com/blavatar/ee4c59993abdb971416349dee59ca9d1?s=200&ts=1440425508",
            {"40265033" : [
              "http://0.gravatar.com/blavatar/ee4c59993abdb971416349dee59ca9d1?s=200&ts=1440425508",
              "http://0.gravatar.com/blavatar/ee4c59993abdb971416349dee59ca9d1?s=200&ts=1440425508",
              None, None, None,
              ["//lh6.googleusercontent.com/proxy/IvWQIbjjvIWCUhTACtHDQRysGY2NYqf-A6XWPOGMLdr4W5BHFjIeQw4ZOTDrkDA2oc1kKfCgkV7gT-iQIFvOaeUhtfEf_3BPBTNsmesTGSawvh5kednyc-Oi8MPmpdRZ_SE2=w120-h120",
               120, 120, None, None, None, None, 120,
               [2,
                "https://lh6.googleusercontent.com/proxy/IvWQIbjjvIWCUhTACtHDQRysGY2NYqf-A6XWPOGMLdr4W5BHFjIeQw4ZOTDrkDA2oc1kKfCgkV7gT-iQIFvOaeUhtfEf_3BPBTNsmesTGSawvh5kednyc-Oi8MPmpdRZ_SE2=w800-h800"]],
              # ...
           ]}]]}], # ...
  ]}],

 # second element is non-post, under 7 items long
 [1002, None, None],

 # third element is non-post, item 6 is empty
 [1002, None, None, None, None, None, {}],

] # ...

HTML_ACTIVITIES_GP_HEADER = """
<!DOCTYPE html><html lang="en" dir="ltr" ><head><meta name="referrer" content="origin"><base href="https://plus.google.com/"><style>
...
</style></head><body class="Td lj"><input type="text" name="hist_state" id="hist_state" style="display:none;"><iframe id="hist_frame" name="hist_frame1623222153" class="ss" tabindex="-1"></iframe><script>window['OZ_wizstart'] && window['OZ_wizstart']()</script>
<script>AF_initDataCallback({key: '199', isError:  false , hash: '13', data:[2,0]
});</script><script>AF_initDataCallback({key: '161', isError:  false , hash: '14', data:["os.con",[[]
,"these few lines test the code that collapses commas",
[,1,1,,,,20,,"social.google.com",[,]
,,,2,,,0,,15,,[[1002,2],"..."]],,[,],,,"""
HTML_ACTIVITIES_GP_FOOTER = """
]
]
});</script></body></html>"""

HTML_ACTIVITY_AS = {  # Google+
    'id': tag_uri('z13gjrz4ymeldtd5f04chnrixnvpjjqy42o'),
    'url': 'https://plus.google.com/+DavidBarrettQuinthar/posts/VefFHLMoCqV',
    'actor': {
      'id': tag_uri('105815303293125791402'),
      'url': 'https://plus.google.com/105815303293125791402',
      'objectType': 'person',
      'displayName': 'David Barrett',
      'image': {
        'url': 'https://lh4.googleusercontent.com/-OvNQMFbbks0/AAAAAAAAAAI/AAAAAAAAOuo/YXnsx5bfWxo/photo.jpg',
      },
    },
    'verb': 'post',
    'object': {
      'id': tag_uri('z13gjrz4ymeldtd5f04chnrixnvpjjqy42o'),
      'url': 'https://plus.google.com/+DavidBarrettQuinthar/posts/VefFHLMoCqV',
      'objectType': 'note',
      'published': '2015-08-24T14:11:53Z',
      'updated': '2015-08-24T14:11:53Z',
      'content': u'Hi! It’s been a while since I’ve written because we’ve been hard at work, but I’m very happy to take the wraps off our latest feature (or really, series of features): Realtime Expense Reports. I know I’ve been hyping this up for a long time, and you’re…',
      'attachments': [
        {
          'objectType': 'article',
          'displayName': 'Realtime Expense Reports are Here! (And so much more...)',
          'content': "Hi! It's been a while since I've written because we've been hard at work, but I'm very happy to take the wraps off our latest feature (or really, series of features): Realtime Expense Reports. I kn...",
          'url': 'http://blog.expensify.com/2015/08/24/realtime-expense-reports-are-here-and-so-much-more/',
          'image': {
            'url': 'http://0.gravatar.com/blavatar/ee4c59993abdb971416349dee59ca9d1?s=200&ts=1440425508',
          }
        }
      ]
    },
    'location': {
      'displayName': '(41.2305630, 9.1726818)',
      'url': 'https://maps.google.com?ll=41.230564,9.172682&q=41.230564,9.172682',
      'latitude': 41.230564,
      'longitude': 9.172682,
    },
    # 'access': {
    #   'kind': 'plus#acl',
    #   'description': 'Public',
    #   'items': [
    #     {
    #       'type': 'public'
    #     }
    #   ]
    # }
  }


CREDS_JSON = json.dumps({
  'access_token': 'my token',
  'client_id': appengine_config.GOOGLE_CLIENT_ID,
  'client_secret': appengine_config.GOOGLE_CLIENT_SECRET,
  'refresh_token': 'my refresh token',
  'token_expiry': '',
  'token_uri': '',
  'user_agent': '',
  'invalid': '',
})

class GooglePlusTest(testutil.HandlerTest):

  def setUp(self):
    super(GooglePlusTest, self).setUp()
    self.auth_entity = oauth_googleplus.GooglePlusAuth(
      id='my_string_id',
      user_json=json.dumps({
          'displayName': 'Bob',
          }),
      creds_json=CREDS_JSON)
    self.googleplus = googleplus.GooglePlus(auth_entity=self.auth_entity)

  def tearDown(self):
    oauth_googleplus.json_service = None

  def init(self, **kwargs):
    """Sets up the API service from test_googleplus_discovery.

    Pass a requestBuilder or http kwarg to inject expected HTTP requests and
    responses.
    """
    oauth_googleplus.json_service = discovery.build_from_document(
      DISCOVERY_DOC, **kwargs)

  def test_get_comment(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.comments.get': (None, json.dumps(COMMENT_GP)) # None means 200 OK
          }))

    self.assert_equals(COMMENT_AS, self.googleplus.get_comment('234'))

  def test_get_activity(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.get': (None, json.dumps(ACTIVITY_GP))
          }))

    self.assert_equals([ACTIVITY_AS],
                       self.googleplus.get_activities(activity_id='234'))

  def test_get_activities_no_extras_to_fetch(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.list': (None, json.dumps({
                'items': [ACTIVITY_GP, ACTIVITY_GP],
                })),
          },
          # ACTIVITY_GP doesn't say there are any comments, +1s, or shares (via
          # totalItems), so we shouldn't ask for them.
          check_unexpected=True))

    got = self.googleplus.get_activities(fetch_replies=True, fetch_likes=True,
                                         fetch_shares=True)
    self.assert_equals([ACTIVITY_AS, ACTIVITY_AS], got)

  def test_get_activities_fetch_extras(self):
    self.init()

    # Generate minimal fake responses for each request in the batch.
    #
    # Test with multiple activities to cover the bug described in
    # https://github.com/snarfed/bridgy/issues/22#issuecomment-56329848 :
    # util.CacheDict.get_multi() didn't originally handle generator args.
    batch = MIMEMultipart()
    for i, item in enumerate((COMMENT_GP, PLUSONER, RESHARER) * 2):
      msg = Message()
      msg.set_payload('HTTP/1.1 200 OK\n\r\n\r\n' + json.dumps({'items': [item]}))
      msg['Content-ID'] = '<response-abc+%d>' % (i + 1)
      batch.attach(msg)

    # as_string() must be called before get_boundary() to generate the
    # boundaries between parts, but can't be called again, so we capture the
    # result.
    batch_str = batch.as_string()

    gpe_1 = ACTIVITY_GP_EXTRAS
    gpe_2 = copy.deepcopy(gpe_1)
    gpe_2['id'] = '002'
    http_seq = http.HttpMockSequence(
      [({'status': '200'}, json.dumps({'items': [gpe_1, gpe_2]})),
       ({'status': '200',
         'content-type': 'multipart/mixed; boundary="%s"' % batch.get_boundary()},
        batch_str),
       ({'status': '200'}, json.dumps({'items': [gpe_1, gpe_2]})),
       ])

    self.auth_entity.http = lambda: http_seq

    ase_1 = ACTIVITY_AS_EXTRAS
    ase_2 = copy.deepcopy(ase_1)
    ase_2['id'] = tag_uri('002')
    ase_2['object']['tags'][0]['id'] = tag_uri('002_liked_by_222')
    ase_2['object']['tags'][1]['id'] = tag_uri('002_shared_by_444')
    cache = util.CacheDict()
    self.assert_equals([ase_1, ase_2], self.googleplus.get_activities(
        fetch_replies=True, fetch_likes=True, fetch_shares=True, cache=cache))
    for id in '001', '002':
      for prefix in 'AGL ', 'AGS ':
        self.assertEquals(1, cache[prefix + id])

    # no new extras, so another request won't fill them in
    as_1 = copy.deepcopy(ACTIVITY_AS)
    for field in 'replies', 'plusoners', 'resharers':
      as_1['object'][field] = {'totalItems': 1}
    as_2 = copy.deepcopy(as_1)
    as_2['id'] = tag_uri('002')
    self.assert_equals([as_1, as_2], self.googleplus.get_activities(
        fetch_replies=True, fetch_likes=True, fetch_shares=True, cache=cache))

  def test_get_activities_search(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.search': (None, json.dumps({'items': [ACTIVITY_GP]})),
      }))
    self.assert_equals([ACTIVITY_AS],
                       self.googleplus.get_activities(search_query='qwert'))

    # TODO: resurrect?
  # def test_get_activities_request_etag(self):
  #   self.init()
  #   http_seq = http.HttpMockSequence(
  #     [({'status': '200'}, json.dumps({'items': [item]}))])
  #   self.auth_entity.http = lambda: http_seq

  #   resp = self.googleplus.get_activities_response(
  #     fetch_replies=True, fetch_likes=True, fetch_shares=True)
  #   self.assertEquals('"my etag"', resp['etag'])

  def test_get_activities_response_etag(self):
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.list': (httplib2.Response({'status': 200}),
                                   json.dumps({'etag': '"my etag"'})),
          }))
    resp = self.googleplus.get_activities_response(
      fetch_replies=True, fetch_likes=True, fetch_shares=True)
    self.assertEquals('"my etag"', resp['etag'])

  def test_get_activities_304_not_modified(self):
    """Requests with matching ETags return 304 Not Modified."""
    self.init(requestBuilder=http.RequestMockBuilder({
          'plus.activities.list': (httplib2.Response({'status': 304}), '{}'),
          }))
    self.assert_equals([], self.googleplus.get_activities(
          fetch_replies=True, fetch_likes=True, fetch_shares=True))

  def test_postprocess_actor_url_field(self):
    pa = self.googleplus.postprocess_actor
    self.assertEqual({'foo': 'bar'}, pa({'foo': 'bar'}))
    self.assertEqual({'url': 'x',
                      'urls': [{'value': 'x'}]},
                     pa({'urls': [{'value': 'x'}]}))
    self.assertEqual({'url': 'x',
                      'urls': [{'value': 'x'}, {'value': 'y'}]},
                     pa({'urls': [{'value': 'x'}, {'value': 'y'}]}))

    # check alias
    self.assertEquals(self.googleplus.postprocess_actor,
                      self.googleplus.user_to_actor)

  def test_get_actor_minimal(self):
    self.assert_equals({'displayName': 'Bob'}, self.googleplus.get_actor())

  def test_get_actor(self):
    user = {
      'id': '222',
      'displayName': 'Alice',
      'urls': [{'value': 'https://profiles.google.com/alice'}],
    }
    self.auth_entity.user_json = json.dumps(user)

    user.update({
      'id': tag_uri('222'),
      'url': 'https://profiles.google.com/alice',
    })
    self.assert_equals(user, self.googleplus.get_actor())

  def test_get_actor_other_user(self):
    with self.assertRaises(NotImplementedError):
      self.googleplus.get_actor('other')

  def test_get_activities_extra_fetches_fail(self):
    """Sometimes the extras fetches return errors. Ignore that."""
    self.init()

    batch = MIMEMultipart()
    for i in range(3):
      msg = Message()
      msg.set_payload('HTTP/1.1 500 Foo Bar\n\r\n\r\n')
      msg['Content-ID'] = '<response-abc+%d>' % (i + 1)
      batch.attach(msg)

    # as_string() must be called before get_boundary() to generate the
    # boundaries between parts, but can't be called again, so we capture the
    # result.
    batch_str = batch.as_string()

    self.auth_entity.http = lambda: http.HttpMockSequence(
      [({'status': '200'}, json.dumps({'items': [ACTIVITY_GP_EXTRAS]})),
       ({'status': '200',
         'content-type': 'multipart/mixed; boundary="%s"' % batch.get_boundary()},
        batch_str),
       ])

    cache = util.CacheDict()
    self.assert_equals([ACTIVITY_AS], self.googleplus.get_activities(
        fetch_replies=True, fetch_likes=True, fetch_shares=True, cache=cache))
    for prefix in 'AGC ', 'AGL ', 'AGS ':
      self.assertNotIn(prefix + '001', cache)

  def test_html_to_activities(self):
    html = (HTML_ACTIVITIES_GP_HEADER + json.dumps(HTML_ACTIVITY_GP) +
            HTML_ACTIVITIES_GP_FOOTER)
    self.assert_equals([HTML_ACTIVITY_AS], self.googleplus.html_to_activities(html))

  def test_html_to_activities_plusoned(self):
    html_gp = copy.deepcopy(HTML_ACTIVITY_GP)
    html_gp[1][6].values()[0][69] = [
      202,
      [['Billy Bob',
        '1056789',
        1,
        1,
        'https://lh3.googleusercontent.com/billybob.jpg',
        'https://plus.google.com/+BillyBob',
        'male',
      ]],
      # ...
    ]

    expected = copy.deepcopy(HTML_ACTIVITY_AS)
    expected.update({
      'verb': 'like',
      'actor': {
        'id': tag_uri('1056789'),
        'url': 'https://plus.google.com/+BillyBob',
        'objectType': 'person',
        'displayName': 'Billy Bob',
        'image': {'url': 'https://lh3.googleusercontent.com/billybob.jpg'},
      },
    })

    html = (HTML_ACTIVITIES_GP_HEADER + json.dumps(html_gp) +
            HTML_ACTIVITIES_GP_FOOTER)
    self.assert_equals([expected], self.googleplus.html_to_activities(html))

  def test_html_to_activities_similar_to_plusoned(self):
    html_gp = copy.deepcopy(HTML_ACTIVITY_GP)
    for data_at_69 in None, [], [None], [None, None], [None, [None]]:
      html_gp[1][6].values()[0][69] = data_at_69
      html = (HTML_ACTIVITIES_GP_HEADER + json.dumps(html_gp) +
              HTML_ACTIVITIES_GP_FOOTER)
      self.assert_equals([HTML_ACTIVITY_AS],
                         self.googleplus.html_to_activities(html))

  def test_html_to_activities_missing_data(self):
    self.assert_equals([], self.googleplus.html_to_activities(''))
