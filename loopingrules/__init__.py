"""loopingrules -- an entity-ATTRIBUTE world, a loop that runs rules over
it, and one thread to run a session on.

    from loopingrules import Engine, Loop, World

> **Phase S in progress (D8).** The substrate has been re-founded from
> entity + typed *component* to entity + **attribute** (`docs/plan-
> attributes.md`): a value is a scalar, an entity reference, or a flat
> list; a component is a shape an entity carries, tagged with a flag; and
> the whole vocabulary is names. The engine core -- `world`, `analyze`,
> `reflect`, `loop`, `memory`, `save`, `share`, `engine` -- is ported. The
> forge, the scheduler and every `examples/` domain follow.

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
* `loopingrules.loop` -- call every rule, in order, until a whole pass
  changes nothing. A rule is a function of one `World` that writes to it
  directly, and `Loop.tick` is the only thing that ever calls one.
  Registering a rule runs `loopingrules.analyze` over it and stays uncalled
  on any tick where none of the ATTRIBUTE NAMES it reads exist yet.
* `loopingrules.memory` -- SHORT-TERM MEMORY: `remember` promotes selected
  changes out of the transient change log and into ordinary, durable
  entities, and `forget` drops them again past a tuned policy. See
  `docs/plan-memory.md`.
* `loopingrules.reflect` -- REFLECTION: `reify` deposits a card entity per
  rule (its reads/writes, derived by `analyze`), so one rule can read
  another; a control entity is the engine's one CONTROL CHANNEL, read by
  the loop to disable or reprioritise a rule WITHOUT editing it. See
  `docs/plan-reflection.md`.
* `loopingrules.engine` -- ONE thread that runs the loop, and the channels
  attached to it.
* `loopingrules.save` -- the world as JSONL (one entity per line), and back.
* `loopingrules.share` -- a NAMED SUBSET of entities, portable between
  strangers' worlds -- unlike `save`, it remaps ids on import, and needs
  `World.refs` to know which attribute names are references.
"""

from __future__ import annotations

from . import analyze, engine, loop, memory, reflect, save, share, world
from .engine import Engine
from .loop import Loop
from .world import MISSING, Change, Entity, World

__version__ = "0.1.0"

__all__ = ["Change", "Engine", "Entity", "Loop", "MISSING", "World",
           "analyze", "engine", "loop", "memory", "reflect", "save",
           "share", "world", "__version__"]
