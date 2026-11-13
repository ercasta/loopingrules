# D8 — The attribute substrate: entities, attributes, and references

Status: **design / to perform.** The built engine is `entity + component`: an
entity is a handle with no data, a component is a typed `@dataclass` an entity
may carry many of, and every layer above keys on the component **type**
(`analyze`, `reflect.RuleCard`, the forge IR, the scheduler, `save`, the
calibration kit). This doc records a substrate **simplification** settled in
discussion. Both halves are settled: the **representation** (below) and the
**migration** (a clean break, no classes, in its own section).

## The problem, stated once

The substrate uses two kinds of machinery where one will do. A "component"
gives a bundle of fields an identity, a name and a lifetime; a "value" carries
data; and "many of a kind" is a second mechanism (a type carried repeatedly)
next to "a list". All of it is named by a **Python class** the analysis, the
catalog and the IR must walk. The proposal is one concept — the **attribute** —
whose value may be a scalar, a **reference**, or a **list**; whose multi-field
structure is **not a value at all but an entity**; and whose whole vocabulary
is **names**, so nothing needs a class.

The second motive is homoiconicity (locked decision 13, D7). If the world's
unit is `name -> value`, a rule is naturally an entity whose attributes
*describe it* — its `reads`, its `writes`, its `lhs`, its `rhs` — instead of a
Python function a bespoke introspector must decode.

## The shape

### Entity and attribute

An entity is unchanged: identity with no data, `#7`, ids counting up, handles
comparing by id. An **attribute** is a `(name, value)` slot on an entity, and
there is **at most one slot per name per entity** — multiplicity lives *inside*
the value. That single decision deletes today's cross product in `each()` and
the `get`/`get_all` ambiguity.

The **name carries the semantics** the component *type* carried today. This
preserves `PRINCIPLES.md`'s invariant **"values are primitives only — there is
no semantic value-type layer"**: meaning is in the name, never in a type
attached to the value.

### Value: a scalar, a ref, or a flat list

| Value | Meaning |
|---|---|
| `None` / `bool` / `int` / `float` / `str` | a scalar |
| another entity | stored as its plain `int` id, exactly as `world._lower` does today — a **reference** |
| a **flat list** of the above | the multi-valued or ordered case |

**No dict, no record value, no nesting.** Whatever looks like a structured
value is a **reference to an entity**, not a value.

### A component is an entity

There are **only entities and attributes**. A "component" is not a class and
not a slot; it is the schema's name for a **shape** — an attribute set — that a
**reference** targets. Every component is realized as an **entity**, and a
holder links to it with an attribute named for the component:

```
file.size  ->  #20            #20.bytes = 17      (a Size)
file.entry ->  #21            #21.folder = #1, #21.name = "a.txt"   (an Entry)
file.tags  = [ #22, #23 ]     #22.name = "urgent" (a set of refs)
```

Even a **one-field** component is an entity: "size is an entity having a single
attribute, `bytes`." Nothing needs a Python class — a component is *names*.

There is exactly **one exception**: a **tag** (a fieldless component,
`Stale()`, `NeedsApproval()`) stays a **flag** on the holder. It has no data,
so it needs no entity.

This is the `id-attr-value` shape `comparison-soar.md` already maps onto the
substrate, and it *strengthens* "values are primitives only": there is now no
structured value at all — structure is **entities referencing entities**.

### Three kinds, plus a flag

| Kind | Holds | Write verbs | Settles? |
|---|---|---|---|
| **singular** | exactly one value | `set` / `unset` | re-set an equal value = no change |
| **set** | deduped by value, **insertion-ordered** | `add` / `remove` | `add` an equal value = no change |
| **sequence** | **ordered, duplicates kept** | `append` / `pop` | every `append` changes |
| **flag** | a unit marker (no payload) | `mark` / `unmark` | re-`mark` = no change |

