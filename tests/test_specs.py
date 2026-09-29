"""`loopingrules.specs`: a circuit spec survives being written down and
read back -- equal, and behaving the same once compiled -- and a file
that lies about what it is (an unregistered class, an unknown shape, a
class hidden in `Const`, a nesting bomb) is refused rather than obeyed.

The round-trip is proven against every spec the repo already has, not a
toy written for this file: the cards specs in `test_circuits`, and
`examples.files.do_stat_spec`, which carries a `Call`."""

import dataclasses
import json

import pytest

import test_circuits
from examples import cards, files, judge
from loopingrules import circuits, specs
from loopingrules.loop import Loop
from loopingrules.world import World


def _all_specs():
    found = {}
    for module in (test_circuits, files):
        for name, value in vars(module).items():
            if isinstance(value, (circuits.TagCircuit, circuits.ValueCircuit,
                                  circuits.ActionCircuit)):
                found["%s.%s" % (module.__name__, name)] = value
    return found


def _registry():
    kinds = []
    for module in (test_circuits, cards, judge, files, circuits):
        kinds += [v for v in vars(module).values()
                  if isinstance(v, type) and dataclasses.is_dataclass(v)]
    return specs.registry_of(*kinds)


REAL = _all_specs()


def _through_json(data):
    return json.loads(json.dumps(data))


def test_the_repo_has_enough_real_specs_to_make_the_round_trip_mean_something():
    assert len(REAL) >= 12


@pytest.mark.parametrize("name", sorted(REAL))
def test_every_real_spec_comes_back_equal_through_json(name):
    spec = REAL[name]
    back = specs.decode_spec(_through_json(specs.encode_spec(spec)), _registry())
    assert back == spec
    assert hash(back) == hash(spec)


def test_the_catalog_names_every_dataclass_circuits_defines_that_is_a_spec():
    not_specs = {"ToolRequest", "ToolResult", "Rejected"}
    defined = {name for name, v in vars(circuits).items()
               if isinstance(v, type) and dataclasses.is_dataclass(v)
               and v.__module__ == circuits.__name__ and name not in not_specs}
    assert defined == set(specs._CATALOG)


# -- a loaded spec runs the same as the one it came from -----------------

@dataclasses.dataclass(frozen=True)
class Price:
    amount: int


@dataclasses.dataclass(frozen=True)
class Cheap:
    pass


CHEAP = circuits.TagCircuit(
    for_each=Price,
    condition=circuits.Le(circuits.Self(Price, "amount"), circuits.Const(10)),
    tag=Cheap,
)


def _cheap_rows(rule):
    w = World()
    for amount in (3, 10, 11, 99):
        w.spawn(Price(amount))
    rule(w)
    return sorted(p.amount for _e, p, _c in w.each(Price, Cheap))


def test_a_loaded_tag_circuit_tags_exactly_what_the_original_did():
    data = _through_json(specs.dump_specs({"cheap": CHEAP}))
    problems, loaded = specs.load_specs(data, specs.registry_of(Price, Cheap))
    assert problems == []
    assert _cheap_rows(circuits.compile_circuit(loaded["cheap"])) == \
        _cheap_rows(circuits.compile_circuit(CHEAP)) == [3, 10]


@dataclasses.dataclass(frozen=True)
class Wanted:
    folder: int


def test_a_loaded_call_still_needs_its_tool_registered_to_compile():
    spec = circuits.ActionCircuit(
        require=(Wanted,), without=(),
        effects=(circuits.Call("ls", (circuits.Self(Wanted, "folder"),)),
                 circuits.Destroy()))
    data = _through_json(specs.dump_specs({"rescan": spec}))
    _problems, loaded = specs.load_specs(data, specs.registry_of(Wanted))
    with pytest.raises(KeyError):
        circuits.compile_circuit(loaded["rescan"], tools={"stat": lambda w, x: x})
    with pytest.raises(KeyError):
        circuits.compile_circuit(loaded["rescan"])
    circuits.compile_circuit(loaded["rescan"], tools={"ls": lambda w, x: x})


def test_a_loaded_action_circuit_deposits_the_same_request():
    spec = circuits.ActionCircuit(
        require=(Wanted,), without=(),
        effects=(circuits.Call("ls", (circuits.Self(Wanted, "folder"),)),
                 circuits.Destroy()))
    data = _through_json(specs.dump_specs({"rescan": spec}))
    _problems, loaded = specs.load_specs(data, specs.registry_of(Wanted))
    loop = Loop()
    loop.rule(circuits.compile_circuit(loaded["rescan"], tools={"ls": lambda w, x: x}))
    loop.world.spawn(Wanted(7))
    loop.run()
    requests = [r for _e, r in loop.world.each(circuits.ToolRequest)]
    assert requests == [circuits.ToolRequest("ls", (7,))]
    assert loop.world.each(Wanted) == []


