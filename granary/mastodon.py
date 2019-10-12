# coding=utf-8
"""Mastodon source class.

Mastodon is an ActivityPub implementation, but it also has a REST + OAuth 2 API
independent of AP. API docs: https://docs.joinmastodon.org/api/
"""
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()

import urllib.parse

from oauth_dropins.webutil import util
import ujson as json

from . import appengine_config
from . import as2
from . import source

API_STATUSES = '/api/v1/statuses'


class Mastodon(source.Source):
  """Mastodon source class. See file docstring and Source class for details.

  Attributes:
    instance: string, base URL of Mastodon instance, eg https://mastodon.social/
    access_token: string, optional, OAuth access token
  """
  DOMAIN = 'N/A'
  BASE_URL = 'N/A'
  NAME = 'Mastodon'

  # https://docs.joinmastodon.org/usage/basics/#text
  TRUNCATE_TEXT_LENGTH = 500
  TRUNCATE_URL_LENGTH = 23

  def __init__(self, instance, username=None, access_token=None):
    """Constructor.

    Args:
      instance: string, base URL of Mastodon instance, eg https://mastodon.social/
      username: string, optional, current user's username on this instance
      access_token: string, optional OAuth access token
    """
    assert instance
    self.instance = instance
    self.username = username
    self.access_token = access_token

  def user_url(self, username):
    return urllib.parse.urljoin(self.instance, '@' + username)

  def api(self, path, *args, **kwargs):
    headers = kwargs.setdefault('headers', {})
    headers['Authorization'] = 'Bearer ' + self.access_token

    url = urllib.parse.urljoin(self.instance, path)
    resp = util.requests_post(url, *args, **kwargs)
    try:
      resp.raise_for_status()
    except BaseException as e:
      util.interpret_http_exception(e)
      raise
    return resp

  def get_activities_response(self, user_id=None, group_id=None, app_id=None,
                              activity_id=None, fetch_replies=False,
                              fetch_likes=False, fetch_shares=False,
                              fetch_events=False, fetch_mentions=False,
                              search_query=None, **kwargs):
    """Fetches toots and converts them to ActivityStreams activities.

    See :meth:`Source.get_activities_response` for details.
    """
    if (fetch_shares or fetch_events or fetch_mentions or search_query or
        group_id or user_id or activity_id):
      raise NotImplementedError()

    assert self.username
    # XXX TODO: brittle
    url = urllib.parse.urljoin(self.instance,
                               '/users/%s/outbox?page=true' % self.username)
    resp = util.requests_get(url, headers=as2.CONNEG_HEADERS)
    activities = [as2.to_as1(a) for a in
                  json.loads(resp.text).get('orderedItems', [])]

    response = self.make_activities_base_response(util.trim_nulls(activities))
    return response

  def create(self, obj, include_link=source.OMIT_LINK,
             ignore_formatting=False):
    """Creates a status (aka toot), reply, boost (aka reblog), or favorite.

    https://docs.joinmastodon.org/api/rest/statuses/

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns: CreationResult whose content will be a dict with 'id', 'url', and
      'type' keys (all optional) for the newly created object (or None)
    """
    return self._create(obj, preview=False, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def preview_create(self, obj, include_link=source.OMIT_LINK,
                     ignore_formatting=False):
    """Preview creating a status (aka toot), reply, boost (aka reblog), or favorite.

    https://docs.joinmastodon.org/api/rest/statuses/

    Args:
      obj: ActivityStreams object
      include_link: string
      ignore_formatting: boolean

    Returns: CreationResult whose content will be a unicode string HTML
      snippet (or None)
    """
    return self._create(obj, preview=True, include_link=include_link,
                        ignore_formatting=ignore_formatting)

  def _create(self, obj, preview=None, include_link=source.OMIT_LINK,
              ignore_formatting=False):
    """Creates or previews a status (aka toot), reply, boost (aka reblog), or favorite.

    https://docs.joinmastodon.org/api/rest/statuses/

    Args:
      obj: ActivityStreams object
      preview: boolean
      include_link: string
      ignore_formatting: boolean

    Returns: CreationResult. If preview is True, the content will be a unicode
      string HTML snippet. If False, it will be a dict with 'id' and 'url' keys
      for the newly created object.
    """
    assert preview in (False, True)
    type = obj.get('objectType')
    verb = obj.get('verb')

    base_obj = self.base_object(obj)
    base_id = base_obj.get('id')
    base_url = base_obj.get('url')

    is_reply = type == 'comment' or 'inReplyTo' in obj
    is_rsvp = (verb and verb.startswith('rsvp-')) or verb == 'invite'
    # images = util.get_list(obj, 'image')
    # video_url = util.get_first(obj, 'stream', {}).get('url')
    # has_media = (images or video_url) and (type in ('note', 'article') or is_reply)

    # prefer displayName over content for articles
    type = obj.get('objectType')
    prefer_content = type == 'note' or (base_url and (type == 'comment'
                                                      or obj.get('inReplyTo')))
    preview_description = ''
    quote_tweet_url = None
#     for att in obj.get('attachments', []):
#       url = self.URL_CANONICALIZER(att.get('url', ''))
#       if url and TWEET_URL_RE.match(url):
#         quote_tweet_url = url
#         preview_description += """\
# <span class="verb">quote</span>
# <a href="%s">this tweet</a>:<br>
# %s
# <br>and """ % (url, self.embed_post(att))
#         break

    content = self._content_for_create(
      obj, ignore_formatting=ignore_formatting, prefer_name=not prefer_content)
      # strip_first_video_tag=bool(video_url), strip_quotations=bool(quote_tweet_url))

    if not content:
      if type == 'activity' and not is_rsvp:
        content = verb
      # elif has_media:
      #   content = ''
      else:
        return source.creation_result(
          abort=False,  # keep looking for things to publish,
          error_plain='No content text found.',
          error_html='No content text found.')

#     if is_reply and base_url:
#       # Twitter *used* to require replies to include an @-mention of the
#       # original tweet's author
#       # https://dev.twitter.com/docs/api/1.1/post/statuses/update#api-param-in_reply_to_status_id
#       # ...but now we use the auto_populate_reply_metadata query param instead:
#       # https://dev.twitter.com/overview/api/upcoming-changes-to-tweets

#       # the embed URL in the preview can't start with mobile. or www., so just
#       # hard-code it to twitter.com. index #1 is netloc.
#       parsed = urllib.parse.urlparse(base_url)
#       parts = parsed.path.split('/')
#       if len(parts) < 2 or not parts[1]:
#         raise ValueError('Could not determine author of in-reply-to URL %s' % base_url)
#       reply_to_prefix = '@%s ' % parts[1].lower()
#       if content.lower().startswith(reply_to_prefix):
#         content = content[len(reply_to_prefix):]

#       parsed = list(parsed)
#       parsed[1] = self.DOMAIN
#       base_url = urllib.parse.urlunparse(parsed)

#     # need a base_url with the tweet id for the embed HTML below. do this
#     # *after* checking the real base_url for in-reply-to author username.
#     if base_id and not base_url:
#       base_url = 'https://twitter.com/-/statuses/' + base_id

#     if is_reply and not base_url:
#       return source.creation_result(
#         abort=True,
#         error_plain='Could not find a tweet to reply to.',
#         error_html='Could not find a tweet to <a href="http://indiewebcamp.com/reply">reply to</a>. '
#         'Check that your post has an <a href="http://indiewebcamp.com/comment">in-reply-to</a> '
#         'link a Twitter URL or to an original post that publishes a '
#         '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

    # truncate and ellipsize content if it's over the character
    # count. URLs will be t.co-wrapped, so include that when counting.
    content = self.truncate(content, obj.get('url'), include_link, type)
                             # quote_tweet=quote_tweet_url)

    # linkify defaults to Twitter's link shortening behavior
    preview_content = util.linkify(content, pretty=True, skip_bare_cc_tlds=True)
    # TODO
    # preview_content = MENTION_RE.sub(
    #   r'\1<a href="https://twitter.com/\2">@\2</a>', preview_content)
    # preview_content = HASHTAG_RE.sub(
    #   r'\1<a href="https://twitter.com/hashtag/\2">#\2</a>', preview_content)

#     if type == 'activity' and verb == 'like':
#       if not base_url:
#         return source.creation_result(
#           abort=True,
#           error_plain='Could not find a tweet to like.',
#           error_html='Could not find a tweet to <a href="http://indiewebcamp.com/favorite">favorite</a>. '
#           'Check that your post has a like-of link to a Twitter URL or to an original post that publishes a '
#           '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

#       if preview:
#         preview_description += """\
# <span class="verb">favorite</span>
# <a href="%s">this tweet</a>:
# %s""" % (base_url, self.embed_post(base_obj))
#         return source.creation_result(description=preview_description)
#       else:
#         data = urllib.parse.urlencode({'id': base_id})
#         self.urlopen(API_POST_FAVORITE, data=data)
#         resp = {'type': 'like'}

#     elif type == 'activity' and verb == 'share':
#       if not base_url:
#         return source.creation_result(
#           abort=True,
#           error_plain='Could not find a tweet to retweet.',
#           error_html='Could not find a tweet to <a href="http://indiewebcamp.com/repost">retweet</a>. '
#           'Check that your post has a repost-of link to a Twitter URL or to an original post that publishes a '
#           '<a href="http://indiewebcamp.com/rel-syndication">rel-syndication</a> link to Twitter.')

#       if preview:
#           preview_description += """\
# <span class="verb">retweet</span>
# <a href="%s">this tweet</a>:
# %s""" % (base_url, self.embed_post(base_obj))
#           return source.creation_result(description=preview_description)
#       else:
#         data = urllib.parse.urlencode({'id': base_id})
#         resp = self.urlopen(API_POST_RETWEET % base_id, data=data)
#         resp['type'] = 'repost'

    if type in ('note', 'article') or is_reply or is_rsvp:  # a post
      data = {'status': content}

      if is_reply:
        preview_description += """\
<span class="verb">@-reply</span> to <a href="%s">this toot</a>:
%s""" % (base_url, self.embed_post(base_obj))
        data['in_reply_to_status_id'] = base_id
      else:
        preview_description += '<span class="verb">toot</span>:'

#       if video_url:
#         preview_content += ('<br /><br /><video controls src="%s"><a href="%s">'
#                             'this video</a></video>' % (video_url, video_url))
#         if not preview:
#           ret = self.upload_video(video_url)
#           if isinstance(ret, source.CreationResult):
#             return ret
#           data.append(('media_ids', ret))

#       elif images:
#         num = len(images)
#         if num > MAX_MEDIA:
#           images = images[:MAX_MEDIA]
#           logging.warning('Found %d photos! Only using the first %d: %r',
#                           num, MAX_MEDIA, images)
#         preview_content += '<br /><br />' + ' &nbsp; '.join(
#           '<img src="%s" alt="%s" />' % (img.get('url'), img.get('displayName', ''))
#                                          for img in images)
#         if not preview:
#           ret = self.upload_images(images)
#           if isinstance(ret, source.CreationResult):
#             return ret
#           data.append(('media_ids', ','.join(ret)))

      if preview:
        return source.creation_result(content=preview_content,
                                      description=preview_description)
      else:
        resp = json.loads(self.api(API_STATUSES, json=data).text)
        resp['type'] = 'comment' if is_reply else 'post'

    else:
      return source.creation_result(
        abort=False,
        error_plain='Cannot publish type=%s, verb=%s to Mastodon' % (type, verb),
        error_html='Cannot publish type=%s, verb=%s to Mastodon' % (type, verb))

    if 'url' not in resp:
      resp['url'] = base_url

    return source.creation_result(resp)
