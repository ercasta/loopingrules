"""M0's claims, as permanent verification points (`docs/plan-forge.md`).

M0 asks two things of the forge: that `cards`' catalog is *derivable* from
the rules' own source, and that a small IR can *express* a real domain --
all of it, text front-ends included -- and lower back to Python with the
same behaviour. If either stops holding, this fails loudly, before anything
is built on top of it. The spike proved it once; this keeps it proven.
"""

from examples import cards
from loopingrules_calibration.kit import Scenario, replay

import loopingrules.analyze as analyze
from loopingrules_forge import m0


def test_every_cards_rule_is_derivable():
    """No rule in the dialect's blind spot: the catalog can be regenerated,
    not hand-maintained."""
    assert analyze.component_map(*cards.RULES).opaque == {}


def test_reads_survive_the_round_trip():
    """Reads are the dormancy gate (`Loop.rule`), so if lowering changed
    them, the trajectory would differ for reasons that have nothing to do
    with behaviour -- including through helpers, which `analyze` follows."""
    module = m0.load_emitted(m0.emit_module())
    for name in m0.IR:
        real = analyze.analyze(getattr(cards, name))
        got = analyze.analyze(getattr(module, name))
        assert got.reads == real.reads, name
        assert got.negated_reads == real.negated_reads, name


def test_emitted_rules_reproduce_the_signature():
    """The whole claim, driven by real command lines through the kit's
    `replay`: IR -> emitted Python -> identical `signature` (`fired` +
    settled snapshot) and identical replies."""
    module = m0.load_emitted(m0.emit_module())
    scenario = Scenario(lines=m0.LINES)

    real = replay(scenario, cards.install)
    emit = replay(scenario, m0.make_install(module))

    assert not real.hot and not emit.hot
    assert real.replies == emit.replies
    assert m0.signature(real.world, real.fired) == \
        m0.signature(emit.world, emit.fired)
