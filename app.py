"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <granary@ryanb.org>'

import json
import logging
import urllib
import urllib2

import appengine_config

from google.appengine.ext import ndb
from oauth_dropins import facebook
from oauth_dropins import flickr
from oauth_dropins import googleplus
from oauth_dropins import instagram
from oauth_dropins import twitter
from oauth_dropins.webutil import handlers
from oauth_dropins.webutil import util
import webapp2

import activitystreams
from granary import atom
from granary import microformats2
from granary import source

API_PARAMS = {
  'access_token',
  'access_token_key',
  'access_token_secret',
  'auth_entity',
  'format',
}


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves the front page."""
  def template_file(self):
    return 'granary/templates/index.html'

  def template_vars(self):
    vars = dict(self.request.params)
    key = vars.get('auth_entity')
    if key:
      vars['entity'] = ndb.Key(urlsafe=key).get()

    return vars


class DemoHandler(webapp2.RequestHandler):
  """Handles silo requests from the interactive demo form on the front page."""
  def get(self):
    params = {name: val for name, val in self.request.params.items()
              if name in API_PARAMS}
    return self.redirect('/%s/@me/%s/@app/%s?plaintext=true&%s' % (
      util.get_required_param(self, 'site'),
      self.request.get('group_id', source.ALL),
      self.request.get('activity_id', ''),
      urllib.urlencode(params)))


class UrlHandler(activitystreams.Handler):
  """Handles AS/mf2 requests from the interactive demo form on the front page."""
  def get(self):
    expected_inputs = ('activitystreams', 'html', 'json-mf2')
    input = util.get_required_param(self, 'input')
    if input not in expected_inputs:
      raise exc.HTTPBadRequest('Invalid input: %s, expected one of %r' %
                               (input, expected_inputs))

    # fetch url
    url = util.get_required_param(self, 'url')
    logging.info('Fetching %s', url)
    resp = urllib2.urlopen(url, timeout=appengine_config.HTTP_TIMEOUT)
    body = resp.read()

    # decode data
    if input == 'activitystreams':
      activities = json.loads(body)
    # elif input == 'html':
    #   activities = json.loads(body)
    elif input == 'json-mf2':
      activities = microformats2.json_to_object(json.loads(body).get('items', []))

    self.write_response(source.Source.make_activities_base_response(activities))


application = webapp2.WSGIApplication([
  ('/', FrontPageHandler),
  ('/demo', DemoHandler),
  ('/facebook/start_auth', facebook.StartHandler.to('/facebook/oauth_callback')),
  ('/facebook/oauth_callback', facebook.CallbackHandler.to('/')),
  ('/flickr/start_auth', flickr.StartHandler.to('/flickr/oauth_callback')),
  ('/flickr/oauth_callback', flickr.CallbackHandler.to('/')),
  ('/google\\+/start_auth', googleplus.StartHandler.to('/google+/oauth_callback')),
  ('/google\\+/oauth_callback', googleplus.CallbackHandler.to('/')),
  ('/instagram/start_auth', instagram.StartHandler.to('/instagram/oauth_callback')),
  ('/instagram/oauth_callback', instagram.CallbackHandler.to('/')),
  ('/twitter/start_auth', twitter.StartHandler.to('/twitter/oauth_callback')),
  ('/twitter/oauth_callback', twitter.CallbackHandler.to('/')),
  ('/url', UrlHandler),
] + handlers.HOST_META_ROUTES, debug=appengine_config.DEBUG)
