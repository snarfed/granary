"""Unit tests for reddit.py."""
import copy

from mox3 import mox
from oauth_dropins import reddit as oauth_reddit
from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import reddit

import praw
from praw.models import Subreddit, User
from praw.models.comment_forest import CommentForest
from praw.models.listing.mixins.redditor import SubListing
from prawcore.exceptions import NotFound


class FakeUserSubreddit():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/other/usersubreddit.html
  """
  id = 'abc123'
  display_name = 'u_bonkerfield'
  name = 'Human readable?'
  description = 'foo bar'
  public_description = 'https://bonkerfield.org https://viewfoil.bonkerfield.org'


class FakeRedditor():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/redditor.html
  """
  id = '59ucsixw'
  name = 'bonkerfield'
  subreddit = FakeUserSubreddit()
  icon_img = 'https://styles.redditmedia.com/t5_2az095/styles/profileIcon_ek6onop1xbf41.png'
  created_utc = 1576950011.0


class FakeMissingRedditor():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/redditor.html
  """
  name = 'ms_missing'

  @property
  def subreddit(self):
    class FakeResponse():
      status_code = '404'
    raise NotFound(FakeResponse())


class FakeSubmission():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/submission.html
  """
  id = 'ezv3f2'
  permalink = '/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'
  created_utc = 1581007919.0
  title = '[P] GPT-2 + BERT reddit replier'
  selftext = '<!-- SC_OFF --><div class="md"><p>I was trying to make a reddit reply bot with GPT-2 to see if it could pass as a human on reddit. I wrote up a <a href="https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/">results overview</a> and a <a href="https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/">tutorial post</a> to explain how it works.'

  def __init__(self, fake_redditor):
    self.author = fake_redditor


class FakeComment():
  """ to mock https://praw.readthedocs.io/en/latest/code_overview/models/comment.html
  """
  id = 'fgpvzfw'
  permalink = '/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/fgpvzfw/'
  created_utc = 1581013069.0
  body_html = '<div class="md"><p>The ultimate purpose of Reddit will be the testing ground for passing the Turing test. Then we can all quit the internet.</p>\n</div>'

  def __init__(self, fake_submission, fake_redditor):
    self._parent = fake_submission
    self.author = fake_redditor

  def parent(self):
    return self._parent


ACTOR = {
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
}

ACTIVITY_WITH_SELFTEXT = {
  'verb': 'post',
  'id': 'tag:reddit.com:ezv3f2',
  'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/',
  'title': '[P] GPT-2 + BERT reddit replier',
  'actor': ACTOR,
  'object': {
    'objectType': 'note',
    'id': 'tag:reddit.com:ezv3f2',
    'author': ACTOR,
    'displayName': '[P] GPT-2 + BERT reddit replier',
    'content': '<!-- SC_OFF --><div class="md"><p>I was trying to make a reddit reply bot with GPT-2 to see if it could pass as a human on reddit. I wrote up a <a href="https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/">results overview</a> and a <a href="https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/">tutorial post</a> to explain how it works.',
    'published': '2020-02-06T16:51:59Z',
    'tags': [{
      'displayName': 'https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/',
      'objectType': 'article',
      'url': 'https://www.bonkerfield.org/2020/02/combining-gpt-2-and-bert/',
    }, {
      'displayName': 'https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/',
      'objectType': 'article',
      'url': 'https://www.bonkerfield.org/2020/02/reddit-bot-gpt2-bert/',
    }],
    'to': [{'alias': '@public', 'objectType': 'group'}],
    'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/',
  },
}

ACTIVITY_WITH_LINK ={
  'verb': 'post',
  'id': 'tag:reddit.com:ezv3f2',
  'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/',
  'title': '[P] GPT-2 + BERT reddit replier',
  'actor': ACTOR,
  'object': {
    'objectType': 'bookmark',
    'id': 'tag:reddit.com:ezv3f2',
    'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/',
    'author': ACTOR,
    'displayName': '[P] GPT-2 + BERT reddit replier',
    'targetUrl': 'https://reddit.com/ezv3f2',
    'published': '2020-02-06T16:51:59Z',
    'to': [{'alias': '@public', 'objectType': 'group'}],
  },
}

