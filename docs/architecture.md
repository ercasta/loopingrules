# Architecture

## Module map

```
loopingrules/
  world.py      World, Entity, @transient
  loop.py       Loop: registers rules, ticks them, runs to a fixpoint
  engine.py     Engine: one thread, one queue, N channels; Said/Reply
  save.py       world <-> JSONL, ids preserved, into an empty world
  share.py      pack of entities <-> another world, ids remapped
  analyze.py    what a rule reads/writes, derived from its own AST
```

## Dependencies between modules

```
world  <--  loop  <--  engine
  ^          |            |
  |          v            v
  |       analyze        save
  |
  +--- save, share  (both build on world)
```

- `world.py` depends on nothing but the standard library.
- `loop.py` imports `analyze` (to gate rules) and `World` (as a default).
- `engine.py` imports `save` (for the `get` message) and `Said`/`Reply`.
- `share` is an **optional layer**: nothing in the core imports it, and a
  domain that never moves entities between worlds pays nothing for it.
  (`analyze` is not optional -- `loop.py` imports it to gate rules.)

## What "no domain, no channel, no transport" means

`world`, `loop`, `engine` and `save` ship no rules and no components beyond
`Said` and `Reply`, and know nothing about files, sockets or terminals.

## One tick, step by step

`Loop.tick()` in `loop.py`:

1. Compute the order: rules sorted by `priority` descending, ties in
   registration order.
2. For each rule:
    1. **Gate.** If the rule has a derived read set and
       `world.populated(*reads)` is false, skip it. The body is never
       called.
    2. Record `world.revision`.
    3. Call `fn(world)` inside `try/except`.
    4. If it raised, record `(name, error)` on `loop.errors`, once per
       rule and message, and carry on to the next rule.
    5. If `revision` moved, the rule *fired*.
3. Return the names of the rules that fired.

`Loop.run()` repeats this until a tick fires nothing (`Settled(tick, [])`)
or `budget` ticks pass (`Settled(budget, fired)`). `after_tick` is called
after every tick that changed something.

## One message through the engine

For a line typed on a channel:

```
channel thread            engine thread                       world
--------------            -------------                       -----
post(ch, "say", text) --> inbox.get()
                          spawn(Said(ch.name, text))     -->  #n Said
                          settle():
                            loop.run(after_tick=drain)   -->  rules react
                            drain(): Reply -> channels
                            "settled" -> everyone
                            on_settle(loop)  (e.g. save)
```

Channels are threads that never touch the world. They only `post()` to a
queue. The engine's single thread is the only thing that ever calls a rule,
so there is **no lock around the world** and a tick means the same thing on
every channel.

The consequence to remember: **no rule may block.** A rule that stopped to
wait for input would stop the world for every channel. A rule that needs a
person's answer spawns a `Reply` asking and finishes. The suspended state is
a component sitting in the world, and another rule picks it up when the
answer arrives.

## Key design decisions, and where they are argued

| Decision | Where |
|---|---|
| Rules write directly, not by returning a change list | `loop.py` module docstring |
| Registration order (or `priority=`), not scoring | `loop.py`, "Order is registration order" |
| Dormancy gate derived from the AST, not declared | `loop.py` and `analyze.py` |
| The budget is a circuit breaker, not a proof of termination | `loop.py`, "The budget" |
| Small closed vocabulary, conclusions re-enter as ordinary components | `PRINCIPLES.md` |
| Abstention must be structural | `PRINCIPLES.md`, "To guard it" |
