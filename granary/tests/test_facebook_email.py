# coding=utf-8
"""Unit tests for facebook_email.py.
"""
from __future__ import unicode_literals
from future import standard_library
standard_library.install_aliases()

from datetime import datetime

from oauth_dropins.webutil import testutil
from oauth_dropins.webutil import util

from granary import appengine_config
from granary import facebook_email

# test data
def tag_uri(name):
  return util.tag_uri('facebook.com', name)

# HTML
COMMENT_EMAIL = """\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional //EN">
<html>
  <head>
    <title>Facebook
    </title>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <style>...</style>
  </head>
  <body dir="ltr" bgcolor="#ffffff">
    <table border="0" cellspacing="0" cellpadding="0" align="center" id="email_table">
      <tr>
        <td id="email_content">
          <table border="0" width="100%" cellspacing="0" cellpadding="0">
            <tr>
              <td height="1" colspan="3">
                <span>Ryan Barrett wrote: &quot;test comment foo bar baz&quot;  -  Reply to this email to comment on this post.
                </span>
              </td>
            </tr>
            <tr>
              <td width="15">&nbsp;&nbsp;&nbsp;
              </td>
              <td>
                <table border="0" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td width="32" align="left" valign="middle">
                      <a href="https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com">
                        <img src="https://static.xx.fbcdn.net/rsrc.php/v3/yL/r/vd4aB0GIe9z.png" width="32" height="32" />
                      </a>
                    </td>
                    <td width="100%">
                      <a href="https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com">Facebook
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td>
                <table border="0" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                  </tr>
                  <tr>
                    <td>
                      <span class="mb_text">
                        <span class="mb_text">
                          <a href="https://www.facebook.com/nd/?snarfed.org&amp;aref=123&amp;medium=email&amp;mid=1a2b3c&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=image">Ryan Barrett
                          </a> commented on your
                          <a href="https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com">post
                          </a>.
                        </span>
                      </span>
                    </td>
                  </tr>
                  <tr>
                    <td>
                      <table border="0" width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                          <td>
                            <table border="0" cellspacing="0" cellpadding="0">
                              <tr>
                                <td>
                                  <a href="https://www.facebook.com/nd/?snarfed.org&amp;aref=123&amp;medium=email&amp;mid=1a2b3c&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=image">
                                    <img src="https://scontent-atl3-1.xx.fbcdn.net/v/t1.0-1/p200x200/123_456_789_n.jpg?_nc_cat=105&amp;_nc_ht=scontent-atl3-1.xx&amp;oh=xyz&amp;oe=ABC" width="50" height="50" />
                                  </a>
                                </td>
                                <td width="100%">
                                  <table border="0" cellspacing="0" cellpadding="0">
                                    <tr>
                                      <td>
                                        <a href="https://www.facebook.com/nd/?snarfed.org&amp;aref=123&amp;medium=email&amp;mid=1a2b3c&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=image">Ryan Barrett
                                        </a>
                                      </td>
                                    </tr>
                                    <tr>
                                      <td>December 14 at 12:35 PM
                                      </td>
                                    </tr>
                                  </table>
                                </td>
                              </tr>
                              <tr>
                                <td colspan="3">
                                  <span class="mb_text">test comment foo bar baz&nbsp;
                                  </span>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <table border="0" width="100%" cellspacing="0" cellpadding="0">
                              <tr>
                                <td>
                                  <a href="https://www.facebook.com/nd/?email%2Fufi%2Fclick&amp;action=like&amp;target=123_456&amp;hash=abcxyz&amp;aref=246&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=email_ufi_like&amp;sig_t=1357&amp;sig=9x8y7z">
                                    <table border="0" cellspacing="0" cellpadding="0">
                                      <tr>
                                        <td valign="middle">
                                          <img src="https://static.xx.fbcdn.net/rsrc.php/v3/yn/r/A9uao6Uj7et.png" width="16" height="16" />
                                        </td>
                                        <td valign="middle">
                                          <a href="https://www.facebook.com/nd/?email%2Fufi%2Fclick&amp;action=like&amp;target=123_456&amp;hash=abcxyz&amp;aref=246&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=email_ufi_like&amp;sig_t=1357&amp;sig=9x8y7z">Like
                                          </a>
                                        </td>
                                      </tr>
                                    </table>
                                  </a>
                                </td>
                                <td>
                                  <a href="https://www.facebook.com/nd/?email%2Fufi%2Fclick&amp;action=comment&amp;target=123_456&amp;hash=abcxyz&amp;aref=246&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=email_ufi_comment&amp;sig_t=1357&amp;sig=9x8y7z">
                                    <table border="0" cellspacing="0" cellpadding="0">
                                      <tr>
                                        <td valign="middle">
                                          <a href="https://www.facebook.com/nd/?email%2Fufi%2Fclick&amp;action=comment&amp;target=123_456&amp;hash=abcxyz&amp;aref=246&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com&amp;lloc=email_ufi_comment&amp;sig_t=1357&amp;sig=9x8y7z">Comment
                                          </a>
                                        </td>
                                      </tr>
                                    </table>
                                  </a>
                                </td>
                              </tr>
                            </table>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td>
                <table border="0" width="100%" cellspacing="0" cellpadding="0">
                  <tr>
                    <td class="mb_blk">
                      <a href="https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com">
                        <table border="0" width="100%" cellspacing="0" cellpadding="0">
                          <tr>
                            <td>
                              <a href="https://www.facebook.com/nd/?permalink.php&amp;story_fbid=123&amp;id=456&amp;comment_id=789&amp;aref=012&amp;medium=email&amp;mid=a1b2c3&amp;bcode=2.34567890.ABCxyz&amp;n_m=recipient%40example.com">
                                <center>
                                  <font size="3">
                                    <span>View&nbsp;on&nbsp;Facebook
                                    </span>
                                  </font>
                                </center>
                              </a>
                            </td>
                          </tr>
                        </table>
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""

LIKE_EMAIL = """\
"""

# ActivityStreams
ACTOR = {
  'objectType': 'person',
  'displayName': 'Ryan Barrett',
  'image': {'url': 'https://scontent-atl3-1.xx.fbcdn.net/v/t1.0-1/p200x200/123_456_789_n.jpg?_nc_cat=105&_nc_ht=scontent-atl3-1.xx&oh=xyz&oe=ABC'},
  # 'id': tag_uri('snarfed.org'),
  # 'numeric_id': '212038',
  'url': 'https://www.facebook.com/snarfed.org',
  # 'username': 'snarfed.org',
}
COMMENT_OBJ = {
  'objectType': 'comment',
  'author': ACTOR,
  'content': 'test comment foo bar baz',
  # 'id': tag_uri('547822715231468_6796480'),
  'published': '1999-12-14T12:35:00',
  # 'url': 'https://www.facebook.com/547822715231468?comment_id=6796480',
  'inReplyTo': [{
    # 'id': tag_uri('547822715231468'),
    'url': 'https://www.facebook.com/permalink.php?story_fbid=2017389631919271&id=100009447618341',
  }],
  'to': [{'objectType':'group', 'alias':'@public'}],
}
LIKE_OBJ = {
  # 'id': tag_uri('10100176064482163_liked_by_100004'),
  'url': 'https://www.facebook.com/212038/posts/10100176064482163#liked-by-100004',
  'objectType': 'activity',
  'verb': 'like',
  'object': {'url': 'https://www.facebook.com/212038/posts/10100176064482163'},
  'author': ACTOR,
}


class FacebookEmailTest(testutil.TestCase):

  def test_email_to_object_comment(self):
    self.mox.StubOutWithMock(facebook_email, 'now_fn')
    facebook_email.now_fn().AndReturn(datetime(1999, 1, 1))
    self.mox.ReplayAll()

    self.assert_equals(COMMENT_OBJ, facebook_email.email_to_object(COMMENT_EMAIL))

  # def test_email_to_object_like(self):
  #   self.assert_equals(LIKE_OBJ, facebook_email.email_to_object(LIKE_EMAIL))
