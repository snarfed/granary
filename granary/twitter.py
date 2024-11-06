"""Twitter source class.

Uses the v1.1 REST API: https://developer.twitter.com/en/docs/api-reference-index

The Audience Targeting ``to`` field is set to ``@public`` or ``@private`` based
on whether the tweet author's ``protected`` field is true or false.
https://dev.twitter.com/docs/platform-objects/users

"""
import collections
import datetime
import http.client
import itertools
import logging
import mimetypes
import re
import socket
import time
import urllib.parse, urllib.request

from oauth_dropins import twitter_auth
from oauth_dropins.webutil import util
from oauth_dropins.webutil.util import json_dumps, json_loads
from requests import RequestException

from . import as1
from . import source

logger = logging.getLogger(__name__)

# common to all API calls that fetch tweets
API_TWEET_PARAMS = '&include_entities=true&tweet_mode=extended&include_ext_alt_text=true'

API_BASE = 'https://api.twitter.com/1.1/'
API_BLOCK_IDS = 'blocks/ids.json?count=5000&stringify_ids=true&cursor=%s'
API_BLOCKS = 'blocks/list.json?skip_status=true&count=5000&cursor=%s'
API_CURRENT_USER = 'account/verify_credentials.json'
API_DELETE_TWEET = 'statuses/destroy.json'
API_DELETE_FAVORITE = 'favorites/destroy.json'
API_FAVORITES = 'favorites/list.json?screen_name=%s'
API_LIST_TIMELINE = 'lists/statuses.json?count=%(count)d&slug=%(slug)s&owner_screen_name=%(owner_screen_name)s' + API_TWEET_PARAMS
API_LIST_ID_TIMELINE = 'lists/statuses.json?count=%(count)d&list_id=%(list_id)s' + API_TWEET_PARAMS
API_LOOKUP = 'statuses/lookup.json?id=%s' + API_TWEET_PARAMS
API_POST_FAVORITE = 'favorites/create.json'
API_POST_MEDIA = 'statuses/update_with_media.json'
API_POST_RETWEET = 'statuses/retweet/%s.json'
API_POST_TWEET = 'statuses/update.json'
API_RETWEETS = 'statuses/retweets.json?id=%s' + API_TWEET_PARAMS
API_SEARCH = 'search/tweets.json?q=%(q)s&result_type=recent&count=%(count)d' + API_TWEET_PARAMS
API_STATUS = 'statuses/show.json?id=%s' + API_TWEET_PARAMS
API_TIMELINE = 'statuses/home_timeline.json?count=%d' + API_TWEET_PARAMS
API_UPLOAD_MEDIA = 'https://upload.twitter.com/1.1/media/upload.json'
API_MEDIA_STATUS_MAX_DELAY_SECS = 30
API_MEDIA_STATUS_MAX_POLLS = 20
API_MEDIA_METADATA = 'https://upload.twitter.com/1.1/media/metadata/create.json'
API_USER = 'users/show.json?screen_name=%s'
API_USER_TIMELINE = 'statuses/user_timeline.json?count=%(count)d&screen_name=%(screen_name)s' + API_TWEET_PARAMS
SCRAPE_LIKES_URL = 'https://api.twitter.com/2/timeline/liked_by.json?tweet_mode=extended&include_user_entities=true&tweet_id=%s&count=80'

TWEET_URL_RE = re.compile(r'https://twitter\.com/[^/?]+/status(es)?/[^/?]+$')
HTTP_RATE_LIMIT_CODES = (429, 503)

# Don't hit the RETWEETS endpoint more than this many times per
# get_activities() call.
# https://dev.twitter.com/docs/rate-limiting/1.1/limits
# TODO: sigh. figure out a better way. dammit twitter, give me a batch API!!!
RETWEET_LIMIT = 15

# Number of IDs to search for at a time
QUOTE_SEARCH_BATCH_SIZE = 20

# For read requests only.
RETRIES = 3

# Config constants, as of 2017-11-08:
# * Current max tweet length and expected length of a t.co URL.
#   https://twittercommunity.com/t/updating-the-character-limit-and-the-twitter-text-library/96425
#   https://dev.twitter.com/docs/tco-link-wrapper/faq
# * Max media per tweet.
#   https://dev.twitter.com/rest/reference/post/statuses/update#api-param-media_ids
# * Allowed image formats:
#   https://dev.twitter.com/rest/media/uploading-media#imagerecs
# * Allowed video formats, max video size, and upload chunk size:
#   https://dev.twitter.com/rest/public/uploading-media#keepinmind
# * Max alt text length.
#   https://developer.twitter.com/en/docs/media/upload-media/api-reference/opst-media-metadata-create
#
# Update by running help/configuration.json manually in
# https://apigee.com/embed/console/twitter
#
# TODO: pull these from /help/configuration.json instead (except max tweet length)
# https://developer.twitter.com/en/docs/developer-utilities/configuration/api-reference/get-help-configuration
MAX_TWEET_LENGTH = 280
TCO_LENGTH = 23
MAX_MEDIA = 4
IMAGE_MIME_TYPES = frozenset(('image/jpg', 'image/jpeg', 'image/png',
                              'image/gif', 'image/webp',))
VIDEO_MIME_TYPES = frozenset(('video/mp4',))
MB = 1024 * 1024
# https://developer.twitter.com/en/docs/media/upload-media/uploading-media/media-best-practices
MAX_IMAGE_SIZE = 5 * MB
MAX_VIDEO_SIZE = 512 * MB
UPLOAD_CHUNK_SIZE = 5 * MB
MAX_ALT_LENGTH = 420

# username requirements and limits:
# https://support.twitter.com/articles/101299#error
# http://stackoverflow.com/a/13396934/186123
USERNAME = r'\w{1,15}'
USERNAME_RE = re.compile(USERNAME + '$')
MENTION_RE = re.compile(r'(^|[^\w@/\!?=&])@(' + USERNAME + r')\b', re.UNICODE)

# alias allows unit tests to mock this function
sleep_fn = time.sleep


class OffsetTzinfo(datetime.tzinfo):
  """A simple, DST-unaware tzinfo from given utc offset in seconds.
  """
  def __init__(self, utc_offset=0):
    """Constructor.

    Args:
      utc_offset: Offset of time zone from UTC in seconds
    """
    self._offset = datetime.timedelta(seconds=utc_offset)

  def utcoffset(self, dt):
    return self._offset

  def dst(self, dt):
    return datetime.timedelta(0)


