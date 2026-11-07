"""R1's claims, as permanent verification points (`docs/plan-reflection.md`).

The forge's IR is a CLOSED semantics, so `reads`/`writes` over it is a total
function that agrees with `analyze` on the lowered Python -- the structural
sibling of M0's behavioural claim. If a rule ever stopped agreeing, or a
verbatim helper could be silently under-reported, this fails.
"""

import pytest

from loopingrules_forge import m0
from loopingrules_reflect import r1


def test_ir_analysis_agrees_with_analyze_for_every_rule():
    """12/12: reads, writes, negated_reads and destroys, IR vs the AST."""
    result = r1.report()
    assert result["agree"] == result["total"] == len(m0.IR)
    assert result["ok"]


def test_a_verbatim_helper_must_declare_its_reads():
    """The escape is forced and named, not silent: `hear_status`'s reads live
    in the verbatim `_status_text`, so without a declaration the walker
    REFUSES rather than reporting that it reads nothing."""
    with pytest.raises(r1.Unknown):
        r1.reads_of(m0.IR["hear_status"](), m0.IR_HELPERS, {})


def test_ir_analysis_is_total_over_the_whole_ir():
    """Every rule AND every IR helper analyzes without an `Unknown` -- the
    totality the Python AST cannot offer. `_status_text` is declared because
    it is verbatim; nothing else needs a declaration. An unknown tag would
    raise here, which is the point: a closed semantics has no `Opaque`, only
    nodes that exist and nodes that do not."""
    external = {"_status_text": (set(), set(), False)}
    for body in m0.IR.values():
        r1.reads_of(body(), m0.IR_HELPERS, external)
    for _params, body in m0.IR_HELPERS.values():
        r1.reads_of(body, m0.IR_HELPERS, external)


def test_negated_reads_survive_the_ir():
    """`decide_buy` tests `wants is None` in a variable, which -- like the
    emitted Python -- `analyze` does NOT read as absence (the read is bound,
    not the direct operand). The IR analysis reproduces that exactly, so the
    gate is the same."""
    got = r1.reads_of(m0.IR["decide_buy"](), m0.IR_HELPERS,
                      {"_status_text": (set(), set(), False)})
    assert got.negated_reads == set()
