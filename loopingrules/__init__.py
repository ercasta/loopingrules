"""loopingrules -- an entity-ATTRIBUTE world, a loop that runs rules over
it, and one thread to run a session on.

    from loopingrules import Engine, Loop, World

> **Phase S in progress (D8).** The substrate is being re-founded from
> entity + typed *component* to entity + **attribute** (`docs/plan-
> attributes.md`): a value is a scalar, an entity reference, or a flat
> list; a component is a shape a reference targets, not a class; and the
> whole vocabulary is names. `world.py` is ported (the seam); `analyze`,
> `loop`, `save`/`share`, `reflect`/IR, the forge, the scheduler and
> every example follow in that order. Until they land, this package
> exports only the seam and the modules above it are still the old
> component engine on disk, not re-exported here.

* `loopingrules.world` -- entities (identity, no data) and **attributes**:
  a `(name, value)` slot, at most one per name per entity, whose value is
  a scalar (`None`/`bool`/`int`/`float`/`str`), another entity (stored as
  its plain int id), or a **flat list** of those -- no dict, no tuple, no
  nesting. The verbs are `set`/`unset` (singular), `add`/`remove` (a
  deduped set), `append`/`pop` (an ordered sequence) and `mark`/`unmark`
  (a flag); the declared KINDS live in the JSON schema, not here. Every
  write also lands in a transient, in-memory change log
  (`World.changes`), which a rule may read to condition on what has
  HAPPENED, not only on what is true now -- see `docs/plan-memory.md`; it
  is never saved.

The rest of the package, once ported, keeps its shape: `loop` calls every
rule until nothing changes; `engine` runs one thread with channels;
`save`/`share` persist a world; `memory`/`reflect` promote the change log
and reify rules; `patterns`/`calibration` are the author workflow.
"""

from __future__ import annotations

from . import world
from .world import MISSING, Change, Entity, World

__version__ = "0.1.0"

__all__ = ["Change", "Entity", "MISSING", "World", "world", "__version__"]
