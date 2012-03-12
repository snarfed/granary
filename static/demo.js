/*
 * Utilities for the demo form on the front page.
 */

var ACTIVITY_ID_BLURB = 'activity id (optional)';
var ACCESS_TOKEN_RE = new RegExp('access_token=([^&]+)');
var OAUTH_INPUT_IDS = ['access_token', 'access_token_key', 'access_token_secret'];

function render_form() {
  // the activity id field's style depends on whether it has a value, and whether it
  // has focus, and whether @all or @self is selected.
  var group_id = document.getElementById('group_id').value;
  var activity_id_elem = document.getElementById('activity_id');
  var activity_id = activity_id_elem.value;

  if (activity_id == '' || activity_id == ACTIVITY_ID_BLURB) {
    if (document.activeElement == activity_id_elem) {
      activity_id_elem.value = '';
      activity_id_elem.style.color = 'black';
    } else {
      activity_id_elem.value = ACTIVITY_ID_BLURB;
      activity_id_elem.style.color = 'gray';
    }
  }

  // the oauth access token field styles depend on whether they have values.
  var oauth_inputs = new Array();
  for (i in OAUTH_INPUT_IDS) {
    elem = document.getElementById(OAUTH_INPUT_IDS[i]);
    if (elem)
      oauth_inputs.push(elem);
  }

  for (i in oauth_inputs) {
    label = document.getElementById(oauth_inputs[i].id + '_label');
    label.style.color = (oauth_inputs[i].value) ? 'black' : 'gray';
  }

  // construct URL
  var url = '/@me/@' + group_id + '/@app/';
  if (!activity_id_elem.disabled && activity_id != ACTIVITY_ID_BLURB)
    url += activity_id;

  url += '?'
   for (i in oauth_inputs) {
    if (oauth_inputs[i].value)
      url += oauth_inputs[i].name + '=' + oauth_inputs[i].value + '&';
  }

  document.getElementById('url').innerHTML = url;
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
