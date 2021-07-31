"""Cron jobs. Currently just nightly CircleCI build."""
from oauth_dropins.webutil import util

from app import app

CIRCLECI_TOKEN = util.read('circleci_token')


@app.get('/cron/build_circle')
def build_circle(self):
  resp = util.requests_post('https://circleci.com/api/v1.1/project/github/snarfed/granary/tree/main?circle-token=%s' % CIRCLECI_TOKEN)
  resp.raise_for_status()
