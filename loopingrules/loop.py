"""The game loop: call every rule, over and over, until nothing changes.

A rule is a Python function of one argument, the `World`. It QUERIES
the world -- `each`, `get`, `has`, `first`, `the` -- and it WRITES to it
directly -- `spawn`, `attach`, `replace`, `detach`, `remove`, `destroy` --
the same four-turned-six verbs `install()` already calls outside any
rule's turn::

    @loop.rule
    def list_dir(w):
        for entity, want in w.each(ListWanted):
            w.destroy(entity)
            fs_tools.ls(w, want.folder)

`tick()` calls every registered rule once, in tick order (see `priority`,
below), and a rule's own writes are visible to the world -- and so to the
next rule in the SAME tick -- the instant it makes them, because there is
nothing in between: no list of changes to build, nothing later that
applies it. `run()` ticks until a whole pass changes nothing -- the world
has SETTLED -- and that is the moment the REPL gets its prompt back.

## Why a rule may touch the world directly

A rule is already a plain function of one `World`, called once per tick
in a known order, by the one place (`Loop.tick`) that ever calls it --
nothing about reasoning over what it does needs its writes described
rather than made: `world.revision` before and after the call already
says whether it fired (see below), the same as it would if the writes
arrived by way of a returned list first. Handing back a description of a
change instead of making it bought exactly one thing -- a rule that
FORGOT the contract and touched the world anyway could be caught, named,
and refused -- and it cost real weight for that one guarantee: a second
vocabulary for the four things `World` already does, and a `Pending`
placeholder standing in for an entity `spawn()` had not made "real" yet
even though nothing was stopping it from being real immediately. That
guarantee also stopped holding well before this note did: three of this
harness's own rules called `w.spawn`/`w.destroy` directly for a while
before anyone noticed, and the suite stayed green throughout, because
nothing asserted `loop.errors == []`. A rule that wants to defer or hold
something (a proposed rename, say) still can -- the same way `fs.py`
already does it, as a component sitting in the world (`RenameWish` +
`NeedsApproval`) for another rule to query, approve, or leave alone. That
is what "proposed" means here now; it never needed a second, lower-level
notion of "not yet real" underneath every ordinary write too.

## Order is registration order, unless a rule says otherwise

By default there is no ranking, no attention, no scoring of which rule
most deserves a turn: rules run in the order they were installed, every
tick, and a rule whose query is empty does nothing and costs a dict
lookup. This is a deliberately small idea, and it buys the thing it is
hardest to buy otherwise: the same input produces the same output, in the
same order, every time. If a listing should be reported entry-by-entry and
then counted, register the entry rule before the count rule and it is so.

`loop.rule(fn, priority=N)` is the one deliberate override: HIGHER runs
FIRST, ties (including the default, `0`, when nobody sets one) keep
registration order. This is what settles the case registration order
cannot express on its own -- two rules reading the SAME component
type, installed by two domains that do not know about each other and so
cannot agree on which one to register first. Declared once, by whichever
rule actually needs to run before the other, it is a property of the
RULE rather than an accident of install order.

⚠ Priority is a total order over every rule, not a per-type one -- two
rules that watch entirely disjoint types are still ordered by it. That
is not a hazard: only a shared type ever makes the relative order of two
rules OBSERVABLE (each rule in its own tick still ends up doing what
its own query finds, regardless of who ran first, unless they touch the
same entities), so widening the ordering as a matter of policy costs
nothing a domain could actually notice going wrong, and it is far simpler
than the alternative -- an ordering that is only PARTIALLY defined, so
that a rule newly given a shared type with another discovers the tie is
suddenly broken by installation order it never chose.

A rule may also be controlled at RUNTIME, without being edited: a controller
attaches a `reflect.RuleControl` naming a rule by its hash, and `_tick_order`
reads it at the top of each tick to skip or reprioritise that rule. That is
the one control channel above the shared `World`; it is opt-in (no control
exists until a rule writes one) and it may only SUBTRACT or REORDER, never
manufacture a firing -- `analyze`'s gate still decides dormancy. See
`loopingrules.reflect`.

`Loop(schedule=True)` moves that channel into the recognize-act cycle
(`docs/plan-scheduler.md`, probe `q0`). Controller rules -- those registered
`controller=True` -- run first, the order is recomputed so their writes land
THIS tick, and then ONE eligible rule fires. It is opt-in and rule-level: the
engine cannot see a rule's BINDINGS, which is exactly the IR-native question
`docs/plan-scheduler.md` leaves open, so this is the rule-level half of the
scheduler, not the activation-level one. The default loop is unchanged.

## A rule fires by CHANGING something

The loop cannot see inside a rule and does not try. It reads
`world.revision` before and after calling it -- a rule that spawned an
entity, destroyed one, or attached a component that was not already
there, fired; a rule that re-attached a component equal to the one
already on the entity did not. That is what settling is measured in, and
it is why `World.attach` comparing before it stores is load-bearing
rather than a convenience.

## Every change is logged, and a rule may read the log

The same write methods also append to a transient CHANGE LOG
(`World.changes` / `World.recent`): what changed, on which tick, and by
which rule. This is not `revision`-watching for the loop -- it is for a
RULE that needs to condition on what has already HAPPENED, not only on
what is true now (see `docs/plan-memory.md`). `tick()` stamps each record
with the running rule (`world._actor`) and the tick (`world._tick`), so a
rule calling `w.changes()` sees only changes from BEFORE the current tick
and cannot react to its own write and loop. The log is in-memory and never
saved; `Loop(capacity=N)` bounds it. It is what the removed
`World.tracing` was reaching for, now first-class rather than a debug
trace.

## A rule wakes only when something it reads exists

There used to be a `loop.rule(fn, watches=(Kind, ...))` a rule author
declared by hand -- what could gate a rule instead is exactly what
`loopingrules.analyze.analyze()` already derives from its own source,
soundly, so `Loop.rule` now calls `analyze(fn)` itself at registration
time rather than asking anyone to say it twice. A rule whose reads
resolve cleanly is skipped -- its Python body never called at all -- on
any tick where `world.populated(*reads)` is false, i.e. NOTHING carries
any type it reads yet. A rule `analyze()` cannot resolve (raises
`analyze.Opaque` -- an aliased world parameter, a call into an unrelated
module, anything outside the dialect its own docstring names) or that
resolves with NO reads at all (nothing to gate on, a timer-shaped rule
that ignores its `World` parameter entirely) is called every tick, no
questions asked -- the same fallback the old `watches=None` default was,
reached automatically instead of chosen.

This closes the gap the hand-written version always carried and named
honestly rather than fixed (`PRINCIPLES.md`: "declare `watches` too
narrow... there is no way to catch this from here"): `analyze()`'s own
reads ARE the exact set a rule's body can possibly act on, not a
person's guess at a safe superset, so there is no longer a way to name
one too narrow -- gating a rule wrong now takes rewriting its body
outside the analyzable dialect, which is exactly the case that already
falls back to "called every tick" rather than going silently dormant.

⚠ One genuine trap survived the switch, found by a rule reacting to a
type's ABSENCE (`tests/test_engine.py`'s `pong`: `if not w.each(Ping):
w.spawn(Ping())`) rather than its presence -- gating that on `Ping`
would skip it exactly when `Ping` is gone, which is precisely when it
needs to run. `analyze.Analysis.negated_reads` is the fix: a type a
rule's own source tests for absence (`not`, `is None`, `== []`, `len(
...) == 0`) never contributes to the gate, even where the SAME type is
also read positively elsewhere in the same rule -- see its own
docstring for why that exclusion is global rather than per-occurrence.

⚠ A rule is one entry in `self.rules` and `tick()` visits each entry
exactly once, so reading several types is never a reason to be called
more than once in the same tick -- there is no per-type dispatch loop
here to accidentally invoke a rule twice for two types that both
happen to be populated. "Read three types, run once" is not a rule this
module enforces; it is a rule this module's SHAPE makes impossible to
break.

## The budget is the circuit breaker

Two rules can feed each other forever -- one spawns what the other
destroys, which spawns what the first destroys. Nothing detects that in general, so the
loop counts ticks and stops at `budget`, handing back the rules that were
still firing when it ran out. The REPL prints them. A settled run reports
no hot rules, and that is how a caller tells the two apart.

## A rule that raises does not take the session with it

The exception is caught, recorded on `loop.errors` (once per rule and
message, however many ticks it raises on), and the loop goes on to the
next rule. Whatever the rule already wrote before it raised stands --
there is nothing to roll back to, the same as any ordinary function that
mutates something and then throws -- but the world still settles, and the
person at the prompt gets both their prompt and the traceback's message,
which is better than a REPL that dies on a typo in a domain nobody is
editing right now.

## A rule's own name

Every rule registered on a loop answers to a name, unique on THAT loop --
given (`name=`) or inferred (`module.function`), `rule()` raises rather
than let a second registration answer to a name already taken. This was
always the convention every rule this harness's own domains register
already followed by hand (`"effects.%s" % name`, one per closure a
factory hands back); now the engine holds it, for a tidy `/rules` listing
and to avoid ambiguity if two rules were to share a name.
"""

