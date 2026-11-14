"""`memory` -- the DECLARED tunable surface for `loopingrules.memory`.

The mechanism -- the `memory`/`memory_policy`/`remembered`/`memory_cursor`
shapes and the two rules over them -- lives in the engine
(`loopingrules.memory`), because what it reads is an engine primitive, the
transient change log, and the engine must not import
`loopingrules_calibration`. The DECLARED surface must live where calibration
can see it, so it lives here, on the very same rule functions: `tunable(...)`
mutates and returns the function it is given.

Two knobs, both attributes of the `memory_policy` singleton: `max_entries`
(how much of the trail to keep) and `max_per_target` (how much of it any one
entity may spend). The rules themselves hard-code neither -- they read the
attributes.
"""

from __future__ import annotations

from loopingrules import memory as _memory
from loopingrules_calibration import Knob, tunable

install = _memory.install
REMEMBERED = _memory.REMEMBERED
CURSOR = _memory.CURSOR
POLICY = _memory.POLICY
MEMORY = _memory.MEMORY

remember = tunable(
    Knob("max_entries", 0, 256, steps=9, integer=True),
    Knob("max_per_target", 0, 32, steps=9, integer=True),
)(_memory.remember)

forget = tunable(
    Knob("max_entries", 0, 256, steps=9, integer=True),
    Knob("max_per_target", 0, 32, steps=9, integer=True),
)(_memory.forget)

__all__ = ["CURSOR", "MEMORY", "POLICY", "REMEMBERED", "forget", "install",
           "remember"]