class Twitter(source.Source):
  """Twitter source class. See file docstring and :class:`Source` for details."""

  DOMAIN = 'twitter.com'
  BASE_URL = 'https://twitter.com/'
  NAME = 'Twitter'
  FRONT_PAGE_TEMPLATE = 'templates/twitter_index.html'
  POST_ID_RE = re.compile('^[0-9]+$')
  OPTIMIZED_COMMENTS = True

  # HTML snippet for embedding a tweet.
  # https://dev.twitter.com/docs/embedded-tweets
  EMBED_POST = """
  <script async defer src="//platform.twitter.com/widgets.js" charset="utf-8"></script>
  <br />
  <blockquote class="twitter-tweet" lang="en" data-dnt="true">
  <p>%(content)s
  <a href="%(url)s">#</a></p>
  </blockquote>
  """

  URL_CANONICALIZER = util.UrlCanonicalizer(
    domain=DOMAIN,
    approve=TWEET_URL_RE,
    reject=r'https://twitter\.com/.+\?protected_redirect=true')

  # These use the Twitter-based defaults in Source.truncate() (and brevity).
  # TRUNCATE_TEXT_LENGTH = None
  # TRUNCATE_URL_LENGTH = None

  def __init__(self, access_token_key, access_token_secret, username=None,
               scrape_headers=None):
    """Constructor.

    Twitter now requires authentication in v1.1 of their API. You can get an
    OAuth access token by creating an app here: https://dev.twitter.com/apps/new

    Args:
      access_token_key (str): OAuth access token key
      access_token_secret (str): OAuth access token secret
      username (str): optional, the current user. Used in e.g. preview/create.
      scrape_headers (dict): optional, with string HTTP header keys and values to
        use when scraping likes
    """
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret
    self.username = username
    self.scrape_headers = scrape_headers

  def get_actor(self, screen_name=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      screen_name (str): username. Defaults to the current user.
    """
    url = API_CURRENT_USER if screen_name is None else API_USER % screen_name
    return self.to_as1_actor(self.urlopen(url))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, include_shares=True,
                              fetch_events=False, fetch_mentions=False,
                              search_query=None, scrape=False, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    See :meth:`source.Source.get_activities_response` for details. ``app_id``
    is ignored. ``min_id`` is translated to Twitter's ``since_id``.

    The code for handling ETags (and 304 Not Changed responses and setting
    ``If-None-Match``) is here, but unused right now since Twitter evidently
    doesn't support ETags. From https://dev.twitter.com/discussions/5800 : "I've
    confirmed with our team that we're not explicitly supporting this family of
    features."

    Likes (nee favorites) are scraped from twitter.com, since Twitter's REST API
    doesn't offer a way to fetch them. You can also get them from the Streaming
    API, though, and convert them with :meth:`streaming_event_to_object`.
    https://dev.twitter.com/docs/streaming-apis/messages#Events_event

    Shares (ie retweets) are fetched with a separate API call per tweet:
    https://dev.twitter.com/docs/api/1.1/get/statuses/retweets/%3Aid

    However, retweets are only fetched for the first 15 tweets that have them,
    since that's Twitter's rate limit per 15 minute window. :(
    https://dev.twitter.com/docs/rate-limiting/1.1/limits

    Quote tweets are fetched by searching for the possibly quoted tweet's ID,
    using the OR operator to search up to 5 IDs at a time, and then checking
    the ``quoted_status_id_str`` field:
    https://dev.twitter.com/overview/api/tweets#quoted_status_id_str

    Use the group_id @self to retrieve a user_id’s timeline. If ``user_id`` is
    None or ``@me``, it will return tweets for the current API user.

    group_id can be used to specify the slug of a list for which to return tweets.
    By default the current API user’s lists will be used, but lists owned by other
    users can be fetched by explicitly passing a username to ``user_id``, e.g. to
    fetch tweets from the list ``@exampleuser/example-list`` you would call
    ``get_activities(user_id='exampleuser', group_id='example-list')``.

    Twitter replies default to including a mention of the user they're replying
    to, which overloads mentions a bit. When fetch_mentions is True, we determine
    that a tweet mentions the current user if it @-mentions their username and:

    * it's not a reply, OR
    * it's a reply, but not to the current user, AND
    * the tweet it's replying to doesn't @-mention the current user

    Raises:
      NotImplementedError: if ``fetch_likes`` is True but ``scrape_headers`` was not
        provided to the constructor.

    XXX HACK: this is currently hacked for Bridgy to NOT pass ``min_id`` to the
    request for fetching activity tweets themselves, but to pass it to all of
    the requests for filling in replies, retweets, etc. That's because we want
    to find new replies and retweets of older initial tweets.
    TODO: find a better way.

    """
    if fetch_likes and not self.scrape_headers:
        raise NotImplementedError('fetch_likes requires scrape_headers')

    if group_id is None:
      group_id = source.FRIENDS

    if user_id:
      if user_id.startswith('@'):
        user_id = user_id[1:]
      if not USERNAME_RE.match(user_id):
        raise ValueError(f'Invalid Twitter username: {user_id}')

    # nested function for lazily fetching the user object if we need it
    user = []

    def _user():
      if not user:
        user.append(self.urlopen(API_USER % user_id if user_id else API_CURRENT_USER))
      return user[0]

    if count:
      count += start_index

    activities = []
    if activity_id:
      self._validate_id(activity_id)
      tweets = [self.urlopen(API_STATUS % int(activity_id))]
      total_count = len(tweets)
    else:
      if group_id == source.SELF:
        if user_id in (None, source.ME):
          user_id = ''
        url = API_USER_TIMELINE % {
          'count': count,
          'screen_name': user_id,
        }

        if fetch_likes:
          liked = self.urlopen(API_FAVORITES % user_id)
          if liked:
            activities += [self._make_like(tweet, _user()) for tweet in liked]
      elif group_id == source.SEARCH:
        if not search_query:
          raise ValueError('search requires search_query parameter')
        url = API_SEARCH % {
          'q': urllib.parse.quote_plus(search_query.encode('utf-8')),
          'count': count,
        }
      elif group_id in (source.FRIENDS, source.ALL):
        url = API_TIMELINE % (count)
      else:
        if util.is_int(group_id):
          # it's a list id
          url = API_LIST_ID_TIMELINE % {
            'count': count,
            'list_id': group_id,
          }
        else:
          # it's a list slug
          if not user_id:
            user_id = _user().get('screen_name')
          url = API_LIST_TIMELINE % {
            'count': count,
            'slug': urllib.parse.quote(group_id),
            'owner_screen_name': user_id,
          }

      headers = {'If-None-Match': etag} if etag else {}
      total_count = None
      try:
        resp = self.urlopen(url, headers=headers, parse_response=False)
        etag = resp.info().get('ETag')
        tweet_obj = source.load_json(resp.read(), url)
        if group_id == source.SEARCH:
          tweet_obj = tweet_obj.get('statuses', [])
        tweets = tweet_obj[start_index:]
      except urllib.error.HTTPError as e:
        if e.code == 304:  # Not Modified, from a matching ETag
          tweets = []
        else:
          raise

    if cache is None:
      # for convenience, throwaway object just for this method
      cache = {}

    if fetch_shares:
      retweet_calls = 0
      for tweet in tweets:
        # don't fetch retweets if the tweet is itself a retweet or if the
        # author's account is protected. /statuses/retweets 403s with error
        # code 200 (?!) for protected accounts.
        # https://github.com/snarfed/bridgy/issues/688
        if tweet.get('retweeted') or tweet.get('user', {}).get('protected'):
          continue
        elif retweet_calls >= RETWEET_LIMIT:
          logger.warning(f"Hit Twitter's retweet rate limit ({RETWEET_LIMIT}) with more to fetch! Results will be incomplete!")
          break

        # store retweets in the 'retweets' field, which is handled by
        # tweet_to_activity().
        # TODO: make these HTTP requests asynchronous. not easy since we don't
        # (yet) require threading support or use a non-blocking HTTP library.
        #
        # twitter limits this API endpoint to one call per minute per user,
        # which is easy to hit, so we stop before we hit that.
        # https://dev.twitter.com/docs/rate-limiting/1.1/limits
        #
        # can't use the statuses/retweets_of_me endpoint because it only
        # returns the original tweets, not the retweets or their authors.
        id = tweet['id_str']
        count = tweet.get('retweet_count')
        if count and count != cache.get('ATR ' + id):
          url = API_RETWEETS % id
          if min_id is not None:
            url = util.add_query_params(url, {'since_id': min_id})

          try:
            tweet['retweets'] = self.urlopen(url)
          except urllib.error.URLError as e:
            code, body = util.interpret_http_exception(e)
            try:
              # duplicates code in interpret_http_exception :(
              error_code = json_loads(body).get('errors')[0].get('code')
            except BaseException:
              error_code = None
            if not (code == '404' or  # tweet was deleted
                    (code == '403' and error_code == 200)):  # tweet is protected?
              raise

          retweet_calls += 1
          cache['ATR ' + id] = count

    if not include_shares:
      tweets = [t for t in tweets if not t.get('retweeted_status')]

    tweet_activities = [self.tweet_to_activity(t) for t in tweets]

    if fetch_replies:
      self.fetch_replies(tweet_activities, min_id=min_id)

    if fetch_mentions:
      # fetch mentions *after* replies so that we don't get replies to mentions
      # https://github.com/snarfed/bridgy/issues/631
      mentions = self.fetch_mentions(_user().get('screen_name'), tweets,
                                     min_id=min_id)
      tweet_activities += [self.tweet_to_activity(m) for m in mentions]

    if fetch_likes:
      for tweet, activity in zip(tweets, tweet_activities):
        id = tweet['id_str']
        count = tweet.get('favorite_count')
        if as1.is_public(activity) and count and count != cache.get('ATF ' + id):
          try:
            resp = util.requests_get(SCRAPE_LIKES_URL % id,
                                     headers=self.scrape_headers)
            resp.raise_for_status()
          except RequestException as e:
            util.interpret_http_exception(e)  # just log it
            continue

          likes = [self._make_like(tweet, author) for author in
                   resp.json().get('globalObjects', {}).get('users', {}).values()]
          activity['object'].setdefault('tags', []).extend(likes)
          cache['ATF ' + id] = count

    activities += tweet_activities
    response = self.make_activities_base_response(activities)
    response.update({'total_count': total_count, 'etag': etag})
    return response

  def fetch_replies(self, activities, min_id=None):
    """Fetches and injects Twitter replies into a list of activities, in place.

    Includes indirect replies ie reply chains, not just direct replies. Searches
    for @-mentions, matches them to the original tweets with
    ``in_reply_to_status_id_str``, and recurses until it's walked the entire
    tree.

    Args:
      activities (list of dict)

    Returns:
      list of dict: same activities
    """

    # cache searches for @-mentions for individual users. maps username to dict
    # mapping tweet id to ActivityStreams reply object dict.
    mentions = {}

    # find replies
    for activity in activities:
      # list of ActivityStreams reply object dict and set of seen activity ids
      # (tag URIs). seed with the original tweet; we'll filter it out later.
      replies = [activity]
      _, id = util.parse_tag_uri(activity['id'])
      seen_ids = set([id])

      for reply in replies:
        # get mentions of this tweet's author so we can search them for replies to
        # this tweet. can't use statuses/mentions_timeline because i'd need to
        # auth as the user being mentioned.
        # https://dev.twitter.com/docs/api/1.1/get/statuses/mentions_timeline
        #
        # note that these HTTP requests are synchronous. you can make async
        # requests by using urlfetch.fetch() directly, but not with urllib2.
        # https://developers.google.com/appengine/docs/python/urlfetch/asynchronousrequests
        author = reply['actor']['username']
        if author not in mentions:
          url = API_SEARCH % {
            'q': urllib.parse.quote_plus('@' + author),
            'count': 100,
          }
          if min_id is not None:
            url = util.add_query_params(url, {'since_id': min_id})
          mentions[author] = self.urlopen(url)['statuses']

        # look for replies. add any we find to the end of replies. this makes us
        # recursively follow reply chains to their end. (python supports
        # appending to a sequence while you're iterating over it.)
        for mention in mentions[author]:
          id = mention['id_str']
          if (mention.get('in_reply_to_status_id_str') in seen_ids and
              id not in seen_ids):
            replies.append(self.tweet_to_activity(mention))
            seen_ids.add(id)

      items = [r['object'] for r in replies[1:]]  # filter out seed activity
      activity['object']['replies'] = {
        'items': items,
        'totalItems': len(items),
      }

  def fetch_mentions(self, username, tweets, min_id=None):
    """Fetches a user's @-mentions and returns them as ActivityStreams.

    Tries to only include explicit mentions, not mentions automatically created
    by @-replying. See :meth:`get_activities_response` for details.

    Args:
      username (str)
      tweets (list): of Twitter API objects. used to find quote tweets quoting them.
      min_id (str): only return activities with ids greater than this

    Returns:
      list of dict: activities
    """
    # get @-name mentions
    url = API_SEARCH % {
      'q': urllib.parse.quote_plus('@' + username),
      'count': 100,
    }
    if min_id is not None:
      url = util.add_query_params(url, {'since_id': min_id})
    candidates = self.urlopen(url)['statuses']

    # fetch in-reply-to tweets (if any)
    in_reply_to_ids = util.trim_nulls(
      [c.get('in_reply_to_status_id_str') for c in candidates])
    origs = {
      o.get('id_str'): o for o in
      self.urlopen(API_LOOKUP % ','.join(in_reply_to_ids))
    } if in_reply_to_ids else {}

    # filter out tweets that we don't consider mentions
    mentions = []
    for c in candidates:
      if (c.get('user', {}).get('screen_name') == username or
          c.get('retweeted_status')):
        continue
      reply_to = origs.get(c.get('in_reply_to_status_id_str'))
      if not reply_to:
        mentions.append(c)
      else:
        reply_to_user = reply_to.get('user', {}).get('screen_name')
        mentioned = [u.get('screen_name') for u in
                     reply_to.get('entities', {}).get('user_mentions', [])]
        if username != reply_to_user and username not in mentioned:
          mentions.append(c)

    # search for quote tweets
    # Guideline ("Limit your searches to 10 keywords and operators.")
    # implies fewer, but 20 IDs seems to work in practice.
    # https://dev.twitter.com/rest/public/search
    for batch in [
        tweets[i:i + QUOTE_SEARCH_BATCH_SIZE]
        for i in range(0, len(tweets), QUOTE_SEARCH_BATCH_SIZE)
    ]:
      batch_ids = [t['id_str'] for t in batch]
      url = API_SEARCH % {
        'q': urllib.parse.quote_plus(' OR '.join(batch_ids)),
        'count': 100,
      }
      if min_id is not None:
        url = util.add_query_params(url, {'since_id': min_id})
      candidates = self.urlopen(url)['statuses']
      for c in candidates:
        quoted_status_id = c.get('quoted_status_id_str')
        if (quoted_status_id and quoted_status_id in batch_ids and
            not c.get('retweeted_status')):
          mentions.append(c)

    return mentions

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id (str): comment id
      activity_id (str): activity id, optional
      activity_author_id (str): activity author id; ignored
      activity (dict): original object, optional
    """
    self._validate_id(comment_id)
    url = API_STATUS % comment_id
    return self.tweet_to_as1_object(self.urlopen(url))

  def get_share(self, activity_user_id, activity_id, share_id, activity=None):
    """Returns an ActivityStreams 'share' activity object.

    Args:
      activity_user_id (str): id of the user who posted the original activity
      activity_id (str): activity id
      share_id (str): id of the share object
      activity (dict): original object, optional
    """
    self._validate_id(share_id)
    url = API_STATUS % share_id
    return self.retweet_to_as1(self.urlopen(url))

  def get_blocklist(self):
    """Returns the current user's block list.

    May make multiple API calls, using cursors, to fully fetch large blocklists.
    https://dev.twitter.com/overview/api/cursoring

    Block lists may have up to 10k users, but each API call only returns 100 at
    most, and the API endpoint is rate limited to 15 calls per user per 15m. So
    if a user has >1500 users on their block list, we can't get the whole thing
    at once. :(

    Returns:
      list of dict: actors

    Raises:
      source.RateLimited: if we hit the rate limit. The partial attribute will
      have the list of user ids we fetched before hitting the limit.
    """
    return self._get_blocklist_fn(API_BLOCKS,
        lambda resp: (self.to_as1_actor(user) for user in resp.get('users', [])))

  def get_blocklist_ids(self):
    """Returns the current user's block list as a list of Twitter user ids.

    May make multiple API calls, using cursors, to fully fetch large blocklists.
    https://dev.twitter.com/overview/api/cursoring

    Subject to the same rate limiting as :meth:`get_blocklist`, but each API
    call returns ~4k ids, so realistically this can actually fetch blocklists of
    up to 75k users at once. Beware though, many Twitter users have even more!

    Returns:
      sequence of str: Twitter user ids

    Raises:
      source.RateLimited: if we hit the rate limit. The partial attribute will
      have the list of user ids we fetched before hitting the limit.
    """
    return self._get_blocklist_fn(API_BLOCK_IDS, lambda resp: resp.get('ids', []))

  def _get_blocklist_fn(self, api_endpoint, response_fn):
    values = []
    cursor = '-1'
    while cursor and cursor != '0':
      try:
        resp = self.urlopen(api_endpoint % cursor)
      except urllib.error.HTTPError as e:
        if e.code in HTTP_RATE_LIMIT_CODES:
          raise source.RateLimited(str(e), partial=values)
        raise
      values.extend(response_fn(resp))
      cursor = resp.get('next_cursor_str')

    return values

  def create(self, obj, include_link=source.OMIT_LINK,
             ignore_formatting=False):
    """Creates a tweet, reply tweet, retweet, or favorite.

    Args:
      obj (dict): ActivityStreams object
      include_link (str)
      ignore_formatting(bool):

    Returns:
      CreationResult: content will be a dict with ``id``, ``url``, and ``type``
      keys (all optional) for the newly created Twitter object (or None)
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Previews creating a tweet, reply tweet, retweet, or favorite.

    Args:
      obj: ActivityStreams object
      include_link (str):
      ignore_formatting (bool):

    Returns:
      CreationResult or None: content will be an HTML snippet
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates or previews creating a tweet, reply tweet, retweet, or favorite.

    * https://dev.twitter.com/docs/api/1.1/post/statuses/update
    * https://dev.twitter.com/docs/api/1.1/post/statuses/retweet/:id
    * https://dev.twitter.com/docs/api/1.1/post/favorites/create

    Args:
      obj (dict): ActivityStreams object
      preview (bool)
      include_link (str)
      ignore_formatting (bool)

    Returns:
      CreationResult: If ``preview`` is True, ``content`` will be an HTML
      snippet. If False, it will be a dict with ``id`` and ``url`` keys for the
      newly created Twitter object.
    """
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')

    base_obj = self.base_object(obj)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')

    is_reply = type == 'comment' or 'inReplyTo' in obj
    is_rsvp = (verb and verb.startswith('rsvp-')) or verb == 'invite'
    images = util.get_list(obj, 'image')
    video_url = util.get_first(obj, 'stream', {}).get('url')
    has_media = (images or video_url) and (type in ('note', 'article') or is_reply)
    lat = obj.get('location', {}).get('latitude')
    lng = obj.get('location', {}).get('longitude')

    # prefer displayName over content for articles
    type = obj.get('objectType')
    prefer_content = type == 'note' or (base_url and (type == 'comment'
                                                      or obj.get('inReplyTo')))
    preview_description = ''
    quote_tweet_url = None
    for att in obj.get('attachments', []):
      url = self.URL_CANONICALIZER(att.get('url', ''))
      if url and TWEET_URL_RE.match(url):
        quote_tweet_url = url
        preview_description += f"""<span class="verb">quote</span>
<a href="{url}">this tweet</a>:<br>
{self.embed_post(att)}
<br>and """
        break

    content = self._content_for_create(
      obj, ignore_formatting=ignore_formatting, prefer_name=not prefer_content,
      strip_first_video_tag=bool(video_url), strip_quotations=bool(quote_tweet_url))

    if not content:
      if type == 'activity' and not is_rsvp:
        content = verb
      elif has_media:
        content = ''
      else:
        return source.creation_result(
          abort=False,  # keep looking for things to publish,
          error_plain='No content text found.',
          error_html='No content text found.')

    if is_reply and base_url:
      # Twitter *used* to require replies to include an @-mention of the
      # original tweet's author
      # https://dev.twitter.com/docs/api/1.1/post/statuses/update#api-param-in_reply_to_status_id
      # ...but now we use the auto_populate_reply_metadata query param instead:
      # https://dev.twitter.com/overview/api/upcoming-changes-to-tweets

      # the embed URL in the preview can't start with mobile. or www., so just
      # hard-code it to twitter.com. index #1 is netloc.
      parsed = urllib.parse.urlparse(base_url)
      parts = parsed.path.split('/')
      if len(parts) < 2 or not parts[1]:
        raise ValueError(f'Could not determine author of in-reply-to URL {base_url}')
      reply_to_prefix = f'@{parts[1].lower()} '
      if content.lower().startswith(reply_to_prefix):
        content = content[len(reply_to_prefix):]

      parsed = list(parsed)
      parsed[1] = self.DOMAIN
      base_url = urllib.parse.urlunparse(parsed)

    # need a base_url with the tweet id for the embed HTML below. do this
    # *after* checking the real base_url for in-reply-to author username.
    if base_id and not base_url:
      base_url = 'https://twitter.com/-/statuses/' + base_id

    # truncate and ellipsize content if it's over the character
    # count. URLs will be t.co-wrapped, so include that when counting.
    content = self.truncate(content, obj.get('url'), include_link, type=type,
                            quote_url=quote_tweet_url)

    # linkify defaults to Twitter's link shortening behavior
    preview_content = util.linkify(content, pretty=True, skip_bare_cc_tlds=True)
    preview_content = MENTION_RE.sub(
      r'\1<a href="https://twitter.com/\2">@\2</a>', preview_content)
    # Twitter hashtag details:
    # https://support.twitter.com/articles/370610
    # http://stackoverflow.com/questions/8451846
    preview_content = as1.HASHTAG_RE.sub(
      r'\1<a href="https://twitter.com/hashtag/\2">#\2</a>', preview_content)

    if type == 'activity' and verb in ('like', 'favorite'):
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a tweet to like.',
          error_html='Could not find a tweet to <a href="http://indiewebcamp.com/like">like</a>. '
          'Check that your post has a like-of link to a Twitter URL or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

      if preview:
        preview_description += f"""<span class="verb">like</span>
<a href="{base_url}">this tweet</a>:
{self.embed_post(base_obj)}"""
        return source.creation_result(description=preview_description)
      else:
        data = urllib.parse.urlencode({'id': base_id})
        self.urlopen(API_POST_FAVORITE, data=data)
        resp = {'type': 'like'}

    elif type == 'activity' and verb == 'share':
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a tweet to retweet.',
          error_html='Could not find a tweet to <a href="http://indiewebcamp.com/repost">retweet</a>. '
          'Check that your post has a repost-of link to a Twitter URL or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

      if preview:
          preview_description += f"""<span class="verb">retweet</span>
<a href="{base_url}">this tweet</a>:
{self.embed_post(base_obj)}"""
          return source.creation_result(description=preview_description)
      else:
        data = urllib.parse.urlencode({'id': base_id})
        resp = self.urlopen(API_POST_RETWEET % base_id, data=data)
        resp['type'] = 'repost'

    elif (type in ('note', 'article') or is_reply or is_rsvp or
          (type == 'activity' and verb == 'post')):  # probably a bookmark
      content = str(content).encode('utf-8')
      data = [('status', content)]

      if is_reply and base_url:
        preview_description += f"""<span class="verb">@-reply</span> to <a href="{base_url}">this tweet</a>:
{self.embed_post(base_obj)}"""
        data.extend([
          ('in_reply_to_status_id', base_id),
          ('auto_populate_reply_metadata', 'true'),
        ])
      else:
        preview_description += '<span class="verb">tweet</span>:'

      if video_url:
        preview_content += f'<br /><br /><video controls src="{video_url}"><a href="{video_url}">this video</a></video>'
        if not preview:
          ret = self.upload_video(video_url)
          if isinstance(ret, source.CreationResult):
            return ret
          data.append(('media_ids', ret))

      elif images:
        num = len(images)
        if num > MAX_MEDIA:
          images = images[:MAX_MEDIA]
          logger.warning(f'Found {num} photos! Only using the first {MAX_MEDIA}: {images}')
        preview_content += '<br /><br />' + ' &nbsp; '.join(
          f"<img src=\"{img.get('url')}\" alt=\"{util.ellipsize(img.get('displayName', ''), words=1000, chars=MAX_ALT_LENGTH)}\" />"
                                         for img in images)
        if not preview:
          ret = self.upload_images(images)
          if isinstance(ret, source.CreationResult):
            return ret
          data.append(('media_ids', ','.join(ret)))

      if lat and lng:
        preview_content += (
          f'<div>at <a href="https://maps.google.com/maps?q={lat},{lng}">{lat}, {lng}</a></div>')
        data.extend([
          ('lat', lat),
          ('long', lng),
        ])

      if preview:
        return source.creation_result(content=preview_content,
                                      description=preview_description)
      resp = self.urlopen(API_POST_TWEET, data=urllib.parse.urlencode(sorted(data)))
      resp['type'] = 'comment' if is_reply and base_url else 'post'

    else:
      return source.creation_result(
        abort=False,
        error_plain=f'Cannot publish type={type}, verb={verb} to Twitter',
        error_html=f'Cannot publish type={type}, verb={verb} to Twitter')

    id_str = resp.get('id_str')
    if id_str:
      resp.update({'id': id_str, 'url': self.tweet_url(resp)})
    elif 'url' not in resp:
      resp['url'] = base_url

    return source.creation_result(resp)

  def upload_images(self, images):
    """Uploads one or more images from web URLs.

    https://dev.twitter.com/rest/reference/post/media/upload

    Note that files and JSON bodies in media POST API requests are *not*
    included in OAuth signatures.
    https://developer.twitter.com/en/docs/media/upload-media/uploading-media/media-best-practices

    Args:
      images (sequence of dict): AS image objects, eg::

          [{'url': 'http://picture', 'displayName': 'a thing'}, ...]

    Returns:
      list of str, or CreationResult on error: media ids
    """
    ids = []
    for image in images:
      url = image.get('url')
      if not url:
        continue

      image_resp = util.urlopen(url)
      error = self._check_media(url, image_resp, IMAGE_MIME_TYPES,
                                'JPG, PNG, GIF, and WEBP images', MAX_IMAGE_SIZE)
      if error:
        return error

      headers = twitter_auth.auth_header(
        API_UPLOAD_MEDIA, self.access_token_key, self.access_token_secret, 'POST')
      resp = util.requests_post(API_UPLOAD_MEDIA,
                                files={'media': image_resp},
                                headers=headers)
      resp.raise_for_status()
      logger.debug(f'Got: {resp.text}')
      media_id = source.load_json(resp.text, API_UPLOAD_MEDIA)['media_id_string']
      ids.append(media_id)

      alt = image.get('displayName')
      if alt:
        alt = util.ellipsize(alt, words=1000, chars=MAX_ALT_LENGTH)
        headers = twitter_auth.auth_header(
          API_MEDIA_METADATA, self.access_token_key, self.access_token_secret, 'POST')
        resp = util.requests_post(
          API_MEDIA_METADATA,
          json={'media_id': media_id, 'alt_text': {'text': alt}},
          headers=headers)
        resp.raise_for_status()
        logger.debug(f'Got: {resp.text}')

    return ids

  def upload_video(self, url):
    """Uploads a video from a web URL using the chunked upload process.

    Chunked upload consists of multiple API calls:

    * ``command=INIT``, which allocates the media id
    * ``command=APPEND`` for each 5MB block, up to 15MB total
    * ``command=FINALIZE``
    * ``command=STATUS`` to wait until Twitter finishes processing the video

    https://developer.twitter.com/en/docs/media/upload-media/uploading-media/chunked-media-upload

    Args:
      url (str): URL of video

    Returns:
      str, or CreationResult on error: media id
    """
    video_resp = util.urlopen(url)
    error = self._check_media(url, video_resp, VIDEO_MIME_TYPES, 'MP4 videos',
                              MAX_VIDEO_SIZE)
    if error:
      return error

    # INIT
    media_id = self.urlopen(API_UPLOAD_MEDIA, data=urllib.parse.urlencode({
      'command': 'INIT',
      'media_type': 'video/mp4',
      # https://twittercommunity.com/t/large-file-can-not-be-finalized-synchronously/82929/3
      'media_category': 'tweet_video',
      # _check_media checked that Content-Length is set
      'total_bytes': video_resp.headers['Content-Length'],
    }))['media_id_string']

    # APPEND
    headers = twitter_auth.auth_header(
      API_UPLOAD_MEDIA, self.access_token_key, self.access_token_secret, 'POST')

    i = 0
    while True:
      chunk = util.FileLimiter(video_resp, UPLOAD_CHUNK_SIZE)
      data = {
        'command': 'APPEND',
        'media_id': media_id,
        'segment_index': i,
      }
      resp = util.requests_post(API_UPLOAD_MEDIA, data=data,
                                files={'media': chunk}, headers=headers)
      resp.raise_for_status()

      if chunk.ateof:
        break
      i += 1

    # FINALIZE
    resp = self.urlopen(API_UPLOAD_MEDIA, data=urllib.parse.urlencode({
      'command': 'FINALIZE',
      'media_id': media_id,
    }))

    total_delay = 0
    for _ in range(API_MEDIA_STATUS_MAX_POLLS):
      info = resp.get('processing_info', {})
      state = info.get('state')
      if not state or state == 'succeeded':
        return media_id
      elif state == 'failed':
        # TODO test
        return source.creation_result(abort=True, error_plain=str(info.get('error')))

      # STATUS
      delay = min(info.get('check_after_secs', 0),
                  API_MEDIA_STATUS_MAX_DELAY_SECS)
      total_delay += delay
      logger.info(f'video still processing, waiting {delay}s to check status')
      sleep_fn(delay)

      params = urllib.parse.urlencode({
        'command': 'STATUS',
        'media_id': media_id,
      })
      resp = self.urlopen(f'{API_UPLOAD_MEDIA}?{params}')

    msg = f'Twitter still processing uploaded video after {total_delay}s'
    return source.creation_result(abort=True, error_plain=msg)

  @staticmethod
  def _check_media(url, resp, types, label, max_size):
    """Checks that an image or video is an allowed type and size.

    Args:
      url (str):
      resp (urllib.response.addinfourl): :func:`urllib.request.urlopen`` response
      types (sequence of str): allowed str MIME types
      label (str): human-readable description of the allowed MIME types, to be
        used in an error message
      max_size (int): maximum allowed size, in bytes

    Returns:
      None or CreationResult: None if the url's type and size are valid,
      :class:`CreationResult` with ``abort=True`` otherwise
    """
    type = resp.headers.get('Content-Type')
    if not type:
      type, _ = mimetypes.guess_type(url)
    if type and type not in types:
      msg = f'Twitter only supports {label}; {util.pretty_link(url)} looks like {type}'
      return source.creation_result(abort=True, error_plain=msg, error_html=msg)

    length = resp.headers.get('Content-Length')
    if not util.is_int(length):
      msg = f"Couldn't determine the size of {util.pretty_link(url)}"
      return source.creation_result(abort=True, error_plain=msg, error_html=msg)

    length = int(length)
    if int(length) > max_size:
      msg = f"Your {length // MB:.2f}MB file is larger than Twitter's {max_size // MB}MB limit: {util.pretty_link(url)}"
      return source.creation_result(abort=True, error_plain=msg, error_html=msg)

  def delete(self, id):
    """Deletes a tweet. The authenticated user must have authored it.

    Args:
      id (int or str): tweet id to delete

    Returns:
      CreationResult: content is Twitter API response dict
    """
    resp = self.urlopen(API_DELETE_TWEET, data=urllib.parse.urlencode({'id': id}))
    return source.creation_result(resp)

  def preview_delete(self, id):
    """Previews deleting a tweet.

    Args:
      id (int or str): tweet id to delete

    Returns:
      CreationResult:
    """
    url = self.status_url(self.username or '_', id)
    return source.creation_result(description=f"""<span class="verb">delete</span>
<a href="{url}">this tweet</a>:
{self.embed_post({'url': url})}""")

  def urlopen(self, url, parse_response=True, **kwargs):
    """Wraps :func:`urllib.request.urlopen` and adds an OAuth signature."""
    if not url.startswith('http'):
      url = API_BASE + url

    def request():
      resp = twitter_auth.signed_urlopen(
        url, self.access_token_key, self.access_token_secret, **kwargs)
      return source.load_json(resp.read(), url) if parse_response else resp

    if ('data' not in kwargs and not
        (isinstance(url, urllib.request.Request) and url.get_method() == 'POST')):
      # this is a GET. retry up to 3x if we deadline.
      for _ in range(RETRIES):
        try:
          return request()
        except http.client.HTTPException as e:
          if not str(e).startswith('Deadline exceeded'):
            raise
        except socket.timeout:
          pass
        except urllib.error.HTTPError as e:
          code, body = util.interpret_http_exception(e)
          if code is None or int(code) not in (500, 501, 502):
            raise
        logger.info('Twitter API call failed! Retrying...')

    # last try. if it deadlines, let the exception bubble up.
    return request()

  def base_object(self, obj):
    """Returns the "base" silo object that an object operates on.

    Includes special handling for Twitter photo and video URLs, eg:

    * ``https://twitter.com/nelson/status/447465082327298048/photo/1``
    * ``https://twitter.com/nelson/status/447465082327298048/video/1``

    Args:
      obj (dict): ActivityStreams object

    Returns:
      dict: minimal ActivityStreams object. Usually has at least ``id`` and
      ``url`` fields; may also have author.
    """
    base_obj = super(Twitter, self).base_object(obj)
    url = base_obj.get('url')
    if url:
      try:
        parsed = urllib.parse.urlparse(url)
        parts = parsed.path.split('/')
        if len(parts) >= 3 and parts[-2] in ('photo', 'video'):
          base_obj['id'] = parts[-3]
          parsed = list(parsed)
          parsed[2] = '/'.join(parts[:-2])
          base_obj['url'] = urllib.parse.urlunparse(parsed)
      except BaseException as e:
        logger.error(
          "Couldn't parse object URL %s : %s. Falling back to default logic.",
          url, e)

    return base_obj

  def tweet_to_as1_activity(self, tweet):
    """Converts a tweet to an AS1 activity.

    Args:
      tweet (dict): a decoded JSON tweet

    Returns:
      dict: ActivityStreams activity
    """
    obj = self.tweet_to_as1_object(tweet)
    activity = {
      'verb': 'post',
      'published': obj.get('published'),
      'id': obj.get('id'),
      'url': obj.get('url'),
      'actor': obj.get('author'),
      'object': obj,
    }

    retweeted = tweet.get('retweeted_status')
    if retweeted:
      activity['verb'] = 'share'
      activity['object'] = self.tweet_to_as1_object(retweeted)

    in_reply_to = obj.get('inReplyTo')
    if in_reply_to:
      activity['context'] = {'inReplyTo': in_reply_to}

    # yes, the source field has an embedded HTML link. bleh.
    # https://dev.twitter.com/docs/api/1.1/get/statuses/show/
    parsed = re.search('<a href="([^"]+)".*>(.+)</a>', tweet.get('source', ''))
    if parsed:
      url, name = parsed.groups()
      activity['generator'] = {'displayName': name, 'url': url}

    return self.postprocess_activity(activity)

  tweet_to_activity = tweet_to_as1_activity
  """Deprecated! Use :meth:`tweet_to_as1_activity` instead."""

  def tweet_to_as1_object(self, tweet):
    """Converts a tweet to an AS1 object.

    Args:
      tweet (dict): a decoded JSON tweet

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    obj = {}

    # always prefer id_str over id to avoid any chance of int overflow.
    # usually shouldn't matter in Python, but still.
    id = tweet.get('id_str')
    if not id:
      return {}

    created_at = tweet.get('created_at')
    try:
      published = self.rfc2822_to_iso8601(created_at)
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

    retweeted = tweet.get('retweeted_status')
    base_tweet = retweeted or tweet
    entities = self._get_entities(base_tweet)

    # text content
    text = base_tweet.get('full_text') or base_tweet.get('text') or ''
    text_start, text_end = (base_tweet.get('display_text_range')
                            or (0, len(text)))

    # author
    user = tweet.get('user')
    if user:
      obj['author'] = self.to_as1_actor(user)
      username = obj['author'].get('username')
      if username:
        obj['url'] = self.status_url(username, id)

      protected = user.get('protected')
      if protected is not None:
        obj['to'].append({
          'objectType': 'group',
          'alias': '@public' if not protected else '@private',
        })

    # media! into attachments.
    # https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/extended-entities-object
    media = entities.get('media', [])
    if media:
      types = {
        'photo': 'image',
        'video': 'video',
        'animated_gif': 'video',
      }
      obj['attachments'] = [{
          'objectType': types.get(m.get('type')),
          'image': {
            'url': m.get('media_url_https') or m.get('media_url'),
            'displayName': m.get('ext_alt_text'),
          },
          'stream': {'url': self._video_url(m)},
          'displayName': m.get('ext_alt_text'),
      } for m in media]

      first = obj['attachments'][0]
      if first['objectType'] == 'video':
        obj['stream'] = first['stream']
      else:
        obj['image'] = first['image']

    # if this tweet is quoting another tweet, include it as an attachment
    quoted = tweet.get('quoted_status')
    quoted_url = None
    if quoted:
      quoted_obj = self.tweet_to_as1_object(quoted)
      obj.setdefault('attachments', []).append(quoted_obj)
      quoted_url = (quoted_obj.get('url') or
                    tweet.get('quoted_status_permalink', {}).get('expanded'))

      # remove quoted tweet URL from text, tags
      url_entities = entities.get('urls', [])
      for i, entity in enumerate(url_entities):
        indices = entity.get('indices')
        if indices and entity.get('expanded_url') == quoted_url:
          start, end = indices
          text = text[:start] + text[end:]
          del url_entities[i]
          if start >= text_start and end <= text_end:
            text_end -= (end - start)

    # tags
    obj['tags'] = [
      {'objectType': 'mention',
       'id': self.tag_uri(t.get('screen_name')),
       'url': self.user_url(t.get('screen_name')),
       'displayName': t.get('name'),
       'indices': t.get('indices')
       } for t in entities.get('user_mentions', [])
    ] + [
      {'objectType': 'hashtag',
       'url': 'https://twitter.com/search?q=%23' + t.get('text'),
       'indices': t.get('indices'),
       } for t in entities.get('hashtags', [])
    ] + [
      {'objectType': 'article',
       'url': t.get('expanded_url'),
       'displayName': t.get('display_url'),
       'indices': t.get('indices'),
       } for t in entities.get('urls', [])
    ]

    # media. these are only temporary, to get rid of the image t.co links. the tag
    # elements are removed farther down below.
    #
    # when there are multiple, twitter usually (always?) only adds a single
    # media link to the end of the tweet text, and all of the media objects will
    # have the same indices. so de-dupe based on indices.
    indices_to_media = {
      tuple(t['indices']): {
        'objectType': 'image',
        'displayName': '',
        'indices': t['indices'],
      } for t in media if t.get('indices')}
    obj['tags'].extend(indices_to_media.values())

    # sort tags by indices, since they need to be processed (below) in order.
    obj['tags'].sort(key=lambda t: (t.get('indices') or []))

    # RT @username: prefix for retweets
    rt_prefix = ''
    if retweeted and retweeted.get('text'):
      rt_prefix = 'RT <a href="https://twitter.com/%s">@%s</a>: ' % (
        (retweeted.get('user', {}).get('screen_name'),) * 2)

    # person mentions
    obj['to'].extend(tag for tag in obj['tags']
                     if tag.get('objectType') in ('person', 'mention')
                     and tag.get('indices')[1] <= text_start)

    # replace entities with display URLs, convert start/end indices to start/length
    content = rt_prefix + text[text_start:text_end]
    offset = len(rt_prefix) - text_start
    for t in obj['tags']:
      start, end = t.pop('indices', None) or (0, 0)
      if start >= text_start and end <= text_end:
        start += offset
        end += offset
        length = end - start
        if t['objectType'] in ('article', 'image'):
          tag_text = t.get('displayName', t.get('url'))
          if tag_text is not None:
            content = content[:start] + tag_text + content[end:]
            offset += len(tag_text) - length
            length = len(tag_text)
        t.update({'startIndex': start, 'length': length})

    obj.update({
      'tags': [t for t in obj['tags'] if t['objectType'] != 'image'] +
              [self.retweet_to_as1(r) for r in tweet.get('retweets', [])],
      'content': content,
    })

    # location
    place = tweet.get('place')
    if place:
      obj['location'] = {
        'displayName': place.get('full_name'),
        'id': self.tag_uri(place.get('id')),
      }

      # place['url'] is a JSON API url, not useful for end users. get the
      # lat/lon from geo instead.
      geo = tweet.get('geo')
      if geo:
        coords = geo.get('coordinates')
        if coords:
          obj['location']['url'] = ('https://maps.google.com/maps?q=%s,%s' %
                                    tuple(coords))

    # inReplyTo
    reply_to_screenname = tweet.get('in_reply_to_screen_name')
    reply_to_id = tweet.get('in_reply_to_status_id')
    if reply_to_id and reply_to_screenname:
      obj['inReplyTo'] = [{
        'id': self.tag_uri(reply_to_id),
        'url': self.status_url(reply_to_screenname, reply_to_id),
      }]

    return self.postprocess_object(obj)

  tweet_to_object = tweet_to_as1_object
  """Deprecated! Use :meth:`tweet_to_as1_object` instead."""

  @staticmethod
  def _get_entities(tweet):
    """Merges and returns a tweet's ``entities`` and ``extended_entities``.

    Most entities are in the ``entities`` field - urls, hashtags, user_mentions,
    symbols, etc. Media are special though: ``extended_entities`` is always
    preferred. It has videos, animated gifs, and multiple photos. ``entities``
    only has one photo at most, either the first or a thumbnail from the video,
    and its type is always ``photo`` even for videos and animated gifs. (The
    ``id`` and ``id_str`` will be the same.) So ignore it unless
    ``extended_entities`` is missing.

    https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/extended-entities-object
    """
    entities = collections.defaultdict(list)

    # maps kind to set of id_str, url, and text values we've seen, with indices,
    # for de-duping
    seen_ids = collections.defaultdict(set)

    for field in 'extended_entities', 'entities':  # prefer extended_entities!
      # kind is media, urls, hashtags, user_mentions, symbols, etc
      for kind, values in tweet.get(field, {}).items():
        for v in values:
          id = (v.get('id_str') or v.get('id') or v.get('url') or v.get('text'),
                tuple(v.get('indices') or []))
          if id[0] or id[1]:
            if id in seen_ids[kind]:
              continue
            seen_ids[kind].add(id)
          entities[kind].append(v)

    return entities

  def _video_url(self, media):
    """Returns the best video URL from a media object.

    Prefers MIME types that start with ``video/``, then falls back to others.

    https://developer.twitter.com/en/docs/tweets/data-dictionary/overview/extended-entities-object

    Twitter videos in extended entities currently often have both ``.m3u8`` (HLS)
    and ``.mp4`` variants. Twitter threatened to drop the MP4s in Aug 2016, but
    they're still there as of Dec 2017.

    https://twittercommunity.com/t/retiring-mp4-video-output-support-on-august-1st-2016/66045
    https://twittercommunity.com/t/retiring-mp4-video-output/66093
    https://twittercommunity.com/t/mp4-still-appears-despite-of-retiring-announcment/78894

    Args:
      media (dict): Twitter media object

    Returns:
      str: URL
    """
    variants = media.get('video_info', {}).get('variants')
    if not variants:
      return

    best_bitrate = 0
    best_url = None
    for variant in variants:
      url = variant.get('url')
      bitrate = variant.get('bitrate', 0)
      type = variant.get('content_type', '')
      if url and type.startswith('video/') and bitrate >= best_bitrate:
        best_url = url
        best_bitrate = bitrate

    return best_url or variants[0].get('url')

  def to_as1_actor(self, user):
    """Converts a user to an actor.

    Args:
      user (dict): a decoded JSON Twitter user

    Returns:
      dict: ActivityStreams actor
    """
    username = user.get('screen_name')
    if not username:
      return {}

    urls = [self.user_url(username)] + util.trim_nulls(
      [e.get('expanded_url') for e in itertools.chain(
        *(user.get('entities', {}).get(field, {}).get('urls', [])
          for field in ('url', 'description')))])

    image = user.get('profile_image_url_https') or user.get('profile_image_url')
    if image:
      # remove _normal for a ~256x256 avatar rather than ~48x48
      image = image.replace('_normal.', '.', 1)

    return util.trim_nulls({
      'objectType': 'person',
      'displayName': user.get('name') or username,
      'image': {'url': image},
      'id': self.tag_uri(username),
      # numeric_id is our own custom field that always has the source's numeric
      # user id, if available.
      'numeric_id': user.get('id_str'),
      'published': self.rfc2822_to_iso8601(user.get('created_at')),
      'url': urls[0],
      'urls': [{'value': u} for u in urls] if len(urls) > 1 else None,
      'location': {'displayName': user.get('location')},
      'username': username,
      'description': user.get('description'),
    })

  user_to_actor = to_as1_actor
  """Deprecated! Use :meth:`to_as1_actor` instead."""

  def retweet_to_as1(self, retweet):
    """Converts a retweet to an AS1 share activity.

    Args:
      retweet (dict): a decoded JSON tweet

    Returns:
      dict: ActivityStreams object
    """
    orig = retweet.get('retweeted_status')
    if not orig:
      return None

    share = self.tweet_to_as1_object(retweet)
    share.update({
        'objectType': 'activity',
        'verb': 'share',
        'object': {'url': self.tweet_url(orig)},
    })
    if 'tags' in share:
      # the existing tags apply to the original tweet's text, which we replaced
      del share['tags']
    return self.postprocess_object(share)

  retweet_to_object = retweet_to_as1
  """Deprecated! Use :meth:`retweet_to_as1` instead."""

  def streaming_event_to_object(self, event):
    """Converts a Streaming API event to an object.

    https://dev.twitter.com/docs/streaming-apis/messages#Events_event

    Right now, only converts favorite events to like objects.

    Args:
      event (dict): a decoded JSON Streaming API event

    Returns:
      dict: ActivityStreams object
    """
    source = event.get('source')
    tweet = event.get('target_object')
    if event.get('event') == 'favorite' and source and tweet:
      obj = self._make_like(tweet, source)
      obj['published'] = self.rfc2822_to_iso8601(event.get('created_at'))
      return obj

  def _make_like(self, tweet, liker):
    """Generates and returns a ActivityStreams like object.

    Args:
      tweet (dict): Twitter tweet
      liker (dict): Twitter user

    Returns:
      dict: ActivityStreams object
    """
    # TODO: unify with Mastodon._make_like()
    tweet_id = tweet.get('id_str')
    liker_id = liker.get('id_str')
    id = None
    url = obj_url = self.tweet_url(tweet)

    if liker_id:
      id = self.tag_uri(f'{tweet_id}_favorited_by_{liker_id}')
      url += f'#favorited-by-{liker_id}'

    return self.postprocess_object({
        'id': id,
        'url': url,
        'objectType': 'activity',
        'verb': 'like',
        'object': {'url': obj_url},
        'author': self.to_as1_actor(liker),
    })

  @staticmethod
  def rfc2822_to_iso8601(time_str):
    """Converts a timestamp string from RFC 2822 format to ISO 8601.

    Example RFC 2822 timestamp string generated by Twitter:
      ``Wed May 23 06:01:13 +0000 2007``

    Resulting ISO 8610 timestamp string:
      ``2007-05-23T06:01:13``
    """
    if not time_str:
      return None

    without_timezone = re.sub(' [+-][0-9]{4} ', ' ', time_str)
    timezone = re.search('[+-][0-9]{4}', time_str).group(0)
    # convert offset to seconds
    offset = 3600 * int(timezone[1:3]) + 60 * int(timezone[3:])
    # negative offset
    if timezone[0] == '-':
      offset = -offset

    dt = datetime.datetime.strptime(without_timezone, '%a %b %d %H:%M:%S %Y').replace(tzinfo=OffsetTzinfo(offset))
    return dt.isoformat()

  def user_url(self, username):
    """Returns the Twitter URL for a given user."""
    return f'https://{self.DOMAIN}/{username}'

  def status_url(self, username, id):
    """Returns the Twitter URL for a tweet from a given user with a given id."""
    return f'{self.user_url(username)}/status/{id}'

  def tweet_url(self, tweet):
    """Returns the Twitter URL for a tweet given a tweet object."""
    return self.status_url(tweet.get('user', {}).get('screen_name'),
                           tweet.get('id_str'))

  @staticmethod
  def _validate_id(id):
      if not util.is_int(id):
        raise ValueError(f'Twitter ids must be ints; got {id}')