A **flag is not a fourth kind in the data**: it is a *singular whose value is a
unit marker*, present or absent, and `has` means the slot is present. It is
spelled out here because tags are the idiom for state and deserve their own
verbs.

The **set** kind is deduped and insertion-ordered so iteration is deterministic
and settling stays reproducible — today's `attach` behavior, exactly. A
**sequence** is the one deliberately non-idempotent kind, and **keeping it from
looping forever is the author's declared responsibility**: the budget stays the
backstop, and a non-settling sequence is a `hot` loop, a named failure that a
scorer already penalises.

### The schema is a JSON artifact

The declared schema (names, kinds, ref-ness) and the derived use (the read/write
graph `analyze` observes) are the two halves the repo already separates, now
over names — and the declared half lives in **JSON**:

- **JSON schema** (declared, the forge owns and emits, the engine loads): the
  **shapes** (a named attribute set) and the **attributes** (name, kind, whether
  its value is scalar or a **ref**, and — for a ref — the **shape** it targets).
- **Derived** the read/write graph `analyze` computes over the names, recomputed
  whenever rules change.
- **Checked against each other**: a name **used but not declared** is a
  **blocking gap** (the forge's own discipline — the build does not proceed on an
  undeclared name, the same as an unmapped clause); a declared name never used,
  or a use that disagrees with the kind, is reported, never merged.

JSON is the same shape the forge IR already targets: portable, diffable, and
emitted without a Python class anywhere.

### Reads, writes, and the gate

`analyze` keeps its posture — reads and writes **derived** from the rule's own
AST, never declared — but the unit is a **string-literal attribute name**
(`w.get(e, "card")`), not a class. The dormancy gate is the same
over-approximation as today: `populated(*names)` becomes "at least one read
attribute is present," and `RuleCard.reads`/`writes`, `reflect`'s hashing and
the change log's `changed=` filter all name attributes.

Writes are the verbs above plus `spawn`/`destroy`. Idempotence still decides
settling: a write that changes nothing moves no revision.

### Reading across refs: own attributes join, refs are walked

An entity's **own** attributes are co-located, so an attribute join survives:
`each("card", "price")` yields the entities carrying both — one row per entity,
no cross product. To cross a **reference** you walk it explicitly: read the ref
(or list of refs), then `get(ref, "bytes")`. There is **no implicit traversal
join**, which keeps `analyze` total and the gate cheap.

### Refs and lifetime

