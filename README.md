activitystreams-unofficial ![ActivityStreams](https://raw.github.com/snarfed/activitystreams-unofficial/master/static/logo_small.png)
===

This is a library and REST API that converts Facebook, Twitter, and Instagram
data to [ActivityStreams](http://activitystrea.ms/) format. The web services
live at these endpoints:

http://facebook-activitystreams.appspot.com/  
http://twitter-activitystreams.appspot.com/  
http://instagram-activitystreams.appspot.com/

It's part of a suite of projects that use the major social networks' APIs to
implement federated social web protocols. The other projects include
[portablecontacts-](https://github.com/snarfed/portablecontacts-unofficial),
[salmon-](https://github.com/snarfed/salmon-unofficial),
[webfinger-](https://github.com/snarfed/webfinger-unofficial), and
[ostatus-unofficial](https://github.com/snarfed/ostatus-unofficial).

License: This project is placed in the public domain.


Using
===

The library and REST API are both based on the
[OpenSocial Activity Streams service](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).
Let's start with an example.

This method call in the library:

is equivalent to this `HTTP GET` request:

`https://twitter-activitystreams.appspot.com/@me/@friends/@app/?access_token_key=KEY&access_token_secret=SECRET`

which returns the authenticated user's Twitter stream, ie tweets from the people they
follow. Here's the JSON output:

    {
      "itemsPerPage": 12,
      "startIndex": 0,
      "totalResults": 12
      "items": [{
          "verb": "post",
          "id": "tag:twitter.com,2013:374272979578150912"
          "url": "http://twitter.com/evanpro/status/374272979578150912",
          "content": "Getting stuff for barbecue tomorrow. No ribs left! Got some nice tenderloin though. (@ Metro Plus Famille Lemay) http://t.co/b2PLgiLJwP",
          "actor": {
          "username": "evanpro",
            "displayName": "Evan Prodromou",
            "description": "Prospector.",
            "url": "http://twitter.com/evanpro",
          },
          "object": {
            "tags": [{
                "url": "http://4sq.com/1cw5vf6",
                "startIndex": 113,
                "length": 22,
                "objectType": "article"
              }, ...],
          },
        }, ...]
      ...
    }

where each
element is optional. `user_id` may be `@me`. `group_id` may be `@all`,
`@friends` (currently identical to `@all`), or `@self`. `app_id` is currently
ignored; best practice it to use `@app` as a placeholder.


Most requests will need an OAuth token from the source provider. Here are their
authentication docs:
[Facebook](https://developers.facebook.com/docs/facebook-login/access-tokens/),
[Twitter](https://dev.twitter.com/docs/auth/3-legged-authorization),
[Instagram](http://instagram.com/developer/authentication/).

If you obtain an OAuth access token and give it to the library or REST API, it
will be used to sign and authorize the underlying requests to the sources
providers. See the demos on the REST API endpoints above for examples.


Paging is supported via the `startIndex` and `count` parameters. They're
described in detail in the OpenSocial spec and
[OpenSearch spec](http://www.opensearch.org/Specifications/OpenSearch/1.1#The_.22count.22_parameter)
and
[OpenSocial spec](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).

Output data is
[JSON Activity Streams 1.0](http://activitystrea.ms/specs/json/1.0/) objects
wrapped in the
[OpenSocial envelope]http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).


Using the REST API
===

The web services above all serve the
[OpenSocial Activity Streams REST API](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).
Request paths are of the form `/user_id/group_id/app_id/activity_id`, where each
element is optional. `user_id` may be `@me`. `group_id` may be `@all`,
`@friends` (currently identical to `@all`), or `@self`. `app_id` is currently
ignored; best practice it to use `@app` as a placeholder.

Request paths are of the form `/user_id/group_id/app_id/activity_id`.

Errors are returned with the appropriate HTTP response code, e.g. 403 for
Unauthorized, with details in the response body.



Using the library
===

As precedent,
[Cliqset's FeedProxy](http://www.readwriteweb.com/archives/cliqset_activity_streams_api.php)
used to do this, but unfortunately it and
Cliqset died.

Facebook
[used to](https://developers.facebook.com/blog/post/225/)
[officially](https://developers.facebook.com/blog/post/2009/08/05/streamlining-the-open-stream-apis/)
[support](https://groups.google.com/forum/#!topic/activity-streams/-b0LmeUExXY)
ctivityStreams, but that's also dead.

To use the web services, in a ActivityStreams client, you'll need to hard-code
exceptions for the domains you want to use (e.g. `facebook.com`) and redirect
ActivityStreams HTTP requests to the corresponding endpoint above.


Development
===

Pull requests are welcome! Feel free to [ping me](http://snarfed.org/about) with
any questions.

All dependencies are included as git submodules. Be sure to run `git submodule
init` after cloning this repo.

[This ActivityStreams validator](http://activitystreamstester.appspot.com/) is
useful for manual testing.

You can run the unit tests with `./alltests.py`. They depend on the
[App Engine SDK](https://developers.google.com/appengine/downloads) and
[mox](http://code.google.com/p/pymox/), both of which you'll need to install
yourself.

Note the `app.yaml.*` files, one for each App Engine app id. To work on or deploy
a specific app id, `symlink app.yaml` to its `app.yaml.xxx` file. Likewise, if you
add a new site, you'll need to add a corresponding `app.yaml.xxx` file.

To deploy:
    rm -f app.yaml && ln -s app.yaml.twitter app.yaml && \
      ~/google_appengine/appcfg.py --oauth2 update . && \
    rm -f app.yaml && ln -s app.yaml.facebook app.yaml && \
      ~/google_appengine/appcfg.py --oauth2 update . && \
    rm -f app.yaml && ln -s app.yaml.instagram app.yaml && \
      ~/google_appengine/appcfg.py --oauth2 update .
