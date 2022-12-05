class Foo():

  def __init__(self):
    self.access_token_key = access_token_key

  def get_activities_response(self):
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
    """
    if fetch_likes and not self.scrape_headers:
        raise NotImplementedError('fetch_likes requires scrape_headers')
