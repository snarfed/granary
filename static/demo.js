/*
 * Utilities for the demo form on the front page.
 */

var ACCESS_TOKEN_RE = new RegExp('access_token=([^&]+)');

/* Only used for Facebook's client side OAuth flow, which returns the access
 * token in the URL fragment.
 */
function access_token_from_fragment() {
  var input = document.getElementById('access_token');
  var match = window.location.hash.match(ACCESS_TOKEN_RE);
  if (input && match)
    input.value = match[1];
}
