"""Unit tests for templates/macros.html."""
from webutil import testutil

from .. import microformats2
from ..source import jinja_macros


class MacrosTest(testutil.TestCase):

  def test_img_blank_alt(self):
    self.assertEqual('<img class="u-photo" src="http://foo" alt="" />',
                      jinja_macros.img('http://foo'))

  def test_value_sanitizes_html(self):
    self.assert_html_equals(
      '<p>a <a href="http://b">b</a> <a>c</a></p>',
      jinja_macros.value({
        'html': '<p onclick="x()">a <a href="http://b">b</a> <a href="javascript:y()">c</a><script>z()</script><iframe src="http://i"></iframe></p>',
      }))

  def test_value_sanitize_keeps_class_rel_microformats_media(self):
    html = """\
<a class="u-mention" rel="tag" href="http://a">a</a>
<data class="p-uid" value="b"></data>
<time class="dt-published" datetime="2022-01-02">c</time>
<video class="u-video" src="http://v" poster="http://p" controls="controls">d</video>
<audio class="u-audio" src="http://au" controls="controls">e</audio>
<a class="u-mention" aria-hidden="true" href="http://f"></a>
<div style="white-space:pre">g</div>
"""
    self.assert_html_equals(html, jinja_macros.value({'html': html}))

  def test_value_sanitize_only_allows_white_space_style(self):
    self.assert_html_equals(
      '<div style="white-space:pre">x</div><p>y</p>',
      jinja_macros.value({'html': '<div style="white-space: pre; background: url(http://z)">x</div><p style="white-space: pre">y</p>'}))

  def test_value_text_escaped_not_sanitized(self):
    self.assertEqual('&lt;script&gt;', jinja_macros.value('<script>'))

  def test_json_to_html_sanitizes_content(self):
    self.assert_html_equals("""\
<article class="h-entry">
<span class="p-uid"></span>
<div class="e-content p-name">
<b>x</b>
</div>
</article>
""", microformats2.json_to_html({
      'type': ['h-entry'],
      'properties': {
        'content': [{'html': '<b onmouseover="y()">x</b><script>z()</script>'}],
      },
    }))

  def test_to_html_sanitize_false(self):
    raw = '<b onmouseover="y()">x</b>'
    hcard = {
      'type': ['h-card'],
      'properties': {'name': [{'html': raw}]},
    }
    entry = {
      'type': ['h-entry'],
      'properties': {
        'author': [hcard],
        'content': [{'html': raw}],
      },
    }
    expected_entry = f"""\
<article class="h-entry">
<span class="p-uid"></span>
<span class="p-author h-card"><span class="p-name">{raw}</span></span>
<div class="e-content p-name">{raw}</div>
</article>
"""
    self.assert_html_equals(expected_entry,
                            microformats2.json_to_html(entry, sanitize=False))
    self.assert_html_equals(
      f'<span class="h-card"><span class="p-name">{raw}</span></span>',
      microformats2.hcard_to_html(hcard, sanitize=False))

    obj = {'objectType': 'note', 'content': raw}
    self.assert_html_equals(f"""\
<article class="h-entry">
<span class="p-uid"></span>
<div class="e-content p-name">{raw}</div>
</article>
""", microformats2.object_to_html(obj, sanitize=False))
    self.assertIn(raw, microformats2.activities_to_html([obj], sanitize=False))

    # default is to sanitize
    self.assertNotIn('onmouseover', microformats2.json_to_html(entry))
    self.assertNotIn('onmouseover', microformats2.hcard_to_html(hcard))
    self.assertNotIn('onmouseover', microformats2.object_to_html(obj))
    self.assertNotIn('onmouseover', microformats2.activities_to_html([obj]))

  def test_render_content_does_not_sanitize(self):
    html = '<b onmouseover="y()">x</b>'
    self.assertEqual(html, microformats2.render_content({'content': html}))

  def test_linked_name_escapes_html(self):
    self.assert_equals(
      '<a class="p-name u-url" href="http://foo">&lt;bar&gt;</a>',
      jinja_macros.linked_name({
        'url': ['http://foo'],
        'name': ['<bar>'],
      }))
