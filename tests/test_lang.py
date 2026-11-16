"""`loopingrules_lang` -- the authoring surface + harness.

A model in YAML (components + operations) runs against a context (the anchor) on
the existing substrate: different contexts take different trajectories with no
per-use-case code, an unknown concept is a **gap**, and a run is deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from loopingrules import schema
from loopingrules_lang import cli, context, harness

MODELS = Path(harness.__file__).resolve().parent / "models"
MARKET = MODELS / "market.yaml"
MARKET_CTX = MODELS / "market.context.yaml"


def _context(*entities):
    return {"entities": list(entities)}


def test_components_are_declared_and_a_gap_is_a_gap():
    model = harness.load(MARKET)
    assert model.schema.slot("candidate", "worth") == ("candidate", "worth")
    with pytest.raises(schema.Gap):
        model.schema.slot("nope", None)
    with pytest.raises(schema.Gap):
        model.schema.slot("candidate", "nope")
    assert model.schema.component("excluded").is_tag


def test_the_sample_model_reaches_the_expected_answer():
    run = harness.run_files(MARKET, MARKET_CTX)
    assert run.settled
    assert run.chosen() == {"goblin"}          # cheapest within the limit
    assert run.gaps() == []
    assert run.ticks >= 1


def test_an_unknown_concept_is_a_gap_not_a_guess():
    model = harness.load(MARKET)
    run = harness.run(model, _context(
        {"candidate": {"worth": 5.0, "name": "goblin"}},
        {"do": {"what": "underrated"}},
    ))
    assert run.chosen() == set()
    assert run.gaps() == ["underrated"]


def test_held_out_combinations_compose_without_new_operations():
    model = harness.load(MARKET)
    cases = {
        ("all", None): {"goblin", "wand", "dragon"},
        ("all", 20.0): {"goblin"},
        ("cheapest", None): {"goblin"},
        ("cheapest", 30.0): {"goblin"},
    }
    for (what, limit), expected in cases.items():
        directive = {"what": what}
        if limit is not None:
            directive["limit"] = limit
        run = harness.run(model, _context(
            {"candidate": {"worth": 5.0, "name": "goblin"}},
            {"candidate": {"worth": 25.0, "name": "wand"}},
            {"candidate": {"worth": 40.0, "name": "dragon"}},
            {"funds": {"cash": 30.0, "reserve": 10.0}},
            {"do": directive},
        ))
        assert run.settled
        assert run.chosen() == expected, (what, limit)


def test_a_run_is_deterministic():
    first = harness.run_files(MARKET, MARKET_CTX)
    second = harness.run_files(MARKET, MARKET_CTX)
    assert first.applied == second.applied


def test_context_seeds_tags_and_fields():
    from loopingrules.world import World
    world = World()
    spawned = context.seed(world, _context({"done": {}}, {"do": {"what": "all"}}))
    assert world.has(spawned[0], "done")
    assert world.get(spawned[1], "do", "what") == "all"


def test_cli_run_prints_the_world_and_exits_zero(capsys):
    code = cli.main(["run", str(MARKET), "-c", str(MARKET_CTX)])
    out = capsys.readouterr().out
    assert code == 0
    assert "goblin" in out
    assert "gaps: (none)" in out