from __future__ import annotations

import collections

from . import analyze
from .reflect import control_map, identity, rule_name

Settled = collections.namedtuple("Settled", "ticks hot")


def _name_of(fn) -> str:
    """`fs.flag_big` -- the module a rule came from, then the function.

    Qualified because two domains installed at once will both have one
    called `hear`, and `/rules` listing it twice, or an error naming one
    of them, would send you to the wrong file.

    Delegates to `reflect.rule_name`, which is the SAME name a `RuleCard`
    carries and a `Remembered.rule` records -- one definition, so a
    controller matching a card against the change log cannot drift from
    registration.
    """
    return rule_name(fn)


class Loop:
    """Rules, in order, over one world."""

    def __init__(self, world=None, budget: int = 200, capacity=None,
                 schedule: bool = False) -> None:
        from .world import World
        self.world = World() if world is None else world
        self.budget = budget
        # The opt-in recognize-act cycle (see the module note, "Resolve within
        # the tick"). False is today's loop, unchanged: every rule, in order,
        # recomputed once at the top. True runs controller rules first, then
        # ONE eligible rule: the scheduler the q0 probe proved, moved into the
        # engine -- rule-level, because the engine cannot see a rule's bindings
        # (`docs/plan-scheduler.md`: activation-level needs IR-native rules).
        self.schedule = schedule
        self.rules: "list[tuple[str, object]]" = []
        # (rule name, exception) for everything that blew up in the last
        # `run`. The caller drains it; the loop only ever appends.
        self.errors: "list[tuple[str, BaseException]]" = []
        self.tick_count = 0
        # The change log itself is the World's (see `world.py`); the loop
        # owns only its bound and the provenance it stamps on each record:
        # `_tick` (the current tick) and `_actor` (the rule running now, or
        # None). `capacity` is the optional retention bound -- older
        # changes are dropped past it; None keeps the whole session.
        self.world._log_capacity = capacity
        self.world._actor = None

    # -- registering --------------------------------------------------

    def rule(self, fn=None, *, name=None, priority=0, controller=False):
        """Register a rule. Bare or called::

            @loop.rule
            def flag_big(w): ...          # -> "fs.flag_big"

            @loop.rule(name="flag big")
            def _(w): ...

            @loop.rule(priority=10)
            def watch_first(w): ...       # ahead of any priority-0 rule
                                           # reading the same type, whoever
                                           # installed it

        `priority` orders the tick -- higher runs first, ties (the
        default, `0`, included) keep registration order -- see the module
        note on why this is a total order rather than a per-type one.

        There is no `watches=` to pass any more -- see the module note,
        "A rule wakes only when something it reads exists": `analyze(fn)`
        is called right here, and its reads (if any resolve) become the
        gate `tick()` checks, in place of what a person used to have to
        declare and could get wrong.

        The name -- `name` if given, `module.function` (see `_name_of`)
        otherwise -- must be unique on THIS loop: registering a second
        rule under a name already taken raises `ValueError` rather than
        silently shadowing the first entry in `self.rules`. This is not
        new ceremony most call sites will ever feel -- every rule this
        harness's own domains register already spells a qualified name
        for exactly this reason (`"effects.%s" % name`, one per closure a
        factory returns, would otherwise all answer to the SAME inferred
        `effects.make`) -- it is the engine finally checking a
        convention that used to only be a habit. It matters more now
        than it used to: a rule's identity is also the key `tracing`
        traces BY (see `tick()`), and two rules answering to one name
        would make that trajectory ambiguous, not just `/rules`' listing.
        """
        if fn is None:
            return lambda f: self.rule(f, name=name, priority=priority,
                                       controller=controller)
        try:
            analysis = analyze.analyze(fn)
            reads = analysis.reads - analysis.negated_reads
        except analyze.Opaque:
            reads = None
        if reads:
            fn._loopingrules_watches = tuple(reads)
        fn._loopingrules_priority = priority
        # A controller runs in the CONTROL PHASE of a `schedule=True` tick, so
        # its `RuleControl` writes are read by the order the act phase uses --
        # i.e. control lands THIS tick, not the next. Opt-in, and meaningless
        # under the default loop (see the module note).
        fn._loopingrules_controller = controller
        # The rule's identity for `reflect.RuleControl` -- a content hash, so
        # a controller can name this rule without holding a reference to a
        # function `World` could never store. A generator may have stamped an
        # IR-datum hash on `fn` already; `identity` prefers it over the source
        # hash, so a generated rule is named by its structure. See
        # `loopingrules.reflect` and `loopingrules_forge.evolve`.
        fn._loopingrules_hash = identity(fn)
        rule_name = name or _name_of(fn)
        if any(existing == rule_name for existing, _ in self.rules):
            raise ValueError(
                "a rule named %r is already registered on this loop -- "
                "give this one its own name=" % rule_name)
        self.rules.append((rule_name, fn))
        return fn

    def install(self, fn, *args, **kwargs):
        """Hand this loop to a domain's own installer -- `install(loop)` --
        which is expected to register its rules and seed its facts. The one
        thing `harneskills.config` names, and the only shape of a domain
        this harness knows."""
        return fn(self, *args, **kwargs)

    # -- running ------------------------------------------------------

    def _record(self, name: str, error: BaseException) -> None:
        # Once per settle, not once per tick: a rule that raises (or
        # keeps failing the same way) raises again on every pass until
        # the world stops moving, and one typed line should not print the
        # same traceback message four times.
        if not any(n == name and str(seen) == str(error)
                   for n, seen in self.errors):
            self.errors.append((name, error))

    def _tick_order(self) -> "list[int]":
        """Indices into `self.rules`, in the order THIS tick calls
        them: `priority` descending, registration index ascending on a
        tie -- `self.rules` itself stays in registration order (what
        `/rules` and every direct reader of it expects), this is purely
        `tick()`'s own execution order, recomputed fresh so a rule
        registered after the loop has already ticked once takes its
        declared priority into account immediately, not from whenever it
        happened to be appended.

        `reflect.control_map` is read here, at the top of the tick: a rule
        whose hash carries `enabled=False` is dropped from the order and
        never called, and a control's `priority` overrides the rule's own.
        A control written DURING this tick therefore takes effect on the
        NEXT -- the same one-tick lag `World.changes` gives a rule reading
        history, and it settles for the same reason: a controller that keeps
        re-emitting an equal control moves nothing and the world stops.
        """
        controls = control_map(self.world)
        order = []
        for i, (_name, fn) in enumerate(self.rules):
            found = controls.get(getattr(fn, "_loopingrules_hash", None))
            if found is not None and not found[0]:
                continue
            order.append(i)

        def key(i):
            fn = self.rules[i][1]
            found = controls.get(getattr(fn, "_loopingrules_hash", None))
            if found is not None:
                return (-found[1], i)
            return (-getattr(fn, "_loopingrules_priority", 0), i)

        return sorted(order, key=key)

    def _fire(self, i: int, fired: "list[str]") -> bool:
        """Call rule `i` exactly as `tick` always has: skip it if its derived
        gate is closed, catch and record a raise, and append to `fired` iff it
        moved `revision`. Returns whether it fired."""
        name, fn = self.rules[i]
        watches = getattr(fn, "_loopingrules_watches", None)
        if watches is not None and not self.world.populated(*watches):
            return False    # dormant -- not even called, see the module note
        before = self.world.revision
        raised = None
        self.world._actor = name
        try:
            fn(self.world)
        except Exception as e:  # noqa: BLE001 -- see the module docstring
            raised = e
        finally:
            self.world._actor = None
        if raised is not None:
            self._record(name, raised)
            return False
        if self.world.revision != before:
            fired.append(name)
            return True
        return False

    def tick(self) -> "list[str]":
        """One pass over every rule, in tick order: call it, done. Returns
        the names of the ones that changed something, in the order they
        ran.

        Under `schedule=True` the pass is the recognize-act cycle instead:
        controller rules run first (the control phase), the order is
        recomputed so their `RuleControl` lands THIS tick, then exactly ONE
        eligible rule fires (the act phase) -- the world re-settles around it
        and the cycle repeats. With no controller and one eligible rule the
        two coincide, which is why the schedule is a conservative extension:
        `schedule=False` (the default) is the loop above, byte for byte.
        """
        self.tick_count += 1
        self.world._tick = self.tick_count
        fired: "list[str]" = []
        if not self.schedule:
            for i in self._tick_order():
                self._fire(i, fired)
            return fired
        ran = set()
        for i in self._tick_order():
            if getattr(self.rules[i][1], "_loopingrules_controller", False):
                self._fire(i, fired)
                ran.add(i)
        for i in self._tick_order():        # recomputed: control lands THIS tick
            if i in ran or getattr(self.rules[i][1], "_loopingrules_controller",
                                   False):
                continue
            if self._fire(i, fired):
                break                       # ONE rule (that fires) per tick
        return fired

    def run(self, budget=None, after_tick=None) -> Settled:
        """Tick until a whole pass changes nothing.

        `Settled(ticks, hot)`: `hot` is empty on a clean settle, and holds
        the rules still firing if the budget ran out first.

        `after_tick()` is called after every tick that changed something,
        and it is not decoration: a rule may BLOCK -- ask a person to
        approve something, wait on a network -- and everything the world
        had to say before that moment should already be on their screen
        when it does. Draining only once, at the end, is how a prompt ends
        up asking `approve rename X?` above the line explaining why.
        """
        budget = self.budget if budget is None else budget
        fired: "list[str]" = []
        for tick in range(1, budget + 1):
            fired = self.tick()
            if not fired:
                return Settled(tick, [])
            if after_tick is not None:
                after_tick()
        return Settled(budget, fired)
