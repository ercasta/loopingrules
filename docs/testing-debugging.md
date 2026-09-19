# Testing and debugging

All commands run from the repository root. The examples use the project
virtual environment, `.venv`, which is git-ignored.

## Set up

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"      # package + pytest
.venv\Scripts\python -m pytest -q                     # whole suite
```

On macOS or Linux, use `.venv/bin/python`.

## Running tests

```powershell
.venv\Scripts\python -m pytest tests\test_loop.py -q             # one file
.venv\Scripts\python -m pytest -k settl -q                       # by name
.venv\Scripts\python -m pytest -x --pdb                          # debugger at first failure
.venv\Scripts\python -m pytest tests\test_loop.py -k settl --trace   # stop at test start
```

`tests/` maps onto the modules:

| File | Pins down |
|---|---|
| `test_world.py` | identity, values, and the intersection of the two |
| `test_loop.py` | order, settling, the budget, a rule that raises |
| `test_engine.py` | one world, several channels, a broadcast reply |
| `test_save.py` | the same world, ids and all, next time |
| `test_analyze.py` | a rule's reads/writes, and where analysis refuses to guess |
| `test_circuits.py` | the catalog, proven against real rules from two domains |
| `test_memory.py` | `Focus`/`Memory`/`MemoryEntry`, genuine regain vs no-op reattach |
| `test_chart.py` | two idle ticks, exactly, and a covering combination |
| `test_share.py` | pack import, id remapping under collision, dangling refs skipped, a registry that never imports a name from the file |
| `test_examples_*.py` | each example domain, end to end |

## A test template

```python
import dataclasses
from loopingrules.loop import Loop

@dataclasses.dataclass(frozen=True)
class Ping: pass

def test_my_rule():
    loop = Loop()
    loop.rule(my_rule)
    loop.world.spawn(Ping())
    settled = loop.run()
    assert settled.hot == []          # it settled, it did not just hit the budget
    assert loop.errors == []          # and nothing raised
    assert loop.world.each(Pong)      # the thing you expect
```

Always assert `loop.errors == []`. A raising rule does not fail the loop.

## Debugging recipes

### A rule does nothing

1. Is it **dormant**? Check `analyze.analyze(fn).reads`. If none of those
   types exist yet, `Loop.tick` never calls the body. Put a `print` at the top;
   if it never appears, this is why. If `analyze` raises `Opaque`, the rule is
   called every tick instead.
2. Did a query match? `print(world.each(Kind))`.
3. Is an earlier rule consuming your input first? Check the order in
   `[n for n, _ in loop.rules]` and any `priority=`.

### The loop will not settle (`Settled(budget, hot=[...])`)

`hot` names the rules that were still changing the world when the budget ran
out. Usual causes: an unguarded spawn, attaching a different value each tick,
two rules that undo each other, or an in-place mutation followed by
`changed()`. Turn on tracing to see what they write.

### Tracing: which rule wrote what, on which tick

```python
loop = Loop(trace=True)          # or loop.tracing = True
loop.run()
for entry in loop.trace:         # TraceEntry(tick, rule, changes)
    print(entry.tick, entry.rule,
          [(c.action, c.entity, c.kind) for c in entry.changes])
```

Verified output for a small rule that spawns an entity and attaches to it:

```
[(1, '__main__.a', ['spawn', 'attach'])]
```

Each `Change` has `action` (`spawn`, `destroy`, `attach`, `detach`,
`replace`, `remove`, `changed`), `entity` (an id), `kind` (a type name)
and `component`. Tracing is off by default because it allocates per write.
It also attributes writes made by a rule that then raised.

### A rule raised

```python
for name, error in loop.errors:
    print(name, repr(error))
```

Only the first occurrence per rule and message is kept. Through an engine
you see it as an `{"error": ...}` message on every channel.

### Look at the world

```python
for e in world.entities():
    print(world.show(e))         # "#7  Entry(folder=1, ...)  Size(bytes=17)"
```

Through an engine, `/show` and `/rules` do the same on the engine thread.

### Step through one tick with a debugger

Set a breakpoint inside `Loop.tick` in `loopingrules/loop.py`, at the line
`fn(self.world)`. You see one rule called at a time and the world between
calls. Or put `breakpoint()` inside your own rule and run a test with `-s`.

## Reproducing a subtle failure

Because ordering is deterministic (registration order plus `priority`), a
failure reproduces exactly. If it does not, suspect something outside the
world: threads (channels), wall-clock time, or a dict/set you keep by hand.
