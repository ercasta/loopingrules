"""`examples.parts` -- does a generic `Part` tag, minted alongside every
specific edge through one choke point, let a generic walker stay
generic (provably: adding a brand new edge kind costs it nothing) while
staying analyzable? See that module's own docstring for the question,
and its closing paragraph for the one thing this does NOT fix."""

import dataclasses

import pytest

from examples import parts
from loopingrules import analyze
from loopingrules.world import World


def _tree(w):
    """`block` -[body]-> `add` -[left]-> `a`, -[right]-> `b`, all minted
    through `part_edge` -- the one choke point, never `w.attach` by
    hand for a part edge."""
    block = w.spawn(parts.Block())
    add = w.spawn(parts.Add())
    a = w.spawn(parts.Readable())
    b = w.spawn(parts.Readable())
    parts.part_edge(w, block.id, add.id, parts.Body, "body")
    parts.part_edge(w, add.id, a.id, parts.Left, "left")
    parts.part_edge(w, add.id, b.id, parts.Right, "right")
    return block.id, add.id, a.id, b.id


# -- the generic walkers, over Part alone --------------------------------

def test_part_edge_mints_both_the_specific_and_the_generic_component():
    w = World()
    block, add, a, b = _tree(w)
    assert w.get(block, parts.Body) == parts.Body(add)
    assert parts.Part(add, "body") in w.get_all(block, parts.Part)


def test_parent_of_is_generic_over_which_specific_edge_kind_it_was():
    w = World()
    block, add, a, b = _tree(w)
    assert parts.parent_of(w, add) == block
    assert parts.parent_of(w, a) == add
    assert parts.parent_of(w, b) == add
    assert parts.parent_of(w, block) is None


def test_reachable_crosses_every_specific_edge_kind_generically():
    w = World()
    block, add, a, b = _tree(w)
    assert parts.reachable(w, block) == {block, add, a, b}


def test_a_brand_new_edge_kind_costs_the_generic_walkers_nothing():
    """The actual claim this whole prototype is FOR: define a new
    specific edge kind AFTER `parent_of`/`reachable` are already
    written, mint it through the same choke point, and confirm neither
    walker needed a single line changed to see it -- the property
    `pystrider.symbolic._parent_of`/`_reachable`'s own docstring already
    has, restated here as a test rather than an argument."""
    @dataclasses.dataclass(frozen=True)
    class Otherwise:
        entity: int

    w = World()
    block, add, a, b = _tree(w)
    otherwise_branch = w.spawn(parts.Readable())
    parts.part_edge(w, add, otherwise_branch.id, Otherwise, "otherwise")
    assert parts.parent_of(w, otherwise_branch.id) == add
    assert otherwise_branch.id in parts.reachable(w, block)


# -- the handoff: a specific rule, alongside the generic walkers --------

def test_both_operands_readable_keys_on_the_specific_edges_not_part():
    w = World()
    block, add, a, b = _tree(w)
    parts.both_operands_readable(w)
    assert w.has(add, parts.BothOperandsReadable)


def test_both_operands_readable_abstains_when_one_operand_is_not_readable():
    w = World()
    add = w.spawn(parts.Add())
    readable = w.spawn(parts.Readable())
    unreadable = w.spawn()    # a placeholder -- never marked Readable
    parts.part_edge(w, add.id, readable.id, parts.Left, "left")
    parts.part_edge(w, add.id, unreadable.id, parts.Right, "right")
    parts.both_operands_readable(w)
    assert not w.has(add, parts.BothOperandsReadable)


# -- the actual point: analyzability, before and after ------------------

def test_parent_of_and_reachable_analyze_cleanly():
    for fn in (parts.parent_of, parts.reachable):
        result = analyze.analyze(fn)
        assert result.reads == {parts.Part}, fn.__name__


def test_both_operands_readable_analyzes_cleanly_too():
    result = analyze.analyze(parts.both_operands_readable)
    assert result.reads == {parts.Add, parts.Left, parts.Right, parts.Readable}
    assert result.writes == {parts.BothOperandsReadable}


def test_enclosing_is_honestly_still_opaque():
    """The one thing `Part` does NOT fix, named plainly rather than
    glossed over: `enclosing` is parameterized by WHICH ancestor kind to
    stop at (`kind`, a plain parameter -- not a literal at its own
    definition site), the same "kind held in a variable" pattern found
    in `pystrider.symbolic.known_value` and others. `Part` fixes the
    TRAVERSAL half of this function's job; the stopping condition is a
    separate, sibling instance of an already-named family, not
    something this prototype's fix reaches. Pinned so this stays an
    honest, permanent record rather than something that quietly stops
    being true (or gets "fixed" by loosening the check) unnoticed."""
    with pytest.raises(analyze.Opaque):
        analyze.analyze(parts.enclosing)
