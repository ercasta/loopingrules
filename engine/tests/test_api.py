import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from loopingrules.api import create_app

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "folder-scan"


@pytest.fixture
def client(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("1\n2\n")
    proj = tmp_path / "proj"
    shutil.copytree(EXAMPLE, proj)
    sheet = (proj / "sheet.ttl").read_text().replace('ex:path "."', f'ex:path "{data.as_posix()}"')
    (proj / "sheet.ttl").write_text(sheet)
    with TestClient(create_app(proj)) as c:
        yield c


def test_sheet_and_edit(client):
    s = client.get("/api/sheet").json()
    assert any(t["p"]["short"] == "ex:path" for t in s["triples"])
    assert s["violations"] == []
    r = client.post("/api/sheet/triples", json={"s": "ex:orphan", "p": "a", "o": "ex:File"})
    assert r.status_code == 200
    s = client.get("/api/sheet").json()
    added = next(t for t in s["triples"] if t["s"]["short"] == "ex:orphan")
    assert added["changed"]
    assert any(v["focus"] == "ex:orphan" for v in s["violations"])
    r = client.post("/api/sheet/delete", json={k: added[k]["n3"] for k in "spo"})
    assert r.status_code == 200
    assert client.get("/api/sheet").json()["violations"] == []


def test_bad_term(client):
    r = client.post("/api/sheet/triples", json={"s": "nope:x", "p": "a", "o": "1"})
    assert r.status_code == 400


def test_manual_apply_and_approval(client):
    apps = client.get("/api/applications").json()["applications"]
    assert [a["operation"] for a in apps] == ["scan folder"]
    assert client.post(f"/api/apply/{apps[0]['id']}").status_code == 200
    [call] = client.get("/api/state").json()["pending"]
    assert call["command"].startswith("ls -1p")
    assert client.post("/api/approvals", json={"id": call["id"], "approve": True}).status_code == 200
    assert client.get("/api/state").json()["pending"] == []
    ops = {a["operation"] for a in client.get("/api/applications").json()["applications"]}
    assert ops == {"register file"}


def test_contains_filter(client):
    r = client.get("/api/applications", params={"contains": "?f ex:scanned true"}).json()
    assert len(r["applications"]) == 1
    r = client.get("/api/applications", params={"contains": "?f ex:lineCount ?n"}).json()
    assert r["applications"] == []


def test_autopilot_with_approvals(client):
    client.post("/api/autopilot/start", json={"delay_ms": 0})
    deadline = time.time() + 30
    while time.time() < deadline:
        st = client.get("/api/state").json()
        for call in st["pending"]:
            client.post("/api/approvals", json={"id": call["id"], "approve": True})
        if st["autopilot"] == "done":
            break
        time.sleep(0.05)
    assert st["autopilot"] == "done"
    triples = client.get("/api/sheet").json()["triples"]
    assert any(t["p"]["short"] == "ex:lineCount" and t["o"]["value"] == "2" for t in triples)


def test_suggest_predicates_for_new_file(client):
    client.post("/api/sheet/triples", json={"s": "ex:f1", "p": "a", "o": "ex:File"})
    r = client.get("/api/suggest", params={"field": "p", "s": "ex:f1"}).json()
    missing = {m["value"] for m in r["missing"]}
    assert missing == {"ex:name", "ex:inFolder"}
    values = [i["value"] for i in r["items"]]
    assert values.index("ex:name") < values.index("ex:extension")  # missing first


def test_suggest_objects(client):
    client.post("/api/sheet/triples", json={"s": "ex:f1", "p": "a", "o": "ex:File"})
    # sh:class -> existing instances
    r = client.get("/api/suggest", params={"field": "o", "s": "ex:f1", "p": "ex:inFolder"}).json()
    assert [i["value"] for i in r["items"]] == ["ex:target"]
    assert r["constraint"]["class"] == "ex:Folder"
    # sh:datatype
    r = client.get("/api/suggest", params={"field": "o", "s": "ex:f1", "p": "ex:lineCount"}).json()
    assert r["constraint"] == {"kind": "literal", "datatype": "xsd:integer"}
    # rdf:type -> target classes
    r = client.get("/api/suggest", params={"field": "o", "s": "ex:new", "p": "a"}).json()
    assert {"ex:File", "ex:Folder", "lr:ShellCall"} <= {i["value"] for i in r["items"]}
    # sh:in on the built-in tool shape
    client.post("/api/sheet/triples", json={"s": "ex:c", "p": "a", "o": "lr:ShellCall"})
    r = client.get("/api/suggest", params={"field": "o", "s": "ex:c", "p": "lr:status"}).json()
    assert [i["value"] for i in r["items"]] == ["lr:Pending", "lr:Done", "lr:Rejected", "lr:Failed"]


def test_suggest_full_and_typable(client):
    r = client.get("/api/suggest", params={"field": "o", "s": "ex:target", "p": "ex:path"}).json()
    assert "full" in r["constraint"]
    r = client.get("/api/suggest", params={"field": "p", "s": "ex:target"}).json()
    assert next(i for i in r["items"] if i["value"] == "ex:path")["status"] == "full"
    r = client.get("/api/suggest", params={"field": "s", "q": "targ"}).json()
    assert r["items"] == [{"value": "ex:target", "hint": "ex:Folder"}]
