"""The A/B: the SAME coordination in the substrate and in Linda.

See `docs/patterns-oblivious-composition.md` §7. One hub writer attaches a shared
`verdict`; two domain readers (`alpha`, `beta`) act on the shared verdict **joined
with their own component**. `measure_*` returns the numbers; each is a claim that
can fail, and `run_all()` gives the rows and the pre-registered verdict.

The fairness concession the doc names: Linda gets a **tag convention** (a
fixed-arity keyed tuple), because comparing against a positional straw man would
prove nothing.
"""

from __future__ import annotations

from loopingrules import Loop

from .linda import Blocked, TupleSpace, Var

# (name, candidate worth, the domain's OWN component)
ENTITIES = (("a", 5.0, "alpha"), ("b", -1.0, "alpha"), ("c", 7.0, "beta"))
IDS = {name: index for index, (name, _, _) in enumerate(ENTITIES)}
NAME = {index: name for name, index in IDS.items()}
VAR_ID = Var("id")
VAR_WORTH = Var("worth")


# -- instrument A: the substrate -------------------------------------------

def alpha_reader(w) -> None:
    """Reads the shared `verdict.ok` JOINED with its OWN `alpha` component."""
    for entity, ok in w.each("verdict", "ok"):
        if ok and w.has(entity, "alpha"):
            w.mark(entity, "alpha_done")


def beta_reader(w) -> None:
    for entity, ok in w.each("verdict", "ok"):
        if ok and w.has(entity, "beta"):
            w.mark(entity, "beta_done")


def install(loop, *, audit=False) -> None:
    world = loop.world
    for name, worth, domain in ENTITIES:
        entity = world.spawn()
        world.set(entity, "candidate", "worth", worth)
        world.set(entity, "name", "name", name)
        world.mark(entity, domain)

    def evaluate(w):
        for entity, worth in w.each("candidate", "worth", without="verdict"):
            w.set(entity, "verdict", "ok", worth > 0.0)
            if audit:
                w.set(entity, "verdict", "reason", "seen")   # SAME component, new field

    loop.rule(evaluate)
    loop.rule(alpha_reader)
    loop.rule(beta_reader)


def _names_carrying(world, component) -> set:
    return {world.get(entity, "name", "name") for entity, in world.each(component)}


def substrate(*, audit=False):
    loop = Loop()
    install(loop, audit=audit)
    settled = loop.run()
    done = (_names_carrying(loop.world, "alpha_done")
            | _names_carrying(loop.world, "beta_done"))
    return loop, settled, done


# -- instrument B: Linda ----------------------------------------------------

def linda(*, audit=False, tagged=False):
    """The same coordination in a tuple space. `tagged` keeps the `verdict` tuple
    at a fixed arity (the convention) and adds the audit data as its own tuple;
    untagged lets the tuple grow a field (the naive, positional encoding)."""
    ts = TupleSpace()
    for name, worth, domain in ENTITIES:
        ts.out("candidate", IDS[name], worth)
        ts.out(domain, IDS[name])

    for _tup, bind in ts.all("candidate", VAR_ID, VAR_WORTH):
        id_, ok = bind["id"], bind["worth"] > 0.0
        if not audit:
            ts.out("verdict", id_, ok)
        elif tagged:
            ts.out("verdict", id_, ok)
            ts.out("audit", id_, "seen")
        else:
            ts.out("verdict", id_, ok, "seen")            # arity grew

    for domain in ("alpha", "beta"):
        for _tup, bind in ts.all("verdict", VAR_ID, True):
            if ts.rdp(domain, bind["id"]) is not None:
                ts.out(domain + "_done", bind["id"])

    done = set()
    for suffix in ("alpha_done", "beta_done"):
        for _tup, bind in ts.all(suffix, VAR_ID):
            done.add(NAME[bind["id"]])
    return ts, done


# -- the four measurements --------------------------------------------------

