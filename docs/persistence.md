# Persistence and sharing

Two modules, for two different jobs.

| | `save` | `share` |
|---|---|---|
| Job | restore *your own* world after a restart | move a *named subset* into someone else's world |
| Target world | must be **empty** | may already hold anything |
| Ids | preserved exactly | **remapped** to fresh ids |
| Needs field marking | no | yes, `share.ref()` on entity-id fields |

## `save`: the world as JSONL

```python
from loopingrules import save

save.write(world, "world.jsonl")        # to a path
problems = save.read(world2, "world.jsonl")   # into an EMPTY world; [] if fine
```

`dump(world) -> list[dict]` and `load(world, records) -> list[str]` are the
same thing without the file. A missing file is not a problem: `read` treats
it as an empty world, the normal first run.

The format is one JSON object per line. The first is a header, then one
line per component or bare entity:

```
{"version": 2, "next": 1}
{"entity": 1, "type": "mymodule:Order", "fields": {"item": "a", "qty": 1}}
```

Points to know:

- **Ids and the counter are preserved.** Every reference in every component
  is an id, so `#3` must come back as `#3`, and `next` is restored so new
  entities cannot collide.
- **Components are rebuilt without calling `__init__`**, field by field. A
  file saved before a field rename comes back with the fields it had.
- **Unknown classes are skipped and named** in the returned problems, and the
  entity keeps everything else. A state file should survive a refactor.
- **`@transient` components are not saved.**
- A field may hold only what `attach` allows. A tuple is stored as
  `{"$tuple": [...]}`, because JSON cannot tell a tuple from a list.
- `SaveError` is raised on things that should never have reached disk.

## `share`: packs between strangers' worlds

Restoring into an empty world sidesteps two problems that appear as soon as
you merge into a populated one:

**1. Ids must be remapped, so a ref field must be identified.** An entity
reference and an ordinary `int` are the same shape. When a pack is merged,
every entity gets a fresh id, so fields holding a pack entity's id must be
rewritten and fields holding a price must not be. Mark refs explicitly:

```python
import dataclasses
from loopingrules import share

@dataclasses.dataclass(frozen=True)
class Edge:
    src: int = share.ref(default=0)     # an entity id: remapped on import
    cost: int = 0                       # an ordinary number: left alone
```

**2. The file does not get to say what is a ref.** The importer decides using
the class in its own `registry`, not a list read from the pack. A stranger's
file can say which entities exist and what data they carry, but it cannot
redefine which of your component's fields are references.

```python
records = share.dump_pack(src_world, entities)       # entities you name
problems, mapping = share.load_pack(
    target_world, records, {"mymodule:Edge": Edge})   # registry: you build it
# mapping: {pack_id: new_id}
```

Verified behaviour: with two existing entities in the target, a pack whose
entity `#1` was referenced by an `Edge` was imported as ids `3, 4, 5`, and the
`Edge.src` field was rewritten from `1` to `3` while `cost` stayed `5`.

- The registry is `{"module:Qualname": class}`, built by the caller, never
  resolved with `importlib` from the file.
- A type name not in the registry is skipped and named in `problems`.
- `PackError` is raised for malformed packs.

`examples/trip.py` merges three independently authored networks this way.

## `specs`: circuit rules as a pack

`share` moves entities and components. A `circuits` spec is neither: it is a
tree of dataclasses whose leaves include component *classes*
(`Self(RescanWanted, "folder")`), and `attach` refuses a class as a field. So
rules-as-data have their own small serializer.

```python
from loopingrules import specs
data = specs.dump_specs({"rescan": do_rescan_spec})    # JSON-shaped, with a header
problems, loaded = specs.load_specs(data, specs.registry_of(RescanWanted))
rule = circuits.compile_circuit(loaded["rescan"], tools=TOOLS)
```

- Spec shapes are looked up in a fixed catalog by name; a name outside it
  (`__import__`, `ToolRequest`) is refused, never resolved.
- Component classes resolve only through the `registry` you pass, as in
  `share.load_pack`. A spec naming a class you did not register is skipped and
  named in `problems`; the other specs in the pack still load.
- `Const.value` is plain data. A class or a spec node hidden there is refused.
- A `Call` tool name is data, not authority: `compile_circuit(spec, tools=...)`
  still raises `KeyError` for a tool you did not register, and that stays the
  one place that decides what a loaded rule may reach.
- Nesting deeper than `specs.MAX_DEPTH` is refused.

Verified behaviour: `harneskills.examples.automations.do_rescan_spec` comes
back equal from JSON, compiles against that module's `TOOLS`, and is refused
when `RescanWanted` is not in the registry. Every spec in `tests/test_circuits.py`
and `examples/files.py` round-trips equal.
