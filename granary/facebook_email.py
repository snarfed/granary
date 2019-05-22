# coding=utf-8
"""Facebook email notification source class.

https://github.com/snarfed/bridgy/issues/854
"""
from __future__ import absolute_import, unicode_literals
from future import standard_library
standard_library.install_aliases()

from datetime import datetime
import re
import urllib.parse
import xml.sax.saxutils

from . import appengine_config
from bs4 import BeautifulSoup
from oauth_dropins.webutil import util


# alias allows unit tests to mock the function
now_fn = datetime.now


def email_to_object(html):
  """Converts a Facebook HTML notification email to an AS1 object.

  Returns: dict, AS1 object, or None if email html couldn't be parsed

  Arguments:
    html: string
  """
  soup = BeautifulSoup(html)
  type = None

  type = 'comment'
  descs = _find_all_text(soup, 'commented on your')

  if not descs:
    type = 'like'
    descs = _find_all_text(soup, 'likes your')

  if not descs:
    return None

  links = descs[0].find_all('a')
  name_link = links[0]
  name = name_link.get_text(strip=True)
  profile_url = name_link['href']
  post_url = _sanitize_url(links[1]['href'])

  if type == 'comment':
    # comment emails have a second section with a preview rendering of the
    # comment, picture and date and comment text are there.
    name_link = soup.find_all('a', string=re.compile(name))[1]

  picture = name_link.find_previous('img')['src']
  when = name_link.find_next('td')
  comment = when.find_next('span', class_='mb_text')

  # example email date/time string: 'December 14 at 12:35 PM'
  published = datetime.strptime(when.get_text(strip=True), '%B %d at %I:%M %p')\
                      .replace(year=now_fn().year)

  obj = {
    'published': published.isoformat(util.T),
    'author': {
      'objectType': 'person',
      'displayName': name,
      'image': {'url': picture},
      'url': _sanitize_url(profile_url),
    },
    # XXX TODO
    'to': [{'objectType':'group', 'alias':'@public'}],
  }


  if type == 'comment':
    obj.update({
      'objectType': 'comment',
      'content': comment.get_text(strip=True),
      'inReplyTo': [{'url': post_url}],
    })
  elif type == 'like':
    obj.update({
      'objectType': 'activity',
      'verb': 'like',
      'object': {'url': post_url},
    })

  return util.trim_nulls(obj)


def _find_all_text(soup, text):
  """BeautifulSoup utility that searches for text and returns a Tag.

  I'd rather just use soup.find(string=...), but it returns a NavigableString
  instead of a Tag, and I need a Tag so I can look at the elements inside it.
  https://www.crummy.com/software/BeautifulSoup/bs4/doc/#the-string-argument

  Args:
    soup: BeautifulSoup
    text: string, must match the target's text exactly after stripping whitespace
  """
  return soup.find_all(lambda tag: text in
                       (c.string.strip() for c in tag.contents if c.string))


def _sanitize_url(url):
  """Normalizes a URL from a notification email.

  Specifically, removes the parts that only let the receiving user use it, and
  removes some personally identifying parts.

  Example profile:
  https://www.facebook.com/nd/?snarfed.org&amp;aref=123&amp;medium=email&amp;mid=1a2b3c&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=image
  https://www.facebook.com/n/?snarfed.org&amp;lloc=actor_profile&amp;aref=789&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com

  Example posts:
  https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com
  https://www.facebook.com/n/?permalink.php&amp;story_fbid=123&amp;id=456&amp;aref=789&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.2.34567890.ABCxyz&amp;n_m=recipient%40example.com

  Args:
    url: string

  Returns: string, sanitized URL
  """
  if util.domain_from_link(url) != 'facebook.com':
    return url

  parsed = urllib.parse.urlparse(url)
  parts = list(parsed)
  if parsed.path in ('/nd/', '/n/'):
    new_path, query = xml.sax.saxutils.unescape(parsed.query).split('&', 1)
    new_query = [(k, v) for k, v in urllib.parse.parse_qsl(query)
                 if k in ('story_fbid', 'id')]
    parts[2] = new_path
    parts[4] = urllib.parse.urlencode(new_query)

  return urllib.parse.urlunparse(parts)
