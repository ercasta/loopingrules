# Patterns

`loopingrules` ships no domain vocabulary — that is the engine's whole
stance. But some vocabulary is worth sharing across domains, and
`loopingrules_patterns` is where it lives: a small, curated library of
**patterns**, each exposing a [declared tunable surface](plan-calibration.md).
A pattern is importable, oblivious to the domain that installs it, and
calibratable by the same kit as any other rule.

```
pip install -e .   # installs loopingrules, loopingrules_calibration, loopingrules_patterns
```

## Two shapes, one package

- A **bridge** is a domain-oblivious reader over a thin shape several
  domains **project** onto, so the reader never learns what produced it
  (`judge`).
- A **shape** is a component vocabulary a domain instantiates, plus the
  rules over it.

Both live in the one package, one module per pattern.

## Only real reuse is promoted

`README.md`'s standing bar: a pattern is promoted here only when a **second
domain depends on it at runtime**, not merely in a test written to feed it.
`examples/` is the nursery; promotion is graduation. The engine's own rule —
"a domain that wants that pattern writes its own components and its own
generic reader over them" — still holds for anything with only one user.

## Shipped: `judge`

`loopingrules_patterns.judge` — the threshold judge. A domain's own rule
projects a normalized claim onto `Risk(level, reason)`; then `flag_too_risky`,
which has never heard of a listing, a purse or a deadline, flags anything
past the `RiskTolerance(max_level)` it owns.

```python
from loopingrules_patterns import judge

# a domain projects its own "how concerning" onto the shared shape...
w.replace(listing, judge.Risk(level, "most of the room left"))
# ...and the oblivious rule turns that into the domain's cue
if w.has(listing, judge.TooRisky):
    ...
```

Its tunable surface is `RiskTolerance.max_level`, declared on the rule with
`@tunable`, so a calibration can collect it from the loop:

```python
from loopingrules_calibration import calibrate, knobs
loop = ...                       # a domain installed judge.flag_too_risky
report = calibrate(install, cases, knobs(loop), scorer)
```

Three domains install it — `examples.cards`, `examples.market`,
`examples.shopping` — which is why it was the first to graduate.

## Shipped: `memory` (a declared surface, not a pattern)

`loopingrules_patterns.memory` holds the declared tunable surface for
`loopingrules.memory`, the engine's short-term memory. The mechanism stays in
the engine — it reads the transient change log, an engine primitive, and the
engine must not import `loopingrules_calibration` — so this module imports
`remember`/`forget` and attaches `Knob(MemoryPolicy, ...)` to those exact
functions. `knobs(loop)` and `lint` therefore see them like any pattern's
rules; there is no separate `MemoryPolicy`-shaped copy to drift.

## Not shipped yet

Named so the gap is not a surprise: the other candidates — a scored contest
(`examples.decide`), and the shape patterns (catalog + inventory,
wants/goal, question/investigation, ...) — are candidates listed in
`docs/plan.md`'s Phase 3, not guarantees.