# -- what the file does not get to say ------------------------------------

def _load_one(body, registry=None):
    return specs.load_specs({"version": 1, "specs": {"x": body}},
                            registry if registry is not None else specs.registry_of(Price, Cheap))


def test_a_class_outside_the_registry_refuses_that_spec_and_names_it():
    data = specs.dump_specs({"cheap": CHEAP})
    problems, loaded = specs.load_specs(data, specs.registry_of(Price))
    assert loaded == {}
    assert len(problems) == 1 and "cheap" in problems[0] and "Cheap" in problems[0]


def test_one_bad_spec_does_not_take_the_others_down():
    data = specs.dump_specs({"cheap": CHEAP})
    data["specs"]["bad"] = {"$spec": "Nope"}
    problems, loaded = specs.load_specs(data, specs.registry_of(Price, Cheap))
    assert list(loaded) == ["cheap"]
    assert len(problems) == 1 and problems[0].startswith("bad:")


def test_a_name_that_is_not_a_catalog_shape_is_refused_not_looked_up():
    for name in ("__import__", "os.system", "compile_circuit", "MISSING", "ToolRequest"):
        problems, loaded = _load_one({"$spec": name})
        assert loaded == {} and problems, name


def test_a_class_smuggled_into_const_is_refused():
    body = {"$spec": "TagCircuit", "for_each": {"$class": specs._name_of(Price)},
            "condition": {"$spec": "Const", "value": {"$class": specs._name_of(Price)}},
            "tag": {"$class": specs._name_of(Cheap)}}
    problems, loaded = _load_one(body)
    assert loaded == {} and "Const.value" in problems[0]


def test_a_spec_node_smuggled_into_const_is_refused():
    body = {"$spec": "TagCircuit", "for_each": {"$class": specs._name_of(Price)},
            "condition": {"$spec": "Const", "value": {"$spec": "Destroy"}},
            "tag": {"$class": specs._name_of(Cheap)}}
    problems, loaded = _load_one(body)
    assert loaded == {} and "Const.value" in problems[0]


def test_an_unknown_or_missing_field_is_refused():
    good = specs.encode_spec(CHEAP)
    extra = dict(good, sneaky=1)
    assert _load_one(extra)[0]
    missing = {k: v for k, v in good.items() if k != "tag"}
    assert _load_one(missing)[0]


def test_a_registry_value_that_is_not_a_class_is_refused():
    problems, loaded = _load_one(specs.encode_spec(CHEAP),
                                 {specs._name_of(Price): Price, specs._name_of(Cheap): 3})
    assert loaded == {} and problems


def test_a_nesting_bomb_is_refused_rather_than_blowing_the_stack():
    body = {"$spec": "Const", "value": 1}
    for _ in range(specs.MAX_DEPTH * 4):
        body = {"$spec": "Not", "expr": body}
    wrapper = {"$spec": "TagCircuit", "for_each": {"$class": specs._name_of(Price)},
               "condition": body, "tag": {"$class": specs._name_of(Cheap)}}
    problems, loaded = _load_one(wrapper)
    assert loaded == {} and "deeper" in problems[0]


def test_only_a_rule_shape_may_be_a_top_level_spec():
    with pytest.raises(specs.SpecError):
        specs.dump_specs({"x": circuits.Const(1)})
    problems, loaded = _load_one(specs.encode_spec(circuits.Const(1)))
    assert loaded == {} and "rule shape" in problems[0]


def test_a_wrong_version_or_shapeless_pack_loads_nothing_and_says_why():
    assert specs.load_specs({"version": 99, "specs": {}}, {})[1] == {}
    assert "version" in specs.load_specs({"version": 99, "specs": {}}, {})[0][0]
    assert specs.load_specs({"version": 1}, {})[0]
    assert specs.load_specs([], {})[0]


def test_encoding_refuses_what_is_not_the_closed_catalog():
    with pytest.raises(specs.SpecError):
        specs.encode_spec(lambda w: None)
    with pytest.raises(specs.SpecError):
        specs.encode_spec(circuits.Const(Price))
    with pytest.raises(specs.SpecError):
        specs.encode_spec(circuits.Const(object()))


def test_tuples_and_lists_stay_distinct_inside_const():
    for value in ((1, 2), [1, 2], ("a", (1, [2]))):
        back = specs.decode_spec(_through_json(specs.encode_spec(circuits.Const(value))), {})
        assert back == circuits.Const(value)
        assert type(back.value) is type(value)