**Ref-ness and the target shape are declared** in the JSON schema, and
`share`/`save`/the graph read that declaration — the need `plan-forge.md` names
("the engine lowers entity handles to plain ints, so the reference type is
lost"). There is **no ownership**: destroying a holder leaves the entities it
referenced, and a ref may **dangle** — a plain int pointing at nothing, exactly
as today's int refs already may. Cleanup is explicit.

## The migration: a clean break, no classes

This is a **re-founding**, and it is done as a **clean break**: a new core, the
old component engine **retired** once the suite is green on the new one — not a
compatibility layer accepting both shapes. Nothing keeps a `@dataclass`; a
domain defines **names**, and its components are entities it spawns and links.

The mapping from today's components, one rule:

- **fieldless** (`Stale()`) → a **flag** on the holder;
- **any fields** (`Size(bytes=17)`, `Entry(folder, name)`) → the named
  **shape**, realized as an **entity** the holder references through an
  attribute named for the component (singular for one, `set` for many).

The order (`plan-forge.md`'s "prove the seam below before building above"):

1. **`world.py`** — entity store, attribute slots by name, the kinds, refs, the
   change log. The old component engine is removed here; this is the seam.
2. **`analyze.py`** — the same AST walk, retargeted onto string-literal
   attribute names; a use that is not in the JSON schema is a blocking gap.
3. **`save`/`share`** — JSONL of entities and their slots, refs as ids kept by
   the declaration; `share` remaps the declared refs.
4. **`reflect`/IR**, then the **forge**, then the **scheduler** — each already
   names by a hash and a read/write set, so the retarget is mechanical but not
   free.
5. **`calibration`/`patterns`/`islands`/`examples`** — last, because they are
   the proof the substrate still runs real domains; every example is rewritten
   to spawn entities and set names.

## What this changes, layer by layer

| Layer | Today | Under attributes |
|---|---|---|
| `world.py` | entities + typed components, `attach`/`replace`/`detach`/`remove` | entities + name slots, `set`/`add`/`append`/`mark`/`remove`/`unset` |
| `analyze.py` | reads/writes over component classes | reads/writes over name literals; undeclared = blocking gap |
| change log | `payload` holds component instances | `payload` holds attribute deltas `(name, old, new)` |
| queries | `each(types)` cross-products repeated types | `each(names)`, one row per entity; refs walked explicitly |
| `save`/`share` | JSONL of components, ids preserved | JSONL of name slots; refs as ids, kept by the JSON schema |
| `reflect` / `RuleCard` | hash, reads/writes as class names | hash, reads/writes as attribute names |
| forge IR | component specs + rule productions | the **JSON schema** (shapes/attributes) + rule productions |
| scheduler | activations `(rule, binding)` over components | activations over attribute values |
| calibration | `signature` over component state | `signature` over attribute state |
| `memory`, `patterns`, `islands` | `Remembered`, `Risk`, `Item` as components | a flag, or a shape realized as an entity |
| `examples/` | every domain | every domain, rewritten without classes |

## Why simpler, and what it costs

Simpler: one concept (attribute) replaces two (component, and "many of a type");
a list is the multi case with no second mechanism; **a component is just an
entity**, so there is no separate shape machinery and **no Python class
anywhere**; a rule is an entity with attributes, so nothing has to *translate*
rules into data (locked 13). No dicts in values, no cross product, no
`get`/`get_all` split.

The costs, named rather than hidden:

- **Indirection.** Every component is now a referenced entity, so a read like
  "the file's size in bytes" is a ref-walk (`file.size` then `bytes`), and the
  entity count grows — a record is an entity, and so is a one-field `Size`.
- **The JSON schema is a first-class artifact** the forge emits, the engine
  loads and `lint`/the gates check. The component set has not vanished; it has
  become a JSON vocabulary of names, shapes and refs.
- **The built layers migrate**, and until they do the docs disagree: this doc
  says attribute, `concepts.md`/`architecture.md`/`README.md` say component.
  Expected while the change is *to perform*; it must not be half-applied.
- **Lifetime is the author's**, since refs do not die with their holder.

## What this does not settle

- **Naming convention** — whether the link attribute and the shape share a name
  (`size`/`Size`), and the plural convention for a `set` of refs (`entries`).
- **The verb set in detail** — whether `set` on a `set`/`sequence` replaces the
  whole collection, and a `clear` distinct from `unset`.
- **How a component-entity is built** — a schema-driven helper that spawns the
  shape's entity and links it (`w.add(e, "size", bytes=17)`), or plain
  `spawn` + `set` by hand.
- **Cycles** — a ref graph may cycle; `save` and any traversal must handle it.
- **Schema versioning** — how a JSON schema version is frozen and rolled back
  (the forge's `Frozen`, now over the JSON artifact).
- **Anonymous scalar attributes** — whether a rule may set a scalar name that
  belongs to no shape (a scratch value), or every name is declared.
- **The query API** — the exact spelling of `each`/`get` over names and of an
  explicit ref walk.

## Open questions

1. Does the link attribute share the shape's name, and is a set of refs named by
   a plural convention or declared?
2. Is a schema-driven constructor (`w.add(e, "size", …)`) the idiom, or `spawn`
   plus `set`?
3. Does `set` on a `set`/`sequence` replace the collection; is there a `clear`?
4. How are **cycles** in the ref graph handled by `save` and `share`?
5. How is the JSON schema **versioned** and frozen, and does `share` carry it?
6. May a rule set an **anonymous** scalar name (no shape), or is every name in
   the JSON schema?
