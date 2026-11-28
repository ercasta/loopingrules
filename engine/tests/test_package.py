import io
import shutil
import zipfile
from pathlib import Path

import pytest

from loopingrules.engine import Engine
from loopingrules.package import PackageError, declared, export_project, import_export, inspect_export, read_manifest
from loopingrules.project import Project

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "folder-scan"


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buf.getvalue()


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "folder-scan"
    shutil.copytree(EXAMPLE, p, ignore=shutil.ignore_patterns(".lr"))
    return p


def test_round_trip(proj, tmp_path):
    out = export_project(proj, tmp_path / "x.lr.zip")
    names = set(zipfile.ZipFile(out).namelist())
    assert names == {"package.ttl", "model.ttl", "controllers.ttl", "sheet.ttl", "README.md"}
    manifest = import_export(out.read_bytes(), tmp_path / "imported")
    assert manifest.title == "folder-scan"
    assert {"ls -1p '{}'", "wc -l < '{}'"} <= set(manifest.may_run)
    eng = Engine(Project.load(tmp_path / "imported"))
    assert [a.operation.name for a in eng.applications()] == ["scan folder"]


def test_export_never_contains_runtime_state(proj, tmp_path):
    (proj / ".lr").mkdir()
    (proj / ".lr" / "history.rdfp").write_text("TX .\nTC .\n")
    out = export_project(proj, tmp_path / "x.lr.zip", sheet="none")
    assert set(zipfile.ZipFile(out).namelist()) == {"package.ttl", "model.ttl", "controllers.ttl", "README.md"}


@pytest.mark.parametrize("files,why", [
    ({"model.ttl": "", "../evil.ttl": ""}, "unexpected file"),
    ({"model.ttl": "", "sub/model.ttl": ""}, "unexpected file"),
    ({"README.md": "hi"}, "no definitions or knowledge"),
    ({"knowledge.ttl": "<urn:a> <urn:b> [ <urn:c> 1 ] ."}, "blank nodes"),
    ({"model.ttl": "", "sheet.ttl": "", "package.ttl": '@prefix lr: <https://loopingrules.org/ns#> . '
                   '<urn:p> a lr:Package ; lr:extends "base" .'}, "no state"),
    ({"model.ttl": "this is not turtle"}, "does not parse"),
    ({"model.ttl": '@prefix lr: <https://loopingrules.org/ns#> . <urn:x> a lr:Operation ; '
                   'lr:where "?s ?p ?o SERVICE <http://evil.example/> { ?a ?b ?c }" .'}, "SERVICE"),
    ({"model.ttl": "", "package.ttl": '@prefix lr: <https://loopingrules.org/ns#> . '
                   '<urn:p> a lr:Package ; lr:mayRun "rm -rf {}" .'}, "not a valid template"),
])
def test_hostile_exports_are_refused(files, why):
    with pytest.raises(PackageError, match=why):
        inspect_export(make_zip(files))


def test_import_refuses_non_empty_destination(proj, tmp_path):
    out = export_project(proj, tmp_path / "x.lr.zip")
    with pytest.raises(PackageError, match="not empty"):
        import_export(out.read_bytes(), proj)


def test_declared_commands(proj):
    m = read_manifest(proj)
    assert declared(m, "ls -1p 'data'") is True
    assert declared(m, "curl 'http://x'") is False
    assert declared(None, "ls") is None
