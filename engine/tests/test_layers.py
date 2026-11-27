"""Controller packs (layers): a pack with only a controller steers the trajectory."""

import shutil
from pathlib import Path

import pytest
from rdflib import Literal, Namespace

from loopingrules.engine import Engine
from loopingrules.package import PackageError, add_layer, export_project, import_export
from loopingrules.project import Project
from loopingrules.tools.shell import ShellTool

EX = Namespace("https://example.org/folderscan#")
ROOT = Path(__file__).resolve().parents[2] / "examples"


def shell(files: list[str], calls: list[str]):
    def run(cmd):
        calls.append(cmd)
        if cmd.startswith("ls"):
            return 0, "".join(f + "\n" for f in files), ""
        if cmd.startswith("wc -l <"):
            return 0, "3\n", ""
        if cmd.startswith("wc -l '"):  # batch: one line per .txt file, then a total
            txt = [f for f in files if f.endswith(".txt")]
            body = "".join(f"  {i + 1} data/{f}\n" for i, f in enumerate(txt))
            return 0, body + f"  {sum(range(1, len(txt) + 1))} total\n", ""
        raise AssertionError(cmd)
    return ShellTool(executor=run)


def project(tmp_path, with_layer: bool) -> Path:
    p = tmp_path / "proj"
    shutil.copytree(ROOT / "folder-scan", p, ignore=shutil.ignore_patterns(".lr"))
    if with_layer:
        pack = export_project(ROOT / "big-folders", tmp_path / "big-folders.lr.zip")
        add_layer(pack.read_bytes(), p)
    return p


def run(path: Path, files: list[str], extra=()):
    proj = Project.load(path)
    calls: list[str] = []
    eng = Engine(proj, shell=shell(files, calls), approver=lambda c: True)
    if extra:
        eng.edit(add=extra)
    assert eng.run(max_ticks=200).status == "done"
    counts = {str(proj.sheet.value(f, EX.name)): int(n) for f, n in proj.sheet.subject_objects(EX.lineCount)}
    return [c for c in calls if c.startswith("wc")], counts, eng


MANY = ["a.txt", "b.txt", "c.txt", "d.md", "e.py", "f.csv"]  # 6 files > default threshold 4
FEW = ["a.txt", "b.txt", "c.md"]


def test_without_the_pack_counts_per_file(tmp_path):
    wc, counts, _ = run(project(tmp_path, with_layer=False), MANY)
    assert all(c.startswith("wc -l <") for c in wc) and len(wc) == 3
    assert set(counts) == {"a.txt", "b.txt", "c.txt"}


def test_the_pack_switches_to_one_batch_for_big_folders(tmp_path):
    wc, counts, eng = run(project(tmp_path, with_layer=True), MANY)
    assert wc == ["wc -l '.'/*.txt"]  # one batch call instead of three
    assert counts == {"a.txt": 1, "b.txt": 2, "c.txt": 3}
    assert [c.layer for c in eng.controllers if c.name == "batch when many files"] == ["big-folders"]
    assert eng.sheet_violations() == []


def test_the_pack_does_nothing_for_small_folders(tmp_path):
    wc, _, _ = run(project(tmp_path, with_layer=True), FEW)
    assert all(c.startswith("wc -l <") for c in wc) and len(wc) == 2


def test_threshold_is_data_in_the_sheet(tmp_path):
    raise_it = [(EX.settings, EX.batchThreshold, Literal(10))]
    wc, _, _ = run(project(tmp_path, with_layer=True), MANY, extra=raise_it)
    assert all(c.startswith("wc -l <") for c in wc)


def test_pack_rules(tmp_path):
    pack = export_project(ROOT / "big-folders", tmp_path / "pack.lr.zip")
    # a pack is not a project
    with pytest.raises(PackageError, match="controller pack"):
        import_export(pack.read_bytes(), tmp_path / "x")
    # it only goes on top of the package it extends
    goal = tmp_path / "goal"
    shutil.copytree(ROOT / "folder-scan-goal", goal, ignore=shutil.ignore_patterns(".lr"))
    with pytest.raises(PackageError, match="extends 'folder-scan'"):
        add_layer(pack.read_bytes(), goal)
    # and only once
    p = project(tmp_path, with_layer=True)
    with pytest.raises(PackageError, match="already installed"):
        add_layer(pack.read_bytes(), p)


def test_a_pack_cannot_smuggle_a_model(tmp_path):
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("package.ttl", (ROOT / "big-folders" / "package.ttl").read_text())
        z.writestr("controllers.ttl", (ROOT / "big-folders" / "controllers.ttl").read_text())
        z.writestr("model.ttl", (ROOT / "folder-scan" / "model.ttl").read_text())
    with pytest.raises(PackageError, match="only contain controllers"):
        add_layer(buf.getvalue(), project(tmp_path, with_layer=False))
