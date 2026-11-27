import shutil
from pathlib import Path

import pytest
from rdflib import Literal, Namespace
from rdflib.namespace import RDF, XSD

from loopingrules.engine import Engine
from loopingrules.project import Project
from loopingrules.tools.shell import ShellTool
from loopingrules.vocab import LR

EX = Namespace("https://example.org/folderscan#")
EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "folder-scan"


@pytest.fixture
def project(tmp_path):
    data = tmp_path / "data"
    (data / "sub").mkdir(parents=True)
    (data / "a.txt").write_text("one\ntwo\nthree\n")
    (data / "B.MD").write_text("# hi\n")
    (data / "noext").write_text("x")
    proj_dir = tmp_path / "proj"
    shutil.copytree(EXAMPLE, proj_dir, ignore=shutil.ignore_patterns(".lr"))
    seed = proj_dir / "sheet.ttl"
    seed.write_text(seed.read_text().replace('ex:path "."', f'ex:path "{data.as_posix()}"'))
    return Project.load(proj_dir)


SMALL = {"ls": "a.txt\n", "wc": "3\n"}


def fake_shell(outputs):
    """Executor returning canned output for commands starting with a given prefix."""
    def run(cmd):
        for prefix, out in outputs.items():
            if cmd.startswith(prefix):
                return 0, out, ""
        raise AssertionError(f"unexpected command {cmd}")
    return ShellTool(executor=run)


def test_initial_applications(project):
    apps = Engine(project).applications()
    assert [a.operation.name for a in apps] == ["scan folder"]
    app = apps[0]
    assert app.valid
    # Resulting state has one pending call -> -1; no progress yet -> 0
    assert app.scores == {"progress": 0.0, "prefer few pending calls": -1.0, "prefer per-file counts": 0.0}


def test_autopilot_pauses_for_approval(project):
    eng = Engine(project)
    assert eng.step().status == "applied"
    assert eng.step().status == "awaiting-approval"
    [call] = eng.pending_calls()
    assert call.command.startswith("ls -1p '")
    eng.resolve(call.iri.n3(), approve=False)
    assert (call.iri, LR.status, LR.Rejected) in eng.sheet
    assert eng.step().status == "done"


def test_end_to_end_with_stub_shell(project):
    shell = fake_shell({"ls": "a.txt\nB.MD\nnoext\nsub/\n", "wc": "3\n"})
    eng = Engine(project, shell=shell, approver=lambda call: True)
    result = eng.run(max_ticks=50)
    assert result.status == "done"
    g = eng.sheet
    files = {str(g.value(f, EX.name)): f for f in g.subjects(RDF.type, EX.File)}
    assert set(files) == {"a.txt", "B.MD", "noext"}
    assert g.value(files["B.MD"], EX.extension) == Literal("md")
    assert g.value(files["noext"], EX.extension) is None
    assert g.value(files["a.txt"], EX.lineCount) == Literal(3, datatype=XSD.integer)
    assert eng.sheet_violations() == []


def test_end_to_end_real_shell(project):
    eng = Engine(project, approver=lambda call: True)
    assert eng.run(max_ticks=50).status == "done"
    g = eng.sheet
    a = next(f for f in g.subjects(EX.name, Literal("a.txt")))
    assert g.value(a, EX.lineCount) == Literal(3, datatype=XSD.integer)


def test_shacl_guard_blocks_invalid_application(project):
    project.model.parse(data="""
        @prefix lr: <https://loopingrules.org/ns#> .
        @prefix ex: <https://example.org/folderscan#> .
        ex:secondPath a lr:Operation ;
          lr:where "?f a ex:Folder" ;
          lr:insert "?f ex:path \\"/other\\"" .
    """, format="turtle")
    apps = {a.operation.name: a for a in Engine(project).applications()}
    bad = apps["ex:secondPath"]
    assert not bad.valid and bad.violations and not bad.scores
    assert apps["scan folder"].valid


def test_invalid_sheet_does_not_block(project):
    # D13: a pre-existing violation must not make every application invalid
    project.sheet.add((EX.orphan, RDF.type, EX.File))  # missing name and folder
    eng = Engine(project)
    assert eng.sheet_violations()
    assert all(a.valid for a in eng.applications())


def test_journal_survives_restart_and_undo(project):
    eng = Engine(project, shell=fake_shell(SMALL), approver=lambda c: True)
    eng.run(max_ticks=50)
    n_triples = len(project.sheet)
    assert (project.path / ".lr" / "history.rdfp").exists()
    # authored files are never rewritten
    assert "Point this at a folder" in (project.path / "sheet.ttl").read_text()

    again = Project.load(project.path)  # replay the journal on top of the seed
    assert set(again.sheet) == set(project.sheet)
    assert len(again.sheet) == n_triples
    assert Engine(again).applications() == []

    # undo the last change, also across a restart
    last = again.last_undoable()
    Engine(again).undo()
    assert len(again.sheet) != n_triples
    third = Project.load(again.path)
    assert set(third.sheet) == set(again.sheet)
    assert third.last_undoable().n < last.n  # the undone change is not offered again


def test_snapshot_then_replay(project):
    eng = Engine(project, shell=fake_shell(SMALL), approver=lambda c: True)
    eng.run(max_ticks=3)
    project.snapshot()
    eng.run(max_ticks=50)
    again = Project.load(project.path)
    assert again.snapshot_tx > 0
    assert set(again.sheet) == set(project.sheet)


def test_no_blank_nodes_after_ticks(project):
    from rdflib import BNode
    eng = Engine(project, shell=fake_shell(SMALL), approver=lambda c: True)
    eng.run(max_ticks=50)
    assert not any(isinstance(x, BNode) for t in project.sheet for x in t)
