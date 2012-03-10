#!/usr/bin/python
"""ActivityStreams API handler classes.

The REST API design follows the precedents of the ActivityStreams APIs below.


DECIDED: use this
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service 



StatusNet
===
e.g. api/statuses/user_timeline/1.atom

http://status.net/wiki/Twitter-compatible_API
http://wiki.activitystrea.ms/w/page/25347165/StatusNet%20Mapping

?callback=foo for JSONP callback

generally follows twitter global query params, e.g. cursor


OpenSocial
===
e.g. baseURL/method/userID/selector?queryParameters

!!! BEST !!!
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service 

http://docs.opensocial.org/display/OSD/OpenSocial+REST+Developer%27s+Guide+%28v0.9%29
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-API-Server.xml
http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml

@me, @self, @all, @friends

http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Core-API-Server.xml#rfc.section.6

count
The number of items per page, for a paged collection. A social network may have a default value for this parameter.
fields
A comma-separated list of fields to include in the representation. A social network may have a default value for this parameter; if you want the complete set of fields included, then set fields to @all.
filterBy
The field to apply the filterOp and filterValue parameters to.
filterOp
The operation to use on the filterBy field when filtering. Defaults to contains. Valid values are contains, equals, startsWith, and present.
filterValue
The value to use with filterOp when filtering.
format
The data format to use, such as json (the default) or atom.
indexBy
Indicates that the specified field should be used as an index in the returned JSON mapping.
networkDistance
Indicates that the returned collection should include results for all friends up to this many links away.
sortBy
The field to use in sorting.
sortOrder
The order in which to sort entries: ascending (the default) or descending.
startIndex
The 1-based index of the first result to be retrieved (for paging).
updatedSince
The date to filter by; returns only items with an updated date equal to or more recent than the specified value.

Google+
===
e.g. plus/v1/people/userId/activities/collection

https://developers.google.com/+/api/latest/activities/list
https://developers.google.com/+/api/

collection 	string 	The collection of activities to list.

Acceptable values are:

    "public" - All public activities created by the specified user.

userId 	string 	The ID of the user to get activities for. The special value "me" can be used to indicate the authenticated user.
Optional Parameters
alt 	string 	Specifies an alternative representation type.

Acceptable values are:

    "json" - Use JSON format (default)

maxResults 	unsigned integer 	The maximum number of activities to include in the response, used for paging. For any response, the actual number returned may be less than the specified maxResults. Acceptable values are 1 to 100, inclusive. (Default: 20)
pageToken 	string 	The continuation token, used to page through large
result sets. To get the next page of results, set this parameter to the value of
"nextPageToken" from the previous response. 

callback 	string 	Specifies a JavaScript function that will be passed the response data for using the API with JSONP.
fields 	string 	Selector specifying which fields to include in a partial response.
key 	string 	API key. Your API key identifies your project and provides you with API access, quota, and reports. Required unless you provide an OAuth 2.0 token.
access_token 	string 	OAuth 2.0 token for the current user. Learn more about OAuth.
prettyPrint 	boolean 	If set to "true", data output will include line breaks and indentation to make it more readable. If set to "false", unnecessary whitespace is removed, reducing the size of the response. Defaults to "true".
userIp 	string 	Identifies the IP address of the end user for whom the API call is being made. This allows per-user quotas to be enforced when calling the API from a server-side application. Learn more about Capping Usage. 
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

try:
  import json
except ImportError:
  import simplejson as json
import logging
import re
import os
import urllib
import webapp2
from webob import exc

import appengine_config
import facebook
import source
import twitter
import util

from google.appengine.ext.webapp.util import run_wsgi_app

# maps app id to source class
SOURCE = {
  'facebook-activitystreams': facebook.Facebook,
  'twitter-activitystreams': twitter.Twitter,
  }.get(appengine_config.APP_ID)

XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<response>%s</response>
"""
ITEMS_PER_PAGE = 100


class Handler(webapp2.RequestHandler):
  """Base class for ActivityStreams API handlers.

  Attributes:
    source: Source subclass
  """

  def __init__(self, *args, **kwargs):
    super(Handler, self).__init__(*args, **kwargs)
    self.source = SOURCE(self)

  def get(self, *args):
    """Handles an API GET.

    Args:
      users: user id (or sequence)
      group: group id
      app: app id
      activities: activity id (or sequence)
    """
    args = urllib.unquote(self.request.path).strip('/').split('/')
    logging.info('@as %r', args)
    if args and args[0] == source.ME:
      args[0] = self.source.get_current_user()
    paging_params = self.get_paging_params()
    total_results, activities = self.source.get_activities(*args, **paging_params)

    response = {'startIndex': paging_params['start_index'],
                'itemsPerPage': len(activities),
                'totalResults': total_results,
                'entry': activities,
                'filtered': False,
                'sorted': False,
                'updatedSince': False,
                }

    format = self.request.get('format', 'json')
    if format == 'json':
      self.response.headers['Content-Type'] = 'application/json'
      self.response.out.write(json.dumps(response, indent=2))
    elif format in ('atom', 'xml'):
      self.response.headers['Content-Type'] = 'text/xml'
      self.response.out.write(XML_TEMPLATE % util.to_xml(response))
    else:
      raise exc.HTTPBadRequest('Invalid format: %s, expected json, atom, xml' %
                               format)

  def get_paging_params(self):
    """Extracts, normalizes and returns the startIndex and count query params.

    Returns:
      dict with 'start_index' and 'count' keys mapped to integers
    """
    start_index = self.get_positive_int('startIndex')
    count = self.get_positive_int('count')

    if count == 0:
      count = ITEMS_PER_PAGE - start_index
    else:
      count = min(count, ITEMS_PER_PAGE)

    return {'start_index': start_index, 'count': count}

  def get_positive_int(self, param):
    try:
      val = self.request.get(param, 0)
      val = int(val)
      assert val >= 0
      return val
    except (ValueError, AssertionError):
      raise exc.HTTPBadRequest('Invalid %s: %s (should be positive int)' %
                               (param, val))


application = webapp2.WSGIApplication([('.*', Handler)],
                                      debug=appengine_config.DEBUG)

def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
