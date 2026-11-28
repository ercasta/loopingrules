"""Design D25: input and output channels, listening, app mode."""

import io

import pytest
from fastapi.testclient import TestClient
from rdflib import RDF, Literal, Namespace

from loopingrules.api import create_app
from loopingrules.channels import PostError
from loopingrules.cli import listen
from loopingrules.engine import Engine
from loopingrules.package import Manifest, read_manifest
from loopingrules.project import Project
from loopingrules.vocab import LR

EX = Namespace("https://example.org/")
CMD = Namespace("https://example.org/cmd#")

PFX = ("@prefix lr: <https://loopingrules.org/ns#> . @prefix ex: <https://example.org/> . "
       "@prefix cmd: <https://example.org/cmd#> . @prefix sh: <http://www.w3.org/ns/shacl#> . "
       "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> . "
       "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")

# A to-do list driven by messages: cmd:AddTask creates a task and answers on lr:out.
MODEL = PFX + '''
cmd:AddTaskShape a sh:NodeShape ; sh:targetClass cmd:AddTask ;
  sh:property [ sh:path cmd:title ; sh:minCount 1 ; sh:maxCount 1 ; sh:datatype xsd:string ] .

ex:addTask a lr:Operation ; rdfs:label "add task" ;
  lr:params "m" ;
  lr:where  """ ?m lr:channel lr:in ; a cmd:AddTask ; cmd:title ?t . """ ;
  lr:insert """ [] a ex:Task ; ex:title ?t .
                [] lr:channel lr:out ; a lr:Say ; lr:text ?t ; lr:replyTo ?m . """ ;
  lr:steps ( [ lr:where """ ?m ?p ?o . """ ; lr:delete """ ?m ?p ?o . """ ] ) .
'''


def make(tmp_path, package=None) -> Engine:
    (tmp_path / "model.ttl").write_text(MODEL)
    (tmp_path / "controllers.ttl").write_text(PFX)
    (tmp_path / "sheet.ttl").write_text(PFX + "ex:list a ex:List .")
    if package:
        (tmp_path / "package.ttl").write_text(package)
    return Engine(Project.load(tmp_path))


def test_post_mints_and_journals(tmp_path):
    eng = make(tmp_path)
    iri = eng.post('[] a cmd:AddTask ; cmd:title "write tests" .')
    assert (iri, LR.channel, LR["in"]) in eng.sheet
    assert (iri, CMD.title, Literal("write tests")) in eng.sheet
    assert eng.project.journal[-1].headers["kind"] == "input"
    [m] = eng.messages("in")
    assert m.iri == iri and m.types == [CMD.AddTask]


@pytest.mark.parametrize("text, why", [
    ('ex:list ex:title "x" .', "own new nodes"),
    ('[] a cmd:AddTask ; cmd:title "a" . [] a cmd:AddTask ; cmd:title "b" .', "exactly one root"),
    ('[] a lr:ShellCall ; lr:command "rm -rf /" .', "may not use"),
    ('[] a cmd:AddTask .', "shapes"),
    ('[] a cmd:AddTask ; cmd:title "x"', "does not parse"),
])
def test_post_refused(tmp_path, text, why):
    eng = make(tmp_path)
    before = set(eng.sheet)
    with pytest.raises(PostError, match=why):
        eng.post(text)
    assert set(eng.sheet) == before and eng.project.journal == []


def test_post_may_point_at_state_and_nest(tmp_path):
    eng = make(tmp_path)
    iri = eng.post('[] a cmd:AddTask ; cmd:title "x" ; cmd:list ex:list ; cmd:meta [ ex:by "me" ] .')
    [m] = eng.messages("in")
    assert m.iri == iri
    assert len(m.triples) == 6  # 5 about the message (with lr:channel) + 1 about its nested part


def test_operation_consumes_and_replies(tmp_path):
    eng = make(tmp_path)
    iri = eng.post('[] a cmd:AddTask ; cmd:title "write tests" .')
    assert eng.run().status == "done"
    assert eng.messages("in") == []
    assert len(list(eng.sheet.subjects(RDF.type, EX.Task))) == 1
    [out] = eng.messages("out")
    assert out.text == "write tests" and (out.iri, LR.replyTo, iri) in eng.sheet
    assert eng.ack([out.iri]) == 1
    assert eng.messages("out") == [] and eng.project.journal[-1].headers["kind"] == "ack"


