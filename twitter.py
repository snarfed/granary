# coding=utf-8
"""Twitter source class.

Uses the v1.1 REST API: https://dev.twitter.com/docs/api

TODO: collections for twitter accounts; use as activity target?

The Audience Targeting 'to' field is set to @public or @private based on whether
the tweet author's 'protected' field is true or false.
https://dev.twitter.com/docs/platform-objects/users
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']

import collections
import datetime
import itertools
import json
import logging
import re
import urllib
import urllib2
import urlparse

from appengine_config import HTTP_TIMEOUT

from bs4 import BeautifulSoup

import source
from oauth_dropins import twitter_auth
from oauth_dropins.webutil import util

API_TIMELINE_URL = \
  'https://api.twitter.com/1.1/statuses/home_timeline.json?include_entities=true&count=%d'
API_SELF_TIMELINE_URL = \
  'https://api.twitter.com/1.1/statuses/user_timeline.json?include_entities=true&count=%d'
API_STATUS_URL = \
  'https://api.twitter.com/1.1/statuses/show.json?id=%s&include_entities=true'
API_RETWEETS_URL = \
  'https://api.twitter.com/1.1/statuses/retweets.json?id=%s'
API_USER_URL = \
  'https://api.twitter.com/1.1/users/lookup.json?screen_name=%s'
API_CURRENT_USER_URL = \
  'https://api.twitter.com/1.1/account/verify_credentials.json'
API_SEARCH_URL = \
    'https://api.twitter.com/1.1/search/tweets.json?q=%s&include_entities=true&result_type=recent&count=100'
API_POST_TWEET_URL = 'https://api.twitter.com/1.1/statuses/update.json'
API_POST_RETWEET_URL = 'https://api.twitter.com/1.1/statuses/retweet/%s.json'
API_POST_FAVORITE_URL = 'https://api.twitter.com/1.1/favorites/create.json'
API_POST_MEDIA_URL = 'https://api.twitter.com/1.1/statuses/update_with_media.json'
HTML_FAVORITES_URL = 'https://twitter.com/i/activity/favorited_popup?id=%s'

# Don't hit the RETWEETS endpoint more than this many times per
# get_activities() call.
# https://dev.twitter.com/docs/rate-limiting/1.1/limits
# TODO: sigh. figure out a better way. dammit twitter, give me a batch API!!!
RETWEET_LIMIT = 15

# HTML snippet that embeds a tweet.
# https://dev.twitter.com/docs/embedded-tweets
EMBED_SCRIPT = """
<script async src="//platform.twitter.com/widgets.js" charset="utf-8"></script>
"""
EMBED_TWEET = """
<br />
<blockquote class="twitter-tweet" lang="en" data-conversation="none" data-dnt="true">
<p></p>
<a href="%s"></a>
</blockquote>
"""

# Current max tweet length and expected length of a t.co URL, as of 2014-03-11.
# (This is actually just for https links; it's 22 for http.)
#
# TODO: pull tco length from the API /help/configuration.json endpoint instead.
# Details:
# https://dev.twitter.com/docs/tco-link-wrapper/faq
# https://dev.twitter.com/docs/api/1.1/get/help/configuration
# https://dev.twitter.com/discussions/869
MAX_TWEET_LENGTH = 140
TCO_LENGTH = 23

class OffsetTzinfo(datetime.tzinfo):
  """A simple, DST-unaware tzinfo from given utc offest in seconds.
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
  NAME = 'Twitter'
  FRONT_PAGE_TEMPLATE = 'templates/twitter_index.html'

  def __init__(self, access_token_key, access_token_secret):
    """Constructor.

    Twitter now requires authentication in v1.1 of their API. You can get an
    OAuth access token by creating an app here: https://dev.twitter.com/apps/new

    Args:
      access_token_key: string, OAuth access token key
      access_token_secret: string, OAuth access token secret
    """
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret

  def get_actor(self, screen_name=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      screen_name: string username. Defaults to the current user.
    """
    if screen_name is None:
      url = API_CURRENT_USER_URL
    else:
      url = API_USER_URL % screen_name
    return self.user_to_actor(json.loads(self.urlopen(url).read()))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, fetch_events=False):
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
    """
    if activity_id:
      resp = self.urlopen(API_STATUS_URL % activity_id)
      tweets = [json.loads(resp.read())]
      total_count = len(tweets)
    else:
      url = API_SELF_TIMELINE_URL if group_id == source.SELF else API_TIMELINE_URL
      url = url % (count + start_index)
      headers = {'If-None-Match': etag} if etag else {}
      total_count = None
      try:
        resp = self.urlopen(url, headers=headers)
        etag = resp.info().get('ETag')
        tweets = json.loads(resp.read())[start_index:]
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
          url = API_RETWEETS_URL % id
          if min_id is not None:
            url = util.add_query_params(url, {'since_id': min_id})
          tweet['retweets'] = json.loads(self.urlopen(url).read())
          retweet_calls += 1
          cache_updates['ATR ' + id] = count

    activities = [self.tweet_to_activity(t) for t in tweets]

    if fetch_replies:
      self.fetch_replies(activities, min_id=min_id)

    if fetch_likes:
      for tweet, activity in zip(tweets, activities):
        id = tweet['id_str']
        count = tweet.get('favorite_count')
        if count and count != cached.get('ATF ' + id):
          url = HTML_FAVORITES_URL % id
          logging.debug('Fetching %s', url)
          html = json.loads(urllib2.urlopen(url, timeout=HTTP_TIMEOUT).read()
                            ).get('htmlUsers', '')
          likes = self.favorites_html_to_likes(tweet, html)
          activity['object'].setdefault('tags', []).extend(likes)
          cache_updates['ATF ' + id] = count

    response = self._make_activities_base_response(activities)
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
          url = API_SEARCH_URL % urllib.quote_plus('@' + author)
          if min_id is not None:
            url = util.add_query_params(url, {'since_id': min_id})
          resp = self.urlopen(url).read()
          mentions[author] = json.loads(resp)['statuses']

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

  def get_comment(self, comment_id, activity_id=None, activity_author_id=None):
    """Returns an ActivityStreams comment object.

    Args:
      comment_id: string comment id
      activity_id: string activity id, optional
      activity_author_id: string activity author id. Ignored.
    """
    url = API_STATUS_URL % comment_id
    return self.tweet_to_object(json.loads(self.urlopen(url).read()))

  def get_share(self, activity_user_id, activity_id, share_id):
    """Returns an ActivityStreams 'share' activity object.

    Args:
      activity_user_id: string id of the user who posted the original activity
      activity_id: string activity id
      share_id: string id of the share object
    """
    url = API_STATUS_URL % share_id
    return self.retweet_to_object(json.loads(self.urlopen(url).read()))

  def create(self, obj, include_link=False):
    """Creates a tweet, reply tweet, retweet, or favorite.

    Args:
      obj: ActivityStreams object
      include_link: boolean

    Returns: dict with 'id', 'url', and 'type' keys (all optional) for the newly
      created Twitter object
    """
    return self._create(obj, preview=False, include_link=include_link)

  def preview_create(self, obj, include_link=False):
    """Previews creating a tweet, reply tweet, retweet, or favorite.

    Args:
      obj: ActivityStreams object
      include_link: boolean

    Returns: unicode string HTML snippet
    """
    return self._create(obj, preview=True, include_link=include_link)

  def _create(self, obj, preview=None, include_link=False):
    """Creates or previews creating a tweet, reply tweet, retweet, or favorite.

    https://dev.twitter.com/docs/api/1.1/post/statuses/update
    https://dev.twitter.com/docs/api/1.1/post/statuses/retweet/:id
    https://dev.twitter.com/docs/api/1.1/post/favorites/create

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: boolean

    Returns:
      If preview is True, a unicode string HTML snippet. If False, a dict with
      'id' and 'url' keys for the newly created Twitter object.
    """
    # TODO: validation, error handling
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')
    base_id, base_url = self.base_object(obj)
    content = self._content_for_create(obj)
    if not content:
      raise NotImplementedError('No content text found.')

    is_reply = (type == 'comment' or 'inReplyTo' in obj) and base_url
    if is_reply:
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
      mention = '@' + parts[1]
      if mention not in content:
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

    # truncate and ellipsize content if it's over the character count. URLs will
    # be t.co-wrapped, so include that when counting.
    links = set(util.extract_links(content))
    max = MAX_TWEET_LENGTH
    include_url = obj.get('url') if include_link else None
    if include_url:
      max -= TCO_LENGTH + 3

    length = 0
    tokens = content.split()
    for i, token in enumerate(tokens):
      # extract_links() strips trailing slashes from URLs, so do the same here
      # so we can compare.
      as_url = token[:-1] if token.endswith('/') else token
      length += (TCO_LENGTH if as_url in links else len(token))
      if i > 0:
        length += 1  # space between tokens
      if length > max:
        break
    else:
      i = len(tokens)

    # normalize whitespace
    # TODO: user opt in to preserve original whitespace (newlines, etc)
    content = ' '.join(tokens[:i])
    if i < len(tokens):
      content += u'…'
    if include_url:
      content += ' (%s)' % include_url
    # linkify defaults to Twitter's link shortening behavior
    preview_content = util.linkify(content, pretty=True)

    if is_reply:
      if preview:
        return ('will <span class="verb">@-reply</span>:<br /><br />\n<em>%s</em>\n'
                '<br /><br />...to <a href="%s">this tweet</a>:\n%s' %
                (preview_content, base_url, EMBED_TWEET % base_url))
      else:
        content = unicode(content).encode('utf-8')
        data = urllib.urlencode({'status': content, 'in_reply_to_status_id': base_id})
        resp = json.loads(self.urlopen(API_POST_TWEET_URL, data=data).read())
        resp['type'] = 'comment'

    elif type == 'activity' and verb == 'like':
      if preview:
        return ('will <span class="verb">favorite</span> <a href="%s">this tweet</a>:\n%s' %
                (base_url, EMBED_TWEET % base_url))
      else:
        data = urllib.urlencode({'id': base_id})
        self.urlopen(API_POST_FAVORITE_URL, data=data).read()
        resp = {'type': 'like'}

    elif type == 'activity' and verb == 'share':
      if preview:
        return ('will <span class="verb">retweet</span> <a href="%s">this tweet</a>:\n%s' %
                (base_url, EMBED_TWEET % base_url))
      else:
        data = urllib.urlencode({'id': base_id})
        resp = json.loads(self.urlopen(API_POST_RETWEET_URL % base_id, data=data).read())
        resp['type'] = 'repost'

    elif type == 'note' and obj.get('image'):
      image_url = obj.get('image').get('url')
      if preview:
        return ('will <span class="verb">tweet</span> with photo:<br /><br />'
                '<em>%s</em><br /><img src="%s"/><br />' % (preview_content, image_url))
      else:
        content = unicode(content).encode('utf-8')
        data = {'status': content}
        files = {'media[]': urllib2.urlopen(image_url)}
        headers = twitter_auth.auth_header(API_POST_MEDIA_URL, self.access_token_key, self.access_token_secret, 'POST')
        resp = json.loads(requests.post(API_POST_MEDIA_URL, data=data, files=files, headers=headers).text)
        resp['type'] = 'post'

    elif type in ('note', 'article', 'comment'):
      if preview:
        return ('will <span class="verb">tweet</span>:<br /><br />'
                '<em>%s</em><br />' % preview_content)
      else:
        content = unicode(content).encode('utf-8')
        data = urllib.urlencode({'status': content})
        resp = json.loads(self.urlopen(API_POST_TWEET_URL, data=data).read())
        resp['type'] = 'post'

    else:
      raise NotImplementedError()

    id_str = resp.get('id_str')
    if id_str:
      resp.update({'id': id_str, 'url': self.tweet_url(resp)})
    elif 'url' not in resp:
      resp['url'] = base_url
    return resp

  def urlopen(self, url, **kwargs):
    """Wraps urllib2.urlopen() and adds an OAuth signature.
    """
    return twitter_auth.signed_urlopen(
      url, self.access_token_key, self.access_token_secret, **kwargs)

  def base_object(self, obj):
    """Returns id and URL of the 'base' silo object that an object operates on.

    Includes special handling for Twitter photo URLs, e.g.
    https://twitter.com/nelson/status/447465082327298048/photo/1

    Args:
      obj: ActivityStreams object

    Returns: (string id, string URL) tuple. Both may be None.
    """
    id, url = super(Twitter, self).base_object(obj)
    if url:
      try:
        parsed = urlparse.urlparse(url)
        parts = parsed.path.split('/')
        if len(parts) >= 3 and parts[-2] == 'photo':
          return parts[-3], url
      except BaseException, e:
        logging.error(
          "Couldn't parse object URL %s : %s. Falling back to default logic.",
          url, e)

    return id, url

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

    reply_to_screenname = tweet.get('in_reply_to_screen_name')
    reply_to_id = tweet.get('in_reply_to_status_id')
    if reply_to_id and reply_to_screenname:
      activity['context'] = {
        'inReplyTo': [{
          'objectType': 'note',
          'id': self.tag_uri(reply_to_id),
          'url': self.status_url(reply_to_screenname, reply_to_id),
          }]
        }

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
      'objectType': 'note',
      'published': self.rfc2822_to_iso8601(tweet.get('created_at')),
      # don't linkify embedded URLs. (they'll all be t.co URLs.) instead, use
      # entities below to replace them with the real URLs, and then linkify.
      'content': tweet.get('text'),
      'attachments': [],
      }

    user = tweet.get('user')
    if user:
      obj['author'] = self.user_to_actor(user)
      username = obj['author'].get('username')
      if username:
        obj['id'] = self.tag_uri(id)
        obj['url'] = self.status_url(username, id)

      protected = user.get('protected')
      if protected is not None:
        obj['to'] = [{'objectType': 'group',
                      'alias': '@public' if not protected else '@private'}]

    entities = tweet.get('entities', {})

    # currently the media list will only have photos. if that changes, though,
    # we'll need to make this conditional on media.type.
    # https://dev.twitter.com/docs/tweet-entities
    media = entities.get('media')
    if media:
      obj['attachments'] += [{
          'objectType': 'image',
          'image': {'url': m.get('media_url')},
          } for m in media]
      obj['image'] = {'url': media[0].get('media_url')}

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
      # TODO: links are both tags and attachments right now. should they be one
      # or the other?
      # file:///home/ryanb/docs/activitystreams_schema_spec_1.0.html#tags-property
      # file:///home/ryanb/docs/activitystreams_json_spec_1.0.html#object
      {'objectType': 'article',
       'url': t.get('expanded_url'),
       'displayName': t.get('display_url'),
       'indices': t.get('indices'),
       } for t in entities.get('urls', [])
      ] + [
      {'objectType': 'image',
       'url': t.get('media_url'),
       'displayName': '[picture]',
       'indices': t.get('indices'),
       } for t in entities.get('media', [])]

    # sort tags by indices, since they need to be processed (below) in order.
    obj['tags'].sort(key=lambda t: t.get('indices'))

    # convert start/end indices to start/length, and replace t.co URLs with
    # real "display" URLs.
    offset = 0
    for t in obj['tags']:
      indices = t.pop('indices', None)
      if indices:
        start = indices[0] + offset
        end = indices[1] + offset
        length = end - start
        if t['objectType'] in ('article', 'image'):
          text = t.get('displayName') or t.get('url')
          if text:
            obj['content'] = obj['content'][:start] + text + obj['content'][end:]
            offset += len(text) - length
            length = len(text)
        t.update({'startIndex': start, 'length': length})

    # retweets
    obj['tags'] += [self.retweet_to_object(r) for r in tweet.get('retweets', [])]

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

    return self.postprocess_object(obj)

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

    url = user.get('url')
    if url:
      for entity in user.get('entities', {}).get('url', {}).get('urls', []):
        expanded = entity.get('expanded_url')
        if entity['url'] == url and expanded:
          url = expanded
    else:
      url = self.user_url(username)

    image = user.get('profile_image_url_https') or user.get('profile_image_url')
    if image:
      # remove _normal for a ~256x256 avatar rather than ~48x48
      image = image.replace('_normal.', '.', 1)

    return util.trim_nulls({
      'displayName': user.get('name'),
      'image': {'url': image},
      'id': self.tag_uri(username),
      # numeric_id is our own custom field that always has the source's numeric
      # user id, if available.
      'numeric_id': user.get('id_str'),
      'published': self.rfc2822_to_iso8601(user.get('created_at')),
      'url': url,
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

    url = share.get('url')
    content = '<a href="%s">retweeted this.</a>' % url if url else 'retweeted this.'

    share.update({
        'objectType': 'activity',
        'verb': 'share',
        'object': {'url': self.tweet_url(orig)},
        # postprocess_object() populates displayName based on content, but we
        # want to override it to omit the link.
        'displayName': '%s retweeted this.' % self.actor_name(share.get('author')),
        'content': content,
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
    id = self.tag_uri('%s_favorited_by_%s' % (tweet_id, liker_id)) \
        if liker_id else None
    url = self.tweet_url(tweet)
    return self.postprocess_object({
        'id': id,
        'url': url,
        'objectType': 'activity',
        'verb': 'like',
        'object': {'url': url},
        'author': self.user_to_actor(liker),
        'content': 'favorited this.',
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
