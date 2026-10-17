# Rule analysis

`analyze` answers "what does this rule touch?" by reading the source of an
ordinary Python rule and deriving its reads and writes.

## `analyze`: reads and writes from the AST

```python
from loopingrules import analyze

a = analyze.analyze(flag)       # -> Analysis
a.reads            # {Order, Bulk}       component types the rule queries
a.writes           # {Bulk}              component types it attaches, etc.
a.negated_reads    # subset of reads tested for ABSENCE
```

For several rules at once, `component_map` builds the "who reads and writes
what" map:

```python
rep = analyze.component_map(r1, r2, r3)
rep.reads      # {A: {'mod.r1'}, B: {'mod.r2'}}   type -> rule names that read it
rep.writes     # {B: {'mod.r1'}}                  type -> rule names that write it
rep.opaque     # {'mod.r3': "the world parameter 'w' is used in a way ..."}
```

This is a data-flow map of your rule set that no generic call-graph tool can
produce, because rules never call each other. They communicate only through
component types, and this is exactly that graph.

### Used automatically

`Loop.rule` calls `analyze` when you register a rule. If it resolves and has
positive reads, the rule is skipped on any tick where
`world.populated(*reads)` is false. You never declare this.

### It refuses instead of guessing

`analyze` raises `analyze.Opaque` when the rule steps outside its dialect
(the world parameter stored in a variable, forwarded through `*args`, passed
to an imported function, or a component argument that is not a literal type).
In `component_map`, such a rule lands in `opaque` with the reason and is
**absent** from `reads`/`writes`, because a partial map is worse than an
honest "unknown". In `Loop.rule`, an opaque rule is simply called every
tick.

Two caveats:

- `analyze` needs source. A function defined in an interactive prompt or piped
  to stdin has none, and comes back opaque ("no source available").
- It follows plain same-module helper functions, at any depth, but not
  imported ones.


