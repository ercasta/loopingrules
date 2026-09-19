# Getting started

## Install and run the tests

From the repository root:

```bash
pip install -e ".[dev]"
python -m pytest -q
```

The suite is fast (a few seconds). `pyproject.toml` sets
`pythonpath = ["."]`, so tests can import `examples/` from a checkout
without installing it. `pip install -e .` installs the `loopingrules`
package only. `examples/` is source in this repo and is never installed.

## A first rule

```python
import dataclasses
from loopingrules import Loop
from loopingrules.world import Reply, Said

loop = Loop()

@loop.rule
def greet(w):
    for entity, said in w.each(Said):
        w.destroy(entity)                       # consume the input
        w.spawn(Reply("user", "hi, %s" % said.text))

loop.world.spawn(Said("user", "world"))
result = loop.run()                             # Settled(ticks=2, hot=[])
for entity, reply in loop.world.each(Reply):
    print(reply.text)                           # hi, world
```

What happened:

1. `spawn(Said(...))` put a new entity carrying one component in the world.
2. `run()` called `greet` (tick 1). It found the `Said`, destroyed it and
   spawned a `Reply`.
3. Tick 2 called `greet` again. Nothing matched, so nothing changed, and the
   loop reported the world **settled**.

`Said` and `Reply` are the only two components the package ships for
conversation. Everything else you define yourself.

## Your own components and rules

A component is a plain `@dataclasses.dataclass`. There is no base class.
Prefer `frozen=True`.

```python
import dataclasses
from loopingrules import Loop

@dataclasses.dataclass(frozen=True)
class Order:
    item: str
    qty: int

@dataclasses.dataclass(frozen=True)
class Bulk:                       # a tag: a claim some rule made
    pass

loop = Loop()

@loop.rule
def flag_bulk(w):
    for entity, order in w.each(Order, without=Bulk):
        if order.qty >= 100:
            w.attach(entity, Bulk())

w = loop.world
w.spawn(Order("bolts", 500))
w.spawn(Order("nuts", 3))
loop.run()
print([(e, o.item) for e, o, _ in w.each(Order, Bulk)])   # [(#1, 'bolts')]
```

Note that the rule *derives a fact* (`Bulk`) and attaches it as an ordinary
component. It does not return anything, and no other rule needs to know it
exists. Some other rule can now read `Bulk`. That is the pattern
the whole package is built around.

## Running it interactively

The repo has no runnable app of its own. It is a library, and
[channels](engine.md) live in other packages (`harneskills`) or in your code.
For exploration, the simplest thing is a script like the ones above.
See [Testing and debugging](testing-debugging.md) for stepping through a tick
with a debugger.
