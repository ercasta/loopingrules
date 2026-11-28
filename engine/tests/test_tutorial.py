"""Design D26: the tutorial, played from start to finish.

This also documents the intended solution of every lesson.
"""

import shutil
from pathlib import Path

from rdflib import RDF, Literal, Namespace

from loopingrules.engine import Engine
from loopingrules.project import Project

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "tutorial"
TUT = Namespace("https://loopingrules.org/tutorial#")
EX = Namespace("https://example.org/")


def lesson(eng) -> str:
    return str(eng.sheet.value(TUT.progress, TUT.current)).rsplit("#", 1)[-1]


def said(eng) -> list[str]:
    """Everything the tutorial said since last time (acknowledged on reading)."""
    out = eng.messages("out")
    eng.ack([m.iri for m in out])
    return [m.text for m in out]


def settle(eng) -> str:
    result = eng.run(max_ticks=50)
    assert result.status == "stopped" and result.application.operation.name == "wait for you", result
    return lesson(eng)


def test_play_through(tmp_path):
    proj = tmp_path / "tutorial"
    shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns(".lr"))
    eng = Engine(Project.load(proj))

    # The welcome is in the seed; starting autopilot presents lesson 0.
    assert said(eng)[0].startswith("Welcome to LoopingRules!")
    assert settle(eng) == "L0"
    assert said(eng)[0].startswith("Lesson 0")

    # Anything it doesn't understand gets an answer, and is consumed.
    eng.post("[] a ex:Nonsense .")
    settle(eng)
    assert "I can't do anything with that" in said(eng)[0]
    assert eng.messages("in") == []

    eng.post("[] a tut:Next .")
    assert settle(eng) == "L1"
    assert said(eng)[0].startswith("Lesson 1")

    # Next only works on reading lessons; a hint always works.
    eng.post("[] a tut:Next .")
    eng.post("[] a tut:Hint .")
    settle(eng)
    answers = said(eng)
    assert any("I can't do anything" in a for a in answers) and any("Click the subject field" in a for a in answers)
    assert lesson(eng) == "L1"

    eng.edit(add=[(EX.me, RDF.type, EX.Person)])
    assert settle(eng) == "L2"
    assert [a.split("\n")[0][:9] for a in said(eng)] == ["There it ", "Lesson 2 "]

    eng.edit(add=[(EX.me, EX.name, Literal("Ada"))])
    assert settle(eng) == "L3"
    said(eng)

    eng.edit(add=[(EX.me, EX.knows, EX.grace)])
    assert settle(eng) == "L3"  # ex:grace isn't a person yet
    eng.edit(add=[(EX.grace, RDF.type, EX.Person)])
    assert settle(eng) == "L4"
    said(eng)
    assert eng.sheet_violations()  # ex:grace has no name

    eng.edit(add=[(EX.grace, EX.name, Literal("Grace"))])
    assert settle(eng) == "L5"
    said(eng)
    assert eng.sheet_violations() == []

    # Autopilot won't introduce by itself (wait scores higher): apply it by hand.
    [intro] = [a for a in eng.applications() if a.operation.name == "introduce" and a.valid]
    eng.apply(intro)
    assert settle(eng) == "L6"
    texts = said(eng)
    assert "Ada has been introduced to Grace." in texts
    # Lesson 6 unlocked greeting, and "prefer formal" is on.
    assert {str(o) for o in eng.sheet.objects(None, EX.greetingStyle)} == {"formal"}

    for c in eng.controllers:
        if c.name in ("prefer formal", "prefer casual"):
            c.active = not c.active
    eng.edit(add=[(EX.alan, RDF.type, EX.Person), (EX.alan, EX.name, Literal("Alan"))])
    assert settle(eng) == "L7"
    assert "Hey Alan! 👋" in said(eng)

    # Commands are checked by shapes: ex:list isn't a person.
    try:
        eng.post("[] a ex:Introduce ; ex:who ex:list ; ex:to ex:me .")
        raise AssertionError("an invalid command was accepted")
    except ValueError:
        pass
    eng.post("[] a ex:Introduce ; ex:who ex:alan ; ex:to ex:me .")
    assert settle(eng) == "L8"
    texts = said(eng)
    assert "Done: Ada now knows Alan." in texts and any(t.startswith("Lesson 8") for t in texts)
    assert (EX.me, EX.knows, EX.alan) in eng.sheet
    assert eng.messages("in") == []
    assert eng.sheet_violations() == []

    # The end: there's no next lesson.
    eng.post("[] a tut:Next .")
    assert settle(eng) == "L8"


def test_skip_everything(tmp_path):
    proj = tmp_path / "tutorial"
    shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns(".lr"))
    eng = Engine(Project.load(proj))
    settle(eng)
    for _ in range(8):
        eng.post("[] a tut:Skip .")
        settle(eng)
    assert lesson(eng) == "L8"


def test_lr_tutorial_copies_then_resumes(tmp_path, monkeypatch):
    from loopingrules import cli

    served = []
    monkeypatch.setattr(cli, "cmd_serve", lambda args, console: served.append(args.project) or 0)
    dest = tmp_path / "learn"
    assert cli.main(["tutorial", str(dest)]) == 0
    assert (dest / "model.ttl").exists() and not (dest / ".lr").exists()
    (dest / "sheet.ttl").write_text((dest / "sheet.ttl").read_text(encoding="utf-8") + "\n# mine\n", encoding="utf-8")
    assert cli.main(["tutorial", str(dest)]) == 0  # resumes: the copy is left alone
    assert (dest / "sheet.ttl").read_text(encoding="utf-8").endswith("# mine\n")
    assert served == [str(dest), str(dest)]
    other = tmp_path / "other"
    other.mkdir()
    assert cli.main(["tutorial", str(other)]) == 1  # not a project: refused
