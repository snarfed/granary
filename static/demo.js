/*
 * Utilities for the demo form on the front page.
 */

var ACCESS_TOKEN_RE = new RegExp('access_token=([^&]+)');

function render_form() {
  // the activity id field's style depends on whether it has a value, and whether it
  // has focus, and whether @all or @self is selected.
  var group_id = document.getElementById('group_id').value;
  var activity_id_elem = document.getElementById('activity_id');
  var activity_id = activity_id_elem.value;
  var format = document.getElementById('format').value;

  // construct URL
  var url = '/@me/@' + group_id + '/@app/';
  if (!activity_id_elem.disabled)
    url += activity_id;

  url += '?format=' + format + '&';
   for (i in oauth_inputs) {
    if (oauth_inputs[i].value)
      url += oauth_inputs[i].name + '=' + oauth_inputs[i].value + '&';
  }

  document.getElementById('demo').action = url;
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
