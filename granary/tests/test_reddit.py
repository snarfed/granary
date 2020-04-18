from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import reddit

import copy
import json

class FakeRedditor():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/redditor.html
  """
  id = '59ucsixw'
  name = 'bonkerfield'
  subreddit = {
    'display_name': 'u_bonkerfield',
    'title': '',
    'icon_img': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png',
    'display_name_prefixed': 'u/bonkerfield',
    'name': 't5_2az095',
    'url': '/user/bonkerfield/',
    'public_description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
    }

  icon_img = 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png'

  created_utc = 1576950011.0


class FakeSubmission():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
  """
  id = 'ezv3f2'
  permalink = '/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'
  created_utc = 1581007919.0
  title = '[P] GPT-2 + BERT reddit replier. I built a system that generates replies by taking output from GPT-2 and using BERT models to select the most realistic replies. People on r/artificial replied to it as if it were a person.'
  selftext = 'I was trying to make a reddit reply bot with GPT-2 to see if it could pass as a human on reddit. I wrote up a [results overview](https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/) and a [tutorial post](https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/) to explain how it works.'

  def __init__(self, fake_redditor):
    self.author = fake_redditor


class FakeComment():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
  """
  id = 'fgpvzfw'
  permalink = '/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/fgpvzfw/'
  created_utc = 1581013069.0
  body = 'The ultimate purpose of Reddit will be the testing ground for passing the Turing test. Then we can all quit the internet.'

  def __init__(self, fake_submission, fake_redditor):
    self._parent = fake_submission
    self.author = fake_redditor

  def parent(self):
    return self._parent


ACTIVITY = {
  'filtered': False,
  'items': [
    {'actor':
      {'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
        'displayName': 'bonkerfield',
        'id': 'tag:reddit.com:bonkerfield',
        'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png'},
        'numeric_id': '59ucsixw',
        'objectType': 'person',
        'published': '2019-12-21T17:40:11Z',
        'url': 'https://reddit.com/user/bonkerfield/',
        'urls': [
          {'value': 'https://reddit.com/user/bonkerfield/'},
          {'value': 'https://bonkerfield.org'},
          {'value': 'https://viewfoil.bonkerfield.org'}
        ],
        'username': 'bonkerfield'
      },
    'id': 'ezv3f2',
    'object':
      {'author':
        {'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
          'displayName': 'bonkerfield',
          'id': 'tag:reddit.com:bonkerfield',
          'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png'},
          'numeric_id': '59ucsixw',
          'objectType': 'person',
          'published': '2019-12-21T17:40:11Z',
          'url': 'https://reddit.com/user/bonkerfield/',
          'urls': [
            {'value': 'https://reddit.com/user/bonkerfield/'},
            {'value': 'https://bonkerfield.org'},
            {'value': 'https://viewfoil.bonkerfield.org'}
          ],
          'username': 'bonkerfield'
        },
        'content': '[P] GPT-2 + BERT reddit replier. I built a system that generates replies by taking output from GPT-2 and using BERT models to select the most realistic replies. People on r/artificial replied to it as if it were a person.',
        'id': 'tag:reddit.com:ezv3f2',
        'objectType': 'note',
        'published': '2020-02-06T16:51:59Z',
        'tags': [
          {'displayName': 'https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/',
          'objectType': 'article',
          'url': 'https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/'},
          {'displayName': 'https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/',
          'objectType': 'article',
          'url': 'https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/'}
        ],
        'to': [{'alias': '@public', 'objectType': 'group'}],
        'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'},
        'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/',
        'verb': 'post'
      }
    ],
    'itemsPerPage': 1,
    'sorted': False,
    'startIndex': 0,
    'totalResults': 1,
    'updatedSince': False
  }

COMMENT_OBJECT = {
  'author': {
    'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
    'displayName': 'bonkerfield',
    'id': 'tag:reddit.com:bonkerfield',
    'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png'},
    'numeric_id': '59ucsixw',
    'objectType': 'person',
    'published': '2019-12-21T17:40:11Z',
    'url': 'https://reddit.com/user/bonkerfield/',
    'urls': [
      {'value': 'https://reddit.com/user/bonkerfield/'},
      {'value': 'https://bonkerfield.org'},
      {'value': 'https://viewfoil.bonkerfield.org'}
    ],
    'username': 'bonkerfield'
  },
  'content': 'The ultimate purpose of Reddit will be the testing ground for passing the Turing test. Then we can all quit the internet.',
  'id': 'tag:reddit.com:fgpvzfw',
  'inReplyTo': [
    {
      'id': 'tag:reddit.com:ezv3f2',
      'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'
    }
  ],
  'objectType': 'note',
  'published': '2020-02-06T18:17:49Z',
  'to': [{'alias': '@public', 'objectType': 'group'}],
  'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/fgpvzfw/'
}


ACTOR = {
  'objectType': 'person',
  'displayName': 'bonkerfield',
  'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png'},
  'id': 'tag:reddit.com:bonkerfield',
  'numeric_id': '59ucsixw',
  'published': '2019-12-21T17:40:11Z',
  'url': 'https://reddit.com/user/bonkerfield/',
  'urls': [
    {"value":"https://reddit.com/user/bonkerfield/"},
    {"value":"https://bonkerfield.org"},
    {"value":"https://viewfoil.bonkerfield.org"}
  ],
  'username': 'bonkerfield',
  'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
  }

class RedditTest(testutil.TestCase):

  def setUp(self):
    super(RedditTest, self).setUp()
    self.reddit = reddit.Reddit('token-here')

  def test_praw_to_actor(self):
    self.assert_equals(ACTOR, self.reddit.praw_to_actor(FakeRedditor()))

  def test_praw_to_comment(self):
    fake_author = FakeRedditor()
    fake_sub = FakeSubmission(fake_author)
    self.assert_equals(COMMENT_OBJECT, self.reddit.praw_to_object(FakeComment(fake_sub,fake_author),'comment'))

  def test_submission_to_activity(self):
    fake_activities = [self.reddit.praw_to_activity(FakeSubmission(FakeRedditor()),type='submission')]
    self.assert_equals(ACTIVITY, self.reddit.make_activities_base_response(fake_activities))
