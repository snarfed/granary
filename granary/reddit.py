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
    BASE_URL = 'https://reddit.com'
    NAME = 'reddit'

    def __init__(self, refresh_token):
        self.refresh_token = refresh_token

    @staticmethod
    def timestamp_to_iso8601(time_stmp):
        """Converts a timestamp from UNIX format to ISO 8601.
        """
        if not time_stmp:
            return None

        return datetime.datetime.fromtimestamp(time_stmp).isoformat()

    def redditor_to_actor(self, user):
        """Converts a praw Redditor to an actor.
        https://praw.readthedocs.io/en/latest/code_overview/models/redditor.html

        Args:
          user: praw Redditor object

        Returns:
          an ActivityStreams actor dict, ready to be JSON-encoded
        """
        username = user.name
        if not username:
            return {}


        # trying my best to grab all the urls from the profile description

        description = ''
        if user.subreddit:
            user_url = self.BASE_URL+user.subreddit.get('url')
            urls = [user_url]
            description = user.subreddit['public_description']
            profile_urls = re.findall(r'(https?://\S+)', description)
            profile_urls += re.findall(r'(http?://\S+)', description)
            urls += util.trim_nulls(profile_urls)
        else:
            urls = [self.BASE_URL+'/user/'+username]

        image = user.icon_img

        return util.trim_nulls({
          'objectType': 'person',
          'displayName': username,
          'image': {'url': image},
          'id': self.tag_uri(username),
          # numeric_id is our own custom field that always has the source's numeric
          # user id, if available.
          'numeric_id': user.id,
          'published': self.timestamp_to_iso8601(user.created_utc),
          'url': urls[0],
          'urls': [{'value': u} for u in urls] if len(urls) > 1 else None,
          'username': username,
          'description': description,
          })


    def praw_to_object(self, thng, typ):
        """
        Converts a tweet to an object.

        Args:
          thng: a praw object, Sumbission or Comment
          typ: string to denote whether to get submission or comment content

        Returns:
          an ActivityStreams object dict, ready to be JSON-encoded
            """
        obj = {}

        # always prefer id_str over id to avoid any chance of integer overflow.
        # usually shouldn't matter in Python, but still.
        id = thng.id
        if not id:
            return {}

        created_at = thng.created_utc
        try:
            published = self.timestamp_to_iso8601(created_at)
        except ValueError:
            # this is probably already ISO 8601, likely from the archive export.
            # https://help.twitter.com/en/managing-your-account/how-to-download-your-twitter-archive
            # https://chat.indieweb.org/dev/2018-03-30#t1522442860737900
            published = created_at

        obj = {
        'id': self.tag_uri(id),
        'objectType': 'note',
        'published': published,
        'to': [],
        }

        user = thng.author
        if user:
            obj['author'] = self.redditor_to_actor(user)
            username = obj['author'].get('username')

        obj['to'].append({
                          'objectType': 'group',
                          'alias': '@public',
                          })

        obj['url'] = self.BASE_URL+thng.permalink

        if typ=='submission':
            obj['content'] = thng.title
        elif typ=='comment':
            obj['content'] = thng.body

        return self.postprocess_object(obj)


    def praw_to_activity(self, thng, typ):
        """Converts a praw submission or comment to an activity.
        https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
        https://praw.readthedocs.io/en/latest/code_overview/models/comment.html

        Args:
          thng: a praw object, Sumbission or Comment
          typ: string to denote whether to get submission or comment content

        Returns:
          an ActivityStreams activity dict, ready to be JSON-encoded
        """
        obj = self.praw_to_object(thng, typ)
        actor = obj['author']

        activity = {
          'verb': 'post',
          'id': thng.id,
          'url': self.BASE_URL+thng.permalink,
          'actor': actor,
          'object': obj
          }

        return self.postprocess_activity(activity)

    def fetch_replies(self, r, activities):
        """Fetches and injects reddit comments into a list of activities, in place.

        limitations: Only includes top level comments
        Args:
          r: praw api object for querying submissions in activities
          activities: list of activity dicts

        Returns:
          same activities list
        """
        for activity in activities:
            subm = r.submission(id=activity['id'])

            # for v0 we will use just the top level comments because threading is hard
            subm.comments.replace_more()
            replies = []
            for top_level_comment in subm.comments:
                replies.append(self.praw_to_activity(top_level_comment, 'comment'))

            items = [r['object'] for r in replies]
            activity['object']['replies'] = {
            'items': items,
            'totalItems': len(items),
            }

    def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None, **kwargs):
        """
        Fetches reddit submissions and ActivityStreams activities.

        Currently only implements activity_id, search_query and fetch_replies
        """

        activities = []

        r = reddit.get_reddit_api(self.refresh_token)
        r.read_only = True

        if activity_id:
            subm = r.submission(id=activity_id)
            activities.append(self.praw_to_activity(subm, 'submission'))

        if search_query:
            sr = r.subreddit("all")
            subms = sr.search(search_query)
            activities.extend([self.praw_to_activity(subm, 'submission') for subm in subms])

        if fetch_replies:
            self.fetch_replies(r, activities)

        return self.make_activities_base_response(activities)

