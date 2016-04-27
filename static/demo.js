/*
 * Utilities for the demo form on the front page.
 */

var OAUTH_INPUT_IDS = ['access_token', 'auth_entity',
                       'access_token_key', 'access_token_secret',
                       'user_id'];

function render_demo_request() {
  var site = get('site');
  var user_id = get('user_id') || '@me';

  var url = window.location.origin + '/' +
      site + '/' + encodeURIComponent(user_id) + '/' +
      get('group_id') + '/@app/' +
      (get('group_id') == '@search'
       ? '?search_query=' + encodeURIComponent(get('search_query')) + '&'
       : encodeURIComponent(get('activity_id')) + '?') +
      'format=' + get('format');

  if (site != 'instagram') {
    for (i in OAUTH_INPUT_IDS) {
      elem = document.getElementById(OAUTH_INPUT_IDS[i]);
      if (elem && elem.value)
        url += '&' + elem.name + '=' + elem.value;
    }
  }

  document.getElementById('request').innerHTML =
    'GET <a href="' + url + '">' + url + '</a>';
}

function render_url_request() {
  var url = window.location.origin + '/url'
      + '?input=' + get('input')
      + '&output=' + get('output')
      + '&url=' + encodeURIComponent(get('url'));

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

function get(id) {
  var elem = document.getElementById(id);
  return elem ? elem.value : '';
}
