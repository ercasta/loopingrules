"""`memory` -- the DECLARED tunable surface for `loopingrules.memory`.

The mechanism -- `Memory` / `Remembered` / `MemoryPolicy` / `MemoryCursor`
and the two rules over them -- lives in the engine (`loopingrules.memory`),
because what it reads is an engine primitive, the transient change log, and
the engine must not import `loopingrules_calibration`. The DECLARED surface
must live where calibration can see it, so it lives here, on the very same
rule functions: `tunable(...)` mutates and returns the function it is given,
so `remember`/`forget` below ARE `loopingrules.memory.remember`/`forget`,
now carrying the knobs `knobs(loop)` collects and `lint` holds them to.

Importing this module is what attaches the surface. A domain that installs
memory through `loopingrules_patterns.memory.install` (or imports this
module at all) gets it; one that imports only `loopingrules.memory` gets the
rules with no declared knobs -- correct, still reading `MemoryPolicy`, just
not advertised to a calibration run.

Two knobs, both fields of the `MemoryPolicy` singleton:
`max_entries` (how much of the trail to keep) and `max_per_target` (how much
of it any one entity may spend). The rules themselves hard-code neither --
they read the component -- which is exactly what the linter would otherwise
flag.
"""

from __future__ import annotations

from loopingrules import memory as _memory
from loopingrules_calibration import Knob, tunable

Memory = _memory.Memory
MemoryPolicy = _memory.MemoryPolicy
Remembered = _memory.Remembered
install = _memory.install

remember = tunable(
    Knob(MemoryPolicy, "max_entries", 0, 256, steps=9, integer=True),
    Knob(MemoryPolicy, "max_per_target", 0, 32, steps=9, integer=True),
)(_memory.remember)

forget = tunable(
    Knob(MemoryPolicy, "max_entries", 0, 256, steps=9, integer=True),
    Knob(MemoryPolicy, "max_per_target", 0, 32, steps=9, integer=True),
)(_memory.forget)

__all__ = ["Memory", "MemoryPolicy", "Remembered", "forget", "install",
           "remember"]
