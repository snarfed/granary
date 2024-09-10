"""Tests for meetup.py."""
import copy

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps
from granary.meetup import Meetup


# test data
def tag_uri(name):
    return util.tag_uri('meetup.com', name)

RSVP_ACTIVITY = {
        'id': tag_uri('145304994_rsvp_11500'),
        'url': 'http://localhost/post/wibble/',
        'objectType': 'activity',
        'verb': 'rsvp-yes',
        'object': [
          {
            'url': 'https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439',
          }
        ],
        'actor': {
            'objectType': 'person',
            'displayName': 'Jamie T',
            'id': tag_uri('189380737'),
            'numeric_id': '189380737',
            'url': 'https://www.meetup.com/members/189380737/',
            'image': {'url': 'https://secure.meetupstatic.com/photos/member/6/8/7/5/member_288326741.jpeg'},
            },
        }

USER_JSON = {
        "id": 189380737,
        "name": "Jamie Tanna",
        "email": "email@example.com",
        "status": "active",
        "joined": 1435825101000,
        "city": "Nottingham",
        "country": "gb",
        "localized_country_name": "United Kingdom",
        "state": "J9",
        "lat": 52.95,
        "lon": -1.18,
        "photo": {
            "id": 288326741,
            "highres_link": "https://secure.meetupstatic.com/photos/member/6/8/7/5/highres_288326741.jpeg",
            "photo_link": "https://secure.meetupstatic.com/photos/member/6/8/7/5/member_288326741.jpeg",
            "thumb_link": "https://secure.meetupstatic.com/photos/member/6/8/7/5/thumb_288326741.jpeg",
            "type": "member",
            "base_url": "https://secure.meetupstatic.com"
            },
        "is_pro_admin": False
        }

ACTOR = {
        'objectType': 'person',
        'displayName': 'Jamie Tanna',
        'image': {'url': 'https://secure.meetupstatic.com/photos/member/6/8/7/5/member_288326741.jpeg'},
        'id': 'tag:meetup.com:189380737',
        # numeric_id is our own custom field that always has the source's numeric
        # user id, if available.
        'numeric_id': 189380737,
        'published': '2015-07-02T08:18:21+00:00',
        'url': 'https://www.meetup.com/members/189380737/',
        'urls': None,
        'location': {'displayName': 'United Kingdom'},
        'username': '189380737',
        'description': None,
        }

