"""`files` -- one real capability (`stat`, real disk I/O) reached only
through `loopingrules.circuits.Call`: the worked proof that a rule
authored as DATA -- constructible by something that never gets to run
Python, a YAML loader some day, an LLM today -- can request a
filesystem stat without ever being handed Python to do it in.

Modeled directly on `harneskills.examples.fs_tools.stat`/`_observe`:
the same `fn(w, *data)` shape (a tool takes the live `World` and plain
data, does real I/O, and writes its own conclusion back with an
ordinary `w.replace`/`w.spawn` -- nothing here decides what the write
MEANS, same as `fs_tools.py`'s own module docstring says of itself),
but reached from a *compiled circuit spec* instead of a hand-written
rule's own `import os`. Nothing here imports `harneskills` -- this
package does not know that checkout exists on disk (see `README.md`'s
Scope section) -- `stat`, below, is a small, self-contained restatement
of `fs_tools._observe`'s real half, not an import of it.

## What this proves, and what it deliberately does not

One occasion (`StatRequest`), one tool, one `Call`-bearing
`ActionCircuit`, real I/O against a real temp file in
`tests/test_examples_files.py`. Not a folder listing, not a rename, not
an approval gate -- those would restate the same mechanism against more
surface area, not test anything new about it. See
`loopingrules.circuits`'s own docstring, "`Call`: the one way a spec
reaches outside the World, by name only," for the mechanism this is
proving; this module is the worked example, not the argument.

## The trust boundary this actually draws

`do_stat_spec` never mentions the Python function `stat` at all -- only
the STRING `"stat"`. `install()`, below, is the only place the string
and the real, trusted callable ever meet: once, in the one `tools`
dict passed to BOTH `compile_circuit(do_stat_spec, tools=tools)` (which
only ever checks the name is registered, eagerly, and never calls
`stat` itself any more -- see `loopingrules.circuits`'s own docstring,
"`Call`: a request, deposited, not a tool invoked in place") and
`compile_answerer(tools)` (the rule that actually does). A spec naming
any other tool -- or compiled with no registry at all -- fails at
`compile_circuit`'s own call, before ever touching a `World`; `tests/
test_examples_files.py` pins exactly this. An untrusted spec author (a
person, or an LLM generating `do_stat_spec`-shaped data) can choose to
request a stat, and of which entry -- never choose to run arbitrary
code, and never reach any capability `install()` did not already
choose to register.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from loopingrules import circuits


@dataclass(frozen=True)
class Entry:
    """One file, named by its full path -- deliberately flatter than
    `harneskills.examples.fs.model.Entry` (no `Folder`/`Contents`
    indexing here): this module exists to prove `Call`, not to restate
    the whole `fs` domain."""
    path: str


@dataclass(frozen=True)
class Size:
    bytes: int


@dataclass(frozen=True)
class Modified:
    when: int


@dataclass(frozen=True)
class StatRequest:
    """An occasion: please `stat` this `entry` (a plain entity id)."""
    entry: int


@dataclass(frozen=True)
class Failed:
    """It did not work, and this is what the OS said -- `fs_tools.py`'s
    own `Failed` shape, restated."""
    what: str
    reason: str


# -- the tool: real Python, real I/O, never named by a spec directly ------

def stat(w, entry_id):
    """`fn(w, *data)` -- the exact shape every `Call`-registered tool
    must have, and the exact shape `fs_tools.stat`/`rename`/`ls`
    already use in `harneskills`. `entry_id` is a plain int (`Call`'s
    own docstring: a tool never receives a live `Entity`) -- resolved
    back to the `Entry` it names with an ordinary `w.get`, the ordinary
    way any world method already accepts a bare id.

    Real `os.stat`, not a stand-in: `Size`/`Modified` replace whatever
    was there (`fs_tools._observe`'s own idiom -- `replace`, not
    `attach`, because these are meant to stay singular), or a `Failed`
    is spawned naming the path and what the OS said, and `entry_id`'s
    old `Size`/`Modified` are left standing rather than guessed away.
    Returns whether it worked -- unused by `do_stat_spec` below (the
    action destroys the request either way; the OUTCOME lives in
    whether `Size`/`Failed` shows up, not in a return value nothing
    downstream of a `Call` effect can see), but the same `ok` a
    hand-written caller would want.
    """
    entry = w.get(entry_id, Entry)
    try:
        st = os.stat(entry.path)
    except OSError as e:
        w.spawn(Failed("stat %s" % entry.path, str(e.strerror or e)))
        return False
    w.replace(entry_id, Size(st.st_size), Modified(int(st.st_mtime)))
    return True


# -- the spec: data, never Python, until install() compiles it ------------

do_stat_spec = circuits.ActionCircuit(
    require=(StatRequest,),
    without=(),
    effects=(
        circuits.Call("stat", (circuits.Self(StatRequest, "entry"),)),
        circuits.Destroy(),
    ),
)
"""Claim a `StatRequest`, deposit a `ToolRequest("stat", (entry,))` (`Call`
-- the actual `stat` call happens later, on whichever tick `do_stat_
answers` sees it, not this one), destroy the `StatRequest` -- the same
"claim a fact, destroy it" idiom `loopingrules.circuits`'s three
`reply_*` restatements already use. Destroying the request does not
wait for the stat to run: nothing downstream needs `StatRequest`
itself standing once it is claimed, whether the stat that eventually
runs succeeds or not -- a failed stat is a fact too (`Failed`, spawned
by the tool), not a reason to leave anything standing for something to
retry blindly."""


def install(loop) -> None:
    """Register `do_stat_spec`, compiled against the one real tool this
    module trusts, plus the answerer that is the only place `"stat"`
    and the function `stat` ever actually meet -- see the module
    docstring, "The trust boundary this actually draws," and
    `loopingrules.circuits`'s own docstring, "`Call`: a request,
    deposited, not a tool invoked in place." `do_stat` only ever spawns
    a `ToolRequest`; `do_stat_answers` is the rule that runs `stat`."""
    tools = {"stat": stat}
    loop.rule(circuits.compile_circuit(do_stat_spec, tools=tools), name="do_stat")
    loop.rule(circuits.compile_answerer(tools), name="do_stat_answers")
