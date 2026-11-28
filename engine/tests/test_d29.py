"""Design D29: lr check, and the arch-check example on a fake package."""

import json
import shutil
from pathlib import Path

from loopingrules.check import check
from loopingrules.cli import main
from loopingrules.tools.shell import ShellTool

ROOT = Path(__file__).resolve().parents[2] / "examples"

# A fake engine/loopingrules: store imports engine (upward), mystery has no layer.
FILES = {
    "store.py": "",
    "engine.py": "from .store import x\n",
    "mystery.py": "from .vocab import LR\n",
    "vocab.py": "",
}
BAD = dict(FILES, **{"store.py": "    from .engine import Engine\n"})


def fake_shell(files: dict[str, str]) -> ShellTool:
    def run(command: str):
        if command.startswith("ls -1 "):
            return 0, "".join(f + "\n" for f in ["__init__.py", *files]), ""
        name = command.rsplit("/", 1)[-1].rstrip("'")
        lines = [ln.strip() for ln in files[name].splitlines() if ln.strip().startswith("from .")]
        return (0 if lines else 1), "".join(" ".join(ln.split()[:3]) + "\n" for ln in lines), ""
    return ShellTool(run)


def project(tmp_path) -> Path:
    p = tmp_path / "arch-check"
    shutil.copytree(ROOT / "arch-check", p)
    return p


def test_layering_holds(tmp_path):
    files = dict(FILES)
    del files["mystery.py"]
    r = check(project(tmp_path), trust_declared=True, trust_path=tmp_path / "t.ttl", shell=fake_shell(files))
    assert r.status == "passed", r.as_dict()
    assert not (tmp_path / "arch-check" / ".lr").exists()  # writes nothing


def test_findings_fail_the_check(tmp_path):
    r = check(project(tmp_path), trust_declared=True, trust_path=tmp_path / "t.ttl", shell=fake_shell(BAD))
    assert r.exit_code == 1
    assert any(f.startswith("store (core) imports engine (runtime)") for f in r.findings)
    assert any(f.startswith("mystery.py has no layer") for f in r.findings)


def test_untrusted_commands_make_it_incomplete(tmp_path):
    r = check(project(tmp_path), trust_path=tmp_path / "t.ttl", shell=fake_shell(FILES))
    assert r.exit_code == 2 and r.refused and r.refused[0].startswith("ls -1")


def test_tick_limit_makes_it_incomplete(tmp_path):
    r = check(project(tmp_path), trust_declared=True, max_ticks=3, trust_path=tmp_path / "t.ttl",
              shell=fake_shell(FILES))
    assert r.exit_code == 2 and "did not come to rest" in r.incomplete


def test_seed_violations_fail(tmp_path):
    p = project(tmp_path)
    (p / "shapes.ttl").write_text(
        "@prefix sh: <http://www.w3.org/ns/shacl#> . @prefix arch: <https://loopingrules.org/arch#> .\n"
        "arch:PackageShape a sh:NodeShape ; sh:targetClass arch:Package ;"
        " sh:property [ sh:path arch:owner ; sh:minCount 1 ] .")
    files = dict(FILES)
    del files["mystery.py"]
    r = check(p, trust_declared=True, trust_path=tmp_path / "t.ttl", shell=fake_shell(files))
    assert r.exit_code == 1 and r.violations and not r.findings


def test_cli_json_and_exit_code(tmp_path, capsys, monkeypatch):
    import loopingrules.check as chk
    original = chk.check
    monkeypatch.setattr(chk, "check", lambda *a, **k: original(*a, **k, shell=fake_shell(BAD),
                                                                 trust_path=tmp_path / "t.ttl"))
    code = main(["check", str(project(tmp_path)), "--trust-declared", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 1 and out["status"] == "failed" and len(out["findings"]) == 2
