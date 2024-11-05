"""Unit tests for jsonfeed.py."""
from oauth_dropins.webutil import testutil

from ..jsonfeed import from_as1, to_as1


class JsonFeedTest(testutil.TestCase):

  def test_from_as1_empty(self):
    self.assert_equals({
      'version': 'https://jsonfeed.org/version/1.1',
      'title': 'JSON Feed',
    }, from_as1([], {}))

  def test_from_as1_extra_fields(self):
    self.assert_equals({
      'version': 'https://jsonfeed.org/version/1.1',
      'title': 'a something',
      'feed_url': 'http://a/feed',
      'home_page_url': 'http://a/home',
    }, from_as1(
      [], {}, title='a something', feed_url='http://a/feed',
      home_page_url='http://a/home'))

  def test_from_as1_skip_people(self):
    self.assert_equals({
      'version': 'https://jsonfeed.org/version/1.1',
      'title': 'JSON Feed',
    }, from_as1([{
      'objectType': 'person',
      'displayName': 'somebody',
    }], {}))

  def test_from_as1_no_content(self):
    self.assert_equals({
      'version': 'https://jsonfeed.org/version/1.1',
      'title': 'JSON Feed',
      'items': [{
        'image': 'http://no/content',
        'content_text': '',
      }],
    }, from_as1([{
      'image': [{'url': 'http://no/content'}],
    }], {}))

  def test_from_as1_name_is_not_title(self):
    self.assert_equals([{
      'content_html': 'a microblog post',
    }], from_as1([{
      'content': 'a microblog post',
      'displayName': 'a microblog post',
    }], {})['items'])

  def test_from_as1_image_attachment(self):
    self.assert_equals([{
      'content_html': '\n<p>\n<img class="u-photo" src="http://pict/ure.jpg" alt="" />\n</p>',
      'attachments': [{
        'url': 'http://pict/ure.jpg',
        'mime_type': 'image/jpeg',
      }],
    }], from_as1([{
      'attachments': [{'image': {'url': 'http://pict/ure.jpg'}}],
    }], {})['items'])

  def test_from_as1_ignore_other_attachment_types(self):
    self.assert_equals([{
      'content_html': '\n<p>\n<a class="link" href="http://some/one">\n</a>\n</p>'
    }], from_as1([{
      'attachments': [{
        'url': 'http://quoted/tweet',
        'objectType': 'note',
      }, {
        'url': 'http://some/one',
        'objectType': 'person',
      }],
    }], {})['items'])

  def test_from_as1_attachment_without_url(self):
    self.assert_equals([{'content_text': ''}], from_as1([{
      'attachments': [{
        'content': 'foo',
        'objectType': 'note',
      }],
    }], {})['items'])

  def test_from_as1_image_not_dict(self):
    """
    https://console.cloud.google.com/errors/detail/CMnZ6r6AlaXUSg;time=P30D?project=granary-demo
    """
    self.assert_equals([{'content_html': """
<p>
<img class="u-photo" src="https://att/image" alt="" />
</p>"""}], from_as1([{
      'attachments': [{
        'image': 'https://att/image',
      }],
    }], {})['items'])

  def test_from_as1_not_list(self):
    for bad in None, 3, 'asdf', {'not': 'a list'}:
      with self.assertRaises(TypeError):
        from_as1(bad)

  def test_from_as1_string_object_actor(self):
    self.assert_equals([{
      'id': 'http://example.com/original/post',
      'content_text': '',
    }], from_as1([{
      'objectType': 'activity',
      'verb': 'like',
      'object': 'http://example.com/original/post',
      'actor': 'http://example.com/author-456'
    }])['items'])

  def test_from_as1_note_article(self):
    activities, _ = to_as1({
      'version': 'https://jsonfeed.org/version/1.1',
      'title': 'JSON Feed',
      'items': [{
        'content_text': 'foo bar',
        'authors': [{
          'name': 'Alice',
          'url': 'http://it/me',
          'avatar': 'http://my/pic.jpg',
        }],
      }, {
        'id': 'http://my/article',
        'title': 'a thing I wrote',
        'content_html': 'its <em>gud</em>',
        'url': 'http://read/this',
      }],
    })

    self.assert_equals([{
      'objectType': 'note',
      'content': 'foo bar',
      'author': {
        'displayName': 'Alice',
        'url': 'http://it/me',
        'image': 'http://my/pic.jpg',
      },
    }, {
      'objectType': 'article',
      'id': 'http://my/article',
      'title': 'a thing I wrote',
      'content': 'its <em>gud</em>',
      'url': 'http://read/this',
    }], activities)

  def test_to_as1_attachment_extra_list(self):
    """Originally seen in:
    https://console.cloud.google.com/errors/CPyvpeH077rvIg
    https://www.macstories.net/feed/json
    """
    with self.assertRaises(ValueError):
      to_as1({
        'items': [{
          'attachments': [[{'content': 'foo'}]],
        }]
      })

  def test_to_as1_not_jsonfeed(self):
    """Based on this JSON, which isn't JSON Feed:

    http://blogs.adobe.com/adobemarketingcloudjapan/feed-json-adobemarketingcloudjapan/

    https://console.cloud.google.com/errors/2337929195804363905
    """
    with self.assertRaises(ValueError):
      to_as1([{
        'id': 7,
        'date': 'July 11, 2017',
        'title': 'Adobe Digital Insights: 音声認識機能は次の破壊的技術革新となるか',
        'catname': 'Adobe Digital Insights',
        'tags': 'ADI',
        'description': '音声認識機能は新しいコンセプトではありませんが、人工知能 (AI) とマシンラーニングの進歩により、近年採用される機会が増えています。アドビが公開したAdobe Digital Insights (ADI) の最新のレポートによると、音声認識デバイスの市場競争が激化していることが明らかになりました。',
        'subdescription': '音声認識機能は新しいコンセプトではありませんが、人工知能 (AI) とマシンラーニングの進歩により、近年採用される機会が増えています。アドビが公開したAdobe Digital Insights (ADI) の最新のレポートによると、音声認識デバイスの市場競争が激化していることが明らかになりました。',
        'document': 'http://blogs.adobe.com/adobemarketingcloudjapan/2017/07/11/adi-voice-report/',
        'iconUrl': 'http://blogs.adobe.com/adobemarketingcloudjapan/files/2017/07/1046x616_Voice-Assistants-Are-Poised-To-Be-The-Next-Tech-Disruptor-Static-1024x603.jpg'
      }])

  def test_to_as1_author_not_dict(self):
    """Based on output from https://rss2json.com/

    https://console.cloud.google.com/errors/detail/COO65cat_4niTQ?project=granary-demo
    """
    with self.assertRaises(ValueError):
      to_as1({'items': [{'authors': ['Ms. Foo']}]})

  def test_from_as1_author_not_dict(self):
    """https://console.cloud.google.com/errors/detail/CN-yh-3M7crdLA;time=P30D?project=granary-demo"""
    self.assertEqual({
      'version': 'https://jsonfeed.org/version/1.1',
      'title': 'JSON Feed',
      'items': [{
        'content_text': '',
      }],
    }, from_as1([{
      'author': 'http://foo',
    }]))

  def test_convert_newlines_to_brs(self):
    """https://github.com/snarfed/granary/issues/456"""
    got = from_as1([{
      'content': 'foo\nbar\nbaz',
    }])
    self.assert_equals("""\
foo<br />
bar<br />
baz
""", got['items'][0]['content_html'])
