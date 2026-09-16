"""loopingrules -- an entity-component world, a loop that runs rules over
it, and one thread to run a session on.

    from loopingrules import Engine, Loop, World

* `loopingrules.world` -- entities (identity, no data) and components: plain
  `@dataclasses.dataclass` instances, no base class, holding only
  `None`/`bool`/`int`/`float`/`str` and `list`/`dict`/`tuple` of those --
  another entity is referenced by its plain id, never a live handle. An
  entity may carry SEVERAL components of one type.
* `loopingrules.loop` -- call every rule, in order, until a whole pass changes
  nothing. A rule is a function of one `World` that writes to it directly
  -- `spawn`/`attach`/`replace`/`detach`/`remove`/`destroy` -- and
  `Loop.tick` is the only thing that ever calls one. Registering a rule
  runs `loopingrules.analyze` over it and stays uncalled on any tick where
  none of the component types it reads exist yet; it may also declare
  `priority=` to run ahead of another rule, regardless of which was
  registered first.
* `loopingrules.engine` -- ONE thread that runs the loop, and the channels
  attached to it. `Said(name, "...")` in from whichever channel it
  arrived on; `Reply(user, "...")` out to every channel there is.
* `loopingrules.save` -- the world as JSONL (one record per line), and back.
* `loopingrules.share` -- a NAMED SUBSET of entities and components, portable
  between strangers' worlds -- unlike `save`, which only restores into an
  empty world with every id intact, this remaps ids on import and needs a
  component field marked `share.ref()` to know which of its values are
  another entity's id, not an ordinary number.

That is the whole of `loopingrules`: entities and components, nothing else in this
package's own vocabulary. `harneskills` is the worked door onto it --
`harneskills.repl`, `harneskills.serve` and `harneskills.client` are
channels built on top of `Engine`, and `harneskills.examples.fs` is a
domain built on top of `World` and `Loop` alone -- neither of which this
package knows exists.

There used to be a `loopingrules.facts` here too -- a `fact`/`state`/`deny`
vocabulary for relations-as-components, and `loopingrules.arbitration`/
`loopingrules.request`, two generic readers built on it. Removed rather than
ported once the rewrite above landed: `Relation` subclassed a `Component`
base class this package no longer has, nothing in this repository ever
used any of the three, and the standing argument holds without the code
-- a domain that wants "several values," interning, or a generic
decision needs writes its own components and its own queries, the way
`harneskills.examples.fs` already does. `DECISION_PATTERNS.md` keeps the
design note; see this package's own `README.md`, "Facts/arbitration/
request removed," for the removal itself.
"""

from __future__ import annotations

from . import engine, loop, save, share, world
from .engine import Engine
from .loop import Loop
from .world import World

__version__ = "0.1.0"

__all__ = ["Engine", "Loop", "World", "engine", "loop", "save", "share",
          "world", "__version__"]
