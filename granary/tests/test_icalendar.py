"""Unit tests for icalendar.py."""
from datetime import datetime, timezone

from icalendar import Calendar
from oauth_dropins.webutil import testutil

from ..icalendar import from_as1, to_as1


EVENT_AS1 = {
  'objectType': 'event',
  'id': 'tag:example.com,2011:event-xyz',
  'url': 'http://example.com/event-xyz',
  'displayName': 'XYZ',
  'summary': "it's happening!",
  'content': 'this event is gonna be great',
  'published': '2017-01-22T01:29:15+00:00',
  'startTime': '2017-07-12 17:30',
  'endTime': '2017-07-12 19:30',
  'location': {
    'objectType': 'place',
    'displayName': 'the place',
  },
}

ACTIVITY_WITH_EVENT = {
  'objectType': 'activity',
  'verb': 'post',
  'object': EVENT_AS1,
}


class ICalendarTest(testutil.TestCase):

  def _parse_ical(self, ical_str):
    """Helper to parse iCalendar string into a Calendar object."""
    return Calendar.from_ical(ical_str)

  def _get_events(self, ical_str):
    """Helper to get VEVENT components from iCalendar string."""
    cal = self._parse_ical(ical_str)
    return [c for c in cal.walk() if c.name == 'VEVENT']

  def test_from_as1_empty(self):
    got = from_as1([])
    cal = self._parse_ical(got)
    self.assertEqual('2.0', str(cal['version']))
    events = self._get_events(got)
    self.assertEqual(0, len(events))

  def test_from_as1_title(self):
    got = from_as1([], title='My Calendar')
    cal = self._parse_ical(got)
    self.assertEqual('My Calendar', str(cal['x-wr-calname']))

  def test_from_as1_event(self):
    got = from_as1([EVENT_AS1])
    events = self._get_events(got)
    self.assertEqual(1, len(events))

    event = events[0]
    self.assertEqual('tag:example.com,2011:event-xyz', str(event['uid']))
    self.assertEqual('XYZ', str(event['summary']))
    self.assertEqual('this event is gonna be great', str(event['description']))
    self.assertEqual('http://example.com/event-xyz', str(event['url']))
    self.assertEqual('the place', str(event['location']))

  def test_from_as1_activity_with_event(self):
    got = from_as1([ACTIVITY_WITH_EVENT])
    events = self._get_events(got)
    self.assertEqual(1, len(events))
    self.assertEqual('XYZ', str(events[0]['summary']))

  def test_from_as1_skip_non_events(self):
    got = from_as1([{
      'objectType': 'note',
      'content': 'just a note',
    }, EVENT_AS1])
    events = self._get_events(got)
    self.assertEqual(1, len(events))
    self.assertEqual('XYZ', str(events[0]['summary']))

  def test_from_as1_skip_people(self):
    got = from_as1([{
      'objectType': 'person',
      'displayName': 'somebody',
    }])
    events = self._get_events(got)
    self.assertEqual(0, len(events))

  def test_from_as1_multiple_events(self):
    event2 = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-abc',
      'displayName': 'ABC Event',
      'startTime': '2017-08-15 10:00',
      'endTime': '2017-08-15 12:00',
    }
    got = from_as1([EVENT_AS1, event2])
    events = self._get_events(got)
    self.assertEqual(2, len(events))

  def test_from_as1_location_with_address(self):
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-loc',
      'displayName': 'Located Event',
      'startTime': '2017-07-12 17:30',
      'location': {
        'objectType': 'place',
        'displayName': 'City Hall',
        'address': '123 Main St',
      },
    }
    got = from_as1([event])
    events = self._get_events(got)
    self.assertEqual('City Hall, 123 Main St', str(events[0]['location']))

  def test_from_as1_location_with_geo(self):
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-geo',
      'displayName': 'Geo Event',
      'startTime': '2017-07-12 17:30',
      'location': {
        'objectType': 'place',
        'displayName': 'City Hall',
        'latitude': 37.7749,
        'longitude': -122.4194,
      },
    }
    got = from_as1([event])
    events = self._get_events(got)
    geo = events[0]['geo']
    self.assertAlmostEqual(37.7749, geo.latitude)
    self.assertAlmostEqual(-122.4194, geo.longitude)

  def test_from_as1_content_with_html(self):
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-html',
      'displayName': 'HTML Event',
      'content': '<p>This is <b>bold</b> text</p>',
      'startTime': '2017-07-12 17:30',
    }
    got = from_as1([event])
    events = self._get_events(got)
    # HTML should be stripped
    self.assertEqual('This is bold text', str(events[0]['description']))

  def test_from_as1_summary_fallback(self):
    """When content is missing, summary should be used for description."""
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-summ',
      'displayName': 'Summary Event',
      'summary': 'a brief summary',
      'startTime': '2017-07-12 17:30',
    }
    got = from_as1([event])
    events = self._get_events(got)
    self.assertEqual('a brief summary', str(events[0]['description']))

  def test_from_as1_not_list(self):
    for bad in None, 3, 'asdf', {'not': 'a list'}:
      with self.assertRaises(TypeError):
        from_as1(bad)

  def test_from_as1_no_start_time(self):
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-notime',
      'displayName': 'No Time Event',
    }
    got = from_as1([event])
    events = self._get_events(got)
    self.assertEqual(1, len(events))
    self.assertIsNone(events[0].get('dtstart'))

  def test_to_as1_basic(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:tag:example.com,2011:event-xyz
SUMMARY:XYZ
DESCRIPTION:this event is gonna be great
URL:http://example.com/event-xyz
DTSTART:20170712T173000Z
DTEND:20170712T193000Z
LOCATION:the place
END:VEVENT
END:VCALENDAR"""
    activities = to_as1(ical)
    self.assertEqual(1, len(activities))

    activity = activities[0]
    self.assertEqual('activity', activity['objectType'])
    self.assertEqual('post', activity['verb'])

    obj = activity['object']
    self.assertEqual('event', obj['objectType'])
    self.assertEqual('tag:example.com,2011:event-xyz', obj['id'])
    self.assertEqual('XYZ', obj['displayName'])
    self.assertEqual('this event is gonna be great', obj['content'])
    self.assertEqual('http://example.com/event-xyz', obj['url'])
    self.assertIn('2017-07-12', obj['startTime'])
    self.assertIn('2017-07-12', obj['endTime'])
    self.assertEqual('the place', obj['location']['displayName'])
    self.assertEqual('place', obj['location']['objectType'])

  def test_to_as1_multiple_events(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:event-1
SUMMARY:First Event
DTSTART:20170712T173000Z
END:VEVENT
BEGIN:VEVENT
UID:event-2
SUMMARY:Second Event
DTSTART:20170813T100000Z
END:VEVENT
END:VCALENDAR"""
    activities = to_as1(ical)
    self.assertEqual(2, len(activities))
    self.assertEqual('First Event', activities[0]['object']['displayName'])
    self.assertEqual('Second Event', activities[1]['object']['displayName'])

  def test_to_as1_with_geo(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:event-geo
SUMMARY:Geo Event
DTSTART:20170712T173000Z
LOCATION:City Hall
GEO:37.7749;-122.4194
END:VEVENT
END:VCALENDAR"""
    activities = to_as1(ical)
    obj = activities[0]['object']
    self.assertEqual('City Hall', obj['location']['displayName'])
    self.assertAlmostEqual(37.7749, obj['location']['latitude'])
    self.assertAlmostEqual(-122.4194, obj['location']['longitude'])

  def test_to_as1_created_modified(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:event-dates
SUMMARY:Dated Event
DTSTART:20170712T173000Z
CREATED:20170101T120000Z
LAST-MODIFIED:20170601T150000Z
END:VEVENT
END:VCALENDAR"""
    activities = to_as1(ical)
    obj = activities[0]['object']
    self.assertIn('2017-01-01', obj['published'])
    self.assertIn('2017-06-01', obj['updated'])

  def test_to_as1_no_events(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
END:VCALENDAR"""
    activities = to_as1(ical)
    self.assertEqual([], activities)

  def test_to_as1_skips_non_vevent(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VTODO
UID:todo-1
SUMMARY:A Todo Item
END:VTODO
BEGIN:VEVENT
UID:event-1
SUMMARY:An Event
DTSTART:20170712T173000Z
END:VEVENT
END:VCALENDAR"""
    activities = to_as1(ical)
    self.assertEqual(1, len(activities))
    self.assertEqual('An Event', activities[0]['object']['displayName'])

  def test_to_as1_not_string(self):
    for bad in None, 3, {}, []:
      with self.assertRaises(TypeError):
        to_as1(bad)

  def test_roundtrip_from_as1_to_as1(self):
    """Test converting AS1 -> iCal -> AS1 roundtrip."""
    ical = from_as1([EVENT_AS1])
    activities = to_as1(ical)
    self.assertEqual(1, len(activities))

    obj = activities[0]['object']
    self.assertEqual('event', obj['objectType'])
    self.assertEqual('tag:example.com,2011:event-xyz', obj['id'])
    self.assertEqual('XYZ', obj['displayName'])
    self.assertEqual('this event is gonna be great', obj['content'])
    self.assertEqual('http://example.com/event-xyz', obj['url'])
    self.assertEqual('the place', obj['location']['displayName'])

  def test_from_as1_minimal_event(self):
    """An event with only objectType should still produce a VEVENT."""
    event = {'objectType': 'event'}
    got = from_as1([event])
    events = self._get_events(got)
    self.assertEqual(1, len(events))

  def test_from_as1_published_and_updated(self):
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-ts',
      'displayName': 'Timestamp Event',
      'published': '2017-01-22T01:29:15+00:00',
      'updated': '2017-06-01T15:00:00+00:00',
      'startTime': '2017-07-12 17:30',
    }
    got = from_as1([event])
    events = self._get_events(got)
    event_obj = events[0]
    self.assertIsNotNone(event_obj.get('created'))
    self.assertIsNotNone(event_obj.get('last-modified'))

  def test_from_as1_location_address_dict(self):
    """Test location where address is a dict with 'formatted' key."""
    event = {
      'objectType': 'event',
      'id': 'tag:example.com,2011:event-addr',
      'displayName': 'Address Event',
      'startTime': '2017-07-12 17:30',
      'location': {
        'objectType': 'place',
        'displayName': 'City Hall',
        'address': {'formatted': '123 Main St, Springfield'},
      },
    }
    got = from_as1([event])
    events = self._get_events(got)
    self.assertEqual('City Hall, 123 Main St, Springfield',
                     str(events[0]['location']))

  def test_to_as1_minimal_vevent(self):
    ical = """\
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//Test//EN
BEGIN:VEVENT
UID:minimal-event
END:VEVENT
END:VCALENDAR"""
    activities = to_as1(ical)
    self.assertEqual(1, len(activities))
    obj = activities[0]['object']
    self.assertEqual('event', obj['objectType'])
    self.assertEqual('minimal-event', obj['id'])