class MeetupTest(testutil.TestCase):

    def setUp(self):
        super(MeetupTest, self).setUp()
        self.meetup = Meetup('token-here')

    def test_create_rsvp_yes(self):
        self.expect_urlopen(
                url='https://api.meetup.com/PHPMiNDS-in-Nottingham/events/264008439/rsvps',
                data='response=yes',
                response='',
                headers={
                    'Authorization': 'Bearer token-here'
                    }
                )
        self.mox.ReplayAll()

        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'rsvp-yes'
        created = self.meetup.create(rsvp)
        self.assert_equals({'url': 'https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439#rsvp-by-http%3A%2F%2Flocalhost%2Fpost%2Fwibble%2F', 'type': 'rsvp'},
                created.content,
                f'{created.content}\n{rsvp}')

    def test_create_rsvp_yes_with_www(self):
        self.expect_urlopen(
                url='https://api.meetup.com/PHPMiNDS-in-Nottingham/events/264008439/rsvps',
                data='response=yes',
                response='',
                headers={
                    'Authorization': 'Bearer token-here'
                    }
                )
        self.mox.ReplayAll()

        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['object'][0]['url'] = 'https://www.meetup.com/PHPMiNDS-in-Nottingham/events/264008439'
        rsvp['verb'] = 'rsvp-yes'
        created = self.meetup.create(rsvp)
        self.assert_equals({'url': 'https://www.meetup.com/PHPMiNDS-in-Nottingham/events/264008439#rsvp-by-http%3A%2F%2Flocalhost%2Fpost%2Fwibble%2F', 'type': 'rsvp'},
                created.content,
                f'{created.content}\n{rsvp}')

    def test_create_rsvp_yes_with_non_numeric_event_id(self):
        self.expect_urlopen(
                url='https://api.meetup.com/NottsJS/events/qhnpfqyzcblb/rsvps',
                data='response=yes',
                response='',
                headers={
                    'Authorization': 'Bearer token-here'
                    }
                )
        self.mox.ReplayAll()

        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['object'][0]['url'] = 'https://www.meetup.com/NottsJS/events/qhnpfqyzcblb'
        rsvp['verb'] = 'rsvp-yes'
        created = self.meetup.create(rsvp)
        self.assert_equals({'url': 'https://www.meetup.com/NottsJS/events/qhnpfqyzcblb#rsvp-by-http%3A%2F%2Flocalhost%2Fpost%2Fwibble%2F', 'type': 'rsvp'},
                created.content,
                f'{created.content}\n{rsvp}')

    def test_preview_create_rsvp_yes(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'rsvp-yes'
        preview = self.meetup.preview_create(rsvp)
        self.assertEqual('<span class="verb">RSVP yes</span> to '
                          '<a href="https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439">this event</a>.',
                          preview.description)

    def test_create_rsvp_invalid_preview_parameter(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'rsvp-yes'
        result = self.meetup._create(rsvp, preview=None)
        self.assertTrue(result.abort)
        self.assertIn('Invalid Preview parameter, must be True or False', result.error_plain)
        self.assertIn('Invalid Preview parameter, must be True or False', result.error_html)

    def test_create_rsvp_no(self):
        self.expect_urlopen(
                url='https://api.meetup.com/PHPMiNDS-in-Nottingham/events/264008439/rsvps',
                data='response=no',
                response='',
                headers={
                    'Authorization': 'Bearer token-here'
                    }
                )
        self.mox.ReplayAll()

        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'rsvp-no'
        created = self.meetup.create(rsvp)

        self.assert_equals({'url': 'https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439#rsvp-by-http%3A%2F%2Flocalhost%2Fpost%2Fwibble%2F', 'type': 'rsvp'},
                created.content,
                f'{created.content}\n{rsvp}')

    def test_create_rsvp_handles_url_with_trailing_slash(self):
        self.expect_urlopen(
                url='https://api.meetup.com/PHPMiNDS-in-Nottingham/events/264008439/rsvps',
                data='response=yes',
                response='',
                headers={
                    'Authorization': 'Bearer token-here'
                    }
                )
        self.mox.ReplayAll()

        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['object'][0]['url'] = 'https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439/'
        created = self.meetup.create(rsvp)
        self.assert_equals({'url': 'https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439/#rsvp-by-http%3A%2F%2Flocalhost%2Fpost%2Fwibble%2F', 'type': 'rsvp'},
                created.content,
                f'{created.content}\n{rsvp}')

    def test_create_rsvp_does_not_support_rsvp_interested(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'rsvp-interested'
        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('Meetup.com does not support rsvp-interested', result.error_plain)
        self.assertIn('Meetup.com does not support rsvp-interested', result.error_html)

    def test_create_rsvp_does_not_support_rsvp_maybe(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'rsvp-maybe'
        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('Meetup.com does not support rsvp-maybe', result.error_plain)
        self.assertIn('Meetup.com does not support rsvp-maybe', result.error_html)

    def test_create_rsvp_does_not_support_other_verbs(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['verb'] = 'post'
        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('Meetup.com syndication does not support post', result.error_plain)
        self.assertIn('Meetup.com syndication does not support post', result.error_html)

    def test_create_rsvp_without_in_reply_to_object(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        del rsvp['object']
        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('RSVP not to Meetup.com or missing in-reply-to', result.error_plain)
        self.assertIn('RSVP not to Meetup.com or missing in-reply-to', result.error_html)

    def test_create_rsvp_with_empty_in_reply_to_object(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['object'] = []
        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('RSVP not to Meetup.com or missing in-reply-to', result.error_plain)
        self.assertIn('RSVP not to Meetup.com or missing in-reply-to', result.error_html)

    def test_create_rsvp_with_in_reply_to_object_with_no_url_property(self):
        self.expect_urlopen(
            url='https://api.meetup.com/PHPMiNDS-in-Nottingham/events/264008439/rsvps',
            data='response=yes',
            status=498,
            response=json_dumps({'errors': [{'code':'0', 'message':'foo biff'}]}),
            headers={'Authorization': 'Bearer token-here'},
        )
        self.mox.ReplayAll()

        result = self.meetup.create(RSVP_ACTIVITY)
        self.assertTrue(result.abort)
        self.assertIn('From Meetup: 498 error: foo biff', result.error_plain)
        self.assertIn('From Meetup: 498 error: foo biff', result.error_html)

    def test_create_rsvp_with_invalid_url(self):
        for url in ['https://meetup.com/PHPMiNDS-in-Nottingham/', 'https://meetup.com/PHPMiNDS-in-Nottingham/events', 'https://meetup.com/PHPMiNDS-in-Nottingham/events/', 'https://meetup.com//events/264008439']:
            rsvp = copy.deepcopy(RSVP_ACTIVITY)
            rsvp['object'][0]['url'] = url
            result = self.meetup.create(rsvp)

            self.assertTrue(result.abort)
            self.assertIn('Invalid Meetup.com event URL', result.error_plain)
            self.assertIn('Invalid Meetup.com event URL', result.error_html)

    def test_create_rsvp_with_non_meetup_url(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['object'][0]['url'] = 'https://www.eventbrite.com/e/indiewebcamp-amsterdam-tickets-68004881431/faked'

        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('RSVP not to Meetup.com or missing in-reply-to', result.error_plain)
        self.assertIn('RSVP not to Meetup.com or missing in-reply-to', result.error_html)

    def test_create_rsvp_with_no_url(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['url'] = None

        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('Missing the post\'s url', result.error_plain)
        self.assertIn('Missing the post\'s url', result.error_html)

    def test_create_rsvp_api_error(self):
        rsvp = copy.deepcopy(RSVP_ACTIVITY)
        rsvp['url'] = None

        result = self.meetup.create(rsvp)

        self.assertTrue(result.abort)
        self.assertIn('Missing the post\'s url', result.error_plain)
        self.assertIn('Missing the post\'s url', result.error_html)

    def test_user_to_actor(self):
        self.assert_equals(ACTOR, self.meetup.user_to_actor(USER_JSON))

    def test_user_to_actor_with_no_photo(self):
        user_json = {
                "id": 189380737,
                "name": "Jamie Tanna",
                "email": "email@example.com",
                "status": "active",
                "joined": 1435825101000,
                "city": "Nottingham",
                "country": "gb",
                "localized_country_name": "United Kingdom",
                "state": "J9",
                "lat": 52.95,
                "lon": -1.18,
                "is_pro_admin": False
                }

        actor = {
                'objectType': 'person',
                'displayName': 'Jamie Tanna',
                'image': {'url': 'https://secure.meetupstatic.com/img/noPhoto_80.png'},
                'id': 'tag:meetup.com:189380737',
                # numeric_id is our own custom field that always has the source's numeric
                # user id, if available.
                'numeric_id': 189380737,
                'published': '2015-07-02T08:18:21+00:00',
                'url': 'https://www.meetup.com/members/189380737/',
                'urls': None,
                'location': {'displayName': 'United Kingdom'},
                'username': '189380737',
                'description': None,
                }

        self.assert_equals(actor, self.meetup.user_to_actor(user_json))

    def test_user_url(self):
        self.assert_equals('https://www.meetup.com/members/1234/', self.meetup.user_url(1234))

    def test_embed_post(self):
        self.assert_equals('<span class="verb">RSVP yes</span> to <a href="https://meetup.com/PHPMiNDS-in-Nottingham/events/264008439">this event</a>.', Meetup.embed_post(RSVP_ACTIVITY))
