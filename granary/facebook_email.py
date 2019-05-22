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

  Arguments:
    html: string
  """
  soup = BeautifulSoup(html)

  desc = _find_all_text(soup, 'commented on your')
  if desc:
    return _comment_to_object(soup, desc[0])


def _comment_to_object(soup, desc):
  """Converts a Facebook HTML comment notification email to an AS1 object.

  Arguments:
    soup: BeautifulSoup
    desc: Tag element of span with 'X commented on your post.'
  """
  links = desc.find_all('a')
  name = links[0].get_text(strip=True)
  profile_url = links[0]['href']
  post_url = links[1]['href']

  name_in_comment = soup.find_all('a', string=re.compile(name))[1]
  picture = name_in_comment.find_previous('img')['src']
  when = name_in_comment.find_next('td')
  comment = when.find_next('span', class_='mb_text')

  # example email date/time string: 'December 14 at 12:35 PM'
  published = datetime.strptime(when.get_text(strip=True), '%B %d at %I:%M %p')\
                      .replace(year=now_fn().year)

  return util.trim_nulls({
    'objectType': 'comment',
    'content': comment.get_text(strip=True),
    'published': published.isoformat(util.T),
    'inReplyTo': [{
      'url': _sanitize_url(post_url),
    }],
    'author': {
      'objectType': 'person',
      'displayName': name,
      'image': {'url': picture},
      'url': _sanitize_url(profile_url),
    },
    # XXX TODO
    'to': [{'objectType':'group', 'alias':'@public'}],
  })


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

  Example post:
  https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com

  Args:
    url: string

  Returns: string, sanitized URL
  """
  if util.domain_from_link(url) != 'facebook.com':
    return url

  parsed = urllib.parse.urlparse(url)
  parts = list(parsed)
  if parsed.path == '/nd/':
    new_path, query = xml.sax.saxutils.unescape(parsed.query).split('&', 1)
    new_query = [(k, v) for k, v in urllib.parse.parse_qsl(query)
                 if k in ('story_fbid', 'id')]
    parts[2] = new_path
    parts[4] = urllib.parse.urlencode(new_query)

  return urllib.parse.urlunparse(parts)
