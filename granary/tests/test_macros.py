"""Unit tests for templates/macros.html."""
from webutil import testutil

from ..source import jinja_macros


class MacrosTest(testutil.TestCase):

  def test_img_blank_alt(self):
    self.assertEqual('<img class="u-photo" src="http://foo" alt="" />',
                      jinja_macros.img('http://foo'))

  def test_linked_name_escapes_html(self):
    self.assert_equals(
      '<a class="p-name u-url" href="http://foo">&lt;bar&gt;</a>',
      jinja_macros.linked_name({
        'url': ['http://foo'],
        'name': ['<bar>'],
      }))
