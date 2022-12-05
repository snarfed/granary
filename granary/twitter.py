class Foo():

  def __init__(self, access_token_key, access_token_secret, username=None,
               scrape_headers=None):
    self.access_token_key = access_token_key
    self.access_token_secret = access_token_secret
    self.username = username
    self.scrape_headers = scrape_headers

  def get_actor(self, screen_name=None):
    """Returns a user as a JSON ActivityStreams actor dict.

    Args:
      screen_name: string username. Defaults to the current user.
    """
    url = API_CURRENT_USER if screen_name is None else API_USER % screen_name
    return self.user_to_actor(self.urlopen(url))

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, start_index=0, count=0,
                              etag=None, min_id=None, cache=None,
                              fetch_replies=False, fetch_likes=False,
                              fetch_shares=False, include_shares=True,
                              fetch_events=False, fetch_mentions=False,
                              search_query=None, scrape=False, **kwargs):
    """Fetches posts and converts them to ActivityStreams activities.

    XXX HACK: this is currently hacked for bridgy to NOT pass min_id to the
    request for fetching activity tweets themselves, but to pass it to all of
    the requests for filling in replies, retweets, etc. That's because we want
    to find new replies and retweets of older initial tweets.
    TODO: find a better way.

    See :meth:`source.Source.get_activities_response()` for details. app_id is
    ignored. min_id is translated to Twitter's since_id.

    The code for handling ETags (and 304 Not Changed responses and setting
    If-None-Match) is here, but unused right now since Twitter evidently doesn't
    support ETags. From https://dev.twitter.com/discussions/5800 :
    "I've confirmed with our team that we're not explicitly supporting this
    family of features."

    Likes (nee favorites) are scraped from twitter.com, since Twitter's REST
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
    to, which overloads mentions a bit. When fetch_mentions is True, we determine
    that a tweet mentions the current user if it @-mentions their username and:

    * it's not a reply, OR
    * it's a reply, but not to the current user, AND
      * the tweet it's replying to doesn't @-mention the current user

    Raises:
      NotImplementedError: if fetch_likes is True but scrape_headers was not
        provided to the constructor.
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
