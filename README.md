<img src="https://raw.github.com/snarfed/granary/main/static/granary_logo_512.png" alt="Granary" width="128" /> granary [![Circle CI](https://circleci.com/gh/snarfed/granary.svg?style=svg)](https://circleci.com/gh/snarfed/granary) [![Coverage Status](https://coveralls.io/repos/github/snarfed/granary/badge.svg)](https://coveralls.io/github/snarfed/granary)
===

The social web translator. Fetches and converts data between social networks, HTML and JSON with [microformats2](http://microformats.org/wiki/microformats2), [ActivityStreams](http://activitystrea.ms/)/[ActivityPub](https://activitypub.rocks/), [Atom](https://tools.ietf.org/html/rfc4287), [JSON Feed](https://jsonfeed.org/), and more.

* [About](#about)
* [Using](#using)
  * [Using the REST API](#using-the-rest-api)
  * [Using the library](#using-the-library)
* [Troubleshooting/FAQ](#troubleshootingfaq)
* [Future work](#future-work)
* [Development](#development)
* [Release instructions](#release-instructions)
* [Related work](#related-work)
* [Changelog](#changelog)


About
---

Granary is a library and REST API that fetches and converts between a wide variety of social data sources and formats:

* Facebook, Flickr, GitHub, Instagram, Mastodon, and Twitter native APIs
* Instagram and Facebook scraped HTML
* [ActivityStreams](http://activitystrea.ms/) 1.0 and 2.0 JSON, including [ActivityPub](https://activitypub.rocks/)
* HTML and JSON with [microformats2](http://microformats.org/wiki/microformats2)
* [Atom](https://tools.ietf.org/html/rfc4287), [RSS 2.0](http://www.rssboard.org/rss-specification), [JSON Feed](https://jsonfeed.org/)
* Plain XML
* [Bluesky](https://blueskyweb.org/)/[AT Protocol](https://atproto.com/)
* [Nostr](https://nostr.com/), with many [NIPs](https://nostr.com/the-protocol/nips)

[Free](https://en.wikipedia.org/wiki/Threshing) yourself from silo API [chaff](https://en.wikipedia.org/wiki/Chaff) and expose the sweet social data foodstuff inside in standard formats and protocols!

Here's how to get started:

* Granary is [available on PyPi.](https://pypi.python.org/pypi/granary/) Install with `pip install granary`.
* [Getting started docs.](#using)
* [Reference docs.](https://granary.readthedocs.io/en/latest/source/granary.html)
* REST API and demo app at [granary.io](https://granary.io/).
* [Source code on GitHub.](https://github.com/snarfed/granary/)

License: This project is placed in the public domain. You may also use it under the [CC0 License](https://creativecommons.org/publicdomain/zero/1.0/).


Using
---

The library and REST API are both based on the [OpenSocial Activity Streams service](https://opensocial.github.io/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service). Let's start with an example. This code using the library:

```python
from granary import twitter
...
tw = twitter.Twitter(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
tw.get_activities(group_id='@friends')
```

is equivalent to this `HTTP GET` request:

```
https://granary.io/twitter/@me/@friends/@app/
  ?access_token_key=ACCESS_TOKEN_KEY&access_token_secret=ACCESS_TOKEN_SECRET
```

They return the authenticated user's Twitter stream, ie tweets from the people they follow. Here's the JSON output:

```json
{
  "itemsPerPage": 10,
  "startIndex": 0,
  "totalResults": 12,
  "items": [{
      "verb": "post",
      "id": "tag:twitter.com,2013:374272979578150912",
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
          }, "..."],
      },
    }, "..."]
  "..."
}
```

The request parameters are the same for both, all optional: `USER_ID` is a source-specific id or `@me` for the authenticated user. `GROUP_ID` may be `@all`, `@friends` (currently identical to `@all`), `@self`, `@search`, or `@blocks`; `APP_ID` is currently ignored; best practice is to use `@app` as a placeholder.

Paging is supported via the `startIndex` and `count` parameters. They're self explanatory, and described in detail in the [OpenSearch spec](http://www.opensearch.org/Specifications/OpenSearch/1.1#The_.22count.22_parameter) and [OpenSocial spec](https://opensocial.github.io/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service).

When using the `GROUP_ID` `@search` (for platforms that support it — currently Twitter and Instagram), provide a search string via the `q` parameter. The API is loosely based on the [OpenSearch spec](http://www.opensearch.org/Specifications/OpenSearch/1.1#OpenSearch_URL_template_syntax), the [OpenSocial Core Container spec](http://opensocial.github.io/spec/2.5.1/Core-Container.xml#rfc.section.11.2), and the [OpenSocial Core Gadget spec](http://opensocial.github.io/spec/2.5.1/Core-Gadget.xml#OpenSearch).

Output data is [JSON Activity Streams 1.0](http://activitystrea.ms/specs/json/1.0/) objects wrapped in the [OpenSocial envelope](https://opensocial.github.io/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service), which puts the activities in the top-level `items` field as a list and adds the `itemsPerPage`, `totalCount`, etc. fields.

Most Facebook requests and all Twitter, Instagram, and Flickr requests will need OAuth access tokens. If you're using Python on Google App Engine, [oauth-dropins](https://github.com/snarfed/oauth-dropins) is an easy way to add OAuth client flows for these sites. Otherwise, here are the sites' authentication docs: [Facebook](https://developers.facebook.com/docs/facebook-login/access-tokens/), [Flickr](https://www.flickr.com/services/api/auth.oauth.html), [Instagram](http://instagram.com/developer/authentication/), [Twitter](https://dev.twitter.com/docs/auth/3-legged-authorization).

If you get an access token and pass it along, it will be used to sign and authorize the underlying requests to the sources providers. See the demos on the REST API [endpoints above](#about) for examples.


Using the REST API
---

The [endpoints above](#about) all serve the [OpenSocial Activity Streams REST API](https://opensocial.github.io/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service). Request paths are of the form:

```
/USER_ID/GROUP_ID/APP_ID/ACTIVITY_ID?startIndex=...&count=...&format=FORMAT&access_token=...
```

All query parameters are optional. `FORMAT` may be `as1` (the default), `as2`, `atom`, `html`, `jsonfeed`, `mf2-json`, `rss`, or `xml` (the default). `atom` supports a boolean `reader` query parameter for toggling rendering appropriate to feed readers, e.g. location is rendered in content when `reader=true` (the default). The rest of the path elements and query params are [described above](#using).

Errors are returned with the appropriate HTTP response code, e.g. 403 for Unauthorized, with details in the response body.

By default, responses are cached and reused for 10m without re-fetching the source data. (Instagram responses are cached for 60m.) You can prevent this by adding the `cache=false` query parameter to your request.

Include the `shares=false` query parameter to omit shares, eg Twitter retweets, from the results.

To use the REST API in an existing ActivityStreams/ActivityPub client, you'll need to hard-code exceptions for the domains you want to use e.g. `facebook.com`, and redirect HTTP requests to the corresponding [endpoint above](#about).

Facebook and Instagram are disabled in the REST API entirely, sadly.


Using the library
---

See the [example above](#using) for a quick start guide.

Clone or download this repo into a directory named `granary`. Each source works the same way. Import the module for the source you want to use, then instantiate its class by passing the HTTP handler object. The handler should have a `request` attribute for the current HTTP request.

The useful methods are `get_activities()` and `get_actor()`, which returns the current authenticated user (if any). See the [full reference docs](https://granary.readthedocs.io/en/stable/source/granary.html#module-granary.source) for details. All return values are Python dicts of decoded ActivityStreams 1 JSON.

The `microformats2.*_to_html()` functions are also useful for rendering ActivityStreams 1 objects as nicely formatted HTML.


Troubleshooting/FAQ
---
Check out the [oauth-dropins Troubleshooting/FAQ section](https://github.com/snarfed/oauth-dropins#troubleshootingfaq). It's pretty comprehensive and applies to this project too.


Future work
---

We'd love to add more sites! Off the top of my head, [YouTube](http://youtu.be/), [Tumblr](http://tumblr.com/), [WordPress.com](http://wordpress.com/), [Sina Weibo](http://en.wikipedia.org/wiki/Sina_Weibo), [Qzone](http://en.wikipedia.org/wiki/Qzone), and [RenRen](http://en.wikipedia.org/wiki/Renren) would be good candidates. If you're looking to get started, implementing a new site is a good place to start. It's pretty self contained and the existing sites are good examples to follow, but it's a decent amount of work, so you'll be familiar with the whole project by the end.


Development
---
Pull requests are welcome! Feel free to [ping me in #indieweb-dev](https://indieweb.org/discuss) with any questions.

First, fork and clone this repo. Then, install the [Google Cloud SDK](https://cloud.google.com/sdk/) and run `gcloud components install cloud-firestore-emulator` to install the [Firestore emulator](https://cloud.google.com/firestore/docs/emulator). Once you have them, set up your environment by running these commands in the repo root directory:

```shell
gcloud config set project granary-demo
python3 -m venv local
source local/bin/activate
pip install -r requirements.txt
# needed to serve static files locally
ln -s local/lib/python3*/site-packages/oauth_dropins/static oauth_dropins_static
```

Now, run the tests to check that everything is set up ok:

```shell
gcloud emulators firestore start --host-port=:8089 --database-mode=datastore-mode < /dev/null >& /dev/null &
python3 -m unittest discover
```

Finally, run the web app locally with [`flask run`](https://flask.palletsprojects.com/en/2.0.x/cli/#run-the-development-server):

```shell
GAE_ENV=localdev FLASK_ENV=development flask run -p 8080
```

Open [localhost:8080](http://localhost:8080/) and you should see the granary home page!

If you want to work on [oauth-dropins](https://github.com/snarfed/oauth-dropins) at the same time, install it in editable mode with `pip install -e <path to oauth-dropins repo>`. You'll also need to update the `oauth_dropins_static` symlink, which is needed for serving static file handlers locally: `ln -sf <path-to-oauth-dropins-repo>/oauth_dropins/static oauth_dropins_static`.

To deploy to production:

```shell
gcloud -q beta app deploy --no-cache granary-demo *.yaml
```

The docs are built with [Sphinx](http://sphinx-doc.org/), including [apidoc](http://www.sphinx-doc.org/en/stable/man/sphinx-apidoc.html), [autodoc](http://www.sphinx-doc.org/en/stable/ext/autodoc.html), and [napoleon](http://www.sphinx-doc.org/en/stable/ext/napoleon.html). Configuration is in [`docs/conf.py`](https://github.com/snarfed/granary/blob/master/docs/conf.py) To build them, first install Sphinx with `pip install sphinx`. (You may want to do this outside your virtualenv; if so, you'll need to reconfigure it to see system packages with `virtualenv --system-site-packages local`.) Then, run [`docs/build.sh`](https://github.com/snarfed/granary/blob/master/docs/build.sh).


Release instructions
---
Here's how to package, test, and ship a new release. (Note that this is [largely duplicated in the oauth-dropins readme too](https://github.com/snarfed/oauth-dropins#release-instructions).)

1. Run the unit tests.
   ```sh
   source local/bin/activate.csh
   CLOUDSDK_CORE_PROJECT=granary-demo gcloud emulators firestore start --host-port=:8089 --database-mode=datastore-mode < /dev/null >& /dev/null &
   sleep 5
   python -m unittest discover
   kill %1
   deactivate
   ```
1. Bump the version number in `setup.py` and `docs/conf.py`. `git grep` the old version number to make sure it only appears in the changelog. Change the current changelog entry in `README.md` for this new version from _unreleased_ to the current date.
1. Bump the `oauth-dropins` version specifier in `setup.py` to the most recent version.
1. Build the docs. If you added any new modules, add them to the appropriate file(s) in `docs/source/`. Then run `./docs/build.sh`. Check that the generated HTML looks fine by opening `docs/_build/html/index.html` and looking around.
1. `git commit -am 'release vX.Y'`
1. Upload to [test.pypi.org](https://test.pypi.org/) for testing.
   ```sh
   python setup.py clean build sdist
   setenv ver X.Y
   source local/bin/activate.csh
   twine upload -r pypitest dist/granary-$ver.tar.gz
   ```
1. Install from test.pypi.org.
   ```sh
   cd /tmp
   python -m venv local
   source local/bin/activate.csh
   pip uninstall granary # make sure we force Pip to use the uploaded version
   pip install --upgrade pip
   pip install mf2py==1.1.2
   pip install -i https://test.pypi.org/simple --extra-index-url https://pypi.org/simple granary==$ver
   deactivate
   ```
1. Smoke test that the code trivially loads and runs.
   ```sh
   source local/bin/activate.csh
   python
   # run test code below
   deactivate
   ```
   Test code to paste into the interpreter:
   ```py
   import json
   from granary import github
   github.__file__  # check that it's in the virtualenv

   g = github.GitHub('XXX')  # insert a GitHub personal OAuth access token
   a = g.get_activities()
   print(json.dumps(a, indent=2))

   from granary import atom
   print(atom.activities_to_atom(a, {}))
   ```
1. Tag the release in git. In the tag message editor, delete the generated comments at bottom, leave the first line blank (to omit the release "title" in github), put `### Notable changes` on the second line, then copy and paste this version's changelog contents below it.
   ```sh
   git tag -a v$ver --cleanup=verbatim
   git push && git push --tags
   ```
1. [Click here to draft a new release on GitHub.](https://github.com/snarfed/granary/releases/new) Enter `vX.Y` in the _Tag version_ box. Leave _Release title_ empty. Copy `### Notable changes` and the changelog contents into the description text box.
1. Upload to [pypi.org](https://pypi.org/)!
   ```sh
   twine upload dist/granary-$ver.tar.gz
   ```
1. [Build the docs on Read the Docs](https://readthedocs.org/projects/granary/builds/): first choose _latest_ in the drop-down, then click _Build Version_.
1. On the [Versions page](https://readthedocs.org/projects/granary/versions/), check that the new version is active, If it's not, activate it in the _Activate a Version_ section.


Related work
--

[Apache Streams](http://streams.incubator.apache.org/) is a similar project that translates between storage systems and database as well as social schemas. It's a Java library, and its design is heavily structured. [Here's the list of formats it supports.](http://streams.incubator.apache.org/site/0.3-incubating-SNAPSHOT/streams-project/streams-contrib/index.html) It's mainly used by [People Pattern](http://www.peoplepattern.com/).

[Gnip](http://gnip.com/) similarly [converts social network data to ActivityStreams](http://support.gnip.com/documentation/activity_streams_intro.html) and supports [many more source networks](http://gnip.com/sources/). Unfortunately, it's commercial, there's no free trial or self-serve signup, and [plans start at $500](http://gnip.com/products/pricing/).

[DataSift](http://datasift.com/) looks like broadly the same thing, except they offer [self-serve, pay as you go billing](http://dev.datasift.com/docs/billing), and they use [their own proprietary output format](http://dev.datasift.com/docs/getting-started/data) instead of ActivityStreams. They're also aimed more at data mining as opposed to individual user access.

[Cliqset's FeedProxy](http://www.readwriteweb.com/archives/cliqset_activity_streams_api.php) used to do this kind of format translation, but unfortunately it and Cliqset died.

Facebook [used to](https://developers.facebook.com/blog/post/225/) [officially](https://developers.facebook.com/blog/post/2009/08/05/streamlining-the-open-stream-apis/) [support](https://groups.google.com/forum/#!topic/activity-streams/-b0LmeUExXY) ActivityStreams, but that's also dead.

There are a number of products that download your social network data, normalize it, and let you query and visualize it. [SocialSafe](http://socialsafe.net/) is one, although the SSL certificate is currently out of date. [ThinkUp](http://web.archive.org/web/20161108212106/http://www.thinkup.com/) was an open source product, but shuttered on 18 July 2016. There's also the lifelogging/lifestream aggregator vein of projects that pull data from multiple source sites. [Storytlr](https://github.com/storytlr/storytlr) is a good example. It doesn't include Facebook, or Instagram, but does include a number of smaller source sites. There are lots of others, e.g. the [Lifestream WordPress plugin](http://www.enthropia.com/labs/wp-lifestream/). Unfortunately, these are generally aimed at end users, not developers, and don't usually expose libraries or REST APIs.

On the open source side, there are many related projects. [php-mf2-shim](https://github.com/indieweb/php-mf2-shim) adds [microformats2](http://microformats.org/wiki/microformats2) to Facebook and Twitter's raw HTML. [sockethub](https://github.com/sockethub/sockethub) is a similar "polyglot" approach, but more focused on writing than reading.


Changelog
---

### 7.1 - unreleased

* `as1`:
  * Add new `is_dm` `recipient_if_dm`, and `is_audience` functions.
* `as2`:
  * Add [`sensitive`](https://swicg.github.io/miscellany/#sensitive) support.
  * Add new `is_server_actor` function ([FEP-d556](https://codeberg.org/fediverse/fep/src/branch/main/fep/d556/fep-d556.md), [discussion](https://socialhub.activitypub.rocks/t/fep-d556-server-level-actor-discovery-using-webfinger/3861)).
  * `from_as1`:
    * Always convert images to objects with `type: Image`, never to bare string URLs ([bridgy-fed#/1000](https://github.com/snarfed/bridgy-fed/issues/1000)).
    * Bug fix for converting links to facets when the link text is the link URL.
  * `to_as1`:
    * Handle other types of tags better, eg non-standard `Hashtag` and inner `tag` field for name.
    * Bug fix for videos, `mimeType` goes in outer object, not in `stream`.
    * Bug fix for `to`/`cc` with mixed dict and string elements.
* `atom`:
  * `atom_to_activity/ies`: Get URL from `link` for activities as well as objects. ([Thanks @imax9000!](https://github.com/snarfed/granary/issues/752))
* `bluesky`:
  * Translate Bluesky `app.bsky.feed.post#langs` to/from AS1 `contentMap` (which isn't officially part of AS1; we steal it from AS2).
  * Translate AS2 `sensitive` on posts to Bluesky `graphic-media` self label, and many Bluesky self labels back to `sensitive` with content warning(s) in `summary`.
  * Translate AS1/2 DMs to/from Bluesky chats.
  * Translate video embeds in posts.
  * `create`/`previewCreate`:
    * If `inReplyTo` isn't a Bluesky URL or AT URI, return `CreationResult` instead of raising `ValueError`.
  * `from_as1`:
    * Convert `article`s to external embeds with no post text.
    * Add new `as_embed` boolean kwarg to do the same thing for any object.
    * When truncating and adding a link to the original post, use `id` if `url` is not available ([snarfed/bridgy-fed#1155](https://github.com/snarfed/bridgy-fed/issues/1155)).
    * If the input object has `inReplyTo` or `object` or `target` with no recognizable ATProto or Bluesky object, raise `ValueError`.
    * Omit images that aren't in `blobs`.
    * Bug fix for quote posts with text content that's longer than Bluesky's limit ([snarfed/bridgy-fed#1197](https://github.com/snarfed/bridgy-fed/issues/1197)).
    * When a `flag` has multiple objects, use the first one that's an ATProto record.
    * Handle URLs more carefully, don't add link facets with invalid `uri`s.
    * Bug fix: handle HTML links with `title` in `content` correctly.
  * `to_as1`:
    * Extract links from `app.bsky.actor.profile#description` into `url`/`urls` fields
    * Bug fix: first URL (singular) goes in `url`, list of URLs goes in `urls`.
    * Bug fix: handle hashtags with regexp special characters.
    * Support string and bytes CIDs in blob `ref`s as well as `CID` instances.
  * `Bluesky.get_activities`: skip unknown record types instead of raising `ValueError`.
* `rss`:
  * Support image enclosures, both directions.

### 7.0 - 2024-06-24

_Breaking changes:_

* `jsonfeed`:
  * `jsonfeed_to_activities`: return AS1 objects, not activities.

_Non-breaking changes:_

* `as1`:
  * `activity_changed`: add `displayName`, `summary` fields.
  * `is_public`: return `False` if the object/activity contains `to` that's empty or has only unknown aliases.
* `as2`:
  * Add support for the `Application`, `Block`, `Flag`, and `Link` types.
  * Generalize actor logic in `to/from_as1` across all actor types, not just `Person`.
  * Add new `link_tags` function.
* `atom`:
  * `activities_to_atom`: handle image attachments without `url` field.
* `bluesky`:
  * `to_as1`:
    * Add support for:
      * `app.bsky.embed.record`
      * `app.bsky.embed.recordWithMedia`
      * `app.bsky.feed.defs#notFoundPost`
      * `app.bsky.feed.generator`
      * `app.bsky.graph.block`
      * `app.bsky.graph.list`
      * `app.bsky.graph.listitem`
      * `com.atproto.admin.defs#repoRef`
      * `com.atproto.moderation.createReport#input`
      * `com.atproto.repo.strongRef`
    * Add hashtag facet support.
    * Convert blobs in embeds to `getBlob` image URLs.
    * `app.bsky.actor.profile`: add HTML links for URLs in `summary` ([snarfed/bridgy-fed#1065](https://github.com/snarfed/bridgy-fed/issues/1065)).
    * Escape HTML characters (`<`, `>`, `&`) in `app.bsky.actor.profile` `description` field.
    * Bug fix for `create`/`update` activities with bare string `object`.
  * `from_as1`:
    * Add hashtag, mention, block, and flag support. Interpret `tags` with missing `objectType` as hashtags.
    * Guess missing indices in facets based on content text. Otherwise, if we still don't know a facet's indices, discard it.
    * Extract HTML links (<a> tags) from HTML content and convert to link facets ([snarfed/bridgy-fed#976](https://github.com/snarfed/bridgy-fed/issues/976)).
    * If an output string value is longer than its ``maxGraphemes`` or ``maxLength`` in its lexicon, truncate it with an ``…`` ellipsis character at the end in order to fit. If this happens to post text, include a link embed pointing to the original post.
    * If the object has a video, include an external embed pointing to the original post and mark it as `[Video]` ([snarfed/bridgy-fed#1078](https://github.com/snarfed/bridgy-fed/issues/1078)).
    * If the object has images, add the original post link to the end of the text, since Bluesky doesn't support both image and external embeds in the same post ([bluesky-social/atproto#2575](https://github.com/bluesky-social/atproto/discussions/2575), [snarfed/bridgy-fed#1106](https://github.com/snarfed/bridgy-fed/issues/1106)).
    * If a `note` has `summary` - often used for content warnings in the fediverse - add it to `content` as a prefix instead of overriding `content` ([snarfed/bridgy-fed#1001](https://github.com/snarfed/bridgy-fed/issues/1001)).
    * Populate `reply.root` properly in reply posts ([snarfed/bridgy#1696](https://github.com/snarfed/bridgy/issues/1696)).
    * Add new `original_fields_prefix` kwarg to store original data in custom (off-Lexicon) `*OriginalDescription` and `*OriginalUrl` fields in `app.bsky.actor.profile` and `*OriginalText` and `*OriginalUrl` fields in `app.bsky.feed.post` ([snarfed/bridgy-fed#1092](https://github.com/snarfed/bridgy-fed/issues/1092)).
    * Support `lexrpc.Client` as well as `Bluesky` for `client` kwarg.
  * `from_as1_to_strong_ref`:
    * Add `value` boolean kwarg.
    * Change `client` kwarg from `Bluesky` to `lexrpc.Client`.
* `microformats2`:
  * Generalize actor logic across all actor types, not just `person`.
  * `json_to_object`:
    * Strip leading `#` prefix (if present) from hashtag `u-category`s.
    * Bug fix for when `name` property is an object, eg an `h-card`.
  * `object_to_json`:
    * Convert both `id` and `url` inside `inReplyTo` to `in-reply-to.`
* `nostr`:
  * Handle connection closing while sending initial query.
* `source`:
  * `Source.postprocess`: when extracting @-mentions, defer to existing tag if it has the same `displayName` and has `url`.

### 6.2 - 2024-03-15

* `as1`:
  * `get_owner` bug fix for `post`, `update`, `delete` activities.
  * `activity_changed`: add new `inReplyTo` kwarg.
  * `is_public`: add new `unlisted` kwarg.
* `as2`:
  * `to_as1`: bug fix, preserve `objectType: featured` for banner/header images even when `mediaType` is also set.
  * `is_public`: add new `unlisted` kwarg.
  * `from_as1`:
    * For `icon` field, prefer image types that are [allowed by Mastodon](https://github.com/mastodon/mastodon/blob/b4c332104a8b3748f619de250f77c0acc8e80628/app/models/concerns/account/avatar.rb#L6).
    * Bug fix, handle `stop-following` with string `object` id.
* `atom`:
  * Add new `extract_entries` function.
  * `activity_to_atom`: default actor/author name to username.
  * `atom_to_activities`: support top-level `entry` element as well as `feed`.
  * `atom_to_*`:
    * add `object.author`
    * default `objectType` to `article`/`note` and `verb` to `post`
    * convert `link rel=self`/`alternate` to `url`
    * use `displayName` in objects instead of `title`
    * Interpret entry `link` without `rel` as self link.
  * If `entry.author` doesn't have id or url, default them to feed author's.
* `bluesky`:
  * Implement `create` and `preview`.
  * Fully support both `record` and `object` types in `from_as1` and `to_as1`. Use `to_as1`'s `type` kwarg and `from_as1`'s `out_type` kwarg to disambiguate.
  * Implement `Bluesky.post_id`.
  * Add new `blob_to_url` function.
  * Delete `as1_to_profile`, switch `from_as1` to return `$type: app.bsky.actor.profile`.
  * Convert HTML `summary` and `content` to plain text.
  * Implement `Bluesky.user_to_actor`, `Bluesky.get_actor`.
  * Don't log in (fetch an access token) eagerly in the constructor; wait until the client makes a call.
  * Prefer DID to handle in API calls that accept either.
  * `at_uri_to_web_url`: support lists.
  * `web_url_to_at_uri`: convert profile URLs like `https://bsky.app/profile/snarfed.org` to profile record URIs (`at://snarfed.org/app.bsky.actor.profile/self`) instead of repo URIs (`at://snarfed.org`).
  * Add `from_as1_to_strong_ref`.
  * Allow `:`s in record keys ([atproto#2224](https://github.com/bluesky-social/atproto/discussions/2224)).
  * `to_as1`:
    * Convert blobs, [both new and old style](https://atproto.com/specs/data-model#blob-type), to PDS `getBlob` URLs.
    * Add new `uri` kwarg.
    * Translate `handle` to `username`, add new `repo_handle` kwarg.
    * Add support for `app.bsky.feed.repost`, `app.bsky.graph.defs#listView`, `app.bsky.feed.defs#blockedPost`.
    * Add `actor`/`author` based on `repo_did`.
    * Improve `url` field: include custom handles, only use `repo_did/handle` for `app.bsky.actor.profile`.
    * Handle bad facet indices that point inside Unicode code points ([example](https://bsky.app/profile/did:plc:2ythpj4pwwpka2ljkabouubm/post/3kkfszbaiic2g); [discussion](https://discord.com/channels/1097580399187738645/1097580399187738648/1203118842516082848)).
    * Convert [`!no-unauthenticated` label](https://github.com/bluesky-social/atproto/blob/main/packages/api/docs/labels.md#label-behaviors) on profiles to [AS1 `@unlisted` audience target](https://activitystrea.ms/specs/json/targeting/1.0/) ([bridgy-fed#828](https://github.com/snarfed/bridgy-fed/issues/828)).
  * `from_as1`:
    * Add `out_type` kwarg to specify desired output type, eg `app.bsky.actor.profile` vs `app.bsky.actor.defs#profileViewBasic` vs `app.bsky.actor.defs#profileView`.
    * Add `blobs` kwarg to provide blob objects to use for image URLs.
    * Add `client` kwarg to fetch and populate CIDs.
    * Handle mention tags pointing to bare DIDs.
    * Use `parent` as `root` in replies. (Technically wrong in cases where the parent isn't the root, but we don't actually know the root. 🤷)
    * Bug fix: handle bare string URLs in `image` field.
    * Bug fix: handle tags without `url` field.
    * Strip trailing slash from home page URLs in order to remove visible `/` from rel-me verified links on Mastodon etc.
    * Convert `attributedTo` to singular if it has only one element.
    * If `name` isn't set, fall back to `preferredUsername` or infer Webfinger handle from `id` or `url`.
    * Prioritize bsky.app profile URL before handle URL in `url` field ([bridgy#1640](https://github.com/snarfed/bridgy/issues/1640)).
    * Convert `bsky.app` `inReplyTo` URLs to `at://` URIs.
    * Tighten up `datetime` conversion to match the [ATProto recommended format](https://atproto.com/specs/lexicon#datetime).
* `facebook`:
  * Remove `Facebook.fql_stream_to_post`. [Facebook turned down FQL in 2016.](https://en.wikipedia.org/wiki/Facebook_Query_Language#History)
* `github`:
  * When converting data to AS1, use `displayName` in objects instead of `title`.
* `mastodon`:
  * `get_activities` bug fix: use query params for `/api/v1/notifications` API call, not JSON body.
  * Convert HTTP 200 responses with `error` JSON field (eg from Sharkey) to 400/401 exceptions.
  * Prefer `media_attachments.remote_url` when available since it may be more long-lived than `url` for remote statuses ([bridgy#1675](https://github.com/snarfed/bridgy/issues/1675)).
* `microformats2`:
  * `object_to_json` bug fix: handle singular `inReplyTo`.
  * `json_to_object` bug fix: handle list-valued `location`.
* `nostr:`
  * `get_*`: return partial results when the websocket connection is closed prematurely.
  * `to_as1`: handle invalid NIP05 values (eg `{}`)
* `rss`:
  * `to_activities`:
    * Use `objectType: note` if `title` isn't set or is a prefix (possibly ellipsized) of `content`/`description`.
    * Add support for images in `media:content` tags ([#674](https://github.com/snarfed/granary/issues/674)).
* `Source`:
  * `postprocess_activity/object`: add `mentions` kwarg to convert @-mentions in HTML links to `mention` tags.

### 6.1 - 2023-09-16

Highlights: Nostr, Bluesky `get_activities`, lots of improvements in `as2` and `microformats2`, and more!

_REST API breaking changes:_

[Twitter is dead](https://snarfed.org/2023-04-03_so-long-twitter-api-and-thanks-for-all-the-fish), at least in the REST API.

_Non-breaking changes:_

* Add new `nostr` module!
* `as1`:
  * Add `get_owner`, `targets`.
  * Add `accept`, `reject`, `stop-following` to `VERBS_WITH_OBJECT` and remove `repost`, [it's not an AS1 verb](https://activitystrea.ms/specs/json/schema/activity-schema.html#verbs).
  * Handle `url` field list values (even though it's invalid AS1).
* `as2`:
  * `to_as1`:
    * Improve `Video` handling: support `Link` objects in `url`, extract stream URLs and types from link `tag`s.
    * Coerce non-float `latitude` and `longitude` to float, raise `ValueError` on failure.
    * Put image attachments into `image` as well as `attachments` ([bridgy-fed#429](https://github.com/snarfed/bridgy-fed/issues/429)).
    * Handle Hubzilla's composite object attachment `value`s.
    * Bug fix for null `mediaType` in `attachment` and `tags`.
  * Add new `TYPES_WITH_OBJECT` constant.
  * Add new `get_urls`, `address` functions.
  * Improve `Content-Type` compatibility with `application/ld+json; profile="https://www.w3.org/ns/activitystreams"`.
  * Bug fix for `Undo` activities with bare string id `object`s.
  * Revise HTML in `PropertyValue` attachments on actors to include full URL in anchro text to be compatible with Mastodon's profile link verification.
* `atom`:
  * `activities_to_atom` etc:
    * Switch `content` from XHTML to HTML inside CDATA to support non-XHTML input content ([bridgy-fed#624](https://github.com/snarfed/bridgy-fed/issues/624).
    * Bug fix, handle bare string URL `image` values.
    * Bug fix, emove incorrect `type="application/atom+xml"` from `rel="self"` `link` in `entry`.
    * Render `objectType: comment` attachments.
    * Remove invalid `<a>` element for tags.
    * Bug fix: avoid encoded `<` and `>` characters in `title` ([#629](https://github.com/snarfed/granary/issues/629)).
  * Bug fixes in `activity_to_atom`/`activities_to_atom` for dict-valued `url` fields.
  * Render images in article/note attachments.
  * Render `objectType: service` attachments, eg Bluesky custom feeds.
* `bluesky`:
  * Implement `Bluesky` API class, including `get_activities`.
  * Drop bundled `app.bsky`/`com.atproto` lexicons, use lexrpc's instead.
  * Convert reposts, quotes, inline links, attached links, and mentions, both directions. Includes Bluesky facet (rich text) support.
  * Handle quote posts with attached images, both directions.
  * Handle likes, both directions.
  * Add new `web_url_to_at_uri` function.
  * `from_as1`: handle link tags without start/end indices.
  * `to_as1`:
    * Add new `type` kwarg.
    * Generate staging.bsky.app profile and post URLs.
    * Propagate profile `did` into actor `id`.
    * Add unimplemented stub for custom feeds, eg `app.bsky.feed.defs#generatorView`.
  * Add `as1_to_profile`.
  * Bug fix for converting follows, both directions: `subject` in `app.bsky.graph.follow` is followee, not follower. ([That field is badly named!](https://discord.com/channels/1097580399187738645/1097580399187738648/1151933384738746478))
* `jsonfeed`:
  * `activities_to_jsonfeed`:
    * Bug fix, handle bare string values for `image` and `stream`.
    * Bug fix: handle non-object `author`.
* `mastodon`:
  * `status_to_object`: add/fix alt text handling for images.
* `microformats2`:
  * `json_to_html`:
    * HTML-escape tag and quote attachment names. Fixes [GHSA-4w4f-g49g-3f7j](https://github.com/snarfed/bridgy/security/advisories/GHSA-4w4f-g49g-3f7j); thank you [@janboddez](https://github.com/janboddez)!
  * `json_to_object`:
    * Improve handling of items with multiple types by using [post type discovery](https://indiewebcamp.com/post-type-discovery) more aggressively.
    * Normalize ISO-8601 format of `published` and `updated` timestamps.
  * `object_to_json`:
    * Bug fix, handle bare string URL `image` values.
    * Normalize ISO-8601 format of `published` and `updated` timestamps.
    * Handle bare string ids for `replies ` and `shares` (usually from AS2.)
  * `render_content`:
    * Bug fix for bare string `author` and `actor` values.
  * Include `objectType: service` attachments, eg Bluesky custom feeds, in JSON and HTML output.
* `rss`:
  * `from_activities`: handle bare string id `author`.

### 6.0 - 2023-03-22

_Breaking changes:_

* `as2`:
  * Interpret bare string `object`, `inReplyTo`, etc values as ids, convert them to bare strings or `id` instead of `url`.
* `microformats2`:
  * Convert simple string `in-reply-to`, `repost-of`, `like-of` etc values to AS1 bare strings or `id`s instead of `url`s.

_Non-breaking changes:_

* Add new `bluesky` module for [Bluesky](https://blueskyweb.org/)/[AT Protocol](https://atproto.com/)!
* `as1`:
  * Add the `organization` object type and `ACTOR_TYPES` constant ([based on AS2](https://www.w3.org/TR/activitystreams-core/#actors)).
  * Add new `get_ids`, `get_object`, and `get_objects` functions.
* `activity_changed`: ignore `inReplyTo.author` ([snarfed/bridgy#1338](https://github.com/snarfed/bridgy/issues/1338))
* `as2`:
  * Support converting between AS1 `stop-following` and AS2 `Undo` `Follow`.
  * Support AS2 `Accept` and `Reject` for follows as well as event RSVPs.
  * Add support for the `Question` (ie poll), `Organization`, and `Delete` object types.
  * Convert `to`/`cc` to/from AS1 `to` for public and unlisted.
  * Handle `type: Document` video attachments like Mastodon emits.
  * `from_as1`: bug fix for image objects with `url` and `value` fields (for alt text).
  * `from_as1`: bug fix, handle bare string URL `image` values.
  * `from_as1`: convert `urls.displayName` to `attachment.name` ([bridgy-fed#331](https://github.com/snarfed/bridgy-fed/issues/331)).
  * `from_as1`: preserve `inReplyTo` object values as objects, inline single-element lists down down to just single element.
  * `to_as1`: use `objectType: featured` for first image in `image` field.
  * `to_as1`: populate `actor` into `object.author` for `Update`s as well as `Create`s.
  * `to_as1`: convert Mastodon profile metadata `PropertyValue` attachments to `url` composite objects with `displayName`.
  * Preserve `to` and `cc` values when converting both directions.
* `atom`:
  * Bug fix for rendering image attachments without `image` field to Atom.
  * Bug fix for `published` and `updated` in entries with objects, eg likes, reposts, RSVPs, bookmarks. Thanks [@gregorlove](https://gregorlove.com/)! ([#480](https://github.com/snarfed/granary/issues/480))
  * Bug fix for content `activity/ies_to_atom` when `object` is present and empty.
  * Bug fix for objects with elements without `objectType` in the `to` field.
* `flickr`:
  * `get_activities`: add support for the `count` kwarg.
* `github`:
  * `get_activities`: add support for the `count` kwarg.
* `jsonfeed`:
  * Switch from `white-space: pre` CSS to converting newlines to `<br>`s because some feed readers follow it strictly and don't even line wrap ([#456](https://github.com/snarfed/granary/issues/456)).
* `mastodon`:
  * Add compatibility support for [Truth Social](https://truthsocial.com/).
  * Handle truncated JSON API responses.
* `microformats2`:
  * `json_to_object`: drop backward compatibility support for `like` and `repost` properties. [Background discussion.](https://chat.indieweb.org/dev/2022-12-23#t1671833687984200)
  * `json_to_object`: add new `rel_urls` kwarg to allow attaching `displayName`s to `urls` based on HTML text or `title` attribute ([bridgy-fed#331](https://github.com/snarfed/bridgy-fed/issues/331)).
  * Add new `json_to_activities` function.
  * `hcard_to_html`/`maybe_linked_name`: when `name` is missing, use pretty URL as visible text.
  * Support the `h-card` `org` property.
  * `json_to_object`: handle composite `rsvp` property value.
  * `json_to_object`: bug fix when `fetch_mf2` is True, handle when we run the authorship algorithm and fetch an author URL that has a `u-photo` with `alt`.
* `rss`:
  * `from_activities`: fix item ordering to match input activities.

### 5.0 - 2022-12-03

_Breaking changes:_

* Drop Python 3.6 support. Python 3.7 is now the minimum required version.
* Twitter, Instagram, Mastodon:
  * Drop `get_activities` `cache` kwarg's support for App Engine memcache interface. It's now only used as a plain `dict`. `get_activities` will now make many small modifications, so if you pass an object that implements those as API calls, you'll probably want to batch those separately.
* Twitter, Mastodon, Flickr, GitHub:
  * `create`/`preview`: support the AS1 `favorite` verb as well as `like`. ([bridgy#1345](https://github.com/snarfed/bridgy/issues/1345))
* Atom:
  * Switch to converting AS1 `id` (instead of `url`) to Atom `id`.
* Reddit:
  * Implement `get_actor`.
* Mastodon:
  * `create`/`preview`: allow non-Mastodon replies, ie activities that include `inReplyTo` URLs even if none of them point to a toot. ([bridgy#1321](https://github.com/snarfed/bridgy/issues/1321))
  * Raise `requests.HTTPError` with `response.status_code` 502 instead of `JSONDecodeError` on non-JSON responses. This is synthetic, but more helpful for error handling.
* microformats2:
  * `object_to_json` and related functions: handle all escaped HTML entities, not just `&amp;` `&lt;` `&gt;`.
  * Unify `microformats2.prefix_image_urls` and `prefix_video_urls` into a new `as1.prefix_urls` function.
* RSS:
  * Remove `itunes:category`. It has to be [one of Apple's explicit categories](https://feedgen.kiesow.be/ext/api.ext.podcast.html#feedgen.ext.podcast.PodcastExtension.itunes_category), which we aren't prepared to validate, so don't try.
* ActivityStreams 2:
  * Translate both `url` and `urls` from AS1 into multi-valued AS2 `url` field.
* Move a number of utility methods from the `Source` class to a new `as1` module: `object_type`, `merge_by_id`, `is_public`, `add_rsvps_to_event`, `get_rsvps_from_event`, `activity_changed`, `append_in_reply_to`, `actor_name`, `original_post_discovery`.
* `as1.original_post_discovery`: remove deprecated `cache` kwarg.

_Non-breaking changes:_

* ActivityStreams 2:
  * Fix spec compliance bug: [`icon` and `image` are singly valued, not multiply valued](https://www.w3.org/TR/activitystreams-vocabulary/#dfn-icon).
  * Add new `is_public` method and `PUBLIC_AUDIENCE` constant.
  * Prefer `"objectType": "featured"` first in the `image` field when converting from AS1, last in the `icon` field. This matches the ActivityPub (Mastodon) convention of using `icon` for profile pictures and `image` for header images.
  * Propagate `url` values into new `PropertyValue` attachments on `Person` objects; these end up in Mastodon's "profile metadata" link fields.
  * `to_as1`: if an attachment's `mediaType` is `image/...`, override `objectType` and set it to `image`.
* Twitter
  * Trim alt text in line between post preview and creation
  * Correctly trim Twitter alt text
* Facebook
  * Scraping: extract post id and owner id from `data-ft` attribute and `_ft_` query param more often instead of `story_fbid`, which is now an opaque token that changes regularly. ([facebook-atom#27](https://github.com/snarfed/facebook-atom/issues/27))
* Instagram
  * Add new `Instagram.scraped_json_to_activities` method.
* GitHub
  * `create` and `preview`: convert profile URLs to @-mentions, eg `https://github.com/snarfed` to `@snarfed` ([bridgy#1090](https://github.com/snarfed/bridgy/issues/1090)).
    * `get_activities` with `activity_id` now supports `fetch_replies` and `fetch_likes`.
* Reddit
  * Add `cache` support to `get_activities`.
* REST API
  * Add new `/scraped` endpoint that accepts `POST` requests with silo HTML as input. Currently only supports Instagram. Requires `site=instagram`, `output=...` (any supported output format), and HTML as either raw request body or MIME multipart encoded file in the `input` parameter.
* microformats2
  * Add new `extra` and `body_class` kwargs to `activities_to_html`.
  * When converting `u-featured` images to AS1, add new non-standard `"objectType": "featured"` field to distinguish them from `u-photo`.
  * Convert `p-note` to AS1 `summary`.
  * Bug fixes for converting `image` attachments to `photo`.
* `Source.original_post_discovery`: add new `max_redirect_fetches` keyword arg.

### 4.0 - 2022-03-23

_Breaking changes:_

* Drop Python 3.5 support. Python 3.6 is now the minimum required version.

_Non-breaking changes:_

* RSS:
  * Add support for RSS input via new `rss.to_activities` function.
* Add new `include_shares` kwarg to `get_activities`, implemented for Twitter and Mastodon. Defaults to `True`. If `False`, shares (retweets in Twitter, boosts in Mastodon) will be discarded and not returned. Also add a corresponding `shares` query param to the REST API.
* Instagram (scraping):
  * Handle media items with no `user` object, add new fetch for comments.
  * Add `Instagram.merge_scraped_comments()`.
* ActivityStreams 2:
  * Handle error when `type` isn't a string.
* Reddit:
  * Implement `get_activities()` to fetch posts by the current user or a user specified with `user_id`.
* Facebook scraping:
  * Skip "Suggested for you" posts.
  * Add `log_html` kwarg to `get_activities`; defaults to False.
  * Miscellaneous bug fixes.
* JSONFeed:
  * Handle malformed `items.author` element.

### 3.2 - 2021-09-15
* `Source.original_post_discovery`: add new `include_reserved_hosts` kwarg, defaults to `True`.
* Instagram:
  * Update scraping to handle new `feed_v2` JSON format.
* Facebook:
  * Scraping: handle pictures, videos, link attachments, and text links in timeline/news feed posts.
* Mastodon:
  * Bug fix for `get_activities()` with `fetch_mentions=True`: handle notifications with `status: null`. Maybe happens when a status is deleted?
  * `create`/`preview_create`: support bookmarks. (Nothing special happens with them; their `content` is posted as a normal toot.)
* microformats2:
  * Stop rendering `image.displayName` as visible text in HTML, since it's already in the `<img>`'s `alt` attribute.
  * Add [`bookmark-of`](https://indieweb.org/bookmark#How_to_markup) support.
  * Add `prefix_image_urls()` function.
  * Handle null `content` in AS1/2 objects.
  * `json_to_object` bug fix for composite `bookmark-of` properties.
* Twitter:
  * `create`/`preview`: [support large videos](https://twittercommunity.com/t/large-file-can-not-be-finalized-synchronously/82929/3) via async upload. We now pass `media_category=tweet_video` to the chunked upload `INIT` stage, and then make blocking `STATUS` calls until the video is finished processing. ([bridgy#1043](https://github.com/snarfed/bridgy/issues/1043))
  * `create`/`preview`: allow bookmarks. ([bridgy#1045](https://github.com/snarfed/bridgy/issues/1045))
  * `create`/`preview`: allow non-Twitter replies, ie activities that include `inReplyTo` URLs even if none of them point to a tweet. ([bridgy#1063](https://github.com/snarfed/bridgy/issues/1063))
  * `get_activities`: support list ids as well as slugs.
  * Bug fixes for removing t.co links to quoted tweets.
  * Bug fix for multiple instances of the same link in tweet text.
  * `get_activities()`: raise `ValueError` on invalid `user_id`.
* REST API: ported web framework from webapp2 to Flask. No user-visible behavior change expected.

### 3.1 - 2021-04-03

* Add Python 3.8 support, drop 3.3 and 3.4. Python 3.5 is now the minimum required version.
* Add [Pixelfed](https://pixelfed.org/)! Heavily based on Mastodon.
* Standardize Instagram's and Facebook's scraping into new common `scraped_to_activities()`, `scraped_to_activity()`, and `merge_scraped_reactions()` methods.
* Atom:
  * Add the `summary` element ([#157](https://github.com/snarfed/granary/issues/157)).
* REST API:
  * Bug fix: URL-encode Unicode characters in `Link` HTTP headers (eg `rel=self`, `rel=header`).
* Facebook:
  * Scraping now uses [mbasic.facebook.com](https://mbasic.facebook.com/) instead of [m.facebook.com](https://m.facebook.com/).
* Flickr:
  * Add support for adding tags to existing photos ([bridgy#857](https://github.com/snarfed/bridgy/issues/857)).
  * `get_comment()`: skip fetching comments from API if `activity` kwarg is provided and contains the requested comment.
* GitHub:
  * Handle [HTTP 451 Unavailable for Legal Reasons](https://en.wikipedia.org/wiki/HTTP_451) responses ([eg for DMCA takedowns](https://developer.github.com/changes/2016-03-17-the-451-status-code-is-now-supported/)) gracefully.
  * Add create/preview support for reactions on pull review request comments (ie URLs with `#discussion_r...` fragments).
* HTML/microformats2:
  * Add `aria-hidden="true"` to empty links ([bridgy#947](https://github.com/snarfed/bridgy/issues/947)).
  * Bug fix: escape `&`, `<`, and `>` characters in bare mf2 `content` properties ([aaronpk/XRay#102](https://github.com/aaronpk/XRay/issues/102)).
  * `json_to_object()`: convert `nickname` to `username`.
* JSON Feed:
  * Gracefully handle when `content_html` and `content_text` are [incorrectly](https://jsonfeed.org/version/1#items) lists instead of strings.
* Instagram:
  * Include threaded (ie nested) comments in scraping ([bridgy#958](https://github.com/snarfed/bridgy/issues/958)).
* Mastodon:
  * Bug fix for alt text with image attachments ([bridgy#975](https://github.com/snarfed/bridgy/issues/975)).
  * Omit empty `limit` param [for compatibility with Pleroma](https://git.pleroma.social/pleroma/pleroma/-/issues/2198) ([bridgy#977](https://github.com/snarfed/bridgy/issues/977)).
* Meetup:
  * `create()`: handle API errors and return the error message in the `CreationResult` ([bridgy#921](https://github.com/snarfed/bridgy/issues/921)).
* Twitter:
  * Bug fix: URL-encode list names in API calls.
  * Bug fix: propagate alt text into AS1 `photo.displayName` so that it gets all the way into microformats2 JSON and HTML ([#183](https://github.com/snarfed/granary/issues/183)).
* Reddit:
  * Implement `post_id()`.
  * Cache user data fetched from the API for 5m to avoid repeating user profile API requests ([bridgy#1021](https://github.com/snarfed/bridgy/issues/1021)).
    when fetching multiple comments or posts from the same author
  * Bug fix: use 'displayName' instead of 'name' in AS1 objects for submissions.
  * Bug fix: use tag URIs for activity ids.
* ActivityStreams 2:
  * `to_as1()`: for `Create` activities, include the activity actor's data in the object's author ([snarfed/bridgy-fed#75](https://github.com/snarfed/bridgy-fed/issues/75)).
  * `to_as1()`: convert `preferredUsername` to `username`.
  * `from_as1()`: convert `username` to `preferredUsername`.
  * `from_as1()`: bug fix, make `context` kwarg actually work.

### 3.0 - 2020-04-08

_Breaking changes:_

* _Python 2 is no longer supported!_ Including the [App Engine Standard Python 2 runtime](https://cloud.google.com/appengine/docs/standard/python/). On the plus side, the [Python 3 runtime](https://cloud.google.com/appengine/docs/standard/python3/) is now supported! See this [list of differences](https://cloud.google.com/appengine/docs/standard/python3/python-differences) for more details.

Non-breaking changes:

* Migrate demo app and API to the App Engine Standard Python 3 runtime.
* Instagram:
  * Scraping: fetch 50 likes instead of 24. ([snarfed/bridgy#898](https://github.com/snarfed/bridgy/issues/898))
  * Scraping bug fix for `get_actor()` with `user_id`.
* Twitter:
  * Add [image alt text](https://blog.twitter.com/developer/en_us/a/2016/alt-text-support-for-twitter-cards-and-the-rest-api.html) support to `get_activites()` etc ([#183](https://github.com/snarfed/granary/issues/183)).
* RSS:
  * Add `itunes:image`, `itunes:author`, and `itunes:category`.
  * Strip HTML from `title` element ([#177](https://github.com/snarfed/granary/issues/177)). [Background.](https://validator.w3.org/feed/docs/warning/ContainsHTML.html)
  * Always include author in items ([#177](https://github.com/snarfed/granary/issues/177)).
  * Bug fix: extract feed image from `hfeed` correctly.
  * Bug fix: don't crash on `article` or `mention` tags in items with enclosures.
* Atom:
  * Bug fix: extract feed image from `hfeed` correctly.
* REST API:
  * Add HTTP `HEAD` support.
  * Add support for URL fragments with `input=html`. If a fragment is provided, only that specific element is extracted and converted. ([#185](https://github.com/snarfed/granary/issues/185))
* GitHub:
  * Publish: preserve `<code>` tags instead of converting them to \`s so that GitHub renders HTML entities like `&gt;` inside them instead of leaving them escaped. [Background.](https://chat.indieweb.org/dev/2019-12-24#t1577174464779200)
* JSON Feed:
  * Handle malformed attachments better.
* microformats2:
  * Don't crash on string `context` fields.
  * `html_to_activities()`: limit to `h-entry`, `h-event`, and `h-cite` items ([#192](https://github.com/snarfed/granary/issues/192)).
* The `cache` kwarg to `Source.original_post_discovery()` now has no effect. `webutil.util.follow_redirects()` has its own built in caching now.
* Added Meetup.com support for publishing RSVPs.

### 2.2 - 2019-11-02
* Add Mastodon support!
* Add Python 3.7 support, and improve overall Python 3 compatibility.
* Update a number of dependencies.
* Switch from Python's built in `json` module to [`ujson`](https://github.com/esnme/ultrajson/) to speed up JSON parsing and encoding.
* Add `duration` and `size` support to ActivityStreams 1 and 2, RSS, and microformats2 HTML and JSON. [microformats2 support is still emerging for both](https://indieweb.org/podcast#Brainstorming). Both integer seconds and [ISO 8601 string durations](https://en.wikipedia.org/wiki/ISO_8601#Durations) are supported for `duration`. Integer bytes is used for `size` everywhere. microformats2 HTML also includes human-readable strings, eg `5.1 MB`. ([#169](https://github.com/snarfed/granary/issues/169))
* Twitter:
  * `[preview]_create()`: detect attempts to upload [images over 5MB](https://developer.twitter.com/en/docs/media/upload-media/uploading-media/media-best-practices#image-specs) and return an error.
* Facebook:
  * Add `get_activities(scrape=True)` for scraping HTML from [m.facebook.com](https://m.facebook.com/). Requires `c_user` and `xs` cookies from a logged in session ([snarfed/bridgy#886](https://github.com/snarfed/bridgy/issues/886)).
  * [Upgrade Graph API version from 2.10 to 4.0.](https://developers.facebook.com/docs/graph-api/changelog)
* Atom:
  * Bug fix for de-duping images in attachments.
* RSS:
  * Wrap all `<description>` element contents in `CDATA` sections.
  * Render images in `<description>` with HTML `<img>` tags ([#175](https://github.com/snarfed/granary/issues/175)).
  * `from_activities()` bug fix: don't crash when converting multiple attachments to enclosures in a single item. (RSS only supports one enclosure per item, so we now only include the first, and log a warning if the activity has more.)

### 2.1 - 2019-09-04
* Convert AS2 `Mention` tags to AS1 `objectType` `mention` (non-standard) and vice versa ([snarfed/bridgy-fed#46](https://github.com/snarfed/bridgy-fed/issues/46)).
* Twitter:
  * Bug fix for large block list fetches that get rate limited after a few successful requests.
  * Handle HTTP 403 + error code 200 when fetching retweets for a protected or otherwise unavailable tweet ([bridgy#688](https://github.com/snarfed/bridgy/issues/688#issuecomment-520600329)).
  * Demote @-mentions from [person-tags](https://indieweb.org/person-tag) to [mentions](https://indieweb.org/mention). Specifically, this means they'll no longer get rendered with `u-category` mf2.
* Instagram:
  * Disabled in the REST API entirely due to Instagram's aggressive rate limiting and blocking ([bridgy#655](https://github.com/snarfed/bridgy/issues/665#issuecomment-524977427)).
  * Update scraping to handle replies in new `edge_media_to_parent_comment` field ([#164](https://github.com/snarfed/granary/issues/164)).
  * Use cookie for all scraping HTTP requests, not just for likes.
* microformats2:
  * Revise whitespace handling; use `white-space: pre` CSS in HTML output.
* Facebook:
  * Bug fix: don't interpret `photo.php` as username in post URLs.
* Atom:
  * Switch from `white-space: pre` CSS back to converting newlines to `<br>`s because some feed readers ([eg NewsBlur](https://forum.newsblur.com/t/android-cant-read-line-pre-formatted-lines/6116)) follow it too strictly and don't even line wrap.
* RSS:
  * Default title to ellipsized content.

### 2.0 - 2019-03-01

_Breaking change_: drop Google+ since [it shuts down in March](https://developers.google.com/+/api-shutdown). Notably, this removes the `googleplus` module.

### 1.15 - 2019-02-28
* Add RSS 2.0 output! ([#124](https://github.com/snarfed/granary/issues/124))
* All silos:
  * Switch users' primary URLs from web site to silo profile ([#158](https://github.com/snarfed/granary/issues/158)).
* GitHub:
  * Don't enclose bare URLs in `<`/`>` ([snarfed/bridgy#850](https://github.com/snarfed/bridgy/issues/850)).
* Atom:
  * Bug fix for actors and attachments with multiple image URLs.
  * Bug fix for attachment author objects with no properties.
* Google+:
  * Drop from web UI and REST API since [consumer Google+ is shutting down entirely](https://blog.google/technology/safety-security/expediting-changes-google-plus/) ([more](https://github.com/snarfed/bridgy/issues/846)).
  * Switch from deprecated global API endpoint to G+ endpoint. Background in [snarfed/bridgy#846](https://github.com/snarfed/bridgy/issues/846), [Google blog post](https://developers.googleblog.com/2018/03/discontinuing-support-for-json-rpc-and.html) [and docs](https://developers.google.com/api-client-library/python/guide/batch).
* Instagram:
  * Fix individual photo/video link urls for multi-photo/video posts.
  * Handle [user-provided alt text](https://instagram-press.com/blog/2018/11/28/creating-a-more-accessible-instagram/) ([#159](https://github.com/snarfed/granary/issues/159)).
* Twitter:
  * Update max video upload size from 5MB to 512MB ([#162](https://github.com/snarfed/granary/issues/162)).
* `/url`: Return HTTP 400 when fetching the user's URL results in an infinite redirect.

### 1.14 - 2018-11-12
Add `delete()`. Currently includes Twitter and Flickr support.
* Instagram:
  * Make extra HTTP fetch (with cookie) to get individual likes ([snarfed/bridgy#840](https://github.com/snarfed/bridgy/issues/840)).
  * Update scraping logic to handle feed HTML changes.
  * Link @-mentions in comments as well as photo/video captions.
* GitHub:
  * `create`/`preview_create` bug fixes for issues and comments on private repos.
  * Handle HTTP 410 Gone responses from REST API, eg when a repo has been deleted or issues for the repo disabled.
* Twitter:
  * Add `delete()` and `preview_delete()` for deleting tweets.
* Flickr:
  * Add `delete()` and `preview_delete()` for deleting photos.
* microformats2:
  * Add [follow-of](https://indieweb.org/follow) support.
  * Only use quotation-of property for quote tweets, not URLs. ([#155](https://github.com/snarfed/granary/issues/155))
  * If a tag has startIndex/length, it gets linkified in the content, so don't also emit an mf2 child or HTML h-cite for it. ([#155](https://github.com/snarfed/granary/issues/155)
* Atom:
  * Encode `&`s in author URL and email address too. (Thanks [sebsued](https://twitter.com/sebsued)!)
* AS2:
  * Add `Follow` support.

### 1.13 - 2018-08-08
* Twitter:
  * Support ISO 8601 formatted created_at timestamps, which the [archive download uses](https://help.twitter.com/en/managing-your-account/how-to-download-your-twitter-archive), as well as RFC 2822 from the API.
  * `create()` and `preview_create()`: support RSVPs. Tweet them as normal tweets with the RSVP content. ([snarfed/bridgy#818](https://github.com/snarfed/bridgy/issues/818))
  * `create()` and `preview_create()`: support alt text for images, via AS1 `displayName`. ([snarfed/bridgy#756](https://github.com/snarfed/bridgy/issues/756)).
* Instagram:
  * Add global rate limiting lock for scraping. If a scraping HTTP request gets a 429 or 503 response, we refuse to make more requests for 5m, and instead short circuit and return the same error. This can be overridden with a new `ignore_rate_limit` kwarg to `get_activities()`.
* GitHub:
  * Add `tag` support to `create`/`preview_create` to add label(s) to existing issues ([snarfed/bridgy#811](https://github.com/snarfed/bridgy/issues/811)).
  * Escape HTML characters (`<`, `>`, and `&`) in content in `create()` and `preview_create()` ([snarfed/bridgy#810](https://github.com/snarfed/bridgy/issues/810)).
  * `get_activities()` and `get_comment()` now return `ValueError` instead of `AssertionError` on malformed `activity_id` and `comment_id` args, respectively.
  * `get_activities()` bug fix for issues/PRs with no body text.
  * Switch from GraphQL to REST API for creating comments and reactions, since GraphQL hits authorization errors on many org repos. ([snarfed/bridgy#824](https://github.com/snarfed/bridgy/issues/824))
  * Improve GraphQL support for comments and users.
* Atom:
  * Shorten and ellipsize feed title when necessary ([#144](https://github.com/snarfed/granary/issues/144)).
* microformats2:
  * Upgrade mf2py to improve a few things like [implied p-name detection](http://microformats.org/wiki/microformats2-implied-properties) and whitespace handling ([#142](https://github.com/snarfed/granary/issues/142), fixes [#145](https://github.com/snarfed/granary/issues/145), [snarfed/bridgy#756](https://github.com/snarfed/bridgy/issues/756), [snarfed/bridgy#828](https://github.com/snarfed/bridgy/issues/828)).
  * Support `alt` attribute in `<img>` tags ([snarfed/bridgy#756](https://github.com/snarfed/bridgy/issues/756)).

### 1.12 - 2018-03-24
* Add Python 3 support! Granary now requires either Python 2.7+ or Python 3.3+.
* Instagram:
  * Fix scraping profile pages.
* Twitter:
  * Update character counting to handle Twitter change that now auto-links *all* ccTLDs. [Background.](https://github.com/kylewm/brevity/issues/8)
* GitHub:
  * Bug fix for `get_activities()` with deleted issues and repos.
* microformats2:
  * `object_to_json()`: convert tags to simple strings in the `category` property, not full nested objects like `h-card`s ([#141](https://github.com/snarfed/granary/issues/141)).
  * Special case GitHub issues that are in-reply-to a repo or its `/issues` URL to be objectType `issue`.
  * Render simple string categories in HTML output.

This release is intentionally small and limited in scope to contain any impact of the Python 3 migration. It *should* be a noop for existing Python 2 users, and we've tested thoroughly, but I'm sure there are still bugs. Please file issues if you notice anything broken!

### 1.11 - 2018-03-09
* Add GitHub!
  * `get_activities()` supports issues and pull requests, including comments and reactions. It's currently based on notifications, so it's best effort, not comprehensive, and only includes recently active issues/PRs.
  * `create()` and `preview_create()` support issues, comments, [stars](https://help.github.com/articles/about-stars), and [reactions](https://help.github.com/articles/about-conversations-on-github/#reacting-to-ideas-in-comments).
* Twitter:
  * Prefer MP4 and other video/... content types to HLS (.m3u8) etc. [Background.](https://twittercommunity.com/t/retiring-mp4-video-output/66093)
  * Prefer HTTPS URLs for media images.
  * `get_activities()`: Support @-prefixed usernames in `user_id`.
* Facebook:
  * Support new [recurring aka multi-instance events](https://stackoverflow.com/questions/45131646/decoding-recurring-events-from-facebook-open-graph-api). `create()` and `preview_create()` now only support RSVPs to individual instances of multi-instance events, to match the Facebook API itself.
  * Try harder to find original (full) sized photo URLs, specifically `_o.jpg` files instead of `_s.jpg`.
  * `create()` bug fix for photo and image URLs with unicode characters.
  * Fixed bug where `get_activities(user_id=...)` included the authenticated user's own recent photos, albums, and news publishes.
* Instagram:
  * Extract more user (`author`) data from scraped profile pages.
  * Fix home page feed scraping.
* microformats2, Atom:
  * Add enclosures for image attachments.
  * Bug fixes for rendering image, video, and audio attachments inside shares and attachments. De-dupe images.
* microformats2:
  * Handle simple string-only author properties.
  * Add `fetch_mf2` kwarg to `json_to_object()` for fetching additional pages over HTTP to determine authorship.
  * Generate explicit blank `p-name` in HTML to prevent old flawed [implied p-name handling](http://microformats.org/wiki/microformats2-implied-properties) ([#131](https://github.com/snarfed/granary/issues/131)).
  * Fix `share` verb handling in `activity_to_json()` and `activities_to_html()` ([#134](https://github.com/snarfed/granary/issues/134)).
  * Remember which content contains HTML, preserve newlines in it, and don't translate those newlines to `<br>`s ([#130](https://github.com/snarfed/granary/issues/130)).
* Atom:
  * Fix timezone bugs in `updated` and `published`.
* JSON Feed:
  * Omit title from items if it's the same as the content. (Often caused by microformats2's implied `p-name` logic.)

### 1.10 - 2017-12-10
* Moved web site and REST API to [granary.io](https://granary.io/)! [granary-demo.appspot.com](https://granary-demo.appspot.com/) now 301 redirects.
* Twitter:
  * Update the publish character limit to 280. [Background.](https://twittercommunity.com/t/updating-the-character-limit-and-the-twitter-text-library/96425)
  * Fix a [bug in preview_create that auto-linked @-mentions inside URLs](https://github.com/snarfed/bridgy/issues/527#issuecomment-346302800), e.g. Medium posts.
  * Support videos and animated GIFs in `get_activities()` etc.
* Instagram:
  * Add cookie query param to REST API to allow scraping that logged in user's feed.
* HTML (including Atom content):
  * Render image, video, and audio attachments more often and consistently.
  * Include microformats2 `u-photo`, `u-video`, and `u-audio` classes more often and consistently.
* Atom:
  * Add `atom_to_activities()` for converting full feed documents.
  * Add to REST API and web UI.
  * Include source URL in `rel=alternate` link as well as actor/author URL ([#151](https://github.com/snarfed/granary/issues/151)).
* JSON Feed:
  * Fix bug that omitted title in some cases ([#122](https://github.com/snarfed/granary/issues/122)).

### 1.9 - 2017-10-24

* Add [ActivityStreams 2.0](http://www.w3.org/TR/activitystreams-core/)! New `as2` module includes `to_as1()` and `from_as1()` functions. Currently supported: articles, notes, replies, likes, reposts, events, RSVPs, tags, attachments.
* Atom:
  * Add new `atom_to_activity()` function for converting Atom to AS1.
  * Add email field to author, if provided.
* JSON Feed:
  * Raise ValueError on bad (non-dict) input.
* REST API:
  * Add `as2` value for `format` and `input`. Revise existing ActivityStreams and microformats2 value names to `as1`, `as1-xml`, and `mf2-json`. Old values `activitystreams`, `json`, `json-mf2`, and `xml` are still accepted, but deprecated.

### 1.8 - 2017-08-29

* Add [JSON Feed](https://jsonfeed.org/) support to both library and REST API.
* Twitter:
    * Add `get_blocklist()`.
    * Bug fix for creating replies, favorites, or retweets of video URLs, e.g. https://twitter.com/name/status/123/video/1 .
    * Bug fix for parsing favorites HTML to handle a small change on Twitter's side.
    * `post_id()` now validates ids more strictly before returning them.
* Facebook:
    * Improve heuristic for determining privacy of wall posts from other users.
    * Support GIFs in comments (attachment types `animated_image_autoplay` and `animated_image_share`).
    * Upgrade Graph API from [v2.6](https://developers.facebook.com/docs/apps/changelog#v2_6) to [v2.10](https://developers.facebook.com/docs/apps/changelog#v2_10).
* Instagram:
    * Update scraping to handle new home page (ie news feed) JSON schema, which changed sometime around 2017-02-27. (Profile pages and individual photo/video permalinks still haven't changed yet.)
* microformats2:
    * Add [`u-featured`](https://indieweb.org/featured) to ActivityStreams `image`.
    * Improve `h-event` support.
    * Minor whitespace change (added <p>) when rendering locations as HTML.
    * `post_id()` now validates ids more strictly before returning them.
    * Fix bugs in converting latitude and longitude between ActivityStreams and mf2.
* Google+:
    * Update HTML scraping to handle changed serialized JSON data format.
* Atom:
    * Add new `activity_to_atom()` function that renders a single top-level `<entry>` instead of `<feed>`.
    * Add new `reader` query param for toggling rendering decisions that are specific to feed readers. Right now, just affects location: it's rendered in the content when `reader=true` (the default), omitted when `reader=false`.
    * Include author name when rendering attached articles and notes (e.g. quote tweets).
    * Only include AS `activity:object-type` and `activity:verb` elements when they have values.
    * Render AS image and mf2 u-photo if they're not already in content.
    * Render `thr:in-reply-to` from `object.inReplyTo` as well as `activity.context.inReplyTo`.
* REST API:
    * Fix bugs in html => json-mf2 and html => html conversions.
* Upgrade brevity to 0.2.14 for a couple [bug](https://github.com/kylewm/brevity/issues/5) [fixes](https://github.com/kylewm/brevity/issues/6).

### 1.7 - 2017-02-27
* microformats2:
    * Interpret h-cite and [u-quotation-of](https://indieweb.org/quotation#How_to_markup) (experimental) as attachments, e.g. for quote tweets.
    * Convert [audio](http://indieweb.org/audio) and [video](http://indieweb.org/video) properties to AS attachments.
* Twitter:
    * Linkify @-mentions and hashtags in `preview_create()`.
    * Support creating quote tweets from attachments with Twitter URLs.
    * When converting quote tweets to AS, strip quoted tweet URL from end of text.
    * Raise ValueError when `get_activities()` is passed `group_id='@search'` but not `search_query`.
* Instagram:
    * Improve HTML scraping error handling.
    * Support [multi-photo/video posts](https://www.instagram.com/p/BQ0mDB2gV_O/).
* Facebook:
    * Disable creating "interested" RSVPs, since Facebook's API doesn't allow it.
* Atom:
    * Support [media enclosures](http://atomenabled.org/developers/syndication/#link) for audio and video attachments.
* Source.get_activities(): start raising ValueError on bad argument values, notably invalid Facebook and Twitter ids and Instagram search queries.
* Fix rendering and linkifying content with Unicode high code points (ie above the 16-bit Basic Multilingual Plane), including some emoji, on "narrow" builds of Python 2 with `--enable-unicode=ucs2`, which is the default on Mac OS X, Windows, and older *nix.

### 1.6 - 2016-11-26
* Twitter:
    * Handle new "extended" tweets with hidden reply-to @-mentions and trailing
    URLs for media, quote tweets, etc. Background:
    https://dev.twitter.com/overview/api/upcoming-changes-to-tweets
    * Bug fix: ensure like.author.displayName is a plain unicode string so that it
    can be pickled normally, e.g. by App Engine's memcache.
    * Bug fix: handle names with emoji correctly in favorites_html_to_likes().
    * Bug fix: handle search queries with unicode characters.
* Atom:
    * Render full original quoted tweet in retweets of quote tweets.
* microformats2 HTML:
    * Optionally follow and fetch rel="author" links.
    * Improve mapping between microformats2 and ActivityStreams 'photo' types. (mf2 'photo' type is a note or article *with* a photo, but AS 'photo' type *is* a photo. So, map mf2 photos to underlying type without photo.)
    * Support location properties beyond h-card, e.g. h-adr, h-geo, u-geo, and even
    when properties like latitude and longitude appear at the top level.
* Error handling: return HTTP 502 for non-JSON API responses, 504 for connection failures.

### 1.5 - 2016-08-25
* REST API:
    * Support tag URI for user id, app id, and activity id.
* Twitter:
    * Better error message when uploading a photo with an unsupported type.
    * Only include original quote tweets, not retweets of them.
    * Skip fetching retweets for protected accounts since the API call always 403s.
* Flickr:
    * Better username detection. Flickr's API is very inconsistent about username
    vs real name vs path alias. This specifically detects when a user name is
    probably actually a real name because it has a space.
    * Uploading: detect and handle App Engine's 10MB HTTP request limit.
    * Bug fix in create: handle unicode characters in photo/video description,
    hashtags, and comment text.
* Atom:
    * Bug fix: escape &s in attachments' text (e.g. quote tweets).
    * Bug fix: handle multiply valued 'object' fields in ActivityStreams 1 activities.
* GitHub:
    * Switch creating comments and reactions from GraphQL to REST API ([bridgy#824](https://github.com/snarfed/bridgy/issues/824).

### 1.4.1 - 2016-06-27
* Bump oauth-dropins requirement to 1.4.

### 1.4.0 - 2016-06-27
* REST API:
    * Cache silo requests for 5m by default, 60m for Instagram because they aggressively blocking scraping. You can skip the cache with the new cache=false query param.
* Facebook:
    * Upgrade from API v2.2 to v2.6. https://developers.facebook.com/docs/apps/changelog
    * Add reaction support.
    * De-dupe event RSVPs by user.
* Twitter:
    * Switch create() to use brevity for counting characters. https://github.com/kylewm/brevity
    * Fix bug in create() that occasionally incorrectly escaped ., +, and - characters.
    * Fix text rendering bug when there are multipl photos/videos.
    * When replying to yourself, don't add a self @-mention.
* Instagram:
    * Fix bugs in scraping.
* Upgrade to requests 2.10.0 and requests-toolbelt 0.60, which support App Engine.

### 1.3.1 - 2016-04-07
* Update [oauth-dropins](https://github.com/snarfed/oauth-dropins) dependency to >=1.3.

### 1.3.0 - 2016-04-06
* Support posting videos! Currently in Facebook, Flickr, and Twitter.
* Instagram:
    * Add support for scraping, since they're [locking down their API and requiring manual approval](http://developers.instagram.com/post/133424514006/instagram-platform-update).
    * Linkify @-mentions in photo captions.
* Facebook:
    * Fetch [Open Graph stories](https://developers.facebook.com/docs/reference/opengraph/action-type/news.publishes/) aka `news.publish` actions.
    * Many bug fixes for photo posts: better privacy detection, fix bug that attached comments to wrong posts.
* Twitter:
    * Handle all photos/videos attached to a tweet, not just the first.
    * Stop fetching replies to @-mentions.
* Atom:
    * Render attachments.
    * Add `xml:base`.
* microformats2:
    * Load and convert h-card.
    * Implement full post type discovery algorithm, using mf2util. https://indiewebcamp.com/post-type-discovery
    * Drop support for h-as-* classes, both incoming and outgoing. They're deprecated in favor of post type discovery.
    * Drop old deprecated `u-like` and `u-repost` properties.
* Misc bug fixes.
* Set up Coveralls.

### 1.2.0 - 2016-01-11
* Improve original post discovery algorithm. ([bridgy #51](https://github.com/snarfed/bridgy/issues/51))
* Flickr tweaks. ([bridgy #466](https://github.com/snarfed/bridgy/issues/466))
* Add mf2, activitystreams, atom, and search to interactive UI. ([#31](https://github.com/snarfed/granary/issues/31), [#29](https://github.com/snarfed/granary/issues/29))
* Improved post type discovery (using mf2util).
* Extract user web site links from all fields in profile (e.g. description/bio).
* Add fabricated fragments to comment/like permalinks (e.g. #liked-by-user123) so that object urls are always unique (multiple silos).
* Improve formatting/whitespace support in create/preview (multiple silos).
* Google+:
    * Add search.
* Facebook:
    * Fetch more things in get_activities: photos, events, RSVPs.
    * Support person tags in create/preview.
    * Prevent facebook from automatically consolidating photo posts by uploading photos to "Timeline Photos" album.
    * Include title in create/preview.
    * Improve object id parsing/resolving.
    * Improve tag handling.
    * Bug fix for fetching nested comments.
    * Misc improvements, API error/flakiness handling.
* Flickr:
    * Create/preview support for photos, comments, favorites, tags, person tags, location.
* Twitter:
    * Create/preview support for location, multiple photos.
    * Fetch quote tweets.
    * Fetching user mentions improvements, bug fixes.
    * Fix embeds.
    * Misc AS conversion improvements.
* microformats2:
    * Improve like and repost rendering.
* Misc bug fixes.
* Set up CircleCI.

### 1.1.0 - 2015-09-06
* Add Flickr.
* Facebook:
    * Fetch multiple id formats, e.g. with and without USERID_ prefix.
    * Support threaded comments.
    * Switch from /posts API endpoint to /feed.
* Google+:
    * Support converting plus.google.com HTML to ActivityStreams.
* Instagram:
    * Support location.
* Improve original post discovery algorithm.
* New logo.

### 1.0.1 - 2015-07-11
* Bug fix for atom template rendering.
* Facebook, Instagram: support access_token parameter.

### 1.0 - 2015-07-10
* Initial PyPi release.
