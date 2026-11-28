"""examples/rubik: the cube, its turns and its commands (doc/rubik.md, step 1)."""

import random
import shutil
from pathlib import Path

import pytest
from rdflib import Namespace

from loopingrules.engine import Engine
from loopingrules.project import Project

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "rubik"
RK = Namespace("https://example.org/rubik#")
POS = Namespace("https://example.org/rubik/pos#")

FACES = "UDFBRL"
QUARTERS = list(FACES)
ALL_MOVES = [f + s for f in FACES for s in ("", "i", "2")]
INVERSE = {**{f: f + "i" for f in FACES}, **{f + "i": f for f in FACES}, **{f + "2": f + "2" for f in FACES}}


@pytest.fixture
def eng(tmp_path):
    proj = tmp_path / "rubik"
    shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns(".lr", "*.py"))
    return Engine(Project.load(proj))


def colours(eng) -> dict[str, str]:
    return {str(p).rsplit("#", 1)[1]: str(c).rsplit("#", 1)[1] for p, c in eng.sheet.subject_objects(RK.colour)}


def solved(eng) -> bool:
    home = {"U": "White", "D": "Yellow", "F": "Green", "B": "Blue", "R": "Red", "L": "Orange"}
    cs = colours(eng)
    return len(cs) == 54 and all(c == home[p[0]] for p, c in cs.items())


def play(eng, moves: list[str]) -> None:
    eng.post("[] a rk:Scramble ; rk:moves ( " + " ".join(f"mv:{m}" for m in moves) + " ) .")
    result = eng.run(max_ticks=len(moves) + 10)
    assert result.status == "done", result
    assert eng.sheet.value(RK.cube, RK.plan) is not None
    assert not eng.messages("in")
    assert eng.sheet_violations() == []


def test_seed_is_solved_and_valid(eng):
    assert solved(eng)
    assert eng.sheet_violations() == []


@pytest.mark.parametrize("face", QUARTERS)
def test_four_quarter_turns_are_the_identity(eng, face):
    play(eng, [face] * 2)
    assert not solved(eng)
    play(eng, [face] * 2)
    assert solved(eng)
    assert int(eng.sheet.value(RK.cube, RK.turns)) == 4


def test_known_effects(eng):
    """Pins the conventions: R lifts the front's right column to the top; U moves the right face to the front."""
    play(eng, ["R"])
    cs = colours(eng)
    assert [cs[p] for p in ("U3", "U6", "U9")] == ["Green"] * 3
    assert [cs[p] for p in ("F3", "F6", "F9")] == ["Yellow"] * 3
    play(eng, ["Ri", "U"])
    cs = colours(eng)
    assert [cs[p] for p in ("F1", "F2", "F3")] == ["Red"] * 3
    assert [cs[p] for p in ("L1", "L2", "L3")] == ["Green"] * 3


def test_double_is_two_quarters(eng, tmp_path):
    play(eng, ["R2", "F2"])
    doubled = colours(eng)
    play(eng, ["Fi", "Fi", "Ri", "Ri"])
    assert solved(eng)
    play(eng, ["R", "R", "F", "F"])
    assert colours(eng) == doubled


def test_scramble_then_inverse_solves(eng):
    rng = random.Random(7)
    moves = [rng.choice(ALL_MOVES) for _ in range(25)]
    play(eng, moves)
    assert not solved(eng)
    counts = sorted(list(colours(eng).values()).count(c) for c in ("White", "Yellow", "Green", "Blue", "Red", "Orange"))
    assert counts == [9] * 6
    play(eng, [INVERSE[m] for m in reversed(moves)])
    assert solved(eng)
    assert len(list(eng.sheet.subjects(RK.seq, None))) == 50


def test_reset(eng):
    play(eng, ["R", "U", "F2"])
    eng.post("[] a rk:Reset .")
    assert eng.run(max_ticks=5).status == "done"
    assert solved(eng)


def test_commands_wait_for_the_plan(eng):
    eng.post("[] a rk:Scramble ; rk:moves ( mv:R mv:U ) .")
    eng.post("[] a rk:Scramble ; rk:moves ( mv:Ui mv:Ri ) .")
    eng.run(max_ticks=20)
    assert solved(eng)
    assert int(eng.sheet.value(RK.cube, RK.turns)) == 4


def test_scramble_must_list_moves(eng):
    from loopingrules.channels import PostError
    with pytest.raises(PostError, match="shapes|move"):
        eng.post("[] a rk:Scramble ; rk:moves ( mv:R rk:cube ) .")


# --- rubik-viewer: the integration pack (doc/rubik.md, step 2) -------------------

VIEWER = EXAMPLE.parent / "rubik-viewer"
VIZ = Namespace("https://example.org/rubik/viz#")
MV = Namespace("https://example.org/rubik/move#")


def install(proj: Path, pack: Path) -> None:
    target = proj / "layers" / pack.name
    target.mkdir(parents=True)
    for f in pack.glob("*.ttl"):
        shutil.copy(f, target / f.name)


@pytest.fixture
def viewer(tmp_path):
    proj = tmp_path / "rubik"
    shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns(".lr", "*.py"))
    install(proj, VIEWER)
    return Engine(Project.load(proj))


def out_of(eng, kind):
    return [m for m in eng.messages("out") if VIZ[kind] in m.types]


def test_every_turn_is_announced_once(viewer):
    play(viewer, ["R", "U2", "Fi"])
    turns = out_of(viewer, "Turn")
    got = sorted((int(viewer.sheet.value(m.iri, VIZ.seq)), viewer.sheet.value(m.iri, VIZ.move)) for m in turns)
    assert got == [(1, MV.R), (2, MV.U2), (3, MV.Fi)]
    viewer.ack([m.iri for m in turns])
    assert viewer.run(max_ticks=5).status == "done"
    assert out_of(viewer, "Turn") == []


def test_sync_sends_the_state(viewer):
    play(viewer, ["R", "U"])
    viewer.ack([m.iri for m in viewer.messages("out")])
    viewer.post("[] a viz:Sync .")
    assert viewer.run(max_ticks=5).status == "done"
    [state] = out_of(viewer, "State")
    g = viewer.sheet
    assert int(g.value(state.iri, VIZ.turns)) == 2
    sent = {g.value(f, VIZ.pos): g.value(f, VIZ.colour) for f in g.objects(state.iri, VIZ.facelet)}
    assert sent == dict(g.subject_objects(RK.colour))
    viewer.ack([state.iri])
    assert not list(g.subjects(VIZ.pos, None))  # the facelets were parts of the message


def test_ack_wakes_a_listening_autopilot(tmp_path):
    from fastapi.testclient import TestClient
    from loopingrules.api import create_app
    proj = tmp_path / "rubik"
    shutil.copytree(EXAMPLE, proj, ignore=shutil.ignore_patterns(".lr", "*.py"))
    install(proj, VIEWER)
    app = create_app(proj, trust_path=tmp_path / "trust.ttl")
    with TestClient(app) as c:
        c.post("/api/in", json={"turtle": "[] a rk:Scramble ; rk:moves ( mv:R ) ."})
        for _ in range(3):
            c.post("/api/autopilot/step")
        session = app.state.session
        session.input_event.clear()
        assert c.post("/api/out/ack", json={}).json()["acked"] >= 1
        assert session.input_event.is_set()
