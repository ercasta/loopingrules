"""The pyoxigraph mirror (mirror.py) must match exactly what rdflib matches."""

import random
import shutil
from pathlib import Path

import pytest
from rdflib import XSD, BNode, Graph, Literal, Namespace, URIRef

from loopingrules.engine import Engine
from loopingrules.mirror import Mirror, available
from loopingrules.operations import enumerate_applications
from loopingrules.project import Project

from test_lazy_pick import project, stub_shell

pytestmark = pytest.mark.skipif(not available(), reason="pyoxigraph is not installed or can't load")

ROOT = Path(__file__).resolve().parents[2] / "examples"
EX = Namespace("https://example.org/")


def same_enumeration(eng: Engine) -> int:
    """Enumerate with the mirror and with rdflib; return how many applications there are."""
    with_mirror = eng._enumerate()
    plain = eng._protect_knowledge(enumerate_applications(eng.view, eng.operations, eng.model))
    def unminted(triples):  # minted names are fresh on every enumeration
        return frozenset(tuple(URIRef("urn:lr:gen:*") if str(x).startswith("urn:lr:gen:") else x for x in t)
                         for t in triples)
    key = lambda a: (a.id, a.valid, unminted(a.deletes), unminted(a.inserts),  # noqa: E731
                     tuple(sorted(a.bindings.items())), tuple(v["message"] for v in a.violations))
    assert [key(a) for a in with_mirror] == [key(a) for a in plain]
    assert not eng.mirror.unsupported
    return len(with_mirror)


@pytest.mark.parametrize("example, layer", [("folder-scan", False), ("folder-scan", True),
                                            ("folder-scan-goal", False)])
def test_folder_scan_matches_alike_at_every_tick(tmp_path, example, layer):
    eng = Engine(project(tmp_path, example, layer), shell=stub_shell(), approver=lambda c: True)
    ticks = 0
    while True:
        eng.tool_phase()
        same_enumeration(eng)
        best = eng.pick()
        if best is None:
            break
        eng.apply(best, run_tools=False)
        ticks += 1
    assert ticks > 3


def test_rubik_matches_alike_at_every_tick(tmp_path):
    d = tmp_path / "rubik"
    shutil.copytree(ROOT / "rubik", d, ignore=shutil.ignore_patterns(".lr", "*.py", "__pycache__"))
    eng = Engine(Project.load(d, persist=False))
    rng = random.Random(7)
    moves = " ".join("mv:" + rng.choice("UDFBRL") + rng.choice(["", "i", "2"]) for _ in range(8))
    eng.post(f"[] a rk:Scramble ; rk:moves ( {moves} ) .")
    while eng.step().status == "applied":
        same_enumeration(eng)
    eng.post("[] a rk:Solve .")
    ticks = 0
    while True:
        same_enumeration(eng)
        if eng.step().status != "applied":
            break
        ticks += 1
    assert ticks > 3


def test_terms_round_trip_and_sync_follows_the_sheet():
    knowledge = Graph()
    knowledge.add((EX.k, EX.p, Literal("shared")))
    sheet = Graph()
    b = BNode()
    terms = [Literal("plain"), Literal("en", lang="en"), Literal(5), Literal("x", datatype=XSD.string),
             Literal("1.50", datatype=XSD.decimal), Literal("odd", datatype=EX.custom), b]
    for i, o in enumerate(terms):
        sheet.add((EX[f"s{i}"], EX.p, o))
    sheet.add((EX.k, EX.p, Literal("shared")))  # in the sheet and in the knowledge
    m = Mirror(knowledge).sync(sheet, sheet)
    rows = m.solutions("?s ex:p ?o", "PREFIX ex: <https://example.org/>\n")
    found = {r["o"] for r in rows}
    assert found == set(terms) | {Literal("shared")}
    for o in found:  # the very same rdflib terms, datatype and all
        assert any(o == t and type(o) is type(t) and getattr(o, "datatype", None) == getattr(t, "datatype", None)
                   for t in terms + [Literal("shared")])

    # removing a sheet triple that is also knowledge keeps it; others go
    sheet.remove((EX.k, EX.p, Literal("shared")))
    sheet.remove((EX.s0, EX.p, Literal("plain")))
    m.sync(sheet, sheet)
    found = {r["o"] for r in m.solutions("?s ex:p ?o", "PREFIX ex: <https://example.org/>\n")}
    assert Literal("shared") in found and Literal("plain") not in found


def test_guards_see_their_bindings():
    sheet = Graph()
    sheet.add((EX.a, EX.p, EX.b))
    m = Mirror(Graph()).sync(sheet, sheet)
    pfx = "PREFIX ex: <https://example.org/>\n"
    assert m.holds("?x ex:p ?y", {"x": EX.a}, pfx)
    assert not m.holds("?x ex:p ?y", {"x": EX.b}, pfx)
    assert not m.holds("FILTER NOT EXISTS { ?x ex:p ?y }", {"x": EX.a}, pfx)
    # a parameter only inside the filter is bound there too (as rdflib does)
    assert m.holds("FILTER NOT EXISTS { ?x ex:p ?y }", {"x": EX.b}, pfx)
    assert m.holds("?x ex:p ?y", {"x": EX.a, "unused": Literal("1.50", datatype=XSD.decimal)}, pfx)
