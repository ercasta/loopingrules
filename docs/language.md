# The language: YAML models, contexts, and `lr`

`loopingrules_lang` is a minimal, growable authoring surface over the substrate.
You write **components** and **operations** in YAML, initialise a **context** (the
anchor), and run; the harness installs the operations on the existing `Loop` and
ticks to a fixpoint. YAML lowers to Python **first** (ADR-7's staged execution),
so this is not a throwaway: the same surface folds to an IR core later. There is
**no control network yet** -- the loop fires every eligible operation to a
fixpoint.

This page is the whole of what exists. Two worked models ship in
`loopingrules_lang/models/`: `market` (a fixed set of choose/scope operations) and
`trip` (reads a timetable through the **tool seam**).

## Run it

```
lr run loopingrules_lang/models/market.yaml  loopingrules_lang/models/market.context.yaml
lr run loopingrules_lang/models/trip.yaml    loopingrules_lang/models/trip.context.yaml --json
python -m loopingrules_lang run <model> <context>          # same thing, no install
```

It prints the **applications** (which operation fired, per tick), the settled
world, and any **gaps**:

```
trip: settled in 2 ticks
applied:
  1   trip.load_timetable, trip.choose_cheapest
  2   trip.scope_before, trip.choose_cheapest
world:
  #1    do{what='cheapest', before=480, ...}  tool_request{...}  resolved  tool_answered
  #4    departure{train='R1', ..., depart=390, fare=45.0}  chosen
gaps: (none)
```

## A model

A model is a **name**, its **components** (the declared schema, ADR-10) and its
**operations** (capabilities, ADR-11):

```yaml
model: market
components:
  candidate: {worth: singular, name: singular}
  do: {what: singular, limit: singular, affordable: flag}
  excluded: {}          # a tag
  chosen: {}

operations:
  - name: scope_limit
    when: [{slot: do.limit, op: present}]                # op-level guard (a singleton)
    match: {component: candidate, fields: [worth], without: [excluded]}
    effect:
      - when: [{field: worth, op: gt, value: {slot: do.limit}}]
        mark: excluded

  - name: choose_cheapest
    when: [{slot: do.what, op: eq, value: cheapest}]
    match: {component: candidate, fields: [worth], without: [excluded]}
    reduce: {op: argmin, field: worth}
    effect:
      - clear: {component: chosen, target: losers}
      - mark: {component: chosen, target: winner}
      - mark: {component: resolved, target: {component: do}}
```

An operation is: `when` (op-level, over **singleton** slots -- false ⇒ do
nothing), `match` (`{component, fields?, without?}` -- the entities it iterates),
`reduce` (`argmin`/`argmax` -- the one `winner`), and an ordered `effect` list.
**Every rule reads one concept**, so any *combination* of concepts composes with no
code that names the combination.

### Conditions

`{slot|field, op, value?}`, op one of `present`/`absent`/`eq`/`ne`/`gt`/`ge`/`lt`/
`le`. `slot:` names a **singleton** slot `component.field`; `field:` names a field
of the current match. A **value** is a literal, or `{field: n}`, `{slot: c.f}`, or
`{sub|add|mul|div: [value, value]}`.

### Effects

`set`/`mark`/`unmark`/`add`/`remove`/`spawn`/`destroy`/`clear`/`emit`, each with an
optional `target:` -- `match` (the default), `winner`, `losers`, or
`{component: c}` (the oldest entity carrying it) -- and an optional per-target
`when:`. *(Use `target:`, not `on:`: YAML 1.1 parses a bare `on` key as `True`.)*

## A context

The context is the **anchor** (ADR-8): entities and their components. The
directive is just another entity -- no operation names a use case.

```yaml
entities:
  - candidate: {worth: 5.0, name: goblin}
  - funds: {cash: 30.0, reserve: 10.0}
  - do: {what: cheapest, limit: 20.0}
```

A term no operation defines is a **gap** (`unresolved{name}`), never a guess.

## The tool seam

An operation may `emit` a request; the harness answers it **between ticks** by
calling a registered tool, which **reifies its result into the world** as ordinary
entities and components (ADR-11 §3). Free Python is confined to the tool.

```yaml
  - name: load_timetable
    when: [{slot: do.timetable, op: present}]
    match: {component: do, fields: [timetable], without: [tool_request]}
    effect:
      - emit: {request: train_timetable, args: [{field: timetable}]}
```

`loopingrules_lang.tools` ships `train_timetable`, whose **return schema** is one
**`departure`** per CSV row:

```
train,from,to,depart,arrive,fare
R1,Milano,Roma,06:30,12:00,45

departure{train: str, from: str, to: str, depart: int, arrive: int, fare: number}
```

`depart`/`arrive` are **minutes since midnight** (so a model can compare and
reduce them). A model that reads departures declares the `departure` component --
an undeclared use is a `schema.Gap`, refused at load, not a silent no-op. An
unknown tool, or one that raises, becomes `tool_failed{reason}` (world data, not a
crash).

## What it is not, yet

No control network, no NL edge, no guided UI; contexts are structured YAML, not
text. No references in a context (a `{ref: ...}` form is next). No `session`
subcommand (load once, re-run many contexts) yet. Package name and YAML surface
are provisional.
