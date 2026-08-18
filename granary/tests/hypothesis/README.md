Property-based tests, using [hypothesis](https://hypothesis.readthedocs.io/).

They're slow, so they're kept out of `python -m unittest discover`. That's
enforced by naming: files here are `[module]_test.py`, which doesn't match
discover's default `test*.py` pattern. Don't name a new one `test_*.py`, or it
will run with the rest of the suite.

Run them with:

```sh
python -m unittest granary/tests/hypothesis/*.py
```