def test_out_order_and_parts(tmp_path):
    eng = make(tmp_path)
    for title in ("one", "two", "three"):
        eng.post(f'[] a cmd:AddTask ; cmd:title "{title}" .')
        eng.run()
    assert [m.text for m in eng.messages("out")] == ["one", "two", "three"]
    # a minted node that state also refers to is not part of a message: ack must not delete it
    task = next(eng.sheet.subjects(RDF.type, EX.Task))
    first = eng.messages("out")[0]
    eng.edit(add=[(first.iri, EX.about, task), (EX.list, EX.has, task)])
    assert all(t[0] != task for t in eng.messages("out")[0].triples)
    eng.ack([first.iri])
    assert (task, RDF.type, EX.Task) in eng.sheet


def test_listen_over_streams(tmp_path):
    eng = make(tmp_path)
    stdin = io.StringIO('[] a cmd:AddTask ; cmd:title "a" .\n\n[] a cmd:Nope ; lr:status 1 .\n\n'
                        '[] a cmd:AddTask ; cmd:title "b" .\n')
    stdout = io.StringIO()
    from rich.console import Console
    assert listen(eng, stdin, stdout, Console(file=io.StringIO())) == 0
    out = stdout.getvalue()
    assert out.count("# posted") == 2 and "# refused" in out
    assert '"a"' in out and '"b"' in out and out.index('"a"') < out.index('"b"')
    assert eng.messages("out") == []  # printed and acknowledged


def test_app_mode_manifest_roundtrip(tmp_path):
    m = Manifest(title="t", direct_edits=False)
    (tmp_path / "package.ttl").write_text(m.to_graph().serialize(format="turtle"))
    assert read_manifest(tmp_path).direct_edits is False
    assert Manifest(title="t").direct_edits is True


def test_api_app_mode_and_channels(tmp_path):
    make(tmp_path, package=PFX + '<urn:lr:package> a lr:Package ; lr:directEdits false .')
    with TestClient(create_app(tmp_path, trust_path=tmp_path / "trust.ttl")) as c:
        st = c.get("/api/state").json()
        assert st["directEdits"] is False
        edit = {"s": "ex:x", "p": "a", "o": "ex:Thing"}
        assert c.post("/api/sheet/triples", json=edit).status_code == 403
        assert c.post("/api/sheet/triples", json={**edit, "force": True}).status_code == 200

        r = c.post("/api/in", json={"turtle": "[] a cmd:AddTask ."})
        assert r.status_code == 422 and r.json()["detail"]["violations"]
        r = c.post("/api/in", json={"turtle": '[] a cmd:AddTask ; cmd:title "via api" .'})
        assert r.status_code == 200
        assert c.post("/api/autopilot/step").json()["status"] == "applied"
        [m] = c.get("/api/messages", params={"channel": "out"}).json()["messages"]
        assert m["text"] == "via api" and m["types"] == ["lr:Say"]
        assert c.post("/api/out/ack", json={}).json()["acked"] == 1
        assert c.get("/api/messages").json()["messages"] == []


def test_api_listening_autopilot(tmp_path):
    import time
    make(tmp_path)
    with TestClient(create_app(tmp_path, trust_path=tmp_path / "trust.ttl")) as c:
        c.post("/api/autopilot/start", json={"delay_ms": 0, "listen": True})

        def wait(pred):
            for _ in range(200):
                if pred():
                    return True
                time.sleep(0.02)
            return False

        assert wait(lambda: c.get("/api/state").json()["autopilot"] == "listening")
        c.post("/api/in", json={"turtle": '[] a cmd:AddTask ; cmd:title "later" .'})
        assert wait(lambda: c.get("/api/state").json()["messages"]["out"] == 1)
        assert wait(lambda: c.get("/api/state").json()["autopilot"] == "listening")
        c.post("/api/autopilot/listen", json={"listen": False})
        assert wait(lambda: c.get("/api/state").json()["autopilot"] == "done")
