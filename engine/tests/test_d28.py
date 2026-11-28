"""Design D28: everything is SPO. Packs carry complete features; knowledge is read-only."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from rdflib import RDF, Literal, Namespace

from loopingrules.api import create_app
from loopingrules.definitions import split
from loopingrules.engine import Engine
from loopingrules.package import PackageError, add_layer, export_project
from loopingrules.project import Project

EX = Namespace("https://example.org/")
PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix dcterms: <http://purl.org/dc/terms/> . "
       "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")

# One file with everything: a manifest, a shape, an operation, a controller and knowledge.
MODEL = PFX + '''
<urn:lr:package> a lr:Package ; dcterms:title "shop" .

ex:OrderShape a sh:NodeShape ; sh:targetClass ex:Order ;
  sh:property [ sh:path ex:item ; sh:minCount 1 ; sh:class ex:Product ] .

ex:price a lr:Operation ; rdfs:label "price" ;
  lr:where  "?o a ex:Order ; ex:item ?p . ?p ex:price ?v . FILTER NOT EXISTS { ?o ex:total ?t }" ;
  lr:insert "?o ex:total ?v" .

ex:dropProduct a lr:Operation ; rdfs:label "drop product" ;
  lr:where  "?p a ex:Product" ;
  lr:delete "?p a ex:Product" .

ex:likesPricing a lr:Controller ; rdfs:label "likes pricing" ;
  lr:query "SELECT (1 AS ?score) WHERE { GRAPH lr:action { lr:this lr:operation ex:price } }" .

# knowledge: plain facts, beside the sheet
ex:tea a ex:Product ; ex:price 3 ; rdfs:label "Tea" .
'''


def make(tmp_path, sheet="ex:o1 a ex:Order ; ex:item ex:tea .", model=MODEL) -> Engine:
    (tmp_path / "model.ttl").write_text(model)
    (tmp_path / "sheet.ttl").write_text(PFX + sheet)
    return Engine(Project.load(tmp_path, persist=False))


def test_split_by_convention():
    from rdflib import Graph
    defs, know = split(Graph().parse(data=MODEL, format="turtle"))
    assert (EX.tea, EX.price, Literal(3)) in know
    assert (EX.price, RDF.type, None) in defs and (EX.OrderShape, None, None) in defs
    assert not any(s == EX.tea for s, _, _ in defs)
    assert len(list(defs.triples((None, None, None)))) > 10  # the blank nodes came along


def test_knowledge_is_visible_and_satisfies_shapes(tmp_path):
    eng = make(tmp_path)
    assert eng.sheet_violations() == []  # sh:class ex:Product is satisfied by knowledge
    assert (EX.tea, RDF.type, EX.Product) not in eng.sheet  # ...which is not in the sheet
    [price] = [a for a in eng.applications() if a.operation.name == "price"]
    assert price.valid and price.inserts == {(EX.o1, EX.total, Literal(3))}
    assert eng.run(max_ticks=5).status in ("done", "stopped")
    assert (EX.o1, EX.total, Literal(3)) in eng.sheet


def test_knowledge_is_read_only(tmp_path):
    eng = make(tmp_path)
    [drop] = [a for a in eng.applications() if a.operation.name == "drop product"]
    assert not drop.valid and "would delete knowledge from knowledge" in drop.violations[0]["message"]
    with pytest.raises(ValueError, match="read-only knowledge"):
        eng.edit(remove=[(EX.tea, RDF.type, EX.Product)])


def test_knowledge_has_no_blank_nodes(tmp_path):
    with pytest.raises(ValueError, match="blank nodes"):
        make(tmp_path, model=MODEL + "\nex:tea ex:origin [ rdfs:label \"China\" ] .\n")


def _pack(title: str, extends: str, body: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("package.ttl", PFX + f'<urn:lr:package> a lr:Package ; dcterms:title "{title}" ; '
                                       f'lr:version "1.0" ; lr:extends "{extends}" .')
        z.writestr("feature.ttl", PFX + body)
    return buf.getvalue()


DISCOUNT = '''
ex:discount a lr:Operation ; rdfs:label "discount" ;
  lr:where  """?o ex:total ?t . ?d ex:percent ?pc . FILTER NOT EXISTS { ?o ex:discounted true }
               BIND(?t * (100 - ?pc) / 100 AS ?n)""" ;
  lr:delete "?o ex:total ?t" ;
  lr:insert "?o ex:total ?n ; ex:discounted true" .
ex:likesDiscounts a lr:Controller ; rdfs:label "likes discounts" ;
  lr:query "SELECT (1 AS ?score) WHERE { GRAPH lr:action { lr:this lr:operation ex:discount } }" .
ex:sale ex:percent 50 .
'''


def test_a_pack_adds_a_complete_feature(tmp_path):
    make(tmp_path)
    add_layer(_pack("sale", "shop", DISCOUNT), tmp_path)
    eng = Engine(Project.load(tmp_path, persist=False))
    assert {o.name: o.layer for o in eng.operations}["discount"] == "sale"
    assert {c.name: c.layer for c in eng.controllers}["likes discounts"] == "sale"
    eng.run(max_ticks=10)
    assert (EX.o1, EX.total, Literal(1.5)) in eng.sheet or any(
        float(o) == 1.5 for o in eng.sheet.objects(EX.o1, EX.total))
    assert eng.knowledge_source[(EX.sale, EX.percent, Literal(50))] == "sale"

    # packs can extend packs
    add_layer(_pack("sale-banner", "sale", 'ex:sale rdfs:label "Half price" .'), tmp_path)
    assert len(Project.load(tmp_path, persist=False).layers) == 2


def test_conflicting_packs_are_refused(tmp_path):
    make(tmp_path)
    clash = 'ex:price a lr:Operation ; lr:where "?x ?y ?z" ; lr:insert "?x ex:y 1" .'
    with pytest.raises(PackageError, match="defined both"):
        add_layer(_pack("evil", "shop", clash), tmp_path)
    other = _pack("other", "shop", "@prefix ex: <https://elsewhere.org/> . ex:a ex:b 1 .")
    with pytest.raises(PackageError, match="prefix ex"):
        add_layer(other, tmp_path)
    assert not (tmp_path / "layers" / "evil").exists() and not (tmp_path / "layers" / "other").exists()


def test_export_carries_every_file(tmp_path):
    make(tmp_path)
    (tmp_path / "knowledge.ttl").write_text(PFX + "ex:coffee a ex:Product ; ex:price 4 .")
    out = export_project(tmp_path, tmp_path / "shop.lr.zip")
    names = set(zipfile.ZipFile(out).namelist())
    assert {"model.ttl", "knowledge.ttl", "package.ttl", "sheet.ttl"} <= names


def test_api_marks_knowledge(tmp_path):
    make(tmp_path)
    with TestClient(create_app(tmp_path, trust_path=tmp_path / "trust.ttl")) as c:
        rows = c.get("/api/sheet").json()["triples"]
        tea = [r for r in rows if r["s"]["short"] == "ex:tea"]
        assert tea and all(r["source"] == "knowledge" for r in tea)
        assert all("source" not in r for r in rows if r["s"]["short"] == "ex:o1")
        r = c.post("/api/sheet/delete", json={k: tea[0][k]["n3"] for k in "spo"})
        assert r.status_code == 409
