#!/usr/bin/python
"""Twitter front page and OAuth demo handlers.

Mostly copied from https://github.com/wasauce/tweepy-examples .
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import logging
import urllib
from webob import exc

import appengine_config
import tweepy
from webutil import handlers

from google.appengine.ext import db
import webapp2

OAUTH_CALLBACK = 'http://%s/oauth_callback' % appengine_config.HOST


class OAuthToken(db.Model):
  """Datastore model class for an OAuth token.
  """
  token_key = db.StringProperty(required=True)
  token_secret = db.StringProperty(required=True)


class StartAuthHandler(webapp2.RequestHandler):
  """Starts three-legged OAuth with Twitter.

  Fetches an OAuth request token, then redirects to Twitter's auth page to
  request an access token.
  """
  handle_exception = handlers.handle_exception

  def get(self):
    try:
      auth = tweepy.OAuthHandler(appengine_config.TWITTER_APP_KEY,
                                 appengine_config.TWITTER_APP_SECRET,
                                 OAUTH_CALLBACK)
      auth_url = auth.get_authorization_url()
    except tweepy.TweepError, e:
      msg = 'Could not create Twitter OAuth request token: '
      logging.exception(msg)
      raise exc.HTTPInternalServerError(msg + `e`)

    # store the request token for later use in the callback handler
    OAuthToken(token_key = auth.request_token.key,
               token_secret = auth.request_token.secret,
               ).put()
    logging.info('Generated request token, redirecting to Twitter: %s', auth_url)
    self.redirect(auth_url)


class CallbackHandler(webapp2.RequestHandler):
  """The OAuth callback. Fetches an access token and redirects to the front page.
  """
  handle_exception = handlers.handle_exception

  def get(self):
    oauth_token = self.request.get('oauth_token', None)
    oauth_verifier = self.request.get('oauth_verifier', None)
    if oauth_token is None:
      raise exc.HTTPBadRequest('Missing required query parameter oauth_token.')

    # Lookup the request token
    request_token = OAuthToken.gql('WHERE token_key=:key', key=oauth_token).get()
    if request_token is None:
      raise exc.HTTPBadRequest('Invalid oauth_token: %s' % oauth_token)

    # Rebuild the auth handler
    auth = tweepy.OAuthHandler(appengine_config.TWITTER_APP_KEY,
                               appengine_config.TWITTER_APP_SECRET)
    auth.set_request_token(request_token.token_key, request_token.token_secret)

    # Fetch the access token
    try:
      access_token = auth.get_access_token(oauth_verifier)
    except tweepy.TweepError, e:
      msg = 'Twitter OAuth error, could not get access token: '
      logging.exception(msg)
      raise exc.HTTPInternalServerError(msg + `e`)

    params = {'access_token_key': access_token.key,
              'access_token_secret': access_token.secret,
              }
    self.redirect('/?%s' % urllib.urlencode(params))


application = webapp2.WSGIApplication(
  [('/start_auth', StartAuthHandler),
   ('/oauth_callback', CallbackHandler),
   ],
  debug=appengine_config.DEBUG)
