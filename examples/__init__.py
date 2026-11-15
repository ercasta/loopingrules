"""Worked examples of domains built on `loopingrules`, kept in this repo for
demonstration -- see `README.md`'s "Scope" section for what that does and does
not mean. Not part of `packages=` in `pyproject.toml`: `pip install -e .`
installs `loopingrules` and `loopingrules_calibration` alone, and nothing here
is imported by either.

Five survive the move to Plan U, chosen for the standard library the plan rests
on rather than kept wholesale:

* **`cards`** -- the flagship trading domain; a goal, a risk profile, and one
  autonomous agent reacting to a card market.
* **`market`** -- a richer *two-bridge* trading island, and `cards`'s partner
  for the "an island is reused across two domains" bar.
* **`shopping`** -- a second domain that reads the shipped `judge` pattern,
  proving its reuse.
* **`trip`** -- a graph / plan-search domain, through the `decide` bridge.
* **`decide`** -- the domain-oblivious bridge (`Option`/`Score`/`Winner`) that
  `market`/`trip` speak.

The tuning and dataset EXPERIMENTS (`ablation`, `acquisition`, `adapters`,
`branching`, `bridge_transfer`, `drift`) and the marginal domains (`party`,
`quorum`, `hierarchy`, `planning`, `trade`) are gone -- they belonged to the
research program (`docs/tuning.md`, Experiments 1-8) that Plan U supersedes, and
the correction pass retired the separate slow-timescale controller they existed
to test. `judge` (`Risk`/`RiskTolerance`) has been PROMOTED out of this
directory into `loopingrules_patterns`, which is where `cards`/`market`/
`shopping` import it from.
"""
