# Writing rules

A rule is `def name(w): ...`, registered with `@loop.rule`. This page covers
the idioms that keep a rule set predictable and the mistakes that break it.

## Registering

```python
@loop.rule                          # name: "module.function"
def flag_big(w): ...

@loop.rule(name="flag big")         # explicit name
def _(w): ...

@loop.rule(priority=10)             # runs ahead of priority-0 rules
def watch_first(w): ...
```

- **Names must be unique per loop.** A second rule under a taken name raises
  `ValueError`. The name is how `/rules`, error messages and traces identify
  a rule, so an ambiguous name would make "which rule did this" unanswerable.
  A factory that returns several closures must pass `name=` for each.
- **Order is registration order**, every tick, unless `priority=` says
  otherwise. Higher runs first and ties keep registration order. The same
  input produces the same output in the same order.
- **Use `priority` for real pipelining**, such as "parse before interpret", not
  to silently pick a winner between two rules that disagree. Disagreement
  wants explicit [arbitration](language.md#proposals-and-arbitration).
- `loop.install(fn, *args)` hands the loop to a domain's own installer, which
  registers its rules and seeds its entities.

## The consume pattern

An occasion is an entity that means "this needs handling." The rule that
handles it destroys it, so it fires once:

```python
@loop.rule
def hear_list(w):
    for entity, said in w.each(Said):
        if not said.text.startswith("list"):
            continue
        w.destroy(entity)                    # claimed: nobody else sees it
        w.spawn(ListWanted(said.channel))
```

If no rule claims a `Said`, the engine reports it as `unheard` once the world
settles.

## Derive, don't store: the tag pattern

Compute a boolean fact and attach or detach a tag. Do it in **both
directions** whenever the inputs can change in place:

```python
@loop.rule
def tag_affordable(w):
    for e, listing in w.each(Listing):
        if listing.price <= purse_cash(w):
            w.attach(e, Affordable())
        else:
            w.detach(e, Affordable)
```

Once nothing changes, both branches are no-ops, so `revision` does not
move and the world settles. Guarding with `without=Tag` and computing once
is only safe when the underlying fact can never change under a live entity
id. `examples/cards.py` documents exactly this trap.

## Idempotence is what lets the world settle

A rule that fires every tick forever never lets the loop stop. Ways to
break it:

- Spawning something every tick with no guard (`w.spawn(X())` unconditionally).
- Attaching a *different* value each tick (a timestamp, a counter).
- Mutating a component in place and calling `changed()` each tick.

Ways to be safe: consume the trigger, guard with `without=`, or make the
written value a pure function of the world.

## Never block

A rule runs on the engine's only thread. Do not call `input()`, sleep, or wait
on a network. If a rule needs an answer from a person, spawn a `Reply` asking
and leave a component behind describing the pending state; another rule reads
the answer when it arrives as a `Said`. See `fs.approve` in `harneskills` for
the pattern, and `NeedsApproval` above.

## Errors are contained, not hidden

A rule that raises does not stop the session. The exception is recorded on
`loop.errors` (once per rule and message) and the loop continues. **Whatever
the rule wrote before raising stands.** There is no rollback. The engine
forwards each error to every channel as `{"error": {...}}`.

!!! tip
    Tests should assert `loop.errors == []`. Three of this codebase's own rules
    once called the world in a forbidden way and the suite stayed green because
    nothing checked.

## Keep components literal (so analysis can read your rule)

`Loop.rule` runs [`analyze`](analysis.md) on your function to learn which
component types it reads, and skips the rule on any tick where none of them
exist. That only works if the rule stays inside a small dialect:

- The world parameter is used only as the receiver of `each`, `get`,
  `has`, `first`, `the`, `all`, `spawn`, `attach`, `replace`, `detach`,
  `remove`, `destroy` and friends.
- Component types appear as literal names (`w.each(Order)`), never computed
  (`w.each(getattr(mod, name))`).
- It may call plain functions defined in the same module and pass `w`
  straight through.

If a rule steps outside that, `analyze` raises `Opaque` and the rule is simply
called every tick. That is safe, only slower. It never silently goes dormant.

### A trap the analyzer already handles

A rule that reacts to the *absence* of a type:

```python
@loop.rule
def pong(w):
    if not w.each(Ping):
        w.spawn(Ping())
```

must not be gated on `Ping`, or it would sleep exactly when it needs to
run. `Analysis.negated_reads` records such types (`not`, `is None`,
`== []`, `len(...) == 0`) and the gate excludes them.

## Checklist before you commit a rule

- [ ] Unique, qualified name.
- [ ] Consumes what it handles, or is guarded so it cannot re-fire.
- [ ] Two-directional if it derives a tag from data that changes.
- [ ] Attaches fresh frozen components. Nothing mutated in place.
- [ ] Does not block.
- [ ] Component types are literal.
- [ ] A test settles the loop and asserts `loop.errors == []`.
