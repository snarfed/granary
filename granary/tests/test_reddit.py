from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import reddit

import copy
import json

class FakeRedditor():
  id = '59ucsixw'
  name = 'bonkerfield'
  subreddit = {'display_name': 'u_bonkerfield',
   'title': '',
   'icon_img': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png?width=256&height=256&crop=256:256,smart&s=81fbf5a84c69533b5679f46638353d9e8471b817',
   'display_name_prefixed': 'u/bonkerfield',
   'name': 't5_2az095',
   'url': '/user/bonkerfield/',
   'public_description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
   }

  icon_img = 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png?width=256&height=256&crop=256:256,smart&s=81fbf5a84c69533b5679f46638353d9e8471b817'

  created_utc = 1576950011.0

class FakeSubmission():
  id = 'ezv3f2'
  permalink = '/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'
  created_utc = 1581007919.0
  title = '[P] GPT-2 + BERT reddit replier. I built a system that generates replies by taking output from GPT-2 and using BERT models to select the most realistic replies. People on r/artificial replied to it as if it were a person.'

  def __init__(self, fake_redditor):
    self.author = fake_redditor


class RedditTest(testutil.TestCase):

  def setUp(self):
    super(RedditTest, self).setUp()
    self.reddit = reddit.Reddit('token-here')

  def test_user_to_actor(self):
    actor = {
      'objectType': 'person',
      'displayName': 'bonkerfield',
      'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png?width=256&height=256&crop=256:256,smart&s=81fbf5a84c69533b5679f46638353d9e8471b817'},
      'id': 'tag:reddit.com:bonkerfield',
      'numeric_id': '59ucsixw',
      'published': '2019-12-21T17:40:11Z',
      'url': 'https://reddit.com/user/bonkerfield/',
      'urls': [
        {
        "value":"https://reddit.com/user/bonkerfield/"
        },
        {
        "value":"https://bonkerfield.org"
        },
        {
        "value":"https://viewfoil.bonkerfield.org"
        }
      ],
      'username': 'bonkerfield',
      'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
      }

    self.assert_equals(actor, self.reddit.user_to_actor(FakeRedditor()))

  def test_submission_to_activity(self):
    activity = {
      'filtered': False,
      'items': [
        {'actor':
          {'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
            'displayName': 'bonkerfield',
            'id': 'tag:reddit.com:bonkerfield',
            'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png?width=256&height=256&crop=256:256,smart&s=81fbf5a84c69533b5679f46638353d9e8471b817'},
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
          'object': {'author':
            {'description': 'https://bonkerfield.org https://viewfoil.bonkerfield.org',
              'displayName': 'bonkerfield',
              'id': 'tag:reddit.com:bonkerfield',
              'image': {'url': 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png?width=256&height=256&crop=256:256,smart&s=81fbf5a84c69533b5679f46638353d9e8471b817'},
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
            'to': [{'alias': '@public', 'objectType': 'group'}],
            'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'
          },
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
    fake_activities = [self.reddit.praw_to_activity(FakeSubmission(FakeRedditor()),type='submission')]

    self.assert_equals(activity, self.reddit.make_activities_base_response(fake_activities))
