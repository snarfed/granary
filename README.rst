.. image:: https://raw.github.com/snarfed/granary/master/static/granary_logo_128.png
   :target: https://github.com/snarfed/granary
.. image:: https://circleci.com/gh/snarfed/granary.svg?style=svg
   :target: https://circleci.com/gh/snarfed/granary
.. image:: https://coveralls.io/repos/github/snarfed/granary/badge.svg?branch=master
   :target: https://coveralls.io/github/snarfed/granary?branch=master


Granary is a library and REST API that fetches and converts social network
data between a wide variety of formats:

- Facebook, Flickr, Google+, Instagram, and Twitter native APIs
- Instagram and Google+ scraped HTML
- `ActivityStreams <http://activitystrea.ms/>`__
- `microformats2 <http://microformats.org/wiki/microformats2>`__ HTML and JSON
- `Atom <http://atomenabled.org/>`__
- XML

`Try out the interactive demo <https://granary-demo.appspot.com/>`__ and
`check out the docs <https://granary.readthedocs.io/>`__.

License: This project is placed in the public domain.


Using
-----

The library and REST API are both based on the
`OpenSocial Activity Streams service <http://opensocial-resources.googlecode.com/svn/spec/2.0.1/Social-API-Server.xml#ActivityStreams-Service>`__.

Let's start with an example. This code using the library:

.. code:: python

    from granary import twitter
    ...
    tw = twitter.Twitter(ACCESS_TOKEN_KEY, ACCESS_TOKEN_SECRET)
    tw.get_activities(group_id='@friends')

is equivalent to this ``HTTP GET`` request:

::

    https://granary-demo.appspot.com/twitter/@me/@friends/@app/
      ?access_token_key=ACCESS_TOKEN_KEY&access_token_secret=ACCESS_TOKEN_SECRET

They return the authenticated user's Twitter stream, ie tweets from the
people they follow. Here's the JSON output:

.. code:: json

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

`Check out the docs for more! <https://granary.readthedocs.io/>`__
