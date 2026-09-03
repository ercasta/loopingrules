"""Worked examples of domains built on `loopingrules`, kept in this repo
for demonstration -- see `README.md`'s "Scope" section for what that does
and does not mean. Not part of `packages=` in `pyproject.toml`: `pip
install -e .` installs `loopingrules` alone, and nothing here is imported
by it. `examples.cards` is the one domain; `examples.judge` is not a
domain at all -- a single domain-oblivious rule `cards` feeds, and the
only module here that never imports `cards` back. See `judge.py`'s own
docstring for the question it is testing."""
