"""Worked examples of domains and experiments built on `loopingrules`,
kept in this repo for demonstration -- see `README.md`'s "Scope" section
for what that does and does not mean. Not part of `packages=` in
`pyproject.toml`: `pip install -e .` installs `loopingrules` alone, and
nothing here is imported by it.

Domains: `cards`, `shopping`, `market`, `quorum`, `trip`. The two
domain-oblivious bridges they share are `judge` (`Risk`/`RiskTolerance`)
and `decide` (`Option`/`Score`/`Winner`).

The tuning experiment -- parameters as components the rules read, and a
search over their values against examples -- lives here too: `tuning` is
the instrument, `bridge_transfer` is Experiment 1, and `ablation` is
Experiment 2 plus the structure/ladder probes. See `docs/tuning.md`.
"""
