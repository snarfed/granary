"""Convert between ActivityStreams 1 and iCalendar.

iCalendar spec (RFC 5545): https://tools.ietf.org/html/rfc5545

Python icalendar library docs: https://icalendar.readthedocs.io/
"""
from datetime import datetime, timezone
import logging

import dateutil.parser
from icalendar import Calendar, Event, vText
import mf2util
from oauth_dropins.webutil import util

from . import as1, microformats2
from .source import Source

logger = logging.getLogger(__name__)

CONTENT_TYPE = 'text/calendar; charset=utf-8'


def from_as1(activities, actor=None, title=None, multiple=False):
  """Converts ActivityStreams activities to an iCalendar VCALENDAR.

  Only event objects are included; non-event activities are skipped.

  Args:
    activities (sequence of dict): ActivityStreams activities or objects
    actor (dict): ActivityStreams actor, unused (for compatibility with other
      from_as1 functions)
    title (str): calendar title, used as X-WR-CALNAME
    multiple (bool): unused, for compatibility with other from_as1 functions

  Returns:
    str: iCalendar data (RFC 5545)
  """
  try:
    iter(activities)
  except TypeError:
    raise TypeError('activities must be iterable')

  if isinstance(activities, (dict, str)):
    raise TypeError('activities may not be a dict or string')

  cal = Calendar()
  cal.add('prodid', '-//granary//granary//EN')
  cal.add('version', '2.0')
  if title:
    cal.add('x-wr-calname', title)

  for activity in activities:
    obj = as1.get_object(activity) or activity
    if activity.get('verb', 'post') in ('create', 'post') and as1.get_object(activity):
      obj = as1.get_object(activity)

    if obj.get('objectType') != 'event':
      continue

    event = Event()

    uid = obj.get('id') or obj.get('url') or ''
    if uid:
      event.add('uid', uid)

    name = obj.get('displayName') or obj.get('title') or ''
    if name:
      event.add('summary', name)

    content = obj.get('content') or ''
    summary = obj.get('summary') or ''
    description = content or summary
    if description:
      # strip HTML tags for iCalendar description
      description = util.parse_html(description).get_text('')
      event.add('description', description)

    url = obj.get('url')
    if url:
      event.add('url', url)

    # location
    location = as1.get_object(obj, 'location')
    loc_parts = []
    loc_name = location.get('displayName') or ''
    if loc_name:
      loc_parts.append(loc_name)
    address = location.get('address') or ''
    if isinstance(address, dict):
      address = address.get('formatted') or ''
    if address and address != loc_name:
      loc_parts.append(address)
    if loc_parts:
      event.add('location', ', '.join(loc_parts))

    # geo coordinates
    lat = location.get('latitude')
    lon = location.get('longitude')
    if lat is not None and lon is not None:
      event.add('geo', (float(lat), float(lon)))

    # timestamps
    start_time = obj.get('startTime')
    if start_time:
      dt = _parse_datetime(start_time)
      if dt:
        event.add('dtstart', dt)

    end_time = obj.get('endTime')
    if end_time:
      dt = _parse_datetime(end_time)
      if dt:
        event.add('dtend', dt)

    published = obj.get('published')
    if published:
      dt = _parse_datetime(published)
      if dt:
        event.add('created', dt)

    updated = obj.get('updated')
    if updated:
      dt = _parse_datetime(updated)
      if dt:
        event.add('last-modified', dt)

    cal.add_component(event)

  return cal.to_ical().decode('utf-8')


def to_as1(ical_str):
  """Converts iCalendar data to ActivityStreams 1 activities.

  Only VEVENT components are converted; other component types are skipped.

  Args:
    ical_str (str): iCalendar data (RFC 5545)

  Returns:
    list of dict: ActivityStreams activities
  """
  if not isinstance(ical_str, str):
    raise TypeError(f'Expected str, got {ical_str.__class__.__name__}')

  cal = Calendar.from_ical(ical_str)
  activities = []

  for component in cal.walk():
    if component.name != 'VEVENT':
      continue

    obj = {
      'objectType': 'event',
    }

    uid = component.get('uid')
    if uid:
      obj['id'] = str(uid)

    summary = component.get('summary')
    if summary:
      obj['displayName'] = str(summary)

    description = component.get('description')
    if description:
      obj['content'] = str(description)

    url = component.get('url')
    if url:
      obj['url'] = str(url)

    dtstart = component.get('dtstart')
    if dtstart:
      obj['startTime'] = _format_datetime(dtstart.dt)

    dtend = component.get('dtend')
    if dtend:
      obj['endTime'] = _format_datetime(dtend.dt)

    created = component.get('created')
    if created:
      obj['published'] = _format_datetime(created.dt)

    last_modified = component.get('last-modified')
    if last_modified:
      obj['updated'] = _format_datetime(last_modified.dt)

    location_val = component.get('location')
    if location_val:
      location = {
        'objectType': 'place',
        'displayName': str(location_val),
      }
      geo = component.get('geo')
      if geo:
        location['latitude'] = geo.latitude
        location['longitude'] = geo.longitude
      obj['location'] = location

    activity = {
      'objectType': 'activity',
      'verb': 'post',
      'object': obj,
    }
    obj_id = obj.get('id') or obj.get('url')
    if obj_id:
      activity['id'] = obj_id
      activity['url'] = obj.get('url')
    activities.append(Source.postprocess_activity(activity))

  return util.trim_nulls(activities)


def _parse_datetime(s):
  """Parses a datetime string.

  Args:
    s (str): datetime string

  Returns:
    datetime or None
  """
  if not s or not isinstance(s, str):
    return None

  try:
    dt = mf2util.parse_datetime(s)
    if not isinstance(dt, datetime):
      from datetime import time
      dt = datetime.combine(dt, time.min)
    if not dt.tzinfo:
      dt = dt.replace(tzinfo=timezone.utc)
    return dt
  except (ValueError, TypeError):
    try:
      return dateutil.parser.parse(s)
    except (ValueError, dateutil.parser.ParserError):
      return None


def _format_datetime(dt):
  """Formats a datetime as an ISO 8601 string.

  Args:
    dt: datetime or date

  Returns:
    str
  """
  if isinstance(dt, datetime):
    if not dt.tzinfo:
      dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
  else:
    # date-only
    return dt.isoformat()
