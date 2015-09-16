/*
 * Utilities for the demo form on the front page.
 */

var OAUTH_INPUT_IDS = ['access_token', 'auth_entity',
                       'access_token_key', 'access_token_secret',
                       'user_id'];

function render_demo_request() {
  var url = window.location.origin + '/' +
      document.getElementById('site').value + '/@me/' +
      document.getElementById('group_id').value + '/@app/' +
      (document.getElementById('group_id').value == '@search'
         ? '?search_query=' + document.getElementById('search_query').value + '&'
         : document.getElementById('activity_id').value + '?') +
      'format=' + document.getElementById('format').value;

  for (i in OAUTH_INPUT_IDS) {
    elem = document.getElementById(OAUTH_INPUT_IDS[i]);
    if (elem && elem.value)
      url += '&' + elem.name + '=' + elem.value;
  }

  document.getElementById('request').innerHTML =
    'GET <a href="' + url + '">' + url + '</a>';
}

function render_url_request() {
  var url = window.location.origin + '/' +
      document.getElementById('site').value + '/@me/' +
      document.getElementById('group_id').value + '/@app/' +
      document.getElementById('activity_id').value + '?format=' +
      document.getElementById('format').value;

  document.getElementById('request').innerHTML =
    'GET <a href="' + url + '">' + url + '</a>';
}

function update_search() {
  group_id = document.getElementById('group_id');
  if (group_id) {
    searching = group_id.value == '@search';
    document.getElementById('activity_id_span').style.display =
      searching ? 'none' : 'inline';
    document.getElementById('search_query_span').style.display =
      searching ? 'inline' : 'none';
  }
}
