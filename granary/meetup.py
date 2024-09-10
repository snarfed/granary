"""Meetup.com source class."""
import datetime
import logging
import re
import urllib.error, urllib.parse, urllib.request

from oauth_dropins import meetup
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_loads

from . import as1
from . import source

logger = logging.getLogger(__name__)

API_BASE = 'https://api.meetup.com'
API_RSVPS = '/%(urlname)s/events/%(event_id)s/rsvps'

# We don't want to be too strict here with what a valid urlname and event_id
# are because Meetup.com haven't documented it too well, and it may change
EVENT_URL_RE = re.compile(r'https://(www\.|)meetup.com/([^/]+)/events/([^/]+)/?$')


class Meetup(source.Source):
  DOMAIN = 'meetup.com'
  NAME = 'Meetup.com'
  URL_CANONICALIZER = util.UrlCanonicalizer(domain=DOMAIN, approve=EVENT_URL_RE)

  @classmethod
  def embed_post(cls, obj):
    """Returns the HTML string for embedding an RSVP from Meetup.com.

    Args:
      obj (dict): AS1 object with at least url, and optionally also content.

    Returns:
      str: HTML
    """
    return f"<span class=\"verb\">RSVP {as1.object_type(obj)[5:]}</span> to <a href=\"{source.Source.base_object(cls, obj)['url']}\">this event</a>."

  def __init__(self, access_token):
    self.access_token = access_token

  def create(self, obj, include_link=source.OMIT_LINK, ignore_formatting=False):
    return self._create(obj, False, include_link, ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK, ignore_formatting=False):
    return self._create(obj, True, include_link, ignore_formatting)

  def post_rsvp(self, urlname, event_id, response):
    url = API_BASE + API_RSVPS % {
      'urlname': urlname,
      'event_id': event_id,
    }
    params = f'response={response}'
    logger.debug(f'Creating RSVP={response} for {urlname} {event_id}')
    return meetup.urlopen_bearer_token(url, self.access_token, data=params)

  def _create(self, obj, preview=False, include_link=source.OMIT_LINK, ignore_formatting=False):
    if preview not in (False, True):
      return self.return_error('Invalid Preview parameter, must be True or False')
    verb = as1.object_type(obj)
    response = None
    if verb == 'rsvp-yes':
      response = 'yes'
    elif verb == 'rsvp-no':
      response = 'no'
    elif verb in ('rsvp-maybe', 'rsvp-interested'):
      return self.return_error(f'Meetup.com does not support {verb}')
    else:
      return self.return_error(f'Meetup.com syndication does not support {verb}')

    # parse the in-reply-to out
    url_containers = self.base_object(obj)
    if not url_containers:
      return self.return_error('RSVP not to Meetup.com or missing in-reply-to')
    if 'url' not in url_containers:
      return self.return_error('missing an in-reply-to')

    event_url = url_containers['url']
    if not event_url:
      return self.return_error('missing an in-reply-to')

    event_url = self.URL_CANONICALIZER(event_url)
    if not event_url:
      return self.return_error('Invalid Meetup.com event URL')

    parsed_url_part = EVENT_URL_RE.match(event_url)
    if not parsed_url_part:
      return self.return_error('Invalid Meetup.com event URL')

    urlname = parsed_url_part.group(2)
    event_id = parsed_url_part.group(3)

    if preview:
      return source.creation_result(description=Meetup.embed_post(obj))

    post_url = obj.get('url')
    if not post_url:
      return self.return_error('Missing the post\'s url')

    create_resp = {
      'url': f'{event_url}#rsvp-by-{urllib.parse.quote_plus(post_url)}',
      'type': 'rsvp'
    }

    try:
      resp = self.post_rsvp(urlname, event_id, response)
      logger.debug(f'Response: {resp.getcode()} {resp.read()}')
      return source.creation_result(create_resp)
    except urllib.error.HTTPError as e:
      code, body = util.interpret_http_exception(e)
      try:
        msg = json_loads(body)['errors'][0]['message']
      except BaseException:
        msg = body
      return self.return_error(f'From Meetup: {code} error: {msg}')

  def return_error(self, msg):
    return source.creation_result(abort=True, error_plain=msg, error_html=msg)

  def user_to_actor(self, user):
    """Converts a user to an actor.

    Args:
      user (dict): a decoded JSON Meetup user

    Returns:
      dict: ActivityStreams actor
    """
    user_id = user.get('id')
    user_id_str = str(user_id)
    published_s = round(user.get('joined') / 1000)
    published_dt = datetime.datetime.fromtimestamp(published_s, tz=datetime.timezone.utc)
    photo = user.get('photo', {}).get('photo_link', 'https://secure.meetupstatic.com/img/noPhoto_80.png')
    return util.trim_nulls({
        'objectType': 'person',
        'displayName': user.get('name'),
        'image': {'url': photo},
        'id': self.tag_uri(user_id_str),
        # numeric_id is our own custom field that always has the source's numeric
        # user id, if available.
        'numeric_id': user_id,
        'published': published_dt.isoformat(),
        'url': self.user_url(user_id_str),
        'urls': None,
        'location': {'displayName': user.get('localized_country_name')},
        'username': user_id_str,
        'description': None,
    })

  def user_url(self, user_id):
    """Returns the URL for a user's profile."""
    return f'https://www.meetup.com/members/{user_id}/'