COMMENT_OBJECT = {
  'objectType': 'comment',
  'id': 'tag:reddit.com:fgpvzfw',
  'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/fgpvzfw/',
  'author': ACTOR,
  'content': '<div class="md"><p>The ultimate purpose of Reddit will be the testing ground for passing the Turing test. Then we can all quit the internet.</p>\n</div>',
  'inReplyTo': [{
    'id': 'tag:reddit.com:ezv3f2',
    'url': 'https://reddit.com/r/MachineLearning/comments/ezv3f2/p_gpt2_bert_reddit_replier_i_built_a_system_that/'
  }],
  'published': '2020-02-06T18:17:49Z',
  'to': [{'alias': '@public', 'objectType': 'group'}],
}

ACTIVITY_WITH_COMMENT = copy.deepcopy(ACTIVITY_WITH_SELFTEXT)
ACTIVITY_WITH_COMMENT['object']['replies'] = {
  'items': [COMMENT_OBJECT],
  'totalItems': 1,
}

MISSING_OBJECT = {}


class RedditTest(testutil.TestCase):

  def setUp(self):
    super(RedditTest, self).setUp()
    oauth_reddit.REDDIT_APP_KEY = oauth_reddit.REDDIT_APP_LOCAL = 'foo'
    self.reddit = reddit.Reddit('token-here')
    self.api = self.reddit.api = self.mox.CreateMockAnything(praw.Reddit)

    self.redditor = FakeRedditor()
    self.submission_selftext = FakeSubmission(self.redditor)
    self.comment = FakeComment(self.submission_selftext, self.redditor)

    self.submission_link = FakeSubmission(self.redditor)
    self.submission_link.selftext = ''
    self.submission_link.url = 'https://reddit.com/ezv3f2'

    reddit.user_cache.clear()

  def test_user_url(self):
    self.assert_equals('https://reddit.com/user/foo', self.reddit.user_url('foo'))

  def test_missing_to_as1_actor(self):
    self.assert_equals(MISSING_OBJECT,
                       self.reddit.praw_to_as1_actor(FakeMissingRedditor()))

  def test_suspended_to_as1_actor(self):
    suspended = util.Struct(name='mr_suspended', is_suspended=True)
    self.assert_equals(MISSING_OBJECT, self.reddit.praw_to_as1_actor(suspended))

  def test_praw_to_as1_actor(self):
    self.assert_equals(ACTOR, self.reddit.praw_to_as1_actor(self.redditor))

  def test_broken_praw_to_as1_actor(self):
    self.assert_equals(MISSING_OBJECT, self.reddit.praw_to_as1_actor(util.Struct()))

  def test_praw_to_as1_actor_no_subreddit(self):
    self.redditor.subreddit = None
    expected = copy.deepcopy(ACTOR)
    del expected['description']
    del expected['urls']
    expected['url'] = 'https://reddit.com/user/bonkerfield/'
    self.assert_equals(expected, self.reddit.praw_to_as1_actor(self.redditor))

  def test_praw_to_comment(self):
    self.assert_equals(COMMENT_OBJECT,
                       self.reddit.to_as1_object(self.comment, 'comment'))

  def test_broken_praw_to_comment(self):
    self.assert_equals(MISSING_OBJECT,
                       self.reddit.to_as1_object(util.Struct(), 'comment'))

  def test_submission_to_activity_with_link(self):
    self.assert_equals(
      ACTIVITY_WITH_LINK,
      self.reddit.to_as1_activity(self.submission_link, type='submission'))

  def test_submission_to_activity_with_selftext(self):
    self.assert_equals(
      ACTIVITY_WITH_SELFTEXT,
      self.reddit.to_as1_activity(self.submission_selftext, type='submission'))

  def test_broken_submission_to_object(self):
    self.assert_equals(MISSING_OBJECT,
                       self.reddit.to_as1_activity(util.Struct(), type='submission'))

  def test_post_id(self):
    self.assert_equals(
      'lhzukq',
      self.reddit.post_id('https://www.reddit.com/r/xyz/comments/lhzukq/abc/'))

  def test_get_activities_user_id(self):
    self.api.redditor('plfff').AndReturn(self.redditor)
    self.redditor.submissions = self.mox.CreateMock(SubListing)
    self.redditor.submissions.new(limit=None).AndReturn(
      [self.submission_selftext, self.submission_link])
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_WITH_SELFTEXT, ACTIVITY_WITH_LINK],
                       self.reddit.get_activities(user_id='plfff'))

  def test_get_activities_default_user(self):
    self.api.user = self.mox.CreateMock(User)
    self.api.user.me().AndReturn(self.redditor)
    self.redditor.submissions = self.mox.CreateMock(SubListing)
    self.redditor.submissions.new(limit=None).AndReturn(
      [self.submission_selftext, self.submission_link])
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_WITH_SELFTEXT, ACTIVITY_WITH_LINK],
                       self.reddit.get_activities())

  def test_get_activities_activity_id(self):
    self.api.submission(id='abc').AndReturn(self.submission_selftext)
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_WITH_SELFTEXT],
                       self.reddit.get_activities(activity_id='abc'))

  def test_get_activities_search_query(self):
    subreddit = self.mox.CreateMock(Subreddit)
    self.mox.StubOutWithMock(self.api, 'subreddit')
    self.api.subreddit('all').AndReturn(subreddit)
    subreddit.search('foo bar', sort='new', limit=None).AndReturn(
      [self.submission_selftext, self.submission_link])
    self.mox.ReplayAll()

    self.assert_equals([ACTIVITY_WITH_SELFTEXT, ACTIVITY_WITH_LINK],
                       self.reddit.get_activities(search_query='foo bar'))

  def test_get_activities_fetch_replies(self):
    self.api.submission(id='ezv3f2').MultipleTimes().AndReturn(self.submission_selftext)
    self.submission_selftext.comments = CommentForest(self.submission_selftext,
                                                      comments=[self.comment])
    self.mox.StubOutWithMock(self.submission_selftext.comments, 'replace_more')
    self.submission_selftext.comments.replace_more()
    self.mox.ReplayAll()

    self.assert_equals(
      [ACTIVITY_WITH_COMMENT],
      self.reddit.get_activities(activity_id='ezv3f2', fetch_replies=True))

  def test_get_activities_cache_comments(self):
    # get first_activities() call, fetches comments
    self.submission_selftext.num_comments = 1
    for _ in range(2):
      self.api.submission(id='ezv3f2').AndReturn(self.submission_selftext)

    comments = CommentForest(self.submission_selftext, comments=[self.comment])
    self.submission_selftext.comments = comments
    self.mox.StubOutWithMock(comments, 'replace_more')
    comments.replace_more()

    # second call, comment count is unchanged, skips comment fetch
    for _ in range(2):
      self.api.submission(id='ezv3f2').AndReturn(self.submission_selftext)

    # third call, comment count is different, skips comment fetch
    other_sub = FakeSubmission(self.redditor)
    other_sub.num_comments = 2
    other_sub.comments = comments
    for _ in range(2):
      self.api.submission(id='ezv3f2').AndReturn(other_sub)
    comments.replace_more()

    # fourth call, comment count is unchanged, skips comment fetch
    for _ in range(2):
      self.api.submission(id='ezv3f2').AndReturn(other_sub)

    self.mox.ReplayAll()
    cache = {}
    for num_comments in (1, 2):
      # not cached
      self.assert_equals(
        [ACTIVITY_WITH_COMMENT],
        self.reddit.get_activities(activity_id='ezv3f2', fetch_replies=True, cache=cache))
      self.assert_equals(num_comments, cache['ARR ezv3f2'])

      # not cached
      self.assert_equals(
        [ACTIVITY_WITH_SELFTEXT],
        self.reddit.get_activities(activity_id='ezv3f2', fetch_replies=True, cache=cache))
      self.assert_equals(num_comments, cache['ARR ezv3f2'])

  def test_get_comment(self):
    self.api.comment(id='xyz').AndReturn(self.comment)
    self.mox.ReplayAll()

    self.assert_equals(COMMENT_OBJECT, self.reddit.get_comment('xyz'))

  def test_get_actor(self):
    self.api.redditor('schnarfed').AndReturn(self.redditor)
    self.mox.ReplayAll()

    self.assert_equals(ACTOR, self.reddit.get_actor('schnarfed'))

  def test_get_actor_missing(self):
    self.api.redditor('schnarfed').AndReturn(self.comment)
    self.mox.ReplayAll()

    self.assert_equals(MISSING_OBJECT, self.reddit.get_actor('schnarfed'))
