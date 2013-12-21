"""Google+ source class.

TODO(ryan): finish this, write a test, maybe hook it up to a demo app
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import appengine_config
import source


class GooglePlus(source.Source):
  """Implements the ActivityStreams API for Google+.

  The Google+ API already exposes data in ActivityStreams format, so this is
  just a pass through.
  """

  DOMAIN = 'plus.google.com'
  NAME = 'Google+'

  def __init__(self, auth_entity=None, access_token=None):
    """Constructor.

    Currently, only auth_entity is supported. TODO: implement access_token.

    Args:
      access_token: string OAuth access token
      auth_entity: oauth-dropins.googleplus.GooglePlusAuth
    """
    self.access_token = access_token
    self.auth_entity = auth_entity

  def get_actor(self, user_id=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      user_id: string id or username. Defaults to 'me', ie the current user.

    Raises: GooglePlusAPIError
    """
    return self.auth_entity.user_json

  def get_activities(self, user_id=None, group_id=None, app_id=None,
                     activity_id=None, start_index=0, count=0,
                     fetch_likes=False, fetch_shares=False):
    """Returns a list of ActivityStreams activity dicts.

    See method docstring in source.py for details. app_id is ignored.
    """
    if user_id is None:
      user_id = 'me'

    # https://developers.google.com/+/api/latest/activities
    if activity_id:
      call = self.auth_entity.api().activities().get(activityId=activity_id)
      activities = [call.execute(self.auth_entity.http())]
    else:
      call = self.auth_entity.api().activities().list(
        userId=user_id, collection='public', maxResults=count)
      activities = call.execute(self.auth_entity.http()).get('items', [])

    for activity in activities:
      self.postprocess_activity(activity)

    return len(activities), activities

  def get_comment(self, comment_id, activity_id=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
    """
    # https://developers.google.com/+/api/latest/comments
    call = self.auth_entity.api().comments().get(commentId=comment_id)
    cmt = call.execute(self.auth_entity.http())
    self.postprocess_comment(cmt)
    return cmt

  def postprocess_activity(self, activity):
    """Massage G+'s ActivityStreams dialect into our dialect, in place.

    Args:
      activity: ActivityStreams activity dict.
    """
    activity['object']['author'] = activity['actor']
    # also convert id to tag URI
    activity['id'] = self.tag_uri(activity['id'])

  def postprocess_comment(self, comment):
    """Hack to pretend comment activities are comment objects.

    G+ puts almost everything in the comment *activity*, not the object
    inside the activity. So, copy over the content and use the activity
    itself.
    """
    comment['content'] = comment['object']['content']
    comment['author'] = comment.pop('actor')
    # also convert id to tag URI
    comment['id'] = self.tag_uri(comment['id'])
    # G+ comments don't have their own permalinks. :/ so, use the post's.
    comment['url'] = comment['inReplyTo'][0]['url']
