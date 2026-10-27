"""Worked examples of domains and experiments built on `loopingrules`,
kept in this repo for demonstration -- see `README.md`'s "Scope" section
for what that does and does not mean. Not part of `packages=` in
`pyproject.toml`: `pip install -e .` installs `loopingrules` and
`loopingrules_calibration` alone, and nothing here is imported by either.

Domains: `cards`, `shopping`, `market`, `quorum`, `trip`. The two
domain-oblivious bridges they share are `judge` (`Risk`/`RiskTolerance`)
and `decide` (`Option`/`Score`/`Winner`).

`trade` is a third oblivious module, of ownership rather than a claim:
`Holding`/`Movement`/`Agreed` describe who holds how much of an opaque
thing and one rule that moves amounts, refusing to overdraw. `adapters` is
the probe built on it -- an explicit, one-directional mapping between
`cards`' own `Purse`/`Copies` and `trade`'s shape, measuring whether
ownership stratifies while policy does not. See their own docstrings.

The tuning experiments -- parameters as components the rules read, and a
search over their values against examples -- live here, built on the kit in
`loopingrules_calibration`: `bridge_transfer` is Experiment 1, and
`ablation` is Experiment 2 plus the structure/ladder probes. See
`docs/tuning.md`.
"""
