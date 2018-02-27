/*
 * Utilities for the demo form on the front page.
 */

var OAUTH_INPUT_IDS = ['access_token', 'auth_entity',
                       'access_token_key', 'access_token_secret',
                       'user_id'];

function render_demo_request() {
  var site = get('site');
  var user_id = encodeURIComponent(get('user_id')) || '@me';

  var url = window.location.origin + '/' +
      site + '/' + user_id + '/' +
      get('group_id') + '/@app/' +
      (get('group_id') == '@search'
       ? '?search_query=' + encodeURIComponent(get('search_query')) + '&'
       : encodeURIComponent(get('activity_id')) + '?') +
      'format=' + get('format');

  cookie = get('cookie');
  if (cookie && site == 'instagram') {
    url += '&cookie=' + cookie;
  }

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

function update_form() {
  group = document.getElementById('group_id');
  if (group) {
    activity = document.getElementById('activity_id_span');
    search = document.getElementById('search_query_span');
    if (group.value == '@search') {
      search.style.display = 'inline';
      activity.style.display  = 'none';
    } else if (group.value == '@blocks') {
      search.style.display = activity.style.display  = 'none';
    } else {
      activity.style.display = 'inline';
      search.style.display = 'none';
    }
  }
}

function get(id) {
  var elem = document.getElementById(id);
  return elem ? elem.value : '';
}
