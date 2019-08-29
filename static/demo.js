/*
 * Utilities for the demo form on the front page.
 */

var OAUTH_INPUT_IDS = ['access_token', 'auth_entity',
                       'access_token_key', 'access_token_secret',
                       'user_id'];

function render_demo_request() {
  var site = get('site');
  var user_id = encodeURIComponent(get('user_id')) || '@me';

  var group = get('group_id');
  if (group == '@list') {
    group = get('list');
  }

  var url = window.location.origin + '/' +
      site + '/' + user_id + '/' + group + '/@app/' +
      (group == '@search'
       ? '?search_query=' + encodeURIComponent(get('search_query')) + '&'
       : encodeURIComponent(get('activity_id')) + '?') +
      'format=' + get('format');

  cookie = get('cookie');
  if (cookie && site == 'instagram') {
    url += '&cookie=' + cookie;
  }

  var request = document.getElementById('request');
  if (site == 'instagram') {
    request.innerHTML = 'Instagram is available here in the web UI, <a href="https://granary.readthedocs.io/">and in the library</a>, <em>but not elsewhere (like feed readers)</em>. <a href="https://instagram-atom.appspot.com/">Try instagram-atom instead!</a>'
    request.style.fontFamily = 'sans-serif';
    request.style.fontSize = 'large';
    request.style.color = 'lightcoral';
  } else {
    for (i in OAUTH_INPUT_IDS) {
      elem = document.getElementById(OAUTH_INPUT_IDS[i]);
      if (elem && elem.value)
        url += '&' + elem.name + '=' + elem.value;
    }
    request.innerHTML = 'GET <a href="' + url + '">' + url + '</a>';
  }
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
    list = document.getElementById('list');

    search.style.display = activity.style.display = list.style.display = 'none';
    list.required = false;

    if (group.value == '@search') {
      search.style.display = 'inline';
    } else if (group.value == '@list') {
      list.style.display = 'inline';
      list.required = true;
    } else if (group.value == '@blocks') {
      /* hide activity id input */
    } else {
      activity.style.display = 'inline';
    }
  }
}

function get(id) {
  var elem = document.getElementById(id);
  return elem ? elem.value : '';
}
