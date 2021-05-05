"""Cron jobs. Currently just nightly CircleCI build."""
import requests
import webapp2

from oauth_dropins.webutil import util

CIRCLECI_TOKEN = util.read('circleci_token')


class BuildCircle(webapp2.RequestHandler):
  def get(self):
    resp = requests.post('https://circleci.com/api/v1.1/project/github/snarfed/granary/tree/main?circle-token=%s' % CIRCLECI_TOKEN)
    resp.raise_for_status()
