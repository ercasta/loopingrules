# Rule analysis and circuits

Two modules answer "what does this rule touch?" in two different ways.

- **`analyze`** reads the source of an ordinary Python rule and derives its
  reads and writes.
- **`circuits`** is a small closed catalog of rule *shapes* that are plain
  data, so what they touch is known by construction.

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

## `circuits`: rules as data

`circuits` restates one rule family that turned out to be data rather than
control flow: *for each entity of a kind, compute something from arithmetic
over a few fields, then attach or detach a tag, or replace a value.*

```python
from loopingrules import circuits

tag_wanted = circuits.TagCircuit(
    for_each=Listing,
    condition=circuits.Lt(
        circuits.Coalesce(
            circuits.Via(Listing, "card", Copies, "count"),   # follow the id in Listing.card
            circuits.Const(0)),
        circuits.Via(Listing, "card", Wants, "qty"),
    ),
    tag=Wanted,
)
rule = circuits.compile_circuit(tag_wanted)     # -> an ordinary rule function
loop.rule(rule, name="tag wanted")
circuits.reads(tag_wanted)                      # {Listing, Copies, Wants}
```

(From `tests/test_circuits.py`, which restates the hand-written rules in
`examples/cards.py` this way and proves they behave identically.)

The vocabulary, in `circuits.py`:

| Group | Members |
|---|---|
| Values | `Self`, `Via`, `World`, `TheEntity`, `SelfId`, `Const` |
| Arithmetic | `Add`, `Sub`, `Mul`, `Min`, `Max`, `SafeDiv`, `Coalesce`, `If` |
| Text/lists | `Lower`, `Split`, `At`, `Len`, `ParseInt`, `FindBy`, `Format`, `Join`, `JoinStrings`, `Optional` |
| Conditions | `Le`, `Lt`, `Ge`, `Gt`, `Eq`, `Exists`, `HasSelf`, `And`, `Or`, `Not` |
| Quantifiers | `Any`, `Forall`, `Count`, `Children` |
| Circuits | `TagCircuit`, `ValueCircuit`, `ActionCircuit` |
| Effects | `ReplaceAt`, `Destroy`, `Spawn`, `Call`, `ToolRequest`, `ToolResult`, `Rejected` |

`evaluate`, `compile_circuit`, `compile_answerer`, `reads`, `writes` and
`destroys` are the functions that run and inspect them.

### Why so small

This is deliberately **not** a general DSL. It is a closed catalog, which is
what any future search or learning process over rules would need to be
tractable. Every component type and field a circuit touches is a **literal on
the spec, never computed at runtime**, which is what keeps `reads()` and
`writes()` exact. `TODO.md` and the README's History record what this
module has and has not settled.

`Call` and `ToolRequest` are how a data-authored rule reaches a real
capability (see `examples/files.py`) without ever being handed Python to do it
in.
