"""Property-based tests, using hypothesis.

https://hypothesis.readthedocs.io/
"""
from hypothesis import settings

# the first example that parses HTML loads bs4, lxml, etc, which is slow and
# trips hypothesis's per-example deadline and gets reported as flakiness
settings.register_profile('granary', deadline=None)
settings.load_profile('granary')