def measure_m1() -> dict:
    """Layout decoupling: the writer adds a field; does the reader still match?"""
    _l0, _s0, plain = substrate(audit=False)
    _l1, _s1, audited = substrate(audit=True)
    _t1, naive = linda(audit=True, tagged=False)
    _t2, tagged = linda(audit=True, tagged=True)
    return {
        "substrate_plain": sorted(plain),
        "substrate_stable": plain == audited,
        "linda_naive": sorted(naive),
        "linda_naive_breaks": naive == set(),
        "linda_tagged_stable": tagged == plain,
    }


def consider(w) -> None:
    """Negation in the match: candidates with NO `item` component."""
    for entity, _worth in w.each("candidate", "worth", without="item"):
        w.mark(entity, "item")


def measure_m2() -> dict:
    """Negation/conjunction: one match vs a scan + a probe per candidate."""
    loop = Loop()
    for name, worth, domain in ENTITIES:
        entity = loop.world.spawn()
        loop.world.set(entity, "candidate", "worth", worth)
    loop.rule(consider)
    loop.run()
    substrate_marked = len(loop.world.each("item"))

    ts = TupleSpace()
    for name, worth, domain in ENTITIES:
        ts.out("candidate", IDS[name], worth)
    linda_calls = 0
    for _tup, bind in ts.all("candidate", VAR_ID, VAR_WORTH):
        linda_calls += 1                              # the scan
        if ts.rdp("item", bind["id"]) is None:        # the absence probe
            linda_calls += 1
            ts.out("item", bind["id"])
    linda_marked = len(ts.all("item", VAR_ID))
    return {"substrate_marked": substrate_marked, "linda_marked": linda_marked,
            "linda_calls": linda_calls}


def measure_m3() -> dict:
    """Derived obliviousness: what does the reader's own analysis say it reads?"""
    loop = Loop()
    loop.rule(alpha_reader)
    reads = getattr(alpha_reader, "_loopingrules_watches", None)
    return {
        "substrate_reads": sorted(reads or ()),
        "linda_reads": (("verdict", "?", "?"), ("alpha", "?")),
    }


def measure_m4() -> dict:
    """Blocking vs reactive."""
    ts = TupleSpace()
    blocked = False
    try:
        ts.rd("nothing", "here", timeout=0.005)
    except Blocked:
        blocked = True
    _loop, settled, _done = substrate()
    return {"linda_rd_blocks": blocked,
            "substrate_settles": not settled.hot}


def run_all():
    m1, m2, m3, m4 = measure_m1(), measure_m2(), measure_m3(), measure_m4()
    rows = [
        ("M1 layout", m1["substrate_stable"] and m1["linda_naive_breaks"]
         and m1["linda_tagged_stable"],
         "naive -> %s, tagged -> %s" % (m1["linda_naive"], m1["substrate_plain"])),
        ("M2 conjunction", m2["substrate_marked"] == m2["linda_marked"]
         and m2["linda_calls"] > m2["substrate_marked"],
         "%d marked; linda %d calls" % (m2["substrate_marked"], m2["linda_calls"])),
        ("M3 derived reads", bool(m3["substrate_reads"]),
         "%r" % (m3["substrate_reads"],)),
        ("M4 blocking", m4["substrate_settles"] and m4["linda_rd_blocks"],
         "substrate settles; linda rd blocks"),
    ]
    return m1, m2, m3, m4, rows


def main() -> int:
    m1, m2, m3, m4, rows = run_all()
    print("== linda A/B: the substrate vs a tuple space", "=" * 20)
    for label, ok, note in rows:
        print("  %-18s %-5s %s" % (label, "ok" if ok else "NO", note))
    print("  substrate reads:", m3["substrate_reads"])
    print("  rdp/rdp probes for absence:", m2["linda_calls"], "calls for",
          m2["substrate_marked"], "candidates")
    return 0 if all(ok for _label, ok, _note in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
