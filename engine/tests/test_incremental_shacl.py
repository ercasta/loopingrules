"""Incremental SHACL (validation.validate_change) must find exactly the new violations
that validating everything finds, for every candidate application."""

import random
import shutil
from pathlib import Path

import pytest

from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.validation import validate, violation_key

from test_lazy_pick import project as folder_project, stub_shell

ROOT = Path(__file__).resolve().parents[2] / "examples"


def new_violations(eng: Engine, app, incremental: bool) -> set:
    eng.incremental_shacl = incremental
    try:
        found = eng.validate_change(eng.resulting_state(app), app.deletes | app.inserts)
    finally:
        eng.incremental_shacl = True
    baseline = {violation_key(v) for v in eng.sheet_violations()}
    return {violation_key(v) for v in found} - baseline


def same_for_every_candidate(eng: Engine) -> int:
    n = 0
    for app in eng._enumerate():
        if not app.valid or app.noop:
            continue
        assert new_violations(eng, app, True) == new_violations(eng, app, False), app.operation.name
        n += 1
    return n


def run_comparing(eng: Engine, limit: int = 1000) -> int:
    ticks = 0
    while ticks < limit:
        eng.tool_phase()
        same_for_every_candidate(eng)
        if eng.step().status != "applied":
            break
        ticks += 1
    return ticks


@pytest.mark.parametrize("example, layer", [("folder-scan", False), ("folder-scan", True), ("folder-scan-goal", False)])
def test_folder_scan(tmp_path, example, layer):
    eng = Engine(folder_project(tmp_path, example, layer), shell=stub_shell(), approver=lambda c: True)
    assert run_comparing(eng) > 3


def test_planning_pack_counter(tmp_path):
    from test_d31 import project as counter
    assert run_comparing(counter(tmp_path, goal=7)) > 20


def test_rubik_scramble_and_first_ticks_of_a_solve(tmp_path):
    d = tmp_path / "rubik"
    shutil.copytree(ROOT / "rubik", d, ignore=shutil.ignore_patterns(".lr", "*.py", "__pycache__"))
    eng = Engine(Project.load(d, persist=False))
    rng = random.Random(5)
    moves = " ".join("mv:" + rng.choice("UDFBRL") + rng.choice(["", "i", "2"]) for _ in range(4))
    eng.post(f"[] a rk:Scramble ; rk:moves ( {moves} ) .")
    assert run_comparing(eng) >= 4
    eng.post("[] a rk:Solve .")
    assert run_comparing(eng, limit=12) == 12


# --- the cases where "where a change can matter" is subtle -------------------------

PFX = """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix lr: <https://loopingrules.org/ns#> .
@prefix ex: <https://example.org/> .
"""

SHAPES = PFX + """
ex:PetShape a sh:NodeShape ; sh:targetClass ex:Pet ;
  sh:property [ sh:path ex:owner ; sh:class ex:Person ; sh:maxCount 1 ] .
ex:PersonShape a sh:NodeShape ; sh:targetClass ex:Person ;
  sh:property [ sh:path [ sh:inversePath ex:owner ] ; sh:class ex:Pet ] .
ex:ListShape a sh:NodeShape ; sh:targetClass ex:Bag ;
  sh:property [ sh:path ( ex:items [ sh:zeroOrMorePath rdf:rest ] rdf:first ) ; sh:class ex:Thing ] .
"""

OPS = {
    # a value's type changes: sh:class on the node that points at it (one step back)
    "unperson": ("?x a ex:Person", "?x a ex:Person", ""),
    # an inverse path's value loses its type
    "unpet": ("?x a ex:Pet", "?x a ex:Pet", ""),
    # a second owner (maxCount)
    "coown": ("?p a ex:Pet . ?o a ex:Person . FILTER NOT EXISTS { ?p ex:owner ?o }", "", "?p ex:owner ?o"),
    # deep in a list: a complex path
    "untype": ("?t a ex:Thing", "?t a ex:Thing", ""),
    # classes in the data
    "subclass": ("?c a ex:Kind", "", "?c rdfs:subClassOf ex:Person"),
    # blank nodes
    "blank": ("?p a ex:Pet", "", "?p ex:owner [ a ex:Robot ]"),
}

SHEET = PFX + """
ex:rex a ex:Pet ; ex:owner ex:ann .
ex:ann a ex:Person .
ex:bob a ex:Person .
ex:bag a ex:Bag ; ex:items ( ex:t1 ex:t2 ) .
ex:t1 a ex:Thing . ex:t2 a ex:Thing .
ex:Robot a ex:Kind .
ex:r2d2 a ex:Robot . ex:cat ex:owner ex:r2d2 .   # once robots are persons, ex:cat must be a Pet
ex:old a ex:Pet ; ex:owner ex:nobody .
"""


def synthetic(tmp_path) -> Engine:
    model = SHAPES
    for name, (where, delete, insert) in OPS.items():
        model += f'ex:{name} a lr:Operation ; rdfs:label "{name}" ; lr:where "{where}" ; '
        model += (f'lr:delete "{delete}" ; ' if delete else "") + (f'lr:insert "{insert}" ' if insert else "") + ".\n"
    (tmp_path / "model.ttl").write_text(model)
    (tmp_path / "sheet.ttl").write_text(SHEET)
    return Engine(Project.load(tmp_path, persist=False))


def test_subtle_cases_find_the_same_new_violations(tmp_path):
    eng = synthetic(tmp_path)
    assert eng.sheet_violations()  # ex:old's owner isn't a Person: there before, never "new"
    caught = {}
    for app in eng._enumerate():
        inc, full = new_violations(eng, app, True), new_violations(eng, app, False)
        assert inc == full, (app.operation.name, app.bindings)
        caught[app.operation.name] = caught.get(app.operation.name, False) or bool(full)
    # every case does add a violation, so the comparison isn't vacuous
    assert caught == {name: True for name in OPS}, caught
