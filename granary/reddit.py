# coding=utf-8
"""reddit.com source class.
"""

from . import source
import datetime
import logging
from oauth_dropins import reddit
from oauth_dropins.webutil import util
import re
import urllib.parse, urllib.request

import praw

class Reddit(source.Source):

    DOMAIN = 'reddit.com'
    BASE_URL = 'https://reddit.com/'
    NAME = 'reddit'

    def __init__(auth_entity, **kwargs):
        api = get_reddit_api(auth_entity)


    def submission_to_activity(self, subm):
        """Converts a reddit submission to an activity.

        Args:
          tweet: dict, a decoded JSON tweet

        Returns:
          an ActivityStreams activity dict, ready to be JSON-encoded
        """
        activity = {
          'verb': 'post',
          'published': subm.created_utc,
          'id': subm.id,
          'url': subm.url,
          'actor': subm.author,
          }

        return self.postprocess_activity(activity)

    def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None, **kwargs):
        """
        blah blah documentation
        """
        if group_id is not None:
            logging.info('group_id not supported')

        if app_id is not None:
            logging.info('app_id not supported')

        if user_id is not None:
            logging.info('user_id not supported')

        activities = []
        r = reddit.get_api(self.refresh_token)

        if activity_id:
            submission = r.get_submission(submission_id=activity_id)

        submission_activity = self.submission_to_activity(submission)

        activities.append(submission_activity)

        response = self.make_activities_base_response(activities)
        return response