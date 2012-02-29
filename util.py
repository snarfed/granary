#!/usr/bin/python
"""Misc utilities.
"""

__author__ = ['Ryan Barrett <activitystreams@ryanb.org>']


def to_xml(value):
  """Renders a dict (usually from JSON) as an XML snippet.
  """
  if isinstance(value, dict):
    elems = []
    for key, vals in value.iteritems():
      if not isinstance(vals, (list, tuple)):
        vals = [vals]
      elems.extend(u'<%s>%s</%s>' % (key, to_xml(val), key) for val in vals)
    return '\n' + '\n'.join(elems) + '\n'
  else:
    if value is None:
      value = ''
    return unicode(value)
