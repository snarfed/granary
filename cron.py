"""Cron jobs. Currently just nightly CircleCI build."""
import appengine_config

import requests
import webapp2

CIRCLECI_TOKEN = appengine_config.read('circleci_token')


class BuildCircle(webapp2.RequestHandler):
  def get(self):
    resp = requests.post('https://circleci.com/api/v1.1/project/github/snarfed/granary/tree/master?circle-token=%s' % CIRCLECI_TOKEN)
    resp.raise_for_status()
