# coding=utf-8
"""Unit tests for source.py.

Most of the tests are in testdata/. This is just a few things that are too small
for full testdata tests.
"""

__author__ = ['Ryan Barrett <granary@ryanb.org>']

import re

from oauth_dropins.webutil import testutil
import mf2py

from granary import microformats2


class Microformats2Test(testutil.HandlerTest):

  def test_post_type_discovery(self):
    for prop, verb in ('like-of', 'like'), ('repost-of', 'share'):
      obj = microformats2.json_to_object(
        {'type': ['h-entry'],
          'properties': {prop: ['http://foo/bar']}})
      self.assertEquals('activity', obj['objectType'])
      self.assertEquals(verb, obj['verb'])

  def test_verb_require_of_suffix(self):
    for prop in 'like', 'repost':
      obj = microformats2.json_to_object(
        {'type': ['h-entry'],
         'properties': {prop: ['http://foo/bar']}})
      self.assertNotIn('verb', obj)

  def test_ignore_h_as(self):
    """https://github.com/snarfed/bridgy/issues/635"""
    obj = microformats2.json_to_object({'type': ['h-entry']})
    self.assertEquals('note', obj['objectType'])

  def test_html_content_and_summary(self):
    for expected_content, expected_summary, value in (
        ('my html', 'my val', {'value': 'my val', 'html': 'my html'}),
        ('my html', None, {'html': 'my html'}),
        ('my val', 'my val', {'value': 'my val'}),
        ('my str', 'my str', 'my str'),
        (None, None, {})):
      obj = microformats2.json_to_object({'properties': {'content': [value],
                                                         'summary': [value]}})
      self.assertEquals(expected_content, obj.get('content'))
      self.assertEquals(expected_summary, obj.get('summary'))

  def test_photo_property_is_not_url(self):
    """handle the case where someone (incorrectly) marks up the caption
    with p-photo
    """
    mf2 = {'properties':
           {'photo': ['the caption', 'http://example.com/image.jpg']}}
    obj = microformats2.json_to_object(mf2)
    self.assertEquals([{'url': 'http://example.com/image.jpg'}], obj['image'])

  def test_photo_property_has_no_url(self):
    """handle the case where the photo property is *only* text, not a url"""
    mf2 = {'properties':
           {'photo': ['the caption', 'alternate text']}}
    obj = microformats2.json_to_object(mf2)
    self.assertFalse(obj.get('image'))

  def test_video_stream(self):
    """handle the case where someone (incorrectly) marks up the caption
    with p-photo
    """
    mf2 = {'properties':
           {'video': ['http://example.com/video.mp4']}}
    obj = microformats2.json_to_object(mf2)
    self.assertEquals([{'url': 'http://example.com/video.mp4'}], obj['stream'])

  def test_nested_compound_url_object(self):
    mf2 = {'properties': {
             'repost-of': [{
               'type': ['h-outer'],
               'properties': {
                 'url': [{
                   'type': ['h-inner'],
                   'properties': {'url': ['http://nested']},
                 }],
               },
             }],
           }}
    obj = microformats2.json_to_object(mf2)
    self.assertEquals('http://nested', obj['object']['url'])

  def test_object_to_json_unescapes_html_entities(self):
    self.assertEquals({
      'type': ['h-entry'],
      'properties': {'content': [{
        'html': 'Entity &lt; <a href="http://my/link">link too</a>',
        'value': 'Entity < link too',
      }]},
     }, microformats2.object_to_json({
       'verb': 'post',
       'object': {
        'content': 'Entity &lt; link too',
        'tags': [{'url': 'http://my/link', 'startIndex': 12, 'length': 8}]
       }
     }))

  def test_object_to_json_note_with_in_reply_to(self):
    self.assertEquals({
      'type': ['h-entry'],
      'properties': {
        'content': [{
          'html': '@hey great post',
          'value': '@hey great post',
        }],
        'in-reply-to': ['http://reply/target'],
      },
    }, microformats2.object_to_json({
      'verb': 'post',
      'object': {
        'content': '@hey great post',
      },
      'context': {
        'inReplyTo': [{
          'url': 'http://reply/target',
        }],
      }}))

  def test_object_to_json_preserves_url_order(self):
    self.assertEquals({
      'type': ['h-card'],
      'properties': {
        'url': ['http://2', 'http://4', 'http://6'],
      },
    }, microformats2.object_to_json({
      'objectType': 'person',
      'url': 'http://2',
      'urls': [{'value': 'http://4'},
               {'value': 'http://6'}],
    }))

  def test_object_to_html_note_with_in_reply_to(self):
    expected = """\
<article class="h-entry">
<span class="p-uid"></span>
<div class="e-content p-name">
@hey great post
</div>
<a class="u-in-reply-to" href="http://reply/target"></a>
</article>
"""
    result = microformats2.object_to_html({
      'verb': 'post',
      'context': {
        'inReplyTo': [{
          'url': 'http://reply/target',
        }],
      },
      'object': {
        'content': '@hey great post',
      }
    })
    self.assertEquals(re.sub('\n\s*', '\n', expected),
                      re.sub('\n\s*', '\n', result))

  def test_render_content_link_with_image(self):
    self.assert_equals("""\
foo
<p>
<a class="link" href="http://link">
<img class="thumbnail" src="http://image" alt="name" />
<span class="name">name</span>
</a>
</p>""", microformats2.render_content({
        'content': 'foo',
        'tags': [{
          'objectType': 'article',
          'url': 'http://link',
          'displayName': 'name',
          'image': {'url': 'http://image'},
        }]
      }))

  def test_render_content_multiple_image_attachments(self):
    self.assert_equals("""\
foo
<p>
<img class="thumbnail" src="http://1" alt="" />
</p>
<p>
<img class="thumbnail" src="http://2" alt="" />
</p>""", microformats2.render_content({
        'content': 'foo',
        'attachments': [
          {'objectType': 'image', 'image': {'url': 'http://1'}},
          {'objectType': 'image', 'image': {'url': 'http://2'}},
        ]
      }))

  def test_render_content_converts_newlines_to_brs(self):
    self.assert_equals("""\
foo<br />
bar<br />
<a href="http://baz">baz</a>
""", microformats2.render_content({
  'content': 'foo\nbar\nbaz',
  'tags': [{'url': 'http://baz', 'startIndex': 8, 'length': 3}]
}))

  def test_render_content_omits_tags_without_urls(self):
    self.assert_equals("""\
foo
<a class="tag" href="http://baj"></a>
<a class="tag" href="http://baz">baz</a>
""", microformats2.render_content({
        'content': 'foo',
        'tags': [{'displayName': 'bar'},
                 {'url': 'http://baz', 'displayName': 'baz'},
                 {'url': 'http://baj'},
               ],
      }))

  def test_render_content_location(self):
    self.assert_equals("""\
foo
<span class="p-location h-card">
  <a class="p-name u-url" href="http://my/place">My place</a>

</span>
""", microformats2.render_content({
        'content': 'foo',
        'location': {
          'displayName': 'My place',
          'url': 'http://my/place',
        }
      }))

  def test_render_content_synthesize_content(self):
    for verb, phrase in ('like', 'likes'), ('share', 'shared'):
      obj = {
        'verb': verb,
        'object': {'url': 'http://orig/post'},
      }
      self.assert_equals('<a href="http://orig/post">%s this.</a>' % phrase,
                         microformats2.render_content(obj, synthesize_content=True))
      self.assert_equals('',
                         microformats2.render_content(obj, synthesize_content=False))

      obj['content'] = 'Message from actor'
      for val in False, True:
        self.assert_equals(obj['content'],
                           microformats2.render_content(obj, synthesize_content=val))

  def test_render_content_video(self):
    self.assert_equals("""\
foo
<p><video class="thumbnail" src="http://vid/eo" poster="http://im/age" controls="controls">Your browser does not support the video tag. <a href="http://vid/eo">Click here to view directly<img src="http://im/age"/></a></video>
</p>
""", microformats2.render_content({
      'content': 'foo',
      'attachments': [{
        'image': [{'url': 'http://im/age'}],
        'stream': [{'url': 'http://vid/eo'}],
        'objectType': 'video',
      }],
    }))

  def test_render_content_unicode_high_code_points(self):
    """Test Unicode high code point chars.

    The first three unicode chars in the content are the '100' emoji, which is a
    high code point, ie above the Basic Multi-lingual Plane (ie 16 bits). The
    emacs font i use doesn't render it, so it looks blank.

    First discovered in https://twitter.com/schnarfed/status/831552681210556416
    """
    self.assert_equals(
      u'💯💯💯 (by <a href="https://twitter.com/itsmaeril">@itsmaeril</a>)',
      microformats2.render_content({
        'content': u'💯💯💯 (by @itsmaeril)',
        'tags': [{
          'displayName': 'Maeril',
          'objectType': 'person',
          'startIndex': 8,
          'length': 10,
          'url': 'https://twitter.com/itsmaeril',
        }]}))

  def test_escape_html_attribute_values(self):
    self.assert_equals("""\
<article class="h-entry">
<span class="p-uid"></span>

<span class="p-author h-card">
<span class="p-name">a " b ' c</span>
<img class="u-photo" src="img" alt="" />
</span>

<div class="e-content p-name">

<p>
<img class="thumbnail" src="img" alt="d &amp; e" />
<span class="name">d & e</span>
</p>
</div>

</article>""", microformats2.object_to_html({
        'author': {'image': {'url': 'img'}, 'displayName': 'a " b \' c'},
        'attachments': [{'image': {'url': 'img'}, 'displayName': 'd & e'}],
      }))

  def test_mention_and_hashtag(self):
    self.assert_equals("""
<a class="p-category" href="http://c"></a>
<a class="u-mention" href="http://m">m</a>""",
                       microformats2.render_content({
        'tags': [{'objectType': 'mention', 'url': 'http://m', 'displayName': 'm'},
                 {'objectType': 'hashtag', 'url': 'http://c'}],
      }))

  def test_tag_multiple_urls(self):
    expected_urls = ['http://1', 'https://2']
    expected_html = """
<a class="tag" href="http://1"></a>
<a class="tag" href="https://2"></a>
"""
    for tag in ({'url': 'http://1',
                  'urls': [{'value': 'http://1'}, {'value': 'https://2'}]},
                {'url': 'http://1',
                 'urls': [{'value': 'https://2'}]},
                {'urls': [{'value': 'http://1'}, {'value': 'https://2'}]}):
      self.assert_equals(expected_urls,
                         microformats2.object_to_json(tag)['properties']['url'],
                         tag)
      self.assert_equals(expected_html,
                         microformats2.render_content({'tags': [tag]}),
                         tag)

  def test_dont_render_images_inside_non_image_attachments(self):
    self.assert_equals('my content', microformats2.render_content({
       'content': 'my content',
       'attachments': [{
         'objectType': 'note',
         'image': {'url': 'http://attached/image'},
       }],
    }))

  def test_dont_stop_at_unknown_tag_type(self):
    obj = {'tags': [
      {'objectType': 'x', 'url': 'http://x'},
      {'objectType': 'person', 'url': 'http://p', 'displayName': 'p'}],
    }
    self.assert_equals({
      'type': ['h-entry'],
      'properties': {
        'category': [{
          'type': ['h-card'],
          'properties': {
            'name': ['p'],
            'url': ['http://p'],
          },
        }],
        'content': [{'html': '\n<a class="tag" href="http://x"></a>'}],
      },
    }, microformats2.object_to_json(obj))

  def test_attachments_to_children(self):
    obj = {'attachments': [
      {'objectType': 'note', 'url': 'http://p', 'displayName': 'p'},
      {'objectType': 'x', 'url': 'http://x'},
      {'objectType': 'article', 'url': 'http://a'},
    ]}

    self.assert_equals([{
      'type': ['u-quotation-of', 'h-cite'],
      'properties': {'url': ['http://p'], 'name': ['p']},
    }, {
      'type': ['u-quotation-of', 'h-cite'],
      'properties': {'url': ['http://a']},
    }], microformats2.object_to_json(obj)['children'])

    html = microformats2.object_to_html(obj)
    self.assert_multiline_in("""\
<article class="u-quotation-of h-cite">
<span class="p-uid"></span>

<a class="p-name u-url" href="http://p">p</a>
<div class="">

</div>

</article>

<article class="u-quotation-of h-cite">
<span class="p-uid"></span>

<a class="u-url" href="http://a">http://a</a>
<div class="">

</div>

</article>
""", html)

  def test_object_to_json_reaction(self):
    self.assert_equals({
      'type': ['h-entry'],
      'properties': {
        'content': [{'html': u'✁', 'value': u'✁'}],
        'in-reply-to': ['https://orig/post'],
      },
    }, microformats2.object_to_json({
      'objectType': 'activity',
      'verb': 'react',
      'content': u'✁',
      'object': {'url': 'https://orig/post'},
    }))

  def test_object_to_json_multiple_object_urls(self):
    self.assert_equals({
      'type': ['h-entry'],
      'properties': {
        'content': [{'html': u'✁', 'value': u'✁'}],
        'in-reply-to': ['https://orig/post/1', 'https://orig/post/2'],
      },
    }, microformats2.object_to_json({
      'objectType': 'activity',
      'verb': 'react',
      'content': u'✁',
      'object': [
        {'url': 'https://orig/post/1'},
        {'url': 'https://orig/post/2'},
      ],
    }))

  def test_object_to_json_not_dict(self):
    """This can happen if we get a dict instead of a list, e.g. with AS 2.0.

    Found via AS2 on http://evanminto.com/indieweb/activity-stream.php, e.g.:

    {
      "@context": "https://www.w3.org/ns/activitystreams",
      "0": {
        "name": "Evan reposted another post.",
        "type": "Announce",
        "actor": {
          "type": "Person",
          "name": "Evan Minto",
          "url": "http://evanminto.com"
        },
        "object": "http://www.harkavagrant.com/index.php?id=402"
      },
    ...
    """
    self.assert_equals({}, microformats2.object_to_json('foo bar'))

  def test_get_string_urls(self):
    for expected, objs in (
        ([], []),
        (['asdf'], ['asdf']),
        ([], [{'type': 'h-ok'}]),
        ([], [{'properties': {'url': ['nope']}}]),
        ([], [{'type': ['h-ok'], 'properties': {'no': 'url'}}]),
        (['good1', 'good2'], ['good1',
                            {'type': ['h-ok']},
                            {'type': ['h-ok'], 'properties': {'url': ['good2']}}]),
        (['nested'], [{'type': ['h-ok'], 'properties': {'url': [
            {'type': ['h-nested'], 'url': ['nested']}]}}]),
        ):
      self.assertEquals(expected, microformats2.get_string_urls(objs))

  def test_img_blank_alt(self):
    self.assertEquals('<img class="bar" src="foo" alt="" />',
                      microformats2.img('foo', 'bar', None))

  def test_json_to_html_no_properties_or_type(self):
    # just check that we don't crash
    microformats2.json_to_html({'x': 'y'})

  def test_json_to_object_with_location_hcard(self):
    obj = microformats2.json_to_object({
      'type': ['h-entry'],
      'properties': {
        'location': [{
          'type': ['h-card'],
          'properties': {
            'name': ['Timeless Coffee Roasters'],
            'locality': ['Oakland'],
            'region': ['California'],
            'latitude': ['50.820641'],
            'longitude': ['-0.149522'],
            'url': ['https://kylewm.com/venues/timeless-coffee-roasters-oakland-california'],
          },
          'value': 'Timeless Coffee Roasters',
        }],
      }})
    self.assertEquals({
      'objectType': 'place',
      'latitude': 50.820641,
      'longitude': -0.149522,
      'displayName': 'Timeless Coffee Roasters',
      'url': 'https://kylewm.com/venues/timeless-coffee-roasters-oakland-california',
    }, obj['location'])

  def test_json_to_object_with_location_geo(self):
    self._test_json_to_object_with_location({
      'location': [{
        'type': ['h-geo'],
        'properties': {
          'latitude': ['50.820641'],
          'longitude': ['-0.149522'],
        }
      }],
    })

  def test_json_to_object_with_geo(self):
    self._test_json_to_object_with_location({
      'geo': [{
        'properties': {
          'latitude': ['50.820641'],
          'longitude': ['-0.149522'],
        },
      }]
    })

  def test_json_to_object_with_geo_url(self):
    self._test_json_to_object_with_location({
      'geo': ['geo:50.820641,-0.149522;foo=bar'],
    })

  def test_json_to_object_with_lat_lon_top_level(self):
    self._test_json_to_object_with_location({
      'latitude': ['50.820641'],
      'longitude': ['-0.149522'],
    })

  def _test_json_to_object_with_location(self, props):
    obj = microformats2.json_to_object({
      'type': ['h-entry'],
      'properties': props,
    })
    self.assertEquals({
      'latitude': 50.820641,
      'longitude': -0.149522,
      'objectType': 'place',
    }, obj.get('location'))

  def test_json_to_object_with_categories(self):
    obj = microformats2.json_to_object({
      'type': ['h-entry'],
      'properties': {
        'category': [
          {
            'type': ['h-card'],
            'properties': {
              'name': ['Kyle Mahan'],
              'url': ['https://kylewm.com'],
            },
          },
          'cats',
          'indieweb']
      },
    })

    self.assertEquals([
      {
        'objectType': 'person',
        'displayName': 'Kyle Mahan',
        'url': 'https://kylewm.com',
      },
      {
        'objectType': 'hashtag',
        'displayName': 'cats',
      },
      {
        'objectType': 'hashtag',
        'displayName': 'indieweb',
      },
    ], obj.get('tags'))

  def test_json_to_object_converts_text_newlines_to_brs(self):
    """Text newlines should be converted to <br>s."""
    self.assert_equals({
      'objectType': 'note',
      'content': 'asdf\nqwer',
    }, microformats2.json_to_object({
      'properties': {'content': [{'value': 'asdf\nqwer'}]},
    }))

  def test_json_to_object_drops_html_newlines(self):
    """HTML newlines should be discarded."""
    self.assert_equals({
      'objectType': 'note',
      'content': 'asdf qwer',
    }, microformats2.json_to_object({
      'properties': {'content': [{'html': 'asdf\nqwer', 'value': ''}]},
    }))

  def test_find_author(self):
    self.assert_equals({
    'displayName': 'my name',
    'url': 'http://li/nk',
    'image': {'url': 'http://pic/ture'},
  }, microformats2.find_author(mf2py.parse(doc="""\
<body class="h-entry">
<div class="p-author h-card">
<a href="http://li/nk">my name</a>
<img class="u-photo" src="http://pic/ture" />
</div>
</body>
""", url='http://123')))

  def test_object_urls(self):
    for expected, actor in (
        ([], {}),
        ([], {'displayName': 'foo'}),
        ([], {'url': None, 'urls': []}),
        (['http://foo'], {'url': 'http://foo'}),
        (['http://foo'], {'urls': [{'value': 'http://foo'}]}),
        (['http://foo', 'https://bar', 'http://baz'], {
          'url': 'http://foo',
          'urls': [{'value': 'https://bar'},
                   {'value': 'http://foo'},
                   {'value': 'http://baz'},
          ],
        }),
    ):
      self.assertEquals(expected, microformats2.object_urls(actor))

  def test_hcard_to_html_no_properties(self):
    self.assertEquals('', microformats2.hcard_to_html({}))
    self.assertEquals('', microformats2.hcard_to_html({'properties': {}}))
