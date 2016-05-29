# coding=utf-8
"""Twitter source class.

Uses the v1.1 REST API: https://dev.twitter.com/docs/api

TODO: collections for twitter accounts; use as activity target?

The Audience Targeting 'to' field is set to @public or @private based on whether
the tweet author's 'protected' field is true or false.
https://dev.twitter.com/docs/platform-objects/users
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import collections
import datetime
import itertools
import httplib
import json
import logging
import mimetypes
import re
import socket
import urllib
import urllib2
import urlparse

import appengine_config

from bs4 import BeautifulSoup
import requests
import brevity

import source
from oauth_dropins import twitter_auth
from oauth_dropins.webutil import util

API_BASE = 'https://api.twitter.com/1.1/'
API_TIMELINE = 'statuses/home_timeline.json?include_entities=true&count=%d'
API_USER_TIMELINE = 'statuses/user_timeline.json?include_entities=true&count=%(count)d&screen_name=%(screen_name)s'
API_LIST_TIMELINE = 'lists/statuses.json?include_entities=true&count=%(count)d&slug=%(slug)s&owner_screen_name=%(owner_screen_name)s'
API_STATUS = 'statuses/show.json?id=%s&include_entities=true'
API_LOOKUP = 'statuses/lookup.json?id=%s&include_entities=true'
API_RETWEETS = 'statuses/retweets.json?id=%s'
API_USER = 'users/show.json?screen_name=%s'
API_CURRENT_USER = 'account/verify_credentials.json'
API_SEARCH = 'search/tweets.json?q=%(q)s&include_entities=true&result_type=recent&count=%(count)d'
API_FAVORITES = 'favorites/list.json?screen_name=%s&include_entities=true'
API_POST_TWEET = 'statuses/update.json'
API_POST_RETWEET = 'statuses/retweet/%s.json'
API_POST_FAVORITE = 'favorites/create.json'
API_POST_MEDIA = 'statuses/update_with_media.json'
API_UPLOAD_MEDIA = 'https://upload.twitter.com/1.1/media/upload.json'
HTML_FAVORITES = 'https://twitter.com/i/activity/favorited_popup?id=%s'

# Don't hit the RETWEETS endpoint more than this many times per
# get_activities() call.
# https://dev.twitter.com/docs/rate-limiting/1.1/limits
# TODO: sigh. figure out a better way. dammit twitter, give me a batch API!!!
RETWEET_LIMIT = 15

# Number of IDs to search for at a time
QUOTE_SEARCH_BATCH_SIZE = 20

# For read requests only.
RETRIES = 3

# Config constants, as of 2015-12-29:
# * Current max tweet length and expected length of a t.co URL.
#   https://dev.twitter.com/docs/tco-link-wrapper/faq
# * Max media per tweet.
#   https://dev.twitter.com/rest/reference/post/statuses/update#api-param-media_ids
# * Allowed video formats, max video size, and upload chunk size:
#   https://dev.twitter.com/rest/public/uploading-media#keepinmind
#
# TODO: pull these from /help/configuration.json instead.
# https://dev.twitter.com/docs/api/1.1/get/help/configuration
MAX_TWEET_LENGTH = 140
TCO_LENGTH = 23
MAX_MEDIA = 4

MB = 1024 * 1024
MAX_VIDEO_SIZE = 15 * MB
UPLOAD_CHUNK_SIZE = 5 * MB
VIDEO_MIME_TYPES = frozenset(('video/mp4',))


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
  """Implements the ActivityStreams API for Twitter.
  """

  DOMAIN = 'twitter.com'
  BASE_URL = 'https://twitter.com/'
  NAME = 'Twitter'
  FRONT_PAGE_TEMPLATE = 'templates/twitter_index.html'

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

  def __init__(self, access_token_key, access_token_secret, username=None):
    """Constructor.

    Twitter now requires authentication in v1.1 of their API. You can get an
    OAuth access token by creating an app here: https://dev.twitter.com/apps/new

    Args:
      access_token_key: string, OAuth access token key
      access_token_secret: string, OAuth access token secret
      username: string, optional, the current user. Used in e.g. preview/create.
    """
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret
    self.username = username

  def get_actor(self, screen_name=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      screen_name: string username. Defaults to the current user.
    """
    if screen_name is None:
      url = API_CURRENT_USER
    else:
      url = API_USER % screen_name
    return self.user_to_actor(self.urlopen(url))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False,
                              fetch_mentions=False, search_query=None, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    XXX HACK: this is currently hacked for bridgy to NOT pass min_id to the
    request for fetching activity tweets themselves, but to pass it to all of
    the requests for filling in replies, retweets, etc. That's because we want
    to find new replies and retweets of older initial tweets.
    TODO: find a better way.

    See method docstring in source.py for details. app_id is ignored.
    min_id is translated to Twitter's since_id.

    The code for handling ETags (and 304 Not Changed responses and setting
    If-None-Match) is here, but unused right now since Twitter evidently doesn't
    support ETags. From https://dev.twitter.com/discussions/5800 :
    "I've confirmed with our team that we're not explicitly supporting this
    family of features."

    Likes (ie favorites) are scraped from twitter.com HTML, since Twitter's REST
    API doesn't offer a way to fetch them. You can also get them from the
    Streaming API, though, and convert them with streaming_event_to_object().
    https://dev.twitter.com/docs/streaming-apis/messages#Events_event

    Shares (ie retweets) are fetched with a separate API call per tweet:
    https://dev.twitter.com/docs/api/1.1/get/statuses/retweets/%3Aid

    However, retweets are only fetched for the first 15 tweets that have them,
    since that's Twitter's rate limit per 15 minute window. :(
    https://dev.twitter.com/docs/rate-limiting/1.1/limits

    Quote tweets are fetched by searching for the possibly quoted tweet's ID,
    using the OR operator to search up to 5 IDs at a time, and then checking
    the quoted_status_id_str field
    https://dev.twitter.com/overview/api/tweets#quoted_status_id_str

    Use the group_id @self to retrieve a user_id’s timeline. If user_id is None
    or @me, it will return tweets for the current API user.

    group_id can be used to specify the slug of a list for which to return tweets.
    By default the current API user’s lists will be used, but lists owned by other
    users can be fetched by explicitly passing a username to user_id, e.g. to
    fetch tweets from the list @exampleuser/example-list you would call
    get_activities(user_id='exampleuser', group_id='example-list').

    Twitter replies default to including a mention of the user they're replying
    to, which overloads mentions a bit. When fetch_shares is True, we determine
    that a tweet mentions the current user if it @-mentions their username and:
    * it's not a reply, OR
    * it's a reply, but not to the current user, AND
      * the tweet it's replying to doesn't @-mention the current user
    """
    if group_id is None:
      group_id = source.FRIENDS

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
      tweets = [self.urlopen(API_STATUS % activity_id)]
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
        url = API_SEARCH % {
          'q': urllib.quote_plus(search_query),
          'count': count,
        }
      elif group_id in (source.FRIENDS, source.ALL):
        url = API_TIMELINE % (count)
      else:
        if not user_id:
          user_id = _user().get('screen_name')
        url = API_LIST_TIMELINE % {
          'count': count,
          'slug': group_id,
          'owner_screen_name': user_id,
        }

      headers = {'If-None-Match': etag} if etag else {}
      total_count = None
      try:
        resp = self.urlopen(url, headers=headers, parse_response=False)
        etag = resp.info().get('ETag')
        tweet_obj = json.loads(resp.read())
        if group_id == source.SEARCH:
          tweet_obj = tweet_obj.get('statuses', [])
        tweets = tweet_obj[start_index:]
      except urllib2.HTTPError, e:
        if e.code == 304:  # Not Modified, from a matching ETag
          tweets = []
        else:
          raise

    # batch get memcached counts of favorites and retweets for all tweets
    cached = {}
    if cache is not None:
      keys = itertools.product(('ATR', 'ATF'), [t['id_str'] for t in tweets])
      cached = cache.get_multi('%s %s' % (prefix, id) for prefix, id in keys)
    # only update the cache at the end, in case we hit an error before then
    cache_updates = {}

    if fetch_shares:
      retweet_calls = 0
      for tweet in tweets:
        if tweet.get('retweeted'):  # this tweet is itself a retweet
          continue
        elif retweet_calls >= RETWEET_LIMIT:
          logging.warning("Hit Twitter's retweet rate limit (%d) with more to "
                          "fetch! Results will be incomplete!" % RETWEET_LIMIT)
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
        if count and count != cached.get('ATR ' + id):
          url = API_RETWEETS % id
          if min_id is not None:
            url = util.add_query_params(url, {'since_id': min_id})

          try:
            tweet['retweets'] = self.urlopen(url)
          except urllib2.URLError, e:
            code, _ = util.interpret_http_exception(e)
            if code != '404':  # 404 means the original tweet was deleted
              raise

          retweet_calls += 1
          cache_updates['ATR ' + id] = count

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
        if self.is_public(activity) and count and count != cached.get('ATF ' + id):
          url = HTML_FAVORITES % id
          try:
            html = json.loads(util.urlopen(url).read()).get('htmlUsers', '')
          except urllib2.URLError, e:
            util.interpret_http_exception(e)  # just log it
            continue
          likes = self.favorites_html_to_likes(tweet, html)
          activity['object'].setdefault('tags', []).extend(likes)
          cache_updates['ATF ' + id] = count

    activities += tweet_activities
    response = self.make_activities_base_response(activities)
    response.update({'total_count': total_count, 'etag': etag})
    if cache_updates and cache is not None:
      cache.set_multi(cache_updates)
    return response

  def fetch_replies(self, activities, min_id=None):
    """Fetches and injects Twitter replies into a list of activities, in place.

    Includes indirect replies ie reply chains, not just direct replies. Searches
    for @-mentions, matches them to the original tweets with
    in_reply_to_status_id_str, and recurses until it's walked the entire tree.

    Args:
      activities: list of activity dicts

    Returns:
      same activities list
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
            'q': urllib.quote_plus('@' + author),
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
    by @-replying. See the get_activities() docstring for details.

    Args:
      username: string
      tweets: list of Twitter API objects. used to find quote tweets quoting them.
      min_id: only return activities with ids greater than this

    Returns:
      list of activity dicts
    """
    # get @-name mentions
    url = API_SEARCH % {
      'q': urllib.quote_plus('@' + username),
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
        for i in xrange(0, len(tweets), QUOTE_SEARCH_BATCH_SIZE)
    ]:
      batch_ids = [t['id_str'] for t in batch]
      url = API_SEARCH % {
        'q': urllib.quote_plus(' OR '.join(batch_ids)),
        'count': 100,
      }
      if min_id is not None:
        url = util.add_query_params(url, {'since_id': min_id})
      candidates = self.urlopen(url)['statuses']
      for c in candidates:
        quoted_status_id = c.get('quoted_status_id_str')
        if quoted_status_id and quoted_status_id in batch_ids:
          mentions.append(c)

    return mentions

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None,
                  activity=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id. Ignored.
      activity: activity object, optional
    """
    url = API_STATUS % comment_id
    return self.tweet_to_object(self.urlopen(url))

  def get_share(self, activity_user_id, activity_id, share_id, activity=None):
    """Returns an ActivityStreams 'share' activity object.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object
      activity: activity object, optional
    """
    url = API_STATUS % share_id
    return self.retweet_to_object(self.urlopen(url))

  def create(self, obj, include_link=source.OMIT_LINK,
             ignore_formatting=False):
    """Creates a tweet, reply tweet, retweet, or favorite.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose content will be a dict with 'id', 'url',
      and 'type' keys (all optional) for the newly created Twitter
      object (or None)

    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Previews creating a tweet, reply tweet, retweet, or favorite.

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult whose content will be a unicode string HTML
      snippet (or None)
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates or previews creating a tweet, reply tweet, retweet, or favorite.

    https://dev.twitter.com/docs/api/1.1/post/statuses/update
    https://dev.twitter.com/docs/api/1.1/post/statuses/retweet/:id
    https://dev.twitter.com/docs/api/1.1/post/favorites/create

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: string
      ignore_formatting: boolean

    Returns:
      a CreationResult

      If preview is True, the content will be a unicode string HTML
      snippet. If False, it will be a dict with 'id' and 'url' keys
      for the newly created Twitter object.
    """
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')

    base_obj = self.base_object(obj)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')

    is_reply = type == 'comment' or 'inReplyTo' in obj
    image_urls = [image.get('url') for image in util.get_list(obj, 'image')]
    video_url = util.get_first(obj, 'stream', {}).get('url')
    has_media = (image_urls or video_url) and (type in ('note', 'article') or is_reply)
    lat = obj.get('location', {}).get('latitude')
    lng = obj.get('location', {}).get('longitude')

    # prefer displayName over content for articles
    type = obj.get('objectType')
    base_url = self.base_object(obj).get('url')
    prefer_content = type == 'note' or (base_url and (type == 'comment'
                                                      or obj.get('inReplyTo')))
    content = self._content_for_create(obj, ignore_formatting=ignore_formatting,
                                       prefer_name=not prefer_content,
                                       strip_first_video_tag=bool(video_url))
    if not content:
      if type == 'activity':
        content = verb
      elif has_media:
        content = ''
      else:
        return source.creation_result(
          abort=False,  # keep looking for things to publish,
          error_plain='No content text found.',
          error_html='No content text found.')

    if is_reply and base_url:
      # extract username from in-reply-to URL so we can @-mention it, if it's
      # not already @-mentioned, since Twitter requires that to make our new
      # tweet a reply.
      # https://dev.twitter.com/docs/api/1.1/post/statuses/update#api-param-in_reply_to_status_id
      # TODO: this doesn't handle an in-reply-to username that's a prefix of
      # another username already mentioned, e.g. in reply to @foo when content
      # includes @foobar.
      parsed = urlparse.urlparse(base_url)
      parts = parsed.path.split('/')
      if len(parts) < 2 or not parts[1]:
        raise ValueError('Could not determine author of in-reply-to URL %s' % base_url)
      reply_to = parts[1].lower()
      if not self.username or reply_to != self.username.lower():
        mention = '@' + reply_to
        if mention not in content.lower():
          content = mention + ' ' + content

      # the embed URL in the preview can't start with mobile. or www., so just
      # hard-code it to twitter.com. index #1 is netloc.
      parsed = list(parsed)
      parsed[1] = self.DOMAIN
      base_url = urlparse.urlunparse(parsed)

    # need a base_url with the tweet id for the embed HTML below. do this
    # *after* checking the real base_url for in-reply-to author username.
    if base_id and not base_url:
      base_url = 'https://twitter.com/-/statuses/' + base_id

    if is_reply and not base_url:
      return source.creation_result(
        abort=True,
        error_plain='Could not find a tweet to reply to.',
        error_html='Could not find a tweet to <a href="http://indiewebcamp.com/reply">reply to</a>. '
        'Check that your post has an <a href="http://indiewebcamp.com/comment">in-reply-to</a> '
        'link a Twitter URL or to an original post that publishes a '
        '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

    # truncate and ellipsize content if it's over the character
    # count. URLs will be t.co-wrapped, so include that when counting.
    content = self._truncate(
      content, obj.get('url'), include_link, type, has_media)

    # linkify defaults to Twitter's link shortening behavior
    preview_content = util.linkify(content, pretty=True, skip_bare_cc_tlds=True)

    if type == 'activity' and verb == 'like':
      if not base_url:
        return source.creation_result(
          abort=True,
          error_plain='Could not find a tweet to like.',
          error_html='Could not find a tweet to <a href="http://indiewebcamp.com/favorite">favorite</a>. '
          'Check that your post has a like-of link to a Twitter URL or to an original post that publishes a '
          '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

      if preview:
        return source.creation_result(
          description='<span class="verb">favorite</span> <a href="%s">'
                      'this tweet</a>:\n%s' % (base_url, self.embed_post(base_obj)))
      else:
        data = urllib.urlencode({'id': base_id})
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
        return source.creation_result(
          description='<span class="verb">retweet</span> <a href="%s">'
                      'this tweet</a>:\n%s' % (base_url, self.embed_post(base_obj)))
      else:
        data = urllib.urlencode({'id': base_id})
        resp = self.urlopen(API_POST_RETWEET % base_id, data=data)
        resp['type'] = 'repost'

    elif type in ('note', 'article') or is_reply:  # a tweet
      content = unicode(content).encode('utf-8')
      data = {'status': content}

      if is_reply:
        description = \
          '<span class="verb">@-reply</span> to <a href="%s">this tweet</a>:\n%s' % (
            base_url, self.embed_post(base_obj))
        data['in_reply_to_status_id'] = base_id
      else:
        description = '<span class="verb">tweet</span>:'

      if video_url:
        preview_content += ('<br /><br /><video controls src="%s"><a href="%s">'
                            'this video</a></video>' % (video_url, video_url))
        if not preview:
          ret = self.upload_video(video_url)
          if isinstance(ret, source.CreationResult):
            return ret
          data['media_ids'] = ret

      elif image_urls:
        num_urls = len(image_urls)
        if num_urls > MAX_MEDIA:
          image_urls = image_urls[:MAX_MEDIA]
          logging.warning('Found %d photos! Only using the first %d: %r',
                          num_urls, MAX_MEDIA, image_urls)
        preview_content += '<br /><br />' + ' &nbsp; '.join(
          '<img src="%s" />' % url for url in image_urls)
        if not preview:
          data['media_ids'] = ','.join(self.upload_images(image_urls))

      if lat and lng:
        preview_content += (
          '<div>at <a href="https://maps.google.com/maps?q=%s,%s">'
          '%s, %s</a></div>' % (lat, lng, lat, lng))
        data['lat'] = lat
        data['long'] = lng

      if preview:
        return source.creation_result(content=preview_content, description=description)
      else:
        resp = self.urlopen(API_POST_TWEET, data=urllib.urlencode(data))
        resp['type'] = 'comment' if is_reply else 'post'

    elif (verb and verb.startswith('rsvp-')) or verb == 'invite':
      return source.creation_result(
        abort=True,
        error_plain='Cannot publish RSVPs to Twitter.',
        error_html='This looks like an <a href="http://indiewebcamp.com/rsvp">RSVP</a>. '
        'Publishing events or RSVPs to Twitter is not supported.')

    else:
      return source.creation_result(
        abort=False,
        error_plain='Cannot publish type=%s, verb=%s to Twitter' % (type, verb),
        error_html='Cannot publish type=%s, verb=%s to Twitter' % (type, verb))

    id_str = resp.get('id_str')
    if id_str:
      resp.update({'id': id_str, 'url': self.tweet_url(resp)})
    elif 'url' not in resp:
      resp['url'] = base_url

    return source.creation_result(resp)

  def _truncate(self, content, url, include_link, type, has_media):
    """Shorten tweet content to fit within the 140 character limit.

    Args:
      content: string
      url: string
      include_link: string
      type: string
      has_media: boolean

    Return: string, the possibly shortened and ellipsized tweet text
    """
    if type == 'article':
      format = brevity.FORMAT_ARTICLE
    else:
      format = brevity.FORMAT_NOTE
    if has_media:
      format += '+' + brevity.FORMAT_MEDIA

    return brevity.shorten(
      content,
      # permalink is included only when the text is truncated
      permalink=url if include_link != source.OMIT_LINK else None,
      # permashortlink is always included
      permashortlink=url if include_link == source.INCLUDE_LINK else None,
      target_length=MAX_TWEET_LENGTH, link_length=TCO_LENGTH, format=format)

  def upload_images(self, urls):
    """Uploads one or more images from web URLs.

    https://dev.twitter.com/rest/reference/post/media/upload

    Args:
      urls: sequence of string URLs of images

    Returns: list of string media ids
    """
    ids = []
    for url in urls:
      headers = twitter_auth.auth_header(
        API_UPLOAD_MEDIA, self.access_token_key, self.access_token_secret, 'POST')
      resp = util.requests_post(API_UPLOAD_MEDIA,
                                files={'media': util.urlopen(url)},
                                headers=headers)
      resp.raise_for_status()
      logging.info('Got: %s', resp.text)
      try:
        ids.append(json.loads(resp.text)['media_id_string'])
      except ValueError, KeyError:
        logging.exception("Couldn't parse response: %s", resp.text)
        raise

    return ids

  def upload_video(self, url):
    """Uploads a video from web URLs using the chunked upload process.

    Chunked upload consists of multiple API calls:
    * command=INIT, which allocates the media id
    * command=APPEND for each 5MB block, up to 15MB total
    * command=FINALIZE

    https://dev.twitter.com/rest/reference/post/media/upload-chunked
    https://dev.twitter.com/rest/public/uploading-media#chunkedupload

    Args:
      url: string URL of images

    Returns: string media id or CreationResult on error
    """
    video_resp = util.urlopen(url)

    # check format and size
    type = video_resp.headers.get('Content-Type')
    if not type:
      type, _ = mimetypes.guess_type(url)
    if type and type not in VIDEO_MIME_TYPES:
      msg = 'Twitter only supports MP4 videos; yours looks like a %s.' % type
      return source.creation_result(abort=True, error_plain=msg, error_html=msg)

    length = video_resp.headers.get('Content-Length')
    if not util.is_int(length):
      msg = "Couldn't determine your video's size."
      return source.creation_result(abort=True, error_plain=msg, error_html=msg)

    length = int(length)
    if int(length) > MAX_VIDEO_SIZE:
      msg = "Your %sMB video is larger than Twitter's %dMB limit." % (
        length // MB, MAX_VIDEO_SIZE // MB)
      return source.creation_result(abort=True, error_plain=msg, error_html=msg)

    # INIT
    media_id = self.urlopen(API_UPLOAD_MEDIA, data=urllib.urlencode({
      'command': 'INIT',
      'media_type': 'video/mp4',
      'total_bytes': length,
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
    self.urlopen(API_UPLOAD_MEDIA, data=urllib.urlencode({
      'command': 'FINALIZE',
      'media_id': media_id,
    }))

    return media_id

  def urlopen(self, url, parse_response=True, **kwargs):
    """Wraps urllib2.urlopen() and adds an OAuth signature.
    """
    if not url.startswith('http'):
      url = API_BASE + url

    def request():
      resp = twitter_auth.signed_urlopen(
        url, self.access_token_key, self.access_token_secret, **kwargs)
      if parse_response:
        try:
          return json.loads(resp.read())
        except (ValueError, TypeError):
          msg = 'Non-JSON response! (Synthetic HTTP error generated by Bridgy.)'
          logging.exception(msg)
          raise urllib2.HTTPError(API_BASE + url, 503, msg, {}, None)
      else:
        return resp

    if ('data' not in kwargs and not
        (isinstance(url, urllib2.Request) and url.get_method() == 'POST')):
      # this is a GET. retry up to 3x if we deadline.
      for attempt in range(RETRIES):
        try:
          return request()
        except httplib.HTTPException, e:
          if not str(e).startswith('Deadline exceeded'):
            raise
        except socket.error, e:
          pass
        except urllib2.HTTPError, e:
          code, body = util.interpret_http_exception(e)
          if code is None or int(code) / 100 != 5:
            raise
        logging.warning('Twitter API call failed! Retrying...')

    # last try. if it deadlines, let the exception bubble up.
    return request()

  def base_object(self, obj):
    """Returns the 'base' silo object that an object operates on.

    Includes special handling for Twitter photo URLs, e.g.
    https://twitter.com/nelson/status/447465082327298048/photo/1

    Args:
      obj: ActivityStreams object

    Returns: dict, minimal ActivityStreams object. Usually has at least id and
      url fields; may also have author.
    """
    base_obj = super(Twitter, self).base_object(obj)
    url = base_obj.get('url')
    if url:
      try:
        parsed = urlparse.urlparse(url)
        parts = parsed.path.split('/')
        if len(parts) >= 3 and parts[-2] == 'photo':
          base_obj['id'] = parts[-3]
          parsed = list(parsed)
          parsed[2] = '/'.join(parts[:-2])
          base_obj['url'] = urlparse.urlunparse(parsed)
      except BaseException, e:
        logging.error(
          "Couldn't parse object URL %s : %s. Falling back to default logic.",
          url, e)

    return base_obj

  def tweet_to_activity(self, tweet):
    """Converts a tweet to an activity.

    Args:
      tweet: dict, a decoded JSON tweet

    Returns:
      an ActivityStreams activity dict, ready to be JSON-encoded
    """
    obj = self.tweet_to_object(tweet)
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
      activity['object'] = self.tweet_to_object(retweeted)

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

  def tweet_to_object(self, tweet):
    """Converts a tweet to an object.

    Args:
      tweet: dict, a decoded JSON tweet

    Returns:
      an ActivityStreams object dict, ready to be JSON-encoded
    """
    obj = {}

    # always prefer id_str over id to avoid any chance of integer overflow.
    # usually shouldn't matter in Python, but still.
    id = tweet.get('id_str')
    if not id:
      return {}

    obj = {
      'id': self.tag_uri(id),
      'objectType': 'note',
      'published': self.rfc2822_to_iso8601(tweet.get('created_at')),
      # don't linkify embedded URLs. (they'll all be t.co URLs.) instead, use
      # entities below to replace them with the real URLs, and then linkify.
      'content': tweet.get('text'),
      }

    content_prefix = ''
    retweeted = tweet.get('retweeted_status')
    if retweeted:
      entities = self._get_entities(retweeted)
      text = retweeted.get('text', '')
      if text:
        content_prefix = 'RT <a href="https://twitter.com/%s">@%s</a>: ' % (
          (retweeted.get('user', {}).get('screen_name'),) * 2)
        obj['content'] = content_prefix + text
    else:
      entities = self._get_entities(tweet)

    user = tweet.get('user')
    if user:
      obj['author'] = self.user_to_actor(user)
      username = obj['author'].get('username')
      if username:
        obj['url'] = self.status_url(username, id)

      protected = user.get('protected')
      if protected is not None:
        obj['to'] = [{'objectType': 'group',
                      'alias': '@public' if not protected else '@private'}]

    # currently the media list will only have photos. if that changes, though,
    # we'll need to make this conditional on media.type.
    # https://dev.twitter.com/docs/tweet-entities
    media = entities.get('media', [])
    if media:
      obj['attachments'] = [{
          'objectType': 'image',
          'image': {'url': m.get('media_url')},
      } for m in media]
      obj['image'] = {'url': media[0].get('media_url')}

    # if this tweet is quoting another tweet, include it as an attachment
    quoted = tweet.get('quoted_status')
    if quoted:
      obj.setdefault('attachments', []).append(self.tweet_to_object(quoted))

    # tags
    obj['tags'] = [
      {'objectType': 'person',
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
    obj['tags'].sort(key=lambda t: t.get('indices'))

    # convert start/end indices to start/length, and replace t.co URLs with
    # real "display" URLs.
    offset = len(content_prefix)
    for t in obj['tags']:
      indices = t.pop('indices', None)
      if indices:
        start = indices[0] + offset
        end = indices[1] + offset
        length = end - start
        if t['objectType'] in ('article', 'image'):
          text = t.get('displayName', t.get('url'))
          if text is not None:
            obj['content'] = obj['content'][:start] + text + obj['content'][end:]
            offset += len(text) - length
            length = len(text)
        t.update({'startIndex': start, 'length': length})

    obj['tags'] = [t for t in obj['tags'] if t['objectType'] != 'image']

    # retweets
    obj['tags'] += [
      self.retweet_to_object(r) for r in tweet.get('retweets', [])]

    # location
    place = tweet.get('place')
    if place:
      obj['location'] = {
        'displayName': place.get('full_name'),
        'id': place.get('id'),
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

  @staticmethod
  def _get_entities(tweet):
    """Merges and returns a tweet's entities and extended_entities."""
    entities = collections.defaultdict(list)

    # maps kind to set of id_str, url, and text values we've seen, for de-duping
    seen_ids = collections.defaultdict(set)

    for field in 'entities', 'extended_entities':
      # kind is media, urls, hashtags, user_mentions, symbols, etc
      for kind, values in tweet.get(field, {}).items():
        for v in values:
          id = v.get('id_str') or v.get('id') or v.get('url') or v.get('text')
          if id in seen_ids[kind]:
            continue
          elif id:
            seen_ids[kind].add(id)
          entities[kind].append(v)

    return entities

  def user_to_actor(self, user):
    """Converts a tweet to an activity.

    Args:
      user: dict, a decoded JSON Twitter user

    Returns:
      an ActivityStreams actor dict, ready to be JSON-encoded
    """
    username = user.get('screen_name')
    if not username:
      return {}

    urls = util.trim_nulls(
      [e.get('expanded_url') for e in itertools.chain(
        *(user.get('entities', {}).get(field, {}).get('urls', [])
          for field in ('url', 'description')))])
    url = urls[0] if urls else user.get('url') or self.user_url(username)

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
      'url': url,
      'urls': [{'value': u} for u in urls],
      'location': {'displayName': user.get('location')},
      'username': username,
      'description': user.get('description'),
      })

  def retweet_to_object(self, retweet):
    """Converts a retweet to a share activity object.

    Args:
      retweet: dict, a decoded JSON tweet

    Returns:
      an ActivityStreams object dict
    """
    orig = retweet.get('retweeted_status')
    if not orig:
      return None

    share = self.tweet_to_object(retweet)
    share.update({
        'objectType': 'activity',
        'verb': 'share',
        'object': {'url': self.tweet_url(orig)},
        })
    if 'tags' in share:
      # the existing tags apply to the original tweet's text, which we replaced
      del share['tags']
    return self.postprocess_object(share)

  def streaming_event_to_object(self, event):
    """Converts a Streaming API event to an object.

    https://dev.twitter.com/docs/streaming-apis/messages#Events_event

    Right now, only converts favorite events to like objects.

    Args:
      event: dict, a decoded JSON Streaming API event

    Returns:
      an ActivityStreams object dict
    """
    source = event.get('source')
    tweet = event.get('target_object')
    if event.get('event') == 'favorite' and source and tweet:
      obj = self._make_like(tweet, source)
      obj['published'] = self.rfc2822_to_iso8601(event.get('created_at'))
      return obj

  def favorites_html_to_likes(self, tweet, html):
    """Converts the HTML from a favorited_popup request to like objects.

    e.g. https://twitter.com/i/activity/favorited_popup?id=434753879708672001

    Args:
      html: string

    Returns:
      list of ActivityStreams like object dicts
    """
    soup = BeautifulSoup(html)
    likes = []

    for user in soup.find_all(class_='js-user-profile-link'):
      username = user.find(class_='username')
      if not username:
        continue
      username = username.string
      if username.startswith('@'):
        username = username[1:]

      img = user.find(class_='js-action-profile-avatar') or {}
      fullname = user.find(class_='fullname') or {}
      author = {
        'id_str': img.get('data-user-id'),
        'screen_name': username,
        'name': fullname.string if fullname else None,
        'profile_image_url': img.get('src'),
        }
      likes.append(self._make_like(tweet, author))

    return likes

  def _make_like(self, tweet, liker):
    """Generates and returns a ActivityStreams like object.

    Args:
      tweet: Twitter tweet dict
      liker: Twitter user dict

    Returns: ActivityStreams object dict
    """
    tweet_id = tweet.get('id_str')
    liker_id = liker.get('id_str')
    id = None
    url = obj_url = self.tweet_url(tweet)

    if liker_id:
      id = self.tag_uri('%s_favorited_by_%s' % (tweet_id, liker_id))
      url += '#favorited-by-%s' % liker_id

    return self.postprocess_object({
        'id': id,
        'url': url,
        'objectType': 'activity',
        'verb': 'like',
        'object': {'url': obj_url},
        'author': self.user_to_actor(liker),
        })

  @staticmethod
  def rfc2822_to_iso8601(time_str):
    """Converts a timestamp string from RFC 2822 format to ISO 8601.

    Example RFC 2822 timestamp string generated by Twitter:
      'Wed May 23 06:01:13 +0000 2007'

    Resulting ISO 8610 timestamp string:
      '2007-05-23T06:01:13'
    """
    if not time_str:
      return None

    without_timezone = re.sub(' [+-][0-9]{4} ', ' ', time_str)
    timezone = re.search('[+-][0-9]{4}', time_str).group(0)
    ## convert offset to seconds
    offset = 3600 * int(timezone[1:3]) + 60 * int(timezone[3:])
    ## negative offset
    if timezone[0] == '-':
      offset = -offset

    dt = datetime.datetime.strptime(without_timezone, '%a %b %d %H:%M:%S %Y').replace(tzinfo=OffsetTzinfo(offset))
    return dt.isoformat()

  def user_url(self, username):
    """Returns the Twitter URL for a given user."""
    return 'https://%s/%s' % (self.DOMAIN, username)

  def status_url(self, username, id):
    """Returns the Twitter URL for a tweet from a given user with a given id."""
    return '%s/status/%s' % (self.user_url(username), id)

  def tweet_url(self, tweet):
    """Returns the Twitter URL for a tweet given a tweet object."""
    return self.status_url(tweet.get('user', {}).get('screen_name'),
                           tweet.get('id_str'))
