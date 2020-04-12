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

    def __init__(self, refresh_token):
        self.refresh_token = refresh_token


    def submission_to_activity(self, subm):
        """Converts a reddit submission to an activity.

        Args:
          tweet: dict, a decoded JSON tweet

        Returns:
          an ActivityStreams activity dict, ready to be JSON-encoded
        """
        attribute_list = ['comment_karma',
                          'created_utc',
                          'id',
                          'name',
                          'link_karma',
                          'icon_img']
        actor = {a:getattr(subm.author,a) for a in attribute_list}
        actor['username']=actor['name']
        activity = {
          'verb': 'post',
          'id': subm.id,
          'url': subm.url,
          'actor': actor,
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
        r = reddit.get_reddit_api(self.refresh_token)
        r.read_only = True

        logging.info(activity_id)
        if activity_id:
            subm = r.submission(id=activity_id)

        logging.info(subm.title)
        logging.info(dir(subm))
        # logging.info(subm.title)
        submission_activity = self.submission_to_activity(subm)

        activities.append(submission_activity)

        response = self.make_activities_base_response(activities)
        return response