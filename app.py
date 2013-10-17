"""Serves the the front page, discovery files, and OAuth flows.
"""

__author__ = 'Ryan Barrett <activitystreams@ryanb.org>'

import urllib

import activitystreams
import appengine_config
import webapp2
from webutil import handlers

from oauth_dropins import facebook
from oauth_dropins import twitter
site_module = {'facebook-activitystreams': facebook,
               'twitter-activitystreams': twitter,
               }[appengine_config.APP_ID]


class FrontPageHandler(handlers.TemplateHandler):
  """Renders and serves /, ie the front page.
  """
  def template_file(self):
    return activitystreams.SOURCE.FRONT_PAGE_TEMPLATE

  def template_vars(self):
    return {'domain': activitystreams.SOURCE.DOMAIN,
            'auth_url': activitystreams.SOURCE.AUTH_URL,
            }


class CallbackHandler(site_module.CallbackHandler):
  def finish(self, auth_entity, state=None):
    return_params = {'facebook-activitystreams': ('access_token',),
                     'twitter-activitystreams': ('token_key', 'token_secret'),
                     }[appengine_config.APP_ID]

    self.redirect('/?%s' % urllib.urlencode(
        {k: getattr(auth_entity, k) for k in return_params}))


application = webapp2.WSGIApplication([
    ('/', FrontPageHandler),
    ('/start_auth', site_module.StartHandler.to('/oauth_callback')),
    ('/oauth_callback', CallbackHandler),
    ] + handlers.HOST_META_ROUTES,
  debug=appengine_config.DEBUG)
