"""`examples.adapters` -- the representation-adapter probe, and
`examples.trade`, the oblivious ownership island it maps onto.

Pins both mechanics (the move rule, the overdraft refusal, the
no-double-spend re-read; the seed-only projection and the authoritative
absorb) and findings (ownership round-trips on magnitude; the adapter must
invent the holder and the money-thing `cards` elides; policy has no home).
Findings are pinned as SHAPE, not as one frozen snapshot, so the probe
stays honest if a domain default changes."""

import ast
import dataclasses
import inspect

from examples import adapters, cards, trade
from loopingrules.loop import Loop


def _trade_loop():
    loop = Loop()
    trade.install(loop)
    return loop


def _amounts(w):
    return [holding.amount for _entity, holding in w.all(trade.Holding)]


# -- trade: oblivious, and never in the market ---------------------------

def test_trade_imports_nothing_from_any_example_domain():
    tree = ast.parse(inspect.getsource(trade))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(name.startswith("examples") for name in imported), imported


def test_trade_moves_an_amount_between_opaque_things():
    loop = _trade_loop()
    w = loop.world
    holder, thing = w.spawn(), w.spawn()
    w.spawn(trade.Holding(holder.id, thing.id, 10))
    w.spawn(trade.Movement(holder.id, thing.id, +5), trade.Agreed())
    loop.run()
    assert _amounts(w) == [15]


def test_trade_creates_a_holding_the_first_time_a_pair_is_touched():
    loop = _trade_loop()
    w = loop.world
    holder, thing = w.spawn(), w.spawn()
    w.spawn(trade.Movement(holder.id, thing.id, +3), trade.Agreed())
    loop.run()
    assert _amounts(w) == [3]


def test_trade_refuses_a_movement_that_would_overdraw():
    loop = _trade_loop()
    w = loop.world
    holder, thing = w.spawn(), w.spawn()
    w.spawn(trade.Holding(holder.id, thing.id, 10))
    w.spawn(trade.Movement(holder.id, thing.id, -25), trade.Agreed())
    loop.run()
    assert _amounts(w) == [10]
    assert [r for _entity, r in w.all(trade.Refused)] == [
        trade.Refused(holder.id, thing.id, -25)]
    assert w.all(trade.Movement) == []          # consumed, not retried


def test_trade_needs_agreed_before_it_moves():
    loop = _trade_loop()
    w = loop.world
    holder, thing = w.spawn(), w.spawn()
    w.spawn(trade.Holding(holder.id, thing.id, 10))
    w.spawn(trade.Movement(holder.id, thing.id, +5))    # proposed, not agreed
    loop.run()
    assert _amounts(w) == [10]
    assert len(w.all(trade.Movement)) == 1              # still just proposed


def test_trade_does_not_double_spend_a_holding_within_one_call():
    # Two losses of 6 against a holding of 10: each ALONE is affordable,
    # neither TOGETHER is. The re-read at the top of `apply_movements` is
    # what makes the second one refuse rather than reach 6 - 6 = -2.
    loop = _trade_loop()
    w = loop.world
    holder, thing = w.spawn(), w.spawn()
    w.spawn(trade.Holding(holder.id, thing.id, 10))
    w.spawn(trade.Movement(holder.id, thing.id, -6), trade.Agreed())
    w.spawn(trade.Movement(holder.id, thing.id, -6), trade.Agreed())
    loop.run()
    assert _amounts(w) == [4]
    assert len(w.all(trade.Refused)) == 1


# -- the adapter: cards <-> trade ----------------------------------------

def test_adapter_round_trips_cards_ownership_losslessly():
    before, after = adapters.round_trip(held={"dragon": 2, "goblin": 1})
    assert before == after
    assert before["copies"]["dragon"] == 2      # a real, non-trivial state


def test_adapter_invents_the_holder_and_money_thing_cards_never_had():
    loop, w = adapters.cards_world(cash=100)
    assert w.all(adapters.Agent) == [] and w.all(adapters.Coin) == []
    adapters.install(loop)
    assert len(w.all(adapters.Agent)) == 1
    assert len(w.all(adapters.Coin)) == 1
    # and cards' own shape still has no holder field to recover it into
    assert not any(f.name == "holder" for f in dataclasses.fields(cards.Copies))


def test_adapter_projects_cards_state_onto_trade_holdings():
    loop, w = adapters.cards_world(cash=70, held={"dragon": 2})
    adapters.install(loop)
    loop.run()
    holdings = {(h.holder, h.thing): h.amount for _e, h in w.all(trade.Holding)}
    agent, coin = adapters._agent(w), adapters._coin(w)
    dragon = adapters._card_entity(w, "dragon")
    assert holdings[(agent.id, coin.id)] == 70
    assert holdings[(agent.id, dragon.id)] == 2


def test_a_purchase_in_the_canonical_shape_lands_in_cards_own_representation():
    # Two `Movement`s + `Agreed` performed the buy; NO card rule decided or
    # executed it -- only the adapter and `trade`. The effect lands back in
    # cards' own `Purse`/`Copies`.
    w = adapters.demo_purchase(card_name="dragon", price=40, cash=100)
    assert w.the(cards.Purse) == cards.Purse(60)
    assert adapters.snapshot(w)["copies"]["dragon"] == 1


def test_adapter_leaves_policy_and_value_with_no_home_in_trade():
    assert set(adapters.residual()) == {
        "value", "wants", "max_premium", "max_spend_per_trade",
        "min_cash_reserve", "decision"}
    for concept in ("CardDef", "Wants", "RiskProfile"):
        assert not hasattr(trade, concept)      # trade has no such shape


# -- the verdict, from the run -------------------------------------------

def test_report_states_the_split_verdict():
    r = adapters.report()
    assert r["ownership_round_trips"] is True
    assert r["purchase_landed_in_cards"] is True
    assert r["adapter_invents"] == ("Agent", "Coin")
    assert r["cards_alone_counts"] == {"holdings": 0, "holders": 0}
    assert r["verdict"].startswith("split")
    assert "max_premium" in r["no_home_in_trade"]
