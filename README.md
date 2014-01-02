activitystreams-unofficial ![ActivityStreams](https://raw.github.com/snarfed/activitystreams-unofficial/master/static/logo_small.png)
===

  * [About](#about)
  * [Using](#using)
    * [Using the REST API](#using-the-REST-API)
    * [Using the library](#using-the-library)
  * [Future work](#future-work)
  * [Development](#development)


About
---

This is a library and REST API that converts Facebook, Twitter, and Instagram data to [ActivityStreams](http://activitystrea.ms/) format. You can try it out with these interactive demos:

http://facebook-activitystreams.appspot.com/  
http://twitter-activitystreams.appspot.com/  
http://instagram-activitystreams.appspot.com/

It's part of a suite of projects that implement the [OStatus](http://ostatus.org/) federation protocols for the major social networks. The other projects include [portablecontacts-](https://github.com/snarfed/portablecontacts-unofficial), [salmon-](https://github.com/snarfed/salmon-unofficial), [webfinger-](https://github.com/snarfed/webfinger-unofficial), and [ostatus-unofficial](https://github.com/snarfed/ostatus-unofficial).

Google+ isn't included because the [Google+ API](https://developers.google.com/+/api/) already outputs ActivityStreams directly with only minor tweaks and extensions.

There are many related projects.
[php-mf2-shim](https://github.com/indieweb/php-mf2-shim) adds
[microformats2](http://microformats.org/wiki/microformats2) to Facebook and
Twitter's raw HTML. [sockethub](https://github.com/sockethub/sockethub) is a
similar "polyglot" approach, but more focused on writing than reading.
[Cliqset's FeedProxy](http://www.readwriteweb.com/archives/cliqset_activity_streams_api.php)
used to do this kind of format translation, but unfortunately it and Cliqset
died. Facebook [used to](https://developers.facebook.com/blog/post/225/)
[officially](https://developers.facebook.com/blog/post/2009/08/05/streamlining-the-open-stream-apis/)
[support](https://groups.google.com/forum/#!topic/activity-streams/-b0LmeUExXY)
ActivityStreams, but that's also dead.

License: This project is placed in the public domain.


Using
---

The library and REST API are both based on the [OpenSocial Activity Streams service](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).

Let's start with an example. This code using the library:

```python
from activitystreams_unofficial import twitter
...
tw = twitter.Twitter(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
tw.get_activities(group_id='@friends')
```

is equivalent to this `HTTP GET` request:

```
https://twitter-activitystreams.appspot.com/@me/@friends/@app/
  ?access_token_key=ACCESS_TOKEN_KEY&access_token_secret=ACCESS_TOKEN_SECRET
```

They return the authenticated user's Twitter stream, ie tweets from the people they follow. Here's the JSON output:

```json
{
  "itemsPerPage": 10,
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
```

The request parameters are the same for both, all optional: `USER_ID` is a source-specific id or `@me` for the authenticated user. `GROUP_ID` may be `@all`, `@friends` (currently identical to `@all`), or `@self`. `APP_ID` is currently ignored; best practice is to use `@app` as a placeholder.

Paging is supported via the `startIndex` and `count` parameters. They're self explanatory, and described in detail in the [OpenSearch spec](http://www.opensearch.org/Specifications/OpenSearch/1.1#The_.22count.22_parameter) and [OpenSocial spec](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).

Output data is [JSON Activity Streams 1.0](http://activitystrea.ms/specs/json/1.0/) objects wrapped in the [OpenSocial envelope](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service), which puts the activities in the top-level `items` field as a list and adds the `itemsPerPage`, `totalCount`, etc. fields.

Most Facebook requests and all Twiter and Instagram requests will need OAuth access tokens. If you're using Python on Google App Engine, [oauth-dropins](https://github.com/snarfed/oauth-dropins) is an easy way to add OAuth client flows for these sites. Otherwise, here are the sites' authentication docs: [Facebook](https://developers.facebook.com/docs/facebook-login/access-tokens/), [Twitter](https://dev.twitter.com/docs/auth/3-legged-authorization), [Instagram](http://instagram.com/developer/authentication/).

If you get an access token and pass it along, it will be used to sign and authorize the underlying requests to the sources providers. See the demos on the REST API [endpoints above](#about) for examples.


Using the REST API
---

The [endpoints above](#about) all serve the [OpenSocial Activity Streams REST API](http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service). Request paths are of the form:

```
/USER_ID/GROUP_ID/APP_ID/ACTIVITY_ID?startIndex=...&count=...&format=FORMAT&access_token=...
```

All query parameters are optional. `FORMAT` may be `json` (the default), `xml`, or `atom`, both of which return [Atom](http://www.intertwingly.net/wiki/pie/FrontPage). The rest of the path elements and query params are [described above](#using).

Errors are returned with the appropriate HTTP response code, e.g. 403 for Unauthorized, with details in the response body.

To use the REST API in an existing ActivityStreams client, you'll need to hard-code exceptions for the domains you want to use e.g. `facebook.com`, and redirect HTTP requests to the corresponding [endpoint above](#about).


Using the library
---

See the [example above](#using) for a quick start guide.

Clone or download this repo into a directory named `activitystreams_unofficial` (note the underscore instead of dash). Each source works the same way. Import the module for the source you want to use, then instantiate its class by passing the HTTP handler object. The handler should have a `request` attribute for the current HTTP request.

The useful methods are `get_activities()` and `get_actor()`, which returns the current authenticated user (if any). See the [individual method docstrings](https://github.com/snarfed/activitystreams-unofficial/blob/master/source.py) for details. All return values are Python dicts of decoded ActivityStreams JSON.

The `activitystreams.render_html()` function is also useful for rendering an ActivityStreams object as nicely formatted HTML.


Future work
---

The REST APIs are currently much more usable than the library. We need to make the library easier to use. Most of the hard work is already done; here's what remains.

  * Allow passing OAuth tokens as keyword args.
  * Expose the initial OAuth permission flow. The hard work is already done, we just need to let users trigger it programmatically.
  * Expose the `format` arg and let users request [Atom](http://www.intertwingly.net/wiki/pie/FrontPage) output.
  * Clean up and document `activitystreams.render_html()`.

We'd also love to add more sites! Off the top of my head, [YouTube](http://youtu.be/), [Tumblr](http://tumblr.com/), [WordPress.com](http://wordpress.com/), [Sina Weibo](http://en.wikipedia.org/wiki/Sina_Weibo), [Qzone](http://en.wikipedia.org/wiki/Qzone), and [RenRen](http://en.wikipedia.org/wiki/Renren) would be good candidates. If you're looking to get started, implementing a new site is a good place to start. It's pretty self contained and the existing sites are good examples to follow, but it's a decent amount of work, so you'll be familiar with the whole project by the end.


Development
---

Pull requests are welcome! Feel free to [ping me](http://snarfed.org/about) with any questions.

Most dependencies are included as git submodules. Be sure to run `git submodule init` after cloning this repo.

[This ActivityStreams validator](http://activitystreamstester.appspot.com/) is useful for manual testing.

You can run the unit tests with `./alltests.py`. They depend on the [App Engine SDK](https://developers.google.com/appengine/downloads) and [mox](http://code.google.com/p/pymox/), both of which you'll need to install yourself.

Note the `app.yaml.*` files, one for each App Engine app id. To work on or deploy a specific app id, symlink `app.yaml` to its `app.yaml.xxx` file. Likewise, if you add a new site, you'll need to add a corresponding `app.yaml.xxx` file.

To deploy:

```shell
rm -f app.yaml && ln -s app.yaml.twitter app.yaml && \
  ~/google_appengine/appcfg.py --oauth2 update . && \
rm -f app.yaml && ln -s app.yaml.facebook app.yaml && \
  ~/google_appengine/appcfg.py --oauth2 update . && \
rm -f app.yaml && ln -s app.yaml.instagram app.yaml && \
  ~/google_appengine/appcfg.py --oauth2 update .
```


TODO
---
* https kwarg to get_activities() etc that converts all http links to https
* convert most of the per-site tests to testdata tests
