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
