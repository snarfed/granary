/*
 * Utilities for the demo form on the front page.
 */

var OAUTH_INPUT_IDS = ['access_token', 'access_token_key', 'access_token_secret'];
var ACCESS_TOKEN_RE = new RegExp('access_token=([^&]+)');

function render_request() {
  var url = window.location.origin + '/' +
      document.getElementById('site').value + '/@me/' +
      document.getElementById('group_id').value + '/@app/' +
      document.getElementById('activity_id').value + '?format=' +
      document.getElementById('format').value;

  for (i in OAUTH_INPUT_IDS) {
    elem = document.getElementById(OAUTH_INPUT_IDS[i]);
    if (elem && elem.value)
      url += '&' + elem.name + '=' + elem.value;
  }

  document.getElementById('request').innerHTML = 'GET ' + url;
}

/* Only used for Facebook's client side OAuth flow, which returns the access
 * token in the URL fragment.
 */
function access_token_from_fragment() {
  var input = document.getElementById('access_token');
  var match = window.location.hash.match(ACCESS_TOKEN_RE);
  if (input && match)
    input.value = match[1];
}
