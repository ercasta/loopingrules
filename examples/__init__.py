"""Worked examples of domains built on `loopingrules`, kept in this repo
for demonstration -- see `README.md`'s "Scope" section for what that does
and does not mean. Not part of `packages=` in `pyproject.toml`: `pip
install -e .` installs `loopingrules` alone, and nothing here is imported
by it. `examples.cards` is the one domain; `examples.judge` and
`examples.parts` are not domains at all -- each is a prototype testing
one question a design conversation raised, neither imports `cards`
back, and each says which question in its own docstring. `examples.
circuits` USED to be a third such prototype -- promoted to `loopingrules.
circuits`, in the package itself, once the question it was testing
(a closed shape catalog restating real rules as data) had enough
cross-repo evidence behind it; see that module's own docstring and
`README.md`'s History for the promotion."""
